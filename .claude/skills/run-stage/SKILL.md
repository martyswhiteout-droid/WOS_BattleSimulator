---
name: run-stage
description: Formula-derivation stage runner for the WoS deterministic battle law. Invoke as /run-stage 2 (builder, constraint back-solve), /run-stage 3 (builder, family elimination), /run-stage 4 (builder, tier law), /run-stage 5 (builder, assemble predictor + composition), /run-stage 6 (builder, class-general law + Gatot-kit model + corpus-wide validation), /run-stage 6.6 (builder, hero-state-aware Gatot kit v3 + table refresh + full-corpus winner gate), /run-stage 6.7 (builder, fold-ownership migration: the seam computes hero folds itself), /run-stage 6.8 (builder, Type-1 router into the app's predict() path), /run-stage 7 (builder, Type-2 proc layer phase A: proc inventory + telemetry validation + instrument design), /run-stage eval-N (evaluator, N=2/3/4/5/6/6.6/6.7/6.8/7). Each stage is self-contained — the invoking window needs NO prior conversation context. Use whenever Martin says "run stage N", "evaluate stage N", or wants to continue the deterministic formula derivation.
---

# WoS deterministic-formula derivation — stage runner

You are one role in a two-role protocol: **builder** (stages 2/3) or **evaluator**
(eval-2/eval-3). The argument tells you which. Read this whole file first.

## Mission context (all stages)

The game's Type-1 battles are 100% deterministic. We are back-solving the exact
battle formula from 71 controlled NanoMart battles. A prior attempt (DeepSeek)
FABRICATED its result — read `ENGINE_REBUILD/DEEPSEEK_KERNEL_VALIDATION.md` for
the cautionary tale and the replay method that caught it.

**Data (already built, do not re-parse by hand):**
- `wos_sim/formula_research/ledger_dataset.json` — 71 rows (61 turn-clocked):
  per-side force (count/class/tier), deployed A/D/L/H, hero skills (Seo-yoon S1
  level; Vulcanus S1/S2/S3 trigger + KILL counts), casualty outcomes, winner,
  turns_lo/turns_hi. Produced by `wos_sim/formula_research/parse_ledger.py`.
- Source of truth for ambiguity: `wos_sim/data/experiments/NANOMART_EXPERIMENT_LEDGER.md`.
- **Gatot 1v1 + beast battery (Stage 4): `wos_sim/data/experiments/Lab Rat/`** — 36
  exact-turn Gatot 1v1 Infantry isolation rows + 7 beast-ladder rows + a Lab
  Rat/Gordon 0-stat battery. Master table + analysis: `Lab Rat/GATOT_MASTER_TABLE.md`,
  `Lab Rat/gatot_1v1_isolation.py`, `Lab Rat/gatot_ladder_analysis.py`.
- **CANONICAL TYPE-1 CORPUS (all stages): `wos_sim/data/experiments/_corpus/`** —
  every deterministic battle normalized into `TYPE1_CORPUS.json` (+ human
  `TYPE1_CORPUS.md` with coverage matrices; `corpus.py` query CLI). OCR corrections
  applied at build time from `corrections.json`. ALWAYS retrieve battle data here
  first; NEVER ask Martin for data before checking the coverage matrix; re-run
  `build_corpus.py` after any new ingestion.

**Confirmed mechanics (do not re-derive; cite ledger if you must confirm):**
- Simultaneous turns; casualties removed at end of turn; absorption Inf→Lan→MM.
- Seo-yoon S1 attacker Attack ×1.05/×1.10/×1.15 (L1/L2/L3).
- Vulcanus (defender side unless stated): S1 enemy Attack ×0.96 (once, start).
  S2 fires every 6th attack of EACH Vulcanus-side UNIT (+20%, CAN SCORE
  KILLS), counters SUMMED across units (PER-UNIT model, corrected 2026-07-19
  by the 3u@T=4 battle: 0 procs where the side-event model said 2; retrofits
  every prior anomaly: 2u@3→0, 2u@6→2, 2u@35→10, 2u@78→26, 2u@90→30). In 1v1
  that is turns 6,12,18; the ×31/30 average damage fold is UNCHANGED. S3 fires on
  turns **3,6,9,…** (TRIANGULATED 2026-07-18, 10/10 battles vs 9/10 for the old
  1,4,7 convention; sole strict discriminator T=35→11 procs = floor(T/3)).
  ⇒ Vulcanus-only turn bands are [3k, 3k+2] (NOT [3k−2, 3k]); build_corpus.py
  re-derives every Vulcanus-clocked band from the RECORDED S2/S3 counters at
  build time (flag `band_rederived_phase3`, 60 rows, 2026-07-18) — the ledger
  MD's turn cells are the STALE phase-1 numbers, trust the corpus. S3's EFFECT
  is SETTLED (Martin's True Strike tooltip, L4 = 48%/48% ⇒ L1 = 12%/12%):
  each proc BOTH shreds enemy Inf/Lan Defense −12% for 3 turns (⇒ continuous
  ×0.88 from turn 3) AND buffs the holder's own Marksmen's Attack +12% for
  1 turn (⇒ ×(1+0.12/3) ≈ ×1.04 avg on a MM dealer; in `_nanomart_offense`).
- Counter passives, always-on ×1.10 damage, directional: Inf→Lan (Master
  Brawler), Lan→MM (Charge), MM→Inf (Ranged Strike). Mirrors are passive-free.
- Panels: Lethality/Health chief-panel bonuses are 0% in this corpus (Martin-
  confirmed); deployed stats in the dataset already include panels.
- **Gatot instrument (Stage 4):** Far Seer Infantry hero. S2 King's Bestowal
  triggers once per attack → `triggers == rounds` EXACTLY (no cadence band).
  S1 +6% own Inf Defense; S2 self-shield; **S3 = −15% ENEMY Attack at L1
  (Martin-confirmed 2026-07-18)** — so Gatot is NOT purely own-side-defensive.
  CAVEAT: every measured G_l cell whose instrument had a Gatot-led TARGET
  already folds S1/S2/S3 implicitly (that is why those cells validate without
  an explicit S3 fold — do NOT double-apply). OPEN PHYSICS: Gatot-led sides
  as DEALERS run ~2.5–4.3× slower than the law (the "reverse-race residual");
  `MuellerAlpaca_1v1_T7InfvFC1T1Inf_151127` is Martin-screenshot-VERIFIED
  clean (T7, panels right, defender unscathed at 599t vs law 141t) — real
  missing mechanic, and it discriminates DEALER-side suppression from
  target-side amplification (the target there is naked). Global battle cap =
  **1500 rounds** (a capped battle where the attacker survives is a "defeat"
  if any enemy remains).
- **HERO-STATE DISCOVERIES (2026-07-18/19, `docs/HERO_KITS.md` = the registry;
  `formula_research/gatot_shield_test.py` = the evidence):** (a) heroes add
  flat panel AURAS = the hero's own Expedition stat block, verified at source
  (Mueller Gatot +301.93 EXACT; Alpaca +337.85; FarSeer +186.45; Vulcanus on
  Alpaca's MM +873.3 A/D); auras are captured in per-battle panels — never
  reuse hero-led panels for hero-less setups. (b) An UN-AURA'D Gatot (unit
  panels at no-hero baseline) is INERT — no shield, no Royal-Legion fold; 12
  corpus rows fit the plain law ±3.2%. (c) AURA'D Gatot vs HERO-LESS dealers
  = linear subtractive budget: net = max(0, Σ A·L/(K·G_w) − B); B measured
  201.95 (Mueller, 21/22-MM edge) / 30.15 (FarSeer, 66/67 edge) / ~879-949
  (Alpaca, the 2026-07-19 204/205-Lancer edge; K(Lan→Inf)-branch-dependent).
  Hero-LED (Vulcanus) dealers BYPASS the budget (S-curve regime; n>1 pooling
  order unvalidated). (d) The 40/41 edge + independent B_Mueller imply
  K(Lan→Inf) ≈ 90.4 at T6 (T3 tension via 66/67 remains, ordinary-vs-FC1
  caveat). (e) G_w(Inf,7) MEASURED = 14.1–14.5 (T7 discriminator
  `..._235302`); the cube-root extrapolant 13.2 was −8%. (f) The GATOT-DEALER
  SLOWDOWN (a Gatot-led side's own kill clock ~4× slow vs a naked target,
  `151127`, ≥3.9× fully controlled) is REAL UNEXPLAINED PHYSICS → Stage 7.
  (g) Codex QA v2 (2026-07-19, `qa_codex_v2/`): in-domain 132/138 with ALL 6
  misses = the documented open list; zero adversarial counterexamples;
  24/24 Alpaca budget-branch winners correct. (h) E-battery 2026-07-19
  (5 battles, corpus 243): hero-led √N POOLING ORDER CONFIRMED (3×Vulc-MM
  kill @4 = per-dealer-then-√N; pooled said 3); GATOT-DEALER SLOWDOWN =
  INERT-STATE-ONLY (aura'd T7 dealer @37 = plain law EXACT; Gordon-led
  [72,74] ≈ no-hero) ⇒ production (maxed heroes, Martin's policy) is CLEAN;
  G_w(Inf,6)=10.889 CONFIRMED on the zero-panel MiniMart instrument
  ([9.53,11.11] bracket) ⇒ the ×1.17 tension is Alpaca-FC1T1-target-specific;
  K(Lan→Lan) third measurement 126.2 (Gordon instrument; spread 126/149.8/176
  across instruments — cell stays open); GORDON auras/cadences first-measured
  (HERO_KITS.md); heroes buff ONLY their own class (E3b live proof).
- **WITHIN-TIER LAW (Stage 4, CONFIRMED):** `turns = C·(D_l·H_l)/(A_w·L_w)`,
  C≈12.54 T1 Infantry — damage/attack ∝ A·L/D, HP ∝ H, exponents (+1,+1,−1,−1).
  Exact on Gatot Lab-Rat ladders (≤0.4 turns) AND on MuellerAlpaca T1-v-FC1T1
  (±3%, REAL captured L/H, two-sided battle). `HP=D+H` refuted (product D·H).
- **REAL base-stat table:** `docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json`
  (all classes × T1–T10 × FC1–FC10). ALWAYS compute effective stats = real base ×
  (1+panel); NanoMart's stored A_eff/L used a WRONG additive base — recompute.
- **TIER LAW = SOLVED (Stages 4–5 + E-NIF, all ACCEPTED).** Tier damping factors
  G_w (dealer) and G_l (target) multiply the within-tier law and are
  **CLASS-DEPENDENT**: Infantry heavy (G_w 1/2.68/4.32/5.88/9.79/10.89), Lancer
  mild (1/—/1.09/—/—/1.63), Marksman ~flat (≤1.17, entangled with S_gatot);
  G_l: Inf T1–T10 measured, MM steep (1.05/0.25/0.085 @ T1/T3/T6), Lan T2=0.654.
  Full current state: `STAGE5_REPORT.md` + `STAGE5_EVAL.md` +
  `wos_sim/data/ENIF/ENIF_ANALYSIS.md`. (Historical: the "×1.20/tier
  multiplicative base" claim was retracted as circular.)

## GUARDRAILS (all stages — violating any of these is a failed stage)

1. **No fabrication.** Every number you present must be produced by a script
   that exists in `wos_sim/formula_research/` and is re-runnable. If you did
   not compute it, do not print it.
2. **No regression / best-fit.** Constants are SOLVED from minimal equation
   subsets or enumerated over simple rationals, then accepted ONLY on exact
   blind prediction of all remaining rows (within the reported turns_lo..hi
   integer band). Any unexplained residual anywhere = family REJECTED. Never
   minimize aggregate error.
3. **Observed outcomes are never inputs.** Predictions are stats-in →
   turns/survivors/winner-out. (Stage 2's back-solve legitimately USES observed
   turns to compute implied damage — that is its purpose — but label every such
   quantity `implied_*`, and Stage 3+ may not feed observed outcomes into
   predictions.)
4. **Ambiguity → branch, never silently pick.** If a mechanic reading is
   ambiguous (e.g. S2 kill timing), record BOTH interpretations as explicit
   branches in the output with the evidence for each.
5. **Scope:** write only inside `wos_sim/formula_research/`. Do not touch the
   engine, prototype/, or data files. Do not commit/push unless Martin asks.
6. **Report failures as failures.** "No family survived" is an acceptable,
   reportable outcome; a polished fiction is not.

## /run-stage 2 — BUILDER: exact constraint back-solve

Goal: turn the 61 turn-clocked battles into an exact machine-readable
constraint table. NO formula proposals in this stage.

1. For each battle: compute effective offense/defense inputs per side (apply
   hero factors + passives + S3 defense windows per the mechanics above; the
   dataset's deployed stats already include panels).
2. Back-solve the implied per-turn damage each side dealt: cumulative damage
   over T turns = loser's HP pool (HP model: per-unit hidden HP; treat the HP
   unit itself as unknown — express constraints in units of H_def AND raw, so
   Stage 3 can test HP∝H vs HP∝(D+H) etc.). Respect the turns_lo..hi band →
   output an INTERVAL [implied_d_min, implied_d_max] per side, exact rational
   arithmetic where possible (fractions module), floats only for display.
   Account for S2 boosted turns (floor(T/6) turns at ×1.2) and S2 kills where
   K>0. Winner side's damage: constrain from loser wipe; loser side's damage:
   constrain from winner's survivor/injury state (1v1: winner uninjured only
   bounds damage < 1 HP-unit — record as inequality).
3. The count-ladder rows (100v200 etc.) yield SURVIVOR constraints — include
   them (damage_total over T turns = casualties×H-unit), with the √N question
   left OPEN (record count, don't assume the exponent).
4. Deliverables: `stage2_constraints.json`, `STAGE2_CONSTRAINTS.md` (human
   table: battle, side, effective inputs, implied damage interval, branch
   notes), and the generating script(s). End with: rows covered, rows excluded
   (why), ambiguity branches found, and the 5 most constraint-rich battles.

## /run-stage 3 — BUILDER: family elimination (needs Stage 2 output)

Candidate families (at minimum): linear difference c·(A−k·D+K)·f(L,H); ratio
forms; polynomial (quadratic/cubic) terms per stat (Martin's request); cap/clamp
variants; HP-pool variants (H, D+H, class-specific); count laws (√N, linear,
frontage) tested on the ladder rows. For each: SOLVE constants from a minimal
determining subset (document which rows), then BLIND-predict every remaining
row (stats-in only). Deliverables: `stage3_results.json` + `STAGE3_REPORT.md`
with a per-row predicted-vs-observed table per family, surviving families (if
any), and the discriminating experiment that would separate survivors.

## /run-stage 4 — BUILDER: solve the TIER law (needs `STAGE4_SPEC.md`)

Read `wos_sim/formula_research/STAGE4_SPEC.md` first. The WITHIN-TIER form
`A·L/(D·H)` is CONFIRMED (Gatot exact + MuellerAlpaca ±3% with real L/H). Stage 4's
job is the OPEN tier law, using the REAL base-stat table.

0. **Build a real-stat loader** from `docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json`;
   effective = real base × (1+panel). Recompute NanoMart effective stats from it
   (its stored A_eff/L used a wrong additive base). This step is mandatory — every
   later number depends on it.
1. **Re-confirm within-tier** `turns = C·D_l·H_l/(A_w·L_w)`, C≈12.54, on the Gatot
   Lab-Rat 1v1 (exact) and MuellerAlpaca T1-v-FC1T1 (±3%) rows. Report residuals.
2. **Derive the tier law.** The obstruction: real base A≈tier, L=tier → `A·L/(D·H)`
   predicts tier mirrors collapse 300→36, but they are FLAT (~265). Fit forms that
   reconcile local-ratio (panel space) with global-difference (`A−D=−3` is tier-
   invariant): candidate directions incl. difference terms `(A−D)`, `(L−H)`,
   ratio-of-differences, or a power/normalization by tier. SOLVE constants from a
   minimal subset (mirror ladder + one cross-tier ladder), then BLIND-predict every
   other row within its exact turn band. Report the surviving form, or an honest
   "no closed form yet + the smallest missing ladder."
3. **Blind-validate** the resulting law on the held-out Gordon battery
   (`LABRAT_GORDON_ASSESSMENT.md`) and the full NanoMart tier ladder.
4. **Flag** the T2 MuellerAlpaca anomaly (2 rows die faster than T1) as suspect
   pending re-capture; do not let it drive the fit.
5. Deliverables: `stage4_law.py`, `stage4_validate.py`, `STAGE4_REPORT.md`
   (within-tier confirmation, the tier-law result or honest gap, per-row tables, the
   retraction of the multiplicative-base claim, still-missing data).

## /run-stage 5 — BUILDER: assemble the predictor + composition layer (needs `STAGE5_SPEC.md`)

Read `wos_sim/formula_research/STAGE5_SPEC.md` first. The per-unit Infantry law is
COMPLETE and the composition layer is MEASURED; Stage 5 freezes, extracts, assembles,
validates, and wires to the app. No new experiments needed for the core.

- **Per-unit law (freeze, K-table formulation — see STAGE5_PREFLIGHT_REVIEW.md):**
  `turns = K(dealer_cls,target_cls)·D_l·H_l/(A_w·L_w)·G_w(τ_w)·G_l(τ_l)`.
  K measured: Inf→Inf 12.5, Inf→Lan 22.4, Inf→MM 73.1; clean Gordon rows give
  MM→Inf≈93, MM→MM≈567, Lan→MM≈500 (non-Inf penalty ≈×7). NO separate ctr — the
  K-table absorbs passives. Factorization hypothesis K≈f(dealer)·g(target) predicts
  the 3 untested cells — blind-test it. **Freeze G_w/G_l as the MEASURED tables**
  (G_w {1,2.68,4.32,5.90,~9.8,10.89}; G_l {1.00,0.996,0.904,0.795,0.770,0.749,
  0.742,0.744,0.757,0.777}); cube-root (A_base·L_base)^(2/3) interpolates T7+ only.
  HP=D·H, √N offense.
- **Data discipline:** load ALL battles via `wos_sim/data/experiments/_corpus/`
  (`corpus.py` / TYPE1_CORPUS.json — corrections pre-applied). Check its coverage
  matrix BEFORE requesting any new experiment from Martin. Re-run `build_corpus.py`
  after ingesting new reports.
- **Composition layer (`Meuller_Alpaca_v5_8_Battle`):** frontline tank takes a BINARY
  tanking penalty (solo 78 → any-backline 33, CONSTANT across backline count 1..10 and
  class MM/Lancer); backline mopped up LINEARLY (~1.33 turns/unit; end=33+1.33k). Model
  as an algorithm on the per-unit law (absorption order Inf→Lan→MM; tank life =
  per-unit turns × tanking factor; linear backline clear).
- Assemble `predict_battle`, blind-validate (Gordon, NanoMart directional), wire behind
  `wos_sim/predictor/api.py` (seam only; run `py -m wos_sim.backtest`, gate G12).
- Deliverables: `stage5_law.py`, `stage5_composition.py`, `stage5_validate.py`,
  `STAGE5_REPORT.md`, api.py wiring.

## /run-stage 6 — BUILDER: class-general law + Gatot-kit model (needs `STAGE6_SPEC.md`)

Read `wos_sim/formula_research/STAGE6_SPEC.md` first. Stages 1–5 are ACCEPTED;
the E-NIF battery (2026-07-17, `wos_sim/data/ENIF/ENIF_ANALYSIS.md`) measured
everything Stage 5 had to freeze as hypothesis. Stage 6 = consolidation:

- **Class-keyed tables (`stage6_tables.py` → `stage6_tables.json`):** dealer
  tier-damping G_w is CLASS-DEPENDENT — Infantry {1,2.68,4.32,5.88,9.79,10.89}
  (measured), Lancer {1, —, 1.091, —, —, 1.625} (E-NIF3, interpolate gaps with
  meta flags), Marksman ≈1 with a stated [1, 1.17] band (entangled with S_gatot).
  G_l likewise class-keyed: Inf T1–T10; MM {1.051, 0.249, 0.085} @ T1/T3/T6
  (steep); Lan T2=0.654 only. K-cells updated: Lan→MM 489 and MM→MM 567 confirmed
  at full panels; MM→Inf 90.1 clean (Gordon target). Every cell carries
  {measured|interpolated|bounded} provenance + source row ids.
- **Gatot-kit model (`stage6_gatot.py`) — the one open mechanism:** SOLVE a
  saturating suppression from the measured S_gatot ≈ {4.73, 2.23, 1.17} at dealer
  damage scales {~2.9, ~13.9, ~48.6} HP-units/turn (enumerate candidate families
  — fixed absorb, Attack-scaled shield, capped absorb — never regress), then
  BLIND-predict the eight count-threshold battles (21/22 T6MM, 40/41 T6Lan,
  32/33 T3MM, 66/67 T3Lan): the model must reproduce the knife-edge (N−1 capped,
  N wins in the observed turns, √N stacking). Failure = report honestly, leave
  thresholds out-of-scope.
- **Corpus-wide validation (`stage6_validate.py`):** blind-predict every
  scoreable row of the 232-row corpus; per-instrument buckets with the ceil
  gate; nothing regresses vs the Stage-5 buckets; non-Inf dealers at τ≥2 must
  improve. Alliance rule: panels are per-battle inputs (never reuse across
  battles; the +23/+10pp RFJ instance is documentary, not a constant).
- **Housekeeping:** orphaned L21 registry entry (duplicate-of-L19); R03/R04
  Mueller-MM H cosmetic; document troop_catalog.py-vs-docs divergence (the
  deterministic path uses docs/TroopStats ONLY; never silently edit
  troop_catalog — it feeds the legacy engine).
- **Seam:** api.py deterministic entry points load `stage6_tables.json`
  (additive only; `predict()` untouched; meta `law_version: "stage6"` +
  provenance flags). Gates: `py -m wos_sim.backtest` (G12 may only improve) +
  predictor suite.
- Deliverables: `stage6_tables.py` + `stage6_tables.json`, `stage6_gatot.py`,
  `stage6_validate.py`, `STAGE6_REPORT.md`. Evaluate via `/run-stage eval-6`.

## /run-stage eval-N — EVALUATOR (N = 2 / 3 / 4 / 5 / 6)

Independently verify the builder's output (fresh eyes, adversarial):
1. Re-run the builder's scripts; confirm outputs reproduce byte-identically.
2. Recompute 3 randomly-chosen rows by hand/own script; compare.
3. Check guardrails: no fitted constants (stage 2), no observed-outcome leakage
   into predictions (stages 3/4), ambiguities branched, intervals not points where
   bands exist, **residual-zero honored for the identified law (stage 4)**, failures
   reported as failures.
4. Verdict: ACCEPT / REJECT with the specific rows and reasons. Write
   `STAGE<N>_EVAL.md` next to the builder's deliverables.

## /run-stage 6.6 — BUILDER: hero-state-aware Gatot kit v3 + table refresh + full-corpus winner gate

Everything below derives from corpus rows + the registry — NO new constants may
be invented; every frozen number must re-derive from a named battle. Work in
`wos_sim/formula_research/`; seam changes only via `stage5_composition.py` /
`api.py` (additive; `predict()` untouched). Deliverable: `STAGE6_6_REPORT.md`
+ a v2 emit of `stage6_tables.json` (byte-stable double-emit) + updated
validator. Do not commit.

1. **Table refresh (stage6_tables v2, per-cell provenance):**
   a. G_w(Inf,7): derive from `..._AlpacaFC1T1Vulcanus_20260718_235302`
      (t∈[75,77]; folds: Vulcanus S1 ×0.96 only). Freeze the measured band
      and a point value; keep T8-T10 extrapolated (status-tagged).
   b. K(Lan→Inf): derive from the 40/41 edge + the INDEPENDENT B_Mueller
      (pinned by the 21/22 MM edge): K·G_w^Lan(6) = 732.3/(201.95/40.5)
      ⇒ K ≈ 90.4. Freeze as edge-implied (T6); document the T3 tension
      (66/67 edge ⇒ ~111 with G_w^Lan(3)=1.091) as a known-open with the
      ordinary-vs-FC1 caveat. Carry the old factorized 83.7 as a branch tag.
   c. gatot_kit v2: B table keyed by (copy, state): mueller_aurad 201.95,
      farseer_aurad 30.15, alpaca_aurad = derive from the 204/205 edge
      (rate WITH G_w^Lan(6); both K branches; kill-time 575 consistency
      check must pass), any_inert = 0 (kit inert). Registry numbers
      (Expedition %s, skill levels) from `docs/HERO_KITS.md`.
2. **Kit v3 in the seam (`stage5_composition.py` + `_kit_for_side`):**
   hero-STATE detection from panels via the registry: for a known copy,
   aura'd iff the unit's class A-panel is nearer (baseline + Expedition%)
   than baseline (nearest-neighbor; baselines from the copy's known no-hero
   captures, tabulated with provenance); unknown copies → present-but-
   unmeasured (abstain as today). Inert ⇒ NO kit (plain law, no Royal-Legion
   fold). Aura'd ⇒ budget (hero-less dealers) / S-curve (Vulcanus-led).
   `law_version: "stage6.6"`. Default args byte-identical to 6.5.
3. **W6 v2 — full-corpus four-way winner gate:** extend `_w6_scoreable` to
   every row with a winner (incl. NanoMart multicount: race with √N + folds;
   composition/beast rows may stay excluded with stated reasons). Expected
   movements to VERIFY row-by-row: the 12 inert rows CORRECT via plain race;
   the 24 Alpaca-target rows CORRECT via budget-cap; the 14 Lancer-dealer
   abstains now MODELED (K edge-implied + B) — report each. Investigate the
   7 multicount winner-misses from Codex v2 (`qa_codex_v2/qa2_results.csv`):
   fixed by proper √N racing, or honest opens with named causes. Target:
   ABSTAIN only where genuinely unmeasured; WRONG only the known list (3) —
   any NEW wrong = investigate before reporting.
4. **Housekeeping:** stage6_tables meta row_count dynamic (238-aware); the 3
   stale stage2-era tests refreshed with dated annotations asserting the
   CORRECTED data-state (eval-6 recommendation); W6 printout labels.
5. **Gates:** full stage6_validate battery + G12 backtest (7/13 may only
   hold/rise) + predictor suite; stage5_law drift 0.0%; every 6.5-era gate
   that changes must be explained line-by-line in the report.

## /run-stage eval-6.6 — EVALUATOR

Independent re-run of every gate; own-arithmetic recomputation of: G_w(Inf,7)
from the battle, K(Lan→Inf) from the 40/41 edge, B_Alpaca from the 204/205
edge (incl. the 575 kill-time consistency), at least 3 of the abstain→CORRECT
upgrades, and the byte-stability double-emit. Verdict ACCEPT/REJECT with the
usual guardrail audit (no regression-fitting, branches carried, failures
honest).

## /run-stage 6.7 — BUILDER: fold-ownership migration (the seam computes hero folds)

Codex QA v3 finding #1 (STAGE6_6_REPORT.md §8): the deterministic hero FOLDS
(Seo-yoon S1; Vulcanus S1/S2/S3; Royal Legion) live in a validator-side
private helper (`stage5_validate._nanomart_offense`), so a live seam caller
that declares kits still gets fold-blind clocks (interim warning flag
`hero_folds_not_applied_*`). This stage moves fold computation INTO the seam
— folds enter EXACTLY ONCE, from the kits + armies. No new constants: every
fold value is the frozen mechanic (Seo-yoon ×1.05/1.10/1.15 by level;
Vulcanus S1 ×0.96 enemy Attack, S2 ×31/30 dealer-side average, S3 /0.88 on
enemy-Inf/Lan-target clocks AND ×(1+0.12/3) on holder-side MM dealers;
Royal Legion −10%/−15% enemy Attack at L2/L3, AURA'D state only, level from
the hero_state registry by copy — unknown copy ⇒ no fold + informational
flag, never a guess).

1. **Seam implementation** (`stage5_composition.py`): a direction-fold
   function `(dealer_units, dealer_kit, target_units, target_kit) → mult`,
   multiplied into each race direction inside `predict_battle`;
   `apply_hero_folds=True` default parameter (False = legacy behavior for
   migration comparisons); explicit caller `*_offense_mult` multiplies ON TOP
   (documented as extras, e.g. anchors — NOT the standard folds). Kit schema
   gains `{"seoyoon": level}`. The 6.6 `hero_folds_not_applied_*` warning is
   REMOVED (gap closed); add `hero_folds_applied` informational flag listing
   which folds fired per direction.
2. **Validator migration** (`stage6_validate.py`, `stage5_validate.py`):
   W6 stops passing `_nanomart_offense` mults and lets the seam fold (kits
   must carry seoyoon levels — derive in `_kit_for_side` from the corpus
   heroes). One-directional sections (A6/B6/D6…) may keep explicit mults
   where they score observed-winner clocks, but each section's choice must
   be stated. `_nanomart_offense` itself stays only if a section still needs
   it; mark it deprecated-for-callers.
3. **Re-baseline discipline (the risky part):** rows the validator
   previously raced with mult=1.0 but which carry fold-bearing heroes
   (non-NanoMart Vulcanus rows: ENIF R11/R12, the T6/T7 discriminators,
   E3b, the E-battles) get clock changes of a few %. Produce a ROW-BY-ROW
   before/after for every W6 classification that MOVES, with justification.
   HARD GATES: WRONG == the 3 known rows exactly (no new wrong); ABSTAIN
   ≤ 1 (the E3a cell); CORRECT + COIN_FLIP total may not drop. Clock
   accuracy on the affected exact rows should IMPROVE toward the folded
   conventions (e.g. the T7 discriminator 73→~76 vs band [75,77]) — report
   per-row deltas.
4. **Precision housekeeping:** emit `K_LanInf_for_gate` values at 6 decimals
   (like B after QA v3 #2); verify the 205v1 clock moves 587 → ≤580
   (obs 575); double-emit byte-stable.
5. **Regression tests** (`test_deterministic_seam.py`): the Codex v3 W6
   construction (their fold-blind flip probe, from `qa_codex_v3/`) must now
   return the FOLDED verdict as a test; Seo-yoon fold test; Royal-Legion
   state-aware fold test (aura'd folds, inert does not); opt-out
   (`apply_hero_folds=False`) preserves 6.6 behavior; REPLACE the
   now-obsolete `test_vulcanus_kit_without_folds_warns`.
6. **api.py**: `law_version: "stage6.7"`; docstring; `predict()`/server.py
   untouched (verify byte-identical behavior — G12).
7. OUT OF SCOPE (do not touch): the E3a monotonicity upgrade (6.8 candidate),
   any Type-1 router/app wiring (6.8), K-cell re-derivations, the corpus.

Gates: full `stage6_validate` battery (11 PASS + the 2 deliberate FAILs,
W6 per the hard gates above), `stage5_validate` exit 0 (byte-identical where
unmigrated; documented where migrated), backtest 7/13, both pytest suites
green (121+ predictor / 24 formula_research), tables double-emit stable.
Deliverable: `STAGE6_7_REPORT.md` with the row-by-row movement table.

## /run-stage eval-6.7 — EVALUATOR

Re-run every gate; recompute ≥5 fold-migrated rows' clocks by hand (incl.
the T7 discriminator and one ENIF R-row); verify the Codex-v3 flip probe now
folds; verify opt-out reproduces 6.6; audit the movement table row-by-row;
verdict ACCEPT/REJECT.

## /run-stage 6.8 — BUILDER: the Type-1 router into the app's predict() path

Goal: when a submitted matchup is TYPE-1-CLASSIFIABLE and inside the law's
validated domain, `api.predict()` serves the deterministic law's exact result
(honestly labeled through the EXISTING Forecast/serialize/UI contract);
everything else flows to the turn engine unchanged. server.py untouched
(standing rule: engine only through api.py).

CONTRACT FACTS (verified 2026-07-19; do not re-derive): SideProfile fields =
profiles.py:17-55 (formation_counts/formation+troops_total; quality per class
= ClassQuality(tier, fc, t12_stack); panel keyed (class, stat) in FRACTIONS
(10.96 = 1096% -- the law wants displayed-percent x100); lead_heroes
{class: name}; joiners list; own_buffs/debuffs_on_enemy dicts).
Forecast/summarize = summary.py:360-443 (confidence in {"coin_flip",
"directional", "validated"}; stochastic; calibrated; near_even;
engine_model_error; engine_path; engine_note). serialize.forecast_to_dict =
serialize.py:86-105. UI (prototype/index.html:3569-3652): tier 'hedge' iff
confidence=='coin_flip' or near_even; else calibrated ? 'full' :
'restrained'; stochastic=false renders "deterministic · single outcome";
note = badge tooltip. THE UI NEEDS NO CHANGES THIS STAGE.

1. **Classifier** `_type1_classifiable(matchup) -> (bool, reason)` in api.py
   (or a small router module): CLASSIFIABLE iff, for BOTH sides: every
   deployed class has tier <= 6 AND fc < 3 (no proc unlocks — the
   troop-passives gates); heroes ⊆ {none, "Seo-yoon"/"SeoYoon", "Vulcanus",
   "Gatot"} (name-normalized; ANY other hero incl. Gordon -> not
   classifiable); joiners empty; own_buffs and debuffs_on_enemy empty;
   exactly ONE class with nonzero count per side (single-class stacks — the
   W6-validated domain; multi-class comps stay on the turn engine until the
   composition regime generalizes). Conservative default: any doubt ->
   NOT classifiable.
2. **Router in predict()**: classify FIRST; if classifiable, build army
   dicts (counts from formation_counts else formation x troops_total;
   eff/panel from quality + panel via the stage5_law base tables — panel
   fractions x100 into panel_pct) + kits from lead_heroes (gatot -> {"gatot":
   True} + panels for state detection; vulcanus/seoyoon flags with levels
   where the profile carries them), call the frozen law
   (stage5_composition.predict_battle via the same path
   predict_deterministic_battle uses). Outcomes:
   - confident winner -> Forecast with p_win 1.0/0.0 (se 0), stochastic
     False, calibrated True, confidence "validated", engine_path
     "deterministic_law", engine_model_error 0.03 (the A6 exact-gate band),
     near_even False, engine_note naming law_version + the exact clock;
     rounds/army_losses/class_losses as single-point distributions from the
     death timelines; skill_telemetry/timeline None; n=1.
   - clock gap <= 10% (the coin-flip carve-out) -> as above but p_win 0.5,
     near_even True, confidence "coin_flip" (UI renders 'hedge' — honest).
   - seam abstains (gatot_abstain) OR raises -> FALL THROUGH to the turn
     engine unchanged, appending a short "(deterministic law abstained:
     <flag>)" clause to the turn path's engine_note.
   - opt-out: params={"deterministic_router": False} forces the turn path
     (tests/comparisons).
3. **Hard invariants**: the golden backtest (`py -m wos_sim.backtest`) and
   the full predictor suite must be UNCHANGED — backtest profiles are
   T12/FC10 and must all classify NOT-classifiable (assert this in a test:
   every golden profile -> reason "tier/fc"). serialize round-trips the new
   Forecast without schema changes. predict()'s signature unchanged.
4. **Tests** (extend the predictor suite): classifier truth-table (tier>6,
   fc>=3, unknown hero, Gordon, joiners, buffs, multi-class, happy path);
   router end-to-end on a corpus-derived Type-1 matchup (winner + exact
   clock in the Forecast; confidence/stochastic/calibrated fields per the
   contract); coin-flip mapping; abstain-fallthrough (Gatot unknown-copy
   target -> turn-engine Forecast + note clause); opt-out param; golden
   profiles all reject.
5. OUT OF SCOPE: server.py, prototype/index.html (UI polish is 6.8b if
   Martin wants a distinct badge later), the corpus, stage6 tables, the
   composition multi-class generalization, Stage 7.

Gates: full battery (stage6_validate 11 PASS + 2 deliberate FAILs unchanged;
backtest PASS 7/13; predictor suite ALL passing incl. the new tests;
formula_research 24). Deliverable: STAGE6_8_REPORT.md (router design, the
classifier truth table, response-mapping table, gates before/after).

## /run-stage eval-6.8 — EVALUATOR

Re-run gates; construct 3 matchups by hand (one classifiable-confident, one
coin-flip, one abstain-fallthrough) and verify the Forecast fields against
the contract table above; verify all 13 golden backtest profiles reject with
tier/fc reasons; verdict ACCEPT/REJECT.

## /run-stage 7 — BUILDER: Type-2 proc layer, PHASE A (inventory + telemetry + design)

The deterministic Type-1 program is COMPLETE (stages 1-6.8): the law is exact
in its domain and routed into the app. Stage 7 extends prediction into proc
territory (Type-2) under the BINDING no-fudge rule: Type-2 reports are NEVER
regression-fit — proc probabilities come from tooltips/catalogs, validation
is by DISTRIBUTION ONLY (observed trigger counts vs binomial expectations,
observed outcomes vs predicted distributions). Phase A is ANALYSIS-ONLY:
no engine/seam/table changes; you may write only new .md/.py analysis files
under `wos_sim/formula_research/` and `docs/`. Phases B (the stochastic
layer on the law) and C (router widening) are follow-on stages — you DESIGN
them here, you do not build them.

1. **PROC INVENTORY** → `docs/PROC_CATALOG.md`. Every chance-based mechanic:
   troop skills (the FC/tier proc table in
   `.claude/skills/wos-battlereport-ingestion/references/troop-passives.md`
   + the `skill_catalog`/`fire_crystal_troop_skill` blocks in
   `docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json` + `wos_sim/
   troop_catalog.py`), proc HEROES (the turn engine's `wos_sim/skills.py`
   catalog + the 2026-07-07 proc-classifier audit notes in the repo docs),
   and anything in `GAME_RULES.md`. Per proc: trigger condition, stated
   probability, effect, source, modeling class (damage-mult / extra-attack /
   absorb / defense-mult / on-death / next-attack), interaction notes with
   the deterministic law's terms, and measurement status.
2. **TELEMETRY MINING (no new battles)**: every Type-2 report on file with
   visible skill trigger counts — the golden anchors (see
   `wos_sim/backtest.py` + the normalize_reports outputs it uses), the RAW/
   T12 reports, and any Type-2 JSONs in `wos_sim/data/experiments/`. For
   each proc with countable triggers: observed count vs opportunity count vs
   the catalog probability — exact binomial two-sided p-value / CI, per
   report and pooled. Deliverable table: CONFIRMED / CONTRADICTED /
   unmeasurable-from-file, with arithmetic shown. A contradiction is a
   FINDING (flag with evidence), never a refit.
3. **PHASE-B DESIGN DOC** (in the report): how the stochastic layer sits ON
   the deterministic law — per-turn law damage x proc rolls, CRN seeding,
   which procs touch which law terms, how kill-turn/survivor DISTRIBUTIONS
   replace point clocks, and the validation gate design (distribution
   checks against the Type-2 rows currently excluded, incl. the
   Vulcanus-dealer −6.5% family and the proc-gated non-Inf rows). Also the
   Phase-C router-widening criteria (which FC/tier gates open when which
   procs are validated).
4. **EXPERIMENT MENU for Martin** (E-battery table format: setup / battles /
   capture / predicted readings): the small prioritized set that pins what
   files cannot — e.g. FC3 Crystal Lance double-damage count over a long
   Gatot-clocked 1v1; Volley extra-attack counts; Ambusher backline-strike
   rate; Crystal Shield offset counts. Only experiments whose READ is
   decisive; state the binomial power (how many trials the battle yields).
5. **PARKED-PHYSICS TRIAGE**: the 3 known-WRONG rows (151127 inert-Gatot-
   dealer slowdown; LabRat Lan-vs-MM cross-cell; NanoMart MM→Inf +26%),
   Royal Legion decontamination (needs a differing-LEVEL Gatot instrument),
   K(Lan→Lan) 126/149.8/176 spread, K(Lan→Inf) T3-vs-T6, the Alpaca-FC1T1
   ×1.17 family, multicount clock regime, n>1 S-curve, composition
   generalization. Classify each: needs-experiment (name the one-battle
   discriminator) / needs-analysis / Phase-B-blocked.

Deliverables: `docs/PROC_CATALOG.md` + `STAGE7A_REPORT.md` (telemetry
tables, phase-B design, experiment menu, triage). Write the report
INCREMENTALLY from the start. Gates: nothing may change — run the full
battery once at the END and show it is byte-identical to the 6.8 baseline
(stage6_validate, backtest, both pytest suites).

## /run-stage eval-7 — EVALUATOR

Verify inventory completeness by independently walking the three catalog
sources; recompute the binomial arithmetic for ≥3 mined procs by hand;
check the experiment menu's predicted readings; confirm the no-change gate.
Verdict ACCEPT/REJECT.
