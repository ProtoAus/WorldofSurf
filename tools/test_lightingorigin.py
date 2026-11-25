#!/usr/bin/env python3
"""P1832 bounded matrix oracle + source wiring + optional local BSP metadata checks.

Eligibility tests execute a Python translation of the production scalar predicate,
not QC bytecode or a render callback. No renderer/VM execution or Source
closed-renderer parity claim. Run with -B;
--bsp is optional and reads the owner's map without changing it.
"""
import argparse
import math
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
BSP = None


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def apply(columns, point):
    return tuple(sum(columns[j][i] * point[j] for j in range(3)) for i in range(3))


def axes(angles):
    # Source QAngle / Quake makevectors: forward, LEFT (-right), up.
    p, y, r = map(math.radians, angles)
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    return ((cp * cy, cp * sy, -sp),
            (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, sr * cp),
            (cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp))


IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def offset(helper, landmark):
    if landmark is None:
        return IDENTITY, (0, 0, 0)
    hp, ha = helper
    lp, la = landmark
    h, l = axes(ha), axes(la)
    # These are exactly LO_Matrix's three explicit columns, not H-L displacement.
    columns = tuple(apply(h, tuple(l[j][i] for j in range(3))) for i in range(3))
    return columns, sub(hp, apply(columns, lp))


def query(matrix, point):
    return add(apply(matrix[0], point), matrix[1])


def vec(value):
    return tuple(map(float, value.split()))


def incoming_io(pairs, consumer):
    """Mirror the loader's conservative exact-name / any-wildcard targeting rule."""
    rows = []
    for entity in pairs:
        for key, value in entity:
            if not key.lower().startswith('on'):
                continue
            separator = ',' if ',' in value else '\x1b'
            if separator not in value:
                continue
            target = value.split(separator, 1)[0]
            if target == consumer.get('targetname', '') or '*' in target:
                rows.append((key, value))
    return rows


def consumer_unsupported(consumer, refunsafe, expression=None):
    # Execute only the loader's side-effect-free scalar eligibility predicate.
    # This does not execute LO_Load, LO_Delta, native submission, or QC semantics.
    if expression is None:
        source = (ROOT / 'src/client/cl_lightingorigin.qc').read_text()
        expression = re.search(r'if \((r->unsafe.*?)\)\s*\{ lo_state->unsupported', source, re.S).group(1)
    values = {
        'LO_Static(&lo_records[h])': True,
        'r->unsafe': bool(float(consumer.get('body', '0')) or float(consumer.get('setbodygroup', '0')) or consumer.get('defaultanim')),
        'r->refunsafe': bool(refunsafe),
        'r->parent': consumer.get('parentname', ''),
        'r->absolute': consumer.get('lightingorigin', ''),
        'r->relative': consumer.get('lightingoriginhack', ''),
    }
    for name, value in values.items():
        expression = expression.replace(name, repr(value))
    expression = expression.replace('||', ' or ').replace('&&', ' and ')
    expression = re.sub(r'!(?!=)', ' not ', expression)
    return eval('(' + expression + ')', {'__builtins__': {}}, {})


class LightingOriginMatrixTests(unittest.TestCase):
    def close(self, a, b):
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=7)

    def test_identity(self):
        frame = ((3, -5, 7), (23, 49, -81))
        self.close(query(offset(frame, frame), (90, -42, 10)), (90, -42, 10))

    def test_missing_landmark_is_identity_not_helper_position(self):
        matrix = offset(((100, -200, 300), (30, 60, 90)), None)
        self.assertEqual(matrix, (IDENTITY, (0, 0, 0)))
        self.close(query(matrix, (4, 5, 6)), (4, 5, 6))

    def test_translation_and_moving_consumer(self):
        matrix = offset(((10, 20, 30), (0, 0, 0)), ((3, 7, 11), (0, 0, 0)))
        self.assertEqual(matrix[1], (7, 13, 19))
        self.close(query(matrix, (0, 0, 24)), (7, 13, 43))
        self.close(query(matrix, (100, -50, 24)), (107, -37, 43))

    def test_rotation_all_rigid_columns_h_times_inverse_l(self):
        helper = ((10, -20, 30), (21, 63, -15))
        landmark = ((-3, 7, 11), (-32, 17, 41))
        matrix = offset(helper, landmark)
        # Every point L*q must map to H*q, including all three basis directions.
        for local in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (17, -8, 4)):
            world = add(apply(axes(landmark[1]), local), landmark[0])
            expected = add(apply(axes(helper[1]), local), helper[0])
            self.close(query(matrix, world), expected)

    def test_wrong_order_negative_control(self):
        helper = ((4, 8, -2), (25, 90, -15))
        landmark = ((7, 3, 12), (-45, -10, 35))
        correct = query(offset(helper, landmark), landmark[0])
        wrong = query(offset(landmark, helper), landmark[0])
        self.close(correct, helper[0])
        self.assertGreater(sum((a - b) ** 2 for a, b in zip(wrong, correct)), 1)

    def test_source_matrix_matches_oracle_columns_and_missing_guard(self):
        source = (ROOT / 'src/client/cl_lightingorigin.qc').read_text()
        for axis, components in zip('XYZ', ('lx_x, ly_x, lz_x', 'lx_y, ly_y, lz_y', 'lx_z, ly_z, lz_z')):
            self.assertIn(f'out->axis{axis} = LO_Transform(hx, hy, hz, [{components}]);', source)
        self.assertIn('out->translation = helper->origin - LO_Transform(out->axisX, out->axisY, out->axisZ, landmark->origin);', source)
        self.assertLess(source.index('if (!landmark) return;'), source.index('makevectors(helper->angles)'))
        self.assertIn('hy = -v_right', source)
        self.assertIn('ly = -v_right', source)

    def test_native_fallback_and_no_per_frame_tokenization(self):
        source = (ROOT / 'src/client/cl_lightingorigin.qc').read_text()
        callback = source.split('float(float isnew) LO_Delta =', 1)[1].split('// Parse to temporary', 1)[0]
        self.assertNotIn('getentitytoken', callback)
        self.assertIn('if (isnew)', callback)
        self.assertIn('lo_records[i].origin == self.origin', callback)
        self.assertIn('return Tint_Delta(isnew)', callback)
        self.assertIn('self.drawmask = 0', callback)
        self.assertIn('if (ok)', callback)
        self.assertIn('if (cl_scene_worldonly) return FALSE;', callback)
        self.assertIn('checkbuiltin(LO_DrawOrigin)', source)
        self.assertIn('checkbuiltin(LO_DrawOffset)', source)
        main = (ROOT / 'src/client/cl_main.qc').read_text()
        self.assertLess(main.index('Tint_Load();'), main.index('LO_Load();'))
        self.assertIn('CSQC_Shutdown = { LO_Reset();', main)

    def test_initial_body_zero_incoming_setbodygroup_is_declined(self):
        consumer = {'classname': 'prop_dynamic', 'targetname': 'pose_consumer',
                    'body': '0', 'setbodygroup': '0', 'lightingoriginhack': 'static_helper'}
        self.assertFalse(consumer_unsupported(consumer, False))
        for separator in (',', '\x1b'):
            pairs = [[('OnTrigger', separator.join(('pose_consumer', 'SetBodygroup', '1', '0', '-1')))]]
            rows = incoming_io(pairs, consumer)
            self.assertEqual(len(rows), 1)
            self.assertTrue(consumer_unsupported(consumer, rows))
        # Negative control: the pre-fix predicate admitted precisely this consumer.
        source = (ROOT / 'src/client/cl_lightingorigin.qc').read_text()
        expression = re.search(r'if \((r->unsafe.*?)\)\s*\{ lo_state->unsupported', source, re.S).group(1)
        self.assertFalse(consumer_unsupported(consumer, True, expression.replace('r->refunsafe', '0')))

    def test_actual_authored_metadata(self):
        if BSP is None:
            self.skipTest('pass --bsp to check unchanged local authored metadata')
        sys.path.insert(0, str(ROOT / 'tools/census'))
        import bsplib
        pairs, _ = bsplib.read_pairs(BSP)
        entities = [dict(e) for e in pairs]
        consumers = [e for e in entities if e.get('lightingorigin') or e.get('lightingoriginhack')]
        self.assertEqual(len(consumers), 5)
        resolved, missing = [], []
        incoming_count = sum(len(incoming_io(pairs, consumer)) for consumer in consumers)
        for consumer in consumers:
            name = consumer.get('lightingoriginhack') or consumer.get('lightingorigin')
            refs = [e for e in entities if e.get('targetname') == name]
            if not refs:
                missing.append(consumer)
                continue
            self.assertEqual(len(refs), 1)
            helper = refs[0]
            self.assertEqual(helper['classname'], 'info_lighting_relative')
            landmarks = [e for e in entities if e.get('targetname') == helper.get('lightinglandmark')]
            self.assertEqual(len(landmarks), 1)
            landmark = landmarks[0]
            for frame in (helper, landmark):
                self.assertFalse(frame.get('parentname'))
                # No authored input can invalidate these cached static reference frames.
                for row in pairs:
                    for key, value in row:
                        if key.startswith('on'):
                            self.assertNotEqual(value.replace('\x1b', ',').split(',')[0], frame['targetname'])
            incoming = incoming_io(pairs, consumer)
            self.assertEqual(len(incoming), 0)
            self.assertFalse(consumer_unsupported(consumer, incoming))
            self.assertFalse(consumer.get('defaultanim'))
            for key in ('body', 'setbodygroup', 'randomanimation'):
                self.assertEqual(float(consumer.get(key, '0')), 0)
            self.assertFalse(consumer.get('parentname'))
            collisions = [e for e in entities if e.get('model') == consumer['model'] and e.get('origin') == consumer['origin']]
            self.assertEqual(len(collisions), 1)
            matrix = offset((vec(helper['origin']), vec(helper.get('angles', '0 0 0'))),
                            (vec(landmark['origin']), vec(landmark.get('angles', '0 0 0'))))
            self.close(query(matrix, vec(landmark['origin'])), vec(helper['origin']))
            sample = add(vec(consumer['origin']), (0, 0, 24))
            print(f'authored relative matrix: columns={matrix[0]} translation={matrix[1]} sample={sample} query={query(matrix, sample)}')
            resolved.append(consumer)
        self.assertEqual(len(resolved), 2)
        self.assertEqual(len(missing), 3)
        print(f'local BSP: entities={len(entities)} authored={len(consumers)} eligible={len(resolved)} missing={len(missing)} consumer_incoming_io={incoming_count} eligible_consumer_incoming_io=0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bsp', type=Path)
    args, rest = parser.parse_known_args()
    BSP = args.bsp
    unittest.main(argv=[sys.argv[0]] + rest)
