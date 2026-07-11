from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = ROOT / "wos_sim" / "data" / "experiments"

# Martin explicitly corrected this artifact on 2026-07-11. Its filename and
# source labels say Lancer-vs-Infantry while its structured sides say
# Infantry-vs-Marksman. A separate correctly named Infantry-vs-Marksman
# fixture exists, so this stale artifact is not part of the canonical 70.
EXCLUDED_FILES = {
    "NanoMart_1v1_T1LanvT1Inf_SeoYoonlvl3_Vulcanus.json": (
        "stale mislabelled artifact explicitly removed from the canonical "
        "corpus by Martin on 2026-07-11"
    ),
}

STAT_NAMES = ("Attack", "Defense", "Lethality", "Health")


@dataclass(frozen=True)
class SideRecord:
    name: str
    troop_class: str
    tier: int
    troops: int
    losses: int
    injured: int
    lightly_injured: int
    survivors: int
    panel_pct: dict[str, float]
    heroes: tuple[str, ...] = ()
    hero_skills: tuple[str, ...] = ()
    skill_levels: dict[str, int] = field(default_factory=dict)
    troop_passives: tuple[str, ...] = ()


@dataclass
class BattleRecord:
    report_id: str
    source_file: str
    source_sha256: str
    schema: str
    timestamp: str | None
    setup: str | None
    attacker: SideRecord
    defender: SideRecord
    winner: str
    turns: int | None
    turns_min: int | None
    turns_max: int | None
    turn_method: str | None
    counters: dict[str, int] = field(default_factory=dict)
    procs: list[Any] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicate_of: str | None = None
    included: bool = True
    exclusion_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8-sig")), sha256(raw).hexdigest()


def _normal_class(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "inf": "Infantry",
        "infantry": "Infantry",
        "lan": "Lancer",
        "lancer": "Lancer",
        "mar": "Marksman",
        "mm": "Marksman",
        "marks": "Marksman",
        "marksman": "Marksman",
    }
    if text not in aliases:
        raise ValueError(f"unknown deployed class {value!r}")
    return aliases[text]


def _tier(side: dict[str, Any], data: dict[str, Any]) -> int:
    if side.get("tier") is not None:
        return int(side["tier"])
    display = str(side.get("tier_display") or "")
    match = re.search(r"(?:Lv\s*|T)(\d+)", display, re.IGNORECASE)
    if match:
        return int(match.group(1))
    schema = str(data.get("_type") or "")
    if schema in {
        "nanomart_nohero_ladder",
        "nanomart_seoyoon_ladder",
        "nanomart_vulcanus_ladder",
    }:
        return 6
    setup = str(data.get("setup") or "")
    matches = re.findall(r"(?:Lv\s*|T)(\d+)", setup, re.IGNORECASE)
    if matches and len(set(matches)) == 1:
        return int(matches[0])
    raise ValueError(f"tier not captured for {side.get('name')!r}")


def _panel(side: dict[str, Any], troop_class: str) -> tuple[dict[str, float], list[str]]:
    all_stats = side.get("stats_pct") or side.get("stats_pct_visible") or {}
    class_stats = all_stats.get(troop_class) or {}
    assumptions: list[str] = []
    panel: dict[str, float] = {}
    for stat in STAT_NAMES:
        if stat in class_stats and class_stats[stat] is not None:
            panel[stat] = float(class_stats[stat])
        elif stat in {"Lethality", "Health"}:
            panel[stat] = 0.0
            assumptions.append(
                f"{stat} panel set to 0% from Martin's NanoMart/MiniMart "
                "chief-level confirmation; field is not visible in this report"
            )
        else:
            raise ValueError(f"missing {troop_class} {stat} panel")
    return panel, assumptions


def _heroes(side: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    if side.get("lead_hero"):
        values.append(str(side["lead_hero"]))
    for hero in (side.get("lead_heroes") or {}).values():
        if isinstance(hero, dict) and hero.get("name"):
            values.append(str(hero["name"]))
    return tuple(dict.fromkeys(values))


def _skills(side: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for skill in side.get("hero_skills") or []:
        if not isinstance(skill, dict):
            continue
        hero = skill.get("hero") or "unknown hero"
        slot = skill.get("slot") or "unknown slot"
        level = skill.get("level")
        effect = skill.get("effect") or skill.get("name") or "effect not captured"
        values.append(f"{hero} {slot} L{level}: {effect}")
    if side.get("lead_hero") and side.get("skill_levels"):
        for slot, level in side["skill_levels"].items():
            values.append(f"{side['lead_hero']} {slot} L{level}")
    return tuple(dict.fromkeys(values))


def _skill_levels(side: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    lead = side.get("lead_hero")
    if lead:
        for slot, level in (side.get("skill_levels") or {}).items():
            try:
                result[f"{lead}:{slot}"] = int(level)
            except (TypeError, ValueError):
                continue
    for skill in side.get("hero_skills") or []:
        if not isinstance(skill, dict) or skill.get("level") is None:
            continue
        hero = skill.get("hero") or "unknown hero"
        slot = skill.get("slot") or "unknown slot"
        result[f"{hero}:{slot}"] = int(skill["level"])
    return result


def _passives(side: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for passive in side.get("troop_passives_active") or []:
        if not isinstance(passive, dict):
            continue
        applies = passive.get("applies_in_this_battle")
        values.append(
            f"{passive.get('class')} {passive.get('skill')}: "
            f"{passive.get('effect')} (applies={applies})"
        )
    return tuple(values)


def _side(side: dict[str, Any], data: dict[str, Any]) -> tuple[SideRecord, list[str]]:
    troop_class = _normal_class(side.get("deployed_class"))
    panel, assumptions = _panel(side, troop_class)
    return (
        SideRecord(
            name=str(side.get("name") or "unknown"),
            troop_class=troop_class,
            tier=_tier(side, data),
            troops=int(side.get("troops") or 0),
            losses=int(side.get("losses") or 0),
            injured=int(side.get("injured") or 0),
            lightly_injured=int(side.get("lightly_injured") or 0),
            survivors=int(side.get("survivors") or 0),
            panel_pct=panel,
            heroes=_heroes(side),
            hero_skills=_skills(side),
            skill_levels=_skill_levels(side),
            troop_passives=_passives(side),
        ),
        assumptions,
    )


def _turns(data: dict[str, Any]) -> tuple[int | None, int | None, int | None, str | None, list[str]]:
    info = data.get("turn_inference") or {}
    assumptions = [str(v) for v in info.get("assumptions") or []]
    exact = info.get("turns")
    bounds = info.get("turns_range") or info.get("intersection")
    if exact is None:
        exact = info.get("representative_turns")
    if bounds and len(bounds) >= 2:
        low, high = int(bounds[0]), int(bounds[1])
    elif exact is not None:
        low = high = int(exact)
    else:
        low = high = None
    return (
        int(exact) if exact is not None else None,
        low,
        high,
        str(info.get("method") or info.get("skill_3_schedule_assumption") or "") or None,
        assumptions,
    )


def _counters(data: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for name, detail in (data.get("skill_details") or {}).items():
        if isinstance(detail, dict) and detail.get("triggered") is not None:
            result[str(name)] = int(detail["triggered"])
    for side_name in ("attacker", "defender"):
        for skill in (data.get(side_name) or {}).get("hero_skills") or []:
            if isinstance(skill, dict) and skill.get("triggers") is not None:
                key = f"{side_name}:{skill.get('hero')}:{skill.get('slot')}"
                result[key] = int(skill["triggers"])
    return result


def _winner(attacker: SideRecord, defender: SideRecord, data: dict[str, Any]) -> str:
    if attacker.survivors > 0 and defender.survivors == 0:
        return "attacker"
    if defender.survivors > 0 and attacker.survivors == 0:
        return "defender"
    text = str(data.get("outcome") or "").lower()
    if "attacker victory" in text or "attacker won" in text:
        return "attacker"
    if "attacker defeat" in text or "defender" in text:
        return "defender"
    if attacker.survivors == defender.survivors == 0:
        return "mutual_wipe"
    return "unknown"


def _fingerprint(record: BattleRecord) -> str:
    payload = {
        "timestamp": record.timestamp,
        "attacker": asdict(record.attacker),
        "defender": asdict(record.defender),
        "winner": record.winner,
        "turns": [record.turns_min, record.turns_max],
        "counters": record.counters,
    }
    return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def discover_nanomart() -> list[BattleRecord]:
    records: list[BattleRecord] = []
    for path in sorted(EXPERIMENT_DIR.glob("NanoMart_*.json")):
        data, digest = _read_json(path)
        attacker, attacker_assumptions = _side(data["attacker"], data)
        defender, defender_assumptions = _side(data["defender"], data)
        turns, low, high, method, turn_assumptions = _turns(data)
        timestamp = data.get("timestamp") or data.get("battle_date")
        record = BattleRecord(
            report_id=path.stem,
            source_file=str(path.relative_to(ROOT)).replace("\\", "/"),
            source_sha256=digest,
            schema=str(data.get("_type") or "unknown"),
            timestamp=str(timestamp) if timestamp else None,
            setup=str(data.get("setup") or data.get("source_heading") or "") or None,
            attacker=attacker,
            defender=defender,
            winner=_winner(attacker, defender, data),
            turns=turns,
            turns_min=low,
            turns_max=high,
            turn_method=method,
            counters=_counters(data),
            procs=list(data.get("procs") or []),
            assumptions=attacker_assumptions + defender_assumptions + turn_assumptions,
        )
        if path.name in EXCLUDED_FILES:
            record.included = False
            record.exclusion_reason = EXCLUDED_FILES[path.name]
        records.append(record)

    first_by_fingerprint: dict[str, BattleRecord] = {}
    for record in records:
        fingerprint = _fingerprint(record)
        if fingerprint in first_by_fingerprint:
            record.duplicate_of = first_by_fingerprint[fingerprint].report_id
        else:
            first_by_fingerprint[fingerprint] = record
    return records


def manifest_summary(records: list[BattleRecord]) -> dict[str, Any]:
    included = [r for r in records if r.included]
    excluded = [r for r in records if not r.included]
    duplicates = [r for r in included if r.duplicate_of]
    return {
        "discovered": len(records),
        "included": len(included),
        "excluded": len(excluded),
        "included_with_turn_evidence": sum(r.turns_min is not None for r in included),
        "included_without_turn_evidence": sum(r.turns_min is None for r in included),
        "duplicate_artifacts": len(duplicates),
        "duplicate_ids": [
            {"report_id": r.report_id, "duplicate_of": r.duplicate_of}
            for r in duplicates
        ],
        "excluded_ids": [
            {"report_id": r.report_id, "reason": r.exclusion_reason}
            for r in excluded
        ],
    }
