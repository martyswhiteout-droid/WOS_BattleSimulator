from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

from wos_sim.models import StatType, TroopType
from wos_sim.troop_catalog import troop_base_stats

from .dataset import BattleRecord, SideRecord


CLASS_TO_ENUM = {
    "Infantry": TroopType.INFANTRY,
    "Lancer": TroopType.LANCER,
    "Marksman": TroopType.MARKSMAN,
}


@dataclass(frozen=True)
class SimulationResult:
    winner: str
    turns: int
    attacker_survivors: int
    defender_survivors: int


class Model(Protocol):
    name: str

    def simulate(self, battle: BattleRecord) -> SimulationResult: ...


def _has_hero(side: SideRecord, name: str) -> bool:
    target = name.casefold()
    return any(hero.casefold() == target for hero in side.heroes)


def _skill_level(side: SideRecord, hero: str, slot: str, default: int = 0) -> int:
    return int(side.skill_levels.get(f"{hero}:{slot}", default))


def effective_stats(side: SideRecord, opponent: SideRecord) -> dict[str, float]:
    troop = CLASS_TO_ENUM[side.troop_class]
    base = troop_base_stats(side.tier, 0, troop)
    values = {
        "Attack": base[StatType.ATTACK] * (1 + side.panel_pct["Attack"] / 100),
        "Defense": base[StatType.DEFENSE] * (1 + side.panel_pct["Defense"] / 100),
        "Lethality": base[StatType.LETHALITY]
        * (1 + side.panel_pct["Lethality"] / 100),
        "Health": base[StatType.HEALTH] * (1 + side.panel_pct["Health"] / 100),
    }

    seo_level = _skill_level(side, "Seo-yoon", "Skill 1")
    if seo_level:
        values["Attack"] *= 1 + 0.05 * seo_level

    # DeepSeek's delivered model only specifies the level-1 Vulcanus values
    # used by the controlled corpus.
    if _has_hero(opponent, "Vulcanus"):
        values["Attack"] *= 0.96
        if side.troop_class in {"Infantry", "Lancer"}:
            values["Defense"] *= 0.88
    return values


def counter_multiplier(attacker_class: str, defender_class: str) -> float:
    counters = {
        ("Infantry", "Lancer"),
        ("Lancer", "Marksman"),
        ("Marksman", "Infantry"),
    }
    return 1.10 if (attacker_class, defender_class) in counters else 1.0


@dataclass(frozen=True)
class DeepSeekKernel:
    """The constants and ordering from DeepSeek's delivered specification."""

    alpha: float = 1 / 32
    beta: float = 1 / 64
    gamma: float = 1 / 80
    delta: float = 1 / 80

    def damage(self, attack: float, lethality: float, defense: float, health: float) -> float:
        raw = max(0.0, self.alpha * attack - self.beta * defense)
        raw += self.gamma * lethality
        return min(raw, self.delta * health)


class DeepSeekRepairedHPModel:
    """Charitable replay: keep DeepSeek's mechanics but conserve total HP."""

    name = "deepseek_repaired_hp"

    def __init__(self, max_turns: int = 100_000):
        self.kernel = DeepSeekKernel()
        self.max_turns = max_turns

    def simulate(self, battle: BattleRecord) -> SimulationResult:
        attacker_stats = effective_stats(battle.attacker, battle.defender)
        defender_stats = effective_stats(battle.defender, battle.attacker)
        attacker_hp = battle.attacker.troops * attacker_stats["Health"]
        defender_hp = battle.defender.troops * defender_stats["Health"]
        turn = 0

        while attacker_hp > 0 and defender_hp > 0 and turn < self.max_turns:
            turn += 1
            attacker_live = math.ceil(attacker_hp / attacker_stats["Health"])
            defender_live = math.ceil(defender_hp / defender_stats["Health"])

            attacker_damage = self.kernel.damage(
                attacker_stats["Attack"],
                attacker_stats["Lethality"],
                defender_stats["Defense"],
                defender_stats["Health"],
            )
            attacker_damage *= counter_multiplier(
                battle.attacker.troop_class, battle.defender.troop_class
            )
            defender_damage = self.kernel.damage(
                defender_stats["Attack"],
                defender_stats["Lethality"],
                attacker_stats["Defense"],
                attacker_stats["Health"],
            )
            defender_damage *= counter_multiplier(
                battle.defender.troop_class, battle.attacker.troop_class
            )

            if _has_hero(battle.attacker, "Vulcanus") and turn % 6 == 0:
                attacker_damage *= 1.20
            if _has_hero(battle.defender, "Vulcanus") and turn % 6 == 0:
                defender_damage *= 1.20

            next_attacker_hp = attacker_hp - math.sqrt(defender_live) * defender_damage
            next_defender_hp = defender_hp - math.sqrt(attacker_live) * attacker_damage
            attacker_hp = next_attacker_hp
            defender_hp = next_defender_hp

        attacker_survivors = max(0, math.ceil(attacker_hp / attacker_stats["Health"]))
        defender_survivors = max(0, math.ceil(defender_hp / defender_stats["Health"]))
        winner = _winner(attacker_survivors, defender_survivors)
        return SimulationResult(winner, turn, attacker_survivors, defender_survivors)


class DeepSeekPublishedModel:
    """Literal replay of the delivered pseudocode, including HP remainder loss."""

    name = "deepseek_published"

    def __init__(self, max_turns: int = 100_000):
        self.kernel = DeepSeekKernel()
        self.max_turns = max_turns

    def simulate(self, battle: BattleRecord) -> SimulationResult:
        attacker_stats = effective_stats(battle.attacker, battle.defender)
        defender_stats = effective_stats(battle.defender, battle.attacker)
        attacker_troops = battle.attacker.troops
        defender_troops = battle.defender.troops
        attacker_hp = attacker_troops * attacker_stats["Health"]
        defender_hp = defender_troops * defender_stats["Health"]
        turn = 0

        while attacker_troops > 0 and defender_troops > 0 and turn < self.max_turns:
            turn += 1
            attacker_damage = self.kernel.damage(
                attacker_stats["Attack"],
                attacker_stats["Lethality"],
                defender_stats["Defense"],
                defender_stats["Health"],
            ) * counter_multiplier(
                battle.attacker.troop_class, battle.defender.troop_class
            )
            defender_damage = self.kernel.damage(
                defender_stats["Attack"],
                defender_stats["Lethality"],
                attacker_stats["Defense"],
                attacker_stats["Health"],
            ) * counter_multiplier(
                battle.defender.troop_class, battle.attacker.troop_class
            )
            if _has_hero(battle.attacker, "Vulcanus") and turn % 6 == 0:
                attacker_damage *= 1.20
            if _has_hero(battle.defender, "Vulcanus") and turn % 6 == 0:
                defender_damage *= 1.20

            defender_hp -= math.sqrt(attacker_troops) * attacker_damage
            attacker_hp -= math.sqrt(defender_troops) * defender_damage
            attacker_troops = max(0, int(attacker_hp // attacker_stats["Health"]))
            defender_troops = max(0, int(defender_hp // defender_stats["Health"]))
            attacker_hp %= attacker_stats["Health"]
            defender_hp %= defender_stats["Health"]

        return SimulationResult(
            _winner(attacker_troops, defender_troops),
            turn,
            attacker_troops,
            defender_troops,
        )


def _winner(attacker_survivors: int, defender_survivors: int) -> str:
    if attacker_survivors > 0 and defender_survivors == 0:
        return "attacker"
    if defender_survivors > 0 and attacker_survivors == 0:
        return "defender"
    if attacker_survivors == defender_survivors == 0:
        return "mutual_wipe"
    return "unresolved"
