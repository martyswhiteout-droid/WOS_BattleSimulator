# OCR QA round 2 — post-merge independent review (charter)

**Date:** 2026-08-15. **Target:** merged `master` at `64921da` (merge of `ocr-panel-build`, 77
commits). **Requested by:** owner ("another independent QA brief post the merge").
**Prior evidence:** `shell/EVAL_OCR_PANEL_QA1.md` (6 rounds, D-001..D-042, L4 gate CLOSED).

## Why this round exists

Rounds 1–6 covered the parse/convert/service pipeline, the metering endpoint, and the overlay UI.
Four areas were **never independently QA'd** (built after round 1, verified only by their own
builders' tests and the benchmark), plus the merge itself deserves a fresh-eyes pass:

## Scope (in priority order)

1. **`shell/app/ocr/panel/engine_rapidocr.py`** — adapter debt. Loop-bound semaphore (weakref
   keying — probe the id-reuse hazard class), `OCR_CPU_CONCURRENCY` clamp [1,8], error paths
   (corrupt image, zero-text image, engine import failure), output contract (tokens + confidences
   shape expected by `service.py`), determinism across repeated runs on the same fixture.
2. **`shell/app/ocr/panel/engine_gemini.py`** — adapter debt. Budget committed BEFORE the call
   (crash between commit and response must not leak budget), `GEMINI_OCR_DAILY_BUDGET` day
   rollover, per-(label,side) replacement semantics (gap-fill must never overwrite a confident
   RapidOCR field), no-key behavior (`GeminiUnavailable` before any HTTP), API-error surfacing
   into response warnings, validation rejections (null / wrong-format / out-of-range → unreadable,
   never emitted) — the existing tests assert these; VERIFY the tests actually bite (mutate
   mentally: would a plausible bug pass them?).
3. **`shell/tests/test_ocr_panel_benchmark.py`** — the harness itself. Selection logic
   (`_benchmark_selected`), D2 gate arithmetic (digit accuracy, false-confident counting): a
   broken harness could false-PASS the release gate. Read it as adversarially as a defect.
4. **Fixture/vector integrity** — `shell/tests/fixtures/panel_ocr/golden_vectors.json` account C:
   internal consistency against `docs/STAT_PANELS_FORMULA.md` (does the recorded battle column
   convert to the recorded scout column under the recorded specials? does bo_troops+bo_class+U
   reconcile?). The vectors are UNTOUCHABLE ground truth — if arithmetic disagrees, report it;
   do not edit them.
5. **`shell/app/ocr/client/engine_tesseract.mjs`** — benched engine (coordinator Ruling 1:
   SERVER-ONLY v1). Confirm it is dead code: not imported by any live UI module, no network
   fetch of models at page load, no CDN reference (self-containment rule).
6. **Whole-feature spot check on master** — suites (expect 341 py / 144 node with 143 pass +
   1 documented skip / 7 style guard), boot the server, one real `/shell/ocr/panel` read over
   HTTP with the account-C fixtures, free-tier 402 signal, pro path via `X-Dev-Plan` header
   (sanctioned dev-bypass technique, `docs/OCR_QA_PLAN.md` §8).

## Method rules (binding, same as rounds 1–6)

- **Evidence only.** Every finding needs a reproducible probe (command or script). No
  taste-based findings; cosmetic observations go in a separate short list.
- **Fix nothing.** This round produces a BRIEF, not patches. Owner decides what gets fixed.
- Defect numbering continues: **D-043 onward**. Severity: BLOCKER (wrong number shown
  confidently / money or quota leak) > MAJOR (functional break on a supported path) > MINOR >
  COSMETIC.
- Golden vectors and `prototype/index.html` are untouchable. `shell/.env` contains a real API
  key — never print or commit its contents.
- Real Gemini calls cost prepaid credits: at most a handful, only where the question genuinely
  requires a live call (budget/replacement semantics are testable with the existing mock
  patterns instead).
- Report file: **`shell/EVAL_OCR_PANEL_QA2.md`** (new file; do not edit QA1). Structure:
  verdict up front, findings by severity with probes, then the per-scope-item evidence log.
  Do not commit — the coordinator reviews and commits.

## Environment notes (Windows, verified)

- PowerShell 5.1: no `&&`; native quoting breaks on embedded double quotes.
- `node --test` needs explicit file paths (directory form fails on this Node 24).
- Run the server per `docs/OCR_TEST_INSTRUCTIONS.md` §1 but on a **different port (e.g. 8215)**
  — :8200 is occupied by the owner's instance.
- Python: `py` launcher. Suites: `py -m pytest shell/tests -q`;
  benchmark opt-in: `py -m pytest -m benchmark shell/tests/test_ocr_panel_benchmark.py -q -s`.
