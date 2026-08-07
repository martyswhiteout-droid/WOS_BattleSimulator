# Gear / Charm / Widget Ladders — rulebook (2026-08-07; Leth/HP sub-question OPEN)

Owner asked (2026-08-07): codify the chief-gear / chief-charm / hero-gear / widget ladders, test whether the panel law needs them, using the third (non-max) account. Companion: `docs/STAT_PANELS_FORMULA.md`.
**Headline answers:** the panel law does NOT need gear levels (scout/battle panels already contain them — proven §Account-C below); gear ladders matter for U-calibration cross-checks, what-if simulation, and the future gear-OCR phase. Widget SKILL scales with widget level (read it from the special panel, never assume). Widget BASE stats are NOT in the panels.

## 1. Chief Charms ladder (Lv.1–16) — CONFIRMED vs owner endpoints (+9% → +100%)

Source: whiteoutsurvival.wiki chief-charms calculator (DOM-extracted, twice-verified). Each charm grants **Health AND Lethality, each at the % below**, for its gear piece's troop type. **3 charm slots per gear piece → 18 charms total; 6 per class.** Whale check: Lv.16 ×3 slots = +300/piece ×2 pieces = +600 Leth & HP per class = exactly the measured whale charm block ✓.

| Lv | HP=Leth % | | Lv | HP=Leth % |
|---|---|---|---|---|
| 1 | +9.00 | | 9 | +45.00 |
| 2 | +12.00 | | 10 | +50.00 |
| 3 | +16.00 | | 11 | +55.00 |
| 4 | +19.00 | | 12 | +64.00 |
| 5 | +25.00 | | 13 | +73.00 |
| 6 | +30.00 | | 14 | +82.00 |
| 7 | +35.00 | | 15 | +91.00 |
| 8 | +40.00 | | 16 | +100.00 |

(Materials/power columns in the source; omitted here.) **Charm level ↔ SHAPE** (OCR classifier target): 16 distinct shapes per the in-game Charm Guide (owner screenshots 2026-08-07: Lv1 triangle → Lv16 ornate pentagon; guide images are the classifier reference set). **Color ↔ class = owner-confirmed from the in-game guide: Green=Infantry, Blue=Lancer, Orange=Marksman** (no external source documents this; in-game guide is authoritative).

## 2. Chief Gear ladder — all 110 rungs (DOM-extracted from wostools.net/wiki/gear/chief-gear)

Grants **Attack AND Defense (each)** at the % below, for the piece's troop type only. Slots: **Helmet+Watch = Lancer, Jacket+Pants = Infantry, Ring+Cane = Marksman** (source-confirmed). Battle-report display order (owner rule): **Row 1 = Lancer, Lancer, Infantry · Row 2 = Infantry, Marksman, Marksman.** Red tier adds Troop Deployment Capacity (+40 → +1,200/piece). Set bonuses exist (3-piece = Defense all troops, 6-piece = Attack all troops — values not yet codified). Whale check: Red T4 ★★★ = +187.00 ×2 pieces = +374/class ✓ exactly the measured whale gear component.

Key rungs (full 110-rung table = agent extraction 2026-08-07, kept verbatim in the session record; codify to JSON in the gear-OCR phase):
Green — +9.35 · Green ★ +12.75 · Blue — +17.00 … ★★★ +29.75 · Purple — +34.00 … T1 ★★★ +54.23 · Gold — +56.78 … T1 ★★★ +74.63 · Gold T2 — +77.18 … ★★★ +85.00→+88.19 (sub-rungs) · Red — +89.25 … ★★★ +105.19 · Red T1 +106.25 … ★★★ +122.19 · Red T2 +123.25 … ★★★ +139.19 · Red T3 +140.25 … ★★★ +159.80 · **Red T4 +161.50 … ★★★ +187.00 (max)**. Note: several color+tier+star buckets contain 2–5 sequential sub-rungs with the same badge but different % (genuine source rows — OCR of the badge alone is AMBIGUOUS within those buckets by up to ~4pp; treat badge-derived values as a RANGE, or resolve via the piece's Power number when visible).

## 3. Hero gear & widget rules (owner-stated 2026-08-07 + reconciliations)

- Slots per hero: R1 Goggles, Gauntlet · R2 Belt, Boots. **Goggles/Boots → Lethality; Gauntlet/Belt → Health.** Applies only to the hero's own class.
- **THE MASTERY×ENHANCEMENT LAW (decoded 2026-08-07 from the owner's Saboteur-Goggles walkthrough, 8/8 points exact):**
  `gear_stat_% = (100 + E) × (100 + 10·M) / 200` — E = enhancement level (0–100), M = mastery level.
  Per-level step = (100+10M)/200 (→ 1.05 @M11, 1.10 @M12, 1.15 @M13, 1.40 @M18). Verified exactly: 124.95 (E19/M11), 126.00 (E20/M11), 145.95 (E39/M11), 152.90 (E39/M12), 154.00 (E40/M12), 174.90 (E59/M12), 182.85 (E59/M13), 184.00 (E60/M13), 222.60→224.00 (E59→60/M18, different gear). Max E100/M20 = 300% ✓ (whales). Empower GATES require mastery: +20 needs M≥11, +40 needs M≥12, +60 needs M≥13 (owner-observed; presumably +80→M14?, +100→M15? — unconfirmed). Validity below M≈10 untested.
- **Enhancement gates** (+20/+60/+100) add **Expedition Atk/Def** per the owner's slot table (+20, +30, +50 respectively; slot alternation ⇒ a fully-gated hero grants exactly **+200 Atk and +200 Def** to its class). +40/+80 gates = Exploration (hero-only) — no troop-panel impact. Gate points are FLAT (not mastery-scaled): Marlinman's classes each show exactly +40 (four +20 gates), whales exactly +200.
- **REVISED U MODEL (Marlinman discriminates; supersedes the §6 story in STAT_PANELS_FORMULA for the Leth/HP half):**
  `U_AtkDef(class) = hero_card_injection(gen, ascension) + gate points` — Rufus 5★: 1281.02 table + 40 = 1323.05 observed ✓ exact; Gisela/Karol (<5★): scalers 0.7395 / 0.785 on the gen table — **ascension ladder OPEN (need star counts)**.
  `U_LethHP(class) = Σ gear leth/hp (law above) + WIDGET BASE STATS` — **the hero card contributes ZERO Leth/HP to panels, and widget base stats ARE in the panels** (reversing the earlier §3 claim): Marlinman leftovers after exact gear arithmetic are 202.49/202.53 (Inf) = **Helacore +5's displayed 202.50 to the decimal**, 145.01/144.98 (Lan) = Karol's +4 widget, 224.02/224.01 (MM) = Rufus's +7 widget — Leth≡HP in every case, the widget signature.
  Whale re-attribution: U_lh 1095.0 = gear 600 + **widget ≈ 495** (their +15 widgets), not "injection 490 + 605". The old HERO_GEN_STAT Leth/HP column (4.9 etc.) was numerically absorbing the widget — it needs re-derivation as a widget ladder, not a hero-card stat. The whale "+5.00 uniform extra" now exists on the Atk/Def side only (2166.55 − 1961.56 − 200 = +4.99) — still unattributed (candidates: widget atk/def crumb, ascension precision).
- **Widget level** = `+N` on the first-row leftmost icon. **Widget SKILL scales with level** (PROVEN: Marlinman +7.5% Defender Troops' Attack vs whales' +15% Atk+HP) — fold sets must be read per report. **Widget BASE stats scale with level and DO enter the panel class rows** (measured points: +4 → 145.0, +5 → 202.5 (Helacore), +7 → 224.0, ~+15 → ≈495 (whales, inferred); per-widget ladder tables OPEN — likely widget-specific).

## 4. OCR detectability & phase-2 codification plan

| Element | How | Detectable? |
|---|---|---|
| Hero-gear mastery `Lv.N`, enhancement `+N`, widget `+N`, chief-gear tier badge `T1..T4` | text OCR, position-keyed by the layout orders above | YES (standard pipeline) |
| Chief-gear stars | icon count (small star glyphs) | classifier (template match) |
| Chief-gear color (Green/Blue/Purple/Gold/Red) | color histogram of the tile frame | classifier, easy |
| Charm level (16 shapes) + class (G/B/O) | shape+color classifier vs the Charm Guide reference images | classifier, medium |
| Ambiguity | same-badge sub-rungs (§2 note) | resolve via Power number or emit range |

Phase-2 tasks (extend the TDD plan when scheduled): ladders as JSON fixtures; gear-panel token schema; classifiers with the Charm-Guide/gear reference crops as test fixtures; reconciliation checks (predicted BO components vs OCR'd gear levels) as a new validator layer. NOT on the v1 critical path (§Account-C proof).

## Account C — [Lns] Marlinman (#567), transcribed 2026-08-07 from fixtures/panel_ocr/images (my reads, double-check pending)

**Trio (Hero Comparison; badge=gen CONFIRMED 3rd time):** Rufus S11 = gen-11 Marksman (5★ visible) · Gisela S13 = gen-13 Infantry · Karol S12 = gen-12 Lancer. Widgets: Rufus +7, Gisela +5, Karol +4. Hero gear (Goggles, Gauntlet / Belt, Boots):
- Rufus: Lv.14+59, Lv.13+59 / Lv.14+59, Lv.13+59
- Gisela: Lv.12+33, Lv.12+39 / Lv.12+39, Lv.12+31
- Karol: Lv.13+59, Lv.11+39 / Lv.11+35, Lv.11+39
Chief gear (mine): Red T1 — stars 2,2,3 / 3,3,3 (order Lancer,Lancer,Infantry / Infantry,Marksman,Marksman). Charms visible per piece (3 slots), levels TBD from shapes.
Specials panel: exactly ONE row — **Defender Troops' Attack +7.50%** | enemy +0.00. Enemy: 1 troop Lv10, NO heroes, experts 20/8.

**BO (Bonus Overview):** Troops' A 429.07 D 477.37 L 109.90 H 103.90 · Inf A 436.25 D 435.25 L 523.71 H 516.77 · Lan A 421.81 D 407.81 L 519.99 H 521.82 · MM A 460.25 D 440.25 L 556.33 H 555.74. NEW: BO has a **City Defenses** section (Defender/Territory Atk+Def) — all 0.0 here, and NOT the source of the +7.50 (that's the hero-widget skill).

**Scout = Battle-left, BYTE-IDENTICAL (12/12 cells):** Inf 2269.7/2151.7/1126.5/1129.0 · Lan 2189.6/2064.1/1103.7/1058.4 · MM 2385.8/2240.6/1263.9/1257.3. (Battle-right: Inf 543.3/509.1/411.7/368.3 · Lan 553.1/497.7/417.0/367.6 · MM 645.4/587.2/466.1/392.2.)

## CONFIRMED by account C (third independent account, non-max gear, mixed gens)

1. **The panel law holds unchanged.** S_scout = S_battle = {Atk +7.5% widget-skill row}, P=0 → predicted battle ≡ scout exactly → observed byte-identical. Zero adjustments.
2. **The widget SKILL scales with widget level**: +7.50% Defender Troops' Attack here vs +15.00% (whales, maxed) — and at this level grants Attack only (whales also had the Health row). ⇒ fold sets must always be READ from the report's special panel, never assumed constant. (OCR path already does this.)
3. **U is per-class** (first mixed-gen account): U differs by class exactly as the per-class lead-hero model requires.
4. **U_Atk = U_Def per class** to ≤0.07: Inf 1239.05/1239.08 · Lan 1178.98/1178.92 · MM 1323.05/1322.98 (S_scout atk fold divided out).
5. **MM (Rufus, 5★) Atk=Def decomposes EXACTLY**: U 1323.0 − gates 40 (his four gears all ≥+20 gate ⇒ 20 Atk + 20 Def per Martin's slot table) = **1283.0 vs gen-11 table 1281.02 (+0.16%)** — gen-injection table + gate arithmetic both validated at once.
6. **Widget BASE stats (e.g. Helacore +5 = Inf Leth/HP +202.5%) are NOT in the panel class rows**: if they were, implied injections go NEGATIVE. Where they act (hero power only? exploration?) = open; they do NOT contaminate the panels.

## OPEN — the Leth/HP overshoot (needs owner input / next derivation round)

U_Leth/U_HP per class (observed): Inf 492.89/508.33 · Lan 473.81/432.68 · MM 597.67/597.66.
Predicted by [gen-table injection + Martin's gear rule (mastery 10%/lvl + enhancement 1%/lvl per gear, 2 leth gears + 2 hp gears)]:
- MM (if Rufus 5★, injection 323): gear should be 274.7 observed-implied vs 388 predicted (Δ −113)
- Same-direction overshoots for Inf/Lan (entangled with unknown ascension of Gisela/Karol).
Whale identity (U_lh = injection 490 + gear 600 + 5) fit max accounts; account C says the leth/hp arithmetic at NON-max differs from the simple reading. Hypotheses: (a) my image transcription of the +N/Lv.N badges needs a double-check; (b) hero-card injection scales with ascension differently per stat pair; (c) mastery/enhancement contribute differently below max (e.g. gates consume part of enhancement's leth/hp; or Mastery Forging's two lines "Gear Strength Up" vs "Gear Stats Up" are distinct quantities); (d) BO class rows on this account include a component the whales' didn't.
**Discriminating questions for Martin:** (Q1) exact star/ascension of Rufus, Gisela, Karol on Marlinman; (Q2) one hero-gear detail screen from Marlinman (like the Mastery Forging shot) showing a gear's actual Leth/HP % so the per-gear number is measured, not derived; (Q3) confirm whether "Gear Strength Up" and "Gear Stats Up" are the same number at all levels.

## Task-12 fixture status (IMPORTANT — Codex must NOT run yet)

The dropped images are account C (Marlinman), NOT the golden-vector accounts A/B. Before Task 12: rename to `C_*`, add `accounts.C` to `golden_vectors.json` (panel values above; specials = the one +7.5 row; S/P sets {atk .075}/zeros; U per class from §above), update the images README and the Task-12 prompt mapping. B-account images and A-whale images still welcome to widen the corpus. Note: `A_battle_1/2` are gear/hero/expert screens (valuable for the FUTURE gear-OCR phase, not the panel benchmark); `A_battle_3` = the stat panel; `A_battle_4` = specials panel.
