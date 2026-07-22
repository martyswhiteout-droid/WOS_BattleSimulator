# NanoMart vs MiniMart Count Scaling Exp 2

Generated 2026-07-10 from `E:/WOS/WOS_BattleReports_NanoMart_Exp_2.pdf`.

All fixtures were saved under:

`E:/WOS/Battle Simulator/wos_sim/data/experiments/`

## Saved Fixtures

| File | Turns | Result |
| --- | ---: | --- |
| `NanoMart_1v2_T1InfvT1Inf_SeoYoonlvl3_Vulcanus.json` | 192 | A loses |
| `NanoMart_1v2_T1LanvT1Lan_SeoYoonlvl3_Vulcanus.json` | 20 | A loses |
| `NanoMart_1v2_T1MMvT1MM_VulcanusVsVulcanus.json` | 8 | A loses |
| `NanoMart_1v2_T1LanvT1Inf_SeoYoonlvl3_Vulcanus.json` | 56 | A loses |
| `NanoMart_1v2_T1InfvT1Lan_SeoYoonlvl3_Vulcanus.json` | 62 | A loses |
| `NanoMart_2v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus.json` | 186 | A wins |
| `NanoMart_2v1_T1LanvT1Lan_SeoYoonlvl3_Vulcanus.json` | 20 | A wins |
| `NanoMart_2v1_T1MMvT1MM_SeoYoonlvl3_Vulcanus.json` | 8 | A loses |
| `NanoMart_2v1_T1InfvT1Lan_SeoYoonlvl3_Vulcanus.json` | 56 | A wins |
| `NanoMart_2v1_T1LanvT1Inf_SeoYoonlvl3_Vulcanus.json` | 62 | A wins |
| `NanoMart_2v1_T1LanvT1MM_SeoYoonlvl3_Vulcanus.json` | 6 | A loses |

## Key Count-Scaling Signal

Same-class mirror rows:

| Mirror | 1v1 turns | 1v2 turns | 2v1 turns | Read |
| --- | ---: | ---: | ---: | --- |
| T1 Infantry | 264 | 192 | 186 | 2 troops are not 2x output; about sqrt-like scaling |
| T1 Lancer | 30 | 20 | 20 | same sublinear count scaling, faster class clock |
| T1 Marksman | contaminated | 8 | 8 | not clean; hero/stat distortion dominates |

Approximate count exponent from mirror rows:

- Infantry, 2v1: `log(264/186)/log(2) = 0.51`
- Infantry, 1v2: `log(264/192)/log(2) = 0.46`
- Lancer, 2v1 or 1v2: `log(30/20)/log(2) = 0.58`

This points to a count term around:

`effective_firepower ~ troop_count ^ 0.5`

not:

`effective_firepower ~ troop_count`

## Formula Status

The deterministic formula is not fully solved yet, but the shape is much clearer:

1. Damage is accumulated against hidden HP; it is not immediate fractional troop removal.
2. Same-class same-tier mirrors use a hidden class clock:
   - Infantry is slow, around `264` turns for 1v1.
   - Lancer is fast, around `30` turns for 1v1.
   - Marksman rows are currently contaminated by hero-stat asymmetry.
3. Troop count scales sublinearly, roughly with exponent `0.5-0.6`.
4. Tier seems normalized in same-class mirrors: T1/T2/T3/T6 Infantry mirrors all sit around `264-266` turns.
5. Cross-class rows require a class/counter term; they cannot be explained by scalar tier power alone.

Cross-class rows also need the deterministic T1 troop passives applied before
inferring any unknown formula term:

| Source class | Target class | Passive | Formula effect |
| --- | --- | --- | --- |
| Infantry | Lancer | Master Brawler | `Damage Dealt x1.10` |
| Lancer | Marksman | Charge | `Damage Dealt x1.10` |
| Marksman | Infantry | Ranged Strike | `Damage Dealt x1.10` |

The passive belongs to the attacking class for that attack packet and is keyed
to the defender's class. It is not symmetric across a matchup.

Working structural candidate:

`damage_per_turn = class_clock(attacker_class, defender_class) * count_attacker^alpha * stat_term`

where:

- `alpha` is probably near `0.5`.
- `stat_term` must use base troop stats multiplied by the visible/scouted panel stats.
- Lethality and Health must be in the final formula, but the current screenshots do not expose their percentage rows.

## Important Data Warnings

- Marksman rows are not clean formula anchors because Vulcanus greatly inflates Marksman stats on the defender, and sometimes on the attacker.
- The screenshots show Attack/Defense rows but not Lethality/Health rows, so JSON files record base Lethality/Health and mark panel bonuses as missing.
- Skill backout is still required:
  - Seo-yoon L3: attacker Troops Attack `+15%`.
  - Vulcanus L1 Skill 1: enemy Troops Attack `-4%`.
  - Vulcanus Skill 2/3 also affect runtime damage/defense windows and are not merely counters.
