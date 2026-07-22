"""Layer 3 — the local web API. The front-end talks ONLY to this; it never
touches the engine. Run:  uvicorn wos_sim.predictor.server:app --reload

Endpoints:
  GET  /api/health           -> liveness
  POST /api/predict          -> {own, enemy, n, seed} -> forecast JSON
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import api, gate, serialize
from .validate import InvalidInput

app = FastAPI(title="WoS Battle Predictor", version="0.1")
# local single-user tool: allow the static front-end (any localhost origin) to call it
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DEFAULT_RUNS = 1_000      # default when a caller omits n (matches the UI default)
MAX_RUNS = 100_000        # hard ceiling — only a guard against a hang/DoS on absurd n
# The turn engine is the default: after the 2026-07-08 recalibration it ranks
# ALL THREE T12 anchors correctly with survivor magnitudes in band, and it is
# the only path that emits skill telemetry. engine_meta labels near-even
# matchups "coin_flip" (a +-2% strength shift flips them - as in reality).
DEFAULT_ENGINE_PARAMS = {"engine": "turn"}


@app.exception_handler(gate.GateReject)
async def _gate_reject(request: Request, exc: gate.GateReject):
    """Deployment gate (Vercel only; see gate.py) -> clean 400/429, never a 500."""
    return JSONResponse(status_code=exc.status,
                        content={"error": exc.error, "message": exc.message})


@app.exception_handler(InvalidInput)
async def _invalid_input(request: Request, exc: InvalidInput):
    """Malformed profile -> a clean 400 with the per-field problems (never a 500 stack)."""
    return JSONResponse(status_code=400, content={"error": "invalid_input", "problems": exc.problems})


class PredictRequest(BaseModel):
    own: dict            # BRD S.9 profile dict (see serialize.profile_from_dict)
    enemy: dict
    n: int = DEFAULT_RUNS
    seed: int = 0


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/predict")
def predict(req: PredictRequest, request: Request):
    gate.check_gate(request, req.own, req.enemy)     # Vercel-only; no-op locally
    if req.n < 1 or req.n > MAX_RUNS:
        raise InvalidInput([f"n must be between 1 and {MAX_RUNS:,}"])
    own = serialize.profile_from_dict(req.own)
    enemy = serialize.profile_from_dict(req.enemy)
    fc = api.predict(own, enemy, n=req.n, seed=req.seed,
                     params=DEFAULT_ENGINE_PARAMS)
    return serialize.forecast_to_dict(fc)


class BattleRequest(BaseModel):
    own: dict
    enemy: dict
    seed: int = 0
    index: int = 0       # 0-based battle #; reproduced deterministically via CRN


@app.post("/api/battle")
def battle(req: BattleRequest, request: Request):
    """One battle's per-turn timeline, reproduced on demand (same seed+index as the
    forecast, so it matches the averaged run exactly)."""
    gate.check_gate(request, req.own, req.enemy)     # Vercel-only; no-op locally
    if req.index < 0 or req.index >= MAX_RUNS:
        raise InvalidInput([f"battle index must be between 0 and {MAX_RUNS - 1:,}"])
    own = serialize.profile_from_dict(req.own)
    enemy = serialize.profile_from_dict(req.enemy)
    return api.battle_timeline(own, enemy, seed=req.seed, index=req.index,
                               params=DEFAULT_ENGINE_PARAMS)


# serve the front-end (index.html + avatars) from the same origin, so
# `uvicorn wos_sim.predictor.server:app` runs the whole app. Mounted LAST so the
# /api/* routes above match first.
from pathlib import Path                       # noqa: E402
from fastapi.staticfiles import StaticFiles    # noqa: E402


class _NoCacheHTML(StaticFiles):
    """HTML responses must always revalidate. Without Cache-Control, browsers
    apply heuristic caching to index.html and keep showing a stale UI long
    after the file changed on disk (observed 2026-07-14: fixes invisible until
    a hard refresh). Assets (fonts/images/video) keep normal caching."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        ctype = resp.headers.get("content-type", "")
        if "text/html" in ctype:
            resp.headers["Cache-Control"] = "no-cache"
        return resp


_PROTOTYPE = Path(__file__).resolve().parents[2] / "prototype"
if _PROTOTYPE.is_dir():
    app.mount("/", _NoCacheHTML(directory=str(_PROTOTYPE), html=True), name="app")
