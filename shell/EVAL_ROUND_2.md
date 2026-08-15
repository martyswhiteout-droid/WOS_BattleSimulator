# EVAL_ROUND_2 — independent re-evaluation of the fix round

**Evaluator:** independent QA agent (fresh, did not write any of the fix-round code)
**Date:** 2026-08-15
**Branch:** `shell-fix-round2` @ `adbf6bc0b8c564a0d3228f43fddec97eb6f3827b`
**Scope:** the four merged fix-round branches (agents A/B/C/D, `MORNING_BRIEF.md` §Resume) evaluated against
`shell/EVAL_ROUND_1.md`'s 5 Criticals + 15 Majors, `shell/ARCHITECTURE.md`, `PRODUCTION_CRITERIA.md`.
**Method:** evidence only, adversarial. Five live keyless uvicorn deployments (dev / staging+bypass /
staging+real-auth / staging+webhook-secret / a byte-for-byte simulated Docker image), the full `shell/tests`
suite on Python 3.12.13, the 13-file Node client suite, the UI style guard, `promote.py --dry-run`, and the
probe suite run against a live server. No builder or predecessor claim was accepted without reproducing it.

---

# VERDICT: **NOT APPROVED — 3 Critical, 6 Major**

All 5 of round 1's named Criticals (F1–F5) are genuinely, robustly fixed — each verified live, including one
(F1) reproduced in a byte-for-byte simulated Docker image. That is a real result and the fix-round agents
should get credit for it. But round 2 exists specifically to catch what happens when four independently-fixed
parallel branches meet each other, and adversarial testing of the *integrated* tree found three new
Critical-severity defects that only exist because of how the fixes interact, plus confirmed that four of round
1's Majors were never assigned to anyone this round and remain exactly as broken as before, plus one new
instance of the exact "probe suite reports a false result" failure class F12 was supposed to close.

---

## 1. The 5 named Criticals — all CLOSED, verified live

| # | Round-1 finding | Verdict | Evidence |
|---|---|---|---|
| F1 | OCR dead in every deployable artifact (Dockerfile/promote omit `.claude/`) | **FIXED** | `shell/Dockerfile:28` now `COPY .claude/skills/wos-battlereport-ingestion/ ...`. `shell/promote.py`'s `step1_checkout`/`step3_assemble` archive the same path; new `gate_ingestion_skill` (promote.py:453) asserts the validator + schema files exist inside the bundle. **Live-reproduced**: robocopied the exact Dockerfile `COPY` set (`wos_sim/`, `prototype/`, `shell/`, `.claude/skills/wos-battlereport-ingestion/` — nothing else, confirmed by directory listing) into `shell/tmp_eval2/docker_sim/`, booted `uvicorn` from it on :8236, `POST /shell/ocr` → **200**, real profile extracted. `promote.py --dry-run` (`shell/tmp_eval2/promote_dryrun.log`) → step 4 `ingestion skill bundle (EVAL F1): clean`. |
| F2 | OCR cache hit 500s (`job_id`/`id` KeyError) | **FIXED** | `shell/app/ocr/cache.py:95` `DbOcrJobs.get_by_hash` now `row.setdefault("job_id", row.get("id"))`; `extract.py:438` has a second, independent defense (`cached.get("job_id") or cached.get("id")`). New regression tests wire the **real** store (`test_ocr_router.py::test_cache_hit_via_real_db_store_no_key_mismatch`, `..._preserves_failed_result` — exactly the "tests must use the app's REAL store" lesson). **Live-reproduced**: same PNG uploaded twice to `/shell/ocr` on :8231 → 200/200, second response `cached:true`, `job_id` identical both times. |
| F3 | Verified Pro users served hardcoded `plan="free"` | **FIXED** | `shell/app/auth.py:168-186` `_resolve_plan_for` — lazy-imported, wrapped in try/except, defaults to `"free"` on any failure, called from `_verify()` (real-JWT path, `auth.py:223`) — never from the DEV_BYPASS branch (confirmed by reading `auth.py:230-241`: the bypass branch reads only the `X-Dev-Plan` header, no call to `_resolve_plan_for`). `billing/entitlements.py:resolve_plan` is cached (30 s TTL), invalidated by `webhook.py` on every subscription write (`invalidate_plan_cache(user_id)` after `checkout.session.completed`/`.updated`/`.deleted`), and never raises. **Cross-agent contract verified in the integrated tree**: `test_auth_middleware.py::test_verified_session_resolves_real_plan_from_subscription` constructs a real RS256 JWT, verifies it through a real JWKS round-trip, writes a subscription via `db.apply_subscription_update`, and asserts `GET /shell/me` returns `plan:"pro"` — this is Agent A's auth.py genuinely calling into Agent B's billing/db stack, not a stub. Companion tests cover failure-degrades-to-free and dev-bypass-never-calls-resolve_plan. All pass. |
| F4 | No body cap, no `max_runs` enforcement | **FIXED** (see also new Critical C1 below) | `limits.py:175-195` `_clamp_runs` silently reduces `n` to `entitlements.max_runs` and returns it via `Allowed.body`; `LimitsMiddleware` (the module actually wired by `main.py`, confirmed — `_their_mw = getattr(_limits, "LimitsMiddleware", ...)` wins whenever importable) forwards the clamped body downstream. **Live-reproduced**: `n:20000` request on :8231 → forecast response `"n":1000`. `BodyLimitMiddleware` (`main.py:172-236`) is outermost, checks `Content-Length` before buffering, 413s over `MAX_BODY_BYTES` (256 KiB default) — **live**: 2 MiB `/api/predict` body → 413 (probe `adv_huge_body`). App-level OCR-aware split confirmed (see §3). |
| F5 | `/docs`,`/redoc`,`/openapi.json` open in staging | **FIXED** | `main.py`'s `DocsGuardMiddleware` (outermost-3) 404s the three paths whenever `settings.is_prodlike`, regardless of `dev_bypass`; shell's own FastAPI instance already had `docs_url=None` etc. **Live-reproduced** on :8233 (`ENV=staging DEV_BYPASS=0`): `/docs`→404, `/redoc`→404, `/openapi.json`→404. The static `gate_debug_endpoints` grep (which round 1 correctly noted can never see FastAPI auto-docs) is now backed by a genuine **active runtime probe**, `probe_docs_endpoints_closed` (`probes/run_probes.py:216`), wired into `run_probes()` and therefore into `promote.py`'s `step7_probes` gate whenever a real base URL is probed. |

**Honesty invariant (COMPASS #3) — re-verified, still airtight.** Same near-even mirror predict body posted to
:8231 (dev) and :8232 (staging+bypass): `verdict` block byte-identical (`win.p:0.55` both), `engine` block
byte-identical including `near_even:true`, `confidence:"coin_flip"`, `model_error:0.5`, the note text.
`kill_matrix` absent from staging's `battle_timeline`. `skill_telemetry` correctly *differs* — staging
collapses each skill's full 12-bin `triggers`/`kills` histograms to `{"fired": 4, "kills": 0}` (F7), dev keeps
the full distribution. No path was added, no path was silently dropped outside the documented set. This
invariant held under adversarial re-testing; it is not one of this round's findings.

---

## 2. Live e2e — dev mode (`DEV_BYPASS=1 ENV=dev`, :8231)

| Check | Observed | Verdict |
|---|---|---|
| `GET /shell/health` | `sim_mounted:true` | PASS |
| `GET /` overlay injected exactly once, disk `prototype/index.html` has 0 refs | 266 434 B served, `shell/overlay.js`×1, disk×0 | PASS |
| Overlay serves `ocr_flow.js`×1, `ocr_flow.css`×1, disclaimer text present in `overlay.js` | confirmed | PASS |
| `/shell/me` X-Dev-Plan pro/free | pro→100 sims/30 ocr, free→5/0 | PASS |
| `POST /api/predict` real round-trip | 200, full forecast (`verdict`,`engine`,…) | PASS |
| Runs clamp `n:20000` | 200, response `"n":1000` | PASS |
| `POST /shell/billing/checkout` | mock URL, `mock:true` | PASS |
| `POST /shell/ocr` same image twice | 200/200, `cached:true` 2nd time, same `job_id` | PASS |
| `POST /shell/ocr` free plan | 402 `payment_required` | PASS |
| `POST /shell/signout` | 200; `Set-Cookie: __session=""; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=lax` | PASS |
| `/shell/ocr/panel` free tier | 402 | PASS |
| `/shell/ocr/panel` pro + real fixture `C_battle_3.png` (747 KB) | 200, `source:"engine"`, `specials_observed:"none"` | PASS |
| `/shell/ocr/panel` pro + real fixture `C_battle_4.png` (433 KB) | 200, `source:"engine"`, `specials_observed:"read"` | PASS |
| `/shell/ocr/panel` pro + largest fixture `C_battle_1.png` (1.62 MB) | 200 (app-level cap correctly allows it) | PASS |
| dev-mode CORS unaffected (not accidentally locked) | `OPTIONS` evil origin → `ACAO:*` | PASS |

All real-fixture OCR-panel reads went through the actual RapidOCR engine (`source:"engine"`, not the token
mock) — zero Gemini/Anthropic calls made (no `GEMINI_API_KEY`; `_gemini_gap_fill` skips cleanly with
`"GEMINI_API_KEY not configured"`).

## 3. Live e2e — staging mode

| Check | Server | Observed | Verdict |
|---|---|---|---|
| `IP_HASH_SALT` empty + `ENV=staging` → **fail-fast at boot** | one-shot `uvicorn` boot | Exit 1, `RuntimeError: IP_HASH_SALT is empty while ENV='staging' … refusing to boot` (raised from `main.py:373`, at **import time** since `app = create_app()` is module-level) | PASS |
| Same, with `IP_HASH_SALT` set | :8232, :8233, :8235 | boot to 200 `/shell/health` | PASS |
| `verdict`/`engine` byte-identical dev vs staging; `skill_telemetry` summarized; `kill_matrix` stripped | :8231 vs :8232 | see §1 honesty-invariant row | PASS |
| Anonymous `GET /` with **no** `Accept` header (F9) | :8233 real-auth | 307 → `sign-in?redirect_url=...` (not 200/full UI) | PASS |
| Same for `/index.html` | :8233 | 307 | PASS |
| Anonymous `POST /api/predict` | :8233 | 401 `auth_required` | PASS |
| 5× path-trick variants (`//`, trailing slash, case, `%2f..%2f`, `/../`) | :8233 | all 401 | PASS |
| `/docs`,`/redoc`,`/openapi.json` | :8233 | 404/404/404 | PASS |
| `OPTIONS /api/predict`, `Origin: evil.example` (F14) | :8233 | 200 but **`access-control-allow-origin` absent** | PASS |
| `OPTIONS /api/predict`, `Origin` = configured `BASE_URL` | :8233 | 200, `ACAO` = that origin (correctly allowed) | PASS |
| Old alias `GET /shell/billing/webhook` | :8233 | 401 (not silently 200/accepted — route isn't registered at all) | PASS |
| `POST /shell/webhook/stripe`, unsigned, no secret, `ENV≠dev` | :8233 | 503 `webhook secret not configured` | PASS |
| `POST /shell/webhook/stripe`, **bad signature**, secret configured | :8235 (env-var-driven `STRIPE_WEBHOOK_SECRET`) | 400 `invalid signature` | PASS |
| `POST /shell/webhook/stripe`, **missing** `Stripe-Signature` header, secret configured | :8235 | 400 `missing signature` | PASS |
| `GET /shell/webhook/stripe` | :8235 | 404 (POST-only route) | PASS |

**Caveat on methodology (not a product bug):** an early attempt to test webhook signature verification via
`create_app(Settings(STRIPE_WEBHOOK_SECRET=...))` (constructing a `Settings` object directly, in-process)
produced a false "unsigned accepted" result — `shell/app/billing/webhook.py` and `_contracts.py` read the
**environment** via their own `get_settings()`, not whatever object was passed to `create_app()`. Re-tested
correctly with real env vars on a real `uvicorn` boot (:8235) and got the expected 400/400. This divergence
between "the `Settings` object `create_app()` was called with" and "the `Settings` object Agent B's billing
code actually reads" is real but **not reachable in production** — `main.py`'s module-level `app =
create_app()` never passes an explicit object, so both paths always read the same single environment. Noting
it only so a future test-writer doesn't repeat the mistake (see Minor finding M-Settings below).

---

## 4. Suites

| Suite | Command | Result |
|---|---|---|
| Shell tests | `python -m pytest shell/tests -q` (Python 3.12.13, keyless) | **480 passed**, 0 failed, 0 skipped |
| UI style guard | `python -m pytest wos_sim/predictor/tests/test_ui_style_guard.py -q` | **7 passed** |
| Node OCR client (13 files, exact list from `docs/OCR_TEST_INSTRUCTIONS.md` §8) | `node --test <13 files>` | **150 tests, 149 pass, 1 skipped, 0 fail** — file inventory on disk matches the doc's list exactly (13/13, no stragglers) |
| `promote.py --dry-run` | `python shell/promote.py --tag release-eval-round2-dryrun --target staging --dry-run` | Exit 0. Step 2 (real subprocess pytest/regression/backtest) ran and passed: `709 passed, 2 xfailed`, backtest `7/13` (unchanged baseline). Step 4 static gates: **all clean**, including the new ingestion-skill gate. |
| `git status` in worktree | `git status --porcelain` | Clean throughout (only gitignored `*.log` / `shell/build/` / `shell/tmp_eval2/` artifacts from this evaluation) |

---

## 5. Findings

Severity per the brief: **CRITICAL** = wrong/absent security or money/quota behavior, honesty-invariant
violation, broken shipped feature. **MAJOR** = functional break on a supported path or a gate that lies.
**MINOR** = note.

---

### C1 · CRITICAL · Caddy's edge body cap still blocks real OCR uploads — the F4 fix never reached the Caddyfile

`shell/Caddyfile` (both the `wostests.com` and `staging.wostests.com` blocks, lines 19–21 / 33–35) sets a
single, path-unscoped cap:

```
request_body {
    max_size 256KB
}
```

This directive applies to **every** request to the site (no matcher). `shell/app/main.py`'s
`BodyLimitMiddleware` — the fix this same round shipped for F4 — deliberately gives `/shell/ocr` and
`/shell/ocr/panel` a **much larger** allowance (`MAX_OCR_BODY_BYTES = 8*1024*1024 + 65536` ≈ 8.06 MB, chosen to
exactly match `panel_router.py`'s own `MAX_REQUEST_BYTES`), specifically because commit `4ca8566` self-caught
that a uniform 256 KiB cap "was about to break real OCR uploads." That fix landed **only in the app layer**.
The Caddyfile — the mandatory front door in the real topology — was never updated to match.

`docker-compose.yml` confirms Caddy is not optional: the `app` service only `expose`s port 8200 (container-network-only); only `caddy` publishes `80`/`443` to the host. Every real request, staging or prod, passes
through Caddy's 256 KiB cap **before** it ever reaches the app's own correct, OCR-aware 8.06 MB cap.

**Reproduction (static + cross-checked against real fixture sizes):**
```
shell/tests/fixtures/panel_ocr/images/C_battle_1.png   1 624 899 B  (1.6 MB)
shell/tests/fixtures/panel_ocr/images/C_battle_2.png   1 289 300 B
shell/tests/fixtures/panel_ocr/images/C_battle_3.png     765 384 B   <- this round's own e2e fixture
shell/tests/fixtures/panel_ocr/images/C_battle_4.png     443 173 B   <- this round's own e2e fixture
shell/tests/fixtures/panel_ocr/images/C_citystats_1.png   530 484 B
shell/tests/fixtures/panel_ocr/images/C_scout.png       1 008 885 B
shell/tests/fixtures/panel_ocr/images/C_citystats_2.png    67 929 B  (the only one under 256 KB)
```
6 of the 7 real screenshot fixtures — including both fixtures this evaluation was told to use for the
happy-path check, and every one over ~260 KB — exceed Caddy's cap. I confirmed live (§2 table) that the app
itself correctly accepts `C_battle_1.png` (1.62 MB, the largest) through `BodyLimitMiddleware`; in the real
Caddy-fronted deployment this exact request would 413 at the edge before reaching that code. I could not run
Caddy directly in this sandbox (no Docker daemon running, no standalone `caddy` binary on PATH) to capture a
literal HTTP 413 from Caddy itself, so this is a high-confidence **static-inspection** finding (Caddy's
`request_body{max_size}` directive is well-documented to reject any body exceeding the configured size with a
413, and nothing in the Caddyfile scopes it away from the OCR paths) rather than a directly-observed live
Caddy response — flagging that distinction rather than overclaiming it.

**Why Critical:** this breaks the shipped, already-QA'd OCR panel feature (explicit Critical criterion) in the
only topology a real user ever reaches, and it is the exact same defect class (uniform body cap vs.
variable-size legitimate uploads) the round already self-identified and fixed once — just at the wrong layer.

**Suggested fix:** scope the Caddy cap with a path matcher, e.g.
```
@ocr path /shell/ocr /shell/ocr/panel
request_body @ocr {
    max_size 8456KB
}
request_body {
    max_size 256KB
}
```
and add a probe/gate that gets the actual Caddy config into the loop (today nothing exercises the Caddyfile at
all — every probe in `run_probes.py` targets the app directly).

---

### C2 · CRITICAL · `/shell/ocr` burns 2 quota units per upload and trips burst at half the documented rate — the F21 fix collides with the live `LimitsMiddleware`

`shell/app/ocr/router.py:70-71` (Agent C's F21 fix, this round) now correctly calls
`check_and_record(user, "/shell/ocr", None, _ip_hash(request))` — round 1 found the *old* string `"ocr"`
made this call dead code, and the fix for that is textually correct. But `main.py`'s `create_app()` wires
Agent B's own `limits.LimitsMiddleware` as the app-wide limits layer whenever it is importable — which it
always is in this integrated tree — and `LimitsMiddleware._metered()` (`limits.py:325-329`) already matches
`/shell/ocr` (`classify_endpoint("/shell/ocr") == "ocr"`) and already calls `check_and_record` itself
(`limits.py:402`) for every such request, **before** it ever reaches the router.

The two call sites are both live simultaneously. Every `/shell/ocr` request that reaches the route handler has
therefore already been recorded once by the middleware; the router's own (now-live) call records it **again**.
`panel_router.py` deliberately does **not** duplicate this call — its own docstring says so explicitly
("Plan gating is NOT done here... Both OCR endpoints are metered by LimitsMiddleware... a second in-route
plan check could only ever disagree with it") — which is exactly correct, and exactly what `/shell/ocr`'s
handler should also do but no longer does.

**Live reproduction** (fresh account, 6 sequential uploads of 6 *different* images — rules out any cache-hit
interaction — default `BURST_PER_MIN=5`):
```
0 200  (1st successful upload)
1 200  (2nd successful upload)
2 429 {"error":"burst","message":"Slow down: at most 5 requests per minute."}
3 429 {"error":"burst", ...}
4 429 {"error":"burst", ...}
5 429 {"error":"burst", ...}
```
A budget documented and tested (in isolation, without the real middleware wired) as "5 requests/minute" is
**2** in the integrated app. The same doubling applies to the daily quota: a Pro user's paid 30 OCR/day
(`daily_ocr_quota`) becomes ~15 real uploads/day. This was not caught by Agent C's own regression suite
because `test_ocr_router.py::build_client()` constructs a bare `FastAPI()` with only `app.include_router(
ocr_router)` plus a fake-auth stand-in — it never wires `limits.LimitsMiddleware`, so the router's F21 fix was
only ever tested with the middleware **absent**, never with both layers present as they are in the real,
merged `shell.app.main:app`.

**Why Critical:** wrong money/quota behavior, live-confirmed, on a paid feature.

**Suggested fix:** delete the redundant call in `router.py` (mirror `panel_router.py`'s approach — one
metering layer, `LimitsMiddleware`, full stop) and add an integration test that boots `create_app()` (not a
bare router-only app) and asserts N successful `/shell/ocr` uploads consume exactly N quota units / N
burst-window slots.

---

### C3 · CRITICAL · `POST /api/predict` crashes with an unhandled 500 on a malformed `panel` key — previously masked by F12, now exposed by the F12 fix

`wos_sim/predictor/serialize.py:18`:
```python
for k, v in (d.get("panel") or {}).items():
    cls, stat = k.split("|")     # <- ValueError if k has 0 or >=2 "|" characters
```
`shell/probes/payloads/bad_panel_key.json` sends exactly this shape (`"panel": {"no-pipe-here": 1.0}`).

**Live reproduction:**
```
POST /api/predict  body = bad_panel_key.json's body, X-Dev-Plan: pro
-> HTTP 500, body: "Internal Server Error" (generic Starlette handler — no stack trace or
   path info leaked to the client)
```
Server-side traceback (`shell/tmp_eval2/dev_server.log`) confirms the exact line:
`ValueError: not enough values to unpack (expected 2, got 1)` at `serialize.py:18`, reached through
`shell/app/main.py` → `auth.py` → `limits.py` → `minimize.py` → `overlay/middleware.py` → the mounted
`wos_sim.predictor.server:app`'s `predict()` handler.

This is not a new regression in this fix round's own code — it is a pre-existing gap in `wos_sim` (read-only
from the shell's side per `ARCHITECTURE.md` boundary rule 1) that **round 1 never actually observed**: round
1's own evidence for this exact payload was `adv_bad_panel_key → 429, FAIL — burst-window contamination, not
a payload result` (`EVAL_ROUND_1.md` §3e) — the F12 burst bug meant the probe never got far enough to see the
payload's *true* response. Agent D's F12 fix (reordering `probe_burst` to run last, adding the reset sleep)
is exactly what makes this payload's real behavior observable for the first time, and what it reveals is a
crash, not a clean 4xx.

**Live evidence, probe suite against :8231** (`shell/tmp_eval2/probe_report_dev.md`):
```
| adv_bad_panel_key | B2/E2 | 400-422, never 5xx | 500 | **FAIL** | SERVER 5xx on adversarial input |
```

**Why Critical:** `PRODUCTION_CRITERIA` B2/E2 ("adversarial payloads... never 5xx") is an explicit release gate
on the shell's own criteria table; this is the shell's public predict endpoint (the core product), the crash
is 100%-reproducible with a single crafted request from any authenticated (including free-tier) account, and
it burns one of that user's daily quota units for a request that does nothing but crash (`limits.py` records
usage before the engine runs).

**Suggested fix:** since `wos_sim/` cannot be edited from `shell/` (boundary rule 1), the fix has to live on
the shell side — either (a) validate `panel` key shape (`"Class|Stat"`, class ∈ the known set) before
forwarding the body to the mounted engine, returning a clean 400, or (b) wrap the mounted app's route calls in
an exception-to-JSON boundary that turns any uncaught `ValueError`/`KeyError` from the engine into a 400/422
instead of letting it become an unhandled 500. Also worth a companion check for other unguarded `.split("|")`
/ dict-key-shape assumptions in `serialize.py` reachable the same way (not audited exhaustively here — this
report only confirms the one payload the existing adversarial suite already carries).

---

### M1 · MAJOR (carried over, unfixed) · Quota meter shown to users is still always full — round 1's F13

`shell/app/main.py:396-398` still carries the exact stale comment: *"TODO(Agent B): subtract today's
usage_events once db.py exposes a usage query; until then 'remaining' reports the full daily quota."*
`db.get_usage_today` has existed since before round 1 and is used elsewhere (`limits.py:256`). Not assigned to
anyone in `MORNING_BRIEF.md`'s §Resume fix-round briefs (neither Agent A's nor Agent B's bullet list mentions
F13), so it is unsurprising it's still open — but it is still open.

**Live reproduction:** fresh account, `X-Dev-Plan: pro`. `/shell/me` → `remaining.sims:100`. Three successful
`POST /api/predict` calls. `/shell/me` again → **still `remaining.sims:100`**.

This is round 1's own severity call (MAJOR) and nothing here changes that — but per the round-2 mandate
("verify each Critical/Major is genuinely closed... not just in isolation") it is not closed, and the mandate
requires zero Majors for approval.

---

### M2 · MAJOR (carried over, unfixed) · JWKS fetch failure has no negative-cache backoff — round 1's F16

`shell/app/auth.py:113-123` `JWKSCache.key_for` is byte-for-byte unchanged from round 1: the `or not
self._keys` clause still bypasses `min_refresh_s`, so a Clerk outage (or any JWKS fetch failure) after a fresh
process start means **every** authenticated request triggers a fresh 5 s `httpx` fetch, forever, with no
backoff and no lock against a thundering herd. Not assigned this round.

---

### M3 · MAJOR (carried over, unfixed) · `assets_prod/` still never served or mapped — round 1's F18

`grep -rn assets_prod shell/app/` → **zero matches**, same as round 1. The 22-SVG replacement pack Agent D
built exists on disk and is never mounted; nothing maps the prototype's hero-name → emblem paths onto it.
Not assigned this round.

---

### M4 · MAJOR (carried over, unfixed) · Sweep detection still never scheduled — round 1's F19

`grep -rn sweep_scan shell/` outside its own definition/tests/config-comment → nothing calls it. No cron, no
`docker-compose` sidecar, no in-app scheduled task. `PRODUCTION_CRITERIA` D3 remains un-satisfiable in the
current build. Not assigned this round.

---

### M5 · MAJOR · New probe-suite self-contamination: `adv_absurd_n` false-FAILs against the F4-b clamp it was never told about

`shell/probes/payloads/absurd_n.json` (`n: 10,000,000`) still expects `expected_status_min/max: 400/429` —
unchanged by Agent D's F12 fix-round commit (which only touched this file to fix the unrelated `fc:0→1` bug).
Agent B's F4-b runs list (`shell/app/limits.py:_clamp_runs`) never rejects an oversized `n` — it silently
clamps to `entitlements.max_runs` and returns 200. The two fix-round branches were developed in true parallel
(both branch from the same pre-fix-round base commit) and were never reconciled against each other.

**Live reproduction, probe suite against :8231:**
```
| adv_absurd_n | B2/E2 | 400-429, never 5xx | 200 | **FAIL** | {"n":1000,"engine":{...
```
The observed 200 is the *correct*, intended F4-b behavior (silently clamped and answered, not rejected) — the
probe's expectation is simply stale. This is the identical failure class F12 itself was about
("`EVAL_ROUND_1.md` F12... The suite's verdict is a coin flip... A gate that certifies a violated criterion is
worse than no gate" / here: a gate that *fails* satisfied criteria is equally worth fixing, since it corrupts
the same evidence trail `promote.py`'s `step7_probes` gate relies on) — reopened by a cross-agent reconciliation
gap rather than by the original root cause.

**Suggested fix:** update `absurd_n.json`'s `expected_status_min/max` to `200` (or add a "clamped, not
rejected" comment + assert `n` was actually reduced in the response body, which is the more meaningful check),
and add a step to future fix-round coordination that re-diffs *all* probe payload expectations against
whatever runs-clamp / limits changes landed in parallel.

---

### Minor findings

**Mn1 · MINOR · `probe_ocr_panel_mock_200` false-FAILs against any `--dev-bypass` target that doesn't also have
`OCR_PANEL_MOCK=1` set.** The probe's own docstring says it should SKIP "when the target isn't configured for
it," but its actual guard only checks `opts.dev_bypass` (the CLI flag), not whether the target server actually
has the mock flag enabled — an entirely realistic mismatch (my own :8231 dev-bypass server is a live example:
`DEV_BYPASS=1` but no `OCR_PANEL_MOCK` env var). Live: 422 `unreadable_tokens` (the real engine correctly
rejecting a synthetic non-image) reported as FAIL rather than SKIP. Low blast radius — it exercises an opt-in
dev convenience path, not a security/money control — so kept Minor rather than folded into M5, but it is the
same root problem (probe assumptions about the target's exact configuration) and should be fixed alongside it
(e.g., treat 422/`unreadable_tokens` the same as the existing 503 SKIP branch).

**Mn2 · MINOR · `shell.app.billing._contracts.get_settings()` / `shell.app.config.get_settings()` both read only
from `os.environ`/`.env`, ignoring any `Settings` object explicitly passed to `create_app(settings=...)`.**
Discovered via my own test methodology (see §3 caveat) — not reachable in real deployment, since
`main.py`'s module-level `app = create_app()` never passes an explicit object and both settings sources
therefore always agree on one process's environment. Noted so a future test author doesn't lose time on the
same false lead; not scored against the round.

**Mn3 · MINOR · `SKILL_INGESTION_DIR` is not a declared `config.py` field**, so it can only be overridden via a
real process environment variable, never via `shell/.env` (pydantic-settings' `env_file` loader drops unknown
keys under `extra="ignore"`, and this key is read straight from `os.environ` by `_shims.resolve_skill_dir`,
bypassing the `.env`-parsed `Settings` object entirely). Does not affect the default resolution path — which
is what F1 actually requires and is what ships — only the escape hatch for relocating the skill directory.

**Mn4 · MINOR · `promote.py`'s assembled scp/VPS bundle (distinct from the Docker image) still excludes
`shell/tests/`** (`BUNDLE_EXCLUDE_DIRS`), so `MockVision`'s `FIXTURE_DIR` (`shell/tests/fixtures/ocr/`) would
be missing if that deployment path is ever used with the default `OCR_MOCK=1` left on. The Docker path
(`docker-compose.yml`, the apparent primary mechanism, confirmed by the presence of a healthcheck, restart
policy, and TLS-terminating Caddy sidecar) is unaffected — its `Dockerfile` does an unconditional `COPY
shell/ shell/`, tests included. Only bites a secondary deploy path combined with a non-default-for-production
config value.

---

## 6. Round-1 items not re-litigated here (confirmed fixed, brief evidence only)

- **F6** signout: `POST /shell/signout` now exists, clears `__session` server-side with
  `Max-Age=0; HttpOnly; Secure; SameSite=lax` (live-confirmed §2), best-effort Clerk session revoke when a
  secret is configured.
- **F7** `skill_telemetry` leak: summarized to `fired`/`kills` scalars in staging/prod (live-confirmed §1);
  verdict/engine/coin_flip untouched.
- **F8** disclaimer: rendered verbatim in `overlay.js`, matches `shell/legal/disclaimer.md`'s canonical
  paragraph exactly, links to `/legal/tos` and `/legal/privacy` (both served, live-confirmed).
- **F9** Accept-header bypass: closed (live-confirmed §2 — 307 regardless of `Accept`).
- **F10** webhook dual-path trap: only one route registered now, `THIRD_PARTY_SETUP.md` corrected, regression
  test asserts the registered route set ⊆ `auth.EXEMPT_PATHS`.
- **F11** unsalted IP hash: `IP_HASH_SALT` now a declared config key, fail-fast on empty value in
  staging/prod (live-confirmed §3, both the direct `create_app()` call and a real `uvicorn` boot crash).
- **F12** probe self-contamination (original two root causes — burst ordering, `huge_body`'s missing `enemy`
  key): both fixed as designed. (New, different self-contamination instances found this round: M5, Mn1.)
- **F14** CORS/HSTS: `CorsLockMiddleware` strips/rewrites ACAO outside dev, live-confirmed both the deny case
  (evil origin → no ACAO) and the allow case (configured origin → ACAO reflects it); HSTS + security headers
  present in `Caddyfile` (static-inspection only, Caddy not runnable in this sandbox — see C1 for the one real
  gap found in this file).
- **F15** unpinned requirements: `requirements.txt` now pins all 16 dependencies to exact versions; a fresh
  venv installed from it byte-for-byte and ran the full suite green.
- **F17** `shell/build/` not gitignored: now is (`.gitignore:22`), verified by `git check-ignore` against a
  file inside it; `.env.example` correctly negated (`!shell/.env.example`).
- **F20** `promote.py` step 1 mislabeling a working-tree fallback as PASS: now reports SKIP, live-confirmed via
  `promote.py --dry-run`'s own report (`H docs/tag: SKIP — ... NOT release-grade evidence for H2`).
- **F21** dead OCR quota gate: fixed (this is also the root of C2 above — the fix itself is correct in
  isolation, the bug is a *second*, independent metering layer being live at the same time).

---

## 7. What to fix first

1. **C2** — delete the redundant `check_and_record` call in `shell/app/ocr/router.py`; it is a one-line
   deletion plus a new create_app()-level integration test, and it is presently costing every real Pro
   customer half their paid OCR quota.
2. **C1** — scope the Caddy body cap to exempt `/shell/ocr*`; without it the OCR feature is dead in real
   deployment exactly as thoroughly as round 1's original F1, just for a different reason.
3. **C3** — validate or catch the `panel` dict shape before it reaches the mounted engine.
4. **M5 + Mn1** — reconcile probe expectations against the F4-b clamp and the OCR_PANEL_MOCK target-config
   assumption; these actively mislead `promote.py`'s gate report the way F12 did.
5. **M1, M2, M3, M4** — pick these up explicitly in the next coordination brief; none of them were assigned
   this round, all four are exactly as broken as `EVAL_ROUND_1.md` found them.

Then re-run: the full suite, the probe suite (expect all-PASS/SKIP once M5/Mn1 are fixed), the honesty-invariant
diff, and a real (or at minimum simulated) Caddy boot before the next gate report claims C1 closed.

---

## 8. Housekeeping note

Running `promote.py --dry-run` (§4, without `--skip-prototype-checks`) invoked `wos_sim.regression`/
`wos_sim.backtest` as subprocesses, which rewrote three `source_media` absolute-path strings in
`wos_sim/data/avatars/manifest.json` to reflect this worktree's own path (`E:\WOS\wt-fix2\...` in place of the
committed `E:\WOS\Battle Simulator\...`) — a cosmetic, checkout-path-dependent side effect of some asset-manifest
tooling, not data loss or a functional change. Reverted with `git checkout -- wos_sim/data/avatars/manifest.json`
before finishing; `git status --porcelain` is clean apart from this report and `shell/tmp_eval2/` scratch
artifacts. Flagging only so a future `promote.py --dry-run` run (in any checkout) isn't mistaken for an
accidental hand-edit of a read-only `wos_sim/` file.

---

*This document is an evaluation, not a Gate Report. It does not constitute the independent QA PASS required by
`PRODUCTION_CRITERIA.md` §I1, and nothing here authorises anything entering `E:\WOS\WOSTests.com`.*

---
---

# ROUND 2B — re-verification of the 9 fix commits

**Evaluator:** same agent, same worktree (`E:\WOS\wt-fix2`, `shell-fix-round2`), fresh adversarial pass over the
9 new commits.
**Date:** 2026-08-15 (same day, later commits: `ba2f2c1` … `cb8fe07`, on top of `adbf6bc`).
**Method:** for every finding, read the actual diff (not the commit message), then closed it out with the
strongest honest evidence available: a live re-measurement reproducing my original round-2 numbers where I had
one, the commit's own regression test where a live check would just re-derive the same fact, and a fresh
static check for the one item (C1) that can't be exercised without a running Caddy (none available in this
sandbox — no Docker daemon, no standalone `caddy` binary, same constraint as round 2).

## VERDICT (ROUND 2B): **APPROVED**

Zero Critical, zero Major remain open. All 3 Criticals and all 6 Majors from the NOT APPROVED verdict above are
closed, each with live or test-level evidence below — not just a diff read.

---

## Per-finding re-verification

| Finding | Fix commit | Verification method | Result |
|---|---|---|---|
| **C1** — Caddy edge cap blocked OCR uploads | `d536a77` | Static: `shell/Caddyfile` now splits `request_body` into an `@ocr_upload path /shell/ocr /shell/ocr/panel` block (`max_size 8454144`) and a complementary `@default_body not path ...` block (`max_size 256KB`). `8454144` cross-checked byte-for-byte against `Settings.MAX_OCR_BODY_BYTES` (`8*1024*1024+65_536`) — computed independently, matches exactly. New `shell/tests/test_deploy_config.py` tests parse the Caddyfile with regex and assert the OCR cap is `>=` the live `Settings` value (not a hardcoded duplicate — would catch future drift) and that the two matchers are true complements. Ran: part of the 518-suite pass below. **Could not literally reproduce a live Caddy 413→200 flip** (no Docker daemon, no `caddy` binary in this sandbox, same as round 2) — this remains a static-inspection verdict, honestly labeled as such. | **CLOSED** |
| **C2** — `/shell/ocr` double-metering | `0ea8e20` | Live re-measurement, fresh account, 6 sequential distinct-image uploads on :8231: `200,200,200,200,200,429` — burst now trips at request 6 (i.e., 5 successes), not request 3 as round 2 observed. Separately: fresh account, exactly 2 uploads, `/shell/me` OCR remaining dropped from 30 → **28** (exactly 1 unit/upload). Note: round 2 could not directly show the pre-fix "26" via `/shell/me`, since M1's quota-meter bug meant `/shell/me` always echoed the full 30 regardless of real usage at that time — round 2's C2 evidence was the burst-trip pattern (2 successes then 429s) plus the code-level double-call; this round's combined C2+M1 fix now makes the unit count directly observable, and it's exactly 1 per upload. Diff confirms `router.py` no longer imports or calls `check_and_record`; `LimitsMiddleware` is the sole metering point, matching `panel_router.py`'s pattern. | **CLOSED** |
| **C3** — malformed panel key → 500 | `ba2f2c1` | Live POST of the exact `bad_panel_key.json` body plus 2 additional variants (extra-pipe, non-numeric value) to :8231 through the full shell stack → all four **400** `invalid_input`, `"bad panel key '...' (expected (Class, Stat))"`. Zero 500s in the server log across this whole round-2b session. Independently re-ran `wos_sim.backtest` myself (not just trusted the commit message): `VERDICT: PASS — no locked battle regressed, no new silent miss`, winners 7/13 unchanged from baseline. `wos_sim/predictor/tests` run myself: **206 passed, 2 xfailed** (matches commit claim exactly). | **CLOSED** |
| **M1** — quota meter always full | `35ef0c4` | Live re-measurement (same account/session as the C2 check): before any usage `remaining:{sims:100,ocr:30}`; after 2 OCR uploads `ocr:28` (sims untouched at 100); after 3 further `/api/predict` calls `sims:97` (ocr stays 28 — no cross-bleed between kinds, confirmed both directions). | **CLOSED** |
| **M2** — JWKS no backoff | `1af1f08` | Diff read: `JWKSCache` now tracks `_last_attempt_at`/`_consecutive_failures` independently of `_fetched_at`, exponential backoff (30s→…→300s cap) gated by a double-checked `asyncio.Lock`. Ran the specific new tests: `test_jwks_sequential_requests_during_failure_window_trigger_one_fetch`, `test_jwks_concurrent_requests_during_failure_trigger_one_fetch`, `test_jwks_retries_after_backoff_window_lapses`, `test_jwks_backoff_resets_after_a_successful_fetch`, `test_jwks_key_for_never_raises_on_persistent_failure` — all **PASSED**. A live equivalent would need a real/forced-failing JWKS endpoint under real auth mode (not keyless-testable without deliberately breaking DNS/network); the monkeypatched-transport test is the honest proof here, not a live check I skipped. | **CLOSED** |
| **M3** — `assets_prod/` never served | `9a2c731` | Live: `GET /shell/assets/manifest.json` on :8231 → 200; fetched all 3 SVGs the overlay's fallback maps to (`class_infantry.svg`, `chip_role_rally.svg`, `chip_role_garrison.svg`) → all 200, `image/svg+xml`. Independently verified (Node, outside the test suite) that `overlay.js`'s 5 regex patterns actually match the *real* prototype paths (`assets/Icons/Infantry.png`, `.../Lancer.png`, `.../marksman.png` — note the inconsistent casing in the real source; `assets/ui/rally-swords.png`, `.../garrison-shield.png`) — all 5 matched their intended manifest key. Confirmed the manifest actually contains all 5 keys. This is a fix that was checked for being *real*, not just present. | **CLOSED** |
| **M4** — sweep never scheduled | `e64bd56` | Live: booted `create_app()` under `TestClient(app)`'s context-manager form (the one thing in this whole suite that exercises FastAPI lifespan) — `app.state.sweep_task` is a genuine pending `asyncio.Task` running `run_sweep_scheduler` at `limits.py:615`, app serves `/shell/health` normally while it runs, and the task is confirmed `cancelled()` after the context exits. Not a mock — an actual scheduled task in a running app. | **CLOSED** |
| **M5** — `adv_absurd_n` false-FAIL | `90a4f66` | Live: ran the full probe suite against :8231 (see below) — `adv_absurd_n` now **PASS**, `200 body.n=1000`, with the new `expect_clamped_field` check actually reading the response body (not just the status code). | **CLOSED** |
| **Mn1** — `ocr_panel_mock_200` false-FAIL | `cb8fe07` | Live: same probe run — now **SKIP** with an honest, specific reason ("target's OCR_PANEL_MOCK is not enabled here... deployment/config fact, not a code defect"), not FAIL. | **CLOSED** |
| **Mn2** (settings-wiring test caveat) | not assigned / not a code defect | No fix needed — my round-2 note already said this wasn't reachable in production. Unchanged, not re-checked. | N/A |
| **Mn3** (`SKILL_INGESTION_DIR` env-only) | not assigned | Not a blocking finding in round 2; not fixed, not re-checked (informational only). | N/A |
| **Mn4** (scp-bundle excludes `shell/tests/`) | `cb8fe07` | Diff read: `promote.py`'s `BUNDLE_EXCLUDE_DIRS` comment and `step3_assemble`'s evidence string now state the exclusion and its rationale explicitly, so a Gate Report reviewer sees it rather than having to know to look for its absence. Decision (keep excluding, document why) matches what I'd have recommended — this was never a "must reject uploads" bug, only an undocumented gap. | **CLOSED** |

---

## Collateral / suites

| Check | Command | Result | vs. expected |
|---|---|---|---|
| Shell suite | `python -m pytest shell/tests -q` | **518 passed**, 0 failed | matches |
| UI style guard | `python -m pytest wos_sim/predictor/tests/test_ui_style_guard.py -q` | **7 passed** | matches |
| Node OCR client (13 files) | `node --test <13 files>` | **150 tests, 149 pass, 1 skip, 0 fail** | matches |
| Predictor suite | `python -m pytest wos_sim/predictor/tests -q` | **206 passed, 2 xfailed** | matches |
| G12 backtest (mandatory guardrail, CLAUDE.md standing rule 2 — independently re-run, not trusted from the commit message) | `python -m wos_sim.backtest` | `VERDICT: PASS`, winners 7/13 (baseline 7) | no regression |
| Probes, live, dev-bypass | `python shell/probes/run_probes.py --base http://127.0.0.1:8231 --dev-bypass` | **21 probes · 17 PASS · 0 FAIL · 4 SKIP**, exit 0 | zero FAILs; all 4 SKIPs are the expected DEV_BYPASS-target-context ones (`anonymous_predict_401`, `docs_endpoints_closed`, `invalid_webhook_signature` — all correctly defer to a staging/prod target; `ocr_panel_mock_200` — target has no `OCR_PANEL_MOCK` set) |

## F1–F5 spot-checks (fastest honest check per item, not a full redo)

- **F1**: `shell/Dockerfile:28` still has the `COPY .claude/skills/wos-battlereport-ingestion/ ...` line. Unchanged.
- **F2**: `shell/app/ocr/cache.py:95` still has `row.setdefault("job_id", row.get("id"))`. Unchanged.
- **F3**: `shell/app/auth.py` still calls `_resolve_plan_for` → `resolve_plan(user_id)` from the real-JWT verify path (line 274); `test_verified_session_resolves_real_plan_from_subscription` still in the 518-pass suite. Unchanged.
- **F4**: live re-check on :8231, `n:20000` → forecast response `"n":1000`. Still clamps correctly (and, per C2's fix, the metering that enforces this is now single-path too).
- **F5**: live re-check on :8233 (`ENV=staging DEV_BYPASS=0`): `/docs`→404, `/redoc`→404, `/openapi.json`→404. Unchanged.

All five hold. No regressions introduced by the 9 fix commits.

## Housekeeping note (round 2b)

Same cosmetic `wos_sim/data/avatars/manifest.json` `source_media` path-string side effect as round 2's §8 note
recurred — this time from running the predictor test/backtest suites directly (not `promote.py`, which wasn't
run this round), confirming it's a general property of exercising that suite in this checkout rather than
specific to `promote.py`. Reverted with `git checkout -- wos_sim/data/avatars/manifest.json` before finishing;
`git status --porcelain` is clean apart from this report and `shell/tmp_eval2/` scratch artifacts. Both servers
booted this round (:8231, :8233) were stopped and confirmed closed before finishing.

---

*Round 2b addendum. Nothing in this section authorises anything entering `E:\WOS\WOSTests.com` — that remains
gated on `PRODUCTION_CRITERIA.md`'s own §I1 process (independent QA PASS + Martin's literal sign-off through
`promote.py`'s hard prod door), which this evaluation is input to, not a substitute for.*
