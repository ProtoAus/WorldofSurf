/*
  P1740 (Lex 23 Nov: "favourite maps, we need an option to click on a map to favourite it, like a star button"):
  a star on every Source map row (over the card's picture, before the compact row's name) toggles the map in
  data/favourites.txt, one lower-case name a line; the Extra group's "favourites" chip lists only them.
  GoldSrc rows have no star yet.  None of the UI fonts has a star glyph (Roboto, GoogleMed, Bebas), so it is
  drawn as polygons, as m_stats.qc draws the crown.
*/
#define FAV_FILE    "data/favourites.txt"
#define FAV_GOLD    '1 0.78 0.22'
#define FAV_TWOSIDED 1024      // CSQC's DRAWFLAG_TWOSIDED (m_stats.qc MS_TWOSIDED)

var float fav_buf = -1;        // strbuf of names; a removed name leaves "" (the file is rewritten without it)
hashtable fav_set;              // P1740 review: the same names for O(1) lookups (ui_refilter asks per row)
float fav_n;                // names held, removals excluded
float fav_ver;              // bumps on every change: the "favourites" filter re-runs on it

void() Fav_Load =
{
	local float fh, have;
	local string l;
	if (fav_buf >= 0)
		return;
	fav_buf = buf_create();
	fav_set = hash_createtab(256, EV_FLOAT);
	fh = fopen(FAV_FILE, FILE_READ);
	if (fh < 0)
		return;
	while ((l = fgets(fh)))
	{
		l = strtolower(strtrim(l));
		have = 1;
		if (l != "")
			have = hash_get(fav_set, l, 0, EV_FLOAT);
		if (!have)
		{
			bufstr_add(fav_buf, l, TRUE);
			hash_add(fav_set, l, 1, HASH_REPLACE | EV_FLOAT);
			fav_n++;
		}
	}
	fclose(fh);
};

float(string mname) Fav_Find =
{
	local float i, n;
	Fav_Load();
	mname = strtolower(mname);
	if (mname == "")
		return -1;
	n = buf_getsize(fav_buf);
	for (i = 0; i < n; i++)
		if (bufstr_get(fav_buf, i) == mname)
			return i;
	return -1;
};

float() Fav_Ver = { return fav_ver; };

float(string mname) Fav_Has =
{
	local float have;
	Fav_Load();
	if (fav_n <= 0 || mname == "")
		return FALSE;
	have = hash_get(fav_set, strtolower(mname), 0, EV_FLOAT);
	return have != 0;
};

void() Fav_Save =
{
	local float fh, i, n;
	local string l;
	fh = fopen(FAV_FILE, FILE_WRITE);
	if (fh < 0)
	{
		print("^3favourites: could not write ", FAV_FILE, "\n");
		return;
	}
	n = buf_getsize(fav_buf);
	for (i = 0; i < n; i++)
	{
		l = bufstr_get(fav_buf, i);
		if (l != "")
			fputs(fh, strcat(l, "\n"));
	}
	fclose(fh);
};

void(string mname) Fav_Toggle =
{
	local float i;
	i = Fav_Find(mname);
	if (i >= 0)
	{
		bufstr_set(fav_buf, i, "");
		hash_delete(fav_set, strtolower(mname));
		fav_n--;
	}
	else if (mname != "")
	{
		bufstr_add(fav_buf, strtolower(mname), TRUE);
		hash_add(fav_set, strtolower(mname), 1, HASH_REPLACE | EV_FLOAT);
		fav_n++;
	}
	fav_ver++;
	Fav_Save();
};

// A five-pointed star of outer radius r centred on c (sui coordinates): the inner pentagon, then the points.
void(vector c, float r, vector col, float a) Fav_StarShape =
{
	local float k, ang;
	local vector ov[5], iv[5], p, q, m;
	for (k = 0; k < 5; k++)
	{
		ang = (k * 72 - 90) * (3.14159265 / 180);
		ov[k] = c + [cos(ang) * r, sin(ang) * r];
		ang = (k * 72 - 54) * (3.14159265 / 180);
		iv[k] = c + [cos(ang) * r * 0.42, sin(ang) * r * 0.42];
	}
	R_BeginPolygon("", FAV_TWOSIDED, TRUE);
	for (k = 0; k < 5; k++)
	{
		p = iv[k];
		sui_transform_point(p);
		R_PolygonVertex(p, '0 0 0', col, a);
	}
	R_EndPolygon();
	for (k = 0; k < 5; k++)
	{
		p = iv[(k + 4) - floor((k + 4) / 5) * 5];
		q = ov[k];
		m = iv[k];
		sui_transform_point(p); sui_transform_point(q); sui_transform_point(m);
		R_BeginPolygon("", FAV_TWOSIDED, TRUE);
		R_PolygonVertex(p, '0 0 0', col, a);
		R_PolygonVertex(q, '0 0 0', col, a);
		R_PolygonVertex(m, '0 0 0', col, a);
		R_EndPolygon();
	}
};

// The star button: a size x size box at pos.  Registered after the row's own element, so the click lands here.
void(vector pos, float size, string id, string mname) Fav_Button =
{
	local float on, hot;
	local vector c;
	if (mname == "")
		return;
	sui_action_element(pos, [size, size], id, sui_noop);
	on = Fav_Has(mname);
	hot = sui_is_hovered(id);
	c = pos + [size, size] * 0.5;
	Fav_StarShape(c + '0 1 0', size * 0.5, '0 0 0', 0.55);     // a shadow, for a light picture
	if (on)
		Fav_StarShape(c, size * 0.46, hot ? FAV_GOLD * 1.15 : FAV_GOLD, 1);
	else
		Fav_StarShape(c, size * 0.46, COL_TEXT, hot ? 0.9 : 0.35);
	sui_tooltip_for(id, on ? "Remove from favourites" : "Add to favourites", 2);
	if (sui_is_released(id))
		Fav_Toggle(mname);
};
