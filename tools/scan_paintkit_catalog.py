#!/usr/bin/env python3
"""Build a normalized workshop catalog from a local CS:GO Legacy install.

Only labels, kit IDs, parameters, compatibility and VPK paths are emitted.
No assets, inventory, Steam account data, or original schema/VMTs are copied.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import re
import unicodedata

from scan_knife_catalog import generate
from sourceassets import ResourceError, VpkSource, keyvalues, material_path, resolve_vmt

WEAPONS = {
    'v_knife_butterfly': 'knife_butterfly', 'v_knife_m9_bay': 'knife_m9_bayonet',
    'v_knife_bayonet': 'bayonet', 'v_knife_canis': 'knife_canis',
    'v_knife_cord': 'knife_cord', 'v_knife_css': 'knife_css',
    'v_knife_falchion_advanced': 'knife_falchion', 'v_knife_flip': 'knife_flip',
    'v_knife_gut': 'knife_gut', 'v_knife_gypsy_jackknife': 'knife_gypsy_jackknife',
    'v_knife_karam': 'knife_karambit', 'v_knife_outdoor': 'knife_outdoor',
    'v_knife_push': 'knife_push', 'v_knife_skeleton': 'knife_skeleton',
    'v_knife_stiletto': 'knife_stiletto', 'v_knife_survival_bowie': 'knife_survival_bowie',
    'v_knife_tactical': 'knife_tactical', 'v_knife_ursus': 'knife_ursus',
    'v_knife_widowmaker': 'knife_widowmaker',
}
GLOVES = {
    'studded_bloodhound_gloves': 37, 'studded_brokenfang_gloves': 38,
    'studded_hydra_gloves': 39, 'leather_handwraps': 42,
    'motorcycle_gloves': 46, 'slick_gloves': 47,
    'specialist_gloves': 48, 'sporty_gloves': 49,
}
STYLE_DIR = {2: 'hydrographic', 3: 'spray', 5: 'anodized_multi', 6: 'anodized_air',
             7: 'custom', 8: 'antiqued', 9: 'gunsmith'}
ROOT = 'materials/models/weapons/'
NULL = '$whiteimage'
TOKENS = re.compile(r'\s+|//[^\r\n]*|"((?:[^"\\]|\\[\s\S])*)"|([{}])|([^"{}\s]+)')


def kv(text):
    """Read ordered pairs, including repeated top-level paint_kits blocks."""
    stack, root, pos = [], [], 0
    node, key = root, None
    for m in TOKENS.finditer(text):
        if m.start() != pos:
            raise ResourceError(f'invalid schema token at {pos}')
        pos = m.end()
        if m[2] == '{':
            if key is None or len(stack) >= 32:
                raise ResourceError('invalid schema block')
            child = []
            node.append((key, child))
            stack.append(node)
            node, key = child, None
        elif m[2] == '}':
            if key is not None or not stack:
                raise ResourceError('invalid schema close')
            node = stack.pop()
        elif (value := m[1] if m[1] is not None else m[3]) is not None:
            if key is None:
                key = value
            else:
                node.append((key, value))
                key = None
    if pos != len(text) or stack or key is not None:
        raise ResourceError('incomplete schema')
    return root


def numbers(value, default, limits):
    words = value.strip('[]{} ').split() if isinstance(value, str) else []
    if len(words) != len(default):
        return default
    try:
        values = tuple(float(x) for x in words)
    except ValueError:
        return default
    if not all(math.isfinite(x) and limits[0] <= x <= limits[1] for x in values):
        return default
    return values


def number(params, key, default=0, limits=(-360, 360)):
    return numbers(params.get(key), (default,), limits)[0]


def vector(values):
    return ' '.join(f'{x:.6g}' for x in values)


def vtf(pack, name):
    if not isinstance(name, str) or not name:
        return None
    try:
        key = material_path(name.replace('\\', '/').lstrip('/'), '.vtf')
    except ResourceError:
        return None
    if key.startswith(ROOT) and key in pack.entries and re.fullmatch(r'[a-z0-9_./-]+', key):
        return key[len(ROOT):]
    return None


def pattern_path(pack, p, style):
    if style in (1, 4):
        return NULL
    if style not in STYLE_DIR or not p:
        return None
    return vtf(pack, f'{ROOT}customization/paints/{STYLE_DIR[style]}/{p}')


def wear(kit, default):
    low = number(kit, 'wear_remap_min', default[0], (0, 1))
    high = number(kit, 'wear_remap_max', default[1], (0, 1))
    if low >= high:
        raise ResourceError('invalid wear bounds: ' + kit['name'])
    return (low, high, max(low, min(high, number(kit, 'wear_default', .15, (0, 1)))))


def span(params, stem, default, lim):
    return tuple(number(params, stem + '_' + key, d, lim) for key, d in zip(('start', 'end'), default))


def pattern_params(params, glove=False):
    prefix = '$pattern' if glove else 'pattern'
    return (vector(span(params, prefix + '_offset_x', (0, 0), (-4, 4)) + (0,)),
            vector(span(params, prefix + '_offset_y', (0, 0), (-4, 4)) + (0,)),
            vector(span(params, prefix + '_rotate', (0, 0), (-360, 360)) +
                   (number(params, prefix + 'scale' if glove else prefix + '_scale', 1, (.01, 128)),)))


def rgb(value):
    if isinstance(value, str):
        value = ' '.join(value.strip('[]{} ').split()[:3])
    return vector(numbers(value, (128, 128, 128), (0, 255)))


def label_for(tokens, kit):
    raw = tokens.get(kit.get('description_tag', '').lstrip('#').lower(), kit['name'].replace('_', ' ').title())
    # QC's checked-in source/screens use the English table. Strip markup/control
    # codes and avoid separators that would end up in a HUD or shader parser.
    raw = unicodedata.normalize('NFKD', raw).encode('ascii', 'ignore').decode('ascii')
    raw = re.sub(r'[^A-Za-z0-9 .,+!?/()\x27&:-]', '', raw).strip() or kit['name']
    name = kit['name']
    suffix = re.search(r'_(phase_?[1-4]|emerald|ruby|sapphire|blackpearl)(?=_|$)', name)
    if suffix and 'doppler' in raw.lower():
        desc = re.sub(r'(phase)_?([1-4])', r'\1 \2', suffix[1]).title()
        desc = 'Black Pearl' if desc == 'Blackpearl' else desc
        if desc.lower() not in raw.lower():
            raw += ' (' + desc + ')'
    return raw[:64]


def build(directory):
    pack = VpkSource(directory / 'pak01_dir.vpk')
    _, models, _ = generate(pack.path)
    model_bits = {'weapon_usp_silencer': 25, 'weapon_glock': 26}
    unfit = set()
    for m in models:
        stem = Path(m['path']).stem
        if m['kind'] != 'knife' or stem not in WEAPONS:
            continue
        name = 'weapon_' + WEAPONS[stem]
        mask = m['mask']
        maps = [mask, m['base']]
        maps.extend(mask.removesuffix('_masks.vtf') + suf + '.vtf' for suf in ('_ao', '_pos', '_surface'))
        if not mask.endswith('_masks.vtf') or not all(p in pack.entries for p in maps):
            unfit.add(name)
        if not 0 < m['row'] < 25:  # bits 25/26 are the USP/Glock (cl_paintkit.qc PKC_USP/PKC_GLOCK)
            raise ResourceError(f'knife row {m["row"]} collides with the pistol bits')
        model_bits[name] = m['row']
    schema = dict(kv((directory / 'scripts/items/items_game.txt').read_text(encoding='utf-8-sig')))['items_game']
    loc = (directory / 'resource/csgo_english.txt').read_text(encoding='utf-16')
    # Localization also contains platform conditionals. Only consume localized
    # single-line paint labels; none of the other UI strings belong here.
    tokens = {k.lower(): v for k, v in re.findall(r'^\s*"(PaintKit_[^"\r\n]+)"[^\S\r\n]+"([^"\r\n]+)"', loc, re.M | re.I)}
    blocks = [block for key, block in schema if key == 'paint_kits']
    kits, base = {}, {}
    for block in blocks:
        for kit_id, fields in block:
            if not kit_id.isdecimal() or not isinstance(fields, list):
                continue
            kit_id = int(kit_id)
            target = base if kit_id == 0 else kits.setdefault(kit_id, {})
            target.update(dict(fields))
    iconblocks = dict(dict(schema)['alternate_icons2'])['weapon_icons']
    pairs = defaultdict(set)
    ordered_models = sorted(model_bits | GLOVES, key=len, reverse=True)
    for _, icon in iconblocks:
        path = dict(icon).get('icon_path', '').removeprefix('econ/default_generated/')
        if not path.endswith('_light'):
            continue
        for item in ordered_models:
            if path.startswith(item + '_'):
                pairs[path[len(item)+1:-6]].add(item)
                break
    rows, rejected = [], []
    for kit_id, kit in kits.items():
        name = kit.get('name', '')
        owned = pairs.get(name, set())
        if not owned:
            continue
        label = label_for(tokens, kit)
        what = kit.get('vmt_path', '')
        bitmask = 0
        if what:
            gloves = owned & GLOVES.keys()
            if len(gloves) != 1:
                rejected.append((kit_id, name, 'glove model ambiguous'))
                continue
            slot = GLOVES[next(iter(gloves))]
            try:
                shader, params, _ = resolve_vmt(pack, what)
            except (ResourceError, KeyError) as exc:
                # These three stock Moto VMTs omit closing quotes on two vectors.
                # Repair only those fields in memory; use the strict parser after.
                if kit_id not in (10049, 10051, 10052):
                    rejected.append((kit_id, name, str(exc)))
                    continue
                data = pack.read(material_path(what)).data
                data, fixes = re.subn(rb'(\$(?:grime|damagegrunge) "\[(?: [0-9]+\.[0-9]{6}){4} \])(?=\r?\n)', rb'\1"', data)
                if fixes != 2:
                    rejected.append((kit_id, name, str(exc)))
                    continue
                shader, params = keyvalues(data)
            if shader != 'customcharacter':
                rejected.append((kit_id, name, 'unsupported glove shader class'))
                continue
            params.update(dict(kit.get('vmt_overrides', [])))
            files = [vtf(pack, params.get('$' + key)) for key in ('materialmask', 'ao', 'grunge', 'detail')]
            pattern = vtf(pack, params.get('$pattern')) if params.get('$pattern') else NULL
            if None in files or pattern is None:
                rejected.append((kit_id, name, 'missing glove texture'))
                continue
            files.extend((pattern, vtf(pack, params.get('$detailnormal')) or NULL,
                          vtf(pack, params.get('$bumpmap')) or NULL))
            indices = numbers(params.get('$patterncolorindices'), (1, 2, 3, 4), (0, 8))
            detail = numbers(params.get('$detailscale'), (4, 4, 4, 4), (.01, 128))
            info = [vector(wear(kit, (.06, .8))), *pattern_params(params, glove=True), vector(indices[:3]),
                    vector((number(params, '$patternreplaceindex', 0, (0, 8)),
                            number(params, '$grungescale', 2.5, (.01, 128)), int(pattern != NULL))),
                    vector(detail[:3]), vector((detail[3], indices[3], int(files[-1] != NULL)))]
            info += [rgb(params.get(f'$palettecolor{i}')) for i in range(1, 9)]
            bitmask = -slot
        else:
            for code in (owned & model_bits.keys()) - unfit:
                bitmask |= 1 << model_bits[code]
            if not bitmask:
                rejected.append((kit_id, name, 'model customization maps missing'))
                continue
            style = int(kit.get('style', base.get('style', '0')))
            pattern = pattern_path(pack, kit.get('pattern'), style)
            if not pattern:
                rejected.append((kit_id, name, 'pattern missing for style ' + str(style)))
                continue
            values = base | kit
            files = [pattern]
            info = [vector(wear(kit, (.06, .8))), *pattern_params(values),
                    vector((style, number(values, 'phongexponent', 32, (1, 255)),
                            number(values, 'phongintensity', 40, (0, 255)))),
                    *[rgb(values.get(f'color{i}')) for i in range(4)]]
        rows.append((label, kit_id, bitmask, '|'.join(files), '|'.join(info)))
    if not rows or len(rows) >= 1024 or any(not 0 < kit_id < 11000 for _, kit_id, *_ in rows):
        raise ResourceError('catalog outside checked VM bounds')
    summary = {'weapon_kits': sum(mask > 0 for _, _, mask, *_ in rows),
               'glove_kits': sum(mask < 0 for _, _, mask, *_ in rows),
               'compatible': {name: sum(mask > 0 and bool(mask & (1 << bit)) for _, _, mask, *_ in rows)
                              for name, bit in model_bits.items()},
               'glove_families': {name: sum(mask == -row for _, _, mask, *_ in rows) for name, row in GLOVES.items()},
               'unfit_models': sorted(unfit), 'excluded': sorted(rejected)}
    lines = ['// Generated by tools/scan_paintkit_catalog.py; asset references and normalized metadata only.',
             'void() PKC_Data =', '{']
    for label, kit_id, mask, files, info in sorted(rows, key=lambda r: (r[0].casefold(), r[1])):
        lines.append(f'\tPKC_Add({kit_id}i, {mask}i, {json.dumps(label)}, {json.dumps(files)}, {json.dumps(info)});')
    lines += ['};', '']
    return '\n'.join(lines), summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy', type=Path, required=True, help='Legacy csgo gamedir (containing pak01_dir.vpk)')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    generated, summary = build(args.legacy)
    args.output.write_text(generated, encoding='ascii')
    if args.report:
        args.report.write_text(json.dumps(summary, indent=2) + '\n', encoding='ascii')
    print(f"{summary['weapon_kits']} unique weapon kits, {summary['glove_kits']} glove kits; {len(summary['excluded'])} exclusions")
    print('Compatible model/kit pairs:', sum(summary['compatible'].values()))


if __name__ == '__main__':
    main()
