"""Turn-by-turn PvP engine with catalog-driven skill telemetry.

This engine is intentionally separate from ``pvp_engine`` while the rebuild is
being validated.  It consumes the same constructed Units, but rebuilds active
skill effects from the workbook/catalog instead of using averaged DD/DT pools.
Telemetry is written from the same packet applications that remove troops.
"""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from wos_sim.loader import load_skill_book
from wos_sim.models import (
    AffectingSide,
    CombatContext,
    DamageCategory,
    EffectReceiver,
    SkillAttribute,
    SkillEffect,
    SkillMechanic,
    SkillSource,
    StatType,
    TriggerUnit,
    TroopSkill,
    TroopType,
)
from wos_sim.pvp_engine import (
    A,
    BEST_PARAMS,
    COUNTERS,
    D,
    H,
    L,
    ORDER,
    Unit,
    base_strike_damage,
)
from wos_sim.t12 import side_mods as t12_mods
from wos_sim.troop_catalog import active_troop_skills, gate_chance_for

EPS = 1e-9
SIDE_LABEL = {"attacker": "A", "defender": "D"}
SIDE_NAME = {"A": "attacker", "D": "defender"}
SLOT = {
    SkillSource.SKILL_1: "skill_1",
    SkillSource.SKILL_2: "skill_2",
    SkillSource.SKILL_3: "skill_3",
    SkillSource.WIDGET: "widget",
}
STAT_ATTRS = {
    SkillAttribute.ATTACK: StatType.ATTACK,
    SkillAttribute.DEFENSE: StatType.DEFENSE,
    SkillAttribute.LETHALITY: StatType.LETHALITY,
    SkillAttribute.HEALTH: StatType.HEALTH,
}
TROOP_BY_NAME = {t.value: t for t in TroopType}
TURN_PARAMS = {
    # Locked 2026-07-08 (second pass) against FOUR real anchors
    # (pvp_t12_report_001/002 + Calibration_Amanda_Omar + Calibration_Amanda_Ramp)
    # via wos_sim.anchor_eval / fit sweeps. Result: ALL FOUR winners correct;
    # A3 survivors 75% (real 34%), A4 46% (real 58%, in band); durations
    # 15/20/18/24 (real 16/25/19-20/~16). KNOWN, DECLARED trade-off: near-even
    # rally survivor DEPTH is sacrificed (A1/A2 predict ~65-73% survivors vs
    # real 3.45%/6.54%) - the near-even flag + coin_flip labeling carries the
    # honesty. The A2-vs-A4 tension (marks-heavy sides) is the open mechanic:
    # see ENGINE_REBUILD/QA_REPORT.md 2026-07-08 second pass.
    # NOTE 2026-07-08 (fourth pass): the third-pass SIZE-DEPENDENT defender
    # scale (def_k=0.0183/def_ed=1.28) was REVERTED. It was motivated by anchor
    # 5's "defender needs x1.35-1.45" cliff, which was itself computed from a
    # MISTRANSLATED comp (Martin's 676k were MARKSMAN, not lancers). With the
    # corrected comp that cliff dissolves, and the flat lock below ranks all
    # four decisive anchors with equal/better gates. Kept flat.
    "rate": 168.0,
    # Defender fires at ~0.45x the attacker's per-capita scale (flat). The
    # anchor-4 lock; ranks A1-A4 winners correctly. A5 (near-mirror rally that
    # the defender WON) is a coin-flip the engine cannot call - declared miss.
    "def_k": 0.45,
    "def_ed": 1.0,
    # Wounded-keep-fighting: stacks fire at STARTING strength until broken
    # (the anchors show constant-in-time absolute casualty rates, not
    # Lanchester taper).
    "fire_mode": "start",
    # Diminishing returns on stacked skill modifiers: raw multiplicative kits
    # predict a 3-4x exchange edge; the anchors show ~0.9-1.1x real.
    "mod_gamma": 0.30,
    # Floor on the composed per-stat modifier (additive stacking used to reach
    # -97.8% defense and blow up damage through def^qd).
    "stat_floor": 0.4,
    # Skill packets scaled to the A4 report's per-skill kill columns: real
    # skill-attributed kills are ~7% of casualties; K_skill=1.0 produced 38-50%
    # (def Ligeia 99k engine kills vs 8.6k real).
    "K_skill": 0.15,
    # Mild compression of the defense-side stat denominator (beast-fitted
    # H^1.45 over-rewards health-stacked panels; anchor A4).
    "q_def": 0.7,
    # Marksman damage coefficient (turn-engine only; overrides BEST_PARAMS km
    # 1.206 for PvP, leaves the PvE/farm kernel untouched). STEP 1 of the
    # counter-physics build (2026-07-09): the base km under-weighted marksman
    # offense ~2x - the engine killed the fragile marksman before they dealt
    # their high damage, so lancer-vs-marksman read 71% (real 42%) and
    # inf-vs-marksman read 67% (real 4.9%). Calibrated to the clean
    # lancer>marksman controlled anchor (Lv6, no skills): km=2.41 lands it at
    # 42% EXACTLY and halves the inf<marksman error to 33%. Passes the
    # mandatory back-test (py -m wos_sim.backtest): all 7 locked golden winners
    # hold, no new silent miss. The residual inf<marksman gap (33% vs 4.9%) is
    # the coupled under-grind (mirror still 57% vs real 24%) - deferred to the
    # grind step, NOT chased with more km (km x4 over-kills lancer>marksman to
    # 0%). See ENGINE_REBUILD/07_CONTROLLED_EXPERIMENTS.md.
    "km": 2.41,
    "ambush_proc": 0.20,
    "ambush_frac": 1.0,
    "cara_burst": 1.0,
}
SKILL_DISPLAY_PATH = Path(__file__).resolve().parent / "data" / "skill_display" / "hero_skills.json"
_ALL_TROOP_ATTACK_RE = re.compile(r"\ball\s+troops?\s+(?:normal\s+)?attacks?\b")
_ALL_TROOPS_HAVE_CHANCE_RE = re.compile(
    r"\b(?:grant(?:s|ing)?|give|gives)\s+all\s+troops?\s+a\s+(?:\d+\s+)*\d+\s+chance\b"
    r"|\ball\s+troops?\s+have\s+a\s+(?:\d+\s+)*\d+\s+chance\b"
)


@dataclass
class TypeStack:
    troop: TroopType
    tier: float
    n: float
    n0: float
    astat: dict
    base_atk: float
    dd: float = 0.0
    dt: float = 0.0
    incap: float = 0.0
    attacks_made: int = 0


@dataclass
class SkillDef:
    owner: str
    side: str                      # "attacker" | "defender"
    slot: str                      # skill_1/2/3, widget, troop, t12
    role: str                      # captain, joiner, troop_skill, t12
    troop: TroopType | None
    rows: tuple[SkillEffect, ...] = ()
    troop_skill: TroopSkill | None = None
    source_id: str = ""
    ordinal: int = 0
    is_widget: bool = False
    is_passive: bool = False
    deals_damage: bool = False
    is_bypass: bool = False
    bypass_targets: tuple[TroopType, ...] = ()
    special: str | None = None
    suppress_own_stat_passives: bool = False
    start_turn: int = 1
    triggers: int = 0
    kills: float = 0.0


@dataclass
class DamagePacket:
    source: SkillDef | str
    side: str
    magnitude: float
    target_mode: str = "front"      # "front" | "backline"
    target_types: tuple[TroopType, ...] = ()
    source_troop: TroopType | None = None


@dataclass
class TurnRecord:
    turn: int
    start_counts: dict
    casualties: dict
    kills_by_source: dict
    attack_events: dict = field(default_factory=dict)
    procs: list = field(default_factory=list)   # chance/turn-based skills that fired this turn
    kills_by_troop: dict = field(default_factory=dict)
    # {"attacker": {(atk_class, victim_class): n}, "defender": {...}} - the joint
    # kill matrix whose row/col sums are kills_by_troop / casualties.
    kills_matrix: dict = field(default_factory=dict)


@dataclass
class TurnEngineResult:
    winner: str
    turns: int
    a_survivors: dict
    d_survivors: dict
    a_incap: dict
    d_incap: dict
    skill_telemetry: dict | None
    turn_log: list[TurnRecord] = field(default_factory=list)


@dataclass
class _Mods:
    stat: dict[tuple[str, TroopType, StatType], float] = field(default_factory=dict)
    normal_dd: dict[tuple[str, TroopType], float] = field(default_factory=dict)
    normal_dt: dict[tuple[str, TroopType], float] = field(default_factory=dict)
    skill_dd: dict[tuple[str, TroopType], float] = field(default_factory=dict)
    skill_dt: dict[tuple[str, TroopType], float] = field(default_factory=dict)

    def add_stat(self, side: str, troop: TroopType, stat: StatType, value: float):
        self.stat[(side, troop, stat)] = self.stat.get((side, troop, stat), 0.0) + value

    def mul_stat(self, side: str, troop: TroopType, stat: StatType, value: float):
        key = (side, troop, stat)
        self.stat[key] = (1.0 + self.stat.get(key, 0.0)) * (1.0 + value) - 1.0

    def add_dd(self, side: str, troop: TroopType, value: float,
               category: DamageCategory = DamageCategory.BOTH):
        if category in (DamageCategory.BOTH, DamageCategory.NORMAL):
            key = (side, troop)
            self.normal_dd[key] = self.normal_dd.get(key, 0.0) + value
        if category in (DamageCategory.BOTH, DamageCategory.SKILLS):
            key = (side, troop)
            self.skill_dd[key] = self.skill_dd.get(key, 0.0) + value

    def add_dt(self, side: str, troop: TroopType, value: float,
               category: DamageCategory = DamageCategory.BOTH):
        if category in (DamageCategory.BOTH, DamageCategory.NORMAL):
            key = (side, troop)
            self.normal_dt[key] = self.normal_dt.get(key, 0.0) + value
        if category in (DamageCategory.BOTH, DamageCategory.SKILLS):
            key = (side, troop)
            self.skill_dt[key] = self.skill_dt.get(key, 0.0) + value


@dataclass
class _ActiveEffect:
    skill: SkillDef
    starts_at: int
    expires_after: int


def _clone_units(units: Iterable[Unit]) -> dict[TroopType, TypeStack]:
    out = {}
    for u in units:
        out[u.troop] = TypeStack(
            troop=u.troop,
            tier=float(u.tier),
            n=float(u.n),
            n0=float(u.n),
            astat=dict(u.astat),
            base_atk=float(u.base_atk),
            # Do not copy averaged DD/DT from the legacy construct; the turn
            # engine replays passive and firing skill rows to avoid double count.
            dd=0.0,
            dt=0.0,
        )
    return out


def _front(stacks: dict[TroopType, TypeStack]) -> TypeStack | None:
    for troop in ORDER:
        st = stacks.get(troop)
        if st and st.n > EPS:
            return st
    return None


def _total(stacks: dict[TroopType, TypeStack]) -> float:
    return sum(st.n for st in stacks.values())


def _snapshot(a: dict[TroopType, TypeStack], d: dict[TroopType, TypeStack]) -> dict:
    return {
        "attacker": {t: st.n for t, st in a.items()},
        "defender": {t: st.n for t, st in d.items()},
    }


def _row_amount(row: SkillEffect) -> float:
    if row.amount_per_proc is not None:
        amount = float(row.amount)
        per_proc = float(row.amount_per_proc)
        if amount < 0 < per_proc:
            return -per_proc
        if amount > 0 > per_proc:
            return abs(per_proc)
        return per_proc
    return float(row.amount)


def _row_probability(row: SkillEffect) -> float:
    return 1.0 if row.probability is None else float(row.probability)


def _has_runtime_fields(row: SkillEffect) -> bool:
    return any(v is not None for v in (
        row.probability, row.amount_per_proc, row.frequency, row.trigger_unit,
        row.duration, row.duration_unit,
    ))


def _is_static_passive(rows: Iterable[SkillEffect]) -> bool:
    rows = tuple(rows)
    return all(r.mechanic == SkillMechanic.STATS_BASED and not _has_runtime_fields(r)
               for r in rows)


def _row_is_direct_damage(row: SkillEffect) -> bool:
    """True when a workbook row should emit a casualty packet, not a DD buff."""
    amount = _row_amount(row)
    if row.side != AffectingSide.FRIEND or amount <= 0:
        return False
    if row.attribute == SkillAttribute.CRIT_RATE:
        return True
    if row.attribute != SkillAttribute.DAMAGE_DEALT:
        return False
    if _is_static_passive([row]):
        return False
    if row.damage_category == DamageCategory.SKILLS:
        return True
    if row.duration is None:
        return True
    if row.duration <= 1:
        return True
    if row.duration_unit in (TriggerUnit.ATTACKS, TriggerUnit.STRIKES):
        return True
    if row.amount_per_proc is not None and row.amount_per_proc >= 1.0:
        return True
    return False


def _row_is_direct_damage_for_skill(row: SkillEffect,
                                    rows: Iterable[SkillEffect]) -> bool:
    if row.hero == "Renee" and row.source in (SkillSource.SKILL_2, SkillSource.SKILL_3):
        return False
    if row.hero == "Lynn" and row.source == SkillSource.SKILL_1:
        return False
    if not _row_is_direct_damage(row):
        return False
    rows = tuple(rows)
    if row.attribute != SkillAttribute.DAMAGE_DEALT:
        return True
    if row.damage_category == DamageCategory.SKILLS:
        return True
    paired_damage_taken = any(
        other.attribute == SkillAttribute.DAMAGE_TAKEN
        for other in rows
    )
    amount = abs(_row_amount(row))
    per_proc = abs(row.amount_per_proc) if row.amount_per_proc is not None else amount
    if paired_damage_taken and amount < 1.0 and per_proc < 1.0:
        return False
    return True


def _skill_cadence_rows(skill: SkillDef) -> tuple[SkillEffect, ...]:
    rows = tuple(skill.rows)
    direct = tuple(row for row in rows if _row_is_direct_damage_for_skill(row, rows))
    if direct:
        return direct
    own_cadence = tuple(
        row for row in rows
        if row.frequency is not None and row.trigger_unit != TriggerUnit.RECEIVED
    )
    if own_cadence:
        return own_cadence
    any_cadence = tuple(row for row in rows if row.frequency is not None)
    if any_cadence:
        return any_cadence
    return rows


def _receivers_for(row: SkillEffect, front: TroopType | None = None) -> list[TroopType]:
    if row.receiver == EffectReceiver.TARGET:
        return [front] if front is not None else list(ORDER)
    return [TroopType(row.receiver.value)]


def _skill_frequency(skill: SkillDef) -> float | None:
    values = [r.frequency for r in _skill_cadence_rows(skill) if r.frequency]
    return float(values[0]) if values else None


def _skill_trigger_unit(skill: SkillDef) -> TriggerUnit | None:
    values = [r.trigger_unit for r in _skill_cadence_rows(skill) if r.trigger_unit]
    return values[0] if values else None


def _row_troop(row: SkillEffect) -> TroopType | None:
    if row.receiver == EffectReceiver.TARGET:
        return None
    return TroopType(row.receiver.value)


def _unique_troops(troops: Iterable[TroopType | None]) -> list[TroopType]:
    out = []
    for troop in troops:
        if troop is None or troop in out:
            continue
        out.append(troop)
    return out


@lru_cache(maxsize=1)
def _display_skill_effects() -> dict[tuple[str, str], str]:
    try:
        display = json.loads(SKILL_DISPLAY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for hero, record in (display.get("heroes") or {}).items():
        for skill in record.get("skills") or []:
            slot = skill.get("slot")
            effect = skill.get("effect")
            if slot and effect:
                out[(str(hero).casefold(), str(slot))] = str(effect)
    return out


def _normalized_skill_effect_text(skill: SkillDef) -> str:
    text = _display_skill_effects().get((skill.owner.casefold(), skill.slot), "")
    text = text.casefold().replace("'", "").replace("’", "").replace("â€™", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _text_says_each_troop_can_proc(skill: SkillDef) -> bool:
    text = _normalized_skill_effect_text(skill)
    return bool(
        _ALL_TROOP_ATTACK_RE.search(text)
        or _ALL_TROOPS_HAVE_CHANCE_RE.search(text)
    )


def _direct_trigger_troops(skill: SkillDef) -> list[TroopType]:
    rows = tuple(skill.rows)
    return _unique_troops(
        _row_troop(row)
        for row in rows
        if _row_is_direct_damage_for_skill(row, rows)
    )


def _modifier_trigger_troops(skill: SkillDef) -> list[TroopType | None]:
    if _skill_probability(skill) < 1.0 and _text_says_each_troop_can_proc(skill):
        return list(ORDER)
    if skill.troop is not None:
        return [skill.troop]
    return [None]


def _trigger_candidate_troops(skill: SkillDef) -> list[TroopType | None]:
    direct = _direct_trigger_troops(skill)
    return direct or _modifier_trigger_troops(skill)


def _filter_by_probability(candidates: Iterable[TroopType | None],
                           prob: float,
                           rng: random.Random) -> list[TroopType | None]:
    if prob >= 1.0:
        return list(candidates)
    return [candidate for candidate in candidates if rng.random() < prob]


def _uses_per_attack_probability(skill: SkillDef, prob: float) -> bool:
    if prob >= 1.0:
        return False
    if _direct_trigger_troops(skill):
        return True
    return len(_modifier_trigger_troops(skill)) > 1


def _skill_probability(skill: SkillDef) -> float:
    probs = []
    seen = set()
    for row in _skill_cadence_rows(skill):
        if row.probability is None:
            continue
        prob = _row_probability(row)
        if prob in seen:
            continue
        seen.add(prob)
        probs.append(prob)
    if skill.troop_skill and skill.troop_skill.proc_chance is not None:
        probs.append(float(skill.troop_skill.proc_chance))
    prob = 1.0
    for p in probs:
        prob *= p
    return prob


def _skill_duration(skill: SkillDef) -> int:
    durations = [_row_duration_turns(skill, r) for r in skill.rows]
    return max(durations) if durations else 1


def _row_duration_turns(skill: SkillDef, row: SkillEffect) -> int:
    if skill.owner.casefold() == "lynn" and skill.slot == "skill_3":
        return 4000
    if not row.duration:
        return 1
    if row.duration_unit in (None, TriggerUnit.TURNS):
        return max(int(row.duration), 1)
    return 1


def _row_active_for_effect(effect: _ActiveEffect, row: SkillEffect, turn: int) -> bool:
    if effect.starts_at > turn:
        return False
    if row.duration_unit in (TriggerUnit.ATTACKS, TriggerUnit.STRIKES):
        return False
    if (row.duration_unit == TriggerUnit.RECEIVED
            and not _is_mark_companion_skill(effect.skill)):
        return False
    row_expires = effect.starts_at + _row_duration_turns(effect.skill, row) - 1
    return turn <= min(effect.expires_after, row_expires)


def _slot_from_source(source: SkillSource) -> str:
    return SLOT[source]


def _slug_owner(hero: str, slot: str, role: str, side: str, ordinal: int) -> str:
    return f"{side}:{role}:{hero}:{slot}:{ordinal}"


def _hero_rows(book, hero: str, source: SkillSource,
               context: CombatContext | None = None) -> tuple[SkillEffect, ...]:
    return tuple(
        e for e in book.for_hero(hero)
        if e.source == source and (context is None or e.context in (CombatContext.ALL, context))
    )


def _is_damage_bearing_rows(rows: Iterable[SkillEffect]) -> bool:
    rows = tuple(rows)
    for row in rows:
        if _row_is_direct_damage_for_skill(row, rows):
            return True
    for row in rows:
        if _is_next_attack_dt_row(row):
            return True
    return False


def _backline_targets(owner: str, slot: str) -> tuple[TroopType, ...]:
    key = (owner.casefold(), slot)
    if key == ("cara", "skill_3"):
        return (TroopType.LANCER, TroopType.MARKSMAN)
    return ()


def _hero_skill_start_turn(hero: str, slot: str) -> int:
    key = (hero.casefold(), slot)
    if key == ("cara", "skill_3"):
        return 2
    if key == ("ahmose", "skill_1"):
        return 4
    return 1


def _skill_pauses_attack(skill: SkillDef) -> bool:
    return skill.owner.casefold() == "ahmose" and skill.slot == "skill_1"


def _skill_allows_self_stacking(skill: SkillDef) -> bool:
    return skill.owner.casefold() == "lynn" and skill.slot == "skill_3"


def _add_active_effect(active_effects: list[_ActiveEffect], effect: _ActiveEffect):
    if effect.skill.troop_skill or _skill_allows_self_stacking(effect.skill):
        active_effects.append(effect)
        return
    for idx, existing in enumerate(active_effects):
        if existing.skill.source_id != effect.skill.source_id:
            continue
        if existing.expires_after < effect.starts_at - 1:
            continue
        active_effects[idx] = _ActiveEffect(
            effect.skill,
            min(existing.starts_at, effect.starts_at),
            max(existing.expires_after, effect.expires_after),
        )
        return
    active_effects.append(effect)


def _is_mark_companion_skill(skill: SkillDef) -> bool:
    return skill.owner.casefold() == "renee" and skill.slot in ("skill_2", "skill_3")


def _mark_companion_skills(skills: list[SkillDef], marker: SkillDef) -> list[SkillDef]:
    if marker.owner.casefold() != "renee" or marker.slot != "skill_1":
        return []
    return [
        skill for skill in skills
        if skill.side == marker.side
        and skill.owner == marker.owner
        and skill.role == marker.role
        and skill.ordinal == marker.ordinal
        and _is_mark_companion_skill(skill)
    ]


def _effect_start_turn(skill: SkillDef, fired_turn: int) -> int:
    return fired_turn + 1 if _skill_pauses_attack(skill) else fired_turn


def _make_hero_skill(hero: str, source: SkillSource, rows: tuple[SkillEffect, ...],
                     side: str, role: str, troop: TroopType | None,
                     ordinal: int,
                     suppress_own_stat_passives: bool = False) -> SkillDef:
    slot = _slot_from_source(source)
    targets = _backline_targets(hero, slot)
    is_widget = source == SkillSource.WIDGET
    is_passive = is_widget or _is_static_passive(rows)
    skill = SkillDef(
        owner=hero,
        side=side,
        slot=slot,
        role=role,
        troop=troop,
        rows=rows,
        source_id=_slug_owner(hero, slot, role, side, ordinal),
        ordinal=ordinal,
        is_widget=is_widget,
        is_passive=is_passive,
        deals_damage=_is_damage_bearing_rows(rows),
        is_bypass=bool(targets),
        bypass_targets=targets,
        suppress_own_stat_passives=suppress_own_stat_passives,
        start_turn=_hero_skill_start_turn(hero, slot),
    )
    return skill


def _active_troop_skills(troop: TroopType, tier: float, fc: int) -> list[TroopSkill]:
    active = []
    for skill in active_troop_skills(troop, fc if tier >= 10 else 0):
        if skill.unlock == "T7" and tier < 7:
            continue
        if skill.unlock.startswith("FC") and tier < 10:
            continue
        active.append(skill)
    return active


def _make_troop_skill(skill: TroopSkill, side: str, ordinal: int) -> SkillDef:
    special = skill.special
    is_damage = (
        special in ("bypass_to_marksman", "extra_attack")
        or (skill.attribute == SkillAttribute.DAMAGE_DEALT
            and (skill.proc_amount or 0.0) > 0
            and skill.proc_chance is not None)
    )
    targets = (TroopType.MARKSMAN,) if special == "bypass_to_marksman" else ()
    return SkillDef(
        owner=skill.name,
        side=side,
        slot="troop",
        role="troop_skill",
        troop=skill.troop_type,
        troop_skill=skill,
        source_id=f"{side}:troop:{skill.troop_type.value}:{skill.name}:{ordinal}",
        ordinal=ordinal,
        is_passive=skill.proc_chance is None and special is None,
        deals_damage=is_damage,
        is_bypass=special == "bypass_to_marksman",
        bypass_targets=targets,
        special=special,
    )


def _make_t12_skill(name: str, troop: TroopType, side: str, level: int) -> SkillDef:
    return SkillDef(
        owner=name,
        side=side,
        slot="t12",
        role="t12",
        troop=troop,
        source_id=f"{side}:t12:{name}",
        is_passive=False,
        special=f"t12:{level}",
    )


def skill_defs_from_matchup(construct, params: dict | None = None) -> list[SkillDef]:
    """Build runtime SkillDefs for every active hero, widget, troop, and T12 skill."""
    if construct.attacker_profile is None or construct.defender_profile is None:
        raise ValueError("turn engine requires Construct.attacker_profile/defender_profile")
    book = load_skill_book()
    defs: list[SkillDef] = []
    params = params or {}

    def widgets_in_panel(profile) -> bool:
        if getattr(profile, "panel_is_final", False):
            return True
        if "widgets_in_panel" in params:
            return bool(params["widgets_in_panel"])
        value = getattr(profile, "widgets_in_panel", None)
        if value is not None:
            return bool(value)
        return getattr(profile, "stats_mode", "scouted") == "scouted"

    def add_side(profile, units, side: str, t12_levels):
        battle = (CombatContext.GARRISON
                  if getattr(profile, "role", "rally") == "garrison"
                  else CombatContext.RALLY)
        ordinal = 0
        for cls, hero in (profile.lead_heroes or {}).items():
            if not hero:
                continue
            troop = TROOP_BY_NAME.get(cls)
            hero_ordinal = ordinal
            sources = [SkillSource.SKILL_1, SkillSource.SKILL_2, SkillSource.SKILL_3]
            if not widgets_in_panel(profile):
                sources.append(SkillSource.WIDGET)
            for source in sources:
                rows = _hero_rows(book, hero, source, battle)
                if rows:
                    defs.append(_make_hero_skill(hero, source, rows, side, "captain",
                                                 troop, hero_ordinal,
                                                 getattr(profile, "panel_is_final", False)))
            ordinal += 1
        seen_joiners: set[str] = set()
        for hero in (profile.joiners or [])[:4]:
            if not hero:
                continue
            # DUPLICATE-JOINER DEDUP: the same hero's joiner Skill-1 applies
            # ONCE, not per copy. Anchored on pvp_t12_report_005 (real 4x-Nora
            # rally, near-mirror totals, LOST): full additive stacking predicts
            # a guaranteed 60%-survivor win; dedup lands the forecast at the
            # coin-flip edge, consistent with the real defeat. One-battle
            # evidence - flagged as an assumption in QA_REPORT.
            if hero in seen_joiners:
                continue
            seen_joiners.add(hero)
            rows = _hero_rows(book, hero, SkillSource.SKILL_1, battle)
            if rows:
                # JOINER stat rows are NEVER panel-suppressed: a joiner is
                # another player's hero, so its stat skills cannot be inside
                # this side's scouted/final panel (unlike the captains').
                # Suppressing them silently zeroed stat-joiners (Patrick,
                # Gatot) while DD/DT-joiners (Nora, Bahiti) passed in full.
                defs.append(_make_hero_skill(hero, SkillSource.SKILL_1, rows, side,
                                             "joiner", None, ordinal, False))
                ordinal += 1
        quality = profile.quality or {}
        for u in units:
            cls = u.troop.value
            q = quality.get(cls)
            fc = int(getattr(q, "fc", 10))
            for ts in _active_troop_skills(u.troop, float(u.tier), fc):
                defs.append(_make_troop_skill(ts, side, ordinal))
                ordinal += 1
        t12_levels = t12_levels or {}
        t12_map = (
            ("indomitable_wall", TroopType.INFANTRY),
            ("meridian_phalanx", TroopType.LANCER),
            ("starfire", TroopType.MARKSMAN),
        )
        for name, troop in t12_map:
            level = int(t12_levels.get(name, 0) or 0)
            if level > 0:
                defs.append(_make_t12_skill(name, troop, side, level))

    add_side(construct.attacker_profile, construct.attacker_units,
             "attacker", params.get("a_t12", construct.engine_params.get("a_t12")))
    add_side(construct.defender_profile, construct.defender_units,
             "defender", params.get("d_t12", construct.engine_params.get("d_t12")))
    return defs


def catalog_classification_report(construct) -> dict:
    defs = skill_defs_from_matchup(construct)
    unclassified = []
    for skill in defs:
        if skill.role in ("troop_skill", "t12"):
            continue
        if not skill.is_passive and not skill.deals_damage and not skill.rows:
            unclassified.append(skill.source_id)
    return {
        "total": len(defs),
        "heroes": sum(1 for s in defs if s.role in ("captain", "joiner")),
        "widgets": sum(1 for s in defs if s.is_widget),
        "troop_skills": sum(1 for s in defs if s.role == "troop_skill"),
        "t12": sum(1 for s in defs if s.role == "t12"),
        "unclassified": unclassified,
    }


def _side_stacks(side: str, a, d):
    return a if side == "attacker" else d


def _enemy_stacks(side: str, a, d):
    return d if side == "attacker" else a


def _stack_view(stack: TypeStack, side: str, mods: _Mods,
                channel: DamageCategory = DamageCategory.NORMAL,
                stat_floor: float = 0.25, mod_gamma: float = 1.0) -> TypeStack:
    """Stack with skill modifiers applied.

    ``mod_gamma`` compresses every composed modifier multiplier toward 1
    (diminishing returns on stacked bonuses): all three T12 anchors show that
    nominally huge kits (+45% DD, -60% debuffs) net out to a ~0.9-1.1x real
    exchange ratio, while raw multiplicative stacking predicts 3-4x.
    """
    astat = dict(stack.astat)
    for stat in (A, D, L, H):
        mult = 1.0 + mods.stat.get((side, stack.troop, stat), 0.0)
        if mod_gamma != 1.0:
            mult = mult ** mod_gamma if mult > 0.0 else 0.0
        astat[stat] *= max(stat_floor, mult)
    if channel == DamageCategory.SKILLS:
        dd = mods.skill_dd.get((side, stack.troop), 0.0)
        dt = mods.skill_dt.get((side, stack.troop), 0.0)
    else:
        dd = mods.normal_dd.get((side, stack.troop), 0.0)
        dt = mods.normal_dt.get((side, stack.troop), 0.0)
    dd_total = max(stack.dd + dd, -1.0)
    dt_total = max(stack.dt + dt, -1.0)
    if mod_gamma != 1.0:
        dd_total = (1.0 + dd_total) ** mod_gamma - 1.0
        dt_total = (1.0 + dt_total) ** mod_gamma - 1.0
    return replace(
        stack,
        astat=astat,
        dd=dd_total,
        dt=dt_total,
    )


def _target_side_for(row: SkillEffect, skill: SkillDef) -> str:
    if row.side == AffectingSide.FRIEND:
        return skill.side
    return "defender" if skill.side == "attacker" else "attacker"


def _should_suppress_own_stat_passive(skill: SkillDef, row: SkillEffect) -> bool:
    return (
        skill.suppress_own_stat_passives
        and row.side == AffectingSide.FRIEND
        and row.mechanic == SkillMechanic.STATS_BASED
        and row.attribute in STAT_ATTRS
    )


def _apply_row_to_mods(mods: _Mods, row: SkillEffect, skill: SkillDef,
                       a, d, scale: float = 1.0):
    if _should_suppress_own_stat_passive(skill, row):
        return
    target_side = _target_side_for(row, skill)
    front = _front(_side_stacks(target_side, a, d))
    front_troop = front.troop if front else None
    amount = _row_amount(row) * scale
    for troop in _receivers_for(row, front_troop):
        if troop is None:
            continue
        if row.attribute in STAT_ATTRS:
            if not skill.is_widget and skill.role in ("captain", "joiner"):
                # hero stat rows compose MULTIPLICATIVELY (GAME_RULES 6l), for
                # timed rows too: additive stacking let -25%/-25%/-60% kits
                # reach -97.8% and blow up damage through def^qd (A1 2-turn
                # blowout). _stack_view floors the composed multiplier.
                mods.mul_stat(target_side, troop, STAT_ATTRS[row.attribute], amount)
            else:
                mods.add_stat(target_side, troop, STAT_ATTRS[row.attribute], amount)
        elif row.attribute == SkillAttribute.DAMAGE_DEALT:
            mods.add_dd(target_side, troop, amount, row.damage_category)
        elif row.attribute == SkillAttribute.DAMAGE_TAKEN:
            mods.add_dt(target_side, troop, amount, row.damage_category)
        elif row.attribute == SkillAttribute.CRIT_RATE:
            mods.add_dd(target_side, troop, amount, row.damage_category)


def _apply_troop_skill_to_mods(mods: _Mods, skill: SkillDef, active: list[TroopSkill]):
    ts = skill.troop_skill
    if ts is None or ts.special is not None:
        return
    if ts.proc_chance is not None or ts.requires is not None:
        return
    amount = ts.expected_value(gate_chance_for(ts, active))
    if amount is None:
        return
    side = skill.side
    targets = list(ORDER) if ts.against == "All" else [TROOP_BY_NAME.get(ts.against)]
    if ts.attribute in (SkillAttribute.DAMAGE_DEALT, SkillAttribute.ATTACK):
        receivers = [ts.troop_type]
    else:
        receivers = [t for t in targets if t is not None]
    for troop in receivers:
        if ts.attribute in STAT_ATTRS:
            mods.add_stat(side, troop, STAT_ATTRS[ts.attribute], amount)
        elif ts.attribute == SkillAttribute.DAMAGE_DEALT:
            mods.add_dd(side, troop, amount)
        elif ts.attribute == SkillAttribute.DAMAGE_TAKEN:
            mods.add_dt(side, troop, amount)


def _apply_active_troop_skill_to_mods(mods: _Mods, skill: SkillDef):
    ts = skill.troop_skill
    if ts is None or ts.attribute is None:
        return
    if (ts.proc_chance is not None and ts.requires is None
            and ts.attribute == SkillAttribute.DAMAGE_DEALT):
        return
    amount = ts.proc_amount
    if amount is None:
        return
    side = skill.side
    troop = ts.troop_type
    if ts.attribute in STAT_ATTRS:
        mods.add_stat(side, troop, STAT_ATTRS[ts.attribute], amount)
    elif ts.attribute == SkillAttribute.DAMAGE_TAKEN:
        mods.add_dt(side, troop, amount)
    elif ts.attribute == SkillAttribute.DAMAGE_DEALT:
        mods.add_dd(side, troop, amount)


def _troop_dependents(skills: list[SkillDef]) -> dict[tuple[str, TroopType], list[SkillDef]]:
    out: dict[tuple[str, TroopType], list[SkillDef]] = defaultdict(list)
    for skill in skills:
        ts = skill.troop_skill
        if ts and ts.requires:
            out[(skill.side, ts.troop_type)].append(skill)
    return out


def _troop_proc_chance(skill: SkillDef, params: dict) -> float | None:
    ts = skill.troop_skill
    if ts is None:
        return None
    names = []
    if ts.special == "bypass_to_marksman":
        names.extend(("ambush_proc", "ambusher_proc"))
    elif ts.special == "extra_attack":
        names.extend(("volley_proc", "volley"))
    elif ts.special == "damage_offset":
        names.extend(("crystal_shield_proc", "crystal_shield"))
    elif ts.name.startswith("Crystal Lance"):
        names.extend(("crystal_lance_proc", "crystal_lance"))
    elif ts.name.startswith("Crystal Gunpowder"):
        names.extend(("crystal_gunpowder_proc", "crystal_gunpowder"))
    elif ts.name.startswith("Incandescent Field"):
        names.extend(("incandescent_field_proc", "incandescent_field"))
    for name in names:
        if name in params:
            return float(params[name])
    return ts.proc_chance


def _skill_has_modifier_rows(skill: SkillDef) -> bool:
    if skill.troop_skill:
        return not skill.deals_damage or skill.troop_skill.special == "damage_offset"
    rows = tuple(skill.rows)
    return any(not _row_is_direct_damage_for_skill(row, rows) for row in rows)


def _skill_has_dependent_mods(skill: SkillDef,
                              dependents: dict[tuple[str, TroopType], list[SkillDef]]) -> bool:
    ts = skill.troop_skill
    if ts is None:
        return False
    for dependent in dependents.get((skill.side, ts.troop_type), []):
        dts = dependent.troop_skill
        if dts and ts.name.startswith(dts.requires or ""):
            return True
    return False


def _should_track_active_effect(skill: SkillDef,
                                dependents: dict[tuple[str, TroopType], list[SkillDef]]) -> bool:
    return _skill_has_modifier_rows(skill) or _skill_has_dependent_mods(skill, dependents)


def _volley_reroll_candidates(skills: list[SkillDef], volley_skill: SkillDef) -> list[SkillDef]:
    ts = volley_skill.troop_skill
    if ts is None or ts.special != "extra_attack":
        return []
    out = []
    for skill in skills:
        other = skill.troop_skill
        if skill is volley_skill or other is None:
            continue
        if skill.side != volley_skill.side or other.troop_type != ts.troop_type:
            continue
        if other.proc_chance is None or other.special == "extra_attack":
            continue
        if other.attribute == SkillAttribute.DAMAGE_DEALT:
            out.append(skill)
    return out


def _passive_mods(skills: list[SkillDef], a, d) -> _Mods:
    mods = _Mods()
    by_side_troop: dict[tuple[str, TroopType], list[TroopSkill]] = defaultdict(list)
    for skill in skills:
        if skill.troop_skill:
            by_side_troop[(skill.side, skill.troop_skill.troop_type)].append(skill.troop_skill)
    for skill in skills:
        if skill.role == "troop_skill":
            _apply_troop_skill_to_mods(
                mods, skill, by_side_troop.get((skill.side, skill.troop), []))
            continue
        if skill.role == "t12":
            continue
        if skill.is_passive:
            for row in skill.rows:
                # Final Stats panels exclude hero skill effects; passive hero
                # stat rows are battle-time modifiers. Widget stat rows only
                # appear here for legacy/raw profiles where widgets were not
                # already included in the panel.
                _apply_row_to_mods(mods, row, skill, a, d)
    return mods


def _skill_is_alive(skill: SkillDef, stacks: dict[TroopType, TypeStack]) -> bool:
    if skill.troop is None:
        return any(st.n > EPS for st in stacks.values())
    st = stacks.get(skill.troop)
    return st is not None and st.n > EPS


def _trigger_count_for_skill(skill: SkillDef, turn: int,
                             stacks: dict[TroopType, TypeStack],
                             side_attack_events: int,
                             rng: random.Random,
                             params: dict | None = None) -> list[TroopType | None]:
    params = params or {}
    if skill.role == "t12":
        if skill.owner == "starfire":
            return [skill.troop] if (turn - 1) % 5 == 0 else []
        return [skill.troop] if turn == 1 else []
    if skill.is_passive:
        return []
    if _is_mark_companion_skill(skill):
        return []
    if not _skill_is_alive(skill, stacks):
        return []
    ts = skill.troop_skill
    if ts is not None:
        st = stacks.get(ts.troop_type)
        if st is None or st.n <= EPS:
            return []
        prob = _troop_proc_chance(skill, params)
        if prob is not None and rng.random() >= prob:
            return []
        return [ts.troop_type]

    freq = _skill_frequency(skill)
    trigger = _skill_trigger_unit(skill)
    prob = _skill_probability(skill)
    per_attack_prob = _uses_per_attack_probability(skill, prob)
    if not per_attack_prob and rng.random() >= prob:
        return []
    def alive(candidates):
        return [
            troop for troop in candidates
            if troop is None or (stacks.get(troop) is not None and stacks[troop].n > EPS)
        ]
    if freq is None:
        direct = alive(_direct_trigger_troops(skill))
        candidates = direct or alive(_modifier_trigger_troops(skill)) or [skill.troop]
        return _filter_by_probability(candidates, prob, rng) if per_attack_prob else candidates
    n = max(int(freq), 1)
    if trigger == TriggerUnit.TURNS or trigger is None:
        if turn < skill.start_turn or (turn - skill.start_turn) % n != 0:
            return []
        direct = alive(_direct_trigger_troops(skill))
        candidates = direct or alive(_modifier_trigger_troops(skill)) or [skill.troop]
        return _filter_by_probability(candidates, prob, rng) if per_attack_prob else candidates
    if trigger == TriggerUnit.STRIKES:
        fired = []
        for troop in _trigger_candidate_troops(skill):
            st = stacks.get(troop)
            if st is None:
                continue
            if st.n <= EPS:
                continue
            if (st.attacks_made + 1) % n == 0:
                fired.append(troop)
        return _filter_by_probability(fired, prob, rng) if per_attack_prob else fired
    if trigger == TriggerUnit.ATTACKS:
        fired = []
        event_no = side_attack_events
        candidates = _trigger_candidate_troops(skill)
        global_candidate = candidates == [None]
        for troop in ORDER:
            st = stacks.get(troop)
            if st is None or st.n <= EPS:
                continue
            event_no += 1
            if event_no % n != 0:
                continue
            if global_candidate:
                fired.append(None)
                continue
            if candidates and troop not in candidates and _direct_trigger_troops(skill):
                continue
            fired.append(troop if troop in candidates else (skill.troop or troop))
        return _filter_by_probability(fired, prob, rng) if per_attack_prob else fired
    if trigger == TriggerUnit.RECEIVED:
        return [skill.troop] if turn >= skill.start_turn and (turn - skill.start_turn) % n == 0 else []
    return []


def _build_mods(base: _Mods, active: list[_ActiveEffect], turn: int, a, d,
                dependents: dict[tuple[str, TroopType], list[SkillDef]] | None = None) -> _Mods:
    mods = _Mods(
        dict(base.stat),
        dict(base.normal_dd),
        dict(base.normal_dt),
        dict(base.skill_dd),
        dict(base.skill_dt),
    )
    dependents = dependents or {}
    for effect in active:
        if effect.starts_at > turn or effect.expires_after < turn:
            continue
        if effect.skill.troop_skill:
            _apply_active_troop_skill_to_mods(mods, effect.skill)
            ts = effect.skill.troop_skill
            for dependent in dependents.get((effect.skill.side, ts.troop_type), []):
                dts = dependent.troop_skill
                if dts and ts.name.startswith(dts.requires or ""):
                    _apply_active_troop_skill_to_mods(mods, dependent)
            continue
        rows = tuple(effect.skill.rows)
        for row in rows:
            if not _row_active_for_effect(effect, row, turn):
                continue
            if _row_is_direct_damage_for_skill(row, rows):
                continue
            _apply_row_to_mods(mods, row, effect.skill, a, d)
    return mods


def _damage_offsets(active: list[_ActiveEffect], turn: int) -> dict[str, float]:
    offsets: dict[str, float] = defaultdict(float)
    for effect in active:
        if effect.starts_at > turn or effect.expires_after < turn:
            continue
        ts = effect.skill.troop_skill
        if ts and ts.special == "damage_offset" and ts.flat_offset:
            offsets[effect.skill.side] += float(ts.flat_offset)
    return offsets


def _apply_offsets(packets: list[DamagePacket], offset: float) -> list[DamagePacket]:
    if offset <= 0:
        return packets
    out = []
    for pkt in packets:
        out.append(replace(pkt, magnitude=max(0.0, pkt.magnitude - offset)))
    return out


def _damage_for(src: TypeStack, target: TypeStack, own_front: TypeStack | None,
                src_side: str, target_side: str, mods: _Mods, p: dict,
                marks_dd: float,
                channel: DamageCategory = DamageCategory.NORMAL) -> float:
    floor = float(p.get("stat_floor", 0.25))
    gamma = float(p.get("mod_gamma", 1.0))
    src_v = _stack_view(src, src_side, mods, channel, stat_floor=floor, mod_gamma=gamma)
    tgt_v = _stack_view(target, target_side, mods, channel, stat_floor=floor, mod_gamma=gamma)
    # Firing strength blend between LIVE (n = current count, Lanchester taper)
    # and START (n = starting count, constant casualty rate). fire_blend in
    # [0,1]: 0 = live, 1 = start. Pure start over-fires a nearly-dead stack (a
    # 1-troop stack dealt a full-strength volley -> forced mutual annihilation
    # and a defender-favoring near-mirror bug, Martin's mirror experiments
    # 2026-07-08). A partial blend keeps the ~constant casualty-rate shape the
    # T12 anchors show while letting a dying stack taper in the endgame.
    fire_blend = p.get("fire_blend")
    if fire_blend is None:
        fire_blend = 1.0 if p.get("fire_mode", "live") == "start" else 0.0
    fire_blend = float(fire_blend)
    if fire_blend > 0.0 and src_v.n > EPS:
        n_eff = src_v.n + fire_blend * (src_v.n0 - src_v.n)
        src_v = replace(src_v, n=n_eff)
    own_front_v = src_v if own_front is src else own_front
    return base_strike_damage(src_v, tgt_v, p, own_front=own_front_v, marks_dd=marks_dd)


def _is_next_attack_dt_row(row: SkillEffect) -> bool:
    return (
        row.side == AffectingSide.FOE
        and row.attribute == SkillAttribute.DAMAGE_TAKEN
        and row.duration_unit in (TriggerUnit.ATTACKS, TriggerUnit.STRIKES,
                                  TriggerUnit.RECEIVED)
        and _row_amount(row) > 0
    )


def _instant_target_dt(skill: SkillDef, rows: tuple[SkillEffect, ...],
                       target_troop: TroopType) -> float:
    bonus = 0.0
    for row in rows:
        if _row_is_direct_damage_for_skill(row, rows):
            continue
        if not _is_next_attack_dt_row(row):
            continue
        if row.receiver != EffectReceiver.TARGET and _row_troop(row) != target_troop:
            continue
        bonus += _row_amount(row)
    return bonus


def _base_packets(side: str, own, enemy, mods: _Mods, p: dict,
                  scale: float, marks_dd: float, target_inf_dt: float,
                  target_enemy_out: float,
                  paused_troops: set[TroopType] | None = None) -> list[DamagePacket]:
    front = _front(enemy)
    if front is None:
        return []
    own_front = _front(own)
    target_side = "defender" if side == "attacker" else "attacker"
    out = []
    paused_troops = paused_troops or set()
    for src in own.values():
        if src.n <= EPS:
            continue
        if src.troop in paused_troops:
            continue
        dmg = _damage_for(src, front, own_front, side, target_side, mods, p, marks_dd,
                          DamageCategory.NORMAL)
        if front.troop == TroopType.INFANTRY:
            dmg *= target_inf_dt
        dmg *= target_enemy_out
        out.append(DamagePacket("auto", side, dmg * scale, source_troop=src.troop))
    return out


def _skill_packets(skill: SkillDef, trigger_troops: list[TroopType | None],
                   own, enemy, mods: _Mods, p: dict, scale: float,
                   marks_dd: float, target_inf_dt: float,
                   target_enemy_out: float) -> list[DamagePacket]:
    if not skill.deals_damage:
        return []
    target_side = "defender" if skill.side == "attacker" else "attacker"
    own_front = _front(own)
    packets: list[DamagePacket] = []

    if skill.troop_skill:
        ts = skill.troop_skill
        src = own.get(ts.troop_type)
        if src is None or src.n <= EPS:
            return []
        targets = skill.bypass_targets if skill.is_bypass else ()
        front = enemy.get(targets[0]) if targets else _front(enemy)
        if front is None or front.n <= EPS:
            return []
        base = _damage_for(src, front, own_front, skill.side, target_side, mods, p,
                           marks_dd, DamageCategory.NORMAL)
        if front.troop == TroopType.INFANTRY:
            base *= target_inf_dt
        base *= target_enemy_out
        amount = 1.0
        if ts.special == "bypass_to_marksman":
            amount = float(p.get("ambush_frac", 1.0))
        elif ts.special == "extra_attack":
            amount = float(ts.proc_amount or 1.0)
        elif ts.proc_amount is not None:
            amount = float(ts.proc_amount)
        packets.append(DamagePacket(
            skill, skill.side, base * amount * scale,
            "backline" if targets else "front", targets, ts.troop_type))
        return packets

    skill_rows = tuple(skill.rows)
    rows = [r for r in skill_rows if _row_is_direct_damage_for_skill(r, skill_rows)]
    dt_damage_rows = [] if rows else [r for r in skill_rows if _is_next_attack_dt_row(r)]
    for troop in trigger_troops or [skill.troop]:
        src_candidates = [own[troop]] if troop in own else [s for s in own.values() if s.n > EPS]
        for row in rows:
            row_receivers = _receivers_for(row)
            for src in src_candidates:
                if src.n <= EPS:
                    continue
                if row.receiver != EffectReceiver.TARGET and src.troop not in row_receivers:
                    continue
                targets = skill.bypass_targets
                if row.specific_target:
                    specific = TROOP_BY_NAME.get(row.specific_target)
                    if specific is not None:
                        targets = (specific,)
                front = enemy.get(targets[0]) if targets else _front(enemy)
                if front is None or front.n <= EPS:
                    continue
                base = _damage_for(src, front, own_front, skill.side, target_side,
                                   mods, p, marks_dd, DamageCategory.SKILLS)
                instant_dt = _instant_target_dt(skill, skill_rows, front.troop)
                if instant_dt:
                    base *= max(0.0, 1.0 + instant_dt)
                if front.troop == TroopType.INFANTRY:
                    base *= target_inf_dt
                base *= target_enemy_out
                amount = _row_amount(row) * float(p.get("K_skill", 1.0))
                if skill.owner.casefold() == "cara" and skill.slot == "skill_3":
                    amount *= float(p.get("cara_burst", 1.0))
                packets.append(DamagePacket(
                    skill, skill.side, base * amount * scale,
                    "backline" if targets else "front", targets, src.troop))
        for row in dt_damage_rows:
            target_troops = _receivers_for(row, _front(enemy).troop if _front(enemy) else None)
            for src in src_candidates:
                if src.n <= EPS:
                    continue
                for target_troop in target_troops:
                    front = enemy.get(target_troop)
                    if front is None or front.n <= EPS:
                        continue
                    base = _damage_for(src, front, own_front, skill.side, target_side,
                                       mods, p, marks_dd, DamageCategory.SKILLS)
                    if front.troop == TroopType.INFANTRY:
                        base *= target_inf_dt
                    base *= target_enemy_out
                    amount = _row_amount(row) * float(p.get("K_skill", 1.0))
                    packets.append(DamagePacket(
                        skill, skill.side, base * amount * scale,
                        "backline", (target_troop,), src.troop))
    return packets


def _apply_packets_full(packets: list[DamagePacket],
                        stacks: dict[TroopType, TypeStack]) -> tuple[dict, dict, dict, dict]:
    casualties = {t: 0.0 for t in stacks}
    kills_by_source: dict[str, float] = defaultdict(float)
    kills_by_troop: dict[TroopType, float] = defaultdict(float)
    # joint (attacker troop class -> victim troop class) kills. The marginals
    # above are exactly this matrix's row sums (attacker) and, on the opposing
    # side, its column sums (victim). Pure instrumentation - see
    # ENGINE_HANDOFF_kill_matrix.md.
    kills_matrix: dict[tuple[TroopType, TroopType], float] = defaultdict(float)
    for pkt in packets:
        order = list(pkt.target_types) if pkt.target_mode == "backline" else list(ORDER)
        remaining = max(0.0, pkt.magnitude)
        for troop in order:
            if remaining <= EPS:
                break
            st = stacks.get(troop)
            if st is None or st.n <= EPS:
                continue
            killed = min(st.n, remaining)
            st.n -= killed
            st.incap += killed
            casualties[troop] = casualties.get(troop, 0.0) + killed
            src_id = pkt.source.source_id if isinstance(pkt.source, SkillDef) else str(pkt.source)
            kills_by_source[src_id] += killed
            src_troop = pkt.source_troop
            if src_troop is None and isinstance(pkt.source, SkillDef):
                src_troop = pkt.source.troop
            if src_troop is not None:
                kills_by_troop[src_troop] += killed
                kills_matrix[(src_troop, troop)] += killed   # (attacker, victim)
            if isinstance(pkt.source, SkillDef):
                pkt.source.kills += killed
            remaining -= killed
    return casualties, dict(kills_by_source), dict(kills_by_troop), dict(kills_matrix)


def apply_packets(packets: list[DamagePacket],
                  stacks: dict[TroopType, TypeStack]) -> tuple[dict, dict]:
    casualties, kills_by_source, _kbt, _kmx = _apply_packets_full(packets, stacks)
    return casualties, kills_by_source


def _assert_conservation(casualties: dict, kills_by_source: dict):
    cas = sum(casualties.values())
    src = sum(kills_by_source.values())
    if abs(cas - src) > max(1e-6, cas * 1e-6):
        raise AssertionError(f"kill conservation failed: casualties={cas} sources={src}")


def _side_t12(params: dict, side: str, turn: int):
    levels = params.get("a_t12") if side == "attacker" else params.get("d_t12")
    return t12_mods(levels, turn)


def _init_passive_triggers(skills: list[SkillDef]):
    for skill in skills:
        if skill.is_passive:
            skill.triggers = 1


def simulate_turns(a_units, d_units, skills: list[SkillDef], params=None,
                   rng: random.Random | None = None, max_turns: int = 4000) -> TurnEngineResult:
    p = dict(BEST_PARAMS)
    p.update(TURN_PARAMS)
    if params:
        p.update(params)
    rng = rng or random.Random(0)
    a, d = _clone_units(a_units), _clone_units(d_units)
    base_mods = _passive_mods(skills, a, d)
    dependent_mods = _troop_dependents(skills)
    active_effects: list[_ActiveEffect] = []
    _init_passive_triggers(skills)
    turn_log: list[TurnRecord] = []
    side_attack_events = {"attacker": 0, "defender": 0}

    winner = "mutual"
    t = 0
    for t in range(1, max_turns + 1):
        if _total(a) <= EPS or _total(d) <= EPS:
            break
        start = _snapshot(a, d)
        fired: list[tuple[SkillDef, list[TroopType | None]]] = []
        paused_attacks: dict[str, set[TroopType]] = {
            "attacker": set(),
            "defender": set(),
        }
        for skill in skills:
            own = _side_stacks(skill.side, a, d)
            trigger_troops = _trigger_count_for_skill(
                skill, t, own, side_attack_events[skill.side], rng, p)
            if trigger_troops:
                skill.triggers += len(trigger_troops)
                fired.append((skill, trigger_troops))
                if _skill_pauses_attack(skill):
                    pause_troop = skill.troop or TroopType.INFANTRY
                    paused_attacks[skill.side].add(pause_troop)
                if _should_track_active_effect(skill, dependent_mods):
                    starts_at = _effect_start_turn(skill, t)
                    _add_active_effect(active_effects, _ActiveEffect(
                        skill, starts_at, starts_at + _skill_duration(skill) - 1))
                for companion in _mark_companion_skills(skills, skill):
                    companion.triggers += len(trigger_troops)
                    starts_at = t + 1
                    _add_active_effect(active_effects, _ActiveEffect(
                        companion, starts_at,
                        starts_at + _skill_duration(companion) - 1))

        mods = _build_mods(base_mods, active_effects, t, a, d, dependent_mods)
        a_md, a_idt, a_eo = _side_t12(p, "attacker", t)
        d_md, d_idt, d_eo = _side_t12(p, "defender", t)
        rate = float(p.get("rate", 1.0))
        atk_scale = rate
        def_scale = rate * float(p.get("def_k", 1.0))
        def_ed = float(p.get("def_ed", 1.0))
        d_fire_count = sum(st.n for st in d.values() if st.n > EPS)
        if def_ed != 1.0 and d_fire_count > 0:
            def_scale *= d_fire_count ** (def_ed - 1.0)
        # target-abundance (controlled farm-ladder E-11: per-turn R ~
        # N_enemy^0.571): each side's output also scales with the RECEIVER's
        # live count, normalized at 1M so `rate` keeps its magnitude. This is
        # the anti-snowball term - the anchors show near-CONSTANT absolute
        # mutual casualty rates to the end (A1 ~109k/t vs ~117k/t for 16
        # turns), not Lanchester taper. enemy_ab=0 restores the legacy form.
        enemy_ab = float(p.get("enemy_ab", 0.0))
        if enemy_ab != 0.0:
            a_fire_count = sum(st.n for st in a.values() if st.n > EPS)
            if d_fire_count > 0:
                atk_scale *= (d_fire_count / 1e6) ** enemy_ab
            if a_fire_count > 0:
                def_scale *= (a_fire_count / 1e6) ** enemy_ab

        a_packets = _base_packets(
            "attacker", a, d, mods, p, atk_scale, a_md, d_idt, d_eo,
            paused_attacks["attacker"])
        d_packets = _base_packets(
            "defender", d, a, mods, p, def_scale, d_md, a_idt, a_eo,
            paused_attacks["defender"])
        extra_attack_events: dict[tuple[str, TroopType], int] = defaultdict(int)
        for skill, trigger_troops in fired:
            own = _side_stacks(skill.side, a, d)
            enemy = _enemy_stacks(skill.side, a, d)
            scale = atk_scale if skill.side == "attacker" else def_scale
            marks_dd = a_md if skill.side == "attacker" else d_md
            target_inf_dt = d_idt if skill.side == "attacker" else a_idt
            target_enemy_out = d_eo if skill.side == "attacker" else a_eo
            packets = _skill_packets(skill, trigger_troops, own, enemy, mods, p,
                                     scale, marks_dd, target_inf_dt, target_enemy_out)
            if skill.side == "attacker":
                a_packets.extend(packets)
            else:
                d_packets.extend(packets)
            ts = skill.troop_skill
            if ts and ts.special == "extra_attack":
                extra_attack_events[(skill.side, ts.troop_type)] += len(trigger_troops)
                for candidate in _volley_reroll_candidates(skills, skill):
                    second_triggers = _trigger_count_for_skill(
                        candidate, t, own, side_attack_events[skill.side], rng, p)
                    if not second_triggers:
                        continue
                    candidate.triggers += len(second_triggers)
                    if _should_track_active_effect(candidate, dependent_mods):
                        starts_at = _effect_start_turn(candidate, t)
                        _add_active_effect(
                            active_effects,
                            _ActiveEffect(
                                candidate, starts_at,
                                starts_at + _skill_duration(candidate) - 1))
                    second_packets = _skill_packets(
                        candidate, second_triggers, own, enemy, mods, p, scale,
                        marks_dd, target_inf_dt, target_enemy_out)
                    if candidate.side == "attacker":
                        a_packets.extend(second_packets)
                    else:
                        d_packets.extend(second_packets)

        offsets = _damage_offsets(active_effects, t)
        a_packets = _apply_offsets(a_packets, offsets.get("defender", 0.0))
        d_packets = _apply_offsets(d_packets, offsets.get("attacker", 0.0))
        cas_d, kills_a, kills_a_troop, kmx_a = _apply_packets_full(a_packets, d)
        cas_a, kills_d, kills_d_troop, kmx_d = _apply_packets_full(d_packets, a)
        _assert_conservation(cas_d, kills_a)
        _assert_conservation(cas_a, kills_d)
        turn_attack_events = {"attacker": {}, "defender": {}}
        for side, stacks in (("attacker", a), ("defender", d)):
            for st in stacks.values():
                if start[side].get(st.troop, 0.0) > EPS:
                    if st.troop in paused_attacks[side]:
                        events = 0
                    else:
                        events = 1 + extra_attack_events.get((side, st.troop), 0)
                    st.attacks_made += events
                    side_attack_events[side] += events
                    turn_attack_events[side][st.troop] = events
        turn_procs, seen_proc = [], set()
        for sk, _ in fired:
            if not _is_proc_display(sk):
                continue
            key = (sk.side, sk.owner, sk.slot)
            if key in seen_proc:
                continue
            seen_proc.add(key)
            kill_map = kills_a if sk.side == "attacker" else kills_d
            turn_procs.append({"name": sk.owner, "troop": _troop_name(sk.troop),
                               "slot": sk.slot, "role": sk.role, "side": sk.side,
                               "kills": kill_map.get(sk.source_id, 0.0)})
        turn_log.append(TurnRecord(
            t, start, {"attacker": cas_a, "defender": cas_d},
            {"attacker": kills_a, "defender": kills_d},
            turn_attack_events, turn_procs,
            {"attacker": kills_a_troop, "defender": kills_d_troop},
            {"attacker": kmx_a, "defender": kmx_d}))
        aa, da = _total(a) > EPS, _total(d) > EPS
        if not aa or not da:
            winner = "mutual" if not aa and not da else "D" if not aa else "A"
            break
    else:
        winner = "A" if _total(a) >= _total(d) else "D"

    if _total(a) > EPS and _total(d) <= EPS:
        winner = "A"
    elif _total(d) > EPS and _total(a) <= EPS:
        winner = "D"
    elif _total(a) <= EPS and _total(d) <= EPS:
        winner = "mutual"

    return TurnEngineResult(
        winner=winner,
        turns=t,
        a_survivors={troop: st.n for troop, st in a.items()},
        d_survivors={troop: st.n for troop, st in d.items()},
        a_incap={troop: st.incap for troop, st in a.items()},
        d_incap={troop: st.incap for troop, st in d.items()},
        skill_telemetry=skill_telemetry(skills),
        turn_log=turn_log,
    )


def _troop_name(troop: TroopType | None):
    return troop.value if troop is not None else None


def _is_proc_display(skill: SkillDef) -> bool:
    """A skill worth showing as a per-turn proc icon: chance-based OR periodic
    (turn-based cadence). Excludes passives/statics and one-time turn-1 effects
    (T12 wall/phalanx) that 'always proc at the beginning'. Starfire (every-5) is
    the one T12 that counts."""
    if skill.is_passive:
        return False
    if skill.role == "t12":
        return skill.owner == "starfire"
    if _skill_probability(skill) < 1.0:                 # chance-based (Ambusher, Crystal Lance, hero procs)
        return True
    freq = _skill_frequency(skill)
    return bool(freq and freq > 1)                      # fires every N>1 events -> turn-based cadence


def skill_telemetry(skills: list[SkillDef]) -> dict:
    out = {
        "attacker": {"heroes": [], "troop_skills": []},
        "defender": {"heroes": [], "troop_skills": []},
    }
    hero_rows: dict[tuple[str, str, str, int], dict] = {}
    for skill in skills:
        side = skill.side
        if skill.role in ("troop_skill", "t12"):
            out[side]["troop_skills"].append({
                "name": skill.owner,
                "troop": _troop_name(skill.troop),
                "slot": skill.slot,
                "triggers": skill.triggers,
                "kills": skill.kills,
                "is_passive": skill.is_passive,
            })
            continue
        key = (side, skill.owner, skill.role, skill.ordinal)
        row = hero_rows.get(key)
        if row is None:
            row = {
                "hero": skill.owner,
                "role": skill.role,
                "troop": _troop_name(skill.troop),
                "skills": [],
            }
            hero_rows[key] = row
            out[side]["heroes"].append(row)
        row["skills"].append({
            "slot": skill.slot,
            "triggers": skill.triggers,
            "kills": skill.kills,
        })
    return out


def run_construct(construct, rng: random.Random, params=None) -> TurnEngineResult:
    merged = dict(construct.engine_params)
    if params:
        merged.update(params)
    skills = skill_defs_from_matchup(construct, merged)
    return simulate_turns(construct.attacker_units, construct.defender_units,
                          skills, params=merged, rng=rng)


def _fresh_skill_defs(templates: list[SkillDef]) -> list[SkillDef]:
    """Clone active skill definitions for one run while sharing immutable rows.

    ``SkillDef`` runtime state is only trigger/kill counters; rows and catalog
    objects are immutable. Building the active skill list requires workbook
    catalog lookups, so the batch path builds templates once and resets clones
    per simulation.
    """
    return [replace(skill, triggers=0, kills=0.0) for skill in templates]


_TL_CLASSES = (TroopType.INFANTRY, TroopType.LANCER, TroopType.MARKSMAN)


def _compact_timeline(turn_log) -> list:
    """Per turn compact timeline for the app.

    Tuple fields:
      0-1: attacker/defender alive by class after the turn
      2-3: attacker/defender casualties suffered, total
      4-5: attacker/defender casualties suffered by class
      6-7: attacker/defender kills dealt by source class
      8-9: attacker/defender kill matrix [attacker_class][victim_class] (3x3)
    """
    out = []
    for tr in turn_log:
        sa = tr.start_counts.get("attacker") or {}
        sd = tr.start_counts.get("defender") or {}
        ca = tr.casualties.get("attacker") or {}
        cd = tr.casualties.get("defender") or {}
        ka = tr.kills_by_troop.get("attacker") or {}
        kd = tr.kills_by_troop.get("defender") or {}
        ma = tr.kills_matrix.get("attacker") or {}
        md = tr.kills_matrix.get("defender") or {}
        a_alive = tuple(sa.get(t, 0.0) - ca.get(t, 0.0) for t in _TL_CLASSES)
        d_alive = tuple(sd.get(t, 0.0) - cd.get(t, 0.0) for t in _TL_CLASSES)
        a_lost = tuple(ca.get(t, 0.0) for t in _TL_CLASSES)
        d_lost = tuple(cd.get(t, 0.0) for t in _TL_CLASSES)
        a_dealt = tuple(ka.get(t, 0.0) for t in _TL_CLASSES)
        d_dealt = tuple(kd.get(t, 0.0) for t in _TL_CLASSES)
        # rows = attacker class, cols = victim class, fixed _TL_CLASSES order
        a_kmx = tuple(tuple(ma.get((atk, vic), 0.0) for vic in _TL_CLASSES) for atk in _TL_CLASSES)
        d_kmx = tuple(tuple(md.get((atk, vic), 0.0) for vic in _TL_CLASSES) for atk in _TL_CLASSES)
        out.append((a_alive, d_alive, sum(ca.values()), sum(cd.values()),
                    a_lost, d_lost, a_dealt, d_dealt, a_kmx, d_kmx))
    return out


def run_batch_construct(construct, *, n: int = 10_000, seed: int = 0,
                        params=None) -> list:
    from wos_sim.predictor.kernel import RunRecord, _fill, _run_rng, _starts

    merged = dict(construct.engine_params)
    if params:
        merged.update(params)
    skill_templates = skill_defs_from_matchup(construct, merged)
    a_start = _starts(construct.attacker_units)
    d_start = _starts(construct.defender_units)
    records = []
    for i in range(n):
        res = simulate_turns(
            construct.attacker_units,
            construct.defender_units,
            _fresh_skill_defs(skill_templates),
            params=merged,
            rng=_run_rng(seed, i),
        )
        records.append(RunRecord(
            res.winner, res.turns, a_start, d_start,
            _fill(res.a_incap, a_start), _fill(res.d_incap, d_start),
            res.skill_telemetry, _compact_timeline(res.turn_log)))
    return records
