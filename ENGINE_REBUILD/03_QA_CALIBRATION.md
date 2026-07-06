# Engine Rebuild — QA Agent Spec & Calibration Gate

A **separate QA agent** owns this document. It runs AFTER Codex reports the TDD suite
green. Its job is NOT to write engine code — it is to (a) **fit the calibration knobs**
against the two anchors, (b) **judge whether the model is trustworthy**, and (c)
**refuse to pass a build that fakes precision**. The QA agent is adversarial by design.

---

## 1. Mandate

> Given a turn-by-turn engine that passes the structural TDD suite, find a single
> parameter set that reproduces BOTH real battles within tolerance, and certify the
> result honestly — including certifying *failure* when the model can't do it.

The QA agent must produce a written report: `ENGINE_REBUILD/QA_REPORT.md` with a
verdict of **PASS / CONDITIONAL / FAIL** and the evidence for it.

---

## 2. Inputs it may tune (and nothing else)

Only the `TURN_PARAMS` knobs listed in `01_BUILD_SPEC.md` §8
(`rate`, `K_skill`, `ambush_frac`/`ambush_proc`, `cara_burst`, `cm`, …). It may NOT:
- edit the engine's mechanics or the absorption order,
- add per-battle special-cases,
- widen the acceptance tolerances below,
- disable conservation or honesty checks.

If a PASS is only reachable by breaking one of those, the verdict is **FAIL** with the
reason, and it escalates to Martin.

---

## 3. Calibration procedure (recommended)

1. **Duration first.** With skills at nominal, fit `rate` so both battles land near
   their turn counts (B1≈16, B2≈25). Note: one `rate` should give both, because turn
   count scales with the matchup, not a per-battle constant. If it can't, record it.
2. **Back-line procs second.** Fit `ambush_frac` + `cara_burst` so B2's marksman die
   ~T14 (annihilated) while B1's marksman only chip ~690k→~580k and survive. This is
   the knob that flips the survivor TYPE between the two battles — the crux.
3. **Exchange/counters third.** Fit `cm` / `K_skill` so survivor COUNTS land in-band
   (B1 62k, B2 118k) and the death ORDER matches.
4. **Re-check triggers.** Trigger counts are emergent from the death schedule; once
   turns + death order are right they should fall within ±1. If not, the cadence
   phase (`start_turn`) is wrong — fix in the skill config, not by fudging.
5. **Lock the set. Re-run both. Then re-run r6/r8** (pre-T12) to confirm no gross
   regression, or explicitly document the re-baseline.

Search method: coarse grid → local refine is fine. Log every evaluated set and its
scores to `QA_REPORT.md` so the fit is reproducible (no `Date.now`/random-seeded
search that can't be replayed — the environment forbids nondeterministic search).

---

## 4. Acceptance gates (ALL must hold for PASS)

| Gate | Criterion |
|---|---|
| **G1 winner+type** | Both anchors: winner == attacker (exact) AND survivor type == {B1 MARKSMAN, B2 LANCER} (exact). Non-negotiable. |
| **G2 duration** | B1 turns ∈ [15,17], B2 turns ∈ [23,27]. |
| **G3 survivor count** | B1 survivors ∈ [30k,110k]; B2 ∈ [60k,190k]. (Wide on purpose — near-even is chaotic; a tight fit here would be overfitting.) |
| **G4 single param set** | G1–G3 hold for BOTH battles with ONE identical `TURN_PARAMS`. If not → **CONDITIONAL** at best, with the unavoidable trade-off quantified. |
| **G5 triggers** | All six trigger oracles per battle within ±1 (see `00_HANDOVER.md` §3). |
| **G6 conservation** | Σ per-source kills == total casualties every turn, all runs (1e-6). |
| **G7 death order** | Per-type death ordering matches the reports (turns ±2). |
| **G8 honesty** | `engine_meta` flags both anchors near-even/`coin_flip`; a ±2% defender-strength perturbation visibly swings the outcome; NO confident point survivor% is emitted for near-even. |
| **G9 no regression** | r6/r8 (pre-T12) still produce sane winners/turns, or the re-baseline is documented in `STATUS.md`. |
| **G10 hero source alignment** | Run `py -m wos_sim.skill_source_audit --live --output ENGINE_REBUILD/SKILL_SOURCE_AUDIT.md`. Every active hero Skill 1/2/3 mechanic must match the max-level Expedition text on `whiteoutsurvival.wiki/heroes/{hero}/`, or the report must list an explicit documented exception. |
| **G11 troop skill rules alignment** | Every `troop_catalog.py` troop skill and every T12 skill in `t12.py` must match `GAME_RULES.md`, including Ambusher, Volley, Crystal Shield, Body of Light, Crystal Lance, Incandescent Field, Crystal Gunpowder, Flame Charge, Indomitable Wall, Meridian Phalanx, and Starfire. |

**CONDITIONAL** = structure correct, G1/G5/G6/G8 hold, but a single param set can't
simultaneously nail G2+G3 for both (i.e. the model is directionally right but the
near-even magnitudes trade off). This is an acceptable, HONEST state to ship behind a
`confidence="directional"` flag — as long as it is declared, not hidden.

**FAIL** = any of G1, G5, G6, G8 broken, or PASS was only reachable by violating §2.

---

## 5. The honesty audit (QA's most important job)

Calibration success is seductive and easy to fake. The QA agent must actively try to
BREAK its own PASS:

1. **Overfit probe.** Does the winning param set generalize, or is it perched on a
   knife-edge? Jitter every knob ±5%. If survivor TYPE flips or a winner flips, the
   fit is fragile → report it; the near-even confidence flag must reflect it.
2. **Telemetry-vs-reality probe.** Do the engine's per-skill KILLS land in the right
   order of magnitude and ranking vs the report's kill numbers (Vulcanus, Ligeia,
   Dominic, Cara, Ambusher)? They needn't match exactly, but if the engine says a
   buff skill made 500k kills, or a burst that the report credits with 96k kills makes
   ~0, that's a misattribution → FAIL even if totals look right.
3. **Conservation spot-audit.** Pick 3 random turns from each battle's `turn_log`;
   hand-verify Σ kills == casualties.
4. **"Kills change the result" probe.** Zero out `cara_burst` and `ambush_frac`;
   confirm B2 no longer produces LANCER survival (marksman stop dying early). This
   proves the procs are load-bearing, not decorative. If the result is unchanged, the
   telemetry is disconnected from the sim → FAIL.
5. **False-precision probe.** Confirm the front-end payload for a near-even matchup
   does NOT present a single-number survivor forecast without the variance/coin-flip
   flag. The two anchors PROVE that ~identical inputs give 16t/marks vs 25t/lancers;
   the product must never imply it can call the exact survivor count of a coin-flip.

---

## 6. What the QA report must contain

`ENGINE_REBUILD/QA_REPORT.md`:
1. Verdict: PASS / CONDITIONAL / FAIL, dated.
2. The locked `TURN_PARAMS` set.
3. A table: per anchor, predicted vs actual for winner, type, turns, survivors,
   death order, all trigger counts — with the tolerance met/missed.
4. The overfit-probe results (fragility characterization).
5. The telemetry-vs-report kill comparison table.
6. Any gate that is CONDITIONAL/FAIL, with the specific trade-off quantified and a
   recommendation (e.g. "need an attacker-barely-LOSES report to pin the other side
   of the knife-edge").
7. Explicit statement of the near-even confidence policy the engine now emits.
8. The `SKILL_SOURCE_AUDIT.md` summary for G10 and the troop/T12 rule-alignment
   summary for G11.

---

## 7. Standing reminder (why this rigor)

These two battles were reconstructed proc-by-proc from real reports; they are the best
ground truth we have. But they also PROVE the regime is chaotic: a ~1.4% effective-
strength shift flips win↔total-wipe, and two near-identical armies gave opposite
survivors. So the bar is: **get the structure and direction provably right, report the
magnitude honestly, and never let the UI imply certainty the physics doesn't have.**
A model that says "coin-flip, catastrophic losses either way" for a near-even rally is
CORRECT and valuable. A model that says "you win with 62,364 survivors" is a lie, even
when it happens to be right.
