# Composition / multi-troop tests — manual entry (2026-07-13, Martin)

Not yet JSON-ingested. Stored here so they're not lost. **Contains known + suspected OCR issues — see flags.**

Defender (all rows): Alpaca 1 FC1 T1 Infantry + 1 FC1 T1 Marksman, with Gatot + Vulcanus. Defender wins every row.
`turns` = how long the ATTACKER's army survives (Gatot King's Bestowal clock = per-turn).

## Buffed Gatot-Infantry count ladder (attacker = Mueller Gatot Infantry)
| N Infantry | turns | Δ from prev |
|---|---|---|
| 3 | 144 | +54 (vs JSON-backed N=2=90) |
| 4 | 198 | +54 |
| 5 | 252 | +54 |

(N=1=78 and N=2=90 are JSON-backed — `..._112033` / `MuellerAlpaca_2v2_2T1Inf...` — removed from this table so the corpus doesn't double-count.) **FLAG:** N=2→5 is clean linear (slope +54, turns = 54N − 18). But N=1→2 is only +12.
The line 54N−18 predicts N=1 = 36, not 78. So **the 1-Inf (78) or 2-Inf (90) is suspect** —
please re-verify both against their screenshots.

## Mixed & other attackers (same defender)
| attacker army | turns | note |
|---|---|---|
| 2 naked Infantry | 8 | screenshots pending JSON |
| 3 naked Marksman | 5 | screenshots pending JSON |
| 1 Infantry + 2 Lancer | 36 | Lancer-backline ladder, Martin 2026-07-14 (verbal; screenshots pending JSON ingestion). Front-death turn not re-read. |
| 1 Infantry + 3 Lancer | 37 | Lancer-backline ladder, Martin 2026-07-14 |
| 1 Infantry + 4 Lancer | 39 | Lancer-backline ladder, Martin 2026-07-14 |
| 1 Infantry + 5 Lancer | 40 | Lancer-backline ladder, Martin 2026-07-14 |
| 1 Infantry + 10 Lancer | 47 | Lancer-backline ladder, Martin 2026-07-14 |

**JSON-backed battles (removed from the table above so the corpus does NOT double-count;
retrieve them from their JSONs):** 1 Inf = 78 (`..._1v2_T1InfvT1Inf+T1MM_..._112033`); 2 Inf = 90
(`MuellerAlpaca_2v2_2T1Inf...`); 1 Inf + 1 MM = 33/35 (`..._2v2_T1Inf+T1MMv..._112159`); 1 naked
Inf = 6 (`..._112003`, class-corrected); **1 named MM = 3** (`..._111936`, ingested 2026-07-14);
**2 named MM = 3** (`..._115521`, ingested 2026-07-14 — FLAG RESOLVED: Martin screenshot-verified
both battles are genuinely 3 turns; wound split 1 injured + 1 lightly injured shows both marksmen
absorbed damage before dying together on turn 3).

**Lancer-backline ladder note (2026-07-14):** k=1 re-verified = **36** (screenshot re-checked;
JSON `ColonelMuller_2v2_T1Inf+T1LanvT1Inf+T1MM_..._004535` — NOT re-listed above to avoid a
duplicate corpus row). k=2..10 exactly match the Marksman-backline ladder (36/37/39/40/47)
despite Lancers carrying 4x the D*H HP pool — mop-up is kill-cadence-limited, not HP-limited.
Only the SINGLE-backliner case is class-dependent (MM +2 turns after the front, Lancer +3).

## Open puzzles (NOT explained — do not fit until clean data)
1. Why does `1 Inf + 1 MM` Infantry die at 33 when a lone Infantry survives 78? (The
   "frontline absorption" story is RETRACTED — it doesn't hold: same frontline, same
   incoming damage should = same death time.)
2. The MM behind the Inf: protected 33 turns, then dies in 2 (≈ its solo 3) — this part
   IS consistent.
3. Count-ladder N=1 outlier (78 vs the 36 the N≥2 line predicts).

These need **clean controlled composition experiments** before any model.
