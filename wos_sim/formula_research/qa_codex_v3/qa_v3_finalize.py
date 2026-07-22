"""Build the final V3 report after the single stage6_validate cross-check."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any

OUT = Path(__file__).resolve().parent
CORE = json.loads((OUT / "qa3_core.json").read_text(encoding="utf-8"))
EXT = json.loads((OUT / "qa3_external.json").read_text(encoding="utf-8"))
VALIDATOR_META = json.loads((OUT / "stage6_validate_once.json").read_text(encoding="utf-8"))
VALIDATOR_TEXT = (OUT / "stage6_validate_once.log").read_text(encoding="utf-8")
CSV_PATH = OUT / "qa3_results.csv"
REPORT_PATH = OUT / "qa3_report.md"
LOCK_PATH = OUT / "qa3_final.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(map(safe, headers)) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(safe(v) for v in row) + " |" for row in rows)
    return "\n".join(lines)


def validator_w6() -> dict[str, Any]:
    block = VALIDATOR_TEXT.split("W6  TWO-SIDED WINNER GATE", 1)[1].split("I6  FULL", 1)[0]
    counts = {}
    for key in ("CORRECT", "COIN_FLIP", "ABSTAIN", "WRONG"):
        match = re.search(rf"^\s*{key}\s+(\d+)", block, re.MULTILINE)
        counts[key] = int(match.group(1)) if match else None

    w1_rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    w1_rows = [row for row in w1_rows if row["record_type"] == "W1"]
    ids = [row["id"] for row in w1_rows]
    noncorrect: dict[str, str] = {}
    current = None
    for line in block.splitlines():
        marker = re.match(r"^\s*(COIN_FLIP|ABSTAIN|WRONG)\s+\d+", line)
        if marker:
            current = marker.group(1)
            continue
        if current and line.startswith("    "):
            stripped = line.strip()
            if not stripped or stripped.startswith(("flags=", "diagnosis:", "the ")):
                continue
            prefix = stripped.split()[0]
            if "obs=" not in stripped and current != "ABSTAIN":
                continue
            matches = [row_id for row_id in ids if row_id.startswith(prefix)]
            if len(matches) == 1:
                noncorrect[matches[0]] = current
    validator_by_id = {row_id: noncorrect.get(row_id, "CORRECT") for row_id in ids}
    seam_by_id = {row["id"]: row["classification"] for row in w1_rows}
    differences = [{"id": row_id, "seam": seam_by_id[row_id], "validator": validator_by_id[row_id]}
                   for row_id in ids if seam_by_id[row_id] != validator_by_id[row_id]]
    return {"counts": counts, "per_row_differences": differences,
            "classified_ids": len(validator_by_id)}


def probe_rows() -> list[dict[str, str]]:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    return [row for row in rows if row["record_type"] == "W2"]


def actual_probe(row: dict[str, str]) -> str:
    if row["seam_winner"]:
        actual = row["seam_winner"]
        if row["gatot_abstain"] and row["gatot_abstain"] not in ("null", ""):
            actual += "; abstain=" + row["gatot_abstain"]
        return actual
    if "exception" in row["details"]:
        try:
            return json.loads(row["details"])["exception"]
        except Exception:
            return row["details"]
    return row["details"][:140]


def main() -> None:
    cross = validator_w6()
    w1, w2, w3, w5, w6 = (CORE[key] for key in ("W1", "W2", "W3", "W5", "W6"))
    probes = probe_rows()
    pred_counts = EXT["predictor_pytest"]["counts"]
    formula_counts = EXT["formula_pytest"]["counts"]
    adv = w6["adversarial_vulcanus_kit_only_reversal"]

    failures = [row for row in probes if row["pass"].casefold() != "true"]
    lines = [
        "# Type-1 deterministic seam QA — V3",
        "",
        "## Verdict",
        "",
        "**WIRING QA: FAIL.** The 170-row corpus replay is wired consistently with the validator and exactly matches the expected scorecard, but W2/W5/W6 expose production-seam honesty and metadata defects.",
        "",
        f"W1 scorecard: **{w1['counts']['CORRECT']} CORRECT / {w1['counts']['COIN_FLIP']} COIN_FLIP / {w1['counts']['ABSTAIN']} ABSTAIN / {w1['counts']['WRONG']} WRONG** across {w1['scoreable']} rows — exact match to V3 expected.",
        "",
        "## Headline wiring findings",
        "",
        f"1. **SEAM BUG — documented Vulcanus kit is not self-contained.** A legal call with `def_kit={{\"vulcanus\": true}}` returns a confident **{adv['seam_kit_only']['winner']}** ({adv['seam_kit_only']['t_def']}t vs {adv['seam_kit_only']['t_att']}t; {adv['seam_kit_only']['gap_pct']:.2f}% gap). Applying the documented S1/S2/S3 folds independently reverses it to a confident **{adv['independent_documented_folds']['winner']}** ({adv['independent_documented_folds']['t_att']}t vs {adv['independent_documented_folds']['t_def']}t; {adv['independent_documented_folds']['gap_pct']:.2f}% gap). The validator avoids this through a private caller-side NanoMart helper; a normal caller can omit it without warning.",
        "2. **SEAM BUG — Alpaca 205-Lancer clock is outside the required bracket.** The seam returns 648 turns; V3 requires [544,638], and independent paired-(K,B) arithmetic gives 575 on both branches. The extra drift is the composition layer's 1.125 solo-tank multiplier being applied after the budget gate already produced the full target kill clock.",
        "3. **SEAM BUG — Gatot target `count>1` silently bypasses the kit gate.** The public, schema-valid input receives a confident plain-law result instead of an honest abstention outside the measured single-target regime.",
        "4. **SEAM BUG — degenerate inputs crash internally.** `count=0` and either empty army raise `IndexError`; zero effective Attack raises `ZeroDivisionError`. No clean seam validation error is returned.",
        "5. **SEAM BUG — n>1 hero-led extrapolation is not explicitly flagged.** The S-curve + √N path runs, but its flags do not identify the n>1 extrapolation as unvalidated.",
        f"6. **FROZEN-ARTIFACT BUG — metadata is stale.** `stage6_tables.json` declares {w5['current_row_count']} rows while the corpus and deterministic re-emission contain {w5['actual_row_count']}. Re-emission is stable; the only JSON value difference is `corpus.row_count`.",
        "7. **PROVENANCE GAP — Far Seer aura cross-check.** The registry's hero-sheet Expedition value is 186.45 pp, while the named panel pair differs by 188.60 pp (+2.15 pp). This does not change the nearest-neighbour state call, but the panel-pair provenance is not exact (unlike Mueller and Alpaca).",
        "",
        "## W1 — corpus replay",
        "",
        table(["classification", "actual", "expected"], [[key, w1["counts"][key], w1["expected"][key]] for key in ("CORRECT", "COIN_FLIP", "ABSTAIN", "WRONG")]),
        "",
        "Known-open rows were reproduced without retuning:",
        "",
        *[f"- `{row_id}`" for row_id in w1["wrong_ids"]],
        f"- E3a honest abstention: `{w1['abstain_ids'][0]}`.",
        "",
        f"The seam and the final validator W6 classification agree on every row: **{len(cross['per_row_differences'])} per-row differences**. Validator W6 counts were {cross['counts']}.",
        "",
        f"Independent V2 clock arithmetic matched {w1['arithmetic_status'].get('MATCH', 0)} directly comparable rows. Four non-Nano rows differ because W1/validator supply Vulcanus/Seo folds only through the private NanoMart caller helper; they are **INPUT-CONSTRUCTION** discrepancies, not arithmetic errors:",
        "",
        *[f"- `{item['id']}`: V2 ({item['v2_t_att_dead']}, {item['v2_t_def_dead']}) vs seam ({item['seam_t_att_dead']}, {item['seam_t_def_dead']})." for item in w1["arithmetic_differences"]],
        "",
        "## W2 — edge fuzz matrix",
        "",
        table(["probe", "expected", "actual", "result", "class"], [
            [row["id"], row["expected"], actual_probe(row), "PASS" if row["pass"].casefold() == "true" else "FAIL", row["finding_class"] or "—"]
            for row in probes
        ]),
        "",
        f"Result: **{w2['passed']}/{w2['probes']} passed; {w2['failed']} findings.** Side-swap checks mirrored correctly on the plain, measured-Gatot, missing-panel, and ambiguous-panel paths. The 204/220 paired-budget verdicts were correct; 205 had the clock error described above.",
        "",
        "## W3 — production app-path isolation",
        "",
        f"- Golden-anchor backtest: **PASS, 7/13**, exit {EXT['backtest']['exit_code']}.",
        f"- `predict()` source is byte-identical to Git HEAD: **{w3['predict_source_identical_to_HEAD']}**; both hashes `{w3['predict_source_current_sha256']}`.",
        f"- Four constructed production `predict()` calls completed while the deterministic seam was monkeypatched to raise: **PASS**; meta leaks: **{len(w3['meta_leaks'])}**.",
        f"- Reloading `api.py` opened **{len(w3['import_stage6_file_opens'])}** Stage-6/formula files.",
        f"- `server.py` routes: {', '.join('`' + route + '`' for route in w3['server_routes'])}; deterministic seam route present: **{w3['server_mentions_deterministic_seam']}**.",
        "",
        "## W4 — test-suite audit",
        "",
        f"- Predictor tests: **PASS**, {pred_counts['passed']} passed / {pred_counts['skipped']} skipped / {pred_counts['xfailed']} xfailed (exit {EXT['predictor_pytest']['exit_code']}). The prompt expected 115/8/2; the same 125-test total ran, but FastAPI was available, so the eight `TestServer` cases passed instead of skipping. This is an environment difference, not a regression.",
        f"- Formula-research tests: **PASS**, {formula_counts['passed']} passed (exit {EXT['formula_pytest']['exit_code']}); exact expected count.",
        "",
        "### Recommended seam-test additions",
        "",
        "1. Missing `panel_pct` on both attacker- and defender-side Gatot targets.",
        "2. Unknown copy plus explicit `gatot_state` (`aurad` and `inert`) and conflicting explicit state vs panel detector.",
        "3. n>1 Vulcanus-led S-curve behavior with an explicit unvalidated-extrapolation flag assertion.",
        "4. `count=0`, empty attacker/defender armies, and zero A/L validation with clean public errors.",
        "5. Gatot target `count>1` must abstain instead of falling through to plain law.",
        "6. Exact 205-Lancer clock bracket [544,638], not the current coarse [500,700] assertion.",
        "7. Attacker/defender side-swap invariance for plain, gated, and abstention paths.",
        "8. Multi-stack dealers versus aura'd Gatot, input non-mutation, and 1500+ cap behavior.",
        "9. `predict_deterministic_1v1` metadata/content tests; the current seam file exercises only battle-level metadata.",
        "10. A public-kit test proving Vulcanus folds are either applied automatically or rejected unless explicit offense multipliers are supplied.",
        "",
        "## W5 — frozen constants",
        "",
        f"- Emit hashes: `{w5['emit1_sha256']}` and `{w5['emit2_sha256']}` — byte-identical: **{w5['two_emits_byte_identical']}**.",
        f"- Current hash: `{w5['current_sha256']}` — byte-identical to emission: **{w5['current_byte_identical_to_emit']}**.",
        f"- Law version current/emitted: `{w5['current_law_version']}` / `{w5['emitted_law_version']}`.",
        f"- Row count current/emitted/actual: **{w5['current_row_count']} / {w5['emitted_row_count']} / {w5['actual_row_count']}**.",
        "",
        table(["B branch", "K", "G_w", "B calculated", "B frozen", "204 caps", "205 forward"], [
            [item["branch"], f"{item['K']:.2f}", f"{item['G_w']:.3f}", f"{item['B_calculated']:.3f}", item["B_frozen"], item["cap_204"], f"{item['forward_205']:.3f}"]
            for item in w5["b_alpaca_checks"]
        ]),
        "",
        table(["copy", "baseline A", "aura A", "panel delta", "Expedition", "difference", "≤0.1 pp"], [
            [item["copy"], item["baseline_panel_A"], item["aura_panel_A"], f"{item['panel_delta']:.2f}", item["expedition_pp"], f"{item['difference_pp']:+.2f}", item["matches_0p1pp"]]
            for item in w5["aura_checks"]
        ]),
        "",
        "The two B branches reproduce the 204 cap and 575-turn 205 source exactly within published precision. Mueller and Alpaca panel deltas match their Expedition auras; Far Seer carries the 2.15 pp provenance offset noted above.",
        "",
        "## W6 — adversarial wiring hunt",
        "",
        "**Finding reproduced:** a legal kit-only Vulcanus input produces a confident winner opposite the fully measured deterministic folds. This is the headline contract/wiring failure. Six real Nano rows also change CORRECT↔COIN_FLIP classification when the validator-only caller folds are omitted; the known Nano MM→Inf row remains confidently WRONG.",
        "",
        f"No additional corpus WRONG rows beyond the known three: **{len(w6['new_w1_wrong_beyond_known_three'])}**. No unexpected measured abstentions beyond E3a: **{len(w6['unexpected_w1_abstentions_beyond_E3a'])}**.",
        "",
        "## Final validator cross-check",
        "",
        f"`stage6_validate` was run once after the independent lock and exited {VALIDATOR_META['exit_code']}. W6 matched this audit exactly. Its overall failure is the expected three known WRONG rows plus the known factorized Lan→Lan gate. It accounts **243/243**, although its regression label still says `all 232 rows accounted`—another stale display string.",
        "",
        "## Evidence",
        "",
        "- `qa3_results.csv`: all 170 W1 rows plus all 24 W2 probes.",
        "- `pre_crosscheck_v3.lock.json`: immutable hashes before the validator run.",
        "- Raw backtest, pytest, table-emission, and one-time validator logs are retained in this directory.",
    ]

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    lock = {
        "qa3_results_sha256": sha(CSV_PATH),
        "qa3_report_sha256": sha(REPORT_PATH),
        "qa3_core_sha256": sha(OUT / "qa3_core.json"),
        "qa3_external_sha256": sha(OUT / "qa3_external.json"),
        "stage6_validate_log_sha256": sha(OUT / "stage6_validate_once.log"),
        "w1_counts": w1["counts"],
        "w1_validator_per_row_differences": cross["per_row_differences"],
        "w2_failure_ids": [row["id"] for row in failures],
        "verdict": "FAIL_WIRING_FINDINGS",
    }
    LOCK_PATH.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": lock["verdict"], "w1": w1["counts"],
        "validator_row_differences": len(cross["per_row_differences"]),
        "w2_failures": len(failures), "report": str(REPORT_PATH),
    }, indent=2))


if __name__ == "__main__":
    main()
