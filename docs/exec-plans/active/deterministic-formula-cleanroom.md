# Clean-Room Deterministic Battle Formula Derivation

## Purpose / Big Picture

Build an executable, auditable process for deriving and testing the deterministic Whiteout Survival battle formula from Martin's controlled reports. The user-visible result is not merely a proposed equation: it is a saved per-report table showing observed versus predicted winner, turns, survivors, and available skill counters, together with the exact code and command that produced it. The 70-report NanoMart corpus is the derivation corpus. Complete non-Fire-Crystal Far Seer reports are a held-out validation corpus and must not influence fitted parameters.

No statement may use the words “exact,” “verified,” or “solved” unless the corresponding executable acceptance gate passes. Source facts, implementation assumptions, fitted parameters, and hypotheses must be labelled separately.

## Progress

- [x] (2026-07-11 09:34Z) Established a canonical, duplicate-aware manifest: 71 JSON files discovered, 70 included, one stale user-corrected artifact excluded, 60 with turn evidence, and 10 survivor-only.
- [x] (2026-07-11 09:40Z) Implemented the replay/evaluation harness and independently rejected both DeepSeek's literal pseudocode and its charitable repaired-HP interpretation across all 70 canonical fixtures.
- [x] (2026-07-11 10:28Z) Derived 37 unique one-unit clock constraints, exposed one incompatible modeled-input pair, and tested power-law and affine persistent-HP families with five- and six-event Vulcanus schedules. All candidate families were rejected.
- [x] (2026-07-11 10:30Z) Emitted the complete 70-report observed-versus-predicted table for the best bounded-search candidate. It is `REJECTED`: 69/70 winners, 54/70 survivor pairs, and 6/60 turn ranges.
- [ ] Run the frozen best NanoMart model against the untouched complete Far Seer holdout and emit a separate residual table.
- [ ] Complete the contamination audit, update governing documentation, and record the final outcome and remaining unknowns.

## Surprises & Discoveries

- The exec-plan skill expects `docs/PLANS.md`, but this repository does not contain that template. This plan uses every mandatory section specified by the skill itself.
- `ENGINE_REBUILD/DEEPSEEK_KERNEL_VALIDATION.md` claims an executable 14-row replay, but its cited `scratchpad/validate_deepseek.py` is absent. Treat the document as an unverified report until the result is independently reproduced.
- The live experiment directory contains 71 NanoMart JSON files, not 70. The difference is the stale `NanoMart_1v1_T1LanvT1Inf_SeoYoonlvl3_Vulcanus.json` artifact that Martin explicitly corrected and asked to remove. Excluding it yields the canonical 70.
- Two included files are exact duplicate captures: the Set A T6-vs-T2 `Duplicate2` artifact and the Set B reversed-role copy of the Set A T1-vs-T1 report. They remain visible in the 70-source manifest but are flagged for de-weighting in model search.
- One Vulcanus-versus-Vulcanus source records a skill level as the literal text `not displayed`. The loader preserves it as unknown and does not coerce it to Level 1.
- DeepSeek's literal pseudocode matches 12/70 winners, 0/70 survivor pairs, and 0/60 turn observations. Repairing only its HP-conservation bug improves this to 54/70 winners, 42/70 survivor pairs, and 1/60 turn observations. Its constants solve 0/5 claimed equations.
- Two independently captured T5-Infantry-vs-T1-Infantry reports have identical modeled inputs and the same 1/0 survivor result, but disjoint inferred clocks of 79-81 and 67-69 turns. A deterministic formula over the captured fields cannot fit both.
- The wiki wording for Vulcanus S2 is "after every 5 attacks." The experiment counters are internally compatible with an empowered sixth attack (6, 12, 18, ...) when cross-checked against the assumed S3 clock, not with empowered attacks 5, 10, 15, .... This supports cadence 6 for the counter interpretation but does not independently prove the game's internal event index.
- A shared minimum-HP damage floor was tested because same-class Infantry mirrors remain near 264 turns across tiers. Adding that floor did not rescue either candidate family; the clock-first floor search matched at most 1/37 turn ranges.
- The best all-report bounded-search candidate is still structurally poor: 6/60 exact turn ranges, median absolute clock error 18 turns, and maximum error 167 turns. Its optimizer exhausted the declared 35-generation budget rather than converging, so it is only the best observed candidate, not a global optimum.

## Decision Log

- 2026-07-11: Far Seer is holdout-only. It cannot be used to choose constants, formula shape, rounding, or skill semantics.
- 2026-07-11: Candidate formula families may use shared global or documented class/mechanic parameters, but no per-report scalar, identity-specific adjustment, or hidden branch keyed to a fixture name.
- 2026-07-11: A failed exact search is an acceptable outcome. The deliverable must preserve falsifying examples and residuals rather than force a neat formula.
- 2026-07-11: Preserve all 70 canonical source fixtures in reporting, but give exact duplicate fingerprints zero additional fitting weight so repeated screenshots cannot bias parameter selection.
- 2026-07-11: Treat `deepseek_published` and `deepseek_repaired_hp` as separate rejected models. This distinguishes the delivered code defect from the independent failure of the delivered kernel constants.
- 2026-07-11: A modeled-input conflict blocks `EXACT` status independently of formula family. Keep both source captures visible and require screenshot/counter re-verification rather than silently dropping the harder row.
- 2026-07-11: Treat Vulcanus S2 cadence 5 and cadence 6 as competing hypotheses in search. Do not infer cadence from English wording alone; report the counter cross-check separately.

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
