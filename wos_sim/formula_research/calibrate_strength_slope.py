"""Phase A follow-up (2026-07-28): does the joiner-aware STRENGTH MARGIN predict the
REAL winner? If so, the displayed probability can be the strength sigmoid with a
slope CALIBRATED on real outcomes (replacing winprob.K_SLOPE=10, a judgment
constant, and DAMP=0.10, which pinned near-even battles at 0.55).

Model:  P(own wins) = logistic(k * m_own),   m_own = ln(effective_ratio_own)
One parameter, through the origin (parity => 50% by construction). Fitted by
maximum likelihood on the 22 labelled battles; leave-one-out Brier reported
against the constant-hit-rate model and the old 0.55 heuristic.
"""
from __future__ import annotations

import json
import math
import os

from wos_sim.formula_research.calibrate_winprob import ARMY, _prof, brier
from wos_sim.predictor import api, construct, serialize, winprob
from wos_sim.predictor.profiles import Matchup

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "predictor", "winprob_calibration.json")


def signed_points(n_runs=40, seed=4471):
    from wos_sim.normalize_reports import golden_anchors
    pts = []
    for aid, scen, exp in golden_anchors():
        own = serialize.profile_from_dict(scen["own"])
        enemy = serialize.profile_from_dict(scen["enemy"])
        con = construct.build(Matchup(own, enemy), apply_legacy_skills=False)
        r = winprob.effective_ratio(con)
        m = math.log(r if con.own_is_attacker else 1.0 / r)
        fc = api.predict(own, enemy, n=n_runs, seed=seed, params={"engine": "turn"})
        pts.append({"id": aid, "set": "golden", "m_own": m,
                    "real_own": exp["real_winner"] == "own",
                    "call_own": fc.p_win.p >= 0.5, "old_p": fc.p_win.p})
    for aid, ac, ap, dc, dp, tier, n, f in ARMY:
        own, enemy = _prof("rally", ac, n, ap, tier), _prof("garrison", dc, n, dp, tier)
        con = construct.build(Matchup(own, enemy), apply_legacy_skills=False)
        m = math.log(winprob.effective_ratio(con))
        fc = api.predict(own, enemy, n=n_runs, seed=seed, params={"engine": "turn"})
        pts.append({"id": aid, "set": "army", "m_own": m, "real_own": True,
                    "call_own": fc.p_win.p >= 0.5, "old_p": fc.p_win.p})
    return pts


def fit_k(ms, ys, iters=4000, lr=2.0):
    k = 1.0
    for _ in range(iters):
        g = sum((y - 1 / (1 + math.exp(-k * m))) * m for m, y in zip(ms, ys)) / len(ms)
        k = max(0.0, k + lr * g)
    return k


def sig(k, m):
    return 1.0 / (1.0 + math.exp(-k * m))


def main():
    pts = signed_points()
    ms = [p["m_own"] for p in pts]
    ys = [1.0 if p["real_own"] else 0.0 for p in pts]
    k_all = fit_k(ms, ys)
    g = [p for p in pts if p["set"] == "golden"]
    k_gold = fit_k([p["m_own"] for p in g], [1.0 if p["real_own"] else 0.0 for p in g])
    print("=" * 74)
    print("STRENGTH MARGIN -> REAL WINNER   P(own) = logistic(k * m_own)")
    for p in pts:
        print(f"  {p['id']:36s} [{p['set']:6s}] m_own={p['m_own']:+.3f} real_own={'Y' if p['real_own'] else 'n'} "
              f"call_own={'Y' if p['call_own'] else 'n'}  sig(k_all)={sig(k_all, p['m_own']):.3f}")
    sign_right = sum(1 for p in pts if (p["m_own"] >= 0) == p["real_own"])
    print(f"\n  strength SIGN predicts the real winner: {sign_right}/{len(pts)}")
    print(f"  k (all 22) = {k_all:.3f}   k (13 golden only) = {k_gold:.3f}   (winprob.K_SLOPE today = 10)")
    # leave-one-out Brier for the folded display rule: magnitude from the sigmoid,
    # side from the hybrid call (so the G12 winner is untouched)
    loo = []
    for i in range(len(pts)):
        ki = fit_k(ms[:i] + ms[i + 1:], ys[:i] + ys[i + 1:])
        s = sig(ki, ms[i])
        mag = max(s, 1 - s)
        loo.append(mag if pts[i]["call_own"] else 1 - mag)
    real = ys
    old = [p["old_p"] for p in pts]
    const = [0.7272 if p["call_own"] else 1 - 0.7272 for p in pts]
    print(f"  Brier: old 0.55 heuristic {brier(old, real):.4f} | constant hit-rate {brier(const, real):.4f} | "
          f"strength sigmoid, folded to the call (LOO) {brier(loo, real):.4f}")
    with open(OUT, encoding="utf-8") as f:
        cal = json.load(f)
    cal["strength_slope"] = {
        "k_all": round(k_all, 5), "k_golden_only": round(k_gold, 5), "n": len(pts),
        "sign_accuracy": f"{sign_right}/{len(pts)}",
        "brier_folded_loo": round(brier(loo, real), 5),
        "brier_constant_hit_rate": round(brier(const, real), 5),
        "brier_old_heuristic": round(brier(old, real), 5),
        "display_rule": "p = sigmoid(k*m_own); magnitude kept, side folded onto the hybrid winner call",
        "points": [{k: (round(v, 5) if isinstance(v, float) else v) for k, v in p.items()} for p in pts],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cal, f, indent=1)
    print(f"\nwrote strength_slope into {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
