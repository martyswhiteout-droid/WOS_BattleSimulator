# PRODUCTION_PLAN — Prototype → Monetized SaaS (v1.1, 2026-08-04)

**Status: IN EXECUTION (Martin's directive, 2026-08-04).** v1.0 was the Stage-2 draft (2026-07-11). Martin ordered execution on 08-04 without the Stage 3–5 red-team round — a consciously accepted risk, recorded in `DECISIONS_2026-08-04.md` (the red-team can still run against the *built* shell before launch). COMPASS.md §6 "do not execute" is superseded by this directive for the shell BUILD; **LAUNCH remains gated** by `PRODUCTION_CRITERIA.md` (independent QA PASS + Martin sign-off) and by engine certification scope (COMPASS D4).

Decisions of record (Martin 08-04 + logged defaults): **Clerk** (auth + user management), **Supabase Postgres** (data ONLY — no Supabase Auth), **Hostinger VPS** hosting (Docker; VERIFY plan is a VPS), **Stripe direct** (Clerk Billing logged as alternative), **IP posture:** hero names + original class iconography, Century Games letter drafted but HELD (COMPASS D3), **tiers:** free 5 sims/day manual-entry / paid ~100 sims/day + OCR (quota contradiction resolved to the lower pair per COMPASS D2).

---

## 1. Objectives

- A paying customer can: sign up → verify email → subscribe via Stripe → upload a battle-report screenshot → get a simulation verdict — without Martin touching anything.
- The prototype's engine + UI stay **clean**: no auth, paywall, or database code enters `wos_sim/` or `prototype/`. All production code lives in the isolated `shell/` directory (see boundary rules in `shell/ARCHITECTURE.md`). Martin keeps iterating on engine + UI exactly as today.
- Promoting a prototype release to production is a **repeatable, mostly-automated pipeline** ("the gate"), not a manual integration project each time.
- Everything that ships passes `PRODUCTION_CRITERIA.md` v2 with an independent QA gate report and Martin's sign-off, logged in `WOSTests.com\PRODUCTION_LOG.md`.

**Success by end of plan:** staging environment live with one test subscriber end-to-end; first gate report produced; production launch is then a sign-off decision, not a build task.

## 2. Architecture — the shell pattern

Build the production wrapper ONCE as its own long-lived codebase ("the shell"). Each release, the pipeline snaps the current prototype into the shell. The prototype is the phone; the shell is the case; the pipeline is the assembly line.

```
┌─ TESTING ENV (E:\WOS\Battle Simulator) ─────────────────┐
│  wos_sim/ engine + predictor    prototype/index.html    │
│  (no auth/db/paywall — unchanged)                       │
│  shell/  ← the production wrapper (ISOLATED subfolder)  │
└──────────────── git tag: release-YYYY-MM-DD ────────────┘
                          │  promote.py pulls tagged artifact
                          ▼
┌─ SHELL (shell/) ─────────────────────────────────────────┐
│  FastAPI wrapper app:                                    │
│   • Clerk auth (hosted sign-in; __session JWT cookie     │
│     verified server-side via Clerk JWKS)                 │
│   • quota + rate-limit middleware (Supabase-backed)      │
│   • Stripe billing + idempotent webhook                  │
│   • OCR service endpoint (vision-LLM, v2 schema)         │
│   • production config (MIN_TROOPS=5000, caps, timeouts)  │
│   • IP-safe asset pack (assets_prod/, swappable)         │
│   • small JS overlay (login/quota/upgrade UI, injected   │
│     at serve time — prototype index.html NOT edited)     │
│  imports → wos_sim.predictor.api (the existing seam)     │
└──────────────────────────────────────────────────────────┘
                          │  Docker build
                          ▼
        staging.wostests.com  ──gate probes + QA report──▶  wostests.com
              (Hostinger VPS, docker compose: app + caddy + backups)
```

Why this works with zero prototype changes:
- The prototype UI talks to the backend only via `POST /api/predict` and `/api/battle`. Clerk's session cookie (`__session`) flows automatically with those same fetch calls — `index.html` runs unmodified. Unauthenticated requests are redirected to Clerk's hosted sign-in page (Account Portal), so we ship no login UI of our own.
- The engine is only reachable through `wos_sim/predictor/api.py` (the seam). The shell imports it like any package; middleware wraps it.
- Login state, quota meter, and upgrade prompts are a separate overlay script the shell injects when serving the UI — additive, never editing the prototype file.

### 2.1 Environments

| Env | Where | Purpose | Auth | Stripe | Data |
|---|---|---|---|---|---|
| Testing | local (`E:\WOS\Battle Simulator`) | Martin's daily work; micro battles ALLOWED; no auth (shell runs with `DEV_BYPASS=1` mock identity for local shell testing) | mock | none | local/staging Supabase |
| Staging | `staging.wostests.com` (same VPS, second compose stack) | full shell; gate probes run here; QA agent tests here | Clerk dev instance | test keys | staging Supabase project |
| Production | `wostests.com` | paying users | Clerk prod instance | live keys | production Supabase project |

`E:\WOS\WOSTests.com` (the folder) holds release artifacts + gate reports + PRODUCTION_LOG — the auditable record of what is deployed. **It stays empty until a gated release.**

### 2.2 Data model (Supabase Postgres — data only; identity lives in Clerk)

- `users` — clerk_user_id (PK), email (synced via Clerk webhook), created_at. Local mirror of Clerk identities for joins.
- `profiles` — clerk_user_id FK, display name, game server.
- `subscriptions` — clerk_user_id, stripe_customer_id, stripe_subscription_id, plan, status, current_period_end. **Updated ONLY by verified Stripe webhook or admin.**
- `entitlements` — plan → daily_sim_quota, daily_ocr_quota, max_runs. Seeded: free = 5 sims/day, 0 OCR; paid = 100 sims/day, 30 OCR/day.
- `usage_events` — append-only: clerk_user_id, ip_hash, endpoint, request_fingerprint (hashed normalized payload), troops_own, troops_enemy, ts. Feeds quotas AND sweep detection.
- `ocr_jobs` — upload ref, image_hash, status, extracted JSON, validator verdict, cost.
- `saved_scenarios` — user's saved setups (`schema_version` mandatory, per B1).
- `audit_log` — admin/security events.

The shell is the ONLY database client (service-role key, server-side). The browser never talks to Supabase or Clerk's APIs beyond the sign-in flow — smaller attack surface, simpler model. RLS stays ON as defense-in-depth.

### 2.3 OCR service (the killer paid feature)

The spec ALREADY EXISTS: `.claude/skills/wos-battlereport-ingestion/` (deterministic v2 schema, Type-1/Type-2 rules, never-fabricate, `validate_report.py`). Production OCR = that skill industrialized:

1. User uploads screenshot(s) → stored (size/type-limited, EXIF-stripped).
2. Vision-LLM call (Anthropic API; Gemini as fallback) with the v2 schema as the extraction contract; temperature 0; "if a field is not visible, return null — NEVER guess" (the skill's never-fabricate rule, verbatim; COMPASS invariant 8).
3. Server runs `validate_report.py` logic on the output; failures → "couldn't read these fields, please enter manually" (partial prefill, honest).
4. Result prefills the sim form; user confirms before running.

Notes: WoS screenshots come in many languages/resolutions — vision LLMs handle this far better than classical OCR. Cost ≈ US$0.01–0.05/screenshot → paid-tier only, quota-metered, cached by image hash. The LLM sees only the user's screenshot — no engine internals in the prompt (D4 respected).

### 2.4 Anti-distillation & security config (per PRODUCTION_CRITERIA v2 §C–E; COMPASS invariant 6)

Enforced in the shell, configured per-environment, NEVER in the prototype:
- `MIN_TROOPS_PER_SIDE = 5000` (staging/prod; testing env exempt — micro battles are the research method, COMPASS invariant 5).
- Quotas (single source of truth = `entitlements` table): free 5 sims/day, 0 OCR; paid 100 sims/day, 30 OCR/day. Burst ≤5/min/account; per-IP caps; global concurrency cap; request body limits; timeouts.
- Response minimization: strip `skill_telemetry` internals/debug fields from prod responses; survivor figures banded (no noise — honesty design preserved, COMPASS invariant 3).
- Sweep detection: nightly job over `usage_events` fingerprints → flag → throttle + email Martin.
- Secrets in VPS env vars only; HTTPS via Caddy (auto-TLS); CORS locked to the domain; ToS forbids reverse engineering/bulk querying (D6). Cloudflare free tier in front (DDoS/WAF) recommended — see THIRD_PARTY_SETUP.

### 2.5 IP-safe asset pack (per §F; COMPASS D3 = ship clean, hold the letter)

- `shell/assets_prod/` replaces scraped art: hero NAMES as text + ORIGINAL class/generation/role token art (code-drawn SVG emblems — ice/survival theme, nothing resembling Century Games characters).
- Pipeline asset-swap step + automated check: perceptual-hash blocklist of known scraped images — build FAILS if any blocklisted image is in the bundle.
- Footer disclaimer: "Fan-made tool. Not affiliated with or endorsed by Century Games." Game name used nominatively only.
- Century Games permission letter: DRAFTED, NOT SENT (D3 — Martin decides after shipping clean).
- User-uploaded screenshots shown back to the uploader only; no galleries.

## 3. The gate pipeline (the "transformer")

One script, `shell/promote.py`, fully repeatable:

```
1  INPUT: prototype git tag (e.g. release-2026-08-01)
2  Pull tagged artifact (wos_sim + prototype/index.html + assets manifest)
3  Prototype-side checks:  pytest ▸ regression ▸ backtest ≥ baseline (A1–A3)
4  Assemble: shell + artifact + assets_prod + prod config
5  Static gates: no blocklisted images ▸ no debug endpoints ▸ no secrets in bundle ▸ UTF-8 check
6  Build Docker image, deploy → STAGING
7  Automated staging probes: anonymous /api/predict → 401 ▸ sub-5000 troops → 400 ▸
   burst > limit → 429 ▸ free account calling OCR → 402/403 ▸ Stripe test checkout+webhook round-trip ▸
   adversarial payload suite → clean 400s (QA_PROMPT.md)
8  Emit draft Gate Report (PRODUCTION_CRITERIA template) with machine evidence filled in
9  HUMAN GATE: independent QA agent completes §B–F judgment items → verdict (PASS required)
10 HUMAN GATE: Martin sign-off
11 Promote same image staging → production; append PRODUCTION_LOG.md; archive artifacts to E:\WOS\WOSTests.com
```

Steps 1–8 autonomous; 9–10 deliberately human, no exceptions (COMPASS invariant 4).

## 4. Phases & budgets

Overnight agent build (2026-08-04) covers the CODE of Phases 1–5 in mock-first form (runnable with `DEV_BYPASS=1` and mocked Stripe/OCR — no external accounts exist yet). Martin's account registrations (Phase 0, see `THIRD_PARTY_SETUP.md`) then activate real integrations.

| Phase | Scope | Status |
|---|---|---|
| 0 | Accounts: verify Hostinger VPS (BLOCKER if shared); Clerk app (dev+prod); Supabase ×2; Stripe; Anthropic key; DNS (+ Cloudflare optional) | **Martin, morning — see THIRD_PARTY_SETUP.md** |
| 1 | Shell skeleton: FastAPI wrapper, Clerk JWT middleware (+dev bypass), UI serving + overlay, Docker+Caddy compose | agent build tonight |
| 2 | Money & limits: Stripe checkout/webhook, entitlements, quotas, rate limits, MIN_TROOPS, usage_events, response minimization | agent build tonight |
| 3 | OCR: upload → vision-LLM (v2 schema) → validator → prefill; quota + caching; mocked client + fixtures | agent build tonight |
| 4 | IP & legal: SVG asset pack, phash blocklist check, ToS/Privacy (HK PDPO baseline)/refund drafts, disclaimer, CG letter draft | agent build tonight |
| 5 | Gate automation: promote.py steps 1–8, probe suite, sweep-detection job; pen-test AFTER real staging exists | agent build tonight (probes run for real once staging is up) |

**Recurring cost estimate:** Hostinger VPS (existing) + Clerk free (≤10k MAU) + Supabase free→$25/mo + OCR API usage + Stripe fees + domain ≈ **< US$40/mo pre-revenue.**

## 5. Failure modes

Planned for: Hostinger plan is shared-not-VPS (fallback: any Docker host — image is portable) · Stripe webhook loss (idempotent handlers, replay, nightly reconciliation) · OCR misreads (validator + user-confirm + never-guess; worst case = manual entry) · VPS dies (nightly Supabase backups; redeploy < 1 hr; runbook) · engine accuracy complaints (paid promise scoped to certified rungs — COMPASS §3; badges honest) · agent context decay (workstreams split across agents with written handoffs) · Clerk outage (sessions verified via cached JWKS keep working short-term; sign-ins fail gracefully).

Not planned for: DDoS beyond Cloudflare free + caps · multi-region · account sharing within alliances · chargeback abuse · Century Games demand letter · Supabase/Stripe outages.

## 6. Out of scope (v1) — mirrors COMPASS §5

G1 optimizer as paid feature · alliance/team tier · mobile app · UI i18n · referral system · admin dashboard beyond Supabase console + logs · live game integration.

## 7. Approval checkpoints

1. ~~Stage 3–5 red-team before build~~ — SKIPPED by Martin's 08-04 directive (logged risk; red-team the BUILT shell before launch instead).
2. Morning review: `DECISIONS_2026-08-04.md` — Martin can reverse any logged decision cheaply while nothing is deployed.
3. Phase 0 (Hostinger plan type) may force the hosting decision back open.
4. LAUNCH: independent QA gate PASS + Martin sign-off + COMPASS D4 scoping (certify-narrow) — unchanged and non-negotiable.
5. Century Games letter sent only with Martin's explicit approval.
