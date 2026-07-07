"""Two-sided PvP engine (Phase 3) - symmetric generalization of the
round-4 asymmetric-width mechanism (wos_sim/farm_engine.py).

Key transfer: the round-4 OWN-OUTPUT term (per-class k, self-durability
throttle, pinned-front, armor penetration, counters - all LINEAR in the
firing side's count) is a property of the attacking troops, not of the
opponent type. So each side deals damage to the other with the SAME
formula. The beast-specific INCOMING terms (kb, ed frontage, beast-
pressure) drop out - in PvP both sides are spread armies firing at each
other, no compact-target asymmetry. => reuses farm_engine.BEST_PARAMS,
NO new per-unit params. DD/DT hero modifiers layer on multiplicatively.

Per turn (simultaneous, turn-start snapshot):
  side X damage to side Y front (absorption Inf->Lan->Mar; overflow
  cascades) from each X stack s:
    dmg = kc[cls]*n_s*(A_s*L_s)/(Yfront.D^qd * Yfront.H^qh)
          / power(tier_s)^so * pin(if s is X-front) * counter
          * pen(base_A_s / (base_A_s + pc*Yfront.D))
          * (1 + DD_s) * (1 + DT_Yfront)
  Ambusher: X T7+ lancers route 20% of output past the front to Y marks.
Ends at first wipe (mutual wipe possible). One free scale knob (`rate`)
for PvP-vs-beast calibration on the r6/r8 sister pair.
"""

from dataclasses import dataclass, field, replace

from .farm_engine import BEST_PARAMS
from .mechanics import LANCER_BYPASS_CHANCE, AMBUSHER_MIN_TIER
from .models import StatType, TroopType
from .t12 import side_mods as t12_mods
from .troop_catalog import (interpolated_tier_power, troop_base_stats)

A, D, L, H = StatType.ATTACK, StatType.DEFENSE, StatType.LETHALITY, StatType.HEALTH
ORDER = [TroopType.INFANTRY, TroopType.LANCER, TroopType.MARKSMAN]
COUNTERS = {TroopType.INFANTRY: TroopType.LANCER,
            TroopType.LANCER: TroopType.MARKSMAN,
            TroopType.MARKSMAN: TroopType.INFANTRY}
_KC = {TroopType.INFANTRY: "ki", TroopType.LANCER: "kl", TroopType.MARKSMAN: "km"}


@dataclass
class Unit:
    troop: TroopType
    tier: int
    n: float
    astat: dict          # ABSOLUTE effective stats A/D/L/H
    base_atk: float      # base tier attack (for penetration, buff-independent)
    dd: float = 0.0      # damage-dealt bonus (own output)
    dt: float = 0.0      # damage-taken bonus (incoming amplification)
    incap: float = 0.0   # cumulative incapacitated


def units_from_side(side, board=None, tag=None):
    """SideState (ClassState.stats are (1+bonus) multipliers) -> Units with
    ABSOLUTE stats. board+tag optional for DD/DT pools."""
    out = []
    for troop, cs in side.classes.items():
        if cs.count <= 0:
            continue
        base = troop_base_stats(cs.tier, cs.fc_level, troop)
        astat = {s: base[s] * cs.stats.get(s, 1.0) for s in (A, D, L, H)}
        dd = cs.damage_dealt
        dt = cs.damage_taken
        out.append(Unit(troop, cs.tier, cs.count, astat, base[A], dd, dt))
    return out


def _front(units):
    for t in ORDER:
        for u in units:
            if u.troop == t and u.n > 1e-9:
                return u
    return None


def base_strike_damage(src, tgt_front, p, own_front=None, marks_dd=1.0):
    """Damage one source stack deals into the current enemy front stack.

    The unit is the same one used by the legacy engine: incapacitated troops
    before the global per-turn scale.  ``src``/``tgt_front`` only need the Unit
    fields used below, which lets the turn engine pass local stack views.
    """
    qd, qh, so, pc, cm = p["qd"], p["qh"], p["so"], p["pc"], p["cm"]
    dmg = (p[_KC[src.troop]] * src.n * (src.astat[A] * src.astat[L])
           / (tgt_front.astat[D] ** qd * tgt_front.astat[H] ** qh)
           / interpolated_tier_power(src.tier) ** so
           * max(0.0, 1.0 + src.dd) * max(0.0, 1.0 + tgt_front.dt))
    if src.troop == TroopType.MARKSMAN:
        dmg *= marks_dd
    if own_front is not None and src is own_front:
        dmg *= p["pin"]
    if pc > 0:
        dmg *= src.base_atk / (src.base_atk + pc * tgt_front.astat[D])
    if COUNTERS[src.troop] == tgt_front.troop:
        dmg *= cm
    return dmg


def _side_damage(attackers, defenders, p, frontage_exp=1.0, scale=1.0,
                 t12=(1.0, 1.0, 1.0), enemy_ab=0.0):
    # t12 = (atk_marks_dd, def_inf_dt, def_enemy_out) per-turn T12 multipliers
    """Damage the `attackers` side deals to `defenders` this turn (front +
    a separate marksman-bypass bucket). Returns (front_dmg, bypass_dmg).

    frontage_exp<1 makes this side's output SUBLINEAR in its own live count
    (frontage-limited return fire): total output scaled by
    N_firing^(frontage_exp-1). The garrison (defender), being piled-upon,
    fires this way (mirrors the beast's frontage-limited return term);
    the rally (attacker) fires LINEARLY (frontage_exp=1). This asymmetry
    is the structural Phase-3 fix - NOT a scalar atk_adv."""
    df = _front(defenders)
    if df is None:
        return 0.0, 0.0
    af = _front(attackers)
    front_dmg = 0.0
    bypass_dmg = 0.0
    atk_marks_dd, def_inf_dt, def_enemy_out = t12
    for s in attackers:
        if s.n <= 1e-9:
            continue
        dmg = base_strike_damage(s, df, p, own_front=af, marks_dd=atk_marks_dd)
        # Ambusher: T7+ lancers send a fraction straight to enemy marksmen
        if s.troop == TroopType.LANCER and s.tier >= AMBUSHER_MIN_TIER:
            bypass_dmg += dmg * LANCER_BYPASS_CHANCE
            dmg *= (1.0 - LANCER_BYPASS_CHANCE)
        front_dmg += dmg
    if df.troop == TroopType.INFANTRY:
        front_dmg *= def_inf_dt          # T12 Meridian: defender inf takes less
    front_dmg *= def_enemy_out           # T12 Indomitable Wall: cuts attacker output
    bypass_dmg *= def_enemy_out
    if frontage_exp != 1.0:
        n_fire = sum(s.n for s in attackers if s.n > 1e-9)
        if n_fire > 0:
            scale *= n_fire ** (frontage_exp - 1.0)
    # target-abundance (controlled-ladder E-11): this side's output also scales
    # with the ENEMY/receiver live count ^enemy_ab (ed-1=0.571 from the ladder).
    # default 0.0 = legacy/off (keeps the r6/r8 calibration untouched).
    if enemy_ab != 0.0:
        n_recv = sum(s.n for s in defenders if s.n > 1e-9)
        if n_recv > 0:
            scale *= n_recv ** enemy_ab
    return front_dmg * scale, bypass_dmg * scale


def _apply(units, dmg, target_troop=None):
    """Apply dmg with absorption; if target_troop given, hit that class first
    (marksman bypass) then cascade normally."""
    order = ORDER
    if target_troop is not None:
        order = [target_troop] + [t for t in ORDER if t != target_troop]
    remaining = dmg
    for t in order:
        if remaining <= 1e-12:
            break
        for u in units:
            if u.troop == t and u.n > 1e-9:
                take = min(remaining, u.n)
                u.n -= take
                u.incap += take
                remaining -= take
                if remaining <= 1e-12:
                    break


@dataclass
class PvpResult:
    winner: str            # 'A' | 'D' | 'mutual'
    turns: int
    a_incap: dict          # troop -> incapacitated
    d_incap: dict
    a_total0: float
    d_total0: float


def simulate_pvp(a_units, d_units, params=None, max_turns=4000):
    p = dict(BEST_PARAMS)
    p.setdefault("rate", 1.0)
    if params:
        p.update(params)
    # clone defensively - the sim mutates unit counts (callers reuse inputs)
    a_units = [replace(u, astat=dict(u.astat)) for u in a_units]
    d_units = [replace(u, astat=dict(u.astat)) for u in d_units]
    a0 = sum(u.n for u in a_units)
    d0 = sum(u.n for u in d_units)
    turns = 0
    while turns < max_turns:
        turns += 1
        # simultaneous: compute both sides' damage on the turn-start snapshot.
        # STRUCTURAL ASYMMETRY (Phase-3 fix, 2026-07-04): attacker fires
        # LINEARLY (piles onto the garrison); defender returns fire
        # FRONTAGE-LIMITED (~N_def^def_ed), mirroring the beast engine's
        # return term. def_ed<1 makes the garrison's output sublinear ->
        # fixes the symmetric-copy defender-win bias. def_k = defender
        # output coefficient (absorbs the frontage units), like the beast
        # kb. def_ed defaults to 1.0 (symmetric/legacy) unless set.
        def_ed = p.get("def_ed", 1.0)
        def_k = p.get("def_k", 1.0)
        rate = p["rate"]
        enemy_ab = p.get("enemy_ab", 0.0)   # E-11 target-abundance (both sides)
        # T12 per-turn mods (empty dict -> no-op tuple)
        a_md, a_idt, a_eo = t12_mods(p.get("a_t12"), turns)
        d_md, d_idt, d_eo = t12_mods(p.get("d_t12"), turns)
        a_front_dmg, a_bypass = _side_damage(
            a_units, d_units, p, frontage_exp=1.0, scale=rate,
            t12=(a_md, d_idt, d_eo), enemy_ab=enemy_ab)
        d_front_dmg, d_bypass = _side_damage(
            d_units, a_units, p, frontage_exp=def_ed, scale=rate * def_k,
            t12=(d_md, a_idt, a_eo), enemy_ab=enemy_ab)
        _apply(d_units, a_front_dmg)
        if a_bypass > 0:
            _apply(d_units, a_bypass, TroopType.MARKSMAN)
        _apply(a_units, d_front_dmg)
        if d_bypass > 0:
            _apply(a_units, d_bypass, TroopType.MARKSMAN)
        a_alive = _front(a_units) is not None
        d_alive = _front(d_units) is not None
        if not a_alive or not d_alive:
            winner = ("mutual" if (not a_alive and not d_alive)
                      else "D" if not a_alive else "A")
            break
    else:
        winner = "A" if sum(u.n for u in a_units) >= sum(u.n for u in d_units) else "D"
    return PvpResult(
        winner=winner, turns=turns,
        a_incap={u.troop: u.incap for u in a_units},
        d_incap={u.troop: u.incap for u in d_units},
        a_total0=a0, d_total0=d0)
