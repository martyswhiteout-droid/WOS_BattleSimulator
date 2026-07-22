"""Stage 6.6 -- hero-STATE derivations for the Gatot kit v3 (2026-07-19).

Everything here is computed from TYPE1_CORPUS.json rows + already-frozen
stage6 constants at run time; the frozen literals this module feeds into
stage6_tables.py are printed next to their re-derivation (drift must be ~0).

Derivations (spec: .claude/skills/run-stage/SKILL.md, /run-stage 6.6):

  D1  G_w(Infantry, 7) -- MEASURED from the T7 discriminator battle
      `MuellerAlpaca_1v1_T7InfvFC1T1Inf_..._AlpacaFC1T1Vulcanus_20260718_235302`
      (no-hero T7 Mueller Inf kills Alpaca's Vulcanus-led FC1-T1 Inf in
      t in [75,77]; the ONLY fold on the attacker's clock is Vulcanus S1
      enemy-Attack x0.96 -- S2/S3 act on the defender's own dealing).
      Cross-check: the same-instrument T6 twin (`..._161706`, t in [90,92])
      implies G_w(6) ~ 12.6-12.9 vs the frozen 10.889 (FarSeer-v3 x2 +
      beasts) -- a +16-19% CROSS-INSTRUMENT TENSION that is recorded, NOT
      corrected away (it is the already-open "Inf-dealer residual +18-21%"
      of the 6.5 fresh-data scorecard). The frozen T7 cell carries this
      instrument's convention with the tension in its note.

  D2  K(Lancer->Infantry) -- EDGE-IMPLIED at T6 from the 40/41 Lancer
      count-threshold pair with B(Mueller)=201.95 pinned INDEPENDENTLY by
      the 21/22 Marksman edge:  K*G_w^Lan(6) = AL_lancer * 40.5 / B_M
      => K ~ 90.4.  Variants carried: win-turn bracket (41x kill at 286t)
      => ~91.0; old factorization 6.680*12.524 = 83.7 (SUPERSEDED at T6,
      kept as a branch tag because B_Alpaca inherits it); the T3-ordinary
      edge (66/67 vs FarSeer) => ~111.3 (+23% -- the ordinary-vs-FC1 /
      tier-transfer caveat, OPEN).

  D3  B(Alpaca aura'd Gatot) -- from the 2026-07-19 204/205 Lancer knife
      edge: 204x hero-less T6 Lancers CAPPED at 1500 (defender untouched),
      205x kill at exactly t=575.  B = 205*r1 - pool/575 with
      r1 = AL/(K(Lan->Inf)*G_w^Lan(6)) -- K-branch-dependent:
      ~879 (edge-implied 90.4) / ~949 (factorized 83.7).  Consistency:
      net(204) must be <= pool/1500 (cap check) -- both branches pass.

  D4  INERT-GATOT anchor -- the 12 `MuellerAlpaca_1v1_T1InfvFC1T1Inf_*`
      rows (attacker = Mueller's Gatot at UN-aura'd panels +194/+251) fit
      the PLAIN law within +-3.2% with NO kit folds: an un-aura'd Gatot
      contributes nothing (no absorption, no Royal-Legion fold).

  D5  HERO-STATE REGISTRY + PANEL DETECTOR -- per copy (Mueller / Alpaca /
      FarSeer): Expedition Inf-A aura (hero sheets, docs/HERO_KITS.md),
      the copy's no-hero baseline Infantry A-panel (named corpus captures),
      and the nearest-neighbour state rule:
          aura'd  iff |panel_A - (baseline + Exp)| < |panel_A - baseline|
      with a x2 margin guard (closer hypothesis must be >= 2x nearer, else
      "ambiguous" -> the seam abstains).  The full-corpus detection audit
      is printed: every Gatot-led side classifies with >= 3x margin.

Run:  py -m wos_sim.formula_research.stage6_hero_state
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.abspath(os.path.join(
    HERE, "..", "data", "experiments", "_corpus", "TYPE1_CORPUS.json"))

# frozen stage-6 constants consumed by the derivations (single source:
# stage6_tables / its JSON -- imported, not retyped, except where the import
# would be circular at emit time; those are asserted against the module).
K_INF_INF = 12.524           # asserted == stage6_tables.K_CELLS at import
GW_LAN6 = 1.625              # asserted == stage6_tables G_w Lancer T6
GW_LAN3 = 1.0909             # asserted == stage6_tables G_w Lancer T3
B_MUELLER = 201.95           # gatot_kit budget (21/22 MM edge, stage6_gatot)
B_FARSEER = 30.15            # gatot_kit budget (32/33 MM edge, stage6_gatot)
CAP_TURNS = 1500
VULC_S1 = 0.96               # Vulcanus S1: enemy Attack x0.96 (once, start)

#: hero sheets (Martin's hero-screen screenshots 2026-07-18/19; the
#: Expedition Inf block IS the aura -- docs/HERO_KITS.md, verified at source:
#: Mueller +301.93 vs measured battle-panel aura +301.9/+302.0 EXACT).
EXPEDITION_PP = {"mueller": 301.93, "alpaca": 337.85, "farseer": 186.45}

#: STAGE 6.7 (2026-07-19, fold-ownership migration): Royal Legion (Gatot S3)
#: skill LEVEL per copy, from Martin's tooltip statements in docs/HERO_KITS.md
#: (Mueller: "Royal Legion Lv.2 tooltip screenshot, Martin 2026-07-18";
#: Alpaca: S3 L3, "corrected L2->L3 same day"; Far Seer: S1/S2 only, NO S3 --
#: skill-slot audit). The fold VALUES are the frozen mechanic (-10%/-15%
#: enemy Attack at L2/L3, aura'd state only); this table only records WHICH
#: level each copy runs. None = the copy has no S3 (measured absence, not
#: unknown).
ROYAL_LEGION_S3_LEVEL = {"mueller": 2, "alpaca": 3, "farseer": None}

#: no-hero baseline Infantry A-panels per copy, from named corpus captures.
BASELINE_ROWS = {
    "mueller": ("MuellerAlpaca_v5_R04", "attacker"),          # no-hero loadout 179.1
    "alpaca": ("MuellerAlpaca_1v1_T6InfvFC1T1Inf_AttInfA+179.1", "defender"),
    #            ^ 20260718_161706: "VulcanusNoGatot" -- Vulcanus is a
    #              Marksman hero, adds nothing to Infantry panels => this IS
    #              the Infantry no-hero baseline capture (176.2)
    "farseer": ("LabRat_1v1_T1InfvT1Inf_NoAttackerHero_Gordonlvl1", "attacker"),
    #            ^ Gordon-battery 0-stat LabRat unit (0.0)
}

ROW_T7 = "MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+179.1"     # ..._235302
ROW_T6 = "MuellerAlpaca_1v1_T6InfvFC1T1Inf_AttInfA+179.1"     # ..._161706
ROW_40 = "AlpacaMueller_40v1_FC1T6LanvT1Inf"
ROW_41 = "AlpacaMueller_41v1_FC1T6LanvT1Inf"
ROW_66 = "LabRat_66v1_T3LanvT1Inf"
ROW_67 = "LabRat_67v1_T3LanvT1Inf"
ROW_204 = "MuellerAlpaca_204v1_T6LanvFC1T1Inf"
ROW_205 = "MuellerAlpaca_205v1_T6LanvFC1T1Inf"
MIRROR_PREFIX = "MuellerAlpaca_1v1_T1InfvFC1T1Inf"


def _rows():
    with open(CORPUS, encoding="utf-8") as fh:
        return json.load(fh)["rows"]


def _get(rows, prefix):
    for r in rows:
        if r["id"].startswith(prefix):
            return r
    raise KeyError(prefix)


def _unit(r, side):
    return r[side]["classes"][0]


def _band(r):
    o = r["outcome"]
    if o["turns"] is not None:
        return float(o["turns"]), float(o["turns"])
    lo, hi = o["turns_range"]
    return float(lo), float(hi)


def _assert_frozen_inputs():
    """The constants above must match the live stage6 tables (no retyping)."""
    from wos_sim.formula_research import stage6_tables as t6
    assert abs(t6.K_CELLS[("Infantry", "Infantry")]["value"] - K_INF_INF) < 1e-9
    assert abs(t6.G_W["Lancer"][6]["value"] - GW_LAN6) < 1e-9
    assert abs(t6.G_W["Lancer"][3]["value"] - GW_LAN3) < 1e-9
    kit = json.load(open(os.path.join(HERE, "stage6_tables.json"),
                         encoding="utf-8"))["gatot_kit"]
    B = kit["no_hero_budget_gate"]["B_hp_units_per_turn"]
    assert abs(B["Mueller_Gatot_S123_L1"] - B_MUELLER) < 1e-9
    assert abs(B["FarSeer_Gatot_S12_L1"] - B_FARSEER) < 1e-9


# --------------------------------------------------------------------------- #
#  D1  G_w(Infantry, 7)
# --------------------------------------------------------------------------- #
def derive_gw7(rows):
    """G_w(7) = t * (A*L*0.96) / (K_II * D_t*H_t); t in [75,77]."""
    r7 = _get(rows, ROW_T7)
    a = _unit(r7, "attacker")["eff"]
    d = _unit(r7, "defender")["eff"]
    lo, hi = _band(r7)

    def gw(t):
        return t * (a["A"] * a["L"] * VULC_S1) / (K_INF_INF * d["D"] * d["H"])

    out = {"row": r7["id"], "band_turns": [lo, hi],
           "gw7_band": [gw(lo), gw(hi)], "gw7_point": gw((lo + hi) / 2.0)}

    # same-instrument T6 cross-check (recorded tension, not a correction)
    r6 = _get(rows, ROW_T6)
    a6 = _unit(r6, "attacker")["eff"]
    d6 = _unit(r6, "defender")["eff"]
    lo6, hi6 = _band(r6)

    def gw6(t):
        return t * (a6["A"] * a6["L"] * VULC_S1) / (K_INF_INF * d6["D"] * d6["H"])

    out["t6_check"] = {"row": r6["id"], "band_turns": [lo6, hi6],
                       "gw6_implied_band": [gw6(lo6), gw6(hi6)],
                       "gw6_frozen": 10.889,
                       "tension_ratio_band": [gw6(lo6) / 10.889, gw6(hi6) / 10.889]}
    return out


# --------------------------------------------------------------------------- #
#  D2  K(Lancer -> Infantry)
# --------------------------------------------------------------------------- #
def derive_k_laninf(rows):
    r40, r41 = _get(rows, ROW_40), _get(rows, ROW_41)
    al = _unit(r40, "attacker")["eff"]
    AL = al["A"] * al["L"]                       # per-unit A*L (same loadout 40/41)
    dg = _unit(r41, "defender")["eff"]
    pool = dg["D"] * dg["H"]                     # Mueller Gatot pool
    t41 = _band(r41)[0]

    kg_edge = AL * 40.5 / B_MUELLER              # count-edge midpoint solve
    r1_win = (B_MUELLER + pool / t41) / 41.0     # win-turn solve
    kg_win = AL / r1_win

    # T3-ordinary edge (FarSeer defender) -- same two conventions
    r66, r67 = _get(rows, ROW_66), _get(rows, ROW_67)
    al3 = _unit(r66, "attacker")["eff"]
    AL3 = al3["A"] * al3["L"]
    dg3 = _unit(r67, "defender")["eff"]
    pool3 = dg3["D"] * dg3["H"]
    t67 = _band(r67)[0]
    kg3_edge = AL3 * 66.5 / B_FARSEER
    kg3_win = AL3 / ((B_FARSEER + pool3 / t67) / 67.0)

    # factorized branch = f(Lancer) * g(Infantry) = (K_LanMM/K_InfMM) * K_InfInf
    k_fact = 488.71 / 73.16 * K_INF_INF
    return {
        "rows": [r40["id"], r41["id"]],
        "AL_per_lancer_T6FC1": AL, "pool_mueller": pool,
        "K_edge_T6": kg_edge / GW_LAN6, "KG6_edge": kg_edge,
        "K_winturn_T6": kg_win / GW_LAN6, "KG6_winturn": kg_win,
        "K_factorized_branch": k_fact,
        "t3_edge": {"rows": [r66["id"], r67["id"]],
                    "AL_per_lancer_T3ord": AL3,
                    "K_edge_T3": kg3_edge / GW_LAN3,
                    "K_winturn_T3": kg3_win / GW_LAN3},
    }


# --------------------------------------------------------------------------- #
#  D3  B(Alpaca aura'd)
# --------------------------------------------------------------------------- #
def derive_b_alpaca(rows, k_edge_t6, k_fact):
    r204, r205 = _get(rows, ROW_204), _get(rows, ROW_205)
    al = _unit(r205, "attacker")["eff"]
    AL = al["A"] * al["L"]                       # ordinary T6 Lancer, Mueller loadout
    dg = _unit(r205, "defender")["eff"]
    pool = dg["D"] * dg["H"]                     # Alpaca aura'd Gatot pool
    t205 = _band(r205)[0]
    assert _band(r204)[0] >= CAP_TURNS, "204v1 must be the capped row"

    out = {"rows": [r204["id"], r205["id"]],
           "AL_per_lancer_T6ord": AL, "pool_alpaca_aurad": pool,
           "kill_turn": t205, "branches": {}}
    for tag, k in (("k_laninf_edge_90p4", k_edge_t6),
                   ("k_laninf_factorized_83p7", k_fact)):
        r1 = AL / (k * GW_LAN6)
        B = 205.0 * r1 - pool / t205
        net204 = 204.0 * r1 - B
        ok_cap = net204 <= pool / CAP_TURNS + 1e-9
        # forward re-check (by construction, but guards arithmetic slips)
        t_fwd = pool / (205.0 * r1 - B)
        out["branches"][tag] = {
            "K": k, "r1": r1, "B": B,
            "cap_check_204": {"net": net204, "must_be_le": pool / CAP_TURNS,
                              "ok": bool(ok_cap)},
            "kill_time_consistency_575": t_fwd}
    return out


# --------------------------------------------------------------------------- #
#  D4  inert-Gatot anchor (12 mirror rows, plain law, no folds)
# --------------------------------------------------------------------------- #
def derive_inert(rows):
    out = []
    for r in rows:
        if not r["id"].startswith(MIRROR_PREFIX):
            continue
        mu = _unit(r, "attacker")["eff"]         # Mueller's un-aura'd Gatot (target)
        alp = _unit(r, "defender")["eff"]        # hero-less Alpaca FC1 T1 (dealer)
        t = r["outcome"]["turns"]
        if not t:
            continue
        d_plain = alp["A"] * alp["L"] / K_INF_INF
        t_pred = (mu["D"] * mu["H"]) / d_plain
        out.append({"id": r["id"], "t_obs": t, "t_plain": t_pred,
                    "err": t_pred / t - 1.0,
                    "att_panel_A": _unit(r, "attacker")["panel_pct"]["Attack"]})
    return out


# --------------------------------------------------------------------------- #
#  D5  registry + panel detector + corpus-wide audit
# --------------------------------------------------------------------------- #
def build_registry(rows):
    reg = {}
    for copy, (prefix, side) in BASELINE_ROWS.items():
        r = _get(rows, prefix)
        u = _unit(r, side)
        assert u["cls"] == "Infantry"
        assert not any(h["hero"] == "Gatot" for h in r[side].get("heroes", []))
        reg[copy] = {
            "expedition_inf_A_pp": EXPEDITION_PP[copy],
            "baseline_inf_A_pp": u["panel_pct"]["Attack"],
            "baseline_source": {"row": r["id"], "side": side},
            "provenance": "Expedition: hero sheet screenshots 2026-07-18/19 "
                          "(docs/HERO_KITS.md); baseline: named corpus capture",
            # STAGE 6.7: the seam's Royal-Legion fold reads the S3 level here
            # (aura'd state only; -10%/-15% at L2/L3; None = copy has no S3).
            "royal_legion_s3_level": ROYAL_LEGION_S3_LEVEL[copy],
            "royal_legion_provenance": "docs/HERO_KITS.md tooltip table "
                                       "(Martin 2026-07-18: Mueller Lv.2 "
                                       "screenshot; Alpaca S3 L3 corrected "
                                       "same day; FarSeer S1/S2 only)",
        }
    return reg


def detect_state(reg_entry, panel_a, margin_min=2.0):
    """Nearest-neighbour aura'd/inert call with a x`margin_min` guard.
    Returns (state, margin): state in {"aurad","inert","ambiguous"}."""
    b = reg_entry["baseline_inf_A_pp"]
    e = reg_entry["expedition_inf_A_pp"]
    d_in = abs(panel_a - b)
    d_au = abs(panel_a - (b + e))
    state = "aurad" if d_au < d_in else "inert"
    margin = max(d_in, d_au) / max(min(d_in, d_au), 1e-3)
    if margin < margin_min:
        return "ambiguous", margin
    return state, margin


COPY_NAME_MAP = (
    # (substrings-in-casefolded-name, copy) -- ground-truth report names.
    (("mueller", "müller"), "mueller"),
    (("far seer", "farseer"), "farseer"),
    (("alpaca", "沃草泥的馬"), "alpaca"),   # 沃草泥的馬
)


def copy_for_name(name):
    n = (name or "").casefold()
    for subs, copy in COPY_NAME_MAP:
        if any(s in n for s in subs):
            return copy
    return None


def detection_audit(rows, reg):
    """Classify every Gatot-led corpus side; the evidence table for the seam."""
    audit = []
    for r in rows:
        for side in ("attacker", "defender"):
            s = r[side]
            if not any(h["hero"] == "Gatot" for h in s.get("heroes", [])):
                continue
            infs = [u for u in s["classes"] if u["cls"] == "Infantry"]
            if not infs:
                audit.append((r["id"], side, None, None, "no-inf-unit", None))
                continue
            u = infs[0]
            copy = copy_for_name(s.get("name"))
            pa = (u.get("panel_pct") or {}).get("Attack")
            if copy is None or pa is None:
                audit.append((r["id"], side, copy, pa, "unknown-copy-or-panel", None))
                continue
            state, margin = detect_state(reg[copy], pa)
            audit.append((r["id"], side, copy, pa, state, margin))
    return audit


# --------------------------------------------------------------------------- #
#  frozen block for stage6_tables.json  (all values re-derived above)
# --------------------------------------------------------------------------- #
def hero_state_block(rows=None):
    rows = rows or _rows()
    _assert_frozen_inputs()
    gw7 = derive_gw7(rows)
    kli = derive_k_laninf(rows)
    ba = derive_b_alpaca(rows, kli["K_edge_T6"], kli["K_factorized_branch"])
    reg = build_registry(rows)
    inert = derive_inert(rows)
    max_inert_err = max(abs(x["err"]) for x in inert)
    b_edge = ba["branches"]["k_laninf_edge_90p4"]["B"]
    b_fact = ba["branches"]["k_laninf_factorized_83p7"]["B"]
    return {
        "frozen": "2026-07-19",
        "registry": {c: {k: (round(v, 2) if isinstance(v, float) else v)
                         for k, v in e.items()} for c, e in reg.items()},
        "detection": {
            "rule": "aura'd iff the unit's Infantry Attack-panel is nearer "
                    "(baseline + Expedition%) than baseline; nearest-neighbour "
                    "with a x2 margin guard, else 'ambiguous' (seam abstains). "
                    "Corpus audit: every Gatot-led side classifies at >= x3 "
                    "margin (printout).",
            "margin_min": 2.0},
        "B_by_copy_state": {
            "mueller.aurad": {"value": B_MUELLER, "status": "measured",
                              "sources": ["21/22 T6-MM edge (stage6_gatot)"]},
            "farseer.aurad": {"value": B_FARSEER, "status": "measured",
                              "sources": ["32/33 T3-MM edge (stage6_gatot)"]},
            "alpaca.aurad": {
                # FULL precision (2026-07-19 QA v3 finding #2): the 205-edge
                # net is ~0.53/turn, so a 1-decimal B (+-0.05) swings the
                # predicted kill turn by ~11% (575 -> 648). Emit 6 decimals.
                "value": round(b_edge, 6), "status": "measured",
                "branch_k_laninf_edge": round(b_edge, 6),
                "branch_k_laninf_factorized": round(b_fact, 6),
                "branch_note": "B inherits the K(Lan->Inf) branch (the "
                               "measuring dealers were Lancers); primary = "
                               "the edge-implied K=90.4 branch; the 204-cap "
                               "and 575-kill checks pass on BOTH branches",
                "sources": [ba["rows"][0], ba["rows"][1] + " (kill @575)"]},
            "any.inert": {"value": 0.0, "status": "measured",
                          "sources": ["12 MuellerAlpaca_1v1_T1InfvFC1T1Inf_* "
                                      "rows fit the plain law, max |err| "
                                      f"{max_inert_err:.1%} (D4)"]},
        },
        "scurve_by_copy_state": {
            "mueller.aurad": "gatot_kit.hero_led_suppression (exp_decay; "
                             "solved/blind on the four Mueller-target singles)"},
        "K_LanInf_for_gate": {
            # STAGE 6.7 precision (QA v3 finding #2 extended to K): the 205-edge
            # net is ~0.5/turn, so the stored-K precision dominates the
            # predicted kill turn (2-dp K read 587 vs the exact 575). Emit 6
            # decimals, matching B.
            "T6": round(kli["K_edge_T6"], 6),
            "T6_winturn_variant": round(kli["K_winturn_T6"], 6),
            "T3_ordinary": round(kli["t3_edge"]["K_edge_T3"], 6),
            "factorized_branch": round(kli["K_factorized_branch"], 6),
            "robustness_span": [round(kli["K_factorized_branch"], 6),
                                round(kli["t3_edge"]["K_edge_T3"], 6)],
            "note": "per-edge, shield-model-conditional; T6 primary; the "
                    "T3-ordinary edge disagrees +23% (ordinary-vs-FC1 / "
                    "tier-transfer OPEN); gate verdicts for other tiers "
                    "must be invariant across the robustness span or the "
                    "seam abstains"},
        "gatot_led_dealer_policy": {
            "vs_aurad_target": "plain law (the Lab-Rat Gatot-mirror battery "
                               "-- the K(Inf->Inf) source rows -- IS this "
                               "configuration and resolves on the clean law)",
            "caveat": "the Gatot-DEALER slowdown (151127, ~4x) remains open "
                      "physics; where the Gatot-led dealer's naive clock is "
                      "the LOSING one the verdict is slowdown-robust "
                      "(slowdown only lengthens it)"},
    }


# --------------------------------------------------------------------------- #
def main():
    rows = _rows()
    _assert_frozen_inputs()
    print("=" * 96)
    print("STAGE 6.6 -- HERO-STATE DERIVATIONS (all numbers from corpus rows;"
          " re-runnable)")
    print("=" * 96)

    gw7 = derive_gw7(rows)
    print("\nD1  G_w(Infantry, 7)  [row %s]" % gw7["row"][:72])
    print("    t in [%d, %d]  ->  G_w(7) in [%.3f, %.3f], point %.3f"
          % (*gw7["band_turns"], *gw7["gw7_band"], gw7["gw7_point"]))
    t6 = gw7["t6_check"]
    print("    T6 same-instrument check [row %s]:" % t6["row"][:64])
    print("      implied G_w(6) in [%.3f, %.3f] vs frozen %.3f  "
          "(tension x%.3f-x%.3f -- RECORDED, not corrected; the open "
          "'Inf-dealer residual')"
          % (*t6["gw6_implied_band"], t6["gw6_frozen"],
             *t6["tension_ratio_band"]))
    print("      cube-root interpolant anchored T6 gave 13.19 for T7 -> "
          "measured point is %+.1f%% above it"
          % ((gw7["gw7_point"] / 13.1911 - 1) * 100))

    kli = derive_k_laninf(rows)
    print("\nD2  K(Lancer->Infantry)")
    print("    T6 edge (40/41 vs B_Mueller=%.2f):  AL/Lancer = %.2f" %
          (B_MUELLER, kli["AL_per_lancer_T6FC1"]))
    print("      count-edge solve:  K*G6 = %.2f  ->  K = %.2f   [FROZEN primary]"
          % (kli["KG6_edge"], kli["K_edge_T6"]))
    print("      win-turn solve  :  K*G6 = %.2f  ->  K = %.2f   [band variant]"
          % (kli["KG6_winturn"], kli["K_winturn_T6"]))
    print("      factorized branch: K = %.2f                    [superseded at "
          "T6; carried for B_Alpaca]" % kli["K_factorized_branch"])
    t3 = kli["t3_edge"]
    print("    T3-ordinary edge (66/67 vs B_FarSeer=%.2f): K = %.2f "
          "(win-turn %.2f)  -- +%.0f%% vs the T6 cell: ordinary-vs-FC1 / "
          "tier-transfer OPEN" % (B_FARSEER, t3["K_edge_T3"], t3["K_winturn_T3"],
                                  (t3["K_edge_T3"] / kli["K_edge_T6"] - 1) * 100))

    ba = derive_b_alpaca(rows, kli["K_edge_T6"], kli["K_factorized_branch"])
    print("\nD3  B(Alpaca aura'd)  [204v1 capped / 205v1 kill @ %d]" % ba["kill_turn"])
    print("    AL/Lancer (ordinary T6, Mueller loadout) = %.2f ; pool(Alpaca "
          "aura'd Gatot) = %.2f" % (ba["AL_per_lancer_T6ord"], ba["pool_alpaca_aurad"]))
    for tag, b in ba["branches"].items():
        c = b["cap_check_204"]
        print("    %-28s K=%.2f  r1=%.4f  ->  B = %.1f" % (tag, b["K"], b["r1"], b["B"]))
        print("      204-cap check: net = %+.2f  (must be <= %.3f)  %s ; "
              "forward kill-time = %.1f"
              % (c["net"], c["must_be_le"], "OK" if c["ok"] else "VIOLATED",
                 b["kill_time_consistency_575"]))

    inert = derive_inert(rows)
    print("\nD4  INERT anchor -- 12 mirror rows, plain law, no folds:")
    for x in inert:
        print("    t_obs=%4d  t_plain=%6.1f  err=%+5.1f%%  att_panel_A=%.1f"
              % (x["t_obs"], x["t_plain"], x["err"] * 100, x["att_panel_A"]))
    print("    max |err| = %.1f%%  (anchor: <= 3.2%%)"
          % (max(abs(x["err"]) for x in inert) * 100))

    reg = build_registry(rows)
    print("\nD5  REGISTRY + corpus-wide detection audit:")
    for c, e in reg.items():
        print("    %-8s baseline A-panel %.1f  (+Exp %.2f -> aura'd %.1f)   [%s]"
              % (c, e["baseline_inf_A_pp"], e["expedition_inf_A_pp"],
                 e["baseline_inf_A_pp"] + e["expedition_inf_A_pp"],
                 e["baseline_source"]["row"][:56]))
    audit = detection_audit(rows, reg)
    counts = {}
    worst = None
    for rid, side, copy, pa, state, margin in audit:
        counts[state] = counts.get(state, 0) + 1
        if margin is not None and (worst is None or margin < worst[-1]):
            worst = (rid, side, copy, pa, state, margin)
    print("    Gatot-led sides classified:", dict(sorted(counts.items())))
    for rid, side, copy, pa, state, margin in audit:
        if state in ("ambiguous", "unknown-copy-or-panel", "no-inf-unit"):
            print("      !! %-9s %-8s panel=%s  %s  [%s]"
                  % (state, str(copy), pa, side, rid[:56]))
    if worst:
        print("    tightest margin: x%.2f  (%s, %s, panel %.1f -> %s)  [%s]"
              % (worst[5], worst[2], worst[1], worst[3], worst[4], worst[0][:48]))

    print("\nJSON block preview (stage6_tables.json 'hero_state'):")
    print(json.dumps(hero_state_block(rows), indent=1)[:1400] + " ...")


if __name__ == "__main__":
    main()
