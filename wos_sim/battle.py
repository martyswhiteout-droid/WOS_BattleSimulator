"""Battle-mechanics HYPOTHESIS engine (v0) - parameterized, to be fitted.

Nothing here is confirmed game logic; it synthesizes the best available
clues (see GAME_RULES.md section "Battle formula hypotheses"):

  H1 "ratio kernel" (community consensus - Kingshot guide, Reddit, and
  Martin's own MAIN PAGE hypothesis):
      kills per attack ~ k x N^e x (Atk x Leth x OffMod)
                             / (Def x Health x DefMod) / UnitBaseHealth
  with e ~ 0.5 (sqrt troop scaling) and modifiers composed from
  Damage Dealt / Damage Taken effects.

  H2 "two-channel" (WoS customer service): Attack damage is mitigated by
  the target's Defense; Lethality is true damage that ignores Defense and
  all damage-reduction. Available as an alternative kernel for fitting.

Damage pipeline vocabulary (per Martin):
  damage OUTPUT   = attacker side, after Damage Dealt modifiers
  damage RECEIVED = what lands on the target, after its Damage Taken
                    modifiers and (H2 only) Defense mitigation
  casualties      = damage received / unit health -> incapacitated units,
                    split into killed / severely injured / lightly injured
                    by parameterized shares (to be fitted per context).

RNG: rng_sigma > 0 applies lognormal-ish multiplicative noise per attack
event; 0 = deterministic expected-value mode (default for fitting).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace

from .mechanics import ABSORPTION_ORDER, ATTACK_SEQUENCE, LANCER_BYPASS_CHANCE
from .models import StatType, TroopType
from .troop_catalog import troop_base_stats


@dataclass
class ClassState:
    """One troop class on one side: config, final stats, modifiers, buckets."""

    troop_type: TroopType
    count: float
    tier: int = 11
    fc_level: int = 10
    # Final battle stats as MULTIPLIERS on troop base stats, i.e.
    # (1 + total bonus): attack/defense/lethality/health.
    stats: dict[StatType, float] = field(default_factory=dict)
    damage_dealt: float = 0.0   # aggregated Damage Dealt bonus (additive pool)
    damage_taken: float = 0.0   # aggregated Damage Taken bonus on this class
    killed: float = 0.0
    severely_injured: float = 0.0
    lightly_injured: float = 0.0

    def base(self, stat: StatType) -> float:
        return troop_base_stats(self.tier, self.fc_level, self.troop_type)[stat]

    def effective(self, stat: StatType) -> float:
        """Base stat x (1 + aggregated bonus)."""
        return self.base(stat) * self.stats.get(stat, 1.0)

    @property
    def alive(self) -> float:
        return max(self.count, 0.0)


@dataclass
class SideState:
    name: str
    classes: dict[TroopType, ClassState]

    def alive_total(self) -> float:
        return sum(c.alive for c in self.classes.values())

    def front_target(self) -> ClassState | None:
        """First class in absorption order with troops alive."""
        for troop in ABSORPTION_ORDER:
            if self.classes[troop].alive > 0:
                return self.classes[troop]
        return None


@dataclass
class BattleParams:
    """Every free parameter of the hypothesis, exposed for fitting."""

    model: str = "ratio"          # "ratio" (H1) or "two_channel" (H2)
    kernel_k: float = 1.0         # global damage constant
    troop_exponent: float = 0.5   # sqrt scaling per sources
    per_unit_health: bool = True  # divide by target unit base Health
    # modifier composition: "additive" per Martin (same-effect stacks sum);
    # "multiplicative" = Kingshot's cross-hero claim, kept for fitting
    modifier_stacking: str = "additive"
    # H2 mitigation form: attack_damage = Atk x mitigation(Def)
    mitigation: str = "inverse"   # "inverse": 1/Def, "fraction": Atk/(Atk+Def)
    # casualty split (fit targets; likely context-dependent)
    share_killed: float = 0.1
    share_severe: float = 0.6
    share_light: float = 0.3
    # battle flow
    max_turns: int = 20
    lancer_bypass: float = LANCER_BYPASS_CHANCE
    count_enemy_attacks: bool = False  # "Attacks" counters: own side only
    # RNG
    rng_sigma: float = 0.0
    rng_seed: int | None = None


@dataclass
class AttackLog:
    turn: int
    side: str
    attacker: TroopType
    target: TroopType
    damage_output: float
    damage_received: float
    incapacitated: float


def _noise(params: BattleParams, rng: random.Random) -> float:
    if params.rng_sigma <= 0:
        return 1.0
    return math.exp(rng.gauss(0.0, params.rng_sigma))


def _offense_mod(attacker: ClassState) -> float:
    return 1.0 + attacker.damage_dealt


def _defense_mod(target: ClassState) -> float:
    return 1.0 + target.damage_taken


def damage_kernel(attacker: ClassState, target: ClassState,
                  params: BattleParams) -> tuple[float, float]:
    """Return (damage_output, damage_received) for one attack event.

    Units are abstract "damage points"; casualties = received / unit base
    Health (per_unit_health) so the kernel reduces to the community formula:
    kills ~ k x N^e x AtkxLeth / (DefxHP) x mods / unit_hp.
    """
    n_factor = attacker.alive ** params.troop_exponent
    atk = attacker.effective(StatType.ATTACK)
    leth = attacker.effective(StatType.LETHALITY)
    dfn = target.effective(StatType.DEFENSE)
    hp = target.effective(StatType.HEALTH)

    if params.model == "ratio":
        raw = params.kernel_k * n_factor * (atk * leth) / (dfn * hp)
    elif params.model == "two_channel":
        mitigated = (atk / dfn if params.mitigation == "inverse"
                     else atk / (atk + dfn))
        raw = params.kernel_k * n_factor * (mitigated + leth) / hp
    else:
        raise ValueError(f"Unknown model {params.model!r}")

    output = raw * _offense_mod(attacker)
    received = output * _defense_mod(target)
    return output, received


def _resolve_attack(turn: int, side_name: str, attacker: ClassState,
                    defender: SideState, params: BattleParams,
                    rng: random.Random, log: list[AttackLog]) -> None:
    """One attack event: pick targets per absorption rules, apply casualties."""
    if attacker.alive <= 0:
        return
    front = defender.front_target()
    if front is None:
        return
    # Lancers leak a share of their attack directly onto Marksmen (Ambusher)
    splits: list[tuple[ClassState, float]] = [(front, 1.0)]
    marks = defender.classes[TroopType.MARKSMAN]
    if (attacker.troop_type == TroopType.LANCER and params.lancer_bypass > 0
            and front.troop_type != TroopType.MARKSMAN and marks.alive > 0):
        splits = [(front, 1.0 - params.lancer_bypass),
                  (marks, params.lancer_bypass)]

    for target, weight in splits:
        output, received = damage_kernel(attacker, target, params)
        output *= weight
        received *= weight * _noise(params, rng)
        unit_hp = target.base(StatType.HEALTH) if params.per_unit_health else 1.0
        incapacitated = min(received / unit_hp, target.alive)
        target.count -= incapacitated
        target.killed += incapacitated * params.share_killed
        target.severely_injured += incapacitated * params.share_severe
        target.lightly_injured += incapacitated * params.share_light
        log.append(AttackLog(turn, side_name, attacker.troop_type,
                             target.troop_type, output, received, incapacitated))


def simulate_battle(attacker: SideState, defender: SideState,
                    params: BattleParams | None = None
                    ) -> tuple[SideState, SideState, list[AttackLog]]:
    """Run the hypothesis engine: attacker (rally) strikes first each turn."""
    params = params or BattleParams()
    rng = random.Random(params.rng_seed)
    log: list[AttackLog] = []
    sides = {"Attacker": attacker, "Defender": defender}
    for turn in range(1, params.max_turns + 1):
        for side_name, troop in ATTACK_SEQUENCE:
            own = sides[side_name]
            other = defender if side_name == "Attacker" else attacker
            _resolve_attack(turn, side_name, own.classes[troop], other,
                            params, rng, log)
        if attacker.alive_total() <= 0 or defender.alive_total() <= 0:
            break
    return attacker, defender, log


def make_side(name: str, counts: dict[TroopType, float], tier: int = 11,
              fc_level: int = 10,
              stat_bonus: dict[tuple[TroopType, StatType], float] | None = None,
              damage_dealt: dict[TroopType, float] | None = None,
              damage_taken: dict[TroopType, float] | None = None) -> SideState:
    """Convenience builder: bonuses are decimal fractions (0.25 = +25%)."""
    classes = {}
    for troop in TroopType:
        stats = {stat: 1.0 + (stat_bonus or {}).get((troop, stat), 0.0)
                 for stat in StatType}
        classes[troop] = ClassState(
            troop_type=troop, count=counts.get(troop, 0.0), tier=tier,
            fc_level=fc_level, stats=stats,
            damage_dealt=(damage_dealt or {}).get(troop, 0.0),
            damage_taken=(damage_taken or {}).get(troop, 0.0))
    return SideState(name=name, classes=classes)
