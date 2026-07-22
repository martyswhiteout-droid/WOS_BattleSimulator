# Stage 2 evaluation — VERDICT: ACCEPT (2026-07-11, evaluator window)

Evaluated per `.claude/skills/run-stage/SKILL.md` eval-2 protocol.

## 1. Reproducibility — PASS
- Re-ran `parse_ledger.py` + `stage2_backsolve.py`; `stage2_constraints.json` and
  `ledger_dataset.json` reproduced **byte-identically** (sha256 verified:
  f5d3c111… / cb0fa25a…).
- Builder's unit tests: `test_stage2_backsolve.py` — **11/11 pass**.
- Pipeline summary reproduces: 71 battles, 61 clocked; kinds = 39 exact_1v1,
  12 exact_clean_multi, 2 winner_exact_loser_piecewise, 8 aggregate,
  10 survivor_only; conflicts: none.

## 2. Independent recomputation (3 rows, evaluator's own arithmetic) — PASS
- **T1InfvT1Inf (T=264)**: winner rate [1/264, 1/263) = [0.0037878788,
  0.0038022814) ✓ exact. Loser plain bound <1/(264+44·0.2)=1/272.8 =
  0.0036656891 ✓. Next-attack branch: 43 events at 6k+1 ≤ 264 → <1/274.95 =
  0.0036370249 ✓ — boundary count handled correctly.
- **T1LanvT1Lan (T=30)**: [1/30, 1/29) ✓; loser <1/31 ✓; nextatk 4 events →
  <1/31.2 = 0.032051282 ✓.
- **1v2 T1LanvT1Inf (T=55-57, Vulcanus side wins)**: lo = 1/W(57) = 1/58.8 =
  0.017006803 ✓; hi = 1/W(54) = 1/55.8 = 0.017921147 ✓ — S2 weights correctly
  applied to the Vulcanus side only.

## 3. Guardrail check — PASS
- **No fitted constants**: every quantity is an exact-rational consequence of
  observables + confirmed mechanics; `implied_*` labelling respected.
- **Intervals, not points**, wherever turn bands exist; loser damage emitted as
  inequalities (winner-uninjured bound) — honest use of one-sided information.
- **Ambiguities branched, not picked**: S2 cadence (branch B *derived* refuted
  by 32 rows — evidence listed, not assumed), S2 next-attack +5% (OPEN, both
  branches emitted per row), S2 kill semantics (OPEN), pool-vs-unit overkill
  (OPEN, both branches for the 2v1 defeats), count law g(N) left symbolic.
- **Assumptions documented with evidence** (1 event/side/turn from S2=floor(T/6);
  power column excluded with a demonstrated non-linearity counterexample).
- **Scope**: stage-2 deliverables confined to `wos_sim/formula_research/`.

## Notes for Stage 3 (non-blocking)
1. Exploratory candidate files exist in `ENGINE_REBUILD/formula_research/`
   (candidate_affine_c6, power_law_c5/c6, best_model.json, timestamps ~18:0x —
   BEFORE stage-2 completion at 20:38). They are not part of the Stage-2
   deliverable and were not evaluated; Stage 3 must not inherit their constants
   without re-deriving under the exactness gate.
2. The corpus now includes the Exp4 stat-buff isolation rows, SetA/SetB
   side-swap + no-hero rows, and SetC count rows (1v3/1v5/2v2/3v1, 10v10) —
   excellent discriminating power for Stage 3's count-law and stat-term tests.
3. Builder also fixed a real Stage-1 parser bug (Vulcanus tag regex dropped all
   tags; kills field added) — fix verified by reproduction.

**ACCEPT.** Stage 2 output is fit to serve as the sole input constraint set for
Stage 3 family elimination.
