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

from . import api, serialize
from .validate import InvalidInput

app = FastAPI(title="WoS Battle Predictor", version="0.1")
# local single-user tool: allow the static front-end (any localhost origin) to call it
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DEFAULT_RUNS = 1_000      # default when a caller omits n (matches the UI default)
MAX_RUNS = 100_000        # hard ceiling — only a guard against a hang/DoS on absurd n
TELEMETRY_ENGINE_PARAMS = {"engine": "turn"}


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
def predict(req: PredictRequest):
    if req.n < 1 or req.n > MAX_RUNS:
        raise InvalidInput([f"n must be between 1 and {MAX_RUNS:,}"])
    own = serialize.profile_from_dict(req.own)
    enemy = serialize.profile_from_dict(req.enemy)
    fc = api.predict(own, enemy, n=req.n, seed=req.seed,
                     params=TELEMETRY_ENGINE_PARAMS)
    return serialize.forecast_to_dict(fc)


# serve the front-end (index.html + avatars) from the same origin, so
# `uvicorn wos_sim.predictor.server:app` runs the whole app. Mounted LAST so the
# /api/* routes above match first.
from pathlib import Path                       # noqa: E402
from fastapi.staticfiles import StaticFiles    # noqa: E402

_PROTOTYPE = Path(__file__).resolve().parents[2] / "prototype"
if _PROTOTYPE.is_dir():
    app.mount("/", StaticFiles(directory=str(_PROTOTYPE), html=True), name="app")
