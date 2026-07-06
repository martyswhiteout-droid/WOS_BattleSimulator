"""Rally / Garrison battle skill-activation rules (confirmed with Martin, Jul 2026).

Scope: only EXPEDITION skills exist in this model. Exploration skills are
ignored entirely - the "Hero Skills" tab records expedition skills only.

Rule 1 - Captain (Rally Lead / Garrison Leader). The captain's march has one
hero of each class (Infantry, Lancer, Marksman). ALL of the captain's skills
activate: 3 heroes x 3 skills = 9 skills, plus all 3 widgets. Garrison defense
works identically to rallies.

Hero generation is a proxy for server age: a server starts at generation 1
and advances one generation every 100 days, so a ~600-day server implies
captains field generation 6-7 heroes. Older-generation and SR heroes are
never captain heroes - which is why the "Hero Skills" tab deliberately
records only Skill 1 for SR/legacy heroes (Jessie, Patrick, Sergey, ...):
their other skills would never be activated, per Rule 2.

Rule 2 - Joiners (rally or garrison reinforcements). Per joiner, only the
slot-1 (flag) hero matters, and only that hero's FIRST expedition skill.
Slots 2-3 contribute nothing; joiner widgets never activate. A rally holds
at most 4 joiner contributions - the game keeps the 4 highest-leveled
first-skills among all joiners (with max-level skills everywhere, join
order is the effective tiebreak). Duplicate flag heroes stack ADDITIVELY:
two Jessie flags = 2 x her Skill 1 amounts summed.
"""

from __future__ import annotations

from .models import CombatContext, SkillBook, SkillEffect, SkillSource, TroopType

GENERATION_DAYS = 100   # a server advances one hero generation per 100 days
MAX_ACTIVE_JOINERS = 4  # buff cap: contributions kept per rally/garrison
DEFAULT_SKILL_LEVEL = 5  # the workbook records max-level (level 5) amounts

# --- Battle turn structure (confirmed) -------------------------------------
# Turn-based; per turn each side's three troop types make one normal attack
# each (6 normal attacks per turn while all types are alive on both sides).
NORMAL_ATTACKS_PER_TURN = 6
# The attacker (rally) resolves all three attacks first, then the defender
# (garrison) retaliates:
ATTACK_SEQUENCE = (
    ("Attacker", TroopType.INFANTRY), ("Attacker", TroopType.LANCER),
    ("Attacker", TroopType.MARKSMAN),
    ("Defender", TroopType.INFANTRY), ("Defender", TroopType.LANCER),
    ("Defender", TroopType.MARKSMAN),
)
# Damage absorption order: all attacks hit Infantry while any Infantry lives,
# then Lancers, then Marksmen ...
ABSORPTION_ORDER = (TroopType.INFANTRY, TroopType.LANCER, TroopType.MARKSMAN)
# ... except Lancer attacks (Ambusher): 20% chance to strike Marksmen directly
# from turn 1, bypassing the front line. Ambusher is a SKILL that UNLOCKS at
# T7 - a T6 lancer does NOT have it (confirmed Martin 2026-07-04). Principle:
# a proc only exists if the skill is actually on the troop/hero panel; never
# assume one from the troop CLASS. Procs are gated by their real unlock tier.
LANCER_BYPASS_CHANCE = 0.20
AMBUSHER_MIN_TIER = 7      # Ambusher (lancer 20% bypass) unlocks at T7
CRYSTAL_LANCE_MIN_TIER = 11  # Crystal Lance is a Fire-Crystal skill (FC/T11+);
#   sub-T11 lancers have no Crystal Lance. Adjust if game data pins it tighter.
# Damage-scope convention: any effect described as plain "damage" applies to
# BOTH normal and skill damage; only effects explicitly scoped to "normal
# attack" or "skill damage" are category-restricted.
# Stat-layer rule (GAME_RULES 6, set-5): STATS-BASED hero stat skills are
# MULTIPLICATIVE - Prod(1+x), the skillmult factor in assemble.py; only
# CHANCE/TURN-based stat skills enter the additive standard pool (at their EV).
# Widget skills + buff items form the multiplicative special pool. Damage Dealt /
# Damage Taken are battle-only modifiers, not panel stats. See GAME_RULES.md.


def server_generation(server_age_days: int) -> int:
    """Current hero generation for a server of the given age in days."""
    return server_age_days // GENERATION_DAYS + 1


def viable_lead_generations(server_age_days: int) -> set[str]:
    """Generations a competitive captain is expected to field (gen, gen-1)."""
    gen = server_generation(server_age_days)
    return {str(gen), str(max(gen - 1, 1))}


def _in_context(effect: SkillEffect, battle: CombatContext | None) -> bool:
    """Whether an effect is active in the given battle context.

    Rally-scoped effects (mostly widgets) only apply in rallies, Garrison-
    scoped ones only in garrison defense; battle=None keeps everything.
    """
    if battle is None or battle == CombatContext.ALL:
        return True
    return effect.context in (CombatContext.ALL, battle)


def captain_effects(book: SkillBook, captain_heroes: list[str],
                    hero_classes: dict[str, TroopType] | None = None,
                    battle: CombatContext | None = None) -> list[SkillEffect]:
    """All activated effects for the captain: every skill + widget per hero.

    captain_heroes should be the 3 march heroes, one per class; pass
    hero_classes (name -> TroopType, e.g. from HeroRoster) to enforce that.
    Pass battle=CombatContext.RALLY or GARRISON to drop effects scoped to
    the other context (e.g. a Rally-only widget in a garrison defense).
    """
    if hero_classes is not None:
        classes = {hero_classes[h] for h in captain_heroes}
        if len(captain_heroes) != 3 or len(classes) != 3:
            raise ValueError(
                f"Captain march must be one hero of each class, got {captain_heroes}")
    effects: list[SkillEffect] = []
    for hero in captain_heroes:
        effects.extend(e for e in book.for_hero(hero) if _in_context(e, battle))
    return effects


def joiner_effects(book: SkillBook, joiners: list[list[str]],
                   first_skill_levels: list[int] | None = None,
                   battle: CombatContext | None = None) -> list[SkillEffect]:
    """Activated effects contributed by rally/garrison joiners.

    joiners is one hero-name list per joiner in join order, slot-1 (flag)
    hero first. Only the flag hero's Skill 1 can activate. The game keeps
    the MAX_ACTIVE_JOINERS highest-leveled first-skills; supply
    first_skill_levels (one per joiner, default all max level) to model
    that selection - join order breaks ties. Amounts stack additively, so
    the returned list keeps one entry per activation, duplicates included.
    """
    levels = first_skill_levels or [DEFAULT_SKILL_LEVEL] * len(joiners)
    if len(levels) != len(joiners):
        raise ValueError("first_skill_levels must have one entry per joiner")
    flagged = [(lineup[0], lvl) for lineup, lvl in zip(joiners, levels) if lineup]
    selected = sorted(range(len(flagged)), key=lambda i: -flagged[i][1])
    effects: list[SkillEffect] = []
    for i in sorted(selected[:MAX_ACTIVE_JOINERS]):
        flag_hero = flagged[i][0]
        effects.extend(e for e in book.for_hero(flag_hero)
                       if e.source == SkillSource.SKILL_1
                       and _in_context(e, battle))
    return effects


# Backwards-compatible aliases (rally and garrison share the same rules)
rally_lead_effects = captain_effects
rally_joiner_effects = joiner_effects
