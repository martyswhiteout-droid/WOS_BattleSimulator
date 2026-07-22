# QA BRIEF — independent validation of the WoS deterministic battle law (for Codex)

You are the INDEPENDENT QA for a reverse-engineered deterministic battle formula.
Your job: re-implement the law yourself from the constants + spec below (do NOT
import or call the project's predictor code — independence is the point), run it
against EVERY Type-1 battle report on file, and report the margin of error.
**Acceptance bar: ≤10% margin (or exact-integer-turn hit) on every row inside the
law's declared domain.** Out-of-domain rows are scored too, but tabled separately
against their declared bands.

## Hard rules (violating any = failed QA)
1. Never fabricate a number. Every figure in your report must come from code you
   wrote and ran in this session. Show the per-row table.
2. Do not modify ANY repo file. Read-only, plus your own new script(s) in
   `wos_sim/formula_research/qa_codex/` (new folder).
3. If a row's inputs look physically impossible or internally inconsistent, FLAG
   it (id + field + why) instead of "fixing" it — OCR errors are a known hazard.
4. Report failures as failures. A row >10% in-domain is a FINDING, not something
   to re-tune around. There are NO tunable constants in this exercise.

## Data (single source of truth)
- **Corpus:** `wos_sim/data/experiments/_corpus/TYPE1_CORPUS.json` — 232 rows,
  every battle normalized, OCR corrections pre-applied. Load rows from here ONLY
  (never re-parse raw folders; never use `NANOMART_EXPERIMENT_LEDGER.md` raw).
  Each row: attacker/defender → classes[] (cls, tier, fc, count, per-class panel
  pct, precomputed eff stats), hero_skills (with trigger counts), outcome
  (winner, turns or turns_range), determinism class, flags.
- **Constants:** `wos_sim/formula_research/stage6_tables.json` — the frozen
  K-table, G_w/G_l class-keyed tables (with per-cell status: measured /
  interpolated / bounded / extrapolated / factorized / fallback), the gatot_kit
  block, and policy blocks. Use these numbers verbatim; implement the arithmetic
  yourself.
- **Base stats (if you recompute eff):** `docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json`
  ONLY. Never use `wos_sim/troop_catalog.py` (legacy engine table, diverges T2+).

## The law you are implementing

Effective stats per unit (class c, tier τ, FC f; panels are per-battle):
    X_eff = X_base(c, τ, f) · (1 + panel_X/100),   X ∈ {A, D, L, H}

Per-unit kill time, dealer d → target t (1v1 core):
    turns(d→t) = ceil[ K(c_d, c_t) · (D_t·H_t) / (A_d·L_d)
                       · G_w(c_d, τ_d) · G_l(c_t, τ_t) / √N_d · S_kit ]
- HP pool = D_t · H_t (product). Deaths land on INTEGER turns → point
  prediction = ceil(t); a row passes if ceil(pred) equals the observed turn, or
  pred falls inside the observed [lo, hi] band, or |pred/obs − 1| ≤ 10%.
- Global cap: 1500 turns (if kill time > 1500 → stalemate; attacker "defeat" if
  any defender remains).
- Two-sided race: compute both sides' kill times; the shorter wins; that side's
  time is the battle length. Both capped → stalemate.
- √N_d: dealer stack count (open-field). Counter passives are INSIDE K — never
  apply a separate ±10%.

Deterministic hero folds (apply only when the hero is present in the row):
- Seo-yoon S1: dealer Attack ×1.05/1.10/1.15 (level 1/2/3).
- Vulcanus (on a side): S1 → enemy Attack ×0.96; S2 → every 6th attack ×1.2
  (average fold ×31/30); S3 → enemy Infantry/Lancer Defense ×0.88 (continuous).
- Gordon/Elif/Ursar on the TARGET side: their debuffs slow the DEALER by ~2–5%
  — do not model; expect those rows a few % high and say so.
- Gatot on a side: S1/S2 are own-side defensive; his clock (S2 triggers = rounds)
  is metadata, not a stat effect — EXCEPT the kit gate below.

Gatot-kit gate (ONLY when the dying target is a Gatot-led Infantry and the
dealer is non-Infantry) — constants in the `gatot_kit` block:
- Hero-less dealer(s): budget absorb, LINEAR pooling:
  net = max(0, Σ_d r_d − B), r_d = (A_d·L_d)/K(c_d, Infantry); capped iff
  net·1500 < D_t·H_t; else turns = ceil(pool/net). B is DEFENDER-SPECIFIC
  (measured: Mueller 201.95, FarSeer 30.15); any other Gatot defender → flag
  `gatot_gate_unmodeled`, exclude from the ≤10% verdict.
- Hero-led (Vulcanus) dealer(s): per-dealer suppression S(d) = 1 + 10.727·e^(−d/16.893)
  applied to each dealer's Vulcanus-folded rate, then √N pooling.
  (Verified blind: 3× T6-MM kill in ceil(3.85) = 4 = observed.)

Composition (multi-unit mixed armies) — validate in ANCHOR mode only:
- Absorption order Infantry → Lancer → Marksman (Infantry tanks first).
- Sequential tanking vs a fixed defender, ratios of the solo tank time t_solo:
  first tank 0.4231·t_solo, middle tanks 0.6923·t_solo each, last 0.7308·t_solo;
  deaths at ceil(prev_death + duration).
- Backline mop-up: unit j dies at front_death + max(ceil(4j/3), latency_class)
  (latency: MM 2, Lancer 3 vs the measured defender).
- These constants are measured against ONE defender config (the Alpaca
  Inf+MM duo, Gatot+Vulcanus) — score composition rows from that regime; other
  defenders are out-of-domain (flag, don't fail).

## Domain map (score everything; verdict only on in-domain)

IN-DOMAIN (the ≤10% bar applies):
- All same-class and cross-class exact-turn 1v1 rows (Lab Rat, MuellerAlpaca,
  MuellerAlpaca_Gatot_v4/v5, FarSeerGatot_v3, ENIF, Gordon battery, Elif/Ursar).
- Beast ladder rows (per-kill = turns/18, victories only).
- NanoMart T1 rows with Seo-yoon-dealer (fold ×1.15·×0.96).
- Composition rows from the measured regime (anchor mode).
- Gatot-kit rows covered by the measured B defenders or the S-curve.

OUT-OF-DOMAIN (separate table, scored against their DECLARED bands):
- Factorized K cells (Lan→Inf, Lan→Lan, MM→Lan): declared ±15%.
- Vulcanus-DEALER rows (its side deals the kill): declared −6.5% systematic.
- Non-Inf dealers vs Gatot-Inf in NanoMart (proc/kit contaminated): declared
  +19..+51% band.
- Rows flagged `gatot_gate_unmodeled`, `base_mismatch`-driven T3 threshold
  tension, capped stalemates (report capped/not-capped correctness instead of %).
- NanoMart multi-count/survivor rows (√N-regime evidence; skip % scoring,
  check winner only). Legacy `exp*` rows (no numeric inputs): skip, list.

## Required output
1. `qa_results.csv` (or .md): one row per battle — id, matchup, N-vs-N, observed
   (turns or band), predicted, %err (or ceil-exact / band-hit / capped-correct),
   domain class, PASS/FAIL, flags.
2. Summary by instrument bucket (median |err|, max, pass rate) and by domain
   class.
3. The verdict: does the IN-DOMAIN set meet ≤10% on every row? List every
   in-domain row that misses, with your diagnosis (arithmetic shown).
4. A discrepancy section: anywhere your independent implementation disagrees
   with the repo's `stage6_validate.py` bucket results (run it once at the END,
   after your own numbers are locked, purely as a cross-check) — disagreements
   are findings about THEIR code or YOUR code; investigate which.
5. Any OCR-suspect rows you flagged (id + field + reason).

## Known traps (each has burned someone already)
- NanoMart ledger-derived rows: effective stats in older artifacts used a wrong
  ADDITIVE base; the corpus rows are corrected — trust corpus eff, or recompute
  from docs/TroopStats.
- Panels are PER-BATTLE (alliance membership shifts them, e.g. +23pp A/D
  +10pp L/H observed); never reuse a panel across battles.
- Turn quantization: 6-turn battles have ±8% granularity — that's why the gate
  is ceil-exact OR ≤10%, not raw % alone.
- `troop_passives` blocks in some raw JSONs are stale after class corrections —
  the corpus `corrections_applied` field is the truth.
- G_l falls back to the Infantry column for unmeasured (class, tier) cells with
  a `fallback_infantry` status — expect degraded accuracy there and label it.
