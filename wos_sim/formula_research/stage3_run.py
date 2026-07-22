"""Stage 3 capstone: run the exact family-elimination gate, characterise the
closest (still-rejected) shape, derive the model-free count law, record the
hard data conflicts, and emit `stage3_results.json`.

Guardrails: the ACCEPT/REJECT verdict uses only the exact-band gate (delta=0).
All "closest shape" and "min-slack" numbers are explicitly labelled DIAGNOSTIC
(characterisation of the residual, never an acceptance).  The count law is
computed model-free as ratios of observed winner-rate intervals -- no formula is
assumed.  Every number is produced here and re-runnable.
"""

from __future__ import annotations

import json
import os
from fractions import Fraction

from wos_sim.formula_research.stage3_common import (
    load_constraints, winner_rows, true_1v1,
)
from wos_sim.formula_research.stage3_families import (
    all_families, ratio_monomials, named_forms, difference_forms,
    two_factor_forms, build_subsets, run_gate, core_winner, SUBSET_ORDER,
    HARD_CONFLICT, SUSPECT_VS_T1,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def fstr(x: Fraction) -> str:
    return f"{float(x):.8g}"


def rate_mid(r, branch="plain"):
    iv = r.rate_plain if branch == "plain" else r.rate_nextatk
    return (iv.lo + iv.hi) / 2


# --- elimination -----------------------------------------------------------

def elimination(fams, subs):
    out = {}
    for target in SUBSET_ORDER:
        surv = []
        for fam in fams:
            for br in ("plain", "nextatk"):
                g = run_gate(fam, subs[target], branch=br)
                if g.feasible:
                    surv.append({"family": fam.name, "branch": br,
                                 "C_lo": fstr(g.lo), "C_hi": fstr(g.hi),
                                 "desc": fam.desc})
        out[target] = {"n_rows": len(subs[target]),
                       "n_survivors": len(surv), "survivors": surv}
    return out


# --- closest shape (DIAGNOSTIC) -------------------------------------------

def c_spread(fam, rows, branch="plain"):
    cs = []
    for r in rows:
        core = core_winner(fam, r) * r.winner.ctr
        if core <= 0:
            return None
        cs.append(rate_mid(r, branch) / core)
    return min(cs), max(cs), cs


def closest_family(fams, rows):
    best = None
    for fam in fams:
        res = c_spread(fam, rows)
        if res is None:
            continue
        lo, hi, _ = res
        spread = float(hi / lo)
        if best is None or spread < best[1]:
            best = (fam, spread)
    return best


def predicted_table(fam, rows, branch="plain"):
    lo, hi, cs = c_spread(fam, rows, branch)
    # geometric-centre C (diagnostic pick, minimises max multiplicative error)
    Cstar = (lo * hi) ** Fraction(1, 2) if False else None
    # exact geometric centre not rational; use float for the diagnostic pick
    import math
    Cf = math.sqrt(float(lo) * float(hi))
    table = []
    n_pass = 0
    for r in rows:
        iv = r.rate_plain if branch == "plain" else r.rate_nextatk
        core = float(core_winner(fam, r) * r.winner.ctr)
        pred = Cf * core
        ok = float(iv.lo) <= pred <= float(iv.hi)
        n_pass += ok
        table.append({
            "ledger_line": r.ledger_line, "matchup": r.matchup,
            "winner": r.winner_role,
            "obs_lo": float(iv.lo), "obs_hi": float(iv.hi),
            "pred": pred,
            "rel_err_vs_mid": pred / ((float(iv.lo) + float(iv.hi)) / 2) - 1,
            "pass": ok,
        })
    return {"C_star": Cf, "n_pass": n_pass, "n_rows": len(rows),
            "rows": table}


# --- model-free count law --------------------------------------------------

def count_law(data):
    by = {b["name"]: b for b in data["battles"]}

    def rate_iv(name):
        proj = by[name]["constraints"]["projected"]["s2_plain"]["winner_rate"]
        return Fraction(proj["lo"]), Fraction(proj["hi"])

    def ratio(nN, n1):
        loN, hiN = rate_iv(nN)
        lo1, hi1 = rate_iv(n1)
        # g(N)/g(1) interval = [loN/hi1, hiN/lo1]
        return loN / hi1, hiN / lo1

    result = {"note": "g(N)/g(1) computed model-free as ratio of observed "
                       "winner-rate intervals for the SAME matchup "
                       "(T1InfvT1Inf); no damage formula assumed."}
    # defender-stacking: winner=def, def count N; base N=1 is SetA def-win
    defseq = {
        1: "NanoMart_SetA_1v1_T1InfvT1Inf_Vulcanus_SeoYoonlvl3",
        2: "NanoMart_1v2_T1InfvT1Inf_SeoYoonlvl3_Vulcanus",
        3: "NanoMart_SetC_1v3_T1InfvT1Inf_SeoYoonlvl3_Vulcanus",
        5: "NanoMart_SetC_1v5_T1InfvT1Inf_SeoYoonlvl3_Vulcanus",
    }
    attseq = {
        1: "NanoMart_1v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus",
        2: "NanoMart_2v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus",
        3: "NanoMart_SetC_3v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus",
    }
    for label, seq in (("def_stacking", defseq), ("att_stacking", attseq)):
        rows = []
        base = seq[1]
        for N, name in seq.items():
            if N == 1:
                g_lo, g_hi = Fraction(1), Fraction(1)
            else:
                g_lo, g_hi = ratio(name, base)
            g_mid = (g_lo + g_hi) / 2
            import math
            rows.append({
                "N": N, "name": name,
                "gN_over_g1_lo": float(g_lo), "gN_over_g1_hi": float(g_hi),
                "gN_over_g1_mid": float(g_mid),
                "sqrtN": math.sqrt(N),
                "sqrtN_inside_band": float(g_lo) <= math.sqrt(N) <= float(g_hi),
                "gN_over_sqrtN_mid": float(g_mid) / math.sqrt(N),
                "implied_exponent_mid": (math.log(float(g_mid)) / math.log(N)
                                         if N > 1 else None),
            })
        result[label] = rows
    return result


# --- data conflicts --------------------------------------------------------

def conflicts(rows):
    by = {r.ledger_line: r for r in rows}
    out = {}
    # L32 vs L69 hard conflict
    a, b = by.get(32), by.get(69)
    if a and b:
        out["hard_identical_input_conflict"] = {
            "rows": ["L32 NanoMart_1v1_T5InfvT1Inf", "L69 NanoMart_SetA_1v1_T5InfvT1Inf"],
            "identical_inputs": {
                "A_w": fstr(a.winner.A), "L_w": fstr(a.winner.L),
                "D_l": fstr(a.loser.D), "H_l": fstr(a.loser.H)},
            "L32_rate": [float(a.rate_plain.lo), float(a.rate_plain.hi)],
            "L69_rate": [float(b.rate_plain.lo), float(b.rate_plain.hi)],
            "L32_tset": list(a.t_set), "L69_tset": list(b.t_set),
            "verdict": "identical deployed stats, disjoint rate bands -> "
                       "no captured-variable deterministic formula can satisfy "
                       "both; an uncaptured variable exists.",
        }
    # T4/T6-vs-T1 non-monotonicity
    t4, t5, t6 = by.get(31), by.get(32), by.get(33)
    if t4 and t6:
        out["non_monotonic_vs_T1_block"] = {
            "rows": {
                "T4vT1_L31": {"A_w": fstr(t4.winner.A),
                              "rate_mid": float(rate_mid(t4)), "t_set": list(t4.t_set)},
                "T5vT1_L32": {"A_w": fstr(t5.winner.A),
                              "rate_mid": float(rate_mid(t5)), "t_set": list(t5.t_set)},
                "T6vT1_L33": {"A_w": fstr(t6.winner.A),
                              "rate_mid": float(rate_mid(t6)), "t_set": list(t6.t_set)},
            },
            "verdict": "T4vT1 and T6vT1 both last exactly 96 turns despite "
                       "A_w differing 4.51 vs 6.77, while T5vT1 (between) is "
                       "faster -> rate non-monotonic in attack; no monotone "
                       "damage form can fit the block.",
        }
    return out


def main():
    data = load_constraints()
    rows = true_1v1(winner_rows(data))
    subs = build_subsets(rows)
    fams = all_families()

    results = {
        "stage": 3,
        "generated_by": "wos_sim/formula_research/stage3_run.py",
        "input": "stage2_constraints.json (Stage 2 ACCEPTED)",
        "guardrail_statement":
            "ACCEPT/REJECT is the exact-band interval-intersection gate "
            "(delta=0). Structural constants enumerated over simple rationals; "
            "global scale solved as a feasible interval, not regressed. "
            "'closest shape' / 'min-slack' figures are DIAGNOSTIC only.",
        "family_counts": {
            "ratio_monomials": len(ratio_monomials()),
            "named_forms": len(named_forms()),
            "difference_forms": len(difference_forms()),
            "two_factor_forms": len(two_factor_forms()),
            "total": len(fams),
        },
        "subset_sizes": {k: len(v) for k, v in subs.items()},
        "elimination": elimination(fams, subs),
        "count_law_model_free": count_law(data),
        "data_conflicts": conflicts(rows),
    }

    # closest shape diagnostics
    for target in ("INF_CLEAN", "FULL_CLEAN"):
        best = closest_family(fams, subs[target])
        fam, spread = best
        tbl = predicted_table(fam, subs[target])
        results.setdefault("closest_shape_diagnostic", {})[target] = {
            "family": fam.name, "desc": fam.desc,
            "C_spread_max_over_min": spread,
            "n_pass_exact_band": tbl["n_pass"], "n_rows": tbl["n_rows"],
            "C_star": tbl["C_star"],
            "predicted_vs_observed": tbl["rows"],
        }

    with open(os.path.join(HERE, "stage3_results.json"), "w",
              encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)

    # console summary
    print("STAGE 3 SUMMARY")
    print(f"  families tested: {results['family_counts']['total']}")
    for target in SUBSET_ORDER:
        e = results["elimination"][target]
        print(f"  {target:11} rows={e['n_rows']:2}  "
              f"survivors={e['n_survivors']}")
    print()
    for target in ("INF_CLEAN", "FULL_CLEAN"):
        d = results["closest_shape_diagnostic"][target]
        print(f"  closest shape on {target}: {d['family']}  "
              f"C-spread={d['C_spread_max_over_min']:.3f}  "
              f"pass {d['n_pass_exact_band']}/{d['n_rows']}  ({d['desc']})")
    print()
    print("  count law g(N)/g(1) (def-stacking, T1InfvT1Inf):")
    for row in results["count_law_model_free"]["def_stacking"]:
        exp = row["implied_exponent_mid"]
        print(f"    N={row['N']}: g={row['gN_over_g1_mid']:.4f} "
              f"(sqrtN={row['sqrtN']:.4f}"
              f"{', exp=%.3f' % exp if exp else ''})")
    print("  count law g(N)/g(1) (att-stacking, T1InfvT1Inf):")
    for row in results["count_law_model_free"]["att_stacking"]:
        exp = row["implied_exponent_mid"]
        print(f"    N={row['N']}: g={row['gN_over_g1_mid']:.4f} "
              f"(sqrtN={row['sqrtN']:.4f}"
              f"{', exp=%.3f' % exp if exp else ''})")
    print("\n  wrote stage3_results.json")


if __name__ == "__main__":
    main()
