# Candidate Formula Search

This is a numerical search over shared formula families. It is not proof of the game's internal formula.

- Seed: 20260711
- Differential-evolution iterations per candidate: 25
- Population multiplier: 6
- Exact duplicate captures: zero additional fitting weight
- Objective: 4x winner mismatch + 2x normalized survivor error + 2x normalized out-of-range turn error

| Rank | Family | Vulcanus S2 cadence | Objective | Winners | Turns | Survivors | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | power_law | 5 | 0.12337037 | 35/37 | 0/37 | 35/37 | REJECTED |
| 2 | affine | 5 | 0.12967539 | 34/37 | 1/37 | 34/37 | REJECTED |
| 3 | power_law | 6 | 0.13782137 | 35/37 | 1/37 | 35/37 | REJECTED |
| 4 | affine | 6 | 0.16872965 | 31/37 | 0/37 | 31/37 | REJECTED |

## Best Candidate

```json
{
  "name": "candidate_power_law_c5",
  "family": "power_law",
  "kernel": {
    "log_scale": -4.171021239994624,
    "attack_exponent": 0.6982453750372779,
    "defense_exponent": 0.16277392751074826,
    "lethality_exponent": 0.39003345532353717,
    "target_health_exponent": 0.35476386527479464
  },
  "mechanics": {
    "hp_exponent": 0.5216875056987722,
    "frontage_exponent": 0.532951949160861,
    "vulcanus_s2_cadence": 5,
    "vulcanus_s2_multiplier": 1.2,
    "minimum_hp_fraction": 0.001039274168888358
  },
  "max_turns": 500
}
```
