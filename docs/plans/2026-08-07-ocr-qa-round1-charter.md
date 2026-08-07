# OCR Panel Build — QA Round 1 Charter (pre-merge, branch `ocr-panel-build`)

**Stage:** post-execution, pre-merge (qa-review discipline) · **Date:** 2026-08-07
**Build under test:** Codex-executed TDD plan Tasks 0–11 — commits `384e302..8995b3b` plus coordinator fixes `d305143` (plan node-invocation + D4 scanner scope) and `24a6c92` (limits-test UTC flake). Baseline checkpoint: `e2417ef`.
**Artifacts:** `shell/app/ocr/panel/*` (8 modules), `shell/app/ocr/panel_router.py`, `shell/app/main.py` (+6 router include), `shell/app/ocr/client/panel_parser.mjs` + `flow_state.mjs` + 2 node test files, `shell/tests/test_ocr_panel_*.py` (10 files), `shell/tests/fixtures/panel_ocr/golden_vectors.json`.
**Reference docs (authoritative):** `docs/plans/2026-08-06-ocr-panel-tdd-plan.md` (the promised build), `docs/OCR_QA_PLAN.md` (standing QA inventory), `docs/STAT_PANELS_FORMULA.md` (the law + raw numbers), `docs/OCR_UX_FLOW_SPEC.md` (product rules).

## Environment matrix
Local only (no deploy exists): repo root `E:\WOS\Battle Simulator`, branch `ocr-panel-build` (already checked out). Commands: `py -m pytest shell/tests -q` · `node --test shell/app/ocr/client/tests/panel_parser.test.mjs shell/app/ocr/client/tests/flow_state.test.mjs` (explicit files — bare directory breaks on Windows Node). Router tests use FastAPI TestClient; no server needed. QA MUST NOT commit, and MUST NOT modify any file except scratch scripts under the session scratchpad.

## Categories in scope (with pass bars)

| # | Category | What to do | PASS bar |
|---|---|---|---|
| C1 | Functional re-run | Both suites from scratch, fresh shell | 187 pytest + 10 node, zero fail |
| C2 | Plan fidelity | Diff every built file against the plan's code blocks; flag semantic divergences (mechanical adaptation OK) | No unexplained divergence; thresholds byte-equal (`LOW_CONF=0.90`, fuzzy ≤2, tolerances 0.11/0.10, range 0–6000) |
| C3 | Data integrity | Independently re-check `golden_vectors.json` values against `docs/STAT_PANELS_FORMULA.md` §3 + §9 tables (both accounts, all panels, specials); re-derive the law on the fixture with your own arithmetic | Zero transcription mismatches; law residuals ≤0.11 pp |
| C4 | Adversarial probing (beyond committed tests) | Novel inputs per `docs/OCR_QA_PLAN.md` §3 P-cases not already unit-tested: unicode/full-width digits, "−" (U+2212) signs, negative zero, 1e6-style notation, duplicate rows within ONE shot, both-colors-on-one-token, empty specials with battle conversion, unknown special labels, label split across 3 tokens, conf exactly 0.90 boundary, giant/empty token lists, service called with battle panel but side_hint, malformed multipart/zero-byte/duplicate-field uploads on the router | Every probe resolves to absent+flagged/4xx — NEVER a fabricated value in `stats`, never a 500, never a guess |
| C5 | Determinism | Hash service + parser outputs over 3 identical runs (Python AND node); check no wall-clock/randomness imports in `shell/app/ocr/panel/` + `client/*.mjs` | Byte-identical; zero `random`/`time.time`/`Date.now` in logic paths |
| C6 | Never-fabricate integrity | Trace every code path that writes into `stats`/`stats_left`/`stats_right`: prove no path emits a value with conf < 0.90, conflict flag, or failed parse; confirm `unreadable_fields` completeness | Proof by code trace + targeted probes |
| C7 | Security/abuse (endpoint) | Free-tier 403, oversize 413 (cap enforced BEFORE full read — verify mechanism), MIME sniff 415 (spoofed extensions, empty magic), unauth 401, >3 files 422, no disk writes anywhere in the request path (audit + tmp scan after requests), no secrets/keys in new code | All enforced server-side; zero persistence |
| C8 | Regression | Rest of shell suite untouched-and-green; `git diff e2417ef..HEAD --stat` contains ONLY the expected files; `wos_sim/`, `prototype/index.html`, `prototype/mocks/` untouched; style guard still green (`py -m pytest wos_sim/predictor/tests/test_ui_style_guard.py -q`) | All green, no scope creep |

## Explicitly out of scope this round (report as GATED, not skipped)
- **L2 accuracy benchmark** — `shell/tests/fixtures/panel_ocr/images/` contains no PNGs (owner supplies); Task 12 unbuilt by design.
- **L4 real-UI walkthrough** — the overlay UI does not exist yet; `prototype/mocks/ocr_flow_mock.html` is its design blueprint, not the implementation.
- **Performance budgets** — no real OCR engines yet (client tesseract / server RapidOCR are Task 12+).
- **Quota (A2) / concurrency semaphore (A7)** — deferred to the shell fix-round; CONFIRM absent and list as open items, do not fail the build for them.

## Output contract
Defect list in the house format — `DEFECT-NNN [Critical|Major|Minor] — Category / Issue / Evidence (file:line or command+output) / Proposed fix / Blocks merge: Yes|No` — followed by: per-category PASS/FAIL/GATED table, the untestable-gated list, and a final verdict line: **READY | CONDITIONAL (fix list) | REVISE**. Report defects, not approvals; zero defects must be earned by evidence shown.
