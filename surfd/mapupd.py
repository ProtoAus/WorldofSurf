#!/usr/bin/env python3
"""P1746: an admin uploads a new map from the game (src/menu/m_mapupload.qc). Deny by default, like zonepub.

challenge  a code for one manifest's SHA-256 (stateless: time, salt, MAC)
begin      the manifest, signed by the menu's linked key (friends_sign op "mapupload", who = its SHA-256); the key's
           Steam account must be linked, unbanned and hold this service's map role. Answers a session token.
part       one file, streamed to the spool (gzip allowed); its size and SHA-256 must be the manifest's
finish     checks the BSP (VBSP 17-21 or 25, lumps inside the file), the picture and the zones, then publishes: the
           library, the zone directories, the site's pictures, a row in the map list and in the map table.

P1799 (Lex: "Allow uploading without zone ... Allow uploading of a map with the zone files already on the server"):
zones are optional for every mode, and zone files already on the server no longer hold a name (zone_edit's Publish
can put a map's zones up before the map). Attached zones replace them, the old files kept aside in the store
(<store>/zones-aside, recorded in upload_zones) and put back if the publish fails; no attached zones leaves them be.
`remove` takes back only the zones its upload placed, and puts back what they replaced.

The two tables are other writers' files (mapwatch's list, mapmedia's table). A row they drop on a rewrite is put
back by the minute tick (heal); every write is checked with the readers' own rules before it replaces the file.
Refusals answer 200 with ok=0: the game's HTTP client keeps no body for any other status.
"""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import sys
import threading
import time
import zlib
from flask import Flask, jsonify, request
import accounts
import mapmanifest
import zonepub
import zonepub_publish
try:
    import fcntl
except ImportError:             # Windows test runs: one process
    fcntl = None

SITE = 'play.proto.bar:443'
STATEMENT = 'FTESURF-FRIENDS 1\nserver %s\nnonce %s\nop mapupload\nwho %s\n'     # cl_receipt.c CL_FriendsSign
NAME = re.compile(r'(surf|bhop)_[a-z0-9_-]{1,59}')     # the list and the pool key a map's mode on its prefix
HEX64 = re.compile(r'[0-9a-f]{64}')
AUTHOR = re.compile(r'[A-Za-z0-9 _.\'-]{1,40}')
MAX_BSP = 1 << 30                   # the engine's uri_postfile cap
MAX_SHOT = 16 << 20
MAX_ZONE = zonepub.MAX_ZONE_BYTES
SHOT_EXT = ('png', 'jpg', 'jpeg', 'tga')
CODE_TTL = 600                      # s a challenge code is good for
SESSION_TTL = 3 * 3600              # s an accepted manifest may take to upload
PEER_RATE = 30                      # requests a minute per address, before any other work
PART_DEADLINE = 3600                # s one file may take in all (a slow uplink and a 1 GB map)
SMALL_BODY = 8192                   # challenge, begin and finish (nginx caps them too)
INFLATE_STEP = 4 << 20              # bytes out of one inflate call
FREE_FLOOR = 20 << 30               # disk left beside the library after an upload
DAY_UPLOADS, DAY_KB = 10, 8 << 20   # one account's maps and KB in a day
VBSP_VERSIONS = (17, 18, 19, 20, 21, 25)    # what plugins/hl2/mod_vbsp.c loads (25: Strata, SourceBroom)
SQL = '''
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS roles(steamid TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS nonces(nonce TEXT PRIMARY KEY, seen INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, steamid TEXT NOT NULL, map TEXT NOT NULL,
 manifest TEXT NOT NULL, created INTEGER NOT NULL, got TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS uploads(map TEXT PRIMARY KEY, steamid TEXT NOT NULL, at INTEGER NOT NULL,
 bsp_sha TEXT NOT NULL, kb INTEGER NOT NULL, mode TEXT NOT NULL, tier INTEGER NOT NULL, stages INTEGER NOT NULL,
 bonuses INTEGER NOT NULL, author TEXT NOT NULL, shot INTEGER NOT NULL, zone INTEGER NOT NULL);
'''
ZONES_SQL = ('CREATE TABLE IF NOT EXISTS upload_zones(map TEXT PRIMARY KEY, sha TEXT NOT NULL, aside TEXT NOT NULL, '
             'at INTEGER NOT NULL DEFAULT 0)')
SQL += ZONES_SQL + ';\n'
# P1799: sha = the zone file an upload wrote ('' none); aside = JSON [{dir, file, sha}], one per zone dir it wrote, file
# the copy (in <store>/zones-aside) of what it replaced there ('' none); at, when it wrote them. Written before the first
# zone write: a row with no uploads row is an attempt that crashed or a remove left part done. A table, not uploads columns: the old release
# still serving during `init` (--upgrade-from) inserts 12 values into uploads. Pre-P1799 uploads have no row.
ASIDE = 'zones-aside'
# zonepub_publish.locked's flock (publish.lock beside zonepub's store): an upload's or remove's zone writes take it too
ZONEPUB_LOCK = '/srv/nvme/ftesurf-ops/zonepub-state/publish.lock'
LOCK_WAIT = 30                      # s finish waits for it (zonepub's apply holds it through a publish's lobby reloads)


class Refused(Exception):
    """A reason the uploader is shown."""


@contextmanager
def connect(path, readonly=False):
    uri = Path(path).resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw')
    db = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


@contextmanager
def writing(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        yield db
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


def initialize(store):
    """A new store, or an older one brought up to date: every step is additive (CREATE ... IF NOT EXISTS)."""
    store = Path(store)
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    (store / 'spool').mkdir(mode=0o700, exist_ok=True)
    (store / ASIDE).mkdir(mode=0o700, exist_ok=True)
    db = sqlite3.connect(store / 'mapupd.db')
    try:
        db.execute('PRAGMA journal_mode=WAL')
        with db:
            db.executescript(SQL)
            db.execute("INSERT OR IGNORE INTO meta(k, v) VALUES ('secret', ?)", (secrets.token_hex(32),))
    finally:
        db.close()
    os.chmod(store / 'mapupd.db', 0o600)


def parse_manifest(text):
    """The manifest's fields, or Refused. Exactly the menu's lines, in its order (m_mapupload.qc MUp_Manifest)."""
    lines = text.split('\n')
    if len(lines) != 12 or lines[0] != 'FTESURF-MAPUP 1' or lines[11] != '':
        raise Refused('That upload is not one this service reads: update your game.')
    want = ('map', 'bsp', 'shot', 'zone', 'mode', 'tier', 'stages', 'bonuses', 'linear', 'author')
    got = {}
    for key, line in zip(want, lines[1:11]):
        k, _, v = line.partition(' ')
        if k != key or not v:
            raise Refused('That upload is not one this service reads: update your game.')
        got[key] = v
    m = {}
    if not NAME.fullmatch(got['map']):
        raise Refused('Map names here are surf_ or bhop_ then lowercase letters, digits, _ or -.')
    m['map'] = got['map']

    def file_field(key, cap, ext=False):
        if got[key] == '-':
            return None
        parts = got[key].split(' ')
        if len(parts) != (3 if ext else 2) or not HEX64.fullmatch(parts[0]) or not re.fullmatch('[0-9]{1,10}', parts[1]):
            raise Refused('That upload is not one this service reads: update your game.')
        size = int(parts[1])
        if not 0 < size <= cap:
            raise Refused('The %s is over %d MB.' % ({'bsp': 'map', 'shot': 'picture', 'zone': 'zone file'}[key], cap >> 20)
                          if size else 'The %s file is empty.' % key)
        if ext and parts[2] not in SHOT_EXT:
            raise Refused('Pictures are .png, .jpg or .tga.')
        return (parts[0], size, parts[2]) if ext else (parts[0], size)
    m['bsp'] = file_field('bsp', MAX_BSP)
    if m['bsp'] is None:
        raise Refused('Choose a map.')
    m['shot'] = file_field('shot', MAX_SHOT, ext=True)
    m['zone'] = file_field('zone', MAX_ZONE)
    if got['mode'] not in ('surf', 'bhop') or not m['map'].startswith(got['mode'] + '_'):
        raise Refused('The mode must be the name\'s own (surf_ or bhop_).')
    m['mode'] = got['mode']
    for key, top in (('tier', 10), ('stages', 64), ('bonuses', 16), ('linear', 1)):
        if not re.fullmatch('[0-9]{1,2}', got[key]) or int(got[key]) > top:
            raise Refused('The %s is out of range.' % key)
        m[key] = int(got[key])
    if m['linear'] != (1 if m['stages'] == 0 else 0):
        raise Refused('A map is linear or has stages, not both.')
    m['author'] = '' if got['author'] == '-' else got['author']
    if m['author'] and not AUTHOR.fullmatch(m['author']):
        raise Refused('The author name has characters it cannot carry.')
    return m


def check_bsp(path, size):
    """A Source BSP whose 64 lumps lie inside the file: the game's loader reads them from the header."""
    with open(path, 'rb') as f:
        head = f.read(8 + 64 * 16)
    if len(head) < 8 + 64 * 16 or head[:4] != b'VBSP':
        raise Refused('That is not a Source map (.bsp starting VBSP).')
    version = int.from_bytes(head[4:8], 'little')
    if version not in VBSP_VERSIONS:
        raise Refused('BSP version %d is not one the game loads (17-21 or 25).' % version)
    for i in range(64):
        ofs = int.from_bytes(head[8 + i * 16:12 + i * 16], 'little', signed=True)
        ln = int.from_bytes(head[12 + i * 16:16 + i * 16], 'little', signed=True)
        if ofs < 0 or ln < 0 or ofs + ln > size:
            raise Refused('That map file is cut short or damaged (lump %d lies past its end).' % i)


def render_pictures(src):
    """The bytes of <name>.jpg (the card and backdrop, at most 1920x1080) and <name>-thumb.jpg (320x180): decoded and
    checked before anything shared is touched (P1799), written by the caller."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 20_000_000     # 5K; an 8K RGBA PNG peaked at 638 MiB decoding (review 2)
    try:
        # the decoder is chosen from the bytes: only these three, whatever the name says (never EPS, which is Ghostscript)
        with Image.open(src, formats=('PNG', 'JPEG', 'TGA')) as im:
            if im.width < 160 or im.height < 90 or im.width * im.height > Image.MAX_IMAGE_PIXELS:
                raise Refused('The picture must be at least 160x90 and at most 20 megapixels.')
            im.load()
            im = im.convert('RGB')
            big = im.copy()
            big.thumbnail((1920, 1080), Image.LANCZOS)
            thumb = im.copy()
            # the list's cells are 16:9: centre-cropped, then scaled
            w, h = thumb.size
            cw, ch = (w, w * 9 // 16) if w * 9 <= h * 16 else (h * 16 // 9, h)
            thumb = thumb.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch)).resize((320, 180), Image.LANCZOS)
    except Refused:
        raise
    except Exception:
        raise Refused('That picture could not be read.')
    out = []
    for img in (big, thumb):
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=88)
        out.append(buf.getvalue())
    return out


def atomic_write(path, body, mode=0o644):
    tmp = path.with_name('.%s.mapupd.tmp' % path.name)
    with open(tmp, 'wb') as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def list_row(u, today):
    return 'dl %s %s - %d %d %s 1 %d 0' % (u['map'], u['mode'], u['tier'], u['kb'], today, u['tier'])


def meta_row(u):
    author = re.sub(r'[^A-Za-z0-9_.-]', lambda c: '_' if c.group() == ' ' else '.%02x' % ord(c.group()), u['author']) or '-'
    return 'meta %s %s %d %d %d - - - %d upload - %s - -' % (
        u['map'], u['tier'] or '-', 1 if u['stages'] == 0 else 0, u['stages'], u['bonuses'],
        1 if u['mode'] == 'surf' else 2, author[:64])


def heal_list(path, uploads, today, log=print):
    """Each upload's row in the map list (mapwatch rewrites it every few hours). Read with mapmanifest's own rules
    before and after: a list it would refuse is never written."""
    if not path or not uploads:
        return 0
    path = Path(path)
    try:
        before = os.stat(path)
        text = path.read_text(encoding='utf-8')
        have = {r['map'] for r in mapmanifest.read_list(path)}
    except (OSError, ValueError) as e:
        log('map list unreadable, not healed:', e)
        return 0
    add = [list_row(u, today) for u in uploads if u['map'] not in have]
    if not add:
        return 0
    new = text if text.endswith('\n') else text + '\n'
    new += ''.join(r + '\n' for r in add)
    tmp = path.with_name('.mapdl.mapupd.tmp')
    tmp.write_text(new, encoding='utf-8')
    try:
        mapmanifest.read_list(tmp)
        st = os.stat(path)
        if (st.st_ino, st.st_mtime_ns, st.st_size) != (before.st_ino, before.st_mtime_ns, before.st_size):
            raise ValueError('rewritten while read; next tick')
        os.chmod(tmp, before.st_mode & 0o777)
        os.replace(tmp, path)
    except (OSError, ValueError) as e:
        tmp.unlink(missing_ok=True)
        log('map list not healed:', e)
        return 0
    return len(add)


def heal_meta(path, uploads, log=print):
    """Each upload's row in the site's map table, before its "# end N" (the menu takes the table only when N is its
    count of meta rows), and a new "# stamp" so a menu takes this copy."""
    if not path or not uploads:
        return 0
    path = Path(path)
    try:
        before = os.stat(path)
        lines = path.read_text(encoding='utf-8').split('\n')
    except OSError as e:
        log('map table unreadable, not healed:', e)
        return 0
    if not lines or lines[0] != 'FTESURF-MAPMETA 1':
        log('map table not one the menu reads; not healed')
        return 0
    have = {ln.split()[1] for ln in lines if ln.startswith('meta ') and len(ln.split()) > 1}
    add = [meta_row(u) for u in uploads if u['map'] not in have]
    if not add:
        return 0
    ends = [i for i, ln in enumerate(lines) if re.fullmatch(r'# end [0-9]{1,6}', ln)]
    if len(ends) != 1:
        log('map table has no single end line; not healed')
        return 0
    rows = sum(1 for ln in lines if ln.startswith('meta ')) + len(add)
    lines[ends[0]] = '# end %d' % rows
    last_meta = max((i for i, ln in enumerate(lines) if ln.startswith('meta ')), default=ends[0] - 1)
    lines[last_meta + 1:last_meta + 1] = add
    stamp = time.strftime('%Y%m%d%H%M%S', time.gmtime())
    lines = [('# stamp ' + stamp) if re.fullmatch(r'# stamp [0-9]{14}', ln) else ln for ln in lines]
    tmp = path.with_name('.mapmeta.mapupd.tmp')
    tmp.write_text('\n'.join(lines), encoding='utf-8')
    try:
        st = os.stat(path)
        if (st.st_ino, st.st_mtime_ns, st.st_size) != (before.st_ino, before.st_mtime_ns, before.st_size):
            raise ValueError('rewritten while read; next tick')
        os.chmod(tmp, before.st_mode & 0o777)
        os.replace(tmp, path)
    except (OSError, ValueError) as e:
        tmp.unlink(missing_ok=True)
        log('map table not healed:', e)
        return 0
    return len(add)


def drop_rows(path, prefix, meta=False):
    """The lines starting `prefix` out of a table, the meta table's "# end N" kept true."""
    lines = path.read_text(encoding='utf-8').split('\n')
    keep = [ln for ln in lines if not ln.startswith(prefix)]
    if len(keep) == len(lines):
        return
    if meta:
        n = sum(1 for ln in keep if ln.startswith('meta '))
        keep = ['# end %d' % n if re.fullmatch(r'# end [0-9]{1,6}', ln) else ln for ln in keep]
    tmp = path.with_name('.%s.mapupd.tmp' % path.name)
    tmp.write_text('\n'.join(keep), encoding='utf-8')
    os.chmod(tmp, os.stat(path).st_mode & 0o777)
    os.replace(tmp, path)


def library_has(maps_dir, name):
    try:
        return any(p.suffix.lower() == '.bsp' and p.stem.lower() == name for p in Path(maps_dir).iterdir())
    except OSError:
        raise Refused('The map library cannot be read right now; try again later.')


def ed25519_verifier():
    """tasupd's: the cryptography library's when it is there, tools/ed25519.py's small-order refusal kept beside it."""
    tools = os.environ.get('SURFD_TOOLS', str(Path(__file__).resolve().parent.parent / 'tools'))
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import ed25519 as ed
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return ed.verify

    def fast(pub, msg, sig):
        if len(pub) != 32 or len(sig) != 64 or ed._point_decompress(pub) is None or ed.small_order(pub):
            return False
        try:
            Ed25519PublicKey.from_public_bytes(pub).verify(sig, msg)
            return True
        except (InvalidSignature, ValueError):
            return False
    return fast


def log(*words):
    print('mapupd:', *words, file=sys.stderr, flush=True)


def taken(name, maps_dir, list_path, media_dir):
    """Why `name` cannot be a new map ("" when it can): a BSP, or a row either table already has. Zone files do not
    hold a name (P1799): zone_edit's Publish (zonepub) writes only the zone directories, never the list or table, so
    a name with published zones and no BSP is free."""
    if library_has(maps_dir, name):
        return '%s is already in the library. Uploads add new maps; give it a new name.' % name
    try:
        if list_path and name in {r['map'] for r in mapmanifest.read_list(list_path)}:
            return '%s is already in the map list; give it a new name.' % name
    except (OSError, ValueError):
        pass
    try:
        if media_dir and any(ln.split()[1:2] == [name] for ln in (Path(media_dir) / 'mapmeta.txt').read_text().split('\n')
                             if ln.startswith('meta ')):
            return '%s is already in the map table; give it a new name.' % name
    except OSError:
        pass
    return ''


def zones_held(name, zone_dirs):
    """The directories (of those given) holding a zone file of this name."""
    return [Path(d) for d in zone_dirs if (Path(d) / (name + '.json')).exists()]


def where(d):
    """A zone directory as the uploader is told it."""
    s = str(d).replace('\\', '/').rstrip('/')
    if '/game/' in s:
        return s.split('/game/', 1)[1]
    return "the site's zones" if s.endswith('ftesurf-site/zones') else s


def outranking(held, zone_dirs):
    """Held copies a lobby reads before the maps/zones/local file an upload writes: QC_FixFileName tries data/ first
    (sv_zones.qc's load order), so a data/maps/zones/local copy still wins."""
    keys = {zonepub_publish.key(d) for d in zone_dirs}
    return [d for d in held if zonepub_publish.key(d) not in keys and 'data/maps/zones/local' in str(d).replace('\\', '/')]


def zones_note(name, held, zone_dirs, attached):
    """What begin says about zones of this name already up ("" none)."""
    if not held:
        return ''
    if not attached:
        return '%s already has zones on the server (%s): they stay as they are (this upload attaches none).' % (
            name, ', '.join(where(d) for d in held))
    keys = {zonepub_publish.key(d) for d in zone_dirs}
    mine = [d for d in held if zonepub_publish.key(d) in keys]
    first = outranking(held, zone_dirs)
    rest = [d for d in held if d not in mine and d not in first]
    out = '%s already has zones on the server.' % name
    if mine:
        out += (' Your zone file replaces the copies in %s (the old ones are kept in the upload service\'s store).'
                % ', '.join(where(d) for d in mine))
    if rest:
        out += ' The copies in %s are left as they are.' % ', '.join(where(d) for d in rest)
    if first:
        out += (' Lobbies read the copy in %s first, so that one still wins: ask Proto to take it out.'
                % ', '.join(where(d) for d in first))
    return out


@contextmanager
def zone_lock(path, wait):
    """zonepub's publish lock, held while an upload or a remove changes zone files, so neither interleaves with a
    zone_edit Publish, apply or rollback. Opened read-only when it is there: the unit cannot write zonepub's directory
    (ProtectSystem=strict) and flock needs no write access."""
    if fcntl is None:
        yield
        return
    nofollow = getattr(os, 'O_NOFOLLOW', 0)
    try:
        try:
            fd = os.open(path, os.O_RDONLY | nofollow)
        except FileNotFoundError:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | nofollow, 0o600)
    except OSError as e:
        log('zone lock not opened:', path, e)
        raise Refused('The zone service\'s lock cannot be taken; nothing was published. Tell Proto.')
    try:
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Refused('The zone service is publishing zones right now; try again in a minute.')
                time.sleep(0.1)
        yield
    finally:
        os.close(fd)            # releases it


def aside_dir(store):
    d = Path(store) / ASIDE
    d.mkdir(mode=0o700, exist_ok=True)
    return d


def keep_aside(store, name, stamp, files, label):
    """[(path, body or None)] -> [{"dir", "file", "sha"}]: each body copied into the store (private, never served)
    before the caller touches a zone file; file and sha '' where there was none."""
    out, d = [], aside_dir(store)
    try:
        for path, body in files:
            e = dict(dir=zonepub_publish.key(Path(path).parent), file='', sha='')
            if body is not None:
                e['file'] = '%s.%s-%d.%d.%s.json' % (name, label, stamp, len(out), secrets.token_hex(3))
                atomic_write(d / e['file'], body, 0o600)
                e['sha'] = hashlib.sha256(body).hexdigest()
            out.append(e)
    except Exception:
        drop_aside(store, out)
        raise
    return out


def drop_aside(store, entries):
    for e in entries:
        if e['file']:
            (Path(store) / ASIDE / e['file']).unlink(missing_ok=True)


def aside_names(entries):
    return [e['file'] for e in entries if e['file']]


def read_aside(store, entry):
    """The bytes kept aside for `entry`, or None when the copy is gone or is not what was recorded."""
    try:
        body = (Path(store) / ASIDE / entry['file']).read_bytes()
    except OSError:
        return None
    return body if hashlib.sha256(body).hexdigest() == entry['sha'] else None


def take_back(store, name, zone_dirs, sha, entries, stamp):
    """Undo an upload's zone writes (`remove`; finish, for an attempt that crashed with its zones live). In each
    directory given whose file is still the one the upload wrote (`sha`), what it replaced is put back (or the file
    taken out), the upload's own copied aside first. A directory not given, a file gone or changed since (a zone_edit
    Publish), a copy that is missing, or a read or write that fails is left, its entry kept. The caller holds the zone
    lock. Returns (entries kept, what was done)."""
    given = {zonepub_publish.key(d): Path(d) for d in zone_dirs}
    kept, said = [], []
    for e in entries:
        was = (ASIDE + '/' + e['file']) if e['file'] else 'nothing'
        d = given.get(e['dir'])
        if d is None:
            kept.append(e)
            said.append('%s not handled (no --zone-dir for it; it replaced %s)' % (e['dir'], was))
            continue
        path = d / (name + '.json')
        try:
            cur = zonepub_publish.read_file(path, MAX_ZONE)
        except (OSError, ValueError) as err:
            kept.append(e)
            said.append('%s cannot be read (%s): left (it replaced %s)' % (path, err, was))
            continue
        now_sha = hashlib.sha256(cur).hexdigest() if cur is not None else ''
        if now_sha != sha:
            if now_sha == e['sha']:     # already as before the upload (a remove that stopped after putting it back)
                drop_aside(store, [e])
                said.append('%s already as it was before the upload' % path)
                continue
            kept.append(e)
            said.append('%s is %s since the upload: left (it replaced %s)' % (path, 'gone' if cur is None else 'changed', was))
            continue
        prev = read_aside(store, e) if e['file'] else None
        if e['file'] and prev is None:
            kept.append(e)
            said.append('%s left: the copy of what it replaced (%s) is missing or changed' % (path, was))
            continue
        own = []
        try:
            own = keep_aside(store, name, stamp, [(path, cur)], 'removed')
            zonepub_publish.put([path], [prev], MAX_ZONE)
        except Exception as err:
            kept.append(e)
            said.append('%s cannot be written (%s): left (it replaced %s%s)' % (
                path, err, was, '; the upload\'s own copied to %s/%s' % (ASIDE, own[0]['file']) if own else ''))
            continue
        drop_aside(store, [e])          # back in place
        said.append('%s %s (the upload\'s own kept as %s/%s)' % (
            path, 'put back as it was before the upload' if prev is not None else 'taken out', ASIDE, own[0]['file']))
    return kept, said


def set_record(db_path, name, sha=None, entries=None, at=0):
    """upload_zones' row for `name` (entries None: deleted)."""
    with connect(db_path) as db, writing(db):
        if entries is None:
            db.execute('DELETE FROM upload_zones WHERE map=?', (name,))
        else:
            db.execute('INSERT OR REPLACE INTO upload_zones(map, sha, aside, at) VALUES(?,?,?,?)',
                       (name, sha, json.dumps(entries), at))


def published_since(zstore, name, at):
    """Whether zonepub has a publication of `name` queued at or after `at` (any kind: an identical publish is a
    noop row, and the file is then that publish's too), or None when its store cannot be read. No store at all:
    zonepub never ran here."""
    if not Path(zstore).exists():
        return False
    try:
        with connect(zstore, readonly=True) as z:
            return z.execute('SELECT 1 FROM publications WHERE map=? AND at>=? LIMIT 1', (name, at)).fetchone() is not None
    except sqlite3.Error:
        return None


def undo_zones(store, zstore, name, zone_dirs, r, stamp):
    """take_back for a record `r`, unless zonepub published the map since it was written (or that cannot be read):
    then the files are that publish's, and every entry is kept. Returns (entries kept, what was done)."""
    entries = json.loads(r['aside'])
    pub = published_since(zstore, name, r['at'])
    if pub is None:
        return entries, ['left: zonepub\'s history cannot be read, so whose zone files these are cannot be told']
    if pub:
        return entries, ['left: %s was published with zone_edit since, so its zone files are that publish\'s' % name]
    return take_back(store, name, zone_dirs, r['sha'], entries, stamp)


def peer_key(addr):
    # an IPv6 client holds a /64: a limit per address it can rotate would be no limit
    if ':' in addr:
        return ':'.join(addr.split(':')[:4]) + '::/64'
    return addr


def create_app(store, account_db, maps_dir, zone_dirs=(), media_dir=None, list_path=None, clock=time.time,
               verify=None, free_bytes=None, zone_check=None, zonepub_lock=None, lock_wait=LOCK_WAIT):
    app = Flask(__name__)
    store, account_db = Path(store), Path(account_db)
    db_path, spool = store / 'mapupd.db', store / 'spool'
    zone_dirs = tuple(Path(p) for p in zone_dirs)
    # where a name is looked for (every zone directory a lobby reads); written are only zone_dirs (zonepub's two)
    zone_check = tuple(Path(p) for p in (zone_check if zone_check is not None else zone_dirs))
    media_dir = Path(media_dir) if media_dir else None
    zonepub_lock = zonepub_lock or os.environ.get('MAPUPD_ZONEPUB_LOCK') or ZONEPUB_LOCK
    zonepub_store = Path(zonepub_lock).with_name('zones.sqlite3')      # zonepub_publish.locked's: beside its store
    if free_bytes is None:
        free_bytes = lambda: min(shutil.disk_usage(maps_dir).free, shutil.disk_usage(store).free)
    verifier = []
    seen, seen_lock = {}, threading.Lock()
    state_lock = threading.Lock()       # one finish at a time: two can never publish one name
    inflight, inflight_lock = set(), threading.Lock()   # (token, part) being received: one stream a file
    with connect(db_path) as db:
        secret = db.execute("SELECT v FROM meta WHERE k='secret'").fetchone()['v']
        db.execute(ZONES_SQL)       # P1799: a store `init` has not brought up to date yet (additive)

    def answer(**kw):
        return jsonify(ok=1, **kw)

    def fail(message, status=400):
        return jsonify(ok=0, error=message, status=status), 200

    def mac(*words):
        return hmac.new(secret.encode(), '\n'.join(words).encode(), hashlib.sha256).hexdigest()

    def code_for(stamp, salt, msha):
        return '%08x%s%s' % (stamp, salt, mac('code', '%08x' % stamp, salt, msha)[:16])

    @app.before_request
    def gate():
        # every route but a file's takes a small body, judged before a byte of it is read
        if request.path != '/mapup/api/part':
            size = request.content_length
            if size is None or size > SMALL_BODY:
                return fail('Invalid request.', 413)
        now, peer = time.monotonic(), peer_key(request.remote_addr or '')
        with seen_lock:
            if len(seen) > 4096:
                for k in [k for k, v in seen.items() if not v or now - v[-1] >= 60]:
                    del seen[k]
                # still full: the oldest go, so a crowd of addresses cannot lock everyone else out
                for k in sorted(seen, key=lambda k: seen[k][-1])[:len(seen) - 4096 + 1]:
                    del seen[k]
            hits = [t for t in seen.get(peer, ()) if now - t < 60]
            if len(hits) >= PEER_RATE:
                return fail('Too many requests; wait a minute.', 429)
            seen[peer] = hits + [now]

    @app.after_request
    def private(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.post('/mapup/api/health')
    def health():
        # the installer's probe: the store and surfd's accounts, read by the service itself inside its sandbox
        try:
            with connect(db_path, readonly=True) as db:
                db.execute('SELECT COUNT(*) FROM roles').fetchone()
            with connect(account_db, readonly=True) as main:
                main.execute('SELECT 1 FROM accounts LIMIT 1').fetchone()
        except sqlite3.Error:
            return fail('Unavailable.', 503)
        return answer(accounts=1)

    @app.post('/mapup/api/challenge')
    def challenge():
        data = request.get_json(silent=True)
        msha = data.get('manifest') if isinstance(data, dict) else None
        if not isinstance(msha, str) or not HEX64.fullmatch(msha):
            return fail('Invalid request.')
        return answer(nonce=code_for(int(clock()), secrets.token_hex(4), msha))

    def account(pub=None, sid=None):
        """(RANK_*, steamid) for a key, or for a Steam account (finish's second look)."""
        try:
            with connect(account_db, readonly=True) as main:
                if pub is not None:
                    return accounts.ranked_as(main, pub)
                row = main.execute('SELECT banned_at FROM accounts WHERE steamid=?', (sid,)).fetchone()
                return ((accounts.RANK_BANNED if row[0] else accounts.RANK_LINKED) if row else accounts.RANK_UNLINKED), sid
        except sqlite3.Error:
            raise Refused('Accounts cannot be read right now; try again later.')

    def has_role(db, sid):
        return db.execute('SELECT 1 FROM roles WHERE steamid=?', (sid,)).fetchone() is not None

    def drop_session(db, token):
        db.execute('DELETE FROM sessions WHERE token=?', (token,))
        for p in spool.glob(token + '.*'):
            p.unlink(missing_ok=True)

    @app.post('/mapup/api/begin')
    def begin():
        raw = request.get_data(cache=False)
        try:
            text = raw.decode('ascii')
            cut = text.rfind('\nnonce ') + 1      # the proof is the last three lines (an author may say "nonce ")
            if cut <= 0:
                raise Refused('That upload carries no account proof: update your game.')
            manifest, proof = text[:cut], text[cut:]
            pm = re.fullmatch(r'nonce ([0-9a-f]{32})\npub ([0-9a-f]{64})\nsig ([0-9a-f]{128})\n', proof)
            if not pm:
                raise Refused('That upload carries no account proof: update your game.')
            nonce, pub, sig = pm.groups()
            msha = hashlib.sha256(manifest.encode()).hexdigest()
            m = parse_manifest(manifest)
            now, stamp = int(clock()), int(nonce[:8], 16)
            if not (0 <= now - stamp <= CODE_TTL and hmac.compare_digest(nonce, code_for(stamp, nonce[8:16], msha))):
                raise Refused('That confirmation expired or is not for these files: press Upload again.')
            # the signature before the account: whether a key is linked is not anyone's to ask
            if not verifier:
                verifier.append(verify or ed25519_verifier())
            if not verifier[0](bytes.fromhex(pub), (STATEMENT % (SITE, nonce, msha)).encode(), bytes.fromhex(sig)):
                raise Refused('The account proof did not check out.')
            state, sid = account(pub=pub)
            if state in (accounts.RANK_UNLINKED, accounts.RANK_UNPROVEN):
                raise Refused('Link your Steam account in Settings first.')
            if state != accounts.RANK_LINKED:
                raise Refused('This Steam account cannot upload.')
            why = taken(m['map'], maps_dir, list_path, media_dir)
            if why:
                raise Refused(why)
            if free_bytes() < 2 * m['bsp'][1] + FREE_FLOOR:
                raise Refused('The server is short of disk space; ask Proto.')
            with connect(db_path) as db, writing(db):
                if not has_role(db, sid):
                    raise Refused('This Steam account is not a map uploader. Ask Proto for the role.')
                db.execute('DELETE FROM nonces WHERE seen<?', (now - CODE_TTL - 60,))
                try:
                    db.execute('INSERT INTO nonces VALUES(?,?)', (nonce, now))
                except sqlite3.IntegrityError:
                    raise Refused('That confirmation was used: press Upload again.')
                for old in db.execute('SELECT token FROM sessions WHERE created<?', (now - SESSION_TTL,)).fetchall():
                    drop_session(db, old['token'])
                # an earlier attempt at this map by the same account is replaced (a failed one must not lock anyone out)
                for old in db.execute('SELECT token, steamid FROM sessions WHERE map=?', (m['map'],)).fetchall():
                    if old['steamid'] != sid:
                        raise Refused('Someone else is uploading %s right now.' % m['map'])
                    drop_session(db, old['token'])
                # at three open, the oldest goes (attempts at other names must not lock anyone out either)
                for old in db.execute('SELECT token FROM sessions WHERE steamid=? ORDER BY created DESC LIMIT -1 OFFSET 2',
                                      (sid,)).fetchall():
                    drop_session(db, old['token'])
                n, kb = db.execute('SELECT COUNT(*), COALESCE(SUM(kb), 0) FROM uploads WHERE steamid=? AND at>?',
                                   (sid, now - 86400)).fetchone()
                if n >= DAY_UPLOADS or (kb + m['bsp'][1] // 1024) > DAY_KB:
                    raise Refused('That is today\'s limit for one account (%d maps, %d GB); try tomorrow.'
                                  % (DAY_UPLOADS, DAY_KB >> 20))
                token = secrets.token_hex(16)
                db.execute('INSERT INTO sessions(token, steamid, map, manifest, created) VALUES(?,?,?,?,?)',
                           (token, sid, m['map'], manifest, now))
            log('begin', m['map'], 'by', sid[-4:], msha[:12])
            need = [k for k in ('bsp', 'shot', 'zone') if m[k]]
            # P1799: zones already up for this name (published first, or Momentum's) are said plainly
            held = zones_held(m['map'], zone_check)
            return answer(session=token, need=' '.join(need), zones=1 if held else 0,
                          note=zones_note(m['map'], held, zone_dirs, m['zone'] is not None))
        except Refused as e:
            return fail(str(e))
        except (UnicodeDecodeError, ValueError):
            return fail('Invalid request.')

    def session(token, now):
        with connect(db_path) as db:
            row = db.execute('SELECT * FROM sessions WHERE token=? AND created>=?', (token, now - SESSION_TTL)).fetchone()
        if row is None:
            raise Refused('That upload expired: press Upload again.')
        return row, parse_manifest(row['manifest'])

    @app.post('/mapup/api/part')
    def part():
        # the session, part and encoding come in the URL and are checked before a byte of the body is read; a refused
        # body is never read (the connection closes), so nobody without a session can hold a thread with a slow one
        now, start = int(clock()), time.monotonic()
        size = request.content_length
        token, which, enc = request.args.get('s', ''), request.args.get('p', ''), request.args.get('e', '')
        if not (re.fullmatch('[0-9a-f]{32}', token) and which in ('bsp', 'shot', 'zone') and enc in ('raw', 'gzip')):
            return fail('That upload is not one this service reads: update your game.')
        if size is None or size <= 0 or size > MAX_BSP + (64 << 20):
            return fail('Upload too large.', 413)
        key = (token, which)
        tmp = spool / ('%s.%s.part' % (token, which))
        try:
            row, m = session(token, now)
        except Refused as e:
            return fail(str(e))
        if m[which] is None or which in row['got'].split():
            return fail('That file was not asked for.')
        want_sha, want_size = m[which][0], m[which][1]
        if size > want_size + (64 << 20):     # gzip can grow a little, never by this much
            return fail('That file is larger than the one confirmed: press Upload again.')
        with inflight_lock:
            if key in inflight:
                return fail('That file is already arriving.', 409)
            inflight.add(key)
        try:
            h, got = hashlib.sha256(), 0
            inflate = zlib.decompressobj(31) if enc == 'gzip' else None
            with open(tmp, 'wb') as out:
                def put(data):
                    nonlocal got
                    got += len(data)
                    if got > want_size:
                        raise Refused('That file is larger than the one confirmed: press Upload again.')
                    h.update(data)
                    out.write(data)
                def inflated(data):
                    if inflate.eof:     # nothing may follow the gzip stream (it would pile up in unused_data)
                        raise Refused('That file arrived damaged (data after its end): press Upload again.')
                    # a few MB a call, never past the confirmed size: a small gzip bomb stays small
                    put(inflate.decompress(data, min(want_size - got + 1, INFLATE_STEP)))
                    while inflate.unconsumed_tail:
                        put(inflate.decompress(inflate.unconsumed_tail, min(want_size - got + 1, INFLATE_STEP)))
                    if inflate.unused_data:
                        raise Refused('That file arrived damaged (data after its end): press Upload again.')
                while True:
                    chunk = request.stream.read(1 << 20)
                    if not chunk:
                        break
                    if time.monotonic() - start > PART_DEADLINE:
                        raise Refused('That file took over an hour; press Upload again on a faster connection.')
                    if inflate:
                        inflated(chunk)
                    else:
                        put(chunk)
                if inflate:
                    put(inflate.flush())
                    if not inflate.eof:
                        raise Refused('That file arrived cut short: press Upload again.')
            if got != want_size or not hmac.compare_digest(h.hexdigest(), want_sha):
                raise Refused('That file is not the one confirmed (it changed or arrived damaged): press Upload again.')
            os.replace(tmp, spool / ('%s.%s' % (token, which)))
            with connect(db_path) as db, writing(db):
                cur = db.execute('SELECT got FROM sessions WHERE token=?', (token,)).fetchone()
                if cur is None:
                    raise Refused('That upload expired: press Upload again.')
                done = sorted(set(cur['got'].split()) | {which})
                db.execute('UPDATE sessions SET got=? WHERE token=?', (' '.join(done), token))
            left = [k for k in ('bsp', 'shot', 'zone') if m[k] and k not in done]
            return answer(received=which, left=' '.join(left))
        except Refused as e:
            return fail(str(e))
        except zlib.error:
            return fail('That file arrived damaged (gzip): press Upload again.')
        finally:
            tmp.unlink(missing_ok=True)
            with inflight_lock:
                inflight.discard(key)

    def file_sha(path):
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(1 << 20), b''):
                h.update(block)
        return h.hexdigest()

    def publish(row, m, now):
        name, token = m['map'], row['token']
        bsp = spool / (token + '.bsp')
        # what lies in the spool is what was signed, read again (a part's check hashed its stream)
        for which in ('bsp', 'shot', 'zone'):
            if m[which] and file_sha(spool / ('%s.%s' % (token, which))) != m[which][0]:
                raise Refused('A file changed on the server before publishing; press Upload again.')
        check_bsp(bsp, m['bsp'][1])
        zone_body = None
        if m['zone']:
            zone_body = (spool / (token + '.zone')).read_bytes()
            try:
                zonepub.validate(zone_body)
            except (ValueError, TypeError, KeyError, RecursionError, UnicodeDecodeError):
                raise Refused('The zone file is not one the game reads (check it in the zone editor).')
        shot = spool / (token + '.shot') if m['shot'] else None
        final = Path(maps_dir) / (name + '.bsp')
        part = Path(maps_dir) / ('.mapupd.%s.bsp.part' % name)
        zone_paths = [d / (name + '.json') for d in zone_dirs] if zone_body is not None else []
        # P1799: what can fail without touching a shared file goes first (the pictures decoded, the BSP staged), so a
        # refused picture or a short disk never changes a zone file. Then, under zonepub's lock: zones, pictures, and
        # the BSP linked last, so nothing can fail once the map is live.
        pics = []
        if shot and media_dir:
            pics = list(zip((media_dir / 'uploads' / (name + '.jpg'), media_dir / 'uploads' / (name + '-thumb.jpg')),
                            render_pictures(shot)))
        aside, olds = [], []
        try:
            with open(bsp, 'rb') as src, open(part, 'wb') as dst:
                for block in iter(lambda: src.read(1 << 20), b''):
                    dst.write(block)
                dst.flush()
                os.fsync(dst.fileno())
            os.chmod(part, 0o644)       # nginx (www-data) serves the library
            with zone_lock(zonepub_lock, lock_wait), zonepub_publish.content_publication():
                why = taken(name, maps_dir, list_path, media_dir)
                if why:
                    raise Refused(why)
                reconcile(name, now)
                if zone_paths:
                    try:
                        olds = [zonepub_publish.read_file(z, MAX_ZONE) for z in zone_paths]
                    except (OSError, ValueError):
                        raise Refused('A zone file of that name on the server is not a plain zone file; tell Proto.')
                    aside = keep_aside(store, name, now, list(zip(zone_paths, olds)), 'replaced')
                    try:
                        set_record(db_path, name, m['zone'][0], aside, now)    # before the first zone write
                    except sqlite3.Error as e:
                        drop_aside(store, aside)
                        log('upload not recorded before its zones:', name, e)
                        raise Refused('The server could not record the upload; nothing was published.')
                    try:
                        zonepub_publish.put(zone_paths, [zone_body] * len(zone_paths), MAX_ZONE)
                    except zonepub_publish.PartialPublish:
                        log('ZONES PARTLY WRITTEN', name, '; what they replaced is in', ASIDE, aside_names(aside))
                        raise
                    except Exception:
                        undo(name, aside)       # put() restored the old files itself
                        raise
                written = []
                try:
                    for path, body in pics:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        atomic_write(path, body)
                        written.append(path)
                    os.link(part, final)        # never over a file that arrived meanwhile
                except Exception:
                    for path in written:        # taken() saw no BSP of this name: its pictures are this upload's
                        path.unlink(missing_ok=True)
                    if zone_paths:
                        # what was there before, byte for byte (None: there was none, so it goes)
                        try:
                            zonepub_publish.put(zone_paths, olds, MAX_ZONE)
                        except Exception as e:
                            log('ZONES NOT PUT BACK', name, e, '; what they replaced is in', ASIDE, aside_names(aside))
                            raise zonepub_publish.PartialPublish('zones not put back: %s' % e) from e
                        undo(name, aside)
                    raise
                u = dict(map=name, steamid=row['steamid'], at=now, bsp_sha=m['bsp'][0], kb=(m['bsp'][1] + 1023) // 1024,
                         mode=m['mode'], tier=m['tier'], stages=m['stages'], bonuses=m['bonuses'], author=m['author'],
                         shot=1 if shot else 0, zone=1 if zone_body else 0)
                try:
                    with connect(db_path) as db, writing(db):
                        db.execute('INSERT OR REPLACE INTO uploads VALUES(:map,:steamid,:at,:bsp_sha,:kb,:mode,:tier,'
                                   ':stages,:bonuses,:author,:shot,:zone)', u)
                        db.execute('INSERT OR REPLACE INTO upload_zones(map, sha, aside, at) VALUES(?,?,?,?)',
                                   (name, m['zone'][0] if zone_body is not None else '', json.dumps(aside), now))
                        drop_session(db, token)
                except sqlite3.Error as e:
                    log('PUBLISHED BUT NOT RECORDED', name, e, '; zones replaced are in', ASIDE, aside_names(aside))
                    raise Refused('%s is live, but the server could not record it (no list row yet); tell Proto.' % name)
        finally:
            part.unlink(missing_ok=True)
        try:
            heal(now)
        except Exception as e:      # the map is live and recorded: the minute tick heals the rows instead
            log('heal after publish failed:', e)
        replaced = aside_names(aside)
        log('published', name, m['bsp'][0][:12], 'by', row['steamid'][-4:], 'zones replaced %d' % len(replaced))
        held = zones_held(name, zone_check)
        if zone_body is not None:
            u['zones_note'] = (' Its zones replaced the ones already on the server; those are kept in the upload '
                               'service\'s store (zones-aside).' if replaced else ' Its zones are live with it.')
            first = outranking(held, zone_dirs)
            if first:
                u['zones_note'] += (' But lobbies read the copy in %s first, so that one still wins: ask Proto to take '
                                    'it out.' % ', '.join(where(d) for d in first))
        elif held:
            u['zones_note'] = ' It uses the zones already on the server.'
        else:
            u['zones_note'] = (' It has no zone file: runs on it can only be timed if the map has its own zone '
                               'triggers, until zones are published (zone editor, Publish saved).')
        return u

    def undo(name, aside):
        """A failed attempt whose zones were put back: its copies and its record go."""
        drop_aside(store, aside)
        try:
            set_record(db_path, name)
        except sqlite3.Error as e:
            log('record of a failed attempt at', name, 'not dropped:', e)

    def reconcile(name, now):
        """A record with no uploads row is an earlier attempt that crashed (or a remove left part done): its zone writes
        are undone first, so this upload replaces what was there before it, not its file."""
        with connect(db_path, readonly=True) as db:
            r = db.execute('SELECT sha, aside, at FROM upload_zones z WHERE map=? AND NOT EXISTS '
                           '(SELECT 1 FROM uploads u WHERE u.map=z.map)', (name,)).fetchone()
        if r is None:
            return
        kept, said = undo_zones(store, zonepub_store, name, zone_dirs, r, now) if r['sha'] else ([], [])
        log('earlier attempt at', name, 'undone:', '; '.join(said) or 'it wrote no zones')
        if kept:                    # the trail stays until this attempt's own record replaces it
            log('copies from it left in', ASIDE, aside_names(kept))
            set_record(db_path, name, r['sha'], kept, r['at'])
        else:
            set_record(db_path, name)

    def uploads():
        with connect(db_path, readonly=True) as db:
            return [dict(r) for r in db.execute('SELECT * FROM uploads ORDER BY at')]

    def heal(now=None):
        # only maps still in the library: one an operator took out loses its rows with mapwatch's next run
        us = [u for u in uploads() if library_has(maps_dir, u['map'])]
        today = time.strftime('%Y-%m-%d', time.gmtime(now or clock()))
        a = heal_list(list_path, us, today, log)
        b = heal_meta(media_dir / 'mapmeta.txt', us, log) if media_dir else 0
        if a or b:
            log('healed', a, 'list rows and', b, 'table rows')
        # and the spool: a file no open session owns (a crash between write and cleanup)
        with connect(db_path, readonly=True) as db:
            live = {r['token'] for r in db.execute('SELECT token FROM sessions')}
        cutoff = time.time() - 3600
        for p in spool.iterdir():
            try:
                if p.name.split('.')[0] not in live and p.stat().st_mtime < cutoff:
                    p.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
        return a, b
    app.config['MAPUPD_HEAL'] = heal

    @app.post('/mapup/api/finish')
    def finish():
        now = int(clock())
        raw = request.get_data(cache=False)
        tm = re.fullmatch(rb'session ([0-9a-f]{32})\n', raw)
        if not tm:
            return fail('Invalid request.')
        try:
            row, m = session(tm.group(1).decode(), now)
            need = [k for k in ('bsp', 'shot', 'zone') if m[k]]
            if sorted(need) != sorted(row['got'].split()):
                raise Refused('Not every file has arrived yet.')
            # a role revoked or an account banned since begin stops it here
            if account(sid=row['steamid'])[0] != accounts.RANK_LINKED:
                raise Refused('This Steam account cannot upload.')
            with connect(db_path) as db:
                if not has_role(db, row['steamid']):
                    raise Refused('This Steam account is not a map uploader. Ask Proto for the role.')
            if not state_lock.acquire(timeout=30):
                raise Refused('Another map is being published; try again in a minute.')
            try:
                u = publish(row, m, now)
            finally:
                state_lock.release()
            return answer(published=1, map=u['map'], note='%s is live: lobbies can load it now, and everyone sees it in '
                          'their map list within a minute (they download it on first play).%s' % (u['map'],
                                                                                                  u['zones_note']))
        except Refused as e:
            return fail(str(e))
        except zonepub_publish.PartialPublish as e:
            log('partial zone publish:', e)
            return fail('The zone files could not all be written or put back; nothing was published. Tell Proto.', 500)
        except sqlite3.Error as e:
            log('publish failed (store):', e)
            return fail('The server could not record the upload; nothing was published.', 500)
        except OSError as e:
            log('publish failed:', e)
            return fail('The map could not be written on the server; nothing was published.', 500)

    return app


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--store', type=Path, required=True)
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    for word in ('grant', 'revoke'):
        sub.add_parser(word).add_argument('--identity-file', type=Path, required=True,
                                         help='private file holding the approved SteamID64')
    gz = sub.add_parser('grant-zone-admins', help="give the zone service's admins the map role")
    gz.add_argument('--zonepub-store', type=Path, default=Path('/srv/nvme/ftesurf-ops/zonepub-state/zones.sqlite3'))
    rm = sub.add_parser('remove', help='take an upload back')
    rm.add_argument('--map', required=True)
    rm.add_argument('--maps', required=True)
    rm.add_argument('--zone-dir', action='append')
    rm.add_argument('--media')
    rm.add_argument('--list')
    rm.add_argument('--zonepub-lock', default=os.environ.get('MAPUPD_ZONEPUB_LOCK') or ZONEPUB_LOCK,
                    help="zonepub's publish.lock, held while zone files change")
    sub.add_parser('roles', help='how many accounts hold the role (never the ids)')
    sub.add_parser('list', help='published uploads')
    args = ap.parse_args()
    if args.command == 'init':
        initialize(args.store)
        print('Initialized', args.store)
        return
    db_path = args.store / 'mapupd.db'
    if args.command in ('grant', 'revoke'):
        sid = args.identity_file.read_text().strip()
        if not re.fullmatch(r'7656119[0-9]{10}', sid):
            ap.error('Expected a SteamID64 in the private identity file')
        with connect(db_path) as db, writing(db):
            if args.command == 'grant':
                db.execute('INSERT OR IGNORE INTO roles VALUES(?)', (sid,))
            else:
                db.execute('DELETE FROM roles WHERE steamid=?', (sid,))
                gone = [r['token'] for r in db.execute('SELECT token FROM sessions WHERE steamid=?', (sid,))]
                db.execute('DELETE FROM sessions WHERE steamid=?', (sid,))
                for t in gone:
                    for f in (args.store / 'spool').glob(t + '.*'):
                        f.unlink(missing_ok=True)
        print('Map role updated')
    elif args.command == 'grant-zone-admins':
        # the zone service's admins get the map role too, the ids never printed
        with connect(args.zonepub_store, readonly=True) as z:
            sids = [r[0] for r in z.execute('SELECT steamid FROM roles') if re.fullmatch(r'7656119[0-9]{10}', r[0])]
        with connect(db_path) as db, writing(db):
            for sid in sids:
                db.execute('INSERT OR IGNORE INTO roles VALUES(?)', (sid,))
        print('Granted the map role to the %d zone admins' % len(sids))
    elif args.command == 'remove':
        # an upload taken back, all under zonepub's lock (a finish of the same name waits, and cannot slip between the
        # read and the writes): the BSP aside, the zones it placed (P1799: what they replaced put back; zones it did not
        # bring, from before P1799, or published since, left) with the record updated at once, pictures and table rows,
        # and the uploads row last. Every step can be run again (heal skips a map whose BSP is gone).
        name = args.map
        if not NAME.fullmatch(name):
            ap.error('Expected an uploaded map name')
        maps = Path(args.maps)
        old = maps / '.old'
        old.mkdir(exist_ok=True)
        stamp = int(time.time())
        kept, moved = [], None
        try:
            with zone_lock(args.zonepub_lock, 120), zonepub_publish.content_publication():
                with connect(db_path) as db, writing(db):
                    db.execute(ZONES_SQL)   # a store `init` has not brought up to date
                    up = db.execute('SELECT zone FROM uploads WHERE map=?', (name,)).fetchone()
                    zr = db.execute('SELECT sha, aside, at FROM upload_zones WHERE map=?', (name,)).fetchone()
                if up is None and zr is None:
                    raise Refused('%s is not an upload' % name)
                if (maps / (name + '.bsp')).exists():
                    moved = old / ('%s.removed-%d.bsp' % (name, stamp))
                    os.replace(maps / (name + '.bsp'), moved)
                if zr is None:
                    said = ['left as they are: ' + ('this upload is from before P1799, so which zone files it brought is '
                                                    'not recorded' if up['zone'] else 'the upload brought none')]
                elif not zr['sha']:
                    said = ['left as they are: the upload brought none']
                else:
                    kept, said = undo_zones(args.store, Path(args.zonepub_lock).with_name('zones.sqlite3'), name,
                                            [Path(d) for d in args.zone_dir or ()], zr, stamp)
                    with connect(db_path) as db, writing(db):   # progress, before anything else can fail
                        db.execute('UPDATE upload_zones SET aside=? WHERE map=?', (json.dumps(kept), name))
                if args.media:
                    for f in (name + '.jpg', name + '-thumb.jpg'):
                        (Path(args.media) / 'uploads' / f).unlink(missing_ok=True)
                    drop_rows(Path(args.media) / 'mapmeta.txt', 'meta ' + name + ' ', meta=True)
                if args.list:
                    drop_rows(Path(args.list), 'dl ' + name + ' ')
                with connect(db_path) as db, writing(db):
                    if not kept:            # what was not acted on stays recorded, for a re-run
                        db.execute('DELETE FROM upload_zones WHERE map=?', (name,))
                    db.execute('DELETE FROM uploads WHERE map=?', (name,))
        except Refused as e:
            ap.error(str(e))
        print('Removed %s (%s); zones: %s' % (name, 'its BSP is now %s' % moved if moved else 'no BSP of it was in the library',
                                             '; '.join(said) or 'all handled already'))
        if kept:
            print('%d zone directories are still recorded for %s: run remove again once they can be handled.'
                  % (len(kept), name))
            sys.exit(1)
    elif args.command == 'roles':
        with connect(db_path, readonly=True) as db:
            print(db.execute('SELECT COUNT(*) FROM roles').fetchone()[0], 'accounts hold the map role')
    elif args.command == 'list':
        with connect(db_path, readonly=True) as db:
            zt = db.execute("SELECT 1 FROM sqlite_master WHERE name='upload_zones'").fetchone()
            q = ('SELECT u.map, at, kb, mode, tier, stages, bonuses, shot, zone, %s AS aside FROM uploads u %s ORDER BY at'
                 % (("z.aside", "LEFT JOIN upload_zones z ON z.map=u.map") if zt else ("NULL", "")))
            for r in db.execute(q):
                print('%s %s %d KB %s tier %d stages %d bonuses %d shot %d zone %d%s' % (
                    r['map'], time.strftime('%Y-%m-%d %H:%MZ', time.gmtime(r['at'])), r['kb'], r['mode'], r['tier'],
                    r['stages'], r['bonuses'], r['shot'], r['zone'],
                    ' (replaced %d zone files)' % len(json.loads(r['aside'])) if r['aside'] and r['aside'] != '[]' else ''))


if __name__ == '__main__':
    main()
