"""shell/app/auth.py — Clerk session verification + DEV_BYPASS mock (Agent A).

Implements PRODUCTION_PLAN.md §2 (Clerk auth; ``__session`` JWT verified
server-side via JWKS) as a pure-ASGI middleware, per the shared contract in
shell/ARCHITECTURE.md:

* ``UserCtx`` dataclass exposed to downstream layers as ``request.state.user``
  (``None`` when unauthenticated).
* DEV_BYPASS mode (keyless): every request gets
  ``UserCtx(user_id="dev_user", plan=<X-Dev-Plan header or "free">)``.
  The X-Dev-Plan header is honored ONLY in bypass mode — never in real mode
  (hostile-client rule, COMPASS invariant 6).
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

import json
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from urllib.parse import quote

import httpx
import jwt

from .config import Settings

# Paths reachable WITHOUT auth (shell/ARCHITECTURE.md + build brief):
# Stripe signs its own webhook, health is for probes/monitors, and the overlay
# assets must load on any page state (they render the signed-out chip too).
EXEMPT_PATHS = frozenset({
    "/shell/webhook/stripe",
    "/shell/health",
    "/shell/overlay.js",
    "/shell/overlay.css",
})

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
    refetch at most every ``min_refresh_s`` (key rotation without hammering)."""

    def __init__(self, url: str, ttl_s: float = 3600.0, min_refresh_s: float = 30.0):
        self.url = url
        self.ttl_s = ttl_s
        self.min_refresh_s = min_refresh_s
        self._keys: dict = {}
        self._fetched_at: float = 0.0

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

    async def key_for(self, kid: str | None):
        if not kid:
            return None
        age = time.monotonic() - self._fetched_at
        if age > self.ttl_s or (kid not in self._keys and age > self.min_refresh_s) \
                or not self._keys:
            try:
                await self._refresh()
            except Exception:
                pass               # keep serving cached keys on transient fetch failure
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
        # TODO(Agent B): resolve the real plan from the subscriptions table
        # (db.py) once it lands; until then every verified user is "free".
        return UserCtx(user_id=sub, email=claims.get("email"), plan="free")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        if self.settings.dev_bypass:
            plan = headers.get("x-dev-plan", "free").strip().lower() or "free"
            user: UserCtx | None = UserCtx(user_id="dev_user", email=None,
                                           plan=plan if plan in ("free", "pro") else "free")
        else:
            user = await self._verify(_session_token(headers))

        scope.setdefault("state", {})["user"] = user   # -> request.state.user

        if user is None and scope.get("method", "GET") != "OPTIONS":
            path = scope.get("path", "/")
            if path not in EXEMPT_PATHS:
                sign_in = self.settings.sign_in_url
                if path.startswith("/api/") or path.startswith("/shell/"):
                    await _send_json(send, 401, {"error": "auth_required",
                                                 "sign_in_url": sign_in})
                    return
                accept = headers.get("accept", "")
                if scope.get("method") in ("GET", "HEAD") and "text/html" in accept:
                    target = self.settings.BASE_URL.rstrip("/") + path
                    sep = "&" if "?" in sign_in else "?"
                    await _send_redirect(
                        send, f"{sign_in}{sep}redirect_url={quote(target, safe='')}")
                    return
                # non-HTML static assets fall through unauthenticated

        await self.app(scope, receive, send)
