// A local catalog of model/kit pairs, not a player inventory. The VPK alias
// keeps customization maps separate from loose files, downloads and CS:S.
#define PK_ROOT "materials/models/weapons/"
#define PK_ALIAS "materials/ftesurf/legacy/"
#define PK_SHARED "materials/ftesurf/legacy/customization/shared/"
#define PKC_LIMIT 1024i
#define PKC_IDS 11000i
#define PKC_USP 25
#define PKC_GLOCK 26
#define PKC_NAME 0i
#define PKC_FILES 1i
#define PKC_INFO 2i
float wkit_mode, wkit_kind, wkit_avail, wkit_pistol, wkit_primarymodel;
int pk_rand_idum, pk_rand_iy, *pk_rand_iv, pk_wplace_kit, pk_gplace_kit;
float pk_wplace_seed, pk_gplace_seed;
int pkc_count, *pkc_ids, *pkc_index, *pkc_bits;
string *pkc_meta;
void() PKC_Data;

void(int id, int compatibility, string label, string files, string info) PKC_Add =
{
	if (id <= 0i || id >= PKC_IDS || pkc_count >= PKC_LIMIT || pkc_index[id]) return;
	pkc_count += 1i;
	pkc_ids[pkc_count] = id;
	pkc_index[id] = pkc_count;
	pkc_bits[pkc_count] = compatibility;
	pkc_meta[pkc_count * 3i] = label;
	pkc_meta[pkc_count * 3i + 1i] = files;
	pkc_meta[pkc_count * 3i + 2i] = info;
};

void() PK_Register =
{
	local float i;
	pkc_index = (int*)memalloc(PKC_IDS * 4i);
	pkc_ids = (int*)memalloc((PKC_LIMIT + 1i) * 4i);
	pkc_bits = (int*)memalloc((PKC_LIMIT + 1i) * 4i);
	pkc_meta = (string*)memalloc((PKC_LIMIT + 1i) * 12i);
	memfill8((void*)pkc_index, 0i, PKC_IDS * 4i);
	pk_rand_iv = (int*)memalloc(32i * 4i);
	PKC_Data();
	registercvar("cl_wshop_mode", "0", CVAR_ARCHIVE);
	registercvar("cl_wshop_kit", "413", CVAR_ARCHIVE);
	registercvar("cl_wshop_seed", "1", CVAR_ARCHIVE);
	registercvar("cl_wshop_wear", "0.05", CVAR_ARCHIVE);
	registercvar("cl_wshop_gunwear", "0.15", CVAR_ARCHIVE);
	registercvar("cl_wshop_gunfinish", "1", CVAR_ARCHIVE);
	registercvar("cl_wshop_uspkit", "318", CVAR_ARCHIVE);
	registercvar("cl_wshop_glockkit", "1119", CVAR_ARCHIVE);
	registercvar("cl_wshop_scale", "1", CVAR_ARCHIVE);
	registercvar("cl_wshop_rotation", "0", CVAR_ARCHIVE);
	registercvar("cl_wshop_x", "0", CVAR_ARCHIVE);
	registercvar("cl_wshop_y", "0", CVAR_ARCHIVE);
	registercvar("cl_wshop_tint", "0", CVAR_ARCHIVE);
	// Keep the separate enable bit from the original Sporty preview.
	registercvar("cl_wshop_sporty", "0", CVAR_ARCHIVE);
	registercvar("cl_wshop_glovekit", "10018", CVAR_ARCHIVE);
	registercvar("cl_wshop_glovewear", "0.15", CVAR_ARCHIVE);
	for (i = 0; i < 4; i += 1) registercvar(sprintf("cl_wkit_col%g", i), "128 128 128", 0);
	for (i = 0; i < 8; i += 1) registercvar(sprintf("cl_gkit_col%g", i), "128 128 128", 0);
	for (i = 0; i < 5; i += 1) registercvar(sprintf("cl_wkit_opts%g", i), "0 0 0", 0);
	for (i = 0; i < 8; i += 1) registercvar(sprintf("cl_gkit_opts%g", i), "0 0 0", 0);
	registercvar("cl_wkit_place", "0 0 0", 0);
	registercvar("cl_gkit_place", "0 0 0", 0);
};

string(string path) PK_Alias =
{
	if (strstrofs(path, PK_ROOT, 0) != 0) return "";
	return strcat(PK_ALIAS, substring(path, strlen(PK_ROOT), -1));
};
float(string path) PK_Has =
{
	local float f;
	if (!strcmp(path, "$whiteimage")) return TRUE;
	if (!strcmp(path, "")) return FALSE;
	f = fopen(path, FILE_READ);
	if (f < 0) return FALSE;
	fclose(f);
	return TRUE;
};
string(string rel) PK_Asset =
{
	if (!strcmp(rel, "") || !strcmp(rel, "$whiteimage")) return rel;
	return strcat(PK_ALIAS, rel);
};
int(float id) PKC_Index =
{
	if (!pkc_index || id < 1 || id >= (float)PKC_IDS || id != floor(id)) return 0i;
	return pkc_index[(int)id];
};
float(int index, float model) PKC_Matches =
{
	if (!pkc_bits || index <= 0i || index > pkc_count || model == 0) return FALSE;
	if (model < 0) return pkc_bits[index] == (int)model;
	if (model > PKC_GLOCK || pkc_bits[index] < 0i) return FALSE;
	return (pkc_bits[index] & (1i << (int)model)) != 0i;
};
string(int index, int field) PKC_Get =
{
	if (!pkc_meta || index <= 0i || index > pkc_count) return "";
	return pkc_meta[index * 3i + field];
};
vector(int index) PKC_Wear =
{
	if (!index) return '0 1 0.15';
	tokenizebyseparator(PKC_Get(index, PKC_INFO), "|");
	return stov(argv(0));
};
int(float model) PKC_Selected =
{
	local float id;
	local int index;
	if (model < 0) id = cvar("cl_wshop_glovekit");
	else if (model == PKC_USP) id = cvar("cl_wshop_uspkit");
	else if (model == PKC_GLOCK) id = cvar("cl_wshop_glockkit");
	else
	{
		id = cvar("cl_wshop_kit");
		if (id == 1) id = 413;
		else if (id == 2) id = 12;
		else if (id == 3) id = 38;
	}
	index = PKC_Index(id);
	return PKC_Matches(index, model) ? index : 0i;
};
void(int index, float model) PKC_Select =
{
	local string id;
	if (!PKC_Matches(index, model)) return;
	id = itos(pkc_ids[index]);
	if (model < 0) { cvar_set("cl_wshop_glovekit", id); cvar_set("cl_wshop_sporty", "1"); }
	else if (model == PKC_USP) { cvar_set("cl_wshop_uspkit", id); cvar_set("cl_wshop_gunfinish", "1"); }
	else if (model == PKC_GLOCK) { cvar_set("cl_wshop_glockkit", id); cvar_set("cl_wshop_gunfinish", "1"); }
	else { cvar_set("cl_wshop_kit", id); if (!cvar("cl_wshop_mode")) cvar_set("cl_wshop_mode", "1"); }
};

// The live view has at most one local weapon and one pair of gloves. Set their
// uniforms on skin transition, so hundreds of kits share GPU program variants.
void(int index, float glove) PKC_Uniforms =
{
	local float i, count;
	local string prefix;
	prefix = glove ? "cl_gkit_" : "cl_wkit_";
	count = glove ? 8 : 5;
	tokenizebyseparator(PKC_Get(index, PKC_INFO), "|");
	for (i = 0; i < count; i += 1)
		cvar_set(sprintf("%sopts%g", prefix, i), argv(i));
	for (i = 0; i < (glove ? 8 : 4); i += 1)
		cvar_set(sprintf("%scol%g", prefix, i), argv(count + i));
};

// CS:GO places a kit's pattern with Valve's CUniformRandomStream (Numerical Recipes
// ran1, Source SDK vstdlib/random.cpp) seeded by the paint seed: offset X, offset Y,
// then rotation, each drawn from the kit's range. Wear/grunge placement is not CS:GO's.
int() PK_RandomInt =
{
	local int j, k;
	if (pk_rand_idum <= 0i || pk_rand_iy == 0i)
	{
		if (pk_rand_idum >= 0i) pk_rand_idum = 1i;
		else pk_rand_idum = 0i - pk_rand_idum;
		for (j = 39i; j >= 0i; j = j - 1i)
		{
			k = pk_rand_idum / 127773i;
			pk_rand_idum = 16807i * (pk_rand_idum - k * 127773i) - 2836i * k;
			if (pk_rand_idum < 0i) pk_rand_idum = pk_rand_idum + 2147483647i;
			if (j < 32i) pk_rand_iv[j] = pk_rand_idum;
		}
		pk_rand_iy = pk_rand_iv[0];
	}
	k = pk_rand_idum / 127773i;
	pk_rand_idum = 16807i * (pk_rand_idum - k * 127773i) - 2836i * k;
	if (pk_rand_idum < 0i) pk_rand_idum = pk_rand_idum + 2147483647i;
	j = (pk_rand_iy / 67108864i) & 31i;
	pk_rand_iy = pk_rand_iv[j];
	pk_rand_iv[j] = pk_rand_idum;
	return pk_rand_iy;
};
float(float lo, float hi) PK_RandomFloat =
{
	local float f;
	f = (float)PK_RandomInt() / 2147483647;
	if (f > 0.99999988) f = 0.99999988;
	return f * (hi - lo) + lo;
};
// Sets cl_wkit_place / cl_gkit_place (offset x, offset y, rotation) when the kit or seed changes.
void(int index, float glove) PK_Place =
{
	local float seed;
	local vector x, y, r;
	seed = bound(0, floor(cvar("cl_wshop_seed")), 1000);
	if (glove)
	{
		if (index == pk_gplace_kit && seed == pk_gplace_seed) return;
		pk_gplace_kit = index; pk_gplace_seed = seed;
	}
	else
	{
		if (index == pk_wplace_kit && seed == pk_wplace_seed) return;
		pk_wplace_kit = index; pk_wplace_seed = seed;
	}
	if (!index) return;
	tokenizebyseparator(PKC_Get(index, PKC_INFO), "|");
	x = stov(argv(1)); y = stov(argv(2)); r = stov(argv(3));
	pk_rand_idum = 0i - (int)seed;
	pk_rand_iy = 0i;
	x_z = PK_RandomFloat(x_x, x_y);
	y_z = PK_RandomFloat(y_x, y_y);
	r_z = PK_RandomFloat(r_x, r_y);
	cvar_set(glove ? "cl_gkit_place" : "cl_wkit_place", sprintf("%.6f %.6f %.4f", x_z, y_z, r_z));
	if (cvar("developer")) print(sprintf("paintkit: place %s kit %i seed %g -> %.6f %.6f %.4f\n", glove ? "glove" : "weapon", pkc_ids[index], seed, x_z, y_z, r_z));
};

string(float kind, int kit, float mode, float pistol) PK_Shader =
{
	local string name, stem, base, mask, pattern, customized, ao, posmap, surface, data;
	local vector style;
	wkit_avail = FALSE;
	if (!cvar("fs_legacy_viewmodels")) return "";
	if (pistol)
	{
		stem = pistol == FS_WEAPON_USP ? "pist_223" : "pist_glock18";
		customized = strcat(PK_ALIAS, "customization/", stem, "/", stem);
		base = strcat(PK_ALIAS, "v_models/", stem, "/", stem, ".vtf");
		mask = strcat(customized, "_masks.vtf");
	}
	else
	{
		if (!mode || !kit) return "";
		base = PK_Alias(KCAT_Get(kind, KCAT_BASE));
		mask = PK_Alias(KCAT_Get(kind, KCAT_MASK));
		customized = substring(mask, 0, strlen(mask) - strlen("_masks.vtf"));
	}
	ao = strcat(customized, "_ao.vtf");
	posmap = strcat(customized, "_pos.vtf");
	surface = strcat(customized, "_surface.vtf");
	pattern = PK_Asset(PKC_Get(kit, PKC_FILES));
	if (!PK_Has(base)) return "";
	if (!mode || !kit || !PK_Has(mask) || !PK_Has(ao) || !PK_Has(posmap) || !PK_Has(surface) || !PK_Has(pattern) ||
	    !PK_Has(PK_SHARED "paint_wear.vtf") || !PK_Has(PK_SHARED "gun_grunge.vtf"))
	{
		if (!pistol) return "";
		name = sprintf("ftesurf/kit_unpainted_%g", pistol);
		data = sprintf("{\nprogram defaultskin\n{ map %s }\n}\n", base);
		return shaderforname(name, data) > 0 ? name : "";
	}
	PKC_Uniforms(kit, FALSE);
	style = stov(cvar_string("cl_wkit_opts4"));
	name = sprintf("ftesurf/kit_%g_%g_%i_%g", kind, pistol, pkc_ids[kit], mode);
	data = strcat(sprintf("{\nprogram weapon_catalog#STYLE=%g#EDIT=%g#PISTOL=%g\n{ map %s }\n{ map %s }\n{ map $nosrgb:%s }\n{ map $nosrgb:%s }\n",
		style_x, mode == 2, pistol != 0, base, pattern, mask, ao),
		sprintf("{ map $nosrgb:%s }\n{ map $nosrgb:%s }\n{ map $nosrgb:%spaint_wear.vtf }\n{ map $nosrgb:%sgun_grunge.vtf }\n}\n",
		posmap, surface, PK_SHARED, PK_SHARED));
	wkit_avail = shaderforname(name, data) > 0;
	return wkit_avail ? name : "";
};

string(float row, int kit) PK_GloveRules =
{
	local string name, data, surface, result, previous, base, file;
	local float i, count;
	local vector opts;
	if (!kit || !cvar("fs_legacy_viewmodels")) return "";
	PKC_Uniforms(kit, TRUE);
	opts = stov(cvar_string("cl_gkit_opts7"));
	name = sprintf("ftesurf/glove_kit_%i", pkc_ids[kit]);
	count = tokenizebyseparator(PKC_Get(kit, PKC_FILES), "|");
	if (count != 7) return "";
	data = sprintf("{\nprogram glove_catalog#NORMAL=%g\n", opts_z);
	for (i = 0; i < count; i += 1)
	{
		file = PK_Asset(argv(i));
		if (!PK_Has(file)) return "";
		data = strcat(data, sprintf("{ map %s%s }\n", (i == 4 || !strcmp(file, "$whiteimage")) ? "" : "$nosrgb:", file));
	}
	if (!shaderforname(name, strcat(data, "}\n"))) return "";
	result = "";
	count = tokenizebyseparator(KCAT_Get(row, KCAT_NEUTRAL), "|");
	for (i = 0; i + 1 < count; i += 2)
	{
		surface = argv(i);
		previous = result;
		result = strzone(strcat(result, sprintf("replace \"%s\" \"%s\"\n", surface, name)));
		if (strcmp(previous, "")) strunzone(previous);
	}
	if (!strcmp(result, "")) return "";
	shaderforname("ftesurf/knife_bare_skin", "{\nprogram defaultskin\n{ map materials/models/weapons/v_models/arms/v_model_base_arms_color.vtf }\n}\n");
	base = KCAT_Rules(KCAT_Get(row, KCAT_SKIN), "ftesurf/knife_bare_skin");
	if (strcmp(base, ""))
	{
		previous = result;
		result = strzone(strcat(base, result));
		strunzone(previous); strunzone(base);
	}
	return result;
};
