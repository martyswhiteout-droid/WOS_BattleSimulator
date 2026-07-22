# QA BRIEF v3 — WIRING/ADOPTION audit of the Type-1 deterministic law in the engine seam (for Codex)

Different mission from v1/v2. Those validated the LAW (re-implement the physics
independently, score the corpus). This round validates the WIRING: is the
frozen law correctly and completely adopted by the engine's Python seam, does
the seam behave honestly at its edges, and is the production app-path
untouched? You may now IMPORT and CALL the project's code — calling it is the
point — but you must construct every INPUT independently from the corpus, and
verify every OUTPUT against your own v2-style arithmetic where applicable.

## Hard rules
1. Never fabricate a number; every figure comes from code you wrote and ran.
2. Read-only repo; write ONLY inside `wos_sim/formula_research/qa_codex_v3/`.
3. Failures are findings; no tunable constants.
4. If a seam output looks wrong, verify with your own arithmetic (reuse your
   `qa_type1_v2.py` law implementation) before reporting — classify each
   discrepancy as SEAM BUG vs YOUR-ARITHMETIC vs KNOWN-OPEN.

## The seam under test

- Entry points: `wos_sim.predictor.api.predict_deterministic_battle(att_army,
  def_army, att_kit=…, def_kit=…)` and `predict_deterministic_1v1`. These wrap
  `wos_sim/formula_research/stage5_composition.predict_battle` + the frozen
  `stage6_tables.json` (`law_version` must read `"stage6.6"`).
- Army dicts: `[{"cls","tier","count","eff":{A,D,L,H},"panel_pct":{...}}]` —
  `panel_pct` feeds the Gatot hero-STATE detector (aura'd vs inert, per-copy
  registry in the tables' `hero_state` block; read `docs/HERO_KITS.md` first).
- Kit descriptors: `{"gatot": "mueller"|"alpaca"|"farseer"|True,
  "gatot_state": "aurad"|"inert" (optional), "vulcanus": bool}`.
- The PRODUCTION app path (`predict()` in api.py, `server.py`, the
  `pvp_turn_engine`) must be COMPLETELY UNAFFECTED by all of this — verifying
  that isolation is part of your job.

## Test program (all six sections required)

**W1 — corpus replay through the seam.** For every one of the 243 corpus rows
(`_corpus/TYPE1_CORPUS.json`) that reduces to single-class sides with a winner:
build the army/kit inputs YOURSELF from the row (classes→army with eff+panel;
heroes+name→kit tokens per HERO_KITS.md), call `predict_deterministic_battle`,
classify four-way (CORRECT / COIN_FLIP ≤10% clock gap / ABSTAIN / WRONG).
Expected: 151 CORRECT / 15 COIN_FLIP / 1 ABSTAIN (the E3a Vulcanus-led
INFANTRY-dealer-vs-aura'd-Gatot cell) / 3 WRONG (the known list:
`LabRat_..._213859`, `..._151127`, `NanoMart_1v1_T1MMvT1Inf_..._Vulcanus`).
Any deviation from that scorecard = a wiring finding. Then diff your
classification per-row against `stage6_validate.py`'s W6 section (run once at
the end): any row where the SEAM gives you a different verdict than W6 gives
the validator (same code underneath — differences expose input-construction
sensitivity or hidden validator-only folds; the known one: the validator
applies `_nanomart_offense` hero folds for NanoMart rows — replicate that and
document any OTHER fold the seam does NOT apply by itself).

**W2 — behavioral edge fuzzing.** Systematically probe: missing `panel_pct`
on a Gatot side (must abstain, not guess); panels halfway between baseline and
aura'd (ambiguous ⇒ abstain); unknown copy token `True`; unknown copy with
explicit `gatot_state` (should that override? document actual behavior);
inert Gatot (must add NO folds, race plain); n>1 hero-led dealers (S-curve +
√N — runs but flag); zero/1500+ turn caps; count=0 or empty armies (crash vs
clean error); Lancer-dealer-vs-Alpaca branch pairing (204 ⇒ defender, 205 ⇒
attacker with kill in [544,638], 220 ⇒ attacker — the coherent (K,B) pairs).
Every crash, silent guess, or asymmetric behavior (att vs def side swap must
mirror) is a finding.

**W3 — app-path isolation.** Prove `predict()` (the web app's entry) is
byte-identical to its pre-stage6.5 behavior: run the golden-anchor backtest
(`py -m wos_sim.backtest` — must PASS 7/13) and call `predict()` on 3–5
constructed inputs, confirming none of the new meta keys (`law_version`,
`gatot_abstain`) leak into its output and no deterministic-law code executes
in its path (e.g. import-time side effects). Also confirm `server.py` exposes
NO route to the deterministic seam yet (that is deliberate).

**W4 — test-suite audit.** Run `py -m pytest wos_sim/predictor/tests/ -q`
(expect 115 passed / 8 skipped / 2 xfailed) and
`py -m pytest wos_sim/formula_research/ -q` (expect 24 passed). Read
`test_deterministic_seam.py` critically: list any seam behavior YOU probed in
W2 that the suite does not cover — those are recommended test additions.

**W5 — frozen-constants integrity.** Verify `stage6_tables.json` re-emits
byte-identically (`py -m wos_sim.formula_research.stage6_tables --emit`
twice + hash), that every `hero_state` constant matches its named provenance
row in the corpus by YOUR arithmetic (B_alpaca from the 204/205 rows with
G_w^Lan(6)=1.625 and both K branches; the Expedition auras vs the panel
deltas of the named row pairs), and that `law_version`/`row_count` metadata
match reality (243).

**W6 — adversarial wiring hunt.** Actively try to construct a LEGAL input
(valid army dicts + kit tokens a live caller could plausibly send) that makes
the seam return a CONFIDENT verdict that your independent arithmetic says is
wrong, or an abstention where the physics is fully measured. Any such input
is the headline finding.

## Known-open list (reproduce, don't "fix")
The 3 WRONG rows; the E3a abstain (unmeasured Vulcanus-led-Infantry S-curve
cell — a monotonicity upgrade is a KNOWN possible improvement, recommend
don't implement); K(Lan→Lan) instrument spread 126.2/149.8/176; the
K(Lan→Inf) T3-vs-T6 tension; the Alpaca-FC1T1-target ×1.17 family; the
inert-Gatot-dealer slowdown (out of production domain per the maxed-hero
policy).

## Required output (in `qa_codex_v3/`)
1. `qa3_results.csv` — per-row W1 classifications + per-probe W2 outcomes.
2. `qa3_report.md` — scorecard vs expected; every discrepancy classified
   (SEAM BUG / input-construction / known-open); the W2 fuzz matrix; the W3
   isolation proof; W4 coverage gaps; W5 integrity results; W6 verdict.
3. An explicit list of recommended seam-test additions (from W4/W2).
