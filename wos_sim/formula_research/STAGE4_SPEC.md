# Stage 4 spec — solve the TIER law (within-tier form confirmed; real stat table in hand)

**Status (2026-07-12, revised after MuellerAlpaca + the real stat table):** the
*within-tier* per-unit form is confirmed with REAL Lethality/Health. The *cross-tier*
law is the open problem, and a previous "multiplicative base ×1.20/tier" claim is
**RETRACTED as circular** (it inverted the formula to fit, then claimed to confirm
it). The real base-stat table now makes the tier problem tractable.

## What is CONFIRMED (within a tier)

    turns = C · D_loser · H_loser / (A_winner · L_winner),   C ≈ 12.54   (T1 Infantry)

- **38 within-tier same-class rows** (Gatot Lab-Rat exact ≤0.4 turns + MuellerAlpaca
  T1-v-FC1T1 with REAL captured L/H, two-sided) fit `A·L/(D·H)` to **median +0%,
  range −3%..+3%** with the SAME C≈12.54. Strongest confirmation; L/H no longer assumed.
- So `A·L/(D·H)` is the correct *local* form: damage/attack ∝ A·L/D, HP pool ∝ H.

## What is OPEN (the tier / base-stat law)

The real base-stat table `docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json`
(all 3 classes × T1–T10 × FC1–FC10) shows Infantry base A≈tier, L=tier, so `A·L`
grows ≈tier². Then `A·L/(D·H)` predicts tier **mirrors** should collapse
**300→36 turns (T1→T6)** — but they are observed **FLAT (~264–266)**. And the
MuellerAlpaca T2/T7 rows miss by +35% to +260%. So `A·L/(D·H)` does **not** govern
the tier dimension.

**The tier lead:** with the real stats, `(A − D) = −3` for *every* Infantry tier (A
rises in lockstep with D), and `(L − H) ≈ −5/−6`. The **difference** is tier-invariant
— which is why mirrors are flat. So the tier dependence is difference-structured while
the panel dependence is ratio-structured. Confirmed a 3rd way by the FarSeerGatot_v3
**winner-Inf tier ladder** (T1→T6 vs a fixed T1 Lancer): `turns×(A·L)` grows ~10×
across the ladder (would be constant if A·L were the numerator); damage scales ≈(A·L)^0.34,
not ^1. Reconciling local-ratio with global-difference is Stage 4's core task.
Note: within-T1 panel ladders give attack elasticity exactly −1 (pure ratio), which a
naive `(A−kD)` cannot match (predicts ≈−2), so neither pure form is the whole story.

**A SECOND open problem — cross-class (fails even at T1).** FarSeerGatot_v3 (Inf
winner kills Lancer/MM loser): the Infantry takes **2–6× longer** to kill a low-stat
Lancer/MM than `A·L/(D·H)` predicts, at T1 (no tier confound). Neither `D·H` (product,
which fits Inf-v-Inf) nor `(D+H)` (sum) rescues it. Leads to test: a damage floor / HP
additive constant (the miss grows as D·H→small; MM off 5–6×, Lancer off 2×), and the
counter-triangle *disadvantage* direction (Inf→MM is Inf's losing matchup — a penalty
there would make MM survive longest, as observed). Genuinely unsolved.

## Stage 4 goal

Using the **real stat table** for every troop (never the additive/multiplicative
guesses), derive the single law `turns = F(A_w,L_w,D_l,H_l; base-tier)` that:
1. reproduces the within-tier `A·L/(D·H)` panel behavior (Gatot + MuellerAlpaca T1),
2. reproduces flat tier mirrors (NanoMart T1–T6 Inf mirrors ~265),
3. predicts the cross-tier turns (NanoMart tier ladder; MuellerAlpaca T2/T7; Gatot
   T3) within the exact turn bands,
then BLIND-validate on the held-out Gordon battery. Report where it holds/breaks.

## Data (all real-stat-based)

- `wos_sim/data/experiments/Lab Rat/` — Gatot 1v1 isolation (36) + beast ladders (7).
- `wos_sim/data/experiments/MuellerAlpaca/` — 15 rows, REAL L/H, developed FC1 defender
  (Inf-v-Inf; Alpaca base is FC-table, see each file's `_stat_base_reference`).
- `wos_sim/data/experiments/FarSeerGatot_v3/` — 18 rows: **cross-class + winner-Inf
  tier ladder** (LabRat Lancer/MM loser vs FarSeer Gatot Inf T1–T6 winner), REAL L/H.
- `wos_sim/data/experiments/GATOT_ALL_TESTS_COMBINED.md` — the merged 66-row table + grouped fit.
- `wos_sim/formula_research/stage2_constraints.json` — NanoMart 71 (BUT its A/D/L/H
  were built on the ADDITIVE base model — **recompute effective stats from the real
  table** before using; do not trust its cross-tier A_eff/L).
- `docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json` — the real base stats.
- `wos_sim/formula_research/stage4_validate_nanomart.py` — prelim NanoMart test.

## Data sufficiency (what Stage 4 CAN vs CANNOT close)

**CAN close now (data sufficient):** the within-tier form (38 rows), the **tier law**
(winner-Inf ladder T1–T6 + NanoMart mirrors + MuellerAlpaca), and the **cross-class
form with Infantry as the damage-dealer** (FarSeerGatot_v3 Inf-vs-Lan/MM across the
tier ladder). No more experiments needed for these.

**CANNOT fully close (one genuine gap):** **attacker-class symmetry** — every clean
exact-turn row has *Infantry* dealing the killing blow (Gatot is Infantry-only, so
the per-attack clock only exists for Infantry). We have Lancer/MM only as the *loser*.
So whether a Lancer/MM *damage-dealer* obeys the same law/constant is not directly
testable with this instrument. Stage 4 should DERIVE for Infantry-attacker, then
cross-check against the (messier, Vulcanus-contaminated) NanoMart Lan/MM-winner rows
and FLAG any disagreement — it is a validation cross-check, not a blocker.

**Minor:** verify the 2 anomalous MuellerAlpaca T2 rows (die faster than T1); optional
FC-dimension probe (one ladder varying only Fire-Crystal level at fixed tier).

## Method & guardrails

Same `run-stage` guardrails: no fabrication; solve/confirm via the exact gate, never
regression-fit; observed turns are readouts, not prediction inputs; ambiguity →
branch; report failures as failures; scope `wos_sim/formula_research/` + read
`data/experiments/` and `docs/TroopStats/`. **Always compute effective stats from the
real base table.** The tier law must be SOLVED from a minimal subset (e.g. the mirror
ladder + one cross-tier ladder) then BLIND-predict the rest within exact turn bands.

## Deliverables

`stage4_law.py` (real-stat loader; within-tier confirm + the tier-law derivation),
`stage4_validate.py` (blind-predict NanoMart + Gordon with real stats), `STAGE4_REPORT.md`
(the reconciling law or an honest "still open, here's the smallest missing ladder";
the retraction of the multiplicative-base claim; per-row tables). Evaluate via `eval-4`.
