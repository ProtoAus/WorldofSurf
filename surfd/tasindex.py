"""P1806: uploaded TAS runs on the main board's TAS tab.

  python3 tasindex.py --store <tasup.sqlite3> --db <surfd.db> --state <tasindex.sqlite3> [--dry-run]

tasupd (P1640) keeps uploads in its own store and showed them only on /tasup/board; the board's TAS tab (web and game)
is surfd's community/tas rows. Each run files the best shown upload per (map, track, player) as one of those rows:
node 'tasup', runid 'tasup-<id>', flags TF_TAS, no replay (surfd serves no tasupd file yet). The player's own row there
stays when it is as fast (the board's order: millis, then submitted); a slower lobby row is replaced and kept in
--state, and put back when the upload stops being shown. A row of ours whose upload is no longer the player's best
shown one is taken out. Banned accounts are left alone (accounts.ban_rows parks their rows); an upload whose row surfd
moved to another tier (a review set-aside) is not filed again. --state also lists the rows filed, so a pass reads
surfd.db by primary key only (no scan under the write lock); --full scans for strays by hand. Safe to run every few
minutes. surfd is not imported: its connect() migrates, and this runs beside whichever generation is live.
"""
import argparse
import json
import re
import sqlite3
import sys
import time

TF_TAS = 4194304            # surfd.TF_TAS
TIER, STYLE = 'community', 'tas'   # surfd.TIER_COMMUNITY, STYLE_TAS: the TAS board's only tier
NODE, RUNID = 'tasup', 'tasup-%d'
RATE = 66.6667              # what lobby rows store for the game's tick; tasupd.TICK is 0.015
MAX_TRACK = 99              # tasupd.MAX_TRACK
MAPNAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}$')   # surfd._MAPNAME_OK
COLS = ('map', 'track', 'leg', 'tier', 'style', 'player', 'name', 'ticks', 'tickrate', 'millis', 'flags', 'node',
        'runid', 'submitted', 'replay_id', 'plat', 'pad', 'oldgame')


def connect(path, readonly=False):
    if readonly:
        db = sqlite3.connect('file:%s?mode=ro' % path, uri=True, timeout=15)
    else:
        db = sqlite3.connect(path, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout = 15000')
    return db


def shown_uploads(store):
    """{(map, track, steamid): (id, ticks, uploaded_at)} of each player's best shown run on a course."""
    db = connect(store, readonly=True)
    try:
        rows = db.execute("SELECT id, steamid, map, track, ticks, uploaded_at FROM runs WHERE state = 'shown'"
                          ' ORDER BY ticks, id').fetchall()
    finally:
        db.close()
    best = {}
    for r in rows:
        mp = (r['map'] or '').lower()
        if not MAPNAME.match(mp) or not 0 <= r['track'] <= MAX_TRACK or r['ticks'] <= 0:
            continue
        best.setdefault((mp, r['track'], r['steamid']), (r['id'], r['ticks'], r['uploaded_at']))
    return best


def board_row(key, up, name):
    (mp, track, sid), (rid, ticks, at) = key, up
    return dict(map=mp, track=track, leg=0, tier=TIER, style=STYLE, player=sid, name=name, ticks=ticks,
                tickrate=RATE, millis=int(round(ticks * 1000.0 / RATE)), flags=TF_TAS, node=NODE, runid=RUNID % rid,
                submitted=at, replay_id=0, plat=0, pad=0, oldgame=0)


def put(db, row):
    db.execute('INSERT INTO runs (%s) VALUES (%s) ON CONFLICT(map, track, leg, tier, style, player) DO UPDATE SET %s'
               % (', '.join(COLS), ','.join('?' * len(COLS)),
                  ', '.join('%s = excluded.%s' % (c, c) for c in COLS[6:])), [row[c] for c in COLS])


def course_rows(db, key):
    """Every TAS row of player key[2] on course (key[0], key[1]): the primary key's (map, track, leg) prefix."""
    return db.execute('SELECT rowid, * FROM runs WHERE map = ? AND track = ? AND leg = 0 AND style = ? AND player = ?',
                      (key[0], key[1], STYLE, key[2])).fetchall()


def sync(store, surfd_db, state, dry_run=False, full=False, log=print):
    """One pass. full: also find rows of ours the state does not list (a scan of every runs row: by hand only).
    -> {'added', 'updated', 'removed', 'restored', 'kept_lobby', 'skipped'} counts."""
    want = shown_uploads(store)
    n = dict(added=0, updated=0, removed=0, restored=0, kept_lobby=0, skipped=0)
    st = connect(state)
    st.execute('CREATE TABLE IF NOT EXISTS filed(map TEXT NOT NULL, track INTEGER NOT NULL, player TEXT NOT NULL,'
               ' PRIMARY KEY(map, track, player))')
    st.execute('CREATE TABLE IF NOT EXISTS displaced(map TEXT NOT NULL, track INTEGER NOT NULL, player TEXT NOT NULL,'
               ' row TEXT NOT NULL, PRIMARY KEY(map, track, player))')
    db = connect(surfd_db)
    try:
        st.execute('BEGIN IMMEDIATE')
        db.execute('BEGIN IMMEDIATE')
        keys = set(want) | {tuple(r) for r in st.execute('SELECT map, track, player FROM filed')}
        if full:
            keys |= {tuple(r) for r in db.execute('SELECT DISTINCT map, track, player FROM runs WHERE node = ?'
                                                  ' AND leg = 0 AND style = ?', (NODE, STYLE))}
        accts, sids = {}, sorted({k[2] for k in keys})
        for i in range(0, len(sids), 500):
            part = sids[i:i + 500]
            for r in db.execute('SELECT steamid, name, banned_at FROM accounts WHERE steamid IN (%s)'
                                % ','.join('?' * len(part)), part):
                accts[r['steamid']] = (r['name'] or '', bool(r['banned_at']))
        for key in sorted(keys):
            sid = key[2]
            if sid in accts and accts[sid][1]:
                continue                    # banned: accounts.ban_rows parks and restores their rows
            up = want.get(key) if sid in accts else None    # tasupd's board shows no unknown account
            row = board_row(key, up, accts[sid][0] or 'Steam ' + sid[-4:]) if up else None   # tasupd's who()
            rows = course_rows(db, key)
            # surfd moved this upload's row to another tier (a review set-aside): not filed again, still watched
            parked = row is not None and any(r['runid'] == row['runid'] and r['tier'] != TIER for r in rows)
            if parked:
                n['skipped'] += 1
                row = None
            for r in rows:
                if r['node'] == NODE and r['tier'] == TIER and (row is None or r['runid'] != row['runid']):
                    db.execute('DELETE FROM runs WHERE rowid = ?', (r['rowid'],))
                    n['removed'] += 1
                    log('removed %s %s/%d %s' % ((r['runid'],) + key))
                elif r['node'] == NODE and r['tier'] != TIER and not parked:
                    db.execute('DELETE FROM runs WHERE rowid = ?', (r['rowid'],))    # a set-aside copy of a gone upload
                    n['removed'] += 1
                    log('removed %s (%s) %s/%d %s' % ((r['runid'], r['tier']) + key))
            cur = db.execute('SELECT * FROM runs WHERE map = ? AND track = ? AND leg = 0 AND tier = ? AND style = ?'
                             ' AND player = ?', (key[0], key[1], TIER, STYLE, sid)).fetchone()
            old = st.execute('SELECT row FROM displaced WHERE map = ? AND track = ? AND player = ?', key).fetchone()
            if old is not None and cur is None:
                put(db, json.loads(old['row']))     # the lobby time an upload displaced, back before any compare
                n['restored'] += 1
                log('restored %s/%d %s' % key)
                cur = db.execute('SELECT * FROM runs WHERE map = ? AND track = ? AND leg = 0 AND tier = ? AND style = ?'
                                 ' AND player = ?', (key[0], key[1], TIER, STYLE, sid)).fetchone()
            if old is not None and cur is not None and cur['node'] != NODE:
                st.execute('DELETE FROM displaced WHERE map = ? AND track = ? AND player = ?', key)
            if row is None:
                if not parked:
                    st.execute('DELETE FROM filed WHERE map = ? AND track = ? AND player = ?', key)
                continue
            if cur is not None and cur['node'] != NODE:
                if (cur['millis'], cur['submitted']) <= (row['millis'], row['submitted']):
                    n['kept_lobby'] += 1
                    st.execute('DELETE FROM filed WHERE map = ? AND track = ? AND player = ?', key)
                    continue
                st.execute('INSERT OR REPLACE INTO displaced(map, track, player, row) VALUES (?, ?, ?, ?)',
                           key + (json.dumps({c: cur[c] for c in COLS}),))
            elif cur is not None and all(cur[c] == row[c] for c in COLS):
                st.execute('INSERT OR IGNORE INTO filed(map, track, player) VALUES (?, ?, ?)', key)
                continue
            put(db, row)
            st.execute('INSERT OR IGNORE INTO filed(map, track, player) VALUES (?, ?, ?)', key)
            n['added' if cur is None or cur['node'] != NODE else 'updated'] += 1
            log('%s %s %s/%d %s %d ticks' % ('updated' if cur is not None and cur['node'] == NODE else 'filed',
                                              row['runid'], key[0], key[1], sid, row['ticks']))
        # state first: a lost surfd commit leaves only a stale entry, which the next pass drops
        end = 'ROLLBACK' if dry_run else 'COMMIT'
        st.execute(end)
        db.execute(end)
    except BaseException:
        for c in (st, db):
            if c.in_transaction:
                c.execute('ROLLBACK')
        raise
    finally:
        db.close()
        st.close()
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--store', required=True, help="tasupd's tasup.sqlite3 (read only)")
    ap.add_argument('--db', required=True, help="surfd's surfd.db")
    ap.add_argument('--state', required=True, help='this tool\'s own sqlite file (lobby rows an upload displaced)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--full', action='store_true', help='also scan every runs row for ours (slow; by hand)')
    ap.add_argument('--quiet', action='store_true', help='print only the totals line, and only when something changed')
    a = ap.parse_args(argv)
    n = sync(a.store, a.db, a.state, a.dry_run, a.full, log=(lambda s: None) if a.quiet else print)
    if not a.quiet or any(n[k] for k in ('added', 'updated', 'removed', 'restored')):
        print('%s tasindex%s: %s' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), ' (dry run)' if a.dry_run else '',
                                    ' '.join('%s=%d' % kv for kv in n.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
