# World of Surf 0.1.57 delivery

Published 22 Nov 2026, completing at **~03:46 UTC** (14:46 local; worldofsurf-88) from the Linux PC, one sealed
candidate, no rebuild, under Lex's standing go-ahead (22 Nov: "you have my advanced go head, I love when my lobbies and
client and servers and websites are updated"). Page: <https://proto.bar/ftesurf>.

- Version **0.1.57** (QC build 91). Frozen QC `701c4e07` = main at the cut (branch `release-0.1.57` in release0157-88;
  tag `v0.1.57`). 10 patch entries: P1710 (old-game runs marked), P1711 (Jargon guide start + aim), P1712 (TAS upload
  offer), P1713 (mover 15: teleport-exit jumps, SOLID_VPHYSICS brush entities through their vcollide), P1714 (prediction
  skips unreachable physents), P1715 (run lines native), P1716 (TAS uploads straight to the board), P1717 (Source props
  lit at Source's scale; Strata leaf light), P1719 (sky water shares the main capture), P1720 (prediction memo).
  Release-time fixes on main: three patch-note points split under the 250-character limit (0d1678b2); shipguard denies
  P1712's runtime data/tasproj/upload_offer.txt (701c4e07).
- Progs: qwprogs `e0fa1b80`, csprogs `fb427ec1` (appended to tasrevd codes.txt by the lobby deploy), menu `2825952e`.
- Engine **e4f48ac0e** (patch-1717, carrying P1713/P1714/P1719/P1720): Windows cross-built in the root's engine worktree
  (TLS check 0 plain-address uses); Linux built in the Debian 11 rootfs (BUILDINFO gates G1-G10 PASS); both stamp
  `git-9001-patch-1717-0-ge4f48ac0e`.
- Launchers unchanged (Windows bootstrap reused from 0.1.56 via `-ReuseWindowsBootstrap`, Linux 0.1.7).
- Prepared `9f07f5aa04a2a93c553e9e1b17b34e3dbddd2fe4bb9ee8484f75f4a8abcf56f9`; live feed `684be379` (prev 0.1.56
  `3835e261`); 1290 objects; `-MaxTotalMB 130` (stage 128.5 MB).

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.57.7z` | 79,391,885 | `ccb01b35777ec71a37894f67c5d2eb682abd8fb01715f94185c49a9b3b4156fe` |
| `ftesurf-0.1.57-linux-x86_64.tar.xz` | 79,810,432 | `f79a62e0c1e3794a3974a2cf93e2614ab24facc06ed32a91ab127e522f4c37fa` |
| `WOS-Launcher-0.1.57.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.57-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (10 patches; first run caught the shipguard miss); preparation gates 1-4 PASS, Linux gates PASS;
  `-PublishPrepared -DryRun` 1290 objects; publish `-VerifyFull` rc 0 (archives, launchers and 1290 objects
  round-tripped; page and feed served byte for byte); release_smoke linux64 1384 / win64 1383 managed files rehashed from
  the live feed.
- Wine smoke of the Windows stage: game rc 0, both screenshots. Linux game smoke of the Linux stage: 5/5 (engine
  patch-1717, eye 64 then 28).
- After the lobby swap, the released Linux client on lobby 12: engine patch-1717, pm_sourceversion 15, fs_wop* keys,
  noclip ON/OFF with 0 prederr, no client errors.

## Lobbies (one 10 s warning, one restart each, 03:46:12-03:47:08Z; tools/deploy0157.sh in the root)

- Engine **patch-1717** arm64 `049f7062` + hl2 plugin `55778b14` (built on the Pi from a git-blob tarball of e4f48ac0e,
  /srv/nvme/agent-work/eng1713-20261122-88, stamp git-9001-patch-1717-0-ge4f48ac0e). It is also the surfd verifier
  (sweep.py ENGINE = game/fteqw-svarm64): no generation needed. Gate on the live cfg: old (patch-1709) vs new identical
  on pm_dettest x7 maps + 12 pm_verify runs (9 PASS / 3 REFUSE, 132 lines); the new server reports pm_sourceversion 15.
- The release's progs, over v0.1.56 + P1710 + P1715 (deploy/p1715-lobby, now obsolete). No cfg change.
- Predecessors kept as `*.pre0157-20261122T034612Z` beside each file. Rollback: copy each back over a .rb name, mv into
  place, restart every ftesurf@N.
- Live after: all 12 active, `*version` git-9001-patch-1717-0-ge4f48ac0e, pm_sourceversion 15, no program errors in the
  journal since the swap.
- The one-lobby canary BACKLOG "P1713" asked for was not run: all lobbies share one game dir (see BACKLOG).

## Scope and limits

Automated checks only; owner check pending (lextest.md). 0.1.56 clients on the upgraded lobbies mispredict mover 15's
two changes (teleport-exit jumps, SOLID_VPHYSICS clip ramps) until they update. Not shown: a mover-15 run verified end
to end by surfd. Root `FTESurf-worktrees/release0157-88` keeps qc/dist, artifacts, inputs and the Pi build root until the
next release.
