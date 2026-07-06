"""Canonical troop data snapshot from wostools.net.

Sources: wostools.net/wiki/troops/{infantry,lancers,marksmen}.
- BASE tier tables T1-T11 (_TIER_ROWS): cross-checked EXACT vs the wiki for all
  three classes (Martin re-confirmed 2026-07-04). troop_base_stats serves every
  tier T1-T12 (T1-T9 = base, no FC; T10/T11 = FC ladder; T12 = T11 FC +3).
- Fire-Crystal ladders (_FC_ROWS): T10 and T11 at FC0-10; T11 FC9/FC10 verified
  against the workbook "Troop Stats" tab exactly.
"""

from __future__ import annotations

from .models import SkillAttribute, StatType, TroopSkill, TroopType

# Full Fire Crystal tables, wostools.net. (tier, fc, class) -> (Atk, Def, Leth, HP).
# Troop tier config is PER PLAYER (a joiner can bring FC10 T11 Infantry and
# FC9 T10 Lancers); T12 to be added when released.
_FC_ROWS: dict[tuple[int, TroopType], list[tuple[int, int, int, int]]] = {
    # index = FC level 0..10
    (10, TroopType.INFANTRY): [
        (10, 13, 10, 15), (11, 14, 10, 16), (12, 16, 11, 17), (13, 17, 12, 18),
        (13, 18, 13, 19), (14, 20, 13, 20), (14, 21, 13, 21), (15, 22, 14, 22),
        (15, 23, 15, 23), (16, 25, 15, 24), (18, 26, 16, 25)],
    (11, TroopType.INFANTRY): [
        (12, 15, 12, 17), (13, 16, 12, 18), (14, 17, 13, 19), (15, 18, 14, 20),
        (15, 19, 15, 21), (16, 22, 15, 22), (17, 23, 16, 23), (17, 24, 16, 24),
        (18, 25, 17, 25), (18, 27, 17, 26), (19, 28, 18, 27)],
    (10, TroopType.LANCER): [
        (13, 11, 14, 11), (14, 12, 15, 11), (16, 13, 16, 12), (17, 14, 17, 13),
        (18, 14, 18, 13), (20, 15, 19, 14), (21, 15, 20, 14), (22, 16, 21, 15),
        (23, 17, 22, 15), (25, 17, 23, 16), (26, 19, 24, 17)],
    (11, TroopType.LANCER): [
        (15, 13, 16, 13), (16, 14, 17, 13), (18, 15, 18, 14), (19, 16, 19, 15),
        (20, 16, 20, 15), (22, 17, 21, 16), (23, 18, 22, 16), (24, 18, 23, 17),
        (25, 19, 24, 17), (27, 19, 25, 18), (28, 21, 26, 20)],
    (10, TroopType.MARKSMAN): [
        (14, 10, 15, 10), (15, 11, 16, 11), (17, 12, 17, 12), (18, 13, 18, 13),
        (19, 14, 19, 13), (21, 14, 20, 14), (22, 15, 21, 14), (23, 15, 22, 15),
        (24, 16, 23, 15), (26, 17, 24, 16), (27, 19, 25, 17)],
    (11, TroopType.MARKSMAN): [
        (16, 12, 17, 12), (17, 13, 18, 13), (19, 14, 19, 14), (20, 15, 20, 15),
        (21, 16, 21, 15), (23, 16, 22, 16), (24, 17, 23, 16), (25, 18, 24, 17),
        (26, 19, 25, 18), (28, 19, 26, 18), (30, 21, 27, 20)],
}


def troop_base_stats(tier: int, fc_level: int,
                     troop: TroopType) -> dict[StatType, int]:
    """Base combat stats for a troop config, for ANY tier T1-T12.

    - T1-T9: base tier stats (no Fire Crystal), from _TIER_ROWS; fc_level is
      IGNORED - sub-T10 troops have no FC ladder. (This is the fix for the
      predictor construct hitting a KeyError on e.g. a T6 lancer.)
    - T10, T11: the Fire-Crystal ladder in _FC_ROWS, indexed by fc_level 0-10.
    - T12 "Exalted" (wostools, Apr-2026): T11 at the SAME FC level +3 per combat
      stat (exact for Infantry; Lancer/Marksman derived). Power 178 uniform.

    All T1-T11 BASE tiers cross-checked exact vs the wostools wiki
    (Martin 2026-07-04); T11 FC9/FC10 also match the workbook "Troop Stats" tab.
    """
    if tier == 12:
        base = troop_base_stats(11, fc_level, troop)
        return {stat: v + 3 for stat, v in base.items()}
    if (tier, troop) in _FC_ROWS:                       # T10/T11: FC ladder
        if not 0 <= fc_level <= 10:                     # fail closed (no neg-index)
            raise ValueError(f"fc_level {fc_level} out of range (expected 0-10)")
        atk, dfn, leth, hp = _FC_ROWS[(tier, troop)][fc_level]
    elif 1 <= tier <= 11:                               # T1-T9: base tier, no FC
        atk, dfn, leth, hp = _TIER_ROWS[troop][tier - 1]
    else:
        raise ValueError(f"tier {tier} out of range (expected 1-12)")
    return {StatType.ATTACK: atk, StatType.DEFENSE: dfn,
            StatType.LETHALITY: leth, StatType.HEALTH: hp}


# Base (non-FC) tier tables T1-T11 from the wostools troop pages: (Atk, Def, Leth, HP).
# CONFIRMED EXACT vs the wiki for ALL three classes (Martin, 2026-07-04); the
# earlier "Marksman T7-T9 provisional" flag is CLEARED - those values were right.
# Power per tier is uniform across classes EXCEPT T3 (wiki: Infantry 6 but
# Lancer/Marksman 5); kept uniform=6 here - T3 never appears in a real battle,
# negligible for the calibrated self-durability throttle.
TIER_POWER = {1: 3, 2: 4, 3: 6, 4: 9, 5: 13, 6: 20, 7: 28, 8: 38, 9: 50, 10: 66, 11: 80, 12: 178}
_TIER_ROWS: dict[TroopType, list[tuple[int, int, int, int]]] = {
    TroopType.INFANTRY: [  # T1..T11
        (1, 4, 1, 6), (2, 5, 2, 7), (3, 6, 3, 8), (4, 7, 4, 9), (5, 8, 5, 10),
        (6, 9, 6, 11), (7, 10, 7, 12), (8, 11, 8, 13), (9, 12, 9, 14),
        (10, 13, 10, 15), (12, 15, 12, 17)],
    TroopType.LANCER: [
        (4, 2, 5, 2), (5, 3, 6, 3), (6, 4, 7, 4), (7, 5, 8, 5), (8, 6, 9, 6),
        (9, 7, 10, 7), (10, 8, 11, 8), (11, 9, 12, 9), (12, 10, 13, 10),
        (13, 11, 14, 11), (15, 13, 16, 13)],
    TroopType.MARKSMAN: [
        (5, 1, 5, 1), (6, 2, 7, 2), (7, 3, 8, 3), (8, 4, 9, 4), (9, 5, 10, 5),
        (10, 6, 11, 6), (11, 7, 12, 7), (12, 8, 13, 8), (13, 9, 14, 9),
        (14, 10, 15, 10), (16, 12, 17, 12)],
}


def interpolated_tier_stats(level: float, troop: TroopType) -> dict[StatType, float]:
    """Stats for a fractional tier level (beast unit groups, e.g. Lv 6.0, 9.1).

    VERIFIED via beast power-per-unit: integer levels match tier power
    EXACTLY (Lv6.0 -> 20.0, Lv8.0 -> 38.0, Lv5.0 -> 13.0); fractional
    levels interpolate linearly between adjacent tiers (Lv2.4 -> 4.8 ✓).
    """
    lo = max(1, min(11, int(level)))
    hi = min(11, lo + 1)
    frac = level - int(level)
    a = _TIER_ROWS[troop][lo - 1]
    b = _TIER_ROWS[troop][hi - 1]
    keys = [StatType.ATTACK, StatType.DEFENSE, StatType.LETHALITY, StatType.HEALTH]
    return {k: a[i] + frac * (b[i] - a[i]) for i, k in enumerate(keys)}


def interpolated_tier_power(level: float) -> float:
    lo = max(1, min(11, int(level)))
    hi = min(11, lo + 1)
    return TIER_POWER[lo] + (level - int(level)) * (TIER_POWER[hi] - TIER_POWER[lo])


def parse_tier_label(label: str) -> tuple[int, int]:
    """'FC10 T11' -> (tier=11, fc=10); 'T11' -> (11, 0)."""
    fc, tier = 0, None
    for part in label.split():
        if part.upper().startswith("FC"):
            fc = int(part[2:])
        elif part.upper().startswith("T"):
            tier = int(part[1:])
    if tier is None:
        raise ValueError(f"No tier in label {label!r}")
    return tier, fc


# Legacy keys matching the workbook's tier-block labels (kept for validation)
TROOP_BASE_STATS: dict[tuple[str, TroopType], dict[StatType, int]] = {
    (label, troop): troop_base_stats(*parse_tier_label(label), troop)
    for label in ("FC9 T11", "FC10 T11") for troop in TroopType
}

_I, _L, _M = TroopType.INFANTRY, TroopType.LANCER, TroopType.MARKSMAN
_DD, _DEF = SkillAttribute.DAMAGE_DEALT, SkillAttribute.DEFENSE
_DT, _ATK = SkillAttribute.DAMAGE_TAKEN, SkillAttribute.ATTACK
_HP = SkillAttribute.HEALTH

TROOP_SKILL_CATALOG: list[TroopSkill] = [
    # --- Infantry ---
    TroopSkill(_I, "Master Brawler", "T1", _DD, "Lancer",
               "Increases attack damage to Lancers by 10%.", proc_amount=0.10),
    TroopSkill(_I, "Bands of Steel", "T7", _DEF, "Lancer",
               "Increases Defense against Lancers by 10%.", proc_amount=0.10),
    TroopSkill(_I, "Crystal Shield I", "FC3", _HP, "All",
               "25% chance of offsetting 36 damage (any damage category).",
               proc_chance=0.25, flat_offset=36, special="damage_offset"),
    TroopSkill(_I, "Crystal Shield II", "FC5", _HP, "All",
               "37.5% chance of offsetting 36 damage (any damage category).",
               proc_chance=0.375, flat_offset=36, special="damage_offset"),
    TroopSkill(_I, "Body of Light I", "FC8", _DEF, "All",
               "Infantry Defense +4%; extra 10% damage reduction while "
               "Crystal Shield is active.", proc_amount=0.04),
    TroopSkill(_I, "Body of Light I (reduction)", "FC8", _DT, "All",
               "Extra 10% damage reduction while Crystal Shield is active.",
               proc_amount=-0.10, requires="Crystal Shield"),
    TroopSkill(_I, "Body of Light II", "FC10", _DEF, "All",
               "Infantry Defense +6%; extra 15% damage reduction while "
               "Crystal Shield is active.", proc_amount=0.06),
    TroopSkill(_I, "Body of Light II (reduction)", "FC10", _DT, "All",
               "Extra 15% damage reduction while Crystal Shield is active.",
               proc_amount=-0.15, requires="Crystal Shield"),
    # --- Lancer ---
    TroopSkill(_L, "Charge", "T1", _DD, "Marksman",
               "Increases attack damage to Marksmen by 10%.", proc_amount=0.10),
    TroopSkill(_L, "Ambusher", "T7", None, "Marksman",
               "Attacks have a 20% chance to strike Marksmen behind Infantry.",
               proc_chance=0.20, special="bypass_to_marksman"),
    TroopSkill(_L, "Crystal Lance I", "FC3", _DD, "All",
               "10% chance of dealing double damage.",
               proc_chance=0.10, proc_amount=1.0),
    TroopSkill(_L, "Crystal Lance II", "FC5", _DD, "All",
               "15% chance of dealing double damage.",
               proc_chance=0.15, proc_amount=1.0),
    TroopSkill(_L, "Incandescent Field I", "FC8", _DT, "All",
               "10% chance of taking half damage when under attack.",
               proc_chance=0.10, proc_amount=-0.5),
    TroopSkill(_L, "Incandescent Field II", "FC10", _DT, "All",
               "15% chance of taking half damage when under attack.",
               proc_chance=0.15, proc_amount=-0.5),
    # --- Marksman ---
    TroopSkill(_M, "Ranged Strike", "T1", _DD, "Infantry",
               "Increases attack damage to Infantry by 10%.", proc_amount=0.10),
    # Confirmed by Martin: model Volley as a literal second attack event
    # (can re-roll procs / advance attack counters), not a flat +10% DD.
    # His tab keeps the +10% DD shorthand for Excel simplicity.
    TroopSkill(_M, "Volley", "T7", None, "All",
               "Attacks have a 10% chance to strike twice.",
               proc_chance=0.10, proc_amount=1.0, special="extra_attack"),
    TroopSkill(_M, "Crystal Gunpowder I", "FC3", _DD, "All",
               "20% chance of dealing 50% more damage.",
               proc_chance=0.20, proc_amount=0.5),
    TroopSkill(_M, "Crystal Gunpowder II", "FC5", _DD, "All",
               "30% chance of dealing 50% more damage.",
               proc_chance=0.30, proc_amount=0.5),
    TroopSkill(_M, "Flame Charge I", "FC8", _ATK, "All",
               "Basic attack +4%; extra 25% damage while Crystal Gunpowder "
               "is active.", proc_amount=0.04),
    TroopSkill(_M, "Flame Charge I (extra)", "FC8", _DD, "All",
               "Extra 25% damage while Crystal Gunpowder is active.",
               proc_amount=0.25, requires="Crystal Gunpowder"),
    TroopSkill(_M, "Flame Charge II", "FC10", _ATK, "All",
               "Basic attack +6%; extra 37.5% damage while Crystal Gunpowder "
               "is active.", proc_amount=0.06),
    TroopSkill(_M, "Flame Charge II (extra)", "FC10", _DD, "All",
               "Extra 37.5% damage while Crystal Gunpowder is active.",
               proc_amount=0.375, requires="Crystal Gunpowder"),
]

_UNLOCK_ORDER = {"T1": 0, "T7": 0, "FC3": 3, "FC5": 5, "FC8": 8, "FC10": 10}


def active_troop_skills(troop_type: TroopType, fc_level: int) -> list[TroopSkill]:
    """Skills a T11 troop of the given class actually has at an FC level.

    Tier skills (T1/T7) always apply; for versioned crystal skills only the
    highest unlocked version applies (FC9 troops still run the version-I
    skills whose II unlock is FC10).
    """
    candidates = [s for s in TROOP_SKILL_CATALOG
                  if s.troop_type == troop_type
                  and _UNLOCK_ORDER[s.unlock] <= fc_level]
    best: dict[str, TroopSkill] = {}
    for skill in candidates:
        family = (skill.name.replace(" I ", " ").replace(" II ", " ")
                  .removesuffix(" I").removesuffix(" II")
                  .replace(" I (", " (").replace(" II (", " ("))
        prev = best.get(family)
        if prev is None or _UNLOCK_ORDER[skill.unlock] > _UNLOCK_ORDER[prev.unlock]:
            best[family] = skill
    return list(best.values())


def gate_chance_for(skill: TroopSkill, active: list[TroopSkill]) -> float:
    """Uptime multiplier for effects gated on another skill being active."""
    if not skill.requires:
        return 1.0
    for other in active:
        if other.name.startswith(skill.requires) and other.proc_chance:
            return other.proc_chance
    return 0.0
