#!/usr/bin/env python3
"""P1868: admin's top-10 and run page attach a runid's receipt only to the finish it is for (receipts.ticks).

    python surfd/test_p1868_finish.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_board  # noqa: E402
import test_noev  # noqa: E402
from test_plat import FAILS  # noqa: E402
from test_noev import eq  # noqa: E402


def main():
    mod = test_board.fresh()
    test_noev.setup(mod)
    for player, ticks in (("pa", 4000), ("pb", 4100)):
        test_board.submit(mod, player=player, name=player.upper(), ticks=str(ticks), runid="r-" + player)
    test_noev.receipt(mod, "r-pa", ticks=4000)          # pa's own finish
    test_noev.receipt(mod, "r-pb", ticks=4300)          # pb's runid: the receipt is for an earlier, slower finish
    import admin
    conn = sqlite3.connect(mod._test_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = {r["player"]: r for r in admin.list_top10(conn, 0, 0)}
        eq("top-10: a run's own receipt is attached", (rows["pa"]["rverdict"], rows["pa"]["rother"]),
              ("VALID", None))
        eq("top-10: another finish's receipt is not, and says which", (rows["pb"]["rverdict"], rows["pb"]["rother"]),
              (None, 4300))
        conn.execute("UPDATE receipts SET ticks = -2")  # rows read before P1868: attached as before
        rows = {r["player"]: r for r in admin.list_top10(conn, 0, 0)}
        eq("top-10: an unread receipt is attached as before", (rows["pb"]["rverdict"], rows["pb"]["rother"]),
              ("VALID", None))
        conn.execute("UPDATE receipts SET ticks = 4300 WHERE runid = 'r-pb'")
        ids = {}
        for player, ticks in (("pa", 4000), ("pb", 4100)):
            ids[player] = conn.execute(
                "INSERT INTO replays (map, map_dir, track, leg, leaf, tier, style, player, name, ticks, tickrate,"
                " millis, flags, node, submitted, runid, kind) VALUES ('surf_test', 'surf_test', 0, 0, ?, 'ranked',"
                " 'clean', ?, ?, ?, 0.01, ?, 0, '', 1, ?, 'run')",
                ("%07d_%s.rec" % (ticks, player), player, player.upper(), ticks, ticks * 10, "r-" + player)).lastrowid
        got = admin.receipt_for(conn, ids["pb"], "r-pb")
        eq("run page: another finish's receipt is flagged", got["other_finish"] if got else "no receipt", 4300)
        got = admin.receipt_for(conn, ids["pa"], "r-pa")
        eq("run page: a run's own receipt is not flagged", got["other_finish"] if got else "no receipt", None)
        conn.execute("UPDATE receipts SET ticks = -2 WHERE runid = 'r-pb'")
        got = admin.receipt_for(conn, ids["pb"], "r-pb")
        eq("run page: an unread receipt is not flagged", got["other_finish"] if got else "no receipt", None)
    finally:
        conn.close()
    print("%d failed" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
