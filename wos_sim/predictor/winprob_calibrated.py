"""Phase A (2026-07-28) -- the DISPLAYED win probability, from measured quantities.

Replaces the fixed 0.55/0.45 near-even damping in winprob.py (which encoded one
bit: which side the engine picked) with numbers that come from real battles.
Constants live in winprob_calibration.json, emitted by
`py -m wos_sim.formula_research.calibrate_winprob` (re-run after engine changes).

ARMY-LAW path -- continuous, derived:
    P(attacker wins) = Phi(-mu / sigma)
    mu    = ln(beta/alpha * R)        attacker wins iff mu < 0
    sigma = RMS of the leave-one-out residuals of ln(beta/alpha) over the nine
            deterministic army anchors  (0.0197; the MEASURED model error)
  This is the probability that the law's winner call survives its own measured
  error. A decisive battle reads 99%+; a near-parity one reads ~60-80%.

TURN-ENGINE path -- THREE honest negative results, and where the number came from.
  Three separate attempts to make this number margin-sensitive all failed:
    1. P(call correct | |ln r|) = logistic(a + b|ln r|)  ->  b = 0.
    2. P(own wins)  = logistic(k * signed margin)        ->  k = 0.019 (13-battle
       golden subset: k = 0.000), sign accuracy 12/22, and the folded leave-one-out
       Brier 0.263 is WORSE than a constant's 0.198.
    3. Driving the near-even branch from the strength sigmoid instead of the sim
       ->  the winner call degrades from 15/20 to 11/20. (winprob.py's docstring
       had already recorded the same result on the 13 golden battles: 5/13 vs 7/13.)
  So the joiner-aware strength margin genuinely does not predict this engine's
  correctness, and the display rule keeps the SIM's side. What is measured is the
  near-even ACCURACY, 15/20 = 0.750, which lives in winprob.NEAR_EVEN_HIT_RATE and
  replaced the chosen DAMP = 0.10 (that constant pinned every near-even battle to
  exactly 0.55/0.45 -- and 20 of the 22 labelled battles are near-even, so it was
  the whole product).

  NOT USED FOR DISPLAY: turn_engine_confidence() below is retained as the measured
  fit, but api.py must NOT apply it battle-by-battle. An earlier cut did, and it
  flattened the DECISIVE branch too -- expX2, a 2.3x rout, displayed 0.727.

  OPEN (do not fit): across the 20 near-even battles the 5 misses all sit FAR from
  parity (lambda 0.35-1.00) while the 12 nearest parity are 12/12 correct. That is
  the structural garrison upset -- the sim over-trusts a paper advantage. It points
  the OPPOSITE way to intuition, and on a post-hoc split of 20 points it is not
  significant (p ~ 0.03 with a chosen cut). It needs more labelled battles before
  it may shape the number.
"""
from __future__ import annotations

import json
import math
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "winprob_calibration.json")
_CAL = None


def calibration() -> dict:
    global _CAL
    if _CAL is None:
        with open(_PATH, encoding="utf-8") as f:
            _CAL = json.load(f)
    return _CAL


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def army_law_p_attacker(ln_beta_over_alpha: float) -> float:
    """P(attacker wins) under the law's measured log-ratio error."""
    sigma = calibration()["army_law"]["sigma_ln_beta_over_alpha"]
    return _phi(-ln_beta_over_alpha / sigma)


def turn_engine_confidence(abs_ln_margin: float) -> float:
    """P(the turn engine's winner call is correct), floored at 0.5 (a call is
    never reported as less likely than a coin flip to be right).

    Measured, but NOT the display rule -- see the module docstring. Applying this
    per battle flattens decisive routs onto the average. Kept so the fit stays
    visible and re-checkable."""
    c = calibration()["turn_engine"]
    return max(0.5, 1.0 / (1.0 + math.exp(-(c["a"] + c["b"] * abs_ln_margin))))


def turn_engine_summary(near_even: bool = True) -> str:
    """The user-facing provenance line. Must describe the rule api.py ACTUALLY
    applies: near-even -> measured near-even accuracy; decisive -> the sim's call."""
    from . import winprob
    if near_even:
        n = calibration()["turn_engine"]["n_battles"]
        return (f"win% = this engine's measured accuracy on near-even battles "
                f"({winprob.NEAR_EVEN_HIT_RATE:.0%}, from {n} labelled real battles), "
                f"not a fixed 55/45")
    return "win% = the simulation's own margin; this battle is not near-even"
