"""Bottom-up battle assembly: BattleReport -> battle engine inputs.

Pipeline per side:
  1. Exact class counts from participant rows.
  2. Additive standard pool from scouted stats (netting confirmed).
  3. Active hero skills: captain's 9 skills (widgets EXCLUDED here - they are
     already inside the special-bonus panel / S_net) + the top-4 joiners'
     flag-hero Skill 1, stacked additively. Proc effects enter at expected
     value computed from raw fields.
  4. Troop skills at each class's FC level (catalog EVs).
  5. Battle stat multiplier = (1 + std + skill/troop stat EVs) x (1 + S_net).
     Damage Dealt / Damage Taken effects go to per-class modifier pools.

v0 approximations (documented, revisit during fitting):
  - Damage-category splits (Normal vs Skills) are averaged into one channel.
  - Effects with receiver "Target" land on the enemy front line (Infantry).
  - Class-targeted troop skills: Ranged Strike (vs Infantry) applies fully
    (front-line logic); Master Brawler / Charge / Bands of Steel skipped.
  - Crystal Shield's flat damage offset is skipped.
  - Volley folded in as +10% Damage Dealt EV (engine's literal second-attack
    mode reserved for the stochastic engine).
"""

from __future__ import annotations

from dataclasses import replace

from .battle import BattleParams, ClassState, SideState, simulate_battle
from .mechanics import captain_effects
from .models import (
    AffectingSide,
    CombatContext,
    EffectReceiver,
    SkillAttribute,
    SkillBook,
    SkillEffect,
    SkillMechanic,
    SkillSource,
    StatType,
    TroopType,
)
from .reports import BattleReport, ReportSide
from .troop_catalog import active_troop_skills, gate_chance_for

_STAT_ATTRS = {
    SkillAttribute.ATTACK: StatType.ATTACK,
    SkillAttribute.DEFENSE: StatType.DEFENSE,
    SkillAttribute.LETHALITY: StatType.LETHALITY,
    SkillAttribute.HEALTH: StatType.HEALTH,
}


def expected_amount(e: SkillEffect) -> float:
    """EV of one skill-effect row from raw fields (rule: H is display-only)."""
    if e.mechanic == SkillMechanic.STATS_BASED:
        return e.amount
    j = e.probability if e.probability is not None else 1.0
    k = e.amount_per_proc if e.amount_per_proc is not None else e.amount
    cadence = e.frequency if e.frequency else 1.0
    duration = e.duration if e.duration else 1.0
    return j * k * min(duration / cadence, 1.0)


class ModifierBoard:
    """Accumulates per-side, per-class stat deltas and DD/DT pools.

    Two stat channels (GAME_RULES 6l, set-5 CONFIRMED):
      - `stat`     : ADDITIVE pool (troop-skill stat passives, standard pool).
      - `skillmult`: MULTIPLICATIVE hero stat-skills, Prod(1 + x). A hero
        stat skill (e.g. Seo-yoon +25% attack) is its OWN factor on the
        stat, NOT added into the panel pool (proven: +25% on a +850% panel
        moved kills x1.25, not x1.026).
    OPEN: whether MULTIPLE stacked joiner stat-skills compose as Prod(1+x)
    (implemented) or (1 + Sum x) - unresolved below ~5% resolution; revisit
    with the 4x-Jessie reports (r3/r7) once PvP is calibrated.
    """

    def __init__(self):
        self.stat: dict[tuple[str, TroopType, StatType], float] = {}
        self.skillmult: dict[tuple[str, TroopType, StatType], float] = {}
        self.dd: dict[tuple[str, TroopType], float] = {}
        self.dt: dict[tuple[str, TroopType], float] = {}

    def add_stat(self, side: str, troop: TroopType, stat: StatType, ev: float):
        self.stat[(side, troop, stat)] = self.stat.get((side, troop, stat), 0.0) + ev

    def mul_stat(self, side: str, troop: TroopType, stat: StatType, ev: float):
        key = (side, troop, stat)
        self.skillmult[key] = self.skillmult.get(key, 1.0) * (1.0 + ev)

    def add_dd(self, side: str, troop: TroopType, ev: float):
        self.dd[(side, troop)] = self.dd.get((side, troop), 0.0) + ev

    def add_dt(self, side: str, troop: TroopType, ev: float):
        self.dt[(side, troop)] = self.dt.get((side, troop), 0.0) + ev


def _route_effect(board: ModifierBoard, e: SkillEffect, own: str, foe: str):
    target_side = own if e.side == AffectingSide.FRIEND else foe
    if e.receiver == EffectReceiver.TARGET:
        receivers = [TroopType.INFANTRY]          # front-line convention
        target_side = foe
    else:
        receivers = [TroopType(e.receiver.value)]
    ev = expected_amount(e)
    for troop in receivers:
        if e.attribute in _STAT_ATTRS:
            # PERMANENT (stats-based) hero stat skill -> MULTIPLICATIVE
            # factor (set-5 confirmed). TEMPORARY (chance/turn-based) stat
            # buffs are procs -> additive pool at EXPECTED VALUE, NOT a
            # permanent multiplier (else they compound and inflate stacked
            # whale stats ~3x - the r004 defender bug).
            if e.mechanic == SkillMechanic.STATS_BASED:
                board.mul_stat(target_side, troop, _STAT_ATTRS[e.attribute], ev)
            else:
                board.add_stat(target_side, troop, _STAT_ATTRS[e.attribute], ev)
        elif e.attribute == SkillAttribute.DAMAGE_DEALT:
            board.add_dd(target_side, troop, ev)
        elif e.attribute == SkillAttribute.DAMAGE_TAKEN:
            board.add_dt(target_side, troop, ev)
        elif e.attribute == SkillAttribute.CRIT_RATE:
            board.add_dd(target_side, troop, ev)  # EV of +100% DD at chance


def _dedupe_damage_category_splits(effects: list[SkillEffect]) -> list[SkillEffect]:
    """Average Normal/Skills-split pairs of the same effect into one row (v0).

    Must be applied per activation instance - duplicate joiner stacks of the
    same hero are separate activations and stack additively, never merge.
    """
    out, seen = [], {}
    for e in effects:
        key = (e.hero, e.source, e.side, e.receiver, e.attribute, e.mechanic)
        if e.damage_category.value in ("Normal", "Skills"):
            if key in seen:
                idx, prev = seen[key]
                merged = replace(prev, amount=(prev.amount + e.amount) / 2)
                out[idx] = merged
                seen[key] = (idx, merged)
                continue
            seen[key] = (len(out), e)
        out.append(e)
    return out


def _hero_effects(report_side: ReportSide, book: SkillBook,
                  battle_ctx: CombatContext) -> list[SkillEffect]:
    effects: list[SkillEffect] = []
    captain = report_side.captain
    if captain is not None:
        lead = [h.name for h in report_side.lead_heroes]
        captain_rows = [e for e in captain_effects(book, lead, None, battle=battle_ctx)
                        if e.source != SkillSource.WIDGET]  # widgets live in S_net
        effects.extend(_dedupe_damage_category_splits(captain_rows))
    for flag_hero in report_side.joiner_flag_heroes():
        rows = [e for e in book.for_hero(flag_hero)
                if e.source == SkillSource.SKILL_1]
        effects.extend(_dedupe_damage_category_splits(rows))
    return effects


def _troop_skill_evs(board: ModifierBoard, side: str, troop: TroopType, fc: int):
    active = active_troop_skills(troop, fc)
    for s in active:
        if s.special == "bypass_to_marksman":
            continue                              # engine handles Ambusher
        if s.special == "extra_attack":
            board.add_dd(side, troop, s.proc_chance * (s.proc_amount or 1.0))
            continue
        if s.special == "damage_offset":
            continue                              # flat offset skipped in v0
        if s.against not in ("All", "Infantry"):
            continue                              # targeted skills skipped (v0)
        ev = s.expected_value(gate_chance_for(s, active))
        if ev is None:
            continue
        if s.attribute in _STAT_ATTRS:
            board.add_stat(side, troop, _STAT_ATTRS[s.attribute], ev)
        elif s.attribute == SkillAttribute.DAMAGE_DEALT:
            board.add_dd(side, troop, ev)
        elif s.attribute == SkillAttribute.DAMAGE_TAKEN:
            board.add_dt(side, troop, ev)


def assemble_battle(report: BattleReport, book: SkillBook
                    ) -> tuple[SideState, SideState, ModifierBoard]:
    """Build attacker/defender SideStates with fully-loaded modifiers."""
    board = ModifierBoard()
    atk_rs, def_rs = report.attacker, report.defender

    for e in _hero_effects(atk_rs, book, CombatContext.RALLY):
        _route_effect(board, e, "A", "D")
    for e in _hero_effects(def_rs, book, CombatContext.GARRISON):
        _route_effect(board, e, "D", "A")

    sides = {}
    for tag, rs, enemy_rs in (("A", atk_rs, def_rs), ("D", def_rs, atk_rs)):
        counts = rs.class_counts()
        std = rs.standard_pool(enemy_rs)
        classes = {}
        for troop in TroopType:
            fc = rs.composition[troop].fc_badge if troop in rs.composition else 10
            _troop_skill_evs(board, tag, troop, fc)
            stats = {}
            for stat in StatType:
                s_own = rs.special_pool(stat)
                p_enemy = rs.enemy_penalty_pool(stat, enemy_rs)
                # additive pool = standard (scouted) + troop-skill stat EVs
                pool = std.get((troop, stat), 0.0) + board.stat.get((tag, troop, stat), 0.0)
                skillmult = board.skillmult.get((tag, troop, stat), 1.0)
                # CONFIRMED rule: additive pool x special buffs / enemy
                # penalties x Prod(1 + hero stat skills)
                stats[stat] = ((1.0 + pool) * (1.0 + s_own)
                               / (1.0 + p_enemy) * skillmult)
            classes[troop] = ClassState(
                troop_type=troop, count=counts.get(troop, 0.0), tier=11,
                fc_level=fc, stats=stats,
                damage_dealt=board.dd.get((tag, troop), 0.0),
                damage_taken=board.dt.get((tag, troop), 0.0))
        sides[tag] = SideState(name=rs.player, classes=classes)
    return sides["A"], sides["D"], board


def run_report_battle(report: BattleReport, book: SkillBook,
                      params: BattleParams | None = None):
    attacker, defender, _ = assemble_battle(report, book)
    return simulate_battle(attacker, defender, params or BattleParams())
