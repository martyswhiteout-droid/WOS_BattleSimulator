"""Stage 8.1 army-router tests: the classifier's domain boundaries, the
end-to-end seam behaviour on the REAL 20k/2k anchors, and the guarantee that
nothing outside the validated domain is captured."""
import pytest

from wos_sim.predictor import api, army_router, serialize
from wos_sim.predictor.profiles import Matchup

# the real exp1/exp2 encampment mirror panels (displayed %)
ATT = {"Attack": 176.2, "Defense": 169.0, "Lethality": 109.7, "Health": 109.3}
DEF = {"Attack": 174.3, "Defense": 153.0, "Lethality": 112.0, "Health": 108.7}
OBSERVED_SURV = 0.24185          # attacker survivors 4,837 / 20,000
#: the router is OPT-IN after the 2026-07-25 QA -- seam tests must enable it
ARMY_ON = {"army_router": True}


def prof(role, cls, n, panel_pct, tier=1, fc=1, heroes=None, joiners=None,
         own_buffs=None, debuffs=None):
    d = {"role": role, "troops_total": n, "stats_mode": "scouted",
         "formation_counts": {cls: n},
         "quality": {cls: {"tier": tier, "fc": fc}},
         # schema stores the panel as a FRACTION (1.762 == 176.2%)
         "panel": {f"{cls}|{k}": v / 100.0 for k, v in panel_pct.items()},
         "panel_is_final": True, "lead_heroes": heroes or {}, "joiners": joiners or []}
    if own_buffs:
        d["own_buffs"] = own_buffs
    if debuffs:
        d["debuffs_on_enemy"] = debuffs
    return serialize.profile_from_dict(d)


def mirror(n=20000, **kw):
    return Matchup(prof("rally", "Infantry", n, ATT, **kw),
                   prof("garrison", "Infantry", n, DEF, **kw))


def own_surv(fc):
    return 1.0 - serialize.forecast_to_dict(fc)["army_losses"]["own"]["median"] / 100.0


# ---- classifier boundaries -------------------------------------------------
def test_happy_path_classifies():
    ok, reason = army_router.army_classifiable(mirror())
    assert ok, reason


@pytest.mark.parametrize("kw,expect", [
    ({"tier": 7}, "tier/fc"),                 # T7 unlocks Ambusher/Volley procs
    ({"fc": 3}, "tier/fc"),                   # FC3 unlocks Crystal* procs
    ({"heroes": {"Infantry": "Gatot"}}, "heroes"),
    ({"joiners": ["Mia"]}, "joiners"),
    ({"own_buffs": {"Attack": 0.1}}, "buffs"),
])
def test_out_of_domain_rejected(kw, expect):
    ok, reason = army_router.army_classifiable(mirror(**kw))
    assert not ok and reason.startswith(expect), reason


def test_below_army_scale_rejected():
    ok, reason = army_router.army_classifiable(mirror(n=50))
    assert not ok and reason.startswith("below_army_scale"), reason


def test_cross_class_rejected():
    m = Matchup(prof("rally", "Infantry", 20000, ATT),
                prof("garrison", "Lancer", 20000, DEF))
    ok, reason = army_router.army_classifiable(m)
    assert not ok and reason.startswith("cross_class"), reason


def test_cross_tier_rejected():
    m = Matchup(prof("rally", "Infantry", 20000, ATT, tier=1),
                prof("garrison", "Infantry", 20000, DEF, tier=6))
    ok, reason = army_router.army_classifiable(m)
    assert not ok and reason.startswith("cross_tier"), reason


def test_multi_class_rejected():
    own = serialize.profile_from_dict({
        "role": "rally", "troops_total": 20000, "stats_mode": "scouted",
        "formation_counts": {"Infantry": 10000, "Lancer": 10000},
        "quality": {"Infantry": {"tier": 1, "fc": 1}, "Lancer": {"tier": 1, "fc": 1}},
        "panel": {}, "panel_is_final": True, "lead_heroes": {}, "joiners": []})
    ok, reason = army_router.army_classifiable(
        Matchup(own, prof("garrison", "Infantry", 20000, DEF)))
    assert not ok and reason.startswith("multi_class"), reason


# ---- end-to-end through the seam ------------------------------------------
def test_seam_routes_and_reproduces_the_real_anchor():
    m = mirror()
    fc = api.predict(m.own, m.enemy, n=5, seed=0, params=ARMY_ON)
    d = serialize.forecast_to_dict(fc)
    assert d["engine"]["path"] == "army_law"
    assert d["engine"]["stochastic"] is False
    assert d["verdict"]["win"]["p"] > 0.99             # attacker (own) wins -- derived, not forced
    # within the declared +-10% band of the observed 24.185%
    assert abs(own_surv(fc) - OBSERVED_SURV) / OBSERVED_SURV < 0.10


def test_outcome_is_scale_invariant():
    """The measured property: 10x the army, identical survivor fraction."""
    a = own_surv(api.predict(mirror(20000).own, mirror(20000).enemy, n=5, seed=0, params=ARMY_ON))
    b = own_surv(api.predict(mirror(2000).own, mirror(2000).enemy, n=5, seed=0, params=ARMY_ON))
    assert abs(a - b) < 1e-6


def test_model_error_is_the_honest_band():
    d = serialize.forecast_to_dict(api.predict(mirror().own, mirror().enemy, n=5, seed=0, params=ARMY_ON))
    assert d["engine"]["model_error"] == pytest.approx(0.10)
    assert d["engine"]["confidence"] == "directional"      # never "validated"


def test_opt_out_falls_back_to_turn_engine():
    m = mirror()
    d = serialize.forecast_to_dict(api.predict(
        m.own, m.enemy, n=5, seed=0,
        params={"engine": "turn"}))
    assert d["engine"]["path"] == "pvp_turn_engine"


def test_golden_style_t12_profile_is_not_captured():
    """The golden backtest profiles are T12/FC10 -- they must keep their engine."""
    big = {"Attack": 1000.0, "Defense": 900.0, "Lethality": 800.0, "Health": 800.0}
    m = Matchup(prof("rally", "Infantry", 500000, big, tier=12, fc=10),
                prof("garrison", "Infantry", 500000, big, tier=12, fc=10))
    ok, reason = army_router.army_classifiable(m)
    assert not ok and reason.startswith("tier/fc"), reason


# ---- regressions for the 2026-07-25 independent-QA P1 findings --------------
def test_default_routing_is_OFF_after_qa():
    """QA P1 #4: the router is OPT-IN. A qualifying matchup must NOT reach
    army_law unless params explicitly enables it, so no user prediction depends
    on an uncalibrated band."""
    m = mirror()
    d = serialize.forecast_to_dict(api.predict(m.own, m.enemy, n=5, seed=0))
    assert d["engine"]["path"] != "army_law"


def test_cross_fc_rejected():
    """QA P1 #2: the research base table varies with FC below T10, so unequal FC
    breaks the 'base stats cancel' precondition and previously REVERSED the
    winner (FC1-v-FC2)."""
    m = Matchup(prof("rally", "Infantry", 20000, ATT, tier=1, fc=1),
                prof("garrison", "Infantry", 20000, DEF, tier=1, fc=2))
    ok, reason = army_router.army_classifiable(m)
    assert not ok and reason.startswith("cross_fc"), reason


def test_solver_limit_never_fabricates_a_winner():
    """QA P1 #1: with both sides alive at the solver's numerical limit the old
    code broke the tie toward the attacker and zeroed the defender. GAME_RULES
    s.424 (confirmed): every battle ends in a wipe -- there is no turn cap, so a
    capped state is a solver artefact and must abstain, preserving both counts."""
    from wos_sim.formula_research.stage8_army import predict_army_same_class
    # a near-parity, extremely slow exchange: both sides survive the limit
    stat = {"A": 1.0, "D": 1000.0, "L": 1.0, "H": 1000.0}
    res = predict_army_same_class(stat, dict(stat), n_att=20000, n_def=20000,
                                  rate=1e-6)
    assert res["capped"] is True
    assert res["winner"] == "uncertain"
    assert res["att_survivors"] > 0 and res["def_survivors"] > 0   # both preserved


def test_solver_limit_abstains_through_the_seam():
    """The router must fall through (not emit a fabricated army_law verdict)
    when the backbone returns 'uncertain'."""
    from wos_sim.formula_research import stage8_army
    m = mirror()
    real = stage8_army.predict_army_cross_class

    def fake(*a, **kw):
        r = real(*a, **kw)
        return {**r, "winner": "uncertain", "reason": "forced for the test"}

    stage8_army.predict_army_cross_class = fake
    try:
        fc, note = army_router.try_army(m)
        assert fc is None and "abstained" in note, (fc, note)
    finally:
        stage8_army.predict_army_cross_class = real


# ---- cross-class (2026-07-28): R measured with two battles per pair ---------
def x_pair(att_cls, att_panel, def_cls, def_panel, n=10000):
    return Matchup(prof("rally", att_cls, n, att_panel, tier=6, fc=1),
                   prof("garrison", def_cls, n, def_panel, tier=6, fc=1))


INF_A = {"Attack": 199.2, "Defense": 192.0, "Lethality": 119.7, "Health": 119.3}
LAN_D = {"Attack": 189.1, "Defense": 160.7, "Lethality": 115.3, "Health": 112.6}


def test_cross_class_now_classifies_at_the_measured_tier():
    ok, reason = army_router.army_classifiable(
        x_pair("Infantry", INF_A, "Lancer", LAN_D))
    assert ok, reason


def test_cross_class_rejected_off_the_measured_tier():
    """R is measured only at tier 6; other tiers must not extrapolate."""
    m = Matchup(prof("rally", "Infantry", 10000, INF_A, tier=1, fc=1),
                prof("garrison", "Lancer", 10000, LAN_D, tier=1, fc=1))
    ok, reason = army_router.army_classifiable(m)
    assert not ok and reason.startswith("cross_class_tier"), reason


def test_cross_class_reproduces_its_anchor():
    """exp4: 10k Infantry vs 10k Lancer, observed attacker 0.4536."""
    m = x_pair("Infantry", INF_A, "Lancer", LAN_D)
    fc = api.predict(m.own, m.enemy, n=5, seed=0, params=ARMY_ON)
    d = serialize.forecast_to_dict(fc)
    assert d["engine"]["path"] == "army_law"
    assert abs(own_surv(fc) - 0.4536) / 0.4536 < 0.05


def test_near_parity_cross_class_is_an_honest_probability():
    """exp5 sits 0.24% from parity. Phase A: instead of abstaining, the router
    reports P(attacker) under the law's MEASURED error -- well below certainty,
    above a coin flip, and never the old forced 1.0 / 0.5."""
    mm_def = {"Attack": 189.1, "Defense": 165.7, "Lethality": 131.2, "Health": 128.6}
    m = x_pair("Infantry", INF_A, "Marksman", mm_def)
    fc, note = army_router.try_army(m)
    assert fc is not None, note
    d = serialize.forecast_to_dict(fc)
    assert 0.55 < d["verdict"]["win"]["p"] < 0.95
    assert d["verdict"]["win"]["p"] + d["verdict"]["loss"]["p"] + d["verdict"]["mutual"]["p"] == pytest.approx(1.0)


def test_R_table_reciprocal_and_identity():
    from wos_sim.formula_research.stage8_army import class_pair_R
    fwd, _ = class_pair_R("Infantry", "Lancer")
    rev, _ = class_pair_R("Lancer", "Infantry")
    assert abs(fwd * rev - 1.0) < 1e-9          # reverse is the reciprocal
    assert class_pair_R("Lancer", "Lancer") == (1.0, 0.0)   # same class is exact
