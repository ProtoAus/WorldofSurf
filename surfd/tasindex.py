"""P1806: uploaded TAS runs on the main board's TAS tab.

  python3 tasindex.py --store <tasup.sqlite3> --db <surfd.db> [--dry-run] [--full] [--withdraw] [--quiet]

tasupd (P1640) keeps uploads in its own store and showed them only on /tasup/board; the board's TAS tab (web and game)
is surfd's community/tas rows. Each pass files a player's best shown upload on a course as one of those rows (node
'tasup', runid 'tasup-<id>', TF_TAS, rep 0: surfd serves no tasupd file) -- only into an empty slot: a player with any
TAS row of their own on that course (live or set aside by surfd), or an unrejected lobby recording of it, keeps it, and
the upload stays on /tasup/board only.
A row of ours whose upload is no longer the player's best shown one is taken out, and the slot refilled from the
player's best unrejected lobby replay, as surfd.restand does. Banned accounts are left to accounts.ban_rows; an upload
whose row surfd set aside is not filed again. No state: the courses looked at are every (map, track, player) the
store has ever held, read by primary key; the write lock is taken only when something changes. --full also scans
surfd.db for strays (before the lock); --withdraw takes every upload row off (rollback). surfd is not imported: its
connect() migrates, and this runs beside whichever generation is live.
"""
import argparse
import re
import sqlite3
import sys
import time

TF_TAS = 4194304            # surfd.TF_TAS
TIER, STYLE = 'community', 'tas'   # surfd.TIER_COMMUNITY, STYLE_TAS: the TAS board's only tier
NODE, RUNID, RUNID_RE = 'tasup', 'tasup-%d', re.compile(r'^tasup-[0-9]+$')
RATE = 66.6667              # what lobby rows store for the game's tick; tasupd.TICK is 0.015
MAX_TRACK = 99              # tasupd.MAX_TRACK
MAPNAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}$')   # surfd._MAPNAME_OK; clean_map also refuses '..'
REJECTED_SQL = ("EXISTS (SELECT 1 FROM reviews w WHERE w.replay_id = p.id"
                " AND w.decision = 'reject' AND w.at >= p.submitted)")   # surfd._REJECTED_SQL
COLS = ('map', 'track', 'leg', 'tier', 'style', 'player', 'name', 'ticks', 'tickrate', 'millis', 'flags', 'node',
        'runid', 'submitted', 'replay_id', 'plat', 'pad', 'oldgame')   # surfd._UPSERT_RUN's (runs also has momdemo)
UPSERT = ('INSERT INTO runs (%s) VALUES (%s) ON CONFLICT(map, track, leg, tier, style, player) DO UPDATE SET %s'
          % (', '.join(COLS), ','.join('?' * len(COLS)), ', '.join('%s = excluded.%s' % (c, c) for c in COLS[6:])))


def connect(path, readonly=False):
    if readonly:
        db = sqlite3.connect('file:%s?mode=ro' % path, uri=True, timeout=15)
    else:
        db = sqlite3.connect(path, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout = 15000')
    return db


def read_store(store):
    """({(map, track, steamid): (id, ticks, uploaded_at)} of each best shown run, every key the store has held)."""
    db = connect(store, readonly=True)
    try:
        rows = db.execute('SELECT id, steamid, map, track, ticks, uploaded_at, state FROM runs ORDER BY ticks, id').fetchall()
    finally:
        db.close()
    best, keys = {}, set()
    for r in rows:
        mp = (r['map'] or '').lower()
        if not MAPNAME.match(mp) or '..' in mp or not 0 <= r['track'] <= MAX_TRACK:
            continue
        key = (mp, r['track'], r['steamid'])
        keys.add(key)
        if r['state'] == 'shown' and r['ticks'] > 0:
            best.setdefault(key, (r['id'], r['ticks'], r['uploaded_at']))
    return best, keys


def ours(r):
    return r['node'] == NODE and RUNID_RE.match(r['runid'] or '') and r['replay_id'] == 0


def plan(db, key, up, name, banned=False, withdraw=False):
    """[(action, arg)] for one course and player; `up` is the best shown upload or None."""
    want = None
    if up is not None:
        rid, ticks, at = up
        want = dict(map=key[0], track=key[1], leg=0, tier=TIER, style=STYLE, player=key[2], name=name, ticks=ticks,
                    tickrate=RATE, millis=int(round(ticks * 1000.0 / RATE)), flags=TF_TAS, node=NODE,
                    runid=RUNID % rid, submitted=at, replay_id=0, plat=0, pad=0, oldgame=0)
    rows = db.execute('SELECT rowid, * FROM runs WHERE map = ? AND track = ? AND leg = 0 AND style = ? AND player = ?',
                      (key[0], key[1], STYLE, key[2])).fetchall()
    mine = [r for r in rows if ours(r)]
    theirs = [r for r in rows if not ours(r)]
    if banned:                              # accounts.ban_rows parks and restores their rows; withdraw takes ours
        return [('removed', r['rowid']) for r in mine] if want is None and withdraw else []
    if want is not None and any(r['runid'] == want['runid'] and r['tier'] != TIER for r in mine):
        return [('skipped', None)]          # surfd set this upload's row aside (a review): its call, not ours
    # the player's best unrejected lobby recording: submit_run files a slower one with no row while ours stands
    best = db.execute('SELECT p.* FROM replays p WHERE p.map = ? AND p.track = ? AND p.leg = 0 AND p.tier = ?'
                      " AND p.style = ? AND p.player = ? AND p.kind = 'run' AND NOT " + REJECTED_SQL +
                      ' ORDER BY p.millis, p.submitted, p.id LIMIT 1', (key[0], key[1], TIER, STYLE, key[2])).fetchone()
    out, freed = [], False
    for r in mine:
        if want is None or r['runid'] != want['runid']:
            out.append(('removed', r['rowid']))
            freed = freed or r['tier'] == TIER
    if want is not None:
        cur = next((r for r in mine if r['tier'] == TIER and r['runid'] == want['runid']), None)
        if cur is not None:
            if any(cur[c] != want[c] for c in COLS):
                out.append(('updated', want))
            return out
        if not theirs and best is None:
            return out + [('added', want)]
        out.append(('kept_lobby', None))
    if freed and best is not None and not any(r['tier'] == TIER for r in theirs):
        out.append(('refilled', {c: (best['id'] if c == 'replay_id' else '' if c == 'runid' else best[c])
                                 for c in COLS}))   # surfd.restand's row for it
    return out


def sync(store, surfd_db, dry_run=False, full=False, withdraw=False, log=print):
    """One pass. -> {'added', 'updated', 'removed', 'refilled', 'kept_lobby', 'skipped'} counts."""
    best, keys = read_store(store)
    if withdraw:
        best, full = {}, True
    n = dict(added=0, updated=0, removed=0, refilled=0, kept_lobby=0, skipped=0)
    db = connect(surfd_db)
    try:
        if full:
            keys |= {(r['map'], r['track'], r['player']) for r in db.execute(
                'SELECT DISTINCT map, track, player FROM runs WHERE node = ? AND leg = 0 AND style = ?', (NODE, STYLE))}
        accts = {}

        def read_accounts(sids):
            sids = sorted(sids)
            for i in range(0, len(sids), 500):
                part = sids[i:i + 500]
                for r in db.execute('SELECT steamid, name, banned_at FROM accounts WHERE steamid IN (%s)'
                                    % ','.join('?' * len(part)), part):
                    accts[r['steamid']] = (r['name'] or '', bool(r['banned_at']))

        def course(key):
            sid = key[2]
            up = best.get(key) if sid in accts else None    # tasupd's board shows no unknown account
            return plan(db, key, up, accts.get(sid, ('',))[0] or 'Steam ' + sid[-4:],   # tasupd's who()
                        banned=sid in accts and accts[sid][1], withdraw=withdraw)

        read_accounts({k[2] for k in keys})

        todo = []
        for key in sorted(keys):
            acts = course(key)
            for a, _ in acts:
                if a in ('kept_lobby', 'skipped'):
                    n[a] += 1
            if any(a not in ('kept_lobby', 'skipped') for a, _ in acts):
                todo.append(key)
        if not todo:
            return n
        db.execute('BEGIN IMMEDIATE')
        accts.clear()                       # a ban or rename since the first read
        read_accounts({k[2] for k in todo})
        for key in todo:                    # planned again under the lock: surfd may have written since
            for a, arg in course(key):
                if a == 'removed':
                    db.execute('DELETE FROM runs WHERE rowid = ?', (arg,))
                elif a in ('added', 'updated', 'refilled'):
                    db.execute(UPSERT, [arg[c] for c in COLS])
                else:
                    continue
                n[a] += 1
                what = '' if not isinstance(arg, dict) else ' ' + (arg['runid'] or 'rep %d' % arg['replay_id'])
                log('%s %s/%d %s%s' % ((a,) + key + (what,)))
        db.execute('ROLLBACK' if dry_run else 'COMMIT')
    except BaseException:
        if db.in_transaction:
            db.execute('ROLLBACK')
        raise
    finally:
        db.close()
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--store', required=True, help="tasupd's tasup.sqlite3 (read only)")
    ap.add_argument('--db', required=True, help="surfd's surfd.db")
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--full', action='store_true', help='also find upload rows of courses the store no longer names')
    ap.add_argument('--withdraw', action='store_true', help='take every upload row off the board')
    ap.add_argument('--quiet', action='store_true', help='print only the totals line, and only when something changed')
    a = ap.parse_args(argv)
    n = sync(a.store, a.db, a.dry_run, a.full, a.withdraw, log=(lambda s: None) if a.quiet else print)
    if not a.quiet or any(n[k] for k in ('added', 'updated', 'removed', 'refilled')):
        print('%s tasindex%s: %s' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), ' (dry run)' if a.dry_run else '',
                                    ' '.join('%s=%d' % kv for kv in n.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
