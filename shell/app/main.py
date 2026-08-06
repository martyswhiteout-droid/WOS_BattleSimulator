"""shell/app/main.py — production-shell app assembly (Agent A).

Implements the composition model of shell/ARCHITECTURE.md and
PRODUCTION_PLAN.md §2:

    Caddy (TLS) → shell.app.main:app
      ├─ AuthMiddleware      (auth.py — outermost)
      ├─ LimitsMiddleware    (adapter around Agent B's limits.check_and_record)
      ├─ MinimizeMiddleware  (minimize.py — staging/prod response minimization)
      ├─ OverlayMiddleware   (overlay/ — script injection into the served UI)
      ├─ /shell/* routes     (health, me, overlay assets; B's billing, C's ocr)
      └─ mount("/"): wos_sim.predictor.server:app  (LAST — /api/* + static UI)

Starlette runs the LAST-added middleware OUTERMOST, so add_middleware calls
below are in reverse of the request-path order above.

sys.path: importing ``shell.app.main`` already requires the REPO ROOT on
sys.path — run from the repo root (``uvicorn shell.app.main:app --port 8200``
puts the cwd there). This module ALSO inserts the repo root derived from
``__file__`` (two levels up) before importing ``wos_sim``, so app-dir tricks,
Docker, and IDE test runners work regardless of cwd.

Cross-agent imports (Agent B's db/limits/billing, Agent C's ocr) are inside
try/except ImportError with graceful no-op fallbacks, so this module is fully
functional keyless and BEFORE those modules land.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import logging
import sys
from pathlib import Path

# --- repo root on sys.path (see module docstring) -------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI, Request              # noqa: E402
from fastapi.responses import JSONResponse        # noqa: E402

from shell.app import overlay                     # noqa: E402
from shell.app.auth import AuthMiddleware, UserCtx  # noqa: E402
from shell.app.config import Settings, get_settings  # noqa: E402
from shell.app.minimize import MinimizeMiddleware  # noqa: E402

log = logging.getLogger("wos.shell")

# --- other agents' modules: import if present, degrade if not -------------
# Broad except (not just ImportError): agents build concurrently, and a
# transiently broken limits.py/db.py must degrade the shell, not crash it.
try:
    from shell.app import limits as _limits       # Agent B (quota/rate/MIN_TROOPS)
except Exception:                                 # TODO(Agent B): no-op until limits.py lands
    log.warning("shell.app.limits unavailable — quota/rate/MIN_TROOPS NOT enforced")
    _limits = None

try:
    from shell.app import db as _db               # Agent B (entitlements/usage)
except Exception:                                 # TODO(Agent B): no-op until db.py lands
    log.warning("shell.app.db unavailable — using config-default entitlements")
    _db = None


_GUARDED_PATHS = frozenset({"/api/predict", "/api/battle", "/shell/ocr"})


class LimitsAdapterMiddleware:
    """Thin ASGI adapter that feeds Agent B's contract function

        limits.check_and_record(user, endpoint, body, ip_hash) -> LimitVerdict

    for the guarded endpoints. While limits.py is absent (or exposes no
    check_and_record) this is a pass-through, so Agent A's build works alone.
    A Denied verdict is recognized by an integer ``status`` attribute (the
    contract's Denied(status, code, message)); anything else is Allowed.
    Adapter errors fail OPEN with a log line — auth stays enforced either way,
    and a broken quota layer must not take the product down."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        check = getattr(_limits, "check_and_record", None) if _limits else None
        if (scope["type"] != "http" or check is None
                or scope.get("path") not in _GUARDED_PATHS):
            await self.app(scope, receive, send)
            return

        # buffer the request body so it can be inspected AND replayed downstream
        messages = []
        raw = b""
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            raw += message.get("body", b"")
            if not message.get("more_body"):
                break

        try:
            body = json.loads(raw.decode("utf-8")) if raw else None
            if not isinstance(body, dict):
                body = None
        except Exception:
            body = None
        user = (scope.get("state") or {}).get("user")
        client = scope.get("client") or ("", 0)
        ip_hash = hashlib.sha256(str(client[0]).encode("utf-8")).hexdigest()

        verdict = None
        try:
            result = check(user, scope["path"], body, ip_hash)
            verdict = await result if inspect.isawaitable(result) else result
        except Exception:
            log.exception("limits.check_and_record failed; failing open")

        status = getattr(verdict, "status", None)
        if isinstance(status, int):          # Denied(status, code, message)
            payload = json.dumps({"error": getattr(verdict, "code", "denied"),
                                  "message": getattr(verdict, "message", "")}).encode()
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(payload)).encode()),
                                    (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": payload})
            return

        replay = iter(messages)

        async def replayed_receive():
            for message in replay:
                return message
            return await receive()

        await self.app(scope, replayed_receive, send)


async def _entitlements_for(plan: str, settings: Settings) -> dict:
    """Daily quotas for a plan. Prefers Agent B's db.get_entitlements(plan)
    (single source of truth = entitlements table; sync or async accepted);
    keyless/dev fallback uses the config defaults."""
    ent = None
    getter = getattr(_db, "get_entitlements", None) if _db else None
    if getter is not None:
        try:
            ent = getter(plan)
            if inspect.isawaitable(ent):
                ent = await ent
        except Exception:
            ent = None
            log.exception("db.get_entitlements failed; using config defaults")
    if ent is not None:
        sims = getattr(ent, "daily_sim_quota", None)
        ocr = getattr(ent, "daily_ocr_quota", None)
        if isinstance(ent, dict):
            sims, ocr = ent.get("daily_sim_quota", sims), ent.get("daily_ocr_quota", ocr)
        if sims is not None:
            return {"daily_sim_quota": int(sims), "daily_ocr_quota": int(ocr or 0)}
    if plan == "pro":
        return {"daily_sim_quota": settings.PRO_SIMS_PER_DAY,
                "daily_ocr_quota": settings.PRO_OCR_PER_DAY}
    return {"daily_sim_quota": settings.FREE_SIMS_PER_DAY, "daily_ocr_quota": 0}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="WoS Battle Simulator — production shell",
                  version="0.1", docs_url=None, redoc_url=None, openapi_url=None)

    # ---- /shell routes ---------------------------------------------------

    @app.get("/shell/health", include_in_schema=False)
    def health():
        return {"status": "ok", "env": settings.ENV,
                "dev_bypass": settings.dev_bypass, "sim_mounted": sim_mounted}

    @app.get("/shell/me", include_in_schema=False)
    async def me(request: Request):
        user: UserCtx | None = getattr(request.state, "user", None)
        if user is None:      # AuthMiddleware already 401s; this is defense in depth
            return JSONResponse(status_code=401,
                                content={"error": "auth_required",
                                         "sign_in_url": settings.sign_in_url})
        ent = await _entitlements_for(user.plan, settings)
        # TODO(Agent B): subtract today's usage_events once db.py exposes a
        # usage query; until then "remaining" reports the full daily quota.
        remaining = {"sims": ent["daily_sim_quota"], "ocr": ent["daily_ocr_quota"]}
        return {"user": {"user_id": user.user_id, "email": user.email,
                         "plan": user.plan},
                "entitlements": ent, "remaining": remaining,
                "env": settings.ENV, "sign_in_url": settings.sign_in_url}

    app.include_router(overlay.router)

    # Agent B's billing routes (checkout + Stripe webhook), when they land.
    try:
        from shell.app import billing as _billing   # TODO(Agent B): router pending
        _billing_router = getattr(_billing, "router", None)
        if _billing_router is not None:
            app.include_router(_billing_router)
    except ImportError:
        pass

    # Agent C's OCR route (POST /shell/ocr), when it lands.
    try:
        from shell.app.ocr.router import router as _ocr_router  # TODO(Agent C): pending
        app.include_router(_ocr_router)
    except ImportError:
        pass

    # ---- mount the untouched prototype app LAST (so /shell/* wins) -------
    sim_mounted = False
    try:
        from wos_sim.predictor.server import app as sim_app
        app.mount("/", sim_app)
        sim_mounted = True
    except ImportError:
        log.exception("wos_sim.predictor.server not importable — shell is up "
                      "but the simulator is NOT mounted (check numpy/openpyxl "
                      "and that the repo root is intact)")

    # ---- middlewares: LAST added runs OUTERMOST --------------------------
    app.add_middleware(overlay.OverlayMiddleware, settings=settings)   # innermost
    app.add_middleware(MinimizeMiddleware, settings=settings)
    # Limits layer: Agent B's own middleware when it has landed (adds the
    # global-concurrency semaphore); otherwise my thin adapter around the
    # check_and_record contract; otherwise (keyless, pre-Agent-B) nothing.
    _their_mw = getattr(_limits, "LimitsMiddleware", None) if _limits else None
    if _their_mw is not None:
        app.add_middleware(_their_mw)
    else:
        app.add_middleware(LimitsAdapterMiddleware, settings=settings)
    app.add_middleware(AuthMiddleware, settings=settings)              # outermost

    return app


app = create_app()
