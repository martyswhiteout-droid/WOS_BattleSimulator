"""Stage 8.1 army router -- routes ARMY-SCALE SAME-CLASS battles to the derived
attrition backbone (`formula_research/stage8_army.py`) instead of the legacy
`def_k`-fudged turn engine.

Sits beside `type1_router` in `api.predict()`: the Type-1 router owns the
single-TROOP lab domain, this one owns the LARGE same-class domain. Everything
else still falls through to the turn engine unchanged.

WHY THIS EXISTS
  The turn engine reaches these battles only through `def_k=0.45`, a defender
  fire-rate handicap with no physical basis; on the real 20,000-v-20,000 mirror it
  produces a mirror sweep, and the small-N composition algorithm produces a
  turn-capped "defeat" with survivor fractions that DRIFT with troop count. The
  measured data says outcomes are exactly scale-invariant and are set by the stat
  ratio alone. The backbone reproduces that with ZERO fitted constants.

DOMAIN (deliberately narrow -- see STAGE8_1_FINDINGS.md)
  * BOTH sides deploy exactly ONE class, at the SAME tier and SAME FC.
    - SAME class: any tier <= 6 (base stats cancel in beta/alpha).
    - CROSS class (2026-07-28): only at TIER 6 and only for a pair whose ratio R is
      MEASURED (stage8_army.R_TABLE; each entry carries two independent battles at
      different stat gaps). Off-tier or unmeasured pairs fall through -- the lab
      K-table does not transfer to army scale and R's tier dependence is unmeasured.
    - Near parity the router ABSTAINS: if beta/alpha sits inside the measured R
      spread of 1.0 the evidence cannot name a winner (the exp5 lesson -- 0.24% from
      parity turned a 2.5% R error into a 149% survivor error).
  * Proc-free: tier <= 6 and fc < 3 (Ambusher/Volley unlock at T7, Crystal* at FC3+).
  * No heroes, no joiners, no buffs/debuffs.
  * Both sides >= ARMY_MIN_TROOPS -- below that the small-N composition regime
    applies and the Type-1 router/turn engine keep it.

HONEST ACCURACY (why model_error is 10%, not 3%)
  Validated on three army anchors: the alliance-free 20k and 2k encampment mirrors
  fit to -0.44%/-0.50%, but the ALLIANCE-GARRISON mirror (exp7) is +8.93% -- a
  residual that is NOT discretisation, NOT a hidden panel buff, NOT tier and NOT
  the deployed class (all four ruled out, STAGE8_1_FINDINGS.md Addendum 3/4). Since
  the app's battles ARE garrison battles, that is the anchor that governs, so the
  band is 10% and the confidence is "directional", never "validated".
"""
from __future__ import annotations

from wos_sim.models import TroopType

from . import construct
from .kernel import RunRecord
from .profiles import CLASSES, STATS, ClassQuality, Matchup, SideProfile
from .summary import summarize
_TROOP_ENUM = {"Infantry": TroopType.INFANTRY, "Lancer": TroopType.LANCER,
               "Marksman": TroopType.MARKSMAN}

#: Below this the small-N composition regime applies (measured on 1-6-unit
#: ladders); at/above it the pooled attrition backbone is the validated model.
#: The lowest validated army anchor is 2,000/side; 1,000 keeps a safety margin
#: while staying far above the lab ladders.
ARMY_MIN_TROOPS = 1000

#: The garrison anchor's residual (+8.93%) governs -- see the module docstring.
ARMY_MODEL_ERROR = 0.10

#: A battle this close to mutual annihilation is reported as a coin flip rather
#: than a confident call (the winner fraction is sqrt(1 - beta/alpha), so a small
#: fraction means a knife-edge stat ratio).
COIN_FLIP_FRACTION = 0.10


def _deployed(side: SideProfile) -> list:
    counts = construct.class_counts(side)
    return [c for c in CLASSES if counts.get(c, 0) > 0]


def army_classifiable(matchup: Matchup):
    """(bool, reason) -- see the module docstring for the domain."""
    sides = (("own", matchup.own), ("enemy", matchup.enemy))
    seen = []
    for who, side in sides:
        deployed = _deployed(side)
        if len(deployed) != 1:
            return False, (f"multi_class: {who} deploys {len(deployed)} classes "
                           f"(army backbone covers same-class only)")
        cls = deployed[0]
        q = side.quality.get(cls) or ClassQuality()
        if not float(q.tier).is_integer() or q.tier > 6 or q.fc >= 3:
            return False, (f"tier/fc: {who} {cls} tier={q.tier} fc={q.fc} outside the "
                           f"proc-free army domain (whole tier <= 6, fc < 3)")
        n = construct.class_counts(side)[cls]
        if n < ARMY_MIN_TROOPS:
            return False, (f"below_army_scale: {who} deploys {n} < {ARMY_MIN_TROOPS} "
                           f"(small-N composition regime)")
        if any((side.lead_heroes or {}).values()):
            return False, f"heroes: {who} brings lead heroes (army backbone is hero-free)"
        if side.joiners:
            return False, f"joiners: {who} has {len(side.joiners)} joiner(s)"
        if side.own_buffs or side.debuffs_on_enemy:
            return False, f"buffs: {who} carries buffs/debuffs"
        seen.append((cls, int(q.tier), int(q.fc), n))
    (c0, t0, f0, _n0), (c1, t1, f1, _n1) = seen
    if c0 != c1:
        # CROSS-CLASS (2026-07-28): allowed only where the class-pair ratio R is
        # MEASURED -- tier 6, and a pair that appears in stage8_army.R_TABLE (each
        # entry carries two independent battles). Everything else still falls
        # through: the lab K-table does not transfer to army scale, and tier
        # dependence of R is unmeasured.
        from wos_sim.formula_research.stage8_army import class_pair_R, R_MEASURED_TIER
        if t0 != R_MEASURED_TIER or t1 != R_MEASURED_TIER:
            return False, (f"cross_class_tier: {c0} vs {c1} at T{t0}/T{t1} -- the "
                           f"class-pair ratio R is measured only at tier "
                           f"{R_MEASURED_TIER}")
        if class_pair_R(c0, c1)[0] is None:
            return False, (f"cross_class_unmeasured: no measured R for {c0}->{c1}")
    if t0 != t1:
        return False, (f"cross_tier: own T{t0} vs enemy T{t1} -- base stats only cancel "
                       f"at equal tier")
    if f0 != f1:
        # QA P1 #2: the base-stat table used here varies with FC below T10, so
        # unequal FC breaks the "base stats cancel" precondition that the whole
        # same-class derivation rests on -- an FC1-v-FC2 T1 pair (physically
        # identical to the production catalog, which ignores FC at T1-T9)
        # REVERSED the winner. Require identical base provenance.
        return False, (f"cross_fc: own FC{f0} vs enemy FC{f1} -- base stats only "
                       f"cancel at equal FC (and the FC-dependence below T10 is "
                       f"itself a research-table artefact)")
    return True, "army same-class"


def _eff(side: SideProfile, cls: str, tier: int) -> dict:
    """Effective stats = real base x (1 + panel). Panel fractions are x100 in the
    profile schema (profiles.py: "1096% -> 10.96")."""
    from wos_sim.formula_research.stage8_army import eff as _eff_law
    from wos_sim.formula_research.stage4_common import base_stats
    # No silent coercion (QA P1 #2 / P2 #5): FC is used exactly as declared. The
    # classifier already requires BOTH sides to share it, so whatever this table's
    # FC-dependence is below T10, it is identical on both sides and cancels.
    fc = int((side.quality.get(cls) or ClassQuality()).fc)
    a, d, l, h = base_stats(cls, tier, fc)
    panel_pct = {s: side.panel.get((cls, s), 0.0) * 100.0 for s in STATS}
    return _eff_law(panel_pct, {"A": a, "D": d, "L": l, "H": h})


def try_army(matchup: Matchup):
    """(Forecast|None, note_suffix). Never raises: any failure falls back to the
    caller's existing path, so a bug here can only ever restore pre-8.1 behavior."""
    try:
        from wos_sim.formula_research.stage8_army import predict_army_cross_class

        own_cls = _deployed(matchup.own)[0]
        enemy_cls = _deployed(matchup.enemy)[0]
        tier = int((matchup.own.quality.get(own_cls) or ClassQuality()).tier)
        own_n = construct.class_counts(matchup.own)[own_cls]
        enemy_n = construct.class_counts(matchup.enemy)[enemy_cls]
        own_eff = _eff(matchup.own, own_cls, tier)
        enemy_eff = _eff(matchup.enemy, enemy_cls, tier)

        if matchup.own_is_attacker:
            att_eff, def_eff, att_n, def_n = own_eff, enemy_eff, own_n, enemy_n
            att_cls, def_cls = own_cls, enemy_cls
        else:
            att_eff, def_eff, att_n, def_n = enemy_eff, own_eff, enemy_n, own_n
            att_cls, def_cls = enemy_cls, own_cls

        # CONTINUUM, not discrete (QA 2026-07-25, P2 x2). The discrete mode needs an
        # absolute rate `c = 1/(K*G_w*G_l)` whose transfer from the 1-6-unit lab to
        # army scale is UNMEASURED, and it makes the result depend on the research
        # base table's sub-T10 FC dependence -- which the production catalog says
        # does not exist (troop_catalog: FC is ignored at T1-T9). Equal-FC pairs
        # still moved: Lancer T1 23.28% @FC1 vs 23.06% @FC2, and the turn counts
        # moved much more. The continuum result depends ONLY on beta/alpha, where
        # the base product cancels exactly -- so it is the honest estimator until an
        # army-scale clock is measured. Consequence: no turn count is reported.
        res = predict_army_cross_class(
            att_eff, def_eff, att_cls=att_cls, def_cls=def_cls,
            n_att=att_n, n_def=def_n, tier=tier)

        winner = res["winner"]
        frac = res.get("winner_fraction", 0.0)
        if winner == "uncertain":
            # No winner may be inferred. Two causes, both principled: the solver hit
            # its numerical limit with both sides alive (QA P1 #1 / GAME_RULES s.424),
            # or beta/alpha sits inside the MEASURED R uncertainty so the evidence
            # cannot distinguish the outcomes (the exp5 near-parity lesson).
            return None, f"(army law abstained: {res.get('reason', 'unresolved')})"
        if winner == "mutual" or frac < COIN_FLIP_FRACTION:
            coin_flip, winner = True, (winner if winner != "mutual" else "attacker")
        else:
            coin_flip = False

        att_surv = res["survivors"] if winner == "attacker" else 0.0
        def_surv = res["survivors"] if winner == "defender" else 0.0
        record = RunRecord(
            # continuum mode reports no clock (QA P2: the army turn-count is unvalidated);
            # 0 is the schema's "no timeline" value, not a claim of a 0-turn battle.
            winner=("A" if winner == "attacker" else "D"), turns=0,
            attacker_start={_TROOP_ENUM[att_cls]: att_n},
            defender_start={_TROOP_ENUM[def_cls]: def_n},
            attacker_incap={_TROOP_ENUM[att_cls]: max(0.0, att_n - att_surv)},
            defender_incap={_TROOP_ENUM[def_cls]: max(0.0, def_n - def_surv)})

        note = (f"EXPERIMENTAL army-scale attrition law (stage8.1, opt-in): same-class "
                f"pooled race, {winner} keeps {frac:.1%}. Derived from only TWO measured "
                f"configurations (one misses by 8.9%), so treat both the winner and the "
                f"magnitude as provisional; no turn count is claimed (the army clock is "
                f"unmeasured).")
        if coin_flip:
            note = ("Army-scale attrition law (stage8.1): the two sides are within a "
                    "knife-edge stat ratio -- near-mutual annihilation, called a coin flip.")
            return summarize([record], own_is_attacker=matchup.own_is_attacker,
                             engine_model_error=ARMY_MODEL_ERROR, engine_path="army_law",
                             engine_note=note, stochastic=False, calibrated=False,
                             near_even=True, confidence="coin_flip",
                             win_prob_override=0.5), ""
        return summarize([record], own_is_attacker=matchup.own_is_attacker,
                         engine_model_error=ARMY_MODEL_ERROR, engine_path="army_law",
                         engine_note=note, stochastic=False, calibrated=False,
                         near_even=False, confidence="directional"), ""
    except Exception as e:                                       # noqa: BLE001
        return None, f"(army law abstained: exception:{type(e).__name__})"
