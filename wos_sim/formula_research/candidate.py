from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Protocol

from .dataset import BattleRecord
from .models import (
    SimulationResult,
    _has_hero,
    _winner,
    counter_multiplier,
    effective_stats,
)


class DamageKernel(Protocol):
    def damage(
        self, attack: float, lethality: float, defense: float, health: float
    ) -> float: ...


@dataclass(frozen=True)
class SharedMechanics:
    hp_exponent: float
    frontage_exponent: float
    vulcanus_s2_cadence: int
    vulcanus_s2_multiplier: float = 1.20
    minimum_hp_fraction: float = 0.0


@dataclass(frozen=True)
class PowerLawKernel:
    log_scale: float
    attack_exponent: float
    defense_exponent: float
    lethality_exponent: float
    target_health_exponent: float

    def damage(
        self, attack: float, lethality: float, defense: float, health: float
    ) -> float:
        return math.exp(self.log_scale) * (
            max(attack, 1e-12) ** self.attack_exponent
            * max(lethality, 1e-12) ** self.lethality_exponent
            / max(defense, 1e-12) ** self.defense_exponent
            / max(health, 1e-12) ** self.target_health_exponent
        )


@dataclass(frozen=True)
class AffineKernel:
    log_scale: float
    defense_weight: float
    lethality_weight: float
    positive_floor: float
    target_health_exponent: float

    def damage(
        self, attack: float, lethality: float, defense: float, health: float
    ) -> float:
        core = max(
            self.positive_floor,
            attack - self.defense_weight * defense + self.lethality_weight * lethality,
        )
        return math.exp(self.log_scale) * core / (
            max(health, 1e-12) ** self.target_health_exponent
        )


class CandidateModel:
    def __init__(
        self,
        family: str,
        kernel: DamageKernel,
        mechanics: SharedMechanics,
        max_turns: int = 500,
        name: str | None = None,
    ):
        self.family = family
        self.kernel = kernel
        self.mechanics = mechanics
        self.max_turns = max_turns
        self.name = name or f"candidate_{family}_c{mechanics.vulcanus_s2_cadence}"

    def simulate(self, battle: BattleRecord) -> SimulationResult:
        attacker_stats = effective_stats(battle.attacker, battle.defender)
        defender_stats = effective_stats(battle.defender, battle.attacker)
        attacker_unit_hp = attacker_stats["Health"] ** self.mechanics.hp_exponent
        defender_unit_hp = defender_stats["Health"] ** self.mechanics.hp_exponent
        attacker_hp = battle.attacker.troops * attacker_unit_hp
        defender_hp = battle.defender.troops * defender_unit_hp
        turn = 0

        attacker_unit_damage = self.kernel.damage(
            attacker_stats["Attack"],
            attacker_stats["Lethality"],
            defender_stats["Defense"],
            defender_stats["Health"],
        ) * counter_multiplier(
            battle.attacker.troop_class, battle.defender.troop_class
        )
        defender_unit_damage = self.kernel.damage(
            defender_stats["Attack"],
            defender_stats["Lethality"],
            attacker_stats["Defense"],
            attacker_stats["Health"],
        ) * counter_multiplier(
            battle.defender.troop_class, battle.attacker.troop_class
        )
        attacker_unit_damage = max(
            attacker_unit_damage,
            self.mechanics.minimum_hp_fraction * defender_unit_hp,
        )
        defender_unit_damage = max(
            defender_unit_damage,
            self.mechanics.minimum_hp_fraction * attacker_unit_hp,
        )
        attacker_has_vulcanus = _has_hero(battle.attacker, "Vulcanus")
        defender_has_vulcanus = _has_hero(battle.defender, "Vulcanus")

        if battle.attacker.troops == battle.defender.troops == 1:
            return self._simulate_one_v_one(
                battle,
                attacker_hp,
                defender_hp,
                attacker_unit_hp,
                defender_unit_hp,
                attacker_unit_damage,
                defender_unit_damage,
                attacker_has_vulcanus,
                defender_has_vulcanus,
            )

        while attacker_hp > 0 and defender_hp > 0 and turn < self.max_turns:
            turn += 1
            attacker_live = math.ceil(attacker_hp / attacker_unit_hp)
            defender_live = math.ceil(defender_hp / defender_unit_hp)
            attacker_damage = (
                attacker_live ** self.mechanics.frontage_exponent
            ) * attacker_unit_damage
            defender_damage = (
                defender_live ** self.mechanics.frontage_exponent
            ) * defender_unit_damage

            cadence = self.mechanics.vulcanus_s2_cadence
            if attacker_has_vulcanus and turn % cadence == 0:
                attacker_damage *= self.mechanics.vulcanus_s2_multiplier
            if defender_has_vulcanus and turn % cadence == 0:
                defender_damage *= self.mechanics.vulcanus_s2_multiplier

            attacker_hp, defender_hp = (
                attacker_hp - defender_damage,
                defender_hp - attacker_damage,
            )

        attacker_survivors = max(0, math.ceil(attacker_hp / attacker_unit_hp))
        defender_survivors = max(0, math.ceil(defender_hp / defender_unit_hp))
        return SimulationResult(
            _winner(attacker_survivors, defender_survivors),
            turn,
            attacker_survivors,
            defender_survivors,
        )

    def _simulate_one_v_one(
        self,
        battle: BattleRecord,
        attacker_hp: float,
        defender_hp: float,
        attacker_unit_hp: float,
        defender_unit_hp: float,
        attacker_unit_damage: float,
        defender_unit_damage: float,
        attacker_has_vulcanus: bool,
        defender_has_vulcanus: bool,
    ) -> SimulationResult:
        cadence = self.mechanics.vulcanus_s2_cadence
        pulse = self.mechanics.vulcanus_s2_multiplier - 1.0

        def cumulative(base: float, turns: int, has_vulcanus: bool) -> float:
            pulses = turns // cadence if has_vulcanus else 0
            return base * (turns + pulse * pulses)

        def turns_to_kill(base: float, hp: float, has_vulcanus: bool) -> int:
            if cumulative(base, self.max_turns, has_vulcanus) + 1e-12 < hp:
                return self.max_turns + 1
            low, high = 1, self.max_turns
            while low < high:
                middle = (low + high) // 2
                if cumulative(base, middle, has_vulcanus) + 1e-12 >= hp:
                    high = middle
                else:
                    low = middle + 1
            return low

        attacker_ttk = turns_to_kill(
            attacker_unit_damage,
            defender_hp,
            attacker_has_vulcanus,
        )
        defender_ttk = turns_to_kill(
            defender_unit_damage,
            attacker_hp,
            defender_has_vulcanus,
        )
        turn = min(attacker_ttk, defender_ttk, self.max_turns)
        attacker_hp -= cumulative(
            defender_unit_damage,
            turn,
            defender_has_vulcanus,
        )
        defender_hp -= cumulative(
            attacker_unit_damage,
            turn,
            attacker_has_vulcanus,
        )
        attacker_survivors = max(0, math.ceil(attacker_hp / attacker_unit_hp))
        defender_survivors = max(0, math.ceil(defender_hp / defender_unit_hp))
        return SimulationResult(
            _winner(attacker_survivors, defender_survivors),
            turn,
            attacker_survivors,
            defender_survivors,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "kernel": asdict(self.kernel),
            "mechanics": asdict(self.mechanics),
            "max_turns": self.max_turns,
        }


def model_from_dict(data: dict[str, Any]) -> CandidateModel:
    family = str(data["family"])
    if family == "power_law":
        kernel: DamageKernel = PowerLawKernel(**data["kernel"])
    elif family == "affine":
        kernel = AffineKernel(**data["kernel"])
    else:
        raise ValueError(f"unknown candidate family {family!r}")
    return CandidateModel(
        family,
        kernel,
        SharedMechanics(**data["mechanics"]),
        max_turns=int(data.get("max_turns", 500)),
        name=data.get("name"),
    )
