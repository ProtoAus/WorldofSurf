/* Patch 502: a visual prefix beside each save's .view. This is not evidence.
   Raw samples retain contact/stitch marks when a branch is rebuilt; copying
   only the decimated positions would keep abandoned glyphs and lose colours. */
float tr_raw, tr_stitch, tr_slseq, tr_cur_flags;
// P1756: the rows of tr_raw in use. A load of a save on this line cuts here instead of re-reading its trail.txt
// (Trail_Load); strings past it are stale, overwritten as the line grows again.
float tr_rawn;
float() Trail_RawN = { return (tr_raw >= 1) ? tr_rawn : 0; };
vector tr_cur_ang, tr_cur_vel, tr_loadorg;
float tr_rep_raw, tr_rep_tick, tr_rep_end, tr_rep_ack, tr_rep_go, tr_saveack;
float tr_rep_n;                 // P1756: the rows of tr_rep_raw in use (Trail_RewindPrefix copies the whole buffer)
float(float t) Trail_RawIndex;
float tr_req_wait;
float tr_timedgo_ack, tr_go_visual_t, tr_rep_tracewant, tr_rep_tracegot, tr_ticket;
float tr_practice, tr_practicebase, tr_practiceat;
// P1007: the energy zero the HUD used for this sample, as a 15th field of the
// raw line when known (a 14-field line is an older file or a replay prefix).
float tr_eref, tr_erefok;

/*
  P1384: a load or a trim fills tr_raw at once and the live line takes those rows over the next
  frames (Trail_Catch from Trail_Frame), TR_CATCH a frame. Refeeding them all in the load's frame
  was 300 ms for 45835 rows, 45 ms for 6416 (bhop_monster_jam save012, a p90 save; rig/bench1 in
  the P1384 task root). While it catches up Trail_Take only records, so the rows stay in order;
  Trail_Settle finishes it first wherever the whole line is read (rewind, a run's end).
*/
#define TR_CATCH 400            // ~2.6 ms of QC a frame at the measured 6.6 us a row
#define TR_CATCHMS 0.004        // P1756: and about this long a frame -- a row costs 15-30 us now (rig long3, 36k rows)...
#define TR_CATCHMIN 128         // ...but at least this many rows, so a rewind's Settle soon after finds little left
float  tr_catching, tr_catchi;  // the line is behind tr_raw; the next row it has not taken
float  tr_catchcl, tr_catchspent;       // P1756 review: this frame's cltime and the catch time spent in it
vector tr_catchv;               // the last recorded sample's velocity: Trail_Take's break test

// A catch dropped before it finished: the slot's points are unbuilt, so it is cleared, not drawn.
void() Trail_CatchDrop =
{
	if (!tr_catching)
		return;
	tr_catching = FALSE;
	ln_holdslot = 0;
	Line_Clear(tr_live);
};

void() Trail_RawClear =
{
	if (tr_raw >= 1)
		buf_del(tr_raw);
	tr_raw = buf_create_ex("string", 0);
	tr_rawn = 0;
	tr_stitch = tr_practice = FALSE;
	tr_catching = FALSE;            // the callers Line_Begin the slot right after
	ln_holdslot = 0;
};

// One raw row into the live line, nothing else (Trail_Take keeps the sample counters).
float(string s) Trail_CatchFeed =
{
	local float n;
	n = tokenize(s);
	if (n != 14 && n != 15)
		return FALSE;
	Line_Point(tr_live, [stof(argv(1)), stof(argv(2)), stof(argv(3))],
	           [stof(argv(4)), stof(argv(5)), stof(argv(6))], stof(argv(7)), stof(argv(0)),
	           stof(argv(8)), stof(argv(9)), [stof(argv(10)), stof(argv(11)), stof(argv(12))]);
	return TRUE;
};

// Up to `rows` more of tr_raw into the line, held (ln_holdslot) until it is whole: unbuilt
// points draw one by one and a Line_End repaints the slot, so it is neither painted nor drawn
// meanwhile. Line_End runs every step (it builds from its watermark): one at the end over 45834
// rows was a 46-52 ms frame. A bad middle row is passed over (Trail_Load stops at a cut last one).
void(float rows) Trail_Catch =
{
	local float n, end, t0, g, fed;
	if (!tr_catching)
		return;
	n = Trail_RawN();
	end = min(n, tr_catchi + rows);
	// Review: gettime(2), the per-frame clock (gettime(1) is whole ms, coarser past hours); one budget a frame
	// across the frame's calls (Trail_Frame, a load's and a trim's CatchStart).
	if (cltime != tr_catchcl)
	{
		tr_catchcl = cltime;
		tr_catchspent = 0;
	}
	t0 = gettime(2);
	for (g = fed = 0; tr_catchi < end; tr_catchi = tr_catchi + 1)
	{
		Trail_CatchFeed(bufstr_get(tr_raw, tr_catchi));
		fed = fed + 1;
		if (rows == TR_CATCH && (g = g + 1) >= 32)
		{
			g = 0;
			if (fed >= TR_CATCHMIN && tr_catchspent + gettime(2) - t0 > TR_CATCHMS)
			{
				tr_catchi = tr_catchi + 1;
				break;
			}
		}
	}
	tr_catchspent = tr_catchspent + max(0, gettime(2) - t0);
	Line_End(tr_live);
	if (tr_catchi < n)
		return;
	tr_catching = FALSE;
	ln_holdslot = 0;
};

void() Trail_Settle = { Trail_Catch(LN_CAP * 4); };

// The rows just put in tr_raw: counters from its last row, then the line starts catching up.
void() Trail_CatchStart =
{
	local float n;
	n = Trail_RawN();
	tr_nsamp = n;
	tr_lastt = 0;
	if (n > 0 && tokenize(bufstr_get(tr_raw, n - 1)) >= 14)
	{
		tr_lastt = stof(argv(0));
		tr_lastp = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
		tr_catchv = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
	}
	tr_catchi = 0;
	tr_catching = (n > 0);
	ln_holdslot = tr_catching ? tr_live + 1 : 0;
	Trail_Catch(TR_CATCH);
	if (!n)
		Line_End(tr_live);
};

string(vector o, vector v, float fl, float t, float brk, float stitch, vector aux, float pitch) Trail_RawSample =
{
	return sprintf("%.6f %s %s %g %g %g %s", t,
	               sprintf("%.6f %.6f %.6f", o_x, o_y, o_z),
	               sprintf("%.6f %.6f %.6f", v_x, v_y, v_z), fl, brk, stitch,
	               sprintf("%.6f %.6f %.6f %.6f", aux_x, aux_y, aux_z, pitch));
};

#include "cl_trailreplay.qc"

void(vector o, vector v, float fl, float t, float brk, float stitch, vector aux) Trail_Record =
{
	if (tr_raw < 1)
		return;
	if (tr_rawn >= LN_CAP * 4)
		return;
	if (tr_erefok)
		bufstr_set(tr_raw, tr_rawn,
		           strcat(Trail_RawSample(o, v, fl, t, brk, stitch, aux, input_angles_x),
		                  sprintf(" %.4f", tr_eref)));
	else
		bufstr_set(tr_raw, tr_rawn, Trail_RawSample(o, v, fl, t, brk, stitch, aux, input_angles_x));
	tr_rawn = tr_rawn + 1;
};

// Raw clocks are six-decimal text. Compare cutoffs in that same representation.
float(float t) Trail_RawClock =
{
	return stof(sprintf("%.6f", t));
};

// Last sample at/before t on the nondecreasing clock, including duplicates.
float(float t) Trail_RawIndex =
{
	local float lo, hi, mid;

	if (tr_raw < 1) return -1;
	lo = 0;
	hi = tr_rawn - 1;
	if (hi < 0) return -1;
	while (lo < hi)
	{
		mid = ceil((lo + hi) * 0.5);
		if (stof(bufstr_get(tr_raw, mid)) <= t) lo = mid;
		else hi = mid - 1;
	}
	return lo;
};

// Authoritative practice-save posture/velocity remains the selected sample.
void(float t) Trail_CursorState =
{
	local float i, n;

	tr_cur_flags = 0;
	tr_cur_ang = '0 0 0';
	i = Trail_RawIndex(t);
	if (i < 0) return;
	n = tokenize(bufstr_get(tr_raw, i));
	if (n != 14 && n != 15) return;
	tr_cur_flags = stof(argv(7));
	tr_cur_ang = [stof(argv(13)), stof(argv(10)), 0];
	tr_cur_vel = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
};

float tr_vis_ok, tr_vis_flags, tr_vis_eref, tr_vis_erefok;
vector tr_vis_vel, tr_vis_ang;
// Visual interpolation has separate outputs; never used to serialize a save.
void(float t) Trail_VisualState =
{
	local float i, t0, t1, f, n;
	local vector vel0, ang0;

	tr_vis_ok = FALSE;
	tr_vis_flags = 0;
	tr_vis_erefok = FALSE;
	tr_vis_vel = tr_vis_ang = '0 0 0';
	i = Trail_RawIndex(t);
	if (i < 0) return;
	n = tokenize(bufstr_get(tr_raw, i));
	if (n != 14 && n != 15) return;
	tr_vis_ok = TRUE;
	// P1007: the zero is a step (a jump or an anchor moves it), so the sample's own.
	if (n == 15)
	{
		tr_vis_eref = stof(argv(14));
		tr_vis_erefok = TRUE;
	}
	tr_vis_flags = stof(argv(7));
	tr_vis_ang = [stof(argv(13)), stof(argv(10)), 0];
	tr_vis_vel = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
	t0 = stof(argv(0));
	vel0 = tr_vis_vel;
	ang0 = tr_vis_ang;
	if (i + 1 >= tr_rawn) return;
	n = tokenize(bufstr_get(tr_raw, i + 1));
	if (n != 14 && n != 15) return;
	t1 = stof(argv(0));
	// Trails store breaks/stitches separately from legacy recording flags.
	if (t1 <= t0 || (stof(argv(7)) & 0x4000000) || stof(argv(8)) || stof(argv(9))) return;
	f = bound(0, (t - t0) / (t1 - t0), 1);
	tr_vis_vel = vel0 + ([stof(argv(4)), stof(argv(5)), stof(argv(6))] - vel0) * f;
	tr_vis_ang = Interp_View(ang0, [stof(argv(13)), stof(argv(10)), 0], f);
};

void(float t) Trail_Trim =
{
	local float i, n, tmp;
	local string s;
	n = Trail_RawN();
	tmp = buf_create_ex("string", 0);
	if (tmp < 1)
		return;
	Line_Begin(tr_live);
	Line_Tick(tr_live, tr_tick);
	tr_stagefrom = 0;               // P1006: a rebuilt line is shown whole until its next stage
	tr_contbrk = FALSE;
	t = Trail_RawClock(t);
	for (i = 0; i < n; i = i + 1)
	{
		s = bufstr_get(tr_raw, i);
		if (stof(s) > t)
			break;
		bufstr_set(tmp, i, s);
	}
	// Do not retain a future branch in either the points OR the raw history.
	if (tr_raw >= 1)
		buf_del(tr_raw);
	tr_raw = tmp;
	tr_rawn = i;
	Trail_CatchStart();             // P1384
	tr_since = 0;
	tr_builds = tr_builds + 1;
	tr_settle = cltime + TR_SETTLE;
	tr_stitch = TRUE;
	if (FS_SlopOp(SaveEvent_Slop()) == SLOP_LOADED)
		tr_loadorg = SaveEvent_Origin();
	else
		tr_loadorg = [getstatf(STAT_FS_SLORG), getstatf(STAT_FS_SLORG + 1), getstatf(STAT_FS_SLORG + 2)];
};

// P1087: what a TAS go (back, edit, undo) cut off at t, kept as the comparison line; the
// sample at/before t starts it so it joins the kept prefix. Nothing past t: the old one stays.
float tr_tasref;
float tr_tasload_at;            // cltime this client sent `tas project load` (cl_tastimeline.qc)
float(float st) Trail_TASGo =
{
	return (getstatf(STAT_FS_TASPAUSE) == 1 && st == TS_RUNNING && cltime - tr_tasload_at > 3);
};
void() Trail_TASDrop =
{
	if (tr_tasref) Line_Clear(LN_S_TASREF);
	tr_tasref = FALSE;
};
void(float t) Trail_TASKeep =
{
	local float i, n, a;
	n = Trail_RawN();
	a = Trail_RawIndex(Trail_RawClock(t));
	if (a < 0 || a + 1 >= n)
		return;
	ln_want = min(n - a, LN_CAP2);  // the arena grew by LN_CAP2 for it; longer is halved
	Line_Begin(LN_S_TASREF);
	Line_Tick(LN_S_TASREF, tr_tick);
	for (i = a; i < n; i = i + 1)
	{
		if (tokenize(bufstr_get(tr_raw, i)) < 14)
			continue;
		Line_Point(LN_S_TASREF, [stof(argv(1)), stof(argv(2)), stof(argv(3))],
			[stof(argv(4)), stof(argv(5)), stof(argv(6))], stof(argv(7)), stof(argv(0)),
			stof(argv(8)), stof(argv(9)), [stof(argv(10)), stof(argv(11)), stof(argv(12))]);
	}
	Line_End(LN_S_TASREF);
	tr_tasref = (ln_n[LN_S_TASREF] >= 2);
};

string(float id) Trail_SavePath =
{
	local string p;
	p = Rec_SavePath(id);
	return strcat(substring(p, 0, strlen(p) - 8), "trail.txt");
};

/*
  P1756: a save's trail.txt is a prefix of the live line while nothing has replaced its rows since: the row count
  it wrote, its last row and its clock are kept (Trail_Mark), and a load that finds that row still at that place
  cuts tr_rawn there instead of reading the file back (a QC fgets loop over every row of the run).
*/
float *tr_wm_n;                 // rows; 0 none
float *tr_wm_ticks;            // the save's run clock
float *tr_wm_tick;             // the line's tick length
string *tr_wm_row;

void(float id) Trail_Forget =
{
	if (!tr_wm_n || id < 0 || id > FS_MAXSAVES)
		return;
	tr_wm_n[id] = 0;
	if (tr_wm_row[id] != "") strunzone(tr_wm_row[id]);
	tr_wm_row[id] = "";
};

// Rows 0..last of the live line are save id's picture (taken at ticks, on a line of tick seconds).
void(float id, float ticks, float tick, float last) Trail_Mark =
{
	if (id < 0 || id > FS_MAXSAVES)
		return;
	if (!tr_wm_n)
	{
		tr_wm_n = memalloc(sizeof(float) * (FS_MAXSAVES + 1));
		tr_wm_ticks = memalloc(sizeof(float) * (FS_MAXSAVES + 1));
		tr_wm_tick = memalloc(sizeof(float) * (FS_MAXSAVES + 1));
		tr_wm_row = memalloc(sizeof(string) * (FS_MAXSAVES + 1));
	}
	Trail_Forget(id);
	if (last < 0 || last >= tr_rawn)
		return;
	tr_wm_n[id] = last + 1;
	tr_wm_ticks[id] = ticks;
	tr_wm_tick[id] = tick;
	tr_wm_row[id] = strzone(bufstr_get(tr_raw, last));
};

float(float id, float ticks) Trail_Marked =
{
	local float n;
	if (!tr_wm_n || id < 0 || id > FS_MAXSAVES || tr_raw < 1)
		return FALSE;
	n = tr_wm_n[id];
	if (n < 1 || n > tr_rawn || tr_wm_ticks[id] != ticks || tr_wm_tick[id] != tr_tick)
		return FALSE;
	return !strcmp(bufstr_get(tr_raw, n - 1), tr_wm_row[id]);
};

void(float id, float ticks) Trail_Save =
{
	local float f, n, t, raw, tick, timed, observed, last;
	raw = (tr_rep_raw >= 1) ? tr_rep_raw : tr_raw;
	tick = (tr_rep_raw >= 1) ? tr_rep_tick : tr_tick;
	if (raw < 1 || tick <= 0)
	{
		observed = (tr_req_wait > 0 && getstatf(STAT_FS_SLSAVEACK) == tr_req_wait &&
		            FS_SlopOp(getstatf(STAT_FS_SLSAVEOP)) == SLOP_SAVED &&
		            FS_SlopId(getstatf(STAT_FS_SLSAVEOP)) == id);
		if (!observed)
			observed = (tr_saveack > 0 && SaveEvent_Tag() == tr_saveack);
		if (observed)
		{
			fremove(Trail_SavePath(id)); // invalidate only an observed new save
			Trail_Forget(id);
			SaveLead_Forget();
		}
		Trail_ReplayClear();
		return;
	}
	f = fopen(Trail_SavePath(id), FILE_WRITE);
	if (f < 0)
		return;
	timed = (ticks >= 0);           // the saved result, not a later load's live state
	fputs(f, sprintf("FTESURF-TRAIL 1 %.9g %g %g\n", tick, ticks, timed));
	n = (raw == tr_raw) ? tr_rawn : tr_rep_n;
	t = timed ? ticks * tick : 99999999;
	t = Trail_RawClock(t);
	// P1756: the rows at/before t (clock order: the tail past t is the few frames since the save), written by the
	// engine. The QC loop was a row at a time in this frame.
	for (last = n - 1; last >= 0; last = last - 1)
		if (stof(bufstr_get(raw, last)) <= t)
			break;
	buf_writefile(f, raw, 0, last + 1);
	fclose(f);
	// A press's snapshot (Trail_RewindPrefix) is a copy of the live line: marked while its last row is still there.
	if (raw == tr_raw || (last >= 0 && last < tr_rawn && tick == tr_tick && !strcmp(bufstr_get(raw, last), bufstr_get(tr_raw, last))))
		Trail_Mark(id, ticks, tick, last);
	else
		Trail_Forget(id);
	SaveLead_Remember(id, ticks, raw, last);  // P1384
	Trail_ReplayClear();
};

float(float id, float ticks) Trail_Load =
{
	local float f, tick, saved, i, argc, timed, endt;
	local string s, last;
	// P1756: before the open -- FILE_READ reads the whole file on the first fgets.
	if (Trail_Marked(id, ticks))
	{
		tr_stitch = tr_practice = tr_catching = FALSE;      // Trail_RawClear's, keeping the rows
		ln_holdslot = 0;
		tr_rawn = tr_wm_n[id];
		Line_Begin(tr_live);
		Line_Tick(tr_live, tr_tick);
		tr_stagefrom = 0;
		tr_contbrk = FALSE;
		Trail_CatchStart();
		tr_since = 0;
		tr_builds = tr_builds + 1;
		tr_settle = cltime + TR_SETTLE;
		tr_stitch = TRUE;
		return tr_nsamp > 0;
	}
	f = fopen(Trail_SavePath(id), FILE_READ);
	if (f < 0)
		return FALSE;
	s = fgets(f);
	argc = tokenize(s);
	tick = stof(argv(2));
	saved = stof(argv(3));
	timed = (argc >= 5) ? stof(argv(4)) : (saved > 0);
	if (strcmp(argv(0), "FTESURF-TRAIL") || stof(argv(1)) != 1 || tick <= 0 || saved != ticks)
	{
		fclose(f);
		return FALSE;
	}
	Trail_RawClear();
	tr_tick = tick;
	Line_Begin(tr_live);
	Line_Tick(tr_live, tick);
	tr_stagefrom = 0;               // P1006
	tr_contbrk = FALSE;
	endt = timed ? ticks * tick : 99999999;
	endt = Trail_RawClock(endt);
	last = "";
	for (i = 0; i < LN_CAP * 4; i = i + 1)
	{
		s = fgets(f);
		if (!strcmp(s, ""))
			break;
		if (!i)
		{
			argc = tokenize(s);
			if (argc != 14 && argc != 15)
				break;              // not a picture row: an empty picture, as before
		}
		if (stof(s) > endt)
			break;
		if (i)
			bufstr_set(tr_raw, i - 1, last);
		last = s;
	}
	fclose(f);
	// One row behind: a crash mid-write leaves the last row cut, and it is kept only if it parses.
	tr_rawn = max(0, i - 1);
	if (i)
	{
		argc = tokenize(last);
		if (argc == 14 || argc == 15)
		{
			bufstr_set(tr_raw, i - 1, last);
			tr_rawn = i;
		}
	}
	Trail_Mark(id, ticks, tick, tr_rawn - 1);      // P1756: a reload of it cuts
	Trail_CatchStart();             // P1384: the line takes these rows over the next frames
	tr_since = 0;
	tr_builds = tr_builds + 1;
	tr_settle = cltime + TR_SETTLE;
	tr_stitch = TRUE;
	return tr_nsamp > 0;
};

#include "cl_trailrequest.qc"
