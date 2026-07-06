"""Phase-3 back-test: run all 8 validated PvP reports through the
two-sided engine and compare outcome + casualty magnitudes to observed.

This is the REAL high-tier accuracy check (farm/beast regime was a
diagnostic proxy). First cut uses farm-calibrated BEST_PARAMS with a
single PvP rate scale; the r6/r8 sister pair is the calibration anchor.

Run:  py -m wos_sim.pvp_backtest [rate]
"""

import sys

from .assemble import assemble_battle
from .loader import load_skill_book
from .pvp_engine import simulate_pvp, units_from_side
from .reports import load_all_reports

WB = r"WoS battle simulator.xlsx"


def observed(side):
    return side.troops - side.survivors      # total incapacitated (removed)


def run_one(report, book, rate):
    a_side, d_side, board = assemble_battle(report, book)
    a_units = units_from_side(a_side)
    d_units = units_from_side(d_side)
    # attach DD/DT from the board (A=attacker, D=defender)
    for tag, units in (("A", a_units), ("D", d_units)):
        for u in units:
            u.dd = board.dd.get((tag, u.troop), 0.0)
            u.dt = board.dt.get((tag, u.troop), 0.0)
    res = simulate_pvp(a_units, d_units, {"rate": rate})
    return res


def main(rate=1.0):
    book = load_skill_book(WB)
    reports = load_all_reports()
    print(f"PvP back-test (rate={rate}) - {len(reports)} reports")
    print(f"{'report':<26} {'winner':>7} {'act':>4} | "
          f"{'A inc pred/obs':>20} | {'D inc pred/obs':>20}")
    for r in reports:
        res = run_one(r, book, rate)
        # actual winner: the side with survivors (or 'friendly' outcome)
        act = "A" if r.attacker.survivors > 0 else "D"
        if r.attacker.survivors > 0 and r.defender.survivors > 0:
            act = "both"
        a_pred = sum(res.a_incap.values())
        d_pred = sum(res.d_incap.values())
        a_obs = observed(r.attacker)
        d_obs = observed(r.defender)
        wflag = "OK" if res.winner == act else "MISS"
        print(f"{r.report_id[:26]:<26} {res.winner:>7} {act:>4} {wflag:<4}"
              f" {a_pred:>9,.0f}/{a_obs:>9,.0f} "
              f" {d_pred:>9,.0f}/{d_obs:>9,.0f}  T{res.turns}")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 1.0)
