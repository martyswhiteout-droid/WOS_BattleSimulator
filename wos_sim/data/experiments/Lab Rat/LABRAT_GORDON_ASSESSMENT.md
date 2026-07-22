# Lab Rat + Gordon 1v1 battery — assessment (2026-07-12)

6 deterministic T1 1v1s ingested by GPT-5.6 via the wos-battlereport-ingestion
skill (schema v2, validator PASS; the "looks like a fraction" WARNINGs are the
known false positive — Lab Rat is a genuine 0-stat account so its panels really
do read ~2.1%/0.1%). Turn-range arithmetic re-verified by hand (all correct).

| matchup | attacker (naked) | defender (Gordon) | turns | winner |
|---|---|---|---|---|
| Inf v Inf | Inf 1.000/4.000 | Inf 1.021/4.004 | [285,287] | defender |
| Lan v Inf | Lan 4.000/2.000 | Inf 1.021/4.004 | [90,91] | defender |
| MM v Inf  | Mar 5.000/1.000 | Inf 1.021/4.004 | [72,74] | attacker |
| MM v Inf (repeat) | Mar 5.000/1.000 | Inf 1.021/4.004 | [72,74] | attacker |
| Lan v MM  | Lan 4.000/2.000 | Mar 5.105/1.001 | [24,26] | attacker |
| MM v MM   | Mar 5.105/1.001 (Gordon) | Mar 5.000/1.000 | [18,19] | attacker |

## Verdict vs Stages 1–3
- **No contradiction to Stages 1–2** (exact NanoMart arithmetic, untouched).
- **Confirms:** determinism (identical MM-v-Inf → identical [72,74]); class-clock
  order MM(~18) < Lancer(~30) < Infantry(~286); Infantry mirror stays slow.
- **Extends:** a true 0-stat baseline (isolates base-tier from panel) and a
  *different* hero regime (Gordon) → a held-out validation set against overfit.
- **Method upgrade:** Gordon's dual counter (S2 every 3 turns, S3 every 4)
  intersects to a tighter turn band than a single Vulcanus clock.

## Caveat (watch-item for backout)
Gordon's effects are **target-conditional**: he's a Lancer hero deployed on
non-Lancer sides (own-side Lancer buffs inert; only enemy-debuffs apply), and
S3's +6% Infantry-damage-taken switches off when the enemy front isn't Infantry.
Do **not** merge these into the NanoMart constraint table; keep them as a
separate Gordon-regime set with their own backout, for Stage-4 blind validation.

See `../../formula_research/STAGE4_SPEC.md` for how these + the Gatot beast
ladder feed the next derivation stage.
