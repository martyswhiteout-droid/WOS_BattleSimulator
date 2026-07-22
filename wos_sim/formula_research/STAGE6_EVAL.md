# Stage 6 evaluation — VERDICT: ACCEPT (2026-07-17, evaluator window)

Evaluated per the run-stage eval protocol. Builder and evaluator shared the same
232-row corpus state (no provenance drift, unlike eval-5). This stage contains
the most ambitious claims of the program — a two-regime Gatot-kit model with an
impossibility proof — so the recomputation pass targeted exactly those.

## 1. Reproducibility — PASS
- `stage6_tables`: all frozen cells re-derive from the corpus (≤0.02% display
  rounding); `stage6_tables.json` **byte-identical across a double `--emit`**
  (sha256 b8125dfe… twice).
- `stage6_gatot`: both G_w^MM branches (1.0 and 1.17) reproduce — B(Mueller) =
  201.95 / 172.32, B'(FarSeer) = 30.15 / 25.71, all five consistency checks
  PASS in both branches, exp-decay the sole surviving family (1/5 solves).
- `stage6_validate`: **ALL 12 GATES PASS, exit code 0**; 232/232 rows accounted
  (94 A6 + 14 B6 + 3 C6 + 23 D6 + 3 E6 + 12 H6 + 21 composition + 62 stated
  exclusions).
- **G12 backtest PASS** (7/13, unchanged); **predictor suite 105 passed / 8
  skipped / 2 xfailed** (unchanged); `stage5_law` still re-derives at 0.0%
  drift (the stage-5 deliverables provably untouched, as claimed).

## 2. Independent recomputation (own arithmetic) — PASS
- **Budget solve:** r1(T6 threshold MM) = 835.26/90.11 = 9.2694 ✓; pool =
  291.36 ✓; B ∈ (201.93, 201.94] vs builder's (201.94, 201.95] — a 0.01
  endpoint-convention difference, immaterial; 21-mob cap check passes with the
  same +7.5 margin.
- **√N impossibility:** need net(22) ≥ 1.982; net(21) ≤ 0.194; √N gross step =
  1.000; monotone-absorb bound net(22) ≤ 1.194 < 1.982 — **the inequality is
  real and airtight**. The refutation of √N inside the shield regime (and hence
  of all three spec-listed candidate families under √N) is arithmetic fact,
  not judgment.
- **Exp-decay blind points:** S(58.46) = 1.337 ∈ (1.140, 1.414] ✓ and
  S(61.35) = 1.284 ∈ (1.196, 1.484] ✓ — both genuinely blind (solved from
  T1+R11 only).
- **S-band construction:** T1_102 upper bound reproduces exactly (d = 13.94,
  S_hi = 5.732) including the load-bearing Vulcanus folds (S2 ×1.2 cadence,
  S3 ×0.88 pool).

## 3. Guardrails — PASS
- **Enumeration, not regression:** six families, constants solved from 1–2
  point minimal subsets, accepted only on all-band pass; five families
  rejected with zero passing solves each; the raw-(unfolded)-branch that kills
  everything is reported rather than buried.
- **Branch discipline exemplary:** the G_w^MM ∈ {1.0, 1.17} entanglement is
  carried through the ENTIRE budget analysis as two parallel branches, both
  passing — the conclusion is branch-invariant, which is the strongest form of
  the ambiguity guardrail.
- **Honest opens, stated with their discriminators:** B's defender anchoring
  (±20%, no clean scaling — `gatot_gate_unmodeled` flag elsewhere), the
  hero-led-mob untested cell, the K(Lan→Inf) T3-vs-T6 tension (+33% with the
  ordinary-vs-FC1 caveat), the reverse-race residual (~2.5×), the
  linear-volley-vs-√N boundary — each with the one-battle experiment that
  would close it.
- **Scope:** api.py additive (`law_version: "stage6"`, `predict()` untouched);
  the `stage5_composition.py` `law=` injection proven byte-identical at
  default; corrections.json annotations proven output-neutral (corpus rebuilt
  byte-identical twice).
- **Genuine new science in-stage:** the TWO-REGIME split proven irreducible
  (S not a function of total rate; not a per-hit law; budget inapplicable to
  hero-led dealers); the thresholds independently imply K(Lan→Inf) ≈ 91 at T6
  (+8.8%, inside the factorization band) — a fourth cross-check of the
  factorization; the razor-thin F_MM_32 cap margin (+0.59) surviving is a
  severe test the model could easily have failed.

## 4. Verified side-findings
- The **3 failing stage2-era tests** are confirmed pre-existing and are
  actually *stale-anomaly assertions*: `test_constraint_audit_exposes_
  incompatible_t5_clocks` asserts the L32/L69 conflict EXISTS — Martin's
  2026-07-14 counter-correction dissolved it, so the test now fails because
  the data improved. Same family for the other two (71→70 ledger rows after
  the L21 dedup). Import-graph independence from stage-6 files verified.
  **Recommendation (non-blocking):** refresh those three tests with a dated
  annotation to assert the corrected state, so the suite is green end-to-end.
- B6 improvement (6→9 in-band) comes precisely from the class-keyed G_w^Lan
  fix (R09: 40.5→10.0 pred vs [9,11]; R10: 44.5→6.5 vs [6,7]) — the spec's
  promised improvement, delivered and verified in the gate output.

## Verdict
**ACCEPT.** The class-keyed law is frozen with per-cell provenance and
validated corpus-wide with zero regressions and real improvements (A6 85→87,
B6 6→9, races 4/4). The Gatot kit is solved as far as the data permits — an
exact budget gate reproducing all eight knife-edge battles with √N proven
impossible in-regime, plus a saturating exp-decay candidate for hero-led
dealers with two blind passes — and every remaining unknown is named, bounded,
and paired with its discriminating experiment. With eval-6, **Stages 1–6 are
all ACCEPTED: the deterministic Type-1 program is complete and shipped behind
the seam.** The remaining frontier is Stage 7: the Type-2 proc layer
(distribution-only) plus the three mechanism questions (§6 of the report).

## ADDENDUM (2026-07-18) — Codex independent QA: verdict amended

Codex's clean-room QA (232 rows, `qa_codex/`) exposed a blind spot that THIS
EVAL shares: **the corpus-wide validation was one-directional** — it scored the
observed winner's kill clock and never asked "does the law pick the right
winner from stats alone?" except on the 4 ENIF1b races. Worse (confirmed by
code-reading): the production seam `predict_battle` runs a real two-sided race
but WITHOUT the Gatot-kit gate → it mis-calls winners against Gatot-defended
Infantry. That is a live P0 defect the eval should have caught by demanding a
corpus-wide winner gate. The ACCEPT stands for what was validated (the one-way
clocks, tables, kit-in-validator — all reproduced and still correct as
MEASUREMENTS); the assembly's winner-call coverage was NOT validated, and the
eval's gate list should have included it.

Evaluator reconciliation of Codex's miss list (2026-07-18 checks):
1. **The F1 cluster is REAL** (MuellerAlpaca_v5 R02–R09 + T7_151127): the
   reverse-race inequalities require a defender-side amplification for
   Alpaca's Lv64/S8 Gatot vs Infantry dealers with measured-G_w lower bounds
   M ≥ 1.29 (T4) / 1.74 (T5) / 2.58 (T6) and extrapolated-G_w bounds up to
   ≥ 5.96 (T10). NOTE: T2's bound is 0.39 (<1) — that row's winner call is
   already correct without any M. The bounds RISE with dealer tier ⇒ a single
   constant M is NOT supported; kit-LEVEL dependence is confirmed
   (Mueller's L1 Gatot ≈ ×1.03 from the anchor set; Alpaca's L64 ≥ ×2.58).
2. **Several 10%+ rows are QA-implementation differences, not law defects**:
   e.g. T5InfvT1Inf — Codex +30.4%, our conventions +5..9%; T1InfvT6Inf —
   Codex +11.9%, ours −1% (the ×0.88 S3 fold is visibly absent from Codex's
   number; its Vulcanus detection appears to miss ledger-shaped hero fields).
   A row-by-row reconciliation pass is required before any table changes.
3. Near-even mirror flips are the intentional coin_flip zone (standing rule
   #4) — they belong under a coin_flip carve-out in the winner gate, not in
   the failure count.

Remediation endorsed (see Martin's remediation-window plan + amendments):
two-sided winner gate with coin_flip carve-out (A1+A4); seam wires the
EXISTING kit + ABSTAINS (`gatot_gate_unmodeled` → uncertain verdict) on
strong-Gatot × Inf-dealer cells rather than inventing M (no-fudge); M_gatot
pinned later by one discriminator battle (a Mueller Infantry config that
actually BEATS Alpaca's Gatot-Inf gives the upper bound). Verdict language:
**ACCEPT (measurements + tables) / winner-call assembly REOPENED as Stage 6.5.**

