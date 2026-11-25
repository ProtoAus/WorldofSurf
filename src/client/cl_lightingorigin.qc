// Source: ValveSoftware/source-sdk-2013 src/game/client/c_baseanimating.cpp,
// C_InfoLightingRelative::GetLightingOffset (released game-side contract).
// P1832: static map references only. Source's helper matrix is H * inverse(L).
// The native API substitutes only this engine's ambient sample; not Source renderer parity.
float(entity ent, vector point) LO_DrawOrigin = #0:addentity_lightingorigin;
float(entity ent, vector translation, vector axisX, vector axisY, vector axisZ) LO_DrawOffset = #0:addentity_lightingoffset;

typedef struct {
	string name, classname, model, absolute, relative, landmark, parent;
	vector origin, angles;
	vector translation, axisX, axisY, axisZ;
	float unsafe, refunsafe, mi, mode;
} lo_record_t;
typedef struct {
	float count, authored, resolved, missing, unsupported, ambiguous, bound, draws, rejected;
	float apiOrigin, apiOffset, warned, bindtries, lastmi;
	vector lastorigin;
} lo_state_t;
lo_record_t *lo_records;
lo_state_t *lo_state;
.float lo_binding;

string(string old, string value) LO_String =
{
	local string result;
	if (old != "") strunzone(old);
	result = value != "" ? strzone(value) : "";
	return result;
};
void(lo_record_t *r) LO_FreeStrings =
{
	if (r->name != "") strunzone(r->name); if (r->classname != "") strunzone(r->classname); if (r->model != "") strunzone(r->model);
	if (r->absolute != "") strunzone(r->absolute); if (r->relative != "") strunzone(r->relative); if (r->landmark != "") strunzone(r->landmark); if (r->parent != "") strunzone(r->parent);
};
void() LO_Reset =
{
	local float i;
	if (lo_state)
	{
		for (i = 0; i < lo_state->count; i = i + 1)
			LO_FreeStrings(&lo_records[i]);
		memfree((__variant*)lo_records);
		memfree((__variant*)lo_state);
	}
	lo_records = __NULL__;
	lo_state = __NULL__;
};
// Called at load only. Duplicate names deliberately resolve to no reference.
float(string name) LO_Find =
{
	local float i, found;
	found = -1;
	if (name == "") return -1;
	for (i = 0; i < lo_state->count; i = i + 1)
		if (!strcmp(lo_records[i].name, name))
		{
			if (found >= 0) return -1;
			found = i;
		}
	return found;
};
float(lo_record_t *r) LO_Static =
{
	return (r->parent == "" && !r->refunsafe &&
		(r->classname == "info_target" || r->classname == "info_lighting_relative"));
};
vector(vector x, vector y, vector z, vector p) LO_Transform =
{
	local vector result;
	result = x * p_x + y * p_y + z * p_z;
	return result;
};
void(lo_record_t *out, lo_record_t *helper, lo_record_t *landmark) LO_Matrix =
{
	local vector hx, hy, hz, lx, ly, lz;
	out->axisX = '1 0 0'; out->axisY = '0 1 0'; out->axisZ = '0 0 1';
	out->translation = '0 0 0';
	if (!landmark) return; // Source GetLightingOffset: absent landmark is IDENTITY.
	makevectors(helper->angles);
	hx = v_forward; hy = -v_right; hz = v_up;
	makevectors(landmark->angles);
	lx = v_forward; ly = -v_right; lz = v_up;
	out->axisX = LO_Transform(hx, hy, hz, [lx_x, ly_x, lz_x]);
	out->axisY = LO_Transform(hx, hy, hz, [lx_y, ly_y, lz_y]);
	out->axisZ = LO_Transform(hx, hy, hz, [lx_z, ly_z, lz_z]);
	out->translation = helper->origin - LO_Transform(out->axisX, out->axisY, out->axisZ, landmark->origin);
};

float(float isnew) LO_Delta =
{
	local float i, match, ok;
	local vector savedAngles, color;
	local lo_record_t *r;
	self.drawmask = 0;
	if (isnew)
	{
		lo_state->bindtries = lo_state->bindtries + 1;
		lo_state->lastmi = self.modelindex;
		lo_state->lastorigin = self.origin;
		self.lo_binding = 0;
		match = -1;
		for (i = 0; i < lo_state->count; i = i + 1)
			if (lo_records[i].mi == self.modelindex && lo_records[i].origin == self.origin)
			{
				if (match >= 0) { match = -2; break; }
				match = i;
			}
		if (match >= 0)
			if (lo_records[match].mode)
			{
				self.lo_binding = match + 1;
				lo_state->bound = lo_state->bound + 1;
			}
		if (match == -2) lo_state->ambiguous = lo_state->ambiguous + 1;
	}
	if (cl_scene_worldonly) return FALSE;
	if (!self.lo_binding || !cvar("vbsp_lightingorigin")) return Tint_Delta(isnew);
	r = &lo_records[self.lo_binding - 1];
	if ((r->mode == 1 && !lo_state->apiOrigin) || (r->mode == 2 && !lo_state->apiOffset))
	{
		if (!lo_state->warned)
		{
			print("lightingorigin: native lighting sample API unavailable; ordinary drawing retained\n");
			lo_state->warned = TRUE;
		}
		return Tint_Delta(isnew);
	}
	if (self.effects & EF_NODRAW) return TRUE;
	savedAngles = self.angles; color = self.colormod;
	// Compose with exact map tint, without leaving its pitch/roll conversion applied twice.
	Tint_Delta(isnew);
	self.angles = savedAngles;
	self.angles_x = self.angles_x * cvar("r_meshpitch");
	self.angles_z = self.angles_z * cvar("r_meshroll");
	if (r->mode == 1) ok = LO_DrawOrigin(self, r->translation);
	else ok = LO_DrawOffset(self, r->translation, r->axisX, r->axisY, r->axisZ);
	self.angles = savedAngles; self.colormod = color; self.drawmask = 0;
	if (ok)
	{
		lo_state->draws = lo_state->draws + 1;
		return TRUE; // exactly one submitted copy, no addentities duplicate
	}
	lo_state->rejected = lo_state->rejected + 1;
	return Tint_Delta(isnew); // no native submission: keep the existing rendering path
};

// Parse to temporary zoned strings so the entity tokenizer never owns retained metadata.
float(lo_record_t *r) LO_Read =
{
	local string tok, key;
	memfill8((__variant*)r, 0, sizeof(lo_record_t));
	while ((tok = getentitytoken()) != "" && tok != "{") {}
	if (tok == "") return FALSE;
	while ((key = getentitytoken()) != "" && key != "}")
	{
		tok = getentitytoken(); key = strtolower(key);
		if (key == "targetname") r->name = LO_String(r->name, tok);
		else if (key == "classname") r->classname = LO_String(r->classname, tok);
		else if (key == "model") r->model = LO_String(r->model, tok);
		else if (key == "lightingorigin") r->absolute = LO_String(r->absolute, tok);
		else if (key == "lightingoriginhack") r->relative = LO_String(r->relative, tok);
		else if (key == "lightinglandmark") r->landmark = LO_String(r->landmark, tok);
		else if (key == "parentname") r->parent = LO_String(r->parent, tok);
		else if (key == "origin") r->origin = stov(tok);
		else if (key == "angles") r->angles = stov(tok);
		else if ((key == "body" || key == "setbodygroup" || key == "randomanimation") && stof(tok)) r->unsafe = TRUE;
		else if (key == "defaultanim" && tok != "") r->unsafe = TRUE;
		else if (substring(key, 0, 2) == "on") r->refunsafe = TRUE;
		else if (key == "playbackrate" && tok != "" && stof(tok) != 1) r->unsafe = TRUE;
	}
	return TRUE;
};
void() LO_Load =
{
	local lo_record_t *r;
	local lo_record_t *temp;
	local float n, i, j, h, l, pass;
	local lo_record_t *kept;
	local string tok, key, target;
	local vector forward, right, up;
	LO_Reset();
	lo_state = (lo_state_t*)memalloc(sizeof(lo_state_t));
	temp = (lo_record_t*)memalloc(sizeof(lo_record_t));
	n = 0;
	// Keep only named references and prop candidates (including unlit collision candidates).
	for (pass = 0; pass < 2; pass = pass + 1)
	{
		n = 0; getentitytoken(0);
		while (LO_Read(temp))
		{
			if (temp->name != "" || substring(temp->classname, 0, 5) == "prop_")
			{
				if (pass) lo_records[n] = *temp;
				n = n + 1;
				if (pass) continue;
			}
			LO_FreeStrings(temp);
		}
		if (!pass) lo_records = (lo_record_t*)memalloc(sizeof(lo_record_t) * max(1, n));
	}
	memfree((__variant*)temp); lo_state->count = n;
	lo_state->apiOrigin = checkbuiltin(LO_DrawOrigin);
	lo_state->apiOffset = checkbuiltin(LO_DrawOffset);
	// Incoming I/O can move references or change consumer body/pose fields absent from the listener.
	getentitytoken(0);
	while ((key = getentitytoken()) != "")
	{
		if (key == "{" || key == "}") continue;
		tok = getentitytoken();
		if (substring(strtolower(key), 0, 2) != "on") continue;
		i = strstrofs(tok, ",", 0);
		if (i < 0) i = strstrofs(tok, "\x1b", 0);
		if (i < 0) continue;
		target = substring(tok, 0, i);
		for (i = 0; i < n; i = i + 1)
			if (!strcmp(lo_records[i].name, target) || strstrofs(target, "*", 0) >= 0)
				lo_records[i].refunsafe = TRUE;
	}
	forward = v_forward; right = v_right; up = v_up;
	for (i = 0; i < n; i = i + 1)
	{
		r = &lo_records[i];
		if (substring(r->classname, 0, 5) != "prop_") continue;
		r->mi = getmodelindex(r->model, TRUE);
		if (r->absolute == "" && r->relative == "") continue;
		lo_state->authored = lo_state->authored + 1;
		h = LO_Find(r->relative != "" ? r->relative : r->absolute);
		if (h < 0) { lo_state->missing = lo_state->missing + 1; continue; }
		if (r->unsafe || r->refunsafe || r->parent != "" || !LO_Static(&lo_records[h]) ||
			(r->absolute != "" && r->relative != ""))
		{ lo_state->unsupported = lo_state->unsupported + 1; continue; }
		if (r->relative != "")
		{
			if (lo_records[h].classname != "info_lighting_relative")
			{ lo_state->missing = lo_state->missing + 1; continue; }
			l = LO_Find(lo_records[h].landmark);
			if (l >= 0)
				if (!LO_Static(&lo_records[l]))
				{ lo_state->unsupported = lo_state->unsupported + 1; continue; }
			if (l < 0) LO_Matrix(r, &lo_records[h], __NULL__);
			else LO_Matrix(r, &lo_records[h], &lo_records[l]);
			r->mode = 2;
		}
		else { r->translation = lo_records[h].origin; r->mode = 1; }
		lo_state->resolved = lo_state->resolved + 1;
	}
	// Resolve model/spawn-origin collisions before dropping the load-only reference table.
	for (i = 0; i < n; i = i + 1)
	{
		r = &lo_records[i];
		if (!r->mode) continue;
		for (j = 0; j < n; j = j + 1)
			if (i != j && r->mi == lo_records[j].mi && r->origin == lo_records[j].origin)
			{
				r->mode = 0;
				lo_state->ambiguous = lo_state->ambiguous + 1;
				break;
			}
	}
	kept = (lo_record_t*)memalloc(sizeof(lo_record_t) * max(1, lo_state->resolved));
	j = 0;
	for (i = 0; i < n; i = i + 1)
	{
		if (lo_records[i].mode && lo_records[i].mi > 0)
		{
			kept[j] = lo_records[i]; j = j + 1;
			// One callback per model: explicitly compose with Tint_Delta.
			deltalisten(lo_records[i].model, LO_Delta, 0);
		}
		else LO_FreeStrings(&lo_records[i]);
	}
	memfree((__variant*)lo_records); lo_records = kept; lo_state->count = j;
	v_forward = forward; v_right = right; v_up = up;
	if (lo_state->unsupported) print("lightingorigin: unsupported animated/parented/moving references retained ordinary lighting\n");
};
void() LO_Info =
{
	local float i;
	local lo_record_t *r;
	local entity probe;
	if (!lo_state) { print("lightingorigin: map metadata not loaded\n"); return; }
	print(sprintf("lightingorigin: authored %.0f resolved %.0f missing %.0f unsupported %.0f bound %.0f draws %.0f rejected %.0f\n",
		lo_state->authored, lo_state->resolved, lo_state->missing, lo_state->unsupported, lo_state->bound, lo_state->draws, lo_state->rejected));
	print(sprintf("lightingorigin: enabled %g api %g/%g ambiguous %.0f; sample-only static-reference policy\n",
		cvar("vbsp_lightingorigin"), lo_state->apiOrigin, lo_state->apiOffset, lo_state->ambiguous));
	print(sprintf("lightingorigin binding: tries %.0f last model %g origin %v; draws counts accepted submissions\n",
		lo_state->bindtries, lo_state->lastmi, lo_state->lastorigin));
	for (i = 0; i < lo_state->count; i = i + 1)
	{
		r = &lo_records[i];
		if (!r->mode) continue;
		print(sprintf("  %s @ %v mode %g t %v X %v Y %v Z %v\n", r->model, r->origin, r->mode,
			r->translation, r->axisX, r->axisY, r->axisZ));
		probe = spawn(); setmodel(probe, r->model);
		print(sprintf("    model %g bounds %v .. %v (unscaled local)\n", r->mi, probe.mins, probe.maxs));
		remove(probe);
		print(sprintf("    spawn sample %v -> %v (current consumer motion uses the same affine matrix)\n", r->origin + '0 0 24',
			r->mode == 1 ? r->translation : r->translation + LO_Transform(r->axisX, r->axisY, r->axisZ, r->origin + '0 0 24')));
	}
};
