"""Input hardening — reject malformed profiles BEFORE they reach the engine,
with clear, per-field messages. Called at the api.predict boundary; the server
turns InvalidInput into a 400.
"""
from __future__ import annotations

import json
from pathlib import Path

from .profiles import CLASSES, STATS, Matchup, SideProfile

_known_heroes_cache: set | None = None


class InvalidInput(ValueError):
    """One or more profile problems. `.problems` is the human-readable list."""
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def _known_heroes() -> set:
    global _known_heroes_cache
    if _known_heroes_cache is None:
        known = set()
        try:
            from wos_sim.loader import load_skill_book
            known.update(e.hero for e in load_skill_book()._effects)
        except Exception:
            pass
        gen_path = Path(__file__).resolve().parents[1] / "data" / "hero_generations.json"
        if gen_path.exists():
            known.update(json.loads(gen_path.read_text(encoding="utf-8")).keys())
        _known_heroes_cache = known
    return _known_heroes_cache


def profile_problems(side: SideProfile, who: str) -> list:
    p = []
    if side.role not in ("rally", "garrison"):
        p.append(f"{who}: role must be 'rally' or 'garrison'")
    if side.stats_mode not in ("scouted", "pools"):
        p.append(f"{who}: stats_mode must be 'scouted' or 'pools'")
    if not side.troops_total or side.troops_total <= 0:
        p.append(f"{who}: total troops must be greater than 0")

    for c in CLASSES:
        v = side.formation.get(c, 0.0)
        if v < -1e-9 or v > 1 + 1e-9:
            p.append(f"{who}: {c} formation {v:.0%} is outside 0-100%")
    total = sum(side.formation.get(c, 0.0) for c in CLASSES)
    if abs(total - 1.0) > 0.02:
        p.append(f"{who}: formation adds to {total:.0%}, must total 100%")

    for c in CLASSES:
        q = side.quality.get(c)
        if q is None:
            continue
        if not (1 <= q.tier <= 12):
            p.append(f"{who}: {c} tier {q.tier} outside 1-12")
        if not (1 <= q.fc <= 10):
            p.append(f"{who}: {c} FC {q.fc} outside 1-10")
        if not (0 <= q.t12_stack <= 24):
            p.append(f"{who}: {c} T12 stacking {q.t12_stack} outside 0-24")

    known = _known_heroes()
    for cls, h in (side.lead_heroes or {}).items():
        if h and h not in known:
            p.append(f"{who}: unknown lead hero '{h}'")
    if len(side.joiners) > 4:
        p.append(f"{who}: at most 4 joiners ({len(side.joiners)} given)")
    for h in side.joiners:
        if h and h not in known:
            p.append(f"{who}: unknown joiner hero '{h}'")

    for k in side.panel:
        cls, stat = (k if isinstance(k, tuple) else (None, None))
        if cls not in CLASSES or stat not in STATS:
            p.append(f"{who}: bad panel key {k!r} (expected (Class, Stat))")
    return p


def validate_matchup(m: Matchup) -> None:
    problems = profile_problems(m.own, "own") + profile_problems(m.enemy, "enemy")
    if {m.own.role, m.enemy.role} != {"rally", "garrison"}:
        problems.append("matchup: exactly one side must be Rally and the other Garrison")
    if problems:
        raise InvalidInput(problems)
