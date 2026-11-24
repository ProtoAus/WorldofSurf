# World of Surf 0.1.65 delivery

Published 24 Nov 2026, completing at **04:54:33 UTC** (worldofsurf-67) from the Linux PC, one sealed candidate, no rebuild,
after Lex's second bhop_canals pass ("I need some of this delt with": saves 11-20 beside Momentum). Page:
<https://proto.bar/ftesurf>.

- Version **0.1.65** (QC build 99). Frozen QC `3d14e91f` = main at the cut (branch `release-0.1.65` in release0165-67;
  tag `v0.1.65`). Player-facing entries: P1765 (sharp world shadows on Strata cascade maps, full-length shadows, props
  shadow themselves), P1766 (shadows no longer switch off at a line ahead: cascade blend, 4096 cascade atlas, fading and
  off-view props keep casting), P1767 (vbsp_autoexposure switches at once), P1768 (alpha-tested casters), P1769 (barn
  shafts: no white glow in fog, exact amber tint), P1770 ($selfillum 0 off: dark oaks and railings), P1771 (named HDR
  cubemaps: glass reflects).
- Progs (release build): qwprogs `c0c66e9f`, csprogs `63f62701`, menu `f2445a14`.
- Engine **548a07573** (tag patch-1771: P1765-P1771 records over b9b56f8d2; client-side only, mover 16 unchanged);
  stamp `git-9058-patch-1771-0-g548a07573`; Windows cross-build and the bullseye Linux drop (gates PASS).
- Launchers unchanged (Windows bootstrap reused from 0.1.64, Linux 0.1.7).
- Prepared `b0c498cae1a851c7ab9bb747aea7a0486509c2e91cf28df0543296fbb6981989`; previous feed 0.1.64 `54091188`;
  1290 objects; `-MaxTotalMB 132`. Receipt `6328d143`.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.65.7z` | 79,447,254 | `9c7dd5148df3ea856dd8fe7441c064114d409e0bbdb2863e35565c42e8bd828d` |
| `ftesurf-0.1.65-linux-x86_64.tar.xz` | 79,896,772 | `80c40c834685e55d73d90707fce7439f636992f1a93101f5c0fb53e6b90b010b` |
| `WOS-Launcher-0.1.65.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.65-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (first run); preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects;
  publish `-VerifyFull` rc 0; release_smoke linux64 1384 / win64 1383 managed files rehashed; live feed reads 0.1.65.
- Wine smoke of the Windows stage: game rc 0, screenshots looked at (HUD 0.1.65). Linux game smoke: PASS (patch-1771
  stamp, eye 64 then 28).
- On the STAGED Linux client + progs, bhop_canals saves 8/15/16/17 match the rig build (world shadows, plank shadows,
  amber shafts); save 8's pipe shadow identical across staged/rig binaries and progs.
- P1765-P1771 had three review rounds (fixes: tint copy drawn twice, sun-world cache across maps, RF_SHADOWONLY instead
  of RF_EXTERNALMODEL, cascade atlas clamped to the GPU limit, #ALPHASHADOW, cached cube checks).
- Lex's dev install: client/server/plugins/progs from the stage (`tools/install-dev0165.sh`, `.pre0165-20261124T045618Z`).

## Lobbies

Empty; one warning and one restart each, 04:56:47-04:57:08Z; tools/deploy0165.sh in the root.

- Progs only: the release's qwprogs `c0c66e9f` / csprogs `63f62701` (csprogs appended to codes.txt, 185 lines) over
  0.1.64's `3cf79c3c` / `1799fdf7`; backups `*.pre0165-20261124T045615Z`. Engine stays patch-1747 (0.1.63's arm64,
  surfd's verifier).
- After: 12 lobbies answering, pm_sourceversion 16; no error lines in any server<N>.log; the released 0.1.65 Linux
  client on lobby 3 (surf_shady): connected, CSQC up, 0 prediction errors.
