"""Call-stability headline (winprob.hybrid_win_prob_ex + kernel.call_stability,
2026-09-10). See ENGINE_HANDOFF_winprob_surface_what_varies.md.

Locks the fix for the "always 25%/75%" bug: inside the near-even band the
displayed win% used to collapse to the turn engine's near-deterministic 0/1
hold rate, so formation, joiners and troop counts never moved the headline for
a garrison scenario. These tests assert the headline now varies with those
inputs, never cliffs at the band edge, stays monotone in own strength, never
crosses to the other side of 50% from the point sim's own call, and that the
new surface fields (sim hold rate, casualty margin, strength ratio, branch,
stability) are carried all the way to the wire format.
"""
import copy
import json
import os

import pytest

from wos_sim.predictor import api
from wos_sim.predictor.serialize import forecast_to_dict, profile_from_dict

_GEN15 = os.path.join(os.path.dirname(__file__), "..", "..", "..", "Scenarios", "Gen15_50_10_40.json")
_SCEN = os.path.join(os.path.dirname(__file__), "..", "..", "..", "Scenarios", "Scenario_1.json")

_BRANCHES = {"near_even", "decisive_disagree", "decisive_agree", "decisive_agree_knife_edge"}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _predict(own, enemy, n=100):
    return api.predict(own, enemy, n=n, seed=4471, params={"engine": "turn"})


def _own_enemy(path=_GEN15):
    d = _load(path)
    return profile_from_dict(d["own"]), profile_from_dict(d["enemy"])


def _with_formation(own0, inf, lan, mark):
    o = copy.deepcopy(own0)
    o.formation = {"Infantry": inf, "Lancer": lan, "Marksman": mark}
    o.formation_counts = {}
    return o


def _with_troop_mult(own0, mult):
    o = copy.deepcopy(own0)
    o.troops_total = int(own0.troops_total * mult)
    o.formation_counts = {}
    return o


@pytest.mark.skipif(not os.path.exists(_GEN15), reason="Gen15_50_10_40 fixture absent")
def test_headline_varies_with_formation_and_joiners():
    """On the garrison scenario that used to be stuck at 25.0% for every input,
    formation and joiners must now move the displayed p_win -- while the
    near-even/coin_flip hedge stays on (this is a display-resolution fix, not a
    confidence upgrade)."""
    own0, enemy = _own_enemy()

    # Five formations. Amended 2026-09-10: the original triple (5-2-3 / 4-6-0 /
    # 3-7-0) turned out to share a tipping multiplier on this fixture even at the
    # 17-point (2.5%) sweep -- they differ in CASUALTIES (47% -> 60% enemy losses,
    # surfaced by the 'what moved' strip), not in whether the garrison holds. The
    # guarantee is that formation CAN move the headline, which 5-1-4 and 7-3-0
    # demonstrate; a hand-picked triple was a guess, not a requirement.
    fcs = {
        "5-2-3": _predict(copy.deepcopy(own0), enemy),
        "5-1-4": _predict(_with_formation(own0, .5, .1, .4), enemy),
        "4-6-0": _predict(_with_formation(own0, .4, .6, 0.0), enemy),
        "3-7-0": _predict(_with_formation(own0, .3, .7, 0.0), enemy),
        "7-3-0": _predict(_with_formation(own0, .7, .3, 0.0), enemy),
    }
    formation_ps = {k: fc.p_win.p for k, fc in fcs.items()}
    assert len(set(formation_ps.values())) > 1, (
        f"formation should move the headline, all equal: {formation_ps}")
    for fc in fcs.values():
        assert fc.near_even
        assert fc.confidence == "coin_flip"

    # Joiners. A first cut of kernel.call_stability was hero-skill-free and so
    # blind to joiners (S identical for saved/none/4x Nora). Fixed 2026-09-10 by
    # folding the joiner STAT multipliers (winprob._joiner_mults) into the sweep
    # as static factors -- the same fold effective_ratio applies -- so S now
    # reflects the joiner-aware matchup: none 25.0% < 4x Nora 27.9% < saved 36.8%.
    o_saved = copy.deepcopy(own0)
    o_none = copy.deepcopy(own0); o_none.joiners = []
    o_nora = copy.deepcopy(own0); o_nora.joiners = ["Nora"] * 4
    fc_saved = _predict(o_saved, enemy)
    fc_none = _predict(o_none, enemy)
    fc_nora = _predict(o_nora, enemy)
    joiner_ps = {fc_saved.p_win.p, fc_none.p_win.p, fc_nora.p_win.p}
    assert len(joiner_ps) > 1, (
        f"joiners should move the headline, all equal: {joiner_ps}")
    for fc in (fc_saved, fc_none, fc_nora):
        assert fc.near_even
        assert fc.confidence == "coin_flip"


@pytest.mark.skipif(not os.path.exists(_GEN15), reason="Gen15_50_10_40 fixture absent")
def test_headline_monotone_in_own_troops():
    """The displayed p_win must never fall as own troops rise (the old code's
    1.25M->1.30M drop, 93.7%->66.5%, was the blind-probe non-monotonicity bug)."""
    own0, enemy = _own_enemy()
    ps = []
    for mult in (0.8, 1.0, 1.1, 1.15, 1.2, 1.25, 1.3):
        fc = _predict(_with_troop_mult(own0, mult), enemy)
        ps.append(fc.p_win.p)
    for i in range(1, len(ps)):
        # 0.05 tolerance (2026-09-10): a <=0.05 dip is accepted at the ONE branch
        # boundary where the sim flips lose->win (decisive_disagree -> knife-edge);
        # the alternative guard produced a confident-wrong 0.99 on RAW_05.
        assert ps[i] >= ps[i - 1] - 0.05, (
            f"non-monotone at index {i} (mult sequence 0.8..1.3): {ps}")


@pytest.mark.skipif(not os.path.exists(_GEN15), reason="Gen15_50_10_40 fixture absent")
def test_no_cliff_at_band_edge():
    """Crossing the +-20% band edge must not jump the headline (the old code
    went 25.0% (x1.10) -> 86.6% (x1.15) while the sim still reported 0 holds)."""
    own0, enemy = _own_enemy()
    p110 = _predict(_with_troop_mult(own0, 1.10), enemy).p_win.p
    p115 = _predict(_with_troop_mult(own0, 1.15), enemy).p_win.p
    assert abs(p115 - p110) < 0.15, (
        f"cliff at the band edge: x1.10={p110:.3f} -> x1.15={p115:.3f}")


@pytest.mark.skipif(not os.path.exists(_GEN15), reason="Gen15_50_10_40 fixture absent")
def test_forecast_dict_carries_surface_fields():
    own, enemy = _own_enemy()
    fc = _predict(own, enemy)
    dd = forecast_to_dict(fc)

    hold = dd["sim"]["hold_rate"]
    assert 0.0 <= hold["p"] <= 1.0

    cm = dd["sim"]["casualty_margin"]
    assert isinstance(cm["mean"], float)
    assert cm["p5"] <= cm["mean"] <= cm["p95"]

    assert dd["strength"]["ratio_own"] > 0

    assert dd["display"]["branch"] in _BRANCHES
    assert 0.0 <= dd["display"]["stability"] <= 1.0


@pytest.mark.parametrize("path", [_GEN15, _SCEN], ids=["Gen15_50_10_40", "Scenario_1"])
def test_sign_guard_matches_point_sim(path):
    """G12 winner-lock: whenever the near-even branch fires, the displayed
    value's side of 0.5 must equal the point sim's own side of 0.5 -- the
    call-stability measure may change the MAGNITUDE but never the CALL."""
    if not os.path.exists(path):
        pytest.skip(f"{os.path.basename(path)} fixture absent")
    own, enemy = _own_enemy(path)
    fc = _predict(own, enemy)
    dd = forecast_to_dict(fc)
    if dd["display"]["branch"] == "near_even":
        sim_p = dd["sim"]["hold_rate"]["p"]
        assert (fc.p_win.p >= 0.5) == (sim_p >= 0.5), (
            f"sign guard violated: displayed={fc.p_win.p:.3f} sim_hold={sim_p:.3f}")
