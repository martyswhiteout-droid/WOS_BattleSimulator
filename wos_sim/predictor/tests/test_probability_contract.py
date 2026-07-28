"""The serialized outcome distribution must be a VALID probability distribution.

QA 2026-07-25 (P2 live / P1 before re-enabling the army law): whenever
`win_prob_override` is supplied, `p_loss`/`p_mutual` kept their raw Monte-Carlo
values, so the mass no longer summed to 1 -- the LIVE turn-engine path serialized
0.55 + 0 + 0 = 0.55 to every direct API consumer. (The front-end hid it by deriving
loss as the complement itself.) These tests pin the contract at 0 / 0.5 / 1.
"""
import pytest

from wos_sim.predictor.kernel import RunRecord
from wos_sim.predictor.summary import summarize
from wos_sim.models import TroopType

INF = TroopType.INFANTRY


def _records(n, own_wins, own_is_attacker=True):
    tag = "A" if own_is_attacker else "D"
    other = "D" if own_is_attacker else "A"
    out = []
    for i in range(n):
        w = tag if i < own_wins else other
        out.append(RunRecord(winner=w, turns=10,
                             attacker_start={INF: 1000}, defender_start={INF: 1000},
                             attacker_incap={INF: 500}, defender_incap={INF: 500}))
    return out


@pytest.mark.parametrize("override", [0.0, 0.45, 0.5, 0.55, 1.0])
def test_override_keeps_the_distribution_normalized(override):
    fc = summarize(_records(20, 20), own_is_attacker=True,
                   win_prob_override=override)
    total = fc.p_win.p + fc.p_loss.p + fc.p_mutual.p
    assert total == pytest.approx(1.0, abs=1e-9), (
        f"override={override} -> win {fc.p_win.p} + loss {fc.p_loss.p} "
        f"+ mutual {fc.p_mutual.p} = {total}")


@pytest.mark.parametrize("override", [0.0, 0.5, 1.0])
def test_override_effective_probabilities_also_sum_to_one(override):
    fc = summarize(_records(20, 20), own_is_attacker=True,
                   win_prob_override=override)
    assert fc.p_win_effective + fc.p_loss_effective == pytest.approx(1.0, abs=1e-9)


def test_override_is_reported_verbatim():
    fc = summarize(_records(20, 20), own_is_attacker=True, win_prob_override=0.45)
    assert fc.p_win.p == pytest.approx(0.45)


def test_without_override_the_raw_distribution_is_untouched():
    """No override -> the Monte-Carlo proportions must be reported as-is."""
    fc = summarize(_records(20, 13), own_is_attacker=True)
    assert fc.p_win.p == pytest.approx(13 / 20)
    assert fc.p_loss.p == pytest.approx(7 / 20)
    assert fc.p_win.p + fc.p_loss.p + fc.p_mutual.p == pytest.approx(1.0)
