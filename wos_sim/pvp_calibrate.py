"""Phase-3 step 1: calibrate the PvP coupling (rate + attacker/defender
asymmetry atk_adv) on the r6/r8 SISTER PAIR, then validate on the other 6.

r6/r8 are the cleanest anchor: same fortress, same sides, 17 min apart,
both attacker wins with the defender fully wiped and graded attacker
casualties. Fit 2 params (rate, atk_adv) to reproduce r6/r8 attacker
incapacitated + defender wipe; hold out r1-r5, r7.

Run:  py -m wos_sim.pvp_calibrate
"""

import math
from itertools import product

from .assemble import assemble_battle
from .loader import load_skill_book
from .pvp_engine import simulate_pvp, units_from_side
from .reports import load_all_reports

WB = r"WoS battle simulator.xlsx"


def _units(report, book):
    a_side, d_side, board = assemble_battle(report, book)
    a_units = units_from_side(a_side)
    d_units = units_from_side(d_side)
    for tag, units in (("A", a_units), ("D", d_units)):
        for u in units:
            u.dd = board.dd.get((tag, u.troop), 0.0)
            u.dt = board.dt.get((tag, u.troop), 0.0)
    return a_units, d_units


def incap(side):
    return side.troops - side.survivors


DEF_ED = 0.483   # frontage exponent transfers from the beast engine


def run(report, book, rate, def_k):
    a_units, d_units = _units(report, book)
    return simulate_pvp(a_units, d_units,
                        {"rate": rate, "def_k": def_k, "def_ed": DEF_ED})


def calib_loss(reports_by_id, book, rate, def_k):
    """Fit target on r6/r8: attacker incap matches + defender wiped +
    attacker wins."""
    err = 0.0
    for rid in ("report_006", "report_008"):
        r = reports_by_id[rid]
        res = run(r, book, rate, def_k)
        a_pred = sum(res.a_incap.values())
        d_pred = sum(res.d_incap.values())
        a_obs = incap(r.attacker)
        d_obs = incap(r.defender)         # = full troops (wiped)
        err += math.log(max(a_pred, 1) / max(a_obs, 1)) ** 2
        # defender must (near-)wipe
        if d_pred < d_obs - 0.5:
            err += 2.0 * math.log(max(d_pred, 1) / max(d_obs, 1)) ** 2
        # attacker must survive (win)
        a_surv = res.a_total0 - a_pred
        if a_surv <= 0:
            err += 9.0
    return err


def main():
    book = load_skill_book(WB)
    reports = load_all_reports()
    by_id = {r.report_id.split("_v")[0].replace("report_00", "report_00"): r
             for r in reports}
    by_id = {}
    for r in reports:
        # normalize key to report_00N
        key = "report_" + r.report_id.split("_")[1]
        by_id[key] = r

    # log-spaced 2D search over (rate, def_k); def_ed fixed at 0.483.
    rates = [10, 20, 40, 80, 160, 320, 640]
    defks = [1, 10, 30, 100, 300, 1000, 3000, 10000, 30000]
    best, berr = None, float("inf")
    for rate in rates:
        for def_k in defks:
            e = calib_loss(by_id, book, rate, def_k)
            if e < berr:
                best, berr = (rate, def_k), e
    rate, dk = best
    for _ in range(6):
        for dr in (0.8, 1.25):
            e = calib_loss(by_id, book, rate * dr, dk)
            if e < berr:
                rate, berr = rate * dr, e
        for dd in (0.8, 1.25):
            e = calib_loss(by_id, book, rate, dk * dd)
            if e < berr:
                dk, berr = dk * dd, e
    print(f"CALIBRATED on r6/r8: rate={rate:.2f} def_k={dk:.1f} "
          f"def_ed={DEF_ED} (loss {berr:.4f})\n")

    print(f"{'report':<24}{'eng':>5}{'act':>5}  {'A inc pred/obs':>24}"
          f"  {'D inc pred/obs':>24}  turns")
    hits = 0
    for r in reports:
        res = run(r, book, rate, dk)
        act = "A" if r.attacker.survivors > 0 else "D"
        if r.attacker.survivors > 0 and r.defender.survivors > 0:
            act = "both"
        a_pred, d_pred = sum(res.a_incap.values()), sum(res.d_incap.values())
        a_obs, d_obs = incap(r.attacker), incap(r.defender)
        ok = res.winner == act
        hits += ok
        held = "" if r.report_id.split("_")[1] in ("006", "008") else " (holdout)"
        print(f"{r.report_id[:24]:<24}{res.winner:>5}{act:>5} {'OK' if ok else 'X':>3}"
              f"  {a_pred:>11,.0f}/{a_obs:>11,.0f}"
              f"  {d_pred:>11,.0f}/{d_obs:>11,.0f}  T{res.turns}{held}")
    print(f"\nwinner accuracy: {hits}/{len(reports)} "
          f"({hits-2}/6 on holdouts)")


if __name__ == "__main__":
    main()
