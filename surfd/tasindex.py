"""P1806: uploaded TAS runs on the main board's TAS tab.

  python3 tasindex.py --store <tasup.sqlite3> --db <surfd.db> [--tasup-dir DIR] [--dry-run] [--full] [--withdraw] [--quiet]

tasupd (P1640) keeps uploads in its own store and showed them only on /tasup/board; the board's TAS tab (web and game)
is surfd's community/tas rows. Each pass files a player's best shown upload on a course as one of those rows (node
'tasup', runid 'tasup-<id>', TF_TAS) -- only into an empty slot: a player with any
TAS row of their own on that course (live or set aside by surfd), or an unrejected lobby recording of it, keeps it, and
the upload stays on /tasup/board only.
A row of ours whose upload is no longer the player's best shown one is taken out, and the slot refilled from the
player's best unrejected lobby replay, as surfd.restand does. Banned accounts are left to accounts.ban_rows; an upload
whose row surfd set aside is not filed again. No state: the courses looked at are every (map, track, player) the
store has ever held, read by primary key; the write lock is taken only when something changes. --full also scans
surfd.db for strays (before the lock); --withdraw takes every upload row off (rollback). surfd is not imported: its
connect() migrates, and this runs beside whichever generation is live.
P1870: the row's rep is a replays row of kind 'tasup' naming a copy of the upload's .rec under --tasup-dir (surfd's
TASUP_DIR), so the game's click-to-watch works. Copies are made (or repaired) and checked against the upload's sha256
before the write lock; a row whose copy cannot be made, or whose header the game would not read, has rep 0. A
'tasup' replays row no board row names is deleted with its copy, except a rejected one (its reject keys on the id; the
upload stays off the board); unnamed copies are swept after an hour. --withdraw removes all but rejected rows. Needs a
surfd that serves kind 'tasup': deploy after that generation, and roll back with this version's --withdraw first
(an older tasindex does not recognise rows with a rep).
"""
import argparse
import hashlib
import os
import re
import sqlite3
import stat
import sys
import time

TF_TAS = 4194304            # surfd.TF_TAS
TIER, STYLE = 'community', 'tas'   # surfd.TIER_COMMUNITY, STYLE_TAS: the TAS board's only tier
NODE, RUNID, RUNID_RE = 'tasup', 'tasup-%d', re.compile(r'^tasup-[0-9]+$')
KIND, LEAF = 'tasup', 'tasup-%d-%s.rec'          # surfd's replays.kind and _TASLEAF_OK: id, sha256[:16]
LEAF_RE = re.compile(r'^tasup-[1-9][0-9]{0,9}-[0-9a-f]{16}\.rec$')
ORPHAN_AGE = 3600           # s; a copy no replays row names, older than this, is swept (a pass that lost its slot)
HEAD_MAX, LINE_MAX = 64, 4095   # cl_online.qc OR_HEADMAX fgets calls look for `begin`; PF_fgets keeps 4095 bytes
WARN = ('copy ', 'unlink failed', 'sweep failed')      # printed even with --quiet
RATE = 66.6667              # what lobby rows store for the game's tick; tasupd.TICK is 0.015
MAX_TRACK = 99              # tasupd.MAX_TRACK
MAPNAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}$')   # surfd._MAPNAME_OK; clean_map also refuses '..'
REJECTED_SQL = ("EXISTS (SELECT 1 FROM reviews w WHERE w.replay_id = p.id"
                " AND w.decision = 'reject' AND w.at >= p.submitted)")   # surfd._REJECTED_SQL
COLS = ('map', 'track', 'leg', 'tier', 'style', 'player', 'name', 'ticks', 'tickrate', 'millis', 'flags', 'node',
        'runid', 'submitted', 'replay_id', 'plat', 'pad', 'oldgame')   # surfd._UPSERT_RUN's (runs also has momdemo)
UPSERT = ('INSERT INTO runs (%s) VALUES (%s) ON CONFLICT(map, track, leg, tier, style, player) DO UPDATE SET %s'
          % (', '.join(COLS), ','.join('?' * len(COLS)), ', '.join('%s = excluded.%s' % (c, c) for c in COLS[6:])))
RCOLS = ('map', 'map_dir', 'track', 'leg', 'leaf', 'tier', 'style', 'player', 'name', 'ticks', 'tickrate', 'millis',
         'flags', 'node', 'submitted', 'bytes', 'runid', 'bound', 'sha', 'sha_at', 'kind')
REP_UPSERT = ('INSERT INTO replays (%s) VALUES (%s) ON CONFLICT(map, track, leg, leaf) DO UPDATE SET name = excluded.name'
              % (', '.join(RCOLS), ','.join('?' * len(RCOLS))))
# A 'tasup' row no board row names; a rejected one stays (even on --withdraw): the reject keys on its id.
UNNAMED = ("SELECT p.id, p.map_dir, p.track, p.leaf FROM replays p WHERE p.kind = 'tasup'"
           ' AND NOT EXISTS (SELECT 1 FROM runs r WHERE r.replay_id = p.id) AND NOT ' + REJECTED_SQL)


def connect(path, readonly=False):
    if readonly:
        db = sqlite3.connect('file:%s?mode=ro' % path, uri=True, timeout=15)
    else:
        db = sqlite3.connect(path, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout = 15000')
    return db


def default_tasup_dir(surfd_db):
    """surfd's TASUP_DIR: DATA_DIR/tasup, and surfd.db is DATA_DIR/surfd.db."""
    return os.path.join(os.path.dirname(os.path.abspath(surfd_db)), 'tasup')


def leg_dir(track):
    """surfd.leg_dir(track, 0): tasupd uploads are whole courses."""
    return 'main' if track <= 0 else 'bonus_%d' % track


def rec_path(store, sha):
    """tasupd.rec_path."""
    return os.path.join(os.path.dirname(os.path.abspath(store)), 'recs', sha[:2], sha + '.rec')


def copy_path(tasup_dir, key, up):
    return os.path.join(tasup_dir, key[0], leg_dir(key[1]), LEAF % (up[0], up[3][:16]))


def sha_file(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def game_finds_begin(data):
    """cl_online.qc Online_RecName's header scan, so a copy the game cannot store gets no rep: HEAD_MAX calls of
    PF_fgets (pr_bgcmd.c, FILE_READ): each reads to the next \\n dropping \\r, keeps at most LINE_MAX bytes (the byte
    that meets the cap is consumed, not kept); an empty line or the end ends the scan (`!l`); a first word `begin`
    succeeds when the last `FTESURF-REC <ver>` before it read >= 1 (stof = atof). A NUL refuses (Online_ReplayStore's
    fputs would cut there). tokenize (qctokenize: quotes, {}()[]':,; and every byte <= ' ' split) is not replayed:
    a line it could read as FTESURF-REC or begin while a plain split does not, or any \\" (its C-string escapes),
    refuses the file instead. Fuzzed against a C model of PF_fgets/COM_StringParse: no file accepted that it fails."""
    if b'\x00' in data:
        return False
    pos, end, ver = 0, len(data), 0.0
    for _ in range(HEAD_MAX):
        if pos >= end:
            return False
        line = bytearray()
        while pos < end:
            c = data[pos]
            pos += 1
            if c == 10:
                break
            if c == 13:
                continue
            if len(line) >= LINE_MAX:
                break
            line.append(c)
        if not line:
            return False
        if b'\\"' in line:                   # tokenize's C-string escapes (COM_ParseCString): not replayed
            return False
        words = line.split()
        bare = line.lstrip(bytes(range(33)) + b'"\'\\')
        for kw in (b'FTESURF-REC', b'begin'):
            if bare.startswith(kw) and not (words[:1] == [kw] and line[:1] in (b' ', b'\t', kw[:1])):
                return False
        if words[:1] == [b'begin']:
            return ver >= 1
        if len(words) >= 2 and words[0] == b'FTESURF-REC':
            num = re.match(rb'[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?', words[1])
            ver = float(num.group()) if num else 0.0
    return False


def has_copy(tasup_dir, key, up):
    try:
        return sha_file(copy_path(tasup_dir, key, up)) == up[3]
    except OSError:
        return False


def copy_rec(store, tasup_dir, key, up, write=True):
    """Put the upload's .rec at copy_path, checked against its sha256 (write=False: only check it could be).
    -> (True, '') when it is there, else (False, why): logged by sync only when it changes a row."""
    if has_copy(tasup_dir, key, up):
        return True, ''
    dst = copy_path(tasup_dir, key, up)
    what = '%s/%d tasup-%d' % (key[0], key[1], up[0])
    try:
        with open(rec_path(store, up[3]), 'rb') as f:
            data = f.read()
        if hashlib.sha256(data).hexdigest() != up[3]:
            return False, 'copy refused %s: the stored file is not its sha256' % what
        if not game_finds_begin(data):
            return False, 'copy skipped %s: the game would not find its begin line' % what
        if not write:
            return True, ''
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + '.part'
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, dst)
        return True, ''
    except OSError as e:
        return False, 'copy failed %s: %s' % (what, e)


def read_store(store):
    """({(map, track, steamid): (id, ticks, uploaded_at, sha)} of each best shown run, every key the store has held)."""
    db = connect(store, readonly=True)
    try:
        rows = db.execute('SELECT id, steamid, map, track, ticks, uploaded_at, state, sha FROM runs ORDER BY ticks, id'
                          ).fetchall()
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
            best.setdefault(key, (r['id'], r['ticks'], r['uploaded_at'], (r['sha'] or '').lower()))
    return best, keys


def ours(r, reps):
    """reps: {id: (runid, leaf, rejected)} of this course's 'tasup' replays rows."""
    return (r['node'] == NODE and RUNID_RE.match(r['runid'] or '')
            and (r['replay_id'] == 0 or reps.get(r['replay_id'], ('',))[0] == r['runid']))


def plan(db, key, up, name, banned=False, withdraw=False, rep_ok=lambda key, up: False):
    """[(action, arg)] for one course and player; `up` is the best shown upload or None. A filed row's replay_id is
    its copy's replays row, else -1 for one to be made; 0 when rep_ok(key, up) says the copy is not in place and
    cannot be made (asked only for a row that is or will be filed: the copy is made or repaired there). An upload
    whose copy carries a current review reject is treated as not shown (off the board, as restand takes a run)."""
    reps = {r['id']: (r['runid'], r['leaf'], r['rejected']) for r in db.execute(
        'SELECT p.id, p.runid, p.leaf, ' + REJECTED_SQL + ' AS rejected FROM replays p WHERE p.map = ? AND p.track = ?'
        ' AND p.leg = 0 AND p.player = ? AND p.kind = ?', (key[0], key[1], key[2], KIND))}
    want = None
    if up is not None:
        rid, ticks, at, sha = up
        leaf = LEAF % (rid, sha[:16])
        have = next((i for i, (ru, lf, _) in reps.items() if ru == RUNID % rid and lf == leaf), 0)
        if have and reps[have][2]:
            up = have = None
    if up is not None:
        want = dict(map=key[0], track=key[1], leg=0, tier=TIER, style=STYLE, player=key[2], name=name, ticks=ticks,
                    tickrate=RATE, millis=int(round(ticks * 1000.0 / RATE)), flags=TF_TAS, node=NODE,
                    runid=RUNID % rid, submitted=at, replay_id=have, plat=0, pad=0, oldgame=0)
    rows = db.execute('SELECT rowid, * FROM runs WHERE map = ? AND track = ? AND leg = 0 AND style = ? AND player = ?',
                      (key[0], key[1], STYLE, key[2])).fetchall()
    mine = [r for r in rows if ours(r, reps)]
    theirs = [r for r in rows if not ours(r, reps)]
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
        if cur is not None or (not theirs and best is None):
            if not rep_ok(key, up):
                want['replay_id'] = 0
            elif not want['replay_id']:
                want['replay_id'] = -1
            if cur is None:
                return out + [('added', want)]
            if any(cur[c] != want[c] for c in COLS):
                out.append(('updated', want))
            return out
        out.append(('kept_lobby', None))
    if freed and best is not None and not any(r['tier'] == TIER for r in theirs):
        out.append(('refilled', {c: (best['id'] if c == 'replay_id' else '' if c == 'runid' else best[c])
                                 for c in COLS}))   # surfd.restand's row for it
    return out


def sync(store, surfd_db, dry_run=False, full=False, withdraw=False, log=print, tasup_dir=None, warn_all=False):
    """One pass. -> {'added', 'updated', 'removed', 'refilled', 'kept_lobby', 'skipped', 'reps', 'unreps', 'norep'}
    counts (norep: filed rows whose copy could not be made). A copy problem is logged on the pass that files its row
    without the replay, or on every pass with warn_all (a run without --quiet)."""
    if tasup_dir is None:
        tasup_dir = default_tasup_dir(surfd_db)
    best, keys = read_store(store)
    if withdraw:
        best, full = {}, True
    n = dict(added=0, updated=0, removed=0, refilled=0, kept_lobby=0, skipped=0, reps=0, unreps=0, norep=0)
    copied, whys = {}, {}                   # upload id -> its copy is in place (made before the lock); why not
    gone = []                               # copies to unlink once the deletes are committed
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

        def course(key, rep_ok):
            sid = key[2]
            up = best.get(key) if sid in accts else None    # tasupd's board shows no unknown account
            return plan(db, key, up, accts.get(sid, ('',))[0] or 'Steam ' + sid[-4:],   # tasupd's who()
                        banned=sid in accts and accts[sid][1], withdraw=withdraw, rep_ok=rep_ok)

        read_accounts({k[2] for k in keys})

        def copy_once(key, up):
            if up[0] not in copied:
                copied[up[0]], whys[up[0]] = copy_rec(store, tasup_dir, key, up, write=not dry_run)
                if whys[up[0]]:
                    n['norep'] += 1
                    if warn_all:
                        log(whys[up[0]])
            return copied[up[0]]

        def copy_known(key, up):            # under the lock: no copying, only what pass 1 made or a check
            return copied[up[0]] if up[0] in copied else has_copy(tasup_dir, key, up)

        todo = []
        for key in sorted(keys):
            acts = course(key, copy_once)
            for a, _ in acts:
                if a in ('kept_lobby', 'skipped'):
                    n[a] += 1
            if any(a not in ('kept_lobby', 'skipped') for a, _ in acts):
                todo.append(key)
        if not todo and db.execute(UNNAMED + ' LIMIT 1').fetchone() is None:
            if not dry_run:
                sweep_copies(db, tasup_dir, log, 0 if withdraw else ORPHAN_AGE)
            return n
        db.execute('BEGIN IMMEDIATE')
        accts.clear()                       # a ban or rename since the first read
        read_accounts({k[2] for k in todo})
        for key in todo:                    # planned again under the lock: surfd may have written since
            for a, arg in course(key, copy_known):
                if a == 'removed':
                    db.execute('DELETE FROM runs WHERE rowid = ?', (arg,))
                elif a in ('added', 'updated', 'refilled'):
                    if arg['replay_id'] == -1:
                        arg = dict(arg, replay_id=add_replay(db, store, tasup_dir, key, best[key], arg))
                        n['reps'] += 1
                    db.execute(UPSERT, [arg[c] for c in COLS])
                else:
                    continue
                n[a] += 1
                what = '' if not isinstance(arg, dict) else ' ' + (arg['runid'] or 'rep %d' % arg['replay_id'])
                log('%s %s/%d %s%s' % ((a,) + key + (what,)))
                if a in ('added', 'updated') and arg['replay_id'] == 0 and whys.get(best[key][0]) and not warn_all:
                    log(whys[best[key][0]])     # once: the pass that files the row without its replay
        for r in db.execute(UNNAMED).fetchall():           # a copy no board row names any more
            db.execute('DELETE FROM replays WHERE id = ?', (r['id'],))
            gone.append(os.path.join(tasup_dir, r['map_dir'], leg_dir(r['track']), r['leaf']))
            n['unreps'] += 1
            log('unrep %s/%d %s' % (r['map_dir'], r['track'], r['leaf']))
        db.execute('ROLLBACK' if dry_run else 'COMMIT')
        for path in [] if dry_run else gone:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            except OSError as e:                # sweep_copies retries it
                log('unlink failed %s: %s' % (path, e))
        if not dry_run:
            sweep_copies(db, tasup_dir, log, 0 if withdraw else ORPHAN_AGE)
    except BaseException:
        if db.in_transaction:
            db.execute('ROLLBACK')
        raise
    finally:
        db.close()
    return n


def sweep_copies(db, tasup_dir, log, min_age):
    """Unlink copies (and .part files) of ours under tasup_dir that no 'tasup' replays row names, older than min_age:
    a copy whose slot a lobby run took between the passes, a failed unlink, a crash before commit."""
    named = {(r['map_dir'], leg_dir(r['track']), r['leaf'])
             for r in db.execute("SELECT map_dir, track, leaf FROM replays WHERE kind = 'tasup'")}
    now = time.time()

    def entries(d, want):                   # names of real (not symlinked) dirs or files in d; errors logged
        try:
            names = os.listdir(d)
        except FileNotFoundError:
            return []
        except OSError as e:
            log('sweep failed %s: %s' % (d, e))
            return []
        out = []
        for name in names:
            try:
                if want(os.lstat(os.path.join(d, name)).st_mode):
                    out.append(name)
            except OSError:
                pass
        return out
    for mp in entries(tasup_dir, stat.S_ISDIR):
        for lg in entries(os.path.join(tasup_dir, mp), stat.S_ISDIR):
            d = os.path.join(tasup_dir, mp, lg)
            for leaf in entries(d, stat.S_ISREG):
                base = leaf[:-5] if leaf.endswith('.part') else leaf
                if not LEAF_RE.match(base) or (mp, lg, leaf) in named:
                    continue
                path = os.path.join(d, leaf)
                try:
                    if now - os.lstat(path).st_mtime >= min_age:
                        os.unlink(path)
                        log('swept %s/%s/%s' % (mp, lg, leaf))
                except OSError as e:
                    log('sweep failed %s: %s' % (path, e))


def add_replay(db, store, tasup_dir, key, up, row):
    """The 'tasup' replays row for the upload's copy (made before the lock) -> its id."""
    leaf = LEAF % (up[0], up[3][:16])
    try:
        size = os.path.getsize(copy_path(tasup_dir, key, up))
    except OSError:                         # a dry run makes no copy
        size = -1
    vals = dict(row, map_dir=key[0], leaf=leaf, bytes=size, bound=0, sha=up[3], sha_at=row['submitted'], kind=KIND)
    db.execute(REP_UPSERT, [vals[c] for c in RCOLS])
    return db.execute('SELECT id FROM replays WHERE map = ? AND track = ? AND leg = 0 AND leaf = ?',
                      (key[0], key[1], leaf)).fetchone()[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--store', required=True, help="tasupd's tasup.sqlite3 (read only)")
    ap.add_argument('--db', required=True, help="surfd's surfd.db")
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--full', action='store_true', help='also find upload rows of courses the store no longer names')
    ap.add_argument('--withdraw', action='store_true', help='take every upload row off the board')
    ap.add_argument('--tasup-dir', help="surfd's TASUP_DIR (default: tasup/ beside --db)")
    ap.add_argument('--quiet', action='store_true', help='print only the totals line, and only when something changed')
    a = ap.parse_args(argv)
    n = sync(a.store, a.db, a.dry_run, a.full, a.withdraw,
             log=(lambda s: print(s) if s.startswith(WARN) else None) if a.quiet else print, tasup_dir=a.tasup_dir,
             warn_all=not a.quiet)
    if not a.quiet or any(n[k] for k in ('added', 'updated', 'removed', 'refilled', 'reps', 'unreps')):
        print('%s tasindex%s: %s' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), ' (dry run)' if a.dry_run else '',
                                    ' '.join('%s=%d' % kv for kv in n.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
