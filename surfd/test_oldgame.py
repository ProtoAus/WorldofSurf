#!/usr/bin/env python3
"""P1710: a run's unchecked mark (`oldgame`, 1 = its game could not count scripts or controller use) ranks,
is stored, rises from its recording like `pad`, and reaches the boards only on the rows that carry it.

    python surfd/test_oldgame.py
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_board  # noqa: E402
from test_plat import check, FAILS, leaf, row, board_row  # noqa: E402


def put_rec(mod, ticks, player, runid, head_pad=False, finish_pad=False, plat=None):
    """A recording where a lobby on this box would have left it, with `oldgame 1` as a finish record when asked
    (and in the header, which no build writes, when head_pad)."""
    d = os.path.join(os.environ["SURFD_RUNS"], "surf_test", mod.leg_dir(0, 0))
    os.makedirs(d, exist_ok=True)
    name = leaf(ticks, player)
    head = ["FTESURF-REC 13", "map surf_test", "track 0", "startseg 0", "leg 0", "tickrate 0.015",
            "owner %s" % player, "runid %s" % runid, "flags 0         "]
    if plat is not None:
        head.append("plat %d" % plat)
    if head_pad:
        head.append("oldgame 1")
    fin = ["prof ok"] + (["oldgame 1"] if finish_pad else [])
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(head + ["begin", "0.0000 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"] + fin
                           + ["end %d 1 0 0" % ticks]) + "\n")
    return name


def case_schema():
    mod = test_board.fresh()
    conn = sqlite3.connect(mod._test_db)
    try:
        for t in ("runs", "replays"):
            cols = {r[1]: r for r in conn.execute("PRAGMA table_info(%s)" % t)}
            check("migrate adds %s.oldgame INTEGER NOT NULL DEFAULT 0" % t,
                  "oldgame" in cols and cols["oldgame"][2] == "INTEGER" and cols["oldgame"][3] == 1
                  and cols["oldgame"][4] == "0", cols.get("oldgame"))
        mod.runs_oldgame(conn)
        check("runs_oldgame again is harmless",
              sum(1 for r in conn.execute("PRAGMA table_info(runs)") if r[1] == "oldgame") == 1)
        check("the schema version is not bumped", conn.execute("PRAGMA user_version").fetchone()[0]
              == mod.SCHEMA_VERSION)
    finally:
        conn.close()


def case_post_and_board():
    mod = test_board.fresh()
    body = test_board.submit(mod, player="pad", name="Pad", ticks="4000", runid="r-pad", oldgame="1")
    check("an oldgame 1 run is stored on the ranked board", isinstance(body, dict) and body.get("stored")
          and body.get("tier") == "ranked", body)
    check("runs.oldgame is 1", (row(mod, "pad") or {}).get("oldgame") == 1, row(mod, "pad"))
    test_board.submit(mod, player="kbm", name="Kbm", ticks="4100", runid="r-kbm")
    check("a run without oldgame stores 0", (row(mod, "kbm") or {}).get("oldgame") == 0, row(mod, "kbm"))
    for raw in ("0", "2", "x", "", "1.0"):
        test_board.submit(mod, player="g" + str(abs(hash(raw)) % 10 ** 6), name="G", ticks="4200",
                          runid="r-g" + raw, oldgame=raw)
        who = [r for r in test_board.board(mod)["rows"] if r["ticks"] == 4200]
        check("oldgame %r: accepted, filed 0" % raw, who and "oldgame" not in who[-1], who)
        conn = sqlite3.connect(mod._test_db)
        conn.execute("DELETE FROM runs WHERE ticks=4200")
        conn.commit()
        conn.close()
    test_board.submit(mod, player="both", name="Both", ticks="4300", runid="r-both", oldgame="1", plat="1")
    b = test_board.board(mod)
    check("/api/board: the marked row says oldgame 1", (board_row(b, "pad") or {}).get("oldgame") == 1, board_row(b, "pad"))
    check("/api/board: an unmarked row has no oldgame key", board_row(b, "kbm") is not None
          and "oldgame" not in board_row(b, "kbm"), board_row(b, "kbm"))
    check("/api/board: a Linux unchecked run carries both marks",
          (board_row(b, "both") or {}).get("oldgame") == 1 and (board_row(b, "both") or {}).get("plat") == 1,
          board_row(b, "both"))
    resp = mod.app.test_client().get("/board/api/map", query_string={"map": "surf_test"},
                                      environ_base={"REMOTE_ADDR": "127.0.0.1"})
    rows = json.loads(resp.get_data(as_text=True)).get("rows", []) if resp.status_code == 200 else []
    pad = [r for r in rows if r.get("name") == "Pad"]
    kbm = [r for r in rows if r.get("name") == "Kbm"]
    check("/board/api/map: the marked row says oldgame 1", pad and pad[0].get("oldgame") == 1, (resp.status_code, rows))
    check("/board/api/map: an unmarked row has no oldgame key", kbm and "oldgame" not in kbm[0], kbm)
    resp = mod.app.test_client().get("/board/api/maps", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    st = [m for m in json.loads(resp.get_data(as_text=True)).get("maps", []) if m.get("map") == "surf_test"]
    check("/board/api/maps: an unchecked WR says oldgame 1", st and (st[0].get("wr") or {}).get("oldgame") == 1, st)
    test_board.submit(mod, player="pad", name="Pad", ticks="900", leg="2", runid="r-pad", oldgame="1")
    check("a stage row keeps the mark", (board_row(test_board.board(mod, leg=2), "pad") or {}).get("oldgame") == 1)


def case_recording():
    mod = test_board.fresh()
    name = put_rec(mod, 4000, "pad", "r-pad", finish_pad=True)
    body = test_board.submit(mod, player="pad", name="Pad", ticks="4000", runid="r-pad", oldgame="1", rec=name)
    rep = row(mod, "pad", "replays")
    check("an unchecked run's recording is filed oldgame 1, bound", isinstance(body, dict) and body.get("rep")
          and rep and rep["oldgame"] == 1 and rep["bound"] == 1, (body, rep))
    name = put_rec(mod, 3990, "low", "r-low", finish_pad=True)
    body = test_board.submit(mod, player="low", name="Low", ticks="3990", runid="r-low", rec=name)
    check("a post without oldgame over a finish `oldgame 1` is filed 1, leaf kept",
          isinstance(body, dict) and body.get("rep") and (row(mod, "low") or {}).get("oldgame") == 1
          and (row(mod, "low", "replays") or {}).get("oldgame") == 1, (body, row(mod, "low")))
    name = put_rec(mod, 3980, "hd", "r-hd", head_pad=True)
    body = test_board.submit(mod, player="hd", name="Hd", ticks="3980", runid="r-hd", rec=name)
    check("a header `oldgame` (no build writes one) does not raise the mark",
          isinstance(body, dict) and (row(mod, "hd") or {}).get("oldgame") == 0, (body, row(mod, "hd")))
    name = put_rec(mod, 4100, "kbm", "r-kbm")
    body = test_board.submit(mod, player="kbm", name="Kbm", ticks="4100", runid="r-kbm", rec=name)
    check("a recording without oldgame files 0", (row(mod, "kbm") or {}).get("oldgame") == 0
          and (row(mod, "kbm", "replays") or {}).get("oldgame") == 0, (body, row(mod, "kbm")))
    # The mark only rises: a replay an older surfd filed at 0 is raised by a same-evidence re-post.
    conn = sqlite3.connect(mod._test_db)
    conn.execute("UPDATE replays SET oldgame = 0 WHERE player='pad'")
    conn.execute("DELETE FROM runs WHERE player='pad'")
    conn.commit()
    conn.close()
    name = leaf(4000, "pad")
    body = test_board.submit(mod, player="pad", name="Pad", ticks="4000", runid="r-pad", oldgame="1", rec=name)
    check("a same-evidence re-post raises the replay and stands the row marked",
          (row(mod, "pad") or {}).get("oldgame") == 1 and (row(mod, "pad", "replays") or {}).get("oldgame") == 1,
          (body, row(mod, "pad"), row(mod, "pad", "replays")))
    rid = row(mod, "pad", "replays")["id"]
    conn = sqlite3.connect(mod._test_db)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("DELETE FROM runs WHERE player='pad'")
        got = mod.restand(conn, rid)
        conn.commit()
        back = conn.execute("SELECT oldgame FROM runs WHERE player='pad' AND leg=0").fetchone()
    finally:
        conn.close()
    check("restand stands the row with its replay's mark", got == "moved" and back and back[0] == 1, (got, back))


def case_upsert():
    mod = test_board.fresh()
    test_board.submit(mod, player="flip", name="Flip", ticks="5000", runid="r-f1", oldgame="1")
    test_board.submit(mod, player="flip", name="Flip", ticks="4900", runid="r-f2")
    check("an unchecked best beaten by a checked run loses the mark", (row(mod, "flip") or {}).get("oldgame") == 0)
    resp = mod.app.test_client().get("/board/api/maps", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    st = [m for m in json.loads(resp.get_data(as_text=True)).get("maps", []) if m.get("map") == "surf_test"]
    check("/board/api/maps: an unmarked WR has no oldgame key", st and st[0].get("wr") and "oldgame" not in st[0]["wr"], st)


def main():
    case_schema()
    case_post_and_board()
    case_recording()
    case_upsert()
    print("%d failed" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
