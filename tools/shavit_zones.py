#!/usr/bin/env python3
"""Copy native surf/bhop zones into Shavit Surf JSON REVIEW CANDIDATES.

This is an offline exporter, not a timing-equivalence certificate or permission
to redistribute somebody else's zones. Native files are never changed. See
shavit_zones.md for the inspected target version and known semantic losses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

MAP = re.compile(r"(?:surf|bhop)_[a-z0-9_+\-]{1,100}\Z", re.ASCII)
MAX_BYTES = 2 * 1024 * 1024
MAX_ZONES = 128
TARGET_REF = "bhopppp/Shavit-Surf-Timer@71e4beb680407870239c9fd889ac5d29d527536d"
NOTICE = """REVIEW CANDIDATES ONLY — NOT DROP-IN VERIFIED ZONES

z/ contains Shavit Surf JSON candidates, native/ contains byte-identical source
copies up to 2 MiB each (oversized inputs are reported, not copied). report.json
lists skipped existing maps, unsupported shapes/routes,
source hashes, approximations and omitted semantics. No upstream files changed.

A box's numeric corners are NOT a proof of equal touch timing: the target uses
Source trigger/player hulls while native zones use point/polygon tests. Calibrate
starts, ends, crouching and stage/bonus restarts on the intended CS:S map build.
Do not substitute these zones into an existing ranked timer without review.

The target JSON cannot carry all native settings, teleport angles, speed flags,
filters, global regions or restart behavior. See each map's warnings and native
copy. This tool does not resolve BSP entities or invent missing spawn positions.

Source-data redistribution rights/credits must be confirmed before publishing
these files. The target repository's Unlicense does not license unrelated input
zones. Do not include BSPs, Valve assets, user-private maps or account data.
"""


class Unsupported(ValueError):
    """A whole map cannot be represented by this candidate profile."""


def number(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Unsupported(f"{where}: expected a finite number")
    # Bound integers before converting to C doubles (math.isfinite/float), so a
    # valid JSON integer with hundreds of digits becomes a blocked map, not a crash.
    if abs(value) > 1_000_000:
        raise Unsupported(f"{where}: coordinate outside supported range")
    if not math.isfinite(value):
        raise Unsupported(f"{where}: expected a finite number")
    return float(value)


def vector(value, size, where):
    if not isinstance(value, list) or len(value) != size:
        raise Unsupported(f"{where}: expected {size} coordinates")
    return [number(v, where) for v in value]


def box(region, where, approximate):
    if not isinstance(region, dict):
        raise Unsupported(f"{where}: expected a region object")
    raw = region.get("points")
    if not isinstance(raw, list) or not 3 <= len(raw) <= 64:
        raise Unsupported(f"{where}: expected 3..64 polygon points")
    points = [vector(p, 2, where) for p in raw]
    bottom = number(region.get("bottom"), where)
    height = number(region.get("height"), where)
    if height <= 72:
        raise Unsupported(f"{where}: height must exceed 72 (target trigger Z shrink needs review)")
    top = bottom + height
    if not math.isfinite(top) or abs(top) > 1_000_000:
        raise Unsupported(f"{where}: invalid top coordinate")
    x0, x1 = min(p[0] for p in points), max(p[0] for p in points)
    y0, y1 = min(p[1] for p in points), max(p[1] for p in points)
    signed_area = sum(a[0]*b[1] - b[0]*a[1] for a, b in zip(points, points[1:]+points[:1])) / 2
    area = abs(signed_area)
    outer = (x1-x0)*(y1-y0)
    if outer <= 0 or area <= 0:
        raise Unsupported(f"{where}: degenerate polygon")
    # Every point must be on the interior side of every oriented edge. Merely
    # checking consecutive turns would incorrectly accept a self-crossing star.
    orientation = 1 if signed_area > 0 else -1
    tolerance = max(1e-8, outer * 1e-8)
    for a, b in zip(points, points[1:]+points[:1]):
        if any(orientation*((b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0])) < -tolerance
               for p in points):
            raise Unsupported(f"{where}: polygon is not a convex ordered ring")
    # Shoelace area equality alone is not sufficient for a malformed ring; every
    # edge must follow one of the rectangle's four boundary lines as well.
    def edge(a, b):
        return any(a[axis] == v and b[axis] == v
                   for axis, values in ((0, (x0, x1)), (1, (y0, y1))) for v in values)
    rectangular = abs(area-outer) <= max(1e-6, outer*1e-6) and all(
        edge(a, b) for a, b in zip(points, points[1:]+points[:1]))
    if not rectangular and not approximate:
        raise Unsupported(f"{where}: non-axis-aligned polygon; not replaced by a bounding box")
    return [x0, y0, bottom], [x1, y1, top], not rectangular


def candidates(obj, *, approximate=False):
    """Return (JSON zone array, warnings). No output is timing-certified."""
    if not isinstance(obj, dict) or type(obj.get("formatVersion")) is not int or obj["formatVersion"] != 1:
        raise Unsupported("expected native formatVersion 1")
    tracks = obj.get("tracks")
    if not isinstance(tracks, dict) or not isinstance(tracks.get("main"), dict):
        raise Unsupported("missing main track")
    unknown_tracks = set(tracks)-{"main", "bonuses"}
    if unknown_tracks:
        raise Unsupported("tracks: additional entries may contain omitted routes: "+", ".join(sorted(unknown_tracks)))
    bonuses = tracks.get("bonuses", [])
    if not isinstance(bonuses, list) or len(bonuses) > 12:
        raise Unsupported("target supports at most 12 bonus tracks")
    result, warnings = [], ["REVIEW REQUIRED: target hull/touch/restart timing is not calibrated"]

    def emit(group, kind, track, ordinal, where):
        if not isinstance(group, dict) or not isinstance(group.get("regions"), list) or not group["regions"]:
            raise Unsupported(f"{where}: missing regions (no partial track exported)")
        extra_group_keys = set(group)-{"regions"}
        if extra_group_keys:
            warnings.append(f"{where}: group fields not carried: {', '.join(sorted(extra_group_keys))}")
        for ri, region in enumerate(group["regions"]):
            path = f"{where}.regions[{ri}]"
            a, b, expanded = box(region, path, approximate)
            zone = {"id": len(result)+1, "type": kind, "track": track,
                    "point_a": a, "point_b": b}
            if ordinal is not None:
                zone["data"] = ordinal
            if expanded:
                warnings.append(f"{path}: APPROXIMATION — polygon replaced by enclosing AABB; touch timing changes")
            if "teleDestPos" in region:
                dest = vector(region["teleDestPos"], 3, path+".teleDestPos")
                if kind == "stage" and any(dest):
                    zone["dest"] = dest
                else:
                    warnings.append(f"{path}: explicit restart position not carried by this target zone type")
            if "teleDestTargetname" in region:
                warnings.append(f"{path}: named restart destination unresolved; NOT copied into target/filter")
            if "teleDestYaw" in region:
                number(region["teleDestYaw"], path+".teleDestYaw")
                warnings.append(f"{path}: restart yaw not representable in target JSON")
            if "safeHeight" in region:
                warnings.append(f"{path}: safeHeight not representable in target JSON")
            unknown = set(region)-{"points", "bottom", "height", "teleDestPos", "teleDestYaw", "teleDestTargetname", "safeHeight"}
            if unknown:
                warnings.append(f"{path}: additional region fields not carried: {', '.join(sorted(unknown))}")
            result.append(zone)
            if len(result) > MAX_ZONES:
                raise Unsupported(f"target zone cap {MAX_ZONES} exceeded; no partial map exported")

    for ti, track in enumerate([tracks["main"]]+bonuses):
        path = "tracks.main" if ti == 0 else f"tracks.bonuses[{ti-1}]"
        if not isinstance(track, dict) or not isinstance(track.get("zones"), dict):
            raise Unsupported(f"{path}: missing zones")
        extra_zone_keys = set(track["zones"])-{"segments", "end"}
        if extra_zone_keys:
            warnings.append(f"{path}.zones: zone fields not carried: {', '.join(sorted(extra_zone_keys))}")
        groups = track["zones"].get("segments")
        if not isinstance(groups, list) or not groups or len(groups) > 63:
            raise Unsupported(f"{path}: expected 1..63 supported segments (target index limit)")
        staged = len(groups) > 1
        if ti and staged:
            raise Unsupported(f"{path}: staged bonuses not supported by inspected target")
        for si, segment in enumerate(groups):
            if not isinstance(segment, dict):
                raise Unsupported(f"{path}: invalid segment")
            cps = segment.get("checkpoints")
            if not isinstance(cps, list) or not cps:
                raise Unsupported(f"{path}: segment without a start checkpoint")
            if (staged or ti) and len(cps) > 1:
                raise Unsupported(f"{path}: mixed staged/checkpoint or bonus-checkpoint route not supported")
            for ci, cp in enumerate(cps):
                kind = ("start" if si == 0 else "stage") if ci == 0 else "checkpoint"
                ordinal = si+1 if kind == "stage" else ci if kind == "checkpoint" else None
                if ordinal is not None and ordinal >= 64:
                    raise Unsupported(f"{path}: target stage/checkpoint index limit")
                emit(cp, kind, ti, ordinal, f"{path}.zones.segments[{si}].checkpoints[{ci}]")
            flags = set(segment)-{"checkpoints"}
            if flags:
                warnings.append(f"{path}.zones.segments[{si}]: segment rules need manual setup: {', '.join(sorted(flags))}")
        emit(track["zones"].get("end"), "end", ti, None, path+".zones.end")
        rules = set(track)-{"zones"}
        if rules:
            warnings.append(f"{path}: track rules need manual setup: {', '.join(sorted(rules))}")
    extras = set(obj)-{"formatVersion", "dataTimestamp", "tracks"}
    if extras:
        warnings.append("map metadata/global regions NOT converted: "+", ".join(sorted(extras)))
    return result, warnings


def load_native(raw):
    if len(raw) > MAX_BYTES:
        raise Unsupported("native JSON exceeds 2 MiB limit")
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise Unsupported(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def finite_float(text):
        value = float(text)
        if not math.isfinite(value):
            raise Unsupported(f"nonfinite JSON number: {text}")
        return value
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_float=finite_float,
                          parse_constant=lambda value: (_ for _ in ()).throw(Unsupported(f"nonfinite JSON value: {value}")))
    except Unsupported:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        raise Unsupported(f"invalid native JSON: {error}") from error


def inventory(directories):
    chosen, shadowed = {}, []
    for source_index, directory in enumerate(directories):
        if not directory.is_dir():
            raise ValueError(f"not a source directory: {directory}")
        local = set()
        for path in sorted(directory.glob("*.json")):
            name = path.stem.lower()
            if not MAP.fullmatch(name):
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"not a regular source JSON file: {path}")
            if name in local:
                raise ValueError(f"case-colliding source filenames: {name}")
            local.add(name)
            if name in chosen:
                shadowed.append({"map": name, "source_index": source_index})
            else:
                chosen[name] = (path, source_index)
    return chosen, shadowed


def export(directories, output, *, existing=None, approximate=False):
    chosen, shadowed = inventory(directories)
    if not chosen:
        raise ValueError("no surf_/bhop_ native JSON files found; nothing exported")
    if existing is not None and not existing.is_dir():
        raise ValueError("--existing must be the actual upstream z/ directory")
    known = {p.stem.lower() for p in existing.glob("*.json")} if existing is not None else set()
    if output.exists() or output.is_symlink():
        raise ValueError("output must be a fresh absent directory; existing output is never overwritten")
    output.mkdir(parents=True)
    (output/"z").mkdir()
    (output/"native").mkdir()
    (output/"REVIEW-REQUIRED.txt").write_text(NOTICE, encoding="utf-8")
    report = {"target": TARGET_REF, "status": "review-candidates-not-timing-certified",
              "redistribution": "source rights and credits require review before upload",
              "input_precedence": "first --source wins; no suffix aliases",
              "approximate_bounds_enabled": approximate, "shadowed_inputs": shadowed, "maps": []}
    for name, (path, source_index) in sorted(chosen.items()):
        with path.open("rb") as source:
            raw = source.read(MAX_BYTES+1)
        row = {"map": name, "source_index": source_index, "source_filename": path.name}
        if len(raw) > MAX_BYTES:
            row.update(status="blocked-no-partial-map", reason="native JSON exceeds 2 MiB; not read or copied whole",
                       native_sha256=None, native_copy_written=False)
            report["maps"].append(row)
            continue
        row.update(native_sha256=hashlib.sha256(raw).hexdigest(), native_copy_written=True)
        # Keep selected bounded inputs byte-for-byte, even unconvertible maps;
        # this is a LOCAL review copy, not a redistribution license.
        (output/"native"/(name+".json")).write_bytes(raw)
        if name in known:
            row["status"] = "existing-upstream-untouched"
        else:
            try:
                zones, warnings = candidates(load_native(raw), approximate=approximate)
                encoded = (json.dumps(zones, ensure_ascii=True, indent=2, allow_nan=False)+"\n").encode("utf-8")
                (output/"z"/(name+".json")).write_bytes(encoded)
                row.update(status="review-candidate", zones=len(zones), warnings=warnings,
                           candidate_sha256=hashlib.sha256(encoded).hexdigest())
            except Unsupported as error:
                row.update(status="blocked-no-partial-map", reason=str(error))
        report["maps"].append(row)
    report["counts"] = {key: sum(row["status"] == key for row in report["maps"])
                        for key in ("review-candidate", "existing-upstream-untouched", "blocked-no-partial-map")}
    (output/"report.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", required=True,
                        help="explicit native directory; repeat in precedence order, highest first")
    parser.add_argument("--existing", type=Path, help="upstream z/ directory; existing case-folded map names are skipped")
    parser.add_argument("--output", type=Path, required=True, help="fresh local review directory")
    parser.add_argument("--approximate-bounds", action="store_true",
                        help="explicitly allow polygon enclosing boxes, flagged as timing-changing approximations")
    args = parser.parse_args(argv)
    try:
        report = export(args.source, args.output, existing=args.existing, approximate=args.approximate_bounds)
    except (OSError, ValueError) as error:
        print(f"shavit_zones: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report["counts"], sort_keys=True))
    print("Local review bundle only. Native inputs/upstream unchanged; permissions and CS:S runtime checks still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
