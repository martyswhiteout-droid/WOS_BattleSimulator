# Stage 4 evaluation — VERDICT: ACCEPT (2026-07-12, evaluator window)

Evaluated per `.claude/skills/run-stage/SKILL.md` eval-4 protocol. Stage 4's job was
to solve the TIER law using the real base-stat table, re-confirm within-tier, and
report honestly what it can/can't close. It does all three, with a genuine novel
result (winner-tier cube-root damping) and independent cross-validation.

## 1. Reproducibility — PASS
Re-ran `stage4_law` and `stage4_validate` (module form). Console reproduces the
report exactly: within-tier **C = 12.522** (40 rows, max +3.1%); winner-tier ladder
**G = 1.000 / 2.683 / 4.324 / 10.890** at τ=1/2/3/6; validation groups
(within-tier, cross-tier 9/9, the three flagged defects) all reproduce. No JSON
artifact to hash (outputs are the report + console); numbers match.

## 2. Independent recomputation (my own arithmetic, not their loader) — PASS
- **G(3):** parsed the 8 `InfT3>InfT1` rows myself → G = [4.30…4.37], median
  **4.324** ✓ (matches).
- **Gordon held-out Inf mirror:** blind-predicted `12.522·4·6/(1.021·1)` = **294.3**
  vs observed [285,287] → **+2.9%** ✓ (matches the "+3%"; Gordon's skills not used —
  a real out-of-sample check).
- **Cube-root reading:** G_w vs (A_base·L_base)^(2/3) → ratio 1.00/1.06/1.00/0.90 at
  T1/T2/T3/T6 ✓ — the "damage ∝ (A·L)^{1/3}, panels multiply in full" statement is
  internally consistent.
- **Beast T2 cross-check:** per-kill 69.72 / local 26.03 = **G = 2.678**, computed
  from a *different instrument* (18 sequential beast kills) than the 1v1 T2 (2.683).
  Agreement to **0.2%** — the single most convincing datum in the report.

## 3. Guardrail check — PASS
- **No fabrication / reproducible:** every figure re-runs.
- **No regression:** C is a **median**, not a fit; G is **measured** at τ=2,3 then two
  simple forms proposed. The forms are not error-minimised over many rows — they are
  matched to the measured points and **branched** (linear `(5τ−2)/3` vs power
  `τ^{4/3}`; agree <3% to T3, diverge ~15% at T6 where the lone datum is soft).
- **Observed-outcome leakage — honestly bounded:** the back-solve (Q/C/G) legitimately
  uses observed turns (labelled). The headline "cross-tier 9/9 ≤1%" is **mostly
  in-sample** — 8 of the 9 are the `InfT3>InfT1` cluster from which G(3) was derived,
  which the builder **explicitly discloses** as "8-predictions-from-1-constant." The
  genuinely blind support is the **beast T2 (2.678), beast T1 (1.00), and Gordon
  mirror (+3%)** — real, and they pass. No hidden leakage; the disclosure is exemplary.
- **Failures reported as failures:** THREE defects flagged, none fitted — low-D·H
  (glass-cannon) losers (−50…−98%), non-Infantry damage-dealer (−88%), and the
  loser-tier `G_l` (left OPEN; the only datum, MuellerAlpaca T2, is the flagged
  anomaly, correctly not allowed to drive a fit).
- **Self-correction:** the builder **independently caught and retracted the circular
  "×1.20/tier multiplicative base" claim** (guardrail-3 violation — it fed observed
  turns back to confirm an assumed form). Retracting a convenient prior conclusion is
  a strong integrity signal.

## 4. Consistency with independent (post-Stage-4) evidence
Stage 4 started before the AlpacaGatot threshold + FarSeerGatot cross-class data
existed. Its flagged defects are exactly what that new data addresses, with no
conflict:
- Its **non-Infantry-attacker** defect (MarT1>InfT1 −88%, "constant is
  Infantry-specific") matches the threshold finding that a Marksman dealer's
  effective damage ≠ its A·L under the Infantry C.
- Its **low-D·H loser** defect (Inf>Lan/MM slower than predicted, even in the MM
  mirror) is correctly diagnosed as a target-HP problem, **not** the counter (the
  counter would speed Inf→Lan up, but it's slower) — consistent with my earlier read.
- Note for Stage 5: the counter is **~2× (threshold-proven), not the +10% (ctr=1.10)**
  this report uses; that only affects the already-flagged cross-class rows, so it does
  not undermine the accepted Infantry-cell result.

## Addendum — hallucination audit of §6 "missing ladders" (Martin's request)

Adversarial re-read of every claim. **No fabrication found** — C, G_w=1/2.68/4.32/10.89,
beast-T2=2.678, the single 1v1-T2 row (62 turns → G=2.683 exactly), Gordon +2.9%, the
cube-root reading, and the ×1.20 retraction all reproduce from the data. The DERIVATION
is watertight. **But two of the five §6 gaps are redundant/wrong** (Martin was right):

1. **§6 "G_w ladder InfT4..InfT10" is NOT needed — the data already exists.** The
   FarSeerGatot_v3 **Lancer/MM-loser** ladders (winner Inf T1–T6 vs a FIXED T1 loser)
   recover G_w by normalizing each ladder to its own T1 (the constant loser factor
   cancels). Recovered G_w (Lancer / MM) vs the Inf-loser values:

   | τ_w | Lan-recov | MM-recov | Inf-loser | (5τ−2)/3 | τ^4/3 | (A·L)^{2/3} |
   |--|--|--|--|--|--|--|
   | 2 | 2.65 | 2.75 | 2.68 | 2.67 | 2.52 | 2.52 |
   | 3 | 4.31 | 4.54 | 4.32 | 4.33 | 4.33 | 4.33 |
   | 4 | 5.90 | 5.87 | — | 6.00 | 6.35 | 6.35 |
   | **5** | **9.95** | **9.63** | — | 7.67 | 8.55 | **9.65** |
   | 6 | 10.83 | 11.56 | 10.89 | 9.33 | 10.90 | 12.08 |

   T2/T3/T6 match the independent Inf-loser/beast values → the normalization is valid.
   And **T5 (where base A jumps 4→6) matches ONLY the cube-root (A·L)^{2/3}=9.65**, not
   the linear (7.67) or τ-power (8.55). So the recovered ladder **resolves the report's
   own "linear vs power" ambiguity in favour of cube-root-of-real-base** — using data
   the builder already had but treated as pure "out-of-scope defect." Incompleteness,
   not fabrication, but it means §6 gap #1 is essentially already closed.

2. **§6 "non-Inf-clocked hero" is unnecessary in a 1v1.** If a Gatot Infantry *loses*
   1v1 to a non-Inf, King's Bestowal still counts the turns (the Infantry swings each
   turn until it dies) and `turns = HP_Inf / damage_nonInf` → that measures the
   non-Inf's damage. The AlpacaGatot threshold data already does this (N-v-1); a clean
   1-v-1 (one strong Marksman/Lancer beats one Gatot Inf) would pin the constant. No
   Lancer/MM-clocked hero needed — the report over-specified this.

Genuinely-still-open (not redundant): loser-tier G_l (§6 #2 — only MuellerAlpaca data,
anomalous), low-D·H HP term (§6 #3 — needs varied D/H on Lan/MM losers), and the
MuellerAlpaca T2 re-capture (§6 #5). So **3 of 5 gaps are real, 2 are already answered.**

## Verdict
**ACCEPT** (derivation is sound and reproducible; §6 next-steps partially redundant, corrected above). The winner-tier **cube-root damping** `G_w` is a genuine, reproducible,
independently cross-validated result that solves the tier law for the
**Infantry-winner / Infantry-(or high-D·H)-loser** cell to ≤1–3%, and the report is
scrupulously honest about the three cells it does *not* close and about in-sample vs
blind support. Open items (G_w beyond T3, loser-tier G_l, low-D·H HP term, non-Inf
constant) are correctly scoped as the next ladders — several now capturable with the
AlpacaGatot / FarSeerGatot rigs. This is a strong, non-overreaching stage.
