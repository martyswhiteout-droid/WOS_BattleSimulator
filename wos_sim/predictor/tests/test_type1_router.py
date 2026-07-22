"""Stage 6.8 QA -- the Type-1 router (api.predict's classify-then-serve-the-
frozen-law path). Style mirrors test_deterministic_seam.py: plain pytest
functions, behavioral assertions (winner/confidence/abstain/flags), real
corpus rows cited by id in comments where used. See
wos_sim/formula_research/STAGE6_8_REPORT.md for the design writeup -- in
particular Ambiguity #1, the count==1 domain restriction this test file
exercises directly (test_count_above_one_rejects) and relies on throughout
(every fixture below is a single deployed troop per side).
"""
import inspect
import json

import pytest

from wos_sim.normalize_reports import golden_anchors
from wos_sim.predictor import api, serialize
from wos_sim.predictor import type1_router as router
from wos_sim.predictor.profiles import CLASSES, STATS, ClassQuality, Matchup, SideProfile


def _side(role, cls, tier, fc, panel_pct, count=1, lead=None, joiners=None,
         own_buffs=None, debuffs_on_enemy=None):
    """Single-deployed-troop SideProfile builder (the router's only domain --
    see module docstring)."""
    formation_counts = {c: (float(count) if c == cls else 0.0) for c in CLASSES}
    formation = {c: (1.0 if c == cls else 0.0) for c in CLASSES}
    quality = {c: ClassQuality(tier=tier, fc=fc) for c in CLASSES}
    panel = {(cls, s): panel_pct.get(s, 0.0) / 100.0 for s in STATS}
    return SideProfile(role=role, troops_total=count, stats_mode="scouted",
                       formation=formation, formation_counts=formation_counts,
                       quality=quality, panel=panel, panel_is_final=True,
                       lead_heroes=({cls: lead} if lead else {}),
                       joiners=joiners or [], own_buffs=own_buffs or {},
                       debuffs_on_enemy=debuffs_on_enemy or {})


# --------------------------------------------------------------------------- #
#  corpus-derived fixtures (row ids cited; TYPE1_CORPUS.json)
# --------------------------------------------------------------------------- #
def _farseer_confident():
    """FarSeer_1v1_T1InfvT1Inf_AttInfA+188.6_Gatotlvl1_NoDefenderHero_20260712_083001:
    FarSeer Infantry T1 (Gatot L1, S1/S2 only) attacks a naked Lab-Rat
    Infantry T1 (Lethality/Health un-captured on this row -- flag
    lh_panel_uncaptured -- hence 0% here). Gatot is the ATTACKER's OWN hero,
    not the target's, so the Gatot-kit gate never engages on the decisive
    (attacker-kills-defender) direction; the other direction (hero-less
    defender racing into the Gatot-led attacker) takes the naive-Infantry-
    dealer monotonicity check WITHOUT tripping uncertain, because the
    attacker wins outright. Real observed: attacker wins at turn 104; the
    law's own (Lethality/Health-blind) figure is 105 -- a router WIRING test,
    not a re-validation of the law's historical accuracy (already
    stage6_validate's job)."""
    att = _side("rally", "Infantry", 1, 1,
               {"Attack": 188.6, "Defense": 186.6}, lead="Gatot")
    dfn = _side("garrison", "Infantry", 1, 1, {"Attack": 0.0, "Defense": 0.0})
    return att, dfn


def _labrat_lancer_vs_gatot_inf():
    """LabRat_1v1_T1LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_175807: a
    hero-less Lancer attacks a Gatot-led (S1/S2) Far-Seer Infantry. Real
    observed: defender wins at turn 24. A live profile can never carry a
    Gatot "copy" (no such field exists), so stage5_composition can never
    resolve aura'd/inert state here; a non-Infantry dealer into an
    unresolved-copy Gatot target ALWAYS abstains (gatot_gate_unmodeled) --
    deterministic, not a knife-edge."""
    att = _side("rally", "Lancer", 1, 1,
               {"Attack": 2.8, "Defense": 2.3, "Lethality": 0.5, "Health": 1.5})
    dfn = _side("garrison", "Infantry", 1, 1,
               {"Attack": 272.1, "Defense": 202.1, "Lethality": 10.0, "Health": 10.0},
               lead="Gatot")
    return att, dfn


def _mueller_inert_vs_alpaca():
    """MuellerAlpaca_1v1_T1InfvFC1T1Inf_...NoDefenderHero_20260712_150803:
    Mueller's Gatot is actually INERT (his panel sits at his own no-aura
    baseline) but the router has no "copy" to look that up with, so the
    Infantry dealer on the other side (Alpaca, hero-less) races naively into
    Mueller and trips the monotonicity check (Alpaca is the decisive/faster
    side) -- the OTHER abstain flavor, gatot_kit_unmeasured_inf_dealer. Real
    observed: defender (Alpaca) wins at turn 132."""
    att = _side("rally", "Infantry", 1, 1,
               {"Attack": 194.1, "Defense": 172.2, "Lethality": 122.0, "Health": 118.7},
               lead="Gatot")
    dfn = _side("garrison", "Infantry", 1, 1,
               {"Attack": 514.1, "Defense": 506.9, "Lethality": 115.0, "Health": 114.1})
    return att, dfn


def _near_mirror_coin_flip():
    """Illustrative (not corpus-literal): no hero-less/simple-hero count==1
    corpus row carries a recorded panel_pct (Martin's Stat Bonuses captures
    are all hero-instrument rows -- see STAGE6_8_REPORT.md), so this is a
    synthetic near-mirror built to land inside the <=10% clock-gap band."""
    att = _side("rally", "Infantry", 3, 1,
               {"Attack": 51.0, "Defense": 50.0, "Lethality": 50.0, "Health": 50.0})
    dfn = _side("garrison", "Infantry", 3, 1,
               {"Attack": 50.0, "Defense": 50.0, "Lethality": 50.0, "Health": 50.0})
    return att, dfn


# --------------------------------------------------------------------------- #
#  classifier truth table (spec item 4: tier>6, fc>=3, unknown hero, Gordon,
#  joiners, buffs, multi-class, happy path -- plus the two additions from
#  STAGE6_8_REPORT.md: whole-number tier, count==1, and the relayer guard)
# --------------------------------------------------------------------------- #
def test_happy_path_classifiable():
    att, dfn = _farseer_confident()
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert ok, reason


def test_tier_above_six_rejects():
    # eval-6.8 correction: the ceiling is PER-CLASS. T7 INFANTRY is proc-free
    # (Bands of Steel is always-on; Ambusher/Volley are Lancer/MM T7 unlocks)
    # and G_w(Inf,7) is a MEASURED cell -> T7 Infantry now CLASSIFIES.
    # Lancer/Marksman stay capped at T6; T8+ Infantry is extrapolated-only.
    att, dfn = _farseer_confident()
    att.quality["Infantry"] = ClassQuality(tier=7, fc=1)
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert ok, reason
    att.quality["Infantry"] = ClassQuality(tier=8, fc=1)
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert not ok and "tier/fc" in reason

def test_half_tier_rejects():
    # whole-number-tier addition: stage4_common.base_stats keys on f"T{tier}"
    # and would KeyError on a half tier -- checked up front (STAGE6_8_REPORT.md
    # Ambiguity #2) rather than relying on the exception fallback.
    att, dfn = _farseer_confident()
    att.quality["Infantry"] = ClassQuality(tier=5.5, fc=1)
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert not ok
    assert "tier/fc" in reason


def test_fc_at_or_above_three_rejects():
    att, dfn = _farseer_confident()
    att.quality["Infantry"] = ClassQuality(tier=1, fc=3)
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert not ok
    assert "tier/fc" in reason


def test_unknown_hero_gordon_rejects():
    # Gordon is a REAL, validate.py-recognized hero (unlike a nonsense
    # string) -- exactly why the spec names it: a well-formed profile that
    # still isn't Type-1-classifiable because its hero isn't in {Seo-yoon,
    # Vulcanus, Gatot}.
    att, dfn = _farseer_confident()
    att.lead_heroes = {"Infantry": "Gordon"}
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert not ok
    assert "hero" in reason


def test_joiners_reject():
    att, dfn = _farseer_confident()
    att.joiners = ["Jessie"]
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert not ok
    assert "joiners" in reason


def test_own_buffs_reject():
    att, dfn = _farseer_confident()
    att.own_buffs = {"Attack": 0.1}
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert not ok
    assert "buffs" in reason


def test_debuffs_on_enemy_reject():
    att, dfn = _farseer_confident()
    att.debuffs_on_enemy = {"Defense": 0.1}
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert not ok
    assert "buffs" in reason


def test_multi_class_rejects():
    att, dfn = _farseer_confident()
    att.formation_counts["Lancer"] = 1.0        # now two deployed classes
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert not ok
    assert "multi_class" in reason


def test_count_above_one_rejects():
    # STAGE6_8_REPORT.md Ambiguity #1: found while building this router --
    # army_kill_timeline's sequential-tanking loop (range(n_front), the
    # deployed troop COUNT) is only validated at the single-troop instrument
    # scale; a realistic large single-class stack drives it past the
    # 1500-turn cap (empirically confirmed on the backtest.py composition
    # anchors: a clearly-winnable 10,000v10,000 T6 Infantry mirror came back
    # "capped, defender wins" before this gate was added).
    att, dfn = _farseer_confident()
    att.troops_total = 2
    att.formation_counts["Infantry"] = 2.0
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert not ok
    assert "count" in reason


def test_relayer_ambiguous_symmetric_nonfinal_panel_rejects():
    # STAGE6_8_REPORT.md Ambiguity #3: replicates construct.build's own
    # relayering trigger (symmetric, non-final, scouted panels) rather than
    # risk silently diverging from what the turn engine would have relayered.
    panel = {(c, s): 0.1 for c in CLASSES for s in STATS}
    common = dict(
        troops_total=1, stats_mode="scouted",
        formation={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0},
        formation_counts={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0},
        quality={c: ClassQuality(tier=1, fc=1) for c in CLASSES},
        panel=dict(panel), panel_is_final=False)
    att = SideProfile(role="rally", **common)
    dfn = SideProfile(role="garrison", **common)
    ok, reason = router._type1_classifiable(Matchup(att, dfn))
    assert not ok
    assert "relayer_ambiguous" in reason


def test_golden_backtest_profiles_all_reject_tier_fc():
    # Hard invariant: T12/FC10 real battles must all classify NOT-
    # classifiable, and specifically for the tier/fc reason (checked before
    # multi_class so a multi-class T12 profile still reports tier/fc).
    for aid, scen, _exp in golden_anchors():
        own = serialize.profile_from_dict(scen["own"])
        enemy = serialize.profile_from_dict(scen["enemy"])
        ok, reason = router._type1_classifiable(Matchup(own, enemy))
        assert not ok, f"{aid} unexpectedly classified as Type-1: {reason}"
        assert "tier/fc" in reason, f"{aid} rejected for {reason!r}, expected tier/fc"


# --------------------------------------------------------------------------- #
#  hero -> kit mapping
# --------------------------------------------------------------------------- #
def _hero_side(name):
    return SideProfile(role="rally", troops_total=1,
                       formation={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0},
                       formation_counts={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0},
                       quality={c: ClassQuality(tier=1, fc=1) for c in CLASSES},
                       lead_heroes=({"Infantry": name} if name else {}))


def test_seoyoon_maps_to_level_3_kit_case_and_hyphen_insensitive():
    for spelling in ("Seo-yoon", "SeoYoon", "seo yoon", "SEO-YOON"):
        assert router._kit_for_side(_hero_side(spelling), "Infantry") == {"seoyoon": 3}


def test_vulcanus_maps_to_flag_kit():
    assert router._kit_for_side(_hero_side("Vulcanus"), "Infantry") == {"vulcanus": True}


def test_gatot_maps_to_flag_kit_no_copy():
    assert router._kit_for_side(_hero_side("Gatot"), "Infantry") == {"gatot": True}


def test_no_hero_maps_to_empty_kit():
    assert router._kit_for_side(_hero_side(None), "Infantry") == {}


# --------------------------------------------------------------------------- #
#  router end-to-end (through api.predict -- the real call path)
# --------------------------------------------------------------------------- #
def test_corpus_derived_confident_winner():
    att, dfn = _farseer_confident()
    fc = api.predict(att, dfn, n=1, seed=0, params={"engine": "turn"})
    assert fc.engine_path == "deterministic_law"
    assert fc.confidence == "validated"
    assert fc.calibrated is True
    assert fc.stochastic is False
    assert fc.near_even is False
    assert fc.n == 1
    assert fc.p_win.p == 1.0
    assert fc.p_win.se == 0.0
    assert fc.engine_model_error == router.LAW_MODEL_ERROR
    assert "stage6.7" in fc.engine_note
    assert "105" in fc.engine_note                  # the law's own exact clock

    # cross-check: the SAME law call (predict_deterministic_battle) the
    # router uses internally, called directly with the equivalent army
    # dicts, reproduces the identical clock -- proves the SideProfile ->
    # army/kit mapping is wired correctly, not just "a Forecast came back".
    direct = api.predict_deterministic_battle(
        [{"cls": "Infantry", "tier": 1, "fc": 1, "count": 1,
          "panel": {"Attack": 188.6, "Defense": 186.6, "Lethality": 0.0, "Health": 0.0}}],
        [{"cls": "Infantry", "tier": 1, "fc": 1, "count": 1,
          "panel": {"Attack": 0.0, "Defense": 0.0, "Lethality": 0.0, "Health": 0.0}}],
        att_kit={"gatot": True})
    assert direct["winner"] == "attacker"
    assert direct["turns"] == 105


def test_serialize_round_trips_without_modification():
    att, dfn = _farseer_confident()
    fc = api.predict(att, dfn, n=1, seed=0, params={"engine": "turn"})
    d = serialize.forecast_to_dict(fc)
    json.dumps(d)                                    # must be JSON-serializable
    assert d["engine"]["path"] == "deterministic_law"
    assert d["engine"]["confidence"] == "validated"
    assert d["engine"]["calibrated"] is True
    assert d["engine"]["stochastic"] is False
    assert d["engine"]["near_even"] is False
    assert d["verdict"]["win"]["p"] == 1.0
    assert d["battle_timeline"] is None
    assert d["skill_telemetry"] is None


def test_coin_flip_mapping():
    att, dfn = _near_mirror_coin_flip()
    fc = api.predict(att, dfn, n=1, seed=0, params={"engine": "turn"})
    assert fc.engine_path == "deterministic_law"
    assert fc.confidence == "coin_flip"
    assert fc.near_even is True
    assert fc.p_win.p == 0.5
    assert fc.calibrated is True
    assert fc.stochastic is False
    assert "coin flip" in fc.engine_note.lower()


def test_abstain_fallthrough_non_infantry_dealer():
    att, dfn = _labrat_lancer_vs_gatot_inf()
    fc = api.predict(att, dfn, n=5, seed=0, params={"engine": "turn"})
    assert fc.engine_path != "deterministic_law"     # fell through to the turn engine
    assert "deterministic law abstained" in fc.engine_note
    assert "gatot_gate_unmodeled" in fc.engine_note


def test_abstain_fallthrough_naive_infantry_dealer_monotonicity():
    att, dfn = _mueller_inert_vs_alpaca()
    fc = api.predict(att, dfn, n=5, seed=0, params={"engine": "turn"})
    assert fc.engine_path != "deterministic_law"
    assert "deterministic law abstained" in fc.engine_note
    assert "gatot_kit_unmeasured_inf_dealer" in fc.engine_note


def test_try_deterministic_converts_exceptions_to_abstain(monkeypatch):
    # "OR raises" (spec item 2): a bug/edge-case inside the law must fall
    # through, never break predict(). Force one via monkeypatch.
    att, dfn = _farseer_confident()

    def boom(*_a, **_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(api, "predict_deterministic_battle", boom)
    fc, note = router._try_deterministic(Matchup(att, dfn))
    assert fc is None
    assert "exception:RuntimeError" in note


def test_opt_out_param_forces_turn_path():
    att, dfn = _farseer_confident()
    fc = api.predict(att, dfn, n=5, seed=0,
                     params={"engine": "turn", "deterministic_router": False})
    assert fc.engine_path != "deterministic_law"


def test_not_classifiable_is_byte_identical_to_pre_router_note():
    # A NOT-classifiable matchup must take the untouched pre-6.8 code path:
    # no "(deterministic law abstained...)" clause anywhere, since the
    # router's preamble never even calls try_predict for it.
    att, dfn = _farseer_confident()
    att.lead_heroes = {"Infantry": "Gordon"}         # -> not classifiable
    fc = api.predict(att, dfn, n=5, seed=0, params={"engine": "turn"})
    assert fc.engine_path != "deterministic_law"
    assert "deterministic law abstained" not in fc.engine_note


def test_predict_signature_unchanged():
    params = list(inspect.signature(api.predict).parameters)
    assert params == ["own", "enemy", "n", "seed", "kernel_impl", "params",
                      "engine_model_error"]


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))


# ---- eval-6.8 additions: the per-class tier ceiling ------------------------

def test_t7_lancer_and_marksman_rejected():
    # T7 unlocks Ambusher (Lancer) / Volley (Marksman) -- chance procs
    for cls in ("Lancer", "Marksman"):
        att = _side("rally", cls, 7, 1, {"Attack": 150.0, "Defense": 150.0})
        dfn = _side("garrison", cls, 1, 1, {"Attack": 100.0, "Defense": 100.0})
        ok, reason = router._type1_classifiable(Matchup(att, dfn))
        assert not ok and "tier/fc" in reason


def test_t7_infantry_routes_end_to_end():
    # the T7 discriminator battle shape (no-hero T7 Inf vs FC1T1+Vulcanus)
    # must now route deterministically: exact clock, honest labels
    att = _side("rally", "Infantry", 7, 1,
                {"Attack": 179.1, "Defense": 179.7,
                 "Lethality": 112.0, "Health": 108.7})
    dfn = _side("garrison", "Infantry", 1, 1,
                {"Attack": 176.2, "Defense": 169.0,
                 "Lethality": 109.7, "Health": 109.3}, lead="Vulcanus")
    fc = api.predict(att, dfn, n=50, seed=0, params={"engine": "turn"})
    assert fc.engine_path == "deterministic_law"
    assert fc.stochastic is False and fc.calibrated is True
    assert fc.p_win.p == 1.0
    # observed battle: kill at [75,77]; the folded law lands inside
    assert "76" in fc.engine_note or "75" in fc.engine_note or "77" in fc.engine_note
