# Stat-Panel OCR — TDD Implementation Plan

> **For agentic workers (Codex or Claude subagents):** Execute task-by-task, strictly test-first (red → green → commit). Steps use checkbox syntax. Claude workers: use superpowers:subagent-driven-development or superpowers:executing-plans. You need ZERO prior context — everything is specified here or in the three referenced docs.

**Goal:** Users screenshot in-game stat panels; the app reads them deterministically, converts them to engine inputs via the confirmed panel law, and the flow UI fills the simulator — per `docs/OCR_UX_FLOW_SPEC.md`.

**Architecture:** A shared **golden-vector fixture set** is the single source of truth. An engine-agnostic **token normal form** feeds a pure **deterministic parser** (label lexicon → rows), then a pure **converter** (panel law → scout-net engine input). The parser+converter exist twice — Python (server, RapidOCR path) and JS ES-module (client, tesseract.js path) — both verified against the SAME vectors. UI ships as an overlay-injected module; `prototype/index.html` is never edited. Vision-LLM: not in v1. Free tier: NO OCR (server-enforced).

**Tech stack:** Python 3.11/pytest/FastAPI (shell), vanilla-JS ES modules tested with `node:test` (dev-only; nothing external ships), tesseract.js v7 (vendored, later task), RapidOCR-ONNX (server, later task).

## Global constraints (every task inherits these)

- **Never fabricate:** unreadable ⇒ absent + flagged; never zero, never guessed. No value is emitted below its confidence floor.
- **Determinism:** same input bytes → byte-identical JSON output. No wall-clock, no randomness in parser/converter.
- **User-facing copy:** "screenshot(s)", never "picture"; no jargon (OCR/parse/confidence banned in copy).
- **Free tier = NO OCR** (D1): server rejects with 403 `ocr_not_available_on_free`; client hides entry.
- **Do not modify** `prototype/index.html`, `wos_sim/` engine code, or anything in `WOSTests.com`.
- **Reference docs:** flow = `docs/OCR_UX_FLOW_SPEC.md`; math = `docs/STAT_PANELS_FORMULA.md` (§2 law, §8 recipes, §9 second account); architecture = `docs/OCR_SERVICE_PLAN.md`.
- Commit after every green test, message prefix `ocr:`.
- Run Python tests: `py -m pytest shell/tests/<file> -q` (from repo root `E:\WOS\Battle Simulator`). Run JS tests with EXPLICIT file paths — on Windows, Node treats a bare directory argument as a module and fails with MODULE_NOT_FOUND (verified Node v24.14.1, 2026-08-07): `node --test shell/app/ocr/client/tests/panel_parser.test.mjs shell/app/ocr/client/tests/flow_state.test.mjs` (list only the files that exist yet).

## File structure (locked)

```
shell/app/ocr/panel/__init__.py        # package
shell/app/ocr/panel/tokens.py          # Task 1 — OcrToken normal form + loaders
shell/app/ocr/panel/values.py          # Task 2 — value grammar
shell/app/ocr/panel/lexicon.py         # Task 3 — canonical labels + fuzzy match
shell/app/ocr/panel/rows.py            # Task 4 — row assembly (1-col + 2-col)
shell/app/ocr/panel/stitch.py          # Task 5 — multi-screenshot overlap dedup
shell/app/ocr/panel/convert.py         # Task 6 — panel law conversions
shell/app/ocr/panel/detect.py          # Task 7 — panel-type auto-detect
shell/app/ocr/panel/service.py         # Task 8 — orchestration: tokens→result JSON
shell/app/ocr/panel_router.py          # Task 9 — POST /shell/ocr/panel (gate, caps)
shell/app/ocr/client/panel_parser.mjs  # Task 10 — JS mirror of Tasks 2-6
shell/app/ocr/client/flow_state.mjs    # Task 11 — S1/S2 flow state machine
shell/app/ocr/client/tests/*.test.mjs  # node:test suites
shell/tests/fixtures/panel_ocr/golden_vectors.json   # Task 0 — THE contract
shell/tests/fixtures/panel_ocr/images/               # real PNGs (owner-supplied)
shell/tests/test_ocr_panel_{values,lexicon,rows,stitch,convert,detect,service,router}.py
```

---

### Task 0: Golden vectors fixture (the contract everything tests against)

**Files:** Create `shell/tests/fixtures/panel_ocr/golden_vectors.json`, `shell/tests/test_ocr_panel_fixture.py`

**Interfaces — Produces:** fixture keys used by every later task: `accounts.A|B.{bo_troops,bo_class,scout,battle_left,battle_right,specials_own,specials_enemy,S_scout,S_battle,P_enemy,U}` and `value_grammar_cases`, `label_cases`.

- [ ] **Step 1: Write the failing test**

```python
# shell/tests/test_ocr_panel_fixture.py
import json, pathlib
FIX = pathlib.Path(__file__).parent / "fixtures" / "panel_ocr" / "golden_vectors.json"

def _load():
    return json.loads(FIX.read_text(encoding="utf-8"))

def test_fixture_has_two_accounts_with_full_panels():
    g = _load()
    for acct in ("A", "B"):
        a = g["accounts"][acct]
        for k in ("bo_troops", "bo_class", "scout", "battle_left", "S_scout", "S_battle", "P_enemy", "U"):
            assert k in a, f"{acct} missing {k}"
        assert set(a["bo_class"]) == {"Infantry", "Lancer", "Marksman"}
        for cls in a["scout"]:
            assert set(a["scout"][cls]) == {"Attack", "Defense", "Lethality", "Health"}

def test_law_reproduces_battle_from_scout_both_accounts():
    # THE ground truth: Battle+1 = (Scout+1)*(1+S_battle)/((1+S_scout)*(1+P_enemy))
    g = _load()
    for acct in ("A", "B"):
        a = g["accounts"][acct]
        for cls, stats in a["scout"].items():
            for st, sv in stats.items():
                r = (1 + a["S_battle"][st]) / ((1 + a["S_scout"][st]) * (1 + a["P_enemy"][st]))
                pred = ((1 + sv / 100) * r - 1) * 100
                obs = a["battle_left"][cls][st]
                assert abs(pred - obs) <= 0.11, f"{acct}/{cls}/{st}: {pred} vs {obs}"
```

- [ ] **Step 2: Run to verify it fails** — `py -m pytest shell/tests/test_ocr_panel_fixture.py -q` → FAIL (file missing).

- [ ] **Step 3: Create the fixture with these exact values** (transcribed from owner captures, verified against the law to ≤0.064 pp; stats keyed Attack/Defense/Lethality/Health; S/P sets as fractions):

```json
{
  "accounts": {
    "A": {
      "label": "main [RFJ]Marty 191, Gen-15 trio, pets, experts maxed, defender home-territory",
      "bo_troops": {"Attack": 748.49, "Defense": 775.42, "Lethality": 238.84, "Health": 219.86},
      "bo_class": {
        "Infantry": {"Attack": 658.25, "Defense": 666.25, "Lethality": 1197.36, "Health": 1223.08},
        "Lancer":   {"Attack": 649.25, "Defense": 616.25, "Lethality": 1190.39, "Health": 1154.28},
        "Marksman": {"Attack": 626.25, "Defense": 616.25, "Lethality": 1153.24, "Health": 1146.45}},
      "scout": {
        "Infantry": {"Attack": 4491.6, "Defense": 3979.1, "Lethality": 2794.3, "Health": 3197.4},
        "Lancer":   {"Attack": 4480.4, "Defense": 3924.1, "Lethality": 2786.7, "Health": 3111.4},
        "Marksman": {"Attack": 4451.6, "Defense": 3924.1, "Lethality": 2745.8, "Health": 3101.6}},
      "battle_left": {
        "Infantry": {"Attack": 4859.0, "Defense": 4098.0, "Lethality": 2683.0, "Health": 3040.4},
        "Lancer":   {"Attack": 4846.8, "Defense": 4041.4, "Lethality": 2675.6, "Health": 2958.5},
        "Marksman": {"Attack": 4815.8, "Defense": 4041.4, "Lethality": 2636.3, "Health": 2949.2}},
      "battle_right": {
        "Infantry": {"Attack": 694.3, "Defense": 545.6, "Lethality": 495.7, "Health": 416.4},
        "Lancer":   {"Attack": 740.5, "Defense": 574.7, "Lethality": 533.5, "Health": 442.8},
        "Marksman": {"Attack": 800.6, "Defense": 626.6, "Lethality": 587.1, "Health": 499.0}},
      "specials_own": [
        {"label": "Defender Troops' Attack", "value": 15.0}, {"label": "Defender Troops' Health", "value": 15.0},
        {"label": "Enemy Defense Penalty (Pet Skill)", "value": -10.0},
        {"label": "Enemy Lethality Penalty (Pet Skill)", "value": -5.0},
        {"label": "Enemy Health Penalty (Pet Skill)", "value": -5.0},
        {"label": "Attack Bonus (Pet Skill)", "value": 10.0}, {"label": "Defense Bonus (Pet Skill)", "value": 10.0},
        {"label": "Lethality Bonus (Pet Skill)", "value": 10.0}, {"label": "Health Bonus (Pet Skill)", "value": 10.0},
        {"label": "Territory Defender Attack", "value": 10.0}, {"label": "Territory Defender Defense", "value": 10.0},
        {"label": "Defender Troops Attack When Defending Own City", "value": 5.0},
        {"label": "Defender Troops Defense When Defending Own City", "value": 5.0},
        {"label": "Enemy Lethality Penalty (Expert Skill)", "value": -0.75}],
      "specials_enemy": [
        {"label": "Enemy Defense Penalty (Pet Skill)", "value": -6.0},
        {"label": "Enemy Lethality Penalty (Pet Skill)", "value": -4.0},
        {"label": "Enemy Health Penalty (Pet Skill)", "value": -5.0},
        {"label": "Attack Bonus (Pet Skill)", "value": 8.0}, {"label": "Defense Bonus (Pet Skill)", "value": 6.0},
        {"label": "Lethality Bonus (Pet Skill)", "value": 7.0}, {"label": "Health Bonus (Pet Skill)", "value": 5.0}],
      "S_scout":  {"Attack": 0.25, "Defense": 0.10, "Lethality": 0.10, "Health": 0.25},
      "S_battle": {"Attack": 0.35, "Defense": 0.20, "Lethality": 0.10, "Health": 0.25},
      "P_enemy":  {"Attack": 0.00, "Defense": 0.06, "Lethality": 0.04, "Health": 0.05},
      "U": {"Attack": 2166.55, "Defense": 2166.60, "Lethality": 1095.01, "Health": 1094.98},
      "hero_generation": 15
    },
    "B": {
      "label": "[LnS]MaTiX, Gen-13 trio, NO pets, experts not maxed, defender home-territory, enemy zero specials",
      "bo_troops": {"Attack": 723.50, "Defense": 748.47, "Lethality": 208.86, "Health": 184.37},
      "bo_class": {
        "Infantry": {"Attack": 617.25, "Defense": 620.25, "Lethality": 1104.96, "Health": 1110.03},
        "Lancer":   {"Attack": 617.25, "Defense": 616.25, "Lethality": 1103.60, "Health": 1107.63},
        "Marksman": {"Attack": 666.25, "Defense": 663.25, "Lethality": 1158.52, "Health": 1154.88}},
      "scout": {
        "Infantry": {"Attack": 3668.6, "Defense": 3205.0, "Lethality": 2333.8, "Health": 2676.6},
        "Lancer":   {"Attack": 3668.6, "Defense": 3201.0, "Lethality": 2332.5, "Health": 2673.8},
        "Marksman": {"Attack": 3724.9, "Defense": 3248.0, "Lethality": 2387.4, "Health": 2728.1}},
      "battle_left": {
        "Infantry": {"Attack": 3996.3, "Defense": 3535.5, "Lethality": 2333.8, "Health": 2676.6},
        "Lancer":   {"Attack": 3996.3, "Defense": 3531.1, "Lethality": 2332.5, "Health": 2673.8},
        "Marksman": {"Attack": 4057.6, "Defense": 3582.8, "Lethality": 2387.4, "Health": 2728.1}},
      "battle_right": {
        "Infantry": {"Attack": 862.3, "Defense": 913.6, "Lethality": 623.7, "Health": 610.8},
        "Lancer":   {"Attack": 847.9, "Defense": 886.2, "Lethality": 620.0, "Health": 615.8},
        "Marksman": {"Attack": 886.3, "Defense": 918.6, "Lethality": 656.3, "Health": 649.7}},
      "specials_own": [
        {"label": "Defender Troops' Attack", "value": 15.0}, {"label": "Defender Troops' Health", "value": 15.0},
        {"label": "Territory Defender Attack", "value": 10.0}, {"label": "Territory Defender Defense", "value": 10.0},
        {"label": "Defender Troops Attack When Defending Own City", "value": 5.0},
        {"label": "Defender Troops Defense When Defending Own City", "value": 5.0}],
      "specials_enemy": [],
      "S_scout":  {"Attack": 0.15, "Defense": 0.00, "Lethality": 0.00, "Health": 0.15},
      "S_battle": {"Attack": 0.25, "Defense": 0.10, "Lethality": 0.00, "Health": 0.15},
      "P_enemy":  {"Attack": 0.00, "Defense": 0.00, "Lethality": 0.00, "Health": 0.00},
      "U": {"Attack": 1836.28, "Defense": 1836.28, "Lethality": 1020.01, "Health": 1020.00},
      "hero_generation": 13
    }
  },
  "value_grammar_cases": [
    {"raw": "748.49%", "value": 748.49, "unit": "pct", "signed": false},
    {"raw": "+4491.6%", "value": 4491.6, "unit": "pct", "signed": true},
    {"raw": "-10.0%", "value": -10.0, "unit": "pct", "signed": true},
    {"raw": "+0.00%", "value": 0.0, "unit": "pct", "signed": true},
    {"raw": "1223.08%", "value": 1223.08, "unit": "pct", "signed": false},
    {"raw": "188,900", "value": 188900, "unit": "int", "signed": false},
    {"raw": "1,581", "value": 1581, "unit": "int", "signed": false},
    {"raw": "295.20%", "value": 295.20, "unit": "pct", "signed": false},
    {"raw": "-0.75%", "value": -0.75, "unit": "pct", "signed": true},
    {"raw": "4,491.6%", "value": 4491.6, "unit": "pct", "signed": false},
    {"raw": "garbage", "value": null}, {"raw": "12.", "value": null}, {"raw": "", "value": null},
    {"raw": "+4491.6", "value": 4491.6, "unit": "pct_missing_sign_ok", "signed": true}
  ],
  "label_cases": [
    {"raw": "Troops' Attack", "canonical": "Troops|Attack"},
    {"raw": "Troops’ Attack", "canonical": "Troops|Attack"},
    {"raw": "Troops\" Attack", "canonical": "Troops|Attack"},
    {"raw": "Infantry Attack", "canonical": "Infantry|Attack"},
    {"raw": "lnfantry Attack", "canonical": "Infantry|Attack"},
    {"raw": "Marksman Lethality", "canonical": "Marksman|Lethality"},
    {"raw": "Enemy Defense Penalty (Pet Skill)", "canonical": "special:Enemy Defense Penalty (Pet Skill)"},
    {"raw": "Defender Troops Attack When Defending Own City", "canonical": "special:Defender Troops Attack When Defending Own City"},
    {"raw": "Deployment Capacity", "canonical": "meta:Deployment Capacity"},
    {"raw": "March Speed Up", "canonical": "meta:March Speed Up"},
    {"raw": "Bonus Overview", "canonical": "header:Bonus Overview"},
    {"raw": "Stat Bonuses", "canonical": "header:Stat Bonuses"},
    {"raw": "Utterly Unknown Row", "canonical": null}
  ]
}
```

- [ ] **Step 4: Run to verify both tests pass** — `py -m pytest shell/tests/test_ocr_panel_fixture.py -q` → 2 passed. (If the law test fails, a number was mistyped — fix the fixture, never the tolerance.)
- [ ] **Step 5: Commit** — `git add shell/tests/... && git commit -m "ocr: golden vectors fixture (two verified accounts + grammar/label cases)"`

---

### Task 1: Token normal form

**Files:** Create `shell/app/ocr/panel/__init__.py` (empty), `shell/app/ocr/panel/tokens.py`, `shell/tests/test_ocr_panel_tokens.py`

**Interfaces — Produces:** `OcrToken(text, x0, y0, x1, y1, conf, color=None)` frozen dataclass, coords normalized 0..1; `tokens_from_json(list[dict]) -> list[OcrToken]` (rejects out-of-range coords, conf outside [0,1]).

- [ ] **Step 1: Failing test**

```python
# shell/tests/test_ocr_panel_tokens.py
import pytest
from shell.app.ocr.panel.tokens import OcrToken, tokens_from_json

def test_token_roundtrip_and_validation():
    ts = tokens_from_json([{"text": "Infantry Attack", "x0": 0.05, "y0": 0.10, "x1": 0.40, "y1": 0.13, "conf": 0.98}])
    assert ts[0].text == "Infantry Attack" and ts[0].color is None

def test_token_rejects_bad_coords_and_conf():
    with pytest.raises(ValueError):
        tokens_from_json([{"text": "x", "x0": -0.1, "y0": 0, "x1": 0.5, "y1": 0.1, "conf": 0.9}])
    with pytest.raises(ValueError):
        tokens_from_json([{"text": "x", "x0": 0.1, "y0": 0, "x1": 0.5, "y1": 0.1, "conf": 1.7}])
```

- [ ] **Step 2: Run — FAIL** (module missing).
- [ ] **Step 3: Implement**

```python
# shell/app/ocr/panel/tokens.py
from dataclasses import dataclass

@dataclass(frozen=True)
class OcrToken:
    text: str
    x0: float; y0: float; x1: float; y1: float
    conf: float
    color: str | None = None  # 'green' | 'red' | None

def tokens_from_json(items):
    out = []
    for it in items:
        t = OcrToken(str(it["text"]), float(it["x0"]), float(it["y0"]),
                     float(it["x1"]), float(it["y1"]), float(it["conf"]), it.get("color"))
        for v in (t.x0, t.y0, t.x1, t.y1):
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"coord out of range: {v}")
        if not 0.0 <= t.conf <= 1.0:
            raise ValueError(f"conf out of range: {t.conf}")
        if t.x1 <= t.x0 or t.y1 <= t.y0:
            raise ValueError("degenerate box")
        if t.color not in (None, "green", "red"):
            raise ValueError(f"bad color: {t.color}")
        out.append(t)
    return out
```

- [ ] **Step 4: Run — PASS.**  **Step 5: Commit** `ocr: token normal form`.

---

### Task 2: Value grammar

**Files:** Create `shell/app/ocr/panel/values.py`, `shell/tests/test_ocr_panel_values.py`

**Interfaces — Produces:** `parse_value(raw: str) -> ParsedValue | None` where `ParsedValue = namedtuple("ParsedValue", "value unit signed")`, unit ∈ {"pct","int"}; returns None for anything malformed (never guesses). A trailing-%-missing but otherwise well-formed signed number parses as pct (in-game values are always %); flag preserved via `signed`.

- [ ] **Step 1: Failing test** (drives from fixture)

```python
# shell/tests/test_ocr_panel_values.py
import json, pathlib
from shell.app.ocr.panel.values import parse_value
FIX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "panel_ocr" / "golden_vectors.json").read_text(encoding="utf-8"))

def test_value_grammar_all_fixture_cases():
    for case in FIX["value_grammar_cases"]:
        got = parse_value(case["raw"])
        if case["value"] is None:
            assert got is None, f"{case['raw']!r} must not parse"
        else:
            assert got is not None and abs(got.value - case["value"]) < 1e-9, f"{case['raw']!r}"

def test_no_locale_ambiguity_rejected():
    assert parse_value("1.234,5%") is None   # EU decimal style: reject in v1, don't guess
    assert parse_value("12 345") is None
```

- [ ] **Step 2: FAIL.**  **Step 3: Implement**

```python
# shell/app/ocr/panel/values.py
import re
from collections import namedtuple
ParsedValue = namedtuple("ParsedValue", "value unit signed")
_PCT = re.compile(r"^([+-]?)(\d{1,3}(?:,\d{3})*|\d+)(\.\d+)?%$")
_PCT_NOSYM = re.compile(r"^([+-])(\d{1,3}(?:,\d{3})*|\d+)(\.\d+)?$")  # signed ⇒ clearly a bonus value
_INT = re.compile(r"^(\d{1,3}(?:,\d{3})*|\d+)$")

def parse_value(raw):
    raw = (raw or "").strip()
    m = _PCT.match(raw)
    if m:
        v = float((m.group(2)).replace(",", "") + (m.group(3) or ""))
        return ParsedValue(-v if m.group(1) == "-" else v, "pct", m.group(1) != "")
    m = _PCT_NOSYM.match(raw)
    if m:
        v = float((m.group(2)).replace(",", "") + (m.group(3) or ""))
        return ParsedValue(-v if m.group(1) == "-" else v, "pct", True)
    m = _INT.match(raw)
    if m:
        return ParsedValue(float(m.group(1).replace(",", "")), "int", False)
    return None
```

- [ ] **Step 4: PASS.**  **Step 5: Commit** `ocr: value grammar (strict, never-guess)`.

---

### Task 3: Label lexicon + fuzzy matcher

**Files:** Create `shell/app/ocr/panel/lexicon.py`, `shell/tests/test_ocr_panel_lexicon.py`

**Interfaces — Produces:** `match_label(raw: str) -> str | None` returning canonical ids exactly as in the fixture's `label_cases` (`"Infantry|Attack"`, `"Troops|Attack"`, `"special:<exact label>"`, `"meta:<name>"`, `"header:<name>"`); `CLASSES = ("Infantry","Lancer","Marksman")`, `STATS = ("Attack","Defense","Lethality","Health")`. Fuzzy tolerance: case-insensitive, apostrophe variants (`' ’ "`), l/I/1 and O/0 confusions in LETTERS ONLY, ≤2 edit distance on the letters-only skeleton; below that → None (never guess).

- [ ] **Step 1: Failing test**

```python
# shell/tests/test_ocr_panel_lexicon.py
import json, pathlib
from shell.app.ocr.panel.lexicon import match_label
FIX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "panel_ocr" / "golden_vectors.json").read_text(encoding="utf-8"))

def test_label_cases_from_fixture():
    for case in FIX["label_cases"]:
        assert match_label(case["raw"]) == case["canonical"], case["raw"]

def test_all_24_class_stat_labels_and_specials_resolve():
    for cls in ("Infantry", "Lancer", "Marksman"):
        for st in ("Attack", "Defense", "Lethality", "Health"):
            assert match_label(f"{cls} {st}") == f"{cls}|{st}"
    for sp in ("Attack Bonus (Pet Skill)", "Territory Defender Defense", "Enemy Lethality Penalty (Expert Skill)"):
        assert match_label(sp) == f"special:{sp}"

def test_numbers_never_match_labels():
    assert match_label("4491.6%") is None
```

- [ ] **Step 2: FAIL.**  **Step 3: Implement**

```python
# shell/app/ocr/panel/lexicon.py
import re
CLASSES = ("Infantry", "Lancer", "Marksman")
STATS = ("Attack", "Defense", "Lethality", "Health")
_SPECIALS = (
    "Defender Troops' Attack", "Defender Troops' Health",
    "Enemy Defense Penalty (Pet Skill)", "Enemy Lethality Penalty (Pet Skill)", "Enemy Health Penalty (Pet Skill)",
    "Attack Bonus (Pet Skill)", "Defense Bonus (Pet Skill)", "Lethality Bonus (Pet Skill)", "Health Bonus (Pet Skill)",
    "Territory Defender Attack", "Territory Defender Defense",
    "Defender Troops Attack When Defending Own City", "Defender Troops Defense When Defending Own City",
    "Enemy Lethality Penalty (Expert Skill)", "Enemy Attack Penalty (Pet Skill)",
    "Attack Bonus", "Defense Bonus", "Lethality Bonus", "Health Bonus",
    "Enemy Attack Reduction", "Enemy Defense Reduction",
)
_META = ("Deployment Capacity", "March Queue", "March Speed Up", "Training Capacity", "Training Speed", "Healing Speed")
_HEADERS = ("Bonus Overview", "Stat Bonuses", "Military", "Troops Total", "Lootable")

def _skeleton(s):
    s = s.lower().replace("’", "'").replace('"', "'")
    s = s.replace("0", "o").replace("1", "l")
    return re.sub(r"[^a-z]", "", s)

def _dist(a, b):
    if abs(len(a) - len(b)) > 2:
        return 3
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
        if min(prev) > 2:
            return 3
    return prev[-1]

_CANON = {}
for _c in CLASSES:
    for _s in STATS:
        _CANON[_skeleton(f"{_c} {_s}")] = f"{_c}|{_s}"
for _s in STATS:
    _CANON[_skeleton(f"Troops' {_s}")] = f"Troops|{_s}"
for _sp in _SPECIALS:
    _CANON[_skeleton(_sp)] = f"special:{_sp}"
for _m in _META:
    _CANON[_skeleton(_m)] = f"meta:{_m}"
for _h in _HEADERS:
    _CANON[_skeleton(_h)] = f"header:{_h}"

def match_label(raw):
    sk = _skeleton(raw or "")
    if len(sk) < 4:
        return None
    if sk in _CANON:
        return _CANON[sk]
    best, bestd = None, 3
    for k, v in _CANON.items():
        d = _dist(sk, k)
        if d < bestd:
            best, bestd = v, d
    return best if bestd <= 2 else None
```

- [ ] **Step 4: PASS.**  **Step 5: Commit** `ocr: label lexicon + bounded fuzzy match`.

---

### Task 4: Row assembly — single-column and two-column battle panels

**Files:** Create `shell/app/ocr/panel/rows.py`, `shell/tests/test_ocr_panel_rows.py`

**Interfaces — Consumes:** `OcrToken`, `parse_value`, `match_label`. **Produces:**
`PanelRow = namedtuple("PanelRow", "canonical side value unit conf raw_label flags")` with side ∈ {None,"left","right"} and flags a tuple of strings (e.g. `("low_conf",)`);
`assemble_rows(tokens, two_column: bool) -> list[PanelRow]`. Pairing rule: tokens whose vertical centers differ ≤ 0.6× median row height belong to one row; in a row, label = concatenated non-value tokens (x-order), values = value-parsable tokens. Two-column: value left of the label's x-center → side "left", right → side "right"; `color` (green→left, red→right) overrides geometry when present and disagrees ⇒ add flag `"col_conflict"` and TRUST COLOR. Value conf < 0.90 ⇒ flag `"low_conf"`. A label with no value ⇒ row with value=None + flag `"missing_value"` (never fabricated).

- [ ] **Step 1: Failing tests**

```python
# shell/tests/test_ocr_panel_rows.py
from shell.app.ocr.panel.tokens import tokens_from_json
from shell.app.ocr.panel.rows import assemble_rows

def _tok(text, x0, y0, w=0.2, h=0.03, conf=0.98, color=None):
    return {"text": text, "x0": x0, "y0": y0, "x1": x0 + w, "y1": y0 + h, "conf": conf, "color": color}

def test_single_column_rows_pair_label_and_value():
    toks = tokens_from_json([
        _tok("Troops' Attack", 0.05, 0.10), _tok("748.49%", 0.70, 0.101),
        _tok("Infantry Attack", 0.05, 0.16), _tok("658.25%", 0.70, 0.161),
    ])
    rows = assemble_rows(toks, two_column=False)
    got = {r.canonical: r.value for r in rows}
    assert got == {"Troops|Attack": 748.49, "Infantry|Attack": 658.25}
    assert all(r.side is None for r in rows)

def test_two_column_battle_row_sides_by_geometry_and_color():
    toks = tokens_from_json([
        _tok("+4859.0%", 0.03, 0.20, color="green"), _tok("Infantry Attack", 0.38, 0.201),
        _tok("+694.3%", 0.78, 0.202, color="red"),
    ])
    rows = assemble_rows(toks, two_column=True)
    sides = {(r.canonical, r.side): r.value for r in rows}
    assert sides[("Infantry|Attack", "left")] == 4859.0
    assert sides[("Infantry|Attack", "right")] == 694.3

def test_color_beats_geometry_with_conflict_flag():
    toks = tokens_from_json([
        _tok("Infantry Attack", 0.38, 0.20),
        _tok("+694.3%", 0.05, 0.201, color="red"),  # red but geometrically left
    ])
    rows = assemble_rows(toks, two_column=True)
    (r,) = rows
    assert r.side == "right" and "col_conflict" in r.flags

def test_low_conf_and_missing_value_flags():
    toks = tokens_from_json([
        _tok("Infantry Health", 0.05, 0.30), _tok("3197.4%", 0.70, 0.301, conf=0.55),
        _tok("Lancer Health", 0.05, 0.36),
    ])
    rows = {r.canonical: r for r in assemble_rows(toks, two_column=False)}
    assert "low_conf" in rows["Infantry|Health"].flags
    assert rows["Lancer|Health"].value is None and "missing_value" in rows["Lancer|Health"].flags
```

- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement**

```python
# shell/app/ocr/panel/rows.py
from collections import namedtuple
from statistics import median
from .values import parse_value
from .lexicon import match_label

PanelRow = namedtuple("PanelRow", "canonical side value unit conf raw_label flags")
LOW_CONF = 0.90

def _group_rows(tokens):
    toks = sorted(tokens, key=lambda t: ((t.y0 + t.y1) / 2, t.x0))
    if not toks:
        return []
    h = median(t.y1 - t.y0 for t in toks)
    groups, cur, cur_y = [], [toks[0]], (toks[0].y0 + toks[0].y1) / 2
    for t in toks[1:]:
        cy = (t.y0 + t.y1) / 2
        if abs(cy - cur_y) <= 0.6 * h:
            cur.append(t)
            cur_y = min(cur_y, cy)
        else:
            groups.append(cur)
            cur, cur_y = [t], cy
    groups.append(cur)
    return groups

def assemble_rows(tokens, two_column):
    out = []
    for group in _group_rows(tokens):
        labels = [t for t in group if parse_value(t.text) is None]
        values = [t for t in group if parse_value(t.text) is not None]
        raw_label = " ".join(t.text for t in sorted(labels, key=lambda t: t.x0)).strip()
        canonical = match_label(raw_label)
        if canonical is None:
            continue
        if not values:
            out.append(PanelRow(canonical, None, None, None, 0.0, raw_label, ("missing_value",)))
            continue
        lx = (min(t.x0 for t in labels) + max(t.x1 for t in labels)) / 2 if labels else 0.5
        for vt in values:
            pv = parse_value(vt.text)
            flags = []
            side = None
            if two_column:
                geo = "left" if (vt.x0 + vt.x1) / 2 < lx else "right"
                col = {"green": "left", "red": "right"}.get(vt.color)
                side = col or geo
                if col and col != geo:
                    flags.append("col_conflict")
            if vt.conf < LOW_CONF:
                flags.append("low_conf")
            out.append(PanelRow(canonical, side, pv.value, pv.unit, vt.conf, raw_label, tuple(flags)))
    return out
```

- [ ] **Step 4: PASS.**  **Step 5: Commit** `ocr: row assembly (1-col + 2-col, color-over-geometry)`.

---

### Task 5: Multi-screenshot overlap stitch

**Files:** Create `shell/app/ocr/panel/stitch.py`, `shell/tests/test_ocr_panel_stitch.py`

**Interfaces — Consumes:** `PanelRow`. **Produces:** `stitch(rows_per_shot: list[list[PanelRow]]) -> tuple[list[PanelRow], list[str]]` returning (merged rows, warnings). Rules: rows keyed (canonical, side); duplicates with EQUAL values collapse to the higher-conf copy; duplicates with UNEQUAL values keep NEITHER — emit row with value None + flag `"conflict"` + warning (never guess); order = first-seen.

- [ ] **Step 1: Failing test**

```python
# shell/tests/test_ocr_panel_stitch.py
from shell.app.ocr.panel.rows import PanelRow
from shell.app.ocr.panel.stitch import stitch

def _r(c, v, conf=0.98, side=None, flags=()):
    return PanelRow(c, side, v, "pct", conf, c, tuple(flags))

def test_overlap_dedup_keeps_higher_conf():
    a = [_r("Infantry|Attack", 4491.6, 0.95), _r("Infantry|Defense", 3979.1, 0.97)]
    b = [_r("Infantry|Defense", 3979.1, 0.99), _r("Infantry|Lethality", 2794.3, 0.98)]
    merged, warns = stitch([a, b])
    got = {r.canonical: (r.value, r.conf) for r in merged}
    assert got["Infantry|Defense"] == (3979.1, 0.99) and len(merged) == 3 and warns == []

def test_conflicting_duplicate_never_guesses():
    merged, warns = stitch([[_r("Infantry|Attack", 4491.6)], [_r("Infantry|Attack", 4431.6)]])
    (r,) = merged
    assert r.value is None and "conflict" in r.flags and len(warns) == 1
```

- [ ] **Step 2: FAIL.**  **Step 3: Implement**

```python
# shell/app/ocr/panel/stitch.py
from .rows import PanelRow

def stitch(rows_per_shot):
    order, best, warns = [], {}, []
    for rows in rows_per_shot:
        for r in rows:
            k = (r.canonical, r.side)
            if k not in best:
                best[k] = r
                order.append(k)
            else:
                cur = best[k]
                if cur.value is not None and r.value is not None and cur.value != r.value:
                    warns.append(f"conflict on {k}: {cur.value} vs {r.value}")
                    best[k] = PanelRow(r.canonical, r.side, None, None, 0.0, r.raw_label,
                                       tuple(set(cur.flags) | set(r.flags) | {"conflict"}))
                elif r.value is not None and (cur.value is None or r.conf > cur.conf):
                    best[k] = r
    return [best[k] for k in order], warns
```

- [ ] **Step 4: PASS.**  **Step 5: Commit** `ocr: overlap stitch (conflicts surface, never guessed)`.

---

### Task 6: Panel-law converter (the crown jewel — tested on both real accounts)

**Files:** Create `shell/app/ocr/panel/convert.py`, `shell/tests/test_ocr_panel_convert.py`

**Interfaces — Consumes:** special-row dicts `{label, value}` (percent points). **Produces** (all stats keyed "Attack","Defense","Lethality","Health"; class keys "Infantry","Lancer","Marksman"; percent points in/out):
- `fold_sets(specials_own: list, specials_enemy: list) -> (S_scout, S_battle, P_enemy)` — fractions per stat. Law: S_scout = pet self-buffs + `Defender Troops'` widget rows (+ any `... Bonus` item rows); S_battle = S_scout + `Territory Defender` rows; `When Defending Own City` rows are EXCLUDED from both; P_enemy = |enemy penalty rows| ÷100 (their `Enemy X Penalty ...` entries).
- `battle_to_scoutnet(battle_rows: dict, S_scout, S_battle, P_enemy) -> dict` — per class/stat: `scout = ((1+b/100)·(1+S_scout)·(1+P_enemy)/(1+S_battle) − 1)·100`.
- `calibrate_U(bo_troops, bo_class, scout_rows, S_scout) -> dict` — per stat, mean over classes of `((1+s/100)/(1+S_scout) − 1)·100 − bo_troops − bo_class`; raises `CalibrationError` if class spread > 1.0.
- `citystats_to_scoutnet(bo_troops, bo_class, U, S_scout) -> dict`.

- [ ] **Step 1: Failing tests** (golden vectors do the work)

```python
# shell/tests/test_ocr_panel_convert.py
import json, pathlib, pytest
from shell.app.ocr.panel.convert import fold_sets, battle_to_scoutnet, calibrate_U, citystats_to_scoutnet, CalibrationError
FIX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "panel_ocr" / "golden_vectors.json").read_text(encoding="utf-8"))
STATS = ("Attack", "Defense", "Lethality", "Health")

@pytest.mark.parametrize("acct", ["A", "B"])
def test_fold_sets_reproduce_documented_sets(acct):
    a = FIX["accounts"][acct]
    S_scout, S_battle, P_enemy = fold_sets(a["specials_own"], a["specials_enemy"])
    for st in STATS:
        assert abs(S_scout[st] - a["S_scout"][st]) < 1e-9, (acct, st)
        assert abs(S_battle[st] - a["S_battle"][st]) < 1e-9, (acct, st)
        assert abs(P_enemy[st] - a["P_enemy"][st]) < 1e-9, (acct, st)

@pytest.mark.parametrize("acct", ["A", "B"])
def test_battle_to_scoutnet_recovers_scout_panel(acct):
    a = FIX["accounts"][acct]
    S_scout, S_battle, P_enemy = fold_sets(a["specials_own"], a["specials_enemy"])
    got = battle_to_scoutnet(a["battle_left"], S_scout, S_battle, P_enemy)
    for cls, stats in a["scout"].items():
        for st, v in stats.items():
            assert abs(got[cls][st] - v) <= 0.11, (acct, cls, st, got[cls][st], v)

@pytest.mark.parametrize("acct", ["A", "B"])
def test_calibrate_U_matches_documented_block(acct):
    a = FIX["accounts"][acct]
    U = calibrate_U(a["bo_troops"], a["bo_class"], a["scout"], a["S_scout"])
    for st in STATS:
        assert abs(U[st] - a["U"][st]) <= 0.10, (acct, st)

@pytest.mark.parametrize("acct", ["A", "B"])
def test_citystats_roundtrip_reproduces_scout(acct):
    a = FIX["accounts"][acct]
    U = calibrate_U(a["bo_troops"], a["bo_class"], a["scout"], a["S_scout"])
    got = citystats_to_scoutnet(a["bo_troops"], a["bo_class"], U, a["S_scout"])
    for cls, stats in a["scout"].items():
        for st, v in stats.items():
            assert abs(got[cls][st] - v) <= 0.11, (acct, cls, st)

def test_calibration_error_on_inconsistent_panels():
    a = FIX["accounts"]["A"]
    bad_scout = {c: dict(s) for c, s in a["scout"].items()}
    bad_scout["Infantry"]["Attack"] += 50.0
    with pytest.raises(CalibrationError):
        calibrate_U(a["bo_troops"], a["bo_class"], bad_scout, a["S_scout"])
```

- [ ] **Step 2: FAIL.**  **Step 3: Implement**

```python
# shell/app/ocr/panel/convert.py
STATS = ("Attack", "Defense", "Lethality", "Health")

class CalibrationError(ValueError):
    pass

def _stat_of(label):
    for st in STATS:
        if st in label:
            return st
    return None

def fold_sets(specials_own, specials_enemy):
    S_scout = {st: 0.0 for st in STATS}
    territory = {st: 0.0 for st in STATS}
    for sp in specials_own:
        label, v, st = sp["label"], sp["value"] / 100.0, _stat_of(sp["label"])
        if st is None or v < 0:
            continue                      # own outgoing penalties don't touch own rows
        if "When Defending Own City" in label:
            continue                      # displayed but never folded (measured, both accounts)
        if "Territory Defender" in label:
            territory[st] += v
        else:                             # pet self-buffs, defender-widget rows, item bonuses
            S_scout[st] += v
    S_battle = {st: S_scout[st] + territory[st] for st in STATS}
    P_enemy = {st: 0.0 for st in STATS}
    for sp in specials_enemy:
        st = _stat_of(sp["label"])
        if st is not None and sp["value"] < 0 and "Penalty" in sp["label"]:
            P_enemy[st] += abs(sp["value"]) / 100.0
    return S_scout, S_battle, P_enemy

def battle_to_scoutnet(battle_rows, S_scout, S_battle, P_enemy):
    out = {}
    for cls, stats in battle_rows.items():
        out[cls] = {}
        for st, b in stats.items():
            r = (1 + S_scout[st]) * (1 + P_enemy[st]) / (1 + S_battle[st])
            out[cls][st] = ((1 + b / 100.0) * r - 1) * 100.0
    return out

def calibrate_U(bo_troops, bo_class, scout_rows, S_scout):
    U = {}
    for st in STATS:
        us = []
        for cls, stats in scout_rows.items():
            std = ((1 + stats[st] / 100.0) / (1 + S_scout[st]) - 1) * 100.0
            us.append(std - bo_troops[st] - bo_class[cls][st])
        if max(us) - min(us) > 1.0:
            raise CalibrationError(f"U not uniform for {st}: spread {max(us)-min(us):.2f}")
        U[st] = sum(us) / len(us)
    return U

def citystats_to_scoutnet(bo_troops, bo_class, U, S_scout):
    out = {}
    for cls, stats in bo_class.items():
        out[cls] = {}
        for st in STATS:
            std = bo_troops[st] + stats[st] + U[st]
            out[cls][st] = ((1 + std / 100.0) * (1 + S_scout[st]) - 1) * 100.0
    return out
```

- [ ] **Step 4: PASS** (all 9 tests, both accounts).  **Step 5: Commit** `ocr: panel-law converter, golden-verified on two accounts`.

---

### Task 7: Panel-type auto-detect

**Files:** Create `shell/app/ocr/panel/detect.py`, `shell/tests/test_ocr_panel_detect.py`

**Interfaces — Consumes:** `list[PanelRow]` (from a `two_column=True` assembly pass — single-column panels simply produce side=None rows). **Produces:** `detect_panel_type(rows) -> str` ∈ {"battle","scout","citystats","unknown"}. Rules in order: any `Troops|X` canonical ⇒ "citystats"; ≥4 class-stat rows with BOTH left and right sides ⇒ "battle"; ≥4 class-stat rows single-sided with signed pct ⇒ "scout"; else "unknown".

- [ ] **Step 1: Failing test**

```python
# shell/tests/test_ocr_panel_detect.py
from shell.app.ocr.panel.rows import PanelRow
from shell.app.ocr.panel.detect import detect_panel_type

def _r(c, side=None, v=100.0):
    return PanelRow(c, side, v, "pct", 0.99, c, ())

def test_detects_citystats_by_troops_rows():
    assert detect_panel_type([_r("Troops|Attack"), _r("Infantry|Attack")]) == "citystats"

def test_detects_battle_by_two_sides():
    rows = [_r("Infantry|Attack", "left"), _r("Infantry|Attack", "right"),
            _r("Infantry|Defense", "left"), _r("Infantry|Defense", "right"),
            _r("Lancer|Attack", "left"), _r("Lancer|Attack", "right"),
            _r("Lancer|Defense", "left"), _r("Lancer|Defense", "right")]
    assert detect_panel_type(rows) == "battle"

def test_detects_scout_single_sided():
    rows = [_r(f"{c}|{s}") for c in ("Infantry", "Lancer") for s in ("Attack", "Defense", "Lethality")]
    assert detect_panel_type(rows) == "scout"

def test_unknown_for_garbage():
    assert detect_panel_type([]) == "unknown"
```

- [ ] **Step 2: FAIL.**  **Step 3: Implement**

```python
# shell/app/ocr/panel/detect.py
def detect_panel_type(rows):
    class_rows = [r for r in rows if "|" in r.canonical and not r.canonical.startswith(("special:", "meta:", "header:"))]
    if any(r.canonical.startswith("Troops|") for r in rows):
        return "citystats"
    sided = [r for r in class_rows if r.side in ("left", "right")]
    if len({(r.canonical) for r in sided if r.side == "left"} & {(r.canonical) for r in sided if r.side == "right"}) >= 4:
        return "battle"
    if len(class_rows) >= 4:
        return "scout"
    return "unknown"
```

- [ ] **Step 4: PASS.**  **Step 5: Commit** `ocr: panel-type auto-detect`.

---

### Task 8: Service orchestration (tokens → result JSON, deterministic, never-fabricate)

**Files:** Create `shell/app/ocr/panel/service.py`, `shell/tests/test_ocr_panel_service.py`

**Interfaces — Consumes:** everything above. **Produces:** `extract_panel(token_shots: list[list[dict]], side_hint: str|None, panel_hint: str|None) -> dict`:

```json
{"status": "ok|partial|failed", "panel_type": "...", "stats": {"<Class>|<Stat>": float, ...},
 "specials": [{"label": ..., "value": ...}], "unreadable_fields": ["stats.Lancer|Health", ...],
 "warnings": [...], "field_conf": {"<Class>|<Stat>": 0.97, ...}}
```

`stats` keys use the app grammar `Class|Stat` (matches prototype `readInputPanelPct` and shell extract.py). Rows with value None / flags conflict/low_conf(<0.90) go to `unreadable_fields`, NEVER into `stats`. Battle panels return BOTH sides: `stats_left`/`stats_right` instead of `stats`. status: ok = all 12 class-stats present per relevant side; partial = ≥1 present; failed = none. **Determinism test is mandatory.**

- [ ] **Step 1: Failing tests**

```python
# shell/tests/test_ocr_panel_service.py
import json
from shell.app.ocr.panel.service import extract_panel

def _shot_scout():
    toks, y = [], 0.10
    for cls in ("Infantry", "Lancer", "Marksman"):
        for st, v in (("Attack", "+4491.6%"), ("Defense", "+3979.1%"), ("Lethality", "+2794.3%"), ("Health", "+3197.4%")):
            toks.append({"text": f"{cls} {st}", "x0": 0.05, "y0": y, "x1": 0.4, "y1": y + 0.03, "conf": 0.99})
            toks.append({"text": v, "x0": 0.7, "y0": y, "x1": 0.95, "y1": y + 0.03, "conf": 0.97})
            y += 0.05
    return toks

def test_scout_extraction_ok_and_deterministic():
    r1 = extract_panel([_shot_scout()], side_hint="enemy", panel_hint=None)
    r2 = extract_panel([_shot_scout()], side_hint="enemy", panel_hint=None)
    assert r1["status"] == "ok" and r1["panel_type"] == "scout"
    assert r1["stats"]["Infantry|Attack"] == 4491.6 and len(r1["stats"]) == 12
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)

def test_low_conf_field_is_unreadable_not_guessed():
    shot = _shot_scout()
    shot[1]["conf"] = 0.55   # Infantry Attack value token
    r = extract_panel([shot], side_hint="enemy", panel_hint=None)
    assert r["status"] == "partial"
    assert "Infantry|Attack" not in r["stats"]
    assert "stats.Infantry|Attack" in r["unreadable_fields"]

def test_empty_input_fails_cleanly():
    r = extract_panel([[]], side_hint=None, panel_hint=None)
    assert r["status"] == "failed" and r["stats"] == {}
```

- [ ] **Step 2: FAIL.**  **Step 3: Implement**

```python
# shell/app/ocr/panel/service.py
from .tokens import tokens_from_json
from .rows import assemble_rows, LOW_CONF
from .stitch import stitch
from .detect import detect_panel_type
from .lexicon import CLASSES, STATS

def _bucket(rows, side):
    stats, conf, unreadable = {}, {}, []
    for r in rows:
        if r.canonical.startswith(("special:", "meta:", "header:")) or "|" not in r.canonical:
            continue
        if r.canonical.startswith("Troops|"):
            key = r.canonical
        else:
            key = r.canonical
        if side is not None and r.side != side:
            continue
        bad = r.value is None or "conflict" in r.flags or r.conf < LOW_CONF
        if bad:
            unreadable.append(f"stats.{key}")
        else:
            stats[key] = r.value
            conf[key] = round(r.conf, 4)
    return stats, conf, unreadable

def extract_panel(token_shots, side_hint=None, panel_hint=None):
    shots = [assemble_rows(tokens_from_json(s), two_column=True) for s in token_shots]
    rows, warnings = stitch(shots)
    ptype = panel_hint or detect_panel_type(rows)
    specials = [{"label": r.canonical.split(":", 1)[1], "value": r.value}
                for r in rows if r.canonical.startswith("special:") and r.value is not None]
    out = {"panel_type": ptype, "specials": specials, "warnings": list(warnings)}
    expected = {f"{c}|{s}" for c in CLASSES for s in STATS}
    if ptype == "battle":
        for side, key in (("left", "stats_left"), ("right", "stats_right")):
            st, cf, un = _bucket(rows, side)
            out[key], out[key + "_conf"] = st, cf
            out.setdefault("unreadable_fields", []).extend(f"{key}.{u.split('.',1)[1]}" for u in un)
        present = len(out["stats_left"]) + len(out["stats_right"])
        total = 24
    else:
        st, cf, un = _bucket(rows, None)
        out["stats"], out["field_conf"] = st, cf
        out["unreadable_fields"] = un
        present = len([k for k in st if k.split("|")[0] in CLASSES])
        total = 12
    missing = expected - set((out.get("stats") or {}) | (out.get("stats_left") or {}))
    out.setdefault("unreadable_fields", [])
    out["status"] = "ok" if present >= total else ("partial" if present > 0 else "failed")
    out.setdefault("stats", out.get("stats", {}))
    return out
```

(Note to implementer: the exact `status` arithmetic above is intentionally simple — refine ONLY to make the three tests pass without weakening never-fabricate.)

- [ ] **Step 4: PASS.**  **Step 5: Commit** `ocr: extraction service (deterministic, never-fabricate)`.

---

### Task 9: Endpoint `/shell/ocr/panel` — entitlement gate, caps, never-persist

**Files:** Create `shell/app/ocr/panel_router.py`; Modify `shell/app/main.py` (include router, same pattern as the existing `shell/app/ocr/router.py`); Test `shell/tests/test_ocr_panel_router.py`

**Interfaces — Consumes:** `extract_panel`; shell auth dependency (same used by `/shell/ocr`) exposing `user.plan`. **Produces:** `POST /shell/ocr/panel` multipart: `file` (image, may repeat ≤3), `side` ∈ {you,enemy}, `panel` optional ∈ {battle,scout,citystats}. Responses: 403 `{"error":"ocr_not_available_on_free"}` for plan=="free"; 413 over `MAX_BODY_BYTES`; 415 non-image (magic-byte sniff, not filename); 200 → Task-8 JSON. `OCR_PANEL_MOCK=1` (default in tests) short-circuits the engine with fixture tokens — the real RapidOCR engine is a later task; this endpoint must be green with the mock.

- [ ] **Step 1: Failing tests**

```python
# shell/tests/test_ocr_panel_router.py  (follow the client/auth fixture pattern of shell/tests/test_ocr_router.py)
def test_free_tier_gets_403(client_free):
    r = client_free.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 403 and r.json()["error"] == "ocr_not_available_on_free"

def test_oversize_body_413(client_paid):
    blob = b"\x89PNG\r\n\x1a\n" + b"0" * (MAX_BODY_BYTES + 1)
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", blob, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 413

def test_non_image_sniffed_415(client_paid):
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", b"MZ\x90\x00notpng", "image/png")}, data={"side": "enemy"})
    assert r.status_code == 415

def test_mock_extraction_roundtrip_and_no_files_left(tmp_path, client_paid, monkeypatch):
    monkeypatch.setenv("OCR_PANEL_MOCK", "1")
    r = client_paid.post("/shell/ocr/panel", files={"file": ("a.png", PNG_BYTES, "image/png")}, data={"side": "enemy"})
    assert r.status_code == 200 and r.json()["status"] in ("ok", "partial")
    assert list(tmp_path.iterdir()) == []   # nothing persisted anywhere under the app tmp dir
```

- [ ] **Step 2: FAIL.**  **Step 3: Implement** the router mirroring `shell/app/ocr/router.py`'s dependency/validation structure: plan gate first (`resolve_plan` — wired by shell fix item F3), size check on the spooled upload before reading fully, magic-byte sniff (`png/jpeg/webp`), process **in memory only** (no disk writes; assert by construction — no `open()` for write anywhere in the module), call `extract_panel` (mock tokens under `OCR_PANEL_MOCK`), return JSON.
- [ ] **Step 4: PASS.**  **Step 5: Commit** `ocr: /shell/ocr/panel endpoint (gate, caps, sniff, in-memory)`.

---

### Task 10: JS mirror parser + shared golden vectors (client path)

**Files:** Create `shell/app/ocr/client/panel_parser.mjs`, `shell/app/ocr/client/tests/panel_parser.test.mjs`

**Interfaces — Produces (ES module, no dependencies):** `parseValue(raw)`, `matchLabel(raw)`, `assembleRows(tokens, twoColumn)`, `stitch(rowsPerShot)`, `foldSets(specialsOwn, specialsEnemy)`, `battleToScoutnet(rows, sScout, sBattle, pEnemy)`, `calibrateU(...)`, `cityStatsToScoutnet(...)`, `extractPanel(tokenShots, sideHint, panelHint)` — SAME signatures/semantics as Python Tasks 2–8, same JSON shapes. The test suite loads `shell/tests/fixtures/panel_ocr/golden_vectors.json` — the SAME file — so the two implementations cannot drift.

- [ ] **Step 1: Failing test** (node ≥20, built-in test runner)

```js
// shell/app/ocr/client/tests/panel_parser.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseValue, matchLabel, foldSets, battleToScoutnet, calibrateU } from '../panel_parser.mjs';
const FIX = JSON.parse(readFileSync(new URL('../../../../tests/fixtures/panel_ocr/golden_vectors.json', import.meta.url), 'utf8'));
const STATS = ['Attack', 'Defense', 'Lethality', 'Health'];

test('value grammar matches fixture', () => {
  for (const c of FIX.value_grammar_cases) {
    const got = parseValue(c.raw);
    if (c.value === null) assert.equal(got, null, c.raw);
    else assert.ok(got && Math.abs(got.value - c.value) < 1e-9, c.raw);
  }
});
test('labels match fixture', () => {
  for (const c of FIX.label_cases) assert.equal(matchLabel(c.raw), c.canonical, c.raw);
});
for (const acct of ['A', 'B']) {
  test(`law round-trips on account ${acct}`, () => {
    const a = FIX.accounts[acct];
    const [sScout, sBattle, pEnemy] = foldSets(a.specials_own, a.specials_enemy);
    for (const st of STATS) assert.ok(Math.abs(sScout[st] - a.S_scout[st]) < 1e-9, st);
    const scout = battleToScoutnet(a.battle_left, sScout, sBattle, pEnemy);
    for (const cls of Object.keys(a.scout))
      for (const st of STATS)
        assert.ok(Math.abs(scout[cls][st] - a.scout[cls][st]) <= 0.11, `${acct}/${cls}/${st}`);
    const U = calibrateU(a.bo_troops, a.bo_class, a.scout, a.S_scout);
    for (const st of STATS) assert.ok(Math.abs(U[st] - a.U[st]) <= 0.1, st);
  });
}
```

- [ ] **Step 2: Run `node --test shell/app/ocr/client/tests/panel_parser.test.mjs` — FAIL** with `ERR_MODULE_NOT_FOUND: Cannot find module '…panel_parser.mjs'` (the module under test doesn't exist yet). Do NOT pass the bare tests/ directory — Windows Node resolves it as a module and fails for the wrong reason.
- [ ] **Step 3: Implement** `panel_parser.mjs` by PORTING Tasks 2–8 line-for-line (same regexes, same skeleton/edit-distance fuzzy match, same thresholds `LOW_CONF=0.90`, same fold rules incl. own-city exclusion). No new behavior; where JS lacks a Python feature (namedtuple), use plain objects `{value, unit, signed}`.
- [ ] **Step 4: PASS.**  **Step 5: Commit** `ocr: client parser mirror, verified against the same golden vectors`.

---

### Task 11: Flow state machine (pure logic behind the mock's S1/S2/S5)

**Files:** Create `shell/app/ocr/client/flow_state.mjs`, `shell/app/ocr/client/tests/flow_state.test.mjs`

**Interfaces — Produces:** `createFlow()` returning an object with:
`pickKind(kind)` kind ∈ {battle,scout,citystats} → presets per spec (`scout→{you:'scout',enemy:'scout'}`, `citystats→{you:'citystats',enemy:'scout'}`, `battle→{you:'battle',enemy:'battle'}`);
`setSideType(side, type)` (validates: enemy never 'citystats'; never clears uploads);
`addShot(side, shotId)` / `removeShot(side, shotId)`;
`coverage()` → `{you: bool, enemy: bool, complete: bool}` where a battle-type side WITH a shot covers both sides, and a side's OWN shot takes precedence for that side;
`defaultHeroes(gen)` → `{Infantry, Lancer, Marksman}` names from a passed-in generation table (dependency-injected map, e.g. `{15:{Infantry:'Hank',Lancer:'Estrella',Marksman:'Viveca'}}`) or `null` per slot when gen unknown (never guess).

- [ ] **Step 1: Failing tests**

```js
// shell/app/ocr/client/tests/flow_state.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { createFlow } from '../flow_state.mjs';

test('S1 presets per spec', () => {
  const f = createFlow();
  f.pickKind('citystats');
  assert.deepEqual(f.types(), { you: 'citystats', enemy: 'scout' });
  f.pickKind('battle');
  assert.deepEqual(f.types(), { you: 'battle', enemy: 'battle' });
});
test('enemy can never be citystats', () => {
  const f = createFlow();
  assert.throws(() => f.setSideType('enemy', 'citystats'));
});
test('battle-with-shot covers both; own shot takes precedence', () => {
  const f = createFlow();
  f.pickKind('battle');
  f.addShot('you', 's1');
  assert.deepEqual(f.coverage(), { you: true, enemy: true, complete: true });
  f.setSideType('enemy', 'scout');          // enemy switches to its own scout shot
  assert.equal(f.coverage().enemy, true);   // still covered by the battle shot until...
  f.addShot('enemy', 's2');                 // ...own shot exists — precedence, still covered
  assert.equal(f.coverage().complete, true);
});
test('type changes never clear uploads', () => {
  const f = createFlow();
  f.pickKind('scout');
  f.addShot('you', 'a'); f.addShot('enemy', 'b');
  f.setSideType('you', 'citystats');
  assert.equal(f.shots('you').length, 1);
  assert.equal(f.shots('enemy').length, 1);
});
test('two-side without both shots is incomplete', () => {
  const f = createFlow();
  f.pickKind('scout');
  f.addShot('you', 'a');
  assert.deepEqual(f.coverage(), { you: true, enemy: false, complete: false });
});
test('hero defaulting from gen, never guessed', () => {
  const f = createFlow({ genTable: { 15: { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' } } });
  assert.deepEqual(f.defaultHeroes(15), { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' });
  assert.deepEqual(f.defaultHeroes(99), { Infantry: null, Lancer: null, Marksman: null });
});
```

- [ ] **Step 2: FAIL.**  **Step 3: Implement** (`flow_state.mjs`, ~60 lines: a closure over `{types, shots, genTable}` implementing exactly the rules above; battle-covers-both = `types[side]==='battle' && shots[side].length>0` covers the OTHER side too unless that side has its own shots).
- [ ] **Step 4: PASS.**  **Step 5: Commit** `ocr: flow state machine (presets, coverage, hero defaults)`.

---

### Task 12 (GATED — needs owner-supplied PNGs): real-engine adapters + accuracy benchmark

**Files:** Create `shell/app/ocr/client/engine_tesseract.mjs`, `shell/app/ocr/panel/engine_rapidocr.py`, `shell/tests/test_ocr_panel_benchmark.py`; fixture images under `shell/tests/fixtures/panel_ocr/images/` named `A_citystats_1.png, A_scout.png, A_battle.png, A_specials.png, B_citystats_1.png, B_citystats_2.png, B_scout.png, B_battle.png, B_specials.png` (+ any additional device variants).

**BLOCKED UNTIL:** the owner drops the real screenshots into that folder (the golden-vector VALUES for them are already in Task 0). Do not begin this task before the images exist; do not substitute synthetic renders.

**Adapter contract (both engines):** `image bytes -> list[token dict]` in the Task-1 normal form, colors populated for battle panels (classify value-token pixels: green if G>R+40, red if R>G+40 in sRGB, else None). Tesseract: two passes — full pass for labels, digit-whitelisted pass (`tessedit_char_whitelist="0123456789.,%+-"`) for value regions; merge by box overlap.

**The benchmark test (this is Phase-0 gate D2):**

```python
# shell/tests/test_ocr_panel_benchmark.py — marked @pytest.mark.benchmark, excluded from default run
# For each fixture image: engine -> tokens -> extract_panel -> compare against golden vectors.
# PASS BAR (from docs/OCR_SERVICE_PLAN.md Phase 0): digit accuracy >= 99% across all readable fields,
# and ZERO false-confident fields (a field emitted into stats with a wrong value = instant FAIL;
# wrong values may ONLY appear as unreadable/low-conf).
```

- [ ] Steps follow the same red→green cycle per engine; commit `ocr: real-engine adapters + benchmark`. **If neither engine clears the bar, ship with no HIGH-confidence tier rather than weakening it (owner decision D2).**

---

## Self-review checklist (run before handing to executors)
- Spec coverage: OCR_UX_FLOW_SPEC §1 (D1 gate → Task 9; no LLM → absent by design; never-fabricate → Tasks 2/5/8), §2 (per-side OCR → Tasks 8/9/11; battle both columns → Tasks 4/8; conversions → Task 6), §3 S1/S2 rules → Task 11, hero defaulting → Task 11; SERVICE_PLAN parser spec → Tasks 2–5, reconciliation → Task 6 CalibrationError; two-account law → Tasks 0/6/10.
- UI screens themselves (S0–S5 DOM) are covered by the mock as reference and are NOT in this plan's scope — they are a follow-on plan once the real host page integration point (overlay module mount) is scheduled.
- Type consistency: `Class|Stat` grammar everywhere; STATS tuple ordering identical in Python and JS; `LOW_CONF = 0.90` in both.

