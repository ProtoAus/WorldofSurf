#!/usr/bin/env python3
"""Site-only publisher receiver. No GC: all candidates, including failures, are retained.

The SSH entrypoint has a fixed site root; root overrides exist only in the Python
API for synthetic fixtures. Cooperating publishers serialize on publish.sh's lock.
This is not a security boundary against a hostile writer with the same Unix uid.
"""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

SITE = Path('/srv/nvme/ftesurf-site')
FILES = frozenset(('site.js', 'dl.js', 'zoning.js', 'site.css'))
MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_ENTRIES = 20000
MAX_ASSET = 2 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def directory(path, owned=True):
    s = path.lstat()
    require(stat.S_ISDIR(s.st_mode), 'nonordinary directory refused')
    require(not owned or s.st_uid == os.getuid(), 'directory not owned by publisher')


def root_check(root):
    require(root.is_absolute(), 'absolute site root required')
    for p in reversed((root, *root.parents)):
        directory(p, owned=(p == root))


def read_file(path, limit=MAX_FILE):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        s = os.fstat(f.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'linked/special file refused')
        require(s.st_size <= limit, 'file size limit exceeded')
        raw = f.read(limit + 1)
        require(len(raw) <= limit and len(raw) == s.st_size, 'file changed or size limit exceeded')
        return raw


def inventory(tree):
    """Digest includes names, empty directories, sizes and every file byte."""
    directory(tree)
    rows = {}
    total = 0

    def walk(parent, depth):
        nonlocal total
        require(depth <= 32, 'tree depth limit exceeded')
        # Enforce the budget while consuming entries, not after sorting an
        # unbounded directory. digest() canonicalizes the final dictionary.
        with os.scandir(parent) as entries:
            for entry in entries:
                require(len(rows) < MAX_ENTRIES, 'tree entry limit exceeded')
                p = Path(entry.path)
                name = p.relative_to(tree).as_posix()
                require(len(name) <= 1024, 'path length limit exceeded')
                s = p.lstat()
                if stat.S_ISDIR(s.st_mode):
                    directory(p)
                    rows[name] = ['d']
                    walk(p, depth + 1)
                else:
                    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'linked/special tree member refused')
                    require(s.st_size <= MAX_FILE and total + s.st_size <= MAX_TOTAL, 'tree size limit exceeded')
                    raw = read_file(p)
                    total += len(raw)
                    rows[name] = ['f', len(raw), sha(raw)]
    walk(tree, 0)
    return rows


def digest(rows):
    return sha(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode())


def info(root=SITE):
    root_check(root)
    require((root / 'static').is_symlink(), 'static must be a symlink')
    link = os.readlink(root / 'static')
    require(re.fullmatch(r'(releases/[0-9]+\.[0-9]+\.[0-9]+|asset-releases/[A-Za-z0-9][A-Za-z0-9_-]{0,127})', link),
            'static target outside allowed release namespace')
    directory(root / link.split('/')[0])
    tree = root / link
    rows = inventory(tree)
    for name in ('index.html', 'update.json', 'update-verified.json', 'version.json'):
        require(rows.get(name, [None])[0] == 'f', 'required baseline metadata missing')
    require(os.readlink(root / 'static') == link, 'static changed during inspection')
    return dict(link=link, tree_sha256=digest(rows), update_sha256=rows['update.json'][2])


def assets(request):
    encoded = request.get('files', {})
    require(isinstance(encoded, dict) and 0 < len(encoded) <= len(FILES), 'assets required')
    require(set(encoded) <= FILES, 'asset not allowlisted')
    require(set(request.get('hashes', {})) == set(encoded), 'asset hashes required')
    result = {}
    for name, value in encoded.items():
        require(isinstance(value, str) and len(value) <= ((MAX_ASSET + 2) // 3) * 4, 'asset size limit exceeded')
        raw = base64.b64decode(value, validate=True)
        require(len(raw) <= MAX_ASSET and sha(raw) == request['hashes'][name], 'asset hash/size mismatch')
        result[name] = raw
    require(re.fullmatch('[0-9a-f]{40}', request.get('ref', '')), 'full git commit required')
    return result


def desired_tree(rows, replacement):
    desired = dict(rows)
    for name, raw in replacement.items():
        require(name not in rows or rows[name][0] == 'f', 'asset collides with directory')
        desired[name] = ['f', len(raw), sha(raw)]
    require(len(desired) <= MAX_ENTRIES, 'candidate entry limit exceeded')
    require(sum(row[1] for row in desired.values() if row[0] == 'f') <= MAX_TOTAL,
            'candidate size limit exceeded')
    return desired


def publish(request, root=SITE, before_swap=None):
    replacement = assets(request)
    expected = request.get('baseline')
    require(isinstance(expected, dict), 'baseline CAS required')
    root_check(root)
    if request.get('dry_run'):
        current = info(root)
        require(current == expected, 'baseline changed (CAS)')
        desired = desired_tree(inventory(root / current['link']), replacement)
        return dict(ok=True, dry_run=True, baseline=current, target='asset-releases/' + digest(desired),
                    tree_sha256=digest(desired), hashes=request['hashes'], ref=request['ref'])
    fd = os.open(root / '.publish.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o644)
    with os.fdopen(fd, 'wb') as lock:
        s = os.fstat(lock.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_uid == os.getuid(), 'unsafe publication lock')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('publication lock busy') from None
        current = info(root)
        require(current == expected, 'baseline changed (CAS)')
        tree = root / current['link']
        rows = inventory(tree)
        desired = desired_tree(rows, replacement)
        target = 'asset-releases/' + digest(desired)
        if desired == rows:
            return dict(ok=True, unchanged=True, baseline=current, target=current['link'], ref=request['ref'], hashes=request['hashes'])
        parent = root / 'asset-releases'
        if not parent.exists() and not parent.is_symlink():
            parent.mkdir(mode=0o755)
            parent.chmod(0o755)  # independent of the SSH account's umask
        directory(parent)
        require(parent.stat().st_mode & 0o005 == 0o005, 'asset parent not nginx traversable')
        dest = root / target
        if dest.exists() or dest.is_symlink():
            require(inventory(dest) == desired, 'content-bound destination collision')
        else:
            stage = parent / ('.pending-' + uuid.uuid4().hex)
            stage.mkdir(mode=0o755)
            # No hardlinks: old releases and their permissions remain untouched.
            for name, row in sorted(desired.items()):
                p = stage / name
                if row[0] == 'd':
                    p.mkdir(mode=0o755)
                else:
                    raw = replacement[name] if name in replacement else read_file(tree / name)
                    require(['f', len(raw), sha(raw)] == row, 'baseline changed while copying')
                    with p.open('xb') as f:
                        f.write(raw)
                        f.flush()
                        os.fsync(f.fileno())
                    p.chmod(0o444)
            require(inventory(stage) == desired, 'candidate digest mismatch')
            for p in sorted(stage.rglob('*'), reverse=True):
                if p.is_dir():
                    p.chmod(0o555)
            stage.chmod(0o555)
            stage.rename(dest)
        # Reused candidates must be readable and immutable as well.
        for p in (dest, *dest.rglob('*')):
            s = p.lstat()
            require(s.st_mode & 0o222 == 0 and s.st_mode & 0o004 and
                    (not stat.S_ISDIR(s.st_mode) or s.st_mode & 0o001), 'candidate permissions unsafe')
        require(info(root) == expected, 'baseline changed before swap (CAS)')
        if before_swap:
            before_swap()
        link = root / ('.static-assets-' + uuid.uuid4().hex)
        link.symlink_to(target)
        os.replace(link, root / 'static')
        return dict(ok=True, target=target, tree_sha256=digest(desired), baseline=current,
                    ref=request['ref'], hashes=request['hashes'])


def main():
    try:
        require(os.getuid() != 0, 'run as site owner, not root')
        line = sys.stdin.buffer.readline(12 * 1024 * 1024 + 1)
        require(len(line) <= 12 * 1024 * 1024, 'request too large')
        request = json.loads(line)
        if request.get('mode') == 'info':
            result = dict(ok=True, baseline=info())
        else:
            require(request.get('mode') == 'publish', 'unknown mode')
            result = publish(request)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = dict(ok=False, error=str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
