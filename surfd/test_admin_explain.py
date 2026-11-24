#!/usr/bin/env python3
"""P1820: admin.explain_verdict puts pm_verify's reasons in plain words.  python3 test_admin_explain.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import admin  # noqa: E402

# Every distinct reason in the live store on 24 Nov 2026 (digits as they print), and its expected heading.
LIVE = (
    ('PASS', 'ticks 9131 rows 9131', 'Replayed exactly'),
    ('PASS', 'abandoned at tick 51; the replay reproduces to there (pm_verify: no finish: the zones never end this run)',
     'Partial run replayed'),
    ('REFUSE', 'a cold rewind (`pause retry|load`): the move before it has no stated duration', 'Used retry or a save'),
    ('REFUSE', 'a non-counted/kept v12 closing clock (not modelled)', 'Timer kind not replayable yet'),
    ('REFUSE', 'an incomplete or inconsistent v12 viewing clock', 'Watched mid-run; viewing time does not add up'),
    ('REFUSE', 'a `pause` no `session` answers (the run is still parked)', 'Parked, never resumed'),
    ('REFUSE', 'a save-state resume or retry', 'Used retry or a save'),
    ('REFUSE', 'parked-wall clock edges (not modelled)', 'Parked, finished later'),
    ('REFUSE', 'frozen timer accounting (`hold`) is not modeled', 'Timer was frozen'),
    ('ERROR', 'timeout', 'Checker error'),
)


class Explain(unittest.TestCase):
    def test_live_reasons(self):
        for verdict, reason, short in LIVE:
            e = admin.explain_verdict(verdict, reason)
            self.assertEqual(e['short'], short, reason)
            self.assertTrue(e['text'].endswith('.'), reason)

    def test_hold_always_asks_for_a_look(self):
        for reason in ('state: 3 packet(s) differ, first at row 40', 'native REC15 body/clock reproduction disagrees',
                       'counts: the view read mouse counts the device did not send (2 record(s), first at row 9)', ''):
            self.assertEqual(admin.explain_verdict('HOLD', reason)['look'], 2, reason)

    def test_refuse_never_accuses(self):
        # REFUSE is "cannot say": at most "worth a look when it stands high", never the HOLD level.
        for reason in ('a malformed `pause`', 'a different map', 'something a newer engine prints', ''):
            e = admin.explain_verdict('REFUSE', reason)
            self.assertLess(e['look'], 2, reason)
        self.assertEqual(admin.explain_verdict('REFUSE', 'something new')['short'], 'Checker could not replay it')

    def test_prop_skew_is_said(self):
        e = admin.explain_verdict('HOLD', 'state: 1 packet(s) differ, first at row 5; lobby lacked 2 prop model file(s): a, b')
        self.assertIn('missing 2 prop model file(s)', e['text'])

    def test_no_verdict(self):
        self.assertIsNone(admin.explain_verdict(None, None))


if __name__ == '__main__':
    unittest.main()
