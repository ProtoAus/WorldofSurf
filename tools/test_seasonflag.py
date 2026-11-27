#!/usr/bin/env python3
"""P1857 falsifiers for tools/seasonflag.py's season() and its report writer (synthetic rows, no Pi)."""
import json
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seasonflag as sf  # noqa: E402

FAILS = []


def check(ok, msg):
    print(("ok    " if ok else "FAIL  ") + msg)
    if not ok:
        FAILS.append(msg)


def pool(seed=1857, players=8, runs=30, spread=0.3, noise=1.4):
    rng = random.Random(seed)
    rows = []
    for k in range(players):
        mu = rng.gauss(0.0, spread)
        for _ in range(runs):
            rd = rng.gauss(mu, noise)
            rows.append(dict(who="p%d" % k, name="P%d" % k, rd=rd, rd_inj=rd + 1.72))
    return rows


rows = pool()
rep = sf.season(rows)
check(rep["qualifying_players"] == 8 and rep["flagged"] == [],
      "8 honest players, 30 runs each: none flagged (honest max |z| %s)" % rep["honest_max_abs_z"])
check(rep["always_on_min_z"] is not None and rep["always_on_min_z"] > rep["honest_max_abs_z"],
      "the always-on control sits above the honest pool (%s > %s)" % (rep["always_on_min_z"], rep["honest_max_abs_z"]))
cheat = [dict(r, rd=r["rd_inj"]) if r["who"] == "p3" else r for r in rows]
rc = sf.season(cheat)
check([p["who"] for p in rc["flagged"]] == ["p3"], "an optimiser on every run of one player: that player alone is flagged (z %s)"
      % next(p["z"] for p in rc["players"] if p["who"] == "p3"))
half = [dict(r, rd=r["rd_inj"]) if r["who"] == "p3" and i % 2 == 0 else r for i, r in enumerate(rows)]
check(all(p["who"] != "p3" or p["z"] < next(q["z"] for q in rc["players"] if q["who"] == "p3") for p in sf.season(half)["players"]),
      "half-time use scores lower than always-on (the stated limit)")
few = rows + [dict(who="new", name="New", rd=9.0, rd_inj=10.0) for _ in range(19)]
rf = sf.season(few)
check(all(p["who"] != "new" for p in rf["players"]) and rf["measured_players"] == 9,
      "19 runs is under MIN_RUNS: measured, never compared or flagged")
tiny = [r for r in rows if r["who"] in ("p0", "p1")]
check(sf.season(tiny)["players"] == [], "two qualifying players: no z is computed (nothing to compare against)")
check(sf.season([])["honest_max_abs_z"] is None and sf.season([])["flagged"] == [], "no rows: an empty, honest report")
with tempfile.TemporaryDirectory() as d:
    out = os.path.join(d, "s.json")
    sf.write_atomic(out, rep)
    check(json.load(open(out))["qualifying_players"] == 8 and not [n for n in os.listdir(d) if n.endswith(".part")],
          "the report is written whole, no temporary left behind")
print("\n%d failed" % len(FAILS))
sys.exit(1 if FAILS else 0)
