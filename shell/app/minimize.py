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
* summarizes ``skill_telemetry`` (F7, EVAL_ROUND_1.md): each skill's display
  identity (source/slot/name/icon/effect/troop) is kept, but the full
  ``triggers``/``kills`` Distribution (a 12-bin histogram + median/mean/
  p5/p95, PER skill, PER hero, PER side, PER request — the richest
  per-request distillation surface in the response, richer than the
  kill_matrix stripped above) is reduced to one coarse "fired N times" and
  one coarse "kills ~N" figure each (``summarize_skill_telemetry``).
* KEEPS every other user-facing field: verdict win/mutual/loss probabilities,
  ``engine`` meta (path, model_error, note, near_even, confidence — the
  coin_flip/honesty labels are NEVER touched), outcome_quality,
  army/class loss distributions (percentages — not counts, not banded),
  rounds, procs.
"""
from __future__ import annotations

import json
import logging

from .config import Settings

log = logging.getLogger("wos.shell.minimize")

_MINIMIZED_PATHS = frozenset({"/api/predict", "/api/battle"})
_UNPARSEABLE = object()   # sentinel: body wasn't valid JSON despite its content-type

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


def _summarize_dist(dist):
    """A full Distribution dict (``{"counts", "edges", "median", "mean",
    "p5", "p95"}`` — see wos_sim/predictor/serialize.py's ``_dist``) reduced
    to ONE coarse figure: the rounded median. Drops the per-bin histogram
    and the mean/p5/p95 percentiles — the highest-resolution per-request
    surface in the whole response (F7, EVAL_ROUND_1.md)."""
    if not isinstance(dist, dict):
        return None
    try:
        return int(round(float(dist.get("median"))))
    except (TypeError, ValueError):
        return None


def summarize_skill_telemetry(tel):
    """Reduce ``skill_telemetry`` to a user-facing summary (F7,
    EVAL_ROUND_1.md): keep each skill's display identity (source, slot,
    name, icon, effect, troop) plus ONE coarse "fired N times" figure and
    ONE coarse kills figure; drop the full ``triggers``/``kills``
    Distribution (12-bin histogram + median/mean/p5/p95 — proc-timing +
    kill-attribution detail richer, per request, than the ``kill_matrix``
    PRODUCTION_CRITERIA D4 already strips). Row-level identity (kind, hero,
    role, troop) is untouched. Never touches ``verdict``/``engine``/
    coin_flip — this function only ever sees the skill_telemetry subtree
    (COMPASS invariant 3 stays intact by construction)."""
    if not isinstance(tel, dict):
        return tel
    out = {}
    for side, rows in tel.items():
        new_rows = []
        for row in rows or []:
            new_row = dict(row)
            new_row["skills"] = [
                {**{k: v for k, v in skill.items() if k not in ("triggers", "kills")},
                 "fired": _summarize_dist(skill.get("triggers")),
                 "kills": _summarize_dist(skill.get("kills"))}
                for skill in row.get("skills", [])]
            new_rows.append(new_row)
        out[side] = new_rows
    return out


def minimize_predict(payload: dict) -> dict:
    """/api/predict (serialize.forecast_to_dict shape)."""
    out = strip_debug(payload)
    if isinstance(out.get("battle_timeline"), dict):
        out["battle_timeline"] = band_timeline(out["battle_timeline"])
    if "skill_telemetry" in out:
        out["skill_telemetry"] = summarize_skill_telemetry(out["skill_telemetry"])
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
            status = start_msg.get("status", 200)
            if status == 200 and b"application/json" in ctype:
                try:
                    payload = json.loads(body.decode("utf-8"))
                except Exception:
                    payload = _UNPARSEABLE   # not JSON despite the header: nothing to strip
                if payload is not _UNPARSEABLE:
                    try:
                        body = json.dumps(minimizer(payload),
                                          separators=(",", ":")).encode("utf-8")
                    except Exception:
                        # F30 (EVAL_ROUND_1.md): the OLD code fell back to
                        # shipping the RAW, un-minimized payload here (debug
                        # fields, full skill-telemetry histogram, everything)
                        # whenever the minimizer choked on a novel response
                        # shape. Fail CLOSED instead — never let a minimizer
                        # bug become a staging/prod data leak — and log
                        # loudly so the gap gets fixed, not silently worked
                        # around.
                        log.error("minimize.py: minimizer raised on a parsed "
                                 "JSON payload for %s %s — failing closed, "
                                 "NOT shipping the raw response",
                                 scope.get("method"), scope.get("path"),
                                 exc_info=True)
                        status = 500
                        body = json.dumps(
                            {"error": "minimization_failed"}).encode("utf-8")
            headers = [(n, v) for n, v in headers if n.lower() != b"content-length"]
            headers.append((b"content-length", str(len(body)).encode()))
            await send({"type": "http.response.start",
                        "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, capture)
