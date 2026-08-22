"""Tests for shell/Dockerfile's COPY set (Agent A) — keyless, no docker
daemon required.

F1 (EVAL_ROUND_1.md): shell/Dockerfile's COPY set omitted
.claude/skills/wos-battlereport-ingestion/, which shell/app/ocr/extract.py
and vision.py require at runtime (the validator, hit on every OCR request
including the mock path, and the v2 schema embed, hit on every real-key
request) — every OCR upload 500s with FileNotFoundError in the deployed
image. This parses the Dockerfile's declared COPY sources and cross-checks
them against the REAL paths the OCR module resolves at import time, so it
stays correct even if the skill's on-disk location ever changes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _dockerfile_copy_sources() -> list[str]:
    text = (_REPO_ROOT / "shell" / "Dockerfile").read_text(encoding="utf-8")
    sources = []
    for line in text.splitlines():
        m = re.match(r"\s*COPY\s+(\S+)\s+\S+", line)
        if m:
            sources.append(m.group(1))
    return sources


def _covered(rel_path: str, sources: list[str]) -> bool:
    rel = rel_path.replace("\\", "/")
    for src in sources:
        src_norm = src.rstrip("/")
        if rel == src_norm or rel.startswith(src_norm + "/"):
            return True
    return False


def test_dockerfile_copies_the_ingestion_skill_directory():
    sources = _dockerfile_copy_sources()
    assert _covered(".claude/skills/wos-battlereport-ingestion", sources), (
        f"shell/Dockerfile COPY sources {sources} do not include the ingestion "
        "skill; extract.py/vision.py hard-fail without it (F1, EVAL_ROUND_1.md).")


def test_dockerfile_covers_every_runtime_path_the_ocr_module_needs():
    """Cross-checked against the REAL constants the OCR module resolves at
    import time, not a hardcoded string — catches drift if Agent C ever
    moves the skill directory."""
    from shell.app.ocr import extract, vision

    sources = _dockerfile_copy_sources()
    for label, path in (("extract.VALIDATOR_PATH", extract.VALIDATOR_PATH),
                        ("vision.SCHEMA_MD_PATH", vision.SCHEMA_MD_PATH)):
        rel = path.resolve().relative_to(_REPO_ROOT).as_posix()
        assert _covered(rel, sources), (
            f"{label} resolves to {rel!r}, which shell/Dockerfile's COPY set "
            f"{sources} does not cover.")


def test_dockerfile_still_copies_wos_sim_prototype_and_shell():
    """Non-regression: the fix must ADD a COPY line, not replace one."""
    sources = _dockerfile_copy_sources()
    for expected in ("wos_sim/", "prototype/", "shell/"):
        assert expected in sources


def test_dockerfile_does_not_run_as_root():
    """F28 (EVAL_ROUND_1.md, minor): cheap hardening for a single-VPS
    deployment — the image should drop to a non-root user before CMD."""
    text = (_REPO_ROOT / "shell" / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^USER\s+\S+", text, re.MULTILINE), (
        "shell/Dockerfile never switches away from the root user (F28).")


def test_dockerignore_keeps_secrets_and_sample_captures_out_of_the_image():
    # Build context is the repo root (shell/docker-compose.yml `context: ..`)
    # and the Dockerfile does `COPY shell/ shell/` — without a root
    # .dockerignore a real shell/.env on the build machine is baked into the
    # image (PRODUCTION_CRITERIA E4), and the real-game sample captures under
    # shell/app/ocr/client/samples/ ship as Century Games IP (F1).
    root = Path(__file__).resolve().parents[2]
    ignore = root / ".dockerignore"
    assert ignore.is_file(), "repo-root .dockerignore missing (build context is the root)"
    lines = [ln.strip() for ln in ignore.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    for required in ("shell/.env", ".env", "shell/app/ocr/client/samples/*.jpg"):
        assert required in lines, f".dockerignore must list {required!r}"
    assert "!shell/.env.example" in lines, "the template must still ship"
