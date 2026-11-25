# P1834 owned native driver

`tools/test_p1834_native.py` is test-only. The P1838 parent executed all eight
native cases successfully on 25 Nov 2026; this is scoped functional evidence,
not a fleet deployment or speed benchmark. Serialize it under the game lock with
an inspected coherent dedicated engine/plugin and already-built current QC.
Wide-global inspection requires the P1838 FTE32/QTEST typed-definition repair;
the driver does not choose/build/download an engine or infer provenance from a name.

## Invocation

From the QC worktree, substitute explicit inspected paths (no paths embedded in
the driver):

```sh
wos-lock game -- python3 -B tools/test_p1834_native.py \
  --engine /absolute/owned/engine/release/fteqw-sv64 \
  --plugin /absolute/owned/engine/release/fteplug_hl2_amd64.so \
  --progs /absolute/owned/current-NoDeploy-output \
  --assets /absolute/owned/bounded-fixture-assets \
  --out "$PWD/rig/lobbyfast/native-owner-first" --case owner
```

`--progs` is a directory containing qwprogs.dat, csprogs.dat and menu.dat. Retain
the associated build/qcframes/source receipt: output hashes alone do not prove
which source produced those progs. `--assets` is an explicit **bounded** ordinary
asset directory, not a whole install or map library. No symlinks are accepted.
Files are copied to the fresh owned root and made read-only. The driver does not
select a canonical install, Steam/private path, SDK or dependency cache. Normal
engine/plugin/config asset discovery may still open local read-only mounts; retain
the native log rather than asserting that no automatic mount occurred.

Run `--case slow`, `pause`, `revoke`, `connecting`, `spectator`, `nonowner`, `date`
with fresh output paths. `--case all` runs all eight in order and stops on the
first failure. Default per-condition timeout is 180s (override `--timeout` for the
completion wait); slow completion may require many 1.2s response cycles. No
speed/performance threshold is asserted. Port allocation is loopback/ephemeral;
a bind race is a failure, never permission to stop another server.

## Acting design

- A disposable bootstrap process loads the raw map from
  `test_ui_modern.make_map`, with expiry disabled and no seeded data. It queries
  actual `poke_ssqc mapname`; extension spelling is never assumed. It then stops.
- Each selected case is a **fresh process/gamedir** seeded by the 176-file helper
  using that exact native mapname. The corrected helper cfg uses **set** for every
  QC-owned policy, before the first map. The target engine sees no prior map's
  cvar registration. A gated localhost HTTP endpoint prevents an ACK/retention
  before fresh-start assertions.
- Requires exact boot echo marker, native spawn, actual QC map identity and actual
  entity/zone readiness. Queries effective policy values (including any effective
  latched-value override), native movement profile, published serverinfo,
  reservation state, queue arming and effective one-second empty deadline. It
  requires all data still intact before the first successful ACK.
- Owner/nonowner/date act real parsers, filesystem search/deletion and original
  predicates across seven roots. Nonowner preserves foreign evidence and emits no
  all-tree stamp. Date seeds yesterday relative to current UTC; native boundary
  interpretation is checked without changing the host clock. A day change during
  an arm fails as inconclusive rather than silently redating the oracle.
- Slow uses actual HTTP responses delayed 1.2s, checks a later pending request
  **after readiness** prevents all queue progression, then requires completion
  and nonoverlapping ordinary requests. It does not replace HTTP callback/QC code.
- Pause observes an actual first-root open search, writes only the allowed fixture
  checkpoint `sv_maint_next`, connects its own real QW slot, releases that deadline
  and checks the native guard with **no pending HTTP request**. It refreshes only
  the planned expired metadata while occupied, kicks its own slot, and requires
  native completion with refreshed/protected bytes unchanged.
- Revoke pauses an actual all-tree iterator before its first result, revokes the
  existing ownership cvar, releases the deadline and requires closure, preserved
  foreign bytes and no completion stamp. A missed checkpoint fails; it is not
  rewound with fake iterator/parser state.
- Connecting/spectator use QW UDP getchallenge + connect protocol 28 with unique
  qports and synthetic names. Native class-specific status must list the owned
  slot. No new/prespawn/spawn/begin gameplay command is sent. A held HTTP response
  then sends a syntax-valid `map p1834_other`; actual QC must refuse it, keep mapname
  unchanged, leave map-command pending clear and retain all files. The driver sets
  both native maxspectators and the requested sv_maxspectators fixture value.
  `kick # 1` acts only inside the freshly owned server, whose sole client it made.

There are **no production hooks, fake active entities, replaced parsers, fake
filesystem builtins or clienttype overrides**. Only queue deadlines are poked;
all other poke operations read globals. Reservation and movement-profile guards
are queried to avoid attributing a blocked arm to the wrong predicate.

## Evidence, cleanup and limits

Fresh output is restricted beneath this QC worktree's `rig/`. The root has an
OWNER marker and input/source SHA-256 receipt; every process/case has argv, owned
PID, port, query outputs, local HTTP timing, verification results and actual exit.
Copied binary/progs hashes and original immutable inputs are checked. Processes
are stopped by their exact Popen handles in finally (quit, then owned terminate/
kill only if necessary); the driver never kills by name or cleans data. Failed
arms remain for diagnosis. No commit/deploy/release or automatic cleanup occurs.

PASS means **only selected completed native arms**. The receipt explicitly lists
unreached cases: fully spawned active-player protection, literal midnight
rollover, native-policy object expiry, failed enqueue/timeout/stale callbacks,
reserved/custom/disabled cadence, and accepted-empty directed transition. Native
policy functions are not replaced and their queue phases run, but no native
policy object grammar is invented and their expiry effect is not certified.
The file verifier's `native_run_attested: false` remains honest: the wrapper's
separate process/guard/query/exit evidence is what can attest actual native acting.

Synchronous scans/native policy/per-slot parsing remain unbounded in wall time.
Neither script writing, `--help`, AST checks nor fixture-oracle unit tests are
native validation. Review actual run logs and hashes before reporting acceptance.
