#!/usr/bin/env python3
"""Test fixture preparation/JSON verification only; NOT native retention proof."""
import argparse
import json
from pathlib import Path
from p1834_retention_fixture import ROOT, PROFILES, date, load, prepare, refresh_paused, verify


def simulate_expected_filesystem(manifest, scenario):
    # Deliberately implements JSON expectations, not a retention algorithm.
    # This tests the verifier and its negative controls, never native behavior.
    _, game, data = load(manifest)
    for item in data['files']:
        if item['expected'][scenario] == 'absent':
            (game / item['path']).unlink()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    out = args.out.resolve()
    if ROOT not in out.parents or out.exists():
        ap.error('--out must be fresh within the QC worktree')
    out.mkdir(parents=True)
    results = []
    for scenario in ('owner', 'nonowner', 'owner_nextday'):
        manifest = prepare(out / scenario, 'p1834_fixture_map', date('20261125'), 14)
        data = json.loads(manifest.read_text())
        assert set(data['profiles']) == set(PROFILES)
        assert len(data['files']) == 176
        cfg = (manifest.parent / 'gamedir' / 'p1834_retention.cfg').read_text().splitlines()
        for name, value in [('lobby_enable', '1'), ('lobby_master', '""'),
                            ('lobby_empty_fast', '1'), ('lobby_idle_maintenance', '1'),
                            ('run_resume_days', '14'), ('run_evidence_days', '14'),
                            ('run_evidence_sweepall', '1')]:
            assert f'set {name} {value}' in cfg, ('fresh-start QC cvar requires set', name)
            assert not any(line.startswith(name + ' ') for line in cfg)
        assert not verify(manifest, 'prepared')['problems']
        assert verify(manifest, scenario)['problems'], 'missing action must fail'
        simulate_expected_filesystem(manifest, scenario)
        result = verify(manifest, scenario)
        assert not result['problems'], result
        results.append(result)
    manifest = prepare(out / 'paused-refresh', 'p1834_fixture_map', date('20261125'), 14)
    refresh_paused(manifest)
    _, game, data = load(manifest)
    targets = [f for f in data['files'] if f['case'] == 'paused-refresh']
    assert len(targets) == 21 and all(f['expected']['owner'] == 'unchanged' for f in targets)
    simulate_expected_filesystem(manifest, 'owner')
    assert not verify(manifest, 'owner')['problems']
    protected = next(f for f in data['files'] if f['case'] == 'claimed-open')
    (game / protected['path']).write_text('corrupted protected claim\n')
    assert any(protected['path'] in p for p in verify(manifest, 'owner')['problems'])
    (game / 'data' / 'unexpected.txt').write_text('unexpected\n')
    assert any('unexpected data file' in p for p in verify(manifest, 'owner')['problems'])
    try:
        prepare(out / 'owner', 'p1834_fixture_map', date('20261125'), 14)
        raise AssertionError('existing gamedir overlay accepted')
    except ValueError:
        pass
    (out / 'results.json').write_text(json.dumps({'fixture_verifier_tests': results,
        'negative_controls': ['no acting deletions rejected', 'protected bytes changed rejected',
                              'unexpected file rejected', 'existing output overlay rejected'],
        'native_executed': False}, indent=2) + '\n')
    print('PASS fixture-only preparation/verifier: 176 files, seven roots, three scenarios, paused refresh and negative controls; NO NATIVE RUN')


if __name__ == '__main__':
    main()
