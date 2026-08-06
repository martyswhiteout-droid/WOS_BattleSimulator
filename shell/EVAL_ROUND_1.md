# EVAL_ROUND_1 — independent evaluation of the overnight shell build

**Evaluator:** independent QA agent (did not write any shell code)
**Date:** 2026-08-04
**Scope:** everything under `shell/` produced by Agents A–D on 2026-08-04, evaluated against
`shell/ARCHITECTURE.md`, `PRODUCTION_PLAN.md` v1.1, `PRODUCTION_CRITERIA.md` §A–I, `COMPASS.md` §3–4.
**Method:** evidence only. Full test suite on Python 3.12, five live uvicorn deployments (dev / staging /
real-auth / probe / simulated-Docker-image), the probe suite, `promote.py --dry-run`, and a
Dockerfile-layout reconstruction. No builder claim was accepted without reproducing it.

---

# VERDICT: **REVISE**

**5 Critical, 15 Major, 11 Minor.** The e2e smoke is **not** clean: `/shell/ocr` returns HTTP 500 on the
second upload of any image, and returns HTTP 500 on *every* upload in the actual Docker image layout.

This is a strong build with excellent boundary discipline and a genuinely impressive honesty-preservation
result (see "Credit where due"). But four independent defects would each, on their own, break the product
for a paying customer on day one, and every one of them lives in the seams *between* agents — precisely
where four parallel builders were always going to be weakest. None of the four appears in any builder's
self-declared gap list.

---

## 1. Boundary integrity — **PASS**

| Check | Result | Evidence |
|---|---|---|
| Files under `wos_sim/`, `prototype/`, `.claude/` modified 2026-08-04 | **CLEAN** | `find wos_sim prototype .claude -newermt 2026-08-04 -type f` returns **only** `__pycache__/*.pyc` (compiled artifacts of my own test runs + the builders'). Zero source files. |
| Root-level files touched today | Planning layer only | `BRD.md`, `COMPASS.md`, `DECISIONS_2026-08-04.md`, `PRODUCTION_CRITERIA.md`, `PRODUCTION_PLAN.md`, `THIRD_PARTY_SETUP.md`, `shell/` |
| `PRODUCTION_CRITERIA.md` edit direction | **Tightening, not weakening** | Diff: D2 `≤20/day free, ≤200/day paid` → `5/day free, 100/day paid — reconciled 2026-08-04 per COMPASS D2`. This is the lower pair, matching Martin's logged decision. Acceptable. |
| `prototype/index.html` unmodified while overlay is served | **PROVEN** | Served HTML contains `shell/overlay.js` ×1; `grep -c 'shell/overlay.js' prototype/index.html` = **0** |
| `E:\WOS\WOSTests.com` untouched | **CLEAN** | `ls` → `AGENTS.md  CLAUDE.md  PRODUCTION_LOG.md` and nothing else |

`.gitignore` shows as dirty but the change is pre-existing CRLF churn (not in today's mtime set) and
contains no shell-related edit. **COMPASS invariant 5 held.** This is the single most important thing the
build could have got right, and it got it right.

---

## 2. Test suite — **PASS** (builders' claim verified)

```
$ ~/venv312/bin/python -m pytest shell/tests -q
152 passed, 1 warning in 11.28s          (Python 3.12.13, keyless, no network)
```

The builders' claim that the 9 failures they saw were Python-3.10-only (`enum.StrEnum` in
`wos_sim/models.py`) is **confirmed**: all 9 vanish on 3.12. Zero failures, zero skips, zero errors.

The problem is not the tests that fail. It is the four production-breaking defects that **152 passing tests
did not catch**, because every one of them lives in a seam the tests stub out (see F1–F4).

---

## 3. Live e2e smoke — **FAIL**

### 3a. DEV mode (`DEV_BYPASS=1 ENV=dev`, uvicorn :8211)

| # | Test | Expected | Observed | Result |
|---|---|---|---|---|
| T1 | `GET /shell/health` | 200 | `{"status":"ok","env":"dev","dev_bypass":true,"sim_mounted":true}` | PASS |
| T2 | `GET /` overlay injected | script tag present | 200, 266 604 B, `overlay.js` ×1 | PASS |
| T2b | disk `index.html` unchanged | 0 occurrences | **0** | PASS |
| T3 | `/shell/me` (`X-Dev-Plan: pro`) | pro quotas | `plan:pro, 100 sims, 30 ocr` | PASS |
| T3b | `/shell/me` (free) | free quotas | `plan:free, 5 sims, 0 ocr` | PASS |
| T4 | `POST /api/predict` Scenario_1 | 200 | 200, 47 866 B, full forecast | PASS |
| T5 | `POST /shell/billing/checkout` | mock URL | `{"url":".../mock-checkout?session_id=cs_mock_…","mock":true}` | PASS |
| T6 | `POST /shell/ocr` (OCR_MOCK=1, pro) | contract shape | 200, `{status, profile, unreadable_fields, job_id, cached:false}` | PASS |
| **T6b** | **same image again (cache path)** | **200 + `cached:true`** | **HTTP 500 — `KeyError: 'job_id'`** | **FAIL (F2)** |
| T7 | `/shell/ocr` on free plan | 402 | `{"error":"payment_required",…}` 402 | PASS |
| T8 | rapid sims on free plan | 429 | 200,200,429,429,429,429,429,429 | PASS |

### 3b. STAGING mode (`ENV=staging`, uvicorn :8212)

| # | Test | Expected | Observed | Result |
|---|---|---|---|---|
| S1 | troops 4 999/side | 400 | `{"error":"below_min_troops",…}` 400 | PASS |
| S2 | near-even mirror predict | 200 | 200, `near_even:true, confidence:"coin_flip"` | PASS |
| S3 | `/api/battle` | 200, no `kill_matrix` | 200; keys = `by_class, enemy_killed, enemy_survivors, index, own_killed, own_survivors, procs, turns` — **`kill_matrix` absent** | PASS |
| S5 | staging leak grep | no `TURN_PARAMS`/`debug`/`kill_matrix` | all 0 | PASS |
| **S6** | **12 MB body on `/api/predict`** | **413 / clean 4xx** | **200 OK in 9.55 s — engine ran** | **FAIL (F4)** |
| S7 | unsigned webhook, no secret, ENV=staging | refuse | **503** on both routes | PASS |
| **S8** | `/shell/me` remaining after 4 sims | decremented | still full quota | **FAIL (F13)** |

### 3c. Real-auth mode (`DEV_BYPASS=0`, no Clerk keys — nobody can authenticate; uvicorn :8213)

| # | Test | Expected | Observed | Result |
|---|---|---|---|---|
| A1 | anon `POST /api/predict` | 401 | `{"error":"auth_required","sign_in_url":…}` 401 | PASS |
| A2 | `X-Dev-Plan: pro` outside bypass | ignored | 401 | PASS |
| A3 | 11 path-trick variants (`//`, `/../`, `%2f..%2f`, trailing slash, case, query smuggling) | all 401/405 | all 401 or 405 — **zero bypasses** | PASS |
| A4 | exempt-path variants (`/shell/health/`, `/SHELL/HEALTH`) | fail closed | 401 / 404 | PASS |
| A5 | anon HTML `GET /` | 307 → sign-in | 307 with `redirect_url` | PASS |
| **A6** | **anon `GET /` with no `Accept` header** | **307** | **200, full 266 KB UI served** | **FAIL (F9)** |
| **A7** | `/openapi.json`, `/docs`, `/redoc` anon | 404 | **200 / 200 / 200** | **FAIL (F5)** |
| A8 | forged `alg:none` JWT, garbage cookie | 401 | 401, 401 | PASS |
| **A9** | `OPTIONS /api/predict` from `evil.example` | locked origin | **200, `access-control-allow-origin: *`** | **FAIL (F14)** |
| A4b | `GET /shell/billing/webhook` anon | exempt (Stripe posts unauthenticated) | **401** | **FAIL (F10)** |

### 3d. Simulated Docker image (exactly `COPY wos_sim/ prototype/ shell/` — no `.claude/`)

```
### .claude present in image?  NO
### /shell/ocr  ->  http=500
FileNotFoundError: Ingestion-skill validator not found at
  /tmp/eval/imagesim/.claude/skills/wos-battlereport-ingestion/scripts/validate_report.py;
  the deploy must include the wos-battlereport-ingestion skill.
```

### 3e. Probe suite (`run_probes.py --dev-bypass`, ENV=staging)

```
15 probes · 13 PASS · 1 FAIL · 1 SKIP        exit code 1
```

| Probe | Observed | Note |
|---|---|---|
| health | 200 | PASS |
| anonymous_predict_401 | 400 | SKIP (honest — DEV_BYPASS server) |
| sub_5000_troops_400 | 400 | PASS |
| burst_over_limit_429 | 400,400,400,400,429,429,429,429 | PASS |
| free_plan_ocr_402 | 402 | PASS |
| **adv_bad_panel_key** | **429** | **FAIL — burst-window contamination, not a payload result** |
| adv_absurd_n / adv_unknown_fields | 429 | "PASS" only because 429 falls in the accepted range |
| adv_huge_body | 400 | "PASS" but the 400 is `below_min_troops`, **not** a body-size limit (F12) |
| remaining 6 adversarial | 400 | PASS, no 5xx anywhere |

### 3f. `promote.py --dry-run` — **works**

```
[PASS] step 1 checkout   [SKIP] step 2   [PASS] step 3 assemble
[PASS] step 4 static gates  [TODO] step 5 docker  [SKIP] 6  [SKIP] 7      EXIT=0
```
Prod-door refusal logic verified by reading + its own 34 tests. Bundle assembled: 635 files.
**Bundle contains no `.claude/` and no `shell/tests/`** (F1).

---

## 4. Findings

Severity: **CRITICAL** = broken / insecure / contract-violating · **MAJOR** = must fix before Martin wakes ·
**MINOR** = note.

---

### F1 · CRITICAL · OCR is dead in every deployable artifact — Agent A (Dockerfile) + Agent D (promote.py)

`shell/app/ocr/extract.py:44-52` and `shell/app/ocr/vision.py:23-27` resolve the ingestion skill at runtime
from `<repo_root>/.claude/skills/wos-battlereport-ingestion/`. Both the validator (`extract.py:130-149`,
hit on **every** request including the mock path) and the schema embed (`vision.py:37-50`, hit on every
real-key request) hard-fail if it is absent.

`shell/Dockerfile:20-22` copies exactly `wos_sim/`, `prototype/`, `shell/`. `shell/promote.py:325-329`
assembles exactly the same three trees plus `config/`. **Neither ships `.claude/`.**

Reproduced live (§3d): the paid flagship feature returns HTTP 500 with `FileNotFoundError` on every upload
in the image layout. `promote.py`'s `BUNDLE_EXCLUDE_DIRS` (`promote.py:68`) also strips `shell/tests/`,
which is where `MockVision`'s fixtures live (`vision.py:27`) — so the `OCR_MOCK=1` fallback is dead too.

Agent C wrote *"the deploy image must ship the skill directory"* in `BUILD_LOG.md` line 20. Agents A and D
never read it. Classic four-parallel-agents failure.

**Required fix:** add `COPY .claude/skills/wos-battlereport-ingestion/ .claude/skills/wos-battlereport-ingestion/`
to `shell/Dockerfile`; add the same path to `promote.py` `step3_assemble`; add a `promote.py` static gate
that asserts `VALIDATOR_PATH` and `SCHEMA_MD_PATH` exist inside the bundle. Add a test that boots the app
from a directory containing only the Dockerfile's `COPY` set and exercises `/shell/ocr`.

---

### F2 · CRITICAL · OCR cache hit returns HTTP 500 — Agent C (`extract.py`) / Agent B (`db.py` row shape)

`shell/app/ocr/extract.py:424-429`:
```python
cached = await self.jobs.get_by_hash(prepared.sha256)
if cached is not None:
    out = dict(cached["result"])
    out["job_id"] = cached["job_id"]      # <-- KeyError
```
`cache.get_job_store()` (`cache.py:100-112`) prefers `DbOcrJobs` whenever `shell.app.db` exposes
`get_ocr_job_by_hash`/`create_ocr_job` — which it does. But `db.get_ocr_job_by_hash` returns the
`ocr_jobs` **row**, whose primary key is `id` (`db.py:241`, `001_init.sql:104`), not `job_id`. The
compatibility shim at `db.py:857-869` back-fills `result` and `cost_estimate_usd` but **not** `job_id`.

Reproduced live (§3a T6b): every second upload of the same screenshot → 500. Agent C's 26 tests pass
because they inject `InMemoryOcrJobs` (`cache.py:41-65`), which *does* have a `job_id` key. The two
in-memory stores were never reconciled with each other.

Note this is also a cost bug: the cache exists specifically so a re-upload does not burn another vision
call. As written, the second call crashes *after* the lookup, so the user retries and pays again.

**Required fix:** add `row.setdefault("job_id", str(row.get("id")))` to `db.get_ocr_job_by_hash`, or make
`extract.py` use `cached.get("job_id") or cached.get("id")`. Then add a router-level test that runs the
cache path through `DbOcrJobs` — not `InMemoryOcrJobs`.

---

### F3 · CRITICAL · Paying Pro subscribers are served the free plan — Agent A (`auth.py`) / Agent B (`entitlements.py`)

`shell/app/auth.py:181-183`:
```python
# TODO(Agent B): resolve the real plan from the subscriptions table
# (db.py) once it lands; until then every verified user is "free".
return UserCtx(user_id=sub, email=claims.get("email"), plan="free")
```
Agent B *did* land it: `shell/app/billing/entitlements.py:21` `resolve_plan(user_id)` is complete, correct
and tested. It is called **from nowhere in the application** — `grep` finds callers only inside its own
module and `test_billing_webhook.py`.

Consequence in real-auth mode (staging/prod): a user pays, the Stripe webhook correctly writes
`subscriptions.plan='pro'`, and then `limits.check_and_record` reads `user.plan == "free"` and gives them
**5 sims/day and a 402 on OCR**. We would be charging for a product we do not deliver. This is a
`PRODUCTION_CRITERIA` C2 failure (server-side entitlement enforcement enforcing the *wrong* entitlement)
and a refund/chargeback generator.

Both builders declared it as a gap (Agent A #2, Agent B #2) — each assuming the other would wire it. Nobody
did. A declared gap is still a Critical when the gap is "the paywall does not work".

**Required fix:** in `auth.py:183`, `plan = await resolve_plan(sub)` (guarded so a DB failure degrades to
"free", never to "pro"). Add an integration test: webhook → `checkout.session.completed` → authenticated
request → pro quota observed.

---

### F4 · CRITICAL · No body-size limit and no execution cap — a single free-tier user can wedge the box — Agent A (Caddyfile/app) + Agent B (`limits.py`)

Three compounding gaps, all `PRODUCTION_CRITERIA` E6 / D2:

1. **No body limit anywhere.** A 12 MB JSON body was accepted, fully buffered, parsed, and executed →
   HTTP 200 in 9.55 s (§3b S6). `limits.LimitsMiddleware:293-302` reads the entire body into memory
   *before* any quota check; `Caddyfile:6-14` sets no `request_body { max_size }`.
2. **No request timeout.** A single authenticated `POST /api/predict` with `n=20000` **never returned
   within 35 s** (measured). Neither uvicorn, Caddy, nor the shell sets a timeout.
3. **`max_runs` is enforced nowhere.** `entitlements.max_runs=1000` is seeded in `001_init.sql:62-65` and
   returned by `db.get_entitlements` — and read by no code path (`grep max_runs` → `db.py` only). The
   effective cap is the prototype's own `n ≤ 100,000` — **100× the entitlement**.

With `GLOBAL_CONCURRENCY=8` (`limits.py:358`), eight requests at `n=100000` hold every worker
indefinitely. A free account gets 5/day; three accounts suffice. This is exactly the "flood degrades
gracefully instead of taking the service down" clause of D2, unmet.

**Required fix:** (a) `Caddyfile`: `request_body { max_size 256KB }`; (b) enforce `n <= ent.max_runs` inside
`check_and_record` and return `400 runs_exceeded`; (c) set a hard server-side request timeout
(uvicorn `--timeout-keep-alive` is not it — wrap the engine call in `asyncio.wait_for`, or set Caddy
`reverse_proxy { transport http { read_timeout 30s } }`); (d) add a probe that asserts a 413 on an
oversized body instead of the current false-positive (F12).

---

### F5 · CRITICAL · `/docs`, `/redoc`, `/openapi.json` publicly reachable in staging/prod — Agent A (`main.py`), Agent D (`promote.py` gate)

`shell/app/main.py:172-173` correctly sets `docs_url=None, redoc_url=None, openapi_url=None` on the
**shell** app — then mounts the prototype app at `/` (`main.py:220`), which brings its **own** unsuppressed
FastAPI docs with it. Verified anonymous, `DEV_BYPASS=0, ENV=staging`: `/openapi.json` → 200,
`/docs` → 200, `/redoc` → 200 (§3c A7).

`PRODUCTION_CRITERIA` D4: *"no debug/dev endpoints"*. And `promote.py:397-409` `gate_debug_endpoints`
greps for `/api/debug`, `/shell/debug`, `debug=True`, `set_trace(`, `breakpoint(` — none of which match
FastAPI's auto-docs — so the draft gate report currently reads **"debug endpoints (D4): clean"**. A gate
that certifies a violated criterion is worse than no gate.

**Required fix:** in `main.py`, either strip the docs routes from the mounted sub-app after mounting, or add
a middleware returning 404 for `/docs`, `/redoc`, `/openapi.json` when `settings.is_prodlike`. Add both a
`promote.py` static gate and a runtime probe.

---

### F6 · MAJOR · Sign-out does not sign anyone out — Agent A (`overlay.js`)

`shell/app/overlay/overlay.js:120`:
```js
document.cookie = "__session=; Max-Age=0; path=/";
```
Clerk's `__session` cookie is **HttpOnly** — JavaScript cannot read or delete it. The user is redirected to
the sign-in page while remaining fully authenticated; hitting Back restores the session. Shared-device
scenario = account takeover. `PRODUCTION_CRITERIA` C4 requires *"logout works"*.

Agent A's gap #4 says "clears the `__session` cookie client-side + redirects; no Clerk server-side session
revocation" — but the client-side clear does not work either, which the gap text implies it does.

**Required fix:** add `POST /shell/signout` that emits `Set-Cookie: __session=; Max-Age=0; Path=/; HttpOnly;
Secure; SameSite=Lax` and (with `CLERK_SECRET_KEY`) calls Clerk's session-revoke API; have the overlay call
it and only then redirect.

---

### F7 · MAJOR · Per-skill proc histograms and kill attribution ship in production responses — Agent A (`minimize.py`)

`minimize.py` strips `debug`/`*_debug` and `kill_matrix` and bands counts — but leaves `skill_telemetry`
entirely untouched (explicit, `minimize.py:21-23`: *"skill_telemetry (display-shaped skill panels)"*).
Actual content of a staging response:

```json
"triggers": {"counts":[0,0,0,0,0,0,0,0,0,0,0,1000],
             "edges":[0.0,0.0833…,1.0],
             "median":1.0,"mean":1.0,"p5":1.0,"p95":1.0},
"kills": { … }
```

That is a 12-bin proc-timing histogram plus per-skill kill attribution, per hero, per side, for every
request. `PRODUCTION_CRITERIA` D4 forbids *"internal telemetry fields"*; `COMPASS.md` §2 names
*"per-proc kill attribution"* as the mechanics we deliberately do not surface. This is the highest-resolution
distillation channel left in the response — richer, per request, than the `kill_matrix` that was removed.

**Required fix:** decide deliberately what the skill panel needs to render (probably: skill name, level,
effect text, and a coarse "fired N times" figure) and strip `triggers.counts`/`edges`/percentiles and the
`kills` breakdown in `is_prodlike` mode. If the UI genuinely renders the histogram, that is a product
decision for Martin — but it must be a decision, not an oversight.

---

### F8 · MAJOR · The Century Games disclaimer is not rendered anywhere — unowned (A overlay / D legal)

`PRODUCTION_PLAN.md` §2.5 and `PRODUCTION_CRITERIA` F2 both require a **visible** disclaimer:
*"Not affiliated with or endorsed by Century Games."*

- `grep -c "Century Games" prototype/index.html` → **0**
- `grep -rn "Century Games" shell/app/overlay/` → **nothing**

The overlay is the only place the shell can add it without editing the prototype (boundary rule 1), and the
overlay does not. Agent D wrote five polished legal drafts; nobody rendered the one line that F2 actually
gates on. This is a gate item that will fail QA, and it is a ten-line fix.

**Required fix:** append a small footer element in `overlay.js` (textContent, per its own hostile-client
rule) with the disclaimer plus links to `/legal/tos`, `/legal/privacy`; serve `shell/legal/*` as static
routes.

---

### F9 · MAJOR · Anonymous clients get the full UI by omitting the `Accept` header — Agent A (`auth.py`)

`shell/app/auth.py:208-215`: the 307-to-sign-in only fires when `"text/html" in accept`. Any request
without that header falls through unauthenticated (comment: *"non-HTML static assets fall through … the page
itself already redirected"* — an assumption that a hostile client will send a browser's headers).

Verified: `curl http://…/` with no `Accept` → **200, 266 604 bytes of index.html** (§3c A6).
`GET /index.html` → 200 likewise.

The engine stays protected (all `/api/*` 401 correctly), so this is not a D5 leak — but it defeats the
gating intent, and the same fall-through would expose any future non-HTML content the prototype serves.

**Required fix:** invert the rule — default to redirect/401 for any unauthenticated non-exempt path, and
allow-list the specific static asset prefixes that must load pre-auth.

---

### F10 · MAJOR · Stripe webhook dual-path trap: the documented route 401s in production — Agent A (`auth.py`) / Agent B (`webhook.py`)

`auth.py:39-44` exempts exactly one webhook path: `/shell/webhook/stripe`.
`webhook.py:152-153` registers **two**, with `/shell/billing/webhook` first — and it is the path named
first in the module docstring (`webhook.py:8`), which is the natural thing an operator copies.

Verified in real-auth mode: `GET/POST /shell/billing/webhook` → **401** (§3c A4b), while
`/shell/webhook/stripe` is exempt. Neither `README.md` nor `.env.example` states which URL to configure in
the Stripe dashboard.

Failure mode: Martin pastes `/shell/billing/webhook` into Stripe, every event 401s, Stripe retries for
three days and gives up, and **no subscription ever activates** — with no error anywhere except a 401 in the
access log. Combined with F3 this means the money path has two independent ways to silently not work.

**Required fix:** pick one canonical path, delete the alias (or exempt both), and document it in
`README.md` + `.env.example` + `THIRD_PARTY_SETUP.md`. Add a test asserting the registered webhook route
set is a subset of `auth.EXEMPT_PATHS`.

---

### F11 · MAJOR · IP hashes are unsalted by default, and the salt key is undocumented — Agent B (`limits.py`)

`shell/app/limits.py:139-141`:
```python
def hash_ip(ip: str) -> str:
    salt = settings_extra(get_settings(), "ip_hash_salt", "")
```
`IP_HASH_SALT` is **not** in `config.py`'s field list and **not** in `.env.example`, so it will be empty in
production. An unsalted SHA-256 of an IPv4 address is a 2³²-entry rainbow table — minutes of compute to
reverse the entire address space. `shell/legal/privacy.md:70` states as a security control: *"IPs in usage
events are stored hashed."* That claim does not hold.

Same class of problem: `SWEEP_MIN_EVENTS`, `OCR_VISION_MODEL`, `OCR_MOCK_FIXTURE` are all read from the
environment but appear in neither `config.py` nor `.env.example`. `ARCHITECTURE.md` says config.py carries
"every env key"; four keys escaped it.

**Required fix:** add `IP_HASH_SALT`, `SWEEP_MIN_EVENTS`, `OCR_VISION_MODEL`, `OCR_MOCK_FIXTURE` to
`config.py` and `.env.example`; make the shell **refuse to boot** when `is_prodlike` and `IP_HASH_SALT` is
empty (an empty salt is a silent privacy downgrade — it must be loud).

---

### F12 · MAJOR · The probe suite contaminates itself and reports one false E6 result — Agent D (`probes/`)

Two problems, both damaging because this suite's output is pasted into the gate report as evidence:

1. **Burst contamination.** `run_probes.run_probes:239-249` runs `probe_burst` (8 rapid requests, exhausting
   the 5/min window) and then immediately runs 10 adversarial probes with no cooldown. Result on a clean
   local run: `adv_bad_panel_key` → **429, FAIL**, and `adv_absurd_n`/`adv_unknown_fields` "pass" only
   because 429 happens to fall inside their accepted range. Exit code 1. The suite's verdict is a coin flip
   on timing, not on the system under test.
2. **False E6 evidence.** `shell/probes/payloads/huge_body.json` describes itself as *"~2 MiB body — must
   hit the body-size limit (E6), clean 4xx"* and passes on a 400. That 400 is `below_min_troops` (the
   generated body has no `enemy` key), not a size limit — and §3b S6 proves a 12 MB body sails through with
   a 200. The gate report would carry a PASS for a control that does not exist.

Also missing from the suite, given it is the primary machine evidence for C/D/E: no probe for response
minimization (D4), none for `/docs` exposure, none for CORS (E5), none for the Stripe round-trip
(Agent D's own gap 6).

**Required fix:** sleep past the burst window (or use a distinct account) before the adversarial block;
rewrite `huge_body.json` to use a *valid, above-minimum* body so the only possible rejection reason is size,
and expect 413; add D4/E5/docs probes.

---

### F13 · MAJOR · The quota meter shown to users is always full — Agent A (`main.py`)

`shell/app/main.py:190-192`:
```python
# TODO(Agent B): subtract today's usage_events once db.py exposes a
# usage query; until then "remaining" reports the full daily quota.
remaining = {"sims": ent["daily_sim_quota"], "ocr": ent["daily_ocr_quota"]}
```
`db.get_usage_today(user_id, kind)` has existed since Agent B's commit (`db.py:785-787`). Verified live: after
four sims, `/shell/me` still reports `remaining: {sims: 500, ocr: 30}` (§3b S8).

The overlay renders this as *"Sims left today: 5"* right up to the moment the 6th request 429s. That is a
`PRODUCTION_CRITERIA` G3 problem (*"free-tier limits stated up front; no dark patterns"*) and, more to the
point for this product, it is the UI telling the user something untrue — the one thing this project has
decided it will not do.

Also relevant: `main.py:143-167` `_entitlements_for` awaits `db.get_entitlements` correctly (Agent B's
BUILD_LOG gap #1 claiming a sync-call/coroutine bug is **stale** — `inspect.isawaitable` handles it, and
`/shell/me` returned correct DB-sourced quotas live). Credit to Agent A for that; the remaining defect is
only the subtraction.

**Required fix:** `used = await db.get_usage_today(user.user_id, "sim")` (and `"ocr"`), report
`max(0, quota - used)`.

---

### F14 · MAJOR · CORS wide open; `OPTIONS` bypasses auth entirely; no HSTS — Agent A (`main.py`/`Caddyfile`)

- `auth.py:200` skips the auth branch for `OPTIONS` (reasonable for preflight), and the mounted prototype's
  own CORS middleware answers with `access-control-allow-origin: *` plus the full method list. Verified
  (§3c A9) — anonymous, from `Origin: https://evil.example`.
- `Caddyfile:6-14` sets no `Strict-Transport-Security` header (Caddy does not add HSTS by default), no
  security headers, no CORS override.

`PRODUCTION_CRITERIA` E5 requires *"HTTPS only; HSTS; CORS locked to the production origin"* — all three
unmet. Practical exploitability is limited (a `*` ACAO cannot carry credentials, so the cookie-authenticated
engine is not reachable cross-origin), which is why this is Major rather than Critical — but E5 is a gate
item with three explicit clauses and the build satisfies one of them.

Agent A flagged this (gap #5) and Agent D acknowledged it (gap #7); neither fixed it and no probe asserts it.

**Required fix:** add to `Caddyfile`: `header { Strict-Transport-Security "max-age=31536000; includeSubDomains"
X-Content-Type-Options nosniff X-Frame-Options DENY Referrer-Policy strict-origin-when-cross-origin }` and
strip/override `Access-Control-Allow-Origin` to the deployment origin; add an E5 probe.

---

### F15 · MAJOR · `requirements.txt` is fully unpinned despite calling itself pinned — Agent A

`shell/requirements.txt` header: *"pinned base list from shell/ARCHITECTURE.md"*. Actual content: 14
dependencies, **one** version constraint (`pydantic>=2`). `Dockerfile:16` runs
`pip install --no-cache-dir -r shell/requirements.txt` with no lockfile, so the release image is not
reproducible and a `docker build` next month can silently ship a different FastAPI/stripe/anthropic major.

`PRODUCTION_CRITERIA` E3 (dependency audit clean, `pip-audit`) is unrunnable against an unpinned set —
there is no version to audit.

**Required fix:** pin every dependency to an exact version (`pip freeze` from the verified 3.12 venv into
`requirements.lock`, install from the lock in the Dockerfile), run `pip-audit`, and record the output in the
gate report.

---

### F16 · MAJOR · JWKS failure has no negative cache — a Clerk outage becomes our outage — Agent A (`auth.py`)

`shell/app/auth.py:92-102`:
```python
if age > self.ttl_s or (kid not in self._keys and age > self.min_refresh_s) \
        or not self._keys:
    try: await self._refresh()
    except Exception: pass
```
The `or not self._keys` clause **bypasses the `min_refresh_s` throttle**. If the JWKS fetch fails (Clerk
down, DNS, or simply an app restart during an outage), `_keys` stays empty and `_fetched_at` stays 0 — so
**every single authenticated request** triggers a fresh 5-second `httpx` fetch, forever. Latency for all
users goes to 5 s and we hammer Clerk while it is already struggling.

`PRODUCTION_PLAN.md` §5 claims this case is planned for: *"Clerk outage (sessions verified via cached JWKS
keep working short-term)"*. That only holds if the cache was populated before the outage; after a restart
there is no cache and no backoff.

**Required fix:** record `_last_attempt_at` on failure too, and apply exponential backoff (e.g. 30 s → 5 min)
regardless of whether `_keys` is empty. Cap concurrent refreshes with an `asyncio.Lock` so a thundering
herd produces one fetch, not N.

---

### F17 · MAJOR · `shell/build/` is not gitignored — Agent D

`git check-ignore shell/build` → rc=1 (not ignored). The directory currently holds **296 files / 3.9 MB**,
including a full duplicate copy of `wos_sim/`. Committing the shell as-is checks build output into the source
tree, and every subsequent `promote.py` run dirties the working tree — directly at odds with
`PRODUCTION_CRITERIA` H2 (*"clean, tagged git commit — never a dirty working tree"*), which `promote.py`
itself enforces on others.

Related: `shell/.env.example` **is** gitignored by the pre-existing root rule `.gitignore:17 .env*`, so the
file `README.md:25` instructs the operator to copy will not exist in a fresh clone.

**Required fix:** add `shell/build/` to `.gitignore` and negate the example file (`!.env.example` or
`!shell/.env.example`). Verify with `git status --porcelain` after a promote run.

---

### F18 · MAJOR · `assets_prod/` is never served and never mapped — Agent A (overlay) / Agent D (assets)

`promote.py:335-343` deletes **all** raster images from the bundle's `wos_sim/` and `prototype/` trees
(142 files on the real-repo dry run). Nothing replaces them: `grep -rn assets_prod shell/app/` → **no
match**. There is no static mount for `shell/assets_prod/`, and no hero-name → emblem mapping anywhere.

Result after a real promotion: the production UI requests avatars and skill icons that 404 — and the staging
response I captured contains `"icon": "assets/hero_skills/hank-2/skill_1.png"`, i.e. the API itself points
the browser at art that the pipeline has just deleted. Twenty-two well-made original SVGs ride along as
dead weight.

Agent D flagged the avatar half of this (gap #3, "until Agent A's overlay maps hero names → assets_prod
emblems"); Agent A's overlay contains nothing of the kind and Agent A's gap list does not mention it.

**Required fix:** mount `shell/assets_prod/` at `/shell/assets/`, and add an overlay-side (or middleware)
rewrite mapping the prototype's image paths onto the manifest keys — or accept text-only hero names and
suppress the `<img>` elements. Either way it must be verified against a *promoted bundle*, not the dev tree.

---

### F19 · MAJOR · Sweep detection is never scheduled and never alerts — Agent B (declared)

`limits.sweep_scan` (`limits.py:387-489`) is solid, well-tested work that **nothing calls**. No cron, no
`docker-compose` sidecar, no startup task. `PRODUCTION_CRITERIA` D3 requires *"flag/throttle … Alert goes to
Martin; automated response is throttle"* — the build delivers flag-to-`audit_log` only, with no scheduler
and no alert path.

Declared honestly by Agent B (gap #5), which is why it is Major rather than Critical, but D3 is a gate item
and cannot be checked off in its current state.

**Required fix:** add a compose sidecar or an in-app `asyncio` daily task calling `sweep_scan`, plus an
email/webhook alert. Or, if this is v1.1 scope, get Martin's written waiver recorded in the gate report.

---

### F20 · MAJOR · `promote.py` step 1 reports **PASS** for a working-tree fallback — Agent D

`promote.py:283-286` returns `StepResult("1 checkout", "PASS", …)` when the tag does not exist and the
dry-run copies the dirty working tree. The evidence string is scrupulously honest (*"NOT release-grade
evidence for H2"*), but the gate report renders it as:

```
H  docs/tag:   PASS — tag `release-2026-08-04` not found; DRY-RUN fallback copied the WORKING TREE …
```

A reviewer skimming the Evidence block sees `PASS` against H. Everything else in `promote.py` is built to
resist exactly this kind of skim (the prod door, the DRAFT verdict, the write-path guard) — this one line
undercuts it.

**Required fix:** return status `SKIP` (or add a `WARN` status) for the working-tree fallback, and make the
H line read `NOT RELEASE-GRADE`.

---

### Minor findings

**F21 · MINOR · Agent C** — `ocr/router.py:67` calls `check_and_record(user, "ocr", …)`, but
`limits.classify_endpoint` (`limits.py:68-75`) normalises to `/ocr`, which is not in
`OCR_ENDPOINTS = {"/shell/ocr"}` (`limits.py:64`) → returns `None` → `Allowed()`. The router's own quota gate
is dead code; the 402 observed live comes entirely from `LimitsMiddleware`. Pass `"/shell/ocr"`. (Harmless
today, silently unprotected if middleware ordering ever changes.)

**F22 · MINOR · Agents B/D** — `X-Dev-User` is honoured by `limits.py:314-322` and sent by
`probes/run_probes.py:45-46`, but `auth.py:191-194` ignores it and always sets `user_id="dev_user"`. The
probe suite's "free user" and "pro user" are therefore the *same account*, which is part of why the burst
window bleeds across probes (F12). Either honour `X-Dev-User` in `auth.py` (bypass mode only) or remove it
from `limits.py` and the probes.

**F23 · MINOR · Agent D** — `shell/legal/privacy.md:26` promises *"Screenshots deleted after [30] days"* and
lists *"Our storage + database"* for uploads. The shell never stores screenshots: `extract.py:421-472`
hashes the bytes and discards them; `upload_ref` is always `None`. Over-declaring is safer than
under-declaring, but the policy should describe what the system does, and the referenced deletion job does
not exist.

**F24 · MINOR · Agents A/C** — two settings shims coexist: `ocr/_shims.py` (returns Agent A's
**lru_cached** `get_settings()`) and `billing/_contracts.py` (builds a **fresh** `Settings` per call). OCR
therefore freezes its settings at first use while limits/billing see env changes. Also `_shims.py:41`
defaults `ocr_mock=False` while `config.py:49` defaults `OCR_MOCK=True` — divergent defaults for the same
key in two shims. The stub branches are now unreachable; collapse both onto `config.get_settings` and delete
the stubs.

**F25 · MINOR · Agent A** — the casing bridge (`_contracts.SettingsView.__getattr__`, `_contracts.py:67-72`)
tries `name`, then `.upper()`, then `.lower()`. It works and is tested, but it silently resolves typos to
`AttributeError` only after three lookups and makes `getattr(settings, "anything_at_all", default)` behave
identically to a real missing key — which is exactly how `IP_HASH_SALT` (F11) slipped through undocumented.
It is fragile in the sense that it *hides* contract drift rather than failing on it. Once `config.py` carries
every key, delete `SettingsView` and the lowercase alias loop (`config.py:122-133`) and use one casing.

**F26 · MINOR · Agent D** — `promote.py` `TEXT_EXTS` (`promote.py:95-96`) omits extension-less files and
`.pem`/`.key`/`.crt`/`.sh`, so `gate_secret_scan` would not read an `id_rsa` or `server.key` that landed in
the bundle — despite having a `-----BEGIN … PRIVATE KEY-----` pattern ready for it.

**F27 · MINOR · Agent A** — no CSRF protection on the cookie-authenticated `POST /shell/billing/checkout`.
Clerk's `__session` is `SameSite=Lax` by default, which blocks cross-site POST, so this is currently
mitigated by the provider rather than by us. Worth an explicit `Origin` check.

**F28 · MINOR · Agent A** — `Dockerfile` runs as root, and `docker-compose.yml` sets no `mem_limit`/`cpus`,
no `security_opt: [no-new-privileges:true]`, and no `read_only` root filesystem. Cheap hardening on a
single-VPS deployment.

**F29 · MINOR · Agent B (declared)** — usage is recorded before the engine runs (`limits.py:238-249`), so a
downstream 5xx still burns a quota unit. Acceptable for v1 as declared, but it interacts badly with F4: a
request that times out costs the user one of their five daily sims.

**F30 · MINOR · Agent A** — `minimize.py:139` swallows every exception during rewrite and sends the
**original** bytes. If the minimizer ever throws on a novel response shape, production silently reverts to
the unminimized (unbanded, debug-carrying) body. Fail closed instead: on exception, return a 500 or an
explicitly-stripped payload, and log loudly.

**F31 · MINOR · Agent A** — responses carry verbatim in-game skill text (`"effect": "Hank's rage and the
roaring of his chainsaw…"`) and wiki-derived icon paths. `PRODUCTION_CRITERIA` F3 (scraped-content audit)
should rule explicitly on whether verbatim skill descriptions are "needed to render OUR results".

---

## 5. COMPASS invariant check

| Invariant | Verdict | Evidence |
|---|---|---|
| **#3 — hedging preserved, no manufactured precision** | **PASS — and impressively so** | Same near-even mirror scenario, dev :8221 vs staging :8222. `engine` block **byte-identical** including `near_even:true, confidence:"coin_flip", model_error:0.5, calibrated:false`. `verdict` block **byte-identical** (`win.p = 0.55` both). Changed leaf paths: 20, **all** of them count series banded to exact multiples of 100 (`981565.30 → 981600`). Dropped paths: 0 outside `kill_matrix`. **Added paths: 0** — nothing is invented in prod mode. No noise, deterministic banding, honesty labels untouched. |
| **#5 — prototype stays clean** | **PASS** | Boundary check §1; `MIN_TROOPS_PER_SIDE` exists only in `shell/` (`config.py:53`, `limits.py:180`); zero occurrences in `wos_sim/` or `prototype/` |
| **#6 — minimal output surface / hostile client** | **FAIL** | `skill_telemetry` proc histograms + kill attribution (F7); `/docs`+`/openapi.json` public (F5); no body/time/`max_runs` caps (F4) |
| **#8 — never fabricate an OCR input** | **PASS** | `vision.py:31-33` `NEVER_FABRICATE_RULE` is embedded verbatim as binding rule 1 (`vision.py:59`), plus rule 2 (null + `_validation.missing`), rule 4 (never substitute an assumed tier), rule 6 (declare missing screens). Schema is read from the skill at runtime (`vision.py:44-50`) so it cannot drift. `extract.map_report_to_profile` surfaces every gap in `unreadable_fields` rather than defaulting. Best-executed invariant in the build — **but see F1: this prompt never runs in a deployed image.** |
| **#4 — production empty until it earns otherwise** | **PASS** | `WOSTests.com` untouched; `promote.py` write-guard (`promote.py:157-165`) + prod door (`promote.py:168-195`) verified by reading and by its 34 tests |

---

## 6. PRODUCTION_CRITERIA readiness (indicative — this is not a Gate Report)

| Item | State | Blocking findings |
|---|---|---|
| A1–A5 engine | Not evaluated here (engine unchanged; still CONDITIONAL per `ENGINE_REBUILD/QA_REPORT.md`) | — |
| B1 schema_version | Partial — `saved_scenarios.schema_version NOT NULL` ✔; OCR profile emits `schema_version: 1` ✔; **no version-rejection path** for unknown versions | — |
| B2 strict validation | **PASS** — 10 adversarial payloads, zero 5xx, clean 400s | — |
| B3 data model | **PASS** — 8 tables, RLS, indexes, seeded entitlements; migration is good work | — |
| C1 login required | Partial | F9 |
| C2 server-side entitlements | **FAIL** | **F3** |
| C3 hosted checkout + verified webhook | Partial — logic correct, routing broken | F10 |
| C4 session security / logout | **FAIL** | F6 |
| C5 abuse-resistant free tier | Partial — per-IP 3× cap works; hash is reversible | F11 |
| D1 MIN_TROOPS | **PASS** — 4 999 → 400, verified live | — |
| D2 layered rate limits | Partial — quota/burst/IP/concurrency all verified working; no request cap | F4 |
| D3 sweep detection | **FAIL** — never scheduled, never alerts | F19 |
| D4 minimized output | **FAIL** | F5, F7 |
| D5 engine server-side | **PASS** | — |
| D6 ToS clauses | **PASS** — all four clauses present in `legal/tos.md` | — |
| E1 pentest | Not run (no staging deployment exists) | — |
| E2 adversarial suite | Partial — suite self-contaminates | F12 |
| E3 dependency audit | **FAIL** — unpinned, unauditable | F15 |
| E4 secrets | **PASS** — no secrets found; `.env` gitignored; scanner works | F26 (coverage gap) |
| E5 HTTPS/HSTS/CORS | **FAIL** | F14 |
| E6 timeouts + body limits | **FAIL** | F4 |
| F1 asset audit | Partial — 355-image phash blocklist and stripping work; replacement half missing | F18 |
| F2 disclaimer | **FAIL** | F8 |
| F4 legal pages | Drafted, not served, not lawyer-reviewed | F8, F23 |
| G3 honest paywall UX | **FAIL** — quota meter always full | F13 |
| H2 clean tagged tree | **FAIL** — `shell/` untracked, `shell/build/` not ignored, no tag exists | F17 |

---

## 7. The three best things about this build

**1. COMPASS invariant 3 is not just respected — it is provable.**
I tried hard to break it. I ran the same near-even mirror scenario through a dev instance and a staging
instance and diffed every leaf in the response tree. The `engine` block and the `verdict` block came back
**byte-identical**, `near_even:true` and `confidence:"coin_flip"` intact, `model_error` untouched. The only
20 changed leaves were count series banded to exact multiples of 100 — deterministic, no noise — and the set
of *added* paths was empty, meaning production mode invents nothing. `minimize.py` is 147 lines and it does
exactly what its docstring says, no more. For a project whose entire moat is "the tool admits when it does
not know", getting this right on the first pass is the result that matters most.

**2. `promote.py` is written to resist its own operator.**
The prod door refuses by default and demands a literal `VERDICT: PASS` line in a file it did not write, plus
Martin's exact sign-off phrase — and the DRAFT verdict it emits is deliberately constructed so it can never
satisfy its own gate. On top of that, `assert_safe_write_path` raises on *any* path containing
`wostests.com`, so even with both gates open the script physically cannot write to production. That is a
builder anticipating the failure mode "a future agent runs me with plausible-looking arguments" and closing
it structurally rather than with a comment. `PromoteRefusal` exit code 3, tested. Genuinely excellent.

**3. Boundary discipline held under four-way parallel pressure — and the plumbing underneath is clean.**
Not one source file outside `shell/` was touched, verified by mtime rather than by trust. The overlay proves
the pattern works: the served page carries the script tag, the disk file demonstrably does not. Beyond that,
`001_init.sql` is professional work (RLS on all eight tables, guarded `DO` blocks that no-op on vanilla
Postgres, `audit_log.dedup_key UNIQUE` doing double duty as the Stripe idempotency ledger — an elegant
choice), the auth middleware survived eleven path-traversal and case/slash-smuggling variants with zero
bypasses, `limits.py`'s check ordering is deliberate and correct, and Agent C's decision to `importlib`-load
the ingestion skill's validator *in place, unmodified* rather than copying its logic is exactly the right
instinct. The parts each agent owned are, with few exceptions, good code.

---

## 8. What to fix first

In order, by "what breaks a paying customer soonest":

1. **F3** — paying users get the free plan. One line in `auth.py` + an integration test.
2. **F1** — ship `.claude/skills/wos-battlereport-ingestion/` in the Dockerfile and the promote bundle.
3. **F2** — the `job_id`/`id` key mismatch in the OCR cache.
4. **F4** — body-size limit, request timeout, and `max_runs` enforcement.
5. **F10 + F6** — webhook path reconciliation and a working sign-out.
6. **F5, F7, F8, F13, F14** — the D4/F2/G3/E5 gate items, all small and all currently failing.

Then re-run: full suite on 3.12, the six live smoke scenarios in §3, the probe suite (after fixing F12), and
a boot from a Dockerfile-layout directory. Re-gate from scratch — several of these findings were invisible
to a 152-test green suite, so a green suite is not sufficient evidence for round 2 either.

---

*This document is an evaluation, not a Gate Report. It does not constitute the independent QA PASS required
by `PRODUCTION_CRITERIA.md` §I1, and nothing here authorises anything entering `E:\WOS\WOSTests.com`.*
