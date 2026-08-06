"""shell/app/minimize.py — production response minimization (Agent A).

Implements PRODUCTION_PLAN.md §2.4 "Response minimization" for the two engine
endpoints (``POST /api/predict``, ``POST /api/battle``) when ENV is staging or
prod. In ENV=dev the middleware is a pure pass-through (Martin's daily work is
untouched).

What it does (field names verified READ-ONLY against
``wos_sim/predictor/serialize.py`` (forecast_to_dict) and
``wos_sim/predictor/api.py`` (battle_timeline), 2026-08-04):

* strips debug/internal keys: any dict key named ``debug`` or ``*_debug``,
  recursively, plus the per-turn 3×3 ``kill_matrix`` from ``/api/battle``
  (raw engine telemetry internals — the highest-resolution distillation
  surface; COMPASS invariant 6).
* bands survivor/casualty POINT-ESTIMATES (absolute troop counts in the
  per-turn timeline series) to the nearest 100. Deterministic banding, no
  noise — the honesty design is preserved (COMPASS invariant 3).
* KEEPS every user-facing field: verdict win/mutual/loss probabilities,
  ``engine`` meta (path, model_error, note, near_even, confidence — the
  coin_flip/honesty labels are NEVER touched), outcome_quality,
  army/class loss distributions (percentages — not counts, not banded),
  rounds, skill_telemetry (display-shaped skill panels), procs.
"""
from __future__ import annotations

import json

from .config import Settings

_MINIMIZED_PATHS = frozenset({"/api/predict", "/api/battle"})

# per-turn series that are absolute troop counts -> banded to nearest 100
_COUNT_SERIES = ("own_survivors", "enemy_survivors", "own_killed", "enemy_killed")
_CLASS_SERIES = ("own", "enemy", "own_killed", "enemy_killed", "own_dealt", "enemy_dealt")


def _is_debug_key(key) -> bool:
    return isinstance(key, str) and (key == "debug" or key.endswith("_debug"))


def strip_debug(obj):
    """Recursively drop ``debug`` / ``*_debug`` keys from a JSON-ish tree."""
    if isinstance(obj, dict):
        return {k: strip_debug(v) for k, v in obj.items() if not _is_debug_key(k)}
    if isinstance(obj, list):
        return [strip_debug(v) for v in obj]
    return obj


def _band100(value):
    try:
        return int(round(float(value) / 100.0)) * 100
    except (TypeError, ValueError):
        return value


def _band_series(seq):
    return [_band100(v) for v in seq] if isinstance(seq, list) else seq


def band_timeline(tl: dict) -> dict:
    """Band the absolute-count per-turn series of a timeline-shaped dict
    (both the forecast's ``battle_timeline`` and the ``/api/battle`` body).
    ``turns``/``procs``/``truncated``/``index`` are left untouched."""
    out = dict(tl)
    for key in _COUNT_SERIES:
        if key in out:
            out[key] = _band_series(out[key])
    by_class = out.get("by_class")
    if isinstance(by_class, dict):
        out["by_class"] = {
            cls: {k: (_band_series(v) if k in _CLASS_SERIES else v)
                  for k, v in (sides or {}).items()}
            for cls, sides in by_class.items()}
    return out


def minimize_predict(payload: dict) -> dict:
    """/api/predict (serialize.forecast_to_dict shape)."""
    out = strip_debug(payload)
    if isinstance(out.get("battle_timeline"), dict):
        out["battle_timeline"] = band_timeline(out["battle_timeline"])
    return out


def minimize_battle(payload: dict) -> dict:
    """/api/battle (api.battle_timeline shape) — timeline-shaped at top level."""
    out = strip_debug(payload)
    out.pop("kill_matrix", None)
    return band_timeline(out)


class MinimizeMiddleware:
    """Buffers the JSON response of the two engine endpoints and rewrites it.
    Non-200 responses, non-JSON bodies, other paths, and ENV=dev pass through
    byte-for-byte."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http"
                or not self.settings.is_prodlike
                or scope.get("method") != "POST"
                or scope.get("path") not in _MINIMIZED_PATHS):
            await self.app(scope, receive, send)
            return

        minimizer = (minimize_battle if scope["path"] == "/api/battle"
                     else minimize_predict)
        state = {"start": None, "chunks": [], "done": False}   # per-request closure

        async def capture(message):
            if state["done"]:
                return
            if message["type"] == "http.response.start":
                state["start"] = message
            elif message["type"] == "http.response.body":
                state["chunks"].append(message.get("body", b""))
                if not message.get("more_body"):
                    state["done"] = True
                    await _flush()
            else:
                await send(message)

        async def _flush():
            start_msg = state["start"] or {"status": 200, "headers": []}
            body = b"".join(state["chunks"])
            headers = list(start_msg.get("headers") or [])
            ctype = next((v for n, v in headers if n.lower() == b"content-type"), b"")
            if start_msg.get("status") == 200 and b"application/json" in ctype:
                try:
                    payload = json.loads(body.decode("utf-8"))
                    body = json.dumps(minimizer(payload),
                                      separators=(",", ":")).encode("utf-8")
                except Exception:
                    pass    # malformed body: send the original bytes untouched
            headers = [(n, v) for n, v in headers if n.lower() != b"content-length"]
            headers.append((b"content-length", str(len(body)).encode()))
            await send({"type": "http.response.start",
                        "status": start_msg.get("status", 200), "headers": headers})
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, capture)
