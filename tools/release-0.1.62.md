# World of Surf 0.1.62 delivery

Published 23 Nov 2026, completing at **05:36:43 UTC** (23 Nov 16:36 local; worldofsurf-08) from the Linux PC, one sealed
candidate, no rebuild, under Lex's standing pattern (his 23 Nov list: bhop_canals fall-through and fps, ahop_coast
downloads and local mode, old save locks, wobbly replays; then every patch on the lobbies and a release). Page:
<https://proto.bar/ftesurf>.

- Version **0.1.62** (QC build 96). Frozen QC `53e23c80` = main at the cut (branch `release-0.1.62` in release0162-08;
  tag `v0.1.62`). Player-facing entries: P1748 (mover 16: far Source brushes collide as they are), P1749 (ahop_coast's
  soundscript names no longer precached as files), P1750 (an older lobby save says it is position only), P1751 (Local-tab
  replays align the runner's view). Release-time fix on main: next's entries sorted highest patch first (53e23c80).
- Progs (release build; build.ps1's NoDeploy manifest name makes the bytes unique to this compile): qwprogs `d2bd004d`,
  csprogs `65de9276`, menu `2e1e0142`. Rig-checked as staged: ahop_coast 9 soundscript skips and no download requests
  (0.1.61's progs: the client asked for sound/coast.windmill and the rest); Akatosh's 3:18.820 Local-tab replay "310 ms
  ahead ... aligned (20.5 to 0.2 degrees over 64 probes)"; 26 timed lobby saves, save 1 "position only", save 26 resumes.
- Engine **3e7ad92da** (tag patch-1748 = P1742 + P1748 with its three review rounds); stamp
  `git-9039-patch-1748-0-g3e7ad92da`; Windows cross-build (TLS check 0 plain-address uses) and the bullseye Linux drop
  (gates G1-G10 PASS). The released Linux binaries land the bhop_canals drops on the bank (-329.5 / -422.7) and on brush
  4283 (-152.6) where 0.1.61 fell to -512 / stood inside at -216.5.
- Launchers unchanged (Windows bootstrap reused from 0.1.61, Linux 0.1.7).
- Prepared `a368c21a0f7c8f03d8a2d3632050a39d291466eb007646ea3d8b5e9c44b0c1b9`; live feed `3d0c3f0b` (prev 0.1.61
  `7fd6d0c2`); 1290 objects; `-MaxTotalMB 132` (stage 128.5 MB).

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.62.7z` | 79,371,546 | `1cf089b0bd69a6a4d39bdd6f79273bbed0f85cdea8aacc58ea81b248530824d2` |
| `ftesurf-0.1.62-linux-x86_64.tar.xz` | 79,863,832 | `5e1d10b4b4135c6eb98207784277ff592bfaa643ad30d6622a4546641963d2d3` |
| `WOS-Launcher-0.1.62.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.62-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (first run); preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects;
  publish `-VerifyFull` rc 0 (page and feed byte for byte); release_smoke linux64 1384 / win64 1383 managed files rehashed
  from the live feed.
- Wine smoke of the Windows stage: game rc 0, both screenshots looked at (surf_prelude, bkz_goldbhop_gs; HUD 0.1.62).
  Linux game smoke: 5/5 (engine patch-1748, eye 64 then 28).
- P1748 (before the cut): pm_recsim of Lex's save 2/3 recordings (mover 15) exact on 0.1.61 and on 1748 (785/785,
  4058/4058); save 2 with its pin edited to 16 diverges at t 4.74, where he walks into brush 4283; recorded pins
  bhop_canals 16, surf_mesa 15; old exe + new plugin = 0.1.61's pm_dettest; new exe + old plugin prints the mismatch line.

## Lobbies (empty; one warning and one restart each, 05:39:03-05:39:25Z; tools/deploy0162.sh in the root)

- arm64 `fteqw-svarm64` `be372f27` + `fteplug_hl2_arm64.so` `b96bb483` (3e7ad92da, stamp git-9039-patch-1748-0-g3e7ad92da)
  and the release's qwprogs `d2bd004d` / csprogs `65de9276`, over 0.1.61's b94f7365 / b9d76a46 / bd9ec782 / 59b63f13;
  backups `*.pre0162-20261123T053830Z`; csprogs appended to tasrevd codes.txt (180 lines). Built and gated in
  nanopi:/srv/nvme/agent-work/eng1748-20261123-08 (eng1748.sh, from eng1739.sh): 1157 blobs verified, warnings as
  before (16 + 1), GATE old and new identical (130 lines: pm_dettest 7 maps, 24 pm_verify runs 9 PASS / 3 REFUSE as
  0.1.61, Lex's bhop_canals save 2 pm_recsim 785/785 exact on both); pm_sourceversion 15 -> 16; bhop_canals' plain-trace
  hashes differ as on x86 (identical hashes across the two architectures), mover hashes identical; skew run unchanged.
- After: all 12 active and answering `git-9039-patch-1748-0-g3e7ad92da` / pm_sourceversion 16; each lobby's own log
  (server<N>.log; the journal is not readable to proto) has no Host_Error/program error/crash since its patch-1748 start.
- The released 0.1.62 Linux client (git-9039-patch-1748-0-g3e7ad92da) on lobby 12 (ping350 arm, p1706arm.py rel --bin
  bin_rel0162 --sections live): 0 prederr, noclip ON/OFF.
- This native is surfd's verifier now (sweep.py ENGINE = game/fteqw-svarm64): new runs on maps with far brushes (e.g.
  bhop_canals) pin 16 and verify at once; the next surfd generation's kit must pin be372f27.
