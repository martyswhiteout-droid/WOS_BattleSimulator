from .dataset import discover_nanomart
from .evaluate import deepseek_equation_checks
from .models import DeepSeekPublishedModel, DeepSeekRepairedHPModel


def _battle(prefix: str):
    return next(
        record
        for record in discover_nanomart()
        if record.included and record.report_id.startswith(prefix)
    )


def test_deepseek_constants_solve_none_of_the_claimed_equations():
    checks = deepseek_equation_checks()
    assert len(checks) == 5
    assert not any(check["matches"] for check in checks)


def test_published_hp_loop_cannot_reproduce_t1_infantry_clock():
    battle = _battle("NanoMart_1v1_T1InfvT1Inf")
    result = DeepSeekPublishedModel().simulate(battle)
    assert result.turns != 264


def test_repaired_hp_loop_cannot_reproduce_t1_lancer_clock():
    battle = _battle("NanoMart_1v1_T1LanvT1Lan")
    result = DeepSeekRepairedHPModel().simulate(battle)
    assert not (battle.turns_min <= result.turns <= battle.turns_max)
