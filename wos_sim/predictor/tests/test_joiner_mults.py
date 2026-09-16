"""winprob._joiner_mults -- Damage-Taken channel composition (QA fix, 2026-09-16).

Before this fix, _joiner_mults resolved a single JOINER skill's multiple
Damage-Taken rows by keeping whichever row had the largest |amount|,
regardless of which damage CHANNEL (Normal vs Skills vs Both) it applied to.
That overstated toughness whenever a skill's biggest reduction lived on the
Skills channel: Wu Ming S1 (-25% Normal, -30% Skills) folded as the -30% row
even though Wu Ming deals ordinary Normal damage every turn, not Skills
damage -- at 3 copies that was (1/0.70)**3 instead of the physically correct
(1/0.75)**3, a ~23% overstatement that alone lifted a near-even garrison to a
75% headline.

The fix: within one skill, a Normal hit is reduced by every row whose
category is Normal OR Both (they compound with each other -- a Both row
applies to every hit, so it stacks with a Normal row on the same skill); a
Skills-only row is used only as a FALLBACK when the skill has no Normal/Both
row at all for that (target, class). This mirrors the engine's own channel
split (pvp_turn_engine._stack_view / TURN_PARAMS) and the DT experiment's
measurement (wos_sim/formula_research/EXPERIMENT_DT_STACKING.md s.8): normal
attacks are the default channel, so the display's strength proxy follows it.
"""
import json
import os

import pytest

from wos_sim.models import (
    AffectingSide,
    CombatContext,
    DamageCategory,
    EffectReceiver,
    SkillAttribute,
    SkillCategory,
    SkillEffect,
    SkillMechanic,
    SkillSource,
)
from wos_sim.predictor import construct, winprob
from wos_sim.predictor.profiles import Matchup
from wos_sim.predictor.serialize import profile_from_dict
from wos_sim.pvp_turn_engine import SkillDef, skill_defs_from_matchup

_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
_GEN15_RALLY_WM = os.path.join(_ROOT, "Scenarios", "Gend15", "Gen15_Rally_WM.json")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dt_row(amount, category, receiver=EffectReceiver.INFANTRY,
           side=AffectingSide.FRIEND):
    """Minimal real SkillEffect row exercising only the fields _joiner_mults
    reads (attribute/side/receiver/amount/damage_category); every other
    column is irrelevant to a Damage-Taken passive row."""
    return SkillEffect(
        hero="Synthetic", source=SkillSource.SKILL_1, context=CombatContext.ALL,
        side=side, receiver=receiver, attribute=SkillAttribute.DAMAGE_TAKEN,
        amount=amount, mechanic=SkillMechanic.STATS_BASED,
        damage_category=category, category=SkillCategory.DAMAGE_TAKEN,
    )


def _joiner_skill(*rows, side="attacker", owner="Synthetic"):
    return SkillDef(owner=owner, side=side, slot="skill_1", role="joiner",
                    troop=None, rows=rows)


@pytest.mark.skipif(not os.path.exists(_GEN15_RALLY_WM), reason="Gen15_Rally_WM fixture absent")
def test_three_wu_ming_tough_multiplier_follows_normal_channel():
    """3x Wu Ming S1 on Gen15_Rally_WM's garrison Infantry must fold as
    (1/0.75)**3 -- the Normal-channel product -- not the old strongest-|amount|
    rule's (1/0.70)**3 (which picked the Skills -30% row over the Normal
    -25% row).

    The fixture's enemy joiners are cleared: the stock enemy lineup (Nora,
    Jessie, Blanchette, Hendrik) includes Hendrik's real "Foe Infantry
    Defense -25%" row, which folds into the SAME mult[defender][Infantry]
    [tough] bucket through the ordinary (non-DT) stat path and would
    otherwise confound this test's isolation of Wu Ming's DT-channel
    composition -- that contribution is real game data, untouched by this
    fix, and is exercised on its own by the other tests in this module."""
    d = _load(_GEN15_RALLY_WM)
    own = profile_from_dict(d["own"])
    own.joiners = ["Wu Ming"] * 3
    enemy = profile_from_dict(d["enemy"])
    enemy.joiners = []
    con = construct.build(Matchup(own, enemy), apply_legacy_skills=False)
    # own is the garrison in this fixture, so it maps to the "defender" side key.
    assert con.own_is_attacker is False, "expected own (garrison) to map to defender"
    mult = winprob._joiner_mults(skill_defs_from_matchup(con))
    expected = (1.0 / 0.75) ** 3
    assert mult["defender"]["Infantry"]["tough"] == pytest.approx(expected, abs=1e-9)


def test_skills_only_row_is_a_fallback_when_no_normal_or_both_row_exists():
    """A synthetic skill whose only DT row is Skills-category -30% (no
    Normal/Both row at all) must fall back to the Skills channel: 1/0.70."""
    skill = _joiner_skill(_dt_row(-0.30, DamageCategory.SKILLS))
    mult = winprob._joiner_mults([skill])
    assert mult["attacker"]["Infantry"]["tough"] == pytest.approx(1.0 / 0.70, abs=1e-9)


def test_normal_and_both_rows_on_one_skill_compound_with_each_other():
    """Normal -10% and Both -20% on the same class in ONE skill both apply to
    a normal hit, so they DO compound: 1/(0.9*0.8) (the latent Both+Normal
    case the old strongest-row rule also got wrong)."""
    skill = _joiner_skill(
        _dt_row(-0.10, DamageCategory.NORMAL),
        _dt_row(-0.20, DamageCategory.BOTH),
    )
    mult = winprob._joiner_mults([skill])
    expected = 1.0 / (0.9 * 0.8)
    assert mult["attacker"]["Infantry"]["tough"] == pytest.approx(expected, abs=1e-9)


def test_normal_row_present_ignores_a_sibling_skills_row_on_the_same_skill():
    """The exact Wu Ming shape in isolation: one skill with BOTH a Normal
    -25% row and a Skills -30% row must use only the Normal row (1/0.75), not
    the Skills row and not both multiplied together -- a hit is either a
    Normal hit or a Skills hit, never both, so once a Normal/Both row exists
    the Skills-only row for the same skill is inert."""
    skill = _joiner_skill(
        _dt_row(-0.25, DamageCategory.NORMAL),
        _dt_row(-0.30, DamageCategory.SKILLS),
    )
    mult = winprob._joiner_mults([skill])
    assert mult["attacker"]["Infantry"]["tough"] == pytest.approx(1.0 / 0.75, abs=1e-9)


def test_multiple_copies_of_the_same_joiner_still_stack_multiplicatively():
    """Copies of the same joiner remain separate SkillDefs, so the per-skill
    Normal-channel factor still stacks multiplicatively across copies
    (unchanged by this fix) -- 3 independent -25%-Normal skills fold as
    (1/0.75)**3, same shape as the real Wu Ming case."""
    skills = [_joiner_skill(_dt_row(-0.25, DamageCategory.NORMAL)) for _ in range(3)]
    mult = winprob._joiner_mults(skills)
    expected = (1.0 / 0.75) ** 3
    assert mult["attacker"]["Infantry"]["tough"] == pytest.approx(expected, abs=1e-9)
