"""Predictor facade — the single entry point the web app calls.

    predict(own_profile, enemy_profile, n, seed) -> summary.Forecast

Ties Layer 1 (construct), the kernel seam, and Layer 2 (summary). The web
API (FastAPI) and the front-end code only ever touch this — never the engine.
"""
from __future__ import annotations

from . import construct, kernel, summary, validate
from .profiles import Matchup, SideProfile


def predict(own: SideProfile, enemy: SideProfile, *, n: int = 10_000, seed: int = 0,
            kernel_impl=None, params=None, engine_model_error=None) -> summary.Forecast:
    matchup = Matchup(own, enemy)
    validate.validate_matchup(matchup)              # raises InvalidInput on bad profiles
    turn_engine = bool(params and params.get("engine") == "turn")
    con = construct.build(matchup, apply_legacy_skills=not turn_engine)
    eng_params = dict(con.engine_params)         # profile-derived (T12 a_t12/d_t12, ...)
    if params:
        eng_params.update(params)                # explicit caller params win

    # per-matchup confidence: which engine path ran + its calibrated error band
    meta = kernel.engine_meta(con.attacker_units, con.defender_units, eng_params)
    records = kernel.run_batch(con, n=n, seed=seed, kernel=kernel_impl, params=eng_params)
    err = engine_model_error if engine_model_error is not None else meta["model_error"]
    return summary.summarize(
        records, own_is_attacker=con.own_is_attacker, engine_model_error=err,
        engine_path=meta.get("path", "general"), engine_note=meta.get("note", ""),
        stochastic=meta.get("stochastic", True), calibrated=meta.get("calibrated", False),
        near_even=meta.get("near_even", False),
        confidence=meta.get("confidence", "directional"))
