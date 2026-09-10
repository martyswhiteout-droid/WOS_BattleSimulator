# ENGINE HANDOFF — the headline win% is stuck at 25% for every garrison scenario; surface what varies

**Date:** 2026-09-10 · **Author:** Claude (analysis session with Martin) · **Audience:** Engine Builder
**Owner directive (Martin, 2026-09-10):** "If it's always 25% it looks odd — I've changed formations, I've used different joiners, it is still 25%. People will not trust it. Isolate the issue and propose a change so it can surface what varies."
**Status:** diagnosis COMPLETE, reproduction scripted, fix PROPOSED (not implemented). Nothing in the engine or UI was changed by this session.

---

## 1. Symptom

`Scenarios/Gen15_50_10_40.json` (garrison Hank/Estrella/Cara + Ahmose/Gatot/Freya/Nora vs rally Hank/Dominic/Viveca + Jessie/Hendrik/Hervor/Nora, both 5-2-3, identical T12/FC10/24 quality) shows **25.0% win, "Too close to call"** in the UI, and keeps showing exactly 25.0% after any change of formation, enemy formation, or joiners. Same through the shell on :8200 (it mounts `wos_sim.predictor.server:app`) and through `api.predict` directly.

## 2. Reproduction (35 variations, n=400 each, seed 4471, same call chain as `server.py`)

`shown` = `Forecast.p_win.p` (what the UI prints). `simWin` = fraction of the n turn-engine runs the garrison actually wins. `r_own` = joiner-aware effective-strength ratio from `winprob.effective_ratio` (own/enemy). Losses are means.

| variation (own = garrison) | shown | simWin | r_own | own loss | enemy loss | display branch |
|---|---|---|---|---|---|---|
| saved file (5-2-3) | **25.0%** | 0.000 | 1.048 | 100% | 46.7% | near-even collapse |
| own 5-1-4 / 6-2-2 / 7-3-0 / 2-2-6 | **25.0%** | 0.000 | 1.02–1.06 | 100% | 40–48% | near-even collapse |
| own 4-6-0 / 3-7-0 | **25.0%** | 0.000 / 0.003 | 1.02 / 1.01 | 100% | 58.6% / 59.5% | near-even collapse |
| enemy 5-1-4 / 3-3-4 / 7-2-1 | **25.0%** | 0.000 | 1.04–1.06 | 100% | 41–60% | near-even collapse |
| own joiners none (enemy 4) | **25.0%** | 0.000 | 0.876 | 100% | 31.0% | near-even collapse |
| own 4×Nora / 4×Gatot / 4×Jessie / mirror / both none | **25.0%** | 0.000 | 0.88–1.03 | 100% | 37–58% | near-even collapse |
| own saved 4, **enemy NONE** | **88.8%** | 0.003 | 1.230 | 100% | 68.2% | decisive-DISAGREE → strength sigmoid |
| own 0.80M / 0.90M / 1.10M troops | **25.0%** | 0.000 | 0.84–1.15 | 100% | 30–57% | near-even collapse |
| own 1.15M troops | **86.6%** | 0.000 | 1.205 | 100% | 65.7% | decisive-DISAGREE → sigmoid |
| own 1.20M / 1.25M troops | 90.8% / 93.7% | 0.035 / 0.365 | 1.26 / 1.31 | 99.7% / 94.9% | 79% / 93% | decisive-DISAGREE → sigmoid |
| own **1.30M** troops | **66.5%** | **0.830** | 1.362 | 81.2% | 98.8% | blind probe demotes to near-even |
| own panel ×1.10 / ×1.15 / ×1.20 | 32.5% / 74.4% / 75.0% | 0.15 / 0.99 / 1.00 | 1.15 / 1.20 / 1.25 | 98% / 67% / 51% | 87% / 100% / 100% | near-even collapse |
| own panel ×1.30 | 100.0% | 1.000 | 1.358 | 36.4% | 100% | decisive-agree → sim value |
| **reference, engine `def_k`=1.0**, saved file | 75.0% | 1.000 | 1.048 | 50.4% | 100% | near-even collapse |
| `def_k`=1.0, own 4-6-0 | 75.0% | 1.000 | 1.022 | 35.8% | 100% | near-even collapse |
| `def_k`=1.0, own no joiners | 32.2% | 0.145 | 0.876 | 98.6% | 84.2% | near-even collapse |

Reproduce: run the script attached to this handoff (`variations.py`, also sent to Martin), or the minimal snippet in §8.

## 3. Root cause — three stacked layers

**Layer 1 — the display rule collapses the sim to one bit (`wos_sim/predictor/winprob.py::hybrid_win_prob`).**
Inside the ±20% effective-strength band the displayed value is `0.5 + (p_sim − 0.5) · DAMP` with `DAMP = 2·(NEAR_EVEN_HIT_RATE − 0.5) = 0.50`. At army scale the turn engine is near-deterministic (procs move casualties a few %, almost never the winner), so `p_sim ∈ {0, 1}` and the headline is exactly **25% or 75%**. Every input the user changes inside the band — formation, enemy formation, joiners up to a 3-vs-4 gap, ±10% troops, ±10% stats — is discarded. The joiner-aware ratio `r_own` IS computed but is unused inside the band. On the 13 real golden anchors the headline takes only the values 25% / 75% / 100% (see §4): the product has never shown any other number for a real battle.

**Layer 2 — the one bit is stuck on "garrison loses" by `def_k = 0.45` (`wos_sim/pvp_turn_engine.py:84`, `TURN_PARAMS`).**
`def_scale = rate · def_k` scales the defender's per-turn output to 0.45× the attacker's. Consequences measured above and in the 66-formation sweeps of 2026-09-09: the garrison loses 100% of runs in **every** formation and joiner mix, including a +4.8% paper-strength edge and 4-vs-0 joiners in its favour; swapping roles (same units, own = rally) turns the loss into a 100% win with 23% losses; setting `def_k = 1.0` turns the saved file into a 100% garrison win. So for any garrison scenario the collapsed bit is always 0 → always 25%. `def_k` is the documented attacker-bias fudge (`STAGE8_SPEC.md`, `ENGINE_RULES_REVIEW.md`, memory `simultaneous-resolution-and-defk-fudge`).

**Layer 3 — the band edge is a cliff and the result is not monotone.**
Crossing `|ln r| > ln 1.2` switches to the *strength sigmoid* override (`decisive and turn_owner != strength_owner`): +50k troops takes the headline from 25.0% (1.10M) to 86.6% (1.15M) while the sim still reports 0.0% holds and 100% own losses — the loss panels then contradict the headline on the same screen. Going further (1.30M) the `blind_near_even` probe (±5% swing flips the winner) forces the near-even branch again and the headline **falls** to 66.5% although the sim's own hold rate has risen to 83%. A 30% stat edge shows 100%, a 30% troop edge 66.5%, a 15% troop edge 86.6%, a 10% troop edge 25%.

Not causes (checked): the UI sends `formation` and `formation_counts` consistently (`buildProfile`, `readCounts`); the server passes `n` and `{"engine": "turn"}` unchanged; `construct.class_counts` prefers `formation_counts` (a hazard only for hand-edited JSON, see §6-D); the shell mounts the same app.

## 4. Golden-anchor guardrail today (`eval_reports.golden_regression`, n=25, seed 4471)

| engine | winners right | broken locked | fixed known-miss | near-even flagged |
|---|---|---|---|---|
| default `def_k`=0.45 | **7/13** (baseline) | — | — | 13/13 |
| `def_k`=1.0 | 6/13 | RAW_06, RAW_08, T12_04 | RAW_01, RAW_07 | 13/13 |

So flipping `def_k` to 1.0 is **gate-blocked (G12)** and is not the fix. Note the pattern: the symmetric engine fixes the Lancer-heavy garrisons that really held (RAW_01 53/41/7, RAW_07 71/29/0) and breaks the no-Marksman garrisons that really fell (RAW_06/08 61/39/0 vs 4×Nora rallies) and the thin-wall garrison (T12_04 20/10/69). No single role constant reproduces both sets: the missing mechanism is composition/joiner dynamics, which is Stage 8.1's remit, not a knob.

## 5. What must NOT change

- The `coin_flip` badge and hedged framing stay (CLAUDE.md rule 4; near-even battles are genuinely chaotic).
- No fitting to Type-2 reports; no new hand-chosen constants presented as measured (`ENGINE_CHANGE_CHECKLIST.md`; Phase A replaced the chosen `DAMP=0.10` with the measured 0.750 hit rate for exactly this reason).
- Martin's 2026-07-09 directive: joiners must move the odds; 0-vs-4 joiners must read as an underdog (~10%), and a mirror must not read 100%.
- `py -m wos_sim.backtest` gate G12: 7/13 may only increase; no new silent misses.
- Existing tests `wos_sim/predictor/tests/test_winprob_joiners.py` (symmetric near-even → `p == NEAR_EVEN_HIT_RATE`; 0-vs-4 → `p < 0.25`; own joiners lift p by > 0.10). If a proposal below changes what a *unanimous* near-even call displays, renegotiate the first assertion with Martin explicitly rather than editing it.

## 6. Proposed change (in priority order)

### A. Surface what varies — seam + UI (no engine change, highest value, lowest risk)
Add to `summary.Forecast` → `serialize.forecast_to_dict` → UI, alongside the existing hedged headline:
1. `sim.hold_rate` (= `p_turn_own`, already computed in `api.predict` and then discarded) with its MC standard error, labelled "battle sim: you win N of n runs".
2. `sim.casualty_margin` = mean and p5–p95 of (enemy loss% − own loss%) per run; and the exchange in troops. This is the quantity that DID move in every variation above (46.7% → 58.6% enemy losses from 5-2-3 → 4-6-0) and it is already in the `RunRecord`s.
3. `strength.ratio_own` (= `winprob.effective_ratio`, joiner-folded) plus the troops-only index, so the UI can print "paper strength: you +4.8% (joiners +3.1%)" and show where the matchup sits in the ±20% band.
4. `display.branch` ∈ {`near_even`, `decisive_agree`, `decisive_disagree`} and the numbers each branch saw, so the headline is auditable and the UI can explain "paper strength says 89%, the battle sim says 0 of 400 — shown: …".
5. A role-honesty line when `own.role == garrison` and near-even: the engine carries an attacker-favouring term (`def_k`) and mis-called the three real garrison holds against Infantry/Marksman-heavy rallies (T12_05, RAW_01, RAW_07); read the garrison side-call as directional only.
UI: keep the wax-seal honesty block; add a compact "what moved" strip (hold rate · casualty margin · paper strength) that updates with formation/joiners even when the headline is hedged.

### B. Make the headline continuous and monotone inside the band (winprob.py; no new fitted constants)
1. **Replace the one-bit collapse with the call's robustness.** Generalise `kernel._near_even_probe` (already 3 deterministic sims at ±5%) into a *call-stability* measure: run the point sim under K own-strength multipliers spanning the existing band (e.g. K=9, −20%…+20%, CRN seed) and set `S = fraction of multipliers at which own wins`. Display `p = 0.5 + (S − 0.5)·DAMP`. Endpoints are unchanged (robust win → 0.75, robust loss → 0.25, so the existing measured-accuracy semantics and tests hold), but a knife-edge call reads ~50% and a call that only survives a +12% shift reads ~36%. On the saved file the tipping point is ≈ +12% own strength (panel ×1.10 → 15% holds, ×1.15 → 99%), and it moves with formation (4-6-0 tips earlier than 5-2-3), so formation and joiners finally move the headline — using a band that already exists, not a new constant. Cost: K−1 extra single-run sims per forecast.
2. **Remove the cliff.** Blend the near-even value and the decisive-disagree sigmoid over a transition zone (e.g. linear in `|ln r|` from `ln 1.2` to `ln 1.35`) instead of switching; and never let the headline exceed the sim's hold rate by more than the band without `display.branch = decisive_disagree` being shown next to it (A.4).
3. **Monotonicity guard.** For a fixed matchup, the displayed value must be non-decreasing in own troop count and own panel scale. The 1.25M → 1.30M drop (93.7% → 66.5%) comes from `blind_near_even` demoting a decisive-agree call; when strength and sim agree, the blind probe may cap but must not lower the value below the neighbouring decisive-disagree result. Encode as a test (§7).
4. **Validate, don't assume.** Run `wos_sim/formula_research/calibrate_winprob.py` with the new rule: Brier over the 22 labelled battles must not be worse than the constant's 0.198, and the winner call must stay 15/20 on the near-even set. If S fails that bar, keep the constant headline and ship A only.

### C. Engine — `def_k` (gated; longer term)
- Do **not** flip the default (§4: 6/13, three locked anchors break).
- Expose `def_k` as an explicit, labelled *experimental engine variant* in the API (`params={"def_k": 1.0}` already works) and as a dev-only toggle in the UI ("symmetric engine — experimental, fails G12 on RAW_06/RAW_08/T12_04"), so formation studies can be run without the attacker bias while the default stays honest.
- The real fix remains Stage 8.1 (army-scale composition law). The G12 breakdown in §4 is a usable target: whatever replaces `def_k` must hold RAW_01/RAW_07 AND RAW_06/RAW_08/T12_04 — i.e. it must be composition-aware (Lancer share vs attacker Marksman share, wall thickness, 4×Nora joiners).

### D. Validation hygiene (validate.py)
Warn (or reject) when `formation_counts` disagree with `formation × troops_total` by more than 2%: `construct.class_counts` silently prefers the counts, so a hand-edited scenario's fractions are ignored (`Gen15_50_10_40.json` is named 50-10-40 but contains 50-20-30 on both sides with matching counts — harmless here, but the failure mode is silent).

## 7. Acceptance criteria (on `Scenarios/Gen15_50_10_40.json`, n ≥ 400, seed 4471)

1. Displayed headline differs between own 5-2-3, 4-6-0 and 3-7-0, and between own joiners none / saved 4 / 4×Nora — while `near_even` stays true and the badge still hedges.
2. Displayed headline is monotone non-decreasing in own troop count over 0.8M → 1.3M and in own panel scale over ×0.9 → ×1.3.
3. No headline exceeds the sim hold rate by more than 0.20 unless `display.branch == decisive_disagree` is emitted with both numbers.
4. `forecast_to_dict` carries `sim.hold_rate`, `sim.casualty_margin`, `strength.ratio_own`, `display.branch`; the UI renders them on the forecast card and they update on every run.
5. `py -m wos_sim.backtest`: still 7/13, no broken locked ids, no new silent misses. `py -m pytest`: green (or a dated, Martin-approved amendment of `test_symmetric_joiners_reads_as_coin_flip`).
6. Brier on the 22 labelled battles (calibrate_winprob.py) ≤ current constant.

## 8. Minimal reproduction

```python
import json, copy
from wos_sim.predictor import api
from wos_sim.predictor.serialize import profile_from_dict
d = json.load(open("Scenarios/Gen15_50_10_40.json", encoding="utf-8"))
own, enemy = profile_from_dict(d["own"]), profile_from_dict(d["enemy"])
for label, o, p in [("saved", own, {}), ("4-6-0", copy.deepcopy(own), {}), ("def_k=1", own, {"def_k": 1.0})]:
    if label == "4-6-0":
        o.formation = {"Infantry": .4, "Lancer": .6, "Marksman": 0}; o.formation_counts = {}
    fc = api.predict(o, enemy, n=400, seed=4471, params={"engine": "turn", **p})
    raw = sum(fc.outcome_quality.get(b, 0) for b in (5, 6, 7, 8)) / fc.n
    print(label, "shown", round(fc.p_win.p, 3), "sim hold", raw, "near_even", fc.near_even,
          "own loss", round(fc.army_losses["own"].mean, 1), "enemy loss", round(fc.army_losses["enemy"].mean, 1))
# saved  shown 0.25 sim hold 0.0 near_even True own loss 100.0 enemy loss 46.7
# 4-6-0  shown 0.25 sim hold 0.0 near_even True own loss 100.0 enemy loss 58.6
# def_k=1 shown 0.75 sim hold 1.0 near_even True own loss 50.4 enemy loss 100.0
```

Related: `ENGINE_HANDOFF_joiner_stacking.md`, `wos_sim/formula_research/STAGE8_SPEC.md`, `wos_sim/formula_research/STAGE8_1_FINDINGS.md`, `wos_sim/predictor/winprob_calibrated.py` (Phase A rationale and the three failed margin-sensitivity attempts), `wos_sim/data/golden_baseline.json`.
