# OCR feature — hands-on test instructions (owner walkthrough)

> **Audience:** Martin. **Status:** written at merge time (2026-08-15), when the L4 gate closed
> (`shell/EVAL_OCR_PANEL_QA1.md`, HEAD `73e6bd9` + recovery-notice nit fix). Everything below was
> executed live against the real app before being written down.
>
> **What you are testing:** screenshot → server OCR (RapidOCR, Gemini gap-fill fallback) →
> three-panel-law conversion to scout-net → simulator form filled. Server-only v1: no OCR runs in
> the browser. The engine (`wos_sim/`) is untouched by this feature.

---

## 1. Start the app

From the repo root (PowerShell):

```bash
py -m uvicorn shell.app.main:app --port 8200 --env-file shell/.env
```

- `--env-file shell/.env` matters: that file holds `GEMINI_API_KEY`, and settings read `.env`
  relative to the *working directory* — without the flag the app boots keyless, which still works
  but silently runs **RapidOCR-only** (no Gemini gap-fill on weak fields).
- No Clerk key in `shell/.env` ⇒ the app is in `DEV_BYPASS` mode: every request is
  `dev_user, plan=free`. That is what you want for testing (next step upgrades you to pro).
- Open **http://localhost:8200/** — the normal predictor page, with a **“Fill from screenshots”**
  button above the input form. Stop the server later with `Ctrl+C`.

## 2. Plan handling on localhost (updated 2026-08-15)

**You are Pro by default on localhost — no setup needed.** Dev mode (`ENV=dev`, keyless
`DEV_BYPASS`) now mints `plan="pro"` automatically (owner decision 2026-08-15;
`dev_default_plan` in `shell/app/config.py`), so the OCR flow works directly without the
"see plans" gate. This default is **ENV-gated**: in staging/prod it hard-collapses to
"free" no matter what is configured, so production always serves the plan gate
(`PRODUCTION_CRITERIA.md` item C6 verifies exactly this at release time).

To test the **free-tier** experience (plan gate, manual-only path, 402), paste this in
DevTools (F12) — the header works only in dev bypass mode, never in production:

```js
const f = window.fetch; window.fetch = (u, o) => f(u, { ...o, headers: { ...(o && o.headers), 'X-Dev-Plan': 'free' } });
```

Pro OCR quota is 30 reads/day — each successful read consumes one; `/shell/me` shows the
real remaining count.

## 3. Happy path — battle report, digit-exact fill

Fixture screenshots live in `shell\tests\fixtures\panel_ocr\images\` (account C = your
[Lns]Marlinman capture set; the untouchable ground truth is `golden_vectors.json` next to them).

1. Click **Fill from screenshots** → pick **Battle Report**.
2. Upload **`C_battle_3.png` and `C_battle_4.png`** together. These are **two different screens**
   (QA2 D-045 corrected an earlier version of this step): `C_battle_3` is the complete
   "Stat Bonuses" class-stat panel (all 12 rows, both columns), and `C_battle_4` is the separate
   **"Notes on Special Bonuses" popup**, reached in-game by tapping the small **!** icon next to
   the "Stat Bonuses" title. **Both are required**: without the popup the app now refuses to
   convert (D-043) and tells you so, instead of silently treating the account as specials-free.
   One battle upload feeds *both* sides — the panel has My/Enemy columns.
3. Continue → reading screen → review. Accept → the simulator form fills, exactly **one** network
   call to `/shell/ocr/panel` (check the Network tab if curious).
4. **Expected — digit-exact.** “Stats are scouted values” (`#statsScouted`) is checked, and *My*
   side shows the battle numbers converted to scout-net:

   | My side | Attack | Defense | Lethality | Health |
   |---|---|---|---|---|
   | Infantry | 2269.7 | 2151.7 | 1126.5 | 1129.0 |
   | Lancer | 2189.6 | 2064.1 | 1103.7 | 1058.4 |
   | Marksman | 2385.8 | 2240.6 | 1263.9 | 1257.3 |

   The Enemy side fills from the right-hand column of the same screenshots (24 filled fields
   total; the enemy here is the no-hero 1-troop poke, zero specials). The exact 24-value
   measurement is recorded in the L4 closure entry of `shell/EVAL_OCR_PANEL_QA1.md`.
5. A provenance chip on the review/battle screen says the values came from screenshots; **Undo**
   reverts the fill.
6. **Missing-popup variant (D-043/D-044 behavior):** run the same flow with **only
   `C_battle_3.png`**. All 24 numbers read cleanly, but the completion chip reports
   *"…not filled in — tap to check"* with a notice card per side explaining the Special Bonuses
   popup is missing, and **no simulator field changes** (whatever was typed before stays). The
   upload screen also warns up front that Battle Report needs both screenshots.

**Any mismatch with the table above is a release blocker, not a rounding nit** — file it in the
ledger and stop (no-fabrication rule: the feature must never present a confident wrong number).

## 4. Typed overrides win

On the review screen, type over any field (e.g. set My Infantry Attack to `1234.5`), then accept.
That field keeps **your** number; every other field keeps the converted OCR value. This is
per-field, not all-or-nothing (defect D-042's regression).

## 5. Wrong-screenshot recovery

1. Start over → **Battle Report** → upload **`C_battle_1.png`** (a battle screen, but not the stat
   panel — deliberately the wrong variant).
2. Expected: the friendly error screen (“doesn’t look like the right screenshot”), with
   **Add a clearer screenshot**.
3. Click it → you land back on upload with the bad shot removed and the notice
   *“We took that one out. Add a new screenshot.”*
4. Upload a correct screenshot → the notice **disappears** (the 2026-08-15 nit fix) and the new
   thumbnail appears. Dropzones must stay alive for repeated recoveries (D-041's regression).

## 6. Other panel types

Same flow with the other fixture sets, choosing the matching type on the first screen:

- **City Stats:** `C_citystats_1.png` + `C_citystats_2.png` (two-part scroll, per-side upload).
- **Scout:** `C_scout.png` (single screenshot, per-side upload).

Scout values pass through un-converted (scout *is* the target basis); City Stats convert per the
law in `docs/STAT_PANELS_FORMULA.md`.

## 7. Free tier / quota behavior

- Apply the `X-Dev-Plan: free` wrapper from §2 (localhost is pro by default now): the flow
  offers **manual entry only** — typing values by hand must work end-to-end with no network
  OCR call, and the manual path fills the form the same way (user-typed values win).
- The 31st pro read of a (UTC) day returns the standardized `payment_required` signal (HTTP 402)
  and the UI degrades to manual — no crash, no half-filled form.

## 8. Suites and benchmarks (before/after any change)

```bash
py -m pytest shell/tests -q
```
Expected: **341 passed**.

```bash
py -m pytest wos_sim/predictor/tests/test_ui_style_guard.py -q
```
Expected: **7 passed** (prototype/index.html is untouched by this feature).

Node client tests — file list is explicit because `node --test <dir>` breaks on Windows Node 24:

```bash
node --test shell/app/ocr/client/tests/flow_state.test.mjs shell/app/ocr/client/tests/panel_parser.test.mjs shell/app/ocr/client/tests/api_samples.test.mjs shell/app/ocr/client/tests/convert_side.test.mjs shell/app/ocr/client/tests/fill_mapper.test.mjs shell/app/ocr/client/tests/error_copy.test.mjs shell/app/ocr/client/tests/screens_entry.test.mjs shell/app/ocr/client/tests/screens_reading.test.mjs shell/app/ocr/client/tests/controller.test.mjs shell/app/ocr/client/tests/screens_pick_upload.test.mjs shell/app/ocr/client/tests/screens_review.test.mjs shell/app/ocr/client/tests/screens_setup.test.mjs shell/app/ocr/client/tests/ocr_flow.test.mjs
```
Expected: **144 tests, 143 pass, 1 skipped** (documented skip), 0 fail.

Real-engine benchmark (opt-in, slow — loads RapidOCR models; Gemini cases need the key):

```bash
py -m pytest -m benchmark shell/tests/test_ocr_panel_benchmark.py -q -s
```
Gate D2 bar: 100% digit accuracy, **zero false-confident fields** (a confident wrong read is the
only unforgivable failure).

## 9. If something looks wrong

1. Check `shell/EVAL_OCR_PANEL_QA1.md` — 42 defects (D-001..D-042) are already catalogued with
   regression tests; what you found may be a known non-goal or an already-fixed pattern.
2. OCR anomaly rule applies to fixtures too: if a number defies physics, suspect the screenshot
   read before the law (`docs/STAT_PANELS_FORMULA.md` is CONFIRMED zero-fudge on 3 accounts).
3. New misread reaching you = permanent regression fixture (QA plan §8) — save the screenshot
   into the fixtures folder and note it in the ledger.
