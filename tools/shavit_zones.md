# Native zones → Shavit Surf review copies (P1829)

`shavit_zones.py` is an offline, Python-standard-library exporter for native
Momentum-format-v1 surf/bhop timer files. It **does not edit native zones, live
servers, maps, account data, or an upstream repository**. Its outputs are review
candidates, never a claim of identical ranked timing or a redistribution license.

## Use

Pick explicit input directories, highest priority first. Prefer an inspected
published zone snapshot; a download cache or personal editor save is not
necessarily the live authoritative table. The tool does not discover private
folders or fetch somebody else's zone collection automatically.

```sh
python3 tools/shavit_zones.py \
  --source /path/to/published/native-zones \
  --source /path/to/older-native-library \
  --existing /path/to/surf-zones/z \
  --output /path/to/new-local-review-directory
```

- Output must be a **fresh absent directory**, never an existing tree.
- `z/<map>.json`: Shavit Surf JSON arrays for representable candidate maps.
- `native/<map>.json`: byte-identical selected native inputs, including blocked
  maps, up to the 2 MiB per-file limit. Oversized files are neither read nor copied
  whole; their report row has no purported full-file hash.
- `report.json`: source/candidate SHA256s, source precedence, existing-map skips,
  blocked reasons and per-map semantic warnings. It has no absolute source paths.
- `REVIEW-REQUIRED.txt`: calibration and redistribution warning.

Only `surf_*.json` and `bhop_*.json` names are selected. Names are lowercased for the
target's lowercase map lookup; suffixes such as `_ksf`, `_css`, `_fix` are **never
aliased or removed**. First `--source` wins; shadowed inputs are reported. Source
symlinks and case-colliding names within a directory are refused. When `--existing`
is supplied, existing case-folded map filenames are skipped without modifying
those files. This is a missing-filename comparison, not proof of matching BSP
builds, correct zones, or permission to contribute.

The default refuses non-axis-aligned polygons rather than silently enlarging
them. `--approximate-bounds` explicitly permits their enclosing boxes, marked
**APPROXIMATION — touch timing changes** in every affected report row. Never use
that option to imply an exact conversion. Strict rectangle edges must match the
input's axis-aligned boundaries exactly; even tiny slants need explicit
approximation. All output still needs in-engine review.

## Mapping and limits

Target inspected: [`bhopppp/Shavit-Surf-Timer` at `71e4beb`](https://github.com/bhopppp/Shavit-Surf-Timer/tree/71e4beb680407870239c9fd889ac5d29d527536d),
particularly `shavit-zones-json.sp`, `include/shavit/zones.inc`, and the touch and
restart paths in `shavit-zones.sp`. The timer identifies itself as the CS:S Surf
fork. Its lineage does not certify compatibility with a different version of
vanilla Shavit BhopTimer.

- Main track → 0; bonuses → 1–12.
- First segment's first checkpoint → `start`; later segment starts → `stage`
  with `data` 2 onward. Single-segment main checkpoints → `checkpoint` with `data`
  1 onward. End regions → `end`.
- Multiple regions remain separate zone objects, with the same logical index
  and distinct deterministic IDs. No partial track/map is exported.
- Numeric corners are the region's bounds. These are **not proof of equal touch
  geometry**: native timing uses point/polygon tests, while Shavit creates Source
  triggers and uses player hulls, Z shrinking and its box-offset setting. Test
  standing, crouched, edge crossings and restarts on the exact CS:S map build.
- Maximum 128 physical zones; conservative stage/checkpoint index below 64;
  default box heights must exceed 72 to avoid inverted or degenerate bounds after
  the target's Z shrink in either inspected engine-height branch. Thin zones need manual work.
- Mixed stage/checkpoint routes, staged/checkpoint bonuses, malformed/nonfinite
  geometry, unsupported format versions and cap overflow block the whole map.

`teleDestTargetname` is **not** copied into Shavit `target`: the latter can mean a
trigger selector or player filter/output, not a native restart destination.
Explicit nonzero stage positions can be carried as `dest`; ordinary-start
positions, named destinations and restart yaw remain warnings requiring manual
setup. Do not fabricate spawns from a polygon center.

Global allow-bhop/cancel/overbounce regions, per-segment/track rules, max velocity,
physics, speed-limit flags, restart angles, enabled-state filters and map-specific
I/O are not silently claimed as converted. They are retained in the native copy
and reported for review. The exporter does not emit unsupported customspawn,
area/cluster or BSP-hook forms, install stripper fixes, or resolve BSP entities.
No Source/Valve code or assets are copied by this tool.

## Test and then distribute, not the reverse

After reviewing a particular map and its original author/zone-setter permissions,
validate only that candidate on an isolated CS:S server with the inspected fork:

1. Disable SQL zone selection (`shavit_zones_usesql 0`) and choose local JSON
   (`shavit_zones_json_folder 1`).
2. Put the **reviewed** candidate at
   `addons/sourcemod/data/zones-cstrike/z/<map>.json`.
3. Verify all main stages/checkpoints, bonuses, start/end boundary timing,
   crouching, restart positions/angles, speed limits, trigger filters and map I/O.
   Resolve every warning; do not silently reuse old ranked records with altered
   boundaries. Test bhop physics/styles separately.
4. Only then host reviewed JSON or prepare an upstream missing-only contribution.
   The fork also accepts an HTTP URL ending in `z/{map}.json`; this exporter does
   not deploy a web route or change anybody's server configuration.

The inspected [`wrldspawn/surf-zones` at `5102563`](https://github.com/wrldspawn/surf-zones/tree/51025635e19b833c00bb69c88559cea087434e0d)
contains 81 surf JSON files and no bhop files. Its Unlicense covers its own
contribution, not unrelated source zones. Public accessibility and our repository's
code license do not settle Momentum/community/map-author zone-data permissions.
Keep source provenance and required credits; do not upload BSPs, Valve content,
private maps, user editor drafts or account data. No bulk corpus is committed or
published by this patch.

## Bounded regression tests

Use a new owned test root (not a default system temporary folder):

```sh
python3 -B tools/test_shavit_zones.py --test-root /path/to/new-owned-test-root
```

Tests cover candidate numbering, native byte preservation, deterministic output,
strict/explicit-approximate geometry, target caps, whole-map refusal, malformed
JSON/numbers, unresolved restart names, missing-only behavior, case collisions,
source precedence, symlink/overwrite refusal and bounded oversized inputs. They
are not an in-engine CS:S timing or redistribution-clearance test.
