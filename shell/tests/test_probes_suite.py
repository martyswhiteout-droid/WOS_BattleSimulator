"""Tests for shell/probes/run_probes.py (Agent D). Keyless.

Runs the full probe suite against an in-process WSGI stub that implements
the shell contract (auth 401, MIN_TROOPS 400, burst 429, free-OCR 402,
clean 4xx on adversarial bodies) via httpx.WSGITransport — no server, no
keys. Also validates every payload descriptor file parses as JSON.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

SHELL_DIR = Path(__file__).resolve().parents[1]
PROBES_DIR = SHELL_DIR / "probes"

spec = importlib.util.spec_from_file_location(
    "run_probes_under_test", PROBES_DIR / "run_probes.py")
rp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rp
spec.loader.exec_module(rp)

MIN_TROOPS = 5000
BURST_LIMIT = 5
BODY_LIMIT = 1_000_000


def make_stub_wsgi():
    """A tiny WSGI app behaving like the production shell's contract."""
    counts: dict[str, int] = {}

    def app(environ, start_response):
        def respond(status: int, payload: dict | None = None):
            body = json.dumps(payload or {"status": status}).encode()
            start_response(f"{status} S", [("Content-Type", "application/json")])
            return [body]

        path = environ.get("PATH_INFO", "")
        headers = {k[5:].replace("_", "-").lower(): v
                   for k, v in environ.items() if k.startswith("HTTP_")}
        if path == "/shell/health":
            return respond(200, {"status": "ok"})
        user = headers.get("x-dev-user")
        if user is None:
            return respond(401, {"error": "auth_required"})
        if path == "/shell/ocr":
            if headers.get("x-dev-plan", "free") == "free":
                return respond(402, {"error": "payment_required"})
            return respond(200)
        if path != "/api/predict":
            return respond(404)

        length = int(environ.get("CONTENT_LENGTH") or 0)
        if length > BODY_LIMIT:
            return respond(413, {"error": "body_too_large"})
        raw = environ["wsgi.input"].read(length)
        try:
            data = json.loads(raw)
        except Exception:
            return respond(400, {"error": "invalid_json"})
        if not isinstance(data, dict):
            return respond(400, {"error": "invalid_input"})

        def troops(side):
            if not isinstance(side, dict):
                return None
            t = side.get("troops_total")
            return t if isinstance(t, int) and not isinstance(t, bool) else None

        own, enemy = data.get("own"), data.get("enemy")
        t_own, t_enemy = troops(own), troops(enemy)
        if t_own is None or t_enemy is None:
            return respond(400, {"error": "invalid_input"})
        if t_own < MIN_TROOPS or t_enemy < MIN_TROOPS:
            return respond(400, {"error": "below_min_troops"})
        n = data.get("n")
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 10000:
            return respond(400, {"error": "invalid_n"})
        panel = own.get("panel") if isinstance(own, dict) else None
        if isinstance(panel, dict) and any("|" not in k for k in panel):
            return respond(400, {"error": "bad_panel_key"})
        counts[user] = counts.get(user, 0) + 1
        if counts[user] > BURST_LIMIT:
            return respond(429, {"error": "burst"})
        return respond(200, {"verdict": "stub"})

    return app


@pytest.fixture()
def client():
    transport = httpx.WSGITransport(app=make_stub_wsgi())
    with httpx.Client(transport=transport,
                      base_url="http://stub.test") as c:
        yield c


def test_payload_descriptors_are_valid_json():
    files = sorted((PROBES_DIR / "payloads").glob("*.json"))
    assert len(files) >= 8
    names = set()
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))  # must parse
        assert d["name"], f
        assert d.get("path", "/api/predict").startswith("/")
        assert ("body" in d) or ("raw_body" in d) or ("generate" in d)
        names.add(d["name"])
    # the required adversarial scenarios exist
    for required in ("malformed_json", "huge_body", "negative_troops",
                     "string_where_number", "unknown_fields"):
        assert required in names, f"missing payload: {required}"


def test_full_suite_against_contract_stub(client):
    opts = rp.ProbeOptions(dev_bypass=True, burst_count=8, timeout=10)
    results = rp.run_probes(client, opts)
    by_name = {r.name: r for r in results}

    assert by_name["health"].status == "PASS"
    assert by_name["anonymous_predict_401"].status == "PASS"     # stub 401s
    assert by_name["sub_5000_troops_400"].status == "PASS"
    assert by_name["burst_over_limit_429"].status == "PASS"
    assert by_name["free_plan_ocr_402"].status == "PASS"
    adversarial = [r for r in results if r.name.startswith("adv_")]
    assert len(adversarial) >= 8
    failed = [r for r in results if r.status == "FAIL"]
    assert not failed, "unexpected FAILs:\n" + "\n".join(
        f"{r.name}: expected {r.expected}, observed {r.observed} ({r.notes})"
        for r in failed)


def test_suite_flags_a_5xx_server():
    def bad_app(environ, start_response):
        start_response("500 ISE", [("Content-Type", "text/plain")])
        return [b"stack trace here"]

    with httpx.Client(transport=httpx.WSGITransport(app=bad_app),
                      base_url="http://bad.test") as client:
        opts = rp.ProbeOptions(dev_bypass=True, burst_count=3, timeout=5)
        results = rp.run_probes(client, opts)
    advs = [r for r in results if r.name.startswith("adv_")]
    assert advs and all(r.status == "FAIL" for r in advs), \
        "5xx on adversarial input must FAIL the probe (B2: never a 500)"


def test_markdown_report_renders(client):
    opts = rp.ProbeOptions(dev_bypass=True, burst_count=8)
    md = rp.render_markdown(rp.run_probes(client, opts), "http://stub.test")
    assert "| Probe | Criteria | Expected | Observed | Result | Notes |" in md
    assert "anonymous_predict_401" in md and "**PASS**" in md


def test_module_importable_as_script_help():
    """CLI arg surface stays stable for promote.py step 7."""
    with pytest.raises(SystemExit) as e:
        rp.main(["--help"])
    assert e.value.code == 0
