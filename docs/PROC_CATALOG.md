# PROC CATALOG — every chance-based battle mechanic (Stage 7 Phase A, 2026-07-21)

> The Type-2 inventory. One entry per chance-based (probabilistic) mechanic, plus the
> deterministic-cadence skills that serve as battle-clock instruments, plus the stacking rules
> that govern them. **No-fudge rule applies: the probabilities below come from catalogs/tooltips
> and are NEVER fit from outcomes.** Measurement statuses come from
> `wos_sim/formula_research/stage7a_telemetry.py` (re-runnable; exact binomial tests over the
> RAW_01..08 trigger telemetry — see `STAGE7A_REPORT.md` §3–4 for method and evidence).

## 0. Sources and source-of-truth corrections

| Source | What it holds | Caveat |
|---|---|---|
| `WoS battle simulator.xlsx` "Hero Skills" tab via `wos_sim/loader.py:load_skill_book()` (+ `_normalize_skill_effect` corrections loader.py:424–544, + 3 hardcoded Gen-15 heroes loader.py:312–401) | **The live hero-skill catalog the engine consumes**: 54 heroes / 541 effect rows (2026-07-21) | The Stage-7 spec's `wos_sim/skills.py` path does not exist; `wos_sim/predictor/skills.py` is only a resolution layer (its "51 heroes / 506 effects" comment is stale) |
| `wos_sim/troop_catalog.py` (`TROOP_SKILL_CATALOG`) | Troop-innate skills with raw `proc_chance`/`proc_amount`/`flat_offset`/`special` | Sole source for some magnitudes (see divergences) |
| `.claude/skills/wos-battlereport-ingestion/references/troop-passives.md` | Human-curated troop-passives reference | Omits Crystal Gunpowder I entirely |
| `docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json` (`skill_catalog` + `fire_crystal_troop_skill`) | FC unlock structure (FC3/5/8/10), per-tier×FC skill-state grid | Covers ONLY the 6 FC-gated families; its skill text was copied from troop-passives.md (not independent); Crystal Gunpowder I effect deliberately `null` ("not guessed") |
| `GAME_RULES.md` §3/§4/§5/§6 | Rule-level statements incl. the PROC-UNLOCK PRINCIPLE and FC account-gating | Body of Light row carries a dangling "see contradiction A" (defined nowhere) |
| `ENGINE_REBUILD/QA_REPORT.md:254–406` + commit `11d71e0` (2026-07-07) | The "proc-classifier audit": stacking/refresh/floor fixes | No standalone audit doc exists; substance = QA narrative + loader/engine fixes + regression tests |
| `docs/HERO_KITS.md` | Per-copy empirical hero kits (Gatot/Vulcanus/Gordon/Seo-yoon…) | All kits documented there are deterministic-cadence, none chance-based |

**Unlock gating (binding, GAME_RULES §6l + §6p):** troop procs gate by REAL unlock — T7 for
Ambusher/Volley, FC3/5/8/10 for the crystal families — and FC procs are **account-gated**: once an
account has FC, its FC skills proc for ALL troop tiers, even T1. Never assume a proc from class
alone. This is exactly the boundary the Stage-6.8 router enforces (tier ≤ 6, fc < 3 = proc-free).

## 1. Modeling classes and opportunity streams

Modeling classes: `damage-mult` (× on a packet) · `extra-attack` (a literal second attack event)
· `absorb` (flat damage offset per hit) · `defense-mult` (damage-taken ×) · `bypass-redirect`
(attack strikes the backline directly) · `crit` (chance of +100% DD on that attack) ·
`stat-proc` (temporary stat buff/debuff) · `next-attack` (packet on the next strike).

**Opportunity streams (Stage-7A measured concept):** a proc's count is Binomial(N, p) where N is
its stream size — `turns` (one roll per battle turn), `own_attack_events` (one roll per own
class-stack attack event, ≈ classes-alive × T), `own_class_strikes` (the owner's class only),
`received` (incoming attack events). The stream is a per-skill property and the RAW telemetry
DISCRIMINATES it (§4 of the report): buff-type chance skills measured so far roll **per turn**;
Gregory's crit and Rufus S3 roll **per attack event**; troop procs roll **per own-class strike**.

## 2. Troop-innate skills

### 2a. Chance procs (the Type-2 population)

| Skill | Class | Unlock | p | Effect | Modeling class | Stream (measured/assumed) | Law interaction | Status |
|---|---|---|---|---|---|---|---|---|
| Crystal Shield I | Inf | FC3 | 0.25 | offset 36 flat damage | absorb | received (assumed) | subtractive per-hit — same math family as the Gatot budget B | unmeasured (see fiery-gate hypothesis, report §4.6) |
| Crystal Shield II | Inf | FC5 | 0.375 | offset 36 flat damage | absorb | received (assumed) | as above | fiery-gate rows plausibly = its proc counter; identity OPEN |
| Ambusher | Lan | T7 | 0.20 | attack strikes Marksmen directly (whole-stack redirect, GAME_RULES §6c) | bypass-redirect | **own_class_strikes (MEASURED)** | composition-layer absorption EXCEPTION: damage skips the Inf wall (T12_03 ground truth: wall stood, MM still lost 66%) | **CONFIRMED: pooled 76 triggers / 14 sides, consistent with p=0.20 (max_p=1.0)** |
| Crystal Lance I | Lan | FC3 | 0.10 | double damage (+100%) | damage-mult | own_class_strikes (assumed) | ×2 on the A·L/(K·G) packet that turn | unmeasured-from-file |
| Crystal Lance II | Lan | FC5 | 0.15 | double damage (+100%) | damage-mult | own_class_strikes (assumed) | as above | "blue blade" rows rates 0.14–0.32/turn — candidate, identity OPEN |
| Incandescent Field I | Lan | FC8 | 0.10 | takes half damage | defense-mult | received (assumed) | ×0.5 on incoming packet | unmeasured-from-file |
| Incandescent Field II | Lan | FC10 | 0.15 | takes half damage | defense-mult | received (assumed) | as above | unmeasured-from-file |
| Volley | MM | T7 | 0.10 | strike twice (literal second attack event; re-rolls other procs — Martin-confirmed, troop_catalog.py comment) | extra-attack | **own_class_strikes (MEASURED)** | a second full packet; kills column = its direct damage | **consistent: 6 triggers / 2 sides at p=0.10** (weak N) |
| Crystal Gunpowder I | MM | FC3 | **0.20 per troop_catalog.py ONLY** | +50% damage | damage-mult | own_class_strikes (assumed) | ×1.5 packet | **CATALOG DIVERGENCE** — see §2c; unmeasured |
| Crystal Gunpowder II | MM | FC5 | 0.30 | +50% damage | damage-mult | own_class_strikes (assumed) | ×1.5 packet | "gun" rows rate ≈0.28–0.39/MM-strike across 7 sides — strong hypothesis match, identity OPEN |
| T12 Indomitable Wall | Inf | T12 | 0.6%/level | (per-level proc, SKILL_SOURCE_AUDIT token table) | defense | — | — | unmeasured |
| T12 Meridian Phalanx | Lan | T12 | 1%/level | (per-level proc) | — | — | — | unmeasured |
| T12 Starfire | MM | T12 | 0.5%/level | (per-level proc) | — | — | — | unmeasured |

### 2b. Gated always-on components (EV depends on a chance proc's uptime)

| Skill | Class | Unlock | Effect | Gate |
|---|---|---|---|---|
| Body of Light I / II | Inf | FC8 / FC10 | +4% / +6% Def always; **extra 10% / 15% damage reduction while Crystal Shield active** (percentages stated ONLY in troop_catalog.py; corroborated by GAME_RULES §5 which flags "see contradiction A" — dangling) | uptime = Crystal Shield's 25% / 37.5% (`gate_chance_for`, troop_catalog.py:240) |
| Flame Charge I / II | MM | FC8 / FC10 | +4% / +6% basic attack always; **extra 25% / 37.5% damage while Crystal Gunpowder active** (only in troop_catalog.py + GAME_RULES §5) | uptime = Gunpowder's chance |

### 2c. Known cross-source divergences (capture, never average)

1. **Crystal Gunpowder I:** troop-passives.md omits it; the TroopStats JSON asserts it exists at
   FC3 but explicitly declines an effect ("not guessed"); GAME_RULES §5 has no row;
   `troop_catalog.py:196–198` alone states **20% / +50%**. Uncorroborated → experiment E7-A.
2. **Body of Light / Flame Charge extras:** magnitudes (10/15%, 25/37.5%) exist only in
   troop_catalog.py (+GAME_RULES §5 with the unresolved "contradiction A" flag).
3. **JSON scope gap:** the TroopStats JSON has NO entries for Master Brawler / Bands of Steel /
   Charge / Ranged Strike / Ambusher / Volley (0 grep hits) — scope boundary, not conflict.
4. Deterministic counters (context): Master Brawler / Charge / Ranged Strike ×1.10 always-on are
   **already absorbed in the deterministic law's K-table** — they are not procs and not re-modeled.

## 3. Hero chance procs (workbook catalog, mechanic = Chance-based or p<1)

Pure chance rows (probability p, no cadence). Effects are per-proc (`amount_per_proc`); the
`amount` column is the workbook's EV fold. All from `load_skill_book()` 2026-07-21.

| Hero | Slot | p | Per-proc effect | Modeling class | Stream | Status (RAW telemetry) |
|---|---|---|---|---|---|---|
| Lloyd | S3 | 0.4 | Friend ALL +50% Lethality | stat-proc | **turns (MEASURED — attack-event streams REJECTED p≤3e-5)** | **CONFIRMED @ per-turn: 72/[190,205] rate 0.35–0.38, p=0.60** |
| Gisela | S2 | 0.4 | Friend ALL +50% Defense ("when hit") | stat-proc | **turns/own-strikes (attack-event streams REJECTED p≤1e-6)** — "when hit" tooltip ≠ per-hit roll | **CONFIRMED @ per-turn: 66/[174,180], p=0.59** |
| Gisela | S3 | 0.4 | Friend ALL −50% Damage Taken | stat-proc | as S2 | **CONFIRMED @ per-turn: 74/[174,180], p=0.76**; S2:S3 ratio test 66:74 vs 50:50 → p=0.55 ✓ |
| Gregory | S2 | 0.25 | crit: +100% DD on that attack | crit | **own/enemy attack events (per-TURN REJECTED p≈0)** | **CONFIRMED @ per-attack-event: 50/[120,215]; per-turn rate 0.58–0.63 impossible for p=0.25** |
| Rufus | S3 | 0.2 | Foe ALL −50% Lethality, 2 turns | stat-proc (debuff) | **own attack events (per-turn & own-strikes REJECTED p≈0)** — workbook says `every=1 Strikes`; telemetry says ATTACKS (any own class), matching Martin's report_001 note "per own-side attack" → **workbook trigger_unit encoding correction candidate** | **CONFIRMED @ per-attack-event: 57/[220,327]** |
| Freya | S2 | 0.5 | Friend Lancer +100% DD | damage-mult | turns/own-Lancer-strikes (own_attack_events rejected) | consistent: 20/[40,43] (1 report) |
| Flora | S1 | 0.5 | Foe ALL +50% Damage Taken | stat-proc (debuff) | see report §4.6 — its counter EXCEEDS 1/turn (46–65 over 42–47 turns) ⇒ multi-roll stream proven, but "Flora proc skill" row identity is ingestion-labeled, not slot-certain | rate evidence only; slot mapping OPEN |
| Gisela | S2/S3 pair | — | — | — | — | ratio test is the internal validation row above |
| Hector | S1 | 0.4 | −50% Damage Taken | defense-mult | unmeasured | not in RAW set |
| Hector | S3 | 0.25 | +200% DD (discrete proc post-audit) | damage-mult | unmeasured | not in RAW set |
| Mia | S1 | 0.5 | Target +50% Damage Taken (Target-receiver) | next-attack | unmeasured | RAW_02 Mia rows exist but icon-keyed, slot-uncertain — unmapped (honest) |
| Mia | S2 | 0.5 | Friend ALL +50% Attack | stat-proc | unmeasured | — |
| Mia | S3 | 0.4 | Friend ALL −50% Damage Taken | stat-proc | unmeasured | — |
| Reina | S2 | 0.2 | −100% Damage Taken | defense-mult | unmeasured | — |
| Reina | S3 | 0.25 | Friend Lancer +200% DD | damage-mult | unmeasured | — |
| Philly | S2 | 0.25 | +200% DD | damage-mult | unmeasured | — |
| Philly | S3 | 0.4 | −50% Damage Taken | defense-mult | unmeasured | — |
| Alonso | S1 | 0.4 | Friend ALL +50% Lethality | stat-proc | unmeasured | — |
| Alonso | S3 | 0.5 | Friend ALL +50% DD | damage-mult | unmeasured | — |
| Natalia | S1 | 0.4 | −50% Damage Taken (1 turn) | stat-proc | unmeasured | — |
| Molly | S1 | 0.4 | −50% Damage Taken (1 turn) | stat-proc | unmeasured | — |
| Molly | S2 | 0.5 | +50% DD | damage-mult | unmeasured | — |
| Gisela (garrison) etc. widgets | W | — | +15% stats (always-on) | stats | — | not procs |
| Magnus | S2 | 0.4 | Friend Inf +50% Defense | stat-proc | unmeasured | — |
| Wayne | S3 | 0.25 | crit +100% DD (Skills-only) | crit | expect attack-event stream (Gregory analogy) | unmeasured |
| Viveca | S2 | 0.2 | Friend MM +100% DD | damage-mult | unmeasured | — |
| Lynn | S1 | 0.4 | +50% DD shared 1-turn buff (post-audit rebuild) | stat-proc | unmeasured | — |
| Greg | S1 | 0.2 | +40% DD, 3 turns | hybrid (chance+duration) | unmeasured | — |
| Greg | S2 | 0.2 | Foe −50% DD, 2 turns | hybrid | unmeasured | refresh-not-stack canonical test hero |
| Alonso | S2 | 0.2 | Foe −50% DD, 2 turns | hybrid | unmeasured | — |

## 4. Deterministic-cadence hero skills (NOT chance — the clock instruments)

`probability=1.0` cadence rows; their counters clock battles (`n = floor(T/k)`, floor convention
Martin-confirmed in report_001 notes and triangulated for Vulcanus S3 2026-07-18).

| Hero | Slot | Cadence | Unit | Notes |
|---|---|---|---|---|
| Lloyd | S2 | every 3 | Turns | Iceflare Bomb — primary clock. **Display anomaly:** shows Triggered=1 in RAW_06/08 on BOTH sides (even with Lancers present) while counting 9/6 in RAW_01/03 — OPEN |
| Bradley | S3 | every 4 | Turns | Tactical Assistance — primary clock; fires even with zero Marksmen deployed (RAW_06/07/08) ⇒ hero cadence skills are troop-independent unless class-targeted |
| Flora | S3 | every 4 | Turns | clock (RAW_04/05) |
| Vulcanus | S3 | every 3 | Turns | −60% enemy Inf/Lan Def 3t + own-MM +60% Atk 1t; NanoMart fold conventions in stage-6 law |
| Vulcanus | S2 | every 5 (workbook) / every 6 per unit (research, 2026-07-19) | Strikes / per-unit | **DISPUTED cadence — never a clock.** Rally-scale counters (19–20 @ T=42–47) reject ALL single-stack readings; T12_01 prose fits "every 5 attacks PER TROOP TYPE" (k=5 per-type sum) while NanoMart triangulation pinned k=6 per unit → open discriminator (experiment E7-E) |
| Eleonora | S3 | every 5 | Strikes (Inf) | strikes-cadence VALIDATED exactly (RAW_02 n=2 pred 2; RAW_06 n=6 pred [6,7]; RAW_08 n=8 pred 8) |
| Fred | S3 | every 4 | Strikes (Lan) | validated (RAW_02 n=3 pred 3; RAW_07 death-clock) |
| Ligeia | S2, S3 | every 2 | Strikes (MM) | both slots same cadence; wiped-class counters = death clocks |
| Blanchette | S2 | every 3 | Strikes (MM) | **CONTRADICTED: RAW_07 n=18 ⇒ needs ≥54 turns of MM life, but T=[40,43] and S3 puts MM death at ~24–25 — impossible under k=3-own-strikes** (slot-row mapping or unit wrong) — experiment E7-F |
| Blanchette | S3 | every 2 | Strikes (MM) | death-clock consistent with itself |
| Renee | S1 | every 2 | Turns | not in RAW set |
| Hendrik | S2/S3 | every 4/3 | Turns | not in RAW set |
| Sonya | S3 | every 5 | Turns | not in RAW set |
| Gwen | S2 | every 5 | Attacks | note: ATTACKS unit exists in-catalog |
| Gordon | S1/S2/S3 | every 2 Strikes / 3 Turns / 4 Turns | — | HERO_KITS measured; class-locked aura |
| Gatot | S2 | once per attack | — | `triggers == rounds` exactly — the premier 1v1 clock |
| display rule | — | — | — | Per-attack continuous skills (freq=1, no chance) display **Triggered=1** (report_001 note 9) — count-1 rows are always uninformative |

## 5. Stacking / refresh / floor rules (2026-07-07 audit, still binding in the engine)

- Same-source reproc **refreshes** (merges min-start/max-expiry), never stacks — sole exception
  **Lynn S3** (`pvp_turn_engine.py:570–589`).
- Composed DD/DT multipliers **floored at −100%** (`_stack_view`, pvp_turn_engine.py:805–839).
- Temporary (chance/turn) stat buffs enter an **additive EV pool**; permanent stat skills compose
  multiplicatively with `mod_gamma` DR + `stat_floor` (assemble.py:87–116).
- **Duplicate joiner flags STACK additively** (dedup removed 2026-07-09 — guardrail comments in
  both paths; do not re-add).
- Captain: all 9 skills + 3 widgets; joiners: flag hero's S1 only, top-4 (mechanics.py:1–25).

## 6. Interaction map with the deterministic law (Phase-B hooks)

| Modeling class | Law term touched | Mechanism |
|---|---|---|
| damage-mult / crit | the per-turn damage `A_w·L_w/(K·G_w·G_l)` | multiply that turn's (or that attack-event's) packet |
| stat-proc (A/L up, D/H down…) | same, via the stat monomial | temporary exponent-1 fold for the proc duration |
| defense-mult / absorb | incoming packet / HP budget `D_l·H_l` | ×(1−r) per hit, or subtract flat offset per hit — the absorb family is mathematically the Gatot-budget shape (net = max(0, dmg − B)) |
| extra-attack (Volley) | adds a second packet that turn | re-rolls downstream procs; advances attack counters (cadence interaction!) |
| bypass-redirect (Ambusher, Cara-S3-like bursts) | the COMPOSITION layer | packet skips the Inf wall → backline pre-mortality while the wall stands (T12_03/T12_04 structural ground truth) |
| next-attack (Target rows) | one packet | routed to packets post-audit |

Stream semantics measured so far: per-turn (buff-type chance procs) · per-attack-event (crit,
Rufus S3) · per-own-class-strike (troop procs) · per-received (absorbs, assumed). Every Phase-B
roll must implement the measured stream, not the workbook's unit field, where they disagree.

## 7. Measurement-status roll-up (Phase A)

| Status | Entries |
|---|---|
| CONFIRMED (rate + stream) | Ambusher 0.20/strike; Lloyd S3 0.4/turn; Gisela S2 0.4/turn; Gisela S3 0.4/turn (+ ratio test); Gregory S2 0.25/attack-event; Rufus S3 0.2/attack-event |
| consistent (weak N) | Volley 0.10; Freya S2 0.5 |
| CONTRADICTED (finding, not refit) | Blanchette S2 cadence (impossible count); Vulcanus S2 single-stack cadence at rally scale |
| identity OPEN (rate evidence only) | "fiery gate" (Inf; candidate Crystal Shield per-received), "gun" (MM; candidate Gunpowder II 0.30/strike), "blue blade" (Lan; candidate Crystal Lance II), "Flora proc skill" (slot), Mia icon rows |
| unmeasurable-from-file | all other hero chance procs (not present in RAW telemetry); every FC troop proc count except via the OPEN icon rows; T12 anchors (prose-only trigger data) |
