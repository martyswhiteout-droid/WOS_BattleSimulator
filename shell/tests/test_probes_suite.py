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
MAX_RUNS = 1000   # F4-b (limits.py _clamp_runs) / db.py _DEFAULT_MAX_RUNS


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
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            return respond(400, {"error": "invalid_n"})
        panel = own.get("panel") if isinstance(own, dict) else None
        if isinstance(panel, dict) and any("|" not in k for k in panel):
            return respond(400, {"error": "bad_panel_key"})
        counts[user] = counts.get(user, 0) + 1
        if counts[user] > BURST_LIMIT:
            return respond(429, {"error": "burst"})
        # F4-b (limits.py _clamp_runs): an oversized n is silently clamped to
        # entitlements.max_runs, never rejected — mirrors the real app so
        # this stub models the SAME contract adv_absurd_n asserts against.
        return respond(200, {"verdict": "stub", "n": min(n, MAX_RUNS)})

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

    # F12: probe_burst must run LAST so it can never contaminate anything
    # that runs after it (there is nothing after it).
    assert results[-1].name == "burst_over_limit_429"

    # F12 regression: adv_unknown_fields is the one stub-reachable adversarial
    # payload whose body clears every check the stub implements (n=50 valid,
    # no "panel" key to reject). Before the fix, it inherited a 429 from
    # probe_burst's 8 prior requests — masked only because its accepted
    # range (200-499) happens to include 429 too. Assert the REAL observed
    # status is 200 (its true behavior), not merely "in the accepted range".
    assert by_name["adv_unknown_fields"].observed == "200"

    # The stub has no route for the new D4/C3/OCR-panel probes (docs,
    # webhook, /shell/ocr/panel) — each has its own dedicated pass/fail test
    # below against a purpose-built mock. Restrict this "no unexpected
    # FAILs" check to the core contract this stub actually models.
    core_names = {"health", "anonymous_predict_401", "sub_5000_troops_400",
                  "burst_over_limit_429", "free_plan_ocr_402"}
    core_failed = [r for r in results if r.status == "FAIL"
                   and (r.name in core_names or r.name.startswith("adv_"))]
    assert not core_failed, "unexpected FAILs:\n" + "\n".join(
        f"{r.name}: expected {r.expected}, observed {r.observed} ({r.notes})"
        for r in core_failed)


def test_huge_body_generator_produces_valid_troops_shape():
    """F12: the old generator omitted "enemy" entirely, so every run 400'd
    on below_min_troops and never touched the size limit. The regenerated
    body must have BOTH sides valid (>= MIN_TROOPS) so a rejection can only
    be about size."""
    descriptor = next(d for d in rp.load_payload_descriptors()
                       if d["name"] == "huge_body")
    kw = rp._materialize_body(descriptor, rp.ProbeOptions())
    body = json.loads(kw["content"])
    assert body["own"]["troops_total"] >= MIN_TROOPS
    assert body["enemy"]["troops_total"] >= MIN_TROOPS
    assert len(kw["content"]) >= descriptor["generate"]["approx_bytes"]


def test_huge_body_descriptor_expects_413_only():
    descriptor = next(d for d in rp.load_payload_descriptors()
                       if d["name"] == "huge_body")
    assert descriptor["expected_status_min"] == 413
    assert descriptor["expected_status_max"] == 413


def test_burst_reset_sleep_fires_between_panel_probes_and_adversarial():
    """The suite must reset the shared burst window (a sleep, real or
    stubbed) between the three budget-consuming /shell/ocr/panel probes and
    the adversarial block — proven here by monkeypatching time.sleep rather
    than actually waiting out a real window."""
    calls = []
    real_sleep = rp.time.sleep
    rp.time.sleep = lambda s: calls.append(s)
    try:
        transport = httpx.WSGITransport(app=make_stub_wsgi())
        with httpx.Client(transport=transport, base_url="http://stub.test") as c:
            opts = rp.ProbeOptions(dev_bypass=True, burst_count=8, timeout=10,
                                   burst_reset_sleep_s=61.0)
            rp.run_probes(c, opts)
    finally:
        rp.time.sleep = real_sleep
    assert calls == [61.0]


def test_burst_reset_sleep_is_off_by_default():
    """Library/test callers get a fast suite unless they opt in (main()'s
    CLI defaults --burst-reset-sleep to a real 61s; ProbeOptions() itself
    defaults to 0 so importing this module never silently blocks)."""
    assert rp.ProbeOptions().burst_reset_sleep_s == 0.0


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


# =====================================================================
# Dedicated tests for the new probes (each against a purpose-built mock,
# not the generic contract stub above, since these exercise paths — auto
# docs, the Stripe webhook, /shell/ocr/panel — the stub does not model).
# =====================================================================

def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="http://stub.test")


# ------------------------------------------------------- docs endpoints (F5/D4)

def test_docs_probe_skips_under_dev_bypass():
    def handler(request):
        raise AssertionError("must not probe when dev_bypass is set")
    with _mock_client(handler) as client:
        r = rp.probe_docs_endpoints_closed(client, rp.ProbeOptions(dev_bypass=True))
    assert r.status == "SKIP"


def test_docs_probe_fails_when_docs_are_open():
    """Reproduces EVAL_ROUND_1 §3c A7 exactly: /docs, /redoc, /openapi.json
    all 200 anonymously — this is the CURRENT, unfixed real-app shape (F5 is
    Agent A's fix, not yet merged here)."""
    def handler(request):
        return httpx.Response(200, json={"openapi": "3.0"})
    with _mock_client(handler) as client:
        r = rp.probe_docs_endpoints_closed(client, rp.ProbeOptions(dev_bypass=False))
    assert r.status == "FAIL"
    assert "/docs" in r.notes


def test_docs_probe_passes_when_docs_are_closed():
    """The TARGET (fixed) shape once Agent A ships F5."""
    def handler(request):
        return httpx.Response(404)
    with _mock_client(handler) as client:
        r = rp.probe_docs_endpoints_closed(client, rp.ProbeOptions(dev_bypass=False))
    assert r.status == "PASS"


# --------------------------------------------------- webhook signature (C3)

def test_webhook_signature_probe_passes_on_400_bad_signature():
    def handler(request):
        return httpx.Response(400, json={"detail": "invalid signature"})
    with _mock_client(handler) as client:
        r = rp.probe_invalid_webhook_signature(client, rp.ProbeOptions())
    assert r.status == "PASS"


def test_webhook_signature_probe_passes_on_503_no_secret_outside_dev():
    def handler(request):
        return httpx.Response(503, json={"detail": "webhook secret not configured"})
    with _mock_client(handler) as client:
        r = rp.probe_invalid_webhook_signature(client, rp.ProbeOptions())
    assert r.status == "PASS"


def test_webhook_signature_probe_fails_if_forged_event_applied():
    """A forged signature silently accepted as a real, state-changing event
    outside dev must FAIL — this is the exact vulnerability C3 exists to
    prevent (a forged checkout.session.completed would grant free Pro)."""
    def handler(request):
        return httpx.Response(200, json={"received": True, "duplicate": False,
                                         "disposition": "applied"})
    with _mock_client(handler) as client:
        r = rp.probe_invalid_webhook_signature(client,
                                               rp.ProbeOptions(dev_bypass=False))
    assert r.status == "FAIL"


def test_webhook_signature_probe_skips_applied_200_only_under_dev_bypass():
    def handler(request):
        return httpx.Response(200, json={"received": True, "duplicate": False,
                                         "disposition": "applied"})
    with _mock_client(handler) as client:
        r = rp.probe_invalid_webhook_signature(client,
                                               rp.ProbeOptions(dev_bypass=True))
    assert r.status == "SKIP"


def test_webhook_signature_probe_fails_on_unexpected_5xx():
    def handler(request):
        return httpx.Response(500, text="stack trace")
    with _mock_client(handler) as client:
        r = rp.probe_invalid_webhook_signature(client, rp.ProbeOptions())
    assert r.status == "FAIL"


# ------------------------------------------------- /shell/ocr/panel (QA_PLAN §7)

def test_ocr_panel_free_tier_probe_passes_on_402():
    def handler(request):
        return httpx.Response(402, json={"error": "payment_required"})
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_free_tier(client, rp.ProbeOptions(dev_bypass=True))
    assert r.status == "PASS"


def test_ocr_panel_free_tier_probe_fails_on_200():
    def handler(request):
        return httpx.Response(200, json={"source": "mock"})
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_free_tier(client, rp.ProbeOptions(dev_bypass=True))
    assert r.status == "FAIL"


def test_ocr_panel_oversize_probe_passes_on_413():
    def handler(request):
        return httpx.Response(413, json={"error": "body_too_large"})
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_oversize(client, rp.ProbeOptions())
    assert r.status == "PASS"


def test_ocr_panel_oversize_probe_fails_on_200():
    def handler(request):
        return httpx.Response(200, json={"source": "mock"})
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_oversize(client, rp.ProbeOptions())
    assert r.status == "FAIL"


def test_ocr_panel_sniff_probe_passes_on_415():
    def handler(request):
        return httpx.Response(415, json={"error": "unsupported_image_type"})
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_sniff(client, rp.ProbeOptions())
    assert r.status == "PASS"


def test_ocr_panel_mock_200_probe_skips_without_dev_bypass():
    def handler(request):
        raise AssertionError("should not probe without --dev-bypass")
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_mock_200(client, rp.ProbeOptions(dev_bypass=False))
    assert r.status == "SKIP"


def test_ocr_panel_mock_200_probe_skips_on_engine_unavailable():
    def handler(request):
        return httpx.Response(503, json={"error": "ocr_engine_unavailable"})
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_mock_200(client, rp.ProbeOptions(dev_bypass=True))
    assert r.status == "SKIP"


def test_ocr_panel_mock_200_probe_passes_on_200_with_source():
    def handler(request):
        return httpx.Response(200, json={"source": "mock", "fields": {}})
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_mock_200(client, rp.ProbeOptions(dev_bypass=True))
    assert r.status == "PASS"


def test_ocr_panel_mock_200_probe_fails_on_200_without_source():
    def handler(request):
        return httpx.Response(200, json={"fields": {}})
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_mock_200(client, rp.ProbeOptions(dev_bypass=True))
    assert r.status == "FAIL"


def test_ocr_panel_mock_200_probe_skips_on_real_engine_rejecting_the_fixture():
    """Mn1 (EVAL_ROUND_2.md): a --dev-bypass target WITHOUT OCR_PANEL_MOCK=1
    routes the probe's synthetic fixture to the real engine, which correctly
    422s it as unreadable — a deployment/config fact (the mock isn't on
    here), not a code defect, and must SKIP like the existing 503 branch,
    not FAIL."""
    def handler(request):
        return httpx.Response(422, json={"error": "unreadable_tokens"})
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_mock_200(client, rp.ProbeOptions(dev_bypass=True))
    assert r.status == "SKIP"


def test_ocr_panel_mock_200_probe_still_fails_on_a_different_422():
    """Non-regression: only the specific 'unreadable_tokens' reason (the
    real engine's honest rejection of a fake image) is treated as SKIP —
    this is not a blanket "422 is fine" carve-out; any OTHER 422 must still
    FAIL."""
    def handler(request):
        return httpx.Response(422, json={"error": "invalid_side"})
    with _mock_client(handler) as client:
        r = rp.probe_ocr_panel_mock_200(client, rp.ProbeOptions(dev_bypass=True))
    assert r.status == "FAIL"


# --------------------------------------------- adversarial clamp check (M5)
# EVAL_ROUND_2.md M5: absurd_n.json used to expect a 400/429 rejection, but
# F4-b (limits.py _clamp_runs) silently clamps an oversized n to
# entitlements.max_runs and answers 200 — the stale expectation false-FAILed
# the correct, intended behavior (the exact failure class F12 was about:
# a gate that fails a satisfied criterion corrupts the same evidence trail
# as one that passes a violated one).

def test_absurd_n_descriptor_expects_the_clamp_not_a_rejection():
    descriptor = next(d for d in rp.load_payload_descriptors()
                       if d["name"] == "absurd_n")
    assert descriptor["expected_status_min"] == 200
    assert descriptor["expected_status_max"] == 200
    assert descriptor["expect_clamped_field"] == {"field": "n", "value": 1000}


def _absurd_n_descriptor():
    return next(d for d in rp.load_payload_descriptors() if d["name"] == "absurd_n")


def test_adv_absurd_n_passes_when_the_response_shows_the_real_clamp():
    def handler(request):
        return httpx.Response(200, json={"n": 1000, "verdict": "clamped"})
    with _mock_client(handler) as client:
        r = rp.probe_adversarial(client, rp.ProbeOptions(), _absurd_n_descriptor())
    assert r.status == "PASS", r.notes


def test_adv_absurd_n_fails_on_an_unclamped_200():
    """'Gates must not lie': a 200 alone is not proof the clamp happened —
    an unclamped n=10000000 sailing through as 200 must still FAIL, not
    false-PASS on status code alone."""
    def handler(request):
        return httpx.Response(200, json={"n": 10000000, "verdict": "unclamped"})
    with _mock_client(handler) as client:
        r = rp.probe_adversarial(client, rp.ProbeOptions(), _absurd_n_descriptor())
    assert r.status == "FAIL"
    assert "clamp" in r.notes.lower()


def test_adv_absurd_n_fails_on_a_500():
    def handler(request):
        return httpx.Response(500, text="stack trace")
    with _mock_client(handler) as client:
        r = rp.probe_adversarial(client, rp.ProbeOptions(), _absurd_n_descriptor())
    assert r.status == "FAIL"


def test_adv_absurd_n_fails_on_a_400_rejection_too():
    """The pre-fix 'reject with 4xx' behavior must ALSO now FAIL — a
    real reversion to rejecting oversized n would not be F4-b's documented
    contract either, so the probe must not silently accept it."""
    def handler(request):
        return httpx.Response(400, json={"error": "n_too_large"})
    with _mock_client(handler) as client:
        r = rp.probe_adversarial(client, rp.ProbeOptions(), _absurd_n_descriptor())
    assert r.status == "FAIL"


def test_probe_adversarial_without_clamp_field_is_unaffected():
    """Non-regression: every OTHER descriptor (no expect_clamped_field) keeps
    the original status-range-only behavior."""
    descriptor = {"name": "plain", "expected_status_min": 400,
                 "expected_status_max": 429, "body": {}}

    def handler(request):
        return httpx.Response(422, json={"error": "whatever"})
    with _mock_client(handler) as client:
        r = rp.probe_adversarial(client, rp.ProbeOptions(), descriptor)
    assert r.status == "PASS"
