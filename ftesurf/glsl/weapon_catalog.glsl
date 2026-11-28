!!ver 100 150
!!permu FRAMEBLEND
!!permu SKELETAL
!!permu FOG
!!samps 8
!!cvarf cl_wshop_seed
!!cvarf cl_wshop_wear
!!cvarf cl_wshop_gunwear
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

varying vec2 kit_uv;
varying vec3 kit_normal, kit_eye;
#ifdef VERTEX_SHADER
#include "sys/skeletal.h"
void main()
{
	vec3 w, n, s, t;
	gl_Position = skeletaltransform_wnst(w, n, s, t);
	kit_uv = v_texcoord;
	kit_normal = n;
	kit_eye = e_eyepos - w;
}
#endif
#ifdef FRAGMENT_SHADER
#include "sys/fog.h"
uniform float cvar_cl_wshop_seed, cvar_cl_wshop_wear, cvar_cl_wshop_gunwear;
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
	vec3 base = texture2D(s_t0, kit_uv).rgb;
	vec4 mask = texture2D(s_t2, kit_uv);
	vec4 ao = texture2D(s_t3, kit_uv);
	vec3 posmap = texture2D(s_t4, kit_uv).rgb;
	vec3 surface = texture2D(s_t5, kit_uv).rgb;
	float seed = floor(clamp(cvar_cl_wshop_seed, 0.0, 1000.0));
	// Seeded offset/rotation from CS:GO's random stream (cl_paintkit.qc PK_Place).
	vec2 shift = cvar_cl_wkit_place.xy;
	float angle = cvar_cl_wkit_place.z;
	float scale = cvar_cl_wkit_opts3.z;
#if PISTOL == 1
	float wear = cvar_cl_wshop_gunwear;
#else
	float wear = cvar_cl_wshop_wear;
#endif
	wear = clamp(wear, cvar_cl_wkit_opts0.x, cvar_cl_wkit_opts0.y);
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
	vec3 pattern = texture2D(s_t1, rotation * (uv - 0.5) * scale + 0.5 + shift).rgb;
	vec3 paint;
#if STYLE == 1 || STYLE == 4
	paint = kit_palette(mask.gba, cvar_cl_wkit_col0, cvar_cl_wkit_col1, cvar_cl_wkit_col2, cvar_cl_wkit_col3);
#elif STYLE == 7 || STYLE == 8 || STYLE == 9
	paint = pattern;
#else
	paint = kit_palette(pattern, cvar_cl_wkit_col0, cvar_cl_wkit_col1, cvar_cl_wkit_col2, cvar_cl_wkit_col3);
#endif
#if EDIT == 1
	float tint = clamp(cvar_cl_wshop_tint, -1.0, 1.0);
	paint *= vec3(1.0 + 0.55 * tint, 1.0, 1.0 - 0.55 * tint);
#endif
	vec2 wearuv = kit_uv + vec2(kit_sample(seed, 4.0), kit_sample(seed, 5.0));
	float weartex = texture2D(s_t6, wearuv).r;
	float grunge = texture2D(s_t7, kit_uv + shift).r;
	float edge = clamp(max(surface.r, ao.g * 0.75), 0.0, 1.0);
	float abrasion = smoothstep(0.70, 0.84, weartex * 0.43 + edge * 0.30 + grunge * 0.11 + wear * 0.82);
	vec3 n = normalize(kit_normal);
	vec3 v = normalize(kit_eye);
	vec3 l = normalize(e_light_dir + 0.001);
	float direct = max(0.0, dot(n, l));
	vec3 light = clamp(e_light_ambient + (0.25 + 0.75 * direct) * e_light_mul, 0.55, 1.30);
	float spec = pow(max(0.0, dot(n, normalize(l + v))), mix(cvar_cl_wkit_opts4.y, 16.0, abrasion));
#if STYLE == 7 || STYLE == 9
	float coverage = 1.0 - abrasion;
#else
	float coverage = mask.r * (1.0 - abrasion);
#endif
	vec3 coloured = mix(base, paint * mix(0.65, 1.18, ao.r) * mix(0.78, 1.08, grunge), coverage);
	float fresnel = pow(1.0 - clamp(dot(n, v), 0.0, 1.0), 3.0);
	vec3 reflected = mix(vec3(0.18), paint, 0.42) * (spec + fresnel * 0.22) * cvar_cl_wkit_opts4.z / 255.0;
#if STYLE == 4 || STYLE == 5 || STYLE == 6 || STYLE == 8
	reflected += sqrt(max(paint, vec3(0.0))) * (0.23 + 0.40 * spec + 0.33 * fresnel) * (1.0 - abrasion * 0.75);
#endif
	gl_FragColor = fog4(vec4(coloured * light + reflected * coverage, 1.0));
}
#endif
