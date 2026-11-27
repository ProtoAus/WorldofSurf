#!/usr/bin/env python3
"""P1857: the admin's season strafe flag reader -- bounded, validated, unavailable rather than falsely clean."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import admin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import seasonflag  # noqa: E402


def report():
    rows = [dict(who='p%d' % k, name='P%d' % k, rd=(k - 4) * 0.05 + (i % 5 - 2) * 0.3, rd_inj=(k - 4) * 0.05 + 1.7)
            for k in range(8) for i in range(25)]
    rep = seasonflag.season(rows)
    rep['generated_utc'] = '2026-11-28T00:00:00Z'
    return rep


class SeasonFlag(unittest.TestCase):
    def read(self, data):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.json')
            if data is not None:
                Path(p).write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode())
            return admin.seasonflag_report(p)

    def test_the_tools_report_reads_back(self):
        got = self.read(report())
        self.assertTrue(got['available'])
        self.assertEqual(len(got['players']), 8)
        self.assertEqual(got['flagged'], 0)
        self.assertEqual(got['min_runs'], seasonflag.MIN_RUNS)
        self.assertEqual(set(got['players'][0]), {'name', 'runs', 'z', 'z_if_always_on', 'flag'})

    def test_missing_is_not_a_clean_list(self):
        self.assertEqual(self.read(None), {'available': False, 'why': 'no report yet'})

    def test_oversized_and_malformed_are_unavailable(self):
        self.assertFalse(self.read(b'{' + b' ' * admin.SEASONFLAG_BYTES + b'}')['available'])
        self.assertFalse(self.read(b'not json')['available'])
        bad = report()
        del bad['players'][0]['z']
        self.assertEqual(self.read(bad)['why'], 'report unreadable')

    def test_names_are_bounded(self):
        rep = report()
        rep['players'][0]['name'] = 'x' * 500
        self.assertEqual(len(self.read(rep)['players'][0]['name']), 64)


if __name__ == '__main__':
    unittest.main()
