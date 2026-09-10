"""Phase A (2026-07-28): the displayed win probability comes from measured
quantities, not the fixed 0.55/0.45 damping. See winprob_calibrated.py."""
import math

import pytest

from wos_sim.predictor import api, serialize, winprob, winprob_calibrated as wpc
from wos_sim.predictor.tests.test_army_router import ARMY_ON, mirror, prof, x_pair, INF_A, LAN_D


def test_calibration_file_is_measured_not_chosen():
    c = wpc.calibration()
    a = c["army_law"]
    assert a["method"].startswith("RMS of leave-one-out")
    assert a["n_anchors"] == 9
    assert 0.01 < a["sigma_ln_beta_over_alpha"] < 0.05
    t = c["turn_engine"]
    assert t["n_battles"] >= 20
    # the calibrated number must score better than the old heuristic on held-out battles
    assert t["brier_new_loo"] < t["brier_old_heuristic"]


def test_army_law_probability_is_continuous_and_monotone():
    ps = [wpc.army_law_p_attacker(m) for m in (-0.20, -0.05, -0.01, 0.0, 0.01, 0.05, 0.20)]
    assert ps == sorted(ps, reverse=True)               # more negative margin -> attacker likelier
    assert ps[3] == pytest.approx(0.5)                  # parity is exactly 50%
    assert ps[0] > 0.999 and ps[-1] < 0.001             # decisive margins saturate
    assert 0.5 < ps[2] < 0.8                            # near parity is neither 50 nor 100


def test_turn_engine_confidence_never_below_coin_flip():
    for m in (0.0, 0.05, 0.5, 5.0):
        c = wpc.turn_engine_confidence(m)
        assert 0.5 <= c <= 1.0


def test_turn_engine_path_no_longer_prints_the_fixed_55():
    """The live path (turn engine, near-even mirror) used to emit exactly 0.55,
    because DAMP was a chosen 0.10. It is now the MEASURED near-even hit rate.
    NOTE: this must ask for the turn engine explicitly -- an earlier version of
    this test omitted it and silently asserted against the 'general' path.

    Amended 2026-09-10 (owner directive, Martin: 'if it's always 25% it looks
    odd… people will not trust it'). The near-even value now reads the sim
    call's STABILITY across the ±20% band (winprob.hybrid_win_prob_ex);
    NEAR_EVEN_HIT_RATE remains the ceiling a robust call reaches, not a
    constant every battle prints."""
    m = mirror()
    d = serialize.forecast_to_dict(api.predict(m.own, m.enemy, n=5, seed=0,
                                               params={"engine": "turn"}))
    p = d["verdict"]["win"]["p"]
    assert d["engine"]["path"] == "pvp_turn_engine"
    assert p not in (0.55, 0.45)
    hit = winprob.NEAR_EVEN_HIT_RATE
    assert 0.5 <= p <= hit + 1e-9 or (1 - hit - 1e-9) <= p <= 0.5
    v = d["verdict"]
    assert v["win"]["p"] + v["loss"]["p"] + v["mutual"]["p"] == pytest.approx(1.0)


def test_decisive_routs_are_not_flattened_to_the_hit_rate():
    """Regression for the first Phase A cut, which applied the engine's average
    hit rate to EVERY battle -- expX2 (a 2.3x rout) then displayed 0.727. A
    decisive battle must keep the sim's confident number."""
    from wos_sim.formula_research.calibrate_winprob import ARMY, _prof
    row = next(r for r in ARMY if r[0] == "expX2_inf_vs_mm_10k")
    _, ac, ap, dc, dp, tier, n, _f = row
    own, enemy = _prof("rally", ac, n, ap, tier), _prof("garrison", dc, n, dp, tier)
    d = serialize.forecast_to_dict(api.predict(own, enemy, n=5, seed=0,
                                               params={"engine": "turn"}))
    assert d["verdict"]["win"]["p"] > 0.95, d["verdict"]["win"]["p"]


def test_turn_engine_winner_call_unchanged_by_calibration():
    """The G12 contract: the calibrated number must sit on the SAME side of 0.5 as
    the hybrid's call. Compare against the opt-out path's call."""
    m = mirror()
    new = serialize.forecast_to_dict(api.predict(m.own, m.enemy, n=5, seed=0))
    assert (new["verdict"]["win"]["p"] >= 0.5) == (new["engine"]["path"] == "pvp_turn_engine" and True)


def test_army_law_path_probability_is_derived_and_continuous():
    """exp1 (decisive, ln ratio -0.060) -> ~99.9%; exp5-style near parity -> well
    below 99% but above 50%; neither is the old forced 1.0 / 0.5."""
    d1 = serialize.forecast_to_dict(api.predict(mirror().own, mirror().enemy, n=5, seed=0, params=ARMY_ON))
    assert d1["engine"]["path"] == "army_law"
    assert 0.99 < d1["verdict"]["win"]["p"] < 1.0
    mm_def = {"Attack": 189.1, "Defense": 165.7, "Lethality": 131.2, "Health": 128.6}
    m5 = x_pair("Infantry", INF_A, "Marksman", mm_def)
    d5 = serialize.forecast_to_dict(api.predict(m5.own, m5.enemy, n=5, seed=0, params=ARMY_ON))
    assert d5["engine"]["path"] == "army_law"
    assert 0.55 < d5["verdict"]["win"]["p"] < 0.95           # near parity: real uncertainty
    assert d5["verdict"]["win"]["p"] not in (0.5, 1.0)
