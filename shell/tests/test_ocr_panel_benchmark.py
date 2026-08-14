"""Real-image OCR benchmark (Task 12 / Phase-0 gate D2).

Run explicitly with::

    py -m pytest -m benchmark shell/tests/test_ocr_panel_benchmark.py -q -s

The module defines no tests during the default suite, so real OCR engines and
their model startup cost stay outside ``py -m pytest shell/tests -q``.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


def _benchmark_selected() -> bool:
    if os.environ.get("OCR_PANEL_BENCHMARK") == "1":
        return True
    for index, arg in enumerate(sys.argv[:-1]):
        if arg == "-m" and "benchmark" in sys.argv[index + 1]:
            return "not benchmark" not in sys.argv[index + 1]
    return any(arg.startswith("-mbenchmark") for arg in sys.argv)


if _benchmark_selected():
    from shell.app.ocr.panel.engine_gemini import GeminiUnavailable, extract_panel_gemini
    from shell.app.ocr.panel.engine_rapidocr import recognize_image
    from shell.app.ocr.panel.service import extract_panel

    ROOT = Path(__file__).resolve().parents[2]
    IMAGE_DIR = Path(__file__).parent / "fixtures" / "panel_ocr" / "images"
    FIXTURE_PATH = IMAGE_DIR.parent / "golden_vectors.json"
    FIX = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"), parse_float=Decimal)
    TESSERACT_ENGINE = ROOT / "shell" / "app" / "ocr" / "client" / "engine_tesseract.mjs"
    STATS = ("Attack", "Defense", "Lethality", "Health")


    @dataclass(frozen=True)
    class ImageCase:
        name: str
        account: str
        kind: str
        expected_keys: tuple[str, ...] = ()


    C_CITY_1 = (
        "Troops|Attack", "Troops|Defense", "Troops|Lethality", "Troops|Health",
        "Infantry|Attack", "Infantry|Defense", "Infantry|Health",
    )
    C_CITY_2 = (
        "Infantry|Lethality",
        "Lancer|Attack", "Lancer|Defense", "Lancer|Lethality", "Lancer|Health",
        "Marksman|Attack", "Marksman|Defense", "Marksman|Lethality", "Marksman|Health",
    )


    def _flatten(matrix):
        return {
            f"{cls}|{stat}": value
            for cls, stats in matrix.items()
            for stat, value in stats.items()
        }


    def _account_maps(account):
        acct = FIX["accounts"][account]
        city = {f"Troops|{stat}": value for stat, value in acct["bo_troops"].items()}
        city.update(_flatten(acct["bo_class"]))
        return {
            "citystats": city,
            "scout": _flatten(acct["scout"]),
            "battle_left": _flatten(acct["battle_left"]),
            "battle_right": _flatten(acct["battle_right"]),
        }


    def _discover_cases():
        cases = [
            ImageCase("C_citystats_1.png", "C", "citystats", C_CITY_1),
            ImageCase("C_citystats_2.png", "C", "citystats", C_CITY_2),
            ImageCase("C_scout.png", "C", "scout",
                      tuple(_account_maps("C")["scout"])),
            ImageCase("C_battle_3.png", "C", "battle",
                      tuple(_account_maps("C")["battle_left"])
                      + tuple(_account_maps("C")["battle_right"])),
            ImageCase("C_battle_4.png", "C", "specials"),
        ]
        present = {path.name for path in IMAGE_DIR.glob("*.png")}
        cases = [case for case in cases if case.name in present]
        for account in ("A", "B"):
            maps = _account_maps(account)
            for path in sorted(IMAGE_DIR.glob(f"{account}_*.png")):
                lower = path.stem.lower()
                if "citystats" in lower:
                    cases.append(ImageCase(path.name, account, "citystats", tuple(maps["citystats"])))
                elif "scout" in lower:
                    cases.append(ImageCase(path.name, account, "scout", tuple(maps["scout"])))
                elif "battle" in lower:
                    cases.append(ImageCase(
                        path.name, account, "battle",
                        tuple(maps["battle_left"]) + tuple(maps["battle_right"])))
                elif "special" in lower:
                    cases.append(ImageCase(path.name, account, "specials"))
        return cases


    CASES = _discover_cases()


    def _decimal_places(value: Decimal) -> int:
        return max(0, -value.as_tuple().exponent)


    def _digits(value, template: Decimal) -> str:
        observed = Decimal(str(value))
        places = _decimal_places(template)
        rendered = f"{observed:.{places}f}"
        return "".join(character for character in rendered if character.isdigit())


    def _edit_distance(left: str, right: str) -> int:
        previous = list(range(len(right) + 1))
        for index, left_char in enumerate(left, 1):
            current = [index]
            for column, right_char in enumerate(right, 1):
                current.append(min(
                    previous[column] + 1,
                    current[column - 1] + 1,
                    previous[column - 1] + (left_char != right_char),
                ))
            previous = current
        return previous[-1]


    def _digit_score(expected: Decimal, observed):
        expected_digits = _digits(expected, expected)
        if observed is None:
            return 0, len(expected_digits)
        observed_digits = _digits(observed, expected)
        correct = max(0, len(expected_digits) - _edit_distance(expected_digits, observed_digits))
        return correct, len(expected_digits)


    def _validate_tokens(tokens, *, battle):
        assert isinstance(tokens, list)
        for token in tokens:
            assert set(token) >= {"text", "x0", "y0", "x1", "y1", "conf", "color"}
            assert 0.0 <= token["x0"] < token["x1"] <= 1.0
            assert 0.0 <= token["y0"] < token["y1"] <= 1.0
            assert 0.0 <= token["conf"] <= 1.0
            assert token["color"] in (None, "green", "red")
        if battle:
            assert any(token["color"] in ("green", "red") for token in tokens)


    def _special_expected(account):
        acct = FIX["accounts"][account]
        values = [(item["label"], item["value"]) for item in acct["specials_own"]]
        values.extend((item["label"], item["value"]) for item in acct["specials_enemy"])
        if account == "C":
            label = acct["specials_own"][0]["label"]
            values.append((label, Decimal("0.0")))
        return values


    def _evaluate(case, tokens):
        result = extract_panel([tokens], side_hint="you", panel_hint=None)
        return _score(case, result)


    def _score(case, result):
        """Score an already-produced ``extract_panel``-shaped result against
        the golden vectors. Split out from ``_evaluate`` so the Gemini engine
        — which returns this same shape directly, with no token layer — can
        share the exact scoring logic (digit accuracy, false-confident) used
        for the token-based engines."""
        maps = _account_maps(case.account)
        correct_digits = total_digits = false_confident = fields_read = 0
        if case.kind == "specials":
            expected = _special_expected(case.account)
            observed = [(item["label"], item["value"]) for item in result["specials"]]
            remaining = list(observed)
            fields_read = len(observed)
            for label, value in expected:
                match = next((item for item in remaining
                              if item[0] == label and item[1] == float(value)), None)
                if match is not None:
                    remaining.remove(match)
                    score = _digit_score(value, match[1])
                else:
                    wrong = next((item for item in remaining if item[0] == label), None)
                    if wrong is not None:
                        remaining.remove(wrong)
                        false_confident += 1
                        score = _digit_score(value, wrong[1])
                    else:
                        score = _digit_score(value, None)
                correct_digits += score[0]
                total_digits += score[1]
            false_confident += len(remaining)
        else:
            if case.kind == "battle":
                observed = {}
                observed.update({f"left:{key}": value for key, value in result.get("stats_left", {}).items()})
                observed.update({f"right:{key}": value for key, value in result.get("stats_right", {}).items()})
                expected_all = {}
                expected_all.update({f"left:{key}": value for key, value in maps["battle_left"].items()})
                expected_all.update({f"right:{key}": value for key, value in maps["battle_right"].items()})
                expected_keys = tuple(expected_all)
            else:
                observed = result.get("stats", {})
                expected_all = maps[case.kind]
                expected_keys = case.expected_keys
            fields_read = len(observed)
            for key in expected_keys:
                value = expected_all[key]
                emitted = observed.get(key)
                score = _digit_score(value, emitted)
                correct_digits += score[0]
                total_digits += score[1]
            false_confident += sum(
                1 for key, value in observed.items()
                if key not in expected_all or value != float(expected_all[key])
            )
        return {
            "image": case.name,
            "fields_read": fields_read,
            "expected_fields": (len(_special_expected(case.account))
                                if case.kind == "specials" else len(case.expected_keys)),
            "correct_digits": correct_digits,
            "total_digits": total_digits,
            "digit_accuracy": correct_digits / total_digits if total_digits else 0.0,
            "false_confident": false_confident,
            "panel_type": result["panel_type"],
            "status": result["status"],
        }


    def _rapidocr_results():
        results = []
        for case in CASES:
            raw = (IMAGE_DIR / case.name).read_bytes()
            started = time.perf_counter()
            tokens = recognize_image(raw)
            latency_ms = (time.perf_counter() - started) * 1000.0
            _validate_tokens(tokens, battle=case.kind in ("battle", "specials"))
            row = _evaluate(case, tokens)
            row["latency_ms"] = latency_ms
            results.append(row)
        return results


    def _tesseract_results():
        script = r"""
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const engine = await import(pathToFileURL(process.argv[1]).href);
const output = [];
for (const path of process.argv.slice(2)) {
  const bytes = await readFile(path);
  const started = performance.now();
  const tokens = await engine.recognizeImage(bytes);
  output.push({ path, latency_ms: performance.now() - started, tokens });
}
await engine.terminateEngine();
process.stdout.write(JSON.stringify(output));
"""
        paths = [str(IMAGE_DIR / case.name) for case in CASES]
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(TESSERACT_ENGINE), *paths],
            cwd=ROOT, capture_output=True, text=True, timeout=600, check=False,
        )
        assert completed.returncode == 0, completed.stderr
        payload = json.loads(completed.stdout)
        results = []
        for case, item in zip(CASES, payload, strict=True):
            tokens = item["tokens"]
            _validate_tokens(tokens, battle=case.kind in ("battle", "specials"))
            row = _evaluate(case, tokens)
            row["latency_ms"] = item["latency_ms"]
            results.append(row)
        return results


    def _gemini_results():
        """Run the Gemini engine over the same CASES used by the token-based
        engines. Unlike those, extract_panel_gemini returns the final result
        shape directly (binding decision #1: a vision LLM's native strength
        is structured extraction, not per-token bounding boxes) — so there is
        no _validate_tokens() step here, and _score() is called directly.

        Raises GeminiUnavailable (propagated to the caller) if no
        GEMINI_API_KEY is configured — the caller is expected to catch this
        and report Gemini as skipped rather than failing the whole benchmark.
        """
        results = []
        models_used = set()
        for case in CASES:
            raw = (IMAGE_DIR / case.name).read_bytes()
            started = time.perf_counter()
            result = extract_panel_gemini(raw, panel_hint=None, side_hint="you")
            latency_ms = (time.perf_counter() - started) * 1000.0
            models_used.add(result.get("engine_model"))
            row = _score(case, result)
            row["latency_ms"] = latency_ms
            results.append(row)
        return results, models_used


    def _summary(engine, rows):
        correct = sum(row["correct_digits"] for row in rows)
        total = sum(row["total_digits"] for row in rows)
        false_confident = sum(row["false_confident"] for row in rows)
        accuracy = correct / total if total else 0.0
        return {
            "engine": engine,
            "digit_accuracy": accuracy,
            "false_confident": false_confident,
            "passed": accuracy >= 0.99 and false_confident == 0,
            "images": rows,
        }


    @pytest.mark.benchmark
    def test_real_engine_adapters_clear_phase0_bar():
        assert CASES, "the real-image gate is closed: no benchmark PNGs found"
        reports = [
            _summary("rapidocr", _rapidocr_results()),
            _summary("tesseract", _tesseract_results()),
        ]
        try:
            gemini_rows, gemini_models = _gemini_results()
        except GeminiUnavailable as exc:
            # No GEMINI_API_KEY configured: Gemini is skipped, never a hard
            # failure — the D2 verdict below must still stand on RapidOCR
            # alone regardless of Gemini's presence (binding decision #6).
            reports.append({"engine": "gemini", "passed": False, "skipped": True,
                             "reason": str(exc)})
        else:
            gemini_report = _summary("gemini", gemini_rows)
            gemini_report["model"] = sorted(model for model in gemini_models if model)
            reports.append(gemini_report)
        print("OCR_BENCHMARK_JSON=" + json.dumps(reports, sort_keys=True))
        assert any(report.get("passed") for report in reports), reports
