# The Three Stat Panels — Deterministic Mapping (CONFIRMED 2026-08-05)

**Status: CONFIRMED, zero fudge.** Worst residual across all 24 predicted cells = **0.054 percentage points**, i.e. display-rounding noise (panels show 1 decimal on values ~3000–4900).
**Provenance:** 9 screenshots of account `[RFJ]小艾Marty 191` (7.9M troops), captured 2026-08-05, all same account state: Bonus Overview (Military tab), own-city scout "Stat Bonuses", battle-report "Stat Bonuses" (Martin = defender, home territory), the battle report's "Special Bonuses" sub-panel, Expert Comparison, Hero Comparison, Chief Gear Comparison.
**Verification script:** session scratchpad `stat_panel_law_verify.py` (logic reproduced in §5; trivially re-runnable from the tables below).
**Companion docs:** `docs/EXPERTS_RULES.md` (expert skill tables), `docs/HERO_KITS.md` (hero aura = expedition stat block), `GAME_RULES.md` §2 + §6h (aggregation law this confirms and extends), §6s (pointer to this file).

---

## 1. The puzzle

The same account shows three wildly different "stats" depending on where you look (Infantry Attack: **658.25%** in Bonus Overview vs **+4491.6%** scouted vs **+4859.0%** in a battle report). All three are views of the SAME underlying state through different *inclusion sets* and a *multiplicative special-bonus fold*:

| Panel | What it shows |
|---|---|
| **Bonus Overview** (city screen, Military) | Standard additive pool ONLY, split into a global `Troops' X` row + per-class rows. **Excludes heroes and experts entirely; excludes all special-pool bonuses.** |
| **Scout report "Stat Bonuses"** | Full per-class standard pool (incl. lead heroes + experts) **multiplicatively folded** with the *always-on* special pool (pet self-buffs, defender-widget rows). |
| **Battle report "Stat Bonuses"** | Same as scout, but the fold uses the *battle-context* special set (adds territory rows), and the **enemy's penalties divide** the displayed value. Left column = viewer, right = enemy, both computed identically from each side's own state. |

## 2. The law

All values below as fractions (panel % ÷ 100). Per class `c` ∈ {Inf, Lan, MM} and stat `s` ∈ {Atk, Def, Leth, HP}:

```
std(c,s)      = BO_troops(s) + BO_class(c,s) + U(s)          # additive standard pool
Scout(c,s)+1  = (1 + std(c,s)) × (1 + S_scout(s))            # peacetime fold
Battle(c,s)+1 = (1 + std(c,s)) × (1 + S_battle(s)) / (1 + P_enemy(s))
```

equivalently, panel-to-panel (no std needed):

```
Battle+1 = (Scout+1) × (1 + S_battle) / (1 + S_scout) / (1 + P_enemy)
```

**Fold sets measured in this instance** (each special pool sums additively *within itself*, then applies as ONE factor — exactly GAME_RULES §2's special-pool law; enemy penalties enter as a **divisor** — exactly §6h's back-calc form):

| Term | Atk | Def | Leth | HP | Composition |
|---|---|---|---|---|---|
| `S_scout` | +0.25 | +0.10 | +0.10 | +0.25 | pet self-buffs +10% (all four) + defender-widget rows +15% (Atk, HP only) |
| `S_battle` | +0.35 | +0.20 | +0.10 | +0.25 | `S_scout` + Territory Defender rows +10% (Atk, Def only) |
| `P_enemy` | 0 | +0.06 | +0.04 | +0.05 | enemy's pet penalties (their "Enemy X Penalty" rows) |

Numerically pinned, not assumed: attack admits ONLY {widget 15 + pet 10} scout / {…+ territory 10} battle (ratio 1.35/1.25 = 1.0800 observed 1.08000); defense pins {pet 10} → {pet 10 + territory 10} with the 1.06 divisor (1.20/1.10/1.06 = 1.029160 observed 1.029149); lethality and health pin the pure divisors 1/1.04 and 1/1.05 to 2×10⁻⁵.

**The "Defending Own City +5%" rows are listed in the Special Bonuses sub-panel but are NOT folded into the displayed rows** (any fold set including them fails by ≥4 percentage points of ratio). Open sub-question §7.1.

**The `U(s)` block** — what Bonus Overview omits but scout/battle include — fitted from 12 cells with class-spread ≤ 0.06:

| | Atk | Def | Leth | HP |
|---|---|---|---|---|
| `U` (pct-points) | **+2166.55** | **+2166.60** | **+1095.01** | **+1094.98** |

`U_Atk = U_Def` and `U_Leth = U_HP` to 0.05 — precisely the paired structure of hero generation injections (`HERO_GEN_STAT`, prototype/index.html:2326: gen 13 → [16.2129, 4.05]). See §6 for decomposition.

## 3. Raw data (percent points, as displayed)

**Bonus Overview** — `Troops'`: Atk 748.49, Def 775.42, Leth 238.84, HP 219.86. Per class:

| Class | Atk | Def | Leth | HP |
|---|---|---|---|---|
| Infantry | 658.25 | 666.25 | 1197.36 | 1223.08 |
| Lancer | 649.25 | 616.25 | 1190.39 | 1154.28 |
| Marksman | 626.25 | 616.25 | 1153.24 | 1146.45 |

**Scout panel** (own city):

| Class | Atk | Def | Leth | HP |
|---|---|---|---|---|
| Infantry | 4491.6 | 3979.1 | 2794.3 | 3197.4 |
| Lancer | 4480.4 | 3924.1 | 2786.7 | 3111.4 |
| Marksman | 4451.6 | 3924.1 | 2745.8 | 3101.6 |

**Battle report, viewer column** (Martin defending, home territory):

| Class | Atk | Def | Leth | HP |
|---|---|---|---|---|
| Infantry | 4859.0 | 4098.0 | 2683.0 | 3040.4 |
| Lancer | 4846.8 | 4041.4 | 2675.6 | 2958.5 |
| Marksman | 4815.8 | 4041.4 | 2636.3 | 2949.2 |

**Battle report, enemy column** (attacker, no defender/territory rows): Inf 694.3/545.6/495.7/416.4, Lan 740.5/574.7/533.5/442.8, MM 800.6/626.6/587.1/499.0.

**Special Bonuses sub-panel** (mine | enemy): Defender Troops' Atk +15|0, Defender Troops' HP +15|0, Enemy Def Penalty (Pet) −10|−6, Enemy Leth Penalty (Pet) −5|−4, Enemy HP Penalty (Pet) −5|−5, Atk/Def/Leth/HP Bonus (Pet) +10 each|+8/+6/+7/+5, Territory Defender Atk/Def +10|0, Own-City Atk/Def +5|0, Enemy Leth Penalty (Expert) −0.75|0.
**Scout special list** (own scout, informational): the outgoing penalties only (−10/−5/−5 pet + −0.75 expert).

## 4. Why the naive additive reading fails

Treating the panels as additive sums (battle = scout + specials − penalties) misses by **−357 Atk / −115 Def / +107 Leth / +152 HP** points. The fold is multiplicative and the penalties are divisors; on a ~4000% base, ×1.08 ≈ +360 points. This is the trap that made the three panels look inconsistent.

## 5. Verification (all 24 cells)

`Battle_pred = (1 + BO_troops + BO_class + U) × (1+S_battle)/(1+P_enemy) − 1`, `Scout_pred` analogous with `S_scout`, no divisor:

| Cell | worst residual |
|---|---|
| Scout→Battle ratio law, 12 cells | ≤ 2.5×10⁻⁵ (ratio units) |
| BO+U→Scout, 12 cells (U fitted, 2 free values) | ≤ 0.061 pct-points |
| BO+U→Battle full chain, 12 cells | ≤ 0.054 pct-points |

12 equations per panel, 2 fitted constants total — the structure is massively over-determined and lands at display precision. **Zero fudge factors.**

## 6. Decomposing U — RESOLVED as a pure hero block (experts live in Bonus Overview)

- Prior art: GAME_RULES §7 "Next step agreed" already records that the scouted panel *includes* pet/item/widget/gears but **excludes hero [expedition] skills**; and §6o (hero panel injection) proves a lead hero injects its Expedition stat block into its OWN class rows only (Sonya +780.6/+780.6/+189.1/+175.1; `docs/HERO_KITS.md`: aura = expedition stat block, verified exact for Gatot copies).
- U is **uniform across the three classes** (spread ≤ 0.06) ⇒ each class row carries its own lead hero's injection and all three leads inject **identical** values ⇒ same-generation trio with identical gear. **Trio identified (Martin, 2026-08-06): Hank (Gen-15 Infantry), Estrella (Gen-15 Lancer), Viveca (Gen-15 Marksman)** — the portrait badge number = generation (skill `.claude/skills/wos-hero-identifier/`), confirmed against `hero_generations.json`. (The March corpus trio Gisela g13/Flora g13/Ligeia g12 would produce a 170.1-point Atk/Def spread — a different, older lineup.)
- **Expert test (the discriminator):** Romulus L100 maxed + Gareth-3 L88 give combined +10% Atk / +19% Def / +55.8% Leth / +62.8% HP (`docs/EXPERTS_RULES.md` §4, wiki tables). If experts sat inside U, the hero-gear residual would come out ASYMMETRIC (gear_Atk − gear_Def = +9.0, gear_Leth − gear_HP = +7.0). With experts excluded, the residual is symmetric to ≤0.05. ⇒ **expert war buffs are already counted inside Bonus Overview's global `Troops' X` rows** (they are permanent account-wide bonuses, like research), NOT in U. Corroboration: Gareth-3's "Fearsome Reputation" Lv.3 = −0.75% enemy lethality reproduces the battle report's expert-penalty row exactly. **Status upgraded to MEASURED by the §9 second-account test (2026-08-06):** the alt account runs a different, non-maxed expert loadout whose Def-only components would inject a +2–9 point Atk/Def asymmetry into U — observed asymmetry is −0.001.
- **Resolved decomposition per class row** (Gen-15 trio; corrected 2026-08-06 — an earlier draft wrongly assumed gen 13):

| Component | Atk = Def | Leth = HP |
|---|---|---|
| Lead-hero generation injection (Gen 15, `HERO_GEN_STAT` [19.6156, 4.9]) | 1961.56 | 490.00 |
| Remaining hero block (measured residual; identical across the trio) | 204.99–205.04 | 604.98–605.01 |
| **U total** | **2166.55–2166.60** | **1094.98–1095.01** |

- The residual block is **exactly the app's long-standing max hero-gear values (`MAX_GEAR_BONUS` 200/200/600/600) plus a uniform +5.00 on all four stats** (+4.99/+5.04/+5.01/+4.98). The 200/600 gear scale is therefore CONFIRMED at max; the uniform +5.00's source is unidentified (candidates: an exclusive-weapon passive or another small always-on hero-block source — a second-account capture set discriminates; see §7.2).
- The −0.75% "Enemy Lethality Penalty (Expert Skill)" appears in both scout and battle special lists and folds into the OPPONENT's divisor (part of their `P_enemy`), not into own rows.

## 7. Open items

1. **Own-city +5% rows**: displayed in the special panel but provably not folded into the shown rows. Either display-only, or applied in the engine's effective-stat layer without appearing in the panel numbers. One discriminator: a same-state city-defense report where own-city rows are the ONLY special difference.
2. **U decomposition residuals** (§6, updated after §9): experts-in-BO is now MEASURED (two-account discriminator). Remaining open: the small uniform above-gear component varies by account (**+5.00 main, +15.00 alt** — both exactly uniform across all four stats); candidates: exclusive-weapon passives, hero ascension deltas vs the gen table, or another small always-on hero-block source. Also the gen-injection table itself assumes the app's `HERO_GEN_STAT` values are exact per ascension state.
3. **Attack penalty divisor untested** (no pet/expert attack-penalty exists in these captures; assume symmetric divisor if one appears).
4. **Enemy column cross-check**: same law assumed for their column (their S_battle = their pets +8/+6/+7/+5, our penalties −10/−5.75/−5 as their divisor); untestable without their BO/scout — collect one allied pair to confirm.
5. Label localization variants (CJK panels) for the OCR lexicon.

## 8. OCR conversion recipes (the product payoff)

The engine's input contract is the **scout-net panel** (`stats_mode="scouted"`, ENGINE_INTERFACE.md §Legacy decision), with item/pet buffs passed RAW separately. Therefore:

- **From a scout screenshot:** use rows as-is. Done.
- **From a battle-report screenshot (both sides at once — the ideal user flow):** recover each side's scout-net panel exactly:
  `Scout+1 = (Battle+1) × (1+S_scout) × (1+P_enemy) / (1+S_battle)`
  where every term on the right is read from the SAME report's Special Bonuses sub-panel (side's own pet/widget/territory/own-city rows → S sets; opponent's penalty rows → P). No account knowledge needed.
- **From a Bonus Overview screenshot (own account only):** requires the account's U block. Calibrate U ONCE per account from any (BO, scout) same-state pair via `U = (Scout+1)/(1+S_scout) − 1 − BO_troops − BO_class`; thereafter BO alone suffices. U changes only when heroes/gear/experts change.
- Sanity ranges for validators: class rows 0–6000%; `S`/`P` components from the known special-row vocabulary (±20% items, +10% pets, −10/−5/−5 pet penalties, +15% widgets, +10% territory, +5% own-city, expert penalties <1%).

## 9. Second-account triangulation (2026-08-06, CONFIRMED — zero adjustments)

Account `[LnS]MᴀTɪX` (1.2B power, 3.7M troops; max chief gear + charms, **Gen-13 lead trio**, experts NOT maxed, **no pet rows at all**, no expert penalty; defender at home territory; enemy specials all 0). Same-state City Stats (Bonus Overview) + scout panel + battle report + special list. The identical law, with this account's fold sets read straight off its special panel (`S_scout` = widget 15 Atk/HP only; `S_battle` adds territory 10 Atk/Def; own-city excluded; no divisors since no penalties exist on either side):

| Test | Result |
|---|---|
| Scout→Battle ratio law, 12 cells | worst diff 2.6×10⁻⁵ (defense = 1.100000 exactly ×3; Leth/HP rows byte-identical scout↔battle, as predicted with no pets/penalties) |
| U uniformity across classes | spread ≤ 0.067 |
| U symmetry | U_Atk−U_Def = −0.001; U_Leth−U_HP = +0.013 (with a DIFFERENT expert loadout ⇒ experts-in-BO measured) |
| U totals | 1836.28 / 1020.00 = Gen-13 injection (1621.29/405.00) + **215.0/615.0** residual (≈ gear 200/600 + uniform +15.00; main account: +5.00) |
| Full chain BO+U→Battle, 12 cells | worst residual 0.064 pct-points |
| Own-city-folded alternative | fails by 4.35%/5.00% — rejected again, independently |

Raw data: BO Troops' 723.50/748.47/208.86/184.37; BO class Inf 617.25/620.25/1104.96/1110.03, Lan 617.25/616.25/1103.60/1107.63, MM 666.25/663.25/1158.52/1154.88. Scout Inf 3668.6/3205.0/2333.8/2676.6, Lan 3668.6/3201.0/2332.5/2673.8, MM 3724.9/3248.0/2387.4/2728.1. Battle (viewer) Inf 3996.3/3535.5/2333.8/2676.6, Lan 3996.3/3531.1/2332.5/2673.8, MM 4057.6/3582.8/2387.4/2728.1. Battle (enemy) Inf 862.3/913.6/623.7/610.8, Lan 847.9/886.2/620.0/615.8, MM 886.3/918.6/656.3/649.7. Specials (viewer): defender-widget +15 Atk/HP, territory +10 Atk/Def, own-city +5 Atk/Def; (enemy): all 0.

Notes: (a) accounts without pets simply lack those rows — the law degrades gracefully; (b) internal cross-checks hold exactly (Inf Atk = Lan Atk at every layer because BO class rows are equal and U is uniform; Def's 4.0-point Inf−Lan BO gap propagates unchanged to scout and battle).
