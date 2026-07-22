# Type 1 NanoMart Seo-yoon Ladder

Generated 2026-07-09 from:

- `NanoMart_100_SeoYoonlvl1.json`
- `NanoMart_100_SeoYoonlvl2.json`
- `NanoMart_100_SeoYoonlvl3.json`
- `NanoMart_100_SeoYoonlvl3_Vulcanus.json`

All reports are deterministic T6 Infantry-vs-Infantry controls.

The only deployed troop class is Infantry. Seo-yoon is in the Marksman hero slot,
so her visible Marksman hero stat rows do not matter for the casualty math here.
The relevant mechanic is Seo-yoon Skill 1:

- Level 1: Troops Attack `+5%`
- Level 2: Troops Attack `+10%`
- Level 3: Troops Attack `+15%`

## OCR Outcomes

| Report | Attacker setup | Defender setup | Winner | Attacker survivors | Defender survivors | Skill counters |
| --- | --- | --- | --- | ---: | ---: | --- |
| NanoMart_100_NoHero | none | none | Defender | 0 | 149 | none |
| NanoMart_100_SeoYoonlvl1 | Seo-yoon L1 | none | Defender | 0 | 147 | Seo-yoon 1 |
| NanoMart_100_SeoYoonlvl2 | Seo-yoon L2 | none | Defender | 0 | 144 | Seo-yoon 1 |
| NanoMart_100_SeoYoonlvl3 | Seo-yoon L3 | none | Defender | 0 | 141 | Seo-yoon 1 |
| NanoMart_100_SeoYoonlvl3_Vulcanus | Seo-yoon L3 | Vulcanus L1 | Defender | 0 | 148 | Seo-yoon 1; Vulcanus S1/S2/S3 = 1/35/70 |

Vulcanus counters imply exactly turn `210`:

- S2: `35` triggers, with attack schedule `6, 12, 18, ...` -> turns `210-215`
- S3: `70` triggers, with turn schedule `1, 4, 7, ...` -> turns `208-210`
- Intersection: `210`

## Seo-yoon Correlation

Use the no-hero 100-vs-200 report as the base:

- NoHero defender casualties = `200 - 149 = 51`

If Seo-yoon simply multiplies attacker damage by `1 + Attack bonus`, predicted
defender survivors are:

| Skill level | Attack bonus | Formula | Predicted defender survivors | Actual |
| --- | ---: | --- | ---: | ---: |
| L1 | 5% | `200 - 51 * 1.05` | 146.45 | 147 |
| L2 | 10% | `200 - 51 * 1.10` | 143.90 | 144 |
| L3 | 15% | `200 - 51 * 1.15` | 141.35 | 141 |

This is an excellent fit. Seo-yoon's skill appears to be a plain multiplicative
Attack/damage-output modifier, at least in this controlled setup.

## Seo-yoon L3 For 200/250/300

Use each no-hero report's casualty exchange ratio:

`exchange_ratio = defender casualties / attacker casualties`

Then apply Seo-yoon L3:

`exchange_ratio_with_seoyoon = exchange_ratio * 1.15`

For attacker-win rows, attacker casualties to wipe defender become:

`attacker casualties = defender_start / exchange_ratio_with_seoyoon`

Initial diagnostic predictions:

| Predicted report | No-hero exchange ratio | Predicted winner | Predicted attacker survivors | Predicted defender survivors |
| --- | ---: | --- | ---: | ---: |
| NanoMart_200_SeoYoonlvl3 | `200 / 196 = 1.0204` | Attacker | ~30 | 0 |
| NanoMart_250_SeoYoonlvl3 | `200 / 141 = 1.4184` | Attacker | ~127 | 0 |
| NanoMart_300_SeoYoonlvl3 | `200 / 122 = 1.6393` | Attacker | ~194 | 0 |

Actual follow-up reports:

| Report | Actual winner | Actual attacker survivors | Initial diagnostic prediction | Error |
| --- | --- | ---: | ---: | ---: |
| NanoMart_200_SeoYoonlvl3 | Attacker | 52 | ~30 | -22 |
| NanoMart_250_SeoYoonlvl3 | Attacker | 131 | ~127 | -4 |
| NanoMart_300_SeoYoonlvl3 | Attacker | 196 | ~194 | -2 |

The current turn engine with the closest no-hero scalar setting predicts a
similar but slightly higher set:

| Predicted report | Turn-engine prediction |
| --- | --- |
| NanoMart_200_SeoYoonlvl3 | Attacker ~37 survivors |
| NanoMart_250_SeoYoonlvl3 | Attacker ~126 survivors |
| NanoMart_300_SeoYoonlvl3 | Attacker ~198 survivors |

The 250/300 rows agree with the simple exchange-ratio approximation, but the
200-vs-200 row does not. This is a near-even knife-edge row: the real battle
amplifies the +15% Attack bonus more than a single static exchange-ratio
shortcut predicts.

## What This Says About The Missing Mechanic

This does not look like a random/proc problem. It also does not look like
Seo-yoon's skill is mistranslated.

The key signal is that the no-hero and Seo-yoon rows do not behave like pure
live Lanchester tapering. The 100/250/300 rows are well approximated by a
starting-strength casualty exchange view, but the 200-vs-200 row proves the
shortcut is incomplete near the win/loss boundary. A pure linear fudge cannot fix
that across 100/200/250/300.

The missing mechanic is probably one of:

1. Wounded/lightly-injured troops continue contributing for most or all of the
   combat resolution.
2. Casualties are accumulated from a fixed-start-strength exchange and only
   assigned to injured/lightly injured/survivors after the battle.
3. The turn counter is real for skills, but the casualty engine is not reducing
   firepower every turn as aggressively as our current live model does.

Mathematically, the needed correction is not a flat linear scalar. It is a
nonlinear count-scaling/casualty-exchange curve. It may look parabolic in a small
range, but the structure suggested by the data is closer to a reciprocal exchange
formula:

`winner survivors ~= start - enemy_start / effective_exchange_ratio`

where `effective_exchange_ratio` already includes troop count ratio, stat edge,
and battle Attack modifiers like Seo-yoon.
