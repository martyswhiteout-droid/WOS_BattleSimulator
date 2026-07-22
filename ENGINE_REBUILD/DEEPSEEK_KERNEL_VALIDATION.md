# DeepSeek kernel validation — REJECTED as written (2026-07-11)

DeepSeek claimed: `raw = max(0, A/32 − D_def/64) + L/80; dmg = min(raw, H_def/80)`,
HP = H (ε=1), side dmg = √(live) × per-unit, counter ×1.10 after cap, SY ×1.15,
Vulc S1 ×0.96 / S3 ×0.88 — "every one of the 71 NanoMart battles matched exactly ±1 turn."

## Replay result (kernel implemented exactly as specified, ledger deployed inputs)

| battle | obs turns | pred | obs winner | pred |
|---|---|---|---|---|
| T1InfvT1Inf | 264 | 465 | A | **D** |
| T1InfvT1Lan | 80 | 78 | A | **D** |
| T1InfvT1MM | 8 | 71 | D | D |
| T1InfvT6Inf | 68 | 78 | D | D |
| T1LanvT1Inf | 8 | 80 | D | **A** |
| T1LanvT1Lan | 30 | 78 | A | **D** |
| T1LanvT1MM | 80 | 73 | D | **A** |
| T1MMvT1Inf | 68 | 73 | A | A |
| T1MMvT1Lan | 20 | 71 | D | D |
| T2InfvT1Inf | 176 | 182 | A | A |
| T2InfvT2Inf | 266 | 271 | A | **D** |
| T3InfvT1Inf | 126 | 80 | A | A |
| T3InfvT3Inf | 266 | 154 | A | **D** |
| 100v200 SY3+Vulc | 209 | 593 | D | D (surv 151 vs 148) |

**Turns within ±1: 0/14. Winners: 7/14 (coin-flip rate).** The claim does not
reproduce from the delivered spec. Script: scratchpad/validate_deepseek.py.

## Structural refutation (no constants can rescue this kernel family)

Infantry tiers are (A,D,L,H) = (n, n+3, n, n+5); observed mirrors are FLAT
264-266 for T1/T2/T3/T6, and T1 Lancer mirror is 30.

- If γ·L dominates (clamp active): dmg ∝ n, HP = n+5 → turns ∝ (n+5)/n —
  falls 3.3× from T1 to T6. Contradicts flatness.
- If α·A−β·D dominates with α=2β (DeepSeek's 1/32 vs 1/64): αA−βD ∝ (n−3) —
  grows with tier. Contradicts flatness (this is why its T3 mirror predicts 154
  while its T2 predicts 271).
- If the cap δ·H always binds: turns = H/(δH) = 1/δ — flat across tiers AND
  classes → Inf mirror = Lancer mirror. Contradicts Inf 264 vs Lan 30.

Flat infantry mirrors + fast lancer mirror require the DIFFERENCE structure
(α=β so A−D is tier-invariant, cf. the earlier derivation: dmg ∝ A_att−D_def+K,
K≈4.74 fits the whole tier ladder within ~3%) AND a class-dependent HP/L term.
DeepSeek's α=2β choice is analytically incompatible with the corpus.

## What IS worth keeping from DeepSeek's attempt

- The kernel SHAPE max(0, αA−βD)+γL with a cap is a reasonable family — but
  the data forces α=β (difference law), not α=2β.
- √N count scaling matches the exp-2 estimate (~count^0.5) qualitatively, and
  its 100v200 SURVIVOR prediction (151 vs 148 real) is close — relative
  attrition is roughly right even where the absolute clock (593 vs 209) is 3× off.
- Its PvE section honestly reports +82-131% misses — the kernel fails
  out-of-domain too.

## Asks back to DeepSeek (via Martin)

1. The actual per-battle verification table for the 71 (it offered one).
2. The actual simulator code/parameters it ran — if its sim matched, the sim
   differs from the written spec, and the WRITTEN spec is what we were given.
3. Its effective-stat construction per battle (exact A/D/L/H used per side).
