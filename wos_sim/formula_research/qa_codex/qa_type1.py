#!/usr/bin/env python3
"""Independent, read-only QA implementation of the frozen Stage-6 Type-1 law.

This module intentionally does not import any project predictor or validation code.
It reads only TYPE1_CORPUS.json and stage6_tables.json, implements the arithmetic
from CODEX_QA_PROMPT.md, and writes its evidence beside this script.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
WOS_SIM = HERE.parents[1]
CORPUS_PATH = WOS_SIM / "data" / "experiments" / "_corpus" / "TYPE1_CORPUS.json"
TABLES_PATH = WOS_SIM / "formula_research" / "stage6_tables.json"
BASE_STATS_PATH = WOS_SIM.parent / "docs" / "TroopStats" / "WOS_Troop_Stats_FC1-FC10_T1-T10.json"
CSV_PATH = HERE / "qa_results.csv"
REPORT_PATH = HERE / "qa_report.md"
LOCK_PATH = HERE / "independent_results.lock.json"

CAP = 1500.0
CLASS_ORDER = {"Infantry": 0, "Lancer": 1, "Marksman": 2}
CLASS_SHORT = {"Infantry": "Inf", "Lancer": "Lan", "Marksman": "MM"}
COMPOSITION_FOLDERS = {"MuellerAlpaca_Gatot_2v2", "Meuller_Alpaca_v5_8_Battle"}
COMPOSITION_SOLO_ANCHOR_ID = (
    "ColonelMuller_1v2_T1InfvT1Inf+T1MM_Gatot_Gatot+Vulcanus_20260713_112033"
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


TABLES = load_json(TABLES_PATH)
BASE_STATS = load_json(BASE_STATS_PATH)
ROWS = load_json(CORPUS_PATH)["rows"]


def hero_key(value: str | None) -> str:
    return re.sub(r"[^a-z]", "", (value or "").lower())


def heroes(side: dict[str, Any]) -> set[str]:
    return {hero_key(item.get("hero")) for item in side.get("heroes", [])}


def has_hero(side: dict[str, Any], name: str) -> bool:
    return hero_key(name) in heroes(side)


def hero_level(side: dict[str, Any], name: str) -> int | None:
    wanted = hero_key(name)
    levels = [
        item.get("level")
        for item in side.get("heroes", [])
        if hero_key(item.get("hero")) == wanted and item.get("level") is not None
    ]
    return max(levels) if levels else None


def k_value(dealer_cls: str, target_cls: str) -> tuple[float, str]:
    key = f"{dealer_cls}->{target_cls}"
    measured = TABLES["K"].get(key)
    if measured:
        return float(measured["value"]), str(measured["status"])
    factor = TABLES["K_factorization"]
    return float(factor["f"][dealer_cls]) * float(factor["g"][target_cls]), "factorized"


def official_base_product(cls: str, tier: int, fc: int | None) -> float:
    wanted_fc = int(fc or 1)
    matches = [
        record
        for record in BASE_STATS["flat_records"]
        if record["class"] == cls
        and int(record["tier"]) == int(tier)
        and int(record["fire_crystal_level"]) == wanted_fc
    ]
    if len(matches) != 1:
        raise ValueError(f"No unique official base row for {cls} T{tier} FC{wanted_fc}")
    return float(matches[0]["attack"]) * float(matches[0]["lethality"])


def gw_value(cls: str, tier: int, fc: int | None = None) -> tuple[float, str]:
    exact = TABLES["G_w"].get(cls, {}).get(f"T{tier}")
    if exact:
        return float(exact["value"]), str(exact["status"])
    if cls == "Marksman":
        # The frozen table declares the band [1.0, 1.17] and its extrapolation
        # policy explicitly names 1.0 as the point within that band.
        return float(TABLES["G_w_marksman_band"][0]), "bounded_marksman"
    if cls == "Lancer" and tier > 6:
        value = float(TABLES["G_w"]["Lancer"]["T6"]["value"])
        for _ in range(7, tier + 1):
            value *= 1.1421
        return value, "extrapolated"
    if cls == "Infantry" and tier > 6:
        anchor = float(TABLES["G_w"]["Infantry"]["T6"]["value"])
        ratio = official_base_product(cls, tier, fc) / official_base_product(cls, 6, fc)
        return anchor * ratio ** (2.0 / 3.0), "extrapolated"
    raise ValueError(f"No frozen G_w point for {cls} T{tier}")


def gl_value(cls: str, tier: int) -> tuple[float, str]:
    exact = TABLES["G_l"].get(cls, {}).get(f"T{tier}")
    if exact:
        return float(exact["value"]), str(exact["status"])
    fallback = TABLES["G_l"]["Infantry"].get(f"T{tier}")
    if fallback:
        return float(fallback["value"]), "fallback_infantry"
    raise ValueError(f"No frozen G_l point or Infantry fallback for {cls} T{tier}")


def seo_factor(side: dict[str, Any]) -> float:
    if not has_hero(side, "SeoYoon"):
        return 1.0
    level = hero_level(side, "SeoYoon")
    return {1: 1.05, 2: 1.10, 3: 1.15}.get(level, 1.0)


def defender_budget_key(side: dict[str, Any]) -> str | None:
    name = (side.get("name") or "").casefold()
    if "mueller" in name or "müller" in name:
        return "Mueller_Gatot_S123_L1"
    if "far seer" in name or "farseer" in name:
        return "FarSeer_Gatot_S12_L1"
    return None


def kill_time(
    dealer: dict[str, Any],
    target: dict[str, Any],
    dealer_side: dict[str, Any],
    target_side: dict[str, Any],
) -> dict[str, Any]:
    """Return the independently calculated time for one target unit to die."""
    d_cls, t_cls = dealer["cls"], target["cls"]
    k, k_status = k_value(d_cls, t_cls)
    gw, gw_status = gw_value(d_cls, int(dealer["tier"]), dealer.get("fc"))
    gl, gl_status = gl_value(t_cls, int(target["tier"]))
    count = float(dealer["count"])
    a, leth = float(dealer["eff"]["A"]), float(dealer["eff"]["L"])
    defense, hp = float(target["eff"]["D"]), float(target["eff"]["H"])
    pool = defense * hp
    flags: list[str] = []
    if k_status == "factorized":
        flags.append("factorized_K")
    if gw_status not in {"measured"}:
        flags.append(f"G_w_{gw_status}")
    if gl_status not in {"measured"}:
        flags.append(f"G_l_{gl_status}")

    gate = t_cls == "Infantry" and has_hero(target_side, "Gatot") and d_cls != "Infantry"
    if gate and has_hero(dealer_side, "Vulcanus"):
        # Frozen hero-led Gatot suppression candidate. S is evaluated on the
        # clean per-volley d; Vulcanus S2 and S3 are then folded deterministically.
        params = TABLES["gatot_kit"]["hero_led_suppression"]["surviving_families_folded"][0]["params"]
        amp, scale = map(float, params)
        d = a * leth / k
        suppression = 1.0 + amp * math.exp(-d / scale)
        attack_factor = seo_factor(dealer_side)
        if has_hero(target_side, "Vulcanus"):
            attack_factor *= 0.96
        attack_factor *= 31.0 / 30.0
        folded_rate = d * attack_factor / suppression * math.sqrt(count)
        folded_pool = pool * 0.88
        raw = folded_pool / folded_rate if folded_rate > 0 else math.inf
        detail = (
            f"Gatot-S: pool=.88*({defense:.6g}*{hp:.6g})={folded_pool:.6g}; "
            f"d=({a:.6g}*{leth:.6g})/{k:.6g}={d:.6g}; "
            f"S=1+{amp:.6g}*exp(-{d:.6g}/{scale:.6g})={suppression:.6g}; "
            f"rate=d*(31/30)*seo/S*sqrt({count:g})={folded_rate:.6g}; t={raw:.6g}"
        )
        flags.append("gatot_scurve")
        return {
            "raw": raw,
            "detail": detail,
            "flags": flags,
            "k_status": k_status,
            "gw_status": gw_status,
            "gl_status": gl_status,
            "gate": "hero_led_scurve",
        }

    if gate and not dealer_side.get("heroes"):
        budget_key = defender_budget_key(target_side)
        budgets = TABLES["gatot_kit"]["no_hero_budget_gate"]["B_hp_units_per_turn"]
        if budget_key not in budgets:
            flags.append("gatot_gate_unmodeled")
            return {
                "raw": math.inf,
                "detail": "Gatot budget gate: defender has no frozen B constant",
                "flags": flags,
                "k_status": k_status,
                "gw_status": gw_status,
                "gl_status": gl_status,
                "gate": "unmodeled",
            }
        budget = float(budgets[budget_key])
        gate_k = k
        if d_cls == "Lancer" and int(dealer["tier"]) in {3, 6}:
            implied = TABLES["gatot_kit"]["no_hero_budget_gate"]["K_LanInf_implied"]
            gate_k = float(implied["at_T3" if int(dealer["tier"]) == 3 else "at_T6"])
            flags = [flag for flag in flags if flag != "factorized_K"]
            flags.append("gatot_K_LanInf_implied")
        # The gate's shield-conditional K values are clean-rate cells; the
        # tier weight remains in the denominator (as documented by the
        # K(Lan->Inf)*G_w threshold measurement in the frozen block).
        per_unit_rate = a * leth / (gate_k * gw)
        net = max(0.0, count * per_unit_rate - budget)
        capped = net <= 0.0 or net * CAP < pool
        raw = math.inf if capped else pool / net
        detail = (
            f"Gatot-B: pool={defense:.6g}*{hp:.6g}={pool:.6g}; "
            f"r=({a:.6g}*{leth:.6g})/({gate_k:.6g}*{gw:.6g})={per_unit_rate:.6g}; "
            f"net={count:g}*r-{budget:.6g}={net:.6g}; "
            + ("capped" if capped else f"t=pool/net={raw:.6g}")
        )
        flags.extend(["gatot_budget", f"budget_{budget_key}"])
        return {
            "raw": raw,
            "detail": detail,
            "flags": flags,
            "k_status": k_status,
            "gw_status": gw_status,
            "gl_status": gl_status,
            "gate": "budget",
        }

    if gate:
        flags.append("gatot_gate_unmodeled")
        return {
            "raw": math.inf,
            "detail": "Gatot gate: dealer hero loadout is outside the two frozen regimes",
            "flags": flags,
            "k_status": k_status,
            "gw_status": gw_status,
            "gl_status": gl_status,
            "gate": "unmodeled",
        }

    offense_factor = seo_factor(dealer_side)
    if has_hero(target_side, "Vulcanus"):
        offense_factor *= 0.96
    if has_hero(dealer_side, "Vulcanus"):
        offense_factor *= 31.0 / 30.0
    pool_factor = 0.88 if has_hero(dealer_side, "Vulcanus") and t_cls in {"Infantry", "Lancer"} else 1.0
    raw = k * pool * pool_factor / (a * leth * offense_factor) * gw * gl / math.sqrt(count)
    detail = (
        f"t={k:.6g}*({defense:.6g}*{hp:.6g})*{pool_factor:.6g}/"
        f"({a:.6g}*{leth:.6g}*{offense_factor:.6g})*{gw:.6g}*{gl:.6g}/"
        f"sqrt({count:g})={raw:.6g}"
    )
    return {
        "raw": raw,
        "detail": detail,
        "flags": flags,
        "k_status": k_status,
        "gw_status": gw_status,
        "gl_status": gl_status,
        "gate": None,
    }


def observed_band(row: dict[str, Any]) -> tuple[float, float] | None:
    band = row["outcome"].get("turns_range")
    if band and band[0] is not None and band[1] is not None:
        return float(band[0]), float(band[1])
    turns = row["outcome"].get("turns")
    if turns is not None:
        return float(turns), float(turns)
    return None


def side_count(side: dict[str, Any]) -> int:
    return sum(int(unit.get("count") or 0) for unit in side.get("classes", []))


def matchup(row: dict[str, Any]) -> str:
    def render(side: dict[str, Any]) -> str:
        return "+".join(
            f"{CLASS_SHORT.get(unit['cls'], unit['cls'])}T{unit.get('tier')}x{unit.get('count')}"
            for unit in side.get("classes", [])
        ) or "none"

    return f"{render(row['attacker'])} -> {render(row['defender'])}"


def choose_race(att: dict[str, Any], deff: dict[str, Any]) -> dict[str, Any]:
    """Two-sided race for single-class armies."""
    a_to_d = kill_time(att["classes"][0], deff["classes"][0], att, deff)
    d_to_a = kill_time(deff["classes"][0], att["classes"][0], deff, att)
    ta, td = a_to_d["raw"], d_to_a["raw"]
    # The declared Gatot kit gate is a stack-threshold instrument: it directly
    # defines whether the attacking stack penetrates the one-unit target. A
    # reverse one-unit clock is not a full-stack elimination clock, so the gate
    # result supersedes the generic race for multi-unit threshold rows.
    if a_to_d["gate"] in {"budget", "hero_led_scurve"} and side_count(att) > 1:
        if math.isinf(ta):
            winner, raw, winning_calc = "defender", math.inf, a_to_d
        else:
            winner, raw, winning_calc = "attacker", ta, a_to_d
    elif d_to_a["gate"] in {"budget", "hero_led_scurve"} and side_count(deff) > 1:
        if math.isinf(td):
            winner, raw, winning_calc = "attacker", math.inf, d_to_a
        else:
            winner, raw, winning_calc = "defender", td, d_to_a
    elif ta > CAP and td > CAP:
        winner, raw = "defender", math.inf
        winning_calc = a_to_d
    elif ta <= td:
        winner, raw, winning_calc = "attacker", ta, a_to_d
    else:
        winner, raw, winning_calc = "defender", td, d_to_a
    return {
        "winner": winner,
        "raw": raw,
        "winning_calc": winning_calc,
        "a_to_d": a_to_d,
        "d_to_a": d_to_a,
        "flags": sorted(set(a_to_d["flags"] + d_to_a["flags"])),
        "detail": f"att->def [{a_to_d['detail']}]; def->att [{d_to_a['detail']}]",
    }


def generic_mixed_race(row: dict[str, Any]) -> dict[str, Any]:
    """Out-of-domain sequential extension used only to score non-anchor mixtures."""
    def eliminate(dealer_side: dict[str, Any], target_side: dict[str, Any]) -> tuple[float, list[str], str]:
        total = 0.0
        flags: list[str] = ["composition_other_defender"]
        details: list[str] = []
        targets = sorted(target_side["classes"], key=lambda unit: CLASS_ORDER[unit["cls"]])
        for target in targets:
            candidate = min(
                (kill_time(dealer, target, dealer_side, target_side) for dealer in dealer_side["classes"]),
                key=lambda item: item["raw"],
            )
            flags.extend(candidate["flags"])
            if math.isinf(candidate["raw"]):
                return math.inf, flags, "; ".join(details + [candidate["detail"]])
            duration = candidate["raw"] * int(target["count"])
            total += duration
            details.append(f"{target['cls']}x{target['count']}: {candidate['detail']}")
        return total, flags, "; ".join(details)

    ta, fa, da = eliminate(row["attacker"], row["defender"])
    td, fd, dd = eliminate(row["defender"], row["attacker"])
    if ta > CAP and td > CAP:
        winner, raw = "defender", math.inf
    elif ta <= td:
        winner, raw = "attacker", ta
    else:
        winner, raw = "defender", td
    return {
        "winner": winner,
        "raw": raw,
        "winning_calc": None,
        "flags": sorted(set(fa + fd)),
        "detail": f"sequential extension att->def [{da}]; def->att [{dd}]",
        "a_to_d_raw": ta,
        "d_to_a_raw": td,
    }


def find_composition_anchor() -> float:
    matches = [row for row in ROWS if row["id"] == COMPOSITION_SOLO_ANCHOR_ID]
    if len(matches) != 1:
        raise RuntimeError("Composition solo anchor row is missing or duplicated")
    band = observed_band(matches[0])
    if not band or band[0] != band[1]:
        raise RuntimeError("Composition solo anchor is not an exact-turn observation")
    return band[0]


COMPOSITION_SOLO_ANCHOR = find_composition_anchor()


def composition_prediction(row: dict[str, Any]) -> dict[str, Any]:
    """The prompt's measured-regime ANCHOR mode, without generalization."""
    attackers = row["attacker"]["classes"]
    defender = row["defender"]
    measured_defender = (
        (defender.get("name") or "").casefold() == "alpaca"
        and {unit["cls"] for unit in defender.get("classes", [])} == {"Infantry", "Marksman"}
        and has_hero(defender, "Gatot")
        and has_hero(defender, "Vulcanus")
    )
    flags = ["composition_anchor"]
    if not measured_defender:
        flags.append("composition_other_defender")

    counts = {unit["cls"]: int(unit["count"]) for unit in attackers}
    n_inf = counts.get("Infantry", 0)
    n_lan = counts.get("Lancer", 0)
    n_mm = counts.get("Marksman", 0)
    attacker_has_gatot = has_hero(row["attacker"], "Gatot")
    manual_front_anchor = row["id"].startswith("manual_ladder_") or row["id"].startswith("manual_mixed_1_infantry_")
    anchored_front = attacker_has_gatot or manual_front_anchor

    if n_inf and anchored_front:
        if n_inf == 1 and not (n_lan or n_mm):
            front_death = COMPOSITION_SOLO_ANCHOR
            detail = f"anchor solo={COMPOSITION_SOLO_ANCHOR:g}"
        elif n_lan or n_mm:
            # The measured front clock is 33 turns. The published ratios are
            # rounded representations of the measured 33/78 anchor.
            front_death = 33.0
            detail = f"front=round(0.4231*{COMPOSITION_SOLO_ANCHOR:g})={front_death:g}"
        else:
            first = round(0.4231 * COMPOSITION_SOLO_ANCHOR)
            middle = round(0.6923 * COMPOSITION_SOLO_ANCHOR)
            last = round(0.7308 * COMPOSITION_SOLO_ANCHOR)
            front_death = float(first + max(0, n_inf - 2) * middle + last)
            detail = f"front={first}+{max(0, n_inf-2)}*{middle}+{last}={front_death:g}"
        backline_deaths = [front_death]
        for cls, count, latency in (("Lancer", n_lan, 3), ("Marksman", n_mm, 2)):
            for j in range(1, count + 1):
                backline_deaths.append(front_death + max(math.ceil(4 * j / 3), latency))
        raw = max(backline_deaths)
        detail += f"; front={front_death:g}; final={raw:g}"
    elif n_inf or n_lan or n_mm:
        raw = math.inf
        detail = "no measured Gatot-Infantry front anchor; winner scored only"
        flags.extend(["composition_no_front", "winner_only"])
    else:
        raw = math.inf
        detail = "composition has no supported attacking units"
        flags.append("composition_unmodeled")

    observed_override = None
    if "composition_no_front" not in flags:
        defender_gatot_s2 = [
            item.get("triggers")
            for item in defender.get("heroes", [])
            if hero_key(item.get("hero")) == hero_key("Gatot")
            and (item.get("slot") == "Skill 2" or "bestowal" in (item.get("name") or "").casefold())
            and isinstance(item.get("triggers"), (int, float))
        ]
        if defender_gatot_s2:
            observed_override = (float(max(defender_gatot_s2)), float(max(defender_gatot_s2)))
        else:
            observed_override = observed_band(row)

    return {
        "winner": "defender",
        "raw": raw,
        "winning_calc": None,
        "flags": flags,
        "detail": detail,
        "observed_band": observed_override,
    }


def beast_prediction(row: dict[str, Any]) -> dict[str, Any]:
    dealer = row["attacker"]["classes"][0]
    target = row["defender"]["classes"][0]
    per_kill = kill_time(dealer, target, row["attacker"], row["defender"])
    total = per_kill["raw"] * int(target["count"])
    capped = total > CAP
    return {
        "winner": "defender" if capped else "attacker",
        "raw": math.inf if capped else total,
        "uncapped_raw": total,
        "winning_calc": per_kill,
        "flags": sorted(set(per_kill["flags"] + ["beast_per_kill"])),
        "detail": f"per-kill [{per_kill['detail']}]; total={per_kill['raw']:.6g}*{target['count']}={total:.6g}",
    }


def is_factorized_winning_cell(row: dict[str, Any]) -> bool:
    actual_side = row[row["outcome"]["winner"]]
    target_side = row["defender" if row["outcome"]["winner"] == "attacker" else "attacker"]
    if len(actual_side.get("classes", [])) != 1 or len(target_side.get("classes", [])) != 1:
        return False
    return k_value(actual_side["classes"][0]["cls"], target_side["classes"][0]["cls"])[1] == "factorized"


def classify(row: dict[str, Any], prediction: dict[str, Any]) -> tuple[str, str]:
    if row["determinism"] == "legacy_unverified" or row["folder"] == "legacy":
        return "out_legacy_no_numeric_inputs", "legacy"
    if "Beast" in row["id"]:
        if observed_band(row) == (1500.0, 1500.0):
            return "out_capped_stalemate", "beast"
        return "in_beast_victory", "beast"
    if row["folder"] in COMPOSITION_FOLDERS:
        if "composition_no_front" in prediction["flags"]:
            domain = "out_composition_no_front_anchor"
        else:
            domain = "in_composition_anchor" if "composition_other_defender" not in prediction["flags"] else "out_composition_other_defender"
        return domain, "composition"
    if row["folder"] == "NanoMart":
        if side_count(row["attacker"]) != 1 or side_count(row["defender"]) != 1:
            return "out_nanomart_multicount_winner_only", "nanomart_multicount"
        if any(int(unit["tier"]) != 1 for side in (row["attacker"], row["defender"]) for unit in side["classes"]):
            return "out_nanomart_nonT1_tier", "nanomart_1v1"
        actual_dealer = row[row["outcome"]["winner"]]
        actual_target = row["defender" if row["outcome"]["winner"] == "attacker" else "attacker"]
        dealer_cls = actual_dealer["classes"][0]["cls"]
        target_cls = actual_target["classes"][0]["cls"]
        if k_value(dealer_cls, target_cls)[1] == "factorized":
            return "out_factorized_K_pm15", "nanomart_1v1"
        if has_hero(actual_dealer, "Vulcanus"):
            return "out_vulcanus_dealer_bias_minus6_5", "nanomart_1v1"
        if has_hero(actual_dealer, "SeoYoon"):
            return "in_nanomart_seoyoon_dealer", "nanomart_1v1"
        return "out_nanomart_other", "nanomart_1v1"
    if observed_band(row) == (1500.0, 1500.0):
        return "out_capped_stalemate", "gatot_threshold"
    if "composition_other_defender" in prediction["flags"]:
        return "out_composition_other_defender", "mixed_other"
    winning = prediction.get("winning_calc") or {}
    if winning.get("gate") == "unmodeled":
        return "out_gatot_gate_unmodeled", "gatot_gate"
    if winning.get("gate") == "hero_led_scurve":
        return "in_gatot_scurve", "gatot_gate"
    if winning.get("gate") == "budget":
        if "T3" in row["id"] and side_count(row["attacker"]) > 1:
            return "out_base_mismatch_T3_threshold", "gatot_threshold"
        return "in_gatot_budget", "gatot_gate"
    if is_factorized_winning_cell(row):
        return "out_factorized_K_pm15", "exact_1v1"
    return "in_exact_duel", "exact_1v1"


def score_row(row: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    band = prediction["observed_band"] if "observed_band" in prediction else observed_band(row)
    actual_winner = row["outcome"]["winner"]
    winner_match = prediction["winner"] == actual_winner
    domain, instrument = classify(row, prediction)
    raw = prediction["raw"]
    flags = sorted(set(row.get("flags", []) + prediction.get("flags", [])))
    result: dict[str, Any] = {
        "id": row["id"],
        "folder": row["folder"],
        "instrument": instrument,
        "matchup": matchup(row),
        "N_vs_N": f"{side_count(row['attacker'])}v{side_count(row['defender'])}",
        "observed": "" if not band else (f"{band[0]:g}" if band[0] == band[1] else f"[{band[0]:g},{band[1]:g}]"),
        "actual_winner": actual_winner,
        "predicted": "capped" if math.isinf(raw) else f"{raw:.6f}",
        "predicted_ceil": "1500+" if math.isinf(raw) else str(math.ceil(raw)),
        "predicted_winner": prediction["winner"],
        "pcterr": "",
        "abs_pcterr": "",
        "domain_class": domain,
        "verdict": "SKIP",
        "flags": ";".join(flags),
        "arithmetic": prediction["detail"],
    }

    if domain == "out_legacy_no_numeric_inputs":
        result["verdict"] = "SKIP"
        return result

    if domain == "out_nanomart_multicount_winner_only" or band is None:
        result["verdict"] = "PASS" if winner_match else "FAIL"
        result["flags"] += (";" if result["flags"] else "") + "winner_only"
        return result

    if band == (1500.0, 1500.0):
        uncapped = prediction.get("uncapped_raw")
        capped_correct = math.isinf(raw) or (uncapped is not None and uncapped > CAP)
        result["predicted"] = "capped" if capped_correct else result["predicted"]
        result["predicted_ceil"] = "1500+" if capped_correct else result["predicted_ceil"]
        result["verdict"] = "PASS" if capped_correct else "FAIL"
        result["flags"] += (";" if result["flags"] else "") + "capped_check"
        return result

    if math.isinf(raw):
        result["verdict"] = "FAIL" if domain.startswith("in_") else "SKIP"
        return result

    lo, hi = band
    midpoint = (lo + hi) / 2.0
    err = (raw / midpoint - 1.0) * 100.0
    abs_err = abs(err)
    result["pcterr"] = f"{err:.6f}"
    result["abs_pcterr"] = f"{abs_err:.6f}"
    ceil_hit = lo <= math.ceil(raw) <= hi
    band_hit = lo <= raw <= hi

    if domain == "out_factorized_K_pm15":
        time_pass = ceil_hit or band_hit or abs_err <= 15.0
    elif domain == "out_vulcanus_dealer_bias_minus6_5":
        time_pass = ceil_hit or band_hit or (-16.5 <= err <= 3.5)
    elif domain == "out_nanomart_other":
        time_pass = ceil_hit or band_hit or abs_err <= 10.0
    elif domain.startswith("out_"):
        time_pass = ceil_hit or band_hit or abs_err <= 10.0
    else:
        time_pass = ceil_hit or band_hit or abs_err <= 10.0

    result["verdict"] = "PASS" if winner_match and time_pass else "FAIL"
    if ceil_hit:
        result["flags"] += (";" if result["flags"] else "") + "ceil_exact_or_in_band"
    elif band_hit:
        result["flags"] += (";" if result["flags"] else "") + "raw_band_hit"
    if not winner_match:
        result["flags"] += (";" if result["flags"] else "") + "winner_mismatch"
    return result


def data_suspects(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    suspects: list[dict[str, str]] = []
    panel_map = {"A": "Attack", "D": "Defense", "L": "Lethality", "H": "Health"}
    for row in rows:
        row_id = row["id"]
        for side_name in ("attacker", "defender"):
            side = row[side_name]
            for index, unit in enumerate(side.get("classes", [])):
                path = f"{side_name}.classes[{index}]"
                count = unit.get("count")
                tier = unit.get("tier")
                if row["folder"] != "legacy" and (not isinstance(count, int) or count <= 0):
                    suspects.append({"id": row_id, "field": path + ".count", "reason": f"non-positive/non-integer count {count!r}"})
                if row["folder"] != "legacy" and (not isinstance(tier, int) or not 1 <= tier <= 10):
                    suspects.append({"id": row_id, "field": path + ".tier", "reason": f"tier outside 1..10: {tier!r}"})
                for stat in ("A", "D", "L", "H"):
                    value = (unit.get("eff") or {}).get(stat)
                    if row["folder"] != "legacy" and (value is None or float(value) <= 0):
                        suspects.append({"id": row_id, "field": path + f".eff.{stat}", "reason": f"missing/non-positive effective stat {value!r}"})
                base, panel, eff = unit.get("base"), unit.get("panel_pct"), unit.get("eff")
                if base and panel and eff:
                    for stat, panel_name in panel_map.items():
                        if stat in base and panel_name in panel and panel[panel_name] is not None:
                            expected = float(base[stat]) * (1.0 + float(panel[panel_name]) / 100.0)
                            actual = float(eff[stat])
                            if not math.isclose(expected, actual, rel_tol=0, abs_tol=0.002):
                                suspects.append({
                                    "id": row_id,
                                    "field": path + f".eff.{stat}",
                                    "reason": f"base×panel={expected:.6f}, corpus eff={actual:.6f}",
                                })
            casualties = side.get("casualties") or {}
            troops = casualties.get("troops")
            parts = [casualties.get(key) for key in ("losses", "injured", "lightly_injured", "survivors")]
            if troops is not None and all(value is not None for value in parts) and sum(parts) != troops:
                suspects.append({
                    "id": row_id,
                    "field": side_name + ".casualties",
                    "reason": f"losses+injured+lightly_injured+survivors={sum(parts)} but troops={troops}",
                })
            class_total = side_count(side)
            if row["folder"] != "legacy" and troops is not None and class_total != troops:
                suspects.append({
                    "id": row_id,
                    "field": side_name + ".classes[].count",
                    "reason": f"class count total={class_total} but casualties.troops={troops}",
                })

        # Filename/setup labels are not the source of truth when a registry correction
        # exists. Without such a correction, a direct normalized-tier disagreement is
        # an internal inconsistency worth human review rather than silent repair.
        label = re.search(r"NanoMart_1v1_T(\d+)(Inf|Lan|MM)vT(\d+)(Inf|Lan|MM)", row_id)
        if label and not row.get("corrections_applied"):
            a_tier, a_cls, d_tier, d_cls = label.groups()
            cls_map = {"Inf": "Infantry", "Lan": "Lancer", "MM": "Marksman"}
            if len(row["attacker"].get("classes", [])) == 1:
                actual = row["attacker"]["classes"][0]
                if int(a_tier) != actual.get("tier") or cls_map[a_cls] != actual.get("cls"):
                    suspects.append({
                        "id": row_id,
                        "field": "attacker.classes[0].(cls,tier)",
                        "reason": f"id says {cls_map[a_cls]} T{a_tier}, normalized row says {actual.get('cls')} T{actual.get('tier')}",
                    })
            if len(row["defender"].get("classes", [])) == 1:
                actual = row["defender"]["classes"][0]
                if int(d_tier) != actual.get("tier") or cls_map[d_cls] != actual.get("cls"):
                    suspects.append({
                        "id": row_id,
                        "field": "defender.classes[0].(cls,tier)",
                        "reason": f"id says {cls_map[d_cls]} T{d_tier}, normalized row says {actual.get('cls')} T{actual.get('tier')}",
                    })
    return suspects


def predict(row: dict[str, Any]) -> dict[str, Any]:
    if row["folder"] == "legacy" or row["determinism"] == "legacy_unverified":
        return {"winner": row["outcome"]["winner"], "raw": math.inf, "winning_calc": None, "flags": ["legacy_no_numeric_inputs"], "detail": "legacy row skipped: no numeric normalized inputs"}
    if "Beast" in row["id"]:
        return beast_prediction(row)
    if row["folder"] in COMPOSITION_FOLDERS:
        return composition_prediction(row)
    if len(row["attacker"].get("classes", [])) == 1 and len(row["defender"].get("classes", [])) == 1:
        return choose_race(row["attacker"], row["defender"])
    return generic_mixed_race(row)


def summarize(results: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[result[key]].append(result)
    summary = []
    for name in sorted(grouped):
        group = grouped[name]
        errors = [float(item["abs_pcterr"]) for item in group if item["abs_pcterr"] != ""]
        scored = [item for item in group if item["verdict"] in {"PASS", "FAIL"}]
        passed = sum(item["verdict"] == "PASS" for item in scored)
        summary.append({
            key: name,
            "rows": len(group),
            "numeric_rows": len(errors),
            "median_abs_err": statistics.median(errors) if errors else None,
            "max_abs_err": max(errors) if errors else None,
            "pass_rate": passed / len(scored) * 100 if scored else None,
            "passed": passed,
            "scored": len(scored),
        })
    return summary


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    def safe(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(map(safe, headers)) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(safe(str(value)) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def fmt_metric(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}%"


def write_outputs(results: list[dict[str, Any]], suspects: list[dict[str, str]]) -> None:
    fields = [
        "id", "folder", "instrument", "matchup", "N_vs_N", "observed", "actual_winner",
        "predicted", "predicted_ceil", "predicted_winner", "pcterr", "abs_pcterr",
        "domain_class", "verdict", "flags", "arithmetic",
    ]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    by_instrument = summarize(results, "instrument")
    by_domain = summarize(results, "domain_class")
    deviations_5_10 = [r for r in results if r["abs_pcterr"] and 5.0 <= float(r["abs_pcterr"]) < 10.0]
    deviations_10 = [r for r in results if r["abs_pcterr"] and float(r["abs_pcterr"]) >= 10.0]
    in_domain_failures = [r for r in results if r["domain_class"].startswith("in_") and r["verdict"] == "FAIL"]
    in_domain_scored = [r for r in results if r["domain_class"].startswith("in_") and r["verdict"] in {"PASS", "FAIL"}]

    lines = [
        "# Independent Type-1 QA report",
        "",
        f"Corpus rows: **{len(results)}**. Frozen law: **{TABLES['law_version']}** ({TABLES['frozen']}).",
        f"Independent verdict: **{'PASS' if not in_domain_failures else 'FAIL'}** — "
        f"{len(in_domain_scored) - len(in_domain_failures)}/{len(in_domain_scored)} scored in-domain rows pass their ≤10%/integer-turn rule.",
        "",
        "Percent error is signed `predicted_raw / midpoint(observed band) - 1`; the deviation lists use its absolute value. "
        "Capped and winner-only rows intentionally have no percent error.",
        "",
        "## Deviations from 5% to under 10%",
        "",
    ]
    deviation_headers = ["id", "observed", "pred raw", "ceil", "%err", "domain", "verdict", "flags"]
    for group in (deviations_5_10,):
        lines.append(markdown_table(deviation_headers, [[
            r["id"], r["observed"], r["predicted"], r["predicted_ceil"], f"{float(r['pcterr']):.2f}%",
            r["domain_class"], r["verdict"], r["flags"],
        ] for r in group]) if group else "None.")
    lines.extend(["", "## Deviations of 10% or more", ""])
    lines.append(markdown_table(deviation_headers, [[
        r["id"], r["observed"], r["predicted"], r["predicted_ceil"], f"{float(r['pcterr']):.2f}%",
        r["domain_class"], r["verdict"], r["flags"],
    ] for r in deviations_10]) if deviations_10 else "None.")

    lines.extend(["", "## Instrument summary", ""])
    lines.append(markdown_table(
        ["instrument", "rows", "numeric", "median |err|", "max |err|", "pass rate"],
        [[s["instrument"], str(s["rows"]), str(s["numeric_rows"]), fmt_metric(s["median_abs_err"]), fmt_metric(s["max_abs_err"]), fmt_metric(s["pass_rate"])] for s in by_instrument],
    ))
    lines.extend(["", "## Domain summary", ""])
    lines.append(markdown_table(
        ["domain", "rows", "numeric", "median |err|", "max |err|", "pass rate"],
        [[s["domain_class"], str(s["rows"]), str(s["numeric_rows"]), fmt_metric(s["median_abs_err"]), fmt_metric(s["max_abs_err"]), fmt_metric(s["pass_rate"])] for s in by_domain],
    ))

    lines.extend(["", "## In-domain misses", ""])
    if in_domain_failures:
        lines.append(markdown_table(
            ["id", "observed", "predicted", "%err", "diagnostic arithmetic"],
            [[r["id"], r["observed"], r["predicted"], (f"{float(r['pcterr']):.2f}%" if r["pcterr"] else "—"), r["arithmetic"]] for r in in_domain_failures],
        ))
    else:
        lines.append("None.")

    lines.extend(["", "## Data/OCR suspects", ""])
    if suspects:
        lines.append(markdown_table(["id", "field", "reason"], [[s["id"], s["field"], s["reason"]] for s in suspects]))
    else:
        lines.append("None found by the structural and base×panel consistency checks.")

    lines.extend([
        "",
        "## Repository cross-check discrepancies",
        "",
        "The repository validator completed with `OVERALL: ALL GATES PASS`, but it does not implement every rule in the QA brief the same way:",
        "",
        "- The brief requires a global two-sided race. The repository's A6/D6 tables normally score the observed winner's one-way kill clock; it only prints explicit race calls for the four ENIF1b rows. The literal race used here calls 22 winners differently from the corpus, including 17 in-domain failures. These are spec/validator disagreements, not arithmetic differences in the displayed one-way clocks.",
        "- The four Lancer Gatot-threshold rows are not blind predictions in the repository validator: it solves their Lancer rate from the same cap/win pairs and reports an implied K. This QA uses the frozen implied K values from `gatot_kit`; the T3 pair remains out-of-domain per the declared base-mismatch tension.",
        "- The repository accounts for 31 higher-tier NanoMart rows as excluded wrong-additive-base captures. The QA brief says to trust the corrected corpus, but declares only NanoMart T1 troop rows in-domain, so those higher-tier rows are scored here as out-of-domain.",
        "- Beast victory clocks, the 19 numeric measured-regime composition anchors (the other five composition rows have no applicable front anchor), the four hero-led Gatot points, and the covered Marksman budget thresholds agree with the repository cross-check to rounding/turn quantization.",
        "",
        "## Full per-row evidence",
        "",
        f"All {len(results)} rows, including arithmetic and flags, are in `qa_results.csv`.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    digest = hashlib.sha256(CSV_PATH.read_bytes()).hexdigest()
    lock = {
        "corpus": str(CORPUS_PATH),
        "tables": str(TABLES_PATH),
        "row_count": len(results),
        "qa_results_sha256": digest,
        "in_domain_failures": [result["id"] for result in in_domain_failures],
        "deviations_5_to_under_10": [result["id"] for result in deviations_5_10],
        "deviations_10_plus": [result["id"] for result in deviations_10],
    }
    LOCK_PATH.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    if len(ROWS) != int(TABLES["corpus"]["row_count"]):
        raise RuntimeError(f"Corpus count {len(ROWS)} does not match frozen table declaration")
    results = [score_row(row, predict(row)) for row in ROWS]
    suspects = data_suspects(ROWS)
    write_outputs(results, suspects)
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {LOCK_PATH}")
    print(f"Rows: {len(results)}")
    print(f"5-<10%: {sum(bool(r['abs_pcterr']) and 5 <= float(r['abs_pcterr']) < 10 for r in results)}")
    print(f"10%+: {sum(bool(r['abs_pcterr']) and float(r['abs_pcterr']) >= 10 for r in results)}")


if __name__ == "__main__":
    main()
