"""Row-by-row reconciliation of Codex QA's FAIL rows (qa_codex/qa_results.csv)
against the corrected 2026-07-18 state:

  1. PHASE-3 Vulcanus bands -- build_corpus.py now re-derives every
     Vulcanus-clocked band from the RECORDED S2/S3 counters under the
     triangulated cadence (S3 procs turns 3,6,9,...; flag
     `band_rederived_phase3`, 60 rows). Codex scored against the stale
     phase-1 bands.
  2. TRUE-STRIKE dual effect -- Martin's tooltip: S3 also buffs the holder's
     own Marksmen's Attack +12% for 1 turn each proc -> x(1+0.12/3) on MM
     dealers (now in `_nanomart_offense`); the -12% Inf/Lan Def shred stands.
  3. The Stage-6.5 seam (Gatot-kit gate + honest abstention + coin-flip
     carve-out), so kit-unmeasured rows classify as ABSTAIN, not misses.

For every Codex FAIL row we recompute OUR prediction through the same path
W6 uses (stage5_composition.predict_battle + stage6 law + folds + kit
descriptors) and bucket the row:

  RESOLVED            our pred passes vs the corrected band (in band,
                      ceil-in-band, or <=10% vs the nearest edge) with the
                      right winner; attribution tags say WHY Codex missed it
                      (stale band / MM fold / QA-side implementation diff).
  COIN_FLIP_CARVEOUT  near-even (<=10% clock gap), standing rule #4.
  KNOWN_OPEN_ABSTAIN  Gatot-kit constants unmeasured (the F1/M cluster and
                      Lancer-K gate rows) -- the seam now abstains here.
  KNOWN_WRONG         the 3 investigated W6 WRONG rows (diagnoses inline).
  RESIDUAL_CLOCK      winner right but clock still >10% off the corrected
                      band -- genuine open findings (listed with %).
  OUT_OF_DOMAIN       rows Codex itself tabled out-of-domain (tier rows with
                      wrong-base captures, count/survivor rows, declared
                      estimator bands) -- shown with their declared bands.

Output: prints the table and writes CODEX_RECONCILIATION.md next to this
file. Re-runnable; no number in the MD is hand-typed.
"""
import csv
import math
import os

from wos_sim.formula_research import stage6_tables as t6
from wos_sim.formula_research import stage5_composition as comp
from wos_sim.formula_research.stage5_validate import _nanomart_offense
from wos_sim.formula_research.stage6_validate import (
    rows_all, single, band, pct, _kit_for_side, _w6_scoreable,
    COIN_FLIP_BAND, W6_KNOWN_WRONG)

HERE = os.path.dirname(os.path.abspath(__file__))
QA_CSV = os.path.join(HERE, "qa_codex", "qa_results.csv")
OUT_MD = os.path.join(HERE, "CODEX_RECONCILIATION.md")


def clock_pass(pred, r):
    """QA bar: in corrected band (ceil-in-band counts) or <=10% vs nearest edge."""
    lo, hi = band(r)
    if lo is None:
        return False, None
    c = math.ceil(pred)
    if lo <= c <= hi or lo <= pred <= hi:
        return True, 0.0
    edge = lo if pred < lo else hi
    err = pred / edge - 1.0
    return abs(err) <= 0.10, err


def race(r):
    """Two-sided race exactly as section_w6 runs it. Returns the result dict."""
    ua, ud = single(r["attacker"]), single(r["defender"])
    mult_a = mult_d = 1.0
    if r["folder"] == "NanoMart":
        mult_a = _nanomart_offense(r, "attacker", ua, ud)
        mult_d = _nanomart_offense(r, "defender", ud, ua)
    att_army = [{"cls": ua["cls"], "tier": ua["tier"], "count": ua["count"], "eff": ua["eff"]}]
    def_army = [{"cls": ud["cls"], "tier": ud["tier"], "count": ud["count"], "eff": ud["eff"]}]
    return comp.predict_battle(att_army, def_army, law=t6.law_funcs(),
                               att_offense_mult=mult_a, def_offense_mult=mult_d,
                               att_kit=_kit_for_side(r["attacker"]),
                               def_kit=_kit_for_side(r["defender"]))


def mm_fold_applies(r):
    """True if the x1.04 True-Strike MM-attack fold touches this row's
    winner-direction dealer (Vulcanus S3 on the dealer side, MM dealer)."""
    w = r["outcome"]["winner"]
    if w not in ("attacker", "defender") or r["folder"] != "NanoMart":
        return False
    dealer_side = r[w]
    u = single(dealer_side)
    return bool(u and u["cls"] == "Marksman" and any(
        h["hero"] == "Vulcanus" and h.get("slot") == "Skill 3"
        for h in dealer_side["heroes"]))


def main():
    corpus = {r["id"]: r for r in rows_all()}
    fails = [row for row in csv.DictReader(open(QA_CSV, encoding="utf-8"))
             if row["verdict"].strip().upper() == "FAIL"]
    buckets = {k: [] for k in ("RESOLVED", "COIN_FLIP_CARVEOUT", "KNOWN_OPEN_ABSTAIN",
                               "KNOWN_WRONG", "RESIDUAL_CLOCK", "OUT_OF_DOMAIN")}

    for q in fails:
        rid = q["id"]
        r = corpus.get(rid)
        if r is None:
            buckets["OUT_OF_DOMAIN"].append((q, None, "id not in current corpus"))
            continue
        band_flag = next((f for f in r.get("flags", []) if f.startswith("band_rederived")), None)
        lo, hi = band(r)
        scored = _w6_scoreable(r)
        if scored is None:
            note = f"corrected band [{lo},{hi}]" + (f"; {band_flag}" if band_flag else "")
            buckets["OUT_OF_DOMAIN"].append((q, r, f"excluded from exact scoring ({q['domain_class']}); {note}"))
            continue

        res = race(r)
        if res["winner"] == "uncertain":
            ab = res["gatot_abstain"]
            det = ab.get("detail") or f"M >= {ab.get('M_bound_ge', 0):.2f} ({ab.get('direction')})"
            buckets["KNOWN_OPEN_ABSTAIN"].append((q, r, f"[{ab['flag']}] {det}"))
            continue
        known = next((v for k, v in W6_KNOWN_WRONG.items() if rid.startswith(k)), None)
        t_att, t_def = res["att_deaths"][-1][0], res["def_deaths"][-1][0]
        gap = abs(t_att - t_def) / min(t_att, t_def)
        obs_w = r["outcome"]["winner"]
        battle_len = t_def if res["winner"] == "attacker" else t_att
        ok, err = clock_pass(battle_len, r)
        winner_ok = res["winner"] == obs_w

        if known and not (winner_ok and ok):
            buckets["KNOWN_WRONG"].append((q, r, known.split(".")[0]))
            continue
        if gap <= COIN_FLIP_BAND:
            buckets["COIN_FLIP_CARVEOUT"].append((q, r, f"clock gap {gap:.1%}"))
            continue
        if winner_ok and ok:
            tags = []
            if band_flag:
                tags.append(band_flag)
            if mm_fold_applies(r):
                tags.append("true_strike_mm_fold_x1.04")
            if not tags:
                tags.append("qa_side_implementation_difference")
            buckets["RESOLVED"].append((q, r, " + ".join(tags)))
        elif winner_ok:
            buckets["RESIDUAL_CLOCK"].append(
                (q, r, f"pred {battle_len:.1f} vs [{lo},{hi}] ({err:+.1%} past edge)"
                       + (f"; {band_flag}" if band_flag else "")))
        else:
            buckets["KNOWN_WRONG" if known else "RESIDUAL_CLOCK"].append(
                (q, r, (known.split(".")[0] if known else
                        f"WINNER MISS pred={res['winner']} obs={obs_w} gap={gap:.1%} -- NEW")))

    lines = ["# Codex QA reconciliation -- 2026-07-18 corrected state",
             "",
             f"Input: the {len(fails)} FAIL rows of `qa_codex/qa_results.csv`, re-scored",
             "against phase-3 bands + True-Strike dual fold + the Stage-6.5 seam.",
             "Generated by `codex_reconciliation.py` (re-runnable; nothing hand-typed).",
             ""]
    for bk, items in buckets.items():
        lines.append(f"## {bk} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("(none)")
            lines.append("")
            continue
        lines.append("| id | Codex obs/pred (%err) | reconciliation |")
        lines.append("|---|---|---|")
        for q, r, why in sorted(items, key=lambda x: x[0]["id"]):
            codex = f"{q['observed']} / {q['predicted'][:9]} ({q['pcterr'][:7] or 'n/a'})"
            lines.append(f"| `{q['id'][:64]}` | {codex} | {why} |")
        lines.append("")
    summary = ", ".join(f"{k} {len(v)}" for k, v in buckets.items())
    lines.append(f"**Summary: {summary}.**")
    text = "\n".join(lines) + "\n"
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
