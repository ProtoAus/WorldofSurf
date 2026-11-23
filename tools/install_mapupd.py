#!/usr/bin/env python3
"""P1746: owner/root installation of the isolated map upload service (surfd/mapupd.py); default dry run.

New install: a clean inspected commit, the exact nginx predecessor hash, --apply under sudo. Never touches surfd,
its DB or a lobby; grants no roles (`mapupd.py --store ... grant --identity-file F` as proto does that).
--upgrade moves an installed service onto a new commit and nothing else; a failure puts the old one back.
Modelled on tools/install_zonepub.py.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path('/srv/nvme/ftesurf-ops/mapupd')
STATE = Path('/srv/nvme/ftesurf-ops/mapupd-state')
ENABLED = Path('/etc/nginx/sites-enabled/play.proto.bar.conf')
SITE = ENABLED.resolve() if ENABLED.is_symlink() else ENABLED
BACKUPS = Path('/etc/nginx')        # never sites-enabled: a backup there would be loaded
SNIPPET = Path('/etc/nginx/snippets/ftesurf-mapupd.conf')
UNIT = Path('/etc/systemd/system/ftesurf-mapupd.service')
PORT = 8096
MAPS = Path('/srv/nvme/ftesurf-server/game/momentum/maps')
ZONES = (Path('/srv/nvme/ftesurf-server/game/ftesurf/maps/zones/local'), Path('/srv/nvme/ftesurf-site/zones'))
MEDIA = Path('/srv/nvme/ftesurf-site/media')
LIST = Path('/srv/nvme/surfd/data/mapwatch/mapdl.txt')
ACCOUNTS = Path('/srv/nvme/surfd/data/surfd.db')
# No request buffering: nginx would spool a 1 GB body to the root filesystem (6 GB free). The service reads it
# straight into its own spool on the NVMe, one thread per upload.
NGINX = '''location ^~ /mapup/api/ {
    limit_except POST { deny all; }
    client_max_body_size 1100m;
    proxy_request_buffering off;
    proxy_pass http://127.0.0.1:%d;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_http_version 1.1;
    proxy_connect_timeout 2s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    client_body_timeout 120s;
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
''' % PORT
FILES = {'surfd/mapupd.py': 'mapupd.py', 'surfd/mapupd_wsgi.py': 'mapupd_wsgi.py',
         'surfd/mapmanifest.py': 'mapmanifest.py', 'surfd/zonepub.py': 'zonepub.py',
         'surfd/zonepub_publish.py': 'zonepub_publish.py', 'surfd/tascontent.py': 'tascontent.py',
         'surfd/accounts.py': 'accounts.py', 'surfd/steam.py': 'steam.py', 'surfd/rcon.py': 'rcon.py',
         'surfd/ksfprofile.py': 'ksfprofile.py', 'surfd/momprofile.py': 'momprofile.py',
         'tools/ed25519.py': 'tools/ed25519.py'}
ENV_KEYS = {'MAPUPD_STORE', 'MAPUPD_ACCOUNTS', 'MAPUPD_MAPS', 'MAPUPD_ZONES', 'MAPUPD_MEDIA', 'MAPUPD_LIST',
            'MAPUPD_SOURCE', 'SURFD_TOOLS'}


def sha(body): return hashlib.sha256(body).hexdigest()
def run(*args): return subprocess.run(args, check=True, capture_output=True, timeout=60)


def safe_path(p):
    if not re.fullmatch(r'/[a-zA-Z0-9_./-]+', str(p)) or '..' in Path(p).parts:
        raise ValueError('Unsafe configured path: %s' % p)


def writable():
    return [str(STATE), str(MAPS), *map(str, ZONES), str(MEDIA), str(LIST.parent)]


def unit_text(release, env):
    entries = ''.join('Environment="%s=%s"\n' % (k, v.replace('\\', '\\\\').replace('"', '\\"'))
                      for k, v in sorted(env.items()))
    return """[Unit]
Description=World of Surf admin map uploads (P1746)
After=network.target
[Service]
User=proto
Group=proto
UMask=0022
WorkingDirectory=%s
ExecStart=/usr/bin/python3 -m gunicorn --bind 127.0.0.1:%d --workers 1 --threads 4 --timeout 300 --access-logfile /dev/null mapupd_wsgi:app
%sRestart=on-failure
MemoryMax=512M
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=%s
[Install]
WantedBy=multi-user.target
""" % (release, PORT, entries, ' '.join(writable()))


def env_for(release, commit, accounts):
    return dict(MAPUPD_STORE=str(STATE), MAPUPD_ACCOUNTS=str(accounts), MAPUPD_MAPS=str(MAPS),
                MAPUPD_ZONES=json.dumps([str(p) for p in ZONES], separators=(',', ':')), MAPUPD_MEDIA=str(MEDIA),
                MAPUPD_LIST=str(LIST), MAPUPD_SOURCE=commit, SURFD_TOOLS=str(release / 'tools'))


def check_imports(blobs):
    with tempfile.TemporaryDirectory() as d:
        for dest, body in blobs.items():
            p = Path(d) / dest
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
        r = subprocess.run([sys.executable, '-c', 'import mapupd, PIL.Image'], cwd=d, env=env, capture_output=True,
                           timeout=60)
    if r.returncode:
        raise RuntimeError('Service files do not import on their own: ' + r.stderr.decode(errors='replace')[-400:])


def probe(commit, url='http://127.0.0.1:%d/mapup/api/challenge' % PORT):
    req = urllib.request.Request(url, data=json.dumps(dict(manifest='0' * 64)).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=10) as r:
        if r.headers.get('X-Mapupd-Source') != commit:
            raise RuntimeError('Unexpected serving source')
        body = json.loads(r.read(4096))
    if body.get('ok') != 1 or not re.fullmatch('[0-9a-f]{32}', body.get('nonce', '')):
        raise RuntimeError('The challenge control did not act')


def healthy(commit, url=None):
    for attempt in range(30):       # a restart's or a reload's old workers answer for a moment
        try:
            return probe(commit, url) if url else probe(commit)
        except (OSError, ValueError, RuntimeError):
            if attempt == 29:
                raise
            time.sleep(.5)


def source_blobs(a):
    if run('git', '-C', str(a.source), 'rev-parse', 'HEAD').stdout.decode().strip() != a.commit:
        raise RuntimeError('Source ref differs')
    if run('git', '-C', str(a.source), 'status', '--porcelain', '--', *FILES).stdout:
        raise RuntimeError('Service source is not clean at the inspected commit')
    return {dest: (a.source / src).read_bytes() for src, dest in FILES.items()}


def lay_release(release, blobs, commit):
    release.mkdir(parents=True, mode=0o755)
    for dest, body in blobs.items():
        p = release / dest
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        p.chmod(0o644)
    (release / 'SOURCE.json').write_text(json.dumps(dict(commit=commit, files={k: sha(v) for k, v in blobs.items()}),
                                                    indent=2) + '\n')


def upgrade(a):
    blobs = source_blobs(a)
    if UNIT.is_symlink() or not UNIT.is_file() or not STATE.is_dir() or not SNIPPET.is_file():
        raise RuntimeError('No installed map upload service to upgrade')
    old = UNIT.read_text()
    m = re.search(r'^WorkingDirectory=%s/([0-9a-f]{40})$' % re.escape(str(ROOT)), old, re.M)
    if not m:
        raise RuntimeError('The installed unit names no release under %s' % ROOT)
    cur = m.group(1)
    if unit_text(ROOT / cur, env_for(ROOT / cur, cur, a.account_db)) != old:
        raise RuntimeError('The installed unit is not exactly what this installer writes; inspect it first')
    release = ROOT / a.commit
    if release.exists():
        raise RuntimeError('%s already exists; inspect it, then remove it as root to retry' % release)
    check_imports(blobs)
    healthy(cur)
    print('Preflight: clean source; installed release %s answers; state, roles and nginx are kept' % cur[:12])
    if not a.apply:
        print('DRY RUN: no changes; rerun under sudo with --apply')
        return
    if os.geteuid() != 0:
        raise RuntimeError('Root is required for --apply')
    lay_release(release, blobs, a.commit)
    new = unit_text(release, env_for(release, a.commit, a.account_db))

    def put(text):
        tmp = UNIT.with_name(UNIT.name + '.upgrade-tmp')
        tmp.write_text(text)
        tmp.chmod(0o644)
        os.replace(tmp, UNIT)
        run('/usr/bin/systemctl', 'daemon-reload')
        subprocess.run(['/usr/bin/systemctl', 'reset-failed', 'ftesurf-mapupd.service'], capture_output=True, timeout=30)
        run('/usr/bin/systemctl', 'restart', 'ftesurf-mapupd.service')
    try:
        put(new)
        healthy(a.commit)
        healthy(a.commit, 'https://play.proto.bar/mapup/api/challenge')
    except BaseException:
        print('Upgrade failed; putting release %s back' % cur[:12])
        put(old)
        healthy(cur)
        raise
    print('Upgraded the map upload service to %s; release %s stays as the way back' % (a.commit[:12], cur[:12]))


def install(a):
    blobs = source_blobs(a)
    for p in (a.source, a.account_db, MAPS, MEDIA, LIST, *ZONES):
        safe_path(p)
    proto = pwd.getpwnam('proto')
    for d in (MAPS, MEDIA, LIST.parent, *ZONES):
        if d.is_symlink() or not d.is_dir() or d.stat().st_uid != proto.pw_uid:
            raise RuntimeError('Must be a real directory owned by proto: %s' % d)
    with contextlib.closing(sqlite3.connect('file:%s?mode=ro' % a.account_db, uri=True)) as db:
        db.execute('SELECT steamid, banned_at FROM accounts LIMIT 0')
        db.execute('SELECT pub, steamid FROM keylinks LIMIT 0')
    before = SITE.read_bytes()
    if sha(before) != a.expected_nginx_sha256:
        raise RuntimeError('nginx changed; inspect again')
    anchor = b'include snippets/ftesurf-media.conf;'
    if before.count(anchor) != 1:
        raise RuntimeError('Expected one existing media include to place the snippet beside')
    if any(p.exists() or p.is_symlink() for p in (SNIPPET, UNIT, STATE, ROOT / a.commit)):
        raise RuntimeError('Destination already exists; nothing is overwritten')
    if run('/usr/bin/systemctl', 'show', '--value', '--property=LoadState', 'ftesurf-mapupd.service').stdout.strip() != b'not-found':
        raise RuntimeError('A unit of that name is loaded; inspect it first')
    with socket.socket() as s:
        s.bind(('127.0.0.1', PORT))
    check_imports(blobs)
    run('/usr/bin/python3', '-c', 'import flask, gunicorn')
    backup = BACKUPS / (SITE.name + '.pre-mapupd-' + a.commit[:12])
    if backup.exists():
        raise RuntimeError('nginx backup collision; nothing overwritten')
    print('Preflight: clean source, exact nginx predecessor, new service/state, no roles granted')
    print('Publishes accepted uploads into %s, %s, %s; rows into %s' % (MAPS, ', '.join(map(str, ZONES)), MEDIA, LIST))
    if not a.apply:
        print('DRY RUN: no changes; rerun under sudo with --apply')
        return
    if os.geteuid() != 0:
        raise RuntimeError('Root is required for --apply')
    release = ROOT / a.commit
    lay_release(release, blobs, a.commit)
    STATE.mkdir(mode=0o700)
    os.chown(STATE, proto.pw_uid, proto.pw_gid)
    run('/usr/sbin/runuser', '-u', 'proto', '--', '/usr/bin/python3', str(release / 'mapupd.py'), '--store', str(STATE), 'init')
    unit = unit_text(release, env_for(release, a.commit, a.account_db))
    wanted = before.replace(anchor, anchor + b'\n    include snippets/ftesurf-mapupd.conf;')
    backup.write_bytes(before)
    backup.chmod(0o600)
    written = unit_written = False
    try:
        with UNIT.open('x') as f:
            f.write(unit)
        unit_written = True
        with SNIPPET.open('x') as f:
            f.write(NGINX)
        run('/usr/bin/systemctl', 'daemon-reload')
        run('/usr/bin/systemctl', 'enable', '--now', 'ftesurf-mapupd.service')
        healthy(a.commit)
        if SITE.read_bytes() != before:
            raise RuntimeError('nginx changed during service setup')
        SITE.write_bytes(wanted)
        written = True
        run('/usr/sbin/nginx', '-t')
        if b'location ^~ /mapup/api/' not in run('/usr/sbin/nginx', '-T').stdout:
            raise RuntimeError('nginx -T does not show the route; nothing is public')
        run('/usr/bin/systemctl', 'reload', 'nginx')
        healthy(a.commit, 'https://play.proto.bar/mapup/api/challenge')
    except Exception:
        if written and SITE.read_bytes() == wanted:
            SITE.write_bytes(before)
            run('/usr/sbin/nginx', '-t')
            run('/usr/bin/systemctl', 'reload', 'nginx')
        if unit_written and UNIT.read_text() == unit:
            run('/usr/bin/systemctl', 'disable', '--now', 'ftesurf-mapupd.service')
        raise       # source, state, unit, snippet and backup are kept for inspection
    print('Installed the map upload service; every account is refused until granted the map role')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--expected-nginx-sha256')
    ap.add_argument('--account-db', type=Path, default=ACCOUNTS)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--upgrade', action='store_true')
    a = ap.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', a.commit):
        ap.error('Expected the full inspected source SHA')
    if a.upgrade:
        return upgrade(a)
    if not a.expected_nginx_sha256 or not re.fullmatch('[0-9a-f]{64}', a.expected_nginx_sha256):
        ap.error('A new install needs --expected-nginx-sha256 (sha256sum of %s)' % SITE)
    install(a)


if __name__ == '__main__':
    main()
