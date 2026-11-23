#!/usr/bin/env python3
"""P1746: owner/root installation of the isolated map upload service (surfd/mapupd.py); default dry run.

The TAS service's installer (tools/install_tasupd.py) with the names, files, unit and nginx routes changed: a clean inspected
source commit, an exact nginx predecessor hash and --apply; the files are the commit's git objects; run it as
`sudo python3 -I` and it refuses to be anything but that commit's own tools/install_mapupd.py; releases go under
RELEASES (/opt, root's alone); the state directory is chowned through its fd; git and the import check run as
proto. Never changes or restarts surfd, its DB, another service or a lobby; grants no roles (as proto:
`mapupd.py --store <state> grant-zone-admins` or `grant --identity-file F`). Refuses existing destinations.

nginx: /mapup/api/part takes up to 1100m unbuffered (a 1 GB body must not spool to the root filesystem), two
connections an address; every other /mapup/api/ route takes 8k; /ftesurf/media/uploads/ serves the pictures.

--upgrade-from <installed commit>: a new release, the unit pointed at it, the old one put back if it does not serve.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path('/srv/nvme/ftesurf-ops/mapupd')     # no release is ever written here (proto's tree); kept for checks
RELEASES = Path('/opt/ftesurf-mapupd')
STATE = Path('/srv/nvme/ftesurf-ops/mapupd-state')
ENABLED = Path('/etc/nginx/sites-enabled/play.proto.bar.conf')
SITE = ENABLED.resolve() if ENABLED.is_symlink() else ENABLED
BACKUPS = Path('/etc/nginx')   # never sites-enabled: a backup there would be loaded as config
SNIPPET = Path('/etc/nginx/snippets/ftesurf-mapupd.conf')
ZONES = Path('/etc/nginx/conf.d/ftesurf-mapupd-zones.conf')   # http{} scope: limit_conn_zone is not valid lower
UNIT = Path('/etc/systemd/system/ftesurf-mapupd.service')
PORT = 8096                 # free on the Pi (8087 zonepub, 8093 tasupd, 8095 taken; checked 23 Nov)
PUBLIC_URL = 'https://play.proto.bar/mapup'
MAPS = '/srv/nvme/ftesurf-server/game/momentum/maps'
ZONE_DIRS = ['/srv/nvme/ftesurf-server/game/ftesurf/maps/zones/local', '/srv/nvme/ftesurf-site/zones']   # zonepub's
# every zone directory a lobby reads (the TAS installer's list): a name with zones in any of them is not new
ZONE_CHECK = ['/srv/nvme/ftesurf-server/game/%s/maps/zones/%s' % d for d in (
    ('ftesurf', 'local'), ('ftesurf', 'curated'), ('momentum', 'curated'), ('momentum', 'local'),
    ('ftesurf', 'online'), ('momentum', 'online'))] + ['/srv/nvme/ftesurf-site/zones']
MEDIA = '/srv/nvme/ftesurf-site/media'
LIST = '/srv/nvme/surfd/data/mapwatch/mapdl.txt'
NGINX = """location = /mapup/api/part {
    limit_except POST { deny all; }
    client_max_body_size 1100m;   # mapupd.MAX_BSP and a gzip's slack
    proxy_request_buffering off;  # straight to the service's spool on the NVMe, not nginx's temp on the root fs
    client_body_timeout 20s;      # between reads
    proxy_pass http://127.0.0.1:%d;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_http_version 1.1;
    proxy_connect_timeout 2s;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
    limit_conn mapupd_addr 2;
    limit_conn mapupd_all 4;      # of the service's eight threads: challenge, begin, finish and health keep four
    access_log off;
}
location ^~ /mapup/api/ {
    limit_except POST { deny all; }
    client_max_body_size 8k;      # challenge, begin, finish, health (mapupd.SMALL_BODY)
    proxy_pass http://127.0.0.1:%d;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_connect_timeout 2s;
    proxy_read_timeout 300s;      # finish hashes and copies up to 1 GB
    proxy_send_timeout 60s;
    access_log off;
}
location ~ "^/ftesurf/media/uploads/(?<fteup>[a-z0-9_-]{1,64})(?<fteupk>-thumb)?\\.jpg$" {
    root /srv/nvme/ftesurf-site/media/uploads;
    try_files /$fteup$fteupk.jpg =404;
    default_type image/jpeg;
    add_header Cache-Control "public, max-age=3600";
    autoindex off;
    disable_symlinks if_not_owner;
}
""" % (PORT, PORT)
NGINX_ZONES = """# ftesurf-mapupd (tools/install_mapupd.py): the snippet's connection limits.
limit_conn_zone $binary_remote_addr zone=mapupd_addr:2m;
limit_conn_zone $server_name zone=mapupd_all:64k;
"""
FILES = {'surfd/mapupd.py': 'mapupd.py', 'surfd/mapupd_wsgi.py': 'mapupd_wsgi.py', 'surfd/mapmanifest.py': 'mapmanifest.py',
         'surfd/zonepub.py': 'zonepub.py', 'surfd/zonepub_publish.py': 'zonepub_publish.py', 'surfd/tascontent.py': 'tascontent.py',
         'surfd/accounts.py': 'accounts.py', 'surfd/steam.py': 'steam.py', 'surfd/rcon.py': 'rcon.py',
         'surfd/ksfprofile.py': 'ksfprofile.py', 'surfd/momprofile.py': 'momprofile.py', 'tools/ed25519.py': 'tools/ed25519.py'}


def sha(body): return hashlib.sha256(body).hexdigest()
def why(e):
    # A CalledProcessError's repr leaves out what the command said (review 5: `nginx -t` failed without saying why).
    err = getattr(e, 'stderr', None)
    return '%r%s' % (e, (': ' + err.decode(errors='replace').strip()[-400:]) if isinstance(err, bytes) and err.strip() else '')
def run(*args, timeout=30, **kw): return subprocess.run(args, check=True, capture_output=True, timeout=timeout, **kw)
def as_user(name, *args):
    # P1119: as root, a command over a proto-owned tree runs as its owner (repo config, release code).
    return (('/usr/sbin/runuser', '-u', name, '--') + args) if os.geteuid() == 0 else args
def safe_path(p):
    if not re.fullmatch(r'/[a-zA-Z0-9_./-]+', str(p)) or '..' in Path(p).parts: raise ValueError('Unsafe configured path')


def check_accounts(path):
    # immutable: root must not recreate surfd's -wal/-shm, which would hide the sandboxed reader's view
    # (AGENT_NOTES P1618); the health probe reads it as the service does. runs: the course records.
    with contextlib.closing(sqlite3.connect('file:' + str(path) + '?mode=ro&immutable=1', uri=True)) as db:
        db.execute('SELECT steamid,name,banned_at FROM accounts LIMIT 0')
        db.execute('SELECT pub,steamid FROM keylinks LIMIT 0')


def write_site(body):
    # Whole or not at all: written beside the backups (never sites-enabled, which nginx includes) and
    # renamed over the site file, keeping its mode and owner.
    st = SITE.stat()
    tmp = BACKUPS / ('.mapupd-site-%d.tmp' % os.getpid())
    try:
        with open(tmp, 'xb') as f:
            f.write(body); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, stat.S_IMODE(st.st_mode)); os.chown(tmp, st.st_uid, st.st_gid)
        os.replace(tmp, SITE)
    finally:
        if tmp.exists(): tmp.unlink()


def pending_reloads():
    # daemon-reload loads every unit's staged edits (a peer's surfd drop-in too): refused while any waits.
    # --all: without it systemctl shows only active units, and a stopped one's staged edit would load too.
    out = run('/usr/bin/systemctl', 'show', '--all', '--property=Id,NeedDaemonReload', '*').stdout.decode()
    units, cur = [], None
    for line in out.splitlines():
        if line.startswith('Id='): cur = line[3:]
        elif line == 'NeedDaemonReload=yes' and cur: units.append(cur)
    if units: raise RuntimeError('Units with edits systemd has not loaded (daemon-reload would load them): %s' % ', '.join(units))


def check_self(source, commit):
    # The installer that runs as root must be the inspected commit's own, in a file only root can change
    # (taken out of git into /root and run as `sudo python3 -I`).
    me = Path(__file__).resolve()
    if me.read_bytes() != git(source, 'cat-file', 'blob', '%s:tools/install_mapupd.py' % commit):
        raise RuntimeError('This installer is not tools/install_mapupd.py of %s; run that one' % commit[:12])
    if os.geteuid() == 0:
        root_only(me)


def root_only(path):
    for q in [path] + list(path.parents):
        st = os.lstat(q)
        if st.st_uid != 0 or st.st_mode & 0o022:
            raise RuntimeError('%s can be changed by someone other than root: copy the installer to /root' % q)


def make_state():
    # Root in directories proto owns (/srv/nvme is proto's on the Pi): every step from / by descriptor
    # with O_NOFOLLOW, so no symlink swap can redirect the mkdir or the chown.
    owner = pwd.getpwnam('proto')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open('/', flags)
    try:
        for part in STATE.parent.parts[1:]:
            nxt = os.open(part, flags, dir_fd=fd); os.close(fd); fd = nxt
        os.mkdir(STATE.name, 0o700, dir_fd=fd)
        st = os.open(STATE.name, flags, dir_fd=fd)
        try: os.fchown(st, owner.pw_uid, owner.pw_gid)
        finally: os.close(st)
    finally:
        os.close(fd)


def check_port():
    with socket.socket() as probe: probe.bind(('127.0.0.1', PORT))


def check_imports(blobs):
    # The release directory holds only FILES: they must import with nothing else beside them, as proto.
    with tempfile.TemporaryDirectory() as d:
        for dest, body in blobs.items():
            p = Path(d) / dest; p.parent.mkdir(parents=True, exist_ok=True); p.parent.chmod(0o755); p.write_bytes(body); p.chmod(0o644)
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
        env['SURFD_TOOLS'] = str(Path(d) / 'tools')
        try: run(*as_user('proto', sys.executable, '-c', 'import mapupd, PIL.Image; mapupd.ed25519_verifier()'), cwd=d, env=env)
        except subprocess.CalledProcessError as e:
            raise RuntimeError('Service files do not import on their own: ' + (e.stderr or b'').decode(errors='replace')[-400:])


def probe_app(commit, url='http://127.0.0.1:%d/mapup/api/health' % PORT):
    # ok only when the service read its store and surfd's accounts itself, inside its sandbox.
    req = urllib.request.Request(url, data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.headers.get('X-Mapupd-Source') != commit: raise RuntimeError('Unexpected serving source')
        body = json.loads(response.read(65536))
    if body.get('ok') != 1 or body.get('accounts') != 1: raise RuntimeError('New service health control did not act')


def init_store(release):
    run('/usr/sbin/runuser', '-u', 'proto', '--', '/usr/bin/python3', str(release / 'mapupd.py'), '--store', str(STATE), 'init',
        cwd=str(release), env=dict(PATH='/usr/bin:/bin', SURFD_TOOLS=str(release / 'tools')))


def old_units(old, account_db, commit):
    """The unit this installer writes for the release `old` (the first mapupd installer: one shape)."""
    return (unit_text(old, service_env(old, account_db, commit)).encode(),)


def service_env(release, account_db, commit):
    return dict(MAPUPD_STORE=str(STATE), MAPUPD_ACCOUNTS=str(account_db), MAPUPD_MAPS=MAPS,
                MAPUPD_ZONES=json.dumps(ZONE_DIRS, separators=(',', ':')), MAPUPD_MEDIA=MEDIA, MAPUPD_LIST=LIST,
                MAPUPD_ZONECHECK=json.dumps(ZONE_CHECK, separators=(',', ':')),
                SURFD_TOOLS=str(release / 'tools'), MAPUPD_SOURCE=commit)


def write_release(release, commit, blobs):
    # Modes set outright: an owner's umask 077 would leave proto unable to enter the release.
    release.mkdir(parents=True, mode=0o755); release.chmod(0o755)
    for dest, body in blobs.items():
        p = release / dest
        if p.parent != release: p.parent.mkdir(exist_ok=True); p.parent.chmod(0o755)
        p.write_bytes(body); p.chmod(0o644)
    src = release / 'SOURCE.json'
    src.write_text(json.dumps(dict(commit=commit, files={k: sha(v) for k, v in blobs.items()}), indent=2) + '\n'); src.chmod(0o644)


def git(source, *args):
    # As proto whoever owns the checkout: a repository's config then acts as proto at worst. The
    # command-line safe.directory lets proto read a root-owned checkout; SUDO_* is not passed on.
    env = {k: v for k, v in os.environ.items() if not k.startswith('SUDO_')}
    return run(*as_user('proto', 'git', '-c', 'safe.directory=' + str(source), '-C', str(source), '-c', 'core.fsmonitor=false',
                        *args), env=env).stdout


def commit_blobs(source, commit):
    # The commit's own bytes, not the working tree's (skip-worktree hides edits from status).
    return {dest: git(source, 'cat-file', 'blob', '%s:%s' % (commit, src)) for src, dest in FILES.items()}


def await_probe(commit, url=None, tries=20, pause=.25):
    for attempt in range(tries):
        try: probe_app(commit, url) if url else probe_app(commit); return
        except (OSError, ValueError, RuntimeError):
            if attempt == tries - 1: raise
            time.sleep(pause)


def replace_unit(body):
    tmp = UNIT.with_name(UNIT.name + '.upgrade-new')
    tmp.write_bytes(body); tmp.chmod(0o644); os.replace(tmp, UNIT)


def unit_property(name):
    return run('/usr/bin/systemctl', 'show', '--value', '--property=' + name, 'ftesurf-mapupd.service').stdout.decode().strip()


def check_chain(path):
    # Root writes the release here: the directory and all above it must be root's, unlinked, unshared.
    for p in [path] + list(path.parents):
        st = os.lstat(p)
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise RuntimeError('%s is not a directory only root can write' % p)


def rollback(oldunit, newunit, oldcommit, why):
    """Puts the old unit back and proves it serves; returns what happened, for the error."""
    stage = 'the old unit could not be put back; the new one is on disk'
    try:
        if UNIT.read_bytes() != newunit:
            return 'upgrade failed (%r) and the unit changed meanwhile: left as it is; owner inspection' % why
        replace_unit(oldunit)
        stage = 'the old unit file is back but systemd may still run the new release'
        try: run('/usr/bin/systemctl', 'reset-failed', 'ftesurf-mapupd.service')
        except subprocess.CalledProcessError: pass   # not failed: nothing to reset
        run('/usr/bin/systemctl', 'daemon-reload')
        run('/usr/bin/systemctl', 'restart', 'ftesurf-mapupd.service', timeout=120)
        stage = 'the old unit is back and restarted but did not serve'
        await_probe(oldcommit)
    except BaseException as e:
        return 'upgrade failed (%r); %s (%r): systemctl status ftesurf-mapupd' % (why, stage, e)
    return 'upgrade failed (%r); rolled back, %s serves again (the new release directory stays)' % (why, oldcommit[:12])


def say(line):
    try: print(line, flush=True)
    except OSError: pass   # a dropped session's terminal; UPGRADE.txt has it


def record(release, outcome):
    # First, for an owner whose session dropped (a print to its closed terminal can fail).
    try: (release / 'UPGRADE.txt').write_text(outcome + '\n')
    except OSError as e: say('(could not write %s: %s)' % (release / 'UPGRADE.txt', e))


def record_install(release, outcome):
    try: (release / 'INSTALL.txt').write_text(outcome + '\n')
    except OSError as e: say('(could not write %s: %s)' % (release / 'INSTALL.txt', e))


def older_releases(keep):
    """Release directories other than `keep` (P1702, Lex 21 Nov: the serving release and its rollback, no more).
    Only this installer's own: a commit-named directory whose SOURCE.json names that commit; never a link."""
    out = []
    for p in sorted(RELEASES.iterdir()) if RELEASES.is_dir() else []:
        if p.name in keep or not re.fullmatch(r'[0-9a-f]{40}', p.name) or not stat.S_ISDIR(os.lstat(p).st_mode):
            continue
        try: commit = json.loads((p / 'SOURCE.json').read_text()).get('commit')
        except (OSError, ValueError): continue
        if commit == p.name: out.append(p)
    return out


def prune_releases(keep):
    gone = []
    for p in older_releases(keep):
        try: shutil.rmtree(p); gone.append(p.name[:12])
        except OSError as e: say('(could not remove the old release %s: %s)' % (p, e))
    return gone


def upgrade(a, blobs):
    """The installed release `a.upgrade_from` -> `a.commit`; see the module doc."""
    old = RELEASES / a.upgrade_from
    new = RELEASES / a.commit
    if a.upgrade_from == a.commit: raise RuntimeError('Upgrade to the installed commit')
    if any(p.exists() or p.is_symlink() for p in (new, ROOT / a.commit)): raise RuntimeError('The new release directory already exists')
    if json.loads((old / 'SOURCE.json').read_text()).get('commit') != a.upgrade_from:
        raise RuntimeError('The old release directory is not that commit')
    oldunit = UNIT.read_bytes()   # put back as read, if the switch fails
    if oldunit not in old_units(old, a.account_db, a.upgrade_from):
        raise RuntimeError('The unit is not the one this installer wrote for that release; owner inspection')
    if SNIPPET.read_bytes() != NGINX.encode() or ZONES.read_bytes() != NGINX_ZONES.encode():
        raise RuntimeError('The nginx snippet or its zones changed; owner inspection')
    if not (STATE / 'mapupd.db').is_file(): raise RuntimeError('Service state missing')
    if unit_property('ActiveState') != 'active': raise RuntimeError('The service is not running; owner inspection')
    if unit_property('DropInPaths') or unit_property('NeedDaemonReload') != 'no' or unit_property('FragmentPath') != str(UNIT):
        raise RuntimeError('The unit has drop-ins, a pending reload or another unit file; owner inspection')
    check_chain(RELEASES if RELEASES.exists() or RELEASES.is_symlink() else RELEASES.parent)
    probe_app(a.upgrade_from)   # what serves now is the old release
    check_accounts(a.account_db)
    pending_reloads()
    check_imports(blobs)
    print('Preflight (upgrade): the commit\'s files, the unit and snippet this installer wrote for %s, state present, serving it'
          % a.upgrade_from[:12])
    older = older_releases((a.commit, a.upgrade_from))
    if older: print('Once it serves, removes the older releases: %s' % ', '.join(p.name[:12] for p in older))
    if not a.apply:
        print('DRY RUN: no changes; owner may rerun under sudo with --apply')
        return
    if os.geteuid() != 0: raise RuntimeError('Owner sudo/root is required for --apply')
    RELEASES.mkdir(mode=0o755, exist_ok=True); RELEASES.chmod(0o755)
    check_chain(RELEASES)
    write_release(new, a.commit, blobs)
    try: init_store(new)   # additive schema steps; the old release keeps serving the store meanwhile
    except Exception as e:
        shutil.rmtree(new)     # root's own release directory, just written: a retry must not find it (review 8)
        raise RuntimeError('the store could not be prepared (%s); nothing switched, the new release removed' % why(e)) from e
    newunit = unit_text(new, service_env(new, a.account_db, a.commit)).encode()
    if UNIT.read_bytes() != oldunit: raise RuntimeError('The unit changed during the upgrade; nothing switched (the new release directory stays)')
    # The switch and its proof are one step: Ctrl-C or a dropped session must not leave the unit ahead of systemd.
    held = {n: signal.signal(n, signal.SIG_IGN) for n in (signal.SIGINT, signal.SIGHUP)}
    try:
        replace_unit(newunit)
        try:
            run('/usr/bin/systemctl', 'daemon-reload')
            run('/usr/bin/systemctl', 'restart', 'ftesurf-mapupd.service', timeout=120)
            await_probe(a.commit)
            await_probe(a.commit, PUBLIC_URL + '/api/health', pause=.5)
        except BaseException as e:
            outcome = rollback(oldunit, newunit, a.upgrade_from, e)
            record(new, outcome); say(outcome)
            raise RuntimeError(outcome) from e
    finally:
        for n, h in held.items(): signal.signal(n, h)
    # the unit it replaced, as read: going back by hand (an older installer refuses the newer unit: ops review 2)
    try: (new / 'unit.prev').write_bytes(oldunit); (new / 'unit.prev').chmod(0o644)
    except OSError as e: say('(could not keep the old unit in %s: %s)' % (new / 'unit.prev', e))
    outcome = 'Upgraded the map upload service to %s (the old release stays at %s; its unit is %s)' % (a.commit, old, new / 'unit.prev')
    gone = prune_releases((a.commit, a.upgrade_from))
    if gone: outcome += '; removed older releases %s' % ', '.join(gone)
    record(new, outcome); say(outcome)


def unit_text(release, env):
    entries = ''.join('Environment="%s=%s"\n' % (k, v.replace('\\', '\\\\').replace('"', '\\"')) for k, v in env.items())
    return """[Unit]
Description=World of Surf admin map uploads (mapupd, P1746)
After=network.target
[Service]
User=proto
Group=proto
UMask=0022
WorkingDirectory=%s
ExecStart=/usr/bin/python3 -m gunicorn --bind 127.0.0.1:%d --workers 1 --threads 8 --timeout 120 --access-logfile /dev/null mapupd_wsgi:app
%sRestart=on-failure
MemoryMax=768M
MemorySwapMax=0
CPUQuota=50%%
Nice=10
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
ReadWritePaths=%s
[Install]
WantedBy=multi-user.target
""" % (release, PORT, entries, ' '.join([str(STATE), MAPS] + ZONE_DIRS + [MEDIA, str(Path(LIST).parent)]))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--expected-nginx-sha256')
    ap.add_argument('--upgrade-from', help='the installed release commit to replace')
    ap.add_argument('--account-db', type=Path, default=Path('/srv/nvme/surfd/data/surfd.db'))
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', a.commit): ap.error('Expected full inspected source SHA')
    if a.upgrade_from is not None:
        if not re.fullmatch('[0-9a-f]{40}', a.upgrade_from): ap.error('--upgrade-from: the installed commit, 40 lowercase hex')
        if a.expected_nginx_sha256: ap.error('An upgrade does not change nginx')
    elif not re.fullmatch('[0-9a-f]{64}', a.expected_nginx_sha256 or ''): ap.error('Expected exact predecessor nginx SHA256')
    for p in (a.source, a.account_db): safe_path(p)
    if git(a.source, 'rev-parse', 'HEAD').decode().strip() != a.commit: raise RuntimeError('Source ref differs')
    check_self(a.source, a.commit)
    blobs = commit_blobs(a.source, a.commit)
    if a.upgrade_from is not None:
        upgrade(a, blobs)
        return
    before = SITE.read_bytes()
    if sha(before) != a.expected_nginx_sha256: raise RuntimeError('nginx changed; inspect again')
    anchor = b'include snippets/surfd.conf;'
    if before.count(anchor) != 1: raise RuntimeError('Expected one existing public surfd include')
    if any(p.exists() or p.is_symlink() for p in (SNIPPET, ZONES, UNIT, STATE, ROOT / a.commit, RELEASES / a.commit)):
        raise RuntimeError('Destination already exists; do not overwrite a peer/previous installation')
    if not a.account_db.is_file(): raise RuntimeError('Configured accounts DB absent')
    check_accounts(a.account_db)
    check_port()
    if run('/usr/bin/systemctl', 'show', '--value', '--property=LoadState', 'ftesurf-mapupd.service').stdout.decode().strip() != 'not-found':
        raise RuntimeError('Existing loaded unit requires owner inspection')
    check_imports(blobs)
    check_chain(RELEASES if RELEASES.exists() or RELEASES.is_symlink() else RELEASES.parent)
    backup = BACKUPS / (SITE.name + '.pre-mapupd-' + a.commit[:12])
    if backup.exists(): raise RuntimeError('nginx backup collision; nothing overwritten')
    try: run(*as_user('proto', '/usr/bin/python3', '-I', '-c', 'import flask,gunicorn'), cwd='/')   # as the service will
    except subprocess.CalledProcessError as e: raise RuntimeError('flask/gunicorn do not import as proto: %s' % why(e)) from e
    if os.geteuid() == 0:
        run('/usr/sbin/nginx', '-t')   # a config that fails already would also fail the rollback's test
        if b'zone=mapupd_' in run('/usr/sbin/nginx', '-T').stdout:
            raise RuntimeError('nginx already defines a mapupd_ zone; owner inspection')
    else:
        print('(not root: nginx -t is left to the --apply run; it reads root-only keys and logs)')
    pending_reloads()
    owner = pwd.getpwnam('proto').pw_uid
    for d in [MAPS, MEDIA, str(Path(LIST).parent)] + ZONE_DIRS:   # the publish targets: real, proto's (the service is proto)
        st = os.lstat(d)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != owner: raise RuntimeError('%s is not a directory proto owns' % d)
    print('Preflight: the files of that commit, exact nginx predecessor, separate new service/state; publishes into %s, %s, '
          '%s/uploads and rows into %s' % (MAPS, ', '.join(ZONE_DIRS), MEDIA, LIST))
    if not a.apply:
        print('DRY RUN: no changes; owner may rerun under sudo with --apply')
        return
    if os.geteuid() != 0: raise RuntimeError('Owner sudo/root is required for --apply')
    RELEASES.mkdir(mode=0o755, exist_ok=True); RELEASES.chmod(0o755)
    check_chain(RELEASES)
    release = RELEASES / a.commit   # root's alone, as upgrades are (not under proto's /srv/nvme/ftesurf-ops)
    write_release(release, a.commit, blobs)
    make_state()
    try: init_store(release)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise RuntimeError('the store could not be prepared (%s); %s and %s stay: remove them before a retry'
                           % (why(e), release, STATE)) from e
    unit = unit_text(release, service_env(release, a.account_db, a.commit))
    wanted = before.replace(anchor, anchor + b'\n    include snippets/ftesurf-mapupd.conf;')
    backup.write_bytes(before); backup.chmod(0o600)
    written = unit_written = zones_written = False
    # As in upgrade: Ctrl-C or a dropped session must not leave the include on disk for the next reload.
    held = {n: signal.signal(n, signal.SIG_IGN) for n in (signal.SIGINT, signal.SIGHUP)}
    try:
        with UNIT.open('x') as f: f.write(unit)
        unit_written = True
        zones_written = True   # before the write: a half-written file is taken back too (review 9)
        with ZONES.open('xb') as f: f.write(NGINX_ZONES.encode())
        # conf.d is always loaded: test the zones before anything else can reload them (review 5)
        try: run('/usr/sbin/nginx', '-t')
        except Exception as e:
            ZONES.unlink(); zones_written = False
            raise RuntimeError('nginx refuses the zones file (removed again): %s' % why(e)) from e
        with SNIPPET.open('xb') as f: f.write(NGINX.encode())
        run('/usr/bin/systemctl', 'daemon-reload')
        run('/usr/bin/systemctl', 'enable', '--now', 'ftesurf-mapupd.service')
        for attempt in range(20):
            try: probe_app(a.commit); break
            except (OSError, ValueError, RuntimeError):
                if attempt == 19: raise
                time.sleep(.25)
        if SITE.read_bytes() != before: raise RuntimeError('nginx changed during service setup')
        written = True   # before the write: whatever it leaves is put back
        write_site(wanted)
        run('/usr/sbin/nginx', '-t')
        if b'location = /mapup/api/part' not in run('/usr/sbin/nginx', '-T').stdout:
            raise RuntimeError('nginx -T does not show the mapup route; nothing is public')
        run('/usr/bin/systemctl', 'reload', 'nginx')
        for attempt in range(20):
            try: probe_app(a.commit, PUBLIC_URL + '/api/health'); break
            except (OSError, ValueError, RuntimeError):
                if attempt == 19: raise
                time.sleep(.5)
    except BaseException as first:
        # Each step on its own: a failing nginx test must not leave the unit enabled, nor hide the cause.
        failed = []
        site_back = not written
        if written:
            try:
                if wanted.startswith(SITE.read_bytes()):
                    write_site(before); site_back = True
                elif SITE.read_bytes() != before:
                    failed.append('the site changed meanwhile: not put back')
                else: site_back = True
            except BaseException as e: failed.append('site not put back (%s)' % why(e))
        # conf.d loads the zones whatever the site says: with the include gone they go too, if still ours
        # (review 5: a zones file nginx refused stayed, and the next restart would have failed).
        if zones_written and site_back:
            for f, body in ((SNIPPET, NGINX), (ZONES, NGINX_ZONES)):
                try:
                    if body.encode().startswith(f.read_bytes()): f.unlink()   # ours, whole or cut short
                except FileNotFoundError: pass
                except BaseException as e: failed.append('%s not removed (%s)' % (f, why(e)))
        if written and site_back:
            try: run('/usr/sbin/nginx', '-t'); run('/usr/bin/systemctl', 'reload', 'nginx')
            except BaseException as e: failed.append('nginx put back but not reloaded (%s)' % why(e))
        if unit_written:
            try:
                if UNIT.read_text() != unit: failed.append('the unit changed meanwhile: not stopped')
                else: run('/usr/bin/systemctl', 'disable', '--now', '--no-reload', 'ftesurf-mapupd.service', timeout=120)   # gunicorn: up to 30 s
            except BaseException as e: failed.append('unit not disabled (%s)' % why(e))
        hint = (' -- before a retry remove %s and the release/state left, then run systemctl daemon-reload' % UNIT) if unit_written else ''
        if failed: raise RuntimeError('install failed (%s); rollback: %s%s' % (why(first), '; '.join(failed), hint)) from first
        if hint: say('rolled back' + hint)
        if isinstance(first, subprocess.CalledProcessError): raise RuntimeError('install failed: %s' % why(first)) from first
        raise   # source, state, unit and backup stay for inspection (the snippet and zones go once the site is back)
    finally:
        for n, h in held.items(): signal.signal(n, h)
    outcome = 'Installed the map upload service at %s/ (release %s)' % (PUBLIC_URL, release)
    record_install(release, outcome); say(outcome)   # a dropped session's terminal must not turn success into exit 1


if __name__ == '__main__': main()
