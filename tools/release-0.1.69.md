# World of Surf 0.1.69 delivery

Published 24 Nov 2026 (UTC; 25 Nov in Lex's time zone), completing at **19:26:33 UTC** (worldofsurf-67, session 55) from
the Linux PC, one sealed candidate, no rebuild: the tree LODs and envmap follow-ups to Lex's fourth bhop_canals pass, with
worldofsurf-8b's P1806 and worldofsurf-47's P1820 notes and site files. Page: <https://proto.bar/ftesurf>.

- Version **0.1.69** (QC build 103). Frozen QC `65bb87b5` = main at the cut (branch `release-0.1.69b` in
  release0169b-67; tag `v0.1.69`). Player-facing entries: P1820 (47: map downloads and the site menu), P1811 (envmaps
  exposed and added in linear light), P1810 (Source model LODs at Source's switch points), P1806 (8b: TAS uploads on the
  boards' TAS tab, live since 18:37Z; the 30-day Steam sign-in becomes true when Lex runs the staged root tasupd upgrade).
- Progs (release build): qwprogs `2b8bfc7f`, csprogs `1dd36f2c`, menu `4bf68e9b`.
- Engine **0bfecb073** (patch-1799 + 18: P1810/P1811 and the records over 763640620 and 8b's P1806 record; client-side
  only, mover 16 unchanged); stamp `git-9088-patch-1799-18-g0bfecb073`; Windows cross-build and the bullseye Linux drop
  (gates PASS), built in release0169-67.
- Launchers unchanged (Windows bootstrap reused from 0.1.68, Linux 0.1.7).
- Prepared `9eceee2094f2e1b32c6c00746a691be0c243d7b1cfa84c6685e9e8f5803375f4`; previous feed 0.1.68 `614e48c8`;
  1290 objects; `-MaxTotalMB 132` (stage 128.8 MB). Receipt `9c22bcf5`.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.69.7z` | 79,453,548 | `cb2bac9e45957d3401e1550a6864f7525c9c4ad5d5169f4c210523a5bce4b73a` |
| `ftesurf-0.1.69-linux-x86_64.tar.xz` | 79,878,520 | `192933ee804c9dbe9e4d18309acdb4d6396630e1f14c637d50285217f02cdd39` |
| `WOS-Launcher-0.1.69.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.69-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- A first candidate (release0169-67, prepared from a311bb05) was abandoned unpublished when worldofsurf-47 pushed P1820's
  site files (cbefd439) mid-cut -- publishing it would have rolled the site back. release.ps1 will not prepare a version
  twice in one root, so the re-cut is a fresh root at main 65bb87b5 reusing the same engine build and Linux drop; 47's
  in-place site publish into releases/0.1.68 finished (19:08Z) before this publish; main unchanged at the publish.
- Preflight PASS; preparation gates 1-4 PASS, Linux gates PASS; the staged site carries dl.js/get.html/sitenav;
  `-PublishPrepared -DryRun` 1290 objects; publish `-VerifyFull` rc 0; release_smoke linux64 1384 / win64 1383 managed
  files rehashed; live feed reads 0.1.69, get.html 200.
- Wine smoke of the Windows stage: game rc 0, HUD 0.1.69. Linux game smoke: PASS (patch-1799-18 stamp, eye 64 then 28).
- Rig before the cut (canalsgfx root): oak_tree01 at its LOD levels (save 41 level 1, close level 0), nothing garbled;
  save 36's pane 52 -> 57.5 (Momentum 124); canals saves 6-32 as 0.1.68 but for the intended (distant trees, envmapped
  props within a level); timing saves 8/6/5 GPU -0.1/0/0 ms.
- P1810/P1811 had three review rounds (VRAM: identical vertex arrays share one buffer; zero and falling switch points;
  the shadow and cascade metric; viewmodels; envmaps added in linear light).
- Lex's dev install: client/server/plugins/progs from the stage at 19:28Z (`tools/install-dev0169.sh`,
  `.pre0169-20261124T192832Z`).

## Lobbies

Restarted 19:49:57-19:50:20Z (one restart each, after one player waited out the 20 min with the 1 min and 10 s notices);
tools/deploy0169.sh in release0169b-67.

- Progs only: the release's qwprogs `2b8bfc7f` / csprogs `1dd36f2c` (csprogs appended to codes.txt, 189 lines) over
  0.1.68's `b442b030` / `e5fb3ab9`; backups `*.pre0169-20261124T192817Z`. Engine stays patch-1747 (0.1.63's arm64,
  surfd's verifier).
- After: 12 lobbies answering, 0 players; no game error in any server<N>.log (lobby 1 logged the social API's one 503/500
  at startup, as at 0.1.67's deploy).
