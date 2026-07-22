"""Stage 6 -- CLASS-KEYED tables with provenance (+ the stage6 predictor shim).

Consolidates the E-NIF battery (2026-07-17) into the frozen law:

    turns(dealer kills target) =
        K(dealer_cls, target_cls)
        * (D_t * H_t) / (A_d * L_d)            # effective stats, corpus 'eff'
        * G_w(dealer_cls, tier_d) * G_l(target_cls, tier_t)
        / sqrt(N_dealer)                        # count law AWAY from the Gatot
                                                # shield (see stage6_gatot)

Changes vs stage5_law (which stays frozen, untouched, for eval-5 repro):
  * G_w is CLASS-KEYED: Infantry measured T1-T6 (unchanged); Lancer measured
    T1/T3/T6 from E-NIF3 (R08-R10), T2/T4/T5 geometric-interpolated, FLAGGED;
    Marksman = 1.0 with a stated [1, 1.17] band (E-NIF2-redo; ENTANGLED with
    the Gatot-kit suppression -- see stage6_gatot).
  * G_l gains the measured MARKSMAN column (E-NIF2 R05-R07: steep), keyed like
    the Infantry/Lancer ones; unmeasured cells interpolate (within a measured
    class column) or fall back to the Infantry column, always FLAGGED.
  * K cells updated: Lan->MM frozen from the full-panel E-NIF3 R08 row
    (488.71; Gordon 499.50 kept as second source, +2.2%); MM->Inf frozen from
    the alliance-corrected tight-band ENIF1b R02 row (90.11; LabRat Gordon
    pair 91.16 and the R03 sqrt(2)-fold 88.71 recorded); MM->MM unchanged.
  * Every cell carries {value, status, sources, band?}:
        status in {measured, interpolated, bounded, extrapolated,
                   factorized, fallback_infantry}.
  * `stage6_tables.json` is emitted as the single source of truth the
    predictor seam loads (py -m wos_sim.formula_research.stage6_tables --emit).

Interpolated cells are COMPUTED at import time from the measured rungs
(geometric in tier) -- nothing hand-rounded can drift.

Provenance discipline: every frozen constant is recomputed from
TYPE1_CORPUS.json by derive_from_corpus(); the no-flag run prints
frozen-vs-derived (0.0% at freeze time, 2026-07-17, corpus row_count=232).

Base-stat sources (HOUSEKEEPING NOTE, Stage-6 task 4): the deterministic path
uses corpus `eff` stats, which build_corpus computes from
docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json (FC troops) or the
in-file captures (ordinary troops).  `wos_sim/troop_catalog.py` (wostools.net
snapshot) DIVERGES from that table and feeds the LEGACY engine only -- never
use it here, and never silently edit it.
"""
import argparse
import json
import math
import os
import statistics as st

from wos_sim.formula_research.stage4_common import base_stats

CAP_TURNS = 1500
CLASSES = ("Infantry", "Lancer", "Marksman")

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.abspath(os.path.join(
    HERE, "..", "data", "experiments", "_corpus", "TYPE1_CORPUS.json"))
TABLES_JSON = os.path.join(HERE, "stage6_tables.json")


# --------------------------------------------------------------------------- #
#  FROZEN TABLES (2026-07-17, corpus row_count=232; run with no flag to
#  re-derive and see drift). cell = {value, status, sources} [+ band, note]
# --------------------------------------------------------------------------- #
K_CELLS = {
    ("Infantry", "Infantry"): {
        "value": 12.524, "status": "measured",
        "sources": ["39 clean within-tier rows (stage5, +-3%)"]},
    ("Infantry", "Lancer"): {
        "value": 22.43, "status": "measured",
        "sources": ["9 T1-target rows (v4 + FarSeer, stage5)"]},
    ("Infantry", "Marksman"): {
        "value": 73.16, "status": "measured",
        "sources": ["10 rows (v4 + FarSeer, stage5)",
                    "ENIF1b_R01/R04 replicate at 77.15 (+5.5%)",
                    "ENIF2_R05 replicates at 76.84 (+5.0%)"]},
    ("Marksman", "Infantry"): {
        "value": 90.11, "status": "measured",
        "sources": ["ENIF1b_R02 (90.11, band [66,67]) -- FROZEN (alliance-"
                    "corrected, tightest band)",
                    "LabRat Gordon pair 91.16 x2 (band [72,74])",
                    "ENIF1b_R03 1v2 /sqrt(2) 88.71 (band [52,53])"],
        "band": [88.71, 91.16],
        "note": "vs GORDON-led Infantry; vs GATOT-led Infantry the kit "
                "suppression applies instead (stage6_gatot). The R03 "
                "sqrt(2)-fold band [87.9,89.6] misses the LabRat band "
                "[89.9,92.4] by 0.4 (-1.6%) -- instrument spread, recorded."},
    ("Marksman", "Marksman"): {
        "value": 566.66, "status": "measured",
        "sources": ["Gordon battery, band [18,19] (stage5)",
                    "confirmed at +1072% panels 07-14 (panels multiply in full)"]},
    ("Lancer", "Marksman"): {
        "value": 488.71, "status": "measured",
        "sources": ["ENIF3_R08 full-panel exact-band [21,23] (488.71) -- FROZEN",
                    "Gordon battery band [24,26] (499.50, +2.2%)"],
        "band": [466.5, 510.9],
        "note": "frozen from the tighter full-panel E-NIF3 row; Gordon kept "
                "as the second source"},
    # ---- STAGE 6.6 (2026-07-19): edge-implied cell, stage6_hero_state.py ---- #
    ("Lancer", "Infantry"): {
        "value": 90.38, "status": "edge_implied",
        "sources": ["40/41 T6-FC1-Lancer count edge vs Mueller-Gatot with the "
                    "INDEPENDENT B_Mueller=201.95 (21/22 MM edge): "
                    "K*G_w^Lan(6) = AL*40.5/B = 146.87 -> K = 90.38",
                    "win-turn solve (41x kill @286t) -> 91.04 (band)",
                    "204/205 B_Alpaca knife-edge self-consistency at 10x scale "
                    "(cap check + 575-kill forward check, stage6_hero_state D3)"],
        "band": [90.38, 91.04],
        "note": "SHIELD-MODEL-CONDITIONAL (measured through the budget gate, "
                "not on a clean kill clock). The T3-ordinary 66/67 edge vs "
                "B_FarSeer implies 111.29 (+23%) -- ordinary-vs-FC1 base / "
                "tier-transfer OPEN; the old factorization f*g = 83.66 is "
                "SUPERSEDED at T6 but carried as a branch tag (B_Alpaca "
                "inherits it). Gate verdicts at tiers other than 6/3 must be "
                "invariant across [83.66, 111.29] or the seam abstains."},
}

#: factorization for the 3 never-measured cells: K ~ f(dealer) * g(target),
#: g = the Infantry-dealer row. +-10-15% estimator (stage5 verdict), FLAGGED.
#: The Gatot count-threshold battles independently imply
#: K(Lan->Inf)*G_w^Lan(6) ~ 152.6 => K(Lan->Inf) ~ 94 (+12% vs factorized) --
#: shield-model-conditional, recorded by stage6_gatot, NOT frozen here.
K_G = {c: K_CELLS[("Infantry", c)]["value"] for c in CLASSES}
K_F = {
    "Infantry": 1.0,
    "Lancer":   K_CELLS[("Lancer", "Marksman")]["value"] / K_G["Marksman"],   # 6.680
    "Marksman": st.median([K_CELLS[("Marksman", "Infantry")]["value"] / K_G["Infantry"],
                           K_CELLS[("Marksman", "Marksman")]["value"] / K_G["Marksman"]]),  # 7.472
}


def _geo_fill(cells):
    """Fill integer-tier gaps between measured rungs geometrically (monotone),
    status='interpolated'. Returns a new dict; ratio of the last measured
    segment is exposed for flagged extrapolation."""
    tiers = sorted(cells)
    out = {t: dict(c) for t, c in cells.items()}
    for lo, hi in zip(tiers, tiers[1:]):
        span = hi - lo
        if span <= 1:
            continue
        ratio = (cells[hi]["value"] / cells[lo]["value"]) ** (1.0 / span)
        for t in range(lo + 1, hi):
            out[t] = {"value": cells[lo]["value"] * ratio ** (t - lo),
                      "status": "interpolated",
                      "sources": [f"geometric T{lo}..T{hi}"]}
    last_ratio = None
    if len(tiers) >= 2:
        lo, hi = tiers[-2], tiers[-1]
        last_ratio = (cells[hi]["value"] / cells[lo]["value"]) ** (1.0 / (hi - lo))
    return out, last_ratio


#: dealer tier damping, CLASS-KEYED (measured rungs; gaps geo-filled below)
_G_W_MEASURED = {
    "Infantry": {  # measured T1-T6 (stage4/5: FarSeer-v3 x2 + beasts + Gatot)
        1: {"value": 1.0,    "status": "measured", "sources": ["definition"]},
        2: {"value": 2.680,  "status": "measured", "sources": ["FarSeer-v3 + beasts"]},
        3: {"value": 4.323,  "status": "measured", "sources": ["FarSeer-v3 + beasts + Gatot T3 set"]},
        4: {"value": 5.884,  "status": "measured", "sources": ["FarSeer-v3 + beasts"]},
        5: {"value": 9.791,  "status": "measured", "sources": ["FarSeer-v3"]},
        6: {"value": 10.889, "status": "measured", "sources": ["FarSeer-v3 x2 + beasts (<=6% spread)"]},
        # -- STAGE 6.6 (2026-07-19): T7 measured, stage6_hero_state.py D1 -- #
        7: {"value": 14.285, "status": "measured",
            "sources": ["T7 discriminator MuellerAlpaca_1v1_T7InfvFC1T1Inf_"
                        "..._AlpacaFC1T1Vulcanus_20260718_235302, t in [75,77], "
                        "Vulcanus S1 x0.96 the only fold"],
            "band": [14.097, 14.473],
            "note": "MEASURED ON THE MuellerAlpaca/Vulcanus-target instrument. "
                    "The same-instrument T6 twin (..._161706, t in [90,92]) "
                    "implies G_w(6) = 12.69-12.97 vs the frozen 10.889 "
                    "(FarSeer-v3 instrument) -- a x1.17-1.19 CROSS-INSTRUMENT "
                    "TENSION (the open 'Inf-dealer residual', 6.5 scorecard), "
                    "RECORDED not corrected. Cube-root interpolant (T6 anchor) "
                    "predicted 13.19 = -8% under this cell."},
    },
    "Lancer": {   # E-NIF3 (R08-R10; FC1 dealers, base_mismatch-flagged rows)
        1: {"value": 1.0,    "status": "measured", "sources": ["ENIF3_R08 (definition rung)"]},
        3: {"value": 1.0909, "status": "measured", "sources": ["ENIF3_R09/R08"],
            "band": [0.9391, 1.2571]},
        6: {"value": 1.6250, "status": "measured", "sources": ["ENIF3_R10/R08"],
            "band": [1.4348, 1.8333]},
    },
    "Marksman": {  # bounded near-flat; ENTANGLED with S_gatot (E-NIF2-redo)
        1: {"value": 1.0, "status": "measured", "sources": ["K-cell definition rung"]},
    },
}
G_W = {}
_G_W_RATIO = {}
for _cls, _cells in _G_W_MEASURED.items():
    G_W[_cls], _G_W_RATIO[_cls] = _geo_fill(_cells)
G_W_MM_BAND = [1.0, 1.17]      # Marksman tiers >= 2: value 1.0, stated band

#: target tier factor, CLASS-KEYED (measured rungs; gaps geo-filled)
_G_L_MEASURED = {
    "Infantry": {t: {"value": v, "status": "measured",
                     "sources": ["v5 ladder (stage5)"]}
                 for t, v in {1: 1.0, 2: 0.996, 3: 0.904, 4: 0.795, 5: 0.770,
                              6: 0.748, 7: 0.742, 8: 0.744, 9: 0.757,
                              10: 0.777}.items()},
    "Lancer": {
        1: {"value": 1.0,   "status": "measured", "sources": ["definition"]},
        2: {"value": 0.654, "status": "measured",
            "sources": ["2 corrected T2-Lancer rows, both 0.654 (stage5)"]},
    },
    "Marksman": {  # E-NIF2 R05-R07: STEEP (far steeper than Infantry's)
        1: {"value": 1.0,    "status": "measured",
            "sources": ["K-cell definition; ENIF2_R05 re-measures the cell "
                        "at 76.84 (+5.0% instrument spread)"]},
        3: {"value": 0.2488, "status": "measured", "sources": ["ENIF2_R06"]},
        6: {"value": 0.0846, "status": "measured", "sources": ["ENIF2_R07"]},
    },
}
G_L = {}
_G_L_RATIO = {}
for _cls, _cells in _G_L_MEASURED.items():
    G_L[_cls], _G_L_RATIO[_cls] = _geo_fill(_cells)


# --------------------------------------------------------------------------- #
#  lookups (value + provenance status; never silent)
# --------------------------------------------------------------------------- #
def K(dealer_cls, target_cls):
    """(value, status) -- measured cell or flagged factorization."""
    cell = K_CELLS.get((dealer_cls, target_cls))
    if cell is not None:
        return cell["value"], cell["status"]
    return K_F[dealer_cls] * K_G[target_cls], "factorized"


def g_w(cls, tier):
    """(value, status). Beyond the measured range: Infantry keeps the stage5
    cube-root interpolant DELIBERATELY ANCHORED AT T6 for T8-T10 (stage 6.6:
    the measured T7 cell rides the MuellerAlpaca/Vulcanus instrument whose T6
    twin shows a x1.17-1.19 cross-instrument tension -- chaining T8-T10 to it
    would bake that possible offset into three more cells; T7-anchored
    alternates are listed in the emitted JSON meta); Lancer extrapolates its
    last geometric tier ratio; Marksman stays 1.0 inside its stated band --
    all FLAGGED."""
    table = G_W[cls]
    if tier in table:
        cell = table[tier]
        return cell["value"], cell["status"]
    if cls == "Infantry":
        a6, _, l6, _ = base_stats(cls, 6)
        at, _, lt, _ = base_stats(cls, tier)
        return table[6]["value"] * ((at * lt) / (a6 * l6)) ** (2.0 / 3.0), "extrapolated"
    if cls == "Lancer":
        return table[6]["value"] * _G_W_RATIO["Lancer"] ** (tier - 6), "extrapolated"
    return 1.0, "bounded"          # Marksman: [1, 1.17] band, tiers >= 2


def g_l(cls, tier):
    """(value, status). Within a measured class column: table cells (some
    interpolated). Outside: Marksman extrapolates its own last ratio; Lancer
    falls back to the Infantry column -- FLAGGED."""
    table = G_L.get(cls, {})
    if tier in table:
        cell = table[tier]
        return cell["value"], cell["status"]
    if cls == "Marksman" and tier > 6:
        return table[6]["value"] * _G_L_RATIO["Marksman"] ** (tier - 6), "extrapolated"
    inf = G_L["Infantry"].get(tier)
    if inf is None:
        raise ValueError(f"G_l undefined for tier {tier}")
    return inf["value"], "fallback_infantry"


# --------------------------------------------------------------------------- #
#  stage6 predictor shim (same unit-dict schema as stage5_law)
# --------------------------------------------------------------------------- #
def eff_stats(cls, tier, fc=None, panel=None):
    A0, D0, L0, H0 = base_stats(cls, tier, fc or 1)
    p = panel or {}

    def m(key):
        v = p.get(key)
        return 1.0 + (float(v) / 100.0 if v is not None else 0.0)

    return {"A": A0 * m("Attack"), "D": D0 * m("Defense"),
            "L": L0 * m("Lethality"), "H": H0 * m("Health")}


def predict_turns_1v1(dealer, target, *, dealer_count=1, offense_mult=1.0):
    """Stage-6 per-unit law: class-keyed G_w/G_l + updated K cells.
    Returns (turns, meta); meta carries per-cell provenance statuses."""
    ed = dealer.get("eff") or eff_stats(dealer["cls"], dealer["tier"],
                                        dealer.get("fc"), dealer.get("panel"))
    et = target.get("eff") or eff_stats(target["cls"], target["tier"],
                                        target.get("fc"), target.get("panel"))
    k, k_status = K(dealer["cls"], target["cls"])
    gw, gw_status = g_w(dealer["cls"], dealer["tier"])
    gl, gl_status = g_l(target["cls"], target["tier"])
    t = (k * (et["D"] * et["H"]) / (ed["A"] * ed["L"] * offense_mult)
         * gw * gl / math.sqrt(max(dealer_count, 1)))
    meta = {"law_version": "stage6",
            "K": k, "K_status": k_status,
            "G_w": gw, "G_w_status": gw_status,
            "G_l": gl, "G_l_status": gl_status,
            "provenance_flags": sorted({s for s in (k_status, gw_status, gl_status)
                                        if s != "measured"}),
            "dealer_eff": ed, "target_eff": et}
    if dealer["cls"] == "Marksman" and dealer["tier"] >= 2:
        meta["G_w_band"] = G_W_MM_BAND
    return t, meta


def law_funcs():
    """Injection dict for stage5_composition.predict_battle(law=...):
    adapts the class-keyed stage6 lookups to the stage5 call signatures."""
    return {"K": K,
            "g_w": lambda tier, cls: g_w(cls, tier)[0],
            "g_l": lambda tier, cls: g_l(cls, tier)}


# --------------------------------------------------------------------------- #
#  corpus re-derivation (provenance / drift check)
# --------------------------------------------------------------------------- #
def _rows():
    with open(CORPUS, encoding="utf-8") as fh:
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


def _turns_band(r):
    o = r["outcome"]
    if o["turns"] is not None:
        return float(o["turns"]), float(o["turns"])
    tr = o.get("turns_range")
    return (float(tr[0]), float(tr[1])) if tr else (None, None)


def _k_raw(r, n_sqrt=1, t=None):
    """K_eff = t * A_w*L_w * sqrt(n) / (D_l*H_l)  (sqrt-count law)."""
    w, l = _wl(r)
    uw, ul = _single(w), _single(l)
    t = t if t is not None else _turns_mid(r)
    if not (uw and ul and t):
        return None
    ew, el = uw["eff"], ul["eff"]
    return t * ew["A"] * ew["L"] * math.sqrt(n_sqrt) / (el["D"] * el["H"])


def derive_from_corpus(rows=None):
    """Recompute the NEW/UPDATED stage6 cells from the corpus.
    (Infantry G_w/G_l and the Inf-dealer K row re-derive via stage5_law's own
    derive_from_corpus -- those cells are unchanged, not repeated here.)"""
    rows = rows or _rows()
    out = {"K_MM_Inf_parts": {}, "K_Lan_MM_parts": {}, "G_W_Lancer": {},
           "G_W_Lancer_band": {}, "G_L_Marksman": {}, "K_Inf_MM_replicates": {}}
    lan_ladder = {}          # tier -> (K_mid, K_lo, K_hi)
    k_inf_mm = K_CELLS[("Infantry", "Marksman")]["value"]

    for r in rows:
        w, l = _wl(r)
        if not w:
            continue
        uw, ul = _single(w), _single(l)
        if not (uw and ul):
            continue
        rid = r["id"]

        # --- K(MM->Inf): Gordon-target rows (Gordon battery + ENIF1b) ------ #
        if (uw["cls"], ul["cls"]) == ("Marksman", "Infantry") and \
                r["determinism"] == "gordon_deterministic":
            out["K_MM_Inf_parts"][rid] = _k_raw(r, n_sqrt=uw["count"])

        # --- K(Lan->MM) + the Lancer G_w ladder (E-NIF3 / Gordon) ---------- #
        if (uw["cls"], ul["cls"]) == ("Lancer", "Marksman") and \
                r["determinism"] == "gordon_deterministic" and \
                uw["count"] == ul["count"] == 1:
            out["K_Lan_MM_parts"][rid] = _k_raw(r)
            if r["folder"] == "ENIF":
                lo, hi = _turns_band(r)
                lan_ladder[uw["tier"]] = (_k_raw(r), _k_raw(r, t=lo),
                                          _k_raw(r, t=hi))

        # --- Marksman G_l ladder (E-NIF2 R05-R07: Gatot Inf dealer) -------- #
        if (r["folder"] == "ENIF" and uw["cls"] == "Infantry"
                and ul["cls"] == "Marksman" and r["determinism"] == "clean"):
            k_eff = _k_raw(r)
            if ul["tier"] == 1:
                out["K_Inf_MM_replicates"][rid] = k_eff
            out["G_L_Marksman"][ul["tier"]] = k_eff / k_inf_mm

    if 1 in lan_ladder:
        k1_mid, k1_lo, k1_hi = lan_ladder[1]
        for t, (k_mid, k_lo, k_hi) in sorted(lan_ladder.items()):
            out["G_W_Lancer"][t] = k_mid / k1_mid
            out["G_W_Lancer_band"][t] = (k_lo / k1_hi, k_hi / k1_lo)
        out["K_Lan_MM_enif"] = k1_mid
    return out


# --------------------------------------------------------------------------- #
#  JSON emission (single source of truth for the predictor seam)
# --------------------------------------------------------------------------- #
def build_tables_dict():
    j = {
        # STAGE 6.7 (2026-07-19, fold-ownership migration): hero_state gains
        # per-copy Royal-Legion S3 levels + 6-decimal K_LanInf_for_gate values
        # (stage6_hero_state.py); the K/G/B PHYSICS is unchanged from 6.6.
        "law_version": "stage6.7",
        "frozen": "2026-07-19",
        "corpus": {"path": "wos_sim/data/experiments/_corpus/TYPE1_CORPUS.json",
                   # STAGE 6.6 housekeeping: row_count read from the corpus at
                   # emit time (was a hand-frozen 232 that went stale at 238)
                   "row_count": len(_rows())},
        "law": ("turns = K(dealer,target) * D_t*H_t/(A_d*L_d) "
                "* G_w(dealer_cls,tier_d) * G_l(target_cls,tier_t) / sqrt(N); "
                "HP = D*H; cap 1500; point prediction = ceil(turns)"),
        "K": {f"{a}->{b}": dict(c) for (a, b), c in K_CELLS.items()},
        "K_factorization": {
            "f": K_F, "g": K_G,
            "status": "factorized (+-10-15%, stage5 verdict) -- now covers "
                      "only Lan->Lan and MM->Lan; the Lan->Inf cell is frozen "
                      "edge-implied (stage 6.6, K table) and supersedes its "
                      "factorized 83.66 at T6 (carried as a branch tag)"},
        "G_w": {cls: {f"T{t}": dict(c) for t, c in tbl.items()}
                for cls, tbl in G_W.items()},
        "G_w_marksman_band": G_W_MM_BAND,
        "G_w_extrapolation": {
            "Infantry": "T7 now MEASURED (14.285, band [14.097,14.473]); "
                        "T8-T10 keep the cube-root interpolant ANCHORED AT T6 "
                        "(the T7 cell's instrument carries a x1.17-1.19 "
                        "cross-instrument tension -- see its note; chaining "
                        "T8-T10 to it would propagate the possible offset). "
                        "T7-anchored alternates for reference: "
                        + ", ".join(
                            f"T{t}={14.285 * ((base_stats('Infantry', t)[0] * base_stats('Infantry', t)[2]) / (base_stats('Infantry', 7)[0] * base_stats('Infantry', 7)[2])) ** (2.0 / 3.0):.2f}"
                            for t in (8, 9, 10)),
            "Lancer": f"geometric ratio {_G_W_RATIO['Lancer']:.4f}/tier beyond T6",
            "Marksman": "1.0 within stated band"},
        "G_l": {cls: {f"T{t}": dict(c) for t, c in tbl.items()}
                for cls, tbl in G_L.items()},
        "G_l_fallback": "unmeasured class cells fall back to the Infantry "
                        "column, status=fallback_infantry",
        "count_law": {
            "default": "sqrt(N) (Stage-3; reconfirmed by ENIF1b R03 1v2 at -1.6%)",
            "gatot_shield_regime": "LINEAR volley pooling vs the Gatot budget "
                                   "absorb -- see gatot_kit"},
        "alliance_policy": "panels are PER-BATTLE inputs from the report "
                           "(RFJ instance +23pp A/D, +10pp L/H is documentary, "
                           "never a constant)",
        "base_stat_policy": "corpus eff stats only (docs/TroopStats table); "
                            "troop_catalog.py is the LEGACY engine's snapshot "
                            "and DIVERGES -- never use or silently edit it",
        "type2_boundary": "Vulcanus/Seo-yoon folds deterministic-cadence only; "
                          "-6.5% Vulcanus-dealer systematic is a documented "
                          "band, not a fit; FC procs untouched",
    }
    try:
        from wos_sim.formula_research.stage6_gatot import gatot_kit_block
        j["gatot_kit"] = gatot_kit_block()
    except Exception as exc:                                  # pragma: no cover
        j["gatot_kit"] = {"status": f"unavailable ({exc})"}
    # STAGE 6.6: hero-STATE layer (registry + per-(copy,state) budgets +
    # panel detector + gate K spans) -- every number re-derived by
    # stage6_hero_state.py from named corpus rows.
    try:
        from wos_sim.formula_research.stage6_hero_state import hero_state_block
        j["hero_state"] = hero_state_block()
    except Exception as exc:                                  # pragma: no cover
        j["hero_state"] = {"status": f"unavailable ({exc})"}
    return j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true", help="write stage6_tables.json")
    args = ap.parse_args()

    if args.emit:
        j = build_tables_dict()
        with open(TABLES_JSON, "w", encoding="utf-8") as fh:
            json.dump(j, fh, indent=1, sort_keys=False)
            fh.write("\n")
        print(f"wrote {TABLES_JSON}")
        return

    d = derive_from_corpus()
    print("STAGE 6 -- frozen vs corpus-derived (new/updated cells only)\n")
    print("K(MM->Inf) parts (K_eff = t*A*L*sqrt(n)/(D*H)):")
    for rid, k in sorted(d["K_MM_Inf_parts"].items()):
        print(f"   {k:8.2f}  {rid[:64]}")
    frozen = K_CELLS[("Marksman", "Infantry")]["value"]
    r02 = d["K_MM_Inf_parts"].get(
        "ENIF1b_R02_MuellerGordon_T1Inf_v_AlpacaFC1T1MM_20260717_004437")
    print(f"   frozen {frozen} = ENIF1b_R02 rule; derived R02 {r02:.2f}  "
          f"drift {r02 / frozen - 1:+.2%}")
    print("\nK(Lan->MM) parts:")
    for rid, k in sorted(d["K_Lan_MM_parts"].items()):
        print(f"   {k:8.2f}  {rid[:64]}")
    frozen = K_CELLS[("Lancer", "Marksman")]["value"]
    print(f"   frozen {frozen} = ENIF3 T1 rung; derived {d['K_Lan_MM_enif']:.2f}  "
          f"drift {d['K_Lan_MM_enif'] / frozen - 1:+.2%}")
    print("\nG_w(Lancer) (E-NIF3 ladder / T1 rung; band from turn bands):")
    for t, g in sorted(d["G_W_Lancer"].items()):
        fro = _G_W_MEASURED["Lancer"].get(t, {}).get("value")
        b = d["G_W_Lancer_band"][t]
        print(f"   T{t}: derived {g:7.4f}  band [{b[0]:.4f}, {b[1]:.4f}]  "
              f"frozen {fro}  "
              + (f"drift {g / fro - 1:+.2%}" if fro else ""))
    print("\nG_l(Marksman) (E-NIF2 ladder / K(Inf->MM)=73.16):")
    for t, g in sorted(d["G_L_Marksman"].items()):
        fro = _G_L_MEASURED["Marksman"].get(t, {}).get("value")
        tag = ("replicate of the K cell (T1 == 1 by normalization; "
               "spread rides the cell)" if t == 1 else
               (f"frozen {fro}  drift {g / fro - 1:+.2%}"))
        print(f"   T{t}: derived {g:7.4f}   {tag}")
    print("\nK(Inf->MM) T1 replicates (join the cell's evidence, cell unchanged):")
    for rid, k in sorted(d["K_Inf_MM_replicates"].items()):
        print(f"   {k:8.2f}  {rid[:64]}")
    print("\ninterpolated cells (geometric fill, computed at import):")
    for cls in ("Lancer",):
        cells = {t: c for t, c in sorted(G_W[cls].items())
                 if c["status"] == "interpolated"}
        print(f"   G_w({cls}): " + ", ".join(
            f"T{t}={c['value']:.4f}" for t, c in cells.items()))
    for cls in ("Marksman",):
        cells = {t: c for t, c in sorted(G_L[cls].items())
                 if c["status"] == "interpolated"}
        print(f"   G_l({cls}): " + ", ".join(
            f"T{t}={c['value']:.4f}" for t, c in cells.items()))
    print("\nfactorization: f = {Inf 1, Lan %.3f, MM %.3f}" % (
        K_F["Lancer"], K_F["Marksman"]))
    for dealer, target in (("Lancer", "Infantry"), ("Lancer", "Lancer"),
                           ("Marksman", "Lancer")):
        k, kind = K(dealer, target)
        print(f"   predicted K({dealer[:3]}->{target[:3]}) = {k:.1f}  [{kind}]")

    # ---- STAGE 6.6 cells: frozen vs re-derived (stage6_hero_state.py) ---- #
    from wos_sim.formula_research import stage6_hero_state as hs
    rows = _rows()
    print("\nSTAGE 6.6 cells -- frozen vs corpus-derived:")
    gw7 = hs.derive_gw7(rows)
    fro = G_W["Infantry"][7]["value"]
    print(f"   G_w(Inf,7): frozen {fro}  derived point {gw7['gw7_point']:.3f} "
          f"band [{gw7['gw7_band'][0]:.3f}, {gw7['gw7_band'][1]:.3f}]  "
          f"drift {gw7['gw7_point'] / fro - 1:+.2%}")
    kli = hs.derive_k_laninf(rows)
    fro = K_CELLS[("Lancer", "Infantry")]["value"]
    print(f"   K(Lan->Inf): frozen {fro} [edge_implied]  derived edge "
          f"{kli['K_edge_T6']:.2f} (win-turn {kli['K_winturn_T6']:.2f}; "
          f"T3-ord {kli['t3_edge']['K_edge_T3']:.2f}; factorized branch "
          f"{kli['K_factorized_branch']:.2f})  "
          f"drift {kli['K_edge_T6'] / fro - 1:+.2%}")
    ba = hs.derive_b_alpaca(rows, kli["K_edge_T6"], kli["K_factorized_branch"])
    for tag, b in ba["branches"].items():
        print(f"   B_Alpaca[{tag}]: derived {b['B']:.1f}  "
              f"(204-cap {'OK' if b['cap_check_204']['ok'] else 'VIOLATED'}, "
              f"forward kill-time {b['kill_time_consistency_575']:.1f})")


if __name__ == "__main__":
    main()
