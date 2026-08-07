# Codex Task-12 prompt — real OCR engines + accuracy benchmark (paste when the images exist)

**Owner pre-flight:** drop the raw screenshots into `shell/tests/fixtures/panel_ocr/images/` per its README naming scheme (`A_citystats_1.png` … `B_specials.png`). Without them Codex must refuse to start — do not paste this prompt until the folder has PNGs.

---

## PROMPT (paste everything below into Codex)

You are resuming a test-first build you executed earlier (Tasks 0–11 of `docs/plans/2026-08-06-ocr-panel-tdd-plan.md`, branch `ocr-panel-build`). Since your last commit, an independent QA cycle landed **13 additional commits** (`d305143`, `24a6c92`, `562dd45`, `e838c25..97af525` + wording fix) fixing 27 defects — 4 of the blockers originated in the plan's own code blocks. **Read `shell/EVAL_OCR_PANEL_QA1.md` first**: it contains the defect list, the binding rulings, and the cycle outcome. The code you remember has changed.

**Contract deltas since Task 11 (binding — your Task-12 harness must use these):**
1. `assemble_rows(tokens, two_column)` now returns a TUPLE `(rows, warnings)`; value↔label pairing is gated by a per-row vertical band (±0.35·h_row on the label centre, h_row = max(shot median, row label median)); orphan/unmatched values emit warnings.
2. `stitch(rows_per_shot)` consumes/merges the warnings channel; conflicts are sticky.
3. `extract_panel` output: battle responses have NO `stats` key — use `stats_left`/`stats_right` (+`_conf`), plus `stats_you`/`stats_enemy` aliases when `side` was given (left column = the report viewer), `requested_side`, and `specials_observed: "none"|"partial"|"read"`. `unreadable_fields` enumerates never-seen expected keys too. Class-row values outside [0,6000] and specials |v|>25 are withheld as unreadable. `panel_hint` is a compatibility CHECK, not an override (battle-hint + one readable column = legal partial read).
4. `fold_sets(specials_own, specials_enemy, *, observed)` — keyword-only; `observed` must be `"none"|"partial"|"read"` and anything but `"read"` raises `MissingSpecialsError`. `calibrate_U` requires all three classes.
5. All Python value/label regexes are `re.ASCII` (JS parity); mock responses carry `source:"mock"` and the mock flag only works when `Settings.ENV == "dev"`.
6. Router: pre-parse Content-Length ceiling (`MAX_BODY_BYTES + 64KiB` → 413), chunked → 411, aggregate size cap, malformed tokens → 422. Never a 500.
7. JS tests run with EXPLICIT files: `node --test shell/app/ocr/client/tests/panel_parser.test.mjs shell/app/ocr/client/tests/flow_state.test.mjs`.

**Your task: exactly plan Task 12** (`docs/plans/2026-08-06-ocr-panel-tdd-plan.md`, final task), updated only by the deltas above:
- GATE CHECK first: if `shell/tests/fixtures/panel_ocr/images/` has no PNGs, STOP and report. Never substitute synthetic or downloaded images.
- Build `shell/app/ocr/client/engine_tesseract.mjs` and `shell/app/ocr/panel/engine_rapidocr.py` to the adapter contract: image bytes → Task-1 token dicts (normalized 0..1 coords, conf 0..1, `color` populated for battle panels via the G>R+40 / R>G+40 rule). Tesseract: two passes (full for labels, digit-whitelisted `0123456789.,%+-` for value regions), merged by box overlap. New runtime deps (tesseract.js vendored, rapidocr/onnxruntime in `shell/requirements.txt`) must be pinned and committed with rationale.
- Build `shell/tests/test_ocr_panel_benchmark.py`, marked `@pytest.mark.benchmark` and excluded from the default run: for each fixture image → engine → tokens → `extract_panel` → compare against `golden_vectors.json` (the expected values for every image are already there).
- **Pass bar (owner decision D2, non-negotiable): ≥99% digit accuracy across readable fields AND ZERO false-confident fields** (a wrong value emitted into stats = instant FAIL; wrong values may only appear as unreadable/low-conf). If neither engine clears the bar, report the numbers honestly — do NOT loosen `LOW_CONF`, tolerances, or the bar itself.
- TDD protocol as before: failing test → confirm reason → implement → green → full suites (`py -m pytest shell/tests -q` = 255 baseline, node explicit files = 33 baseline, style guard 7) → scoped explicit `git add` commit (`ocr:` prefix). Golden vectors and all `test_qa_defect_*` tests are untouchable — if one goes red, your change is wrong.
- Touch only: the two engine files, the benchmark test, `shell/requirements.txt`, and (if vendoring) a new `shell/app/ocr/client/vendor/` folder. Nothing else.

**Report:** per-engine benchmark table (per image: fields read, digit accuracy, false-confident count, latency), the pass/fail verdict against the bar, commits, final suite counts, and any images the engines could not process at all (list, don't guess).
