# Stage 6.5 remediation — honest two-sided winner gate + Gatot-kit seam wiring (2026-07-18)

Implements the plan endorsed in `STAGE6_EVAL.md`'s 2026-07-18 addendum after
Codex's independent QA (`qa_codex/qa_report.md`) found the corpus-wide
validation was one-directional and the production seam raced both sides
**without** the Gatot-kit gate. Three changes, as scoped:

- **A1** — corpus-wide two-sided **W6** gate in `stage6_validate.py`.
- **A3′** — wires the *existing* `stage6_gatot.py` kit model + honest
  abstention into the seam (`stage5_composition.predict_battle`, consumed by
  `wos_sim/predictor/api.py`).
- **A4** — the COIN_FLIP carve-out (part of W6, same convention exposed in
  the seam's `capped`/near-even handling).

**No new physics constants.** Every number the gate uses — K/G_w/G_l, the two
measured budgets `B(Mueller)=201.95` / `B(FarSeer)=30.15`, the S-curve
`a=10.7274, d0=16.8932` — is *read* from the frozen `stage6_tables.json`
`gatot_kit` block (`stage6_gatot.py`'s own output). Untouched this window:
`stage6_tables.py`, `stage6_tables.json`, `stage6_gatot.py`, `stage5_law.py`,
the corpus, and `predict()`/`server.py`.

## 1 · What changed (file:line)

### `wos_sim/formula_research/stage5_composition.py` (untracked file; no prior git baseline to diff against — line numbers are absolute in the current file)

- **L44–65** — module docstring addendum explaining the Stage 6.5 gate.
- **L100–191** — new Gatot-kit gate block:
  - `GATOT_MEASURED_BUDGET_VARIANTS` / `GATOT_MEASURED_SCURVE_VARIANT` (L107–113) — the token names (`"mueller_s123_l1"`, `"farseer_s12_l1"`) a caller's `att_kit`/`def_kit` use to name the two measured defenders + the one measured S-curve defender.
  - `_gatot_kit_frozen()` (L118–139) — lazy, cached, **read-only** loader of `stage6_tables.json`'s `gatot_kit` block.
  - `_gatot_gate_rate()` (L142–191) — the two-regime model (budget absorb / S(d) exp-decay + √N) reproduced from `stage6_gatot.py`'s formulas, operating on one dealer stack; returns `(rate, flags, abstain)` where `abstain` is set (rate `None`) whenever: the dealer-class K feeding the gate isn't `measured` (this is why the four Lancer count-threshold pairs and all 10 Lancer-dealer v4 rows abstain — `K(Lancer→Infantry)` is only a ±10–15% factorization estimator, never validated to separate capped/uncapped at the razor-thin count thresholds the model is knife-edge-sensitive to); the target's Gatot identity isn't one of the two measured budget defenders; or (Vulcanus-led dealers) the target isn't the one measured S-curve defender.
- **L208–269** `_dealer_rate()` — gained `target_kit=None, dealer_kit=None`; routes non-Infantry dealers into a Gatot-led single Infantry target through `_gatot_gate_rate`; flags (never computes differently) Infantry-dealer-vs-Gatot-target stacks as `gatot_kit_inf_dealer_naive` for the caller's monotonicity check. Returns a 3-tuple now (private function, only caller is this file).
- **L272–352** `army_kill_timeline()` — gained `target_kit`, `dealer_kit`, `note_sink` kwargs; returns `(None, flags)` when the front's rate is unresolvable (public 2-tuple contract unchanged — old callers in `stage5_validate.py`/`stage6_validate.py` never pass the new kwargs, so they never see `None`).
- **L355–360** `_uncertain_result()` — the shared `{"winner": "uncertain", "turns": None, ..., "gatot_abstain": {...}}` shape.
- **L363–448** `predict_battle()` — gained `att_kit=None, def_kit=None`; after both directions resolve, checks (in order): (ii) either direction unresolvable → uncertain (`gatot_gate_unmodeled`); (i) an Infantry-dealer-vs-Gatot-target direction that is *currently* the decisive (shorter) one → uncertain (`gatot_kit_unmeasured_inf_dealer` + `M_bound_ge`, computed as `other_clock / this_clock` — the multiplier the unmeasured kit would need to flip the verdict); otherwise the plain race, byte-identical to before.

### `wos_sim/predictor/api.py`

- **L97–120** `predict_deterministic_battle()` — docstring updated; `**kw` already forwarded `att_kit`/`def_kit` to `predict_battle` with no signature change needed; `res["meta"]` now overrides `law_version` to `"stage6.5"` and mirrors `res["gatot_abstain"]` into `res["meta"]["gatot_abstain"]` when present. `predict_deterministic_1v1` (single-direction primitive, no race, nothing to abstain from) and `predict()`/`server.py` are untouched — `predict_deterministic_1v1` still reports `law_version: "stage6"` (see §5, "ambiguities").

### `wos_sim/formula_research/stage6_validate.py`

- **L22–36** docstring: new **W6** section description.
- **L42–45** `COIN_FLIP_BAND = 0.10` module constant.
- **L423–451** `W6_KNOWN_WRONG` — the 3 already-investigated non-Gatot WRONG rows (see §4) with their diagnosis; anything landing in WRONG that is *not* in this dict is flagged `"NEW finding"` in the printout.
- **L453–474** `_kit_for_side()` — derives `att_kit`/`def_kit` from the raw corpus row's `heroes` + `name` fields (the *identity* check, `"mueller"`/`"müller"`/`"far seer"`/`"farseer"` substring match, mirrors Codex's own `defender_budget_key` in `qa_codex/qa_type1.py` — not a new heuristic).
- **L476–505** `_w6_scoreable()` — the corpus-wide subset filter (mirrors the existing A6/D6/I6 exclusion conventions: composition regime, beast, NanoMart tier/count-survivor rows, legacy_unverified, multi-class sides, no winner/no clock).
- **L507–576** `section_w6()` — calls **the real seam**, `stage5_composition.predict_battle`, once per scoreable row (both directions, through `stage6_tables.law_funcs()`), applies the existing NanoMart hero-fold (`_nanomart_offense`, unchanged, reused) per direction, and classifies CORRECT / COIN_FLIP / ABSTAIN / WRONG.
- **L642** new gate tuple `("W6 two-sided winner gate (WRONG == 0)", results["W6"]["ok"])` added to the existing gate battery.
- **`main()`** — calls `section_w6(rows)` and threads `results["W6"]` into `section_i`. `section_w6` deliberately does **not** write into the `accounted` dict — it's a cross-cutting re-check of rows A6/B6/D6/G6/H6 already own, not a new partition, so I6's own 232-row accounting is provably unchanged (confirmed: still 94+14+3+23+3+4+8+21+16+31+4+9+1+1 = 232).

## 2 · Design note: why W6 is monotonicity-based, not identity-based, for Infantry dealers

Part (i) of the ABSTAIN spec could have been read as "abstain whenever an
Infantry dealer with no Gatot faces a Gatot target whose identity isn't the
measured anchor." That rule is **falsifiable by the data**: `MuellerAlpaca_v5_R01`
(T2 dealer) and `R05` (T3 dealer) face the *exact same* unmeasured "Alpaca"
Gatot target as `R02–R09`, yet the naive law **already** calls the winner
correctly for R01/R05 (no amplification needed) and only needs help for
R02–R09 (T4–T10) — see §4. A pure identity rule would have abstained R01/R05
too, needlessly. The implemented rule instead asks: *does an unmeasured
kit amplification (which can only lengthen the Gatot-target's own
survival, never shorten it) threaten to flip the currently-decisive
clock?* This reproduces the correct split without hand-picking row IDs, and
is what let `MuellerAlpaca_v5_R01`/`R05` land CORRECT while `R02–R09` land
ABSTAIN below.

## 3 · W6 accounting (232-row corpus)

```
143 scored, 89 excluded (matches A6/B6/D6/G6/H6/E6/C6/legacy/multi-class/no-clock rows exactly)

CORRECT    80
COIN_FLIP  14   (near-even, |t_att-t_def|/min <= 10%, project standing rule #4 -- not graded)
ABSTAIN    46   (Gatot-kit constants unmeasured for this configuration -- never a guess)
WRONG       3   (see §4 -- all three are OUT of the Gatot-kit's scope)

W6 gate: FAIL (WRONG == 0 required) -- 143 scored (80 correct + 14 coin_flip + 46 abstain + 3 wrong)
```

### ABSTAIN breakdown (46 rows)

| reason | n | rows |
|---|---|---|
| `gatot_gate_unmodeled` — K(Lancer→Infantry) is factorized, not measured | 14 | the 4 Lancer count-threshold pairs (`AlpacaMueller_40/41v1`, `LabRat_66/67v1`) + the 10 `LabRat_1v1_T1Lan…Gatotlvl1` / `MuellerAlpaca_v4_R01–R04/R11/R12,R14` Lancer-dealer rows |
| `gatot_gate_unmodeled` — no measured budget B for the target's Gatot identity (`'Alpaca'`, `variant=True`) | 8 | `MuellerAlpaca_v4_R05–R10,R13,R15` (Marksman dealers vs Alpaca's Gatot-Infantry — a real defender, but not one of the two measured budget instruments) |
| `gatot_kit_unmeasured_inf_dealer` — Infantry dealer vs unmeasured-kit Gatot target, naive clock currently decisive | 24 | `MuellerAlpaca_v5_R02,R03,R04,R06,R07,R08,R09` (T4/T5/T6/T7/T8/T9/T10, `M ≥ 1.29/1.74/2.58/3.34/4.27/5.43/6.89`) + 12 `MuellerAlpaca_1v1_T1Inf…` naked-mirror rows vs the same target (`M ≥ 2.12–4.40`, `defender_kills_attacker` direction) |

`M_bound_ge` rises monotonically with dealer tier for the v5 ladder (1.29 →
6.89, T4→T10) — consistent with the ADDENDUM's own bounds (1.29/1.74/2.58 at
T4/T5/T6, ≥5.96 at T10 extrapolated); this run's numbers are ≤0.5% off the
addendum's stated bounds (integer-turn ceiling vs continuous math accounts
for the residual). **`R01` (T2) and `R05` (T3) are *not* in this list** — the
naive law already calls them CORRECT (see §2, §5).

## 4 · WRONG rows (3) — all confirmed out of the Gatot-kit's scope

| id | obs | law_pred | gap | diagnosis |
|---|---|---|---|---|
| `LabRat_1v1_T1LanvT1MM_NoAttackerHero_Gordonlvl1_20260711_213859` | attacker | defender | 13.6% (ceil 22 vs 25) | No Gatot/Vulcanus on either side. A pre-existing `K(Lancer→Marksman)` [measured, 488.71] vs `K(Marksman→Lancer)` [factorized, ~167.6] cross-cell tension, just outside the 10% coin-flip band. The one-directional B6 gate already scored this row (as "in-band", using only the *observed winner's* clock — 24.5 vs band [24,26]) and never noticed the other direction (21.9) was shorter; the two-sided race is exactly what surfaces it. Fixing it needs a K-cell re-derivation (`stage6_tables.py`, off-limits this window) or a new constant (forbidden by governance) — reported only. |
| `MuellerAlpaca_1v1_T7InfvFC1T1Inf_..._20260712_151127` | defender | attacker | 325.5% (ceil 141 vs 600, obs 599) | The Gatot holder here is the **attacker** (Colonel Mueller), not the defender — the opposite polarity from the v5 ladder. Gatot only ever shields its holder as a *target*; it does not buff its holder's own offense. So the decisive attacker→defender clock (141t) involves no Gatot-defended target at all and is not rescued by any `M≥1` story on the other leg (600t, itself already close to the observed 599 using the plain law). This matches the ALREADY-OPEN "reverse-race residual" (`STAGE6_REPORT.md` §6 item 6: a Gatot-side's own kill-rate running ~2.5x slower than the law elsewhere) at ~4.3x here — Stage-7 mechanism territory (target-switching/wounded mechanics), not a Gatot-kit-gate defect. **Flagged per the project's OCR-anomaly-flag rule as well** — recommend Martin double-check this specific capture (single row, non-reproduced instrument, unlike the 9-row v5 ladder). |
| `NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus` | attacker | defender | 27.1% (ceil 70 vs 89) | Defender has **Vulcanus**, not Gatot — entirely outside the Gatot-kit's scope. Pre-existing gap already visible one-directionally in the unmodified D6 section (`Mar->Inf [measured] pred 88.2 (+29.7%) ... IMPROVED` — improved vs stage5's +31.2% but still large); the two-sided race just also flags it as a winner miss. Not a Gatot-kit defect; reported only. |

Every WRONG row is annotated in `stage6_validate.py`'s `W6_KNOWN_WRONG` dict;
any WRONG row *not* in that dict would print `"NEW finding -- not yet
investigated this window"` — none did.

## 5 · Ambiguities I did **not** resolve silently

1. **The task's literal "R02–R09" framing vs. the derived rule.** The remediation brief said to expect `MuellerAlpaca_v5 R02–R09` in ABSTAIN. My principled (monotonicity-based, stats-derived) rule abstains R02, R03, R04, R06, R07, R08, R09 — **but not R01 (T2) or R05 (T3)**, both of which the naive law already calls correctly without any amplification. R05's tier (T3) numerically falls "inside" the R02–R09 *row-number* range even though its *tier* (T3) is lower than R02's (T4) — the ladder isn't tier-monotonic in row-number order. I kept the derived (data-driven) answer rather than force-fitting the literal row list, since a hard-coded list can't distinguish R01/R05 from R02–R09 without *also* re-deriving the same monotonicity check — but flag this explicitly for Martin's sign-off.
2. **`predict_deterministic_1v1`'s `law_version`.** The task says generically "meta `law_version` becomes `stage6.5`." I read this as applying to the two-sided *race* entry point (`predict_deterministic_battle`), since the gate/abstention concept only exists where there's a race to abstain from. `predict_deterministic_1v1` (pure one-direction primitive, unaffected by this change) still reports `"stage6"`. If Martin wants it bumped too for uniformity, that's a one-line change but felt like a possible over-claim (it gained no new capability).
3. **The 3 WRONG rows are real, not swept away.** The task's own gate spec says "Gate passes iff WRONG == 0," but also says "if anything lands WRONG, investigate and report it; do NOT paper over it." I chose honesty over a green gate: `stage6_validate.py` now exits 1 (because of the new W6 gate only — all 12 pre-existing gates still PASS). I did not loosen `COIN_FLIP_BAND`, add identity-based carve-outs, or otherwise adjust the classifier to make these 3 disappear, since none of them are Gatot-kit issues and two have literally no Gatot involved at all.
4. **`gatot=True` (generic/unmeasured) vs a named variant.** `_kit_for_side` reports `{"gatot": True}` for any Gatot presence that isn't recognizably "Mueller" or "Far Seer" by name (e.g. "Alpaca"). This is a real, load-bearing modeling choice: the seam has no way to know a *specific* Gatot instance's kit level/skill rank from generic stats (the corpus's own `heroes[].level` field is `1` for every Gatot occurrence, including the "Alpaca Lv64/S8" instance per the addendum — a schema/ingestion limitation, not something this window can fix). A live caller who only knows "the enemy has Gatot" should pass `{"gatot": True}`; only a caller who specifically knows the defender is one of the two measured instruments should pass the named token.
5. **Multi-count Gatot-Infantry targets.** The gate requires `target["count"] == 1` to fire at all (matching the only evidence that exists — every Gatot-Infantry target in the corpus is a single unit). A hypothetical multi-unit Gatot-Infantry front is untested and falls through to the plain law untouched — I did not invent a generalization for it.

## 6 · Gate outputs

**1. `py -m wos_sim.formula_research.stage6_validate`** — exit 1 (new W6 gate only; all 12 pre-existing gates PASS):
```
    PASS  A6 pass count >= stage5 (85/91 report)
    PASS  A6 predictions identical except fallback->measured cells
    PASS  B6 in-band count >= stage5
    PASS  B6 ENIF1b alliance-flip races all correct
    PASS  C6 beast rows identical
    PASS  D6 measured-cell moved rows improved-or-equal
    PASS  D6 factorized moved rows within the +-15% estimator band
    PASS  E6 composition anchor-mode exact
    PASS  H6 budget-gate consistency checks
    PASS  H6 eight threshold battles reproduced
    PASS  H6 hero-led singles in-band under surviving family
    PASS  I6 all 232 rows accounted
    FAIL  W6 two-sided winner gate (WRONG == 0)

  OVERALL: GATE FAILURES -- see above
```
(W6 detail: `80 correct + 14 coin_flip + 46 abstain + 3 wrong`, full per-row
listing in the module's own printout — §3/§4 above are the same numbers.)

**2. `py -m wos_sim.formula_research.stage5_validate`** — exit 0, output
**byte-identical** to the pre-6.5 baseline (`diff` clean). Buckets unchanged.

**3. `py -m wos_sim.backtest`** — exit 0:
```
    winners correct: 7/13   (baseline 7)
 VERDICT: PASS - no locked battle regressed, no new silent miss.
```

**4. `py -m pytest wos_sim/predictor/tests/ -q`** — exit 0:
```
105 passed, 8 skipped, 2 xfailed, 23 subtests passed
```
(identical to the pre-change baseline; the 3 pre-existing stage2-era
formula_research failures mentioned in the task brief live outside this
test path and were not touched.)

**5. Smoke test, `api.predict_deterministic_battle`:**

*(i) normal matchup → confident winner:*
```
winner: attacker  turns: 104
meta: {
 "law_version": "stage6.5", "frozen": "2026-07-17",
 "corpus": {"path": "wos_sim/data/experiments/_corpus/TYPE1_CORPUS.json", "row_count": 232},
 "gatot_kit_status": "two-regime (measured-defender models; NOT a general law)"
}
```

*(ii) Mueller-v5-style Inf (T6) vs Alpaca-Gatot-Inf (`def_kit={"gatot": True}`) → uncertain + flag + bound:*
```
winner: uncertain  turns: None   (obs: defender, 469 -- matches the ABSTAIN row above)
meta: {
 "law_version": "stage6.5", "frozen": "2026-07-17",
 "corpus": {"path": "wos_sim/data/experiments/_corpus/TYPE1_CORPUS.json", "row_count": 232},
 "gatot_kit_status": "two-regime (measured-defender models; NOT a general law)",
 "gatot_abstain": {
  "flag": "gatot_kit_unmeasured_inf_dealer",
  "direction": "attacker_kills_defender",
  "M_bound_ge": 2.576923076923077
 }
}
```

## 7 · Still open (none are blockers for this remediation)

1. **M_gatot pinning battle** (STAGE6_EVAL.md addendum) — a Mueller Infantry
   config that actually *beats* Alpaca's Gatot-Infantry would pin the true M
   at some dealer tier; until then, all 7 v5-ladder rows + the 12 naked-
   mirror rows correctly abstain rather than guess.
2. **The 3 WRONG rows (§4)** — none are Gatot-kit defects; two need a K-cell
   re-derivation (off-limits this window, would touch `stage6_tables.py`)
   and one (`T7_151127`) looks like the already-flagged Stage-7 "reverse-
   race residual" mechanism, possibly worth an OCR double-check by Martin.
3. **Ambiguities in §5** — the R01/R05-vs-"R02–R09" framing discrepancy and
   the `predict_deterministic_1v1` law_version choice, both flagged for
   Martin rather than resolved unilaterally.
4. Everything already open in `STAGE6_REPORT.md` §6 (splitter battle, regime
   discriminator, hero-led mobs untested, Lancer G_w/G_l interpolated rungs,
   K(Lan→Inf) T3-vs-T6 tension) is unchanged by this remediation.

## 8 · Evaluator review (2026-07-18, same window) — ACCEPTED with one fix

All builder claims independently re-run and reproduced: `stage6_validate` exit 1
(12 pre-existing gates PASS; W6 = 80 correct + 14 coin_flip + 46 abstain +
3 wrong; 232/232 accounted), `stage5_validate` exit 0, backtest PASS 7/13,
suite 105 passed / 8 skipped / 2 xfailed. Monotonicity-based abstention (§2)
endorsed — R01/R05 landing CORRECT is the data-faithful outcome and supersedes
the brief's literal "R02–R09" row list. The `predict_deterministic_1v1`
law_version choice (§5.2) endorsed. The 3 WRONG rows verified out-of-scope as
diagnosed; `T7_151127` forwarded to Martin as an OCR-check card.

**One defect found and fixed (evaluator):** `_gatot_gate_rate`'s hero-led
branch suppressed the POOLED rate — `net = (d1·√n)/S(d1·√n)` — but the
2026-07-17 regime-discriminator battle (3× Vulcanus-led T6 MM vs
Mueller-Gatot T1 Inf = 4 turns, `ENIF_ANALYSIS.md` pressure-test #1) pinned
the order as **per-dealer suppression, then √N pooling**. Fixed to
`net = √n · d1/S(d1)`. Verified: the discriminator now gives ceil(3.842) = 4 =
observed through the fixed code path (the old order gives ceil(2.952) = 3, the
rejected model); n=1 is order-invariant, so every hero-led corpus row and all
gate outputs are numerically identical after the fix (battery re-run: same
80/14/46/3, same 12 PASS + W6 FAIL, s5v exit 0, suite unchanged). No corpus
row exercises n>1 hero-led — the discriminator JSON is still pending
ingestion, which is exactly why the gates could not catch this.

**Verdict: Stage 6.5 remediation ACCEPTED** (with the pooling-order fix).
W6 stands as an honest FAIL — the 3 WRONG rows are real, known, out of the
kit's scope, and wait on the K-cell rederivation / Stage-7 mechanisms /
Martin's OCR check of `T7_151127`.

### 8.1 Addendum (2026-07-18 evening) — n>1 hero-led pooling order UNPINNED

The "3× Vulcanus T6 MM = 4 turns" regime-discriminator battle that justified
the evaluator's per-dealer-suppression-then-√N fix turned out, on Martin's
report check, to be a **1v1** (6 turns — an R12 replicate, now ingested as
`..._20260718_164811`). No n>1 hero-led battle exists. The per-dealer order is
retained as the only choice consistent with the n=1 S-curve solves, but it is
now **unvalidated for n>1** (no corpus row exercises it). The real 3-dealer
battle remains the one-battle discriminator. Fresh-data scorecard for the kit
gate (2026-07-18 pair + discriminator): 3/3 winners; naked-MM budget-cap
branch EXACT (150.0 vs 150); S-curve branch 7 vs 6 (+1 turn); Inf-dealer
residual +18-21% (open).
