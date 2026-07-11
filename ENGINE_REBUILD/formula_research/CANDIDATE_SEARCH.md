# Candidate Formula Search

This is a numerical search over shared formula families. It is not proof of the game's internal formula.

- Seed: 20260711
- Differential-evolution iterations per candidate: 35
- Population multiplier: 8
- Exact duplicate captures: zero additional fitting weight
- Objective: 4x winner mismatch + 2x normalized survivor error + 2x normalized out-of-range turn error

| Rank | Family | Vulcanus S2 cadence | Objective | Winners | Turns | Survivors | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | power_law | 6 | 0.07450694 | 69/70 | 6/60 | 54/70 | REJECTED |
| 2 | affine | 6 | 0.07712321 | 69/70 | 1/60 | 53/70 | REJECTED |
| 3 | affine | 5 | 0.08342543 | 68/70 | 1/60 | 53/70 | REJECTED |
| 4 | power_law | 5 | 0.08574747 | 68/70 | 4/60 | 51/70 | REJECTED |

## Best Candidate

```json
{
  "name": "candidate_power_law_c6",
  "family": "power_law",
  "kernel": {
    "log_scale": -4.345889083046355,
    "attack_exponent": 0.6800275505205483,
    "defense_exponent": 0.22928258989105887,
    "lethality_exponent": 0.20815231339617601,
    "target_health_exponent": 0.0830458361220856
  },
  "mechanics": {
    "hp_exponent": 0.5000497927702362,
    "frontage_exponent": 0.9196122261406497,
    "vulcanus_s2_cadence": 6,
    "vulcanus_s2_multiplier": 1.2
  },
  "max_turns": 1000
}
```
