# World of Surf 0.1.68 delivery

Published 24 Nov 2026 (UTC; 25 Nov in Lex's time zone), completing at **17:57:57 UTC** (worldofsurf-67, session 55) from
the Linux PC, one sealed candidate, no rebuild, after Lex's fourth bhop_canals pass (saves 33-41 beside Momentum) and his
note "sun sprite should be blocked by 3d skybox geometry". Page: <https://proto.bar/ftesurf>.

- Version **0.1.68** (QC build 102). Frozen QC `6518d999` = main at the cut (branch `release-0.1.68` in release0168-67;
  tag `v0.1.68`). Player-facing entries: P1805 (Strata props lit by local lights again), P1804 (the sun sprite fades
  behind hills and the 3D skybox), P1803 (lit smoke volumes), P1802 (tree cards cast branch shadows), P1801 (the
  r_shadows 2->1 crash), P1800 (inverted-fade static props drawn: save 33's driftwood).
- Progs (release build): qwprogs `b442b030`, csprogs `e5fb3ab9`, menu `b198d6ff`.
- Engine **763640620** (patch-1799 + 12: P1800-P1805 and the records over bd0111709; client-side only, mover 16
  unchanged); stamp `git-9082-patch-1799-12-g763640620`; Windows cross-build and the bullseye Linux drop (gates PASS).
- Launchers unchanged (Windows bootstrap reused from 0.1.67, Linux 0.1.7).
- Prepared `2ac82201c92a35fcfe81281a0af6ae87593d363d8d028b4ccd97152807445d9b`; previous feed 0.1.67 `b2a96cff`;
  1290 objects; `-MaxTotalMB 132` (stage 128.8 MB). Receipt `09351b59`.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.68.7z` | 79,447,482 | `732d411304bb06b8cb8122845a675be37d7eeaab8b6922708e9cfa5a2dd6daed` |
| `ftesurf-0.1.68-linux-x86_64.tar.xz` | 79,916,508 | `ab2967be5be43cf2f1fbb85ccb90ed36b779741ffb4c03ea884f6cf973b6b53e` |
| `WOS-Launcher-0.1.68.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.68-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (first run); preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects;
  publish `-VerifyFull` rc 0 (archives round-tripped, page byte for byte); release_smoke linux64 1384 / win64 1383 managed
  files rehashed; live feed reads 0.1.68.
- Wine smoke of the Windows stage: game rc 0, screenshots looked at (HUD 0.1.68). Linux game smoke: PASS (patch-1799-12
  stamp, eye 64 then 28).
- Rig before the cut (canalsgfx root): save 33 against Momentum 0018 (logs and branch shadows), save 39 against 0025
  (lit cans and barrels), save 38 (faint smoke), saves 40/41 and a sweep (sun fades behind hills); canals saves 5-21/29/32
  against 0.1.67 unchanged but for the intended (save 5's ramp is not deterministic between runs, any build); surf_shady
  and bhop_ancientcanals identical to 0.1.67. Timing saves 8/6/5: GPU +0.0-0.1 ms.
- P1800-P1805 had three review rounds (fixes: P1804 honours vbsp_skyroom and the default scale, traces only near the
  screen and when the eye moves, VF_FOV is zero before renderscene (fallback fov widened by the aspect); P1802 props only;
  P1801 also guards GLBE_DrawMesh_List).
- Lex's dev install: client/server/plugins/progs from the stage at 18:04Z (`tools/install-dev0168.sh`,
  `.pre0168-20261124T180408Z`).
- The 0.1.67 records' dates were corrected first (6518d999): 0.1.67 published 24 Nov UTC, not 25 Nov.

## Lobbies

Restarted 18:12:57-18:13:18Z (one restart each, after one player waited out with the 1 min and 10 s notices);
tools/deploy0168.sh in the root.

- Progs only: the release's qwprogs `b442b030` / csprogs `e5fb3ab9` (csprogs appended to codes.txt, 188 lines) over
  0.1.67's `b0760514` / `33515a70`; backups `*.pre0168-20261124T180353Z`. Engine stays patch-1747 (0.1.63's arm64,
  surfd's verifier).
- After: 12 lobbies answering, 0 players; no error lines in any server<N>.log.
