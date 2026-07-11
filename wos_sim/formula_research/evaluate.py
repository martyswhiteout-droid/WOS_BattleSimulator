from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
from pathlib import Path
import math
import statistics
from typing import Any

from .dataset import BattleRecord
from .models import Model, SimulationResult


@dataclass(frozen=True)
class Residual:
    report_id: str
    duplicate_of: str | None
    observed_winner: str
    predicted_winner: str
    winner_match: bool
    observed_turns: int | None
    observed_turns_min: int | None
    observed_turns_max: int | None
    predicted_turns: int
    turn_error: int | None
    turn_match: bool | None
    observed_attacker_survivors: int
    predicted_attacker_survivors: int
    attacker_survivor_error: int
    observed_defender_survivors: int
    predicted_defender_survivors: int
    defender_survivor_error: int
    survivor_match: bool


def residual(battle: BattleRecord, result: SimulationResult) -> Residual:
    if battle.turns_min is None:
        turn_match = None
        turn_error = None
    else:
        turn_match = battle.turns_min <= result.turns <= battle.turns_max
        if turn_match:
            turn_error = 0
        elif result.turns < battle.turns_min:
            turn_error = result.turns - battle.turns_min
        else:
            turn_error = result.turns - battle.turns_max
    attacker_error = result.attacker_survivors - battle.attacker.survivors
    defender_error = result.defender_survivors - battle.defender.survivors
    return Residual(
        report_id=battle.report_id,
        duplicate_of=battle.duplicate_of,
        observed_winner=battle.winner,
        predicted_winner=result.winner,
        winner_match=battle.winner == result.winner,
        observed_turns=battle.turns,
        observed_turns_min=battle.turns_min,
        observed_turns_max=battle.turns_max,
        predicted_turns=result.turns,
        turn_error=turn_error,
        turn_match=turn_match,
        observed_attacker_survivors=battle.attacker.survivors,
        predicted_attacker_survivors=result.attacker_survivors,
        attacker_survivor_error=attacker_error,
        observed_defender_survivors=battle.defender.survivors,
        predicted_defender_survivors=result.defender_survivors,
        defender_survivor_error=defender_error,
        survivor_match=attacker_error == 0 and defender_error == 0,
    )


def evaluate(model: Model, battles: list[BattleRecord]) -> tuple[list[Residual], dict[str, Any]]:
    rows = [residual(battle, model.simulate(battle)) for battle in battles]
    turn_rows = [row for row in rows if row.turn_match is not None]
    absolute_turn_errors = [abs(row.turn_error or 0) for row in turn_rows]
    absolute_survivor_errors = [
        abs(row.attacker_survivor_error) + abs(row.defender_survivor_error)
        for row in rows
    ]
    summary = {
        "model": model.name,
        "reports": len(rows),
        "winner_matches": sum(row.winner_match for row in rows),
        "survivor_matches": sum(row.survivor_match for row in rows),
        "reports_with_turn_evidence": len(turn_rows),
        "turn_matches": sum(bool(row.turn_match) for row in turn_rows),
        "turn_mae": statistics.mean(absolute_turn_errors) if absolute_turn_errors else None,
        "turn_median_absolute_error": (
            statistics.median(absolute_turn_errors) if absolute_turn_errors else None
        ),
        "turn_max_absolute_error": max(absolute_turn_errors) if absolute_turn_errors else None,
        "survivor_total_mae": statistics.mean(absolute_survivor_errors),
        "status": "REJECTED",
        "classification_rule": (
            "EXACT requires every winner, survivor pair, and available turn range; "
            "PARTIAL requires at least 90% winner matches and at least 50% of both "
            "survivor pairs and available turn ranges"
        ),
    }
    if (
        summary["winner_matches"] == len(rows)
        and summary["survivor_matches"] == len(rows)
        and summary["turn_matches"] == len(turn_rows)
    ):
        summary["status"] = "EXACT"
    elif (
        summary["winner_matches"] >= math.ceil(0.90 * len(rows))
        and summary["survivor_matches"] >= math.ceil(0.50 * len(rows))
        and summary["turn_matches"] >= math.ceil(0.50 * len(turn_rows))
    ):
        summary["status"] = "PARTIAL"
    return rows, summary


def write_evaluation(
    output_dir: Path,
    model: Model,
    rows: list[Residual],
    summary: dict[str, Any],
    equation_checks: list[dict[str, Any]] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = model.name
    payload = {
        "summary": summary,
        "equation_checks": equation_checks or [],
        "residuals": [asdict(row) for row in rows],
    }
    (output_dir / f"{stem}.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )

    with (output_dir / f"{stem}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)

    lines = [
        f"# {model.name} Evaluation",
        "",
        f"Status: **{summary['status']}**",
        "",
        f"- Reports: {summary['reports']}",
        f"- Winner matches: {summary['winner_matches']}/{summary['reports']}",
        f"- Survivor matches: {summary['survivor_matches']}/{summary['reports']}",
        f"- Turn matches: {summary['turn_matches']}/{summary['reports_with_turn_evidence']}",
        f"- Turn MAE: {summary['turn_mae']}",
        f"- Turn median absolute error: {summary['turn_median_absolute_error']}",
        f"- Turn maximum absolute error: {summary['turn_max_absolute_error']}",
        f"- Survivor total MAE: {summary['survivor_total_mae']}",
        "",
    ]
    if equation_checks:
        lines.extend(
            [
                "## Claimed Equation Checks",
                "",
                "| Control | Claimed damage | Linear expression | Kernel after floor/cap | Matches? |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for check in equation_checks:
            lines.append(
                f"| {check['control']} | {check['claimed']:.6f} | "
                f"{check['linear']:.6f} | {check['kernel']:.6f} | "
                f"{'yes' if check['matches'] else 'no'} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Per-Report Residuals",
            "",
            "| Report | Winner obs/pred | Turns obs/pred | Survivors A obs/pred | Survivors D obs/pred |",
            "|---|---|---|---:|---:|",
        ]
    )
    for row in rows:
        observed_turns = (
            str(row.observed_turns)
            if row.observed_turns is not None
            else (
                f"{row.observed_turns_min}-{row.observed_turns_max}"
                if row.observed_turns_min is not None
                else "NC"
            )
        )
        lines.append(
            f"| {row.report_id} | {row.observed_winner}/{row.predicted_winner} | "
            f"{observed_turns}/{row.predicted_turns} | "
            f"{row.observed_attacker_survivors}/{row.predicted_attacker_survivors} | "
            f"{row.observed_defender_survivors}/{row.predicted_defender_survivors} |"
        )
    worst_turns = sorted(
        (row for row in rows if row.turn_error is not None),
        key=lambda row: abs(row.turn_error or 0),
        reverse=True,
    )[:10]
    lines.extend(
        [
            "",
            "## Largest Clock Residuals",
            "",
            "| Report | Observed range | Predicted | Signed error |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in worst_turns:
        lines.append(
            f"| {row.report_id} | {row.observed_turns_min}-{row.observed_turns_max} | "
            f"{row.predicted_turns} | {row.turn_error} |"
        )
    (output_dir / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def deepseek_equation_checks() -> list[dict[str, Any]]:
    alpha, beta, gamma, delta = 1 / 32, 1 / 64, 1 / 80, 1 / 80
    controls = [
        ("T1 Infantry mirror", 1.128288, 3.52, 1.0, 6.0, 0.022727),
        ("T1 Lancer mirror", 4.513152, 1.76, 5.0, 2.0, 0.066667),
        ("T1 Lancer +20% L vs Infantry", 4.513152, 3.52, 6.0, 6.0, 0.083333),
        ("T6 Infantry mirror", 6.769728, 7.92, 6.0, 11.0, 0.041667),
        ("T4 Infantry vs T1 Infantry", 4.513152, 3.52, 4.0, 6.0, 0.0625),
    ]
    checks: list[dict[str, Any]] = []
    for name, attack, defense, lethality, health, claimed in controls:
        linear = alpha * attack - beta * defense + gamma * lethality
        raw = max(0.0, alpha * attack - beta * defense) + gamma * lethality
        kernel = min(raw, delta * health)
        checks.append(
            {
                "control": name,
                "claimed": claimed,
                "linear": linear,
                "kernel": kernel,
                "matches": abs(kernel - claimed) < 1e-6,
            }
        )
    return checks
