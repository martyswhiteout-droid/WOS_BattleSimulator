"""shell/app/main.py — production-shell app assembly (Agent A).

Implements the composition model of shell/ARCHITECTURE.md and
PRODUCTION_PLAN.md §2:

    Caddy (TLS) → shell.app.main:app
      ├─ BodyLimitMiddleware (this file — outermost; 413 before anything buffers)
      ├─ CorsLockMiddleware  (this file — locks CORS to BASE_URL outside dev)
      ├─ DocsGuardMiddleware (this file — 404s /docs,/redoc,/openapi.json outside dev)
      ├─ AuthMiddleware      (auth.py)
      ├─ LimitsMiddleware    (adapter around Agent B's limits.check_and_record)
      ├─ MinimizeMiddleware  (minimize.py — staging/prod response minimization)
      ├─ OverlayMiddleware   (overlay/ — script injection into the served UI)
      ├─ /shell/* routes     (health, me, signout, legal/*; B's billing, C's ocr)
      └─ mount("/"): wos_sim.predictor.server:app  (LAST — /api/* + static UI)

Starlette runs the LAST-added middleware OUTERMOST, so add_middleware calls
below are in reverse of the request-path order above. The three new
outermost layers (F4/F5/F14, EVAL_ROUND_1.md) don't depend on auth/limits
state, so they reject what they're going to reject before the app spends
any work getting there.

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

import httpx                                       # noqa: E402
import jwt                                         # noqa: E402
from fastapi import FastAPI, Request              # noqa: E402
from fastapi.responses import JSONResponse, PlainTextResponse  # noqa: E402

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


def _scope_header(scope, name: bytes) -> str | None:
    """One decoded request header value from a raw ASGI scope."""
    for key, value in scope.get("headers") or []:
        if key.lower() == name:
            return value.decode("latin-1")
    return None


async def _send_413(send) -> None:
    payload = json.dumps({"error": "payload_too_large",
                          "message": "Request body exceeds the size limit."}).encode()
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(payload)).encode()),
                            (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": payload})


_OCR_UPLOAD_PATHS = frozenset({"/shell/ocr", "/shell/ocr/panel"})


class BodyLimitMiddleware:
    """Outermost guard: rejects an oversized request body with 413 BEFORE
    any downstream layer buffers it (F4, EVAL_ROUND_1.md — a 12 MB JSON
    body sailed through as a 200 in 9.55s because ``LimitsMiddleware``'s
    own buffering had no cap). Applies in every ENV, not just staging/prod,
    and is independent of which limits implementation (Agent B's own
    LimitsMiddleware, or this module's LimitsAdapterMiddleware fallback)
    ends up active downstream. Complements shell/Caddyfile's edge-level
    ``request_body { max_size }`` cap, so the limit still holds when the
    app is reached directly (dev, tests, a misconfigured proxy).

    Route-aware: /shell/ocr and /shell/ocr/panel get the LARGER
    ``MAX_OCR_BODY_BYTES`` instead of the default ``MAX_BODY_BYTES`` — a
    uniform tight cap would reject legitimate screenshot uploads (real
    phone captures run hundreds of KB to a few MB; Agent C's own
    ocr/panel_router.py already validates up to ~8 MB, QA D-014/D-024) long
    before Agent C's own, already-correct, already-tested size check ever
    ran. Every other path (in particular /api/predict and /api/battle,
    which is what the eval's 12 MB reproduction actually hit) keeps the
    tight default."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.default_limit = settings.MAX_BODY_BYTES
        self.ocr_limit = settings.MAX_OCR_BODY_BYTES

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = (self.ocr_limit if scope.get("path") in _OCR_UPLOAD_PATHS
                 else self.default_limit)

        content_length = _scope_header(scope, b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > limit:
                    await _send_413(send)
                    return
            except ValueError:
                pass   # malformed header: fall through to the byte-counted guard

        messages = []
        total = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            total += len(message.get("body", b""))
            if total > limit:      # chunked / no Content-Length: bound it live
                await _send_413(send)
                return
            if not message.get("more_body"):
                break

        replay = iter(messages)

        async def replayed_receive():
            for message in replay:
                return message
            return await receive()

        await self.app(scope, replayed_receive, send)


_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})


class DocsGuardMiddleware:
    """Blocks the MOUNTED sub-app's auto-generated docs outside dev (F5,
    EVAL_ROUND_1.md). The shell's own FastAPI instance already sets
    docs_url=None/redoc_url=None/openapi_url=None UNCONDITIONALLY (see
    create_app below) — but wos_sim.predictor.server:app (mounted at "/")
    sets no such override, and it is a READ-ONLY import (shell/ARCHITECTURE.md
    boundary rule 1: wos_sim/ is never edited from here), so its copy of
    /docs, /redoc, /openapi.json is closed at the shell boundary instead. A
    promote.py gate reporting "debug endpoints: clean" while these were
    live and public in staging is exactly the false-negative F5 flagged."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "") if scope["type"] == "http" else ""
        if (scope["type"] != "http" or not self.settings.is_prodlike
                or path not in _DOCS_PATHS):
            await self.app(scope, receive, send)
            return
        payload = json.dumps({"detail": "Not Found"}).encode()
        await send({"type": "http.response.start", "status": 404,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(payload)).encode())]})
        await send({"type": "http.response.body", "body": payload})


_CORS_HEADER_NAMES = frozenset({b"access-control-allow-origin",
                                b"access-control-allow-credentials"})


class CorsLockMiddleware:
    """Outside dev, rewrites CORS response headers so only the configured
    production origin (BASE_URL) is ever granted cross-origin access — no
    matter which inner layer produced the header (F14, EVAL_ROUND_1.md).
    wos_sim/predictor/server.py wires its OWN
    ``CORSMiddleware(allow_origins=["*"], ...)`` for local dev convenience;
    it is a READ-ONLY import (boundary rule 1) so it cannot be edited to be
    env-aware — the lock is enforced here, at the outermost shell layer,
    which sees (and can rewrite) every response regardless of origin."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings
        origin = (settings.BASE_URL or "").rstrip("/")
        self._allowed = origin or None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.settings.is_prodlike:
            await self.app(scope, receive, send)
            return

        request_origin = _scope_header(scope, b"origin")
        allow = self._allowed is not None and request_origin == self._allowed

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = [(n, v) for n, v in message.get("headers", [])
                           if n.lower() not in _CORS_HEADER_NAMES]
                if allow:
                    headers.append((b"access-control-allow-origin",
                                    self._allowed.encode("latin-1")))
                    headers.append((b"access-control-allow-credentials", b"true"))
                    headers.append((b"vary", b"Origin"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


async def _revoke_clerk_session(token: str, settings: Settings) -> None:
    """Best-effort Clerk session revocation for POST /shell/signout (F6,
    EVAL_ROUND_1.md extra credit beyond the binding "server-side cookie
    expiry" scope). Never raises: the Set-Cookie clear on the /shell/signout
    response is what actually ends the session for THIS browser, and that
    must land even if Clerk is unreachable, misconfigured, or this call's
    endpoint shape ever drifts from Clerk's API. Skips entirely (no network
    call) when keyless — mock-first rule."""
    if not settings.CLERK_SECRET_KEY:
        return
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
        sid = claims.get("sid")
        if not sid:
            return
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.clerk.com/v1/sessions/{sid}/revoke",
                headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"})
    except Exception:
        log.warning("Clerk session revoke failed/skipped", exc_info=True)


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


async def _usage_today_for(user_id: str, kind: str) -> int:
    """Today's recorded usage_events count for (user, kind) — "sim" | "ocr",
    the same values limits.classify_endpoint() / db.record_usage() use (M1,
    EVAL_ROUND_2.md — round 1's F13). Never raises: db.get_usage_today
    missing or failing degrades to 0 (a wrong-but-safe "full quota shown"
    display beats a broken /shell/me), same fail-open posture as
    _entitlements_for above."""
    getter = getattr(_db, "get_usage_today", None) if _db else None
    if getter is None:
        return 0
    try:
        used = getter(user_id, kind)
        if inspect.isawaitable(used):
            used = await used
        return int(used or 0)
    except Exception:
        log.exception("db.get_usage_today failed; reporting 0 usage for %s/%s",
                      user_id, kind)
        return 0


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    # Fail-fast (F11, EVAL_ROUND_1.md): an unsalted IP hash
    # (shell.app.limits.hash_ip) is a 2**32-entry rainbow table — minutes to
    # reverse the whole address space. Refuse to assemble the app at all
    # rather than silently downgrade a privacy control. Gated on
    # is_prodlike alone (NOT also dev_bypass) — DEV_BYPASS is an escape
    # hatch for auth, never for this.
    if settings.is_prodlike and not settings.IP_HASH_SALT:
        raise RuntimeError(
            f"IP_HASH_SALT is empty while ENV={settings.ENV!r} (staging/prod). "
            "An unsalted IP hash is reversible in minutes — refusing to boot. "
            "Set IP_HASH_SALT to a long random secret (see shell/.env.example).")

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
        # M1 (EVAL_ROUND_2.md, round 1's F13): "remaining" used to always
        # report the full daily quota regardless of recorded usage — the
        # overlay chip told a signed-in user "Sims left today: 5" right up
        # to the moment the 6th request 429'd. db.get_usage_today records
        # the same "sim"/"ocr" kinds limits.py's check_and_record uses.
        used_sims = await _usage_today_for(user.user_id, "sim")
        used_ocr = await _usage_today_for(user.user_id, "ocr")
        remaining = {"sims": max(0, ent["daily_sim_quota"] - used_sims),
                    "ocr": max(0, ent["daily_ocr_quota"] - used_ocr)}
        return {"user": {"user_id": user.user_id, "email": user.email,
                         "plan": user.plan},
                "entitlements": ent, "remaining": remaining,
                "env": settings.ENV, "sign_in_url": settings.sign_in_url}

    @app.post("/shell/signout", include_in_schema=False)
    async def signout(request: Request):
        """Server-side sign-out (F6, EVAL_ROUND_1.md): Clerk's __session
        cookie is HttpOnly, so client-side `document.cookie = ...` can never
        clear it — only a Set-Cookie RESPONSE header can (HttpOnly blocks
        script access, not server-set headers). Idempotent: works even with
        no/garbage cookie, so it never itself requires being authenticated
        (see EXEMPT_PATHS in auth.py)."""
        token = request.cookies.get("__session")
        if token and settings.CLERK_SECRET_KEY:
            try:
                await _revoke_clerk_session(token, settings)
            except Exception:
                log.warning("Clerk session revoke raised; cookie clear still applies",
                           exc_info=True)
        resp = JSONResponse({"status": "signed_out"})
        resp.delete_cookie("__session", path="/", secure=True, httponly=True,
                           samesite="lax")
        return resp

    @app.get("/legal/tos", include_in_schema=False)
    def legal_tos():
        """Serves shell/legal/tos.md (Agent D's content; Agent A owns the
        route). F8/F4 (EVAL_ROUND_1.md, PRODUCTION_CRITERIA F2/F4): the
        overlay's disclaimer chip links here."""
        path = _REPO_ROOT / "shell" / "legal" / "tos.md"
        if not path.is_file():
            return PlainTextResponse("Terms of Service not available.", status_code=404)
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")

    @app.get("/legal/privacy", include_in_schema=False)
    def legal_privacy():
        """Serves shell/legal/privacy.md — see legal_tos() above."""
        path = _REPO_ROOT / "shell" / "legal" / "privacy.md"
        if not path.is_file():
            return PlainTextResponse("Privacy Policy not available.", status_code=404)
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")

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

    try:
        from shell.app.ocr.panel_router import router as _ocr_panel_router
        app.include_router(_ocr_panel_router)
    except ImportError:
        pass

    # shell/app/ocr/client/ is mounted as static so the browser can `import`
    # ocr_flow.js's sibling ES modules (flow_state.mjs, panel_parser.mjs,
    # engine_tesseract.mjs) and fetch the vendored tesseract.js/WASM assets at
    # runtime — OverlayMiddleware only injects <link>/<script> TAGS for
    # ocr_flow.js/.css, it does not serve any file itself.
    from pathlib import Path as _Path
    from starlette.staticfiles import StaticFiles as _StaticFiles
    _ocr_client_dir = _Path(__file__).resolve().parent / "ocr" / "client"
    app.mount("/shell/ocr/client", _StaticFiles(directory=str(_ocr_client_dir)),
              name="ocr_client_assets")

    # shell/assets_prod/ — the original SVG emblem pack (class/generation/
    # rarity/role badges), mounted at /shell/assets/ (M3, EVAL_ROUND_1.md
    # F18 / EVAL_ROUND_2.md M3). A promoted bundle strips ALL raster art from
    # prototype/ and wos_sim/ before it ships (promote.py step3_assemble —
    # Century Games IP never ships), but the mounted prototype's own JS still
    # emits <img src="avatars/...">, "assets/Icons/*.png" etc unconditionally,
    # so those requests 404 in that exact deployment. prototype/ is READ-ONLY
    # from shell/ (ARCHITECTURE.md boundary rule 1), so the replacement pack
    # is served here and overlay.js's asset-fallback listener swaps broken
    # <img> tags onto it (or hides them) at runtime instead of editing the
    # prototype. Guarded on the directory existing so a stripped/missing
    # assets_prod never takes the boot down (fail-safe, same posture as the
    # sim mount below).
    _assets_prod_dir = _REPO_ROOT / "shell" / "assets_prod"
    if _assets_prod_dir.is_dir():
        app.mount("/shell/assets", _StaticFiles(directory=str(_assets_prod_dir)),
                  name="assets_prod")

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
    app.add_middleware(AuthMiddleware, settings=settings)
    # Outermost three: none of these depend on auth/limits state, and each
    # closes a seam the eval reproduced live (F5/F14/F4 — EVAL_ROUND_1.md).
    app.add_middleware(DocsGuardMiddleware, settings=settings)
    app.add_middleware(CorsLockMiddleware, settings=settings)
    app.add_middleware(BodyLimitMiddleware, settings=settings)         # outermost

    return app


app = create_app()
