"""Profile schema (BRD S.9) — the config the UI collects, as typed data.

One SideProfile per combatant. A Matchup pairs own + enemy. Role decides who
attacks: rally attacks garrison. Under the current browser contract, ``panel``
is the Final Stats panel: the front-end has already folded base assumptions,
lead hero generation, buffs, and widgets into it. The rebuilt turn engine uses
that panel directly and applies hero skills only during battle.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CLASSES = ("Infantry", "Lancer", "Marksman")
STATS = ("Attack", "Defense", "Lethality", "Health")


@dataclass
class ClassQuality:
    """Per-class troop quality (troop-quality control in the UI)."""
    tier: float = 12.0      # 10, 10.5, 11, 11.5, 12
    fc: int = 10            # 1..10
    t12_stack: int = 24     # 0..24 — E-7: not yet modelled in-engine, carried through


@dataclass
class SideProfile:
    label: str = ""
    role: str = "rally"                       # "rally" | "garrison"
    troops_total: int = 1_000_000
    formation: dict = field(default_factory=lambda: {"Infantry": 0.5, "Lancer": 0.2, "Marksman": 0.3})
    # exact per-class troop counts (the numbers the user typed). When present these
    # are used DIRECTLY as each class's count; `formation` (fractions) is the fallback.
    formation_counts: dict = field(default_factory=dict)
    quality: dict = field(default_factory=lambda: {c: ClassQuality() for c in CLASSES})
    # how the panel is interpreted (GAME_RULES 6h):
    #   "scouted" -> displayed net value; already includes item/widget/pet buffs
    #               and nets enemy debuffs -> effective = base x (1+panel)
    #   "pools"   -> raw std pool; buffs added on top from own_buffs/debuffs_on_enemy
    stats_mode: str = "scouted"
    # stat-bonus panel as fractions per (class, stat): 1096% -> 10.96
    panel: dict = field(default_factory=dict)
    # True when the app has already folded base assumptions + lead generation +
    # item/pet buffs + widgets into `panel`. This bypasses the legacy
    # symmetric-scouted relayer and suppresses widget stat rows.
    panel_is_final: bool = False
    # additive own buff pool per stat (item + pet on own troops): +20% -> 0.20
    own_buffs: dict = field(default_factory=dict)
    # magnitude of debuffs THIS side applies to the enemy per stat: enemy -20% -> 0.20
    debuffs_on_enemy: dict = field(default_factory=dict)
    # None -> default by stats_mode: scouted panels already include widgets,
    # pools/raw panels do not. Set explicitly to override that assumption.
    widgets_in_panel: bool | None = None
    lead_heroes: dict = field(default_factory=dict)   # {class: hero_name}
    joiners: list = field(default_factory=list)        # [hero_name, ...] (top 4)


@dataclass
class Matchup:
    own: SideProfile
    enemy: SideProfile

    @property
    def own_is_attacker(self) -> bool:
        return self.own.role == "rally"
