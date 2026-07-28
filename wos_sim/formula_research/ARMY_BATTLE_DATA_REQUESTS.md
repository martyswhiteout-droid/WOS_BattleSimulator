# Army-scale battle data — inventory and what's needed (2026-07-25)

Every deterministic army-scale battle on file, what it contains, and the exact gap.
Source dir: `wos_sim/data/experiments/`. "Panels" = the Stat Bonuses screen (both sides),
the load-bearing capture. Sorted by priority of the ask.

## A. MISSING ENTIRELY — no file exists (highest value)

| # | Battle | Known outcome | Where it's recorded | WHAT I NEED |
|---|---|---|---|---|
| **A1** | **20k MIXED composition**: (5k Infantry + 15k Lancer) **vs** (5k Infantry + 15k Marksman) | **Marksman DEFENDER won, 8,302 survivors = 41.5%** | Only as prose inside `exp3a_lancer.json`'s `NEEDS_CONFIRMATION` — the file that **overwrote** it | **Full report screenshots**: Battle Overview (both sides' troop counts per class), **Stat Bonuses panel for BOTH sides** (all 12 rows each), casualties per class, turn count if shown. This is the single most valuable missing anchor — the only multi-class army battle. |
| **A2** | **Alliance-garrison Infantry mirror**, attacker +10pt | **attacker 30.2% survivors** | Summary line only in `ENGINE_REBUILD/07_CONTROLLED_EXPERIMENTS.md` | **Full report screenshots** — same list as A1. Gives a *second* same-class blind test of the solved law (different stat gap from exp1). |

## B. ON FILE BUT INCOMPLETE

| # | File | Timestamp | Attacker | Defender | Attacker comp | Defender comp | Tier | Observed | Has panels? | WHAT I NEED |
|---|---|---|---|---|---|---|---|---|---|---|
| **B1** | `exp3b_lancer.json` | — | *not recorded* | *not recorded* | 20,000 (class not recorded) | 20,000 (class not recorded) | — | **defender won, 4,963 = 24.8%** | **NO** | **Everything**: which classes each side deployed, player names, **both Stat Bonuses panels**, casualties per class. ⚠️ It says "same as 3a (repeat)" but records the **opposite winner** — please confirm whether this is (a) a genuine repeat of the Lancer-v-Marksman battle, or (b) actually the **A1 mixed battle** mislabelled. |
| **B2** | `exp3a_lancer.json` | — (report clock 23:23:25) | *not recorded* | *not recorded* | 10,000 **Lancer** *(INFERRED)* | 10,000 **Marksman** *(INFERRED)* | Lv 6.0 | attacker won, 4,205 = 42% | **YES** (under `stats_pct_LEFT_side` / `_RIGHT_side`) | **Confirm which side deployed Lancer vs Marksman** (I currently assume attacker=left=Lancer — this flips the whole test's sign). Also: player names, timestamp, and casualty breakdown (injured / lightly injured) for both sides. |
| **B3** | `exp0_beast.json` | 2026-07-08 21:37:45 | `[RTS]Colonel Müller` | Lv.18 Titan Roc (beast) | 20,000 Infantry, Lv 1.0 | 8,645 beast troops in 3 × Lv 6.0 units | Lv 1.0 vs 6.0 | **attacker defeat**, 0 survivors; beast kept 7,176 | attacker only | Beast side has **no stat panel and no per-unit breakdown** (notes say "flat +57.0%"). Low priority — beasts aren't a troop class pair. Only if easy. |

## C. COMPLETE — no action needed (used in the analysis)

| # | File | Timestamp | Attacker | Defender | Attacker comp | Defender comp | Tier | Observed |
|---|---|---|---|---|---|---|---|---|
| C1 | `exp1_mirror_20k.json` | 2026-07-08 21:43:41 | 沃草泥的馬 (X:766 Y:484) | Colonel Müller (X:767 Y:486) | 20,000 Infantry | 20,000 Infantry | Lv 1.0 | attacker **24.185%** (4,837); defender 0 — ran ×3 identical |
| C2 | `exp2_mirror_2k.json` | 2026-07-08 21:52:11 | 沃草泥的馬 | Colonel Müller | 2,000 Infantry | 2,000 Infantry | Lv 1.0 | attacker **24.2%** (484); defender 0 |
| C3 | `exp4_inf_vs_lancer.json` | — | *not recorded* | *not recorded* | 10,000 Infantry | 10,000 Lancer | Lv 6.0 | attacker **45.36%** (4,536) |
| C4 | `exp4b_..._mueller_updated.json` | — | `[Rfj] ...` (truncated) | `[Rfj] Colonel Muller` | 10,000 Infantry | 10,000 Lancer | Lv 6.0 | attacker **42.82%** (4,282) |
| C5 | `exp4c_..._gordon.json` | — | `[Rfj] ...` | `[Rfj] Colonel Muller` | 10,000 Infantry (+Gordon) | 10,000 Lancer | Lv 6.0 | attacker **45.33%** (4,533) |
| C6 | `exp5_inf_vs_marksman.json` | — | *not recorded* | *not recorded* | 10,000 Infantry | 10,000 Marksman | Lv 6.0 | attacker **4.88%** (488) — barely |

Nice-to-have on C3–C6 (not blocking): player names/timestamps, and the **defender's**
injured / lightly-injured split (only exp4b/4c have it).

## D. Also on file — real PvP at full scale (Type-2, procs)
`wos_sim/data/reports/report_001..008.json` — real battles at ~1.7 M troops, multi-class,
full stats (e.g. report_001 `[ACE]MaTi5678x` 1,721,972 troops, defeat). These are the
golden-anchor set. **Nothing needed** — they contain procs, so they validate by
distribution only, not exact fit.

## E. Repo bug for me to fix (no action from you)
`wos_sim/backtest.py` `COMPOSITION_ANCHORS` "mirror (inf v inf)" builds the mirror from
**exp4's** panels (Inf 199.2/192.0/119.7/119.3) but targets **24.0%**, which came from
**exp1's** mirror (panels 176.2/169.0/109.7/109.3) — two different battles. The anchor
needs re-pairing to exp1's real stats.

---

## Summary of the ask, shortest form
1. **A1** — the mixed 20k battle (5k Inf+15k Lan vs 5k Inf+15k MM, MM defender won 41.5%): full screenshots. ★ top value
2. **B1** — `exp3b`: what battle was it really? Full screenshots, or confirm it's A1.
3. **B2** — `exp3a`: **which side was Lancer, which was Marksman?** (one-line answer unblocks it)
4. **A2** — the alliance-garrison mirror (+10pt → 30.2%): full screenshots.

For any of these, screenshots or the PDF page are fine — I can OCR the panels myself; I
don't need you to transcribe numbers.
