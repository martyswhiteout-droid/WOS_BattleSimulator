# Type 1 1v1 Skill Backout And Formula Probe

Generated 2026-07-10 from NanoMart 1v1 controls with Seo-yoon L3 on attacker and Vulcanus L1 on defender.

## Battle Skill Backout

The reports are not pure base-stat reports. The active battle skills must be backed out before deriving a base casualty law.

| Skill | Level | Runtime effect used for backout |
| --- | ---: | --- |
| Seo-yoon Skill 1 | 3 | Attacker Troops Attack `+15%` |
| Vulcanus Skill 1 | 1 | Enemy Troops Attack `-4%` |
| Vulcanus Skill 2 | 1 | Defender periodic damage packet, inferred every sixth attack event |
| Vulcanus Skill 3 | 1 | Enemy Infantry/Lancer Defense `-12%` for 3 turns; cadence `1,4,7,...`, effectively continuous |

For the attacker's winning damage into the defender, the direct stat multiplier is:

`1.15 * 0.96 = 1.104`

So an observed winning-side duration can be approximately normalized to a no-battle-skill duration by:

`pure_turns ~= observed_turns * 1.104`

This is only a first-order backout of the winner's damage clock. It does not yet model Vulcanus Skill 2/3 damage into the attacker.

## Counter-Inferred Turns

| Report | Observed representative turns | Approx pure no-skill turns |
| --- | ---: | ---: |
| T1 Infantry vs T1 Infantry | 264 | 291.5 |
| T6 Infantry vs T6 Infantry | 264 | 291.5 |
| T1 Lancer vs T1 Lancer | 30 | 33.1 |
| T1 Infantry vs T1 Lancer | 80 | 88.3 |
| T2 Infantry vs T1 Infantry | 176 | 194.3 |
| T3 Infantry vs T1 Infantry | 126 | 139.1 |

## Rejected Naive Formula

The old style formula:

`damage ~ Attack * Lethality / (Defense * Health)`

does not explain the 1v1 controls.

Examples:

- T1 Infantry mirror: `1 * 1 / (4 * 6) = 0.0417`
- T6 Infantry mirror: `6 * 6 / (9 * 11) = 0.3636`

That says T6 Infantry should resolve about `8.7x` faster than T1 Infantry. The reports show the same clock, around `264` turns.

## Candidate Shape

A much better first-principles shape is:

`damage_clock ~ Attack / (Attack + target Defense) / (target Defense + target Health)`

This has useful properties:

- T1 Infantry mirror: `1/(1+4)/(4+6) = 0.0200`
- T6 Infantry mirror: `6/(6+9)/(9+11) = 0.0200`
- T1 Lancer mirror: `4/(4+2)/(2+2) = 0.1667`

It exactly explains why T1 and T6 Infantry mirrors can have the same duration while T1 Lancer mirror is much faster.

Calibrating one global clock unit from the T1 Infantry mirror with both battle skills active gives:

`clock_unit = 0.1722`

This is a unit conversion constant from displayed stat units to hidden HP-per-turn units. It is not yet a per-report fit; the test is whether it generalizes.

## Candidate Prediction Check

Using:

`turns = 1 / (clock_unit * Attack/(Attack+target Defense)/(target Defense+target Health))`

with the attacker battle skill factor `1.104` applied:

| Report | Observed turns | Candidate predicted turns | Read |
| --- | ---: | ---: | --- |
| T1 Infantry vs T1 Infantry | 264 | 264.0 | calibration point |
| T6 Infantry vs T6 Infantry | 264 | 270.6 | close |
| T1 Lancer vs T1 Lancer | 30 | 33.5 | close |
| T1 Infantry vs T1 Lancer | 80 | 64.4 | too fast |
| T2 Infantry vs T1 Infantry | 176 | 161.0 | fast by ~9% |
| T3 Infantry vs T1 Infantry | 126 | 126.7 | close |

## Current Conclusion

The new controls are enough to reject the current engine's immediate fractional-casualty model and the old `Attack * Lethality / Defense / Health` law.

They are not yet enough to certify the final formula, because:

1. All current 1v1 clock reports still include Seo-yoon and Vulcanus.
2. Lethality and Health panel bonuses are not visible in the screenshots.
3. The T1 Infantry vs T1 Lancer cross-class row is materially slower than the simple candidate predicts, implying a class/counter/targeting term still missing.

The most promising next implementation path is a hidden-HP turn engine with a damage clock close to:

`Attack / (Attack + target Defense) / (target Defense + target Health)`

plus a class/counter correction and explicit skill schedules.
