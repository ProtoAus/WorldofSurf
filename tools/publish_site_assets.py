#!/usr/bin/env python3
"""Publish only site.js/dl.js/zoning.js/site.css without a client release.

python3 -B tools/publish_site_assets.py --host nanopi --ref COMMIT --file zoning.js [--dry-run]

Reads committed src/release/site/ blobs, never working-tree bytes. The receiver
clones the whole live site, preserves signed metadata verbatim and swaps static
under publish.sh's lock after a baseline CAS. No HTML/feed/version edits or GC.
Failed candidates and old asset releases are retained for owner inspection.
Dry-run and info create nothing remotely. No signing key or root required.
A later normal client release can supersede these assets; include them in its
source. This does not validate JS/API compatibility or perform HTTP acceptance.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PI_PROGRAM = Path(__file__).with_name('site_assets_pi.py')
FILES = ('site.js', 'dl.js', 'zoning.js', 'site.css')
MAX_ASSET = 2 * 1024 * 1024


def git(*args, root=ROOT):
    return subprocess.run(['git', '--no-replace-objects', '-C', str(root), *args], check=True, capture_output=True).stdout


def source(ref, names, root=ROOT):
    commit = git('rev-parse', '--verify', '--end-of-options', ref + '^{commit}', root=root).decode().strip()
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('full SHA1 commit required')
    files = {}
    for name in names:
        if name not in FILES or name in files:
            raise ValueError('invalid or duplicate asset')
        path = 'src/release/site/' + name
        entry = git('ls-tree', commit, '--', path, root=root).decode().split()
        if len(entry) != 4 or entry[0] not in ('100644', '100755') or entry[1] != 'blob':
            raise ValueError('asset must be an ordinary committed blob')
        size = int(git('cat-file', '-s', entry[2], root=root))
        if size > MAX_ASSET:
            raise ValueError('asset size limit exceeded')
        raw = git('cat-file', 'blob', entry[2], root=root)
        files[name] = raw
    return dict(ref=commit, files={n: base64.b64encode(b).decode() for n, b in files.items()},
                hashes={n: hashlib.sha256(b).hexdigest() for n, b in files.items()})


def remote(payload, host):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*', host):
        raise ValueError('invalid SSH host')
    program = PI_PROGRAM.read_text()
    done = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-T', host,
                           '/usr/bin/python3.11 -I -B -c ' + shlex.quote(program)],
                          input=(json.dumps(payload) + '\n').encode(), capture_output=True, timeout=300)
    try:
        out = json.loads(done.stdout)
    except ValueError:
        raise ValueError('receiver returned no JSON (rc %d)' % done.returncode) from None
    if done.returncode or not out.get('ok'):
        raise ValueError('receiver refused: ' + out.get('error', 'transport failed'))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--host', default='nanopi')
    ap.add_argument('--ref', required=True)
    ap.add_argument('--file', action='append', choices=FILES, required=True)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    try:
        request = source(a.ref, a.file)
        baseline = remote(dict(mode='info'), a.host)['baseline']
        result = remote(dict(request, mode='publish', baseline=baseline, dry_run=a.dry_run), a.host)
    except (ValueError, subprocess.SubprocessError) as exc:
        ap.exit(1, 'REFUSED: %s\n' % exc)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
