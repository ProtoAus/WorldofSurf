# World of Surf 0.1.59 delivery

Published 22 Nov 2026, completing at **~12:47 UTC** (23:47 local; worldofsurf-88) from the Linux PC, one sealed candidate,
no rebuild, under Lex's standing go-ahead, after P1732 (Lex: "can you finish up what was partly done? also the exposure,
can you maybe add a test cvar"); worldofsurf-08 handed the cut over ("cut 0.1.59 whenever you're ready"; its P1731 rides
the next release). Page: <https://proto.bar/ftesurf>.

- Version **0.1.59** (QC build 93). Frozen QC `125fd7f0` = main at the cut (branch `release-0.1.59` in release0159-88;
  tag `v0.1.59`). 3 patch entries: P1732 (r_shadows 2 keeps instanced props, no self-shadowing, shadow_control's colour,
  a Strata map's shadow takes out only the sun; r_exposure/vbsp_exposure test cvars), P1730 (worldofsurf-08: a damaged
  replay angle no longer hangs CSQC), P1729 (worldofsurf-08: opt-in hl2_water_lod).
- Progs: qwprogs `45b97cc5`, csprogs `e01610d8` (appended to tasrevd codes.txt by the lobby deploy), menu `8fc5707c`.
- Engine **bea74fbb2** (patch-1732, carrying P1729): Windows cross-built (TLS check 0 plain-address uses); Linux built in
  the Debian 11 rootfs (BUILDINFO gates G1-G10 PASS); both stamp `git-9016-patch-1732-0-gbea74fbb2`.
- Launchers unchanged (Windows bootstrap reused from 0.1.58 via `-ReuseWindowsBootstrap`, Linux 0.1.7).
- Prepared `02da8cdcff3cf649a7210f009f0380fbaf29bb0f4a58a85b64aa1cc233683f39`; live feed `e5c08c03` (prev 0.1.58
  `a962c11f`); 1290 objects; `-MaxTotalMB 132` (stage 128.5 MB).

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.59.7z` | 79,398,284 | `691d29178dbcbfbea0aeef2bd44340e104e58a5a4fda0df5f80e3634c3ad3e6f` |
| `ftesurf-0.1.59-linux-x86_64.tar.xz` | 79,855,084 | `1c1a5cde60a31f75417b882b318b21a0fc34898b202f65c1b6496b4b53477749` |
| `WOS-Launcher-0.1.59.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.59-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS; preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects; publish
  `-VerifyFull` rc 0 (page and feed served byte for byte); release_smoke linux64 1384 / win64 1383 managed files rehashed
  from the live feed.
- Wine smoke of the Windows stage: game rc 0, both screenshots. Linux game smoke: 5/5 (engine patch-1732, eye 64 then 28).
- After the lobby swap, the released Linux client on lobby 12: engine patch-1732, pm_sourceversion 15, noclip ON/OFF with
  0 prederr, no client errors.
- Run while the owner's own (non-WoS) game was open, with his OK ("can you do it anyways"); builds niced.

## Lobbies (one 10 s warning, one restart each, 12:49:27-12:50:19Z; tools/deploy0159.sh in the root)

- The release's progs over v0.1.58's (qw 1ab03d45 / cs 0b99ceff). Engine patch-1717 049f7062 + plugin 55778b14 unchanged
  (0.1.59's engine changes are client-only). Backups `*.pre0159-20261122T124927Z`. Rollback: copy each back over a .rb
  name, mv into place, restart every ftesurf@N.
- Live after: all 12 active, patch-1717, pm_sourceversion 15, no program errors in the journal since the swap.

## Scope and limits

Automated checks only; owner check pending (lextest.md). P1732's fps gain is shown as draw batches (surf_fantasy_css
157 -> 54 and 200 -> 83 under r_shadows 2), not timed: the owner's game shared the machine. Root
`FTESurf-worktrees/release0159-88` keeps qc/dist, artifacts, inputs and stages until the next release.
