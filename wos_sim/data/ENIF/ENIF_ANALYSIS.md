# E-NIF battery — analysis record (2026-07-17, evaluator window)

10 battles, all Gordon/Gatot-clocked, all Type-1. Re-runnable: `enif_analysis.py`.
Panels: Martin's OCR corrections of 2026-07-17 are applied IN the files (alliance-
buffed vs unbuffed Mueller loadouts per run; Alpaca MM H+129.0; Mueller MM H+118.6,
R01 128.6).

## E-NIF1b — VERDICT (final, alliance-corrected 2026-07-17)

The R01/R04-vs-R02 winner flip was the **RFJ alliance buff** (Martin-confirmed;
panels now corrected per run: in-alliance = +23pp A/D, +10pp L/H on Mueller).
Determinism fully restored — alliance membership is a real stat variable that
must be captured per battle.

| run | Mueller | winner | turns | K_eff | vs reference |
|---|---|---|---|---|---|
| R01 | in RFJ | Mueller Inf | [69,71] | 77.1 (Inf→MM) | v4 73.1, **+5%** |
| R04 | in RFJ | Mueller Inf | [69,71] | 77.1 | exact replicate ✓ |
| R02 | outside | **Alpaca MM** | [66,67] | **90.1 (MM→Inf)** | naked 93, **−3%** |
| R03 | in RFJ, 1v2 | MM side | [52,53] | 62.7 raw → **88.7**/unit (√2) | naked 93, −5% |

**VERDICT: the MM→Infantry ~4.7× suppression is a GATOT-KIT effect.** Against a
GORDON Infantry the Marksman dealer sits at K = 88.7–90.1 ≈ the naked-derived 93
(±5%); against the GATOT Infantry it was 440. Gatot's kit protects his Infantry
~4.7× beyond the naive 6%-shield estimate (~12%) — quantifying his kit is now a
scoped Stage-6 item, and any battle whose DYING side carries Gatot must be
modelled with it.

**Two-sided race validation (first winner-flip prediction of the K-table):**
- in-alliance: MM needs 77.8t to kill Mueller; Mueller needs 66.4t → **Mueller wins** (obs [69,71] ✓)
- out-of-alliance: MM needs 68.6t; Mueller needs 75.3t → **MM wins** (obs [66,67] ✓)
The K-table called both sides of a knife-edge battle correctly — including the
flip caused by a 12% stat change.

Minor cosmetic note: R03/R04 carry in-alliance A/D/L on Mueller's MM row but
H=118.6 (out-of-alliance value; expected 128.6 by the +10 pattern). Mueller's MM
does not fight in those battles — no calculation impact.

## E-NIF2 — ran off-design; yielded the MM LOSER-tier curve instead

The +176.2% MM loadout cannot beat the +481% Gatot Infantry, so the MM **lost**
all three battles → the intended MM-dealer tier curve was NOT measured. What WAS
measured (winner = Mueller Gatot Inf, fixed; loser = FC1 MM at rising tier):

| loser | turns | K·G_l | ⇒ G_l^MM(τ) (K=73.1) |
|---|---|---|---|
| FC1 T1 MM | 38 | 76.8 | **1.051** (replicates the Inf→MM cell again, +5%) |
| FC1 T3 MM | 81 | 18.2 | **0.249** |
| FC1 T6 MM | 150 | 6.2 | **0.085** |

New result: the **Marksman loser-tier curve is far steeper than Infantry's**
(Inf G_l: 1.0/0.904/0.749 at T1/T3/T6). Equivalently: MM effective HP grows far
slower than D·H across tiers. Shape is robust to the H-panel fill (same panel all
rungs). **Redo needed for the original goal:** same ladder with the **+1072%
loadout** (which beats the Gatot Inf) → the true MM-dealer tier curve.

## E-NIF3 — clean success: Lancer dealer confirmed + class-dependent tier damping

| dealer | turns | K_eff | G^Lan(τ) |
|---|---|---|---|
| FC1 T1 Lancer | [21,23] | **488.7** | 1.000 |
| FC1 T3 Lancer | [9,11] | 533.1 | **1.091** |
| FC1 T6 Lancer | [6,7] | 794.2 | **1.625** |

- **K(Lan→MM) = 489 at full panels vs naked-derived 500 (−2%): Lancer panels
  multiply in full; the K-cell is confirmed at strength.** (Third class where
  panels enter linearly: Inf proven, Lan proven, MM proven vs MM-targets.)
- **Tier damping is CLASS-DEPENDENT:** G^Lan = 1 / 1.09 / 1.63 vs Infantry's
  G_w = 1 / 4.32 / 10.89 (and vs cube-root-of-growth 1.79/3.12). The cube-root
  structure is an INFANTRY property, not universal. G_w^MM is still unmeasured
  (needs the E-NIF2 redo).
- Caveat: these dealers are FC1 troops; the Infantry G_w ladder used ordinary
  troops. The ordinary-vs-FC1 base question (troop_catalog vs docs table, the
  `base_mismatch` flag) is still open and now materially matters.

## Consolidated status of the K-table (measured cells, full-panel confirmed)

| dealer\target | Infantry | Lancer | Marksman |
|---|---|---|---|
| Infantry | 12.5 | 22.4 | 73.1 (×4 independent: v4, 1b-R01/R04, NIF2-T1) |
| Lancer | (factorization ~85) | (~152) | **500 → 489 CONFIRMED** |
| Marksman | 93 naked; **88.7–90.1 vs Gordon-Inf (alliance-corrected)**; 440 vs GATOT-Inf (kit effect) | (~170) | 567 (confirmed at +1072% panels, 07-14) |

## E-NIF2 redo (R11/R12, 2026-07-17) — the last curve, and the Gatot-kit shape

Alpaca MM + Vulcanus (NoAlliance panels 1049.5/1039.3/247.2/150.6 = the 07-13
loadout minus exactly the +23/+10 alliance uplift — independent confirmation of
the alliance-buff pattern) vs the same Gatot-Mueller Inf (D·H = 291.4, constant):

| dealer | turns | K_eff | K/93 |
|---|---|---|---|
| T1 MM (07-13 battle) | 102 | 439.9 | 4.73× |
| **T3 MM (R11)** | 21 | **207.1** | 2.23× |
| **T6 MM (R12)** | 6 | **108.5** | 1.17× |

(R12 replicates the 07-13 RFJ T6 battle: 108.5 vs 113.8 ✓.)

**Reading:** K_eff collapses toward the clean 93 as the dealer strengthens ⇒ the
**Gatot-kit suppression DECAYS with incoming damage: S_gatot ≈ 4.7× → 2.2× →
1.2×** — a saturating defensive kit (large vs small hits, negligible vs huge
ones), now with 3 points to fit its form. Since S ≥ 1 always, **G^MM(T6) ≤ 1.17
⇒ the Marksman's own tier curve is bounded NEAR-FLAT** (Lancer-like, nothing
like Infantry's 10.9× damping). G^MM and S_gatot multiply and can't be fully
split from Gatot-target data; **one optional battle splits them: a T6 MM vs the
GORDON-Mueller Infantry** (K_eff = 93×G^MM(6) directly).

**Tier-damping panorama (dealer curves):** Infantry 1/4.32/10.89 (heavy),
Lancer 1/1.09/1.63 (mild), Marksman ~flat (≤1.17) — class-dependent throughout.

## Asks back to Martin (updated)
1. ~~E-NIF2 redo~~ **DONE (R11/R12).** Optional splitter remaining: **one T6 MM
   vs the GORDON-Mueller Infantry** — cleanly separates G^MM from S_gatot.
2. *(cosmetic)* R03/R04 Mueller-MM Health 118.6 → 128.6 if you want the panels
   internally consistent (no calc impact).

## Pressure-test battles (2026-07-17 late, Martin verbal — JSONs pending ingestion)

1. **Regime discriminator — 3× Vulcanus-led T6 MM vs Mueller-Gatot T1 Inf: 4 turns,
   Infantry defeated.** The budget gate predicted CAPPED (3×58.5=175 < B=202) →
   **REFUTED for hero-led mobs**; the S-curve with **per-dealer suppression then √N
   pooling** predicts ceil(3.85) = **4 = observed, exact blind pass** (linear pooling
   gives 3 — rejected). CONCLUSIONS: the two-regime split is **attacker hero
   presence**; hero-led mobs = S(d) per dealer + √N; the budget-absorb gate is
   hero-less-only; the order of operations is pinned.
2. **Splitter — Alpaca naked T6 MM vs Mueller-GORDON T1 Inf: 18–19 turns.**
   G_w^MM(6) = 1.079 (if Mueller in-alliance panels) / 1.224 (if out) →
   **near-flat confirmed**; back-solved S_gatot(T6) ≈ 1.0–1.1 (kit ~transparent to
   big hitters, matching the exp-decay). Pin needs the battle's alliance state /
   stat screen — ask Martin; Gordon's ~−5% dealer debuffs push G lower still.

## CORRECTION 2026-07-18 — pressure-test battle B re-read; splitter conclusion VOID

Martin's checked report: battle B ended **150 turns, Mueller (Gordon T1 Inf)
VICTORY** — not the verbally-reported 18–19-turn MM kill. Root cause of the
original misread: the "naked" (hero-less) T6 MM's true panels are ~+176/+166
(A/D) — the +1049.5/+1039.3 loadout used in the splitter arithmetic INCLUDES
Vulcanus's aura (+873.3 A/D, measured 2026-07-18 by same-day hero-swap pair
`MuellerAlpaca_..._2026 0718_162413/164811`). With naked panels the MM cannot
beat the Infantry, and a ~150-turn Infantry victory is law-consistent
(replicated exactly by the Gatot-analog battle: pred 150.0 vs obs 150, with
the budget gate correctly calling the MM's damage fully absorbed).
⇒ **G_w^MM(6) = 1.079/1.224 pin WITHDRAWN; G_w^MM stays bounded ≤1.17 (R12)
only. S_gatot(T6)≈1 back-solve also withdrawn.** Battle A correction: 6 turns
(1v1 R12 replicate, `..._164811`) — the 3-dealer version that would pin
hero-led √N pooling order was never captured and remains an open experiment.
Alliance state: Martin confirms Mueller's Gordon battles were IN RFJ.
