# MORNING_BRIEF — overnight build 2026-08-04 → 08-05

## TL;DR

The production shell is **built and independently evaluated**: ~152 tests green, but the evaluator issued **REVISE — 5 Critical, 15 Major, 11 Minor** (full evidence: `shell/EVAL_ROUND_1.md`). The fix round was dispatched to four agents with coordinated briefs, then **Claude's monthly spend limit cut them off before any fix landed**. Nothing is broken-on-disk: the build state is exactly as the evaluator reviewed it. Nothing was deployed; WOSTests.com is still empty (verified); the prototype engine/UI untouched (verified via mtime audit); nothing external was sent or registered.

## What exists now (all new, all inside `shell/`)

| Piece | State |
|---|---|
| Shell core (Clerk auth + DEV_BYPASS, minimize, overlay, Docker/Caddy) | Built, 33 tests |
| DB/limits/billing (full SQL schema, quotas 5/100, MIN_TROOPS, Stripe mock-first, idempotent webhook, sweep detection) | Built, 59 tests |
| OCR service (vision-LLM w/ v2 schema + your ingestion skill's validator reused unmodified, mock-first) | Built, 26 tests |
| Gate pipeline (promote.py w/ hard prod door), probes, phash blocklist (355 scraped images hashed), original SVG asset pack (22), legal drafts + CG letter (EN/中文, NOT sent) | Built, 34 tests |
| Independent evaluation | `shell/EVAL_ROUND_1.md` — REVISE |
| Supporting docs | `PRODUCTION_PLAN.md` v1.1 (Clerk), `DECISIONS_2026-08-04.md` (14 logged decisions + alternatives), `THIRD_PARTY_SETUP.md`, `shell/ARCHITECTURE.md`, `shell/BUILD_LOG.md` |

## The 5 Criticals the fix round was about to close

1. **F1** — Docker image & promote bundle omit `.claude/skills/wos-battlereport-ingestion/`; OCR 500s in the deployed layout.
2. **F2** — OCR cache reads `job_id`, DB returns `id` → second upload of any image = 500 (tests hid it by injecting a different store).
3. **F3** — verified users hardcoded plan="free"; `resolve_plan()` exists, is tested, and is called from nowhere → **paying subscribers would never get pro quotas.**
4. **F4** — no body-size cap before parse; `max_runs` enforced by nothing; n=20000 wedges a worker → 3 free accounts can stall the box.
5. **F5** — `/docs`, `/redoc`, `/openapi.json` open anonymously in staging, while promote's gate reports "debug endpoints: clean" (false-negative gate).

Also notable Majors: sign-out is a no-op (HttpOnly cookie), `skill_telemetry` leaks proc histograms + kill attribution in prod responses, disclaimer not rendered, unauth clients can fetch the full UI by omitting `Accept`, webhook path mismatch (`/shell/webhook/stripe` is the exempt canonical), empty `IP_HASH_SALT` default, unpinned requirements, two probe-suite self-contamination bugs.

## YOUR morning actions

1. **Raise the Claude spend limit** (claude.ai/settings/usage) or wait for reset — the loop needs agent capacity.
2. **Resume the loop with one instruction:** *"Run the fix round per MORNING_BRIEF §Resume, then evaluator round 2; loop until approved."* Everything a fresh session needs is in this file + `shell/EVAL_ROUND_1.md`.
3. **Review `DECISIONS_2026-08-04.md`** — 14 delegated decisions incl. skipping the red-team (recommend running it against the built shell before launch), quotas 5/100, US$7.99 placeholder price, Clerk hosted sign-in.
4. **Register accounts** (`THIRD_PARTY_SETUP.md`, ~60–90 min, independent of the fix round): FIRST verify Hostinger plan is a VPS, then Clerk, Supabase ×2, Stripe, Anthropic key, DNS (+ Cloudflare recommended).
5. Still yours from COMPASS: D1 (non-wipe experiment campaign) and D4 (certify-narrow launch scoping) — the engine, not the shell, remains the real product bottleneck.

## §Resume — fix-round briefs (coordination decisions are FINAL; one agent per letter, ownership per `shell/ARCHITECTURE.md`)

- **A** (main/config/auth/minimize/overlay/Docker/Caddy/requirements): Dockerfile COPYs the ingestion skill; wire `resolve_plan` into auth post-verify (import-guarded, default free); MAX_BODY_BYTES 413 guard + Caddy body cap; disable docs/redoc/openapi outside dev on BOTH apps; `/shell/signout` route (server-side cookie expiry); block unauth UI regardless of Accept header; reduce `skill_telemetry` in staging/prod to user-facing summary (NEVER touch verdict/engine_meta/coin_flip — invariant 3 verified intact, keep it so); disclaimer chip in overlay; fail-fast on empty IP_HASH_SALT in staging/prod; pin requirements; lock CORS outside dev; sweep A-minors.
- **B** (db/limits/billing/migrations): `resolve_plan` exported, awaitable, cached, never-raising; clamp `runs` to `entitlements.max_runs` (+tests incl. 20000→1000); canonical webhook path `/shell/webhook/stripe` everywhere; missing STRIPE_WEBHOOK_SECRET in staging/prod → refuse 503, never skip verification; sweep B-minors.
- **C** (ocr/*): skill path via settings `SKILL_INGESTION_DIR`, missing → clean 503 not 500; accept `id`/`job_id` cache keys; tests must use the app's REAL store (the lesson: a green suite hid a broken app); regression test = same image twice → 200/200, one vision call; sweep C-minors.
- **D** (promote/probes/tools/legal): bundle includes the ingestion skill + completeness assert; D4 gate actively probes docs endpoints (200 = FAIL); fix probe burst contamination + huge_body false evidence (assert new 413); add invalid-signature webhook probe; sweep D-minors.
- Then: **evaluator round 2** (fresh critical eye, same mandate: APPROVED only when zero Critical/Major and clean e2e; evidence scripts live in the session outputs as `e2e_*.sh` — recreate if absent). Loop until approved.

## Guardrail attestation (evaluator-verified)

WOSTests.com: only CLAUDE.md/AGENTS.md/PRODUCTION_LOG.md · zero source files modified tonight in `wos_sim/`, `prototype/`, `.claude/` · COMPASS invariant 3 (honesty labels) byte-identical through the minimizer · promote.py physically cannot write to WOSTests.com and refuses prod without `VERDICT: PASS` + your literal sign-off flag.
