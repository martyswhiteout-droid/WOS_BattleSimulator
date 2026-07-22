# Type 1 Incomplete and Excluded Records

These records are intentionally outside the 52-report exact-fit pool.

| Cohort | Rows | Status | Reason |
|---|---:|---|---|
| `exp3a_lancer.json` | 1 | Incomplete | It declares no skills/procs, but both A/D/L/H panels are absent and the Lancer/Marksman side assignment is inferred. |
| `exp3b_lancer.json` | 1 | Incomplete | The old battle was overwritten; class and numeric inputs are absent. |
| `farseer_set5.json` | 5 Far Seer rows | Incomplete | Full A/D/L/H panel is not stored in the JSON. |
| `farseer_set7.json` | 5 | Incomplete | Only the +20% Lethality state is explicit; Attack, Defense, and Health panel values are absent. |
| `farseer_set8.json` | 4 | Incomplete | Only the continuing +20% Lethality state is explicit; full A/D/L/H panel values are absent. |
| Alpaca / Colonel Mueller ladders | 12 | Incomplete | See `TYPE1_ALPACA_MUELLER_FC1_INCOMPLETE.md`: panels and Colonel FC level are missing. |
| `FS4-M1`, `FS4-M2` Marlinman rows | 2 | Excluded | Later source evidence establishes a Fire Crystal proc-capable path on Marlinman. They are not pure deterministic controls. |

No record in this file should be used to derive or tune an exact deterministic combat formula until its missing inputs are recovered and any chance path is ruled out for the actual account state.
