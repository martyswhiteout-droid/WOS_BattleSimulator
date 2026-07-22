# STAGE 7 — PHASE A REPORT: Type-2 proc layer (inventory + telemetry + design)

**Builder:** Claude (Fable 5) · **Date:** 2026-07-21 · **Status:** COMPLETE (pending eval-7)
**Scope discipline:** analysis-only. New files only: `docs/PROC_CATALOG.md`,
`wos_sim/formula_research/stage7a_telemetry.py` + `stage7a_telemetry.json`, this report.
No engine/seam/table/corpus changes. Gate battery byte-identical to the 6.8 baseline (§7).

---

## 0. Mission and rules of engagement

Stages 1–6.8 completed the deterministic Type-1 program: the law
`turns = K(dealer,target) · D_l·H_l/(A_w·L_w) · G_w · G_l` (+ composition, Gatot kit, hero folds)
is exact in its validated domain and routed into `api.predict()` behind a conservative classifier
(tier ≤ 6, fc < 3, hero allowlist — i.e. **no proc unlocks**). Stage 7 extends prediction into proc
territory (Type-2) under the binding no-fudge rule (`ENGINE_REBUILD/ENGINE_CHANGE_CHECKLIST.md`):

- Proc probabilities come from tooltips/catalogs — **never** fit from outcomes.
- Type-2 validation is **by distribution only**: observed trigger counts vs exact binomial
  expectations; observed outcomes vs predicted distributions.
- A contradiction between catalog probability and observed counts is a **finding to flag**,
  never a number to refit.

Phase A (this report) is analysis-only: inventory (§2), telemetry mining of existing files
(§3–§4), Phase-B/C design (§5), experiment menu (§6), no-change gate (§7), triage (§8).

## 1. Source-of-truth corrections discovered during inventory

1. **The hero-skill catalog is not `wos_sim/skills.py`** (that path does not exist; the stage-7
   spec text is stale on this point). The live catalog is the **workbook** `WoS battle
   simulator.xlsx` ("Hero Skills" tab) parsed by `wos_sim/loader.py:load_skill_book()` (with
   per-hero corrections in `_normalize_skill_effect()`, loader.py:424–544, and 3 hardcoded Gen-15
   heroes, loader.py:312–401). `wos_sim/predictor/skills.py` is only a resolution layer. Live
   extraction 2026-07-21: **54 heroes, 541 effect rows** (the "51 heroes / 506 effects" comment at
   predictor/skills.py:29 is stale).
2. **The only structured skill-trigger telemetry on file** is the 8 RAW golden-anchor source files
   `wos_sim/data/reports/report_001..008.json` (`lead_heroes[].rows[].{skill, triggered, kills?,
   identified?}`). The T12 anchors (`wos_sim/data/pvp_t12_report_001..005.json`) carry trigger/kill
   numbers **only as free-text prose** in note fields (dumped verbatim by the script — §4.8).
   `Scenarios/normalized/*.json` strips all trigger data. `wos_sim/data/experiments/` (incl. the
   corpus) is deliberately Type-1: `"type": 2` matches = 0, non-empty `"procs"` arrays = 0.
3. **The "2026-07-07 proc-classifier audit"** has no standalone document; its substance is commit
   `11d71e0`: narrative `ENGINE_REBUILD/QA_REPORT.md:254–406`, data fixes
   `loader.py:_normalize_skill_effect`, engine fixes `pvp_turn_engine.py:570–589` (refresh-not-
   stack; Lynn S3 sole exception) and `:805–839` (DD/DT floor at −100%), regression tests
   `predictor/tests/test_pvp_turn_engine.py:242–980`.
4. **Cadence rows carry `probability = 1.0`** in the workbook — a certainty marker, not a chance
   gate. Only p < 1 makes a skill chance-based (the miner classifies on this rule).

## 2. Proc inventory — `docs/PROC_CATALOG.md`

The full catalog is `docs/PROC_CATALOG.md` (troop procs §2, hero chance procs §3, cadence/clock
instruments §4, stacking rules §5, law-interaction map §6, status roll-up §7). Summary counts:

- **Troop chance procs:** 10 (Crystal Shield I/II, Ambusher, Crystal Lance I/II, Incandescent
  Field I/II, Volley, Crystal Gunpowder I/II) + 2 gated always-on extras (Body of Light, Flame
  Charge) + 3 T12 per-level procs. FC procs are **account-gated** (fire at every troop tier).
- **Hero chance procs (workbook, p < 1):** 22 pure-chance rows across 16 heroes, + 5 hybrid
  (chance+duration) rows across 4 heroes, + 2 crit-class rows (Gregory S2, Wayne S3).
- **Deterministic-cadence hero skills:** the clock instruments (Lloyd S2, Bradley S3, Flora S3,
  Vulcanus S2/S3, Eleonora S3, Fred S3, Ligeia S2/S3, Blanchette S2/S3, + Gordon/Gatot/Renee/
  Hendrik/Sonya/Gwen out of the RAW set). NOT Type-2; listed because they clock the binomials.
- **Known catalog divergences** (captured, never averaged): Crystal Gunpowder I (20%/+50% exists
  ONLY in troop_catalog.py; troop-passives.md omits the skill; the TroopStats JSON explicitly
  declines to state an effect); Body of Light / Flame Charge extra-magnitudes (troop_catalog.py
  only, GAME_RULES §5 corroborates but flags a dangling "contradiction A").

## 3. Telemetry mining — methodology

Script: `wos_sim/formula_research/stage7a_telemetry.py` (stdlib-only; re-runnable; emits
`stage7a_telemetry.json` deterministically — double-emit byte-stable). **No probability or
cadence is hand-copied:** hero constants are read from `load_skill_book()` and troop constants
from `TROOP_SKILL_CATALOG` at runtime. The only curated content is the icon-string → troop-skill
mapping (each rule carries its evidence note) and the ratio-test pair list.

1. **Clocks.** Deterministic Turns-cadence skills (p=1.0, `every k Turns`) clock each battle:
   count n ⇒ T ∈ [k·n, k·n+k−1] under the **floor convention** (fires at k, 2k, …;
   Martin-confirmed in report_001's own notes; triangulated for Vulcanus S3 2026-07-18), or
   T ∈ [(n−1)k+1, nk] under the offset-1 convention. Both sides share T ⇒ bands intersect across
   the report. Strikes-cadence skills of classes that **survived** are secondary clocks under
   assumption **A1** (one attack event per class-stack per battle turn). Vulcanus S2 is
   **excluded from clocking** (disputed cadence — PROC_CATALOG §4).
2. **Display-1 rule.** `Triggered = 1` rows are uninformative (per-attack/always-on skills
   display 1 — report_001 note 9); n ≥ 2 required everywhere.
3. **Opportunity streams.** Each chance proc is tested against every defensible stream:
   `turns` (N ∈ T-band) · `own_attack_events` (N ∈ [max(T, alive_end·T), deployed·T]) ·
   `enemy_attack_events` (same from the enemy side = the "received" stream) ·
   `own_class_strikes` (hero's class; = T-band if the class survived, else [n, T_hi] flagged).
   Deployed/alive-end per class are aggregated from the participants' survivor rows.
4. **Statistics.** Exact-test two-sided binomial p-value (minimum-likelihood method) **scanned
   over every integer N in the stream interval**, taking the maximum (= the most favourable
   defensible opportunity count); Clopper-Pearson 95% CIs at interval endpoints; per-report and
   pooled (counts and interval endpoints summed). Verdicts, thresholds fixed a priori:
   `consistent` max_p ≥ 0.05 · `rejected` max_p < 0.01 over the whole interval · else `marginal`.
   All streams rejected ⇒ **CONTRADICTED** (finding). Exactly one surviving stream ⇒
   **stream-identified**.
5. **Branch discipline.** The entire test battery is recomputed under the offset-1 cadence
   convention; pooled verdict flips are reported (§4.7: there are none). T-free **conditional
   ratio tests** (X₁ | X₁+X₂ ~ Bin(m, p₁/(p₁+p₂))) validate same-hero pairs independently of T.
6. **Quarantine.** `identified: false` icon rows never enter the identified tests; they get a
   rate-analysis table (hypothesis generation only). T12 prose numbers are dumped verbatim,
   never fed to the binomial machinery.

## 4. Telemetry mining — results

All numbers: `stage7a_telemetry.py` output (`stage7a_telemetry.json`). Reports RAW_01..08 =
`wos_sim/data/reports/report_001..008.json`.

### 4.1 Battle clocks

| rid | T floor-conv | T offset-conv | source (clock rows) |
|---|---|---|---|
| RAW_01 | **[28,29]** | [25,27] | Lloyd S2 k3 n9 ∩ Bradley S3 k4 n7 (matches Martin's note "~28-29 turns") |
| RAW_02 | [12,14] (strikes-A1) | — | Eleonora S3 k5 n2 ∩ Fred S3 k4 n3 (no Turns clock in this report) |
| RAW_03 | **[18,20]** (∩ strikes → [20,20]) | [16,18] | Lloyd S2 k3 n6; Ligeia k2 n10 alive-end |
| RAW_04 | **[42,43]** | [40,40] | Flora S3 k4 n10 ×2 ∩ Vulcanus S3 k3 n14 |
| RAW_05 | **[45,47]** | [43,44] | Flora S3 k4 n11 ×2 ∩ Vulcanus S3 k3 n15 |
| RAW_06 | **[32,35]** | [29,32] | Bradley S3 k4 n8 |
| RAW_07 | **[40,43]** | [37,40] | Bradley S3 k4 n10 |
| RAW_08 | **[40,43]** | [37,40] | Bradley S3 k4 n10 |

### 4.2 Headline: the game's proc opportunity model is SKILL-SPECIFIC (and measured)

Pooled exact-binomial verdicts (across all report-sides; p_cat from the live catalog):

| Skill | p_cat | pooled n / N-interval | per-turn stream | attack-event streams | verdict |
|---|---|---|---|---|---|
| **Lloyd S3** | 0.4 | 72 / [190,205] | rate 0.35–0.38, **p=0.60 ✓** | REJECTED (p ≤ 2.9e-5) | **rolls once per TURN** |
| **Gisela S2** | 0.4 | 66 / [174,180] | **p=0.59 ✓** | REJECTED (p ≤ 1e-6) | per TURN — despite the "when hit" tooltip (a per-incoming-hit roll is rejected) |
| **Gisela S3** | 0.4 | 74 / [174,180] | **p=0.76 ✓** | REJECTED (p ≤ 1.1e-4) | per TURN |
| **Gregory S2 (crit)** | 0.25 | 50 / [120,215] | REJECTED (p≈0; per-turn rate 0.58–0.63) | **p=1.0 ✓** | **rolls per ATTACK EVENT** |
| **Rufus S3** | 0.2 | 57 / [220,327] | REJECTED (p≈0; per-turn rate 0.42–0.46) | **p=1.0 ✓** | **per ATTACK EVENT** — the workbook's `every=1 Strikes` (own class only) is ALSO rejected; matches Martin's report_001 note "20% per own-side attack" ⇒ workbook trigger-unit encoding correction candidate |
| Freya S2 | 0.5 | 20 / [40,43] | ✓ (0.47–0.50) | own-events rejected | per turn or per own-Lancer-strike (degenerate — Lancers survived) |
| **Ambusher (troop)** | 0.2 | **76 / [229,470] (14 sides)** | — | — | **CONFIRMED at 0.20 per own-Lancer-strike** (max_p=1.0) |
| Volley (troop) | 0.1 | 6 / [15,43] (2 sides) | — | — | consistent (max_p=0.44; weak N) |

The per-turn/per-attack-event split is not noise: the rejections are at rate ratios of 1.6–3×
with p < 10⁻³ in every case, in both cadence conventions. **Phase-B rolls must implement the
measured stream per skill, not the workbook's unit column, where they disagree.**

### 4.3 Internal validation

- **Gisela S2:S3 ratio test** (T-free): pooled 66:74 vs expected 50:50 (both p=0.4) → p=0.55 ✓.
  Per-report: 0.19 / 1.0 / 0.86 / 0.74 — no report contradicts the equal-probability catalog.
- **Strikes-cadence self-checks (validates A1):** Eleonora S3 (k5): RAW_02 n=2 = pred 2; RAW_06
  n=6 ∈ pred [6,7]; RAW_08 n=8 = pred 8. Fred S3 (k4): RAW_02 n=3 = pred 3. Ligeia (k2): RAW_03
  n=10 ∈ pred [9,10]. The one-attack-event-per-class-per-turn assumption holds exactly.
- **Convention robustness:** recomputing the entire pooled battery under the offset-1 convention
  produces **zero verdict flips**.

### 4.4 Contradictions and anomalies (findings — flagged, never refit)

1. **Blanchette S2 cadence IMPOSSIBLE under catalog:** RAW_07 enemy n=18 at k=3-own-Strikes
   requires ≥ 54 turns of Marksman life; T=[40,43] and Blanchette S3 (k=2, n=12) puts MM death at
   ~turn 24–25. Either the S2 cadence/unit differs from the workbook or the ingestion's icon→slot
   mapping swapped rows (T12_03 notes flag "slot mapping partly uncertain" for this hero family).
   One-battle discriminator: E7-F.
2. **Vulcanus S2 at rally scale:** observed 19 (RAW_04) / 20 (RAW_05) vs single-stack predictions
   7–9 (both k=5 workbook and k=6 research) — all single-stack readings rejected. T12_01 prose
   (Martin, 07-05) fits "every 5 attacks PER TROOP TYPE" (k=5 summed over types: 2+2+3=7 ✓ for
   that battle), while the NanoMart triangulation (07-19) pinned k=6 per unit (e.g. 2u@35→10;
   k=5 would give 14). Both cannot hold with one global k — the "unit" semantics at rally scale
   are OPEN. One-battle discriminator: E7-E.
3. **Lloyd S2 display anomaly:** shows Triggered=1 in RAW_06/08 on BOTH sides (Lancers present on
   the enemy side) while counting 9/6 in RAW_01/03. Excluded by the display-1 rule; cause OPEN
   (possibly receiver-class-gated display, possibly ingestion).
4. **Gisela "when hit" tooltip ≠ mechanics:** the per-incoming-hit stream is rejected at p ≤ 1e-6
   pooled; the roll is per turn. Tooltip wording is not evidence of stream.

### 4.5 By-product: per-class death-turn estimates (Phase-B validation targets)

From strikes-cadence counters of wiped classes (floor conv): RAW_03 enemy MM ~[20,20];
RAW_04 friendly MM ~[20,21]; RAW_05 friendly MM ~[6,7]; RAW_06 enemy Inf ~[25,29]; RAW_07 enemy
Lancer ~[40,43], enemy MM ~[24,25] (from S3; S2 impossible — §4.4.1); RAW_08 enemy Inf ~[35,39].
These are exactly the per-class kill-clock observables the Phase-B distribution gate can score.

### 4.6 Unidentified icon rows — rate analysis (hypothesis generation ONLY)

- **"fiery gate" (Infantry icon; every FC10 side):** counts 22–66; implied per-turn rates
  0.63–1.83 — **exceeding 1/turn in 4 of 12 sides**, proving a multi-roll stream. Most consistent
  with **Crystal Shield II (0.375) per incoming attack event** (predicted 0.375×(2–3 enemy
  classes) = 0.75–1.13/turn), but dispersion is wider than that model — identity OPEN (E7-D).
- **"gun" (Marksman icon):** rates per MM-strike 0.28–0.39 across 7 sides — strong match to
  **Crystal Gunpowder II (0.30/strike)**; kills attached (direct +50% packets). Identity OPEN.
- **"blue blade" (Lancer icon):** rates 0.14–0.32/turn — Crystal Lance II (0.15/strike) fits some
  sides; RAW_01's 0.31 does not — OPEN (possibly two skills sharing an icon row).
- **"Flora proc skill":** counts 46–65 over 42–47 turns (>1/turn) — proves multi-roll; consistent
  with Flora S1 (0.5) on an attack-event stream, but the row is ingestion-labeled, slot-uncertain.
- **Mia rows (RAW_02):** icon-keyed, slot-uncertain — quarantined.

### 4.7 Kills columns (Phase-B packet-EV inputs)

42 rows carry direct-damage kill attributions (script table "Kills-column rows"): e.g. Volley
4.4k–21.9k kills/proc, Ambusher 0.7k–7.7k/proc, Gregory S2 crits 1.6k–3.6k/proc, Ligeia S2
2.9k–6.3k/proc, Vulcanus S2 2.8k–3.0k/proc. Per-proc magnitudes scale with stack sizes/stats —
these become the packet-size validation data once Phase B computes law-based packets.
T12_04/05 prose adds side-level totals: skill-attributed kills ≈ 7% (T12_04) and ≈ 16–20%
(T12_05) of all casualties — the proc layer is a second-order correction on the law, not the
first-order engine.

### 4.8 T12 anchors

No structured trigger data exists (recursive key scan: zero `trigger` keys). The script dumps the
prose fields verbatim (JSON `t12_prose`): Martin's reconstructions there used the older offset
convention ("9x → (9−1)·3+1 = 25") and the "every 5 attacks per troop type" Vulcanus S2 reading —
both superseded-or-disputed by later corpus work; kept as documentary evidence only.

## 5. Phase-B design — the stochastic layer ON the deterministic law

**Architecture (no new constants; every parameter is catalog- or measurement-sourced):**

1. **Base process:** per direction, per turn, the Stage-6 law provides the deterministic damage
   clock `d = A_w·L_w / (K(dealer,target) · G_w · G_l)` in HP-units/turn against `HP = D_l·H_l`
   (composition layer: absorption order, tank ratios, mop-up cadence; kits: budget/S-curve).
   Type-1 battles remain the p=1 degenerate case — byte-identical outputs.
2. **Proc rolls layered on the clock:** each active proc rolls on its **measured stream**:
   per-turn (Lloyd-S3-class buffs), per-attack-event (crit/Rufus-S3 class; one event per alive
   class-stack per turn — A1, validated §4.3), per-own-class-strike (troop procs), per-received
   (absorbs). Effects apply as PROC_CATALOG §6 maps them: damage-mult/crit multiply that packet;
   stat-procs fold into the monomial for their duration; defense-mult/absorb reduce incoming
   (absorb = the Gatot-budget math family, max(0, dmg − offset)); Volley emits a second packet
   that re-rolls downstream procs and advances attack counters; **Ambusher/bypass redirects the
   packet past the Inf wall into the composition layer** (the mechanism the old engine could not
   reproduce — T12_02 engine_finding; T12_03/04 "wall stood yet MM died" ground truths).
3. **Stacking semantics:** the audited rules verbatim (refresh-not-stack, Lynn S3 exception,
   DD/DT floor −100%, duplicate joiners stack) — already engine-tested; reuse, don't reinvent.
4. **CRN seeding:** seed derived per (battle_seed, side, skill_id, stream_index) so runs are
   replayable and A/B comparisons variance-reduced — same contract as `ENGINE_INTERFACE.md`
   (non-mutating, CRN-seeded seam).
5. **Outputs:** distributions replace point clocks — per-class kill-turn bands, survivor
   distributions, win probability = fraction of draws; `coin_flip`/honesty semantics preserved
   (near-even distributions stay hedged; that is design, not a bug).
6. **Validation gates (distribution-only, no refitting):**
   - **G-T1:** trigger-count replication — simulated per-skill trigger counts must cover the
     RAW_01..08 observed counts within central 95% intervals (the §4 tables are the gate data).
   - **G-T2:** per-class death turns within simulated bands vs §4.5.
   - **G-T3:** winners — observed winner inside the simulated distribution (no golden-anchor
     regression; backtest G12 stays mandatory).
   - **G-T4:** the Vulcanus-dealer −6.5% systematic (stage-5 fold family) must EMERGE from
     discrete S2/S3 rolls (distribution covering the fold) rather than be tuned.
   - **G-T5:** proc-gated non-Inf rows (no-hero MM/Lan cannot beat Gatot-Inf — Martin-confirmed)
     stay losses in ≥ 99% of draws.
7. **Branching:** where mechanics remain disputed (Vulcanus S2 rally semantics, Blanchette S2,
   Crystal Gunpowder I, fiery-gate identity), Phase B implements the branches behind explicit
   flags and the E7 experiments decide — never a fit.

**Phase-C router-widening criteria (per gate, in order):**
- **fc ≥ 3 per class** opens when that class's FC procs are fully parameterized (tooltip p +
  effect + stream) AND G-T1/G-T3 pass on every file row involving them (E7-A/-D close the two
  open identities first).
- **tier 7–10** opens when Ambusher/Volley packet sizes validate (rate already CONFIRMED;
  packets via kills columns + E7-B/-C) and bypass-composition reproduces the T12_03/04
  structural truths distributionally.
- **Hero allowlist** widens per-hero once its kit folds are implemented and its RAW-measured
  stream/probability validates: first wave = the six measured heroes (Lloyd, Gisela, Gregory,
  Rufus, Freya + the cadence-deterministic Bradley/Flora/Eleonora/Fred/Ligeia/Blanchette-S3).
- **T11/T12 + Gen-14 kits** (the golden-anchor domain) last — requires the T12 per-level procs
  and remains gated by G12.

## 6. Experiment menu for Martin (decisive reads only)

Power/CI numbers from the script's exact-binomial power grid (§ "Binomial power grid"). All
battles use the standard capture (full report + Skill Details panel, per the ingestion skill);
"clocked" = a Gatot-led Infantry tank on the far side (S2 triggers == rounds) or a Vulcanus/
Gordon cadence clock.

| ID | Setup | Battles | Capture / read | Predicted readings (discriminating) | Power |
|---|---|---|---|---|---|
| **E7-A** | FC3-account Marksman stack (any tier — FC procs are account-gated) vs aura'd Gatot-Inf tank, long clocked 1v1 (aim T ≈ 200) | 1 | "gun"-row trigger count ÷ rounds | Crystal Gunpowder I: absent → ~0; troop_catalog 20% → ~0.20·T; if it's really the II value → 0.30·T | 20-vs-30: power 0.91 @ N=200 (CI ±0.065) |
| **E7-B** | same battle | — | Volley-row count ÷ rounds; kills ÷ count | 0.10·T; per-proc kills = one law packet | 10-vs-20: 0.98 @ N=200 |
| **E7-C** | T7+ Lancers attacking an Inf+MM defender (backline present), clocked, T ≈ 100 | 1 | Ambusher count ÷ Lancer attacks; kills/proc vs law packet | 0.20·T; packet = full-stack A·L/(K·G) vs MM (whole-stack redirect, not a slice) | 20-vs-10: 0.80 @ N=100 (CI ±0.127) |
| **E7-D** | FC-account Infantry defender vs a single-class dealer (received = exactly 1 event/turn), clocked, T ≈ 200 | 1 | "fiery gate"-row count ÷ rounds | Crystal Shield II per-received → 0.375·T; per-turn-cap model → ≤ 1.0·T with different shape; absent → 0 | 25-vs-37.5: 0.97 @ N=200 |
| **E7-E** | Vulcanus-led side deploying ALL THREE classes (nonzero Inf+Lan+MM) vs Gatot tank, T ≈ 30 known | 1 | Vulcanus S2 counter | per-troop-type k=5 → 3·floor(T/5)=18; per-unit k=6 → 15; single-stack → 5–6 | integer separation ≥ 3 — one battle decisive |
| **E7-F** | Blanchette-led MM 1v1 vs Gatot tank, T ≈ 30–60 known | 1 | S2 and S3 counters | k=3-strikes → floor(T/3); k=2 → floor(T/2); chance-based → non-integer-band rate | deterministic read |
| **E7-G** | Rufus-led side twice at matched T ≈ 40: once 1 class deployed, once 3 classes | 2 | Rufus S3 counter ratio | per-attack-event → count scales ×3 (≈8 → ≈24); per-turn → equal | ≈4σ separation; also grid row "per-turn vs 3×-stream": power 1.0 @ N=45 |
| E7-H (low) | Crystal Lance / Incandescent ladders | — | — | 10-vs-15% needs N≈800 for power 0.99 | deprioritize (long battles required) |

## 7. No-change gate (byte-identical to the 6.8 baseline)

Baseline captured at session start (before any new file was written), re-run at session end.

| Gate | 6.8 baseline (session-start run) | After Phase A | Verdict |
|---|---|---|---|
| `py -m pytest wos_sim/predictor/tests/ -q` | 152 passed, 8 skipped, 2 xfailed, 23 subtests | 152 passed, 8 skipped, 2 xfailed, 23 subtests | identical counts |
| `py -m wos_sim.backtest` | PASS, winners 7/13 (baseline 7) | — | **stdout BYTE-IDENTICAL** (`diff` clean) |
| `py -m wos_sim.formula_research.stage6_validate` | 11 PASS + the 2 known deliberate FAILs (D6 factorized-band, W6) | — | **stdout BYTE-IDENTICAL** (`diff` clean) |
| `py -m pytest wos_sim/formula_research/ -q` | 24 passed | 24 passed | identical |

`stage7a_telemetry.json` double-emit: md5 `3224601f425b5460085ddad78f4521cf` on consecutive runs
(byte-stable). Working tree: the only additions are the four new analysis files
(`docs/PROC_CATALOG.md`, `STAGE7A_REPORT.md`, `stage7a_telemetry.py`, `stage7a_telemetry.json`);
every pre-existing tracked file is untouched by this stage.

## 8. Parked-physics triage

| # | Item | Class | Disposition |
|---|---|---|---|
| 1 | **151127 inert-Gatot-dealer slowdown** (~4× slow own clock; screenshot-verified real) | needs-experiment (low priority) | Production-clean per the E-battery (aura'd/maxed dealers follow the plain law exactly; Martin's policy = maxed heroes). One battle if ever needed: inert-Gatot-led dealer vs naked target at a second tier to test scaling. Not Phase-B-blocking. |
| 2 | **LabRat Lan-vs-MM cross-cell** (K(Lan→MM) instrument spread 126.2/149.8/176) | needs-analysis → then one battle | Re-derive each instrument's panel folds first; if the spread survives, one zero-panel Lan-vs-MM Gatot-clocked battle pins the cell. |
| 3 | **NanoMart MM→Inf +26% residual** (post-OCR-correction row) | needs-experiment | One re-capture of the NanoMart MM→Inf cell at known panels; +26% on a single row is below multi-point trust (OCR rule). |
| 4 | **Royal Legion decontamination** (S3 level fold entangled with B) | needs-experiment | Differing-LEVEL Gatot instrument: same copy before/after an S3 level-up (or a third copy), one budget-edge battle per level. |
| 5 | **K(Lan→Inf) T3-vs-T6 tension** (90.4 vs ~111; ordinary-vs-FC1 caveat) | needs-experiment | One battle: T3 ordinary vs T3 FC1 Lancers into the same Gatot-Inf target — separates base-table family from tier law. |
| 6 | **Alpaca-FC1T1 ×1.17 family** (rising kit-level M-bounds, 6.5 reconciliation) | needs-analysis | Reconciliation pass over the Codex-v2/v3 fold-miss rows before any table change; single-constant M already ruled unsupported. |
| 7 | **Multicount clock regime** (3 remaining W6 WRONG rows) | needs-analysis | The 6.6 √N racing fixed most; the residual 3 are named in stage6_validate W6 — row-level analysis first. |
| 8 | **n>1 S-curve pooling order** | closed-by-pressure-test | Per-dealer-suppress-then-√N confirmed (3×Vulc-MM @4, blind ceil-exact). Corpus JSONs for the pressure battles still pending ingestion (Martin verbal 07-17). |
| 9 | **Composition generalization** (beyond tank+backline single-class stacks) | needs-experiment (matrix) | Phase-C blocker for multi-class routing, not a Phase-B blocker. |
| 10 | **Vulcanus-dealer −6.5% systematic** | Phase-B-blocked | This IS a Phase-B validation target (gate G-T4): the fold should emerge from discrete S2/S3 rolls. |
| 11 | **Vulcanus S2 rally-scale semantics** (new, §4.4.2) | needs-experiment | E7-E (one battle). |
| 12 | **Blanchette S2 cadence contradiction** (new, §4.4.1) | needs-experiment | E7-F (one battle). |
| 13 | **Rufus S3 trigger-unit workbook encoding** (new, §4.2) | needs-analysis (Martin decision) | Telemetry says ATTACKS, workbook says Strikes. Workbook is Martin's artifact — propose the correction, do not edit. |
| 14 | **"fiery gate"/"gun"/"blue blade" icon identities** (new, §4.6) | needs-experiment | E7-A/-D resolve the two that matter most. |

---

*Deliverables: `docs/PROC_CATALOG.md` · `stage7a_telemetry.py` · `stage7a_telemetry.json` · this
report. Next: `/run-stage eval-7` (independent verification), then Phase B behind its own spec.*

---

## Eval-7 (evaluator window, 2026-07-21): ACCEPT

1. **Inventory sources independently verified:** `wos_sim/skills.py` confirmed
   absent (the spec was stale; the builder's workbook-via-`load_skill_book()`
   correction is right); live extraction reproduces **54 heroes / 541 effect
   rows EXACTLY**; the Crystal Gunpowder I divergence is real
   (`troop_catalog.py` carries 20%/+50%; troop-passives.md omits it); the
   22+5+2 skill-level accounting is consistent with the 75 raw p<1 effect
   rows (multi-effect skills share one probability).
2. **Binomial machinery hand-reproduced** with the evaluator's OWN exact-test
   implementation (minimum-likelihood two-sided, N-interval scan) — never
   calling the builder's script: Lloyd S3 0.604 (claim 0.60), Gisela S2/S3
   0.589/0.761 (0.59/0.76), Gregory S2 and Rufus S3 max_p=1.000 on the
   attack-event stream, Ambusher max_p=1.000 at 76/[229,470]; the rejection
   sides reproduce (Lloyd S3 at a 2× event stream p=1.6e-18; Gregory
   per-turn p=6.3e-11); the Gisela ratio test 0.554 (claim 0.55). **All
   match to the digit.**
3. **Experiment menu verified:** E7-E's discriminating integers (18 / 15 /
   5–6 at T=30) and the 20%-vs-30% power figure (0.907 vs claimed 0.91)
   recompute exactly.
4. **No-change gate re-confirmed:** predictor suite 152/8/2, backtest PASS
   7/13, stage6_validate 151/15/1/3 over 243/243, formula_research 24 —
   all identical to the 6.8 baseline; `stage7a_telemetry.json` re-emit
   byte-stable (md5 3224601f… unchanged).

**Verdict: ACCEPT.** The headline finding — proc opportunity streams are
SKILL-SPECIFIC and measurable from existing files (per-TURN vs
per-ATTACK-EVENT split at p<10⁻³ in both cadence conventions) — is the
Phase-B design's load-bearing input and survived independent recomputation.
Phase B may proceed behind its own spec; the E7 menu (E7-E/F/G first: one
battle each, integer-separated reads) is ready for Martin.
