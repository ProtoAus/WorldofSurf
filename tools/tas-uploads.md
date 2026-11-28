# TAS uploads and bring-your-own bot — plan (20 Nov 2026)

## Lex's decision, 20 Nov 2026

> "I don't mind if the anti-cheat can't work 100% it's ok, as long as the run makes
> sense physics wise, it's fine."

This widens the 28 Oct rule (TAS boards admit only server re-simulated runs, no offline
TAS): a TAS record made anywhere — our TAS tools, someone's own bot, a fork such as
Rounin's — can be uploaded, and goes on the TAS board when its physics checks out.
TAS stays off the human and segmented boards; nothing here changes their admission.

## Verdict ladder for an uploaded `.rec`

| Verdict | How | Board |
|---|---|---|
| EXACT (not built) | native recording with `in` rows: `pm_verify` (sweep.py) re-simulates it in our engine and the zones finish it | "re-simulated" badge |
| PLAUSIBLE | `tools/tasplaus.py` PASS: every tick within the measured movement bounds, start/checkpoints/finish visited | upload board (tasupd), "physics checked" |
| HOLD | tasplaus HOLD | owner review queue (`tasupd.py list`), shown to its uploader only |
| FAIL | cannot be a run (no samples, clock backwards, past sv_maxvelocity, samples stop before the finish) | refused with the reason |

tasplaus status (commit b7fab6e2): 117/117 honest KSF/Momentum replays PASS; 12 checks
each proven by a cheat test (speed edits, deleted ticks, teleports into the end, clock
edits, low gravity, start outside the zone, early finish claims). Not yet known to it:
collision (a wall clip at legal speed passes), map push/booster volumes (HOLD), stage
legs (HOLD). Before it gates a public board it gets the independent review that
evidence code requires (CLAUDE.md).

## Bring your own bot (what already works)

- **Any tool, any fork**: the upload takes a `.rec`, so whatever produced it — a fork of
  this public repo, an external optimiser, a hand-made input list — is judged by the
  same physics. A fork that changes movement gets PLAUSIBLE at best, never EXACT.
- **Your inputs, our physics**: `tas demo <file> [rows [from]]` plays a recording's
  input rows (moves, pitch, yaw, with a `ksfbuttons` line before each) as TAS tapes in
  a local game (sv_tasoptimize.qc, P1449). An external program can write that file;
  the game plays it under the real mover and records a native run that can reach EXACT.
- **Tweak Jargon**: every search weight is a `tas_jargon_w_*` cvar (Tuning tab, P1572).
  A preset is a `.cfg` of those lines that people share and `exec`.
- **Analysis**: `tools/runcompare.py REF.rec RUN.rec ...` splits runs at the reference's
  ramp boards, gives the loss per split, the sum of best splits and per-ramp board/leave
  numbers. First use: surf_sandtrap2 bonus 4 (WR 7.827, human-proven splits ≈ 7.765).

## Built: P1640 upload service (tasupd)

`surfd/tasupd.py` at `https://play.proto.bar/tasup/`: an isolated service like tasrevd (own
store under `/srv/nvme/ftesurf-ops/tasupd-state`, read-only surfd `accounts`, no surfd schema or
generation change, 127.0.0.1:8093; 8091 is the twitch bot).

- **Who**: Steam OpenID sign-in on the page; the SteamID must have a World of Surf account (signed
  in once at `/board/link`, which states that names are shown) and no ban (Lex, 20 Nov: Steam-linked
  only). Bans and names are read live (5-minute cache); a ban hides that player's rows.
- **What**: a FTESURF-REC, 8 MB max, tickrate/movetickrate 0.015, map and track from its header,
  read by tasplaus's own header reader (a key given twice or a line break other than `\n`/`\r\n`
  is refused). The KSF/Momentum importers' header lines (`foreign`, `ksfdemo`, `mom-`/`ksf-` run ids...)
  are no claim (P1798, 24 Nov: Rounin's bot run on a downloaded KSF replay's header was refused); instead
  each upload's motion is compared with the course's public replays (surfd's KSF, Momentum and World of Surf
  runs: the one its runid names, then the 8 nearest in length whose files read, 2 a player, never the uploader's own;
  6 s, then the rest go unread) and the same motion is refused as "the motion of <player>'s <source> run". Held for
  the owner instead: a match with a lobby TAS-style row, with a lobby row surfd hides (banned owner, rejected in
  review; never named), or an upload shorter than the replay it matches by more than the matcher's 16-tick shift
  window (a tool improving a seed run; within the window a copy's end line can simply be moved).
  /api/health fails while a replay folder cannot be read; stage legs (`leg`/`startseg`) refused (whole courses only); the header must end within
  64 KB and the samples must be plain ASCII. The same file twice is refused. Another player's motion
  is HELD for the owner with "the motion of run N (another player's)", never shown (two bots on one
  course may converge, so it is not refused as an accusation): rounded motion, or velocities on the
  tick grid (samples at their nearest tick, so moving every time by part of a tick does not hide it)
  against the course's uploads within 10% of the length -- at most 3 per other account, shown ones
  first, 60 in all; +-8 ticks, 2 u/s + 1% on 95% of the upload's sampled ticks -- or the path itself (each step between samples within the same
  tolerance, positions only: velocities edited on their own or a constant offset do not hide it), so
  a reprint, a new header, dropped samples or a lightly edited copy is refused as theirs; so is
  anything the owner removed (that one is refused). A copy re-flown with deliberate small changes (a physically consistent
  wiggle of a few units) is not caught: remove it by id. Your own runs may be
  uploaded again (a re-export, an improvement).
- **Record backstop**: tasplaus cannot see walls, so an upload that reaches the best known time on its
  course (surfd's clean record in a trusted tier: ranked, momentum or ksf -- not community, banned or
  `tas`-styled rows -- or the best upload shown) is held for the owner, ties included, and so is the
  first upload on a course with no time at all. A run held for physics carries the same note, so an
  approval knows it makes a record. Rounin's run will be held: approve it and later slower uploads
  show by themselves. A TAS author whose every upload is a new record hits the 10-held cap: approve
  or reject to free it. Your own shown motion uploaded again skips the hold only at the same or a slower
  finish: the same samples may claim any finish the end-zone slack allows (review 5: a slow decoy came
  back as the record).
- **Verdicts**: tasplaus PASS -> shown ("physics checked"); HOLD -> held, its uploader sees the
  reasons; FAIL -> refused with the reasons, not kept. At most 40 reasons are kept per run. A held
  run the owner approves is labelled "owner approved", not "physics checked". Review-1 (P1640)
  tasplaus rules, all HOLD: samples off whole ticks, under 2 decimals, ground speed-squared gain
  over 2AW-A^2, a jump not from the ground, contact-tick travel the velocity does not explain, an
  air turn past v'.(v'-v) <= 30|v'-v|, a finish claimed more than a hull early, a teleport that is
  not back to the ridden stage's start or gains speed, a start over 480 u/s (3D), or a moving
  opening on a course with no start limit. Review 2: friction on ground ticks, jumps only after
  a sample that is not rising, unexplained travel summed per second, sharp turns that keep speed
  (air control cannot, a wall would take speed) on air and contact ticks, the clock starting high
  in the start box; walls, steps, slopes and shortest-form numbers no longer hold. The speed cap
  is the larger of the zone file's and `cfg/maps/map_<map>.cfg`'s sv_maxvelocity (past it: HOLD).
  Review 3: landings on a down-slope (the slope fix) and jumps straight after a rising landing pass;
  an arc's top reaching vz 0 by gravity alone is no landing; duck sums reset on jump ticks; steps of 2+
  ticks count with off-tick ones and their turns are checked; the precision is the coarser of positions
  and velocities. Honest corpus (117 sandtrap2 b4 replays): all PASS; across 301 honest files no
  verdict changed in either round. Review 4: hops off an up-slope (the engine lands at the next
  tick's start, jumping from vz up to 140), %g-printed deep maps, and a slope landing inside a lost
  packet pass; jump ticks are held to air control (|v'|^2 <= |v|^2 + 900); at most one lost packet
  after the start, and it may hide ~2 ticks (~0.03 s). Review 5: precision is read from the samples
  checked only (one coarse sample past the finish had widened every bound) and trailing zeros are not
  significant; the end zone allows a tick of travel for a file whose samples stop before its finish (our
  recorder's last sample is the tick before; 53 false "never reaches end" gone, no new reason across 276
  honest files); a jump inside a lost packet gets its ground ticks' allowance; 2+ lost packets after the
  start still hold, now saying so plainly. Review 6: a number other than plain decimal or exponent form
  (`3_4_8.4`, `nan`, Unicode digits: Python reads them, other readers do not) FAILs the file; precision is
  per pair, from its two samples; the end-zone allowance covers the ticks the samples stop short (up to 2);
  a lost packet on the ground allows a step or slope's rise; a jump inside one gets its ground ticks'
  friction; header integers are ASCII digits only. Review 7: the body must leave the start zone within 2.5
  ticks of t=0 (or 8 u at its speed; honest max 1.73 ticks) -- a clock relabelled to start early holds; a file
  that shows %g output gets each number's %g rounding (z -14942 is 0.05 coarse); the energy test's height term
  reads z's precision alone; the per-second drift limit is 6 u (honest PASS max 0.33); at most 100000 samples.
  Review 8: beside the median, the clock's trimmed mean (largest 2 + 1% dropped) must stay <= 1.002 and at most
  2 + 1% of moving steps may cover over 1.15x their speed x time (a clock compressed on a minority of ticks);
  in free flight a ratio over 1 is first discounted by |vb|/|mean| (slow perfect strafing); an air wall hit gets
  the contact allowance in the drift test. Review 9: the clock tests also run in 3D (a velocity tilted toward
  horizontal on ramp ticks had kept the horizontal ratio at 1.000) and the |vb|/|mean| discount applies on every
  tick, contact included (short courses that gain speed on a ramp); exponent-form numbers count their real
  decimals (numpy's %.18e is full precision).
- **Board**: `/tasup/board?map=&track=` best per player; `/tasup/run/<id>` reasons and numbers;
  `/tasup/run/<id>.rec` the file (shown runs only); JSON under `/tasup/api/`.
- **Caps**: 30 uploads per account a day (refusals count), 1000 uploads / 1 GiB of kept runs for
  everyone, 10 held per account, 4 GiB store, 120 reads (GET and HEAD) and 10 sign-ins a minute per
  address (IPv6 by /64), 30 Steam confirmations a minute for everyone and 2 at once, 8 form parts,
  one checker at a time (a 6 MB / 88k-sample file: 1.5 s, 75 MB on the Pi; unit MemoryMax 512M, no
  swap; at most 200 reasons listed by the checker), `.rec` downloads 32 MiB a minute per address and
  128 MiB for everyone, nginx `limit_rate 1m`.
- **Owner review** (as proto on the Pi):
  `python3 /opt/ftesurf-tasupd/<commit>/tasupd.py --store /srv/nvme/ftesurf-ops/tasupd-state/tasup.sqlite3 list`
  then `show ID`, `approve ID [--note ...]`, `reject ID [--note ...]`, `remove ID`, `unblock ID`. A rejected run
  shows its note to its uploader; a removed one is gone for everyone (its file is deleted), and
  its motion stays refused as a duplicate -- except to an uploader who owns that motion (below). A rejected run uploaded again by
  its uploader is held with a note; `approve` also undoes a reject. Review 6: whether a removed run refuses
  you depends on whether you own that motion (a shown or held run of yours with it), not on upload order;
  your rejected motion is caught by the copy match too. `unblock ID` turns a removed run back into a hold
  for its motion (the real author's upload then waits as "another player's"); it cannot be approved itself
  (its file is gone). `reject`/`unblock` without `--note` keep the note; `approve` clears a reject's note.
  Review 7: only a SHOWN run of the motion counts as owning it (a held copy does not); another account's
  rejected run no longer holds the owner of that motion; an identical file is refused with how to re-upload.
  Review 8: a held run of yours counts against copies made after it (the author's first, held upload is not
  refused once a later copier is removed); your own duplicate names your run; 10 candidates per other account.
- **Known gap**: a human's public replay with its import markers stripped is real motion and
  passes; tasupd does not yet compare uploads with surfd's public replays (BACKLOG). Remove it by id.
- **Known gap** (review 6): another player's run re-timed as a whole by ~0.1% (times / f, velocities x f)
  is not seen as a copy -- sub-tick samples drift across tick boundaries -- so it can show a tick ahead of
  theirs below the record (at the record the backstop holds it). Remove it by id; BACKLOG has the fix.
- **Load**: at most two uploads are checked at once (a third gets 503 at once), one per account, so pages
  and sign-in keep two of gunicorn's four threads; each candidate's motion is read one at a time by id; the
  copy check stops after 20 s and holds the run for the owner; copies are matched up to 16 ticks apart.

Install: `tools/install_tasupd.py`, root, dry run by default (install_tasrevd.py's shape). Root takes
the installer out of git as proto into a root-owned file, checks its sha256, and runs that with
`python3 -I` (it refuses to be anything but the commit's own). The commit's own files go into a
root-owned release under /opt/ftesurf-tasupd, its connection-limit zones into
/etc/nginx/conf.d/ftesurf-tasupd-zones.conf, state dir as proto, systemd unit, loopback probe,
then ONE `include snippets/ftesurf-tasupd.conf;` after surfd's include in play.proto.bar's site
(exact predecessor hash required, backup in /etc/nginx), `nginx -t`, reload, public probe; nginx is
put back and the unit disabled if any step fails (Ctrl-C and hangup are held from the unit on). Both
probes read `/tasup/api/health`, which reads the store and surfd's accounts as the sandboxed service
does (a closed WAL surfd.db with no `-wal` is read immutable, as r2gateway does). `--upgrade-from
<installed commit>` for later releases; it runs the new release's `init` (additive schema steps) first.

INSTALLED 21 Nov 2026 00:10Z (Lex's root run): release /opt/ftesurf-tasupd/a8efd378, unit
`ftesurf-tasupd` on 127.0.0.1:8093, store /srv/nvme/ftesurf-ops/tasupd-state. Checked live: health ok,
the page, Steam sign-in redirect, an unsigned upload refused (401), `/tasup/api/board`.

## Built: P1696 upload from the game

The TAS menu's Upload tab (src/client/cl_tasupload.qc), in a game the player hosts (`isserver()`), lists the TAS runs
that game finished: each TAS finish appends `<sha256> <path>` to data/tasproj/uploads.txt (sv_timer.qc SV_TASUpNote),
which client code cannot write (engine QC_TasprojDenied), and `cmd tas uploads` (SV_TASUpList) answers the host's own
client with this map's newest 10 (TAS_EV_UPLIST). So a file a server's csprogs wrote into data/runs/ is never offered
as the player's run; Upload refuses bytes that differ from the recorded hash. A bot's .rec goes through the web form.
Upload: `POST /tasup/api/game/challenge {"sha"}` -> a code (8 hex time, 8 hex salt, 16 hex of the service's HMAC over
them and the file hash; nothing stored). Send, on a real press: `acct_sign(sha256("ftesurf-tasup <code> <sha>")[:32],
-6)` (zone publishing's kind, the site fixed; the digest names this purpose and the file, so neither service takes the
other's proof), then `POST /tasup/upload` as `application/x-ftesurf-tasup`: lines FTESURF-TASUP 1 / nonce / sha / pub /
sig / game, then the raw .rec. The service checks the code, the game code, the signature and the key's linked
unbanned account from the 396-byte header before reading the file (refusals then drain the body: nginx), spends the
code, then runs the web form's checks. Game code: the lobbies' csprogs (and the newest two `csprogs.dat.pre*`), released
csprogs learned from `releases/<ver>/update.json` (BLAKE2b, one a platform; fetched once from the mirror, network
failures retried, doubling to an hour), each carrying the upload flow (`ftesurf-tasup ` in its bytes); or by the owner,
as proto: `tasupd.py --store ... allow-code <sha256> [--note]` / `deny-code <sha256>` (any build) / `codes`. Refusals
answer 200 with ok=0 (the game's HTTP client keeps no other body). The tool reads "sent from the game": how it came,
not what made it (any linked key can sign any file).

INSTALLED 21 Nov 2026 03:01Z (Lex's root run, `--upgrade-from a8efd378`): release /opt/ftesurf-tasupd/73229378 (the
old unit kept as its unit.prev). Checked live: health and X-Tasupd-Source 73229378, the page, a game challenge, a
proofless game upload refused (200, ok=0); releases 0.1.45-0.1.54 learned (none carries the upload flow yet);
`allow-code 4af237be...` for Lex's dev install (main 73229378). Players: from the first release with P1696.

## Built: P1712 the offer (Lex 22 Nov: "an auto popup, like the f6 ... or do it automatically if they don't press anything")

SV_TASUpNote sends the host's client TAS_EV_UPNEW (path, mode) when no other own TAS run in the course folder is as
fast (SV_TASUpBest: every `*_tas.rec` there, each as its name's ticks at its header's own tick rate; ties are not a
best). The mode -- 2 the box then it sends itself (default, Upload tab "Auto-upload"), 1 the box asks, 0 nothing -- is
data/tasproj/upload_offer.txt, set by `cmd tas offer N [token]` from the host, so no server's csprogs or stuffed cvar
can change it; raising it needs the map's token, sent only to the host's own client with the list (the tab's chips use
it), so a bind a server once stuffed cannot turn auto-upload back on. The client (cl_tasupload.qc TASUp_NewEvent) asks for the list, then the challenge at once,
and shows a box where the F6 report boxes sit (under the finish card when that covers it): F6 sends it keyed (kind -6,
header 1) in one press, F7 keeps it local. In mode 2, when its 12 s run out -- counted only at state 2 while the box is
seen: not under the scoreboard, the TAS menu, another report box or any panel holding the cursor, no console or menu
over the game (ui_native_gamefocus) and the window in front (engine P1712 `cl_windowactive`) -- it sends itself:
`acct_sign(..., -7)`, a kind only the engine's P1712 has, always unkeyed ("key 0", no press spent), site fixed like
-6, and only on a loopback connection with the window in front; header FTESURF-TASUP 2 tells tasupd to verify that statement (GAME_AUTO_KIND)
and store the tool "sent from the game by itself". If the engine will not sign it, the box falls back to asking. The
box acts only on its own run (the tab's Back or another Upload closes it); bests arriving meanwhile wait, one a course.
Known limit: SV_TASUpBest reads every own `*_tas.rec` in the folder, a place a server's csprogs can write, so a planted
fast file can stop offers for that course; over 2000 files there is no offer at all (never a slower run as a best; the console says so). Checked headless against a scratch tasupd: auto send taken (held: Jargon's resume records), old engine refuses -7,
a finish slower than a saved one gets no box.
INSTALLED 22 Nov 2026 ~12:20 local (Lex's root run, `--upgrade-from e5ecca2b`, source /srv/nvme/ftesurf-ops/
tasupd-src-91a26c9f, installer sha256 688efc3c...b880): release /opt/ftesurf-tasupd/91a26c9f (e5ecca2b kept as unit.prev's;
1a144758 removed). Checked live: health ok, X-Tasupd-Source 91a26c9f, a header-2 upload now reaches the confirmation
check (409) where e5ecca2b refused it as "no account proof" (400).
Pushed: engine main c05e443e4 (tag patch-1712), game main 91a26c9f; Lex's dev install rebuilt (cs 79ceab96, allow-coded).

## P1716: published without review (Lex 22 Nov)

Asked whether a made-up wall-clipping record staying up until he notices was acceptable: "thats fine"; his 20 Nov rule
stays "as long as the run makes sense physics wise". So tasupd shows at once: a PASS; a new record (the record rule's
note says "published without review"); and a HOLD whose every note only says the checker could not see (tasplaus
note(..., unseen=True): stage leg, native resume records, low decimals, too little movement, lost packets (gaps of 8
ticks or fewer, still tested), whole multi-tick sample steps, no zones). A gap over 8 ticks is suspect: four review
rounds kept finding room for a shortcut inside one, and our own runs have none. Those carry runs.unchecked = 1 (schema
3) and read "not fully checked"; `tasupd.py list --state unreviewed` lists them and `approve` makes one "owner approved".
Still held: a HOLD saying the physics looks wrong (tasplaus out["suspect"]: speed or energy past the bounds, position
jumps, a gap over 8 ticks, steps between ticks past the allowance, clock edits, start/finish faults), a copy of
another player's motion, a checker that could not run. Lex's Jargon runs (resume records, lost packets, 2-tick steps)
come out unseen-only: published. `create_app(review=True)` / TASUPD_REVIEW=1 restores
the review flow, which the existing tests pin (svc.REVIEW_DEFAULT = True in test_tasupd.py). Next: re-simulation of
game uploads (pm_verify on the Pi) for a "re-simulated" mark -- Lex: "a cool part of the anti-cheat that I would want".

INSTALLED 22 Nov 2026 (Lex's root run, `--upgrade-from 91a26c9f`, source /srv/nvme/ftesurf-ops/tasupd-src-b61c53ef):
release /opt/ftesurf-tasupd/b61c53ef (91a26c9f kept as unit.prev's; e5ecca2b removed). Checked live: X-Tasupd-Source
b61c53ef, the page's publish-mode text, store user_version 3 with runs.unchecked, unit active without TASUPD_REVIEW.

## P1745: WOS User-Agents (Lex 23 Nov)
steam.py sends `WOS/0.1 surfd` and tasupd.py's code fetch `WOS-tasupd`, no URL (were `FTESurf/0.1 surfd
(+https://proto.bar/ftesurf)` and `tasupd`); nothing else in the service changed since b61c53ef.
INSTALLED 23 Nov 2026 03:10:52Z (Lex's root run, `--upgrade-from b61c53ef`, source /srv/nvme/ftesurf-ops/tasupd-src-45aab35b,
the installer copied to /root/install_tasupd-45aab35b.py first: as root it refuses a file proto can change): release
/opt/ftesurf-tasupd/45aab35b (b61c53ef kept as unit.prev's; 91a26c9f removed). Checked live: X-Tasupd-Source 45aab35b,
unit active, public /tasup/api/health 200, both labels WOS in the release.

## P1700: on the website

tasupd's pages carry the site's menu (SITE_NAV, `TAS uploads` current) and every site page links here (the release
page template, site/zoning.html, site/anticheat.html, surfd/web/board.html). The course finder is a map name with
the browser's own list (`<datalist>`, no script) of every map in the site's media/mapmeta.txt (TASUPD_MAPMETA,
re-read when it changes); a map's page (`/tasup/board?map=`, track defaults to Main) shows its thumbnail
(/ftesurf/media/thumbs/<uuid>.jpg, same origin: CSP img-src 'self'), tier, stage and bonus counts, and chips for
Main and each bonus (and any track with runs). The Steam link page is proto.bar/ftesurf/board/link.
INSTALLED 21 Nov (Lex's root run, `--upgrade-from 73229378`): release /opt/ftesurf-tasupd/da9042b3; checked live: the
menu, 2846 maps in the finder, surf_sandtrap2's thumbnail and Bonus 4 chip, CSP img-src 'self'. The site's static
pages (releases/0.1.54 index/zoning/anticheat) carry the link (edited in place, *.pre1700 backups); board.html waits
for the next surfd generation.

## Still to build

1. DONE by P1806 (below): shown uploads are rows of the boards' TAS tab. P1870: those rows carry a rep (replays kind
   `tasup`, a copy of the upload's .rec under surfd's TASUP_DIR = data/tasup), so the game's click plays it (the web
   board shows no community/TAS recording, by policy). Left: a link from such a row to its /tasup/run page.
2. EXACT: native recordings with `in` rows re-simulated by pm_verify (sweep.py), shown with a
   "re-simulated" badge.
3. tasplaus: map push volumes from the entity lump; stage legs (both HOLD today).
4. Optional: a short public "make your own bot" page describing the `tas demo` row format.

Lex, 20 Nov: Steam-linked uploaders only (answered the open question above).

## P1798: uploads judged by motion, not importer header lines (Lex 24 Nov, Rounin's sandtrap b4)
INSTALLED 25 Nov 2026 (Lex's root run, `--upgrade-from 45aab35b`, source /srv/nvme/ftesurf-ops/tasupd-src-a0cf6968, the
installer copied to /root/install_tasupd-a0cf6968.py): release /opt/ftesurf-tasupd/a0cf6968 (45aab35b kept as unit.prev's;
b61c53ef removed). Checked live: X-Tasupd-Source a0cf6968, /tasup/api/health {"ok":1,"replays":3} (the service lists the
three replay roots in its sandbox), unit carries TASUPD_REPLAYS. Next upgrade: --upgrade-from a0cf69682ea08fd2b9bdab3adc4f8468f8e734fb.

## P1806: uploads on the main board's TAS tab (Lex 25 Nov: Rounin's sandtrap main "doesn't appear on the leaderboard")
The TAS tab (web board, game boards) is surfd's community/tas rows; tasupd's uploads were only on /tasup/board.
`surfd/tasindex.py` files each player's best shown upload per course as one of those rows (node `tasup`, runid
`tasup-<id>`, TF_TAS, rep 0, name = the linked account's), every 5 minutes from a proto user timer
(`surfd/ftesurf-tasindex.{service,timer}`; not crontab, which the generation kits hash). Only into an empty slot: a
player with any TAS row of their own on that course (live, or set aside by surfd), or an unrejected lobby recording
of it, keeps it and the upload stays on /tasup/board -- the first review round showed that displacing and later restoring a lobby row can undo a reject or
lose a better lobby run. A row whose upload stops being shown (removed, rejected, beaten by the player's own better
upload) is taken out and the slot refilled from the player's best unrejected lobby replay (surfd.restand's rule).
Banned accounts are left to accounts.ban_rows; an upload row surfd set aside is not filed again. No state file: it
looks at every (map, track, player) tasupd's store has held, by primary key, and takes surfd's write lock only to
write. Never imports surfd (its connect() migrates). A held upload reaches the board once the owner approves it.

Install / upgrade (proto, no root; D=/srv/nvme/ftesurf-ops/tasindex, C=<commit>):

    mkdir -p $D/$C && git -C <clean checkout> show $C:surfd/tasindex.py > $D/$C/tasindex.py
    python3 $D/$C/tasindex.py --store /srv/nvme/ftesurf-ops/tasupd-state/tasup.sqlite3 --db /srv/nvme/surfd/data/surfd.db --dry-run
    git -C <checkout> show $C:surfd/ftesurf-tasindex.service | sed "s/@COMMIT@/$C/" > ~/.config/systemd/user/ftesurf-tasindex.service
    git -C <checkout> show $C:surfd/ftesurf-tasindex.timer > ~/.config/systemd/user/ftesurf-tasindex.timer
    systemctl --user daemon-reload && systemctl --user enable --now ftesurf-tasindex.timer

LIVE 24 Nov 2026 18:37:22Z (worldofsurf-8b): release $D/d8c4953325c9c4bc844a921eb09eed8c6e39714b, timer enabled; the
first pass filed Rounin's surf_sandtrap2 main (48.165) and Proto's bonus 4 (7.830). Log: $D/tasindex.log (a line only
when a pass changed something). Stop: `systemctl --user disable --now
ftesurf-tasindex.timer`; rollback: then the dry-run command with `--withdraw` instead of `--dry-run` (every upload row
off, slots refilled from lobby replays). `--full` finds upload rows of courses the store no longer names.

tasupd half: the Steam sign-in lasts 30 days, renewed by a page read a day after the cookie was made, and at most 90
days from the Steam sign-in; Sign out ends the account's session in every browser (meta `session <steamid>` = a
generation the cookie carries). Cookies made before this release are refused: everyone signs in once more.
INSTALLED 25 Nov 2026 00:51:44Z (Lex's root run, `--upgrade-from a0cf6968`, source /srv/nvme/ftesurf-ops/tasupd-src-cbefd439,
installer /root/install_tasupd-cbefd439.py): release /opt/ftesurf-tasupd/cbefd439 (with worldofsurf-47's P1820 site look;
a0cf6968 kept as unit.prev's; 45aab35b removed). Checked live: X-Tasupd-Source cbefd439, health ok (replays 3), the new
header and tabs, the Steam redirect, an old-format cookie served signed out (200), a game challenge, the TAS board API;
unit active with its TASUPD_* env. Next upgrade: --upgrade-from cbefd4396935a3d3b3484b63d7da1db165690c31.
