"""Stage 3 tests: gate correctness on synthetic cases + real-data verdict locks.

Run:  py -m pytest wos_sim/formula_research/test_stage3.py -q
"""

from fractions import Fraction

from wos_sim.formula_research.stage3_common import (
    load_constraints, winner_rows, true_1v1, Side, Interval, WinnerRow,
)
from wos_sim.formula_research.stage3_families import (
    all_families, build_subsets, run_gate, Family, _p,
)
from wos_sim.formula_research import stage3_run


def _row(name, A_w, D_l, H_l, rate_lo, rate_hi, ctr=Fraction(1)):
    # Side(role, count, cls, tier, A, D, L, H, ctr)
    w = Side("att", 1, "Infantry", 1, Fraction(A_w), Fraction(1),
             Fraction(1), Fraction(6), ctr)
    l = Side("def", 1, "Infantry", 1, Fraction(1), Fraction(D_l),
             Fraction(1), Fraction(H_l), Fraction(1))
    iv = Interval(Fraction(rate_lo), Fraction(rate_hi), True, False)
    return WinnerRow(name, 0, "exact_1v1", "1v1", "T1", "att", None,
                     w, l, 1, 1, iv, iv, None, None, (0,))


def test_gate_accepts_exact_construction():
    # core = oA / (dD*dH); build rows that satisfy rate = C*core with C=2.
    fam = Family("t", "oA/(dD*dH)",
                 lambda oA, oL, oD, oH, dA, dL, dD, dH: oA / (dD * dH), {})
    C = Fraction(2)
    rows = []
    for i, (A, D, H) in enumerate([(3, 4, 6), (5, 2, 3), (1, 5, 5)]):
        core = Fraction(A) / (Fraction(D) * Fraction(H))
        r = C * core
        rows.append(_row(f"r{i}", A, D, H,
                         r - Fraction(1, 10**6), r + Fraction(1, 10**6)))
    g = run_gate(fam, rows, use_loser_ub=False)
    assert g.feasible
    assert g.lo <= C <= g.hi


def test_gate_rejects_incompatible():
    fam = Family("t", "oA/(dD*dH)",
                 lambda oA, oL, oD, oH, dA, dL, dD, dH: oA / (dD * dH), {})
    # two rows demanding wildly different C for the same core value
    rows = [
        _row("a", 3, 4, 6, Fraction(1, 100), Fraction(101, 10000)),
        _row("b", 3, 4, 6, Fraction(5, 100), Fraction(51, 1000)),
    ]
    g = run_gate(fam, rows, use_loser_ub=False)
    assert not g.feasible


def test_loader_row_count():
    rows = true_1v1(winner_rows(load_constraints()))
    assert len(rows) == 37


def test_no_family_survives_full_clean():
    data = load_constraints()
    subs = build_subsets(true_1v1(winner_rows(data)))
    fams = all_families()
    for target in ("INF_MIRROR", "INF_CLEAN", "INF_ALL", "FULL_CLEAN"):
        surv = [f for f in fams
                for br in ("plain", "nextatk")
                if run_gate(f, subs[target], branch=br).feasible]
        assert surv == [], f"unexpected survivor on {target}: {surv[:3]}"


def test_count_law_sqrtN_attacker_inside_bands():
    cl = stage3_run.count_law(load_constraints())
    att = {r["N"]: r for r in cl["att_stacking"]}
    for N in (2, 3):
        assert att[N]["sqrtN_inside_band"], f"att g({N}) not sqrtN"


def test_hard_conflict_L32_L69_detected():
    rows = true_1v1(winner_rows(load_constraints()))
    conf = stage3_run.conflicts(rows)
    assert "hard_identical_input_conflict" in conf
    c = conf["hard_identical_input_conflict"]
    # disjoint bands
    assert c["L32_rate"][1] < c["L69_rate"][0]
