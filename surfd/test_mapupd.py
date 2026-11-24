#!/usr/bin/env python3
"""P1746 map upload service: the whole flow with a real Ed25519 proof, and each refusal leaving nothing behind."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock
import fcntl
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
os.environ['SURFD_TAS_CONTENT_LEASE'] = ''      # zonepub_publish: no lease file in a test
import ed25519
import mapmanifest
import mapupd as M

SEED = bytes(range(32))
PUB = ed25519.publickey(SEED).hex()
SID = '76561198000000001'


def vbsp(version=20, extra=b''):
    return b'VBSP' + version.to_bytes(4, 'little') + bytes(64 * 16) + (1).to_bytes(4, 'little') + extra


def png(w=640, h=360):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (w, h), (30, 120, 200)).save(buf, 'PNG')
    return buf.getvalue()


def zone(height=64):
    r = dict(points=[[0, 0], [32, 0], [32, 32], [0, 32]], bottom=0, height=height)
    return json.dumps(dict(formatVersion=1, tracks=dict(main=dict(zones=dict(
        segments=[dict(checkpoints=[dict(regions=[r])])], end=dict(regions=[r])))))).encode()


def sha(b): return hashlib.sha256(b).hexdigest()


def manifest(name, bsp, shot=None, zonebody=None, mode='surf', tier=3, stages=0, bonuses=1, author='Proto'):
    f = lambda b, ext=None: '-' if b is None else ('%s %d' % (sha(b), len(b)) + (' ' + ext if ext else ''))
    return ('FTESURF-MAPUP 1\nmap %s\nbsp %s\nshot %s\nzone %s\nmode %s\ntier %d\nstages %d\nbonuses %d\nlinear %d\n'
            'author %s\n') % (name, f(bsp), f(shot, 'png'), f(zonebody), mode, tier, stages, bonuses,
                              1 if stages == 0 else 0, author or '-')


META_HEAD = 'FTESURF-MAPMETA 1\n# stamp 20261117020745\n# atlas 0 1\n'


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.store, self.maps, self.media = t / 'state', t / 'maps', t / 'media'
        self.zones = [t / 'zl', t / 'zs']
        for d in [self.maps, self.media] + self.zones: d.mkdir()
        self.lock = t / 'publish.lock'                  # zonepub's, beside its store
        self.lock.write_bytes(b'')
        os.environ['MAPUPD_ZONEPUB_LOCK'] = str(self.lock)
        M.initialize(self.store)
        self.main = t / 'surfd.db'
        with sqlite3.connect(self.main) as db:
            db.executescript('CREATE TABLE accounts(steamid TEXT PRIMARY KEY, banned_at INTEGER);'
                             'CREATE TABLE keylinks(pub TEXT, steamid TEXT);')
            db.execute('INSERT INTO accounts VALUES(?,0)', (SID,))
            db.execute('INSERT INTO keylinks VALUES(?,?)', (PUB, SID))
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            db.execute('INSERT INTO roles VALUES(?)', (SID,))
        (self.maps / 'surf_old.bsp').write_bytes(vbsp())
        self.list = t / 'mapdl.txt'
        self.list.write_text('FTESURF-MAPDL 1\n# written by surfd/mapwatch.py\ndl surf_old surf m 2 10 2026-01-01 0 2 0\n')
        (self.media / 'mapmeta.txt').write_text(META_HEAD + 'meta surf_old 2 1 0 0 - - - 1 rank - - - -\n'
                                                'variant surf_old surf_old_css\n# end 1\n')
        self.now = 1_800_000_000
        self.app = M.create_app(self.store, self.main, self.maps, self.zones, self.media, self.list,
                                clock=lambda: self.now, verify=ed25519.verify, free_bytes=lambda: 1 << 40)
        self.c = self.app.test_client()

    def tearDown(self):
        os.environ.pop('MAPUPD_ZONEPUB_LOCK', None)
        self.tmp.cleanup()

    def post(self, path, **kw):
        r = self.c.post('/mapup/api/' + path, **kw)
        self.assertEqual(r.status_code, 200)
        return r.json

    def begin(self, text, seed=SEED, nonce=None):
        msha = sha(text.encode())
        if nonce is None:
            nonce = self.post('challenge', json=dict(manifest=msha))['nonce']
        sig = ed25519.sign(seed, (M.STATEMENT % (M.SITE, nonce, msha)).encode()).hex()
        body = text + 'nonce %s\npub %s\nsig %s\n' % (nonce, ed25519.publickey(seed).hex(), sig)
        return self.post('begin', data=body.encode()), nonce

    def part(self, token, which, body, enc='raw'):
        data = gzip.compress(body) if enc == 'gzip' else body
        return self.post('part?s=%s&p=%s&e=%s' % (token, which, enc), data=data)

    def finish(self, token):
        return self.post('finish', data=('session %s\n' % token).encode())

    def upload(self, name, bsp=None, z=None, shot=None, mode=None):
        """begin, every part, finish: (begin's answer, finish's answer)."""
        bsp = bsp if bsp is not None else vbsp()
        b, _ = self.begin(manifest(name, bsp, shot, z, mode=mode or name.split('_')[0]))
        self.assertEqual(b['ok'], 1, b)
        for which, body in (('bsp', bsp), ('shot', shot), ('zone', z)):
            if body is not None:
                self.assertEqual(self.part(b['session'], which, body)['ok'], 1)
        return b, self.finish(b['session'])

    def remove(self, name, zone_dirs=None, store=None):
        """`remove` as an operator runs it: what it printed."""
        argv = ['mapupd.py', '--store', str(store or self.store), 'remove', '--map', name, '--maps', str(self.maps),
                '--media', str(self.media), '--list', str(self.list)] + sum(
                    (['--zone-dir', str(d)] for d in (self.zones if zone_dirs is None else zone_dirs)), [])
        return self.cli(argv)

    def cli(self, argv):
        """What a command printed; its exit status in self.rc, what it said on stderr in self.err."""
        old, sys.argv = sys.argv, argv
        out, err = io.StringIO(), io.StringIO()
        self.rc = 0
        try:
            with mock.patch('sys.stdout', out), mock.patch('sys.stderr', err):
                M.main()
        except SystemExit as e:
            self.rc = e.code
        finally:
            sys.argv = old
        self.err = err.getvalue()
        return out.getvalue()

    def zonepub(self, *rows):
        """zonepub's store beside its lock, with publications (map, at[, kind, live]): zonepub_publish's columns."""
        with sqlite3.connect(self.lock.with_name('zones.sqlite3')) as z:
            z.execute('CREATE TABLE IF NOT EXISTS publications(id INTEGER PRIMARY KEY, map TEXT, at INTEGER, kind TEXT, '
                      'live INTEGER)')
            for r in rows:
                name, at, kind, live = (tuple(r) + ('noop', None))[:4]
                z.execute('INSERT INTO publications(map, at, kind, live) VALUES(?,?,?,?)', (name, at, kind, live))

    def record(self, name):
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            r = db.execute('SELECT sha, aside FROM upload_zones WHERE map=?', (name,)).fetchone()
        return (r[0], json.loads(r[1])) if r else None

    def stamp(self, name):
        """Each zone file's identity: a rewrite changes it, even with the same bytes."""
        return [(d / (name + '.json')).stat()[1:] if (d / (name + '.json')).exists() else None for d in self.zones]

    def aside(self):
        return sorted(p.name for p in (self.store / M.ASIDE).iterdir())

    def test_publishes_everything(self):
        bsp, shot, z = vbsp(extra=b'x' * 5000), png(), zone()
        b, _ = self.begin(manifest('surf_newmap', bsp, shot, z, tier=4, stages=6, bonuses=2, author="Mark B'54"))
        self.assertEqual(b['ok'], 1, b)
        self.assertEqual(b['need'], 'bsp shot zone')
        tok = b['session']
        self.assertEqual(self.part(tok, 'bsp', bsp, 'gzip')['left'], 'shot zone')
        self.assertEqual(self.part(tok, 'shot', shot)['left'], 'zone')
        self.assertEqual(self.part(tok, 'zone', z)['left'], '')
        f = self.finish(tok)
        self.assertEqual(f['ok'], 1, f)
        self.assertEqual((self.maps / 'surf_newmap.bsp').read_bytes(), bsp)
        self.assertEqual(oct((self.maps / 'surf_newmap.bsp').stat().st_mode & 0o777), '0o644')
        for d in self.zones:
            self.assertEqual((d / 'surf_newmap.json').read_bytes(), z)
        self.assertTrue((self.media / 'uploads' / 'surf_newmap.jpg').is_file())
        self.assertTrue((self.media / 'uploads' / 'surf_newmap-thumb.jpg').is_file())
        rows = {r['map']: r for r in mapmanifest.read_list(self.list)}
        self.assertEqual((rows['surf_newmap']['mode'], rows['surf_newmap']['tier'], rows['surf_newmap']['mt']), ('surf', 4, 4))
        meta = (self.media / 'mapmeta.txt').read_text().split('\n')
        self.assertIn('meta surf_newmap 4 0 6 2 - - - 1 upload - Mark_B.2754 - -', meta)
        self.assertIn('# end 2', meta)
        self.assertNotIn('# stamp 20261117020745', meta)
        self.assertEqual(list((self.store / 'spool').iterdir()), [])
        # a second upload of the same name is refused before any file moves
        b2, _ = self.begin(manifest('surf_newmap', bsp))
        self.assertEqual(b2['ok'], 0)
        self.assertIn('already in the library', b2['error'])

    def test_heal_puts_rows_back(self):
        bsp = vbsp()
        tok = self.begin(manifest('surf_healed', bsp))[0]['session']
        self.part(tok, 'bsp', bsp)
        self.assertEqual(self.finish(tok)['ok'], 1)
        # mapwatch and mapmedia rewrite their files without the rows
        self.list.write_text('FTESURF-MAPDL 1\ndl surf_old surf m 2 10 2026-01-01 0 2 0\n')
        (self.media / 'mapmeta.txt').write_text(META_HEAD + 'meta surf_old 2 1 0 0 - - - 1 rank - - - -\n# end 1\n')
        self.assertEqual(self.app.config['MAPUPD_HEAL'](), (1, 1))
        self.assertIn('surf_healed', {r['map'] for r in mapmanifest.read_list(self.list)})
        self.assertIn('# end 2', (self.media / 'mapmeta.txt').read_text())
        self.assertEqual(self.app.config['MAPUPD_HEAL'](), (0, 0))   # present: left alone

    def test_heal_never_writes_a_list_the_reader_refuses(self):
        self.list.write_text('FTESURF-MAPDL 1\ndl BAD ROW\n')
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            db.execute("INSERT INTO uploads VALUES('surf_x',?,1,?,1,'surf',0,0,0,'',0,0)", (SID, '0' * 64))
        (self.maps / 'surf_x.bsp').write_bytes(vbsp())
        self.assertEqual(self.app.config['MAPUPD_HEAL'](), (0, 1))
        self.assertEqual(self.list.read_text(), 'FTESURF-MAPDL 1\ndl BAD ROW\n')

    def test_no_role(self):
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            db.execute('DELETE FROM roles')
        b, _ = self.begin(manifest('surf_norole', vbsp()))
        self.assertEqual(b['ok'], 0)
        self.assertIn('not a map uploader', b['error'])

    def test_unlinked_and_banned(self):
        b, _ = self.begin(manifest('surf_stranger', vbsp()), seed=bytes(range(1, 33)))
        self.assertIn('Link your Steam account', b['error'])
        with sqlite3.connect(self.main) as db:
            db.execute('UPDATE accounts SET banned_at=1')
        b, _ = self.begin(manifest('surf_banned', vbsp()))
        self.assertIn('cannot upload', b['error'])

    def test_forged_and_reused_proofs(self):
        text = manifest('surf_proof', vbsp())
        msha = sha(text.encode())
        nonce = self.post('challenge', json=dict(manifest=msha))['nonce']
        sig = ed25519.sign(SEED, (M.STATEMENT % (M.SITE, nonce, sha(b'other'))).encode()).hex()
        r = self.post('begin', data=(text + 'nonce %s\npub %s\nsig %s\n' % (nonce, PUB, sig)).encode())
        self.assertIn('did not check out', r['error'])
        ok, nonce = self.begin(text)
        self.assertEqual(ok['ok'], 1)
        again, _ = self.begin(text, nonce=nonce)
        self.assertIn('was used', again['error'])
        # a code for one manifest does not cover another
        other = manifest('surf_proof2', vbsp())
        r2, _ = self.begin(other, nonce=nonce)
        self.assertIn('not for these files', r2['error'])

    def test_expired_code(self):
        text = manifest('surf_late', vbsp())
        nonce = self.post('challenge', json=dict(manifest=sha(text.encode())))['nonce']
        self.now += M.CODE_TTL + 1
        b, _ = self.begin(text, nonce=nonce)
        self.assertIn('expired', b['error'])

    def test_wrong_bytes_and_gzip_overflow(self):
        bsp = vbsp()
        tok = self.begin(manifest('surf_bytes', bsp))[0]['session']
        r = self.part(tok, 'bsp', vbsp(version=21))     # same size, other bytes
        self.assertIn('not the one confirmed', r['error'])
        r = self.part(tok, 'bsp', bsp + bytes(100000), 'gzip')
        self.assertIn('larger than the one confirmed', r['error'])
        self.assertEqual(list((self.store / 'spool').iterdir()), [])
        f = self.finish(tok)
        self.assertIn('Not every file', f['error'])
        self.assertFalse((self.maps / 'surf_bytes.bsp').exists())

    def test_bad_bsp_is_not_published(self):
        bad = b'VBSP' + (20).to_bytes(4, 'little') + (2000).to_bytes(4, 'little') + (99).to_bytes(4, 'little') + bytes(1020)
        tok = self.begin(manifest('surf_cut', bad))[0]['session']
        self.part(tok, 'bsp', bad)
        f = self.finish(tok)
        self.assertIn('cut short', f['error'])
        self.assertFalse((self.maps / 'surf_cut.bsp').exists())
        self.assertNotIn('surf_cut', self.list.read_text())

    def test_strata_v25_and_unknown_versions(self):
        ok, bad = vbsp(version=25), vbsp(version=22)
        tok = self.begin(manifest('surf_strata', ok))[0]['session']
        self.part(tok, 'bsp', ok)
        self.assertEqual(self.finish(tok)['ok'], 1)
        tok = self.begin(manifest('surf_v22', bad))[0]['session']
        self.part(tok, 'bsp', bad)
        self.assertIn('not one the game loads', self.finish(tok)['error'])

    def test_manifest_rules(self):
        for text, why in ((manifest('kz_map', vbsp()), 'surf_ or bhop_'),
                          (manifest('surf_mode', vbsp(), mode='bhop', zonebody=zone()), "name's own"),
                          (manifest('surf_tier', vbsp(), tier=11), 'out of range')):
            b, _ = self.begin(text)
            self.assertEqual(b['ok'], 0, text)
            self.assertIn(why, b['error'])

    def test_heal_skips_a_map_taken_out(self):
        bsp = vbsp()
        tok = self.begin(manifest('surf_gone', bsp))[0]['session']
        self.part(tok, 'bsp', bsp)
        self.assertEqual(self.finish(tok)['ok'], 1)
        (self.maps / 'surf_gone.bsp').unlink()
        self.list.write_text('FTESURF-MAPDL 1\ndl surf_old surf m 2 10 2026-01-01 0 2 0\n')
        self.assertEqual(self.app.config['MAPUPD_HEAL'](), (0, 0))
        self.assertNotIn('surf_gone', self.list.read_text())

    def test_big_bodies_refused_unread(self):
        r = self.c.post('/mapup/api/begin', data=b'x' * (M.SMALL_BODY + 1))
        self.assertEqual(r.json['status'], 413)
        r = self.c.post('/mapup/api/challenge', data=b'x' * (M.SMALL_BODY + 1))
        self.assertEqual(r.json['status'], 413)

    def test_a_retry_replaces_the_failed_attempt(self):
        bsp = vbsp()
        first = self.begin(manifest('surf_retry', bsp))[0]['session']
        self.part(first, 'bsp', vbsp(version=21))       # refused: other bytes
        for _ in range(4):                              # more than the three-open limit
            second = self.begin(manifest('surf_retry', bsp))[0]
            self.assertEqual(second['ok'], 1, second)
        self.assertIn('expired', self.part(first, 'bsp', bsp)['error'])
        self.part(second['session'], 'bsp', bsp)
        self.assertEqual(self.finish(second['session'])['ok'], 1)

    def test_role_revoked_before_finish(self):
        bsp = vbsp()
        tok = self.begin(manifest('surf_revoked', bsp))[0]['session']
        self.part(tok, 'bsp', bsp)
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            db.execute('DELETE FROM roles')
        self.assertIn('not a map uploader', self.finish(tok)['error'])
        self.assertFalse((self.maps / 'surf_revoked.bsp').exists())

    def test_names_held_elsewhere(self):
        with open(self.list, 'a') as f:
            f.write('dl surf_listed surf m 0 10 2026-01-01 0 0 0\n')
        self.assertIn('map list', self.begin(manifest('surf_listed', vbsp()))[0]['error'])
        self.assertIn('already in the library', self.begin(manifest('SURF_OLD'.lower(), vbsp()))[0]['error'])

    def test_disk_floor_and_daily_limit(self):
        low = M.create_app(self.store, self.main, self.maps, self.zones, self.media, self.list,
                           clock=lambda: self.now, verify=ed25519.verify, free_bytes=lambda: 1 << 30).test_client()
        text = manifest('surf_floor', vbsp())
        nonce = low.post('/mapup/api/challenge', json=dict(manifest=sha(text.encode()))).json['nonce']
        sig = ed25519.sign(SEED, (M.STATEMENT % (M.SITE, nonce, sha(text.encode()))).encode()).hex()
        r = low.post('/mapup/api/begin', data=(text + 'nonce %s\npub %s\nsig %s\n' % (nonce, PUB, sig)).encode()).json
        self.assertIn('short of disk', r['error'])
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            for i in range(M.DAY_UPLOADS):
                db.execute("INSERT INTO uploads VALUES(?,?,?,?,1,'surf',0,0,0,'',0,0)", ('surf_d%d' % i, SID, self.now, '0' * 64))
        self.assertIn("today's limit", self.begin(manifest('surf_daily', vbsp()))[0]['error'])

    def test_remove_takes_an_upload_back(self):
        bsp = vbsp()
        tok = self.begin(manifest('surf_takeback', bsp, zonebody=zone()))[0]['session']
        self.part(tok, 'bsp', bsp)
        self.part(tok, 'zone', zone())
        self.assertEqual(self.finish(tok)['ok'], 1)
        argv = ['mapupd.py', '--store', str(self.store), 'remove', '--map', 'surf_takeback', '--maps', str(self.maps),
                '--media', str(self.media), '--list', str(self.list)] + sum((['--zone-dir', str(d)] for d in self.zones), [])
        old, sys.argv = sys.argv, argv
        try:
            M.main()
        finally:
            sys.argv = old
        self.assertFalse((self.maps / 'surf_takeback.bsp').exists())
        self.assertTrue(any((self.maps / '.old').iterdir()))
        self.assertFalse(any((d / 'surf_takeback.json').exists() for d in self.zones))
        self.assertNotIn('surf_takeback', self.list.read_text())
        meta = (self.media / 'mapmeta.txt').read_text()
        self.assertNotIn('surf_takeback', meta)
        self.assertIn('# end 1', meta)
        mapmanifest.read_list(self.list)
        self.assertEqual(self.app.config['MAPUPD_HEAL'](), (0, 0))

    def test_health(self):
        self.assertEqual(self.post('health', json={}), {'ok': 1, 'accounts': 1})

    def test_data_after_the_gzip_stream(self):
        bsp = vbsp()
        tok = self.begin(manifest('surf_trail', bsp))[0]['session']
        r = self.post('part?s=%s&p=bsp&e=gzip' % tok, data=gzip.compress(bsp) + b'junk' * 1000)
        self.assertIn('data after its end', r['error'])
        self.assertEqual(self.part(tok, 'bsp', bsp, 'gzip')['left'], '')

    def test_zone_names_in_other_lobby_dirs(self):
        # P1799: zones in a directory a lobby reads (Momentum's online ones here) no longer hold the name; they are
        # said, and never written or moved: only zonepub's two directories are
        other = Path(self.tmp.name) / 'online'
        other.mkdir()
        (other / 'surf_elsewhere.json').write_bytes(zone())
        self.app = M.create_app(self.store, self.main, self.maps, self.zones, self.media, self.list,
                                clock=lambda: self.now, verify=ed25519.verify, free_bytes=lambda: 1 << 40,
                                zone_check=self.zones + [other])
        self.c = self.app.test_client()
        b, f = self.upload('surf_elsewhere')
        self.assertEqual(b['zones'], 1)
        self.assertIn('they stay as they are', b['note'])
        self.assertEqual(f['ok'], 1, f)
        self.assertIn('uses the zones already on the server', f['note'])
        self.assertEqual((other / 'surf_elsewhere.json').read_bytes(), zone())
        self.assertFalse(any((d / 'surf_elsewhere.json').exists() for d in self.zones))
        b, f = self.upload('surf_elsewhere2', z=zone(96))
        self.assertEqual(b['zones'], 0)
        self.assertEqual(b['note'], '')
        self.assertEqual(self.aside(), [])

    # ---- P1799: zones optional, and zones already on the server -------------------------------------------------
    def test_bhop_without_zones_is_accepted(self):
        b, f = self.upload('bhop_nozone', mode='bhop')
        self.assertEqual((b['need'], b['zones'], b['note']), ('bsp', 0, ''))
        self.assertEqual(f['ok'], 1, f)
        self.assertIn('has no zone file: runs on it can only be timed if the map has its own zone triggers', f['note'])
        self.assertTrue((self.maps / 'bhop_nozone.bsp').is_file())
        self.assertEqual({r['map']: r['mode'] for r in mapmanifest.read_list(self.list)}['bhop_nozone'], 'bhop')
        self.assertFalse(any((d / 'bhop_nozone.json').exists() for d in self.zones))
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            self.assertEqual(db.execute("SELECT zone FROM uploads WHERE map='bhop_nozone'").fetchone(), (0,))
        self.assertEqual(self.record('bhop_nozone'), ('', []))

    def test_a_name_with_published_zones_is_accepted(self):
        # Lex's bhop_uncanny: zone_edit's Publish (zonepub) wrote both zone directories before the map existed;
        # zonepub writes nothing else (no list row, no table row), and the name was refused
        for d in self.zones:
            (d / 'bhop_uncanny.json').write_bytes(zone())
        b, f = self.upload('bhop_uncanny')
        self.assertEqual(b['zones'], 1)
        self.assertIn('bhop_uncanny already has zones on the server', b['note'])
        self.assertEqual(f['ok'], 1, f)
        for d in self.zones:
            self.assertEqual((d / 'bhop_uncanny.json').read_bytes(), zone())
        # the BSP still holds the name: a second upload is refused
        b2, _ = self.begin(manifest('bhop_uncanny', vbsp(), mode='bhop'))
        self.assertIn('already in the library', b2['error'])

    def test_attached_zones_replace_the_old_and_keep_them(self):
        old, new = zone(), zone(128)
        for d in self.zones:
            (d / 'bhop_swap.json').write_bytes(old)
        b, f = self.upload('bhop_swap', z=new)
        self.assertEqual(b['zones'], 1)
        self.assertIn('Your zone file replaces the copies in', b['note'])
        self.assertNotIn('still wins', b['note'])
        self.assertEqual(f['ok'], 1, f)
        self.assertIn('replaced the ones already on the server; those are kept in the upload service', f['note'])
        self.assertNotIn('Proto can', f['note'])
        for d in self.zones:
            self.assertEqual((d / 'bhop_swap.json').read_bytes(), new)
        kept = self.aside()
        self.assertEqual(len(kept), 2)
        for k in kept:
            self.assertTrue(k.startswith('bhop_swap.replaced-'))
            self.assertEqual((self.store / M.ASIDE / k).read_bytes(), old)
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            sha_, aside = db.execute("SELECT sha, aside FROM upload_zones WHERE map='bhop_swap'").fetchone()
        self.assertEqual(sha_, sha(new))
        self.assertEqual(sorted(e['dir'] for e in json.loads(aside)), sorted(str(d.resolve()) for d in self.zones))
        self.assertTrue(all(e['file'] and e['sha'] == sha(old) for e in json.loads(aside)))
        # taken back: the old zones return, the upload's own are kept aside
        self.remove('bhop_swap')
        for d in self.zones:
            self.assertEqual((d / 'bhop_swap.json').read_bytes(), old)
        kept = self.aside()
        self.assertEqual(len(kept), 2)
        for k in kept:
            self.assertTrue(k.startswith('bhop_swap.removed-'))
            self.assertEqual((self.store / M.ASIDE / k).read_bytes(), new)
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            self.assertIsNone(db.execute("SELECT 1 FROM upload_zones WHERE map='bhop_swap'").fetchone())

    def test_no_attached_zones_leaves_the_old(self):
        old = zone()
        for d in self.zones:
            (d / 'surf_kept.json').write_bytes(old)
        b, f = self.upload('surf_kept')
        self.assertIn('they stay as they are', b['note'])
        self.assertEqual(f['ok'], 1, f)
        self.assertIn('uses the zones already on the server', f['note'])
        for d in self.zones:
            self.assertEqual((d / 'surf_kept.json').read_bytes(), old)
        self.assertEqual(self.aside(), [])
        self.remove('surf_kept')
        for d in self.zones:
            self.assertEqual((d / 'surf_kept.json').read_bytes(), old)
        self.assertFalse((self.maps / 'surf_kept.bsp').exists())

    def test_remove_leaves_zones_it_did_not_bring(self):
        # zones published (zone_edit) after an upload that brought none, and over an upload's own
        self.assertEqual(self.upload('surf_later')[1]['ok'], 1)
        self.assertEqual(self.upload('surf_over', z=zone())[1]['ok'], 1)
        later = zone(200)
        for d in self.zones:
            (d / 'surf_later.json').write_bytes(later)
            (d / 'surf_over.json').write_bytes(later)
        self.assertIn('the upload brought none', self.remove('surf_later'))
        self.assertEqual(self.rc, 0)
        out = self.remove('surf_over')
        self.assertEqual(self.rc, 1)                        # left recorded: not done
        self.assertIn('changed since the upload: left (it replaced nothing)', out)
        for d in self.zones:
            self.assertEqual((d / 'surf_later.json').read_bytes(), later)
            self.assertEqual((d / 'surf_over.json').read_bytes(), later)
        self.assertEqual(self.aside(), [])
        self.assertIsNone(self.record('surf_later'))
        self.assertEqual(len(self.record('surf_over')[1]), 2)      # not acted on: still recorded

    def test_a_rejected_picture_never_touches_the_zones(self):
        old, new = zone(), zone(128)
        (self.zones[0] / 'surf_fails.json').write_bytes(old)       # one directory had them, the other not
        before = self.stamp('surf_fails')
        bad = b'\x89PNG\r\n\x1a\n' + bytes(4000)
        b, f = self.upload('surf_fails', z=new, shot=bad)
        self.assertEqual(f['ok'], 0)
        self.assertIn('picture could not be read', f['error'])
        self.assertEqual(self.stamp('surf_fails'), before)          # never rewritten, not just put back
        self.assertEqual((self.zones[0] / 'surf_fails.json').read_bytes(), old)
        self.assertFalse((self.maps / 'surf_fails.bsp').exists())
        self.assertEqual(self.aside(), [])
        self.assertIsNone(self.record('surf_fails'))
        self.assertEqual([p.name for p in self.maps.iterdir()], ['surf_old.bsp'])   # no .part left

    def test_the_link_failing_after_the_zones_puts_them_back(self):
        old, new = zone(), zone(128)
        (self.zones[0] / 'surf_nolink.json').write_bytes(old)
        with mock.patch('mapupd.os.link', side_effect=OSError(5, 'I/O error')):
            b, f = self.upload('surf_nolink', z=new, shot=png())
        self.assertEqual(f['ok'], 0)
        self.assertIn('could not be written on the server', f['error'])
        self.assertEqual((self.zones[0] / 'surf_nolink.json').read_bytes(), old)
        self.assertFalse((self.zones[1] / 'surf_nolink.json').exists())
        self.assertFalse((self.media / 'uploads' / 'surf_nolink.jpg').exists())
        self.assertEqual(sorted(p.name for p in self.maps.iterdir()), ['surf_old.bsp'])
        self.assertEqual(self.aside(), [])
        self.assertIsNone(self.record('surf_nolink'))

    def test_a_crashed_attempt_is_undone_by_the_next(self):
        # a crash after the zones were written (the process killed before the BSP and its record): the next attempt
        # puts back what the crashed one replaced, so its own copies are of the real old zones
        class Crash(BaseException):
            pass
        old, first, second = zone(), zone(96), zone(128)
        for d in self.zones:
            (d / 'surf_crash.json').write_bytes(old)
        with mock.patch('mapupd.os.link', side_effect=Crash()):
            with self.assertRaises(Crash):
                self.upload('surf_crash', z=first)
        for d in self.zones:
            self.assertEqual((d / 'surf_crash.json').read_bytes(), first)
        self.assertEqual(self.record('surf_crash')[0], sha(first))        # recorded before the zones changed
        b, f = self.upload('surf_crash', z=second)
        self.assertEqual(f['ok'], 1, f)
        rec = self.record('surf_crash')
        self.assertEqual(rec[0], sha(second))
        for e in rec[1]:
            self.assertEqual((self.store / M.ASIDE / e['file']).read_bytes(), old)
        self.remove('surf_crash')
        for d in self.zones:
            self.assertEqual((d / 'surf_crash.json').read_bytes(), old)

    def test_finish_and_remove_take_zonepubs_lock(self):
        old = zone()
        (self.zones[0] / 'surf_locked.json').write_bytes(old)
        self.assertEqual(self.upload('surf_held', z=zone(96))[1]['ok'], 1)
        self.app = M.create_app(self.store, self.main, self.maps, self.zones, self.media, self.list,
                                clock=lambda: self.now, verify=ed25519.verify, free_bytes=lambda: 1 << 40, lock_wait=0.3)
        self.c = self.app.test_client()
        orig = M.zone_lock
        with open(self.lock, 'a') as held:                  # held as zonepub_publish.locked holds it
            fcntl.flock(held.fileno(), fcntl.LOCK_EX)
            b, f = self.upload('surf_locked', z=zone(128))
            self.assertEqual(f['ok'], 0)
            self.assertIn('publishing zones right now', f['error'])
            self.assertEqual((self.zones[0] / 'surf_locked.json').read_bytes(), old)
            self.assertFalse((self.maps / 'surf_locked.bsp').exists())
            with mock.patch('mapupd.zone_lock', lambda path, wait: orig(path, 0.2)):
                self.remove('surf_held')
            self.assertEqual(self.rc, 2)
            self.assertIn('publishing zones right now', self.err)
            self.assertTrue((self.maps / 'surf_held.bsp').exists())     # nothing moved while it was held
            self.assertIsNotNone(self.record('surf_held'))
        b, f = self.upload('surf_locked', z=zone(128))      # released: it goes through
        self.assertEqual(f['ok'], 1, f)

    def test_remove_with_some_zone_dirs_keeps_the_rest_recorded(self):
        old, new = zone(), zone(128)
        for d in self.zones:
            (d / 'surf_part.json').write_bytes(old)
        self.assertEqual(self.upload('surf_part', z=new)[1]['ok'], 1)
        out = self.remove('surf_part', zone_dirs=self.zones[:1])
        self.assertEqual(self.rc, 1)
        self.assertIn('not handled (no --zone-dir for it; it replaced zones-aside/surf_part.replaced-', out)
        self.assertEqual((self.zones[0] / 'surf_part.json').read_bytes(), old)
        self.assertEqual((self.zones[1] / 'surf_part.json').read_bytes(), new)
        self.assertEqual([e['dir'] for e in self.record('surf_part')[1]], [str(self.zones[1].resolve())])
        out = self.remove('surf_part')                      # the re-run continues from the record
        self.assertEqual(self.rc, 0)
        self.assertIn('no BSP of it was in the library', out)
        self.assertEqual((self.zones[1] / 'surf_part.json').read_bytes(), old)
        self.assertIsNone(self.record('surf_part'))

    def test_remove_failing_partway_then_again(self):
        old, new = zone(), zone(128)
        for d in self.zones:
            (d / 'surf_ro.json').write_bytes(old)
        self.assertEqual(self.upload('surf_ro', z=new)[1]['ok'], 1)
        os.chmod(self.zones[1], 0o500)                      # its file cannot be put back
        try:
            out = self.remove('surf_ro')
        finally:
            os.chmod(self.zones[1], 0o700)
        self.assertEqual(self.rc, 1)
        self.assertIn('cannot be written', out)
        self.assertNotIn('copied to []', out)
        self.assertIn('still recorded', out)
        self.assertEqual((self.zones[0] / 'surf_ro.json').read_bytes(), old)
        self.assertEqual((self.zones[1] / 'surf_ro.json').read_bytes(), new)
        self.assertFalse((self.maps / 'surf_ro.bsp').exists())
        self.assertIn('put back as it was', self.remove('surf_ro'))     # no uploads row now: the record carries it
        self.assertEqual(self.rc, 0)
        self.assertEqual((self.zones[1] / 'surf_ro.json').read_bytes(), old)
        self.assertIsNone(self.record('surf_ro'))
        self.remove('surf_ro')                              # nothing left: not an upload
        self.assertEqual(self.rc, 2)
        self.assertIn('not an upload', self.err)

    # ---- round 2 ---------------------------------------------------------------------------------------------------
    def test_remove_reads_its_rows_under_the_lock(self):
        # a remove that left a dir recorded, re-run while a new upload of the name finishes just before it gets the
        # lock: it must act on the new upload's rows, never on what it saw before (that moved the new BSP and wrote
        # the old record over the new one)
        o, a, b = zone(), zone(96), zone(128)
        for d in self.zones:
            (d / 'surf_race.json').write_bytes(o)
        self.assertEqual(self.upload('surf_race', z=a)[1]['ok'], 1)
        self.remove('surf_race', zone_dirs=self.zones[:1])
        self.assertEqual(self.rc, 1)
        orig, ran = M.zone_lock, []

        def finish_first(path, wait):
            if wait == 120 and not ran:                     # remove's call: the new upload slips in before it
                ran.append(1)
                self.assertEqual(self.upload('surf_race', z=b)[1]['ok'], 1)
            return orig(path, wait)
        with mock.patch('mapupd.zone_lock', finish_first):
            self.remove('surf_race')
        self.assertEqual(self.rc, 0)
        for d in self.zones:
            self.assertEqual((d / 'surf_race.json').read_bytes(), o)
        self.assertIsNone(self.record('surf_race'))
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            self.assertIsNone(db.execute("SELECT 1 FROM uploads WHERE map='surf_race'").fetchone())

    def test_a_remove_that_died_can_be_run_again(self):
        o, a = zone(), zone(96)
        for d in self.zones:
            (d / 'surf_died.json').write_bytes(o)
        self.assertEqual(self.upload('surf_died', z=a)[1]['ok'], 1)
        argv = ['mapupd.py', '--store', str(self.store), 'remove', '--map', 'surf_died', '--maps', str(self.maps),
                '--list', str(self.list) + '.typo'] + sum((['--zone-dir', str(d)] for d in self.zones), [])
        with self.assertRaises(FileNotFoundError):         # after the zones went back, before the rows
            old, sys.argv = sys.argv, argv
            try:
                with mock.patch('sys.stdout', io.StringIO()):
                    M.main()
            finally:
                sys.argv = old
        for d in self.zones:
            self.assertEqual((d / 'surf_died.json').read_bytes(), o)
        out = self.remove('surf_died')
        self.assertEqual(self.rc, 0)
        self.assertIn('all handled already', out)
        self.assertNotIn('surf_died', self.list.read_text())
        self.assertIsNone(self.record('surf_died'))

    def test_take_back_counts_a_dir_already_put_back_as_done(self):
        # died between putting the files back and recording it: the files are the replaced ones, the copies gone
        o, a = zone(), zone(96)
        for d in self.zones:
            (d / 'surf_done.json').write_bytes(o)
        self.assertEqual(self.upload('surf_done', z=a)[1]['ok'], 1)
        for d in self.zones:
            (d / 'surf_done.json').write_bytes(o)
        for k in self.aside():
            (self.store / M.ASIDE / k).unlink()
        out = self.remove('surf_done')
        self.assertEqual(self.rc, 0)
        self.assertEqual(out.count('already as it was before the upload'), 2)
        self.assertIsNone(self.record('surf_done'))

    def test_a_zonepub_publish_since_keeps_the_zones(self):
        # a crashed attempt's zones, then the same zones published with zone_edit (zonepub records a noop row): a
        # retry without zones keeps them, as begin says; so does remove
        class Crash(BaseException):
            pass
        o, a = zone(), zone(96)
        for d in self.zones:
            (d / 'bhop_pub.json').write_bytes(o)
        with mock.patch('mapupd.os.link', side_effect=Crash()):
            with self.assertRaises(Crash):
                self.upload('bhop_pub', z=a)
        self.zonepub(('bhop_pub', self.now + 5))
        self.now += 10
        b, f = self.upload('bhop_pub')
        self.assertIn('they stay as they are', b['note'])
        self.assertEqual(f['ok'], 1, f)
        for d in self.zones:
            self.assertEqual((d / 'bhop_pub.json').read_bytes(), a)
        # an upload whose zones were published again since: remove leaves them
        self.assertEqual(self.upload('bhop_pub2', z=a)[1]['ok'], 1)
        self.zonepub(('bhop_pub2', self.now))
        out = self.remove('bhop_pub2')
        self.assertEqual(self.rc, 1)
        self.assertIn('published with zone_edit since', out)
        for d in self.zones:
            self.assertEqual((d / 'bhop_pub2.json').read_bytes(), a)
        # a history that cannot be read decides nothing either
        self.assertEqual(self.upload('bhop_pub3', z=a)[1]['ok'], 1)
        self.lock.with_name('zones.sqlite3').write_bytes(b'not a database' * 100)
        self.assertIn('cannot be read', self.remove('bhop_pub3'))
        self.assertEqual((self.zones[0] / 'bhop_pub3.json').read_bytes(), a)

    def test_a_zone_copy_lobbies_read_first_is_warned(self):
        first = Path(self.tmp.name) / 'game' / 'ftesurf' / 'data' / 'maps' / 'zones' / 'local'
        first.mkdir(parents=True)
        (first / 'surf_shadow.json').write_bytes(zone())
        self.app = M.create_app(self.store, self.main, self.maps, self.zones, self.media, self.list,
                                clock=lambda: self.now, verify=ed25519.verify, free_bytes=lambda: 1 << 40,
                                zone_check=self.zones + [first])
        self.c = self.app.test_client()
        b, f = self.upload('surf_shadow', z=zone(128))
        self.assertIn('Lobbies read the copy in ftesurf/data/maps/zones/local first, so that one still wins', b['note'])
        self.assertNotIn('Your zone file replaces', b['note'])
        self.assertIn('still wins', f['note'])
        self.assertEqual((first / 'surf_shadow.json').read_bytes(), zone())     # never written

    def test_remove_of_an_upload_from_before_p1799(self):
        # no upload_zones row: uploads.zone says whether it wrote zones (nothing could be under them then)
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            for name, z in (('surf_legacy0', 0), ('surf_legacy1', 1)):
                db.execute("INSERT INTO uploads VALUES(?,?,1,?,1,'surf',0,0,0,'',0,?)", (name, SID, '0' * 64, z))
        for d in self.zones:
            (d / 'surf_legacy0.json').write_bytes(zone())        # published later: not the upload's
            (d / 'surf_legacy1.json').write_bytes(zone(96))      # maybe the upload's own: nothing says so
        self.assertIn('the upload brought none', self.remove('surf_legacy0'))
        self.assertIn('from before P1799, so which zone files it brought is not recorded', self.remove('surf_legacy1'))
        for d in self.zones:
            self.assertEqual((d / 'surf_legacy0.json').read_bytes(), zone())
            self.assertEqual((d / 'surf_legacy1.json').read_bytes(), zone(96))
        self.assertEqual(self.aside(), [])

    # ---- round 3 ---------------------------------------------------------------------------------------------------
    def test_list_on_a_store_with_the_table(self):
        for d in self.zones:
            (d / 'surf_listed2.json').write_bytes(zone())
        self.assertEqual(self.upload('surf_listed2', z=zone(96))[1]['ok'], 1)
        self.assertEqual(self.upload('surf_plain')[1]['ok'], 1)
        out = self.cli(['mapupd.py', '--store', str(self.store), 'list'])
        self.assertEqual(self.rc, 0, self.err)
        self.assertIn('surf_listed2 ', out)
        self.assertIn('(replaced 2 zone files)', out)
        self.assertIn('surf_plain ', out)

    def test_a_p1799_store_without_at_gains_it(self):
        # a store made by P1799's first commits: upload_zones without `at`; init, the service and remove add it (0)
        for entry in ('init', 'app', 'remove'):
            t = Path(self.tmp.name) / ('noat-' + entry)
            t.mkdir()
            (t / 'spool').mkdir()
            with sqlite3.connect(t / 'mapupd.db') as db:
                db.executescript(M.SQL.replace(M.ZONES_SQL + ';\n', ''))
                db.execute('CREATE TABLE upload_zones(map TEXT PRIMARY KEY, sha TEXT NOT NULL, aside TEXT NOT NULL)')
                db.execute("INSERT INTO meta VALUES('secret','x')")
                db.execute("INSERT INTO uploads VALUES('surf_noat',?,1,?,1,'surf',0,0,0,'',0,0)", (SID, '0' * 64))
                db.execute("INSERT INTO upload_zones VALUES('surf_noat','','[]')")
            if entry == 'init':
                M.initialize(t)
            elif entry == 'app':
                M.create_app(t, self.main, self.maps, self.zones)
            else:
                self.remove('surf_noat', store=t)
                self.assertEqual(self.rc, 0, self.err)
            with sqlite3.connect(t / 'mapupd.db') as db:
                self.assertIn('at', [r[1] for r in db.execute('PRAGMA table_info(upload_zones)')], entry)
                if entry != 'remove':
                    self.assertEqual(db.execute("SELECT at FROM upload_zones").fetchone(), (0,))

    def test_published_since_reads_applied_kinds_and_live(self):
        zs = self.lock.with_name('zones.sqlite3')
        t = 1_800_000_100
        self.zonepub(('m_late', t - 50, 'noop', t + 5),           # queued before, applied (as noop) after: counts
                     ('m_dead', t + 10, 'superseded'), ('m_dead', t + 10, 'expired'), ('m_dead', t + 10, 'failed'),
                     ('m_dead', t + 10, 'pending'), ('m_old', t - 50, 'live', t - 40), ('m_now', t, 'live', t))
        self.assertTrue(M.published_since(zs, 'm_late', t))
        self.assertFalse(M.published_since(zs, 'm_dead', t))      # never wrote or confirmed the files
        self.assertFalse(M.published_since(zs, 'm_old', t))
        self.assertTrue(M.published_since(zs, 'm_now', t))
        self.assertFalse(M.published_since(zs, 'm_none', t))

    def test_the_record_time_is_taken_under_the_lock(self):
        # a finish that waited for zonepub's lock: the record's time is when it got it, not when the request came in
        orig = M.zone_lock

        def slow(path, wait):
            self.now += 50
            return orig(path, wait)
        with mock.patch('mapupd.zone_lock', slow):
            self.assertEqual(self.upload('surf_waited', z=zone(96))[1]['ok'], 1)
        with sqlite3.connect(self.store / 'mapupd.db') as db:
            self.assertEqual(db.execute("SELECT at FROM upload_zones WHERE map='surf_waited'").fetchone(), (self.now,))

    def test_an_older_store_without_the_table(self):
        t = Path(self.tmp.name) / 'oldstore2'
        t.mkdir()
        with sqlite3.connect(t / 'mapupd.db') as db:
            db.executescript(M.SQL.replace(M.ZONES_SQL + ';\n', ''))
            db.execute("INSERT INTO meta VALUES('secret','x')")
            db.execute("INSERT INTO uploads VALUES('surf_x',?,1,?,1,'surf',0,0,0,'',0,1)", (SID, '0' * 64))
        self.assertIn('surf_x', self.cli(['mapupd.py', '--store', str(t), 'list']))
        for d in self.zones:
            (d / 'surf_x.json').write_bytes(zone())
        self.assertIn('not recorded', self.remove('surf_x', store=t))
        self.assertTrue(all((d / 'surf_x.json').exists() for d in self.zones))
        t3 = Path(self.tmp.name) / 'oldstore3'
        t3.mkdir()
        with sqlite3.connect(t3 / 'mapupd.db') as db:
            db.executescript(M.SQL.replace(M.ZONES_SQL + ';\n', ''))
            db.execute("INSERT INTO meta VALUES('secret','x')")
        (t3 / 'spool').mkdir()
        M.create_app(t3, self.main, self.maps, self.zones)
        with sqlite3.connect(t3 / 'mapupd.db') as db:
            self.assertIsNotNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='upload_zones'").fetchone())

    def test_an_older_store_gains_the_table(self):
        # a store made by the P1746 release: init (the installer's upgrade step) adds upload_zones and keeps the rows
        t = Path(self.tmp.name) / 'oldstore'
        t.mkdir()
        with sqlite3.connect(t / 'mapupd.db') as db:
            db.executescript(M.SQL.replace(M.ZONES_SQL + ';\n', ''))
            db.execute("INSERT INTO meta VALUES('secret','x')")
            db.execute("INSERT INTO uploads VALUES('surf_x',?,1,?,1,'surf',0,0,0,'',0,0)", (SID, '0' * 64))
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='upload_zones'").fetchone())
        M.initialize(t)
        with sqlite3.connect(t / 'mapupd.db') as db:
            self.assertIsNotNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='upload_zones'").fetchone())
            self.assertEqual(db.execute('SELECT map FROM uploads').fetchall(), [('surf_x',)])
            self.assertEqual(db.execute("SELECT v FROM meta WHERE k='secret'").fetchone(), ('x',))
        self.assertTrue((t / M.ASIDE).is_dir())

    def test_a_refused_part_is_not_read(self):
        r = self.post('part?s=%s&p=bsp&e=raw' % ('0' * 32), data=b'x' * 100000)
        self.assertIn('expired', r['error'])
        self.assertIn('not one this service reads', self.post('part?s=zz&p=bsp&e=raw', data=b'x')['error'])

    def test_other_session_cannot_send_parts(self):
        bsp = vbsp()
        r = self.part('0' * 32, 'bsp', bsp)
        self.assertIn('expired', r['error'])


if __name__ == '__main__':
    unittest.main()
