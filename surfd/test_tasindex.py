#!/usr/bin/env python3
"""P1806: tasindex files tasupd's shown uploads as the TAS board's rows, read back through surfd's own /api/board."""
import json
import os
from pathlib import Path
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
        for p in HOME.glob('surfd.db*'):
            p.unlink()
        self.store, self.state, self.db = HOME / 'tasup.sqlite3', HOME / 'tasindex.sqlite3', HOME / 'surfd.db'
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

    def upload(self, sid, mapname, track, ticks, state='shown', at=1795528494):
        self.n += 1
        with sqlite3.connect(self.store) as s:
            cur = s.execute('INSERT INTO runs(sha, samples_sha, steamid, map, track, ticks, verdict, state, reasons, stats,'
                            " tool, size, uploaded_at, sig) VALUES (?, '', ?, ?, ?, ?, 'PASS', ?, '[]', '{}', 't', 1, ?, x'00')",
                            ('%064x' % self.n, sid, mapname, track, ticks, state, at))
            return cur.lastrowid

    def set_state(self, rid, state):
        with sqlite3.connect(self.store) as s:
            s.execute('UPDATE runs SET state = ? WHERE id = ?', (state, rid))

    def lobby(self, sid, mapname, track, ticks, at=1795400000, name='LobbyName'):
        with sqlite3.connect(self.db) as c:
            c.execute(S._UPSERT_RUN, (mapname, track, 0, 'community', 'tas', sid, name, ticks, 66.6667,
                                      int(round(ticks * 1000.0 / 66.6667)), 4718985, 'p27620', '', at, 0, 0, 0, 0))

    def sync(self, **kw):
        return T.sync(self.store, self.db, self.state, log=lambda s: None, **kw)

    def board(self, mapname, track=0):
        S._rate.clear()
        r = self.client.get('/api/board', query_string=dict(map=mapname, track=track, leg=0, tier='community',
                                                            style='tas', limit=50))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return [(x['player'], x['name'], x['ms'], x['rep']) for x in json.loads(r.get_data(as_text=True))['rows']]

    def rows(self):
        with sqlite3.connect(self.db) as c:
            return sorted(c.execute("SELECT map, track, tier, player, node, runid, millis FROM runs WHERE style = 'tas'"))

    def test_constants_match_their_owners(self):
        self.assertEqual((T.TF_TAS, T.TIER, T.STYLE, T.MAX_TRACK), (S.TF_TAS, S.TIER_COMMUNITY, S.STYLE_TAS, U.MAX_TRACK))
        self.assertEqual(T.MAPNAME.pattern, S._MAPNAME_OK.pattern)
        self.assertEqual(round(1 / U.TICK, 4), T.RATE)
        self.assertEqual(set(T.COLS), set(S._UPSERT_RUN.split('(')[1].split(')')[0].replace(' ', '').replace('\n', '').split(',')))

    def test_shown_upload_reaches_the_board(self):
        self.upload(ROU, 'surf_sandtrap2', 0, 3211)
        self.upload(LEX, 'surf_sandtrap2', 0, 3000, state='held')
        self.upload(LEX, 'surf_sandtrap2', 0, 2900, state='rejected')
        self.upload(NOBODY, 'surf_sandtrap2', 0, 2800)     # no account: tasupd's board does not show it either
        self.upload(BAN, 'surf_sandtrap2', 0, 2700)
        self.assertEqual(self.board('surf_sandtrap2'), [])
        n = self.sync()
        self.assertEqual((n['added'], n['removed']), (1, 0))
        self.assertEqual(self.board('surf_sandtrap2'), [(ROU, 'Rounin', 48165, 0)])
        self.assertEqual(self.sync(), dict(added=0, updated=0, removed=0, restored=0, kept_lobby=0, skipped=0))

    def test_dry_run_writes_nothing(self):
        self.upload(ROU, 'surf_sandtrap2', 0, 3211)
        self.assertEqual(self.sync(dry_run=True)['added'], 1)
        self.assertEqual(self.board('surf_sandtrap2'), [])
        self.assertEqual(self.sync()['added'], 1)

    def test_best_upload_and_removal(self):
        a = self.upload(ROU, 'surf_x', 2, 900)
        b = self.upload(ROU, 'surf_x', 2, 800)
        self.sync()
        self.assertEqual(self.rows(), [('surf_x', 2, 'community', ROU, 'tasup', 'tasup-%d' % b, 12000)])
        self.set_state(b, 'removed')
        n = self.sync()
        self.assertEqual((n['removed'], n['added']), (1, 1))
        self.assertEqual(self.rows(), [('surf_x', 2, 'community', ROU, 'tasup', 'tasup-%d' % a, 13500)])
        self.set_state(a, 'rejected')
        self.sync()
        self.assertEqual(self.rows(), [])

    def test_faster_lobby_row_stays(self):
        self.lobby(LEX, 'surf_y', 0, 500)
        self.upload(LEX, 'surf_y', 0, 600)
        n = self.sync()
        self.assertEqual((n['added'], n['kept_lobby']), (0, 1))
        self.assertEqual(self.board('surf_y'), [(LEX, 'LobbyName', 7500, 0)])

    def test_slower_lobby_row_comes_back(self):
        self.lobby(LEX, 'surf_y', 0, 700)
        with sqlite3.connect(self.db) as c:
            before = c.execute("SELECT * FROM runs WHERE style = 'tas'").fetchall()
        rid = self.upload(LEX, 'surf_y', 0, 600)
        self.sync()
        self.assertEqual(self.board('surf_y'), [(LEX, 'Proto', 9000, 0)])
        self.set_state(rid, 'removed')
        self.assertEqual(self.sync()['restored'], 1)
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute("SELECT * FROM runs WHERE style = 'tas'").fetchall(), before)
        self.assertEqual(sqlite3.connect(self.state).execute('SELECT COUNT(*) FROM displaced').fetchone()[0], 0)

    def test_next_best_slower_than_the_lobby_row(self):
        self.lobby(LEX, 'surf_y', 0, 650)
        fast = self.upload(LEX, 'surf_y', 0, 600)
        self.upload(LEX, 'surf_y', 0, 680)
        self.sync()
        self.set_state(fast, 'removed')
        n = self.sync()
        self.assertEqual((n['removed'], n['restored'], n['kept_lobby'], n['added']), (1, 1, 1, 0))
        self.assertEqual(self.board('surf_y'), [(LEX, 'LobbyName', 9750, 0)])

    def test_lobby_goes_faster_later(self):
        self.lobby(LEX, 'surf_y', 0, 700)
        self.upload(LEX, 'surf_y', 0, 600)
        self.sync()
        self.lobby(LEX, 'surf_y', 0, 550, at=1795600000)     # submit_run's upsert over the upload's row
        n = self.sync()
        self.assertEqual(n['kept_lobby'], 1)
        st = sqlite3.connect(self.state)
        self.assertEqual(st.execute('SELECT (SELECT COUNT(*) FROM displaced) + (SELECT COUNT(*) FROM filed)').fetchone()[0], 0)

    def test_set_aside_row_is_not_filed_again(self):
        rid = self.upload(ROU, 'surf_z', 0, 1000)
        self.sync()
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE runs SET tier = 'community^x' WHERE runid = ?", ('tasup-%d' % rid,))
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
        self.assertEqual(self.rows(), [('surf_z', 0, 'banned:community', ROU, 'tasup', 'tasup-%d' % rid, 15000)])
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

    def test_cli_quiet(self):
        self.upload(ROU, 'surf_z', 0, 1000)
        self.assertEqual(T.main(['--store', str(self.store), '--db', str(self.db), '--state', str(self.state), '--quiet']), 0)
        self.assertEqual(len(self.rows()), 1)


if __name__ == '__main__':
    unittest.main()
