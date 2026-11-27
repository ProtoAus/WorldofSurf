"""Store-only turning observations, on synthetic recordings and an in-memory DB."""
import hashlib
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

import admin
import test_simcheck_ingestion as fixture

ROOT, rs, sc = fixture.ROOT, fixture.rs, fixture.sc


def recording(step, *, start=0, count=82, rate=100, bad=None):
    rows = ['FTESURF-REC 9', 'map synthetic', f'tickrate {rate}', 'begin']
    for i in range(count):
        index = i - start
        yaw = bad if bad is not None and i == 25 else (359 + index * step) % 360
        rows.append(f'in {i} {i} 0 {100 + index} 0 0 0 {yaw} 0 4')
    return ('\n'.join(rows + [f'end {count}']) + '\n').encode()


class Turning(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='sim-yaw-')
        self.addCleanup(temp.cleanup)
        self.a, self.b = Path(temp.name) / 'a.rec', Path(temp.name) / 'b.rec'
        self.left, self.right = (self.current(recording(1, count=80)), self.current(recording(1, start=2)))
        self.a.write_bytes(self.left)
        self.b.write_bytes(self.right)
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.addCleanup(self.c.close)
        self.c.execute('CREATE TABLE replays (id INTEGER PRIMARY KEY, map TEXT, track INTEGER, leg INTEGER, '
                       'kind TEXT, tier TEXT, player TEXT)')
        self.c.executemany("INSERT INTO replays VALUES (?, 'synthetic',0,0,'run','ranked','synthetic')",
                           [(1,), (2,)])
        self.c.commit()
        self.app = SimpleNamespace(replay_file=lambda row: (str(self.a if row['id'] == 1 else self.b), ''))

    @staticmethod
    def current(data):
        # The view-clock record adds no move; the released row still carries input.
        return data.replace(b'FTESURF-REC 9', b'FTESURF-REC 14').replace(
            b'begin\nin 0', b'begin\nviewclock spec 1 100.5 0\nfzin 0', 1)

    def read(self, **kwargs):
        return rs.compare_paths(str(self.a), str(self.b), **kwargs)

    def step(self):
        return sc.similarity_step(self.c, self.app, tools_dir=str(ROOT / 'tools'))

    def stored(self):
        out = admin.similarity_for(self.c, 1)
        self.assertTrue(out['available'])
        self.assertEqual(len(out['pairs']), 1)
        return out['pairs'][0]

    def test_aligned_wrap_and_exact_source_bytes_reach_review(self):
        verdict, data = self.read(max_bytes=8192, max_moves=82)
        self.assertEqual((verdict, data['offset'], data['compared']), ('compared', 2, 80))
        expected = {'agree': 79, 'turning': 79}
        self.assertEqual(data.get('yaw'), expected)
        self.assertEqual(self.step()[0], 1)
        self.assertEqual(tuple(self.c.execute('SELECT yaw_agree,yaw_turning FROM sims').fetchone()), (79, 79))
        pair = self.stored()
        self.assertEqual(pair.get('yaw'), expected)
        self.assertEqual(admin.similarity_for(self.c, 2)['pairs'][0].get('yaw'), expected)
        self.assertEqual(pair['sources'], {'version': 1, **{
            side: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            for side, raw in [('a', self.left), ('b', self.right)]}})
        self.assertEqual(pair['metrics']['match'], 1.0)

    def test_zero_agreement_is_not_missing(self):
        self.b.write_bytes(recording(-1, start=2))
        self.assertEqual(self.step()[0], 1)
        self.assertEqual(self.stored().get('yaw'), {'agree': 0, 'turning': 79})

    def test_unavailable_turning_does_not_replace_move_measurement(self):
        fixtures = [(recording(0, count=80), recording(0, start=2)),
                    (self.left, recording(1, start=2, rate=125)),
                    (self.left, recording(1, start=2, bad='NaN')),
                    (self.left, recording(1, start=2, bad='invalid'))]
        for a, b in fixtures:
            with self.subTest(rate=b.splitlines()[2], row=b.splitlines()[29]):
                self.a.write_bytes(a)
                self.b.write_bytes(b)
                verdict, detail = self.read()
                self.assertEqual((verdict, detail['compared'], detail.get('yaw')), ('compared', 80, None))

    def test_unknown_tickrate_key_does_not_create_turn_eligibility(self):
        self.a.write_bytes(recording(1, count=80, rate=0.008).replace(
            b'begin\n', b'tickrate_note 0.01\nbegin\n', 1))
        self.b.write_bytes(recording(1, start=2, rate=0.01))
        verdict, detail = self.read()
        self.assertEqual((verdict, detail['compared']), ('compared', 80))
        self.assertEqual((detail['tickrate_a'], detail['tickrate_b']), (0.008, 0.01))
        self.assertIsNone(detail.get('yaw'))

    def test_pairs_cli_reports_move_controls_with_unreadable_yaw(self):
        root = self.a.parent / 'data/runs/synthetic/main'
        root.mkdir(parents=True)
        (root / 'a.rec').write_bytes(recording(1, count=80, bad='invalid'))
        (root / 'b.rec').write_bytes(recording(1, start=2))
        cli = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/census/recsim.py'),
                              '--root', str(root), 'pairs', '--max', '3'],
                             capture_output=True, text=True, timeout=20)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertIn('NEGATIVE pairs (different runs, same map+leg): 1', cli.stdout)
        self.assertIn('POSITIVE pairs (same recording, shifted tick epoch): 2', cli.stdout)
        turn_control = next(line for line in cli.stdout.splitlines() if 'POSITIVE exact copy:' in line)
        self.assertTrue(turn_control.endswith('(n 1)'), turn_control)

    def create_preyaw_schema(self):
        legacy = sc.SIMS_SQL.replace('    yaw_agree  INTEGER,\n    yaw_turning INTEGER,\n', '')
        self.c.executescript(legacy)

    def test_direct_writer_stores_move_on_preyaw_schema_without_migration(self):
        self.create_preyaw_schema()
        before = tuple(self.c.execute('PRAGMA table_info(sims)'))
        row = self.c.execute('SELECT * FROM replays ORDER BY id LIMIT 1').fetchone()
        self.assertEqual(sc.compare_run(self.app, self.c, row, tools_dir=str(ROOT / 'tools')), (1, 0, 1))
        self.assertEqual(tuple(self.c.execute('PRAGMA table_info(sims)')), before)
        item = self.stored()
        self.assertEqual(item['metrics']['compared'], 80)
        self.assertIsNotNone(item['sources'])
        self.assertIsNone(item.get('yaw'))

    def test_legacy_schema_and_writer_do_not_invent_a_measurement(self):
        self.create_preyaw_schema()
        self.c.execute("INSERT INTO sims (a_id,b_id,map,track,leg,verdict,at,compared,tick_a,tick_b) "
                       "VALUES (1,2,'synthetic',0,0,'compared',123,80,100,100)")
        self.c.commit()
        original = tuple(self.c.execute('SELECT * FROM sims').fetchone())
        self.assertIsNone(self.stored().get('yaw'))
        sc.ensure_schema(self.c)
        sc.ensure_schema(self.c)
        row = self.c.execute('SELECT * FROM sims').fetchone()
        self.assertEqual(set(row.keys()) & {'yaw_agree', 'yaw_turning'}, {'yaw_agree', 'yaw_turning'})
        self.assertEqual(tuple(row[k] for k in row.keys() if k not in ('yaw_agree', 'yaw_turning')), original)
        self.assertIsNone(row['yaw_agree'])
        self.assertIsNone(row['yaw_turning'])
        self.assertIsNone(self.stored().get('yaw'))
        self.assertEqual(self.step()[0], 0)  # new reader must not backfill historical observations
        self.c.execute("INSERT INTO sims (a_id,b_id,map,track,leg,verdict,at) "
                       "VALUES (3,4,'synthetic',0,0,'skip',124)")
        row = self.c.execute('SELECT yaw_agree,yaw_turning FROM sims WHERE a_id=3').fetchone()
        self.assertEqual(tuple(row), (None, None))

    def test_old_reader_and_invalid_metrics_preserve_new_observation(self):
        def compare(reader_yaw):
            def old_reader(a, b, **kw):
                verdict, d = rs.compare_paths(a, b, **kw)
                self.assertEqual(verdict, 'compared')
                d.pop('yaw', None)
                if reader_yaw is not None:
                    d['yaw'] = reader_yaw
                return verdict, d
            return old_reader

        sc.ensure_schema(self.c)
        row = self.c.execute('SELECT * FROM replays ORDER BY id LIMIT 1').fetchone()
        for values in (None, {'agree': True, 'turning': 79}, {'agree': 0, 'turning': 1 << 70}):
            with self.subTest(values=values):
                self.c.execute('DELETE FROM sims')
                self.c.execute('DELETE FROM sim_cursor')
                self.c.commit()
                reader = SimpleNamespace(compare_paths=compare(values))
                self.assertEqual(sc.compare_run(self.app, self.c, row, reader=reader), (1, 0, 1))
                self.assertEqual(tuple(self.c.execute('SELECT yaw_agree,yaw_turning FROM sims').fetchone()), (None, None))
                self.assertEqual(self.stored()['metrics']['compared'], 80)

    def test_review_rejects_unbound_or_invalid_counts(self):
        self.assertEqual(self.step()[0], 1)
        self.assertEqual(self.stored().get('yaw'), {'agree': 79, 'turning': 79})
        for a, n in [(80, 79), (-1, 79), (0, 80), (0, 0), (None, 79), ('invalid', 79)]:
            with self.subTest(a=a, n=n):
                self.c.execute('UPDATE sims SET yaw_agree=?, yaw_turning=?', (a, n))
                pair = self.stored()
                self.assertIsNone(pair.get('yaw'))
                self.assertIsNotNone(pair['metrics'])
        self.c.execute("UPDATE sims SET yaw_agree=0,yaw_turning=79,source_capture='' ")
        self.assertIsNone(self.stored().get('yaw'))


if __name__ == '__main__':
    unittest.main()
