# deepseek_repaired_hp Evaluation

Status: **REJECTED**

- Reports: 70
- Winner matches: 54/70
- Survivor matches: 42/70
- Turn matches: 1/60

## Claimed Equation Checks

| Control | Claimed damage | Linear expression | Kernel after floor/cap | Matches? |
|---|---:|---:|---:|---|
| T1 Infantry mirror | 0.022727 | -0.007241 | 0.012500 | no |
| T1 Lancer mirror | 0.066667 | 0.176036 | 0.025000 | no |
| T1 Lancer +20% L vs Infantry | 0.083333 | 0.161036 | 0.075000 | no |
| T6 Infantry mirror | 0.041667 | 0.162804 | 0.137500 | no |
| T4 Infantry vs T1 Infantry | 0.062500 | 0.136036 | 0.075000 | no |

## Per-Report Residuals

| Report | Winner obs/pred | Turns obs/pred | Survivors A obs/pred | Survivors D obs/pred |
|---|---|---|---:|---:|
| NanoMart_100_NoHero | defender/defender | NC/675 | 0/0 | 149/149 |
| NanoMart_100_SeoYoonlvl1 | defender/defender | NC/680 | 0/0 | 147/145 |
| NanoMart_100_SeoYoonlvl2 | defender/defender | NC/681 | 0/0 | 144/144 |
| NanoMart_100_SeoYoonlvl3 | defender/defender | NC/681 | 0/0 | 141/144 |
| NanoMart_100_SeoYoonlvl3_Vulcanus | defender/defender | 210-210/593 | 0/0 | 148/151 |
| NanoMart_100_Vulcanus | defender/defender | 205-207/585 | 0/0 | 156/159 |
| NanoMart_1v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker/defender | 264/465 | 1/0 | 0/1 |
| NanoMart_1v1_T1InfvT1Lan_SeoYoonlvl3_Vulcanus | attacker/defender | 80/78 | 1/0 | 0/1 |
| NanoMart_1v1_T1InfvT1MM_SeoYoonlvl3_Vulcanus | defender/defender | 8/71 | 0/0 | 1/1 |
| NanoMart_1v1_T1InfvT6Inf_SeoYoonlvl3_Vulcanus | defender/defender | 68/78 | 0/0 | 1/1 |
| NanoMart_1v1_T1LanvT1Lan_SeoYoonlvl3_Vulcanus | attacker/defender | 30/78 | 1/0 | 0/1 |
| NanoMart_1v1_T1LanvT1MM_SeoYoonlvl3_Vulcanus | defender/attacker | 80/73 | 0/1 | 1/0 |
| NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus | attacker/attacker | 68/73 | 1/1 | 0/0 |
| NanoMart_1v1_T1MMvT1Lan_NoAttackerHero_Vulcanus | defender/defender | 20/71 | 0/0 | 1/1 |
| NanoMart_1v1_T1MMvT1MM_VulcanusVsVulcanus | defender/mutual_wipe | 12/78 | 0/0 | 1/0 |
| NanoMart_1v1_T2InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 176/182 | 1/1 | 0/0 |
| NanoMart_1v1_T2InfvT2Inf_SeoYoonlvl3_Vulcanus | attacker/defender | 266/271 | 1/0 | 0/1 |
| NanoMart_1v1_T3InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 126/80 | 1/1 | 0/0 |
| NanoMart_1v1_T3InfvT3Inf_SeoYoonlvl3_Vulcanus | attacker/defender | 266/154 | 1/0 | 0/1 |
| NanoMart_1v1_T4InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 96/80 | 1/1 | 0/0 |
| NanoMart_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 80/80 | 1/1 | 0/0 |
| NanoMart_1v1_T6InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 96/80 | 1/1 | 0/0 |
| NanoMart_1v1_T6InfvT6Inf_SeoYoonlvl3_Vulcanus | attacker/defender | 264/78 | 1/0 | 0/1 |
| NanoMart_1v2_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | defender/defender | 192/329 | 0/0 | 2/2 |
| NanoMart_1v2_T1InfvT1Lan_SeoYoonlvl3_Vulcanus | defender/defender | 62/55 | 0/0 | 2/2 |
| NanoMart_1v2_T1LanvT1Inf_SeoYoonlvl3_Vulcanus | defender/defender | 56/75 | 0/0 | 2/2 |
| NanoMart_1v2_T1LanvT1Lan_SeoYoonlvl3_Vulcanus | defender/defender | 20/55 | 0/0 | 2/2 |
| NanoMart_1v2_T1MMvT1MM_VulcanusVsVulcanus | defender/defender | 8/55 | 0/0 | 2/2 |
| NanoMart_200_NoHero | attacker/attacker | NC/2167 | 4/6 | 0/0 |
| NanoMart_200_SeoYoonlvl3 | attacker/attacker | NC/1632 | 52/40 | 0/0 |
| NanoMart_200_Vulcanus | defender/defender | 379-381/1466 | 0/0 | 46/61 |
| NanoMart_250_NoHero | attacker/attacker | NC/1371 | 109/109 | 0/0 |
| NanoMart_250_SeoYoonlvl3 | attacker/attacker | NC/1221 | 131/124 | 0/0 |
| NanoMart_250_Vulcanus | attacker/attacker | 355-357/1610 | 84/68 | 0/0 |
| NanoMart_2v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 186/340 | 2/2 | 0/0 |
| NanoMart_2v1_T1InfvT1Lan_SeoYoonlvl3_Vulcanus | attacker/attacker | 56/78 | 2/1 | 0/0 |
| NanoMart_2v1_T1LanvT1Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 62/57 | 2/2 | 0/0 |
| NanoMart_2v1_T1LanvT1Lan_SeoYoonlvl3_Vulcanus | attacker/attacker | 20/57 | 2/2 | 0/0 |
| NanoMart_2v1_T1LanvT1MM_SeoYoonlvl3_Vulcanus | defender/attacker | 6/52 | 0/2 | 1/0 |
| NanoMart_2v1_T1MMvT1MM_SeoYoonlvl3_Vulcanus | defender/attacker | 8/57 | 0/2 | 1/0 |
| NanoMart_300_NoHero | attacker/attacker | NC/1163 | 178/178 | 0/0 |
| NanoMart_300_SeoYoonlvl3 | attacker/attacker | NC/1049 | 196/190 | 0/0 |
| NanoMart_300_Vulcanus | attacker/attacker | 295-297/1296 | 159/148 | 0/0 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+10D+10H_SeoYoonlvl3_Vulcanus | defender/defender | 246/423 | 0/0 | 1/1 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+20D+10H_SeoYoonlvl3_Vulcanus | defender/defender | 242/465 | 0/0 | 1/1 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+20D_SeoYoonlvl3_Vulcanus | attacker/attacker | 266/437 | 1/1 | 0/0 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10D+10H_SeoYoonlvl3_Vulcanus | attacker/defender | 264/465 | 1/0 | 0/1 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10A+20D_SeoYoonlvl3_Vulcanus | defender/attacker | 242/437 | 0/1 | 1/0 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10D+10H_SeoYoonlvl3_Vulcanus | defender/defender | 270/465 | 0/0 | 1/1 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10D_SeoYoonlvl3_Vulcanus | attacker/attacker | 264/437 | 1/1 | 0/0 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+10D_SeoYoonlvl3_Vulcanus | defender/defender | 242/465 | 0/0 | 1/1 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+20D+10H_SeoYoonlvl3_Vulcanus | defender/defender | 242/465 | 0/0 | 1/1 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+20D_SeoYoonlvl3_Vulcanus | defender/defender | 242/465 | 0/0 | 1/1 |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10D_SeoYoonlvl3_Vulcanus | defender/defender | 270/465 | 0/0 | 1/1 |
| NanoMart_Exp4_1v1_T1LanvT1Inf_Att+20_SeoYoonlvl3_Vulcanus | attacker/attacker | 72/80 | 1/1 | 0/0 |
| NanoMart_SetA_1v1_T1InfvT1Inf_Vulcanus_SeoYoonlvl3 | defender/attacker | 264/465 | 0/1 | 1/0 |
| NanoMart_SetA_1v1_T3InfvT2Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 188/108 | 1/1 | 0/0 |
| NanoMart_SetA_1v1_T4InfvT2Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 144/80 | 1/1 | 0/0 |
| NanoMart_SetA_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 68/80 | 1/1 | 0/0 |
| NanoMart_SetA_1v1_T5InfvT2Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 120/80 | 1/1 | 0/0 |
| NanoMart_SetA_1v1_T6InfvT2Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 102/80 | 1/1 | 0/0 |
| NanoMart_SetA_1v1_T6InfvT2Inf_SeoYoonlvl3_Vulcanus_Duplicate2 | attacker/attacker | 102/80 | 1/1 | 0/0 |
| NanoMart_SetB_1v1_T1InfvT1Inf_NoAttackerHero_Vulcanus | defender/defender | 270/465 | 0/0 | 1/1 |
| NanoMart_SetB_1v1_T1InfvT1Inf_Vulcanus_SeoYoonlvl3 | defender/attacker | 264/465 | 0/1 | 1/0 |
| NanoMart_SetB_1v1_T1LanvT1Lan_NoAttackerHero_Vulcanus | defender/defender | 30/78 | 0/0 | 1/1 |
| NanoMart_SetC_1v3_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | defender/defender | 156/269 | 0/0 | 3/3 |
| NanoMart_SetC_1v5_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | defender/defender | 120/208 | 0/0 | 5/5 |
| NanoMart_SetC_2v2_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker/defender | 318/787 | 1/0 | 0/1 |
| NanoMart_SetC_2v2_T1LanvT1Lan_SeoYoonlvl3_Vulcanus | attacker/defender | 36/132 | 1/0 | 0/1 |
| NanoMart_SetC_3v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | attacker/attacker | 152/278 | 3/3 | 0/0 |
