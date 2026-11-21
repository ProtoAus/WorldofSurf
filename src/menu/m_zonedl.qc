/* Refresh the trusted public zone cache BEFORE a picker Play command starts
 * its local server, and (P1707) whenever this client sees a new map. Client-only
 * maps/zones/dl remains non-authoritative. Local editor overrides still win;
 * failed/404/timed-out refreshes keep prior files. */
#define MZD_SOURCE "https://play.proto.bar/ftesurf/maps/zones/local/"
float mzd_req, mzd_until, mzd_at, mzd_ok;
string mzd_map, mzd_play;
// P1707: Mzd_Watch's state. mzd_seen persists across a hosted map's restart, so each first sight restarts once.
string mzd_seen;
float mzd_restart, mzd_due, mzd_boot;
float(string id) Mgs_Find;      // m_goldsrc.qc: a GoldSrc id has no zone file
void(string mapname) ui_playlocal_now;

void(string mapname) Mzd_Fetch =
{
	if (cvar("rec_terms") < FS_TERMS_ONLINE || mzd_req) return;
	if (!Mdl_Made(mapname, MDL_NAMECH, 64)) return;
	if (strcmp(mapname, mzd_map) == 0 && gettime(0) - mzd_at < 60) return;
	if (strlen(mzd_map)) strunzone(mzd_map);
	mzd_map = strzone(mapname); mzd_at = gettime(0); mzd_ok = FALSE;
	mzd_req = Lob_NextReq(); mzd_until = gettime(0) + 8;
	if (!uri_get(strcat(MZD_SOURCE, mapname, ".json"), mzd_req))
		mzd_req = 0;
};

void() Mzd_Pump =
{
	local string play;
	if (mzd_req && gettime(0) > mzd_until)
	{
		mzd_req = 0; mzd_at = gettime(0); mzd_restart = FALSE;
		print("^3zones:^7 refresh timed out; existing zones kept\n");
	}
	if (cvar("rec_terms") < FS_TERMS_ONLINE) { mzd_req = 0; mzd_restart = FALSE; }
	if (!strlen(mzd_play) || mzd_req) return;
	if (cvar("rec_terms") < FS_TERMS_ONLINE || (strcmp(mzd_play, mzd_map) == 0 && gettime(0) - mzd_at < 60))
	{
		play = strzone(mzd_play); strunzone(mzd_play); mzd_play = "";
		ui_playlocal_now(play); strunzone(play);
	}
	else Mzd_Fetch(mzd_play);
};

void(string mapname) Mzd_Play =
{
	if (cvar("rec_terms") < FS_TERMS_ONLINE || !Mdl_Made(mapname, MDL_NAMECH, 64))
	{
		ui_playlocal_now(mapname); return;
	}
	if (strlen(mzd_play)) strunzone(mzd_play);
	mzd_play = strzone(mapname);
	mzd_restart = FALSE;    // P1707: the picker's own refresh comes first; its game starts after it
	Mzd_Pump();
};

// P1707: every new map this client plays -- a lobby's, or one it hosts -- refreshes its published copy in the
// background, so the next local game times with the lobby's table. A hosted game that loaded none (zonecrc ""),
// or the map a launch option's +map spawned before m_init, restarts once: at once when a copy is here, else when
// the refresh lands. With no zones there is no run to lose; a +map's library table is replaced once at boot.
float(string path) Mzd_Exists =
{
	local float fh = fopen(path, FILE_READ);
	if (fh < 0) return FALSE;
	fclose(fh); return TRUE;
};
void(string mapname) Mzd_Restart =
{
	print(sprintf("^5zones:^7 restarting %s with its published zones\n", mapname));
	localcmd(sprintf("map %S\n", mapname));
};
void(string mapname, string zonecrc, float hosting) Mzd_Watch =
{
	local float boot = mzd_boot;
	hosting = (hosting && cvar("sv_zones_curated"));
	if (mzd_due)
	{   // a refresh for this map landed: restart only if it is still the hosted map and still has no zones
		mzd_due = FALSE;
		if (hosting && zonecrc == "" && mapname == mzd_map && mapname == mzd_seen)
		{
			Mzd_Restart(mapname); return;
		}
	}
	if (mapname == "" || mapname == mzd_seen) return;
	if (strlen(mzd_seen)) strunzone(mzd_seen);
	mzd_seen = strzone(mapname);
	mzd_restart = FALSE; mzd_boot = FALSE;
	if (!Mdl_Made(mapname, MDL_NAMECH, 64) || Mgs_Find(mapname) >= 0) return;
	if (Mzd_Exists(strcat("data/maps/zones/curated/", mapname, ".json")))
	{
		if (hosting && (zonecrc == "" || boot))
		{
			Mzd_Restart(mapname); return;
		}
		Mzd_Fetch(mapname);     // refresh for next time; this game keeps the table it loaded
		return;
	}
	Mzd_Fetch(mapname);         // consent, one request and one-minute guards are its own
	mzd_restart = (hosting && (zonecrc == "" || boot) && mzd_req && mzd_map == mapname);
};

float(float id, float code, string body) Mzd_Reply =
{
	if (!mzd_req || id != mzd_req) return FALSE;
	mzd_req = 0; mzd_at = gettime(0);
	mzd_ok = FALSE;
	if (code == 0 || code == 200)
		mzd_ok = ZoneFile_Store(strcat("maps/zones/curated/", mzd_map, ".json"), body);
	if (mzd_ok)
		print(sprintf("^5zones:^7 refreshed %s (saved local overrides retained)\n", mzd_map));
	else
		print(sprintf("^3zones:^7 no valid refresh for %s; existing zones kept\n", mzd_map));
	// P1707: Mzd_Watch restarts from m_draw, where it sees the map now loaded (a reply can land mid-load).
	mzd_due = (mzd_restart && mzd_ok);
	mzd_restart = FALSE;
	return TRUE;
};
