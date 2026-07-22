"""Independent V3 wiring/adoption QA harness.

Writes only beside this file.  Corpus inputs are constructed here; project
code is called only through the public deterministic seam (except the safe
table-emitter redirection required by W5).
"""
from __future__ import annotations

import ast
import builtins
import copy
import csv
import dataclasses
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

sys.dont_write_bytecode = True

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CORPUS_PATH = ROOT / "wos_sim" / "data" / "experiments" / "_corpus" / "TYPE1_CORPUS.json"
TABLE_PATH = ROOT / "wos_sim" / "formula_research" / "stage6_tables.json"
V2_PATH = ROOT / "wos_sim" / "formula_research" / "qa_codex_v2" / "qa_type1_v2.py"
CSV_PATH = OUT / "qa3_results.csv"
CORE_PATH = OUT / "qa3_core.json"
EMIT1 = OUT / "stage6_tables_emit_1.json"
EMIT2 = OUT / "stage6_tables_emit_2.json"

CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
ROWS: list[dict[str, Any]] = CORPUS["rows"]
BY_ID = {row["id"]: row for row in ROWS}
FROZEN = json.loads(TABLE_PATH.read_text(encoding="utf-8"))

from wos_sim.predictor import api  # noqa: E402
from wos_sim.predictor.profiles import SideProfile  # noqa: E402
from wos_sim.formula_research import stage6_tables as t6  # noqa: E402


def load_v2():
    spec = importlib.util.spec_from_file_location("codex_v2_independent", V2_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load independent V2 checker")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V2 = load_v2()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(side: dict[str, Any]) -> dict[str, Any] | None:
    classes = side.get("classes") or []
    return classes[0] if len(classes) == 1 else None


def scoreable(row: dict[str, Any]) -> bool:
    """Rebuild the documented W6-shaped 170-row subset from corpus fields."""
    ua, ud = one(row["attacker"]), one(row["defender"])
    if ua is None or ud is None:
        return False
    if row.get("determinism") == "legacy_unverified" or "Beast" in row["id"]:
        return False
    if row["folder"] in {"Meuller_Alpaca_v5_8_Battle", "MuellerAlpaca_Gatot_2v2"}:
        return False
    if row["id"].startswith(("manual_mixed", "manual_")):
        return False
    if row["folder"] == "NanoMart" and (ua["tier"] != 1 or ud["tier"] != 1):
        return False
    outcome = row["outcome"]
    if outcome.get("winner") not in {"attacker", "defender"}:
        return False
    return outcome.get("turns") is not None or outcome.get("turns_range") is not None


def army_from(side: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "cls": unit["cls"],
            "tier": unit["tier"],
            "fc": unit.get("fc"),
            "count": unit["count"],
            "eff": copy.deepcopy(unit["eff"]),
            "panel_pct": copy.deepcopy(unit.get("panel_pct")),
        }
        for unit in side["classes"]
    ]


def hero_names(side: dict[str, Any]) -> set[str]:
    return {str(hero.get("hero")) for hero in side.get("heroes", [])}


def kit_from(side: dict[str, Any]) -> dict[str, Any] | None:
    """Independent corpus-name -> public kit-token mapping from HERO_KITS.md."""
    hs = hero_names(side)
    kit: dict[str, Any] = {}
    if "Gatot" in hs:
        name = (side.get("name") or "").casefold()
        if any(token in name for token in ("mueller", "muller", "müller")):
            kit["gatot"] = "mueller"
        elif "far seer" in name or "farseer" in name:
            kit["gatot"] = "farseer"
        elif "alpaca" in name or (any(ord(ch) > 127 for ch in name) and "müller" not in name):
            kit["gatot"] = "alpaca"
        else:
            kit["gatot"] = True
    if "Vulcanus" in hs:
        kit["vulcanus"] = True
    other = hs - {"Gatot", "Vulcanus"}
    if kit and other:
        # The public seam tolerates extra keys and uses their truthiness to
        # avoid silently treating an unmeasured hero-led dealer as hero-less.
        kit["other_heroes"] = sorted(other)
    return kit or None


def offense_mult(row: dict[str, Any], dealer_side: str) -> float:
    """Independent deterministic hero folds from HERO_KITS.md.

    W6 historically supplies these only for NanoMart rows; V3 requires the
    caller-side construction sensitivity to be made explicit.
    """
    dealer = row[dealer_side]
    enemy_key = "defender" if dealer_side == "attacker" else "attacker"
    enemy = row[enemy_key]
    dunit, target = one(dealer), one(enemy)
    if dunit is None or target is None:
        return 1.0
    mult = 1.0
    for hero in dealer.get("heroes", []):
        if hero.get("hero") == "SeoYoon" and hero.get("slot") == "Skill 1":
            mult *= {1: 1.05, 2: 1.10, 3: 1.15}.get(hero.get("level") or 3, 1.15)
        if hero.get("hero") == "Vulcanus":
            if hero.get("slot") == "Skill 2":
                mult *= 31.0 / 30.0
            if hero.get("slot") == "Skill 3" and target["cls"] in {"Infantry", "Lancer"}:
                mult /= 0.88
            if hero.get("slot") == "Skill 3" and dunit["cls"] == "Marksman":
                mult *= 1.04
    for hero in enemy.get("heroes", []):
        if hero.get("hero") == "Vulcanus" and hero.get("slot") == "Skill 1":
            mult *= 0.96
    return mult


def seam_class(row: dict[str, Any], result: dict[str, Any]) -> tuple[str, float | None, float | None, float | None]:
    if result.get("winner") == "uncertain":
        return "ABSTAIN", None, None, None
    t_att = float(result["att_deaths"][-1][0])
    t_def = float(result["def_deaths"][-1][0])
    gap = abs(t_att - t_def) / min(t_att, t_def) * 100.0 if min(t_att, t_def) > 0 else math.inf
    if gap <= 10.0:
        verdict = "COIN_FLIP"
    elif result.get("winner") == row["outcome"]["winner"]:
        verdict = "CORRECT"
    else:
        verdict = "WRONG"
    return verdict, gap, t_att, t_def


def independent_clock_check(row: dict[str, Any], result: dict[str, Any], mult_a: float, mult_d: float) -> dict[str, Any]:
    """Verify single-count plain clocks with the independent V2 arithmetic."""
    if result.get("winner") == "uncertain":
        return {"status": "ABSTAIN_OUTPUT"}
    ua, ud = one(row["attacker"]), one(row["defender"])
    if ua is None or ud is None or ua["count"] != 1 or ud["count"] != 1:
        return {"status": "WINNER_ONLY_MULTICOUNT"}
    flags = set(result.get("flags") or [])
    if any("gatot_budget" in flag or "gatot_scurve" in flag or "gatot_kit_target" in flag for flag in flags):
        return {"status": "GATOT_SPECIAL_REGIME"}
    try:
        pred = V2.predict(row)
        a_raw, d_raw = pred.get("a_clock"), pred.get("d_clock")
        if a_raw is None or d_raw is None or math.isinf(a_raw) or math.isinf(d_raw):
            return {"status": "V2_UNSCORED"}
        # V2 already applies the documented folds. The seam received those
        # folds only in NanoMart W1 construction, matching W6.
        expect_t_def = math.ceil(a_raw)
        expect_t_att = math.ceil(d_raw)
        actual_t_att = result["att_deaths"][-1][0]
        actual_t_def = result["def_deaths"][-1][0]
        ok = actual_t_att == expect_t_att and actual_t_def == expect_t_def
        return {
            "status": "MATCH" if ok else "CLOCK_DIFFERENCE",
            "v2_t_att_dead": expect_t_att,
            "v2_t_def_dead": expect_t_def,
            "seam_t_att_dead": actual_t_att,
            "seam_t_def_dead": actual_t_def,
            "att_offense_mult": mult_a,
            "def_offense_mult": mult_d,
        }
    except Exception as exc:  # evidence, never hide an independent-check failure
        return {"status": "V2_CHECK_ERROR", "error": f"{type(exc).__name__}: {exc}"}


def run_w1() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output: list[dict[str, Any]] = []
    score_rows = [row for row in ROWS if scoreable(row)]
    if len(score_rows) != 170:
        raise AssertionError(f"W1 subset is {len(score_rows)}, expected 170")
    for row in score_rows:
        att = army_from(row["attacker"])
        dfn = army_from(row["defender"])
        att_kit, def_kit = kit_from(row["attacker"]), kit_from(row["defender"])
        mult_a = offense_mult(row, "attacker") if row["folder"] == "NanoMart" else 1.0
        mult_d = offense_mult(row, "defender") if row["folder"] == "NanoMart" else 1.0
        before = copy.deepcopy((att, dfn, att_kit, def_kit))
        result = api.predict_deterministic_battle(
            att, dfn, att_offense_mult=mult_a, def_offense_mult=mult_d,
            att_kit=att_kit, def_kit=def_kit,
        )
        mutated = before != (att, dfn, att_kit, def_kit)
        classification, gap, t_att, t_def = seam_class(row, result)
        arithmetic = independent_clock_check(row, result, mult_a, mult_d)
        output.append({
            "record_type": "W1",
            "section": "W1",
            "id": row["id"],
            "folder": row["folder"],
            "observed_winner": row["outcome"]["winner"],
            "seam_winner": result.get("winner"),
            "classification": classification,
            "clock_gap_pct": gap,
            "att_dead_clock": t_att,
            "def_dead_clock": t_def,
            "expected": "151 CORRECT / 15 COIN_FLIP / 1 ABSTAIN / 3 WRONG",
            "pass": True,
            "finding_class": "KNOWN_OPEN" if classification == "WRONG" else "",
            "flags": result.get("flags", []),
            "gatot_abstain": result.get("gatot_abstain"),
            "law_version": (result.get("meta") or {}).get("law_version"),
            "input_mutated": mutated,
            "arithmetic": arithmetic,
            "details": "",
        })
    counts = {key: sum(item["classification"] == key for item in output)
              for key in ("CORRECT", "COIN_FLIP", "ABSTAIN", "WRONG")}
    expected = {"CORRECT": 151, "COIN_FLIP": 15, "ABSTAIN": 1, "WRONG": 3}
    wrong_ids = [item["id"] for item in output if item["classification"] == "WRONG"]
    abstain_ids = [item["id"] for item in output if item["classification"] == "ABSTAIN"]
    return output, {
        "scoreable": len(output),
        "counts": counts,
        "expected": expected,
        "scorecard_match": counts == expected,
        "wrong_ids": wrong_ids,
        "abstain_ids": abstain_ids,
        "law_versions": sorted({item["law_version"] for item in output}),
        "mutated_inputs": [item["id"] for item in output if item["input_mutated"]],
        "arithmetic_status": {
            status: sum(item["arithmetic"].get("status") == status for item in output)
            for status in sorted({item["arithmetic"].get("status") for item in output})
        },
        "arithmetic_differences": [
            {"id": item["id"], **item["arithmetic"]}
            for item in output if item["arithmetic"].get("status") == "CLOCK_DIFFERENCE"
        ],
    }


def unit(cls: str, tier: int, count: int, A: float, D: float, L: float, H: float,
         panel_a: float | None = None) -> list[dict[str, Any]]:
    value: dict[str, Any] = {
        "cls": cls, "tier": tier, "count": count,
        "eff": {"A": A, "D": D, "L": L, "H": H},
    }
    if panel_a is not None:
        value["panel_pct"] = {"Attack": panel_a}
    return [value]


def lancers(n: int) -> list[dict[str, Any]]:
    return unit("Lancer", 6, n, 27.91, 21.536, 22.583, 14.182)


def alpaca_target(count: int = 1, panel: bool = True) -> list[dict[str, Any]]:
    return unit("Infantry", 1, count, 6.141, 24.276, 2.097, 12.558,
                514.1 if panel else None)


def mueller_target(count: int = 1, panel: bool = True) -> list[dict[str, Any]]:
    return unit("Infantry", 1, count, 5.81, 23.268, 2.12, 12.522,
                481.0 if panel else None)


def summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "winner": result.get("winner"),
        "turns": result.get("turns"),
        "att_dead_clock": (result.get("att_deaths") or [[None]])[-1][0] if result.get("att_deaths") else None,
        "def_dead_clock": (result.get("def_deaths") or [[None]])[-1][0] if result.get("def_deaths") else None,
        "flags": result.get("flags"),
        "gatot_abstain": result.get("gatot_abstain"),
        "meta": result.get("meta"),
    }


def safe_seam(att: list[dict[str, Any]], dfn: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    try:
        return {"crashed": False, "result": api.predict_deterministic_battle(att, dfn, **kwargs)}
    except Exception as exc:
        return {"crashed": True, "exception": f"{type(exc).__name__}: {exc}"}


def mirror_ok(first: dict[str, Any], swapped: dict[str, Any]) -> bool:
    if first.get("crashed") or swapped.get("crashed"):
        return False
    a, b = first["result"], swapped["result"]
    expected = {"attacker": "defender", "defender": "attacker", "uncertain": "uncertain"}.get(a.get("winner"))
    if b.get("winner") != expected:
        return False
    if a.get("winner") == "uncertain":
        return True
    return (a["att_deaths"][-1][0] == b["def_deaths"][-1][0]
            and a["def_deaths"][-1][0] == b["att_deaths"][-1][0])


def run_w2() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def add(name: str, actual: Any, expected: str, passed: bool,
            finding: str = "", details: str = "") -> None:
        if isinstance(actual, dict) and "result" in actual and not actual.get("crashed"):
            summary = summarize_result(actual["result"])
            seam_winner = summary["winner"]
            flags = summary["flags"] or []
        else:
            summary = actual
            seam_winner = None
            flags = []
        records.append({
            "record_type": "W2", "section": "W2", "id": name, "folder": "probe",
            "observed_winner": "", "seam_winner": seam_winner, "classification": "",
            "clock_gap_pct": None, "att_dead_clock": None, "def_dead_clock": None,
            "expected": expected, "pass": passed,
            "finding_class": finding if not passed else "", "flags": flags,
            "gatot_abstain": summary.get("gatot_abstain") if isinstance(summary, dict) else None,
            "law_version": ((summary.get("meta") or {}).get("law_version")
                            if isinstance(summary, dict) else None),
            "input_mutated": False, "arithmetic": {},
            "details": details or json.dumps(summary, ensure_ascii=False, default=str),
        })

    # State detection and explicit override behavior.
    missing = safe_seam(lancers(50), alpaca_target(panel=False), def_kit={"gatot": "alpaca"})
    add("missing_panel_known_copy", missing, "ABSTAIN", not missing["crashed"] and missing["result"]["winner"] == "uncertain",
        "SEAM_BUG")
    missing_sw = safe_seam(alpaca_target(panel=False), lancers(50), att_kit={"gatot": "alpaca"})
    add("missing_panel_side_swap", {"first": missing, "swapped": missing_sw}, "mirror ABSTAIN", mirror_ok(missing, missing_sw), "SEAM_BUG")

    halfway = unit("Infantry", 1, 1, 4.5, 17.0, 2.1, 10.0, 345.125)
    ambiguous = safe_seam(lancers(50), halfway, def_kit={"gatot": "alpaca"})
    add("halfway_panel_ambiguous", ambiguous, "ABSTAIN", not ambiguous["crashed"] and ambiguous["result"]["winner"] == "uncertain", "SEAM_BUG")
    ambiguous_sw = safe_seam(halfway, lancers(50), att_kit={"gatot": "alpaca"})
    add("halfway_panel_side_swap", {"first": ambiguous, "swapped": ambiguous_sw}, "mirror ABSTAIN", mirror_ok(ambiguous, ambiguous_sw), "SEAM_BUG")

    unknown = safe_seam(lancers(100), alpaca_target(), def_kit={"gatot": True})
    add("unknown_copy_true", unknown, "ABSTAIN", not unknown["crashed"] and unknown["result"]["winner"] == "uncertain", "SEAM_BUG")
    unknown_aurad = safe_seam(lancers(100), alpaca_target(), def_kit={"gatot": True, "gatot_state": "aurad"})
    add("unknown_copy_explicit_aurad", unknown_aurad, "ABSTAIN (state cannot supply copy identity)", not unknown_aurad["crashed"] and unknown_aurad["result"]["winner"] == "uncertain", "SEAM_BUG")
    unknown_inert = safe_seam(lancers(100), alpaca_target(), def_kit={"gatot": True, "gatot_state": "inert"})
    add("unknown_copy_explicit_inert", unknown_inert, "confident plain law (all inert copies B=0)", not unknown_inert["crashed"] and unknown_inert["result"]["winner"] != "uncertain", "SEAM_BUG")

    explicit_aurad = safe_seam(lancers(204), alpaca_target(panel=False), def_kit={"gatot": "alpaca", "gatot_state": "aurad"})
    add("known_copy_explicit_aurad_no_panel", explicit_aurad, "defender", not explicit_aurad["crashed"] and explicit_aurad["result"]["winner"] == "defender", "SEAM_BUG")
    explicit_inert = safe_seam(lancers(204), alpaca_target(), def_kit={"gatot": "alpaca", "gatot_state": "inert"})
    add("known_copy_explicit_inert_overrides_aura_panel", explicit_inert, "confident plain law; explicit state wins", not explicit_inert["crashed"] and explicit_inert["result"]["winner"] != "uncertain" and "gatot_inert_no_kit" in explicit_inert["result"]["flags"], "SEAM_BUG")

    inert = unit("Infantry", 1, 1, 2.941, 10.888, 2.22, 7.081, 194.1)
    naked = unit("Infantry", 1, 1, 6.141, 24.276, 2.15, 12.846)
    inert_call = safe_seam(inert, naked, att_kit={"gatot": "mueller"})
    plain_call = safe_seam(inert, naked)
    inert_same = (not inert_call["crashed"] and not plain_call["crashed"]
                  and inert_call["result"]["winner"] == plain_call["result"]["winner"]
                  and inert_call["result"]["att_deaths"] == plain_call["result"]["att_deaths"]
                  and inert_call["result"]["def_deaths"] == plain_call["result"]["def_deaths"])
    add("inert_gatot_exact_plain_equivalence", {"inert": inert_call, "plain": plain_call}, "identical clocks/winner; no folds", inert_same, "SEAM_BUG")

    # Hero-led count pooling and flag honesty.
    vulc3 = unit("Marksman", 6, 3, 126.445, 79.751, 41.664, 17.542)
    n3 = safe_seam(vulc3, mueller_target(), att_kit={"vulcanus": True}, def_kit={"gatot": "mueller"})
    n3_runs = not n3["crashed"] and n3["result"]["winner"] == "attacker" and "gatot_scurve" in n3["result"]["flags"]
    add("vulcanus_led_n3_runs_scurve_sqrtN", n3, "runs S-curve + sqrt(N)", n3_runs, "SEAM_BUG")
    n3_flag = (not n3["crashed"] and any("n_gt1" in flag or "unvalidated" in flag for flag in n3["result"]["flags"]))
    add("vulcanus_led_n3_unvalidated_flag", n3, "explicit n>1 unvalidated flag", n3_flag, "SEAM_BUG",
        "The S-curve flag exists, but V3 requires the n>1 extrapolation to be called out explicitly.")

    # Caps and malformed/degenerate but schema-shaped inputs.
    weak = unit("Infantry", 1, 1, 0.001, 100.0, 0.001, 100.0)
    capped = safe_seam(weak, copy.deepcopy(weak))
    add("both_clocks_over_1500_cap", capped, "capped defender at 1500", not capped["crashed"] and capped["result"].get("capped") is True and capped["result"]["winner"] == "defender" and capped["result"]["turns"] == 1500, "SEAM_BUG")
    zero_count = safe_seam(unit("Infantry", 1, 0, 1, 4, 1, 6), unit("Infantry", 1, 1, 1, 4, 1, 6))
    add("count_zero", zero_count, "clean validation error", not zero_count["crashed"] and zero_count["result"]["winner"] == "uncertain", "SEAM_BUG")
    empty_att = safe_seam([], unit("Infantry", 1, 1, 1, 4, 1, 6))
    add("empty_attacker_army", empty_att, "clean validation error", not empty_att["crashed"], "SEAM_BUG")
    empty_def = safe_seam(unit("Infantry", 1, 1, 1, 4, 1, 6), [])
    add("empty_defender_army", empty_def, "clean validation error", not empty_def["crashed"], "SEAM_BUG")
    zero_attack = safe_seam(unit("Infantry", 1, 1, 0, 4, 1, 6), unit("Infantry", 1, 1, 1, 4, 1, 6))
    add("zero_effective_attack", zero_attack, "clean validation error or capped zero-rate side", not zero_attack["crashed"], "SEAM_BUG")

    # Coherent (K,B) branch pair at the Alpaca knife edge.
    edge_results: dict[int, dict[str, Any]] = {}
    for n, expected_winner in ((204, "defender"), (205, "attacker"), (220, "attacker")):
        call = safe_seam(lancers(n), alpaca_target(), def_kit={"gatot": "alpaca"})
        edge_results[n] = call
        ok = not call["crashed"] and call["result"]["winner"] == expected_winner
        if n == 205 and ok:
            death = call["result"]["def_deaths"][-1][0]
            ok = 544 <= death <= 638
        add(f"alpaca_lancer_edge_{n}", call, expected_winner + ("; kill [544,638]" if n == 205 else ""), ok, "SEAM_BUG")

    # Side-swap invariance for plain, measured gate, and abstention paths.
    plain_a = unit("Infantry", 1, 1, 8, 10, 3, 6)
    plain_d = unit("Marksman", 1, 1, 4, 7, 2, 5)
    p1, p2 = safe_seam(plain_a, plain_d), safe_seam(plain_d, plain_a)
    add("plain_side_swap_mirror", {"first": p1, "swapped": p2}, "winner/clocks mirror", mirror_ok(p1, p2), "SEAM_BUG")
    g1 = edge_results[205]
    g2 = safe_seam(alpaca_target(), lancers(205), att_kit={"gatot": "alpaca"})
    add("gatot_205_side_swap_mirror", {"first": g1, "swapped": g2}, "winner/clocks mirror", mirror_ok(g1, g2), "SEAM_BUG")

    # Multi-stack and multi-target honesty boundaries.
    mixed = lancers(10) + unit("Marksman", 6, 10, 30.382, 18.62, 27.492, 16.03)
    mixed_call = safe_seam(mixed, alpaca_target(), def_kit={"gatot": "alpaca"})
    add("mixed_dealer_stacks_vs_aurad_gatot", mixed_call, "ABSTAIN", not mixed_call["crashed"] and mixed_call["result"]["winner"] == "uncertain", "SEAM_BUG")
    target2 = safe_seam(lancers(204), alpaca_target(count=2), def_kit={"gatot": "alpaca"})
    add("gatot_target_count_2", target2, "ABSTAIN outside measured single-target gate", not target2["crashed"] and target2["result"]["winner"] == "uncertain", "SEAM_BUG",
        "A live schema-valid count>1 Gatot target bypasses the kit gate when the seam requires target count == 1.")

    failures = [item for item in records if not item["pass"]]
    return records, {
        "probes": len(records),
        "passed": len(records) - len(failures),
        "failed": len(failures),
        "failures": [{"id": item["id"], "class": item["finding_class"], "details": item["details"]} for item in failures],
    }


def recursive_keys(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            out.add(str(key))
            out |= recursive_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            out |= recursive_keys(child)
    return out


def source_function(text: str, name: str) -> bytes:
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    lines = text.splitlines(keepends=True)
    return "".join(lines[node.lineno - 1:node.end_lineno]).encode("utf-8")


def make_profile(label: str, role: str, strength: float, joiners: list[str] | None = None) -> SideProfile:
    panel = {(cls, stat): strength for cls in ("Infantry", "Lancer", "Marksman")
             for stat in ("Attack", "Defense", "Lethality", "Health")}
    return SideProfile(label=label, role=role, troops_total=10_000,
                       formation={"Infantry": 0.5, "Lancer": 0.2, "Marksman": 0.3},
                       stats_mode="scouted", panel=panel, joiners=joiners or [])


def run_w3() -> dict[str, Any]:
    # Import-time proof: reload api while trapping stage6/formula file opens.
    opened: list[str] = []
    original_open = builtins.open

    def tracking_open(file: Any, *args: Any, **kwargs: Any):
        path = os.fspath(file) if isinstance(file, (str, os.PathLike)) else str(file)
        if "stage6" in path.casefold() or "formula_research" in path.casefold():
            opened.append(path)
        return original_open(file, *args, **kwargs)

    builtins.open = tracking_open
    try:
        importlib.reload(api)
    finally:
        builtins.open = original_open

    # Monkeypatch the deterministic seam to explode if production predict calls it.
    original_det = api.predict_deterministic_battle

    def forbidden(*args: Any, **kwargs: Any):
        raise AssertionError("production predict executed deterministic seam")

    api.predict_deterministic_battle = forbidden
    calls = []
    try:
        cases = [
            ("even", 1.0, 1.0, [], []),
            ("own_strong", 1.5, 0.8, ["Seo-yoon"], []),
            ("enemy_strong", 0.7, 1.6, [], ["Jessie"]),
            ("joiners", 1.1, 1.1, ["Jessie", "Seo-yoon"], ["Bradley"]),
        ]
        for label, own_s, enemy_s, own_j, enemy_j in cases:
            forecast = api.predict(make_profile(label + " A", "rally", own_s, own_j),
                                   make_profile(label + " D", "garrison", enemy_s, enemy_j),
                                   n=3, seed=17)
            data = dataclasses.asdict(forecast) if dataclasses.is_dataclass(forecast) else vars(forecast)
            keys = recursive_keys(data)
            calls.append({"case": label, "keys": sorted(keys),
                          "leaked_keys": sorted(keys & {"law_version", "gatot_abstain"}),
                          "output_sha256": hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()})
    finally:
        api.predict_deterministic_battle = original_det

    current_text = (ROOT / "wos_sim" / "predictor" / "api.py").read_text(encoding="utf-8")
    head = subprocess.run(["git", "show", "HEAD:wos_sim/predictor/api.py"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", check=False)
    if head.returncode == 0:
        current_predict = source_function(current_text, "predict")
        head_predict = source_function(head.stdout, "predict")
        predict_identical = current_predict == head_predict
        current_hash = hashlib.sha256(current_predict).hexdigest()
        head_hash = hashlib.sha256(head_predict).hexdigest()
    else:
        predict_identical = False
        current_hash = head_hash = None

    server_text = (ROOT / "wos_sim" / "predictor" / "server.py").read_text(encoding="utf-8")
    routes = []
    for line in server_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("@app.") and "(" in stripped:
            routes.append(stripped)
    return {
        "predict_calls": calls,
        "predict_call_count": len(calls),
        "meta_leaks": [call for call in calls if call["leaked_keys"]],
        "deterministic_seam_monkeypatch_not_called": True,
        "import_stage6_file_opens": opened,
        "predict_source_identical_to_HEAD": predict_identical,
        "predict_source_current_sha256": current_hash,
        "predict_source_head_sha256": head_hash,
        "git_show_error": head.stderr.strip() if head.returncode else "",
        "server_routes": routes,
        "server_mentions_deterministic_seam": "predict_deterministic" in server_text,
    }


def json_diffs(a: Any, b: Any, prefix: str = "") -> list[dict[str, Any]]:
    if type(a) is not type(b):
        return [{"path": prefix, "current": a, "emitted": b}]
    if isinstance(a, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in a or key not in b:
                out.append({"path": path, "current": a.get(key), "emitted": b.get(key)})
            else:
                out.extend(json_diffs(a[key], b[key], path))
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [{"path": prefix + ".length", "current": len(a), "emitted": len(b)}]
        out = []
        for index, (x, y) in enumerate(zip(a, b)):
            out.extend(json_diffs(x, y, f"{prefix}[{index}]"))
        return out
    return [] if a == b else [{"path": prefix, "current": a, "emitted": b}]


def find_prefix(prefix: str) -> dict[str, Any]:
    matches = [row for row in ROWS if row["id"].startswith(prefix)]
    if not matches:
        raise KeyError(prefix)
    return matches[0]


def run_w5() -> dict[str, Any]:
    # Execute the real emitter entry point twice, redirecting only its output
    # path so the repo remains read-only as required by the brief.
    old_path, old_argv = t6.TABLES_JSON, sys.argv[:]
    try:
        for destination in (EMIT1, EMIT2):
            t6.TABLES_JSON = str(destination)
            sys.argv = ["stage6_tables", "--emit"]
            t6.main()
    finally:
        t6.TABLES_JSON, sys.argv = old_path, old_argv

    emitted = json.loads(EMIT1.read_text(encoding="utf-8"))
    current = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    diffs = json_diffs(current, emitted)

    hero = emitted["hero_state"]
    row204 = find_prefix("MuellerAlpaca_204v1_T6LanvFC1T1Inf")
    row205 = find_prefix("MuellerAlpaca_205v1_T6LanvFC1T1Inf")
    dealer = one(row205["attacker"])
    target = one(row205["defender"])
    assert dealer and target
    al = dealer["eff"]["A"] * dealer["eff"]["L"]
    pool = target["eff"]["D"] * target["eff"]["H"]
    t205 = float((row205["outcome"].get("turns_range") or [row205["outcome"]["turns"]])[0])
    gw6 = 1.625
    bcalc = []
    branches = [
        ("edge", float(hero["K_LanInf_for_gate"]["T6"]),
         float(hero["B_by_copy_state"]["alpaca.aurad"]["branch_k_laninf_edge"])),
        ("factorized", float(hero["K_LanInf_for_gate"]["factorized_branch"]),
         float(hero["B_by_copy_state"]["alpaca.aurad"]["branch_k_laninf_factorized"])),
    ]
    for name, kval, frozen_b in branches:
        r1 = al / (kval * gw6)
        calc_b = 205 * r1 - pool / t205
        net204 = 204 * r1 - calc_b
        bcalc.append({
            "branch": name, "K": kval, "G_w": gw6, "AL": al, "pool": pool,
            "B_calculated": calc_b, "B_frozen": frozen_b,
            # K is published to two decimals in JSON, so recomputing from the
            # emitted values owes agreement within the B field's 0.1 precision.
            "matches_0p1_precision": abs(calc_b - frozen_b) <= 0.1,
            "cap_204": net204 <= pool / 1500 + 1e-9,
            "forward_205": pool / (205 * r1 - calc_b),
        })

    # Named baseline/aura panel pairs from HERO_KITS.md and the registry.
    aura_sources = {
        "mueller": ("MuellerAlpaca_1v1_T1InfvFC1T6MM_AttInfA+481.0", "attacker"),
        "alpaca": ("MuellerAlpaca_204v1_T6LanvFC1T1Inf", "defender"),
        "farseer": ("FarSeer_1v1_T1InfvT1Inf_AttInfA+188.6", "attacker"),
    }
    aura_checks = []
    for copy_name, reg in hero["registry"].items():
        base_row = BY_ID[reg["baseline_source"]["row"]]
        base_side = reg["baseline_source"]["side"]
        base_panel = one(base_row[base_side])["panel_pct"]["Attack"]
        aura_prefix, aura_side = aura_sources[copy_name]
        aura_row = find_prefix(aura_prefix)
        aura_panel = one(aura_row[aura_side])["panel_pct"]["Attack"]
        delta = aura_panel - base_panel
        exp = float(reg["expedition_inf_A_pp"])
        aura_checks.append({
            "copy": copy_name, "baseline_row": base_row["id"], "aura_row": aura_row["id"],
            "baseline_panel_A": base_panel, "aura_panel_A": aura_panel,
            "panel_delta": delta, "expedition_pp": exp,
            "difference_pp": delta - exp, "matches_0p1pp": abs(delta - exp) <= 0.1,
        })

    return {
        "current_sha256": sha256(TABLE_PATH),
        "emit1_sha256": sha256(EMIT1),
        "emit2_sha256": sha256(EMIT2),
        "two_emits_byte_identical": EMIT1.read_bytes() == EMIT2.read_bytes(),
        "current_byte_identical_to_emit": TABLE_PATH.read_bytes() == EMIT1.read_bytes(),
        "json_differences": diffs,
        "current_law_version": current.get("law_version"),
        "emitted_law_version": emitted.get("law_version"),
        "current_row_count": current.get("corpus", {}).get("row_count"),
        "emitted_row_count": emitted.get("corpus", {}).get("row_count"),
        "actual_row_count": len(ROWS),
        "b_alpaca_checks": bcalc,
        "aura_checks": aura_checks,
        "hero_state_current_equals_emitted": current.get("hero_state") == emitted.get("hero_state"),
    }


def run_w6(w1_rows: list[dict[str, Any]], w2: dict[str, Any]) -> dict[str, Any]:
    # Known caller-side fold sensitivity: compare every NanoMart W1 verdict
    # with a legal call that supplies kit tokens but omits offense multipliers.
    folded = {item["id"]: item for item in w1_rows}
    changed = []
    confident_wrong_without_folds = []
    for row in ROWS:
        if not scoreable(row) or row["folder"] != "NanoMart":
            continue
        result = api.predict_deterministic_battle(
            army_from(row["attacker"]), army_from(row["defender"]),
            att_kit=kit_from(row["attacker"]), def_kit=kit_from(row["defender"]),
        )
        cls, gap, t_att, t_def = seam_class(row, result)
        folded_cls = folded[row["id"]]["classification"]
        if cls != folded_cls:
            item = {"id": row["id"], "without_folds": cls, "with_folds": folded_cls,
                    "winner_without_folds": result.get("winner"), "gap_without_folds": gap,
                    "t_att": t_att, "t_def": t_def}
            changed.append(item)
        if cls == "WRONG":
            confident_wrong_without_folds.append(row["id"])

    w1_new_wrong = [item["id"] for item in w1_rows
                    if item["classification"] == "WRONG" and item["id"] not in {
                        "LabRat_1v1_T1LanvT1MM_NoAttackerHero_Gordonlvl1_20260711_213859",
                        "NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus",
                        "MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+194.1D+172.2L+122.0H+118.7_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_151127",
                    }]
    fully_measured_abstentions = [item["id"] for item in w1_rows if item["classification"] == "ABSTAIN"
                                  and "121104" not in item["id"]]

    # Legal adversarial input: the public kit contract says Vulcanus is a bool,
    # but outside the Gatot gate the seam does not apply S1/S2/S3 by itself.
    # Tune no constants: choose a plain 11% attacker offense edge, then apply
    # the documented defender-Vulcanus folds independently. Both races have a
    # >10% gap, but the winner reverses.
    adv_att = unit("Infantry", 1, 1, 1.11, 4.0, 1.0, 6.0)
    adv_def = unit("Infantry", 1, 1, 1.00, 4.0, 1.0, 6.0)
    adv_seam = api.predict_deterministic_battle(
        copy.deepcopy(adv_att), copy.deepcopy(adv_def), def_kit={"vulcanus": True})
    adv_physics = api.predict_deterministic_battle(
        copy.deepcopy(adv_att), copy.deepcopy(adv_def),
        att_offense_mult=0.96,
        def_offense_mult=(31.0 / 30.0) / 0.88,
        def_kit={"vulcanus": True})
    def adv_summary(result: dict[str, Any]) -> dict[str, Any]:
        ta, td = result["att_deaths"][-1][0], result["def_deaths"][-1][0]
        return {"winner": result["winner"], "t_att": ta, "t_def": td,
                "gap_pct": abs(ta - td) / min(ta, td) * 100.0,
                "flags": result.get("flags")}
    adversarial_reversal = {
        "input": {"attacker_AL": 1.11, "defender_AL": 1.0,
                  "def_kit": {"vulcanus": True}},
        "seam_kit_only": adv_summary(adv_seam),
        "independent_documented_folds": {
            **adv_summary(adv_physics),
            "att_offense_mult": 0.96,
            "def_offense_mult": (31.0 / 30.0) / 0.88,
        },
    }
    adversarial_reversal["confident_winner_reversal"] = (
        adversarial_reversal["seam_kit_only"]["winner"]
        != adversarial_reversal["independent_documented_folds"]["winner"]
        and adversarial_reversal["seam_kit_only"]["gap_pct"] > 10.0
        and adversarial_reversal["independent_documented_folds"]["gap_pct"] > 10.0)
    return {
        "nano_verdict_changes_without_caller_folds": changed,
        "confident_wrong_without_caller_folds": confident_wrong_without_folds,
        "new_w1_wrong_beyond_known_three": w1_new_wrong,
        "unexpected_w1_abstentions_beyond_E3a": fully_measured_abstentions,
        "target_count_2_probe_failed_honesty": any(f["id"] == "gatot_target_count_2" for f in w2["failures"]),
        "adversarial_vulcanus_kit_only_reversal": adversarial_reversal,
        "verdict": ("WIRING_FINDING" if adversarial_reversal["confident_winner_reversal"]
                    or w1_new_wrong or fully_measured_abstentions
                    else "NO_NEW_FULLY_MEASURED_COUNTEREXAMPLE"),
    }


def write_csv(rows: list[dict[str, Any]]) -> None:
    fields = [
        "record_type", "section", "id", "folder", "observed_winner", "seam_winner",
        "classification", "clock_gap_pct", "att_dead_clock", "def_dead_clock",
        "expected", "pass", "finding_class", "flags", "gatot_abstain", "law_version",
        "input_mutated", "arithmetic", "details",
    ]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            for key in ("flags", "gatot_abstain", "arithmetic"):
                rendered[key] = json.dumps(rendered.get(key), ensure_ascii=False, sort_keys=True, default=str)
            writer.writerow(rendered)


def main() -> None:
    w1_rows, w1 = run_w1()
    w2_rows, w2 = run_w2()
    w3 = run_w3()
    w5 = run_w5()
    w6 = run_w6(w1_rows, w2)
    write_csv(w1_rows + w2_rows)
    core = {
        "corpus": {"declared": CORPUS.get("row_count"), "actual": len(ROWS),
                   "path": str(CORPUS_PATH)},
        "W1": w1,
        "W2": w2,
        "W3": w3,
        "W5": w5,
        "W6": w6,
        "artifacts": {"qa3_results_sha256": sha256(CSV_PATH)},
    }
    CORE_PATH.write_text(json.dumps(core, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "W1": {"counts": w1["counts"], "scorecard_match": w1["scorecard_match"]},
        "W2": {"probes": w2["probes"], "failed": w2["failed"]},
        "W3": {"meta_leaks": len(w3["meta_leaks"]), "predict_identical": w3["predict_source_identical_to_HEAD"],
               "stage6_import_opens": len(w3["import_stage6_file_opens"])},
        "W5": {"emits_stable": w5["two_emits_byte_identical"],
               "current_matches_emit": w5["current_byte_identical_to_emit"],
               "row_counts": [w5["current_row_count"], w5["emitted_row_count"], w5["actual_row_count"]]},
        "W6": w6["verdict"],
    }, indent=2))


if __name__ == "__main__":
    main()
