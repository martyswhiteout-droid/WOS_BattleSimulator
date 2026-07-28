# Stage 8 spec — the Army-Scale First-Principles Engine

**Status:** proposed 2026-07-25, after eval-7 ACCEPT (`STAGE7A_REPORT.md`) and the
def_k investigation (this session). Stages 1–6.8 derived and shipped the exact
deterministic **1v1** law; Stage 7A catalogued every proc and mined the telemetry.
Stage 8 is the leap the whole project was aimed at: make the first-principles
engine handle **real army battles** — multi-class, million-troop, hero/joiner-laden,
proc-capable — and **retire the legacy turn engine (and its `def_k=0.45` fudge) for
every battle it can cover.**

---

## 0. Why this stage exists (the def_k finding, 2026-07-25)

Martin's three Gen15 test battles surfaced the core defect. Verified end-to-end
this session (scripts in scratchpad; reproduced through `api.predict`):

- The app's army-scale win% is **not a simulated probability.** It is the fixed
  heuristic `0.5 + (p_sim − 0.5)·0.10` (`winprob.py`), which only encodes *which
  side the sim picked* — every near-even loss prints exactly 45%, every near-even
  win 55%.
- The sim underneath is driven by **`def_k=0.45`** (`pvp_turn_engine.py` TURN_PARAMS),
  a flat "defender deals 45% of the attacker's per-capita damage" fudge. On a
  **perfect mirror** (identical stats + heroes, only the role differs) it hands the
  attacker a **300/300 win**; a fair simultaneous engine must return ~50/50.
- The fudge is **irreducible by tuning.** The mandatory backtest at `def_k=1.0`
  scores **6/13 and FAILS the guardrail** (fixes RAW_01/RAW_07 real *defender*
  wins, but breaks RAW_06/RAW_08/T12_04 real *attacker* wins + adds a silent miss).
  A single global scalar cannot satisfy both attacker- and defender-favoring real
  battles — the definitional signature of a fudge standing in for missing physics.
- At the neutral `def_k=1.0`, a mirror shows **genuine run-to-run winner variation**
  (128 D / 61 A / 11 mutual over 200 runs) — the stochastic win-rate Martin
  correctly expected. The fudge *suppresses* it.

**Conclusion:** the fudge cannot be lifted, only replaced. Stage 8 replaces it with
the first-principles deterministic base + a stochastic proc layer, so army battles
emit real win/loss **distributions** and mirrors resolve ~50/50 by construction.
No `def_k`. This is also what deletes the display heuristic: a trustworthy engine
emits a real number, so `winprob.py`'s override is no longer needed for covered battles.

---

## 1. What we have vs. the gap

| Capability | Shipped (stages 1–7A) | Needed for army battles |
|---|---|---|
| Per-unit within/cross-tier law | ✅ exact, class-keyed G_w/G_l, K-table | reused as the backbone |
| HP = D·H, √N offense | ✅ | validate at N up to 1e6 |
| Composition (tank + mop-up) | measured, small-N, **single-class router only** | **generalize to arbitrary multi-class both sides** |
| Hero auras/folds | ✅ for {SeoYoon, Vulcanus, Gatot} via 6.7 fold-ownership | **full hero registry: 3 leads + 4 joiners/side** |
| Proc catalog + telemetry | ✅ `docs/PROC_CATALOG.md`, streams measured | **build the live stochastic layer (Phase B)** |
| Routing | single-class 1v1 lab domain only | **widen gates so army battles route in (Phase C)** |
| Role (rally/garrison) effect | **unmodelled** (turn engine fakes it with def_k) | **measure it or prove it absent** |

The 1v1 law is a backbone with four missing limbs: composition, scale+heroes,
live procs, and the router. Stage 8 grows each, in that dependency order.

---

## 2. THE BINDING PREREQUISITE — army-scale ground truth (Stage 8.0)

**The entire Type-1 corpus is 1v1 / small-N lab battles.** We have essentially
**zero clean army-scale ground truth** — which is *why* `def_k` was ever fitted.
Under the no-fudge rule, Stage 8 cannot derive or validate anything at army scale
without real reports to predict against. So Stage 8.0 is a data battery Martin
captures in-game (via the `wos-battlereport-ingestion` skill — **full stat panels
always captured**), before 8.1 derivation begins. Minimum decisive set:

| # | Setup | What it pins | Decisive read |
|---|---|---|---|
| A | **Pure mirror at scale** — identical account/troops/heroes both sides, one rallies one garrisons, ~100k–1M | The role effect the turn engine fakes with def_k | outcome should be ~mutual / coin-flip; a systematic winner = a REAL role mechanic to measure |
| B | **Parity single-class** rally vs garrison, Inf-only, MM-only, Lan-only, no heroes | Role effect per class, clean of composition | winner + survivor% per class |
| C | **Multi-class comp** (e.g. 50/20/30) vs same, no proc heroes, low FC | Composition generalization at scale | survivor% by class → tank/mop-up law |
| D | **Counter comps** (Inf-heavy vs Lan-heavy, etc.) at scale | Class-triangle at composition scale | winner + survivor% |
| E | **Proc battery** — FC10 + proc heroes (Gatot/Blanchette/Mia…), otherwise matched | Phase-B distribution validation | visible skill trigger COUNTS + outcome, repeated if possible |
| F | **Martin's actual Gen15 trio** with real in-game outcomes | The end-to-end acceptance test | the app must land these inside the measured distribution |

Each row is an **anchor**: stats-in → outcome-out, no fitting. **8.1–8.4 accept
criteria are defined against this battery.** If a regime has no anchor, it stays
on the turn engine (honestly banner-flagged) until one exists. Deliverable: these
ingested into the corpus (`build_corpus.py`), coverage matrix updated.

---

## 3. Sub-stages (each a builder + evaluator cycle, standard guardrails)

### Stage 8.1 — Multi-class composition at scale (deterministic backbone)
- **Goal:** extend `predict_battle` from single-class to **arbitrary Inf/Lan/MM
  mixes on both sides**, two-sided race, absorption order Inf→Lan→MM, using the
  frozen per-unit K/G_w/G_l tables unchanged.
- **Method:** generalize the Stage-5 tank/mop-up algorithm (binary frontline
  tanking penalty + linear backline mop-up) to N classes and both sides. SOLVE
  the multi-class front/back interaction from anchors C/D + existing
  `Meuller_Alpaca_v5_8_Battle` composition rows; **blind-predict** the rest. No
  aggregate-error minimization — exact within the survivor bands or the family is
  rejected.
- **Validate:** the 4 composition anchors (mirror 24 / inf>lan 45.4 / inf<mm 4.9 /
  lan>mm 42) + anchors C/D + any multi-class corpus rows.
- **Gate:** `stage8_validate` composition bucket exact; G12 backtest unchanged;
  suites green. **Deliverable:** `stage8_composition.py`, `STAGE8_1_REPORT.md`.

### Stage 8.2 — Scale + full hero/joiner registry + the role effect
- **Goal:** (a) validate √N offense + per-unit clock from lab-N to 1e6 (numerical
  stability, the 1500-turn cap, no snowball); (b) extend 6.7 fold-ownership to the
  **entire hero registry** — arbitrary lead heroes + up to 4 joiners/side, auras +
  stat folds + joiner stacks, from `docs/HERO_KITS.md` (+ new entries as needed);
  (c) **measure the rally/garrison role effect** from anchors A/B and encode it as
  a *measured* mechanic — or prove it's ~0 (mirrors → ~50/50), **which is what
  formally retires `def_k`.**
- **Method:** auras/folds are frozen mechanics (no new constants without an anchor);
  the role effect is SOLVED from the parity battles, branched if ambiguous, never
  fitted to make other rows work.
- **Gate:** scale invariance shown numerically; anchors A/B within bands; G12
  unchanged. **Deliverable:** `stage8_scale.py`, hero-registry extension,
  `STAGE8_2_REPORT.md`.

### Stage 8.3 — Stochastic proc layer (this is Stage 7 **Phase B**)
- **Goal:** roll the catalogued procs (CRN-seeded) **on top of** the deterministic
  base, so a battle yields kill-turn / survivor / **winner DISTRIBUTIONS** — the
  genuine win-rate variation, replacing the point clock. **No `def_k`; no fudge.**
- **Method:** each proc touches a specific law term (damage-mult / extra-attack /
  absorb / def-mult / on-death) per `PROC_CATALOG.md`; probabilities come from
  tooltips/catalog, **never regression-fit**. Monte-Carlo the proc rolls; the win%
  is the **fraction of runs won** (real, not a heuristic).
- **Validate — DISTRIBUTION ONLY (gates G-T1…G-T5 from STAGE7A):** observed trigger
  counts vs binomial expectation (anchor E); observed outcomes inside the predicted
  distribution; the currently-excluded Type-2 families (Vulcanus-dealer −6.5%,
  proc-gated non-Inf) checked by distribution. A contradiction is a FINDING, not a refit.
- **Gate:** distribution gates pass on anchor E; G12 unchanged; suites green.
  **Deliverable:** `stage8_proc.py`, `STAGE8_3_REPORT.md`.

### Stage 8.4 — Router widening + app integration (this is Stage 7 **Phase C**)
- **Goal:** progressively open the `type1_router` classifier gates as each regime
  above validates (multi-class → higher tier/FC as procs validate → arbitrary
  heroes → joiners → buffs), route covered army battles to the new engine, and let
  the app show the **real distributional win% + survivor bands.** The honesty
  banner (Round 15) self-suppresses because covered battles now report
  `engine_path='army_law'` (≠ the turn engine).
- **Method:** additive at the `api.py` seam only (server.py untouched, standing
  rule). The turn engine + `def_k` path is retained **only** as the fallback for
  still-uncovered matchups; deprecated for covered ones. Each opened gate names the
  anchor that justifies it.
- **Gate:** G12 backtest holds/rises; **anchor F (Martin's Gen15 trio) lands inside
  the measured outcome distribution**; full predictor suite; the Vercel min-troop
  gate and the banner both behave. **Deliverable:** router extension,
  `STAGE8_4_REPORT.md`, updated `run-stage` skill entries (8.1–8.4 + evals).

---

## 4. What Stage 8 deletes

- **`def_k` (and the whole TURN_PARAMS fudge set)** for covered battles — replaced
  by measured role physics + first-principles damage. Kept only behind the
  shrinking turn-engine fallback.
- **The `winprob.py` display heuristic** for covered battles — the engine emits a
  real win-rate, so the 0.5±0.05 override is bypassed (kept for the fallback).
- **The Round-15 honesty banner**, automatically, per battle, as its regime becomes
  first-principles (the banner is keyed to engine provenance, so no code change is
  needed to retire it — it just stops showing).

## 5. Guardrails (inherit, binding)

All standing rules apply unchanged: **no fabrication** (every number from a
re-runnable `formula_research/` script); **no regression/best-fit** (SOLVE from
minimal subsets, blind-predict, any unexplained residual = family rejected);
**observed outcomes are never inputs**; **ambiguity → branch, never silently pick**;
**Type-2 validated by DISTRIBUTION only, never fit**; engine reached **only through
`api.py`**; **`py -m wos_sim.backtest` (G12) before and after every stage, may only
hold or rise**; nothing enters `WOSTests.com` until PRODUCTION_CRITERIA passes.

## 6. Open risks / honest unknowns

- **Data is the gating risk.** Without anchors A–F, 8.1–8.3 cannot be validated
  without fitting — which is forbidden. If Martin can't capture a regime, that
  regime stays on the turn engine (banner-flagged), and that's an acceptable,
  honest outcome, not a failure.
- The role effect (8.2) may turn out to be **class- or scale-dependent**, not a
  single number — the parity battery must span classes and sizes to catch that.
- The composition generalization (8.1) may not close from existing rows; the spec
  budgets for one or two extra discriminator comps if so.
- Proc interactions at army scale (8.3) may exceed the per-proc independence the
  catalog assumes; distribution gates will expose it as a contradiction to report,
  not paper over.

---

*Next action if approved: capture the Stage 8.0 battery (or the subset Martin can
run now), ingest to the corpus, then `/run-stage 8.1`.*
