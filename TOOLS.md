# TOOLS — every command a future agent needs

All commands run from repo root `E:\WOS\Battle Simulator`. Python lives in the local `.venv` (Windows). `py` = the Windows Python launcher; use `.venv\Scripts\python` when the venv's packages are required.

## Run the app locally (UI + API together)

```
.venv\Scripts\python -m uvicorn wos_sim.predictor.server:app --reload
```
Then open http://127.0.0.1:8000/ — `server.py` serves `prototype/` as static files and exposes `POST /api/predict` and `POST /api/battle`.

VS Code launch configs (`.claude/launch.json`): `prototype` (port 8137) and `prototype-verify` (port 8138).

## Tests & guardrails (run these before claiming anything works)

| Command | What it does | When required |
|---|---|---|
| `py -m pytest` | Full suite — 108 tests in `wos_sim/predictor/tests/` (no pytest config needed) | Any code change |
| `py -m wos_sim.regression` | End-to-end "nothing broke" gate | Any code change |
| `py -m wos_sim.backtest` | **Golden-anchor backtest. MANDATORY before any engine/TURN_PARAMS change lands. Pass count may only increase (gate G12).** | Any engine change |

## Calibration / analysis harnesses (`py -m wos_sim.X` — not part of the serving path)

| Command | Purpose |
|---|---|
| `py -m wos_sim.demo` | Load & inspect the xlsx workbook data |
| `py -m wos_sim.anchor_eval` | Evaluate engine against the anchor battles |
| `py -m wos_sim.eval_reports` | Evaluate against ingested battle reports |
| `py -m wos_sim.pvp_backtest` | PvP backtest harness |
| `py -m wos_sim.calibrate` / `pvp_calibrate` / `fit_kernel` / `fit_turn_params` / `fit_report` | Fitting harnesses. **Caution:** the 07-09 no-fudge rule (`ENGINE_REBUILD/ENGINE_CHANGE_CHECKLIST.md`) forbids regression-fitting Type-2 reports — check the rule before using these |
| `py -m wos_sim.normalize_reports` | Convert raw ingested reports → normalized scenario format |
| `py -m wos_sim.skill_source_audit --live` | Audit modeled hero skills vs the wiki (regenerates `ENGINE_REBUILD/SKILL_SOURCE_AUDIT.md`; currently 18/145 mismatches) |
| `py -m wos_sim.reconcile_troop_skills` | Reconcile troop skill data |

## Data ingestion

- **Battle report screenshots → canonical JSON:** follow `.claude/skills/wos-battlereport-ingestion/SKILL.md` (v2 schema, Type-1/Type-2 classification, never fabricate). Validate with:
  ```
  py .claude\skills\wos-battlereport-ingestion\scripts\validate_report.py <file.json>
  ```
- **Refresh hero skill display assets from the wiki:**
  ```
  py scripts\fetch_hero_skill_assets.py
  ```
  (writes to `prototype/assets/` and `wos_sim/data/skill_display/`; numeric skill effects come from the workbook, not this scraper)

## Deploy (Vercel — demo only; this is NOT the production push to WOSTests.com)

```
npx vercel deploy --prod
```
- Entrypoint: `app.py` (re-exports the FastAPI app). Config: `vercel.json` (`maxDuration: 300`).
- Uses `requirements-vercel.txt` (minimal: openpyxl, numpy, fastapi, pydantic — no scipy/uvicorn). Dev set is `requirements.txt`.
- `.vercelignore` excludes `.venv`, `.pytest_cache`, `.claude`, `ENGINE_REBUILD`, `Scenarios`, `reports`.
- Demo is capped at 1,000 sims/request (`DEFAULT_RUNS=1000`; UI-enforced + API 400). See `VERCEL_DEPLOY.md`.

## Environment notes / gotchas

- Two requirements files diverge on purpose — scipy and uvicorn are dev-only.
- The workbook `WoS battle simulator.xlsx` is the numeric source of truth; `wos_sim/loader.py` reads it via openpyxl.
- Repo is often mid-experiment: expect a dirty `git status` (untracked `wos_sim/data/experiments/NanoMart_*` etc.). Branch: `master` only.
- `prototype/index.html` is UTF-8 — read `UX_BACKLOG.md` §0 before editing.
- `.claude/settings.local.json` holds the Claude Code permission allowlist (incl. `WebFetch(domain:www.whiteoutsurvival.wiki)`).
