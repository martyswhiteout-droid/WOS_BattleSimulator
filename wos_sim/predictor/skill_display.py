"""Display metadata for skill telemetry rows.

The engine owns the numeric telemetry. This module only enriches that telemetry
with names, icon paths, and max-level tooltip text for the UI.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "skill_display"


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


@lru_cache(maxsize=1)
def _hero_data() -> dict:
    path = DATA_DIR / "hero_skills.json"
    if not path.exists():
        return {"heroes": {}}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _troop_data() -> dict:
    path = DATA_DIR / "troop_skills.json"
    if not path.exists():
        return {"normal": {}, "t12": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def hero_skill(hero: str | None, slot: str | None) -> dict:
    """Return display metadata for one hero expedition skill slot."""
    hero_record = (_hero_data().get("heroes") or {}).get(hero or "", {})
    for skill in hero_record.get("skills") or []:
        if skill.get("slot") == slot:
            return {
                "name": skill.get("name") or slot or "Skill",
                "icon": skill.get("icon"),
                "effect": skill.get("effect") or "",
            }
    label = (slot or "skill").replace("_", " ").title()
    return {"name": label, "icon": None, "effect": ""}


def troop_skill(name: str | None) -> dict:
    """Return display metadata for a troop or T12 skill name/key."""
    key = _norm(name)
    data = _troop_data()
    for section in ("normal", "t12"):
        for fallback_key, record in (data.get(section) or {}).items():
            aliases = [fallback_key, record.get("name", ""), *record.get("aliases", [])]
            if key in {_norm(alias) for alias in aliases}:
                return {
                    "name": record.get("name") or name or "Troop Skill",
                    "icon": record.get("icon"),
                    "effect": record.get("effect") or "",
                    "troop": record.get("troop"),
                }
    label = (name or "troop_skill").replace("_", " ").title()
    return {"name": label, "icon": None, "effect": "", "troop": None}
