# OCR Overlay UI — TDD Implementation Plan

> **For agentic workers (Codex or Claude subagents):** Execute task-by-task, strictly test-first (red → green → commit). Steps use checkbox syntax. Claude workers: use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. You need ZERO prior context beyond this document and the docs it cites — do not re-derive the spec from scratch.
>
> **Status: DRAFT for coordinator review.** This plan implements the binding architecture decisions below, but the research pass that produced it surfaced real ambiguities the source docs don't resolve. They are listed immediately below, each with the concrete default this plan builds to so the plan stays executable without blocking on an answer. Resolve or override before/while executing.

## COORDINATOR RULINGS (2026-08-10, BINDING — these resolve the open questions below; where a ruling contradicts a task's drafted text, the ruling wins)

1. **SERVER-ONLY v1.** The engine decision post-dates the docs the draft followed: tesseract.js benchmarked at 64% (benched); the D2-passing engines (RapidOCR 100%, Gemini 100%) are server-side behind `/shell/ocr/panel`'s production ladder. Task 7 shrinks accordingly: S3 = upload + server read with progress; NO client engine driver, no WASM load states. QA rows F8/F9 become N/A-v1 (documented in Task 10's gate list). The S3 trust copy is REPLACED (spec amended): "Sent securely and read right away. Your screenshots are never saved." The vendored tesseract stays untouched as the future client tier.
2. **3-tier display comes from the SERVER contract, better than the drafted degradation:** ok-tier = fields in `stats*` read by RapidOCR (`field_conf` present, no `field_engine` entry); check-tier (gold, "please check") = `field_engine`-marked Gemini fills — they carry values AND provenance; missing-tier = `unreadable_fields`/absent (type it). No client-row recovery. `classifyFields` implements exactly this.
3. **Hero-gen defaulting ships DORMANT as drafted** (adapter built + tested, always "unknown gen" in v1; empty + prompt state). No stopgap prompt.
4. **localStorage U-cache approved for v1** (keyed by `/shell/me` user_id). Server persistence = future shell/DB work, not this plan.
5. **`GET /shell/me` gate approved as drafted** (soft client gate + the hard 402 on upload — with server-only v1 the hard gate now covers the whole read path, strengthening the drafted design).
6. **The `overlay/middleware.py` + `test_overlay_inject.py` edits are AUTHORIZED** (minimal diff, intentional test update with reasons — same discipline as the limits.py change).
7. **"Direct read wins, silently" accepted for v1** — it IS the owner's own precedence rule from the mock rounds. P19's compare-and-choose screen = documented follow-on, out of scope.

## OPEN QUESTIONS (as drafted — resolved by the rulings above; kept for the record)

1. **Is client-side OCR (tesseract.js) actually primary for v1, or is this plan server-only?** The binding file-read list for this plan named `flow_state.mjs`, `panel_parser.mjs`, and `panel_router.py` — not `shell/app/ocr/client/engine_tesseract.mjs` (which already exists, already shaped correctly: `recognizeImage(bytes) -> token[]` matching the `OcrToken` normal form exactly) or `docs/OCR_SERVICE_PLAN.md`. But: `OCR_UX_FLOW_SPEC.md` §3 S3 commits to literal copy — *"Your screenshot stays on your phone. We read it right here."* — which is **false** if the flow only ever uploads to the server; `OCR_SERVICE_PLAN.md` §4/§9 designs client-side tesseract.js as the primary engine with server RapidOCR as an explicit fallback; and `docs/OCR_QA_PLAN.md` §5 rows **F8/F9** ("client engine fails to load → automatic server-fallback offer... three-step degradation" / "engine download interrupted mid-fetch → retry affordance") describe exactly that three-tier (client → server → manual) behavior as a release-gated requirement. **This plan builds the three-tier design** (Task 4, Task 7): client engine first, automatic escalation to `/shell/ocr/panel` on failure/timeout/insufficient read, manual typing always available as the floor. `engine_tesseract.mjs` is treated as an existing, already-built dependency this plan's controller calls through an injected seam — this plan does not add unit coverage for tesseract.js/WASM internals themselves (out of scope; flag separately if that coverage gap matters). If the coordinator intends server-only for v1, Task 7 shrinks and the S3 trust-line copy needs to change.

2. **S4's three visual states (ok / check-please-verify / missing) need data the server contract doesn't expose.** The mock's gold "check" state shows a *value* the user should verify. The real `/shell/ocr/panel` response (`shell/app/ocr/panel/service.py`) only ever gives two tiers: a field is either in `stats`/`stats_you`/`stats_enemy` (confidence ≥ 0.90, trusted) or it's a bare string key in `unreadable_fields` — there is no value, confidence, or reason attached to an unreadable key. A genuine "here's what we saw, low confidence, please check" value can only be recovered by calling `assembleRows`/`stitch` directly (both exported from `panel_parser.mjs`) on client-side tesseract tokens *before* `extractPanel`'s stricter bucket filter discards it. **This plan implements 3-tier when the client engine produced the read (row-level data available) and degrades to 2-tier (ok / missing) when the result came from the server fallback** (Task 2's `classifyFields`). This is an honest degradation, not a bug, but confirm it's acceptable — the alternative is extending the server response contract with a low-confidence preview field, which is out of scope here.

3. **Captain hero-gen defaulting ("gen badge → names") has no live data source anywhere in the codebase.** Neither `service.py` (this feature's OCR) nor the pre-existing `/shell/ocr` battle-report OCR (`shell/app/ocr/extract.py`) extracts a hero-generation number from a screenshot. `.claude/skills/wos-hero-identifier/SKILL.md` is a human/Claude-assisted manual identification workflow ("read the badge number N on the portrait"), not a wired API a browser can call. **This plan builds and tests the pure adapter** (`hero_generations.json` → gen-keyed table → `flow_state.defaultHeroes(gen)`, Task 2) so it is ready the moment a `gen` value exists, but ships it **dormant** in v1: captains keep whatever the real app already defaults to, and every side is always treated as "unknown gen" (QA row **F10**'s "empty + prompt" path, permanently). Confirm this is acceptable for v1, or scope a manual "which generation is your hero?" micro-prompt as a stopgap (not in the mock or spec — would need fresh design).

4. **City-Stats U-calibration has no persistence layer.** `docs/STAT_PANELS_FORMULA.md` §8 and `OCR_UX_FLOW_SPEC.md` §2 both say U is calibrated once per account and *stored*; no table, endpoint, or schema for that exists anywhere under `shell/`. **This plan caches U in `localStorage`, keyed by the `user_id` `/shell/me` already returns** (Task 4) — simplest honest v1 mechanism, never fabricates a value it doesn't have (falls to the QA row **P17** "needs one-time setup" state when nothing is cached and no fresh scout capture is available this session to calibrate from). Confirm localStorage is acceptable for v1, or this becomes a backend task (new table + endpoint) that this plan should not silently take on.

5. **Free-tier gate mechanism (this plan's call per the coordinator's decision item 7).** Uses an independent `GET /shell/me` fetch from `ocr_flow.js` (the endpoint already exists and already returns `user.plan`) rather than a 402 upload-probe — probing via a real upload would be wasteful and strange for a feature whose primary path never uploads anything. This duplicates `overlay.js`'s own `/shell/me` fetch (one extra small same-origin GET per page load) rather than reaching into `overlay.js` for its cached result, to keep the two overlay modules decoupled (see item 6). This is necessarily a **soft** client-side gate for the client-OCR path — nothing server-side can stop a modified client from calling `recognizeImage` directly; the **hard** gate is the existing 402 on the `/shell/ocr/panel` fallback. Documented as the unavoidable shape of gating a feature whose primary path is client-only, not an oversight.

6. **Where `ocr_flow.js`/`ocr_flow.css` are served from, and that this touches an "Agent A"-owned file.** `shell/app/overlay/middleware.py`'s header attributes that package to "Agent A," and this plan's Task 5 both (a) mounts `shell/app/ocr/client/` as a static directory (needed regardless, so the browser can `import` `flow_state.mjs`/`panel_parser.mjs`/`engine_tesseract.mjs`/the vendored tesseract.js assets at runtime — not just so it can fetch two fixed files) and (b) edits `middleware.py`'s `inject()`/`SCRIPT_TAG` to add the new `<link>`/`<script type="module">` tags alongside the existing chip's `SCRIPT_TAG`. That edit necessarily changes `shell/tests/test_overlay_inject.py`'s byte-exact injection assertions (Task 5 updates that test explicitly, with reasons — this is a legitimate behavior change, not an unauthorized edit). Confirm this cross-package edit is fine to land in this plan, or that it should be coordinated with/handed to whoever owns `shell/app/overlay/` concurrently.

7. **Reconciliation when a side has two disagreeing data sources — deliberately NOT built here.** QA row **P19** describes a side's own scout upload *and* inherited battle-report coverage disagreeing beyond 0.11 pp after conversion, with the user shown both numbers to pick from. Task 4's `deriveViews` resolves this the simpler way instead: **a side's own direct read always wins outright** the moment one exists (`flow_state.mjs`'s own documented precedence) — the inherited/battle-derived view for that side is never even computed for comparison, so nothing is silently dropped, but nothing is surfaced as a disagreement either; whichever number the direct read produced is simply what fills. Building P19's actual compare-and-choose UI (which neither the mock nor the spec shows — it would be fresh design) is out of this plan's scope. Confirm "direct always wins, silently" is an acceptable v1 behavior for this specific edge case, or scope P19's reconciliation screen as follow-on work.

*(Not an open question, just a landmine to save the executor time: the mock's big-digit editor validates every field 0–6000 with no separate range for specials — this turns out to be correct as-is, because S4's review grid only ever shows the 24 class-stat cells, never specials rows; specials are an internal conversion input, not something the user edits directly. No inconsistency with `service.py`'s `CLASS_VALUE_MIN/MAX` once scoped correctly.)*

**Goal:** Users tap "Fill from screenshots" above the existing manual stat panel, add screenshots for both sides, watch them get read (on-device first, then a described fallback chain), review/fix the numbers, and land on the app's own existing battle-setup section with the scout-net panel and (where possible) captains pre-filled — never fabricating a value, always leaving an honest trail back to manual entry. Per `docs/OCR_UX_FLOW_SPEC.md`, mock reference `prototype/mocks/ocr_flow_mock.html`.

**Architecture:** The UI ships as two files injected by the existing `OverlayMiddleware` alongside the account chip: `shell/app/ocr/client/ocr_flow.js` (ES module, `type="module"`) + `ocr_flow.css`. `prototype/index.html` is **never edited** — the flow's "final act" is calling the app's own already-global functions (`applyPanel`, `applyHeroes`, `updateFinalStats`, the `#statsScouted` checkbox) exactly as its own "Load config" feature does, and its own DOM (`#statPanel`, `#capMe`/`#capFoe`, `#formMe`/`#formFoe`) exactly as it already renders. Five pure logic modules (import-tested against real, previously-verified data — the golden vectors and the real API contract, never invented numbers) do all the thinking; five thin screen modules do string-template rendering + delegated events; a controller module wires state (`flow_state.mjs`) to logic to screens. Client OCR (tesseract.js via the existing `engine_tesseract.mjs`) is tried first; `/shell/ocr/panel` is an automatic, described fallback; manual typing is always the floor. See Open Question 1 if that premise is wrong for this plan's scope.

**Tech stack:** Vanilla ES modules, zero new dependencies, tested with Node's built-in `node:test` (dev-only — nothing new ships to the browser beyond what's already vendored under `shell/app/ocr/client/vendor/`). Python/FastAPI/pytest only for the injection-seam task (Task 5). No bundler, no build step — the browser loads `ocr_flow.js` and its sibling `.mjs` imports directly over HTTP.

## Global constraints (every task inherits these)

- **Never fabricate:** a value only appears as trustworthy once it is either API-confirmed (≥ 0.90 confidence, present in `stats`/`stats_you`/`stats_enemy`) or user-typed. A low-confidence client-side read may be *shown* for the user to confirm (the "check" tier, Open Question 2) but is never auto-filled into the real app's inputs.
- **Determinism:** every pure module (`convert_side.mjs`, `fill_mapper.mjs`, `error_copy.mjs`, the controller's decision logic) is a function of its inputs — no wall-clock, no randomness, dependencies (network calls, the OCR engine, `localStorage`) always **injected**, never imported-and-called directly, so tests never touch a real network or a real WASM engine.
- **Terminology:** "screenshot(s)" — never "picture"/"photo". No jargon in user-facing copy: "OCR", "parse", "confidence", raw HTTP status codes, and internal error codes (`payment_required`, `quota_exhausted`, etc.) are all banned from strings a user reads. `error_copy.mjs` (Task 3) is tested explicitly against this list.
- **`[hidden]{display:none!important}`** pattern for all show/hide; reduced-motion kill-switch (`@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}`) in `ocr_flow.css`; ≥44px touch targets on every interactive element; focus moves to the new screen's heading on every navigation (`el.setAttribute('tabindex','-1'); el.focus({preventScroll:true})`, matching the mock's own pattern exactly); auto-advance screens (PREP→S3→S4) **replace** the current history entry rather than pushing, so Back/Cancel always lands on the last screen the user deliberately chose.
- **Do not modify** `prototype/index.html`, `wos_sim/` engine code, or anything in `WOSTests.com`. `shell/app/overlay/middleware.py` and `shell/app/overlay/__init__.py`/`shell/app/main.py` (Task 5 only) and `shell/tests/test_overlay_inject.py` (Task 5 only, see Open Question 6) are the only files outside the new-files list this plan touches.
- **Reference docs:** flow = `docs/OCR_UX_FLOW_SPEC.md`; copy/visual source of truth = `prototype/mocks/ocr_flow_mock.html`; math = `docs/STAT_PANELS_FORMULA.md` §8; API = `shell/app/ocr/panel_router.py` + `shell/app/ocr/panel/service.py` + `shell/app/limits.py`; QA gate = `docs/OCR_QA_PLAN.md` §5 (L4, rows F1–F13).
- Commit after every green test, message prefix `ocr:`.
- Run Python tests: `py -m pytest shell/tests/<file> -q` (from repo root `E:\WOS\Battle Simulator`).
- Run JS tests with **explicit file paths** (Windows Node treats a bare directory argument as a module and fails with `MODULE_NOT_FOUND` — verified Node v24.14.1): `node --test shell/app/ocr/client/tests/<file1>.test.mjs shell/app/ocr/client/tests/<file2>.test.mjs ...` — each task's steps list the cumulative explicit file set to run.

## File structure (locked)

```
shell/tests/fixtures/overlay_ui/api_samples.json        # Task 0 — the contract: real API response + denial shapes
shell/app/ocr/client/tests/api_samples.test.mjs          # Task 0
shell/app/ocr/client/convert_side.mjs                    # Task 1 — per-side conversion orchestrator
shell/app/ocr/client/tests/convert_side.test.mjs         # Task 1
shell/app/ocr/client/fill_mapper.mjs                      # Task 2 — percent/hero-gen/field-tier/snapshot mapping
shell/app/ocr/client/tests/fill_mapper.test.mjs           # Task 2
shell/app/ocr/client/error_copy.mjs                       # Task 3 — HTTP status/body -> honest user copy
shell/app/ocr/client/tests/error_copy.test.mjs            # Task 3
shell/app/ocr/client/controller.mjs                       # Task 4 — flow controller ("state glue")
shell/app/ocr/client/tests/controller.test.mjs            # Task 4
shell/app/overlay/middleware.py                           # Task 5 — MODIFIED: inject ocr_flow tags too
shell/app/main.py                                         # Task 5 — MODIFIED: mount shell/app/ocr/client/ as static
shell/tests/test_overlay_inject.py                        # Task 5 — MODIFIED: injection now carries 3 tags
shell/tests/test_overlay_ocr_client_assets.py             # Task 5 — new: static mount + injection order
shell/app/ocr/client/screens/entry.mjs                    # Task 5 — S0 CTA + free-tier gate screen
shell/app/ocr/client/tests/screens_entry.test.mjs         # Task 5
shell/app/ocr/client/screens/pick_upload.mjs              # Task 6 — S1 + S2 + E1
shell/app/ocr/client/tests/screens_pick_upload.test.mjs   # Task 6
shell/app/ocr/client/screens/reading.mjs                  # Task 7 — PREP + S3
shell/app/ocr/client/tests/screens_reading.test.mjs       # Task 7
shell/app/ocr/client/screens/review.mjs                   # Task 8 — S4 (grid + editor + screenshot viewer)
shell/app/ocr/client/tests/screens_review.test.mjs        # Task 8
shell/app/ocr/client/screens/setup.mjs                    # Task 9 — S5 (fills the real app)
shell/app/ocr/client/tests/screens_setup.test.mjs         # Task 9
shell/app/ocr/client/ocr_flow.js                          # Tasks 5-9 — bootstrap; grows by one import per task
shell/app/ocr/client/ocr_flow.css                         # Tasks 5-9 — styles; grows by one section per task
```

---

### Task 0: Fixtures — the contract every later task tests against

**Files:** Create `shell/tests/fixtures/overlay_ui/api_samples.json`, `shell/app/ocr/client/tests/api_samples.test.mjs`

**Interfaces — Produces:** fixture keys `ok.scout_you`, `ok.battle_specials_read`, `ok.battle_specials_partial`, `ok.battle_specials_none`, `ok.citystats_you`, `partial.scout_missing_fields`, `failed.scout_failed`, `denials.{401,402,411,413,415,422_side,422_panel,422_count,429_quota,429_burst,503}` — every value transcribed byte-for-byte from `shell/app/ocr/panel/service.py`, `shell/app/ocr/panel_router.py`, and `shell/app/limits.py` (never invented), and every "ok"/"partial" numeric sample reuses `shell/tests/fixtures/panel_ocr/golden_vectors.json` account A's real, already-verified numbers so later tasks can cross-check against the same ground truth instead of a second, driftable copy.

- [ ] **Step 1: Write the failing test**

```js
// shell/app/ocr/client/tests/api_samples.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const FIX = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/overlay_ui/api_samples.json', import.meta.url), 'utf8'));
const GOLD = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/panel_ocr/golden_vectors.json', import.meta.url), 'utf8'));

test('ok samples carry the real response shape', () => {
  const scout = FIX.ok.scout_you;
  assert.equal(scout.panel_type, 'scout');
  assert.equal(scout.requested_side, 'you');
  assert.equal(scout.status, 'ok');
  assert.equal(scout.specials_observed, 'read');
  assert.equal(Object.keys(scout.stats).length, 12);
  assert.deepEqual(scout.unreadable_fields, []);

  const battle = FIX.ok.battle_specials_read;
  assert.ok('stats_left' in battle && 'stats_right' in battle);
  assert.ok('stats_you' in battle && 'stats_enemy' in battle);
  assert.ok('specials_you' in battle && 'specials_enemy' in battle);
  assert.equal(battle.specials_observed, 'read');
});

test('ok scout_you reuses golden-vector account A numbers verbatim (no invented data)', () => {
  const scout = FIX.ok.scout_you.stats;
  for (const cls of Object.keys(GOLD.accounts.A.scout)) {
    for (const stat of Object.keys(GOLD.accounts.A.scout[cls])) {
      assert.equal(scout[`${cls}|${stat}`], GOLD.accounts.A.scout[cls][stat]);
    }
  }
});

test('battle_specials_read reuses golden-vector account A battle + specials verbatim', () => {
  const b = FIX.ok.battle_specials_read;
  for (const cls of Object.keys(GOLD.accounts.A.battle_left)) {
    for (const stat of Object.keys(GOLD.accounts.A.battle_left[cls])) {
      assert.equal(b.stats_you[`${cls}|${stat}`], GOLD.accounts.A.battle_left[cls][stat]);
      assert.equal(b.stats_enemy[`${cls}|${stat}`], GOLD.accounts.A.battle_right[cls][stat]);
    }
  }
  const ownLabels = new Set(b.specials_you.map((s) => s.label));
  for (const special of GOLD.accounts.A.specials_own) assert.ok(ownLabels.has(special.label));
});

test('partial/failed samples never smuggle a value into stats', () => {
  const p = FIX.partial.scout_missing_fields;
  assert.equal(p.status, 'partial');
  for (const key of p.unreadable_fields) assert.ok(!(key.split('.')[1] in p.stats));
  assert.equal(FIX.failed.scout_failed.status, 'failed');
  assert.deepEqual(FIX.failed.scout_failed.stats, {});
});

test('denial shapes match the real HTTP contract exactly', () => {
  assert.deepEqual(FIX.denials['401'], { status: 401, body: { error: 'auth_required' } });
  assert.equal(FIX.denials['402'].status, 402);
  assert.equal(FIX.denials['402'].body.error, 'payment_required');
  assert.match(FIX.denials['402'].body.message, /Pro feature/);
  assert.equal(FIX.denials['411'].status, 411);
  assert.equal(FIX.denials['411'].body.error, 'length_required');
  assert.equal(FIX.denials['413'].status, 413);
  assert.equal(FIX.denials['413'].body.error, 'body_too_large');
  assert.equal(FIX.denials['415'].status, 415);
  assert.equal(FIX.denials['415'].body.error, 'unsupported_image_type');
  assert.equal(FIX.denials['422_side'].body.error, 'invalid_side');
  assert.equal(FIX.denials['429_quota'].status, 429);
  assert.equal(FIX.denials['429_quota'].body.error, 'quota_exhausted');
  assert.equal(FIX.denials['429_burst'].body.error, 'burst');
  assert.equal(FIX.denials['503'].status, 503);
  assert.equal(FIX.denials['503'].body.error, 'ocr_engine_unavailable');
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test shell/app/ocr/client/tests/api_samples.test.mjs` → FAIL (fixture file missing).

- [ ] **Step 3: Create the fixture** (values transcribed from `service.py`/`panel_router.py`/`limits.py` and `golden_vectors.json` account A — no new numbers invented anywhere in this file):

```json
{
  "ok": {
    "scout_you": {
      "panel_type": "scout", "requested_side": "you", "specials": [], "specials_observed": "read",
      "warnings": [],
      "stats": {
        "Infantry|Attack": 4491.6, "Infantry|Defense": 3979.1, "Infantry|Lethality": 2794.3, "Infantry|Health": 3197.4,
        "Lancer|Attack": 4480.4, "Lancer|Defense": 3924.1, "Lancer|Lethality": 2786.7, "Lancer|Health": 3111.4,
        "Marksman|Attack": 4451.6, "Marksman|Defense": 3924.1, "Marksman|Lethality": 2745.8, "Marksman|Health": 3101.6
      },
      "field_conf": {
        "Infantry|Attack": 0.99, "Infantry|Defense": 0.99, "Infantry|Lethality": 0.99, "Infantry|Health": 0.99,
        "Lancer|Attack": 0.99, "Lancer|Defense": 0.99, "Lancer|Lethality": 0.99, "Lancer|Health": 0.99,
        "Marksman|Attack": 0.99, "Marksman|Defense": 0.99, "Marksman|Lethality": 0.99, "Marksman|Health": 0.99
      },
      "unreadable_fields": [], "status": "ok", "source": "mock"
    },
    "battle_specials_read": {
      "panel_type": "battle", "requested_side": "you", "specials_observed": "read", "warnings": [],
      "stats_left": {
        "Infantry|Attack": 4859.0, "Infantry|Defense": 4098.0, "Infantry|Lethality": 2683.0, "Infantry|Health": 3040.4,
        "Lancer|Attack": 4846.8, "Lancer|Defense": 4041.4, "Lancer|Lethality": 2675.6, "Lancer|Health": 2958.5,
        "Marksman|Attack": 4815.8, "Marksman|Defense": 4041.4, "Marksman|Lethality": 2636.3, "Marksman|Health": 2949.2
      },
      "stats_right": {
        "Infantry|Attack": 694.3, "Infantry|Defense": 545.6, "Infantry|Lethality": 495.7, "Infantry|Health": 416.4,
        "Lancer|Attack": 740.5, "Lancer|Defense": 574.7, "Lancer|Lethality": 533.5, "Lancer|Health": 442.8,
        "Marksman|Attack": 800.6, "Marksman|Defense": 626.6, "Marksman|Lethality": 587.1, "Marksman|Health": 499.0
      },
      "stats_you": {
        "Infantry|Attack": 4859.0, "Infantry|Defense": 4098.0, "Infantry|Lethality": 2683.0, "Infantry|Health": 3040.4,
        "Lancer|Attack": 4846.8, "Lancer|Defense": 4041.4, "Lancer|Lethality": 2675.6, "Lancer|Health": 2958.5,
        "Marksman|Attack": 4815.8, "Marksman|Defense": 4041.4, "Marksman|Lethality": 2636.3, "Marksman|Health": 2949.2
      },
      "stats_enemy": {
        "Infantry|Attack": 694.3, "Infantry|Defense": 545.6, "Infantry|Lethality": 495.7, "Infantry|Health": 416.4,
        "Lancer|Attack": 740.5, "Lancer|Defense": 574.7, "Lancer|Lethality": 533.5, "Lancer|Health": 442.8,
        "Marksman|Attack": 800.6, "Marksman|Defense": 626.6, "Marksman|Lethality": 587.1, "Marksman|Health": 499.0
      },
      "specials": [
        {"label": "Defender Troops' Attack", "value": 15.0, "side": "left"},
        {"label": "Defender Troops' Health", "value": 15.0, "side": "left"},
        {"label": "Territory Defender Attack", "value": 10.0, "side": "left"},
        {"label": "Territory Defender Defense", "value": 10.0, "side": "left"},
        {"label": "Enemy Defense Penalty (Pet Skill)", "value": -6.0, "side": "right"},
        {"label": "Enemy Lethality Penalty (Pet Skill)", "value": -4.0, "side": "right"},
        {"label": "Enemy Health Penalty (Pet Skill)", "value": -5.0, "side": "right"}
      ],
      "specials_you": [
        {"label": "Defender Troops' Attack", "value": 15.0, "side": "left"},
        {"label": "Defender Troops' Health", "value": 15.0, "side": "left"},
        {"label": "Territory Defender Attack", "value": 10.0, "side": "left"},
        {"label": "Territory Defender Defense", "value": 10.0, "side": "left"}
      ],
      "specials_enemy": [
        {"label": "Enemy Defense Penalty (Pet Skill)", "value": -6.0, "side": "right"},
        {"label": "Enemy Lethality Penalty (Pet Skill)", "value": -4.0, "side": "right"},
        {"label": "Enemy Health Penalty (Pet Skill)", "value": -5.0, "side": "right"}
      ],
      "unreadable_fields": [], "status": "ok", "source": "mock"
    },
    "citystats_you": {
      "panel_type": "citystats", "requested_side": "you", "specials": [], "specials_observed": "read", "warnings": [],
      "stats": {
        "Troops|Attack": 748.49, "Troops|Defense": 775.42, "Troops|Lethality": 238.84, "Troops|Health": 219.86,
        "Infantry|Attack": 658.25, "Infantry|Defense": 666.25, "Infantry|Lethality": 1197.36, "Infantry|Health": 1223.08,
        "Lancer|Attack": 649.25, "Lancer|Defense": 616.25, "Lancer|Lethality": 1190.39, "Lancer|Health": 1154.28,
        "Marksman|Attack": 626.25, "Marksman|Defense": 616.25, "Marksman|Lethality": 1153.24, "Marksman|Health": 1146.45
      },
      "field_conf": {}, "unreadable_fields": [], "status": "ok", "source": "mock"
    }
  },
  "partial": {
    "scout_missing_fields": {
      "panel_type": "scout", "requested_side": "enemy", "specials": [], "specials_observed": "none", "warnings": [],
      "stats": {
        "Infantry|Attack": 4491.6, "Infantry|Defense": 3979.1, "Infantry|Lethality": 2794.3,
        "Lancer|Attack": 4480.4, "Lancer|Defense": 3924.1
      },
      "field_conf": {
        "Infantry|Attack": 0.99, "Infantry|Defense": 0.99, "Infantry|Lethality": 0.99,
        "Lancer|Attack": 0.99, "Lancer|Defense": 0.99
      },
      "unreadable_fields": [
        "stats.Infantry|Health", "stats.Lancer|Lethality", "stats.Lancer|Health",
        "stats.Marksman|Attack", "stats.Marksman|Defense", "stats.Marksman|Lethality", "stats.Marksman|Health"
      ],
      "status": "partial", "source": "mock"
    }
  },
  "failed": {
    "scout_failed": {
      "panel_type": "unknown", "requested_side": "you", "specials": [], "specials_observed": "none", "warnings": [],
      "stats": {}, "field_conf": {}, "unreadable_fields": [], "status": "failed", "source": "mock"
    }
  },
  "denials": {
    "401": {"status": 401, "body": {"error": "auth_required"}},
    "402": {"status": 402, "body": {"error": "payment_required", "message": "Screenshot OCR is a Pro feature. Upgrade to use it."}},
    "411": {"status": 411, "body": {"error": "length_required", "message": "chunked uploads are not accepted; send a Content-Length"}},
    "413": {"status": 413, "body": {"error": "body_too_large"}},
    "415": {"status": 415, "body": {"error": "unsupported_image_type"}},
    "422_side": {"status": 422, "body": {"error": "invalid_side"}},
    "422_panel": {"status": 422, "body": {"error": "invalid_panel"}},
    "422_count": {"status": 422, "body": {"error": "invalid_file_count"}},
    "429_quota": {"status": 429, "body": {"error": "quota_exhausted", "message": "Daily limit reached: 10 OCR uploads/day on the pro plan. Resets at midnight UTC."}},
    "429_burst": {"status": 429, "body": {"error": "burst", "message": "Slow down: at most 20 requests per minute."}},
    "503": {"status": 503, "body": {"error": "ocr_engine_unavailable"}}
  }
}
```

- [ ] **Step 4: Run to verify all tests pass** — `node --test shell/app/ocr/client/tests/api_samples.test.mjs` → 5 passed.
- [ ] **Step 5: Commit** — `git add shell/tests/fixtures/overlay_ui/api_samples.json shell/app/ocr/client/tests/api_samples.test.mjs && git commit -m "ocr: overlay-UI API fixture (real shapes, golden-vector numbers, zero invented data)"`

---

### Task 1: Conversion orchestrator — `convert_side.mjs`

**Files:** Create `shell/app/ocr/client/convert_side.mjs`, `shell/app/ocr/client/tests/convert_side.test.mjs`

**Interfaces — Consumes:** `foldSets`, `battleToScoutnet`, `cityStatsToScoutnet`, `calibrateU`, `CalibrationError`, `MissingSpecialsError` (all from `panel_parser.mjs` — imported, never re-implemented, per the binding architecture decision). **Produces:**

`convertSide({ panelType, stats, specialsOwn, specialsEnemy, specialsObserved, calibratedU, scoutForCalibration }) -> ConversionResult`

```
ConversionResult = {
  outcome: 'ready' | 'needs_specials' | 'needs_calibration' | 'blocked',
  percents: { 'Class|Stat': number } | null,   // scout-net PERCENT points, ready to hand to fill_mapper
  rawUnconverted: { 'Class|Stat': number } | null,  // battle numbers, present only on 'needs_specials' (QA row P16's explicit fallback)
  calibratedU: { Attack, Defense, Lethality, Health } | null,  // present on a fresh citystats 'ready' outcome so the caller can persist it
  reason: string | null,
}
```

Rules (per `docs/STAT_PANELS_FORMULA.md` §8 and QA rows P16–P18 — P19's cross-source reconciliation is a controller-level, not a per-side-conversion, concern; see Open Question 7 for why this plan doesn't build it):
- `panelType === 'scout'` → always `ready`, `percents = stats` unchanged ("From a scout screenshot: use rows as-is. Done.").
- `panelType === 'battle'` → requires `specialsObserved === 'read'`; anything else is `needs_specials` with `rawUnconverted` set (P16's explicit unconverted-fallback, never silently treated as scout-net). On `read`, folds sets and applies `Scout+1 = (Battle+1)(1+S_scout)(1+P_enemy)/(1+S_battle)`.
- `panelType === 'citystats'` → also requires `specialsObserved === 'read'` (S_scout is needed for both calibration and application). If `calibratedU` is supplied, use it directly. Otherwise, if `scoutForCalibration` (a same-state scout `stats` dict) is supplied, calibrate U fresh and return it on the result (P17). Otherwise `needs_calibration`.
- `CalibrationError` from `calibrateU`/`battleToScoutnet` → `blocked` (P18's "these two screenshots don't match — retake both", worded by `error_copy.mjs` / the screen layer, not here).
- Unknown `panelType` → `blocked`.

- [ ] **Step 1: Write the failing tests**

```js
// shell/app/ocr/client/tests/convert_side.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { convertSide } from '../convert_side.mjs';

const GOLD = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/panel_ocr/golden_vectors.json', import.meta.url), 'utf8'));

function flat(grouped) {
  const out = {};
  for (const [cls, stats] of Object.entries(grouped)) {
    for (const [stat, value] of Object.entries(stats)) out[`${cls}|${stat}`] = value;
  }
  return out;
}

test('scout panel type is ready, unchanged', () => {
  const a = GOLD.accounts.A;
  const stats = flat(a.scout);
  const result = convertSide({ panelType: 'scout', stats, specialsOwn: [], specialsEnemy: [], specialsObserved: 'none' });
  assert.equal(result.outcome, 'ready');
  assert.deepEqual(result.percents, stats);
});

for (const acct of ['A', 'B']) {
  test(`battle panel with specials 'read' converts to scout-net within tolerance (account ${acct})`, () => {
    const a = GOLD.accounts[acct];
    const result = convertSide({
      panelType: 'battle', stats: flat(a.battle_left),
      specialsOwn: a.specials_own, specialsEnemy: a.specials_enemy, specialsObserved: 'read',
    });
    assert.equal(result.outcome, 'ready');
    for (const cls of Object.keys(a.scout)) {
      for (const stat of Object.keys(a.scout[cls])) {
        const got = result.percents[`${cls}|${stat}`];
        assert.ok(Math.abs(got - a.scout[cls][stat]) <= 0.11, `${acct}/${cls}/${stat}: ${got} vs ${a.scout[cls][stat]}`);
      }
    }
  });
}

test('battle panel abstains when specials were not fully captured, offers the raw numbers labeled unconverted', () => {
  const a = GOLD.accounts.A;
  const battleStats = flat(a.battle_left);
  for (const observed of ['none', 'partial']) {
    const result = convertSide({ panelType: 'battle', stats: battleStats, specialsOwn: [], specialsEnemy: [], specialsObserved: observed });
    assert.equal(result.outcome, 'needs_specials');
    assert.equal(result.percents, null);
    assert.deepEqual(result.rawUnconverted, battleStats);
  }
});

test('citystats with no calibration and no scout to calibrate from needs_calibration', () => {
  const a = GOLD.accounts.A;
  const stats = { ...flat({ Troops: a.bo_troops }), ...flat(a.bo_class) };
  const result = convertSide({ panelType: 'citystats', stats, specialsOwn: a.specials_own, specialsEnemy: a.specials_enemy, specialsObserved: 'read' });
  assert.equal(result.outcome, 'needs_calibration');
});

for (const acct of ['A', 'B']) {
  test(`citystats calibrates U fresh from a same-state scout capture and reproduces scout-net (account ${acct})`, () => {
    const a = GOLD.accounts[acct];
    const stats = { ...flat({ Troops: a.bo_troops }), ...flat(a.bo_class) };
    const result = convertSide({
      panelType: 'citystats', stats,
      specialsOwn: a.specials_own, specialsEnemy: a.specials_enemy, specialsObserved: 'read',
      scoutForCalibration: flat(a.scout),
    });
    assert.equal(result.outcome, 'ready');
    for (const stat of ['Attack', 'Defense', 'Lethality', 'Health']) {
      assert.ok(Math.abs(result.calibratedU[stat] - a.U[stat]) <= 0.10, `${acct}/${stat} U`);
    }
    for (const cls of Object.keys(a.scout)) {
      for (const stat of Object.keys(a.scout[cls])) {
        const got = result.percents[`${cls}|${stat}`];
        assert.ok(Math.abs(got - a.scout[cls][stat]) <= 0.11, `${acct}/${cls}/${stat}`);
      }
    }
  });
}

test('citystats reuses an already-cached calibratedU without needing a fresh scout capture', () => {
  const a = GOLD.accounts.A;
  const stats = { ...flat({ Troops: a.bo_troops }), ...flat(a.bo_class) };
  const result = convertSide({
    panelType: 'citystats', stats,
    specialsOwn: a.specials_own, specialsEnemy: a.specials_enemy, specialsObserved: 'read',
    calibratedU: a.U,
  });
  assert.equal(result.outcome, 'ready');
  assert.equal(result.percents['Infantry|Attack'].toFixed(1), a.scout.Infantry.Attack.toFixed(1));
});

test('unknown panel type is blocked, never silently treated as anything', () => {
  const result = convertSide({ panelType: 'unknown', stats: {}, specialsOwn: [], specialsEnemy: [], specialsObserved: 'none' });
  assert.equal(result.outcome, 'blocked');
  assert.equal(result.percents, null);
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test shell/app/ocr/client/tests/convert_side.test.mjs` → FAIL (module missing).

- [ ] **Step 3: Implement**

```js
// shell/app/ocr/client/convert_side.mjs
import {
  foldSets, battleToScoutnet, cityStatsToScoutnet, calibrateU,
  CalibrationError, MissingSpecialsError,
} from './panel_parser.mjs';

const CLASSES = ['Infantry', 'Lancer', 'Marksman'];
const STATS = ['Attack', 'Defense', 'Lethality', 'Health'];

function groupByClass(flat) {
  const out = {};
  for (const cls of CLASSES) {
    out[cls] = {};
    for (const stat of STATS) {
      const key = `${cls}|${stat}`;
      if (key in flat) out[cls][stat] = flat[key];
    }
  }
  return out;
}

function groupTroops(flat) {
  const out = {};
  for (const stat of STATS) {
    const key = `Troops|${stat}`;
    if (key in flat) out[stat] = flat[key];
  }
  return out;
}

function flattenByClass(grouped) {
  const out = {};
  for (const [cls, stats] of Object.entries(grouped)) {
    for (const [stat, value] of Object.entries(stats)) out[`${cls}|${stat}`] = value;
  }
  return out;
}

function ready(percents, extra = {}) {
  return { outcome: 'ready', percents, rawUnconverted: null, calibratedU: null, reason: null, ...extra };
}
function needsSpecials(rawUnconverted, reason) {
  return { outcome: 'needs_specials', percents: null, rawUnconverted, calibratedU: null, reason };
}
function needsCalibration(reason) {
  return { outcome: 'needs_calibration', percents: null, rawUnconverted: null, calibratedU: null, reason };
}
function blocked(reason) {
  return { outcome: 'blocked', percents: null, rawUnconverted: null, calibratedU: null, reason };
}

export function convertSide({
  panelType, stats, specialsOwn = [], specialsEnemy = [], specialsObserved = 'none',
  calibratedU = null, scoutForCalibration = null,
}) {
  if (panelType === 'scout') return ready(stats);

  if (panelType === 'battle') {
    if (specialsObserved !== 'read') {
      return needsSpecials(stats, 'the Stat Bonuses screenshot for this side has not been fully read yet');
    }
    try {
      const [sScout, sBattle, pEnemy] = foldSets(specialsOwn, specialsEnemy, { observed: specialsObserved });
      const scoutGrouped = battleToScoutnet(groupByClass(stats), sScout, sBattle, pEnemy);
      return ready(flattenByClass(scoutGrouped));
    } catch (err) {
      if (err instanceof MissingSpecialsError) return needsSpecials(stats, err.message);
      if (err instanceof CalibrationError) return blocked(err.message);
      throw err;
    }
  }

  if (panelType === 'citystats') {
    if (specialsObserved !== 'read') {
      return needsSpecials(null, 'the Stat Bonuses screenshot for this side has not been fully read yet');
    }
    const boTroops = groupTroops(stats);
    const boClass = groupByClass(stats);
    try {
      const [sScout] = foldSets(specialsOwn, specialsEnemy, { observed: specialsObserved });
      let U = calibratedU;
      let freshlyCalibrated = null;
      if (!U) {
        if (!scoutForCalibration) {
          return needsCalibration('this account needs a one-time setup: add a matching scout screenshot once');
        }
        U = calibrateU(boTroops, boClass, groupByClass(scoutForCalibration), sScout);
        freshlyCalibrated = U;
      }
      const scoutGrouped = cityStatsToScoutnet(boTroops, boClass, U, sScout);
      return ready(flattenByClass(scoutGrouped), { calibratedU: freshlyCalibrated });
    } catch (err) {
      if (err instanceof MissingSpecialsError) return needsSpecials(null, err.message);
      if (err instanceof CalibrationError) return blocked(err.message);
      throw err;
    }
  }

  return blocked(`cannot convert panel type: ${panelType}`);
}
```

- [ ] **Step 4: Run to verify all pass** — `node --test shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs` → all passed (both accounts, both panel types).
- [ ] **Step 5: Commit** — `git add shell/app/ocr/client/convert_side.mjs shell/app/ocr/client/tests/convert_side.test.mjs && git commit -m "ocr: per-side conversion orchestrator, golden-verified on both accounts"`

---

### Task 2: Fill-mapper — `fill_mapper.mjs`

**Files:** Create `shell/app/ocr/client/fill_mapper.mjs`, `shell/app/ocr/client/tests/fill_mapper.test.mjs`

**Interfaces — Consumes:** `convertSide`'s `percents` output (Task 1); `flow_state.mjs`'s `defaultHeroes(gen)` contract (already built — this task only builds the adapter that feeds it real data). **Produces**, all pure (no DOM, no globals — the thin wrappers that actually call `window.applyPanel`/`window.applyHeroes`/`window.readInputPanelPct`/`window.readHeroes` live in `controller.mjs`/`screens/setup.mjs`, Task 4/9, and are exercised only by the final browser gate per the decided test split):

- `sideToWhich(side)` — `'you'→'me'`, `'enemy'→'foe'`, throws on anything else.
- `toApplyPanelPayload(percents)` — `{ 'Class|Stat': percentValue }` → `{ 'Class|Stat': fractionValue }` (÷100), the exact shape `applyPanel(which, panel)` (`prototype/index.html`) expects — it does `x.value = +(panel[k]*100).toFixed(2)`, so the round-trip is percent → fraction → percent, never lossy beyond that function's own `.toFixed(2)`.
- `buildGenTable(heroGenerationsJson)` — inverts `wos_sim/data/hero_generations.json`'s `{name: {generation, troop}}` shape into the gen-keyed `{gen: {Infantry, Lancer, Marksman}}` shape `flow_state.mjs`'s `defaultHeroes(gen)` already expects (its own tests inject exactly this shape). One hero per (generation, class) is a game-mechanics invariant (`.claude/skills/wos-hero-identifier/SKILL.md`: "each generation has exactly three heroes — one per troop class") — a collision is a data-file defect, so `buildGenTable` throws rather than silently dropping one.
- `toApplyHeroesPayload(namesByClass)` — `{Infantry, Lancer, Marksman}` (any may be `null`) → `[Infantry, Lancer, Marksman]`, the exact ordered-array shape `applyHeroes(id, names)` expects (`arr[i]` falsy ⇒ that lane is left untouched, never blanked — matches its own real behavior read from `prototype/index.html`).
- `classifyFields({ expectedKeys, stats, fieldConf, lowConfRows })` — the S4 3-tier logic (Open Question 2): a key present in `stats` is `FIELD_OK`; else, if present in the optional `lowConfRows` (client-engine-only row-level data, `{key, value, conf}[]`), it's `FIELD_CHECK`; else `FIELD_MISSING`. `lowConfRows` defaults to `[]`, so a server-sourced result naturally degrades to 2-tier.
- `ALL_FIELD_KEYS` — the fixed 12-entry `Class|Stat` key order (`Infantry|Attack, Infantry|Defense, ... Marksman|Health`), exported so every consumer (fill-mapper, review screen, controller) iterates fields in one canonical, tested order.
- `buildSnapshot({ percentsMe, percentsFoe, heroesMe, heroesFoe, statsScoutedChecked })` — the pre-fill undo snapshot's pure shape (mock's `priorSnapshot`/`#undoChip`, but data-driven instead of demo-scripted): stores `applyPanel`-ready fractions for both sides plus the pre-fill hero names and checkbox state, so restoring is a direct replay through the same real functions used to fill.

- [ ] **Step 1: Write the failing tests**

```js
// shell/app/ocr/client/tests/fill_mapper.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  sideToWhich, toApplyPanelPayload, buildGenTable, toApplyHeroesPayload,
  classifyFields, ALL_FIELD_KEYS, FIELD_OK, FIELD_CHECK, FIELD_MISSING, buildSnapshot,
} from '../fill_mapper.mjs';

test('sideToWhich maps the OCR vocabulary onto the real app vocabulary', () => {
  assert.equal(sideToWhich('you'), 'me');
  assert.equal(sideToWhich('enemy'), 'foe');
  assert.throws(() => sideToWhich('bogus'));
});

test('toApplyPanelPayload converts percent points to the fractions applyPanel expects', () => {
  const payload = toApplyPanelPayload({ 'Infantry|Attack': 4491.6, 'Lancer|Health': 0 });
  assert.equal(payload['Infantry|Attack'], 44.916);
  assert.equal(payload['Lancer|Health'], 0);
});

test('buildGenTable inverts the name-keyed hero file into the gen-keyed shape defaultHeroes expects', () => {
  const raw = {
    Hank: { generation: 15, troop: 'Infantry' },
    Estrella: { generation: 15, troop: 'Lancer' },
    Viveca: { generation: 15, troop: 'Marksman' },
    Cara: { generation: 14, troop: 'Marksman' },
  };
  const table = buildGenTable(raw);
  assert.deepEqual(table[15], { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' });
  assert.equal(table[14].Marksman, 'Cara');
});

test('buildGenTable throws on a data collision rather than silently dropping a hero', () => {
  const raw = {
    Hank: { generation: 15, troop: 'Infantry' },
    Impostor: { generation: 15, troop: 'Infantry' },
  };
  assert.throws(() => buildGenTable(raw), /15.*Infantry/);
});

test('buildGenTable on the REAL hero_generations.json produces exactly one hero per (gen, class)', () => {
  const raw = JSON.parse(readFileSync(
    new URL('../../../../../wos_sim/data/hero_generations.json', import.meta.url), 'utf8'));
  const table = buildGenTable(raw);
  for (const gen of Object.keys(table)) {
    for (const cls of ['Infantry', 'Lancer', 'Marksman']) {
      assert.ok(typeof table[gen][cls] === 'string' || table[gen][cls] === undefined, `${gen}/${cls}`);
    }
  }
  // the known reference trio from the hero-identifier skill's own worked example
  assert.deepEqual(table[15], { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' });
});

test('toApplyHeroesPayload orders by class and preserves nulls (untouched lanes, never blanked)', () => {
  assert.deepEqual(
    toApplyHeroesPayload({ Infantry: 'Hank', Lancer: null, Marksman: 'Viveca' }),
    ['Hank', null, 'Viveca'],
  );
});

test('classifyFields: present -> ok, low-conf-row -> check, absent -> missing', () => {
  const result = classifyFields({
    expectedKeys: ['Infantry|Attack', 'Infantry|Defense', 'Infantry|Lethality'],
    stats: { 'Infantry|Attack': 4491.6 },
    fieldConf: { 'Infantry|Attack': 0.99 },
    lowConfRows: [{ key: 'Infantry|Defense', value: 3900.0, conf: 0.62 }],
  });
  assert.deepEqual(result['Infantry|Attack'], { state: FIELD_OK, value: 4491.6, conf: 0.99 });
  assert.deepEqual(result['Infantry|Defense'], { state: FIELD_CHECK, value: 3900.0, conf: 0.62 });
  assert.deepEqual(result['Infantry|Lethality'], { state: FIELD_MISSING, value: null, conf: null });
});

test('classifyFields degrades to 2-tier (ok/missing) when no row-level data is available (server-sourced)', () => {
  const result = classifyFields({ expectedKeys: ['Marksman|Health'], stats: {}, fieldConf: {} });
  assert.equal(result['Marksman|Health'].state, FIELD_MISSING);
});

test('ALL_FIELD_KEYS is the fixed 12-key class-stat order', () => {
  assert.equal(ALL_FIELD_KEYS.length, 12);
  assert.equal(ALL_FIELD_KEYS[0], 'Infantry|Attack');
  assert.equal(ALL_FIELD_KEYS[ALL_FIELD_KEYS.length - 1], 'Marksman|Health');
});

test('buildSnapshot stores applyPanel-ready fractions and pre-fill hero/checkbox state', () => {
  const snap = buildSnapshot({
    percentsMe: { 'Infantry|Attack': 1300 }, percentsFoe: { 'Infantry|Attack': 1300 },
    heroesMe: { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' },
    heroesFoe: { Infantry: 'Gisela', Lancer: 'Flora', Marksman: 'Vulcanus' },
    statsScoutedChecked: false,
  });
  assert.equal(snap.me.panel['Infantry|Attack'], 13);
  assert.equal(snap.foe.panel['Infantry|Attack'], 13);
  assert.deepEqual(snap.heroesMe, { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' });
  assert.equal(snap.statsScoutedChecked, false);
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test shell/app/ocr/client/tests/fill_mapper.test.mjs` → FAIL (module missing).

- [ ] **Step 3: Implement**

```js
// shell/app/ocr/client/fill_mapper.mjs
const CLASSES = ['Infantry', 'Lancer', 'Marksman'];
const STATS = ['Attack', 'Defense', 'Lethality', 'Health'];

export const ALL_FIELD_KEYS = CLASSES.flatMap((cls) => STATS.map((stat) => `${cls}|${stat}`));

export const FIELD_OK = 'ok';
export const FIELD_CHECK = 'check';
export const FIELD_MISSING = 'missing';

export function sideToWhich(side) {
  if (side === 'you') return 'me';
  if (side === 'enemy') return 'foe';
  throw new Error(`unknown side: ${side}`);
}

export function toApplyPanelPayload(percents) {
  const out = {};
  for (const [key, value] of Object.entries(percents)) out[key] = value / 100;
  return out;
}

export function buildGenTable(heroGenerationsJson) {
  const table = {};
  for (const [name, info] of Object.entries(heroGenerationsJson)) {
    const gen = info.generation;
    const cls = info.troop;
    if (!CLASSES.includes(cls)) continue;    // non-troop-class entries (if any) are not lead-hero candidates
    table[gen] ??= {};
    if (table[gen][cls] && table[gen][cls] !== name) {
      throw new Error(`hero_generations.json data collision: generation ${gen} ${cls} has both `
        + `'${table[gen][cls]}' and '${name}' — expected exactly one hero per (generation, class)`);
    }
    table[gen][cls] = name;
  }
  return table;
}

export function toApplyHeroesPayload(namesByClass) {
  return CLASSES.map((cls) => namesByClass[cls] ?? null);
}

export function classifyFields({ expectedKeys, stats, fieldConf, lowConfRows = [] }) {
  const lowByKey = new Map(lowConfRows.map((row) => [row.key, row]));
  const out = {};
  for (const key of expectedKeys) {
    if (key in stats) {
      out[key] = { state: FIELD_OK, value: stats[key], conf: fieldConf[key] ?? null };
      continue;
    }
    const low = lowByKey.get(key);
    out[key] = low
      ? { state: FIELD_CHECK, value: low.value, conf: low.conf }
      : { state: FIELD_MISSING, value: null, conf: null };
  }
  return out;
}

export function buildSnapshot({ percentsMe, percentsFoe, heroesMe, heroesFoe, statsScoutedChecked }) {
  return {
    me: { panel: toApplyPanelPayload(percentsMe) },
    foe: { panel: toApplyPanelPayload(percentsFoe) },
    heroesMe, heroesFoe, statsScoutedChecked,
  };
}
```

- [ ] **Step 4: Run to verify all pass** — `node --test shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs` → all passed.
- [ ] **Step 5: Commit** — `git add shell/app/ocr/client/fill_mapper.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs && git commit -m "ocr: fill-mapper (percent/hero-gen/field-tier/snapshot pure mapping)"`

---

### Task 3: Error-copy mapper — `error_copy.mjs`

**Files:** Create `shell/app/ocr/client/error_copy.mjs`, `shell/app/ocr/client/tests/error_copy.test.mjs`

**Interfaces — Consumes:** Task 0's fixture `denials.*` shapes (`{status, body:{error, message?}}`) — the exact real HTTP contract. **Produces:** `mapError(status, body) -> { heading, body, cta }` where `cta` is one of `'upgrade' | 'retake' | 'wait' | 'slow_down' | 'retry_or_type' | 'sign_in'`. **Critical design point:** the server's own `body.message` (e.g. `limits.py`'s `"Screenshot OCR is a Pro feature. Upgrade to use it."`) is written for logs/API consumers and contains banned jargon (the literal word "OCR") — `mapError` **never passes it through**; it always writes fresh copy keyed only on `status`/`body.error`, per the global terminology constraints.

- [ ] **Step 1: Write the failing tests**

```js
// shell/app/ocr/client/tests/error_copy.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { mapError } from '../error_copy.mjs';

const FIX = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/overlay_ui/api_samples.json', import.meta.url), 'utf8'));

const BANNED = /\b(ocr|parse|parsing|confidence|payment_required|quota_exhausted|auth_required|ocr_engine_unavailable|unsupported_image_type|body_too_large|invalid_side|invalid_panel|invalid_file_count|burst)\b/i;
const STATUS_CODE_LEAK = /\b(401|402|411|413|415|422|429|503)\b/;

function allCopyText(result) {
  return `${result.heading} ${result.body}`;
}

test('402 payment_required maps to an honest upgrade note, never the word OCR', () => {
  const d = FIX.denials['402'];
  const result = mapError(d.status, d.body);
  assert.equal(result.cta, 'upgrade');
  assert.doesNotMatch(allCopyText(result), BANNED);
  assert.doesNotMatch(allCopyText(result), STATUS_CODE_LEAK);
});

test('413 and 415 both map to retake guidance', () => {
  for (const code of ['413', '415']) {
    const d = FIX.denials[code];
    const result = mapError(d.status, d.body);
    assert.equal(result.cta, 'retake');
  }
});

test('429 quota_exhausted and 429 burst map to DIFFERENT, distinguishing copy', () => {
  const quota = mapError(FIX.denials['429_quota'].status, FIX.denials['429_quota'].body);
  const burst = mapError(FIX.denials['429_burst'].status, FIX.denials['429_burst'].body);
  assert.equal(quota.cta, 'wait');
  assert.equal(burst.cta, 'slow_down');
  assert.notEqual(quota.heading, burst.heading);
});

test('503 maps to "the reader is busy" plus a manual-typing path', () => {
  const d = FIX.denials['503'];
  const result = mapError(d.status, d.body);
  assert.equal(result.cta, 'retry_or_type');
  assert.match(result.body, /busy/i);
});

test('401 maps to a sign-in prompt', () => {
  const result = mapError(FIX.denials['401'].status, FIX.denials['401'].body);
  assert.equal(result.cta, 'sign_in');
});

test('every real denial shape maps to copy with no banned jargon and no leaked status code', () => {
  for (const [name, d] of Object.entries(FIX.denials)) {
    const result = mapError(d.status, d.body);
    assert.ok(result.heading && result.body && result.cta, name);
    assert.doesNotMatch(allCopyText(result), BANNED, name);
    assert.doesNotMatch(allCopyText(result), STATUS_CODE_LEAK, name);
  }
});

test('unrecognized status/network failure falls back to a generic honest retry-or-type message', () => {
  const result = mapError(0, null);   // 0 = fetch threw (offline, DNS, etc.), no HTTP response at all
  assert.equal(result.cta, 'retry_or_type');
  assert.doesNotMatch(allCopyText(result), BANNED);
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test shell/app/ocr/client/tests/error_copy.test.mjs` → FAIL (module missing).

- [ ] **Step 3: Implement**

```js
// shell/app/ocr/client/error_copy.mjs
export function mapError(status, body) {
  const code = body && body.error;

  if (status === 402) {
    return {
      heading: 'This needs a paid plan',
      body: 'Reading screenshots is a paid feature. Typing the numbers in yourself is always free.',
      cta: 'upgrade',
    };
  }
  if (status === 413 || status === 415) {
    return {
      heading: "That screenshot didn't come through",
      body: 'Try a smaller screenshot, saved as a plain PNG or JPEG.',
      cta: 'retake',
    };
  }
  if (status === 429 && code === 'burst') {
    return {
      heading: 'Slow down a little',
      body: 'Give it a few seconds, then try again.',
      cta: 'slow_down',
    };
  }
  if (status === 429) {
    return {
      heading: "That's today's limit",
      body: "You've used up today's screenshot reads. They come back at midnight. You can still type the numbers in.",
      cta: 'wait',
    };
  }
  if (status === 503) {
    return {
      heading: 'The reader is busy right now',
      body: 'Try again in a moment, or type the numbers in yourself.',
      cta: 'retry_or_type',
    };
  }
  if (status === 401) {
    return {
      heading: 'Please sign in',
      body: 'Sign in to read screenshots.',
      cta: 'sign_in',
    };
  }
  // 411/422/anything else the UI should never trigger by construction, plus a real
  // network failure (status 0, no body) — degrade the same honest way as 503 rather
  // than surface an internal code.
  return {
    heading: "That didn't work",
    body: "Something went wrong on our end. Try again, or type the numbers in yourself.",
    cta: 'retry_or_type',
  };
}
```

- [ ] **Step 4: Run to verify all pass** — `node --test shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs shell/app/ocr/client/tests/error_copy.test.mjs` → all passed.
- [ ] **Step 5: Commit** — `git add shell/app/ocr/client/error_copy.mjs shell/app/ocr/client/tests/error_copy.test.mjs && git commit -m "ocr: error-copy mapper (honest, jargon-free, status-code-free)"`

---

### Task 4: Flow controller ("state glue") — `controller.mjs`

**Files:** Create `shell/app/ocr/client/controller.mjs`, `shell/app/ocr/client/tests/controller.test.mjs`

**Interfaces — Consumes:** `flow_state.mjs`'s `createFlow` (unmodified, wrapped not re-implemented); `panel_parser.mjs`'s `extractPanel` (client-side use, mirrors what `ladder.py` does server-side but with the injected client engine); Tasks 1–3's `convertSide`/`classifyFields`/`mapError`. Every side-effecting capability is **injected**, so this task's tests never touch a real network, WASM engine, or `localStorage` (per the global determinism constraint and Open Question 1's client-first design):

```
createController({ genTable, recognizeImage, postPanel, fetchMe, storage, timeoutMs }) -> {
  flow,                                    // the underlying flow_state.mjs instance, untouched
  checkAccess() -> Promise<{allowed, plan, reachable, userId}>,
  readAll(shotBytesBySide) -> Promise<{results, views, conversion}>,
}
```

- `recognizeImage(bytes) -> Promise<token[]>` — the injected client engine (real: `engine_tesseract.mjs`'s `recognizeImage`; fake in every test here).
- `postPanel({shotBytesList, side, panelType}) -> Promise<resultJson>` — the injected server call (real: a `fetch('/shell/ocr/panel', ...)` wrapper built in Task 5/9's bootstrap; **on any non-2xx it must reject with an `Error` carrying `.status` and `.body`** so `mapError` can read them — this contract is asserted by the tests below, not by this task's own code).
- `fetchMe() -> Promise<{user:{plan, user_id, ...}, ...}>` — the injected `GET /shell/me` call (Open Question 5).
- `storage` — `{getItem(key) -> string|null, setItem(key, value)}`, the `localStorage` shape (Open Question 4's U cache), injected so tests use a plain object instead of a browser API.
- **Escalation policy (Open Question 1's default):** run the client engine on every shot (each wrapped in a `timeoutMs` race, default 5000ms per `docs/OCR_QA_PLAN.md` §6's client-OCR budget); if the client result's `status !== 'ok'` **or** the engine throws/times out, call `postPanel` once; if both exist, keep whichever has fewer `unreadable_fields`; if only the server call fails too, keep the client result if one exists, else surface `error_copy.mjs`'s mapping. Never more than one server call per side per `readAll()` (no retry loop — a leftover gap is left for the user to type, honestly, not silently retried forever).
- **Coverage-aware reads:** `readAll` only calls `readSide` for sides that actually have bytes to read (`shotBytesBySide[side]` non-empty). A side with no bytes of its own but covered by the other side's `battle`-typed, successfully-read upload gets its view **derived** from that same result's `stats_you`/`stats_enemy`/`specials_you`/`specials_enemy` aliases (`service.py`'s own documented behavior) — never a second network/engine call.
- **U cache:** `readAll` reads/writes `storage` under key `` `ocr_u_${userId}` `` (JSON), only for the `you` side (city stats is self-only), only via `convertSide`'s own `calibratedU` in/`calibratedU` out contract from Task 1 — the controller never computes U itself.

- [ ] **Step 1: Write the failing tests**

```js
// shell/app/ocr/client/tests/controller.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createController } from '../controller.mjs';

const GOLD = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/panel_ocr/golden_vectors.json', import.meta.url), 'utf8'));

function scoutTokens(cls, stat, value, y) {
  return [
    { text: `${cls} ${stat}`, x0: 0.05, y0: y, x1: 0.4, y1: y + 0.03, conf: 0.99, color: null },
    { text: value, x0: 0.7, y0: y, x1: 0.95, y1: y + 0.03, conf: 0.97, color: null },
  ];
}
function fullScoutShot() {
  const rows = [
    ['Infantry', 'Attack', '+4491.6%'], ['Infantry', 'Defense', '+3979.1%'],
    ['Infantry', 'Lethality', '+2794.3%'], ['Infantry', 'Health', '+3197.4%'],
    ['Lancer', 'Attack', '+4480.4%'], ['Lancer', 'Defense', '+3924.1%'],
    ['Lancer', 'Lethality', '+2786.7%'], ['Lancer', 'Health', '+3111.4%'],
    ['Marksman', 'Attack', '+4451.6%'], ['Marksman', 'Defense', '+3924.1%'],
    ['Marksman', 'Lethality', '+2745.8%'], ['Marksman', 'Health', '+3101.6%'],
  ];
  let y = 0.05;
  const tokens = [];
  for (const [cls, stat, val] of rows) { tokens.push(...scoutTokens(cls, stat, val, y)); y += 0.06; }
  return tokens;
}

function memoryStorage() {
  const map = new Map();
  return { getItem: (k) => (map.has(k) ? map.get(k) : null), setItem: (k, v) => map.set(k, v) };
}

test('checkAccess reports plan and allowed from the injected /shell/me', async () => {
  const proController = createController({ fetchMe: async () => ({ user: { plan: 'pro', user_id: 'u1' } }) });
  assert.deepEqual(await proController.checkAccess(), { allowed: true, plan: 'pro', reachable: true, userId: 'u1' });

  const freeController = createController({ fetchMe: async () => ({ user: { plan: 'free', user_id: 'u2' } }) });
  const freeResult = await freeController.checkAccess();
  assert.equal(freeResult.allowed, false);

  const offlineController = createController({ fetchMe: async () => { throw new Error('network down'); } });
  const offlineResult = await offlineController.checkAccess();
  assert.equal(offlineResult.allowed, false);
  assert.equal(offlineResult.reachable, false);
});

test('client engine success never calls the server (on-device stays on-device)', async () => {
  let serverCalls = 0;
  const controller = createController({
    recognizeImage: async () => fullScoutShot(),
    postPanel: async () => { serverCalls += 1; throw new Error('should not be called'); },
    storage: memoryStorage(),
  });
  controller.flow.pickKind('scout');
  controller.flow.addShot('you', 's1');
  const { results, conversion } = await controller.readAll({ you: [new Uint8Array([1])] });
  assert.equal(results.you.status, 'ok');
  assert.equal(results.you.engineUsed, 'client');
  assert.equal(serverCalls, 0);
  assert.equal(conversion.you.outcome, 'ready');
  assert.equal(conversion.you.percents['Infantry|Attack'], 4491.6);
});

test('client engine failure escalates to the server exactly once', async () => {
  let clientCalls = 0;
  let serverCalls = 0;
  const controller = createController({
    recognizeImage: async () => { clientCalls += 1; throw new Error('WASM failed to load'); },
    postPanel: async ({ side, panelType }) => {
      serverCalls += 1;
      return { panel_type: panelType, requested_side: side, specials: [], specials_observed: 'none',
                warnings: [], stats: { 'Infantry|Attack': 4491.6 }, field_conf: { 'Infantry|Attack': 0.99 },
                unreadable_fields: [], status: 'partial' };
    },
    storage: memoryStorage(),
  });
  controller.flow.pickKind('scout');
  controller.flow.addShot('you', 's1');
  const { results } = await controller.readAll({ you: [new Uint8Array([1])] });
  assert.equal(clientCalls, 1);
  assert.equal(serverCalls, 1);
  assert.equal(results.you.engineUsed, 'server');
  assert.equal(results.you.status, 'partial');
});

test('server result wins only when it is strictly more complete than the client result', async () => {
  const controller = createController({
    recognizeImage: async () => [],   // empty shot -> extractPanel resolves this to status "failed"
    postPanel: async () => ({
      panel_type: 'scout', requested_side: 'you', specials: [], specials_observed: 'none', warnings: [],
      stats: { 'Infantry|Attack': 4491.6 }, field_conf: { 'Infantry|Attack': 0.99 },
      unreadable_fields: ['stats.Infantry|Defense'], status: 'partial',
    }),
    storage: memoryStorage(),
  });
  controller.flow.pickKind('scout');
  controller.flow.addShot('you', 's1');
  const { results } = await controller.readAll({ you: [new Uint8Array([1])] });
  assert.equal(results.you.status, 'partial');   // server (partial) beats client (failed)
  assert.equal(results.you.engineUsed, 'client+server');
});

test('battle-covers-both: enemy view is derived from the same read, no second call', async () => {
  let recognizeCalls = 0;
  let serverCalls = 0;
  const controller = createController({
    recognizeImage: async () => { recognizeCalls += 1; return []; },   // will be "failed" -> escalate for 'you' only
    postPanel: async ({ side }) => {
      serverCalls += 1;
      return {
        panel_type: 'battle', requested_side: side, specials: [], specials_observed: 'read', warnings: [],
        stats_left: { 'Infantry|Attack': 4859.0 }, stats_left_conf: {},
        stats_right: { 'Infantry|Attack': 694.3 }, stats_right_conf: {},
        stats_you: { 'Infantry|Attack': 4859.0 }, stats_you_conf: {},
        stats_enemy: { 'Infantry|Attack': 694.3 }, stats_enemy_conf: {},
        specials_you: [], specials_enemy: [],
        unreadable_fields: [], status: 'partial',
      };
    },
    storage: memoryStorage(),
  });
  controller.flow.pickKind('battle');
  controller.flow.addShot('you', 's1');
  assert.deepEqual(controller.flow.coverage(), { you: true, enemy: true, complete: true });
  const { views } = await controller.readAll({ you: [new Uint8Array([1])] });   // no 'enemy' key at all
  assert.equal(recognizeCalls, 1);   // only 'you' was read
  assert.equal(serverCalls, 1);      // only 'you' escalated
  assert.equal(views.you.stats['Infantry|Attack'], 4859.0);
  assert.equal(views.enemy.stats['Infantry|Attack'], 694.3);   // derived, no extra call
});

test('city-stats U cache round-trips through the injected storage, keyed per user', async () => {
  // Reuses account A's REAL specials rows (not an empty/invented set) — cityStatsToScoutnet's
  // S_scout term must match what U was actually calibrated against, or the round-trip is
  // mathematically meaningless even with the "right" U plugged in.
  const a = GOLD.accounts.A;
  const citystatsResult = (statsOverride) => ({
    panel_type: 'citystats', requested_side: 'you',
    specials: a.specials_own.map((s) => ({ ...s, side: null })),
    specials_observed: 'read', warnings: [],
    stats: statsOverride, field_conf: {}, unreadable_fields: [],
    status: Object.keys(statsOverride).length ? 'ok' : 'failed',
  });
  const fullCityStats = {
    'Troops|Attack': a.bo_troops.Attack, 'Troops|Defense': a.bo_troops.Defense,
    'Troops|Lethality': a.bo_troops.Lethality, 'Troops|Health': a.bo_troops.Health,
    'Infantry|Attack': a.bo_class.Infantry.Attack, 'Infantry|Defense': a.bo_class.Infantry.Defense,
    'Infantry|Lethality': a.bo_class.Infantry.Lethality, 'Infantry|Health': a.bo_class.Infantry.Health,
    'Lancer|Attack': a.bo_class.Lancer.Attack, 'Lancer|Defense': a.bo_class.Lancer.Defense,
    'Lancer|Lethality': a.bo_class.Lancer.Lethality, 'Lancer|Health': a.bo_class.Lancer.Health,
    'Marksman|Attack': a.bo_class.Marksman.Attack, 'Marksman|Defense': a.bo_class.Marksman.Defense,
    'Marksman|Lethality': a.bo_class.Marksman.Lethality, 'Marksman|Health': a.bo_class.Marksman.Health,
  };

  const storage = memoryStorage();
  const controllerA = createController({
    fetchMe: async () => ({ user: { plan: 'pro', user_id: 'acct-A' } }),
    recognizeImage: async () => [],
    postPanel: async () => citystatsResult(fullCityStats),
    storage,
  });
  const access = await controllerA.checkAccess();
  controllerA.flow.pickKind('citystats');
  controllerA.flow.addShot('you', 's1');
  const before = await controllerA.readAll({ you: [new Uint8Array([1])] }, access.userId);
  assert.equal(before.conversion.you.outcome, 'needs_calibration');   // nothing cached yet

  storage.setItem(`ocr_u_${access.userId}`, JSON.stringify(a.U));
  const controllerB = createController({
    recognizeImage: async () => [],
    postPanel: async () => citystatsResult(fullCityStats),
    storage,
  });
  const after = await controllerB.readAll({ you: [new Uint8Array([1])] }, access.userId);
  assert.equal(after.conversion.you.outcome, 'ready');
  assert.ok(Math.abs(after.conversion.you.percents['Infantry|Attack'] - a.scout.Infantry.Attack) <= 0.11);
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test shell/app/ocr/client/tests/controller.test.mjs` → FAIL (module missing).

- [ ] **Step 3: Implement**

```js
// shell/app/ocr/client/controller.mjs
import { createFlow } from './flow_state.mjs';
import { extractPanel } from './panel_parser.mjs';
import { convertSide } from './convert_side.mjs';
import { mapError } from './error_copy.mjs';

const DEFAULT_TIMEOUT_MS = 5000;   // docs/OCR_QA_PLAN.md §6 client-OCR budget
const SIDES = ['you', 'enemy'];

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timed out after ${ms}ms`)), ms);
    Promise.resolve(promise).then(
      (value) => { clearTimeout(timer); resolve(value); },
      (err) => { clearTimeout(timer); reject(err); },
    );
  });
}

function countUnreadable(result) {
  return (result && result.unreadable_fields || []).length;
}

function betterOf(clientResult, serverResult) {
  if (!clientResult) return serverResult;
  if (!serverResult) return clientResult;
  return countUnreadable(serverResult) <= countUnreadable(clientResult) ? serverResult : clientResult;
}

function extractView(result, side) {
  if (result.panel_type === 'battle') {
    return {
      panelType: 'battle',
      stats: (side === 'you' ? result.stats_you : result.stats_enemy) || {},
      specialsOwn: (side === 'you' ? result.specials_you : result.specials_enemy) || [],
      specialsEnemy: (side === 'you' ? result.specials_enemy : result.specials_you) || [],
      specialsObserved: result.specials_observed,
    };
  }
  return {
    panelType: result.panel_type,
    stats: result.stats || {},
    specialsOwn: result.specials || [],
    specialsEnemy: [],
    specialsObserved: result.specials_observed,
  };
}

function deriveViews(types, results) {
  const views = { you: null, enemy: null };
  for (const side of SIDES) {
    const other = side === 'you' ? 'enemy' : 'you';
    if (results[side] && !results[side].error) {
      views[side] = extractView(results[side], side);
    } else if (types[other] === 'battle' && results[other] && !results[other].error
               && results[other].panel_type === 'battle') {
      views[side] = extractView(results[other], side);
    }
  }
  return views;
}

export function createController({
  genTable = {}, recognizeImage, postPanel, fetchMe, storage, timeoutMs = DEFAULT_TIMEOUT_MS,
} = {}) {
  const flow = createFlow({ genTable });

  async function checkAccess() {
    if (!fetchMe) return { allowed: false, plan: null, reachable: false, userId: null };
    let me;
    try {
      me = await fetchMe();
    } catch (err) {
      return { allowed: false, plan: null, reachable: false, userId: null };
    }
    const plan = me && me.user && me.user.plan;
    const userId = (me && me.user && me.user.user_id) || null;
    return { allowed: plan === 'pro', plan: plan || null, reachable: true, userId };
  }

  async function readSide({ side, panelType, shotBytesList }) {
    let clientResult = null;
    if (recognizeImage) {
      try {
        const shots = [];
        for (const bytes of shotBytesList) {
          shots.push(await withTimeout(recognizeImage(bytes), timeoutMs));
        }
        clientResult = extractPanel(shots, side, panelType);
        clientResult.engineUsed = 'client';
      } catch (err) {
        clientResult = null;
      }
    }
    if (clientResult && clientResult.status === 'ok') return clientResult;

    if (!postPanel) {
      if (clientResult) return clientResult;
      return { error: true, mapped: mapError(0, null) };
    }
    try {
      const serverResult = await postPanel({ shotBytesList, side, panelType });
      const winner = betterOf(clientResult, serverResult);
      winner.engineUsed = clientResult ? 'client+server' : 'server';
      return winner;
    } catch (err) {
      if (clientResult) return clientResult;
      return { error: true, mapped: mapError(err.status ?? 0, err.body ?? null) };
    }
  }

  function loadCachedU(userId) {
    if (!storage || !userId) return null;
    const raw = storage.getItem(`ocr_u_${userId}`);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (err) { return null; }
  }
  function saveCachedU(userId, U) {
    if (!storage || !userId) return;
    storage.setItem(`ocr_u_${userId}`, JSON.stringify(U));
  }

  async function readAll(shotBytesBySide, userId = null) {
    const types = flow.types();
    const results = {};
    for (const side of SIDES) {
      const bytesList = shotBytesBySide[side];
      if (!bytesList || !bytesList.length) continue;
      results[side] = await readSide({ side, panelType: types[side], shotBytesList: bytesList });
    }
    const views = deriveViews(types, results);
    const conversion = {};
    const cachedU = loadCachedU(userId);
    for (const side of SIDES) {
      if (!views[side]) continue;
      const extra = side === 'you' ? { calibratedU: cachedU } : {};
      const outcome = convertSide({ ...views[side], ...extra });
      conversion[side] = outcome;
      if (side === 'you' && outcome.calibratedU) saveCachedU(userId, outcome.calibratedU);
    }
    return { results, views, conversion };
  }

  return { flow, checkAccess, readAll };
}
```

- [ ] **Step 4: Run to verify all pass** — `node --test shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs shell/app/ocr/client/tests/error_copy.test.mjs shell/app/ocr/client/tests/controller.test.mjs` → all passed.
- [ ] **Step 5: Commit** — `git add shell/app/ocr/client/controller.mjs shell/app/ocr/client/tests/controller.test.mjs && git commit -m "ocr: flow controller — client-first reads, server escalation, coverage-aware, U cache"`

---

### Task 5: Entry seam — server-side injection, static mount, S0 CTA, free-tier gate

**Files:** Modify `shell/app/overlay/middleware.py`, `shell/app/main.py`, `shell/tests/test_overlay_inject.py`; Create `shell/tests/test_overlay_ocr_client_assets.py`, `shell/app/ocr/client/screens/entry.mjs`, `shell/app/ocr/client/tests/screens_entry.test.mjs`, `shell/app/ocr/client/ocr_flow.js`, `shell/app/ocr/client/ocr_flow.css`

**Note on the two modified test files:** `shell/tests/test_overlay_inject.py`'s injection is byte-exact-asserted; this task legitimately changes what gets injected (Open Question 6), so that test's expectations must change with it — this is not a scope-creep edit, it is the direct consequence of the feature this task implements. `shell/app/overlay/__init__.py` is **deliberately left untouched**: the new test imports `INJECTED_TAGS` from the `middleware` submodule directly rather than through the package's `__init__.py` re-export, to keep this plan's footprint in the "Agent A"-owned `overlay/` package to the one file that actually has to change.

**Interfaces — Produces:**
- `middleware.py`: `OCR_FLOW_CSS_TAG`, `OCR_FLOW_SCRIPT_TAG`, `INJECTED_TAGS = SCRIPT_TAG + OCR_FLOW_CSS_TAG + OCR_FLOW_SCRIPT_TAG`; `inject()` now inserts all three tags together, same position/case-insensitivity rules as before.
- `main.py`: `shell/app/ocr/client/` mounted at `/shell/ocr/client` via `StaticFiles` — this is what makes `flow_state.mjs`, `panel_parser.mjs`, `engine_tesseract.mjs`, and the vendored tesseract.js assets fetchable by the browser as real ES-module imports, not just the two files the injected tags name directly.
- `screens/entry.mjs`: `renderEntryCard()`, `renderUpgradeNote()` (pure, string-testable); `decideEntryAction(checkAccess) -> Promise<'proceed'|'upgrade'>` (pure decision, injected `checkAccess`); `mountEntry({root})`, `wireEntry(node, {checkAccess, onProceed, onNeedsUpgrade})`, `wireUpgradeNote(node, {checkout})` (thin DOM wrappers — exercised by the Task 10 browser gate, not node:test, per the decided test split).
- `ocr_flow.js`: the bootstrap — imports `screens/entry.mjs`, mounts it on `DOMContentLoaded` (or immediately if the document is already interactive/complete), guarded so importing this file under `node --test` (which has no `document`) never throws.

- [ ] **Step 1: Write the failing tests**

```python
# shell/tests/test_overlay_inject.py — MODIFIED (existing file; only the two byte-exact
# assertions and the import line change; every other test in this file is untouched)
from shell.app.config import Settings
from shell.app.main import create_app
from shell.app.overlay import SCRIPT_TAG, inject
from shell.app.overlay.middleware import INJECTED_TAGS   # NEW import

# ... (existing fixtures/tests unchanged) ...

def test_inject_before_last_body_tag_case_insensitive():
    assert inject(b"<html><body>x</body></html>") == \
        b"<html><body>x" + INJECTED_TAGS + b"</body></html>"
    assert inject(b"<HTML><BODY>x</BODY></HTML>").endswith(
        INJECTED_TAGS + b"</BODY></HTML>")


def test_inject_without_body_tag_appends():
    assert inject(b"<p>fragment</p>") == b"<p>fragment</p>" + INJECTED_TAGS
```

```python
# shell/tests/test_overlay_ocr_client_assets.py — new file
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from fastapi.testclient import TestClient

from shell.app.config import Settings
from shell.app.main import create_app
from shell.app.overlay import SCRIPT_TAG
from shell.app.overlay.middleware import OCR_FLOW_CSS_TAG, OCR_FLOW_SCRIPT_TAG

OVERLAY_TAG = SCRIPT_TAG.decode()
CSS_TAG = OCR_FLOW_CSS_TAG.decode()
JS_TAG = OCR_FLOW_SCRIPT_TAG.decode()


@pytest.fixture(autouse=True)
def _fresh_limits_state():
    try:
        from shell.app import db as _db
        _db.reset_db()
    except Exception:
        pass
    yield


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True)))


def test_served_index_carries_all_three_tags_in_order(client):
    resp = client.get("/")
    assert resp.status_code == 200
    text = resp.text
    assert OVERLAY_TAG in text and CSS_TAG in text and JS_TAG in text
    body_close = text.lower().rfind("</body>")
    assert text.find(OVERLAY_TAG) < text.find(CSS_TAG) < text.find(JS_TAG) < body_close


def test_ocr_flow_js_served_as_a_module_self_contained(client):
    resp = client.get("/shell/ocr/client/ocr_flow.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    for cdn in ("http://", "https://cdn", "googleapis", "unpkg", "jsdelivr"):
        assert cdn not in resp.text


def test_ocr_flow_css_served(client):
    resp = client.get("/shell/ocr/client/ocr_flow.css")
    assert resp.status_code == 200
    assert "css" in resp.headers["content-type"]


def test_sibling_client_modules_are_fetchable_for_browser_import(client):
    # The exact relative import targets ocr_flow.js resolves at runtime.
    for path in ("flow_state.mjs", "panel_parser.mjs", "engine_tesseract.mjs"):
        resp = client.get(f"/shell/ocr/client/{path}")
        assert resp.status_code == 200, path


def test_prototype_file_on_disk_still_untouched():
    html = (_REPO_ROOT / "prototype" / "index.html").read_text(encoding="utf-8")
    assert "/shell/ocr/client/ocr_flow.js" not in html
```

```js
// shell/app/ocr/client/tests/screens_entry.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderEntryCard, renderUpgradeNote, decideEntryAction } from '../screens/entry.mjs';

test('entry card reuses the mock copy verbatim', () => {
  const html = renderEntryCard();
  assert.match(html, /Fill from screenshots/);
  assert.match(html, /Fastest way\. No typing\./);
  assert.match(html, /id="ocrfCtaScreenshots"/);
  assert.doesNotMatch(html, /\bpicture\b/i);   // terminology rule: never "picture"
});

test('upgrade note never says OCR and matches the error-copy 402 body exactly', () => {
  const html = renderUpgradeNote();
  assert.match(html, /This needs a paid plan/);
  assert.match(html, /Reading screenshots is a paid feature\. Typing the numbers in yourself is always free\./);
  assert.doesNotMatch(html, /\bocr\b/i);
});

test('decideEntryAction proceeds for a paid plan and asks to upgrade otherwise', async () => {
  assert.equal(await decideEntryAction(async () => ({ allowed: true, plan: 'pro' })), 'proceed');
  assert.equal(await decideEntryAction(async () => ({ allowed: false, plan: 'free' })), 'upgrade');
  assert.equal(await decideEntryAction(async () => ({ allowed: false, plan: null, reachable: false })), 'upgrade');
});
```

- [ ] **Step 2: Run to verify each fails** — `py -m pytest shell/tests/test_overlay_inject.py shell/tests/test_overlay_ocr_client_assets.py -q` → the modified assertions FAIL (old `SCRIPT_TAG`-only expectation) and the new file FAILS (route/import missing); `node --test shell/app/ocr/client/tests/screens_entry.test.mjs` → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# shell/app/overlay/middleware.py — MODIFIED (only the tag constants and inject() body change;
# the OverlayMiddleware class and _INJECT_PATHS are untouched)
SCRIPT_TAG = b'<script defer src="/shell/overlay.js"></script>'
OCR_FLOW_CSS_TAG = b'<link rel="stylesheet" href="/shell/ocr/client/ocr_flow.css">'
OCR_FLOW_SCRIPT_TAG = b'<script type="module" src="/shell/ocr/client/ocr_flow.js"></script>'
INJECTED_TAGS = SCRIPT_TAG + OCR_FLOW_CSS_TAG + OCR_FLOW_SCRIPT_TAG

_INJECT_PATHS = frozenset({"/", "/index.html"})


def inject(html: bytes) -> bytes:
    """Insert the overlay + ocr_flow tags before the LAST ``</body>`` (case-
    insensitive). No closing tag -> append (still a valid, working page)."""
    idx = html.lower().rfind(b"</body>")
    if idx == -1:
        return html + INJECTED_TAGS
    return html[:idx] + INJECTED_TAGS + html[idx:]
```

```python
# shell/app/main.py — MODIFIED, insert immediately after the _ocr_panel_router
# try/except block and BEFORE the "mount the untouched prototype app LAST" comment:
    try:
        from shell.app.ocr.panel_router import router as _ocr_panel_router
        app.include_router(_ocr_panel_router)
    except ImportError:
        pass

    # shell/app/ocr/client/ is mounted as static so the browser can `import`
    # ocr_flow.js's sibling ES modules (flow_state.mjs, panel_parser.mjs,
    # engine_tesseract.mjs) and fetch the vendored tesseract.js/WASM assets at
    # runtime — OverlayMiddleware only injects <link>/<script> TAGS for
    # ocr_flow.js/.css, it does not serve any file itself (Open Question 6).
    from pathlib import Path as _Path
    from starlette.staticfiles import StaticFiles as _StaticFiles
    _ocr_client_dir = _Path(__file__).resolve().parent / "ocr" / "client"
    app.mount("/shell/ocr/client", _StaticFiles(directory=str(_ocr_client_dir)),
              name="ocr_client_assets")

    # ---- mount the untouched prototype app LAST (so /shell/* wins) -------
```

```js
// shell/app/ocr/client/screens/entry.mjs
export function renderEntryCard() {
  return `
<section class="ocrf-entry" id="ocrfEntry">
  <button type="button" class="ocrf-cta" id="ocrfCtaScreenshots">
    <span class="ocrf-cta-emoji" aria-hidden="true">\u{1F4F7}</span> Fill from screenshots
  </button>
  <p class="ocrf-cta-note">Fastest way. No typing.</p>
</section>`.trim();
}

export function renderUpgradeNote() {
  return `
<div class="ocrf-modal-scrim" id="ocrfUpgradeScrim" aria-hidden="true" inert>
  <div class="ocrf-sheet" role="dialog" aria-modal="true" aria-labelledby="ocrfUpgradeTitle">
    <h2 id="ocrfUpgradeTitle" tabindex="-1">This needs a paid plan</h2>
    <p>Reading screenshots is a paid feature. Typing the numbers in yourself is always free.</p>
    <div class="ocrf-sheet-actions">
      <button type="button" class="ocrf-btn-ghost" id="ocrfUpgradeClose">Type it in myself</button>
      <button type="button" class="ocrf-btn-primary" id="ocrfUpgradeCta">See plans</button>
    </div>
  </div>
</div>`.trim();
}

export async function decideEntryAction(checkAccess) {
  const access = await checkAccess();
  return access.allowed ? 'proceed' : 'upgrade';
}

export function mountEntry({ root = document } = {}) {
  const statPanel = root.getElementById('statPanel');
  if (!statPanel) return null;
  const anchor = statPanel.closest('.iblock') || statPanel;
  const wrap = root.createElement('div');
  wrap.innerHTML = renderEntryCard();
  const node = wrap.firstElementChild;
  anchor.parentNode.insertBefore(node, anchor);
  return node;
}

export function wireEntry(node, { checkAccess, onProceed, onNeedsUpgrade }) {
  const button = node.querySelector('#ocrfCtaScreenshots');
  button.addEventListener('click', async () => {
    const action = await decideEntryAction(checkAccess);
    if (action === 'proceed') onProceed();
    else onNeedsUpgrade();
  });
}

export function wireUpgradeNote(node, { checkout } = {}) {
  const close = node.querySelector('#ocrfUpgradeClose');
  const cta = node.querySelector('#ocrfUpgradeCta');
  close.addEventListener('click', () => node.remove());
  cta.addEventListener('click', async () => {
    cta.disabled = true;
    cta.textContent = 'Opening…';
    try {
      const result = await (checkout ? checkout() : Promise.reject(new Error('no checkout configured')));
      if (result && result.url) { window.location.href = result.url; return; }
      throw new Error('no checkout url');
    } catch (err) {
      cta.textContent = 'Try again from the account panel';
    }
  });
}
```

```js
// shell/app/ocr/client/ocr_flow.js — bootstrap; grows by one import + one wire-up per task (6-9)
import { renderEntryCard, mountEntry, wireEntry, renderUpgradeNote, wireUpgradeNote } from './screens/entry.mjs';

function fetchMe() {
  return fetch('/shell/me', { credentials: 'same-origin' }).then((r) => r.json());
}
async function checkAccess() {
  try {
    const me = await fetchMe();
    const plan = me && me.user && me.user.plan;
    return { allowed: plan === 'pro', plan: plan || null, reachable: true };
  } catch (err) {
    return { allowed: false, plan: null, reachable: false };
  }
}
function checkout() {
  return fetch('/shell/billing/checkout', { method: 'POST', credentials: 'same-origin' })
    .then((r) => { if (!r.ok) throw new Error('checkout unavailable'); return r.json(); });
}

function showUpgradeNote() {
  const wrap = document.createElement('div');
  wrap.innerHTML = renderUpgradeNote();
  const node = wrap.firstElementChild;
  document.body.appendChild(node);
  node.removeAttribute('inert');
  node.setAttribute('aria-hidden', 'false');
  wireUpgradeNote(node, { checkout });
}

function boot() {
  const entryNode = mountEntry({ root: document });
  if (!entryNode) return;   // this page has no #statPanel — nothing to attach to
  wireEntry(entryNode, {
    checkAccess,
    onProceed: () => { /* Task 6 replaces this with "open S1" */ },
    onNeedsUpgrade: showUpgradeNote,
  });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}
```

```css
/* shell/app/ocr/client/ocr_flow.css — base tokens + Task 5's entry/upgrade styles.
   Palette-locked to prototype/DESIGN_SYSTEM.md (same tokens the mock itself uses);
   Tasks 6-9 append more rules to this file, reusing these custom properties —
   never introducing a new color. Not unit-tested (decision #6); the Task 10
   browser gate is the actual visual acceptance bar. */
:root {
  --ocrf-panel:#0B273D; --ocrf-raised:#123B59; --ocrf-well:rgba(6,20,34,.38);
  --ocrf-ink:#EAF6FF; --ocrf-ink-mute:#B9D2E5;
  --ocrf-cta-1:#8ED0FF; --ocrf-cta-2:#5AAEF3; --ocrf-cta-3:#3E97E8; --ocrf-cta-ledge:#235f9c;
  --ocrf-ice-b:#55BFFF; --ocrf-gold:#D9A94F;
}
[hidden]{display:none!important}
@media (prefers-reduced-motion:reduce){.ocrf-entry *,.ocrf-sheet *{transition:none!important;animation:none!important}}

.ocrf-entry{margin:0 0 16px;text-align:center}
.ocrf-cta{font-family:'Chakra Petch',system-ui,sans-serif;font-weight:700;font-size:15px;color:#fff;
  text-shadow:0 1px 2px rgba(10,52,96,.55);border:0;border-radius:16px;cursor:pointer;
  padding:14px 22px;min-height:48px;display:inline-flex;align-items:center;gap:8px;
  background:linear-gradient(180deg,var(--ocrf-cta-1) 0%,var(--ocrf-cta-2) 46%,var(--ocrf-cta-3) 100%);
  box-shadow:inset 0 2px 1px rgba(255,255,255,.65),inset 0 -2px 1px rgba(20,96,170,.45),
    0 2px 0 var(--ocrf-cta-ledge),0 3px 5px -2px rgba(4,22,44,.7)}
.ocrf-cta-note{font-size:11.5px;color:var(--ocrf-ink-mute);margin:8px 0 0}

.ocrf-modal-scrim{position:fixed;inset:0;background:rgba(4,10,17,.62);display:flex;align-items:center;
  justify-content:center;z-index:2147483000;padding:20px}
.ocrf-modal-scrim[aria-hidden="true"]{display:none}
.ocrf-sheet{max-width:420px;background:linear-gradient(180deg,var(--ocrf-raised),var(--ocrf-panel));
  border-radius:16px;padding:22px;color:var(--ocrf-ink);box-shadow:0 18px 40px -24px rgba(0,0,0,.9)}
.ocrf-sheet h2{font-family:'Chakra Petch',system-ui,sans-serif;margin:0 0 10px;font-size:17px}
.ocrf-sheet p{margin:0 0 16px;font-size:13.5px;color:var(--ocrf-ink-mute);line-height:1.5}
.ocrf-sheet-actions{display:flex;gap:10px}
.ocrf-btn-ghost,.ocrf-btn-primary{min-height:44px;border-radius:12px;font-weight:600;font-size:13px;
  cursor:pointer;flex:1;padding:0 12px}
.ocrf-btn-ghost{background:rgba(255,255,255,.04);border:1px solid rgba(185,210,229,.28);color:var(--ocrf-ink)}
.ocrf-btn-primary{border:0;color:#fff;background:linear-gradient(180deg,var(--ocrf-cta-1),var(--ocrf-cta-3))}
```

- [ ] **Step 4: Run to verify all pass** — `py -m pytest shell/tests/test_overlay_inject.py shell/tests/test_overlay_ocr_client_assets.py -q` → all pass; `node --test shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs shell/app/ocr/client/tests/error_copy.test.mjs shell/app/ocr/client/tests/controller.test.mjs shell/app/ocr/client/tests/screens_entry.test.mjs` → all pass. Also re-run the FULL existing suite once (`py -m pytest shell/tests -q`) to confirm nothing else depended on the old single-tag injection shape.
- [ ] **Step 5: Commit** — `git add shell/app/overlay/middleware.py shell/app/main.py shell/tests/test_overlay_inject.py shell/tests/test_overlay_ocr_client_assets.py shell/app/ocr/client/screens/entry.mjs shell/app/ocr/client/tests/screens_entry.test.mjs shell/app/ocr/client/ocr_flow.js shell/app/ocr/client/ocr_flow.css && git commit -m "ocr: entry seam — inject+serve ocr_flow, S0 CTA above #statPanel, free-tier gate"`

---

### Task 6: S1 + S2 + E1 — pick a kind, add screenshots, recover from a bad one

**Files:** Create `shell/app/ocr/client/screens/pick_upload.mjs`, `shell/app/ocr/client/tests/screens_pick_upload.test.mjs`; append to `ocr_flow.js`/`ocr_flow.css`

**Copy source:** `prototype/mocks/ocr_flow_mock.html` lines ~696–865 (S1/S2/E1 markup) and its JS (`renderTagMenuOptions`, `chooseType`, `updateS2Continue`, `E1_TEXT`, `dzLabel`) — reused verbatim below, with one deliberate adaptation: the mock's E1 "partial" heading is a hardcoded demo string (`"We read 15 of 24 numbers"`); this build computes it from the real unreadable-field count (`renderE1('partial', {readCount, totalCount})`), since 15/24 was never anything but that demo's own canned data.

**A finding from the mock worth acting on, not copying:** per the mock's own code comment ("The single-zone 'Battle mode' collapse/expand design ... is DELETED ... type changes never touch uploads, so no confirm is needed here at all"), **nothing in S2 actually triggers a discard-confirmation** — picking a different type for a side never clears its uploads. This plan does not build a confirm dialog for type-switching; the "any action that would discard an upload confirms first" principle (global constraints) is honored by Reset (Task 8) and E1's own explicit, always-shown notice (below) instead.

**Interfaces — Consumes:** `flow_state.mjs`'s `TYPES = ['battle','scout','citystats']` vocabulary (this task uses that vocabulary throughout — **not** the mock's internal `'city'` shorthand). **Produces**, pure/string-testable:
- `renderS1()`, `renderS2({types, coverage, shots})`, `renderE1(variant, {readCount, totalCount})`.
- `TYPE_LABEL`, `YOU_TYPES`, `ENEMY_TYPES` — the real `flow_state.mjs` type set, labeled for display.
- `dropzoneLabel({side, covered})`, `computeS2ContinueState(coverage)` — the exact copy/enable-state decisions, pulled out of the templates so they're unit-testable without parsing HTML.
Thin (DOM-wired, exercised by the Task 10 browser gate): `wireS1`, `wireS2`, `wireE1`.

- [ ] **Step 1: Write the failing tests**

```js
// shell/app/ocr/client/tests/screens_pick_upload.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  renderS1, renderS2, renderE1, dropzoneLabel, computeS2ContinueState, TYPE_LABEL,
} from '../screens/pick_upload.mjs';

test('S1 uses the real flow_state type vocabulary and the mock copy verbatim', () => {
  const html = renderS1();
  assert.match(html, /Which screenshot do you have\?/);
  assert.match(html, /data-pick-type="battle"/);
  assert.match(html, /data-pick-type="scout"/);
  assert.match(html, /data-pick-type="citystats"/);   // NOT "city" — flow_state's real vocabulary
  assert.match(html, /BEST · FILLS BOTH SIDES/);
  assert.match(html, /Shows your stats and the enemy's stats together\./);
  assert.match(html, /called Bonus Overview in the game/);
  assert.doesNotMatch(html, /\bpicture\b/i);
});

test('dropzoneLabel matches the mock exactly for all three states', () => {
  assert.equal(dropzoneLabel({ side: 'you', covered: false }), 'Tap to add your screenshot');
  assert.equal(dropzoneLabel({ side: 'enemy', covered: false }), "Tap to add the enemy's screenshot");
  assert.equal(dropzoneLabel({ side: 'you', covered: true }), 'Add your own screenshot instead');
  assert.equal(dropzoneLabel({ side: 'enemy', covered: true }), 'Add your own screenshot instead');
});

test('computeS2ContinueState matches updateS2Continue exactly, all four branches', () => {
  assert.deepEqual(computeS2ContinueState({ you: true, enemy: true }), { disabled: false, hint: null });
  assert.deepEqual(computeS2ContinueState({ you: true, enemy: false }),
    { disabled: true, hint: "Now add the enemy's screenshot." });
  assert.deepEqual(computeS2ContinueState({ you: false, enemy: true }),
    { disabled: true, hint: 'Now add your screenshot.' });
  assert.deepEqual(computeS2ContinueState({ you: false, enemy: false }),
    { disabled: true, hint: 'Add a screenshot to continue' });
});

test('S2 renders both sides, the always-on hint card, and reflects Continue state', () => {
  const html = renderS2({
    types: { you: 'battle', enemy: 'battle' },
    coverage: { you: true, enemy: true },
    shots: { you: ['shot1'], enemy: [] },
  });
  assert.match(html, /Add your screenshots/);
  assert.match(html, /data-side="you"/);
  assert.match(html, /data-side="enemy"/);
  assert.match(html, /Long list\? Take 2 screenshots that share a row\. We'll join them\./);
  assert.match(html, /Covered by your battle report/);   // enemy has no shots of its own but battle covers it
  assert.doesNotMatch(html, /disabled/);                 // both covered -> Continue enabled
});

test('S2 disables Continue and shows the hint when only one side is covered', () => {
  const html = renderS2({
    types: { you: 'scout', enemy: 'scout' },
    coverage: { you: true, enemy: false },
    shots: { you: ['shot1'], enemy: [] },
  });
  assert.match(html, /disabled/);
  assert.match(html, /Now add the enemy's screenshot\./);
});

test('E1 "wrong" uses the mock copy verbatim', () => {
  const html = renderE1('wrong');
  assert.match(html, /That doesn't look like the right screenshot/);
  assert.match(html, /This looks like a different screen/);
  assert.match(html, />Type them in myself</);
  assert.match(html, /Add a clearer screenshot/);
});

test('E1 "partial" computes its heading from the real count, never a hardcoded demo number', () => {
  const html = renderE1('partial', { readCount: 9, totalCount: 24 });
  assert.match(html, /We read 9 of 24 numbers/);
  assert.match(html, />Type the missing numbers</);
  const other = renderE1('partial', { readCount: 20, totalCount: 24 });
  assert.match(other, /We read 20 of 24 numbers/);
});

test('TYPE_LABEL covers exactly the three real panel types', () => {
  assert.deepEqual(TYPE_LABEL, { battle: 'Battle Report', scout: 'Scout Report', citystats: 'City Stats' });
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test shell/app/ocr/client/tests/screens_pick_upload.test.mjs` → FAIL (module missing).

- [ ] **Step 3: Implement**

```js
// shell/app/ocr/client/screens/pick_upload.mjs
export const TYPE_LABEL = { battle: 'Battle Report', scout: 'Scout Report', citystats: 'City Stats' };
export const YOU_TYPES = ['citystats', 'scout', 'battle'];
export const ENEMY_TYPES = ['scout', 'battle'];

export function dropzoneLabel({ side, covered }) {
  if (covered) return 'Add your own screenshot instead';
  return side === 'you' ? 'Tap to add your screenshot' : "Tap to add the enemy's screenshot";
}

export function computeS2ContinueState(coverage) {
  if (coverage.you && coverage.enemy) return { disabled: false, hint: null };
  if (coverage.you) return { disabled: true, hint: "Now add the enemy's screenshot." };
  if (coverage.enemy) return { disabled: true, hint: 'Now add your screenshot.' };
  return { disabled: true, hint: 'Add a screenshot to continue' };
}

export function renderS1() {
  return `
<section class="screen" data-screen="s1">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">Which screenshot do you have?</h1></header>
  <div class="ocrf-scr-body">
    <p class="ocrf-sub">Pick the one that matches your screenshot.</p>
    <button type="button" class="ocrf-pick-card ocrf-promoted" data-pick-type="battle"
      aria-label="Battle Report — best, fills both sides at once">
      <span class="ocrf-ribbon">BEST &middot; FILLS BOTH SIDES</span>
      <h2>Battle Report</h2>
      <p>Shows your stats and the enemy's stats together.</p>
      <span class="ocrf-crumb">Mail &rarr; Battle Report &rarr; Stat Bonuses</span>
    </button>
    <button type="button" class="ocrf-pick-card" data-pick-type="scout"
      aria-label="Scout Report — shows one side's stats">
      <h2>Scout Report</h2>
      <p>Shows one side's stats. Yours or the enemy's.</p>
      <span class="ocrf-crumb">Scout &rarr; Report &rarr; Stat Bonuses</span>
    </button>
    <button type="button" class="ocrf-pick-card ocrf-muted" data-pick-type="citystats"
      aria-label="City Stats — advanced, needs one-time setup">
      <span class="ocrf-tag">ADVANCED</span>
      <h2>City Stats<span class="ocrf-h2-sub">(called Bonus Overview in the game)</span></h2>
      <p>Your own city's stats. Needs a quick one-time setup.</p>
      <span class="ocrf-crumb">City &rarr; Bonuses &rarr; Overview</span>
    </button>
  </div>
</section>`.trim();
}

function sideSectionHtml(side, { type, covered, shotCount }) {
  const label = side === 'you' ? 'YOU' : 'ENEMY';
  const coveredNote = covered
    ? '<div class="ocrf-covered-note"><span class="ocrf-covered-check" aria-hidden="true">&#10003;</span>'
      + 'Covered by your battle report</div>'
    : '';
  const subLabel = covered ? '' : '<span>or paste it here</span>';
  return `
<div class="ocrf-side-section ocrf-side-${side}${covered ? ' ocrf-covered' : ''}" data-side="${side}">
  <div class="ocrf-side-head">
    <span class="ocrf-side-label">${label}</span>
    <button type="button" class="ocrf-type-tag" data-type-tag="${side}" aria-haspopup="menu">${TYPE_LABEL[type]} &#9662;</button>
  </div>
  ${coveredNote}
  <button type="button" class="ocrf-dropzone${covered ? ' ocrf-dropzone--muted' : ''}" data-dropzone="${side}">
    <b>${dropzoneLabel({ side, covered })}</b>
    ${subLabel}
  </button>
  <div class="ocrf-thumbs" data-thumbs="${side}"${shotCount ? '' : ' hidden'}></div>
</div>`.trim();
}

export function renderS2({ types, coverage, shots = { you: [], enemy: [] } }) {
  const you = sideSectionHtml('you',
    { type: types.you, covered: coverage.you && !shots.you.length, shotCount: shots.you.length });
  const enemy = sideSectionHtml('enemy',
    { type: types.enemy, covered: coverage.enemy && !shots.enemy.length, shotCount: shots.enemy.length });
  const state = computeS2ContinueState(coverage);
  return `
<section class="screen" data-screen="s2">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">Add your screenshots</h1></header>
  <div class="ocrf-scr-body">
    <div class="ocrf-s2-sides">${you}${enemy}</div>
    <div class="ocrf-hint-card"><span aria-hidden="true">&#128161;</span>
      <p>Long list? Take 2 screenshots that share a row. We'll join them.</p></div>
  </div>
  <footer class="ocrf-scr-foot">
    <button type="button" class="ocrf-btn-primary ocrf-btn-block" id="ocrfS2Continue"${state.disabled ? ' disabled' : ''}>Continue</button>
    ${state.hint ? `<p class="ocrf-foot-note">${state.hint}</p>` : ''}
  </footer>
</section>`.trim();
}

function e1PartialCopy(readCount, totalCount) {
  return {
    heading: `We read ${readCount} of ${totalCount} numbers`,
    body: 'The rest were too unclear to read. Add a clearer screenshot, or type them in yourself.',
    secondary: 'Type the missing numbers',
  };
}
const E1_WRONG_COPY = {
  heading: "That doesn't look like the right screenshot",
  body: 'This looks like a different screen. We need one with a numbers list, like this:',
  secondary: 'Type them in myself',
};

export function renderE1(variant, { readCount = 0, totalCount = 24 } = {}) {
  const copy = variant === 'partial' ? e1PartialCopy(readCount, totalCount) : E1_WRONG_COPY;
  return `
<section class="screen" data-screen="e1">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1" id="ocrfE1Heading">${copy.heading}</h1></header>
  <div class="ocrf-scr-body">
    <div class="ocrf-err-icon" aria-hidden="true">&#128269;</div>
    <p class="ocrf-sub" id="ocrfE1Body">${copy.body}</p>
    <p class="ocrf-fix-caption">A good example:</p>
    <div class="ocrf-e1-actions">
      <button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s2" data-recovery="1">
        <span aria-hidden="true">&#128247;</span> Add a clearer screenshot
      </button>
      <button type="button" class="ocrf-btn-ghost ocrf-btn-block" id="ocrfE1Secondary"
        data-goto="s4" data-show-missing="1">${copy.secondary}</button>
    </div>
  </div>
</section>`.trim();
}

/* ---- thin DOM wiring below: exercised by the Task 10 browser gate, not node:test ---- */

export function wireS1(root, { onPick }) {
  root.querySelectorAll('[data-pick-type]').forEach((card) => {
    card.addEventListener('click', () => onPick(card.dataset.pickType));
  });
}

export function wireS2(root, { onDropzone, onTypeTag, onContinue }) {
  root.querySelectorAll('[data-dropzone]').forEach((zone) => {
    zone.addEventListener('click', () => onDropzone(zone.dataset.dropzone));
  });
  root.querySelectorAll('[data-type-tag]').forEach((tag) => {
    tag.addEventListener('click', () => onTypeTag(tag.dataset.typeTag, tag));
  });
  const continueBtn = root.querySelector('#ocrfS2Continue');
  if (continueBtn) continueBtn.addEventListener('click', () => { if (!continueBtn.disabled) onContinue(); });
}

export function wireE1(root, { onRetake, onTypeMissing }) {
  root.querySelector('[data-recovery="1"]')?.addEventListener('click', onRetake);
  root.querySelector('#ocrfE1Secondary')?.addEventListener('click', onTypeMissing);
}
```

- [ ] **Step 4: Run to verify all pass** — `node --test shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs shell/app/ocr/client/tests/error_copy.test.mjs shell/app/ocr/client/tests/controller.test.mjs shell/app/ocr/client/tests/screens_entry.test.mjs shell/app/ocr/client/tests/screens_pick_upload.test.mjs` → all passed.
- [ ] **Step 5: Commit** — `git add shell/app/ocr/client/screens/pick_upload.mjs shell/app/ocr/client/tests/screens_pick_upload.test.mjs && git commit -m "ocr: S1/S2/E1 screens (pick kind, add screenshots, recovery)"`

---

### Task 7: PREP + S3 — the reading/scanning driver

**Files:** Create `shell/app/ocr/client/screens/reading.mjs`, `shell/app/ocr/client/tests/screens_reading.test.mjs`; append to `ocr_flow.js`/`ocr_flow.css`

**The mock's S3 is scripted (fixed 850/1700/2600/2900ms timers, unconditionally reaches S4 — its own code comment: "S3 scanning (always -&gt; s4; error states are Flow-Map-only)").** That works for a demo with no backend. This build's S3 drives real, variable-latency work (`controller.readAll`, Open Question 1's client-then-server chain), so the step choreography can't be a fixed schedule — `driveScan` (below) advances the same three step labels on a timer **while real work is in flight**, jumps straight to "done" the moment the real promise resolves (however long that took), and supports a **real Cancel** that discards whatever the in-flight read eventually returns (QA row **F1**). One copy adaptation from the mock, for the same reason as Task 6's E1 partial-count fix: the trust line changes from the mock's unconditional *"Your screenshot stays on your phone. We read it right here."* to **"We try to read this right here on your phone first."** — an honest statement of intent rather than a claim that would become false the moment `docs/OCR_QA_PLAN.md` §5 row **F8**'s described server-fallback actually fires.

**Interfaces — Consumes:** a `run()` function returning the in-flight promise (the caller wires this to `controller.readAll(...)`, Task 4). **Produces:**
- `SCAN_STEPS` — the three narration strings, reused verbatim from the mock.
- `driveScan({ run, onStepChange, onDone, onError, stepIntervalMs }) -> { cancel() }` — pure timer/promise orchestration (fake-timers-tested, no DOM): calls `onStepChange(0)` immediately, advances (capped at the last index) every `stepIntervalMs` while `run()` is pending, calls `onStepChange(lastIndex)` then `onDone(result)` on resolve, `onError(err)` on reject; `cancel()` stops the interval and suppresses whichever of `onDone`/`onError` would otherwise still fire.
- `renderPrep()`, `renderS3()` — pure templates.
Thin (DOM, browser-gate only): `applyStepClasses(root, activeIndex)`, `wireS3(root, {onCancel})`.

- [ ] **Step 1: Write the failing tests**

```js
// shell/app/ocr/client/tests/screens_reading.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { driveScan, SCAN_STEPS, renderPrep, renderS3 } from '../screens/reading.mjs';

test('driveScan advances steps on a timer while real work is pending, then completes on resolve', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval', 'clearInterval'] });
  const steps = [];
  let resolveRun;
  const run = () => new Promise((resolve) => { resolveRun = resolve; });
  let done = null;
  driveScan({ run, onStepChange: (s) => steps.push(s), onDone: (r) => { done = r; }, onError: () => {}, stepIntervalMs: 900 });

  assert.deepEqual(steps, [0]);
  t.mock.timers.tick(900);
  assert.deepEqual(steps, [0, 1]);
  t.mock.timers.tick(900);
  assert.deepEqual(steps, [0, 1, 2]);
  t.mock.timers.tick(900);              // caps at the last step — never runs off the end of SCAN_STEPS
  assert.deepEqual(steps, [0, 1, 2, 2]);

  resolveRun({ status: 'ok' });
  await Promise.resolve(); await Promise.resolve();
  assert.deepEqual(done, { status: 'ok' });
  assert.deepEqual(steps, [0, 1, 2, 2, 2]);   // onDone force-sets the final step too
});

test('driveScan resolves fast work immediately, without waiting out the schedule', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval', 'clearInterval'] });
  const steps = [];
  let done = null;
  driveScan({
    run: () => Promise.resolve({ status: 'ok' }),
    onStepChange: (s) => steps.push(s), onDone: (r) => { done = r; }, onError: () => {},
    stepIntervalMs: 900,
  });
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  assert.deepEqual(done, { status: 'ok' });
  assert.deepEqual(steps, [0, 2]);   // never advanced through step 1 — the work finished first
});

test('driveScan calls onError on rejection, never onDone', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval', 'clearInterval'] });
  let rejectRun;
  const run = () => new Promise((_resolve, reject) => { rejectRun = reject; });
  let error = null;
  let doneCalls = 0;
  driveScan({ run, onStepChange: () => {}, onDone: () => { doneCalls += 1; }, onError: (e) => { error = e; }, stepIntervalMs: 900 });
  rejectRun(new Error('engine crashed'));
  await Promise.resolve(); await Promise.resolve();
  assert.equal(error.message, 'engine crashed');
  assert.equal(doneCalls, 0);
});

test('driveScan.cancel() suppresses the eventual onDone and stops advancing (QA row F1)', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval', 'clearInterval'] });
  let resolveRun;
  const run = () => new Promise((resolve) => { resolveRun = resolve; });
  const steps = [];
  let done = null;
  const handle = driveScan({ run, onStepChange: (s) => steps.push(s), onDone: (r) => { done = r; }, onError: () => {}, stepIntervalMs: 900 });
  t.mock.timers.tick(900);
  handle.cancel();
  t.mock.timers.tick(900);              // no further advancement after cancel
  resolveRun({ status: 'ok' });         // the abandoned work finishes anyway — must be ignored
  await Promise.resolve(); await Promise.resolve();
  assert.equal(done, null);
  assert.deepEqual(steps, [0, 1]);
});

test('S3 renders the three narration steps and the honest (non-absolute) trust line', () => {
  const html = renderS3();
  assert.match(html, /Reading your screenshot/);
  for (const step of SCAN_STEPS) assert.ok(html.includes(step), step);
  assert.match(html, /We try to read this right here on your phone first\./);
  assert.doesNotMatch(html, /stays on your phone\. We read it right here\./);   // the overclaim, specifically absent
  assert.match(html, /id="ocrfScanCancel"/);
});

test('PREP screen matches the mock copy and is clearly one-time-only in tone', () => {
  const html = renderPrep();
  assert.match(html, /Getting ready/);
  assert.match(html, /First time only\. Just a few seconds\./);
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test shell/app/ocr/client/tests/screens_reading.test.mjs` → FAIL (module missing).

- [ ] **Step 3: Implement**

```js
// shell/app/ocr/client/screens/reading.mjs
export const SCAN_STEPS = ['Reading the numbers…', 'Matching the labels…', 'Checking both sides…'];
const DEFAULT_STEP_INTERVAL_MS = 900;

export function driveScan({ run, onStepChange, onDone, onError, stepIntervalMs = DEFAULT_STEP_INTERVAL_MS }) {
  let step = 0;
  let cancelled = false;
  onStepChange(step);
  const timer = setInterval(() => {
    if (cancelled) return;
    step = Math.min(step + 1, SCAN_STEPS.length - 1);
    onStepChange(step);
  }, stepIntervalMs);

  run().then(
    (result) => {
      clearInterval(timer);
      if (cancelled) return;
      onStepChange(SCAN_STEPS.length - 1);
      onDone(result);
    },
    (err) => {
      clearInterval(timer);
      if (cancelled) return;
      onError(err);
    },
  );

  return { cancel: () => { cancelled = true; clearInterval(timer); } };
}

export function renderPrep() {
  return `
<section class="screen" data-screen="prep">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <span class="ocrf-scr-head-eyebrow">Setup</span></header>
  <div class="ocrf-scr-body ocrf-prep-body">
    <div class="ocrf-prep-ring" aria-hidden="true"></div>
    <h1 tabindex="-1">Getting ready&hellip;</h1>
    <p class="ocrf-sub">First time only. Just a few seconds.</p>
  </div>
</section>`.trim();
}

export function renderS3() {
  const steps = SCAN_STEPS
    .map((label, i) => `<li class="ocrf-scan-step" data-step="${i}"><span class="ocrf-step-ic" aria-hidden="true"></span>${label}</li>`)
    .join('');
  return `
<section class="screen" data-screen="s3">
  <div class="ocrf-scr-body ocrf-scan-body">
    <h1 tabindex="-1">Reading your screenshot&hellip;</h1>
    <div class="ocrf-scan-track"><div class="ocrf-scan-fill" id="ocrfScanFill"></div></div>
    <ul class="ocrf-scan-steps" id="ocrfScanSteps">${steps}</ul>
    <p class="ocrf-trust-line">We try to read this right here on your phone first.</p>
  </div>
  <footer class="ocrf-scr-foot ocrf-scr-foot-ghost">
    <button type="button" class="ocrf-btn-ghost ocrf-btn-block" id="ocrfScanCancel">Cancel</button>
  </footer>
</section>`.trim();
}

/* ---- thin DOM wiring below: exercised by the Task 10 browser gate, not node:test ---- */

export function applyStepClasses(root, activeIndex) {
  root.querySelectorAll('.ocrf-scan-step').forEach((li) => {
    const i = Number(li.dataset.step);
    li.classList.toggle('ocrf-active', i === activeIndex);
    li.classList.toggle('ocrf-done', i < activeIndex);
  });
}

export function wireS3(root, { onCancel }) {
  root.querySelector('#ocrfScanCancel')?.addEventListener('click', onCancel);
}
```

- [ ] **Step 4: Run to verify all pass** — `node --test shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs shell/app/ocr/client/tests/error_copy.test.mjs shell/app/ocr/client/tests/controller.test.mjs shell/app/ocr/client/tests/screens_entry.test.mjs shell/app/ocr/client/tests/screens_pick_upload.test.mjs shell/app/ocr/client/tests/screens_reading.test.mjs` → all passed.
- [ ] **Step 5: Commit** — `git add shell/app/ocr/client/screens/reading.mjs shell/app/ocr/client/tests/screens_reading.test.mjs && git commit -m "ocr: PREP+S3 reading driver — real-work-driven steps, real cancel"`

---

### Task 8: S4 — check your numbers (review grid, editor, screenshot viewer, Reset)

**Files:** Create `shell/app/ocr/client/screens/review.mjs`, `shell/app/ocr/client/tests/screens_review.test.mjs`; append to `ocr_flow.js`/`ocr_flow.css`

**This is the one screen with no real-app equivalent to reuse** (S5, Task 9, reuses `prototype/index.html`'s own components — S4 does not exist there at all), so it is built fresh from the mock's markup/copy (lines ~774–787, ~866–893) and JS (`fieldState`, `displayVal`, `buildField`, `updateTallyFor`, `openEditor`, `saveEditor`, `renderPictureView`, `handleReset`), reused verbatim **except** where the mock's own data is scripted-demo-only:
- The mock's `fieldState(id)` gates `MISSING_FIELDS` behind a `state.showMissing` flag that is only ever `true` via the E1 recovery exit — that flag existed purely so ONE demo could show both a normal run and a "some fields missing" run without two datasets. This build has no such flag: a field is `missing` **whenever the real data says so** (Task 2's `classifyFields`), full stop, on every run.
- The mock's `CHECK_FIELDS` dict carries an unused `.note` field ("Glare on the screen made this one hard to read.") that is **never read anywhere in the mock's own code** (confirmed by the research pass) — and the real API has no per-field "why" text to source one from anyway (`unreadable_fields` is bare string keys). This build does not invent that feature.

**Interfaces — Consumes:** Task 2's `classifyFields`/`ALL_FIELD_KEYS`/`FIELD_OK`/`FIELD_CHECK`/`FIELD_MISSING`. **Produces**, pure/tested:
- `fieldRenderState({classification, savedValue})` — a user-typed value always wins and always reads as `ok`, matching the mock's `fieldState` priority exactly (`state.savedValues.hasOwnProperty(id)` is checked first, before anything else).
- `provenanceText({state, typed})` — the three exact aria-label strings from the mock.
- `computeTally(states)` — the exact tally copy/percentages from `updateTallyFor`, including its specific rounding order (`checkPct`/`missPct` rounded independently, `okPct` is the *remainder* — this is what guarantees the three bar segments always sum to exactly 100, not an approximation).
- `validateEditorInput(raw)` — the exact regex/range/messages from `saveEditor` (0–6000 inclusive, matches `service.py`'s `CLASS_VALUE_MIN`/`CLASS_VALUE_MAX` exactly — S4 never shows specials, so no second range is needed here, see the plan header's landmine note).
- `editorContentFor({side, key, fieldState})` — the exact title/crop/help copy from `openEditor`.
- `nextResetState(current)` — the two-step confirm's pure transition (`'idle' → 'confirming'`, `'confirming' → 'idle'` + `shouldClear: true`), the 3-second auto-revert timer itself is thin/DOM.
- `renderReviewGrid(states)`, `renderS4({states, tally})`, `renderEditorSheet()`, `renderPictureView(states)` — pure templates. `renderReviewGrid` and `renderPictureView` are proven, by a shared test, to read the identical `states` source (the mock's own "grid and screenshot-view derive from the same field-state source" rule, enforced by construction here rather than by convention).

- [ ] **Step 1: Write the failing tests**

```js
// shell/app/ocr/client/tests/screens_review.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  fieldRenderState, provenanceText, computeTally, validateEditorInput, editorContentFor,
  nextResetState, renderReviewGrid, renderS4, renderPictureView,
} from '../screens/review.mjs';
import { FIELD_OK, FIELD_CHECK, FIELD_MISSING } from '../fill_mapper.mjs';

test('a typed value always wins and always reads ok, even over a check/missing classification', () => {
  const overCheck = fieldRenderState({ classification: { state: FIELD_CHECK, value: 300.6, conf: 0.6 }, savedValue: 350.0 });
  assert.deepEqual(overCheck, { state: 'ok', value: 350.0, typed: true });
  const overMissing = fieldRenderState({ classification: { state: FIELD_MISSING, value: null, conf: null }, savedValue: 12.0 });
  assert.deepEqual(overMissing, { state: 'ok', value: 12.0, typed: true });
  const untouched = fieldRenderState({ classification: { state: FIELD_OK, value: 4491.6, conf: 0.99 }, savedValue: undefined });
  assert.deepEqual(untouched, { state: 'ok', value: 4491.6, typed: false });
});

test('provenanceText matches the mock exactly, all three states', () => {
  assert.equal(provenanceText({ state: 'missing', typed: false }), 'Not read yet. Tap to type it.');
  assert.equal(provenanceText({ state: 'ok', typed: true }), 'You typed this.');
  assert.equal(provenanceText({ state: 'ok', typed: false }), 'Read from your screenshot.');
  assert.equal(provenanceText({ state: 'check', typed: false }), 'Read from your screenshot.');
});

test('computeTally: all clean', () => {
  const t = computeTally(Array(24).fill('ok'));
  assert.equal(t.statusText, 'All 24 numbers are in.');
  assert.equal(t.clear, true);
  assert.equal(t.okPct + t.checkPct + t.missPct, 100);
});

test('computeTally: mixed, exact copy and percentages that always sum to 100', () => {
  const states = [...Array(18).fill('ok'), ...Array(3).fill('check'), ...Array(3).fill('missing')];
  const t = computeTally(states);
  assert.equal(t.statusText, '18 of 24 read well · 3 to check · 3 still empty');
  assert.equal(t.okCount, 18); assert.equal(t.checkCount, 3); assert.equal(t.missingCount, 3);
  assert.equal(t.okPct + t.checkPct + t.missPct, 100);
});

test('computeTally: ok+check only, and ok+missing only (no "0 to check"/"0 still empty" ever shown)', () => {
  const checkOnly = computeTally([...Array(20).fill('ok'), ...Array(4).fill('check')]);
  assert.equal(checkOnly.statusText, '20 of 24 read well · 4 to check');
  const missingOnly = computeTally([...Array(22).fill('ok'), ...Array(2).fill('missing')]);
  assert.equal(missingOnly.statusText, '22 of 24 read well · 2 still empty');
});

test('validateEditorInput matches saveEditor exactly: empty is a silent no-op, bad format and out-of-range have distinct messages', () => {
  assert.deepEqual(validateEditorInput(''), { ok: false, empty: true });
  assert.deepEqual(validateEditorInput('   '), { ok: false, empty: true });
  assert.equal(validateEditorInput('abc').message, 'That needs to be a number.');
  assert.equal(validateEditorInput('12.').message, 'That needs to be a number.');
  assert.equal(validateEditorInput('.5').message, 'That needs to be a number.');
  assert.equal(validateEditorInput('-1').message, 'Numbers here are usually between 0 and 6000.');
  assert.equal(validateEditorInput('6000.01').message, 'Numbers here are usually between 0 and 6000.');
  assert.deepEqual(validateEditorInput('0'), { ok: true, value: 0 });       // inclusive lower bound
  assert.deepEqual(validateEditorInput('6000'), { ok: true, value: 6000 }); // inclusive upper bound
  assert.deepEqual(validateEditorInput('4491.6'), { ok: true, value: 4491.6 });
});

test('editorContentFor: missing vs present copy, exact strings', () => {
  const missing = editorContentFor({ side: 'enemy', key: 'Marksman|Attack', fieldState: { state: 'missing', value: null, typed: false } });
  assert.equal(missing.title, 'Enemy · Marksman · Attack');
  assert.equal(missing.cropTag, 'NOT CAPTURED');
  assert.equal(missing.cropBody, 'This part of the screenshot was not captured.');
  assert.equal(missing.inputValue, '');
  assert.equal(missing.help, "We couldn't read this one. Type the number.");

  const present = editorContentFor({ side: 'you', key: 'Infantry|Attack', fieldState: { state: 'ok', value: 4491.6, typed: false } });
  assert.equal(present.title, 'My side · Infantry · Attack');
  assert.equal(present.cropTag, 'WHAT WE SAW');
  assert.equal(present.inputValue, '4491.6');
  assert.equal(present.help, 'Type over the number if it needs fixing.');
});

test('nextResetState is a clean two-step transition', () => {
  assert.deepEqual(nextResetState('idle'), { state: 'confirming', label: 'Really reset?', shouldClear: false });
  assert.deepEqual(nextResetState('confirming'), { state: 'idle', label: 'Reset', shouldClear: true });
});

function fullStates(overrides = {}) {
  const keys = ['Infantry|Attack', 'Infantry|Defense', 'Infantry|Lethality', 'Infantry|Health',
    'Lancer|Attack', 'Lancer|Defense', 'Lancer|Lethality', 'Lancer|Health',
    'Marksman|Attack', 'Marksman|Defense', 'Marksman|Lethality', 'Marksman|Health'];
  const side = () => Object.fromEntries(keys.map((k) => [k, { state: 'ok', value: 100.0, typed: false }]));
  const states = { you: side(), enemy: side() };
  for (const [path, value] of Object.entries(overrides)) {
    const [s, k] = path.split('.');
    states[s][k] = value;
  }
  return states;
}

test('renderReviewGrid shows both columns, correct icons, and the exact missing placeholder', () => {
  const states = fullStates({ 'enemy.Marksman|Attack': { state: 'missing', value: null, typed: false } });
  const html = renderReviewGrid(states);
  assert.match(html, /MY SIDE/);
  assert.match(html, />ENEMY</);
  assert.match(html, /— —/);              // the missing placeholder, verbatim
  assert.match(html, /Not read yet\. Tap to type it\./);
});

test('renderReviewGrid and renderPictureView derive from the identical states object (cannot disagree)', () => {
  const states = fullStates({ 'you.Infantry|Attack': { state: 'ok', value: 4491.6, typed: true } });
  const grid = renderReviewGrid(states);
  const picture = renderPictureView(states);
  assert.match(grid, /4491\.6/);
  assert.match(picture, /\+4491\.6/);      // picture view prefixes a "+", grid does not — same underlying value either way
});

test('S4 assembles the grid inside the full screen shell with Next always enabled', () => {
  const states = fullStates();
  const html = renderS4({ states, tally: computeTally(Array(24).fill('ok')) });
  assert.match(html, /Check your numbers/);
  assert.match(html, /See my screenshot/);
  assert.doesNotMatch(html, /data-goto="s5"[^>]*disabled/);   // Next is never conditionally disabled
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test shell/app/ocr/client/tests/screens_review.test.mjs` → FAIL (module missing).

- [ ] **Step 3: Implement**

```js
// shell/app/ocr/client/screens/review.mjs
const CLASSES = ['Infantry', 'Lancer', 'Marksman'];
const STATS = ['Attack', 'Defense', 'Lethality', 'Health'];
const SIDE_NAME = { you: 'My side', enemy: 'Enemy' };
const STATE_ICON = { ok: '&#10003;', check: '!', missing: '+' };

export function fieldRenderState({ classification, savedValue }) {
  if (savedValue !== undefined && savedValue !== null) {
    return { state: 'ok', value: savedValue, typed: true };
  }
  return { state: classification.state, value: classification.value, typed: false };
}

export function provenanceText({ state, typed }) {
  if (state === 'missing') return 'Not read yet. Tap to type it.';
  return typed ? 'You typed this.' : 'Read from your screenshot.';
}

export function computeTally(states) {
  const total = states.length;
  const checkCount = states.filter((s) => s === 'check').length;
  const missingCount = states.filter((s) => s === 'missing').length;
  const okCount = total - checkCount - missingCount;
  if (checkCount === 0 && missingCount === 0) {
    return { okCount, checkCount, missingCount, total, clear: true,
      statusText: `All ${total} numbers are in.`, okPct: 100, checkPct: 0, missPct: 0 };
  }
  const checkPct = Math.round((checkCount / total) * 100);
  const missPct = Math.round((missingCount / total) * 100);
  const okPct = 100 - checkPct - missPct;   // remainder, not independently rounded — segments always sum to 100
  const parts = [`${okCount} of ${total} read well`];
  if (checkCount > 0) parts.push(`${checkCount} to check`);
  if (missingCount > 0) parts.push(`${missingCount} still empty`);
  return { okCount, checkCount, missingCount, total, clear: false, statusText: parts.join(' · '), okPct, checkPct, missPct };
}

export function validateEditorInput(raw) {
  const trimmed = (raw || '').trim();
  if (trimmed === '') return { ok: false, empty: true };
  if (!/^[+-]?\d+(\.\d+)?$/.test(trimmed)) return { ok: false, message: 'That needs to be a number.' };
  const num = parseFloat(trimmed);
  if (num < 0 || num > 6000) return { ok: false, message: 'Numbers here are usually between 0 and 6000.' };
  return { ok: true, value: num };
}

export function editorContentFor({ side, key, fieldState }) {
  const [cls, stat] = key.split('|');
  const title = `${SIDE_NAME[side]} · ${cls} · ${stat}`;
  if (fieldState.state === 'missing') {
    return { title, cropTag: 'NOT CAPTURED', cropBody: 'This part of the screenshot was not captured.',
      inputValue: '', help: "We couldn't read this one. Type the number." };
  }
  return { title, cropTag: 'WHAT WE SAW', cropBody: `${cls} ${stat}: +${Number(fieldState.value).toFixed(1)}`,
    inputValue: Number(fieldState.value).toFixed(1), help: 'Type over the number if it needs fixing.' };
}

export function nextResetState(current) {
  if (current === 'confirming') return { state: 'idle', label: 'Reset', shouldClear: true };
  return { state: 'confirming', label: 'Really reset?', shouldClear: false };
}

function fieldButtonHtml(side, key, fieldState) {
  const [, stat] = key.split('|');
  const display = fieldState.state === 'missing' ? '— —' : Number(fieldState.value).toFixed(1);
  const label = `${SIDE_NAME[side]} ${key.replace('|', ' ')}: ${display}. ${provenanceText(fieldState)}`;
  return `<button type="button" class="ocrf-rv-field ocrf-rv-${fieldState.state}" data-field="${side}-${key}" aria-label="${label}">
    <span class="ocrf-rv-lab">${stat}</span><span class="ocrf-rv-val">${display}</span>
    <span class="ocrf-rv-ic" aria-hidden="true">${STATE_ICON[fieldState.state]}</span>
  </button>`;
}

function columnHtml(side, statesForSide) {
  const groups = CLASSES.map((cls) => {
    const fields = STATS.map((stat) => fieldButtonHtml(side, `${cls}|${stat}`, statesForSide[`${cls}|${stat}`])).join('');
    return `<div class="ocrf-rv-group"><div class="ocrf-rv-group-head">${cls}</div><div class="ocrf-rv-stats">${fields}</div></div>`;
  }).join('');
  const headLabel = side === 'you' ? 'MY SIDE' : 'ENEMY';
  return `<div class="ocrf-rv-col ocrf-rv-${side === 'you' ? 'me' : 'enemy'}">
    <div class="ocrf-rv-col-head">${headLabel}</div>${groups}</div>`;
}

export function renderReviewGrid(states) {
  return `<div class="ocrf-review-grid">${columnHtml('you', states.you)}${columnHtml('enemy', states.enemy)}</div>`;
}

function tallyCardHtml(tally) {
  return `<div class="ocrf-tally-head"><span class="ocrf-tally-num">${tally.okCount}/${tally.total}</span>
  <span class="ocrf-tally-status${tally.clear ? ' ocrf-clear' : ''}">${tally.statusText}</span></div>
  <div class="ocrf-tally-bar"><i class="ocrf-b-ok" style="width:${tally.okPct}%"></i>
  <i class="ocrf-b-check" style="width:${tally.checkPct}%"></i>
  <i class="ocrf-b-missing" style="width:${tally.missPct}%"></i></div>`;
}

export function renderS4({ states, tally }) {
  return `
<section class="screen" data-screen="s4">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">Check your numbers</h1></header>
  <div class="ocrf-scr-body">
    <button type="button" class="ocrf-link-btn" data-open-picture>See my screenshot</button>
    <div class="ocrf-tally-card">${tallyCardHtml(tally)}</div>
    <div class="ocrf-tally-actions"><button type="button" class="ocrf-reset-btn" id="ocrfResetS4">Reset</button></div>
    ${renderReviewGrid(states)}
  </div>
  <footer class="ocrf-scr-foot">
    <button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s5">Next</button>
  </footer>
</section>`.trim();
}

export function renderEditorSheet() {
  return `
<div class="ocrf-modal-scrim" id="ocrfEditorScrim" aria-hidden="true" inert>
  <div class="ocrf-editor" role="dialog" aria-modal="true" aria-labelledby="ocrfEditorTitle">
    <div class="ocrf-editor-head"><h2 id="ocrfEditorTitle">&mdash;</h2>
      <button type="button" class="ocrf-close-x" id="ocrfEditorClose" aria-label="Close">&times;</button></div>
    <div class="ocrf-crop-box" id="ocrfEditorCrop"></div>
    <label class="ocrf-editor-label" for="ocrfEditorInput">Number</label>
    <input class="ocrf-big-input" id="ocrfEditorInput" type="text" inputmode="decimal" autocomplete="off">
    <p class="ocrf-editor-msg" id="ocrfEditorMsg" hidden></p>
    <p class="ocrf-editor-help" id="ocrfEditorHelp"></p>
    <div class="ocrf-editor-actions">
      <button type="button" class="ocrf-btn-ghost" id="ocrfEditorCancel">Cancel</button>
      <button type="button" class="ocrf-btn-primary" id="ocrfEditorSave">Save</button>
    </div>
  </div>
</div>`.trim();
}

export function renderPictureView(states) {
  const col = (side) => CLASSES.map((cls) => {
    const rows = STATS.map((stat) => {
      const fs = states[side][`${cls}|${stat}`];
      if (fs.state === 'missing') {
        return `<div class="ocrf-game-row ocrf-dim"><span class="ocrf-gr-label">${stat}</span>`
          + '<span class="ocrf-gr-val ocrf-dim">Not captured</span></div>';
      }
      return `<div class="ocrf-game-row"><span class="ocrf-gr-label">${stat}</span>`
        + `<span class="ocrf-gr-val">+${Number(fs.value).toFixed(1)}</span></div>`;
    }).join('');
    return `<div class="ocrf-rv-group-head">${cls}</div>${rows}`;
  }).join('');
  return `<div class="ocrf-picture-scroll"><div>${col('you')}</div><div>${col('enemy')}</div></div>`;
}

/* ---- thin DOM wiring below: exercised by the Task 10 browser gate, not node:test ---- */

export function wireS4(root, { onOpenField, onOpenPicture, onReset }) {
  root.querySelectorAll('[data-field]').forEach((btn) => {
    btn.addEventListener('click', () => onOpenField(btn.dataset.field));
  });
  root.querySelector('[data-open-picture]')?.addEventListener('click', onOpenPicture);
  root.querySelector('#ocrfResetS4')?.addEventListener('click', onReset);
}
```

- [ ] **Step 4: Run to verify all pass** — `node --test shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs shell/app/ocr/client/tests/error_copy.test.mjs shell/app/ocr/client/tests/controller.test.mjs shell/app/ocr/client/tests/screens_entry.test.mjs shell/app/ocr/client/tests/screens_pick_upload.test.mjs shell/app/ocr/client/tests/screens_reading.test.mjs shell/app/ocr/client/tests/screens_review.test.mjs` → all passed.
- [ ] **Step 5: Commit** — `git add shell/app/ocr/client/screens/review.mjs shell/app/ocr/client/tests/screens_review.test.mjs && git commit -m "ocr: S4 review grid + editor + screenshot viewer + Reset (data-driven, not scripted)"`

---

### Task 9: S5 — fill the real app (not a new screen)

**Files:** Create `shell/app/ocr/client/screens/setup.mjs`, `shell/app/ocr/client/tests/screens_setup.test.mjs`; append to `ocr_flow.js`/`ocr_flow.css`

**Scope correction from the mock, grounded in the real app (important — read before implementing):** `OCR_UX_FLOW_SPEC.md` §3 S5 says outright *"this page is NOT a new design. It IS the current app's setup section with OCR values prefilled."* The mock, being a self-contained single-file demo with no real app underneath it, had to **redraw** Troops Formation (`.form-ctl2` glass sliders), hero pickers (`.hpick-btn2` — and per the research pass, even the mock's OWN hero-picker is a stub: clicking any hero slot just shows a toast reading *"Pick a hero in the real app."* / *"Pick a different hero in the real app."*, with no picker UI behind it at all), joiners, and a role toggle from scratch. **None of that exists in this task.** `prototype/index.html` already has working, real, interactive versions of all four (`#formMe`/`#formFoe`, `#capMe`/`#capFoe` with a full search-and-pick `heroPicker()`, `#joinMe`/`#joinFoe`, `#roleToggle`) sitting on the page below the injected entry point — this task never touches them beyond the one real, tested fill path (`applyPanel`/`applyHeroes`) already read from `prototype/index.html`. Formation is **never** filled (the OCR panel API returns no formation/troop-count data — confirmed absent from `service.py`'s response contract) and joiners stay blank (`OCR_UX_FLOW_SPEC.md` §3: *"Joiners: blank/unset in v1"*). The only new UI this task builds is the **collapsed stats-summary chip** (spec item 1: *"a minimized summary chip of the review grid (expandable); the full stat panel is not the star here"*) — everything else is either "fill it and step back" or "leave it alone."

**The final CTA, per the same spec sentence — *"= the existing forecast button"*, an equality, not a lookalike:** this task does not build a new CTA and does not itself trigger a forecast run (that would silently spend the user's daily sim quota without an explicit action from them — worth flagging if a future pass wants that automated). It fills the data, calls the same `updateFinalStats()` the real app's own "Load config" path calls, and best-effort scrolls the filled panel into view. The user's own tap on the app's real Run/Refresh control is unchanged and untouched.

**Interfaces — Consumes:** Task 8's `renderReviewGrid`/`computeTally` (reused, not rebuilt); Task 2's `toApplyPanelPayload`/`toApplyHeroesPayload`/`buildSnapshot`; the real, already-verified globals `window.applyPanel(which, panel)`, `window.applyHeroes(id, names)`, `window.updateFinalStats()`, and the `#statsScouted`/`#statsBase` checkboxes (`prototype/index.html` — confirmed by reading `selectedStatsType()`/`computeFinalPanelPct()` that **only `#statsScouted`'s `checked` state is load-bearing**; `#statsBase` has no independent effect on the computation and is set purely so the two checkboxes never show a confusing both-checked state; neither needs a dispatched `change` event because `updateFinalStats()` re-reads `.checked` synchronously when called). **Produces**, pure/tested:
- `computeChipText(tally)` — the S5-specific chip wording (distinct from S4's tally-card wording): complete → `"All {total} numbers in ✓ — tap to check"`; incomplete → `"{ok} of {total} in"` + optional `"· {check} to check"` + optional `"· {missing} still empty"`, always suffixed `" — tap to check"`.
- `shouldShowUndo(snapshot)` — `true` whenever a pre-fill snapshot was captured (this build's snapshot always captures the *whole* prior panel state, not just edited fields, so — unlike the mock's narrower "only if something was actually edited" gate — restoring is meaningful even on the very first fill of a session; documented as a deliberate, justified simplification, not an oversight).
- `buildFillPlan({ conversion, heroesMe, heroesFoe })` — turns Task 1's per-side `ConversionResult`s into the exact `{me, foe, heroesMe, heroesFoe}` payload shapes Task 2's mappers produce; a side whose `outcome !== 'ready'` is simply left out of the plan (never partially filled from a non-`ready` result — the never-fabricate rule applies here too).
- `renderS5({chipText, complete, states})` — the chip + expandable grid + Undo link, pure template (the caller computes `chipText`/`complete` from a tally itself, via `computeChipText`, before calling this).
Thin (DOM, browser-gate only): `applyFillPlan(plan, {win})`, `wireS5(...)`.

- [ ] **Step 1: Write the failing tests**

```js
// shell/app/ocr/client/tests/screens_setup.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { computeChipText, shouldShowUndo, buildFillPlan, renderS5 } from '../screens/setup.mjs';
import { computeTally } from '../screens/review.mjs';

test('computeChipText: complete', () => {
  const text = computeChipText(computeTally(Array(24).fill('ok')));
  assert.match(text, /^All 24 numbers in/);
  assert.match(text, /tap to check$/);
});

test('computeChipText: incomplete, same join rules as the tally card, always ends "tap to check"', () => {
  const states = [...Array(18).fill('ok'), ...Array(3).fill('check'), ...Array(3).fill('missing')];
  const text = computeChipText(computeTally(states));
  assert.equal(text, '18 of 24 in · 3 to check · 3 still empty — tap to check');
});

test('shouldShowUndo is true whenever a snapshot was captured, even on the very first fill', () => {
  assert.equal(shouldShowUndo(null), false);
  assert.equal(shouldShowUndo({ me: { panel: {} }, foe: { panel: {} }, heroesMe: null, heroesFoe: null, statsScoutedChecked: false }), true);
});

test('buildFillPlan only fills sides whose conversion is actually ready — never a partial/needs_specials side', () => {
  const plan = buildFillPlan({
    conversion: {
      you: { outcome: 'ready', percents: { 'Infantry|Attack': 4491.6 } },
      enemy: { outcome: 'needs_specials', percents: null, rawUnconverted: { 'Infantry|Attack': 694.3 } },
    },
    heroesMe: null, heroesFoe: null,
  });
  assert.ok(plan.me);
  assert.equal(plan.me['Infantry|Attack'], 44.916);
  assert.equal(plan.foe, null);
});

test('buildFillPlan carries hero payloads only when supplied, ordered Infantry/Lancer/Marksman', () => {
  const plan = buildFillPlan({
    conversion: { you: { outcome: 'ready', percents: {} }, enemy: { outcome: 'ready', percents: {} } },
    heroesMe: { Infantry: 'Hank', Lancer: null, Marksman: 'Viveca' },
    heroesFoe: null,
  });
  assert.deepEqual(plan.heroesMe, ['Hank', null, 'Viveca']);
  assert.equal(plan.heroesFoe, null);
});

test('renderS5 shows the collapsed chip, a hidden expandable body, and a hidden Undo link by default', () => {
  const states = { you: {}, enemy: {} };   // grid content itself is Task 8's concern, not re-tested here
  const html = renderS5({ chipText: 'All 24 numbers in ✓ — tap to check', complete: true, states });
  assert.match(html, /aria-expanded="false"/);
  assert.match(html, /id="ocrfS5Body" hidden/);
  assert.match(html, /id="ocrfUndoChip" hidden/);
  assert.doesNotMatch(html, /Troops Formation/);   // formation is explicitly NOT part of this widget
  assert.doesNotMatch(html, /hero-grid|joiner-pill/i);   // neither are heroes/joiners — those are the real app's own DOM
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test shell/app/ocr/client/tests/screens_setup.test.mjs` → FAIL (module missing).

- [ ] **Step 3: Implement**

```js
// shell/app/ocr/client/screens/setup.mjs
import { renderReviewGrid } from './review.mjs';
import { toApplyPanelPayload, toApplyHeroesPayload } from '../fill_mapper.mjs';

export function computeChipText(tally) {
  if (tally.clear) {
    return `All ${tally.total} numbers in <span class="ocrf-chip-ok-ic" aria-hidden="true">&#10003;</span> — tap to check`;
  }
  const parts = [`${tally.okCount} of ${tally.total} in`];
  if (tally.checkCount > 0) parts.push(`${tally.checkCount} to check`);
  if (tally.missingCount > 0) parts.push(`${tally.missingCount} still empty`);
  return `${parts.join(' · ')} — tap to check`;
}

export function shouldShowUndo(snapshot) {
  return !!snapshot;
}

export function buildFillPlan({ conversion, heroesMe = null, heroesFoe = null }) {
  const plan = { me: null, foe: null, heroesMe: null, heroesFoe: null };
  if (conversion.you && conversion.you.outcome === 'ready') {
    plan.me = toApplyPanelPayload(conversion.you.percents);
  }
  if (conversion.enemy && conversion.enemy.outcome === 'ready') {
    plan.foe = toApplyPanelPayload(conversion.enemy.percents);
  }
  if (heroesMe) plan.heroesMe = toApplyHeroesPayload(heroesMe);
  if (heroesFoe) plan.heroesFoe = toApplyHeroesPayload(heroesFoe);
  return plan;
}

export function renderS5({ chipText, complete, states }) {
  // Undo's own visibility is driven entirely by its `hidden` attribute (thin wiring,
  // via shouldShowUndo(snapshot), toggles that after mount) — the wrapping <p> is never
  // itself conditionally hidden, there is nothing else in it whose visibility depends on
  // anything this pure template knows.
  return `
<section class="ocrf-s5" id="ocrfS5">
  <div class="ocrf-stats-accordion">
    <button type="button" class="ocrf-stats-chip${complete ? ' ocrf-complete' : ' ocrf-needs-attention'}"
      id="ocrfS5Chip" aria-expanded="false" aria-controls="ocrfS5Body">
      <span class="ocrf-chip-text">${chipText}</span>
      <span class="ocrf-chip-caret" aria-hidden="true">&#8964;</span>
    </button>
    <div class="ocrf-stats-body" id="ocrfS5Body" hidden>
      <button type="button" class="ocrf-link-btn" data-open-picture>See my screenshot</button>
      <div class="ocrf-tally-actions"><button type="button" class="ocrf-reset-btn" id="ocrfResetS5">Reset</button></div>
      ${renderReviewGrid(states)}
    </div>
  </div>
  <p class="ocrf-s5-links" id="ocrfS5Links">
    <button type="button" class="ocrf-link-btn" id="ocrfUndoChip" hidden>Put my last numbers back</button>
  </p>
</section>`.trim();
}

/* ---- thin DOM wiring below: exercised by the Task 10 browser gate, not node:test ---- */

export function applyFillPlan(plan, { win = window } = {}) {
  if (plan.me && typeof win.applyPanel === 'function') win.applyPanel('me', plan.me);
  if (plan.foe && typeof win.applyPanel === 'function') win.applyPanel('foe', plan.foe);
  const statsScouted = document.getElementById('statsScouted');
  const statsBase = document.getElementById('statsBase');
  if (statsScouted) statsScouted.checked = true;
  if (statsBase) statsBase.checked = false;
  if (plan.heroesMe && typeof win.applyHeroes === 'function') win.applyHeroes('#capMe', plan.heroesMe);
  if (plan.heroesFoe && typeof win.applyHeroes === 'function') win.applyHeroes('#capFoe', plan.heroesFoe);
  if (typeof win.updateFinalStats === 'function') win.updateFinalStats();
  const statPanel = document.getElementById('statPanel');
  statPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export function wireS5(root, { onToggleChip, onOpenPicture, onReset, onUndo }) {
  root.querySelector('#ocrfS5Chip')?.addEventListener('click', onToggleChip);
  root.querySelector('[data-open-picture]')?.addEventListener('click', onOpenPicture);
  root.querySelector('#ocrfResetS5')?.addEventListener('click', onReset);
  root.querySelector('#ocrfUndoChip')?.addEventListener('click', onUndo);
}
```

- [ ] **Step 4: Run to verify all pass** — `node --test shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs shell/app/ocr/client/tests/error_copy.test.mjs shell/app/ocr/client/tests/controller.test.mjs shell/app/ocr/client/tests/screens_entry.test.mjs shell/app/ocr/client/tests/screens_pick_upload.test.mjs shell/app/ocr/client/tests/screens_reading.test.mjs shell/app/ocr/client/tests/screens_review.test.mjs shell/app/ocr/client/tests/screens_setup.test.mjs` → all passed.
- [ ] **Step 5: Commit** — `git add shell/app/ocr/client/screens/setup.mjs shell/app/ocr/client/tests/screens_setup.test.mjs && git commit -m "ocr: S5 — fills the real app's own controls, never-ready sides left alone"`

---

### Task 10: Final assembly + the acceptance gate

**Files:** Finalize `shell/app/ocr/client/ocr_flow.js` (integration only — no new pure logic, nothing here is independently unit-tested; every decision it makes was already made and tested by Tasks 1–9); walk the QA protocol below (process, not code).

**Part A — wire the screens together.** Every piece this file calls is already built and tested (Tasks 1–9); this step is pure assembly: a small navigation stack (mirroring the mock's own proven `goto`/`back`/`show` pattern — auto-advance screens **replace** the current history entry, deliberate ones **push**, exactly as the global constraints require) and the read → convert → classify → render pipeline.

```js
// shell/app/ocr/client/ocr_flow.js — FINAL bootstrap
import { mountEntry, wireEntry, renderUpgradeNote, wireUpgradeNote } from './screens/entry.mjs';
import { renderS1, renderS2, renderE1, wireS1, wireS2, wireE1, computeS2ContinueState } from './screens/pick_upload.mjs';
import { renderPrep, renderS3, driveScan, applyStepClasses, wireS3 } from './screens/reading.mjs';
import {
  renderS4, renderEditorSheet, renderPictureView, fieldRenderState, computeTally,
  validateEditorInput, editorContentFor, nextResetState, wireS4,
} from './screens/review.mjs';
import { renderS5, computeChipText, shouldShowUndo, buildFillPlan, applyFillPlan, wireS5 } from './screens/setup.mjs';
import { createController } from './controller.mjs';
import { classifyFields, ALL_FIELD_KEYS, buildSnapshot } from './fill_mapper.mjs';

function fetchMe() { return fetch('/shell/me', { credentials: 'same-origin' }).then((r) => r.json()); }
async function checkAccess() {
  try {
    const me = await fetchMe();
    const plan = me?.user?.plan;
    return { allowed: plan === 'pro', plan: plan ?? null, reachable: true, userId: me?.user?.user_id ?? null };
  } catch { return { allowed: false, plan: null, reachable: false, userId: null }; }
}
function postPanel({ shotBytesList, side, panelType }) {
  const form = new FormData();
  for (const bytes of shotBytesList) form.append('file', new Blob([bytes], { type: 'image/png' }), 'shot.png');
  form.append('side', side);
  if (panelType) form.append('panel', panelType);
  return fetch('/shell/ocr/panel', { method: 'POST', body: form, credentials: 'same-origin' }).then(async (r) => {
    if (r.ok) return r.json();
    const err = new Error('panel upload failed'); err.status = r.status; err.body = await r.json().catch(() => null);
    throw err;
  });
}

let recognizeImage = null;   // lazy-imported so its WASM/vendor payload is never fetched before the first real scan
async function getRecognizeImage() {
  if (!recognizeImage) ({ recognizeImage } = await import('./engine_tesseract.mjs'));
  return recognizeImage;
}

const controller = createController({
  fetchMe, postPanel, storage: window.localStorage,
  recognizeImage: (bytes) => getRecognizeImage().then((fn) => fn(bytes)),
});

const app = { history: ['entry'], screen: 'entry', primed: false,
  shots: { you: [], enemy: [] },            // [{id, bytes: Uint8Array}]
  savedValues: { you: {}, enemy: {} }, typedFields: { you: {}, enemy: {} },
  lastRead: null, priorSnapshot: null, resetTimer: null };

function root() { return document.getElementById('ocrfRoot'); }

function show(html) {
  root().innerHTML = html;
  const heading = root().querySelector('h1, h2[tabindex]');
  if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus({ preventScroll: true }); }
}

function goto(screen, { push = true } = {}) {
  if (app.resetTimer) { clearTimeout(app.resetTimer); app.resetTimer = null; }
  if (push) app.history.push(screen); else app.history[app.history.length - 1] = screen;
  app.screen = screen;
  render();
}
function back() {
  if (app.history.length > 1) { app.history.pop(); app.screen = app.history[app.history.length - 1]; render(); }
}

function fieldStatesFor(side) {
  const result = app.lastRead?.results?.[side];
  const classification = classifyFields({
    expectedKeys: ALL_FIELD_KEYS,
    stats: result?.stats ?? result?.[side === 'you' ? 'stats_you' : 'stats_enemy'] ?? {},
    fieldConf: result?.field_conf ?? result?.[side === 'you' ? 'stats_you_conf' : 'stats_enemy_conf'] ?? {},
  });
  const out = {};
  for (const key of ALL_FIELD_KEYS) {
    out[key] = fieldRenderState({ classification: classification[key], savedValue: app.savedValues[side][key] });
  }
  return out;
}
function allFieldStates() { return { you: fieldStatesFor('you'), enemy: fieldStatesFor('enemy') }; }
function flatTallyStates(states) {
  return [...Object.values(states.you), ...Object.values(states.enemy)].map((f) => f.state);
}

function render() {
  if (app.screen === 'entry') {
    return; // the entry card is mounted once, outside the screen stack — see boot()
  }
  if (app.screen === 's1') { show(renderS1()); wireS1(root(), { onPick: onPickKind }); return; }
  if (app.screen === 's2') {
    const coverage = controller.flow.coverage();
    show(renderS2({ types: controller.flow.types(), coverage,
      shots: { you: app.shots.you.map((s) => s.id), enemy: app.shots.enemy.map((s) => s.id) } }));
    wireS2(root(), { onDropzone: onDropzone, onTypeTag: onTypeTag, onContinue: onS2Continue });
    return;
  }
  if (app.screen === 'prep') { show(renderPrep()); setTimeout(() => { app.primed = true; goto('s3', { push: false }); }, 1300); return; }
  if (app.screen === 's3') {
    show(renderS3());
    const handle = driveScan({
      run: () => controller.readAll({ you: app.shots.you.map((s) => s.bytes), enemy: app.shots.enemy.map((s) => s.bytes) }),
      onStepChange: (i) => applyStepClasses(root(), i),
      onDone: onReadDone, onError: onReadError,
    });
    wireS3(root(), { onCancel: () => { handle.cancel(); goto('s2', { push: false }); } });
    return;
  }
  if (app.screen === 's4') {
    const states = allFieldStates();
    show(renderS4({ states, tally: computeTally(flatTallyStates(states)) }));
    wireS4(root(), { onOpenField: openEditor, onOpenPicture: openPicture, onReset: () => doReset('s4') });
    return;
  }
  if (app.screen === 's5') {
    const states = allFieldStates();
    const tally = computeTally(flatTallyStates(states));
    const conversion = app.lastRead?.conversion ?? {};
    const plan = buildFillPlan({ conversion, heroesMe: null, heroesFoe: null });   // hero-gen defaulting: dormant, Open Question 3
    app.priorSnapshot = buildSnapshot({
      percentsMe: window.readInputPanelPct ? window.readInputPanelPct('me') : {},
      percentsFoe: window.readInputPanelPct ? window.readInputPanelPct('foe') : {},
      heroesMe: null, heroesFoe: null, statsScoutedChecked: document.getElementById('statsScouted')?.checked ?? false,
    });
    applyFillPlan(plan);
    show(renderS5({ chipText: computeChipText(tally), complete: tally.clear, states }));
    const undoChip = document.getElementById('ocrfUndoChip');
    if (undoChip) undoChip.hidden = !shouldShowUndo(app.priorSnapshot);
    wireS5(root(), {
      onToggleChip: onToggleS5Chip, onOpenPicture: openPicture, onReset: () => doReset('s5'),
      onUndo: () => {
        const snap = app.priorSnapshot;
        if (!snap) return;
        applyFillPlan({ me: snap.me.panel, foe: snap.foe.panel, heroesMe: null, heroesFoe: null });
        const statsScouted = document.getElementById('statsScouted');
        if (statsScouted) statsScouted.checked = snap.statsScoutedChecked;
        if (window.updateFinalStats) window.updateFinalStats();
      },
    });
    return;
  }
  if (app.screen === 'e1') { show(renderE1(app.e1Variant ?? 'wrong', app.e1Counts ?? {})); wireE1(root(), { onRetake: onE1Retake, onTypeMissing: onE1TypeMissing }); return; }
}

function onPickKind(kind) { controller.flow.pickKind(kind); goto('s2'); }
function onDropzone(side) { /* opens the OS file picker; on file(s) selected, read bytes, controller.flow.addShot(side, id), app.shots[side].push({id, bytes}), re-render s2 */ }
function onTypeTag(side) { /* opens the type-tag popover (Task 6's renderS2 already reflects controller.flow.types(); on choice, controller.flow.setSideType(side, type), re-render) */ }
function onS2Continue() { goto(app.primed ? 's3' : 'prep'); }
function onReadDone(result) { app.lastRead = result; const unreadable = countUnreadable(result); if (unreadable === 0) goto('s4', { push: false }); else { app.e1Variant = 'partial'; app.e1Counts = { readCount: 24 - unreadable, totalCount: 24 }; goto('e1', { push: false }); } }
function onReadError(err) { app.e1Variant = 'wrong'; goto('e1', { push: false }); }
function countUnreadable(result) { return Object.values(result.results ?? {}).reduce((n, r) => n + (r?.unreadable_fields?.length ?? 0), 0); }
function onE1Retake() { app.shots = { you: [], enemy: [] }; goto('s2', { push: false }); }
function onE1TypeMissing() { goto('s4', { push: false }); }
function onToggleS5Chip() { const chip = document.getElementById('ocrfS5Chip'); const body = document.getElementById('ocrfS5Body'); const open = chip.getAttribute('aria-expanded') === 'true'; chip.setAttribute('aria-expanded', String(!open)); body.hidden = open; }

function doReset(screen) {
  const key = `resetState_${screen}`;
  const next = nextResetState(app[key] ?? 'idle');
  app[key] = next.state;
  const btn = document.getElementById(screen === 's4' ? 'ocrfResetS4' : 'ocrfResetS5');
  if (btn) btn.textContent = next.label;
  if (next.shouldClear) {
    app.savedValues = { you: {}, enemy: {} }; app.typedFields = { you: {}, enemy: {} };
    render();
  } else {
    app.resetTimer = setTimeout(() => { app[key] = 'idle'; if (btn) btn.textContent = 'Reset'; }, 3000);
  }
}

let editingField = null;
function openEditor(fieldKey) {
  const [side, key] = [fieldKey.split('-')[0], fieldKey.slice(fieldKey.indexOf('-') + 1)];
  editingField = { side, key };
  const states = allFieldStates();
  const content = editorContentFor({ side, key, fieldState: states[side][key] });
  const scrim = document.body.appendChild(Object.assign(document.createElement('div'), { innerHTML: renderEditorSheet() })).firstElementChild;
  scrim.querySelector('#ocrfEditorTitle').textContent = content.title;
  scrim.querySelector('#ocrfEditorCrop').textContent = content.cropBody;
  scrim.querySelector('#ocrfEditorInput').value = content.inputValue;
  scrim.querySelector('#ocrfEditorHelp').textContent = content.help;
  scrim.removeAttribute('inert'); scrim.setAttribute('aria-hidden', 'false');
  scrim.querySelector('#ocrfEditorInput').focus();
  scrim.querySelector('#ocrfEditorCancel').addEventListener('click', () => scrim.remove());
  scrim.querySelector('#ocrfEditorClose').addEventListener('click', () => scrim.remove());
  scrim.querySelector('#ocrfEditorSave').addEventListener('click', () => {
    const result = validateEditorInput(scrim.querySelector('#ocrfEditorInput').value);
    const msg = scrim.querySelector('#ocrfEditorMsg');
    if (!result.ok) { if (!result.empty) { msg.textContent = result.message; msg.hidden = false; } return; }
    app.savedValues[side][key] = result.value; app.typedFields[side][key] = true;
    scrim.remove(); render();
  });
}
function openPicture() {
  const states = allFieldStates();
  const wrap = document.body.appendChild(Object.assign(document.createElement('div'), { innerHTML: renderPictureView(states) }));
  wrap.querySelector('.ocrf-picture-scroll')?.scrollIntoView({ block: 'center' });
}

function boot() {
  const entryNode = mountEntry({ root: document });
  if (!entryNode) return;
  wireEntry(entryNode, {
    checkAccess,
    onProceed: () => {
      const stack = document.createElement('div'); stack.id = 'ocrfRoot';
      document.body.appendChild(stack);
      goto('s1');
    },
    onNeedsUpgrade: () => {
      const wrap = document.createElement('div'); wrap.innerHTML = renderUpgradeNote();
      const node = wrap.firstElementChild; document.body.appendChild(node);
      node.removeAttribute('inert'); node.setAttribute('aria-hidden', 'false');
      wireUpgradeNote(node, {
        checkout: () => fetch('/shell/billing/checkout', { method: 'POST', credentials: 'same-origin' })
          .then((r) => { if (!r.ok) throw new Error('checkout unavailable'); return r.json(); }),
      });
    },
  });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}
```

`onDropzone`/`onTypeTag` are left as commented stubs above deliberately: they are pure file-input/popover DOM mechanics with no decision logic of their own (every actual decision — which type is valid for a side, whether a type change confirms, what the dropzone should say — was already built and tested in Task 6). Wire them to a real `<input type="file" accept="image/png,image/jpeg,image/webp">` and `controller.flow.addShot`/`setSideType` during implementation; there is nothing here for a test to usefully assert beyond what Task 6 already covers.

- [ ] **Step A1:** Wire the two stubs above to real file input + popover DOM. Run the full existing suite once more to confirm the assembly didn't regress anything: `py -m pytest shell/tests -q` and `node --test shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs shell/app/ocr/client/tests/error_copy.test.mjs shell/app/ocr/client/tests/controller.test.mjs shell/app/ocr/client/tests/screens_entry.test.mjs shell/app/ocr/client/tests/screens_pick_upload.test.mjs shell/app/ocr/client/tests/screens_reading.test.mjs shell/app/ocr/client/tests/screens_review.test.mjs shell/app/ocr/client/tests/screens_setup.test.mjs`.
- [ ] **Step A2: Commit** — `git add shell/app/ocr/client/ocr_flow.js && git commit -m "ocr: final assembly — navigation stack, sheet lifecycle, read/convert/fill pipeline"`

**Part B — the acceptance gate.** This plan's actual acceptance bar (`docs/OCR_QA_PLAN.md` §1: "L4 Flow/UI ... browser walkthrough protocol"). Use the project's established evaluator-gate workflow (see `prototype/mocks/ocr_flow_mock.html`'s own review history for the pattern this project already uses — round after round until every item is satisfied, not a single pass) against the **real overlay running on the real app** (`.claude/skills/run` / the project's `prototype` launch config), not the mock. Walk `docs/OCR_QA_PLAN.md` §5 rows **F1–F13** end to end, at **both** 375×812 (mobile) and ≥1280px (desktop) widths (row **F13** — resize the browser pane between passes, reload so any width-gated logic re-runs):

- [ ] **F1** Cancel mid-scan → lands on Add-screenshots (S2), no auto-advance resurrection.
- [ ] **F2** Back from S4 → the last deliberate screen; edits and uploads both preserved.
- [ ] **F3** Upload a screenshot of something else entirely (e.g. the hero screen) → E1 "wrong" variant; the failed upload is cleared with the notice banner; Continue on S2 stays disabled until a new one is added.
- [ ] **F4** A screenshot with some fields genuinely unreadable → E1 "partial" variant with the REAL count (not a hardcoded one — this is exactly what Task 6 changed from the mock); both exits work; missing fields are inline-highlighted on S4; the tally is honest on S4 **and** S5's chip.
- [ ] **F5** A screenshot where nothing is readable → `status: "failed"` → E1; "Type them in myself" is a fully manual path from there; no dead end anywhere.
- [ ] **F6** Battle-covers-both, then the enemy side gets its own separate upload afterward → coverage/precedence matches `flow_state.mjs`'s own tested behavior (Task 4's "battle-covers-both" test); no upload is ever silently lost switching between these modes.
- [ ] **F7** As a free-tier account (or with `checkAccess` forced to `{allowed:false}` via dev tools), tap the entry CTA → the upgrade note (Task 5), never a dead/broken button.
- [ ] **F8** Force the client engine to fail (e.g. block the tesseract WASM/model network requests in dev tools) → automatic, described fallback to `/shell/ocr/panel`; if that is also blocked, the flow lands on a state where manual typing is clearly available — three honestly-described steps, per Task 4/7's escalation design.
- [ ] **F9** Interrupt the first-ever engine download (throttle/offline mid-PREP) → a retry affordance appears, no permanently broken state on a second attempt.
- [ ] **F10** A gen-badge scenario the hero table doesn't recognize (or — realistically in v1, per **Open Question 3** — every scenario, since there is no live gen source yet) → hero slots stay exactly as the real app already had them, never a wrong-generation default.
- [ ] **F11** Reset (S4 and S5) restores to as-scanned after the second confirming tap, with the exact "Really reset?" / 3-second-auto-revert behavior; Undo (S5) restores the pre-fill snapshot; both pieces of copy are literally true of what just happened.
- [ ] **F12** Full accessibility pass: tab through every screen (focus visibly lands on each new heading), `Escape` closes the editor/picture sheets, background screens are `inert` while a sheet is open, every tap target measures ≥44px, and each review-grid field's screen-reader label reads one of the three exact provenance strings.
- [ ] **F13** Confirmed at both widths already, above — additionally confirm zero horizontal scroll anywhere in the flow at 375px.

- [ ] **Final:** every F1–F13 row above is checked off, on both widths, against the real running app (not the mock). File any row that cannot pass as-is against the **Open Questions** at the top of this document (most will trace back to one of them) rather than silently patching around it. Commit is optional here (no code change expected if the assembly in Part A was correct) — if the gate surfaces a real bug, fix it with its own red→green→commit cycle before re-running the gate.

---

## Self-review checklist (run before handing to executors)

- **Spec coverage:** `OCR_UX_FLOW_SPEC.md` §1 (D1/402 gate → Tasks 4/5; never-fabricate → Tasks 1/2/8 throughout) · §2 (per-side OCR contract → Tasks 1/4; battle-both-columns → Task 4's `deriveViews`) · §3 S0 → Task 5, S1/S2 → Task 6, PREP/S3 → Task 7, S4 → Task 8, S5 → Task 9, E1 → Task 6 · §4 copy/terminology → every task's jargon/terminology tests · §5 engineering patterns (one history slot, `[hidden]`, focus-to-heading, undo, strict validation, sheet inert) → Task 10 Part A, verified by Part B's F1/F2/F11/F12.
- **`docs/OCR_QA_PLAN.md` coverage:** L1 unit layer = Tasks 0–9's own suites (plus the pre-existing `panel_ocr` suite, untouched); L3 API/abuse = already covered by the existing `shell/tests/test_ocr_panel_router.py` (this plan adds no new server endpoint, so no new L3 surface); L4 = Task 10 Part B, F1–F13; L5 determinism = inherited for free from Tasks 1–4 being pure functions of injected inputs (no wall-clock/randomness anywhere in the tested logic).
- **Terminology guard:** every screen-content test asserts against `/\bpicture\b/i`, and Task 3's `error_copy.test.mjs` sweeps every real denial shape for the full jargon list (`ocr`, `parse`, `confidence`, every raw internal error code, every raw status code) — this is the one constraint checked in literally every task rather than once.
- **Data fidelity:** every numeric example in Tasks 0/1/4 traces to `shell/tests/fixtures/panel_ocr/golden_vectors.json` (both accounts) — nothing here invents a scout/battle/citystats number; only the denial-shape and copy strings are authored fresh, and those are checked against the real `service.py`/`panel_router.py`/`limits.py`/`error_copy.mjs` source, never against each other.
- **Test-split discipline (decision #6):** pure logic (`convert_side`, `fill_mapper`, `error_copy`, `controller`'s decision functions, every screen module's non-DOM exports) is fully node:test-covered; DOM mounting/event-wiring is consistently thin and named as such in every task, with Task 10 Part B as the single, explicit place that verifies it actually works.
- **Known gaps, by design, not oversight:** hero-gen defaulting is wired but dormant (Open Question 3); S4's "check" tier only appears on client-sourced reads (Open Question 2); citystats calibration lives in `localStorage`, not a database (Open Question 4); Task 10's `onDropzone`/`onTypeTag` are the only unimplemented stubs left in the whole plan, and they carry no decision logic of their own.
