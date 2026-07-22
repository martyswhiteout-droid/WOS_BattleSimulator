# MuellerAlpaca consolidated table (2026-07-12)

Attacker = Colonel Mueller (Gatot L1, exact turn clock) at tier T{n}; Defender = Alpaca **FC1 T1** (no hero).
Effective stat = REAL base (docs/TroopStats/WOS_Troop_Stats...) x (1+panel). **L/H captured on both sides.**
Defender wins every row (Mueller dies); turns = King's Bestowal count.

| attT | AttA | AttD | AttL | AttH | DefA | DefD | DefL | DefH | turns | pred=12.54*Dm*Hm/(Aa*La) | err |
|--|--|--|--|--|--|--|--|--|--|--|--|
| T1 | 2.94 | 10.89 | 2.22 | 13.12 | 6.14 | 24.28 | 2.15 | 12.85 | 132 | 136 | +3% |
| T1 | 3.51 | 13.18 | 2.22 | 15.40 | 6.14 | 24.28 | 2.15 | 12.85 | 187 | 193 | +3% |
| T1 | 3.51 | 13.18 | 2.26 | 13.42 | 6.14 | 24.28 | 2.15 | 12.85 | 163 | 168 | +3% |
| T1 | 3.51 | 14.74 | 2.22 | 13.12 | 6.14 | 24.28 | 2.15 | 12.85 | 178 | 184 | +3% |
| T1 | 3.51 | 14.74 | 2.22 | 13.12 | 6.14 | 24.28 | 2.72 | 12.85 | 141 | 145 | +3% |
| T1 | 3.51 | 15.31 | 2.22 | 13.12 | 6.14 | 24.28 | 2.72 | 12.85 | 146 | 151 | +3% |
| T1 | 3.51 | 15.38 | 2.22 | 13.12 | 6.14 | 24.28 | 2.72 | 12.85 | 147 | 151 | +3% |
| T1 | 3.51 | 15.38 | 2.22 | 15.40 | 6.14 | 24.28 | 2.10 | 12.56 | 223 | 231 | +3% |
| T1 | 3.51 | 15.38 | 2.22 | 15.40 | 6.14 | 24.28 | 2.10 | 12.56 | 232 | 231 | -1% |
| T1 | 3.51 | 15.38 | 2.22 | 15.40 | 6.14 | 24.28 | 2.10 | 12.56 | 232 | 231 | -1% |
| T1 | 3.51 | 15.38 | 2.22 | 15.40 | 6.14 | 24.28 | 2.10 | 12.56 | 237 | 231 | -3% |
| T1 | 3.51 | 15.38 | 2.22 | 15.40 | 6.14 | 24.28 | 2.72 | 12.85 | 172 | 178 | +3% |
| T2 | 5.88 | 16.07 | 4.44 | 15.31 | 6.14 | 24.28 | 2.10 | 12.56 | 66 | 240 | +263% |
| T2 | 5.88 | 16.07 | 4.44 | 15.31 | 6.14 | 24.28 | 2.10 | 12.56 | 79 | 240 | +203% |
| T7 | 23.53 | 29.94 | 15.54 | 28.43 | 6.14 | 24.28 | 2.15 | 12.85 | 599 | 809 | +35% |

## Findings

1. **T1-v-FC1T1 (12 rows, both T1, REAL captured L/H): A*L/(D*H) confirmed to within +3%/-3%.**
   turns = 12.54 * D_loser * H_loser / (A_winner * L_winner) fits with the SAME C=12.54
   from the Lab Rat Gatot rows. The L/H were previously assumed; now they are read
   from the report and the form still holds. This is the strongest within-tier
   confirmation yet (two-sided battle, developed defender, different account).

2. **T2/T7 (cross-tier) FAIL badly** (+203%, +263%, +35%). Consistent with the tier
   correction below.

## The tier correction (supersedes the 2026-07-12 "multiplicative base" claim)

The real base-stat table shows Infantry base A ~= tier and L = tier, so A*L ~ tier^2
(T3 A*L = 9x T1, T6 = 42x T1). Then A*L/(D*H) predicts tier MIRRORS should collapse
300 -> 36 turns (T1->T6) -- but they are observed FLAT (~264-266). So A*L/(D*H) does
NOT govern the tier dimension. The earlier "base scales x1.20/tier" was CIRCULAR (it
inverted the formula to fit, then claimed to confirm it). With the real stats it is
falsified.

**New lead:** with real stats, (A - D) = -3 for every Infantry tier (A grows in step
with D), and (L - H) ~ -5/-6. The DIFFERENCE is tier-invariant -> that is why mirrors
are flat. So the real law is local-ratio (A*L/(D*H) within a tier / panel space) but
global-difference across tiers. Reconciling the two is the open Stage-4 problem, now
tractable because the REAL base-stat table is available.

