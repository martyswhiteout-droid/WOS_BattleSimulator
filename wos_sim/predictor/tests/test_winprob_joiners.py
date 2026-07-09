"""Joiner-aware displayed win probability (winprob.py, Martin 2026-07-09).

Locks the two user-facing guarantees:
  1. A near-mirror is a coin flip -> ~50%, NOT 100%.
  2. Joiners move the odds -> 0-vs-4 joiners is an underdog (~10%), and the raw
     turn-engine winner alone would (wrongly) still say 100%.
"""
import copy
import json
import os

import pytest

from wos_sim.predictor import api
from wos_sim.predictor.serialize import profile_from_dict

_SCEN = os.path.join(os.path.dirname(__file__), "..", "..", "..", "Scenarios", "Scenario_1.json")


def _load():
    with open(_SCEN) as f:
        return json.load(f)


def _predict(own_d, enemy_d):
    return api.predict(profile_from_dict(own_d), profile_from_dict(enemy_d),
                       n=40, seed=4471, params={"engine": "turn"})


@pytest.mark.skipif(not os.path.exists(_SCEN), reason="Scenario_1 fixture absent")
def test_no_joiners_vs_four_is_an_underdog_not_a_coinflip():
    """own 0 joiners vs enemy 4: the joiner deficit must drag the win% well below
    50% (was a false 100% before joiners entered the probability)."""
    d = _load()
    fc = _predict(d["own"], d["enemy"])         # own 0 joiners, enemy 4
    assert fc.p_win.p < 0.25, f"0-vs-4 joiners should be an underdog, got {fc.p_win.p:.2f}"
    assert not fc.near_even                       # a 4-joiner gap is NOT a coin flip


@pytest.mark.skipif(not os.path.exists(_SCEN), reason="Scenario_1 fixture absent")
def test_symmetric_joiners_reads_as_coin_flip():
    """Equal joiners on a near-mirror -> flagged coin flip and displayed ~50%
    (a hair off only because the panels differ), never a confident 100%."""
    d = _load()
    own = copy.deepcopy(d["own"])
    own["joiners"] = list(d["enemy"]["joiners"])   # match the enemy's 4
    fc = _predict(own, d["enemy"])
    assert fc.near_even
    assert 0.40 <= fc.p_win.p <= 0.60, f"near-mirror should read ~50%, got {fc.p_win.p:.2f}"


@pytest.mark.skipif(not os.path.exists(_SCEN), reason="Scenario_1 fixture absent")
def test_joiners_strictly_improve_own_win_probability():
    """Adding your own joiners must raise your win% (proves joiners are no longer
    invisible to the probability)."""
    d = _load()
    base = _predict(d["own"], d["enemy"]).p_win.p           # own 0 joiners
    own4 = copy.deepcopy(d["own"])
    own4["joiners"] = list(d["enemy"]["joiners"])
    with4 = _predict(own4, d["enemy"]).p_win.p              # own 4 joiners
    assert with4 > base + 0.10, f"4 joiners should lift win% materially: {base:.2f} -> {with4:.2f}"
