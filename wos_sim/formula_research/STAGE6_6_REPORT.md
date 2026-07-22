# Stage 6.6 — hero-state-aware Gatot kit v3 + table refresh + full-corpus winner gate

**Status: COMPLETE (2026-07-19). Builder: background agent (terminated by the
account's monthly spend limit ~90% through); completion + evaluation: the
evaluator window. Attribution is explicit below — all frozen PHYSICS is the
builder's, independently cross-checked against the evaluator's own
pre-existing arithmetic in `gatot_shield_test.py`.**

## 1 · What was frozen (stage6_tables v2, `law_version: "stage6.6"`)

- **`hero_state` block** (new; emitted by `stage6_hero_state.py`, all cells
  with named corpus-row provenance):
  - registry: per-copy Expedition% + no-hero baseline panel (mueller
    301.93/179.1, alpaca 337.85/176.2, farseer 186.45/0.0);
  - detection rule: aura'd iff the unit's Infantry Attack-panel is
    nearest-neighbour to (baseline + Expedition%) with a ×2 margin guard,
    else ambiguous ⇒ abstain. Corpus audit: every Gatot row classifies at
    ≥×3 margin.
  - `B_by_copy_state`: mueller.aurad 201.95 (21/22 MM edge), farseer.aurad
    30.15 (32/33 edge), **alpaca.aurad 879.3** (204/205 Lancer edge;
    factorized-K branch 949.9 carried; the 204-cap and 575-kill checks pass
    on BOTH branches), **any.inert 0.0** (the 12-row ±3.2% plain-law anchor).
  - `K_LanInf_for_gate`: T6 edge-implied **90.38** (winturn variant 91.04);
    T3-ordinary 111.29 (+23% tension, ordinary-vs-FC1 OPEN); factorized
    83.66 carried; gate verdicts must be invariant across the [83.66,
    111.29] span or the seam abstains.
  - `gatot_led_dealer_policy`: plain law vs aura'd targets (the Lab-Rat
    mirror instrument IS this configuration); the 151127 dealer slowdown
    stays open physics with the slowdown-robustness note.
- **G_w(Infantry, T7) = 14.285, status measured** (band [14.097, 14.473],
  from the T7 discriminator row), replacing the cube-root extrapolant 13.19
  (−8%). The cell note RECORDS the ×1.17–1.19 cross-instrument tension: the
  T6 twin battle implies G_w(6) ≈ 12.7–13.0 on the MuellerAlpaca/Vulcanus
  instrument vs the frozen 10.889 (FarSeer-v3 instrument) — the former
  "+18% T6-discriminator residual", now precisely framed, not corrected.
- Corpus metadata: row_count 238 (dynamic).
- `stage6_tables.json` **byte-stable across a double emit** (sha256
  6dee5dd4… ×3, including the on-disk state).

## 2 · Kit v3 in the seam (`stage5_composition.py` — builder's work)

Kit descriptors take copy tokens ("mueller"/"alpaca"/"farseer"; 6.5
instrument tokens remain accepted as aura'd aliases) and an optional explicit
`gatot_state`; absent that, the seam detects the state from the unit's
Infantry Attack-panel (army dicts now carry `panel_pct` through `_norm_army`).
INERT ⇒ plain law, no gate, no abstention. AURA'D ⇒ per-copy budget for
hero-less dealers of EVERY class (Infantry included — the v5 dissolution;
Lancers via the per-edge K with span-invariance abstention) / S-curve for
Vulcanus-led dealers (Mueller target only, as measured). Gatot-led dealers
race plain per the frozen policy. Default args remain byte-identical to
pre-6.5 (`stage5_validate` exit 0).

**Evaluator-completed wiring** (the builder died before these):
`section_w6` passes `panel_pct` into the race (1 edit — without it every
Gatot row abstained "state None"); W6 scope extended to NanoMart multicount
rows (winner-only); I6 partition labels for the five 6.6-instrument rows and
the multicount reclassification; the six stale stage2-era test assertions
refreshed with dated annotations; this report.

## 3 · W6 v2 — full-corpus four-way winner gate

| | 6.5 | 6.6 |
|---|---|---|
| scored | 143 | **165** |
| CORRECT | 80 | **146** |
| COIN_FLIP | 14 | 15 |
| ABSTAIN | 46 | **1** |
| WRONG | 3 | 3 (the same known three) |

- **Abstain collapse 46 → 1**: the 12 inert-Gatot mirror rows (plain race),
  the 24 Alpaca-target rows (budget-capped ⇒ defender), the Lancer
  knife-edge / Lancer-dealer rows (per-edge K + span invariance), and the
  ENIF2/Mueller-target rows (copy+state resolved) all upgraded to CORRECT.
- **The 1 remaining abstain is the 205v1 knife-edge row itself**
  (`gatot_gate_branch_flip`: dealer pool d ∈ [873.4, 879.8] vs
  B ∈ [879.3, 949.9] flips capped-vs-breakthrough across the carried
  K-branch) — definitionally on the measured edge, and the honest verdict
  for the row that SOURCED the constant.
- **Multicount rows (16, newly raced): 14 CORRECT + 2 COIN_FLIP, zero
  wrong** — Codex v2's 7 multicount winner misses were QA-implementation
  differences, not law defects.
- WRONG remains exactly the known list: `LabRat_1v1_T1LanvT1MM_..._213859`
  (cross-cell K tension, 13.6%), `..._T7InfvFC1T1Inf_..._151127` (the
  Gatot-dealer slowdown, Stage-7 physics; its inert state auto-detected by
  the new detector), `NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus`
  (+26%, pre-existing).

## 4 · Gate battery (final)

11 PASS + 2 deliberate honest FAILs (unchanged in meaning from 6.5):
D6-factorized (the K(Lan→Lan) −14/−19% finding) and W6 (WRONG == 0 with the
3 known rows). G12 backtest PASS 7/13; predictor suite 105 passed / 8
skipped / 2 xfailed; `stage5_validate` exit 0; formula_research suite now
**24/24 green** (six stale stage2-era assertions — the T5-clock-conflict
existence test, the 71-row/61-clock/39-exact counts, the casualty-quirk
existence, the duplicate map — refreshed with dated annotations asserting
the CORRECTED data-state per the eval-6 recommendation); I6 238/238
accounted with no "OTHER" bucket.

## 5 · Evaluator verdict (eval-6.6): ACCEPT

Every frozen number was independently reproduced by the evaluator's own
arithmetic BEFORE the builder ran (`gatot_shield_test.py`: G_w(7) 14.1–14.5,
K(Lan→Inf) 90.4 via the 40/41 edge, B_Alpaca 879 with the 575-kill
consistency, the 12-row inert fit ±3.2%) — an unusually strong
independent-derivation guarantee. Gates re-run by the evaluator; double-emit
byte-stable; guardrails held (branches carried to the point of a branch-flip
abstention on the sourcing row itself; failures reported as failures).
Attribution caveat recorded: ~10% of the mechanical work (wiring, scope,
test refreshes) was evaluator-completed after the builder's spend-limit
death, so builder/evaluator separation is imperfect for THOSE pieces — none
of them involve a frozen constant.

## 6 · Open after 6.6

1. The 3 known WRONG rows (unchanged; 151127 = the Gatot-dealer slowdown →
   Stage 7's headline physics question).
2. K(Lan→Lan) factorized cell −14/−19% (needs a direct measurement).
3. The K(Lan→Inf) T3-vs-T6 edge tension (+23%, ordinary-vs-FC1).
4. The ×1.17–1.19 cross-instrument G_w tension (FarSeer-v3 vs
   MuellerAlpaca/Vulcanus instruments) recorded on the T7 cell.
5. The 205v1 branch-flip abstain — closable by one battle that both branches
   agree on (e.g. N=220 Lancers ⇒ breakthrough on both).
6. Hero-led n>1 pooling order (the 3× Vulcanus battle, still unrun).
7. B's cross-copy scaling (Alpaca/Mueller ×4.4 vs sheet ratios ×1.12–1.19):
   stars / S2-level remain the candidates — Mueller's S1/S2 levels + star
   counts of all three copies wanted.
8. Stage 7: the Type-2 proc layer (distribution-only) + the multicount
   clock regime.

## 7 · Post-stage QA addendum (2026-07-19, seam test suite)

`wos_sim/predictor/tests/test_deterministic_seam.py` (10 cases, every scenario
a named corpus battle) was added as the always-on pytest layer for kit v3 —
and immediately caught three real defects, all fixed and re-verified:

1. **`api.py` still stamped `law_version: "stage6.5"`** (the builder died
   before touching it) → now "stage6.6".
2. **Branch cross-product over-abstention**: the budget gate compared a
   Lancer dealer's edge-branch rate against BOTH B branches independently.
   B_Alpaca inherits the K(Lan→Inf) branch (its measuring dealers were
   Lancers), so K and B must be evaluated as coherent PAIRS — under which
   the breakthrough threshold N* ≈ 204.95 is branch-INVARIANT for this
   dealer family. Fixed (`k_b_pairs_alpaca`). Consequence: the 205v1 row
   upgrades from branch-flip abstain to a CONFIDENT correct call, with the
   predicted kill turn (544–638 across stored-precision/branches)
   bracketing the observed 575. **W6 final: 165 scored = 147 CORRECT /
   15 COIN_FLIP / 0 ABSTAIN / 3 WRONG (the known list).** The §3/§5
   "1-abstain" narrative is superseded by this addendum — the earlier
   abstention was the bug's shadow, not physics.
3. Two test fixtures initially used guessed stats; corrected to corpus
   values (rows 162413/164811).

Final battery after the fixes: predictor suite **115 passed** / 8 skipped /
2 xfailed; formula_research 24/24; stage6_validate 11 PASS + the 2 deliberate
FAILs; G12 backtest PASS; s5v exit 0.

## 8 · Codex QA v3 triage (2026-07-19 evening) — wiring audit, all findings resolved or scoped

Codex's v3 (wiring/adoption audit, `qa_codex_v3/`): W1 corpus replay EXACT
(151/15/1/3, zero per-row diffs vs W6); production isolation PASS; verdict
FAIL on 7 edge findings. Disposition:

| # | Finding | Verdict | Action |
|---|---|---|---|
| 1 | Vulcanus kit not self-contained: seam does not compute hero FOLDS; a kit-only caller can get a fold-blind confident verdict (their W6 construction: 11% gap flips) | REAL — accepted as **Stage 6.7 scope** (fold-ownership migration needs its own gates: moving folds into the seam re-baselines every validator convention) | Interim: `hero_folds_not_applied_*` warning flag whenever a kit declares Vulcanus with offense_mult 1.0 — no caller can be silently fold-blind |
| 2 | 205-Lancer clock 648 vs [544,638]; their arithmetic 575 | REAL, but their root-cause (a 1.125 composition multiplier) is WRONG — the path is TANK_SOLO=1.0; the true cause is the stored **B rounded to 1 decimal** (879.3 vs exact 879.251), amplified ×130 by the knife-edge (net 0.53→0.47) | B re-emitted at 6 decimals → clock now **587** (+2.1% vs obs 575; residual = 2-dp stored k at the same edge — noted for 6.7) |
| 3 | Gatot target count>1 silently bypasses the kit gate | REAL (a 6.5-era deliberate fall-through that lacked visibility) | `gatot_kit_multiunit_unmodeled` flag added |
| 4 | Crashes on empty army / count=0 / zero Attack | REAL | `_norm_army` guards → clean ValueError with messages |
| 5 | n>1 S-curve extrapolation unflagged | REAL (n=3 is validated by E2; other n extrapolate) | `gatot_scurve_multi_n_validated_at_3_only` flag |
| 6 | Stale metadata 238 vs 243 | REAL | re-emit → row_count 243 (same emit as #2) |
| 7 | FarSeer aura panel-pair +2.15pp vs sheet | REAL provenance gap (gear/state drift between the two captures; state calls unaffected at ≥×3 margin) | documented here + HERO_KITS; registry annotation deferred |

Post-triage battery: predictor suite **121 passed** (115 + 6 new QA-derived
regression tests covering every probe above) / 8 skipped / 2 xfailed;
W6 unchanged 151/15/1/3 over 243/243; backtest PASS; tables double-emit
stable (sha ae020d1f…). The one behavioral change from the fix set is the
205v1 clock (648→587); no winner classification moved anywhere.
