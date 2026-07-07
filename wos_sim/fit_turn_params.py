"""Grid-fit TURN_PARAMS against the three T12 anchors (ENGINE_REBUILD P1).

Deterministic, replayable search (seed 0 sims; no wall-clock/randomized moves):

    py -m wos_sim.fit_turn_params            # coarse grid
    py -m wos_sim.fit_turn_params --refine "rate=60,def_k=300,def_ed=0.75,stat_floor=0.25"

Objective (lexicographic):
  1. all three winners correct (hard filter, reported either way)
  2. total gates passed (wos_sim.anchor_eval scorecard)
  3. smaller sum of |log(turns_pred / turns_real_mid)|
  4. smaller sum of |log(att_surv_pred / att_surv_real)|
"""
from __future__ import annotations

import argparse
import itertools
import math

from wos_sim.anchor_eval import REALITY, anchors, run_turn, scorecard

TURNS_MID = {"A1": 16.0, "A2": 25.0, "A3": 19.5}
SURV_REAL = {"A1": 62_364.0, "A2": 118_068.0, "A3": 93_432.0}

COARSE = {
    "rate": [140.0, 168.0, 220.0],
    # def_k > 1 = garrison per-capita advantage (defensive position). The base
    # exchange asymmetry at parity is ~1.46 attacker-favored; reality ~1.07.
    "def_k": [1.0, 1.3, 1.6, 2.0, 2.6],
    "def_ed": [1.0],
    # wounded-keep-fighting: stacks fire at STARTING strength until broken
    # (constant absolute casualty rates, all three anchors) vs legacy live-count.
    "fire_mode": ["start", "live"],
    # diminishing returns on stacked skill modifiers: anchors show big kits
    # net to ~1x exchange; raw stacking gives 3-4x.
    "mod_gamma": [0.25, 0.5],
    "stat_floor": [0.40],
}


def evaluate(params: dict, cached_anchors) -> tuple:
    per = {}
    winners_ok = True
    gates = 0
    turns_err = surv_err = 0.0
    for name, matchup in cached_anchors:
        con, res = run_turn(matchup, params, seed=0)
        checks = scorecard(name, con, res, is_turn=True)
        ok = sum(1 for *_, o in checks.values() if o)
        gates += ok
        if not checks["winner"][2]:
            winners_ok = False
        turns_err += abs(math.log(max(res.turns, 1) / TURNS_MID[name]))
        surv = max(sum(res.a_survivors.values()), 1.0)
        surv_err += abs(math.log(surv / SURV_REAL[name]))
        per[name] = (checks["winner"][0], res.turns, round(surv))
    return (winners_ok, gates, -turns_err, -surv_err), per


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--refine", default=None,
                    help="center point k=v,... to refine around (+-30%% x 3 steps)")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args(argv)

    cached = anchors()
    if args.refine:
        grid = {}
        for kv in args.refine.split(","):
            k, v = kv.split("=")
            k = k.strip()
            try:
                grid[k] = sorted({round(float(v) * f, 4)
                                  for f in (0.7, 0.85, 1.0, 1.2, 1.4)})
            except ValueError:
                grid[k] = [v.strip()]          # string knob (e.g. fire_mode)
    else:
        grid = COARSE

    keys = list(grid)
    results = []
    combos = list(itertools.product(*(grid[k] for k in keys)))
    print(f"evaluating {len(combos)} parameter sets over 3 anchors...")
    for combo in combos:
        params = dict(zip(keys, combo))
        try:
            score, per = evaluate(params, cached)
        except Exception as exc:                      # keep the sweep alive
            print(f"  ERROR {params}: {exc}")
            continue
        results.append((score, params, per))
    results.sort(key=lambda r: r[0], reverse=True)
    print(f"\ntop {args.top} (winners_ok, gates, -turns_err, -surv_err):")
    for score, params, per in results[: args.top]:
        flag = "ALL-WINNERS" if score[0] else "           "
        ps = " ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                      for k, v in params.items())
        pa = "  ".join(f"{n}:{w}/{t}t/{s:,}" for n, (w, t, s) in per.items())
        print(f"  {flag} gates={score[1]:2d} tE={-score[2]:.2f} sE={-score[3]:.2f} | {ps}")
        print(f"              {pa}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
