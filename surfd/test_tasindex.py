#!/usr/bin/env python3
"""P1806: tasindex files tasupd's shown uploads as the TAS board's rows, read back through surfd's own /api/board.
P1870: those rows carry a rep surfd serves (kind 'tasup'), read back through /api/replay."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest

HOME = Path(tempfile.mkdtemp(prefix='surfd-tasindex-'))
(HOME / 'surfd.env').write_text('SURFD_KEY=testkey\n')
os.environ.update(SURFD_HOME=str(HOME), SURFD_DB=str(HOME / 'surfd.db'), SURFD_ENV=str(HOME / 'surfd.env'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules['gunicorn'] = types.ModuleType('gunicorn')
import surfd as S          # noqa: E402
import accounts as A       # noqa: E402
import tasupd as U         # noqa: E402
del sys.modules['gunicorn']
import tasindex as T       # noqa: E402

LEX, ROU, BAN, NOBODY = '76561198064721002', '76561198011849191', '76561198000000001', '76561198000000002'


class TasIndex(unittest.TestCase):
    def setUp(self):
        for p in HOME.glob('*.sqlite3*'):
            p.unlink()
        for d in (HOME / 'recs', Path(S.TASUP_DIR)):
            shutil.rmtree(d, ignore_errors=True)
        for p in HOME.glob('surfd.db*'):
            p.unlink()
        self.store, self.db = HOME / 'tasup.sqlite3', HOME / 'surfd.db'
        U.initialize(self.store)
        S.migrate()
        c = S.connect()
        c.executemany('INSERT INTO accounts(steamid, name, created_at, banned_at) VALUES (?, ?, 1, ?)',
                      [(LEX, 'Proto', 0), (ROU, 'Rounin', 0), (BAN, 'Banned', 5)])
        c.commit()
        c.close()
        self.n = 0
        S._rate.clear()
        self.client = S.app.test_client()

    def upload(self, sid, mapname, track, ticks, state='shown', at=1795528494, body=None, stored=None):
        """body: the .rec tasupd keeps (its sha256 names it); stored: other bytes at that path. None: no file."""
        self.n += 1
        sha = hashlib.sha256(body).hexdigest() if body is not None else '%064x' % self.n
        if body is not None:
            path = Path(U.rec_path(self.store, sha))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body if stored is None else stored)
        with sqlite3.connect(self.store) as s:
            cur = s.execute('INSERT INTO runs(sha, samples_sha, steamid, map, track, ticks, verdict, state, reasons, stats,'
                            " tool, size, uploaded_at, sig) VALUES (?, '', ?, ?, ?, ?, 'PASS', ?, '[]', '{}', 't', 1, ?, x'00')",
                            (sha, sid, mapname, track, ticks, state, at))
            return cur.lastrowid

    def rec(self, mapname, ticks, extra=''):
        return ('FTESURF-REC 5\nmap %s\ntrack 0\ntickrate 0.015\nforeign test\nmoves recorded\nbegin\n%d%s\n'
                % (mapname, ticks, extra)).encode()

    def fetch(self, rep):
        S._rate.clear()
        r = self.client.get('/api/replay/%d' % rep)
        out = r.status_code, r.get_data()
        if r.status_code == 200:
            self.assertEqual(r.headers.get('X-Content-Type-Options'), 'nosniff')
        r.close()
        return out

    def copies(self):
        return sorted(str(p.relative_to(S.TASUP_DIR)) for p in Path(S.TASUP_DIR).rglob('*') if p.is_file())

    def tasreps(self):
        with sqlite3.connect(self.db) as c:
            return c.execute("SELECT id, map, track, player, runid, leaf, bytes, sha FROM replays WHERE kind = 'tasup'"
                             ' ORDER BY id').fetchall()

    def set_state(self, rid, state):
        with sqlite3.connect(self.store) as s:
            s.execute('UPDATE runs SET state = ? WHERE id = ?', (state, rid))

    def lobby(self, sid, mapname, track, ticks, at=1795400000, name='LobbyName', node='p27620', runid=''):
        with sqlite3.connect(self.db) as c:
            c.execute(S._UPSERT_RUN, (mapname, track, 0, 'community', 'tas', sid, name, ticks, 66.6667,
                                      int(round(ticks * 1000.0 / 66.6667)), 4718985, node, runid, at, 0, 0, 0, 0))

    def replay(self, sid, mapname, track, ticks, at=1795600000, rejected=False):
        """A lobby TAS recording surfd filed without a board row (slower than the row standing)."""
        with sqlite3.connect(self.db) as c:
            rid = c.execute("INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player, name, ticks, tickrate,"
                            " millis, flags, node, submitted, kind) VALUES (?, ?, ?, 0, ?, 'community', 'tas', ?, 'RecName',"
                            " ?, 66.6667, ?, 4718985, 'p27620', ?, 'run')",
                            (mapname, mapname, track, '%07d_%s_%d.rec' % (ticks, sid[-4:], at), sid, ticks,
                             int(round(ticks * 1000.0 / 66.6667)), at)).lastrowid
            if rejected:
                c.execute("INSERT INTO reviews (replay_id, decision, at) VALUES (?, 'reject', ?)", (rid, at + 1))
            return rid

    def sync(self, **kw):
        kw.setdefault('tasup_dir', S.TASUP_DIR)
        return T.sync(self.store, self.db, log=lambda s: None, **kw)

    def board(self, mapname, track=0):
        S._rate.clear()
        r = self.client.get('/api/board', query_string=dict(map=mapname, track=track, leg=0, tier='community',
                                                            style='tas', limit=50))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return [(x['player'], x['name'], x['ms'], x['rep']) for x in json.loads(r.get_data(as_text=True))['rows']]

    def rows(self):
        with sqlite3.connect(self.db) as c:
            return sorted(c.execute("SELECT map, track, tier, player, node, runid, millis, replay_id FROM runs"
                                    " WHERE style = 'tas'"))

    def test_constants_match_their_owners(self):
        self.assertEqual((T.TF_TAS, T.TIER, T.STYLE, T.MAX_TRACK), (S.TF_TAS, S.TIER_COMMUNITY, S.STYLE_TAS, U.MAX_TRACK))
        self.assertEqual(T.MAPNAME.pattern, S._MAPNAME_OK.pattern)
        self.assertEqual(T.REJECTED_SQL, S._REJECTED_SQL)
        self.assertEqual(round(1 / U.TICK, 4), T.RATE)
        with sqlite3.connect(self.db) as c:
            self.assertEqual(set(T.COLS) | {'momdemo'}, {r[1] for r in c.execute('PRAGMA table_info(runs)')})
        self.assertEqual(list(T.COLS), [w.strip() for w in S._UPSERT_RUN.split('(')[1].split(')')[0].split(',')])
        with sqlite3.connect(self.db) as c:
            self.assertLessEqual(set(T.RCOLS), {r[1] for r in c.execute('PRAGMA table_info(replays)')})
        self.assertEqual(T.rec_path(self.store, 'ab' * 32), str(U.rec_path(self.store, 'ab' * 32)))
        for track in (0, 1, 7):
            self.assertEqual(T.leg_dir(track), S.leg_dir(track, 0))
        self.assertEqual(T.LEAF_RE.pattern, S._TASLEAF_OK.pattern)
        leaf = T.LEAF % (2, 'f' * 16)
        self.assertTrue(S._TASLEAF_OK.match(leaf))
        self.assertFalse(S._LEAF_OK.match(leaf))             # never a lobby leaf: submit_run's leaf lookup
        self.assertFalse(S._TASLEAF_OK.match('0003211_1234abcd_run.rec'))
        self.assertEqual(T.default_tasup_dir(os.path.join(S.DATA_DIR, 'surfd.db')), S.TASUP_DIR)

    def test_shown_upload_reaches_the_board(self):
        self.upload(ROU, 'surf_sandtrap2', 0, 3211)
        self.upload(LEX, 'surf_sandtrap2', 0, 3000, state='held')
        self.upload(LEX, 'surf_sandtrap2', 0, 2900, state='rejected')
        self.upload(NOBODY, 'surf_sandtrap2', 0, 2800)     # no account: tasupd's board does not show it either
        self.upload(BAN, 'surf_sandtrap2', 0, 2700)
        self.upload(ROU, 'surf_a..b', 0, 100)                # a name surfd's clean_map refuses
        self.assertEqual(self.board('surf_sandtrap2'), [])
        n = self.sync()
        self.assertEqual((n['added'], n['removed']), (1, 0))
        self.assertEqual(self.board('surf_sandtrap2'), [(ROU, 'Rounin', 48165, 0)])
        self.assertEqual(self.sync(), dict(added=0, updated=0, removed=0, refilled=0, kept_lobby=0, skipped=0, reps=0,
                                           unreps=0, norep=1))

    def test_dry_run_writes_nothing(self):
        self.upload(ROU, 'surf_sandtrap2', 0, 3211)
        self.assertEqual(self.sync(dry_run=True)['added'], 1)
        self.assertEqual(self.board('surf_sandtrap2'), [])
        self.assertEqual(self.sync()['added'], 1)

    def test_best_upload_and_removal(self):
        a = self.upload(ROU, 'surf_x', 2, 900)
        b = self.upload(ROU, 'surf_x', 2, 800)
        self.sync()
        self.assertEqual(self.rows(), [('surf_x', 2, 'community', ROU, 'tasup', 'tasup-%d' % b, 12000, 0)])
        self.set_state(b, 'removed')
        n = self.sync()
        self.assertEqual((n['removed'], n['added']), (1, 1))
        self.assertEqual(self.board('surf_x', 2), [(ROU, 'Rounin', 13500, 0)])
        self.set_state(a, 'rejected')
        self.sync()
        self.assertEqual(self.rows(), [])

    def test_a_lobby_row_is_never_touched(self):
        self.lobby(LEX, 'surf_y', 0, 500)                    # faster
        self.lobby(ROU, 'surf_y', 0, 900)                    # slower: still the player's own, kept
        self.upload(LEX, 'surf_y', 0, 600)
        self.upload(ROU, 'surf_y', 0, 600)
        with sqlite3.connect(self.db) as c:
            before = c.execute("SELECT * FROM runs WHERE style = 'tas' ORDER BY player").fetchall()
        n = self.sync()
        self.assertEqual((n['added'], n['kept_lobby']), (0, 2))
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute("SELECT * FROM runs WHERE style = 'tas' ORDER BY player").fetchall(), before)

    def test_a_set_aside_lobby_row_blocks_filing(self):
        self.lobby(LEX, 'surf_y', 0, 700)
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE runs SET tier = 'community^r7' WHERE player = ?", (LEX,))    # surfd set it aside
        self.upload(LEX, 'surf_y', 0, 600)
        self.assertEqual(self.sync()['kept_lobby'], 1)
        self.assertEqual(self.board('surf_y'), [])

    def test_a_lobby_node_named_tasup_is_not_ours(self):
        self.lobby(LEX, 'surf_y', 0, 700, node='tasup')
        rid = self.upload(LEX, 'surf_y', 0, 600)
        self.sync()
        self.set_state(rid, 'removed')
        self.sync(full=True)
        self.assertEqual(self.board('surf_y'), [(LEX, 'LobbyName', 10500, 0)])

    def test_lobby_goes_faster_later(self):
        rid = self.upload(LEX, 'surf_y', 0, 600)
        self.sync()
        self.lobby(LEX, 'surf_y', 0, 550, at=1795600000)     # submit_run's upsert over the upload's row
        self.assertEqual(self.sync()['kept_lobby'], 1)
        self.set_state(rid, 'removed')
        self.assertEqual(self.sync()['removed'], 0)
        self.assertEqual(self.board('surf_y'), [(LEX, 'LobbyName', 8250, 0)])

    def test_removal_refills_from_the_best_lobby_replay(self):
        rid = self.upload(LEX, 'surf_y', 0, 600)
        self.sync()
        self.replay(LEX, 'surf_y', 0, 640, rejected=True)
        keep = self.replay(LEX, 'surf_y', 0, 650)
        self.replay(LEX, 'surf_y', 0, 700)
        self.set_state(rid, 'removed')
        n = self.sync()
        self.assertEqual((n['removed'], n['refilled']), (1, 1))
        self.assertEqual(self.board('surf_y'), [(LEX, 'RecName', 9750, keep)])
        self.assertEqual(self.rows()[0][5], '')              # restand's row: no runid

    def test_a_better_lobby_recording_wins_over_the_next_upload(self):
        a = self.upload(LEX, 'surf_y', 0, 600)
        self.sync()
        keep = self.replay(LEX, 'surf_y', 0, 650)             # filed with no row: the upload's 600 stood
        self.upload(LEX, 'surf_y', 0, 700)
        self.set_state(a, 'removed')
        n = self.sync()
        self.assertEqual((n['removed'], n['refilled'], n['added'], n['kept_lobby']), (1, 1, 0, 1))
        self.assertEqual(self.board('surf_y'), [(LEX, 'RecName', 9750, keep)])
        self.assertEqual(self.sync()['kept_lobby'], 1)        # and it stays

    def test_an_unrejected_recording_blocks_filing(self):
        self.replay(LEX, 'surf_y', 0, 650)
        self.replay(ROU, 'surf_y', 0, 650, rejected=True)
        self.upload(LEX, 'surf_y', 0, 600)
        self.upload(ROU, 'surf_y', 0, 600)
        n = self.sync()
        self.assertEqual((n['added'], n['kept_lobby']), (1, 1))
        self.assertEqual(self.board('surf_y'), [(ROU, 'Rounin', 9000, 0)])

    def test_a_ban_between_the_plan_and_the_lock(self):
        self.upload(ROU, 'surf_z', 0, 1000)
        real, calls = T.plan, []

        def plan(db, key, *a, **kw):
            if not calls:
                calls.append(key)
                with sqlite3.connect(self.db) as c:
                    c.execute('UPDATE accounts SET banned_at = 9 WHERE steamid = ?', (ROU,))
            return real(db, key, *a, **kw)
        T.plan = plan
        try:
            self.sync()
        finally:
            T.plan = real
        self.assertEqual(calls, [('surf_z', 0, ROU)])
        self.assertEqual(self.rows(), [])

    def test_withdraw_takes_a_banned_players_upload_row(self):
        self.upload(ROU, 'surf_z', 0, 1000)
        self.sync()
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE accounts SET banned_at = 9 WHERE steamid = ?', (ROU,))
            A.ban_rows(c, ROU, True, S.TIERS_IMPORTED)
        self.assertEqual(self.sync(withdraw=True)['removed'], 1)
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE accounts SET banned_at = 0 WHERE steamid = ?', (ROU,))
            A.ban_rows(c, ROU, False, S.TIERS_IMPORTED)
        self.assertEqual(self.rows(), [])

    def test_set_aside_upload_row_is_not_filed_again(self):
        rid = self.upload(ROU, 'surf_z', 0, 1000)
        self.sync()
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE runs SET tier = 'community^tasup-%d' WHERE runid = ?" % rid, ('tasup-%d' % rid,))
        self.assertEqual(self.sync()['skipped'], 1)
        self.assertEqual(self.board('surf_z'), [])
        self.set_state(rid, 'removed')
        self.assertEqual(self.sync()['removed'], 1)
        self.assertEqual(self.rows(), [])

    def test_banned_player_rows_are_left_to_surfd(self):
        rid = self.upload(ROU, 'surf_z', 0, 1000)
        self.sync()
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE accounts SET banned_at = 9 WHERE steamid = ?', (ROU,))
            A.ban_rows(c, ROU, True, S.TIERS_IMPORTED)
        self.set_state(rid, 'removed')
        self.sync()
        self.assertEqual(self.rows(), [('surf_z', 0, 'banned:community', ROU, 'tasup', 'tasup-%d' % rid, 15000, 0)])
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE accounts SET banned_at = 0 WHERE steamid = ?', (ROU,))
            A.ban_rows(c, ROU, False, S.TIERS_IMPORTED)
        self.assertEqual(self.sync()['removed'], 1)
        self.assertEqual(self.rows(), [])

    def test_rename_updates_the_row(self):
        self.upload(ROU, 'surf_z', 0, 1000)
        self.sync()
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE accounts SET name = 'Rounin2' WHERE steamid = ?", (ROU,))
        self.assertEqual(self.sync()['updated'], 1)
        self.assertEqual(self.board('surf_z'), [(ROU, 'Rounin2', 15000, 0)])

    def test_full_and_withdraw(self):
        self.upload(ROU, 'surf_z', 0, 1000)
        rid = self.upload(LEX, 'surf_y', 0, 600)
        self.sync()
        with sqlite3.connect(self.db) as c:                  # a stray: its course is in no store row
            c.execute("UPDATE runs SET map = 'surf_gone' WHERE runid = ?", ('tasup-%d' % rid,))
        n = self.sync()                                      # the store's own key is filed again; the stray stays
        self.assertEqual((n['removed'], n['added']), (0, 1))
        self.assertEqual(self.sync(full=True)['removed'], 1)
        n = self.sync(withdraw=True)
        self.assertEqual((n['removed'], n['added']), (2, 0))
        self.assertEqual(self.rows(), [])

    def test_upload_row_carries_a_replay_surfd_serves(self):
        body = self.rec('surf_sandtrap2', 3211)
        rid = self.upload(ROU, 'surf_sandtrap2', 0, 3211, body=body)
        n = self.sync()
        self.assertEqual((n['added'], n['reps']), (1, 1))
        [(p, name, ms, rep)] = self.board('surf_sandtrap2')
        self.assertEqual((p, name, ms), (ROU, 'Rounin', 48165))
        self.assertGreater(rep, 0)
        self.assertEqual(self.fetch(rep), (200, body))
        sha = hashlib.sha256(body).hexdigest()
        self.assertEqual(self.tasreps(), [(rep, 'surf_sandtrap2', 0, ROU, 'tasup-%d' % rid,
                                           'tasup-%d-%s.rec' % (rid, sha[:16]), len(body), sha)])
        self.assertEqual(self.sync()['reps'] + self.sync()['updated'], 0)        # settled: ours with a rep

    def test_a_bonus_copy_and_the_cli_default_dir(self):
        body = self.rec('surf_x', 900)
        self.upload(ROU, 'surf_x', 3, 900, body=body)
        self.assertEqual(T.main(['--store', str(self.store), '--db', str(self.db), '--tasup-dir', S.TASUP_DIR,
                                 '--quiet']), 0)
        self.assertEqual(self.copies(), ['surf_x/bonus_3/' + self.tasreps()[0][5]])
        self.assertEqual(self.fetch(self.board('surf_x', 3)[0][3]), (200, body))

    def test_a_row_filed_before_its_copy_gains_a_rep(self):
        body = self.rec('surf_z', 1000)
        rid = self.upload(ROU, 'surf_z', 0, 1000, body=body)
        path = Path(U.rec_path(self.store, hashlib.sha256(body).hexdigest()))
        path.rename(str(path) + '.away')                    # P1806's rows: filed with rep 0
        self.assertEqual(self.sync()['reps'], 0)
        self.assertEqual(self.board('surf_z'), [(ROU, 'Rounin', 15000, 0)])
        self.assertEqual(self.sync()['updated'], 0)         # a copy that cannot be made changes nothing
        Path(str(path) + '.away').rename(path)
        n = self.sync()
        self.assertEqual((n['updated'], n['reps'], n['added']), (1, 1, 0))
        self.assertEqual(self.fetch(self.board('surf_z')[0][3]), (200, body))
        self.assertEqual(self.rows()[0][5], 'tasup-%d' % rid)

    def test_a_stored_file_that_is_not_its_sha_is_not_served(self):
        self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000), stored=b'something else')
        logged = []
        T.sync(self.store, self.db, log=logged.append, tasup_dir=S.TASUP_DIR)
        self.assertEqual(self.board('surf_z'), [(ROU, 'Rounin', 15000, 0)])
        self.assertEqual((self.copies(), self.tasreps()), ([], []))
        self.assertTrue(any('not its sha256' in line for line in logged), logged)

    def test_removed_and_replaced_uploads_take_their_copies(self):
        a = self.upload(ROU, 'surf_x', 0, 900, body=self.rec('surf_x', 900))
        self.sync()
        old = self.board('surf_x')[0][3]
        b_body = self.rec('surf_x', 800)
        b = self.upload(ROU, 'surf_x', 0, 800, body=b_body)
        n = self.sync()
        self.assertEqual((n['removed'], n['added'], n['reps'], n['unreps']), (1, 1, 1, 1))
        new = self.board('surf_x')[0][3]
        self.assertNotEqual(new, old)
        self.assertEqual((self.fetch(old)[0], self.fetch(new)), (404, (200, b_body)))
        self.assertEqual(self.copies(), ['surf_x/main/tasup-%d-%s.rec' % (b, hashlib.sha256(b_body).hexdigest()[:16])])
        self.set_state(b, 'removed')
        self.set_state(a, 'removed')
        n = self.sync()
        self.assertEqual((n['removed'], n['unreps']), (1, 1))
        self.assertEqual((self.rows(), self.tasreps(), self.copies(), self.fetch(new)[0]), ([], [], [], 404))

    def test_a_lobby_upsert_over_the_row_frees_its_copy(self):
        self.upload(LEX, 'surf_y', 0, 600, body=self.rec('surf_y', 600))
        self.sync()
        self.lobby(LEX, 'surf_y', 0, 550, at=1795600000)    # submit_run's upsert takes the row
        n = self.sync()
        self.assertEqual((n['kept_lobby'], n['unreps']), (1, 1))
        self.assertEqual((self.tasreps(), self.copies()), ([], []))

    def test_no_copy_for_an_upload_kept_off_the_board(self):
        self.lobby(LEX, 'surf_y', 0, 500)
        self.replay(ROU, 'surf_y', 0, 650)
        self.upload(LEX, 'surf_y', 0, 600, body=self.rec('surf_y', 600))
        self.upload(ROU, 'surf_y', 0, 600, body=self.rec('surf_y', 601))
        self.assertEqual(self.sync()['kept_lobby'], 2)
        self.assertEqual((self.copies(), self.tasreps()), ([], []))

    def test_banned_or_rejected_copies_are_not_served(self):
        self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000))
        self.sync()
        rep = self.board('surf_z')[0][3]
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE accounts SET banned_at = 9 WHERE steamid = ?', (ROU,))
            A.ban_rows(c, ROU, True, S.TIERS_IMPORTED)
        self.sync()
        self.assertEqual((self.fetch(rep)[0], len(self.tasreps())), (404, 1))   # parked row still names it: kept
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE accounts SET banned_at = 0 WHERE steamid = ?', (ROU,))
            A.ban_rows(c, ROU, False, S.TIERS_IMPORTED)
        self.assertEqual(self.sync()['reps'], 0)
        self.assertEqual(self.fetch(rep)[0], 200)
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO reviews (replay_id, decision, at) VALUES (?, 'reject', ?)", (rep, 1795528495))
        self.assertEqual(self.fetch(rep)[0], 404)

    def test_a_lobby_row_pointing_at_a_lobby_replay_is_not_ours(self):
        keep = self.replay(LEX, 'surf_y', 0, 700)
        rid = self.upload(LEX, 'surf_y', 0, 600, body=self.rec('surf_y', 600))
        with sqlite3.connect(self.db) as c:
            c.execute(S._UPSERT_RUN, ('surf_y', 0, 0, 'community', 'tas', LEX, 'LobbyName', 700, 66.6667, 10500,
                                      4718985, 'tasup', 'tasup-%d' % rid, 1795400000, keep, 0, 0, 0))
        self.set_state(rid, 'removed')
        self.sync(full=True)
        self.assertEqual(self.board('surf_y'), [(LEX, 'LobbyName', 10500, keep)])

    def test_dry_run_and_withdraw_with_copies(self):
        self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000))
        n = self.sync(dry_run=True)
        self.assertEqual((n['added'], n['reps']), (1, 1))
        self.assertEqual((self.rows(), self.tasreps(), self.copies()), ([], [], []))
        self.sync()
        self.assertEqual(len(self.copies()), 1)
        n = self.sync(withdraw=True)
        self.assertEqual((n['removed'], n['unreps']), (1, 1))
        self.assertEqual((self.rows(), self.tasreps(), self.copies()), ([], [], []))

    def test_a_rejected_copy_takes_the_row_off_and_stays_rejected(self):
        rid = self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000))
        self.sync()
        rep = self.board('surf_z')[0][3]
        keep = self.replay(ROU, 'surf_z', 0, 1100, at=1795400000)
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO reviews (replay_id, decision, at) VALUES (?, 'reject', ?)", (rep, 1795528495))
        n = self.sync()
        self.assertEqual((n['removed'], n['refilled'], n['unreps']), (1, 1, 0))
        self.assertEqual(self.board('surf_z'), [(ROU, 'RecName', 16500, keep)])
        self.assertEqual([r[0] for r in self.tasreps()], [rep])                 # kept: the reject keys on its id
        self.set_state(rid, 'held')
        self.sync()
        self.set_state(rid, 'shown')
        self.assertEqual(self.sync()['added'], 0)                               # shown again: still rejected
        self.assertEqual(self.board('surf_z'), [(ROU, 'RecName', 16500, keep)])
        self.assertEqual(self.sync(withdraw=True)['unreps'], 0)                 # a rollback keeps the reject
        self.assertEqual(([r[0] for r in self.tasreps()], len(self.copies())), ([rep], 1))
        self.assertEqual(self.sync()['added'], 0)
        self.assertEqual(self.board('surf_z'), [(ROU, 'RecName', 16500, keep)])

    def test_a_lost_or_corrupt_copy_is_repaired(self):
        body = self.rec('surf_z', 1000)
        self.upload(ROU, 'surf_z', 0, 1000, body=body)
        self.sync()
        rep = self.board('surf_z')[0][3]
        copy = Path(S.TASUP_DIR) / self.copies()[0]
        copy.unlink()
        self.assertEqual(self.sync()['updated'], 0)
        self.assertEqual(self.fetch(rep), (200, body))
        copy.write_bytes(b'x' * len(body))                  # same size, other bytes
        self.sync()
        self.assertEqual(self.fetch(rep), (200, body))

    def test_a_lost_copy_without_its_source_drops_the_rep(self):
        body = self.rec('surf_z', 1000)
        self.upload(ROU, 'surf_z', 0, 1000, body=body)
        self.sync()
        (Path(S.TASUP_DIR) / self.copies()[0]).unlink()
        Path(U.rec_path(self.store, hashlib.sha256(body).hexdigest())).unlink()
        n = self.sync()
        self.assertEqual((n['updated'], n['unreps']), (1, 1))
        self.assertEqual((self.board('surf_z'), self.tasreps()), ([(ROU, 'Rounin', 15000, 0)], []))
        self.assertEqual(self.sync()['updated'] + self.sync()['reps'], 0)

    def test_orphan_copies_are_swept(self):
        self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000))
        self.sync()
        d = Path(S.TASUP_DIR) / 'surf_q' / 'main'
        d.mkdir(parents=True)
        old, young, part, other = (d / ('tasup-7-%s.rec' % ('a' * 16)), d / ('tasup-8-%s.rec' % ('b' * 16)),
                                   d / ('tasup-9-%s.rec.part' % ('c' * 16)), d / 'notes.txt')
        for f in (old, young, part, other):
            f.write_bytes(b'x')
        for f in (old, part):
            os.utime(f, (1, 1))
        self.sync()
        self.assertEqual(sorted(p.name for p in d.iterdir()), sorted([young.name, other.name]))
        self.assertEqual(len(self.copies()), 3)              # the filed copy stays
        self.sync(withdraw=True)
        self.assertEqual(self.copies(), ['surf_q/main/notes.txt'])

    def test_an_unlink_that_fails_is_retried_by_the_sweep(self):
        self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000))
        rid = self.n
        self.sync()
        real = T.os.unlink

        def refuse(path):
            raise PermissionError(13, 'refused', path)
        T.os.unlink = refuse
        try:
            self.set_state(rid, 'removed')
            logged = []
            n = T.sync(self.store, self.db, log=logged.append, tasup_dir=S.TASUP_DIR)
        finally:
            T.os.unlink = real
        self.assertEqual(n['unreps'], 1)
        self.assertTrue(any(line.startswith('unlink failed') for line in logged), logged)
        self.assertEqual(len(self.copies()), 1)
        os.utime(Path(S.TASUP_DIR) / self.copies()[0], (1, 1))
        self.sync()
        self.assertEqual(self.copies(), [])

    def test_dry_run_counts_only_copies_that_could_be_made(self):
        self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000), stored=b'other bytes')
        self.upload(LEX, 'surf_z', 0, 900, body=self.rec('surf_z', 900))
        n = self.sync(dry_run=True)
        self.assertEqual((n['added'], n['reps']), (2, 1))
        self.assertEqual(self.copies(), [])

    def test_a_header_the_game_cannot_read_gets_no_rep(self):
        long_head = b'FTESURF-REC 5\n' + b'note x\n' * 63 + b'begin\n1\n'      # begin is line 65
        ok_head = b'FTESURF-REC 5\n' + b'note x\n' * 62 + b'begin\n1\n'        # begin is line 64
        self.upload(ROU, 'surf_z', 0, 1000, body=long_head)
        self.upload(LEX, 'surf_z', 0, 900, body=ok_head)
        logged = []
        T.sync(self.store, self.db, log=logged.append, tasup_dir=S.TASUP_DIR)
        self.assertEqual(sorted((p, rep > 0) for p, _, _, rep in self.board('surf_z')), [(ROU, False), (LEX, True)])
        self.assertTrue(any(line.startswith('copy skipped') for line in logged), logged)

    def test_the_header_scan_is_the_clients(self):
        head, v = 'FTESURF-REC 5\nmap surf_z\ntrack 0\n', 'FTESURF-REC 5\n'
        cases = [(head + 'begin\n1\n', True), (head.replace('\n', '\r\n') + 'begin\r\n', True),
                 (head + '\nbegin\n', False),                       # a blank line ends the client's scan
                 (head + '\r\nbegin\n', False),                     # so does a CRLF blank line
                 (head + '  begin  \n', True), ('', False), (head + 'beginx\n', False),
                 (v + 'note\n' * 62 + 'begin\n', True), (v + 'note\n' * 63 + 'begin\n', False),
                 (v + 'note\n' * 55 + 'x' * 40000 + '\nbegin\n', False),  # one long line uses up ten reads
                 (v + 'note\n' * 51 + 'x' * 40000 + '\nbegin\n', True),
                 (v + 'x' * 4095 + '\nbegin\n', True),             # fits one read exactly
                 (v + 'x' * 4096 + '\nbegin\n', False),            # the cap byte is dropped; the next read is ""
                 ('begin', False), ('FTESURF-REC 0\nbegin\n', False), ('FTESURF-REC v5\nbegin\n', False),
                 ('FTESURF-REC\nbegin\n', False), ('begin\nFTESURF-REC 5\n', False), ('FTESURF-REC 1\nbegin', True),
                 ('FTESURF-REC 1.5x\nbegin\n', True), ('FTESURF-REC 5\nFTESURF-REC 0\nbegin\n', False),
                 (v + 'note a\x00b\nbegin\n', False),
                 ('FTESURF-REC 5e-1\nbegin\n', False), ('FTESURF-REC 9E-1\nbegin\n', False),
                 ('FTESURF-REC 1e1\nbegin\n', True),
                 (v + 'FTESURF-REC:0\nbegin\n', False), (v + '"FTESURF-REC" 0\nbegin\n', False),
                 (v + "'FTESURF-REC' 0\nbegin\n", False), (v + 'FTESURF-REC\x01x\nbegin\n', False),
                 ('FTESURF-REC 0\n"begin"\nFTESURF-REC 5\nbegin\n', False), (v + 'begin:\n', False),
                 (v + 'map surf_beginner\nbegin\n', True), (v + '{FTESURF-REC 0\nbegin\n', True),
                 (v + 'note ]\\"x\nbegin\n', False), (v + '\\"begin"\nbegin\n', False),
                 ('FTESURF-REC 1d-5\nbegin\n', False), ('FTESURF-REC 5D\nbegin\n', False)]
        for text, want in cases:
            self.assertEqual(T.game_finds_begin(text.encode()), want, repr(text[:60]))
        self.upload(ROU, 'surf_z', 0, 1000, body=(head + '\nbegin\n1\n').encode())
        self.sync()
        self.assertEqual(self.board('surf_z'), [(ROU, 'Rounin', 15000, 0)])

    def test_an_old_named_copy_is_never_swept_and_dry_runs_never_sweep(self):
        body = self.rec('surf_z', 1000)
        self.upload(ROU, 'surf_z', 0, 1000, body=body)
        self.sync()
        rep = self.board('surf_z')[0][3]
        os.utime(Path(S.TASUP_DIR) / self.copies()[0], (1, 1))
        self.sync()
        self.assertEqual(self.fetch(rep), (200, body))
        orphan = Path(S.TASUP_DIR) / 'surf_q' / 'main' / ('tasup-7-%s.rec' % ('a' * 16))
        orphan.parent.mkdir(parents=True)
        orphan.write_bytes(b'x')
        os.utime(orphan, (1, 1))
        self.sync(dry_run=True)
        self.assertTrue(orphan.exists())
        self.sync(withdraw=True, dry_run=True)
        self.assertTrue(orphan.exists())

    def test_the_sweep_survives_unreadable_dirs_and_leaves_symlinks(self):
        self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000))
        self.sync()
        outside = HOME / 'outside' / 'main'
        outside.mkdir(parents=True, exist_ok=True)
        target = outside / ('tasup-7-%s.rec' % ('a' * 16))
        target.write_bytes(b'x')
        os.utime(target, (1, 1))
        os.symlink(HOME / 'outside', Path(S.TASUP_DIR) / 'surf_link')
        locked = Path(S.TASUP_DIR) / 'surf_locked'
        locked.mkdir()
        locked.chmod(0)
        logged = []
        try:
            T.sync(self.store, self.db, log=logged.append, tasup_dir=S.TASUP_DIR, withdraw=True)
        finally:
            locked.chmod(0o755)
            (Path(S.TASUP_DIR) / 'surf_link').unlink()
        self.assertTrue(target.exists())
        if os.geteuid() != 0:
            self.assertTrue(any(line.startswith('sweep failed') for line in logged), logged)

    def test_a_standing_rep0_row_whose_copy_fails_shows_without_quiet(self):
        import contextlib
        import io
        self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000), stored=b'tampered')
        self.sync()                                         # filed with rep 0 (as P1806 filed every row)
        for quiet, want in ((True, False), (False, True), (False, True)):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                T.main(['--store', str(self.store), '--db', str(self.db), '--tasup-dir', S.TASUP_DIR]
                       + (['--quiet'] if quiet else []))
            self.assertEqual('copy refused surf_z/0' in out.getvalue(), want, out.getvalue())
            self.assertEqual('norep=1' in out.getvalue(), not quiet, out.getvalue())

    def test_a_copy_that_cannot_be_made_is_logged_once(self):
        self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000), stored=b'tampered')
        first, second = [], []
        T.sync(self.store, self.db, log=first.append, tasup_dir=S.TASUP_DIR)
        T.sync(self.store, self.db, log=second.append, tasup_dir=S.TASUP_DIR)
        self.assertEqual(([x for x in first if x.startswith('copy')], second),
                         (['copy refused surf_z/0 tasup-1: the stored file is not its sha256'], []))

    def test_cli_quiet(self):
        self.upload(ROU, 'surf_z', 0, 1000)
        self.assertEqual(T.main(['--store', str(self.store), '--db', str(self.db), '--quiet']), 0)
        self.assertEqual(len(self.rows()), 1)

    def test_cli_quiet_still_prints_copy_problems(self):
        import contextlib
        import io
        self.upload(ROU, 'surf_z', 0, 1000, body=self.rec('surf_z', 1000), stored=b'tampered')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            T.main(['--store', str(self.store), '--db', str(self.db), '--tasup-dir', S.TASUP_DIR, '--quiet'])
        self.assertIn('copy refused surf_z/0', out.getvalue())


if __name__ == '__main__':
    unittest.main()
