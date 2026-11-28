!!ver 100 150
!!permu FRAMEBLEND
!!permu SKELETAL
!!permu FOG
!!samps 7
!!cvar3f cl_gkit_state
!!cvar3f cl_gkit_opts0
!!cvar3f cl_gkit_opts1
!!cvar3f cl_gkit_opts2
!!cvar3f cl_gkit_opts3
!!cvar3f cl_gkit_opts4
!!cvar3f cl_gkit_opts5
!!cvar3f cl_gkit_opts6
!!cvar3f cl_gkit_opts7
!!cvar3f cl_gkit_place
!!cvar3f cl_gkit_col0
!!cvar3f cl_gkit_col1
!!cvar3f cl_gkit_col2
!!cvar3f cl_gkit_col3
!!cvar3f cl_gkit_col4
!!cvar3f cl_gkit_col5
!!cvar3f cl_gkit_col6
!!cvar3f cl_gkit_col7
#include "sys/defs.h"

varying vec2 glove_uv;
varying vec3 glove_normal, glove_s, glove_t;
#ifdef VERTEX_SHADER
#include "sys/skeletal.h"
void main()
{
	vec3 w, n, s, t;
	gl_Position = skeletaltransform_wnst(w, n, s, t);
	glove_uv = v_texcoord;
	glove_normal = n;
	glove_s = s;
	glove_t = t;
}
#endif
#ifdef FRAGMENT_SHADER
#include "sys/fog.h"
uniform vec3 cvar_cl_gkit_state;   // gloves: wear, seed (cl_paintkit.qc PK_State)
uniform vec3 cvar_cl_gkit_opts0, cvar_cl_gkit_opts1, cvar_cl_gkit_opts2, cvar_cl_gkit_opts3;
uniform vec3 cvar_cl_gkit_opts4, cvar_cl_gkit_opts5, cvar_cl_gkit_opts6, cvar_cl_gkit_opts7;
uniform vec3 cvar_cl_gkit_place;
uniform vec3 cvar_cl_gkit_col0, cvar_cl_gkit_col1, cvar_cl_gkit_col2, cvar_cl_gkit_col3;
uniform vec3 cvar_cl_gkit_col4, cvar_cl_gkit_col5, cvar_cl_gkit_col6, cvar_cl_gkit_col7;

vec3 glove_palette(float i)
{
	if (i <= 1.0) return cvar_cl_gkit_col0;
	if (i <= 2.0) return cvar_cl_gkit_col1;
	if (i <= 3.0) return cvar_cl_gkit_col2;
	if (i <= 4.0) return cvar_cl_gkit_col3;
	if (i <= 5.0) return cvar_cl_gkit_col4;
	if (i <= 6.0) return cvar_cl_gkit_col5;
	if (i <= 7.0) return cvar_cl_gkit_col6;
	return cvar_cl_gkit_col7;
}
vec3 pattern_palette(float index, vec3 fallback)
{
	return index > 0.0 ? glove_palette(index) : fallback;
}
void main()
{
	vec4 mask = texture2D(s_t0, glove_uv);
	vec3 ao = texture2D(s_t1, glove_uv).rgb;
	// In the inspected VTFs alpha contains eight separated palette values;
	// R/G/B are separate material area masks for texture scale and wear.
	float palette = min(8.0, floor(mask.a * 8.0) + 1.0);
	float detail_scale = mix(cvar_cl_gkit_opts7.x, cvar_cl_gkit_opts6.x, mask.r);
	detail_scale = mix(mix(detail_scale, cvar_cl_gkit_opts6.y, mask.g), cvar_cl_gkit_opts6.z, mask.b);
	vec2 detail_uv = glove_uv * detail_scale;
	vec3 grunge = texture2D(s_t2, glove_uv * cvar_cl_gkit_opts5.y).rgb;
	float detail = texture2D(s_t3, detail_uv).r;
	vec3 paint = glove_palette(palette);
	if (cvar_cl_gkit_opts5.z > 0.0 && palette == cvar_cl_gkit_opts5.x)
	{
		// Seeded placement as for weapons (cl_paintkit.qc PK_Place).
		float angle = radians(cvar_cl_gkit_place.z);
		mat2 rot = mat2(cos(angle), sin(angle), -sin(angle), cos(angle));
		vec2 shift = cvar_cl_gkit_place.xy;
		vec3 p = texture2D(s_t4, rot * (glove_uv - 0.5) * cvar_cl_gkit_opts3.z + 0.5 + shift).rgb;
		paint = mix(pattern_palette(cvar_cl_gkit_opts4.x, paint), pattern_palette(cvar_cl_gkit_opts4.y, paint), p.r);
		paint = mix(mix(paint, pattern_palette(cvar_cl_gkit_opts4.z, paint), p.g), pattern_palette(cvar_cl_gkit_opts7.y, paint), p.b);
	}
	float wear = clamp(cvar_cl_gkit_state.x, cvar_cl_gkit_opts0.x, cvar_cl_gkit_opts0.y);
	float worn = smoothstep(0.58, 0.94, 0.50 * grunge.r + 0.26 * ao.g + 0.65 * wear);
	vec3 n = normalize(glove_normal);
	vec3 tangent_detail = texture2D(s_t5, detail_uv).xyz * 2.0 - 1.0;
#if NORMAL == 1
	tangent_detail += (texture2D(s_t6, glove_uv).xyz * 2.0 - 1.0) * 1.5;
#endif
	n = normalize(n + 0.2 * (tangent_detail.x * glove_s + tangent_detail.y * glove_t));
	// Lit like defaultskin (the bare hands beside it): ambient plus directional, shade side softened.
	float d = dot(n, e_light_dir);
	if (d < 0.0)
		d *= 13.0 / 44.0;
	vec3 light = (e_light_ambient + d * e_light_mul) * e_colourident.rgb;
	vec3 colour = mix(paint / 255.0, paint * (0.62 / 255.0) + vec3(0.08, 0.055, 0.033), worn);
	gl_FragColor = fog4(vec4(colour * mix(0.64, 1.25, detail) * mix(0.42, 1.0, ao.r) * light, 1.0));
}
#endif
