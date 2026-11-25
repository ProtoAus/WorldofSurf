/* Players occupies the scoreboard's table, never a second/sidebar SUI panel.
   Slot gaps are real; list-view scroll reaches every player. P770: the row is
   the Spectate target and its buttons sit on top of it (SUI's topmost element
   is the last added); only pinned-board clicks act. */
#define PL_MAXSLOT 64
#define PL_BMAX 64
float pl_specpick, pl_tppick, pl_rows, pl_bid, pl_bn, pl_req, pl_sent, pl_wait, pl_bgen;
float pl_rowh, pl_wheel;
float pl_bticks[PL_BMAX];
string pl_bmap, pl_profilepick;
vector pl_scroll;

void(string id, float ticks) Players_Note =
{
	local float i;
	if (id == "" || ticks <= 0) return;
	for (i = 0; i < pl_bn; i = i + 1)
		if (!strcmp(bufstr_get(pl_bid, i), id)) break;
	if (i < pl_bn) pl_bticks[i] = min(pl_bticks[i], ticks);
	else if (pl_bn < PL_BMAX)
	{
		bufstr_set(pl_bid, pl_bn, id);
		pl_bticks[pl_bn] = ticks;
		pl_bn = pl_bn + 1;
	}
};
void() Players_AbsorbBoard =
{
	local float i;
	if (!Online_Describes(0, 0, OB_TIER, "clean")) return;
	for (i = 0; i < ob_n; i = i + 1)
		Players_Note(FS_GuidId(bufstr_get(ob_bplayer, i)), ob_ticks[i]);
};
float(float reqid, float code, string body) Players_BoardReply =
{
	local int root, rows, row;
	local float i;
	if (!pl_req || reqid != pl_req) return FALSE;
	pl_req = 0;
	root = 0;
	if (!code) root = json_parse(body);
	if (root)
	{
		if (!strcasecmp(json_get_string(json_find_object_child(root, "map")), serverkey("map")))
		{
			rows = json_find_object_child(root, "rows");
			for (i = 0; i < min(OB_PAGE, json_get_length(rows)); i = i + 1)
			{
				row = json_get_child_at_index(rows, i);
				Players_Note(FS_GuidId(json_get_string(json_find_object_child(row, "player"))),
				             json_get_float(json_find_object_child(row, "ticks")));
			}
		}
		json_free(root);
	}
	else { pl_bgen = -1; pl_wait = cltime + OB_RETRY_SECS; }
	return TRUE;
};
float(string who) Players_Best =
{
	local float i;
	for (i = 0; i < pl_bn; i = i + 1)
		if (!strcmp(bufstr_get(pl_bid, i), who)) return pl_bticks[i];
	return 0;
};

// P1821: a slot's run into pl_r*. Yours from your stats; anyone else's from the server's *run
// (sv_timer.qc SV_RunKeyFrame). No key (a server before it): pl_rok FALSE, and lists show names only.
#define PLR_STAGE 1     // a stage-only run
#define PLR_STOP  2     // the clock is not moving; the key's value is its ticks
#define PLR_HELD  4     // spectating
float pl_rok, pl_rstate, pl_rtrack, pl_rseg, pl_rsegs, pl_rflags, pl_rticks;
void(float slot) Players_Run =
{
	local float f, tick;

	tick = Timer_Tick();
	pl_rok = FALSE;
	pl_rstate = TS_IDLE; pl_rtrack = pl_rseg = pl_rsegs = pl_rflags = pl_rticks = 0;
	if (slot == player_localnum)
	{
		pl_rok = TRUE;
		pl_rstate = getstatf(STAT_FS_TIMERSTATE);
		pl_rtrack = getstatf(STAT_FS_TIMERTRACK);
		pl_rseg = getstatf(STAT_FS_TIMERSEG);
		pl_rsegs = getstatf(STAT_FS_TIMERSEGS);
		f = getstatf(STAT_FS_TIMERFLAGS);
		if (f & (TF_FROZEN | TF_STOPPED)) pl_rflags = PLR_STOP;
		if (f & TF_RECORDING)       // RUNLEG = track * 100 + leg + 1; leg k > 0 is stage k alone
		if (getstatf(STAT_FS_RUNLEG) - 1 - pl_rtrack * 100 > 0)
			pl_rflags = pl_rflags | PLR_STAGE;
		if (spc_stat > 0) pl_rflags = pl_rflags | PLR_HELD;
		pl_rticks = Timer_Display(pl_rstate, getstatf(STAT_FS_TIMERTICKS), tick, f);
		return;
	}
	if (tokenize(getplayerkeyvalue(slot, "*run")) < 6)
		return;
	pl_rok = TRUE;
	pl_rstate = stof(argv(0));
	pl_rtrack = stof(argv(1));
	pl_rseg = stof(argv(2));
	pl_rsegs = stof(argv(3));
	pl_rflags = stof(argv(4));
	pl_rticks = stof(argv(5));
	if (pl_rstate == TS_RUNNING)
	if (!(pl_rflags & PLR_STOP))
		pl_rticks = max(0, time - pl_rticks) / tick;    // the origin, on the mapclock key's clock
};

// "stage 3/5", "stage 3" for a stage alone, "bonus 1", "start"; "" idle or unknown.
string() Players_StageText =
{
	local string b;

	if (!pl_rok) return "";
	if (pl_rflags & PLR_HELD) return "spectating";
	b = "";
	if (pl_rtrack > 0) b = sprintf("bonus %g", pl_rtrack);
	if (pl_rstate == TS_ARMED)
	{
		if (b != "") return strcat(b, " start");
		if (pl_rflags & PLR_STAGE) return sprintf("stage %g start", pl_rseg + 1);
		return "start";
	}
	if (pl_rstate == TS_FINISHED) return (b != "") ? strcat(b, " done") : "finished";
	if (pl_rstate != TS_RUNNING) return "";
	if (pl_rflags & PLR_STAGE) return strcat(b, (b != "") ? " " : "", sprintf("stage %g", pl_rseg + 1));
	if (pl_rsegs > 1) return strcat(b, (b != "") ? " " : "", sprintf("stage %g/%g", pl_rseg + 1, pl_rsegs));
	return (b != "") ? b : "running";
};

// The clock: m:ss.d while it runs (a client count, so tenths), the exact time once finished.
string() Players_TimeText =
{
	local float d, tick;

	if (!pl_rok) return "";
	tick = Timer_Tick();
	if (pl_rstate == TS_FINISHED) return Time_TickString(pl_rticks, tick);
	if (pl_rstate != TS_RUNNING) return "";
	d = floor(pl_rticks * tick * 10 + 0.0001);
	if (d >= 36000)
		return sprintf("%g:%02g:%02g.%g", floor(d / 36000), floor(d / 600) - floor(d / 36000) * 60,
		               floor(d / 10) - floor(d / 600) * 60, d - floor(d / 10) * 10);
	return sprintf("%g:%02g.%g", floor(d / 600), floor(d / 10) - floor(d / 600) * 60, d - floor(d / 10) * 10);
};

// P1590's colour a player wears, lifted when near black (was Scores_RoomRGB).
vector(float slot) Players_RGB =
{
	local vector c;

	c = (slot == player_localnum) ? Av_MyRGB() : Av_WornRGB(slot);
	if (c_x * 0.3 + c_y * 0.59 + c_z * 0.11 < 0.35)
		c = c + ('1 1 1' - c) * 0.45;           // a near-black colour stays readable
	return c;
};
void(float slot, string nm) Pl_VoiceToggle =
{
	// Engine's numeric selector is USERID, not slot or '#slot'.
	localcmd(sprintf("cl_voip_%s %.0f\n", stof(getplayerkeyvalue(slot, "vignored")) ? "unmute" : "mute",
	                 stof(getplayerkeyvalue(slot, "userid"))));
};
// Block: the saved chat silence by name, and for a Steam account the service's
// block (no friendship, adds or private messages). Voice is Mute's alone.
void(string nm, string ahash, float on) Pl_BlockToggle =
{
	if (Chat_Silenced(nm) == on) Chat_SilenceToggle(nm);
	if (ahash != "")
	if ((Friends_Relation(ahash) == 4) == on)
		Friends_Action(on ? "unblock" : "block", ahash);
};
// The widest of a button's labels, padded: every row's buttons line up.
float(string a, string b, string c, float sz) Pl_ButtonW =
{
	return ceil(max(stringwidth(a, TRUE, [sz, sz]), max(stringwidth(b, TRUE, [sz, sz]),
	            stringwidth(c, TRUE, [sz, sz]))) + sz * 2);
};
float(float evtype, float scanx) Players_Wheel =
{
	local float bit, d;
	if (scanx != K_MWHEELUP && scanx != K_MWHEELDOWN) return FALSE;
	bit = scanx == K_MWHEELUP ? 1 : 2;
	if (evtype == IE_KEYUP)
	{
		if (!(pl_wheel & bit)) return FALSE;
		pl_wheel = pl_wheel - bit;
		return TRUE;
	}
	_sui_mouse_move(_cursor_position, FALSE);
	if (sui_hover_index("pl_list") < 0) return FALSE;
	d = max(1, pl_rowh) * 3;
	if (scanx == K_MWHEELUP) d = 0 - d;
	pl_scroll_y = max(0, pl_scroll_y + d);
	pl_wheel = pl_wheel | bit;
	return TRUE;
};

// Block's lit state is rose, not the accent a lit chip wears.
float(string id, vector pos, vector sz, string label, float tsz, float on) Pl_BlockChip =
{
	local float hot;
	if (!on) return Profile_Chip(id, pos, sz, label, tsz, FALSE);
	sui_action_element(pos, sz, id, sui_noop);
	hot = sui_is_hovered(id);
	sui_style_box(pos, sz, sz_y * 0.5, SUI_THEME_BAD_BG, hot ? SUI_THEME_BAD : SUI_THEME_BAD_BG, 1);
	sui_text([pos_x + (sz_x - stringwidth(label, TRUE, [tsz, tsz])) * 0.5, pos_y + (sz_y - tsz) * 0.5],
	         [tsz, tsz], label, SUI_THEME_BAD, 1, 0);
	return sui_is_released(id);
};

// The room's main PBs (Players_Best), asked once a map and board generation. P1590: the
// TAB board's floating list asks too, so Players need not have been opened.
void() Players_Need =
{
	local string map;

	map = serverkey("map");
	if (strcmp(pl_bmap, map))
	{
		if (pl_bmap != "") strunzone(pl_bmap);
		pl_bmap = strzone(map);
		pl_bn = 0; pl_wait = 0; pl_bgen = -1;
	}
	if (pl_req && cltime - pl_sent > OB_DEADLINE) { pl_req = 0; pl_bgen = -1; pl_wait = cltime + OB_RETRY_SECS; }
	if (!pl_req && cltime >= pl_wait && pl_bgen != ob_gen && map != "")
	if (cvar_string("lobby_dir") != "")
	if (ui_consent_ver >= FS_TERMS_ONLINE || cvar("rec_terms") >= FS_TERMS_ONLINE)
	{
		pl_req = Online_NextReq(); pl_sent = cltime; pl_bgen = ob_gen;
		if (!uri_get(sprintf("%s/api/board?map=%s&track=0&leg=0&tier=%s&style=clean&limit=%g",
		             cvar_string("lobby_dir"), uri_escape(map), OB_TIER, OB_PAGE), pl_req))
			{ pl_req = 0; pl_bgen = -1; pl_wait = cltime + OB_RETRY_SECS; }
	}
};

void(vector p, vector sz, float tsz) Players_Draw =
{
	local float i, j, n, rowh, hint, x, y, by, best, vmute, blocked, rel, me, on, hot, av, bh, rw;
	local float wpro, wtp, wadd, wmute, wblk, ax, pbr, pingr, nx, nw, stw, stl;
	local float slots[PL_MAXSLOT];
	local vector lp, c;
	local string who, ahash, nm, s, rid;

	Players_Need();
	n = 0;
	for (i = 0; i < PL_MAXSLOT; i = i + 1)
		if (getplayerkeyvalue(i, "name") != "") { slots[n] = i; n = n + 1; }
	pl_rows = n;

	// Columns, right to left: the buttons, PB, ping, stage (P1821); the name takes the rest.
	// The small labels stop at 11 px, as the board's do (Scores_Type).
	hint = Font_Px(max(tsz * 0.75, 11));
	rowh = max(ceil(tsz * 2.9), tsz + hint + 14);
	pl_rowh = rowh;
	av = ceil(tsz * 2);
	bh = ceil(hint * 2.1);
	rw = sz_x - tsz;                    // the scrollbar's lane
	wpro = Pl_ButtonW("Profile", "", "", hint);
	wtp = Pl_ButtonW("Teleport", "", "", hint);
	wadd = Pl_ButtonW("Add friend", "Requested", "Accept", hint);
	wmute = Pl_ButtonW("Mute", "Unmute", "", hint);
	wblk = Pl_ButtonW("Block", "Unblock", "", hint);
	ax = rw - hint - wpro - wtp - wadd - wmute - wblk - 24;
	pbr = ax - hint * 2;
	pingr = pbr - ceil(stringwidth("88:88.888", TRUE, [hint, hint])) - hint * 2;
	nx = hint * 2 + av;
	stw = ceil(stringwidth("stage 88/88", TRUE, [hint, hint]));
	stl = pingr - ceil(stringwidth("999 ms", TRUE, [hint, hint])) - hint * 2 - stw;
	nw = max(0, stl - hint - nx);

	sui_text([p_x + nx, p_y], [hint, hint], sprintf("IN THIS SERVER: %g", n), SUI_THEME_MUTED, 1, 0);
	sui_text([p_x + pingr - stringwidth("PING", TRUE, [hint, hint]), p_y], [hint, hint], "PING", SUI_THEME_MUTED, 1, 0);
	sui_text([p_x + stl, p_y], [hint, hint], "STAGE", SUI_THEME_MUTED, 1, 0);
	sui_text([p_x + pbr - stringwidth("PB", TRUE, [hint, hint]), p_y], [hint, hint], "PB", SUI_THEME_MUTED, 1, 0);
	s = "Click a player to spectate";
	sui_text([p_x + rw - hint - stringwidth(s, TRUE, [hint, hint]), p_y], [hint, hint], s, SUI_THEME_MUTED, 1, 0);
	p_y = p_y + hint * 1.8; sz_y = sz_y - hint * 1.8;

	sui_list_view_begin("pl_list", p, sz, [rw, rowh], n, pl_scroll, [0, tsz]);
	lp = '0 0 0';
	for (i = sui_list_item(lp); i > -1; i = sui_list_item(lp))
	{
		j = slots[i];
		nm = getplayerkeyvalue(j, "name");
		ahash = getplayerkeyvalue(j, "*ahash");
		who = ahash;
		if (who == "") who = getplayerkeyvalue(j, "*phash");
		me = (j == player_localnum);
		on = (spc_stat == j + 1);
		rid = sprintf("pl_spec%g", j);
		hot = FALSE;
		if (!me)
		{
			sui_action_element(lp, [rw, rowh - 4], rid, sui_noop);
			hot = (sui_hover_index(rid) >= 0);        // under its buttons too
			if (sui_is_released(rid))
			if (rec_sb_open) pl_specpick = j + 1;
		}
		c = SUI_THEME_WELL;
		if (hot) c = SUI_THEME_HOVER;
		if (on) c = SUI_THEME_SELECTED;
		sui_roundbox(lp, [rw, rowh - 4], hint * 0.6, c, (on || hot) ? 1 : 0.85);
		if (on)
			sui_roundbox(lp + [0, hint * 0.6], [3, rowh - 4 - hint * 1.2], 1.5, SUI_THEME_ACCENT, 1);
		Profile_Face([lp_x + hint, lp_y + floor((rowh - 4 - av) * 0.5)], av, who, who != "", nm);

		// The name, and under it what this player is to you.
		y = lp_y + floor((rowh - 4 - tsz - hint - 3) * 0.5);
		sui_text([lp_x + nx, y], [tsz, tsz], Chat_Fit(nm, nw, tsz), SUI_THEME_TEXT, 1, 0);
		rel = (ahash != "") ? Friends_Relation(ahash) : 0;
		vmute = stof(getplayerkeyvalue(j, "vignored"));
		blocked = (Chat_Silenced(nm) || rel == 4);
		s = "";
		c = SUI_THEME_MUTED;
		if (me) { s = "You"; c = SUI_THEME_ACCENT; }
		else if (on) { s = "Spectating"; c = SUI_THEME_ACCENT; }
		else if (sui_is_hovered(rid)) { s = "Click to spectate"; c = SUI_THEME_ACCENT; }
		else if (blocked) { s = "Blocked"; c = SUI_THEME_BAD; }
		else if (vmute) s = "Voice muted";
		if (s != "")
			sui_text([lp_x + nx, y + tsz + 3], [hint, hint], Chat_Fit(s, nw, hint), c, 1, 0);

		y = lp_y + floor((rowh - 4 - hint) * 0.5);
		s = strcat(getplayerkeyvalue(j, "ping"), " ms");
		sui_text([lp_x + pingr - stringwidth(s, TRUE, [hint, hint]), y], [hint, hint], s, SUI_THEME_DIM, 1, 0);
		Players_Run(j);
		s = Players_StageText();
		if (s != "")
			sui_text([lp_x + stl, y], [hint, hint], Chat_Fit(s, stw + hint, hint), SUI_THEME_TEXT, 1, 0);
		best = Players_Best(getplayerkeyvalue(j, "*phash"));
		s = (best > 0) ? Time_TickString(best, Timer_Tick()) : "-";
		sui_text([lp_x + pbr - stringwidth(s, TRUE, [hint, hint]), y], [hint, hint], s,
		         (best > 0) ? SUI_THEME_TEXT : SUI_THEME_MUTED, 1, 0);

		x = lp_x + ax;
		by = lp_y + floor((rowh - 4 - bh) * 0.5);
		if (Profile_Chip(sprintf("pl_name%g", j), [x, by], [wpro, bh], "Profile", hint, FALSE))
		if (rec_sb_open && who != "")
		{
			if (pl_profilepick != "") strunzone(pl_profilepick);
			pl_profilepick = strzone(me ? "me" : who);
		}
		if (me) continue;
		x = x + wpro + 6;
		// Patch 797: the server's setpos to them (SV_TpPlayer).
		if (Profile_Chip(sprintf("pl_tp%g", j), [x, by], [wtp, bh], "Teleport", hint, FALSE))
		if (rec_sb_open) pl_tppick = j + 1;
		x = x + wtp + 6;
		if (rel == 3)
			sui_text([x + (wadd - stringwidth("Friend", TRUE, [hint, hint])) * 0.5, by + (bh - hint) * 0.5],
			         [hint, hint], "Friend", SUI_THEME_GOOD, 1, 0);
		else if (ahash != "" && rel != 4)
			if (Profile_Chip(sprintf("pl_add%g", j), [x, by], [wadd, bh], Friends_AddLabel(ahash), hint, rel == 1))
			if (rec_sb_open) Friends_Add(ahash);
		x = x + wadd + 6;
		if (Profile_Chip(sprintf("pl_voice%g", j), [x, by], [wmute, bh], vmute ? "Unmute" : "Mute", hint, vmute))
		if (rec_sb_open) Pl_VoiceToggle(j, nm);
		x = x + wmute + 6;
		if (Pl_BlockChip(sprintf("pl_chat%g", j), [x, by], [wblk, bh], blocked ? "Unblock" : "Block", hint, blocked))
		if (rec_sb_open) Pl_BlockToggle(nm, ahash, blocked);
	}
	sui_list_view_end();
};

/*
  P1821 (Lex, 25 Nov): the server's players on the HUD -- plain name, stage, live run time --
  hud_edit's "Players". Right-anchored (HEA_RT) under the map info; you first, then slot order,
  so rows do not jump. Only with someone else here, unless hud_players_solo or the editor is up.
*/
void(vector scr) Players_DrawHud =
{
	local float i, k, n, cap, sz, lh, pad, nw, sw, tw, bw, x, y, showst, showt;
	local float slots[PL_MAXSLOT];
	local string nm, s;
	local vector p, c;

	if (!cvar("hud_players") || rec_wt_on)
		return;
	n = 1;
	slots[0] = player_localnum;
	for (i = 0; i < PL_MAXSLOT; i = i + 1)
		if (i != player_localnum)
		if (getplayerkeyvalue(i, "name") != "")
			{ slots[n] = i; n = n + 1; }
	if (n < 2 && !ui_he_open && !cvar("hud_players_solo"))
		return;
	cap = bound(2, cvar("hud_players_rows"), 32);
	showst = cvar("hud_players_stage");
	showt = cvar("hud_players_time");

	Font_Set(ui_font_ui);
	sz = Font_Px(HUD_Size("hud_players_size", 8 * ui_cv_scale));
	lh = ceil(sz * 1.35);
	pad = ceil(sz * 0.5);
	// Measure, then draw: the box goes under the text. Time and stage keep a fixed lane.
	nw = stringwidth("Players", TRUE, [sz, sz]);
	sw = showst ? stringwidth("stage 88/88", TRUE, [sz, sz]) : 0;
	tw = showt ? stringwidth("88:88.888", TRUE, [sz, sz]) : 0;
	for (k = 0; k < min(n, cap); k = k + 1)
	{
		nw = max(nw, stringwidth(strdecolorize(getplayerkeyvalue(slots[k], "name")), TRUE, [sz, sz]));
		Players_Run(slots[k]);
		if (showst) sw = max(sw, stringwidth(Players_StageText(), TRUE, [sz, sz]));
		if (showt) tw = max(tw, stringwidth(Players_TimeText(), TRUE, [sz, sz]));
	}
	nw = min(nw, sz * 11);
	bw = pad * 2 + nw + (showst ? sz + sw : 0) + (showt ? sz + tw : 0);
	k = min(n, cap);
	p = [scr_x * cvar("hud_players_x"), scr_y * cvar("hud_players_y"), 0];
	drawfill([p_x - bw, p_y, 0], [bw, lh * (k + 1) + pad, 0], '0 0 0', 0.45, 0);
	x = p_x - bw + pad;
	y = p_y + pad * 0.5;
	HUD_Text([x, y, 0], sprintf("Players %g", n), sz, '0.55 0.60 0.68', 0.95);
	for (i = 0; i < k; i = i + 1)
	{
		y = y + lh;
		if ((i == cap - 1) && (n > cap))
		{
			HUD_Text([x, y, 0], sprintf("+%g more", n - cap + 1), sz, '0.55 0.60 0.68', 0.95);
			break;
		}
		nm = Chat_Fit(strdecolorize(getplayerkeyvalue(slots[i], "name")), nw, sz);
		c = Players_RGB(slots[i]);
		HUD_Text([x, y, 0], nm, sz, c, 0.95);
		Players_Run(slots[i]);
		if (showst)
		{
			s = Players_StageText();
			if (s != "")
				HUD_Text([x + nw + sz, y, 0], s, sz, '0.70 0.75 0.84', 0.95);
		}
		if (showt)
		{
			s = Players_TimeText();
			c = '1 1 1';
			if (pl_rstate == TS_FINISHED) c = '0.45 1.00 0.45';
			else if (pl_rflags & PLR_STOP) c = '0.55 0.58 0.62';
			if (s != "")
				HUD_TextR([p_x - pad, y, 0], s, sz, c, 0.95);
		}
	}
	Font_Reset();
	HUD_Rect("players", [p_x - bw, p_y, 0], [bw, lh * (k + 1) + pad, 0], p);
};

// `players_status`: each slot's *run key and what the lists draw from it (P1821).
void() Players_Status =
{
	local float i;

	for (i = 0; i < PL_MAXSLOT; i = i + 1)
	if (getplayerkeyvalue(i, "name") != "")
	{
		Players_Run(i);
		print(sprintf("players: %g%s \"%s\" run \"%s\" ok %g stage \"%s\" time \"%s\"\n", i,
		              (i == player_localnum) ? " (you)" : "", strdecolorize(getplayerkeyvalue(i, "name")),
		              getplayerkeyvalue(i, "*run"), pl_rok, Players_StageText(), Players_TimeText()));
	}
};

void() Players_RegisterCvars =
{
	pl_bid = buf_create();
	registercommand("players_status");
	registercvar("hud_players", "1", CVAR_ARCHIVE);         // P1821
	registercvar("hud_players_x", "0.9917", CVAR_ARCHIVE);
	registercvar("hud_players_y", "0.24", CVAR_ARCHIVE);
	registercvar("hud_players_size", "0", CVAR_ARCHIVE);
	registercvar("hud_players_rows", "8", CVAR_ARCHIVE);
	registercvar("hud_players_stage", "1", CVAR_ARCHIVE);
	registercvar("hud_players_time", "1", CVAR_ARCHIVE);
	registercvar("hud_players_solo", "0", CVAR_ARCHIVE);
};
