"""Stage 3 pre-flight: find hard contradictions in the corpus.

A deterministic formula predicts winner-rate from the captured inputs
(A_w, L_w, D_l, H_l, ctr_w, g(N_w)) ONLY.  If two rows share identical inputs
but have non-overlapping winner-rate intervals, NO such formula can satisfy both
-- an uncaptured variable exists.  This script enumerates those groups exactly
(rational arithmetic) so family elimination can quarantine them honestly rather
than best-fit around them (guardrail 2 & 6).
"""

from __future__ import annotations

from fractions import Fraction

from wos_sim.formula_research.stage3_common import (
    load_constraints, winner_rows, Interval,
)


def input_key(r) -> tuple:
    """The full set of variables a captured-variable formula may use."""
    return (
        str(r.winner.A), str(r.winner.L), str(r.loser.D), str(r.loser.H),
        str(r.winner.ctr), r.N_w, r.N_l,
    )


def overlap(a: Interval, b: Interval) -> bool:
    lo = max(a.lo, b.lo)
    hi = min(a.hi, b.hi)
    if lo < hi:
        return True
    if lo == hi:
        # touching endpoints overlap only if both inclusive there
        a_hi_here = (a.hi == lo and a.hi_closed) or (a.lo == lo and a.lo_closed)
        b_hi_here = (b.hi == lo and b.hi_closed) or (b.lo == lo and b.lo_closed)
        return a_hi_here and b_hi_here
    return False


def main():
    data = load_constraints()
    rows = [r for r in winner_rows(data) if r.rate_plain is not None]
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault(input_key(r), []).append(r)

    print("=== identical-input groups (>1 row) ===")
    conflicts = []
    for key, grp in groups.items():
        if len(grp) < 2:
            continue
        names = [g.name.split("Nano")[-1] for g in grp]
        # do ALL pairwise intervals share a common point?
        common_lo = max(g.rate_plain.lo for g in grp)
        common_hi = min(g.rate_plain.hi for g in grp)
        ok = common_lo < common_hi or (
            common_lo == common_hi
            and all(g.rate_plain.contains(common_lo) for g in grp)
        )
        tag = "CONSISTENT" if ok else "*** CONFLICT ***"
        print(f"\n[{tag}] A_w={float(Fraction(key[0])):.5f} L_w={key[1]} "
              f"D_l={float(Fraction(key[2])):.4g} H_l={key[3]} "
              f"ctr={key[4]} g=({key[5]},{key[6]})")
        for g in grp:
            rp = g.rate_plain
            print(f"    L{g.ledger_line:<3} {g.name}")
            print(f"         rate=[{float(rp.lo):.7f},{float(rp.hi):.7f}] "
                  f"t_set={g.t_set}")
        if not ok:
            conflicts.append((key, grp))

    print(f"\n=== {len(conflicts)} hard-conflict group(s) "
          f"(identical inputs, disjoint rate) ===")
    for key, grp in conflicts:
        print("  " + " vs ".join(f"L{g.ledger_line}" for g in grp))


if __name__ == "__main__":
    main()
