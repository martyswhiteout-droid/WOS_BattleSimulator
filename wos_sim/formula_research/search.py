from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
from typing import Any, Callable

from scipy.optimize import differential_evolution

from .candidate import (
    AffineKernel,
    CandidateModel,
    PowerLawKernel,
    SharedMechanics,
)
from .dataset import BattleRecord
from .evaluate import evaluate, write_evaluation


SEED = 20260711


FAMILY_SPECS: dict[str, dict[str, Any]] = {
    "power_law": {
        "names": [
            "log_scale",
            "attack_exponent",
            "defense_exponent",
            "lethality_exponent",
            "target_health_exponent",
            "hp_exponent",
            "frontage_exponent",
            "minimum_hp_fraction",
        ],
        "bounds": [
            (-8.0, 1.0),
            (0.0, 3.0),
            (0.0, 3.0),
            (0.0, 3.0),
            (0.0, 3.0),
            (0.25, 2.0),
            (0.0, 1.0),
            (0.0, 0.02),
        ],
    },
    "affine": {
        "names": [
            "log_scale",
            "defense_weight",
            "lethality_weight",
            "positive_floor",
            "target_health_exponent",
            "hp_exponent",
            "frontage_exponent",
            "minimum_hp_fraction",
        ],
        "bounds": [
            (-8.0, 1.0),
            (0.0, 3.0),
            (0.0, 3.0),
            (0.0001, 5.0),
            (0.0, 3.0),
            (0.25, 2.0),
            (0.0, 1.0),
            (0.0, 0.02),
        ],
    },
}


def _model(family: str, cadence: int, vector: list[float]) -> CandidateModel:
    if family == "power_law":
        kernel = PowerLawKernel(*vector[:5])
    elif family == "affine":
        kernel = AffineKernel(*vector[:5])
    else:
        raise ValueError(family)
    mechanics = SharedMechanics(
        hp_exponent=vector[5],
        frontage_exponent=vector[6],
        vulcanus_s2_cadence=cadence,
        minimum_hp_fraction=vector[7],
    )
    return CandidateModel(family, kernel, mechanics)


def _distance_to_turn_range(battle: BattleRecord, predicted: int) -> float:
    if battle.turns_min is None or battle.turns_max is None:
        return 0.0
    if battle.turns_min <= predicted <= battle.turns_max:
        return 0.0
    if predicted < battle.turns_min:
        return float(battle.turns_min - predicted)
    return float(predicted - battle.turns_max)


def objective(
    model: CandidateModel,
    battles: list[BattleRecord],
    winner_weight: float = 4.0,
    survivor_weight: float = 2.0,
    turn_weight: float = 2.0,
) -> float:
    """Shared, normalized loss; exact duplicate captures are not fitted twice."""
    total = 0.0
    weight = 0.0
    for battle in battles:
        if battle.duplicate_of:
            continue
        result = model.simulate(battle)
        winner_loss = 0.0 if result.winner == battle.winner else 1.0
        survivor_loss = 0.5 * (
            abs(result.attacker_survivors - battle.attacker.survivors)
            / max(1, battle.attacker.troops)
            + abs(result.defender_survivors - battle.defender.survivors)
            / max(1, battle.defender.troops)
        )
        turn_loss = 0.0
        observed_turn_weight = 0.0
        if battle.turns_min is not None and battle.turns_max is not None:
            midpoint = (battle.turns_min + battle.turns_max) / 2
            turn_loss = _distance_to_turn_range(battle, result.turns) / max(1, midpoint)
            observed_turn_weight = turn_weight
        total += (
            winner_weight * winner_loss
            + survivor_weight * survivor_loss
            + observed_turn_weight * turn_loss
        )
        weight += winner_weight + survivor_weight + observed_turn_weight
    return total / weight


def run_search(
    output_dir: Path,
    battles: list[BattleRecord],
    maxiter: int = 35,
    popsize: int = 8,
    winner_weight: float = 4.0,
    survivor_weight: float = 2.0,
    turn_weight: float = 2.0,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for family, spec in FAMILY_SPECS.items():
        for cadence in (5, 6):
            make: Callable[[Any], CandidateModel] = lambda values, f=family, c=cadence: _model(
                f, c, list(values)
            )
            fitted = differential_evolution(
                lambda values: objective(
                    make(values),
                    battles,
                    winner_weight=winner_weight,
                    survivor_weight=survivor_weight,
                    turn_weight=turn_weight,
                ),
                spec["bounds"],
                seed=SEED,
                maxiter=maxiter,
                popsize=popsize,
                tol=1e-7,
                polish=True,
                workers=1,
                updating="immediate",
            )
            model = make(fitted.x)
            rows, summary = evaluate(model, battles)
            results.append(
                {
                    "family": family,
                    "cadence": cadence,
                    "objective": float(fitted.fun),
                    "optimizer_success": bool(fitted.success),
                    "optimizer_message": str(fitted.message),
                    "iterations": int(fitted.nit),
                    "evaluations": int(fitted.nfev),
                    "parameter_names": spec["names"],
                    "bounds": spec["bounds"],
                    "model": model.to_dict(),
                    "evaluation": summary,
                }
            )

    results.sort(key=lambda item: item["objective"])
    best = results[0]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "candidate_search.json").write_text(
        json.dumps(
            {
                "seed": SEED,
                "objective_definition": {
                    "winner_mismatch_weight": winner_weight,
                    "normalized_survivor_error_weight": survivor_weight,
                    "normalized_out_of_range_turn_error_weight": turn_weight,
                    "duplicate_weight": 0.0,
                },
                "maxiter": maxiter,
                "popsize": popsize,
                "results": results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "best_model.json").write_text(
        json.dumps(best["model"], indent=2) + "\n", encoding="utf-8"
    )

    best_model = _model(
        best["family"],
        best["cadence"],
        [best["model"]["kernel"][name] for name in FAMILY_SPECS[best["family"]]["names"][:5]]
        + [
            best["model"]["mechanics"]["hp_exponent"],
            best["model"]["mechanics"]["frontage_exponent"],
            best["model"]["mechanics"]["minimum_hp_fraction"],
        ],
    )
    rows, summary = evaluate(best_model, battles)
    write_evaluation(output_dir, best_model, rows, summary)

    lines = [
        "# Candidate Formula Search",
        "",
        "This is a numerical search over shared formula families. It is not proof of the game's internal formula.",
        "",
        f"- Seed: {SEED}",
        f"- Differential-evolution iterations per candidate: {maxiter}",
        f"- Population multiplier: {popsize}",
        "- Exact duplicate captures: zero additional fitting weight",
        f"- Objective: {winner_weight:g}x winner mismatch + "
        f"{survivor_weight:g}x normalized survivor error + "
        f"{turn_weight:g}x normalized out-of-range turn error",
        "",
        "| Rank | Family | Vulcanus S2 cadence | Objective | Winners | Turns | Survivors | Status |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for rank, result in enumerate(results, 1):
        evaluation = result["evaluation"]
        lines.append(
            f"| {rank} | {result['family']} | {result['cadence']} | "
            f"{result['objective']:.8f} | "
            f"{evaluation['winner_matches']}/{evaluation['reports']} | "
            f"{evaluation['turn_matches']}/{evaluation['reports_with_turn_evidence']} | "
            f"{evaluation['survivor_matches']}/{evaluation['reports']} | "
            f"{evaluation['status']} |"
        )
    lines.extend(["", "## Best Candidate", "", "```json", json.dumps(best["model"], indent=2), "```", ""])
    (output_dir / "CANDIDATE_SEARCH.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return {"best": best, "results": results}
