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

By default only `surf_*.json` and `bhop_*.json` names are selected. Names are lowercased for the
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

## Public catalogue selection

Pass `--catalogue /path/to/retained-public-catalogue.txt` to select by public
catalogue membership and its `surf`/`bhop` mode, not filename prefixes. Native
bhop stems such as `ab_baume` and `agtricks` are otherwise excluded by the legacy
prefix filter. This option is independent of the geometry mode. The converter
never fetches a URL: the caller must retain the public response from
`https://play.proto.bar/api/board?maps=1` and pass the local file explicitly.

The bounded (1 MB) ASCII text must have header `FTESURF-MAPDL 1`, followed by
13-column `dl` rows (blank/comment lines allowed): exact map stem at column index1,
mode at index2, `of` at index10, zoned/enabled flags at indices11/12. Malformed
rows, unsupported modes, invalid flags and duplicate/case-colliding names refuse
before creating output. Map and `of` stems must use only ASCII letters/digits,
underscore, plus or minus, with length1..100; no path separators/dots/traversal.
Disabled pool rows remain eligible. Neither `zoned` nor `enabled` proves a JSON
file exists; an embedded BSP timer can set `zoned` too. The `of` field is recorded,
**never** followed as an alias or a claim of compatible zone geometry.

Catalogue mode selects only safely named listed source files. Unlisted/unsafe
input stems are not read, copied, hashed or named in the public report:
`ignored_inputs` contains counts only. This avoids leaking private unknown names;
it does not make an arbitrary source directory an approved public source.
`input_selection` records `catalogue` versus `surf_/bhop_-prefix`, and
`catalogue_sha256` binds the supplied catalogue bytes. Public catalogue entries
without a selected input appear in `catalogue_entries_without_input`; that is
not a claim of HTTP404 or unavailable zone data. An all-ignored catalogue pass
still emits an empty candidate set and these counts/status fields.

Each selected row records `mode`, original `catalogue_map` and `catalogue_of`,
plus exact-case `source_filename`, `source_index`, `native_copy_filename` and
native SHA256. In catalogue mode the native copy preserves source filename case;
target JSON uses the lowercase stem matching the target's `GetLowercaseMapName`.
The existing case-folded upstream skip and source-collision gates still apply.
Without the flag, prefix selection and lowercase native-copy paths stay as before.

## Explicit geometry proposals (P1831)

Add `--geometry-candidates` instead of `--approximate-bounds` for broader,
**review-only** output. Neither default strict validation nor the old convex-only
approximation policy is relaxed. This new mode encloses any finite bounded
3..64-point ring with positive X/Y ranges, including concave, self-crossing,
unordered or nearly collinear rings. Signed area and ring validity are not
certified. Coordinates remain within +/-1,000,000; nonfinite coordinates, invalid
point counts, zero X/Y ranges, nonpositive heights and collapsed/out-of-range Z
remain whole-map blockers. A candidate is not evidence that the input is a valid
polygon or that the enclosing area matches its native interior.

Positive native heights at most 72 are padded to 73 units: normally the bottom is
kept and the top raised; if that would exceed the coordinate limit, the top is
kept and the bottom lowered. At pinned target `SetZoneMinsMaxs`
(`shavit-zones.sp:6724-6740`), each Z side shrinks by 31 units for Source2013 or 36
otherwise. A 73-unit candidate leaves 11 or 1 units respectively before hull touch
behavior. This avoids inverted/degenerate extents in those branches, **not** a
calibration of the native volume. XY box offsets, floating-point precision and
hull/crouch behavior still need actual target testing.

Each changed region has an exact `transformations` entry: native region path,
original bottom/height/top, emitted corners and actual `added_z_below` /
`added_z_above`. The native point list remains in the byte-preserved source copy.
Per-region warnings call out **MATERIAL TIMING DIFFERENCE** and unvalidated ring
semantics. `candidate_counts` separates `strict`, `geometry-proposal` and legacy
`approximate-proposal` maps; these are geometry classifications, not acceptance
levels. A map with any transformed region is a proposal, even if other regions
are strict-compatible. Existing status counts retain whole-map skipped/blocked
results. All route/cap/missing-track guards still apply; no fallback drops a
bonus, checkpoint or stage merely to emit something. Bounded blocked maps still
get complete native backups/status, not partial target JSON.

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
  the target's Z shrink in either inspected engine-height branch. Thin zones are
  refused unless explicit geometry proposals pad them as described above.
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

## Public review downloads versus ranked installation

The owner authorized redistribution of this task's source zone collection on
25 Nov 2026. This is not a public-domain dedication or a new data license: retain
original provenance, attribution and applicable third-party terms. The tool's
notice remains generic because it cannot establish rights for arbitrary inputs.
Public archives or a missing-only **draft** contribution may contain explicitly
unverified review candidates, provided they include native backups, report,
source index/hashes, original license/status commentary and the prominent timing
warnings. Do not describe them as timing-equivalent, calibrated, ranked-ready or
endorsed upstream. The target zone repository's Unlicense does not relicense
unrelated input data; do not invent an Unlicense/public-domain grant for it.

Before installing a particular candidate into a timer, validate it on an isolated
CS:S server with the inspected fork:

1. Disable SQL zone selection (`shavit_zones_usesql 0`) and choose local JSON
   (`shavit_zones_json_folder 1`).
2. Put the **reviewed** candidate at
   `addons/sourcemod/data/zones-cstrike/z/<map>.json`.
3. Verify all main stages/checkpoints, bonuses, start/end boundary timing,
   crouching, restart positions/angles, speed limits, trigger filters and map I/O.
   Resolve every warning; do not silently reuse old ranked records with altered
   boundaries. Test bhop physics/styles separately.
4. Only after those checks promote that map from review-only to validated use.
   Keep unresolved/unsupported maps in the report rather than silently dropping
   their routes. The fork also accepts an HTTP URL ending in `z/{map}.json`; this
   exporter does not deploy a web route or change anybody's server configuration.

The inspected [`wrldspawn/surf-zones` at `5102563`](https://github.com/wrldspawn/surf-zones/tree/51025635e19b833c00bb69c88559cea087434e0d)
contains 81 surf JSON files and no bhop files. Its Unlicense covers its own
contribution, not unrelated source zones. Public accessibility and our repository's
code license do not settle Momentum/community/map-author zone-data permissions.
Keep source provenance and required credits; do not upload BSPs, Valve content,
private maps, user editor drafts or account data. No bulk corpus is committed or
published by the converter code itself; packaging/publication is a separate step.

## Bounded regression tests

Use a new owned test root (not a default system temporary folder):

```sh
python3 -B tools/test_shavit_zones.py --test-root /path/to/new-owned-test-root
```

Tests cover candidate numbering, native byte preservation, deterministic output,
strict/explicit-approximate/geometry-proposal preservation, concave/crossed rings,
short-height transformations, target caps, whole-map refusal, malformed
JSON/numbers, unresolved restart names, missing-only behavior, case collisions,
source precedence, symlink/overwrite refusal and bounded oversized inputs. They
are not an in-engine CS:S timing or redistribution-clearance test.
