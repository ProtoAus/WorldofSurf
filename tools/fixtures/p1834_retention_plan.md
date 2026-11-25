# P1834 real-native retention qualification (not yet executed)

This plan supplements source-body tests. Those execute production predicates and
scheduler bodies **with mocks**, not real metadata parsing, filesystem expiry,
native slots, sockets, or engine policy maintenance. The data helper below makes
no native pass claim. Do not use synthetic saves as gameplay/resume evidence.

## Isolation and preparation

Parent holds the game lock for builds/native runs. Use a fresh gamedir underneath
this QC worktree's owned `rig/lobbyfast/` tree; never overlay an install, real player
data, a peer's fixture, or shared caches. No production/SSH/deployment is needed.
Use an existing inspected engine and parent-built test progs; supply a real map
through the rig's existing read-only content arrangement, not a copied map library.

```sh
python3 -B tools/p1834_retention_fixture.py prepare \
  --out rig/lobbyfast/native-owner-data --map YOUR_ACTUAL_TEST_MAP
python3 -B tools/p1834_retention_fixture.py verify \
  --manifest rig/lobbyfast/native-owner-data/expected-files.json --scenario prepared
```

The helper creates a **fresh** `gamedir/`, `p1834_retention.cfg` and
`expected-files.json`. It never launches anything or compiles code. Choose the
actual map before preparing. Execute the cfg before loading the map; verify the
published movement profile is empty so the ordinary root is not intentionally
skipped by the production queue. No clients may accept synthetic resume offers.
The cfg sets no-master/offline mode, native idle retention, 14-day retention and
designated ownership, but no automatic map/start/restart. Use an isolated writable
native policy staging root too: its policy operation is part of the real queue.

## Data and JSON oracle

176 files cover all seven closed resume roots: ordinary, ag-100-v1, ag-250-v1,
ag-1000-v1, cs16-v1, hl2-pre-v1, hl2-post-v1. Metadata is the retention-relevant
`FTESURF-RESUME 1`/`day` grammar from `SV_MsReadMeta`; state includes `flags`,
`track`, `startseg`, `stagerun` from `SV_MsSlotCleanMain`. `run.rec` is explicitly a
non-replay sentinel; no posted-stage/runid promotion is requested.

Each root has expired (age 15), exact boundary (14), fresh (1), non-main track,
malformed numeric state, and expired-then-refreshable cases. The six optional
roots also contain **claimed/open slots** (`ms.txt` plus `ms_fixture_claim.txt`):
`SV_MsSweepProtected` must preserve their metadata, state and recording bytes.
Do not mistake this for an OS open-file-descriptor guarantee. The ordinary root
intentionally retains its old different claim rule; this fixture does not invent
a new ordinary-root claim protection.

Legacy map and foreign-map evidence contain expired/boundary/fresh rec/rct/hid
and undated sentinels. Optional-profile evidence sentinels must remain untouched;
these changes do not widen evidence sweep scope. JSON records each expected path,
SHA-256, case/root, and `unchanged` or `absent` for prepared/owner/nonowner/nextday.

## Native controls / required acting arms

Use actual production functions with actual builtins. A test-only copied
sv_progs.src can follow the existing `cmdcontext_begin.qc`/`cmdcontext.qc` pattern:
rename StartFrame immediately before sv_main.qc (after system defs), append a
wrapper calling the renamed original, and use registered fixture cvars solely to
pause at deterministic iterator checkpoints/print observations. Do not replace
SV_MsReadMeta, SV_MsSlotCleanMain, SV_MsSweepProtected, SV_MsWipeDirProfile,
SV_EvidenceSweepOne, search/fopen/fremove, clienttype, or native policy operations.
Keep new fixture state outside function frames; run qcframes. Such a native driver
has **not** been built/run by this worker and remains parent's integration gate.

1. **Owner baseline:** no occupants/reservation, zones/entities ready, explicit
   no-master. Retain scan/turn logs until `maintenance: retention complete`.
   Expired clean files disappear in all seven roots; protected/fresh/boundary and
   optional evidence bytes stay identical. Both native-policy phases execute.
   Verify `fs_evswept` only after all-tree completion, not merely search open.
   ```sh
   python3 -B tools/p1834_retention_fixture.py verify \
     --manifest rig/lobbyfast/native-owner-data/expected-files.json --scenario owner
   ```
2. **Non-owner:** prepare a separate fresh bundle; set
   `run_evidence_sweepall 0` before map load. Verify `--scenario nonowner`: foreign
   evidence preserved, no whole-tree policy operation or completion stamp.
3. **Occupied pause + fresh mutation:** prepare another bundle. Pause exactly
   after an ordinary-root snapshot opens and before its first result; connect a
   real native client (also test connecting-unspawned and spectator separately).
   Release the artificial checkpoint hold while the native occupant remains.
   Prove file bytes/iterator indices do not advance from the real occupancy guard.
   While occupied, run:
   ```sh
   python3 -B tools/p1834_retention_fixture.py refresh-paused \
     --manifest rig/lobbyfast/native-pause-data/expected-files.json
   ```
   This changes only the planned expired metadata in each root to fresh; requires
   original hashes before writing and updates the JSON oracle. Disconnect the
   owned client, prove the actual queue resumes/completes, then verify owner.
   The already-enumerated slot must be reread, not deleted using cached expiry.
4. **Active player protection independently:** with a real owned fixture client,
   construct/identify its actual `SV_MsRoot` via the native fixture, seed a single
   valid expired `ms.txt` and clean state there, and set one actual
   run_ms_phase/offer/pendat field at a time in the test-only driver. Call the real
   `SV_MsSweepProtected`/per-slot helper for that root. Prove active state, not a
   second claim file or missing state, prevents removal; clear state and prove the
   expired control is deleted. Never claim the seven-root idle-data fixture alone
   certifies this branch: it has no matching real active entity. Retain only
   synthetic test-client identity, never real player GUIDs in reports.
5. **Ownership revocation:** pause at all-tree snapshot-open before processing its
   first result. Revoke `run_evidence_sweepall`; resume. Foreign bytes remain,
   search closes and no completion stamp is emitted. Compare explicit file hashes;
   do not use the ordinary owner JSON oracle for this mixed-progress arm.
6. **Date interpretation:** use a fresh bundle with `--today` equal to yesterday
   UTC and verify `--scenario owner_nextday` against today's native runtime. The
   original boundary files now expire, fresh/claimed/non-main stay protected.
   This exercises real date parsing without changing the host clock. It is NOT a
   mid-scan midnight rollover proof; real across-pause rollover remains a separate
   gate if required. Do not silently redate old evidence/fixtures.
7. **Slow successful HTTP:** use the actual server plus parent-owned local stub,
   1.2s successful ACKs and empty 1s policy. Prove readiness then eventual native
   completion, no overlapping normal request sends, and no work during pending
   requests. Send a late directed response with real connecting/spectator clients;
   no map change. Confirm an accepted empty directed reply blocks work before map
   transition. Source-body tests cover this interaction preliminarily, with
   explicitly mocked transport/directed dispatch.

## Evidence and failures

Retain UTC/source/compiler/engine hashes, fixture manifest and cfg, actual native
command/exit/logs, before/after file hashes, observed occupancy/reservation state,
phase/iterator checkpoints and localinfo completion stamp. Verification reports
`native_run_attested: false` deliberately: helper filesystem checks cannot attest
that an engine acted. Pair them with native execution evidence; never simulate
JSON deletions and report that as native success. Test driver
`test_p1834_retention_fixture.py` deliberately simulates expectations **only to
test the oracle**, and labels that limitation.

Keep failed runs and prepare fresh arms rather than reusing partially swept data.
Synchronous glob/native-policy/parser work still has no hard time bound; collect
its diagnostics and do not claim a hitch ceiling or speedup from file correctness.
