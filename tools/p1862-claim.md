# P1862 claim

Claimed 2026-11-28T04:3xZ by Claude Code session efb4d888: CS:GO Legacy weapon workshop (SageWolf's work, continued):
session-only CS:S viewmodel mount (fs_css_weapon_mount), weapon_workshop HUD, 187 weapon + 72 glove paint kits from
the player's Legacy install, 13 faction arm rigs, CS:GO seed placement (Valve uniform random stream). Engine (fs.c,
view.c, hl2 plugin) + client QC. Branch wshop-p1862 in both repos; held off main until the current release is cut.
Root FTESurf-worktrees/viewmodel-cc-20261128.

LANDED 28 Nov 2026 on main for 0.1.73 (merge of wshop-p1862; engine merge cbedfd9d). Lobby: the release's qwprogs +
csprogs (VM_HANDS 32-63). surfd/viewmodel.py rides generation 1859 (tools/backend-pending.md).
