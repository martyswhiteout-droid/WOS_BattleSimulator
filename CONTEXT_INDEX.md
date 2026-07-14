# CONTEXT_INDEX — "I need to know X → open file Y"

Purpose: this repo has too many docs to read wholesale. Look up your question here, open only the file(s) listed, and respect the **Currency** column — several docs contain stale sections that later docs override.

Currency legend: **CURRENT** (trust it) · **PARTIAL** (trust with the noted caveat) · **HISTORICAL** (background/rationale only) · **STALE-TRAP** (contains statements now known false).

Last audited: 2026-07-11.

---

## 1. Quick router

| Your question | Open |
|---|---|
| What is this product supposed to do? Profile JSON schema? | `BRD.md` (§9 for schema) |
| What is the confirmed formula for game mechanic X? | `GAME_RULES.md` (find the section; prefer later dated corrections) |
| What is the engine ⇄ app data contract? | `ENGINE_INTERFACE.md` |
| What are the binding rules before I change the engine? | `ENGINE_REBUILD/ENGINE_CHANGE_CHECKLIST.md` ← **most current policy** |
| What is the current strategic direction? | `ENGINE_REBUILD/DEEPSEEK_FORMULA_DERIVATION_BRIEF.md` (newest doc, 07-10) |
| Is the engine trustworthy? For what? | `ENGINE_REBUILD/QA_REPORT.md` (read TOP entry only) |
| What's the chronological history of how we got here? | `STATUS.md` (read HIGHEST-numbered sections first) |
| What known bugs are open in the predictor layer? | `QA_FINDINGS.md` |
| How do I run / test / deploy anything? | `TOOLS.md` |
| What must pass before something ships to WOSTests.com? | `PRODUCTION_CRITERIA.md` |
| How do we turn the prototype into the paid SaaS? (shell, Supabase, Stripe, OCR, gate pipeline) | `PRODUCTION_PLAN.md` (Stage-2 DRAFT — not yet red-teamed or approved for execution) |
| How do I ingest a battle report screenshot? | `.claude/skills/wos-battlereport-ingestion/SKILL.md` |
| Where is the FULL set of Type-1 deterministic battle data? (check here BEFORE asking Martin) | `wos_sim/data/experiments/_corpus/` — `TYPE1_CORPUS.md` (human table + coverage matrices), `TYPE1_CORPUS.json` + `corpus.py` (query CLI); OCR corrections pre-applied (`corrections.json`); rebuild with `build_corpus.py` after new ingestion |
| What's the current formula-derivation state / how do I continue it? | `.claude/skills/run-stage/SKILL.md` + `wos_sim/formula_research/STAGE5_SPEC.md` (+ `STAGE5_PREFLIGHT_REVIEW.md` audit) |
| I'm editing the front-end — what must I not break? | `UX_BACKLOG.md` (§0 encoding rules + "already done" list) |
| I'm changing how the UI **looks/moves** (styling, components, polish) | `prototype/DESIGN_SYSTEM.md` — binding visual contract (use skill `.claude/skills/wos-ui-styling/`); enforced by `wos_sim/predictor/tests/test_ui_style_guard.py` + `prototype/style_baseline.json` |

---

## 2. Product & rules docs (root)

| File | Answers | Read cost | Currency |
|---|---|---|---|
| `BRD.md` | Product vision: G2 Predictor + G1 Optimizer; functional reqs M1–M7; profile JSON contract (§9); phasing; acceptance criteria | 18 KB, medium | **PARTIAL** — vision is current; its "~10-15% accuracy" framing is optimistic vs. actual engine state |
| `GAME_RULES.md` | Source of truth for confirmed game mechanics: stat-bonus aggregation law, expedition activation, battle mechanics, troop skills, §6b–6r dated calibration discoveries, §7 open items | 58 KB, large — **skim by heading, never read whole** | **PARTIAL** — authoritative, but combat is SIMULTANEOUS (later correction, commit `dcf1917`); early first-strike text is superseded by the dated corrections later in the file |
| `STATUS.md` | Session-by-session engine/working-state history, §18–23 = latest (turn-engine recalibration, joiner suppression, overfit guardrail) | 44 KB, large — read newest sections only | **STALE-TRAP (banner applied 07-11)** — header says "updated 07-02" but content runs to 07-08; early sections describe abandoned fit states; §22 dedup claim reversed later (see §6 below) |
| `ROADMAP.md` | The E-0…E-11 engine task numbering (still cited elsewhere); two-track engine/app plan | 9.6 KB, medium | **HISTORICAL** — predates the ENGINE_REBUILD turn engine and the no-fudge pivot; keep only for E-task references |
| `ENGINE_PLAN.md` | Farm/PvE kernel derivation; `farm_engine.py` BEST_PARAMS provenance | 8 KB, medium | **HISTORICAL** for PvP; still accurate for the farm/PvE kernel |
| `ENGINE_INTERFACE.md` | The engine⇄predictor seam contract: `Unit` input, `RunRecord` output, `run_batch`, CRN/determinism, T12 params, Final-Stats panel (§7), per-stat buff channel (§8), `skill_telemetry` shape (§9) | 23 KB, med-large | **CURRENT** — definitive interface reference |
| `ENGINE_REPLY.md` | Why `engine_meta` returns path + model_error; honesty-badge rationale; severe fraction 0.35 | 7.6 KB, medium | **HISTORICAL** — decisions implemented; rationale only |
| `ENGINE_HANDOFF_joiner_stacking.md` | Joiner Skill-1 stacking: the dedup was WRONG and was removed (commit `8e816f2`) | 4.8 KB, short | **CURRENT** — overrides QA_REPORT & STATUS §22 on this point |
| `ENGINE_HANDOFF_kill_matrix.md` | Kill-matrix / per-turn telemetry handoff | 6.7 KB, short | CURRENT |
| `QA_CONTEXT.md` | QA onboarding: source-of-truth doc order, full `wos_sim/data/` inventory, claims register, known weaknesses | 9.8 KB, medium | **PARTIAL** — data inventory valid; "round-3 mechanism ACTIVE" framing predates the turn engine |
| `QA_FINDINGS.md` | Concrete defect list w/ file:line: fast-path gate over-claiming, hardcoded `engine_model_error=0.13`, aliased RunRecords, perf misses | 12 KB, medium | **PARTIAL** — structural findings (confidence over-claiming) still open; verify others against code before re-reporting |
| `QA_PROMPT.md` | Reusable QA brief for the UI/API layer (adversarial payloads, form-reader robustness, a11y) | 4.5 KB, short | CURRENT |
| `UX_BACKLOG.md` | Front-end backlog from Nielsen critique; §0 UTF-8 encoding discipline; shipped-do-not-regress list (mobile) | 14 KB, medium | CURRENT |
| `prototype/DESIGN_SYSTEM.md` | **Binding visual contract** for `prototype/index.html`: palette tokens, material recipes (glossy buttons, game tiles, glass sliders, parchment cards), motion grammar, append-only style "rounds", verification steps. Palette/self-containment enforced by `test_ui_style_guard.py` + `prototype/style_baseline.json` | 8 KB, short | CURRENT (2026-07-11) |
| `docs/plans/2026-07-07-ux-backlog.md` | Task-by-task implementation plan for the UX backlog (NOT a duplicate of UX_BACKLOG.md) | 14 KB, medium | CURRENT |
| `VERCEL_DEPLOY.md` | Deploy steps; demo capped at 1,000 sims/request | 0.6 KB, trivial | CURRENT |
| `PRODUCTION_PLAN.md` | SaaS productionization plan: shell architecture, Supabase data model, Stripe, OCR service, IP-safe asset pack, `promote.py` gate pipeline, phases 0–5 | 11 KB, medium | **DRAFT (2026-07-11)** — Stage 2 of architectural review; pending red-team + Martin approval before execution |

## 3. ENGINE_REBUILD/ (turn-engine effort — docs only, code lives in `wos_sim/`)

| File | Answers | Currency |
|---|---|---|
| `00_HANDOVER.md` | Rebuild mission ("kills must drive the result"); exact comps/outcomes of ground-truth anchors report_001/002 | **STALE-TRAP (banner applied 07-11)** — opens with "SPEC ONLY. No engine code has been written." **FALSE**: `pvp_turn_engine.py` (1,717 lines) is built, tested (47 tests), and is the default API path |
| `01_BUILD_SPEC.md` | Turn-engine architecture: data structures, `base_strike_damage()`, skill-packet kill attribution (§4), turn loop, calibration knobs | CURRENT (architecture reference) |
| `02_TDD_TESTS.md` | Ordered TDD tiers 0–5 for the engine | CURRENT |
| `03_QA_CALIBRATION.md` | Acceptance gates G1–G12; **G12 = golden-anchor overfit guardrail (binding)**; calibration procedure; honesty audit | CURRENT — G12 actively enforced |
| `04_WHATS_LEFT.md` | Reuse-vs-build inventory B1–B10 | HISTORICAL — checklist essentially delivered |
| `05_ANCHOR3_AMANDA_OMAR.md` | Scouted-mode double-count bug (fixed); bypass/wall-holding diagnostics | HISTORICAL — diagnostic record |
| `06_NEXT_FIXES.md` | Prioritized engine fixes as of 07-08 (P1 refit, P2 anchor-3 inversion, P3 18 skill-audit failures, P4 honesty surface) | **PARTIAL** — P1 approach overtaken by no-fudge pivot; P3 + structural-bypass gap remain open |
| `07_CONTROLLED_EXPERIMENTS.md` | Evidence that grind-magnitude and winner-ranking are coupled through `def_k`; counter-triangle data | **STALE-TRAP (banner applied 07-11)** — its headline "km 1.206→2.41 landed" was REVERTED by commit `036e4ed` (07-10, "remove km fudge") |
| `ENGINE_CHANGE_CHECKLIST.md` | **THE governing rule (07-09):** Type-1 exact-fit zero-fudge; Type-2 distribution-only; mandatory `py -m wos_sim.backtest` | **CURRENT — overrides all earlier calibration narratives** |
| `DEEPSEEK_FORMULA_DERIVATION_BRIEF.md` | Current direction (07-10): clean-room derivation of the deterministic battle formula from NanoMart/MiniMart controls; list of params considered fudges; hidden-HP hypothesis | **CURRENT — newest strategic doc** |
| `QA_REPORT.md` | Engine certification status. Top entry (07-08, 4th pass): **CONDITIONAL** — winner/ranking certified on A1–A4; A5 tracked coin-flip miss; near-even survivor depth NOT certified. Locked TURN_PARAMS history | **PARTIAL** — read top entry only; its "kept dedup" claim is reversed by `ENGINE_HANDOFF_joiner_stacking.md` |
| `SKILL_SOURCE_AUDIT.md` | Per-hero/per-slot workbook-vs-wiki alignment: 145 checks, 18 mismatches (G10 FAIL) | CURRENT (generated artifact) |

## 4. Code map (what's authoritative)

| Path | What it is | Status |
|---|---|---|
| `wos_sim/pvp_turn_engine.py` | Turn-by-turn skill-firing engine, per-proc kill attribution, telemetry | **AUTHORITATIVE / DEFAULT** (`engine="turn"` hardcoded in server.py) |
| `wos_sim/predictor/` | The app layer: `api.py` (facade — the ONLY entry point), `construct.py`, `kernel.py` (seam), `summary.py`, `serialize.py`, `winprob.py`, `validate.py`, `server.py` (FastAPI) | CURRENT |
| `wos_sim/predictor/tests/` | All 108 tests (13 files; largest: `test_pvp_turn_engine.py` = 47) | CURRENT |
| `wos_sim/pvp_engine.py` | Older aggregate engine | LEGACY but load-bearing: `_side_damage`, `COUNTERS`, absorption reused by turn engine; fallback path in `engine_meta` |
| `wos_sim/pvp_kernel.py`, `proc.py`, `battle.py`, `farm_engine.py`, `farm_fit.py` | Prior engines / calibration artifacts | LEGACY — do not assume current behavior |
| `wos_sim/models.py`, `loader.py`, `mechanics.py`, `troop_catalog.py`, `hero_stats.py`, `t12.py`, `reports.py`, `assemble.py` | Data/model core; `loader.py` reads the xlsx workbook | CURRENT |
| `wos_sim/` module harnesses (`regression`, `backtest`, `pvp_backtest`, `calibrate`, `fit_*`, `anchor_eval`, `eval_reports`, `normalize_reports`, `skill_source_audit`, `reconcile_troop_skills`, `demo`) | Run as `py -m wos_sim.X`; not part of the serving path | CURRENT (see TOOLS.md) |
| `prototype/index.html` | THE live UI — single file, ~3,300 lines, styles+JS inline | CURRENT — active work area |
| `prototype/wos-style-*.html`, `*-preview.html` | Design mockups, NOT wired to the API | Do not confuse with the live UI |
| `app.py`, `vercel.json`, `requirements-vercel.txt`, `.vercelignore` | Vercel serverless deploy (see TOOLS.md) | CURRENT |
| `WoS battle simulator.xlsx` | 2.8 MB workbook — **numeric source of truth** for stats/skills | CURRENT — do not edit casually |

## 5. Data & scenarios

| Path | What it is |
|---|---|
| `wos_sim/data/` | Reverse-engineering data: battle reports, skill display metadata; inventory catalogued in `QA_CONTEXT.md` |
| `wos_sim/data/experiments/NanoMart_*` | Controlled 1v1/NvM experiment series (mostly UNTRACKED, mid-ingestion) — feeds the DeepSeek derivation |
| `Scenarios/*.json` | Saved battle setups in the BRD §9 profile format (the exact `/api/predict` payload shape) |
| `Scenarios/normalized/` | 13 real battle-report anchors converted to scenario format; `T12_01/02` are the two ENGINE_REBUILD ground-truth anchors |

## 6. Stale traps & contradictions (read before trusting any single doc)

**Update 2026-07-11:** the five worst offenders (`STATUS.md`, `ROADMAP.md`, `ENGINE_REBUILD/00_HANDOVER.md`, `ENGINE_REBUILD/07_CONTROLLED_EXPERIMENTS.md`, `ENGINE_REBUILD/QA_REPORT.md`) now carry a dated **status banner at the top of the file** stating exactly which claims are superseded and where the current truth lives. Original content is untouched (append-only lab-notebook convention). The list below remains as the consolidated record.

1. **Joiner dedup:** `QA_REPORT.md` + `STATUS.md` §22 say dedup kept → **REVERSED** by `ENGINE_HANDOFF_joiner_stacking.md` (07-09, commit `8e816f2`). Dedup is removed.
2. **km fudge:** `07_CONTROLLED_EXPERIMENTS.md` celebrates km→2.41 → **REVERTED** by commit `036e4ed` (07-10) under the no-fudge rule.
3. **Calibration philosophy:** STATUS / QA_REPORT / 06_NEXT_FIXES / 03_QA_CALIBRATION treat fitting `def_k`, `rate`, `mod_gamma`, `K_skill` as legitimate → the 07-09 `ENGINE_CHANGE_CHECKLIST.md` declares them fudges. **The checklist wins.**
4. **"SPEC ONLY" in `00_HANDOVER.md`** — false; the turn engine is built and default.
5. **TURN_PARAMS values drift across docs** — no single doc states current values. Ground truth = the code (`wos_sim/pvp_turn_engine.py`) at HEAD, not any doc.
6. **`STATUS.md` header date (07-02)** — misleading; content runs to 07-08 and the repo has moved further since.
7. **BRD accuracy framing** ("~10-15%") — optimistic; PvP is directionally trustworthy only (7/13 real-battle winners; misses are structural).
8. **Two near-identical-size UX docs are NOT duplicates** — `UX_BACKLOG.md` (brief) vs `docs/plans/2026-07-07-ux-backlog.md` (implementation plan).

## 7. Maintenance rule for this index

When you finish a work session that changes project state (new doc, reversed decision, new governing rule, engine certification change), append/update the relevant row here and bump the "Last audited" date at the top. Keep entries one line each — this file must stay skimmable.
