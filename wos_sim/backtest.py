"""MANDATORY engine back-test. Run this BEFORE and AFTER any engine or
TURN_PARAMS change:

    py -m wos_sim.backtest

It replays EVERY calibrated real battle through the production engine and
verdicts the change:

  * WINNER LOCK (blocking) - every battle whose winner the engine already gets
    right (golden_baseline.json::locked_pass) must STAY right, and no new
    "silent" wrong-winner (confident + not flagged coin-flip) may appear.
  * COMPOSITION MAGNITUDES (report) - the deterministic controlled experiments
    (mirror, counter matchups) printed against their real survivor%, so a
    change that improves/worsens magnitude is visible.

Exit code 0 = PASS (safe to keep), 1 = FAIL (a previously-correct battle
regressed - DO NOT SHIP). This is the guardrail that stops a fit-to-one-report
change from blowing up the others (Martin's directive 2026-07-09).
"""
from __future__ import annotations

import sys

from wos_sim.eval_reports import evaluate, golden_regression

# Deterministic controlled experiments (Martin's in-game tests): the real
# attacker-survivor% for magnitude tracking. Winners are all correct already;
# these track how close the MAGNITUDE is (the open calibration target).
COMPOSITION_ANCHORS = {
    "mirror (inf v inf)":        24.0,
    "inf > lancer":              45.4,
    "inf < marksman":             4.9,
    "lancer > marksman":         42.0,
}


def _composition_rows():
    """Run the 4 controlled composition matchups (Lv6, no skills)."""
    from wos_sim.predictor import api
    from wos_sim.predictor.profiles import ClassQuality, SideProfile
    CL = ("Infantry", "Lancer", "Marksman"); ST = ("Attack", "Defense", "Lethality", "Health")
    AP = {"Infantry": {"Attack": 1.992, "Defense": 1.920, "Lethality": 1.197, "Health": 1.193},
          "Lancer": {"Attack": 2.057, "Defense": 1.86, "Lethality": 1.455, "Health": 1.441},
          "Marksman": {"Attack": 1.992, "Defense": 1.89, "Lethality": 1.391, "Health": 1.390}}
    DP = {"Infantry": {"Attack": 1.891, "Defense": 1.672, "Lethality": 1.22, "Health": 1.187},
          "Lancer": {"Attack": 1.891, "Defense": 1.607, "Lethality": 1.153, "Health": 1.126},
          "Marksman": {"Attack": 1.891, "Defense": 1.657, "Lethality": 1.312, "Health": 1.286}}

    def mk(role, cls, P):
        comp = {c: (10000 if c == cls else 0) for c in CL}
        return SideProfile(role=role, troops_total=10000, stats_mode="scouted",
                           formation={c: comp[c] / 10000 for c in CL},
                           formation_counts={c: float(comp[c]) for c in CL},
                           quality={c: ClassQuality(tier=6, fc=1) for c in CL},
                           panel={(c, s): P[c][s] for c in CL for s in ST},
                           panel_is_final=True, lead_heroes={}, joiners=[])
    pairs = [("mirror (inf v inf)", "Infantry", "Infantry"),
             ("inf > lancer", "Infantry", "Lancer"),
             ("inf < marksman", "Infantry", "Marksman"),
             ("lancer > marksman", "Lancer", "Marksman")]
    out = []
    for label, a, d in pairs:
        fc = api.predict(mk("rally", a, AP), mk("garrison", d, DP), n=1, seed=1,
                         params={"engine": "turn"})
        out.append((label, 100.0 - fc.army_losses["own"].median, COMPOSITION_ANCHORS[label]))
    return out


def main():
    print("=" * 64)
    print(" MANDATORY ENGINE BACK-TEST (run before AND after any change)")
    print("=" * 64)

    # 1. WINNER LOCK ---------------------------------------------------------
    v = golden_regression(n=25)
    rows = evaluate(n=25)
    print("\n[1] WINNER LOCK - 13 calibrated real battles (production path)")
    print(f"    {'id':9} {'REAL':6} {'ENGINE':6} {'':4} p_win")
    for r in rows:
        mark = "ok" if r["match"] else "MISS"
        print(f"    {r['id']:9} {r['real']:6} {r['eng']:6} {mark:4} {r['p_win']:.2f}")
    print(f"    winners correct: {v['match_count']}/13   (baseline {v['baseline_count']})")

    # 2. COMPOSITION MAGNITUDES --------------------------------------------
    print("\n[2] COMPOSITION MAGNITUDES - controlled experiments (winner already OK)")
    print(f"    {'matchup':22} {'engine surv%':>12} {'real surv%':>11}")
    for label, eng, real in _composition_rows():
        print(f"    {label:22} {eng:11.1f}% {real:10.1f}%")

    # 3. VERDICT ------------------------------------------------------------
    print("\n" + "=" * 64)
    if v["ok"]:
        print(" VERDICT: PASS - no locked battle regressed, no new silent miss.")
        if v["improved"]:
            print(f"   IMPROVED (update golden_baseline.json locked_pass): {v['improved']}")
        print("=" * 64)
        return 0
    print(" VERDICT: FAIL - DO NOT SHIP THIS CHANGE.")
    if v["broken"]:
        print(f"   BROKE previously-correct winners: {v['broken']}")
    if v["new_silent"]:
        print(f"   NEW silent wrong-winner (confident, unflagged): {v['new_silent']}")
    print("=" * 64)
    return 1


if __name__ == "__main__":
    sys.exit(main())
