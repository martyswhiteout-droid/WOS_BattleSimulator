# QA BRIEF v2 — independent re-validation of the WoS deterministic battle law (for Codex)

Second-round QA. Your first run (`qa_codex/`) found a real defect (the
one-directional winner validation) — it was fixed, and your 35 FAIL rows were
reconciled one-by-one (`CODEX_RECONCILIATION.md`: 2 resolved by corrections
you predated, 9 coin-flip, 7 honest abstentions, 3 known-wrong, 1 residual,
13 out-of-domain). Since then the corpus, the folds, and the Gatot model have
all moved. Re-run from scratch against the current state.

## Hard rules (unchanged, violating any = failed QA)
1. Never fabricate a number; every figure comes from code you wrote and ran.
2. Read-only repo; write ONLY inside `wos_sim/formula_research/qa_codex_v2/` (new folder).
3. Physically-impossible-looking inputs → FLAG (id + field + why), never "fix".
4. Failures are findings. No tunable constants exist.
5. Independence: do NOT import the project's predictor code. Run
   `stage6_validate.py` ONCE at the very end as a cross-check only.

## What changed since your first run (read carefully — three of your FAILs came from these)

1. **Corpus is now 236 rows** (`_corpus/TYPE1_CORPUS.json`), still the single
   source of truth. 60 Vulcanus-clocked rows carry a
   `band_rederived_phase3(was X-Y)` flag: the S3 cadence was measured to be
   turns **3, 6, 9, …** (k triggers ⇒ turns ∈ [3k, 3k+2]; S2 on a 1-unit side
   ⇒ [6m, 6m+5]; bands are the intersection). The NANOMART ledger markdown's
   turn cells are STALE by design — never re-parse it.
2. **Vulcanus S3 ("True Strike") has TWO effects** (tooltip-verified, L1):
   −12% enemy Infantry/Lancer Defense for 3 turns (⇒ continuous ×0.88 fold
   from turn 3) **and** +12% own Marksmen's Attack for 1 turn
   (⇒ ×(1 + 0.12/3) average fold on a MARKSMAN dealer of the S3 holder's
   side). Your first run missed the ×0.88 fold on ledger-shaped rows
   (T5vT1 +30.4% yours vs +5..9% ours) — both folds are required this time.
3. **Hero kits and AURAS**: read `docs/HERO_KITS.md` (new). Heroes add flat
   panel-percentage-point auras (e.g. Alpaca's Vulcanus: +873.3 A/D on MM).
   Auras are IN the per-battle panels — the corpus `eff` values are correct
   per battle. The trap is cross-battle reasoning: never reuse a hero-led
   panel capture for a hero-less setup of the same troops.
4. **Gatot's kit scales with the HERO's own sheet, not the troop panels**
   (`gatot_shield_test.py`, 2026-07-18): a Gatot whose aura is ABSENT from
   the panels (unit at its no-hero baseline, e.g. the 12
   `MuellerAlpaca_1v1_T1InfvFC1T1Inf_*` rows at +194 A) is **INERT** — score
   those rows with the PLAIN law, no kit, no Royal-Legion fold (they fit
   ±3.2%). An AURA'D Gatot target vs HERO-LESS dealers = budget-absorb
   regime: net = max(0, Σ A_d·L_d/K(cls_d→Inf) − B), linear pooling,
   B measured per instrument: Mueller 201.95, FarSeer 30.15, Alpaca ≥ 6.3
   (bound only). Vulcanus-LED dealers bypass the budget → per-dealer
   S(d) = 1 + 10.727·e^(−d/16.893), then √N pooling (n>1 unvalidated —
   flag, don't fail).
5. **Winner scoring is now four-way and corpus-wide** (your main finding,
   adopted): for every scoreable row run the two-sided race and classify
   CORRECT / COIN_FLIP (clock gap ≤10%) / ABSTAIN (kit constants unmeasured
   for the configuration — e.g. hero-less dealers vs the aura'd Alpaca Gatot,
   where only the B ≥ 6.3 bound exists) / WRONG. Score BOTH branches for the
   Alpaca-target rows: (a) abstain, (b) budget-capped ⇒ defender wins under
   B_Alpaca ≥ 6.3 — report whether (b) misses anywhere.

## The law (unchanged core)

    turns(d→t) = ceil[ K(c_d,c_t) · (D_t·H_t)/(A_d·L_d) · G_w(c_d,τ_d) · G_l(c_t,τ_t) / √N_d ]

Constants verbatim from `stage6_tables.json`; base stats from
`docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json`; eff = base×(1+panel/100);
HP pool = D·H; deaths on integer turns (ceil); 1500-turn cap; two-sided race;
counters inside K. Deterministic folds: Seo-yoon S1 ×1.05/1.10/1.15;
Vulcanus S1 ×0.96 enemy Attack, S2 ×31/30 average, S3 the dual fold above;
Royal Legion (Gatot S3) −10%/−15% enemy Attack at L2/L3 — ONLY when the
holder's aura is present in the panels (see HERO_KITS.md). Composition
(anchor-mode) and beast rules as in v1.

## Known open findings — REPRODUCE these, do not re-tune around them

| row / cell | expected residual |
|---|---|
| `LabRat_1v1_T1LanvT1MM_..._213859` | two-sided winner miss, 13.6% cross-cell gap (K(Lan→MM) measured vs K(MM→Lan) factorized) |
| `MuellerAlpaca_1v1_T7InfvFC1T1Inf_..._151127` | the reverse-race anomaly: the Gatot-led T7 dealer is ≥3.9× slow vs a naked target — CONFIRMED as real physics by the T7 discriminator `..._AlpacaFC1T1Vulcanus_20260718_235302` (same tier/base/panels/target, no hero, on-law) |
| T7-Infantry-dealer rows generally | the frozen table's G_w(Inf,7) is the cube-root extrapolant 13.2; the 2026-07-18 discriminator measured 14.1–14.5 (+8%) — expect that offset on T7 dealer clocks; the table refresh is deliberately deferred to Stage 6.6 |
| `NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus` | +26% (winner miss in the race) |
| `NanoMart_1v1_T1MMvT1MM_VulcanusVsVulcanus` | ~+14% past band |
| `..._T6InfvFC1T1Inf_...VulcanusNoGatot_20260718_161706` | +18–21% (open residual) |
| K(Lan→Lan) factorized cell | −14%/−19% on its two rows (cell ~17% above the factorization) |
| SeoYoon Inf-mirror family | ~−5%, inside the coin-flip zone |

## Adversarial addendum (new this round)

Actively try to REFUTE the hero-sheet/budget unification with corpus data:
find any row where (a) an aura'd-Gatot target dies to hero-less dealers whose
Σrate < its measured/bounded B, or (b) an inert-Gatot (baseline-panel) row
deviates >5% from the plain law, or (c) a Vulcanus-led dealer is budget-capped.
Any such row is a headline finding.

## Required output (in `qa_codex_v2/`)
1. `qa2_results.csv` — one row per battle: id, matchup, observed, predicted,
   %err / band-hit / capped-correct, winner classification (four-way, both
   branches where applicable), domain class, PASS/FAIL, flags.
2. Summary by instrument bucket and by domain class; verdict on the ≤10%
   in-domain bar; every in-domain miss listed with arithmetic.
3. The adversarial-addendum result (explicit, even if empty).
4. Discrepancy section vs `stage6_validate.py` (run at the END).
5. OCR-suspect flags.
