!!ver 100 150
!!permu FRAMEBLEND
!!permu SKELETAL
!!permu FOG
!!samps 10 envcube:Cube=10
!!cvar3f cl_wkit_state
!!cvarf cl_wshop_scale
!!cvarf cl_wshop_rotation
!!cvarf cl_wshop_x
!!cvarf cl_wshop_y
!!cvarf cl_wshop_tint
!!cvar3f cl_wkit_opts0
!!cvar3f cl_wkit_opts1
!!cvar3f cl_wkit_opts2
!!cvar3f cl_wkit_opts3
!!cvar3f cl_wkit_opts4
!!cvar3f cl_wkit_place
!!cvar3f cl_wkit_col0
!!cvar3f cl_wkit_col1
!!cvar3f cl_wkit_col2
!!cvar3f cl_wkit_col3
#include "sys/defs.h"

// Program defines from cl_paintkit.qc PK_Shader: STYLE (CS:GO paint style), EDIT (custom placement),
// UVS (pattern UV scale: the material's $previewweaponuvscale unless the kit ignores weapon size),
// WEARS ($weartexturetransform scale), ENV (stock $envmaptint), NORMAL (kit normal map in s_t9).
// Samplers: base, pattern, masks, ao, pos, surface, paint_wear, gun_grunge, $exptexture, normal, $reflectcube.
#ifndef UVS
#define UVS 1.0
#endif
#ifndef WEARS
#define WEARS 1.0
#endif
#ifndef ENV
#define ENV 0.2
#endif

varying vec2 kit_uv;
varying vec3 kit_normal, kit_s, kit_t, kit_eye;
#ifdef VERTEX_SHADER
#include "sys/skeletal.h"
void main()
{
	vec3 w, n, s, t;
	gl_Position = skeletaltransform_wnst(w, n, s, t);
	kit_uv = v_texcoord;
	kit_normal = n;
	kit_s = s;
	kit_t = t;
	kit_eye = e_eyepos - w;
}
#endif
#ifdef FRAGMENT_SHADER
#include "sys/fog.h"
uniform vec3 cvar_cl_wkit_state;   // active item: wear, seed (cl_paintkit.qc PK_State)
uniform float cvar_cl_wshop_scale, cvar_cl_wshop_rotation, cvar_cl_wshop_x, cvar_cl_wshop_y, cvar_cl_wshop_tint;
uniform vec3 cvar_cl_wkit_opts0, cvar_cl_wkit_opts1, cvar_cl_wkit_opts2, cvar_cl_wkit_opts3, cvar_cl_wkit_opts4;
uniform vec3 cvar_cl_wkit_place;
uniform vec3 cvar_cl_wkit_col0, cvar_cl_wkit_col1, cvar_cl_wkit_col2, cvar_cl_wkit_col3;

float kit_sample(float seed, float stream)
{
	return mod(seed * (313.0 + 112.0 * stream) + 233.0 * stream, 1009.0) / 1009.0;
}
vec3 kit_palette(vec3 w, vec3 a, vec3 b, vec3 c, vec3 d)
{
	return mix(mix(mix(a, b, w.r), c, w.g), d, w.b) / 255.0;
}
void main()
{
	vec4 basetex = texture2D(s_t0, kit_uv);   // alpha: stock phong mask ($basemapalphaphongmask)
	vec4 mask = texture2D(s_t2, kit_uv);
	vec4 ao = texture2D(s_t3, kit_uv);
	vec3 posmap = texture2D(s_t4, kit_uv).rgb;
	vec3 surface = texture2D(s_t5, kit_uv).rgb;
	float seed = floor(clamp(cvar_cl_wkit_state.y, 0.0, 1000.0));
	// Seeded offset/rotation from CS:GO's random stream (cl_paintkit.qc PK_Place).
	vec2 shift = cvar_cl_wkit_place.xy;
	float angle = cvar_cl_wkit_place.z;
	float scale = cvar_cl_wkit_opts3.z * UVS;
	float wear = clamp(cvar_cl_wkit_state.x, 0.0, 1.0);
	vec2 uv = kit_uv;
#if STYLE == 3 || STYLE == 6
	// Use authored model positions for projected spray and airbrush styles.
	uv = mix(kit_uv, posmap.xz, 0.70);
#endif
#if EDIT == 1
	shift += clamp(vec2(cvar_cl_wshop_x, cvar_cl_wshop_y), -1.0, 1.0);
	angle += clamp(cvar_cl_wshop_rotation, -180.0, 180.0);
	scale *= clamp(cvar_cl_wshop_scale, 0.25, 4.0);
#endif
	angle = radians(angle);
	// Source texture transform: uv' = R(angle) * scale * (uv - 0.5) + 0.5 + offset.
	mat2 rotation = mat2(cos(angle), sin(angle), -sin(angle), cos(angle));
	vec2 patternuv = rotation * (uv - 0.5) * scale + 0.5 + shift;
	vec3 pattern = texture2D(s_t1, patternuv).rgb;
	vec3 paint;
#if STYLE == 1 || STYLE == 4
	paint = kit_palette(mask.gba, cvar_cl_wkit_col0, cvar_cl_wkit_col1, cvar_cl_wkit_col2, cvar_cl_wkit_col3);
#elif STYLE == 8
	// Patina: a neutral pattern weights the kit's metal tints (Stainless, Blue Steel, Stained match CS:GO's
	// icons); a coloured one (Case Hardened's oiled) keeps its own hues. Fitted to the icons, not Valve's formula.
	float sat = max(pattern.r, max(pattern.g, pattern.b)) - min(pattern.r, min(pattern.g, pattern.b));
	paint = mix(kit_palette(pattern, cvar_cl_wkit_col0, cvar_cl_wkit_col1, cvar_cl_wkit_col2, cvar_cl_wkit_col3), pattern, smoothstep(0.08, 0.25, sat));
#elif STYLE == 7 || STYLE == 9
	paint = pattern;
#else
	paint = kit_palette(pattern, cvar_cl_wkit_col0, cvar_cl_wkit_col1, cvar_cl_wkit_col2, cvar_cl_wkit_col3);
#endif
#if EDIT == 1
	float tint = clamp(cvar_cl_wshop_tint, -1.0, 1.0);
	paint *= vec3(1.0 + 0.55 * tint, 1.0, 1.0 - 0.55 * tint);
#endif
	vec2 wearuv = kit_uv * WEARS + vec2(kit_sample(seed, 4.0), kit_sample(seed, 5.0));
	float weartex = texture2D(s_t6, wearuv).r;
	float grunge = texture2D(s_t7, kit_uv * WEARS + shift).r;
	float edge = clamp(max(surface.r, ao.g * 0.75), 0.0, 1.0);
	float abrasion = smoothstep(0.70, 0.84, weartex * 0.43 + edge * 0.30 + grunge * 0.11 + wear * 0.82);
#ifdef NOPAINT
	float coverage = 0.0;   // the stock material (Original), lit and reflected like a painted one
#elif STYLE == 7 || STYLE == 9
	float coverage = 1.0 - abrasion;
#else
	float coverage = mask.r * (1.0 - abrasion);
#endif
	vec3 albedo = mix(basetex.rgb, paint * mix(0.65, 1.18, ao.r) * mix(0.78, 1.08, grunge), coverage);

	vec3 n = normalize(kit_normal);
#if NORMAL == 1
	vec3 tn = texture2D(s_t9, patternuv).xyz * 2.0 - 1.0;
	tn = normalize(mix(vec3(0.0, 0.0, 1.0), tn, coverage));   // worn-through metal is flat
	if (dot(kit_s, kit_s) > 1e-8 && dot(kit_t, kit_t) > 1e-8)   // no tangents: keep the vertex normal
		n = normalize(tn.x * normalize(kit_s) + tn.y * normalize(kit_t) + tn.z * n);
#endif
	// Lit like defaultskin (the hands): ambient plus the directional term, the shade side softened.
	float d = dot(n, e_light_dir);
	if (d < 0.0)
		d *= 13.0 / 44.0;
	vec3 light = e_light_ambient + d * e_light_mul;
	vec3 v = normalize(kit_eye);
	// A viewmodel's light_dir can be zero: normalizing it gave NaN (black). No direction, no highlight.
	float ll = dot(e_light_dir, e_light_dir);
	vec3 h = normalize((ll > 1e-8 ? e_light_dir * inversesqrt(ll) : n) + v);
	// Bare metal: the stock exponent map (Source 1 + 149 * r) and base alpha mask; paint: the kit's phong.
	float exponent = mix(1.0 + 149.0 * texture2D(s_t8, kit_uv).r, cvar_cl_wkit_opts4.y, coverage);
	float specmask = mix(basetex.a, cvar_cl_wkit_opts4.z / 255.0, coverage);
	vec3 spec = pow(max(dot(n, h), 0.0), max(exponent, 1.0)) * specmask * max(e_light_mul, vec3(0.0)) * step(1e-8, ll);
	// The batch's nearest env_cubemap ($reflectcube); stock $envmaptint with $envmapfresnel, more on anodized metal.
	float fresnel = 0.2 + 0.8 * pow(1.0 - clamp(dot(n, v), 0.0, 1.0), 3.0);
	vec3 r = (m_model * vec4(reflect(-v, n), 0.0)).xyz;
	vec3 env = textureCube(s_envcube, r).rgb * fresnel;
#if STYLE == 4 || STYLE == 5 || STYLE == 6
	vec3 envtint = mix(vec3(ENV), sqrt(max(paint, vec3(0.0))) * 0.6, coverage);
#else
	vec3 envtint = vec3(ENV) * (1.0 - coverage * 0.8);
#endif
	vec3 col = albedo * light * e_colourident.rgb + spec + env * envtint;
	gl_FragColor = fog4(vec4(col, 1.0));
}
#endif
