# P1861 claim

Claimed 2026-11-28T03:5xZ by Claude Code session efb4d888 (CS:GO weapon workshop owner): plugins/hl2/mod_hl2.c
Mod_HL2_ReadPose -- stop the pose chain at the first bone >= numbones (Source ignores those entries). Legacy
glove/arm rigs (17 models, e.g. bone 72 in a 48-bone rig) wrote one matrix past the pose buffer: heap abort.
Engine-only plugin fix, separate from the (held) weapon-workshop work. Root FTESurf-worktrees/viewmodel-cc-20261128.
