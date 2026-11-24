# World of Surf 0.1.66 delivery

Published 24 Nov 2026, completing at **08:43:16 UTC** (worldofsurf-67) from the Linux PC, one sealed candidate, no rebuild,
after Lex's third bhop_canals pass ("Here's some notes, but please continue": saves 21-31 beside Momentum). Page:
<https://proto.bar/ftesurf>.

- Version **0.1.66** (QC build 100). Frozen QC `cd272b43` = main at the cut (branch `release-0.1.66` in release0166-67;
  tag `v0.1.66`). Player-facing entries: P1773 (prop shadows no longer fade and snap back on approach: cascade casters
  not sphere-culled), P1774 (cascade-map shadows keep the surface's colour, no teal), P1775 (auto-exposure: dark rooms
  no longer open to the maximum), P1776 (blood/multiply decals no longer brighten their surface; named infodecals wait
  for their input), P1777 (Strata maps: local lights off unbaked props -- canals' barrels/cans/crates), P1778 (barn
  shafts point at the sun patches again), P1779 (no guessed _glow texture on Source materials: the street lamp), P1780
  (Strata's baked prop sun from the .vhv alpha, under the cascades).
- Progs (release build): qwprogs `3dc34294`, csprogs `d92f8394`, menu `33dc0ab6`.
- Engine **e9dc66c46** (patch-1780 + 1: the records with the review fixes, over 0c1525f67; client-side only, mover 16
  unchanged); stamp `git-9065-patch-1780-1-ge9dc66c46`; Windows cross-build and the bullseye Linux drop (gates PASS).
- Launchers unchanged (Windows bootstrap reused from 0.1.65, Linux 0.1.7).
- Prepared `031e6786c86ab7724904fcf738bbfaa30eaefd235c9dadea9dbcd24a4be9ec7e`; previous feed 0.1.65 `896427ec`;
  1290 objects; `-MaxTotalMB 132` (stage 128.7 MB). Receipt `9ce192c0`.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.66.7z` | 79,444,969 | `24a243e1662ce04007a935498ad57487cb35a95c06736c785a3940cc2e327cd7` |
| `ftesurf-0.1.66-linux-x86_64.tar.xz` | 79,900,912 | `cf39fa3e065a1259525be9b9f293f794f38889a8949a626e662d6c6557e6e670` |
| `WOS-Launcher-0.1.66.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.66-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (first run); preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects;
  publish `-VerifyFull` rc 0 (archives round-tripped, page byte for byte); release_smoke linux64 1384 / win64 1383
  managed files rehashed (first try refused: the root had no OWNER.md -- "owned task root"); live feed reads 0.1.66.
- Wine smoke of the Windows stage: game rc 0, screenshots looked at (HUD 0.1.66). Linux game smoke: PASS (patch-1780
  stamp, eye 64 then 28).
- On the STAGED Linux client + progs, bhop_canals: saves 28 and 21 pixel-identical to the rig build, save 30 within
  0.12, the street lamp's sunlit/shaded levels 193/56 (rig 194/55; calibration vs Momentum in ENGINE_PATCHES P1780);
  r_shadows_vhvsun 8.85 7.72 4.70 with hl2_bspversion 25.
- Rig before the cut: saves 5-21 against 0.1.65 (only the intended changes), surf_shady identical but for the HUD,
  interleaved timing saves 8/6/5 +0.1-0.3 ms.
- P1773-P1780 had two review rounds (fixes: vhv alpha stays 255 off Strata + a v25 gate for the sun term, per-channel
  hdrsat, ortho cull in the depth pass only, no shadow floor on a Strata baked prop).
- Lex's dev install: client/server/plugins/progs from the stage (`tools/install-dev0166.sh`, `.pre0166-20261124T084516Z`).

## Lobbies

Empty; one warning and one restart each, 08:45:40-08:46:01Z; tools/deploy0166.sh in the root.

- Progs only: the release's qwprogs `3dc34294` / csprogs `d92f8394` (csprogs appended to codes.txt, 186 lines) over
  0.1.65's `c0c66e9f` / `63f62701`; backups `*.pre0166-20261124T084506Z`. Engine stays patch-1747 (0.1.63's arm64,
  surfd's verifier).
- After: 12 lobbies answering, pm_sourceversion 16; no error lines in any server<N>.log; the released 0.1.66 Linux
  client on lobby 3: connected, CSQC up, 0 prediction errors.
