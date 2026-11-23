P1758 + P1759 + P1760 claimed by Claude Code session worldofsurf-67, 2026-11-23 UTC (24 Nov local).
Lex 24 Nov, bhop_canals graphics vs Momentum (saves 5-8). Root FTESurf-worktrees/canalsgfx-20261124-67.
P1758 (engine plugins/hl2 img_vtf.c, mat_vmt.c): Source compressed-HDR sky faces (RGBS in BGRA8) decode their RGB
as LINEAR, not sRGB (the sRGB read banded the clouds into contours and turned sky_day01_05_hdr green), and HDR sky
faces are encoded to sRGB for the gamma framebuffer (vid_srgb 0) as Patch 887 does for float cubemaps.
P1759 (game src/server/sv_entities.qc): a prop's rendercolor (and its Color input) tints it, as Patch 1250 does
for brush entities -- bhop_canals' vol_light shafts are tinted 21 18 13 and drew at full white.
P1760 (game + engine as needed): on a Strata env_cascade_light map a prop casts the cascade (sun) shadow unless
disableshadowdepth -- disableshadows only turns off Source's RTT blob shadow; plus r_shadows 2 quality there.
