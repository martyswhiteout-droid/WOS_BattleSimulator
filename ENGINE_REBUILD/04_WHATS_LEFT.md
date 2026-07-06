# Engine Rebuild — What's Left to Build (gap inventory)

Read AFTER `00_HANDOVER.md`. This maps the spec onto the **current repo** so Codex
reuses what exists and builds only the gap.

---

## 0. Headline finding

**The `skill_telemetry` CONSUMER path is already built and tested.** The kernel record
field, the batch aggregation, the JSON serialization, and a shape test all exist and
already expect the exact per-record shape from `ENGINE_INTERFACE.md` §8
(`heroes[].skills[{slot, triggers, kills}]`). **The only missing piece is the
PRODUCER** — the turn-by-turn engine that actually simulates procs and fills that
field. Do not rebuild the plumbing; build the engine that feeds it.

---

## 1. EXISTS — reuse, do not rebuild

| Component | Location | Reuse for |
|---|---|---|
| Per-strike damage formula (atk/def/leth/health power, tier power, counter, dd/dt, T12 multipliers) | `wos_sim/pvp_engine.py::_side_damage` (~L90–131) | The base packet damage. Refactor the inner term into `base_strike_damage()` per `01_BUILD_SPEC.md` §3. |
| Counter triangle | `wos_sim/pvp_engine.py::COUNTERS` (Inf>Lan>Mar>Inf) | Counter multiplier. |
| Front-to-back absorption primitive | `wos_sim/pvp_engine.py::_apply` + `ORDER` | The absorption loop + bypass targeting (extend for per-packet kill capture). |
| Ambusher gating / min tiers | `wos_sim/mechanics.py::AMBUSHER_MIN_TIER` (=7), `CRYSTAL_LANCE_MIN_TIER` (=11) | Which lancers/marksmen actually have the bypass/proc skills. |
| **Kernel record field** `skill_telemetry: dict\|None` | `wos_sim/predictor/kernel.py:58` | **The producer just assigns this.** Already deep-copied through `run_batch` (L227, 265, 278). |
| CRN + non-mutating helpers | `kernel.py::_run_rng(seed,i)`, `_replicate`, `engine_meta`, `DEFAULT_PVP_PARAMS` | RNG streams, independent copies, per-matchup confidence. Follow these patterns exactly. |
| Batch aggregation of telemetry | `summary.py::_skill_telemetry` (L130), `_hero_rows_for` (L126), `_skill_values` (L114) | Already collapses per-record `heroes[].skills[]` into per-hero trigger/kill **distributions** across the batch. |
| Forecast field + serialization | `summary.py::Forecast.skill_telemetry` (L177), `serialize.py::_skill_telemetry` (L56) + `forecast_to_dict` (L86) | The API already emits `skill_telemetry` to the front-end. |
| Shape test | `wos_sim/predictor/tests/test_summary.py::TestSkillTelemetry` | Confirms the exact producer shape (see §3). Keep it green. |
| Layer-1 construction (units, effective stats, skills routing, engine_params, T12) | `predictor/construct.py::build`, `predictor/skills.py::resolve`, `loader.py::load_skill_book` | Feed the engine. The `SkillDef` adapter wraps these. |
| Ground-truth anchors | `wos_sim/data/pvp_t12_report_00{1,2}.json` | Calibration + validation. |
| Test dir + regression harness | `wos_sim/predictor/tests/` (existing), `wos_sim/regression.py` | Where new tests go. |

---

## 2. NET-NEW — build this

| # | Deliverable | Spec section | Notes |
|---|---|---|---|
| B1 | `wos_sim/pvp_turn_engine.py` — the turn-by-turn simulator | `01_BUILD_SPEC.md` §2,§4,§6 | The core build. Data structures, turn loop, packet apply + kill capture. |
| B2 | `base_strike_damage()` refactor out of `_side_damage` | §3 | Pure function reused by the loop; keeps the validated formula. |
| B3 | `BACKLINE_SKILLS` config table (bypass procs) | §4.1 | Seed: **Ambusher** → `(MARKSMAN,)`; **Cara SK3** → `(LANCER, MARKSMAN)`. Data-table so new skills need no code change. |
| B4 | `skill_defs_from_matchup(con)` adapter → `list[SkillDef]` | §4,§9 | Turns `construct.build` + `load_skill_book` into fired skills w/ cadence + bypass flags. |
| B5 | Populate `KernelRecord.skill_telemetry` in §3 shape (incl. `troop_skills`) | §7 + `ENGINE_INTERFACE.md` §8 | Producer side of the existing plumbing. |
| B6 | `engine_meta` near-even confidence (`near_even`, `confidence`, honest `model_error`) | §7 | ±2% perturbation → coin-flip flag. |
| B7 | Route `kernel.run_batch` to the new engine (feature-flag `params["engine"]="turn"`, then flip default) | §9 | Preserve `_replicate`/`_run_rng`. |
| B8 | Tests `wos_sim/predictor/tests/test_pvp_turn_engine.py` | `02_TDD_TESTS.md` | Tiers 0–5. |
| B9 | Regression additions | `02` Tier 3 + G6 | Anchors + conservation into `regression.py`. |
| B10 | QA calibration pass → `ENGINE_REBUILD/QA_REPORT.md` | `03_QA_CALIBRATION.md` | Owned by the QA agent, after B1–B9 green. |

---

## 3. CONFIRMED producer schema (read from the live consumer code)

Each `KernelRecord.skill_telemetry` (one per stochastic run) MUST be:

```python
{
  "attacker": {
    "heroes": [
      {"hero": "Elif", "role": "captain", "troop": "Infantry",
       "skills": [{"slot": "skill_1", "triggers": 10, "kills": 0},
                  {"slot": "skill_2", "triggers": 2,  "kills": 100}]},
      ...
    ],
    "troop_skills": [ {"name": "ambusher", "troop": "Lancer", "triggers": 8, "kills": 61950} ]
  },
  "defender": { "heroes": [...], "troop_skills": [...] }
}
```

Verified against `summary._skill_values` (sums each hero's `skills[]` triggers/kills),
`_hero_rows_for` (reads `side.heroes`), and `test_summary.TestSkillTelemetry`. **Match
this exactly** or the (already-green) aggregation test breaks.

---

## 4. TWO consumer gaps — flag to Martin, small decisions

The consumer is built but has two known limitations. Neither blocks the producer;
both are quick follow-ups **if** the UI wants that detail:

1. **Per-slot detail is collapsed.** `summary._skill_values` **sums all of a hero's
   slots** into one `(triggers, kills)` per hero before building the batch
   distribution. So today the front-end sees *per-hero* totals, not per-slot
   (Vulcanus SK2 vs SK3 separately). The battle report shows *per-slot*. If per-slot
   display is wanted, extend `summary._skill_telemetry` to emit a distribution per
   `(hero, slot)` instead of per hero. **Producer emits per-slot regardless** (§3), so
   this is a pure consumer change.
2. **`troop_skills` is not consumed.** `summary`/`serialize` only read `heroes`.
   **Ambusher is a troop skill and it is load-bearing** (it's what annihilates the
   marksman in battle 2), so its triggers/kills matter. Either (a) extend the consumer
   to aggregate + serialize `troop_skills`, or (b) as an interim, emit troop skills as
   pseudo-hero rows (`role: "troop_skill"`). Recommend (a). **Decision for Martin.**

---

## 5. Build order (dependency-correct)

1. **B2** (`base_strike_damage` refactor) — unlocks everything, zero behaviour change; keep `pvp_engine` tests green.
2. **B1 core loop + B3 bypass table**, tested against `02` Tier 0–1 (mechanics + cadence) with synthetic stacks.
3. **B4 adapter** + **B1 kill capture**, tested against `02` Tier 2 (conservation) — this is the correctness spine.
4. **B5 telemetry populate** + keep `test_summary` green; then `02` Tier 4.
5. **B7 routing** behind the flag; **B6 near-even meta**; `02` Tier 5 (honesty).
6. **B8/B9** full suite + regression; then hand to **B10 QA**.
7. QA fits `TURN_PARAMS` against both anchors (`03`), writes `QA_REPORT.md`, verdict PASS/CONDITIONAL/FAIL.

Expect Tier 3 (anchors) to be RED until QA's calibration pass — that's by design. Get
the structure (types, order, trigger counts, conservation) green first; magnitudes are
the QA agent's job, and a **CONDITIONAL** verdict is the honest likely outcome until an
attacker-barely-loses report pins the far side of the knife-edge (`03` gate G4).
