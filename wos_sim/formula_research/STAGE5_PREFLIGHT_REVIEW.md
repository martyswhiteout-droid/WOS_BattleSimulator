# Stage 5 pre-flight review — full audit of the Stages 1–4 chain (2026-07-13)

Requested by Martin before kicking off Stage 5. Adversarial re-check of every
load-bearing claim, with the specific corrections it produced. Verdict at the end.

## A. What re-verified as WATERTIGHT

1. **The per-unit law rests entirely on Vulcanus-free data.** Audited hero presence
   per dataset (script re-run today):
   | dataset | role in the law | heroes present | status |
   |--|--|--|--|
   | MuellerAlpaca 12-row (C anchor) | C = 12.52 | att Gatot only, def NONE | clean |
   | LabRat Gatot ladders | A/L/D/H exponents | att Gatot only | clean |
   | FarSeerGatot_v3 | G_w ladder (+cross-class) | def Gatot only | clean |
   | MuellerAlpaca_Gatot_v4 | HP=D·H + K-table | def Gatot only | clean |
   | MuellerAlpaca_Gatot_v5 | G_l ladder | def Gatot only | clean |
   | AlpacaGatot threshold | counter magnitude | def Gatot only | clean |
   Vulcanus appears ONLY in: the composition sets (2v2, v5_8), the NanoMart regime,
   and the RFJ/Alpaca-MM non-Inf rows. Consequence: every constant in the per-unit
   law (C, exponents, G_w, G_l, K-table) is proc-free and hero-clean.
2. **K-table recomputed independently, tight:** K(Inf→Inf)=12.5 (40 rows),
   K(Inf→Lan)=22.4 (n=7, spread 22.2–22.6), K(Inf→MM)=73.1 (n=8, 72.6–73.5).
3. **Stage-2/3/4 artifacts** previously reproduced byte-identically; evals on file
   (STAGE2/3/4_EVAL.md); the ×1.20 circular claim retracted and documented.
4. **The "~300 vs ~265 hero-regime discrepancy" is NOT a discrepancy** (worry
   withdrawn): NanoMart mirrors fit C=12.52 once real effective stats fold in the
   attacker's panel/hero offense — 12.52×24/1.128 = 266 vs observed 264–266
   (stage4_validate Group 1, ±1–4%). No open absolute-constant problem at T1.

## B. Corrections from this audit (were NOT fully watertight)

1. **"Counter ≈ 3.3×, replace ctr=1.10" was an oversimplification.** The honest
   object is the **per-class-pair constant K(dealer, target)** — passives and
   counters fold into it; no separate ctr may be applied on top. Measured cells:
   K(Inf→Inf)=12.5, K(Inf→Lan)=22.4, K(Inf→MM)=73.1. The "3.3×" is just
   K(Inf→MM)/K(Inf→Lan).
2. **"Non-Inf dealer = Type-2 only" was too pessimistic — it is cleanly
   extractable.** A no-hero MM can't beat a *buffed Gatot* Infantry, but it CAN and
   DID beat naked Lab-Rat targets in the **Gordon battery** (no Vulcanus). Three
   independent clean rows give the non-Inf dealer penalty vs the Inf-dealer table:
   MM→Inf ×7.5, MM→MM ×7.7, Lan→MM ×6.8 → **penalty ≈ ×7 (±10%)**. Bonus
   structure: the six measured cells are consistent with a **factorization
   K(dealer,target) ≈ f(dealer)·g(target)**, f={Inf 1, Lan ≈6.8, MM ≈7.6},
   g={Inf 12.5, Lan 22.4, MM 73.1} (3 cells fit ≈5%; Lan→Inf, Lan→Lan, MM→Lan
   untested → the hypothesis PREDICTS them — a Stage-5 blind test).
3. **The composition count-ladder "N=1 anomaly" is RESOLVED — no re-capture
   needed.** The right lens is **sequential tanking**, not a line fit:
   `total = 33 (first tank, penalized) + 54×(N−2) (middle tanks) + 57 (last one,
   near-solo)` → N=2..5 predicted 90/144/198/252 = observed EXACTLY, and N=1=78 is
   the solo case (no backline → no tanking penalty). All five points exact. Open
   sub-question: post-tank survivors last ~73% of solo time (57/78; backline MM
   2 vs 3 solo) — mechanism TBD in Stage 5.
4. **G_w must be frozen as the MEASURED table, not the cube-root formula.**
   (A_base·L_base)^(2/3) is the best structural form (only one matching the T5
   base-stat jump) but has residuals +6% at T2 and −10% at T6 vs measured
   G_w = {1, 2.68, 4.32, 5.90, ~9.8, 10.89}. Freeze the measured values;
   cube-root serves only to interpolate unmeasured tiers (T7+). Same for G_l:
   freeze the v5-measured table {1.00, 0.996, 0.904, 0.795, 0.770, 0.749, 0.742,
   0.744, 0.757, 0.777} (T1..T10).
5. **The composition constants are measured against a Vulcanus-active defender**
   (2v2/v5_8 Alpaca ran Gatot+Vulcanus). Deterministic cadence → within-set
   comparisons stand (33-flat, +54 steps, ~1.33 mop-up), but Stage 5 must back out
   Vulcanus S2 (+20% every 6th attack ⇒ ×1.033 avg) and S3 (−12% enemy Inf/Lan
   defense on its cadence) before exporting the tanking factor to other defenders.
6. **OCR corrections now formalized in a registry** (applied by the corpus, sources
   untouched): the two T2-Lancer relabels (deployed_class fixed in-file; setup text
   + filenames still say "T2Inf" — registry overrides), the 112003 naked-Infantry
   relabel, the MISSING 3-turn 1-MM battle (manual row, JSON never ingested), the
   unverified T7 row, the "2 named MM = 3 turns" suspect, NanoMart L32/L69 +
   T6vT1=96. See `wos_sim/data/experiments/_corpus/corrections.json`.

## C. Known-open items going INTO Stage 5 (scoped, non-blocking)

- Post-tank ~73% survival factor and the 1.33/unit mop-up (vs 3-turn solo MM) —
  measure-and-model, mechanism unknown.
- Mixed-class backline ordering (Lan+MM together) untested; absorption order
  assumed Inf→Lan→MM.
- K-factorization: 3 predicted cells untested (Lan→Inf, Lan→Lan, MM→Lan).
- Non-Inf ×7 penalty is a 3-row estimate (±10%, turn-band + base-L/H limited).
- Composition Vulcanus backout (B.5).
- Type-2 procs: separate frontier by design (distribution-only, never exact-fit).

## D. The recall problem — structural fix

Martin has repeatedly had to point me at data that already existed (the v4 counter
set, the winner ladders, the troop-stats table, the v5_8 composition set). Root
cause: analytics ran off whatever was in recent conversation memory instead of a
canonical store. Fix shipped with this review: the **Type-1 corpus** at
`wos_sim/data/experiments/_corpus/` — every deterministic battle normalized into
one queryable table (`TYPE1_CORPUS.json` + human `TYPE1_CORPUS.md` + `corpus.py`
query CLI), with the corrections registry applied at build time and coverage
matrices that show at a glance what data exists per class-pair/tier cell.
Standing rule added to the run-stage skill: **check corpus coverage before asking
Martin for any experiment.**

## Verdict

The derivation chain holds under re-audit — nothing load-bearing broke; the
corrections above tighten formulation (K-table), upgrade one pessimistic scoping
(non-Inf dealer), resolve one false anomaly (N=1), and annotate one contamination
(composition/Vulcanus). **Stage 5 is cleared for launch** on the amended spec.
