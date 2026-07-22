# Far Seer Non-Fire-Crystal Type 1 Controls

## Scope

These are the **45 complete Far Seer controls** suitable for exact-formula work. Far Seer troops in this cohort are non-Fire-Crystal. Only deterministic low-tier passives and the explicitly listed static or fixed-cadence hero effects apply.

| Source | Rows retained | Captured panel A/D/L/H % | Deployed troop tiers | Deterministic mechanics |
|---|---:|---|---|---|
| `farseer_infantry_ladder.json` | 8 | Infantry: 12.1/10.1/10.0/10.0 | T1, T2, T7 Infantry | No heroes. |
| `farseer_set3.json` | 22 | All classes: 12.1/10.1/10.0/10.0 | T6/T7 Infantry; T6 Lancer; T6 Marksman | Seo-yoon and Jassier static all-troop modifiers only. |
| `farseer_set4.json` | 7 | All classes: 12.1/10.1/10.0/10.0 | T3/T4/T5/T7 Infantry; T6 Lancer; T6 Marksman | No hero in retained Far Seer rows. |
| `farseer_set6.json` | 8 | All classes: 12.1/10.1/20.0/10.0 | T2/T7 Infantry; T6 Lancer where used | Lloyd, Bradley, and Renee fixed-cadence effects. |

## Non-FC Base Troops

The panels above are percentage modifiers. Base troop values below are `A/D/L/H` and remain non-FC for these Far Seer controls.

| Troop | T1 | T2 | T3 | T4 | T5 | T6 | T7 |
|---|---|---|---|---|---|---|---|
| Infantry | 1/4/1/6 | 2/5/2/7 | 3/6/3/8 | 4/7/4/9 | 5/8/5/10 | 6/9/6/11 | 7/10/7/12 |
| Lancer | - | - | - | - | - | 9/7/10/7 | - |
| Marksman | - | - | - | - | - | 10/6/11/6 | - |

The dash means that tier/class combination is not deployed by the 45 retained records, not that the game lacks it.

## Deterministic Skill and Passive Inputs

| Source | Hero effects exactly recorded | Passive effects relevant to the cohort |
|---|---|---|
| `farseer_infantry_ladder.json` | None | Infantry Master Brawler: +10% Damage Dealt to Lancers. Infantry Bands of Steel: +10% Defense against Lancers at T7. Neither changes the Infantry-only front-beast contact in these runs. |
| `farseer_set3.json` | Seo-yoon Rallying Beat: all Troops Attack +5% / +10% / +15% at L1/L2/L3. Jassier Tactical Genius L2: all troops Damage Dealt +10%. | Infantry Master Brawler (+10% DD vs Lancer), Lancer Charge (+10% DD vs Marksman), Marksman Ranged Strike (+10% DD vs Infantry), applied only to the valid attacking class and target group. |
| `farseer_set4.json` | None in retained Far Seer rows. | Same deterministic low-tier passives. T6 Lancer uses Charge; T6 Marksman uses Ranged Strike. |
| `farseer_set6.json` | Lloyd S1 L1: enemy Lethality -4%. Lloyd S2 L1: every 3 turns, Lancer Attack +30% and all enemy Lethality -6% for one turn. Bradley: S1 L3 +15% Attack; S3 L3 +18% Damage Dealt for two turns every four turns. Renee S1 L2: 80% extra Lancer damage every two turns; Renee S2 L2: +60% Lancer Damage Dealt to marked targets. | Same deterministic low-tier passives. No chance-based T7 Lancer or Marksman skill is in the retained cohort. |

## Beast Inputs

| Beast | Exact group composition captured | Source |
|---|---|---|
| Lv12 Musk Ox | 570 Infantry, 670 Lancer, 670 Marksman at Lv4.0 | `farseer_set3.json` |
| Lv13 Giant Tapir | 740 Infantry, 860 Lancer, 860 Marksman at Lv4.2 | `farseer_set3.json` |
| Lv10 Musk Ox | 320 Infantry, 375 Lancer, 375 Marksman at Lv3.2 | `farseer_set4.json` |
| Lv15 Giant Tapir | 1,120 Infantry, 1,310 Lancer, 1,310 Marksman at Lv5.0 | `farseer_set4.json` |

The source JSONs remain the authoritative row-by-row record: [infantry ladder](E:/WOS/Battle%20Simulator/wos_sim/data/farseer_infantry_ladder.json), [set 3](E:/WOS/Battle%20Simulator/wos_sim/data/farseer_set3.json), [set 4](E:/WOS/Battle%20Simulator/wos_sim/data/farseer_set4.json), and [set 6](E:/WOS/Battle%20Simulator/wos_sim/data/farseer_set6.json).

The one-row-per-battle flat view is [FARSEER_NONFC_EXPERIMENT_LEDGER.md](E:/WOS/Battle%20Simulator/wos_sim/data/experiments/FARSEER_NONFC_EXPERIMENT_LEDGER.md).
