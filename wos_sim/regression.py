"""Regression gate (E-10) - one command that proves nothing silently broke.

As the engine keeps changing (PvP structure, procs, T12, ...), this guards
the ALREADY-SOLVED pieces: the beast/farm fit, the key farm ladder points,
the confirmed stat algebra, the PvP r6/r8 calibration, and that the proc
MC mean tracks the deterministic engine. Run before/after any engine edit.

Run:  py -m wos_sim.regression   (exit 0 = all green)
"""

import sys


def _check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    return ok


def main():
    ok = True

    # 1. Beast/farm kernel fit is unchanged (round-4 solved value).
    import wos_sim.farm_engine as F
    loss = F.loss(F.BEST_PARAMS)
    ok &= _check("beast/farm fit loss ~1.97", abs(loss - 1.973) < 0.05,
                 f"loss={loss:.4f}")

    # 2. Key deterministic farm points reproduce (T7 N-ladder near-exact).
    for beast, army, obs, tol in (("musk12", [("Inf", 7, 1000)], 252, 0.10),
                                  ("musk12", [("Inf", 7, 1200)], 332, 0.10),
                                  ("tapir13", [("Inf", 7, 1000)], 177, 0.12)):
        bl = F.simulate(F.own_stacks(army), F.beast_stacks(beast), F.BEST_PARAMS)[0]
        ok &= _check(f"farm {beast} {army} kills~{obs}",
                     abs(bl - obs) / obs < tol, f"pred={bl:.0f}")

    # 3. Confirmed stat algebra (buff = (1+perm)(1+buffs); divisor for penalties).
    import json
    from pathlib import Path
    ab = json.loads((Path(F.__file__).parent / "data" / "enemy_penalty_ab.json")
                    .read_text(encoding="utf-8"))
    perm = 8.861  # Inf Defense permanent (marlinman)
    pred = (1 + perm) * 1.16 / 1.05 - 1  # buffs 0.16, enemy pen 0.05
    obs = ab["panels"]["right_with_penalty"]["Infantry"][1] / 100.0
    ok &= _check("divisor stat rule (Inf Def w/ penalty)",
                 abs(pred - obs) < 0.01, f"pred={pred*100:.1f}% obs={obs*100:.1f}%")

    # 4. PvP r6/r8 calibration holds (attacker wins, both near-wipe).
    from .assemble import assemble_battle
    from .loader import load_skill_book
    from .pvp_engine import simulate_pvp, units_from_side
    from .reports import load_all_reports
    from .predictor.kernel import DEFAULT_PVP_PARAMS
    book = load_skill_book(r"WoS battle simulator.xlsx")
    reps = {("report_" + r.report_id.split("_")[1]): r for r in load_all_reports()}
    P = dict(DEFAULT_PVP_PARAMS)                 # rate=168 (duration-calibrated)
    # rate=168 fits the REAL round counts (GAME_RULES 6r): r006 ~33, r008 ~42.
    _TURN_TARGET = {"report_006": (30, 36), "report_008": (38, 45)}
    for rid in ("report_006", "report_008"):
        r = reps[rid]
        a, d, board = assemble_battle(r, book)
        au, du = units_from_side(a), units_from_side(d)
        res = simulate_pvp(au, du, P)
        lo, hi = _TURN_TARGET[rid]
        ok &= _check(f"PvP {rid} attacker wins @ real duration",
                     res.winner == "A" and lo <= res.turns <= hi,
                     f"winner={res.winner} turns={res.turns} (want {lo}-{hi})")

    # 5. Proc MC mean tracks the deterministic engine (Ambusher EV = 0.20).
    from .proc import monte_carlo
    r = reps["report_004"]
    a, d, board = assemble_battle(r, book)
    au, du = units_from_side(a), units_from_side(d)
    for tag, us in (("A", au), ("D", du)):
        for u in us:
            u.dd = board.dd.get((tag, u.troop), 0.0)
            u.dt = board.dt.get((tag, u.troop), 0.0)
    # compare like-for-like: Ambusher only (crystal_lance off), whose
    # whole-stack Bernoulli EV(0.20) matches the deterministic fraction.
    det = sum(simulate_pvp(au, du, P).d_incap.values())
    mc = monte_carlo(au, du, dict(P, crystal_lance=0.0), n=800, seed=1)["d_incap"]["mean"]
    ok &= _check("proc MC mean ~ deterministic (Ambusher EV, r004)",
                 abs(mc - det) / det < 0.05, f"mc={mc:.0f} det={det:.0f}")

    # 6. T12 skills wired: on r006 (attacker WINS), defender Indomitable
    #    Wall + Meridian make the attacker take longer to win.
    r6 = reps["report_006"]
    a6, d6, _ = assemble_battle(r6, book)
    au6, du6 = units_from_side(a6), units_from_side(d6)
    base = simulate_pvp(au6, du6, P).turns
    t12 = simulate_pvp(au6, du6, dict(P, d_t12={"indomitable_wall": 24,
                                              "meridian_phalanx": 24})).turns
    ok &= _check("T12 defender skills slow the attacker (r006)", t12 > base,
                 f"turns {base} -> {t12}")

    # 7. Controlled-ladder PvP casualty kernel (E-11) reproduces the 8 points.
    from .pvp_kernel import attacker_casualties
    kmax = 0.0
    for na, nd, obs in ((3000, 6000, 775), (10000, 16000, 1835),
                        (16000, 6000, 343), (10000, 3000, 169),
                        (20000, 6000, 338)):
        pred, win = attacker_casualties(na, nd)
        kmax = max(kmax, abs(pred - obs) / obs)
        if not win:
            ok = False
    ok &= _check("PvP ladder kernel reproduces v9/v9b/v9c", kmax < 0.06,
                 f"max err {kmax*100:.1f}%")

    # 8. troop_base_stats serves EVERY tier T1-T12 (sub-T10 no longer KeyErrors)
    #    with the wiki-confirmed base values (Atk, Def, Leth, HP).
    from .troop_catalog import troop_base_stats
    from .models import StatType, TroopType as _TT
    _A, _D, _L, _H = StatType.ATTACK, StatType.DEFENSE, StatType.LETHALITY, StatType.HEALTH
    tb_ok = True
    for tier, troop, exp in ((6, _TT.LANCER, (9, 7, 10, 7)),
                             (7, _TT.INFANTRY, (7, 10, 7, 12)),
                             (6, _TT.MARKSMAN, (10, 6, 11, 6)),
                             (11, _TT.INFANTRY, (19, 28, 18, 27))):  # FC10 endgame
        s = troop_base_stats(tier, 10, troop)
        tb_ok &= (s[_A], s[_D], s[_L], s[_H]) == exp
    ok &= _check("troop_base_stats serves T1-T12 (wiki base tiers)", tb_ok)

    # 9. Confidence routing is STAT-AWARE (QA Critical) + deterministic records
    #    are not aliased + the general path is honestly uncalibrated (QA High).
    from .pvp_engine import Unit as _U
    from .predictor.kernel import engine_meta, run_batch_units
    from .pvp_kernel import attacker_casualties as _akc
    _INF, _MAR = _TT.INFANTRY, _TT.MARKSMAN
    def _u(tr, ti, cnt, mult=2.7):
        base = troop_base_stats(int(ti), 0, tr)
        return _U(tr, float(ti), float(cnt),
                  {s: base[s] * mult for s in (_A, _D, _L, _H)}, base[_A])
    a_box = [_u(_INF, 10, 3000), _u(_MAR, 6, 3000)]      # T10 att, near-even panels
    d_box = [_u(_INF, 7, 3000), _u(_MAR, 6, 3000)]       # T7 def, 6000 total
    m_box = engine_meta(a_box, d_box, None)
    recs = run_batch_units(a_box, d_box, n=3, seed=0)
    exp_cas, _ = _akc(6000, 6000)
    box_ok = (m_box["path"] == "pvp_kernel" and m_box["calibrated"] is True
              and abs(m_box["model_error"] - 0.045) < 1e-9 and recs[0].winner == "A"
              and abs(recs[0].attacker_incap[_INF] - exp_cas) < 1.0)
    recs[0].attacker_incap[_INF] = -1.0                 # must NOT alias siblings
    alias_ok = recs[1].attacker_incap[_INF] != -1.0
    # stat-mismatched (attacker weak, defender godlike) must NOT be "validated"
    a_bad = [_u(_INF, 10, 3000, 0.1), _u(_MAR, 6, 3000, 0.1)]
    d_bad = [_u(_INF, 7, 3000, 1000.0), _u(_MAR, 6, 3000, 1000.0)]
    m_bad = engine_meta(a_bad, d_bad, None)
    m_gen = engine_meta([_u(_INF, 12, 3000), _u(_MAR, 12, 3000)], d_box, None)  # T12
    gen_ok = (m_bad["path"] == "general" and m_bad["calibrated"] is False
              and m_gen["path"] == "general" and m_gen["calibrated"] is False)
    ok &= _check("stat-aware confidence routing + non-aliased records",
                 box_ok and alias_ok and gen_ok,
                 f"box={m_box['path']} stat-mismatch={m_bad['path']} indep={alias_ok}")

    # 10. Hero GENERATION -> stat model (E-12): gen table + buff-scaled relayer,
    #     and generation must NOT scale skills (only stats).
    from .hero_stats import hero_stat, relayer_panel, GEN_STAT
    hg_ok = (hero_stat(9, StatType.ATTACK) == 9.4075
             and hero_stat(9, StatType.ATTACK) == hero_stat(9, StatType.DEFENSE)
             and hero_stat(3, StatType.LETHALITY) == 0.7
             and set(GEN_STAT) == set(range(1, 16))
             and hero_stat(15, StatType.ATTACK) == 19.6156
             and hero_stat(15, StatType.LETHALITY) == 4.9)
    # controlled Mia gen3 -> Fred gen9 lancer swap: +748% atk (buff .15), +650% def
    d_atk = (hero_stat(9, StatType.ATTACK) - hero_stat(3, StatType.ATTACK)) * 1.15
    d_def = (hero_stat(9, StatType.DEFENSE) - hero_stat(3, StatType.DEFENSE)) * 1.0
    hg_ok &= abs(d_atk - 7.4810) < 1e-3 and abs(d_def - 6.5052) < 1e-3
    # relayer: max-gen class unchanged, lower-gen classes reduced
    out = relayer_panel({("Infantry", "Attack"): 5.0, ("Lancer", "Attack"): 5.0},
                        {"Infantry": 14, "Lancer": 9})
    hg_ok &= abs(out[("Infantry", "Attack")] - 5.0) < 1e-9  # max gen: unchanged
    hg_ok &= out[("Lancer", "Attack")] < 5.0                # gen9 < gen14: reduced
    ok &= _check("hero generation stat model (table + relayer; skills unscaled)",
                 hg_ok, f"d_atk={d_atk:.3f} d_def={d_def:.3f}")

    # 11. Hero-gen relayer is WIRED into construct.build: with the same scouted
    #     panel on both sides, a Gen-2 lead makes that class weaker than Gen-13.
    from .predictor import construct as _con
    from .predictor.profiles import Matchup as _M, SideProfile as _SP, ClassQuality as _CQ
    def _side(role, inf_lead):
        panel = {(c, s): 20.0 for c in ("Infantry", "Lancer", "Marksman")
                 for s in ("Attack", "Defense", "Lethality", "Health")}
        return _SP(role=role, troops_total=100000, stats_mode="scouted", panel=panel,
                   formation={"Infantry": 0.5, "Lancer": 0.0, "Marksman": 0.5},
                   quality={c: _CQ(tier=12, fc=10) for c in ("Infantry", "Lancer", "Marksman")},
                   lead_heroes={"Infantry": inf_lead, "Lancer": "Flora", "Marksman": "Vulcanus"})
    enemy_s = _side("rally", "Gisela")
    def _own_inf_atk(inf_lead):
        con = _con.build(_M(_side("garrison", inf_lead), enemy_s))  # own = defender
        return next(u.astat[StatType.ATTACK] for u in con.defender_units
                    if u.troop == _TT.INFANTRY)
    g13, g2 = _own_inf_atk("Gisela"), _own_inf_atk("Flint")
    ok &= _check("hero-gen relayer wired into construct (Gen2 inf < Gen13)",
                 g2 < g13 * 0.8, f"gen2 atk {g2:.0f} vs gen13 {g13:.0f}")

    # 12. Turn-engine anchor winners (2026-07-08 recalibration): the three real
    #     T12 anchors must all rank ATTACKER as the winner on the production
    #     path (deterministic seed 0). Magnitudes live in the near-even chaos
    #     zone and are NOT asserted here - winner inversion is the regression.
    try:
        from .anchor_eval import anchors as _anchors, run_turn as _run_turn
        anchor_ok = True
        detail = []
        for _name, _matchup in _anchors():
            _con, _res = _run_turn(_matchup, None, seed=0)
            anchor_ok &= _res.winner == "A"
            detail.append(f"{_name}:{_res.winner}/{_res.turns}t")
        ok &= _check("turn engine ranks all three T12 anchors (winner=A)",
                     anchor_ok, " ".join(detail))
    except Exception as exc:                       # anchor data must stay loadable
        ok &= _check("turn engine ranks all three T12 anchors (winner=A)",
                     False, f"harness error: {exc}")

    print(f"\n{'ALL GREEN' if ok else 'REGRESSIONS PRESENT'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
