/*
  P1746: an admin's map upload, F8 (ui_mapupload), in the main menu and over a game.

  Pick a .bsp (the list, Browse, or a file dropped on the window), a screenshot from the grid (screenshots/<map>_*
  or one dropped), the tier, stages and bonuses, and the local zone file; Upload sends it to play.proto.bar/mapup
  (surfd/mapupd.py), which checks the linked Steam account holds the map role and publishes it for everyone.

  The files are hashed as soon as they are chosen (FILE_READSTREAM, a slice a frame) and a code for the manifest is
  asked for once it stops changing, so the press on Upload can sign at once: friends_sign op "mapupload" over the
  manifest's SHA-256, which on a lobby the engine signs only under a device's press (cl_receipt.c). Each file then
  goes as its own uri_postfile (the map gzipped), with uri_progress driving the bar.
*/
#ifndef MUP_BASE   // a test build only (fteqcc -DMUP_BASE): a server must never choose where a proof goes
#define MUP_BASE "https://play.proto.bar/mapup/api/"
#endif
#define MUP_MAXMAPS 400
#define MUP_MAXSHOTS 24
#define MUP_BYTES 1073741823i       // FS_ARCHIVE_BYTES: the engine's uri_postfile cap is 1 GiB
#define MUP_HASHSTEP 65536i         // file_sha256_step's most a call
#define MUP_HASHCALLS 160           // ~10 MB a frame
#define MUP_CODE_LIFE 480           // s a code is used for (the service's is 600)
#define MUP_READSTREAM 10           // sh_streamfile.qc's FS_FILE_READSTREAM (that file needs fwritepathstatus, not in menu)
#define MUP_READNL 4                // FILE_READNL (the menu defs lack it): fgets gives the whole file
string(float fh, int quota) MUp_HashStep = #0:file_sha256_step;
__int64(float fh) MUp_StreamSize = #0:fsize64;
float(string url, float id, string mimetype, string head, string path, float flags) uri_postfile = #0:uri_postfile;
vector(float id) uri_progress = #0:uri_progress;
float(float kind) sys_openfiledialog = #0:sys_openfiledialog;

float mup_back, mup_inited;         // mup_open is m_main.qc's (it draws and routes the screen)
float mup_maps, mup_shots, mup_pics;   // strbufs: map paths, picture paths, pictures loaded
float mup_listed_at;
vector mup_mapscroll, mup_shotscroll;
string mup_filter; float mup_filtercur;
string mup_bsp, mup_shot, mup_zone;          // chosen paths ("" none)
string mup_name; float mup_namecur;
string mup_author; float mup_authorcur;
string mup_shotfor;                          // the name the grid was listed for
float mup_mode, mup_tier, mup_staged, mup_stages, mup_bonuses, mup_usezone, mup_allshots;
// hashes: 1 map, 2 picture, 3 zone
string mup_sha1, mup_sha2, mup_sha3, mup_hpath1, mup_hpath2, mup_hpath3;
int mup_size1, mup_size2, mup_size3;
float mup_hkind, mup_hfh;                    // the file being hashed (fh + 1), its kind
int mup_hdone, mup_htotal;
// the code for the current manifest
string mup_msha, mup_nonce, mup_noncefor, mup_creqfor;   // creqfor: the manifest the code in flight was asked for
float mup_nonceat, mup_creq, mup_changed;
string mup_up1, mup_up2, mup_up3;            // the files an upload sends, fixed at its press (the window may change)
float mup_sentat, mup_wasopen;               // when the request in flight went; the menu was open before F8
// the upload
float mup_state;                             // 0 editing, 1 begin, 2 a file, 3 finish, 4 done, 5 refused
float mup_req, mup_partreq, mup_partsdone;
string mup_session, mup_left, mup_part, mup_note;
float mup_totalkb, mup_donekb;

string(string old, string v) MUp_Keep =
{
	local string c;
	c = strzone(v);
	if (old != "") strunzone(old);
	return c;
};

// what the service accepts as a name (mapupd.NAME)
float(string n) MUp_NameOK =
{
	local float i, c, l;
	l = strlen(n);
	if (l < 6 || l > 64) return FALSE;
	if (substring(n, 0, 5) != "surf_" && substring(n, 0, 5) != "bhop_") return FALSE;
	for (i = 0; i < l; i = i + 1)
	{
		c = str2chr(n, i);
		if (!((c >= 97 && c <= 122) || (c >= 48 && c <= 57) || c == 95 || c == 45)) return FALSE;
	}
	return TRUE;
};

string(string p) MUp_Base =
{
	local float i;
	for (i = strlen(p) - 1; i >= 0; i = i - 1)
		if (str2chr(p, i) == 47) return substring(p, i + 1, -1);
	return p;
};
string(string p) MUp_Stem =
{
	local string b;
	local float i;
	b = MUp_Base(p);
	for (i = strlen(b) - 1; i > 0; i = i - 1)
		if (str2chr(b, i) == 46) return substring(b, 0, i);
	return b;
};
string(string p) MUp_Ext =
{
	local string b;
	local float i;
	b = MUp_Base(p);
	for (i = strlen(b) - 1; i > 0; i = i - 1)
		if (str2chr(b, i) == 46) return strtolower(substring(b, i + 1, -1));
	return "";
};
// letters, digits, _ and - of a file's stem, lowercased: the name field's first guess
string(string s) MUp_CleanName =
{
	local float i, c;
	local string o;
	s = strtolower(s);
	o = "";
	for (i = 0; i < strlen(s) && i < 64; i = i + 1)
	{
		c = str2chr(s, i);
		if ((c >= 97 && c <= 122) || (c >= 48 && c <= 57) || c == 95 || c == 45) o = strcat(o, chr2str(c));
	}
	return o;
};

void() MUp_PicsFree =
{
	local float i;
	if (!mup_inited) return;
	for (i = 0; i < buf_getsize(mup_pics); i = i + 1)
		free_pic(bufstr_get(mup_pics, i));
	buf_del(mup_pics);
	mup_pics = buf_create();
};

// the gamedir's own loose maps, and dropped ones (the engine reads nothing else for an upload)
void() MUp_ListMaps =
{
	local searchhandle h;
	local float i, n, pass;
	local string f, pkg;
	buf_del(mup_maps);
	mup_maps = buf_create();
	for (pass = 0; pass < 2; pass = pass + 1)
	{
		h = search_begin(pass ? "maps/*.bsp" : "dropped/*.bsp", SB_FULLPACKAGEPATH | SB_NAMESORT, TRUE);
		if (h < 0) continue;
		n = search_getsize(h);
		for (i = 0; i < n && buf_getsize(mup_maps) < MUP_MAXMAPS; i = i + 1)
		{
			f = search_getfilename(h, i);
			pkg = strtolower(search_getpackagename(h, i));
			// a package or another game's mount cannot be read as a loose file
			if (strstrofs(pkg, ".pk3") >= 0 || strstrofs(pkg, ".zip") >= 0 || strstrofs(pkg, ".vpk") >= 0
				|| strstrofs(pkg, "steam:") >= 0 || strstrofs(pkg, "downloads/") >= 0)
				continue;
			bufstr_add(mup_maps, f, TRUE);
		}
		search_end(h);
	}
	mup_listed_at = time;
};

// screenshots of this map (screenshots/<name>_*), or every one; dropped pictures first. The newest MUP_MAXSHOTS.
void() MUp_ListShots =
{
	local searchhandle h;
	local float i, n, pass;
	local string pat, f;
	MUp_PicsFree();
	buf_del(mup_shots);
	mup_shots = buf_create();
	mup_shotfor = MUp_Keep(mup_shotfor, mup_name);
	for (pass = 0; pass < 2; pass = pass + 1)
	{
		if (pass == 0) pat = "dropped/*";
		else if (mup_allshots || mup_name == "") pat = "screenshots/*";
		else pat = strcat("screenshots/", mup_name, "_*");
		h = search_begin(pat, SB_NAMESORT, TRUE);
		if (h < 0) continue;
		n = search_getsize(h);
		for (i = n - 1; i >= 0 && buf_getsize(mup_shots) < MUP_MAXSHOTS; i = i - 1)
		{
			f = search_getfilename(h, i);
			pat = MUp_Ext(f);
			if (pat == "png" || pat == "jpg" || pat == "jpeg" || pat == "tga")
				bufstr_add(mup_shots, f, TRUE);
		}
		search_end(h);
	}
};

void(string path) MUp_PickMap;
void() MUp_ZoneFind =
{
	local string z;
	z = strcat("data/maps/zones/local/", mup_name, ".json");
	if (mup_name != "" && ui_file_exists(z))
	{
		if (mup_zone == "" || substring(mup_zone, 0, 8) != "dropped/")
		{
			if (strcmp(mup_zone, z)) mup_usezone = FALSE;   // found, not attached: the admin's click attaches it
			mup_zone = MUp_Keep(mup_zone, z);
		}
	}
	else if (mup_zone != "" && substring(mup_zone, 0, 8) != "dropped/")
	{
		mup_zone = MUp_Keep(mup_zone, "");
		mup_usezone = FALSE;
	}
};

void(float kind, string path, string sha, int size) MUp_SetHash;
// every slot hashed again: a file chosen under the same path may have changed (a recompile, a fresh drop)
void() MUp_Rehash =
{
	MUp_SetHash(1, "", "", 0i); MUp_SetHash(2, "", "", 0i); MUp_SetHash(3, "", "", 0i);
};
void(string path) MUp_PickMap =
{
	local string n;
	MUp_Rehash();
	mup_bsp = MUp_Keep(mup_bsp, path);
	n = MUp_CleanName(MUp_Stem(path));
	mup_name = MUp_Keep(mup_name, n);
	mup_namecur = strlen(mup_name);
	mup_mode = (substring(n, 0, 5) == "bhop_");
	MUp_ZoneFind();
	MUp_ListShots();
	// no picture is chosen for the admin: a server can send `screenshot <name>`, so one in the grid may not be theirs
	if (mup_shot != "" && substring(mup_shot, 0, 8) != "dropped/") mup_shot = MUp_Keep(mup_shot, "");
};
// what the window may pick, whatever the console passes (ui_mapupload pick|shot|zone): maps/ or dropped/ maps, screenshots/
// or dropped/ pictures, this name's local zone file or a dropped one -- never another data/ path a server can write
float(string p, float kind) MUp_PathOK =
{
	local string e;
	e = MUp_Ext(p);
	if (strstrofs(p, "..") >= 0 || strstrofs(p, "\\") >= 0 || strstrofs(p, ":") >= 0) return FALSE;
	if (kind == 1) return (e == "bsp" && (substring(p, 0, 5) == "maps/" || substring(p, 0, 8) == "dropped/"));
	if (kind == 2) return ((e == "png" || e == "jpg" || e == "jpeg" || e == "tga")
		&& (substring(p, 0, 12) == "screenshots/" || substring(p, 0, 8) == "dropped/"));
	return (e == "json" && (substring(p, 0, 22) == "data/maps/zones/local/" || substring(p, 0, 8) == "dropped/"));
};
// what a zone file holds, shown beside its chip so the admin knows what they attach: "" when it does not read
string mup_zonesumfor, mup_zonesum;
string(string p) MUp_ZoneSummary =
{
	local float fh, root, tracks, stages, bonuses;
	local string body;
	if (!strcmp(p, mup_zonesumfor)) return mup_zonesum;
	mup_zonesumfor = MUp_Keep(mup_zonesumfor, p);
	mup_zonesum = MUp_Keep(mup_zonesum, "does not read as a zone file");
	fh = fopen(p, MUP_READNL);
	if (fh < 0) return mup_zonesum;
	body = fgets(fh);
	fclose(fh);
	if (!ZoneFile_Valid(body)) return mup_zonesum;
	root = json_parse(body);
	tracks = json_find_object_child(root, "tracks");
	stages = json_get_length(json_find_object_child(json_find_object_child(json_find_object_child(tracks, "main"), "zones"), "segments"));
	bonuses = json_get_length(json_find_object_child(tracks, "bonuses"));
	json_free(root);
	mup_zonesum = MUp_Keep(mup_zonesum, sprintf("%s, %g bonus%s", (stages > 1) ? sprintf("%g stages", stages) : "linear",
		bonuses, (bonuses == 1) ? "" : "es"));
	return mup_zonesum;
};

void() MUp_Init =
{
	if (mup_inited) return;
	mup_inited = TRUE;
	mup_maps = buf_create(); mup_shots = buf_create(); mup_pics = buf_create();
	mup_filter = ""; mup_name = ""; mup_author = ""; mup_bsp = ""; mup_shot = ""; mup_zone = "";
	mup_sha1 = mup_sha2 = mup_sha3 = mup_hpath1 = mup_hpath2 = mup_hpath3 = "";
	mup_msha = mup_nonce = mup_noncefor = mup_session = mup_left = mup_part = mup_note = mup_shotfor = "";
	mup_creqfor = mup_up1 = mup_up2 = mup_up3 = "";
	mup_stages = 2;
	registercvar("ui_dropfiles", "0", 0);
};

void() MUp_Open =
{
	MUp_Init();
	if (!mup_open) { mup_back = menu_screen; mup_wasopen = menu_active; }
	mup_open = TRUE;
	if (!MUp_Busy()) MUp_Rehash();
	menu_screen = SCREEN_MAPUPLOAD;
	cvar_set("ui_dropfiles", "1");
	if (time - mup_listed_at > 5 || !buf_getsize(mup_maps)) MUp_ListMaps();
	MUp_ListShots();
};

// the window gone, the menu left as it is (m_close calls this)
void() MUp_Hide =
{
	if (!mup_open) return;
	mup_open = FALSE;
	cvar_set("ui_dropfiles", "0");
	MUp_PicsFree();
	if (mup_hfh) { fclose(mup_hfh - 1); mup_hfh = 0; }
	if (!MUp_Busy()) MUp_Rehash();
	if (menu_screen == SCREEN_MAPUPLOAD) menu_screen = (mup_back == SCREEN_MAPUPLOAD) ? SCREEN_MAIN : mup_back;
	sui_text_unfocus();
};
void() MUp_Close =
{
	if (!mup_open) return;
	MUp_Hide();
	if (clientstate() == 2 && !mup_wasopen) m_close();   // F8 over a game goes back to it
};

// the engine copied a dropped or picked file to dropped/<name> (pr_menu.c MP_FileDropped)
void(string path, string name) Menu_FileDropped =
{
	local string e;
	if (!mup_open) return;
	if (MUp_Busy()) { mup_note = MUp_Keep(mup_note, "Wait for this upload to finish before dropping more files."); return; }
	MUp_Rehash();
	e = MUp_Ext(path);
	if (e == "bsp")
	{
		MUp_ListMaps();
		MUp_PickMap(path);
		mup_note = MUp_Keep(mup_note, sprintf("Map: %s", name));
	}
	else if (e == "json")
	{
		mup_zone = MUp_Keep(mup_zone, path);
		mup_usezone = TRUE;
		mup_note = MUp_Keep(mup_note, sprintf("Zone file: %s", name));
	}
	else if (e == "png" || e == "jpg" || e == "jpeg" || e == "tga")
	{
		MUp_ListShots();
		mup_shot = MUp_Keep(mup_shot, path);
		mup_note = MUp_Keep(mup_note, sprintf("Picture: %s", name));
	}
	else
		mup_note = MUp_Keep(mup_note, sprintf("%s is not a map, a picture (.png .jpg .tga) or a zone file.", name));
	if (mup_state >= 4) mup_state = 0;
};

// The file a hash slot holds, "" when it holds none. kind: 1 map, 2 picture, 3 zone.
string(float kind) MUp_Want =
{
	if (kind == 1) return mup_bsp;
	if (kind == 2) return mup_shot;
	return mup_usezone ? mup_zone : "";
};
string(float kind) MUp_Hashed = { return (kind == 1) ? mup_hpath1 : (kind == 2) ? mup_hpath2 : mup_hpath3; };
string(float kind) MUp_Sha = { return (kind == 1) ? mup_sha1 : (kind == 2) ? mup_sha2 : mup_sha3; };
int(float kind) MUp_Size = { return (kind == 1) ? mup_size1 : (kind == 2) ? mup_size2 : mup_size3; };
void(float kind, string path, string sha, int size) MUp_SetHash =
{
	if (kind == 1) { mup_hpath1 = MUp_Keep(mup_hpath1, path); mup_sha1 = MUp_Keep(mup_sha1, sha); mup_size1 = size; }
	else if (kind == 2) { mup_hpath2 = MUp_Keep(mup_hpath2, path); mup_sha2 = MUp_Keep(mup_sha2, sha); mup_size2 = size; }
	else { mup_hpath3 = MUp_Keep(mup_hpath3, path); mup_sha3 = MUp_Keep(mup_sha3, sha); mup_size3 = size; }
};

// One frame's hashing: a file chosen and not yet hashed is opened, then stepped ~10 MB a frame.
void() MUp_HashFrame =
{
	local float k, i, fh;
	local string want, h;
	local __int64 disk;
	h = "";
	if (!checkbuiltin(MUp_HashStep) || !checkbuiltin(MUp_StreamSize)) return;
	if (mup_hfh && strcmp(MUp_Want(mup_hkind), MUp_Hashed(mup_hkind)))
	{	// the choice moved on while it hashed
		fclose(mup_hfh - 1); mup_hfh = 0;
		MUp_SetHash(mup_hkind, "", "", 0i);
	}
	if (!mup_hfh)
	{
		for (k = 1; k <= 3; k = k + 1)
		{
			want = MUp_Want(k);
			if (want == "" || !strcmp(want, MUp_Hashed(k))) continue;
			MUp_SetHash(k, want, "", 0i);
			fh = fopen(want, MUP_READSTREAM);
			if (fh < 0) { MUp_SetHash(k, want, "!", 0i); continue; }
			disk = MUp_StreamSize(fh);
			if (disk < (__int64)1i || disk > (__int64)MUP_BYTES) { fclose(fh); MUp_SetHash(k, want, "!", 0i); continue; }
			mup_hfh = fh + 1; mup_hkind = k; mup_htotal = (int)disk; mup_hdone = 0i;
			MUp_SetHash(k, want, "", mup_htotal);
			break;
		}
		if (!mup_hfh) return;
	}
	for (i = 0; i < MUP_HASHCALLS; i = i + 1)
	{
		h = MUp_HashStep(mup_hfh - 1, MUP_HASHSTEP);
		mup_hdone = mup_hdone + MUP_HASHSTEP;
		if (h != "") break;
	}
	if (h == "") return;
	fclose(mup_hfh - 1); mup_hfh = 0;
	MUp_SetHash(mup_hkind, MUp_Hashed(mup_hkind), (h == "!") ? "!" : h, MUp_Size(mup_hkind));
};

// mapupd.AUTHOR: letters, digits, space, _ . ' - (empty is fine)
float(string a) MUp_AuthorOK =
{
	local float i, c;
	if (strlen(a) > 40) return FALSE;
	for (i = 0; i < strlen(a); i = i + 1)
	{
		c = str2chr(a, i);
		if (!((c >= 97 && c <= 122) || (c >= 65 && c <= 90) || (c >= 48 && c <= 57) || c == 32 || c == 95 || c == 46 || c == 39 || c == 45))
			return FALSE;
	}
	return TRUE;
};
// Where an upload may start: the main menu, a game this client hosts, or a lobby the directory lists. A server's code
// can write the zone files an upload attaches (data/maps/zones/local), so an unknown server's is not trusted with one.
float() MUp_Official =
{
	local string sv, ip, host;
	local float i;
	if (clientstate() != 2 || isserver()) return TRUE;
	// the directory hands out play.proto.bar:<port> (surfd's public host), and a join connects by that name
	sv = strtolower(serverkey("servername"));
	ip = serverkey("ip");
	host = substring(sv, 0, strstrofs(sv, ":"));
	if (host == "play.proto.bar") return TRUE;
	for (i = 0; i < Lob_Count(); i = i + 1)
		if (!strcmp(strtolower(Lob_Addr(i)), sv) || !strcmp(Lob_Addr(i), ip)) return TRUE;
	return FALSE;
};

// what's still missing, as the line under Upload says it; "" when the manifest is whole
string() MUp_Missing =
{
	local float k;
	if (mup_bsp == "") return "Choose a map: pick one from the list, Browse, or drop a .bsp on the window.";
	if (!MUp_NameOK(mup_name)) return "The name must be surf_ or bhop_ then lowercase letters, digits, _ or -.";
	if (mup_mode && !(mup_usezone && mup_zone != "")) return "A bhop map needs its zone file.";
	if (!MUp_AuthorOK(strtrim(mup_author))) return "The author name may use letters, digits, spaces and _ . ' - only.";
	for (k = 1; k <= 3; k = k + 1)
		if (MUp_Want(k) != "")
		{
			if (strcmp(MUp_Want(k), MUp_Hashed(k)) || MUp_Sha(k) == "") return "Reading the files...";
			if (MUp_Sha(k) == "!") return sprintf("%s cannot be read (it must be a loose file under 1 GB).", MUp_Base(MUp_Want(k)));
		}
	if (mup_shot != "" && mup_size2 > 16777216i) return "The picture is over 16 MB: pick a smaller one.";
	if (mup_usezone && mup_zone != "" && mup_size3 > 262144i) return "The zone file is over 256 KB.";
	if (!MUp_Official()) return "Upload from the main menu, a game you host, or one of our lobbies.";
	return "";
};

// The manifest the service reads (mapupd.parse_manifest), line for line.
string() MUp_Manifest =
{
	local string shot, zone, au;
	shot = (mup_shot != "") ? sprintf("%s %s %s", mup_sha2, itos(mup_size2), MUp_Ext(mup_shot)) : "-";
	zone = (mup_usezone && mup_zone != "") ? sprintf("%s %s", mup_sha3, itos(mup_size3)) : "-";
	au = strtrim(mup_author);
	if (au == "") au = "-";
	return strcat(sprintf("FTESURF-MAPUP 1\nmap %s\nbsp %s %s\nshot %s\nzone %s\n", mup_name, mup_sha1, itos(mup_size1), shot, zone),
		sprintf("mode %s\ntier %g\nstages %g\nbonuses %g\nlinear %g\nauthor %s\n", mup_mode ? "bhop" : "surf", mup_tier,
			mup_staged ? mup_stages : 0, mup_bonuses, mup_staged ? 0 : 1, au));
};

void(string s) MUp_Fail =
{
	mup_state = 5;
	mup_note = MUp_Keep(mup_note, s);
	print(sprintf("map upload: %s\n", s));
};

// The code for the current manifest, asked for once it has been still for a second and a half
void() MUp_CodeFrame =
{
	local string m;
	if (mup_state != 0 && mup_state != 5) return;
	if (MUp_Missing() != "") return;
	m = strtolower(digest_hex("SHA256", MUp_Manifest()));
	if (strcmp(m, mup_msha)) { mup_msha = MUp_Keep(mup_msha, m); mup_changed = time; }
	if (!strcmp(mup_noncefor, mup_msha) && time - mup_nonceat < MUP_CODE_LIFE) return;
	if (mup_creq || time - mup_changed < 1.5) return;
	if (ms_consent < FS_TERMS_ONLINE) return;
	mup_creq = Lob_NextReq();
	mup_creqfor = MUp_Keep(mup_creqfor, mup_msha);
	if (!uri_post(strcat(MUP_BASE, "challenge"), mup_creq, "application/json", sprintf("{\"manifest\":\"%s\"}", mup_msha)))
	{
		mup_creq = 0;
		mup_changed = time + 30;
	}
};

// Upload's press, from Menu_InputEvent while the button is under the cursor: the one moment the engine signs
void() MUp_Press =
{
	local string proof, body;
	if (!mup_open || (mup_state != 0 && mup_state != 5) || MUp_Missing() != "") return;
	if (ms_consent < FS_TERMS_ONLINE) { MUp_Fail("Accept the online terms first (F2, Terms)."); return; }
	if (!checkbuiltin(uri_postfile) || !checkbuiltin(friends_sign)) { MUp_Fail("This game is too old to upload maps: update it."); return; }
	mup_msha = MUp_Keep(mup_msha, strtolower(digest_hex("SHA256", MUp_Manifest())));
	if (strcmp(mup_noncefor, mup_msha) || time - mup_nonceat >= MUP_CODE_LIFE)
	{
		mup_note = MUp_Keep(mup_note, "Getting ready... press Upload again in a moment.");
		return;
	}
	proof = friends_sign(mup_nonce, "mapupload", mup_msha);
	if (proof == "" || tokenize(proof) != 2)
	{
		MUp_Fail("The game would not sign the upload: it needs a linked Steam account (Settings) and a real click.");
		return;
	}
	body = strcat(MUp_Manifest(), sprintf("nonce %s\npub %s\nsig %s\n", mup_nonce, argv(0), argv(1)));
	mup_noncefor = MUp_Keep(mup_noncefor, "");      // a code signs once
	mup_up1 = MUp_Keep(mup_up1, mup_hpath1); mup_up2 = MUp_Keep(mup_up2, mup_hpath2); mup_up3 = MUp_Keep(mup_up3, mup_hpath3);
	mup_sentat = time;
	mup_req = Lob_NextReq();
	if (!uri_post(strcat(MUP_BASE, "begin"), mup_req, "text/plain", body)) { MUp_Fail("play.proto.bar could not be reached."); return; }
	mup_state = 1;
	mup_partsdone = 0; mup_donekb = 0;
	mup_totalkb = ceil(itof(mup_size1) / 1024) + ((mup_shot != "") ? ceil(itof(mup_size2) / 1024) : 0)
		+ ((mup_usezone && mup_zone != "") ? ceil(itof(mup_size3) / 1024) : 0);
	mup_note = MUp_Keep(mup_note, "Checking your account...");
};

void() MUp_NextPart =
{
	local string which, path, head;
	local float n;
	n = tokenize(mup_left);
	if (n < 1)
	{
		mup_state = 3;
		mup_req = Lob_NextReq();
		mup_sentat = time;
		mup_note = MUp_Keep(mup_note, "Publishing...");
		if (!uri_post(strcat(MUP_BASE, "finish"), mup_req, "text/plain", sprintf("session %s\n", mup_session)))
			MUp_Fail("play.proto.bar could not be reached.");
		return;
	}
	which = argv(0);
	mup_left = MUp_Keep(mup_left, Mmm_Join(1, n));
	path = (which == "bsp") ? mup_up1 : (which == "shot") ? mup_up2 : mup_up3;
	mup_sentat = time;
	mup_part = MUp_Keep(mup_part, which);
	head = sprintf("part?s=%s&p=%s&e=%s", mup_session, which, (which == "bsp") ? "gzip" : "raw");    // checked before the body
	mup_partreq = Lob_NextReq();
	mup_state = 2;
	if (!uri_postfile(strcat(MUP_BASE, head), mup_partreq, "application/octet-stream", "", path, (which == "bsp") ? 1 : 0))
		MUp_Fail(sprintf("%s could not be sent.", MUp_Base(path)));
};

float(float reqid, float code, string body) MUp_Reply =
{
	local float root, ok;
	local string err;
	if (!reqid) return FALSE;
	if (reqid != mup_creq && reqid != mup_req && reqid != mup_partreq) return FALSE;
	root = json_parse(body);
	ok = (!code && json_get_float(json_find_object_child(root, "ok")) == 1);
	err = json_get_string(json_find_object_child(root, "error"));
	if (err == "") err = code ? sprintf("play.proto.bar answered %g.", code) : "The upload service gave no answer.";
	if (reqid == mup_creq)
	{
		mup_creq = 0;
		if (ok)
		{
			mup_nonce = MUp_Keep(mup_nonce, json_get_string(json_find_object_child(root, "nonce")));
			mup_noncefor = MUp_Keep(mup_noncefor, mup_creqfor);
			mup_nonceat = time;
			if (mup_state == 0 && substring(mup_note, 0, 13) == "Getting ready") mup_note = MUp_Keep(mup_note, "Ready: press Upload.");
		}
		else
		{
			mup_changed = time + 30;   // asked again in half a minute
			mup_note = MUp_Keep(mup_note, strcat("Not ready: ", err));
		}
	}
	else if (!ok)
	{
		MUp_Fail(err);
		MUp_Rehash();
	}
	else if (reqid == mup_req && mup_state == 1)
	{
		mup_session = MUp_Keep(mup_session, json_get_string(json_find_object_child(root, "session")));
		mup_left = MUp_Keep(mup_left, json_get_string(json_find_object_child(root, "need")));
		MUp_NextPart();
	}
	else if (reqid == mup_partreq && mup_state == 2)
	{
		mup_partsdone = mup_partsdone + 1;
		mup_donekb = mup_donekb + ceil(itof((mup_part == "bsp") ? mup_size1 : (mup_part == "shot") ? mup_size2 : mup_size3) / 1024);
		MUp_NextPart();
	}
	else if (reqid == mup_req && mup_state == 3)
	{
		mup_state = 4;
		mup_note = MUp_Keep(mup_note, json_get_string(json_find_object_child(root, "note")));
		print(sprintf("map upload: %s\n", mup_note));
		mup_listed_at = 0;
	}
	if (root) json_free(root);
	return TRUE;
};

// ---------------------------------------------------------------------------------------------------------------
float() MUp_Busy = { return (mup_state >= 1 && mup_state <= 3); };

void(vector pos, float w, float frac, string label) MUp_Bar =
{
	sui_style_box(pos, [w, 22], 7, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	if (frac > 0) sui_style_box(pos + '2 2 0', [max(10, (w - 4) * bound(0, frac, 1)), 18], 6, SUI_THEME_GOOD_BG, SUI_THEME_GOOD, 1);
	MT_Place(pos + '10 0 0', [w - 20, 22], label, 16, SUI_THEME_TEXT, 1);
};

void(vector p, float w) MUp_DrawMaps =
{
	local float i, n, y, shown, h;
	local string f, nm, id, flt;
	sui_text(p, SZ_LABEL, "Map file", COL_DIM, 1, 0);
	if (checkbuiltin(sys_openfiledialog))
	if (ui_button("mup_browse", [p_x + w - 100, p_y - 6], [100, 28], "Browse..."))
		if (!sys_openfiledialog(0))
			mup_note = MUp_Keep(mup_note, "No file picker here (install zenity): drag the file onto the window instead.");
	ui_field("mup_filter", p + '0 26 0', [w, 30], mup_filter, mup_filtercur, "Filter your maps (or drop a .bsp here)");
	h = 150;
	n = buf_getsize(mup_maps);
	flt = strtolower(mup_filter);
	shown = 0;
	for (i = 0; i < n; i = i + 1)
		if (flt == "" || strstrofs(strtolower(MUp_Base(bufstr_get(mup_maps, i))), flt) >= 0) shown = shown + 1;
	sui_style_box(p + '0 62 0', [w, h], 7, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	sui_scroll_view_begin("mup_maplist", p + '2 64 0', [w - 4, h - 4], [w - 20, max(h - 4, shown * 24)], mup_mapscroll, '0 10 0');
	y = 0;
	for (i = 0; i < n; i = i + 1)
	{
		f = bufstr_get(mup_maps, i);
		nm = MUp_Base(f);
		if (flt != "" && strstrofs(strtolower(nm), flt) < 0) continue;
		id = strcat("mup_m", ftos(i));
		sui_action_element([0, y], [w - 20, 24], id, sui_noop);
		if (!strcmp(f, mup_bsp)) sui_roundbox([0, y], [w - 20, 24], 6, COL_ROW_SEL, 1);
		else if (sui_is_hovered(id)) sui_roundbox([0, y], [w - 20, 24], 6, COL_ROW_HOVER, 1);
		sui_text([8, y + 4], SZ_LABEL, nm, !strcmp(f, mup_bsp) ? COL_ACCENT : COL_TEXT, 1, 0);
		if (substring(f, 0, 8) == "dropped/") sui_text([w - 110, y + 4], SZ_LABEL, "dropped", COL_DIM, 1, 0);
		if (sui_is_released(id) && !MUp_Busy()) MUp_PickMap(f);
		y = y + 24;
	}
	if (!shown) sui_text('8 8 0', SZ_LABEL, (n ? "No map matches." : "No loose maps here: Browse or drop one."), COL_DIM, 1, 0);
	sui_scroll_view_end();
};

void(vector p, float w) MUp_DrawDetails =
{
	local float x, r, cw;	// name, mode, tier, type, stages and bonuses
	local string t;
	cw = floor((w - 12) / 2);
	sui_text(p, SZ_LABEL, "Name", COL_DIM, 1, 0);
	ui_field("mup_name", p + '0 22 0', [w, 30], mup_name, mup_namecur, "surf_yourmap");
	if (strcmp(mup_name, mup_shotfor) && !sui_text_has_focus("mup_name") && !MUp_Busy()) { MUp_Rehash(); MUp_ZoneFind(); MUp_ListShots(); }
	p_y = p_y + 64;
	sui_text(p, SZ_LABEL, "Mode", COL_DIM, 1, 0);
	x = p_x + 70;
	x = x + ui_chip([x, p_y - 5], "mup_surf", "Surf", !mup_mode) + 6;
	ui_chip([x, p_y - 5], "mup_bhop", "Bhop", mup_mode);
	// the name says the mode (the list and the pool read the prefix): a chip renames it
	if (sui_is_released("mup_surf") && substring(mup_name, 0, 5) == "bhop_") mup_name = MUp_Keep(mup_name, strcat("surf_", substring(mup_name, 5, -1)));
	if (sui_is_released("mup_bhop") && substring(mup_name, 0, 5) == "surf_") mup_name = MUp_Keep(mup_name, strcat("bhop_", substring(mup_name, 5, -1)));
	if (sui_is_released("mup_surf")) mup_mode = 0;
	if (sui_is_released("mup_bhop")) mup_mode = 1;
	if (MUp_NameOK(mup_name)) mup_mode = (substring(mup_name, 0, 5) == "bhop_");   // the name decides (the pool reads it)
	p_y = p_y + 34;
	sui_text(p, SZ_LABEL, "Tier", COL_DIM, 1, 0);
	t = mup_tier ? sprintf("Tier %g", mup_tier) : "Unrated";
	r = MT_Stepper("mup_tier", [p_x + 70, p_y - 6], [w - 70, 28], t, mup_tier ? COL_ACCENT : COL_DIM, mup_tier > 0, mup_tier < 10, TRUE);
	mup_tier = bound(0, mup_tier + r, 10);
	p_y = p_y + 34;
	sui_text(p, SZ_LABEL, "Type", COL_DIM, 1, 0);
	x = p_x + 70;
	x = x + ui_chip([x, p_y - 5], "mup_linear", "Linear", !mup_staged) + 6;
	ui_chip([x, p_y - 5], "mup_stagedc", "Staged", mup_staged);
	if (sui_is_released("mup_linear")) mup_staged = FALSE;
	if (sui_is_released("mup_stagedc")) mup_staged = TRUE;
	p_y = p_y + 34;
	if (mup_staged)
	{
		sui_text(p, SZ_LABEL, "Stages", COL_DIM, 1, 0);
		r = MT_Stepper("mup_stages", [p_x + 70, p_y - 6], [cw - 70, 28], ftos(mup_stages), COL_TEXT, mup_stages > 2, mup_stages < 64, TRUE);
		mup_stages = bound(2, mup_stages + r, 64);
		x = p_x + cw + 12;
	}
	else
		x = p_x;
	sui_text([x, p_y], SZ_LABEL, "Bonuses", COL_DIM, 1, 0);
	r = MT_Stepper("mup_bonuses", [x + 80, p_y - 6], [(mup_staged ? cw : w) - 80, 28], ftos(mup_bonuses), COL_TEXT, mup_bonuses > 0, mup_bonuses < 16, TRUE);
	mup_bonuses = bound(0, mup_bonuses + r, 16);
};

// under the picture grid: who made it, and the zone file
void(vector p, float w) MUp_DrawExtras =
{
	sui_text(p, SZ_LABEL, "Author", COL_DIM, 1, 0);
	ui_field("mup_author", p + '70 -6 0', [w - 70, 28], mup_author, mup_authorcur, "the mapper (optional)");
	if (strlen(mup_author) > 40) mup_author = substring(mup_author, 0, 40);
	p_y = p_y + 36;
	sui_text(p, SZ_LABEL, "Zones", COL_DIM, 1, 0);
	if (mup_zone != "")
	{
		ui_chip([p_x + 70, p_y - 5], "mup_zonechip", mup_usezone ? sprintf("Attached: %s (%s)", MUp_Base(mup_zone), MUp_ZoneSummary(mup_zone))
			: sprintf("Click to attach %s (%s)", MUp_Base(mup_zone), MUp_ZoneSummary(mup_zone)), mup_usezone);
		if (sui_is_released("mup_zonechip")) mup_usezone = !mup_usezone;
	}
	else
		sui_text([p_x + 70, p_y], SZ_LABEL, (mup_name != "") ? "No local zone file for this name (drop a .json)" : "-", COL_DIM, 1, 0);
};

void(vector p, float w, float hgt) MUp_DrawShots =
{
	local float i, n, cols, cw, ch, x, y, rows;
	local string f, id;
	local vector ready;
	sui_text(p, SZ_LABEL, "Picture", COL_DIM, 1, 0);
	x = p_x + w - ui_chip_w("All screenshots");
	ui_chip([x, p_y - 5], "mup_allshots", "All screenshots", mup_allshots);
	if (sui_is_released("mup_allshots")) { mup_allshots = !mup_allshots; MUp_ListShots(); }
	n = buf_getsize(mup_shots);
	cols = 3;
	cw = floor((w - 4 - (cols - 1) * 8) / cols);
	ch = floor(cw * 9 / 16);
	rows = ceil(n / cols);
	sui_style_box(p + '0 26 0', [w, hgt - 26], 7, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	sui_scroll_view_begin("mup_shotgrid", p + '2 28 0', [w - 4, hgt - 30], [w - 18, max(hgt - 30, rows * (ch + 8))], mup_shotscroll, '0 10 0');
	for (i = 0; i < n; i = i + 1)
	{
		f = bufstr_get(mup_shots, i);
		x = (i - floor(i / cols) * cols) * (cw + 8) + 2;
		y = floor(i / cols) * (ch + 8) + 2;
		id = strcat("mup_s", ftos(i));
		sui_action_element([x, y], [cw - 14, ch], id, sui_noop);
		if (checkbuiltin(drawgetimagesize_async))
		{
			ready = drawgetimagesize_async(f);
			if (ready_x <= 0)
			{
				if (buf_getsize(mup_pics) <= i || bufstr_get(mup_pics, i) != f) { precache_pic(f, 0); bufstr_set(mup_pics, i, f); }
				MT_Place([x, y], [cw - 14, ch], "...", 16, COL_DIM, 1);
			}
			else
				sui_pic([x, y], [cw - 14, ch], f, '1 1 1', 1, 0);
		}
		else
			MT_Place([x, y], [cw - 14, ch], MUp_Base(f), 16, COL_DIM, 1);
		if (!strcmp(f, mup_shot)) sui_border_box([x - 2, y - 2], [cw - 10, ch + 4], 3, COL_ACCENT, 1, 0);
		else if (sui_is_hovered(id)) sui_border_box([x - 1, y - 1], [cw - 12, ch + 2], 1, COL_TEXT, 1, 0);
		if (sui_is_released(id) && !MUp_Busy()) mup_shot = MUp_Keep(mup_shot, (!strcmp(f, mup_shot)) ? "" : f);
	}
	if (!n)
		sui_text('10 10 0', SZ_LABEL, (mup_name != "" && !mup_allshots) ? sprintf("No screenshots/%s_* yet (F9 in game, or drop one)", mup_name)
			: "No screenshots yet (F9 in game, or drop one)", COL_DIM, 1, 0);
	sui_scroll_view_end();
};

void(vector screensize) MUp_Draw =
{
	local vector p, q;
	local float w, h, colw, frac;
	local string why, label;
	local vector pr;
	MUp_HashFrame();
	MUp_CodeFrame();
	// an answer that never comes: a request out 90 s, or a file sent and its reply a minute late
	pr = (mup_state == 2) ? uri_progress(mup_partreq) : '0 0 -1';
	if (time - mup_sentat > ((mup_state == 3) ? 330 : 90) && (mup_state == 1 || mup_state == 3))
		MUp_Fail("play.proto.bar did not answer; press Upload to try again.");
	else if (mup_state == 2 && (pr_z < 0 || pr_z >= 3) && time - mup_sentat > 600)
		MUp_Fail("play.proto.bar did not answer the file; press Upload to try again.");
	else if (mup_state == 2 && pr_z >= 0 && pr_z < 3)
		mup_sentat = time;           // still compressing or sending: a big map takes as long as it takes
	w = min(1040, screensize_x - 24);
	h = min(690, screensize_y - 24);
	p = [floor((screensize_x - w) * 0.5), floor((screensize_y - h) * 0.5)];
	sui_style_panel(p, [w, h], 12, 1);
	Font_Set(ui_font_ui);
	sui_text(p + '18 16 0', SZ_HEAD, "Upload a map", COL_TEXT, 1, 0);
	sui_text(p + '18 46 0', SZ_LABEL, "Map admins only: it goes live for everyone. Drop .bsp, pictures or a zone .json on the window.", COL_DIM, 1, 0);
	if (ui_button("mup_close", [p_x + w - 16 - 90, p_y + 14], [90, 30], "Close") && !MUp_Busy())
	{
		MUp_Close();
		return;
	}
	colw = floor((w - 18 * 2 - 24) * 0.42);
	q = p + '18 82 0';
	MUp_DrawMaps(q, colw);
	MUp_DrawDetails(q + '0 230 0', colw);
	MUp_DrawShots(q + [colw + 24, 0], w - 36 - colw - 24, h - 82 - 112 - 80);
	MUp_DrawExtras([q_x + colw + 24, p_y + h - 112 - 66], w - 36 - colw - 24);

	// the bottom strip: status, progress, Upload
	q = [p_x + 18, p_y + h - 96];
	why = MUp_Missing();
	frac = 0;
	label = "";
	if (mup_hfh)
	{
		frac = itof(mup_hdone) / max(1, itof(mup_htotal));
		label = sprintf("Reading %s  %g%%", MUp_Base(MUp_Hashed(mup_hkind)), floor(min(1, frac) * 100));
	}
	else if (mup_state == 2)
	{
		pr = uri_progress(mup_partreq);
		if (pr_z == 1) { frac = pr_x / max(1, pr_y); label = sprintf("Compressing %s  %g%%", MUp_Base(mup_hpath1), floor(frac * 100)); }
		else
		{
			frac = (mup_donekb + ((pr_z >= 2) ? pr_x : 0)) / max(1, mup_totalkb + ((mup_part == "bsp" && pr_y > 0) ? pr_y - ceil(itof(mup_size1) / 1024) : 0));
			label = sprintf("Uploading %s  %g / %g MB  %g%%", mup_part == "bsp" ? "map" : mup_part == "shot" ? "picture" : "zones",
				floor(pr_x / 102.4) / 10, floor(pr_y / 102.4) / 10, floor(min(1, frac) * 100));
		}
	}
	else if (mup_state == 1 || mup_state == 3) { frac = (mup_state == 3); label = mup_note; }
	else if (mup_state == 4) { frac = 1; label = "Published"; }
	MUp_Bar(q, w - 36 - 180, frac, (label != "") ? label : (why != "") ? why : "Ready.");
	if (mup_state != 1 && mup_state != 2 && mup_state != 3)
		ui_button("mup_upload", [p_x + w - 18 - 168, q_y - 4], [168, 30], (mup_state == 4) ? "Upload another" : "Upload", why == "");
	else
		MT_Value([p_x + w - 18 - 168, q_y - 4], [168, 30], "Uploading...", COL_DIM);
	if (mup_state == 4 && sui_is_released("mup_upload"))
	{
		mup_state = 0;
		mup_bsp = MUp_Keep(mup_bsp, ""); mup_name = MUp_Keep(mup_name, ""); mup_shot = MUp_Keep(mup_shot, "");
		mup_zone = MUp_Keep(mup_zone, ""); mup_note = MUp_Keep(mup_note, "");
		MUp_ListMaps();
	}
	if (mup_note != "")
		ui_para([p_x + 18, q_y + 32], w - 36, SZ_LABEL, 20, mup_note,
			(mup_state == 5) ? SUI_THEME_BAD : (mup_state == 4) ? SUI_THEME_GOOD : COL_DIM, TRUE);
};

// Menu_InputEvent's hook: Upload signs on the press itself (a release is not a device's press to the engine)
float(float evtype, float scanx) MUp_Input =
{
	if (!mup_open) return FALSE;
	if (evtype == IE_KEYDOWN && scanx == K_MOUSE1 && sui_is_hovered("mup_upload") && mup_state != 4)
	{
		MUp_Press();
		return FALSE;               // sui still sees the click (the button draws pressed)
	}
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE && sui_text_focus())
	{
		sui_text_unfocus();
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE && !MUp_Busy())
	{
		MUp_Close();
		return TRUE;
	}
	return FALSE;
};

// ui_mapupload pick|shot|zone <gamedir path>, send, status: the console's way through the window (tests; the
// console is the player's own, MP_ConsoleCommand refuses a server's). send signs as the button does.
float(string verb, string arg) MUp_Command =
{
	if (!mup_open) MUp_Open();
	if (MUp_Busy() && (verb == "pick" || verb == "shot" || verb == "zone")) { print("map upload: busy\n"); return TRUE; }
	if ((verb == "pick" && !MUp_PathOK(arg, 1)) || (verb == "shot" && !MUp_PathOK(arg, 2)) || (verb == "zone" && arg != "" && !MUp_PathOK(arg, 3)))
	{
		print("map upload: not a path the window offers\n");
		return TRUE;
	}
	if (verb == "pick") { MUp_PickMap(arg); return TRUE; }
	if (verb == "shot") { mup_shot = MUp_Keep(mup_shot, arg); return TRUE; }
	if (verb == "zone") { mup_zone = MUp_Keep(mup_zone, arg); mup_usezone = (arg != ""); return TRUE; }
	if (verb == "send") { MUp_Press(); return TRUE; }
	if (verb == "status")
	{
		print(sprintf("map upload: state %g name %s map %s shot %s zone %s(%g)\n", mup_state, mup_name, mup_bsp, mup_shot,
			mup_zone, mup_usezone));
		print(sprintf("map upload: missing \"%s\" code %s note \"%s\"\n", MUp_Missing(),
			(!strcmp(mup_noncefor, mup_msha) && mup_msha != "") ? "ready" : "none", mup_note));
		return TRUE;
	}
	print("ui_mapupload [pick|shot|zone <path>|send|status]\n");
	return TRUE;
};
