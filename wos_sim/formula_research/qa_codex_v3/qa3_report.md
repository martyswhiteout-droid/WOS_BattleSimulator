# Type-1 deterministic seam QA — V3

## Verdict

**WIRING QA: FAIL.** The 170-row corpus replay is wired consistently with the validator and exactly matches the expected scorecard, but W2/W5/W6 expose production-seam honesty and metadata defects.

W1 scorecard: **151 CORRECT / 15 COIN_FLIP / 1 ABSTAIN / 3 WRONG** across 170 rows — exact match to V3 expected.

## Headline wiring findings

1. **SEAM BUG — documented Vulcanus kit is not self-contained.** A legal call with `def_kit={"vulcanus": true}` returns a confident **attacker** (271t vs 301t; 11.07% gap). Applying the documented S1/S2/S3 folds independently reverses it to a confident **defender** (256t vs 283t; 10.55% gap). The validator avoids this through a private caller-side NanoMart helper; a normal caller can omit it without warning.
2. **SEAM BUG — Alpaca 205-Lancer clock is outside the required bracket.** The seam returns 648 turns; V3 requires [544,638], and independent paired-(K,B) arithmetic gives 575 on both branches. The extra drift is the composition layer's 1.125 solo-tank multiplier being applied after the budget gate already produced the full target kill clock.
3. **SEAM BUG — Gatot target `count>1` silently bypasses the kit gate.** The public, schema-valid input receives a confident plain-law result instead of an honest abstention outside the measured single-target regime.
4. **SEAM BUG — degenerate inputs crash internally.** `count=0` and either empty army raise `IndexError`; zero effective Attack raises `ZeroDivisionError`. No clean seam validation error is returned.
5. **SEAM BUG — n>1 hero-led extrapolation is not explicitly flagged.** The S-curve + √N path runs, but its flags do not identify the n>1 extrapolation as unvalidated.
6. **FROZEN-ARTIFACT BUG — metadata is stale.** `stage6_tables.json` declares 238 rows while the corpus and deterministic re-emission contain 243. Re-emission is stable; the only JSON value difference is `corpus.row_count`.
7. **PROVENANCE GAP — Far Seer aura cross-check.** The registry's hero-sheet Expedition value is 186.45 pp, while the named panel pair differs by 188.60 pp (+2.15 pp). This does not change the nearest-neighbour state call, but the panel-pair provenance is not exact (unlike Mueller and Alpaca).

## W1 — corpus replay

| classification | actual | expected |
| --- | --- | --- |
| CORRECT | 151 | 151 |
| COIN_FLIP | 15 | 15 |
| ABSTAIN | 1 | 1 |
| WRONG | 3 | 3 |

Known-open rows were reproduced without retuning:

- `LabRat_1v1_T1LanvT1MM_NoAttackerHero_Gordonlvl1_20260711_213859`
- `MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+194.1D+172.2L+122.0H+118.7_DefInfA+514.1D+506.9L+115.0H+114.1_Gatotlvl1_AlpacaFC1T1_NoDefenderHero_20260712_151127`
- `NanoMart_1v1_T1MMvT1Inf_NoAttackerHero_Vulcanus`
- E3a honest abstention: `MuellerAlpaca_1v1_T7InfvFC1T1Inf_GatotAurad_AlpacaFC1T1Vulcanus_20260719_121104`.

The seam and the final validator W6 classification agree on every row: **0 per-row differences**. Validator W6 counts were {'CORRECT': 151, 'COIN_FLIP': 15, 'ABSTAIN': 1, 'WRONG': 3}.

Independent V2 clock arithmetic matched 52 directly comparable rows. Four non-Nano rows differ because W1/validator supply Vulcanus/Seo folds only through the private NanoMart caller helper; they are **INPUT-CONSTRUCTION** discrepancies, not arithmetic errors:

- `MuellerAlpaca_1v1_T6InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+176.2D+169.0L+109.7H+109.3_NoAttackerHero_AlpacaFC1T1VulcanusNoGatot_20260718_161706`: V2 (965, 78) vs seam (1133, 75).
- `MuellerAlpaca_1v1_T7InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7_DefInfA+176.2D+169.0L+109.7H+109.3_NoAttackerHero_AlpacaFC1T1Vulcanus_20260718_235302`: V2 (1141, 76) vs seam (1340, 73).
- `MuellerAlpaca_1v1_T7InfvFC1T1Inf_Gordonlvl51_AlpacaFC1T1Vulcanus_20260719_121239`: V2 (1141, 76) vs seam (1340, 73).
- `MuellerMiniMart_1v1_T6InfvT1Inf_NoAttackerHero_Vulcanus_20260719_121806`: V2 (5479, 14) vs seam (6434, 14).

## W2 — edge fuzz matrix

| probe | expected | actual | result | class |
| --- | --- | --- | --- | --- |
| missing_panel_known_copy | ABSTAIN | uncertain; abstain={"detail": "Gatot target present but copy/state unresolved (copy 'alpaca', state None) -- budgets are measured per (copy, aura'd) only; pass unit panels or an explicit gatot_state", "flag": "gatot_gate_unmodeled"} | PASS | — |
| missing_panel_side_swap | mirror ABSTAIN | {"first": {"crashed": false, "result": {"winner": "uncertain", "turns": null, "att_deaths": [[169, "Lancer"], [445, "Lancer"], [721, "Lancer | PASS | — |
| halfway_panel_ambiguous | ABSTAIN | uncertain; abstain={"detail": "Gatot target present but copy/state unresolved (copy 'alpaca', state None) -- budgets are measured per (copy, aura'd) only; pass unit panels or an explicit gatot_state", "flag": "gatot_gate_unmodeled"} | PASS | — |
| halfway_panel_side_swap | mirror ABSTAIN | {"first": {"crashed": false, "result": {"winner": "uncertain", "turns": null, "att_deaths": [[230, "Lancer"], [606, "Lancer"], [982, "Lancer | PASS | — |
| unknown_copy_true | ABSTAIN | uncertain; abstain={"detail": "Gatot target present but copy/state unresolved (copy None, state None) -- budgets are measured per (copy, aura'd) only; pass unit panels or an explicit gatot_state", "flag": "gatot_gate_unmodeled"} | PASS | — |
| unknown_copy_explicit_aurad | ABSTAIN (state cannot supply copy identity) | uncertain; abstain={"detail": "Gatot target present but copy/state unresolved (copy None, state 'aurad') -- budgets are measured per (copy, aura'd) only; pass unit panels or an explicit gatot_state", "flag": "gatot_gate_unmodeled"} | PASS | — |
| unknown_copy_explicit_inert | confident plain law (all inert copies B=0) | attacker | PASS | — |
| known_copy_explicit_aurad_no_panel | defender | defender | PASS | — |
| known_copy_explicit_inert_overrides_aura_panel | confident plain law; explicit state wins | attacker | PASS | — |
| inert_gatot_exact_plain_equivalence | identical clocks/winner; no folds | {"inert": {"crashed": false, "result": {"winner": "defender", "turns": 74, "att_deaths": [[74, "Infantry"]], "def_deaths": [[599, "Infantry" | PASS | — |
| vulcanus_led_n3_runs_scurve_sqrtN | runs S-curve + sqrt(N) | attacker | PASS | — |
| vulcanus_led_n3_unvalidated_flag | explicit n>1 unvalidated flag | attacker | FAIL | SEAM_BUG |
| both_clocks_over_1500_cap | capped defender at 1500 | defender | PASS | — |
| count_zero | clean validation error | IndexError: list index out of range | FAIL | SEAM_BUG |
| empty_attacker_army | clean validation error | IndexError: list index out of range | FAIL | SEAM_BUG |
| empty_defender_army | clean validation error | IndexError: list index out of range | FAIL | SEAM_BUG |
| zero_effective_attack | clean validation error or capped zero-rate side | ZeroDivisionError: float division by zero | FAIL | SEAM_BUG |
| alpaca_lancer_edge_204 | defender | defender | PASS | — |
| alpaca_lancer_edge_205 | attacker; kill [544,638] | attacker | FAIL | SEAM_BUG |
| alpaca_lancer_edge_220 | attacker | attacker | PASS | — |
| plain_side_swap_mirror | winner/clocks mirror | {"first": {"crashed": false, "result": {"winner": "attacker", "turns": 107, "att_deaths": [[676, "Infantry"]], "def_deaths": [[107, "Marksma | PASS | — |
| gatot_205_side_swap_mirror | winner/clocks mirror | {"first": {"crashed": false, "result": {"winner": "attacker", "turns": 648, "att_deaths": [[169, "Lancer"], [445, "Lancer"], [721, "Lancer"] | PASS | — |
| mixed_dealer_stacks_vs_aurad_gatot | ABSTAIN | uncertain; abstain={"detail": "multi-stack dealer side vs an aura'd Gatot target: volley pooling across mixed stacks is unmeasured", "flag": "gatot_gate_unmodeled"} | PASS | — |
| gatot_target_count_2 | ABSTAIN outside measured single-target gate | attacker | FAIL | SEAM_BUG |

Result: **17/24 passed; 7 findings.** Side-swap checks mirrored correctly on the plain, measured-Gatot, missing-panel, and ambiguous-panel paths. The 204/220 paired-budget verdicts were correct; 205 had the clock error described above.

## W3 — production app-path isolation

- Golden-anchor backtest: **PASS, 7/13**, exit 0.
- `predict()` source is byte-identical to Git HEAD: **True**; both hashes `427abdc88398b4d7f9df060c80ed5a3d129135d91aaa736e468ec2c11eccf719`.
- Four constructed production `predict()` calls completed while the deterministic seam was monkeypatched to raise: **PASS**; meta leaks: **0**.
- Reloading `api.py` opened **0** Stage-6/formula files.
- `server.py` routes: `@app.exception_handler(InvalidInput)`, `@app.get("/api/health")`, `@app.post("/api/predict")`, `@app.post("/api/battle")`; deterministic seam route present: **False**.

## W4 — test-suite audit

- Predictor tests: **PASS**, 123 passed / 0 skipped / 2 xfailed (exit 0). The prompt expected 115/8/2; the same 125-test total ran, but FastAPI was available, so the eight `TestServer` cases passed instead of skipping. This is an environment difference, not a regression.
- Formula-research tests: **PASS**, 24 passed (exit 0); exact expected count.

### Recommended seam-test additions

1. Missing `panel_pct` on both attacker- and defender-side Gatot targets.
2. Unknown copy plus explicit `gatot_state` (`aurad` and `inert`) and conflicting explicit state vs panel detector.
3. n>1 Vulcanus-led S-curve behavior with an explicit unvalidated-extrapolation flag assertion.
4. `count=0`, empty attacker/defender armies, and zero A/L validation with clean public errors.
5. Gatot target `count>1` must abstain instead of falling through to plain law.
6. Exact 205-Lancer clock bracket [544,638], not the current coarse [500,700] assertion.
7. Attacker/defender side-swap invariance for plain, gated, and abstention paths.
8. Multi-stack dealers versus aura'd Gatot, input non-mutation, and 1500+ cap behavior.
9. `predict_deterministic_1v1` metadata/content tests; the current seam file exercises only battle-level metadata.
10. A public-kit test proving Vulcanus folds are either applied automatically or rejected unless explicit offense multipliers are supplied.

## W5 — frozen constants

- Emit hashes: `d43bb666c7af89cf619bc1fe3e0d1f094438a8f1e443b9f37a08d3f1a8059935` and `d43bb666c7af89cf619bc1fe3e0d1f094438a8f1e443b9f37a08d3f1a8059935` — byte-identical: **True**.
- Current hash: `6dee5dd40fe741329321c0e8d3c6378c7adf2eecfcbe6291e4ec1e10ac431c62` — byte-identical to emission: **False**.
- Law version current/emitted: `stage6.6` / `stage6.6`.
- Row count current/emitted/actual: **238 / 243 / 243**.

| B branch | K | G_w | B calculated | B frozen | 204 caps | 205 forward |
| --- | --- | --- | --- | --- | --- | --- |
| edge | 90.38 | 1.625 | 879.241 | 879.3 | True | 575.000 |
| factorized | 83.66 | 1.625 | 949.909 | 949.9 | True | 575.000 |

| copy | baseline A | aura A | panel delta | Expedition | difference | ≤0.1 pp |
| --- | --- | --- | --- | --- | --- | --- |
| mueller | 179.1 | 481.0 | 301.90 | 301.93 | -0.03 | True |
| alpaca | 176.2 | 514.1 | 337.90 | 337.85 | +0.05 | True |
| farseer | 0.0 | 188.6 | 188.60 | 186.45 | +2.15 | False |

The two B branches reproduce the 204 cap and 575-turn 205 source exactly within published precision. Mueller and Alpaca panel deltas match their Expedition auras; Far Seer carries the 2.15 pp provenance offset noted above.

## W6 — adversarial wiring hunt

**Finding reproduced:** a legal kit-only Vulcanus input produces a confident winner opposite the fully measured deterministic folds. This is the headline contract/wiring failure. Six real Nano rows also change CORRECT↔COIN_FLIP classification when the validator-only caller folds are omitted; the known Nano MM→Inf row remains confidently WRONG.

No additional corpus WRONG rows beyond the known three: **0**. No unexpected measured abstentions beyond E3a: **0**.

## Final validator cross-check

`stage6_validate` was run once after the independent lock and exited 1. W6 matched this audit exactly. Its overall failure is the expected three known WRONG rows plus the known factorized Lan→Lan gate. It accounts **243/243**, although its regression label still says `all 232 rows accounted`—another stale display string.

## Evidence

- `qa3_results.csv`: all 170 W1 rows plus all 24 W2 probes.
- `pre_crosscheck_v3.lock.json`: immutable hashes before the validator run.
- Raw backtest, pytest, table-emission, and one-time validator logs are retained in this directory.
