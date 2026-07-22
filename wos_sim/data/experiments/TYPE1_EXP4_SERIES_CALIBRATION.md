# Type 1 exp4 Series Calibration Note

Generated 2026-07-09 from:

- `wos_sim/data/experiments/exp4_inf_vs_lancer.json`
- `wos_sim/data/experiments/exp4b_inf_vs_lancer_mueller_updated.json`
- `wos_sim/data/experiments/exp4c_inf_vs_lancer_gordon.json`

All three reports are deterministic Type 1 PvP controls: 10,000 T6 Infantry
attacking 10,000 T6 Lancers. `exp4c` includes Gordon, but the relevant observed
effect is deterministic: Gordon Skill 2 level 2 applies enemy Damage Dealt
`-12%` for 1 turn on turns `3, 6, 9, ...`.

## Clock Constraint

`exp4c` reports Gordon Skill 2 triggered 31 times and Skill 3 triggered 23
times. With Martin's schedule:

- Skill 2 on turns `3, 6, 9, ...` -> 31 triggers means final turn is at least 93
  and less than 96.
- Skill 3 every 4 turns -> 23 triggers means final turn is at least 92 and less
  than 96.
- Intersection: `93-95` turns.

With neutral mechanics and `rate=1.0`, the engine gives exp4c 122 turns and 40
Gordon Skill 2 triggers. Therefore `rate` is a clock scalar and must be listed
with the calibration/fudge knobs until it is derived from real mechanics.

## Replay Settings Used

Neutral Type 1 settings:

- `fire_mode="live"`
- `mod_gamma=1.0`
- `q_def=1.0`
- `stat_floor=0.0`
- `K_skill=1.0`
- `def_ed=1.0`
- `cm=1.1` unchanged, treated as the real built-in troop counter

Scenario-local Gordon override for exp4c:

- Skill 2 level 2, enemy Damage Dealt `-12%`
- duration `1` turn
- frequency `3` turns
- start turn `3`

## Best Shared Two-Knob Fit Found

Using `rate=1.30` and `def_k=0.99`:

| Report | Actual attacker survivors | Engine attacker survivors | Error | Engine turns | Gordon S2 triggers |
| --- | ---: | ---: | ---: | ---: | ---: |
| exp4 | 4,536 | 4,591.8 | +55.8 | 90 | 0 |
| exp4b | 4,282 | 4,221.6 | -60.4 | 97 | 0 |
| exp4c | 4,533 | 4,545.6 | +12.6 | 93 | 31 |

This is close, but not an exact Type 1 fit.

## Why A Shared Fudge Is Not Enough

At the Gordon-valid clock setting `rate=1.30`, each report can be made exact
only with a different `def_k`:

| Report | `def_k` required for exact survivor count | Engine turns | Gordon S2 triggers |
| --- | ---: | ---: | ---: |
| exp4 | 0.996481 | 91 | 0 |
| exp4b | 0.983708 | 96 | 0 |
| exp4c | 0.991450 | 93 | 31 |

Conclusion: there is no single shared `def_k` that completely reconciles exp4,
exp4b, and exp4c under the current formula. The residual is small, but the fact
that exp4 and exp4b require different defender-output scalars means the formula
is still responding slightly incorrectly to the defender stat change, not merely
using the wrong global rate.

## Current Interpretation

- `rate` is a fudge/calibration scalar today. It controls battle clock and should
  be kept explicit until derived from a physical/stat mechanic.
- `def_k` remains a fudge scalar if used to fix Type 1. These three reports show
  it cannot be the final answer because no shared value fits all three exactly.
- The next mechanical suspect is the stat-response curve for Attack/Lethality vs
  Defense/Health in same-class controlled PvP, not a new report-specific scalar.
