#!/usr/bin/env python3
"""Act the ordinary12-lobby1s idle traffic through the real heartbeat route."""
import logging
import shutil
import unittest
from test_surfd import fresh, FakeClock


class IdleHeartbeatRate(unittest.TestCase):
    def setUp(self):
        self.m = fresh(trusted='127.0.0.0/8')
        self.clock = FakeClock(1800000000.0)
        self.m.time = self.clock
        self.client = self.m.app.test_client()

    def tearDown(self):
        logging.shutdown()
        shutil.rmtree(self.m._test_home)

    def play(self, seconds=125, source='127.0.0.1'):
        refused = []
        missing = 0
        accepted = set()
        base = self.clock.now
        for second in range(seconds):
            for index in range(12):
                self.clock.now = base + second + index / 20
                port = 27510 + 10 * index
                response = self.client.post('/api/heartbeat', data={
                    'key': 'testkey', 'node': 'idlefixture' + str(index),
                    'map': 'surf_idle_fixture', 'players': '0', 'max': '32',
                    'port': str(port), 'name': 'private synthetic fixture'},
                    environ_base={'REMOTE_ADDR': source})
                if response.status_code == 200:
                    accepted.add(port)
                else:
                    refused.append(response.status_code)
            rows = self.client.get('/lobbies.json').get_json()['lobbies']
            live = {int(x['addr'].rsplit(':', 1)[1]) for x in rows}
            missing += len(accepted - live)
        return refused, missing

    def test_twelve_idle_lobbies_at_one_second_remain_visible(self):
        refused, missing = self.play()
        self.assertEqual(refused, [])
        self.assertEqual(missing, 0)
        self.assertEqual(len(self.client.get('/lobbies.json').get_json()['lobbies']), 12)

    def test_same_traffic_at_original_small_cap_is_discriminating(self):
        self.m.RATE_MAX_TRUSTED = 150
        refused, _ = self.play()
        self.assertIn(429, refused)

    def test_untrusted_source_keeps_original_limit(self):
        self.assertEqual(self.m.RATE_MAX, 150)
        refused, _ = self.play(seconds=20, source='198.51.100.23')
        self.assertIn(429, refused)


if __name__ == '__main__':
    unittest.main()
