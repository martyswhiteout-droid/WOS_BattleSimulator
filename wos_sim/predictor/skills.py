"""Layer 1b — hero-skill resolution.

Turns a side's lead heroes + joiners into combat modifiers, reusing the
report-path machinery (``wos_sim.assemble`` + ``wos_sim.mechanics``) so the
profile path and the report path resolve skills IDENTICALLY.

  * Lead heroes (the captain trio): full skill kit via ``captain_effects``.
  * Joiners: Skill 1 only, rally-wide (top 4).
  * Widgets are included only when the side profile says the panel does not
    already contain widget stats.

Routing (``assemble._route_effect``) sorts each effect into the ModifierBoard:
  permanent stat skills -> MULTIPLICATIVE ``skillmult`` (GAME_RULES 6l);
  Damage-Dealt / Damage-Taken -> the ``dd`` / ``dt`` pools;
  enemy-side effects -> the foe's tag.
"""
from __future__ import annotations

from functools import lru_cache

from wos_sim.assemble import ModifierBoard, _dedupe_damage_category_splits, _route_effect
from wos_sim.loader import load_skill_book
from wos_sim.mechanics import captain_effects
from wos_sim.models import CombatContext, SkillAttribute, SkillMechanic, SkillSource


@lru_cache(maxsize=1)
def skill_book():
    """The workbook skill book (cached; 51 heroes / 506 effects)."""
    return load_skill_book()


def _widgets_in_panel(side) -> bool:
    if getattr(side, "panel_is_final", False):
        return True
    value = getattr(side, "widgets_in_panel", None)
    if value is not None:
        return bool(value)
    return getattr(side, "stats_mode", "scouted") == "scouted"


def _side_effects(side, book, context):
    """Active (effect, role) pairs for a side: lead trio kit, optional widgets,
    and each joiner's Skill 1. The role tag matters: panel-suppression applies
    only to CAPTAIN stat rows (a captain's stat skills show in the side's own
    scouted/final panel; a joiner is another player's hero, so its stat skills
    are never in this side's panel)."""
    effects = []
    lead = [h for h in side.lead_heroes.values() if h]
    if lead:
        rows = [
            e for e in captain_effects(book, lead, None, battle=context)
            if e.source != SkillSource.WIDGET or not _widgets_in_panel(side)
        ]
        effects.extend((e, "captain") for e in _dedupe_damage_category_splits(rows))
    seen = set()
    for flag in side.joiners[:4]:
        if not flag or flag in seen:
            # duplicate-joiner dedup: the same hero's Skill-1 applies once
            # (anchored on pvp_t12_report_005, the real 4x-Nora defeat).
            continue
        seen.add(flag)
        rows = [e for e in book.for_hero(flag) if e.source == SkillSource.SKILL_1]
        effects.extend((e, "joiner") for e in _dedupe_damage_category_splits(rows))
    return effects


def _final_panel_contains_own_stat_skill(side, effect) -> bool:
    return (
        getattr(side, "panel_is_final", False)
        and effect.side.value == "Friend"
        and effect.mechanic == SkillMechanic.STATS_BASED
        and effect.attribute in {
            SkillAttribute.ATTACK,
            SkillAttribute.DEFENSE,
            SkillAttribute.LETHALITY,
            SkillAttribute.HEALTH,
        }
    )


def resolve(own_side, enemy_side, own_tag, foe_tag,
            context=CombatContext.RALLY, board=None, book=None) -> ModifierBoard:
    """Route own_side's hero skills into a ModifierBoard under ``own_tag``
    (enemy-targeted effects land on ``foe_tag``). Returns the board."""
    book = book or skill_book()
    board = board or ModifierBoard()
    for e, role in _side_effects(own_side, book, context):
        if role == "captain" and _final_panel_contains_own_stat_skill(own_side, e):
            continue
        _route_effect(board, e, own_tag, foe_tag)
    return board
