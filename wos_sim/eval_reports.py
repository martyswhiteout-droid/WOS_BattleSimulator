"""Run every normalized real battle through the PRODUCTION engine path
(api.predict, engine=turn) and tabulate engine-vs-reality. This is the
overfit detector: if a calibration change flips a battle the engine used to
get right, it shows up here.

    py -m wos_sim.eval_reports            # full engine-vs-reality table
"""
from __future__ import annotations

import json
from pathlib import Path

from wos_sim.normalize_reports import golden_anchors
from wos_sim.predictor import api, serialize

_BASELINE = Path(__file__).resolve().parent / "data" / "golden_baseline.json"


def golden_regression(n: int = 40, seed: int = 4471) -> dict:
    """The OVERFIT GUARDRAIL check. Returns a verdict dict:
      ok            - True iff no locked-pass battle regressed and silent
                      misses did not grow.
      broken        - locked-pass ids the engine now gets WRONG (must be empty).
      improved      - known-miss ids the engine now gets RIGHT (bonus).
      match_count   - winners correct across all golden battles.
      silent_misses - wrong-winner battles NOT flagged near-even (dangerous).
    Deterministic (fixed seed); the locked battles are decisive (p_win 0/1) so
    the check is stable at low n.
    """
    base = json.loads(_BASELINE.read_text())
    locked = set(base["locked_pass"])
    silent_baseline = set(base.get("silent_miss_baseline", []))
    rows = evaluate(n=n, seed=seed)
    by = {r["id"]: r for r in rows}
    match_ids = {r["id"] for r in rows if r["match"]}
    broken = sorted(locked - match_ids)
    improved = sorted((set(by) - locked) & match_ids
                      & set(base.get("known_miss", {})))
    silent = sorted(r["id"] for r in rows
                    if not r["match"] and r["near_even"] != "Y")
    new_silent = sorted(set(silent) - silent_baseline)
    return {
        "ok": not broken and not new_silent,
        "broken": broken,
        "improved": improved,
        "match_count": len(match_ids),
        "baseline_count": base["baseline_pass_count"],
        "silent_misses": silent,
        "new_silent": new_silent,
    }


def evaluate(n: int = 200, seed: int = 4471):
    rows = []
    for aid, scen, exp in golden_anchors():
        own = serialize.profile_from_dict(scen["own"])
        enemy = serialize.profile_from_dict(scen["enemy"])
        fc = api.predict(own, enemy, n=n, seed=seed, params={"engine": "turn"})
        eng_winner = "own" if fc.p_win.p >= 0.5 else "enemy"
        own_surv = 1.0 - fc.army_losses["own"].median / 100.0
        near_even = "coin" if fc.p_win.p not in (0.0, 1.0) or "coin_flip" in (fc.engine_note or "") else ""
        # honest near-even flag from engine_meta note
        near = "Y" if "coin flip" in (fc.engine_note or "").lower() or "near-even" in (fc.engine_note or "").lower() else "-"
        rows.append({
            "id": aid, "real": exp["real_winner"], "eng": eng_winner,
            "match": eng_winner == exp["real_winner"],
            "p_win": fc.p_win.p, "eng_own_surv": own_surv,
            "real_own_surv": exp["own_surv_frac"], "near_even": near,
            "role": exp.get("own_role"),
        })
    return rows


def main():
    rows = evaluate()
    print(f"{'id':9} {'role':9} {'REAL':6} {'ENGINE':6} {'match':6} "
          f"{'p_win':>6} {'eng_surv':>8} {'real_surv':>9} near-even")
    n_match = 0
    for r in rows:
        mark = "OK" if r["match"] else "**MISS**"
        n_match += r["match"]
        print(f"{r['id']:9} {r['role']:9} {r['real']:6} {r['eng']:6} {mark:8} "
              f"{r['p_win']:6.2f} {r['eng_own_surv']*100:7.1f}% {r['real_own_surv']*100:8.1f}% "
              f"  {r['near_even']}")
    print(f"\nWINNER match: {n_match}/{len(rows)}")
    misses = [r for r in rows if not r["match"]]
    if misses:
        near = [r for r in misses if r["near_even"] == "Y"]
        print(f"  misses: {[r['id'] for r in misses]}")
        print(f"  of which flagged near-even/coin-flip (honest miss): {[r['id'] for r in near]}")
        print(f"  NOT flagged (silent wrong-winner - the dangerous ones): "
              f"{[r['id'] for r in misses if r['near_even'] != 'Y']}")


if __name__ == "__main__":
    main()
