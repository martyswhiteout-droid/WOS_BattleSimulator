# Hero kit registry — expedition skills + stat auras (per COPY)

> **Why this file exists (2026-07-18):** agents cannot read anything in-game;
> every skill effect must come from a Martin-provided tooltip screenshot or
> statement, and every aura from a controlled panel comparison. This registry
> accumulates them so nobody re-asks. **Effects and auras are PER COPY** (level
> / stars / gear of that account's hero) — never assume two copies match.
> Add provenance for every number. Unknown = absent, never guessed.
>
> **Aura = the flat panel-percentage-point contribution the hero adds to its
> class's Stat Bonuses screen when assigned.** Auras ARE captured in per-battle
> stat panels (the corpus is safe); the danger is CROSS-battle reasoning that
> reuses a hero-led panel capture for a hero-less setup or vice versa — that
> error voided the first "splitter" analysis (naked-MM clock estimated with
> Vulcanus-aura'd panels, ~6.3x too strong).

## Gatot (Infantry hero)

Common structure: S1 own-Infantry Defense buff; S2 "King's Bestowal" — fires
once per attack (`triggers == rounds`, THE exact turn clock) and grants a
shield; S3 "Royal Legion" — instills fear, static enemy-Attack debuff (fires
once at battle start). Royal Legion scale: L2 = −10%, L3 = −15%.

| Copy | Skills | Aura on Infantry (A/D/L/H pp) | Skill effects | Provenance |
|---|---|---|---|---|
| **Alpaca** (沃草泥的馬) | S1 **L2** / S2 **L2** / S3 **L3** | **+360.9 / +360.9 / +10.0 / +10.0** | S1 +12% own Inf Defense; S2 shield with protection = **Attack x 12%, each time they attack, for 1 turn**; S3 Royal Legion **−15%** enemy Attack | Levels+effects: Martin 2026-07-18 (S3 corrected L2→L3 same day — "the other way round"). Aura: v5 defender panels (537.1/529.9/119.7/119.3) minus same-day Gatot-removed panels (176.2/169.0/109.7/109.3), battles 20260712 vs 20260718_161706 |
| **Colonel Mueller** | S2 **L2** (= Alpaca's, Martin 2026-07-19 — exonerates S2 level for the B ×4.4 spread; stars/hero-level remain), S3 **L2**; S1 unconfirmed | **+301.9 / +302.0 / 0 / 0** | S3 Royal Legion **−10%** enemy Attack; S1/S2 as structure above (percentages at Mueller's levels unconfirmed) | S3: Royal Legion Lv.2 tooltip screenshot, Martin 2026-07-18. Aura: 20260718_162413 attacker Inf panels (481.0/481.7/112.0/108.7) minus no-hero loadout (179.1/179.7/112.0/108.7) |
| **Far Seer (Lab Rat)** | **S1/S2 only — NO S3** | unmeasured | as structure above | Skill-slot audit 2026-07 (`FarSeer_Gatot_S12_L1` budget key) |

### Gatot hero sheets (Martin's hero-screen screenshots, 2026-07-18/19)

| Copy | HeroAtk | HeroDef | HeroHP | EscAtk | EscDef | EscHP | Escorts | **Expedition Inf A/D** |
|---|---|---|---|---|---|---|---|---|
| Mueller | 2,608 | 3,403 | 51,067 | 868 | 1,134 | 17,022 | 8 | **+301.93%** |
| Alpaca | 3,091 | 4,028 | 60,447 | 1,026 | 1,343 | 20,149 | 9 | **+337.85%** |
| Far Seer | 1,686 | 2,200 | 33,003 | 559 | 733 | 11,001 | 7 | **+186.45%** |

**AURA = the hero's Expedition stat block, verified at source:** Mueller
+301.93% vs the measured battle-panel aura +301.9/+302.0 (EXACT). Alpaca's
cross-date measured +360.9 = 337.85 (Expedition) + 23.05 (alliance A/D delta
between capture dates); the apparent +10 L/H was likewise the alliance L/H
buff — the aura itself carries NO L/H (matches Mueller's same-day 0/0).

**Kit-state law (2026-07-18 shield test, `gatot_shield_test.py`):**
- **Un-aura'd Gatot** (unit's panels at its no-hero baseline) = **INERT**: no
  absorption, no Royal-Legion fold — 12 corpus rows fit the plain law ±3.2%.
- **Aura'd Gatot vs HERO-LESS dealers** = budget absorb, B measured 201.95
  (Mueller) / 30.15 (FarSeer) / ≥6.3 bound (Alpaca). Hero-led (Vulcanus)
  dealers bypass the budget (S-curve regime).
- **B_Alpaca MEASURED = 1419–1543** (K(Lan→Inf) = 91 / 83.7 branch) by the
  2026-07-19 knife-edge: 204× hero-less T6 Lancers CAPPED at 1500 rounds
  (defender untouched), 205× kill at turn 575 — the one-Lancer edge at N≈205
  plus the kill-time self-consistency is the LINEAR subtractive-budget
  signature at 10× the previous largest pooled test. **The (A·L × Expedition%)
  composite predicted 257 — REFUTED (×5.5-6 low).** Cross-copy scaling is
  OPEN: hero sheets scale only ×1.12–1.19 Alpaca/Mueller while B scales ~×7;
  remaining candidates = S2 skill level and STARS (Alpaca S8; Mueller's
  S1/S2 levels + all star counts unconfirmed).
- Static skill folds (S1 1.12 × S3 1/0.85 ≈ 1.32) do NOT explain the old
  "v5 M ≥ 2.58" — that cluster is DISSOLVED into the budget gate (no M
  constant exists).
- **Gatot-DEALER slowdown = INERT-STATE-EXCLUSIVE (settled 2026-07-19, E3a/E3b):**
  the AURA'D Gatot-led T7 dealer killed the discriminator target at **37 turns
  = the plain-law prediction EXACTLY** (`..._121104`), and a GORDON-led T7 was
  also on-law ([72,74] ≈ no-hero −3%, `..._121239`). Only the INERT/un-aura'd
  Gatot dealer (`151127`) runs ~4× slow. Under the production maxed-hero
  policy the inert state is OUT OF DOMAIN — the anomaly is quarantined to one
  historical instrument configuration (mechanism unknown, Stage-7 curiosity,
  no longer a production blocker).

## Vulcanus (Marksman hero)

| Copy | Skills | Aura on Marksman (A/D/L/H pp) | Skill effects | Provenance |
|---|---|---|---|---|
| **MiniMart** | **all L1** | unmeasured | S1 −4% enemy Troops Attack (once, start); S2 every 6th attack EVENT of its side, +20% that attack, CAN kill; S3 "True Strike" (turns 3,6,9,…): −12% enemy Inf/Lan Defense for 3 turns AND +12% own Marksmen's Attack for 1 turn | Levels: Martin 2026-07-18. Cadence: triangulation 2026-07-18. Effects: True Strike tooltip (L4 = 48%/48% ⇒ L1 = 12%/12%) |
| **Alpaca** | levels unconfirmed (an Alpaca-side attacker copy was seen WITHOUT S3 in one battle — slots vary per copy) | **+873.3 / +873.3 / +118.1 / +21.6** | as structure above | Aura: 20260718_164811 defender MM panels (1049.5/1039.3/247.2/150.6) minus Vulcanus-removed same-day panels (176.2/166.0/129.1/129.0, 20260718_162413) |

## Seo-yoon (attacker instrument)

S1: +5% / +10% / +15% own Troops Attack at L1/L2/L3. Aura unmeasured
(NanoMart panels always captured per battle). Provenance: NanoMart program.

## Gordon (Lancer hero)

Class-locked aura CONFIRMED LIVE (E3b, 2026-07-19): Gordon on an Infantry
march added NOTHING to the Infantry panel; his aura lands on LANCER only.

| Copy | Aura on Lancer (A/D/L/H pp) | Cadences (first model, 2026-07-19) | Provenance |
|---|---|---|---|
| Mueller (Lv 51) | +236.6 / +236.7 / +5.3 / +4.3 (L/H source unconfirmed — gear?) | S2 every 3rd turn, S3 every 4th (floor(T/n)); S1 showed 0 procs while leading an OFF-CLASS (Infantry) march | E3b battle `..._121239` (24/18 procs at T∈[72,74] vs the Vulcanus clock); E5 `..._122337` |
| Alpaca (Lv 64) | +251.6 / +251.6 / 0 / 0 | S1 every 2nd, S2 every 3rd, S3 every 4th (10/7/5 at T=21 — triple intersection) | E5 battle |

Kit effects = small enemy debuffs (E3b: −3% on the dealer's clock vs no-hero;
matches the old Gordon-target batteries' 2–5%). Effect tooltips still
uncaptured. NOTE the S1 on/off difference between an on-class and off-class
march — hero skills may require leading their own class.

**Production-domain policy (Martin, 2026-07-19):** the simulator assumes
heroes are MAXED on both sides, so per-copy aura/B spreads (hero level, gear,
stars) are CONTROLLED-EXPERIMENT INSTRUMENT artifacts — in production,
symmetric maxed hero sheets are the modeling assumption. Real marches carry
THREE heroes (one per class) so every class panel gets its aura; the law
consumes per-battle panels, so auras enter automatically.

## Elif / Ursar

Target-side debuff instruments (E-NIF batteries). Tooltips not yet captured.

---

**Maintenance rule:** any new tooltip screenshot or Martin statement about a
hero skill/aura gets added HERE (with date + provenance) in the same session.
The ingestion skill's troop-passives.md points here for hero kits.
