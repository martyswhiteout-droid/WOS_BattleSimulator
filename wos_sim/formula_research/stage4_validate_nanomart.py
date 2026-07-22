"""Stage 4 preliminary validation: apply the Gatot-derived per-unit law to the
NanoMart Stage-2 constraint table.  Re-runnable; nothing fitted.

Law (from the Gatot single-target 1v1 ladders, Lab Rat/):
    turns = C * D_loser * H_loser / (A_winner * L_winner * ctr),   C = 12.54 (T1 Inf)
i.e. damage/attack ~ A*L/D, HP pool ~ H  ->  the A*L/(D*H) monomial.

Three honest groups:
  1. T1 Inf->Inf : direct test (base is model-independent at T1).
  2. cross-tier  : NanoMart stored ADDITIVE base stats (base_Tn = n); the Gatot
                   T3 rows show base is MULTIPLICATIVE (~x1.20/tier). We show the
                   additive stats fail monotonically, and recomputing with a
                   uniform multiplicative factor f snaps mirrors to tier-invariant
                   and T2/T3 to within a few %.
  3. cross-class : recorded here as NOT-yet-modelled (needs class base stats).
"""
import json, os
from fractions import Fraction as Fr

HERE = os.path.dirname(os.path.abspath(__file__))
C = Fr(1254, 100)


def load():
    return json.load(open(os.path.join(HERE, "stage2_constraints.json"), encoding="utf-8"))


def true_1v1(d):
    for b in d["battles"]:
        c = b.get("constraints", {})
        if c.get("type") != "exact_1v1":
            continue
        w = c.get("winner_side")
        if not w:
            continue
        l = "def" if w == "att" else "att"
        W, L = b["sides"][w], b["sides"][l]
        if W["count"] != 1 or L["count"] != 1 or not b["turns"]["t_set"]:
            continue
        yield b, W, L


def pred(Aw, Lw, ctr, Dl, Hl):
    return float(C * Dl * Hl / (Aw * Lw * ctr))


def main():
    d = load()
    print("LAW:  turns = 12.54 * D_l * H_l / (A_w * L_w * ctr)\n")
    print("=== Group 1: T1 Infantry -> Infantry (direct; model-independent) ===")
    errs = []
    for b, W, L in true_1v1(d):
        if not (W["cls"] == "Infantry" == L["cls"] and W["tier"] == 1 == L["tier"]):
            continue
        p = pred(Fr(W["A_eff"]), Fr(W["L"]), Fr(W["counter_mult"]), Fr(L["D_eff"]), Fr(L["H"]))
        obs = sum(b["turns"]["t_set"]) / len(b["turns"]["t_set"])
        errs.append(p / obs - 1)
        print(f"  L{b['ledger_line']:>2} {b['name'][-28:]:28} obs~{obs:5.0f} pred {p:6.1f}  {p/obs-1:+.1%}")
    print(f"  --> {len(errs)} rows, error range {min(errs):+.1%}..{max(errs):+.1%} "
          f"(att-wins ~+1%, def-wins ~-3.5%: small symmetric-regime asymmetry)\n")

    print("=== Group 2: cross-tier Inf — ADDITIVE (NanoMart) vs MULTIPLICATIVE f=1.20 ===")
    f = 1.20; HF = 1.128
    tiers = [("T2vT1", 2, 1, 176), ("T3vT1", 3, 1, 126), ("T4vT1", 4, 1, 96),
             ("T5vT1", 5, 1, 80), ("T6vT1", 6, 1, 96),
             ("T2mirror", 2, 2, 266), ("T3mirror", 3, 3, 266), ("T6mirror", 6, 6, 264),
             ("T3vT2", 3, 2, 188), ("T4vT2", 4, 2, 144), ("T5vT2", 5, 2, 120), ("T6vT2", 6, 2, 102)]
    print(f"  {'matchup':10} {'obs':>4} {'add':>7} {'mult':>7}  (add=NanoMart additive base, mult=x1.20/tier)")
    for lab, wt, lt, obs in tiers:
        add = 12.54 * ((lt + 3) * (lt + 5)) / ((wt * HF) * wt)                  # additive base_Tn=n
        mul = 12.54 * (4 * f**(lt - 1) * 6 * f**(lt - 1)) / ((f**(wt - 1) * HF) * f**(wt - 1))
        print(f"  {lab:10} {obs:>4} {add:7.1f} {mul:7.1f}   add {add/obs-1:+.0%} | mult {mul/obs-1:+.0%}")
    print("  --> mirrors -> tier-invariant ~266 (any f); T2/T3 within ~5%; T5/T6 drift")
    print("      (needs the REAL base-tier stat table to pin f exactly / test if f varies by tier;")
    print("       note T5vT1 obs is the L32/L69 conflict, T6vT1=96 is the flagged mis-record)\n")

    print("=== Group 3: cross-class (Inf/Lan/MM) — NOT yet modelled ===")
    print("  Formula (C, base) is Infantry-specific; cross-class needs class base stats +")
    print("  counter treatment. Also several MM rows are Vulcanus-contaminated. Deferred.")


if __name__ == "__main__":
    main()
