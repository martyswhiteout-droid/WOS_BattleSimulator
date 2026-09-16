"""TURN_PARAMS["modifier_stacking"] — DD/DT composition mode (default
"multiplicative" since 2026-09-16; "legacy" reproduces the pre-change engine). See pvp_turn_engine.TURN_PARAMS's comment and
wos_sim/formula_research/EXPERIMENT_DT_STACKING.md s.8 (the pre-registered,
six-battle measurement this option implements): stacked same-hero
Damage-Taken reductions were measured to compose multiplicatively
(``prod(1-x_i)``), not additively-then-gamma-compressed as the legacy mode
does; Damage-Dealt composition is UNMEASURED (a symmetry hypothesis only).

Three modes: "legacy" (today's additive-sum-then-``mod_gamma``, byte-for-byte
unchanged), "dt_multiplicative" (DT only -> ``prod(1+x_i)``, no gamma; DD
stays legacy), "multiplicative" (both channels -> ``prod(1+x_i)``, no gamma).
"""
import json
import os

import pytest

from wos_sim.models import DamageCategory, TroopType
from wos_sim.predictor import api
from wos_sim.predictor.serialize import profile_from_dict
from wos_sim.pvp_engine import A, D, H, L
from wos_sim.pvp_turn_engine import TypeStack, _Mods, _stack_view

_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
_GEN15_50_10_40 = os.path.join(_ROOT, "Scenarios", "Gen15_50_10_40.json")
_GEN15_RALLY_WM = os.path.join(_ROOT, "Scenarios", "Gend15", "Gen15_Rally_WM.json")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _own_enemy(path):
    d = _load(path)
    return profile_from_dict(d["own"]), profile_from_dict(d["enemy"])


def _stack():
    astat = {A: 100.0, D: 100.0, L: 100.0, H: 100.0}
    return TypeStack(TroopType.INFANTRY, 12, 100_000, 100_000, dict(astat), 100.0)


def test_legacy_is_byte_identical(monkeypatch):
    """The "legacy" MODE must reproduce the pre-2026-09-11 engine exactly, and
    passing it explicitly must equal making it the default.

    Amended 2026-09-11 when the default became dt_multiplicative (a 2026-09-11
    interim): the original assertion compared the DEFAULT run to legacy, which
    is no longer the same thing, and used exact float equality on a summed
    mean (2 ULP noise). The default is now "multiplicative" (2026-09-16 owner
    decision, Martin) -- see test_shipped_default_is_multiplicative below."""
    import os
    import pytest
    from wos_sim import pvp_turn_engine as eng
    own, enemy = _own_enemy(_GEN15_50_10_40)
    explicit = api.predict(own, enemy, n=30, seed=4471,
                           params={"engine": "turn", "modifier_stacking": "legacy"})
    monkeypatch.setitem(eng.TURN_PARAMS, "modifier_stacking", "legacy")
    as_default = api.predict(own, enemy, n=30, seed=4471, params={"engine": "turn"})
    assert as_default.p_win.p == pytest.approx(explicit.p_win.p, abs=1e-12)
    assert as_default.army_losses["own"].mean == pytest.approx(explicit.army_losses["own"].mean, rel=1e-9)
    assert as_default.sim_hold_rate.p == pytest.approx(explicit.sim_hold_rate.p, abs=1e-12)
    # Frozen pre-change signature: under the additive rule, Gen15_Rally_WM's garrison
    # Infantry carry Estrella S3 + 3x Wu Ming S1 = exactly -100% Normal DT, the sum
    # floors at -1.0 and incoming damage is multiplied by 0 -- an immunity cliff that
    # held 99/100 runs (n=100, seed=4471, measured 2026-09-11). Legacy must still do it.
    wm = os.path.join(os.path.dirname(__file__), "..", "..", "..", "Scenarios", "Gend15", "Gen15_Rally_WM.json")
    if os.path.exists(wm):
        import json
        d = json.load(open(wm, encoding="utf-8"))
        o = profile_from_dict(d["own"]); o.joiners = ["Wu Ming"] * 3 + ["Gatot"]
        fc = api.predict(o, profile_from_dict(d["enemy"]), n=100, seed=4471,
                         params={"engine": "turn", "modifier_stacking": "legacy"})
        assert fc.sim_hold_rate.p == pytest.approx(0.99, abs=1e-12), fc.sim_hold_rate.p


def test_dt_composes_multiplicatively():
    """Three stacked -25% Normal-DT rows on one (side, troop): legacy keeps
    additive-sum-then-gamma; both multiplicative modes compose DT as
    prod(1+x_i) with no gamma (dt_multiplicative and multiplicative must
    agree -- DT is the one channel they treat identically)."""
    mods = _Mods()
    for _ in range(3):
        mods.add_dt("attacker", TroopType.INFANTRY, -0.25, category=DamageCategory.NORMAL)

    legacy = _stack_view(_stack(), "attacker", mods, mod_gamma=0.30,
                         modifier_stacking="legacy")
    dt_mult = _stack_view(_stack(), "attacker", mods, mod_gamma=0.30,
                          modifier_stacking="dt_multiplicative")
    both_mult = _stack_view(_stack(), "attacker", mods, mod_gamma=0.30,
                            modifier_stacking="multiplicative")

    assert legacy.dt == pytest.approx((1.0 - 0.75) ** 0.30 - 1.0)
    assert dt_mult.dt == pytest.approx(0.75 ** 3 - 1.0)
    assert both_mult.dt == pytest.approx(0.75 ** 3 - 1.0)


def test_dd_follows_mode():
    """Two stacked +20% Normal-DD rows: legacy AND dt_multiplicative agree
    (DD stays legacy-form in dt_multiplicative mode -- only DT changes there);
    only full "multiplicative" composes DD as prod(1+x_i) too."""
    mods = _Mods()
    for _ in range(2):
        mods.add_dd("attacker", TroopType.INFANTRY, 0.20, category=DamageCategory.NORMAL)

    legacy = _stack_view(_stack(), "attacker", mods, mod_gamma=0.30,
                         modifier_stacking="legacy")
    dt_mult = _stack_view(_stack(), "attacker", mods, mod_gamma=0.30,
                          modifier_stacking="dt_multiplicative")
    both_mult = _stack_view(_stack(), "attacker", mods, mod_gamma=0.30,
                            modifier_stacking="multiplicative")

    assert legacy.dd == pytest.approx(1.4 ** 0.30 - 1.0)
    assert dt_mult.dd == pytest.approx(1.4 ** 0.30 - 1.0)
    assert both_mult.dd == pytest.approx(1.2 ** 2 - 1.0)


def test_mode_reaches_engine_through_api():
    """modifier_stacking must flow api.predict -> eng_params -> kernel.run_batch
    -> run_batch_construct -> simulate_turns's BEST_PARAMS+TURN_PARAMS+params
    layering and actually change the simulated outcome.

    Trigger scenario (EXPERIMENT_DT_STACKING.md): own = garrison, joiners
    3x Wu Ming + Gatot.

    NOTE ON DIRECTION (a real finding, not a test bug): the experiment's
    general result is that multiplicative composition credits MORE stacked-DT
    toughness than legacy's gamma-compressed sum (measured M_3 2.370 vs
    engine-today 1.516). Naively that predicts multiplicative's hold rate
    here should be >= legacy's. It is the OPPOSITE (verified by hand-tracing
    _passive_mods + _stack_view + pvp_engine.base_strike_damage): this
    battle's defender Infantry receives FOUR independent -25% Normal-DT
    passive rows (Estrella capt. skill_3 + 3x Wu Ming joiner skill_1). Their
    ADDITIVE sum is EXACTLY -1.00, which saturates _stack_view's floor to
    dt <= -1.0, and base_strike_damage applies `max(0.0, 1.0 + tgt.dt)` --
    i.e. legacy grants this front-line tank LITERAL ZERO incoming Normal
    damage (total immunity), not merely "a lot of reduction". prod(1+x_i) of
    four 0.75 factors = 0.3164 can get very tough (dt = -0.684, ~3.16x) but
    can never land on exactly -1.0 for any finite stack, so under either
    multiplicative mode the Infantry takes a small-but-real trickle of damage
    every turn and this particular (large, sustained) attacker eventually
    grinds through it. Legacy's 99%-hold-at-n=100 here is therefore a floor-
    saturation ARTIFACT of this exact battle having exactly four quarter-
    reductions stacked on one troop class, not a real toughness advantage --
    see the deliverable for the full verbatim numbers and the decision this
    raises. Asserting a specific direction here would just re-encode that one
    coincidence as a law, so this test instead checks the thing its name
    promises: the parameter reaches the engine and measurably changes the
    result.
    """
    own, enemy = _own_enemy(_GEN15_RALLY_WM)
    assert own.joiners == ["Wu Ming", "Wu Ming", "Wu Ming", "Gatot"]

    results = {}
    for mode in ("legacy", "dt_multiplicative", "multiplicative"):
        results[mode] = api.predict(own, enemy, n=100, seed=4471,
                                    params={"engine": "turn", "modifier_stacking": mode})

    msg = " | ".join(
        f"{mode}: hold={fc.sim_hold_rate.p:.3f} p_win={fc.p_win.p:.3f}"
        for mode, fc in results.items()
    )
    print(msg)
    assert results["legacy"].sim_hold_rate.p != results["multiplicative"].sim_hold_rate.p, msg
    assert results["legacy"].sim_hold_rate.p != results["dt_multiplicative"].sim_hold_rate.p, msg


def test_shipped_default_is_multiplicative():
    """Guard the shipped default (QA finding, 2026-09-16): TURN_PARAMS's
    "modifier_stacking" must stay "multiplicative" per Martin's 2026-09-16
    owner decision -- DT is MEASURED multiplicative and DD is adopted by
    symmetry (see wos_sim/formula_research/EXPERIMENT_DT_STACKING.md s.8 for
    the six-battle measurement this locks in). Nothing else in this suite
    would catch a silent regression of the default back to "legacy" or the
    2026-09-11 interim "dt_multiplicative"."""
    from wos_sim.pvp_turn_engine import TURN_PARAMS
    assert TURN_PARAMS["modifier_stacking"] == "multiplicative", (
        "TURN_PARAMS['modifier_stacking'] regressed from the 2026-09-16 owner "
        "decision (Martin): it must stay 'multiplicative' "
        "(EXPERIMENT_DT_STACKING.md s.8), not "
        f"{TURN_PARAMS['modifier_stacking']!r}"
    )


def test_default_does_not_reproduce_the_immunity_cliff():
    """The shipped DEFAULT (no explicit modifier_stacking key) must not
    reproduce legacy's immunity-cliff artifact on Gen15_Rally_WM.

    Under "legacy", the garrison Infantry carry Estrella S3 + 3x Wu Ming S1 =
    exactly -100% additive Normal DT; the sum floors at -1.0 and
    base_strike_damage's max(0.0, 1.0 + tgt.dt) zeroes ALL incoming Normal
    damage -- literal immunity, which held 99/100 runs (n=100, seed=4471,
    measured 2026-09-11; see test_legacy_is_byte_identical's frozen
    signature). prod(1+x_i) of four 0.75 factors (0.3164) gets very tough but
    can never land on exactly -1.0 for any finite stack, so the shipped
    multiplicative default must let a small-but-real trickle of damage
    through every turn and NOT reproduce the ~99% hold."""
    if not os.path.exists(_GEN15_RALLY_WM):
        pytest.skip(f"fixture not found: {_GEN15_RALLY_WM}")
    d = _load(_GEN15_RALLY_WM)
    own = profile_from_dict(d["own"])
    own.joiners = ["Wu Ming"] * 3 + ["Gatot"]
    enemy = profile_from_dict(d["enemy"])
    fc = api.predict(own, enemy, n=100, seed=4471,
                     params={"engine": "turn"})  # NO mode key: exercise the shipped default
    assert fc.sim_hold_rate.p < 0.5, (
        "the shipped default modifier_stacking must not reproduce legacy's "
        "additive -100% DT floor (measured 0.99 hold, an immunity-cliff "
        f"artifact); got sim_hold_rate.p={fc.sim_hold_rate.p}"
    )


def test_invalid_modifier_stacking_raises():
    """A typo'd/unrecognized modifier_stacking string (e.g. the classic
    "multiplicitive" misspelling) must fail loudly with ValueError instead of
    silently falling through to legacy's additive branches in _stack_view."""
    own, enemy = _own_enemy(_GEN15_50_10_40)
    with pytest.raises(ValueError):
        api.predict(own, enemy, n=5, seed=4471,
                   params={"engine": "turn", "modifier_stacking": "multiplicitive"})
