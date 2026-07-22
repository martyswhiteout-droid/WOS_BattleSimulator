# Stage 3 evaluation — VERDICT: ACCEPT (2026-07-12, evaluator window)

Evaluated per `.claude/skills/run-stage/SKILL.md` eval-3 protocol. Stage 3's
headline is a **negative result** (no per-hit family survives) plus **one
positive sub-law** (g(N)=√N). Guardrail 6 explicitly makes "no family survived"
an acceptable, reportable outcome — the question for the evaluator is whether the
rejection is *earned* (exact, precision-independent, non-fitting) and whether the
one surviving claim is *real*. Both hold.

## 1. Reproducibility — PASS
- Re-ran `stage3_difflaw` + `stage3_run`; `stage3_results.json` and
  `stage3_difflaw.json` reproduced **byte-identically** (sha256:
  e0d4aef8… / 359bff79… — unchanged after re-run).
- Builder's `test_stage3.py` — **6/6 pass**.
- Console summary reproduces the report: 540 families, **0 survivors** on
  INF_MIRROR(17)/INF_CLEAN(24)/INF_ALL(26)/FULL_CLEAN(35).

## 2. Independent recomputation (4 claims, evaluator's own arithmetic) — PASS
Parsed `stage2_constraints.json` directly with my own `Fraction` code (not the
builder's loader):
- **Count law g(N)=√N (attacker):** g(2)/g(1) band [1.4140, 1.4270] ∋ √2=1.4142 ✓;
  g(3)/g(1) band [1.7190, 1.7600] ∋ √3=1.7321 ✓.
- **L32/L69 hard conflict:** both winnerA=5.64144, L=5, D_l=4, H_l=6 (identical),
  rate bands [0.012346, 0.012821] vs [0.014493, 0.015152] — **disjoint**
  (L32.hi < L69.lo), and t_sets 79–81 vs 67–69 independently differ. Real
  uncaptured-variable contradiction. ✓
- **(1,1,1,1) monomial rejection:** A·L/(D·H) → required C(T1 mirror)=
  [0.0806, 0.0809] vs C(T2 mirror)=[0.0291, 0.0294] — **no overlap**; numerator
  grows ∝tier² while rate is flat, so C must collapse ~2.8×. Confirms §3.1. ✓
- **Difference-law solve:** my own Cramer on rows 17/34/29 recovers k=+0.786,
  K=+4.069 — exactly the report's values; blind-predicts 4/24 (INF_CLEAN). ✓

## 3. Precision-independence — PASS (load-bearing)
`stage3_precision`: family gate yields **0 survivors at ±0/±1/±2/±3 turns** on
every subset. The rejection is therefore *fundamental*, not a turn-quantisation
artifact. The pure tier-mirror intersection is empty by exactly one ULP (§3.2,
honestly labelled a precision artifact) but the Exp4 and vs-T2 misses are ≫±3
turns — verified.

## 4. Guardrail check — PASS
- **Gate is feasibility, not fitting:** `run_gate` intersects
  `[lo_i/core_i, hi_i/core_i]`; ACCEPT iff non-empty. No aggregate error is ever
  minimised. Structural constants enumerated over simple rationals.
- **Difference law is solve-then-blind-predict:** 3 solve rows only, exact
  Cramer, then blind exact-band test on the rest — observed data enters only via
  the solve rows (legitimate, like Stage 2 `implied_*`). No outcome leakage.
- **Ambiguities branched:** both S2 branches (`plain`, `nextatk`) tested for
  every family.
- **Failures reported as failures:** the "closest shape" (mem_A/((A+D)(D+H))) is
  explicitly DIAGNOSTIC and still labelled REJECTED (1/24, C-spread 1.48×).
- **Data faults quarantined, not fitted:** L32/L69 and T4/T6-vs-T1 excluded from
  the gate and never used to reject a family.
- **Scope:** all writes inside `wos_sim/formula_research/`.

## Non-blocking notes
1. `stage3_precision.py` line 105 prints "518 families" but calls
   `all_families()` (540) — stale print label only; the robustness result covers
   the full 540. Cosmetic.
2. The difference-law solver picks band **midpoints** for its 3 solve rows (not
   endpoint-robust). This does not affect the verdict: §3.1's measured
   local-vs-global exponent contradiction kills the whole monomial+difference
   space analytically, independent of which point in each solve band is chosen.
3. `stage3_difflaw` `Cstar` dead-branch (`if False else None`) at
   stage3_run.py:85 is harmless leftover.

## What Stage 3 establishes (for Stage 4)
- **REJECT** all 540 enumerated per-hit forms (ratio-monomial, named-physical,
  difference, two-factor) — exact + precision-independent.
- **KEEP** g(N)=√N as an exact attacker-side sub-law (defender-side is 0.95×√N,
  same shape, base inflated by the near-tie).
- The per-unit damage form is **not identifiable from the current corpus**: within
  a class, Attack/Lethality/tier are collinear, and the only stat isolation
  (Exp4) is all at T1 (local). The report's #1 ask — **de-collinearise Attack vs
  Lethality across tiers** — is the correct next experiment.

**ACCEPT.** Stage 3 is a sound, honest elimination. The negative result is earned
and the √N sub-law is real. The deadlock is a genuine *identifiability* limit of
the corpus, not a search failure — which is exactly what the new Gatot/Lab Rat
stat-isolation battles are positioned to break (see `STAGE4_SPEC.md`).
