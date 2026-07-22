# Alpaca and Colonel Mueller FC1 Report Status

## Status: Incomplete, Not an Exact-Fit Pool

These 12 reports are deterministic by design and repeatability evidence, but they are **not** in the exact-formula fitting pool. Their JSON files do not preserve the A/D/L/H stat panels, and Colonel Mueller's Fire Crystal level is not recorded.

Alpaca (`沃草泥的马`) is FC1, per Martin's correction. The FC1 base values below are taken directly from [WOS_Troop_Stats_FC1-FC10_T1-T10.json](E:/WOS/Battle%20Simulator/docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json).

| Alpaca troop | FC1 base A/D/L/H | FC troop skills at FC1 |
|---|---|---|
| T10 Apex Infantry | 11/14/10/16 | None. FC Infantry skills begin at FC3. |
| T6 Heroic Marksman | 11/7/12/7 | None. FC Marksman skills begin at FC3. |

The deterministic base passives still matter: Infantry Master Brawler is +10% Damage Dealt to Lancers and is inactive in these Infantry/Marksman-only ladders. Marksman Ranged Strike is +10% Damage Dealt to Infantry and is active whenever either side's Marksmen attack the opposing Infantry.

| Source | Rows | Alpaca deployed force | Colonel Mueller deployed force | Deterministic evidence | Why incomplete |
|---|---:|---|---|---|---|
| `pvp_ladder_v9.json` | 3 | 50/50 T10 Infantry + T6 Marksman; totals 4k, 6k, 10k | 50/50 T7 Infantry + T6 Marksman; totals 3k, 6k, 10k | Explicit no-proc design; three 6k-vs-6k repeats are identical. Bradley S3 counters are 3/4/4. | Neither side's A/D/L/H panel is stored; Colonel's FC level is unknown. |
| `pvp_ladder_v9b.json` | 4 | Fixed 5,000 T10 Infantry + 5,000 T6 Marksman | Equal T7 Infantry + T6 Marksman; totals 3k, 6k, 10k, 16k | Source declares no-proc deterministic design. | Same missing panels and Colonel FC status. |
| `pvp_ladder_v9c.json` | 5 | Equal T10 Infantry + T6 Marksman; totals 3k, 6k, 10k, 16k, 20k | Fixed 3,000 T7 Infantry + 3,000 T6 Marksman | Source declares no-proc deterministic design. | Same missing panels and Colonel FC status. |

Do not substitute standard T10 base values for Alpaca. For any replay of these reports, use the FC1 values above and supply the missing scouted A/D/L/H panels and Colonel's FC level first.
