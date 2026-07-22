# Type 1 NanoMart 8-Point Calibration

Generated 2026-07-09 from the paired no-hero and Vulcanus farm reports:

- `NanoMart_100_NoHero.json` paired with `NanoMart_100_Vulcanus.json`
- `NanoMart_200_NoHero.json` paired with `NanoMart_200_Vulcanus.json`
- `NanoMart_250_NoHero.json` paired with `NanoMart_250_Vulcanus.json`
- `NanoMart_300_NoHero.json` paired with `NanoMart_300_Vulcanus.json`

All eight reports are deterministic T6 Infantry-vs-Infantry controls. The only
intended difference inside each pair is defender Vulcanus level-1 skills.

The screenshots expose Attack/Defense rows only. Lethality/Health were not
visible and were treated as 0% panel bonus in the quick probes below.

## Loaded Infantry Stats Check

Local engine load:

- `troop_base_stats(6, 1, Infantry) = Attack 6, Defense 9, Lethality 6, Health 11`
- `TIER_POWER[6] = 20`

Report power loss check:

| Report evidence | Implied power per T6 troop |
| --- | ---: |
| 100 troops wiped -> `-700` | 7 |
| 200 troops wiped -> `-1400` | 7 |
| 250 no-hero attacker loses 141 troops -> `-980` | 6.95 |
| 300 no-hero attacker loses 122 troops -> `-860` | 7.05 |

This means the engine's T6 combat stat row may be fine, but the local
`TIER_POWER[6] = 20` does not match battle-report power loss. Since this scalar
appears in the damage denominator, it should be audited. A global `rate` can hide
the absolute scale mismatch for same-tier fights, but it cannot prove the loaded
tier-power table is correct.

## No-Hero Ladder

Actual deterministic no-hero outcomes:

| Report | Attacker start | Defender start | Winner | Attacker survivors | Defender survivors |
| --- | ---: | ---: | --- | ---: | ---: |
| NanoMart_100_NoHero | 100 | 200 | Defender | 0 | 149 |
| NanoMart_200_NoHero | 200 | 200 | Attacker | 4 | 0 |
| NanoMart_250_NoHero | 250 | 200 | Attacker | 109 | 0 |
| NanoMart_300_NoHero | 300 | 200 | Attacker | 178 | 0 |

Live-fire (`fire_blend=0`) does not fit this ladder. With `def_k=1.0`, live fire
predicts:

| Report | Engine winner | Engine survivors |
| --- | --- | --- |
| NanoMart_100_NoHero | Defender | D 172.8 |
| NanoMart_200_NoHero | Attacker | A 12.8 |
| NanoMart_250_NoHero | Attacker | A 150.0 |
| NanoMart_300_NoHero | Attacker | A 223.4 |

Best small probe over existing scalar knobs:

- `def_k=0.96`
- `fire_blend=0.75`
- `rate=1.0` (rate does not materially affect no-hero survivor fractions)

| Report | Actual | Engine | Error |
| --- | ---: | ---: | ---: |
| NanoMart_100_NoHero defender survivors | 149 | 152.6 | +3.6 |
| NanoMart_200_NoHero attacker survivors | 4 | 9.3 | +5.3 |
| NanoMart_250_NoHero attacker survivors | 109 | 105.0 | -4.0 |
| NanoMart_300_NoHero attacker survivors | 178 | 182.1 | +4.1 |

This is close, but not exact.

At `fire_blend=0.75`, each no-hero report still wants a different exact
`def_k`:

| Report | Exact-fit `def_k` |
| --- | ---: |
| NanoMart_100_NoHero | 0.895129 |
| NanoMart_200_NoHero | 0.986178 |
| NanoMart_250_NoHero | 0.939275 |
| NanoMart_300_NoHero | 0.993216 |

Conclusion: no single defender scalar exactly reconciles the four no-hero rows.
The ladder is telling us the count-scaling / wounded-fire curve is wrong, not
that one side needs a constant handicap.

## Paired Vulcanus Check

Using the no-hero best survivor setting (`def_k=0.96`, `fire_blend=0.75`) and
choosing the rate separately to match each Vulcanus clock:

| Pair | Rate to match Vulcanus clock | Engine Vulcanus result | Actual Vulcanus result |
| --- | ---: | --- | --- |
| 100 | 0.39974 | Defender 156.2, 207 turns, S2/S3 34/69 | Defender 156, 205-207 turns |
| 200 | 0.48214 | Defender 7.2, 380 turns, S2/S3 63/127 | Defender 46, 379-381 turns |
| 250 | 0.40447 | Attacker 93.2, 356 turns, S2/S3 59/119 | Attacker 84, 355-357 turns |
| 300 | 0.39397 | Attacker 172.4, 297 turns, S2/S3 49/99 | Attacker 159, 295-297 turns |

The 100, 250, and 300 pairs are close with a rate around `0.40`. The 200-vs-200
pair is not close: the real Vulcanus swing is much larger at the knife edge.

Actual Vulcanus deltas:

| Attacker start | No-hero result | Vulcanus result | Swing |
| ---: | --- | --- | --- |
| 100 | Defender 149 | Defender 156 | +7 defender |
| 200 | Attacker 4 | Defender 46 | about 50 troops across the knife edge |
| 250 | Attacker 109 | Attacker 84 | -25 attacker |
| 300 | Attacker 178 | Attacker 159 | -19 attacker |

This is exactly where a deterministic formula must be careful: a small skill
change near a near-even battle can produce a large survivor swing. The current
engine under-produces that swing for the 200-vs-200 pair.

## Current Explanation

The eight points do not support a single arbitrary fudge factor. They point to
three concrete mechanics issues:

1. The no-hero survivor curve requires partial wounded-fire behavior. Pure live
   fire tapers too much/too little by count regime; a `fire_blend` around `0.75`
   fits the shape far better than `live`.
2. Vulcanus level-1 skills are probably not being translated with the correct
   effective impact near the 200-vs-200 knife edge. The observed no-hero-to-
   Vulcanus swing is far larger than the current runtime produces.
3. The local T6 tier-power scalar does not match report power loss (`20` local
   vs about `7` observed). This may only be a scale issue in same-tier fights,
   but it is still a data-integrity issue to audit before claiming exact
   calibration.

The right next step is not a new fudge. It is to derive the no-hero attrition
curve from these four points first, then layer Vulcanus level-1 skills on top and
check whether the observed pairwise deltas fall out naturally.
