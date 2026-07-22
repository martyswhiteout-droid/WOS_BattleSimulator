"""Stage 3 family elimination -- exact interval-intersection gate + subset localisation.

Method (non-fitting; guardrails 2 & 3):
  A candidate family proposes   rate = C * ctr_att * core(off; def)   where
  `core` is a fixed form with structural constants ENUMERATED over simple
  rationals (never regressed).  For fixed structure the only freedom is the
  global scale C.  ACCEPT iff a single C lands the predicted rate inside EVERY
  row's exact winner-rate interval at once -- i.e. the intersection
  `∩_i [lo_i/(ctr_i*core_i), hi_i/(ctr_i*core_i)]` is non-empty.  Membership ==
  exact blind prediction inside turns_lo..hi.  Loser one-sided bounds add
  `C * ctr_loser * core_loser_i < ub_i` (same C, reverse direction).

  Nested subsets localise the break:
    INF_MIRROR  same-class same-tier Infantry (tier-invariance + Exp4 isolation)
    INF_CLEAN   + clean Infantry cross-tier (vs-T2 ladder, T2/T3 vs T1, T1vT6)
    INF_ALL     + the non-monotonic T4/T6-vs-T1 suspect rows
    FULL_CLEAN  + cross-class (Lancer / Marksman), minus the L32/L69 hard conflict

Everything is exact `fractions.Fraction`; a float pre-screen only shortlists the
ratio-monomial grid before the exact test.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Optional

from wos_sim.formula_research.stage3_common import (
    load_constraints, winner_rows, true_1v1, WinnerRow,
)

HARD_CONFLICT = {32, 69}          # identical inputs, disjoint rate (see stage3_conflicts)
SUSPECT_VS_T1 = {31, 33}          # T4/T6 vs T1: non-monotonic in attack (32 already dropped)


# ---------------------------------------------------------------------------
# families
# ---------------------------------------------------------------------------

@dataclass
class Family:
    name: str
    desc: str
    core: Callable[..., Fraction]     # (oA,oL,oD,oH,dA,dL,dD,dH) -> Fraction>0
    params: dict


def _p(x: Fraction, n: int) -> Fraction:
    return Fraction(1) if n == 0 else x ** n


def ratio_monomials() -> list[Family]:
    fams = []
    for a in (1, 2):
        for b in (0, 1, 2):
            for f in (0, 1, 2):
                for g in (0, 1, 2):
                    for pp in (0, 1, 2):
                        for q in (0, 1, 2):
                            fams.append(Family(
                                name=f"rm_A{a}L{b}_dA{f}dL{g}dD{pp}dH{q}",
                                desc=(f"oA^{a}oL^{b} / "
                                      f"(dA^{f}dL^{g}dD^{pp}dH^{q})"),
                                core=(lambda oA, oL, oD, oH, dA, dL, dD, dH,
                                             a=a, b=b, f=f, g=g, pp=pp, q=q:
                                      _p(oA, a) * _p(oL, b)
                                      / (_p(dA, f) * _p(dL, g)
                                         * _p(dD, pp) * _p(dH, q))),
                                params=dict(a=a, b=b, f=f, g=g, p=pp, q=q),
                            ))
    return fams


def named_forms() -> list[Family]:
    fams = []

    def add(name, desc, fn, **params):
        fams.append(Family(name, desc, fn, params))

    add("lanchester_A_over_DpH", "oA / (dD+dH)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA / (dD + dH))
    add("AL_over_DpH", "oA*oL / (dD+dH)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA * oL / (dD + dH))
    add("sat_A_over_ApD", "oA/(oA+dD)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA / (oA + dD))
    add("sat_A_over_ApD_perH", "oA/((oA+dD)*dH)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA / ((oA + dD) * dH))
    add("mem_A_over_ApD_DpH", "oA/((oA+dD)*(dD+dH))  [memory candidate]",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA / ((oA + dD) * (dD + dH)))
    add("AL_over_ApD_DpH", "oA*oL/((oA+dD)*(dD+dH))",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA * oL / ((oA + dD) * (dD + dH)))
    add("ratio_off_AL", "oA*oL/(dA*dL)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA * oL / (dA * dL))
    add("ratio_off_AL_perH", "oA*oL/(dA*dL*dH)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA * oL / (dA * dL * dH))
    add("A_over_dA_perDpH", "(oA/dA)/(dD+dH)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: (oA / dA) / (dD + dH))
    add("penetration_AmD", "(oA*oL)/(dD*dH) capped-free difference note",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA * oL / (dD * dH))
    # attack-vs-defense ratio scaled by lethality-vs-health
    add("AoverD_LoverH", "(oA/dD)*(oL/dH)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: (oA / dD) * (oL / dH))
    add("AoverD_times_LH", "(oA/dD)*(oL/(oL+dH))",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: (oA / dD) * (oL / (oL + dH)))
    # canonical WoS-community attrition forms
    add("A2_over_ApD", "oA^2/(oA+dD)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA * oA / (oA + dD))
    add("A2_over_ApD_perH", "oA^2/((oA+dD)*dH)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA * oA / ((oA + dD) * dH))
    add("A2_over_ApD_perDpH", "oA^2/((oA+dD)*(dD+dH))",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA * oA / ((oA + dD) * (dD + dH)))
    add("AL_over_ApD_perH", "oA*oL/((oA+dD)*dH)",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA * oL / ((oA + dD) * dH))
    add("sat_ratio_AoverApD_LoverLpH",
        "(oA/(oA+dD))*(oL/(oL+dH))",
        lambda oA, oL, oD, oH, dA, dL, dD, dH:
        (oA / (oA + dD)) * (oL / (oL + dH)))
    add("A_1pL_over_D_1pH", "oA*(1+oL)/(dD*(1+dH))",
        lambda oA, oL, oD, oH, dA, dL, dD, dH:
        oA * (1 + oL) / (dD * (1 + dH)))
    add("Aratio_over_DpH", "(oA/dA)*(dA)/(dD+dH) placeholder relpow",
        lambda oA, oL, oD, oH, dA, dL, dD, dH: oA / (dD + dH))
    return fams


def two_factor_forms() -> list[Family]:
    """[attack-vs-defense factor] x [lethality-vs-health factor], gridded."""
    fams = []
    ad_factors = {
        "A/D": lambda oA, dD: oA / dD,
        "A/(A+D)": lambda oA, dD: oA / (oA + dD),
        "A2/(A+D)": lambda oA, dD: oA * oA / (oA + dD),
    }
    lh_factors = {
        "1": lambda oL, dH: Fraction(1),
        "L/H": lambda oL, dH: oL / dH,
        "L/(L+H)": lambda oL, dH: oL / (oL + dH),
        "(1+L)/H": lambda oL, dH: (1 + oL) / dH,
        "1/H": lambda oL, dH: Fraction(1) / dH,
    }
    for an, af in ad_factors.items():
        for ln_, lf in lh_factors.items():
            def mk(af, lf):
                return (lambda oA, oL, oD, oH, dA, dL, dD, dH:
                        af(oA, dD) * lf(oL, dH))
            fams.append(Family(f"tf_[{an}]x[{ln_}]",
                               f"[{an}] x [{ln_}]", mk(af, lf),
                               dict(ad=an, lh=ln_)))
    return fams


def difference_forms() -> list[Family]:
    fams = []
    for k in (Fraction(1, 8), Fraction(1, 4), Fraction(1, 2),
              Fraction(3, 4), Fraction(1)):
        for b in (0, 1):
            for q in (0, 1):
                def mk(k, b, q):
                    def fn(oA, oL, oD, oH, dA, dL, dD, dH):
                        base = oA - k * dD
                        if base <= 0:
                            return Fraction(1, 10 ** 12)
                        return base * _p(oL, b) / _p(dH, q)
                    return fn
                fams.append(Family(
                    f"diff_k{k}_L{b}_H{q}",
                    f"(oA-{k}*dD)_+ * oL^{b}/dH^{q}",
                    mk(k, b, q), dict(k=k, b=b, q=q)))
    return fams


def all_families() -> list[Family]:
    return (ratio_monomials() + named_forms() + difference_forms()
            + two_factor_forms())


# ---------------------------------------------------------------------------
# gate
# ---------------------------------------------------------------------------

def core_winner(fam, r):
    return fam.core(r.winner.A, r.winner.L, r.winner.D, r.winner.H,
                    r.loser.A, r.loser.L, r.loser.D, r.loser.H)


def core_loser(fam, r):
    return fam.core(r.loser.A, r.loser.L, r.loser.D, r.loser.H,
                    r.winner.A, r.winner.L, r.winner.D, r.winner.H)


@dataclass
class Gate:
    feasible: bool
    lo: Optional[Fraction]
    hi: Optional[Fraction]
    lo_closed: bool
    hi_closed: bool
    first_fail: Optional[str]
    n: int


def _empty(lo, hi, lo_closed, hi_closed):
    if hi is None:
        return False
    if lo > hi:
        return True
    if lo == hi and not (lo_closed and hi_closed):
        return True
    return False


def run_gate(fam, rows, branch="plain", use_loser_ub=True) -> Gate:
    lo, lo_closed = Fraction(0), False
    hi, hi_closed = None, False
    n = 0
    for r in rows:
        iv = r.rate_plain if branch == "plain" else r.rate_nextatk
        if iv is None:
            continue
        core = core_winner(fam, r) * r.winner.ctr
        if core <= 0:
            return Gate(False, lo, hi, lo_closed, hi_closed, r.name, n)
        n += 1
        c_lo, c_hi = iv.lo / core, iv.hi / core
        if c_lo > lo:
            lo, lo_closed = c_lo, iv.lo_closed
        elif c_lo == lo:
            lo_closed = lo_closed and iv.lo_closed
        if hi is None or c_hi < hi:
            hi, hi_closed = c_hi, iv.hi_closed
        elif c_hi == hi:
            hi_closed = hi_closed and iv.hi_closed
        if _empty(lo, hi, lo_closed, hi_closed):
            return Gate(False, lo, hi, lo_closed, hi_closed, r.name, n)
    if use_loser_ub:
        for r in rows:
            ub = r.loser_ub_plain if branch == "plain" else r.loser_ub_nextatk
            if not ub:
                continue
            cl = core_loser(fam, r) * r.loser.ctr
            if cl <= 0:
                continue
            c_hi = ub / cl
            if hi is None or c_hi < hi:
                hi, hi_closed = c_hi, False
            if _empty(lo, hi, lo_closed, hi_closed):
                return Gate(False, lo, hi, lo_closed, hi_closed,
                            r.name + " (loserUB)", n)
    return Gate(True, lo, hi, lo_closed, hi_closed, None, n)


# ---------------------------------------------------------------------------
# subsets
# ---------------------------------------------------------------------------

def build_subsets(rows: list[WinnerRow]) -> dict[str, list[WinnerRow]]:
    def is_inf(r):
        return r.winner.cls == "Infantry" and r.loser.cls == "Infantry"

    def mirror(r):
        return is_inf(r) and r.winner.tier == r.loser.tier

    clean = [r for r in rows if r.ledger_line not in HARD_CONFLICT]
    inf_mirror = [r for r in clean if mirror(r)]
    inf_clean = [r for r in clean if is_inf(r) and r.ledger_line not in SUSPECT_VS_T1]
    inf_all = [r for r in clean if is_inf(r)]
    full_clean = clean
    return {
        "INF_MIRROR": inf_mirror,
        "INF_CLEAN": inf_clean,
        "INF_ALL": inf_all,
        "FULL_CLEAN": full_clean,
    }


SUBSET_ORDER = ["INF_MIRROR", "INF_CLEAN", "INF_ALL", "FULL_CLEAN"]


def largest_surviving(fam, subsets, branch) -> tuple[str, Gate]:
    best = ("(none)", None)
    for name in SUBSET_ORDER:
        g = run_gate(fam, subsets[name], branch=branch)
        if g.feasible:
            best = (name, g)
        else:
            break
    return best


def main():
    data = load_constraints()
    rows = true_1v1(winner_rows(data))
    subs = build_subsets(rows)
    print("subset sizes:", {k: len(v) for k, v in subs.items()})
    fams = all_families()
    print(f"families: {len(fams)}\n")

    # headline: anything survive FULL_CLEAN or INF_ALL or INF_CLEAN?
    for target in ("FULL_CLEAN", "INF_ALL", "INF_CLEAN"):
        hits = []
        for fam in fams:
            for br in ("plain", "nextatk"):
                g = run_gate(fam, subs[target], branch=br)
                if g.feasible:
                    hits.append((fam, br, g))
        print(f"=== survivors on {target}: {len(hits)} ===")
        for fam, br, g in hits[:40]:
            print(f"  [{br}] {fam.name:26} C in "
                  f"[{float(g.lo):.6g},{float(g.hi):.6g}]  {fam.desc}")
        print()

    # localisation: for the physically-motivated named forms + a few monomials,
    # show the largest subset each survives (plain branch)
    print("=== largest surviving subset per family (plain branch) ===")
    named = named_forms() + difference_forms()
    for fam in named:
        name, g = largest_surviving(fam, subs, "plain")
        cstr = (f"C=[{float(g.lo):.5g},{float(g.hi):.5g}]" if g else "-")
        print(f"  {name:12} {cstr:28} {fam.name:22} {fam.desc}")


if __name__ == "__main__":
    main()
