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
DAMP = 0.10        # near-even tempering: p_turn 1.0/0.0 -> ~55%/45% (reads ~50%,
                   # keeps the winner direction defined for the back-test)
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


def hybrid_win_prob(con, p_turn_own: float, blind_near_even: bool = False) -> tuple[float, bool]:
    """Return (displayed_p_win_own, near_even). See module docstring for the rule.

    p_turn_own is the turn engine's own-side win fraction (mutual counted the
    same way the summary does). `blind_near_even` is the troop-only strength
    probe's coin-flip flag: a battle it already called a coin flip must not be
    UPGRADED to a confident (silent) call by the effective-strength gap - the
    structural garrison upsets (a weak attacker beating a strong defender) have a
    decisive effective ratio but the sim gets them wrong, so they stay coin flips
    rather than becoming confident-wrong silent misses."""
    ratio = effective_ratio(con)
    r_own = ratio if con.own_is_attacker else (1.0 / ratio if ratio > 0 else 1.0)
    decisive = abs(math.log(ratio)) > math.log(1.0 + BAND) if ratio > 0 else False

    p_att_sig = _sigmoid_att(ratio)
    p_sig_own = p_att_sig if con.own_is_attacker else (1.0 - p_att_sig)

    turn_owner_own = p_turn_own >= 0.5
    strength_owner_own = r_own >= 1.0

    if decisive and (turn_owner_own != strength_owner_own):
        # joiner/strength decisively contradicts the sim's winner -> trust strength
        # (this is the joiner-gap fix: 0-vs-4 joiners -> ~10%).
        return p_sig_own, False
    if decisive and (turn_owner_own == strength_owner_own) and not blind_near_even:
        # genuinely decisive on BOTH measures -> leave the sim's confident call.
        return p_turn_own, False
    # near-even (on either measure): pull toward 50%, keep the winner direction
    # defined. Covers true coin flips AND blind-coin-flip upsets we must not
    # over-confidently mis-call.
    return 0.5 + (p_turn_own - 0.5) * DAMP, True
