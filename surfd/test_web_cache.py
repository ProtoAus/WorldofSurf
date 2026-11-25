#!/usr/bin/env python3
"""Synthetic controls for public catalogue SWR, availability and bounded search."""
import json
import os
import threading
import time
import unittest
from unittest.mock import patch

from test_web import fresh, get, body, join_rebuilds


class WebCacheTests(unittest.TestCase):
    def setUp(self):
        self.m = fresh()
        self.addCleanup(join_rebuilds)

    def cold(self):
        with self.m._web_lock:
            self.m._web_maps.update(at=None, body=b"", busy=False)

    def test_snapshot_is_public_and_cold_load_does_not_aggregate(self):
        m = self.m
        first = get(m, "/board/api/maps")
        self.assertEqual(first.status_code, 200)
        self.assertTrue(os.path.isfile(m.WEB_MAPS_SNAPSHOT))
        self.cold()
        with patch.object(m, "_web_maps_body", side_effect=AssertionError("aggregate")):
            self.assertEqual(body(get(m, "/board/api/maps")), body(first))
        with open(m.WEB_MAPS_SNAPSHOT) as fh:
            doc = json.load(fh)
        self.assertEqual(set(doc), {"v", "at", "payload"})
        self.assertTrue(m._web_maps_payload(doc["payload"]))

    def test_snapshot_allowlist_and_envelope_validation(self):
        m = self.m
        get(m, "/board/api/maps")
        with open(m.WEB_MAPS_SNAPSHOT) as fh:
            good = json.load(fh)
        mutations = [lambda d: d.update(v=True),
                     lambda d: d.update(at=d["at"] + 1),
                     lambda d: d["payload"].update(player="private"),
                     lambda d: d["payload"]["maps"][0].update(player="private"),
                     lambda d: d["payload"]["maps"][0].update(have=True),
                     lambda d: d["payload"]["maps"][0].update(wr={"name": "test", "ms": 1,
                                                                          "ver": 0, "nonce": 1}),
                     lambda d: d["payload"]["maps"][0].update(map="../bad"),
                     lambda d: d["payload"].update(t=float("nan"))]
        for mutate in mutations:
            doc = json.loads(json.dumps(good))
            mutate(doc)
            with open(m.WEB_MAPS_SNAPSHOT, "w") as fh:
                json.dump(doc, fh)
            self.assertIsNone(m._web_maps_load())
        with open(m.WEB_MAPS_SNAPSHOT, "w") as fh:
            fh.write("{")
        self.assertIsNone(m._web_maps_load())

    def test_stale_snapshot_returns_while_one_refresh_is_blocked(self):
        m = self.m
        first = body(get(m, "/board/api/maps"))
        self.cold()
        m.time.now += 61
        entered, release = threading.Event(), threading.Event()
        original = m._web_maps_body
        calls = []

        def blocked(now, db):
            calls.append(threading.get_ident())
            entered.set()
            self.assertTrue(release.wait(5))
            return original(now, db)

        with patch.object(m, "_web_maps_body", blocked):
            try:
                self.assertEqual(body(get(m, "/board/api/maps")), first)
                self.assertTrue(entered.wait(5))
                for _ in range(4):
                    self.assertEqual(body(get(m, "/board/api/maps")), first)
                self.assertEqual(len(calls), 1)
                self.assertNotEqual(calls[0], threading.get_ident())
            finally:
                release.set()
                join_rebuilds()
        self.assertEqual(body(get(m, "/board/api/maps"))["t"], int(m.time.now))

    def test_no_snapshot_concurrent_cold_requests_build_once(self):
        m = self.m
        entered, release = threading.Event(), threading.Event()
        original = m._web_maps_body
        responses, calls = [], []

        def blocked(now, db):
            calls.append(1)
            entered.set()
            self.assertTrue(release.wait(5))
            return original(now, db)

        with patch.object(m, "_web_maps_body", blocked):
            threads = [threading.Thread(target=lambda: responses.append(get(m, "/board/api/maps")))
                       for _ in range(4)]
            try:
                for thread in threads:
                    thread.start()
                self.assertTrue(entered.wait(5))
            finally:
                release.set()
                for thread in threads:
                    thread.join(10)
        self.assertEqual(calls, [1])
        self.assertEqual([r.status_code for r in responses], [200] * 4)

    def test_failed_background_build_closes_connection_and_retries(self):
        m = self.m
        first = body(get(m, "/board/api/maps"))
        m.time.now += 61
        original = m.connect
        connections = []

        class OwnedConnection:
            def __init__(self):
                self.conn = original()
                self.closed = False

            def close(self):
                self.conn.close()
                self.closed = True

        def opened():
            conn = OwnedConnection()
            connections.append(conn)
            return conn

        with patch.object(m, "connect", opened), patch.object(m, "_web_maps_body", side_effect=RuntimeError("synthetic")):
            self.assertEqual(body(get(m, "/board/api/maps")), first)
            join_rebuilds()
        self.assertFalse(m._web_maps["busy"])
        self.assertEqual(len(connections), 1)
        self.assertTrue(connections[0].closed)
        get(m, "/board/api/maps")
        join_rebuilds()
        self.assertEqual(m._web_maps["at"], int(m.time.now))

    def test_connection_open_failure_and_thread_start_failure_retry(self):
        m = self.m
        get(m, "/board/api/maps")
        m.time.now += 61
        with patch.object(m, "connect", side_effect=RuntimeError("synthetic open")):
            self.assertEqual(get(m, "/board/api/maps").status_code, 200)
            join_rebuilds()
        self.assertFalse(m._web_maps["busy"])
        with patch.object(m.threading.Thread, "start", side_effect=RuntimeError("synthetic start")):
            self.assertEqual(get(m, "/board/api/maps").status_code, 200)
        self.assertFalse(m._web_maps["busy"])
        get(m, "/board/api/maps")
        join_rebuilds()
        self.assertEqual(m._web_maps["at"], int(m.time.now))

    def test_cold_failure_retries_and_clock_rollback_is_stale(self):
        m = self.m
        with patch.object(m, "_web_maps_body", side_effect=RuntimeError("synthetic cold")):
            self.assertEqual(get(m, "/board/api/maps").status_code, 500)
        self.assertEqual(get(m, "/board/api/maps").status_code, 200)
        m.time.now -= 3600
        get(m, "/board/api/maps")
        join_rebuilds()
        self.assertEqual(m._web_maps["at"], int(m.time.now))

    def test_failed_atomic_save_preserves_last_good_and_cleans_temp(self):
        m = self.m
        get(m, "/board/api/maps")
        with open(m.WEB_MAPS_SNAPSHOT, "rb") as fh:
            saved = fh.read()
        m.time.now += 61
        with patch.object(m.os, "replace", side_effect=OSError("synthetic replace")):
            get(m, "/board/api/maps")
            join_rebuilds()
        with open(m.WEB_MAPS_SNAPSHOT, "rb") as fh:
            self.assertEqual(fh.read(), saved)
        self.assertFalse(any(name.startswith("web_maps.json.") for name in os.listdir(m.DATA_DIR)))
        self.assertEqual(m._web_maps["at"], int(m.time.now))

    def test_availability_projects_public_names_without_request_thread_scan(self):
        m = self.m
        catalogue = body(get(m, "/board/api/maps"))
        catalogue["maps"][0].update(map="Surf_Case", have=0)
        m._web_maps_install(catalogue["t"], json.dumps(catalogue).encode())
        m._maps_cache["at"] = -1e9  # real index cold; no map_index stub hides the scan path
        with patch.object(m, "_scan_maps", side_effect=AssertionError("scan")) as scan, \
                patch.object(m.zonefit, "timer_read", side_effect=AssertionError("BSP read")) as read, \
                patch.object(m, "get_db", side_effect=AssertionError("DB")) as db:
            response = get(m, "/board/api/availability")
            scan.assert_not_called()
            read.assert_not_called()
            db.assert_not_called()
        expected = [{"map": row["map"], "have": row["have"]} for row in catalogue["maps"]]
        self.assertEqual(body(response), {"v": 1, "t": catalogue["t"], "maps": expected})
        self.assertIn({"map": "Surf_Case", "have": 0}, expected)
        self.assertEqual(response.headers["Cache-Control"], "max-age=60")
        self.assertEqual(response.headers["Content-Security-Policy"], m.WEB_CSP)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(get(m, "/board/api/availability", method="POST").status_code, 405)
        with patch.object(m, "rate_ok", return_value=False) as rate, \
                patch.object(m, "_web_availability_current", side_effect=AssertionError("work")) as work:
            self.assertEqual(get(m, "/board/api/availability").status_code, 429)
            self.assertEqual(rate.call_args.args[2:], (m.WEB_RATE_MAX, "web"))
            work.assert_not_called()

    def test_no_snapshot_availability_never_waits_behind_real_cold_index(self):
        m = self.m
        entered, release = threading.Event(), threading.Event()
        original = m._scan_maps
        scan_threads, read_threads = [], []
        real_read = m.zonefit.timer_read

        def blocked_scan():
            scan_threads.append(threading.get_ident())
            entered.set()
            if not release.wait(5):
                raise RuntimeError("synthetic scan timeout")
            return original()

        def record_read(*args, **kwargs):
            read_threads.append(threading.get_ident())
            return real_read(*args, **kwargs)

        with patch.object(m, "_scan_maps", blocked_scan), patch.object(m.zonefit, "timer_read", record_read):
            try:
                started = time.monotonic()
                response = get(m, "/board/api/availability")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertLess(time.monotonic() - started, 1)
                self.assertTrue(entered.wait(5))
                started = time.monotonic()
                self.assertEqual(get(m, "/board/api/availability").status_code, 503)
                self.assertLess(time.monotonic() - started, 1)
            finally:
                release.set()
                join_rebuilds()
        self.assertTrue(scan_threads)
        self.assertTrue(read_threads, "exercise actual cold zone-less BSP timer path")
        self.assertNotIn(threading.get_ident(), scan_threads + read_threads)
        self.assertEqual(get(m, "/board/api/availability").status_code, 200)

    def test_search_preserves_total_order_and_cap_without_empty_search_iteration(self):
        m = self.m
        rows = [dict(who=str(i), name="synthetic", key="match", n=i, maps=1,
                     last=0, src="ranked", ranked=1, mom=0, ksf=0) for i in range(125)]

        class NoIteration(list):
            def __iter__(self):
                raise AssertionError("empty query copied full list")

        with patch.object(m, "web_people", return_value=({}, NoIteration(rows))), \
                patch.object(m, "avatars", return_value={"handle": {}}):
            result = body(get(m, "/board/api/players"))
            self.assertEqual(result["n"], 125)
            self.assertEqual([r["who"] for r in result["players"]], [str(i) for i in range(60)])
        with patch.object(m, "web_people", return_value=({}, rows)), \
                patch.object(m, "avatars", return_value={"handle": {}}):
            result = body(get(m, "/board/api/players?q=match"))
            self.assertEqual(result["n"], 125)
            self.assertEqual(len(result["players"]), 60)
            self.assertEqual(result["players"][-1]["who"], "59")

    def test_import_never_starts_cache_threads(self):
        with patch.object(threading.Thread, "start", side_effect=AssertionError("import thread")):
            m = fresh()
        self.assertIsNone(m._web_maps["at"])
        self.assertLess(m._people["at"], 0)

    def test_warm_hook_start_failure_releases_both_guards(self):
        m = self.m
        with patch.object(threading.Thread, "start", side_effect=RuntimeError("synthetic warm start")):
            m.warm_web_cache()
        self.assertFalse(m._web_maps["busy"])
        self.assertFalse(m._web_warm_lock.locked())
        m.warm_web_cache()
        join_rebuilds()
        self.assertEqual(m._web_maps["at"], int(m.time.now))
        self.assertTrue(os.path.exists(m.PEOPLE_SNAPSHOT))

    def test_warm_hook_is_explicit_and_builds_both_caches(self):
        m = self.m
        self.assertIsNone(m._web_maps["at"])
        self.assertFalse(os.path.exists(m.PEOPLE_SNAPSHOT))
        m.warm_web_cache()
        join_rebuilds()
        self.assertEqual(m._web_maps["at"], int(m.time.now))
        self.assertTrue(os.path.exists(m.WEB_MAPS_SNAPSHOT))
        self.assertTrue(os.path.exists(m.PEOPLE_SNAPSHOT))
        with patch.object(m, "_web_maps_body", side_effect=AssertionError("aggregate")) as maps, \
                patch.object(m, "_people_build", side_effect=AssertionError("people build")) as people:
            m.warm_web_cache()
            join_rebuilds()
            maps.assert_not_called()
            people.assert_not_called()

    def test_startup_load_only_restores_files_without_threads_sql_or_builders(self):
        m = self.m
        m.warm_web_cache()
        join_rebuilds()
        self.cold()
        with m._people_lock:
            m._people["at"] = -1e9
            m._people["by_handle"], m._people["list"] = {}, []
        m.time.now += 3600     # even stale files must not refresh while admission is CLOSED
        with patch.object(m, "connect", side_effect=AssertionError("SQL")) as db, \
                patch.object(m.threading.Thread, "start", side_effect=AssertionError("thread")) as start, \
                patch.object(m, "_web_maps_body", side_effect=AssertionError("aggregate")) as maps, \
                patch.object(m, "_people_build", side_effect=AssertionError("people build")) as people:
            m.warm_web_cache(load_only=True)
            m.warm_web_cache(load_only=True)
            for forbidden in (db, start, maps, people):
                forbidden.assert_not_called()
        self.assertIsNotNone(m._web_maps["at"])
        self.assertGreaterEqual(m._people["at"], 0)
        self.assertFalse(m._web_maps["busy"])

    def test_startup_missing_optional_snapshots_preserves_later_retry(self):
        m = self.m
        with patch.object(m, "connect", side_effect=AssertionError("SQL")) as db, \
                patch.object(m.threading.Thread, "start", side_effect=AssertionError("thread")) as start:
            m.warm_web_cache(load_only=True)
            db.assert_not_called()
            start.assert_not_called()
        self.assertIsNone(m._web_maps["at"])
        self.assertLess(m._people["at"], 0)
        self.assertEqual(get(m, "/board/api/maps").status_code, 200)

    def test_overflowing_optional_people_stamp_does_not_break_worker_startup(self):
        m = self.m
        with open(m.PEOPLE_SNAPSHOT, "w") as fh:
            fh.write('{"v":1,"at":1e999,"players":{},"list":[],"main_maps":[]}')
        with patch.object(m, "connect", side_effect=AssertionError("SQL")) as db, \
                patch.object(m.threading.Thread, "start", side_effect=AssertionError("thread")) as start:
            m.warm_web_cache(load_only=True)
            self.assertLess(m._people["at"], 0)
            with open(m.PEOPLE_SNAPSHOT, "w") as fh:
                json.dump({"v": 1, "at": int(m.time.now), "players": {}, "list": [], "main_maps": []}, fh)
            m.warm_web_cache(load_only=True)
            self.assertEqual(m._people["at"], int(m.time.now))
            db.assert_not_called()
            start.assert_not_called()

    def test_avatar_startup_owns_reader_and_preserves_failure_retry(self):
        m = self.m
        from unittest.mock import Mock
        for error in (None, RuntimeError("synthetic pictures")):
            conn = Mock()
            with patch.object(m, "connect", return_value=conn) as opened, \
                    patch.object(m, "avatars", side_effect=error, return_value={}) as pictures:
                m.warm_web_avatars()
                opened.assert_called_once_with()
                pictures.assert_called_once_with(int(m.time.now), db=conn)
                conn.close.assert_called_once_with()
        with patch.object(m, "connect", side_effect=RuntimeError("synthetic open")):
            m.warm_web_avatars()


if __name__ == "__main__":
    unittest.main()
