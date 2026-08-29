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

C1 (EVAL_ROUND_2.md): the F4 cap above was a single, path-unscoped 256 KiB
limit that applied to /shell/ocr and /shell/ocr/panel too — 6 of 7 real
screenshot fixtures exceed that, so they 413'd at the Caddy edge before
shell/app/main.py's already-correct, already-tested route-aware
BodyLimitMiddleware (MAX_OCR_BODY_BYTES) ever got a chance to allow them.
The tests below statically assert the Caddyfile's OCR-route cap is >= the
app's own MAX_OCR_BODY_BYTES constant, that it is scoped so it does NOT
also loosen the cap for every other path, and that the original small
default cap still exists for everything else.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shell.app.config import Settings  # noqa: E402

_PINNED_DEPS = ("fastapi", "uvicorn", "pydantic", "pydantic-settings", "PyJWT",
                "httpx", "stripe", "asyncpg", "anthropic", "pillow", "imagehash",
                "python-multipart", "pytest", "pytest-asyncio")

_OCR_PATHS = ("/shell/ocr", "/shell/ocr/panel")
_HOSTS = ("wostests.com", "staging.wostests.com")


def _server_block(text: str, host: str) -> str:
    """The `{ ... }` body for one vhost block (matches to the next top-level
    '}' at column 0, which is how every block in this file is formatted)."""
    m = re.search(rf"^{re.escape(host)} \{{(.*?)^\}}", text, re.DOTALL | re.MULTILINE)
    assert m, f"no server block found for {host!r} in shell/Caddyfile"
    return m.group(1)


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
    # C1: request_body directives are now matcher-scoped (`request_body
    # @name { ... }`), not bare `request_body { ... }` — broadened from a
    # bare "request_body\s*\{" so this smoke-test still recognizes the
    # scoped form instead of going stale the moment C1 landed.
    assert re.search(r"request_body(?:\s+@\S+)?\s*\{[^}]*max_size", text, re.DOTALL), (
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


# --------------------------------------------------------- C1: OCR body cap

def test_caddyfile_ocr_route_cap_is_at_least_the_app_ocr_cap():
    """C1 (EVAL_ROUND_2.md): the edge cap for /shell/ocr and /shell/ocr/panel
    must be >= shell/app/config.py's Settings.MAX_OCR_BODY_BYTES — the value
    shell/app/main.py's BodyLimitMiddleware already, correctly, allows for
    those two routes. If Caddy's edge cap is smaller, real screenshot
    uploads 413 before the app-level cap ever gets a say."""
    text = _caddyfile_text()
    app_ocr_cap = Settings(_env_file=None).MAX_OCR_BODY_BYTES
    assert app_ocr_cap == 16 * 1024 * 1024 + 65_536  # pin the value this test relies on

    for host in _HOSTS:
        block = _server_block(text, host)
        matcher_names = re.findall(
            r"@(\S+)\s+path\s+/shell/ocr\s+/shell/ocr/panel\b", block)
        assert matcher_names, (
            f"{host}: no Caddyfile matcher scopes both OCR upload routes "
            "together — C1's fix depends on being able to give them a "
            "distinct, larger max_size than every other path.")
        cap = None
        for name in matcher_names:
            m = re.search(rf"request_body\s+@{re.escape(name)}\s*\{{[^}}]*"
                          rf"max_size\s+(\d+)\b", block)
            if m:
                cap = int(m.group(1))
                break
        assert cap is not None, (
            f"{host}: found an OCR-path matcher but no request_body block "
            "using it with a plain numeric (byte-exact) max_size.")
        assert cap >= app_ocr_cap, (
            f"{host}: Caddy's OCR-route cap ({cap} bytes) is smaller than "
            f"the app's MAX_OCR_BODY_BYTES ({app_ocr_cap} bytes) — real "
            "screenshot uploads would still 413 at the edge (C1).")


def test_caddyfile_ocr_cap_does_not_leak_onto_other_paths():
    """Non-regression: the OCR allowance must be scoped AWAY from every other
    path (via a complementary `not path` matcher), not just added alongside
    an unscoped default — two request_body blocks that BOTH match the same
    request would stack (Caddy re-wraps the body reader each time), silently
    re-imposing the smaller cap on OCR uploads and reopening C1 exactly."""
    text = _caddyfile_text()
    for host in _HOSTS:
        block = _server_block(text, host)
        assert re.search(r"@\S+\s*\{\s*not\s+path\s+/shell/ocr\s+/shell/ocr/panel\b",
                         block), (
            f"{host}: the non-OCR request_body block must be scoped with a "
            "`not path /shell/ocr /shell/ocr/panel` matcher (or equivalent), "
            "so it never also applies to the two OCR upload routes.")


def test_caddyfile_default_cap_still_256kb_for_everything_else():
    """Non-regression (F4): the ORIGINAL small cap must still exist for
    every non-OCR path — C1's fix is a carve-out, not a global loosening."""
    text = _caddyfile_text()
    for host in _HOSTS:
        block = _server_block(text, host)
        assert re.search(r"@\S+\s*\{\s*not\s+path[^}]*\}\s*"
                         r"request_body\s+@\S+\s*\{\s*max_size\s+256KB",
                         block, re.DOTALL), (
            f"{host}: the non-OCR-scoped request_body block must still cap "
            "at 256KB (F4's original default).")


# ---------------------------------------------------------- F28: compose

def test_compose_sets_resource_and_hardening_limits():
    text = _compose_text()
    assert "mem_limit" in text
    assert "cpus" in text
    assert "no-new-privileges" in text
