# World of Surf 0.1.64 delivery

Published 24 Nov 2026, completing at **01:50:43 UTC** (worldofsurf-67) from the Linux PC, one sealed candidate, no rebuild,
at Lex's ask ("please finish up and then release to lobbies", after P1758-P1761). Page: <https://proto.bar/ftesurf>.

- Version **0.1.64** (QC build 98). Frozen QC `a36bcdef` = main at the cut (branch `release-0.1.64` in release0164-67;
  tag `v0.1.64`). Player-facing entries: P1764 (Source maps adjust their brightness like Momentum: HDR auto-exposure),
  P1763 (bumped props lit by the sun per pixel), P1762 (four sun shadow cascades on Source maps), plus P1754-P1760 from
  "## next" (P1754-P1757 and P1759/P1760 were already live on the lobbies).
- Progs (release build): qwprogs `3cf79c3c`, csprogs `1799fdf7`, menu `40dc6590`.
- Engine **fc2b41745** (tag patch-1764: P1762-P1764 records over 8381b7879/00a3080dc; client-side only, mover 16
  unchanged); stamp `git-9053-patch-1764-0-gfc2b41745`; Windows cross-build (GCC 16 TLS check clean) and the bullseye
  Linux drop (gates G1-G10 PASS).
- Launchers unchanged (Windows bootstrap reused from 0.1.63, Linux 0.1.7).
- Prepared `3a5332d74a2bf32b3e3b9d8163fccf1a21fa4a52f8b4ea54ab415170fe4afd3c`; previous feed 0.1.63 `306a19a5`;
  1290 objects; `-MaxTotalMB 132` (stage 128.7 MB). Receipt `5a66d227`.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.64.7z` | 79,439,678 | `b60780090f0eb04167fac91a9bdd8096d92e5133390492dcae974d5068cfbf9e` |
| `ftesurf-0.1.64-linux-x86_64.tar.xz` | 79,888,528 | `65e58ff0f9be8da358ab9e6bbaa285df637e2c616b2e9442d642dd73fc121fdb` |
| `WOS-Launcher-0.1.64.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.64-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (first run); preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects;
  publish `-VerifyFull` rc 0 (archives round-tripped, page and signed feed byte for byte); release_smoke linux64 1384 /
  win64 1383 managed files rehashed from the live feed; live feed reads 0.1.64.
- Wine smoke of the Windows stage: game rc 0, screenshots looked at (HUD 0.1.64). Linux game smoke: 4/4 PASS (engine
  patch-1764 stamp, eye 64 then 28), screenshots looked at.
- On the STAGED Linux client + progs, bhop_canals saves 5-8 (headless rig): r_shadows_cascades 4, cascade reach 4000
  from env_cascade_light, auto-exposure 2.0 / 2.0 / 0.787 / 1.22 -- the same frames as the rig build.
- P1762-P1764 had three review rounds (the last found the HDR flag surviving a reload with LDR lighting, fixed).
- Lex's dev install: client/server/plugins/progs from the stage (`tools/install-dev0164.sh`, `.pre0164-20261124T015239Z`).

## Lobbies

Empty; one warning and one restart each, 01:53:07-01:53:29Z; tools/deploy0164.sh in the root.

- Progs only: the release's qwprogs `3cf79c3c` / csprogs `1799fdf7` (csprogs appended to codes.txt, 184 lines) over
  P1760's lobby qwprogs `4b6c2c15` / csprogs `29439f65`; backups `*.pre0164-20261124T015235Z`. The engine stays
  patch-1747 (0.1.63's arm64 `54421115`, also surfd's verifier): P1762-P1764 are client-side.
- After: 12 lobbies answering `FTE git-9044-patch-1747-0-ge000687bf`, pm_sourceversion 16; no error lines in any
  server<N>.log since the restart. The released 0.1.64 Linux client on lobby 12 (agtricks) and lobby 3 (surf_shady):
  connected, CSQC up, 0 prediction errors; on surf_shady the csprogs set r_autoexposure 1 and the engine held it at 1
  (that map is lit LDR only: the P1764 gate).
