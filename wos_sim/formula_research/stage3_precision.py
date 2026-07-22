"""Stage 3 precision probe: is the exact-band rejection fundamental (wrong
formula shape) or an artifact of over-tight recorded turn precision?

Two checks:
  (1) Do the 4 pure Infantry tier-mirror WINNER-rate bands share a common point?
      If empty, NO constant (perfectly tier-invariant) core can fit them -- the
      data is non-monotonic/noisy at the +-1..2 turn level.
  (2) Re-run the family gate with each row's turn band widened by +-delta turns
      (delta = 0,1,2,3).  A family that only survives at delta>=1 is being
      rejected by turn-precision, not by shape.  This is a labelled sensitivity
      probe, NOT an acceptance criterion (guardrail 2 keeps delta=0 as the gate).
"""

from __future__ import annotations

from fractions import Fraction

from wos_sim.formula_research.stage3_common import (
    load_constraints, winner_rows, true_1v1, Interval, WinnerRow,
)
from wos_sim.formula_research.stage3_families import (
    all_families, build_subsets, core_winner, core_loser, SUBSET_ORDER,
)


def band_intersection(rows, branch="plain"):
    lo = Fraction(0)
    hi = None
    lo_closed = True
    hi_closed = True
    for r in rows:
        iv = r.rate_plain if branch == "plain" else r.rate_nextatk
        if iv.lo > lo:
            lo, lo_closed = iv.lo, iv.lo_closed
        elif iv.lo == lo:
            lo_closed = lo_closed and iv.lo_closed
        if hi is None or iv.hi < hi:
            hi, hi_closed = iv.hi, iv.hi_closed
        elif iv.hi == hi:
            hi_closed = hi_closed and iv.hi_closed
    empty = (hi is not None) and (lo > hi or (lo == hi and not (lo_closed and hi_closed)))
    return lo, hi, lo_closed, hi_closed, empty


def widen(iv: Interval, rel: Fraction) -> Interval:
    """Widen an interval multiplicatively by (1 +- rel) on each side -- a proxy
    for +-delta turns (rate ~ 1/T so a delta-turn slack ~ rel = delta/T)."""
    return Interval(iv.lo * (1 - rel), iv.hi * (1 + rel), True, True)


def gate_widened(fam, rows, rel: Fraction, branch="plain"):
    lo, lo_closed = Fraction(0), False
    hi, hi_closed = None, False
    for r in rows:
        iv0 = r.rate_plain if branch == "plain" else r.rate_nextatk
        if iv0 is None:
            continue
        iv = widen(iv0, rel)
        core = core_winner(fam, r) * r.winner.ctr
        if core <= 0:
            return False
        c_lo, c_hi = iv.lo / core, iv.hi / core
        if c_lo > lo:
            lo = c_lo
        if hi is None or c_hi < hi:
            hi = c_hi
        if hi is not None and lo > hi:
            return False
    return True


def main():
    data = load_constraints()
    rows = true_1v1(winner_rows(data))
    subs = build_subsets(rows)

    print("=== (1) pure Infantry tier-mirror rate-band intersection ===")
    tier4 = [r for r in rows if r.ledger_line in (17, 28, 30, 34)]
    for r in tier4:
        iv = r.rate_plain
        print(f"  L{r.ledger_line} {r.matchup:<14} t_set={r.t_set} "
              f"rate=[{float(iv.lo):.7f},{float(iv.hi):.7f}] "
              f"{'[]' if iv.lo_closed else '()'}")
    lo, hi, lc, hc, empty = band_intersection(tier4)
    print(f"  intersection: lo={float(lo):.7f} hi={float(hi):.7f} "
          f"empty={empty}")
    print("  -> a perfectly tier-invariant (constant) core "
          f"{'CANNOT' if empty else 'could'} fit all four.\n")

    print("=== (2) family gate vs turn-precision slack (INF_CLEAN, plain) ===")
    fams = all_families()
    tier_reps = {  # representative rel slack ~ delta/T using T~264
        "delta=0": Fraction(0),
        "delta=1": Fraction(1, 264),
        "delta=2": Fraction(2, 264),
        "delta=3": Fraction(3, 264),
    }
    for target in ("INF_MIRROR", "INF_CLEAN", "INF_ALL", "FULL_CLEAN"):
        line = [f"{target:11}"]
        for label, rel in tier_reps.items():
            n = sum(1 for fam in fams
                    if gate_widened(fam, subs[target], rel))
            line.append(f"{label}:{n:>4}")
        print("  " + "  ".join(line))
    print("  (counts = # of 518 families passing the widened gate)\n")

    # If some family passes INF_CLEAN at delta=2, name a few -- they are the
    # shape candidates the precision is hiding.
    rel2 = Fraction(2, 264)
    winners = [fam for fam in fams if gate_widened(fam, subs["INF_CLEAN"], rel2)]
    print(f"=== families passing INF_CLEAN at delta~2 turns: {len(winners)} ===")
    for fam in winners[:25]:
        print(f"  {fam.name:26} {fam.desc}")


if __name__ == "__main__":
    main()
