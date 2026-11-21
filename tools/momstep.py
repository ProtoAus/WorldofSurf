"""Hold a Momentum Mod demo against this game's mover, ONE tick at a time.

  python tools/momstep.py make  <file.mtv> <out.txt> [--ticks a:b]
  python tools/momstep.py grade <file.mtv> <pm_stepsim output> [--csv rows.csv] [--worst N]

`make` writes the engine's `pm_stepsim` input: for every tick pair (t-1, t) of the demo, the
state Momentum recorded at t-1 (origin, velocity, ground, duck, surface friction, old buttons)
and the command of tick t (buttons, angles).  Run it on the demo's map with the movement
settings under test:

  map <map> / sv_cheats 1 / <settings> / pm_stepsim momstep/in.txt momstep/out.txt

`grade` reads the engine's answer and compares each predicted state with the one Momentum
recorded at t.  Nothing carries from one tick to the next, so a difference is THAT tick's
physics: no drift, no chaos, no route.

What a .mtv cannot give and how it is filled (tools/momreplay.py decodes the rest):
  * forward/side move: from the movement keys (m_nPhysicalButtons), 400 a key, which Momentum
    scales to maxspeed as this mover does; the recorded wishVel checks the direction.
  * ducking mid-transition and the duck timer: not recorded.  `ducked` is FL_DUCKING; a view
    height between the stand and duck eyes marks the tick `transit` and grading lists it apart.
  * surface friction: Source's m_surfaceFriction is 0.25 after a tick that ended airborne and
    rising (CategorizePosition before FinishGravity), else 1 -- derived from t-1.
  * pairs the demo itself does not integrate (a tick with no move or two, a teleport): origin
    step against velocity, flagged `skip` and left out of the totals.

Classes: air (no ground either side), jump (left the ground), land (reached it), ground, and
`contact` when the mover clipped a plane (pm_stepsim's contact kind).  Measures only.
"""
import argparse
import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import momreplay  # noqa: E402

IN_JUMP, IN_DUCK, IN_FORWARD, IN_BACK = 2, 4, 8, 16
IN_MOVELEFT, IN_MOVERIGHT, IN_SPEED, IN_WALK = 512, 1024, 1 << 17, 1 << 18
FL_ONGROUND, FL_DUCKING = 1, 2
KEYSPEED = 400

# Momentum's game modes (GameMode_t) this tool knows the gravity and tick of
MODES = {1: ("surf", 800.0), 2: ("bhop", 800.0), 9: ("ahop", 600.0)}


def ticks_of(path):
    rep = momreplay.parse(path)
    return rep, rep["ticks"]


def _ducked(t):
    return bool(int(t.flags) & FL_DUCKING)


def _transit(t, stand, duck):
    vz = t.view_z
    return vz is not None and abs(vz - stand) > 0.05 and abs(vz - duck) > 0.05


def exact_yaw(t, fwd, side):
    """The view yaw the move used, from the float wishVel: the demo's own yaw is 11 bits
    (0.18 deg), worth ~6 u/s of air-accel projection at 2000 u/s.  None when no key is held."""
    if t.wish_x is None or (fwd == 0 and side == 0) or math.hypot(t.wish_x, t.wish_y) < 1e-3:
        return None
    y = math.degrees(math.atan2(t.wish_y, t.wish_x) - math.atan2(-side, fwd))
    y += 360.0 * round((t.yaw - y) / 360.0)
    return y if abs(y - t.yaw) < 0.5 else None


def command(t, prev=None):
    b = int(t.buttons or 0)
    # a scroll-wheel jump presses and releases inside one frame: the usercmd had IN_JUMP, the
    # physical buttons never show it.  The jump tick moving is the evidence (m_iJumpTick).
    if prev is not None and t.jump_tick is not None and t.jump_tick != prev.jump_tick:
        b |= IN_JUMP
    # toggled duck (m_nButtonsToggled) never reaches the physical buttons either: a tick that
    # ends ducked had the duck down (an unduck blocked by a ceiling is the exception)
    if _ducked(t):
        b |= IN_DUCK
    fwd = KEYSPEED * ((b & IN_FORWARD) != 0) - KEYSPEED * ((b & IN_BACK) != 0)
    side = KEYSPEED * ((b & IN_MOVERIGHT) != 0) - KEYSPEED * ((b & IN_MOVELEFT) != 0)
    if not wish_agrees(t, fwd, side):
        # keys the physical state does not show (an alias, a toggle): the recorded wishVel says
        # which way the command pushed.  Keys give multiples of 45 degrees of the view.
        wl = math.hypot(t.wish_x, t.wish_y)
        if wl < 1e-3:
            fwd = side = 0
        else:
            yaw = math.radians(t.yaw)
            wf = (t.wish_x * math.cos(yaw) + t.wish_y * math.sin(yaw)) / wl
            ws = (t.wish_x * math.sin(yaw) - t.wish_y * math.cos(yaw)) / wl
            phi = round(math.atan2(-ws, wf) / (math.pi / 4)) * (math.pi / 4)
            fwd = KEYSPEED * round(math.cos(phi))
            side = -KEYSPEED * round(math.sin(phi))
    ours = (1 if b & IN_JUMP else 0) | (2 if b & IN_DUCK else 0) | (4 if b & IN_SPEED else 0)
    return fwd, side, ours


def wish_agrees(t, fwd, side):
    """True when the recorded wishVel points where the keys say (or both are zero)."""
    if t.wish_x is None:
        return True
    wl = math.hypot(t.wish_x, t.wish_y)
    if fwd == 0 and side == 0:
        return wl < 1e-3
    yaw = math.radians(t.yaw)
    f = (math.cos(yaw), math.sin(yaw))
    r = (math.sin(yaw), -math.cos(yaw))
    wx, wy = f[0] * fwd + r[0] * side, f[1] * fwd + r[1] * side
    if wl < 1e-3:
        return False
    # 11-bit recorded yaw: ~0.18 deg, so 0.995 is generous and still catches a wrong key
    return (wx * t.wish_x + wy * t.wish_y) / (math.hypot(wx, wy) * wl) > 0.995


def integrates(a, b, dt, tol):
    """The demo moved from a to b with b's velocity (Source moves with the end velocity's
    horizontal part; vertical uses the mid-step value, so z is checked loosely)."""
    dx, dy = b.x - a.x, b.y - a.y
    return math.hypot(dx - b.vx * dt, dy - b.vy * dt) <= tol


def make(args):
    rep, T = ticks_of(args.mtv)
    hdr = rep["header"]
    mode = MODES.get(hdr["game_mode"])
    grav = mode[1] if mode else 800.0
    dt = rep["tick_interval"]
    a0, a1 = 1, len(T)
    if args.ticks:
        lo, hi = args.ticks.split(":")
        a0, a1 = max(1, int(lo or 1)), min(len(T), int(hi or len(T)))
    with open(args.out, "w") as f:
        f.write("# momstep %s map %s mode %s tick %.6f ticks %d..%d\n"
                % (os.path.basename(args.mtv), hdr["map"], hdr["game_mode"], dt, a0, a1 - 1))
        for i in range(a0, a1):
            a, b = T[i - 1], T[i]
            onground = int(a.flags) & FL_ONGROUND
            ducked = _ducked(a)
            sf = 0.25 if (not onground and a.vz + 0.5 * grav * dt > 0) else 1.0
            ob = int(a.buttons or 0)
            old = (1 if ob & IN_JUMP else 0) | (2 if ob & IN_DUCK else 0)
            fwd, side, ours = command(b, a)
            yaw = exact_yaw(b, fwd, side)
            f.write("%d %.4f %.4f %.4f %.4f %.4f %.4f %d %d 0 0 %.2f %d %d %d 0 %d %.5f %.5f\n"
                    % (b.tick, a.x, a.y, a.z, a.vx, a.vy, a.vz, 1 if onground else 0,
                       1 if ducked else 0, sf, old, fwd, side, ours, b.pitch,
                       b.yaw if yaw is None else yaw))
    print("wrote %d ticks to %s" % (a1 - a0, args.out))


def read_out(path):
    head, rows = None, {}
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                head = head or line.strip()
                continue
            p = line.split()
            if len(p) < 17:
                continue
            rows[int(p[0])] = {
                "o": tuple(map(float, p[1:4])), "v": tuple(map(float, p[4:7])),
                "ground": int(p[7]), "ducked": int(p[8]), "ticks": int(p[9]),
                "contact": int(p[10]), "cn": tuple(map(float, p[11:14])),
                "gn": tuple(map(float, p[14:17]))}
    return head, rows


def grade(args):
    rep, T = ticks_of(args.mtv)
    hdr = rep["header"]
    dt = rep["tick_interval"]
    head, out = read_out(args.out)
    print(head or "# (no pm_stepsim header)")
    def mode_of(vals, dflt):
        c = {}
        for v in vals:
            c[round(v, 2)] = c.get(round(v, 2), 0) + 1
        return max(c, key=c.get) if c else dflt
    stand = mode_of([t.view_z for t in T if t.view_z is not None and not _ducked(t)], 64.0)
    duck = mode_of([t.view_z for t in T if t.view_z is not None and _ducked(t)], stand)
    lo_run, hi_run = None, None
    for t in T:
        if t.timer_state == 2:
            lo_run = t.tick if lo_run is None else lo_run
            hi_run = t.tick
    by = {t.tick: t for t in T}
    rows = []
    for tick, r in sorted(out.items()):
        b, a = by.get(tick), by.get(tick - 1)
        if a is None or b is None:
            continue
        ga, gb = int(a.flags) & FL_ONGROUND, int(b.flags) & FL_ONGROUND
        fwd, side, ours = command(b, a)
        kind = ("jump" if ga and not gb else "land" if gb and not ga else
                "ground" if ga and gb else "air")
        skip = []
        if not integrates(a, b, dt, args.tol):
            skip.append("integ")
        if not wish_agrees(b, fwd, side):
            skip.append("wish")
        if _transit(a, stand, duck) or _transit(b, stand, duck) or _ducked(a) != _ducked(b):
            skip.append("transit")
        if b.noint is not None and a.noint is not None and b.noint != a.noint:
            skip.append("teleport")
        dv = [r["v"][k] - (b.vx, b.vy, b.vz)[k] for k in range(3)]
        do = [r["o"][k] - (b.x, b.y, b.z)[k] for k in range(3)]
        sp_m = math.hypot(b.vx, b.vy)
        sp_o = math.hypot(r["v"][0], r["v"][1])
        sp_a = math.hypot(a.vx, a.vy)
        rows.append({
            "tick": tick, "kind": kind, "contact": r["contact"],
            "skip": ",".join(skip), "inrun": lo_run is not None and lo_run <= tick <= hi_run,
            "dv": math.sqrt(sum(x * x for x in dv)), "dvxy": math.hypot(dv[0], dv[1]), "dvz": dv[2],
            "do": math.sqrt(sum(x * x for x in do)),
            "sp_before": sp_a, "sp_mom": sp_m, "sp_ours": sp_o,
            "ground_mom": gb, "ground_ours": r["ground"],
            "cnz": r["cn"][2], "gnz": r["gn"][2], "z": b.z,
            "mom_v": (b.vx, b.vy, b.vz), "our_v": r["v"]})
    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            keys = [k for k in rows[0] if k not in ("mom_v", "our_v")] if rows else []
            w.writerow(keys + ["mvx", "mvy", "mvz", "ovx", "ovy", "ovz"])
            for x in rows:
                w.writerow([x[k] for k in keys] + list(x["mom_v"]) + list(x["our_v"]))

    def summary(name, sel):
        sel = [x for x in sel]
        if not sel:
            print("  %-22s none" % name)
            return
        dvs = sorted(x["dv"] for x in sel)
        exact = sum(1 for d in dvs if d <= args.exact)
        med = dvs[len(dvs) // 2]
        p95 = dvs[min(len(dvs) - 1, int(len(dvs) * 0.95))]
        gain = sum(x["sp_ours"] - x["sp_mom"] for x in sel) / len(sel)
        dos = sorted(x["do"] for x in sel)
        print("  %-22s %6d  exact(<=%.2f) %5.1f%%  |dv| median %8.3f p95 %8.3f max %8.2f  "
              "|do| p95 %6.3f  mean(our-mom 2D speed) %+8.3f"
              % (name, len(sel), args.exact, 100.0 * exact / len(sel), med, p95, dvs[-1],
                 dos[min(len(dos) - 1, int(len(dos) * 0.95))], gain))

    good = [x for x in rows if not x["skip"] and x["inrun"]]
    print("demo %s  map %s  mode %s  player %s  tick %.4f  pairs %d  graded %d  "
          "(skipped: integ %d wish %d transit %d teleport %d, outside the run %d)"
          % (os.path.basename(args.mtv), hdr["map"], hdr["game_mode"], hdr["player"], dt, len(rows),
             len(good), sum("integ" in x["skip"] for x in rows), sum("wish" in x["skip"] for x in rows),
             sum("transit" in x["skip"] for x in rows), sum("teleport" in x["skip"] for x in rows),
             sum(1 for x in rows if not x["inrun"])))
    for kind in ("air", "jump", "land", "ground"):
        summary(kind + " (no contact)", [x for x in good if x["kind"] == kind and not x["contact"]])
        summary(kind + " (contact)", [x for x in good if x["kind"] == kind and x["contact"]])
    land = [x for x in good if x["kind"] == "land"]
    if land:
        print("  landings by slope (Momentum's 2D speed vs ours, after - before):")
        for lo, hi, nm in ((0.999, 1.01, "flat"), (0.7, 0.999, "slope")):
            sel = [x for x in land if lo <= max(x["gnz"], x["cnz"]) < hi]
            if not sel:
                continue
            up = [x for x in sel if x["sp_mom"] - x["sp_before"] <= 1.0]
            dn = [x for x in sel if x["sp_mom"] - x["sp_before"] > 1.0]
            for lab, s in (("kept/lost", up), ("gained", dn)):
                if s:
                    print("    %-6s %-9s %4d  mom %+8.2f  ours %+8.2f  (mean 2D speed change)"
                          % (nm, lab, len(s), sum(x["sp_mom"] - x["sp_before"] for x in s) / len(s),
                             sum(x["sp_ours"] - x["sp_before"] for x in s) / len(s)))
    mism = [x for x in good if x["ground_mom"] != x["ground_ours"]]
    print("  ground flag disagrees on %d graded ticks" % len(mism))
    if args.worst:
        print("  worst graded ticks:")
        for x in sorted(good, key=lambda x: -x["dv"])[:args.worst]:
            print("    %6d %-6s c%d  |dv| %8.2f dvz %+8.2f  2D before %8.2f mom %8.2f ours %8.2f  "
                  "gnd m%d o%d  cnz %.3f gnz %.3f"
                  % (x["tick"], x["kind"], x["contact"], x["dv"], x["dvz"], x["sp_before"],
                     x["sp_mom"], x["sp_ours"], x["ground_mom"], x["ground_ours"], x["cnz"], x["gnz"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("mtv")
    m.add_argument("out")
    m.add_argument("--ticks")
    g = sub.add_parser("grade")
    g.add_argument("mtv")
    g.add_argument("out")
    g.add_argument("--csv")
    g.add_argument("--worst", type=int, default=0)
    g.add_argument("--tol", type=float, default=0.05, help="integration check, units")
    g.add_argument("--exact", type=float, default=0.05, help="|dv| counted as a match, u/s")
    a = ap.parse_args()
    return make(a) if a.cmd == "make" else grade(a)


if __name__ == "__main__":
    sys.exit(main())
