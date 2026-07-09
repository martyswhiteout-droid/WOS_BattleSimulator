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

    # Joiner-aware DISPLAYED win probability (turn engine only). The turn engine
    # decides the winner + mechanics, but its raw win% is a near-deterministic
    # 1/0 that ignores joiners for the winner and reads 100% on a coin flip.
    # winprob.hybrid_win_prob folds joiners into an effective-strength sigmoid:
    # coin flip -> ~50%, a 4-joiner deficit -> ~10%, without ever overriding the
    # sim's winner on the structural upsets. See winprob.py.
    win_override = None
    near_even = meta.get("near_even", False)
    confidence = meta.get("confidence", "directional")
    note = meta.get("note", "")
    if turn_engine and records:
        from . import winprob
        own_tag = 'A' if con.own_is_attacker else 'D'
        wins = sum(1 for r in records if r.winner == own_tag)
        mutual = sum(1 for r in records if r.winner == 'mutual')
        p_turn_own = (wins + (mutual if con.own_is_attacker else 0)) / len(records)
        win_override, near_even = winprob.hybrid_win_prob(
            con, p_turn_own, blind_near_even=meta.get("near_even", False))
        confidence = "coin_flip" if near_even else "directional"
        # keep the note consistent with the FINAL (joiner-aware) near-even call
        note = ("Near-even armies: the win% reflects the strength balance "
                "(joiners included); ~40-60% is a coin flip either side can take."
                if near_even else
                "Turn-by-turn skill engine; win% reflects the joiner-aware "
                "strength balance. Read survivor magnitudes as directional.")

    return summary.summarize(
        records, own_is_attacker=con.own_is_attacker, engine_model_error=err,
        engine_path=meta.get("path", "general"), engine_note=note,
        stochastic=meta.get("stochastic", True), calibrated=meta.get("calibrated", False),
        near_even=near_even, confidence=confidence, win_prob_override=win_override)


def battle_timeline(own: SideProfile, enemy: SideProfile, *, seed: int = 0,
                    index: int = 0, params=None, cap: int = 80) -> dict:
    """Reproduce ONE battle (#index) deterministically and return its per-turn
    survivors + troops-lost timeline. Uses the SAME construct and the SAME CRN
    stream (``_run_rng(seed, index)``) as ``predict``, so battle #index here is
    identical to the one that fed the averaged forecast — no new random sim.
    Turn-engine only (the general engine has no per-turn log)."""
    from wos_sim import pvp_turn_engine
    from .kernel import _run_rng
    matchup = Matchup(own, enemy)
    validate.validate_matchup(matchup)
    turn_engine = bool(params and params.get("engine") == "turn")
    con = construct.build(matchup, apply_legacy_skills=not turn_engine)
    eng_params = dict(con.engine_params)
    if params:
        eng_params.update(params)
    res = pvp_turn_engine.run_construct(con, _run_rng(seed, index), eng_params)
    log = res.turn_log[:cap]
    tl = pvp_turn_engine._compact_timeline(log)
    a_surv = [r[0][0] + r[0][1] + r[0][2] for r in tl]
    d_surv = [r[1][0] + r[1][1] + r[1][2] for r in tl]
    a_kill = [r[2] for r in tl]
    d_kill = [r[3] for r in tl]
    a_lost_cls = [[(r[4] if len(r) > 4 else (0.0, 0.0, 0.0))[i] for r in tl] for i in range(3)]
    d_lost_cls = [[(r[5] if len(r) > 5 else (0.0, 0.0, 0.0))[i] for r in tl] for i in range(3)]
    a_dealt_cls = [[(r[6] if len(r) > 6 else (0.0, 0.0, 0.0))[i] for r in tl] for i in range(3)]
    d_dealt_cls = [[(r[7] if len(r) > 7 else (0.0, 0.0, 0.0))[i] for r in tl] for i in range(3)]
    if con.own_is_attacker:
        os_, es, ok, ek = a_surv, d_surv, a_kill, d_kill
        own_cls, enemy_cls = a_lost_cls, d_lost_cls
        own_dealt_cls, enemy_dealt_cls = a_dealt_cls, d_dealt_cls
        own_surv_cls = [[r[0][i] for r in tl] for i in range(3)]
        enemy_surv_cls = [[r[1][i] for r in tl] for i in range(3)]
    else:
        os_, es, ok, ek = d_surv, a_surv, d_kill, a_kill
        own_cls, enemy_cls = d_lost_cls, a_lost_cls
        own_dealt_cls, enemy_dealt_cls = d_dealt_cls, a_dealt_cls
        own_surv_cls = [[r[1][i] for r in tl] for i in range(3)]
        enemy_surv_cls = [[r[0][i] for r in tl] for i in range(3)]
    names = ("Infantry", "Lancer", "Marksman")
    by_class = {
        name: {
            "own": own_surv_cls[i], "enemy": enemy_surv_cls[i],
            "own_killed": own_cls[i], "enemy_killed": enemy_cls[i],
            "own_dealt": own_dealt_cls[i], "enemy_dealt": enemy_dealt_cls[i],
        }
        for i, name in enumerate(names)
    }
    procs = [_turn_procs(tr, con.own_is_attacker) for tr in log]   # per-turn proc icons
    return {"index": index, "turns": list(range(1, len(tl) + 1)),
            "own_survivors": os_, "enemy_survivors": es,
            "own_killed": ok, "enemy_killed": ek,
            "by_class": by_class, "procs": procs}


def _turn_procs(turn_record, own_is_attacker: bool) -> list:
    """Enrich a turn's fired procs with display name + icon (via skill_display) and
    map A/D -> own/enemy for the front-end."""
    from . import skill_display
    out = []
    for p in getattr(turn_record, "procs", None) or []:
        if p.get("role") in ("troop_skill", "t12"):
            meta = skill_display.troop_skill(p.get("name"))
        else:
            meta = skill_display.hero_skill(p.get("name"), p.get("slot"))
        side = "own" if ((p.get("side") == "attacker") == own_is_attacker) else "enemy"
        out.append({"name": meta.get("name") or p.get("name"),
                    "icon": meta.get("icon"), "side": side,
                    "troop": p.get("troop"),
                    "kills": p.get("kills", 0)})
    return out
