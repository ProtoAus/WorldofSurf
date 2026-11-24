# World of Surf 0.1.70 delivery

Published 24 Nov 2026 (UTC; 25 Nov in Lex's time zone), completing at **20:53:47 UTC** (worldofsurf-67, session 55) from
the Linux PC, one sealed candidate, no rebuild: mover 17 for bhop_canals' walk-through ramp (Lex's save 5), with the lobby
engine and plugin -- surfd's verifier -- swapped in the same pass. Page: <https://proto.bar/ftesurf>.

- Version **0.1.70** (QC build 104). Frozen QC `89e2b7a1` = main at the cut (branch `release-0.1.70` in release0170-67;
  tag `v0.1.70`). Player-facing entry: P1812 (solid Source props collide through their .phy pieces; runs record
  movement version 17). QC sources unchanged since v0.1.69 (the progs differ by the build stamp).
- Progs (release build): qwprogs `7dde97db`, csprogs `a6ec5be0`, menu `6dc28b3f`.
- Engine **9fc09ffcb** (patch-1799 + 22: P1812 mover 17 and its record over 0bfecb073 and 47's P1820 record);
  stamp `git-9092-patch-1799-22-g9fc09ffcb`; Windows cross-build and the bullseye Linux drop (gates PASS).
- Launchers unchanged (Windows bootstrap reused from 0.1.69, Linux 0.1.7).
- Prepared `53c4223d048bfab2c0537040868872f0161ac80530dd44b5952f74ddbcd8a4a3`; previous feed 0.1.69 `439e3840`;
  1290 objects; `-MaxTotalMB 132` (stage 128.8 MB). Receipt `2cfb0ee9`.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.70.7z` | 79,453,107 | `53a41f2fde7d65f1343c475397d11c4c5ee9b1ec8c6a9083f18fb59ec5137deb` |
| `ftesurf-0.1.70-linux-x86_64.tar.xz` | 79,910,792 | `dcacfa9cbdb93a485ee287531744d87ef03216df24b27d3421090bb5932ca244` |
| `WOS-Launcher-0.1.70.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.70-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (1 patch); preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects;
  publish `-VerifyFull` rc 0; release_smoke linux64 1384 / win64 1383 managed files rehashed; live feed reads 0.1.70;
  main unchanged at the publish.
- Wine smoke of the Windows stage: game rc 0 (outer rc 1, the known false alarm). Linux game smoke: PASS (patch-1799-22
  stamp, eye 64 then 28).
- The staged Linux client on P1761's ramp script at save 5: pmsrcver 17; the walk goes up the panel (z -418 at y 6351),
  over and down to y 5978.
- Local gate (0.1.69 server vs P1812): Lex's canals save recordings exact on both; pm_dettest identical on three maps.
- Pi gate (nanopi:/srv/nvme/agent-work/eng1812-20261124-67, arm64 sv + hl2 plugin at 9fc09ffcb vs the live patch-1747
  pair): "old and new identical" -- 18 lobby runs (12 earlier + 2 ahop_coast, 2 surf_artois, 2 surf_fiellu) 11 PASS /
  7 REFUSE on both (the refusals: older recording forms, e.g. a cold rewind with no stated duration); canals saves 2 and
  33 EXACT (785 / 20162 packets); pm_sourceversion 16 -> 17; prison_throwswitchbase001.mdl's pieces are refused as
  brushes (it keeps its triangle collision, as designed).
- P1812 had two review rounds through two lenses (control flow; recorded evidence and cheating): mover <= 16 resolves as
  before; no route to a false pass; the first cut's entity-read pin (16 on prop-free maps) was replaced by pinning 17
  everywhere.
- Lex's dev install: client/server/plugins/progs from the stage at 20:56Z (`tools/install-dev0170.sh`,
  `.pre0170-20261124T205612Z`).

## Lobbies

Restarted 21:00:42-21:01:03Z (one restart each, after one player waited ~4.5 min and got the 1 min and 10 s notices);
tools/deploy0170.sh in release0170-67.

- ENGINE + PLUGIN + progs in one restart: arm64 `fteqw-svarm64` `190160f1` + `fteplug_hl2_arm64.so` `4f3208f5` (9fc09ffcb,
  patch-1799-22, mover 17 -- also surfd's verifier, sweep.py ENGINE) over the patch-1747 pair `54421115` / `f642ceec`;
  the release's qwprogs `7dde97db` / csprogs `a6ec5be0` (csprogs appended to codes.txt, 190 lines) over 0.1.69's
  `2b8bfc7f` / `1dd36f2c`; backups `*.pre0170-20261124T205537Z` (rollback line in artifacts/deploy0170.log).
- After: 12 lobbies answering (a player back on within a minute); every server<N>.log shows the new stamp and no error.
