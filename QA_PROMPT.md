# QA brief — front-end / app layer (engine assumed correct)

You are an independent QA agent. Your job: find defects in the **front-end and
the app layer** of the WoS Battle Predictor before it goes live. Report only
**confirmed, reproducible** issues — not style opinions.

## Assume correct (do NOT test)
- The **simulation engine** (`wos_sim/pvp_engine.py`, `wos_sim/proc.py`,
  `wos_sim/pvp_kernel.py`, `wos_sim/t12.py`, `wos_sim/farm_engine.py`) and its
  math. It is QA'd separately. Treat `engine_meta` / `run_batch` output as truth.
- Everything in the **40 passing unit tests** (`wos_sim/predictor/tests/`):
  construct stat model, T12 mapping, skill resolution, summary stats
  (buckets / distributions / MC error), serialization, validation, the predict
  endpoint. Don't re-derive these — assume they hold and probe *around* them.

## In scope (test this)
The app layer `wos_sim/predictor/` (construct, skills, summary, serialize,
validate, api, server) and the front-end `prototype/index.html`.

## How to run
```
# app (serves UI + API on http://localhost:8137):
.venv/Scripts/python -m uvicorn wos_sim.predictor.server:app --port 8137
# unit tests:
.venv/Scripts/python -m unittest discover -s wos_sim/predictor/tests -p "test_*.py"
```
Env: use the project `.venv` (has numpy, openpyxl, fastapi). The engine is real.

## Verified working already (confirm, then push past)
- Happy path: form → `POST /api/predict` → real forecast renders (verdict,
  8 buckets, army + per-class loss distributions, rounds, ±13% "Provisional"
  badge). No console errors, no horizontal overflow at 1360px.
- Error path: 0 troops → clean 400 → error banner, overlay dismissed.

## The risk surface — hunt here (priority order)

1. **Adversarial `/api/predict` payloads** (the server takes raw dicts). Try:
   extra/unknown fields; wrong types (string where number, list where dict);
   missing required keys (`role`, `formation`, `quality`); `null` values;
   `n` = 0 / negative / 10_000_000 (does it hang or DoS?); non-ASCII / very long
   hero names; panel keys that aren't `"Class|Stat"`; formation summing to ≠100 /
   with negatives; tier/fc/t12 fractional or absurd; both sides same role; empty
   `{}` body; non-JSON body. **Expected:** a clean 400 with `problems`, or a
   clean 422 — **never a 500 stack trace or a hang.** Report any 500/hang.

2. **`buildProfile` form-reader robustness** (`prototype/index.html`). Manipulate
   the DOM/form and Run: a hero picker with no selection; a formation slider at
   0/100; the stats panel toggled visible with edited values; switching role
   (Rally↔Garrison) mid-session; rapid double-clicks on Run/Refresh (concurrent
   requests — does the later response win, or do they interleave/flicker?).

3. **Rendering fidelity** — does the UI faithfully render `forecast_to_dict`?
   Cross-check the JSON (`POST /api/predict` directly) against the DOM: bucket
   percentages, median labels, distribution bar heights, the caliper/haze widths
   (± sampling vs ± model error), the "Validated/Provisional ±X%" badge text and
   its tooltip, deterministic matchups showing "single outcome" not a fake spread.

4. **Summary edge cases** (unit-test them): `n=1`; a single-class army; an
   all-mutual batch; an all-loss batch; a matchup where one class is absent on a
   side (per-class distribution should be `null` → UI shows "—", not `NaN`/`0`).

5. **Client failure states:** server down / unreachable; a 500 from the server;
   a slow response (does the overlay stay honest / not hang?). Reduced-motion.
   Mobile (375px) — no overflow, controls usable. Keyboard-only nav through the
   hero picker, sliders, and dropdowns (focus visible, operable).

6. **Reproducibility:** same profiles + same seed → identical forecast JSON,
   through the real stochastic engine (CRN). Different seed → within MC error.

7. **Serialization round-trip:** `profile_to_dict(profile_from_dict(d))` for a
   range of `d`; unicode hero names; missing optional fields.

8. **Server plumbing:** `/api/*` routes vs the static mount (does `/api/predict`
   ever get shadowed by the SPA mount?); a large payload; concurrent requests.

## Report format
For each confirmed defect: **file:line or endpoint · exact repro (inputs) ·
observed vs expected · severity**. Rank most-severe first. If nothing survives
verification in a category, say so. Skip: engine math, the 40 tested behaviors,
visual/taste preferences.
