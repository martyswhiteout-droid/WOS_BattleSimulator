"""Stage 5 -- per-row validation of the frozen law + composition algorithm.

Predictions are STATS-IN -> turns-out; observed turns are never inputs.
Sections are split by evidential status:

  A  in-sample residuals   clean exact 1v1 rows (the constants' own data --
                           instrument-consistency, gate <=3%)
  B  Gordon battery        held-out regime; 3 rows sourced K cells (marked),
                           the rest are blind transfers
  C  beast ladder          blind per-kill checks (T1/T2/T6)
  D  NanoMart T1 blind     Vulcanus regime, hero-adjusted; the ONLY data on
                           the 3 factorized K cells -- directional gate
  E  composition           algorithm vs the measured ladder/mop-up (anchor
                           mode) + the law-anchored caveat
  F  count thresholds      out-of-scope knife-edge (Gatot S2 shield) -- shown,
                           not fitted

Run:  py -m wos_sim.formula_research.stage5_validate
"""
import json
import math
import os

from wos_sim.formula_research.stage5_law import (
    CAP_TURNS, G_W, K, g_l, g_w, predict_turns_1v1,
)
from wos_sim.formula_research import stage5_composition as comp

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.abspath(os.path.join(
    HERE, "..", "data", "experiments", "_corpus", "TYPE1_CORPUS.json"))


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


def predict_row(r, offense_mult=1.0):
    w, l = wl(r)
    uw, ul = single(w), single(l)
    t, meta = predict_turns_1v1(unit_arg(uw), unit_arg(ul),
                                offense_mult=offense_mult)
    return t, meta


def band(r):
    o = r["outcome"]
    if o["turns"] is not None:
        return o["turns"], o["turns"]
    tr = o.get("turns_range")
    return (tr[0], tr[1]) if tr else (None, None)


def pct(pred, lo, hi):
    mid = (lo + hi) / 2.0
    return pred / mid - 1.0


# --------------------------------------------------------------------------- #
def section_a(rows):
    print("=" * 96)
    print("A  IN-SAMPLE residuals -- clean exact 1v1 rows. Gate: ceil(pred) == obs")
    print("   (deaths land on integer turns) OR |err| <= 3%. Bucketed by instrument.")
    print("=" * 96)
    buckets = {}
    for r in rows:
        if r["determinism"] != "clean" or r["outcome"]["turns"] in (None,):
            continue
        w, l = wl(r)
        if not w:
            continue
        uw, ul = single(w), single(l)
        if not (uw and ul and uw["count"] == 1 and ul["count"] == 1):
            continue
        if r["outcome"]["turns"] >= CAP_TURNS:
            continue
        t, meta = predict_row(r)
        lo, hi = band(r)
        e = pct(t, lo, hi)
        ceil_exact = (math.ceil(t) == r["outcome"]["turns"])
        key = r["folder"] if meta["G_l_measured"] else "G_l-fallback (unmeasured cell)"
        buckets.setdefault(key, []).append((e, ceil_exact, r["id"], r["flags"]))
    total = pass_total = 0
    for key, items in sorted(buckets.items()):
        errs = [e for e, _, _, _ in items]
        npass = sum(1 for e, ce, _, _ in items if ce or abs(e) <= 0.03)
        nceil = sum(1 for _, ce, _, _ in items if ce)
        total += len(items)
        pass_total += npass
        import statistics as _st
        print(f"  {key:28} n={len(errs):3}  pass={npass:3}  ceil-exact={nceil:3}  "
              f"median {_st.median(errs):+6.1%}  worst {max(errs, key=abs):+6.1%}")
        for e, ce, rid, fl in sorted(items, key=lambda x: -abs(x[0])):
            if not ce and abs(e) > 0.03:
                print(f"      MISS {e:+6.1%}  {rid[:66]}  flags={fl}")
    print(f"  TOTAL: {total} rows, {pass_total} pass (ceil-exact or <=3%)")
    return total, pass_total


def section_b(rows):
    print()
    print("=" * 96)
    print("B  GORDON battery (held-out regime; band gate). * = row SOURCED its K cell")
    print("=" * 96)
    sourced = {("Marksman", "Infantry"), ("Marksman", "Marksman"),
               ("Lancer", "Marksman")}
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
        t, meta = predict_row(r)
        tag = "*" if (uw["cls"], ul["cls"]) in sourced else "blind"
        ok = lo <= round(t) <= hi
        print(f"  {uw['cls'][:3]}>{ul['cls'][:3]}  band [{lo},{hi}]  "
              f"pred {t:6.1f} ({pct(t, lo, hi):+5.1%})  "
              f"{'IN-BAND' if ok else 'out':7}  [{tag}]  {r['id'][:44]}")


def section_c(rows):
    print()
    print("=" * 96)
    print("C  BEAST ladder (blind per-kill; fully-resolved rows)")
    print("=" * 96)
    for r in rows:
        if r["folder"] != "Lab Rat" or "Beast" not in r["id"]:
            continue
        w, l = wl(r)
        uw = single(w)
        t_obs = r["outcome"]["turns"]
        if not (uw and t_obs) or t_obs >= CAP_TURNS:
            continue
        n = sum(c["count"] for c in l["classes"])
        if w["casualties"]["kills"] != n:
            continue
        ul = l["classes"][0]
        t, _ = predict_turns_1v1(unit_arg(uw), unit_arg(ul))
        pred_total = t * n
        print(f"  T{uw['tier']}Inf x{n} kills  obs {t_obs}  "
              f"pred {pred_total:7.1f}  ({pred_total / t_obs - 1:+5.1%})  "
              f"{r['id'][:52]}")


# --------------------------------------------------------------------------- #
def _nanomart_offense(r, dealer_side_name, dealer, target):
    """Hero-adjusted dealer offense multiplier for a NanoMart row.
    Seo-yoon S1 (attacker side): Attack x1.05/1.10/1.15 by level.
    Vulcanus S1 (its own side): ENEMY Attack x0.96.
    Vulcanus S2 (dealer side only): +20% dmg every 6th attack -> x31/30 avg.
    Vulcanus S3 (dealer side only), per Martin's in-game True Strike tooltip
    (2026-07-18, L4 = 48%/48%, L1 = 12%/12%), procs turns 3,6,9,...:
    -12% enemy Inf/Lan Defense for 3 turns -> continuous /0.88 on D; AND
    +12% own Marksmen's Attack for 1 turn -> x(1 + 0.12/3) avg on a MM dealer."""
    mult = 1.0
    dealer_row = r[dealer_side_name]
    enemy_name = "defender" if dealer_side_name == "attacker" else "attacker"
    enemy_row = r[enemy_name]
    for h in dealer_row["heroes"]:
        if h["hero"] == "SeoYoon" and h.get("slot") == "Skill 1":
            mult *= {1: 1.05, 2: 1.10, 3: 1.15}.get(h.get("level") or 3, 1.15)
        if h["hero"] == "Vulcanus":
            if h.get("slot") == "Skill 2":
                mult *= 31.0 / 30.0
            if h.get("slot") == "Skill 3" and target["cls"] in ("Infantry", "Lancer"):
                mult /= 0.88
            if h.get("slot") == "Skill 3" and dealer["cls"] == "Marksman":
                mult *= 1.0 + 0.12 / 3.0
    for h in enemy_row["heroes"]:
        if h["hero"] == "Vulcanus" and h.get("slot") == "Skill 1":
            mult *= 0.96
    return mult


def section_d(rows):
    print()
    print("=" * 96)
    print("D  NANOMART T1 blind (Vulcanus regime, hero-adjusted; directional).")
    print("   [factorized] rows are the ONLY tests of the 3 predicted K cells.")
    print("=" * 96)
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
            continue                        # tier rows: wrong-base stats, skip
        lo, hi = band(r)
        if lo is None:
            continue
        side_name = r["outcome"]["winner"]
        mult = _nanomart_offense(r, side_name, uw, ul)
        t, meta = predict_turns_1v1(unit_arg(uw), unit_arg(ul), offense_mult=mult)
        cell = f"{uw['cls'][:3]}->{ul['cls'][:3]}"
        e = pct(t, lo, hi)
        # physically-impossible-as-recorded rows: OCR/ingestion anomaly rule --
        # flag to Martin, never model (dealer A*L in the ledger cannot produce
        # the observed kill speed by ANY smooth law)
        note = ""
        if abs(e) > 0.6:
            note = "  << RECORD ANOMALY -- flag to Martin (see report)"
        print(f"  {cell:9} [{meta['K_kind']:10}]  band [{lo:>3},{hi:>3}]  "
              f"pred {t:6.1f} ({e:+6.1%})  mult {mult:.3f}  "
              f"{r['id'][:52]}{note}")


# --------------------------------------------------------------------------- #
def section_e(rows):
    print()
    print("=" * 96)
    print("E  COMPOSITION -- algorithm vs measured ladder/mop-up")
    print("   anchor mode: t_solo = measured solo of the same regime (78 buffed / 6 naked)")
    print("=" * 96)
    # E1: buffed count ladder, anchor 78
    print("  E1 count ladder (N buffed Gatot Inf; anchor t_solo=78):")
    obs = {}
    for r in rows:
        if r["id"].startswith("manual_ladder_n"):
            obs[sum(c["count"] for c in r["attacker"]["classes"])] = r["outcome"]["turns"]
    for n in sorted(obs):
        deaths, _ = comp.army_kill_timeline(
            [{"cls": "Marksman", "tier": 1, "count": 1,
              "eff": {"A": 1, "D": 1, "L": 1, "H": 1}}],       # dealer unused in anchor mode
            comp._norm_army([{"cls": "Infantry", "tier": 1, "count": n,
                              "eff": {"A": 1, "D": 1, "L": 1, "H": 1}}]),
            t_solo=78.0)
        pred = deaths[-1][0]
        print(f"    N={n}:  obs {obs[n]:>3}   pred {pred:>3}   "
              f"{'OK' if pred == obs[n] else 'MISS'}")
    # E2: naked pair (solo 6 -> 2 naked = 8), anchor 6
    deaths, _ = comp.army_kill_timeline(
        [{"cls": "Marksman", "tier": 1, "count": 1,
          "eff": {"A": 1, "D": 1, "L": 1, "H": 1}}],
        comp._norm_army([{"cls": "Infantry", "tier": 1, "count": 2,
                          "eff": {"A": 1, "D": 1, "L": 1, "H": 1}}]),
        t_solo=6.0)
    print(f"  E2 naked pair (anchor t_solo=6):  obs 8   pred {deaths[-1][0]}   "
          f"{'OK' if deaths[-1][0] == 8 else 'MISS'}")
    # E3: backline mop-up already validated row-by-row in stage5_composition
    print("  E3 backline mop-up: see `py -m wos_sim.formula_research.stage5_composition`")
    print("     end = front + max(ceil(4k/3), latency_cls): 16/16 exact across the")
    print("     MM ladder (k=1..5,10) AND the Lancer ladder (Martin 2026-07-14)")
    # E4: the law-anchored caveat, shown honestly
    att = [{"cls": "Infantry", "tier": 1, "count": 1,
            "panel": {"Attack": 481.0, "Defense": 481.7,
                      "Lethality": 112.0, "Health": 108.7}}]
    dfn = [{"cls": "Infantry", "tier": 1, "count": 1,
            "panel": {"Attack": 537.1, "Defense": 529.9,
                      "Lethality": 119.7, "Health": 119.3}},
           {"cls": "Marksman", "tier": 1, "count": 1,
            "panel": {"Attack": 1072.5, "Defense": 1062.3,
                      "Lethality": 257.2, "Health": 160.6}}]
    res = comp.predict_battle(att, dfn)
    print(f"  E4 LAW-anchored solo tank vs Alpaca duo: pred {res['att_deaths']}"
          f" vs obs 78 -- OUT-OF-SCOPE as expected:")
    print(f"     the duo's MM dealer is proc-gated vs Gatot Infantry "
          f"(Martin-confirmed); flags={res['flags']}")


def section_f(rows):
    print()
    print("=" * 96)
    print("F  COUNT-THRESHOLD rows -- OUT OF SCOPE (knife-edge => Gatot S2 shield")
    print("   gating, incompatible with any smooth K*G*sqrt(N) law; shown, not fit)")
    print("=" * 96)
    for r in rows:
        if r["folder"] not in ("AlpacaGatot_FC1_T6_LanMM",):
            continue
        att = r["attacker"]
        n = sum(c["count"] for c in att["classes"])
        u = att["classes"][0]
        print(f"  N={n:<3} {u['cls'][:3]}T{u['tier']}  winner={r['outcome']['winner']:<9} "
              f"turns={r['outcome']['turns']}  (N-1 fails at cap, N wins -- "
              f"a 3-5% count step flips >1500 -> ~150-300 turns)")
    for r in rows:
        if r["folder"] == "MuellerAlpaca" and r["id"].startswith("LabRat_"):
            att = r["attacker"]
            n = sum(c["count"] for c in att["classes"])
            if n <= 1:
                continue
            u = att["classes"][0]
            print(f"  N={n:<3} {u['cls'][:3]}T{u['tier']}  winner={r['outcome']['winner']:<9} "
                  f"turns={r['outcome']['turns']}")


def main():
    rows = rows_all()
    section_a(rows)
    section_b(rows)
    section_c(rows)
    section_d(rows)
    section_e(rows)
    section_f(rows)


if __name__ == "__main__":
    main()
