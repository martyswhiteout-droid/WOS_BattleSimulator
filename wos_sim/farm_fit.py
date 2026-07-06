"""Deterministic farm-battle engine + kernel fit over Far Seer sets 1+3.

Proc-free fights are DETERMINISTIC (GAME_RULES 6i), so a per-turn sim
must reproduce observed beast losses near-EXACTLY if the kernel form is
right. Kernel per attack event:
    kills = k * N^e * A^pa * L^pl / (D^qd * H^qh) * counters * dd/dt
Facts already measured: e = 0.525 (two N-ladders), pa = 1.0 (Seo-yoon
attack ladder: kills respond 1:1 to an attack multiplier when own
survival is unchanged; Jassier +10% DD == Seo +10% attack).

Run: py -m wos_sim.farm_fit
"""

from dataclasses import dataclass, replace
from itertools import product
import math

from .models import StatType, TroopType
from .troop_catalog import interpolated_tier_stats

A, D, L, H = StatType.ATTACK, StatType.DEFENSE, StatType.LETHALITY, StatType.HEALTH
ORDER = [TroopType.INFANTRY, TroopType.LANCER, TroopType.MARKSMAN]
CLS = {"Inf": TroopType.INFANTRY, "Lan": TroopType.LANCER, "Mar": TroopType.MARKSMAN}


@dataclass
class Stack:
    troop: TroopType
    tier: float
    n: float
    stats: dict
    dd_mult: float = 1.0


@dataclass
class Params:
    family: str = "power"
    k: float = 1.0
    e: float = 0.525
    pa: float = 1.0
    pl: float = 1.0
    qd: float = 1.0
    qh: float = 1.0
    ed: float = 0.0      # defender-count exponent (turn-clock evidence ~0.49)
    c: float = 0.10      # floor fraction / saturation constant per family
    k2: float = 0.01     # revenge-family response coefficient
    qs: float = 0.85     # paced-family self-durability damping exponent
    bk: float = 1.0      # paced-family beast-side k multiplier
    counter_mult: float = 1.10


COUNTERS = {TroopType.INFANTRY: TroopType.LANCER,
            TroopType.LANCER: TroopType.MARKSMAN,
            TroopType.MARKSMAN: TroopType.INFANTRY}


def _core(a, l, d, h, p):
    """Per-unit damage-to-kills core, by structural family."""
    if p.family == "power":
        return a ** p.pa * l ** p.pl / (d ** p.qd * h ** p.qh)
    if p.family == "sub_floor":       # subtractive atk-def with % floor
        dmg = max(a - p.qd * d, p.c * a)
        return dmg * l ** p.pl / h ** p.qh
    if p.family == "sub_floor_LD":    # lethality-health also subtractive
        dmg = max(a - p.qd * d, p.c * a)
        kill = max(l - p.qh * h, p.c * l)
        return dmg * kill
    if p.family == "saturate":        # smooth A-vs-D saturation
        dmg = a * a / (a + p.qd * d)
        return dmg * l ** p.pl / h ** p.qh
    if p.family == "two_stage":       # damage pool then conversion ratio
        return (a / (a + p.qd * d)) * a * (l / (l + p.qh * h))
    raise ValueError(p.family)


def _event_paced(atk, dfd, p):
    """Self-paced symmetric kernel: attacker output is damped by its own
    durability (satisfies tier-cancellation, N^1.5 totals, and both
    duration laws by construction; the sweep tests splits/victories)."""
    dmg = (p.k * atk.n ** p.e * dfd.n ** p.ed
           * atk.stats[A] * atk.stats[L]
           / (atk.stats[D] * atk.stats[H]) ** p.qs
           / (dfd.stats[D] ** p.qd * dfd.stats[H] ** p.qh))
    if COUNTERS[atk.troop] == dfd.troop:
        dmg *= p.counter_mult
    if COUNTERS[dfd.troop] == atk.troop and dfd.tier >= 7:
        dmg /= p.counter_mult
    return dmg * atk.dd_mult


def _event(atk, dfd, p, beast_side=False):
    if p.family == "paced":
        d = _event_paced(atk, dfd, p)
        return d * p.bk if beast_side else d
    dmg = (p.k * atk.n ** p.e * dfd.n ** p.ed
           * _core(atk.stats[A], atk.stats[L], dfd.stats[D], dfd.stats[H], p))
    if COUNTERS[atk.troop] == dfd.troop:
        dmg *= p.counter_mult
    if COUNTERS[dfd.troop] == atk.troop and dfd.tier >= 7:
        dmg /= p.counter_mult          # T7+ defensive counter (Bands of Steel)
    return dmg * atk.dd_mult


def _front(stacks):
    for t in ORDER:
        for s in stacks:
            if s.troop == t and s.n > 1e-9:
                return s
    return None


def simulate(own, beast, p, max_turns=800):
    own = [replace(s) for s in own]
    beast = [replace(s) for s in beast]
    b0 = sum(s.n for s in beast)
    kills_by_stack = [0.0] * len(own)
    turns = 0
    revenge = p.family == "revenge"
    while turns < max_turns:
        turns += 1
        own_before = sum(s.n for s in own)
        # beast side attacks first each turn under revenge pacing
        for t in ORDER:
            for s in beast:
                if s.troop == t and s.n > 1e-9:
                    tgt = _front(own)
                    if tgt is None:
                        break
                    q = replace(p, family="power") if revenge else p
                    tgt.n = max(0.0, tgt.n - _event(s, tgt, q, beast_side=True))
        own_deaths = own_before - sum(s.n for s in own)
        # our side responds
        if revenge:
            for i, s in enumerate(own):
                if s.n > 1e-9:
                    tgt = _front(beast)
                    if tgt is None:
                        break
                    dmg = (p.k2 * own_deaths * s.n ** 0.5
                           * s.stats[A] * s.stats[L]
                           / (tgt.stats[D] ** p.qd * tgt.stats[H] ** p.qh)
                           * s.dd_mult)
                    if COUNTERS[s.troop] == tgt.troop:
                        dmg *= p.counter_mult
                    d = min(dmg, tgt.n)
                    tgt.n -= d
                    kills_by_stack[i] += d
        else:
            for t in ORDER:
                for i, s in enumerate(own):
                    if s.troop == t and s.n > 1e-9:
                        tgt = _front(beast)
                        if tgt is None:
                            break
                        d = min(_event(s, tgt, p), tgt.n)
                        tgt.n -= d
                        kills_by_stack[i] += d
        if _front(own) is None or _front(beast) is None:
            break
    beast_losses = b0 - sum(s.n for s in beast)
    own_alive = sum(s.n for s in own)
    return beast_losses, own_alive, turns, kills_by_stack


PANEL = {A: 0.121, D: 0.101, L: 0.100, H: 0.100}
BEASTS = {
    "musk10": dict(bonus=0.085, groups=[("Inf", 3.2, 65), ("Inf", 3.2, 255), ("Lan", 3.2, 75),
                                        ("Lan", 3.2, 300), ("Mar", 3.2, 75), ("Mar", 3.2, 300)]),
    "musk12": dict(bonus=0.144, groups=[("Inf", 4.0, 570), ("Lan", 4.0, 670), ("Mar", 4.0, 670)]),
    "tapir13": dict(bonus=0.185, groups=[("Inf", 4.2, 150), ("Inf", 4.2, 590), ("Lan", 4.2, 170),
                                         ("Lan", 4.2, 690), ("Mar", 4.2, 170), ("Mar", 4.2, 690)]),
    "tapir15": dict(bonus=0.265, groups=[("Inf", 5.0, 1120), ("Lan", 5.0, 1310), ("Mar", 5.0, 1310)]),
}


def own_stacks(army, atk_mult=1.0, dd=1.0):
    out = []
    for cls, tier, n in army:
        troop = CLS[cls]
        raw = interpolated_tier_stats(float(tier), troop)
        st = {A: raw[A] * (1 + PANEL[A]) * atk_mult, D: raw[D] * (1 + PANEL[D]),
              L: raw[L] * (1 + PANEL[L]), H: raw[H] * (1 + PANEL[H])}
        out.append(Stack(troop, tier, n, st, dd_mult=dd))
    return out


def beast_stacks(name):
    b = BEASTS[name]
    out = []
    for cls, lvl, cnt in b["groups"]:
        troop = CLS[cls]
        raw = interpolated_tier_stats(lvl, troop)
        out.append(Stack(troop, lvl, cnt, {s: v * (1 + b["bonus"]) for s, v in raw.items()}))
    return out


# beast, army, atk_mult, dd_mult, obs kills, censored, kills_by_class or None
BATTLES = [
    ("musk12", [("Inf", 7, 900)],  1.00, 1.0, 214,  False, None),
    ("musk12", [("Inf", 7, 1000)], 1.00, 1.0, 252,  False, None),
    ("musk12", [("Inf", 7, 1100)], 1.00, 1.0, 291,  False, None),
    ("musk12", [("Inf", 7, 1200)], 1.00, 1.0, 332,  False, None),
    ("musk12", [("Inf", 2, 1000)], 1.00, 1.0, 26,   False, None),
    ("musk12", [("Inf", 1, 1000)], 1.00, 1.0, 11,   False, None),
    ("musk12", [("Inf", 2, 2000)], 1.00, 1.0, 74,   False, None),
    ("musk12", [("Inf", 7, 1000)], 1.05, 1.0, 264,  False, None),
    ("musk12", [("Inf", 7, 1200)], 1.05, 1.0, 349,  False, None),
    ("musk12", [("Inf", 7, 1200)], 1.10, 1.0, 366,  False, None),
    ("musk12", [("Inf", 7, 500), ("Lan", 6, 200), ("Mar", 6, 300)], 1.00, 1.0, 1466, False, [112, 394, 960]),
    ("musk12", [("Inf", 7, 500), ("Lan", 6, 200), ("Mar", 6, 300)], 1.10, 1.0, 1910, True, None),
    ("tapir13", [("Inf", 7, 1000)], 1.00, 1.0, 177, False, None),
    ("tapir13", [("Inf", 7, 1000)], 1.10, 1.0, 195, False, None),
    ("tapir13", [("Inf", 7, 1200)], 1.10, 1.0, 257, False, None),
    ("tapir13", [("Inf", 7, 1300)], 1.10, 1.0, 291, False, None),
    ("tapir13", [("Inf", 7, 1500)], 1.10, 1.0, 361, False, None),
    ("tapir13", [("Inf", 7, 1200)], 1.00, 1.1, 257, False, None),
    ("tapir13", [("Inf", 7, 1000)], 1.15, 1.0, 204, False, None),
    ("tapir13", [("Inf", 7, 1500)], 1.15, 1.0, 378, False, None),
    ("tapir13", [("Inf", 7, 1400), ("Lan", 6, 300)], 1.00, 1.0, 1146, False, [343, 803]),
    ("tapir13", [("Inf", 7, 1400), ("Lan", 6, 300)], 1.15, 1.0, 1660, False, None),
    ("tapir13", [("Inf", 7, 1500), ("Lan", 6, 200)], 1.15, 1.0, 1441, False, None),
    ("tapir13", [("Inf", 7, 1500), ("Lan", 6, 200)], 1.00, 1.1, 1269, False, None),
    ("tapir13", [("Inf", 7, 1500), ("Lan", 6, 300)], 1.15, 1.0, 2460, True, None),
    # --- set 4 (tier rungs, single-class, beast ladder) ---
    ("musk12", [("Inf", 3, 1000)], 1.00, 1.0, 51,   False, None),
    ("musk12", [("Inf", 4, 1000)], 1.00, 1.0, 87,   False, None),
    ("musk12", [("Inf", 5, 1000)], 1.00, 1.0, 125,  False, None),
    ("musk12", [("Lan", 6, 1000)], 1.00, 1.0, 185,  False, None),
    ("musk12", [("Mar", 6, 1000)], 1.00, 1.0, 202,  False, None),
    ("tapir15", [("Inf", 7, 1000)], 1.00, 1.0, 83,  False, None),
    ("musk10", [("Inf", 7, 1000)], 1.00, 1.0, 1070, True, None),  # VICTORY; own 563/1000 incap
    ("musk12", [("Inf", 6, 1000)], 1.00, 1.0, 174,  False, None),  # set 5: T6 class triple
]

# (beast, army) -> observed own survivors, for uncensored victories
OWN_SURVIVOR_OBS = {("musk10", (("Inf", 7, 1000),)): 437}

# Turn-clock observations (Bradley S3 x4 / Renee S1 x2, cross-validated).
# Heroes only boost own damage, so own-wipe durations transfer to the
# no-hero config at the same army size.
DURATIONS = [
    ("tapir13", [("Inf", 7, 100)], 17.5),
    ("tapir13", [("Inf", 7, 300)], 31.0),
    ("tapir13", [("Inf", 7, 1000)], 57.5),
    ("tapir13", [("Inf", 2, 300)], 9.5),
    ("tapir13", [("Inf", 2, 1000)], 17.5),
    ("musk12", [("Inf", 3, 1000)], 33.5),
    ("musk12", [("Inf", 4, 1000)], 41.5),
    ("musk12", [("Inf", 5, 1000)], 49.5),
    ("musk12", [("Inf", 7, 1000)], 73.5),
]


def predict(p, battle):
    beast, army, am, dd, obs, cens, splits = battle
    bl, own_alive, turns, ks = simulate(own_stacks(army, am, dd), beast_stacks(beast), p)
    return bl, own_alive, turns, ks


def loss(p, verbose=False):
    err = 0.0
    for battle in BATTLES:
        beast, army, am, dd, obs, cens, splits = battle
        bl, own_alive, turns, ks = predict(p, battle)
        if cens:
            if bl < obs - 0.5:                      # must reach full wipe
                err += (math.log(max(bl, 1e-6) / obs)) ** 2
            key = (beast, tuple(army))
            if key in OWN_SURVIVOR_OBS:             # own survivors observable
                obs_surv = OWN_SURVIVOR_OBS[key]
                err += (math.log(max(own_alive, 1.0) / obs_surv)) ** 2
        else:
            err += (math.log(max(bl, 1e-6) / obs)) ** 2
            if own_alive > 0.5:                     # own side must be wiped
                err += 25.0
            if splits:
                for k_pred, k_obs in zip(ks, splits):
                    err += 0.5 * (math.log(max(k_pred, 1e-6) / max(k_obs, 1))) ** 2
        if verbose:
            tag = "CENS" if cens else "    "
            s = f" splits {[round(x) for x in ks]} vs {splits}" if splits else ""
            print(f"  {beast:8} {str(army):<46} x{am:.2f}/{dd:.1f} obs {obs:>5} "
                  f"pred {bl:8.1f} ownleft {own_alive:7.1f} T{turns:>4} {tag}{s}")
    for beast, army, t_obs in DURATIONS:
        _bl, _oa, turns, _ks = simulate(own_stacks(army), beast_stacks(beast), p)
        err += 4.0 * (math.log(max(turns, 1) / t_obs)) ** 2
        if verbose:
            print(f"  DURATION {beast} {army}: pred T={turns} obs {t_obs}")
    return err


def _calibrate_k(p):
    p.k = max(p.k, 1e-6)
    for _ in range(10):
        pred = simulate(own_stacks([("Inf", 7, 1000)]), beast_stacks("musk12"), p)[0]
        if abs(pred - 252) < 0.3 or pred <= 1e-9:
            break
        p.k *= (252 / max(pred, 1e-9)) ** 0.6
    return p


GRIDS = {
    "power":        dict(pl=[0.0, 0.25, 0.5, 1.0], qd=[0.25, 0.5, 1.0, 1.25], qh=[0.5, 1.0, 1.5], c=[0.1]),
    "sub_floor":    dict(pl=[0.0, 0.5, 1.0], qd=[0.5, 0.75, 1.0, 1.25], qh=[0.5, 1.0, 1.5], c=[0.05, 0.1, 0.2, 0.4]),
    "sub_floor_LD": dict(pl=[1.0], qd=[0.5, 0.75, 1.0, 1.25], qh=[0.25, 0.5, 0.75, 1.0], c=[0.05, 0.1, 0.2, 0.4]),
    "saturate":     dict(pl=[0.0, 0.5, 1.0], qd=[0.5, 1.0, 2.0, 4.0], qh=[0.5, 1.0, 1.5], c=[0.1]),
    "two_stage":    dict(pl=[1.0], qd=[0.5, 1.0, 2.0], qh=[0.5, 1.0, 2.0], c=[0.1]),
    "revenge":      dict(pl=[1.0], qd=[0.85, 1.0], qh=[0.85, 1.0], c=[0.1]),
    "paced":        dict(pl=[1.0], qd=[0.85, 1.0], qh=[0.85, 1.0], c=[0.1]),
}


def _calibrate_paced(p):
    """k -> kills 252 (T7-1000-Musk); bk -> duration 73.5 there."""
    for _ in range(14):
        bl, oa, t, _ = simulate(own_stacks([("Inf", 7, 1000)]), beast_stacks("musk12"), p)
        ok_k = abs(bl - 252) < 0.5
        ok_t = abs(t - 73.5) < 1.0
        if ok_k and ok_t:
            break
        if bl > 1e-9 and not ok_k:
            p.k *= (252 / bl) ** 0.6
        if t > 0 and not ok_t:
            p.bk *= (t / 73.5) ** 0.7
    return p


def _calibrate_revenge(p):
    """k -> duration 73.5 (T7-1000-Musk); k2 -> kills 252 there."""
    for _ in range(12):
        bl, oa, t, _ = simulate(own_stacks([("Inf", 7, 1000)]), beast_stacks("musk12"), p)
        if abs(t - 73.5) < 1.0 and abs(bl - 252) < 0.5:
            break
        if t > 0:
            p.k *= (t / 73.5) ** 0.7          # more incoming -> shorter battle
        if bl > 1e-9:
            p.k2 *= (252 / bl) ** 0.7
    return p


def fit(family):
    g = GRIDS[family]
    best, best_err = None, float("inf")
    e_grid = [0.9, 1.0, 1.05] if family == "paced" else [0.525, 0.75, 1.0]
    ed_grid = [0.4, 0.485, 0.55] if family == "paced" else [0.0, 0.25, 0.5]
    qs_grid = [0.7, 0.85, 1.0] if family == "paced" else [0.85]
    for pl, qd, qh, c in product(g["pl"], g["qd"], g["qh"], g["c"]):
        for e_att, e_def, qs in product(e_grid, ed_grid, qs_grid):
            p = Params(family=family, pl=pl, qd=qd, qh=qh, c=c,
                       k=1.0, e=e_att, ed=e_def, qs=qs)
            p = (_calibrate_revenge(p) if family == "revenge"
                 else _calibrate_paced(p) if family == "paced"
                 else _calibrate_k(p))
            err = loss(p)
            if err < best_err:
                best, best_err = p, err
    p = best
    for _round in range(5):
        for attr, step in (("pl", 0.05), ("qd", 0.05), ("qh", 0.05), ("c", 0.02),
                           ("k", 0.02), ("k2", 0.02), ("bk", 0.03), ("qs", 0.03),
                           ("e", 0.01), ("ed", 0.02), ("counter_mult", 0.02)):
            for sgn in (+1, -1):
                improved = True
                while improved:
                    q = replace(p)
                    setattr(q, attr, getattr(p, attr) + sgn * step)
                    if loss(q) < loss(p):
                        p = q
                    else:
                        improved = False
    return p


if __name__ == "__main__":
    import sys
    fams = sys.argv[1:] or list(GRIDS)
    results = []
    for fam in fams:
        p = fit(fam)
        e = loss(p)
        results.append((e, fam, p))
        print(f"[{fam}] loss={e:.5f} k={p.k:.5f} e={p.e:.3f} pl={p.pl:.3f} "
              f"qd={p.qd:.3f} qh={p.qh:.3f} c={p.c:.3f} counter={p.counter_mult:.3f}",
              flush=True)
    results.sort()
    e, fam, p = results[0]
    print(f"\nWINNER: {fam} loss={e:.5f}")
    loss(p, verbose=True)
