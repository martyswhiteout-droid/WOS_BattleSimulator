# Stage 6 report — class-general law + the Gatot-kit model (2026-07-17)

Builder run of `/run-stage 6` against `STAGE6_SPEC.md`. **Every number below is
produced by a re-runnable script**; the four commands that regenerate this
report's evidence:

```
py -m wos_sim.formula_research.stage6_tables            # frozen vs corpus-derived drift
py -m wos_sim.formula_research.stage6_tables --emit     # (re)write stage6_tables.json
py -m wos_sim.formula_research.stage6_gatot  [--raw]    # the kit model, both branches
py -m wos_sim.formula_research.stage6_validate          # 232-row map + regression gates
```

Corpus state: `TYPE1_CORPUS.json`, **232 rows**, rebuilt twice during this run
and byte-identical modulo `generated_at` both times (the housekeeping edits are
provably output-neutral).

## 1 · Class-keyed tables (`stage6_tables.py` → `stage6_tables.json`)

Every cell carries `{value, status, sources[, band]}` with
`status ∈ {measured, interpolated, bounded, extrapolated, factorized,
fallback_infantry}`. Interpolated cells are **computed at import time**
(geometric fill between measured rungs) — nothing hand-rounded. Frozen-vs-
derived drift on every new/updated cell: **≤0.02%** (the residual is 4-dp
display rounding of the frozen values; the drift printout shows it honestly).

### K-table (updates in bold)

| dealer \ target | Infantry | Lancer | Marksman |
|---|---|---|---|
| **Infantry** | 12.524 (n=39) | 22.43 (n=9) | 73.16 (n=10; ENIF replicates +5.0/+5.5%) |
| **Lancer** | *83.7 factorized* | *149.8 factorized* | **488.71** (ENIF3 R08 full-panel, band [21,23]; Gordon 499.50 = +2.2% second source) |
| **Marksman** | **90.11** (ENIF1b R02, band [66,67]; LabRat pair 91.16×2; R03 √2-fold 88.71) | *167.6 factorized* | 566.66 (Gordon; +1072%-panel confirmed) |

- **MM→Inf freeze rule:** R02 (alliance-corrected, tightest band). The four
  source rows span [88.71, 91.16] (±1.4%); the R03 √2-fold band misses the
  LabRat band by 0.4 turns-equivalent (−1.6%) — instrument spread, recorded in
  the cell note. R03 doubles as a **√N reconfirmation** away from the Gatot
  shield (−1.6% at √2).
- **Factorization** f = {Inf 1, Lan 6.680, MM 7.470} (recomputed from the
  updated cells), g = the Infantry row. Status: ±10–15% estimator (stage5
  verdict, re-confirmed in D6 below). The Gatot thresholds independently imply
  K(Lan→Inf) ≈ 91 at T6 (+8.8%) — recorded, **not** frozen (§2).

### G_w — dealer tier damping is CLASS-KEYED

| τ | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Infantry (measured, S4/S5) | 1.000 | 2.680 | 4.323 | 5.884 | 9.791 | 10.889 |
| Lancer (E-NIF3) | 1.000 | *1.0445 interp* | **1.0909** [0.939, 1.257] | *1.2459 interp* | *1.4229 interp* | **1.6250** [1.435, 1.833] |
| Marksman (bounded) | 1.000 | 1.0 [1, 1.17] | 1.0 [1, 1.17] | 1.0 [1, 1.17] | 1.0 [1, 1.17] | 1.0 [1, 1.17] |

Beyond measured range: Infantry keeps the stage5 cube-root interpolant; Lancer
extrapolates its last geometric ratio (1.1421/tier), flagged `extrapolated`;
Marksman stays 1.0 inside the stated band, flagged `bounded` (entangled with
S_gatot — §2). The E-NIF3 dealer rows carry the `base_mismatch` flag
(FC1 troops); bands come from the exact turn bands.

### G_l — target tier factor, now with the measured MARKSMAN column

| τ | 1 | 2 | 3 | 4 | 5 | 6 | 7–10 |
|---|---|---|---|---|---|---|---|
| Infantry | 1.000 | 0.996 | 0.904 | 0.795 | 0.770 | 0.748 | 0.742/0.744/0.757/0.777 |
| Lancer | 1.000 | **0.654** | *fallback→Inf, flagged* | … | … | … | … |
| Marksman (E-NIF2) | 1.000 | *0.4989 interp* | **0.2488** | *0.1737 interp* | *0.1212 interp* | **0.0846** | *extrapolated ×0.700/tier, flagged* |

The Marksman column is **far steeper** than Infantry's (0.0846 vs 0.748 at T6).
G_l^MM(T1) ≡ 1 by K-cell normalization; the ENIF2 R05 rung re-measures the
Inf→MM cell at 76.84 (+5.0%) — that spread rides the K cell (the Alpaca-FC1-MM
instrument reads consistently +5%, see §3 G6).

Policy blocks in the JSON: per-battle **alliance panels** (RFJ +23/+10pp is
documentary, never a constant), **base-stat policy** (corpus eff / docs table
only — see §5 troop_catalog), Type-2 boundary unchanged (−6.5%
Vulcanus-dealer fold stays a documented band, not a fit).

## 2 · The Gatot-kit model (`stage6_gatot.py`) — TWO REGIMES, both solved

Scope: **non-Infantry dealers vs a Gatot-led Infantry target.** (Infantry
dealers ARE the clean law — the K anchor was measured on Gatot-vs-Gatot
mirrors that resolve in ~264 turns; no gate applies to them.)

### 2a · No-hero mobs: a BUDGET ABSORB with LINEAR volley pooling

`net = max(0, N·r1 − B)` HP-units/turn; capped iff `net·1500 < pool`.

- **B solved from ONE battle** (22×T6MM = 147t): **B(Mueller, S1/S2/S3 L1) =
  201.95**, interval (201.94, 201.95]. **B'(FarSeer, S1/S2 L1) = 30.15** from
  33×T3MM = 186t.
- **All five consistency checks PASS** (and the whole structure survives the
  G_w^MM = 1.17 entanglement branch unchanged):
  - 21×T6MM capped: gross 194.66 ≤ B + 0.19 (margin +7.5) ✓
  - 40/41×T6Lan bracket: one r1L ∈ [4.9501, 4.9505] satisfies win-turn AND cap ✓
  - 32×T3MM capped: margin +0.59 ✓ (razor-tight knife-edge)
  - 66/67×T3Lan bracket: r1L ∈ [0.4531, 0.4532] ✓
  - ENIF2 R05 (single no-hero FC1-T1-MM): d = 2.11 ≪ B → can never break
    through — exactly Martin's "a no-hero MM cannot beat Gatot" ✓
- **√N stacking is REFUTED in this regime by an impossibility inequality**
  (spec asked for √N; the data says no): for ANY suppression monotone in gross
  rate, net(22) ≤ net(21) + (√22−√21)·r1 = 0.193 + 1.000 = **1.193 < required
  1.974**. Per-hit absorption dies the same way (max net(22) = 0.203).
  Fractional capping degenerates (needs c ≥ 0.9990). The spec's candidate
  families (fixed absorb / 0.06·A_def shield / capped absorb) are all inside
  the proven-impossible class **under √N**; under linear volley pooling the
  budget absorb is the surviving form. √N remains the law AWAY from the shield
  (NanoMart ladders; ENIF1b R03 √2 at −1.6%) — the boundary is a Stage-7
  mechanism question.
- **The eight threshold battles reproduce** (solve-sources marked): 21 CAP /
  22 → 146.5 [B-solve] / 40 CAP / 41 → 285.5 / 32 CAP / 33 → 185.5 [B'-solve]
  / 66 CAP / 67 → 333.5 — observed 1500/147/1500/286/1500/186/1500/334.
- The Lancer thresholds **measure** K(Lan→Inf)·G_w^Lan: T6 ⇒ K ≈ **91.0**
  (+8.8% vs factorized 83.7 — inside the ±10–15% band); T3 ⇒ K ≈ 111.3 (+33%,
  **ordinary-vs-FC1 base caveat** — the T3 mob uses ordinary-catalog stats,
  G_w^Lan(3) was measured on FC1 dealers). Both recorded, neither frozen.
- **Defender anchoring of B is OPEN**: closest candidates B/(A·D·H) =
  0.1198 vs 0.1433 and B/(D²·H) = 0.0300 vs 0.0368 across the two defenders
  (±20%); the defenders differ in stats AND S3 presence. No clean scaling —
  the model applies to the two measured defenders; elsewhere the predictor
  must flag `gatot_gate_unmodeled`.

### 2b · Vulcanus-led singles: a SATURATING per-volley suppression S(d)

Four battles vs the same Mueller-Gatot (d = clean HP-units/turn): T1-MM 102t,
T3-MM 21t (R11), T6-MM 6t (R12), RFJ-T6-MM 6t. Exact integer-turn S-bands with
the Vulcanus folds (S2 every-6th ×1.2 cadence; S3 pool ×0.88) as the primary
branch:

| point | d | S band (lo, hi] |
|---|---|---|
| T1_102 | 13.94 | (5.667, 5.732] |
| T3_R11 | 31.89 | (2.562, 2.686] |
| T6_R12 | 58.46 | (1.140, 1.414] |
| T6_RFJ | 61.35 | (1.196, 1.484] |

Six families enumerated, constants solved from minimal 1–2-point subsets,
accepted only if **all four** points land in-band:

- **SURVIVES: `S(d) = 1 + a·e^(−d/d0)`, a = 10.727, d0 = 16.893** — solved
  from T1+R11 (the two tight points), blind on R12 (pred 1.337 ∈ (1.140,
  1.414]) and RFJ (1.284 ∈ (1.196, 1.484]). Status: **candidate**, not frozen
  law — the two blind points have wide integer-turn bands.
- Rejected (0 passing solves each): fixed absorb `d/(d−a)`, the 6%·A_def
  shield variant, hyperbolic `1+a/d`, power `1+a/d^p`, linear-net `φ·d−a`.
- **The raw (unfolded) branch kills every family** including exp-decay — the
  deterministic Vulcanus folds are load-bearing (branch reported, ENIF's raw
  convention numbers reproduced for continuity).

### 2c · The regimes are IRREDUCIBLE to one smooth mechanism (proven)

- S is **not a function of total rate**: single 31.9 → S ≈ 2.6, while mob
  188.8+ → S = ∞ (more gross, infinitely more suppression).
- S is **not a per-hit law**: mob hits (9.27 each) would need S ≈ 103 at N=22
  and S = ∞ at N=21 (same hit size!) vs the single-hit trend S(9.27) ≈ 7.2.
- The budget does **not** apply to hero-led dealers: every single-dealer d
  (13.9–61.4) < B ≈ 202, yet all four won in 6–102 turns.

The split is **attacker hero presence** (hero-less = gated; Vulcanus-led =
saturating penetration). Whether it is hero-presence per se or something
correlated (panels, per-hit size at equal N) is exactly what the
discriminating experiment separates:

- **Discriminator:** 3× Vulcanus-led T6-MM (R12 loadout) vs Mueller-Gatot —
  budget gate predicts CAPPED (3×56.7 < 202); the S-curve predicts a kill in
  ≤4 turns. Maximally separating, one battle.
- **Splitter:** one T6-MM vs the GORDON-Mueller Infantry — K_eff =
  90.11·G_w^MM(6) with no Gatot in the loop; separates G_w^MM from S_gatot.

Report-only residual: in the capped mob battles the Gatot Infantry kills
attackers ~2.5× slower than the law rate (4 kills/1500t vs law ~150 t/kill) —
target-switching / wounded mechanics OPEN, flagged, not fitted.

## 3 · Corpus-wide validation (`stage6_validate.py`) — ALL 12 GATES PASS

Full 232-row accounting: 94 A6 + 14 B6 + 3 C6 + 23 D6 + 3 E6 + 12 H6 + 21
composition-regime + 62 stated exclusions (16 NanoMart count/survivor rows =
Stage-3 √N evidence, 31 NanoMart tier rows = wrong-additive-base captures,
4 capped beast, 9 legacy_unverified, 1 multi-class, 1 no-clock) = **232/232**.

| section | stage5 | stage6 | note |
|---|---|---|---|
| A6 clean exact 1v1 (94 rows, now incl. ENIF2) | 85 pass | **87 pass** | R06/R07 exact under measured G_l^MM (were fallback); predictions identical everywhere else (asserted) |
| B6 Gordon band rows (14) | 6 in-band | **9 in-band** | R03 in (√2 + 90.11); **R09/R10 in** (40.5→10.0 and 44.5→6.5 — the class-keyed G_w^Lan fix, exactly the spec's promised improvement) |
| B6 ENIF1b two-sided races | — | **4/4 correct** | the K-table calls the RFJ alliance winner-FLIP on both sides (R01/R04 att-66.4 vs def-75.4; R02 att-75.3 vs def-66.5) |
| C6 beast blind per-kill | +0.1/+0.1/+0.0% | identical | asserted equal |
| D6 NanoMart T1 blind (23) | — | measured-cell moved rows ALL improved (+51.2→+49.5, +31.2→+29.7, +18.7→+16.1); factorized rows −11.5/−13.6% within the ±15% estimator band | SeoYoon-dealer ≤1.3% and Vulcanus-dealer −6.5% bands unchanged |
| E6 composition anchor-mode | 16/16 | exact (re-asserted) | algorithm untouched |
| H6 kit | out-of-scope | 8/8 thresholds + 4/4 singles | §2 |

G6 note: ENIF1b R01/R04 sit at −5.1% under the frozen Inf→MM cell — the
Alpaca-FC1-T1-MM instrument reads +5% consistently (R01/R04 +5.5%, R05 +5.0%);
the races above are the pass criterion for those rows (magnitude follows the
known instrument spread).

## 4 · Seam wiring + binding gates

- `wos_sim/predictor/api.py`: the two deterministic entry points now route
  through the stage6 class-keyed tables; meta gains `law_version: "stage6"`,
  per-cell provenance statuses, and the `stage6_tables.json` manifest
  (lazy-loaded). `predict()` and `server.py` untouched.
- `stage5_composition.py` gained an **optional, default-None `law=` injection**
  (three functions) so the battle path can run on stage6 tables.
  **Proof of no side effect:** `stage5_validate` and `stage5_composition`
  outputs are **byte-identical** to pre-edit baselines; `stage5_law.py` itself
  untouched (eval-5 repro intact).
- **Backtest gate G12: PASS — 7/13 winners, identical to baseline.**
- **Predictor suite: 105 passed, 8 skipped, 2 xfailed** — identical to the
  stage5-report state.
- Pre-existing (NOT stage6): 3 stage2-era test failures
  (`test_stage2_backsolve` ×2, `test_constraints` ×1) — frozen against the
  71-row ledger; the L21 DUP-EXCLUDED correction (2026-07-14) made it 70.
  Import-graph verified independent of every file this stage touched. See §5.

## 5 · Housekeeping (task 4)

1. **L21 registry entries annotated** (`_corpus/corrections.json`):
   - the `resolved_history` L21 item marked `DOCUMENTARY-ONLY` with the
     ledger-count side-effect note (the 3 stage2 test failures above);
   - the **actually-orphaned ACTIVE matcher** (the old-id L19 correction,
     `NanoMart_1v1_T1LanvT1Inf_…`) marked `INERT`: the ledger dataset
     meanwhile carries the corrected battle under its new id
     (`NanoMart_1v1_T1InfvT1MM_…`, `corrections_applied=[]`), so the 0-match
     build warning is expected; kept for the audit trail. The sibling
     `T1LanvT1MM` entry still matches and stays ACTIVE (verified in-corpus).
   - Corpus rebuilt after each edit — **byte-identical modulo `generated_at`**
     both times (`build_corpus.py` reads only `corrections`/`suspect_flags`).
2. **R03/R04 Mueller-MM Health cosmetic** (118.6 → expected 128.6 by the +10
   alliance pattern): noted here and already in `ENIF_ANALYSIS.md`; the MM
   does not fight in those battles — no calculation impact; in-file fix is
   Martin's call.
3. **troop_catalog.py vs docs/TroopStats divergence documented** (module
   docstring of `stage6_tables.py` + `base_stat_policy` in the JSON + this
   section): the deterministic path uses **corpus eff stats (docs table)
   ONLY**; `troop_catalog.py` is the wostools.net snapshot feeding the LEGACY
   engine — never use it in the deterministic path and never silently edit it.
   The divergence **materially matters**: the T3-threshold attackers carry
   ordinary-catalog stats while G_w^Lan was measured on FC1 dealers — the
   likely source of the K(Lan→Inf) T3-vs-T6 tension (§2a).
4. **Stale figure note:** the stage5 report's "+26%" for the corrected L19 row
   was computed against the pre-rebuild corpus; today `stage5_validate.py`
   itself prints +51.2% for that row (still inside the stated +19..+51%
   non-Inf-dealer band). Not a stage6 change — corpus evolution.

## 6 · Open items / asks (none are blockers)

1. **Splitter battle** (T6-MM vs GORDON-Mueller Inf) — separates G_w^MM from
   S_gatot exactly.
2. **Regime discriminator** (3× Vulcanus-led T6-MM vs Mueller-Gatot) — budget
   gate vs S-curve, one battle.
3. Hero-led **mobs** are an untested cell (all mob data is hero-less; all
   single-dealer data is Vulcanus-led).
4. Lancer G_w T2/T4/T5 and Lancer G_l T3+ rungs — turn interpolated/fallback
   cells into measured ones.
5. K(Lan→Inf) T3-vs-T6 threshold tension (+33% vs +8.8%) — resolved by either
   the splitter program or an FC1-T3 Lancer threshold ladder.
6. Reverse-race residual (Gatot kills into a mob ~2.5× slower than the law) —
   target-switching/wounded mechanics, Stage-7 material.
7. Linear-volley-vs-√N boundary (shield regime pools linearly; open-field
   pools √N) — mechanism question for Stage 7.
8. *(cosmetic)* R03/R04 Mueller-MM H 118.6 → 128.6 if Martin wants the panels
   internally consistent.

## 7 · Deliverables

| file | role |
|---|---|
| `stage6_tables.py` | class-keyed frozen tables + provenance + corpus re-derivation + stage6 predictor shim + `law_funcs()` |
| `stage6_tables.json` | machine-readable single source of truth (incl. the `gatot_kit` block) |
| `stage6_gatot.py` | the two-regime kit model: budget solve + impossibility proofs + family enumeration + JSON block |
| `stage6_validate.py` | 232-row residual map, per-instrument buckets, 12 regression gates (exit code = gate status) |
| `wos_sim/predictor/api.py` | seam entry points now stage6 (`law_version`, provenance meta; additive) |
| `stage5_composition.py` | +optional `law=` injection (default byte-identical; proven) |
| `_corpus/corrections.json` | L21 annotations (output-neutral; proven) |

**Builder verdict: the class-keyed law is frozen with full provenance and
validated corpus-wide with zero regressions (A6 85→87, B6 6→9 in-band, races
4/4, G12 and the predictor suite unchanged). The Gatot kit is SOLVED as a
two-regime model — an exact budget gate (all eight knife-edge battles
reproduced, √N proven impossible in-regime) plus a saturating exp-decay
candidate for hero-led dealers — with the entanglements, the open defender
anchoring, and the two one-battle experiments that would close them stated
honestly. Ready for `/run-stage eval-6`.**
