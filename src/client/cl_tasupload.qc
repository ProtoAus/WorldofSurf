/*
  P1696: upload a TAS run from the game to play.proto.bar/tasup (surfd/tasupd.py's game route), the TAS menu's Upload
  tab. Upload asks the service for a code bound to the file's SHA-256; Send, on a real press only, signs
  TASUp_Signed (the code, the purpose and the file) with the linked key -- acct_sign kind -6, as zone publishing signs --
  and posts the proof and the file in one body. The service checks the run as it checks the web form's.
  The list is the local game's own word (SV_TASUpList: runs it finished, by their SHA-256, kept in data/tasproj/ where
  client code cannot write), so a file a server's csprogs put in data/runs/ is never offered as yours (attack review 2).
  P1797 (Lex, 24 Nov: "list all tas runs in your game"): every other TAS run in data/runs/ follows, any map, marked as
  found in the folder (sha "-": no claim it was finished here); Open folder shows data/runs/ in the file manager.
*/
#ifndef TUP_BASE   // a test build only (fteqcc -DTUP_BASE): a server must never choose where a proof goes
#define TUP_BASE "https://play.proto.bar/tasup/"
#endif
#define TUP_MAX 64                                  // SV_TASUpList's TAS_UPSHOW
#define TUP_PAGE 8
#define TUP_BYTES 8388608                           // tasupd.MAX_REC
string tup_p[TUP_MAX], tup_l[TUP_MAX], tup_s[TUP_MAX];   // path, label, the SHA-256 the game saved it with
string tupe_p[TUP_MAX], tupe_s[TUP_MAX];                  // the list arriving (TASUp_ListEvent)
float tup_n, tup_at, tupe_n, tup_page;
string tup_key;                 // the map the list was asked for
float tup_state;                // 0 the list, 1 asking for a code, 2 confirm, 3 sending, 4 answered
float tup_req, tup_until, tup_armed, tup_size;
float tup_pend, tup_pendt;       // `tas upload N` waiting for the list (row N-1, or -2: `tas upload`, to print it) until tup_pendt
string tup_path, tup_label, tup_nonce, tup_sha, tup_note;
string tup_short;               // P1712: the answer in a few words, for the offer box
var float tup_mode = 2;         // P1712: what a new best does (the local game's word: SV_TASUpOffer)
string tup_tok;                 // P1712: the local game's token that raising it needs (SV_TASUpOfferTok)
// P1712's offer box: up; sends itself; countdown left (runs only while seen, at state 2); last frame; closes; list due
#define TUPB_SECS 12
#define TUPB_Q 4
float tupb_box, tupb_auto, tupb_left, tupb_seen, tupb_end, tupb_want, tupb_qn;
float tupb_asking, tupb_mine;   // TASUp_Ask is the box's (set only by TASUp_OfferList); the flow is the box's since
string tupb_path, tupb_why;     // the run offered; why it fell back to asking
string tupb_q[TUPB_Q];          // bests that came while one was on its way, one a course (the newest)

string(string old, string value) TASUp_Keep =
{
	local string copy;
	copy = strzone(value);
	if (old != "") strunzone(old);
	return copy;
};
// a server's words as one line of plain text
string(string s) TASUp_Clean =
{
	s = strreplace("^", "", strreplace("\n", " ", strreplace("\r", " ", strreplace("\t", " ", s))));
	return (strlen(s) > 240) ? strcat(substring(s, 0, 237), "...") : s;
};
float(string s, float n) TASUp_Hex =
{
	local float i, c;
	if (strlen(s) != n) return FALSE;
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (!((c >= 48 && c <= 57) || (c >= 97 && c <= 102))) return FALSE;
	}
	return TRUE;
};
// tasupd.game_nonce: what the key signs for this file under the service's code
string(string nonce, string sha) TASUp_Signed =
{
	return substring(strtolower(digest_hex("SHA256", strcat("ftesurf-tasup ", nonce, " ", sha))), 0, 32);
};
string(float track) TASUp_Course = { return (track > 0) ? sprintf("Bonus %g", track) : "Main"; };

// P1797: a listed run's header (TASJargon_Head reads this map's only): map, track, leg, the ticks' rate; a few lines a
// file, once while it stays listed
#define TUP_HC 64
string tup_hcp[TUP_HC], tup_hcm[TUP_HC];
float tup_hct[TUP_HC], tup_hcl[TUP_HC], tup_hcr[TUP_HC], tup_hcn;
float(string p) TASUp_Head =
{
	local float i, h, fh, c, mtr;
	local string l, line;
	for (i = 0; i < tup_hcn; i = i + 1) if (!strcmp(tup_hcp[i], p)) return i;
	fh = fopen(p, FILE_READ);
	if (fh < 0) return -1;
	if (tup_hcn >= TUP_HC)
	{
		strunzone(tup_hcp[0]); strunzone(tup_hcm[0]);
		for (i = 1; i < TUP_HC; i = i + 1)
		{
			tup_hcp[i - 1] = tup_hcp[i]; tup_hcm[i - 1] = tup_hcm[i];
			tup_hct[i - 1] = tup_hct[i]; tup_hcl[i - 1] = tup_hcl[i]; tup_hcr[i - 1] = tup_hcr[i];
		}
		tup_hcn = TUP_HC - 1;
	}
	h = tup_hcn; tup_hcn = tup_hcn + 1;
	tup_hct[h] = tup_hcl[h] = -1; tup_hcr[h] = 0.015; mtr = FALSE; line = "";
	for (i = 0; i < 48; i = i + 1)
	{
		l = fgets(fh);
		if (l == "") continue;
		c = tokenize(l);
		if (argv(0) == "begin" || (c >= 7 && FS_TASNumber(argv(0)))) break;
		if (argv(0) == "map" && c >= 2) line = strtolower(argv(1));
		else if (argv(0) == "track" && c == 2) tup_hct[h] = stof(argv(1));
		else if (argv(0) == "leg" && c == 2) tup_hcl[h] = stof(argv(1));
		else if (argv(0) == "tickrate" && c == 2 && stof(argv(1)) > 0) { if (!mtr) tup_hcr[h] = stof(argv(1)); }
		else if (argv(0) == "movetickrate" && c == 2 && stof(argv(1)) > 0) { tup_hcr[h] = stof(argv(1)); mtr = TRUE; }
	}
	fclose(fh);
	if (line == "") { line = substring(p, 10, -1); line = substring(line, 0, max(0, strstrofs(line, "/"))); }   // data/runs/<map>/
	tup_hcp[h] = strzone(p); tup_hcm[h] = strzone(line);
	return h;
};
// a run of a whole course (path, sha): one the local game says it finished (sha its SHA-256), or one found in the folder
// (sha "-", P1797); offered while it is still there
void(string p, string sha) TASUp_Add =
{
	local float i, hd, t, found;
	local string b, lab;
	found = !strcmp(sha, "-");
	if (tup_n >= TUP_MAX || !TASJargon_Safe(p) || !(found || TASUp_Hex(sha, 64))) return;
	if (substring(p, 0, 10) != "data/runs/" || FS_TagFromName(FS_NameTag(TASJargon_Base(p))) != RT_TAS)   // Base drops .rec
		return;
	for (i = 0; i < tup_n; i = i + 1) if (!strcmp(tup_p[i], p)) return;
	hd = TASUp_Head(p);
	if (hd < 0) return;            // nested: QC's || reads tup_hcl[-1] too (flow review 2)
	if (tup_hcm[hd] == "" || tup_hcl[hd] > 0) return;
	b = TASJargon_Base(p);
	t = rint(stof(substring(b, 0, strstrofs(b, "_"))) * tup_hcr[hd] * 100) / 100;
	lab = sprintf("%s  %s", TASUp_Course(max(0, tup_hct[hd])), (t >= 60)
		? sprintf("%g:%s%.2f", floor(t / 60), (t - 60 * floor(t / 60) < 10) ? "0" : "", t - 60 * floor(t / 60)) : sprintf("%.2fs", t));
	if (strcasecmp(tup_hcm[hd], zone_mapname)) lab = strcat(tup_hcm[hd], "  ", lab);
	tup_p[tup_n] = strzone(p); tup_s[tup_n] = strzone(found ? "" : sha);
	tup_l[tup_n] = strzone(strcat(lab, found ? "  TAS run (folder)" : "  TAS run"));
	tup_n = tup_n + 1;
};
void() TASUp_Pending;
void() TASUp_OfferList;
void(string why) TASUp_BoxKeep;
void(string p) TASUp_Unqueue;
float() TASUp_BoxOwns;
// SV_TASUpList's events: index, count, then the run's sha and path; the list is replaced once the last arrives
void() TASUp_ListEvent =
{
	local float i, n, k, m;
	local string sha, path, tk;
	i = readbyte(); n = readbyte(); m = readbyte(); tk = readstring();
	sha = path = "";
	if (n) { sha = readstring(); path = readstring(); }
	if (!isserver()) return;        // only the game this process hosts says what it finished
	tup_mode = m; tup_tok = TASUp_Keep(tup_tok, TASUp_Hex(tk, 16) ? tk : "");   // it goes into a command line
	if (m < 2) tupb_auto = FALSE;   // P1712: turned down (the tab, or `cmd tas offer` -- SV_TASUpSetOffer resends this)
	if (m == 0)
	{
		while (tupb_qn > 0) TASUp_Unqueue(tupb_q[0]);
		tupb_want = 0;
		if (TASUp_BoxOwns() && (tup_state == 1 || tup_state == 2)) TASUp_BoxKeep("Off");
	}
	if (i == 0) { for (k = 0; k < tupe_n; k = k + 1) { strunzone(tupe_p[k]); strunzone(tupe_s[k]); } tupe_n = 0; }
	if (n && i == tupe_n && tupe_n < TUP_MAX) { tupe_p[tupe_n] = strzone(path); tupe_s[tupe_n] = strzone(sha); tupe_n = tupe_n + 1; }
	if (i < n - 1) return;
	for (k = 0; k < tup_n; k = k + 1) { strunzone(tup_p[k]); strunzone(tup_l[k]); strunzone(tup_s[k]); }
	tup_n = 0;
	for (k = 0; k < tupe_n; k = k + 1) TASUp_Add(tupe_p[k], tupe_s[k]);
	if (tup_pendt) TASUp_Pending();         // the console verb, answered by this list (flow review 3: it read the last one)
	if (tupb_want) TASUp_OfferList();
};
// asks the local game for its list: when the map changes, and every 3 s while the tab is drawn
void() TASUp_List =
{
	local string key;
	if (!isserver()) return;
	key = zone_mapname;
	if (key == tup_key && cltime < tup_at) return;
	tup_at = cltime + 3;
	if (key != tup_key) { tup_key = TASUp_Keep(tup_key, key); }
	localcmd("cmd tas uploads\n");
};

void(string note) TASUp_Answer =
{
	tup_state = 4; tup_req = 0;
	tup_note = TASUp_Keep(tup_note, strcat(strtoupper(substring(note, 0, 1)), substring(note, 1, -1)));
	tup_short = TASUp_Keep(tup_short, "not uploaded: see the console");
	if (tupb_box) tupb_end = cltime + 8;
	print(sprintf("tas upload: %s\n", note));
};
// the file as it is now, or "" (missing, too big, or a NUL in it)
string(string p) TASUp_Read =
{
	local float fh;
	local string s;
	tup_size = 0;
	fh = fopen(p, FILE_READNL);
	if (fh < 0) return "";
	s = fgets(fh);
	fclose(fh);
	tup_size = strlen(s);
	return (tup_size > TUP_BYTES) ? "" : s;
};

// Upload's click: the service's code for this file (a draw-time click is enough; only Send signs)
void(float i) TASUp_Ask =
{
	local string body;
	if (i < 0 || i >= tup_n || tup_state == 1 || tup_state == 3) return;
	tupb_mine = tupb_asking;                       // P1712: any other Upload (the tab, `tas upload N`) takes the flow
	tup_label = TASUp_Keep(tup_label, tup_l[i]);   // first: a refusal below shows this run's name (flow review 2)
	tup_path = TASUp_Keep(tup_path, tup_p[i]);     // and the offer box sees whose flow this is (P1712)
	if (!TASShare_Allowed()) { TASUp_Answer("accept the online terms in the main menu first"); return; }
	if (!isserver()) { TASUp_Answer("upload from a game you host, not while on a server"); return; }
	if (!Zone_LooseOwn(tup_p[i])) { TASUp_Answer("that file is not your game's own copy (a package has it); nothing was sent"); return; }
	body = TASUp_Read(tup_p[i]);
	if (body == "") { TASUp_Answer((tup_size > TUP_BYTES) ? "that file is over 8 MB" : "that file could not be read"); return; }
	tup_sha = TASUp_Keep(tup_sha, strtolower(digest_hex("SHA256", body)));
	if (tup_s[i] != "")   // P1797: a folder run makes no claim to check
	if (strcmp(tup_sha, tup_s[i])) { TASUp_Answer("that file is not the run your game saved (it changed since); nothing was sent"); return; }
	tup_req = Online_NextReq();
	if (!uri_post(strcat(TUP_BASE, "api/game/challenge"), tup_req, "application/json", sprintf("{\"sha\":\"%s\"}", tup_sha)))
	{
		TASUp_Answer("the upload service could not be reached; nothing was sent"); return;
	}
	tup_state = 1; tup_until = gettime(0) + 20;
	print(sprintf("tas upload: asked for a code for %s (%g bytes)\n", tup_path, tup_size));
};

// Send: called from TASUI_Input on a device's press over the button (or F6 on the offer), the one moment the engine signs;
// byitself: the offer's countdown ran out under tas_upload_offer 2 -- signed unkeyed, acct_sign kind -7 (P1712)
void(float byitself) TASUp_Send =
{
	local string body, p, env;
	if (tup_state != 2) return;
	if (!byitself && (!cl_input_real || gettime(0) < tup_armed)) return;     // no press carried in from the Upload click
	if (!isserver()) { TASUp_Answer("upload from a game you host, not while on a server; nothing was sent"); return; }
	body = TASUp_Read(tup_path);
	if (body == "" || strcmp(strtolower(digest_hex("SHA256", body)), tup_sha))
	{
		TASUp_Answer("the file changed after Upload: press Upload again; nothing was sent"); return;
	}
	p = acct_sign(TASUp_Signed(tup_nonce, tup_sha), byitself ? -7 : -6);
	if (p == "" || tokenize(p) != 5)
	{
		if (byitself)
		{	// the box asks instead: F6 signs keyed
			print("tas upload: not sent by itself (it needs a linked Steam account and the latest game): F6 sends it\n");
			tupb_auto = FALSE; tupb_left = TUPB_SECS; tupb_why = TASUp_Keep(tupb_why, "could not send by itself: F6 does");
			return;
		}
		TASUp_Answer("the game would not sign the upload: it needs a linked Steam account (Settings), the latest engine and a "
			"real click; nothing was sent");
		return;
	}
	// tasupd.GAME_HEAD: the proof is checked before the file is read; then the bytes the code was asked for, raw
	env = strcat(byitself ? "FTESURF-TASUP 2" : "FTESURF-TASUP 1", "\nnonce ", tup_nonce, "\nsha ", tup_sha, "\npub ", argv(0));   // 2: kind -7
	env = strcat(env, "\nsig ", argv(2));
	env = strcat(env, "\ngame ", argv(4), "\n", body);
	tup_req = Online_NextReq();
	if (!uri_post(strcat(TUP_BASE, "upload"), tup_req, "application/x-ftesurf-tasup", env))
	{
		TASUp_Answer("the upload service could not be reached; nothing was sent"); return;
	}
	tup_state = 3; tup_until = gettime(0) + 180;
	print(sprintf("tas upload: sent %s (%g bytes), %s\n", tup_path, tup_size, byitself ? "by itself when the offer ran out"
		: "signed under a real press"));
};
// P1797: this map's run folder if it has a listed run, else data/runs (engine sys_openfolder, on the press)
float(string gamepath) sys_openfolder = #0:sys_openfolder;
void() TASUp_OpenFolder =
{
	local float i;
	local string f, pre;
	f = "data/runs";
	pre = strcat("data/runs/", strtolower(zone_mapname), "/");
	for (i = 0; i < tup_n; i = i + 1) if (!strcmp(substring(tup_p[i], 0, strlen(pre)), pre)) { f = substring(pre, 0, strlen(pre) - 1); break; }
	if (checkbuiltin(sys_openfolder))
	{
		if (sys_openfolder(f)) return;          // the engine prints the folder
		if (f != "data/runs") if (sys_openfolder("data/runs")) return;   // a refused call spends nothing (odd map names)
	}
	print(sprintf("tas upload: your TAS runs are in the game folder's %s (the file manager opens only in a game you host)\n", f));
};
void() TASUp_Press =
{
	if (tup_state == 2 && sui_is_hovered("tup_send")) TASUp_Send(FALSE);
	if (tup_state == 0 && sui_is_hovered("tup_folder")) TASUp_OpenFolder();
};

float(float reqid, float code, string body) TASUp_Reply =
{
	local int root, rs, it;
	local float ok, i, n, t;
	local string s, why;
	if (!tup_req || reqid != tup_req) return FALSE;
	tup_req = 0;
	if (code == 504 && tup_state == 3)    // nginx gave up waiting (150 s): the check may have finished and kept it
		{ TASUp_Answer("no answer in time: the run may still have arrived -- look at play.proto.bar/tasup before sending it again"); return TRUE; }
	if (code) { TASUp_Answer(sprintf("play.proto.bar could not be reached (%g); try again in a minute", code)); return TRUE; }
	root = json_parse(body);
	if (root <= 0i) { TASUp_Answer("play.proto.bar answered something unreadable; try again in a minute"); return TRUE; }
	ok = json_get_float(json_find_object_child(root, "ok"));
	why = TASUp_Clean(json_get_string(json_find_object_child(root, "error")));
	if (tup_state == 1)
	{
		s = json_get_string(json_find_object_child(root, "nonce"));
		if (ok == 1 && TASUp_Hex(s, 32) && !strcmp(json_get_string(json_find_object_child(root, "sha")), tup_sha))
		{
			tup_nonce = TASUp_Keep(tup_nonce, s);
			tup_state = 2;      // the offer's code came by itself, not with a click
			tup_armed = gettime(0) + ((tupb_box && tupb_mine) ? 0 : 0.5);
			print(sprintf("tas upload: ready to send %s: click Send\n", tup_path));
		}
		else TASUp_Answer(strcat("not uploaded: ", (why != "") ? why : "the service did not give a code"));
	}
	else if (tup_state == 3)
	{
		rs = json_find_object_child(root, "reasons");
		s = "";
		n = (json_get_value_type(rs) == 3i) ? min(3, json_get_length(rs)) : 0;
		for (i = 0; i < n; i = i + 1)
		{
			it = json_get_child_at_index(rs, (int)i);
			t = json_get_float(json_find_object_child(it, "t"));
			s = strcat(s, (s != "") ? "; " : "", (json_get_value_type(json_find_object_child(it, "t")) == 1i) ? sprintf("at %.3fs ", t) : "",
				TASUp_Clean(json_get_string(json_find_object_child(it, "what"))));
		}
		if (ok == 1)
		{
			t = json_get_float(json_find_object_child(root, "id"));
			if (json_get_string(json_find_object_child(root, "state")) == "shown")
			{	// P1716: shown without review when the check could not see everything, or a new record
				TASUp_Answer(sprintf("on the TAS board, %s: run %g, %.3fs. play.proto.bar/tasup/run/%g",
					(json_get_float(json_find_object_child(root, "unchecked")) == 1) ? "not fully checked" : "physics checked",
					t, json_get_float(json_find_object_child(root, "time")), t));
				tup_short = TASUp_Keep(tup_short, sprintf("on the TAS board: run %g", t));
			}
			else
			{
				TASUp_Answer(sprintf("uploaded, waiting for review: run %g (%s). play.proto.bar/tasup/run/%g", t, s, t));
				tup_short = TASUp_Keep(tup_short, sprintf("uploaded: run %g waits for review", t));
			}
		}
		else TASUp_Answer(strcat("not uploaded: ", (why != "") ? why : "the service refused it", (s != "") ? strcat(" -- ", s) : ""));
	}
	json_free(root);
	return TRUE;
};

void() TASUp_Pump =
{
	if ((tup_state == 1 || tup_state == 3) && gettime(0) > tup_until)
		TASUp_Answer((tup_state == 1) ? "play.proto.bar did not answer; try again in a minute"
			: "no answer yet: the run may still have arrived -- look at play.proto.bar/tasup before sending it again");
	if (tup_state == 2 && gettime(0) > tup_armed + 590) TASUp_Answer("the confirmation expired: press Upload again");   // tasupd.CHALLENGE_TTL
};

// P1712: what a new TAS best does -- 2 the box, then it sends itself; 1 the box asks; 0 nothing (SV_TASUpOffer)
vector(vector at, float width, float tsz, float hint, float row) TASUp_OfferChips =
{
	local float i, v, lw, w;
	local string lab;
	if (!isserver()) return at;
	lab = "After a new best:";
	lw = stringwidth(lab, TRUE, [hint, hint]) + 8;
	sui_text(at + [0, (row - hint) * 0.5, 0], [hint, hint], lab, SUI_THEME_DIM, 1, 0);
	w = (width - lw - 8) / 3;
	for (i = 0; i < 3; i = i + 1)
		if (Profile_Chip(sprintf("tup_offer%g", i), at + [lw + i * (w + 4), 0, 0], [w, row, 0],
		                 (i == 0) ? "Auto-upload" : (i == 1) ? "Ask" : "Off", tsz, tup_mode == 2 - i))
		{
			v = 2 - i;
			localcmd(sprintf("cmd tas offer %g %s\n", v, tup_tok));
			tup_mode = v; tup_at = 0;
			if (v == 0) while (tupb_qn > 0) TASUp_Unqueue(tupb_q[0]);   // Off: nothing waiting is offered either
			if (tupb_box && v < 2) tupb_auto = FALSE;              // an offer already up follows it
			if (TASUp_BoxOwns() && v == 0 && (tup_state == 1 || tup_state == 2)) TASUp_BoxKeep("Off");
		}
	at_y = at_y + row + 6;
	return at;
};

void(vector at, float width, float tsz, float hint, float row) TASUp_Draw =
{
	local float i, pages;
	local vector chip, half;
	TASUp_Pump();
	at_y = ZonePub_Wrap(at, width, hint, "Send a finished TAS run to the TAS board at play.proto.bar/tasup, as your "
		"Steam account. It is checked against the game's movement physics: runs that check out are listed there with their "
		"file; a new record, or anything the check cannot clear, waits for review.", SUI_THEME_DIM, TRUE) + hint;
	at = TASUp_OfferChips(at, width, tsz, hint, row);
	half = [(width - 6) / 2, row, 0];
	TASUp_List();               // in every state: the mode the chips show comes with it (P1712)
	if (tup_state == 0)
	{
		if (!isserver())
		{
			ZonePub_Wrap(at, width, tsz, "Upload from a game you host: TAS runs are made there.", SUI_THEME_TEXT, TRUE);
			return;
		}
		// P1797: Open folder (acts on the press: TASUp_Press), then the page's runs
		chip = [tsz * 7, row, 0];
		Profile_Chip("tup_folder", at, [tsz * 9, row, 0], "Open folder", tsz, FALSE);
		pages = max(1, ceil(tup_n / TUP_PAGE));
		tup_page = bound(0, tup_page, pages - 1);
		if (pages > 1)
		{
			if (Profile_Chip("tup_prev", at + [width - chip_x * 2 - 4, 0, 0], chip, "Prev", tsz, FALSE)) tup_page = max(0, tup_page - 1);
			if (Profile_Chip("tup_next", at + [width - chip_x, 0, 0], chip, "Next", tsz, FALSE)) tup_page = min(pages - 1, tup_page + 1);
			sui_text(at + [tsz * 9 + 8, (row - hint) * 0.5, 0], [hint, hint], sprintf("%g runs, page %g of %g", tup_n, tup_page + 1, pages),
				SUI_THEME_DIM, 1, 0);
		}
		at_y = at_y + row + 6;
		if (!tup_n)
		{
			ZonePub_Wrap(at, width, tsz, "No TAS run in this game's data/runs yet. Finish one with Jargon or Manual TAS and it "
				"shows here; a bot's .rec placed in data/runs/<map>/main (or bonus_N) shows too.", SUI_THEME_TEXT, TRUE);
			return;
		}
		for (i = tup_page * TUP_PAGE; i < min(tup_n, (tup_page + 1) * TUP_PAGE); i = i + 1)
		{
			sui_text(at + [0, (row - tsz) * 0.5, 0], [tsz, tsz], tup_l[i], SUI_THEME_TEXT, 1, 0);
			if (Profile_Chip(sprintf("tup_go%g", i), at + [width - chip_x, 0, 0], chip, "Upload", tsz, FALSE)) TASUp_Ask(i);
			at_y = at_y + row + 4;
		}
		return;
	}
	sui_text(at, [tsz, tsz], tup_label, SUI_THEME_TEXT, 1, 0); at_y = at_y + row;
	if (tup_state == 1) sui_text(at, [hint, hint], "Asking play.proto.bar for a confirmation...", SUI_THEME_DIM, 1, 0);
	else if (tup_state == 2)
	{
		at_y = ZonePub_Wrap(at, width, hint, sprintf("Send this run (%g KB) to the TAS board as your Steam account? The game signs "
			"it with your linked account when you click Send.", ceil(tup_size / 1024)), SUI_THEME_TEXT, TRUE) + hint;
		Profile_Chip("tup_send", at, half, "Send", tsz, gettime(0) >= tup_armed);   // the press acts (TASUp_Press), not this
		if (Profile_Chip("tup_back", at + [half_x + 6, 0, 0], half, "Back", tsz, FALSE)) { tup_state = 0; tup_req = 0; }
	}
	else if (tup_state == 3) sui_text(at, [hint, hint], "Sending and checking... a long run takes a few seconds.", SUI_THEME_DIM, 1, 0);
	else
	{
		at_y = ZonePub_Wrap(at, width, hint, tup_note, SUI_THEME_TEXT, TRUE) + hint;
		if (Profile_Chip("tup_list", at, half, "Back to the list", tsz, FALSE)) { tup_state = 0; tup_at = 0; }
	}
};

// `tas upload` lists, `tas upload N` asks for row N's code and opens the tab (Send is a click), `tas upload status`.
// The list comes from the local game (TASUp_ListEvent): the verb acts when it arrives.
void() TASUp_Pending =
{
	local float i;
	i = tup_pend;
	if (cltime > tup_pendt) { tup_pendt = 0; return; }   // asked too long ago: not a click's answer now (flow review 4)
	tup_pendt = 0;
	if (i == -2)
	{
		print(sprintf("tas upload: %g TAS run(s)\n", tup_n));
		for (i = 0; i < tup_n; i = i + 1) print(sprintf("tas upload: %g %s (%s)\n", i + 1, tup_l[i], tup_p[i]));
		return;
	}
	if (i != floor(i) || i < 0 || i >= tup_n) { print(sprintf("tas upload: 1..%g\n", tup_n)); return; }
	if (!tasu_open) TASUI_Toggle(0);
	TASUI_SelectTab(TAS_TAB_UPLOAD);
	if (tup_state == 1 || tup_state == 3) { print("tas upload: one is on its way; wait for its answer\n"); return; }
	tup_state = 0; TASUp_Ask(i);
};
void(float argc) TASUp_Verb =
{
	local float i;
	if (argc >= 3 && argv(2) == "status") { print(sprintf("tas upload: state %g %s\n", tup_state, tup_note)); return; }
	i = (argc >= 3) ? stof(argv(2)) - 1 : -2;
	if (argc >= 3)
	if (checkbuiltin(cmdlevel_local))      // nested: QC evaluates both sides of &&
	if (!cmdlevel_local())
	{
		print("tas upload: only from your own console or binds\n");   // review: a server's command opened the tab
		return;
	}
	if (!isserver()) { print("tas upload: in a game you host\n"); return; }
	tup_pend = i; tup_pendt = cltime + 5;
	tup_at = 0; TASUp_List();
};

// P1712: the offer -- after a local TAS finish that beats this course's other saved TAS runs (SV_TASUpNote), a box where
// the F6 report boxes sit. Its code is asked for as it opens, so F6 signs and sends at once; F7 keeps the run local; in
// mode 2 the countdown's end sends it unkeyed. The box acts only on its own run: the tab taking the flow closes it.
float() PE_BoxUp;
float() CR_BoxUp;
float() cl_windowactive = #0;   // engine P1712
// the game has the keys (no console or menu over it) and the window is in front; TRUE on an engine without the builtins
float() TASUp_Focus =
{
	if (checkbuiltin(ui_native_gamefocus)) if (!ui_native_gamefocus()) return FALSE;
	if (checkbuiltin(cl_windowactive)) if (!cl_windowactive()) return FALSE;
	return TRUE;
};
// seen: not under the scoreboard, the TAS menu, another report box or any panel holding the cursor, with focus (reviews)
float() TASUp_BoxUp = { return tupb_box && !rec_sb_open && !tasu_open && !UI_CursorHeld() && TASUp_Focus() && !PE_BoxUp() && !CR_BoxUp(); };
float() TASUp_BoxOwns = { return tupb_box && tupb_mine && tup_state != 0; };
string(string p) TASUp_Folder = { local float i; for (i = strlen(p) - 1; i > 0; i = i - 1) if (str2chr(p, i) == 47) return substring(p, 0, i); return p; };
void(string p) TASUp_Unqueue =
{
	local float i, k;
	for (i = 0; i < tupb_qn; i = i + 1)
		if (!strcmp(TASUp_Folder(tupb_q[i]), TASUp_Folder(p)))
		{
			strunzone(tupb_q[i]);
			for (k = i + 1; k < tupb_qn; k = k + 1) tupb_q[k - 1] = tupb_q[k];
			tupb_qn = tupb_qn - 1;
			return;
		}
};
float(string p) TASUp_Queued = { local float i; for (i = 0; i < tupb_qn; i = i + 1) if (!strcmp(TASUp_Folder(tupb_q[i]), TASUp_Folder(p))) return TRUE; return FALSE; };
// a newer best of a course replaces that course's waiting one (it is faster: SV_TASUpBest); older: kept only if none waits
void(string p, float older) TASUp_Queue =
{
	local float k;
	if (older && TASUp_Queued(p)) return;
	TASUp_Unqueue(p);
	if (tupb_qn >= TUPB_Q) { strunzone(tupb_q[0]); for (k = 1; k < tupb_qn; k = k + 1) tupb_q[k - 1] = tupb_q[k]; tupb_qn = tupb_qn - 1; }
	tupb_q[tupb_qn] = strzone(p); tupb_qn = tupb_qn + 1;
};
// the state machine is not free: a code or a send on its way, or the tab's confirm or answer while the TAS menu is open
float() TASUp_Busy = { return tup_state == 1 || tup_state == 3 || ((tup_state == 2 || tup_state == 4) && tasu_open); };
void(string path) TASUp_Offer =
{
	if (tupb_box)                // a box still asking goes at once, so F6 in the gap sends nothing (flow review 5)
	{
		if (TASUp_BoxOwns() && (tup_state == 1 || tup_state == 2))
		{
			if (strcmp(TASUp_Folder(tupb_path), TASUp_Folder(path))) TASUp_Queue(tupb_path, TRUE);   // another course: back in line
			tup_state = 0; tup_req = 0;
		}
		tupb_box = FALSE;
	}
	else if (tupb_want && cltime <= tupb_want && strcmp(TASUp_Folder(tupb_path), TASUp_Folder(path)))
		TASUp_Queue(tupb_path, TRUE);     // an offer still waiting for its list, of another course
	TASUp_Unqueue(path);
	tupb_path = TASUp_Keep(tupb_path, path);
	tupb_want = cltime + 5;
	tup_at = 0; TASUp_List();
};
void() TASUp_NewEvent =
{
	local string path;
	local float mode;
	path = readstring(); mode = readbyte();
	if (!isserver() || mode <= 0) return;
	if (ui_consent_ver < FS_TERMS_ONLINE && cvar("rec_terms") < FS_TERMS_ONLINE) return;   // TASShare_Allowed, without its print
	tup_mode = mode;
	if (tup_state == 3 || (!TASUp_BoxOwns() && TASUp_Busy())) { TASUp_Queue(path, FALSE); return; }
	TASUp_Offer(path);
};
void() TASUp_OfferList =
{
	local float i;
	if (cltime > tupb_want) { tupb_want = 0; return; }
	tupb_want = 0;
	for (i = 0; i < tup_n; i = i + 1) if (!strcmp(tup_p[i], tupb_path)) break;
	if (i >= tup_n || tup_mode <= 0) return;
	if (TASUp_Busy()) { TASUp_Queue(tupb_path, TRUE); return; }    // the tab started one in the gap
	tup_state = 0;
	tupb_box = TRUE; tupb_auto = (tup_mode >= 2); tupb_why = TASUp_Keep(tupb_why, "");
	tupb_left = TUPB_SECS; tupb_seen = cltime; tupb_end = 0;
	tupb_asking = TRUE; TASUp_Ask(i); tupb_asking = FALSE;    // a refusal answers in the box
};
// closes the box; the next waiting best (if the machine is free) is offered
void() TASUp_BoxClose =
{
	local string path;
	if (TASUp_BoxOwns() && (tup_state == 1 || tup_state == 2)) { tup_state = 0; tup_req = 0; }   // a late code is ignored
	tupb_box = FALSE;
	if (tupb_qn > 0 && !TASUp_Busy())
	{
		path = strcat(tupb_q[0]);
		TASUp_Unqueue(path);
		TASUp_Offer(path);
	}
};
void(string why) TASUp_BoxKeep =
{
	print(sprintf("tas upload: %s kept on this PC (%s); the TAS menu's Upload tab still has it\n", tup_label, why));
	TASUp_BoxClose();
};
float(float scanx) TASUp_Key =
{
	if ((scanx != K_F6 && scanx != K_F7) || !TASUp_BoxUp() || !TASUp_BoxOwns() || tup_state == 3 || tup_state == 4) return FALSE;
	if (scanx == K_F7) { TASUp_BoxKeep("F7"); return TRUE; }
	if (tup_state == 2) TASUp_Send(FALSE);
	return TRUE;               // state 1: the code is on its way; the box says so
};
void(vector scr) TASUp_DrawBox =
{
	local vector p;
	local float sc, w, h, hh, lsz, y, ask, bh;
	local string st;
	if (!tupb_box)
	{
		if (tupb_want && cltime > tupb_want) tupb_want = 0;               // its list never came
		if (tup_state == 1 || tup_state == 3) TASUp_Pump();               // a tab request whose reply never came
		if (tupb_qn > 0 && !TASUp_Busy() && !tupb_want) TASUp_BoxClose();   // a best that waited on the tab
		return;
	}
	if (!TASUp_BoxOwns()) { TASUp_BoxClose(); return; }   // the tab took the flow: Back, or another run's Upload
	TASUp_Pump();
	if (tup_state == 2 && TASUp_BoxUp()) tupb_left = tupb_left - min(cltime - tupb_seen, 0.25);   // not hidden or stalled
	tupb_seen = cltime;
	if (tup_state == 2 && tupb_left <= 0 && TASUp_BoxUp())
	{
		if (!tupb_auto) { TASUp_BoxKeep("no key pressed"); return; }
		TASUp_Send(TRUE);      // or, refused, the box asks (TASUp_Send)
	}
	if (tup_state == 4 && cltime >= tupb_end) { TASUp_BoxClose(); return; }
	if (!TASUp_BoxUp()) return;
	ask = (tup_state == 1 || tup_state == 2);
	sc = ui_cv_scale;
	Font_Set(ui_font_ui);
	lsz = Font_Px(8 * sc);
	h = 14 * sc;
	hh = 15 * sc;
	w = 176 * sc;
	bh = 3 * sc + hh + (ask ? 4 : 2) * h + 3 * sc;
	p = [scr_x - w - 8 * sc, scr_y * 0.42, 0];
	// the finish card (drawn later, over this) sits on that spot after a finish: under it, else above it
	if (Results_Drawn() && rs_card_t >= cltime - 0.25 && p_x < rs_card_hi_x && p_x + w > rs_card_lo_x)
		p_y = (rs_card_hi_y + 6 * sc + bh <= scr_y - 4 * sc) ? rs_card_hi_y + 6 * sc : max(4 * sc, rs_card_lo_y - 6 * sc - bh);
	_sui_round_draw(p, [w, bh, 0], 5 * sc, SUI_THEME_PANEL, 0.90);
	y = p_y + 3 * sc;
	HUD_Text([p_x + 6 * sc, y + (hh - 2 * sc - lsz) * 0.5], "New TAS best", lsz, SUI_THEME_TEXT, 1);
	if (tup_state == 2)
		HUD_TextR([p_x + w - 6 * sc, y + (hh - 2 * sc - lsz) * 0.5], sprintf("%gs", ceil(max(0, tupb_left))), lsz, SUI_THEME_WARN, 1);
	drawfill([p_x + 4 * sc, y + hh - 2 * sc, 0], [w - 8 * sc, 1, 0], SUI_THEME_EDGE_HI, 0.7, 0);
	y = y + hh;
	HUD_Text([p_x + 6 * sc, y + (h - lsz) * 0.5], tup_label, lsz, SUI_THEME_DIM, 1);
	y = y + h;
	if (tup_state == 1) st = "getting the upload ready...";
	else if (tup_state == 2) st = (tupb_why != "") ? tupb_why : (tupb_auto ? "uploads itself when the timer ends" : "upload it to the TAS board?");
	else if (tup_state == 3) st = "sending and checking...";
	else st = tup_short;
	HUD_Text([p_x + 6 * sc, y + (h - lsz) * 0.5], st, lsz, SUI_THEME_DIM, 1);
	y = y + h;
	if (ask)
	{
		KeyMenu_Row([p_x, y], w, h, "F6", "Upload to the TAS board", (tup_state == 2) ? KM_HOT : KM_INERT, lsz, sc);
		y = y + h;
		KeyMenu_Row([p_x, y], w, h, "F7", "Keep it on this PC", KM_HOT, lsz, sc);
	}
	Font_Reset();
};
