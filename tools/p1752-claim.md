P1752 claimed by Claude Code session worldofsurf-08, 2026-11-23 UTC. NOT LANDED -- design stage.
Lex 23 Nov: "I want the limit raised to like 999 ... cap the user at 999. I don't want players to think about it", plus
"zero prederrors, everything instant and smooth"; asked whether save/load could move client-side.
A first cut (SL_RECKEEP = FS_MAXSAVES, rig-passed: 30/30 timed saves kept their run) was REJECTED in review and never
pushed: demotion was also the only bound on the per-player recording-copy queue (SV_RecCopyFlush copies everything in
one frame at the next load/finish/park/map change -> a save spammer deep in a long run could freeze a lobby for
minutes) and on disk (999 full prefixes per map per player; data/saves is never cleaned).
Plan (needs Lex's go): shared-prefix ("spine") recordings so a save costs only the bytes since the last one, then the
window goes to 999; the client trail copies per save need the same treatment. See BACKLOG "Save-lock audit 23 Nov".
