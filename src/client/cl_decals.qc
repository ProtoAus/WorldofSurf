/*
===========================================================================
  cl_decals.qc -- infodecal.

  7649 instances across 223 maps (17.0%), and every one of them was being
  dropped: infodecal is a point entity, so SSQC's catch-all removed it as
  "nothing to preserve".  They are the wall grime, signage, numbers and
  scorch marks a Source map is dressed with, and without them surfaces that
  the mapper decorated read as blank.

  WHY THIS LIVES ON THE CLIENT.  A decal is pure rendering -- it never
  collides, never blocks and never needs to be authoritative -- so putting it
  on the wire as an entity would cost packet space and an edict each for
  something the client can derive on its own.  CSQC can read the entity lump
  directly (the same getentitytoken walk the skybox fallback uses), so the
  server never has to know these exist.

  Keys, from a census of all 7649: "texture" and "origin" on 100% of them,
  "angles" on 53.8% (and Source ignores it -- the orientation comes from the
  surface, not the entity), "lowpriority" on 11.9%.  So: a material name and
  a point, and everything else is derived.
===========================================================================
*/

// P1489: the lump walkers' map name. While CSQC_WorldLoaded runs, the world that just loaded names itself; on a
// first connect serverkey("map") is still "" there (P948), so these loaders returned and their per-frame safety
// nets loaded everything in the first frames after spawn (surf_fairy: 77 + 51 ms on the PC). Outside WorldLoaded
// the safety nets keep serverkey("map"), as before.
float  cl_worldloading;                 // CSQC_WorldLoaded is running the lump loaders
string cl_worldmapname;                 // ...the loaded world's short name then, "" otherwise
string() CL_LumpMapName =
{
	if (cl_worldloading && cl_worldmapname != "")
		return cl_worldmapname;
	return serverkey("map");
};
// P1489: the loaded world's short name, from mapname (maps/<name>.bsp in native CSQC), cut as the engine cuts
// svs.name (sv_init.c): a ".gz" or ".xz" off, then ".bsp" case-sensitively
string() CL_WorldShortName =
{
	local string w, t;
	local float n;
	w = mapname;
	if (!strcmp(substring(w, 0, 5), "maps/"))
		w = substring(w, 5, -1);
	n = strlen(w);
	if (n >= 3)
	{
		t = substring(w, n - 3, 3);
		if (!strcmp(t, ".gz") || !strcmp(t, ".xz"))
			w = substring(w, 0, n - 3);
	}
	n = strlen(w);
	if (n >= 4)
	if (!strcmp(substring(w, n - 4, 4), ".bsp"))
		w = substring(w, 0, n - 4);
	return w;
};
// P1489: serverkey("map") names the world that is loaded -- not "" (first connect) and not the previous map's
// (a map change, P948). The lazy reload latches wait for it: before it, the world's loaders ran in WorldLoaded.
float() CL_MapKeyCurrent =
{
	local string k;
	k = serverkey("map");
	if (k == "")
		return FALSE;
	return !strcasecmp(k, CL_WorldShortName());
};


/*
  adddecal_static -- clip once at spawn, cache the clipped geometry with its
  lightmap, re-render each frame as a vertex copy.

  The alternative in the shipped defs is adddecal (#375), and it is the wrong
  one here by a wide margin: it is documented as "drawn by the next
  renderscene call, and freed by the next clearscene call", so every decal
  would have to be re-issued -- and re-clipped against the BSP -- every single
  frame.  On a map with 400 decals that is 400 BSP clips per frame forever,
  to draw something that never moves.

  It is an engine addition rather than stock FTE, so it is absent from the
  defs dump and has to be declared by name.  The `#0:name` form is the same
  one crossproduct uses at cl_defs.qc:1265.
*/
float(string shadername, vector origin, vector up, vector side,
      vector rgb, optional vector alpha_aspect_life,
      optional vector srange, optional vector trange)
      adddecal_static = #0:adddecal_static;

/*
  WHY THREE SCALARS SHARE ONE VECTOR.  A builtin can be handed at most EIGHT
  arguments -- the call opcodes stop at OP_CALL8 -- and a ninth is not merely
  ignored, it is invisible: the engine's callargc reads 8 however many the QC
  wrote, and reading past the eighth slot returns unrelated globals.  That was
  measured here, not assumed: a ten-argument version of this call compiled
  without a warning and arrived with both extra vectors missing.  So alpha,
  aspect and lifetime travel together to free the two slots the texture range
  needs.

  srange/trange are that range, as (s0,s1,_) and (t0,t1,_).  Omitted means 0..1
  on both axes -- what every decal did before they existed.  They are the only
  way to express three things the projection frame cannot, because that frame
  is a fixed proper rotation:

    mirrored  s1 < s0          reflection is unreachable by any up/side
    tiled     |s1-s0| > 1      the texture repeats across the footprint
    cropped   a sub-range      only part of the image is shown

  Source's baked overlays need all three; see Overlay_Place.
*/

// Patch 894: removedecal under its own name -- cl_paint.qc declares it later in the .src.
void(float handle) Decal_RemoveStatic = #0:removedecal;

float  vbsp_decal_n;          // placed on this map
float  vbsp_decal_nosurf;     // P1721: no brush face within DECAL_PROBE in any of 26 directions
float  vbsp_decal_noclip;     // P1721: faces found, every clip produced nothing
float  vbsp_decal_hbuf;       // Patch 894: this map's decal + overlay handles (paint keeps its own)
float  vbsp_decal_hbuf_have;
float  vbsp_decal_want;       // vbsp_decals / vbsp_overlays as the last load read them
float  vbsp_overlay_want;

void(float h) Decal_Keep =
{
	if (!vbsp_decal_hbuf_have)
	{
		vbsp_decal_hbuf = buf_create();
		vbsp_decal_hbuf_have = TRUE;
	}
	bufstr_add(vbsp_decal_hbuf, ftos(h), TRUE);
};

// remove: TRUE on the same map (a live toggle). A map change already wiped them in the
// engine (CL_WipePersistentDecals), and the old handles may name the new map's decals.
void(float remove) Decal_Forget =
{
	local float i, n;

	if (!vbsp_decal_hbuf_have)
		return;
	if (remove)
	{
		n = buf_getsize(vbsp_decal_hbuf);
		for (i = 0; i < n; i = i + 1)
			Decal_RemoveStatic(stof(bufstr_get(vbsp_decal_hbuf, i)));
	}
	buf_del(vbsp_decal_hbuf);
	vbsp_decal_hbuf_have = FALSE;
};
float  vbsp_decal_seen;       // infodecal entities found, placed or not
string vbsp_decal_map;        // lazy-reload latch, same idiom as the skybox

float  vbsp_overlay_n;        // info_overlay decals placed on this map
float  vbsp_overlay_seen;     // info_overlay blocks the plugin synthesised
float  vbsp_overlay_noface;   // rejected: the overlay lists no faces (Source draws nothing either)
float  vbsp_overlay_sheared;  // rejected: the quad is too far from a rectangle to fake with one

/*
  How far to look for the surface a decal belongs to.

  Source stores a decal's position slightly OFF the face it is painted on and
  projects it onto whatever is nearest, so the surface has to be found rather
  than assumed.  24 units is generous for the gap and still short enough that
  a decal in a doorway does not reach across to the far wall.
*/
#define DECAL_PROBE 24

// How deep the projection cuts into the geometry.  Small, so a decal near a
// corner does not wrap around it; the engine clips to max(size, depth).
#define DECAL_DEPTH 8

// How far behind the origin an inward probe still counts (P1721): an origin embedded deeper is not on that face.
#define DECAL_EMBED 4

// The 26 neighbours of a cube: a decal on a slope or in a corner finds its face, as Source's radius search
// over the BSP does (r_decal.cpp R_DecalNode), where six axis probes missed (P1721).
vector(float i) Decal_ProbeDir =
{
	local float x, y;
	if (i >= 13)
		i = i + 1;	// skip the centre
	x = i - 3 * floor(i / 3);
	i = floor(i / 3);
	y = i - 3 * floor(i / 3);
	i = floor(i / 3);
	return normalize([x - 1, y - 1, i - 1]);
};

/*
  Decal_Place -- find the surface, then hand the engine its axes.

  THE VECTOR CONVENTION IS RECIPROCAL.  CL_Decal_SetupCtx (cl_ents.c) takes the LENGTHS of `up` and `side` as
  1/depth and 1/height: a bigger vector is a smaller decal, `up` points out of the surface (the engine negates
  it), `side` is the image's UP (texture t runs from +side to -side) and s runs along N x T.  srange's third
  figure carries PDC_SOURCE (1: displacements too; brush entities only once entities arrive) and PDC_SOURCESIZE (2: the material's
  `decalsize`, its texture x $decalscale, replaces side's length and the aspect; an older engine ignores both
  and draws vbsp_decal_size).

  P1721: Source orients a decal from the surface alone (r_decal.cpp R_DecalComputeBasis): a wall's T is
  straight down, a floor's S is world x.  The old tangent cross(n, z) put a wall decal's up sideways.  A clip
  that produces nothing (the nearest hit was a static prop's hull, which Source never decals) tries the
  next-nearest face with another normal, up to four.
*/
void(vector org, string tex, float size) Decal_Place =
{
	local vector dir, n, hit, s, t, t0, t1, t2;
	local float i, d, bestd, tries, h, ntried;

	ntried = 0;
	hit = t0 = t1 = t2 = '0 0 0';
	for (tries = 0; tries < 4; tries = tries + 1)
	{
		bestd = DECAL_PROBE + 1;
		n = '0 0 0';
		// Each direction twice: out from the origin, and in across it from DECAL_EMBED out to DECAL_EMBED past.
		// Hammer leaves most origins a fraction inside the face's (often func_detail) brush, where every outward
		// trace starts solid; the inward one still meets the face (ahop_coast: 25 of 26 misses).
		for (i = 0; i < 52; i = i + 1)
		{
			dir = Decal_ProbeDir(floor(i / 2));
			if (i & 1)
				traceline(org + dir * DECAL_EMBED, org - dir * DECAL_EMBED, MOVE_NOMONSTERS, world);
			else
				traceline(org, org + dir * DECAL_PROBE, MOVE_NOMONSTERS, world);
			if (trace_fraction >= 1 || trace_startsolid || trace_plane_normal == '0 0 0')
				continue;
			// World faces only.  Source paints brush entities too, but this clip runs at world load, before the
			// first entity frame, and the engine clips brush entities only from that packet (review 1).
			if (trace_ent != world)
				continue;
			if (ntried > 0 && trace_plane_normal * t0 > 0.99)
				continue;
			if (ntried > 1 && trace_plane_normal * t1 > 0.99)
				continue;
			if (ntried > 2 && trace_plane_normal * t2 > 0.99)
				continue;
			d = vlen(trace_endpos - org);
			if (d < bestd)
			{
				bestd = d;
				n     = trace_plane_normal;
				hit   = trace_endpos;
			}
		}
		if (n == '0 0 0')
			break;

		if (fabs(n_z) > 0.7071)
		{
			s = '1 0 0';
			t = crossproduct(s, n);
		}
		else
		{
			t = '0 0 -1';
			s = crossproduct(n, t);
			t = crossproduct(s, n);
		}
		t = normalize(t);

		// Lift fractionally off the surface: the clip wants the decal's centre just outside the face.
		h = adddecal_static(tex, hit + n * 0.5,
		                    n  * (1 / DECAL_DEPTH),
		                    -t * (1 / size),
		                    '1 1 1', '1 1 0',      // alpha 1, aspect 1, lifetime 0
		                    '0 1 3', '0 1 0');     // full texture; PDC_SOURCE | PDC_SOURCESIZE
		if (h >= 0)
		{
			vbsp_decal_n = vbsp_decal_n + 1;
			Decal_Keep(h);
			return;
		}
		if (ntried == 0)
			t0 = n;
		else if (ntried == 1)
			t1 = n;
		else
			t2 = n;
		ntried = ntried + 1;
	}
	if (ntried)
		vbsp_decal_noclip = vbsp_decal_noclip + 1;
	else
		vbsp_decal_nosurf = vbsp_decal_nosurf + 1;
	if (vbsp_decal_noclip + vbsp_decal_nosurf <= 12)
		dprint(sprintf("decal miss: %s at %v, %s, contents %g\n", tex, org, ntried ? "clipped to nothing" : "no surface", pointcontents(org)));
};

/*
===========================================================================
  info_overlay -- Source's OTHER decal, the one baked into the BSP.

  An infodecal is an entity: a point and a material, projected at load.  An
  overlay is not.  The mapper draws a rectangle on a face, and VBSP bakes the
  result into LUMP_OVERLAYS (45) as an oriented quad with an explicit texture
  frame -- so it has a rotation, a size, an aspect ratio and a texture range,
  none of which an infodecal has.  230 of the 1310 shipped maps carry one;
  between them that is 9702 decals that have never been drawn, because this
  engine's VBSP loader never read the lump.  surf_rise alone has 105.

  The plugin now decodes lump 45 and writes one of these blocks per overlay
  onto the end of the entity string (plugins/hl2/mod_vbsp.c, VBSP_LoadEntities),
  resolving the format's packed tangent basis to plain world-space vectors.
  What arrives here is already unambiguous:

      "material"  the VMT name, exactly as texinfo resolved it
      "origin"    the quad's CENTRE, in world space
      "normal"    unit surface normal, pointing out of the face
      "imageup"   unit world direction of image-UP
      "extent"    "<width> <height>" of the quad, in world units
      "srange"    "<s0> <s1>" texture s across the footprint (s1<s0 = mirrored)
      "trange"    "<t0> <t1>" texture t across the footprint
      "shear"     how far the quad is from a rectangle, 0..1 relative to its size
      "faces"     how many BSP faces the overlay was baked onto

  WHAT THIS CAN AND CANNOT DRAW.  adddecal_static describes a decal by an
  origin and two vectors, and the frame the engine builds from them is a proper
  rotation -- axis[1] x axis[2] is identically -axis[0].  So:

    * rotation is free (any `side` perpendicular to the normal), but
    * a REFLECTION is not reachable at all, and a hardwired 0..1 texture range
      cannot express a texture that repeats or that shows only part of itself.
      6.3% of the library's overlays are mirrored, 17.8% tile (median 13x, up
      to 344x) and 1.4% crop.  All three are handed to the engine as an
      explicit srange/trange instead, which is what Patch 246 added; the
      alternative was to drop a quarter of every affected map.
    * the footprint is a rectangle, so a sheared or trapezoidal quad can only
      be approximated by its bounding box.  93% of the library is a rectangle
      to within 1e-6 and 97.9% to within 10%, so the tolerance does the work.
===========================================================================
*/
void(vector org, vector n, vector up, float w, float h,
     vector srange, vector trange, string tex) Overlay_Place =
{
	local float depth, aspect, hnd;

	depth = cvar("vbsp_overlay_depth");
	if (depth <= 0)
		depth = 16;

	/*
	  The reciprocal convention again (see Decal_Place): |up| = 1/depth and
	  |side| = 1/radius, and radius is the FULL t extent, not a half-size.

	    radius  = h        -> the image's height maps to h world units
	    hradius = h*aspect -> so aspect = w/h gives the width
	    vradius = depth    -> vertex alpha fades to 0 at depth/2 either side

	  Keeping depth SMALL and independent of h is the whole point.  The engine
	  clips against a box max(radius, vradius) deep, so a tall overlay is always
	  clipped deep -- but with a small `depth` everything past depth/2 fades to
	  zero alpha and contributes nothing.  Without the alpha clamp added in
	  Patch 246 that same geometry came out with NEGATIVE alpha, which the
	  decal blendfunc turns into a multiplicative brightening.
	*/
	aspect = w / h;

	// Half a unit off the face.  6.7% of overlays have their origin up to one
	// unit INSIDE the surface, and none is further in than that.
	hnd = adddecal_static(tex, org + n * 0.5,
	                      n  * (1 / depth),
	                      up * (1 / h),
	                      '1 1 1', [1, aspect, 0],
	                      srange, trange);
	if (hnd >= 0)
	{
		vbsp_overlay_n = vbsp_overlay_n + 1;
		Decal_Keep(hnd);
	}
};

/*
===========================================================================
  sky_camera -- Source's 3D skybox.

  43 instances across the library.  It is a point entity marking where the
  camera should sit to view the miniature sky room the mapper built off to one
  side of the map, and without it that room is just a distant scale model
  nobody ever looks at while the sky itself is flat.

  FTE HAS THE WHOLE FEATURE ALREADY and it needs no engine work: r_refdef
  carries skyroom_pos/skyroom_enabled, R_DrawSkyroom renders the second view,
  and CSQC can set the camera per frame through VF_SKYROOM_CAMERA.  All that
  was missing was somebody reading the entity.

  THE PARALLAX -- fixed in build 13b, and this comment used to say it was not.

  Asked as "do they take into account relative position of the player? I
  believe they need to shift at a 1/16 scale."  Yes, and yes.  Source's rule
  (CSkyboxView::Setup) is

      skybox camera = sky_camera.origin + view.origin / scale

  with `scale` the entity's own key, 16 on essentially every map.  The world
  origin (0,0,0) maps to wherever the mapper put the sky_camera, and everywhere
  else follows at 1/scale.  That is what makes a 3D skybox read as *distance*:
  the model buildings drift a little as you move, the way something a long way
  off does, instead of being pinned.

  FTE's own skyroom has no scale term at all -- gl_warp.c:346 copies
  skyroom_pos straight into vieworg, so the camera never moves and the room
  behaves like a flat backdrop that only rotates.  The earlier note here said
  it "moves with you 1:1", which was wrong in the other direction; it moved not
  at all.  Neither needed engine work, because CSQC sets that camera per frame
  and can simply do Source's arithmetic before it does (cl_main.qc).

  It costs a second scene render, which is why vbsp_skyroom exists.
===========================================================================
*/
vector vbsp_skyroom_pos;
float  vbsp_skyroom_have;
float  vbsp_skyroom_scale;

void() Decal_LoadForMap =
{
	local string tok, key, tex, cn, map, tn;
	local vector org, ovn, ovup;
	local float  size, na, opened, wantdecals, sc;
	local float  ovw, ovh, ovshear, ovfaces;
	local vector ovsrange, ovtrange;
	local float  wantoverlays, shearmax;

	map = CL_LumpMapName();	// P1489
	if (map == "")
		return;

	/*
	  vbsp_decals 0 no longer skips the walk, it only skips the PLACING.

	  This pass is the only read of the entity lump the client makes, and it now
	  answers two questions -- where the decals are, and where the sky camera is.
	  Returning early on vbsp_decals 0 used to be free; now it would silently take
	  the 3D skybox away with the decals, which is not what that cvar says.
	*/
	wantdecals = cvar("vbsp_decals");
	Decal_Forget(!strcmp(map, vbsp_decal_map));

	size = cvar("vbsp_decal_size");
	if (size <= 0)
		size = 32;

	wantoverlays = cvar("vbsp_overlays");
	shearmax = cvar("vbsp_overlay_shear");
	if (shearmax <= 0)
		shearmax = 0.1;

	vbsp_decal_n = 0;
	vbsp_decal_nosurf = 0;
	vbsp_decal_noclip = 0;
	vbsp_decal_seen = 0;
	vbsp_overlay_n = 0;
	vbsp_overlay_seen = 0;
	vbsp_overlay_noface = 0;
	vbsp_overlay_sheared = 0;
	vbsp_skyroom_have = FALSE;
	vbsp_skyroom_scale = 0;
	opened = FALSE;

	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		opened = TRUE;

		cn = "";
		tex = "";
		tn = "";
		org = '0 0 0';
		sc  = 0;
		ovn = ovup = '0 0 0';
		ovw = ovh = ovshear = ovfaces = 0;
		ovsrange = ovtrange = '0 1 0';

		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			if      (key == "classname") cn  = tok;
			else if (key == "texture")   tex = tok;
			else if (key == "scale")     sc  = stof(tok);
			else if (key == "material")  tex = tok;    // info_overlay's spelling of "texture"
			else if (key == "targetname") tn = tok;
			else if (key == "shear")     ovshear  = stof(tok);
			else if (key == "faces")     ovfaces  = stof(tok);
			else if (key == "origin")
			{
				// Not stov: the lump writes a bare "x y z" and stov's
				// tolerance for that is not worth relying on when tokenize
				// says exactly what it parsed.
				na = tokenize(tok);
				if (na >= 3)
					org = [stof(argv(0)), stof(argv(1)), stof(argv(2))];
			}
			else if (key == "normal")
			{
				na = tokenize(tok);
				if (na >= 3)
					ovn = [stof(argv(0)), stof(argv(1)), stof(argv(2))];
			}
			else if (key == "imageup")
			{
				na = tokenize(tok);
				if (na >= 3)
					ovup = [stof(argv(0)), stof(argv(1)), stof(argv(2))];
			}
			else if (key == "extent")
			{
				na = tokenize(tok);
				if (na >= 2)
				{
					ovw = stof(argv(0));
					ovh = stof(argv(1));
				}
			}
			else if (key == "srange")
			{
				na = tokenize(tok);
				if (na >= 2)
					ovsrange = [stof(argv(0)), stof(argv(1)), 0];
			}
			else if (key == "trange")
			{
				na = tokenize(tok);
				if (na >= 2)
					ovtrange = [stof(argv(0)), stof(argv(1)), 0];
			}
		}

		// P1776: a NAMED infodecal waits for its Activate input (CDecal::Spawn) -- bhop_canals' arlene_blood_decals are
		// never fired, so Momentum shows no blood in that room
		if (cn == "infodecal" && tex != "" && tn == "")
		{
			vbsp_decal_seen = vbsp_decal_seen + 1;
			if (wantdecals)
				Decal_Place(org, tex, size);
		}
		else if (cn == "info_overlay" && tex != "")
		{
			vbsp_overlay_seen = vbsp_overlay_seen + 1;
			if (wantoverlays && ovw > 0 && ovh > 0 && ovn != '0 0 0' && ovup != '0 0 0')
			{
				// Source itself draws nothing for an overlay that lists no
				// faces, so placing one would ADD a decal the map never had.
				if (!ovfaces)
					vbsp_overlay_noface = vbsp_overlay_noface + 1;
				// A rectangle is all the footprint can be.  Within the
				// tolerance we draw the bounding box and the error is
				// sub-pixel; past it the shape is visibly not what was drawn.
				else if (ovshear > shearmax)
					vbsp_overlay_sheared = vbsp_overlay_sheared + 1;
				else
					Overlay_Place(org, ovn, ovup, ovw, ovh, ovsrange, ovtrange, tex);
			}
		}
		else if (cn == "sky_camera" && !vbsp_skyroom_have)
		{
			// First one wins.  A map with two sky_cameras has one per 3D skybox
			// area and picks between them with entity I/O we do not model; the
			// first is the one VBSP writes for the primary area.
			vbsp_skyroom_have  = TRUE;
			vbsp_skyroom_pos   = org;
			vbsp_skyroom_scale = sc;
		}
	}

	// Do not latch until the lump was actually readable -- serverkey("map")
	// can be set a frame or two before the entity data is, and latching early
	// would mean never looking again.  Same trap the skybox fallback hit.
	if (!opened)
		return;
	vbsp_decal_map = map;
	vbsp_decal_want = wantdecals;
	vbsp_overlay_want = wantoverlays;

	// A real print, matching the server's props/water lines: the gap between
	// "seen" and "placed" is the only signal that a map's decals failed to
	// find a surface, and a dprint hides exactly the case worth seeing.
	if (vbsp_decal_seen)
	{
		if (wantdecals)
			print(sprintf("decals: %g of %g placed (%g no surface within %g, %g clipped to nothing)\n", vbsp_decal_n,
				vbsp_decal_seen, vbsp_decal_nosurf, DECAL_PROBE, vbsp_decal_noclip));
		else
			print(sprintf("decals: %g found, none placed (vbsp_decals 0)\n", vbsp_decal_seen));
	}

	/*
	  Overlays get their own line, and it accounts for EVERY miss by name.

	  A bare "N of M" would hide the fact that the misses are three unrelated
	  things with three different answers: one we decline on purpose (Source
	  draws nothing for them either), one the rectangular footprint cannot
	  represent, and one where the engine found no geometry under the decal at
	  all -- which is the only one of the three that might be our bug.  The
	  four numbers are made to sum to the total for exactly that reason.
	*/
	if (vbsp_overlay_seen)
	{
		local float miss;
		miss = vbsp_overlay_seen - vbsp_overlay_n - vbsp_overlay_noface - vbsp_overlay_sheared;
		if (!wantoverlays)
			print(sprintf("overlays: %g found, none placed (vbsp_overlays 0)\n", vbsp_overlay_seen));
		else if (vbsp_overlay_noface + vbsp_overlay_sheared + miss)
			print(sprintf("overlays: %g of %g placed (%g no faces, %g sheared, %g off-surface)\n",
			              vbsp_overlay_n, vbsp_overlay_seen,
			              vbsp_overlay_noface, vbsp_overlay_sheared, miss));
		else
			print(sprintf("overlays: %g of %g placed\n", vbsp_overlay_n, vbsp_overlay_seen));
	}

	if (vbsp_skyroom_have)
		print(sprintf("skyroom: sky_camera at %v, map scale %g\n",
		              vbsp_skyroom_pos, vbsp_skyroom_scale));
};
