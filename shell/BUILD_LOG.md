# shell/BUILD_LOG.md — per-agent handoffs

(Each shell build agent appends a section here per ARCHITECTURE.md "Definition of done" #3.)

## Agent C — OCR

**Date:** 2026-08-04 · **Scope:** PRODUCTION_PLAN.md §2.3 (OCR service) · **Owns:** `shell/app/ocr/*`, `shell/tests/test_ocr_*.py`

### What was built

- `shell/app/ocr/vision.py` — `VisionClient` protocol + `AnthropicVision` (anthropic lib, model from settings, temperature 0, image + extraction prompt) + `MockVision` (active when `OCR_MOCK=1` or no `ANTHROPIC_API_KEY`; returns canned extractions from the synthetic fixtures; counts calls for cache tests). The extraction prompt embeds the v2 schema **verbatim at runtime** from `.claude/skills/wos-battlereport-ingestion/references/schema.md` (cannot drift from the skill) plus the never-fabricate rule verbatim: "If a field is not clearly visible, return null. NEVER guess or infer values." (COMPASS invariant 8). No engine internals in the prompt (D4).
- `shell/app/ocr/extract.py` — orchestration: bytes → size/type validation (pillow; 8 MB cap; PNG/JPEG/WEBP by decoded content, not filename; decompression-bomb pixel cap) → EXIF strip (orientation applied, metadata-free re-encode) → sha256 of the original bytes → cache check → vision → JSON parse (fence/prose tolerant) → validator → BRD §9 profile mapping. Result: `{"status": ok|partial|failed, "profile", "unreadable_fields", "job_id", "reason", "warnings", "cached"}`.
- `shell/app/ocr/cache.py` — image-hash → job/result store. Uses Agent B's `shell.app.db` if it exposes `get_ocr_job_by_hash`/`create_ocr_job` (names TBC — TODO(Agent B)), else an in-memory dict with the identical async interface. Records status + cost estimate per job. Deterministic failures are cached too (same image → no repeat spend).
- `shell/app/ocr/router.py` — `POST /shell/ocr` (multipart `file`, optional `side=attacker|defender`). Enforces auth presence via `request.state.user` (401 `auth_required` otherwise); calls Agent B's `limits.check_and_record` when importable, else a documented no-op (TODO(Agent B)). Intake violations → 400 with machine-readable codes.
- `shell/app/ocr/_shims.py` — Settings/UserCtx fallbacks per ARCHITECTURE.md: imports `shell.app.config`/`shell.app.auth` when Agent A lands them, else env-driven stubs with dev defaults. All settings access is `getattr`-with-default, so either implementation works unchanged.
- Fixtures `shell/tests/fixtures/ocr/synthetic_{valid_type1,partial_nulls,invalid}.json` — **synthetic mock-LLM outputs, clearly labeled; NOT real battle data.** Valid + partial PASS the real skill validator; invalid FAILs it (5 ERRORs).

### How the skill validator is reused

`extract.run_validator()` importlib-loads `.claude/skills/wos-battlereport-ingestion/scripts/validate_report.py` **in place, unmodified**, and round-trips the extraction dict through a temp file into its `check(path)` — zero validation logic duplicated. The skill file stays the single source of truth; the deploy image must ship the skill directory (a missing file raises a clear error, same for the schema.md prompt embed).

### Test results

`python3 -m pytest shell/tests/test_ocr_extract.py shell/tests/test_ocr_router.py` — **26 passed** (keyless, Linux sandbox, OCR_MOCK path). Covers: ok/partial/failed statuses, unreadable_fields surfacing, cache hit = no second vision call, oversized/wrong-type/garbage → 400, EXIF actually stripped (asserted on the outgoing bytes), 401 unauthenticated, keyless client selection, prompt embeds schema + never-fabricate.

### Mocked vs real

- Mocked: vision (MockVision fixtures), job store (in-memory), auth (test middleware per Agent A's UserCtx contract), limits (no-op).
- Needs real keys/agents: `ANTHROPIC_API_KEY` (+ optional `OCR_VISION_MODEL`, default `claude-sonnet-4-5`) activates `AnthropicVision`; Agent A's config/auth are picked up automatically by the shims; Agent B's `db.py`/`limits.py` are picked up automatically if they expose the expected names — **confirm helper names with Agent B**.

### Known gaps

1. **Real-screenshot accuracy is untested** — no API key exists yet; only the plumbing is proven. First real-key smoke test should run a handful of Martin's existing report screenshots through and compare with the hand-ingested corpus JSONs.
2. Multi-screen reports (Battle Overview + Stat Bonuses + …) currently mean ONE image per request; multi-image stitching into one report is not built (upload the stat panel you want prefetched, or call per screenshot).
3. `AnthropicVision.extract` is a blocking call inside an async endpoint — fine at current quotas (30 OCR/day pro); switch to `anthropic.AsyncAnthropic` if concurrency matters.
4. Gemini fallback (plan §2.3 mentions it) not implemented — protocol makes it a drop-in third impl.
5. Cost estimate is a flat 0.03 USD placeholder, not token-metered.
6. Cache is global by image hash (content derives solely from the uploaded image; results never listed — plan §2.5). If per-user isolation is preferred, key by (user_id, hash) in Agent B's table.

## Agent A — shell core

**Date:** 2026-08-04 · **Scope:** ARCHITECTURE.md composition model + PRODUCTION_PLAN.md §2/§2.4 · **Owns:** `shell/app/{main,config,auth,minimize}.py`, `shell/app/overlay/*`, `shell/{Dockerfile,docker-compose.yml,Caddyfile,.env.example,README.md,requirements.txt}`, `shell/tests/test_{auth,main,minimize,overlay}_*.py`

### What was built

- `config.py` — pydantic-settings `Settings` with EXACTLY the ARCHITECTURE key list (uppercase fields = env keys), all optional/dev-defaulted. `dev_bypass` property implements the conditional default (True iff no `CLERK_SECRET_KEY`). Derived helpers: `jwks_url` + `sign_in_url` decoded from the Clerk publishable key (Account Portal URL), `is_prodlike`. **Lowercase read-only aliases** (`settings.min_troops_per_side`, …) added for every key because the ARCHITECTURE contract text and Agent B/C's pre-A stubs use lowercase; Agent B's `SettingsView` case-bridge also works — both paths are safe.
- `auth.py` — pure-ASGI `AuthMiddleware` (outermost). Real mode: `__session` cookie / Bearer JWT, RS256 via JWKS (httpx fetch, TTL cache w/ rotation refetch, `_fetch_jwks` monkeypatchable for keyless tests), `exp` verified, `azp` checked only when present + BASE_URL configured. DEV_BYPASS: `UserCtx("dev_user", None, X-Dev-Plan|"free")`; header honored ONLY in bypass mode. Sets `request.state.user` (scope["state"]). Unauthed `/api/*`+`/shell/*` → 401 `{"error":"auth_required","sign_in_url"}`; unauthed HTML GET → 307 to sign-in with `redirect_url`; exempt: `/shell/webhook/stripe`, `/shell/health`, `/shell/overlay.js`, `/shell/overlay.css`. **NOTE(Agent B): the webhook exemption is the literal path `/shell/webhook/stripe` — if your router mounts elsewhere, sync with me.**
- `minimize.py` — staging/prod-only response rewrite for `POST /api/predict|/api/battle` (field names verified read-only against `serialize.forecast_to_dict` / `api.battle_timeline`): strips `debug`/`*_debug` keys recursively, drops the per-turn `kill_matrix`, bands absolute survivor/casualty per-turn series to nearest 100. Verdict probabilities, `engine` meta (near_even/confidence/note — COMPASS inv. 3), % loss distributions, skill_telemetry, procs untouched. ENV=dev: byte-for-byte pass-through.
- `overlay/` — `overlay.js`+`overlay.css` (navy-world DESIGN_SYSTEM tokens, self-contained, reduced-motion kill-switch, all dynamic strings via textContent) served auth-exempt; chip fetches `/shell/me`, Upgrade POSTs `/shell/billing/checkout` (graceful "Billing unavailable" if absent), sign-out clears `__session`. `OverlayMiddleware` injects `<script defer src="/shell/overlay.js"></script>` before `</body>` of the SERVED `/`+`/index.html` response only — disk file untouched (test-proven).
- `main.py` — `create_app(settings)`: routes `/shell/health` (+`sim_mounted` flag) and `/shell/me` (user/plan/entitlements/remaining; uses Agent B's async `db.get_entitlements`, config-default fallback); includes overlay router, Agent B's `billing.router` + Agent C's `ocr.router` when importable; mounts `wos_sim.predictor.server:app` at `/` LAST. Middleware order (request path): Auth → Limits → Minimize → Overlay → routes/mount. Limits layer prefers Agent B's `LimitsMiddleware`; falls back to my `LimitsAdapterMiddleware` coded to the `check_and_record` contract (fail-open with log — auth still enforced); no-ops keyless. Repo root self-inserted onto sys.path from `__file__`.
- Runtime: `Dockerfile` (python:3.12-slim, repo-root context, copies wos_sim/+prototype/+shell/), `docker-compose.yml` (app+caddy, env_file, restart, healthcheck), `Caddyfile` (wostests.com + staging → app:8200, auto-TLS), `.env.example` (every key, commented), `README.md`, `requirements.txt` (pinned base list verbatim).

### Test results

`~/venv312/bin/python -m pytest shell/tests/test_auth* test_main* test_minimize* test_overlay* -q` → **33 passed** (keyless, Linux sandbox). Full `shell/tests` minus Agent D's four promote/probe files → **123 passed** (A+B+C integrate). E2E covered: DEV_BYPASS identity + X-Dev-Plan, 401/307/exempt matrix, real RS256 JWT round-trip against a locally generated JWKS (valid/expired/garbage/unknown-kid), authed `/api/predict` + `/api/battle` through the mounted sim with the real Scenario_1 payload, staging banding + kill-matrix strip vs dev pass-through with IDENTICAL verdict/engine blocks (CRN determinism), overlay injection + disk-untouched proof.

### Mocked / needs real keys

- Mocked keyless: identity (DEV_BYPASS), JWKS (test-local RSA), billing checkout (overlay degrades), entitlements (config defaults if db absent).
- Real keys activate: `CLERK_PUBLISHABLE_KEY`/`CLERK_SECRET_KEY` (+optional `CLERK_JWKS_URL`) → real JWT verify + hosted sign-in redirects. Stripe/Supabase/Anthropic keys are Agent B/C territory, config keys already defined.

### Known gaps

1. **Sandbox/system Python must be ≥3.11** — `wos_sim/models.py` uses `enum.StrEnum`; on 3.10 the shell boots but `sim_mounted=false`. Sandbox runs used a uv-provisioned 3.12 venv (`~/venv312`); Docker image is 3.12.
2. Plan resolution in REAL auth mode is hardcoded "free" (TODO in auth.py) until Agent B exposes a subscriptions lookup; DEV_BYPASS plan switching works via X-Dev-Plan.
3. `/shell/me` `remaining` = full daily quota (no usage subtraction) until Agent B exposes a usage query (`db.get_usage_today` exists — wiring it is a 3-line follow-up, left out to avoid guessing semantics mid-build).
4. Sign-out clears the `__session` cookie client-side + redirects to sign-in; no Clerk server-side session revocation call.
5. Prototype sub-app ships CORS `allow_origins=["*"]` (its own middleware); same-origin serving makes it moot, but a Caddy header override or shell-level CORS lock (plan §2.4 "CORS locked to the domain") is a cheap hardening TODO before launch — flagging for Agent D's probe suite.
6. Agent B's `check_and_record` enforces MIN_TROOPS in ENV=dev too (plan §2.1 exempts the testing env; Martin's micro battles bypass the shell entirely, so impact is nil — noting the divergence).
7. Cross-agent imports in main.py catch broad `Exception` (not just ImportError) so a transiently broken co-agent module degrades the shell instead of crashing it — deliberate deviation from the brief's literal "try/except ImportError", logged here.

## Agent B — db/limits/billing

**Date:** 2026-08-04 · **Scope:** PRODUCTION_PLAN.md §2.2 (data model), §2.4 (limits), PRODUCTION_CRITERIA §C–D · **Owns:** `shell/app/db.py`, `shell/app/limits.py`, `shell/app/billing/*`, `shell/db/migrations/*.sql`, `shell/tests/test_db_*.py` / `test_limits_*.py` / `test_billing_*.py`

### What was built

- `shell/db/migrations/001_init.sql` — all eight §2.2 tables (users, profiles, subscriptions, entitlements, usage_events, ocr_jobs, saved_scenarios, audit_log); indexes on `usage_events(clerk_user_id, ts)`, `(request_fingerprint)`, `(ip_hash, ts)`; RLS enabled on every table with guarded service-role-only policies + anon/authenticated revokes (no-ops on vanilla Postgres/CI); entitlements seeded free={5 sims, 0 OCR}, pro={100 sims, 30 OCR}, max_runs=1000; `audit_log.dedup_key UNIQUE` doubles as the webhook idempotency ledger. Intentional addition to §2.2: `usage_events.fp_fields JSONB` (per-leaf-field value hashes) so sweep detection can see "one field stepped" without storing raw payloads.
- `shell/app/db.py` — `PostgresDB` (asyncpg pool from DATABASE_URL, lazy; `run_migrations()` applies `shell/db/migrations/*.sql` in order) and `InMemoryDB` (dict-backed, same interface, per-day UTC counters) selected by `get_db()`; keyless ⇒ in-memory automatically. Module-level contract functions: `get_pool()`, `record_usage`, `get_entitlements`, `get_usage_today`, `get_ip_usage_today`, `count_recent_events`, `fetch_usage_for_day`, `upsert_user`, `upsert_profile`, `get_subscription`, `get_user_by_customer`, `apply_subscription_update`, `save_scenario`/`get_scenario`/`list_scenarios` (ownership enforced), `audit` (dedup-aware), `get_audit_entries`, plus OCR-job helpers in BOTH styles (two-step `create_ocr_job`+`update_ocr_job`, and Agent C's one-shot `create_ocr_job(image_hash=,user_id=,status=,result=,cost_estimate_usd=)` / `get_ocr_job_by_hash` — cache.py's `DbOcrJobs` binds without changes). `reset_db()` used by tests (Agent A's auth tests already call it — works).
- `shell/app/limits.py` — contract-exact `check_and_record(user, endpoint, body, ip_hash) -> Allowed | Denied(status, code, message)`. Order: MIN_TROOPS (400 below_min_troops, also for missing/malformed troop totals — hostile client) → OCR-on-free (402 payment_required) → daily account quota from entitlements (429 quota_exhausted) → per-IP daily cap at 3× the plan cap (429 quota_exhausted) → burst ≤ BURST_PER_MIN sliding 60 s (429 burst) → record usage_event. Denied requests are NOT recorded (no quota burn from probes). `request_fingerprint` = sha256 of normalized body (sorted keys, troop values rounded to nearest 100, half-up). `LimitsMiddleware` (pure ASGI: buffers body, replays downstream, JSON denials, GLOBAL_CONCURRENCY semaphore) exists per contract — main.py currently uses Agent A's `LimitsAdapterMiddleware` around the same `check_and_record`, which is fine; mine remains available if wiring is consolidated. `sweep_scan(day)` flags ≥20-event families per account (identical fingerprints, or identical-except-one-field with ≥5 distinct stepped values), writes dedup'd `sweep_flag` rows to audit_log — re-runnable nightly; flag-only per D3 (throttle/alert is a follow-up wiring step).
- `shell/app/billing/` — `_contracts.py` (imports Agent A's real `UserCtx`/`Settings`; `SettingsView` bridges config.py's UPPERCASE fields to the contract's lowercase names; fresh settings per call so env changes are seen — A's lru_cached `get_settings` stays untouched); `stripe_client.py` (`create_checkout_session` → real stripe lib when STRIPE_SECRET_KEY set, else MockStripe fake session URLs; client_reference_id + metadata carry clerk_user_id); `entitlements.py` (`resolve_plan(user_id)` → pro iff subscription plan=pro, status active/trialing, period not expired); `webhook.py` (router: `POST /shell/billing/checkout` + `POST /shell/billing/webhook` with alias `POST /shell/webhook/stripe` to match auth.py's EXEMPT_PATHS; handles checkout.session.completed / customer.subscription.updated / deleted idempotently via the audit_log dedup ledger; unsigned events accepted ONLY when no secret AND ENV=dev, else 503; bad signature → 400). Package exports `router`, so main.py's auto-include picks it up.

### Test results (keyless, Linux sandbox, Python 3.10)

`python3 -m pytest shell/tests/test_db_core.py shell/tests/test_limits_core.py shell/tests/test_limits_sweep.py shell/tests/test_billing_webhook.py` — **59 passed**. Covers: quota exhaustion at the 6th free sim; MIN_TROOPS 4999→400 vs 5000→pass; OCR on free→402; burst 6th-in-a-minute→429 burst; per-IP 3× cap; middleware body restore; fingerprint rounding/ordering; sweep_scan flags a 25-step synthetic sweep and identical hammering, ignores varied normal usage, idempotent re-runs; webhook same-event-twice = exactly one state change; mock checkout URL; signature policy; subscription lifecycle → resolve_plan. Full suite: 143 passed; the 9 remaining failures are all `wos_sim` unimportable on the sandbox's Python 3.10 (`enum.StrEnum` needs 3.11+) — environment-only, unrelated to shell code.

### Mocked vs real

- Mocked/keyless: DB (InMemoryDB), Stripe (MockStripe + unsigned dev webhook), identity (dev_bypass fallback UserCtx).
- Real keys activate: DATABASE_URL → PostgresDB (run `001_init.sql` via `db.run_migrations()` or Supabase SQL editor); STRIPE_SECRET_KEY → real checkout sessions; STRIPE_WEBHOOK_SECRET → mandatory signature verification (point the Stripe dashboard at `/shell/webhook/stripe`, the auth-exempt alias).

### Known gaps / reconciliation notes

1. `main.py` `_entitlements_for` calls my **async** `db.get_entitlements` synchronously, sees a coroutine, and falls back to config defaults (identical values; a RuntimeWarning is emitted). TODO(Agent A): await it — also lets `/shell/me` subtract real usage via `db.get_usage_today`.
2. `auth.py` resolves every verified user as plan="free" (its TODO): wire `billing.entitlements.resolve_plan` into UserCtx.plan at auth time or in the limits path so paying users actually get pro quotas in real-auth mode. In DEV_BYPASS the X-Dev-Plan header works end-to-end today.
3. Usage is recorded before the engine runs: a downstream 5xx still consumes one quota unit. Acceptable v1; refund-on-error would need response-status feedback into the limits layer.
4. Per-IP cap uses `X-Forwarded-For` first value (trusted because Caddy terminates); direct-exposure deployments should ignore that header.
5. Sweep response is flag-to-audit_log only — the nightly scheduler, throttle hookup, and "email Martin" alert are not wired (PRODUCTION_PLAN §2.4 nightly job; promote.py/probes land separately).
6. `sweep_scan` cannot see sweeps split across accounts/days, and one-field detection needs ≥5 distinct stepped values (micro-steps <100 troops collapse to the "identical" pattern instead — by design).
7. Neutral scaffolding created because imports need them: `shell/__init__.py`, `shell/app/__init__.py` (comment-only; no owned logic).

## Agent D — pipeline/probes/IP/legal (2026-08-04)

**Built** (owned files only): `shell/promote.py` · `shell/probes/run_probes.py` + `shell/probes/payloads/*.json` (10 descriptors) · `shell/tools/phash_blocklist.py` + generated `shell/tools/blocklist.json` · `shell/assets_prod/` (22 original SVG assets + `manifest.json` + `generate_badges.py`) · `shell/legal/` (5 drafts) · `shell/tests/test_promote_*.py`, `test_probes_suite.py`, `test_phash_blocklist.py` (34 tests, all passing keyless on the sandbox).

**promote.py** implements PRODUCTION_PLAN §3 steps 1–8 as discrete functions: git-archive checkout (working-tree fallback allowed ONLY with `--dry-run`, recorded as not-release-grade for H2) → prototype checks via subprocess (pytest/regression/backtest; pass counts parsed into the report; `--skip-prototype-checks` is dev-only and REFUSED for prod) → assemble (shell runtime + artifact + assets_prod + `config/<target>.env` template; **asset-swap strips ALL raster images from the artifact** — real-repo dry-run stripped 142, incl. `wos_sim/data/avatars`) → static gates (phash scan F1, debug-endpoint grep D4, secret-pattern scan E4, UTF-8 index.html G2) → docker build (graceful TODO when docker absent) → deploy (ssh/scp commands documented, stubbed under `--dry-run`) → probe suite → draft Gate Report on the PRODUCTION_CRITERIA template with machine evidence filled and verdict hard-coded to DRAFT.

**HARD RULE enforced in code + tests:** `--target prod` exits 3 unless `--gate-report` contains a literal `VERDICT: PASS` line AND `--martin-signoff "yes-I-approve"` is passed; CONDITIONAL/FAIL/its own draft never open the door; a write-path guard raises on ANY path containing `WOSTests.com` — this script never writes to production, even when the gates are open (archiving is the human step 11).

**Blocklist:** 355 images phash-hashed (prototype/avatars 71 + prototype/assets 187 + wos_sim/data/avatars 97 — the third root was added after discovering the artifact itself carries scraped avatars). Scan fails (exit 2) at Hamming ≤ 6; exact and resized/recompressed copies verified caught; original SVG/raster verified clean. Rebuild: `python shell/tools/phash_blocklist.py build --roots prototype/avatars prototype/assets wos_sim/data/avatars --out shell/tools/blocklist.json` after any new scraped art lands in the prototype.

**Probes** (`run_probes.py --base URL [--dev-bypass]`): health 200 · anonymous predict 401 (auto-SKIPs with an honest note under DEV_BYPASS servers) · sub-5000 troops 400 · burst >5/min 429 · free-plan OCR 402/403 · 10 adversarial payloads (malformed JSON, 2 MiB body, negative troops, string-where-number, unknown/injection fields, nulls, bad panel key, absurd n, empty/list bodies) expecting clean 4xx never 5xx. Markdown evidence table output; exit 0/1/2. Tested against an in-process WSGI contract stub.

**Evidence:** real-repo dry-run report archived at `shell/build/GATE_REPORT_DRAFT_release-2026-08-04.md` (steps 1,3,4 PASS; 2 skipped — see gaps; 5 TODO docker; 6–7 SKIP dry-run).

**Mocked / needs real env:** deploy step needs a VPS host + deploy key (`--deploy-host`, commands documented in `DEPLOY_COMMANDS`); probe run against real staging needs the deployed shell; docker build needs docker.

**Known gaps:** (1) sandbox Python is 3.10 but wos_sim needs 3.11+ (`StrEnum`) — prototype checks (A1–A3) could not execute here; they run on Martin's box via `py -m` and MUST be run for any real promotion. (2) No git tags exist yet — step 1's tagged-archive path is tested only via the refusal branch + mini-repo; tag a release to exercise it. (3) The stripped-art bundle means production UI will have no hero avatars until Agent A's overlay maps hero names → `assets_prod` emblems (per plan §2.5 "hero NAMES as text"). (4) `blocklist.json` covers prototype+wos_sim art dirs as of tonight; new scraped images added later require a rebuild (promote does not auto-rebuild). (5) Legal drafts are DRAFTS — lawyer review + Martin's decisions required (screenshot retention "N days" placeholders, entity name, contact emails; CG letter is HELD per COMPASS D3 and marked DO NOT SEND). (6) Stripe checkout/webhook round-trip probe (plan §3 step 7) not in the probe suite — needs Agent B's staging Stripe test keys; add before first real gate. (7) Re Agent A's note 5 (CORS `allow_origins=["*"]`): probe suite doesn't yet assert CORS headers; cheap add once the Caddy/shell-level lock exists.
