"""shell/probes/run_probes.py — staging probe suite for the production shell.

Implements PRODUCTION_PLAN.md §3 step 7 and gathers machine evidence for
PRODUCTION_CRITERIA.md items C1 (anonymous -> 401), D1 (MIN_TROOPS -> 400),
D2 (burst -> 429), C2/§2.4 (free-plan OCR -> 402/403), B2/E2 (adversarial
payloads -> clean 4xx, never 5xx), plus a /shell/health liveness check.

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
def predict_body(troops: int = 10_000) -> dict:
    def side(role):
        return {
            "label": f"probe-{role}", "role": role, "troops_total": troops,
            "formation": {"Infantry": 0.5, "Lancer": 0.2, "Marksman": 0.3},
            "quality": {c: {"tier": 10, "fc": 0, "t12_stack": 0}
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
            filler = "A" * n
            return {"content": ('{"own":{"troops_total":10000,"pad":"%s"}}'
                                % filler).encode(),
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
    httpx.ASGITransport). Order: health first (abort early if unreachable)."""
    results = [probe_health(client, opts)]
    if results[0].status == "FAIL" and "Error" in results[0].observed:
        results[0].notes = "base unreachable — remaining probes aborted"
        return results
    results.append(probe_anonymous_predict(client, opts))
    results.append(probe_min_troops(client, opts))
    results.append(probe_burst(client, opts))
    results.append(probe_free_plan_ocr(client, opts))
    for d in load_payload_descriptors():
        results.append(probe_adversarial(client, opts, d))
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
    ap.add_argument("--out", type=Path, default=None,
                    help="also write the markdown table to this file")
    args = ap.parse_args(argv)

    opts = ProbeOptions(dev_bypass=args.dev_bypass,
                        burst_count=args.burst_count, timeout=args.timeout)
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
