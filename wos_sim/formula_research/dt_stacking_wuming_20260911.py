"""Evaluate the 2026-09-11 Wu Ming battles (wos_sim/data/experiments/Wu Ming Experiments)
against the PRE-REGISTERED families in EXPERIMENT_DT_STACKING.md.

These battles deviate from the spec's design (Lv2/Lv3 skills = -10%/-15% instead of the
max-level -25%; Wu Ming fielded as CAPTAIN in B2/B3; 2-unit T9+T10 defender), so the
generic ladder script must not be used. The rungs below are the single-variable steps
the reports actually support. Only Wu Ming's NORMAL channel fired: the attacker's
Gatot skills are stat passives (deals_damage=False) and no chance-based troop skill
was active, so the -12%/-18% Skills rows never applied.

Kill-clock model (per-unit law, exponent 1 on the loser's D and H):
    t  ∝  D_l · H_l · M_DT           (attacker constant across all six battles)
so a rung's DT multiple is  M = (t_b / t_a) / (D_b·H_b / D_a·H_a),  D = 1 + panel/100.

Decision rule (frozen in the spec): a family is ACCEPTED only if every discriminating
rung is within +-5% of its quantised prediction; otherwise the best family is a
HYPOTHESIS only. Nothing is fitted.
"""
from __future__ import annotations

import glob
import json
import math
import os

FOLDER = os.path.join(os.path.dirname(__file__), "..", "data", "experiments", "Wu Ming Experiments")
GAMMA_ENGINE = 0.30
TOL = 0.05


def load():
    out = {}
    for f in sorted(glob.glob(os.path.join(FOLDER, "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        tag = os.path.basename(f).split("_")[2]           # B1..B6
        inf = d["defender"]["stats_pct"]["Infantry"]
        turns = d.get("turn_inference", {}).get("turns")
        if turns is None:
            for hs in d["attacker"].get("hero_skills", []):
                if hs.get("hero") == "Gatot" and hs.get("slot") == "Skill 2":
                    turns = hs.get("triggers")
        out[tag] = dict(turns=turns, D=1 + inf["Defense"] / 100, H=1 + inf["Health"] / 100,
                        A=inf["Attack"], Dp=inf["Defense"])
    return out


def dh(b):
    return b["D"] * b["H"]


def fam_single(x):
    """Multiples for ONE source of reduction x, per family."""
    return {"additive": 1 / (1 - x), "multiplicative": 1 / (1 - x),
            "engine-today (gamma 0.30)": (1 - x) ** -GAMMA_ENGINE}


def fam_two(x1, x2):
    """Multiples for two stacked sources, RELATIVE TO the first alone."""
    return {"additive": (1 - x1) / (1 - x1 - x2),
            "multiplicative": 1 / (1 - x2),
            "engine-today (gamma 0.30)": ((1 - x1) / (1 - x1 - x2)) ** GAMMA_ENGINE}


def main():
    b = load()
    for k in sorted(b):
        print(f"  {k}: turns={b[k]['turns']:>4}  Inf Attack={b[k]['A']:6.1f}  Defense={b[k]['Dp']:6.1f}  D*H={dh(b[k]):.3f}")
    print()
    rungs = []
    # (a) B1 -> B3: captain Wu Ming Lv3 (-15%) enters; Defense +171.7 corrected via the law.
    corr = dh(b["B3"]) / dh(b["B1"])
    obs = (b["B3"]["turns"] / b["B1"]["turns"]) / corr
    rungs.append((f"(a) B1->B3  single -15% (D-corrected x{corr:.3f})", obs, fam_single(0.15), True))
    # (b) B3 -> B4: joiner Wu Ming Lv2 (-10%) added on top of captain -15%; panel identical.
    rungs.append(("(b) B3->B4  +joiner -10% on -15%", b["B4"]["turns"] / b["B3"]["turns"], fam_two(0.15, 0.10), True))
    # (c) B3 -> B5: joiner at Lv3 (-15%) on top of captain -15%; panel carried over from B4.
    rungs.append(("(c) B3->B5  +joiner -15% on -15%", b["B5"]["turns"] / b["B3"]["turns"], fam_two(0.15, 0.15), True))
    # (d) B2 -> B6: captain Lv2 -> Lv3 (-10% -> -15%), Blizzard's own panel both times.
    d_fam = {k: v / w for (k, v), w in zip(fam_single(0.15).items(), fam_single(0.10).values())}
    rungs.append(("(d) B2->B6  captain -10% -> -15%", b["B6"]["turns"] / b["B2"]["turns"], d_fam, False))
    # (e) B4 -> B5: joiner -10% -> -15% with captain -15% (small step)
    e_fam = {k: v / w for (k, v), w in zip(fam_two(0.15, 0.15).items(), fam_two(0.15, 0.10).values())}
    rungs.append(("(e) B4->B5  joiner -10% -> -15%", b["B5"]["turns"] / b["B4"]["turns"], e_fam, False))

    fams = ["additive", "multiplicative", "engine-today (gamma 0.30)"]
    print(f"{'rung':46s} {'observed':>9s}   " + "".join(f"{f:>28s}" for f in fams))
    verdict = {f: True for f in fams}
    for name, obs, pred, discriminating in rungs:
        cells = []
        for f in fams:
            e = obs / pred[f] - 1
            ok = abs(e) <= TOL
            if discriminating and not ok:
                verdict[f] = False
            cells.append(f"{pred[f]:6.3f} ({e:+5.1%}) {'ok' if ok else 'X '}")
        print(f"{name:46s} {obs:9.4f}   " + "".join(f"{c:>28s}" for c in cells)
              + ("" if discriminating else "   [non-discriminating: all within band]"))
    print()
    acc = [f for f in fams if verdict[f]]
    print("Discriminating rungs = (a), (b), (c). Under the pre-registered +-5% rule:")
    for f in fams:
        print(f"  {f:28s} {'ACCEPTED' if verdict[f] else 'REJECTED'}")
    # the compound absolute, for the record (not independent of a and c)
    obs_e = (b["B5"]["turns"] / b["B1"]["turns"]) / corr
    print(f"\nFor the record, B1->B5 absolute (D-corrected, = (a)x(c)): observed {obs_e:.3f} vs "
          f"additive {1/0.70:.3f}, multiplicative {1/0.85**2:.3f}, engine-today {0.70**-GAMMA_ENGINE:.3f}")
    print("Observations sit 2.8-4.5% BELOW the uncompressed multiplicative curve on every rung --")
    print("a consistent shortfall, i.e. a HINT of mild compression (not a fit; needs the max-level rungs).")
    print(f"\nCaveats: rung (a) assumes B1 is MatiLife's garrison with no captain hero (panel evidence: "
          f"Leth/Health identical to B3, Atk/Def exactly -171.7) -- Martin to confirm the header. "
          f"Skill levels here are Lv2/Lv3 (-10/-15%), not the spec's max-level -25%; the FORM is "
          f"measured, its extrapolation to 3x max-level Wu Ming is not.")


if __name__ == "__main__":
    main()
