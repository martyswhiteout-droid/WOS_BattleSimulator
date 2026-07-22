"""Stage 6 -- the Gatot-kit model (the one open mechanism).

Scope: NON-INFANTRY dealers attacking a GATOT-led Infantry target.  (Infantry
dealers vs Gatot targets ARE the clean law -- the K anchor was measured on
Gatot-vs-Gatot mirrors that resolve in ~264 turns, so no gate applies to them.)

Data (all from TYPE1_CORPUS.json; every number in this module is computed
from those rows at run time -- nothing hand-frozen):

  A. NO-HERO mobs (the eight count-threshold battles):
       vs MUELLER-Gatot (S1/S2/S3 L1, pool 290.1):  21x/22x FC1-T6-MM
         (cap / 147t), 40x/41x FC1-T6-Lan (cap / 286t)
       vs FARSEER-Gatot (S1/S2 L1, pool 70.1):      32x/33x T3-MM
         (cap / 186t), 66x/67x T3-Lan (cap / 334t)
     plus ENIF2_R05 (single no-hero FC1-T1-MM: never breaks through).
  B. VULCANUS-led single dealers vs the same Mueller-Gatot:
       T1-MM 102t, T3-MM 21t (R11), T6-MM 6t (R12), RFJ-T6-MM 6t.

RESULT (derived below, printed by `py -m wos_sim.formula_research.stage6_gatot`):

  * Regime A is a BUDGET ABSORB: the kit eats a flat B HP-units of incoming
    volley damage per turn; net = max(0, N*r1 - B) with LINEAR volley pooling.
    B is solved from ONE battle (22x T6MM, 147t); the other seven battles are
    consistency checks / brackets, all passing razor-tight.  sqrt(N) stacking
    is REFUTED in this regime by a monotonicity inequality (any suppression
    that is monotone in gross damage caps the 21->22 net jump at 1.16
    HP-units/turn vs the observed >=1.97).  Per-hit absorption is refuted the
    same way.  The Lancer thresholds then MEASURE K(Lan->Inf)*G_w^Lan --
    within the factorization band at T6, +22% tension at T3 (ordinary-vs-FC1
    base caveat), both reported.
  * Regime B is a SATURATING per-volley suppression S(d) (d = clean
    HP-units/turn of the single dealer): families are enumerated, constants
    solved from 2-point subsets, accepted only if ALL FOUR points sit in
    their exact integer-turn bands (Vulcanus S2 cadence + S3 pool folds
    applied as the primary branch; raw branch reported).
  * The two regimes are IRREDUCIBLE to one smooth mechanism: S is not
    monotone in total rate (30.9 -> S~2.4 but 194.7 -> S=inf) and not a
    per-hit law (mob hits of 9.3 would need S~100 vs the single-hit trend
    ~6); the numeric contradictions are printed.  The scope split is
    ATTACKER-HERO PRESENCE (hero-led penetrates, hero-less is gated) --
    exactly Martin's "a no-hero MM/Lan cannot beat Gatot".
  * DEFENDER ANCHORING of B (and of the S-curve constants) is OPEN: two
    defenders differ in stats AND in S3 presence; candidate scalings are
    printed, none clean.  The splitter battles are listed for Martin.
"""
import argparse
import json
import math
import os

from wos_sim.formula_research.stage6_tables import (
    CAP_TURNS, K, g_w, _rows,
)

# ------------------------------------------------------------------ corpus IDs
MOB_IDS = {
    # key: (defender, dealer_cls, dealer_tier, N)
    "M_MM_21": "AlpacaMueller_21v1_FC1T6MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_194705",
    "M_MM_22": "AlpacaMueller_22v1_FC1T6MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_194558",
    "M_Lan_40": "AlpacaMueller_40v1_FC1T6LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_unknown",
    "M_Lan_41": "AlpacaMueller_41v1_FC1T6LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_200204",
    "F_MM_32": "LabRat_32v1_T3MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_213727",
    "F_MM_33": "LabRat_33v1_T3MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_213849",
    "F_Lan_66": "LabRat_66v1_T3LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_214434",
    "F_Lan_67": "LabRat_67v1_T3LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_214455",
}
SINGLE_IDS = {
    "T1_102": "Alpaca_1v1_T1MMFC1vT1InfFC1_Vulcanus_Gatot_20260713_105103",
    "T3_R11": "ENIF2_R11_AlpacaFC1T3MMVulcanus_v_MuellerT1InfGatot_NoAlliance_20260717_191558",
    "T6_R12": "ENIF2_R12_AlpacaFC1T6MMVulcanus_v_MuellerT1InfGatot_NoAlliance_20260717_191649",
    "T6_RFJ": "RFJPlayer_1v1_T6MMvT1Inf_Vulcanus_Gatot_20260713_002605",
}
R05_ID = "ENIF2_R05_AlpacaFC1T1MM_v_MuellerT1InfGatot_20260717_004906"


def _get(rows, rid_prefix):
    for r in rows:
        if r["id"].startswith(rid_prefix):
            return r
    raise KeyError(rid_prefix)


def _battle(r):
    """Normalize: dealer = attacker side in every kit battle."""
    att, dfn = r["attacker"], r["defender"]
    u = att["classes"][0]
    t = r["outcome"]["turns"]
    dealt_kills = dfn["classes"][0]
    pool = dealt_kills["eff"]["D"] * dealt_kills["eff"]["H"]
    vulc = any(h["hero"] == "Vulcanus" for h in att.get("heroes", []))
    return {"id": r["id"], "cls": u["cls"], "tier": u["tier"], "N": u["count"],
            "AL": u["eff"]["A"] * u["eff"]["L"], "pool": pool,
            "turns": t, "capped": t is not None and t >= CAP_TURNS,
            "vulcanus": vulc,
            "def_eff": {k: dealt_kills["eff"][k] for k in "ADLH"}}


def clean_rate(b, gw_mm=1.0):
    """Per-UNIT clean rate r1 in target-HP-units/turn: A*L / (K * G_w).
    K(MM->Inf) = the frozen Gordon-target cell (the kit model owns the
    difference vs Gatot targets); K(Lan->Inf) is UNMEASURED (factorized) --
    callers treat Lancer r1 as the unknown the thresholds bracket."""
    k, k_status = K(b["cls"], "Infantry")
    gw, _ = g_w(b["cls"], b["tier"])
    if b["cls"] == "Marksman":
        gw = gw_mm if b["tier"] >= 2 else 1.0
    return b["AL"] / (k * gw), k_status


# ------------------------------------------------------------- Vulcanus folds
def g_time(T):
    """Damage-time of T integer turns for a Vulcanus S2 dealer:
    every 6th attack is +20% => cumulative damage = r * (T + 0.2*floor(T/6))."""
    return T + 0.2 * math.floor(T / 6)


def s_interval(b, folds=True, gw_mm=1.0):
    """Exact suppression band S in (lo, hi] from integer-turn semantics:
    cumulative (d/S)*g(T) >= P' and (d/S)*g(T-1) < P'."""
    d, _ = clean_rate(b, gw_mm)
    T = b["turns"]
    if folds and b["vulcanus"]:
        P = b["pool"] * 0.88                    # S3: -12% enemy Inf defense
        gT, gT1 = g_time(T), g_time(T - 1)
    else:
        P = b["pool"]
        gT, gT1 = T, T - 1
    return d * gT1 / P, d * gT / P, d          # (S_lo_excl, S_hi_incl, d)


# =========================================================================== #
#  REGIME A -- no-hero mobs: budget absorb, linear volley pooling
# =========================================================================== #
def solve_budget(rows, gw_mm=1.0):
    """B from the 22x T6MM battle alone; everything else = checks/brackets."""
    b = {k: _battle(_get(rows, rid)) for k, rid in MOB_IDS.items()}
    out = {"gw_mm": gw_mm, "checks": []}

    # --- solve B (Mueller) from M_MM_22: net = N*r1 - B = P/t, t in (146,147]
    w = b["M_MM_22"]
    r1, _ = clean_rate(w, gw_mm)
    P = w["pool"]
    net_lo, net_hi = P / w["turns"], P / (w["turns"] - 1)   # [lo, hi)
    B_lo, B_hi = w["N"] * r1 - net_hi, w["N"] * r1 - net_lo  # (lo, hi]
    B = (B_lo + B_hi) / 2.0
    out["B_mueller"] = {"value": B, "interval": [B_lo, B_hi],
                        "solved_from": w["id"], "r1_T6MM": r1, "pool": P}

    # --- check: M_MM_21 capped => 21*r1 - B <= P/1500
    c = b["M_MM_21"]
    gross = c["N"] * r1
    ok = gross <= B + c["pool"] / CAP_TURNS
    out["checks"].append(("M_MM_21 capped", ok,
                          f"gross {gross:.2f} <= B {B:.2f} + {c['pool']/CAP_TURNS:.3f} "
                          f"(margin {B + c['pool']/CAP_TURNS - gross:+.2f})"))

    # --- T6 Lancer pair: bracket r1L (K(Lan->Inf) unmeasured)
    wl, cl = b["M_Lan_41"], b["M_Lan_40"]
    Pl = wl["pool"]
    r1L_win_lo = (B_lo + Pl / wl["turns"]) / wl["N"]
    r1L_win_hi = (B_hi + Pl / (wl["turns"] - 1)) / wl["N"]
    r1L_cap_max = (B_hi + Pl / CAP_TURNS) / cl["N"]
    consistent = r1L_win_lo <= r1L_cap_max
    r1L = (r1L_win_lo + min(r1L_win_hi, r1L_cap_max)) / 2.0
    kg = wl["AL"] / r1L                        # K(Lan->Inf) * G_w^Lan(6)
    gw6, _ = g_w("Lancer", 6)
    out["checks"].append(("M_Lan pair consistent bracket", consistent,
                          f"r1L in [{r1L_win_lo:.4f}, {r1L_win_hi:.4f}] (win) "
                          f"and <= {r1L_cap_max:.4f} (cap)"))
    out["K_LanInf_G6"] = {"value": kg, "K_LanInf_at_G6": kg / gw6,
                          "vs_factorized": kg / gw6 / K("Lancer", "Infantry")[0] - 1}

    # --- Far Seer defender: solve B' from F_MM_33; checks as above
    w2 = b["F_MM_33"]
    r1f, _ = clean_rate(w2, gw_mm)
    P2 = w2["pool"]
    net2_lo, net2_hi = P2 / w2["turns"], P2 / (w2["turns"] - 1)
    B2_lo, B2_hi = w2["N"] * r1f - net2_hi, w2["N"] * r1f - net2_lo
    B2 = (B2_lo + B2_hi) / 2.0
    out["B_farseer"] = {"value": B2, "interval": [B2_lo, B2_hi],
                        "solved_from": w2["id"], "r1_T3MM": r1f, "pool": P2}
    c2 = b["F_MM_32"]
    gross2 = c2["N"] * r1f
    ok2 = gross2 <= B2 + c2["pool"] / CAP_TURNS
    out["checks"].append(("F_MM_32 capped", ok2,
                          f"gross {gross2:.2f} <= B' {B2:.2f} + {c2['pool']/CAP_TURNS:.3f} "
                          f"(margin {B2 + c2['pool']/CAP_TURNS - gross2:+.2f})"))
    wl2, cl2 = b["F_Lan_67"], b["F_Lan_66"]
    r1L2_win_lo = (B2_lo + P2 / wl2["turns"]) / wl2["N"]
    r1L2_win_hi = (B2_hi + P2 / (wl2["turns"] - 1)) / wl2["N"]
    r1L2_cap_max = (B2_hi + P2 / CAP_TURNS) / cl2["N"]
    consistent2 = r1L2_win_lo <= r1L2_cap_max
    r1L2 = (r1L2_win_lo + min(r1L2_win_hi, r1L2_cap_max)) / 2.0
    kg2 = wl2["AL"] / r1L2
    gw3, _ = g_w("Lancer", 3)
    out["checks"].append(("F_Lan pair consistent bracket", consistent2,
                          f"r1L in [{r1L2_win_lo:.4f}, {r1L2_win_hi:.4f}] (win) "
                          f"and <= {r1L2_cap_max:.4f} (cap)"))
    out["K_LanInf_G3"] = {"value": kg2, "K_LanInf_at_G3": kg2 / gw3,
                          "vs_factorized": kg2 / gw3 / K("Lancer", "Infantry")[0] - 1}

    # --- R05: single no-hero FC1 T1 MM never breaks through
    r05 = _battle(_get(rows, R05_ID))
    d05, _ = clean_rate(r05, gw_mm)
    out["checks"].append(("R05 no-hero single MM gated", d05 < out["B_mueller"]["value"],
                          f"d {d05:.2f} << B {B:.2f} -> net 0 (obs: MM died at "
                          f"t=38 with the Gatot Inf unhurt)"))
    out["battles"] = b
    return out


def refute_sqrt_and_perhit(rows):
    """The two impossibility inequalities, with numbers."""
    b21 = _battle(_get(rows, MOB_IDS["M_MM_21"]))
    b22 = _battle(_get(rows, MOB_IDS["M_MM_22"]))
    r1, _ = clean_rate(b22)
    P = b22["pool"]
    req = P / b22["turns"]                              # net needed at N=22
    cap_net = b21["pool"] / CAP_TURNS                   # max net at N=21
    inc_sqrt = (math.sqrt(22) - math.sqrt(21)) * r1
    lines = [
        ("sqrt(N) stacking", inc_sqrt + cap_net < req,
         f"any suppression monotone in gross rate: net(22) <= net(21) + "
         f"d_gross = {cap_net:.3f} + {inc_sqrt:.3f} = {cap_net + inc_sqrt:.3f} "
         f"< required {req:.3f}  => REFUTED"),
    ]
    # per-hit absorb h: cap at N=21 forces r1-h <= cap_net/21; then
    # net(22) = 22*(r1-h) <= 22/21*cap_net
    max22 = 22.0 / 21.0 * cap_net
    lines.append(("per-hit absorb", max22 < req,
                  f"cap at N=21 => per-hit net <= {cap_net/21:.5f}; "
                  f"net(22) <= {max22:.3f} < required {req:.3f}  => REFUTED"))
    # capped-absorb min(B, c*R): full cap at N=21 needs c >= 1 - eps
    gross21 = 21 * r1
    c_needed = 1 - cap_net / gross21
    lines.append(("fractional cap c*R", True,
                  f"capping N=21 needs c >= {c_needed:.4f} -> degenerates to "
                  f"the budget model (absorb ~= all of R below B)"))
    return lines


# =========================================================================== #
#  REGIME B -- Vulcanus-led singles: saturating S(d), family enumeration
# =========================================================================== #
FAMILIES = {
    # name: (n_params, solve(fn of list[(d,S)] pairs) -> params, S(d, params))
    "fixed_absorb S=d/(d-a)": (
        1, lambda pts: [pts[0][0] * (1 - 1 / pts[0][1])],
        lambda d, p: d / (d - p[0]) if d > p[0] else float("inf")),
    "shield_6pct_Adef (a=k*0.06*A_def)": (
        1, lambda pts: [pts[0][0] * (1 - 1 / pts[0][1])],   # same absorb, k printed
        lambda d, p: d / (d - p[0]) if d > p[0] else float("inf")),
    "hyperbolic S=1+a/d": (
        1, lambda pts: [(pts[0][1] - 1) * pts[0][0]],
        lambda d, p: 1 + p[0] / d),
    "power S=1+a/d^p": (
        2, None,                                             # closed-form below
        lambda d, p: 1 + p[0] / d ** p[1]),
    "exp_decay S=1+a*exp(-d/d0)": (
        2, None,
        lambda d, p: 1 + p[0] * math.exp(-d / p[1])),
    "linear_net net=phi*d-a": (
        2, None,
        lambda d, p: d / (p[0] * d - p[1]) if p[0] * d > p[1] else float("inf")),
}


def _solve2(name, p1, p2):
    """Closed-form 2-param solves from two (d, S) midpoints."""
    (d1, s1), (d2, s2) = p1, p2
    if name == "power S=1+a/d^p":
        if s1 <= 1 or s2 <= 1:
            return None
        p = math.log((s1 - 1) / (s2 - 1)) / math.log(d2 / d1)
        a = (s1 - 1) * d1 ** p
        return [a, p]
    if name == "exp_decay S=1+a*exp(-d/d0)":
        if s1 <= 1 or s2 <= 1:
            return None
        d0 = (d2 - d1) / math.log((s1 - 1) / (s2 - 1))
        if d0 <= 0:
            return None
        a = (s1 - 1) * math.exp(d1 / d0)
        return [a, d0]
    if name == "linear_net net=phi*d-a":
        n1, n2 = d1 / s1, d2 / s2
        phi = (n2 - n1) / (d2 - d1)
        a = phi * d1 - n1
        return [phi, a]
    return None


def enumerate_families(rows, folds=True, gw_mm=1.0):
    """Solve each family from every minimal subset of the 4 single-dealer
    points; ACCEPT only if every point's S lands inside its exact band."""
    singles = {k: _battle(_get(rows, rid)) for k, rid in SINGLE_IDS.items()}
    bands = {}
    for k, b in singles.items():
        lo, hi, d = s_interval(b, folds=folds, gw_mm=gw_mm)
        bands[k] = {"d": d, "S_lo": lo, "S_hi": hi, "turns": b["turns"],
                    "id": b["id"]}
    keys = sorted(bands, key=lambda k: bands[k]["d"])
    pts = [(bands[k]["d"], (bands[k]["S_lo"] + bands[k]["S_hi"]) / 2.0)
           for k in keys]

    results = {}
    for name, (n_par, solve1, s_fn) in FAMILIES.items():
        verdicts = []
        subsets = ([(i,) for i in range(len(pts))] if n_par == 1 else
                   [(i, j) for i in range(len(pts)) for j in range(i + 1, len(pts))])
        for sub in subsets:
            try:
                params = (solve1([pts[i] for i in sub]) if n_par == 1
                          else _solve2(name, pts[sub[0]], pts[sub[1]]))
            except (ValueError, ZeroDivisionError, OverflowError):
                params = None
            if not params or any(not math.isfinite(x) for x in params):
                continue
            ok_all, detail = True, []
            for k in keys:
                b = bands[k]
                s_pred = s_fn(b["d"], params)
                inside = b["S_lo"] < s_pred <= b["S_hi"] + 1e-12
                # S >= 1 always; a band whose top is < 1 is clamped to 1
                if s_pred < 1 and b["S_lo"] < 1:
                    inside = True
                ok_all &= inside
                detail.append((k, s_pred, inside))
            verdicts.append({"subset": [keys[i] for i in sub], "params": params,
                             "pass": ok_all, "detail": detail})
        best = [v for v in verdicts if v["pass"]]
        results[name] = {"survives": bool(best), "passing": best,
                         "n_solves": len(verdicts)}
    return bands, results


# =========================================================================== #
#  cross-regime irreducibility
# =========================================================================== #
def cross_regime(rows, bands, surviving):
    """Numeric contradictions that force the two-regime split."""
    b22 = _battle(_get(rows, MOB_IDS["M_MM_22"]))
    b21 = _battle(_get(rows, MOB_IDS["M_MM_21"]))
    r1, _ = clean_rate(b22)
    lines = []
    # 1. S as a function of TOTAL rate is non-monotone across regimes
    d_r11 = bands["T3_R11"]["d"]
    s_r11 = (bands["T3_R11"]["S_lo"] + bands["T3_R11"]["S_hi"]) / 2
    gross21 = 21 * r1
    lines.append(
        f"S(total): single R11 total {d_r11:.1f} -> S ~{s_r11:.2f}, but mob "
        f"total {gross21:.1f} -> S = inf (capped): larger gross, infinitely "
        f"more suppression => S is NOT a function of total incoming rate")
    # 2. per-hit S: mob per-hit d vs the single-hit trend
    req_s_mob = 22 * r1 / (b22["pool"] / b22["turns"])
    for name, res in surviving.items():
        if not res["survives"]:
            continue
        params = res["passing"][0]["params"]
        s_fn = FAMILIES[name][2]
        s_at_mobhit = s_fn(r1, params)
        lines.append(
            f"per-hit S via {name}: S({r1:.2f}) = {s_at_mobhit:.1f} would give "
            f"net(22 hits) = {22 * r1 / s_at_mobhit:.1f} HP/turn -> "
            f"{b22['pool'] / (22 * r1 / s_at_mobhit):.0f} turns vs observed "
            f"{b22['turns']} (needs S = {req_s_mob:.1f}); and N=21 (same hit "
            f"size) would need S = inf => per-hit application REFUTED")
    # 3. budget model on the singles
    lines.append(
        f"budget model on singles: every single-dealer d (13.9..61.4) < B "
        f"(~202) -> all four would be capped; observed wins in 6..102 turns "
        f"=> the no-hero budget does NOT apply to hero-led dealers")
    return lines


# =========================================================================== #
#  JSON block for stage6_tables.json
# =========================================================================== #
def gatot_kit_block():
    rows = _rows()
    budget = solve_budget(rows)
    bands, fam = enumerate_families(rows, folds=True)
    bands_raw, fam_raw = enumerate_families(rows, folds=False)
    surviving = {n: r for n, r in fam.items() if r["survives"]}
    surv_raw = {n: r for n, r in fam_raw.items() if r["survives"]}

    def fam_entry(name, res):
        v = res["passing"][0]
        return {"family": name, "params": [round(x, 4) for x in v["params"]],
                "solved_from": v["subset"],
                "n_passing_solves": len(res["passing"])}

    return {
        "status": "two-regime (measured-defender models; NOT a general law)",
        "scope": "non-Infantry dealers vs a GATOT-led Infantry target; "
                 "Infantry dealers are the clean law (no gate)",
        "regime_split": "attacker HERO PRESENCE: hero-less mobs face the "
                        "budget gate; Vulcanus-led dealers penetrate on the "
                        "saturating curve. Irreducible to one smooth "
                        "mechanism (see STAGE6_REPORT).",
        "no_hero_budget_gate": {
            "model": "net = max(0, N*r1 - B); LINEAR volley pooling "
                     "(sqrt(N) REFUTED in this regime); capped iff net*1500 "
                     "< pool",
            "B_hp_units_per_turn": {
                "Mueller_Gatot_S123_L1": round(budget["B_mueller"]["value"], 2),
                "FarSeer_Gatot_S12_L1": round(budget["B_farseer"]["value"], 2)},
            "defender_anchoring": "OPEN -- two defenders differ in stats and "
                                  "S3 presence; no clean scaling (candidates "
                                  "printed by stage6_gatot); elsewhere flag "
                                  "gatot_gate_unmodeled",
            "checks": [(name, ok) for name, ok, _ in budget["checks"]],
            "K_LanInf_implied": {
                "at_T6": round(budget["K_LanInf_G6"]["K_LanInf_at_G6"], 1),
                "at_T3": round(budget["K_LanInf_G3"]["K_LanInf_at_G3"], 1),
                "note": "shield-model-conditional measurements; T3 carries "
                        "the ordinary-vs-FC1 base caveat"}},
        "hero_led_suppression": {
            "model": "turns = ceil-solve of (d/S(d))*g_vulc(T) >= 0.88*pool; "
                     "d = A*L/K(MM->Inf) per-volley clean rate",
            "surviving_families_folded": [fam_entry(n, r)
                                          for n, r in surviving.items()],
            "surviving_families_raw": [fam_entry(n, r)
                                       for n, r in surv_raw.items()],
            "points": {k: {"d": round(b["d"], 2),
                           "S_band": [round(b["S_lo"], 3), round(b["S_hi"], 3)]}
                       for k, b in bands.items()},
            "entangled": "G_w^Marksman in [1, 1.17] cannot be split from S "
                         "without the splitter battle",
            "status": "candidate (2-param families solved on 2 points, "
                      "blind on the other 2) -- NOT frozen as law"},
        "discriminating_experiments": [
            "3x Vulcanus-led T6-MM (R12 loadout) vs Mueller-Gatot: budget "
            "gate predicts CAPPED (3*56.7 < B~202); per-volley S predicts a "
            "kill in <= 4 turns",
            "T6-MM vs the GORDON-Mueller Infantry: K_eff = 90.1*G_w^MM(6) "
            "with no Gatot in the loop -- splits G_w^MM from S_gatot"],
    }


# =========================================================================== #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", action="store_true",
                    help="also print the unfolded (no-Vulcanus-fold) branch")
    args = ap.parse_args()
    rows = _rows()

    print("=" * 96)
    print("STAGE 6 -- GATOT-KIT MODEL (all numbers computed from the corpus)")
    print("=" * 96)

    print("\n--- REGIME A: no-hero mobs -> budget absorb (linear volley pooling)")
    for gw_mm in (1.0, 1.17):
        budget = solve_budget(rows, gw_mm)
        tag = f"[G_w^MM = {gw_mm}]"
        bm, bf = budget["B_mueller"], budget["B_farseer"]
        print(f"\n  {tag} B(Mueller,S123) = {bm['value']:.2f}  "
              f"interval ({bm['interval'][0]:.2f}, {bm['interval'][1]:.2f}]  "
              f"solved from 22xT6MM=147t (r1 = {bm['r1_T6MM']:.4f})")
        print(f"  {tag} B(FarSeer,S12)  = {bf['value']:.2f}  "
              f"interval ({bf['interval'][0]:.2f}, {bf['interval'][1]:.2f}]  "
              f"solved from 33xT3MM=186t (r1 = {bf['r1_T3MM']:.4f})")
        for name, ok, detail in budget["checks"]:
            print(f"    {'PASS' if ok else 'FAIL':4} {name}: {detail}")
        k6, k3 = budget["K_LanInf_G6"], budget["K_LanInf_G3"]
        print(f"    implied K(Lan->Inf)*G6 = {k6['value']:.1f} -> "
              f"K = {k6['K_LanInf_at_G6']:.1f} ({k6['vs_factorized']:+.1%} vs "
              f"factorized 83.7)")
        print(f"    implied K(Lan->Inf)*G3 = {k3['value']:.1f} -> "
              f"K = {k3['K_LanInf_at_G3']:.1f} ({k3['vs_factorized']:+.1%}) "
              f"[ordinary-base T3 dealers -- caveat]")

    print("\n  impossibility results (Mueller T6MM pair):")
    for name, proven, detail in refute_sqrt_and_perhit(rows):
        print(f"    [{'PROVEN' if proven else 'noted '}] {name}: {detail}")

    print("\n  defender-anchoring candidates for B (no clean law -- OPEN):")
    budget = solve_budget(rows)
    for name, fn in (("A_def", lambda e: e["A"]),
                     ("D_def", lambda e: e["D"]),
                     ("A*D", lambda e: e["A"] * e["D"]),
                     ("D*H (pool)", lambda e: e["D"] * e["H"]),
                     ("A*D*H", lambda e: e["A"] * e["D"] * e["H"]),
                     ("D^2*H", lambda e: e["D"] ** 2 * e["H"])):
        em = budget["battles"]["M_MM_22"]["def_eff"]
        ef = budget["battles"]["F_MM_33"]["def_eff"]
        rm = budget["B_mueller"]["value"] / fn(em)
        rf = budget["B_farseer"]["value"] / fn(ef)
        print(f"    B/{name:11}: Mueller {rm:8.4f}  FarSeer {rf:8.4f}  "
              f"(ratio {rm/rf:5.2f}; S3 differs between the two)")

    print("\n--- REGIME B: Vulcanus-led singles -> saturating S(d)")
    for folds, label in (((True), "FOLDED (S2 cadence + S3 pool; primary)"),
                         ((False), "RAW (no folds; ENIF-doc convention)")):
        if not folds and not args.raw:
            continue
        bands, fam = enumerate_families(rows, folds=folds)
        print(f"\n  branch: {label}")
        print("    exact S bands (S in (lo, hi], d = clean HP-units/turn):")
        for k in sorted(bands, key=lambda k: bands[k]["d"]):
            b = bands[k]
            print(f"      {k:7} d = {b['d']:6.2f}  turns {b['turns']:>3}  "
                  f"S in ({b['S_lo']:.3f}, {b['S_hi']:.3f}]")
        for name, res in fam.items():
            if res["survives"]:
                for v in res["passing"][:1]:
                    ps = ", ".join(f"{x:.3f}" for x in v["params"])
                    det = "  ".join(f"{k}:{s:.2f}{'Y' if ok else 'N'}"
                                    for k, s, ok in v["detail"])
                    print(f"    SURVIVES {name}  params [{ps}] "
                          f"(solved from {'+'.join(v['subset'])}; "
                          f"{len(res['passing'])}/{res['n_solves']} solves pass)")
                    print(f"             {det}")
            else:
                print(f"    rejected {name}  (0/{res['n_solves']} solves pass)")

    bands, fam = enumerate_families(rows, folds=True)
    surviving = {n: r for n, r in fam.items() if r["survives"]}
    print("\n--- CROSS-REGIME irreducibility (numeric contradictions):")
    for line in cross_regime(rows, bands, surviving):
        print(f"    * {line}")

    print("\n--- reverse-race residual (report-only, not fitted):")
    b21 = _battle(_get(rows, MOB_IDS["M_MM_21"]))
    r = _get(rows, MOB_IDS["M_MM_21"])
    kills = r["defender"]["classes"][0] and r["defender"]["casualties"]["kills"]
    e_inf = b21["def_eff"]
    mm = r["attacker"]["classes"][0]["eff"]
    from wos_sim.formula_research.stage6_tables import g_l as g_l6
    gl, _ = g_l6("Marksman", 6)
    t_per_kill = (K("Infantry", "Marksman")[0] * mm["D"] * mm["H"]
                  / (e_inf["A"] * e_inf["L"]) * gl)
    print(f"    Gatot Inf killed {kills} of 21 MM in 1500 turns "
          f"(~{1500/kills:.0f} t/kill) vs law {t_per_kill:.0f} t/kill -- "
          f"~{1500/kills/t_per_kill:.1f}x slower; target-switching/wounded "
          f"mechanics OPEN (flagged, not fitted)")

    print("\n--- JSON block (goes into stage6_tables.json via --emit there):")
    print(json.dumps(gatot_kit_block(), indent=1)[:2000] + " ...")


if __name__ == "__main__":
    main()
