# Codex build prompt — stat-panel OCR (paste verbatim)

**Owner pre-flight (before starting Codex):**
1. Commit the current working tree as a checkpoint (the plan, spec, fixtures-to-be and mock are all uncommitted right now) and create a work branch: `git checkout -b ocr-panel-build`.
2. Confirm `node --version` ≥ 20 (needed from Task 10 on; Tasks 0–9 are pure Python and can start regardless).
3. Optional, unblocks Task 12 later: save the raw screenshots into `shell/tests/fixtures/panel_ocr/images/` using the naming scheme in the plan's Task 12.

---

## PROMPT (paste everything below into Codex)

You are executing a pre-written, test-first implementation plan. Do not design, re-architect, or improvise — the thinking is done; your job is faithful execution with evidence.

**Repo:** `E:\WOS\Battle Simulator` (Windows). Python runs via `py`, tests via `py -m pytest`; JS tests via `node --test` (Node ≥ 20). Work on branch `ocr-panel-build`.

**Read first, in this order, before writing any code:**
1. `docs/plans/2026-08-06-ocr-panel-tdd-plan.md` — THE plan. Execute it task-by-task, in order (Task 0 → Task 11), exactly as written.
2. `docs/OCR_UX_FLOW_SPEC.md` — owner-locked product rules (tiering D1, per-side OCR contract, never-fabricate).
3. `docs/OCR_QA_PLAN.md` — the QA bar this build must eventually clear.
4. `CLAUDE.md` (repo root) — repo-wide rules; note the PROTOTYPE vs PRODUCTION table and standing rules.

**Scope:** Tasks 0–11 inclusive. **Task 12 is GATED**: if `shell/tests/fixtures/panel_ocr/images/` is missing or empty, STOP after Task 11 and say so — NEVER substitute synthetic or downloaded images.

**Per-task protocol (strict TDD):**
- Write the failing test exactly as given → run it → confirm it fails for the stated reason → implement minimally → run to green → run the FULL suite (`py -m pytest shell/tests -q`, plus `node --test <explicit .test.mjs paths>` once they exist — never a bare directory, which Windows Node rejects) → commit.
- Commits: the exact message from the task (`ocr:` prefix), staging ONLY that task's files with explicit `git add <path>` — never `git add -A` or `git commit -a` (the tree may contain unrelated work).
- Touch only the files each task lists. NEVER modify: `prototype/index.html`, anything under `wos_sim/`, `prototype/mocks/`, `WOSTests.com`, or any doc.

**Non-negotiables:**
- The Task-0 golden-vector numbers are measured ground truth from two real accounts. If a test disagrees with the fixture, your implementation is wrong — never edit fixture values, never loosen a tolerance, threshold (`LOW_CONF = 0.90`), fuzzy bound (≤2), or validation range to get green.
- Never-fabricate: anything unreadable/uncertain/conflicting ends up absent + flagged, never guessed, never zeroed.
- Determinism: no randomness, no wall-clock in parser/converter code; the determinism tests must pass byte-exact.
- If you believe the PLAN ITSELF contains an error or two tasks contradict each other: STOP, report the exact discrepancy (file/line/what conflicts), and wait — do not resolve it yourself.

**Final report (and at any stop):** one line per task — status, test command with pass count, commit hash — then the full-suite final output, then any discrepancies encountered (expected: none), then whether Task 12's image gate was open or closed.
