# As landed (9afa3611): run with MARK=head -- rule (3) keyed on the vbsp_bw_fb marker. Header below is from review 5.
# P1744 review 5 (82dab4c4): new5's copy design with HEAD's drop rule (off flag + src equal; off-cause too while off) and
# rule (3): an own row from a player with NO copy, while the pad is off and the pad's bank_off_player == act, goes to the
# shared world (before the departed-client drop).  Ghost field on the pad: fbby = the player whose own row, through
# fallback, made the pad's latest on->off (None otherwise), so a rule-3 hit is tagged R3ok (fbby == act) or R3MIS.
# Env: NOSTALE=1, FALLBACK=1 ('full'/'room' events), DEPART=1 ('leave' events), CROSS=1 (an own row may carry another
# player's ctx: a nested chain), RULE3=0 (review-4 behaviour: no rule 3), MAXATT (default 2).
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fast2 import bankrec, old_step, verdict, W, R0

NOSTALE = os.environ.get('NOSTALE') == '1'
FALLBACK = os.environ.get('FALLBACK') == '1'
DEPART = os.environ.get('DEPART') == '1'
CROSS = os.environ.get('CROSS') == '1'
RULE3 = os.environ.get('RULE3', '1') == '1'
R3GHOST = os.environ.get('R3GHOST') == '1'   # rule 3 keyed on a dedicated fallback marker instead of bank_off_player
MAXATT = int(os.environ.get('MAXATT', '2'))
MARK = os.environ.get('MARK', 'head')
FULLP = os.environ.get('FULLP')

ROUTE = [None]
def same(c, P):     # SV_BwStep's drop test at HEAD
    return c[0] == P[0] and c[2] == P[2] and (not c[0] or c[1] == P[1])

def shared(P, cp, kind, ctx, fbact):
    P2 = old_step(P, kind, ctx)
    for pl in list(cp):
        c = old_step(cp[pl], kind, ctx)
        if same(c, P2): del cp[pl]
        else: cp[pl] = c
    return P2

def new_step(st, kind, own, act, ctx):
    """st = (P, fbby, copies, full, gone).  Returns (st', tags)."""
    P, fbby, copies, full, gone = st
    cp = dict(copies)
    tags = set()
    if own and act != 0:
        if RULE3 and act not in cp and P[0] and ((fbby == act) if R3GHOST else (P[1][1] == act)):
            tags.add('R3ok' if fbby == act else 'R3MIS')
            if act in gone: tags.add('R3DEP')
            own = False
    if own and act != 0:
        if act in gone:
            ROUTE[0] = 'drop'
            return (P, fbby, tuple(sorted(cp.items())), full, gone), tags | {'DEPDROP'}
        if act in cp or act not in full:
            c = cp.get(act, P)
            c = old_step(c, kind, ctx)
            if same(c, P): cp.pop(act, None)
            else: cp[act] = c
            ROUTE[0] = 'own'
            return (P, fbby, tuple(sorted(cp.items())), full, gone), tags
        tags.add('FB')
        fb = act
    else:
        fb = None
    P2 = shared(P, cp, kind, ctx, fb)
    if MARK == 'head':                        # 9afa3611: ends on -> world; on->off -> own?act:world; off->off unchanged
        if not P2[0]: fbby = None
        elif not P[0]: fbby = fb
    elif MARK == 'clroff':                    # alternative: also cleared by any off->off
        if not P2[0]: fbby = None
        elif not P[0]: fbby = fb
        else: fbby = None
    else:                                     # new6 as written
        if not P[0] and P2[0]: fbby = fb
        elif not P2[0]: pass
        else: fbby = None
    return (P2, fbby, tuple(sorted(cp.items())), full, gone), tags

def world(st, X):
    return dict(st[2]).get(X, st[0])

def run(players, mode, kinds=('enable', 'disable', 'toggle')):
    def ctxs(act, att, own):
        if act == 0:
            out = [None, W]
            if mode == 'loose': out += [(p, att[p], False) for p in players]
            return out
        out = [(act, att[act], False)]
        if att[act] > 1 and not NOSTALE: out.append((act, att[act] - 1, False))
        if CROSS and own: out += [(p, att[p], False) for p in players if p != act]
        return out
    hits = {}
    def addhit(k, h):
        l = hits.setdefault(k, [0, []])
        l[0] += 1
        if len(l[1]) < 300: l[1].append(h)
    start = []
    for sd in (False, True):
        P = (sd, R0, W)
        n = (P, None, (), frozenset(), frozenset())
        start.append(((n, P, tuple(P for _ in players), tuple((p, 1) for p in players)), (('init', sd),), frozenset()))
    seen = set(s for s, _, _ in start)
    frontier = start
    viol = 0
    while frontier:
        nxt = []
        for (n, og, proj, att), seq, tg in frontier:
            attd = dict(att)
            evs = [('restart', p) for p in players if attd[p] < MAXATT and p not in n[4]]
            if FALLBACK:
                FP = [int(x) for x in FULLP.split(',')] if FULLP else players
                evs += [('full', p) for p in FP if p not in n[3]] + [('room', p) for p in FP if p in n[3]]
            if DEPART:
                evs += [('leave', p) for p in players if p not in n[4]]
            for k in kinds:
                for own in (True, False):
                    for act in [0] + players:
                        for c in ctxs(act, attd, own):
                            evs.append((k, own, act, c))
            for e in evs:
                a2 = dict(attd); t = set()
                if e[0] == 'restart':
                    a2[e[1]] += 1; n2, og2, proj2 = n, og, proj
                elif e[0] == 'full':
                    n2 = (n[0], n[1], n[2], n[3] | {e[1]}, n[4]); og2, proj2 = og, proj
                elif e[0] == 'room':
                    n2 = (n[0], n[1], n[2], n[3] - {e[1]}, n[4]); og2, proj2 = og, proj
                elif e[0] == 'leave':
                    cp = dict(n[2]); cp.pop(e[1], None)            # SV_BwForget
                    n2 = (n[0], n[1], tuple(sorted(cp.items())), n[3], n[4] | {e[1]}); og2, proj2 = og, proj
                else:
                    k, own, act, c = e
                    ROUTE[0] = 'shared'
                    n2, t = new_step(n, k, own, act, c)
                    for X in players:
                        if X in n2[4]: continue
                        wb = world(n, X); wa = world(n2, X)
                        if ROUTE[0] == 'shared' or (ROUTE[0] == 'own' and X == act): exp = old_step(wb, k, c)
                        else: exp = wb
                        if not same(exp, wa) or (exp[0] == False and exp[1][0]):
                            addhit((('MACHINERY',), 'world != routed step', X, ROUTE[0]), (seq + (e,), wa, exp, og))
                    og2 = old_step(og, k, c)
                    proj2 = tuple(proj[i] if (own and act != 0 and act != X) else old_step(proj[i], k, c)
                                  for i, X in enumerate(players))
                s2 = seq + (e,)
                tg2 = tg | frozenset(t)
                for rec in [n2[0]] + [c for _, c in n2[2]] + [og2] + list(proj2):
                    if not rec[0] and rec[1][0]: viol += 1
                tag = tuple(sorted(tg2)) or ('clean',)
                for i, X in enumerate(players):
                    if X in n2[4]: continue
                    w = world(n2, X); pj = proj2[i]
                    won, pon, ogon = not w[0], not pj[0], not og2[0]
                    if won != pon:
                        addhit((tag, 'gate differs from projection', 'new on' if won else 'new off',
                                'old on' if ogon else 'old off'), (s2, w, pj, og2))
                    if won and pon and w[2] != pj[2]:
                        vw, vp, vo = verdict(w[2], a2), verdict(w[2] if False else pj[2], a2), verdict(og2[2], a2)
                        rel = 'WORSE' if vw > vp else ('BETTER' if vw < vp else 'same-verdict')
                        rel2 = ('worse than old' if (ogon and vw > vo) else ('old gate off' if not ogon else 'not worse than old'))
                        addhit((tag, 'bank owner differs from projection (both on)', rel, rel2), (s2, w, pj, og2))
                    if len(players) == 1:
                        if w[0] != og2[0]:
                            addhit((tag, '1p: gate differs from old global'), (s2, w, pj, og2))
                        if won and w[2] != og2[2]:
                            addhit((tag, '1p: bank owner differs from old global'), (s2, w, pj, og2))
                st = (n2, (og2 if (len(players) == 1 or os.environ.get('KEEPOG') == '1') else None), proj2, tuple(sorted(a2.items())))
                key = (st, ('R3MIS' in tg2, bool(tg2 & {'FB', 'R3ok'})))
                if key in seen: continue
                if os.environ.get('PRUNE') == '1' and (tg2 - {'DEPDROP'}): continue   # explore clean paths only
                seen.add(key)
                nxt.append(((n2, og2, proj2, tuple(sorted(a2.items()))), s2, tg2))
        frontier = nxt
    return hits, len(seen), viol

if __name__ == '__main__':
    mode = sys.argv[1]
    players = [int(x) for x in sys.argv[2].split(',')]
    lim = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    hits, ns, viol = run(players, mode)
    print('mode', mode, 'players', players, 'NOSTALE', NOSTALE, 'FALLBACK', FALLBACK, 'DEPART', DEPART, 'CROSS', CROSS,
          'RULE3', RULE3, 'R3GHOST', R3GHOST, 'states', ns, 'have-set-while-on violations', viol)
    if not hits: print('NO HITS')
    for k in sorted(hits):
        cnt, v = hits[k]
        print(k, cnt)
        for s, w, pj, og in sorted(v, key=lambda x: len(x[0]))[:lim]:
            print('     new', w, ' proj', pj, ' old', og)
            for e in s: print('        ', e)
