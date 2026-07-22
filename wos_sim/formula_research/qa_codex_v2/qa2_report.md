# Independent Type-1 QA report — V2

Corpus rows: **236** (corpus metadata 236; frozen table metadata 232).
In-domain verdict: **FAIL** — 132/138 scored rows pass the time and four-way winner rules.
Winner classifications: CORRECT 171, COIN_FLIP 16, ABSTAIN 39, WRONG 10.
Alpaca-bound conditional capped branch: 24 rows, 0 winner misses.

Timing % error uses the unchanged V1 convention: the independently predicted clock for the side that actually won versus the observed-band midpoint. `band_edge_pcterr` separately records distance past the nearest edge; the race winner is scored separately.

## In-domain misses

| id | observed | actual-branch prediction | %err midpoint | % past band | winner | arithmetic |
| --- | --- | --- | --- | --- | --- | --- |
| LabRat_1v1_T1LanvT1MM_NoAttackerHero_Gordonlvl1_20260711_213859 | [24,26] | 24.459935 | -2.16% | 0.00% | WRONG | attacker clock [plain: 488.71*(1.001*1)*1/(4*5*1)*1*1/sqrt(1)=24.4599; target_count=1; total=24.459935]; defender clock [plain: 167.557*(2*2)*1/(5.105*6*1)*1*1/sqrt(1)=21.8815; target_count=1; total=21.881479] |
| MuellerAlpaca_1v1_T6InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+176.2D+169.0L+109.7H+109.3_NoAttackerHero_AlpacaFC1T1VulcanusNoGatot_20260718_161706 | [90,92] | 77.240946 | -15.12% | -14.18% | CORRECT | attacker clock [plain: 12.524*(10.76*12.558)*1/(19.537*12.72*0.96)*10.889*1/sqrt(1)=77.2409; target_count=1; total=77.240946]; defender clock [plain: 12.524*(27.97*25.044)*0.88/(2.762*2.097*1.03333)*1*0.748/sqrt(1)=964.853; target_count=1; total=964.852545] |
| MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+194.1D+172.2L+122.0H+118.7_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_151127 | 599 | 599.159360 | 0.03% | 0.03% | WRONG | attacker clock [plain: 12.524*(24.276*12.846)*1/(23.528*15.54*1)*13.1911*1/sqrt(1)=140.907; target_count=1; total=140.907000]; defender clock [plain: 12.524*(29.942*28.431)*1/(6.141*2.15*1)*1*0.742/sqrt(1)=599.159; target_count=1; total=599.159360] |
| NanoMart_1v1_T1InfvT1MM_SeoYoonlvl3_Vulcanus | [9,11] | 11.499923 | 15.00% | 4.54% | CORRECT | attacker clock [plain: 73.16*(6.152*1)*1/(1.022*1*1.104)*1*1/sqrt(1)=398.906; target_count=1; total=398.905528]; defender clock [plain: 90.11*(4.008*6)*0.88/(30.86*5*1.07467)*1*1/sqrt(1)=11.4999; target_count=1; total=11.499923] |
| NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus | [69,71] | 88.170254 | 25.96% | 24.18% | WRONG | attacker clock [plain: 90.11*(4*6)*1/(5.11*5*0.96)*1*1/sqrt(1)=88.1703; target_count=1; total=88.170254]; defender clock [plain: 73.16*(1.002*1)*1/(1.02*1*1.03333)*1*1/sqrt(1)=69.5506; target_count=1; total=69.550588] |
| NanoMart_1v1_T1MMvT1MM_VulcanusVsVulcanus | [12,14] | 15.452594 | 18.87% | 10.38% | CORRECT | attacker clock [plain: 566.66*(6.152*1)*1/(21.805*5*1.03168)*1*1/sqrt(1)=30.9933; target_count=1; total=30.993297]; defender clock [plain: 566.66*(4.341*1)*1/(30.86*5*1.03168)*1*1/sqrt(1)=15.4526; target_count=1; total=15.452594] |

## Known-finding reproduction

| finding | observed | prediction | %err midpoint | % past band | winner | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| Gordon Lan→MM race | [24,26] | 24.459935 | -2.16% | 0.00% | WRONG | FAIL |
| T7 Gatot reverse race | 599 | 599.159360 | 0.03% | 0.03% | WRONG | FAIL |
| T7 no-hero discriminator | [75,77] | 70.178057 | -7.66% | -6.43% | CORRECT | PASS |
| Nano MM→Inf | [69,71] | 88.170254 | 25.96% | 24.18% | WRONG | FAIL |
| Nano MM mirror | [12,14] | 15.452594 | 18.87% | 10.38% | CORRECT | FAIL |
| T6 open residual | [90,92] | 77.240946 | -15.12% | -14.18% | CORRECT | FAIL |
| Factorized Lan→Lan (Seo) | [30,32] | 26.559312 | -14.32% | -11.47% | COIN_FLIP | PASS |
| Factorized Lan→Lan (naked) | [30,32] | 25.069552 | -19.13% | -16.43% | CORRECT | FAIL |

The representative Seo-yoon Infantry mirror remains a COIN_FLIP with a 5.94% two-clock gap; its actual-winner branch is +0.53% from the band midpoint.

## Instrument summary

| instrument | rows | numeric | median \|err\| | max \|err\| | pass rate |
| --- | --- | --- | --- | --- | --- |
| beast | 7 | 3 | 0.08% | 0.12% | 100.00% |
| composition | 24 | 19 | 0.00% | 0.00% | 100.00% |
| exact_1v1 | 88 | 87 | 0.65% | 15.12% | 96.59% |
| gatot_alpaca_bound | 24 | 24 | 0.10% | 1.02% | — |
| gatot_gate | 7 | 7 | 3.88% | 7.61% | 100.00% |
| gatot_threshold | 6 | 2 | 3.02% | 5.88% | 100.00% |
| legacy | 9 | 0 | — | — | — |
| mixed_other | 1 | 0 | — | — | — |
| nanomart_1v1 | 38 | 38 | 7.26% | 27.24% | 73.68% |
| nanomart_multicount | 32 | 0 | — | — | 78.12% |

## Domain summary

| domain | rows | numeric | median \|err\| | max \|err\| | pass rate |
| --- | --- | --- | --- | --- | --- |
| in_beast_victory | 3 | 3 | 0.08% | 0.12% | 100.00% |
| in_composition_anchor | 19 | 19 | 0.00% | 0.00% | 100.00% |
| in_exact_duel | 88 | 87 | 0.65% | 15.12% | 96.59% |
| in_gatot_budget | 2 | 2 | 3.86% | 7.61% | 100.00% |
| in_gatot_scurve | 5 | 5 | 3.88% | 7.54% | 100.00% |
| in_nanomart_T1 | 21 | 21 | 7.21% | 25.96% | 85.71% |
| out_base_mismatch_T3_threshold | 2 | 2 | 3.02% | 5.88% | 100.00% |
| out_capped_beast | 4 | 0 | — | — | 100.00% |
| out_capped_stalemate | 4 | 0 | — | — | 100.00% |
| out_composition_no_front_anchor | 5 | 0 | — | — | — |
| out_composition_other_defender | 1 | 0 | — | — | — |
| out_factorized_K_pm15 | 2 | 2 | 16.73% | 19.13% | 50.00% |
| out_gatot_alpaca_bound_abstain | 24 | 24 | 0.10% | 1.02% | — |
| out_legacy_no_numeric_inputs | 9 | 0 | — | — | — |
| out_nanomart_multicount_winner_only | 32 | 0 | — | — | 78.12% |
| out_nanomart_nonT1_tier | 15 | 15 | 6.18% | 27.24% | 60.00% |

## Adversarial addendum

- Aura'd Gatot target deaths below measured/bounded B: **0**.
- Inert-Gatot plain-law rows checked: **13**; >5% timing misses: **0**.
- Vulcanus-led Gatot-gate rows checked: **5**; budget-capped/unresolved: **0**.

## Alpaca bound branch

Primary classification is ABSTAIN because only B≥6.3 is measured. Under the conditional budget-capped branch, 24/24 winners match.

## OCR/data suspects

| id | field | reason |
| --- | --- | --- |
| NanoMart_1v1_T6InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker.classes[0].(cls,tier) | id says Infantry T6, row says Infantry T4 |

## Repository cross-check

The independent 236-row result was hash-locked before the one permitted `stage6_validate.py` run; see `pre_crosscheck_v2.lock.json`. The validator exited 1 on its two already-open gates: the factorized Lan→Lan estimator and the two-sided winner gate.

- Numeric agreement: the validator reproduced the independent clocks on the three shared WRONG races (Gordon Lan→MM, the T7 Gatot reverse race, and Nano MM→Inf) and on the checked Nano/Vulcanus rows. This cross-check did not change any predictor constant or clock.
- Coverage/classification difference: its W6 gate classified only 147 rows (84 CORRECT, 14 COIN_FLIP, 46 ABSTAIN, 3 WRONG). This V2 run classifies all 236 (171/16/39/10). The extra seven independent WRONG results are winner-only Nano multi-count rows that W6 excludes; V2 explicitly requires corpus-wide four-way scoring.
- Gatot difference: W6 still abstains on older unmeasured-kit categories, including baseline-panel Gatot configurations. V2 says those Gatots are inert, so this run applies the plain law; all 13 inert target-direction checks are within 5%.
- New-row difference: the validator's accounting lists the new T6 open residual and T7 discriminator among `excluded: OTHER`; this run scores them directly. It also labels its accounting as 232 rows while printing 236/236, matching the stale `stage6_tables.json` metadata rather than the current corpus count.
- Reporting convention: the cross-check confirmed that V1/validator `%err` is midpoint-based. The pre-cross-check edge-scored snapshot is preserved; final PASS/FAIL restores the unchanged midpoint bar and exposes edge error separately. This adds the Nano Inf→MM timing row (15.00% midpoint, 4.54% past the band) as a sixth in-domain miss.

## Full evidence

All 236 rows are in `qa2_results.csv`; verdict-ABSTAIN rows: 30.
