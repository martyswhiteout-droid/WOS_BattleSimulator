"""PROPOSED per-hero-class interface (Stage 8 / hero rebuild) — for review.

Design goals (from Martin's 2026-07-25 directive + the hero-skill audit):
  * EVERY hero is its own class with explicit, individually-testable logic.
  * NO generic interpreter makes decisions; a hero DECLARES its skills using a
    shared vocabulary of CORRECT effect primitives, and a deterministic resolver
    executes them. The "decision" lives in the hero class, not a fuzzy interpreter.
  * NO fudge: procs use REAL probability + REAL cadence and are rolled against a
    seeded RNG — never an EV-averaged `amount` (that Excel-era averaging is gone).
  * The four structural gaps the flat model could not express are now first-class
    primitives: Shield (absorb), ExtraAttack, dynamic-frontline Target, and true
    proc cadence/duration.

This module is intentionally engine-independent (no import of the live engine);
it defines the CONTRACT + a handful of exemplar heroes that exercise every fixed
mechanic. The remaining 48 heroes follow the same pattern. Nothing here is wired
into api.py yet — it is a design artifact pending Martin's review.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum


# --------------------------------------------------------------------------- #
#  Vocabulary
# --------------------------------------------------------------------------- #
class Side(Enum):
    FRIEND = "Friend"      # the hero's own troops
    FOE = "Foe"            # the enemy


class Cls(Enum):
    INF = "Infantry"
    LAN = "Lancer"
    MM = "Marksman"


class Stat(Enum):
    ATK = "Attack"
    DEF = "Defense"
    LET = "Lethality"
    HP = "Health"


class Target(Enum):
    """Who an effect lands on."""
    ALL = "All"            # all three classes of the chosen side
    INF = "Infantry"
    LAN = "Lancer"
    MM = "Marksman"
    FRONTLINE = "Frontline"  # DYNAMIC: the whole first-surviving enemy class Inf->Lan->MM
    TARGET = "Target"        # the specific enemy UNIT(S) actually struck this attack
    #   (Martin 2026-07-25 / GAME_RULES §3 "Received"): a debuff "to the target" lands
    #   ONLY on the units hit — 1 Lancer striking 100 Infantry debuffs 1, not all 100.
    #   The engine scales by attacker/struck count at resolution; hero_kit leaves it
    #   unresolved. Use TARGET for every "the target" effect; FRONTLINE only for a
    #   genuine whole-class frontline effect.


class DmgKind(Enum):
    DEALT = "Damage Dealt"
    TAKEN = "Damage Taken"


class Category(Enum):
    BOTH = "Both"
    NORMAL = "Normal"
    SKILLS = "Skills"


# The one measured correction, centralised: the game's attack counter fires one
# later than the wiki's "every N attacks" wording (Vulcanus S2 measured on the
# 6th/12th/18th attack for a wiki "every 5"). Any hero written as `attacks(5)`
# resolves to a real interval of 6. Other intervals are UNMEASURED -> we do NOT
# assume the +1 there; `attacks(n, measured=True)` opts a value in explicitly.
_WIKI_TO_GAME_ATTACK_INTERVAL = {5: 6}


# --------------------------------------------------------------------------- #
#  Triggers  (when does an effect fire?)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Passive:
    """Always on for the whole battle."""


@dataclass(frozen=True)
class ChanceProc:
    """Rolls `p` (REAL probability, not an average) on each of the owner's attacks."""
    p: float


@dataclass(frozen=True)
class ScaledChance:
    """Proc whose PROBABILITY is the skill's per-level value (e.g. dodge 4/8/12/16/20%).
    The effect itself is level-independent; the level tuple supplies the chance."""


@dataclass(frozen=True)
class Cadence:
    """Fires deterministically every `interval` of `unit` ('attack' or 'turn'),
    starting at `interval` (so attacks->6/12/18, turns->3/6/9)."""
    interval: int
    unit: str            # "attack" | "turn"
    offset: int = 0      # fire at offset+interval, offset+2·interval, … (e.g. a
    #                      "next attack after the proc" clause: interval 6, offset 1
    #                      -> attacks 7/13/19). offset 0 = 6/12/18.
    def fires(self, *, attack_no: int, turn: int) -> bool:
        n = attack_no if self.unit == "attack" else turn
        return n > self.offset and (n - self.offset) % self.interval == 0


def attacks(wiki_n: int, offset: int = 0) -> Cadence:
    return Cadence(_WIKI_TO_GAME_ATTACK_INTERVAL.get(wiki_n, wiki_n), "attack", offset)


def turns(n: int) -> Cadence:
    return Cadence(n, "turn")


# --------------------------------------------------------------------------- #
#  Effect primitives  (what happens when a trigger fires?)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StatMod:
    side: Side
    target: Target
    stat: Stat
    value: float                     # +0.25 = +25%, level-resolved by the hero
    duration_turns: int | None = None


@dataclass(frozen=True)
class DamageMod:
    side: Side
    target: Target
    kind: DmgKind
    value: float
    category: Category = Category.BOTH
    duration_turns: int | None = None
    vs_class: object = None          # if set (a Cls), the bonus applies ONLY when the
    #                                  attacked enemy is this class (fixes the
    #                                  "+40% vs Lancer / +20% vs Marksman" flattening)


@dataclass(frozen=True)
class Crit:
    target: Target                   # side is implicitly FRIEND
    rate: float                      # real crit chance


@dataclass(frozen=True)
class Shield:
    """An absorb pool sized by one of the holder's stats (fixes Gatot S2/Elif S3)."""
    target: Target                   # FRIEND side implied
    scale_stat: Stat                 # e.g. Attack
    scale_pct: float                 # absorb = unit[scale_stat] * scale_pct
    duration_turns: int = 1


@dataclass(frozen=True)
class ExtraAttack:
    """An added strike (fixes Freya Reap / Reina Shadow Blade / Wayne / Hendrik)."""
    target: Target                   # FRIEND side implied (which class strikes again)
    damage_pct: float                # the strike's damage as a MULTIPLE of a normal
    #                                  attack: 1.0 = one normal attack; 2.0 = a strike
    #                                  dealing 200%; 0.40 = a strike dealing 40%.


@dataclass(frozen=True)
class DecayingDamage:
    """Damage-dealt boost that decays each attack (fixes Hector 'Rampant')."""
    side: Side
    target: Target
    start_value: float               # e.g. +2.0 (=+200%)
    decay: float                     # e.g. 0.85 (each attack = 85% of previous)
    attacks: int                     # window length, e.g. 10


# --------------------------------------------------------------------------- #
#  A skill = a per-level table of (trigger, effect-builder)
# --------------------------------------------------------------------------- #
@dataclass
class Skill:
    slot: str                        # "S1".."S3" / "Widget"
    name: str
    trigger: object                  # Passive | ChanceProc | Cadence
    # effect(level_value) -> list[primitive]; `levels` gives the 5 level values
    # for the scalable quantity (max at index 4). Non-combat skills: build=None.
    levels: tuple[float, float, float, float, float] | None
    build: object                    # callable(v: float) -> list, or None
    on_class: object = None          # if set (a Cls), this skill only triggers when
    #                                  THAT class is the one attacking ("when her
    #                                  Infantry attacks" / Strikes semantics). The engine
    #                                  supplies view.attacker_class per attack event.
    note: str = ""


# --------------------------------------------------------------------------- #
#  Battle view the resolver reads (engine supplies a concrete one)
# --------------------------------------------------------------------------- #
@dataclass
class BattleView:
    turn: int
    attack_no: int                       # global owner-side attack-event counter (ALL
    #                                       classes) — "Attacks" semantics (GAME_RULES §3)
    enemy_alive: dict                     # {Cls: count} for frontline resolution
    rng: random.Random
    attacker_class: object = None         # which own class is currently attacking, or
    #                                       None = unspecified (for "when Infantry attacks")
    strike_no: int | None = None          # the attacker_class's OWN strike counter —
    #                                       "Strikes" semantics; defaults to attack_no
    #                                       (correct in single-class scenarios).

    def __post_init__(self):
        if self.strike_no is None:
            self.strike_no = self.attack_no

    def frontline(self) -> Cls:
        for c in (Cls.INF, Cls.LAN, Cls.MM):
            if self.enemy_alive.get(c, 0) > 0:
                return c
        return Cls.INF


# --------------------------------------------------------------------------- #
#  Hero base — uniform contract the engine calls
# --------------------------------------------------------------------------- #
class Hero:
    name: str = ""
    troop: Cls = Cls.INF
    on_class_map: dict = {}          # {slot: Cls} for "when [class] attacks" skills
    #                                  (set centrally; inline Skill.on_class wins)
    def build_skills(self) -> list[Skill]:      # each hero implements this
        raise NotImplementedError

    def __init__(self, level: int = 5):
        assert 1 <= level <= 5
        self.level = level
        self._skills = self.build_skills()
        for sk in self._skills:                 # stamp class-conditioned triggers
            if sk.on_class is None and sk.slot in self.on_class_map:
                sk.on_class = self.on_class_map[sk.slot]

    def resolve(self, view: BattleView) -> list:
        """Deterministically produce the concrete effects active THIS turn.
        Rolls real proc probabilities; expands FRONTLINE to the live class."""
        out = []
        for sk in self._skills:
            if sk.build is None:
                continue                        # non-combat skill (research etc.)
            # CLASS ELIGIBILITY FIRST — before any rng.random() or cadence eval, so a
            # wrong-class attack neither fires NOR consumes the RNG stream (CRN-safe).
            # (When attacker_class is unspecified we cannot gate, so it still fires.)
            if sk.on_class is not None and view.attacker_class is not None \
                    and view.attacker_class != sk.on_class:
                continue
            trig = sk.trigger
            if isinstance(trig, Passive):
                fire = True
            elif isinstance(trig, ChanceProc):
                fire = view.attack_no > 0 and view.rng.random() < trig.p
            elif isinstance(trig, ScaledChance):
                p = sk.levels[self.level - 1] if sk.levels is not None else 0.0
                fire = view.attack_no > 0 and view.rng.random() < p
            elif isinstance(trig, Cadence):
                # A class-gated attack cadence counts the skill's OWN class strikes
                # ("Strikes", §3), not the global attack counter: "every 4 Infantry
                # strikes" must use the Infantry strike count, not global event 4.
                counter = (view.strike_no if (sk.on_class is not None and trig.unit == "attack")
                           else view.attack_no)
                fire = trig.fires(attack_no=counter, turn=view.turn)
            else:
                fire = False
            if not fire:
                continue
            v = sk.levels[self.level - 1] if sk.levels is not None else None
            for eff in sk.build(v):
                out.append(_resolve_target(eff, view))
        return out


def _resolve_target(eff, view: BattleView):
    """Replace Target.FRONTLINE with the live frontline class."""
    tgt = getattr(eff, "target", None)
    if tgt is Target.FRONTLINE:
        live = view.frontline()
        eff = eff.__class__(**{**eff.__dict__, "target": Target[live.name]})
    return eff


# =========================================================================== #
#  EXEMPLAR HEROES — one per fixed mechanic (the other 48 follow the pattern)
# =========================================================================== #
class Bradley(Hero):
    """Baseline: pure passive stat buffs (no proc, no fudge)."""
    name, troop = "Bradley", Cls.MM          # canonical (was wrongly Infantry)
    def build_skills(self):
        return [
            Skill("S1", "Veteran's Might", Passive(), (.05, .10, .15, .20, .25),
                  lambda v: [StatMod(Side.FRIEND, Target.ALL, Stat.ATK, v)]),
            # Power Shot: two separate ladders, level-scaled (QA fix: was hardcoded max).
            Skill("S2", "Power Shot", Passive(), (.05, .10, .15, .20, .25),
                  lambda v: [DamageMod(Side.FOE, Target.INF, DmgKind.TAKEN, v)]),
            Skill("S2", "Power Shot", Passive(), (.06, .12, .18, .24, .30),
                  lambda v: [DamageMod(Side.FOE, Target.LAN, DmgKind.TAKEN, v)]),
            Skill("S3", "Tactical Assistance", turns(4), (.06, .12, .18, .24, .30),
                  lambda v: [DamageMod(Side.FRIEND, Target.ALL, DmgKind.DEALT, v,
                                       duration_turns=2)]),
        ]


class Sergey(Hero):
    """Fixes a DROPPED skill: S2 was entirely missing from the codification."""
    name, troop = "Sergey", Cls.INF
    def build_skills(self):
        return [
            Skill("S1", "Defenders' Edge", Passive(), (.04, .08, .12, .16, .20),
                  lambda v: [DamageMod(Side.FRIEND, Target.ALL, DmgKind.TAKEN, -v)]),
            Skill("S2", "Weaken", Passive(), (.04, .08, .12, .16, .20),   # was 0 rows
                  lambda v: [StatMod(Side.FOE, Target.ALL, Stat.ATK, -v)]),
        ]


class Gatot(Hero):
    """Fixes the SHIELD gap: S2 is an Attack-scaled absorb per attack, NOT +Def."""
    name, troop = "Gatot", Cls.INF
    def build_skills(self):
        return [
            Skill("S1", "Golden Guard", Passive(), (.06, .12, .18, .24, .30),
                  lambda v: [StatMod(Side.FRIEND, Target.INF, Stat.DEF, v)]),
            Skill("S2", "King's Bestowal", attacks(1), (.06, .12, .18, .24, .30),
                  lambda v: [Shield(Target.INF, Stat.ATK, v, duration_turns=1)],
                  on_class=Cls.INF,
                  note="Infantry-only shield, each time INFANTRY attacks (was +30% Def)"),
            Skill("S3", "Royal Legion", Passive(), (.05, .10, .15, .20, .25),
                  lambda v: [StatMod(Side.FOE, Target.ALL, Stat.ATK, -v)]),
        ]


class Vulcanus(Hero):
    """Fixes the CADENCE: S2 fires on the game's 6/12/18 counter (wiki 'every 5')."""
    name, troop = "Vulcanus", Cls.MM
    def build_skills(self):
        return [
            Skill("S1", "Raging Storm", Passive(), (.04, .08, .12, .16, .20),
                  lambda v: [StatMod(Side.FOE, Target.ALL, Stat.ATK, -v)]),
            Skill("S2", "Breaker Steel", attacks(5), (.20, .40, .60, .80, 1.00),
                  lambda v: [DamageMod(Side.FRIEND, Target.ALL, DmgKind.DEALT, v)],
                  note="attacks(5) -> real interval 6 (measured 6/12/18)"),
            # Second clause (QA fix: was dropped): target takes +5..15% Damage Taken
            # on the next attack.
            Skill("S2", "Breaker Steel", attacks(5, offset=1), (.05, .075, .10, .125, .15),
                  lambda v: [DamageMod(Side.FOE, Target.TARGET, DmgKind.TAKEN, v,
                                       duration_turns=1)],
                  note="target +DT on the attack AFTER each every-6 proc (attacks "
                       "7/13/19), not every attack; TARGET = struck unit. Precise "
                       "arm-on-6/consume-on-7 coupling is engine-resolved."),
            Skill("S3", "True Strike", turns(3), (.12, .24, .36, .48, .60),
                  lambda v: [StatMod(Side.FOE, Target.INF, Stat.DEF, -v, duration_turns=3),
                             StatMod(Side.FOE, Target.LAN, Stat.DEF, -v, duration_turns=3),
                             StatMod(Side.FRIEND, Target.MM, Stat.ATK, v, duration_turns=1)]),
        ]


class Hector(Hero):
    """Fixes DECAY + 2x MAGNITUDE: S2 = +200%/+100% over a 10-attack x0.85 window;
    S3 'dealing 200% damage' = 2x = +100% (per_proc 1.0, not 2.0)."""
    name, troop = "Hector", Cls.INF
    def build_skills(self):
        return [
            Skill("S1", "Survival Instincts", ChanceProc(0.40), (.10, .20, .30, .40, .50),
                  lambda v: [DamageMod(Side.FRIEND, Target.ALL, DmgKind.TAKEN, -v)]),
            # Rampant: Infantry and Marksman have SEPARATE ladders (QA fix: MM was
            # wrongly derived as half the Infantry ladder).
            Skill("S2", "Rampant", Passive(), (1.00, 1.25, 1.50, 1.75, 2.00),
                  lambda v: [DecayingDamage(Side.FRIEND, Target.INF, v, 0.85, 10)],
                  note="Infantry +100..200% over a 10-attack 0.85-decay window"),
            Skill("S2", "Rampant", Passive(), (.20, .40, .60, .80, 1.00),
                  lambda v: [DecayingDamage(Side.FRIEND, Target.MM, v, 0.85, 10)],
                  note="Marksman +20..100% (own ladder, not half the Infantry one)"),
            Skill("S3", "Blitz", ChanceProc(0.25), (0.20, 0.40, 0.60, 0.80, 1.00),
                  lambda v: [DamageMod(Side.FRIEND, Target.ALL, DmgKind.DEALT, v)],
                  note="'dealing 200% damage' = 2x = +100% -> max value 1.00, not 2.00"),
        ]


class Mia(Hero):
    """Fixes DYNAMIC TARGET: the curse lands on the live frontline, not always Inf."""
    name, troop = "Mia", Cls.LAN          # canonical (was wrongly Marksman)
    def build_skills(self):
        return [
            Skill("S1", "Bad Luck Streak", ChanceProc(0.50), (.10, .20, .30, .40, .50),
                  lambda v: [DamageMod(Side.FOE, Target.TARGET, DmgKind.TAKEN, v,
                                       duration_turns=1)]),
            Skill("S2", "Lucky Charm", ChanceProc(0.50), (.10, .20, .30, .40, .50),
                  lambda v: [DamageMod(Side.FRIEND, Target.ALL, DmgKind.DEALT, v)],
                  note="'50% more damage' = Damage Dealt, not the Attack stat"),
            Skill("S3", "Ritual Deciphering", ChanceProc(0.40), (.10, .20, .30, .40, .50),
                  lambda v: [DamageMod(Side.FRIEND, Target.ALL, DmgKind.TAKEN, -v)]),
        ]


EXEMPLARS = [Bradley, Sergey, Gatot, Vulcanus, Hector, Mia]


if __name__ == "__main__":
    # Deterministic smoke test: instantiate each exemplar and resolve a few turns.
    rng = random.Random(0)
    for H in EXEMPLARS:
        h = H(level=5)
        print(f"\n=== {h.name} (L{h.level}, {h.troop.value}) ===")
        for turn in (1, 3, 6):
            view = BattleView(turn=turn, attack_no=turn,
                              enemy_alive={Cls.LAN: 100, Cls.MM: 50}, rng=random.Random(turn))
            effs = h.resolve(view)
            tag = ", ".join(type(e).__name__ + f"->{getattr(e,'target',None).value if getattr(e,'target',None) else ''}"
                            for e in effs) or "(nothing fired)"
            print(f"  turn {turn}, attack {turn}: {tag}")
