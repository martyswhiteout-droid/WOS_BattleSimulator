"""Deployment gate for the public (Vercel) deployment — Martin's 2026-07-21
request: max 10 simulation requests per visitor per day, minimum 1,000 troops
per side. A first, deliberately small slice of PRODUCTION_CRITERIA.md's D1/D2
(anti-distillation: the min-size rule exists precisely to block the 1v1
isolation experiments this project itself used to reverse-engineer the game).

ACTIVATION — environment-driven, OFF by default:
  * active iff the ``VERCEL`` env var is present (Vercel sets it on every
    deployment) or ``WOS_GATE=1`` is set explicitly (tests / manual enable).
  * localhost / the prototype dev loop therefore stays COMPLETELY ungated —
    per PRODUCTION_CRITERIA.md D1: micro-battles are essential for our own
    calibration; never port the limit back into the prototype.

CONFIG (env, with defaults):
  WOS_GATE_MAX_DAILY   requests per client IP per UTC day     (default 10)
  WOS_GATE_MIN_TROOPS  minimum deployed troops per side       (default 1000)

HONEST LIMITATION (documented, not hidden): the rate counter is in-memory,
per serverless instance. On Vercel that means it resets on cold starts and is
not shared across concurrent instances — it stops casual overuse, not a
determined adversary. Real enforcement needs accounts + a shared store
(PRODUCTION_CRITERIA.md C1/C5/D2); this gate is the interim protection for a
personally-shared prototype URL.
"""
from __future__ import annotations

import datetime as _dt
import os


class GateReject(Exception):
    """Raised by check_gate; the server maps it to a clean HTTP response."""

    def __init__(self, status: int, error: str, message: str):
        super().__init__(message)
        self.status = status
        self.error = error
        self.message = message


#: in-memory per-instance counter: {(ip, "YYYY-MM-DD"): count}
_COUNTS: dict[tuple[str, str], int] = {}


def _active() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("WOS_GATE") == "1")


def _max_daily() -> int:
    return int(os.environ.get("WOS_GATE_MAX_DAILY", "10"))


def _min_troops() -> int:
    return int(os.environ.get("WOS_GATE_MIN_TROOPS", "1000"))


def _client_ip(request) -> str:
    """Client IP; on Vercel the real client is the first x-forwarded-for hop."""
    fwd = request.headers.get("x-forwarded-for") if request is not None else None
    if fwd:
        return fwd.split(",")[0].strip()
    client = getattr(request, "client", None)
    return getattr(client, "host", None) or "unknown"


def _side_troops(profile_dict: dict) -> float:
    """Total deployed troops for one side, computed the same way
    serialize.profile_from_dict/construct do: explicit formation_counts win;
    otherwise troops_total (the formation fractions split it, sum unchanged)."""
    counts = profile_dict.get("formation_counts") or {}
    if counts:
        return float(sum(float(v) for v in counts.values()))
    return float(profile_dict.get("troops_total", 1_000_000))


def check_gate(request, own: dict, enemy: dict) -> None:
    """Raise GateReject (400 min-size / 429 rate) when the deployment gate is
    active and the request violates it. No-op when inactive (localhost)."""
    if not _active():
        return

    floor = _min_troops()
    for label, side in (("own", own), ("enemy", enemy)):
        total = _side_troops(side or {})
        if total < floor:
            raise GateReject(
                400, "below_min_troops",
                f"{label} side deploys {total:,.0f} troops; this deployment "
                f"requires at least {floor:,} troops per side.")

    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    ip = _client_ip(request)
    # prune stale days so the dict cannot grow unboundedly within an instance
    for key in [k for k in _COUNTS if k[1] != today]:
        del _COUNTS[key]
    used = _COUNTS.get((ip, today), 0)
    limit = _max_daily()
    if used >= limit:
        raise GateReject(
            429, "daily_limit_reached",
            f"Daily limit of {limit} simulations reached for this connection; "
            f"resets at 00:00 UTC.")
    _COUNTS[(ip, today)] = used + 1
