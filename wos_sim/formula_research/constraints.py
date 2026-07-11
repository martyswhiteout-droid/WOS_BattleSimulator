from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
from pathlib import Path
from typing import Any

from .dataset import BattleRecord
from .models import counter_multiplier, effective_stats


@dataclass(frozen=True)
class OneVOneConstraint:
    report_id: str
    attacker_class: str
    defender_class: str
    attacker_tier: int
    defender_tier: int
    attacker_attack: float
    attacker_defense: float
    attacker_lethality: float
    attacker_health: float
    defender_attack: float
    defender_defense: float
    defender_lethality: float
    defender_health: float
    observed_winner: str
    turns_min: int
    turns_max: int
    turns_midpoint: float
    loser_health_per_midpoint_turn: float
    attacker_counter_multiplier: float
    defender_counter_multiplier: float
    input_conflict_group: str | None


def _side_key(battle: BattleRecord, side_name: str) -> tuple[Any, ...]:
    side = getattr(battle, side_name)
    return (
        side.troop_class,
        side.tier,
        side.troops,
        tuple(sorted(side.panel_pct.items())),
        side.heroes,
        tuple(sorted(side.skill_levels.items())),
    )


def modeled_input_key(battle: BattleRecord) -> tuple[Any, ...]:
    return _side_key(battle, "attacker"), _side_key(battle, "defender")


def find_input_conflicts(battles: list[BattleRecord]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[BattleRecord]] = {}
    for battle in battles:
        if battle.duplicate_of:
            continue
        groups.setdefault(modeled_input_key(battle), []).append(battle)

    conflicts: list[dict[str, Any]] = []
    for records in groups.values():
        outcomes = {
            (
                record.winner,
                record.attacker.survivors,
                record.defender.survivors,
                record.turns_min,
                record.turns_max,
            )
            for record in records
        }
        if len(records) < 2 or len(outcomes) < 2:
            continue
        conflicts.append(
            {
                "conflict_id": f"input_conflict_{len(conflicts) + 1}",
                "reports": [record.report_id for record in records],
                "observations": [
                    {
                        "report_id": record.report_id,
                        "winner": record.winner,
                        "attacker_survivors": record.attacker.survivors,
                        "defender_survivors": record.defender.survivors,
                        "turns_min": record.turns_min,
                        "turns_max": record.turns_max,
                        "counters": record.counters,
                    }
                    for record in records
                ],
            }
        )
    return conflicts


def derive_one_v_one_constraints(
    battles: list[BattleRecord],
) -> tuple[list[OneVOneConstraint], list[dict[str, Any]]]:
    conflicts = find_input_conflicts(battles)
    conflict_by_report = {
        report_id: conflict["conflict_id"]
        for conflict in conflicts
        for report_id in conflict["reports"]
    }
    rows: list[OneVOneConstraint] = []
    for battle in battles:
        if (
            battle.duplicate_of
            or battle.attacker.troops != 1
            or battle.defender.troops != 1
            or battle.turns_min is None
            or battle.turns_max is None
        ):
            continue
        attacker = effective_stats(battle.attacker, battle.defender)
        defender = effective_stats(battle.defender, battle.attacker)
        midpoint = (battle.turns_min + battle.turns_max) / 2
        loser_health = (
            defender["Health"]
            if battle.winner == "attacker"
            else attacker["Health"]
        )
        rows.append(
            OneVOneConstraint(
                report_id=battle.report_id,
                attacker_class=battle.attacker.troop_class,
                defender_class=battle.defender.troop_class,
                attacker_tier=battle.attacker.tier,
                defender_tier=battle.defender.tier,
                attacker_attack=attacker["Attack"],
                attacker_defense=attacker["Defense"],
                attacker_lethality=attacker["Lethality"],
                attacker_health=attacker["Health"],
                defender_attack=defender["Attack"],
                defender_defense=defender["Defense"],
                defender_lethality=defender["Lethality"],
                defender_health=defender["Health"],
                observed_winner=battle.winner,
                turns_min=battle.turns_min,
                turns_max=battle.turns_max,
                turns_midpoint=midpoint,
                loser_health_per_midpoint_turn=loser_health / midpoint,
                attacker_counter_multiplier=counter_multiplier(
                    battle.attacker.troop_class, battle.defender.troop_class
                ),
                defender_counter_multiplier=counter_multiplier(
                    battle.defender.troop_class, battle.attacker.troop_class
                ),
                input_conflict_group=conflict_by_report.get(battle.report_id),
            )
        )
    return rows, conflicts


def write_constraints(
    output_dir: Path,
    rows: list[OneVOneConstraint],
    conflicts: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "notes": [
            "Effective stats include captured panels and documented battle-time hero modifiers.",
            "loser_health_per_midpoint_turn is a diagnostic quotient, not an accepted damage formula.",
            "Duplicate captures receive no additional fitting weight.",
        ],
        "input_conflicts": conflicts,
        "constraints": [asdict(row) for row in rows],
    }
    (output_dir / "one_v_one_constraints.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "one_v_one_constraints.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)

    lines = [
        "# One-Unit Constraint Audit",
        "",
        f"- Unique 1v1 clocks: {len(rows)}",
        f"- Modeled-input conflicts: {len(conflicts)}",
        "- The per-turn quotient below assumes unit HP equals effective Health only as a diagnostic normalization.",
        "",
        "## Input Conflicts",
        "",
    ]
    if not conflicts:
        lines.append("None detected.")
    for conflict in conflicts:
        lines.append(f"### {conflict['conflict_id']}")
        lines.append("")
        for observation in conflict["observations"]:
            lines.append(
                f"- `{observation['report_id']}`: {observation['winner']}, "
                f"survivors {observation['attacker_survivors']}/"
                f"{observation['defender_survivors']}, turns "
                f"{observation['turns_min']}-{observation['turns_max']}"
            )
        lines.extend(
            [
                "",
                "These rows have identical modeled inputs but disjoint turn ranges. "
                "No deterministic formula using only the captured inputs can match both clocks.",
                "",
            ]
        )
    lines.extend(
        [
            "## Constraints",
            "",
            "| Report | Matchup | Effective A/D/L/H (attacker) | Effective A/D/L/H (defender) | Winner | Turns | Loser H / midpoint | Conflict |",
            "|---|---|---|---|---|---:|---:|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row.report_id} | T{row.attacker_tier} {row.attacker_class} vs "
            f"T{row.defender_tier} {row.defender_class} | "
            f"{row.attacker_attack:.6f}/{row.attacker_defense:.6f}/"
            f"{row.attacker_lethality:.6f}/{row.attacker_health:.6f} | "
            f"{row.defender_attack:.6f}/{row.defender_defense:.6f}/"
            f"{row.defender_lethality:.6f}/{row.defender_health:.6f} | "
            f"{row.observed_winner} | {row.turns_min}-{row.turns_max} | "
            f"{row.loser_health_per_midpoint_turn:.8f} | "
            f"{row.input_conflict_group or ''} |"
        )
    (output_dir / "ONE_V_ONE_CONSTRAINTS.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
