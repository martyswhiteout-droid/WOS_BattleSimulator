"""shell/app/limits.py — quota, rate, burst, MIN_TROOPS enforcement (Agent B).

Implements PRODUCTION_PLAN.md §2.4 (anti-distillation & security config) and
PRODUCTION_CRITERIA.md §D1–D3 via the shell/ARCHITECTURE.md contract:

    async check_and_record(user, endpoint, body, ip_hash) -> LimitVerdict
    LimitVerdict = Allowed | Denied(status, code, message)
    Denials: 400 below_min_troops · 402 payment_required (OCR on free)
             · 429 quota_exhausted / burst

Check order (deliberate):
    1. MIN_TROOPS on /api/predict + /api/battle bodies      -> 400
    2. Runs clamp: sim "n" > entitlements.max_runs is silently reduced to
       max_runs (never rejected) — a single free-tier n=20000 must not be
       able to wedge a worker (EVAL_ROUND_1.md F4-b). The clamped body comes
       back on Allowed.body; LimitsMiddleware forwards THAT, not the
       original bytes, to the mounted engine.
    3. OCR on free plan                                     -> 402
    4. Per-account daily quota (entitlements table)         -> 429 quota_exhausted
    5. Per-IP daily cap (3x the account's plan cap)         -> 429 quota_exhausted
    6. Per-account burst, sliding 60s window <= BURST_PER_MIN -> 429 burst
    7. Record usage_events (fingerprint feeds sweep detection)

Only ALLOWED requests are recorded — denials must not consume quota, and
probe traffic must not poison the sweep corpus.

Also provides:
  * LimitsMiddleware — pure-ASGI wrapper applying check_and_record to POSTs
    on /api/* (and /shell/ocr), reading the body safely and replaying it for
    downstream, plus a global concurrency semaphore (§2.4).
  * sweep_scan(day) — nightly job: flag accounts with >= SWEEP_MIN_EVENTS
    near-identical fingerprints differing in at most one field -> audit_log
    (PRODUCTION_CRITERIA D3; response is flag/throttle, never ban).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional, Union

from shell.app import db
from shell.app.billing._contracts import UserCtx, get_settings, settings_extra

# ---------------------------------------------------------------------------
# Verdict types (contract)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Allowed:
    allowed: bool = True
    #: Non-None ONLY when check_and_record modified the request body (today:
    #: "n" clamped down to entitlements.max_runs, EVAL_ROUND_1.md F4-b).
    #: Callers that forward the request downstream (LimitsMiddleware) must
    #: prefer this over the original body when it is set — the original,
    #: unmodified bytes are otherwise what gets replayed.
    body: Optional[dict] = None


@dataclass(frozen=True)
class Denied:
    status: int
    code: str
    message: str
    allowed: bool = False


LimitVerdict = Union[Allowed, Denied]

SIM_ENDPOINTS = {"/api/predict", "/api/battle"}
# Both OCR upload endpoints share one metered class and therefore one daily
# quota: /shell/ocr (battle-report screenshots) and /shell/ocr/panel (stat-panel
# screenshots, engine ladder in shell/app/ocr/panel/ladder.py).
OCR_ENDPOINTS = {"/shell/ocr", "/shell/ocr/panel"}
IP_CAP_MULTIPLIER = 3  # per-IP daily cap = 3x account cap (task spec / C5)


def classify_endpoint(endpoint: str) -> Optional[str]:
    """'sim' | 'ocr' | None (unmetered)."""
    path = "/" + (endpoint or "").strip("/")
    if path in SIM_ENDPOINTS:
        return "sim"
    if path in OCR_ENDPOINTS:
        return "ocr"
    return None


# ---------------------------------------------------------------------------
# Fingerprinting (feeds sweep detection, D3)
# ---------------------------------------------------------------------------


def _round_troops(value: float) -> int:
    """Round to nearest 100, half-up (banker's rounding would split sweeps)."""
    return int((value + 50) // 100 * 100)


def normalize_body(body: Optional[dict]) -> dict:
    """Sorted keys; every numeric value under a *troops* key rounded to the
    nearest 100 so micro-stepped sweeps collapse to identical fingerprints."""

    def norm(value: Any, key: Optional[str] = None) -> Any:
        if isinstance(value, dict):
            return {k: norm(value[k], k) for k in sorted(value)}
        if isinstance(value, list):
            return [norm(v, key) for v in value]
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and key is not None
            and "troops" in key.lower()
        ):
            return _round_troops(value)
        return value

    return norm(body or {})


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out.update(_flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix or "_"] = value
    return out


def compute_fingerprint(body: Optional[dict]) -> tuple[str, dict[str, str]]:
    """(sha256 of normalized body, per-leaf-field value hashes).

    The per-field map lets sweep_scan detect one-field-stepped query families
    without ever storing raw payloads."""
    normalized = normalize_body(body)
    blob = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    fingerprint = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    fields = {
        path: hashlib.sha256(
            json.dumps(val, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]
        for path, val in _flatten(normalized).items()
    }
    return fingerprint, fields


def hash_ip(ip: str) -> str:
    salt = settings_extra(get_settings(), "ip_hash_salt", "")
    return hashlib.sha256(f"{salt}{ip}".encode("utf-8")).hexdigest()[:32]


def _extract_troops(body: Optional[dict]) -> tuple[Optional[int], Optional[int]]:
    """Contract: body['own']['troops_total'] / body['enemy']['troops_total']."""

    def grab(side: str) -> Optional[int]:
        if not isinstance(body, dict):
            return None
        node = body.get(side)
        if not isinstance(node, dict):
            return None
        val = node.get("troops_total")
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return None
        return int(val)

    return grab("own"), grab("enemy")


def _clamp_runs(body: Optional[dict], max_runs: int) -> Optional[dict]:
    """If body["n"] is a real number over max_runs, return a shallow COPY
    with "n" reduced to max_runs. Returns None when nothing needs to change
    (no cap configured, no/invalid "n", or already within range) — the
    caller uses None to mean "forward the original body unchanged".

    Deliberately narrow: this enforces the ENTITLEMENT ceiling only. A
    malformed "n" (string, negative, missing) is left for wos_sim's own
    validation (server.py's InvalidInput -> clean 400) rather than guessed
    at here.
    """
    if max_runs <= 0 or not isinstance(body, dict):
        return None
    requested = body.get("n")
    if isinstance(requested, bool) or not isinstance(requested, (int, float)):
        return None
    if requested <= max_runs:
        return None
    clamped = dict(body)
    clamped["n"] = max_runs
    return clamped


# ---------------------------------------------------------------------------
# The contract function
# ---------------------------------------------------------------------------


async def check_and_record(
    user: UserCtx, endpoint: str, body: Optional[dict], ip_hash: str
) -> LimitVerdict:
    settings = get_settings()
    kind = classify_endpoint(endpoint)
    if kind is None:
        return Allowed()  # unmetered endpoint — nothing to enforce or record

    plan = (getattr(user, "plan", None) or "free").lower()
    troops_own: Optional[int] = None
    troops_enemy: Optional[int] = None

    # 1. MIN_TROOPS (D1) — kills micro-battle isolation experiments.
    if kind == "sim":
        min_troops = int(settings.min_troops_per_side)
        troops_own, troops_enemy = _extract_troops(body)
        if (
            troops_own is None
            or troops_enemy is None
            or troops_own < min_troops
            or troops_enemy < min_troops
        ):
            return Denied(
                400,
                "below_min_troops",
                f"Battles require at least {min_troops:,} troops per side "
                "(own.troops_total and enemy.troops_total).",
            )

    ent = await db.get_entitlements(plan)

    # 2. Runs clamp (D2/E6) — silently cap "n" at entitlements.max_runs
    # rather than reject, so a request for more runs than the plan allows
    # still gets an answer (a smaller one) instead of an error. This is what
    # actually closes F4-b: main.py's create_app() wires THIS module's
    # LimitsMiddleware as the live limits layer, and it forwards
    # effective_body (below) downstream instead of the raw request bytes.
    effective_body = body
    if kind == "sim":
        clamped = _clamp_runs(body, int(ent.max_runs))
        if clamped is not None:
            effective_body = clamped

    # 3. OCR is a paid feature (402 payment_required on free).
    if kind == "ocr" and (plan == "free" or ent.daily_ocr_quota <= 0):
        return Denied(
            402,
            "payment_required",
            "Screenshot OCR is a Pro feature. Upgrade to use it.",
        )

    # 4. Per-account daily quota (entitlements = single source of truth, D2).
    daily_cap = ent.daily_sim_quota if kind == "sim" else ent.daily_ocr_quota
    used = await db.get_usage_today(user.user_id, kind)
    if used >= daily_cap:
        noun = "simulations" if kind == "sim" else "OCR uploads"
        return Denied(
            429,
            "quota_exhausted",
            f"Daily limit reached: {daily_cap} {noun}/day on the {plan} plan. "
            "Resets at midnight UTC.",
        )

    # 5. Per-IP daily cap = 3x the account cap (C5: burner accounts don't
    #    multiply free quota).
    if ip_hash:
        ip_used = await db.get_ip_usage_today(ip_hash, kind)
        if ip_used >= daily_cap * IP_CAP_MULTIPLIER:
            return Denied(
                429,
                "quota_exhausted",
                "Daily limit for this network reached. Resets at midnight UTC.",
            )

    # 6. Per-account burst: sliding 60s window across metered endpoints (D2).
    burst_cap = int(settings.burst_per_min)
    recent = await db.count_recent_events(user.user_id, 60)
    if recent >= burst_cap:
        return Denied(
            429,
            "burst",
            f"Slow down: at most {burst_cap} requests per minute.",
        )

    # 7. Record (allowed requests only). Fingerprint the ORIGINAL body, not
    # the clamped one — sweep detection should see what the client actually
    # sent, and "n" already isn't part of the troops-rounding identity the
    # fingerprint is built around.
    fingerprint, fp_fields = compute_fingerprint(body)
    await db.record_usage(
        user.user_id,
        endpoint="/" + endpoint.strip("/"),
        kind=kind,
        ip_hash=ip_hash or None,
        request_fingerprint=fingerprint,
        fp_fields=fp_fields,
        troops_own=troops_own,
        troops_enemy=troops_enemy,
    )
    return Allowed(body=effective_body if effective_body is not body else None)


# ---------------------------------------------------------------------------
# ASGI middleware
# ---------------------------------------------------------------------------


class LimitsMiddleware:
    """Applies check_and_record to POST /api/* (and /shell/ocr) requests.

    Pure ASGI: buffers the request body, runs the verdict, and replays the
    body for downstream so the wrapped prototype app sees it untouched.
    Billing/webhook/health/overlay paths are not metered here. Also applies
    the global concurrency cap (GLOBAL_CONCURRENCY, §2.4) to metered paths so
    a flood degrades gracefully.
    """

    def __init__(self, app) -> None:
        self.app = app
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._semaphore_size: Optional[int] = None

    def _metered(self, scope) -> bool:
        if scope["type"] != "http" or scope.get("method") != "POST":
            return False
        path = scope.get("path", "")
        return path.startswith("/api/") or classify_endpoint(path) == "ocr"

    def _get_semaphore(self, size: int) -> asyncio.Semaphore:
        if self._semaphore is None or self._semaphore_size != size:
            self._semaphore = asyncio.Semaphore(max(1, size))
            self._semaphore_size = size
        return self._semaphore

    async def __call__(self, scope, receive, send) -> None:
        if not self._metered(scope):
            await self.app(scope, receive, send)
            return

        settings = get_settings()

        # ---- buffer the body safely --------------------------------------
        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] == "http.request":
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                return  # client went away; nothing to do
        body_bytes = b"".join(chunks)

        body: Optional[dict]
        try:
            parsed = json.loads(body_bytes) if body_bytes else None
            body = parsed if isinstance(parsed, dict) else None
        except (ValueError, UnicodeDecodeError):
            body = None

        # ---- resolve identity (auth middleware runs OUTSIDE this one) ----
        # EVAL_ROUND_1.md F22 (minor, Agents B/D): in the live app this
        # branch never fires — main.py wires AuthMiddleware OUTERMOST, and
        # it unconditionally sets scope["state"]["user"] first (dev bypass
        # included, hardcoded user_id="dev_user", NOT reading X-Dev-User —
        # that's auth.py, out of this file's ownership). The X-Dev-User read
        # below only matters for tests that exercise LimitsMiddleware
        # standalone (test_limits_core.py's make_client()); it does not
        # cause and cannot fix the probe suite's same-account bleed (F12),
        # whose root cause is auth.py. Investigated 2026-08-15, left as-is:
        # removing it would only change this file's own test scaffolding,
        # not the reported behavior.
        user = (scope.get("state") or {}).get("user")
        if user is None and settings.dev_bypass:
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in scope.get("headers", [])
            }
            user = UserCtx(
                user_id=headers.get("x-dev-user", "dev_user"),
                email=None,
                plan=headers.get("x-dev-plan", "free"),
            )
        if user is None:
            # Unauthenticated: auth.py owns the 401 contract; pass through
            # untouched so the auth layer's behavior is authoritative.
            await self.app(scope, self._replay(body_bytes, receive), send)
            return

        # ---- client IP -> hash -------------------------------------------
        headers_raw = dict(scope.get("headers", []))
        fwd = headers_raw.get(b"x-forwarded-for")
        if fwd:
            ip = fwd.decode("latin-1").split(",")[0].strip()
        else:
            client = scope.get("client")
            ip = client[0] if client else "unknown"
        ip_hashed = hash_ip(ip)

        verdict = await check_and_record(user, scope.get("path", ""), body, ip_hashed)

        if isinstance(verdict, Denied):
            payload = json.dumps(
                {"error": verdict.code, "message": verdict.message}
            ).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": verdict.status,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(payload)).encode("latin-1")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": payload})
            return

        # An Allowed verdict may carry a modified body (today: "n" clamped to
        # entitlements.max_runs, F4-b) — forward THAT to the wrapped app
        # instead of the client's original bytes. re-encoding here (rather
        # than mutating body_bytes above) keeps the common, unmodified case
        # a plain passthrough with zero extra encode/decode work.
        outgoing_bytes = body_bytes
        if isinstance(verdict, Allowed) and verdict.body is not None:
            outgoing_bytes = json.dumps(verdict.body).encode("utf-8")

        semaphore = self._get_semaphore(int(settings.global_concurrency))
        async with semaphore:
            await self.app(scope, self._replay(outgoing_bytes, receive), send)

    @staticmethod
    def _replay(body_bytes: bytes, receive):
        """Receive-callable that replays the buffered body once, then
        delegates to the original receive (e.g. for http.disconnect)."""
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {
                    "type": "http.request",
                    "body": body_bytes,
                    "more_body": False,
                }
            return await receive()

        return replay


# ---------------------------------------------------------------------------
# Sweep detection (D3): nightly job over usage_events fingerprints
# ---------------------------------------------------------------------------


async def sweep_scan(day: Union[date, str, None] = None) -> list[dict]:
    """Flag accounts showing the parameter-sweep signature for `day` (UTC).

    Two patterns are flagged, both requiring >= SWEEP_MIN_EVENTS (default 20)
    events from one account in the day:
      * identical  — the same fingerprint repeated (micro-stepping collapses
                     to one fingerprint because troops are rounded to 100);
      * one_field  — a family of requests identical except for exactly one
                     field, with >= 5 distinct stepped values (the classic
                     single-variable sweep used to reverse-engineer engines).

    Flags are written to audit_log (event_type='sweep_flag', deduped per
    user/day/pattern so the nightly job is re-runnable). Response policy per
    D3 is throttle + alert Martin — never an automated ban; this function
    only flags.
    """
    if day is None:
        day = datetime.now(timezone.utc).date()
    elif isinstance(day, str):
        day = date.fromisoformat(day)

    threshold = int(settings_extra(get_settings(), "sweep_min_events", 20))
    min_distinct_steps = 5

    events = await db.fetch_usage_for_day(day)
    by_user: dict[str, list[dict]] = {}
    for event in events:
        by_user.setdefault(event["clerk_user_id"], []).append(event)

    flags: list[dict] = []

    for user_id, user_events in by_user.items():
        if len(user_events) < threshold:
            continue

        # Pattern 1: identical fingerprints repeated.
        fp_counts: dict[str, int] = {}
        for event in user_events:
            fp = event.get("request_fingerprint")
            if fp:
                fp_counts[fp] = fp_counts.get(fp, 0) + 1
        for fp, count in fp_counts.items():
            if count >= threshold:
                flags.append(
                    {
                        "user_id": user_id,
                        "day": day.isoformat(),
                        "pattern": "identical",
                        "field": None,
                        "count": count,
                        "fingerprint": fp,
                    }
                )

        # Pattern 2: near-identical, differing in exactly one field.
        # masked_sig(f) = hash of all field-hashes except f; two events
        # differing only in f share masked_sig(f).
        groups: dict[tuple[str, str], set[str]] = {}
        group_sizes: dict[tuple[str, str], int] = {}
        for event in user_events:
            fields = event.get("fp_fields") or {}
            if not isinstance(fields, dict) or not fields:
                continue
            items = sorted(fields.items())
            for field_path, value_hash in items:
                masked = hashlib.sha256(
                    json.dumps(
                        [pair for pair in items if pair[0] != field_path]
                    ).encode("utf-8")
                ).hexdigest()
                key = (field_path, masked)
                group_sizes[key] = group_sizes.get(key, 0) + 1
                groups.setdefault(key, set()).add(value_hash)

        flagged_fields: set[str] = set()
        for (field_path, _masked), size in group_sizes.items():
            if (
                size >= threshold
                and len(groups[(field_path, _masked)]) >= min_distinct_steps
                and field_path not in flagged_fields
            ):
                flagged_fields.add(field_path)
                flags.append(
                    {
                        "user_id": user_id,
                        "day": day.isoformat(),
                        "pattern": "one_field",
                        "field": field_path,
                        "count": size,
                        "distinct_values": len(groups[(field_path, _masked)]),
                    }
                )

    for flag in flags:
        pattern_key = flag["field"] or flag.get("fingerprint", "identical")
        await db.audit(
            "sweep_flag",
            actor="sweep_scan",
            subject=flag["user_id"],
            detail=flag,
            dedup_key=f"sweep:{flag['day']}:{flag['user_id']}:{flag['pattern']}:{pattern_key}",
        )
    return flags
