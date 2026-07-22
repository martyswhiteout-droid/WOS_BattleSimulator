"""Stage 3 -- dedicated test of the DIFFERENCE LAW (Martin's leading hypothesis).

    rate = c * (A_att - k*D_def + K) * L^Lpow / HP,   HP in {H_def, D_def+H_def}

Because tier adds ~+1 to every Infantry stat, a stat-DIFFERENCE is ~tier-
invariant in mirrors, so this family is NOT killed by the mirror the way pure
monomials are -- it deserves an explicit solve-then-blind-predict test.

Method (guardrail 2: SOLVE from a minimal subset, then blind-predict exactly):
  With HP=H and Lpow=0, define  y = rate*H  (the emitted rate_x_H column).
  Then  y = c*A - (c*k)*D + (c*K)  is LINEAR in three unknowns (c, ck, cK).
  Solve them EXACTLY from 3 chosen rows' band-midpoints, recover k=ck/c and
  K=cK/c, then BLIND-predict y for every other clean row and test membership in
  that row's exact [rate_lo*H, rate_hi*H] band.  Observed outcomes enter only as
  the 3 solve rows (legitimate, like Stage 2's implied_*), never into the
  predictions being tested.
"""

from __future__ import annotations

import json
import os
from fractions import Fraction

from wos_sim.formula_research.stage3_common import (
    load_constraints, winner_rows, true_1v1,
)
from wos_sim.formula_research.stage3_families import build_subsets

HERE = os.path.dirname(os.path.abspath(__file__))


def solve3(rows3, hp, lpow):
    """Solve y = c*A - ck*D + cK from 3 rows (band midpoints). Exact rationals.
    Returns (c, ck, cK) or None if singular."""
    M = []
    rhs = []
    for r in rows3:
        A = r.winner.A * r.winner.ctr          # fold counter into the linear A term
        D = r.loser.D
        H = r.loser.H
        hpv = H if hp == "H" else (D + H)
        L = r.winner.L
        iv = r.rate_plain
        ymid = (iv.lo + iv.hi) / 2 * hpv / (L ** lpow)
        M.append([A, -D, Fraction(1)])
        rhs.append(ymid)
    # 3x3 exact solve (Cramer)
    def det3(m):
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    D0 = det3(M)
    if D0 == 0:
        return None
    sol = []
    for col in range(3):
        Mc = [row[:] for row in M]
        for i in range(3):
            Mc[i][col] = rhs[i]
        sol.append(det3(Mc) / D0)
    return tuple(sol)  # (c, ck, cK)


def blind_test(rows, c, ck, cK, hp, lpow):
    npass = 0
    table = []
    for r in rows:
        A = r.winner.A * r.winner.ctr
        D = r.loser.D
        H = r.loser.H
        hpv = H if hp == "H" else (D + H)
        L = r.winner.L
        iv = r.rate_plain
        y_pred = c * A - ck * D + cK          # predicted rate*HP / (L^0); scale back
        rate_pred = y_pred * (L ** lpow) / hpv
        ok = iv.contains(rate_pred)
        npass += ok
        table.append({
            "ledger_line": r.ledger_line, "matchup": r.matchup,
            "obs_lo": float(iv.lo), "obs_hi": float(iv.hi),
            "pred": float(rate_pred),
            "rel_err_mid": float(rate_pred) / ((float(iv.lo)+float(iv.hi))/2) - 1,
            "pass": ok,
        })
    return npass, table


def main():
    data = load_constraints()
    rows = true_1v1(winner_rows(data))
    subs = build_subsets(rows)
    by = {r.ledger_line: r for r in rows}

    # solve rows: two Infantry mirrors (T1, T6) + one cross-tier (T3 vs T1) --
    # spans the difference axis; all clean, ctr=1.
    solve_lines = [17, 34, 29]
    results = {"family": "difference law c*(A - k*D + K)*L^Lpow / HP",
               "solve_rows": solve_lines,
               "note": "solved from 3 clean Infantry rows' band midpoints, "
                       "then blind-predicted every clean row against exact bands.",
               "variants": []}

    print("DIFFERENCE-LAW solve-then-blind-predict (Martin's hypothesis)\n")
    for hp in ("H", "DpH"):
        for lpow in (0, 1):
            rows3 = [by[l] for l in solve_lines]
            sol = solve3(rows3, hp, lpow)
            if sol is None:
                continue
            c, ck, cK = sol
            k = ck / c if c != 0 else None
            K = cK / c if c != 0 else None
            for target in ("INF_CLEAN", "FULL_CLEAN"):
                npass, table = blind_test(subs[target], c, ck, cK, hp, lpow)
                nrows = len(subs[target])
                results["variants"].append({
                    "HP": hp, "Lpow": lpow, "target": target,
                    "c": float(c), "k": float(k) if k is not None else None,
                    "K": float(K) if K is not None else None,
                    "n_pass": npass, "n_rows": nrows,
                    "predicted_vs_observed": table,
                })
                print(f"  HP={hp:3} L^{lpow}  {target:11}: "
                      f"k={float(k):+.3f} K={float(K):+.3f}  "
                      f"pass {npass}/{nrows}")
        print()

    with open(os.path.join(HERE, "stage3_difflaw.json"), "w",
              encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    print("wrote stage3_difflaw.json")


if __name__ == "__main__":
    main()
