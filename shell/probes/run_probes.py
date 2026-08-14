"""shell/probes/run_probes.py — staging probe suite for the production shell.

Implements PRODUCTION_PLAN.md §3 step 7 and gathers machine evidence for
PRODUCTION_CRITERIA.md items C1 (anonymous -> 401), D1 (MIN_TROOPS -> 400),
D2 (burst -> 429), C2/§2.4 (free-plan OCR -> 402/403), B2/E2 (adversarial
payloads -> clean 4xx, never 5xx), D4 (debug/auto-doc endpoints closed
outside dev), C3 (Stripe webhook signature verification), plus a
/shell/health liveness check and the docs/OCR_QA_PLAN.md §7 panel-endpoint
probes (free-tier paywall, oversize, MIME sniff, mock happy-path).

EVAL_ROUND_1.md F12 (burst-window contamination — binding on this file):
limits.py enforces ONE per-account burst budget (sliding 60s window) SHARED
across every metered endpoint (/api/predict AND /shell/ocr*) — so ANY probe
whose request is allowed through the paywall/quota checks consumes from the
same shared window, regardless of what it is actually testing. run_probes()
below sequences the suite so that (a) probe_burst — the one probe that
DELIBERATELY exhausts the window — always runs LAST, and (b) a configurable
sleep resets the window between the handful of earlier probes that
incidentally consume budget (the three /shell/ocr/panel probes) and the
adversarial block, so no probe ever inherits a 429 that belongs to a
different one (the exact failure this file used to have: adv_bad_panel_key
observed 429 instead of its own real status, masked only because
adv_absurd_n/adv_unknown_fields' accepted ranges happened to include 429 too).

Runnable against ANY base URL (local DEV_BYPASS shell, staging, prod):

  python shell/probes/run_probes.py --base https://staging.wostests.com
  python shell/probes/run_probes.py --base http://localhost:8200 --dev-bypass
  python shell/probes/run_probes.py --base ... --out probe_report.md

--dev-bypass sends the DEV_BYPASS mock-identity headers (X-Dev-User /
X-Dev-Plan, per shell/ARCHITECTURE.md's auth contract) so authed probes work
keyless. NOTE: under a DEV_BYPASS=1 server every request is authenticated, so
the anonymous-401 probe cannot be meaningful there — it is reported as SKIP,
not PASS. Run against staging (DEV_BYPASS off) for real C1 evidence.

Output: a markdown evidence table (stdout, and --out FILE). Exit codes:
0 = all probes passed (skips allowed) · 1 = at least one probe failed ·
2 = could not reach the base URL at all.

Adversarial payloads live in shell/probes/payloads/*.json as VALID-JSON
descriptor files (the malformed bodies are carried as strings / generated at
runtime, so the descriptors themselves always parse).
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    print("ERROR: httpx required (pip install httpx)", file=sys.stderr)
    raise SystemExit(1)

PAYLOAD_DIR = Path(__file__).parent / "payloads"
DEV_HEADERS = {"X-Dev-User": "probe_user", "X-Dev-Plan": "pro"}
FREE_HEADERS = {"X-Dev-User": "probe_free_user", "X-Dev-Plan": "free"}

# Minimal valid-shaped predict body (BRD §9 profile dicts; serialize.profile_from_dict)
# fc (Fire Crystal tier) MUST be 1-10 — verified live against the real app: 0
# is rejected ("FC 0 outside 1-10") BEFORE the request ever reaches the
# engine or limits.py's usage recording. It was 0 here previously, which
# silently made this helper (and every adversarial payload copying its
# quality shape) fail for that reason instead of whatever they actually
# meant to test — the same "false evidence" failure class as F12's
# huge_body bug, just from invalid test data instead of ordering.
def predict_body(troops: int = 10_000) -> dict:
    def side(role):
        return {
            "label": f"probe-{role}", "role": role, "troops_total": troops,
            "formation": {"Infantry": 0.5, "Lancer": 0.2, "Marksman": 0.3},
            "quality": {c: {"tier": 10, "fc": 1, "t12_stack": 0}
                        for c in ("Infantry", "Lancer", "Marksman")},
        }
    return {"own": side("rally"), "enemy": side("garrison"), "n": 50, "seed": 1}


@dataclass
class ProbeResult:
    name: str
    criteria: str          # PRODUCTION_CRITERIA item(s) this evidences
    expected: str
    observed: str
    status: str            # "PASS" | "FAIL" | "SKIP"
    notes: str = ""


@dataclass
class ProbeOptions:
    dev_bypass: bool = False
    burst_count: int = 8
    timeout: float = 20.0
    huge_body_bytes: int = 2_097_152  # 2 MiB
    sleep_between_burst: float = 0.0
    # F12: seconds to sleep past the sliding-60s burst window between the
    # OCR-panel probes and the adversarial block (see module docstring).
    # Defaults to 0 (off) so library/test use stays fast; main() below
    # defaults the CLI to a real 61s. A no-op unless dev_bypass is set, since
    # without mock identity headers every request downstream 401s before it
    # can consume any budget.
    burst_reset_sleep_s: float = 0.0


def _req(client: httpx.Client, method: str, path: str, *, headers=None,
         timeout: float = 20.0, **kw):
    """One request; returns (response|None, error_string|None). Never raises."""
    try:
        r = client.request(method, path, headers=headers, timeout=timeout, **kw)
        return r, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _status_probe(client, opts, *, name, criteria, method, path, expected,
                  headers=None, **kw) -> ProbeResult:
    r, err = _req(client, method, path, headers=headers, timeout=opts.timeout, **kw)
    exp_str = "/".join(str(e) for e in expected)
    if err:
        return ProbeResult(name, criteria, exp_str, err, "FAIL")
    ok = r.status_code in expected
    return ProbeResult(name, criteria, exp_str, str(r.status_code),
                       "PASS" if ok else "FAIL",
                       "" if ok else _body_snip(r))


def _body_snip(r, n=120) -> str:
    try:
        return r.text[:n].replace("\n", " ").replace("|", "\\|")
    except Exception:
        return "<unreadable body>"


# ---------------------------------------------------------------- core probes

def probe_health(client, opts) -> ProbeResult:
    return _status_probe(client, opts, name="health", criteria="ops",
                         method="GET", path="/shell/health", expected=[200])


def probe_anonymous_predict(client, opts) -> ProbeResult:
    r, err = _req(client, "POST", "/api/predict", json=predict_body(),
                  timeout=opts.timeout)  # NO auth headers
    if err:
        return ProbeResult("anonymous_predict_401", "C1", "401", err, "FAIL")
    if r.status_code == 401:
        return ProbeResult("anonymous_predict_401", "C1", "401", "401", "PASS")
    if r.status_code >= 500:
        return ProbeResult("anonymous_predict_401", "C1", "401",
                           str(r.status_code), "FAIL", "5xx on anonymous request")
    if opts.dev_bypass:
        return ProbeResult(
            "anonymous_predict_401", "C1", "401", str(r.status_code), "SKIP",
            "server runs DEV_BYPASS=1 (all requests authed); re-run vs staging")
    return ProbeResult("anonymous_predict_401", "C1", "401",
                       str(r.status_code), "FAIL", _body_snip(r))


def probe_min_troops(client, opts) -> ProbeResult:
    return _status_probe(
        client, opts, name="sub_5000_troops_400", criteria="D1",
        method="POST", path="/api/predict", expected=[400],
        headers=DEV_HEADERS if opts.dev_bypass else None,
        json=predict_body(troops=100))


def probe_burst(client, opts) -> ProbeResult:
    """> burst limit (5/min) rapid requests on a pro account -> at least one 429."""
    headers = DEV_HEADERS if opts.dev_bypass else None
    statuses, errors = [], []
    for _ in range(opts.burst_count):
        r, err = _req(client, "POST", "/api/predict", json=predict_body(),
                      headers=headers, timeout=opts.timeout)
        if err:
            errors.append(err)
        else:
            statuses.append(r.status_code)
        if opts.sleep_between_burst:
            time.sleep(opts.sleep_between_burst)
    observed = ",".join(map(str, statuses)) or (errors[0] if errors else "none")
    if any(s >= 500 for s in statuses):
        return ProbeResult("burst_over_limit_429", "D2", "429 among responses",
                           observed, "FAIL", "5xx under burst")
    if 429 in statuses:
        return ProbeResult("burst_over_limit_429", "D2", "429 among responses",
                           observed, "PASS",
                           f"{opts.burst_count} rapid requests")
    return ProbeResult("burst_over_limit_429", "D2", "429 among responses",
                       observed, "FAIL", "no 429 seen — burst limit not enforced?")


def probe_free_plan_ocr(client, opts) -> ProbeResult:
    headers = dict(FREE_HEADERS) if opts.dev_bypass else {}
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    r, err = _req(client, "POST", "/shell/ocr", headers=headers or None,
                  files={"image": ("probe.png", io.BytesIO(fake_png), "image/png")},
                  timeout=opts.timeout)
    if err:
        return ProbeResult("free_plan_ocr_402", "C2/§2.4", "402/403", err, "FAIL")
    expected = {402, 403} if opts.dev_bypass else {401, 402, 403}
    ok = r.status_code in expected
    return ProbeResult("free_plan_ocr_402", "C2/§2.4",
                       "/".join(map(str, sorted(expected))), str(r.status_code),
                       "PASS" if ok else "FAIL", "" if ok else _body_snip(r))


DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def probe_docs_endpoints_closed(client, opts) -> ProbeResult:
    """EVAL_ROUND_1.md F5 / PRODUCTION_CRITERIA D4: the shell app disables
    docs_url/redoc_url/openapi_url on itself, but the prototype sub-app is
    mounted at '/' and brings its OWN unsuppressed FastAPI docs with it — so
    these three paths must never be reachable outside dev. The static
    promote.py gate (gate_debug_endpoints) greps bundle text for literal
    debug-route patterns and cannot see this (FastAPI's auto-docs are not a
    string anywhere in the source); only a live probe can catch it — this is
    that probe. DEV_BYPASS targets may legitimately leave docs open as a
    local convenience, so this is SKIP (not FAIL/PASS) there."""
    if opts.dev_bypass:
        return ProbeResult(
            "docs_endpoints_closed", "D4", "never 200 (staging/prod)",
            "not probed", "SKIP",
            "server runs DEV_BYPASS=1 — docs may be intentionally open in "
            "dev; re-run vs staging/prod for real D4 evidence")
    observed = {}
    for path in DOCS_PATHS:
        r, err = _req(client, "GET", path, timeout=opts.timeout)
        observed[path] = err or str(r.status_code)
    opened = [p for p, s in observed.items() if s == "200"]
    ok = not opened
    obs_str = ", ".join(f"{p}={s}" for p, s in observed.items())
    return ProbeResult("docs_endpoints_closed", "D4", "never 200", obs_str,
                       "PASS" if ok else "FAIL",
                       "" if ok else f"publicly reachable: {', '.join(opened)}")


def probe_invalid_webhook_signature(client, opts) -> ProbeResult:
    """PRODUCTION_CRITERIA C3: a forged Stripe event with a bogus signature
    must never be accepted as a legitimate, state-changing event.
    shell/app/billing/webhook.py's documented contract: secret configured +
    bad signature -> 400; secret ABSENT and ENV != dev -> 503 (refuse,
    "never skip verification" per Agent B's brief) — either is an acceptable
    PASS here, since both mean the forged event was rejected. Secret absent
    AND ENV == dev intentionally accepts unsigned JSON (keyless dev
    convenience, same design as the DEV_BYPASS auth mock) — that branch is
    indistinguishable from here except via the dev_bypass flag, so a 200
    'applied' response is SKIP (not FAIL) only when dev_bypass was passed."""
    # A fresh id every run: webhook.py's idempotency ledger (audit_log
    # dedup_key) means a REPEATED run against the same long-lived target
    # would otherwise see "duplicate": true / disposition "deduplicated" for
    # a stale id — a harmless outcome that this probe must not mistake for
    # either "applied" (FAIL) or "rejected" (PASS); a unique id sidesteps
    # the ambiguity entirely rather than special-casing it.
    body = {
        "id": f"evt_probe_forged_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {"object": {
            "client_reference_id": "probe_forged_user",
            "customer": "cus_probe_forged",
            "subscription": "sub_probe_forged",
        }},
    }
    headers = {"Stripe-Signature": "t=1,v1=" + "0" * 64}
    r, err = _req(client, "POST", "/shell/webhook/stripe", json=body,
                  headers=headers, timeout=opts.timeout)
    name, criteria, expected = "invalid_webhook_signature", "C3", \
        "400/503, never applied"
    if err:
        return ProbeResult(name, criteria, expected, err, "FAIL")
    if r.status_code in (400, 503):
        return ProbeResult(name, criteria, expected, str(r.status_code), "PASS")
    if r.status_code == 200:
        try:
            disposition = r.json().get("disposition")
        except Exception:
            disposition = None
        if disposition == "applied" and opts.dev_bypass:
            return ProbeResult(
                name, criteria, expected, "200 (applied)", "SKIP",
                "unsigned JSON accepted — expected ONLY when ENV=dev with no "
                "STRIPE_WEBHOOK_SECRET (keyless dev); re-run vs staging/prod")
        return ProbeResult(name, criteria, expected,
                           f"200 (disposition={disposition})", "FAIL",
                           "a forged signature was accepted as a real event")
    if r.status_code >= 500:
        return ProbeResult(name, criteria, expected, str(r.status_code),
                           "FAIL", "unexpected 5xx")
    return ProbeResult(name, criteria, expected, str(r.status_code), "FAIL",
                       _body_snip(r))


# ------------------------------------------------ /shell/ocr/panel (docs/OCR_QA_PLAN.md §7)

def _tiny_png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def probe_ocr_panel_free_tier(client, opts) -> ProbeResult:
    """docs/OCR_QA_PLAN.md §4 A1 ("free-tier-403 probe"). The doc names 403,
    but the implemented contract (shell/ARCHITECTURE.md's shared LimitVerdict
    contract; limits.py OCR_ENDPOINTS includes /shell/ocr/panel, denial is
    402 payment_required) is 402 for BOTH OCR endpoints — probed here against
    the actual code, matching the existing free_plan_ocr_402 probe for the
    older /shell/ocr endpoint. (Doc/code naming mismatch noted, not silently
    "corrected" — docs/OCR_QA_PLAN.md is not owned by this agent.)"""
    headers = dict(FREE_HEADERS) if opts.dev_bypass else {}
    r, err = _req(client, "POST", "/shell/ocr/panel", headers=headers or None,
                  data={"side": "you"},
                  files={"file": ("probe.png", io.BytesIO(_tiny_png()),
                                 "image/png")},
                  timeout=opts.timeout)
    if err:
        return ProbeResult("ocr_panel_free_tier_402", "QA_PLAN §4 A1",
                           "402/403", err, "FAIL")
    expected = {402, 403} if opts.dev_bypass else {401, 402, 403}
    ok = r.status_code in expected
    return ProbeResult("ocr_panel_free_tier_402", "QA_PLAN §4 A1",
                       "/".join(map(str, sorted(expected))),
                       str(r.status_code), "PASS" if ok else "FAIL",
                       "" if ok else _body_snip(r))


def probe_ocr_panel_oversize(client, opts) -> ProbeResult:
    """docs/OCR_QA_PLAN.md §4 A3 ("oversize-413 probe"). panel_router.py's
    _ContentLengthGuardRoute rejects a declared Content-Length above
    MAX_REQUEST_BYTES (8 MiB + 64 KiB framing) before the body is read —
    needs an authenticated pro identity to reach the route at all (a
    free-plan/anonymous request 402s/401s before ever hitting the size
    guard, per limits.py's check order), so this uses the same pro headers
    as the other panel probes below, not the free-tier ones."""
    headers = dict(DEV_HEADERS) if opts.dev_bypass else {}
    big = b"\x89PNG\r\n\x1a\n" + (b"\x00" * (9 * 1024 * 1024))
    r, err = _req(client, "POST", "/shell/ocr/panel", headers=headers or None,
                  data={"side": "you"},
                  files={"file": ("probe.png", io.BytesIO(big), "image/png")},
                  timeout=opts.timeout)
    if err:
        return ProbeResult("ocr_panel_oversize_413", "QA_PLAN §4 A3", "413",
                           err, "FAIL")
    ok = r.status_code == 413
    return ProbeResult("ocr_panel_oversize_413", "QA_PLAN §4 A3", "413",
                       str(r.status_code), "PASS" if ok else "FAIL",
                       "" if ok else _body_snip(r))


def probe_ocr_panel_sniff(client, opts) -> ProbeResult:
    """docs/OCR_QA_PLAN.md §4 A5 ("sniff-415 probe"). A file named *.png
    whose bytes are not a real image must be rejected by magic-byte
    sniffing, never trusted by extension/Content-Type alone
    (panel_router.py:_is_image)."""
    headers = dict(DEV_HEADERS) if opts.dev_bypass else {}
    fake = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 56  # EXE-looking bytes
    r, err = _req(client, "POST", "/shell/ocr/panel", headers=headers or None,
                  data={"side": "you"},
                  files={"file": ("probe.png", io.BytesIO(fake), "image/png")},
                  timeout=opts.timeout)
    if err:
        return ProbeResult("ocr_panel_sniff_415", "QA_PLAN §4 A5", "415",
                           err, "FAIL")
    ok = r.status_code == 415
    return ProbeResult("ocr_panel_sniff_415", "QA_PLAN §4 A5", "415",
                       str(r.status_code), "PASS" if ok else "FAIL",
                       "" if ok else _body_snip(r))


def probe_ocr_panel_mock_200(client, opts) -> ProbeResult:
    """docs/OCR_QA_PLAN.md §4 ("panel-mock-200 probe"). Only meaningful
    against a target with OCR_PANEL_MOCK=1 and ENV=dev
    (panel_router._mock_enabled) — a deployment fact this probe cannot force,
    so it SKIPs rather than false-FAILing when the target isn't configured
    for it (no --dev-bypass), and SKIPs on a clean 503 too (engine
    unavailable is a config/deployment fact, not a code defect)."""
    if not opts.dev_bypass:
        return ProbeResult("ocr_panel_mock_200", "QA_PLAN §4", "200",
                           "not probed", "SKIP",
                           "requires --dev-bypass against an "
                           "OCR_PANEL_MOCK=1, ENV=dev target")
    headers = dict(DEV_HEADERS)
    r, err = _req(client, "POST", "/shell/ocr/panel", headers=headers,
                  data={"side": "you"},
                  files={"file": ("probe.png", io.BytesIO(_tiny_png()),
                                 "image/png")},
                  timeout=opts.timeout)
    if err:
        return ProbeResult("ocr_panel_mock_200", "QA_PLAN §4", "200", err,
                           "FAIL")
    if r.status_code == 503:
        return ProbeResult("ocr_panel_mock_200", "QA_PLAN §4", "200", "503",
                           "SKIP",
                           "OCR engine unavailable on this target (mock not "
                           "enabled here, or no engine deps) — deployment "
                           "fact, not a code defect")
    if r.status_code != 200:
        return ProbeResult("ocr_panel_mock_200", "QA_PLAN §4", "200",
                           str(r.status_code), "FAIL", _body_snip(r))
    try:
        has_source = "source" in r.json()
    except Exception:
        has_source = False
    return ProbeResult("ocr_panel_mock_200", "QA_PLAN §4", "200", "200",
                       "PASS" if has_source else "FAIL",
                       "" if has_source else "200 body missing 'source' key")


# -------------------------------------------------------- adversarial payloads

def load_payload_descriptors(payload_dir: Path = PAYLOAD_DIR) -> list[dict]:
    descriptors = []
    for p in sorted(payload_dir.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))  # descriptors are valid JSON
        d["_file"] = p.name
        descriptors.append(d)
    return descriptors


def _materialize_body(d: dict, opts: ProbeOptions):
    """Returns kwargs for the request from a payload descriptor."""
    ct = d.get("content_type", "application/json")
    if "generate" in d:
        g = d["generate"]
        if g["type"] == "huge_body":
            n = int(g.get("approx_bytes", opts.huge_body_bytes))
            # F12: the body must be VALID (own AND enemy both shaped and
            # above MIN_TROOPS) so the ONLY possible rejection reason is raw
            # size — padding rides in an extra, otherwise-ignored top-level
            # field. The old generator omitted "enemy" entirely, so every
            # run 400'd on below_min_troops and never touched the size limit
            # at all (false E6 evidence — see docstring at module top).
            base = predict_body(troops=10_000)
            base["pad"] = "A" * n
            return {"content": json.dumps(base).encode(),
                    "headers": {"Content-Type": ct}}
        raise ValueError(f"unknown generator: {g['type']}")
    if "raw_body" in d:
        return {"content": d["raw_body"].encode("utf-8", "replace"),
                "headers": {"Content-Type": ct}}
    return {"json": d.get("body")}


def probe_adversarial(client, opts, descriptor: dict) -> ProbeResult:
    name = f"adv_{descriptor['name']}"
    lo = int(descriptor.get("expected_status_min", 400))
    hi = int(descriptor.get("expected_status_max", 499))
    headers = dict(DEV_HEADERS) if opts.dev_bypass else {}
    kw = _materialize_body(descriptor, opts)
    hdr = kw.pop("headers", {})
    headers.update(hdr)
    r, err = _req(client, descriptor.get("method", "POST"),
                  descriptor.get("path", "/api/predict"),
                  headers=headers or None, timeout=opts.timeout, **kw)
    if err:
        return ProbeResult(name, "B2/E2", f"{lo}-{hi}, never 5xx", err, "FAIL",
                           "no clean HTTP error (hang/crash?)")
    if r.status_code >= 500:
        return ProbeResult(name, "B2/E2", f"{lo}-{hi}, never 5xx",
                           str(r.status_code), "FAIL",
                           f"SERVER 5xx on adversarial input: {_body_snip(r)}")
    ok = lo <= r.status_code <= hi
    return ProbeResult(name, "B2/E2", f"{lo}-{hi}, never 5xx",
                       str(r.status_code), "PASS" if ok else "FAIL",
                       descriptor.get("description", "") if ok else _body_snip(r))


# ---------------------------------------------------------------- entry points

def run_probes(client: httpx.Client, opts: ProbeOptions) -> list[ProbeResult]:
    """Full suite against an injected httpx.Client (testable keyless via
    httpx.ASGITransport). Order (F12, see module docstring):
      1. health first — abort early if unreachable.
      2. auth/min-troops/paywall/docs/webhook probes — none of these ever
         reach limits.py's burst-accounting step (denied earlier, or an
         unmetered path), so they carry no ordering constraint.
      3. the three /shell/ocr/panel probes that DO pass the paywall (pro
         headers) — each is allowed-and-recorded by LimitsMiddleware before
         its own route-level guard fires, so up to 3 slots of the shared
         burst budget are gone after this point.
      4. a burst-window reset sleep (dev_bypass only — see ProbeOptions).
      5. the adversarial block — freshly budgeted, so every payload reports
         its own true status instead of an inherited 429.
      6. probe_burst LAST — it deliberately exhausts the window with 8 rapid
         requests; "at least one 429 among 8" holds regardless of whatever
         budget is already spent, so nothing needs to run after it.
    """
    results = [probe_health(client, opts)]
    if results[0].status == "FAIL" and "Error" in results[0].observed:
        results[0].notes = "base unreachable — remaining probes aborted"
        return results
    results.append(probe_anonymous_predict(client, opts))
    results.append(probe_min_troops(client, opts))
    results.append(probe_free_plan_ocr(client, opts))
    results.append(probe_docs_endpoints_closed(client, opts))
    results.append(probe_invalid_webhook_signature(client, opts))
    results.append(probe_ocr_panel_free_tier(client, opts))
    results.append(probe_ocr_panel_oversize(client, opts))
    results.append(probe_ocr_panel_sniff(client, opts))
    results.append(probe_ocr_panel_mock_200(client, opts))
    if opts.dev_bypass and opts.burst_reset_sleep_s > 0:
        time.sleep(opts.burst_reset_sleep_s)
    for d in load_payload_descriptors():
        results.append(probe_adversarial(client, opts, d))
    results.append(probe_burst(client, opts))
    return results


def render_markdown(results: list[ProbeResult], base: str) -> str:
    lines = [
        "## Staging probe evidence",
        "",
        f"Base URL: `{base}` · {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        "| Probe | Criteria | Expected | Observed | Result | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r.name} | {r.criteria} | {r.expected} | "
                     f"{r.observed} | **{r.status}** | {r.notes} |")
    n_fail = sum(1 for r in results if r.status == "FAIL")
    n_skip = sum(1 for r in results if r.status == "SKIP")
    lines += ["", f"**{len(results)} probes · "
                  f"{len(results) - n_fail - n_skip} PASS · "
                  f"{n_fail} FAIL · {n_skip} SKIP**", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True,
                    help="base URL, e.g. https://staging.wostests.com")
    ap.add_argument("--dev-bypass", action="store_true",
                    help="send DEV_BYPASS mock-identity headers")
    ap.add_argument("--burst-count", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--burst-reset-sleep", type=float, default=61.0,
                    help="seconds to sleep past the sliding 60s burst window "
                    "before the adversarial block, so probes unrelated to "
                    "rate-limiting don't inherit a false 429 (F12); pass 0 "
                    "to disable (e.g. a target with a very high "
                    "BURST_PER_MIN where contamination cannot occur)")
    ap.add_argument("--out", type=Path, default=None,
                    help="also write the markdown table to this file")
    args = ap.parse_args(argv)

    opts = ProbeOptions(dev_bypass=args.dev_bypass,
                        burst_count=args.burst_count, timeout=args.timeout,
                        burst_reset_sleep_s=args.burst_reset_sleep)
    with httpx.Client(base_url=args.base, follow_redirects=False) as client:
        results = run_probes(client, opts)
    md = render_markdown(results, args.base)
    print(md)
    if args.out:
        args.out.write_text(md, encoding="utf-8")
    if results and results[0].status == "FAIL" and "abort" in results[0].notes:
        return 2
    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
