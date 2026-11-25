#!/usr/bin/env python3
"""Check local `smokevol_info full` output; no map assets or GL context required.

SMOKE_KEYS is the eye/forward used by the retained derived data. PART rows carry
particle id, xyz, half-width, volume id and alpha. PERM/ORDER rows carry rank,
particle id and distance. This checks full tables, not collision-prone checksums.
"""
import copy
import math
from pathlib import Path
import re
import struct
import sys


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def dot(a, b):
    return f32(f32(f32(a[0] * b[0]) + f32(a[1] * b[1])) + f32(a[2] * b[2]))


def ulps(a, b):
    return abs(struct.unpack("<I", struct.pack("<f", a))[0] - struct.unpack("<I", struct.pack("<f", b))[0])


def parse(text):
    blocks, block = [], None
    for line in text.splitlines():
        header = re.search(r"smokevol: particles (\d+) volumes (\d+) culled (\d+) candidates (\d+) pvs (\S+) cache (\S+)", line)
        if header:
            if block and block.get("keys") is not None:
                blocks.append(block)
            block = {"meta": tuple(map(float, header.groups())), "keys": None,
                     "parts": {}, "volumes": {}, "perm": {}, "order": {}, "bad": None}
        if block is None:
            continue
        bounds = re.search(r"smokevol bounds: (\d+) particle boxes outside", line)
        if bounds:
            block["bad"] = int(bounds[1])
        row = re.search(r"\bSMOKE_(KEYS|PART|VOLUME|PERM|ORDER)\s+(.+)$", line)
        if not row:
            continue
        kind, values = row[1], [float(x) for x in row[2].split()]
        assert all(math.isfinite(x) for x in values), row[0]
        if kind == "KEYS":
            assert len(values) == 6
            block["keys"] = values
        else:
            target = {"PART": "parts", "VOLUME": "volumes", "PERM": "perm", "ORDER": "order"}[kind]
            index = int(values[0])
            assert index == values[0] and index not in block[target], (kind, index)
            block[target][index] = values[1:]
    if block and block.get("keys") is not None:
        blocks.append(block)
    assert blocks, "no full smoke-volume tables found"
    return blocks


def validate(b):
    n, volumes, culled, candidates, pvs, cache = b["meta"]
    n, volumes, candidates = int(n), int(volumes), int(candidates)
    assert 0 < volumes <= n <= 1024, "vacuous/invalid positive fixture"
    assert b["bad"] == 0, "particle box escapes linked PVS volume"
    assert set(b["parts"]) == set(range(n))
    assert set(b["volumes"]) == set(range(volumes))
    assert all(v == [0] or v == [1] for v in b["volumes"].values())
    assert culled == sum(v == [0] for v in b["volumes"].values())
    for part in b["parts"].values():
        assert len(part) == 6 and part[3] >= 0 and 0 <= part[5] <= 1
        assert part[4] == int(part[4]) and 0 <= part[4] < volumes
    assert set(b["order"]) == set(range(candidates))
    if not b["perm"]:
        assert culled == volumes and not b["order"], "missing initialized permutation"
        return
    assert set(b["perm"]) == set(range(n))
    permutation = [int(b["perm"][k][0]) for k in range(n)]
    assert sorted(permutation) == list(range(n)), "lost/duplicated particle"
    eye, forward = b["keys"][:3], b["keys"][3:]
    expected, distances, previous = [], {}, float("inf")
    for k, particle in enumerate(permutation):
        actual = b["perm"][k][1]
        xyz, half, volume, alpha = b["parts"][particle][:3], *b["parts"][particle][3:]
        delta = [f32(p - e) for p, e in zip(xyz, eye)]
        distance = f32(math.sqrt(dot(delta, delta)))
        assert actual >= 0 and actual <= previous, "permutation not far-to-near"
        assert ulps(actual, distance) <= 4, ("stale distance", particle, actual, distance)
        previous = distances[particle] = actual
        if b["volumes"][int(volume)] == [1] and dot(delta, forward) >= -half:
            expected.append(particle)
    actual_order = [int(b["order"][k][0]) for k in range(candidates)]
    assert actual_order == expected, "filtered list lost, duplicated or misordered particles"
    for k, particle in enumerate(actual_order):
        assert f32(b["order"][k][1]) == f32(distances[particle]), "filtered distance changed"


def selftest():
    b = {"meta": (3, 1, 0, 2, 1, 1), "keys": [0, 0, 0, 0, 0, 1], "bad": 0,
         "volumes": {0: [1]},
         "parts": {0: [0, 0, 10, 1, 0, .5], 1: [0, 0, 20, 1, 0, .5], 2: [0, 0, -30, 1, 0, .5]},
         "perm": {0: [2, 30], 1: [1, 20], 2: [0, 10]}, "order": {0: [1, 20], 1: [0, 10]}}
    validate(b)
    mutations = [lambda x: x.update(bad=1), lambda x: x["parts"].pop(1),
                 lambda x: x["perm"][0].__setitem__(0, 1),
                 lambda x: x["perm"][1].__setitem__(1, 25),
                 lambda x: x["order"].pop(1),
                 lambda x: x["order"][0].__setitem__(0, 0),
                 lambda x: x["order"][0].__setitem__(1, 19)]
    for mutate in mutations:
        broken = copy.deepcopy(b)
        mutate(broken)
        try:
            validate(broken)
        except (AssertionError, KeyError):
            continue
        raise AssertionError("negative control was accepted")
    print("PASS: positive fixture + 7 missing/duplicate/stale/bounds/order negative controls")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        assert sys.argv[1:], "usage: p1830_smokevol_check.py LOG [LOG ...] or --selftest"
        for filename in sys.argv[1:]:
            blocks = parse(Path(filename).read_text(errors="replace"))
            for block in blocks:
                validate(block)
            print(f"PASS: {filename}: {len(blocks)} complete snapshots; exact membership/filter order + float32 distance checks")
