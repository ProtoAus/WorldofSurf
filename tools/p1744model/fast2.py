# Two-player model, immutable states. Rec = (h,p,a,b); src = (p,a,b); ctx None or (p,a,b).
import sys
W = (0, 0, False)
R0 = (False, 0, 0, False)
def bankrec(rec, src, on, wasoff, ctx):
    h, p, a, b = rec
    if not on:
        same = ctx is not None and (p, a, b) == ctx
        if not wasoff:
            h = bool(ctx is not None and ctx[1] != 0 and src[1] == 0 and not src[2])
            p, a, b = ctx if ctx is not None else W
        elif not same:
            h = False
    if on and wasoff:
        if h and ctx is not None and (p, a, b) == ctx: src = W
        elif ctx is not None: src = ctx
        else: src = W
        h = False
    return (h, p, a, b), src
# old state: (S, R, src)
def old_step(st, kind, ctx):
    S, R, src = st
    if kind == 'toggle': kind = 'enable' if S else 'disable'
    on = kind == 'enable'
    R, src = bankrec(R, src, on, S, ctx)
    return (not on, R, src)
# new state: (S, R, src, pp(frozenset), slots(tuple per player: (present, rec)))
def new_step(st, players, kind, own, act, ctx):
    S, R, src, pp, slots = st
    slots = dict(slots)
    abit = act if act > 0 else 0
    bit = abit if own else 0
    on = not S
    effoff = (abit in pp) if abit else (len(pp) != 0)
    if kind == 'toggle': kind = 'disable' if (on and not effoff) else 'enable'
    def ppbank(pl, on_, wasoff, R, src):
        present, rec = slots[pl]
        s = present or (not on_)
        if s:
            rec, src = bankrec(rec, src, on_, wasoff, ctx)
            slots[pl] = (not on_, rec) if on_ else (True, rec)
        else:
            R, src = bankrec(R, src, on_, wasoff, ctx)
        return R, src
    if kind == 'disable':
        if bit and on:
            R, src = ppbank(act, False, effoff, R, src)
            pp = pp | {bit}
            return (S, R, src, frozenset(pp), tuple(sorted(slots.items())))
        wasoff = S or effoff
        if ctx is not None and ctx[0] in pp: FLAG[0] = True     # F1: global Disable while the cause's bit is set
        R, src = bankrec(R, src, False, wasoff, ctx)
        return (True, R, src, pp, tuple(sorted(slots.items())))
    if on and effoff:
        if abit: R, src = ppbank(act, True, True, R, src)
        else:
            if ctx is not None and ctx[0] in pp: FLAG[0] = True # F2: no-player activator under that player's cause
            R, src = bankrec(R, src, True, True, ctx)
    pp = (pp - {bit}) if bit else frozenset()
    R, src = bankrec(R, src, True, S, ctx)
    return (False, R, src, frozenset(pp), tuple(sorted(slots.items())))
FILTER = None
FLAG = [False]
import os
SKIPF = os.environ.get('SKIPF') == '1'
NOSTALE = os.environ.get('NOSTALE') == '1'
KEEPOG = os.environ.get('KEEPOG', '1') == '1'
KINDS = tuple(os.environ.get('KINDS', 'enable,disable,toggle').split(','))
def addhit(hits, k, h):
    if FILTER and FILTER(h[0]): return
    lst = hits.setdefault(k, [0, []])
    lst[0] += 1
    if len(lst[1]) < 40: lst[1].append(h)
def verdict(src, att):
    p, a, bad = src
    if a == 0: return 0
    cur = a > 0 and p != 0 and att.get(p) == a
    if not bad and cur: return 0
    return 2 if (not cur or bad) else 1
def run(players, mode, kinds=('enable', 'disable', 'toggle'), MAXATT=2):
    def ctxs(act, att):
        if act == 0:
            out = [None, W]
            if mode == 'loose': out += [(p, att[p], False) for p in players]
            return out
        out = [(act, att[act], False)]
        if att[act] > 1 and not NOSTALE: out.append((act, att[act] - 1, False))
        return out
    start = []
    for sd in (False, True):
        n = (sd, R0, W, frozenset(), tuple((p, (False, R0)) for p in players))
        og = (sd, R0, W)
        proj = tuple((sd, R0, W) for p in players)
        att = tuple((p, 1) for p in players)
        start.append(((n, og, proj, att), (('init', sd),), False))
    seen = set(s for s, _, _ in start); frontier = start; hits = {}
    depth = 0
    MAXD = int(os.environ.get('MAXD', '999'))
    while frontier and depth < MAXD:
        depth += 1
        nxt = []
        for (n, og, proj, att), seq, taint in frontier:
            attd = dict(att)
            evs = [('restart', p) for p in players if attd[p] < MAXATT]
            for k in kinds:
                for own in (True, False):
                    for act in [0] + players:
                        for c in ctxs(act, attd):
                            evs.append((k, own, act, c))
            for e in evs:
                a2 = dict(attd)
                if e[0] == 'restart':
                    a2[e[1]] += 1; n2, og2, proj2 = n, og, proj
                else:
                    k, own, act, c = e
                    FLAG[0] = False
                    n2 = new_step(n, players, k, own, act, c)
                    og2 = old_step(og, k, c) if og is not None else None
                    proj2 = tuple(proj[i] if (own and act != 0 and act != X) else old_step(proj[i], k, c)
                                  for i, X in enumerate(players))
                s2 = seq + (e,)
                t2 = taint or (e[0] != 'restart' and FLAG[0])
                for i, X in enumerate(players):
                    if SKIPF and t2: break
                    newon = not (n2[0] or X in n2[3])
                    pjon = not proj2[i][0]
                    ogon = (not og2[0]) if og2 is not None else False
                    vn = verdict(n2[2], a2)
                    if newon and pjon and vn > verdict(proj2[i][2], a2):
                        addhit(hits, ('bank worse than own-world projection', X), (s2, n2[2], proj2[i][2], (og2[2] if og2 is not None else None)))
                    if og2 is not None and newon and pjon and vn > verdict(proj2[i][2], a2) and (not ogon or vn > verdict(og2[2], a2)):
                        addhit(hits, ('bank worse than BOTH projection and global old (or old gate off)', X), (s2, n2[2], proj2[i][2], og2[2]))
                    if og2 is not None and newon and ogon and vn > verdict(og2[2], a2):
                        addhit(hits, ('bank worse than global old', X), (s2, n2[2], proj2[i][2], (og2[2] if og2 is not None else None)))
                    if newon and not pjon:
                        addhit(hits, ('gate on in new, off in own-world projection', X), (s2, n2[2], proj2[i][2], (og2[2] if og2 is not None else None)))
                st = (n2, (og2 if KEEPOG else None), proj2, tuple(sorted(a2.items())))
                if st in seen: continue
                seen.add(st); nxt.append((st, s2, t2))
        frontier = nxt
    return hits, len(seen)
if __name__ == '__main__':
    players = [int(x) for x in sys.argv[2].split(',')]
    hits, ns = run(players, sys.argv[1], kinds=KINDS)
    print('states', ns)
    lim = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    for k in sorted(hits):
        cnt, v = hits[k]
        v = sorted(v, key=lambda x: len(x[0]))
        print(k, cnt)
        for s, nsrc, psrc, osrc in v[:lim]:
            print('   new', nsrc, 'proj', psrc, 'globalold', osrc if osrc is not None else '-')
            for e in s: print('      ', e)
