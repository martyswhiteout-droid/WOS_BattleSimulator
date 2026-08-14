"""Static-config regression tests for shell/requirements.txt, Caddyfile, and
docker-compose.yml (Agent A) — keyless, no docker/caddy binary required.

F15 (EVAL_ROUND_1.md): shell/requirements.txt called itself "pinned" but had
exactly one version constraint out of 14 dependencies — a `docker build` next
month could silently ship a different FastAPI/stripe/anthropic major.

F4 (EVAL_ROUND_1.md) Caddy portion: no ``request_body { max_size }`` — a
12 MB JSON body sailed through as a 200 in 9.55s (app-level cap is
shell/app/main.py's BodyLimitMiddleware, covered by test_body_limit.py; this
file covers the edge-level cap Caddy is supposed to add too).

F14 (EVAL_ROUND_1.md) Caddy portion: no Strict-Transport-Security / other
security headers (app-level CORS-origin lock is CorsLockMiddleware, covered
by test_cors_lock.py).

F28 (EVAL_ROUND_1.md, minor): docker-compose.yml set no mem_limit/cpus/
security_opt/read_only hardening for a single-VPS deployment.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_PINNED_DEPS = ("fastapi", "uvicorn", "pydantic", "pydantic-settings", "PyJWT",
                "httpx", "stripe", "asyncpg", "anthropic", "pillow", "imagehash",
                "python-multipart", "pytest", "pytest-asyncio")


def _requirements_text() -> str:
    return (_REPO_ROOT / "shell" / "requirements.txt").read_text(encoding="utf-8")


def _caddyfile_text() -> str:
    return (_REPO_ROOT / "shell" / "Caddyfile").read_text(encoding="utf-8")


def _compose_text() -> str:
    return (_REPO_ROOT / "shell" / "docker-compose.yml").read_text(encoding="utf-8")


# --------------------------------------------------------------- F15: pins

def test_every_base_dependency_is_exactly_pinned():
    text = _requirements_text()
    for dep in _PINNED_DEPS:
        # match the line for this dep (allow the [crypto]-style extra) and
        # require an exact-version pin (==), not >=/unpinned.
        pattern = re.compile(
            rf"^{re.escape(dep)}(\[[a-zA-Z]+\])?==\S+\s*$", re.MULTILINE)
        assert pattern.search(text), (
            f"{dep!r} is not exactly pinned (==) in shell/requirements.txt (F15).")


def test_ocr_ladder_pins_are_still_present():
    """Non-regression: the OCR-merge pins (rapidocr/onnxruntime) must survive
    this edit untouched."""
    text = _requirements_text()
    assert "rapidocr==3.9.2" in text
    assert "onnxruntime==1.28.0" in text


# ------------------------------------------------------------ F4/F14: Caddy

def test_caddyfile_caps_request_body_size():
    text = _caddyfile_text()
    assert re.search(r"request_body\s*\{[^}]*max_size", text, re.DOTALL), (
        "shell/Caddyfile has no request_body { max_size } cap (F4).")


def test_caddyfile_sets_hsts_and_security_headers():
    text = _caddyfile_text()
    assert "Strict-Transport-Security" in text
    assert "X-Content-Type-Options" in text
    assert "X-Frame-Options" in text


def test_caddyfile_still_proxies_both_hosts():
    """Non-regression: the hardening must not drop either vhost block."""
    text = _caddyfile_text()
    assert "wostests.com" in text
    assert "staging.wostests.com" in text
    assert text.count("reverse_proxy app:8200") >= 2


# ---------------------------------------------------------- F28: compose

def test_compose_sets_resource_and_hardening_limits():
    text = _compose_text()
    assert "mem_limit" in text
    assert "cpus" in text
    assert "no-new-privileges" in text
