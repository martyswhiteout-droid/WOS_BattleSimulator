# TYPE1_CORPUS — canonical Type-1 deterministic battle-report corpus

Generated: 2026-07-19T13:06:59

**Total rows: 243**

## Coverage

### By folder

| folder | rows |
|---|---|
| NanoMart | 70 |
| Lab Rat | 50 |
| MuellerAlpaca | 32 |
| FarSeerGatot_v3 | 18 |
| MuellerAlpaca_Gatot_2v2 | 16 |
| MuellerAlpaca_Gatot_v4 | 15 |
| ENIF | 12 |
| MuellerAlpaca_Gatot_v5 | 9 |
| legacy | 9 |
| Meuller_Alpaca_v5_8_Battle | 8 |
| AlpacaGatot_FC1_T6_LanMM | 4 |

### By determinism class

| determinism | rows |
|---|---|
| clean | 123 |
| vulcanus_deterministic | 95 |
| gordon_deterministic | 16 |
| legacy_unverified | 9 |

### Matchup coverage (winner class -> loser class)

| winner class | loser class | rows |
|---|---|---|
| Infantry | Infantry | 146 |
| Infantry | Lancer | 29 |
| Infantry | Marksman | 28 |
| Marksman | Infantry | 14 |
| Lancer | Marksman | 6 |
| Lancer | Lancer | 6 |
| Lancer | Infantry | 5 |
| Marksman | Marksman | 4 |
| Marksman | Lancer | 1 |

### Same-class Infantry mirrors (winner tier -> loser tier)

| winner T | loser T | rows |
|---|---|---|
| T1 | T1 | 89 |
| T1 | T10 | 1 |
| T1 | T2 | 1 |
| T1 | T3 | 1 |
| T1 | T4 | 1 |
| T1 | T5 | 1 |
| T1 | T6 | 1 |
| T1 | T7 | 2 |
| T1 | T8 | 1 |
| T1 | T9 | 1 |
| T2 | T1 | 3 |
| T2 | T2 | 1 |
| T3 | T1 | 9 |
| T3 | T2 | 1 |
| T3 | T3 | 1 |
| T4 | T1 | 2 |
| T4 | T2 | 1 |
| T5 | T1 | 2 |
| T5 | T2 | 1 |
| T6 | T1 | 4 |
| T6 | T2 | 2 |
| T6 | T6 | 17 |
| T7 | T1 | 3 |

## Corrections & suspect flags applied

- **MuellerAlpaca_1v1_T2InfvFC1T1Inf_AttInfA+194.1D+221.4L+122.0H+118.7_DefInfA+514.1D+506.9L+109.7H+109.3_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_154739** (`MuellerAlpaca`, json):
  - set `{'attacker_true_class': 'Lancer', 'attacker_true_tier': 2}` — OCR mislabel: attacker was a T2 LANCER not Infantry. Martin verified vs screenshot 2026-07-13. deployed_class already edited in-file; setup text and filename still say Inf; use stats_pct.Lancer. (verified_by: Martin 2026-07-13)
- **MuellerAlpaca_1v1_T2InfvFC1T1Inf_AttInfA+194.1D+221.4L+122.0H+118.7_DefInfA+514.1D+506.9L+109.7H+109.3_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_154928** (`MuellerAlpaca`, json):
  - set `{'attacker_true_class': 'Lancer', 'attacker_true_tier': 2}` — Same OCR mislabel as 154739 (second run). (verified_by: Martin 2026-07-13)
- **ColonelMuller_1v2_T1MMvT1Inf+T1MM_NoHeroes_Gatot+Vulcanus_20260713_112003** (`MuellerAlpaca_Gatot_2v2`, json):
  - set `{'attacker_true_class': 'Infantry', 'attacker_naked': True}` — OCR mislabel: attacker was a NAKED INFANTRY (6 turns), not a Marksman. The real 1-named-MM battle took 3 turns at 11:19:36 and has NO JSON (see manual rows). Martin 2026-07-13. (verified_by: Martin 2026-07-13)
- **NanoMart_1v1_T1LanvT1MM_SeoYoonlvl3_Vulcanus** (`NanoMart`, nanomart_ledger):
  - set `{'attacker_stats_pct': {'Lancer': {'Attack': 2.2, 'Defense': 0.2}}, 'defender_true_class': 'Infantry', 'defender_stats_pct': {'Infantry': {'Attack': 2.0, 'Defense': 0.0}}}` — OCR mislabel (Stage-5 flagged record anomaly, resolved): the DEFENDER is minimart's near-naked T1 INFANTRY (+2.0A/+0.0D), not a Marksman; attacker stays nanomart's naked T1 Lancer; defender wins in [79,81] (Vulcanus S2=13/S3=27). Source JSON corrected in-file by Martin; ledger not regenerated -- registry overrides. With the correction the row fits the frozen law at -6% (the known Vulcanus-dealer fold offset). L/H panel rows not visible (base assumed). (verified_by: Martin 2026-07-14 (screenshot re-check))

## Battles by folder

### AlpacaGatot_FC1_T6_LanMM (4 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| AlpacaMueller_21v1_FC1T6MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_194705 | 21xFC1T6Marksman v 1xT1Infantry | defender | 1500 | clean |  |
| AlpacaMueller_22v1_FC1T6MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_194558 | 22xFC1T6Marksman v 1xT1Infantry | attacker | 147 | clean |  |
| AlpacaMueller_40v1_FC1T6LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_unknown | 40xFC1T6Lancer v 1xT1Infantry | defender | 1500 | clean |  |
| AlpacaMueller_41v1_FC1T6LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_200204 | 41xFC1T6Lancer v 1xT1Infantry | attacker | 286 | clean |  |

### ENIF (12 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| ENIF1b_R01_MuellerGordon_T1Inf_v_AlpacaFC1T1MM_20260717_004328 | 1xT1Infantry v 1xFC1T1Marksman | attacker | None | gordon_deterministic |  |
| ENIF1b_R02_MuellerGordon_T1Inf_v_AlpacaFC1T1MM_20260717_004437 | 1xT1Infantry v 1xFC1T1Marksman | defender | None | gordon_deterministic |  |
| ENIF1b_R03_MuellerGordon_T1Inf_v_AlpacaFC1T1MM_20260717_004607 | 1xT1Infantry v 2xFC1T1Marksman | defender | None | gordon_deterministic |  |
| ENIF1b_R04_MuellerGordon_T1Inf_v_AlpacaFC1T1MM_20260717_004622 | 1xT1Infantry v 1xFC1T1Marksman | attacker | None | gordon_deterministic |  |
| ENIF2_R05_AlpacaFC1T1MM_v_MuellerT1InfGatot_20260717_004906 | 1xFC1T1Marksman v 1xT1Infantry | defender | 38 | clean |  |
| ENIF2_R06_AlpacaFC1T3MM_v_MuellerT1InfGatot_20260717_004958 | 1xFC1T3Marksman v 1xT1Infantry | defender | 81 | clean |  |
| ENIF2_R07_AlpacaFC1T6MM_v_MuellerT1InfGatot_20260717_005034 | 1xFC1T6Marksman v 1xT1Infantry | defender | 150 | clean |  |
| ENIF2_R11_AlpacaFC1T3MMVulcanus_v_MuellerT1InfGatot_NoAlliance_20260717_191558 | 1xFC1T3Marksman v 1xT1Infantry | attacker | 21 | vulcanus_deterministic |  |
| ENIF2_R12_AlpacaFC1T6MMVulcanus_v_MuellerT1InfGatot_NoAlliance_20260717_191649 | 1xFC1T6Marksman v 1xT1Infantry | attacker | 6 | vulcanus_deterministic |  |
| ENIF3_R08_AlpacaFC1T1Lan_v_MuellerT1MMGordon_20260717_005355 | 1xFC1T1Lancer v 1xT1Marksman | attacker | None | gordon_deterministic | base_mismatch |
| ENIF3_R09_AlpacaFC1T3Lan_v_MuellerT1MMGordon_20260717_005448 | 1xFC1T3Lancer v 1xT1Marksman | attacker | None | gordon_deterministic | base_mismatch |
| ENIF3_R10_AlpacaFC1T6Lan_v_MuellerT1MMGordon_20260717_005543 | 1xFC1T6Lancer v 1xT1Marksman | attacker | None | gordon_deterministic | base_mismatch |

### FarSeerGatot_v3 (18 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| LabRat_1v1_T1InfvT2Inf_NoAttackerHero_Gatotlvl1_20260712_180229 | 1xT1Infantry v 1xT2Infantry | defender | 62 | clean |  |
| LabRat_1v1_T1LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_175807 | 1xT1Lancer v 1xT1Infantry | defender | 24 | clean |  |
| LabRat_1v1_T1LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_175937 | 1xT1Lancer v 1xT1Infantry | defender | 27 | clean |  |
| LabRat_1v1_T1LanvT2Inf_NoAttackerHero_Gatotlvl1_20260712_180101 | 1xT1Lancer v 1xT2Infantry | defender | 18 | clean |  |
| LabRat_1v1_T1LanvT2Inf_NoAttackerHero_Gatotlvl1_20260712_180341 | 1xT1Lancer v 1xT2Infantry | defender | 18 | clean |  |
| LabRat_1v1_T1LanvT3Inf_NoAttackerHero_Gatotlvl1_20260712_180446 | 1xT1Lancer v 1xT3Infantry | defender | 13 | clean | base_mismatch |
| LabRat_1v1_T1LanvT4Inf_NoAttackerHero_Gatotlvl1_20260712_180608 | 1xT1Lancer v 1xT4Infantry | defender | 10 | clean | base_mismatch |
| LabRat_1v1_T1LanvT5Inf_NoAttackerHero_Gatotlvl1_20260712_180803 | 1xT1Lancer v 1xT5Infantry | defender | 9 | clean | base_mismatch |
| LabRat_1v1_T1LanvT6Inf_NoAttackerHero_Gatotlvl1_20260712_180932 | 1xT1Lancer v 1xT6Infantry | defender | 7 | clean | base_mismatch |
| LabRat_1v1_T1MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_175821 | 1xT1Marksman v 1xT1Infantry | defender | 19 | clean | base_mismatch |
| LabRat_1v1_T1MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_180006 | 1xT1Marksman v 1xT1Infantry | defender | 22 | clean | base_mismatch |
| LabRat_1v1_T1MMvT2Inf_NoAttackerHero_Gatotlvl1_20260712_180149 | 1xT1Marksman v 1xT2Infantry | defender | 15 | clean | base_mismatch |
| LabRat_1v1_T1MMvT2Inf_NoAttackerHero_Gatotlvl1_20260712_180406 | 1xT1Marksman v 1xT2Infantry | defender | 15 | clean | base_mismatch |
| LabRat_1v1_T1MMvT3Inf_NoAttackerHero_Gatotlvl1_20260712_180531 | 1xT1Marksman v 1xT3Infantry | defender | 11 | clean | base_mismatch |
| LabRat_1v1_T1MMvT4Inf_NoAttackerHero_Gatotlvl1_20260712_180622 | 1xT1Marksman v 1xT4Infantry | defender | 8 | clean | base_mismatch |
| LabRat_1v1_T1MMvT5Inf_NoAttackerHero_Gatotlvl1_20260712_180821 | 1xT1Marksman v 1xT5Infantry | defender | 7 | clean | base_mismatch |
| LabRat_1v1_T1MMvT6Inf_NoAttackerHero_Gatotlvl1_20260712_180945 | 1xT1Marksman v 1xT6Infantry | defender | 6 | clean | base_mismatch |
| LabRat_2v1_T1LanT3MMvT2Inf_NoAttackerHero_Gatotlvl1_20260712_180321 | 1xT1Lancer+1xT3Marksman v 1xT2Infantry | defender | 49 | clean | base_mismatch |

### Lab Rat (50 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| FarSeer_1v1_T1InfvT1Inf_AttInfA+188.6_Gatotlvl1_NoDefenderHero_20260712_083001 | 1xT1Infantry v 1xT1Infantry | attacker | 104 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+217.4_Gatotlvl1_NoDefenderHero_20260712_083146 | 1xT1Infantry v 1xT1Infantry | attacker | 95 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+219.6_Gatotlvl1_NoDefenderHero_20260712_084011 | 1xT1Infantry v 1xT1Infantry | attacker | 94 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+248.7_Gatotlvl1_NoDefenderHero_20260712_085141 | 1xT1Infantry v 1xT1Infantry | attacker | 87 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+251.1_Gatotlvl1_NoDefenderHero_20260712_085329 | 1xT1Infantry v 1xT1Infantry | attacker | 86 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7D+186.6L+0.0H+0.0_DefInfA+14.0D+15.0L+11.8H+12.8_Gatotlvl1_NoDefenderHero_20260712_125440 | 1xT1Infantry v 1xT1Infantry | attacker | 109 | clean |  |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7D+186.6L+0.0H+0.0_DefInfA+19.6D+20.6L+1.8H+2.8_Gatotlvl1_NoDefenderHero_20260712_125607 | 1xT1Infantry v 1xT1Infantry | attacker | 104 | clean |  |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7D+186.6L+0.0H+0.0_DefInfA+4.0D+5.0L+1.8H+14.4_Gatotlvl1_NoDefenderHero_20260712_130906 | 1xT1Infantry v 1xT1Infantry | attacker | 101 | clean |  |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7D+186.6L+0.0H+0.0_DefInfA+4.0D+5.0L+1.8H+4.0_Gatotlvl1_NoDefenderHero_20260712_130534 | 1xT1Infantry v 1xT1Infantry | attacker | 92 | clean |  |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7D+186.6L+0.0H+0.0_DefInfA+4.0D+5.0L+1.8H+4.0_Gatotlvl1_NoDefenderHero_20260712_130627 | 1xT1Infantry v 1xT1Infantry | attacker | 92 | clean |  |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7D+192.1L+0.0H+0.0_DefInfA+14.0D+15.0L+11.8H+27.1_Gatotlvl1_NoDefenderHero_20260712_135033 | 1xT1Infantry v 1xT1Infantry | attacker | 123 | clean |  |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7D+192.1L+0.0H+0.0_DefInfA+4.0D+5.0L+1.8H+16.1_Gatotlvl1_NoDefenderHero_20260712_135000 | 1xT1Infantry v 1xT1Infantry | attacker | 103 | clean |  |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_DefInfA+19.6D+32.6H+10.0_Gatotlvl1_NoDefenderHero_20260712_093521 | 1xT1Infantry v 1xT1Infantry | attacker | 123 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_DefInfA+19.6D+32.6_Gatotlvl1_NoDefenderHero_20260712_092727 | 1xT1Infantry v 1xT1Infantry | attacker | 112 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_DefInfA+19.6D+32.6_Gatotlvl1_NoDefenderHero_20260712_093016 | 1xT1Infantry v 1xT1Infantry | attacker | 112 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_DefInfA+4.0D+0.0_Gatotlvl1_NoDefenderHero_20260712_092047 | 1xT1Infantry v 1xT1Infantry | attacker | 84 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_DefInfA+4.0D+10.0_Gatotlvl1_NoDefenderHero_20260712_092223 | 1xT1Infantry v 1xT1Infantry | attacker | 93 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_DefInfA+4.0D+15.5H+10.0_Gatotlvl1_NoDefenderHero_20260712_093608 | 1xT1Infantry v 1xT1Infantry | attacker | 107 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_DefInfA+4.0D+15.5H+11.1_Gatotlvl1_NoDefenderHero_20260712_095059 | 1xT1Infantry v 1xT1Infantry | attacker | 108 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_DefInfA+4.0D+15.5_Gatotlvl1_NoDefenderHero_20260712_092648 | 1xT1Infantry v 1xT1Infantry | attacker | 97 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_DefInfA+4.0D+5.0H+1.0_Gatotlvl1_NoDefenderHero_20260712_123341 | 1xT1Infantry v 1xT1Infantry | attacker | 89 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_DefInfA+4.0D+5.0H+1.5_Gatotlvl1_NoDefenderHero_20260712_123621 | 1xT1Infantry v 1xT1Infantry | attacker | 90 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+257.7_Gatotlvl1_NoDefenderHero_20260712_090948 | 1xT1Infantry v 1xT1Infantry | attacker | 84 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+269.7D+196.6L+10.0H+10.0_DefInfA+4.0D+5.0L+1.8H+14.4_Gatotlvl1_NoDefenderHero_20260712_131030 | 1xT1Infantry v 1xT1Infantry | attacker | 89 | clean |  |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+269.7D+202.1L+10.0H+10.0_DefInfA+4.0D+5.0L+1.8H+16.1_Gatotlvl1_NoDefenderHero_20260712_134827 | 1xT1Infantry v 1xT1Infantry | attacker | 90 | clean |  |
| FarSeer_1v1_T1InfvT1Inf_AttInfA+269.7D+202.1L+10.0H+10.0_DefInfA+4.0D+5.0L+1.8H+16.1_Gatotlvl1_NoDefenderHero_20260712_135653 | 1xT1Infantry v 1xT1Infantry | attacker | 90 | clean |  |
| FarSeer_1v1_T1InfvT1Inf_Ursarlvl2_NoDefenderHero_20260712_013710 | 1xT1Infantry v 1xT1Infantry | attacker | None | gordon_deterministic | lh_panel_uncaptured,no_turn_clock |
| FarSeer_1v1_T1MMvT1MM_Gordonlvl1_NoDefenderHero_20260711_213829 | 1xT1Marksman v 1xT1Marksman | attacker | None | gordon_deterministic | lh_panel_uncaptured |
| FarSeer_1v1_T3InfvT1Inf_AttInfA+257.7D+186.6L+0.0H+0.0_DefInfA+4.0D+5.0L+1.8H+14.4_Gatotlvl1_NoDefenderHero_20260712_130941 | 1xT3Infantry v 1xT1Infantry | attacker | 49 | clean |  |
| FarSeer_1v1_T3InfvT1Inf_AttInfA+257.7D+186.6L+0.0H+0.0_DefInfA+4.0D+5.0L+1.8H+4.0_Gatotlvl1_NoDefenderHero_20260712_130801 | 1xT3Infantry v 1xT1Infantry | attacker | 44 | clean |  |
| FarSeer_1v1_T3InfvT1Inf_AttInfA+257.7D+192.1L+0.0H+0.0_DefInfA+14.0D+15.0L+11.8H+27.1_Gatotlvl1_NoDefenderHero_20260712_135113 | 1xT3Infantry v 1xT1Infantry | attacker | 59 | clean |  |
| FarSeer_1v1_T3InfvT1Inf_AttInfA+257.7D+192.1L+0.0H+0.0_DefInfA+4.0D+5.0L+1.8H+16.1_Gatotlvl1_NoDefenderHero_20260712_135603 | 1xT3Infantry v 1xT1Infantry | attacker | 49 | clean |  |
| FarSeer_1v1_T3InfvT1Inf_AttInfA+257.7_DefInfA+4.0D+5.0H+1.0_Gatotlvl1_NoDefenderHero_20260712_123127 | 1xT3Infantry v 1xT1Infantry | attacker | 43 | clean | lh_panel_uncaptured |
| FarSeer_1v1_T3InfvT1Inf_AttInfA+269.7D+196.6L+10.0H+10.0_DefInfA+4.0D+5.0L+1.8H+14.4_Gatotlvl1_NoDefenderHero_20260712_131118 | 1xT3Infantry v 1xT1Infantry | attacker | 43 | clean |  |
| FarSeer_1v1_T3InfvT1Inf_AttInfA+269.7D+202.1L+10.0H+10.0_DefInfA+4.0D+5.0L+1.8H+16.1_Gatotlvl1_NoDefenderHero_20260712_134910 | 1xT3Infantry v 1xT1Infantry | attacker | 43 | clean |  |
| FarSeer_1v1_T3InfvT1Inf_AttInfA+272.1D+202.1L+10.0H+10.0_DefInfA+4.0D+5.0L+1.8H+16.1_Gatotlvl1_NoDefenderHero_20260712_135804 | 1xT3Infantry v 1xT1Infantry | attacker | 43 | clean |  |
| FarSeer_Beast_1v18_T1InfvT1Inf_Att+10L_Gatotlvl1_NoDefenderHero_20260712_021010 | 1xT1Infantry v 18xT1Infantry | defender | 1500 | clean | lh_panel_uncaptured,beast_mapping_assumed |
| FarSeer_Beast_1v18_T1InfvT1Inf_Att+21.6L+53.2H_Gatotlvl1_NoDefenderHero_UserSummary | 1xT1Infantry v 18xT1Infantry | defender | 1500 | clean | lh_panel_uncaptured,beast_mapping_assumed |
| FarSeer_Beast_1v18_T1InfvT1Inf_Att+21.6L_Gatotlvl1_NoDefenderHero_20260712_021112 | 1xT1Infantry v 18xT1Infantry | defender | 1500 | clean | lh_panel_uncaptured,beast_mapping_assumed |
| FarSeer_Beast_1v18_T1InfvT1Inf_Att+32.7L+53.2H_Gatotlvl1_NoDefenderHero_20260712_021542 | 1xT1Infantry v 18xT1Infantry | attacker | 1411 | clean | beast_mapping_assumed |
| FarSeer_Beast_1v18_T1InfvT1Inf_Gatotlvl1_NoDefenderHero_20260712_020035 | 1xT1Infantry v 18xT1Infantry | defender | 1500 | clean | lh_panel_uncaptured,beast_mapping_assumed |
| FarSeer_Beast_1v18_T2InfvT1Inf_Gatotlvl1_NoDefenderHero_20260712_020124 | 1xT2Infantry v 18xT1Infantry | attacker | 1255 | clean | lh_panel_uncaptured,beast_mapping_assumed |
| FarSeer_Beast_1v18_T6InfvT1Inf_Gatotlvl1_NoDefenderHero_20260712_015509 | 1xT6Infantry v 18xT1Infantry | attacker | 486 | clean | lh_panel_uncaptured,beast_mapping_assumed |
| LabRat_1v1_T1InfvT1Inf_NoAttackerHero_Eliflvl1_20260712_013954 | 1xT1Infantry v 1xT1Infantry | defender | 44 | gordon_deterministic | lh_panel_uncaptured |
| LabRat_1v1_T1InfvT1Inf_NoAttackerHero_Gatotlvl1_20260712_014520 | 1xT1Infantry v 1xT1Infantry | defender | 104 | clean | lh_panel_uncaptured |
| LabRat_1v1_T1InfvT1Inf_NoAttackerHero_Gordonlvl1_20260711_214025 | 1xT1Infantry v 1xT1Infantry | defender | None | gordon_deterministic | lh_panel_uncaptured |
| LabRat_1v1_T1LanvT1Inf_NoAttackerHero_Gordonlvl1_20260711_214053 | 1xT1Lancer v 1xT1Infantry | defender | None | gordon_deterministic | lh_panel_uncaptured |
| LabRat_1v1_T1LanvT1MM_NoAttackerHero_Gordonlvl1_20260711_213859 | 1xT1Lancer v 1xT1Marksman | attacker | None | gordon_deterministic | lh_panel_uncaptured |
| LabRat_1v1_T1MMvT1Inf_NoAttackerHero_Gordonlvl1_20260711_213754 | 1xT1Marksman v 1xT1Infantry | attacker | None | gordon_deterministic | lh_panel_uncaptured |
| LabRat_1v1_T1MMvT1Inf_NoAttackerHero_Gordonlvl1_20260711_214115 | 1xT1Marksman v 1xT1Infantry | attacker | None | gordon_deterministic | lh_panel_uncaptured |

### Meuller_Alpaca_v5_8_Battle (8 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| ColonelMuller_11v2_T1Inf+10T1MMvT1Inf+T1MM_Gatot+NoMMHero_Gatot+Vulcanus_20260714_004004 | 1xT1Infantry+10xT1Marksman v 1xT1Infantry+1xT1Marksman | defender | None | vulcanus_deterministic | no_turn_clock |
| ColonelMuller_1v2_T1InfvT1Inf+T1MM_Gatot_Gatot+Vulcanus_20260714_003803 | 1xT1Infantry v 1xT1Infantry+1xT1Marksman | defender | 78 | vulcanus_deterministic |  |
| ColonelMuller_2v2_T1Inf+T1LanvT1Inf+T1MM_Gatot_Gatot+Vulcanus_20260714_004535 | 1xT1Infantry+1xT1Lancer v 1xT1Infantry+1xT1Marksman | defender | None | vulcanus_deterministic | no_turn_clock |
| ColonelMuller_2v2_T1Inf+T1MMvT1Inf+T1MM_Gatot+NoMMHero_Gatot+Vulcanus_20260714_003822 | 1xT1Infantry+1xT1Marksman v 1xT1Infantry+1xT1Marksman | defender | None | vulcanus_deterministic | no_turn_clock |
| ColonelMuller_3v2_T1Inf+2T1MMvT1Inf+T1MM_Gatot+NoMMHero_Gatot+Vulcanus_20260714_003848 | 1xT1Infantry+2xT1Marksman v 1xT1Infantry+1xT1Marksman | defender | None | vulcanus_deterministic | no_turn_clock |
| ColonelMuller_4v2_T1Inf+3T1MMvT1Inf+T1MM_Gatot+NoMMHero_Gatot+Vulcanus_20260714_003911 | 1xT1Infantry+3xT1Marksman v 1xT1Infantry+1xT1Marksman | defender | None | vulcanus_deterministic | no_turn_clock |
| ColonelMuller_5v2_T1Inf+4T1MMvT1Inf+T1MM_Gatot+NoMMHero_Gatot+Vulcanus_20260714_004940 | 1xT1Infantry+4xT1Marksman v 1xT1Infantry+1xT1Marksman | defender | None | vulcanus_deterministic | no_turn_clock |
| ColonelMuller_6v2_T1Inf+5T1MMvT1Inf+T1MM_Gatot+NoMMHero_Gatot+Vulcanus_20260714_003939 | 1xT1Infantry+5xT1Marksman v 1xT1Infantry+1xT1Marksman | defender | None | vulcanus_deterministic | no_turn_clock |

### MuellerAlpaca (32 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| Alpaca_1v1_FC1T1LanvT1Lan_Gordonlvl64_Gordonlvl51_20260719_122337 | 1xT1Lancer v 1xT1Lancer | attacker | 21 | gordon_deterministic |  |
| Alpaca_1v1_T1MMFC1vT1InfFC1_Vulcanus_Gatot_20260713_105103 | 1xT1Marksman v 1xT1Infantry | attacker | 102 | vulcanus_deterministic |  |
| Alpaca_3v1_FC1T6MMvT1Inf_Vulcanus_GatotAurad_20260719_120930 | 3xT6Marksman v 1xT1Infantry | attacker | 4 | vulcanus_deterministic |  |
| LabRat_32v1_T3MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_213727 | 32xT3Marksman v 1xT1Infantry | defender | 1500 | clean |  |
| LabRat_33v1_T3MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_213849 | 33xT3Marksman v 1xT1Infantry | attacker | 186 | clean |  |
| LabRat_66v1_T3LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_214434 | 66xT3Lancer v 1xT1Infantry | defender | 1500 | clean |  |
| LabRat_67v1_T3LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_214455 | 67xT3Lancer v 1xT1Infantry | attacker | 334 | clean |  |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+194.1D+172.2L+122.0H+118.7_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_150803 | 1xT1Infantry v 1xFC1T1Infantry | defender | 132 | clean |  |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+229.4L+122.0H+156.6_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_151512 | 1xT1Infantry v 1xFC1T1Infantry | defender | 187 | clean |  |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+229.4L+126.4H+123.6_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_151159 | 1xT1Infantry v 1xFC1T1Infantry | defender | 163 | clean |  |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+268.4L+122.0H+118.7_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_151839 | 1xT1Infantry v 1xFC1T1Infantry | defender | 178 | clean |  |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+268.4L+122.0H+118.7_DefInfA+514.1D+506.9L+172.3H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_152106 | 1xT1Infantry v 1xFC1T1Infantry | defender | 141 | clean |  |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+282.7L+122.0H+118.7_DefInfA+514.1D+506.9L+172.3H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_152248 | 1xT1Infantry v 1xFC1T1Infantry | defender | 146 | clean |  |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+284.4L+122.0H+118.7_DefInfA+514.1D+506.9L+172.3H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_152350 | 1xT1Infantry v 1xFC1T1Infantry | defender | 147 | clean |  |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+284.4L+122.0H+156.6_DefInfA+514.1D+506.9L+109.7H+109.3_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_152607 | 1xT1Infantry v 1xFC1T1Infantry | defender | 223 | clean |  |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+284.4L+122.0H+156.6_DefInfA+514.1D+506.9L+109.7H+109.3_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_152719 | 1xT1Infantry v 1xFC1T1Infantry | defender | 232 | clean | other_hero_present |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+284.4L+122.0H+156.6_DefInfA+514.1D+506.9L+109.7H+109.3_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_152939 | 1xT1Infantry v 1xFC1T1Infantry | defender | 232 | clean | other_hero_present |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+284.4L+122.0H+156.6_DefInfA+514.1D+506.9L+109.7H+109.3_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_154616 | 1xT1Infantry v 1xFC1T1Infantry | defender | 237 | clean | other_hero_present |
| MuellerAlpaca_1v1_T1InfvFC1T1Inf_AttInfA+251.3D+284.4L+122.0H+156.6_DefInfA+514.1D+506.9L+172.3H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_152449 | 1xT1Infantry v 1xFC1T1Infantry | defender | 172 | clean |  |
| MuellerAlpaca_1v1_T1InfvFC1T6MM_AttInfA+481.0D+481.7L+112.0H+108.7_DefMMA+1049.5D+1039.3L+247.2H+150.6_Gatot_Vulcanus_20260718_164811 | 1xT1Infantry v 1xT6Marksman | defender | 6 | vulcanus_deterministic |  |
| MuellerAlpaca_1v1_T1InfvFC1T6MM_AttInfA+481.0D+481.7L+112.0H+108.7_DefMMA+176.2D+166.0L+129.1H+129.0_Gatot_NoDefenderHero_20260718_162413 | 1xT1Infantry v 1xT6Marksman | attacker | 150 | clean |  |
| MuellerAlpaca_1v1_T2InfvFC1T1Inf_AttInfA+194.1D+221.4L+122.0H+118.7_DefInfA+514.1D+506.9L+109.7H+109.3_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_154739 | 1xT2Lancer v 1xFC1T1Infantry | defender | 66 | clean |  |
| MuellerAlpaca_1v1_T2InfvFC1T1Inf_AttInfA+194.1D+221.4L+122.0H+118.7_DefInfA+514.1D+506.9L+109.7H+109.3_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_154928 | 1xT2Lancer v 1xFC1T1Infantry | defender | 79 | clean |  |
| MuellerAlpaca_1v1_T6InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+176.2D+169.0L+109.7H+109.3_NoAttackerHero_AlpacaFC1T1VulcanusNoGatot_20260718_161706 | 1xT6Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic |  |
| MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+176.2D+169.0L+109.7H+109.3_NoAttackerHero_AlpacaFC1T1Vulcanus_20260718_235302 | 1xT7Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic |  |
| MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+194.1D+172.2L+122.0H+118.7_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_151127 | 1xT7Infantry v 1xFC1T1Infantry | defender | 599 | clean |  |
| MuellerAlpaca_1v1_T7InfvFC1T1Inf_GatotAurad_AlpacaFC1T1Vulcanus_20260719_121104 | 1xT7Infantry v 1xT1Infantry | attacker | 37 | vulcanus_deterministic |  |
| MuellerAlpaca_1v1_T7InfvFC1T1Inf_Gordonlvl51_AlpacaFC1T1Vulcanus_20260719_121239 | 1xT7Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic |  |
| MuellerAlpaca_204v1_T6LanvFC1T1Inf_AttLanA+179.1D+169.2L+105.3H+102.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_AlpacaGatotAurad_20260719_004328 | 204xT6Lancer v 1xT1Infantry | defender | 1500 | clean |  |
| MuellerAlpaca_205v1_T6LanvFC1T1Inf_AttLanA+179.1D+169.2L+105.3H+102.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_AlpacaGatotAurad_20260719_004208 | 205xT6Lancer v 1xT1Infantry | attacker | 575 | clean |  |
| MuellerMiniMart_1v1_T6InfvT1Inf_NoAttackerHero_Vulcanus_20260719_121806 | 1xT6Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic |  |
| RFJPlayer_1v1_T6MMvT1Inf_Vulcanus_Gatot_20260713_002605 | 1xT6Marksman v 1xT1Infantry | attacker | 6 | vulcanus_deterministic |  |

### MuellerAlpaca_Gatot_2v2 (16 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| ColonelMuller_1v2_T1InfvT1Inf+T1MM_Gatot_Gatot+Vulcanus_20260713_112033 | 1xT1Infantry v 1xT1Infantry+1xT1Marksman | defender | 78 | vulcanus_deterministic |  |
| ColonelMuller_1v2_T1MMvFC1T1Inf+FC1T1MM_NoHeroes_Gatot+Vulcanus_20260713_111936 | 1xT1Marksman v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 3 | vulcanus_deterministic | composition_from_setup_text |
| ColonelMuller_1v2_T1MMvT1Inf+T1MM_NoHeroes_Gatot+Vulcanus_20260713_112003 | 1xT1Infantry v 1xT1Infantry+1xT1Marksman | defender | 6 | vulcanus_deterministic | attacker_naked_corrected |
| ColonelMuller_2v2_2T1MMvFC1T1Inf+FC1T1MM_NoHeroes_Gatot+Vulcanus_20260713_115521 | 2xT1Marksman v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 3 | vulcanus_deterministic | composition_from_setup_text |
| ColonelMuller_2v2_T1Inf+T1MMvT1Inf+T1MM_Gatot+NoMMHero_Gatot+Vulcanus_20260713_112159 | 1xT1Infantry+1xT1Marksman v 1xT1Infantry+1xT1Marksman | defender | None | vulcanus_deterministic |  |
| MuellerAlpaca_2v2_2T1InfvFC1T1Inf_FC1T1MM_GatotvGatot_Vulcanus_20260713_112652 | 2xT1Infantry v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 90 | vulcanus_deterministic | lh_panel_uncaptured |
| manual_ladder_n3_inf | 3xT1Infantry v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 144 | vulcanus_deterministic | manual_tier_assumed_T1,manual_no_panel_captured |
| manual_ladder_n4_inf | 4xT1Infantry v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 198 | vulcanus_deterministic | manual_tier_assumed_T1,manual_no_panel_captured |
| manual_ladder_n5_inf | 5xT1Infantry v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 252 | vulcanus_deterministic | manual_tier_assumed_T1,manual_no_panel_captured |
| manual_mixed_1_infantry_10_lancer | 1xT1Infantry+10xT1Lancer v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 47 | vulcanus_deterministic | manual_tier_assumed_T1,manual_no_panel_captured |
| manual_mixed_1_infantry_2_lancer | 1xT1Infantry+2xT1Lancer v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 36 | vulcanus_deterministic | manual_tier_assumed_T1,manual_no_panel_captured |
| manual_mixed_1_infantry_3_lancer | 1xT1Infantry+3xT1Lancer v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 37 | vulcanus_deterministic | manual_tier_assumed_T1,manual_no_panel_captured |
| manual_mixed_1_infantry_4_lancer | 1xT1Infantry+4xT1Lancer v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 39 | vulcanus_deterministic | manual_tier_assumed_T1,manual_no_panel_captured |
| manual_mixed_1_infantry_5_lancer | 1xT1Infantry+5xT1Lancer v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 40 | vulcanus_deterministic | manual_tier_assumed_T1,manual_no_panel_captured |
| manual_mixed_2_naked_infantry | 2xT1Infantry v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 8 | vulcanus_deterministic | manual_tier_assumed_T1,manual_no_panel_captured |
| manual_mixed_3_naked_marksman | 3xT1Marksman v 1xFC1T1Infantry+1xFC1T1Marksman | defender | 5 | vulcanus_deterministic | manual_tier_assumed_T1,manual_no_panel_captured |

### MuellerAlpaca_Gatot_v4 (15 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| MuellerAlpaca_v4_R01_1v1_T1LanvFC1T1Inf_AttLanA+179.1D+160.2L+105.3H+102.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_233158 | 1xT1Lancer v 1xFC1T1Infantry | defender | 37 | clean |  |
| MuellerAlpaca_v4_R02_1v1_T1LanvFC1T1Inf_AttLanA+233.4D+214.5L+105.3H+102.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_233303 | 1xT1Lancer v 1xFC1T1Infantry | defender | 44 | clean |  |
| MuellerAlpaca_v4_R03_1v1_T1LanvFC1T1Inf_AttLanA+233.4D+214.5L+105.3H+125.8_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_233326 | 1xT1Lancer v 1xFC1T1Infantry | defender | 49 | clean |  |
| MuellerAlpaca_v4_R04_1v1_T1LanvFC1T1Inf_AttLanA+233.4D+214.5L+105.3H+151.0_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_233403 | 1xT1Lancer v 1xFC1T1Infantry | defender | 55 | clean |  |
| MuellerAlpaca_v4_R05_1v1_T1MMvFC1T1Inf_AttMMA+236.3D+222.4L+121.2H+118.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_233503 | 1xT1Marksman v 1xFC1T1Infantry | defender | 40 | clean | base_mismatch |
| MuellerAlpaca_v4_R06_1v1_T1MMvFC1T1Inf_AttMMA+179.1D+165.2L+121.2H+118.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_233441 | 1xT1Marksman v 1xFC1T1Infantry | defender | 33 | clean | base_mismatch |
| MuellerAlpaca_v4_R07_1v1_T1MMvFC1T1Inf_AttMMA+236.3D+222.4L+121.2H+118.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_233503 | 1xT1Marksman v 1xFC1T1Infantry | defender | 40 | clean | base_mismatch |
| MuellerAlpaca_v4_R08_1v1_T1MMvFC1T1Inf_AttMMA+236.3D+222.4L+121.2H+122.9_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_233900 | 1xT1Marksman v 1xFC1T1Infantry | defender | 41 | clean | base_mismatch |
| MuellerAlpaca_v4_R09_1v1_T1MMvFC1T1Inf_AttMMA+236.3D+222.4L+121.2H+183.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_234044 | 1xT1Marksman v 1xFC1T1Infantry | defender | 52 | clean | base_mismatch |
| MuellerAlpaca_v4_R10_1v1_T1MMvFC1T1Inf_AttMMA+179.1D+167.7L+121.2H+118.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_234345 | 1xT1Marksman v 1xFC1T1Infantry | defender | 33 | clean | base_mismatch |
| MuellerAlpaca_v4_R11_1v1_T1LanvFC1T1Inf_AttLanA+179.1D+162.7L+105.3H+102.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_234350 | 1xT1Lancer v 1xFC1T1Infantry | defender | 37 | clean |  |
| MuellerAlpaca_v4_R12_1v1_T1LanvFC1T1Inf_AttLanA+179.1D+169.2L+105.3H+102.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_234423 | 1xT1Lancer v 1xFC1T1Infantry | defender | 38 | clean |  |
| MuellerAlpaca_v4_R13_1v1_T1MMvFC1T1Inf_AttMMA+179.1D+174.2L+121.2H+118.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_234429 | 1xT1Marksman v 1xFC1T1Infantry | defender | 34 | clean | base_mismatch |
| MuellerAlpaca_v4_R14_1v1_T1LanvFC1T1Inf_AttLanA+233.4D+223.5L+105.3H+151.0_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_234459 | 1xT1Lancer v 1xFC1T1Infantry | defender | 56 | clean |  |
| MuellerAlpaca_v4_R15_1v1_T1MMvFC1T1Inf_AttMMA+236.3D+231.4L+121.2H+118.6_DefInfA+514.1D+506.9L+109.7H+109.3_NoAttackerHero_Gatotlvl1_20260712_234502 | 1xT1Marksman v 1xFC1T1Infantry | defender | 41 | clean | base_mismatch |

### MuellerAlpaca_Gatot_v5 (9 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| MuellerAlpaca_v5_R01_1v1_T2InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012528 | 1xT2Infantry v 1xFC1T1Infantry | defender | 182 | clean |  |
| MuellerAlpaca_v5_R02_1v1_T4InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012619 | 1xT4Infantry v 1xFC1T1Infantry | defender | 332 | clean | base_mismatch |
| MuellerAlpaca_v5_R03_1v1_T5InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012641 | 1xT5Infantry v 1xFC1T1Infantry | defender | 398 | clean | base_mismatch |
| MuellerAlpaca_v5_R04_1v1_T6InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012651 | 1xT6Infantry v 1xFC1T1Infantry | defender | 469 | clean | base_mismatch |
| MuellerAlpaca_v5_R05_1v1_T3InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012912 | 1xT3Infantry v 1xFC1T1Infantry | defender | 255 | clean | base_mismatch |
| MuellerAlpaca_v5_R06_1v1_T7InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012716 | 1xT7Infantry v 1xFC1T1Infantry | defender | 554 | clean | base_mismatch |
| MuellerAlpaca_v5_R07_1v1_T8InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012721 | 1xT8Infantry v 1xFC1T1Infantry | defender | 653 | clean | base_mismatch |
| MuellerAlpaca_v5_R08_1v1_T9InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012734 | 1xT9Infantry v 1xFC1T1Infantry | defender | 771 | clean | base_mismatch |
| MuellerAlpaca_v5_R09_1v1_T10InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_Gatotlvl1_20260713_012738 | 1xT10Infantry v 1xFC1T1Infantry | defender | 909 | clean | base_mismatch |

### NanoMart (70 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| NanoMart_100_NoHero | 100xT6Infantry v 200xT6Infantry | defender | None | clean |  |
| NanoMart_100_SeoYoonlvl1 | 100xT6Infantry v 200xT6Infantry | defender | None | clean |  |
| NanoMart_100_SeoYoonlvl2 | 100xT6Infantry v 200xT6Infantry | defender | None | clean |  |
| NanoMart_100_SeoYoonlvl3 | 100xT6Infantry v 200xT6Infantry | defender | None | clean |  |
| NanoMart_100_SeoYoonlvl3_Vulcanus | 100xT6Infantry v 200xT6Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 210-210) |
| NanoMart_100_Vulcanus | 100xT6Infantry v 200xT6Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 205-207) |
| NanoMart_10v10_SeoYoonlvl3_Vulcanus | 10xT6Infantry v 10xT6Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 400-402) |
| NanoMart_1v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 264-264) |
| NanoMart_1v1_T1InfvT1Lan_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Lancer | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 79-81) |
| NanoMart_1v1_T1InfvT1MM_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Marksman | defender | None | vulcanus_deterministic | band_rederived_phase3(was 7-9) |
| NanoMart_1v1_T1InfvT6Inf_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT6Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 67-69) |
| NanoMart_1v1_T1LanvT1Lan_SeoYoonlvl3_Vulcanus | 1xT1Lancer v 1xT1Lancer | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 30-30) |
| NanoMart_1v1_T1LanvT1MM_SeoYoonlvl3_Vulcanus | 1xT1Lancer v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 79-81) |
| NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus | 1xT1Marksman v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 67-69) |
| NanoMart_1v1_T1MMvT1Lan_NoAttackerHero_Vulcanus | 1xT1Marksman v 1xT1Lancer | defender | None | vulcanus_deterministic | band_rederived_phase3(was 19-21) |
| NanoMart_1v1_T1MMvT1MM_VulcanusVsVulcanus | 1xT1Marksman v 1xT1Marksman | defender | None | vulcanus_deterministic | band_rederived_phase3(was 12-12) |
| NanoMart_1v1_T2InfvT1Inf_SeoYoonlvl3_Vulcanus | 1xT2Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 175-177) |
| NanoMart_1v1_T2InfvT2Inf_SeoYoonlvl3_Vulcanus | 1xT2Infantry v 1xT2Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 265-267) |
| NanoMart_1v1_T3InfvT1Inf_SeoYoonlvl3_Vulcanus | 1xT3Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 126-126) |
| NanoMart_1v1_T3InfvT3Inf_SeoYoonlvl3_Vulcanus | 1xT3Infantry v 1xT3Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 265-267) |
| NanoMart_1v1_T4InfvT1Inf_SeoYoonlvl3_Vulcanus | 1xT4Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 96-96) |
| NanoMart_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus | 1xT5Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 79-81) |
| NanoMart_1v1_T6InfvT1Inf_SeoYoonlvl3_Vulcanus | 1xT4Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 96-96) |
| NanoMart_1v1_T6InfvT6Inf_SeoYoonlvl3_Vulcanus | 1xT6Infantry v 1xT6Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 264-264) |
| NanoMart_1v2_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 2xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 192-192) |
| NanoMart_1v2_T1InfvT1Lan_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 2xT1Lancer | defender | None | vulcanus_deterministic | band_rederived_phase3(was 61-63) |
| NanoMart_1v2_T1LanvT1Inf_SeoYoonlvl3_Vulcanus | 1xT1Lancer v 2xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 55-57) |
| NanoMart_1v2_T1LanvT1Lan_SeoYoonlvl3_Vulcanus | 1xT1Lancer v 2xT1Lancer | defender | None | vulcanus_deterministic | band_rederived_phase3(was 19-21) |
| NanoMart_1v2_T1MMvT1MM_VulcanusVsVulcanus | 1xT1Marksman v 2xT1Marksman | defender | None | vulcanus_deterministic | band_rederived_phase3(was 7-9) |
| NanoMart_200_NoHero | 200xT6Infantry v 200xT6Infantry | attacker | None | clean |  |
| NanoMart_200_SeoYoonlvl3 | 200xT6Infantry v 200xT6Infantry | attacker | None | clean |  |
| NanoMart_200_Vulcanus | 200xT6Infantry v 200xT6Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 379-381) |
| NanoMart_250_NoHero | 250xT6Infantry v 200xT6Infantry | attacker | None | clean |  |
| NanoMart_250_SeoYoonlvl3 | 250xT6Infantry v 200xT6Infantry | attacker | None | clean |  |
| NanoMart_250_Vulcanus | 250xT6Infantry v 200xT6Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 355-357) |
| NanoMart_2v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | 2xT1Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 186-186) |
| NanoMart_2v1_T1InfvT1Lan_SeoYoonlvl3_Vulcanus | 2xT1Infantry v 1xT1Lancer | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 55-57) |
| NanoMart_2v1_T1LanvT1Inf_SeoYoonlvl3_Vulcanus | 2xT1Lancer v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 61-63) |
| NanoMart_2v1_T1LanvT1Lan_SeoYoonlvl3_Vulcanus | 2xT1Lancer v 1xT1Lancer | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 19-21) |
| NanoMart_2v1_T1LanvT1MM_SeoYoonlvl3_Vulcanus | 2xT1Lancer v 1xT1Marksman | defender | None | vulcanus_deterministic | band_rederived_phase3(was 6-6) |
| NanoMart_2v1_T1MMvT1MM_SeoYoonlvl3_Vulcanus | 2xT1Marksman v 1xT1Marksman | defender | None | vulcanus_deterministic | band_rederived_phase3(was 7-9) |
| NanoMart_300_NoHero | 300xT6Infantry v 200xT6Infantry | attacker | None | clean |  |
| NanoMart_300_SeoYoonlvl3 | 300xT6Infantry v 200xT6Infantry | attacker | None | clean |  |
| NanoMart_300_Vulcanus | 300xT6Infantry v 200xT6Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 295-297) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+10D+10H_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 244-246) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+20D+10H_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 241-243) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+20D_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 265-267) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10D+10H_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 262-264) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10A+20D_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 241-243) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10D+10H_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 268-270) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10D_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 262-264) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+10D_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 241-243) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+20D+10H_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 241-243) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+20D_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 241-243) |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10D_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 268-270) |
| NanoMart_SetA_1v1_T1InfvT1Inf_Vulcanus_SeoYoonlvl3 | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 262-264) |
| NanoMart_SetA_1v1_T3InfvT2Inf_SeoYoonlvl3_Vulcanus | 1xT3Infantry v 1xT2Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 187-189) |
| NanoMart_SetA_1v1_T4InfvT2Inf_SeoYoonlvl3_Vulcanus | 1xT4Infantry v 1xT2Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 142-144) |
| NanoMart_SetA_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus | 1xT5Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 79-81) |
| NanoMart_SetA_1v1_T5InfvT2Inf_SeoYoonlvl3_Vulcanus | 1xT5Infantry v 1xT2Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 118-120) |
| NanoMart_SetA_1v1_T6InfvT2Inf_SeoYoonlvl3_Vulcanus | 1xT6Infantry v 1xT2Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 100-102) |
| NanoMart_SetA_1v1_T6InfvT2Inf_SeoYoonlvl3_Vulcanus_Duplicate2 | 1xT6Infantry v 1xT2Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 100-102) |
| NanoMart_SetB_1v1_T1InfvT1Inf_NoAttackerHero_Vulcanus | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 268-270) |
| NanoMart_SetB_1v1_T1InfvT1Inf_Vulcanus_SeoYoonlvl3 | 1xT1Infantry v 1xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 262-264) |
| NanoMart_SetB_1v1_T1LanvT1Lan_NoAttackerHero_Vulcanus | 1xT1Lancer v 1xT1Lancer | defender | None | vulcanus_deterministic | band_rederived_phase3(was 28-30) |
| NanoMart_SetC_1v3_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 3xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 154-156) |
| NanoMart_SetC_1v5_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | 1xT1Infantry v 5xT1Infantry | defender | None | vulcanus_deterministic | band_rederived_phase3(was 118-120) |
| NanoMart_SetC_2v2_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | 2xT1Infantry v 2xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 316-318) |
| NanoMart_SetC_2v2_T1LanvT1Lan_SeoYoonlvl3_Vulcanus | 2xT1Lancer v 2xT1Lancer | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 34-36) |
| NanoMart_SetC_3v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | 3xT1Infantry v 1xT1Infantry | attacker | None | vulcanus_deterministic | band_rederived_phase3(was 151-153) |

### legacy (9 rows)

| id | matchup | winner | turns | determinism | flags |
|---|---|---|---|---|---|
| exp0_beast | 20000xTNoneInfantry v ? | defender | None | legacy_unverified |  |
| exp1_mirror_20k | ? v ? | attacker | None | legacy_unverified |  |
| exp2_mirror_2k | ? v ? | attacker | None | legacy_unverified |  |
| exp3a_lancer | 10000xTNoneLancer v 10000xTNoneMarksman | attacker | None | legacy_unverified | legacy_class_inferred |
| exp3b_lancer | ? v ? | defender | None | legacy_unverified |  |
| exp4_inf_vs_lancer | 10000xTNoneInfantry v 10000xTNoneLancer | attacker | None | legacy_unverified |  |
| exp4b_inf_vs_lancer_mueller_updated | 10000xTNoneInfantry v 10000xTNoneLancer | attacker | None | legacy_unverified |  |
| exp4c_inf_vs_lancer_gordon | 10000xTNoneInfantry v 10000xTNoneLancer | attacker | None | legacy_unverified |  |
| exp5_inf_vs_marksman | 10000xTNoneInfantry v 10000xTNoneMarksman | attacker | None | legacy_unverified |  |
