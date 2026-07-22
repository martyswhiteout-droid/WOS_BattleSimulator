"""One-shot V3 final cross-check runner. Do not execute more than once."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def main() -> None:
    log_path = OUT / "stage6_validate_once.log"
    marker = OUT / "stage6_validate_once.json"
    if marker.exists() or log_path.exists():
        raise RuntimeError("stage6_validate has already been run for this V3 audit")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.time()
    proc = subprocess.run(
        [str(PYTHON), "-m", "wos_sim.formula_research.stage6_validate"],
        cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    text = proc.stdout + ("\n--- STDERR ---\n" + proc.stderr if proc.stderr else "")
    log_path.write_text(text, encoding="utf-8")
    summary = {
        "command": [str(PYTHON), "-m", "wos_sim.formula_research.stage6_validate"],
        "exit_code": proc.returncode,
        "elapsed_seconds": time.time() - started,
        "stdout_sha256": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(),
        "log": str(log_path),
    }
    marker.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
