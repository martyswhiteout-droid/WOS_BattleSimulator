# shell/ARCHITECTURE.md — binding brief for all shell build agents

**The shell is the production wrapper around the untouched prototype.** Read `PRODUCTION_PLAN.md` v1.1 for the why. This file is the HOW and the law for anyone writing code in `shell/`.

## Boundary rules (absolute)

1. **Never modify anything outside `shell/`.** `wos_sim/` and `prototype/` are READ-ONLY imports. No edits to prototype files, ever — the overlay pattern exists precisely so we don't.
2. **Mock-first:** every external service (Clerk, Stripe, Supabase, Anthropic) must work in mock/dev mode with NO keys present (`DEV_BYPASS=1`). Real keys activate real clients via config only. All tests run keyless.
3. Production limits (MIN_TROOPS etc.) live HERE, never back-ported into the prototype.
4. Respect COMPASS invariants 3, 5, 6, 8 (honesty labels untouched; prototype clean; assume hostile client; never fabricate OCR fields).
5. Own only your files (ownership table below). Do not create/edit files owned by another agent. Shared contracts are defined here — code to them.

## Composition model

The shell wraps the existing FastAPI app as ASGI middleware layers:

```
Caddy (TLS) → shell.app.main:app
  ├─ AuthMiddleware        (auth.py: Clerk JWT via JWKS | DEV_BYPASS mock)
  ├─ LimitsMiddleware      (limits.py: quota, rate, burst, MIN_TROOPS, usage_events)
  ├─ MinimizeMiddleware    (minimize.py: strip debug/telemetry fields, band survivors)
  ├─ OverlayMiddleware     (overlay/: inject <script src=/shell/overlay.js> into index.html)
  ├─ /shell/* routes       (billing checkout/webhook, ocr, me/quota endpoints)
  └─ mount: wos_sim.predictor.server.app   (serves /api/predict, /api/battle, static UI)
```

Dev run (repo root): `pip install -r shell/requirements.txt && DEV_BYPASS=1 uvicorn shell.app.main:app --port 8200`

## Directory & ownership

| Path | Owner | Contents |
|---|---|---|
| `shell/app/main.py`, `config.py`, `auth.py`, `minimize.py`, `overlay/` | **Agent A** | App assembly, settings (pydantic-settings, every env key), Clerk JWKS verify + DEV_BYPASS, response minimization, overlay JS/CSS + injection middleware |
| `shell/Dockerfile`, `docker-compose.yml`, `Caddyfile`, `.env.example`, `README.md`, `requirements.txt` | **Agent A** | Runtime + docs. requirements.txt starts from the pinned list below |
| `shell/app/db.py`, `limits.py`, `billing/` (`stripe_client.py`, `webhook.py`, `entitlements.py`), `shell/db/migrations/*.sql` | **Agent B** | Postgres access layer, quota/rate/MIN_TROOPS middleware, Stripe checkout + idempotent webhook, entitlement logic, full schema (tables per PRODUCTION_PLAN §2.2) |
| `shell/app/ocr/` (`router.py`, `vision.py`, `extract.py`, `cache.py`) | **Agent C** | Upload endpoint, Anthropic vision client (+`OCR_MOCK`), v2-schema extraction prompt from `.claude/skills/wos-battlereport-ingestion/references/schema.md`, validator adapter reusing `scripts/validate_report.py` logic, image-hash cache |
| `shell/promote.py`, `probes/`, `tools/phash_blocklist.py`, `assets_prod/`, `legal/` | **Agent D** | Gate pipeline steps 1–8, staging probe suite (runnable vs any base URL), perceptual-hash blocklist builder + checker, original SVG emblem pack + manifest, ToS/Privacy/refund drafts, Century Games letter draft |
| `shell/tests/test_<module>_*.py` | each agent | Name tests after your module; no shared test files |

## Shared contracts (code to these EXACTLY)

```python
# auth.py provides (Agent A):
@dataclass
class UserCtx:
    user_id: str          # clerk_user_id or "dev_user"
    email: str | None
    plan: str             # "free" | "pro" (dev: from X-Dev-Plan header, default "free")
# available to downstream as request.state.user (None if unauthenticated)
# Unauthenticated /api/* or /shell/* (except webhook, health, overlay.js) → 401 JSON {"error":"auth_required","sign_in_url":...}

# limits.py provides (Agent B):
async def check_and_record(user: UserCtx, endpoint: str, body: dict | None, ip_hash: str) -> LimitVerdict
# LimitVerdict = Allowed(allowed: bool = True, body: dict | None = None) | Denied(status: int, code: str, message: str)
# Denials: 400 below_min_troops · 402 payment_required (OCR on free) · 429 quota_exhausted / burst
# Allowed.body: non-None ONLY when check_and_record modified the request (today:
# sim "n" clamped down to entitlements.max_runs, fix-round F4-b). Backward
# compatible — existing `Allowed()` / `isinstance(verdict, Allowed)` callers are
# unaffected. Callers that forward the request downstream MUST prefer this over
# the original body when set (limits.LimitsMiddleware does; it is the
# middleware main.py's create_app() actually wires, preferred over Agent A's
# fallback adapter whenever shell.app.limits.LimitsMiddleware is importable).
# MIN_TROOPS check: body["own"]["troops_total"] and body["enemy"]["troops_total"] >= settings.min_troops_per_side

# db.py provides (Agent B):  get_pool(), record_usage(...), get_entitlements(plan) -> Entitlements
# In DEV_BYPASS with no DATABASE_URL: in-memory fallback implementing the same functions (so A/C tests run keyless)

# ocr/router.py exposes (Agent C):  POST /shell/ocr  (multipart image) →
#   {"status":"ok"|"partial"|"failed", "profile": <BRD §9 partial or null>, "unreadable_fields":[...], "job_id":...}

# config.py keys (Agent A defines; all optional with dev defaults):
# DEV_BYPASS, CLERK_PUBLISHABLE_KEY, CLERK_SECRET_KEY, CLERK_JWKS_URL, SUPABASE_URL,
# SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET,
# STRIPE_PRICE_ID_PRO, ANTHROPIC_API_KEY, GEMINI_API_KEY, OCR_MOCK, MIN_TROOPS_PER_SIDE=5000,
# FREE_SIMS_PER_DAY=5, PRO_SIMS_PER_DAY=100, PRO_OCR_PER_DAY=30, BURST_PER_MIN=5,
# GLOBAL_CONCURRENCY=8, BASE_URL, ENV=dev|staging|prod
```

## Pinned base dependencies (Agent A's requirements.txt; others ADD ONLY, never remove)

fastapi, uvicorn, pydantic>=2, pydantic-settings, PyJWT[crypto], httpx, stripe, asyncpg, anthropic, pillow, imagehash, python-multipart, pytest, pytest-asyncio

## Definition of done (every agent)

1. Your module imports cleanly and `pytest shell/tests/test_<yourmodule>*` passes **keyless** in the Linux sandbox (`pip install --break-system-packages -r shell/requirements.txt` plus repo-root deps `numpy openpyxl` if you import wos_sim).
2. Docstring at top of each file: purpose + which plan section it implements.
3. A `HANDOFF.md` appended under your section in `shell/BUILD_LOG.md`: what you built, what's mocked, what needs real keys, known gaps.
4. You did not touch files outside your ownership rows.
