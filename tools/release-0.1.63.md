# World of Surf 0.1.63 delivery

Published 23 Nov 2026, completing at **~09:58 UTC** (worldofsurf-08) from the Linux PC, one sealed candidate, no rebuild,
at Lex's ask ("Yea push a release please" / "to lobbies and main, include all changes please"). Page:
<https://proto.bar/ftesurf>.

- Version **0.1.63** (QC build 97). Frozen QC `3b329e4b` = main at the cut (branch `release-0.1.63` in release0163-08;
  tag `v0.1.63`). Player-facing entries: P1753 (a save-lock step right after a save is predicted), P1752 (lobby saves
  append to shared-prefix spines; every lobby save keeps its run, up to 999), P1747 (record a replay as a video), P1746
  (admin map upload, F8). P1752/P1753 were already live on the lobbies since 08:22Z (deploy/p1752-lobby).
- Release-time fixes on main: PATCHNOTES gained the 0.1.62 heading over P1748-P1751 (daa57ba6) and VERSION 0.1.62
  (08f9bc72) -- both missed by 0.1.62's records, so preflight read "0.1.62 is not older than 0.1.62"; shipguard denies
  `data/vidrec_restore.txt` (P1747's MVR_RESTORE runtime file, 3b329e4b).
- Progs (release build): qwprogs `1e85d160`, csprogs `d3f29f23`.
- Engine **e000687bf** (tag patch-1747 records over P1748's 3e7ad92da: P1746/P1747 client-side, mover 16 unchanged);
  stamp `git-9044-patch-1747-0-ge000687bf` (the release labels it engine patch 1748, ENGINE.txt's patch field); Windows
  cross-build (TLS check 0 plain-address uses) and the bullseye Linux drop (gates PASS).
- Launchers unchanged (Windows bootstrap reused from 0.1.62, Linux 0.1.7).
- Prepared `e012f9d1f5120e94aef59ea724736e63e336d8bf23544a4b0b009a82667266c6`; previous feed 0.1.62 `3d0c3f0b`;
  1290 objects; `-MaxTotalMB 132` (stage 128.6 MB).

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.63.7z` | 79,426,475 | `4c64a6dc0d391388984f3b878d9fd80d728ddbc9afe69a33f5a7147bb462fb17` |
| `ftesurf-0.1.63-linux-x86_64.tar.xz` | 79,886,336 | `9c1e0d7aede4773219b83d4a096fdb624cb0caf27919b43e56350d8294c9789a` |
| `WOS-Launcher-0.1.63.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.63-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (third run, after the two record fixes above); preparation gates 1-4 PASS, Linux gates PASS;
  `-PublishPrepared -DryRun` 1290 objects; publish `-VerifyFull` rc 0 (archives round-tripped, page and signed feed byte
  for byte); release_smoke linux64 1384 / win64 1383 managed files rehashed from the live feed; live feed reads 0.1.63.
- Wine smoke of the Windows stage: game rc 0, both screenshots looked at (surf_prelude, bkz_goldbhop_gs; HUD 0.1.63).
  Linux game smoke: 4/4 PASS (engine patch-1747 stamp, eye 64 then 28), screenshot looked at.
- P1752 had four review rounds (the last found nothing); P1753 three. Before the cut, on the exact lobby progs: 13 spine
  saves byte-exact against the old whole copies, 8/8 loads resumed, 1 orphan spine swept; 300 ms step-after-save 0 u.

## Lobbies

Empty; one warning and one restart each, 10:00:40-10:01:01Z; tools/deploy0163.sh in the root.

- arm64 `fteqw-svarm64` `54421115` + `fteplug_hl2_arm64.so` `f642ceec` (e000687bf, stamp git-9044-patch-1747-0-ge000687bf;
  built and gated in /srv/nvme/agent-work/eng1747-20261123-08 -- old and new identical over the gate runs) and the
  release's qwprogs `1e85d160` / csprogs `d3f29f23` (csprogs appended to codes.txt, 182 lines), over be372f27 / b96bb483 /
  2f45684a / 6d6c5bb6; backups `*.pre0163-20261123T100006Z`. The lobby binary is also surfd's verifier (sweep.py ENGINE).
- After: 12 lobbies answering `FTE git-9044-patch-1747-0-ge000687bf`, pm_sourceversion 16; no error lines in any
  server<N>.log since the restart; the released 0.1.63 Linux client on lobby 12: 0 prederr, noclip ON/OFF.
