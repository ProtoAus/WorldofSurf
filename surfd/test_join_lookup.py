#!/usr/bin/env python3
"""P1835: actual /api/join admission with an isolated library and SQLite DB.
Run: TMPDIR=<owned scratch> python -B surfd/test_join_lookup.py
"""
import importlib
import logging
import os
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch


def timer_bsp():
    entities = b''.join(b'{"classname" "trigger_momentum_timer_' + kind +
                        b'" "model" "*1"}\n' for kind in (b'start', b'stop'))
    models = struct.pack('<9f3i', 0, 0, 0, 128, 128, 128, 0, 0, 0, 0, 0, 0) * 2
    header_size = 1036
    table = [(0, 0)] * 64
    table[0] = (header_size, len(entities))
    table[14] = (header_size + len(entities), len(models))
    return (b'VBSP' + struct.pack('<i', 20) + b''.join(
        struct.pack('<4i', off, size, 0, 0) for off, size in table) +
        struct.pack('<i', 1) + entities + models)


class JoinLookup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='p1835-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / 'surfd.env').write_text('SURFD_KEY=fixturekey\n')
        self.maps = self.home / 'maps'
        self.zones = [self.home / name for name in ('online', 'local', 'momlocal')]
        for directory in [self.maps] + self.zones:
            directory.mkdir()
        env = dict(SURFD_HOME=str(self.home), SURFD_DB=str(self.home / 'test.db'),
                   SURFD_MAPS=str(self.maps), SURFD_ZONES=str(self.zones[0]),
                   SURFD_ZONES_LOCAL=str(self.zones[1]), SURFD_ZONES_MOMLOCAL=str(self.zones[2]),
                   SURFD_ENV=str(self.home / 'surfd.env'), SURFD_KEY='fixturekey',
                   SURFD_TOURNAMENT_HOLD='0', SURFD_GAME=str(self.home / 'game'),
                   SURFD_RUNS=str(self.home / 'runs'), SURFD_TOOLS=str(self.home / 'tools'))
        self.env = patch.dict(os.environ, env)
        self.env.start()
        self.addCleanup(self.env.stop)
        sys.modules.pop('surfd', None)
        self.S = importlib.import_module('surfd')
        self.S.app.config['TESTING'] = True
        # Any regression to the full scanner or persistent timer cache is fatal.
        self.guards = [patch.object(self.S, name, side_effect=AssertionError(name))
                       for name in ('map_index', '_scan_maps', 'zone_file_index',
                                    '_timer_cache_load', '_timer_cache_save')]
        for guard in self.guards:
            guard.start()
            self.addCleanup(guard.stop)
        self.serial = 0
        self.beat()

    def tearDown(self):
        logger = logging.getLogger('surfd')
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    def beat(self, players=0):
        reply = self.S.app.test_client().post('/api/heartbeat', data=dict(
            key='fixturekey', node='p27510', map='surf_idle', players=str(players),
            max='16', port='27510', name='Fixture'))
        self.assertEqual(reply.status_code, 200)

    def put(self, name='surf_test', body=b'invalid BSP', zone=None):
        (self.maps / (name + '.bsp')).write_bytes(body)
        if zone is not None:
            (self.zones[zone] / (name + '.json')).write_text('{}')

    def join(self, name='surf_test', src=None):
        self.serial += 1
        src = src or '203.0.%d.%d' % (self.serial // 250, self.serial % 250 + 1)
        reply = self.S.app.test_client().get('/api/join', query_string={'map': name},
                                            environ_overrides={'REMOTE_ADDR': src})
        return reply.status_code, reply.get_json()

    def db(self, sql, args=()):
        conn = sqlite3.connect(self.S.DB_PATH)
        try:
            with conn:
                return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def test_mixed_case_and_current_files(self):
        self.put('surf_TEST')
        self.put('Surf_Test')
        self.assertEqual(self.join()[0], 200)
        self.assertEqual(self.db('SELECT map_dir FROM assignments'), [('Surf_Test',)])
        (self.maps / 'Surf_Test.bsp').unlink()
        self.db('DELETE FROM assignments')
        self.assertEqual(self.join()[0], 200)
        self.assertEqual(self.db('SELECT map_dir FROM assignments'), [('surf_TEST',)])
        (self.maps / 'surf_TEST.bsp').rename(self.maps / 'surf_new.bsp')
        self.assertEqual(self.join()[0], 404)
        self.db('DELETE FROM assignments')
        self.assertEqual(self.join('surf_new')[0], 200)
        (self.maps / 'surf_new.bsp').unlink()
        self.assertEqual(self.join('surf_new')[0], 404)
        self.put('surf_new')
        self.assertEqual(self.join('surf_new')[0], 200)

    def test_missing_unreadable_and_nonfile_maps(self):
        self.put()
        self.assertEqual(self.join()[0], 200)
        self.maps.rename(self.home / 'parked')
        self.assertEqual(self.join()[0], 404)
        self.maps.mkdir()
        (self.maps / 'surf_test.bsp').mkdir()
        self.assertEqual(self.join()[0], 404)
        real = os.scandir
        def denied(path):
            if path == str(self.maps):
                raise PermissionError('fixture')
            return real(path)
        with patch.object(self.S.os, 'scandir', side_effect=denied):
            self.assertEqual(self.join()[0], 404)

    def test_all_zone_directories_and_removal_policy(self):
        for i in range(3):
            self.db('DELETE FROM assignments')
            name = 'bhop_test%d' % i
            self.put(name, timer_bsp())
            self.assertEqual(self.join(name)[0], 403)  # embedded timers do not waive pool policy
            zone = self.zones[i] / (name.upper() + '.JSON')
            zone.write_text('{}')
            status, body = self.join(name)
            self.assertEqual((status, body['timed']), (200, 1))
            zone.unlink()
            self.assertEqual(self.join(name)[0], 403)
            zone.mkdir()
            self.assertEqual(self.join(name)[0], 403)

    def test_zone_failures_and_case_directory_do_not_admit_stale_bhop(self):
        self.put('bhop_test', zone=0)
        (self.zones[0] / 'BHOP_TEST.JSON').mkdir()
        self.assertEqual(self.join('bhop_test')[0], 200)
        self.zones[0].rename(self.home / 'parked-zones')
        self.assertEqual(self.join('bhop_test')[0], 403)
        self.zones[0].mkdir()
        (self.zones[0] / 'bhop_test.json').write_text('{}')
        self.assertEqual(self.join('bhop_test')[0], 200)
        real = os.scandir
        def denied(path):
            if path == str(self.zones[0]):
                raise PermissionError('fixture')
            return real(path)
        with patch.object(self.S.os, 'scandir', side_effect=denied):
            self.assertEqual(self.join('bhop_test')[0], 403)

    def test_recent_and_mid_listing_mutations_are_not_cached(self):
        self.put()
        self.assertEqual(self.join()[0], 200)
        self.assertNotIn((str(self.maps), '.bsp'), self.S._join_names_cache)
        (self.maps / 'surf_test.bsp').rename(self.maps / 'Surf_Test.bsp')
        self.db('DELETE FROM assignments')
        self.assertEqual(self.join()[0], 200)
        self.assertEqual(self.db('SELECT map_dir FROM assignments'), [('Surf_Test',)])
        self.S.maps_reset()
        sig = self.S._join_dir_sig(str(self.maps))
        changed = sig[:2] + (sig[2] + 1,) + sig[3:]
        with patch.object(self.S, '_join_dir_sig', side_effect=[sig, changed]):
            self.assertEqual(self.join()[0], 404)
        self.assertNotIn((str(self.maps), '.bsp'), self.S._join_names_cache)
        self.assertEqual(self.join()[0], 200)

    def test_embedded_invalid_and_read_error(self):
        self.put(body=timer_bsp())
        status, body = self.join()
        self.assertEqual((status, body['timed']), (200, 1))
        self.put(body=b'broken')
        self.assertEqual(self.join()[1]['timed'], 0)
        with patch.object(self.S.zonefit, 'timer_read', return_value=None) as read:
            self.assertEqual(self.join()[1]['timed'], 0)
            self.assertEqual(self.join()[1]['timed'], 0)
            self.assertEqual(read.call_count, 2)  # read errors are not cached
        self.put(body=timer_bsp())
        self.assertEqual(self.join()[1]['timed'], 1)

    def test_explicit_pool_changes_and_unavailable(self):
        self.put()
        self.assertEqual(self.join()[0], 200)
        self.db('INSERT INTO map_pool VALUES (?,0,0)', ('surf_test',))
        self.assertEqual(self.join()[0], 403)
        self.db('UPDATE map_pool SET enabled=1')
        self.assertEqual(self.join()[0], 200)
        import mapmanifest
        with patch.object(mapmanifest, 'disabled', side_effect=sqlite3.OperationalError):
            self.assertEqual(self.join()[0], 503)

    def test_rate_bad_name_occupied_and_reservation_guards(self):
        self.put()
        self.assertEqual(self.join('../bad')[0], 400)
        self.beat(players=1)
        self.assertEqual(self.join()[0], 503)
        self.assertEqual(self.db('SELECT * FROM assignments'), [])
        self.beat(players=0)
        self.assertEqual(self.join()[0], 200)
        self.put('surf_other')
        self.assertEqual(self.join('surf_other')[0], 503)
        self.assertEqual(self.db('SELECT map FROM assignments'), [('surf_test',)])
        statuses = [self.join(src='198.51.100.7')[0] for _ in range(self.S.JOIN_RATE_MAX + 1)]
        self.assertEqual(statuses[-1], 429)
        self.assertTrue(all(status == 200 for status in statuses[:-1]))

    def test_no_global_scan_lock_or_sqlite_write_lock_over_timer_io(self):
        self.put(body=timer_bsp())
        real = self.S.zonefit.timer_read
        def read(path):
            conn = sqlite3.connect(self.S.DB_PATH, timeout=0)
            try:
                with conn:
                    conn.execute('BEGIN IMMEDIATE')
            finally:
                conn.close()
            return real(path)
        self.S._maps_scan_lock.acquire()
        try:
            with patch.object(self.S.zonefit, 'timer_read', side_effect=read):
                with ThreadPoolExecutor(max_workers=1) as pool:
                    self.assertEqual(pool.submit(self.join).result(timeout=3)[0], 200)
        finally:
            self.S._maps_scan_lock.release()

    def test_slow_requested_timer_does_not_block_other_join(self):
        self.put('surf_slow', timer_bsp())
        self.put('surf_fast', zone=0)
        entered, release = threading.Event(), threading.Event()
        real = self.S.zonefit.timer_read
        def read(path):
            entered.set()
            if not release.wait(timeout=5):
                raise AssertionError('timer fixture was not released')
            return real(path)
        with patch.object(self.S.zonefit, 'timer_read', side_effect=read):
            with ThreadPoolExecutor(max_workers=2) as pool:
                slow = pool.submit(self.join, 'surf_slow', '198.51.100.30')
                try:
                    self.assertTrue(entered.wait(timeout=3))
                    fast = pool.submit(self.join, 'surf_fast', '198.51.100.31')
                    self.assertEqual(fast.result(timeout=3)[0], 200)
                finally:
                    release.set()
                self.assertEqual(slow.result(timeout=3)[0], 503)  # fast owns the only idle lobby
                self.assertEqual(self.db('SELECT map FROM assignments'), [('surf_fast',)])

    def test_blocked_other_zone_listing_does_not_block_warm_online_join(self):
        for zone_index in (1, 2):
            with self.subTest(blocked_zone=zone_index):
                self.S.maps_reset()
                self.db('DELETE FROM assignments')
                self.put('surf_fast', zone=0)
                self.put('surf_slow')
                old = time.time() - 10
                for directory in [self.maps] + self.zones:
                    os.utime(directory, (old, old))
                self.assertEqual(self.join('surf_fast')[0], 200)
                entered, release = threading.Event(), threading.Event()
                real = os.scandir
                def scan(path):
                    if path == str(self.zones[zone_index]):
                        entered.set()
                        if not release.wait(timeout=5):
                            raise AssertionError('listing fixture was not released')
                    return real(path)
                with patch.object(self.S.os, 'scandir', side_effect=scan):
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        slow = pool.submit(self.join, 'surf_slow', '198.51.100.40')
                        try:
                            self.assertTrue(entered.wait(timeout=3))
                            fast = pool.submit(self.join, 'surf_fast', '198.51.100.41')
                            self.assertEqual(fast.result(timeout=1)[0], 200)
                            self.assertFalse(release.is_set())
                        finally:
                            release.set()
                        self.assertEqual(slow.result(timeout=3)[0], 503)
                self.assertEqual(self.db('SELECT map FROM assignments'), [('surf_fast',)])

    def test_older_listing_failure_preserves_newer_valid_publication(self):
        self.put('bhop_old', zone=1)
        self.put('bhop_new')
        old = time.time() - 10
        for directory in [self.maps] + self.zones:
            os.utime(directory, (old, old))
        self.assertEqual(self.join('bhop_old')[0], 200)
        self.db('DELETE FROM assignments')
        key = (str(self.zones[1]), '.json')
        stale_publication = self.S._join_names_cache[key]
        (self.zones[1] / 'unrelated.txt').write_text('invalidate directory signature')
        os.utime(self.zones[1], (old, old))
        entered, release = threading.Event(), threading.Event()
        real = os.scandir
        def scan(path):
            if path == str(self.zones[1]) and not entered.is_set():
                entered.set()
                if not release.wait(timeout=5):
                    raise AssertionError('listing fixture was not released')
                raise PermissionError('older fixture listing fails')
            return real(path)
        with patch.object(self.S.os, 'scandir', side_effect=scan):
            with ThreadPoolExecutor(max_workers=2) as pool:
                older = pool.submit(self.join, 'bhop_old', '198.51.100.50')
                try:
                    self.assertTrue(entered.wait(timeout=3))
                    (self.zones[1] / 'bhop_old.json').unlink()
                    (self.zones[1] / 'bhop_new.json').write_text('{}')
                    os.utime(self.zones[1], (old, old))
                    newer = pool.submit(self.join, 'bhop_new', '198.51.100.51')
                    self.assertEqual(newer.result(timeout=1)[0], 200)
                    publication = self.S._join_names_cache[key]
                    self.assertIsNot(publication, stale_publication)
                finally:
                    release.set()
                self.assertEqual(older.result(timeout=3)[0], 403)
        self.assertIs(self.S._join_names_cache[key], publication)
        self.assertEqual(self.join('bhop_old')[0], 403)
        self.assertEqual(self.db('SELECT map FROM assignments'), [('bhop_new',)])

    def test_concurrent_claims_and_cache_invalidation(self):
        self.put('Surf_Test', timer_bsp(), zone=0)
        old = time.time() - 10
        for directory in [self.maps] + self.zones:
            os.utime(directory, (old, old))
        barrier = threading.Barrier(8)
        def ask(i):
            barrier.wait(timeout=5)
            return self.join(src='198.51.100.%d' % (i + 1))
        with patch.object(self.S.os, 'scandir', wraps=os.scandir) as scan:
            with ThreadPoolExecutor(max_workers=8) as pool:
                replies = list(pool.map(ask, range(8)))
            # Cold callers may independently list; no global IO single-flight lock.
            self.assertGreaterEqual(scan.call_count, 2)
            self.assertLessEqual(scan.call_count, 16)
        self.assertEqual([r[0] for r in replies], [200] * 8)
        self.assertEqual(self.db('SELECT map_dir FROM assignments'), [('Surf_Test',)])
        (self.maps / 'Surf_Test.bsp').unlink()
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(lambda _: self.join()[0], range(8))), [404] * 8)

    def test_4000_maps_work_counts(self):
        for i in range(4000):
            self.put('surf_%04d' % i)
        # Quiescent directory: exercise a real cache hit without a wall-clock sleep.
        old = time.time() - 10
        for directory in [self.maps] + self.zones:
            os.utime(directory, (old, old))
        real_scan = os.scandir
        real_timer = self.S.zonefit.timer_read
        with patch.object(self.S.os, 'scandir', wraps=real_scan) as scan, \
                patch.object(self.S.zonefit, 'timer_read', wraps=real_timer) as timer:
            start = time.perf_counter()
            self.assertEqual(self.join('surf_0123')[0], 200)
            cold = time.perf_counter() - start
            cold_scans = scan.call_count
            scan.reset_mock()
            start = time.perf_counter()
            for _ in range(10):
                self.assertEqual(self.join('surf_0123')[0], 200)
            warm = time.perf_counter() - start
            self.assertEqual(scan.call_count, 0)
            self.assertEqual(timer.call_count, 11)
            self.assertEqual({Path(call.args[0]).name for call in timer.call_args_list},
                             {'surf_0123.bsp'})
            print('4000-map route: cold=%.6fs, 10 warm=%.6fs, cold listings=%d, '
                  'warm listings=0, timer reads=11 (requested BSP only)' % (cold, warm, cold_scans))
        # Even the settled cache must notice an addition, case rename and deletion.
        self.put('Surf_0123')
        self.db('DELETE FROM assignments')
        self.assertEqual(self.join('surf_0123')[0], 200)
        self.assertEqual(self.db('SELECT map_dir FROM assignments'), [('Surf_0123',)])
        (self.maps / 'Surf_0123.bsp').unlink()
        (self.maps / 'surf_0123.bsp').unlink()
        self.assertEqual(self.join('surf_0123')[0], 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)
