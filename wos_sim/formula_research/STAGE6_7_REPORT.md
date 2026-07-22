# Stage 6.7 — fold-ownership migration (the seam computes hero folds)

**Status: COMPLETE + eval-ACCEPT (2026-07-19). Attribution: the background
builder was killed by the account spend limit before any code landed (only
emitter precision touch-ups from its early steps survived); the migration,
tests, gates and evaluation in this document were done in the evaluator
window. Builder/evaluator separation is therefore NOT satisfied for this
stage — mitigated by the fact that every migrated clock below is
hand-recomputed from first principles (no seam calls) and cross-checked
against the seam, and that the stage moves NO physics constants.**

Closes Codex QA v3 finding #1: the deterministic hero folds lived in a
validator-side private helper (`stage5_validate._nanomart_offense`), so any
live caller that declared kits still raced fold-blind.

## 1 · What changed

### `stage5_composition.py`
- **`_hero_folds(dealers, dealer_kit, targets, target_kit, *, apply_royal_legion=False)`**
  (new, ~70 lines with the constants block): returns `(mult, flags)` for ONE
  race direction. Frozen mechanics only, no new constants:
  - Seo-yoon S1 on the dealer side — ×1.05/1.10/1.15 by level;
  - Vulcanus on the dealer side — S2 ×31/30; S3 ×(1+0.12/3) when the dealer
    fields Marksmen; S3 ÷0.88 when the front target is Infantry/Lancer;
  - Vulcanus on the target side — S1 ×0.96 on the dealer's Attack.
  Every applied fold emits a `fold_*` flag (side-prefixed `att:`/`def:`).
- **`predict_battle(..., apply_hero_folds=True, apply_royal_legion=False)`**:
  folds computed once per direction and multiplied into the direction's
  offense; caller `*_offense_mult` multiplies ON TOP (documented as
  anchors/extras). `apply_hero_folds=False` reproduces 6.6 exactly and emits
  `hero_folds_disabled_by_caller`. The 6.6 interim warning flags
  (`hero_folds_not_applied_*`) are **removed** — the gap they warned about is
  closed.

### `stage6_validate.py`
- `_kit_for_side` now carries everything the seam needs: `seoyoon` level and
  (informational) `royal_legion_level`.
- **W6 no longer passes `_nanomart_offense` mults** — it passes complete kits
  and lets the seam fold. This is the migration's substance: it also extends
  folding to the NON-NanoMart Vulcanus rows, which previously raced fold-blind.

### `api.py`
- `law_version: "stage6.7"`. `predict()` / `server.py` untouched.

### Precision housekeeping (spec item 4)
- `K_LanInf_for_gate` emitted at 6 decimals (the builder's surviving edit),
  re-emitted here: **90.378932** (was 90.38). Combined with the 6-dp B from
  the QA-v3 fix, the 205v1 knife-edge clock lands at **575 = the observed
  value exactly** (6.6: 587, pre-fix: 648).
- Tables byte-stable across a double emit (sha256 `bfec8b2d…` twice);
  `corpus.row_count` 243.

## 2 · The Royal Legion decision (ambiguity NOT resolved silently)

The spec listed Royal Legion (Gatot S3, −10%/−15% enemy Attack) among the
folds to implement. Implementing it as an *applied* fold would have been
**double-counting**: the frozen K/G_l cells were measured on instruments whose
targets were Gatot-led, so the debuff is already absorbed in those constants
(the caveat in the run-stage mechanics block). The seam therefore:
- computes it, but **does not apply it by default**;
- flags `royal_legion_L{n}_absorbed_in_cells` whenever a Gatot target declares
  a level, so the absorption is visible rather than assumed;
- exposes `apply_royal_legion=True` for the future decontamination analysis.

Settling it needs a Gatot-target instrument whose Royal Legion level differs
from the cell-sourcing instrument's — recorded as a Stage-7 item.

## 3 · Re-baseline: W6 movement

| | 6.6 | 6.7 |
|---|---|---|
| scored | 170 | 170 |
| CORRECT | 151 | **151** |
| COIN_FLIP | 15 | **15** |
| ABSTAIN | 1 | **1** (the E3a cell) |
| WRONG | 3 | **3** (the same known rows) |

**No classification moved.** The hard gates hold: WRONG is exactly the three
known rows, ABSTAIN ≤ 1, CORRECT+COIN_FLIP did not drop.

A migration-integrity signal worth recording: an intermediate run with the
seam folding AND the validator still passing the legacy mults produced
**149/8/1/12** — double-folding is loudly visible, which is how we know the
hand-over is complete and single-counted.

### Clock movements on the previously fold-blind rows

| row | 6.6 clock | 6.7 clock | observed | verdict |
|---|---|---|---|---|
| T7 discriminator `..._235302` | 73 | **76** | [75, 77] | **moved INTO band** |
| T6 discriminator `..._161706` | 75 | 78 | [90, 92] | moved toward band (known open residual) |
| E3b Gordon-led T7 `..._121239` | 73 | 76 | [72, 74] | moved OUT (+2.7%) — attributable to Gordon's **unmodeled** kit debuffs (~−3%, `docs/HERO_KITS.md`); winner unchanged |
| E4 MiniMart `..._121806` | 14 | 14 | [12, 14] | in band both ways |
| 205v1 knife-edge | 587 | **575** | 575 | **exact** (K/B precision) |

The E3b out-of-band move is the honest consequence of folding what we know
(Vulcanus) while Gordon's effects remain uncaptured — it is a visible,
explained residual, not a silent regression.

## 4 · Gates

- `stage6_validate`: **11 PASS + the 2 standing deliberate FAILs** (D6
  factorized K(Lan→Lan) finding; W6 WRONG==0 with the 3 known rows);
  243/243 accounted.
- `stage5_validate`: exit 0.
- `backtest` (G12): **PASS**, 7/13 unchanged.
- `pytest wos_sim/predictor/tests/`: **125 passed** / 8 skipped / 2 xfailed
  (121 → 125: five new fold tests replace the obsolete warning test).
- `pytest wos_sim/formula_research/`: 24 passed.
- Tables double-emit byte-stable.

### New tests (`test_deterministic_seam.py`)
1. `test_vulcanus_kit_folds_are_applied_by_the_seam` — the Codex-v3 contract:
   a kit-only caller gets the FOLDED verdict. Construction derived here (their
   exact stats weren't published): a near-even Infantry-vs-Vulcanus-Marksman
   race where folds reverse the winner — folds-off says attacker, folds-on
   says defender.
2. `test_seoyoon_fold_applied_by_level` — L3 < L1 < no-kit kill times.
3. `test_royal_legion_absorbed_not_double_applied` — default flags absorption;
   the opt-in branch changes arithmetic.
4. `test_fold_opt_out_reproduces_stage66` — no fold flags, opt-out flag present.
5. `test_caller_mult_multiplies_on_top_of_folds` — the documented contract.

## 5 · Evaluator pass (eval-6.7)

- **Independent recomputation, no seam calls** (frozen constants + corpus eff,
  hand arithmetic): T7 discriminator folded **76.00 → ceil 76** (seam: 76;
  fold-blind 72.96 → 73, seam: 73); T6 discriminator **77.24 → 78** (seam: 78);
  E3b **76.00 → 76** (seam: 76). All three match the seam exactly.
- Fold multiplier verified against the legacy helper's conventions: a Vulcanus
  Marksman dealer vs an Infantry target = 31/30 × 1/0.88 × 1.04 = **1.2212**,
  identical to `_nanomart_offense`.
- Gate battery re-run (above); double-emit stability confirmed.
- Guardrails: no new constants; the one genuine ambiguity (Royal Legion) is
  branched and flagged, not silently chosen; the E3b regression is reported
  as a residual with its cause rather than tuned away.

**Verdict: ACCEPT**, with the attribution caveat in the header.

## 6 · Open after 6.7

1. The 3 known WRONG rows (unchanged).
2. Royal Legion decontamination (needs a differing-level Gatot instrument).
3. Gordon kit effect magnitudes (uncaptured tooltips) — the E3b residual.
4. K(Lan→Lan) instrument spread 126.2 / 149.8 / 176; K(Lan→Inf) T3-vs-T6.
5. The Alpaca-FC1T1-target ×1.17 family (T6 discriminator residual).
6. Stage 6.8: the Type-1 router into the app path + UI honesty surface.
7. Stage 7: the Type-2 proc layer.
