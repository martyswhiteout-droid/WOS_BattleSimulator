# Drop the raw stat-panel screenshots here (owner task — gates plan Task 12)

Save the ORIGINAL screenshots (PNG preferred, no messenger recompression if avoidable) with these names:

| File | What it is |
|---|---|
| `A_citystats_1.png`, `A_citystats_2.png` | Main account ([RFJ]Marty 191): Bonus Overview, both scroll positions |
| `A_scout.png` | Main account: own-city scout "Stat Bonuses" panel |
| `A_battle.png` | Main account: battle-report "Stat Bonuses" (two-column) |
| `A_specials.png` | Main account: "Notes on Special Bonuses" panel |
| `B_citystats_1.png`, `B_citystats_2.png` | [LnS]MaTiX: Bonus Overview, both scroll positions |
| `B_scout.png` | [LnS]MaTiX: scout "Stat Bonuses" panel |
| `B_battle.png` | [LnS]MaTiX: battle-report "Stat Bonuses" |
| `B_specials.png` | [LnS]MaTiX: "Notes on Special Bonuses" panel |

Extra device/quality variants are welcome (suffix `_alt1` etc.) — they widen the benchmark corpus (`docs/OCR_QA_PLAN.md` §2).

The expected VALUES for every one of these images are already fixed in `../golden_vectors.json` (plan Task 0) — the Task-12 benchmark reads an image, runs the engine, and compares against those numbers. Pass bar: ≥99% digit accuracy, zero false-confident fields.
