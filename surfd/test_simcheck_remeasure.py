"""P1859: a reader-dependent skip from an older reader revision is re-measured once, in place (SQLite only).

SIMCHECK_UNDER_TEST=<path> runs this against another simcheck.py (the parent must fail it)."""
import importlib.util
import os
import sqlite3
import unittest
from types import SimpleNamespace
from unittest import mock

import simcheck

if os.environ.get('SIMCHECK_UNDER_TEST'):
    spec = importlib.util.spec_from_file_location('simcheck_under_test', os.environ['SIMCHECK_UNDER_TEST'])
    simcheck = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(simcheck)


class Remeasure(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('CREATE TABLE replays(id INTEGER PRIMARY KEY, kind TEXT, map TEXT, track INTEGER,'
                          ' leg INTEGER, leaf TEXT, tier TEXT, player TEXT)')
        self.conn.executemany('INSERT INTO replays VALUES(?,?,?,?,?,?,?,?)',
                              [(i, 'run', 'm', 0, 0, str(i), '', 'p') for i in (1, 2, 3)])
        self.conn.commit()
        simcheck.ensure_schema(self.conn)
        self.conn.commit()
        self.compared = []
        self.verdict = 'compared'
        self.surfd = SimpleNamespace(replay_file=lambda row: (row['id'], ''))

    def tearDown(self):
        self.conn.close()

    def seed(self, a, b, verdict, code='', reader=None):
        cols = 'a_id,b_id,map,track,leg,verdict,skip_code,at' + (',reader' if reader is not None else '')
        vals = (a, b, 'm', 0, 0, verdict, code, 0) + ((reader,) if reader is not None else ())
        self.conn.execute('INSERT INTO sims(%s) VALUES(%s)' % (cols, ','.join('?' * len(vals))), vals)
        self.conn.commit()

    def reader(self, revision):
        mod = SimpleNamespace(BOUNDED_INPUT_VERSION=1, SOURCE_CAPTURE_VERSION=1, compare_paths=self.compare)
        if revision is not None:
            mod.READER_REVISION = revision
        return mod

    def compare(self, a, b, **limits):
        self.compared.append((a, b))
        if self.verdict != 'compared':
            return self.verdict, 'synthetic %s' % self.verdict
        return 'compared', {'compared': 80, 'match': .4, 'cover': 1., 'prefix': 1, 'offset': 0, 'moves_a': 80,
                            'moves_b': 80, 'tickrate_a': 100, 'tickrate_b': 100, 'who_a': 'a', 'who_b': 'b',
                            'same_who': False}

    def step(self, revision, pairs=10):
        with mock.patch.object(simcheck, '_recsim', return_value=(self.reader(revision), 'fake')):
            return simcheck.similarity_step(self.conn, self.surfd, limit=5, max_pairs=pairs, max_seconds=5)

    def rows(self):
        return [tuple(r) for r in self.conn.execute(
            'SELECT id, a_id, b_id, verdict, skip_code, reader FROM sims ORDER BY id')]

    def legacy(self):
        self.seed(1, 2, 'skip', 'unmodelled')          # the live shape: no reader recorded -> revision 1
        self.seed(1, 3, 'skip', 'helped')              # not reader-dependent
        self.seed(2, 3, 'compared')

    def test_a_newer_reader_remeasures_only_the_stale_skip_in_place(self):
        self.legacy()
        before = self.rows()
        self.assertEqual([r[5] for r in before], [1, 1, 1], 'existing rows read as revision 1')
        out = self.step(2)
        self.assertEqual(self.compared, [(1, 2)], out)
        after = self.rows()
        self.assertEqual(after[0], (before[0][0], 1, 2, 'compared', '', 2), 'replaced in place, same id')
        self.assertEqual(after[1:], before[1:], 'the helped skip and the measured pair are untouched')
        self.assertEqual(out[0], 1)
        self.assertEqual(self.step(2), (0, 0, ''))
        self.assertEqual((self.compared, self.rows()), ([(1, 2)], after), 'a settled sample stays idle')

    def test_the_installed_reader_remeasures_nothing(self):
        self.legacy()
        dump = tuple(self.conn.iterdump())
        for revision in (None, 1):
            self.assertEqual(self.step(revision), (0, 0, ''))
        self.assertEqual(self.compared, [])
        self.assertEqual(tuple(self.conn.iterdump()), dump)

    def test_a_skip_again_is_stored_at_the_new_revision_and_not_retried(self):
        self.legacy()
        self.verdict = 'malformed input'
        out = self.step(2)
        self.assertEqual(self.compared, [(1, 2)], out)
        self.assertEqual(self.rows()[0][3:], ('skip', 'malformed', 2))
        self.assertEqual(self.step(2), (0, 0, ''))
        self.assertEqual(self.compared, [(1, 2)], 'no re-measure loop')
        self.verdict = 'compared'
        self.step(3)
        self.assertEqual([tuple(sorted(c)) for c in self.compared], [(1, 2), (1, 2)], 'a later revision may try it again')
        self.assertEqual(self.rows()[0][3:], ('compared', '', 3))

    def test_stale_rows_in_both_orientations_settle_without_a_unique_clash(self):
        self.seed(1, 2, 'skip', 'unmodelled')
        self.seed(2, 1, 'skip', 'malformed')
        self.seed(1, 3, 'compared')
        self.seed(2, 3, 'compared')
        self.step(2)
        self.assertEqual(self.compared, [(1, 2)])
        verdicts = sorted((r[1], r[2], r[3], r[5]) for r in self.rows() if {r[1], r[2]} == {1, 2})
        self.assertEqual(verdicts, [(1, 2, 'compared', 2), (2, 1, 'skip', 1)])
        self.assertEqual(self.step(2), (0, 0, ''), 'one settling row settles the pair')

    def test_a_historical_table_gains_the_column_with_revision_1(self):
        old = sqlite3.connect(':memory:')
        self.addCleanup(old.close)
        old.executescript(simcheck.SIMS_SQL.replace('    reader     INTEGER NOT NULL DEFAULT 1,\n', ''))
        self.assertNotIn('reader', {r[1] for r in old.execute('PRAGMA table_info(sims)')})
        old.execute("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,skip_code,at) VALUES(1,2,'m',0,0,'skip','unmodelled',0)")
        old.commit()
        simcheck.ensure_schema(old)
        simcheck.ensure_schema(old)
        self.assertEqual(old.execute('SELECT reader FROM sims').fetchone()[0], 1)

    def test_a_direct_caller_on_a_historical_table_compares_as_before(self):
        old = sqlite3.connect(':memory:')
        self.addCleanup(old.close)
        old.row_factory = sqlite3.Row
        old.execute('CREATE TABLE replays(id INTEGER PRIMARY KEY, kind TEXT, map TEXT, track INTEGER,'
                    ' leg INTEGER, leaf TEXT, tier TEXT, player TEXT)')
        old.executemany('INSERT INTO replays VALUES(?,?,?,?,?,?,?,?)', [(i, 'run', 'm', 0, 0, str(i), '', 'p') for i in (1, 2)])
        old.executescript(simcheck.SIMS_SQL.replace('    reader     INTEGER NOT NULL DEFAULT 1,\n', ''))
        old.commit()
        row = old.execute('SELECT * FROM replays WHERE id=1').fetchone()
        with mock.patch.object(simcheck, '_recsim', return_value=(self.reader(2), 'fake')):
            out = simcheck.compare_run(self.surfd, old, row)
        self.assertEqual(out[0], 1)
        self.assertEqual(old.execute('SELECT verdict FROM sims').fetchone()[0], 'compared')

    def test_the_real_reader_declares_its_revision(self):
        spec = importlib.util.spec_from_file_location(
            'recsim_revision', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'census', 'recsim.py'))
        rs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rs)
        self.assertEqual(simcheck.reader_revision(rs), 2)


if __name__ == '__main__':
    unittest.main()
