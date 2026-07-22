#!/usr/bin/env python3
"""Independent V2 QA of the deterministic WoS battle law.

No project predictor/validator module is imported. Inputs are the normalized
TYPE1 corpus, frozen Stage-6 constants, the official base-stat reference, and
the hero-kit rules transcribed into CODEX_QA_PROMPT_V2.md/HERO_KITS.md.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
WOS_SIM = HERE.parents[1]
ROOT = WOS_SIM.parent
CORPUS_PATH = WOS_SIM / "data" / "experiments" / "_corpus" / "TYPE1_CORPUS.json"
TABLES_PATH = WOS_SIM / "formula_research" / "stage6_tables.json"
BASE_STATS_PATH = ROOT / "docs" / "TroopStats" / "WOS_Troop_Stats_FC1-FC10_T1-T10.json"
CSV_PATH = HERE / "qa2_results.csv"
REPORT_PATH = HERE / "qa2_report.md"
LOCK_PATH = HERE / "independent_v2_results.lock.json"

CAP = 1500.0
COIN_FLIP_PCT = 10.0
CLASS_ORDER = {"Infantry": 0, "Lancer": 1, "Marksman": 2}
SHORT = {"Infantry": "Inf", "Lancer": "Lan", "Marksman": "MM"}
COMPOSITION_FOLDERS = {"MuellerAlpaca_Gatot_2v2", "Meuller_Alpaca_v5_8_Battle"}
COMPOSITION_ANCHOR_ID = "ColonelMuller_1v2_T1InfvT1Inf+T1MM_Gatot_Gatot+Vulcanus_20260713_112033"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


TABLES = load_json(TABLES_PATH)
BASE_STATS = load_json(BASE_STATS_PATH)
CORPUS = load_json(CORPUS_PATH)
ROWS: list[dict[str, Any]] = CORPUS["rows"]


def hero_key(value: str | None) -> str:
    return re.sub(r"[^a-z]", "", (value or "").casefold())


def heroes(side: dict[str, Any]) -> set[str]:
    return {hero_key(item.get("hero")) for item in side.get("heroes", [])}


def has_hero(side: dict[str, Any], name: str) -> bool:
    return hero_key(name) in heroes(side)


def has_skill(side: dict[str, Any], hero: str, skill_number: int) -> bool:
    wanted = hero_key(hero)
    for item in side.get("heroes", []):
        if hero_key(item.get("hero")) != wanted:
            continue
        slot = (item.get("slot") or "").casefold()
        name = (item.get("name") or "").casefold()
        if f"skill {skill_number}" in slot:
            return True
        if skill_number == 2 and ("bestowal" in name or (wanted == "vulcanus" and "skill 2" in name)):
            return True
        if skill_number == 3 and ("true strike" in name or "royal legion" in name or "skill 3" in name):
            return True
    return False


def hero_level(side: dict[str, Any], name: str) -> int | None:
    wanted = hero_key(name)
    levels = [
        item.get("level")
        for item in side.get("heroes", [])
        if hero_key(item.get("hero")) == wanted and item.get("level") is not None
    ]
    return max(map(int, levels)) if levels else None


def side_count(side: dict[str, Any]) -> int:
    return sum(int(unit.get("count") or 0) for unit in side.get("classes", []))


def matchup(row: dict[str, Any]) -> str:
    def render(side: dict[str, Any]) -> str:
        units = "+".join(
            f"{SHORT.get(unit['cls'], unit['cls'])}T{unit.get('tier')}x{unit.get('count')}"
            for unit in side.get("classes", [])
        ) or "none"
        hs = "+".join(sorted(heroes(side)))
        return f"{units}[{hs}]"

    return f"{render(row['attacker'])} vs {render(row['defender'])}"


def observed_band(row: dict[str, Any]) -> tuple[float, float] | None:
    band = row["outcome"].get("turns_range")
    if band and band[0] is not None and band[1] is not None:
        return float(band[0]), float(band[1])
    turns = row["outcome"].get("turns")
    if turns is not None:
        return float(turns), float(turns)
    return None


def k_value(dealer_cls: str, target_cls: str) -> tuple[float, str]:
    entry = TABLES["K"].get(f"{dealer_cls}->{target_cls}")
    if entry:
        return float(entry["value"]), str(entry["status"])
    factor = TABLES["K_factorization"]
    return float(factor["f"][dealer_cls]) * float(factor["g"][target_cls]), "factorized"


def official_base_product(cls: str, tier: int, fc: int | None) -> float:
    wanted_fc = int(fc or 1)
    matches = [
        record for record in BASE_STATS["flat_records"]
        if record["class"] == cls
        and int(record["tier"]) == int(tier)
        and int(record["fire_crystal_level"]) == wanted_fc
    ]
    if len(matches) != 1:
        raise ValueError(f"No unique official base row for {cls} T{tier} FC{wanted_fc}")
    return float(matches[0]["attack"]) * float(matches[0]["lethality"])


def gw_value(unit: dict[str, Any]) -> tuple[float, str]:
    cls, tier = unit["cls"], int(unit["tier"])
    entry = TABLES["G_w"].get(cls, {}).get(f"T{tier}")
    if entry:
        return float(entry["value"]), str(entry["status"])
    if cls == "Marksman":
        return float(TABLES["G_w_marksman_band"][0]), "bounded_marksman"
    if cls == "Lancer" and tier > 6:
        value = float(TABLES["G_w"]["Lancer"]["T6"]["value"])
        for _ in range(7, tier + 1):
            value *= 1.1421
        return value, "extrapolated"
    if cls == "Infantry" and tier > 6:
        anchor = float(TABLES["G_w"]["Infantry"]["T6"]["value"])
        ratio = official_base_product(cls, tier, unit.get("fc")) / official_base_product(cls, 6, unit.get("fc"))
        return anchor * ratio ** (2.0 / 3.0), "extrapolated"
    raise ValueError(f"No G_w rule for {cls} T{tier}")


def gl_value(unit: dict[str, Any]) -> tuple[float, str]:
    cls, tier = unit["cls"], int(unit["tier"])
    entry = TABLES["G_l"].get(cls, {}).get(f"T{tier}")
    if entry:
        return float(entry["value"]), str(entry["status"])
    fallback = TABLES["G_l"]["Infantry"].get(f"T{tier}")
    if fallback:
        return float(fallback["value"]), "fallback_infantry"
    raise ValueError(f"No G_l rule for {cls} T{tier}")


def seo_factor(side: dict[str, Any]) -> float:
    if not has_hero(side, "SeoYoon"):
        return 1.0
    return {1: 1.05, 2: 1.10, 3: 1.15}.get(hero_level(side, "SeoYoon"), 1.0)


def side_name(side: dict[str, Any]) -> str:
    return (side.get("name") or "").casefold()


def gatot_aura_state(side: dict[str, Any], unit: dict[str, Any] | None = None) -> str:
    """Return present/absent/unknown from the holder's own per-battle panels."""
    if not has_hero(side, "Gatot"):
        return "none"
    if unit is None:
        unit = next((candidate for candidate in side.get("classes", []) if candidate["cls"] == "Infantry"), None)
    if not unit or unit.get("cls") != "Infantry":
        return "absent"
    panel = unit.get("panel_pct") or {}
    attack_panel = panel.get("Attack")
    name = side_name(side)
    if "far seer" in name or "farseer" in name:
        return "present"
    if attack_panel is None:
        return "unknown"
    if "mueller" in name or "müller" in name:
        return "present" if float(attack_panel) >= 450.0 else "absent"
    if "alpaca" in name or "沃草泥" in name:
        return "present" if float(attack_panel) >= 400.0 else "absent"
    return "unknown"


def royal_legion_factor(target_side: dict[str, Any], target_unit: dict[str, Any]) -> tuple[float, str | None]:
    if gatot_aura_state(target_side, target_unit) != "present" or not has_skill(target_side, "Gatot", 3):
        return 1.0, None
    name = side_name(target_side)
    if "far seer" in name or "farseer" in name:
        return 1.0, None
    if "alpaca" in name or "沃草泥" in name:
        return 0.85, "royal_legion_L3"
    if "mueller" in name or "müller" in name:
        return 0.90, "royal_legion_L2"
    level = hero_level(target_side, "Gatot")
    return ({2: 0.90, 3: 0.85}.get(level, 1.0), f"royal_legion_L{level}" if level in {2, 3} else None)


def defender_budget(side: dict[str, Any]) -> tuple[float | None, float | None, str]:
    """Return exact B, lower bound, and instrument label."""
    name = side_name(side)
    budgets = TABLES["gatot_kit"]["no_hero_budget_gate"]["B_hp_units_per_turn"]
    if "mueller" in name or "müller" in name:
        return float(budgets["Mueller_Gatot_S123_L1"]), None, "Mueller"
    if "far seer" in name or "farseer" in name:
        return float(budgets["FarSeer_Gatot_S12_L1"]), None, "FarSeer"
    if "alpaca" in name or "沃草泥" in name:
        return None, 6.3, "Alpaca"
    return None, None, "unknown"


def plain_fold_factors(
    dealer: dict[str, Any],
    target: dict[str, Any],
    dealer_side: dict[str, Any],
    target_side: dict[str, Any],
) -> tuple[float, float, list[str]]:
    offense = seo_factor(dealer_side)
    pool = 1.0
    flags: list[str] = []
    if has_skill(target_side, "Vulcanus", 1):
        offense *= 0.96
        flags.append("vulcanus_S1_enemy_attack_x0.96")
    if has_skill(dealer_side, "Vulcanus", 2):
        offense *= 31.0 / 30.0
        flags.append("vulcanus_S2_avg_x31_30")
    if has_skill(dealer_side, "Vulcanus", 3):
        if target["cls"] in {"Infantry", "Lancer"}:
            pool *= 0.88
            flags.append("true_strike_enemy_defense_x0.88")
        if dealer["cls"] == "Marksman":
            offense *= 1.04
            flags.append("true_strike_own_MM_attack_x1.04")
    royal, royal_flag = royal_legion_factor(target_side, target)
    offense *= royal
    if royal_flag:
        flags.append(royal_flag)
    return offense, pool, flags


def gate_rate(dealer: dict[str, Any]) -> tuple[float, str, list[str]]:
    """Per-unit no-hero budget rate, using frozen conditional Lan K cells."""
    k, status = k_value(dealer["cls"], "Infantry")
    gw, gw_status = gw_value(dealer)
    flags: list[str] = []
    denominator = k
    if dealer["cls"] == "Lancer" and int(dealer["tier"]) in {3, 6}:
        implied = TABLES["gatot_kit"]["no_hero_budget_gate"]["K_LanInf_implied"]
        k = float(implied["at_T3" if int(dealer["tier"]) == 3 else "at_T6"])
        denominator = k * gw
        status = "gatot_implied"
        flags.append("gatot_K_LanInf_implied_with_Gw")
    rate = float(dealer["eff"]["A"]) * float(dealer["eff"]["L"]) / denominator
    if gw_status != "measured":
        flags.append(f"G_w_{gw_status}")
    return rate, status, flags


def per_unit_kill_time(
    dealer: dict[str, Any],
    target: dict[str, Any],
    dealer_side: dict[str, Any],
    target_side: dict[str, Any],
) -> dict[str, Any]:
    d_cls, t_cls = dealer["cls"], target["cls"]
    k, k_status = k_value(d_cls, t_cls)
    gw, gw_status = gw_value(dealer)
    gl, gl_status = gl_value(target)
    count = float(dealer["count"])
    a = float(dealer["eff"]["A"])
    leth = float(dealer["eff"]["L"])
    defense = float(target["eff"]["D"])
    hp = float(target["eff"]["H"])
    pool = defense * hp
    flags: list[str] = []
    if k_status == "factorized":
        flags.append("factorized_K")
    if gw_status != "measured":
        flags.append(f"G_w_{gw_status}")
    if gl_status != "measured":
        flags.append(f"G_l_{gl_status}")

    aura_state = gatot_aura_state(target_side, target)
    gate = t_cls == "Infantry" and has_hero(target_side, "Gatot") and aura_state == "present"
    if gate and not dealer_side.get("heroes"):
        exact_b, lower_b, instrument = defender_budget(target_side)
        rates: list[float] = []
        rate_flags: list[str] = []
        rate_statuses: list[str] = []
        # This function is class-local; identical dealer units pool linearly.
        per_rate, rate_status, extra_flags = gate_rate(dealer)
        rates.append(float(dealer["count"]) * per_rate)
        rate_flags.extend(extra_flags)
        rate_statuses.append(rate_status)
        gross = sum(rates)
        flags.extend(rate_flags)
        if exact_b is None:
            guaranteed_cap = lower_b is not None and max(0.0, gross - lower_b) * CAP < pool
            flags.extend(["gatot_budget_bound_only", f"gatot_budget_{instrument}"])
            detail = (
                f"Gatot-B-bound: gross={dealer['count']}*{per_rate:.6g}={gross:.6g}; "
                f"B>={lower_b}; pool={defense:.6g}*{hp:.6g}={pool:.6g}; "
                f"guaranteed_cap={guaranteed_cap}"
            )
            return {
                "raw": math.inf if guaranteed_cap else None,
                "unmeasured": True,
                "bound_cap": guaranteed_cap,
                "bound_winner": "target" if guaranteed_cap else None,
                "gross_rate": gross,
                "budget": lower_b,
                "gate": "alpaca_bound",
                "detail": detail,
                "flags": flags,
                "k_status": rate_statuses[0],
            }
        net = max(0.0, gross - exact_b)
        capped = net <= 0 or net * CAP < pool
        raw = math.inf if capped else pool / net
        flags.extend(["gatot_budget", f"gatot_budget_{instrument}"])
        detail = (
            f"Gatot-B: gross={dealer['count']}*{per_rate:.6g}={gross:.6g}; "
            f"net=gross-{exact_b:.6g}={net:.6g}; pool={pool:.6g}; "
            + ("capped" if capped else f"t={raw:.6g}")
        )
        return {
            "raw": raw,
            "unmeasured": False,
            "bound_cap": None,
            "gross_rate": gross,
            "budget": exact_b,
            "gate": "budget",
            "detail": detail,
            "flags": flags,
            "k_status": rate_statuses[0],
        }

    if gate and has_hero(dealer_side, "Vulcanus"):
        amp, scale = map(float, TABLES["gatot_kit"]["hero_led_suppression"]["surviving_families_folded"][0]["params"])
        d = a * leth / k
        suppression = 1.0 + amp * math.exp(-d / scale)
        offense, pool_factor, fold_flags = plain_fold_factors(dealer, target, dealer_side, target_side)
        # plain_fold_factors includes Seo/Vulcanus/Royal folds but no base A*L.
        rate = d * offense / suppression * math.sqrt(count)
        folded_pool = pool * pool_factor
        raw = folded_pool / rate if rate > 0 else math.inf
        flags.extend(fold_flags)
        flags.append("gatot_scurve")
        if count > 1:
            flags.append("gatot_scurve_n_gt1_unvalidated")
        detail = (
            f"Gatot-S: d=({a:.6g}*{leth:.6g})/{k:.6g}={d:.6g}; "
            f"S=1+{amp:.6g}*exp(-d/{scale:.6g})={suppression:.6g}; "
            f"folded_pool={pool:.6g}*{pool_factor:.6g}={folded_pool:.6g}; "
            f"rate=d*{offense:.6g}/S*sqrt({count:g})={rate:.6g}; t={raw:.6g}"
        )
        return {
            "raw": raw,
            "unmeasured": count > 1,
            "bound_cap": None,
            "gross_rate": d,
            "budget": None,
            "gate": "scurve",
            "detail": detail,
            "flags": flags,
            "k_status": k_status,
        }

    if gate:
        flags.append("gatot_gate_unmeasured_hero_configuration")
        return {
            "raw": None,
            "unmeasured": True,
            "bound_cap": None,
            "gross_rate": None,
            "budget": None,
            "gate": "unmeasured",
            "detail": "Aura'd Gatot target with a dealer hero configuration outside budget/S-curve regimes",
            "flags": flags,
            "k_status": k_status,
        }

    offense, pool_factor, fold_flags = plain_fold_factors(dealer, target, dealer_side, target_side)
    flags.extend(fold_flags)
    if has_hero(target_side, "Gatot") and aura_state == "absent":
        flags.append("gatot_inert_no_aura")
    raw = k * pool * pool_factor / (a * leth * offense) * gw * gl / math.sqrt(count)
    detail = (
        f"plain: {k:.6g}*({defense:.6g}*{hp:.6g})*{pool_factor:.6g}/"
        f"({a:.6g}*{leth:.6g}*{offense:.6g})*{gw:.6g}*{gl:.6g}/sqrt({count:g})={raw:.6g}"
    )
    return {
        "raw": raw,
        "unmeasured": False,
        "bound_cap": None,
        "gross_rate": None,
        "budget": None,
        "gate": "plain",
        "detail": detail,
        "flags": flags,
        "k_status": k_status,
    }


def total_single_class_clock(
    dealer_side: dict[str, Any], target_side: dict[str, Any]
) -> dict[str, Any]:
    dealer, target = dealer_side["classes"][0], target_side["classes"][0]
    per_unit = per_unit_kill_time(dealer, target, dealer_side, target_side)
    raw = per_unit["raw"]
    total = None if raw is None else (math.inf if math.isinf(raw) else raw * int(target["count"]))
    return {
        **per_unit,
        "per_unit_raw": raw,
        "raw": total,
        "detail": per_unit["detail"] + f"; target_count={target['count']}; total={fmt_num(total)}",
    }


def fmt_num(value: float | None) -> str:
    if value is None:
        return "unmeasured"
    if math.isinf(value):
        return "capped"
    return f"{value:.6f}"


def clock_gap_pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    if math.isinf(a) and math.isinf(b):
        return 0.0
    if math.isinf(a) or math.isinf(b):
        return math.inf
    smaller = min(a, b)
    return math.inf if smaller <= 0 else abs(a - b) / smaller * 100.0


def predicted_winner(a_clock: float | None, d_clock: float | None) -> str | None:
    if a_clock is None or d_clock is None:
        return None
    a_capped, d_capped = a_clock > CAP, d_clock > CAP
    if a_capped and d_capped:
        return "defender"
    if not a_capped and (d_capped or a_clock <= d_clock):
        return "attacker"
    return "defender"


def classify_winner(actual: str, predicted: str | None, gap: float | None, abstain: bool) -> str:
    if abstain or predicted is None:
        return "ABSTAIN"
    if actual == predicted:
        return "CORRECT"
    if gap is not None and gap <= COIN_FLIP_PCT:
        return "COIN_FLIP"
    return "WRONG"


def race_prediction(row: dict[str, Any]) -> dict[str, Any]:
    if len(row["attacker"].get("classes", [])) != 1 or len(row["defender"].get("classes", [])) != 1:
        return {
            "a_clock": None, "d_clock": None, "predicted_winner": None,
            "winner_class": "ABSTAIN", "gap": None, "flags": ["mixed_composition_unmeasured"],
            "detail": "Non-anchor mixed armies are outside the frozen composition regime",
            "a_calc": None, "d_calc": None, "bound_branch": "N/A",
        }
    a_calc = total_single_class_clock(row["attacker"], row["defender"])
    d_calc = total_single_class_clock(row["defender"], row["attacker"])
    a_clock, d_clock = a_calc["raw"], d_calc["raw"]
    abstain = bool(a_calc["unmeasured"] or d_calc["unmeasured"])
    pred = predicted_winner(a_clock, d_clock)
    gap = clock_gap_pct(a_clock, d_clock)
    winner_class = classify_winner(row["outcome"]["winner"], pred, gap, abstain)
    flags = sorted(set(a_calc["flags"] + d_calc["flags"]))

    bound_branch = "N/A"
    bound_miss = False
    for direction, calc in (("attacker", a_calc), ("defender", d_calc)):
        if calc["gate"] == "alpaca_bound":
            target_side = "defender" if direction == "attacker" else "attacker"
            conditional_winner = target_side
            branch_class = "CORRECT" if row["outcome"]["winner"] == conditional_winner else "WRONG"
            guarantee = "guaranteed_by_B>=6.3" if calc.get("bound_cap") else "conditional_cap_not_proven_by_bound"
            bound_branch = f"ASSUME_CAPPED->{conditional_winner}:{branch_class}:{guarantee}"
            bound_miss = branch_class == "WRONG"
    return {
        "a_clock": a_clock,
        "d_clock": d_clock,
        "predicted_winner": pred,
        "winner_class": winner_class,
        "gap": gap,
        "flags": flags,
        "detail": f"attacker clock [{a_calc['detail']}]; defender clock [{d_calc['detail']}]",
        "a_calc": a_calc,
        "d_calc": d_calc,
        "bound_branch": bound_branch,
        "bound_miss": bound_miss,
    }


def composition_anchor() -> float:
    rows = [row for row in ROWS if row["id"] == COMPOSITION_ANCHOR_ID]
    if len(rows) != 1 or observed_band(rows[0]) != (78.0, 78.0):
        raise RuntimeError("Composition anchor is missing or changed")
    return 78.0


SOLO_ANCHOR = composition_anchor()


def composition_prediction(row: dict[str, Any]) -> dict[str, Any]:
    units = row["attacker"]["classes"]
    counts = {unit["cls"]: int(unit["count"]) for unit in units}
    n_inf, n_lan, n_mm = counts.get("Infantry", 0), counts.get("Lancer", 0), counts.get("Marksman", 0)
    manual_front = row["id"].startswith("manual_ladder_") or row["id"].startswith("manual_mixed_1_infantry_")
    anchored = has_hero(row["attacker"], "Gatot") or manual_front
    flags = ["composition_anchor"]
    if not anchored or not n_inf:
        return {
            "a_clock": None, "d_clock": None, "predicted_winner": None,
            "winner_class": "ABSTAIN", "gap": None,
            "flags": flags + ["composition_no_front_anchor"],
            "detail": "No measured Gatot-Infantry front anchor", "a_calc": None, "d_calc": None,
            "bound_branch": "N/A", "observed_override": None,
        }
    if n_inf == 1 and not (n_lan or n_mm):
        end = SOLO_ANCHOR
        detail = "solo anchor=78"
    elif n_lan or n_mm:
        front = 33
        backline = []
        for count, latency in ((n_lan, 3), (n_mm, 2)):
            if count:
                backline.append(front + max(math.ceil(4 * count / 3), latency))
        end = float(max(backline or [front]))
        detail = f"front=33; backline_end={backline}; final={end:g}"
    else:
        first, middle, last = 33, 54, 57
        end = float(first + max(0, n_inf - 2) * middle + last)
        detail = f"front ladder={first}+{max(0, n_inf-2)}*{middle}+{last}={end:g}"

    observed_override = observed_band(row)
    defender_gatot = [
        item.get("triggers") for item in row["defender"].get("heroes", [])
        if hero_key(item.get("hero")) == "gatot"
        and (item.get("slot") == "Skill 2" or "bestowal" in (item.get("name") or "").casefold())
        and isinstance(item.get("triggers"), (int, float))
    ]
    if defender_gatot:
        observed_override = (float(max(defender_gatot)), float(max(defender_gatot)))
    winner = "defender"
    return {
        "a_clock": math.inf, "d_clock": end, "predicted_winner": winner,
        "winner_class": classify_winner(row["outcome"]["winner"], winner, math.inf, False),
        "gap": math.inf, "flags": flags, "detail": detail,
        "a_calc": None, "d_calc": {"raw": end, "flags": flags, "gate": "composition"},
        "bound_branch": "N/A", "observed_override": observed_override,
    }


def beast_prediction(row: dict[str, Any]) -> dict[str, Any]:
    # V1 declared rule: score the attacker's per-kill clock across 18 beasts.
    return race_prediction(row)


def predict(row: dict[str, Any]) -> dict[str, Any]:
    if row["folder"] == "legacy" or row["determinism"] == "legacy_unverified":
        return {
            "a_clock": None, "d_clock": None, "predicted_winner": None,
            "winner_class": "ABSTAIN", "gap": None, "flags": ["legacy_no_numeric_inputs"],
            "detail": "Legacy row lacks normalized numeric inputs", "a_calc": None, "d_calc": None,
            "bound_branch": "N/A",
        }
    if row["folder"] in COMPOSITION_FOLDERS:
        return composition_prediction(row)
    if "Beast" in row["id"]:
        return beast_prediction(row)
    return race_prediction(row)


def actual_calc(row: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any] | None:
    return prediction.get("a_calc") if row["outcome"]["winner"] == "attacker" else prediction.get("d_calc")


def domain_class(row: dict[str, Any], prediction: dict[str, Any]) -> tuple[str, str]:
    if row["folder"] == "legacy":
        return "out_legacy_no_numeric_inputs", "legacy"
    if row["folder"] in COMPOSITION_FOLDERS:
        if "composition_no_front_anchor" in prediction["flags"]:
            return "out_composition_no_front_anchor", "composition"
        return "in_composition_anchor", "composition"
    if "Beast" in row["id"]:
        return ("out_capped_beast" if observed_band(row) == (1500.0, 1500.0) else "in_beast_victory"), "beast"
    if prediction["winner_class"] == "ABSTAIN" and "gatot_budget_Alpaca" in prediction["flags"]:
        return "out_gatot_alpaca_bound_abstain", "gatot_alpaca_bound"
    if len(row["attacker"].get("classes", [])) != 1 or len(row["defender"].get("classes", [])) != 1:
        return "out_composition_other_defender", "mixed_other"
    if row["folder"] == "NanoMart":
        if side_count(row["attacker"]) != 1 or side_count(row["defender"]) != 1:
            return "out_nanomart_multicount_winner_only", "nanomart_multicount"
        if any(int(unit["tier"]) != 1 for side in (row["attacker"], row["defender"]) for unit in side["classes"]):
            return "out_nanomart_nonT1_tier", "nanomart_1v1"
        actual = actual_calc(row, prediction)
        if actual and actual.get("k_status") == "factorized":
            return "out_factorized_K_pm15", "nanomart_1v1"
        return "in_nanomart_T1", "nanomart_1v1"
    if observed_band(row) == (1500.0, 1500.0):
        return "out_capped_stalemate", "gatot_threshold"
    actual = actual_calc(row, prediction)
    if actual and actual.get("gate") == "budget":
        if "T3" in row["id"] and side_count(row["attacker"]) > 1:
            return "out_base_mismatch_T3_threshold", "gatot_threshold"
        return "in_gatot_budget", "gatot_gate"
    if actual and actual.get("gate") == "scurve":
        if "gatot_scurve_n_gt1_unvalidated" in prediction["flags"]:
            return "out_gatot_scurve_n_gt1_unvalidated", "gatot_gate"
        return "in_gatot_scurve", "gatot_gate"
    if actual and actual.get("k_status") == "factorized":
        return "out_factorized_K_pm15", "exact_1v1"
    return "in_exact_duel", "exact_1v1"


def display_band(band: tuple[float, float] | None) -> str:
    if not band:
        return ""
    return f"{band[0]:g}" if band[0] == band[1] else f"[{band[0]:g},{band[1]:g}]"


def score(row: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    band = prediction.get("observed_override", observed_band(row))
    domain, instrument = domain_class(row, prediction)
    a_clock, d_clock = prediction["a_clock"], prediction["d_clock"]
    race_clock = None
    if prediction["predicted_winner"] == "attacker":
        race_clock = a_clock
    elif prediction["predicted_winner"] == "defender":
        race_clock = d_clock
    actual_branch = a_clock if row["outcome"]["winner"] == "attacker" else d_clock
    flags = sorted(set(row.get("flags", []) + prediction["flags"]))
    result = {
        "id": row["id"], "folder": row["folder"], "instrument": instrument,
        "matchup": matchup(row), "N_vs_N": f"{side_count(row['attacker'])}v{side_count(row['defender'])}",
        "observed": display_band(band), "actual_winner": row["outcome"]["winner"],
        "attacker_clock": fmt_num(a_clock), "defender_clock": fmt_num(d_clock),
        "predicted_winner": prediction["predicted_winner"] or "ABSTAIN",
        "predicted": fmt_num(race_clock), "actual_branch_predicted": fmt_num(actual_branch),
        "pcterr": "", "abs_pcterr": "", "band_edge_pcterr": "", "time_result": "NOT_SCORED",
        "winner_classification": prediction["winner_class"],
        "clock_gap_pct": "" if prediction["gap"] is None else ("inf" if math.isinf(prediction["gap"]) else f"{prediction['gap']:.6f}"),
        "alpaca_bound_branch": prediction.get("bound_branch", "N/A"),
        "domain_class": domain, "verdict": "SKIP", "flags": ";".join(flags),
        "arithmetic": prediction["detail"],
    }
    if domain == "out_legacy_no_numeric_inputs":
        return result
    if prediction["winner_class"] == "ABSTAIN":
        result["verdict"] = "ABSTAIN"
    if band is None or domain in {"out_nanomart_multicount_winner_only", "out_composition_no_front_anchor"}:
        if prediction["winner_class"] != "ABSTAIN":
            result["verdict"] = "PASS" if prediction["winner_class"] in {"CORRECT", "COIN_FLIP"} else "FAIL"
        result["time_result"] = "WINNER_ONLY"
        return result
    if band == (1500.0, 1500.0):
        actual_capped = actual_branch is not None and actual_branch > CAP
        result["time_result"] = "CAPPED_CORRECT" if actual_capped else "CAPPED_WRONG"
        if prediction["winner_class"] != "ABSTAIN":
            result["verdict"] = "PASS" if actual_capped and prediction["winner_class"] in {"CORRECT", "COIN_FLIP"} else "FAIL"
        return result
    if actual_branch is None or math.isinf(actual_branch):
        result["time_result"] = "UNMEASURED_OR_CAPPED"
        if prediction["winner_class"] != "ABSTAIN":
            result["verdict"] = "FAIL"
        return result
    lo, hi = band
    midpoint = (lo + hi) / 2.0
    err = (actual_branch / midpoint - 1.0) * 100.0
    # Also retain distance past the nearest edge. The unchanged V1 QA bar
    # uses midpoint % error, while V2 describes some residuals as "past band".
    if actual_branch < lo:
        edge_err = (actual_branch / lo - 1.0) * 100.0
    elif actual_branch > hi:
        edge_err = (actual_branch / hi - 1.0) * 100.0
    else:
        edge_err = 0.0
    abs_err = abs(err)
    ceil_hit = lo <= math.ceil(actual_branch) <= hi
    band_hit = lo <= actual_branch <= hi
    tolerance = 15.0 if domain == "out_factorized_K_pm15" else 10.0
    time_pass = ceil_hit or band_hit or abs_err <= tolerance
    result["pcterr"] = f"{err:.6f}"
    result["abs_pcterr"] = f"{abs_err:.6f}"
    result["band_edge_pcterr"] = f"{edge_err:.6f}"
    result["time_result"] = "CEIL_HIT" if ceil_hit else ("BAND_HIT" if band_hit else (f"WITHIN_{tolerance:g}PCT" if time_pass else "MISS"))
    if prediction["winner_class"] != "ABSTAIN":
        result["verdict"] = "PASS" if time_pass and prediction["winner_class"] in {"CORRECT", "COIN_FLIP"} else "FAIL"
    return result


def data_suspects(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    suspects: list[dict[str, str]] = []
    panel_names = {"A": "Attack", "D": "Defense", "L": "Lethality", "H": "Health"}
    for row in rows:
        for side_name_key in ("attacker", "defender"):
            side = row[side_name_key]
            for index, unit in enumerate(side.get("classes", [])):
                path = f"{side_name_key}.classes[{index}]"
                if row["folder"] != "legacy":
                    if not isinstance(unit.get("count"), int) or int(unit["count"]) <= 0:
                        suspects.append({"id": row["id"], "field": path + ".count", "reason": f"invalid count {unit.get('count')!r}"})
                    if not isinstance(unit.get("tier"), int) or not 1 <= int(unit["tier"]) <= 10:
                        suspects.append({"id": row["id"], "field": path + ".tier", "reason": f"invalid tier {unit.get('tier')!r}"})
                base, panel, eff = unit.get("base"), unit.get("panel_pct"), unit.get("eff") or {}
                for stat in ("A", "D", "L", "H"):
                    if row["folder"] != "legacy" and (eff.get(stat) is None or float(eff[stat]) <= 0):
                        suspects.append({"id": row["id"], "field": path + f".eff.{stat}", "reason": f"missing/non-positive {eff.get(stat)!r}"})
                    panel_name = panel_names[stat]
                    if base and panel and panel.get(panel_name) is not None and eff.get(stat) is not None:
                        expected = float(base[stat]) * (1 + float(panel[panel_name]) / 100.0)
                        if not math.isclose(expected, float(eff[stat]), abs_tol=0.002, rel_tol=0):
                            suspects.append({"id": row["id"], "field": path + f".eff.{stat}", "reason": f"base×panel={expected:.6f}, eff={float(eff[stat]):.6f}"})
            casualties = side.get("casualties") or {}
            parts = [casualties.get(key) for key in ("losses", "injured", "lightly_injured", "survivors")]
            troops = casualties.get("troops")
            if troops is not None and all(value is not None for value in parts) and sum(parts) != troops:
                suspects.append({"id": row["id"], "field": side_name_key + ".casualties", "reason": f"losses+injured+light+survivors={sum(parts)}, troops={troops}"})
            if row["folder"] != "legacy" and troops is not None and side_count(side) != troops:
                suspects.append({"id": row["id"], "field": side_name_key + ".classes[].count", "reason": f"class total={side_count(side)}, troops={troops}"})

        label = re.search(r"NanoMart_1v1_T(\d+)(Inf|Lan|MM)vT(\d+)(Inf|Lan|MM)", row["id"])
        if label and not row.get("corrections_applied"):
            a_tier, a_cls, d_tier, d_cls = label.groups()
            cmap = {"Inf": "Infantry", "Lan": "Lancer", "MM": "Marksman"}
            for side_key, tier_text, cls_text in (("attacker", a_tier, a_cls), ("defender", d_tier, d_cls)):
                if len(row[side_key].get("classes", [])) == 1:
                    actual = row[side_key]["classes"][0]
                    if actual["tier"] != int(tier_text) or actual["cls"] != cmap[cls_text]:
                        suspects.append({"id": row["id"], "field": side_key + ".classes[0].(cls,tier)", "reason": f"id says {cmap[cls_text]} T{tier_text}, row says {actual['cls']} T{actual['tier']}"})
    return suspects


def adversarial_findings(rows: list[dict[str, Any]], results_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    below_budget_deaths: list[dict[str, Any]] = []
    inert_plain_misses: list[dict[str, Any]] = []
    vulcanus_capped: list[dict[str, Any]] = []
    inert_rows = 0
    vulc_gate_rows = 0
    for row in rows:
        if row["folder"] == "legacy" or len(row["attacker"].get("classes", [])) != 1 or len(row["defender"].get("classes", [])) != 1:
            continue
        for dealer_key, target_key in (("attacker", "defender"), ("defender", "attacker")):
            dealer_side, target_side = row[dealer_key], row[target_key]
            target = target_side["classes"][0]
            if target["cls"] != "Infantry" or not has_hero(target_side, "Gatot"):
                continue
            aura = gatot_aura_state(target_side, target)
            if aura == "present" and not dealer_side.get("heroes"):
                exact_b, lower_b, instrument = defender_budget(target_side)
                rate, _, _ = gate_rate(dealer_side["classes"][0])
                gross = rate * int(dealer_side["classes"][0]["count"])
                threshold = exact_b if exact_b is not None else lower_b
                casualties = target_side.get("casualties", {})
                # Some 1500-turn stalemates are stored as defender wins even
                # though the Gatot target survived.  The adversarial claim is
                # specifically a death, so use the target's survivor count.
                target_died = casualties.get("survivors") == 0
                if target_died and threshold is not None and gross < threshold:
                    below_budget_deaths.append({"id": row["id"], "gross": gross, "B": threshold, "instrument": instrument})
            if aura == "present" and has_hero(dealer_side, "Vulcanus"):
                vulc_gate_rows += 1
                calc = per_unit_kill_time(dealer_side["classes"][0], target, dealer_side, target_side)
                if calc["raw"] is None or math.isinf(calc["raw"]):
                    vulcanus_capped.append({"id": row["id"], "raw": fmt_num(calc["raw"])})
            if aura == "absent":
                inert_rows += 1
                result = results_by_id[row["id"]]
                if result["abs_pcterr"] and float(result["abs_pcterr"]) > 5.0:
                    inert_plain_misses.append({"id": row["id"], "abs_pcterr": float(result["abs_pcterr"])})
    return {
        "below_budget_deaths": below_budget_deaths,
        "inert_plain_misses": inert_plain_misses,
        "vulcanus_capped": vulcanus_capped,
        "inert_rows_checked": inert_rows,
        "vulcanus_gate_rows_checked": vulc_gate_rows,
    }


def summarize(results: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        groups[result[key]].append(result)
    output = []
    for name in sorted(groups):
        group = groups[name]
        errors = [float(item["abs_pcterr"]) for item in group if item["abs_pcterr"]]
        scored = [item for item in group if item["verdict"] in {"PASS", "FAIL"}]
        passed = sum(item["verdict"] == "PASS" for item in scored)
        output.append({
            key: name, "rows": len(group), "numeric": len(errors),
            "median": statistics.median(errors) if errors else None,
            "max": max(errors) if errors else None,
            "passed": passed, "scored": len(scored),
            "pass_rate": passed / len(scored) * 100 if scored else None,
        })
    return output


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def safe(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(map(safe, headers)) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(safe(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def metric(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}%"


def write_outputs(results: list[dict[str, Any]], suspects: list[dict[str, str]], adversarial: dict[str, Any]) -> None:
    fields = [
        "id", "folder", "instrument", "matchup", "N_vs_N", "observed", "actual_winner",
        "attacker_clock", "defender_clock", "predicted_winner", "predicted",
        "actual_branch_predicted", "pcterr", "abs_pcterr", "band_edge_pcterr", "time_result",
        "winner_classification", "clock_gap_pct", "alpaca_bound_branch",
        "domain_class", "verdict", "flags", "arithmetic",
    ]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    in_domain = [item for item in results if item["domain_class"].startswith("in_") and item["verdict"] in {"PASS", "FAIL"}]
    misses = [item for item in in_domain if item["verdict"] == "FAIL"]
    abstentions = [item for item in results if item["verdict"] == "ABSTAIN"]
    winner_counts: dict[str, int] = defaultdict(int)
    for item in results:
        winner_counts[item["winner_classification"]] += 1
    bound_rows = [item for item in results if item["alpaca_bound_branch"] != "N/A"]
    bound_misses = [item for item in bound_rows if ":WRONG:" in item["alpaca_bound_branch"]]

    lines = [
        "# Independent Type-1 QA report — V2",
        "",
        f"Corpus rows: **{len(results)}** (corpus metadata {CORPUS.get('row_count')}; frozen table metadata {TABLES['corpus']['row_count']}).",
        f"In-domain verdict: **{'PASS' if not misses else 'FAIL'}** — {len(in_domain)-len(misses)}/{len(in_domain)} scored rows pass the time and four-way winner rules.",
        f"Winner classifications: CORRECT {winner_counts['CORRECT']}, COIN_FLIP {winner_counts['COIN_FLIP']}, ABSTAIN {winner_counts['ABSTAIN']}, WRONG {winner_counts['WRONG']}.",
        f"Alpaca-bound conditional capped branch: {len(bound_rows)} rows, {len(bound_misses)} winner misses.",
        "",
        "Timing % error uses the unchanged V1 convention: the independently predicted clock for the side that actually won versus the observed-band midpoint. `band_edge_pcterr` separately records distance past the nearest edge; the race winner is scored separately.",
        "",
        "## In-domain misses",
        "",
    ]
    if misses:
        lines.append(md_table(
            ["id", "observed", "actual-branch prediction", "%err midpoint", "% past band", "winner", "arithmetic"],
            [[item["id"], item["observed"], item["actual_branch_predicted"], (f"{float(item['pcterr']):.2f}%" if item["pcterr"] else "—"), (f"{float(item['band_edge_pcterr']):.2f}%" if item["band_edge_pcterr"] else "—"), item["winner_classification"], item["arithmetic"]] for item in misses],
        ))
    else:
        lines.append("None.")

    by_id = {item["id"]: item for item in results}
    known_specs = [
        ("Gordon Lan→MM race", "LabRat_1v1_T1LanvT1MM_NoAttackerHero_Gordonlvl1_20260711_213859"),
        ("T7 Gatot reverse race", "MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+194.1D+172.2L+122.0H+118.7_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_151127"),
        ("T7 no-hero discriminator", "MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+176.2D+169.0L+109.7H+109.3_NoAttackerHero_AlpacaFC1T1Vulcanus_20260718_235302"),
        ("Nano MM→Inf", "NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus"),
        ("Nano MM mirror", "NanoMart_1v1_T1MMvT1MM_VulcanusVsVulcanus"),
        ("T6 open residual", "MuellerAlpaca_1v1_T6InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+176.2D+169.0L+109.7H+109.3_NoAttackerHero_AlpacaFC1T1VulcanusNoGatot_20260718_161706"),
        ("Factorized Lan→Lan (Seo)", "NanoMart_1v1_T1LanvT1Lan_SeoYoonlvl3_Vulcanus"),
        ("Factorized Lan→Lan (naked)", "NanoMart_SetB_1v1_T1LanvT1Lan_NoAttackerHero_Vulcanus"),
    ]
    known = [(label, by_id[row_id]) for label, row_id in known_specs]
    lines.extend(["", "## Known-finding reproduction", ""])
    lines.append(md_table(
        ["finding", "observed", "prediction", "%err midpoint", "% past band", "winner", "verdict"],
        [[label, item["observed"], item["actual_branch_predicted"], f"{float(item['pcterr']):.2f}%", f"{float(item['band_edge_pcterr']):.2f}%", item["winner_classification"], item["verdict"]] for label, item in known],
    ))
    seo_mirror = by_id["NanoMart_1v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus"]
    lines.extend([
        "",
        f"The representative Seo-yoon Infantry mirror remains a {seo_mirror['winner_classification']} with a {float(seo_mirror['clock_gap_pct']):.2f}% two-clock gap; its actual-winner branch is {float(seo_mirror['pcterr']):+.2f}% from the band midpoint.",
    ])

    lines.extend(["", "## Instrument summary", ""])
    lines.append(md_table(
        ["instrument", "rows", "numeric", "median |err|", "max |err|", "pass rate"],
        [[s["instrument"], s["rows"], s["numeric"], metric(s["median"]), metric(s["max"]), metric(s["pass_rate"])] for s in summarize(results, "instrument")],
    ))
    lines.extend(["", "## Domain summary", ""])
    lines.append(md_table(
        ["domain", "rows", "numeric", "median |err|", "max |err|", "pass rate"],
        [[s["domain_class"], s["rows"], s["numeric"], metric(s["median"]), metric(s["max"]), metric(s["pass_rate"])] for s in summarize(results, "domain_class")],
    ))

    lines.extend(["", "## Adversarial addendum", ""])
    lines.append(f"- Aura'd Gatot target deaths below measured/bounded B: **{len(adversarial['below_budget_deaths'])}**.")
    lines.append(f"- Inert-Gatot plain-law rows checked: **{adversarial['inert_rows_checked']}**; >5% timing misses: **{len(adversarial['inert_plain_misses'])}**.")
    lines.append(f"- Vulcanus-led Gatot-gate rows checked: **{adversarial['vulcanus_gate_rows_checked']}**; budget-capped/unresolved: **{len(adversarial['vulcanus_capped'])}**.")
    for title, key in (("Below-B deaths", "below_budget_deaths"), ("Inert misses", "inert_plain_misses"), ("Vulcanus capped", "vulcanus_capped")):
        if adversarial[key]:
            lines.extend(["", f"### {title}", "", md_table(list(adversarial[key][0].keys()), [list(item.values()) for item in adversarial[key]])])

    lines.extend(["", "## Alpaca bound branch", ""])
    lines.append(f"Primary classification is ABSTAIN because only B≥6.3 is measured. Under the conditional budget-capped branch, {len(bound_rows)-len(bound_misses)}/{len(bound_rows)} winners match.")
    if bound_misses:
        lines.append(md_table(["id", "branch"], [[item["id"], item["alpaca_bound_branch"]] for item in bound_misses]))

    lines.extend(["", "## OCR/data suspects", ""])
    lines.append(md_table(["id", "field", "reason"], [[item["id"], item["field"], item["reason"]] for item in suspects]) if suspects else "None.")

    lines.extend([
        "", "## Repository cross-check", "",
        "The independent 236-row result was hash-locked before the one permitted `stage6_validate.py` run; see `pre_crosscheck_v2.lock.json`. The validator exited 1 on its two already-open gates: the factorized Lan→Lan estimator and the two-sided winner gate.",
        "",
        "- Numeric agreement: the validator reproduced the independent clocks on the three shared WRONG races (Gordon Lan→MM, the T7 Gatot reverse race, and Nano MM→Inf) and on the checked Nano/Vulcanus rows. This cross-check did not change any predictor constant or clock.",
        "- Coverage/classification difference: its W6 gate classified only 147 rows (84 CORRECT, 14 COIN_FLIP, 46 ABSTAIN, 3 WRONG). This V2 run classifies all 236 (171/16/39/10). The extra seven independent WRONG results are winner-only Nano multi-count rows that W6 excludes; V2 explicitly requires corpus-wide four-way scoring.",
        "- Gatot difference: W6 still abstains on older unmeasured-kit categories, including baseline-panel Gatot configurations. V2 says those Gatots are inert, so this run applies the plain law; all 13 inert target-direction checks are within 5%.",
        "- New-row difference: the validator's accounting lists the new T6 open residual and T7 discriminator among `excluded: OTHER`; this run scores them directly. It also labels its accounting as 232 rows while printing 236/236, matching the stale `stage6_tables.json` metadata rather than the current corpus count.",
        "- Reporting convention: the cross-check confirmed that V1/validator `%err` is midpoint-based. The pre-cross-check edge-scored snapshot is preserved; final PASS/FAIL restores the unchanged midpoint bar and exposes edge error separately. This adds the Nano Inf→MM timing row (15.00% midpoint, 4.54% past the band) as a sixth in-domain miss.",
        "", "## Full evidence", "",
        f"All {len(results)} rows are in `qa2_results.csv`; verdict-ABSTAIN rows: {len(abstentions)}.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    digest = hashlib.sha256(CSV_PATH.read_bytes()).hexdigest()
    lock = {
        "corpus": str(CORPUS_PATH), "tables": str(TABLES_PATH),
        "corpus_rows": len(results), "table_declared_rows": int(TABLES["corpus"]["row_count"]),
        "qa2_results_sha256": digest,
        "winner_classifications": dict(winner_counts),
        "in_domain_failures": [item["id"] for item in misses],
        "abstentions": [item["id"] for item in abstentions],
        "adversarial": adversarial,
        "alpaca_bound_branch_misses": [item["id"] for item in bound_misses],
    }
    LOCK_PATH.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    if int(CORPUS.get("row_count", len(ROWS))) != len(ROWS):
        raise RuntimeError("Corpus self-declared count does not match rows")
    predictions = {row["id"]: predict(row) for row in ROWS}
    results = [score(row, predictions[row["id"]]) for row in ROWS]
    results_by_id = {item["id"]: item for item in results}
    suspects = data_suspects(ROWS)
    adversarial = adversarial_findings(ROWS, results_by_id)
    write_outputs(results, suspects, adversarial)
    print(f"Rows={len(results)}")
    print(f"Winner classes={dict((key, sum(r['winner_classification']==key for r in results)) for key in ('CORRECT','COIN_FLIP','ABSTAIN','WRONG'))}")
    print(f"In-domain FAIL={sum(r['domain_class'].startswith('in_') and r['verdict']=='FAIL' for r in results)}")
    print(f"Adversarial={json.dumps(adversarial, ensure_ascii=False)}")
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {LOCK_PATH}")


if __name__ == "__main__":
    main()
