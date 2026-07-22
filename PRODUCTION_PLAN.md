# PRODUCTION_PLAN — Prototype → Monetized SaaS (Stage-2 draft, 2026-07-11)

**Status: DRAFT for Martin's review.** Produced under the architectural-review discipline (Stage 2 of 5). After Martin endorses this draft, Stage 3 produces a self-critical technical brief and Stage 4 a red-team prompt for independent attack by 2–3 other AI models. Do not execute this plan until red-team triage (Stage 5) is complete.

Decisions assumed (Martin 2026-07-11, changeable): **Supabase** (Postgres + auth), **Hostinger VPS** hosting (Docker; VERIFY the plan is a VPS, not shared hosting), **IP posture:** hero names + original class iconography at launch, permission letter to Century Games in parallel; **tiers:** free manual sims / paid OCR + higher quotas.

---

## 1. Objectives

- A paying customer can: sign up → verify email → subscribe via Stripe → upload a battle-report screenshot → get a simulation verdict — without Martin touching anything.
- The prototype repo stays **clean**: no auth, paywall, or database code ever enters `E:\WOS\Battle Simulator`. Martin keeps iterating on engine + UI exactly as today.
- Promoting a prototype release to production is a **repeatable, mostly-automated pipeline** ("the gate"), not a manual integration project each time.
- Everything that ships passes `PRODUCTION_CRITERIA.md` v2 with an independent QA gate report and Martin's sign-off, logged in `WOSTests.com\PRODUCTION_LOG.md`.

**Success by end of plan:** staging environment live with one test subscriber end-to-end; first gate report produced; production launch is then a sign-off decision, not a build task.

## 2. Architecture — the shell pattern

Core idea: build the production wrapper ONCE as its own long-lived codebase ("the shell"). Each release, the pipeline snaps the current prototype into the shell. The prototype is the phone; the shell is the case; the pipeline is the assembly line.

```
┌─ PROTOTYPE repo (E:\WOS\Battle Simulator) ──────────────┐
│  wos_sim/ engine + predictor    prototype/index.html    │
│  (no auth, no db, no paywall — unchanged forever)       │
└──────────────── git tag: release-YYYY-MM-DD ────────────┘
                          │  pipeline pulls tagged artifact
                          ▼
┌─ SHELL repo (new: wos-shell) ───────────────────────────┐
│  FastAPI wrapper app:                                    │
│   • session-cookie auth (Supabase)                       │
│   • quota + rate-limit middleware                        │
│   • Stripe billing + webhook                             │
│   • OCR service endpoint                                 │
│   • production config (MIN_TROOPS=5000, caps, timeouts)  │
│   • IP-safe asset pack (swappable directory)             │
│   • small JS overlay (login/quota/upgrade UI, injected   │
│     at serve time — prototype index.html NOT edited)     │
│  mounts → wos_sim.predictor.api (the existing seam)      │
└──────────────────────────────────────────────────────────┘
                          │  Docker build
                          ▼
        staging.wostests.com  ──gate probes + QA report──▶  wostests.com
              (Hostinger VPS, docker compose: app + caddy + backups)
```

Why this works with zero prototype changes:
- The prototype UI already talks to the backend only via `POST /api/predict` and `/api/battle`. Behind **session-cookie auth**, those same fetch calls carry credentials automatically — `index.html` runs unmodified.
- The engine is already only reachable through `wos_sim/predictor/api.py` (the seam). The shell imports it like any package; middleware wraps it.
- Login page, quota meter, and upgrade prompts are a separate small overlay script the shell injects when serving the UI — additive, never editing the prototype file.

### 2.1 Environments

| Env | Where | Purpose | Stripe | Data |
|---|---|---|---|---|
| Prototype | local (`E:\WOS\Battle Simulator`) | Martin's daily work; micro battles ALLOWED; no auth | none | none |
| Staging | `staging.wostests.com` (same VPS, second compose stack) | full shell; gate probes run here; QA agent tests here | test keys | throwaway Supabase project |
| Production | `wostests.com` | paying users | live keys | production Supabase project |

`E:\WOS\WOSTests.com` (the folder) holds the release artifacts + gate reports + PRODUCTION_LOG — the auditable record of what is deployed.

### 2.2 Data model (Supabase / Postgres)

- `auth.users` — Supabase-managed (email+password, email verification on).
- `profiles` — display name, game server, created_at.
- `subscriptions` — stripe_customer_id, stripe_subscription_id, plan, status, current_period_end. **Updated ONLY by verified Stripe webhook or admin.**
- `entitlements` — derived view/table: plan → daily_sim_quota, daily_ocr_quota, max_runs.
- `usage_events` — append-only: user_id, ip_hash, endpoint, request_fingerprint (hashed normalized payload), troops_own, troops_enemy, ts. Feeds quotas AND sweep detection (D3: many near-identical fingerprints with one field stepped).
- `ocr_jobs` — upload ref, status, extracted JSON, validator verdict, cost.
- `saved_scenarios` — user's saved setups (schema_version field mandatory, per B1).
- `audit_log` — admin/security events.

Row-level security ON for all user tables. The engine remains stateless — Postgres holds user/business state only.

### 2.3 OCR service (the killer paid feature)

The spec ALREADY EXISTS: `.claude/skills/wos-battlereport-ingestion/` (deterministic v2 schema, Type-1/Type-2 rules, never-fabricate, `validate_report.py`). Production OCR = that skill industrialized:

1. User uploads screenshot(s) → stored (size/type-limited, stripped of EXIF).
2. Vision-LLM call (Claude/Gemini via API) with the v2 schema as the extraction contract; temperature 0; "if a field is not visible, return null — NEVER guess" (the skill's never-fabricate rule, verbatim).
3. Server runs `validate_report.py` logic on the output; failures → user sees "couldn't read these fields, please enter manually" (partial prefill, honest).
4. Result prefills the sim form; user confirms before running.

Notes: WoS screenshots come in many languages and resolutions — vision LLMs handle this far better than classical OCR (Tesseract would need per-language templates; wrong tool). Cost ≈ US$0.01–0.05/screenshot → paid-tier only, quota-metered, results cached by image hash (same screenshot re-uploaded = no second API call). The LLM sees only the user's own screenshot — no engine internals in the prompt (anti-distillation D4 respected).

### 2.4 Anti-distillation & security config (per PRODUCTION_CRITERIA v2 §C–E)

Enforced in the shell, configured per-environment, NEVER in the prototype:
- `MIN_TROOPS_PER_SIDE = 5000` (prod/staging; prototype exempt — calibration needs micro battles).
- Quotas: free 5 sims/day, 0 OCR; paid ~100 sims/day, ~30 OCR/day (tune later). Burst ≤5/min/account; per-IP caps; global concurrency cap; request body limits; timeouts.
- Response minimization: strip `skill_telemetry` internals/debug fields from prod responses; survivor figures banded (no noise — honesty design preserved).
- Sweep detection: nightly job over `usage_events` fingerprints → flag → throttle + email Martin.
- Secrets in VPS env vars only; HTTPS via Caddy (auto-TLS); CORS locked to the domain; ToS forbids reverse engineering/bulk querying (D6).

### 2.5 IP-safe asset pack (per §F)

- `assets_prod/` in the shell replaces scraped art: hero NAMES as text + original class/generation/role token art (AI-generate ORIGINAL iconography — not variants of Century Games characters; brief: "original fantasy class emblem, ice/survival theme" — nothing trained to resemble specific heroes).
- Pipeline asset-swap step + an automated check: perceptual-hash blocklist of known scraped images — build FAILS if any blocklisted image is in the bundle (turns F1 from a promise into a machine check).
- Disclaimer in footer: "Fan-made tool. Not affiliated with or endorsed by Century Games." Game name used nominatively only; not in logo/branding.
- Parallel track: permission/partnership letter to Century Games (draft in Phase 4; send when Martin approves). If granted, asset pack upgrades are config, not code.
- User-uploaded screenshots displayed back to the uploading user are their content — acceptable; do not build galleries of them.

## 3. The gate pipeline (the "transformer")

One script/CI job, `promote.py` (lives in the shell repo), fully repeatable:

```
1  INPUT: prototype git tag (e.g. release-2026-08-01)
2  Pull tagged artifact (wos_sim + prototype/index.html + assets manifest)
3  Run prototype-side checks:      pytest ▸ regression ▸ backtest ≥ baseline (A1–A3)
4  Assemble: shell + artifact + assets_prod + prod config
5  Static gates: no blocklisted images ▸ no debug endpoints ▸ no secrets in bundle ▸ UTF-8 check
6  Build Docker image, deploy → STAGING
7  Automated staging probes: anonymous /api/predict → 401 ▸ sub-5000 troops → 400 ▸
   burst > limit → 429 ▸ free account calling OCR → 402/403 ▸ Stripe test checkout+webhook round-trip ▸
   adversarial payload suite → clean 400s (QA_PROMPT.md)
8  Emit draft Gate Report (PRODUCTION_CRITERIA template) with all machine evidence filled in
9  HUMAN GATE: independent QA agent completes remaining items (§B–F judgment calls) → verdict
10 HUMAN GATE: Martin sign-off
11 Promote same image staging → production; append PRODUCTION_LOG.md; archive artifacts to E:\WOS\WOSTests.com
```

Steps 1–8 are autonomous. Steps 9–10 are deliberately human — per the gatekeeper rule, no exceptions. "Repeatable without writing new code" = true from the second release onward; the shell itself is the one-time build below.

## 4. Phases & budgets (solo + agents, part-time; estimates ×1.5 for reality)

| Phase | Scope | Est. |
|---|---|---|
| 0 | Accounts & decisions: verify Hostinger plan is VPS (BLOCKER if not); Supabase projects (staging+prod); Stripe account; DNS for staging./www | 0.5 day |
| 1 | Shell skeleton: repo, Docker+Caddy compose, Supabase session-cookie auth, login/signup overlay, serve prototype UI behind auth, deploy staging | 1–2 wks |
| 2 | Money & limits: Stripe checkout + webhook → subscriptions; entitlement middleware; quotas, rate limits, MIN_TROOPS, usage_events, response minimization | 1 wk |
| 3 | OCR service: upload → vision-LLM (v2 schema) → validator → prefill; quota + caching; failure UX | 1 wk |
| 4 | IP & legal: original asset pack; phash blocklist check; ToS/Privacy (HK PDPO baseline)/refund pages; disclaimer; Century Games letter drafted | 3–4 days |
| 5 | Gate automation & hardening: `promote.py` steps 1–8; staging probe suite; pen-test pass (OWASP Top 10); sweep-detection job; backups+restore drill; first full Gate Report on staging | 1 wk |

Order is deliberate: auth before money, money before OCR (OCR is paid-only), gate automation last because it tests everything before it.

**Recurring cost estimate:** Hostinger VPS (existing) + Supabase free→$25/mo + OCR API usage (variable, paid by subscribers' quota pricing) + Stripe fees + domain ≈ **< US$40/mo pre-revenue.**

## 5. Failure modes

Planned for: Hostinger plan is shared-not-VPS (Phase 0 check; fallback = any Docker host, image is portable) · Stripe webhook loss (idempotent handlers, replay from dashboard, nightly reconciliation job) · OCR misreads (validator + user-confirm step + "never guess" rule; worst case = manual entry, the free-tier path) · VPS dies (nightly Supabase backups; compose file + image re-deployable in <1 hr; document the runbook) · engine accuracy complaints (paid promise scoped to winner/ranking — the certified scope; badges stay honest) · agent context decay during the build (phases are separate sessions; each ends with a written handoff).

Not planned for (red team, please attack): DDoS beyond basic caps on a single VPS · multi-region/scale beyond one box · account sharing between alliance members · chargeback abuse · Century Games responding with a demand rather than silence/consent · Supabase or Stripe outages.

## 6. Out of scope (v1)

G1 optimizer as a paid feature (engine not certified for it) · alliance/team tier · mobile app · UI i18n (OCR handles non-EN screenshots; UI stays EN) · affiliate/referral system · admin dashboard beyond Supabase console + logs.

## 7. Approval checkpoints

1. **Now:** Martin endorses/amends this draft → Stage 3 (technical brief) + Stage 4 (red-team prompt for Codex/DeepSeek/Gemini).
2. After red-team triage: plan v2 → execution approval.
3. Phase 0 result (Hostinger plan type) may force the hosting decision back open.
4. Per-phase completion check-ins; Phases are separate agent sessions.
5. The permission letter to Century Games is sent only with Martin's explicit approval of its wording.
