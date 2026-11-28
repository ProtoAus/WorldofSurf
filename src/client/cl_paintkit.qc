// A local catalog of model/kit pairs, not a player inventory. The VPK alias
// keeps customization maps separate from loose files, downloads and CS:S.
#define PK_ROOT "materials/models/weapons/"
#define PK_ALIAS "materials/ftesurf/legacy/"
#define PK_SHARED "materials/ftesurf/legacy/customization/shared/"
#define PKC_LIMIT 1024i
#define PKC_IDS 11000i
#define PKC_USP 25
#define PKC_GLOCK 26
#define PKC_SSG08 27
#define PKC_NAME 0i
#define PKC_FILES 1i
#define PKC_INFO 2i
float wkit_mode, wkit_kind, wkit_avail, wkit_pistol, wkit_primarymodel, wkit_silencer;
int pk_rand_idum, pk_rand_iy, *pk_rand_iv, pk_wplace_kit, pk_gplace_kit;
float pk_wplace_seed, pk_gplace_seed;
vector pk_wstate, pk_gstate;
int pkc_count, *pkc_ids, *pkc_index, *pkc_bits, pkm_count;
string *pkc_meta;
string *pkm_meta;
void() PKC_Data;
#define PKM_LIMIT 64i

// Per customized material (generated): key, "uvscale objscale wearscale envtint", exponent map.
void(string key, string scales, string exponent) PKM_Add =
{
	if (pkm_count >= PKM_LIMIT) return;
	pkm_meta[pkm_count * 3i] = key;
	pkm_meta[pkm_count * 3i + 1i] = scales;
	pkm_meta[pkm_count * 3i + 2i] = exponent;
	pkm_count += 1i;
};
int(string key) PKM_Find =
{
	local int i;
	for (i = 0i; i < pkm_count; i += 1i)
		if (!strcmp(pkm_meta[i * 3i], key)) return i;
	return -1i;
};

void(int id, int compatibility, string label, string files, string info) PKC_Add =
{
	if (id <= 0i || id >= PKC_IDS || pkc_count >= PKC_LIMIT) return;
	if (pkc_index[id]) return;
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
	pkm_meta = (string*)memalloc(PKM_LIMIT * 3i * 4i);
	PKC_Data();
	pk_wstate = pk_gstate = '-1 -1 -1';   // cl_*kit_state outlive the map; force the first write
	registercvar("cl_wshop_mode", "0", CVAR_ARCHIVE);
	registercvar("cl_wshop_kit", "413", CVAR_ARCHIVE);
	registercvar("cl_wshop_seed", "1", CVAR_ARCHIVE);
	registercvar("cl_wshop_wear", "0.05", CVAR_ARCHIVE);
	registercvar("cl_wshop_uspwear", "0.15", CVAR_ARCHIVE);
	registercvar("cl_wshop_glockwear", "0.15", CVAR_ARCHIVE);
	registercvar("cl_wshop_scoutwear", "0.15", CVAR_ARCHIVE);
	registercvar("cl_wshop_uspseed", "1", CVAR_ARCHIVE);
	registercvar("cl_wshop_glockseed", "1", CVAR_ARCHIVE);
	registercvar("cl_wshop_scoutseed", "1", CVAR_ARCHIVE);
	registercvar("cl_wshop_gloveseed", "1", CVAR_ARCHIVE);
	registercvar("cl_wshop_scoutkit", "0", CVAR_ARCHIVE);
	registercvar("cl_wshop_classicmoved", "0", CVAR_ARCHIVE);
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
	registercvar("cl_wkit_state", "0 0 0", 0);   // active weapon: wear, seed
	registercvar("cl_gkit_state", "0 0 0", 0);   // gloves: wear, seed
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
	if (model > PKC_SSG08 || pkc_bits[index] < 0i) return FALSE;
	return (pkc_bits[index] & (1i << (int)model)) != 0i;
};
string(int index, int field) PKC_Get =
{
	if (!pkc_meta || index <= 0i || index > pkc_count) return "";
	return pkc_meta[index * 3i + field];
};
// info[9]: ignore_weapon_size_scale, only_first_material, normal map in files[1].
vector(int index) PKC_Flags =
{
	if (!index) return '0 0 0';
	if (tokenizebyseparator(PKC_Get(index, PKC_INFO), "|") < 10) return '0 0 0';
	return stov(argv(9));
};
vector(int index) PKC_Wear =
{
	if (!index) return '0 1 0.15';
	tokenizebyseparator(PKC_Get(index, PKC_INFO), "|");
	return stov(argv(0));
};
// Per-item settings: model < 0 gloves, PKC_USP/GLOCK/SSG08 guns, else the knife.
// field is "kit", "wear" or "seed": cl_wshop_kit, cl_wshop_glovewear, cl_wshop_uspseed, ...
string(float model, string field) PK_ItemCvar =
{
	if (model < 0) return strcat("cl_wshop_glove", field);
	if (model == PKC_USP) return strcat("cl_wshop_usp", field);
	if (model == PKC_GLOCK) return strcat("cl_wshop_glock", field);
	if (model == PKC_SSG08) return strcat("cl_wshop_scout", field);
	return strcat("cl_wshop_", field);
};
int(float model) PKC_Selected =
{
	local float id;
	local int index;
	// A switched-off finish reads as Original, whatever kit id is still stored.
	if (model < 0 && cvar("cl_wshop_sporty") <= 0) return 0i;
	if (model >= PKC_USP && cvar("cl_wshop_gunfinish") <= 0) return 0i;
	if (model > 0 && model < PKC_USP && !cvar("cl_wshop_mode")) return 0i;
	id = cvar(PK_ItemCvar(model, "kit"));
	if (model > 0 && model < PKC_USP)
	{
		if (id == 1) id = 413;
		else if (id == 2) id = 12;
		else if (id == 3) id = 38;
	}
	index = PKC_Index(id);
	return PKC_Matches(index, model) ? index : 0i;
};
float(float model) PKC_Count =
{
	local int i;
	local float count;
	count = 0;
	for (i = 1i; i <= pkc_count; i += 1i) if (PKC_Matches(i, model)) count += 1;
	return count;
};
// index 0 picks the item's original finish.
void(int index, float model) PKC_Select =
{
	if (index && !PKC_Matches(index, model)) return;
	cvar_set(PK_ItemCvar(model, "kit"), index ? itos(pkc_ids[index]) : "0");
	if (model < 0) cvar_set("cl_wshop_sporty", index ? "1" : "0");
	else if (model >= PKC_USP) cvar_set("cl_wshop_gunfinish", "1");
	else cvar_set("cl_wshop_mode", index ? (cvar("cl_wshop_mode") == 2 ? "2" : "1") : "0");
};
// The active weapon's / gloves' wear and seed as one shader uniform; set only on change.
void(float glove, float wear, float seed) PK_State =
{
	local vector v;
	v = [wear, seed, 0];
	if (glove) { if (v == pk_gstate) return; pk_gstate = v; cvar_set("cl_gkit_state", sprintf("%.4f %g 0", wear, seed)); }
	else { if (v == pk_wstate) return; pk_wstate = v; cvar_set("cl_wkit_state", sprintf("%.4f %g 0", wear, seed)); }
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
void(int index, float glove, float seed) PK_Place =
{
	local vector x, y, r;
	seed = bound(0, floor(seed), 1000);
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

// Knife: kind is its catalog row, stem "". Gun: one material, dir/stem e.g. snip_ssg08/snip_ssg08_scope.
// kit 0 / mode 0 draws the stock material through the same program (NOPAINT): stock gloss and cubemap.
string(float kind, int kit, float mode, string dir, string stem) PK_Shader =
{
	local string name, base, mask, pattern, customized, ao, posmap, surface, data, key, exponent, normal;
	local vector style, flags, scales;
	local float ready, gun, paint, envtint;
	local int material;
	wkit_avail = FALSE;
	if (cvar("fs_legacy_viewmodels") != 1) return "";
	gun = strcmp(stem, "") != 0;
	if (gun)
	{
		key = strcat("customization/", dir, "/", stem);
		customized = strcat(PK_ALIAS, key);
		base = strcat(PK_ALIAS, "v_models/", dir, "/", stem, ".vtf");
		mask = strcat(customized, "_masks.vtf");
	}
	else
	{
		if (!mode || !kit) return "";
		base = PK_Alias(KCAT_Get(kind, KCAT_BASE));
		mask = PK_Alias(KCAT_Get(kind, KCAT_MASK));
		customized = substring(mask, 0, strlen(mask) - strlen("_masks.vtf"));
		key = substring(customized, strlen(PK_ALIAS), -1);
	}
	ao = strcat(customized, "_ao.vtf");
	posmap = strcat(customized, "_pos.vtf");
	surface = strcat(customized, "_surface.vtf");
	paint = (mode && kit);   // QC binds && below assignment
	flags = PKC_Flags(kit);
	tokenizebyseparator(PKC_Get(kit, PKC_FILES), "|");
	pattern = paint ? PK_Asset(argv(0)) : "$whiteimage";
	normal = (paint && flags_z) ? PK_Asset(argv(1)) : "$whiteimage";
	material = PKM_Find(key);
	scales = '1 1 1';
	exponent = "$whiteimage";
	envtint = 0.1;
	if (material >= 0i)
	{
		scales = stov(pkm_meta[material * 3i + 1i]);
		exponent = PK_Asset(pkm_meta[material * 3i + 2i]);
		tokenizebyseparator(pkm_meta[material * 3i + 1i], " ");
		envtint = stof(argv(3));   // stock $envmaptint
	}
	if (!PK_Has(base)) return "";
	// QC does not short-circuit: probe the material's files only once the base exists.
	ready = FALSE;
	if (PK_Has(mask) && PK_Has(ao) && PK_Has(posmap) && PK_Has(surface) && PK_Has(pattern) && PK_Has(normal))
		if (PK_Has(PK_SHARED "paint_wear.vtf") && PK_Has(PK_SHARED "gun_grunge.vtf") && PK_Has(exponent))
			ready = TRUE;
	if (!ready || (!paint && !gun))
	{
		if (!gun) return "";
		name = strcat("ftesurf/kit_unpainted_", stem);
		data = sprintf("{\nprogram defaultskin\n{ map %s }\n}\n", base);
		return shaderforname(name, data) > 0 ? name : "";
	}
	if (paint) PKC_Uniforms(kit, FALSE);
	style = paint ? stov(cvar_string("cl_wkit_opts4")) : '0 0 0';
	name = sprintf("ftesurf/kit_%g_%s_%i_%g", kind, stem, paint ? pkc_ids[kit] : 0i, mode);
	data = strcat(sprintf("{\nprogram weapon_catalog#STYLE=%g#EDIT=%g#UVS=%.4f#WEARS=%.4f#ENV=%.4f#NORMAL=%g%s\n",
		style_x, mode == 2, (paint && flags_x) ? 1 : scales_x, scales_z, envtint, (paint && flags_z), paint ? "" : "#NOPAINT"),
		sprintf("{ map %s }\n{ map %s }\n{ map $nosrgb:%s }\n{ map $nosrgb:%s }\n{ map $nosrgb:%s }\n{ map $nosrgb:%s }\n",
		base, pattern, mask, ao, posmap, surface),
		sprintf("{ map $nosrgb:%spaint_wear.vtf }\n{ map $nosrgb:%sgun_grunge.vtf }\n{ map $nosrgb:%s }\n{ map $nosrgb:%s }\n{ map $reflectcube }\n}\n",
		PK_SHARED, PK_SHARED, exponent, normal));
	wkit_avail = shaderforname(name, data) > 0;
	return wkit_avail ? name : "";
};

string(float row, int kit) PK_GloveRules =
{
	local string name, data, surface, result, previous, base, file, lit, remap;
	local float i, count;
	local vector opts;
	if (!kit || cvar("fs_legacy_viewmodels") != 1) return "";
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
	// Keep the row's remaps and lit bare-skin surfaces, as KCAT_SkinRules does.
	lit = KCAT_LitRules(row);
	remap = KCAT_Get(row, KCAT_REMAP);
	if (strcmp(lit, "") || strcmp(remap, ""))
	{
		previous = result;
		result = strzone(strcat(remap, lit, result));
		strunzone(previous);
		if (strcmp(lit, "")) strunzone(lit);
	}
	return result;
};
