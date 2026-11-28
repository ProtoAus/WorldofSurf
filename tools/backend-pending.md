# Backend handoff delivered together — 10 November 2026 UTC

## 28 Nov 2026: P1870 waits for the next generation; then tasindex (worldofsurf-33)
Runtime member: surfd/surfd.py only. Serves replays kind 'tasup' (leaf tasup-<id>-<sha16>.rec, _TASLEAF_OK) from
TASUP_DIR = DATA_DIR/tasup = /srv/nvme/surfd/data/tasup (code default; SURFD_TASUP optional, NOT needed: no surfd.env
change, no new setting). /api/replay hides it for a banned owner or a current reject like a run, and adds
X-Content-Type-Options: nosniff to every replay. No schema change (replays.kind is TEXT; a new value), no reader pin.
Inert until tasindex files 'tasup' rows. Then, NOT part of the generation (no root): install surfd/tasindex.py of
39294036 (sha256 77a6d500386950ba...) at /srv/nvme/ftesurf-ops/tasindex/39294036.../ and repoint the proto user unit
ftesurf-tasindex.service's ExecStart path at it (arguments unchanged: --tasup-dir defaults to tasup/ beside --db).
Rehearsed on copies of the 28 Nov 08:35Z live surfd.db + tasup store: pass 1 updated=2 reps=2 (Rounin's
surf_sandtrap2 main tasup-2 and Proto's bonus 4 tasup-1), pass 2 nothing, --quiet silent; surfd served both byte-exact
(sha matches tasupd's). In game, the TAS-tab click on those rows plays the upload. Order matters: tasindex before
the generation would file reps the live surfd 404s. Rollback: run THIS tasindex with --withdraw first (an older
tasindex does not recognise rows with a rep), then repoint the unit at d8c4953325c9c4bc844a921eb09eed8c6e39714b, which
refiles the rows with rep 0; rejected 'tasup' rows and copies are kept on purpose (their reject keys on the id).

## 28 Nov 2026 07:42Z: lobbies on 0.1.72 + P1863 (qwprogs only; worldofsurf-62)
All 12 ftesurf@N restarted 07:42:00-02Z on qwprogs e7884e33 (0.1.72 source f3af055e + P1863 5d783c21, built with the
0.1.72 compiler), replacing e5ad4e89; csprogs unchanged bd41fc6c (codes.txt needs nothing). 0 players at the swap; boot
logs clean; heartbeats flowing. Rollback: game/ftesurf/qwprogs.dat.pre1863-20261128T074143Z; pre-swap data tar
/srv/nvme/agent-work/acland-20261128-62/lobby1863/data-pre1863-20261128T074143Z.tar (parts+resume, 3,751 entries). A
later release must carry P1863 (it is on main) so the lobbies do not regress.

## 28 Nov 2026: P1864 waits for the next generation (worldofsurf-62)
surfd/surfd.py + surfd/tournaments.py (runtime members). A sweep holding the write lock past connect()'s 5 s busy wait
no longer turns lobby writes into 500 tracebacks: heartbeat answers 503 + Retry-After at once (it repeats), /api/run waits
up to 10 s (a lobby never resends a run) and restores the normal wait after its commit, /api/tournaments/game waits up to
8 s (a 'storage' reply aborts a live match). Busy is classified by sqlite result code. Known limit (measured): 12
heartbeats x 5 s waits fill the 4 request threads during a long lock, so reads stall on parent and P1864 alike.

## 28 Nov 2026 UTC: tasrevd codes.txt gains 0.1.71's csprogs; heartbeat lock follow-up (worldofsurf-62)
0.1.71's lobby/client csprogs 6fc76828082b3747... (lobbies 26 Nov 05:38Z to 28 Nov 06:04Z) was never appended at its
rollout. worldofsurf-33 appended it at 06:09:07Z on Lex's yes (backup codes.txt.pre0171code-20261128T060907Z; 192 lines,
the old 12,415 bytes identical; verified by worldofsurf-62). Release rollouts must append their csprogs here (0.1.72 =
bd41fc6c, line 191). Follow-up: surfd's heartbeat/tournament writes use BEGIN IMMEDIATE and return 500 "database is
locked" when a sweep pass holds the write lock past their busy timeout (04:50:25Z, 06:05:24Z while 12 lobbies booted);
rare, a missed heartbeat retries, but a tournament game post could be lost: consider a retry or a longer busy timeout.

## 28 Nov 2026 UTC: generation 1857 LIVE since 05:26:24Z -- reader pins installed (worldofsurf-62)
Lex's Root install 04:59:05Z; step 6 hand-installed rcptcheck 32c88865, reccheck 651abe91, census/recsim b5890190 (REF
4a3123dd: P1613, P1855, P1856, P1859, P1860) at 04:59:32Z (.pre1857-20261128T045932Z copies); primary eef5c7e7 (manifest
d9312fa7) admitted 05:26:24Z; POSTFLIGHT PASS; token CLEAR. Ships P1857 (season-flag admin card), P1858 (collector
rotation resume), P1859 (sims.reader/tried appended by the first sweep; re-measure running). DB backup
surfd.db.bak-pre1857-20261128T044142Z. --reread-receipts marked 2,917 at 05:41Z, all re-read by 06:51Z: exactly 17
FAULT -> VALID (angles FAULT -> BLIND), the shadow's 17, nothing else (old verdicts exported to
/srv/nvme/agent-work/gen1857-20261128-62/receipts-before-reread-20261128.tsv); a full shadow predicted exactly 17
FAULT -> VALID (angles FAULT -> BLIND, P1856) and nothing else. NEXT CURRENT = primary eef5c7e7. P1856, P1857, P1858,
P1859, P1860 and the reader pins above are no longer pending. KSF still stopped.

## 28 Nov 2026: P1860 waits for the reader pins (worldofsurf-62)
tools/reccheck.py only (a reader pin change). On a numbered recording, more than 5% of in-run moves the command rule
did not join (no number, no frame of their own command, or frames out of step) keeps the angle result below tight:
BLIND, never FAULT. Fleet: 0 of 232 verdicts change; honest share median 0.67%, max 4.75% (39 numbered runs). Ships in
gen1857 with P1856/P1858/P1859.

## 28 Nov 2026: P1856 waits for the reader pins (worldofsurf-62)
tools/reccheck.py only (a reader pin change; no runtime/schema change). Remote lobby players' false angle FAULTs
(17 of 232 fleet runs) become BLIND; never OK, 0 new faults. Ship it with the reader-pin generation (gen1857 kit,
REF >= this commit) together with P1858/P1859; re-read the fleet after the swap and expect 17 FAULT -> BLIND.

## 28 Nov 2026: P1859 waits for the next generation AND the reader update (worldofsurf-62)
surfd/simcheck.py + surfd/sweep.py (runtime) and tools/census/recsim.py (READER_REVISION = 2; a reader pin change).
Schema: simcheck.ensure_schema ADDs sims.reader (INTEGER NOT NULL DEFAULT 1) and sims.tried (INTEGER NOT NULL DEFAULT 0)
on the first cron pass, exactly like P1855's yaw columns: an empty-DB CREATE puts them before `at`, the live table gets
them last -- never compare sims table text. With the installed (revisionless) recsim nothing is re-measured; once the
revision-2 recsim is pinned, ~15k unmodelled/malformed skips are re-measured once, in place, at ~110 pairs a pass
(~11 h; note "sims re-measured N (M unjudgeable)"). `sweep.py --dry-run` prints the backlog. Ship it together with
the reader pins (P1613 reccheck, P1671/P1689/P1855 recsim).

## 28 Nov 2026: P1858 waits for the next generation (worldofsurf-62)
surfd/simcheck.py only (source selection). Live, the collector's rotation starved: the cursor sat at the newest run, each
pass's wrap read judged ~650 complete runs before the oldest incomplete one and overran the 1M-step budget ("sims SQL read
limit reached" on 251 of 300 sweeps; 65 runs incomplete for 4-23 days). P1858 judges 8 run ids a read and commits the
cursor past ineligible runs when a pass stops short; on a live-DB snapshot it reaches them on pass 3. No schema change.
After the swap expect a few passes with "SQL read limit reached" while the rotation catches up, then "sims +N".

## 28 Nov 2026: P1857 admin card waits for the next generation (worldofsurf-62)
surfd/admin.py (`/admin/api/seasonflag`, SEASONFLAG_BYTES) and templates/admin_top10.html (a "Season strafe flag" card).
It reads /srv/nvme/surfd/data/seasonflag.json (override SURFD_SEASONFLAG), written daily by the proto user timer
ftesurf-seasonflag (tools/ftesurf-seasonflag.{service,timer}; release /srv/nvme/ftesurf-ops/seasonflag/<commit>/, cache and
log beside it). The timer is outside the generation (not crontab) and can run before the card is live.

## 28 Nov 2026 UTC: generation 1855 LIVE since 03:56:23Z (worldofsurf-62)
Lex's Root install 03:20:41Z; primary fc0efb6b admitted 03:56:23Z (source pin e4bf27e0, reference f33f1577, token
735b9078); POSTFLIGHT PASS (mapwatch graded after its next :23 run); P1845 badge backfill (tournament-tester x5);
sims.yaw_agree/yaw_turning added by the first sweep. NEXT CURRENT = primary fc0efb6b: any kit must advance from gen1855.
Still NOT live: the reader pins and P1856-P1859 (next generation, gen1857). KSF still stopped.
Earlier staging record:
### 27-28 Nov 2026 UTC: generation 1855 STAGED, waiting for Lex's Root install (worldofsurf-62; not live)
Kit FTESurf-private/worktrees/gen1855-20261128-62 (RUNBOOK.md), advanced from gen1837 with genkit; Pi root
/srv/nvme/agent-work/gen1855-20261128-62 (inert, both roles INITIALIZED CLOSED 19:40Z). Ships main 9ee36b2b's 13 changed
surfd members: P1838 surfd half, P1845 (mapper access + badges), site defaults 466fd394/23e2f3ae, P1850, P1855. No added
member; guard, five routes, six readers and native (df333e50 = lobby engine 7b08b0476) unchanged.
LIVE DB ALREADY CHANGED (step 2c, 19:39Z, under the sweep lock): P1845's empty `account_badges` table exists (56 tables,
user_version 26); backup surfd.db.bak-pre1855-20261127T193815Z (sha256 490d1703). gen1837's code never names it. Any other
kit advanced from gen1837 (GoldQuartz's gen1849) must re-advance from gen1855 once it is live and expect 56 tables.
P1855's sims.yaw_agree/yaw_turning arrive on the first collector sweep after the swap. The reader pins (P1613 reccheck,
P1671/P1689/P1855 recsim) are still NOT in any generation: the kit's reader publication path is disabled and untested.

## 28 Nov 2026: P1855 waits for the next generation (worldofsurf-62; not live)
surfd/admin.py, surfd/simcheck.py, surfd/sweep.py, surfd/templates/admin_run.html, surfd/web/board.js and the reader
tools/census/recsim.py (+ tools/simcheck_runtime.py package v2, which now pins heldmeta.py with the paired readers).
Schema: simcheck.ensure_schema ADDs two nullable sims columns (yaw_agree, yaw_turning) on its first cron pass; older
readers/writers keep working (store_yaw checks the columns). No backfill. The P1613 reccheck and P1671/P1689 recsim
pins are still the pending reader pins from 21 Nov; this generation should carry them together with P1855.

## 25 Nov 2026: generation 1837 LIVE — current base for the next generation (QuickPhoenix; public web performance)
Primary d1ba8efa (members-v1/93), manifest6211197c, public application REF5cbebf3c: generation 1820 plus ONLY
surfd.py, web/board.html and web/board.js. Fallback5b9ac3d9 is the exact generation 1820 runtime, CLOSED/qualified;
old primary b80a84f5 is CLOSED. Native190160f1 and all six readers unchanged; schema26/55 unchanged; no lobby restart,
new runtime members, database restore, peer reader/native changes or P1838 batch in this generation.
Private kit FTESurf-private/worktrees/gen1837-20261125-phoenix; remote primary runtime
/srv/nvme/agent-work/gen1837-20261125-phoenix/backend/primary/runtime. Lex installed the checked three-file Root guard
package at11:40Z (reload only). Initial waiting scheduler expired before any gate or execute; independently reviewed
prelaunch-only recovery preserved that failure, corrected the native runtime limit, then used the unchanged launcher:
12:44 DEFER-BUSY, 12:54 GO, one execute12:54:15, rc0/completedprimary, independent POSTFLIGHT PASS. No transaction replay.
Genkit built metadata recorded AFTER acceptance. generation.json.current remains the construction predecessor;
freshly acquire the LIVE primary for any successor—do not literal-advance or reuse this kit's phase refs/clearance.
Mapwatch and mapnew scheduled functional observations are separately pending their normal ticks, not credited by the
core postflight or unchanged-module compilation. Owner-stopped KSF remains a comment; existing producer bytes and
five canonical schedules preserved. Native/reader/backend coordination hold explicitly released after acceptance.
Board-follow/current now publishes the accepted primary's eight files with matching CSP. zoning.js is live from5cb
through the tested site-only asset publisher; signed client feed/version bytes remain unchanged (0.1.70 retained).
Live Chromium browser-cold observations: board list-ready3.48s->0.20s, player directory1.64s->0.38s; zoning~0.2s,
no demonstrated improvement there. Initial board DOM11301->862. These are individual observations, not p95 or a
cold-server/recycle claim. Public API cache expiry/background refresh observed without blocking on a fresh build.
Existing GC remains fail-closed on unreadable root-owned nginx backup directories, untouched; required generation-code
protection is deployed. See tools/p1837-claim.md for qualification, publication safety and retained failure details.

## Historical: 25 Nov 2026 05:27Z — generation 1820 (superseded by generation 1837; worldofsurf-47, Lex "can you push the new update?")
Primary b80a84f5 (members-v1, 93) = gen1745's files + at REF 281b7417: P1820's admin.py, eight admin templates, five
web/ files, ADDED templates/_admin_brand.html; mapwatch.py stays at its held live bytes (held_patch empty); fallback
47436076 = gen1745's 92 exactly; guard 4b6a9fb3 unchanged; native 190160f1 (0.1.70's lobby engine, mover 17). Root
/srv/nvme/agent-work/gen1820-20261125-47; private kit FTESurf-private/worktrees/gen1820-20261125-47 (OWNER.md, RUNBOOK.md);
genkit "built" recorded. Root install (Lex) 05:07:55Z (rotation kept p1820 + p1745, removed p1710); kit review: no
blocking (fixes applied); token review CLEAR (PIN 21dd13da, REF_SHA b426f22d, REV c6a8fdda); swap 05:24:15-05:27:19Z
(rc 0); POSTFLIGHT PASS, MAPNEW PASS (mapwatch's functional grade waits for the 06:23Z run). The board-follow timer's
05:25 run published the FALLBACK's web files mid-swap (state.json 47436076, the old board without download buttons) and
its 05:30:22 run corrected to b80a84f5 (as at gen1702): check state.json after a swap, not during it. Live: /admin/login serves the new page,
health ok/12, lobbies.json and /api/board 200. Next kit: CURRENT b80a84f5 (members-v1, 93), crontab 9ce3cfe9, native =
the lobby engine live when it is built (190160f1 today), reader pins still pending, retention keeps gen1745 + gen1820
(gen1710's root goes by the 14-day rule). main had no surfd change after 281b7417 at the swap.

## P1820 admin half -- LIVE in gen1820 (25 Nov 05:27Z; worldofsurf-47, Lex's site list)
LIVE 24 Nov UTC (game main cbefd439, engine record 0a01afc05): site 19:08Z (src/release/sitepage.ps1 into releases/0.1.68;
backups /srv/nvme/ftesurf-site/.sitepage-prev/0.1.68-20261124T190746Z), board 19:09Z (publish_board.py --commit e0905e56,
cut from gen1745's source_ref c2cbe46f; holds until the next generation, which carries the same web/ bytes from main),
reportd's reportd_reports.html + _admin_style.html + _admin_brand.html 19:09Z (HUP; backups templates/*.pre1820-20261124T190919Z).
tasupd: LIVE at cbefd439 (Lex's root upgrade, 25 Nov 00:51Z). The admin half went live with gen1820 (entry above).
surfd/admin.py (runs list SQL ~10x faster, same rows: 88 state/search/page combos identical to gen1745's on the Pi's
surfd.db.bak-pre1710, worst 2.55 s -> 0.19 s; key_for 0.55 -> 0.07 s; `reason` + `why` = explain_verdict on each row and
verdict), templates/_admin_style.html, admin*.html (site look, sitenav admin menu, tooltips), ADDED
templates/_admin_brand.html (generation.json ship_added) and surfd/test_admin_explain.py; test_admin.py,
test_verifier_counts.py changed. No schema change. reportd's copy of the three templates goes live without a generation
(AGENT_NOTES "P1820 site pages and tabs"). The board/watch web files publish ahead with publish_board.py.

## 24 Nov 2026: P1806 tasindex LIVE 18:37:22Z; tasupd cbefd439 (P1806 + 47's P1820 chrome) INSTALLED 25 Nov 00:51:44Z by Lex's root upgrade (worldofsurf-8b)
tasindex (no root, no surfd generation): /srv/nvme/ftesurf-ops/tasindex/d8c4953325c9c4bc844a921eb09eed8c6e39714b/tasindex.py
(sha256 158af723...), proto user units ftesurf-tasindex.{service,timer} (every 5 min; NOT crontab, so the generation kits'
crontab hash is unchanged), log /srv/nvme/ftesurf-ops/tasindex/tasindex.log. First pass filed 2 rows: Rounin's
surf_sandtrap2 main 48.165 (tasup-2) and Proto's bonus 4 7.830 (tasup-1); the site and /api/board TAS tab show them.
Rollback: `systemctl --user disable --now ftesurf-tasindex.timer`, then the same command with --withdraw.
tasupd upgrade (P1806 30-day sign-in, Sign out everywhere -- signs everyone out once; P1820 the site's dark look and
tabs): re-staged at cbefd439 (carries d8c49533; 47's diff is CSS/header/SITE_NAV only), source
/srv/nvme/ftesurf-ops/tasupd-src-cbefd439 (clean), proto dry run passed, test_tasupd 447 + test_tasindex 18 at that
commit; installer sha256 4f8b2769bf0f205e83acb771a4ab7c2886447d3231201bb5916e533a7e605454 (= a0cf6968's). The d8c49533
checkout was removed. Lex, on the Pi:
  sudo install -m 700 /srv/nvme/ftesurf-ops/tasupd-src-cbefd439/tools/install_tasupd.py /root/install_tasupd-cbefd439.py
  sudo python3 -I /root/install_tasupd-cbefd439.py --source /srv/nvme/ftesurf-ops/tasupd-src-cbefd439 \
      --commit cbefd4396935a3d3b3484b63d7da1db165690c31 --upgrade-from a0cf69682ea08fd2b9bdab3adc4f8468f8e734fb --apply
Check after: `curl -sI https://play.proto.bar/tasup/api/health` shows X-Tasupd-Source cbefd439...; next upgrade
--upgrade-from cbefd4396935a3d3b3484b63d7da1db165690c31.

## P1746 map upload service -- LIVE 23 Nov 07:24Z (ftesurf-cb; Lex's root install, release /opt/ftesurf-mapupd/99171e80)
Checked live: unit active, public POST /mapup/api/health 200 with X-Mapupd-Source 99171e807f56 and accounts 1, a
challenge answers, a 20 KB body to begin gets nginx's 413, GET is refused; `grant-zone-admins` gave the map role to the
2 zone admins (Proto, Markbeaton54). No upload yet. The install record as it was staged:
New isolated service (tools/mapupd.md): surfd/mapupd.py on 127.0.0.1:8096, nginx /mapup/api/ + /ftesurf/media/uploads/,
store /srv/nvme/ftesurf-ops/mapupd-state, release /opt/ftesurf-mapupd/<commit>. No surfd generation, no lobby restart.
Staged 23 Nov: source /srv/nvme/ftesurf-ops/mapupd-src-99171e80 (clean, HEAD 99171e807f5673000056a5665b7f7b7a181420ba),
dry run as proto passed; nginx predecessor 8b932846e87527431b41e6b3e765e7619f2e7615501c618a92fd2e59d35f2826. Lex, on the Pi:
  sudo install -m 700 /srv/nvme/ftesurf-ops/mapupd-src-99171e80/tools/install_mapupd.py /root/install_mapupd.py
  sudo python3 -I /root/install_mapupd.py --source /srv/nvme/ftesurf-ops/mapupd-src-99171e80 \
      --commit 99171e807f5673000056a5665b7f7b7a181420ba \
      --expected-nginx-sha256 8b932846e87527431b41e6b3e765e7619f2e7615501c618a92fd2e59d35f2826 --apply
then as proto: `python3 /opt/ftesurf-mapupd/99171e807f5673000056a5665b7f7b7a181420ba/mapupd.py --store
/srv/nvme/ftesurf-ops/mapupd-state grant-zone-admins` (Proto and Markbeaton54 hold the zone role). If nginx changed
since, re-take its sha256 and re-run the dry run first. Rollback: `systemctl disable --now ftesurf-mapupd`, put
/etc/nginx/play.proto.bar.conf.pre-mapupd-99171e807f56 back over the site file, remove
/etc/nginx/snippets/ftesurf-mapupd.conf and /etc/nginx/conf.d/ftesurf-mapupd-zones.conf, `nginx -t && systemctl reload
nginx`. Pi task root /srv/nvme/agent-work/mapupd-20261123-cb (OWNER.md).
## 24 Nov 2026 21:01Z: lobby ENGINE + plugin + progs = release 0.1.70 LIVE (worldofsurf-67) -- MOVER 17
All 12 lobbies: arm64 engine 190160f1 + hl2 plugin 4f3208f5 (9fc09ffcb patch-1799-22, P1812 mover 17; = surfd's
verifier) over the patch-1747 pair 54421115 / f642ceec; qwprogs 7dde97db / csprogs a6ec5be0 (= release 0.1.70, tag
v0.1.70 = 89e2b7a1) over 2b8bfc7f / 1dd36f2c; backups *.pre0170-20261124T205537Z; codes.txt 190. Gated in
nanopi:/srv/nvme/agent-work/eng1812-20261124-67 (delete once settled). Any future arm64 lobby engine starts from >= 9fc09ffcb.

## 24 Nov 2026 19:50Z: lobby progs = release 0.1.69 LIVE (worldofsurf-67)
All 12 lobbies: qwprogs 2b8bfc7f / csprogs 1dd36f2c (= release 0.1.69, tag v0.1.69 = 65bb87b5; rebuilt for the version),
over b442b030 / e5fb3ab9; backups *.pre0169-20261124T192817Z; codes.txt 189. Engine unchanged (patch-1747 arm64). See
tools/release-0.1.69.md. The next lobby build starts from main (v0.1.69).

## 24 Nov 2026 18:13Z: lobby progs = release 0.1.68 LIVE (worldofsurf-67)
All 12 lobbies: qwprogs b442b030 / csprogs e5fb3ab9 (= release 0.1.68, tag v0.1.68 = 6518d999; P1803 lit smoke, P1804
sun fade csprogs), over b0760514 / 33515a70; backups *.pre0168-20261124T180353Z; codes.txt 188. Engine unchanged
(patch-1747 arm64). See tools/release-0.1.68.md. The next lobby build starts from main (v0.1.68).

## 24 Nov 2026 13:40Z: lobby progs = release 0.1.67 LIVE (worldofsurf-67)
All 12 lobbies: qwprogs b0760514 / csprogs 33515a70 (= release 0.1.67, tag v0.1.67 = ba2eea35; P1772 smoke volumes,
a3's P1796-P1799 client/server QC), over 3dc34294 / d92f8394; backups *.pre0167-20261124T133754Z; codes.txt 187. Engine
unchanged (patch-1747 arm64). See tools/release-0.1.67.md. The next lobby build starts from main (v0.1.67).

## 24 Nov 2026 08:46Z: lobby progs = release 0.1.66 LIVE (worldofsurf-67)
All 12 lobbies: qwprogs 3dc34294 / csprogs d92f8394 (= release 0.1.66, tag v0.1.66 = cd272b43; P1776/P1778/P1780
csprogs), over c0c66e9f / 63f62701; backups *.pre0166-20261124T084506Z; codes.txt 186. Engine unchanged (patch-1747
arm64). See tools/release-0.1.66.md. The next lobby build starts from main (v0.1.66).

## 24 Nov 2026 04:57Z: lobby progs = release 0.1.65 LIVE (worldofsurf-67)
All 12 lobbies: qwprogs c0c66e9f / csprogs 63f62701 (= release 0.1.65, tag v0.1.65 = 3d14e91f; P1767/P1769 csprogs),
over 3cf79c3c / 1799fdf7; backups *.pre0165-20261124T045615Z; codes.txt 185. Engine unchanged (patch-1747 arm64
54421115 / plugin f642ceec). See tools/release-0.1.65.md. The next lobby build starts from main (v0.1.65).

## 24 Nov 2026 01:53Z: lobby progs = release 0.1.64 LIVE (worldofsurf-67)
All 12 lobbies: qwprogs 3cf79c3c / csprogs 1799fdf7 (= release 0.1.64, tag v0.1.64 = a36bcdef; P1762/P1764 csprogs),
over 4b6c2c15 (P1760's lobby qwprogs, 23 Nov 18:38Z) / 29439f65; backups *.pre0164-20261124T015235Z; codes.txt 184.
Engine unchanged: fteqw-svarm64 54421115 / fteplug_hl2_arm64.so f642ceec (patch-1747); 0.1.64's engine changes are
client-side, so the next surfd kit can keep pinning patch-1747. See tools/release-0.1.64.md. The next lobby build starts
from main (v0.1.64).

## 23 Nov 2026 11:44Z: lobby progs = v0.1.63 + P1754-P1757 LIVE (worldofsurf-08)
All 12 lobbies: qwprogs 6b48b32b / csprogs 29439f65 (deploy/p1757-lobby efb40572; its 14 src files byte-identical to
main 5d2b1d48), over 0.1.63's 1e85d160 / d3f29f23; backups *.pre1757-20261123T114331Z; codes.txt 183; engine
unchanged; script coastperf-20261122-08/deploy1757.sh. New string stat STAT_FS_WOPCLK (213). After: 12 active, no
error lines. Lex's dev install has the same qw/cs (menu stays 0.1.63's). The released-client check on a lobby waits
(Lex was playing when it landed).

## 23 Nov 2026 10:01Z: lobbies on 0.1.63 (engine e000687bf + its progs) LIVE (worldofsurf-08)
All 12 lobbies: fteqw-svarm64 54421115 / fteplug_hl2_arm64.so f642ceec (patch-1747 records, mover 16 unchanged) and
qwprogs 1e85d160 / csprogs d3f29f23 (= release 0.1.63), over be372f27 / b96bb483 / 2f45684a / 6d6c5bb6; backups
*.pre0163-20261123T100006Z; codes.txt 182. See tools/release-0.1.63.md. The next surfd kit should pin this engine.

## 23 Nov 2026 08:22Z: lobby progs = v0.1.62 + P1750 fix + P1752 + P1753 LIVE (worldofsurf-08)
All 12 lobbies: qwprogs 2f45684a / csprogs 6d6c5bb6 (deploy/p1752-lobby; the four touched files byte-identical to
main's P1753 tip), over fd61f951 / 65de9276; backups *.pre1752-20261123T082144Z; codes.txt 181; engine be372f27
unchanged; script coastperf-20261122-08/deploy1752.sh. Lobby saves now append to spines (data/saves/<map>/@<guid>/
spines/) and every timed lobby save keeps its run (999); a step right after a save is predicted. After: 12 active,
patch-1748 / pm 16, no errors in server<N>.log; released 0.1.62 client on lobby 12: 0 prederr, noclip ON/OFF.
ROLLBACK LOSES SAVED RUNS: older progs cannot load a spine save (it loads as "run lost").

## 23 Nov 2026 06:58Z: lobby qwprogs = v0.1.62 + P1750 review fix LIVE (worldofsurf-08)
All 12 lobbies: qwprogs fd61f951 (deploy/p1752-lobby cd5c6cde = v0.1.62 + main b8d696da; the "position only" line no
longer follows rewind resumes, replay points, synced saves or gifts), over 0.1.62's d2bd004d; csprogs 65de9276, engine
be372f27 and plugin unchanged; backups *.pre1750r-20261123T065737Z; script coastperf-20261122-08/deploy1750r.sh.
After: 12 active, patch-1748 / pm_sourceversion 16, no errors in server<N>.log since the restart. The next lobby build
must start from main (or include b8d696da).

## 23 Nov 2026 05:39Z: lobby engine patch-1748 (mover 16) + 0.1.62 progs LIVE (worldofsurf-08)
All 12 lobbies: fteqw-svarm64 be372f27 + fteplug_hl2_arm64.so b96bb483 (3e7ad92da, git-9039-patch-1748-0-g3e7ad92da) and
0.1.62's progs (qw d2bd004d / cs 65de9276); backups *.pre0162-20261123T053830Z; gate in
/srv/nvme/agent-work/eng1748-20261123-08. The lobby binary is surfd's verifier: THE NEXT GENERATION'S KIT MUST PIN
be372f27 (gen1745 recorded 049f7062; 0.1.61's b94f7365 was never pinned either). Record: tools/release-0.1.62.md.

## 23 Nov 2026 02:27Z: gen1745 LIVE -- the base for the NEXT generation (ftesurf-e4, Lex "can you please deploy the new UA we have please.")
Primary 570cc70a (members-v1, 92) = gen1710's files + at REF c2cbe46f: ksfimport.py (P1734 + P1745), surfd.py (P1737's
report_points), mapnew.py, momgrab.py, steam.py, momfetch.py (P1745), and mapwatch.py = its held live bytes + the one UA
line (generation.json `held_patch`); fallback 71413555 = gen1710's 92 exactly; guard 4b6a9fb3 unchanged. Root
/srv/nvme/agent-work/gen1745-20261123-e4; private kit FTESurf-private/worktrees/gen1745-20261123-e4 (OWNER.md has every
step); genkit "built" recorded. Root install (Lex) 22 Nov 23:16:16Z; swap 02:24:15-02:27:19Z; POSTFLIGHT PASS and
mapnew's functional PASS (mapwatch's waits for the 06:23Z run); live UA lines WOS only; the board follows 570cc70a
since 02:30Z. The first window (23:44Z) refused CANNOT-MEASURE on a desktop file-manager SFTP mount of the Pi, whose
sftp-server processes the gate cannot read: `pgrep -c -x sftp-server` on the Pi must print 0 before a window. KSF stays
stopped (crontab 9ce3cfe9 keeps the commented row). A supervised probe as `WOS/0.1 mapnew` after the swap still got
403 `proof_required`, and mapnew asks KSF only within 7 h of a mapwatch reading of both lists (mapwatch.py
`len(read) == 2`; catalogue.json `at` is 11 Nov 06:23Z). Next kit: CURRENT 570cc70a (members-v1, 92), crontab 9ce3cfe9,
native b94f7365 (the 0.1.61 lobby ENGINE entry below; gen1745 pinned 049f7062); reader pins still pending (READERS
empty); retention keeps gen1710 + gen1745 (gen1702's root goes by the 14-day rule).

## P1745 WOS User-Agents -- LIVE in gen1745 23 Nov 02:27Z (ftesurf-e4)
Every fetcher User-Agent is the WOS label with no URL (Lex 23 Nov). Ships as CHANGED: surfd/ksfimport.py (with P1734),
mapnew.py (derives `WOS/0.1 mapnew` from mapwatch's UA), momgrab.py, steam.py and tools/momfetch.py (a live member).
mapwatch.py stays held at its live bytes (the P1600 rule below) except its one UA line: the gen1745 kit's
generation.json `held_patch` refuses unless REF's change to it is exactly that line, and applies the same line to the
live bytes. tasupd.py's `WOS-tasupd` stays out of generations: the TAS upload service took it and steam.py's
label in its own upgrade to 45aab35b, 23 Nov (tools/tas-uploads.md). Check after: `grep -n '^UA ='
<primary>/runtime/*.py`.

## KSF STOPPED 22 Nov 2026 16:29Z UTC (23 Nov local; Lex, worldofsurf-2f) -- crontab changed outside a generation
proto's crontab: the `13,43` ksfimport row is commented out (crontab 628583d6 -> 414b8566; the next kit's freshness
check must re-acquire it). /srv/nvme/surfd/data/ksf/.refused is an open-ended park (until 2036), so the mapwatch and
mapnew routes skip KSF as well. Backups and resume steps: /srv/nvme/agent-work/ksfstop-20261123-2f (OWNER.md, RETAIN).

## P1734 KSF demo budget -- LIVE in gen1745 23 Nov 02:27Z, inert while KSF is stopped (worldofsurf-2f)
surfd/ksfimport.py only (ships as CHANGED; nothing added, no schema, no cron/env change). The `13,43` row's `--max 8`
then splits 4 board requests (walks 1, unblock 1, refresh 1, sweep >= 1) + 4 demo downloads a tick instead of 8 + 0.
Inert while KSF is stopped (above) and while ksf.surf refuses us (403 since 11 Nov). Since gen1710's REF 8bbc3700 the
only other surfd/ changes on main are tasupd files (excluded from generations). Check after a resume: the first
unparked tick's ksfwatch.log reads `KSF demos: N request(s)` with N up to 4 and `watch: <=4 request(s)`.

## 21 Nov 2026 23:57Z: gen1710 LIVE -- the base for the NEXT generation (worldofsurf-2c, Lex "pre-pare an update? do it if you need.")
Primary e4dbc744 (members-v1, 92) = gen1702's files + P1710's surfd half at REF 8bbc3700 (admin.py, recplot.py, surfd.py,
templates/admin_run.html, templates/admin_top10.html, web/board.js); fallback 6297635d = gen1702's 92 exactly; guard
4b6a9fb3 unchanged. Root /srv/nvme/agent-work/gen1710-20261122-2c; private kit FTESurf-private/worktrees/gen1710-20261122-2c
(OWNER.md has every step); genkit generation.json "built" recorded. runs/replays.oldgame added by hand 22:51Z (backup
surfd.db.bak-pre1710-20261121T225001Z). Root install (Lex) 23:36:57Z; swap 23:54:15-23:57:19Z; POSTFLIGHT PASS. P1710
backfill: 4 bound runs since the lobby progs, none with `oldgame 1` (no-op). Next kit: CURRENT e4dbc744 (members-v1, 92),
native 59bc2e04 (lobby patch-1709); retention now keeps gen1702 + gen1710 (gen1674 still named by gen1702's code; the 47
roots only gen1674's untrimmed proposal named go by the 14-day rule -- Lex, 22 Nov: "Let retention remove them").

## 21 Nov 2026 11:27Z: gen1702 LIVE -- the base for the NEXT generation (worldofsurf-47, Lex "Release + lobbies now")
Primary 74bb6404 (members-v1, 92 members) = gen1674's files + REF 4fa70237's surfd changes (admin.py, hidupload.py,
recplot.py, surfd.py, sweep.py, templates/admin{,_accounts,_maps,_run,_runs}.html, web/board.{css,html,js}, added
templates/admin_top10.html); fallback 759e3931 = gen1674's 91. Root /srv/nvme/agent-work/gen1702-20261121-a03; private kit
FTESurf-private/worktrees/gen1702-20261121-a03 (OWNER.md has every step); generation.json "built" recorded for advance.py.
Carries P1694 surfd half, P1697, P1699 (OFF), P1700, P1703, P1704. runs.pad/replays.pad added by hand 10:07Z (backup
surfd.db.bak-pre1702-20261121T100658Z). Root: trimmed drop-in 4d92f72e (139 lines, 2 preflights) -> each surfd start
took ~2 s (was ~280 s), so the next kit may lower START_TIMEOUT. POSTFLIGHT PASS (mapwatch graded after 12:23Z).
Readers stay pinned (P1671 recsim, P1694 reccheck NOT in SURFD_TOOLS yet). The static board follows 74bb6404 (11:30Z).
Native for the next kit: lobby engine patch-1705 fteqw-svarm64 0ac1d567efeedb534dede8088cc6e60551df00c71e193d03b0c8174ceb2d4bb1
(swapped 12:49Z; patch-1704 820137cd 11:28Z; gen1702 checked 1753f9d4 only inside its transition, not at surfd start).
Ordering note: 0.1.55 (engine 1694) reached the lobbies at 10:03Z, before this generation; one run was posted in
10:03-11:27Z, so at most that run lacks a controller tag (no backfill).

## 21 Nov 2026 01:36Z: gen1674 (P1674) LIVE -- the base for the NEXT generation (tools/p1672-delivery.md)
Primary cd1965f1 = gen1650's files + party_lobbies/surfd/tournament_pool/tournament_rules at main 9ccec5dc (pool keeps
one build per map family; tournament standings on GET /api/tournament-lobbies?stats=1). The next generation takes
CURRENT = cd1965f1 (root /srv/nvme/agent-work/gen1674-20261121-e3; kit FTESurf-private/worktrees/gen1674-20261121-e3),
pins native fteqw-svarm64 1753f9d4 (lobby engine patch-1683, swapped 01:38Z), and keeps the consumer's 900 s
`systemctl start` (its drop-in will have 18 ExecStartPre blocks, ~280 s; or the owner prunes retired blocks).

## P1727 own long replays -- lobby csprogs LIVE 22 Nov 09:47Z (worldofsurf-08)
LIVE: all 12 lobbies on qw e0fa1b80 (unchanged) / cs f1c57d33 = tag v0.1.57 + P1727's cl_watch.qc (aa43a77a, 39ee29a0,
b75b37fc; branch deploy/p1727-lobby 7c908dc0; 0.1.57's fteqcc in FTESurf-worktrees/release0157-88, which rebuilds the
live e0fa1b80 / fb427ec1 exactly). All 12 were empty; one restart each; backups *.pre1727-20261122T094655Z; codes.txt
175; engine patch-1717 untouched. Checked: 12 active, 12 answer status, 0 SIGSEGV/Host_Error/PR_ExecuteProgram/runaway
since each lobby's last "Loaded progs". Next lobby progs build: start from deploy/p1727-lobby, or a release carrying P1727.

## 0.1.61 lobby ENGINE -- LIVE 23 Nov 02:32Z (worldofsurf-08; record tools/release-0.1.61.md)
LIVE: all 12 lobbies on arm64 fteqw-svarm64 b94f7365 + fteplug_hl2_arm64.so b9d76a46 (engine 6e3a1d3f0 = 0.1.61's,
git-9033-patch-1739-0-g6e3a1d3f0) over patch-1717 (049f7062 / 55778b14); backups *.pre0161e-20261123T022906Z; gated
old = new on the Pi. It is surfd's verifier (sweep.py ENGINE): the NEXT generation's kit must pin b94f7365 (gen1745,
live since 02:27Z, pinned 049f7062 before this swap).

## 0.1.61 lobby half -- LIVE 23 Nov 00:35Z (worldofsurf-08; record tools/release-0.1.61.md)
LIVE: all 12 lobbies on the release's progs (tag v0.1.61 = 97d76ecc; qw bd9ec782 / cs 59b63f13 = P1743's, already in
codes.txt) over P1743's (qw e6b34850). Backups *.pre0161-20261123T003429Z. Engine still patch-1717 049f7062: the swap to
6e3a1d3f0 (arm64 build + gate on the Pi) waits for ftesurf-e4's gen1745 postflight, which pins that native as the
verifier. Any later lobby build: base v0.1.61 or main.

## P1743 lobby half -- LIVE 22 Nov 19:08Z (worldofsurf-08, Lex's standing go-ahead; recipe worldofsurf-88's deploy0160.sh)
LIVE: all 12 lobbies on v0.1.60 + P1743 (deploy/p1743-lobby 7e6ad049 = v0.1.60 71155428 + cherry-pick of 5f28f6c8),
built with the release's own fteqcc (release0160-88/engine; 0 warnings, qcframes clean): qw e6b34850 / cs 59b63f13
(byte-identical to the rig-tested build), over v0.1.60's 033412f1 / 186e76bb; codes.txt appended (.pre1743lobby-*);
backups *.pre1743-20261122T184659Z. One player on lobby 4 for the whole 20 min wait: 60 s + 10 s notices, then one
restart each 19:08:38-19:09:00Z. After: all 12 active, patch-1717, pm_sourceversion 15; journal since the swap has no
program errors; the released 0.1.60 Linux client on lobby 12 (p1706arm.py rel --sections live) downloaded cs 59b63f13,
0 prederr, noclip ON/OFF. Script + logs: FTESurf-worktrees/coastperf-20261122-08 (deploy1743.sh, artifacts/).
Engine and plugin unchanged. The next lobby build's base must include P1743 (main has it since 0710a595).

## 0.1.60 lobby half -- LIVE 22 Nov 18:24Z (worldofsurf-88; record tools/release-0.1.60.md)
LIVE: all 12 lobbies on the release's progs (tag v0.1.60 = 71155428; qw 033412f1 / cs 186e76bb, codes.txt appended) over
v0.1.59's, with P1737's data/reportpoints/seed.txt (145 reports, 7 accounts; the lobbies append p<port>.txt there).
Engine patch-1717 049f7062 + plugin 55778b14 unchanged. Backups *.pre0160-20261122T182356Z. Next lobby progs build: start
from v0.1.60. surfd's report_points (P1737) LIVE in gen1745 (23 Nov 02:27Z).

## 0.1.59 lobby half -- LIVE 22 Nov 12:50Z (worldofsurf-88; record tools/release-0.1.59.md)
LIVE: all 12 lobbies on the release's progs (tag v0.1.59 = 125fd7f0; qw 45b97cc5 / cs e01610d8, codes.txt appended) over
v0.1.58's. Engine patch-1717 049f7062 + plugin 55778b14 unchanged. Backups *.pre0159-20261122T124927Z. Next lobby progs
build: start from v0.1.59.

## 0.1.58 lobby half -- LIVE 22 Nov 10:10Z (worldofsurf-88; record tools/release-0.1.58.md)
LIVE: all 12 lobbies on the release's progs (tag v0.1.58 = 3d6624f8; qw 1ab03d45 / cs 0b99ceff, codes.txt appended) over
v0.1.57 + P1727 (deploy/p1727-lobby, now obsolete). Engine patch-1717 049f7062 + plugin 55778b14 unchanged. Backups
*.pre0158-20261122T100921Z. Next lobby progs build: start from v0.1.58.

## 0.1.57 lobby half -- LIVE 22 Nov 03:47Z (worldofsurf-88; record tools/release-0.1.57.md)
LIVE: all 12 lobbies on engine patch-1717 (fteqw-svarm64 049f7062 + fteplug_hl2_arm64 55778b14, engine main e4f48ac0e,
stamp git-9001-patch-1717-0-ge4f48ac0e; also the surfd verifier) and the release's qw e0fa1b80 / cs fb427ec1 (tag
v0.1.57 = 701c4e07). No cfg change. Backups *.pre0157-20261122T034612Z; codes.txt appended. Mover 15 (P1713) is live.
Next lobby progs build: start from v0.1.57.

## P1715 run lines native -- lobby csprogs LIVE 22 Nov 01:52Z (worldofsurf-08)
LIVE: all 12 lobbies on qw 8bbf41ba (unchanged) / cs 20be3cff = tag v0.1.56 + 2aa72543 + 7d97c6b8 + P1715's cl_lines.qc
(branch deploy/p1715-lobby 12f060dc; 0.1.56's fteqcc in FTESurf-worktrees/release0156-88, which rebuilds the live
8bbf41ba / 36fbd89c exactly); backups *.pre1715-20261122T015158Z; codes.txt 173; engine patch-1709 59bc2e04 untouched.
Checked: 12 active, 12 in lobbies.json, 0 SIGSEGV/Host_Error/PR_ExecuteProgram since each lobby's last "Loaded progs".
SUPERSEDED 22 Nov 03:47Z by 0.1.57 (section above): deploy/p1715-lobby is obsolete.

## P1710 "unchecked" mark -- LIVE end to end 21 Nov 23:57Z (lobby side 21:23Z; surfd half in gen1710) (worldofsurf-2c)
LIVE: all 12 lobbies on qw 8bbf41ba / cs 36fbd89c = tag v0.1.56 (a0c594f3) + 2aa72543 + 7d97c6b8 only (built with 0.1.56's
fteqcc, which rebuilds the tag's bb26775e / b5dc2419 exactly; NOT main, so worldofsurf-5a's later sv_tasautosurf.qc
is not on the lobbies); backups *.pre1710-20261121T212240Z; codes.txt 172; engine patch-1709 untouched. From now on a
finished run from a too-old game writes `oldgame 1` and posts `oldgame=1` (the live surfd ignores the field).
Lex, 22 Nov: no record removed; a run that could not be verified stays up, marked. Files: surfd/surfd.py
(runs_oldgame: runs.oldgame / replays.oldgame INTEGER NOT NULL DEFAULT 0, no schema bump; intake `oldgame=1`; the
finish's `oldgame 1` raises a lower post; replay upsert/merge; restand; board rows and the maps WR), recplot.py,
admin.py (Top 10 query), templates/admin_run.html, admin_top10.html, web/board.js; test surfd/test_oldgame.py.
Generation: a HAND ALTER before staging exactly like pad's (an oldgame_columns.remote.py beside pad_columns.remote.py,
the schema_rehearsal case, a db_oldgame_columns reference check), else the primary alters in its CLOSED phase and
holds. After the swap: the one-off backfill (BACKLOG P1710). Before it: the lobby progs post `oldgame=1` (ignored) and
write the record; board.js shows nothing until surfd sends `oldgame`.

## P1704 views over HTTPS -- LIVE 21 Nov 11:28Z (all three steps; worldofsurf-47)
DONE: 1 in gen1702; 2 nginx --view-only 10:11Z (surfd.conf 91769a88, ratelimit f05ef5db; empty POST -> 413); 3 lobby
engine patch-1704 (820137cd / plugin 04933baf, agent-work eng1704-20261121-47, gate identical) swapped 11:28:26Z with
`set sv_recupload_https 1` in lobby_local.cfg (backup .pre1704-20261121T112821Z); rcon reads 1 on all 12. STILL TO
SEE: the first `stored view for <map>/<runid>` in surfd.log from a 0.1.55 client. Steps as written:
1. surfd/hidupload.py: POST /api/view (`FTESURF-VIEW 1`, exactly the receipt's signed view, finished runs,
   min(4 MiB, 256 KiB + 4 KiB/tick), 30/min, statement names the receipt's server; a refused mismatch leaves
   <map>/<runid>.viewrefused). Check: surfd/test_hidupload.py (29).
2. nginx: `sudo sh surfd/setup_public.sh --view-only BACKUP_DIR SNIPPET_SHA256 ZONES_SHA256` adds `location =
   /api/view` and its three zones (surfdview, surfdviewip, surfdviewglobal) the way --hid-only added the journal's.
   Check: surfd/test_hid_proxy_install.py (10). Then `curl -X POST` an empty body to /api/view: 413 from surfd.
3. Then the lobby engine at engine >= the P1704 commit; then add `set sv_recupload_https 1` to the Pi-only
   cfg/lobby_local.cfg (exec'd last, run.sh) and rcon it to the running lobbies -- not the repo lobby.cfg, which ships
   0 and is exec'd by ~14 test cfgs whose clients would then post to the live collector. Before 1-2 it would send new clients' views to a route that
   does not exist. ORDER FOR THE CLIENT: release a P1704 client only AFTER step 1 is live -- it retries 503s, and
   today's collector answers 503 to every community server's journal (no receipt), so each would be re-sent up to six
   times, up to 64 MiB each, holding the lobby's next upload behind it. Old clients are unaffected by order. ROLLBACK: before taking surfd or
   nginx back past P1704, rcon `sv_recupload_https 0` on every running lobby AND remove the line from lobby_local.cfg
   (every lobby restart runs the file; clients retry a 404 for ~36 minutes, then drop the view). After enabling, check the
   surfd log shows `stored view for <map>/<runid>` for a real run. A wrong evidence root answers 503 while it is
   empty or unreadable, but a wrong POPULATED root answers 410 to every run, and three 410s cut that lobby off for
   the rest of each player's session: check the log right after enabling.
   surfd/sweep.py reads <runid>.viewrefused (no .view beside it) as the digest FAULT the netchan route gave. install_board_endpoint.sh writes the view zones too (surfd.nginx uses them).
   The collector now answers a missing receipt 410 on /api/hid too (it was 503): final, so clients do not re-send.

## P1703 journal in online play -- surfd part LIVE in gen1702 (21 Nov 11:27Z); SURFD_NOEV_JOURNAL_SINCE unset (owner)
surfd/surfd.py: SURFD_NOEV_JOURNAL_SINCE (epoch seconds; unset = a missing Windows journal never counts toward P1699's
mark). Set it to the release time of the build whose menu asks for terms 10. Check: surfd/test_noev.py.

## gen1702 kit (session a03de808, 21 Nov) -- RAN 21 Nov 11:24Z (worldofsurf-47); see the top entry
Private kit FTESurf-private/worktrees/gen1702-20261121-a03 (RUNBOOK.md), made with the one maintained tool
FTESurf-private/genkit/advance.py. It resolves both blockers below (ships the members-v1 guard and
templates/admin_top10.html, excludes tasupd*.py), adds hand step 2c for P1694's runs.pad/replays.pad (as gen1603 did
plat), installs a TRIMMED drop-in (1303 -> 139 lines, 17 -> 2 preflights) and gives the owner installer keep-two
rotation. Its step 4 requires the deployed tools/pi_retention.py to keep what the newest two generations' code names.
Dry build at main 4caa1ad7 passes every bank; two independent reviews + a fix round. Waits for Lex's go.

## BLOCKERS for a generation at current main -- RESOLVED by gen1702 (kept for the reasoning)
1. surfd/tasupd.py + tasupd_wsgi.py (P1640/P1696/P1700) are a separate service (tools/install_tasupd.py), not surfd
   runtime, but sit in surfd/: the kit's build_candidate.py asserts "REF adds modules outside the 91-member runtime".
   The kit must exclude tasupd*.py (they never ship in a generation).
2. P1697's admin.py renders templates/admin_top10.html (admin.py:1856), a file outside tour91-v1's 91 members:
   build_candidate classes it as config and does NOT ship it, so /admin/top10 would raise TemplateNotFound.
   RESOLVED IN THE GUARD (P1702, three review rounds): tools/surfd_transition_guard.py profile `members-v1` takes the
   manifest's own member list (tools/surfd-transition-guard.md). The next generation is therefore a GUARD-CHANGING
   one (guard != live 32af9ea2): its kit must ship the new guard, write `"runtime_profile":"members-v1"` manifests,
   add templates/admin_top10.html, and keep excluding surfd/tasupd*.py (P1702 kit work).
Also: the guard re-hashes all 91 members at every `launch` (surfd_transition_guard.py verify_hashes), so a member
edited in place in a live generation stops the next surfd start. Never hand-edit a generation's files.

## P1700 board menu link -- LIVE in gen1702 (21 Nov 11:27Z)
- surfd/web/board.html: one `<a href="https://play.proto.bar/tasup/">TAS uploads</a>` after Anti-Cheat in the site
  nav (the static pages and tasupd carry it already), and a "TAS uploads for this map" button under each map's title,
  which board.js showMap points at /tasup/board?map=<map>[&track=<n> for a whole course]. Markup and two lines of
  board.js; no surfd code or schema change. Lex (21 Nov) asked for both on the Players and Leaderboard tabs.

## P1699 "no evidence" mark -- LIVE in gen1702, switched OFF (SURFD_NOEV unset; owner turns it on)
surfd/surfd.py (noev_reasons, board_rows' `noev`), web/board.js + board.css; the lobby QC (cl_online/cl_scores) shows
it once the JSON carries it. Leave SURFD_NOEV unset until top-10 evidence uploads are reliable (21 Nov, live db: of
239 WOS main/bonus rows from 14 days, 33 had no receipt, 167 no view, 188 Windows rows no journal; 13 complete).
Check: surfd/test_noev.py; live, /api/board rows carry no `noev` while the switch is off.

## P1697 top-10 review page -- LIVE in gen1702 (21 Nov 11:27Z; /admin/top10 behind login)
surfd/admin.py (list_top10, rec_startlag, /admin/top10, /admin/api/top10), surfd/recplot.py (the `startlag` record into
the admin cert), templates/admin_top10.html (new), admin_run.html (start lag row), the "Top 10" nav link in admin.html,
admin_runs.html, admin_run.html, admin_maps.html, admin_accounts.html and reportd_reports.html. Read-only: no schema,
no board or verdict change. Check: surfd/test_admin.py (section 9t); live, /admin/top10 lists rows after login.

## P1694 controller tag -- surfd half LIVE in gen1702 (11:27Z; columns 10:07Z); reccheck pin and sv_rank_padcount pending
Game main 9841756b. Files: surfd/surfd.py (`runs_pad`: `ALTER TABLE runs|replays ADD COLUMN pad INTEGER NOT NULL
DEFAULT 0`, idempotent, no schema bump; post `pad=1` and the finish record `pad 1` raise it like `plat`; board and
maps JSON `pad: 1`), surfd/recplot.py, surfd/web/board.js + board.css, surfd/templates/admin_run.html; SURFD_TOOLS
tools/reccheck.py (the `pad` record and the `padcount` verdict: notes only on an older copy). Order: this generation
before the release that carries engine 1694 (an older surfd drops `pad=1` and there is no backfill); the lobby QC
(9841756b or later) may go before or after it. Check: surfd/test_pad.py before; live, `PRAGMA table_info(runs)` and
`(replays)` list `pad`. After the release: sv_rank_padcount 1 in lobby.cfg (unranks engines that send no count).

## P1671 pending: simcheck reads current (REC 14) recordings -- NEXT generation (queued 21 Nov, worldofsurf-6f)
- Pin tools/census/recsim.py at or after the P1671 commit in SURFD_TOOLS. Effect: the stored, never-acted-on
  similarity scores start covering lobby runs from 10 Nov on (REC 14); no player-visible change. The surfd similarity
  and admin tests pass with it on the Pi (scratch run 21 Nov). Expect more same-player near-1.0 pairs (BACKLOG P1671).
- P1689 rides the same pin (shared-runid pairs skipped by the census; yaw_agreement). For simcheck to STORE the yaw
  figure its projection must allow the key first (surfd change, not written yet).

## P1659 follow-up pending: lobbies show their movement style (20 Nov 2026, worldofsurf-4a)
Lex: "is it possible for the Lobbys to state their movement style (Surf/Bhop/AG250) with the map they are playing? and have
an ability to swap per map?" Since P1659 the style follows the map on any server (a BSP-30 map runs sv_goldsrcprofile,
default ag-250; the next Source map its own movement), and every server publishes `*movementprofile` (empty = default).
Not built: the directory field. Needs, in one change: sv_lobby.qc's heartbeat body (`&style=` from serverkey
*movementprofile, empty -> the mode from `gamemode`), surfd heartbeat (`clean_text(request.form.get("style"))`, a
column, the lobby list JSON), and the menu's lobby tile (m_lobby.qc / m_home.qc: "AG 250" beside the map). Lobbies
host no GoldSrc map today (the packages are not on the NanoPi and the lobby engine predates P1656), so this waits for
GoldSrc lobbies. Tournament lobbies (tournament_enable) never switch (P1659 skips them; worldofsurf-ed).

## 20 Nov 2026 06:05Z: gen1635 (P1634 + P1639) LIVE, tournaments ON 06:11Z (tools/p1639-delivery.md)
Primary ef0d1c7c = the previous live code with surfd.py + P1634's 36 lines and four added tournament modules (game
448c6832). surfd.py carries NOTHING else from main: P1615 and P1622 below are still pending for the next generation.
A surfd stop/start under the guarded drop-in takes about 4 minutes (ExecStartPre checks).

## P1623 host tooling ready (19 November 2026)

PowerShell7.7 now works on the Linux workstation; it is not required on the Pi. Native QC NoDeploy and the
actual read-only SSH transport pass. Prior missing-shell/general-sudo probes were not a complete deployment
eligibility test. Current per-command grants, exact packet/caller binding and owner-authenticated Root steps
remain distinct. This tooling task did not promote any generation, catalogue or progs. The legacy helper's
Linux WorkRoot support is not a route around sealed-generation controls. Details: `p1623-linux-deploy.md`.

## P1622 pending: course-aware Story catalogue (19 November 2026)

- Include current `surfd.py`'s opt-in `course zones` Story parser and effective-bonus-zone gate in the next guarded
  backend generation. No schema/native/recording change. Missing/malformed/unreadable effective zones fail closed;
  previously earned credit is independent of playability, and normal Story TTL refresh notices later zone edits.
- Only AFTER that generation passes its existing fleet/backend gates, validate/promote `surfd/story.txt` with
  `tools/story_push.py` and its current live-hash compare-and-swap; the old parser does not know `course zones`.
  Do not directly scp the catalogue/code into the live sealed generation or bypass generation/fence guards.
- Catalogue: 73 occupied ordinary Story levels, 71 real G4/G2 target pairs, all bronze finishes; eight requested
  Story additions (autumn_fix exact KSF identity), autosave/gary_barlow and Nightingale B4/B5 Event additions.
  The two Nightingale bonuses stay unavailable until Lex publishes their actual zones; finish-only, no invented
  times. Audit/provenance: `tools/story-catalogue-audit.md`, `tools/story-groups.json`.
- P1619–P1621 QC UI/chat/Splits changes are independent of this backend promotion. Local verification and actual
  install/deployment boundaries are recorded in `tools/p1619-1622-delivery.md`; no public-fleet deployment was
  performed by this task.

The requested P1447/P1448 entries were activated together in the accepted primary
backend, with the corresponding QC on all12 NanoPi lobbies. Public frontend assets
and a real single-leg Fetch were verified. See the
[dated delivery and rollback provenance](p1447-p1448-delivery.md).

Both local Windows DAT/LNO copies were promoted and hash-verified03:20:55 UTC
10Nov after the peer fixture window opened. In-game download/rendering and human
acceptance remain pending; native smoke was not launched through low-memory or
renewed-fixture admission blockers. The activated
backend entries have been removed from this queue, not relabelled as pending.
Do not redeploy a healthy backend merely to refresh this handoff.

## P1615 segment count on segmented rows -- NEXT generation (queued 19 Nov, worldofsurf-15)
Runtime surfd.py (rec_segments / row_segments, board_rows adds `segs`), web/board.js, web/board.css at game main;
surfd/test_segs.py beside them (14 checks pass on the Pi, Flask 2.2.2). No schema object, no cron, no reader change.
The lobby csprogs that shows it in game is independent (an older surfd just sends no `segs`). Check after: a
segmented board's /api/board rows carry `segs` (surf_joutsenlaulu, Proto: 56) and a clean board's bytes are unchanged.
Rides with P1604's reader pin (reccheck.py 059246f0..., below); P1613's reader is ready (merged 21 Nov; see below).

## P1613 reader -- READY for the NEXT generation (merged to main 21 Nov, worldofsurf-6f)
Main's tools/reccheck.py now carries the command rule (branch p1613-cseq's reader, three review rounds on 19 Nov;
its recorder has been on the lobbies since 20 Nov). Real-data condition met 21 Nov: 5 runs, three players (3 local
pairs, 4 lobby evidence pairs, two runs in both), all judged, 0.00% on no drawn path, worst 0.00 deg (tools/p1613-fleet.md). A sidecar
with more than 1% of at least 100 joined moves on no drawn path FAULTs ("the sidecar does not show what this
recording sent"). Pin tools/reccheck.py (+ tools/rcptcheck.py) at game main with the next generation. Check after:
a recent evidence pair (e.g. surf_happyhands 20261120-140615-0-p27590) reads `angle_cmd ... 0.00% on no drawn
path` under the pinned reccheck -v, and the sweep's fault rate is unchanged.

## P1603 Linux runs rank, marked `plat` -- DONE 18 Nov 07:24Z (all three steps live)
Steps 1-2 rode gen1603 and the P1604 lobby progs. Step 2's check, Lex's Linux run bhop_2hrs 0:17.520 (runid
20261118-071933-0-p27610, lobby 27610): .rec `plat 1` in the header and after `prof platform`; community board
row `"plat":1`; reccheck no faults (sweep 0.00%). The scoreboard's sky blue is Lex's to see. Step 3: lobby.cfg
line 217 set to 1 on the Pi (backup cfg/lobby/lobby.cfg.pre-ranklinux-20261118T072335Z; the file equals main's),
then rcon on all 12 lobbies, each read back 1. Rollback as below; the rcon step reads surfd.env's password in a
loopback script (rcon.Rcon("127.0.0.1", port, pw).execute(["set", "sv_rank_linux", "0"]), then read it back).
RULE: never run a surfd without `runs_plat` while any lobby has `sv_rank_linux 1` -- it drops `plat`, so
Linux runs rank unmarked, and its upserts leave stale marks.
1. surfd generation carrying `runs_plat()` (surfd.py; recplot.py, web/board.js, web/board.css,
   templates/admin_run.html beside it). Additive: `ALTER TABLE runs|replays ADD COLUMN plat INTEGER NOT NULL
   DEFAULT 0`, no schema bump; older progs post no `plat` and an older generation ignores the column.
   Check: surfd/test_plat.py before; live, `PRAGMA table_info(runs)` and `(replays)` list `plat`. No test
   POST onto a real board: the live posting check is step 2's real Linux run.
2. Lobby qwprogs + csprogs, with `ftesurf/cfg/lobby/lobby.cfg` (`set sv_rank_linux 0`; unset also reads 0
   on a lobby): Linux runs still do not rank (PW_PLATFORM) but are recorded and posted with `plat 1`.
   Check: a real Linux run lands on the COMMUNITY board, its /api/board row says `"plat":1`, its .rec has
   `plat 1` in the header and after `prof`, and the scoreboard's community tab draws it sky blue.
3. `rcon set sv_rank_linux 1` on every lobby and `set sv_rank_linux 1` in lobby.cfg: Linux runs rank, marked.
Rollback, in reverse and in this order: FIRST `rcon set sv_rank_linux 0` on every lobby AND lobby.cfg back to
`0` (no restart; a restart with lobby.cfg at 1 would rank them again); then the progs' .prev; then the previous
surfd generation. Already-ranked Linux runs show unmarked under an older surfd (it does not read the column),
and its upserts leave `plat` stale (a Windows best over a Linux row keeps 1; a Linux best over a Windows row,
or a new replay row, gets 0). Repair once the runs_plat generation is back: (a) replays, raise-only, from each
file the window filed (`max(header plat, finish plat)`, as surfd's `_rec_plat` / `_rec_finish_plat` read
it); (b) runs with `replay_id > 0` take their replay's `plat`; (c) stage rows (`replay_id 0`) take the plat of
the leg-0 replay with their `runid`. A run a new progs posted to an older surfd is repaired the same way. Raise-only
cannot clear the stale 1 an older surfd leaves when a Windows run re-files a Linux run's leaf (an exact tie):
recompute those replays from their file (`max(header, finish)`) and lower them by hand.

## 17 Nov 2026 04:04Z: P1600 LIVE (tools/p1600-delivery.md)
tascontent.py sealed (mapwatch works again), guard tas86-v1, sweep.py/test_sweep.py at main (P1580; P1469 was
already live). mapwatch stays at the live bytes and `23 */6`; main's mapwatch.py cadence commits must not ship. Next
generation: ftesurf-a8's readers in the Root policy (then P1580's address check and the env activation), P1601
(ftesurf-29's 30-minute new-map route), CURRENT 85->86 constants.

## 16 Nov 2026 22:43Z: the P1592+P1595 generation shipped surfd.py + mapmanifest.py ONLY

LIVE (tools/p1592-delivery.md): runtime delta surfd.py + mapmanifest.py at main 6d228cb1; `sweep.py`, `test_sweep.py`,
`test_replays.py`, `test_mappool.py` stay at the previous bytes, so **P1469 and P1580 below are still pending**.
The next generation should also carry:
- `tascontent.py` as a new sealed runtime member: mapwatch has failed `ModuleNotFoundError: tascontent` under every
  sealed generation since 15 Nov, so the map list (data/mapwatch/mapdl.txt) has not been rewritten since then;
- mapwatch's canonical cron schedule `23,53 * * * *` (scan every 30 min) as a reviewed contract change;
- main's sweep.py/test_sweep.py (P1469, P1580); ftesurf-a8 reviews that lens and later does P1580's env activation.

## 16 Nov 2026: the P1590 generation shipped surfd.py ONLY

The generation that went live 16 Nov 14:12Z (P1590, tools/p1590-delivery.md) changed one runtime file, `surfd.py`
(main f052b3ec). Its identity names f052b3ec as source_ref, but `sweep.py` and `test_sweep.py` are the bytes the
previous generation ran: **the two entries below are still pending**. Compare runtime bytes with main when
building the next generation.

## Next qualified generation — P1469 unavailable similarity reporting

Include the published one-line `surfd/sweep.py` reporting fix from P1469: setup or
collector exceptions retain stderr and return an explicit unavailable/coverage-
not-measured tick-summary note. No schema, evidence, metric, verdict, threshold,
scheduling or resource-limit change. Existing test_simcheck passes79 checks on
Windows and79 on NanoPi Linux; [verification and limits](p1469-sweep-unavailable.md).
Not live yet: accepted runtime source bindings and namespace/Root prerequisites
must be qualified normally. Do not hot-patch an immutable serving generation,
reset grants, restore old data or reopen it to ship this small reporting change.

## Next qualified generation — P1580 receipt server address and account key

`surfd/sweep.py` + `tools/rcptcheck.py` (deploy the new rcptcheck to `SURFD_TOOLS`
too; an older one is skipped, not fatal). A first full receipt read now faults
(admin-only: `receipts.verdict`/`reason`, `sig` untouched, no schema change) a
signed server address that is not the Pi's, and a run credited to an account
whose receipt key is in none of that account's keylinks/installs/runpins
(ROADMAP 14.3 b). README "Receipt address and account-key checks".

Set at activation, in `surfd.env`:

    SURFD_RCPT_HOSTS=180.150.62.57
    SURFD_RCPT_LAN=192.168.1.102
    SURFD_RCPT_PORTS=27510,27520,27530,27540,27550,27560,27570,27580,27590,27600,27610,27620

Unset, the HOST check notes "not configured" -- but the svport rule below applies as soon as main's rcptcheck is in SURFD_TOOLS, env or no env (P1600 review): run it over a copy of the live receipts before copying rcptcheck. The account-key check lives in sweep.py and starts with the generation (dry run 0 of 2,299). DONE 17 Nov (main's rcptcheck, read-only on the Pi, deleted after): all 2,322 receipts carry `svport`, every one
equal to the signed port -- 0 svport faults; with the planned HOSTS/LAN/PORTS, 2,321 match the public address,
1 is the LAN note, 0 faults.
THE ROOT OBSERVER POLICY PINS THE EXTERNAL TOOLS BY HASH (ftesurf-4a, 17 Nov): each context requires its single
pin, so installing new tools before a Root install carries them makes the observer refuse every context and a
controller rollback refuse on reader drift. P1600 does NOT carry them. The generation AFTER P1600 pins these
(game main 8a17053d): rcptcheck.py 4d4837fe6529d060..., reccheck.py 10a9a469e0b41c18..., hidcheck.py
0962bf561bfbed27... DO NOT copy them to SURFD_TOOLS until that generation is live and ftesurf-4a (or its
successor) says go. 18 Nov: PIN reccheck.py 8ab35f6d63263bdd... (game main 00e2d9a5: P1603's `plat` and P1599's
angle join, both reviewed) instead of 10a9a469; rcptcheck.py and hidcheck.py are unchanged. P1599 clears the
false angle FAULTs (lobby evidence 18 Nov: 150 of 240 same-run FAULTs -> BLIND, none newly faulted); stored rows
change only with P1580's export + `--reread-receipts` below. P1604 (18 Nov) changes reccheck.py again (it knows the new header `propstatic`): gen1603 keeps 8ab35f6d; the generation after it pins reccheck.py 059246f0b7395fba... from game main. Until then the Pi's reccheck notes "header key 'propstatic' is not part of v14" on runs from P1604 lobby QC: a note, never a fault. Until then P1580's address check is skipped (getattr); its account-key check runs from P1600. The 16 Nov corpus (2,296
receipts) has 2,295 on the public address and 1 on the LAN one. A LAN address is reported as a note, never
passed or faulted (AGENT_NOTES: "a private address is nobody's" -- another network's server at that address
reads the same). The signed port must also equal the unsigned `svport` the writing lobby recorded, which
catches a nonce relayed between two of the Pi's own lobbies; that rule needs no setting. DTLS/TLS/TCP/
WebSocket clients sign the address with a scheme (`dtls://` etc., net_wins.c); it is stripped first.
If the public address changes, ADD the new one and keep the old in `SURFD_RCPT_HOSTS`: without the old
one, every new receipt faults, and `--reread-receipts` faults every older receipt signed on it.
Existing rows are judged only after `--reread-receipts` (200 a pass).
BEFORE `--reread-receipts`: export every receipt's (runid, verdict, reason, angles, angles_reason) to a dated
file. The re-read overwrites in place with no history and its summary does not count FAULT -> VALID; 231 rows
hold angle FAULTs the current reader repeats on honest lobby clients (BACKLOG, P1599 parked). Owner: Lex said
yes to activation on 17 Nov.
DONE 18 Nov 2026 (P1580 ACTIVE; gen1603 runbook step 15 -- 15a/15b by lex-90, 15c/15d by worldofsurf-43 on Lex's
"ok, go"): exports receipts/pubkeys-pre1580-20261117T191110Z.jsonl (with the backup surfd.db.bak-pre1580-...) and
receipts/pubkeys-pre1580r-20261117T215426Z.jsonl (one receipt arrived after the first); surfd.env.bak-pre1580-20261117T191110Z;
the three lines appended (sweep.server_allowlist: 1 host, 12 ports, 1 LAN, no error); marking pass 21:54Z marked 2,332,
re-read complete 22:50Z. Result = the 15b rehearsal: 152 FAULT -> VALID (151 angle FAULT -> BLIND, P1599), 6 VALID ->
FAULT (5 Lex's Sep/Oct bhop runs whose .view spans an earlier attempt -- BACKLOG; 1 borobongo surf_4am angle fault),
sig/pub/map unchanged, 0 svport/address faults, 0 "receipt server check off". 18 rows went angles BLIND -> "" (not
measured): their .view remains but no .rec names the run any more (a later best replaced it); verdicts unchanged.
POSTFLIGHT HTTP CHECKS (lex-90, 18 Nov): gen1600's postflight_readonly.py and the runbook's 2d check fetched
127.0.0.1:8080, which on the Pi is File Browser; surfd binds 8084. P1600's postflight HTTP section proved nothing;
gen1603's copy is fixed -- start the next generation's tooling from it.

BEFORE ACTIVATION, run `sweep.join_account_key` over a COPY of the live DB (each receipt's runid and pub;
never the live file) and record the fault count here. Expected sources of honest-looking faults: the
owner's ranked rows moved to his account by hand on 11 Oct (signed by his old install's key), and runs
older than the 90-day `runpins` prune whose key was unlinked when the account already had 64 `installs`.
DONE 16 Nov (ftesurf-31, main 363ab0eb's sweep.py, SQLite backup of the live DB into agent-work, deleted after):
2,299 receipts, all signed; **0 faults**; 1,147 "the receipt's key is one of the credited account's", 1,152
"no account is credited with this run". Discriminates: each of the 1,147 with its key swapped for a made-up one,
or for another receipt's real key, faults (1,147 of 1,147 both ways).

Windows only, not run on the Pi: test_rcptcheck 827 checks/0 failed (was 800),
test_sweep 427 ok/0 failed (was 388), test_receipt_{identity,initial_partial,
late_hid,late_rec,late_view,metrics} 0 failed. Mutants fail a named arm: 8 of 8 in
the first round, 5 of 5 in the review round (runpins without `pub = ?`, checks
before the other joins, svport only when configured, no scheme strip, no `runs`
credit). test_receipt_angle_reasons fails one check ("epoch: reader detail names
the measurement/abstention") identically at f5d4450f without this patch.
