#!/usr/bin/env python3
"""P1862: surfd's account viewmodel limits must equal the QC codec's VM_Range (src/shared/sh_viewmodel.qc).

The lobby and the client validate a setup with VM_Range; surfd re-validates it before saving. A field whose
ranges differ is accepted in game and refused by the account store (the 13 faction rigs were, at 49 vs 63).
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'surfd'))
import viewmodel  # noqa: E402


def qc_ranges():
    src = (ROOT / 'src/shared/sh_viewmodel.qc').read_text()
    names = {m[1]: int(m[2]) for m in re.finditer(r'#define (VM_\w+) (\d+)\b', src)}
    body = src[src.index('VM_Range ='):]
    body = body[:body.index('};')]
    rules, default = [], None
    for cond, vec in re.findall(r"if \(([^)]*)\) return '([^']*)';", body):
        fields = [0] if cond.strip() == 'field == 0' else [names[n] for n in re.findall(r'field == (VM_\w+)', cond)]
        lo, hi, integer = (float(x) for x in vec.split())
        rules.append((fields, (lo, hi, bool(integer))))
    default = re.search(r"\n\treturn '([^']*)';", body)[1].split()
    return rules, (float(default[0]), float(default[1]), bool(float(default[2])))


class Ranges(unittest.TestCase):
    def test_every_field_matches(self):
        rules, default = qc_ranges()
        for field in range(viewmodel.FIELDS):
            want = next((r for fs, r in rules if field in fs), default)
            lo, hi, integer = viewmodel.limits(field)
            self.assertEqual((float(lo), float(hi), bool(integer)), want, f'field {field}')

    def test_hands_cover_the_faction_rigs(self):
        self.assertEqual(viewmodel.limits(3)[:2], (32, 63))


if __name__ == '__main__':
    unittest.main()
