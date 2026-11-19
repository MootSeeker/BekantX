"""Remove the middle part of long B.Cu track chains, keep the pad escapes (layout rule 2026-11-19: GND pour on B.Cu
less fragmented). The open connections are then routed again by touchup_router.py with --bcost > 1, which keeps
the long runs on F.Cu.

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/release_mid.py <in.kicad_pcb> <out.kicad_pcb> NET,NET,... [--keep=1.5] [--min=10]

A chain is a run of B.Cu segments of one net between two terminals (pad, via, junction of three or more
segments). Of every chain longer than --min mm, the first and last --keep mm stay (the escape from the pad or via
stays as it was: straight pad entry, fan-out of the QFNs); the rest is removed. Locked segments are left alone.
"""
import collections, math, sys

import pcbnew

from bekantx_layout import P, unP


def key(p):
    return (round(p[0], 4), round(p[1], 4))


def main(src, dst, nets, keep=1.5, min_len=10.0):
    board = pcbnew.LoadBoard(str(src))
    B = pcbnew.B_Cu
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    pads = [(fp, p) for fp in board.GetFootprints() for p in fp.Pads()]
    dead, added, report = [], [], []
    for net in nets:
        segs = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net and t.GetLayer() == B]
        deg = collections.Counter()
        adj = collections.defaultdict(list)
        for t in segs:
            for q in (unP(t.GetStart()), unP(t.GetEnd())):
                deg[key(q)] += 1
                adj[key(q)].append(t)

        def term(q):
            if deg[key(q)] != 2:
                return True
            if any(v.GetNetname() == net and math.dist(unP(v.GetPosition()), q) <= pcbnew.ToMM(v.GetWidth(B)) / 2 + 1e-3 for v in vias):
                return True
            return any(p.GetNetname() == net and p.IsOnLayer(B) and p.HitTest(P(*q)) for _fp, p in pads)

        seen = set()
        for t0 in segs:
            if id(t0) in seen:
                continue
            # ordered chain: walk to one terminal, then collect towards the other
            q, cur = unP(t0.GetStart()), t0
            guard = 0
            while not term(q) and guard < 500:
                nxt = [o for o in adj[key(q)] if o is not cur]
                cur = nxt[0]
                a, b = unP(cur.GetStart()), unP(cur.GetEnd())
                q = b if key(a) == key(q) else a
                guard += 1
            chain, pts = [], [q]
            while True:
                a, b = unP(cur.GetStart()), unP(cur.GetEnd())
                far = b if key(a) == key(pts[-1]) else a
                chain.append(cur)
                pts.append(far)
                seen.add(id(cur))
                if term(far):
                    break
                nxt = [o for o in adj[key(far)] if o is not cur]
                cur = nxt[0]
            L = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
            if L < min_len or any(t.IsLocked() for t in chain):
                continue
            # keep [0, keep] and [L - keep, L] along the chain
            pos, cuts = 0.0, []
            for t, a, b in zip(chain, pts, pts[1:]):
                l = math.dist(a, b)
                lo, hi = pos, pos + l
                keep_a = max(0.0, min(hi, keep) - lo)            # length kept from a
                keep_b = max(0.0, hi - max(lo, L - keep))        # length kept towards b
                if keep_a <= 1e-6 and keep_b <= 1e-6:
                    dead.append(t)
                elif keep_a + keep_b < l - 1e-6:
                    u = ((b[0] - a[0]) / l, (b[1] - a[1]) / l)
                    if keep_a > 1e-6 and keep_b > 1e-6:          # one segment holds both ends: split it
                        qa = (a[0] + u[0] * keep_a, a[1] + u[1] * keep_a)
                        qb = (b[0] - u[0] * keep_b, b[1] - u[1] * keep_b)
                        added.append((qb, b, t))
                        cuts.append((t, a, qa))
                    elif keep_a > 1e-6:
                        cuts.append((t, a, (a[0] + u[0] * keep_a, a[1] + u[1] * keep_a)))
                    else:
                        cuts.append((t, (b[0] - u[0] * keep_b, b[1] - u[1] * keep_b), b))
                pos = hi
            for t, a, b in cuts:
                s, e = unP(t.GetStart()), unP(t.GetEnd())
                if math.dist(s, a) < 1e-4 or math.dist(e, b) < 1e-4:
                    t.SetStart(P(*a)); t.SetEnd(P(*b))
                else:
                    t.SetStart(P(*b)); t.SetEnd(P(*a))
            report.append(f"{net}: {L:.1f} mm chain, {L - 2 * keep:.1f} mm released")
    for a, b, t in added:
        n = pcbnew.PCB_TRACK(board)
        n.SetStart(P(*a)); n.SetEnd(P(*b)); n.SetWidth(t.GetWidth()); n.SetLayer(B); n.SetNet(t.GetNet())
        board.Add(n)
    for t in dead:                             # removals last: pcbnew proxies break after Remove()
        board.Remove(t)
    pcbnew.SaveBoard(str(dst), board)
    print("\n".join(report) or "nothing released")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    opt = lambda k, d: next((float(x.split("=")[1]) for x in sys.argv if x.startswith(f"--{k}=")), d)
    main(a[0], a[1], a[2].split(","), opt("keep", 1.5), opt("min", 10.0))
