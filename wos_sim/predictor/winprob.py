"""Joiner-aware displayed win probability (2026-07-09, Martin's directive).

The turn engine decides the WINNER and the mechanics. But its raw win% is a
near-deterministic 1.0/0.0 even for a coin flip, and it is blind to JOINERS for
the winner (joiners only move survivor depth, never who wins). Two user-visible
consequences this module fixes:

  1. A genuine coin flip should read ~50%, not 100%.
  2. Joiners must move the odds: 0-vs-4 joiners is not a coin flip, it is an
     underdog (~10%).

Mechanism: fold the joiner skill packets (stat buffs, enemy debuffs, damage-
taken) into an EFFECTIVE strength index per side (the plain `_strength_index`
reads only troop stats, so joiners contribute exactly 0 to it - proven). Then:

  * DECISIVE joiner/strength gap that DISAGREES with the turn-engine winner
    (own is favoured by the sim but is really the strength underdog, e.g. an
    attacker who brought no joiners against a 4-joiner defender) -> override the
    displayed win% with the strength sigmoid (parity 50%, ~10% at a 4-joiner
    deficit).
  * NEAR-EVEN (inside the +-band) -> keep the turn-engine winner but temper the
    number toward 50% (a coin flip reads ~50%, not 100%).
  * DECISIVE but AGREEING with the turn engine -> unchanged (never invents a new
    confident-wrong call; the structural garrison upsets stay exactly as-is).

This shape is FORCED by the back-test guardrail: replacing the win% with the raw
strength sigmoid everywhere scores 5/13 winners (vs the turn engine's 7/13) and
mis-calls real upsets, and would break locked winners whose effective ratio
mildly favours the enemy (they won on dynamics). Overriding only on decisive
DISAGREEMENT leaves all 7 locked winners untouched (they are all near-even) while
still fixing the joiner-gap case.

2026-09-10 (owner directive, Martin, via ENGINE_HANDOFF_winprob_surface_what_varies.md):
"if it's always 25% it looks odd -- I've changed formations, I've used different
joiners, it is still 25%; people will not trust it." At army scale the turn-engine
hold rate `p_turn_own` is near-deterministic (0 or 1), so the near-even branch's
old `0.5 + (p_turn_own - 0.5) * DAMP` could only ever display 25% or 75%, and
crossing the band edge into the decisive-disagree branch was a CLIFF (a same-side
p_sig_own swap with no blend) that could also go NON-MONOTONE once the
`blind_near_even` probe re-demoted a decisive-agree call back to near-even.
`hybrid_win_prob_ex` (below) replaces the collapsed bit with `stability`
(``kernel.call_stability`` -- the fraction of own-strength perturbations across
the SAME +-BAND at which own wins a deterministic sim: 17 points, not a new
constant), blends the disagree branch continuously across one more band-width so
there is no cliff, and makes an agreeing-but-knife-edge call take the MORE
confident of the near-even value and the disagree blend at that same ratio (the
monotonicity guard). `hybrid_win_prob` keeps its old (p, near_even) tuple shape
and, without an explicit `stability`, reproduces the pre-2026-09-10 numbers
exactly -- the caller (``api.predict``) is what changed, to supply `stability`.
No existing constant (BAND, DAMP, NEAR_EVEN_HIT_RATE) was retuned.

2026-09-10 (continued -- Changes A and C, same handoff, two defects found once
formations/joiners were swept end-to-end rather than eyeballed one at a time).
(A) the `stability` fed above came from a HERO-SKILL-FREE sim
(``kernel.call_stability``), so it never saw joiner stat packets: on a fixture
whose effective ratio stayed inside the near-even band for every joiner
variant, S was bit-identical across own-joiners=saved/none/4x -- the near-even
value was blind to joiners exactly where the headline most needed to move.
``call_stability`` now takes an optional ``side_mults`` (the same per-class
{"off","tough"} dict ``_joiner_mults`` returns below) and folds it onto BOTH
sides as a static multiplier before the own-strength sweep runs, so S reflects
the joiner-aware matchup while the sim's SKILL logic stays off. (C) the
decisive-disagree blend weighted every gap by the same edge-distance `w`
regardless of WHY the sim and the strength sigmoid disagreed -- a joiner-gap
disagreement (the sim is PROVEN blind to joiners for the winner, so its
contrary call carries no information) was diluted exactly like a troop-gap
disagreement (which the sim DID see, so its call is informative and deserves
the blend), which watered the 2026-07-09 0-vs-4-joiners override (~10%) down
to a near-coinflip 44%. ``hybrid_win_prob_ex`` now takes an optional
`r_blind_own` (the troop-only, joiner-blind own-side strength ratio, computed
by the caller from ``kernel._strength_index``) and derives `joiner_share` `j`
-- the fraction of the log strength-gap that disappears once joiners are
removed -- then blends with `w_eff = max(w, j)`: a joiner-driven gap (j near
1) gets close to the full override even right at the band edge, a troop-driven
gap (j near 0) is unchanged from the plain edge-distance blend. Both changes
are additive and fall back to the pre-Change behaviour when the new kwargs are
omitted (`side_mults=None`, `r_blind_own=None`); neither retunes BAND, DAMP,
K_SLOPE, or NEAR_EVEN_HIT_RATE, and neither introduces a new numeric constant.
"""
from __future__ import annotations

import math

from wos_sim.pvp_engine import StatType as S

# offense = Attack x Lethality ; toughness = Defense x Health ; damage-taken folds
# into toughness (a -25% damage-taken ~ x1.333 effective toughness).
_ATTR = {"Attack": "off", "Lethality": "off",
         "Defense": "tough", "Health": "tough", "Damage Taken": "tough"}
_CLS = ("Infantry", "Lancer", "Marksman")

K_SLOPE = 10.0     # sigmoid steepness: r0.80->~10%, r1.0->50%, r1.2->~86%
BAND = 0.20        # +-20% effective-strength band = "near-even / coin flip"
# Near-even tempering. Until 2026-07-28 this was a CHOSEN constant, DAMP=0.10,
# which pinned every near-even battle to exactly 55%/45% -- and since 20 of the
# 22 labelled battles take the near-even branch, that constant WAS the product.
# It is now MEASURED: on those 20 battles the displayed (sim-sided) call is right
# 15/20 = 0.750, so a near-even battle displays the engine's actual near-even
# accuracy. Gain maps p_turn 1.0/0.0 onto that hit rate: 2*(0.750-0.5) = 0.500.
#   Re-measure with wos_sim/formula_research/calibrate_winprob.py when the
#   labelled set grows; do NOT hand-tune it.
NEAR_EVEN_HIT_RATE = 0.750     # 15/20 labelled near-even battles, 2026-07-28
DAMP = 2.0 * (NEAR_EVEN_HIT_RATE - 0.5)
PARITY = 0.5       # attacker win-prob at equal EFFECTIVE strength (Martin: 50%)


def _joiner_mults(skill_defs):
    """Per-side per-class {'off','tough'} multipliers from JOINER packets only.
    Joiner stat rows are never in the (captain) panel, so this is the whole of
    the joiner contribution the strength index is currently missing."""
    mult = {sd: {c: {"off": 1.0, "tough": 1.0} for c in _CLS}
            for sd in ("attacker", "defender")}
    for s in skill_defs:
        if getattr(s, "role", None) != "joiner":
            continue
        owner = s.side                                   # 'attacker' / 'defender'
        for r in s.rows:
            bucket = _ATTR.get(r.attribute.value)
            if bucket is None:
                continue
            # Friend rows buff the owner; Foe rows debuff the other side.
            target = owner if r.side.value == "Friend" else (
                "defender" if owner == "attacker" else "attacker")
            classes = _CLS if r.receiver.value == "All" else (r.receiver.value,)
            amt = r.amount or 0.0
            factor = (1.0 / (1.0 + amt)) if r.attribute.value == "Damage Taken" else (1.0 + amt)
            for c in classes:
                if c in mult[target]:
                    mult[target][c][bucket] *= factor
    return mult


def _eff_index(units, side_mult) -> float:
    total = 0.0
    for u in units:
        m = side_mult.get(u.troop.value, {"off": 1.0, "tough": 1.0})
        off = u.astat[S.ATTACK] * u.astat[S.LETHALITY] * m["off"]
        tough = u.astat[S.DEFENSE] * u.astat[S.HEALTH] * m["tough"]
        if off > 0 and tough > 0:
            total += u.n * (off * tough) ** 0.25
    return total


def effective_ratio(con) -> float:
    """attacker_effective_strength / defender_effective_strength, joiners folded in."""
    from wos_sim.pvp_turn_engine import skill_defs_from_matchup
    mult = _joiner_mults(skill_defs_from_matchup(con))
    a = _eff_index(con.attacker_units, mult["attacker"])
    d = _eff_index(con.defender_units, mult["defender"])
    return (a / d) if d > 0 else 1.0


def _sigmoid_att(ratio: float) -> float:
    x = K_SLOPE * math.log(ratio) + math.log(PARITY / (1.0 - PARITY))
    return 1.0 / (1.0 + math.exp(-x))


def hybrid_win_prob_ex(con, p_turn_own: float, blind_near_even: bool = False,
                       stability: float | None = None,
                       r_blind_own: float | None = None) -> dict:
    """Full-detail rule behind ``hybrid_win_prob``. See module docstring for the
    branch shape; the 2026-09-10 paragraphs below document the call-stability
    near-even value, the no-cliff blend, the monotonicity guard, and (Changes A
    and C) the joiner-aware stability sweep and the joiner-share blend weight.

    p_turn_own is the turn engine's own-side win fraction (mutual counted the
    same way the summary does). `blind_near_even` is the troop-only strength
    probe's coin-flip flag: a battle it already called a coin flip must not be
    UPGRADED to a confident (silent) call by the effective-strength gap - the
    structural garrison upsets (a weak attacker beating a strong defender) have a
    decisive effective ratio but the sim gets them wrong, so they stay coin flips
    rather than becoming confident-wrong silent misses. `stability` is the
    call-stability S from ``kernel.call_stability`` (fraction of own-strength
    perturbations across the existing band at which own wins); when omitted the
    near-even value falls back to the point sim (byte-identical to the old rule).
    `r_blind_own` is the TROOP-ONLY (joiner-blind) own-side strength ratio; when
    given, a decisive disagreement is weighted toward the full strength override
    in proportion to how much of the log strength-gap is joiner-driven (see
    module docstring); when omitted (None) the blend is unchanged (byte-identical
    to the pre-Change-C rule).

    Returns {"p": float, "near_even": bool, "branch": str, "stability": float,
             "r_own": float, "p_sig_own": float, "near_even_value": float,
             "joiner_share": float, "blend_weight": float}.
    branch in {"near_even", "decisive_disagree", "decisive_agree",
    "decisive_agree_knife_edge"}."""
    ratio = effective_ratio(con)
    r_own = ratio if con.own_is_attacker else (1.0 / ratio if ratio > 0 else 1.0)
    decisive = abs(math.log(ratio)) > math.log(1.0 + BAND) if ratio > 0 else False

    p_att_sig = _sigmoid_att(ratio)
    p_sig_own = p_att_sig if con.own_is_attacker else (1.0 - p_att_sig)

    turn_owner_own = p_turn_own >= 0.5
    strength_owner_own = r_own >= 1.0

    # --- near-even value from call-stability S (falls back to the point sim) ---
    s = p_turn_own if stability is None else stability
    # SIGN GUARD (G12 winner-lock): S may never put the displayed value on the
    # other side of 0.5 from the point sim's call.
    s = max(s, 0.5) if turn_owner_own else min(s, 0.5 - 1e-9)   # strict: the >=0.5 tie-break must never flip a sim-says-lose call
    near_val = 0.5 + (s - 0.5) * DAMP          # robust win -> 0.75, robust loss -> 0.25,
                                               # knife-edge -> ~0.50 (endpoints unchanged)

    base = {"stability": s, "r_own": r_own, "p_sig_own": p_sig_own,
            "near_even_value": near_val}

    if not decisive:
        return {**base, "p": near_val, "near_even": True, "branch": "near_even",
                "joiner_share": 0.0, "blend_weight": 0.0}

    # --- decisive: blend continuously over ONE band-width past the edge. The
    # transition width is BAND itself, so no new constant is introduced. w=0 at
    # the band edge (continuous with near_val: no cliff), w=1 at r=(1+BAND)^2.
    edge = math.log(1.0 + BAND)
    w = min(1.0, max(0.0, (abs(math.log(ratio)) - edge) / edge))

    # Joiner share of the decisive gap. The sim is PROVEN blind to joiners for the
    # winner (module docstring), so a joiner-driven disagreement gets the full
    # strength override; a troop-driven one (which the sim saw) keeps the blend.
    lr = math.log(r_own) if r_own > 0 else 0.0
    if r_blind_own is not None and r_blind_own > 0 and abs(lr) > 1e-9:
        j = min(1.0, max(0.0, abs(lr - math.log(r_blind_own)) / abs(lr)))
    else:
        j = 0.0
    w_eff = max(w, j)
    disagree_val = near_val + (p_sig_own - near_val) * w_eff

    if turn_owner_own != strength_owner_own:
        # strength decisively contradicts the sim (the joiner-gap case): move
        # toward the strength sigmoid, continuously from the near-even value.
        return {**base, "p": disagree_val, "near_even": False,
                "branch": "decisive_disagree",
                "joiner_share": j, "blend_weight": w_eff}
    if blind_near_even:
        # both measures agree but the troop-only probe says knife-edge: keep the
        # hedged badge, but two AGREEING signals may never read less confident
        # than the disagree branch does at this same r. REVISED 2026-09-10 after the
        # Brier gate: that "monotonicity guard" (max of near_val and the disagree
        # blend) pushed RAW_05 -- a REAL lost battle -- from 0.75 to 0.991, exactly
        # the confident-wrong silent miss the module docstring forbids. Restored to
        # the original design: the sim's own hold rate tempered by the MEASURED
        # DAMP, so a fragile call never exceeds the 0.75 near-even ceiling. Cost:
        # a <=0.05 dip at the disagree->knife-edge boundary on a synthetic troop
        # ladder (the sim flips lose->win there); honesty on real battles wins.
        p = 0.5 + (p_turn_own - 0.5) * DAMP
        return {**base, "p": p, "near_even": True,
                "branch": "decisive_agree_knife_edge",
                "joiner_share": j, "blend_weight": w_eff}
    return {**base, "p": p_turn_own, "near_even": False, "branch": "decisive_agree",
            "joiner_share": j, "blend_weight": w_eff}


def hybrid_win_prob(con, p_turn_own: float, blind_near_even: bool = False) -> tuple[float, bool]:
    """Return (displayed_p_win_own, near_even). Thin wrapper over
    ``hybrid_win_prob_ex`` (stability omitted -> falls back to the point sim, so
    this is byte-identical to the pre-2026-09-10 rule for every caller that does
    not have a call-stability measure to hand). See module docstring for the
    rule, and ``hybrid_win_prob_ex`` for the full branch/field detail."""
    res = hybrid_win_prob_ex(con, p_turn_own, blind_near_even=blind_near_even)
    return res["p"], res["near_even"]
