P1752 claimed by Claude Code session worldofsurf-08, 2026-11-23 UTC.
Lex 23 Nov: "999 saves ... I don't want players to think about it", "zero prederrors, instant and smooth"; then
"Yes, do all 3" (shared-prefix recordings + 999, client-owned save list, the hold-release mispredict).
Part 1 (server, this patch): spine recordings. A lobby save appends only the stream bytes since the player's last
save to one spine per branch (data/saves/<map>/@<guid>/spines/*.rec) and lists its segments in state.txt (`recseg
<spine> <from> <to>`); warm loads branch a child spine at the cut on the next save; cold loads, new streams and
legacy run.rec saves start a root spine (one full copy, today's cost). The lobby window SL_RECKEEP = FS_MAXSAVES.
A rescan of a lobby block sweeps spines no save (and no live player) references. First cut without spines was
rejected (queue freeze + disk); see BACKLOG "Save-lock audit 23 Nov".
