/* Local viewmodel workshop; named kit previews are not an inventory or exact Source shader. */
float wpu_open, wpu_frames, wpu_skinstate, wpu_painted;
entity wpu_parts[2];
float wpu_rows[2], wpu_counts[2], wpu_sources[2];
float wpu_availrow[2], wpu_avail[2], wpu_availat[2];   // P1280: KCAT_Available per part, its fopen rechecked every 2 s
float wpu_source, wpu_srcskel, wpu_srcabs;
int *wpu_armmap;
int *wpu_layermap;
float wpu_drag, wpu_mx, wpu_my, wpu_drop, wpu_tsz, wpu_page, wpu_tab;
float wpu_glovepainted, wpu_kitmount, wpu_pickopen, wpu_pickpage, wpu_pickmodel;
int wpu_glovestate;
vector wpu_pos, wpu_size, wpu_offset, wpu_popup_pos, wpu_popup_size;

void() WPU_SourcePose =
{
	if (wpu_source != wp_ent.modelindex)
	{
		if (wpu_srcskel) skel_delete(wpu_srcskel);
		if (wpu_srcabs) skel_delete(wpu_srcabs);
		wpu_source = wp_ent.modelindex;
		wpu_srcskel = skel_create(wp_ent.modelindex);
		wpu_srcabs = skel_create(wp_ent.modelindex, TRUE);
	}
	wp_ent.skeletonindex = 0;
	skel_build(wpu_srcskel, wp_ent, wp_ent.modelindex, 0, 0, 0, 1);
	skel_copybones(wpu_srcabs, wpu_srcskel, 0, 0);
	wp_ent.skeletonindex = wpu_srcabs;
};

void(float slot, float row) WPU_Part =
{
	local entity part;
	local float i, sourcebone, skeleton;
	local int paint, *mapping;
	local string name, rules;
	local vector org, forward, right, up;
	if (row < (float)KCAT_ARMS) return;
	if (row != wpu_availrow[(int)slot] || cltime >= wpu_availat[(int)slot])
	{
		wpu_avail[(int)slot] = KCAT_Available(row);
		wpu_availrow[(int)slot] = row;
		wpu_availat[(int)slot] = cltime + 2;
	}
	if (!wpu_avail[(int)slot]) return;
	forward = v_forward; right = v_right; up = v_up;
	part = wpu_parts[(int)slot];
	if (!part) { part = spawn(); wpu_parts[(int)slot] = part; }
	if (slot == 0) mapping = wpu_armmap;
	else mapping = wpu_layermap;
	paint = 0i;
	if (slot == 0 && !VM_IsMirroring() && cvar("cl_wshop_sporty") > 0 && cvar("fs_legacy_viewmodels") > 0)
		paint = PKC_Selected(-row);
	if (slot == 0) PK_Place(paint, TRUE);
	if (!mapping || row != wpu_rows[(int)slot] || wpu_sources[(int)slot] != wpu_source ||
	    (slot == 0 && wpu_glovestate != paint))
	{
		if (part.skeletonindex) skel_delete(part.skeletonindex);
		part.skeletonindex = 0;
		if (mapping) memfree((void*)mapping);
		name = KCAT_Get(row, KCAT_MODEL);
		precache_model(name); setmodel(part, name);
		part.frame = 0; part.lerpfrac = 0; part.scale = 1;
		// Upper-arm parents differ: merge absolute model-space poses.
		skeleton = skel_create(part.modelindex, TRUE);
		wpu_counts[(int)slot] = bound(0, skel_get_numbones(skeleton), 256);
		for (i = 1; i <= wpu_counts[(int)slot]; i = i + 1)
		{
			org = gettaginfo(part, i);
			skel_set_bone(skeleton, i, org, v_forward, v_right, v_up);
		}
		part.skeletonindex = skeleton;
		mapping = (int*)memalloc(((int)wpu_counts[(int)slot] + 1i) * 4i);
		for (i = 1; i <= wpu_counts[(int)slot]; i = i + 1)
			mapping[(int)i] = (int)skel_find_bone(wpu_srcabs, skel_get_bonename(skeleton, i));
		if (slot == 0) { wpu_glovestate = paint; wpu_glovepainted = FALSE; }
		rules = paint ? PK_GloveRules(row, paint) : "";
		if (paint && strcmp(rules, "")) wpu_glovepainted = TRUE;
		if (!strcmp(rules, "")) rules = KCAT_SkinRules(row);
		setcustomskin(part, "", rules);
		if (strcmp(rules, "")) strunzone(rules);
		wpu_rows[(int)slot] = row; wpu_sources[(int)slot] = wpu_source;
		if (slot == 0) wpu_armmap = mapping;
		else wpu_layermap = mapping;
	}
	for (i = 1; i <= wpu_counts[(int)slot]; i = i + 1)
	{
		sourcebone = (float)mapping[(int)i];
		if (sourcebone <= 0) continue;
		org = skel_get_boneabs(wpu_srcabs, sourcebone);
		skel_set_bone(part.skeletonindex, i, org, v_forward, v_right, v_up);
	}
	v_forward = forward; v_right = right; v_up = up;
	setorigin(part, wp_ent.origin); part.angles = wp_ent.angles;
	part.renderflags = wp_ent.renderflags; part.effects = wp_ent.effects;
	addentity(part);
};

void() WPU_Apply =
{
	local float kind, style, key, isolated, mode, pistol;
	local int kit;
	local string pattern, name, data, rules, base, program;
	kind = KCAT_Knife();
	style = bound(0, floor(VM_Cvar("cl_knife_finish")), 3);
	base = KCAT_Get(kind, KCAT_BASE);
	isolated = FALSE;
	if (!strcmp(base, "materials/models/weapons/v_models/knife_t/knife_t.vtf"))
		if (cvar_type("fs_knife_texture"))
			if (cvar("fs_knife_texture") > 0)
			{
				base = "materials/ftesurf/knife_legacy_t.vtf";
				isolated = TRUE;
			}
	pistol = WP_LegacyPistol(wp_weapon) ? wp_weapon : 0;
	mode = pistol ? (cvar("cl_wshop_gunfinish") > 0) :
		(VM_IsMirroring() || wp_weapon != FS_WEAPON_KNIFE) ? 0 : bound(0, floor(cvar("cl_wshop_mode")), 2);
	kit = PKC_Selected(pistol ? (pistol == FS_WEAPON_USP ? PKC_USP : PKC_GLOCK) : kind);
	PK_Place(kit, FALSE);
	if ((wp_weapon == FS_WEAPON_KNIFE && kind > 0) || pistol)
	{
		WPU_SourcePose();
		if (VM_Cvar("cl_knife_arms") && cvar("r_drawviewmodel") > 0)     // P1280: hidden with the knife (WP_Frame)
		{
			WPU_Part(0, KCAT_Hands());
			if (KCAT_ActiveLayer() >= (float)KCAT_LAYERS) WPU_Part(1, KCAT_ActiveLayer());
		}
	}
	else { wp_ent.skeletonindex = 0; wpu_glovepainted = FALSE; }
	key = kind * 4 + style + isolated * 256 + VM_IsMirroring() * 128;
	if (key == wpu_skinstate && wkit_primarymodel == wp_ent.modelindex && wkit_mode == mode && wkit_kind == kit && wkit_pistol == pistol &&
	    wpu_kitmount == cvar("fs_legacy_viewmodels")) return;
	wpu_kitmount = cvar("fs_legacy_viewmodels");
	wpu_skinstate = key; wkit_primarymodel = wp_ent.modelindex; wkit_mode = mode; wkit_kind = kit; wkit_pistol = pistol;
	wp_ent.forceshader = 0;
	wkit_avail = wpu_painted = FALSE;
	if (pistol)
	{
		name = PK_Shader(0, kit, mode, pistol);
		rules = "";
		if (strcmp(name, ""))
		{
			data = (pistol == FS_WEAPON_USP) ? "studio:parts/v_pist_223.smd:l0:m0|silencer:parts/v_pist_223_silencer.smd:l0:m0" : "studio:glock18_model.smd:l0:m0";
			rules = KCAT_Rules(data, name);
		}
		setcustomskin(wp_ent, "", rules);
		if (strcmp(rules, "")) strunzone(rules);
		wpu_painted = wkit_avail;
		return;
	}
	if (wp_weapon != FS_WEAPON_KNIFE || kind == 0)
	{
		setcustomskin(wp_ent, "", "");
		return;
	}
	name = "";
	if (mode)
	{
		name = PK_Shader(kind, kit, mode, 0);
		wpu_painted = wkit_avail;
	}
	if (!mode && style > 0 && strcmp(KCAT_Get(kind, KCAT_MASK), ""))
	{
		pattern = "anodized_air/fade";
		if (style == 2) pattern = "hydrographic/webs";
		if (style == 3) pattern = "hydrographic/marbleized";
		name = sprintf("ftesurf/knife_%g_%g", kind, style);
		if (isolated) name = strcat(name, "_legacy");
		program = sprintf("knife_finish#STYLE=%g#FAMILY=%s", style, KCAT_Get(kind, KCAT_FAMILY));
		if (VM_IsMirroring())
		{
			name = strcat(name, "_watched");
			program = strcat(program, "#WATCHED");
		}
		data = sprintf("{\nprogram %s\n{ map %s }\n{ map materials/models/weapons/customization/paints/%s.vtf }\n{ map %s }\n}\n", program, base, pattern, KCAT_Get(kind, KCAT_MASK));
		wpu_painted = (shaderforname(name, data) > 0);
	}
	else if (!mode && isolated)
	{
		name = sprintf("ftesurf/knife_%g_original_legacy", kind);
		data = sprintf("{\nprogram defaultskin\n{ map %s }\n}\n", base);
		wpu_painted = (shaderforname(name, data) > 0);
	}
	data = KCAT_Rules(KCAT_Get(kind, KCAT_HIDE), "knife_hidden");
	rules = "";
	if (wpu_painted) rules = KCAT_Rules(KCAT_Get(kind, KCAT_PAINT), name);
	setcustomskin(wp_ent, "", strcat(data, rules));
	if (strcmp(data, "")) strunzone(data);
	if (strcmp(rules, "")) strunzone(rules);
};

void() WPU_Close =
{
	wpu_open = wpu_drag = wpu_drop = wpu_pickopen = FALSE;
	UI_CursorRelease(UIC_WEAPON);
	sui_reset_actions();
	sui_tooltip_reset();
};

void() WPU_Open =
{
	if (UI_CursorHeld() || rec_sb_open)
	{
		print("knife_menu: close the other panel first\n");
		return;
	}
	wpu_open = TRUE;
	wpu_drag = wpu_drop = wpu_pickopen = FALSE;
	sui_reset_actions();
	UI_CursorClaim(UIC_WEAPON);
};

void(float value) WPU_Seed = { cvar_set("cl_knife_seed", ftos(floor(value))); };
void(float value) WPU_Scale = { cvar_set("cl_knife_scale", ftos(value)); };
void(float value) WPU_Rotation = { cvar_set("cl_knife_rotation", ftos(value)); };
void(float value) WPU_Fade = { cvar_set("cl_knife_fade", ftos(value / 100)); };
void(float value) WPU_Wear = { cvar_set("cl_knife_wear", ftos(value)); };

void(string id, string label, vector pos, float width, float value, vector range, void(float) action, float tsz) WPU_Slider =
{
	local float lw, tw, fraction, h, x;
	local vector track;
	lw = tsz * 7; h = ceil(tsz * 1.8);
	tw = width - lw - tsz * 3;
	sui_text(pos + [0, (h - tsz) * 0.5, 0], [tsz, tsz], label, SUI_THEME_DIM, 1, 0);
	sui_text(pos + [width - tsz * 2.8, (h - tsz) * 0.5, 0], [tsz, tsz],
		range_z > (range_y - range_x) * 2 ? sprintf("%.3f", value) : sprintf("%g", value), SUI_THEME_TEXT, 1, 0);
	track = pos + [lw, floor(h * 0.5) - 2, 0];
	fraction = bound(0, (value - range_x) / (range_y - range_x), 1);
	sui_roundbox(track, [tw, 4, 0], 2, SUI_THEME_WELL, 1);
	x = floor(tw * fraction);
	if (x > 0) sui_roundbox(track, [x, 4, 0], 2, SUI_THEME_EDGE_HI, 1);
	sui_roundbox(track + [x - 3, -3, 0], '6 10 0', 2, SUI_THEME_ACCENT, 1);
	sui_slidercontrol(id, pos + [lw, 0, 0], [tw, h, 0], range, value, action);
};

float(float list) WPU_ListCount =
{
	if (list == 1) return kcat_knives;
	if (list == 2) return kcat_hands + 1;
	return kcat_layers;
};

float(float list, float index) WPU_ListRow =
{
	if (list == 1) return index;
	if (list == 2) return (index < kcat_hands) ? (float)KCAT_ARMS + index : -1;
	return (float)KCAT_LAYERS + index;
};

string(float row) WPU_OptionLabel =
{
	if (row == -1) return "Hidden";
	return KCAT_Get(row, KCAT_NAME);
};

float(string id, vector pos, vector size, string label, float tsz, float selected) WPU_ChoiceChip =
{
	local float measured;
	measured = stringwidth(label, TRUE, [tsz, tsz]);
	if (measured > size_x - 12) tsz = tsz * (size_x - 12) / measured;
	return Profile_Chip(id, pos, size, label, tsz, selected);
};

void(float value) WPU_KitSeed = { cvar_set("cl_wshop_seed", ftos(floor(value))); };
void(float value) WPU_KitWear = { cvar_set("cl_wshop_wear", ftos(value)); };
void(float value) WPU_GunWear = { cvar_set("cl_wshop_gunwear", ftos(value)); };
void(float value) WPU_GloveWear = { cvar_set("cl_wshop_glovewear", ftos(value)); };
void(float value) WPU_KitScale = { cvar_set("cl_wshop_scale", ftos(value)); };
void(float value) WPU_KitTurn = { cvar_set("cl_wshop_rotation", ftos(value)); };
void(float value) WPU_KitX = { cvar_set("cl_wshop_x", ftos(value)); };
void(float value) WPU_KitY = { cvar_set("cl_wshop_y", ftos(value)); };
void(float value) WPU_KitTint = { cvar_set("cl_wshop_tint", ftos(value)); };

// Paginate the model-filtered catalog in-place; doesn't overlap the preview
// or leave live sliders behind a dropdown. Long labels fit through ChoiceChip.
float(float model, int selected, vector at, float width, float row, float tsz) WPU_KitPicker =
{
	local int i;
	local float count, first, item, page, x, y;
	local string label;
	count = 0;
	for (i = 1i; i <= pkc_count; i += 1i) if (PKC_Matches(i, model)) count += 1;
	if (!count)
	{
		if (model < 0) label = "No kits: choose a glove family below or in Layout";
		else label = "No kits: choose a supported Legacy knife in Layout";
		WPU_ChoiceChip("wpu_nokits", at, [width,row,0], label, tsz, FALSE);
		wpu_pickopen = FALSE;
		return FALSE;
	}
	if (wpu_pickmodel != model) { wpu_pickmodel = model; if (!wpu_pickopen) wpu_pickpage = 0; }
	label = selected ? PKC_Get(selected, PKC_NAME) : "Choose a finish";
	if (WPU_ChoiceChip("wpu_choose_finish", at, [width,row,0], sprintf("%s  v   (%g finishes)", label, count), tsz, wpu_pickopen))
		wpu_pickopen = !wpu_pickopen;
	if (!wpu_pickopen) return FALSE;
	page = floor((count - 1) / 12);
	wpu_pickpage = bound(0,wpu_pickpage,page);
	first = wpu_pickpage * 12;
	at_y += tsz * 2.4;
	item = 0;
	for (i = 1i; i <= pkc_count; i += 1i)
	{
		if (!PKC_Matches(i, model)) continue;
		if (item >= first && item < first + 12)
		{
			x = ((item - first) % 2) * ((width+6)/2);
			y = floor((item - first) / 2) * tsz * 2.3;
			if (WPU_ChoiceChip(sprintf("wpu_catalog_%i", pkc_ids[i]), at + [x,y,0], [(width-6)/2,row,0], PKC_Get(i,PKC_NAME), tsz, i == selected))
			{
				PKC_Select(i, model);
				if (cvar("fs_legacy_viewmodels") != 1) WP_MountKnifeContent(-1);
				wpu_pickopen = FALSE;
			}
		}
		item += 1;
	}
	at_y += tsz * 14.2;
	if (WPU_ChoiceChip("wpu_catalog_prev", at, [width/3-6,row,0], "Previous", tsz, FALSE)) wpu_pickpage = max(0,wpu_pickpage-1);
	WPU_ChoiceChip("wpu_catalog_page", at + [width/3,0,0], [width/3,row,0], sprintf("%g / %g",wpu_pickpage+1,page+1), tsz, FALSE);
	if (WPU_ChoiceChip("wpu_catalog_next", at + [2*width/3+6,0,0], [width/3-6,row,0], "Next", tsz, FALSE)) wpu_pickpage = min(page,wpu_pickpage+1);
	return TRUE;
};

void(vector at, float width, float row, float tsz, float hint) WPU_KitPage =
{
	local float mode, kind, i, a, b, model, hands;
	local int kit;
	local string label;
	local vector btn, allowed;
	hands = KCAT_LocalHands();
	mode = bound(0, floor(cvar("cl_wshop_mode")), 2);
	kind = KCAT_LocalKnife();
	btn = [(width - 12) / 3, row, 0];
	if (wpu_tab == 1)
	{
		for (i = 0; i < 3; i = i + 1)
		{
			label = i == 0 ? "Classic / off" : i == 1 ? "Stock kit" : "Custom kit";
			if (WPU_ChoiceChip(sprintf("wpu_kit_mode%g", i), at + [(btn_x + 6) * i, 0, 0], btn, label, tsz, mode == i))
			{
				cvar_set("cl_wshop_mode", ftos(i));
				if (i && cvar("fs_legacy_viewmodels") != 1) WP_MountKnifeContent(-1);
			}
		}
		at_y += tsz * 2.4;
		kit = PKC_Selected(kind);
		if (WPU_KitPicker(kind, kit, at, width, row, tsz)) return;
		at_y += tsz * 2.5;
		allowed = PKC_Wear(kit);
		a = allowed_x; b = allowed_y;
		WPU_Slider("wpu_kit_float", "Wear float", at, width, bound(a, cvar("cl_wshop_wear"), b), [a,b,(b-a)*1000], WPU_KitWear, tsz);
		at_y += tsz * 2.25;
		WPU_Slider("wpu_kit_seed", "Pattern seed", at, width, bound(0, floor(cvar("cl_wshop_seed")), 1000), '0 1000 1000', WPU_KitSeed, tsz);
		at_y += tsz * 2.25;
		if (mode == 2)
		{
			WPU_Slider("wpu_kit_scale", "Scale x", at, width, bound(0.25,cvar("cl_wshop_scale"),4), '0.25 4 75', WPU_KitScale, tsz); at_y += tsz * 2.25;
			WPU_Slider("wpu_kit_rot", "Rotation", at, width, bound(-180,cvar("cl_wshop_rotation"),180), '-180 180 360', WPU_KitTurn, tsz); at_y += tsz * 2.25;
			WPU_Slider("wpu_kit_x", "Offset X", at, width, bound(-1,cvar("cl_wshop_x"),1), '-1 1 200', WPU_KitX, tsz); at_y += tsz * 2.25;
			WPU_Slider("wpu_kit_y", "Offset Y", at, width, bound(-1,cvar("cl_wshop_y"),1), '-1 1 200', WPU_KitY, tsz); at_y += tsz * 2.25;
			WPU_Slider("wpu_kit_tint", "Cool/Warm", at, width, bound(-1,cvar("cl_wshop_tint"),1), '-1 1 200', WPU_KitTint, tsz); at_y += tsz * 2.5;
			if (WPU_ChoiceChip("wpu_kit_reset", at, [width, row, 0], "Reset custom offsets and tint", tsz, FALSE))
				{ WPU_KitScale(1); WPU_KitTurn(0); WPU_KitX(0); WPU_KitY(0); WPU_KitTint(0); }
			at_y += tsz * 2.5;
		}
		label = sprintf("%s | %.3f - %.3f", KCAT_Get(kind, KCAT_NAME), a, b);
		if (mode && !kit) label = "Choose a compatible finish from the picker.";
		else if (mode && wp_ready && wp_weapon == FS_WEAPON_KNIFE && !wkit_avail) label = "Kit inputs unavailable; showing Original.";
	}
	else if (wpu_tab == 2)
	{
		if (WPU_ChoiceChip("wpu_cssguns", at, [(width-6)/2,row,0], "CS:S originals", tsz, !cvar("cl_wshop_pistols"))) cvar_set("cl_wshop_pistols", "0");
		if (WPU_ChoiceChip("wpu_goguns", at + [(width+6)/2,0,0], [(width-6)/2,row,0], "CS:GO kits", tsz, cvar("cl_wshop_pistols") != 0))
			{ cvar_set("cl_wshop_pistols", "1"); if (cvar("fs_legacy_viewmodels") != 1) WP_MountKnifeContent(-1); }
		at_y += tsz * 2.6;
		if (WPU_ChoiceChip("wpu_usp", at, [(width-6)/2,row,0], "Equip USP", tsz, wp_weapon == FS_WEAPON_USP)) localcmd("usp\n");
		if (WPU_ChoiceChip("wpu_glock", at + [(width+6)/2,0,0], [(width-6)/2,row,0], "Equip Glock", tsz, wp_weapon == FS_WEAPON_GLOCK)) localcmd("glock\n");
		at_y += tsz * 2.6;
		model = wp_weapon == FS_WEAPON_GLOCK ? PKC_GLOCK : PKC_USP;
		kit = PKC_Selected(model);
		if (WPU_KitPicker(model, kit, at, width, row, tsz)) return;
		at_y += tsz * 2.5;
		if (WPU_ChoiceChip("wpu_gunoriginal", at, [width,row,0], cvar("cl_wshop_gunfinish") ? "Switch to original finish" : "Enable selected finish", tsz, !cvar("cl_wshop_gunfinish")))
			cvar_set("cl_wshop_gunfinish", ftos(!cvar("cl_wshop_gunfinish")));
		at_y += tsz * 2.4;
		allowed = PKC_Wear(kit); a = allowed_x; b = allowed_y;
		WPU_Slider("wpu_gun_float", "Wear float", at, width, bound(a, cvar("cl_wshop_gunwear"), b), [a,b,(b-a)*1000], WPU_GunWear, tsz);
		at_y += tsz * 2.25;
		WPU_Slider("wpu_kit_seed", "Pattern seed", at, width, bound(0,floor(cvar("cl_wshop_seed")),1000), '0 1000 1000', WPU_KitSeed, tsz);
		at_y += tsz * 2.5;
		label = sprintf("%s | %.3f - %.3f", model == PKC_GLOCK ? "Glock" : "USP-S", a, b);
		if (!cvar("cl_wshop_pistols")) label = "Enable CS:GO kits to preview these finishes.";
		if (cvar("cl_wshop_pistols") && WP_IsPistol(wp_weapon) && wp_ready && !wkit_pistol) label = "Legacy unavailable; showing the CS:S original.";
	}
	else
	{
		for (i = 0; i < 8; i += 1)
		{
			model = i < 3 ? 37+i : i == 3 ? 42 : 42+i;
			label = i == 0 ? "Bloodhound" : i == 1 ? "Broken Fang" : i == 2 ? "Hydra" : i == 3 ? "Hand Wraps" : i == 4 ? "Moto" : i == 5 ? "Driver" : i == 6 ? "Specialist" : "Sporty";
			if (WPU_ChoiceChip(sprintf("wpu_family_%g", i), at + [(i%4)*(width+6)/4,floor(i/4)*tsz*2.3,0], [(width-18)/4,row,0], label, tsz, hands == model))
				{ WP_ChooseKnife(model); wpu_pickopen = FALSE; }
		}
		at_y += tsz * 4.8;
		kit = PKC_Selected(-hands);
		if (WPU_KitPicker(-hands, kit, at, width, row, tsz)) return;
		at_y += tsz * 2.6;
		if (WPU_ChoiceChip("wpu_gloves_off", at, [width,row,0], cvar("cl_wshop_sporty") ? "Switch to original hands finish" : "Enable selected finish", tsz, !cvar("cl_wshop_sporty")))
			cvar_set("cl_wshop_sporty", ftos(!cvar("cl_wshop_sporty")));
		at_y += tsz * 2.6;
		allowed = PKC_Wear(kit); a = allowed_x; b = allowed_y;
		WPU_Slider("wpu_glove_float", "Wear float", at, width, bound(a,cvar("cl_wshop_glovewear"),b), [a,b,(b-a)*1000], WPU_GloveWear, tsz);
		at_y += tsz * 2.25;
		WPU_Slider("wpu_kit_seed", "Pattern seed", at, width, bound(0,floor(cvar("cl_wshop_seed")),1000), '0 1000 1000', WPU_KitSeed, tsz);
		at_y += tsz * 2.5;
		label = kit ? sprintf("%s | %.3f - %.3f", PKC_Get(kit,PKC_NAME), a, b) : "Select a family, then a finish. Equip a Legacy knife or pistol.";
	}
	sui_text(at, [hint,hint], label, SUI_THEME_TEXT, 1, 0);
	at_y += tsz * 2.5;
	if (WPU_ChoiceChip("wpu_kit_inspect", at, btn, "Inspect", tsz, FALSE)) WP_Inspect();
	if (WPU_ChoiceChip("wpu_kit_random", at + [btn_x+6,0,0], btn, "Random seed", tsz, FALSE)) WPU_KitSeed(floor(random()*1001));
	if (wpu_tab != 2 && wp_weapon != FS_WEAPON_KNIFE)
	{
		if (WPU_ChoiceChip("wpu_kit_equip", at + [(btn_x+6)*2,0,0], btn, "Equip knife", tsz, FALSE)) WP_EquipKnife();
	}
	else if (WPU_ChoiceChip("wpu_kit_mount", at + [(btn_x+6)*2,0,0], btn, "Mount Legacy", tsz, FALSE)) WP_MountKnifeContent(-1);
	at_y += tsz * 2.5;
	sui_text(at, [hint,hint], "Local previews. Stock uses kit inputs; placement and lighting are approximate.", SUI_THEME_MUTED, 1, 0);
};

void(vector scr) WPU_Draw =
{
	local float sc, tsz, ttl, hint, pad, row, width, kind, arms, style, oldfont, i, selected, count, option, start;
	local vector pos, size, at, box, pop;
	local string text;
	if (!wpu_open) return;
	if (UI_CursorHeld() != UIC_WEAPON || rec_sb_open) { WPU_Close(); return; }
	wpu_frames = wpu_frames + 1;
	pop = '0 0 0';
	sc = max(0.5, ui_cv_scale);
	while (sc > 0.5 && (Font_Px(8 * sc) * 38 > scr_x - 12 || Font_Px(8 * sc) * 41 > scr_y - 12)) sc = sc - 0.5;
	oldfont = drawfont;
	Font_Set(ui_font_ui);
	tsz = Font_Px(8 * sc); ttl = Font_Px(10 * sc); hint = Font_Px(6 * sc);
	wpu_tsz = tsz;
	pad = tsz; row = ceil(tsz * 1.8);
	size = [min(scr_x - 8, tsz * 38), min(scr_y - 8, tsz * 41), 0];
	pos = [cvar("hud_knife_x") * scr_x, cvar("hud_knife_y") * scr_y, 0];
	if (wpu_drag) pos = [wpu_mx, wpu_my, 0] - wpu_offset;
	pos_x = bound(4, pos_x, max(4, scr_x - size_x - 4));
	pos_y = bound(4, pos_y, max(4, scr_y - size_y - 4));
	if (wpu_drag)
	{
		cvar_set("hud_knife_x", ftos(pos_x / scr_x));
		cvar_set("hud_knife_y", ftos(pos_y / scr_y));
	}
	wpu_pos = pos; wpu_size = size;
	sui_begin(scr_x, scr_y);
	sui_style_panel(pos, size, ceil(pad * 0.75), 0.98);
	sui_text(pos + [pad, pad, 0], [ttl, ttl], "Weapon workshop", SUI_THEME_TEXT, 1, 0);
	if (Profile_Chip("wpu_close", pos + [size_x - pad - row, pad * 0.65, 0], [row, row, 0], "X", tsz, FALSE))
	{
		WPU_Close(); sui_end(); Font_Set(oldfont); return;
	}
	sui_tooltip_for("wpu_close", "Close (Esc). Drag the title bar to move this window.", sc);
	at = pos + [pad, tsz * 4, 0];
	width = size_x - pad * 2;
	for (i = 0; i < 4; i += 1)
	{
		text = i == 0 ? "Layout" : i == 1 ? "Knife kits" : i == 2 ? "Pistols" : "Glove kits";
		if (WPU_ChoiceChip(sprintf("wpu_tab%g", i), at + [i*(width+6)/4,0,0], [(width-18)/4,row,0], text, tsz, wpu_tab == i))
			{ wpu_tab = i; wpu_drop = wpu_pickopen = 0; }
	}
	at_y += tsz * 2.55;
	if (wpu_tab)
	{
		WPU_KitPage(at, width, row, tsz, hint);
		sui_end(); Font_Set(oldfont); return;
	}
	kind = KCAT_LocalKnife();
	arms = cvar("cl_knife_arms") ? KCAT_LocalHands() : -1;
	style = bound(0, floor(cvar("cl_knife_finish")), 3);
	sui_text(at + [0, (row - tsz) * 0.5, 0], [tsz, tsz], "Knife", SUI_THEME_DIM, 1, 0);
	box = [width - tsz * 7, row, 0];
	if (WPU_ChoiceChip("wpu_knife", at + [tsz * 7, 0, 0], box, strcat(WPU_OptionLabel(kind), "  v"), tsz, wpu_drop == 1))
		{ wpu_drop = (wpu_drop == 1) ? 0 : 1; wpu_page = 0; }
	if (wpu_drop == 1) pop = at + [tsz * 7, row + 4, 0];
	at_y = at_y + tsz * 2.7;
	sui_text(at + [0, (row - tsz) * 0.5, 0], [tsz, tsz], "Hands", SUI_THEME_DIM, 1, 0);
	if (WPU_ChoiceChip("wpu_arms", at + [tsz * 7, 0, 0], box, strcat(WPU_OptionLabel(arms), "  v"), tsz, wpu_drop == 2))
		{ wpu_drop = (wpu_drop == 2) ? 0 : 2; wpu_page = 0; }
	if (wpu_drop == 2) pop = at + [tsz * 7, row + 4, 0];
	at_y = at_y + tsz * 2.7;
	sui_text(at + [0, (row - tsz) * 0.5, 0], [tsz, tsz], "Sleeves", SUI_THEME_DIM, 1, 0);
	if (WPU_ChoiceChip("wpu_sleeves", at + [tsz * 7, 0, 0], box, strcat(WPU_OptionLabel(KCAT_LocalLayer()), "  v"), tsz, wpu_drop == 3))
		{ wpu_drop = (wpu_drop == 3) ? 0 : 3; wpu_page = 0; }
	if (wpu_drop == 3) pop = at + [tsz * 7, row + 4, 0];
	at_y = at_y + tsz * 3.1;
	for (i = 0; i < 4; i = i + 1)
	{
		text = "Original";
		if (i == 1) text = "Fade";
		if (i == 2) text = "Web";
		if (i == 3) text = "Marble";
		if (Profile_Chip(sprintf("wpu_finish%g", i), at + [i * (width + 6) / 4, 0, 0], [(width - 18) / 4, row, 0], text, tsz, style == i))
		{
			cvar_set("cl_wshop_mode", "0");
			cvar_set("cl_knife_finish", ftos(i));
			WP_EquipKnife();
		}
	}
	at_y = at_y + tsz * 2.5;
	WPU_Slider("wpu_seed", "Pattern seed", at, width, floor(cvar("cl_knife_seed")), '0 1000 1000', WPU_Seed, tsz);
	at_y = at_y + tsz * 2.1;
	WPU_Slider("wpu_scale", "Scale", at, width, cvar("cl_knife_scale"), '0.25 4 75', WPU_Scale, tsz);
	at_y = at_y + tsz * 2.1;
	WPU_Slider("wpu_rotation", "Rotation", at, width, cvar("cl_knife_rotation"), '0 360 360', WPU_Rotation, tsz);
	at_y = at_y + tsz * 2.1;
	WPU_Slider("wpu_fade_amount", "Fade %", at, width, cvar("cl_knife_fade") * 100, '0 100 100', WPU_Fade, tsz);
	at_y = at_y + tsz * 2.1;
	WPU_Slider("wpu_wear", "Wear", at, width, cvar("cl_knife_wear"), '0 1 100', WPU_Wear, tsz);
	at_y = at_y + tsz * 2.7;
	if (Profile_Chip("wpu_inspect", at, [(width - 12) / 3, row, 0], "Inspect", tsz, FALSE)) WP_Inspect();
	if (Profile_Chip("wpu_random", at + [(width + 6) / 3, 0, 0], [(width - 12) / 3, row, 0], "Random seed", tsz, FALSE)) WPU_Seed(floor(random() * 1001));
	if (Profile_Chip("wpu_drop", at + [(width + 6) * 2 / 3, 0, 0], [(width - 12) / 3, row, 0], "Drop", tsz, FALSE)) WP_Drop();
	at_y = at_y + tsz * 2.7;
	if (Profile_Chip("wpu_mount", at, [width, row, 0], "Mount installed CS:GO Legacy", tsz, FALSE)) WP_MountKnifeContent(-1);
	sui_tooltip_for("wpu_mount", "Session-only installed assets; also requested automatically when selecting a Legacy knife. No download.", sc);
	at_y = at_y + tsz * 2.7;
	if (Profile_Chip("wpu_account_save", at, [(width - 6) / 2, row, 0], "Save to account", tsz, FALSE)) VM_ProfileAction("save");
	if (Profile_Chip("wpu_account_reload", at + [(width + 6) / 2, 0, 0], [(width - 6) / 2, row, 0], "Reload account", tsz, FALSE)) VM_ProfileAction("reload");
	at_y = at_y + tsz * 2.5;
	sui_text(at, [hint, hint], VM_Status(), SUI_THEME_MUTED, 1, 0);
	at_y = at_y + tsz * 1.6;
	text = "Classic local previews. For authored paint inputs, open Knife kits.";
	if (kind > 0 && style > 0 && !strcmp(KCAT_Get(kind, KCAT_MASK), "")) text = "No compatible paint mask: showing the original finish.";
	sui_text(at, [hint, hint], text, SUI_THEME_MUTED, 1, 0);
	sui_text(at + [0, hint * 1.4, 0], [hint, hint], "CSS has embedded arms. Legacy hands use matte textures.", SUI_THEME_MUTED, 1, 0);
	// Last in this bracket: the open list owns hit-tests over covered controls.
	if (wpu_drop)
	{
		count = WPU_ListCount(wpu_drop);
		wpu_page = bound(0, wpu_page, floor((count - 1) / 9));
		start = wpu_page * 9;
		wpu_popup_size = [box_x, row * (min(9, count - start) + 1) + 8, 0];
		pop_y = bound(4, pop_y, max(4, scr_y - wpu_popup_size_y - 4));
		wpu_popup_pos = pop;
		sui_style_panel(pop, wpu_popup_size, pad * 0.5, 1);
		selected = kind;
		if (wpu_drop == 2) selected = arms;
		if (wpu_drop == 3) selected = KCAT_LocalLayer();
		for (i = 0; i < min(9, count - start); i = i + 1)
		{
			option = WPU_ListRow(wpu_drop, start + i);
			text = WPU_OptionLabel(option);
			if (WPU_ChoiceChip(sprintf("wpu_option%g_%g", wpu_drop, start + i), pop + [4, 4 + row * i, 0], [box_x - 8, row, 0], text, tsz, selected == option))
			{
				if (option == -1) { cvar_set("cl_knife_arms", "0"); WP_EquipKnife(); }
				else WP_ChooseKnife(option);
				wpu_drop = 0;
				break;
			}
		}
		at = pop + [4, wpu_popup_size_y - row - 4, 0];
		if (Profile_Chip("wpu_prev", at, [row * 2, row, 0], "<", tsz, FALSE)) wpu_page = max(0, wpu_page - 1);
		if (Profile_Chip("wpu_next", at + [box_x - row * 2 - 8, 0, 0], [row * 2, row, 0], ">", tsz, FALSE)) wpu_page = min(floor((count - 1) / 9), wpu_page + 1);
		sui_text(at + [row * 2 + 4, (row - hint) * 0.5, 0], [hint, hint], sprintf("%g-%g / %g", start + 1, min(start + 9, count), count), SUI_THEME_DIM, 1, 0);
	}
	sui_end();
	Font_Set(oldfont);
};

float(float evtype, float scanx, float chary, float devid) WPU_Input =
{
	if (!wpu_open) return FALSE;
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE)
	{
		if (wpu_drop) wpu_drop = 0;
		else if (wpu_pickopen) wpu_pickopen = FALSE;
		else WPU_Close();
		return TRUE;
	}
	if (evtype == IE_MOUSEABS)
	{
		wpu_mx = scanx; wpu_my = chary;
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MOUSE1)
	{
		if (evtype == IE_KEYUP && wpu_drag) { wpu_drag = FALSE; return TRUE; }
		if (evtype == IE_KEYDOWN)
		if (wpu_mx >= wpu_pos_x && wpu_mx < wpu_pos_x + wpu_size_x - wpu_size_y * 0.11 &&
		    wpu_my >= wpu_pos_y && wpu_my < wpu_pos_y + wpu_tsz * 3.5)
		{
			wpu_drag = TRUE; wpu_drop = 0;
			wpu_offset = [wpu_mx, wpu_my, 0] - wpu_pos;
			return TRUE;
		}
		if (evtype == IE_KEYDOWN && wpu_drop)
		if (wpu_mx < wpu_popup_pos_x || wpu_mx >= wpu_popup_pos_x + wpu_popup_size_x ||
		    wpu_my < wpu_popup_pos_y || wpu_my >= wpu_popup_pos_y + wpu_popup_size_y)
		if (wpu_mx < wpu_pos_x + wpu_tsz * 8 || wpu_mx >= wpu_pos_x + wpu_size_x - wpu_tsz ||
		    wpu_my < wpu_pos_y + wpu_tsz * 6.5 || wpu_my >= wpu_pos_y + wpu_tsz * 15)
		{
			wpu_drop = 0;
			return TRUE;
		}
	}
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN) _sui_mouse_move(_cursor_position, FALSE);
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	return FALSE;
};

float() WPU_Command =
{
	local float i, model;
	local int index, count;
	if (strcmp(argv(0), "knife_menu") && strcmp(argv(0), "weapon_workshop")) return FALSE;
	if (!strcmp(argv(1), "kits") || !strcmp(argv(1), "kit"))
	{
		if (!strcmp(argv(2), "knife")) model = KCAT_LocalKnife();
		else if (!strcmp(argv(2), "usp")) model = PKC_USP;
		else if (!strcmp(argv(2), "glock")) model = PKC_GLOCK;
		else if (!strcmp(argv(2), "gloves")) model = -KCAT_LocalHands();
		else { print("weapon_workshop kits <knife|usp|glock|gloves>; kit <category> <number>\n"); return TRUE; }
		if (!strcmp(argv(1), "kit"))
		{
			if (strcmp(argv(4), "")) return TRUE;
			index = PKC_Index(stof(argv(3)));
			if (!PKC_Matches(index, model)) { print("workshop: finish is not compatible with this model\n"); return TRUE; }
			PKC_Select(index, model);
			if (cvar("fs_legacy_viewmodels") != 1) WP_MountKnifeContent(-1);
			return TRUE;
		}
		count = 0i;
		for (index = 1i; index <= pkc_count; index += 1i)
			if (PKC_Matches(index, model))
			{
				print(sprintf("kit %i: %s\n", pkc_ids[index], PKC_Get(index,PKC_NAME)));
				count += 1i;
			}
		print(sprintf("workshop: %i compatible finishes\n", count));
		return TRUE;
	}
	if (!strcmp(argv(1), "picker"))
	{
		if (!wpu_open || !wpu_tab) return TRUE;
		wpu_pickopen = TRUE;
		wpu_pickpage = bound(0, floor(stof(argv(2))) - 1, 99);
		return TRUE;
	}
	if (!strcmp(argv(1), "select"))
	{
		if (!strcmp(argv(2), "") || strcmp(argv(3), "")) print("knife_menu select <catalog number>; knife_menu catalog lists choices\n");
		else WP_ChooseKnife(stof(argv(2)));
		return TRUE;
	}
	if (!strcmp(argv(1), "catalog"))
	{
		for (i = 0; i < 128; i = i + 1)
			if (KCAT_Valid(i)) print(sprintf("knife catalog %g: %s\n", i, KCAT_Get(i, KCAT_NAME)));
		return TRUE;
	}
	if (!strcmp(argv(1), "status"))
	{
		print(sprintf("knife_menu: open %g claims %g frames %g kind %g finish %g painted %g\n", wpu_open, UI_CursorHeld(), wpu_frames, cvar("cl_knife_model"), cvar("cl_knife_finish"), wpu_painted));
		print(sprintf("knife_menu: pos %v size %v drag %g dropdown %g arm-model %g\n", wpu_pos, wpu_size, wpu_drag, wpu_drop, KCAT_Hands()));
		print(sprintf("knife_menu: catalog knife %g hands %g layer %g active-layer %g page %g\n", KCAT_Knife(), KCAT_Hands(), KCAT_Layer(), KCAT_ActiveLayer(), wpu_page));
		print(sprintf("knife_menu: part-models %g %g bones %g %g source %g\n", wpu_parts[0].modelindex, wpu_parts[1].modelindex, wpu_counts[0], wpu_counts[1], wpu_source));
		index = (int)wkit_kind;
		count = wpu_glovepainted ? pkc_ids[wpu_glovestate] : 0i;
		print(strcat(sprintf("workshop: tab %g kit %i mode %g materials %g pistol %g glove %i", wpu_tab, index > 0i ? pkc_ids[index] : 0i, wkit_mode, wkit_avail, wkit_pistol, count),
			sprintf(" catalog %i picker %g page %g\n", pkc_count, wpu_pickopen, wpu_pickpage + 1)));
		return TRUE;
	}
	if (!strcmp(argv(1), "mount")) { WP_MountKnifeContent(-1); return TRUE; }
	if (!strcmp(argv(1), "resetpos")) { cvar_set("hud_knife_x", "0.02"); cvar_set("hud_knife_y", "0.14"); return TRUE; }
	if (!strcmp(argv(1), "close")) WPU_Close();
	else if (!strcmp(argv(1), "open")) { if (!wpu_open) WPU_Open(); }
	else if (!strcmp(argv(1), "layout") || !strcmp(argv(1), "knives") ||
	         !strcmp(argv(1), "pistols") || !strcmp(argv(1), "gloves"))
	{
		wpu_tab = !strcmp(argv(1), "layout") ? 0 : !strcmp(argv(1), "knives") ? 1 : !strcmp(argv(1), "pistols") ? 2 : 3;
		wpu_drop = wpu_pickopen = 0;
		if (!wpu_open) WPU_Open();
	}
	else if (wpu_open) WPU_Close();
	else WPU_Open();
	return TRUE;
};

void() WPU_Register =
{
	wpu_skinstate = -1;
	shaderforname("knife_hidden", "{\nsurfaceparm nodraw\n}\n");
	registercommand("knife_menu"); registercommand("weapon_workshop");
	PK_Register();
	registercvar("cl_knife_arms", "1", CVAR_ARCHIVE);
	registercvar("cl_knife_arm_model", "0", CVAR_ARCHIVE);
	registercvar("hud_knife_x", "0.02", CVAR_ARCHIVE);
	registercvar("hud_knife_y", "0.14", CVAR_ARCHIVE);
	registercvar("cl_knife_finish", "0", CVAR_ARCHIVE);
	registercvar("cl_knife_seed", "0", CVAR_ARCHIVE);
	registercvar("cl_knife_scale", "1", CVAR_ARCHIVE);
	registercvar("cl_knife_rotation", "0", CVAR_ARCHIVE);
	registercvar("cl_knife_fade", "1", CVAR_ARCHIVE);
	registercvar("cl_knife_wear", "0", CVAR_ARCHIVE);
};
