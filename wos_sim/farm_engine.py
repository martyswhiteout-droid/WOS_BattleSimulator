"""Round-3 mechanism: ASYMMETRIC COMBAT WIDTH + per-class coefficients.

Motivation (GAME_RULES 6i-6o; ENGINE_PLAN Phase 1):
Rounds 1-2 used SYMMETRIC pacing and could not satisfy the duration and
total-kills exponents at once. The joint law
    duration   T      ~ N^0.515
    total kills        ~ N^1.525
is only reconcilable with an ASYMMETRIC structure:
  * OUR kill rate is LINEAR in our live count (every own unit fires at
    the compact beast): rate ~ N^1.
  * THE BEAST engages only our frontage each turn ~ N^ed, ed~0.485, so
    our front dies at rate ~ N^ed  ->  T = N / N^ed = N^(1-ed) = N^0.515,
    and total = rate x T ~ N^1 x N^0.515 = N^1.515.
One exponent (ed) sets BOTH measured slopes.

Per turn (dt = 1 turn):
  OWN -> BEAST (offense; all own stacks fire, protected & front alike):
    dmg_s = kc[class_s] * n_s * (A_s L_s) / (D_bf H_bf)^qd  * counter
    routed to the beast FRONT stack (absorption Inf->Lan->Mar), overkill
    cascades to the next beast group.
  BEAST -> OWN (incoming; hits own FRONT only, sublinear frontage):
    dmg_in = kb * n_of^ed * beastpress * (A_bf L_bf) / (D_of H_of)^qh
    beastpress = (live beast units / initial) damps incoming as the beast
    crumbles (fixes the whale-victory cases that broke round 1).

Per-class kc absorbs the cross-class flatness (same-tier solo classes kill
nearly flat despite A*L ratios 1:2.5:3.05 - a class-linked, not
durability-linked, effect: see STATUS round-2 diagnostic).

Run:
  py -m wos_sim.farm_engine          # quick stored-parameter QA check
  py -m wos_sim.farm_engine de [n]   # expensive differential evolution fit
  py -m wos_sim.farm_engine fit      # coordinate-descent fit
"""

from dataclasses import replace
from itertools import product
import math
import sys

from .farm_fit import (A, D, L, H, ORDER, COUNTERS, Stack, own_stacks,
                       beast_stacks, BEASTS, BATTLES, DURATIONS,
                       OWN_SURVIVOR_OBS)
from .models import TroopType
from .troop_catalog import interpolated_tier_power, interpolated_tier_stats

KCLASS = {TroopType.INFANTRY: "ki", TroopType.LANCER: "kl", TroopType.MARKSMAN: "km"}


def _front(stacks):
    for t in ORDER:
        for s in stacks:
            if s.troop == t and s.n > 1e-9:
                return s
    return None


def simulate(own, beast, prm, max_turns=4000):
    """prm: dict with ki,kl,km,kb,ed,qd,qh,cm (counter),bpow (beastpress exp).
    Returns (beast_losses, own_alive, turns, kills_by_stack)."""
    own = [replace(s) for s in own]
    beast = [replace(s) for s in beast]
    b0 = sum(s.n for s in beast)
    o0 = sum(s.n for s in own)
    kc = {TroopType.INFANTRY: prm["ki"], TroopType.LANCER: prm["kl"],
          TroopType.MARKSMAN: prm["km"]}
    ed, qd, qh, kb, cm = prm["ed"], prm["qd"], prm["qh"], prm["kb"], prm["cm"]
    bpow = prm.get("bpow", 1.0)
    so = prm.get("so", 0.0)   # own self-durability THROTTLE on firing rate
    pc = prm.get("pc", 0.0)   # armor-penetration constant (0 = disabled)
    pin = prm.get("pin", 1.0)  # PINNED-FRONT penalty: the own stack being
    #                            attacked fires at fraction `pin`; protected
    #                            (back) stacks fire freely. Physically: a
    #                            targeted unit is engaged/defending.
    kills = [0.0] * len(own)
    turns = 0
    while turns < max_turns:
        turns += 1
        bf = _front(beast)
        of = _front(own)
        if bf is None or of is None:
            break
        # --- OWN -> BEAST : every own stack fires, all at the beast front
        beast_live = sum(s.n for s in beast)
        dmg_pool = {}  # stack index -> damage this turn (for cascade + splits)
        for i, s in enumerate(own):
            if s.n <= 1e-9:
                continue
            # self-throttle on POWER (the game's tier index): compresses
            # WITHIN-class tier spread; leaves same-tier classes equal
            # (all classes share power per tier) for per-class k to balance.
            dmg = kc[s.troop] * s.n * (s.stats[A] * s.stats[L]) \
                / (bf.stats[D] ** qd * bf.stats[H] ** qh) \
                / interpolated_tier_power(s.tier) ** so * s.dd_mult
            # ARMOR PENETRATION (round 4): keyed on BASE tier attack (buff-
            # independent -> preserves marginal linearity) vs the beast's
            # REAL (effective) defense. Suppresses low tiers whose raw
            # attack barely penetrates; ~1 for high tiers. pc=0 disables.
            if pc > 0:
                a_base = interpolated_tier_stats(s.tier, s.troop)[A]
                dmg *= a_base / (a_base + pc * bf.stats[D])
            if s is of:                 # this stack is the pinned front
                dmg *= pin
            if COUNTERS[s.troop] == bf.troop:
                dmg *= cm
            dmg_pool[i] = dmg
        # apply own damage with cascade through beast absorption order
        for i, dmg in dmg_pool.items():
            remaining = dmg
            for t in ORDER:
                if remaining <= 1e-12:
                    break
                for bs in beast:
                    if bs.troop == t and bs.n > 1e-9:
                        take = min(remaining, bs.n)
                        bs.n -= take
                        kills[i] += take
                        remaining -= take
                        if remaining <= 1e-12:
                            break
        # --- BEAST -> OWN : hits own front only, sublinear in own frontage
        of = _front(own)
        if of is None:
            break
        press = (beast_live / b0) ** bpow if b0 > 0 else 0.0
        dmg_in = kb * (of.n ** ed) * press \
            * (bf.stats[A] * bf.stats[L]) / (of.stats[D] ** qd * of.stats[H] ** qh)
        # beast front counter vs our front
        if COUNTERS[bf.troop] == of.troop:
            dmg_in *= cm
        of.n = max(0.0, of.n - dmg_in)
        if _front(own) is None or _front(beast) is None:
            break
    beast_losses = b0 - sum(s.n for s in beast)
    own_alive = sum(s.n for s in own)
    return beast_losses, own_alive, turns, kills


# ------------------------------------------------------------------ loss

def _predict(prm, beast, army, am, dd):
    return simulate(own_stacks(army, am, dd), beast_stacks(beast), prm)


# Marginal-linearity ANCHORS (physically locked, GAME_RULES 6j/6m): same
# army, an attack multiplier am -> kills must scale ~am. These are heavily
# weighted so the optimizer cannot trade away the confirmed linearity.
MARGINAL = [
    ("musk12", [("Inf", 7, 1000)], 1.00, 1.05),   # 252 -> 264
    ("musk12", [("Inf", 7, 1200)], 1.00, 1.05),   # 332 -> 349
    ("musk12", [("Inf", 7, 1200)], 1.00, 1.10),   # 332 -> 366
    ("tapir13", [("Inf", 7, 1000)], 1.00, 1.10),  # 177 -> 195
    ("tapir13", [("Inf", 7, 1000)], 1.00, 1.15),  # 177 -> 204
]


def loss(prm, verbose=False):
    err = 0.0
    for beast, army, am, dd, obs, cens, splits in BATTLES:
        bl, oa, t, ks = _predict(prm, beast, army, am, dd)
        if cens:
            if bl < obs - 0.5:
                err += math.log(max(bl, 1e-6) / obs) ** 2
            key = (beast, tuple(army))
            if key in OWN_SURVIVOR_OBS:
                err += 0.5 * math.log(max(oa, 1.0) / OWN_SURVIVOR_OBS[key]) ** 2
        else:
            err += math.log(max(bl, 1e-6) / obs) ** 2
            if oa > 0.5:
                err += 25.0
            if splits:
                for kp, ko in zip(ks, splits):
                    err += 0.5 * math.log(max(kp, 1e-6) / max(ko, 1)) ** 2
        if verbose:
            tag = "CENS" if cens else "    "
            sp = f" split {[round(x) for x in ks]} vs {splits}" if splits else ""
            print(f"  {beast:8} {str(army):<44} x{am:.2f}/{dd:.1f} "
                  f"obs {obs:>5} pred {bl:8.1f} oleft {oa:7.1f} T{t:>4} {tag}{sp}")
    for beast, army, tobs in DURATIONS:
        _, _, t, _ = _predict(prm, beast, army, 1.0, 1.0)
        err += 4.0 * math.log(max(t, 1) / tobs) ** 2
        if verbose:
            print(f"  DUR {beast} {str(army):<26} pred T={t:>4}  obs {tobs}")
    for beast, army, am0, am1 in MARGINAL:
        b0 = _predict(prm, beast, army, am0, 1.0)[0]
        b1 = _predict(prm, beast, army, am1, 1.0)[0]
        if b0 > 1e-6:
            ratio = b1 / b0
            err += 6.0 * math.log(ratio / am1) ** 2   # enforce kills-scale=am
            if verbose:
                print(f"  MARG {beast} {str(army):<22} x{am1:.2f}: "
                      f"pred ratio {ratio:.3f} (want {am1:.2f})")
    return err


# ------------------------------------------------------------------ fit

BASE = dict(ki=1.0, kl=1.0, km=1.0, kb=1.0, ed=0.485, qd=1.0, qh=0.9,
            cm=1.10, bpow=1.0, so=0.85, pin=0.5)
STEP = dict(ki=0.06, kl=0.06, km=0.06, kb=0.06, ed=0.02, qd=0.04, qh=0.04,
            cm=0.02, bpow=0.1, so=0.04, pin=0.04)

# Physical priors (wostools): class counter is +10% => cm fixed at 1.10.
# When PIN_CM is True cm is held (robustness test - no free-knob cheating).
PIN_CM = True


def _calibrate_scale(prm):
    """Scale ki,kl,km,kb together so T7-1000-Musk hits 252 kills & 73.5 turns.
    kb sets duration; overall k-scale sets kills. Alternate."""
    for _ in range(16):
        bl, oa, t, _ = _predict(prm, "musk12", [("Inf", 7, 1000)], 1.0, 1.0)
        ok_t = abs(t - 73.5) < 1.5
        ok_k = abs(bl - 252) < 1.0
        if ok_t and ok_k:
            break
        if t > 0 and not ok_t:
            prm["kb"] *= (t / 73.5) ** 0.8   # more incoming -> shorter
        if bl > 1e-9 and not ok_k:
            f = (252 / bl) ** 0.6
            for key in ("ki", "kl", "km"):
                prm[key] *= f
    return prm


def coord_descent(prm, rounds=8):
    prm = dict(prm)
    keyset = ("ki", "kl", "km", "kb", "ed", "qd", "qh", "bpow", "so", "pin")
    if not PIN_CM:
        keyset = keyset + ("cm",)
    for _ in range(rounds):
        for key in keyset:
            step = STEP[key]
            for sgn in (+1, -1):
                while True:
                    cand = dict(prm)
                    cand[key] = prm[key] + sgn * step
                    if cand[key] <= 0 and key in ("ki", "kl", "km", "kb", "qd", "qh"):
                        break
                    if loss(cand) < loss(prm) - 1e-9:
                        prm = cand
                    else:
                        break
    return prm


def fit():
    best, berr = None, float("inf")
    for ed, qh, so, pin0, km0 in product([0.42, 0.485, 0.55], [0.75, 0.9, 1.05],
                                         [0.85, 1.0], [0.35, 0.55, 0.8],
                                         [0.5, 0.9, 1.3]):
        prm = dict(BASE, ed=ed, qh=qh, so=so, pin=pin0, km=km0)
        if PIN_CM:
            prm["cm"] = 1.10
        prm = _calibrate_scale(prm)
        e = loss(prm)
        if e < berr:
            best, berr = prm, e
    best = coord_descent(best, rounds=10)
    return best


# --- Round 4: GLOBAL optimizer (differential evolution), ed+cm PINNED to
#     their independently-measured / documented values (no free-knob cheat).
ED_PIN = 0.483   # clock-derived (T ~ N^0.5166 => ed = 1 - 0.5166)
CM_PIN = 1.10    # wostools class counter = +10%

# ROUND 4 best honest fit (DE, ed+cm pinned physical, marginal anchors).
# loss 1.97 over 35 battles + 9 durations + 5 marginal anchors.
# Accurate in the HIGH-TIER regime that real battles use (T7 within ~5%,
# mixed dealers within ~5-15%, marginal linearity exact, censored
# victories classify correctly). Residuals concentrate in DIAGNOSTIC-only
# regimes (solo low-tier T1-T5 +30-50%, solo marksman -30%) that never
# occur in real high-tier PvP. Downstream (predictor/optimizer) loads this.
BEST_PARAMS = dict(ki=2.7046, kl=2.3338, km=1.2057, kb=6.5251, ed=0.483,
                   qd=0.4967, qh=1.4531, cm=1.10, bpow=1.4701, so=1.3028,
                   pin=0.8186, pc=1.1239)
# free params + bounds (order matters)
FREE = [("ki", 0.05, 4.0), ("kl", 0.05, 4.0), ("km", 0.05, 4.0),
        ("kb", 0.5, 16.0), ("qd", 0.4, 1.6), ("qh", 0.4, 1.6),
        ("so", 0.3, 1.5), ("pin", 0.2, 1.0), ("bpow", 0.5, 2.5),
        ("pc", 0.0, 3.0)]


def _vec_to_prm(x):
    prm = dict(BASE, ed=ED_PIN, cm=CM_PIN)
    for (name, _lo, _hi), v in zip(FREE, x):
        prm[name] = float(v)
    return prm


def fit_de(seed=0, maxiter=60, popsize=18, workers=1):
    from scipy.optimize import differential_evolution
    bounds = [(lo, hi) for _n, lo, hi in FREE]
    res = differential_evolution(
        lambda x: loss(_vec_to_prm(x)), bounds, seed=seed, maxiter=maxiter,
        popsize=popsize, tol=1e-7, mutation=(0.4, 1.2), recombination=0.8,
        polish=True, init="sobol", workers=workers, updating="deferred")
    return _vec_to_prm(res.x), res.fun


if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "check"
    keys = ("ki", "kl", "km", "kb", "ed", "qd", "qh", "cm", "bpow", "so", "pin", "pc")
    verbose = False
    if mode in ("check", "best"):
        prm = dict(BEST_PARAMS)
        print("BEST_PARAMS check:", flush=True)
    elif mode == "de" or mode.isdigit():
        maxiter = int(sys.argv[2]) if mode == "de" and len(sys.argv) > 2 else (
            int(mode) if mode.isdigit() else 60)
        prm, fun = fit_de(maxiter=maxiter)
        verbose = True
        print(f"DE (ed={ED_PIN} cm={CM_PIN} pinned, maxiter={maxiter}):", flush=True)
    elif mode == "fit":
        prm = fit()
        verbose = True
        print("Coordinate fit:", flush=True)
    else:
        raise SystemExit(
            "usage: py -m wos_sim.farm_engine [check|best|de [maxiter]|fit]"
        )
    print("BEST:", "  ".join(f"{k}={prm[k]:.4f}" for k in keys), flush=True)
    print(f"loss={loss(prm, verbose=verbose):.5f}")
