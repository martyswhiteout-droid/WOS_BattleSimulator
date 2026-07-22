"""Stage 6 -- corpus-wide validation of the class-keyed law + Gatot-kit model.

Predictions are STATS-IN -> turns-out; observed turns are never inputs.
Every one of the 232 corpus rows is ACCOUNTED FOR: scored in a section or
excluded with a stated reason (section I prints the full map).

  A6  clean exact 1v1        same rows/gate as stage5 section A; stage6 must
                             not regress (Infantry-dealer paths are identical
                             by construction -- asserted, not assumed)
  B6  Gordon band rows       old battery + the E-NIF additions; in-band gate;
                             two-sided RACE check on the ENIF1b alliance flip
  C6  beast ladder           blind per-kill (unchanged cells -- asserted)
  D6  NanoMart T1 blind      Vulcanus regime; the non-Inf-dealer rows move
                             with the updated K cells -- direction must
                             IMPROVE (they all over-predicted in stage5)
  E6  composition            unchanged algorithm; anchor-mode exactness
                             re-asserted (ladder + naked pair)
  G6  E-NIF table            all 12 rows: source cells marked, blind rows
                             scored, races checked
  H6  Gatot-kit              the 8 count-threshold battles + the 4 singles
                             under the two-regime model (stage6_gatot)
  I6  full accounting        232 rows -> section or stated exclusion; bucket
                             summary; REGRESSION GATES vs the stage5 report
  W6  two-sided winner gate  (6.7: seam-owned hero folds; see _kit_for_side)
                             (STAGE 6.5, 2026-07-18) corpus-wide, through the
                             ACTUAL seam (stage5_composition.predict_battle +
                             the stage6_gatot kit) -- CORRECT / COIN_FLIP
                             (near-even, not graded) / ABSTAIN (kit unmeasured
                             for the configuration) / WRONG. Remediates the
                             one-directional blind spot an independent QA
                             found in every section above (A6/B6/D6/G6/H6
                             each score the OBSERVED winner's own clock, not
                             "does the law call the winner from stats alone");
                             see STAGE6_5_REMEDIATION.md.

Run:  py -m wos_sim.formula_research.stage6_validate
"""
import json
import math
import os
import statistics as st

from wos_sim.formula_research import stage5_law
from wos_sim.formula_research import stage6_tables as t6
from wos_sim.formula_research import stage6_gatot as gk
from wos_sim.formula_research import stage5_composition as comp
from wos_sim.formula_research.stage5_validate import _nanomart_offense

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.abspath(os.path.join(
    HERE, "..", "data", "experiments", "_corpus", "TYPE1_CORPUS.json"))

CAP = t6.CAP_TURNS
#: Stage 6.5 A4 -- near-even races are intentionally hedged (project standing
#: rule #4), not graded as a law defect. Documented here, never tuned.
COIN_FLIP_BAND = 0.10


def rows_all():
    return json.load(open(CORPUS, encoding="utf-8"))["rows"]


def wl(r):
    w = r["outcome"]["winner"]
    if w == "attacker":
        return r["attacker"], r["defender"]
    if w == "defender":
        return r["defender"], r["attacker"]
    return None, None


def single(s):
    return s["classes"][0] if s and len(s["classes"]) == 1 else None


def unit_arg(u):
    return {"cls": u["cls"], "tier": u["tier"], "eff": u["eff"]}


def band(r):
    o = r["outcome"]
    if o["turns"] is not None:
        return o["turns"], o["turns"]
    tr = o.get("turns_range")
    return (tr[0], tr[1]) if tr else (None, None)


def pct(pred, lo, hi):
    return pred / ((lo + hi) / 2.0) - 1.0


def predict_both(r, offense_mult=1.0, n=1):
    """(t5, t6, m6, m5) predictions winner-kills-loser for a 1v1(-ish) row."""
    w, l = wl(r)
    uw, ul = single(w), single(l)
    t5, m5 = stage5_law.predict_turns_1v1(unit_arg(uw), unit_arg(ul),
                                          dealer_count=n, offense_mult=offense_mult)
    t6_, m6 = t6.predict_turns_1v1(unit_arg(uw), unit_arg(ul),
                                   dealer_count=n, offense_mult=offense_mult)
    return t5, t6_, m6, m5


def _passes(pred, r):
    lo, hi = band(r)
    ceil_exact = (r["outcome"]["turns"] is not None
                  and math.ceil(pred) == r["outcome"]["turns"])
    return ceil_exact or abs(pct(pred, lo, hi)) <= 0.03, ceil_exact


# --------------------------------------------------------------------------- #
def section_a(rows, accounted):
    print("=" * 96)
    print("A6  clean exact 1v1 (stage5 gate: ceil-exact or <=3%) -- stage6 vs stage5")
    print("=" * 96)
    buckets = {}
    for r in rows:
        if r["determinism"] != "clean" or r["outcome"]["turns"] is None:
            continue
        w, l = wl(r)
        if not w:
            continue
        uw, ul = single(w), single(l)
        if not (uw and ul and uw["count"] == 1 and ul["count"] == 1):
            continue
        if r["outcome"]["turns"] >= CAP:
            continue
        accounted[r["id"]] = "A6"
        t5, t6_, m6, m5 = predict_both(r)
        p5, _ = _passes(t5, r)
        p6, c6 = _passes(t6_, r)
        # differences are legitimate ONLY where a stage5 fallback cell became
        # a stage6 MEASURED cell (e.g. G_l^MM T3/T6 on the E-NIF rows)
        legit = (abs(t5 - t6_) < 1e-9 or
                 (not m5["G_l_measured"] and m6["G_l_status"] == "measured"))
        buckets.setdefault(r["folder"], []).append(
            (r["id"], t5, t6_, p5, p6, c6, pct(t6_, *band(r)), legit))
    tot5 = tot6 = n_tot = 0
    identical = True
    for key, items in sorted(buckets.items()):
        n5 = sum(1 for it in items if it[3])
        n6 = sum(1 for it in items if it[4])
        nc = sum(1 for it in items if it[5])
        med = st.median([it[6] for it in items])
        identical &= all(it[7] for it in items)
        tot5 += n5
        tot6 += n6
        n_tot += len(items)
        print(f"  {key:28} n={len(items):3}  stage5 pass={n5:3}  "
              f"stage6 pass={n6:3}  ceil-exact={nc:3}  median {med:+6.1%}")
    print(f"  TOTAL {n_tot} rows: stage5 {tot5} pass, stage6 {tot6} pass; "
          f"unchanged-cell predictions identical: {identical} "
          f"(differences only on fallback->measured cells)")
    return {"n": n_tot, "pass5": tot5, "pass6": tot6, "identical": identical}


def section_b(rows, accounted):
    print()
    print("=" * 96)
    print("B6  GORDON band rows (battery + E-NIF); * = row SOURCED its cell")
    print("=" * 96)
    sourced_prefix = {
        "LabRat_1v1_T1MMvT1Inf_NoAttackerHero_Gordonlvl1": "old MM->Inf source (cell now R02)",
        "ENIF1b_R02": "K(MM->Inf) FROZEN source",
        "FarSeer_1v1_T1MMvT1MM_Gordonlvl1": "K(MM->MM) source",
        "LabRat_1v1_T1LanvT1MM_NoAttackerHero_Gordonlvl1": "old Lan->MM source (cell now R08)",
        "ENIF3_R08": "K(Lan->MM) FROZEN source",
        "ENIF3_R09": "G_w(Lan,3) source",
        "ENIF3_R10": "G_w(Lan,6) source",
    }
    n_in5 = n_in6 = n_rows = 0
    for r in rows:
        if r["determinism"] != "gordon_deterministic":
            continue
        w, l = wl(r)
        uw, ul = single(w), single(l)
        if not (uw and ul):
            continue
        lo, hi = band(r)
        if lo is None:
            continue
        accounted[r["id"]] = "B6"
        n = uw["count"]
        t5, t6_, m6, _ = predict_both(r, n=n)
        tag = next((v for k, v in sourced_prefix.items()
                    if r["id"].startswith(k)), "blind")
        ok5 = lo <= round(t5) <= hi
        ok6 = lo <= round(t6_) <= hi
        n_rows += 1
        n_in5 += ok5
        n_in6 += ok6
        print(f"  {uw['cls'][:3]}x{n}->{ul['cls'][:3]}  band [{lo},{hi}]  "
              f"s5 {t5:6.1f} {'in ' if ok5 else 'OUT'}  "
              f"s6 {t6_:6.1f} ({pct(t6_, lo, hi):+5.1%}) {'in ' if ok6 else 'OUT'}"
              f"  [{tag}]  {r['id'][:42]}")
    print(f"  in-band: stage5 {n_in5}/{n_rows}  stage6 {n_in6}/{n_rows}")

    # two-sided RACE on the ENIF1b alliance flip (magnitude-independent check)
    print("\n  ENIF1b two-sided race (K-table must call the alliance winner-flip):")
    races = {}
    for r in rows:
        if not r["id"].startswith("ENIF1b_R0"):
            continue
        att, dfn = r["attacker"], r["defender"]
        ua, ud = att["classes"][0], dfn["classes"][0]
        n_a, n_d = ua["count"], ud["count"]
        ta, _ = t6.predict_turns_1v1(unit_arg(ua), unit_arg(ud), dealer_count=n_a)
        td, _ = t6.predict_turns_1v1(unit_arg(ud), unit_arg(ua), dealer_count=n_d)
        # sequential kills for a multi-unit LOSER side: attacker must kill ALL
        ta_all = ta * n_d / max(math.sqrt(1), 1)   # 1 dealer -> sequential
        pred_w = "attacker" if ta_all < td else "defender"
        obs_w = r["outcome"]["winner"]
        ok = pred_w == obs_w
        races[r["id"][:10]] = ok
        print(f"    {r['id'][:44]}  att needs {ta_all:5.1f}t  "
              f"def needs {td:5.1f}t  pred {pred_w:8}  obs {obs_w:8}  "
              f"{'OK' if ok else 'MISS'}")
    return {"n": n_rows, "in5": n_in5, "in6": n_in6,
            "races_ok": all(races.values()), "races": races}


def section_c(rows, accounted):
    print()
    print("=" * 96)
    print("C6  BEAST ladder (blind per-kill; cells unchanged -- must equal stage5)")
    print("=" * 96)
    same = True
    for r in rows:
        if r["folder"] != "Lab Rat" or "Beast" not in r["id"]:
            continue
        w, l = wl(r)
        uw = single(w)
        t_obs = r["outcome"]["turns"]
        if not (uw and t_obs) or t_obs >= CAP:
            continue
        n = sum(c["count"] for c in l["classes"])
        if w["casualties"]["kills"] != n:
            continue
        accounted[r["id"]] = "C6"
        ul = l["classes"][0]
        t5, _ = stage5_law.predict_turns_1v1(unit_arg(uw), unit_arg(ul))
        t6_, _ = t6.predict_turns_1v1(unit_arg(uw), unit_arg(ul))
        same &= abs(t5 - t6_) < 1e-9
        print(f"  T{uw['tier']}Inf x{n} kills  obs {t_obs}  "
              f"pred {t6_ * n:7.1f}  ({t6_ * n / t_obs - 1:+5.1%})  {r['id'][:52]}")
    print(f"  stage6 == stage5 on all beast rows: {same}")
    return {"identical": same}


def section_d(rows, accounted):
    print()
    print("=" * 96)
    print("D6  NANOMART T1 blind (Vulcanus regime, hero-adjusted).")
    print("    non-Inf-dealer rows move with the updated K cells -- direction check.")
    print("=" * 96)
    moved = []
    for r in rows:
        if r["folder"] != "NanoMart":
            continue
        w, l = wl(r)
        if not w:
            continue
        uw, ul = single(w), single(l)
        if not (uw and ul and uw["count"] == 1 and ul["count"] == 1):
            continue
        if uw["tier"] != 1 or ul["tier"] != 1:
            continue
        lo, hi = band(r)
        if lo is None:
            continue
        accounted[r["id"]] = "D6"
        side_name = r["outcome"]["winner"]
        mult = _nanomart_offense(r, side_name, uw, ul)
        t5, t6_, m6, _ = predict_both(r, offense_mult=mult)
        e5, e6 = pct(t5, lo, hi), pct(t6_, lo, hi)
        cell = f"{uw['cls'][:3]}->{ul['cls'][:3]}"
        delta = ""
        if abs(t5 - t6_) > 1e-9:
            better = abs(e6) <= abs(e5) + 1e-12
            moved.append((r["id"], e5, e6, better, m6["K_status"]))
            delta = f"  s5 {e5:+6.1%} -> s6 {e6:+6.1%}  {'IMPROVED' if better else 'WORSE'}"
        print(f"  {cell:9} [{m6['K_status']:10}]  band [{lo:>3},{hi:>3}]  "
              f"pred {t6_:6.1f} ({e6:+6.1%}){delta}  {r['id'][:48]}")
    # gate split by cell provenance: MEASURED cells must improve-or-hold;
    # FACTORIZED cells only owe the stage5 +-15% estimator band
    meas = [m for m in moved if m[4] == "measured"]
    fact = [m for m in moved if m[4] == "factorized"]
    meas_ok = all(b for _, _, _, b, _ in meas)
    fact_ok = all(abs(e6) <= 0.15 for _, _, e6, _, _ in fact)
    print(f"  moved rows: {len(moved)} (measured {len(meas)}: "
          f"{'all improved' if meas_ok else 'REGRESSION'}; factorized "
          f"{len(fact)}: {'within +-15% band' if fact_ok else 'OUT OF BAND'})")
    return {"moved": len(moved), "meas_ok": meas_ok, "fact_ok": fact_ok}


def section_e(accounted, rows):
    print()
    print("=" * 96)
    print("E6  COMPOSITION (algorithm unchanged -- anchor-mode exactness re-asserted)")
    print("=" * 96)
    obs = {}
    for r in rows:
        if r["id"].startswith("manual_ladder_n"):
            obs[sum(c["count"] for c in r["attacker"]["classes"])] = r["outcome"]["turns"]
            accounted[r["id"]] = "E6"
    ok_all = True
    for n in sorted(obs):
        deaths, _ = comp.army_kill_timeline(
            [{"cls": "Marksman", "tier": 1, "count": 1,
              "eff": {"A": 1, "D": 1, "L": 1, "H": 1}}],
            comp._norm_army([{"cls": "Infantry", "tier": 1, "count": n,
                              "eff": {"A": 1, "D": 1, "L": 1, "H": 1}}]),
            t_solo=78.0)
        ok = deaths[-1][0] == obs[n]
        ok_all &= ok
        print(f"  ladder N={n}: obs {obs[n]} pred {deaths[-1][0]} {'OK' if ok else 'MISS'}")
    deaths, _ = comp.army_kill_timeline(
        [{"cls": "Marksman", "tier": 1, "count": 1,
          "eff": {"A": 1, "D": 1, "L": 1, "H": 1}}],
        comp._norm_army([{"cls": "Infantry", "tier": 1, "count": 2,
                          "eff": {"A": 1, "D": 1, "L": 1, "H": 1}}]),
        t_solo=6.0)
    ok = deaths[-1][0] == 8
    ok_all &= ok
    print(f"  naked pair: obs 8 pred {deaths[-1][0]} {'OK' if ok else 'MISS'}")
    print("  (full 16/16 mop-up table: py -m wos_sim.formula_research.stage5_composition)")
    return {"anchor_exact": ok_all}


def section_g(rows, accounted):
    print()
    print("=" * 96)
    print("G6  E-NIF table (12 rows; sources marked; +5% Alpaca-MM-instrument edge)")
    print("=" * 96)
    for r in rows:
        if r["folder"] != "ENIF":
            continue
        w, l = wl(r)
        uw, ul = single(w), single(l)
        lo, hi = band(r)
        if r["id"].startswith(("ENIF2_R11", "ENIF2_R12")):
            accounted[r["id"]] = "H6 (kit single)"
            continue                      # scored in H6
        accounted[r["id"]] = "G6" if accounted.get(r["id"]) is None else accounted[r["id"]]
        n = uw["count"]
        t5, t6_, m6, _ = predict_both(r, n=n)
        e6 = pct(t6_, lo, hi)
        print(f"  {r['id'][:52]:52} band [{lo},{hi}]  pred {t6_:6.1f} "
              f"({e6:+6.1%})  K={m6['K']:.1f} G_w={m6['G_w']:.3f} G_l={m6['G_l']:.3f}")
    print("  (R01/R04 sit at -4.6%: the Alpaca-FC1-T1-MM instrument reads +5% "
          "vs the frozen Inf->MM cell -- same offset as the R05 replicate; "
          "the RACE calls in B6 are the pass criterion for these rows)")


def section_h(rows, accounted):
    print()
    print("=" * 96)
    print("H6  GATOT-KIT (two-regime model; every number from stage6_gatot)")
    print("=" * 96)
    budget = gk.solve_budget(rows)
    checks_ok = all(ok for _, ok, _ in budget["checks"])
    B, Bf = budget["B_mueller"]["value"], budget["B_farseer"]["value"]
    print(f"  budget gate: B(Mueller) = {B:.2f}, B(FarSeer) = {Bf:.2f}; "
          f"all consistency checks {'PASS' if checks_ok else 'FAIL'}")

    # the 8 threshold battles: model prediction vs observed (solve sources
    # marked -- their agreement is by construction; the others are checks)
    print("  count-threshold battles (model: capped iff N*r1 <= B + pool/1500):")
    tags = {"M_MM_22": "B-SOLVE SOURCE", "F_MM_33": "B'-SOLVE SOURCE",
            "M_MM_21": "cap check (blind)", "F_MM_32": "cap check (blind)",
            "M_Lan_41": "win-turn pins r1L (bracket)",
            "F_Lan_67": "win-turn pins r1L (bracket)",
            "M_Lan_40": "cap check (bracket consistency)",
            "F_Lan_66": "cap check (bracket consistency)"}
    thr_ok = True
    for key in ("M_MM_21", "M_MM_22", "M_Lan_40", "M_Lan_41",
                "F_MM_32", "F_MM_33", "F_Lan_66", "F_Lan_67"):
        r = gk._get(rows, gk.MOB_IDS[key])
        accounted[r["id"]] = "H6 (threshold)"
        b = gk._battle(r)
        Bd = B if key.startswith("M") else Bf
        if b["cls"] == "Marksman":
            r1, _ = gk.clean_rate(b)
        else:  # Lancer: K unmeasured -> the bracket-solved r1 (reported as such)
            src = budget["K_LanInf_G6" if key.startswith("M") else "K_LanInf_G3"]
            r1 = b["AL"] / src["value"]
        net = b["N"] * r1 - Bd
        pred_capped = net * CAP < b["pool"]
        pred_t = CAP if pred_capped else b["pool"] / net
        obs_t = b["turns"]
        ok = pred_capped == b["capped"] and (
            b["capped"] or abs(math.ceil(pred_t) - obs_t) <= 1)
        thr_ok &= ok
        print(f"    {key:8} N={b['N']:<3} obs "
              f"{'CAP' if b['capped'] else obs_t:>4}  pred "
              f"{'CAP' if pred_capped else f'{pred_t:6.1f}'}  "
              f"{'OK' if ok else 'MISS'}  [{tags[key]}]")

    # the 4 hero-led singles under the surviving family
    bands, fam = gk.enumerate_families(rows, folds=True)
    surv = {n: r for n, r in fam.items() if r["survives"]}
    print(f"  hero-led singles: surviving family(ies): {list(surv) or 'NONE'}")
    singles_ok = bool(surv)
    for name, res in surv.items():
        v = res["passing"][0]
        for k, s_pred, ok in v["detail"]:
            b = bands[k]
            singles_ok &= ok
            rid = gk.SINGLE_IDS[k]
            accounted[gk._get(rows, rid)["id"]] = "H6 (kit single)"
            print(f"    {k:7} d={b['d']:6.2f}  S band ({b['S_lo']:.3f},{b['S_hi']:.3f}]"
                  f"  S_pred {s_pred:.3f}  {'OK' if ok else 'MISS'}")
    r05 = gk._get(rows, gk.R05_ID)
    accounted[r05["id"]] = accounted.get(r05["id"], "G6")  # also a G_l source
    return {"budget_checks": checks_ok, "thresholds_ok": thr_ok,
            "singles_ok": singles_ok}


# =============================================================================
#  W6  STAGE 6.5 (2026-07-18) -- corpus-wide TWO-SIDED WINNER GATE (A1 + A4)
# =============================================================================
#: known, already-investigated non-Gatot WRONG rows (Stage 6.5 remediation
#: window) -- printed as a diagnosis, NOT swept into COIN_FLIP/ABSTAIN. Any
#: WRONG row NOT in this dict is a genuinely NEW finding this run surfaced.
W6_KNOWN_WRONG = {
    "LabRat_1v1_T1LanvT1MM_NoAttackerHero_Gordonlvl1":
        "no Gatot/Vulcanus on either side. Pre-existing K(Lan->MM) [measured, "
        "488.71] vs K(MM->Lan) [factorized, ~167.6] cross-cell tension; gap "
        "13.6% (ceil 22 vs 25), just outside the 10% coin_flip band. Out of "
        "the Gatot-kit's scope; fixing it means re-deriving a K cell "
        "(stage6_tables.py, off-limits this window) or inventing one -- "
        "neither is permitted. Report only.",
    "NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus":
        "defender has Vulcanus, NOT Gatot -- outside the Gatot-kit's scope "
        "entirely. Pre-existing gap, already visible one-directionally in D6 "
        "(+29.7%, 'IMPROVED' vs stage5 but still large); the two-sided race "
        "just surfaces it as a winner miss too. Report only, not a Gatot-kit "
        "defect.",
    "MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA":
        "the Gatot holder here is the ATTACKER (Mueller), not the defender -- "
        "the OPPOSITE polarity from the v5 series. Gatot only shields its "
        "holder as a TARGET, never buffs its holder's own offense, so the "
        "decisive attacker->defender clock (ceil 141t, no Gatot-target "
        "involved) is not rescued by any M>=1 story on the defender-kills-"
        "attacker leg (ceil 600t, already close to observed 599). Resembles "
        "the ALREADY-OPEN 'reverse-race residual' (STAGE6_REPORT.md S6, item "
        "6: a Gatot-side's own kill-rate running ~2.5x slower than the law "
        "elsewhere) at ~4.3x here -- Stage-7 mechanism territory (target-"
        "switching/wounded), not a Gatot-kit-gate fix. Flagged per the "
        "OCR-anomaly-flag-rule as well: recommend Martin double-check this "
        "specific capture.",
}


def _kit_for_side(side):
    """Stage 6.5/6.6: derive a stage5_composition `att_kit`/`def_kit`
    descriptor from the corpus row's ground-truth hero + name fields
    (corpus-schema-only -- the generic seam interface takes these as plain
    caller input; here we can actually look them up). COPY identity is read
    from the battle-report `name` field (the convention Codex's independent
    QA used); the AURA'D-vs-INERT state is NOT set here -- the seam detects
    it from the unit's Attack-panel via the frozen hero_state registry
    (stage6_hero_state D5), which is the Stage-6.6 point."""
    heroes = {h["hero"] for h in side.get("heroes", [])}
    kit = {}
    if "Gatot" in heroes:
        name = (side.get("name") or "").casefold()
        if "mueller" in name or "müller" in name:
            kit["gatot"] = "mueller"
        elif "far seer" in name or "farseer" in name:
            kit["gatot"] = "farseer"
        elif "alpaca" in name or "沃草泥的馬" in name:
            kit["gatot"] = "alpaca"         # Alpaca's CN report name
        else:
            kit["gatot"] = True             # present, copy unrecognized
    if "Vulcanus" in heroes:
        kit["vulcanus"] = True
    # STAGE 6.7: kits now carry everything the seam needs to fold by itself
    for h in side.get("heroes", []):
        if h.get("hero") == "SeoYoon" and h.get("slot") == "Skill 1":
            kit["seoyoon"] = h.get("level") or 3
        if h.get("hero") == "Gatot" and h.get("slot") == "Skill 3":
            lvl = h.get("level")
            if lvl:
                kit["royal_legion_level"] = lvl   # informational (absorbed in cells)
    other = heroes - {"Gatot", "Vulcanus"}
    if kit and other:
        kit["other_heroes"] = sorted(other)  # honesty: rider heroes recorded
    return kit or None


def _w6_scoreable(r):
    """The corpus-wide subset W6 scores: every 1v1-CLASS row (both sides
    reduce to one class; count may be >1) with a recorded winner and a turn
    clock. Mirrors the EXISTING exclusion conventions already used by
    A6/D6/I6 (composition, beast, NanoMart tier/count-survivor rows,
    legacy_unverified, multi-class sides) -- see the inline reasons; these
    regimes are validated elsewhere (C6/E6/I6) and are not two-sided-race
    shaped. Returns (uw_side_unit, ul_side_unit) as (attacker_unit,
    defender_unit) or None if excluded."""
    att, dfn = r["attacker"], r["defender"]
    ua, ud = single(att), single(dfn)
    if not (ua and ud):
        return None                                     # multi-class side
    if r["determinism"] == "legacy_unverified":
        return None
    if "Beast" in r["id"]:
        return None                                     # scored by C6
    if r["folder"] in ("Meuller_Alpaca_v5_8_Battle", "MuellerAlpaca_Gatot_2v2") or \
            r["id"].startswith(("manual_mixed", "manual_")):
        return None                                     # scored by E6
    if r["folder"] == "NanoMart" and (ua["tier"] != 1 or ud["tier"] != 1):
        return None                                     # wrong-additive-base capture
    # STAGE 6.6: NanoMart multicount rows are now W6-RACED (winner-only value;
    # the sqrt(N) pooling + folds run through the same seam). Their CLOCKS stay
    # out of exact scoring (Stage-3 sqrt-N evidence regime) -- W6 only grades
    # the winner, which is exactly what these rows can support.
    if r["outcome"]["winner"] not in ("attacker", "defender"):
        return None
    if r["outcome"]["turns"] is None and not r["outcome"].get("turns_range"):
        return None
    return ua, ud


def section_w6(rows):
    print()
    print("=" * 96)
    print("W6  TWO-SIDED WINNER GATE (corpus-wide, through the ACTUAL seam:")
    print("    stage5_composition.predict_battle + the stage6_gatot kit). Predicted winner =")
    print("    shorter clock; COIN_FLIP <=10% gap (not graded); ABSTAIN = kit unmeasured for")
    print("    this configuration (never a guess); everything else CORRECT or WRONG.")
    print("=" * 96)
    law = t6.law_funcs()
    correct, coin_flip, abstain, wrong = [], [], [], []
    for r in rows:
        scored = _w6_scoreable(r)
        if scored is None:
            continue
        ua, ud = scored
        att, dfn = r["attacker"], r["defender"]
        att_kit, def_kit = _kit_for_side(att), _kit_for_side(dfn)
        # STAGE 6.7: the SEAM owns the hero folds now (Codex QA v3 #1). W6 no
        # longer passes _nanomart_offense mults -- it passes complete kits and
        # lets predict_battle fold once per direction. This also extends the
        # folds to the NON-NanoMart Vulcanus rows, which previously raced
        # fold-blind (the re-baseline documented in STAGE6_7_REPORT.md).
        mult_a = mult_d = 1.0
        att_army = [{"cls": ua["cls"], "tier": ua["tier"], "count": ua["count"], "eff": ua["eff"],
                     "panel_pct": ua.get("panel_pct")}]   # 6.6: hero-STATE detector input
        def_army = [{"cls": ud["cls"], "tier": ud["tier"], "count": ud["count"], "eff": ud["eff"],
                     "panel_pct": ud.get("panel_pct")}]
        res = comp.predict_battle(att_army, def_army, law=law,
                                  att_offense_mult=mult_a, def_offense_mult=mult_d,
                                  att_kit=att_kit, def_kit=def_kit)
        obs_w = r["outcome"]["winner"]
        if res["winner"] == "uncertain":
            abstain.append((r, res["gatot_abstain"]))
            continue
        t_att, t_def = res["att_deaths"][-1][0], res["def_deaths"][-1][0]
        gap = abs(t_att - t_def) / min(t_att, t_def) if min(t_att, t_def) > 0 else float("inf")
        if gap <= COIN_FLIP_BAND:
            coin_flip.append((r, res, gap))
        elif res["winner"] == obs_w:
            correct.append((r, res, gap))
        else:
            wrong.append((r, res, gap))

    n_scored = len(correct) + len(coin_flip) + len(abstain) + len(wrong)
    print(f"  CORRECT   {len(correct):3}")
    print(f"  COIN_FLIP {len(coin_flip):3}  (near-even by design, project standing rule #4 -- "
          "not graded)")
    for r, res, gap in sorted(coin_flip, key=lambda x: x[0]["id"]):
        t_att, t_def = res["att_deaths"][-1][0], res["def_deaths"][-1][0]
        print(f"    {r['id'][:70]:70} obs={r['outcome']['winner']:9} law_pred={res['winner']:9} "
              f"t_att={t_att:8.2f} t_def={t_def:8.2f} gap={gap:.1%}")
    print(f"  ABSTAIN   {len(abstain):3}  (Gatot-kit constants unmeasured for this configuration)")
    for r, ab in sorted(abstain, key=lambda x: x[0]["id"]):
        bound = (f"M >= {ab['M_bound_ge']:.3f}  ({ab.get('direction')})" if "M_bound_ge" in ab
                 else ab.get("detail", ""))
        print(f"    {r['id'][:70]:70} [{ab['flag']}]")
        print(f"        {bound}")
    print(f"  WRONG     {len(wrong):3}")
    for r, res, gap in sorted(wrong, key=lambda x: x[0]["id"]):
        t_att, t_def = res["att_deaths"][-1][0], res["def_deaths"][-1][0]
        diag = next((v for k, v in W6_KNOWN_WRONG.items() if r["id"].startswith(k)),
                    "NEW finding -- not yet investigated this window.")
        print(f"    {r['id'][:70]:70} obs={r['outcome']['winner']:9} law_pred={res['winner']:9} "
              f"t_att={t_att:8.2f} t_def={t_def:8.2f} gap={gap:.1%}")
        print(f"        flags={sorted(res['flags'])}")
        print(f"        diagnosis: {diag}")

    ok = len(wrong) == 0
    print(f"\n  W6 gate: {'PASS' if ok else 'FAIL'} (WRONG == 0 required) -- "
          f"{n_scored} scored ({len(correct)} correct + {len(coin_flip)} coin_flip + "
          f"{len(abstain)} abstain + {len(wrong)} wrong)")
    return {"ok": ok, "n_scored": n_scored, "correct": len(correct),
            "coin_flip": len(coin_flip), "abstain": len(abstain), "wrong": len(wrong),
            "wrong_rows": [r["id"] for r, _, _ in wrong],
            "coin_flip_rows": [r["id"] for r, _, _ in coin_flip],
            "abstain_rows": [(r["id"], ab) for r, ab in abstain]}


def section_i(rows, accounted, results):
    print()
    print("=" * 96)
    print("I6  FULL 232-ROW ACCOUNTING + REGRESSION GATES")
    print("=" * 96)
    reasons = {}
    for r in rows:
        rid = r["id"]
        if rid in accounted:
            reasons.setdefault(accounted[rid], []).append(rid)
            continue
        # stated exclusions
        w, l = wl(r)
        uw, ul = single(w), single(l)
        if r["determinism"] == "legacy_unverified":
            why = "excluded: legacy_unverified (pre-corpus instruments)"
        elif r["folder"] in ("Meuller_Alpaca_v5_8_Battle", "MuellerAlpaca_Gatot_2v2"):
            why = "composition regime (validated via stage5_composition 16/16)"
        elif r["id"].startswith(("manual_mixed", "manual_")):
            why = "composition regime (manual mop-up rows, 16/16)"
        elif "Beast" in r["id"] and (r["outcome"]["turns"] or 0) >= CAP:
            why = "excluded: capped beast row (attrition regime, no kill clock)"
        elif r["folder"] == "NanoMart" and uw and ul and (
                uw["tier"] != 1 or ul["tier"] != 1):
            why = "excluded: NanoMart tier row (wrong-additive-base captures)"
        elif r["folder"] == "NanoMart" and (not uw or not ul or
                                            uw["count"] > 1 or ul["count"] > 1):
            why = ("W6-raced: NanoMart count row (winner-only; clocks stay "
                   "Stage-3 sqrt-N evidence)")
        elif r["outcome"]["winner"] not in ("attacker", "defender"):
            why = "excluded: no winner recorded (mutual/unknown)"
        elif not uw or not ul:
            why = "excluded: multi-class side (composition regime, unscored)"
        elif r["outcome"]["turns"] is None and not r["outcome"].get("turns_range"):
            why = "excluded: no turn clock captured"
        elif ("VulcanusNoGatot" in rid or "AlpacaFC1T1Vulcanus" in rid
              or "T1InfvFC1T6MM" in rid or "204v1" in rid or "205v1" in rid):
            # 2026-07-18/19 instruments: T6/T7 discriminators, the hero-aura
            # regime pair, and the B_Alpaca knife-edge -- all W6-raced; their
            # exact clocks anchor stage6_hero_state cells (not re-scored here)
            why = "6.6 instrument (discriminator/regime-pair/knife-edge; W6-raced)"
        else:
            why = "excluded: OTHER (inspect!)"
        reasons.setdefault(why, []).append(rid)
    n_acc = 0
    for why, ids in sorted(reasons.items()):
        n_acc += len(ids)
        print(f"  {len(ids):3}  {why}")
        if why.startswith("excluded: OTHER"):
            for i in ids:
                print(f"        !! {i[:70]}")
    print(f"  TOTAL accounted: {n_acc} / {len(rows)}")

    print("\n  REGRESSION GATES (stage6 vs the stage5 report):")
    gates = [
        ("A6 pass count >= stage5 (85/91 report)",
         results["A"]["pass6"] >= results["A"]["pass5"]),
        ("A6 predictions identical except fallback->measured cells",
         results["A"]["identical"]),
        ("B6 in-band count >= stage5", results["B"]["in6"] >= results["B"]["in5"]),
        ("B6 ENIF1b alliance-flip races all correct", results["B"]["races_ok"]),
        ("C6 beast rows identical", results["C"]["identical"]),
        ("D6 measured-cell moved rows improved-or-equal", results["D"]["meas_ok"]),
        ("D6 factorized moved rows within the +-15% estimator band",
         results["D"]["fact_ok"]),
        ("E6 composition anchor-mode exact", results["E"]["anchor_exact"]),
        ("H6 budget-gate consistency checks", results["H"]["budget_checks"]),
        ("H6 eight threshold battles reproduced", results["H"]["thresholds_ok"]),
        ("H6 hero-led singles in-band under surviving family",
         results["H"]["singles_ok"]),
        ("I6 all 232 rows accounted", n_acc == len(rows)),
        ("W6 two-sided winner gate (WRONG == 0)", results["W6"]["ok"]),
    ]
    all_ok = True
    for name, ok in gates:
        all_ok &= ok
        print(f"    {'PASS' if ok else 'FAIL'}  {name}")
    print(f"\n  OVERALL: {'ALL GATES PASS' if all_ok else 'GATE FAILURES -- see above'}")
    return all_ok


def main():
    rows = rows_all()
    accounted = {}
    results = {}
    results["A"] = section_a(rows, accounted)
    results["B"] = section_b(rows, accounted)
    results["C"] = section_c(rows, accounted)
    results["D"] = section_d(rows, accounted)
    results["E"] = section_e(accounted, rows)
    section_g(rows, accounted)
    results["H"] = section_h(rows, accounted)
    results["W6"] = section_w6(rows)
    ok = section_i(rows, accounted, results)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
