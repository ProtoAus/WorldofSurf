/*
  P1747: the replay's half of "record this replay as a video". The menu's Record window (menu/m_vidrec.qc) owns the
  capture -- only it may run `capture`, a server's CSQC may not -- and these commands are how it drives the replay:

    vidrec_cs prep <hud>   rewind the open replay to its start, paused, playing at 1x, and say ready (cvar vidrec_ready)
    vidrec_cs go           play it; at its end (and a second held on the last frame) set vidrec_end
    vidrec_cs done         back to normal

  While recording the replay's bar is never drawn, and with <hud> 0 nothing 2D is (cl_main.qc tests VRec_Clean).
  The engine steps each frame by the video's frame time (capturefixed), so playback, which advances by clframetime,
  is frame-exact; a menu opened mid-video pauses the replay so the video has no gap.
*/
// vrec_state (cl_keys.qc): 0 idle, 1 rewound and waiting for go, 2 recording, 3 ended
float vrec_endat, vrec_menupaused;

void() VRec_Init =
{
	registercvar("vidrec_ready", "0");
	registercvar("vidrec_end", "0");
	registercvar("vidrec_replay", "");
	registercommand("vidrec_cs");
};

float() VRec_Clean = { return (vrec_state >= 1 && vrec_clean); };

// what the Record window shows about the replay: "<map> <seconds>", "" when none is open
string vrec_said;
void() VRec_Publish =
{
	local string s;
	s = rec_wt_open ? sprintf("%s %g", rec_wt_map, max(0, rint((rec_wt_vt1 - rec_wt_vt0) * 10) / 10)) : "";
	if (s == vrec_said) return;
	if (vrec_said != "") strunzone(vrec_said);
	vrec_said = (s != "") ? strzone(s) : "";
	cvar_set("vidrec_replay", s);
};

void(float notmenu) VRec_Frame =
{
	VRec_Publish();
	if (vrec_state != 2) return;
	if (!rec_wt_open)
	{	// closed under the recording: the video ends here
		vrec_state = 3;
		cvar_set("vidrec_end", "1");
		return;
	}
	// a menu or the console over the video: hold the replay so nothing goes by unrecorded
	if (!notmenu && !rec_wt_paused) { rec_wt_paused = TRUE; vrec_menupaused = TRUE; }
	else if (notmenu && vrec_menupaused) { rec_wt_paused = FALSE; vrec_menupaused = FALSE; }
	if (rec_wt_paused && !vrec_menupaused && rec_wt_time >= rec_wt_vt1)
	{
		if (!vrec_endat) vrec_endat = cltime + 1;
		else if (cltime >= vrec_endat)
		{
			vrec_state = 3;
			cvar_set("vidrec_end", "1");
		}
	}
};

float() VRec_ConsoleCommand =
{
	if (argv(0) != "vidrec_cs") return FALSE;
	if (argv(1) == "prep")
	{
		cvar_set("vidrec_end", "0");
		if (!rec_wt_open)
		{
			cvar_set("vidrec_ready", "-1");
			print("vidrec: no replay is open\n");
			return TRUE;
		}
		vrec_clean = !stof(argv(2));
		Watch_Seek(rec_wt_vt0);
		rec_wt_paused = TRUE;
		rec_wt_rate = 1;
		vrec_state = 1;
		vrec_endat = 0;
		vrec_menupaused = FALSE;
		cvar_set("vidrec_ready", "1");
	}
	else if (argv(1) == "go" && vrec_state == 1)
	{
		vrec_state = 2;
		rec_wt_paused = FALSE;
	}
	else if (argv(1) == "done")
	{
		vrec_state = 0;
		vrec_clean = FALSE;
		cvar_set("vidrec_ready", "0");
		cvar_set("vidrec_end", "0");
	}
	return TRUE;
};
