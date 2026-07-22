"""Run V3's required production backtest and pytest suites, logging in V3 only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
PYTEST_PYTHON = Path(r"C:\Users\Martin\OneDrive\Documents\New project\.venv\Scripts\python.exe")


def run(name: str, args: list[str], python: Path = PYTHON) -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # pytest is not installed in the project runtime. Use an existing
    # same-version (3.11.15) pytest interpreter while exposing the project's
    # own runtime dependencies; this installs and edits nothing.
    env["PYTHONPATH"] = os.pathsep.join([
        str(ROOT), str(ROOT / ".venv" / "Lib" / "site-packages"),
        env.get("PYTHONPATH", ""),
    ])
    started = time.time()
    proc = subprocess.run(
        [str(python), *args], cwd=ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    elapsed = time.time() - started
    text = proc.stdout + ("\n--- STDERR ---\n" + proc.stderr if proc.stderr else "")
    (OUT / f"{name}.log").write_text(text, encoding="utf-8")
    return {
        "command": [str(python), *args],
        "exit_code": proc.returncode,
        "elapsed_seconds": elapsed,
        "last_lines": text.splitlines()[-12:],
        "log": str(OUT / f"{name}.log"),
    }


def pytest_counts(lines: list[str]) -> dict:
    text = "\n".join(lines)
    out = {}
    for label in ("passed", "skipped", "xfailed", "failed", "errors"):
        matches = re.findall(rf"(\d+)\s+{label}\b", text)
        out[label] = int(matches[-1]) if matches else 0
    return out


def main() -> None:
    previous_path = OUT / "qa3_external.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    backtest = previous.get("backtest")
    if not backtest or backtest.get("exit_code") != 0:
        backtest = run("w3_backtest", ["-m", "wos_sim.backtest"])
    predictor = run("w4_predictor_pytest", [
        "-m", "pytest", "wos_sim/predictor/tests/", "-q", "-p", "no:cacheprovider",
    ], python=PYTEST_PYTHON)
    formula = run("w4_formula_pytest", [
        "-m", "pytest", "wos_sim/formula_research/", "-q", "-p", "no:cacheprovider",
    ], python=PYTEST_PYTHON)
    predictor["counts"] = pytest_counts(predictor["last_lines"])
    formula["counts"] = pytest_counts(formula["last_lines"])
    summary = {"backtest": backtest, "predictor_pytest": predictor, "formula_pytest": formula}
    (OUT / "qa3_external.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "backtest": {"exit": backtest["exit_code"], "tail": backtest["last_lines"][-3:]},
        "predictor": {"exit": predictor["exit_code"], "counts": predictor["counts"]},
        "formula": {"exit": formula["exit_code"], "counts": formula["counts"]},
    }, indent=2))


if __name__ == "__main__":
    main()
