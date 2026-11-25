#!/usr/bin/env python3
"""Owned, loopback-only P1834 native qualification. Requires parent-held game lock.

No builds. Copies explicit inputs, launches only its own dedicated PID, uses real
QC/builtins/files/HTTP/QW slots. Stops at first failure; receipts never infer a
native pass from fixture generation. See fixtures/p1834_native.md for boundaries.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
import time
import uuid
from urllib.parse import parse_qs

from p1834_retention_fixture import ROOT, prepare, refresh_paused, verify
from test_ui_modern import make_map

CASES = ('owner', 'nonowner', 'date', 'slow', 'pause', 'revoke', 'connecting', 'spectator')
MAP = 'p1834_native.map'
QUEUE = ('ms_maint_root', 'ms_maint_open', 'ms_maint_index', 'ev_maint_phase', 'ev_maint_open', 'ev_maint_index', 'ev_maint_native_done')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(text):
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]|\^[0-9]', '', text).replace('\r', '')


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def until(predicate, timeout=180):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(.005)
    raise TimeoutError('native condition not reached within ' + str(timeout) + 's')


class HTTP(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, delay):
        self.gate = threading.Event()
        self.delay, self.body, self.records = delay, b'ok', []
        super().__init__(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.gate.set()
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=5)
        end = time.monotonic() + 3
        while any('end' not in r and 'error' not in r for r in self.records) and time.monotonic() < end:
            time.sleep(.01)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        fields = parse_qs(self.rfile.read(int(self.headers.get('Content-Length', '0'))).decode())
        if self.path != '/api/heartbeat':
            self.send_error(404)
            return
        if fields.get('key') != ['p1834-test-only']:
            self.send_error(403)
            return
        row = {'start': time.monotonic(), 'peer': self.client_address[0],
               'map': fields.get('map'), 'players': fields.get('players')}
        self.server.records.append(row)
        if not self.server.gate.wait(180):
            row['error'] = 'gate timeout'
            return
        time.sleep(self.server.delay)
        body = self.server.body
        try:
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            row.update(end=time.monotonic(), body=body.decode())
        except OSError as exc:
            row['error'] = str(exc)


class Native:
    def __init__(self, args, out, game, extra, receipt):
        self.out, self.game, self.receipt = out, game, receipt
        self.token = 'P1834_' + uuid.uuid4().hex
        self.log = out / 'stdout.log'
        for src, dst in ((args.engine, out / 'fteqw-sv64'),
                         (args.plugin, out / 'fteplug_hl2_amd64.so')):
            shutil.copyfile(src, dst)
        os.chmod(out / 'fteqw-sv64', 0o555)
        (out / 'fteplug_hl2_amd64.so').chmod(0o444)
        for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
            shutil.copyfile(args.progs / name, game / name)
            (game / name).chmod(0o444)
        (game / 'cfg').mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
        (game / 'maps').mkdir(exist_ok=True)
        for name in (MAP, 'p1834_other.map'):
            (game / 'maps' / name).write_text(make_map())
        (game / 'fs_addons.txt').write_text(str(args.owned_assets) + '\n')
        (out / 'default.fmf').write_text('FTEMANIFEST 1\nGAME P1834OwnedFixture\nBASEGAME gamedir\nDISABLEHOMEDIR 1\nMAINCONFIG fixture-unused\n')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        staging = out / 'native-policy'
        staging.mkdir()
        cfg = ['exec cfg/default.cfg', 'cfg_save_auto 0', 'con_savehistory 0', 'sv_public 0',
               'set sv_port_natpmp ""', 'set net_enable_dtls 0', 'sv_cheats 1',
               f'sv_port {self.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'maxspectators 4',
               'set sv_maxspectators 4', 'set sv_movementprofile ""', 'set lobby_dir ""',
               'set cl_board_url ""', 'set cl_run_upload 0', 'set sv_dlURL ""',
               'set cl_download_mapsrc ""', 'set cl_download_zonesrc ""',
               f'set sv_held_staging "{staging}"', 'developer 1', 'log_developer 1',
               'set lobby_enable 1', 'set lobby_idle_maintenance 0', 'set lobby_master ""',
               'set run_resume_days 0', 'set run_evidence_days 0'] + extra
        (game / 'probe.cfg').write_text('\n'.join(cfg + ['map ' + MAP, 'echo ' + self.token]) + '\n')
        argv = [str(out / 'fteqw-sv64'), '-plugin', '-nohome', '-noreset', '-nobrowse',
                '-ip', '127.0.0.1', '-basedir', str(out), '-manifest', str(out / 'default.fmf'),
                '+set', 'cfg_save_auto', '0', '+exec', 'probe.cfg']
        frozen = [out / 'fteqw-sv64', out / 'fteplug_hl2_amd64.so', game / 'cfg/default.cfg']
        frozen += [game / n for n in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')]
        receipt['copied_inputs'] = {str(p): digest(p) for p in frozen}
        self.output = self.log.open('wb')
        self.p = None
        try:
            self.p = subprocess.Popen(argv, cwd=out, stdin=subprocess.PIPE,
                                      stdout=self.output, stderr=subprocess.STDOUT)
            receipt.update(pid=self.p.pid, argv=argv, port=self.port)
            (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
            boot = self.wait(self.token, 0, 90)
            require('Server spawned.' in boot, 'no native spawn')
            require(self.read('mapname') != '', 'empty actual QC mapname')
            until(lambda: self.number('zone_entsready') == 1 and self.number('zone_loaded') == 1, 30)
        except BaseException:
            self.close()
            raise

    def text(self):
        return clean(self.log.read_text(errors='replace'))

    def wait(self, marker, offset, timeout=30):
        def ready():
            text = self.text()[offset:]
            require(self.p.poll() is None, 'owned native process exited early')
            require(not re.search(r'Host_Error|runaway loop|PR_ExecuteProgram:', text), 'native runtime error')
            return text if re.search(r'(?m)^' + re.escape(marker) + r'\s*$', text) else None
        return until(ready, timeout)

    def query(self, command):
        offset, marker = len(self.text()), self.token + '_' + uuid.uuid4().hex
        self.p.stdin.write((command + '; echo ' + marker + '\n').encode())
        self.p.stdin.flush()
        result = self.wait(marker, offset)
        self.receipt.setdefault('queries', []).append({'command': command, 'output': result})
        return result

    def read(self, expression):
        result = self.query('poke_ssqc ' + expression)
        values = re.findall(r'(?m)^Result: (.*)$', result)
        require(len(values) == 1, 'poke did not return one actual value: ' + expression)
        return values[0].strip().strip('"')

    def number(self, expression):
        return float(self.read(expression))

    def cvar(self, name):
        result = self.query(name)
        effective = re.search(r'Effective value is "([^"]*)"', result)
        value = re.search(r'"' + re.escape(name) + r'" is (?:currently )?"([^"]*)"', result)
        require(value is not None, 'unregistered/unreadable cvar ' + name)
        return (effective or value)[1]

    def checkpoint(self):
        self.query('poke_ssqc sv_maint_next=1000000000')
        require(self.number('sv_maint_next') >= 100000000, 'checkpoint deadline write refused')

    def close(self):
        if self.p is not None and self.p.poll() is None:
            try:
                self.p.stdin.write(b'quit\n'); self.p.stdin.flush(); self.p.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.p.terminate()
                try:
                    self.p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.p.kill(); self.p.wait(timeout=5)
        self.receipt['process_exit'] = self.p.returncode if self.p else None
        self.output.close()
        (self.out / 'receipt.json').write_text(json.dumps(self.receipt, indent=2) + '\n')


def connect(native, spectator):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(('127.0.0.1', 0)); sock.settimeout(3)
        target = ('127.0.0.1', native.port)
        sock.sendto(b'\xff\xff\xff\xffgetchallenge\n', target)
        reply = sock.recv(4096)
        match = re.match(rb'\xff\xff\xff\xffc(-?\d+)', reply)
        require(match is not None, 'no actual QW challenge')
        name = 'p1834_' + uuid.uuid4().hex[:10]
        info = f'\\name\\{name}\\spectator\\{int(spectator)}'
        qport = sock.getsockname()[1]
        sock.sendto(b'\xff\xff\xff\xff' + f'connect 28 {qport} {int(match[1])} "{info}"\n'.encode(), target)
        require(sock.recv(4096).startswith(b'\xff\xff\xff\xffj'), 'native QW connection rejected')
        # Native status distinguishes spectators from players, including unspawned slots.
        sock.sendto(b'\xff\xff\xff\xffstatus ' + (b'4' if spectator else b'2') + b'\n', target)
        status = sock.recv(8192).decode(errors='replace')
        require(name in status, 'accepted slot absent from native status class')
        native.receipt['client'] = {'name': name, 'qport': qport, 'spectator': spectator,
                                    'status': status, 'sent_spawn_commands': False}
        return sock
    except BaseException:
        sock.close()
        raise


def run_case(args, root, name, mapname):
    today = datetime.now(timezone.utc).date()
    fixture = prepare(root, mapname, today - timedelta(days=name == 'date'), 14)
    game, row = root / 'gamedir', {'case': name, 'status': 'RUNNING', 'started_utc': datetime.now(timezone.utc).isoformat()}
    http, native, client = HTTP(1.2 if name == 'slow' else .05), None, None
    def save():
        row['http'] = list(http.records)
        (root / 'receipt.json').write_text(json.dumps(row, indent=2) + '\n')
    try:
        extra = ['exec p1834_retention.cfg', 'set lobby_master_key p1834-test-only',
                 f'set lobby_master "http://127.0.0.1:{http.server_port}"',
                 'set run_evidence_sweepall ' + str(int(name != 'nonowner'))]
        native = Native(args, root, game, extra, row)
        require(native.read('mapname') == mapname, 'bootstrap/target map identity changed')
        for key, value in [('lobby_enable', '1'), ('lobby_empty_fast', '1'), ('lobby_idle_maintenance', '1'),
                           ('run_resume_days', '14'), ('run_evidence_days', '14'),
                           ('run_evidence_sweepall', str(int(name != 'nonowner'))), ('sv_movementprofile', '')]:
            require(native.cvar(key) == value, 'wrong EFFECTIVE startup policy ' + key)
        row['serverinfo'] = native.query('serverinfo')
        require(native.read('tq_id') == '' and native.number('tq_creating') == 0
                and native.cvar('tournament_reserved') == '', 'arm masked by reservation')
        require(native.number('sv_maint_pending') == 1 and native.number('ms_maint_root') == 0,
                'fresh startup did not arm the deferred queue')
        until(lambda: native.number('lobby_hb_pending') == 1)
        require(native.number('lobby_hb_next') - native.number('lobby_hb_last') == 1, 'effective empty send period is not 1s')
        require(not verify(fixture, 'prepared')['problems'], 'data changed before successful ACK')
        before = [native.number(k) for k in QUEUE]
        time.sleep(.3)
        require(before == [native.number(k) for k in QUEUE],
                'queue progressed during pending initial request')
        if name in ('connecting', 'spectator'):
            client = connect(native, name == 'spectator')
            http.body = b'map p1834_other'; http.gate.set()
            until(lambda: any('end' in r for r in http.records))
            until(lambda: native.number('lobby_hb_pending') == 0)
            require(native.read('mapname') == mapname and native.number('lobby_map_pending') == 0,
                    'late directive moved or armed occupied server')
            require('directory wants' in native.text(), 'actual directed occupied refusal not reached')
            require(not verify(fixture, 'prepared')['problems'], 'occupied queue changed files')
            http.body = b'ok'
            native.query('kick # 1'); client.close(); client = None
        else:
            http.gate.set()
        if name == 'slow':
            until(lambda: http.records and 'end' not in http.records[-1]
                  and time.monotonic() - http.records[-1]['start'] < .15
                  and native.number('lobby_hb_ready') == 1 and native.number('lobby_hb_pending') == 1)
            before = [native.number(k) for k in QUEUE]
            time.sleep(.3)
            require(native.number('lobby_hb_pending') == 1 and before == [native.number(k) for k in QUEUE],
                    'acknowledged-ready queue progressed during a later slow pending request')
        if name in ('pause', 'revoke'):

            key = 'ms_maint_open' if name == 'pause' else 'ev_maint_open'
            until(lambda: native.number(key) == 1 and (name != 'revoke' or native.number('ev_maint_phase') == 1))
            native.checkpoint()
            require(native.number('ms_maint_index' if name == 'pause' else 'ev_maint_index') == 0,
                    'missed snapshot-before-first-result checkpoint')
            if name == 'pause':
                client = connect(native, False)
                native.query('poke_ssqc sv_maint_next=0')
                require(native.number('lobby_hb_pending') == 0, 'occupancy arm masked by pending HTTP')
                time.sleep(.4)
                require(native.number('lobby_hb_pending') == 0, 'occupancy observation masked by HTTP')
                require(native.number('ms_maint_index') == 0 and not verify(fixture, 'prepared')['problems'],
                        'native occupancy did not guard the open snapshot')
                refresh_paused(fixture)
                native.query('kick # 1'); client.close(); client = None
            else:
                native.query('set run_evidence_sweepall 0; poke_ssqc sv_maint_next=0')
        until(lambda: native.number('sv_maint_pending') == 0, args.timeout)
        scenario = 'owner_nextday' if name == 'date' else 'nonowner' if name in ('nonowner', 'revoke') else 'owner'
        result = verify(fixture, scenario)
        require(not result['problems'], 'native storage mismatch: ' + repr(result['problems']))
        require(native.number('ms_maint_root') == 7 and native.number('ev_maint_phase') == 2,
                'not every retention phase completed')
        info = native.query('localinfo')
        stamped = bool(re.search(r'fs_evswept[^\n]*' + today.strftime('%Y%m%d'), info))
        require(stamped == (scenario != 'nonowner'), 'completion stamp/ownership mismatch')
        if name == 'slow':
            require(len(http.records) >= 9, 'too few delayed ACKs to act completion interaction')
            for previous, following in zip(http.records, http.records[1:]):
                require('end' in previous and following['start'] >= previous['end'], 'normal HTTP requests overlapped')
                require(previous['end'] - previous['start'] >= 1.2, 'slow ACK delay did not act')
        require(datetime.now(timezone.utc).date() == today, 'UTC day changed during arm; retain as inconclusive')
        require(all(digest(Path(p)) == h for p, h in row['copied_inputs'].items()), 'copied immutable input changed')
        row.update(status='PASS', verification=result, completion_stamp=info)
    except BaseException as exc:
        row.update(status='FAIL', error=repr(exc)); raise
    finally:
        if client is not None:
            client.close()
        http.gate.set()
        if native is not None:
            native.close()
        http.close()
        if row['status'] == 'PASS' and row.get('process_exit') != 0:
            row.update(status='FAIL', error='owned server did not exit cleanly')
        save()
    require(row['status'] == 'PASS', row.get('error', 'native arm failed'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for flag in ('engine', 'plugin', 'progs', 'assets', 'out'):
        ap.add_argument('--' + flag, type=Path, required=True)
    ap.add_argument('--case', choices=('all',) + CASES, default='all')
    ap.add_argument('--timeout', type=float, default=180)
    args = ap.parse_args()
    for key in ('engine', 'plugin', 'progs', 'assets', 'out'):
        setattr(args, key, getattr(args, key).resolve())
    if not args.out.is_relative_to(ROOT / 'rig') or args.out.exists():
        ap.error('--out must be fresh beneath this QC worktree/rig')
    inputs = [args.engine, args.plugin, ROOT / 'ftesurf/cfg/default.cfg'] + [args.progs / n for n in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')]
    inputs += sorted(p for p in args.assets.rglob('*') if p.is_file())
    require(args.assets.is_dir() and all(p.is_file() and not p.is_symlink() for p in inputs), 'inputs must be explicit regular files, no symlinks')
    require(not any(p.is_symlink() for p in args.assets.rglob('*')), 'asset symlinks are not copied')
    args.out.mkdir(parents=True)
    (args.out / 'OWNER.md').write_text('P1834 native fixture, UTC ' + datetime.now(timezone.utc).isoformat() + '\nQC worktree: ' + str(ROOT) + '\nOwned PIDs, input/source hashes and argv in receipts. No shared state. Retain all evidence until explicit owner retirement.\n')
    inputs += [Path(__file__), ROOT / 'tools/p1834_retention_fixture.py', ROOT / 'tools/test_ui_modern.py']
    inputs += [ROOT / 'src/server' / n for n in ('sv_lobby.qc', 'sv_main.qc', 'sv_resume.qc', 'sv_timer.qc')]
    inputs += [ROOT / 'src/shared/sh_defs.qc']
    hashes = {str(p): digest(p) for p in inputs}
    receipt = {'status': 'RUNNING', 'inputs': hashes, 'not_reached': ['fully spawned active-player protection',
        'literal midnight rollover', 'native-policy object expiry (no authored native-policy objects)',
        'failed enqueue/timeout/stale callback native arms', 'reserved/custom/disabled native cadence arms', 'accepted-empty directive transition guard']}
    (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    try:
        args.owned_assets = args.out / 'assets'
        shutil.copytree(args.assets, args.owned_assets)
        for p in args.owned_assets.rglob('*'):
            if p.is_file(): p.chmod(0o444)
        boot = args.out / 'bootstrap'; game = boot / 'gamedir'; game.mkdir(parents=True)
        row = {}; native = Native(args, boot, game, [], row)
        try:
            mapname = native.read('mapname')
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+\-]{0,63}', mapname), 'unsafe actual mapname')
        finally:
            native.close(); (boot / 'receipt.json').write_text(json.dumps(row, indent=2) + '\n')
        for name in CASES if args.case == 'all' else (args.case,):
            run_case(args, args.out / name, name, mapname)
        require(all(digest(Path(p)) == h for p, h in hashes.items()), 'immutable input changed')
        receipt['status'] = 'PASS-selected-native-arms'
    except BaseException as exc:
        receipt.update(status='FAIL', error=repr(exc)); raise
    finally:
        receipt['ended_utc'] = datetime.now(timezone.utc).isoformat()
        (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
