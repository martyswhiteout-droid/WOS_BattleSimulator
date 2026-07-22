# NanoMart 10v10 Seo-yoon L3 vs Vulcanus L1

Captured from Martin screenshot, 2026-07-10.

Source image:

`C:/Users/Martin/AppData/Local/Temp/codex-clipboard-12b40908-de9d-47e5-9a14-d412f2562668.png`

## Battle Overview

| Field | Attacker | Defender |
| --- | --- | --- |
| Player | nanomart | minimart |
| Coordinates | X:556 Y:25 | X:556 Y:27 |
| Result | Victory | Defeat |
| Troop type | T6 Infantry | T6 Infantry |
| Troops | 10 | 10 |
| Power loss | -80 | -80 |
| Losses | 0 | 0 |
| Injured | 4 | 4 |
| Lightly injured | 5 | 6 |
| Survivors | 1 | 0 |

## Visible Stats

Only Attack and Defense are visible in the screenshot.

| Stat | Attacker | Defender |
| --- | ---: | ---: |
| Infantry Attack | +2.2% | +2.0% |
| Infantry Defense | +0.2% | +0.0% |
| Lancer Attack | +2.2% | +2.0% |
| Lancer Defense | +0.2% | +0.0% |
| Marksman Attack | +46.7% | +517.2% |
| Marksman Defense | +44.7% | +515.2% |

The only deployed troop class is Infantry, so the visible Marksman stat gap should not directly affect base troop exchange unless the engine/game applies lead-hero stats more broadly than expected.

## Skill Counters

| Hero | Skill | Triggered | Kills |
| --- | --- | ---: | --- |
| Seo-yoon | Skill 1 | 1 | - |
| Vulcanus | Skill 1 | 1 | - |
| Vulcanus | Skill 2 | 67 | - |
| Vulcanus | Skill 3 | 134 | - |

Assumption from prior controlled probes:

- Vulcanus Skill 3 is a turn-cadence skill on turns `1, 4, 7, ...`.
- Therefore `134` triggers implies battle turn count in the range `400-402`.
- If Vulcanus Skill 2 is interpreted as an empowered hit every sixth attack event, `67` triggers implies roughly `402+` attack events.

This is far longer than any model where one 10-troop stack must lose at least one whole troop per turn.

## Mechanics Implication

This report is a strong counterexample to a whole-troop-per-turn casualty model.

With 10 Infantry vs 10 Infantry, a battle lasting around 400 turns means at least one of the following is true:

1. The game tracks fractional damage or hit points below the troop-count level.
2. A troop can remain active across many turns while accumulating damage.
3. Incapacitation is delayed until accumulated damage crosses a health threshold.
4. The battle report's injured/lightly injured/survivor buckets are produced after hidden HP depletion, not by removing whole troops each turn.

The current turn engine does not track persistent per-unit HP. It tracks a stack count `n` and subtracts fractional/whole incapacitated count directly from `n` when damage packets are applied. That can produce fractional casualties, but it does not preserve per-troop health across turns.

This should become a calibration/mechanics gate for the deterministic Type 1 ladder. Any proposed deterministic formula must be able to explain:

- `10v10` battle duration near `400` turns,
- final result `1` attacker survivor vs `0` defender survivors,
- no skill-kill rows despite Vulcanus counters,
- continuity with the existing `100/200/250/300` NanoMart NoHero, Seo-yoon, and Vulcanus controls.
