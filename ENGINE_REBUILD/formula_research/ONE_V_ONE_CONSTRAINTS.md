# One-Unit Constraint Audit

- Unique 1v1 clocks: 37
- Modeled-input conflicts: 1
- The per-turn quotient below assumes unit HP equals effective Health only as a diagnostic normalization.

## Input Conflicts

### input_conflict_1

- `NanoMart_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus`: attacker, survivors 1/0, turns 79-81
- `NanoMart_SetA_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus`: attacker, survivors 1/0, turns 67-69

These rows have identical modeled inputs but disjoint turn ranges. No deterministic formula using only the captured inputs can match both clocks.

## Constraints

| Report | Matchup | Effective A/D/L/H (attacker) | Effective A/D/L/H (defender) | Winner | Turns | Loser H / midpoint | Conflict |
|---|---|---|---|---|---:|---:|---|
| NanoMart_1v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.128288/3.527040/1.000000/6.000000 | 1.020000/4.000000/1.000000/6.000000 | attacker | 264-264 | 0.02272727 |  |
| NanoMart_1v1_T1InfvT1Lan_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Lancer | 1.128288/3.527040/1.000000/6.000000 | 4.080000/2.000000/5.000000/2.000000 | attacker | 79-81 | 0.02500000 |  |
| NanoMart_1v1_T1InfvT1MM_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Marksman | 1.128288/3.527040/1.000000/6.000000 | 30.860000/6.152000/5.000000/1.000000 | defender | 7-9 | 0.75000000 |  |
| NanoMart_1v1_T1InfvT6Inf_SeoYoonlvl3_Vulcanus | T1 Infantry vs T6 Infantry | 1.128288/3.527040/1.000000/6.000000 | 6.120000/9.000000/6.000000/11.000000 | defender | 67-69 | 0.08823529 |  |
| NanoMart_1v1_T1LanvT1Lan_SeoYoonlvl3_Vulcanus | T1 Lancer vs T1 Lancer | 4.513152/1.763520/5.000000/2.000000 | 4.080000/2.000000/5.000000/2.000000 | attacker | 30-30 | 0.06666667 |  |
| NanoMart_1v1_T1LanvT1MM_SeoYoonlvl3_Vulcanus | T1 Lancer vs T1 Marksman | 4.513152/1.763520/5.000000/2.000000 | 30.860000/6.152000/5.000000/1.000000 | defender | 79-81 | 0.02500000 |  |
| NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus | T1 Marksman vs T1 Infantry | 4.905600/1.002000/5.000000/1.000000 | 1.020000/4.000000/1.000000/6.000000 | attacker | 67-69 | 0.08823529 |  |
| NanoMart_1v1_T1MMvT1Lan_NoAttackerHero_Vulcanus | T1 Marksman vs T1 Lancer | 4.905600/1.002000/5.000000/1.000000 | 4.080000/2.000000/5.000000/2.000000 | defender | 19-21 | 0.05000000 |  |
| NanoMart_1v1_T1MMvT1MM_VulcanusVsVulcanus | T1 Marksman vs T1 Marksman | 20.932800/4.341000/5.000000/1.000000 | 29.625600/6.152000/5.000000/1.000000 | defender | 12-12 | 0.08333333 |  |
| NanoMart_1v1_T2InfvT1Inf_SeoYoonlvl3_Vulcanus | T2 Infantry vs T1 Infantry | 2.256576/4.408800/2.000000/7.000000 | 1.020000/4.000000/1.000000/6.000000 | attacker | 175-177 | 0.03409091 |  |
| NanoMart_1v1_T2InfvT2Inf_SeoYoonlvl3_Vulcanus | T2 Infantry vs T2 Infantry | 2.256576/4.408800/2.000000/7.000000 | 2.040000/5.000000/2.000000/7.000000 | attacker | 265-267 | 0.02631579 |  |
| NanoMart_1v1_T3InfvT1Inf_SeoYoonlvl3_Vulcanus | T3 Infantry vs T1 Infantry | 3.384864/5.290560/3.000000/8.000000 | 1.020000/4.000000/1.000000/6.000000 | attacker | 126-126 | 0.04761905 |  |
| NanoMart_1v1_T3InfvT3Inf_SeoYoonlvl3_Vulcanus | T3 Infantry vs T3 Infantry | 3.384864/5.290560/3.000000/8.000000 | 3.060000/6.000000/3.000000/8.000000 | attacker | 265-267 | 0.03007519 |  |
| NanoMart_1v1_T4InfvT1Inf_SeoYoonlvl3_Vulcanus | T4 Infantry vs T1 Infantry | 4.513152/6.172320/4.000000/9.000000 | 1.020000/4.000000/1.000000/6.000000 | attacker | 96-96 | 0.06250000 |  |
| NanoMart_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus | T5 Infantry vs T1 Infantry | 5.641440/7.054080/5.000000/10.000000 | 1.020000/4.000000/1.000000/6.000000 | attacker | 79-81 | 0.07500000 | input_conflict_1 |
| NanoMart_1v1_T6InfvT1Inf_SeoYoonlvl3_Vulcanus | T6 Infantry vs T1 Infantry | 6.769728/7.935840/6.000000/11.000000 | 1.020000/4.000000/1.000000/6.000000 | attacker | 96-96 | 0.06250000 |  |
| NanoMart_1v1_T6InfvT6Inf_SeoYoonlvl3_Vulcanus | T6 Infantry vs T6 Infantry | 6.769728/7.935840/6.000000/11.000000 | 6.120000/9.000000/6.000000/11.000000 | attacker | 264-264 | 0.04166667 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+10D+10H_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.240896/3.527040/1.100000/6.000000 | 1.020000/4.400000/1.100000/6.600000 | defender | 244-246 | 0.02448980 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+20D+10H_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.240896/3.527040/1.100000/6.000000 | 1.134000/4.900000/1.000000/6.600000 | defender | 241-243 | 0.02479339 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+20D_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.253040/3.924800/1.100000/6.000000 | 1.134000/4.900000/1.000000/6.000000 | attacker | 265-267 | 0.02255639 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10D+10H_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.240896/3.527040/1.100000/6.000000 | 1.020000/4.400000/1.000000/6.600000 | attacker | 262-264 | 0.02509506 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10A+20D_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.128288/3.527040/1.100000/6.000000 | 1.134000/4.900000/1.000000/6.000000 | defender | 241-243 | 0.02479339 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10D+10H_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.128288/3.527040/1.100000/6.000000 | 1.020000/4.400000/1.000000/6.600000 | defender | 268-270 | 0.02230483 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10L_Def+10D_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.128288/3.527040/1.100000/6.000000 | 1.020000/4.400000/1.000000/6.000000 | attacker | 262-264 | 0.02281369 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+10D_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.128288/3.527040/1.000000/6.000000 | 1.134000/4.456000/1.000000/6.000000 | defender | 241-243 | 0.02479339 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+20D+10H_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.128288/3.527040/1.000000/6.000000 | 1.134000/4.900000/1.000000/6.606000 | defender | 241-243 | 0.02479339 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10A+20D_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.128288/3.527040/1.000000/6.000000 | 1.134000/4.900000/1.000000/6.000000 | defender | 241-243 | 0.02479339 |  |
| NanoMart_Exp4_1v1_T1InfvT1Inf_Def+10D_SeoYoonlvl3_Vulcanus | T1 Infantry vs T1 Infantry | 1.128288/3.527040/1.000000/6.000000 | 1.020000/4.400000/1.000000/6.000000 | defender | 268-270 | 0.02230483 |  |
| NanoMart_Exp4_1v1_T1LanvT1Inf_Att+20_SeoYoonlvl3_Vulcanus | T1 Lancer vs T1 Infantry | 4.513152/1.763520/6.000000/2.000000 | 1.020000/4.000000/1.000000/6.000000 | attacker | 70-72 | 0.08450704 |  |
| NanoMart_SetA_1v1_T1InfvT1Inf_Vulcanus_SeoYoonlvl3 | T1 Infantry vs T1 Infantry | 1.020000/4.000000/1.000000/6.000000 | 1.128288/3.527040/1.000000/6.000000 | defender | 262-264 | 0.02281369 |  |
| NanoMart_SetA_1v1_T3InfvT2Inf_SeoYoonlvl3_Vulcanus | T3 Infantry vs T2 Infantry | 3.384864/5.290560/3.000000/8.000000 | 2.040000/5.000000/2.000000/7.000000 | attacker | 187-189 | 0.03723404 |  |
| NanoMart_SetA_1v1_T4InfvT2Inf_SeoYoonlvl3_Vulcanus | T4 Infantry vs T2 Infantry | 4.513152/6.172320/4.000000/9.000000 | 2.040000/5.000000/2.000000/7.000000 | attacker | 142-144 | 0.04895105 |  |
| NanoMart_SetA_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus | T5 Infantry vs T1 Infantry | 5.641440/7.054080/5.000000/10.000000 | 1.020000/4.000000/1.000000/6.000000 | attacker | 67-69 | 0.08823529 | input_conflict_1 |
| NanoMart_SetA_1v1_T5InfvT2Inf_SeoYoonlvl3_Vulcanus | T5 Infantry vs T2 Infantry | 5.641440/7.054080/5.000000/10.000000 | 2.040000/5.000000/2.000000/7.000000 | attacker | 118-120 | 0.05882353 |  |
| NanoMart_SetA_1v1_T6InfvT2Inf_SeoYoonlvl3_Vulcanus | T6 Infantry vs T2 Infantry | 6.769728/7.935840/6.000000/11.000000 | 2.040000/5.000000/2.000000/7.000000 | attacker | 100-102 | 0.06930693 |  |
| NanoMart_SetB_1v1_T1InfvT1Inf_NoAttackerHero_Vulcanus | T1 Infantry vs T1 Infantry | 0.981120/3.527040/1.000000/6.000000 | 1.020000/4.000000/1.000000/6.000000 | defender | 268-270 | 0.02230483 |  |
| NanoMart_SetB_1v1_T1LanvT1Lan_NoAttackerHero_Vulcanus | T1 Lancer vs T1 Lancer | 3.924480/1.763520/5.000000/2.000000 | 4.080000/2.000000/5.000000/2.000000 | defender | 28-30 | 0.06896552 |  |
