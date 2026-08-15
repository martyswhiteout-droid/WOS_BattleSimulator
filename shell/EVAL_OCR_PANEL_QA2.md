# OCR Panel — QA Round 2 Report (independent, post-merge)

> Executed against `docs/plans/2026-08-15-ocr-qa2-postmerge-charter.md`, fresh context, adversarial/
> evidence-only. Target: merged `master` @ `64921da` (confirmed — session HEAD matched the charter's
> commit exactly; no checkout needed). Prior evidence: `shell/EVAL_OCR_PANEL_QA1.md` (6 rounds,
> D-001..D-042, L4 gate CLOSED). This round fixed nothing; all findings are reported for the
> coordinator to triage.
>
> Scratch probe scripts live in `shell/tmp_qa2/` (created this round) — safe to delete after review;
> every script is also reproduced inline below so the report stands on its own.

## VERDICT: DEFECTS-FOUND — 1 BLOCKER, 2 MAJOR, 2 MINOR

The merge is **not** ship-clean. The headline issue (D-043) reopens the exact failure class
`DEFECT-005`/`D-022` were built to eliminate — a confidently-labeled `status: "ok"` battle/scout
read that silently converts to a **wrong** scout-net value (worst case reproduced: **367.4
percentage points**, on account A's real numbers) — reachable via the single most natural real
capture mistake a user can make (photograph the panel you can see; never notice the "!" icon that
opens a second, separate specials popup). It is protected by a regression test that encodes the bug
as correct behavior, so it will not self-heal.

Everything else probed — the RapidOCR adapter's error paths/contract/determinism, the Gemini
adapter's budget/replacement/resilience machinery, the account-C fixture's internal consistency, and
the tesseract dead-code claim — held up clean under adversarial testing. Suites are exactly at their
claimed baseline (341 py / 144 node, 143 pass + 1 skip / 7 style guard).

| ID | Severity | One-line summary |
|---|---|---|
| D-043 | **BLOCKER** | `SPECIALS_PANEL_HEADERS = {"header:Stat Bonuses"}` conflates the main class-stat panel's own title with the separate specials popup's title, in both languages — a battle/scout screenshot with no specials popup captured reads as `specials_observed: "read"` (not `"none"`), silently identity-converting battle numbers into a wrong "scout-net" value. |
| D-044 | MAJOR | The S4/S5 review completion chip (`computeTally`/`computeChipText`) reflects only raw per-field OCR readability, never conversion-readiness — a side `convertSide()` refuses (`needs_specials`) can still show "All N numbers in ✓" while `buildFillPlan` silently leaves that side's simulator fields untouched, with no on-screen explanation anywhere. |
| D-045 | MINOR | `docs/OCR_TEST_INSTRUCTIONS.md` §3 mischaracterizes `C_battle_3.png`+`C_battle_4.png` as "the two-part scroll of the battle stat panel"; they are the main panel and a separate "Notes on Special Bonuses" popup. In-app UI copy never explains the popup is needed either. |
| D-046 | MAJOR | `test_ocr_panel_benchmark.py`'s D2 gate asserts `any(report["passed"] for report in reports)` — a fully-broken RapidOCR report (the production primary engine) can hide behind a passing Gemini report whenever a real `GEMINI_API_KEY` is configured, as it is in this checkout. |
| D-047 | MINOR | `engine_rapidocr.py` has zero dedicated unit tests (only the gated real-image benchmark and one identity-pin exercise it), and `ladder.py`'s `_load_rapidocr()` import-failure → `EngineUnavailable` wrapping is untested at the unit level. Both confirmed to behave *correctly* by direct probe — this is a coverage gap, not a functional bug. |

---

## Findings

### D-043 [BLOCKER] — "Stat Bonuses" header falsely satisfies the specials-capture gate; silent wrong conversion, worst case 367.4pp

**Where:** `shell/app/ocr/panel/lexicon.py:38` (`SPECIALS_PANEL_HEADERS = frozenset({"header:Stat Bonuses"})`) and its byte-identical JS mirror `shell/app/ocr/client/panel_parser.mjs:43`; consumed by `shell/app/ocr/panel/service.py`'s `_specials()` (and `panel_parser.mjs`'s equivalent), which both `engine_rapidocr`-driven and `engine_gemini`-driven reads pass through (`engine_gemini.py` imports `_specials` directly from `service.py`).

**What's wrong:** `_specials()` sets `specials_observed = "read"` (never `"partial"`/`"none"`) whenever the `"header:Stat Bonuses"` token is seen, *even with zero `special:` rows present*, on the documented theory that this is "the legal zero-specials account: the panel WAS captured and read" (`test_qa_defect_022_specials_panel_header_with_no_rows_reads_clean`'s own comment). But **"Stat Bonuses" is the title of the main class-stat rows panel itself** — it appears on *every* scout/battle screenshot regardless of whether specials were ever shown. The actual specials list lives on a **separate screen**: a "Notes on Special Bonuses" popup reached by tapping a small "!" icon next to the "Stat Bonuses" header — visually confirmed against the real fixtures (`shell/tests/fixtures/panel_ocr/images/C_battle_3.png` = the complete 12-row/24-value class-stat panel, titled "Stat Bonuses"; `C_battle_4.png` = the separate "Notes on Special Bonuses" popup). Neither `_HEADERS` nor `SPECIALS_PANEL_HEADERS` recognizes that popup's own title at all.

The result: **any battle or scout capture that omits the specials popup — the single most natural thing for a user to do, since nothing in the product tells them to also grab it — is indistinguishable from "this account genuinely has zero specials."** `convert.fold_sets(observed="read")` then folds an all-zero `S_scout`/`S_battle`/`P_enemy` instead of raising `MissingSpecialsError`, and `battle_to_scoutnet` silently returns the raw battle numbers as if they were scout-net values (identity conversion) for every stat the true specials would have moved — **exactly `DEFECT-005`'s original failure mode**, reopened via a different path than the one D-005/D-022 closed.

**Live reproduction (real server, real RapidOCR, real fixture image, zero Gemini spend):**
```powershell
py -m uvicorn shell.app.main:app --port 8215 --env-file shell/.env
# separate shell:
curl -X POST http://127.0.0.1:8215/shell/ocr/panel -H "X-Dev-Plan: pro" `
  -F "file=@shell/tests/fixtures/panel_ocr/images/C_battle_3.png;type=image/png" `
  -F "side=you" -F "panel=battle"
```
Observed: `"status": "ok"`, `"specials_observed": "read"`, `"specials": []`, `"unreadable_fields": []` —
even though account C genuinely has a `+7.5%` "Defender Troops' Attack" special (visible only in
`C_battle_4.png`, not uploaded here, and not read). Account C's own numbers happen to mask the
*downstream* damage (its `S_scout == S_battle`, so the true conversion is *also* an identity for this
one account — coincidence, not correctness), which is exactly why this slipped through 6 prior QA
rounds. It does **not** mask on an account with asymmetric fold sets — see the quantified probe below.

**Quantified downstream damage, using account A's real golden-vector numbers (no live calls, pure
function probe against the real `service.extract_panel` + `convert.fold_sets` + `convert.
battle_to_scoutnet`):**
```python
# save as probe.py, run: py probe.py
import sys; sys.path.insert(0, ".")
from shell.app.ocr.panel.service import extract_panel
from shell.app.ocr.panel.convert import fold_sets, battle_to_scoutnet
import json
A = json.load(open("shell/tests/fixtures/panel_ocr/golden_vectors.json"))["accounts"]["A"]
CLASSES, STATS = ("Infantry","Lancer","Marksman"), ("Attack","Defense","Lethality","Health")

def tok(text,x0,y0,x1,y1,conf=0.99,color=None):
    t={"text":text,"x0":x0,"y0":y0,"x1":x1,"y1":y1,"conf":conf}
    if color: t["color"]=color
    return t

shot=[tok("Stat Bonuses",0.30,0.02,0.70,0.05)]  # the panel's own title -- nothing else
y=0.10
for cls in CLASSES:
    for st in STATS:
        shot.append(tok(f"{cls} {st}",0.38,y,0.58,y+0.03))
        shot.append(tok(f"+{A['battle_left'][cls][st]}%",0.03,y,0.23,y+0.03,color="green"))
        shot.append(tok(f"+{A['battle_right'][cls][st]}%",0.70,y,0.90,y+0.03,color="red"))
        y+=0.05

r = extract_panel([shot], side_hint="you", panel_hint="battle")
print("specials_observed:", r["specials_observed"], "specials:", r["specials"], "status:", r["status"])
# -> specials_observed: read  specials: []  status: ok   (should be "none" -> MissingSpecialsError)

S_scout,S_battle,P_enemy = fold_sets(r["specials"], [], observed=r["specials_observed"])  # does NOT raise
nested = {c:{} for c in CLASSES}
for k,v in r["stats_left"].items():
    c,s = k.split("|",1); nested[c][s]=v
converted = battle_to_scoutnet(nested, S_scout, S_battle, P_enemy)
worst = max(abs(converted[c][s]-A["scout"][c][s]) for c in CLASSES for s in STATS)
print("worst silent error:", round(worst,1), "pp")   # -> 367.4 pp, Infantry|Attack
```
Full annotated version with a per-cell table: `shell/tmp_qa2/probe_specials_header_confusion.py`
(run: `py shell/tmp_qa2/probe_specials_header_confusion.py`). Output confirmed this session:
`specials_observed: read`, `specials: []`, `status: ok`, worst error **367.4pp on Infantry|Attack**
(Lancer/Marksman Attack ~366/364pp; Defense ~117-119pp; Lethality ~109-111pp; Health ~152-157pp — all
12 cells wrong, none flagged).

**Existing regression test that locks the bug in as intended behavior** (currently PASSING, part of
the 341-green baseline — this is not a gap, it is an *active guard against the correct fix*):
`shell/tests/test_ocr_panel_service.py::test_qa_defect_022_specials_panel_header_with_no_rows_reads_clean`,
plus its JS mirror around `panel_parser.test.mjs:319` (`headerOnly.push(tok('Stat Bonuses', ...))`).
A correct fix (recognizing that "Stat Bonuses" says nothing about the specials popup, mirroring how
`"Bonus Overview"` is *already* deliberately excluded for the identical reason — see the comment
directly above `SPECIALS_PANEL_HEADERS`) will need to update or replace this test, not just the
production code.

**Cross-language / cross-engine reach:** confirmed identical in `panel_parser.mjs` (JS) via direct
grep (`SPECIALS_PANEL_HEADERS = new Set(['header:Stat Bonuses'])`, `panel_parser.mjs:43`), and
inherited by `engine_gemini.py`'s `_assemble_result` (imports `_specials` directly from `service.py`
rather than reimplementing it — confirmed by direct line-by-line diff, see the D-043-adjacent note
in the Item-2 evidence log below). A Gemini-driven read of the same "main panel only" capture would
reproduce the identical false "read" verdict.

**Recommended fix shape (not applied — brief only):** stop treating `"Stat Bonuses"` as evidence the
specials panel was captured; either drop it from `SPECIALS_PANEL_HEADERS` entirely (falls back to
`"none"` when zero special rows are seen, forcing an explicit specials capture every time — always
safe, possibly annoying for genuinely specials-free accounts) or add a *real* header for the popup
("Notes on Special Bonuses" / "Stats Bonuses include the following Special Bonuses:") to `_HEADERS`
and key `SPECIALS_PANEL_HEADERS` off *that* instead.

---

### D-044 [MAJOR] — Review/setup completion UI is blind to conversion-readiness; can claim "All N in" while a side is silently left unfilled

**Where:** `shell/app/ocr/client/fill_mapper.mjs`'s `classifyFields` → `shell/app/ocr/client/
screens/review.mjs`'s `computeTally` → `shell/app/ocr/client/screens/setup.mjs`'s `computeChipText`/
`renderS5`, versus `shell/app/ocr/client/convert_side.mjs`'s `convertSide` → `setup.mjs`'s
`buildFillPlan`.

**What's wrong:** `classifyFields` (and therefore the S4 review grid and the S5 completion chip) is
computed purely from raw per-field OCR readability (`stats`/`fieldConf`/`fieldEngine`) — it has no
input from, and never cross-references, `convertSide()`'s outcome. `buildFillPlan` (correctly, per
its own D-042 regression test) never fills a side whose conversion is `needs_specials` or otherwise
not `"ready"`. But nothing tells the *user* this happened: the completion chip can read "All 24
numbers in ✓ — tap to check" (a "clear" tally, 100% raw fields present) while that exact side's
simulator-form fields are left completely untouched by `applyFillPlan` (no `win.applyPanel(...)`
call for that side at all, since `plan.me`/`plan.foe` is `null`). `convert_side.mjs` does compute a
`rawUnconverted` fallback value precisely for this situation (matching `docs/OCR_QA_PLAN.md` P16's
requirement: "falls back to raw battle values EXPLICITLY LABELED as unconverted — never silently
wrong-mode") — but it is never read anywhere: `grep rawUnconverted shell/app/ocr/client/screens/
*.mjs` returns nothing.

This does not itself fabricate a wrong *stat value* (the field is left at its prior/default value,
not overwritten) — that is why it is MAJOR rather than BLOCKER — but it is a real, confirmed break in
the "never a dead end, tally always honest" contract (`docs/OCR_QA_PLAN.md` F4/F6/F12), and it
compounds D-043 directly: even after D-043 is fixed and `specials_observed` correctly comes back
`"none"`, this gap remains — the completion screen still won't tell the user why a side came up
empty.

**Reproduction (real shipped modules, no server, deliberately uses a *correctly*-refused
`specials_observed: "none"` — independent of D-043):**
```powershell
node shell/tmp_qa2/probe_review_tally_blind_to_conversion.mjs
```
```
tally.clear: true
S5 chip text the user actually sees: "All 12 numbers in ✓ — tap to check"
convertSide() outcome: needs_specials
reason: the Stat Bonuses screenshot for this side has not been fully read yet
[FINDING] tally.clear === true while convertSide() outcome is "needs_specials" ...
```
Minimal inline version (same result, self-contained):
```js
// probe.mjs — node probe.mjs (run from repo root)
import { classifyFields } from './shell/app/ocr/client/fill_mapper.mjs';
import { computeTally } from './shell/app/ocr/client/screens/review.mjs';
import { convertSide } from './shell/app/ocr/client/convert_side.mjs';
const keys = ['Infantry','Lancer','Marksman'].flatMap(c =>
  ['Attack','Defense','Lethality','Health'].map(s => `${c}|${s}`));
const stats = Object.fromEntries(keys.map(k => [k, 1000.0]));
const fieldConf = Object.fromEntries(keys.map(k => [k, 0.999]));
const states = Object.values(classifyFields({ expectedKeys: keys, stats, fieldConf, fieldEngine: {} }))
  .map((s) => s.state);
console.log('tally.clear:', computeTally(states).clear);
console.log('conversion outcome:', convertSide({
  panelType: 'battle', stats, specialsOwn: [], specialsEnemy: [], specialsObserved: 'none',
}).outcome);
```

---

### D-045 [MINOR] — Owner walkthrough doc mischaracterizes the two battle-report screenshots; in-app copy never explains the specials popup either

**Where:** `docs/OCR_TEST_INSTRUCTIONS.md` §3 step 2: *"Upload `C_battle_3.png` and `C_battle_4.png`
together (the two-part scroll of the battle stat panel; the server stitches them)."*

**What's wrong:** Visual inspection of the actual fixture images
(`shell/tests/fixtures/panel_ocr/images/C_battle_3.png`, `C_battle_4.png`) shows this is not
accurate: `C_battle_3.png` already contains the *complete* 12-row/24-value class-stat panel by
itself (nothing is cut off or continued); `C_battle_4.png` is a separate "Notes on Special Bonuses"
popup, reached in-game by tapping a small "!" icon next to the "Stat Bonuses" header — a materially
different physical action from "keep scrolling the same screen." The *functional outcome* the doc
promises (24 digit-exact fields, the specific table) is real and was reproduced live this round (see
Item 6 evidence log) — the doc is not lying about the result, only about *why* two screenshots are
needed and *what they physically are*. `test_ocr_panel_benchmark.py`'s own `_discover_cases()` and
`docs/GEAR_LADDERS.md`'s account-A note (`A_battle_3` = the stat panel, `A_battle_4` = specials panel)
already classify them correctly as two different panel *kinds* — only the owner-facing walkthrough
prose gets it wrong.

Compounding this: `shell/app/ocr/client/screens/pick_upload.mjs`'s in-app copy for "Battle Report"
(`"Long list? Take 2 screenshots that share a row. We'll join them."`) describes only the genuine-
scroll case and never mentions the specials popup at all — grep-confirmed (`grep -i special
shell/app/ocr/client/screens/pick_upload.mjs` → no matches). A user following either the doc or the
in-app copy alone, without already knowing to tap the "!" icon, has no guidance toward avoiding the
D-043 trap.

**Reproduction:** open the two images and compare against the doc's claim.
```powershell
# visually: shell/tests/fixtures/panel_ocr/images/C_battle_3.png is the FULL panel (all 12 rows,
# both columns, "Stat Bonuses" header). C_battle_4.png is a DIFFERENT screen ("Notes on Special
# Bonuses" title, reached via the "!" icon) -- not a scroll continuation of the first.
grep -i "special" shell/app/ocr/client/screens/pick_upload.mjs   # -> no matches
```

---

### D-046 [MAJOR] — Benchmark D2 gate's `any()` semantics can mask a broken primary (RapidOCR) engine behind a passing Gemini report

**Where:** `shell/tests/test_ocr_panel_benchmark.py::test_real_engine_adapters_clear_phase0_bar`,
final line: `assert any(report.get("passed") for report in reports), reports`.

**What's wrong:** The gate passes if **any one** of {rapidocr, tesseract, gemini} clears the D2 bar
(≥99% digit accuracy, zero false-confident). `engine_gemini.py`'s own docstring states binding
decision #6 as "the D2 verdict... must still stand on RapidOCR alone regardless of Gemini's
presence" — but the code enforces "stands on *any* engine," not "stands on RapidOCR specifically."
Concretely: if RapidOCR (the actual free, local, unmetered production **primary** engine) regressed
to 0% accuracy, the assertion would still pass — and CI would go green — as long as a real
`GEMINI_API_KEY` is configured (as it is in `shell/.env` in this checkout) and Gemini's own read
happens to clear the bar. `tesseract` never masks this in practice (historically 64-76%, always
`passed: False`), and without a Gemini key the gate correctly hinges on RapidOCR alone — the risk is
specific to environments with a live key, which includes this one.

This does not put a wrong number in front of an end user by itself (the printed
`OCR_BENCHMARK_JSON=` line still carries the honest per-engine breakdown, so a human reading full
output — not just the exit code — would catch it), which is why this is MAJOR rather than BLOCKER:
it is a release-*gate* integrity issue, exactly the class of thing scope item 3 asked to be checked
("a broken harness could false-PASS the release gate").

**Reproduction (synthetic data, zero live API/network calls, uses the real `_summary()`/`_score()`
aggregator functions imported from the actual test module):**
```powershell
py shell/tmp_qa2/probe_benchmark_gate_masking.py
```
```
[INFO] synthetic degraded RapidOCR summary: passed=False (accuracy=0.0)
[INFO] synthetic clean Gemini summary (via REAL bench._summary()): passed=True (accuracy=1.0)
[RESULT] reports passed-flags: rapidocr=False tesseract=False gemini=True
[RESULT] `assert any(report.get('passed') for report in reports)` would PASS (green CI) even though
the PRIMARY production engine (RapidOCR) scored 0% accuracy
```
Minimal inline version:
```python
import os, sys; os.environ["OCR_PANEL_BENCHMARK"] = "1"; sys.path.insert(0, "shell/tests")
import test_ocr_panel_benchmark as bench
degraded = {"engine": "rapidocr", "digit_accuracy": 0.0, "false_confident": 0, "passed": False}
clean_gemini = bench._summary("gemini", [{"image": "x", "fields_read": 12, "expected_fields": 12,
    "correct_digits": 50, "total_digits": 50, "digit_accuracy": 1.0, "false_confident": 0,
    "panel_type": "scout", "status": "ok", "latency_ms": 1.0}])
print(any(r["passed"] for r in (degraded, clean_gemini)))   # -> True (gate would pass)
```

---

### D-047 [MINOR] — `engine_rapidocr.py` has zero dedicated unit tests; `ladder.py`'s RapidOCR-load-failure path is untested (both confirmed correct by direct probe)

**Where:** `shell/app/ocr/panel/engine_rapidocr.py` (no `test_ocr_panel_rapidocr.py` or equivalent
exists — confirmed by grep: the module is referenced only from `test_ocr_panel_ladder.py`, where it's
monkeypatched away or identity-pinned, and from the `@pytest.mark.benchmark`-gated real-image
benchmark, which only exercises the happy path); `shell/app/ocr/panel/ladder.py:387-390`'s
`try: recognize = _load_rapidocr() except Exception as exc: raise EngineUnavailable(...)`.

**What's wrong:** every other adapter file in scope (`engine_gemini.py`, `ladder.py`) has thorough,
specific unit-test coverage for error paths, contract shape, and failure modes; `engine_rapidocr.py`
does not, and neither does the two-line exception-wrapping block in `ladder.py` that turns a
RapidOCR-import failure into the `EngineUnavailable` → 503 the router promises (contrast
`test_gemini_engine_import_failure_degrades_gracefully`, which *does* exist for the equivalent
Gemini path). This is pure test debt, not a functional defect — every behavior probed below (error
paths, output contract, determinism, the import-failure wrapping) was confirmed **correct** by direct
adversarial probing against the real module this session — but a future regression in any of these
paths (e.g. someone "simplifying" the try/except, or a RapidOCR version bump changing its output
shape) would ship undetected by any automated gate.

**Reproduction — confirms current behavior is correct, and that no test would catch a regression:**
```powershell
py shell/tmp_qa2/probe_rapidocr_errors.py          # 11/11 checks PASS (error paths, contract, determinism)
py shell/tmp_qa2/probe_ladder_rapidocr_loadfail.py # PASS: ImportError from _load_rapidocr() -> EngineUnavailable
grep -rn "engine_rapidocr\b" shell/tests/          # only test_ocr_panel_ladder.py (identity-pin) and
                                                    # test_ocr_panel_benchmark.py (gated happy-path)
```

---

## Cosmetic observations

None beyond what's folded into D-045 above (which is substantive enough to number on its own).

---

## Per-scope-item evidence log

### 1. `engine_rapidocr.py` — adapter debt

- **Weakref-keyed loop-bound semaphore, id-reuse hazard** (`ladder.py`'s `_cpu_semaphore`/
  `_cpu_semaphores`, not literally inside `engine_rapidocr.py` but the mechanism the charter's item 1
  names): **checked via forced adversarial reproduction, clean.** `id()` collisions across
  `asyncio.run()` cycles are not rare on this platform/build (CPython 3.14 / Windows) — **196 of 200**
  cycles collided naturally in one run (`py shell/tmp_qa2/probe_semaphore_idreuse.py`), and a forced
  `gc.collect()`-based reproduction confirmed a genuine collision on the very first extra loop. In
  every case the weakref-alive check correctly rebuilt a *fresh* semaphore rather than inheriting the
  dead loop's — the existing regression test
  (`test_qa_defect_030_a_recycled_loop_id_does_not_inherit_a_dead_semaphore`) is exercising real
  signal, not passing vacuously.
- **`OCR_CPU_CONCURRENCY` clamp [1,8]:** checked by reading `_cpu_concurrency` plus its 6 existing
  `test_qa_defect_032_*` tests (in-range passthrough, out-of-range clamp+warning, garbage-value
  default+warning, absent-setting default silently, clamp actually resizes the semaphore) — all
  present, all green, no gap found.
- **Error paths (corrupt image, zero-text image, engine import failure):** checked via
  `probe_rapidocr_errors.py` (11 checks, all PASS) — non-bytes input raises `TypeError`; corrupt bytes
  and a truncated-mid-body PNG both raise `ValueError("unsupported or malformed OCR image")`, never a
  silent bad result; a genuinely blank/solid-color image returns `[]` without crashing (nothing
  fabricated from nothing to read); `bytearray`/`memoryview` are accepted per the documented
  bytes-like contract. Engine import failure (`ladder._load_rapidocr()` raising `ImportError`)
  correctly becomes `EngineUnavailable` (`probe_ladder_rapidocr_loadfail.py`) — see D-047 for the test
  gap this behavior is otherwise unguarded by.
- **Output contract (tokens + confidences shape expected by `service.py`):** checked against a real
  fixture image (`C_scout.png`, 43 tokens) — every token satisfies `{text, x0, y0, x1, y1, conf,
  color}` with `0<=x0<x1<=1`, `0<=y0<y1<=1`, `0<=conf<=1`, `color in (None,"green","red")`. Confirmed
  on `C_battle_3.png` too (two-column battle image): 24 of 54 tokens correctly carry a color.
- **Determinism across repeated runs on the same fixture:** checked directly — `recognize_image()`
  invoked 3 times on the byte-identical `C_scout.png`, output field-for-field identical across all 3
  runs (text/coords rounded to 1e-6/conf/color). RapidOCR (ONNX Runtime backend, this environment) is
  deterministic on repeat CPU inference for this fixture.
- **`engine_rapidocr.py` has no dedicated test file** — see D-047.

### 2. `engine_gemini.py` — adapter debt

- **Budget committed BEFORE the call:** confirmed by reading `ladder._gemini_gap_fill` — `db.
  record_usage(...)` executes before `asyncio.to_thread(extract_gemini, ...)`, with an explicit
  comment ("pre-committing means no crash can leak an unmetered call"). Confirmed by the existing
  `test_gemini_exception_degrades_gracefully`, which asserts `len(_gemini_events()) == 1` even though
  the simulated call *raised*. No gap.
- **`GEMINI_OCR_DAILY_BUDGET` day rollover:** the budget check calls the shared `db.get_usage_today`,
  which recomputes UTC day bounds fresh on every call (`_day_bounds(_utcnow().date())`) — there is no
  ladder/Gemini-specific day math to diverge. The generic primitive is directly tested
  (`test_usage_today_counts_only_today_and_kind` in `test_db_core.py`: a yesterday-dated event is
  proven not to count). No ladder-specific rollover test exists, but none is needed — there is nothing
  kind-specific left to test once the shared primitive is trusted, and it is.
- **Per-(label,side) replacement never overwrites a confident RapidOCR field:** confirmed by
  reading — `_fill_gaps` iterates *only* `result["unreadable_fields"]`, so a field RapidOCR already
  read structurally cannot be revisited. Confirmed by `test_gemini_value_for_a_field_rapidocr_read_
  is_ignored` and the three `test_qa_defect_029_*` side-aware-specials tests (a fill for one side of a
  two-column special can never disturb the other side's already-read entry).
- **No-key behavior (`GeminiUnavailable` before any HTTP):** confirmed by
  `test_missing_key_raises_before_any_http_call`, which wires an httpx transport that raises
  `AssertionError` if invoked at all — mutation-proof by construction (any reordering that let the
  key check happen after client construction would trip this test).
- **API-error surfacing into response warnings:** confirmed by `test_persistent_5xx_exhausts_retry_
  budget_and_fails_cleanly` and the three `test_malformed_or_empty_gemini_response_*` parametrized
  cases — all degrade to `status: "failed"` with a diagnostic warning, never an exception past the
  public entry point.
- **Validation rejections (null / wrong-format / out-of-range → unreadable, never emitted):**
  confirmed by `test_null_value_row_is_unreadable_not_emitted`, `test_wrong_format_value_is_
  unreadable_not_emitted`, `test_out_of_range_class_value_is_unreadable`, `test_out_of_range_special_
  value_is_unreadable`.
- **"Reuses gating helpers verbatim" claim — independently verified, not just read:** extracted the
  34-line shared tail from both `service.py::extract_panel` (from `specials, special_unreadable,
  specials_observed = _specials(rows)` onward) and `engine_gemini.py::_assemble_result`, diffed them
  programmatically line-by-line: **zero differences.** `attach_side_specials`/`_bucket`/`_dedupe`/
  `_hint_warning`/`_specials` are imported directly, not reimplemented. The docstring's claim holds.
- **D-043 reach:** `engine_gemini.py` imports `_specials` from `service.py` directly, so a
  Gemini-driven extraction inherits D-043 identically — not re-probed separately since the shared
  function is the same object under test either way.

### 3. `test_ocr_panel_benchmark.py` — the harness itself

- **`_benchmark_selected()` selection logic:** traced by hand against every realistic invocation.
  `-m benchmark` → selected (correct). `-m "not benchmark"` → not selected (the substring-`in`-check
  correctly negates via the exact-string re-check, confirmed by tracing the code, not just eyeballing
  it). The plain default suite (`py -m pytest shell/tests -q`, no `-m` flag at all) → not selected,
  confirmed empirically: the file defined and ran zero tests during this session's baseline 341-pass
  run. `OCR_PANEL_BENCHMARK=1` env-var override → selected, used deliberately in this round's own
  probes to import the module's guarded top-level code without spending any live API budget.
- **D2 gate arithmetic (digit accuracy, false-confident counting):** `_digit_score`/`_digits` render
  the observed value at the *expected* value's own decimal-place count before diffing digit strings
  by edit distance — traced through worked examples (exact match, one-digit-off, garbage/oversized
  observed value) by hand; all behave as intended. `false_confident` in `_score()` is scoped correctly
  per case — it checks every *observed* field against the full account map (not just the fields
  visible in that particular half-image), so a half-panel image's legitimately-partial `expected_keys`
  never triggers a false false-confident flag. Found: D-046 (`any()` gate masking).
- **Scope note (not a defect):** the benchmark scores each image *independently*
  (`extract_panel([tokens], ...)`, a one-element list) — it never exercises the multi-image `stitch()`
  path a real two-shot upload goes through, and it never touches `fold_sets`/`battle_to_scoutnet` at
  all. Its "100% digit accuracy" claim is a raw-per-image-extraction claim only; it would not have
  caught D-043 or D-044 even if run, and does not claim to. The real stitched-upload path is covered
  separately by `test_ocr_panel_stitch.py` (synthetic) and was independently re-confirmed live this
  round (Item 6, below).

### 4. Fixture/vector integrity — `golden_vectors.json` account C

- **Battle column ↔ scout column under the recorded specials:** already covered by the existing,
  green `test_ocr_panel_convert.py::test_battle_to_scoutnet_recovers_scout_panel[C]`, which calls the
  **real** `convert.battle_to_scoutnet` (not a re-derivation) against account C's `battle_left` +
  `fold_sets(specials_own, specials_enemy, observed="read")` and checks the result against the
  recorded `scout` column within 0.11pp. Re-verified this round by re-running the suite (green) and by
  reading the test to confirm it calls the production function, not an independent formula (a real
  risk in a fixture-integrity check — confirmed unfounded here).
- **`fold_sets` reproduces the documented S/P sets:** `test_fold_sets_reproduce_documented_sets[C]`,
  also green, also calling the real function.
- **`bo_troops + bo_class + U` reconcile:** account C uses a **per-class** U (mixed-generation trio),
  so `convert.calibrate_U`'s uniformity guard structurally excludes it from the existing `test_
  calibrate_U_matches_documented_block` test (parametrized `["A","B"]` only, by design). No existing
  test recomputes account C's per-class U at all. New probe this round
  (`shell/tmp_qa2/probe_account_c_u_reconcile.py`): re-derived per-class U straight from
  `golden_vectors.json`'s own `(bo_troops, bo_class, scout, S_scout)` using the identical inner
  arithmetic `calibrate_U` uses (minus its cross-class uniformity check, which doesn't apply to a
  mixed-gen trio by design), and cross-checked against `docs/GEAR_LADDERS.md`'s "Account C" section
  (Inf/Lan/MM × Atk/Def/Leth/HP, 12 cells). **Worst residual: 0.0021pp** (float-precision noise) — the
  fixture has not drifted from the doc.
- **Label/value-grammar cases:** not re-probed this round (already covered by the existing green
  `test_ocr_panel_lexicon.py`/`test_ocr_panel_values.py`, unchanged since QA1; charter's item 4 scoped
  the ask specifically to account-C internal consistency).

### 5. `engine_tesseract.mjs` — confirm dead code

- **Not imported by any live UI module:** `grep -rn "import.*engine_tesseract" shell/app/ocr/client`
  (whole directory) → **zero matches**. The only references anywhere in the repo are
  `test_ocr_panel_benchmark.py` (the gated benchmark, via a Node subprocess), `test_overlay_ocr_
  client_assets.py` (asset-presence check, not an import-graph check), a `main.py` comment explaining
  the static mount, a `vendor/node_modules/.gitignore` comment, an `ocr_flow.js` comment, and historical
  `docs/plans/*.md` design documents (not live code).
- **`ocr_flow.js` (the real bootstrap) explicitly documents the exclusion:** *"No recognizeImage:
  SERVER-ONLY v1 (COORDINATOR RULING 2026-08-10 #1) — every read goes straight to `/shell/ocr/panel`'s
  production ladder, nothing client-side to inject here (`engine_tesseract.mjs` stays the future
  client tier)."*
- **No network fetch of models at page load:** the static mount (`main.py`) only makes the file
  *fetchable on request*; nothing in the served page/JS triggers that fetch automatically.
- **No CDN reference (self-containment rule):** `grep -rEno "https?://..."` across
  `shell/app/ocr/client/*.mjs`/`*.js` (excluding `vendor/`) → zero matches. The tesseract.js runtime
  (`vendor/node_modules/tesseract.js*`, `@tesseract.js-data`, `pngjs`, etc.) is fully vendored locally;
  the only `http(s)://` strings anywhere under the client tier live inside third-party vendor
  test/README files (`is-url`'s own test fixtures, `node-fetch`'s doc links), never executed at
  runtime and never fetched over the network.

### 6. Whole-feature spot check on master

- **Suites (fresh run, this session):** `py -m pytest shell/tests -q` → **341 passed**. `node --test`
  (13 explicit files per `docs/OCR_TEST_INSTRUCTIONS.md` §8) → **144 tests, 143 pass, 1 skipped, 0
  fail**. `py -m pytest wos_sim/predictor/tests/test_ui_style_guard.py -q` → **7 passed**. All three
  exactly match the merge commit's own claimed baseline.
- **Server boot:** `py -m uvicorn shell.app.main:app --port 8215 --env-file shell/.env` — clean start,
  no errors/tracebacks in the log for the whole session (`shell/tmp_qa2/server.log`).
- **Free-tier 402 signal:** `POST /shell/ocr/panel` with no `X-Dev-Plan` header (DEV_BYPASS default =
  free) → **`HTTP 402`**, `{"error": "payment_required", "message": "Screenshot OCR is a Pro feature.
  Upgrade to use it."}`. Matches the charter's expectation and the D-031 amendment referenced in QA1.
- **Pro path via `X-Dev-Plan` header (sanctioned technique, `docs/OCR_QA_PLAN.md` §8):** `POST /shell/
  ocr/panel` with `X-Dev-Plan: pro`, uploading `C_battle_3.png` + `C_battle_4.png` together, `side=you
  panel=battle` → **`HTTP 200`**, `status: "ok"`, `engines_used: ["rapidocr"]` (RapidOCR alone
  sufficed — **zero live Gemini calls made this entire session**, confirmed by the absence of any
  Gemini network log line and by `field_engine: {}`), `stats_left`/`stats_you` and `stats_right`/
  `stats_enemy` **digit-exact against `golden_vectors.json`'s account-C `battle_left`/`battle_right`
  on all 24 fields**, `specials_observed: "read"` with the correct `+7.5`/`+0.0` "Defender Troops'
  Attack" row on each side. This reproduces QA1's L4 headline measurement live, on this merge.
- **Uploading only `C_battle_3.png` (no specials popup)** — this same check is what surfaced D-043/
  D-045: raw stats still 12/12 + 12/12 with `status: "ok"`, but `specials_observed` came back `"read"`
  with `specials: []` instead of the honest `"none"` (account C's own numbers happen to mask the
  *conversion*-level damage this causes on other accounts — see D-043).
- **No image persistence / no secrets leaked:** `shell/tmp_qa2/` scratch files (response captures,
  server log) grepped clean for API-key-shaped strings before being left in place for cleanup.

---

## Cleanup note

Scratch probe scripts and captured HTTP responses/log for this round live in `shell/tmp_qa2/`
(7 probe scripts, 2 response+header pairs, 1 server log — all confirmed free of secrets). Safe to
delete; nothing in this report depends on the folder still existing (every probe is reproduced inline
above).

---

# COORDINATOR RESOLUTION (2026-08-15, same night)

All five findings were fixed within hours of the report, each with regression tests, per the
owner's standing overnight mandate ("all failed tasks rectified"). Fix commits, in order:

| ID | Fix commit | What landed |
|---|---|---|
| D-043 | `7e27978` | `SPECIALS_PANEL_HEADERS` re-keyed to the popup's REAL title+subtitle (RapidOCR ground truth from `C_battle_4.png`: "Notes on Special Bonuses" / "Stats Bonuses include the following Special Bonuses"); "Stat Bonuses" demoted to an ordinary header. The D-022 test that encoded the bug now uses the popup title; new py+JS regressions cover main-title-only → "none", subtitle-only → "read", and the full-path refusal. Verified per-case against real fixtures through the real engine. |
| D-044 | `04a94e4` | `conversionNotices()` derives per-side notices from the SAME conversion object `buildFillPlan` consumes; chip text + styling reflect them; notice cards render in the S5 body; `applyFillPlan` no longer flips `statsScouted` when it applied nothing. Live-verified: chip reads "All 24 numbers read · your side and the enemy side not filled in", form untouched. |
| D-045 | `8aa0e9b` | Doc §3 rewritten (panel + popup, not a scroll pair; missing-popup variant added as step 6); S2 shows a battle-only hint card naming the ! icon. |
| D-046 | (this commit) | Benchmark D2 gate asserts **rapidocr by name**; gemini asserted too whenever it actually ran; tesseract informational. Full gated run re-executed: rapidocr 1.0/0 false-confident PASS, tesseract 0.643 honestly failing, gemini skipped keyless. |
| D-047 | (this commit) | New `shell/tests/test_ocr_panel_rapidocr.py` (8 fast keyless tests): TypeError/ValueError validation paths, truncated PNG, bytes-like acceptance, None-result → no tokens, stubbed-engine output contract + glued value/label split, and the ladder's `_load_rapidocr` failure → `EngineUnavailable`. |

Suites after all five: **352 py / 150 node (149 pass + 1 documented skip) / 7 style guard.**

Observation (not a defect, for the release list): browser heuristic caching can serve stale
client modules for a while after a deploy (bit this round's own live verification until a fresh
navigation); consider cache-busting module URLs as VPS-deploy hardening.

An independent verification agent re-runs this round's probes + the full suites post-fix; its
sign-off note is appended below when it lands.

## Independent verification sign-off (2026-08-15, post-fix)

A separate verification agent re-ran this round's probe scripts against fixed master
(per the owner's explicit "QA scripts run by a sub-agent" requirement). **VERDICT: ALL
FIXES HOLD.** Evidence highlights: D-043's probe now shows `specials_observed: none` +
hard `MissingSpecialsError` (the 367.4pp silent path is closed); post-fix adapted probes
(`*_postfix.*`) confirm the real chip wiring reports "not filled in" and the shipped
by-name benchmark gate raises on the exact masking scenario D-046 described; D-047's new
unit suite 8/8 with real-ONNX checks intentionally left to the gated benchmark; suites
352/150(149+1)/7 (three clean reruns); gated benchmark rapidocr 1.0 / 0 false-confident
PASS with gemini legitimately skipped keyless; live E2E battle_3-alone → "none",
battle_3+4 → "read" with +7.5/+0.0 sided specials. Full detail was written to
`shell/tmp_qa2/VERIFICATION_SIGNOFF.md` (scratch folder, deleted at closeout — this
summary is the durable record). One transient observation explained: a single 393-count
suite run was the coordinator's integration-branch checkout window (agents B+C merged on
`shell-fix-round2`), not a code effect; three subsequent master runs reproduced 352
exactly.
