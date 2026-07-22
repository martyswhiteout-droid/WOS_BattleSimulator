# WoS Battle Simulator — Agent Entry Point

> **Read this first. Then use `CONTEXT_INDEX.md` to find the right doc — do NOT try to read everything.**

## What this is

A battle-outcome predictor/optimizer web app for the mobile game **Whiteout Survival** (PvP rally/garrison battles). Python engine (`wos_sim/`) + FastAPI (`wos_sim/predictor/server.py`) + single-file vanilla-JS front-end (`prototype/index.html`). Owner: Martin (single power-user). Game mechanics are reverse-engineered from ~150 controlled battle reports and the workbook `WoS battle simulator.xlsx`.

## Repo roles — PROTOTYPE vs PRODUCTION (binding)

| Location | Role | Rule |
|---|---|---|
| `E:\WOS\Battle Simulator` (this repo) | **PROTOTYPE / work in progress** | All experiments, calibration, and WIP live here. Nothing here is presumed production-quality. |
| `E:\WOS\WOSTests.com` | **PRODUCTION ONLY** | Contains ONLY releases that have passed every item in `PRODUCTION_CRITERIA.md`. **Its default state is EMPTY — an empty production folder is correct, not a mistake.** Never copy WIP there "to be helpful". |

## Navigation

- `CONTEXT_INDEX.md` — RAG-style lookup: "I have question X → open file Y". Includes per-doc currency ratings and known stale traps. **Use this instead of reading docs wholesale.**
- `TOOLS.md` — every command: run the app, tests, regression gate, backtest, calibration harnesses, deploy.
- `PRODUCTION_CRITERIA.md` — the gate checklist anything must pass before it may enter `WOSTests.com`.
- `wos_sim/data/experiments/_corpus/` — **canonical Type-1 battle corpus** (every deterministic battle report, normalized, OCR-corrections applied): `TYPE1_CORPUS.md` human table + coverage matrices, `corpus.py` query CLI. Battle-data analytics MUST retrieve from here — never re-discover folders or ask Martin for data before checking its coverage matrix. Rebuild with `build_corpus.py` after ingesting new reports.

## Standing rules (all agents, all sessions)

1. **No-fudge rule** (`ENGINE_REBUILD/ENGINE_CHANGE_CHECKLIST.md`, 2026-07-09 — the most current governing policy; it OVERRIDES earlier calibration narratives in STATUS.md / QA_REPORT.md):
   - Type-1 reports (deterministic, no procs) are the only legitimate exact-fit calibration targets and must fit with ZERO fudge factors.
   - Type-2 reports (procs) are validated by distribution only — never regression-fit.
2. **Mandatory guardrail before any engine/TURN_PARAMS change lands:** run `py -m wos_sim.backtest` (golden-anchor set; pass count may only increase — gate G12 in `ENGINE_REBUILD/03_QA_CALIBRATION.md`).
3. **Only touch the engine through `wos_sim/predictor/api.py`.** The seam contract is `ENGINE_INTERFACE.md` (non-mutating, CRN-seeded). `server.py` hardcodes `engine="turn"`.
4. **Do not "fix" `coin_flip` labels or honesty badges.** Near-even battles are genuinely chaotic; the hedged output is intentional design, not a bug (`winprob.py`, `engine_meta`).
5. **Front-end discipline:** `prototype/index.html` is UTF-8; follow the rules in `UX_BACKLOG.md` §0 before editing it. **Any change to how the UI looks or moves must follow `prototype/DESIGN_SYSTEM.md`** (palette-locked design system; append-only style "rounds"; no CDNs/Tailwind/external fonts) — use the skill `.claude/skills/wos-ui-styling/`. Any change aimed at how the UI *feels* (delight, celebration, micro-interactions, reveal/feedback moments) must FIRST follow `.claude/skills/wos-emotional-design/` (when/why + confidence-tiered intensity), then implement via wos-ui-styling. The style guard `wos_sim/predictor/tests/test_ui_style_guard.py` enforces the palette baseline (`prototype/style_baseline.json`), self-containment, local fonts, the reduced-motion kill-switch, and an `!important` budget; regenerate the baseline only as a deliberate design decision (`--update-baseline`, justified in the commit).
6. **Battle-report ingestion:** use the skill at `.claude/skills/wos-battlereport-ingestion/` — deterministic v2 schema, Type-1/Type-2 classification, **never fabricate data**; validate with its `scripts/validate_report.py`.
7. **Doc trust order: newest wins.** When docs conflict, the later-dated one is authoritative. Known conflicts are catalogued in `CONTEXT_INDEX.md` § "Stale traps & contradictions".

## Architecture in five lines

```
prototype/index.html (vanilla JS UI)
  → POST /api/predict, /api/battle
  → wos_sim/predictor/server.py (FastAPI; app.py re-exports for Vercel)
  → wos_sim/predictor/api.py (the ONLY facade) → construct.py → kernel.py (seam)
  → engine: wos_sim/pvp_turn_engine.py (AUTHORITATIVE, default) — older engines are legacy
```

Legacy engines (`pvp_engine.py`, `pvp_kernel.py`, `proc.py`, `battle.py`, `farm_engine.py`) are calibration history — do not assume they reflect current behavior. Exception: `pvp_engine._side_damage` is still reused by the turn engine.

## Current phase (as of 2026-07-11)

The project pivoted (07-09/07-10) from parameter-fitting to **first-principles formula derivation**:
- Governing docs: `ENGINE_REBUILD/ENGINE_CHANGE_CHECKLIST.md` (no-fudge rule) and `ENGINE_REBUILD/DEEPSEEK_FORMULA_DERIVATION_BRIEF.md` (clean-room derivation from the NanoMart/MiniMart controlled experiments).
- HEAD commit removes the `km` fudge. Large uncommitted working tree (NanoMart experiment JSONs, engine + UI edits) — do not assume `git status` is clean.
- Engine QA verdict: **CONDITIONAL** (`ENGINE_REBUILD/QA_REPORT.md`, top entry) — certified for winner/ranking on anchors A1–A4; near-even survivor magnitudes NOT certified.
- App layer, seam, profile schema, UI, telemetry: built and working end-to-end. The hard open problem is PvP engine accuracy.
