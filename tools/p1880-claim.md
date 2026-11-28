# P1880-P1889 claim -- worldofsurf-97 (Claude Code), 2026-11-28

bhop_canals all-effects render audit (Lex: find the reflective / refractive / point-scanning / polling work and
make it cheaper without losing the look). Root FTESurf-worktrees/canalsfx-20261128-97 (OWNER.md).

- P1880: the 3D sky room's sun cascades kept in their own atlas between frames (was: regenerated every frame,
  then the main view regenerated them again -- 8 shadow-map sides a frame for 4 cascades).
- P1881 sun rays at 60 Hz; P1882 captures reuse the view's cascades; P1883 outer cascades take turns; P1884 one
  nearest-cubemap search per entity.
- P1885-P1889 (extended 28 Nov ~07:00Z, Lex: "nothing on bhop_canals moves besides the player"): static-world
  shadow cache, exact sky pre-test for sprite sky rays, and the other static-scene exploits this audit measures.
Local candidates only until Lex says ship; nothing deployed from this root.
