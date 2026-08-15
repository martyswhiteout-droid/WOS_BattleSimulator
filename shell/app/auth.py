"""shell/app/auth.py — Clerk session verification + DEV_BYPASS mock (Agent A).

Implements PRODUCTION_PLAN.md §2 (Clerk auth; ``__session`` JWT verified
server-side via JWKS) as a pure-ASGI middleware, per the shared contract in
shell/ARCHITECTURE.md:

* ``UserCtx`` dataclass exposed to downstream layers as ``request.state.user``
  (``None`` when unauthenticated).
* DEV_BYPASS mode (keyless): every request gets
  ``UserCtx(user_id="dev_user", plan=<X-Dev-Plan header or
  settings.dev_default_plan>)`` — the default is "pro" in ENV=dev only
  (localhost works without the plan gate) and hard-collapses to "free" in
  any other ENV (config.py property). The X-Dev-Plan header is honored ONLY
  in bypass mode — never in real mode (hostile-client rule, COMPASS
  invariant 6).
* Real mode: RS256 JWT from the ``__session`` cookie (or Authorization:
  Bearer), verified against Clerk's JWKS fetched with httpx and cached with a
  TTL. ``exp`` is verified (PyJWT default, small leeway); ``azp`` is checked
  only when present AND BASE_URL is configured.
* Unauthenticated ``/api/*`` and ``/shell/*`` (except the exempt set below)
  → 401 JSON ``{"error": "auth_required", "sign_in_url": ...}``.
  Unauthenticated HTML page requests → 307 redirect to the hosted sign-in.
  Other unauthenticated requests (fonts/images/css assets) pass through —
  they expose no engine data and the page itself already redirected.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from urllib.parse import quote

import httpx
import jwt

from .config import Settings

log = logging.getLogger("wos.shell.auth")

# Paths reachable WITHOUT auth (shell/ARCHITECTURE.md + build brief):
# Stripe signs its own webhook, health is for probes/monitors, the overlay
# assets must load on any page state (they render the signed-out chip too),
# /shell/signout must work even with a stale/garbage cookie, and the legal
# pages the disclaimer chip links to must be readable before signing up.
EXEMPT_PATHS = frozenset({
    "/shell/webhook/stripe",
    "/shell/health",
    "/shell/overlay.js",
    "/shell/overlay.css",
    "/shell/signout",
    "/legal/tos",
    "/legal/privacy",
})

# Path PREFIXES reachable without auth, in addition to the exact matches
# above. shell/app/ocr/client/ is a static mount (main.py) the browser needs
# in order to `import` ocr_flow.js's sibling ES modules and vendored
# tesseract.js/WASM assets — OverlayMiddleware injects <script>/<link> tags
# for these UNCONDITIONALLY (auth state is not checked at injection time),
# so they must stay loadable pre-auth, same as overlay.js/css above.
EXEMPT_PREFIXES = ("/shell/ocr/client/",)


def _is_exempt(path: str) -> bool:
    return path in EXEMPT_PATHS or any(path.startswith(p) for p in EXEMPT_PREFIXES)


_ALGORITHMS = ["RS256"]
_LEEWAY_S = 10


@dataclass
class UserCtx:
    """Shared contract (shell/ARCHITECTURE.md) — do not extend without
    updating the contract; Agents B/C code against exactly these fields."""
    user_id: str          # clerk_user_id or "dev_user"
    email: str | None
    plan: str             # "free" | "pro"


async def _fetch_jwks(url: str) -> dict:
    """One JWKS fetch. Module-level so tests can monkeypatch it keylessly."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


class JWKSCache:
    """kid -> PyJWK map with TTL refresh. A miss on an unknown kid triggers a
    refetch at most every ``min_refresh_s`` (key rotation without hammering).

    M2 (EVAL_ROUND_1.md F16 / EVAL_ROUND_2.md M2 — carried over unfixed
    across round 1): the ``or not self._keys`` clause used to bypass
    ``min_refresh_s`` entirely whenever the cache was empty. A FAILED fetch
    always leaves ``_keys`` empty, so a Clerk outage (or simply a fresh
    process start hitting a slow/down JWKS endpoint) meant EVERY
    authenticated request triggered a fresh ~5s httpx fetch, forever — no
    backoff, and no protection against a thundering herd of concurrent
    requests each starting their own fetch. Fixed with exponential backoff
    tracked independently of ``_fetched_at`` (which only advances on
    SUCCESS) via ``_last_attempt_at``/``_consecutive_failures``, plus an
    ``asyncio.Lock`` serializing the actual fetch attempt so N concurrent
    callers during a cold/failing cache produce exactly ONE underlying
    fetch, not N. Auth still fails closed for unverifiable tokens regardless
    of why the cache is stale — ``key_for`` never raises, and a missing key
    for a given kid still returns None either way."""

    def __init__(self, url: str, ttl_s: float = 3600.0, min_refresh_s: float = 30.0,
                 backoff_cap_s: float = 300.0):
        self.url = url
        self.ttl_s = ttl_s
        self.min_refresh_s = min_refresh_s
        self.backoff_cap_s = backoff_cap_s   # F16's suggested 30s -> 5min ceiling
        self._keys: dict = {}
        self._fetched_at: float = 0.0
        self._last_attempt_at: float = 0.0
        self._consecutive_failures: int = 0
        self._lock = asyncio.Lock()

    def _retry_delay(self) -> float:
        """Backoff after N consecutive failures: min_refresh_s, then doubling
        (min_refresh_s, 2x, 4x, ...), capped at backoff_cap_s. Only
        meaningful once _consecutive_failures >= 1."""
        delay = self.min_refresh_s * (2 ** max(0, self._consecutive_failures - 1))
        return min(delay, self.backoff_cap_s)

    def _due(self, kid: str, now: float) -> bool:
        age = now - self._fetched_at
        return (age > self.ttl_s
                or (kid not in self._keys and age > self.min_refresh_s)
                or not self._keys)

    def _backed_off(self, now: float) -> bool:
        return (self._consecutive_failures > 0
                and now - self._last_attempt_at < self._retry_delay())

    async def _refresh(self) -> None:
        data = await _fetch_jwks(self.url)
        keys = {}
        for entry in data.get("keys", []):
            kid = entry.get("kid")
            if not kid:
                continue
            try:
                keys[kid] = jwt.PyJWK(entry)
            except Exception:      # unsupported kty/alg entry — skip, don't fail auth
                continue
        self._keys = keys
        self._fetched_at = time.monotonic()
        self._consecutive_failures = 0

    async def key_for(self, kid: str | None):
        if not kid:
            return None
        now = time.monotonic()
        # Fast path (no lock): the overwhelming common case is a warm cache
        # where nothing is due — never pay lock overhead for that.
        if self._due(kid, now) and not self._backed_off(now):
            async with self._lock:
                now = time.monotonic()   # time may have passed waiting for the lock
                # Re-check inside the lock: another coroutine may have
                # already refreshed (success) or just recorded a fresh
                # failure (moved _last_attempt_at) while we were waiting —
                # THIS is what caps a thundering herd at exactly one fetch.
                if self._due(kid, now) and not self._backed_off(now):
                    self._last_attempt_at = now
                    try:
                        await self._refresh()
                    except Exception:
                        self._consecutive_failures += 1
                        # keep serving cached (possibly empty) keys on
                        # failure — never raise out of key_for
        return self._keys.get(kid)


def _headers(scope) -> dict:
    out = {}
    for name, value in scope.get("headers") or []:
        key = name.decode("latin-1").lower()
        val = value.decode("latin-1")
        out[key] = out[key] + ", " + val if key in out else val
    return out


def _session_token(headers: dict) -> str | None:
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    raw = headers.get("cookie")
    if raw:
        try:
            jar = SimpleCookie()
            jar.load(raw)
            if "__session" in jar:
                return jar["__session"].value or None
        except Exception:
            return None
    return None


async def _send_json(send, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                            (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": body})


async def _send_redirect(send, location: str) -> None:
    await send({"type": "http.response.start", "status": 307,
                "headers": [(b"location", location.encode("utf-8")),
                            (b"content-length", b"0"),
                            (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": b""})


async def _resolve_plan_for(user_id: str) -> str:
    """Agent B's billing.entitlements.resolve_plan(user_id), wired in
    post-verify (F3, EVAL_ROUND_1.md): a verified session previously always
    got plan="free" hardcoded, so a paying Pro subscriber was served the
    free tier forever. Import-guarded (lazy, so there is no import-time
    circularity with billing._contracts, which itself imports UserCtx from
    THIS module) and never-raising — a missing/broken resolver degrades to
    "free", the same mirror-safe direction as the bug this replaces: it must
    never invent "pro" for free either."""
    try:
        from .billing.entitlements import resolve_plan
    except Exception:
        return "free"
    try:
        plan = await resolve_plan(user_id)
    except Exception:
        log.exception("resolve_plan(%r) failed; defaulting to free", user_id)
        return "free"
    return plan if plan in ("free", "pro") else "free"


class AuthMiddleware:
    """Outermost middleware (see main.py composition order)."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings
        self._jwks: JWKSCache | None = None
        url = settings.jwks_url
        if url and not settings.dev_bypass:
            self._jwks = JWKSCache(url)
        # azp is checked only against BASE_URL-derived origins, only when the
        # claim is present (Clerk marks azp optional for non-browser clients).
        base = settings.BASE_URL.rstrip("/")
        self._authorized_parties = {base} if base else set()

    async def _verify(self, token: str | None) -> UserCtx | None:
        if not token or self._jwks is None:
            return None
        try:
            header = jwt.get_unverified_header(token)
            pyjwk = await self._jwks.key_for(header.get("kid"))
            if pyjwk is None:
                return None
            claims = jwt.decode(
                token, key=pyjwk.key, algorithms=_ALGORITHMS, leeway=_LEEWAY_S,
                options={"verify_aud": False})   # Clerk session JWTs carry azp, not aud
        except Exception:
            return None
        azp = claims.get("azp")
        if azp and self._authorized_parties and azp not in self._authorized_parties:
            return None
        sub = claims.get("sub")
        if not sub:
            return None
        plan = await _resolve_plan_for(sub)
        return UserCtx(user_id=sub, email=claims.get("email"), plan=plan)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        if self.settings.dev_bypass:
            # Default plan when no X-Dev-Plan header is sent: the ENV-gated
            # settings.dev_default_plan — "pro" on localhost dev (owner
            # decision 2026-08-15: no "see plans" gate in the way of the OCR
            # flow during development), ALWAYS "free" outside ENV=dev, so a
            # DEV_BYPASS leaking into a prodlike environment still serves the
            # plan gate. The header remains honored in bypass mode only, in
            # BOTH directions — `X-Dev-Plan: free` is how the plan gate and
            # 402 paths are QA'd in dev now (docs/OCR_QA_PLAN.md §8).
            requested = headers.get("x-dev-plan", "").strip().lower()
            plan = requested if requested in ("free", "pro") else self.settings.dev_default_plan
            # X-Dev-User (F22, EVAL_ROUND_1.md): honored ONLY in bypass mode,
            # same hostile-client posture as X-Dev-Plan just above — lets the
            # probe suite's "free user" and "pro user" be genuinely distinct
            # accounts instead of both aliasing dev_user (which was part of
            # why its burst window bled across probes, F12).
            user_id = headers.get("x-dev-user", "dev_user").strip() or "dev_user"
            user: UserCtx | None = UserCtx(user_id=user_id, email=None,
                                           plan=plan if plan in ("free", "pro") else "free")
        else:
            user = await self._verify(_session_token(headers))

        scope.setdefault("state", {})["user"] = user   # -> request.state.user

        if user is None and scope.get("method", "GET") != "OPTIONS":
            path = scope.get("path", "/")
            if not _is_exempt(path):
                sign_in = self.settings.sign_in_url
                if path.startswith("/api/") or path.startswith("/shell/"):
                    await _send_json(send, 401, {"error": "auth_required",
                                                 "sign_in_url": sign_in})
                    return
                # F9 (EVAL_ROUND_1.md): previously only redirected when the
                # client SENT an Accept: text/html header — any request that
                # omitted it (curl, a script, `Accept: */*`) fell through and
                # got served the full unauthenticated app shell. There is no
                # public "marketing teaser" page in this product (A5 already
                # established that an HTML "/" request redirects); the fix
                # is simply to stop trusting a spoofable/optional header as
                # the gate — deny by default for GET/HEAD too, regardless of
                # Accept, and allow-list only the specific pre-auth assets
                # above (EXEMPT_PATHS / EXEMPT_PREFIXES).
                if scope.get("method") in ("GET", "HEAD"):
                    target = self.settings.BASE_URL.rstrip("/") + path
                    sep = "&" if "?" in sign_in else "?"
                    await _send_redirect(
                        send, f"{sign_in}{sep}redirect_url={quote(target, safe='')}")
                    return
                # Any other unauthenticated, non-exempt request (e.g. a
                # POST/PUT to a non-/api//shell path) — deny closed.
                await _send_json(send, 401, {"error": "auth_required",
                                             "sign_in_url": sign_in})
                return

        await self.app(scope, receive, send)
