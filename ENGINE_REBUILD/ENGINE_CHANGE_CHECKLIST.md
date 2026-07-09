# Engine calibration — THE governing rule (Martin, 2026-07-09) — DO NOT FIT TO NOISE

**This rule overrides every calibration decision below.**

Battle reports are exactly TWO kinds:

- **Type 1 — deterministic (NO proc skills).** Same inputs → same survivors/kills,
  every time (Lv/T1-T6 troops, or any battle with no hero/troop procs). The
  outcome is a KNOWN function of stats + mechanics with ZERO free parameters.
  **These are the ONLY legitimate calibration targets. Fit them EXACTLY — to a T,
  0 exceptions.**
- **Type 2 — has procs (Ambusher, Volley, Crystal Gunpowder, hero procs).** The
  report gives how MANY times each skill fired, never WHEN. One report is ONE
  sample of millions of proc-timing permutations — a SIGNAL, not ground truth.

**The rules:**
1. **If every Type 1 report fits, NO fudge factor may exist.** A fudge (a
   non-physical knob like an attacker-bias `def_k`) is an admission that a real
   mechanic is missing or wrong. FIX THE MECHANIC — never paper over it with a
   knob. Every knob must map to a real, stat-derived mechanic or be deleted.
2. **NEVER regression-fit / calibrate to a Type 2 report.** Treat it as a signal:
   reproduce the proc COUNTS, Monte-Carlo ≥10k runs, build the outcome
   distribution, and ask "is the real outcome inside it?" Inside (not "impossible")
   → **do NOTHING**, no calibration, no fudge. Only an IMPOSSIBLE outcome (outside
   the entire distribution) implicates the engine. A cluster of edge cases is NOT
   proof of a bug — you cannot conclude "the engine is wrong" from within-
   distribution samples.
3. **Never reason about real battles from synthetic equal-stat "mirrors."** Real
   reports NEVER have exactly-equal stats (each player's gear/island/expert/
   research differ), so mutual annihilation is not a real outcome to chase. Always
   capture BOTH sides' real Stat Bonuses (see the wos-battle-report skill).

Why this matters: we previously calibrated `def_k=0.45` to force-fit noisy Type-2
PvP winners, which BROKE the deterministic Type-1 mirror (engine 57% vs real
24%). That was fitting noise at the expense of ground truth. Phase plan: (1) nail
Type 1 with 0 fudge, (2) delete the Type-2 fudges, (3) validate Type 2 by
distribution only (start with single-skill reports where all proc permutations
are enumerable).

---

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
