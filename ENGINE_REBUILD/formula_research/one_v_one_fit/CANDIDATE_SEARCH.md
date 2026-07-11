# Candidate Formula Search

This is a numerical search over shared formula families. It is not proof of the game's internal formula.

- Seed: 20260711
- Differential-evolution iterations per candidate: 45
- Population multiplier: 8
- Exact duplicate captures: zero additional fitting weight
- Objective: 4x winner mismatch + 2x normalized survivor error + 2x normalized out-of-range turn error

| Rank | Family | Vulcanus S2 cadence | Objective | Winners | Turns | Survivors | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | power_law | 6 | 0.08563633 | 36/37 | 2/37 | 36/37 | REJECTED |
| 2 | affine | 5 | 0.08920689 | 36/37 | 1/37 | 36/37 | REJECTED |
| 3 | affine | 6 | 0.08946896 | 36/37 | 2/37 | 36/37 | REJECTED |
| 4 | power_law | 5 | 0.10586429 | 35/37 | 1/37 | 35/37 | REJECTED |

## Best Candidate

```json
{
  "name": "candidate_power_law_c6",
  "family": "power_law",
  "kernel": {
    "log_scale": -4.245656028933467,
    "attack_exponent": 0.5874341822734364,
    "defense_exponent": 0.15964274051288374,
    "lethality_exponent": 0.20002847252594913,
    "target_health_exponent": 0.03164448296058442
  },
  "mechanics": {
    "hp_exponent": 0.5390054686866467,
    "frontage_exponent": 0.5127341879811218,
    "vulcanus_s2_cadence": 6,
    "vulcanus_s2_multiplier": 1.2
  },
  "max_turns": 500
}
```
