# P1837 — public website cache and rendering performance

Owner: QuickPhoenix, 25 Nov 2026. User: "Please continue and apply all the fixes, I want to ensure maximum speed."

Base: f8d04f241d0e70c49bcb33faae6eb709766844af. Owned root: FTESurf-worktrees/webperf-20261125-phoenix; backend/ and frontend/ independent implementation/review lanes, integrate/ parent delivery. Canonical dirty checkout preserved.

Scope: public web_maps persisted last-good single-flight background refresh; cheap availability-only API; explicit cache warm callable; bounded player-directory search; initial map-list DOM cap retaining full-catalogue search; route-safe lazy run renderer; independent/coalesced zoning live updates. Tests use synthetic data. No engine/QC/mover/ruleset or database schema change. No weakening of public redaction, cache freshness or join admission.

Coordinated with RedHawk P1833–P1836: RedHawk alone owns map_index/_scan_maps and zone_file_index/_scan_zone_files with join freshness; this patch leaves those functions unchanged. Parent handles guarded backend generation separately; no lobby/fleet restart.

Status: source implementation and independent reviews complete. Prior P1 findings (synchronous availability scans, disposal hash rewrite, incomplete-map canonical names) closed. Optional people-stamp overflow note fixed with an 18th regression control. Local web/cache/profile/backend/frontend/site suites pass; NanoPi real-nginx routes 9/9 and cache/startup 18/18 pass. Full Pi web suite paused after two incomplete source exports (missing tools/momfetch dependency, then src/viewer/src), not product assertion failures; original logs retained, owner approval requested for one complete-public-source export before further qualification. Canonical test_surfd FakeClock baseline failure reproduced and its missing monotonic method corrected in this task.

Actual Chromium synthetic 2,500-map fixture: initial DOM 16,391 -> 792, desktop list paint 369 -> 81 ms; 4x CPU 1,357 -> 277 ms. Real viewer script failure/retry/disposal and keyboard focus pass. These are isolated fixture measurements, not live latency/p95 or proof that low-end zoning layout is solved.

Runtime activation still requires the qualified guarded generation and explicit owner root operation; never overwrite current sealed runtime. Private operational kit is offline only. No production backend/site source cutover yet. Website files remain no-cache until content-versioned publication exists.
