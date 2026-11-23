/*
  P1747: record the open replay as a video. The window picks the size, frame rate, supersampling, motion blur, HUD and
  quality; Record sets the capture cvars (saving what they were), has the replay rewound (CSQC's vidrec_cs, cl_vidrec.qc),
  starts `capture` -- the menu's to run, never a server's -- and stops it when the replay says it has ended, then puts
  every setting back. The engine steps the game by exactly one video frame a frame (capturefixed) and pipes the frames
  to ffmpeg (capturedriver ffmpeg), which scales a supersampled render down and, for motion blur, averages subframes:
  a real shutter over the frame's own time, not the old frame blended into the new one.
*/
#define MVR_NSAVE 27
string mvr_names[MVR_NSAVE] = {"capturedriver", "capturecodec", "capturerate", "capturefixed", "capturedemowidth",
	"capturedemoheight", "capture_outwidth", "capture_outheight", "capture_outrate", "capture_blurframes", "capture_codec",
	"capture_crf", "capturesound", "hl2_water", "hl2_refract", "r_capturerate", "r_capturehalfrate", "r_capturestagger",
	"r_watertargetsize", "r_refractreflect_scale", "r_waterforcereflectentities", "hl2_water_lod", "show_fps",
	"hud_watch_skipidle", "hud_watch_skipfail", "cl_idlefps", "vid_conautoscale"};
string mvr_saved[MVR_NSAVE];
float mvr_inited, mvr_back;
float mvr_res, mvr_fps, mvr_ss, mvr_blur, mvr_hud, mvr_maxq, mvr_codec;
float mvr_state, mvr_t0;            // 0 idle, 1 settings applied, 2 rewinding, 3 recording, 4 finishing, 5 done
float mvr_ff;                       // this recording went to ffmpeg (not PNG frames)
vector mvr_screen;                  // the menu's size, which vid_conautoscale 1 makes the window's pixels
string mvr_out, mvr_note;

string(string old, string v) MVR_Keep =
{
	local string c;
	c = strzone(v);
	if (old != "") strunzone(old);
	return c;
};

void() MVR_Init =
{
	if (mvr_inited) return;
	mvr_inited = TRUE;
	mvr_res = 1; mvr_fps = 1; mvr_ss = 1; mvr_hud = 0; mvr_maxq = TRUE;    // 1080p60, 2x supersampled, clean, max water
	mvr_out = ""; mvr_note = "";
	registercvar("ui_vidrec_open", "0", 0);
};

float() MVR_Fps = { return (mvr_fps == 0) ? 30 : (mvr_fps == 1) ? 60 : 120; };
// the video's size: the window's own, or a standard 16:9 height
vector() MVR_Out =
{
	local vector v;
	if (mvr_res == 0)
	{
		v = mvr_screen;
		if (v_x < 320) v = '1920 1080 0';
		return [floor(v_x / 2) * 2, floor(v_y / 2) * 2, 0];
	}
	if (mvr_res == 1) return '1920 1080 0';
	if (mvr_res == 2) return '2560 1440 0';
	return '3840 2160 0';
};
float() MVR_SS = { return (mvr_ss == 0) ? 1 : (mvr_ss == 1) ? 2 : 4; };
// subframes a video frame when blurring (render rate = fps x this), and how many of them the shutter keeps open
float() MVR_Sub = { return mvr_blur ? ((mvr_fps == 0) ? 8 : (mvr_fps == 1) ? 6 : 4) : 1; };
float() MVR_Blend = { return mvr_blur ? MVR_Sub() / ((mvr_blur == 1) ? 4 : 2) : 0; };
string() MVR_Codec = { return (mvr_codec == 1) ? "h264_nvenc" : (mvr_codec == 2) ? "hevc" : (mvr_codec == 3) ? "av1" : "h264"; };
float() MVR_Busy = { return mvr_state >= 1 && mvr_state <= 4; };

void() MVR_Save =
{
	local float i;
	for (i = 0; i < MVR_NSAVE; i = i + 1)
		mvr_saved[i] = MVR_Keep(mvr_saved[i], cvar_type(mvr_names[i]) ? cvar_string(mvr_names[i]) : "\x01");
};
void() MVR_Restore =
{
	local float i;
	for (i = 0; i < MVR_NSAVE; i = i + 1)
		if (mvr_saved[i] != "\x01" && mvr_saved[i] != "")
			cvar_set(mvr_names[i], mvr_saved[i]);
		else if (mvr_saved[i] == "" && cvar_type(mvr_names[i]))
			cvar_set(mvr_names[i], "");
};

void(string s) MVR_Fail =
{
	if (mvr_state >= 1 && mvr_state <= 3)
	{
		if (mvr_state == 3) localcmd_local("capturestop\n");
		localcmd("vidrec_cs done\n");
		MVR_Restore();
	}
	mvr_state = 5;
	mvr_note = MVR_Keep(mvr_note, s);
	print(sprintf("vidrec: %s\n", s));
};

void() MVR_Start =
{
	local vector out, rnd;
	local float ss, sub, ff;
	local string map;
	if (clientstate() != 2 || cvar_string("vidrec_replay") == "") { mvr_note = MVR_Keep(mvr_note, "Open a replay first."); return; }
	if (!cvar_type("capturefixed")) { mvr_note = MVR_Keep(mvr_note, "This game is too old to record videos: update it."); return; }
	ff = (cvar_string("capture_ffmpeg") != "");
	mvr_ff = ff;
	out = MVR_Out();
	ss = MVR_SS();
	rnd = out * ss;
	if (rnd_x > 8192 || rnd_y > 8192) { ss = 2; rnd = out * 2; }       // a GL framebuffer's practical edge
	sub = MVR_Sub();
	tokenize(cvar_string("vidrec_replay"));
	map = argv(0);
	mvr_out = MVR_Keep(mvr_out, sprintf("videos/%s_%s%s", map, strftime(FALSE, "%Y%m%d-%H%M%S"), ff ? ".mp4" : ""));
	MVR_Save();
	cvar_set("capturedriver", ff ? "ffmpeg" : "raw");
	cvar_set("capturecodec", "png");
	cvar_set("capturefixed", "1");
	cvar_set("capturerate", ftos(MVR_Fps() * sub));
	cvar_set("capture_outrate", (sub > 1) ? ftos(MVR_Fps()) : "0");
	cvar_set("capture_blurframes", ftos(MVR_Blend()));
	cvar_set("capturedemowidth", ftos(rnd_x));
	cvar_set("capturedemoheight", ftos(rnd_y));
	cvar_set("capture_outwidth", ftos(out_x));
	cvar_set("capture_outheight", ftos(out_y));
	cvar_set("capture_codec", MVR_Codec());
	cvar_set("capture_crf", (mvr_codec == 1) ? "19" : (mvr_codec == 3) ? "28" : "16");
	cvar_set("capturesound", "1");
	cvar_set("show_fps", "0");
	cvar_set("hud_watch_skipidle", "0");
	cvar_set("hud_watch_skipfail", "0");
	cvar_set("cl_idlefps", "0");
	// the HUD laid out as it is on this screen: a supersampled (or bigger than the window) render scales 2D up to match
	if (mvr_hud && mvr_screen_x >= 320)
		cvar_set("vid_conautoscale", ftos(max(1, rint(rnd_x / mvr_screen_x * 4) / 4) * max(1, cvar("vid_conautoscale"))));
	if (mvr_maxq)
	{	// every reflection and refraction at full size, redrawn each frame (their usual rate is 60 a second)
		cvar_set("hl2_water", "2");
		cvar_set("hl2_refract", "1");
		cvar_set("r_capturerate", "0");
		cvar_set("r_capturehalfrate", "0");
		cvar_set("r_capturestagger", "0");
		cvar_set("r_watertargetsize", "0");
		cvar_set("r_refractreflect_scale", "1");
		cvar_set("r_waterforcereflectentities", "1");
		cvar_set("hl2_water_lod", "0");
	}
	mvr_state = 1;
	mvr_t0 = gettime(0);
	mvr_note = MVR_Keep(mvr_note, sprintf("Recording %s ...", mvr_out));
	print(sprintf("vidrec: %s, rendered %gx%g, %g fps%s, %s\n", mvr_out, rnd_x, rnd_y, MVR_Fps(),
		(sub > 1) ? sprintf(" (%g subframes, %g blended)", sub, MVR_Blend()) : "", ff ? MVR_Codec() : "PNG frames"));
	m_close();                      // a menu over the game pauses the capture
};

// Every frame, menu open or not (m_draw's top): the steps of a recording
void() MVR_Frame =
{
	local string last;
	if (!mvr_inited) MVR_Init();
	if (cvar("ui_vidrec_open"))
	{
		cvar_set("ui_vidrec_open", "0");
		if (!MVR_Busy() && clientstate() == 2)
		{
			if (menu_screen != SCREEN_VIDREC) mvr_back = menu_screen;
			menu_screen = SCREEN_VIDREC;
			m_open();
		}
	}
	if (!MVR_Busy()) return;
	if (clientstate() != 2) { MVR_Fail("The game left the map; the video stopped."); return; }
	if (mvr_state == 1 && gettime(0) - mvr_t0 > 0.75)
	{	// the settings had their shader reloads; now the replay goes back to its start
		cvar_set("vidrec_ready", "0");
		localcmd(sprintf("vidrec_cs prep %g\n", mvr_hud));
		mvr_state = 2;
		mvr_t0 = gettime(0);
	}
	else if (mvr_state == 2)
	{
		if (cvar("vidrec_ready") == 1)
		{
			localcmd_local(sprintf("capture \"%s\"\n", mvr_out));
			localcmd("vidrec_cs go\n");
			mvr_state = 3;
		}
		else if (cvar("vidrec_ready") < 0 || gettime(0) - mvr_t0 > 5)
			MVR_Fail("No replay is open.");
	}
	else if (mvr_state == 3 && cvar("vidrec_end") == 1)
	{
		localcmd_local("capturestop\n");
		localcmd("vidrec_cs done\n");
		MVR_Restore();
		mvr_state = 4;
		mvr_t0 = gettime(0);
	}
	else if (mvr_state == 4)
	{
		last = cvar_string("capture_ffmpeg_last");
		if (!mvr_ff)
		{
			mvr_state = 5;
			mvr_note = MVR_Keep(mvr_note, sprintf("Saved PNG frames and the audio in %s/ in your game folder.", mvr_out));
			return;
		}
		if (strstrofs(last, substring(mvr_out, 7, -1)) < 0)     // another recording's word: not this one's yet
			last = "";
		if (substring(last, 0, 6) == "saved " || substring(last, 0, 7) == "failed ")
		{
			mvr_state = 5;
			mvr_note = MVR_Keep(mvr_note, (substring(last, 0, 6) == "saved ")
				? sprintf("Saved %s in your game folder (%s).", mvr_out, substring(last, 6, -1)) : sprintf("The video %s", last));
			print(sprintf("vidrec: %s\n", mvr_note));
		}
		else if (gettime(0) - mvr_t0 > 600)
		{
			mvr_state = 5;
			mvr_note = MVR_Keep(mvr_note, "ffmpeg is still finishing the video; it will be in videos/ when it is done.");
		}
	}
};

void() MVR_Open =
{
	MVR_Init();
	if (menu_screen != SCREEN_VIDREC) mvr_back = menu_screen;
	menu_screen = SCREEN_VIDREC;
};
void() MVR_Close =
{
	menu_screen = (mvr_back == SCREEN_VIDREC) ? SCREEN_MAIN : mvr_back;
	if (clientstate() == 2 && menu_screen == SCREEN_MAIN) m_close();
};

// one labelled row of chips; returns the chosen index
float(vector p, string label, string id, string opts, float cur) MVR_Row =
{
	local float n, i, x;
	local string rid;
	sui_text(p, SZ_LABEL, label, COL_DIM, 1, 0);
	n = tokenizebyseparator(opts, ";");
	x = p_x + 150;
	for (i = 0; i < n; i = i + 1)
	{
		rid = strcat(id, ftos(i));
		x = x + ui_chip([x, p_y - 5], rid, argv(i), cur == i) + 6;
		if (sui_is_released(rid)) cur = i;
		n = tokenizebyseparator(opts, ";");     // ui_chip's measuring may tokenize: read the list again
	}
	return cur;
};

void(vector screensize) MVR_Draw =
{
	local vector p, out, rnd;
	local float w, h, y, ss, ff, secs, frames;
	local string rep, line;
	mvr_screen = screensize;
	w = min(760, screensize_x - 24);
	h = min(560, screensize_y - 24);
	p = [floor((screensize_x - w) * 0.5), floor((screensize_y - h) * 0.5)];
	sui_style_panel(p, [w, h], 12, 1);
	Font_Set(ui_font_ui);
	sui_text(p + '18 16 0', SZ_HEAD, "Record replay as video", COL_TEXT, 1, 0);
	rep = cvar_string("vidrec_replay");
	tokenize(rep);
	secs = stof(argv(1));
	sui_text(p + '18 46 0', SZ_LABEL, (rep != "") ? sprintf("%s, %g:%s long", argv(0), floor(secs / 60),
		substring(ftos(100 + floor(secs - floor(secs / 60) * 60)), 1, 2)) : "Open a replay (TAB, then a run), then press record video on its bar.",
		(rep != "") ? COL_ACCENT : COL_DIM, 1, 0);
	if (ui_button("mvr_close", [p_x + w - 16 - 90, p_y + 14], [90, 30], MVR_Busy() ? "Back" : "Close"))
	{
		MVR_Close();
		return;
	}
	y = p_y + 92;
	mvr_res = MVR_Row([p_x + 18, y], "Size", "mvr_res", "Window;1080p;1440p;4K", mvr_res); y = y + 40;
	mvr_fps = MVR_Row([p_x + 18, y], "Frame rate", "mvr_fps", "30;60;120", mvr_fps); y = y + 40;
	mvr_ss = MVR_Row([p_x + 18, y], "Supersampling", "mvr_ss", "Off;2x;4x", mvr_ss); y = y + 40;
	mvr_blur = MVR_Row([p_x + 18, y], "Motion blur", "mvr_blur", "Off;Light;Film", mvr_blur); y = y + 40;
	mvr_hud = MVR_Row([p_x + 18, y], "HUD", "mvr_hud", "Hidden;Shown", mvr_hud); y = y + 40;
	mvr_maxq = MVR_Row([p_x + 18, y], "Water & glass", "mvr_q", "As set;Maximum", mvr_maxq); y = y + 40;
	mvr_codec = MVR_Row([p_x + 18, y], "Encoder", "mvr_codec", "H.264;NVENC (fast);HEVC;AV1", mvr_codec); y = y + 44;
	out = MVR_Out();
	ss = MVR_SS();
	rnd = out * ss;
	if (rnd_x > 8192 || rnd_y > 8192) rnd = out * 2;
	frames = ceil((secs + 1) * MVR_Fps());
	line = sprintf("Renders %gx%g, saves %gx%g at %g fps: %g frames", rnd_x, rnd_y, out_x, out_y, MVR_Fps(), frames);
	if (mvr_blur) line = strcat(line, sprintf(", each the average of %g of %g subframes", MVR_Blend(), MVR_Sub()));
	ui_para([p_x + 18, y], w - 36, SZ_LABEL, 20, line, COL_TEXT, TRUE);
	y = y + 26;
	ff = (cvar_string("capture_ffmpeg") != "");
	if (!cvar_type("capturefixed"))
		line = "This game is too old to record videos: update it.";
	else if (ff)
		line = sprintf("Frames go to ffmpeg (%s). The game runs slower than real time while it records; that is normal.", cvar_string("capture_ffmpeg"));
	else
		line = "ffmpeg was not found, so it saves PNG frames and the audio instead. Install ffmpeg, or put ffmpeg beside the game, for a video file.";
	y = y + ui_para([p_x + 18, y], w - 36, SZ_LABEL, 20, line, COL_DIM, TRUE) + 6;
	if (cvar("sv_running") != 1 && rep != "")
		y = y + ui_para([p_x + 18, y], w - 36, SZ_LABEL, 20, "Best in a game you host: on a lobby, other players and moving map parts keep the server's clock.", SUI_THEME_WARN, TRUE) + 6;
	if (!MVR_Busy())
	{
		if (ui_button("mvr_go", [p_x + w - 18 - 168, p_y + h - 50], [168, 32], "Record", (rep != "" && cvar_type("capturefixed"))))
		if (rep != "")
			MVR_Start();
	}
	else if (ui_button("mvr_stop", [p_x + w - 18 - 168, p_y + h - 50], [168, 32], "Stop recording"))
	{
		if (mvr_state == 3) cvar_set("vidrec_end", "1");    // the next frame stops and saves what was recorded
		else MVR_Fail("Stopped.");
	}
	if (mvr_note != "")
		ui_para([p_x + 18, p_y + h - 46], w - 36 - 190, SZ_LABEL, 20, mvr_note, (mvr_state == 5 && substring(mvr_note, 0, 5) == "Saved")
			? SUI_THEME_GOOD : COL_DIM, TRUE);
};

float(float evtype, float scanx) MVR_Input =
{
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE)
	{
		MVR_Close();
		return TRUE;
	}
	return FALSE;
};

// ui_vidrec set <size> <fps> <ss> <blur> <hud> <water> <encoder> (the chip indices), start, status: tests and binds
float() MVR_Command =
{
	MVR_Init();
	if (argv(1) == "set")
	{
		mvr_res = bound(0, stof(argv(2)), 3); mvr_fps = bound(0, stof(argv(3)), 2); mvr_ss = bound(0, stof(argv(4)), 2);
		mvr_blur = bound(0, stof(argv(5)), 2); mvr_hud = bound(0, stof(argv(6)), 1); mvr_maxq = bound(0, stof(argv(7)), 1);
		mvr_codec = bound(0, stof(argv(8)), 3);
	}
	else if (argv(1) == "start" && !MVR_Busy())
		MVR_Start();
	else if (argv(1) == "status")
		print(sprintf("vidrec: state %g replay \"%s\" out %s note \"%s\" last \"%s\"\n", mvr_state, cvar_string("vidrec_replay"), mvr_out,
			mvr_note, cvar_string("capture_ffmpeg_last")));
	else
		print("ui_vidrec [set <size> <fps> <ss> <blur> <hud> <water> <encoder>|start|status]\n");
	return TRUE;
};
