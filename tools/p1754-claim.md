P1754 + P1755 claimed by Claude Code session worldofsurf-08, 2026-11-23 UTC.
Lex 23 Nov: "the timer and save counter updating the moment you press, delete and goto not waiting on the server,
and the brief stutter on long runs ... see if you can fix that please". P1754: STAT_FS_WOPCLK (213) carries the run
clock of each row STAT_FS_WOPCUR/WOPCHAIN publishes, bound to that C string by crc16 + length; a predicted load or
step draws its row's clock in the timer panel (frozen while held, the server's commands after it otherwise) and the
save panel walks the pending ops (WarpOp_PredList). P1755: sl_del/sl_delall shown on the press (counted by
STAT_FS_SLACK); `sl_goto n` rides the key that lands on n when nothing is pending. P1756: the line picture on long
runs (engine writes, a cut for a save still on the line, a time-bounded catch-up). P1757: a save's .view prefix stays
warm across a file load (marks checked by their last line). Reviews: P1754/P1755 four rounds, P1756/P1757 three.
