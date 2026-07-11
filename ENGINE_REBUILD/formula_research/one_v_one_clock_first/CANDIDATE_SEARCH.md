# Candidate Formula Search

This is a numerical search over shared formula families. It is not proof of the game's internal formula.

- Seed: 20260711
- Differential-evolution iterations per candidate: 35
- Population multiplier: 6
- Exact duplicate captures: zero additional fitting weight
- Objective: 2x winner mismatch + 1x normalized survivor error + 8x normalized out-of-range turn error

| Rank | Family | Vulcanus S2 cadence | Objective | Winners | Turns | Survivors | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | affine | 5 | 0.17275092 | 31/37 | 1/37 | 31/37 | REJECTED |
| 2 | affine | 6 | 0.18071348 | 31/37 | 2/37 | 31/37 | REJECTED |
| 3 | power_law | 6 | 0.18607354 | 30/37 | 2/37 | 30/37 | REJECTED |
| 4 | power_law | 5 | 0.19407901 | 29/37 | 2/37 | 29/37 | REJECTED |

## Best Candidate

```json
{
  "name": "candidate_affine_c5",
  "family": "affine",
  "kernel": {
    "log_scale": -4.7284768911454105,
    "defense_weight": 0.061332307497225846,
    "lethality_weight": 0.3487789158280472,
    "positive_floor": 2.012572638801534,
    "target_health_exponent": 0.2892479582823084
  },
  "mechanics": {
    "hp_exponent": 0.6178570475796235,
    "frontage_exponent": 0.9532639944092113,
    "vulcanus_s2_cadence": 5,
    "vulcanus_s2_multiplier": 1.2,
    "minimum_hp_fraction": 0.003706410438651775
  },
  "max_turns": 500
}
```
