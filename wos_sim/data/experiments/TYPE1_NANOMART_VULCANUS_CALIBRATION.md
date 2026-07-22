# Type 1 NanoMart Vulcanus Ladder

Generated 2026-07-09 from four farm reports:

- `wos_sim/data/experiments/NanoMart_100_Vulcanus.json`
- `wos_sim/data/experiments/NanoMart_200_Vulcanus.json`
- `wos_sim/data/experiments/NanoMart_250_Vulcanus.json`
- `wos_sim/data/experiments/NanoMart_300_Vulcanus.json`

All reports are T6 Infantry vs T6 Infantry. The defender has Vulcanus in the
Marksman hero slot, but no Marksman troops are deployed. The battle report still
shows Vulcanus skills triggering, so the engine's current slot-troop-alive gate
is too strict for hero skills.

The screenshots expose Attack/Defense rows only. The quick replay probe treated
missing Lethality/Health panel bonuses as 0%.

## Turn Inference

Vulcanus Skill 2 aligns with attacks `6, 12, 18, ...`: after five normal attacks,
the next attack is empowered. Vulcanus Skill 3 aligns with turns `1, 4, 7, ...`.

| Report | S2 triggers | S3 triggers | S2 turn range | S3 turn range | Deduced turn range |
| --- | ---: | ---: | ---: | ---: | ---: |
| NanoMart_100_Vulcanus | 34 | 69 | 204-209 | 205-207 | 205-207 |
| NanoMart_200_Vulcanus | 63 | 127 | 378-383 | 379-381 | 379-381 |
| NanoMart_250_Vulcanus | 59 | 119 | 354-359 | 355-357 | 355-357 |
| NanoMart_300_Vulcanus | 49 | 99 | 294-299 | 295-297 | 295-297 |

These are reliable windows, not single exact turn numbers.

## Per-Report Rate Needed With Live Fire

Using neutral live-fire settings (`def_k=1.0`, `fire_mode=live`,
`mod_gamma=1.0`, `q_def=1.0`, `stat_floor=0.0`, `K_skill=1.0`) and level-1
Vulcanus:

| Report | Rate needed to hit clock midpoint | Engine survivors at that rate |
| --- | ---: | --- |
| NanoMart_100_Vulcanus | 0.4065 | Defender 175.2 vs actual 156 |
| NanoMart_200_Vulcanus | 0.8348 | Defender 53.4 vs actual 46 |
| NanoMart_250_Vulcanus | 0.5318 | Attacker 139.1 vs actual 84 |
| NanoMart_300_Vulcanus | 0.4581 | Attacker 216.4 vs actual 159 |

Conclusion: no single global `rate` works across these four reports under the
current live-fire formula.

## Closest Shared Scalar Fit Found

Reduced scan over existing scalars found the closest shared fit at:

- `rate=0.35`
- `def_k=1.1`
- `fire_blend=1.0` (`fire_mode=start`)

| Report | Actual outcome | Engine outcome | Engine turns | Engine S2/S3 |
| --- | --- | --- | ---: | --- |
| NanoMart_100_Vulcanus | Defender 156 survives | Defender 157.6 survives | 200 | 33 / 67 |
| NanoMart_200_Vulcanus | Defender 46 survives | Defender 30.5 survives | 400 | 66 / 134 |
| NanoMart_250_Vulcanus | Attacker 84 survives | Attacker 60.7 survives | 378 | 63 / 126 |
| NanoMart_300_Vulcanus | Attacker 159 survives | Attacker 142.2 survives | 315 | 52 / 105 |

This is close, but it is not certification: it uses start-strength firing, which
conflicts with the current Type 1 rule that `fire_mode` should be live, and it
still misses the counters.

## No-Vulcanus Projection

Using the closest shared scalar fit above and removing Vulcanus:

| Report | No-Vulcanus engine winner | No-Vulcanus turns | Attacker survivors | Defender survivors |
| --- | --- | ---: | ---: | ---: |
| NanoMart_100_Vulcanus | Defender | 207 | 0.0 | 154.3 |
| NanoMart_200_Vulcanus | Defender | 414 | 0.0 | 17.3 |
| NanoMart_250_Vulcanus | Attacker | 363 | 74.5 | 0.0 |
| NanoMart_300_Vulcanus | Attacker | 303 | 153.5 | 0.0 |

Interpretation: in this current probe, Vulcanus has only modest impact on final
survivors. The larger signal is that the engine's troop-count scaling is wrong:
it cannot match 100/200/250/300 attacker counts with one live-fire rate.
