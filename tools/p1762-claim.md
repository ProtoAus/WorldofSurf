P1762 + P1763 + P1764 claimed by Claude Code session worldofsurf-67, 2026-11-24 UTC. Lex 24 Nov "please finish up and then
release to lobbies" (the bhop_canals leftovers of P1758-P1760). Root FTESurf-worktrees/canalsgfx-20261124-67.
P1762 (engine gl_shadow.c, plugin hl2 glsl/vmt lightmapped/transition/vertexlit): r_shadows 2 sun cascades on Source maps
-- the vmt receivers read the cascade atlas; env_cascade_light's maxshadowdistance sets the reach.
P1763 (plugin hl2 glsl/vmt/vertexlit.glsl): a bumped VertexLitGeneric takes its directional (sun) light per pixel
through the normal map, as Source does.
P1764 (engine + game cl_sun.qc): Source HDR auto-exposure on HDR maps (env_tonemap_controller band, adaptation).
