"""Data models for the WoS battle simulator.

Five constructs, mirroring the workbook:
  * HeroStats   - one hero, one troop type, four attribute values ("Hero Stats" tab)
  * HeroProfile - hero identity: generation, notes and avatar image ("Hero Profile" tab)
  * SkillEffect - one atomic effect line of a hero's expedition skill or widget
                  ("Hero Skills" tab); a skill spans one row per affected troop
                  type / attribute, grouped by (hero, skill source)
  * TroopStats  - 12-parameter lookup table (Troop Type x Stats Type), linked to a
                  troop tier such as "FC10 T11" ("Troop Stats" tab)
  * PlayerStats - the same 12-parameter construct, linked to a player ("Me" / "Enemy")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class TroopType(StrEnum):
    INFANTRY = "Infantry"
    LANCER = "Lancer"
    MARKSMAN = "Marksman"


class StatType(StrEnum):
    ATTACK = "Attack"
    DEFENSE = "Defense"
    LETHALITY = "Lethality"
    HEALTH = "Health"


@dataclass(frozen=True)
class HeroStats:
    """A hero's contribution: four stat values applying to one troop type."""

    name: str
    troop_type: TroopType
    values: dict[StatType, float] = field(hash=False)

    def get(self, stat: StatType) -> float:
        return self.values[stat]

    def __str__(self) -> str:
        vals = ", ".join(f"{s}={self.values[s]:g}" for s in StatType)
        return f"{self.name} ({self.troop_type}): {vals}"


class SkillSource(StrEnum):
    """Where a hero effect comes from: expedition skill slot 1-3 or the widget."""

    SKILL_1 = "Skill 1"
    SKILL_2 = "Skill 2"
    SKILL_3 = "Skill 3"
    WIDGET = "Widget"


class CombatContext(StrEnum):
    ALL = "All"
    RALLY = "Rally"
    GARRISON = "Garrison"


class AffectingSide(StrEnum):
    FRIEND = "Friend"  # buffs own troops
    FOE = "Foe"        # debuffs enemy troops


class EffectReceiver(StrEnum):
    """Who receives the effect: a troop class, or the attacked target unit."""

    INFANTRY = "Infantry"
    LANCER = "Lancer"
    MARKSMAN = "Marksman"
    TARGET = "Target"


class SkillAttribute(StrEnum):
    ATTACK = "Attack"
    DEFENSE = "Defense"
    LETHALITY = "Lethality"
    HEALTH = "Health"
    DAMAGE_DEALT = "Damage Dealt"
    DAMAGE_TAKEN = "Damage Taken"
    # Crit Rate = chance (probability column) of +100% Damage Dealt on that
    # attack, i.e. amount = probability x 1.0 expected extra Damage Dealt.
    CRIT_RATE = "Crit Rate"


class SkillMechanic(StrEnum):
    """Column "Skill Type": how the effect applies in combat."""

    STATS_BASED = "Stats-based"    # permanent passive modifier
    TURN_BASED = "Turn-based"      # procs on a turn/attack cycle
    CHANCE_BASED = "Chance-based"  # procs with a probability


class TriggerUnit(StrEnum):
    """Counting unit for proc cadence (col M) and effect duration (col O).

    TURNS    - battle turns; side- and troop-type-agnostic.
    ATTACKS  - attack events on the skill owner's side, any troop type
               (my Inf, then my Lancer, then my Marksman = 3 attacks).
    STRIKES  - attack events by the skill's OWN troop type only, own side
               (Infantry "every 5 strikes" counts only that Infantry's
               attacks - never other troop types, never the other side).
    RECEIVED - recipient-gated: the trigger counts hits received (col M),
               or the effect is active only on units that actually received
               the skill (col O) - a Lancer never touched is never affected.
    """

    TURNS = "Turns"
    ATTACKS = "Attacks"
    STRIKES = "Strikes"
    RECEIVED = "Received"


class DamageCategory(StrEnum):
    """Which damage bucket a modifier applies to."""

    BOTH = "Both"
    NORMAL = "Normal"
    SKILLS = "Skills"


class SkillCategory(StrEnum):
    OFFENSIVE = "Offensive"
    DEFENSIVE = "Defensive"
    DAMAGE_DEALT = "Damage Dealt"
    DAMAGE_TAKEN = "Damage Taken"


@dataclass(frozen=True)
class SkillEffect:
    """One row of the "Hero Skills" tab: a single atomic effect of a skill.

    amount (column H, "Average Amount %") is the max-skill-level effect size as a
    decimal fraction (wiki "4%/8%/12%/16%/20%" -> 0.2); for proc effects it is the
    expected average uplift, with the raw mechanics kept in probability /
    amount_per_proc / frequency / duration. Negative amounts are reductions.
    """

    hero: str
    source: SkillSource
    context: CombatContext           # Rally/Garrison/All
    side: AffectingSide              # Friend = buff, Foe = debuff
    receiver: EffectReceiver         # troop type receiving the effect
    attribute: SkillAttribute        # stat the effect moves
    amount: float                    # col H, decimal fraction, +/-
    mechanic: SkillMechanic          # col I "Skill Type"
    damage_category: DamageCategory  # col P
    category: SkillCategory          # col R
    specific_target: str | None = None      # col G: vs which troop type / "Target"
    probability: float | None = None        # col J: proc chance
    amount_per_proc: float | None = None    # col K: raw amount per occurrence
    frequency: float | None = None          # col L: every N trigger units
    trigger_unit: TriggerUnit | None = None  # col M: see TriggerUnit
    duration: float | None = None           # col N: effect lasts N duration units
    duration_unit: TriggerUnit | None = None  # col O: see TriggerUnit
    multiplier: str | None = None           # col Q: scaling basis, e.g. "Attack"

    def __str__(self) -> str:
        sign = "+" if self.amount >= 0 else ""
        vs = f" vs {self.specific_target}" if self.specific_target else ""
        proc = ""
        if self.mechanic != SkillMechanic.STATS_BASED and self.amount_per_proc is not None:
            proc = f" (proc {self.amount_per_proc:+.0%}"
            if self.probability is not None and self.probability != 1:
                proc += f" @ p={self.probability:g}"
            if self.duration is not None:
                proc += f", {self.duration:g} {self.duration_unit or 'turn(s)'}"
            proc += ")"
        return (f"{self.source} [{self.mechanic}] {self.side}:{self.receiver} "
                f"{self.attribute}{vs} {sign}{self.amount:.4g}{proc} "
                f"[{self.context}, dmg={self.damage_category}]")


class SkillBook:
    """All skill effect rows from the "Hero Skills" tab, queryable."""

    def __init__(self, effects: list[SkillEffect] | None = None):
        self._effects: list[SkillEffect] = list(effects or [])

    def add(self, effect: SkillEffect) -> None:
        self._effects.append(effect)

    def heroes(self) -> list[str]:
        seen: dict[str, None] = {}
        for e in self._effects:
            seen.setdefault(e.hero)
        return list(seen)

    def for_hero(self, hero: str) -> list[SkillEffect]:
        return [e for e in self._effects if e.hero == hero]

    def skills_of(self, hero: str) -> dict[SkillSource, list[SkillEffect]]:
        """A hero's effects grouped by skill slot, in canonical source order."""
        grouped: dict[SkillSource, list[SkillEffect]] = {}
        for source in SkillSource:
            rows = [e for e in self._effects if e.hero == hero and e.source == source]
            if rows:
                grouped[source] = rows
        return grouped

    def query(self, **filters) -> list[SkillEffect]:
        """Filter effects by any SkillEffect field, e.g. query(side=AffectingSide.FOE)."""
        return [e for e in self._effects
                if all(getattr(e, k) == v for k, v in filters.items())]

    def __len__(self) -> int:
        return len(self._effects)

    def __iter__(self):
        return iter(self._effects)


@dataclass(frozen=True)
class TroopSkill:
    """A troop-innate skill (canonical, from wostools.net) with raw mechanics.

    Proc skills carry proc_chance plus either proc_amount (fraction of damage,
    e.g. +1.0 = double damage / extra strike, -0.5 = half damage taken) or
    flat_offset (absolute damage points, e.g. Crystal Shield's 36).
    Effects gated on another skill being active (requires) scale their
    expected value by that skill's proc chance.
    """

    troop_type: TroopType
    name: str          # e.g. "Crystal Gunpowder II"
    unlock: str        # "T1", "T7", "FC3", "FC5", "FC8", "FC10"
    attribute: SkillAttribute | None  # None = mechanical rule, see special
    against: str       # "All" or the opposing troop type; NOTE the direction
    #                    depends on the attribute: for damage effects it is
    #                    the TARGET class, for Defense it is the ATTACKER class
    description: str
    proc_chance: float | None = None
    proc_amount: float | None = None
    flat_offset: float | None = None   # absolute damage points (magnitude)
    requires: str | None = None  # name prefix of the gating skill, if any
    # Mechanical (non-stat) behaviours the battle engine must implement:
    #   "bypass_to_marksman" - Ambusher: attack targets Marksmen directly
    #   "extra_attack"       - Volley: unit performs a second attack event
    #   "damage_offset"      - Crystal Shield: flat damage reduction per hit
    special: str | None = None

    def expected_value(self, gate_chance: float = 1.0) -> float | None:
        """EV as the workbook encodes it: chance x amount (x gate uptime).

        Returns None for purely mechanical rules (bypass, extra attack) -
        the engine simulates those from proc_chance instead of a stat EV.
        """
        if self.special in ("bypass_to_marksman", "extra_attack"):
            return None
        if self.attribute is None:
            return None
        chance = self.proc_chance if self.proc_chance is not None else 1.0
        if self.flat_offset is not None:
            return chance * self.flat_offset * gate_chance
        return chance * (self.proc_amount if self.proc_amount is not None
                         else 1.0) * gate_chance


@dataclass(frozen=True)
class TroopSkillEntry:
    """One row of the workbook's "Troop Stats" skills table (Martin's capture)."""

    troop_type: TroopType
    skill_name: str
    attribute: str | None  # raw text; None for targeting rows (Ambusher)
    against: str | None
    value: float


@dataclass(frozen=True)
class HeroProfile:
    """Hero identity from the "Hero Profile" tab, including the avatar image.

    The avatar is extracted from the workbook to avatar_path so heroes can later
    be identified from screenshots by image matching.
    """

    name: str
    troop_type: TroopType
    generation: str  # "1".."14", or "SR" for special heroes
    notes: str | None = None
    avatar_path: Path | None = None

    def __str__(self) -> str:
        avatar = self.avatar_path.name if self.avatar_path else "no avatar"
        return f"{self.name} ({self.troop_type}, gen {self.generation}) [{avatar}]"


class HeroRoster:
    """All heroes from the "Hero Stats" tab, keyed by name."""

    def __init__(self, heroes: list[HeroStats] | None = None):
        self._heroes: dict[str, HeroStats] = {}
        for hero in heroes or []:
            self.add(hero)

    def add(self, hero: HeroStats) -> None:
        if hero.name in self._heroes:
            raise ValueError(f"Duplicate hero: {hero.name}")
        self._heroes[hero.name] = hero

    def get(self, name: str) -> HeroStats:
        return self._heroes[name]

    def by_troop_type(self, troop_type: TroopType) -> list[HeroStats]:
        return [h for h in self._heroes.values() if h.troop_type == troop_type]

    def names(self) -> list[str]:
        return list(self._heroes)

    def __len__(self) -> int:
        return len(self._heroes)

    def __iter__(self):
        return iter(self._heroes.values())

    def __contains__(self, name: str) -> bool:
        return name in self._heroes


class StatTable:
    """12-parameter lookup: (Troop Type, Stats Type) -> value.

    The shared construct behind TroopStats and PlayerStats. Rows enumerate in
    canonical order: Infantry A/D/L/H, Lancer A/D/L/H, Marksman A/D/L/H.
    """

    def __init__(self, values: dict[tuple[TroopType, StatType], float] | None = None):
        self._values: dict[tuple[TroopType, StatType], float] = {
            (troop, stat): 0.0 for troop in TroopType for stat in StatType
        }
        for key, value in (values or {}).items():
            self.set(*key, value)

    def get(self, troop_type: TroopType, stat_type: StatType) -> float:
        """Look up the value for a (Troop Type, Stats Type) pair."""
        return self._values[(troop_type, stat_type)]

    def set(self, troop_type: TroopType, stat_type: StatType, value: float) -> None:
        key = (TroopType(troop_type), StatType(stat_type))
        self._values[key] = float(value)

    def rows(self):
        """Yield (troop_type, stat_type, value) rows in canonical order."""
        for troop in TroopType:
            for stat in StatType:
                yield troop, stat, self._values[(troop, stat)]

    def as_dict(self) -> dict[tuple[TroopType, StatType], float]:
        return dict(self._values)

    def format_table(self, title: str) -> str:
        lines = [title, f"{'Troop Type':<10}  {'Stats Type':<10}  {'Value':>8}"]
        lines += [f"{t:<10}  {s:<10}  {v:>8g}" for t, s, v in self.rows()]
        return "\n".join(lines)


class TroopStats(StatTable):
    """Troop base-stat lookup table for one troop tier (e.g. "FC10 T11")."""

    def __init__(self, tier: str,
                 values: dict[tuple[TroopType, StatType], float] | None = None):
        super().__init__(values)
        self.tier = tier

    def __str__(self) -> str:
        return self.format_table(f"Troop Stats [{self.tier}]")


class PlayerStats(StatTable):
    """A player's 12 combat stats - same construct as TroopStats, linked to a player."""

    def __init__(self, player: str,
                 values: dict[tuple[TroopType, StatType], float] | None = None):
        super().__init__(values)
        self.player = player

    def __str__(self) -> str:
        return self.format_table(f"Player Stats [{self.player}]")
