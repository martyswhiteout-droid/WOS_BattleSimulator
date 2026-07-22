"""Stage 5 -- the FROZEN per-unit deterministic law (K-table formulation).

    turns(dealer kills target) =
        K(dealer_cls, target_cls)
        * (D_t * H_t) / (A_d * L_d)          # effective stats, real base x (1+panel)
        * G_w(tier_dealer) * G_l(tier_target)
        / sqrt(N_dealer)                      # count law (Stage 3)

    * K absorbs class passives/counters -- NO separate ctr factor.
    * G_w measured T1..T6 (Infantry dealer); T7+ extrapolated by the cube-root
      structural interpolant (A_base*L_base)^(2/3) anchored at T6 -- flagged.
    * G_l measured T1..T10 (Infantry target, v5 ladder).
    * HP = D*H exact (v4); own-side Health of the DEALER is irrelevant.
    * Global battle cap = 1500 rounds.
    * predict_turns_1v1 returns CONTINUOUS time; deaths land on integer turns,
      so a point prediction is ceil(t) (on short battles this matters: the
      FarSeer set is 15/17 ceil-EXACT where naive %err read as a -4% offset).

Provenance: every frozen constant below is recomputed from the Type-1 corpus by
`derive_from_corpus()`;  run  `py -m wos_sim.formula_research.stage5_law`  to
re-derive and print frozen-vs-derived drift. Constants were frozen 2026-07-14
from TYPE1_CORPUS.json (220 rows) -- see STAGE5_REPORT.md for the audit table.

Scope / Type-2 boundary:
  * MEASURED cells: Inf->Inf/Lan/MM (Gatot instrument, clean), MM->Inf, MM->MM,
    Lan->MM (Gordon battery, band rows, different hero regime).
  * PREDICTED cells (factorization K ~ f(dealer)*g(target), +-10%): Lan->Inf,
    Lan->Lan, MM->Lan. Blind-checked against NanoMart (Vulcanus regime,
    directional) in stage5_validate.py -- never exact-fit.
  * G_w is Infantry-dealer-measured. Using it for Lan/MM dealers is a
    HYPOTHESIS (the count-threshold rows suggest extra mechanics -- Gatot S2
    shield -- see STAGE5_REPORT.md; those rows are out of core scope).
"""
import argparse
import json
import math
import os
import statistics as st

from wos_sim.formula_research.stage4_common import base_stats

CAP_TURNS = 1500

# --------------------------------------------------------------------------- #
#  FROZEN TABLES (derived from the corpus -- see derive_from_corpus below)
# --------------------------------------------------------------------------- #
CLASSES = ("Infantry", "Lancer", "Marksman")

#: measured K cells: (dealer, target) -> K   [medians; sources in STAGE5_REPORT]
K_MEASURED = {
    ("Infantry", "Infantry"): 12.524,   # 39 clean within-tier rows (+-3%)
    ("Infantry", "Lancer"):   22.43,    # 9 T1-target rows (v4 + FarSeer)
    ("Infantry", "Marksman"): 73.16,    # 10 rows (v4 + FarSeer)
    ("Marksman", "Infantry"): 91.16,    # Gordon battery, band [72,74] x2
    ("Marksman", "Marksman"): 566.66,   # Gordon battery, band [18,19]
    ("Lancer",   "Marksman"): 499.50,   # Gordon battery, band [24,26]
}

#: factorization K ~ f(dealer) * g(target); g == the Infantry-dealer row
K_G = {c: K_MEASURED[("Infantry", c)] for c in CLASSES}
K_F = {
    "Infantry": 1.0,
    # f(Lan) from the single measured Lan cell; f(MM) = median of its two cells
    "Lancer":   K_MEASURED[("Lancer", "Marksman")] / K_G["Marksman"],     # 6.83
    "Marksman": st.median([K_MEASURED[("Marksman", "Infantry")] / K_G["Infantry"],
                           K_MEASURED[("Marksman", "Marksman")] / K_G["Marksman"]]),  # 7.51
}


def K(dealer_cls, target_cls):
    """Measured cell if we have it, else the factorization prediction."""
    cell = K_MEASURED.get((dealer_cls, target_cls))
    if cell is not None:
        return cell, "measured"
    return K_F[dealer_cls] * K_G[target_cls], "factorized"


#: winner(dealer)-tier damping, MEASURED T1..T6 (Infantry dealer)
G_W = {1: 1.0, 2: 2.680, 3: 4.323, 4: 5.884, 5: 9.791, 6: 10.889}

#: loser(target)-tier factor -- CLASS-SPECIFIC.
#: Infantry: MEASURED T1..T10 (v5 ladder). Lancer: T2 measured from the two
#: corrected T2-Lancer rows (different attacker panels, both imply 0.654
#: exactly -- a clean 2-point cell). Marksman: unmeasured (T1=1 by K-cell
#: definition); other tiers fall back to the Infantry table, FLAGGED.
G_L = {1: 1.0, 2: 0.996, 3: 0.904, 4: 0.795, 5: 0.770,
       6: 0.748, 7: 0.742, 8: 0.744, 9: 0.757, 10: 0.777}
G_L_BY_CLS = {
    "Infantry": G_L,
    "Lancer": {1: 1.0, 2: 0.654},
    "Marksman": {1: 1.0},
}


def g_w(tier, cls="Infantry"):
    """Measured table T1-T6; T7+ = cube-root interpolant anchored at T6
    (EXTRAPOLATION -- no winner-tier data beyond T6 exists yet)."""
    if tier in G_W:
        return G_W[tier]
    a6, _, l6, _ = base_stats(cls, 6)
    at, _, lt, _ = base_stats(cls, tier)
    return G_W[6] * ((at * lt) / (a6 * l6)) ** (2.0 / 3.0)


def g_l(tier, cls="Infantry"):
    """(value, measured: bool). Unmeasured class/tier cells fall back to the
    Infantry table -- callers surface the flag, never hide it."""
    table = G_L_BY_CLS.get(cls, {})
    if tier in table:
        return table[tier], True
    if tier in G_L:
        return G_L[tier], False
    raise ValueError(f"G_l unmeasured for tier {tier}")


# --------------------------------------------------------------------------- #
#  the frozen predictor
# --------------------------------------------------------------------------- #
def eff_stats(cls, tier, fc=None, panel=None):
    """Effective (A, D, L, H) = REAL base x (1 + panel_pct/100)."""
    A0, D0, L0, H0 = base_stats(cls, tier, fc or 1)
    p = panel or {}

    def m(key):
        v = p.get(key)
        return 1.0 + (float(v) / 100.0 if v is not None else 0.0)

    return {"A": A0 * m("Attack"), "D": D0 * m("Defense"),
            "L": L0 * m("Lethality"), "H": H0 * m("Health")}


def predict_turns_1v1(dealer, target, *, dealer_count=1, offense_mult=1.0):
    """Turns for `dealer` to kill ONE `target` unit.

    dealer/target: {"cls", "tier", "fc" (opt), "panel" (opt) | "eff" (opt)}.
    offense_mult folds hero factors on the dealer's damage (e.g. Seo-yoon x1.15,
    enemy Vulcanus S1 x0.96) -- the caller owns hero semantics.
    Returns (turns, meta) with meta noting factorized cells / extrapolated G_w.
    """
    ed = dealer.get("eff") or eff_stats(dealer["cls"], dealer["tier"],
                                        dealer.get("fc"), dealer.get("panel"))
    et = target.get("eff") or eff_stats(target["cls"], target["tier"],
                                        target.get("fc"), target.get("panel"))
    k, k_kind = K(dealer["cls"], target["cls"])
    gw = g_w(dealer["tier"], dealer["cls"])
    gl, gl_measured = g_l(target["tier"], target["cls"])
    t = (k * (et["D"] * et["H"]) / (ed["A"] * ed["L"] * offense_mult)
         * gw * gl / math.sqrt(max(dealer_count, 1)))
    meta = {"K": k, "K_kind": k_kind, "G_w": gw, "G_l": gl,
            "G_w_extrapolated": dealer["tier"] not in G_W,
            "G_l_measured": gl_measured,
            "dealer_eff": ed, "target_eff": et}
    return t, meta


def kill_rate(dealer, target, *, dealer_count=1, offense_mult=1.0):
    """Damage rate in units of 'target HP pools per turn' -- rates from several
    dealer stacks onto one target ADD (simultaneous fire)."""
    t, meta = predict_turns_1v1(dealer, target, dealer_count=dealer_count,
                                offense_mult=offense_mult)
    return (1.0 / t if t > 0 else float("inf")), meta


# --------------------------------------------------------------------------- #
#  provenance: re-derive every frozen table from the corpus
# --------------------------------------------------------------------------- #
def _corpus_rows():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.abspath(os.path.join(
        here, "..", "data", "experiments", "_corpus", "TYPE1_CORPUS.json"))
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["rows"]


def _wl(r):
    w = r["outcome"]["winner"]
    if w == "attacker":
        return r["attacker"], r["defender"]
    if w == "defender":
        return r["defender"], r["attacker"]
    return None, None


def _single(s):
    return s["classes"][0] if s and len(s["classes"]) == 1 else None


def _turns_mid(r):
    o = r["outcome"]
    if o["turns"] is not None:
        return float(o["turns"])
    tr = o.get("turns_range")
    return (tr[0] + tr[1]) / 2.0 if tr else None


def _k_raw(r):
    w, l = _wl(r)
    uw, ul = _single(w), _single(l)
    t = _turns_mid(r)
    if not (uw and ul and t):
        return None
    ew, el = uw["eff"], ul["eff"]
    return t * ew["A"] * ew["L"] / (el["D"] * el["H"])


def _is_1v1(r, det, exact=True):
    w, l = _wl(r)
    if not w:
        return False
    uw, ul = _single(w), _single(l)
    if not (uw and ul and uw["count"] == 1 and ul["count"] == 1):
        return False
    if r["determinism"] not in det:
        return False
    t = r["outcome"]["turns"]
    if exact:
        return t is not None and t < CAP_TURNS
    return _turns_mid(r) is not None and not r["outcome"].get("cap_hit")


def derive_from_corpus(rows=None):
    """Recompute every frozen table; return {name: derived} for drift check."""
    rows = rows or _corpus_rows()
    out = {"K": {}, "G_W": {}, "G_L": {}}
    anchor, k_cells = [], {}
    ladder = {}                                   # FarSeer G_w series
    for r in rows:
        if _is_1v1(r, ("clean",)):
            w, l = _wl(r)
            uw, ul = _single(w), _single(l)
            k = _k_raw(r)
            if uw["cls"] == ul["cls"] == "Infantry" and uw["tier"] == ul["tier"]:
                anchor.append(k)
            # K cells: T1 dealer vs T1 target only (G_w = G_l = 1)
            if uw["tier"] == 1 and ul["tier"] == 1 and (uw["cls"], ul["cls"]) != (
                    "Infantry", "Infantry"):
                k_cells.setdefault((uw["cls"], ul["cls"]), []).append(k)
            # G_w ladders: FarSeer fixed T1 loser, Infantry winner tier varies
            if (r["folder"] == "FarSeerGatot_v3" and uw["cls"] == "Infantry"
                    and ul["tier"] == 1):
                ladder.setdefault((ul["cls"], uw["tier"]), []).append(k)
            # LabRat T3>T1 same-class
            if (r["folder"] == "Lab Rat" and uw["cls"] == ul["cls"] == "Infantry"
                    and uw["tier"] == 3 and ul["tier"] == 1):
                ladder.setdefault(("Infantry", 3), []).append(k)
        # Gordon battery cells (band rows)
        if r["determinism"] == "gordon_deterministic" and _is_1v1(
                r, ("gordon_deterministic",), exact=False):
            w, l = _wl(r)
            uw, ul = _single(w), _single(l)
            if (uw["cls"], ul["cls"]) != ("Infantry", "Infantry"):
                k_cells.setdefault((uw["cls"], ul["cls"]), []).append(_k_raw(r))
    C = st.median(anchor)
    out["K"][("Infantry", "Infantry")] = C
    out["anchor_n"] = len(anchor)
    out["anchor_spread"] = (min(anchor), max(anchor))
    for cell, ks in k_cells.items():
        out["K"][cell] = st.median(ks)
    # beasts (per-kill) extend G_w
    beast_g = {}
    for r in rows:
        if r["folder"] != "Lab Rat" or "Beast" not in r["id"]:
            continue
        w, l = _wl(r)
        uw = _single(w)
        if not uw or not r["outcome"]["turns"] or r["outcome"]["turns"] >= CAP_TURNS:
            continue
        n_losers = sum(c["count"] for c in l["classes"])
        if w["casualties"]["kills"] != n_losers:
            continue
        ul = l["classes"][0]
        q = (r["outcome"]["turns"] / n_losers * uw["eff"]["A"] * uw["eff"]["L"]
             / (ul["eff"]["D"] * ul["eff"]["H"]))
        beast_g.setdefault(uw["tier"], []).append(q / C)
    # G_w per tier = median over: Lan-series ratio, MM-series ratio, Inf 1v1/C, beast
    gw_evidence = {}
    for (lcls, tw), ks in ladder.items():
        base_q = st.median(ladder.get((lcls, 1), [None]) or [None])
        ref = base_q if (lcls != "Infantry" and base_q) else C
        if ref:
            gw_evidence.setdefault(tw, []).append(st.median(ks) / ref)
    for tw, gs in beast_g.items():
        gw_evidence.setdefault(tw, []).extend(gs)
    for tw, gs in sorted(gw_evidence.items()):
        out["G_W"][tw] = st.median(gs)
    # G_l ladder (v5 + the flagged T7 anchor-set row) + the Lancer T2 cell
    gl_lan = {}
    for r in rows:
        if r["folder"] not in ("MuellerAlpaca_Gatot_v5", "MuellerAlpaca"):
            continue
        if not _is_1v1(r, ("clean",)):
            continue
        w, l = _wl(r)
        uw, ul = _single(w), _single(l)
        if uw["cls"] != "Infantry" or uw["tier"] != 1 or ul["tier"] <= 1:
            continue
        if ul["cls"] == "Infantry":
            out["G_L"].setdefault(ul["tier"], []).append(_k_raw(r) / C)
        elif ul["cls"] == "Lancer":
            gl_lan.setdefault(ul["tier"], []).append(
                _k_raw(r) / out["K"][("Infantry", "Lancer")])
    out["G_L"] = {t: st.median(v) for t, v in out["G_L"].items()}
    out["G_L"][1] = 1.0
    out["G_L_LANCER"] = {t: st.median(v) for t, v in gl_lan.items()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit derived tables as JSON")
    args = ap.parse_args()
    d = derive_from_corpus()
    if args.json:
        print(json.dumps({"K": {f"{a}->{b}": v for (a, b), v in d["K"].items()},
                          "G_W": d["G_W"], "G_L": d["G_L"]}, indent=1))
        return
    print("FROZEN vs DERIVED (from TYPE1_CORPUS.json)\n")
    print(f"K(Inf->Inf) anchor: n={d['anchor_n']}  "
          f"spread {d['anchor_spread'][0]:.3f}..{d['anchor_spread'][1]:.3f}")
    print(f"\n  {'cell':24} {'frozen':>9} {'derived':>9} {'drift':>7}")
    for cell in sorted(set(K_MEASURED) | set(d["K"])):
        f = K_MEASURED.get(cell)
        v = d["K"].get(cell)
        drift = (v / f - 1) if (f and v) else None
        print(f"  {cell[0][:3]+'->'+cell[1][:3]:24} "
              f"{f if f is not None else float('nan'):9.2f} "
              f"{v if v is not None else float('nan'):9.2f} "
              f"{f'{drift:+.1%}' if drift is not None else '':>7}")
    for name, frozen, derived in (("G_w", G_W, d["G_W"]), ("G_l(Inf)", G_L, d["G_L"]),
                                  ("G_l(Lan)", G_L_BY_CLS["Lancer"], d["G_L_LANCER"])):
        print(f"\n  {name}:  tier  frozen  derived  drift")
        for t in sorted(set(frozen) | set(derived)):
            f, v = frozen.get(t), derived.get(t)
            drift = (v / f - 1) if (f and v) else None
            print(f"    T{t:<3}  {f if f is not None else float('nan'):6.3f}  "
                  f"{v if v is not None else float('nan'):7.3f}  "
                  f"{f'{drift:+.1%}' if drift is not None else ''}")
    print("\n  factorization: f(dealer) = {Inf 1, Lan %.2f, MM %.2f}" % (
        K_F["Lancer"], K_F["Marksman"]))
    for dealer, target in (("Lancer", "Infantry"), ("Lancer", "Lancer"),
                           ("Marksman", "Lancer")):
        k, kind = K(dealer, target)
        print(f"    predicted K({dealer[:3]}->{target[:3]}) = {k:.1f}  [{kind}]")


if __name__ == "__main__":
    main()
