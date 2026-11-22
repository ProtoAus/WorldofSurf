# World of Surf 0.1.58 delivery

Published 22 Nov 2026, completing at **~10:09 UTC** (20:09 local; worldofsurf-88) from the Linux PC, one sealed candidate,
no rebuild, under Lex's standing go-ahead, after Lex's "Can you do all the stuff you said is not done yet?" (the
ahop_coast/bhop_canals visual audit). Page: <https://proto.bar/ftesurf>.

- Version **0.1.58** (QC build 92). Frozen QC `3d6624f8` = main at the cut (branch `release-0.1.58` in release0158-88;
  tag `v0.1.58`). 7 patch entries: P1721 (infodecals placed/oriented/sized as Source), P1722 (the sun on unbaked Source
  models), P1723 (the map's bloom scale), P1724 (r_shadows 2 follows the map; live toggle fixed), P1726 (phys_motor:
  ahop_coast's windmill turns, body hull untouched), P1727 (worldofsurf-08: replay watch runaway), P1728 (worldofsurf-5a:
  Story tiers). P1725 rides in P1724's note.
- Progs: qwprogs `1ab03d45`, csprogs `0b99ceff` (appended to tasrevd codes.txt by the lobby deploy), menu `3584204b`.
- Engine **7bc12f971** (patch-1724): Windows cross-built (TLS check 0 plain-address uses); Linux built in the Debian 11
  rootfs (BUILDINFO gates G1-G10 PASS); both stamp `git-9007-patch-1724-0-g7bc12f971`.
- Launchers unchanged (Windows bootstrap reused from 0.1.57, Linux 0.1.7).
- Prepared `48d4bd67d947acab6d633be4e6bc1b4585d3d7c7e7f8a7dcd426f826e8acca87`; live feed `a962c11f` (prev 0.1.57
  `684be379`); 1290 objects; `-MaxTotalMB 132` (stage 128.5 MB).

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.58.7z` | 79,392,702 | `683d38f865241d0c767f080ae97c1befbabc4953a7b1de5ef741be1c6e947e30` |
| `ftesurf-0.1.58-linux-x86_64.tar.xz` | 79,809,568 | `f23c71dd36171201b10cad5bf06ea2b533f616650c2838467af41aef8d2c927e` |
| `WOS-Launcher-0.1.58.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.58-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS; preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects; publish
  `-VerifyFull` rc 0; release_smoke linux64 1384 / win64 1383 managed files rehashed from the live feed.
- Wine smoke: game rc 0, both screenshots. Linux game smoke: 5/5 (engine patch-1724, eye 64 then 28).
- After the lobby swap, the released Linux client on lobby 12: engine patch-1724, pm_sourceversion 15, noclip ON/OFF
  with 0 prederr, no client errors.

## Lobbies (one 10 s warning, one restart each, 10:09:21-10:10:13Z; tools/deploy0158.sh in the root)

- The release's progs over v0.1.57 + P1727 (qw e0fa1b80 / cs f1c57d33). Engine patch-1717 049f7062 + plugin 55778b14
  unchanged (0.1.58's engine changes are client-only). Backups `*.pre0158-20261122T100921Z`.
- Live after: all 12 active, patch-1717, pm_sourceversion 15, no program errors in the journal since the swap.

## Scope and limits

Automated checks only; owner check pending (lextest.md). P1726's motor edicts are late, non-solid points: on a map with
a turning motor and a ForceSpawned solid template member, that member's edict number shifts by one (the exposure every
stashed class has; ahop_coast has none). Still not shown: a mover-15 run verified end to end (no player run since
0.1.57's lobby swap). Root `FTESurf-worktrees/release0158-88` keeps qc/dist, artifacts and inputs until the next release.
