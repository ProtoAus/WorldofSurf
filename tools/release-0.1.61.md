# World of Surf 0.1.61 delivery

Published 23 Nov 2026, completing at **00:32:37 UTC** (23 Nov 11:32 local; worldofsurf-08) from the Linux PC, one sealed
candidate, no rebuild, at Lex's request (23 Nov: "ensure all patches are deployed to the lobbies and ensure all changes
are made in a new release"). Page: <https://proto.bar/ftesurf>.

- Version **0.1.61** (QC build 95). Frozen QC `97d76ecc` = main at the cut (branch `release-0.1.61` in release0161-08;
  tag `v0.1.61`). Player-facing entries: P1743 (cooldown-wired trigger_setspeed boosters predicted from the server gate)
  and P1744 (each player has their own world of a booster: own cooldowns and enter edges per player, the old switch and
  P1185 bank run per world; seven review rounds, tools/p1744model). P1745 (WOS User-Agents) is backend only.
  Release-time fix on main: P1743's first patch-note point split under 250 characters (97d76ecc).
- Progs: qwprogs `bd9ec782` (byte-identical to the rig-tested P1744 build), csprogs `59b63f13` (unchanged from P1743's,
  already in tasrevd codes.txt), menu `89e2fc81`.
- Engine **6e3a1d3f0** = 0.1.60's engine exactly (no engine code change since): 0.1.60's verified binaries reused
  (Windows exe/plugins byte-identical; Linux drop BUILDINFO 6e3a1d3f0, gates all PASS); stamp
  `git-9033-patch-1739-0-g6e3a1d3f0`. The page and receipt say "engine patch 1742" (ENGINE_PATCHES' top heading at that
  commit), as in 0.1.60.
- Launchers unchanged (Windows bootstrap reused from 0.1.60, Linux 0.1.7).
- Prepared `f68c154840f5d1a590f931e3147156792c199b8caf55f6e7fb7c2e58e3249c02`; live feed `7fd6d0c2` (prev 0.1.60
  `67bbe71b`); 1290 objects; `-MaxTotalMB 132` (stage 128.5 MB).

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.61.7z` | 79,414,107 | `f17fea2f91ac82ffd68fc1561bd0f9ce695d6b05f17dde63d68f1f0f589c5278` |
| `ftesurf-0.1.61-linux-x86_64.tar.xz` | 79,860,048 | `6f8bc1c9640dc0b9e97a372208f3144655aaafd2533063c73bc87dc55f780464` |
| `WOS-Launcher-0.1.61.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.61-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (first run, after the patch-note split); preparation gates 1-4 PASS, Linux gates PASS;
  `-PublishPrepared -DryRun` 1290 objects; publish `-VerifyFull` rc 0 (page and feed byte for byte); release_smoke
  linux64 1384 / win64 1383 managed files rehashed from the live feed.
- Wine smoke of the Windows stage: game rc 0, both screenshots looked at (surf_prelude, bkz_goldbhop_gs; HUD 0.1.61).
  Linux game smoke: 5/5 (engine patch-1739, eye 64 then 28).
- P1744 rig (before the cut): two clients on surf_classics S7 at 500 ms both boosted and predicted (P1743 progs: denied /
  1600 u/s mispredict); bhop_sandtrap2 boost1 re-arm 502/260/1227/502; six cooldown pushes in a row, no copy-table
  fallback; no 'inherited player-origin' bank line in any run.
- After the lobby swap, the released Linux client on lobby 12: 0 prederr, noclip ON/OFF.

## Lobbies (empty; one restart each, 00:34:29-00:35:23Z; tools/deploy0161.sh in the root)

- The release's progs over P1743's lobby progs (qw e6b34850 / cs 59b63f13). Backups `*.pre0161-20261123T003429Z`.
  After: all 12 active, patch-1717, pm_sourceversion 15; no program errors in the journal.
- Lobby ENGINE swap (arm64 patch-1717 -> 6e3a1d3f0, also surfd's verifier) waits for ftesurf-e4's gen1745 postflight,
  which pins the current native (049f7062); plan: build + gate on the Pi from the eng1713 recipe, then one swap.
