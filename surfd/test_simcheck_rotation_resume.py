"""P1858: a pass that runs out of read budget mid-rotation resumes there (SQLite only).

Live 28 Nov: the source cursor sat at the newest run; each pass wrapped to id 0 and judged 653 complete runs before the
oldest incomplete one (~1.24M VM steps against the 1M pass budget), so 65 runs stayed incomplete for up to 23 days.
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

COMPLETE = 120          # complete runs on one map below the incomplete pair (7,140 stored pairs)


class RotationResume(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('CREATE TABLE replays(id INTEGER PRIMARY KEY, kind TEXT, map TEXT, track INTEGER,'
                          ' leg INTEGER, leaf TEXT, tier TEXT, player TEXT)')
        simcheck.ensure_schema(self.conn)
        ids = list(range(1, COMPLETE + 1))
        rows = [(i, 'run', 'full', 0, 0, str(i), '', 'p') for i in ids]
        rows += [(COMPLETE + 1, 'run', 'gap', 0, 0, 'a', '', 'p'), (COMPLETE + 2, 'run', 'gap', 0, 0, 'b', '', 'p')]
        rows += [(i, 'momentum', 'full', 0, 0, str(i), '', 'p') for i in range(COMPLETE + 3, COMPLETE + 400)]
        top = COMPLETE + 400
        rows += [(top, 'run', 'alone', 0, 0, 't', '', 'p')]
        self.conn.executemany('INSERT INTO replays VALUES(?,?,?,?,?,?,?,?)', rows)
        self.conn.executemany("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,at) VALUES(?,?,'full',0,0,'skip',0)",
                              [(a, b) for a in ids for b in ids if a < b])
        simcheck._checkpoint(self.conn, 'source', top)     # the live cursor: at the newest run
        self.conn.commit()
        self.compared = []
        self.mod = SimpleNamespace(BOUNDED_INPUT_VERSION=1, compare_paths=self.compare)
        self.surfd = SimpleNamespace(replay_file=lambda row: (row['id'], ''))

    def tearDown(self):
        self.conn.close()

    def compare(self, a, b, **limits):
        self.compared.append((a, b))
        return 'compared', {'compared': 1, 'match': .5, 'cover': 1., 'prefix': 1, 'offset': 0, 'moves_a': 80,
                            'moves_b': 80, 'tickrate_a': 100, 'tickrate_b': 100, 'who_a': 'a', 'who_b': 'b',
                            'same_who': False}

    def wrap_cost(self):
        """VM steps of one unbounded wrap read from the bottom to the incomplete pair."""
        steps = [0]
        self.conn.set_progress_handler(lambda: steps.__setitem__(0, steps[0] + 1) or 0, 1)
        try:
            self.conn.execute('SELECT r.* FROM replays r WHERE ' + simcheck._PENDING_WHERE
                              + ' AND r.id <= ? ORDER BY r.id LIMIT 1', (COMPLETE + 400,)).fetchall()
        finally:
            self.conn.set_progress_handler(None, 0)
        return steps[0]

    def step(self, steps):
        with mock.patch.object(simcheck, '_recsim', return_value=(self.mod, 'fake')):
            return simcheck.similarity_step(self.conn, self.surfd, limit=1, max_pairs=1, max_seconds=30,
                                           read_budget=simcheck.ReadBudget(self.conn, steps))

    def test_budget_limited_passes_reach_the_old_incomplete_run(self):
        cost = self.wrap_cost()
        budget = cost // 2
        self.assertGreater(budget, 20000, 'fixture too small to discriminate (wrap read %d steps)' % cost)
        notes = []
        for _ in range(6):
            out = self.step(budget)
            notes.append(out[2])
            if self.compared:
                break
        self.assertIn('SQL read limit', notes[0], 'the condition under test: the first pass runs out (%r)' % notes)
        self.assertEqual(self.compared, [(COMPLETE + 1, COMPLETE + 2)],
                         'the incomplete pair is reached within 6 passes of %d steps (wrap read: %d): %r'
                         % (budget, cost, notes))

    def test_a_rotation_that_fits_writes_nothing(self):
        self.conn.execute("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,at) VALUES(?,?,'gap',0,0,'skip',0)",
                          (COMPLETE + 1, COMPLETE + 2))
        self.conn.commit()
        before = tuple(self.conn.iterdump())
        self.assertEqual(self.step(10 ** 7), (0, 0, ''))
        self.assertEqual(tuple(self.conn.iterdump()), before)

    def test_a_limited_pass_never_moves_the_cursor_past_an_eligible_run(self):
        # Whatever the budget, a pass that stops short leaves the incomplete pair at or after the cursor.
        for budget in (3000, 6000, 12000, 24000, 48000):
            self.setUp()
            self.step(budget)
            if not self.compared:
                cur = simcheck._cursor(self.conn, 'source')
                self.assertTrue(cur <= COMPLETE or cur == COMPLETE + 400,
                                'budget %d left the cursor at %d, past the eligible run %d' % (budget, cur, COMPLETE + 1))


if __name__ == '__main__':
    unittest.main()
