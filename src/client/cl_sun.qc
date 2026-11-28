/*
===========================================================================
  cl_sun.qc -- env_sun (Patch 874).  247 maps carry one.

  Source's C_Sun is two directional glow overlays drawn 100 units in front of
  the eye along the sun's direction (glow_overlay.cpp CalcBasis):
    core   size `size`, colour rendercolor scaled so its brightest channel is 1
           (c_sun.cpp:60-76), full strength while the sky is visible;
    glow   size `overlaysize` (-1 = size) x6, colour overlaycolor (or the core's
           when 0 0 0), alpha 0.75 looking straight at the sun falling to 0 at a
           dot of 0.9 (c_sun.h C_SunGlowOverlay).
  Visibility: a ray along the direction that hits anything but a sky side hides
  it, faded over cl_sun_decay_rate's 0.05 s.  Source's normal path is a pixel
  query, which models occlude (glow_overlay.cpp:160-170; the CONTENTS_SOLID
  trace is its fallback), so P1182 traces props as the glares do.
  Drawn without depth, as light_glow02_add_noz is.
  Direction: use_angles takes angles with the pitch key's override
  (SetupLightNormalFromProps), else the sun's origin minus its target's (the
  first, any case); no target, or one that is not there, keeps CSun's (0,0,1).
  vbsp_sun 0 hides it (gfx menu).
===========================================================================
*/
float  sun_have;
vector sun_dir;
vector sun_col, sun_ocol;
float  sun_size, sun_osize;
string sun_mat, sun_omat;
float  sun_vis;                 // 0..1, the obstruction fade
entity sun_probe;               // the trace's mask: brush glass (WINDOW) shows the sun, glass props do not
float  sun_seen;                // the last visibility printed: -1 none yet
float  sun_traced, sun_target, sun_tracedsky;   // P1804: the last nine-ray answer, kept while the eye stays put
vector sun_tracedeye;

string(string m) Sun_Shader =
{
	m = strtolower(m);
	if (substring(m, strlen(m) - 4, 4) == ".vmt")
		m = substring(m, 0, strlen(m) - 4);
	if (m == "")
		m = "sprites/light_glow02_add_noz";
	return m;
};

// P1182: the glares' mask. Every prop's triangles are BODY only (mod_hl2.c), so SOLID
// alone let all props through (pantheon's hubpillar); VISUAL adds the draw-only ones.
void() Sun_ProbeInit =
{
	if (sun_probe)
		return;
	sun_probe = spawn();
	sun_probe.hitcontentsmaski = SPR_GLARE_MASK;
};

void() Sun_LoadForMap =
{
	local string tok, key, cn, tname, target, mat, omat;
	local vector org, ang, rgb, orgb, torg;
	local float  size, osize, useang, pitch, yaw, found, maxc;
	local vector h;
	local string want;

	sun_have = FALSE;
	sun_vis = 0;
	sun_traced = FALSE;
	sun_seen = -1;
	if (sun_mat != "") strunzone(sun_mat);
	if (sun_omat != "") strunzone(sun_omat);
	sun_mat = sun_omat = "";
	found = FALSE;
	want = "";

	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = tname = target = mat = omat = "";
		org = ang = rgb = orgb = '0 0 0';
		size = 16;
		osize = -1;
		useang = 0;
		pitch = yaw = 0;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")       cn = tok;
			else if (key == "targetname")      tname = tok;
			else if (key == "target")          target = tok;
			else if (key == "origin")          org = stov(tok);
			else if (key == "angles")          ang = stov(tok);
			else if (key == "rendercolor")     rgb = stov(tok);
			else if (key == "overlaycolor")    orgb = stov(tok);
			else if (key == "size")            size = stof(tok);
			else if (key == "overlaysize")     osize = stof(tok);
			else if (key == "material")        mat = tok;
			else if (key == "overlaymaterial") omat = tok;
			else if (key == "use_angles")      useang = stof(tok);
			else if (key == "pitch")           pitch = stof(tok);
			else if (key == "angle")           yaw = stof(tok);
		}
		if (cn != "env_sun" || found)
			continue;
		found = TRUE;
		if (useang)
		{
			// SetupLightNormalFromProps (map_utils.cpp): z is +sin(pitch), not makevectors'
			// -sin; angle -1/-2 (up/down) zero the horizontal.  The sun is the light's reverse.
			if (yaw == -1 || yaw == -2)
				h = '0 0 0';
			else
			{
				if (!yaw)
					yaw = ang_y;
				h = [cos(yaw * M_PI / 180), sin(yaw * M_PI / 180), 0];
			}
			if (!pitch)
				pitch = ang_x;
			sun_dir = -[h_x * cos(pitch * M_PI / 180), h_y * cos(pitch * M_PI / 180), sin(pitch * M_PI / 180)];
		}
		else if (target != "")
		{
			want = strzone(strtolower(target));
			sun_dir = org;       // resolved against the target below
		}
		else
			sun_dir = '0 0 1';   // CSun's default: an empty name finds nothing
		maxc = max(rgb_x, max(rgb_y, rgb_z));
		sun_col = (maxc > 0) ? rgb * (1 / maxc) : '1 1 1';
		sun_ocol = (orgb != '0 0 0') ? orgb * (1 / 255) : sun_col;
		sun_size = size;
		sun_osize = (osize == -1) ? size : osize;
		sun_mat = strzone(Sun_Shader(mat));
		sun_omat = strzone(Sun_Shader(omat));
	}
	if (!found)
		return;
	if (want != "")
	{
		// A second walk for the target: it may come before or after the sun.
		found = FALSE;
		torg = '0 0 0';
		getentitytoken(0);
		while (!found && (tok = getentitytoken()) != "")
		{
			if (tok != "{")
				continue;
			tname = "";
			org = '0 0 0';
			while ((key = getentitytoken()) != "" && key != "}")
			{
				tok = getentitytoken();
				key = strtolower(key);
				if (key == "targetname") tname = tok;
				else if (key == "origin") org = stov(tok);
			}
			if (strtolower(tname) == want)
			{
				torg = org;
				found = TRUE;
			}
		}
		strunzone(want);
		sun_dir = found ? sun_dir - torg : '0 0 1';
		if (sun_dir == '0 0 0')
			sun_dir = '0 0 1';
	}
	sun_dir = normalize(sun_dir);
	sun_have = TRUE;
	dprint(sprintf("env_sun: dir %v size %g/%g %s\n", sun_dir, sun_size, sun_osize, sun_mat));
	// P1182 review 2: the first trace asking for the visual bit builds the plugin's
	// draw-only tree (loading non-solid prop models); pay that here, not mid-run.
	Sun_ProbeInit();
	traceline('0 0 0', '0 0 1', MOVE_NOMONSTERS, sun_probe);
};

void(string mat, vector eye, float hs, vector col, float a) Sun_Quad =
{
	local vector base, rt, up;

	if (a <= 0)
		return;
	base = eye + sun_dir * 100;
	rt = normalize(crossproduct(sun_dir, '0 0 1'));
	if (rt == '0 0 0')
		rt = '1 0 0';
	up = normalize(crossproduct(rt, sun_dir));
	rt = rt * hs;
	up = up * hs;
	R_BeginPolygon(mat, DRAWFLAG_ADD | DRAWFLAG_NODEPTHTEST);
	R_PolygonVertex(base - rt + up, '0 0 0', col, a);
	R_PolygonVertex(base + rt + up, '1 0 0', col, a);
	R_PolygonVertex(base + rt - up, '1 1 0', col, a);
	R_PolygonVertex(base - rt - up, '0 1 0', col, a);
	R_EndPolygon();
};

// P1723-P1725/P1732: the map's bloom, exposure and dynamic-shadow settings, read once at load.  Sources and the
// fidelity notes: ENGINE_PATCHES P1723, P1724, P1732.

// VRAD LightForString: "r g b [brightness [r g b brightness HDR]]" -> linear intensity / 255.  '-1 -1 -1' = not legal.
vector(string val, float hdr) Sun_VradLight =
{
	local float n, r, g, b, k;

	n = tokenize(val);
	if (n == 8 && hdr)
	{
		r = stof(argv(4)); g = stof(argv(5)); b = stof(argv(6)); k = stof(argv(7));
		n = 4;
	}
	else
	{
		r = stof(argv(0)); g = stof(argv(1)); b = stof(argv(2)); k = stof(argv(3));
		if (n == 8)
			n = 4;
	}
	if (n == 1)
		g = b = r;
	if ((n != 1 && n != 3 && n != 4) || r < 0 || g < 0 || b < 0 || k < 0)
		return '-1 -1 -1';
	if (n != 4)
		k = 255;
	return [pow(r / 255, 2.2), pow(g / 255, 2.2), pow(b / 255, 2.2)] * (k / 255);
};

// VRAD ParseLightEnvironment's sky ambient: a legal _ambientHDR (HDR), else _ambient, else half the sun (_light,
// _lightHDR, _lightscaleHDR as ParseLightGeneric); x _AmbientScaleHDR on HDR.  Linear, VRAD units / 255.
// The sun itself (ParseLightGeneric): _lightHDR when legal on HDR, else _light; x _lightscaleHDR on HDR.
vector(float hdr, string lt, string lthdr, float ltscale) Sun_Direct =
{
	local vector sun, v;

	sun = Sun_VradLight(lt, hdr);
	if (hdr)
	{
		v = Sun_VradLight(lthdr, TRUE);
		if (v_x >= 0)
			sun = v;
	}
	if (sun_x < 0)
		sun = '0 0 0';
	if (hdr)
		sun = sun * ltscale;
	return sun;
};
vector(float hdr, string lt, string lthdr, float ltscale, string amb, string ambhdr, float ambscale) Sun_SkyAmbient =
{
	local vector sun, v;

	sun = Sun_Direct(hdr, lt, lthdr, ltscale);
	v = '-1 -1 -1';
	if (hdr)
		v = Sun_VradLight(ambhdr, TRUE);
	if (v_x < 0)
		v = Sun_VradLight(amb, hdr);
	if (v_x < 0)
		v = sun * 0.5;
	if (hdr)
		v = v * ambscale;
	return [max(0, v_x), max(0, v_y), max(0, v_z)];
};

float(float x) Sun_SRGB =
{
	if (x <= 0.0031308)
		return 12.92 * max(0, x);
	return 1.055 * pow(x, 1 / 2.4) - 0.055;
};

// P1769: a prop's rendercolor, exact.  The wire carries colormod in 1/32 steps, so P1759 sends bhop_canals' amber barn
// shafts (21 18 13) as 24 16 16, a pink cast; the entity lump has the exact value, so the client puts it back on the
// entity (deltalisten: the callback's colormod is drawn as a float).
#define TINT_MAX 64
float tint_mi[TINT_MAX];
vector tint_org[TINT_MAX];
vector tint_col[TINT_MAX];
float tint_n;
float(float isnew) Tint_Delta =
{
	local float k;
	local vector d;
	self.drawmask = 0;	// the engine's copy: never also drawn by addentities unless taken below
	for (k = 0; k < tint_n; k = k + 1)
		if (tint_mi[k] == self.modelindex && vlen(self.origin - tint_org[k]) < 4)
		{
			// only while the server still sends the map's colour (rounded to the wire's 1/32): a Color input that
			// changed it wins
			d = self.colormod - tint_col[k];
			if (fabs(d_x) > 0.035 || fabs(d_y) > 0.035 || fabs(d_z) > 0.035)
				return FALSE;
			if (self.effects & EF_NODRAW)
				return TRUE;	// hidden (Disable, rendermode 10): drawn by nobody
			self.colormod = tint_col[k];
			// P1778: drawn by the CSQC path, which flips a mesh's pitch/roll (r_meshpitch/r_meshroll, -1) where the
			// engine's own exempts a Source model (Patch 1027): the barn shafts leant away from the sun patches
			self.angles_x = self.angles_x * cvar("r_meshpitch");
			self.angles_z = self.angles_z * cvar("r_meshroll");
			self.drawmask = MASK_ENGINE;
			return TRUE;
		}
	return FALSE;	// not one of the map's tinted props: the engine draws it as sent
};
void() Tint_Load =
{
	local string tok, key, cn, mdl, rc;
	local vector org, c;
	local float k, mi, seen, animated;
	tint_n = 0;
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = mdl = rc = "";
		org = '0 0 0';
		animated = FALSE;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if (key == "classname")
				cn = tok;
			else if ((key == "setbodygroup" || key == "body") && stof(tok))
				animated = TRUE;	// the client's copy draws body 0 (the engine does not hand CSQC the bodygroup)
			else if ((key == "defaultanim" && tok != "") || (key == "playbackrate" && stof(tok) != 1 && tok != ""))
				animated = TRUE;	// nor its playback rate
			else if (key == "model")
				mdl = tok;
			else if (key == "rendercolor")
				rc = tok;
			else if (key == "origin")
				org = stov(tok);
		}
		if (substring(cn, 0, 5) != "prop_" || mdl == "" || rc == "" || tint_n >= TINT_MAX || animated)
			continue;
		c = stov(rc);
		if (c == '255 255 255' || c == '0 0 0')
			continue;
		mi = getmodelindex(mdl, TRUE);
		if (mi <= 0)
			continue;	// not precached by the server (or only by this client): not on the wire
		seen = FALSE;
		for (k = 0; k < tint_n; k = k + 1)
			if (tint_mi[k] == mi)
				seen = TRUE;
		tint_mi[tint_n] = mi;
		tint_org[tint_n] = org;
		tint_col[tint_n] = [bound(0, c_x, 255), bound(0, c_y, 255), bound(0, c_z, 255)] * (1 / 255);
		tint_n = tint_n + 1;
		if (!seen)
			deltalisten(mdl, Tint_Delta, 0);
	}
};

// P1767: the map's auto-exposure band and the vbsp_autoexposure value it was applied with, so a change takes effect at
// once (Sun_AutoExposureFrame) rather than at the next map.
float sun_aemin, sun_aemax, sun_aeapplied;
void(float on) Sun_ApplyAutoExposure =
{
	if (!cvar_type("r_autoexposure"))
		return;
	if (on)
	{
		cvar_set("r_autoexposure_min", ftos(sun_aemin));
		cvar_set("r_autoexposure_max", ftos(sun_aemax));
		cvar_set("r_autoexposure", "1");
	}
	else
		cvar_set("r_autoexposure", "0");
	sun_aeapplied = on;
};
void() Sun_AutoExposureFrame =
{
	local float on;
	if (!sun_aemax)
		return;	// no map light read yet
	on = (cvar("vbsp_autoexposure") != 0);
	if (on != sun_aeapplied)
		Sun_ApplyAutoExposure(on);
};

void() Sun_MapLight =
{
	local string tok, key, cn, inp, amb, ambhdr, lt, lthdr;
	local float bloom, bat, d, p, y, havesc, havecsm, csmle, havele, epitch, ehaspitch, emin, emax, eminat, emaxat;
	local float ambscale, ltscale, hascol, hdr, hdrk, expo, csmdist, emsd, autoexp;
	local vector eang, scdir, csmdir, ledir, thr, ecol, sccol, skyamb, skyambhdr, v, lesun, lesunhdr;

	bloom = 1;
	bat = eminat = emaxat = -1;
	emin = emax = 0;
	havesc = havecsm = csmle = havele = FALSE;
	csmdist = 0;
	scdir = csmdir = ledir = sccol = skyamb = skyambhdr = lesun = lesunhdr = '0 0 0';
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = amb = ambhdr = lt = lthdr = "";
		eang = ecol = '0 0 0';
		epitch = ehaspitch = hascol = 0;
		ambscale = ltscale = 1;
		d = emsd = 0;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if (key == "classname")
				cn = tok;
			else if (key == "angles")
				eang = stov(tok);
			else if (key == "pitch")
			{
				epitch = stof(tok);
				ehaspitch = TRUE;
			}
			else if (key == "uselightenvangles")
				d = stof(tok);
			else if (key == "maxshadowdistance")
				emsd = stof(tok);	// P1762: env_cascade_light's reach
			else if (key == "color")
			{
				ecol = stov(tok);
				hascol = TRUE;
			}
			else if (key == "_ambient")
				amb = tok;
			else if (key == "_ambienthdr")
				ambhdr = tok;
			else if (key == "_ambientscalehdr")
				ambscale = stof(tok);
			else if (key == "_light")
				lt = tok;
			else if (key == "_lighthdr")
				lthdr = tok;
			else if (key == "_lightscalehdr")
				ltscale = stof(tok);
			else if (key == "onmapspawn")
			{
				if (tokenizebyseparator(strreplace(chr2str(27), ",", tok), ",") < 4)
					continue;
				inp = strtolower(argv(1));
				p = stof(argv(3));
				if (inp == "setbloomscale" && p > bat)
				{
					bat = p;
					bloom = max(0, stof(argv(2)));
				}
				else if (inp == "setautoexposuremin" && p > eminat)
				{
					eminat = p;
					emin = stof(argv(2));
				}
				else if (inp == "setautoexposuremax" && p > emaxat)
				{
					emaxat = p;
					emax = stof(argv(2));
				}
			}
		}
		if (cn == "shadow_control" && !havesc)
		{
			if (eang == '0 0 0')
				eang = '80 30 0';	// CShadowControl::KeyValue's substitute for no angles
			p = eang_x * (M_PI / 180);
			y = eang_y * (M_PI / 180);
			scdir = [cos(p) * cos(y), cos(p) * sin(y), 0 - sin(p)];
			sccol = hascol ? ecol * (1 / 255) : '1 1 1' * (64 / 255);	// the keyvalue's default "64 64 64"
			havesc = TRUE;
		}
		else if (cn == "light_environment" && !havele)
		{
			p = (ehaspitch ? epitch : eang_x) * (M_PI / 180);
			y = eang_y * (M_PI / 180);
			ledir = [cos(p) * cos(y), cos(p) * sin(y), sin(p)];
			havele = TRUE;
			skyamb = Sun_SkyAmbient(FALSE, lt, lthdr, ltscale, amb, ambhdr, ambscale);
			skyambhdr = Sun_SkyAmbient(TRUE, lt, lthdr, ltscale, amb, ambhdr, ambscale);
			lesun = Sun_Direct(FALSE, lt, lthdr, ltscale);	// P1780
			lesunhdr = Sun_Direct(TRUE, lt, lthdr, ltscale);
		}
		else if (cn == "env_cascade_light" && !havecsm)
		{
			p = eang_x * (M_PI / 180);
			y = eang_y * (M_PI / 180);
			csmdir = [cos(p) * cos(y), cos(p) * sin(y), sin(p)];
			csmle = (d != 0);
			csmdist = emsd;
			havecsm = TRUE;
		}
	}
	cvar_set("r_bloom_mapscale", ftos(bloom));

	// Which lighting is drawn only matters to the exposure test and to a map whose HDR keys change the sky ambient;
	// asking reads the BSP header (Emit_MapHDR: the whole file, once per map and hl2_favour_ldr).  mapname, not
	// serverkey("map"): that can still be "" or the previous map here (P948).
	hdrk = 0;
	autoexp = (cvar("vbsp_autoexposure") && cvar_type("r_autoexposure"));	// P1764 (an older engine has no r_autoexposure)
	if (cvar("vbsp_exposure") || skyamb != skyambhdr)
		hdrk = Emit_MapHDR(CL_WorldShortName());	// -1: not read (a map over EM_BSPREAD)
	hdr = hdrk == 1;
	if (hdr)
	{
		skyamb = skyambhdr;
		lesun = lesunhdr;
	}

	// Exposure test: Source's band (values above 0 count; defaults 0.5..2; min over max raises max) clamped round 1.
	// An LDR-lit map has no tonemap: 1.  vbsp_exposure 0 hands r_exposure back to the player.
	if (emin <= 0)
		emin = 0.5;
	if (emax <= 0)
		emax = 2;
	if (emin > emax)
		emax = emin;
	expo = hdr ? bound(emin, 1, emax) : 1;
	// P1764: Source's auto-exposure in the map's band; it replaces the fixed test exposure.  The engine applies it only
	// on a Source map drawn with its HDR lighting (the plugin's own choice), so no BSP read here.
	sun_aemin = emin;
	sun_aemax = emax;
	Sun_ApplyAutoExposure(autoexp);
	if (cvar("vbsp_exposure") && !(autoexp && hdr))
	{
		cvar_set("r_exposure", ftos(expo));
		cvar_set("_vbsp_exposure_set", "1");
	}
	else if (cvar("_vbsp_exposure_set"))
	{
		cvar_set("r_exposure", cvar_defstring("r_exposure"));
		cvar_set("_vbsp_exposure_set", "0");
	}

	if (havesc)
		thr = scdir;
	else if (havecsm && csmle && havele)
		thr = ledir;
	else if (havecsm)
		thr = csmdir;
	else
		thr = stov(cvar_defstring("r_shadows_throwdirection"));
	if (thr != '0 0 0')
		cvar_set("r_shadows_throwdirection", sprintf("%g %g %g", thr_x, thr_y, thr_z));
	// No shadow_control: CClientShadowMgr::LevelInitPreEntity's min(1, 3 x sky ambient + 0.3).
	if (!havesc)
		sccol = [min(1, 3 * skyamb_x + 0.3), min(1, 3 * skyamb_y + 0.3), min(1, 3 * skyamb_z + 0.3)];
	cvar_set("r_shadows_color", sprintf("%g %g %g", sccol_x, sccol_y, sccol_z));
	// A cascade map's lightmap holds the sun's shadows: a dynamic one takes the sun out, down to the sky's share.
	v = '0 0 0';
	if (havecsm && havele)
		v = [Sun_SRGB(skyamb_x), Sun_SRGB(skyamb_y), Sun_SRGB(skyamb_z)];
	cvar_set("r_shadows_sunfloor", sprintf("%g %g %g", v_x, v_y, v_z));
	// P1780: Strata bakes a static prop's direct sun into its .vhv alpha (the plugin keeps it only on a v25 BSP); the
	// shader adds this x alpha where the cascades leave the prop lit.  vbsp_vhvsun calibrated on bhop_canals' street
	// lamp against Momentum's sunlit/shaded sides.
	v = '0 0 0';
	if (havecsm && havele && cvar("hl2_bspversion") >= 25)	// the plugin keeps the .vhv alpha only there (255 elsewhere)
		v = lesun * cvar("vbsp_vhvsun");
	if (cvar_type("r_shadows_vhvsun"))
		cvar_set("r_shadows_vhvsun", sprintf("%g %g %g", v_x, v_y, v_z));
	// P1762: a cascade map's shadows reach as far as its env_cascade_light says (canals 4000), else the engine default.
	if (cvar_type("r_shadows_cascade_dist"))
		cvar_set("r_shadows_cascade_dist", (havecsm && csmdist > 0) ? ftos(bound(512, csmdist, 8192)) : cvar_defstring("r_shadows_cascade_dist"));
	dprint(sprintf("maplight: bloom %g; exposure %g (band %g..%g, %s lighting)%s\n", bloom, expo, emin, emax,
		hdrk < 0 ? "unread" : hdr ? "HDR" : "LDR", autoexp ? ", auto where HDR" : cvar("vbsp_exposure") ? ", applied" : ", not applied"));
	dprint(sprintf("maplight: shadows thrown %v (%s), colour %v, sun floor %v\n", thr,
		havesc ? "shadow_control" : havecsm ? "env_cascade_light" : "engine default", sccol, v));
};

void() Sun_Draw =
{
	local vector eye, fwd, se, rt, up, d, fov;
	local float dot, ga, target, i, sky, sksc;

	if (!sun_have || !cvar("vbsp_sun"))
		return;
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	dot = fwd * sun_dir;
	if (dot <= 0)
	{
		sun_vis = 0;
		sun_traced = FALSE;
		return;                 // behind the view: nothing of it is on screen
	}
	Sun_ProbeInit();
	// P1804: the fraction of the disc's core that reaches the sky, in the world and then through the 3D skybox (its eye
	// sky_camera + view / scale, as cl_main.qc draws it) -- Source fades the noz sprite by a pixel query (C_Sun's glow
	// overlay), so hills, skybox geometry and solid props cover it part-way (Lex 25 Nov: "sun sprite should be blocked by
	// 3d skybox geometry"). Nine rays: the centre and eight at half the quad's radius. Traced only with the sun near the
	// screen, and again only once the eye has moved.
	fov = getproperty(VF_FOV);
	if (fov_x <= 0 || fov_y <= 0)
	{	// clearscene zeroes VF_FOV until renderscene computes it (view.c V_ApplyAFov): the user's fov, a 4:3 width under
		// scr_fov_mode 4, widened by the view's aspect -- linearly, which overestimates the angle (errs wide)
		ga = getproperty(VF_AFOV);
		if (ga <= 0)
			ga = cvar("fov");
		if (ga <= 0)
			ga = 90;
		fov = getproperty(VF_SIZE);
		fov = [ga * max(1, (fov_y > 0) ? fov_x / fov_y * 0.75 : 1.4), ga, 0];
	}
	if (dot < cos(min(89, sqrt(fov_x * fov_x + fov_y * fov_y) * 0.5 + 12) * M_PI / 180))
	{
		sun_vis = 0;
		sun_traced = FALSE;
		return;                 // well off screen
	}
	sky = (vbsp_skyroom_have && cvar("vbsp_skyroom"));
	if (sun_traced && vlen(eye - sun_tracedeye) < 0.5 && sky == sun_tracedsky)
		target = sun_target;
	else
	{
		se = eye;
		if (sky)
		{
			sksc = (vbsp_skyroom_scale > 0) ? vbsp_skyroom_scale : 16;
			se = vbsp_skyroom_pos + eye * (1 / sksc);
		}
		rt = normalize(crossproduct(sun_dir, '0 0 1'));
		if (rt == '0 0 0')
			rt = '1 0 0';
		up = normalize(crossproduct(rt, sun_dir));
		target = 0;
		for (i = 0; i < 9; i = i + 1)
		{
			d = sun_dir;
			if (i)
				d = normalize(sun_dir + (rt * cos(i * 45 * M_PI / 180) + up * sin(i * 45 * M_PI / 180)) * (sun_size * 0.5 / 100));
			traceline(eye, eye + d * 32768, MOVE_NOMONSTERS, sun_probe);
			// SURF_SKY does not come through a VBSP trace; the side's name does (cl_emit.qc's rain).
			if (trace_fraction < 1 && substring(strtolower(trace_surfacename), 0, 4) != "sky/")
				continue;
			if (sky)
			{
				traceline(se, se + d * 32768, MOVE_NOMONSTERS, sun_probe);
				if (trace_fraction < 1 && substring(strtolower(trace_surfacename), 0, 4) != "sky/")
					continue;
			}
			target = target + 1 / 9;
		}
		target = (target > 0.99) ? 1 : target;
		sun_traced = TRUE;
		sun_tracedeye = eye;
		sun_tracedsky = sky;
		sun_target = target;
	}
	if ((target > 0) != sun_seen)
	{
		sun_seen = (target > 0);
		dprint(sprintf("env_sun: %s\n", sun_seen ? "visible" : strcat("hidden by ", trace_surfacename)));
	}
	sun_vis = (sun_vis < target) ? min(target, sun_vis + frametime / 0.05) : max(target, sun_vis - frametime / 0.05);
	if (sun_vis <= 0)
		return;
	Sun_Quad(sun_mat, eye, sun_size, sun_col, sun_vis);
	ga = bound(0, (dot - 0.9) / 0.1 * 0.75, 0.75);
	Sun_Quad(sun_omat, eye, sun_osize * 6, sun_ocol, ga * sun_vis);
};
