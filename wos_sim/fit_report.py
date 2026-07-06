"""Calibrate the hypothesis engine against a real report and compare.

Run:  py -m wos_sim.fit_report
Sweeps the kernel constant (and troop exponent) so simulated casualties
match report_001, then prints sim-vs-actual structure.
"""

from .assemble import assemble_battle
from .battle import BattleParams, simulate_battle
from .loader import load_skill_book
from .models import TroopType
from .reports import load_all_reports

report = load_all_reports()[0]
book = load_skill_book()

actual_atk = report.attacker.class_breakdown()
actual_def = report.defender.class_breakdown()
atk_incap_actual = sum(b["incapacitated"] for b in actual_atk.values())
def_incap_actual = sum(b["incapacitated"] for b in actual_def.values())
print(f"ACTUAL: attacker incapacitated {atk_incap_actual:,} (wiped), "
      f"defender incapacitated {def_incap_actual:,}; ~28-29 turns\n")


def run(k: float, exponent: float, max_turns: int = 60):
    attacker, defender, _ = assemble_battle(report, book)
    params = BattleParams(model="ratio", kernel_k=k, troop_exponent=exponent,
                          share_killed=0.0, share_severe=0.35, share_light=0.65,
                          max_turns=max_turns)
    a, d, log = simulate_battle(attacker, defender, params)
    turns = log[-1].turn if log else 0
    a_incap = sum(c.count for c in []) # placeholder
    a_incap = sum((cl.severely_injured + cl.lightly_injured + cl.killed)
                  for cl in a.classes.values())
    d_incap = sum((cl.severely_injured + cl.lightly_injured + cl.killed)
                  for cl in d.classes.values())
    return a, d, turns, a_incap, d_incap


print("=== sweep: kernel_k x troop_exponent ===")
best, best_err = None, 1e18
for exponent in (0.5, 0.75, 1.0):
    for k in (0.001, 0.01, 0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000, 3000, 10000):
        a, d, turns, a_incap, d_incap = run(k, exponent)
        wiped = a_incap >= 0.999 * atk_incap_actual
        err = (abs(a_incap - atk_incap_actual) / atk_incap_actual
               + abs(d_incap - def_incap_actual) / def_incap_actual
               + (abs(turns - 28.5) / 28.5 if wiped else 2.0))
        if err < best_err:
            best, best_err = (k, exponent), err
        print(f"  k={k:>8} e={exponent:<5} turns={turns:>3} "
              f"atk_incap={a_incap:>12,.0f} def_incap={d_incap:>12,.0f} err={err:.3f}")

k, exponent = best
print(f"\n=== best: k={k}, exponent={exponent} ===")
a, d, turns, a_incap, d_incap = run(k, exponent)
print(f"battle length: {turns} turns (actual ~28-29)")
print(f"{'':22}{'sim':>14}{'actual':>14}")
for side_state, breakdown, label in ((a, actual_atk, "ATTACKER"), (d, actual_def, "DEFENDER")):
    print(label)
    for t in TroopType:
        cl = side_state.classes[t]
        sim_incap = cl.severely_injured + cl.lightly_injured + cl.killed
        print(f"  {t:<12} incap {sim_incap:>14,.0f}{breakdown[t]['incapacitated']:>14,}")
        print(f"  {t:<12} alive {cl.alive:>14,.0f}"
              f"{breakdown[t]['total'] - breakdown[t]['incapacitated']:>14,}")
