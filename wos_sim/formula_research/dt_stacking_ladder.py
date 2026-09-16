"""Pre-registered predictions + evaluator for the Damage-Taken (DT) joiner-stacking
ladder (EXPERIMENT_DT_STACKING.md, 2026-09-11).

THE QUESTION
  How does the game compose k copies of the same joiner's Damage-Taken reduction?
  Wu Ming S1 = -25% DT (Normal channel) on Infantry per copy. The engine today
  composes it ADDITIVELY and then compresses with the fitted mod_gamma = 0.30
  (pvp_turn_engine.py: dt_total = max(sum, -1); (1+dt)**gamma - 1). That form has
  never been measured; GAME_RULES.md s.304 records a real battle that contradicts
  a raw additive stack. This ladder measures it.

THE OBSERVABLE
  The DT side must LOSE, so its death turn t_k is observed. In the Type-1 lab
  regime the kill clock is proportional to effective HP, so
        t_k / t_0 = M_k   (the effective-toughness multiple from k copies)
  and each composition family predicts a distinct M_k:

    additive            M_k = 1 / (1 - 0.25 k)
    multiplicative      M_k = 1 / 0.75**k
    engine-today        M_k = 1 / (1 - 0.25 k)**0.30        (additive + gamma)
    capped at c         M_k = 1 / (1 - min(0.25 k, c))

  k = 1 alone tests the gamma compression (1.33 vs 1.09 -- a 22% gap); k = 3
  separates additive from multiplicative (4.00 vs 2.37 -- a 69% gap).

DECISION RULE (pre-registered, matches the A6 exact-fit bar)
  A family is ACCEPTED only if every observed ratio t_k/t_0 (k = 1..3) lies
  within +-5% of its prediction after integer-turn quantisation (deaths land on
  integer turns: predicted t_k = ceil(t_0 * M_k)). If no family passes, report
  the best log-space least-squares family as a HYPOTHESIS, not a result.
  No family may be fitted to the data: the curves below are frozen before the
  battles are fought.

USAGE
  py -m wos_sim.formula_research.dt_stacking_ladder            # prediction table
  py -m wos_sim.formula_research.dt_stacking_ladder 78         # absolute turns for t_0 = 78
  py -m wos_sim.formula_research.dt_stacking_ladder 78 104 156 312   # evaluate observed t_0..t_3
"""
from __future__ import annotations

import math
import sys

DT_PER_COPY = 0.25          # Wu Ming S1, Normal channel, Infantry (catalog row)
GAMMA_ENGINE = 0.30         # pvp_turn_engine TURN_PARAMS mod_gamma (fitted; under test here)
TURN_CAP = 1500             # GAME_RULES: global battle cap -- t_0 * 4 must stay below it
TOL = 0.05                  # acceptance band on each ratio
KS = (1, 2, 3)


def families() -> dict:
    """Frozen prediction curves. Keys are family names; values map k -> M_k."""
    add = {k: 1.0 / (1.0 - DT_PER_COPY * k) for k in KS}
    mul = {k: 1.0 / (1.0 - DT_PER_COPY) ** k for k in KS}
    eng = {k: 1.0 / (1.0 - DT_PER_COPY * k) ** GAMMA_ENGINE for k in KS}
    cap50 = {k: 1.0 / (1.0 - min(DT_PER_COPY * k, 0.50)) for k in KS}
    cap60 = {k: 1.0 / (1.0 - min(DT_PER_COPY * k, 0.60)) for k in KS}
    return {"additive": add, "multiplicative": mul,
            "engine-today (additive+gamma0.30)": eng,
            "capped -50%": cap50, "capped -60%": cap60}


def table(t0: float | None = None) -> str:
    fam = families()
    w = max(len(n) for n in fam)
    out = [f"{'family':{w}s} " + "".join(f"{'M_'+str(k):>9s}" for k in KS)
           + ("" if t0 is None else "   " + "".join(f"{'t_'+str(k):>7s}" for k in KS))]
    for name, m in fam.items():
        line = f"{name:{w}s} " + "".join(f"{m[k]:9.3f}" for k in KS)
        if t0 is not None:
            line += "   " + "".join(f"{math.ceil(t0 * m[k]):7d}" for k in KS)
        out.append(line)
    if t0 is not None:
        worst = max(math.ceil(t0 * m[3]) for m in fam.values())
        out.append(f"\n  t_0 = {t0:g}: largest 3-copy prediction {worst} turns "
                   f"({'OK' if worst < TURN_CAP else '!! EXCEEDS THE 1500 CAP -- choose a stronger attacker'} "
                   f"vs cap {TURN_CAP})")
    return "\n".join(out)


def evaluate(t0: float, t1: float, t2: float, t3: float) -> str:
    obs = {1: t1 / t0, 2: t2 / t0, 3: t3 / t0}
    lines = [f"observed ratios: " + "  ".join(f"t_{k}/t_0 = {obs[k]:.3f}" for k in KS)]
    accepted, scored = [], []
    for name, m in families().items():
        # quantised prediction: the ratio the integer death turn would show
        pred = {k: math.ceil(t0 * m[k]) / t0 for k in KS}
        errs = {k: obs[k] / pred[k] - 1.0 for k in KS}
        ok = all(abs(e) <= TOL for e in errs.values())
        sse = sum(math.log(obs[k] / pred[k]) ** 2 for k in KS)
        scored.append((sse, name))
        if ok:
            accepted.append(name)
        lines.append(f"  {name:36s} " + "  ".join(f"{errs[k]:+6.1%}" for k in KS)
                     + f"   {'ACCEPT' if ok else 'reject'}")
    scored.sort()
    if accepted:
        lines.append(f"\nRESULT: accepted family/ies within +-{TOL:.0%} on every rung: {accepted}")
    else:
        lines.append(f"\nRESULT: no family within +-{TOL:.0%} on every rung. Best log-LS family is "
                     f"'{scored[0][1]}' -- report as a HYPOTHESIS only; do not fit.")
    return "\n".join(lines)


def main(argv: list[str]) -> None:
    nums = [float(a) for a in argv]
    if len(nums) == 0:
        print(table())
    elif len(nums) == 1:
        print(table(nums[0]))
    elif len(nums) == 4:
        print(table(nums[0])); print(); print(evaluate(*nums))
    else:
        raise SystemExit("usage: [t_0] | t_0 t_1 t_2 t_3")


if __name__ == "__main__":
    main(sys.argv[1:])
