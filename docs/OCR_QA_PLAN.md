# Stat-Panel OCR — Production QA Plan (edge cases, unhappy paths, release gate)

**Date:** 2026-08-06 · **Scope:** everything in `docs/plans/2026-08-06-ocr-panel-tdd-plan.md` plus the flow UI per `docs/OCR_UX_FLOW_SPEC.md`.
**Prime directive (house rule):** a WRONG value presented as confidently read is the worst possible failure — strictly worse than "could not read". Every ambiguous case below must resolve to *absent + flagged*, never to a guess. Zero tolerance: any false-confident field found in any QA pass = release blocker, no exceptions.

## 1. Test layers

| Layer | Runner | What it proves |
|---|---|---|
| L1 Unit (per TDD plan Tasks 0–11) | `py -m pytest shell/tests -q` + `node --test shell/app/ocr/client/tests/panel_parser.test.mjs shell/app/ocr/client/tests/flow_state.test.mjs` (explicit files — a bare directory arg breaks on Windows Node) | parser/converter/flow logic, both languages, same golden vectors |
| L2 Real-image benchmark (Task 12, gated on owner PNGs) | `py -m pytest -m benchmark` | engine accuracy ≥99% digits, ZERO false-confident |
| L3 API contract & abuse | pytest against the shell app | gate/caps/sniff/quota/no-persist |
| L4 Flow/UI (mock now, real overlay later) | browser walkthrough protocol (below) | no dead ends, honesty surfaces, both widths |
| L5 Determinism & performance | scripted repeats + timers | byte-stable outputs, budgets |
| L6 Release gate | `PRODUCTION_CRITERIA.md` + shell probes | nothing ships un-gated |

## 2. Image-level edge cases (L2 corpus — collect one fixture per row; owner supplies real captures where possible)

| # | Case | Expected behavior |
|---|---|---|
| I1 | Clean captures, both accounts, all 3 panel types | status ok, 100% fields, values == golden vectors |
| I2 | Blurry/motion-blurred capture | unreadable fields listed; NO wrong value in `stats` |
| I3 | Cropped mid-row (top or bottom row half-visible) | partial; the cut row absent or flagged, never misread |
| I4 | Two overlapping screenshots of one long panel | stitched; duplicated rows deduped; equal values merged |
| I5 | Two overlapping screenshots where OCR disagrees on one duplicated row | that field CONFLICT-flagged, absent from stats, warning surfaced |
| I6 | Wrong screenshot entirely (hero screen, chat, home city) | panel_type "unknown" → E1 wrong-variant flow |
| I7 | Correct panel but different phone resolution/aspect (short + tall devices) | normalized coords keep pairing correct |
| I8 | Notch/status-bar/system-UI overlapping the panel top | header rows ignored; class rows unaffected |
| I9 | JPEG re-compressed via messenger (WhatsApp/WeChat artifacts) | still ≥99% digits or honestly partial |
| I10 | Screenshot with game rendered in non-EN locale | v1: rows unmatched → "unknown row" per row, clean partial/failed; NEVER mis-mapped |
| I11 | Dark-mode / night-tinted variant (if the game has one) | color-channel split still classifies green/red or falls back to geometry with `col_conflict` honesty |
| I12 | EXIF-rotated image (phone saved landscape) | auto-orient before OCR; rows parse |
| I13 | Extremely large image (12k×12k, decompression bomb) | rejected pre-decode by pixel-count cap → 413/422, server stays healthy |
| I14 | Animated/webp/HEIC container | 415 unless decoded safely; never crash |
| I15 | Battle report where one side's column is partially cut off | cut side partial; other side unaffected |
| I16 | Special-bonus sub-panel screenshot alone | specials parsed; class stats absent; flow explains what's still needed |

## 3. Parser/converter edge cases (L1 — each is a unit test; most already in the TDD plan)

| # | Case | Expected |
|---|---|---|
| P1 | Digit confusions 0/O, 1/l, 5/S, 8/B inside VALUES | impossible by construction: value pass digit-whitelisted; a letter in a value token ⇒ parse_value None ⇒ unreadable |
| P2 | Letter confusions inside LABELS ("lnfantry") | fuzzy skeleton match ≤2 edits resolves; beyond that → unmatched row |
| P3 | Thousands separators + decimals ("4,491.6%") | parses 4491.6 |
| P4 | EU-style "1.234,5%" | REJECTED (None) — never guessed (v1 EN) |
| P5 | Missing % on a signed value | accepted as pct (game values are always %), `signed` retained |
| P6 | Unsigned bare integer ("188,900") | unit "int" (meta rows like Deployment Capacity), never enters class stats |
| P7 | Negative where impossible (e.g. "-4491.6%" on a class row) | converter/validator range check flags it unreadable (plausible range 0–6000 for class rows; penalties −25..0) |
| P8 | Label wraps to two lines ("Defender Troops Attack When / Defending Own City") | row-grouping merges by y-proximity; canonical matches |
| P9 | Two-column: color info missing entirely | geometry-only sides; no crash; `col_conflict` never falsely set |
| P10 | Two-column: green/red disagree with geometry | color wins + `col_conflict` flag (visible downstream) |
| P11 | Duplicate label rows in ONE screenshot (scroll bounce) | same stitch conflict rules apply within a shot |
| P12 | Specials: unknown special label | preserved as unmatched warning; folds computed from KNOWN rows only; conversion marked "partial folds" warning |
| P13 | Specials: item ±20% war-buff rows present | folded into S sets per law (additive with pets/widgets) |
| P14 | Account with NO pet rows (account B, real) | folds degrade gracefully — verified by golden vectors |
| P15 | Older-era panel without pet enemy-penalty rows | same as P14 (GAME_RULES:277) |
| P16 | Battle→scout conversion when special panel screenshot was NOT provided | conversion refuses (needs folds); UI asks for the special-bonus screenshot or falls back to raw battle values EXPLICITLY LABELED as unconverted — never silently wrong-mode |
| P17 | City-Stats path with no U calibration stored | explicit "needs one-time setup" state; never a made-up U |
| P18 | U calibration on inconsistent panels (mixed account state) | `CalibrationError` surfaced as "these two screenshots don't match — retake both" |
| P19 | Reconciliation: battle + scout both supplied and disagree beyond 0.11 pp after conversion | field-level mismatch flag; user sees both numbers and picks; nothing auto-chosen |
| P20 | Determinism | same bytes → byte-identical JSON (hash compare, 3 runs) — includes dict ordering |

## 4. API/abuse unhappy paths (L3)

| # | Case | Expected |
|---|---|---|
| A1 | Free-tier user calls `/shell/ocr/panel` | 403 `ocr_not_available_on_free` (server-side; UI hiding is not the control) |
| A2 | Paid user exceeds daily OCR quota | 429 with reset time; friendly UI copy |
| A3 | Body over `MAX_BODY_BYTES` | 413 before full read (Caddy cap + app cap — shell eval F4 fix is a PREREQUISITE) |
| A4 | >3 files in one request | 422 |
| A5 | MIME spoof (exe bytes named .png) | 415 via magic-byte sniff |
| A6 | Malformed multipart / empty file | 422, no stack trace in body |
| A7 | Concurrent uploads beyond server semaphore (2) | queued or 503 `busy_try_again`, box never wedges (load test: 20 parallel × 5 MB) |
| A8 | Unauthenticated call | 401 (same auth dependency as `/shell/ocr`) |
| A9 | Image persistence audit | after any request (success/failure/crash-path), NO image bytes on disk, none in logs (grep run artifacts for base64/PNG magic) |
| A10 | Double-submit (same request twice quickly) | both succeed idempotently or second is deduped; quota decremented sanely |

## 5. Flow/UI unhappy paths (L4 — walkthrough protocol per build; mock now, real overlay later)

| # | Case | Expected |
|---|---|---|
| F1 | Cancel mid-scan | lands on Add-screenshots, no auto-advance resurrection (proven pattern: timed screens share one history slot) |
| F2 | Back from review | last deliberate screen; checking work preserved; uploads preserved |
| F3 | Wrong screenshot | E1 wrong-variant; failed upload removed WITH notice; Continue disabled until new upload |
| F4 | Partial read (N of 24) | E1 partial-variant; both exits work; missing fields inline on review, gold-highlighted; tally honest everywhere including battle-setup screen |
| F5 | All-fields-unreadable | failed state → E1; "Type them in myself" path fully manual; CTA never dead-ends |
| F6 | Battle-covers-both, then per-side override | coverage logic per flow_state tests; no silent upload loss ANYWHERE (twice a blocker in mock QC — regression-test every mode/type transition) |
| F7 | Free-tier user sees entry point | upgrade explanation, not a broken button (per D1) |
| F8 | Client engine fails to load (WASM unsupported/OOM/offline) | automatic server-fallback offer; if that fails, manual typing — three-step degradation, each explained in one plain sentence |
| F9 | Engine download interrupted mid-fetch | retry affordance; no corrupted-cache lockout (cache-bust on failure) |
| F10 | Hero defaulting when report shows unknown/new generation | hero slots left empty + "pick your heroes" prompt; NEVER a wrong-gen default |
| F11 | Reset/Undo semantics | Reset restores as-scanned after confirm; Undo restores pre-run snapshot; both truthful in copy |
| F12 | Accessibility pass | focus-to-heading, Escape/inert on sheets, ≥44px targets, aria provenance labels ("You typed this" vs "Read from your screenshot") |
| F13 | Both widths | full flows at 375×812 and ≥1280px; zero horizontal scroll; desktop stepper-rail jumps correct |

## 6. Determinism & performance budgets (L5)

- Determinism: 3 identical runs per fixture image per engine → identical JSON hash. Client and server parsers → identical output for identical token input (cross-language vector suite is the guard).
- Budgets (fail the gate if p95 exceeds): client OCR ≤ 5 s/screenshot on a 2019-class Android (mid device); server RapidOCR ≤ 2 s/image at concurrency 2 on the VPS; parser+converter ≤ 50 ms; WASM+model lazy-load ≤ 8 MB, fetched once, cached (verify cache hit on second run).
- Memory: client peak ≤ 300 MB during scan (old-device OOM guard → server fallback F8).

## 7. Release gate (production reliability)

1. All L1 suites green (Python + node), including golden-vector cross-language parity.
2. L2 benchmark: digit accuracy ≥ 99% AND zero false-confident fields across the full fixture corpus (owner decision D2: if unmet, ship WITHOUT the high-confidence tier — fields become "please check" — rather than weaken the bar).
3. L3 abuse suite green; shell F4 (body caps) verified fixed FIRST — prerequisite from `shell/EVAL_ROUND_1.md`.
4. L4 walkthrough protocol executed on real devices: 1× iOS Safari, 1× Android Chrome, 1× desktop Chrome ≥1280px — checklist F1–F13 signed off.
5. L5 budgets met; determinism hashes stable.
6. `wos_sim/predictor/tests/test_ui_style_guard.py` still green (prototype/index.html untouched by construction).
7. Standard repo gates: `py -m wos_sim.backtest` unchanged (no engine files touched — verify via `git status wos_sim/`), full `py -m pytest` suite green.
8. Every item of `PRODUCTION_CRITERIA.md` for anything promoted toward WOSTests.com; shell probes (`shell/probes/run_probes.py`) extended with: free-tier-403 probe, oversize-413 probe, sniff-415 probe, panel-mock-200 probe.
9. Sign-off: owner clicks through the real flow once on his own account's screenshots (both his characters are already golden-vectored) and the numbers match his panels exactly.

## 8. Standing QA rules

- New fixture screenshots are added to the corpus whenever: the game UI updates, a new locale ships, a new device class appears in support requests, or ANY field misread reaches production (that misread becomes a permanent regression fixture — same philosophy as the engine's golden-anchor guardrail).
- The label lexicon is versioned data (`lexicon.py` constants); a game UI rename = data patch + fixture + release-gate rerun, not a code refactor.
- Any relaxation of `LOW_CONF`, the fuzzy-match bound (≤2), or value-range checks is an owner decision, never a convenience fix to make a test pass (no-fudge house rule applies to OCR too).
- **QA-ing the paid flow in dev (L4 walkthrough):** `DEV_BYPASS` mode (no `CLERK_SECRET_KEY` configured) mints every request `UserCtx(user_id="dev_user", plan="free")` unless the request carries an `X-Dev-Plan` header (`shell/app/auth.py`), which is honored ONLY in bypass mode and never in real mode (hostile-client rule, COMPASS invariant 6) — so it is not a backdoor into production. **Amended 2026-08-15 (owner decision):** the bypass-mode DEFAULT is now `settings.dev_default_plan` — **"pro" when `ENV=dev`** (localhost works without the plan gate; no header needed for paid-flow QA), hard-collapsed to "free" in any other ENV (`PRODUCTION_CRITERIA.md` C6 gates the leak-proofing). The header still overrides in both directions in bypass mode — **`X-Dev-Plan: free` is now the technique for QA-ing the FREE path** (plan gate, 402 signal) in dev. To walk the F1–F13 gate as a paid account without a real Clerk session or product code change, add the header client-side for the duration of the browser session via a console fetch wrapper: `const f = window.fetch; window.fetch = (u, o) => f(u, { ...o, headers: { ...(o && o.headers), 'X-Dev-Plan': 'pro' } });`. This is the sanctioned technique — it exercises the real `/shell/me`, `/shell/ocr/panel`, and quota/entitlements paths under a genuine pro identity, unlike stubbing `fetch` to fake a response body (useful for isolating one screen, but bypasses the real server entirely).
