# Engine-change checklist — MANDATORY back-test (Martin's directive, 2026-07-09)

**Any change to the engine or `TURN_PARAMS` MUST pass this before it is kept.**
This is the guardrail that stops a fit-to-one-report change from silently
blowing up battles that were already calibrated.

## The one command

```
py -m wos_sim.backtest
```

It replays **every** calibrated real battle through the production engine and prints:
1. **Winner lock** — the 13 real battles; which winners are correct vs the
   locked baseline (`wos_sim/data/golden_baseline.json`).
2. **Composition magnitudes** — the deterministic controlled experiments
   (mirror + counter matchups) vs their real survivor%.
3. **VERDICT: PASS / FAIL** (exit 0 / 1).

## The rule (blocking)

- Run it **before** your change (record the baseline) and **after**.
- The verdict is **FAIL** if the change **breaks any locked-pass winner** or
  **adds a new silent wrong-winner** (a confident wrong call with no coin-flip
  flag). A FAIL change is **not shippable** — revert or rework.
- A change may **FIX** a `known_miss` (it moves into `locked_pass` — update
  `golden_baseline.json` and note it). The winner-pass count may only go **up**.
- Also enforced automatically: `regression.py` check #13 and
  `wos_sim/predictor/tests/test_golden_anchors.py`. `py -m wos_sim.regression`
  and the pytest suite must stay green.

## Why (do not skip)

Calibration is coupled: tuning a parameter to match the latest battle report
routinely flips the winner of an *earlier* battle. We have proven, measured
examples (e.g. bumping `def_k` 0.45 -> 0.60 silently breaks RAW_08; raising it
to fix the mirror magnitude breaks RAW_06/RAW_08/T12_04). The back-test makes
that damage impossible to miss.

## Data the back-test covers

- **13 real battles** (`normalize_reports.golden_anchors`): 5 T12 PvP reports +
  8 raw reports — attacker wins/losses AND defender wins/losses.
- **6 controlled experiments** (`data/experiments/`): deterministic, minimal-
  skill, in-game mirror + counter matchups (magnitude anchors).

When a NEW real report arrives: add it via `normalize_reports`, run the
back-test, and if the engine already gets its winner right, add its id to
`golden_baseline.json::locked_pass` so it is protected from then on.
