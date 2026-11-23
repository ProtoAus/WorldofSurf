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


def zone():
    r = dict(points=[[0, 0], [32, 0], [32, 32], [0, 32]], bottom=0, height=64)
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
                                clock=lambda: self.now, verify=ed25519.verify)
        self.c = self.app.test_client()

    def tearDown(self):
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
        head = ('FTESURF-MAPUP-PART 1\nsession %s\npart %s\nenc %s\n\n' % (token, which, enc)).encode()
        return self.post('part', data=head + data)

    def finish(self, token):
        return self.post('finish', data=('session %s\n' % token).encode())

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
                          (manifest('bhop_nozone', vbsp(), mode='bhop'), 'needs its zone file'),
                          (manifest('surf_mode', vbsp(), mode='bhop', zonebody=zone()), "name's own"),
                          (manifest('surf_tier', vbsp(), tier=11), 'out of range')):
            b, _ = self.begin(text)
            self.assertEqual(b['ok'], 0, text)
            self.assertIn(why, b['error'])

    def test_other_session_cannot_send_parts(self):
        bsp = vbsp()
        r = self.part('0' * 32, 'bsp', bsp)
        self.assertIn('expired', r['error'])


if __name__ == '__main__':
    unittest.main()
