"""Reduced-form PvP casualty kernel (E-11) - the CONTROLLED-LADDER result.

Derived from three controlled farm-ladders (v9 symmetric, v9b fixed-attacker,
v9c mirror; 8 unique count-pairs) via a design-panel workflow (4 kernel
families, adversarial leave-one-rung-out CV) + an independent refit. For a
battle the attacker WINS with the defender FULLY WIPED, the attacker's
infantry casualties follow a 2-parameter homogeneous law:

    survivors_total = (N_att^E - K * N_def^E) ** (1/E)
    att_inf_incap   = N_att - survivors_total        (all casualties are infantry)

with E = 1.4291 (homogeneity degree = own_exp - enemy_exp + 1) and
K = 0.1308 (the T10-attacker-vs-T7-defender strength ratio, kD/kA).

Equivalent per-turn kill-rate kernel that the turn-by-turn sim integrates:
    R_side = k * N_own * N_enemy^(ed-1),   ed = 3 - E = 1.5709
i.e. LINEAR in own live count, with a target-abundance exponent (ed-1)=0.571
on the ENEMY count (bigger enemy = more targets, sub-linear). NOTE this is the
opposite of a <1 "frontage cap": the super-linear defender scaling in the data
(casualties ~ N_def^1.45) forces ed>1.

VALIDATION: train log-RMSE 0.0286 (max abs err 5.6%), leave-one-rung-out CV
0.0400 - beats the plain OLS baseline's own CV (0.0434) with params rock-stable
across folds (ed CV 0.5%, K CV 0.6%). Winner of the derive-pvp-kernel workflow.

REGIME - do NOT extrapolate blindly (all 8 calibration points share this):
  * composition 50/50 infantry/marksman each side ONLY,
  * T10 attacker vs T7 defender ONLY (K bakes in this exact tier gap),
  * attacker wins & defender fully wiped ONLY (guard below flags otherwise),
  * no procs/RNG (deterministic mean; ~10-15% real per-battle variance).
Weakest calibration corner: very attacker-heavy (16k vs 6k) is +6..8% high.
"""

# identifiable casualty-law constants (TOTAL troops per side, 50/50 comp)
E_DEFAULT = 1.4291
K_DEFAULT = 0.1308
ED_DEFAULT = 3.0 - E_DEFAULT          # 1.5709, per-turn enemy target-abundance+1

# calibrated model error for THIS kernel in-regime (leave-one-rung-out CV
# log-RMSE 0.040, max abs 5.6%). Reported to the app so the honesty banner can
# say "+-4.5% validated" here vs the general engine's weaker band.
MODEL_ERROR = 0.045

# battle-duration estimate (COARSE): fit to the ladder's Bradley-proc proxy,
# turns ~= 4*procs. turns ~= C * N_att^a * N_def^b. Anchored on the mirror ladder
# (att 3k/6k/10k/16k vs 6k def -> ~27/16/12/8 turns). Ordinal, +-a few turns.
_TURN_C, _TURN_A, _TURN_B = 12.9, -0.673, 0.704


def attacker_casualties(n_att, n_def, E=E_DEFAULT, K=K_DEFAULT):
    """Predicted attacker INFANTRY incapacitated when rallying a T7 garrison
    with a T10 rally (both 50/50 inf/marks). `n_att`, `n_def` are TOTAL troops.

    Returns (casualties, attacker_wins). If the attacker's infantry wall would
    be breached (survivors fall below the marksman floor n_att/2), the attacker
    LOSES: casualties are capped at the infantry count and attacker_wins=False.
    That case is OUTSIDE the calibrated regime - treat as low-confidence."""
    inside = n_att ** E - K * n_def ** E
    marks = n_att / 2.0                # 50/50 => infantry == marks == n_att/2
    if inside <= 0:
        return marks, False            # attacker consumed before defender wiped
    surv = inside ** (1.0 / E)
    if surv - marks <= 0:
        return marks, False            # infantry wall breached -> attacker loses
    return n_att - surv, True


def loss_fraction(n_att, n_def, E=E_DEFAULT, K=K_DEFAULT):
    """Attacker infantry loss as a fraction of its infantry (n_att/2)."""
    cas, _ = attacker_casualties(n_att, n_def, E, K)
    return cas / (n_att / 2.0)


def battle_turns(n_att, n_def):
    """Coarse turn-count estimate for a garrison-wipe battle (ordinal, +-a few
    turns; derived from the ladder's Bradley-proc duration proxy)."""
    return max(1, round(_TURN_C * n_att ** _TURN_A * n_def ** _TURN_B))


def garrison_wipe_forecast(n_att, n_def, E=E_DEFAULT, K=K_DEFAULT):
    """One deterministic garrison-wipe outcome (attacker wins, defender fully
    wiped, all attacker casualties infantry). Returns
    (attacker_inf_casualties, attacker_wins, turns). If attacker_wins is False
    the matchup is OUTSIDE this kernel's validated regime - caller should fall
    back to the general engine."""
    cas, wins = attacker_casualties(n_att, n_def, E, K)
    return cas, wins, battle_turns(n_att, n_def)


def min_attacker_for_loss_cap(n_def, max_loss_frac, E=E_DEFAULT, K=K_DEFAULT,
                              hi=10_000_000):
    """Smallest TOTAL attacker army that keeps infantry loss <= max_loss_frac
    vs a T7 garrison of n_def. Bisection; returns None if unreachable."""
    lo, res = 1.0, None
    if loss_fraction(hi, n_def, E, K) > max_loss_frac:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if loss_fraction(mid, n_def, E, K) <= max_loss_frac:
            res, hi = mid, mid
        else:
            lo = mid
    return res


# the 8 controlled points (N_att_total, N_def_total, att_inf_incap) for self-test
_LADDER = [(4000, 3000, 244), (6000, 6000, 579), (10000, 10000, 966),
           (10000, 3000, 169), (10000, 6000, 447), (10000, 16000, 1835),
           (3000, 6000, 775), (16000, 6000, 343)]


def _self_test():
    print("pvp_kernel self-test (E=%.4f, K=%.4f, ed=%.4f)" %
          (E_DEFAULT, K_DEFAULT, ED_DEFAULT))
    worst = 0.0
    for na, nd, obs in _LADDER:
        pred, win = attacker_casualties(na, nd)
        pct = 100 * (pred - obs) / obs
        worst = max(worst, abs(pct))
        print(f"  ({na:5d},{nd:5d}) obs {obs:5d} pred {pred:6.0f} "
              f"({pct:+5.1f}%) win={win}")
    print(f"  max abs err {worst:.1f}%  (expect <=5.7%)")
    assert worst < 6.0, "kernel regressed"
    print("  OK")


if __name__ == "__main__":
    _self_test()
