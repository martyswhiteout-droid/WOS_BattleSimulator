# Independent Type-1 QA report

Corpus rows: **232**. Frozen law: **stage6** (2026-07-17).
Independent verdict: **FAIL** — 127/144 scored in-domain rows pass their ≤10%/integer-turn rule.

Percent error is signed `predicted_raw / midpoint(observed band) - 1`; the deviation lists use its absolute value. Capped and winner-only rows intentionally have no percent error.

## Deviations from 5% to under 10%

| id | observed | pred raw | ceil | %err | domain | verdict | flags |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AlpacaMueller_41v1_FC1T6LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_200204 | 286 | 264.240323 | 265 | -7.61% | in_gatot_budget | PASS | G_l_fallback_infantry;budget_Mueller_Gatot_S123_L1;gatot_K_LanInf_implied;gatot_budget |
| ENIF1b_R01_MuellerGordon_T1Inf_v_AlpacaFC1T1MM_20260717_004328 | [69,71] | 66.448796 | 67 | -5.07% | in_exact_duel | PASS |  |
| ENIF1b_R04_MuellerGordon_T1Inf_v_AlpacaFC1T1MM_20260717_004622 | [69,71] | 66.448796 | 67 | -5.07% | in_exact_duel | PASS |  |
| ENIF2_R12_AlpacaFC1T6MMVulcanus_v_MuellerT1InfGatot_NoAlliance_20260717_191649 | 6 | 5.673878 | 6 | -5.44% | in_gatot_scurve | PASS | G_w_bounded_marksman;gatot_scurve;ceil_exact_or_in_band |
| LabRat_1v1_T1LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_175807 | 24 | 22.760332 | 23 | -5.17% | in_exact_duel | PASS | budget_FarSeer_Gatot_S12_L1;factorized_K;gatot_budget |
| LabRat_1v1_T1LanvT5Inf_NoAttackerHero_Gatotlvl1_20260712_180803 | 9 | 8.443327 | 9 | -6.19% | in_exact_duel | PASS | base_mismatch;budget_FarSeer_Gatot_S12_L1;factorized_K;gatot_budget;ceil_exact_or_in_band |
| LabRat_1v1_T1MMvT2Inf_NoAttackerHero_Gatotlvl1_20260712_180149 | 15 | 14.134064 | 15 | -5.77% | in_exact_duel | PASS | base_mismatch;budget_FarSeer_Gatot_S12_L1;gatot_budget;ceil_exact_or_in_band |
| LabRat_1v1_T1MMvT2Inf_NoAttackerHero_Gatotlvl1_20260712_180406 | 15 | 14.134064 | 15 | -5.77% | in_exact_duel | PASS | base_mismatch;budget_FarSeer_Gatot_S12_L1;gatot_budget;ceil_exact_or_in_band |
| LabRat_1v1_T1MMvT3Inf_NoAttackerHero_Gatotlvl1_20260712_180531 | 11 | 10.132928 | 11 | -7.88% | in_exact_duel | PASS | base_mismatch;budget_FarSeer_Gatot_S12_L1;gatot_budget;ceil_exact_or_in_band |
| LabRat_1v1_T1MMvT6Inf_NoAttackerHero_Gatotlvl1_20260712_180945 | 6 | 5.469290 | 6 | -8.85% | in_exact_duel | PASS | base_mismatch;budget_FarSeer_Gatot_S12_L1;gatot_budget;ceil_exact_or_in_band |
| LabRat_67v1_T3LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_214455 | 334 | 314.372641 | 315 | -5.88% | out_base_mismatch_T3_threshold | PASS | G_l_fallback_infantry;budget_FarSeer_Gatot_S12_L1;gatot_K_LanInf_implied;gatot_budget |
| NanoMart_1v1_T1LanvT1MM_SeoYoonlvl3_Vulcanus | [79,81] | 75.058356 | 76 | -6.18% | out_vulcanus_dealer_bias_minus6_5 | PASS | factorized_K |
| NanoMart_1v1_T2InfvT2Inf_SeoYoonlvl3_Vulcanus | [265,267] | 244.711865 | 245 | -8.00% | out_nanomart_nonT1_tier | FAIL | winner_mismatch |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+10D+10H_SeoYoonlvl3_Vulcanus | [244,246] | 228.597459 | 229 | -6.69% | out_vulcanus_dealer_bias_minus6_5 | PASS |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+20D+10H_SeoYoonlvl3_Vulcanus | [241,243] | 226.178438 | 227 | -6.54% | out_vulcanus_dealer_bias_minus6_5 | PASS |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+20D_SeoYoonlvl3_Vulcanus | [265,267] | 251.685587 | 252 | -5.38% | in_nanomart_seoyoon_dealer | FAIL | winner_mismatch |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10A+20D_SeoYoonlvl3_Vulcanus | [241,243] | 226.178438 | 227 | -6.54% | out_vulcanus_dealer_bias_minus6_5 | PASS |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10D+10H_SeoYoonlvl3_Vulcanus | [268,270] | 251.457205 | 252 | -6.52% | out_vulcanus_dealer_bias_minus6_5 | PASS |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+10D_SeoYoonlvl3_Vulcanus | [241,243] | 226.178438 | 227 | -6.54% | out_vulcanus_dealer_bias_minus6_5 | PASS |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+20D+10H_SeoYoonlvl3_Vulcanus | [241,243] | 226.178438 | 227 | -6.54% | out_vulcanus_dealer_bias_minus6_5 | PASS |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+20D_SeoYoonlvl3_Vulcanus | [241,243] | 226.178438 | 227 | -6.54% | out_vulcanus_dealer_bias_minus6_5 | PASS |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10D_SeoYoonlvl3_Vulcanus | [268,270] | 251.457205 | 252 | -6.52% | out_vulcanus_dealer_bias_minus6_5 | PASS |  |
| NanoMart_SetB_1v1_T1InfvT1Inf_NoAttackerHero_Vulcanus | [268,270] | 251.457205 | 252 | -6.52% | out_vulcanus_dealer_bias_minus6_5 | PASS |  |

## Deviations of 10% or more

| id | observed | pred raw | ceil | %err | domain | verdict | flags |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LabRat_1v1_T1LanvT1MM_NoAttackerHero_Gordonlvl1_20260711_213859 | [24,26] | 21.881479 | 22 | -12.47% | in_exact_duel | FAIL | factorized_K;lh_panel_uncaptured;winner_mismatch |
| MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+194.1D+172.2L+122.0H+118.7_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_151127 | 599 | 140.907000 | 141 | -76.48% | in_exact_duel | FAIL | G_w_extrapolated;winner_mismatch |
| RFJPlayer_1v1_T6MMvT1Inf_Vulcanus_Gatot_20260713_002605 | 6 | 5.192790 | 6 | -13.45% | in_gatot_scurve | PASS | G_w_bounded_marksman;gatot_scurve;ceil_exact_or_in_band |
| MuellerAlpaca_v5_R02_1v1_T4InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012619 | 332 | 258.060494 | 259 | -22.27% | in_exact_duel | FAIL | base_mismatch;winner_mismatch |
| MuellerAlpaca_v5_R03_1v1_T5InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012641 | 398 | 229.020648 | 230 | -42.46% | in_exact_duel | FAIL | base_mismatch;winner_mismatch |
| MuellerAlpaca_v5_R04_1v1_T6InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012651 | 469 | 181.931354 | 182 | -61.21% | in_exact_duel | FAIL | base_mismatch;winner_mismatch |
| MuellerAlpaca_v5_R06_1v1_T7InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012716 | 554 | 165.295605 | 166 | -70.16% | in_exact_duel | FAIL | G_w_extrapolated;base_mismatch;winner_mismatch |
| MuellerAlpaca_v5_R07_1v1_T8InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012721 | 653 | 152.012680 | 153 | -76.72% | in_exact_duel | FAIL | G_w_extrapolated;base_mismatch;winner_mismatch |
| MuellerAlpaca_v5_R08_1v1_T9InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012734 | 771 | 141.116071 | 142 | -81.70% | in_exact_duel | FAIL | G_w_extrapolated;base_mismatch;winner_mismatch |
| MuellerAlpaca_v5_R09_1v1_T10InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012738 | 909 | 131.985560 | 132 | -85.48% | in_exact_duel | FAIL | G_w_extrapolated;base_mismatch;winner_mismatch |
| NanoMart_1v1_T1InfvT1MM_SeoYoonlvl3_Vulcanus | [7,9] | 11.959920 | 12 | 49.50% | out_vulcanus_dealer_bias_minus6_5 | FAIL |  |
| NanoMart_1v1_T1InfvT6Inf_SeoYoonlvl3_Vulcanus | [67,69] | 76.058820 | 77 | 11.85% | out_nanomart_nonT1_tier | FAIL |  |
| NanoMart_1v1_T1LanvT1Lan_SeoYoonlvl3_Vulcanus | 30 | 25.069552 | 26 | -16.43% | out_factorized_K_pm15 | FAIL | factorized_K;winner_mismatch |
| NanoMart_1v1_T1MMvT1Lan_NoAttackerHero_Vulcanus | [19,21] | 23.229954 | 24 | 16.15% | out_vulcanus_dealer_bias_minus6_5 | FAIL | factorized_K |
| NanoMart_1v1_T1MMvT1MM_VulcanusVsVulcanus | 12 | 16.070698 | 17 | 33.92% | out_vulcanus_dealer_bias_minus6_5 | FAIL |  |
| NanoMart_1v1_T3InfvT3Inf_SeoYoonlvl3_Vulcanus | [265,267] | 218.376165 | 219 | -17.90% | out_nanomart_nonT1_tier | FAIL | winner_mismatch |
| NanoMart_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus | [79,81] | 104.332923 | 105 | 30.42% | out_nanomart_nonT1_tier | FAIL |  |
| NanoMart_1v1_T6InfvT6Inf_SeoYoonlvl3_Vulcanus | 264 | 234.679488 | 235 | -11.11% | out_nanomart_nonT1_tier | FAIL | winner_mismatch |
| NanoMart_SetA_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus | [79,81] | 104.332923 | 105 | 30.42% | out_nanomart_nonT1_tier | FAIL |  |
| NanoMart_SetA_1v1_T5InfvT2Inf_SeoYoonlvl3_Vulcanus | [118,120] | 151.543570 | 152 | 27.35% | out_nanomart_nonT1_tier | FAIL |  |
| NanoMart_SetA_1v1_T6InfvT2Inf_SeoYoonlvl3_Vulcanus | [100,102] | 117.040446 | 118 | 15.88% | out_nanomart_nonT1_tier | FAIL |  |
| NanoMart_SetA_1v1_T6InfvT2Inf_SeoYoonlvl3_Vulcanus_Duplicate2 | [100,102] | 117.040446 | 118 | 15.88% | out_nanomart_nonT1_tier | FAIL |  |
| NanoMart_SetB_1v1_T1LanvT1Lan_NoAttackerHero_Vulcanus | [28,30] | 25.069552 | 26 | -13.55% | out_factorized_K_pm15 | PASS | factorized_K |

## Instrument summary

| instrument | rows | numeric | median \|err\| | max \|err\| | pass rate |
| --- | --- | --- | --- | --- | --- |
| beast | 7 | 3 | 0.08% | 0.12% | 100.00% |
| composition | 24 | 19 | 0.00% | 0.00% | 100.00% |
| exact_1v1 | 109 | 108 | 0.69% | 85.48% | 89.91% |
| gatot_gate | 6 | 6 | 4.10% | 13.45% | 100.00% |
| gatot_threshold | 6 | 2 | 3.02% | 5.88% | 100.00% |
| legacy | 9 | 0 | — | — | — |
| mixed_other | 1 | 1 | 0.04% | 0.04% | 100.00% |
| nanomart_1v1 | 38 | 38 | 6.54% | 49.50% | 47.37% |
| nanomart_multicount | 32 | 0 | — | — | 87.50% |

## Domain summary

| domain | rows | numeric | median \|err\| | max \|err\| | pass rate |
| --- | --- | --- | --- | --- | --- |
| in_beast_victory | 3 | 3 | 0.08% | 0.12% | 100.00% |
| in_composition_anchor | 19 | 19 | 0.00% | 0.00% | 100.00% |
| in_exact_duel | 109 | 108 | 0.69% | 85.48% | 89.91% |
| in_gatot_budget | 2 | 2 | 3.86% | 7.61% | 100.00% |
| in_gatot_scurve | 4 | 4 | 4.10% | 13.45% | 100.00% |
| in_nanomart_seoyoon_dealer | 7 | 7 | 4.39% | 5.38% | 14.29% |
| out_base_mismatch_T3_threshold | 2 | 2 | 3.02% | 5.88% | 100.00% |
| out_capped_stalemate | 8 | 0 | — | — | 100.00% |
| out_composition_no_front_anchor | 5 | 0 | — | — | 100.00% |
| out_composition_other_defender | 1 | 1 | 0.04% | 0.04% | 100.00% |
| out_factorized_K_pm15 | 2 | 2 | 14.99% | 16.43% | 50.00% |
| out_legacy_no_numeric_inputs | 9 | 0 | — | — | — |
| out_nanomart_multicount_winner_only | 32 | 0 | — | — | 87.50% |
| out_nanomart_nonT1_tier | 15 | 15 | 11.11% | 30.42% | 40.00% |
| out_nanomart_other | 1 | 1 | 2.28% | 2.28% | 0.00% |
| out_vulcanus_dealer_bias_minus6_5 | 13 | 13 | 6.54% | 49.50% | 76.92% |

## In-domain misses

| id | observed | predicted | %err | diagnostic arithmetic |
| --- | --- | --- | --- | --- |
| LabRat_1v1_T1LanvT1MM_NoAttackerHero_Gordonlvl1_20260711_213859 | [24,26] | 21.881479 | -12.47% | att->def [t=488.71*(1.001*1)*1/(4*5*1)*1*1/sqrt(1)=24.4599]; def->att [t=167.557*(2*2)*1/(5.105*6*1)*1*1/sqrt(1)=21.8815] |
| LabRat_1v1_T1MMvT1Inf_NoAttackerHero_Gordonlvl1_20260711_213754 | [72,74] | 71.655240 | -1.84% | att->def [t=90.11*(4.004*6)*1/(5*6*1)*1*1/sqrt(1)=72.1601]; def->att [t=73.16*(1*1)*1/(1.021*1*1)*1*1/sqrt(1)=71.6552] |
| LabRat_1v1_T1MMvT1Inf_NoAttackerHero_Gordonlvl1_20260711_214115 | [72,74] | 71.655240 | -1.84% | att->def [t=90.11*(4.004*6)*1/(5*6*1)*1*1/sqrt(1)=72.1601]; def->att [t=73.16*(1*1)*1/(1.021*1*1)*1*1/sqrt(1)=71.6552] |
| MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+194.1D+172.2L+122.0H+118.7_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_151127 | 599 | 140.907000 | -76.48% | att->def [t=12.524*(24.276*12.846)*1/(23.528*15.54*1)*13.1911*1/sqrt(1)=140.907]; def->att [t=12.524*(29.942*28.431)*1/(6.141*2.15*1)*1*0.742/sqrt(1)=599.159] |
| MuellerAlpaca_v5_R02_1v1_T4InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012619 | 332 | 258.060494 | -22.27% | att->def [t=12.524*(25.196*13.158)*1/(11.164*8.48*1)*5.884*1/sqrt(1)=258.06]; def->att [t=12.524*(22.376*20.87)*1/(6.371*2.197*1)*1*0.795/sqrt(1)=332.183] |
| MuellerAlpaca_v5_R03_1v1_T5InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012641 | 398 | 229.020648 | -42.46% | att->def [t=12.524*(25.196*13.158)*1/(16.746*10.6*1)*9.791*1/sqrt(1)=229.021]; def->att [t=12.524*(25.173*22.957)*1/(6.371*2.197*1)*1*0.77/sqrt(1)=398.15] |
| MuellerAlpaca_v5_R04_1v1_T6InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012651 | 469 | 181.931354 | -61.21% | att->def [t=12.524*(25.196*13.158)*1/(19.537*12.72*1)*10.889*1/sqrt(1)=181.931]; def->att [t=12.524*(27.97*25.044)*1/(6.371*2.197*1)*1*0.748/sqrt(1)=468.817] |
| MuellerAlpaca_v5_R06_1v1_T7InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012716 | 554 | 165.295605 | -70.16% | att->def [t=12.524*(25.196*13.158)*1/(22.328*14.84*1)*13.1911*1/sqrt(1)=165.296]; def->att [t=12.524*(30.767*27.131)*1/(6.371*2.197*1)*1*0.742/sqrt(1)=554.192] |
| MuellerAlpaca_v5_R07_1v1_T8InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012721 | 653 | 152.012680 | -76.72% | att->def [t=12.524*(25.196*13.158)*1/(25.119*16.96*1)*15.5971*1/sqrt(1)=152.013]; def->att [t=12.524*(33.564*29.218)*1/(6.371*2.197*1)*1*0.744/sqrt(1)=652.834] |
| MuellerAlpaca_v5_R08_1v1_T9InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012734 | 771 | 141.116071 | -81.70% | att->def [t=12.524*(25.196*13.158)*1/(27.91*19.08*1)*18.0988*1/sqrt(1)=141.116]; def->att [t=12.524*(36.361*31.305)*1/(6.371*2.197*1)*1*0.757/sqrt(1)=770.994] |
| MuellerAlpaca_v5_R09_1v1_T10InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012738 | 909 | 131.985560 | -85.48% | att->def [t=12.524*(25.196*13.158)*1/(30.701*21.2*1)*20.6895*1/sqrt(1)=131.986]; def->att [t=12.524*(39.158*33.392)*1/(6.371*2.197*1)*1*0.777/sqrt(1)=909.053] |
| NanoMart_1v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | 264 | 251.457205 | -4.75% | att->def [t=12.524*(4*6)*1/(1.022*1*1.104)*1*1/sqrt(1)=266.4]; def->att [t=12.524*(4.008*6)*0.88/(1.02*1*1.03333)*1*1/sqrt(1)=251.457] |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+20D_SeoYoonlvl3_Vulcanus | [265,267] | 251.685587 | -5.38% | att->def [t=12.524*(4.9*6)*1/(1.135*1.1*1.104)*1*1/sqrt(1)=267.136]; def->att [t=12.524*(4.46*6)*0.88/(1.134*1*1.03333)*1*1/sqrt(1)=251.686] |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10D+10H_SeoYoonlvl3_Vulcanus | [262,264] | 251.457205 | -4.39% | att->def [t=12.524*(4.4*6.6)*1/(1.124*1.1*1.104)*1*1/sqrt(1)=266.447]; def->att [t=12.524*(4.008*6)*0.88/(1.02*1*1.03333)*1*1/sqrt(1)=251.457] |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10D_SeoYoonlvl3_Vulcanus | [262,264] | 251.457205 | -4.39% | att->def [t=12.524*(4.4*6)*1/(1.022*1.1*1.104)*1*1/sqrt(1)=266.4]; def->att [t=12.524*(4.008*6)*0.88/(1.02*1*1.03333)*1*1/sqrt(1)=251.457] |
| NanoMart_SetA_1v1_T1InfvT1Inf_Vulcanus_SeoYoonlvl3 | [262,264] | 251.457205 | -4.39% | att->def [t=12.524*(4.008*6)*0.88/(1.02*1*1.03333)*1*1/sqrt(1)=251.457]; def->att [t=12.524*(4*6)*1/(1.022*1*1.104)*1*1/sqrt(1)=266.4] |
| NanoMart_SetB_1v1_T1InfvT1Inf_Vulcanus_SeoYoonlvl3 | [262,264] | 251.457205 | -4.39% | att->def [t=12.524*(4.008*6)*0.88/(1.02*1*1.03333)*1*1/sqrt(1)=251.457]; def->att [t=12.524*(4*6)*1/(1.022*1*1.104)*1*1/sqrt(1)=266.4] |

## Data/OCR suspects

| id | field | reason |
| --- | --- | --- |
| NanoMart_100_SeoYoonlvl3_Vulcanus | defender.casualties | losses+injured+lightly_injured+survivors=199 but troops=200 |
| NanoMart_1v1_T6InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker.classes[0].(cls,tier) | id says Infantry T6, normalized row says Infantry T4 |

## Repository cross-check discrepancies

The repository validator completed with `OVERALL: ALL GATES PASS`, but it does not implement every rule in the QA brief the same way:

- The brief requires a global two-sided race. The repository's A6/D6 tables normally score the observed winner's one-way kill clock; it only prints explicit race calls for the four ENIF1b rows. The literal race used here calls 22 winners differently from the corpus, including 17 in-domain failures. These are spec/validator disagreements, not arithmetic differences in the displayed one-way clocks.
- The four Lancer Gatot-threshold rows are not blind predictions in the repository validator: it solves their Lancer rate from the same cap/win pairs and reports an implied K. This QA uses the frozen implied K values from `gatot_kit`; the T3 pair remains out-of-domain per the declared base-mismatch tension.
- The repository accounts for 31 higher-tier NanoMart rows as excluded wrong-additive-base captures. The QA brief says to trust the corrected corpus, but declares only NanoMart T1 troop rows in-domain, so those higher-tier rows are scored here as out-of-domain.
- Beast victory clocks, the 19 numeric measured-regime composition anchors (the other five composition rows have no applicable front anchor), the four hero-led Gatot points, and the covered Marksman budget thresholds agree with the repository cross-check to rounding/turn quantization.

## Full per-row evidence

All 232 rows, including arithmetic and flags, are in `qa_results.csv`.
