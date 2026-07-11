# Clean-Room Deterministic Battle Formula Derivation

## Purpose / Big Picture

Build an executable, auditable process for deriving and testing the deterministic Whiteout Survival battle formula from Martin's controlled reports. The user-visible result is not merely a proposed equation: it is a saved per-report table showing observed versus predicted winner, turns, survivors, and available skill counters, together with the exact code and command that produced it. The 70-report NanoMart corpus is the derivation corpus. Complete non-Fire-Crystal Far Seer reports are a held-out validation corpus and must not influence fitted parameters.

No statement may use the words “exact,” “verified,” or “solved” unless the corresponding executable acceptance gate passes. Source facts, implementation assumptions, fitted parameters, and hypotheses must be labelled separately.

## Progress

- [ ] Establish a canonical, duplicate-aware manifest of eligible NanoMart reports and quarantine incomplete or contradictory records.
- [ ] Implement a reproducible replay/evaluation harness and independently reproduce the rejection of DeepSeek's published kernel.
- [ ] Derive algebraic constraints from the 1v1 clocks and count-scaling controls, then test candidate kernel families without report-specific parameters.
- [ ] Emit the complete NanoMart observed-versus-predicted table and classify the best model honestly as rejected, partial, or exact.
- [ ] Run the frozen best NanoMart model against the untouched complete Far Seer holdout and emit a separate residual table.
- [ ] Complete the contamination audit, update governing documentation, and record the final outcome and remaining unknowns.

## Surprises & Discoveries

- The exec-plan skill expects `docs/PLANS.md`, but this repository does not contain that template. This plan uses every mandatory section specified by the skill itself.
- `ENGINE_REBUILD/DEEPSEEK_KERNEL_VALIDATION.md` claims an executable 14-row replay, but its cited `scratchpad/validate_deepseek.py` is absent. Treat the document as an unverified report until the result is independently reproduced.

## Decision Log

- 2026-07-11: Far Seer is holdout-only. It cannot be used to choose constants, formula shape, rounding, or skill semantics.
- 2026-07-11: Candidate formula families may use shared global or documented class/mechanic parameters, but no per-report scalar, identity-specific adjustment, or hidden branch keyed to a fixture name.
- 2026-07-11: A failed exact search is an acceptable outcome. The deliverable must preserve falsifying examples and residuals rather than force a neat formula.

## Outcomes & Retrospective

(fill when complete)

## Context and Orientation

The repository root is `E:/WOS/Battle Simulator`.

The NanoMart source fixtures are `wos_sim/data/experiments/NanoMart_*.json`. They use several schemas created from screenshots and PDFs. `wos_sim/data/experiments/NANOMART_EXPERIMENT_LEDGER.md` is a human-readable consolidation, not an independent source of truth. The canonical manifest must be built from JSON and must identify duplicate captures, corrected/mislabelled files, missing Lethality/Health panels, inferred turn ranges, hero skill levels, and troop passives.

The complete Far Seer holdout is described by `wos_sim/data/experiments/FARSEER_NONFC_EXPERIMENT_LEDGER.md` and sourced from `wos_sim/data/farseer_infantry_ladder.json`, `wos_sim/data/farseer_set3.json`, `wos_sim/data/farseer_set4.json`, and `wos_sim/data/farseer_set6.json`.

Troop base A/D/L/H means Attack, Defense, Lethality, and Health. Base values come from `wos_sim/troop_catalog.py`; the FC reference is `docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json`. Effective stats combine base values with captured panel percentages and documented battle-time skill modifiers. Missing panel values must remain explicit assumptions rather than silently becoming zero.

A hidden-HP model tracks remaining health continuously. A live-count rule maps continuous HP back to active troop count. A damage kernel maps attacker A/L and defender D/H to damage. A frontage rule maps live count to side output. None of those structures is accepted merely because it sounds plausible.

The rejected DeepSeek proposal is documented in `ENGINE_REBUILD/DEEPSEEK_KERNEL_VALIDATION.md` and the user-supplied share transcript. Its rational constants fail its own equations, and its published HP-loop pseudocode discards whole-troop HP. The new harness must encode the published model faithfully enough to reproduce its rejection, with no reliance on the missing scratchpad script.

## Plan of Work

### Milestone 1: Canonical data manifest

Create a read-only loader that normalizes the heterogeneous NanoMart fixtures into one schema: source path, capture identity, troop groups, base stats, panels, hero skills, passive skills, observed result, survivor buckets, and turn evidence. The loader will fail closed when a required input is absent. It will emit a manifest and an exclusions table. Proof is a deterministic count with every source file either included once or explicitly excluded with a reason.

### Milestone 2: Replay and evaluation harness

Implement a small standalone formula-research package separate from the production engine. It will accept a candidate model, replay eligible controls, and write CSV/Markdown residuals. First implement the DeepSeek kernel exactly as written and a corrected-HP variant. Proof is an independently generated rejection table with direct arithmetic unit tests for the five claimed derivation equations.

### Milestone 3: Constraint derivation and model search

Use the one-unit reports to derive lower bounds and incompatibilities before numerical fitting. Search only identifiable shared model families. Candidate families will include persistent HP with alternative live-count rounding, count/frontage exponents, difference/ratio Attack-Defense terms, Lethality placement, Health mapping, caps/floors, and deterministic skill ordering. Search results must include parameter bounds, objective definition, and train/diagnostic splits. Rational-looking constants receive no preference unless independently supported.

### Milestone 4: NanoMart report card

Freeze the best candidate and emit all eligible NanoMart rows. Report exact counts, error distributions, worst rows, and structural failure clusters. Classify the result as `REJECTED`, `PARTIAL`, or `EXACT`. `EXACT` requires every eligible deterministic row to meet its documented discrete tolerance and no unresolved input assumption.

### Milestone 5: Far Seer holdout

Without changing the model, replay complete Far Seer rows supported by the same mechanics. PvE-only beast inputs may be supplied from source facts, but no PvE tuning is allowed. Emit a separate table. Any domain-specific rule required by evidence must be proposed after the frozen holdout result, not inserted retroactively.

### Milestone 6: Contamination cleanup and handover

Search project documentation and code for DeepSeek constants or unsupported “verified” claims. Mark rejected claims, link reproducible outputs, and preserve historical material as rejected evidence. Complete this plan with an honest retrospective and move it to `docs/exec-plans/completed/` only when all acceptance work is done.

## Concrete Steps

Run from `E:/WOS/Battle Simulator`:

1. `py -m wos_sim.formula_research manifest`
   Expected: exits zero; prints the number of discovered, included, duplicate, and excluded NanoMart fixtures; writes deterministic manifest artifacts.
2. `py -m wos_sim.formula_research evaluate --model deepseek`
   Expected: exits zero as a completed evaluation but reports model status `REJECTED`; writes per-report residuals and five equation checks.
3. `py -m wos_sim.formula_research search --corpus nanomart`
   Expected: writes candidate parameters and a complete training/diagnostic report; never claims exact unless all gates pass.
4. `py -m wos_sim.formula_research evaluate --model best --corpus nanomart`
   Expected: writes the frozen NanoMart report card.
5. `py -m wos_sim.formula_research evaluate --model best --corpus farseer --frozen`
   Expected: writes the held-out Far Seer report without changing parameters.
6. `py -m pytest wos_sim/predictor/tests -q -p no:cacheprovider`
   Expected: existing predictor tests remain green except already documented expected failures/skips.

## Validation and Acceptance

The process is accepted when:

- Every NanoMart JSON source is represented exactly once in the manifest or explicitly excluded with a source-specific reason.
- The five DeepSeek equations are evaluated numerically and shown not to be solved by the published constants.
- Every model evaluation writes machine-readable and human-readable per-report output.
- Re-running the same command produces identical deterministic artifacts.
- The best-model label follows objective gates: no narrative override can promote `PARTIAL` to `EXACT`.
- The Far Seer evaluation reads frozen parameters and cannot invoke fitting code.
- No production engine behavior changes until a candidate is separately approved after this research completes.

## Idempotence and Recovery

Research outputs are generated under `ENGINE_REBUILD/formula_research/` and may be overwritten deterministically. Source fixtures are read-only. The production engine is not modified during derivation. If a loader assumption is wrong, fix the normalized manifest and regenerate all downstream outputs; never edit residual tables manually. Git changes remain scoped to the plan, research package, tests, and generated audit artifacts. Existing unrelated dirty-worktree changes must not be reverted or folded into research commits.
