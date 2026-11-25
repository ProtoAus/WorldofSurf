#!/usr/bin/env python3
"""Synthetic local filesystem tests; never contacts SSH or a live site."""
import base64
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import publish_site_assets as client
import site_assets_pi as pi
import updatefeed


class PublishSiteAssets(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='site-assets-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'site'
        self.tree = self.root / 'releases/0.1.0'
        self.tree.mkdir(parents=True)
        seed = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
        public = 'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'
        self.seed, self.public = seed, public
        self.payload = dict(game='ftesurf', schema=2, channel='stable', hash_algo='blake2b-256',
                            object_layout='objects/{h0h1}/{hash}', version='0.1.0', removed=[],
                            mirrors=['https://example.invalid/'],
                            files=[dict(path=p, platform='win64', hash='a' * 64, size=1, exec=False)
                                   for p in ('ftesurf64.exe', 'default.fmf', 'ftesurf/menu.dat',
                                             'ftesurf/csprogs.dat', 'ftesurf/qwprogs.dat')],
                            exec_by_platform={'win64': {'cmd': 'ftesurf64.exe', 'args': ['-manifest', 'default.fmf']}})
        updatefeed.validate(self.payload)
        feed = updatefeed.envelope(self.payload, seed, public)
        self.assertEqual(updatefeed.verify(feed, public)['version'], '0.1.0')
        for name, raw in {'index.html': b'<script src="zoning.js"></script>', 'update.json': feed,
                          'update-verified.json': json.dumps({'feed_sha256': pi.sha(feed)}).encode(),
                          'version.json': b'{"version":"0.1.0"}', 'site.js': b'old',
                          'nested/empty.txt': b'', 'objects/ab': b'object bytes'}.items():
            p = self.tree / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        (self.tree / 'empty').mkdir()
        (self.root / 'static').symlink_to('releases/0.1.0')
        self.baseline = pi.info(self.root)
        self.original = pi.inventory(self.tree)
        self.request = dict(mode='publish', ref='a' * 40, baseline=self.baseline,
                            files={'zoning.js': base64.b64encode(b'new zoning').decode()},
                            hashes={'zoning.js': pi.sha(b'new zoning')})
        # Candidates are deliberately read-only, so fixture retirement must restore modes.
        self.addCleanup(self.make_writable)

    def make_writable(self):
        for p in self.root.rglob('*'):
            if p.is_dir() and not p.is_symlink():
                p.chmod(0o755)

    def test_publish_immutable_complete_clone_and_idempotency(self):
        result = pi.publish(self.request, self.root)
        live = self.root / result['target']
        self.assertEqual(os.readlink(self.root / 'static'), result['target'])
        self.assertEqual(pi.inventory(self.tree), self.original)
        after = pi.inventory(live)
        self.assertEqual({n: row for n, row in after.items() if n != 'zoning.js'}, self.original)
        self.assertNotEqual((live / 'objects/ab').stat().st_ino, (self.tree / 'objects/ab').stat().st_ino)
        self.assertEqual(live.stat().st_mode & 0o777, 0o555)
        self.assertEqual((live / 'update.json').stat().st_mode & 0o777, 0o444)
        again = dict(self.request, baseline=pi.info(self.root))
        self.assertTrue(pi.publish(again, self.root)['unchanged'])
        self.assertEqual(len(list((self.root / 'asset-releases').iterdir())), 1)
        with self.assertRaisesRegex(ValueError, 'CAS'):
            pi.publish(self.request, self.root)

    def test_normal_release_predecessor_gate_after_asset_publish(self):
        pi.publish(self.request, self.root)
        incoming = self.root / '.incoming/0.1.1'
        incoming.mkdir(parents=True)
        data = updatefeed.envelope(dict(self.payload, version='0.1.1'), self.seed, self.public)
        (incoming / 'update.json').write_bytes(data)
        (incoming / 'update-verified.json').write_text(json.dumps(dict(
            version='0.1.1', feed_sha256=pi.sha(data), objects=1, verification='r2-roundtrip-blake2b-256')))
        updatefeed.check_publication(incoming / 'update.json', incoming / 'update-verified.json', '0.1.1',
                                     self.root / 'static/update.json', self.baseline['update_sha256'], self.public)
        with self.assertRaisesRegex(ValueError, 'prior feed changed'):
            updatefeed.check_publication(incoming / 'update.json', incoming / 'update-verified.json', '0.1.1',
                                         self.root / 'static/update.json', '0' * 64, self.public)

    def test_unsafe_lock_and_parent_refused(self):
        (self.root / '.publish.lock').symlink_to(self.tree / 'site.js')
        with self.assertRaises(OSError):
            pi.publish(self.request, self.root)
        (self.root / '.publish.lock').unlink()
        (self.root / 'asset-releases').symlink_to(self.tree)
        with self.assertRaises(ValueError):
            pi.publish(self.request, self.root)
        self.assertEqual(pi.info(self.root), self.baseline)

    def test_dry_run_no_filesystem_changes(self):
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*'))
        result = pi.publish(dict(self.request, dry_run=True), self.root)
        self.assertTrue(result['dry_run'])
        self.assertEqual(before, sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*')))
        self.assertFalse((self.root / '.publish.lock').exists())

    def test_lock_contention_actual_second_process(self):
        with (self.root / '.publish.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code = ('import sys,json; from pathlib import Path; import site_assets_pi as p; '
                    'p.publish(json.loads(sys.stdin.read()),Path(sys.argv[1]))')
            done = subprocess.run(['python3', '-B', '-c', code, str(self.root)], cwd=Path(__file__).parent,
                                  input=json.dumps(self.request), text=True, capture_output=True)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn('publication lock busy', done.stderr)
        self.assertEqual(os.readlink(self.root / 'static'), self.baseline['link'])
        self.assertTrue(pi.publish(self.request, self.root)['ok'])

    def test_changed_baseline_and_link_CAS(self):
        for name in ('site.js', 'update.json'):
            p = self.tree / name
            old = p.read_bytes()
            p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'CAS'):
                pi.publish(self.request, self.root)
            p.write_bytes(old)
        other = self.root / 'releases/0.1.1'
        other.mkdir()
        (self.root / 'static').unlink()
        (self.root / 'static').symlink_to('releases/0.1.1')
        with self.assertRaises(ValueError):
            pi.publish(self.request, self.root)

    def test_forced_preswap_failure_retained_and_reusable(self):
        def fail():
            raise RuntimeError('forced pre-swap failure')
        with self.assertRaisesRegex(RuntimeError, 'forced'):
            pi.publish(self.request, self.root, before_swap=fail)
        self.assertEqual(pi.info(self.root), self.baseline)
        self.assertEqual(pi.inventory(self.tree), self.original)
        candidates = list((self.root / 'asset-releases').iterdir())
        self.assertEqual(len(candidates), 1)
        result = pi.publish(self.request, self.root)
        self.assertEqual(self.root / result['target'], candidates[0])

    def test_namespace_refusals(self):
        for link in ('../outside', str(self.tree), 'releases/../../outside', 'asset-releases/.bad', 'releases/1.2.3/extra'):
            (self.root / 'static').unlink()
            (self.root / 'static').symlink_to(link)
            with self.assertRaises(ValueError):
                pi.info(self.root)
        (self.root / 'static').unlink()
        (self.root / 'static').mkdir()
        with self.assertRaises(ValueError):
            pi.info(self.root)

    def test_link_special_and_limit_controls(self):
        bad = self.tree / 'bad'
        bad.symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):
            pi.info(self.root)
        bad.unlink()
        os.link(self.tree / 'site.js', bad)
        with self.assertRaises(ValueError):
            pi.info(self.root)
        bad.unlink()
        os.mkfifo(bad)
        with self.assertRaises(ValueError):
            pi.info(self.root)
        bad.unlink()
        for constant, value in (('MAX_FILE', 2), ('MAX_TOTAL', 2), ('MAX_ENTRIES', 2)):
            with patch.object(pi, constant, value), self.assertRaises(ValueError):
                pi.info(self.root)
        with patch.object(pi, 'MAX_ASSET', 1), self.assertRaises(ValueError):
            pi.publish(self.request, self.root)

    def test_inventory_stops_consuming_at_entry_budget(self):
        flat = Path(self.temp.name) / 'flat'
        flat.mkdir()
        for i in range(20):
            (flat / str(i)).write_bytes(b'x')
        real_scan, consumed = os.scandir, []

        class CountingScan:
            def __init__(self, parent):
                self.entries = real_scan(parent)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.entries.close()
            def __iter__(self):
                return self
            def __next__(self):
                entry = next(self.entries)
                consumed.append(entry.name)
                return entry

        with patch.object(pi.os, 'scandir', CountingScan), patch.object(pi, 'MAX_ENTRIES', 2):
            with self.assertRaisesRegex(ValueError, 'entry limit'):
                pi.inventory(flat)
        self.assertEqual(len(consumed), 3, 'stop at limit plus refusal entry, not whole directory')

    def test_new_candidate_is_nginx_readable_under_restrictive_umask(self):
        old = os.umask(0o077)
        try:
            result = pi.publish(self.request, self.root)
        finally:
            os.umask(old)
        parent = self.root / 'asset-releases'
        self.assertEqual(parent.stat().st_mode & 0o777, 0o755)
        for p in (self.root / result['target'], *(self.root / result['target']).rglob('*')):
            self.assertTrue(p.stat().st_mode & 0o004)
            if p.is_dir():
                self.assertTrue(p.stat().st_mode & 0o001)

    def test_reused_candidate_corruption_and_permissions_refused(self):
        def fail():
            raise RuntimeError('forced pre-swap failure')
        with self.assertRaises(RuntimeError):
            pi.publish(self.request, self.root, before_swap=fail)
        dest = next((self.root / 'asset-releases').iterdir())
        asset = dest / 'site.js'
        asset.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'permissions unsafe'):
            pi.publish(self.request, self.root)
        asset.write_bytes(b'corrupt')
        asset.chmod(0o444)
        with self.assertRaisesRegex(ValueError, 'destination collision'):
            pi.publish(self.request, self.root)
        self.assertEqual(pi.info(self.root), self.baseline)
        self.assertEqual(pi.inventory(self.tree), self.original)

    def test_source_change_during_copy_refused_before_promotion(self):
        original, reads = pi.read_file, []
        path = self.tree / 'site.js'

        def racing_read(p, *args, **kwargs):
            raw = original(p, *args, **kwargs)
            if p == path:
                reads.append(p)
                if len(reads) == 3:  # info, inventory, then the actual clone read
                    path.write_bytes(b'NEW')
            return raw

        with patch.object(pi, 'read_file', racing_read):
            with self.assertRaisesRegex(ValueError, 'CAS'):
                pi.publish(self.request, self.root)
        self.assertEqual(os.readlink(self.root / 'static'), self.baseline['link'])
        self.assertEqual(len(list((self.root / 'asset-releases').iterdir())), 1,
                         'complete but unpromoted candidate retained for inspection')

    def test_payload_refusals(self):
        for name in ('index.html', 'update.json', '../zoning.js', '/site.js', 'version.json', 'objects/a'):
            with self.assertRaises(ValueError):
                pi.publish(dict(self.request, files={name: 'YQ=='}, hashes={name: pi.sha(b'a')}), self.root)
        with self.assertRaises(ValueError):
            pi.publish(dict(self.request, hashes={'zoning.js': '0' * 64}), self.root)
        with self.assertRaises(ValueError):
            pi.publish(dict(self.request, ref='HEAD'), self.root)

    def test_source_uses_git_blobs_not_dirty_tree(self):
        repo = Path(self.temp.name) / 'repo'
        repo.mkdir()
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout
        git('init', '-q')
        p = repo / 'src/release/site/zoning.js'
        p.parent.mkdir(parents=True)
        p.write_bytes(b'committed')
        git('add', 'src/release/site/zoning.js')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
        p.write_bytes(b'dirty')
        got = client.source('HEAD', ['zoning.js'], repo)
        self.assertEqual(base64.b64decode(got['files']['zoning.js']), b'committed')
        for names in (['index.html'], ['zoning.js', 'zoning.js']):
            with self.assertRaises(ValueError):
                client.source('HEAD', names, repo)
        p.unlink()
        p.symlink_to('/etc/passwd')
        git('add', 'src/release/site/zoning.js')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'linked fixture')
        with self.assertRaises(ValueError):
            client.source('HEAD', ['zoning.js'], repo)

    def test_source_ignores_commit_and_blob_replacements(self):
        repo = Path(self.temp.name) / 'replace-repo'
        repo.mkdir()
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout.strip()
        git('init', '-q')
        p = repo / 'src/release/site/zoning.js'
        p.parent.mkdir(parents=True)
        commits, blobs = [], []
        for raw in (b'original pinned bytes', b'replacement bytes'):
            p.write_bytes(raw)
            git('add', 'src/release/site/zoning.js')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
            commits.append(git('rev-parse', 'HEAD').decode())
            blobs.append(git('rev-parse', 'HEAD:src/release/site/zoning.js').decode())
        for old, replacement in (commits, blobs):
            git('replace', old, replacement)
            try:
                got = client.source(commits[0], ['zoning.js'], repo)
                self.assertEqual(got['ref'], commits[0])
                self.assertEqual(base64.b64decode(got['files']['zoning.js']), b'original pinned bytes')
            finally:
                git('replace', '-d', old)


if __name__ == '__main__':
    unittest.main()
