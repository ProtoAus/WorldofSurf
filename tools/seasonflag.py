#!/usr/bin/env python3
"""seasonflag.py -- the review-only season strafe flag (P1857).

WHAT IT SAYS.  strafestats.py's RD step (the strafe-quality discontinuity at 280 u/s) is too noisy to judge one run:
a full-power optimiser sits ~2.5 standard deviations from honest on a single run.  Averaged over a player's season it
separates: on 28 Nov 2026 (523 measurable lobby runs, 41 players) an optimiser on every run put a player with >= 20
runs at z 3.15-8.0 against the other qualifying players, while the most unusual honest player sat at 2.37.  So this
tool flags, FOR REVIEW ONLY, a player with >= MIN_RUNS measurable runs whose season mean is >= Z_FLAG standard
deviations above the other qualifying players' means.  Part-time use does not separate (z 0.6-5.2 at half the runs)
and the honest pool is small, so the margin is printed with every run of this tool and must be re-read as it grows.
It never accuses, ranks or hides anything.

WHO IS WHO.  A run's identity is its receipt's signing key (hashed) when the backend has one, else the recording's
owner name (hashed) -- the same keying as the 18/28 Nov measurements.  The display name is the recording's own `owner`.

HOW.  Read-only: surfd.db is opened mode=ro; recordings are only read.  Per recording the RD step is measured once,
honest and with StrafePro v2 at max power added above its gate (the control that shows the margin), and cached by
path + size + mtime, so a daily run reads only new files.  The report is written atomically.

usage: seasonflag.py --runs <game>/ftesurf/data/runs --db surfd.db --cache cache.json --out seasonflag.json
"""
import argparse
import glob
import hashlib
import json
import os
import sqlite3
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strafestats  # noqa: E402

MIN_SUPPORT = 20        # RD samples needed on each side of the 280 u/s cut for a run to count (as measured)
MIN_RUNS = 20           # measurable runs before a player's season mean is compared
Z_FLAG = 3.0            # season-mean z (against the other qualifying players) that is flagged for review
VERSION = 1


def run_identity(path):
    """(runid, owner) from a recording's header, or (None, None)."""
    rid = owner = None
    try:
        with open(path, "rb") as fh:
            for raw in fh:
                s = raw.decode("utf-8", "replace").strip()
                if s == "begin":
                    break
                if s.startswith("runid "):
                    rid = s[6:].strip()
                elif s.startswith("owner "):
                    owner = s[6:].strip()
    except OSError:
        pass
    return rid, owner


def measure(path):
    """One recording -> (rd, nlo, nhi, rd_injected) or None when the statistic is undefined."""
    r = strafestats.analyse(path)
    if not r or r.get("rd") != r.get("rd") or len(r.get("rd_n") or ()) != 2:
        return None
    ri = strafestats.analyse(path, inject_k=(0.5 * strafestats.M_YAW, "v2"))
    nlo, nhi = r["rd_n"]
    return r["rd"], nlo, nhi, ri["rd"] if ri and ri.get("rd") == ri.get("rd") else None


def season(rows, min_runs=MIN_RUNS, z_flag=Z_FLAG):
    """rows: dicts with who, name, rd, rd_inj. -> report dict (pure; tested offline)."""
    by = {}
    for r in rows:
        by.setdefault(r["who"], []).append(r)
    qual = {w: v for w, v in by.items() if len(v) >= min_runs}
    means = {w: statistics.mean(x["rd"] for x in v) for w, v in qual.items()}
    players = []
    for w, v in sorted(qual.items(), key=lambda kv: -len(kv[1])):
        others = [m for o, m in means.items() if o != w]
        if len(others) < 2 or statistics.pstdev(others) == 0:
            continue
        mu, sd = statistics.mean(others), statistics.pstdev(others)
        inj = [x["rd_inj"] if x["rd_inj"] is not None else x["rd"] for x in v]
        names = {}
        for x in v:
            names[x["name"]] = names.get(x["name"], 0) + 1
        players.append(dict(who=w, name=max(names, key=names.get) if names else "", runs=len(v),
                            mean=round(means[w], 4), z=round((means[w] - mu) / sd, 2),
                            z_if_always_on=round((statistics.mean(inj) - mu) / sd, 2)))
    honest = [abs(p["z"]) for p in players]
    for p in players:
        p["flag"] = p["z"] >= z_flag
    return dict(version=VERSION, min_runs=min_runs, z_flag=z_flag, min_support=MIN_SUPPORT,
                measured_runs=len(rows), measured_players=len(by), qualifying_players=len(players),
                honest_max_abs_z=round(max(honest), 2) if honest else None,
                always_on_min_z=round(min(p["z_if_always_on"] for p in players), 2) if players else None,
                flagged=[p for p in players if p["flag"]], players=players)


def write_atomic(path, data):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".seasonflag-", suffix=".part", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True, indent=1)
            fh.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp:
            os.unlink(tmp)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--runs", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-new", type=int, default=20000, help="bound on recordings measured in one pass")
    a = ap.parse_args(argv)
    conn = sqlite3.connect("file:%s?mode=ro" % a.db, uri=True, timeout=10)
    try:
        pub = {rid: hashlib.sha256((p or "").encode()).hexdigest()[:8]
               for rid, p in conn.execute("SELECT runid, pub FROM receipts")}
    finally:
        conn.close()
    try:
        cache = json.load(open(a.cache, encoding="utf-8"))
        if cache.get("version") != VERSION:
            cache = {}
    except (OSError, ValueError):
        cache = {}
    files = cache.setdefault("files", {})
    cache["version"] = VERSION
    seen, new = set(), 0
    for p in sorted(glob.glob(os.path.join(a.runs, "*", "*", "*.rec"))):
        try:
            st = os.stat(p)
        except OSError:
            continue
        seen.add(p)
        key = [st.st_size, st.st_mtime_ns]
        hit = files.get(p)
        if hit is not None and hit.get("key") == key:
            continue
        if new >= a.max_new:
            continue
        new += 1
        rid, owner = run_identity(p)
        try:
            m = measure(p)
        except Exception as exc:        # one unreadable recording never stops the pass
            m = None
            print("seasonflag: %s: %r" % (p, exc), file=sys.stderr)
        files[p] = dict(key=key, rid=rid, owner=owner or "", m=m)
    for p in [p for p in files if p not in seen]:
        del files[p]
    write_atomic(a.cache, cache)
    rows = []
    for p, f in files.items():
        m = f.get("m")
        if not m or m[1] < MIN_SUPPORT or m[2] < MIN_SUPPORT:
            continue
        who = pub.get(f.get("rid")) or ("name:" + hashlib.sha256((f.get("owner") or "?").encode()).hexdigest()[:8])
        rows.append(dict(who=who, name=f.get("owner") or "", rd=m[0], rd_inj=m[3]))
    report = season(rows)
    report.update(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), measured_new=new)
    write_atomic(a.out, report)
    print("seasonflag: %d runs, %d qualifying players, %d flagged, honest max |z| %s, always-on min z %s, %d new"
          % (report["measured_runs"], report["qualifying_players"], len(report["flagged"]),
             report["honest_max_abs_z"], report["always_on_min_z"], new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
