"""Phase A (2026-07-28) -- calibrate the DISPLAYED win probability from real battles.

Two paths, two measured quantities, ZERO judgment constants in the shipped numbers:

  1. ARMY-LAW path: P(attacker wins) = Phi(-mu / sigma_army)
       mu    = ln(beta/alpha * R)           (attacker wins iff mu < 0)
       sigma = RMS of the LEAVE-ONE-OUT residuals of ln(beta/alpha) across the nine
               deterministic army anchors -- the MEASURED model error in log-ratio
               space. Cross-class anchors are predicted with the OTHER battle's R.

  2. TURN-ENGINE path: the engine's winner call is kept (G12 lock), and the displayed
     number becomes the CALIBRATED probability that the call is right, as a function
     of the joiner-aware strength margin |ln r| (winprob.effective_ratio):
       P(call correct | m) = logistic(a + b*m), fitted by maximum likelihood on every
       labelled real battle (13 golden anchors + 9 army anchors), leave-one-out
       Brier reported next to the old 0.55/0.45 heuristic's Brier.

Writes wos_sim/predictor/winprob_calibration.json. Re-run after any engine change:
    py -m wos_sim.formula_research.calibrate_winprob
"""
from __future__ import annotations

import json
import math
import os

from wos_sim.formula_research.stage4_common import base_stats
from wos_sim.formula_research.stage8_army import R_TABLE, eff
from wos_sim.predictor import api, construct, serialize, winprob
from wos_sim.predictor.profiles import Matchup

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "predictor", "winprob_calibration.json")


def P(a, d, l, h):
    return {"Attack": a, "Defense": d, "Lethality": l, "Health": h}


# --------------------------------------------------------------------------- #
#  The nine deterministic army anchors (all attacker wins; panels = displayed %)
#  Sources: wos_sim/data/experiments/<id>.json
# --------------------------------------------------------------------------- #
ARMY = [
 # id, att_cls, att_panel, def_cls, def_panel, tier, n, attacker survivor fraction
 ("exp1_mirror_20k", "Infantry", P(176.2, 169.0, 109.7, 109.3), "Infantry", P(174.3, 153.0, 112.0, 108.7), 1, 20000, 0.24185),
 ("exp2_mirror_2k", "Infantry", P(176.2, 169.0, 109.7, 109.3), "Infantry", P(174.3, 153.0, 112.0, 108.7), 1, 2000, 0.24200),
 ("exp7_alliance_garrison_mirror_20k", "Infantry", P(199.2, 192.0, 119.7, 119.3), "Infantry", P(189.1, 167.2, 122.0, 118.7), 1, 20000, 0.30215),
 ("exp4_inf_vs_lancer", "Infantry", P(199.2, 192.0, 119.7, 119.3), "Lancer", P(189.1, 160.7, 115.3, 112.6), 6, 10000, 0.4536),
 ("exp4b_inf_vs_lancer", "Infantry", P(199.2, 192.0, 119.7, 119.3), "Lancer", P(194.1, 165.7, 115.3, 112.6), 6, 10000, 0.4282),
 ("exp5_inf_vs_marksman", "Infantry", P(199.2, 192.0, 119.7, 119.3), "Marksman", P(189.1, 165.7, 131.2, 128.6), 6, 10000, 0.0488),
 ("expX2_inf_vs_mm_10k", "Infantry", P(176.2, 169.0, 109.7, 109.3), "Marksman", P(2.0, 0.0, 0.0, 0.0), 6, 10000, 0.9841),
 ("exp3a_lancer", "Lancer", P(182.7, 163.0, 135.5, 134.1), "Marksman", P(179.1, 155.7, 121.2, 118.6), 6, 10000, 0.4200),
 ("expX1_lan_vs_mm_10k", "Lancer", P(182.7, 163.0, 135.5, 134.1), "Marksman", P(179.1, 174.2, 121.2, 118.6), 6, 10000, 0.3013),
]
# which R_TABLE source label each cross-class anchor corresponds to (for leave-one-out)
SOURCE_OF = {"exp4_inf_vs_lancer": "exp4", "exp4b_inf_vs_lancer": "exp4b",
             "exp5_inf_vs_marksman": "exp5", "expX2_inf_vs_mm_10k": "expX2",
             "exp3a_lancer": "exp3a", "expX1_lan_vs_mm_10k": "expX1"}


def _eff(cls, tier, panel):
    a, d, l, h = base_stats(cls, tier, 1)
    return eff(panel, {"A": a, "D": d, "L": l, "H": h})


def _S(att, dfn):
    return (dfn["A"] * dfn["L"] * dfn["D"] * dfn["H"]) / (att["A"] * att["L"] * att["D"] * att["H"])


def army_sigma():
    """Leave-one-out residuals of ln(beta/alpha). Same-class rows are fully blind
    (no constant was fitted); cross-class rows use the OTHER measurement's R."""
    rows = []
    for aid, ac, ap, dc, dp, tier, n, f in ARMY:
        S = _S(_eff(ac, tier, ap), _eff(dc, tier, dp))
        if ac == dc:
            R = 1.0
        else:
            _, meas, srcs = R_TABLE[(ac, dc)]
            others = [m for m, s in zip(meas, srcs) if s != SOURCE_OF[aid]]
            R = others[0]
        pred = math.log(S * R)
        obs = math.log(1.0 - f * f)
        rows.append({"id": aid, "pred_ln_ba": round(pred, 6), "obs_ln_ba": round(obs, 6),
                     "residual": round(obs - pred, 6)})
    sigma = math.sqrt(sum(r["residual"] ** 2 for r in rows) / len(rows))
    return sigma, rows


def _phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# --------------------------------------------------------------------------- #
#  Turn-engine path: labelled battles -> (|margin|, call correct)
# --------------------------------------------------------------------------- #
def _prof(role, cls, n, panel, tier, fc=1):
    return serialize.profile_from_dict({
        "role": role, "troops_total": n, "stats_mode": "scouted",
        "formation_counts": {cls: n}, "quality": {cls: {"tier": tier, "fc": fc}},
        "panel": {f"{cls}|{k}": v / 100.0 for k, v in panel.items()},
        "panel_is_final": True, "lead_heroes": {}, "joiners": []})


def labelled_turn_engine_points(n_runs=40, seed=4471):
    from wos_sim.normalize_reports import golden_anchors
    pts = []
    for aid, scen, exp in golden_anchors():
        own = serialize.profile_from_dict(scen["own"])
        enemy = serialize.profile_from_dict(scen["enemy"])
        fc = api.predict(own, enemy, n=n_runs, seed=seed, params={"engine": "turn"})
        con = construct.build(Matchup(own, enemy), apply_legacy_skills=False)
        r = winprob.effective_ratio(con)
        r_own = r if con.own_is_attacker else 1.0 / r
        call_own = fc.p_win.p >= 0.5
        real_own = exp["real_winner"] == "own"
        pts.append({"id": aid, "set": "golden", "abs_margin": abs(math.log(r_own)),
                    "call_own": call_own, "real_own": real_own,
                    "correct": call_own == real_own, "old_p": fc.p_win.p})
    for aid, ac, ap, dc, dp, tier, n, f in ARMY:
        own, enemy = _prof("rally", ac, n, ap, tier), _prof("garrison", dc, n, dp, tier)
        fc = api.predict(own, enemy, n=n_runs, seed=seed, params={"engine": "turn"})
        con = construct.build(Matchup(own, enemy), apply_legacy_skills=False)
        r = winprob.effective_ratio(con)
        call_own = fc.p_win.p >= 0.5
        pts.append({"id": aid, "set": "army", "abs_margin": abs(math.log(r)),
                    "call_own": call_own, "real_own": True,       # all attacker wins
                    "correct": call_own, "old_p": fc.p_win.p})
    return pts


def fit_logistic(xs, ys, iters=2000, lr=0.5, ridge=1e-4):
    """P(y=1|x) = logistic(a + b x), maximum likelihood by gradient ascent with a
    negligible ridge (1e-4) purely for numerical stability if the data are
    separable. b is constrained >= 0 (more margin can never make the call LESS
    reliable; enforced by clipping, not by fitting)."""
    a, b = 0.0, 1.0
    n = len(xs)
    for _ in range(iters):
        ga = gb = 0.0
        for x, y in zip(xs, ys):
            p = 1.0 / (1.0 + math.exp(-(a + b * x)))
            ga += (y - p)
            gb += (y - p) * x
        a += lr * (ga / n - ridge * a)
        b += lr * (gb / n - ridge * b)
        b = max(0.0, b)
    return a, b


def brier(ps, ys):
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps)


def main():
    sigma, rows = army_sigma()
    print("=" * 72)
    print("ARMY-LAW PATH: leave-one-out residuals of ln(beta/alpha)")
    for r in rows:
        print(f"  {r['id']:36s} pred {r['pred_ln_ba']:+.4f}  obs {r['obs_ln_ba']:+.4f}  "
              f"resid {r['residual']:+.4f}")
    print(f"  sigma_army (RMS) = {sigma:.5f}")
    print("  implied P(attacker) at each anchor (all were attacker wins):")
    for r in rows:
        print(f"    {r['id']:36s} {_phi(-r['pred_ln_ba'] / sigma):.3f}")

    pts = labelled_turn_engine_points()
    xs = [p["abs_margin"] for p in pts]
    ys = [1.0 if p["correct"] else 0.0 for p in pts]
    a, b = fit_logistic(xs, ys)
    loo = []
    for i in range(len(pts)):
        xa = xs[:i] + xs[i + 1:]
        ya = ys[:i] + ys[i + 1:]
        ai, bi = fit_logistic(xa, ya)
        conf = max(0.5, 1.0 / (1.0 + math.exp(-(ai + bi * xs[i]))))
        loo.append(conf if pts[i]["call_own"] else 1.0 - conf)
    real = [1.0 if p["real_own"] else 0.0 for p in pts]
    old = [p["old_p"] for p in pts]
    print()
    print("=" * 72)
    print("TURN-ENGINE PATH: P(engine call correct | |ln r|)")
    for p, x, y in zip(pts, xs, ys):
        conf = max(0.5, 1.0 / (1.0 + math.exp(-(a + b * x))))
        print(f"  {p['id']:36s} [{p['set']:6s}] |m|={x:.3f} correct={'Y' if y else 'n'}  "
              f"old_p={p['old_p']:.2f}  conf={conf:.3f}")
    print(f"  fit: a={a:.4f} b={b:.4f}  (n={len(pts)}, call accuracy {sum(ys) / len(ys):.0%})")
    print(f"  Brier (own-win prob vs real): OLD heuristic {brier(old, real):.4f}   "
          f"NEW calibrated (leave-one-out) {brier(loo, real):.4f}")

    out = {
        "generated_by": "wos_sim/formula_research/calibrate_winprob.py",
        "army_law": {"sigma_ln_beta_over_alpha": round(sigma, 6), "n_anchors": len(rows),
                     "method": "RMS of leave-one-out residuals", "residuals": rows},
        "turn_engine": {"a": round(a, 6), "b": round(b, 6), "n_battles": len(pts),
                        "margin": "abs(ln(effective_ratio_own)) from winprob.effective_ratio",
                        "brier_old_heuristic": round(brier(old, real), 5),
                        "brier_new_loo": round(brier(loo, real), 5),
                        "points": [{k: (round(v, 5) if isinstance(v, float) else v)
                                    for k, v in p.items()} for p in pts]},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"\nwrote {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
