# World of Surf 0.1.56 delivery

Published 21 Nov 2026, completing at **~21:13 UTC** (22 Nov 08:13 local; worldofsurf-88) from the Linux PC, one sealed
candidate, no rebuild. Lex: "can you get all the latest updates and push a new release, and push to lobbies, full
upgrade please". Page: <https://proto.bar/ftesurf>.

- Version **0.1.56** (QC build 90). Frozen QC `a0c594f3` = main at the cut (branch `release-0.1.56` in release0156-88;
  tag `v0.1.56`). 4 patch entries: P1705 (lobby engine fix), P1706 (noclip/ghost/rewind resume/sl_load predicted at
  high ping), P1707 (zones in every local game), P1709 (mover 14: Momentum 0.10 landings, ahop rules; Jargon KSF start).
  NOT in it: P1708 (uncommitted engine candidate), P1710 (worldofsurf-2c, rides later), worldofsurf-5a's Jargon
  follow-up dac82f8c/612b24a4 (landed on main after the freeze).
- Progs: qwprogs `bb26775e`, csprogs `b5dc2419` (appended to tasrevd codes.txt by the lobby deploy, 171 lines,
  backup .pre0156lobby-20261121T211528Z), menu `4576f9c9`.
- Engine **1786d7225** (patch-1709): Windows cross-built in the root's engine worktree (TLS check 0 plain-address uses);
  Linux built in the Debian 11 rootfs (BUILDINFO gates G1-G10 PASS); both stamp `git-8985-patch-1709-0-g1786d7225`.
- Launchers unchanged (Windows bootstrap reused from 0.1.55 via `-ReuseWindowsBootstrap`, Linux 0.1.7 13e7327).
- Prepared `50e9e1bf7f6e84c962eb8ffb3ec5a7838abd6d19769bfca37404e338cf50a702`; live feed `3835e261` (prev 0.1.55
  `1cccf7cb`); 1290 objects; `-MaxTotalMB 130`.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.56.7z` | 79,381,888 | `c58c38b37eab0e9fd980d04e8037f04e78fc8c0c1a7ac52ad866e0b343a93a1b` |
| `ftesurf-0.1.56-linux-x86_64.tar.xz` | 79,804,144 | `443b4242679e7165a197d422931b0d07cb56d072b553641be490f3d8057ff7fb` |
| `WOS-Launcher-0.1.56.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.56-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (4 patches); preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects;
  publish `-VerifyFull` rc 0 (both archives, launchers and 1290 objects round-tripped; page and feed served byte for
  byte); release_smoke linux64 1384 / win64 1383 managed files rehashed from the live feed.
- Wine smoke of the Windows stage: game rc 0, both screenshots. Linux game smoke of the Linux stage: 5/5 (engine
  patch-1709, eye 64 then 28).
- After the lobby swap, the released Linux client on lobby 12: engine patch-1709, pm_sourceversion 14, fs_wop* keys,
  noclip ON/OFF with no prederr.

## Lobbies (one 10 s warning, one restart each, 21:16:02-21:16:24Z; tools/deploy0156.sh in the root)

- Engine **patch-1709** arm64 `59bc2e04` + hl2 plugin `356933f3` (built on the Pi from a git-blob tarball of 1786d7225,
  /srv/nvme/agent-work/eng1709-20261121-88, stamp git-8985-patch-1709-0-g1786d7225; descends from patch-1705's
  33284da9c). It is also the surfd verifier (sweep.py ENGINE = game/fteqw-svarm64): no generation needed.
  Gate: old (patch-1705) vs new identical on the live cfg (pm_dettest x7 maps + 12 pm_verify runs, 129 lines); with the
  staged cfgs the new server reports pm_sourceversion 14 / fixslopes 2 and the 12 runs give the same 9 PASS / 3 cold-
  rewind REFUSE.
- The release's progs (above), over P1706's 7079778d / 3a2ae666.
- P1709's lobby cfgs: cfg/default.cfg = the Pi's own (hand-deployed 12 Oct) copy with ONLY pm_fixslopes 2,
  pm_groundtracedist 2, pm_jumpzoffset 0 changed (`32a3a5b6`; its 209 other differences from main are client-only);
  cfg/lobby/mode_ahop.cfg = main's (`cf19a379`: P1631's pm_normalizejump 0 + P1709's pm_fixslopes 3). lobby_local.cfg
  untouched.
- Predecessors kept as `*.pre0156-20261121T211528Z` beside each file. Rollback: copy each back over a .rb name, mv into
  place, restart every ftesurf@N; to back out only P1709's movement, restore the two cfgs.
- Live after: all 12 active, `*version` git-8985-patch-1709-0-g1786d7225, pm_sourceversion 14, pm_fixslopes 2,
  pm_groundtracedist 2, pm_jumpzoffset 0, no program errors.

## Scope and limits

Automated checks only; owner check pending (lextest.md). 0.1.55 clients on the upgraded lobbies predict fixslopes 2 as 1
(rubber-banding on uphill landings) until they update. Root `FTESurf-worktrees/release0156-88` keeps qc/dist, artifacts,
inputs and the Pi build root until the next release.
