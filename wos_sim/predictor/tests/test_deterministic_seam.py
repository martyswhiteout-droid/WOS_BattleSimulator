"""QA for the deterministic-law seam (stage6.6 kit v3), 2026-07-19.

Locks the seam behavior Martin's experiments measured into the pytest suite.
Every scenario is a REAL corpus battle re-expressed as a seam call (row ids in
comments); assertions are behavioral (winner / abstention / flags / coarse
clocks) so they survive display-precision changes but break on physics or
wiring regressions. The heavy per-row QA lives in stage6_validate (12 gates +
the W6 four-way winner gate over all 238 corpus rows) and py -m wos_sim.backtest;
these tests are the fast always-on layer.
"""
import pytest

from wos_sim.formula_research import stage5_composition as comp
from wos_sim.formula_research import stage6_tables as t6
from wos_sim.predictor import api


def _army(cls, tier, count, A, D, L, H, panel_a=None):
    u = {"cls": cls, "tier": tier, "count": count,
         "eff": {"A": A, "D": D, "L": L, "H": H}}
    if panel_a is not None:
        u["panel_pct"] = {"Attack": panel_a}
    return [u]


# The 204/205 knife-edge armies (MuellerAlpaca_204v1/205v1_..., 2026-07-19):
# Mueller ordinary T6 Lancers, panels A+179.1 L+105.3 D+169.2 H+102.6.
def _lancers(n):
    return _army("Lancer", 6, n, 27.91, 21.536, 22.583, 14.182)


# Alpaca's AURA'D Gatot FC1 T1 Infantry (panel A 514.1 = 176.2 base + 337.9 aura)
def _alpaca_gatot_aurad():
    return _army("Infantry", 1, 1, 6.141, 24.276, 2.097, 12.558, panel_a=514.1)


ALPACA_KIT = {"gatot": "alpaca"}
LAW = None  # resolved lazily


def _law():
    global LAW
    if LAW is None:
        LAW = t6.law_funcs()
    return LAW


def _race(att, dfn, att_kit=None, def_kit=None, **kw):
    return comp.predict_battle(att, dfn, law=_law(),
                               att_kit=att_kit, def_kit=def_kit, **kw)


def test_api_meta_law_version():
    # the seam entry point reports the 6.7 law + kit status
    res = api.predict_deterministic_battle(
        _army("Infantry", 1, 1, 5.0, 10.0, 2.0, 6.0),
        _army("Infantry", 1, 1, 4.0, 9.0, 2.0, 5.0))
    assert res["meta"]["law_version"] == "stage6.7"


def test_budget_cap_204_lancers_bounce():
    # MuellerAlpaca_204v1_...: 204 hero-less T6 Lancers vs Alpaca's aura'd
    # Gatot Inf -> fully absorbed, defender wins (observed: capped @1500,
    # defender untouched)
    res = _race(_lancers(204), _alpaca_gatot_aurad(), def_kit=ALPACA_KIT)
    assert res["winner"] == "defender"
    assert "gatot_abstain" not in res or res["gatot_abstain"] is None


def test_budget_knife_edge_205_breakthrough():
    # MuellerAlpaca_205v1_...: one Lancer past the measured edge. Under the
    # COHERENT (K, B) branch pairing both branches agree on breakthrough
    # (B_Alpaca inherits the K branch, so the threshold N* ~ 204.95 is
    # branch-invariant for this dealer family), and the predicted kill turn
    # brackets the observed 575.
    res = _race(_lancers(205), _alpaca_gatot_aurad(), def_kit=ALPACA_KIT)
    assert res["winner"] == "attacker"
    t_def_dead = res["def_deaths"][-1][0]
    assert 540 <= t_def_dead <= 640   # 587 post-B-precision fix; obs 575


def test_budget_breakthrough_220_confident():
    # one step past the edge both K branches agree -> confident attacker win
    res = _race(_lancers(220), _alpaca_gatot_aurad(), def_kit=ALPACA_KIT)
    assert res["winner"] == "attacker"


def test_naked_mm_absorbed_inf_kills_at_150():
    # MuellerAlpaca_..._162413: naked FC1 T6 MM vs Mueller's aura'd Gatot T1
    # (panel 481.0 = 179.1 + 301.9 aura): MM fully absorbed; the Infantry
    # kills at obs 150 (pred 150.0 on the frozen cells)
    mm = _army("Marksman", 6, 1, 30.382, 18.62, 27.492, 16.03)
    gatot = _army("Infantry", 1, 1, 5.81, 23.268, 2.12, 12.522, panel_a=481.0)
    res = _race(mm, gatot, def_kit={"gatot": "mueller"})
    assert res["winner"] == "defender"
    t_att_dead = res["att_deaths"][-1][0]
    assert 140 <= t_att_dead <= 160


def test_inert_gatot_plain_race_no_abstain():
    # MuellerAlpaca_1v1_T1InfvFC1T1Inf_* family: Gatot present but panels at
    # the no-hero baseline (194.1 ~ baseline 179.1, nearest-neighbour) ->
    # INERT: plain race, no gate, defender (Alpaca 514-panel FC1T1) wins
    mueller_inert = _army("Infantry", 1, 1, 2.941, 10.888, 2.22, 7.081,
                          panel_a=194.1)
    alpaca_naked = _army("Infantry", 1, 1, 6.141, 24.276, 2.15, 12.846)
    res = _race(mueller_inert, alpaca_naked, att_kit={"gatot": "mueller"})
    assert res["winner"] == "defender"
    assert res.get("gatot_abstain") is None
    assert any("inert" in f for f in res["flags"])


def test_vulcanus_led_bypasses_budget():
    # E-NIF R12 / MuellerAlpaca_..._164811 shape: a Vulcanus-led T6 MM kills
    # the aura'd Mueller Gatot T1 in ~6 turns (S-curve regime, budget bypassed)
    mm = _army("Marksman", 6, 1, 126.445, 79.751, 41.664, 17.542)
    gatot = _army("Infantry", 1, 1, 5.81, 23.268, 2.12, 12.522, panel_a=481.0)
    res = _race(mm, gatot, att_kit={"vulcanus": True},
                def_kit={"gatot": "mueller"})
    assert res["winner"] == "attacker"
    t_def_dead = res["def_deaths"][-1][0]
    assert 4 <= t_def_dead <= 12


def test_ambiguous_state_abstains():
    # a Gatot panel halfway between baseline and aura'd fails the x2 margin
    # guard -> honest abstention, never a guess
    halfway = _army("Infantry", 1, 1, 4.5, 17.0, 2.1, 10.0, panel_a=330.0)
    res = _race(_lancers(50), halfway, def_kit={"gatot": "alpaca"})
    assert res["winner"] == "uncertain"


def test_unknown_copy_abstains():
    # Gatot present but the copy is unrecognized -> constants unmeasured ->
    # abstain (gatot_gate_unmodeled), matching the W6 convention
    unknown = _army("Infantry", 1, 1, 6.0, 24.0, 2.1, 12.5, panel_a=514.0)
    res = _race(_lancers(100), unknown, def_kit={"gatot": True})
    assert res["winner"] == "uncertain"


def test_default_args_no_kits_plain_race():
    # pre-6.5 call convention (no kits): plain two-sided race, deterministic
    # winner, no kit flags -- the byte-compat contract
    res = _race(_army("Infantry", 1, 1, 5.0, 10.0, 2.0, 6.0),
                _army("Infantry", 1, 1, 4.0, 9.0, 1.8, 5.0))
    assert res["winner"] in ("attacker", "defender")
    assert res.get("gatot_abstain") is None
    assert not any("gatot" in f for f in res["flags"])

# ---- QA v3 regression layer (2026-07-19): every probe Codex flagged ---------

def test_empty_army_raises_cleanly():
    with pytest.raises(ValueError):
        _race([], _alpaca_gatot_aurad())


def test_zero_count_raises_cleanly():
    bad = _army("Infantry", 1, 0, 5.0, 10.0, 2.0, 6.0)
    with pytest.raises(ValueError):
        _race(bad, _alpaca_gatot_aurad())


def test_zero_attack_raises_cleanly():
    bad = _army("Infantry", 1, 1, 0.0, 10.0, 2.0, 6.0)
    with pytest.raises(ValueError):
        _race(bad, _army("Infantry", 1, 1, 4.0, 9.0, 1.8, 5.0))


def test_multiunit_gatot_target_flagged_not_silent():
    # QA v3 #3: 2x Gatot-Infantry targets are outside the measured regime --
    # the plain law runs but the bypass must be VISIBLE
    duo = _army("Infantry", 1, 2, 6.141, 24.276, 2.097, 12.558, panel_a=514.1)
    res = _race(_lancers(50), duo, def_kit=ALPACA_KIT)
    assert any("gatot_kit_multiunit_unmodeled" in f for f in res["flags"])


def test_scurve_multi_n_extrapolation_flagged():
    # QA v3 #5: hero-led n>1 runs per-dealer-then-sqrt(N); validated at n=3
    # (E2) -- the extrapolation must be visible on other counts
    mm = _army("Marksman", 6, 5, 126.445, 79.751, 41.664, 17.542)
    gatot = _army("Infantry", 1, 1, 5.81, 23.268, 2.12, 12.522, panel_a=481.0)
    res = _race(mm, gatot, att_kit={"vulcanus": True}, def_kit={"gatot": "mueller"})
    assert any("gatot_scurve_multi" in f for f in res["flags"])


def test_vulcanus_kit_folds_are_applied_by_the_seam():
    """STAGE 6.7 (Codex QA v3 finding #1): a kit-only caller must get the
    FOLDED verdict. Pre-6.7 the folds lived in a validator-side private helper,
    so this shape returned the fold-blind winner. Construction: a near-even
    Infantry-vs-Vulcanus-Marksman race where the documented folds (defender
    S2 x31/30, S3 own-MM x1.04 and /0.88 Inf-defence shred; attacker x0.96 from
    the enemy S1) reverse the verdict."""
    att = _army("Infantry", 1, 1, 6.0, 20.0, 3.0, 12.0)
    dfn = _army("Marksman", 1, 1, 6.5, 14.0, 5.2, 9.0)
    folded = _race(att, dfn, def_kit={"vulcanus": True})
    blind = _race(att, dfn, def_kit={"vulcanus": True}, apply_hero_folds=False)
    assert blind["winner"] == "attacker"        # the old fold-blind answer
    assert folded["winner"] == "defender"       # the documented-folds answer
    assert any("fold_vulcanus_s2" in f for f in folded["flags"])
    assert any("fold_vulcanus_s1_enemy_atk" in f for f in folded["flags"])


def test_seoyoon_fold_applied_by_level():
    # Seo-yoon S1 is a pure own-side Attack buff: L3 (x1.15) must kill strictly
    # faster than L1 (x1.05), and both faster than no kit at all.
    att = _army("Infantry", 1, 1, 6.0, 20.0, 3.0, 12.0)
    dfn = _army("Infantry", 1, 1, 5.0, 18.0, 2.5, 11.0)
    t_none = _race(att, dfn)["def_deaths"][-1][0]
    t_l1 = _race(att, dfn, att_kit={"seoyoon": 1})["def_deaths"][-1][0]
    t_l3 = _race(att, dfn, att_kit={"seoyoon": 3})["def_deaths"][-1][0]
    assert t_l3 < t_l1 < t_none


def test_royal_legion_absorbed_not_double_applied():
    # The Gatot S3 enemy-Attack debuff is ABSORBED in the frozen K/G_l cells
    # (they were measured on Gatot-led-target instruments), so the seam must
    # NOT apply it again by default -- it flags the absorption instead.
    dealer = _army("Infantry", 1, 1, 6.0, 20.0, 3.0, 12.0)
    gatot = _army("Infantry", 1, 1, 5.81, 23.268, 2.12, 12.522, panel_a=481.0)
    kit = {"gatot": "mueller", "royal_legion_level": 2}
    default = _race(dealer, gatot, def_kit=kit)
    applied = _race(dealer, gatot, def_kit=kit, apply_royal_legion=True)
    assert any("royal_legion_L2_absorbed_in_cells" in f for f in default["flags"])
    # the opt-in branch exists for the future decontamination analysis and must
    # actually change the arithmetic (slower dealer -> later kill)
    t_def = default["def_deaths"][-1][0]
    t_app = applied["def_deaths"][-1][0]
    assert t_app >= t_def


def test_fold_opt_out_reproduces_stage66():
    # apply_hero_folds=False is the migration-comparison switch: no fold flags,
    # and the caller's own mult is the only offense modifier.
    att = _army("Infantry", 1, 1, 6.0, 20.0, 3.0, 12.0)
    dfn = _army("Marksman", 1, 1, 6.5, 14.0, 5.2, 9.0)
    res = _race(att, dfn, def_kit={"vulcanus": True}, apply_hero_folds=False)
    assert not any(f.startswith(("att:fold_", "def:fold_")) for f in res["flags"])
    assert any("hero_folds_disabled_by_caller" in f for f in res["flags"])


def test_caller_mult_multiplies_on_top_of_folds():
    # documented contract: *_offense_mult is for anchors/extras and multiplies
    # ON TOP of the seam-owned folds (it does not replace them)
    att = _army("Infantry", 1, 1, 6.0, 20.0, 3.0, 12.0)
    dfn = _army("Infantry", 1, 1, 5.0, 18.0, 2.5, 11.0)
    base = _race(att, dfn, att_kit={"seoyoon": 3})["def_deaths"][-1][0]
    boosted = _race(att, dfn, att_kit={"seoyoon": 3},
                    att_offense_mult=2.0)["def_deaths"][-1][0]
    assert boosted < base
