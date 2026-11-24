# P1765-P1772 claim (worldofsurf-67, 24 Nov; root FTESurf-worktrees/canalsgfx-20261124-67)

Lex's second bhop_canals graphics pass after 0.1.64 (saves 11-20 beside Momentum):
- P1765 cascade-map sun shadows: shadowed light = lit minus the sun's direct term (light_environment's colour and
  angle), no contact fade on env_cascade_light maps (their lightmaps carry no sun shadows), props receive (self-shadow).
- P1766 shadows that blink in and out while moving.
- P1767 vbsp_autoexposure takes effect at once; indoor exposure vs Momentum.
- P1768 alpha-tested shadow casters (bushes shadow their branches, not the whole card).
- P1769 the barn light shafts: distance fade, the reddish tint.
- P1770 pale trees and the black/white street lamp (model lighting).
- P1771 glass window reflections ($envmap on the window material).
- P1772 func_smokevolume (the canal basin haze).
Numbers may be dropped or merged; the records say which shipped.
