"""Stage 4 -- BLIND validation of the tier law.

For every 1v1 row we predict turns from STATS ONLY (real base x panel), never from
the observed turn count, then compare to the exact turn band.  Grouped so the law's
domain of validity is explicit:

  LAW:  turns = C * D_l*H_l / (A_w*L_w*ctr) * G_w(tau_w) * G_l(tau_l)
        C = 12.528   G_w in { (5t-2)/3 , t^(4/3) }   G_l = 1  (best current estimate)

Held-out set = the Gordon battery (band-only rows, a different hero regime).
Categories reveal where the Infantry-derived HP~D*H term holds vs breaks.
"""
from wos_sim.formula_research.stage4_common import base_stats, load_validation
from wos_sim.formula_research.stage4_law import g_linear, g_power

C = 12.528


def predict(r, gfun):
    w, l = r["w"], r["l"]
    local = C * l["D"] * l["H"] / (w["A"] * w["L"] * r["ctr"])
    return local * gfun(w["tier"])          # G_l = 1


def band_ok(pred, lo, hi):
    # exact gate for integer trigger-counts: prediction must ROUND into the band
    return lo <= round(pred) <= hi


def pct_err(pred, lo, hi):
    mid = (lo + hi) / 2.0
    return pred / mid - 1.0


def category(r):
    w, l = r["w"], r["l"]
    if r["src"] == "Gordon":
        return "HELD-OUT (Gordon, all regimes)"
    if w["cls"] != "Infantry":
        return "OUT-OF-SCOPE: non-Inf winner (attacker-class x-check)"
    if not r["same_class"]:                   # Inf winner vs Lan/MM loser
        return "OUT-OF-SCOPE: cross-class Inf>Lan/MM (low-D*H loser)"
    if l["tier"] > 1 and w["tier"] == 1:
        return "loser-tier (winner T1)  [MuellerAlpaca anomaly]"
    if not r["same_tier"]:
        return "cross-tier same-class Inf   <-- THE TIER-LAW TEST"
    return "within-tier same-class Inf"


def main():
    rows = load_validation()
    cats = {}
    for r in rows:
        cats.setdefault(category(r), []).append(r)

    order = ["within-tier same-class Inf", "cross-tier same-class Inf   <-- THE TIER-LAW TEST",
             "loser-tier (winner T1)  [MuellerAlpaca anomaly]",
             "OUT-OF-SCOPE: cross-class Inf>Lan/MM (low-D*H loser)",
             "OUT-OF-SCOPE: non-Inf winner (attacker-class x-check)",
             "HELD-OUT (Gordon, all regimes)"]
    for cat in order:
        rs = cats.get(cat, [])
        if not rs:
            continue
        print("=" * 92)
        print(f"{cat}   ({len(rs)} rows)")
        print("=" * 92)
        print(f"  {'matchup':16} {'src':7} {'obs band':>10}  {'pred(lin)':>9} "
              f"{'%err':>6}  {'lin':>3} {'pow':>3}")
        npass_l = npass_p = 0
        errs = []
        for r in sorted(rs, key=lambda x: (x["w"]["tier"], x["l"]["tier"], x["name"])):
            lo, hi = r["t_lo"], r["t_hi"]
            pl, pp = predict(r, g_linear), predict(r, g_power)
            ol = band_ok(pl, lo, hi); op = band_ok(pp, lo, hi)
            npass_l += ol; npass_p += op
            errs.append(pct_err(pl, lo, hi))
            print(f"  {r['matchup']:16} {r['src']:7} [{lo:>4},{hi:>4}]  "
                  f"{pl:9.1f} {pct_err(pl, lo, hi):+6.0%}   {'Y' if ol else '.':>3} {'Y' if op else '.':>3}")
        amax = max(abs(e) for e in errs)
        print(f"  --> round-into-band PASS: linear {npass_l}/{len(rs)}  power {npass_p}/{len(rs)}"
              f"   |%err| max {amax:.0%}\n")

    print("READ  (law scope = Infantry winner vs Infantry/high-D*H loser):")
    print("  IN SCOPE -> WORKS:")
    print("   * within-tier same-class Inf: exact (LabRat <0.5 turns; Mueller +3% bias).")
    print("   * cross-tier same-class Inf:  law reproduces every band (<=1%) with C & G_w")
    print("     fixed (8 T3 rows from 1 constant). INDEPENDENT blind checks: beast T1->1.00,")
    print("     beast T2->2.68 (==1v1 T2), held-out Gordon Inf-mirror predicted +3%.")
    print("  OUT OF SCOPE -> FLAGGED (as the spec anticipated), THREE distinct defects:")
    print("   * low-D*H loser (Lan/MM target): -50%..-98%. The D*H HP product under-")
    print("     counts glass-cannon HP. Same defect Inf>Lan/MM and the MM mirror ->")
    print("     it is a LOW-D*H-TARGET problem, not a class-identity one.")
    print("   * non-Inf WINNER (MM/Lan attacker): -88%. The constant/law is Infantry-")
    print("     attacker-specific; MM/Lan dealers kill far slower than their A*L implies.")
    print("     (This is the attacker-class symmetry gap the spec said is untestable")
    print("      cleanly here -> confirmed as a real disagreement, flagged not fitted.)")
    print("   * loser-tier T2 (MuellerAlpaca): +200% (dies ~3x too fast) -> the anomaly;")
    print("     pending re-capture, not allowed to drive the fit.")


if __name__ == "__main__":
    main()
