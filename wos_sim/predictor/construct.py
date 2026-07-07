"""Layer 1 — profile -> engine construct.

Turns SideProfiles into the engine's two lists of Units (with resolved
effective stats), plus which side is the attacker (for mapping results back
to "you"). Reuses the engine catalogs (troop_base_stats) and its stat model.
For the rebuilt turn engine, the incoming panel is already the final
pre-battle state, so hero skills are not folded into units here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from wos_sim.assemble import ModifierBoard
from wos_sim.hero_stats import class_gens_from_names, relayer_panel
from wos_sim.models import CombatContext, StatType, TroopType
from wos_sim.pvp_engine import Unit
from wos_sim.troop_catalog import troop_base_stats

from . import skills
from .profiles import CLASSES, STATS, ClassQuality, Matchup, SideProfile

_TROOP = {"Infantry": TroopType.INFANTRY, "Lancer": TroopType.LANCER, "Marksman": TroopType.MARKSMAN}


@dataclass
class Construct:
    """Fully-resolved engine input. `own_is_attacker` maps engine A/D results
    back to 'you' vs 'enemy'. `engine_params` are profile-derived params the
    kernel merges in (e.g. T12 skill levels a_t12/d_t12)."""
    attacker_units: list          # list[Unit]
    defender_units: list
    own_is_attacker: bool
    meta: dict = field(default_factory=dict)
    engine_params: dict = field(default_factory=dict)
    attacker_profile: SideProfile | None = None
    defender_profile: SideProfile | None = None


# T12 tier-3 skill per class (GAME_RULES 6e / wos_sim.t12.side_mods)
_T12_SKILL = {"Infantry": "indomitable_wall", "Lancer": "meridian_phalanx", "Marksman": "starfire"}


def t12_levels(side: SideProfile):
    """Per-class T12 stacking (0-24) -> engine skill-level dict, gated on Tier 12.
    Returns None if no class is at Tier 12 (the engine treats None as no-op)."""
    levels, any12 = {}, False
    for cls in CLASSES:
        q = side.quality.get(cls, ClassQuality())
        at12 = q.tier >= 12
        any12 = any12 or at12
        levels[_T12_SKILL[cls]] = int(q.t12_stack) if at12 else 0
    return levels if any12 else None


def class_counts(side: SideProfile) -> dict:
    """Per-class troop counts. Prefers the exact numbers the user typed
    (``formation_counts``) so the engine uses them directly; falls back to
    ``troops_total`` x ``formation`` fractions when explicit counts aren't given."""
    if side.formation_counts:
        return {c: int(round(side.formation_counts.get(c, 0.0))) for c in CLASSES}
    return {c: round(side.troops_total * side.formation.get(c, 0.0)) for c in CLASSES}


def tier_base(tier: float, fc: int, troop: TroopType) -> dict:
    """Base tier stats, linearly interpolated for half-tiers (10.5, 11.5)."""
    lo, hi = int(math.floor(tier)), int(math.ceil(tier))
    base_lo = troop_base_stats(lo, fc, troop)
    if hi == lo:
        return dict(base_lo)
    base_hi = troop_base_stats(hi, fc, troop)
    frac = tier - lo
    return {s: base_lo[s] * (1 - frac) + base_hi[s] * frac for s in base_lo}


def effective_stats(side: SideProfile, enemy: SideProfile, cls: str,
                    board: ModifierBoard | None = None, tag: str | None = None) -> dict:
    """Effective per-stat value for one class (StatType -> float).

    scouted mode: Eff = TierBase x (1+panel) x optional legacy board skills.
    pools   mode: Eff = TierBase x (1+panel) x (1+own_buffs) / (1+enemy_debuffs)
                        x optional legacy board skills.
    The turn engine supplies an empty legacy board and applies skill effects in
    battle. Older/general callers can still pass a board whose
    `skillmult[(tag, troop, stat)]` values are >1 own buffs or <1 enemy debuffs.
    """
    q = side.quality.get(cls, ClassQuality())
    troop = _TROOP[cls]
    base = tier_base(q.tier, q.fc, troop)
    out = {}
    for stat in STATS:
        st = StatType(stat)
        panel = side.panel.get((cls, stat), 0.0)
        skillmult = board.skillmult.get((tag, troop, st), 1.0) if (board and tag) else 1.0
        if side.stats_mode == "pools":
            own = side.own_buffs.get(stat, 0.0)
            pen = enemy.debuffs_on_enemy.get(stat, 0.0)
            out[st] = base[st] * (1 + panel) * (1 + own) / (1 + pen) * skillmult
        else:  # scouted: the panel is already net; hero skills apply on top
            out[st] = base[st] * (1 + panel) * skillmult
    return out


def side_units(side: SideProfile, enemy: SideProfile,
               board: ModifierBoard | None = None, tag: str | None = None) -> list:
    """Engine Units for one side (classes with zero troops are dropped). Hero
    Damage-Dealt/Taken skills feed each Unit's `dd`/`dt` from the board."""
    counts = class_counts(side)
    units = []
    for cls in CLASSES:
        n = counts[cls]
        if n <= 0:
            continue
        q = side.quality.get(cls, ClassQuality())
        troop = _TROOP[cls]
        base = tier_base(q.tier, q.fc, troop)
        dd = board.dd.get((tag, troop), 0.0) if (board and tag) else 0.0
        dt = board.dt.get((tag, troop), 0.0) if (board and tag) else 0.0
        units.append(Unit(troop=troop, tier=q.tier, n=float(n),
                          astat=effective_stats(side, enemy, cls, board, tag),
                          base_atk=base[StatType.ATTACK], dd=dd, dt=dt))
    return units


def _relayer_hero_stats(side: SideProfile) -> SideProfile:
    """Strip the assumed highest-gen lead hero from the scouted panel and
    re-apply each class's ACTUAL lead-hero generation (GAME_RULES 6q,
    hero_stats.relayer_panel). No-op if no lead hero resolves to a generation."""
    gens = class_gens_from_names(side.lead_heroes)
    if not gens:
        return side
    panel = relayer_panel(side.panel, gens)
    # Guard: a relayered value < 0 means the panel was NOT scouted (e.g. a BASE
    # panel was sent) so the hero-strip underflowed. Clamp to 0 -> the class
    # degrades to base-tier stats instead of producing negative (garbage) astat.
    # The real fix is upstream: send the full SCOUTED panel (ENGINE_INTERFACE).
    return replace(side, panel={k: max(0.0, v) for k, v in panel.items()})


def build(matchup: Matchup, *, apply_legacy_skills: bool = True) -> Construct:
    """Profile pair -> engine construct. Rally is the attacker. Resolves both
    sides' hero skills into one ModifierBoard (attacker='A', defender='D') when
    using the legacy/general engines.

    The catalog-driven turn engine applies hero skills inside the battle loop,
    so its construct must keep units at the profile's final pre-battle panel
    value and skip this legacy approximation.
    """
    own, enemy = matchup.own, matchup.enemy
    # Hero-generation STAT back-calc (GAME_RULES 6q). ONLY in the PRE-ASSUMED
    # symmetric case (both sides fed the SAME scouted panel): strip the assumed
    # highest-gen hero baked into that panel and re-apply each side's ACTUAL
    # per-class lead-hero generation - so a Gen-2 lead is fought as Gen-2, not the
    # panel's Gen-13. When the two sides carry DIFFERENT real stats the user gave
    # actuals - leave them untouched. (Buffs are net out of the scouted panel per
    # ENGINE_INTERFACE §7, so the relayer runs buff-free.)
    if (own.stats_mode == "scouted" and own.panel == enemy.panel
            and not own.panel_is_final and not enemy.panel_is_final):
        own, enemy = _relayer_hero_stats(own), _relayer_hero_stats(enemy)
    attacker, defender = (own, enemy) if matchup.own_is_attacker else (enemy, own)

    board = ModifierBoard()
    if apply_legacy_skills:
        skills.resolve(attacker, defender, "A", "D", CombatContext.RALLY, board)
        skills.resolve(defender, attacker, "D", "A", CombatContext.GARRISON, board)

    atk_u = side_units(attacker, defender, board, "A")
    def_u = side_units(defender, attacker, board, "D")
    meta = {"own_label": own.label, "enemy_label": enemy.label,
            "own_role": own.role, "enemy_role": enemy.role}
    engine_params = {
        "a_t12": t12_levels(attacker), "d_t12": t12_levels(defender),
        # Raw per-stat buff pools forwarded to the engine for legacy callers.
        # The browser's Final Stats contract sends panel_is_final=True with empty
        # buff dicts because the UI has already folded those assumptions into the
        # panel it sends.
        #   *_buffs            = that side's own item/pet buffs   {stat: fraction}
        #   *_debuffs_on_enemy = debuffs that side applies to the OTHER side.
        "a_buffs": dict(attacker.own_buffs), "d_buffs": dict(defender.own_buffs),
        "a_debuffs_on_enemy": dict(attacker.debuffs_on_enemy),
        "d_debuffs_on_enemy": dict(defender.debuffs_on_enemy),
    }
    return Construct(atk_u, def_u, matchup.own_is_attacker, meta, engine_params,
                     attacker_profile=attacker, defender_profile=defender)
