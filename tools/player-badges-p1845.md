# P1845: player badges, F8 access, and account inventory

1. Keep badge/permission authority on the linked Steam account. Add two badges without changing the legacy role mask. Keep the existing upload allowlist independently valid.
2. Backfill Tournament Tester from accepted live tournament replies using the stored match's authenticated identities. Award future testers in the same transaction that accepts `go` during the free beta.
3. Keep one **Manage…** button per linked account in `/admin/accounts`. Group actions under Badges and Items, show the current add/remove action and its explanation, and explicitly confirm changes to upload access.
4. Display the same wrapping badge chips on main-menu player profiles and in-game `hud_player` profiles, including self and inspected players. An active badge also makes an otherwise eligible account available in the profile directory without a leaderboard finish.

## Operator notes

- **Mapper Admin** permits F8 map publishing only. `mapupd` checks the Steam link, ban state and grant on the signed begin and rechecks before publication. Removing only the badge does not remove a separately granted legacy allowlist entry; see [map uploads](mapupd.md).
- **Tournament Tester** is cosmetic. The evidence is a competitor seat in an accepted live round, not a signup, a spectator seat, or a completed run. DNFs count. Participation before the update can be recovered only if the compatible live reply and recorded account identity were retained. A manual removal remains in effect across later rounds and backfills; an operator may explicitly add it again.
- Set `SURFD_TOURNAMENT_TESTER_AWARDS=0` at the end of the free beta. This stops new live awards without switching tournaments off or clearing existing badges. The migration's one-time backfill represents the tournament data predating this update.
- Roll out `surfd` first, then the separately packaged `mapupd`, then the server, client and menu progs. The optional badge field leaves old role masks and inventory messages valid. A newly badged player may have to wait for the normal profile-directory refresh before appearing in search; in-game badges use the normal account poll. No native engine change is required.

## Checks

- Run `test_inventory`, `test_mapupd`, `test_tournaments`, `test_social`, and `test_playstats` as separate Python unittest processes under `surfd/` so they each own their import-time DB and environment. The tests cover CSRF/session controls, published map bytes, revocation/ban/unlink, live participants vs. spectators, migration replay, and the JSON used by both menus.
- Run `python -B test_web.py` under `surfd/` for player-directory and board regression coverage.
- Compile all three QC VMs. For an interactive check, open a fixture account with both badges from the main-menu player search and from `hud_player`; check self and another player's view with a long name, then narrow the window or raise the UI scale to exercise chip wrapping. Existing Tester/Zoner/Developer labels should still display.
