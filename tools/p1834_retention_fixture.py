#!/usr/bin/env python3
"""Prepare/verify disposable P1834 native-retention data, never launch a server.

Minimal metadata/state grammar is from SV_MsReadMeta/SV_MsSlotCleanMain, NOT valid
resumable gameplay evidence. run.rec contains a sentinel, not a replay. Use only
an owned empty gamedir with no clients allowed to accept these synthetic saves.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ('', 'ag-100-v1', 'ag-250-v1', 'ag-1000-v1', 'cs16-v1', 'hl2-pre-v1', 'hl2-post-v1')
SCENARIOS = ('prepared', 'owner', 'nonowner', 'owner_nextday')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def date(value):
    return datetime.strptime(value, '%Y%m%d').date()


def owned(path):
    path = path.resolve()
    if ROOT not in path.parents:
        raise ValueError('fixture must remain below this owned QC worktree')
    return path


def meta(day):
    # Expiry uses header/day; sessions/ticks/rec make the synthetic intent explicit.
    # No posts/runid: expiry must delete, not promote a partial to evidence.
    return f'FTESURF-RESUME 1\nday {day:%Y%m%d}\nsessions 0\nticks 0\nrec none\nrecsess 0 0 0 0\n'


def state(track=0, malformed=False):
    return f'flags {"0.0" if malformed else "0"}\ntrack {track}\nstartseg 0\nstagerun 0\n'


def prepare(out, mapname, today, days):
    out = owned(out)
    if out.exists():
        raise ValueError('output must be fresh; never overlay an existing gamedir')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+\-]{0,63}', mapname):
        raise ValueError('invalid map component')
    if days < 2:
        raise ValueError('days must be >=2 for distinct fresh/boundary cases')
    out.mkdir(parents=True)
    game = out / 'gamedir'
    game.mkdir()
    manifest = {'schema': 1, 'map': mapname, 'today': today.strftime('%Y%m%d'), 'days': days,
                'gamedir': 'gamedir', 'profiles': list(PROFILES), 'files': [],
                'limits': ['Synthetic parser-minimal data, not resumable saves/replays.',
                           'Claim/open protection applies to optional roots, as in production.',
                           'Active player fields/native occupancy require a real runtime actor; not proven by these files.',
                           'No native execution performed by this helper.']}

    def add(rel, text, deleted=(), case='', profile=''):
        data = text.encode()
        p = game / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        manifest['files'].append({'path': rel, 'sha256': sha(data), 'case': case, 'profile': profile,
                                  'expected': {s: 'absent' if s in deleted else 'unchanged' for s in SCENARIOS}})

    ages = {'expired': days + 1, 'boundary': days, 'fresh': 1,
            'nonmain': days + 1, 'malformed-state': days + 1, 'paused-refresh': days + 1}
    for profile in PROFILES:
        prefix = f'data/experimental/{profile}/' if profile else 'data/'
        for case, age in ages.items():
            rel = f'{prefix}resume/{mapname}/@p1834-{case}/save000/'
            delete = ()
            if case in ('expired', 'paused-refresh'):
                delete = ('owner', 'nonowner', 'owner_nextday')
            elif case == 'boundary':
                delete = ('owner_nextday',)
            add(rel + 'ms.txt', meta(today - timedelta(days=age)), delete, case, profile)
            add(rel + 'state.txt', state(track=1 if case == 'nonmain' else 0,
                                         malformed=case == 'malformed-state'), delete, case, profile)
            add(rel + 'run.rec', f'P1834 synthetic non-replay sentinel {profile or "ordinary"} {case}\n', delete, case, profile)
        if profile:
            # Real protection predicate sees >1 ms*.txt, representing an open claim.
            rel = f'{prefix}resume/{mapname}/@p1834-claimed-open/save000/'
            for leaf in ('ms.txt', 'ms_fixture_claim.txt'):
                add(rel + leaf, meta(today - timedelta(days=days + 1)), case='claimed-open', profile=profile)
            add(rel + 'state.txt', state(), case='claimed-open', profile=profile)
            add(rel + 'run.rec', 'P1834 protected claim sentinel\n', case='claimed-open', profile=profile)
        # Optional evidence namespaces are deliberately NOT a new sweep scope.
        if profile:
            add(f'{prefix}evidence/{mapname}/{today - timedelta(days=days + 1):%Y%m%d}-sentinel.rec',
                'P1834 untouched optional evidence\n', case='optional-evidence-scope', profile=profile)
    for scope in (mapname, 'p1834_foreign_map'):
        for case, age in (('expired', days + 1), ('boundary', days), ('fresh', 1)):
            for ext in ('rec', 'rct', 'hid'):
                deleted = []
                if case == 'expired':
                    deleted = ['owner', 'owner_nextday'] + (['nonowner'] if scope == mapname else [])
                elif case == 'boundary':
                    deleted = ['owner_nextday']
                add(f'data/evidence/{scope}/{today - timedelta(days=age):%Y%m%d}-{case}.{ext}',
                    f'P1834 evidence sentinel {scope} {case} {ext}\n', deleted, f'evidence-{case}')
        add(f'data/evidence/{scope}/notdated-sentinel.rec', 'P1834 no date\n', case='evidence-undated')
    config = (f'cfg_save_auto 0\nsv_public 0\nset lobby_enable 1\nset lobby_master ""\n'
              f'set lobby_empty_fast 1\nset lobby_idle_maintenance 1\nset run_resume_days {days}\n'
              f'set run_evidence_days {days}\nset run_evidence_sweepall 1\ndeveloper 1\nlog_developer 1\n')
    (game / 'p1834_retention.cfg').write_text(config)
    (out / 'expected-files.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return out / 'expected-files.json'


def load(path):
    path = owned(path)
    manifest = json.loads(path.read_text())
    if manifest.get('schema') != 1 or manifest['gamedir'] != 'gamedir':
        raise ValueError('unsupported manifest')
    game = path.parent / 'gamedir'
    for f in manifest['files']:
        rel = Path(f['path'])
        if rel.is_absolute() or '..' in rel.parts or game not in (game / rel).resolve().parents:
            raise ValueError('unsafe fixture path')
    return path, game, manifest


def refresh_paused(path):
    path, game, manifest = load(path)
    if manifest.get('paused_refreshed'):
        raise ValueError('refresh already applied; retain the previous evidence')
    targets = [f for f in manifest['files'] if f['case'] == 'paused-refresh']
    # Check all before writing any: never overwrite modified/missing files.
    for f in targets:
        if sha((game / f['path']).read_bytes()) != f['sha256']:
            raise ValueError('paused-refresh files changed before planned mutation')
    for f in targets:
        f['original_sha256'] = f['sha256']
        if f['path'].endswith('/ms.txt'):
            data = meta(date(manifest['today'])).encode()
            (game / f['path']).write_bytes(data)
            f['sha256'] = sha(data)
        f['expected'] = dict.fromkeys(SCENARIOS, 'unchanged')
    manifest['paused_refreshed'] = True
    path.write_text(json.dumps(manifest, indent=2) + '\n')


def verify(path, scenario):
    path, game, manifest = load(path)
    problems = []
    for f in manifest['files']:
        p = game / f['path']
        expected = f['expected'][scenario]
        if expected == 'absent':
            if p.exists():
                problems.append('not deleted: ' + f['path'])
        elif not p.is_file() or sha(p.read_bytes()) != f['sha256']:
            problems.append('missing/changed protected file: ' + f['path'])
    expected_paths = {f['path'] for f in manifest['files']}
    actual_paths = {p.relative_to(game).as_posix() for p in (game / 'data').rglob('*') if p.is_file()}
    problems += ['unexpected data file: ' + p for p in sorted(actual_paths - expected_paths)]
    result = {'scenario': scenario, 'files_checked': len(manifest['files']), 'problems': problems,
              'fixture_day': manifest['today'], 'actual_utc_day': datetime.now(timezone.utc).strftime('%Y%m%d'),
              'native_run_attested': False,
              'note': 'File expectations only; retain engine logs/actor evidence separately. Helper never runs native code.'}
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--map', required=True)
    p.add_argument('--today', default=datetime.now(timezone.utc).strftime('%Y%m%d'))
    p.add_argument('--days', type=int, default=14)
    p = sub.add_parser('refresh-paused')
    p.add_argument('--manifest', type=Path, required=True)
    p = sub.add_parser('verify')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--scenario', choices=SCENARIOS, required=True)
    args = ap.parse_args()
    if args.command == 'prepare':
        print(prepare(args.out, args.map, date(args.today), args.days))
    elif args.command == 'refresh-paused':
        refresh_paused(args.manifest)
        print('Updated only planned paused-refresh slots; expected hashes recorded.')
    else:
        result = verify(args.manifest, args.scenario)
        print(json.dumps(result, indent=2))
        raise SystemExit(bool(result['problems']))


if __name__ == '__main__':
    main()
