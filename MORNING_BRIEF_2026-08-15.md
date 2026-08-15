# MORNING_BRIEF — overnight run 2026-08-14 → 08-15

## TL;DR

Everything you asked for at bedtime is done, and the loop ran to completion:

- **The app is running at http://localhost:8200 with OCR fully intact** — final proof drive on the shipped build: battle screenshots → 1 network call → **12/12 My-side values digit-exact** against the golden scout-net table, 12/12 Enemy-side filled, `statsScouted` set, honest completion chip.
- **QA2 found 1 BLOCKER + 2 Major + 2 Minor → all five fixed the same night**, then an independent sub-agent re-ran the QA scripts: **ALL FIXES HOLD**.
- **The full MORNING_BRIEF shell fix round you approved ran end-to-end**: agents A–D closed every brief item; evaluator round 2 said NOT APPROVED (3 new Criticals, 6 Majors — mostly cross-agent integration gaps and round-1 leftovers nobody owned); a fix pass closed all of them; **evaluator round 2B: APPROVED, zero Critical, zero Major**. Merged to master.
- **Suites on final master: 518 shell / 206(+2xf) predictor / 150 node (149+1 documented skip) / 7 style guard; G12 backtest PASS** (run twice, once independently by the evaluator).

## The one thing worth reading before you test

**QA2's blocker (D-043) changed real behavior, for the better:** the battle/scout stat panel and the specials list are **two different screens** — the specials live in the "Notes on Special Bonuses" popup behind the little **!** icon next to the "Stat Bonuses" title. Before tonight, uploading just the main panel silently *pretended* the account had zero specials and could mis-convert by up to **367pp** (masked on your Marlinman account by a numeric coincidence — that's why six earlier QA rounds never saw it). Now: the upload screen tells you battle needs both screenshots, a main-panel-only upload reads fine but **refuses to fill**, says why on the completion chip, and leaves your typed numbers alone. `docs/OCR_TEST_INSTRUCTIONS.md` §3 step 6 walks the variant.

## How to test (5 minutes)

Open http://localhost:8200 (already running; if you ever restart it yourself:
`py -m uvicorn shell.app.main:app --port 8200 --env-file shell/.env` from the repo root — the
`--env-file` flag is what loads the Gemini key). Then follow `docs/OCR_TEST_INSTRUCTIONS.md`:
DevTools pro-header one-liner, upload `C_battle_3.png` + `C_battle_4.png` from
`shell\tests\fixtures\panel_ocr\images\`, expect the exact 12-value table in §3.

## What landed overnight (by commit area)

1. **QA2 fixes** (`7e27978`…`f11000a`): D-043 popup-evidence semantics (py+JS lexicons, ground-truthed from RapidOCR's own read of the popup fixture), D-044 honest chip + per-side "not filled in" notices + no phantom `statsScouted` flip, D-045 doc/UI copy (two screens, `!` icon), D-046 benchmark gate asserts RapidOCR **by name** (re-ran: 100% digits, 0 false-confident), D-047 eight new adapter unit tests. Ledger: `shell/EVAL_OCR_PANEL_QA2.md` (report + resolution + verification sign-off).
2. **Shell fix round** (merge `c693b16`, evidence `shell/EVAL_ROUND_2.md`): pro-plan wiring real (F3 — paying users actually get pro quotas now), route-aware body caps at app **and** Caddy edge, docs endpoints closed outside dev + actively probed, single-point OCR metering (a double-count was silently halving pro quota), honest `/shell/me` quota meter, JWKS backoff, `assets_prod` mounted with icon fallback, sweep scheduler running, signout/Accept-gate/webhook/CORS/pins, ingestion skill in Docker + promote bundle with completeness gates, probe suite de-contaminated (17 PASS / 0 FAIL / 4 honestly-reasoned SKIPs).
3. **Predictor** (`ba2f2c1`): malformed panel key → clean 400 instead of a quota-burning 500 (found by agent D, promoted Critical by the evaluator; G12 PASS, engine untouched).

## Waiting on you

1. **Push to origin?** Master is ~95 commits ahead locally; nothing was pushed (a push may trigger deploy). Say the word.
2. **THIRD_PARTY_SETUP registrations** (~60–90 min manual): Clerk, Supabase, Stripe, VPS/DNS — the fix round made the shell ready for real keys; this is now the critical path to staging.
3. **Claude spend limit**: it killed the evaluator once mid-run overnight (resumed cleanly, nothing lost). Consider raising it before the next multi-agent day.
4. Two old detached worktrees under `.claude/worktrees/` (`ecstatic-moore`, `keen-hawking`) predate tonight — left untouched, delete if you don't recognize them.
5. Minor hardening candidates logged, not urgent: cache-busted module URLs for deploys (stale-module window after releases), `SKILL_INGESTION_DIR` env-only override, benchmark's real-ONNX subset intentionally not duplicated in unit tests.

## Where the evidence lives

`shell/EVAL_OCR_PANEL_QA2.md` (QA2 + resolution + sign-off) · `shell/EVAL_ROUND_2.md` (rounds 2 + 2B) · `docs/OCR_TEST_INSTRUCTIONS.md` (your walkthrough) · `docs/plans/2026-08-15-ocr-qa2-postmerge-charter.md` (QA2 charter) · git log `d03d2ea..HEAD` (every fix is its own scoped commit).
