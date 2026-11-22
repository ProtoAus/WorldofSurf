# World of Surf 0.1.60 delivery

Published 22 Nov 2026, completing at **~18:22 UTC** (23 Nov 05:22 local; worldofsurf-88) from the Linux PC, one sealed
candidate, no rebuild, under Lex's standing go-ahead, after his 23 Nov list ("I have some things I need delt with").
Page: <https://proto.bar/ftesurf>.

- Version **0.1.60** (QC build 94). Frozen QC `71155428` = main at the cut (branch `release-0.1.60` in release0160-88;
  tag `v0.1.60`). 9 patch entries: P1736 (Source liquid brush entities not two-sided: bhop_canals' goop no longer flickers
  black), P1737 (report points), P1738 (story tier text at 16 px), P1739 (mount games' Steam icons on map cards), P1740
  (favourite maps), P1741 (edge-to-edge 90 px card rows), P1742 / P1733 / P1731 (worldofsurf-08: prediction keeps an
  agreeing snapshot; the memo keys reachable physents; VMT DX-level blocks). P1734 (worldofsurf-2f) is backend only.
  Release-time fix on main: shipguard denies P1740's runtime data/favourites.txt (71155428).
- Progs: qwprogs `033412f1`, csprogs `186e76bb` (appended to tasrevd codes.txt by the lobby deploy), menu `9256e9bd`.
- Engine **6e3a1d3f0** (patch-1739, over patch-1742): Windows cross-built (TLS check 0 plain-address uses); Linux built in
  the Debian 11 rootfs (BUILDINFO gates G1-G10 PASS); both stamp `git-9033-patch-1739-0-g6e3a1d3f0`. The page and receipt
  say "engine patch 1742": release.ps1 reads ENGINE_PATCHES' top heading, which is P1742's entry.
- Launchers unchanged (Windows bootstrap reused from 0.1.59, Linux 0.1.7).
- Prepared `af2a3e56bd73199cb2d086a6f99491d824499562c8051b395ac14975290d79bb`; live feed `67bbe71b` (prev 0.1.59
  `e5c08c03`); 1290 objects; `-MaxTotalMB 132` (stage 128.5 MB).

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.60.7z` | 79,366,874 | `56b7fd0ff97049f014d3b86993a08bda322dbb525b5d0599f7f84486660531dc` |
| `ftesurf-0.1.60-linux-x86_64.tar.xz` | 79,827,064 | `8f542cde999f6c71216c4884ad7a45563db5b69d967c58d550719400343d2a87` |
| `WOS-Launcher-0.1.60.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.60-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS on the second run (the first caught data/favourites.txt, reached through a #define); preparation gates 1-4
  PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects; publish `-VerifyFull` rc 0 (page and feed byte for
  byte); release_smoke linux64 1384 / win64 1383 managed files rehashed from the live feed.
- Wine smoke of the Windows stage: game rc 0, both screenshots. Linux game smoke: 5/5 (engine patch-1739, eye 64 then 28).
- After the lobby swap, the released Linux client on lobby 12: engine patch-1739, pm_sourceversion 15, noclip ON/OFF with
  0 prederr, no client errors.

## Lobbies (one 10 s warning, one restart each, 18:23:57-18:24:52Z; tools/deploy0160.sh in the root)

- The release's progs over v0.1.59's (qw 45b97cc5 / cs e01610d8), and P1737's data/reportpoints/seed.txt (tools/p1737_seed.py
  --before 20261122_182350 over the Pi's 144 report files and the PC's copies: 145 finished reports, 7 accounts). Engine
  patch-1717 049f7062 + plugin 55778b14 unchanged (0.1.60's engine changes are client-only). Backups
  `*.pre0160-20261122T182356Z`; the seed is new (delete it to undo).
- Live after: all 12 active, patch-1717, pm_sourceversion 15, no program errors or unsupported qcrequests in the journal.

## Scope and limits

Automated checks only; owner check pending (lextest.md). Report points are not shown end to end: no prediction-error
report has been stored since the swap. surfd's report_points (the profile tile) waits for the next generation. Root
`FTESurf-worktrees/release0160-88` keeps qc/dist, artifacts, inputs and stages until the next release.
