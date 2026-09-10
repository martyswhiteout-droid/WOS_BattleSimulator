"""Predictor facade — the single entry point the web app calls.

    predict(own_profile, enemy_profile, n, seed) -> summary.Forecast

Ties Layer 1 (construct), the kernel seam, and Layer 2 (summary). The web
API (FastAPI) and the front-end code only ever touch this — never the engine.
"""
from __future__ import annotations

import math

from . import construct, kernel, summary, type1_router, validate
from .profiles import Matchup, SideProfile


def predict(own: SideProfile, enemy: SideProfile, *, n: int = 10_000, seed: int = 0,
            kernel_impl=None, params=None, engine_model_error=None) -> summary.Forecast:
    matchup = Matchup(own, enemy)
    validate.validate_matchup(matchup)              # raises InvalidInput on bad profiles

    # Stage 6.8 Type-1 router: a matchup classifiable into the frozen
    # deterministic law's validated domain gets the law's EXACT result
    # instead of the stochastic engine below. Conservative: any doubt in
    # classification runs the UNCHANGED body that follows. Opt-out (tests/
    # comparisons only -- server.py never sets this):
    # params={"deterministic_router": False}.
    abstain_note = ""
    if (params or {}).get("deterministic_router") is not False:
        classifiable, _reason = type1_router._type1_classifiable(matchup)
        if classifiable:
            forecast, abstain_note = type1_router._try_deterministic(matchup)
            if forecast is not None:
                return forecast

    # Stage 8.1 ARMY router -- OPT-IN ONLY (default OFF).
    #
    # DISABLED FOR THE LIVE PATH 2026-07-25 after independent QA returned "do not
    # approve" with four P1 defects (STAGE8_1_QA_PROMPT.md / the QA response):
    #   * the 1500-turn cap fabricated a winner, contradicting GAME_RULES.md s.424
    #     ("every battle ends in a wipe of at least one side - no turn cap");
    #   * unequal FC leaked into the law (FC1-v-FC2 reversed the winner) because the
    #     research base table varies with FC below T10 while the production catalog
    #     does not;
    #   * the +-10% band and the 0.10 coin threshold are not calibrated from enough
    #     independent configurations (two, both Infantry, one missing by 8.9%);
    #   * the 999/1000 threshold produced a 34-point survivor discontinuity.
    # The backbone stays available for research and for the fixes below, but a user
    # prediction must not depend on it until the band is calibrated.
    # Enable explicitly with params={"army_router": True}.
    if (params or {}).get("army_router") is True:
        from . import army_router
        army_ok, _army_reason = army_router.army_classifiable(matchup)
        if army_ok:
            forecast, army_note = army_router.try_army(matchup)
            if forecast is not None:
                return forecast
            abstain_note = f"{abstain_note} {army_note}".strip()
            # else: the law was classifiable but abstained/raised -- fall
            # through to the engine below; abstain_note is appended to its
            # engine_note further down.

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
    sim_hold_rate = None
    casualty_margin = None
    strength_ratio_own = None
    display_branch = None
    call_stability = None
    if turn_engine and records:
        from . import winprob
        from wos_sim.pvp_turn_engine import skill_defs_from_matchup
        own_tag = 'A' if con.own_is_attacker else 'D'
        wins = sum(1 for r in records if r.winner == own_tag)
        mutual = sum(1 for r in records if r.winner == 'mutual')
        p_turn_own = (wins + (mutual if con.own_is_attacker else 0)) / len(records)

        # Call-stability S: fraction of own-strength perturbations across the
        # existing +-BAND at which own wins a deterministic sim (kernel.py) -
        # replaces the one-bit p_turn_own as the near-even display's basis so
        # formation/joiner/troop changes move the headline instead of collapsing
        # to 25%/75% (ENGINE_HANDOFF_winprob_surface_what_varies.md, 2026-09-10).
        # Change A (2026-09-10): fold joiner stat packets into the sweep too -
        # call_stability's hero-skill-free sim was otherwise blind to joiners,
        # so S was bit-identical across own-joiner variants whenever the ratio
        # stayed inside the near-even band (test_winprob_stability.py Defect 1).
        mults = winprob._joiner_mults(skill_defs_from_matchup(con))
        S, _ = kernel.call_stability(con.attacker_units, con.defender_units,
                                     dict(eng_params), con.own_is_attacker,
                                     side_mults=mults)

        # Change C (2026-09-10): troop-only (joiner-blind) own-side strength
        # ratio, so hybrid_win_prob_ex can tell a joiner-driven decisive
        # disagreement (sim is proven blind to joiners for the winner -> full
        # strength override) from a troop-driven one (sim saw it -> keep the
        # edge-distance blend) (test_winprob_joiners.py Defect 2).
        a_idx = kernel._strength_index(con.attacker_units)
        d_idx = kernel._strength_index(con.defender_units)
        r_blind = a_idx / d_idx if d_idx > 0 else 1.0
        r_blind_own = r_blind if con.own_is_attacker else (
            1.0 / r_blind if r_blind > 0 else 1.0)

        res = winprob.hybrid_win_prob_ex(
            con, p_turn_own, blind_near_even=meta.get("near_even", False),
            stability=S, r_blind_own=r_blind_own)
        win_override, near_even = res["p"], res["near_even"]
        confidence = "coin_flip" if near_even else "directional"
        strength_ratio_own = res["r_own"]
        display_branch = res["branch"]
        call_stability = res["stability"]

        # Surface fields (ENGINE_HANDOFF_winprob_surface_what_varies.md §6.A):
        # the raw sim hold rate and the per-run casualty margin, so the UI can
        # show "what moved" even while the headline stays hedged.
        n_rec = len(records)
        se = math.sqrt(p_turn_own * (1.0 - p_turn_own) / n_rec) if n_rec else 0.0
        sim_hold_rate = summary.Proportion(p_turn_own, se)
        margins = []
        for r in records:
            if con.own_is_attacker:
                own_start, own_incap = r.attacker_start, r.attacker_incap
                enemy_start, enemy_incap = r.defender_start, r.defender_incap
            else:
                own_start, own_incap = r.defender_start, r.defender_incap
                enemy_start, enemy_incap = r.attacker_start, r.attacker_incap
            own_total = sum(own_start.values())
            enemy_total = sum(enemy_start.values())
            own_loss = (sum(own_incap.values()) / own_total) if own_total else 0.0
            enemy_loss = (sum(enemy_incap.values()) / enemy_total) if enemy_total else 0.0
            margins.append(enemy_loss - own_loss)
        margins_sorted = sorted(margins)
        mean_margin = sum(margins_sorted) / len(margins_sorted) if margins_sorted else 0.0
        casualty_margin = {"mean": mean_margin,
                           "p5": summary._percentile(margins_sorted, 0.05),
                           "p95": summary._percentile(margins_sorted, 0.95)}

        # Phase A (2026-07-28), REVISED after measurement. An earlier cut replaced
        # this number wholesale with the engine's measured hit rate. That was wrong
        # on two counts: it also overwrote the DECISIVE branches (expX2, a 2.3x
        # rout, displayed 0.727), and it discarded the sim's own margin. The
        # magnitude now comes from winprob.hybrid_win_prob_ex, whose near-even band
        # is the MEASURED near-even hit rate rather than the old DAMP=0.10 constant.
        from . import winprob_calibrated as _wpc
        # keep the note consistent with the FINAL (joiner-aware) near-even call
        note = (("Near-even armies -- a coin flip either side can take. "
                 if near_even else
                 "Turn-by-turn skill engine; read survivor magnitudes as directional. ")
                + _wpc.turn_engine_summary(near_even) + ".")

    if abstain_note:
        note = f"{note} {abstain_note}".strip()

    return summary.summarize(
        records, own_is_attacker=con.own_is_attacker, engine_model_error=err,
        engine_path=meta.get("path", "general"), engine_note=note,
        stochastic=meta.get("stochastic", True), calibrated=meta.get("calibrated", False),
        near_even=near_even, confidence=confidence, win_prob_override=win_override,
        sim_hold_rate=sim_hold_rate, casualty_margin=casualty_margin,
        strength_ratio_own=strength_ratio_own, display_branch=display_branch,
        call_stability=call_stability)


def _stage6_tables_meta() -> dict:
    """Load (and cache) the frozen table manifest stage6_tables.json --
    the single source of truth the deterministic entry points declare."""
    global _S6_META
    try:
        return _S6_META
    except NameError:
        pass
    import json
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "formula_research", "stage6_tables.json")
    with open(os.path.abspath(path), encoding="utf-8") as fh:
        j = json.load(fh)
    _S6_META = {"law_version": j["law_version"], "frozen": j["frozen"],
                "corpus": j["corpus"], "gatot_kit_status": j["gatot_kit"]["status"]}
    return _S6_META


def predict_deterministic_1v1(dealer: dict, target: dict, *,
                              offense_mult: float = 1.0) -> dict:
    """Stage-6 deterministic per-unit law (formula_research), exposed at the
    seam. Units are plain dicts: {"cls", "tier", "fc"?, "panel"? | "eff"?}.
    Non-mutating, no RNG. Returns {"turns", "meta"} -- meta carries
    law_version="stage6" + per-cell provenance statuses (measured /
    interpolated / bounded / extrapolated / factorized / fallback_infantry)
    from the class-keyed tables frozen in stage6_tables.json. See
    wos_sim/formula_research/STAGE6_REPORT.md for the validity domain
    (incl. the Gatot-kit two-regime scope)."""
    from wos_sim.formula_research.stage6_tables import predict_turns_1v1
    turns, meta = predict_turns_1v1(dealer, target, offense_mult=offense_mult)
    meta["tables"] = _stage6_tables_meta()
    return {"turns": turns, "meta": meta}


def predict_deterministic_battle(att_army: list, def_army: list, **kw) -> dict:
    """Army-level assembly: the stage5 composition ALGORITHM (unchanged,
    16/16 anchor-exact) over the stage6 class-keyed per-unit tables, PLUS
    (Stage 6.5, 2026-07-18) the stage6_gatot two-sided Gatot-kit gate.
    Armies are lists of unit dicts (see predict_deterministic_1v1). Pass
    `att_kit`/`def_kit` (each optional
    {"gatot": None|True|"mueller_s123_l1"|"farseer_s12_l1", "vulcanus": bool})
    to describe a side's own hero loadout when its front is a Gatot-led
    Infantry unit and/or a Vulcanus-led dealer -- see
    stage5_composition.predict_battle's docstring for the full contract.
    Omitting them (the pre-6.5 call convention) reproduces the plain
    two-sided race unchanged. Wherever the frozen kit's constants (the two
    measured budget defenders, the one measured S-curve defender, a
    measured dealer-class K) don't cover the configuration in play, the
    result is an honest `winner: "uncertain"` with `meta["gatot_abstain"]`
    (`{"flag", "detail"}` or `{"flag", "direction", "M_bound_ge"}`) instead
    of a confident winner -- never a guess.
    Non-mutating, no RNG; the stochastic `predict()` path and server.py are
    unaffected."""
    from wos_sim.formula_research.stage5_composition import predict_battle
    from wos_sim.formula_research.stage6_tables import law_funcs
    res = predict_battle(att_army, def_army, law=law_funcs(), **kw)
    res["meta"] = {**_stage6_tables_meta(), "law_version": "stage6.7"}
    if res.get("gatot_abstain") is not None:
        res["meta"]["gatot_abstain"] = res["gatot_abstain"]
    return res


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
    # per-turn 3x3 kill matrix [attacker_class][victim_class] (fixed Inf/Lan/Mar
    # order), mapped own/enemy the same way as the other a_*/d_* series. Row sums
    # equal that side's kills-by-class; column sums equal the OTHER side's
    # per-class casualties. See ENGINE_HANDOFF_kill_matrix.md.
    _z33 = ((0.0, 0.0, 0.0),) * 3
    a_kmx = [(r[8] if len(r) > 8 else _z33) for r in tl]
    d_kmx = [(r[9] if len(r) > 9 else _z33) for r in tl]
    own_kmx, enemy_kmx = (a_kmx, d_kmx) if con.own_is_attacker else (d_kmx, a_kmx)
    return {"index": index, "turns": list(range(1, len(tl) + 1)),
            "own_survivors": os_, "enemy_survivors": es,
            "own_killed": ok, "enemy_killed": ek,
            "by_class": by_class, "procs": procs,
            "kill_matrix": {"own": own_kmx, "enemy": enemy_kmx}}


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
