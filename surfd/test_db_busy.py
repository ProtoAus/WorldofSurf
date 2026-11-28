#!/usr/bin/env python3
"""P1864: lobby writes under a held SQLite write lock (a sweep pass holding it past the busy wait).

A second connection holds BEGIN IMMEDIATE, as sweep.py's writer does; the busy waits are shortened so the
suite stays fast (heartbeat 300 ms for connect()'s 5 s, run 1500 ms for RUN_BUSY_MS).
"""
import functools
import logging
import shutil
import sqlite3
import threading
import time
import unittest

from test_surfd import fresh


def submit(mod, src='127.0.0.1', **kw):
    """POST one run (test_board.submit's form; that module runs its checks on import). Body or 'HTTP nnn'."""
    form = {'key': 'testkey', 'map': 'surf_test', 'track': '0', 'leg': '0', 'player': '0123456789abcdef0123456789abcdef', 'name': 'Alice',
            'ticks': '4108', 'tickrate': '66.666667', 'flags': '0', 'node': 'p27510', 'runid': 'r1'}
    form.update({k: str(v) for k, v in kw.items()})
    resp = mod.app.test_client().post('/api/run', data=form, environ_base={'REMOTE_ADDR': src})
    return resp.get_json() if resp.status_code == 200 else 'HTTP %d' % resp.status_code

BEAT = {'key': 'testkey', 'node': 'p27510', 'map': 'surf_busy_fixture', 'players': '0', 'max': '32',
        'port': '27510', 'name': 'synthetic busy fixture'}


class HeldLock:
    """BEGIN IMMEDIATE on another connection; released after `hold` seconds (None: at exit)."""
    def __init__(self, path, hold=None):
        self.conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=0)
        self.hold, self.timer = hold, None

    def __enter__(self):
        self.conn.execute('BEGIN IMMEDIATE')
        if self.hold is not None:
            self.timer = threading.Timer(self.hold, self.release)
            self.timer.start()
        return self

    def release(self):
        if self.conn.in_transaction:
            self.conn.execute('COMMIT')

    def __exit__(self, *exc):
        if self.timer:
            self.timer.join()
        self.release()
        self.conn.close()


class DbBusy(unittest.TestCase):
    def setUp(self):
        self.m = fresh(trusted='127.0.0.0/8')
        self.m.connect = functools.partial(self.m.connect, busy_timeout_ms=300)
        self.m.RUN_BUSY_MS = 1500
        self.m.TOUR_BUSY_MS = 1500
        self.client = self.m.app.test_client()
        self.assertEqual(self.beat().status_code, 200)        # schema exists before any lock is held
        self.db = self.m.DB_PATH

    def tearDown(self):
        for h in list(self.m.log.handlers):      # each fresh() import adds a file handler under its own home
            h.close()
            self.m.log.removeHandler(h)
        shutil.rmtree(self.m._test_home)

    def beat(self):
        return self.client.post('/api/heartbeat', data=BEAT, environ_base={'REMOTE_ADDR': '127.0.0.1'})

    def test_heartbeat_under_a_long_lock_is_a_clear_503(self):
        with HeldLock(self.db):
            t0 = time.monotonic()
            r = self.beat()
            waited = time.monotonic() - t0
        self.assertEqual(r.status_code, 503, r.get_data(as_text=True))
        self.assertEqual(r.headers.get('Retry-After'), '2')
        self.assertIn('busy', r.get_json()['error'])
        self.assertLess(waited, 1.0)                           # the heartbeat's own busy wait, no longer
        self.assertEqual(self.beat().status_code, 200)         # and the next beat lands

    def test_heartbeat_under_a_brief_lock_waits_and_succeeds(self):
        with HeldLock(self.db, hold=0.1):
            r = self.beat()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_run_submit_waits_past_the_heartbeat_wait(self):
        with HeldLock(self.db, hold=0.8):                      # past 300 ms, inside RUN_BUSY_MS
            out = submit(self.m, runid='busy1')
        self.assertIsInstance(out, dict, out)
        self.assertTrue(out['ok'] and out['stored'], out)

    def test_run_submit_past_its_bound_is_a_clear_503(self):
        with HeldLock(self.db):
            t0 = time.monotonic()
            out = submit(self.m, runid='busy2')
            waited = time.monotonic() - t0
        self.assertEqual(out, 'HTTP 503')
        self.assertLess(waited, 1.5 * 3 + 1.0)                 # bounded: each write waits at most RUN_BUSY_MS
        self.assertTrue(submit(self.m, runid='busy2')['stored'])

    def test_lock_classifier_reads_the_result_code(self):
        def err(msg, code=None, cls=sqlite3.OperationalError):
            e = cls(msg)
            if code is not None:
                e.sqlite_errorcode = code
            return e
        self.assertTrue(self.m.db_locked(err('database is locked', sqlite3.SQLITE_BUSY)))
        self.assertTrue(self.m.db_locked(err('x', sqlite3.SQLITE_BUSY | 512)))           # BUSY_SNAPSHOT
        self.assertFalse(self.m.db_locked(err('database table is locked', sqlite3.SQLITE_LOCKED)))  # code fault: 500
        self.assertFalse(self.m.db_locked(err('database is locked', sqlite3.SQLITE_IOERR)))  # the code wins over text
        self.assertTrue(self.m.db_locked(err('database is locked')))                     # no code: text
        self.assertFalse(self.m.db_locked(err('disk I/O error')))
        self.assertFalse(self.m.db_locked(err('database is locked', cls=sqlite3.IntegrityError)))
        with HeldLock(self.db):                                                         # a real one carries code 5
            c = sqlite3.connect(self.db, timeout=0)
            try:
                c.execute('BEGIN IMMEDIATE')
            except sqlite3.OperationalError as exc:
                real = exc
            c.close()
        self.assertTrue(self.m.db_locked(real), getattr(real, 'sqlite_errorcode', None))

    def run_with_lock_after_identity(self, hold, ranked):
        """The lock is taken after /api/run's identity step (inside story_facts) and held `hold` s."""
        self.m.RANKED_LINKED = ranked
        orig, held = self.m.story_facts, []

        def facts(*a, **k):
            h = HeldLock(self.db, hold=hold)
            h.__enter__()
            held.append(h)
            return orig(*a, **k)
        self.m.story_facts = facts
        try:
            return submit(self.m, runid='mid%g%d' % (hold, ranked))
        finally:
            self.m.story_facts = orig
            for h in held:
                h.__exit__(None, None, None)

    def test_run_main_write_waits_for_a_lock_taken_after_identity(self):
        for ranked in (False, True):
            out = self.run_with_lock_after_identity(0.8, ranked)
            self.assertIsInstance(out, dict, (ranked, out))
            self.assertTrue(out['stored'], (ranked, out))

    def test_run_main_write_past_its_bound_is_a_clear_503(self):
        self.assertEqual(self.run_with_lock_after_identity(2.5, True), 'HTTP 503')

    def test_run_busy_wait_ends_with_the_main_commit(self):
        orig, seen = self.m.rank_of, []

        def rank_of(db, *a, **k):
            seen.append(db.execute('PRAGMA busy_timeout').fetchone()[0])
            return orig(db, *a, **k)
        self.m.rank_of = rank_of
        try:
            self.assertTrue(submit(self.m, runid='restore1')['stored'])
        finally:
            self.m.rank_of = orig
        self.assertEqual(seen, [300])                          # the connection's own wait, not RUN_BUSY_MS

    def test_tournament_state_waits_out_a_lock_shorter_than_its_bound(self):
        with HeldLock(self.db, hold=0.8):
            r = self.client.post('/api/tournaments/game', data={'key': 'testkey', 'node': 'p27510', 'op': 'state'},
                                 environ_base={'REMOTE_ADDR': '127.0.0.1'})
        self.assertNotEqual(r.get_json().get('status'), 'storage', r.get_json())

    def test_tournament_storage_busy_is_a_warning_and_a_retryable_reply(self):
        with HeldLock(self.db), self.assertLogs(self.m.log, level='WARNING') as logs:
            r = self.client.post('/api/tournaments/game', data={'key': 'testkey', 'node': 'p27510', 'op': 'state'},
                                 environ_base={'REMOTE_ADDR': '127.0.0.1'})
        body = r.get_json()
        self.assertEqual(body.get('status'), 'storage', body)       # the lobby resends the identical request
        self.assertTrue(any('tournament storage busy' in x for x in logs.output), logs.output)
        self.assertFalse(any(rec.levelno >= logging.ERROR for rec in logs.records), logs.output)


if __name__ == '__main__':
    unittest.main()
