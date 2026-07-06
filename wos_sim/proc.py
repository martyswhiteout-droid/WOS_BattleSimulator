"""Proc scheduler + Monte-Carlo runner (E-5) - the STOCHASTIC layer.

The deterministic core (pvp_engine/farm_engine) computes damage as its
EXPECTED value; real battles have RNG in PROC ROLLS (GAME_RULES 6i:
determinism holds ONLY without proc skills). This module rolls procs per
turn with a SEEDED rng so N runs produce an OUTCOME DISTRIBUTION - the
substrate for BRD Goal-2 Monte Carlo and Goal-1 optimization (CRN via
shared seeds).

Modelled now (structure is pluggable - add procs in _side_damage_stoch):
  * Ambusher (T7+ lancers): per-turn Bernoulli 0.20; on hit the WHOLE
    lancer stack's output bypasses to enemy marksmen (GAME_RULES: whole
    stack per event). EV = 0.20 -> matches the deterministic fraction, so
    the MC MEAN reproduces the deterministic engine.
  * Crystal Lance (FC3/5 lancers): double-damage that turn at p.crystal_lance.
Hooks left for: Crystal Shield 36-offset, gun double, hero proc skills.

MC reports BOTH error types separately (BRD NFR3): MC sampling s.e.
(shrinks 1/sqrt(N)) vs the engine model/calibration error (tracked
elsewhere; the PvP kernel is not yet calibrated - see ROADMAP).

Run:  py -m wos_sim.proc
"""

import random
from dataclasses import replace

from .mechanics import (LANCER_BYPASS_CHANCE, AMBUSHER_MIN_TIER,
                        CRYSTAL_LANCE_MIN_TIER)
from .models import TroopType
from .t12 import side_mods as t12_mods
from .pvp_engine import (A, D, H, L, BEST_PARAMS, COUNTERS, PvpResult, Unit,
                        _KC, _apply, _front)
from .troop_catalog import interpolated_tier_power


def _clone(units):
    return [replace(u, astat=dict(u.astat)) for u in units]


def _stack_output(s, df, af, p):
    """Raw output of one attacker stack vs defender front (pre ambush/scale)."""
    qd, qh, so, pc, cm = p["qd"], p["qh"], p["so"], p["pc"], p["cm"]
    dmg = (p[_KC[s.troop]] * s.n * (s.astat[A] * s.astat[L])
           / (df.astat[D] ** qd * df.astat[H] ** qh)
           / interpolated_tier_power(s.tier) ** so
           * (1.0 + s.dd) * (1.0 + df.dt))
    if s is af:
        dmg *= p["pin"]
    if pc > 0:
        dmg *= s.base_atk / (s.base_atk + pc * df.astat[D])
    if COUNTERS[s.troop] == df.troop:
        dmg *= cm
    return dmg


def _side_damage_stoch(attackers, defenders, p, rng, frontage_exp=1.0,
                       scale=1.0, t12=(1.0, 1.0, 1.0)):
    df = _front(defenders)
    if df is None:
        return 0.0, 0.0
    af = _front(attackers)
    front, byp = 0.0, 0.0
    cl = p.get("crystal_lance", 0.15)
    atk_marks_dd, def_inf_dt, def_enemy_out = t12
    for s in attackers:
        if s.n <= 1e-9:
            continue
        dmg = _stack_output(s, df, af, p)
        if s.troop == TroopType.MARKSMAN:
            dmg *= atk_marks_dd                          # T12 marks buff
        if (s.troop == TroopType.LANCER and s.tier >= CRYSTAL_LANCE_MIN_TIER
                and cl > 0 and rng.random() < cl):
            dmg *= 2.0                                   # Crystal Lance (FC/T11+)
        if (s.troop == TroopType.LANCER and s.tier >= AMBUSHER_MIN_TIER
                and rng.random() < LANCER_BYPASS_CHANCE):
            byp += dmg                                   # Ambusher whole-stack (T7+)
        else:
            front += dmg
    if df.troop == TroopType.INFANTRY:
        front *= def_inf_dt                              # T12 inf DT down
    front *= def_enemy_out                               # T12 Indomitable Wall
    byp *= def_enemy_out
    if frontage_exp != 1.0:
        nf = sum(s.n for s in attackers if s.n > 1e-9)
        if nf > 0:
            scale *= nf ** (frontage_exp - 1.0)
    return front * scale, byp * scale


def simulate_stoch(a_units, d_units, params, rng, max_turns=4000):
    """One stochastic battle (procs rolled via rng). Mirrors
    pvp_engine.simulate_pvp but with per-turn proc rolls."""
    p = dict(BEST_PARAMS)
    p.setdefault("rate", 1.0)
    if params:
        p.update(params)
    a, d = _clone(a_units), _clone(d_units)
    a0, d0 = sum(u.n for u in a), sum(u.n for u in d)
    def_ed, def_k, rate = p.get("def_ed", 1.0), p.get("def_k", 1.0), p["rate"]
    t = 0
    while t < max_turns:
        t += 1
        a_md, a_idt, a_eo = t12_mods(p.get("a_t12"), t)
        d_md, d_idt, d_eo = t12_mods(p.get("d_t12"), t)
        af, ab = _side_damage_stoch(a, d, p, rng, 1.0, rate, (a_md, d_idt, d_eo))
        dfd, db = _side_damage_stoch(d, a, p, rng, def_ed, rate * def_k,
                                     (d_md, a_idt, a_eo))
        _apply(d, af)
        if ab > 0:
            _apply(d, ab, TroopType.MARKSMAN)
        _apply(a, dfd)
        if db > 0:
            _apply(a, db, TroopType.MARKSMAN)
        aa, da = _front(a) is not None, _front(d) is not None
        if not aa or not da:
            w = ("mutual" if (not aa and not da) else "D" if not aa else "A")
            break
    else:
        w = "A" if sum(u.n for u in a) >= sum(u.n for u in d) else "D"
    return PvpResult(w, t, {u.troop: u.incap for u in a},
                     {u.troop: u.incap for u in d}, a0, d0)


def _dist(xs):
    xs = sorted(xs)
    n = len(xs)
    m = sum(xs) / n
    sd = (sum((x - m) ** 2 for x in xs) / n) ** 0.5
    def q(pp):
        return xs[min(n - 1, int(pp * n))]
    return {"mean": m, "sd": sd, "se": sd / n ** 0.5,
            "p5": q(0.05), "p50": q(0.5), "p95": q(0.95)}


def monte_carlo(a_units, d_units, params=None, n=10000, seed=0):
    """Run n stochastic battles -> outcome distribution. Seeded for
    reproducibility; use the SAME seed across candidates for CRN (Goal 1)."""
    wins = {"A": 0, "D": 0, "mutual": 0}
    a_inc, d_inc, turns = [], [], []
    for i in range(n):
        rng = random.Random(seed * 1_000_003 + i)
        res = simulate_stoch(a_units, d_units, params, rng)
        wins[res.winner] += 1
        a_inc.append(sum(res.a_incap.values()))
        d_inc.append(sum(res.d_incap.values()))
        turns.append(res.turns)
    return {"n": n, "p_win_A": wins["A"] / n, "p_win_D": wins["D"] / n,
            "p_mutual": wins["mutual"] / n,
            "a_incap": _dist(a_inc), "d_incap": _dist(d_inc),
            "turns": _dist(turns)}


if __name__ == "__main__":
    # smoke test: MC over a real report; check the distribution + that the
    # mean tracks the deterministic engine (Ambusher EV = its fraction).
    from .assemble import assemble_battle
    from .loader import load_skill_book
    from .pvp_engine import simulate_pvp, units_from_side
    from .reports import load_all_reports
    book = load_skill_book(r"WoS battle simulator.xlsx")
    # r004 has ~493k attacker LANCERS -> Ambusher + Crystal Lance procs ->
    # real MC variance (r006's 5-0-5 attacker has no lancers = deterministic).
    r = {("report_" + x.report_id.split("_")[1]): x
         for x in load_all_reports()}["report_004"]
    a, d, board = assemble_battle(r, book)
    au, du = units_from_side(a), units_from_side(d)
    for tag, us in (("A", au), ("D", du)):
        for u in us:
            u.dd = board.dd.get((tag, u.troop), 0.0)
            u.dt = board.dt.get((tag, u.troop), 0.0)
    P = {"rate": 320.0, "def_k": 1000.0, "def_ed": 0.483}
    det = simulate_pvp(au, du, P)
    mc = monte_carlo(au, du, P, n=2000, seed=0)
    print(f"r004 deterministic: winner {det.winner}  A_incap "
          f"{sum(det.a_incap.values()):,.0f}  D_incap "
          f"{sum(det.d_incap.values()):,.0f}  T{det.turns}")
    # show BOTH sides; the LOSER's incap saturates (fully wiped -> zero spread),
    # so the proc variance is visible on the surviving/winning side.
    for side in ("a_incap", "d_incap"):
        d = mc[side]
        print(f"r004 MC (n={mc['n']}) {side}: mean {d['mean']:,.0f} "
              f"+-{d['se']:,.0f} (se), sd {d['sd']:,.0f} "
              f"[p5 {d['p5']:,.0f} .. p95 {d['p95']:,.0f}]")
    print(f"   P(A win)={mc['p_win_A']:.3f}  turns mean {mc['turns']['mean']:.1f} "
          f"[{mc['turns']['p5']:.0f}..{mc['turns']['p95']:.0f}]")
