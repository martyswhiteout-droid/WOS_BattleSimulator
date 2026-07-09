# WoS Battle Simulator — Game Rules (source of truth)

Confirmed rules for the battle-formula derivation project. Every rule here was
either confirmed by Martin directly or verified against cited sources. Update
this file whenever a rule is confirmed, corrected, or added.

**Ultimate objective**: ingest many battle reports and decipher the underlying
battle formula — how Attack/Defense/Lethality/Health and all modifiers produce
the report outcomes (Losses / Injured / Lightly Injured / Survivors).

Data sources: `WoS battle simulator.xlsx` (tabs: Hero Stats, Hero Profile,
Hero Skills, Troop Stats, Current Stats - Self/Enemy), whiteoutsurvival.wiki
(hero pages, stat-bonus article, rally article), wostools.net (troop pages).
Code: `wos_sim/` package loads the workbook into typed models.

---

## 1. Troops

- Three classes: Infantry, Lancer, Marksman. Four combat stats: Attack,
  Defense, Lethality, Health. (Power/Load/Speed are non-combat.)
- **Troop tier config is PER PLAYER**: each participant (captain or joiner)
  brings their own tier/FC mix, even across classes (e.g. FC10 T11 Infantry
  with FC9 T10 Lancers). Full T10 & T11 FC0-FC10 tables are codified in
  `wos_sim/troop_catalog.py` (`troop_base_stats(tier, fc, class)`).
- Primary configs in current data: **T11 FC9, T11 FC10** (**T12** later).
  Verified against wostools.net — workbook "Troop Stats" tab matches exactly:

  | Tier | Class | Atk | Def | Leth | HP |
  |---|---|---|---|---|---|
  | FC9 T11 | Infantry | 18 | 27 | 17 | 26 |
  | FC9 T11 | Lancer | 27 | 19 | 25 | 18 |
  | FC9 T11 | Marksman | 28 | 19 | 26 | 18 |
  | FC10 T11 | Infantry | 19 | 28 | 18 | 27 |
  | FC10 T11 | Lancer | 28 | 21 | 26 | 20 |
  | FC10 T11 | Marksman | 30 | 21 | 27 | 20 |

- Stat bonuses are percentages **multiplying these base stats** ("troops are
  the avatar of the stats").

## 2. Stat-bonus aggregation (CONFIRMED, verified to 5 decimals)

```
Final stat = TroopBase × (1 + Σ standard bonuses) × (1 + Σ special bonuses, net)
```

- **Standard pool (additive)**: research, chief gear, chief charms, hero gear,
  hero base-stat contributions ("Heroes Effect"), **and hero expedition-skill
  stat buffs** (captain skills and joiner first-skills, e.g. Bradley +25%
  Attack). Everything sums.
- **Special pool (multiplicative layer)**: ONLY two source types —
  **exclusive widget skills** ("Rally/Defender Troops X +15%") and **buff
  items** ("Troops Attack Bonus +20%"). These pool additively *with each
  other*, then apply as one factor. Verified from wiki worked examples:
  541.6 + (20+5) + 541.6×0.25 = 702 (single pooled factor, NOT compounding).
- **Enemy debuff items net against the special pool before applying**:
  +20% buff vs −20% enemy debuff → net 0.
- Verified against Martin's own calculator (Current Stats - Self):
  Scouted = (Base + HeroesEffect + Gear×Fudge) × (1+Buff) + Buff — exact.
- Scout/battle report "Stat Bonuses" panel: green column = own, red = enemy.
  "Scouted Stats" 29.78573 means +2978.573%.

## 3. Expedition skill activation (CONFIRMED)

- Only **Expedition** skills exist in this model. Exploration skills are
  always ignored.
- **Every battle is Rally vs Garrison** — rally-vs-rally and field battles
  do not exist in this model.
- **Captain (rally lead / garrison leader)** — identical rules for rally and
  garrison: march has one hero per class; ALL 9 skills (3 heroes × 3) +
  all 3 widget skills activate.
- **Widget asymmetry (confirmed)**: Infantry heroes' widgets are ALWAYS
  Garrison-scoped (except irrelevant gen-1), so a rally captain can trigger
  at most TWO widgets (Lancer + Marksman heroes) while a garrison captain
  with three defensive heroes can trigger all THREE. There is no other
  intrinsic defender bonus — no wall/city freebies.
- **Joiners (rally or garrison)**: per joiner only the slot-1 (flag) hero
  matters, and only that hero's FIRST expedition skill. Slots 2-3 and joiner
  widgets contribute nothing. Cap: 4 joiner contributions — the game keeps
  the 4 highest-leveled first-skills among all joiners. Duplicates stack
  **additively**.
- Hero generation ≈ server age: gen 1 at day 0, +1 per 100 days; competitive
  captains field gen / gen−1. SR & legacy heroes are joiner-flags only —
  hence the workbook records only their Skill 1.
- Proc-skill math: simulator computes expected effects **from raw fields**
  (probability J, per-proc amount K, cadence L/M, duration N/O); column H
  ("Average Amount %") is display-only.
- **Counting units** for cadence (col M) and duration (col O) — confirmed:
  - **Turns**: battle turns; side- and troop-type-agnostic.
  - **Attacks**: attack events on the skill owner's side, any troop type
    (my Inf → my Lancer → my Marksman counts 1, 2, 3).
  - **Strikes**: attack events by the skill's OWN troop type only, own side
    (Infantry "every 5 strikes" counts only that Infantry's attacks).
  - **Received**: recipient-gated — as a trigger it counts hits received;
    as a duration/effect scope the effect only applies to units that were
    actually hit by the skill (a Lancer never touched is never affected).

## 4. Battle mechanics (CONFIRMED)

- Turn-based. Per turn each surviving troop class on each side makes its
  normal attack(s) (**6 normal attacks** total when all types are alive: 3
  classes x 2 sides).
- **RESOLUTION IS SIMULTANEOUS (Martin, domain-authoritative — CONFIRMED
  2026-07-09).** The attacker (rally) and defender (garrison) BOTH compute their
  damage from the SAME start-of-turn troop counts; procs/skills are calculated;
  then casualties are removed TOGETHER at the END of the turn (reducing counts
  for the NEXT turn only). There is **NO first-strike and NO within-turn
  retaliation** — a side's losses this turn do NOT reduce its own output this
  turn, and the defender does NOT fire with an already-thinned army. Any earlier
  "attacker first, then defender retaliates" wording was WRONG. (The turn engine
  already resolves this way: both sides' damage packets are built from the
  current counts, then both applied — `pvp_turn_engine.py` turn loop.)
  Corollary: with EXACTLY equal stats on both sides a battle is a mutual
  annihilation (both wiped the same turn). Real reports never have exactly equal
  stats — each player's chief gear / island / expert / research bonuses differ,
  so every real battle is decided by the stat + proc gap, not a role advantage.
- **Damage absorption order: Infantry → Lancer → Marksman.** All attacks hit
  Infantry while any Infantry lives; then Lancers; then Marksmen.
- **Exception — Ambusher (LANCERS ONLY)**: Lancer attacks have a 20% chance
  to strike Marksmen directly from turn 1, bypassing the front line.
- **Damage-scope convention**: any effect described as plain "damage"
  applies to BOTH normal and skill damage. Only effects explicitly scoped
  ("normal attack", "skill damage") are category-restricted. (E.g. Crystal
  Shield's offset applies to skill damage too.)
- **Damage Dealt / Damage Taken are not stats** — they exist only inside
  battle resolution. How they combine with Attack/Defense/Lethality/Health
  is UNKNOWN and is the formula to be derived. Working hypothesis (MAIN
  PAGE): TroopLoss ~ Attack×Lethality×(1+DD)×(1+enemy DT) vs (Def×HP)/unit HP.
- **"Attacks" counters count the skill owner's side only** by default; the
  engine has a `count_enemy_attacks` flag for the occasional exception.

### Battle formula hypotheses (sources reviewed 2026-07-02, to be FITTED)

Codified in `wos_sim/battle.py`; every choice is a parameter.

- **H1 "ratio kernel"** — community consensus (kingshotguides.com, Reddit
  r/whiteoutsurvival "What is lethality?", Google snippet; Kingshot ≈ WoS):
  `kills ≈ k × N^0.5 × (Atk × Leth) / (EnemyDef × EnemyHP) × SkillMod`,
  divided by target unit base Health. √troop scaling; Attack & Lethality
  multiply with equal weight; NO attack-vs-defense / lethality-vs-health
  pairing (explicitly called a myth by the community). Same shape as
  Martin's MAIN PAGE hypothesis.
- **H2 "two-channel"** — WoS Customer Service explanation: Attack damage =
  calculated damage mitigated by target Defense (+ damage-reduction
  effects); Lethality = TRUE damage, ignores Defense and all defensive
  modifiers, reduces Health exactly. Kept as alternative kernel.
  (H1 and H2 are algebraically close; reports will discriminate.)
- **SkillMod composition**: Kingshot guide claims same-hero joiner stacks
  add (4×25% → 2.0×) but DIFFERENT heroes' buffs multiply (1.5×1.5).
  Martin confirmed additive for same-skill stacks; cross-source
  composition is a fittable engine option (modifier_stacking).
- **Casualty split**: incapacitated = damage received / unit health, then
  split killed / severely injured / lightly injured by parameterized
  shares (context-dependent; fit from reports). RNG = optional
  multiplicative noise per attack event (rng_sigma).
- Modifiers can be scoped by damage category: Normal attacks / Skills / Both.
- Report outcome categories: Losses, Injured, Lightly Injured, Survivors.

## 5. Troop skills (from wostools.net; verified vs "Troop Stats" tab)

Innate to troop class at the given unlock. Proc skills recorded with raw
mechanics; expected value (EV) shown as the workbook encodes it.

| Class | Unlock | Skill | Raw effect | EV encoding |
|---|---|---|---|---|
| Infantry | T1 | Master Brawler | +10% attack damage to Lancers | DD +0.10 vs Lancer |
| Infantry | T7 | Bands of Steel | +10% Defense against Lancers | Def +0.10 vs Lancer |
| Infantry | FC5 | Crystal Shield II | 37.5% chance to offset 36 damage | −13.5 flat damage per attack |
| Infantry | FC8/FC10 | Body of Light I/II | Defense +4%/6%; extra 10%/15% damage reduction while Crystal Shield active | see contradiction A |
| Lancer | T1 | Charge | +10% attack damage to Marksmen | DD +0.10 vs Marksman |
| Lancer | T7 | Ambusher | 20% chance to strike Marksmen behind Infantry | targeting rule, no stat |
| Lancer | FC5 | Crystal Lance II | 15% chance of double damage | DD +0.15 |
| Lancer | FC8/FC10 | Incandescent Field I/II | 10%/15% chance of half damage taken | DT −0.05 / −0.075 |
| Marksman | T1 | Ranged Strike | +10% attack damage to Infantry | DD +0.10 vs Infantry |
| Marksman | T7 | Volley | 10% chance to strike twice | engine: literal 2nd attack event (re-rolls procs, advances counters); tab keeps DD +0.10 shorthand |
| Marksman | FC5 | Crystal Gunpowder II | 30% chance of +50% damage | DD +0.15 |
| Marksman | FC8/FC10 | Flame Charge I/II | basic attack +4%/6%; extra 25%/37.5% damage while Crystal Gunpowder active | Atk +0.06; DD +0.1125 (=0.375×0.30) |

Version note: FC9 troops still use the version-I skills where the II unlock
is FC10 (Body of Light, Incandescent Field, Flame Charge). FC5-unlocked IIs
(Crystal Shield/Lance/Gunpowder II) apply from FC5 up.

"Against" direction depends on the attribute: for damage effects it is the
TARGET class (Charge: vs Marksman targets); for Defense effects it is the
ATTACKER class (Bands of Steel: when attacked by Lancers).

## 6. Workbook encoding conventions

- "Hero Skills" tab: one row per atomic effect; a skill = rows grouped by
  (hero, skill source). Column H = max-level amount (decimal); negative =
  reduction. Foe = debuff on enemy troops.
- "The target" of per-attack procs is materialized as the front line
  (enemy Infantry), or Inf+Marks for Lancer attackers (Ambusher leak).
- Widget rows are the ±15% Rally/Garrison stat skill only (the widget's
  other skill is exploration-only).

## 6b. Battle report extraction (procedure confirmed on report_001)

Friendly side is ALWAYS the left column; friendly may be attacker or
defender. White sword icon = attacker, white shield = defender.

1. **Overview**: Troops, Losses, Injured, Lightly Injured, Survivors per
   side. Killed = Losses + Injured. Identity: Troops = Killed + Lightly
   Injured + Survivors. The side reaching 0 survivors first loses.
2. **Troop comparison**: per-class share %, FC badge (10 = 100% FC10;
   badge 9 = NOT all FC10, treat as ~FC9 average), tier level (e.g. 11.0;
   a 10.5 is a weighted average - use as a triangulation reference only;
   exact per-tier counts come bottom-up from the joiner panels).
3. **Stat Bonuses (scouted)**: 12 params per side. CONFIRMED: displayed
   values ALREADY NET the enemy's debuff items and pet penalties.
   Back-calc (divisor form, 6h): std = (1+Scouted)(1+P_enemy)/(1+S_own)-1.
   Hero skills are NOT included. SUPERSEDED (2026-07-03 set 5): hero
   stat skills are MULTIPLICATIVE factors on the stat, NOT additive with
   the panel - Seo-yoon +25% attack on a +850% panel account moved kills
   x1.2506 (additive predicted x1.026). See 6l.
4. **Special Bonuses panel**: composition of the special pool per side -
   war items (+-20%), widget skills (role-scoped: Rally/Defender rows),
   pet bonuses (+10% own stats) and pet enemy-penalties (Def -10%,
   Leth -5%, HP -5%). Reconciles exactly with the Hero Skills tab widget
   rows and the context-scoping rule (verified on report_001).
5. **Lead skill details**: per captain hero - his 3 expedition skills plus
   his class's troop skills. Stats-based rows show Triggered=1; PER-ATTACK
   procs (cadence 1) ALSO display Triggered=1 (game hides turn counts).
   Kills column records DIRECT damage kills only (indirect stat-boost
   contributions are never recorded). Per the CS explanation, Lethality is
   true unmitigated damage - the Kills rows likely isolate that channel.
6/7. **Joiners** (per side): flag hero (Skill 1 relevance), troops sent,
   kills, losses+injured, lightly injured, survivors, per-tier breakdown.
   Joiner universality: all troops share the rally's stats and activated
   skills; only troop type/quality/quantity differ per joiner.
   **Captain identification**: in a RALLY the captain is always the first
   block. In a GARRISON the game auto-selects the STRONGEST player as
   captain regardless of display position (the overview name is the CITY
   OWNER, not necessarily the captain; the skill-details panel always
   shows the actual captain's trio). Garrison joiners = the first four
   non-captain blocks from the top. When the captain isn't obvious from
   the screenshots, ask Martin (it's their strongest whale).

Turn-count triangulation (no turn display in reports): intersect cadence
skills' trigger counts, e.g. every-3-turns x9 => 27-29 and every-4-turns
x7 => 28-31, giving ~28-29 turns for report_001.

### Empirical discoveries from report_003 (defender win, Dec-2025 era; identities exact)

- **The injured share is LOCATION/STRUCTURE-dependent, not era-dependent**
  (revised after report_006): Oct-2025 fortress X:597 = 35%, Dec-2025
  X:117 structure = 30%, 2026 city + fortress battles = 35%. Constant
  within a report and across both sides; read it per report.

### Empirical discoveries from report_006 (Oct-2025, class-omission battle)

- **Composition experiment**: attacker (Smarty, won) brought ZERO Lancers
  (51% Inf + 49% Marks); defender brought ZERO Marksmen (61% Inf + 39%
  Lancers). Omitting a class removes its troop-skill rows from the battle
  panel entirely (friendly Lloyd's lancer rows and enemy Bradley's
  marksman rows are empty) - independent confirmation of class scoping.
- **Joiners tailored to composition**: Nora x4 = Inf+Marks DT -15% / DD
  +15% each -> EV -60% damage taken / +60% damage dealt covering the
  ENTIRE no-lancer army. Won despite conceding the untouchable-lancer
  class and the bypass channel.
- Defender pets all zero (older account/era). Specials panel top cropped -
  items/widgets rows missing, pending re-crop.
- Collapsed participant blocks (totals only, no per-class rows) are valid
  and handled; side totals and kills still reconcile exactly.
- **Losses vs Injured is NOT battle mechanics** (Martin): losses occur only
  when the infirmary overflows; with enough healing nothing ever dies.
  Treat Losses + Injured as one "killed" bucket driven by battle mechanics;
  their split is external.
- **New special-bonus category: "Appointment-based Troop's X"** (president/
  minister appointments; e.g. +7.5% all stats). Special pool sources are now
  item / widget / pet / appointment.
- Older-era panel has no pet enemy-penalty rows.
- Composition panel can show ABSOLUTE COUNTS (preferred over %); Martin can
  send counts in future reports.
- Winner's lancers untouched AGAIN (3/3 reports).
- Row-class assignment check works: AngerR's "marksman" row was actually
  Lancers (caught by panel-count reconciliation + kill-rate signature).
- Widget reconciliation now 6/6 (Defender Atk/Def/Leth +15% = Lloyd +
  Hervor + Ligeia garrison widgets exactly).

### Joint fit status (v0 ratio kernel, e=0.6, k=100, four reports, 2026-07-02)

- report_002: MATCH (within 10%). reports 001/003: sim favors attacker,
  actual defender won. report_004: sim favors DEFENDER (like Martin's own
  expectation), actual attacker won. No garrison freebie exists (Martin) -
  so the misses are NOT a side bonus; the static-EV kernel misses the
  BATTLE DYNAMICS that actually decide outcomes:
  1. The battle is a front-line race - whoever's Infantry falls first
     loses the absorption shield and collapses (4/4 reports).
  2. Lancers are STRUCTURALLY UNTOUCHABLE while infantry lives (nothing
     bypasses to them) - winner's lancers took zero casualties 4/4.
     Marksmen are erodible from turn 1 via Ambusher bypass. Damage
     invested in lancers is safe; in marksmen it degrades over the battle.
  3. Additive-pool dilution: stat-type skills (+30% Def) land on ~+3000%
     pools => <1% relative effect. DD/DT-type skills multiply OUTSIDE the
     pools => full effect. DD/DT joiner picks are ~25x more potent.
  4. v1 engine must therefore model: per-turn proc scheduling (not static
     EV), damage-category channels (not averaged), the marksman-erosion
     feedback loop, and check DT stacking form (Marty's Wu Ming x2 +
     Ahmose stack would be -90% additive - his infantry still fell, so
     DT reduction likely stacks multiplicatively or is capped).

### Empirical discoveries from reports_004/005 (the fortress pair, 2026-03-28/29)

- Same fortress, same defender army (healed), 48 minutes apart; both lost
  despite superior stats, quality, and numbers. Attackers used the same
  recipe: captains Gisela/Flora/Vulcanus + Jessie/Renee flags, lancer-heavy.
- **Formula framing CORRECTED by Martin (and it reconciles r5)**: the
  right comparison is not class-vs-class stats but WALL-CENTRIC - enemy's
  damage-dealer (Lancer+Marksman) Attack x Lethality volume vs my
  Infantry's Defense x Health. Infantry's own damage output is nearly
  negligible; its role is to hold the line - once it falls the army is
  squishy. Redone this way with EQUAL stat weights: r5 stats-only =
  0.63x (Marty should win); adding joiner DD multipliers = 1.33x enemy
  favor (observed 1.66x; erosion dynamics plausibly cover the rest).
  The lethality-downweight hypothesis is therefore DEMOTED - the
  equal-weights kernel + wall framing + skill multipliers largely works.
  Exponents stay as fit dials, but expected ~1.
- **Class output coefficients - REFINED by the first kernel fit**: the
  huge per-unit kill-rate gaps (Lancers 9-60x Infantry) are mostly the
  SQRT LAW acting on stack sizes (per-unit output ~ N^(e-1); big infantry
  stacks dilute), not a hidden class multiplier. Fitted coefficients are
  mild: k_Inf ~0.6, k_Lancer ~1.5, k_Marks = 1.

### First kernel fit results (6 reports, static wall-centric model, 2026-07-02)

Model: G = sum_c k_c N_c^e Atk_c Leth_c^b (1+dd_c) / (WallDef x WallHP)
x (1+wall_dt); fitted on damage ratios + within-side kill shares.

- **e = 0.50 recovered from the data** - the community's sqrt-troops law
  confirmed independently.
- **Lethality weight b = 1 confirmed** (freeing b moves it UP, never
  down) - Martin's wall-centric correction empirically vindicated; no
  lethality downweighting.
- k_Inf 0.6 / k_Lancer 1.5 / k_Marks 1.0.
- Kill-share observables mostly within ~2x; systematic misses are all
  the same shape: DEFENDER lancer shares under-predicted wherever that
  side's marksmen got bypass-eroded (static model uses initial counts;
  reality integrates a decaying marksman force while lancers never
  decay), and r4/r6 damage ratios miss for the same reason.
- CONCLUSION: the static skeleton is right; the missing layer is TIME
  INTEGRATION - the v1 per-turn engine with bypass erosion and proc
  scheduling is the next build.
- Formation meta (Martin): 5-0-5 (no lancers, Nora x4 or Mia/Molly-style
  lancer-free flags) vs 6-4-0 (no marksmen, Bradley favored on defense -
  his skills are class-agnostic) were common strategies; more such
  reports incoming.
- **The marksman duel decides the erosion war**: near-equal marksman
  counts (369k vs 371k), Marty's better stats - yet her marks produced
  221,079 kills vs his 41,318 (5.4x per unit). Her larger lancer mass
  (451k vs 309k) eroded his marks faster via bypass while her Vulcanus
  (20 procs, 56,872 + 33,827 direct kills) outperformed his Ligeia
  (3 procs). Marksman output is an integral of a decaying force.
- Winner's lancers zero casualties: now 5/5 reports.
- Joiner meta confirmed again: DD-multiplier flags (Jessie x3 + Renee)
  beat stat/defensive flags (Gatot diluted to +0.9% relative).
- report_004 attacker panel completed via re-crop (BingChangSIR block);
  RiceCake confirmed stray. All five reports' identities exact.

- **35% injured share CONFIRMED across reports**: 0.35001 on all four
  side-observations so far, and it holds per-class too (attacker Inf
  0.35005, Marks 0.35007). Treat killed:lightly = 35:65 as a constant of
  this battle type.
- **Winner's back rows stay untouched**: the winning side's Lancers took
  ZERO casualties in both reports (r1 defender 603k, r2 attacker 144k)
  while posting the highest per-unit kills (0.81-0.93/unit). Marksman-heavy
  defense (52.6%) collapsed; lancer-heavy compositions have won twice.
- **Pro-rata attribution refined**: per-unit kill rates are identical
  across participants only when their troop quality matches (r1); with
  mixed tiers (r2: Lv 10.7-11.0) rates vary slightly per participant -
  attribution follows damage contribution, not raw unit count.
- **Two-row participant blocks are not always Inf+Marks** - assign classes
  by reconciling against the composition panel shares and per-unit kill
  rates (r2: three blocks carried Lancers in unexpected rows).
- **Widget reconciliation 4/4**: both reports' special panels match the
  captains' widget scopes exactly (r2: Defender Health +15% = Eleonora's
  Garrison Health widget; Rally Attack +30% = Fred + Rufus).
- Mixed tiers (Lv 10.7/10.9): panels do NOT show per-participant tier
  mix; aggregate weighted tier is the only tier signal - open question
  how to bottom-up exact T10/T11 counts.

### Empirical discoveries from report_001 (all identities verified to the digit)

- **Fixed 35% injured share**: Injured / (Injured + Lightly Injured) =
  0.35001 on BOTH sides — the killed-vs-lightly split appears to be a
  constant, not RNG (Losses were 0 in this garrison battle).
- **Pro-rata kill attribution**: within each class, every participant's
  kills-per-unit is identical (e.g. Infantry 5.13% for all 8 attackers) —
  the game resolves battle at SIDE-CLASS aggregate level and distributes
  kills to participants proportionally. Side-level simulation is correct.
- **Absorption confirmed hard**: defender's 603k Lancers took ZERO
  casualties (infantry never fell) while contributing 80.6% of defender
  kills. Defender Marksmen were wiped despite the front line holding —
  only reachable via Ambusher bypass; per-unit kill rates (Lancer 3.08/u
  at 17k vs 0.81/u at 603k) suggest troop exponent ~0.5-0.65.
- **v0 sim status** (assemble.py + fit_report.py): pipeline reproduces
  casualty magnitude and absorption structure, but favors the attacker -
  actual battle favored the defender 2:1. Leading suspects: unknown
  defender joiner first-skills (not in any panel; need hero IDs), v0
  omissions (Crystal Shield flat offset, damage-category channels,
  targeted troop skills), kernel form. To resolve with more reports.

## 6c. Data wishlist & open rule questions (assessment after 8 reports)

Confidence: accounting/activation layer ~95% (fully reconciled);
structural skeleton ~80% (validated incl. r6/r8 A/B); per-turn damage
engine ~40-60% (the frontier - residuals systematic, not random).

Most valuable next reports: (1) any battle NOT ending in a full wipe
(end-condition + uncensored damage), (2) more same-army A/B pairs like
r6/r8, (3) a near-even close fight, (4) an extreme mismatch, (5) more
30%-split structures (X:117 type).

Rule answers (Martin, 2026-07-02) — ALL CONFIRMED:
1. Hit units leave the battlefield IMMEDIATELY (out of commission). The
   35%/65% severe/light classification is post-battle bookkeeping for the
   infirmary economy - zero effect on battle mechanics. This anchors the
   erosion model: damage removes fighting units in real time.
2. Every battle ends in a wipe of at least one side - NO exceptions, no
   turn cap, no retreat. Mutual wipes (both sides 0 survivors) exist but
   are rare.
3. Ambusher proc = the WHOLE lancer stack's damage strikes the marksmen
   that attack event; the 20% is the chance per event, not a damage slice.
4. Mid-turn retargeting is immediate when a class falls; Ambusher still
   procs when marksmen are already the front (no practical difference).
5. r8 specials panel was erroneous - corrected to mirror r6 (data fixed).

Key untapped identification lever: the ~50 direct-kill proc rows
(kills + proc count + stack size + stats known) allow near-algebraic
solution of damage-per-attack-event, independent of aggregate fitting.

## 6d. Battle-type taxonomy & beast hunts (2026-07-02)

- **Battle types**: player city / fortress (X:597-style) = 35% injured
  share; **Foundry** (X:117 map, event-driven, siloed) = 30% share and
  "small nuances" per Martin - report_003 is a Foundry battle, treat as a
  special case (may explain its residuals). **Territory/banner battles**
  exist too (BattleReportData p4): specials include "Territory Defender
  Attack/Defense +10%", shares observed 45%/35%. Beast hunts: severe
  share tiny (~0.2-1%) - shares are bookkeeping, type-dependent.
- **Beast hunts run the SAME battle engine**: beast armies = tiered unit
  groups (unit levels 4.1-10.0 shown like troop tiers) with a flat %
  bonus on all stats (Lv13 +18.5%, Lv18 +57%, Lv25 +257%, Lv30 +455%),
  and they proc troop skills (beast-side Crystal Lance / marksman gun
  procs observed). Beasts appear to never lightly-injure: all beast
  casualties are Losses.
- **beast_hunts.json** holds 11 controlled experiments (no heroes, no
  pets, no buffs, exact troop counts): class isolation (100 inf / 100
  lancer / 100 marks solo each wiping the same Lv18 beast), N-ladder
  (1/1/1 up to 10,000), a wall-size threshold bisection (900+600 loses,
  1,000+600 wins vs Lv30), and defeat-side (uncensored damage)
  observations. Key qualitative results already visible:
  - A single unit per class (1/1/1) wipes a 2,460-unit Lv13 beast with
    zero casualties - per-unit damage at N=1 is observable.
  - Class damage in isolation: marks wipe Lv18 in ~1/10th the turns
    infantry need (proc-count inference) - class output differences in
    isolation are far larger than stat products suggest.
  - 3,000 pure infantry LOSE to Lv30 while 1,000 inf + 600 lancers WIN:
    infantry buy time, lancers/marks convert time into damage.
  - Winner-side lancers untouched in mixed hunts (absorption also
    applies vs beasts).

## 6e. T12 "Exalted" (stats CONFIRMED 2026-07-04; core kernel unchanged)

- T12 base combat stats = same troop's T11 stats at matching FC level +3
  each. VERIFIED ALL THREE CLASSES against in-game screenshots (2026-07-04):
  model troop_base_stats(12,10,x) == screenshot exactly:
    Infantry  A22 D31 L21 H30  | Lancer A31 D24 L29 H23 | Marksman A33 D24 L30 H23.
  Power 178, Load 420, Speed 11 uniform. Owner confirms: core damage
  kernel UNCHANGED - T12 is just stronger stats + the three tier-3 skills.
- Research: Exalted (+3%/lv, +15%/stat + deploy capacity) + Molten
  (+1%/lv up to +120%/stat) - ADDITIVE stat pool, visible in panels.
  Troop counter unchanged.
- THREE T12 tier-3 SKILLS - exact in-game text + per-level values
  (screenshots 2026-07-04), all battle-start, 5 turns, "up to 8 rally
  members active when rallying OR garrisoning, higher skill level priority":
  * Indomitable Wall (Infantry): "reduces enemy Troops' damage inflicted
    by X% for 5 turns" - X = 0.6/1.2/1.8% at L1/2/3 (0.6%/level). Active
    members' levels SUM (Polar Terror: Total Level 4 -> 2.4% = 4x0.6).
  * Meridian Phalanx (Lancer): "reduces Infantry damage received by X%
    and increases Marksman damage dealt by X%, 5 turns" - X = 1/2/3% at
    L1/2/3 (1%/level). Two separate effects (own-inf DT down, own-marks
    DD up), levels sum across active members.
  * Starfire (Marksman): "increases Marksman damage dealt by X% every 5
    turns" - X = 0.5/1/1.5% at L1/2/3 (0.5%/level), STACKABLE every 5
    turns (i.e. +X% at turn 1, +2X at turn 6, +3X at turn 11, ...).
- ACTIVATION RULE (answers the old open Q): each of the three skills
  independently activates on the TOP-8 rally members by that skill's
  level; the active members' levels SUM; applies to rally AND garrison.
  A NEW channel beyond captain+top-4-joiner - the T12 skills poll up to
  8 members. Engine TODO (when simulating T12): battle-start 5-turn
  buff windows + Starfire's every-5-turn stacking ramp.
- HARD CAP (Martin, 2026-07-04): the summed skill level is CLAMPED at
  MAX 24 per rally, per skill - no higher. This equals 8 members x L3
  (the natural ceiling) but is an EXPLICIT clamp the engine must apply:
    total_level = min(sum of active members' levels, 24)
  before computing the effect. => Effect maxima:
    Indomitable Wall  24 x 0.6% = -14.4% enemy damage inflicted
    Meridian Phalanx  24 x 1.0% = -24% own-inf DT and +24% own-marks DD
    Starfire          24 x 0.5% = +12% marks DD per 5-turn increment
                                  (still ramps additively each 5 turns).
- NOTE: earlier "T12 Crystal Shield" was a mis-note - Crystal Shield is
  the pre-existing FC3-FC10 infantry skill (25%/37.5% chance to offset
  36 damage), NOT a T12 addition. T12 adds only the three skills above.
- => T12 is now FULLY specified at the data level. No more T12 field
  experiments needed for the engine; remaining work is pure engine
  implementation of the 5-turn windows + Starfire ramp.

## 6f. Beast units == troop tiers (VERIFIED 2026-07-03)

Beast unit groups ARE troop-tier units: power-per-unit matches tier power
EXACTLY at integer levels (Lv6.0=20, Lv8.0=38, Lv5.0=13) and linear
interpolation at fractional levels (Lv2.4=4.8, Lv3.2=6.6). Residual
mismatches = my 0.1 badge misreads (Lv20 observed 23.199 = exactly 6.4);
the solver infers exact levels by inverting group power. Beast stats =
interpolated tier stats x (1 + beast bonus). Beast bonus ladder:
Lv5/8/10/13/15/18/20/25/30 -> +1.8/5.3/8.5/18.5/26.5/57/87/257/455%.
=> Every quantity in every beast hunt is now KNOWN except the damage
formula itself - the system is fully determined for fitting.
Calibration harness: wos_sim/calibrate.py.

## 6g. Calibration set 2 + Polar Terror (2026-07-03 morning, CONFIRMED)

Data: wos_sim/data/beast_hunts_marlinman2.json, polar_terror_rally.json.

BUFF ALGEBRA - EXACT (12/12 panel readings, <0.1 pct-point error):
  displayed_panel = (1 + permanent_bonuses) x (1 + SUM temporary_buffs) - 1
  Temporary buffs (buff items + pet skills) are ADDITIVE with each other
  inside one pool; that pool MULTIPLIES the permanent panel. Same algebra
  as the PvP special pool S_net - two independent confirmations of:
  Final = Base x (1 + additive) x (1 + special/buffs).

HERO PANEL INJECTION - a hero in a class slot injects their hero-card
  military stats as ADDITIVE pct-points into their OWN class's panel rows
  only (measured: Sonya lancer +780.6 Atk/+780.6 Def/+189.1 Leth/+175.1 HP;
  Rufus marksman +1321.0/+1321.0/+597.7/+597.7). Atk/Def deltas equal
  within a hero. Hero SKILLS never appear in the panel. Both heroes ->
  both class rows boosted, no interaction. => Reports self-document hero
  stat contributions; simulating a lineup from scratch needs hero cards.

HERO LAYERING (100 lancers vs Lv18, incapacitated): none 12.2 avg |
  Rufus-only 7.3 | Sonya-only 0.7 | both 0.7. Rufus had ZERO marksman
  troops -> his 40% casualty cut is battle-time skills only, and his S1
  (+25% attack additive ~ +2.6% relative here) is too small to explain it:
  the working driver is S3 (enemy Lethality -50%, 2 turns, 20% proc -
  9/5/3 procs observed). Sonya = panel injection on the actual troops
  (Def x1.85, HP x1.24, Atk x1.81) + S1 DD+20% + S2/S3 lancer amps.

STOCHASTIC SPREAD at N=300 vs Lv25: 3692/4140/2961/3553/4390 (sd ~16%).
ATTACK ELASTICITY: +10% attack (multiplicative) -> +17% beast losses;
  +17% -> +36% vs baseline mean. Elasticity ~2 = survival-time
  compounding signature (more damage -> beast dealer stacks erode
  faster -> even more relative output). Noisy (sd 16%) but directional.
MARKSMAN WALL: 600 marks + 400 inf vs Lv25 = 25,926 beast losses vs
  8,334 for 1,000 pure lancers - protected marksmen ~3.1x lancer output.
ABSORPTION CONFIRMED ON RECEIVING SIDE: beast lancer group takes ZERO
  losses while beast inf front stands; beast marks losses = our Ambusher
  bypass only. In the marks-wall run (no lancers on our side): beast inf
  WIPED -> our attacks moved to beast LANCER group; beast marks untouched.
  => absorption order Inf -> Lancer -> Marks, bypass goes to Marksmen.
BEAST-SIDE TROOP-SKILL PROCS now visible in skill panels (right columns).

POLAR TERROR (rally-only beast, Lv8 Abyssal Shelldragon, 750k units):
  - Beast units = tier units here too: power/unit 66.0 = EXACT T10.
  - Separate bonus ladder: +660% at Lv8 (field beasts: +5.3% at Lv8).
  - T12 skills CONFIRMED with in-game text: Indomitable Wall "reduces
    enemy damage inflicted by 2.4% for 5 turns" at Total Level 4
    (0.6%/level); Meridian Phalanx "reduces Infantry damage taken by 2%
    and increases Marksman damage by 2% for 5 turns" at Total Level 2
    (1%/level); Starfire "increases Marksman damage dealt every 5 turns
    by 2%" at Total Level 4 (0.5%/level, stacking). "Total <skill>
    Level: N" = SUMMED across rally members -> additive total-level
    stacking confirmed in-game (cap 8 members per wostools).
  - Rally composition panel shows FRACTIONAL tier levels (Inf 11.5 /
    Lancer 11.3 / Marks 11.4) = troop-weighted average of the T11+T12
    mix - same interpolation convention as beast units.
  - The report's Stat Bonuses panel = the VIEWER'S own panel (captain
    Marlinman's, incl. his active buffs, though he sent only 3 troops).
    Rally stat aggregation NOT visible -> open question; controlled farm
    rallies are the right probe.
  - Widgets inert for Polar Terrors (Martin) - neither rally nor
    garrison context applies. Joiner flag-hero skills invisible as usual.

## 6h. Enemy penalties + Bradley skill ladder (2026-07-03, CONFIRMED)

Data: wos_sim/data/enemy_penalty_ab.json, bradley_skill_ladder.json.

THE COMPLETE STAT FORMULA (all pieces now measured exactly):
  Effective stat = TierBase
                   x (1 + permanent panel)      [account research/gear/etc
                                                 + hero-card injection]
                   x (1 + SUM own special buffs) [items + pets + widgets,
                                                  additive within pool]
                   / (1 + SUM enemy penalties)   [DIVISOR - not subtraction]
  Enemy-penalty A/B panels: divisor RMS ~0.03-0.11 pct-points (0.11 when
  recomputed from the 1-decimal rounded JSON; QA 2026-07-04) vs 3.75
  (subtractive) and 2.02 (multiplicative 1-p) across 6 affected rows -
  a DECISIVE divisor win regardless of rounding.
  At small PvP percentages divisor ~= subtraction (why old fits worked).
  Code updated: reports.standard_pool(), assemble.assemble_battle().
  Battle-time hero skill stat buffs join the PERMANENT (additive) pool.

BRADLEY LADDER (weak farm MatiBlizzard, 30 fixed troops vs Lv13 Tapir,
one run per config, then 120-troop finale):
  - Hero card Expedition stats SCREENSHOT (+144.69 Atk/Def, +4.83 Leth/HP)
    == panel deltas to the display digit. Card injection PROVEN by
    document, not just inference. Stars grow the card (2-star: +206.7);
    skill levels change the panel NOT AT ALL.
  - Bradley skill ladders captured from in-game tooltips:
    S1 Veteran's Might: Attack +5/10/15/20/25% (all troops)
    S2 Power Shot: DD to Lancers +6%/lv, to Infantry +5%/lv (all troops)
    S3 Tactical Assistance: DD +6/12/18/24/30% for 2 turns every 4 turns
    (unlocks at 2 stars)
  - Trajectory (beast losses): none 160 | 1* 253 | +S3L1 263 | S3L2 297 |
    S1L3 287 | S2L3 324. The no-hero->1-star jump (marks kills 81->170)
    is a clean big signal; per-skill-LEVEL increments (3-6% EV) are BELOW
    single-run RNG noise (lancer kill column swings 59-95 with no
    lancer-relevant change). Skill-ladder resolution needs ~5 repeats
    per config - repeats are free (no upgrade), do them BEFORE upgrading.
  - Power Shot's Lancer component is INVISIBLE vs beasts (front is
    always infantry; bypass hits marksmen) - only the Infantry component
    acts. Needs PvP/wall-order variation to measure.
  - Lv13 Tapir refined: SIX groups (Inf 150+590, Lan 170+690,
    Mar 170+690). Absorption + bypass reconfirmed (beast lancer groups
    zero losses in every 30-troop run).
  - 120-troop finale (100-inf wall): DEFEAT->VICTORY, 2,460 wipe.

## 6i. Far Seer pure-infantry ladder (2026-07-03 midday, CONFIRMED)

Data: wos_sim/data/farseer_infantry_ladder.json (8 battles, weak farm,
pure T7/T2/T1 infantry vs Lv12 Musk Ox, no heroes, NO PROC SKILLS on
either side).

THE ENGINE IS DETERMINISTIC WITHOUT PROC SKILLS. Three identical
  T7 N=1000 runs produced identical results TO THE UNIT (252/252/252
  beast losses, 2/2/2 injured, identical power losses). All previously
  measured variance (10-16% sd) is proc-skill RNG. Consequences:
  (a) proc-free configs need ONE run per data point - arbitrarily small
  effects are resolvable; (b) the v1 engine core is deterministic with
  RNG only in the proc scheduler.

N-EXPONENT CROSS-VALIDATED: T7 N-ladder 900/1000/1100/1200 ->
  214/252/291/332 kills => kills ~ N^1.525. Survival time ~ N^1 (own
  wipe), so per-event exponent e = 0.525 - EXACTLY the static-fit value
  from the 8 PvP reports. Two independent derivations agree.

TIER LADDER at N=1000: T1 11 / T2 26 / T7 252 kills - clean kernel-shape
  constraints (naive per-event A*L-linear x survival-time overpredicts
  T7/T2 42x vs observed 9.7x -> kernel shape is NOT plain product-linear;
  solver must discriminate forms with these points).

BOOKKEEPING: own power loss = injured x tier power EXACTLY (lightly
  injured cost no power; also identifies attacker tier unambiguously).
  Beast power loss = kills x unit power exactly. Lv12 Musk Ox = Lv4.0
  units (9.0 power), bonus +14.4%, groups 570/670/670.

## 6j. Far Seer set 3 - Seo-yoon/Jassier ladders + kernel facts (2026-07-03)

Data: wos_sim/data/farseer_set3.json (22 battles, deterministic).
Confirmed skill tooltips: Seo-yoon "Rallying Beat" = all-troop Attack
+5/10/15% (L1/2/3); Jassier "Tactical Genius" L2 = +10% damage dealt.

LOCKED KERNEL FACTS (deterministic, exact):
1. ATTACK ELASTICITY = 1.0. When own survival time is unchanged, +x%
   attack -> +x% kills EXACTLY (Seo L1/L2/L3: x1.048/x1.102/x1.153 vs
   predicted 1.05/1.10/1.15; both beasts; integer rounding only).
2. ATTACK SKILL == DAMAGE-DEALT SKILL per point: Jassier +10% DD -> 257
   kills; Seo-yoon +10% attack -> 257 kills, identical config. (Cannot
   yet separate "skill multiplies attack" from "additive-with-panel with
   damage exponent 1.116" because the farm panel is tiny (12.1%). BIG-
   PANEL discriminator experiment: on Marlinman (+858% attack panel),
   additive predicts +1%, multiplicative predicts +10% - one run pair.)
3. N-EXPONENT e = 0.525 (third independent derivation: Seo-L2 Tapir
   ladder N^1.51-1.55; baselines compose: 257/1.10 = 177 x 1.2^1.525).
4. DETERMINISM extends to 3-class armies and hero configs (two exact
   replicate pairs).
5. Composition >> tier: 500 T7I + 200 T6L + 300 T6M kills 1,466 vs 252
   for 1,000 T7 infantry (marks per-unit output ~14x infantry).
6. Compounding reconciliation: Far Seer attack elasticity = 1.0 (beast
   damage sources barely erode -> fixed own survival) vs Marlinman
   elasticity ~1.7 (his marks/lancers erode beast dealers -> longer
   survival). Same engine, endogenous difference.
7. Lv13 Tapir groups are ALL Lv4.2 (power arithmetic 9.797/unit exact).

KERNEL FORM STATUS: the pure multiplicative power law
k N^e A^pa L^pl/(D^qd H^qh) is REJECTED - with pa=1 fixed by fact 1,
no exponents reconcile the T1/T2/T7 tier ladder with the mixed-class
kill splits (T7 overpredicted ~50%, lancer split underpredicted).
Subtractive/floor forms (max(A - qD, cA)-style) are the leading
candidates - they also EXPLAIN attack linearity (a floor proportional
to A keeps damage linear in A even when A < D). Structure sweep in
wos_sim/farm_fit.py (families: power, sub_floor, sub_floor_LD,
saturate, two_stage).

## 6k. Far Seer set 4 - tier rungs, single-class, beast ladder (2026-07-03)

Data: wos_sim/data/farseer_set4.json. All deterministic, all power
identities exact (own power loss = injured x tier power identifies the
attacking tier: 12=T3, 18=T4, 26=T5, 40=T6, 56=T7).

TIER LADDER (N=1000 infantry vs Lv12 Musk Ox):
  T1 11 / T2 26 / T3 51 / T4 87 / T5 125 / T7 252.
SINGLE-CLASS (N=1000 T6 vs Lv12): Lancers 185, Marksmen 202
  (202/185 = 1.092 ~ the marksman-vs-infantry +10% counter).
BEAST LADDER (T7x1000): Lv10 VICTORY (wipe 1,070; OWN 563/1000
  incapacitated - first uncensored own-casualty point) / Lv12 252 /
  Lv13 177 / Lv15 83 (x13 power = Lv5.0 units exact).
Lv10 Musk Ox = SIX groups (65+255 / 75+300 / 75+300 @ Lv3.2).
SEO-YOON IS A MARKSMAN HERO - her card injected +140.1/+148.1/+5.4/+5.4
  into Marlinman's Marksman panel rows (third documented card injection).
  Rallying Beat L5 tooltip: +25% (ladder 5/10/15/20/25 complete).
MARLINMAN DISCRIMINATOR: inconclusive as run - his +850% panel wipes
  the Lv13 Tapir even with 2,000 T1 troops (6 casualties); kills fully
  censored. FIX: defeat configs (200-300 T1/T7 inf vs Lv20-25 field
  beast, no-hero vs Seo-yoon pair; T1/T7 have no procs so runs stay
  deterministic on his account too).

## 6l. Set 5 - skill pool VERDICT + turn clocks (2026-07-03 evening)

Data: wos_sim/data/farseer_set5.json.

STAT SKILLS ARE MULTIPLICATIVE (question closed): Marlinman (+849.8%
  attack panel), 300 T7 infantry vs Lv23 Giant Elk: no hero 830 kills,
  Seo-yoon (+25% attack, marksman card inert for infantry) 1,038 kills
  = x1.2506. Additive-with-panel predicted x1.026 - DEAD. T1 pair
  (36 -> 43) consistent within integer quantization. So: every hero
  stat skill = its own multiplicative factor:
  Effective stat = Base x (1+panel) x (1+Sum buffs)/(1+Sum penalties)
                   x Prod(1 + skill_i).
  (Supersedes the old "skills join the additive pool" assumption in s.2.)

FC PROC SKILLS ARE ACCOUNT-GATED (Martin): once an account has FC,
  Crystal Shield etc. proc for ALL troop tiers, even T1. FC accounts are
  never fully proc-free.

TURN CLOCKS WORK AND CROSS-VALIDATE: Bradley S3 (every 4 turns) and
  Renee S1 (every 2 turns, fires on odd turns from turn 1) agree:
  Tapir13 vs ~300 T7 inf: T = 31; vs ~1000: T = 57-58.
  => Duration scales ~N^0.58, NOT ~N: the beast's kills-per-turn GROW
  with our count (~N^0.42-0.49) - the DEFENDER's count enters the
  damage kernel (engagement-width behavior). Consequently the N-ladder
  exponent 1.525 decomposes as ~N^0.95-1.0 per event x ~N^0.53 duration,
  NOT N^0.525 x N^1. Earlier "per-event e=0.525" reading corrected.

T6 CLASS TRIPLE at N=1000 vs Musk12: Inf 174 / Lan 185 / Mar 202.

SINGLE-DEALER PROBE (Renee +1 lancer): 1 T6 lancer killed 14 (T=31,
  300-wall) and 54 (T=57.5, 1000-wall) - 0.45 vs 0.94 kills/turn. Same
  lancer, same beast: per-turn output doubled with the bigger own-side
  wall -> another own-side-count coupling in the kernel (side-level
  pooling?). Renee card injects Lancer rows (+111.3 Atk/Def) - third
  hero card documented.

BRADLEY MULTIPLIERS vs beast: 1000 T7 Tapir: 213/177 = 1.2034 =
  S1(x1.15) x S3-EV(~1.046). His S2 Power Shot (+15% DD to Infantry)
  apparently did NOT act against beast units - open question (class-
  targeted DD may not apply to beasts, or "Infantry" scoping differs).

## 6m. Set 6 - lethality linear, D*H survival, composition check (2026-07-03 night)

Data: wos_sim/data/farseer_set6.json. All vs Lv13 Tapir. Far Seer panel
CHANGED (Lethality +10% -> +20% all classes) = accidental lethality A/B.

- LETHALITY LINEAR: eff leth x1.0909 -> kills x1.0997 (3 probes).
- ENEMY-LETH DEBUFF (Lloyd EV -6%) -> our survival +5.2%: incoming
  damage ~linear in attacker lethality. Lloyd S1 "enemy Lethality -4%"
  + S2 "every 3 turns ... all enemy lethality -6% for 1 turn" (verbatim
  tooltips, L1). Lloyd offensively inert for pure-inf armies.
- T2 WALL DURATIONS: 300 -> ~9.5-10 turns, 1000 -> ~17.5 turns.
  T7/T2 survival ratio 3.26 ~ own DxH ratio 3.43 -> DEFENSE and HEALTH
  enter survival ~linearly as a PRODUCT.
- DUAL CLOCKS in one battle agree (Lloyd every-3, Bradley every-4).
- GRAND COMPOSITION CHECK: Lloyd+Bradley 1000 T7 = 246 observed =
  177 x 1.10 (leth) x 1.2034 (Bradley) x 1.052 (duration ext) = 246.4.
  The multiplicative layer stack is right end-to-end.
- Bradley baseline check closed: no-hero 300 T7 = 32 (new panel) ->
  29.1 old-panel = 35/1.2034 EXACT.
- THE remaining kernel puzzle: A and L each LINEAR at the margin, but
  across tiers per-turn output ~ (A*L)^0.44 - a large tier-linked
  suppressor (same family as the solo-vs-mixed dealer factor ~10 and
  the N_def^~0.45 coupling) is still unidentified.

## 6n. Set 7 - tier durations, prediction test, emerging kernel shape

Data: wos_sim/data/farseer_set7.json (2026-07-03 22:10-22:12).
- PREDICTION PASSED: T7-1000 vs Musk = 72-75 turns (predicted 75-84).
- Multiplier stack validated x4 more (Bradley 1.2034 x leth 1.0997
  reproduces set-4 no-hero kills exactly: 51/87/125/252-family).
- DURATION LAWS: T ~ N^0.515 (locked across N=100..1000, two beasts);
  T ~ (own DxH)^0.8-1.0 across tiers (T3..T7: 33.5/41.5/49.5/73.5).
- EMERGING KERNEL SHAPE: total battle kills ~ c x A_eff x L_eff x f(N),
  c ~ 4.2-5.3 across T2-T7 vs same wall - duration nearly cancels out
  of TOTAL output while marginal elasticities of A and L stay exactly
  1.0. Candidate mechanisms: retaliation-paced exchange or side-level
  damage pooling. NOT closed: the protected single-lancer runs (never
  struck, output scales with battle length AND wall size) contradict
  pure retaliation. The sim structure-hunt now has: A,L,DD linear;
  DxH-product survival; T~N^0.515; T~(DxH)^0.85; total ~ A*L; solo-vs-
  mixed factor; N_def^0.485. One mechanism must generate ALL of these.
- The +10% lethality was the state-wide Supreme President buff (24h,
  expires 2026-07-04 ~19:00): panels self-document it, comparability
  unaffected; it appears in the TEMP-BUFF pool fold (like items/pets).

## 6o. Set 8 - debuffs, stacking, second blind prediction (2026-07-03 late)

Data: wos_sim/data/farseer_set8.json.
- BLIND PREDICTION #2 PASSED: Ling Xue (-4% enemy attack at her L1) ->
  predicted 14 Bradley procs / 244 kills; observed 14 / 242.
- Enemy-ATTACK debuff multiplies the enemy's attack stat (duration-
  verified); enemy-DEFENSE debuff divides the wall's defense in our
  output (Estrella check exact). Both ~linear.
- SAME-STAT STACKING: two -5% defense debuffs (Estrella+Ligeia) stack
  ~fully (x1.047 obs vs x1.053-1.056 predicted); additive-pool vs
  multiplicative indistinguishable below 5% magnitudes. The community
  "diminishing returns" lore = the divisor algebra (each added point
  divides against a bigger denominator), not a stacking penalty.
- New cards: Elif (INFANTRY, +457.3 Atk/Def - huge), Estrella (lancer,
  +404.1), Ligeia (marksman, +200.1), Ling Xue (lancer, +17.7).
- Ligeia S1 "Nerf Poison" = enemy DEFENSE -5% per tooltip (not
  lethality as commonly believed). Trust tooltips.
- CORRECTION (Martin, 2026-07-04): DD skills (e.g. Jessie S1) apply to
  the ENTIRE rally side, same as all captain/joiner skill activations -
  never just the owner's march. DD vs DT distinction is only: DD = own
  side's output pool; DT = target's received-damage pool; the pools
  multiply with each other.
- First T7-1000 VICTORY vs Tapir (3 heroes incl. Elif) - flagship
  engine regression battle (compounding + wipe dynamics).

## 6p. PvP casualty kernel from 3 controlled ladders (2026-07-04, CONFIRMED)

Data: wos_sim/data/pvp_ladder_v9.json (symmetric), _v9b.json (fixed-attacker),
_v9c.json (mirror). 8 unique (N_att,N_def) count-pairs, all attacker-VICTORY
with the defender FULLY WIPED, attacker MARKS untouched (all attacker casualties
= infantry). Attacker T10 inf + T6 marks (Bradley only) vs defender T7 inf + T6
marks, both 50/50. No procs => deterministic (3 identical 6Kv6K confirmed).

PROC-UNLOCK PRINCIPLE (Martin, 2026-07-04): a proc exists ONLY if the skill is
actually on the troop/hero panel - NEVER assume one from the troop class. Procs
are gated by their real unlock tier: Ambusher (lancer 20% bypass) = T7+; Crystal
Lance (double-dmg) = Fire-Crystal/T11+. A T6 lancer has NEITHER, so a T6-lancer
army is DETERMINISTIC. (A mixed 40/20/40 rung with T6 lancers, 7500 vs 6000,
gave inf_incap 485 - deterministic, ~-4% vs a same-size 50/50 army: the
total-count kernel is roughly composition-robust.) Engine gates:
mechanics.AMBUSHER_MIN_TIER=7, CRYSTAL_LANCE_MIN_TIER=11.

The three ladders (varying both counts / fixing attacker / fixing defender)
jointly IDENTIFY what 8 uncontrolled whale reports could not. A design-panel
workflow (4 kernel families, adversarial leave-one-rung-out CV) + independent
refit converged on ONE 2-parameter homogeneous law (module wos_sim/pvp_kernel.py):

    survivors_total = (N_att^E - K * N_def^E)^(1/E) ,  att_inf_incap = N_att - survivors
    E = 1.4291  (homogeneity = own_exp - enemy_exp + 1)
    K = 0.1308  (the T10-vs-T7 strength ratio kD/kA)

Equivalent per-turn kill-rate kernel: R_side = k * N_own * N_enemy^(ed-1),
ed = 3-E = 1.5709. Each side's kill rate is LINEAR in its OWN live count and
carries a target-abundance exponent (ed-1)=0.571 on the ENEMY count. This gives
the observed casualty law att_inf_incap ~ N_att^-0.465 * N_def^1.451:
  * bigger ATTACKER -> FEWER own casualties (wider wall + faster wipe);
  * bigger DEFENDER -> SUPER-linear (^1.45) more attacker casualties (lives
    longer AND fires with more shooters -> compounding). NOTE ed>1: this is
    target-abundance, NOT a <1 frontage cap - do not import beast ed=0.483.

VALIDATION: train log-RMSE 0.0286 (max 5.6%), LORO-CV 0.0400 (beats the plain
OLS baseline CV 0.0434); params rock-stable across folds. Independently
re-derived from scratch -> identical E,K. Weakest corner: very attacker-heavy
(16k vs 6k) +5.6% high (shared by every model - a data-coverage gap).

REGIME BOUNDS (do NOT extrapolate): 50/50 comp only; T10-vs-T7 only (K bakes in
that tier gap); attacker-wins-full-wipe only (kernel flags attacker-loss when the
inf wall would breach); no proc/RNG (deterministic mean, ~10-15% real variance).

NOT UNIFIED WITH THE WHALE-REPORT ENGINE. The r6/r8 anchors are ~1.6M troops;
transplanting ed=0.571 at that scale (with the small-battle `rate`) blows the
damage up and mutual-wipes turn 1 - a scale mismatch across a 100-1000x count
gap. So pvp_engine keeps its own r6/r8 calibration (enemy_ab defaults OFF); the
ladder kernel is a validated STANDALONE predictor for the farm/garrison-rally
regime. Cross-regime unification needs controlled ladders at other scales/tiers.

## 6q. Hero GENERATION affects STATS only, never skills (2026-07-05, CONFIRMED)

Source: workbook 'Hero Stats' x 'Hero Profile' tabs + the 'Current Stats - Self'
aggregation formula. Module wos_sim/hero_stats.py.

- A LEAD hero's four stat values depend ONLY on its GENERATION (not the hero or
  class). Exact per-gen table (x100 = %; Attack==Defense, Lethality==Health):
  g14 (17.9143, 4.475) g13 (16.2129, 4.05) g12 (14.5116, 3.625) g11 (12.8102,
  3.23) g10 (11.1088, 2.775) g9 (9.4075, 2.32) g8 (7.8062, 1.93) g7 (6.5052,
  1.605) g6 (5.4043, 1.335) g5 (4.4435, 1.11) g4 (3.7029, 0.925) g3 (2.9023,
  0.7) g2 (2.4019, 0.6) g1 (2.0016, 0.5). Verified EXACT for gen 2-14 vs every
  workbook hero; gen 1 is a mixed SR/legacy bucket (joiner-only, never leads).
- AGGREGATION (workbook formula, per class per stat):
  Scouted = (Base + HeroesEffect + Gear*Fudge) * (1 + Buff) + Buff,
  where HeroesEffect = the lead hero's gen value. So the hero enters ADDITIVELY
  in the same units as the panel, INSIDE the buff multiplier -> net panel
  contribution = gen_value * (1 + buff[stat]).
- CROSS-CHECK (controlled report, 20 min apart, only lancer lead swapped):
  Mia g3 -> Fred g9 moved lancer Attack by (9.4075-2.9023)*1.15 = +748% (attack
  buff 0.15) and lancer Defense by *1.0 = +650% (defense buff 0). The
  attack-vs-defense gap IS the per-stat buff factor - model reproduces it.
- GENERATION NEVER SCALES SKILLS. Skill effect amounts come from the skill book
  verbatim (assemble.py); a gen-14 hero's skill == a gen-1 hero's skill. Only the
  STAT contribution grows with generation. (Verified: no gen multiplier on any
  skill amount in the code.)
- USE (predictor, Martin's method): for a PRE-ASSUMED symmetric matchup (front-end
  supplied identical stats both sides), hero_stats.relayer_panel strips the
  highest-gen hero (assumed baked into all classes) and re-applies each class's
  ACTUAL lead-hero generation. When the two sides have DIFFERENT real scouted
  stats, use them as-is (no relayering). assemble.py (report replay) is unchanged
  - the scouted panel there already includes the heroes.

## 6r. Duration calibration - rate 320 -> 168 (2026-07-05, CONFIRMED)

The general PvP engine's clock ran ~2x too fast: `rate=320` was fit to r6/r8
CASUALTIES, which are ~rate-invariant (winner stays A, defender fully wiped,
attacker losses move <8% across a 4x rate change), so the fit barely constrained
`rate` and the TURN COUNT fell out unconstrained (r006=17t, r008=22t).

Ground truth (Martin, from the Bradley Skill-3 "Tactical Assistance" counter,
cadence ~4 rounds/proc): r006 counter 8 -> ~32-35 rounds; r008 counter 10 ->
~40-43. Fit `rate=168` -> engine now gives r006=33t, r008=42t, winner still A
both. Casualties/winner unchanged (rate-invariant on these pre-T12 anchors), so
this ONLY corrects the clock. DEFAULT_PVP_PARAMS rate=168; regression check #4
now guards the turn count (r006 30-36, r008 38-45).

WHY IT MATTERED BEYOND COSMETICS: T12 skills fire in FIXED 5-turn windows. At the
too-fast 15-round clock those 5 turns were ~1/3 of the battle vs ~1/7 of a real
~35-round fight - OVER-weighting T12 ~2x and DISTORTING the winner (with T12 off
the winner is rate-stable at every rate; with T12 on it flips at low rate). The
duration fix therefore also corrects T12-battle outcomes. Example: the
60/30/10 1.5M scenario went from ~15 rounds to ~26.5 at rate 168.

CAVEAT: this calibrates DURATION (and thereby T12 weighting) on the r6/r8
anchors. The general path's absolute OUTCOME magnitude for near-even T12 matchups
is still uncalibrated (engine_meta calibrated=False) - trust direction, not the
exact win%. (Also removed a fragile simulate_pvp winner!='D' guard from
_kernel_box - it was rate-dependent and redundant vs the stat-range checks.)

## 7. Open items

- Encoding consistency (flagged in audit, not yet resolved): "X deals +N% to
  enemy Y" appears both as Friend-X DD-with-target and as Foe-Y DT; "deals
  +N% more damage" appears both as Attack and as Damage Dealt. Decide during
  formula derivation.
- Ahmose Viper Formation duration: tab N=1, wiki says 2 turns.
- Blank duration-unit (col O) on a few chance/turn-based rows (Greg S1/S2,
  Alonso S2, Natalia S1, Molly S1): engine defaults blank O to Turns —
  documented assumption. Legacy heroes' Skill 2/3 blanks stay (never
  activated per Rule 2, agreed with Martin).
- Next step agreed: Martin feeds "Scouted Stats" (includes pet buff, +20%
  item buff, widget, gears; EXCLUDES hero skills). Derive Base Stats by
  inverting the aggregation: Σstd = (Scouted − S)/(1 + S) with S = special
  pool, then subtract gear (and hero stat effect) so hero skills can be
  applied cleanly in battle. Component list per feed to be confirmed.
- T12 stats/skills: to be added when available.

## 8. Data fixes applied to the workbook

- 2026-07-02: Jesse→Jessie (5 cells); K18 0.25→0.6 (by Martin);
  Xura H201/H202 swap, Renee K279/K280 1.5→0.75, Fred K190:K192 sign
  (by Martin, verified); Patrick/Jessie Skill 2 intentionally absent
  (joiner-irrelevant).
- 2026-07-02: Flame Charge Against Marksman→ALL (by Martin, verified) —
  self-buff applies regardless of target.
- 2026-07-02: Volley ruled a literal second attack event in the engine
  (catalog special="extra_attack"); tab intentionally keeps the +10% DD
  Excel shorthand.
- 2026-07-02: Body of Light E18 0.0225→0.06 (by Martin, verified 0.06);
  Ahmose Viper Formation duration 1→2 Turns (by Martin, verified); M/O
  unit vocabulary Turns/Attacks/Strikes/Received populated by Martin.
- 2026-07-02: legacy heroes' skills rewritten by Martin to current game
  mechanics (game changed them since the sheet was first built): Logan,
  Flint, Natalia, Molly, Greg, Alonso reworked; Xura units filled.
  Recaptured and verified loading clean (506 effect rows).
