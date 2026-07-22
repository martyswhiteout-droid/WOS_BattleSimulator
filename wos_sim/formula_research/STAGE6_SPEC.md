# Stage 6 spec — class-general law + the Gatot-kit model (consolidation)

**Status:** proposed 2026-07-17, after eval-5 ACCEPT (`STAGE5_EVAL.md`) and the
E-NIF battery (`wos_sim/data/ENIF/ENIF_ANALYSIS.md`). Stage 5 froze the law as
known on 07-14; the E-NIF week then measured everything Stage 5 had to flag as
hypothesis. Stage 6 folds those measurements in, derives the one remaining
mechanism (Gatot's kit), and re-validates corpus-wide. **No new experiments are
required**; one optional splitter battle is listed at the end.

## What changed since Stage 5 froze (all measured, all in the corpus)

1. **Dealer tier-damping G_w is CLASS-DEPENDENT** — the single Infantry table
   Stage 5 applies to every dealer is wrong for non-Inf dealers at τ≥2:
   | τ | 1 | 2 | 3 | 4 | 5 | 6 |
   |---|---|---|---|---|---|---|
   | Infantry (measured, S4/S5) | 1.000 | 2.680 | 4.323 | 5.884 | 9.791 | 10.889 |
   | Lancer (measured, E-NIF3) | 1.000 | — | 1.091 | — | — | 1.625 |
   | Marksman (bounded, E-NIF2-redo) | 1.000 | — | ~1 (entangled) | — | — | ≤1.17 |
   The cube-root structure is an Infantry property. Unmeasured Lancer rungs
   (T2/T4/T5): interpolate monotonically with meta flags; Marksman: G=1 with a
   stated [1, 1.17] band, flagged (entangled with S_gatot — see below).
2. **Target tier-damping G_l is CLASS-DEPENDENT** (Stage 5 already keyed it):
   Infantry T1–T10 measured; Marksman measured STEEP {1.051, 0.249, 0.085} at
   T1/T3/T6 (E-NIF2 R05–07); Lancer measured only T2 (0.654). Same flag policy.
3. **The Gatot-kit suppression is MEASURED and SATURATING** — the MM→Gatot-Inf
   ladder gives S_gatot ≈ {4.73, 2.23, 1.17} at dealer per-turn damage scales
   {~2.9, ~13.9, ~48.6 HP-units/turn} (T1/T3/T6 vs the same 291.4-pool target).
   It replaces Stage 5's binary "proc-gated" flag for Gatot-led Infantry targets.
4. **K-cells confirmed at full panels:** K(Lan→MM)=489 (−2% vs 500),
   K(MM→Inf)=90.1 clean (R02), K(MM→MM)=567 at +1072% panels. Panels multiply in
   full for ALL THREE dealer classes.
5. **Alliance buff is a real panel variable** (+23pp A/D, +10pp L/H observed for
   RFJ): panels must come from the battle report itself, per battle. It flipped
   a knife-edge winner, and the K-table predicted BOTH sides of the flip.

## Stage 6 tasks (builder)

0. **Load everything through the corpus** (232 rows; rebuild after any ingest).
   Guardrails as always (bottom).
1. **`stage6_tables.py` — class-keyed tables with provenance.** Replace the
   single-G_w law with `G_w(dealer_cls, τ)` and `G_l(target_cls, τ)` per the
   tables above, each cell carrying {measured | interpolated | bounded} + source
   row ids. Update the K-table cells per #4. Emit a machine-readable
   `stage6_tables.json` the predictor loads (single source of truth).
2. **`stage6_gatot.py` — derive the Gatot-kit model (the one open mechanism).**
   SOLVE a saturating suppression form from the three measured S_gatot points —
   candidate families (enumerate, don't regress): fixed per-turn absorb
   `S = dmg/(dmg − a)`; shield ∝ defender Attack `a = 0.06·A_def·k`; capped
   absorb. Acceptance = the 3 points within their turn-quantization bands, THEN
   **blind-predict the eight count-threshold battles** (21/22 T6MM, 40/41 T6Lan,
   32/33 T3MM, 66/67 T3Lan vs Gatot T1 Inf): the model must produce the
   observed knife-edge (N−1 capped at 1500, N wins in the observed turns, with
   √N stacking). Stage 5 §5 hypothesized exactly this — prove or refute it.
   If no enumerated family passes, report the failure honestly and leave the
   thresholds out-of-scope.
3. **`stage6_validate.py` — the full residual map.** Blind-predict every
   scoreable corpus row (232-row state) with the updated law: per-instrument
   buckets, ceil-gate for exact-turn rows, stated bands for Vulcanus-regime and
   factorized cells, composition rows via the Stage-5 algorithm. Nothing may
   regress vs the Stage-5 report's buckets (within-instrument ≤3%, Gordon ≤3%,
   NanoMart SY-dealer ≤1.3%); improvements expected on non-Inf dealers at τ≥2.
4. **Housekeeping (small, do last):** remove/annotate the orphaned L21 registry
   entry (duplicate-of-L19, matches zero rows); note the R03/R04 Mueller-MM H
   cosmetic (118.6→128.6); document the `troop_catalog.py` vs `docs/TroopStats`
   divergence (engine consumers of the deterministic path MUST use the docs
   table — do not silently edit troop_catalog, it feeds the legacy engine).
5. **Seam:** update the api.py deterministic entry points to load
   `stage6_tables.json` (additive change only; `predict()` untouched; meta
   gains `law_version: "stage6"`, per-cell provenance flags surface in meta).
   Run `py -m wos_sim.backtest` (G12 may only improve) + the predictor suite.
6. Deliverables: `stage6_tables.py` + `stage6_tables.json`, `stage6_gatot.py`,
   `stage6_validate.py`, `STAGE6_REPORT.md` (tables with provenance, the
   Gatot-kit result or honest failure, the 232-row residual map, gates).
   Evaluate via `/run-stage eval-6`.

## Optional data (NOT blockers — list for Martin only if he asks)

- **The splitter battle**: one T6 MM vs the GORDON-Mueller Infantry — separates
  G_w^MM from S_gatot exactly (K_eff = 93·G_w^MM(6) with no Gatot in the loop).
- Lancer G_w rungs T2/T4/T5 and Lancer G_l rungs T3+ — turn interpolated cells
  into measured ones.
- JSONs for the two remaining verbal rows (2 naked Inf = 8, 3 naked MM = 5).

## Out of scope (unchanged policy)

Type-2 procs (Vulcanus folds beyond deterministic cadence, FC3+ troop skills,
T7+ class procs) remain distribution-only — that is Stage 7, the last frontier.
The −6.5% Vulcanus-dealer systematic stays a documented band, not a fit.

## Guardrails (same as all stages)

No fabrication (every number from a re-runnable script in
`wos_sim/formula_research/`); no regression/best-fit (enumerate + solve from
minimal subsets, accept only on blind prediction); observed outcomes never
inputs; ambiguity → branch; failures reported as failures; scope =
`formula_research/` + `api.py` seam only; OCR-anomaly rule (flag Martin before
modelling any physically-odd row); corpus discipline (check coverage before
requesting data; rebuild after ingest).
