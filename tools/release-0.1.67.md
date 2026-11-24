# World of Surf 0.1.67 delivery

Published 24 Nov 2026 (UTC; 25 Nov in Lex's time zone), completing at **13:27:28 UTC** (worldofsurf-67) from the Linux PC, one sealed candidate, no rebuild,
after Lex's bhop_canals backlog ("keep going to all is fixed ... make hl2_cubelight 1 default ... the world cascade
shadows seems to get soft sometimes"; "do it, don't wait for me"), carrying worldofsurf-a3's P1796-P1799. Page:
<https://proto.bar/ftesurf>.

- Version **0.1.67** (QC build 101). Frozen QC `ba2eea35` = main at the cut (branch `release-0.1.67` in release0167-67;
  tag `v0.1.67`). Player-facing entries: P1799-P1796 (a3: map uploads with optional zones and a Zone editor tab, TAS
  uploads from KSF bots, every TAS run in the Upload tab, +jumpduck), P1785 (no colour banding: a float scene and a still
  dither, r_dither 1), P1784 (shafts/sprites take the auto-exposure; barn shafts invisible as Momentum's), P1783 (unbaked
  props' sun per pixel: the corrugated ramp's grooves), P1782 (hl2_cubelight 1), P1781 (Strata world sun: one sharp
  shadow edge, save 29/32 as Momentum, displacement normals), P1772 (func_smokevolume).
- Progs (release build): qwprogs `b0760514`, csprogs `33515a70`, menu `5f47af78`.
- Engine **bd0111709** (patch-1799 + 8: a3's P1796-P1799 + P1781-P1785 and the records; client-side only, mover 16
  unchanged); stamp `git-9078-patch-1799-8-gbd0111709`; Windows cross-build and the bullseye Linux drop (gates PASS).
- Launchers unchanged (Windows bootstrap reused from 0.1.66, Linux 0.1.7).
- Prepared `f2f723ca55bda2d00114c79437f80c6702685d16ec2335c247772a0eadd4f239`; previous feed 0.1.66 `240e5d17`;
  1290 objects; `-MaxTotalMB 132` (stage 128.8 MB). Receipt `81f61c69`.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.67.7z` | 79,455,202 | `986bbb14e96382e5cacf8ec96938385e5fbbc1abbe3e48b655f263eb5dc99954` |
| `ftesurf-0.1.67-linux-x86_64.tar.xz` | 79,910,220 | `43b4c2a365e69720ea9c059056046e0666abe0593ac5bd51171996e1b11fbadd` |
| `WOS-Launcher-0.1.67.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.67-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS after one fix: P1797's `data/runs` literal (the player's runs folder) had no shipguard entry --
  DENY_EXACT added on main (ba2eea35). Preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290
  objects; publish `-VerifyFull` rc 0; release_smoke linux64 1384 / win64 1383 managed files rehashed; live feed reads 0.1.67.
- Wine smoke of the Windows stage: game rc 0, screenshots looked at (HUD 0.1.67). Linux game smoke: PASS (patch-1799-8
  stamp, eye 64 then 28). Both at nice 19 while Lex played (his go-ahead: "do it, don't wait for me ... use low priority").
- Rig before the cut (canalsgfx root, nice 10-19): canals saves 5-21/29/32 as reviewed; the merged tree (a3's work on
  top) within 0.05 mean of the pre-merge shots at saves 16/29/32; r_dither: sky columns 54 distinct greens against 42,
  GPU within run noise (+0-0.6 ms), post 0.05 ms. Interleaved timing vs 0.1.66: saves 8/6/5 GPU +0.4/+1.0/+0.6 ms
  (mean of two pairs; single pairs +0.1 to +1.7) -- taken while Lex's Half-Life was open on the same GPU, so noisy;
  before the review fixes, with the machine quiet, the same build line measured +0.2-0.3 ms. Re-time when idle.
- P1772/P1781-P1785: three review rounds (fixes: shader header committed, displacement normals oriented once per
  displacement, unbumped N.L from the normal; sunvis padding/upload, worldcast-off shadows, additive order).

## Lobbies

Restarted 13:40:02-13:40:24Z (one restart each); tools/deploy0167.sh in the root. The first run waited for 2 players on
one lobby from 13:29Z; at 13:38Z Lex said "push update, I want to play", so it was stopped and re-run with no empty-wait
(tools/deploy0167-now.sh: the same script, one 30 s check), which gave the 1 min and 10 s notices.

- Progs only: the release's qwprogs `b0760514` / csprogs `33515a70` (csprogs appended to codes.txt, 187 lines) over
  0.1.66's `3dc34294` / `d92f8394`; backups `*.pre0167-20261124T133754Z`. Engine stays patch-1747 (0.1.63's arm64,
  surfd's verifier): P1781-P1785 are client-side, and a3's +jumpduck is a client command.
- After: 12 lobbies answering, 0 players; no game error in any server<N>.log (lobby 4 logged one 503/500 from the
  social API at startup, not repeated; the API answers).
- Lex's dev install: client/server/plugins/progs from the stage at 13:37Z (`tools/install-dev0167.sh`,
  `.pre0167-20261124T133730Z`), after his game closed.

Correction (0.1.68 cut): the dates first written here, in the PATCHNOTES heading and in the v0.1.67 tag message said
25 Nov; the UTC date was 24 Nov (the tag is left as pushed).
