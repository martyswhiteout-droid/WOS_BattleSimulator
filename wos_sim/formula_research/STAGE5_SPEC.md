# Stage 5 spec — assemble the predictor + the composition layer

**Status (2026-07-13):** the deterministic **per-unit Infantry law is complete** and
the **composition layer is now measured** (frontline binary penalty + linear backline
mop-up). Stage 5 is not more derivation — it is **freeze → extract → assemble →
validate → wire to the app**, plus one small composition derivation. No new
experiments are required for the core (see §Data); the only pending captures are
B3 k=2/3 confirmation (already in `Meuller_Alpaca_v5_8_Battle`) and an optional
Lancer-backline (also present).

## What is CONFIRMED (freeze these)

**Per-unit law (amended per `STAGE5_PREFLIGHT_REVIEW.md` — K-table formulation):**
```
turns = K(dealer_cls, target_cls) · D_l·H_l / (A_w·L_w) · G_w(τ_w) · G_l(τ_l)

  K(dealer,target) — per-class-pair constant; passives/counters FOLD IN (no separate ctr!):
      measured:  K(Inf→Inf)=12.5 (40 rows)   K(Inf→Lan)=22.4 (n=7, 22.2–22.6)
                 K(Inf→MM)=73.1 (n=8, 72.6–73.5)
      clean Gordon rows: K(MM→Inf)≈93, K(MM→MM)≈567, K(Lan→MM)≈500
      ⇒ non-Inf dealer penalty ≈ ×7 (±10%); factorization HYPOTHESIS
        K ≈ f(dealer)·g(target), f={Inf 1, Lan ~6.8, MM ~7.6}, g={12.5, 22.4, 73.1}
        (3 cells fit ≈5%; PREDICTS the untested Lan→Inf, Lan→Lan, MM→Lan — blind-test it)
  G_w(τ_w) — FREEZE THE MEASURED TABLE {1, 2.68, 4.32, 5.90, ~9.8, 10.89} (T1..T6);
      (A_base·L_base)^(2/3) is the structural interpolant for T7+ ONLY (residuals
      +6% T2 / −10% T6 — do not substitute it where a measurement exists)
  G_l(τ_l) — FREEZE the v5-measured table {1.00,0.996,0.904,0.795,0.770,0.749,
      0.742,0.744,0.757,0.777} (T1..T10)
  effective stat = REAL base (docs/TroopStats) × (1+panel); HP = D·H (exact, ±1%)
  count law g(N)=√N on offense (Stage 3)
```
- All K/G constants derive from **Vulcanus-free** data (audit table in the review).
- Retracted for good: "×1.20/tier multiplicative base" (circular); "ctr=1.10 as a
  separate factor" (double-counts — the K-table absorbs passives).
- Non-Inf dealers ARE cleanly extractable (Gordon battery vs naked targets); only the
  Vulcanus-carrying rows (RFJ, Alpaca-T1MM, NanoMart MM) need the Type-2 caveat.

## The COMPOSITION layer (NEW — measured, `Meuller_Alpaca_v5_8_Battle`)

Against a fixed defender, a 1-Infantry-front + backline army resolves as:

| observation | value | source |
|---|---|---|
| Frontline Infantry death, **solo** | 78 | k=0 |
| Frontline Infantry death, **with ANY backline** | **33 (constant)** | k=1..10, MM and Lancer identical |
| Backline mop-up after tank falls | **~1.33 turns / unit** | battle end = 33 + 1.33k |

**Law:** the frontline tank takes a **binary "tanking penalty"** (survives less when
shielding a backline), **independent of backline count and class**; the backline is
then cleared **linearly**. This REFUTES both the headcount-pooling and triangle-class
hypotheses. Absorption order Inf→Lan→MM (GAME_RULES): Infantry is the tank.

**Sequential-tanking decomposition (resolves the "N=1 anomaly" — no re-capture
needed):** the N-Infantry ladder is EXACTLY
`turns(N) = 33 (first tank, penalized) + 54·(N−2) (middle tanks) + 57 (last, near-solo)`
→ predicts 90/144/198/252 for N=2..5 (all observed exactly); N=1 = 78 is the solo
case (no backline ⇒ no penalty). Open sub-question: post-tank survivors last ~73%
of solo time (57/78; backline MM 2 vs 3 solo) — mechanism TBD.

The composition layer is an **algorithm on top of the per-unit law**: (1) order troops
by absorption tier, (2) each successive tank's life = per-unit turns × tanking factor,
(3) mop up the backline at the measured linear rate. The constants (33, 54, 57, 1.33)
are defender-specific and must be *computed* from the per-unit law, not hard-coded.
⚠️ **Vulcanus caveat:** the composition defender ran Gatot+Vulcanus (audit §B.5) —
back out Vulc S2 (×1.033 avg) and S3 (−12% enemy Inf/Lan def, its cadence) before
exporting the tanking factor to other defenders.

## Stage 5 tasks (builder)

1. **Freeze the per-unit law** as a re-runnable function `predict_turns(att, def)` in
   `wos_sim/formula_research/` (real-stat loader; K-table, MEASURED G_w/G_l tables,
   √N; cube-root interpolation for T7+ only). Per-row validation harness vs every
   exact-turn 1v1 row in the corpus (target ≤3%).
2. **Finalize the K-table**: recompute all six measured cells from the corpus
   (Inf→Inf/Lan/MM from v4 + the 12-row anchor; MM→Inf, MM→MM, Lan→MM from the clean
   Gordon rows — NOT the Vulcanus rows). **Blind-test the factorization
   K≈f(dealer)·g(target)** against any available data for the 3 unmeasured cells
   (Lan→Inf, Lan→Lan, MM→Lan; NanoMart rows = directional only). The
   Vulcanus-carrying non-Inf rows (RFJ, Alpaca-T1MM) serve as corroboration with
   S2/S3 backed out, Type-2 caveat.
3. **Derive the composition algorithm**: tanking penalty (solo-vs-tanking factor) +
   linear backline mop-up, expressed in per-unit-law terms so it generalizes beyond the
   one Alpaca defender. Validate against `Meuller_Alpaca_v5_8_Battle` (front=33 flat,
   end=33+1.33k) and the 2v2 set.
4. **Assemble** per-unit + composition into `predict_battle(att_army, def_army)` →
   winner + turns + survivors. **Blind-validate** on held-out Gordon rows and the
   NanoMart tier ladder (directional).
5. **Wire behind the seam** `wos_sim/predictor/api.py` (do NOT touch the engine
   elsewhere; the seam is non-mutating, CRN-seeded per ENGINE_INTERFACE.md), so the app
   can call the new law. Run `py -m wos_sim.backtest` (gate G12; pass count may only
   increase).

## Data — MANDATORY: load through the Type-1 corpus

**`wos_sim/data/experiments/_corpus/`** — `TYPE1_CORPUS.json` (canonical, corrections
pre-applied) + `TYPE1_CORPUS.md` (human master table + coverage matrices) +
`corpus.py` (query API/CLI) + `corrections.json` (OCR override registry). Built by
`build_corpus.py`; **re-run it after any new report ingestion**. Rule: check the
corpus coverage matrix BEFORE requesting any new experiment from Martin.

Underlying sources (for provenance; do not re-parse ad hoc):
- `docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json` — real base stats.
- Per-unit: `Lab Rat/`, `MuellerAlpaca/`, `FarSeerGatot_v3/`, `MuellerAlpaca_Gatot_v4/`,
  `MuellerAlpaca_Gatot_v5/`, `AlpacaGatot_FC1_T6_LanMM/` (all Vulcanus-free).
- Non-Inf clean: the Gordon battery rows (in `Lab Rat/`). Non-Inf Vulcanus-flagged:
  `RFJPlayer…`, `Alpaca_1v1_T1MMFC1…`.
- Composition (Vulcanus-flagged): `Meuller_Alpaca_v5_8_Battle/`, `MuellerAlpaca_Gatot_2v2/`
  + the manual rows in `COMPOSITION_TESTS_manual.md`.
- NanoMart (Vulcanus regime): via `formula_research/ledger_dataset.json` (Stage-2-accepted).

## Guardrails (same as run-stage, plus)

- No fabrication; every number from a re-runnable script.
- Deterministic pieces: exact-fit. Proc/Type-2 pieces (non-Inf dealer, Vulcanus,
  FC-procs): **distribution / Monte-Carlo only, never exact-fit** (calibration philosophy).
- **OCR discipline:** any single result that contradicts a consistent pattern → flag to
  Martin to verify the screenshot BEFORE modelling it; never fit an anomaly.
- Scope: `wos_sim/formula_research/` for derivation; `api.py` for the seam only.

## Deliverables
`stage5_law.py` (frozen per-unit predictor), `stage5_composition.py` (the army
algorithm), `stage5_validate.py` (per-row blind validation), `STAGE5_REPORT.md`
(the assembled law, per-row tables, where it holds/breaks, Type-2 boundary), and the
`api.py` wiring. Evaluate via `eval-5`.
