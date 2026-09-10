"""Stage 8.1 -- the ARMY-SCALE same-class attrition backbone.

Derived (not fitted) from the 20k/2k count-scaling pair
(`exp1_mirror_20k.json` / `exp2_mirror_2k.json`) plus the alliance-garrison mirror
(`exp7_alliance_garrison_mirror_20k.json`). See `STAGE8_1_FINDINGS.md`.

THE PHYSICS
  Per-unit kill-rate coefficients, straight from the frozen Stage-4/6 form
  (damage ~ A*L, effective HP ~ D*H):

      alpha = A_att * L_att / (D_def * H_def)      # attacker's rate vs the defender
      beta  = A_def * L_def / (D_att * H_att)      # defender's rate vs the attacker

  Army damage pools LINEARLY in troop count (MEASURED: the 10x pair fixes the
  survivor fraction at 0.24185 vs 0.242 -- exactly scale-invariant; the sqrt(N)
  alternative predicts 0.1506 and is REFUTED at army scale). Combat is
  SIMULTANEOUS with casualties removed at turn end (GAME_RULES.md s.4), so the
  discrete recurrence is

      N_def(t+1) = N_def(t) - c * alpha * N_att(t)
      N_att(t+1) = N_att(t) - c * beta  * N_def(t)

  both sides computed from START-OF-TURN counts. `c` is the single absolute rate
  scale (turns^-1); it does NOT affect who wins, only how many turns the battle
  takes and hence the discretisation. Its continuum limit (c -> 0) is Lanchester's
  square law:

      A_f^2 = N_att^2 - (beta/alpha) * N_def^2        (equal counts: sqrt(1-beta/alpha))

  Both forms are exactly scale-invariant in the counts, matching the measurement.

WHY DISCRETE MATTERS
  The continuum form over-predicts the winner's survivors when the battle is
  SHORT: the last turn overshoots (a side that would die "mid-turn" still fires a
  full volley). The mixed-composition runs show these battles last only ~6-12
  turns (troop-skill trigger counts 6 and 12), so the discrete form is the honest
  one; `predict_army_same_class` uses it by default.

SCOPE (do not exceed without new data)
  * SAME-CLASS, same-tier, both sides -- base stats cancel, so panels alone decide.
  * Cross-class army battles are NOT covered: the lab-regime K-table and tier
    damping do not transfer to army scale (STAGE8_1_FINDINGS.md Finding 5). Callers
    must not silently use this for mixed matchups.
  * Deterministic only (no procs). Proc-bearing armies -> the Stage 8.3 layer.
"""
from __future__ import annotations

import math

#: global battle cap (GAME_RULES: a capped battle with survivors on both sides is
#: a defeat for the attacker if any enemy remains)
CAP_TURNS = 1500

def law_rate_scale(cls: str, tier: int, law=None) -> float:
    """The absolute per-turn rate scale c from the FROZEN per-unit law -- NOT a
    fitted constant: the law says a 1v1 kill takes K*(D*H)/(A*L)*G_w*G_l turns, so
    the per-unit rate is alpha/(K*G_w*G_l), i.e. c = 1/(K*G_w*G_l).

    MEASURED CONSEQUENCE (2026-07-25): for the same-class mirrors this yields
    500-800 turn battles, so the discrete recurrence sits essentially at its
    continuum limit -- discreteness moves the survivor fraction by only ~0.3%.
    Discreteness is therefore RULED OUT as an explanation of the exp7 residual
    (see the module docstring / STAGE8_1_FINDINGS.md).
    """
    if law is None:
        from wos_sim.formula_research import stage6_tables as _t6
        law = _t6.law_funcs()
    def _v(x):
        return x[0] if isinstance(x, tuple) else x
    k = _v(law["K"](cls, cls))
    g = _v(law["g_w"](tier, cls)) * _v(law["g_l"](tier, cls))
    return 1.0 / (k * g)


def rates(att: dict, dfn: dict) -> tuple[float, float]:
    """(alpha, beta) per-unit kill-rate coefficients from effective stats."""
    alpha = att["A"] * att["L"] / (dfn["D"] * dfn["H"])
    beta = dfn["A"] * dfn["L"] / (att["D"] * att["H"])
    return alpha, beta


def continuum_fraction(alpha: float, beta: float, n_att: float, n_def: float):
    """Lanchester square law (c -> 0 limit). Returns (winner, winner_fraction)."""
    x = n_att * n_att - (beta / alpha) * n_def * n_def
    if x > 0:
        return "attacker", math.sqrt(x) / n_att
    y = n_def * n_def - (alpha / beta) * n_att * n_att
    return "defender", (math.sqrt(y) / n_def if y > 0 else 0.0)


def predict_army_same_class(att: dict, dfn: dict, *, n_att: float, n_def: float,
                            rate: float | None = None, discrete: bool = True) -> dict:
    """Army-scale outcome for a SAME-CLASS, same-tier, proc-free matchup.

    att/dfn: effective stats {"A","D","L","H"} (base x (1+panel)).
    Returns {winner, winner_fraction, att_survivors, def_survivors, turns, capped, mode}.
    O(1) in the continuum mode; O(turns) discrete -- never O(troops), so 1e6-troop
    armies are as cheap as 10.
    """
    alpha, beta = rates(att, dfn)
    if not discrete:
        w, f = continuum_fraction(alpha, beta, n_att, n_def)
        surv = f * (n_att if w == "attacker" else n_def)
        return {"winner": w, "winner_fraction": f, "turns": None, "capped": False,
                "att_survivors": surv if w == "attacker" else 0.0,
                "def_survivors": surv if w == "defender" else 0.0,
                "alpha": alpha, "beta": beta, "mode": "continuum"}
    if rate is None:
        raise ValueError("rate is required in discrete mode -- pass "
                         "law_rate_scale(cls, tier) (the law-derived scale) or an "
                         "explicit value; there is no default fudge constant.")
    c = rate
    a, d = float(n_att), float(n_def)
    t = 0
    while a > 0 and d > 0 and t < CAP_TURNS:
        t += 1
        da = c * beta * d          # attacker losses, from start-of-turn defender count
        dd = c * alpha * a         # defender losses, from start-of-turn attacker count
        a, d = max(0.0, a - da), max(0.0, d - dd)
    capped = t >= CAP_TURNS and a > 0 and d > 0
    if a > 0 and d <= 0:
        w, f = "attacker", a / n_att
    elif d > 0 and a <= 0:
        w, f = "defender", d / n_def
    elif a <= 0 and d <= 0:
        w, f = "mutual", 0.0
    else:
        # BOTH sides still alive at the numerical safety limit. GAME_RULES.md s.424
        # (Martin-CONFIRMED) says "every battle ends in a wipe of at least one side
        # -- no exceptions, no turn cap, no retreat", so a capped state is an
        # ARTEFACT OF THIS SOLVER, not an outcome. Declaring a winner here (the old
        # `a >= d` tie-break, which silently favoured the attacker) FABRICATED
        # results: two identical sides both at 19,191.91 troops were reported as a
        # 100% attacker win with the defender zeroed. Never infer a winner from a
        # partial state -- abstain and preserve BOTH survivor counts (QA P1 #1).
        w, f = "uncertain", 0.0
    return {"winner": w, "winner_fraction": f, "turns": t, "capped": capped,
            "att_survivors": a, "def_survivors": d,
            "alpha": alpha, "beta": beta, "mode": "discrete"}


def _solve_rate(att, dfn, n_att, n_def, observed_fraction, observed_winner="attacker"):
    """Bisect the single rate scale c so the discrete sim reproduces one observed
    survivor fraction. ONE equation, ONE unknown -- an identification, not a fit."""
    lo, hi = 1e-6, 0.5
    for _ in range(200):
        mid = (lo + hi) / 2
        r = predict_army_same_class(att, dfn, n_att=n_att, n_def=n_def, rate=mid)
        f = r["winner_fraction"] if r["winner"] == observed_winner else -r["winner_fraction"]
        # larger c -> shorter battle -> MORE winner survivors (less grind)
        if f > observed_fraction:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


# --------------------------------------------------------------------------- #
#  CROSS-CLASS (2026-07-28) -- the class-pair ratio R
#
#  Extending the same-class law to different classes needs ONE extra factor per
#  ordered class pair. If each attack direction carries a factor C(att -> def),
#  only the RATIO survives in beta/alpha:
#
#       beta/alpha = S(stats) * R      S = (A_d L_d D_d H_d)/(A_a L_a D_a H_a)
#                                      R = C(def->att) / C(att->def)
#
#  Same class => R = 1 (which is why the same-class law needed no extra term).
#  Each observed battle MEASURES its pair: R = (1 - f^2) / S.
#
#  EVIDENCE: every pair has TWO independent battles at different stat gaps.
#  The factorization C(X->Y)=f(X)g(Y) was REFUTED by its own zero-parameter blind
#  test (the triangle R(Inf,Lan)*R(Lan,MM) = R(Inf,MM) misses by -6.2%), so the
#  three pairs are independent and all three are measured. Full derivation and
#  validation: STAGE8_1_FINDINGS.md Addenda 8-9.
#
#  SCOPE: measured at TIER 6, ~10k scale, proc-free, hero-free. Tier dependence is
#  UNMEASURED -- callers must not use these outside T6.
# --------------------------------------------------------------------------- #
R_MEASURED_TIER = 6

#: {(attacker_class, defender_class): (R, [the two measurements], sources)}
R_TABLE = {
    ("Infantry", "Lancer"):   (0.7896, [0.7929, 0.7863], ("exp4", "exp4b")),
    ("Infantry", "Marksman"): (0.7959, [0.8060, 0.7859], ("exp5", "expX2")),
    ("Lancer", "Marksman"):   (0.9454, [0.9317, 0.9592], ("exp3a", "expX1")),
}


def class_pair_R(att_cls: str, def_cls: str):
    """(R, relative_uncertainty) for an ordered class pair, or (None, None) if the
    pair is unmeasured. Same class -> (1.0, 0.0) exactly. The reverse direction is
    the reciprocal: R(Y,X) = 1/R(X,Y) follows from R's definition."""
    if att_cls == def_cls:
        return 1.0, 0.0
    if (att_cls, def_cls) in R_TABLE:
        r, meas, _ = R_TABLE[(att_cls, def_cls)]
        return r, (max(meas) - min(meas)) / r
    if (def_cls, att_cls) in R_TABLE:
        r, meas, _ = R_TABLE[(def_cls, att_cls)]
        return 1.0 / r, (max(meas) - min(meas)) / r
    return None, None


def predict_army_cross_class(att: dict, dfn: dict, *, att_cls: str, def_cls: str,
                             n_att: float, n_def: float, tier: int) -> dict:
    """Army-scale outcome for a proc-free, hero-free SINGLE-class-vs-single-class
    matchup, same tier both sides. Continuum only (see the module docstring for
    why the discrete clock is not claimed).

    ABSTAINS (winner "uncertain") when the measured uncertainty in R could flip the
    winner -- i.e. when beta/alpha sits within the R measurement spread of 1.0.
    This is a DERIVED abstention band, not an arbitrary threshold: it is exactly the
    region where the evidence cannot distinguish the two outcomes. It is also what
    the near-parity anchor exp5 taught us -- at beta/alpha = 0.9976 a 2.5% error in
    R became a 149% error in the survivor fraction, so a confident answer there
    would be dishonest.
    """
    if tier != R_MEASURED_TIER and att_cls != def_cls:
        return {"winner": "uncertain", "reason": f"cross-class R measured only at "
                f"tier {R_MEASURED_TIER}, asked for tier {tier}"}
    R, R_unc = class_pair_R(att_cls, def_cls)
    if R is None:
        return {"winner": "uncertain", "reason": f"unmeasured class pair "
                f"{att_cls}->{def_cls}"}
    alpha, beta = rates(att, dfn)
    ba = (beta / alpha) * R
    # Phase A (2026-07-28): near-parity is no longer a hard abstention. The
    # measured log-ratio error (winprob_calibrated: sigma = 0.0197) turns the
    # margin into a CONTINUOUS win probability, which is the honest expression of
    # "could the winner flip" -- better than refusing, and better than forcing a
    # coin flip. The flag below lets callers label it; the probability does the work.
    near_parity = bool(R_unc and abs(1.0 - ba) <= R_unc)
    if ba < 1.0:
        w, f, n = "attacker", math.sqrt(1.0 - ba), n_att
    else:
        w, f, n = "defender", math.sqrt(max(0.0, 1.0 - 1.0 / ba)), n_def
    return {"winner": w, "winner_fraction": f, "survivors": f * n,
            "alpha": alpha, "beta": beta, "beta_over_alpha": ba, "R": R,
            "R_uncertainty": R_unc, "near_parity": near_parity,
            "mode": "continuum-cross-class"}


def eff(panel_pct: dict, base: dict) -> dict:
    """effective = base x (1 + panel/100). Same-class same-tier matchups cancel
    `base`, so any consistent base works there."""
    return {k: base[k] * (1 + panel_pct[n] / 100.0)
            for k, n in (("A", "Attack"), ("D", "Defense"),
                         ("L", "Lethality"), ("H", "Health"))}


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import json as _json
    _tb = _json.load(open("docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json",
                          encoding="utf-8"))["flat_records"]

    def _base(cls, tier, fc=1):
        for r in _tb:
            if r["class"] == cls and r["tier"] == tier and r["fire_crystal_level"] == fc:
                return {"A": r["attack"], "D": r["defense"],
                        "L": r["lethality"], "H": r["health"]}

    P1A = {"Attack": 176.2, "Defense": 169.0, "Lethality": 109.7, "Health": 109.3}
    P1D = {"Attack": 174.3, "Defense": 153.0, "Lethality": 112.0, "Health": 108.7}
    P7A = {"Attack": 199.2, "Defense": 192.0, "Lethality": 119.7, "Health": 119.3}
    P7D = {"Attack": 189.1, "Defense": 167.2, "Lethality": 122.0, "Health": 118.7}
    TIER = 1                      # base cancels for a same-class mirror (verified T1==T10)
    b = _base("Infantry", TIER)
    c = law_rate_scale("Infantry", TIER)

    print("=" * 78)
    print("VALIDATION -- army-scale same-class backbone (rate from the FROZEN law, "
          f"c=1/(K*G)={c:.5f})")
    print("=" * 78)
    for name, PA, PD, na, nd, obs in (
            ("exp1  20k encampment mirror ", P1A, P1D, 20000, 20000, 0.24185),
            ("exp2   2k encampment mirror ", P1A, P1D, 2000, 2000, 0.24200),
            ("exp7  20k ALLIANCE-GARRISON ", P7A, P7D, 20000, 20000, 0.30215)):
        A, D = eff(PA, b), eff(PD, b)
        dd = predict_army_same_class(A, D, n_att=na, n_def=nd, rate=c)
        cc = predict_army_same_class(A, D, n_att=na, n_def=nd, discrete=False)
        print(f"  {name} observed {obs:.5f}")
        print(f"     discrete  {dd['winner']:8} {dd['winner_fraction']:.5f} "
              f"({dd['turns']:>4} turns) err {((dd['winner_fraction']-obs)/obs):+7.2%}"
              f"   | continuum {cc['winner_fraction']:.5f} err "
              f"{((cc['winner_fraction']-obs)/obs):+7.2%}")
    print()
    print("  => exp1/exp2 (alliance-FREE) fit within OCR noise. exp7 (alliance garrison)")
    print("     is +9% on BOTH forms, so it is NOT a discretisation artefact: it needs a")
    print("     ~2% defender-favouring correction. OPEN -- see STAGE8_1_FINDINGS.md.")
    print()
    print("SCALE + COST (same stats, N from 1e3 to 1e6; O(turns), never O(troops))")
    A, D = eff(P1A, b), eff(P1D, b)
    for n in (1000, 10000, 100000, 1000000):
        r = predict_army_same_class(A, D, n_att=n, n_def=n, rate=c)
        print(f"  N={n:>9,}: {r['winner']} frac={r['winner_fraction']:.5f} "
              f"turns={r['turns']} capped={r['capped']}")
    print("  (fraction constant across 3 orders of magnitude = the measured "
          "scale-invariance)")
