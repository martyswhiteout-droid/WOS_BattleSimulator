# OCR UX Journey — Evaluator Report

> Standing evaluator loop per `docs/plans/2026-08-15-ocr-ux-journey-loop-charter.md`. One section
> per round, append-only. The evaluator judges; it never fixes and never commits.

---

## ROUND 1 — 2026-08-15

### VERDICT: NOT SATISFIED

**0 JOURNEY-BLOCKER · 6 MISMATCH · 0 FRICITON (open) · 0 POLISH (open)**

*(one FRICTION-shaped observation is folded into UXJ-003 as impact evidence rather than
double-counted; one previously-documented POLISH nit was re-tested and no longer reproduces —
see Coverage log.)*

The core mechanics are in very good shape — digit-exact fill, the D-043/D-044/D-045 honesty
fixes, Undo, Reset, the tap-to-edit editor, and the free-tier gate all held up under a fresh,
adversarial pass. But six real, evidenced divergences from the PRD/mock remain, one of which
(UXJ-004) is a genuine honesty problem the prior QA rounds never surfaced: HTTP errors that occur
*during* a screenshot read (quota exhausted, burst-limited, payment lapsed, engine busy, session
expired) are all currently mis-presented to the user as "that doesn't look like the right
screenshot" — a fabricated cause, not just a missing one.

---

### Findings

#### UXJ-001 — MISMATCH — S0 entry CTA renders after the entire manual formation panel, not above it

**PRD citation:** §3 S0 — *"'📷 Fill from screenshots' CTA ABOVE the existing manual form; the
manual form below is labeled as today's form."*

**Mock:** S0 is its own screen; the CTA is the first thing on it, with "or type it yourself" and
a de-emphasized "TODAY'S FORM" section below.

**Observed (real app, `http://localhost:8200`):** the CTA (`#ocrfCtaScreenshots`) is real,
visible, enabled, and correctly wired (a genuine pointer-event click on it does navigate to S1;
the earlier `read_page` accessibility-tree miss on this button was chased down and is a tool-side
snapshot quirk, not a reachability bug — `elementFromPoint` at the button's on-screen center
returns the button itself once scrolled into view, and a real click works). The problem is purely
placement: on desktop (1280×720) the button's top edge sits at **y=741.6px — already below the
fold** (viewport height 720). On mobile (375×812) it sits at **y=1389.5px — 1.7 screen-heights
down**. A first-time user must scroll past the full "MY SIDE / ENEMY" role toggle and all six
Troops-Formation sub-panels (My/Enemy × Infantry/Lancer/Marksman, each with FC/Tier/count
dropdowns and a slider) before the "fastest way, no typing" pitch ever appears — i.e. past
exactly the tedious manual UI the feature exists to let them skip.

**Mechanism:** `shell/app/ocr/client/screens/entry.mjs`'s `mountEntry()` (lines 30-39) anchors on
`root.getElementById('statPanel')`, then `anchor = statPanel.closest('.iblock') || statPanel`.
`#statPanel` has no `.iblock` ancestor (confirmed: its ancestor chain is
`.tabpanel > .tabpanels > .tabgroup.input-tabs > section.input`), so the fallback fires and the
card ends up inserted as a direct child of `section.input`, immediately after
`div.tabgroup.input-tabs` (confirmed via direct DOM inspection: `ocrfEntry.previousElementSibling`
= the tabgroup, `nextElementSibling` = the hero-selection block) — i.e. after however tall the
*currently active* Troops-Formation/Stats/Buffs tab happens to be, not above the form.

**Expected vs observed:** expected the CTA to be the first thing a user sees on/near the top of
the page (per PRD + mock); observed it requires scrolling past the entire troop-formation control
surface first, on both desktop and (worse) mobile.

---

#### UXJ-002 — MISMATCH — S1 and S2 are missing the "faithful mini-renderings" of the real panels

**PRD citation:** §3 S1 — *"3 cards with faithful mini-renderings of the real panels."*

**Mock:** every S1 card (Battle Report / Scout Report / City Stats) carries a `mini-panel` with
realistic-looking stat rows (e.g. Battle Report's card shows a two-column "MY SIDE / ENEMY"
preview with rows like `+4859.0% Infantry Attack +694.3%`). S2's per-side sections repeat the
same `mini-panel--battle` preview above each dropzone, and each dropzone itself carries an SVG
camera/upload icon (`.dz-icon`).

**Observed (real app):** S1 cards contain only a ribbon/tag badge, `<h2>` title, `<p>`
description, and breadcrumb span — zero `<img>`/`<svg>` anywhere in any of the three cards
(confirmed via full `outerHTML` dump of the S1 screen). S2's side-sections go directly from the
type-tag dropdown to the dropzone button — no mini-panel preview — and the dropzone itself has no
icon at all (`<button class="ocrf-dropzone"><b>Tap to add your screenshot</b><span>or paste it
here</span></button>`, no SVG child), unlike the mock's dropzone which includes one.

**Expected vs observed:** expected a visual "does this look like what's on my screen" reference
on both S1 (mandated by name in the PRD) and S2 (mock-only, but an unexplained divergence per the
charter's authority order); observed text-only cards and bare dropzones throughout.

---

#### UXJ-003 — MISMATCH — S3's "candy-stripe progress" is not implemented; the reading screen goes completely static during long reads

**PRD citation:** §3 S3 — *"on-device scanning, candy-stripe progress, honest step narration...".*

**Mock:** `.scan-fill::after` runs `animation: scan-stripes .7s linear infinite` (a continuously
moving diagonal-stripe fill, regardless of how long the wait is) plus `@keyframes step-pulse` (a
pulsing glow on the active step).

**Observed (real app):** `shell/app/ocr/client/ocr_flow.css` contains **zero `@keyframes` rules
of any kind** (confirmed by grep across the whole file — the only animation-related rule at all is
the correctly-scoped `@media (prefers-reduced-motion:reduce)` kill-switch, which has nothing to
disable because there is no motion to begin with). `.ocrf-scan-fill` is a flat gradient that jumps
between three discrete widths (one per step) via `transition:width .3s linear` and otherwise never
moves.

**Why this matters in practice (live-measured, not theoretical):** uploading a deliberately
wrong-variant screenshot (`C_battle_1.png`) causes RapidOCR to fail to detect the panel type,
which escalates to a Gemini gap-fill attempt, which in this run **timed out** — the real response
body's `warnings` included `"gemini fallback skipped: gemini extraction failed: network error
calling Gemini (gemini-3-flash-preview): The read operation timed out"`. Wall-clock time from
clicking Continue to reaching E1 was measured at roughly **45-70 seconds**. `reading.mjs`'s
`driveScan()` correctly never claims false completion (the last step stays "active," not "done"),
but for that entire 45-70s stretch the user sees a **perfectly static** screen: frozen progress
bar, frozen "Checking both sides…" text, no elapsed-time indicator, no "still working" signal of
any kind. The Gemini engine's own documented latency range is 6.7-62.6s (`EVAL_OCR_PANEL_QA1.md`),
so this is not a rare fluke — it is a known, reachable characteristic of the production ladder.

**Expected vs observed:** expected a continuously-animating progress indicator (per PRD wording
and the mock's implementation) that reads as "still alive" no matter how long the backend takes;
observed a static bar/text that, on the documented long-tail path, sits motionless for up to a
minute.

---

#### UXJ-004 — MISMATCH — HTTP errors during a screenshot read (quota, burst, payment, busy, session) are all mis-shown as "that doesn't look like the right screenshot"

**PRD citation:** §1.3 *"Never fabricate... no guesses"* and the general honesty principle in
§4 (*"Honesty: uncertainty always visible, never blocking dishonestly"*) — this is a fabricated
**cause**, not a fabricated number, but the same principle applies: the app tells the user
something that is not true about why their read failed.

**What's wrong, traced to source:**
- `shell/app/ocr/client/error_copy.mjs`'s `mapError(status, body)` is a well-designed, unit-tested
  function producing distinct, honest, jargon-free copy per failure mode: 402 → *"This needs a
  paid plan..."*, 429 (burst) → *"Slow down a little... Give it a few seconds..."*, 429 (quota) →
  *"That's today's limit... You've used up today's screenshot reads. They come back at midnight.
  You can still type the numbers in."*, 503 → *"The reader is busy right now..."*, 401 → *"Please
  sign in..."*.
- `shell/app/ocr/client/controller.mjs`'s `readSide()` (lines 94-101) correctly catches any
  non-2xx from `/shell/ocr/panel` and computes `{ error: true, mapped: mapError(err.status,
  err.body) }` — this is present on the per-side result inside what `readAll()` resolves with.
- But `shell/app/ocr/client/ocr_flow.js`'s `decideAfterRead()` (lines 445-452) — the function that
  actually decides what the user sees next — takes only `tallyStates` (derived purely from
  per-field OCR readability) and never looks at `.error`/`.mapped` at all. Its rule is
  field-count-only: `readCount === 0` → **`{ screen: 'e1', variant: 'wrong' }`** — the same
  "that doesn't look like the right screenshot" copy shown for a genuinely wrong image. `onReadDone`
  (453-460) stores the full result (including `.mapped`) in `app.lastRead` but never reads
  `.mapped` back out of it. `onReadError` (461) is the same story in miniature: it unconditionally
  hardcodes `app.e1Variant = 'wrong'` regardless of `err`.
- Net effect: a quota-exhausted 429, a burst-limited 429, a mid-session 402 (plan lapsed after the
  entry gate already let the user in), a 503 (engine busy), or a 401 (session expired) occurring
  **during** the S3 read all read zero fields and therefore all land on the exact same "That
  doesn't look like the right screenshot / This looks like a different screen. We need one with a
  numbers list..." copy — even though the screenshot was never the problem.

**Live reproduction (real app code, real DOM, `window.fetch` patched only to return a synthetic
429 for `/shell/ocr/panel` — every other layer is the genuine shipped code):** clicking through
S0→S1(Battle Report)→S2(upload)→Continue with a fake `429 {"error":"quota_exceeded"}` response
lands on `data-screen="e1"` with the text *"That doesn't look like the right screenshot... This
looks like a different screen..."* — not the quota copy. `postPanel` (`ocr_flow.js` line 35-45)
was independently confirmed to correctly convert a non-`ok` `Response` into a thrown
`Error{status, body}`, so the break is specifically in `decideAfterRead`/`onReadDone` ignoring
that information, not in the HTTP layer.

**Severity note:** kept at MISMATCH rather than JOURNEY-BLOCKER because "Type them in myself" is
still offered and still works (no dead end, no lost work) — but this is the most user-harmful
finding of the round: it actively misdirects a quota-exhausted or session-expired user into
retaking/re-selecting screenshots that were never the issue, rather than telling them the true,
already-written, already-tested fix ("wait until midnight," "sign in again," "slow down").

---

#### UXJ-005 — MISMATCH — the S4→S5 transition never moves focus to a heading

**PRD citation:** §5 (engineering patterns "proven in the mock... carried into the real build") —
*"focus-to-heading on navigation."*

**Mock:** every screen's `<h1 tabindex="-1">` is the focus target on arrival. Verified live via
the mock's own natural Next-click path (not the flow-map shortcut, which does bypass focus
management and is a dev/QA tool only): after S4→S5, `document.activeElement` is
`H1#` containing "Battle setup".

**Observed (real app):** `#ocrfS5` (the accordion-style completion screen) has **no heading
element at all** — it opens directly with `.ocrf-stats-accordion` > the chip button. After the
real S4→S5 transition (Next click, not a shortcut), `document.activeElement` is `<body>` — nothing
meaningful receives focus. (S1→S2→S3→S4, which stay inside the `#ocrfRoot` modal, each do carry
their own `<h1 tabindex="-1">`, so this gap is specific to the "close the overlay, return to the
live page" transition, not systemic.) The page does scroll to bring S5 into view, which helps
sighted mouse users, but a keyboard or screen-reader user gets no signal that the page moved at
all.

**Expected vs observed:** expected focus to land on a heading or equivalently clear landmark on
arrival at S5, per the explicitly-named carried-over pattern; observed no heading exists to focus
and focus is left on `<body>`.

---

#### UXJ-006 — MISMATCH — S5's primary CTA reads "Run forecast", not "See who wins →"

**PRD citation:** §3 S5.4 — *"Primary CTA: **'See who wins →'** = the existing forecast
button."*

**Mock:** the S5 screen's primary button is literally labeled `See who wins →` (confirmed via
direct button-text enumeration of the mock's live S5 DOM).

**Observed (real app):** the app's global forecast button — the one the OCR flow relies on and
scrolls the page toward — is labeled `Run forecast` (confirmed both in the page's very first
accessibility snapshot and by locating/clicking it by that exact text). It is **functionally**
correct — clicking it after an OCR fill does fire a fresh `POST /api/predict` using the filled
stats, so "See who wins → continuity" works end-to-end — only the label itself never changes to
match the PRD/mock wording, in the OCR-arrival context or otherwise.

**Note for the builder:** the PRD phrasing ("= the existing forecast button") is slightly
ambiguous between "rename the existing button to this text" and "this is what we're calling the
existing button for documentation purposes." The mock resolves the ambiguity — it renders the
literal string "See who wins →" — but whether the real fix should be a permanent app-wide rename
or an OCR-arrival-only relabel is a product call this report doesn't presume to make.

---

### What held up well (verified, not just re-asserted from the ledgers)

- **D-043/D-044/D-045 (missing-popup honesty chain):** live-reproduced end to end. Uploading
  `C_battle_3.png` alone (no specials popup) correctly reads all 24 raw fields but the S5 chip
  reads *"All 24 numbers read · your side and the enemy side not filled in — tap to check"*
  (class `ocrf-needs-attention`, not `ocrf-complete`), with per-side notice text *"We read your
  side's numbers, but didn't fill them in: the Special Bonuses screenshot for this side is
  missing — in the report, tap the ! next to 'Stat Bonuses' and screenshot that popup. Anything
  you typed yourself was kept."* `#statPanel` was confirmed **not** silently overwritten with a
  wrong identity-converted value. The S2 popup-hint card naming the "!" icon (D-045) is present
  and correctly worded. This is real, working, and is a genuine improvement over the mock (which
  never modeled this case) — correctly not treated as a mismatch per the charter.
- **Digit-exact fill:** confirmed twice independently (once desktop, once mobile-width), both via
  a real `C_battle_3.png`+`C_battle_4.png` upload through RapidOCR — all 24 `#statPanel` inputs
  matched the server response's `stats_you`/`stats_enemy` to the digit.
- **S4 editor (tap-to-type-over):** provenance labels correct and update live ("Read from your
  screenshot" ↔ "You typed this"); Save/Cancel work; Reset's two-tap confirm
  (`Reset` → `Really reset?` → clears) works and correctly restores as-scanned values +
  provenance.
- **"See my screenshot" / picture view:** confirmed to be a stylized text recreation in *both* the
  real app and the mock (not a literal photo in either) — not a mismatch, just how the feature is
  designed.
- **S5 Undo ("Put my last numbers back"):** confirmed working — restores the pre-run
  `#statPanel` snapshot exactly.
- **D-041 (post-recovery dropzones):** confirmed alive — after E1's "Add a clearer screenshot"
  exit, the You dropzone accepts a new upload immediately, no dead zone.
- **D-042 (manual path merge):** confirmed — a value typed manually on an empty S4 field survives
  into `#statPanel` on Next, without requiring a successful conversion elsewhere.
- **The previously-documented "recovery notice persists after replacement" nit** (noted as an
  accepted, unfixed cosmetic item in `EVAL_OCR_PANEL_QA1.md`'s L4 gate closure) **no longer
  reproduces**: uploading a replacement screenshot after an E1 recovery correctly clears the "We
  took that one out" notice. Not re-filed as a finding; noted here for the record since it
  contradicts a standing ledger entry.
- **Free-tier gate:** `X-Dev-Plan: free` correctly returns `402 payment_required` from
  `/shell/ocr/panel` at the API level, and the S0 CTA correctly shows the upgrade sheet ("This
  needs a paid plan... Typing the numbers in yourself is always free. / Type it in myself / See
  plans") when the plan check reports free; "Type it in myself" correctly closes the sheet back to
  a clean, usable entry state.
- **Type dropdowns:** "You" side offers City Stats / Scout Report / Battle Report; "Enemy" side
  correctly omits City Stats (self-only), matching §2 exactly.
- **Battle-covers-both-sides:** uploading a Battle Report to one side correctly marks the other
  "✓ Covered by your battle report / Add your own screenshot instead", matching the mock verbatim.
- **Mobile (375×812):** no horizontal overflow detected at any screen (S1-S5) during a full happy
  path; console clean of new errors.

---

### Coverage log

| Area | How verified |
|---|---|
| S0 entry (copy, CTA reachability/click) | Live, desktop + mobile. Finding UXJ-001. |
| S1 type pick, all 3 types' copy | Live text dump, real app vs mock, byte-level copy match confirmed for headings/badges/breadcrumbs. Finding UXJ-002 (mini-renderings). |
| S2 upload (hints, thumbs, remove, dropdown, both-sides coverage) | Live: real fixture uploads via the documented CORS-fixture-server + captured-picker technique; type-dropdown menus for both sides; thumb add/remove; D-045 popup-hint text confirmed present and correctly worded (verified NOT present in mock, confirming it's a ledger-documented improvement, not a mismatch). |
| S3 reading | Live, including the long-tail Gemini-timeout path (measured ~45-70s). Finding UXJ-003. |
| S4 review (field states, editor, provenance, Reset, picture view) | Live: full editor Save/Cancel cycle, two-tap Reset, "See my screenshot" on both real app and mock (source-code-confirmed both are stylized recreations, not photos). |
| S5 (chip truthfulness, expand, Undo, Reset, hero/role/CTA) | Live: chip text for both the clean-complete and needs-attention cases; expand/collapse; Undo; CTA label (UXJ-006); focus handling (UXJ-005). Hero-captain gen-badge defaulting **not** exercised — the Battle Report "Stat Bonuses" panel used for every live read in this round carries no hero-portrait/gen-badge data to default from (confirmed: the raw OCR response has no gen/hero fields), so "no default applied" is correct-for-this-input, not a tested pass/fail of that specific PRD line. Would need a screenshot type that actually shows hero badges to exercise it. |
| Form filled correctly / "See who wins" continuity | Live, twice (desktop + mobile): digit-exact `#statPanel` match to the server response; a fresh `POST /api/predict` fires and returns 200 after clicking the forecast button. |
| E1 wrong-screenshot (both exits) | Live, `C_battle_1.png` (twice, once per exit): "Add a clearer screenshot" → S2 with notice + live dropzone (D-041 held); "Type them in myself" → S4 inline, 0/24, all fields `— —`/`+`, Next enabled per spec. |
| E1 partial-read variant copy | **Not live-reproduced** — no fixture in the panel_ocr corpus naturally produces a genuine partial read (all clean fixtures read either fully or not at all). Verified instead via source + passing unit tests: `screens_pick_upload.test.mjs` asserts the exact mock copy ("We read N of 24 numbers...") is computed from the real count, not hardcoded; `D-038`'s regression test specifically guards the 0-of-24 edge case against being misrouted into this variant. |
| Missing-popup refusal (D-043/D-044) | Live, `C_battle_3.png` alone. Confirmed correct — see "What held up well." |
| Manual "Type them in myself" floor | Live — combined with the E1 "Type them in myself" exit above; one field hand-typed and confirmed to survive into `#statPanel` on Next (D-042). |
| Free-tier plan gate | Live at both layers: `curl -H "X-Dev-Plan: free"` → API-level 402; browser-level via a `fetch` patch on `/shell/me` only (`X-Dev-Plan: free` injected client-side, every other request untouched) → upgrade sheet shown and dismissible. |
| Quota-exhaustion messaging | **Not live-reproduced by draining real quota** (would have cost ~25-30 real reads for a single confirmation). Verified instead two ways: (1) source read of `error_copy.mjs`'s 429-quota copy, unit-tested; (2) a live `fetch`-level 429 simulation against the real S2→S3 flow, which is what surfaced UXJ-004 — the quota-specific copy exists but is provably never reached by the current routing logic, regardless of how the 429 is produced (real exhaustion would hit the identical broken path). |
| Mobile-width pass (375px) | Live, full happy path (S0 reachability measured, S1→S5, digit-exact fill, no horizontal overflow at any screen, console clean). |
| Console/network cleanliness | Checked after every screen transition throughout. Four stale `429`/`402` console errors were present in the tab **before this evaluation's first action** (pre-existing from an earlier session that had the tab open; corroborated by a matching-count, never-growing total across every subsequent check, and by every live network request in this round's own traffic returning its expected status). Not attributed to anything exercised in this round. |

### Quota consumed

`dev_user`: **5 real OCR reads** this round (30 → 25 remaining) — 1 happy-path (desktop), 2×
wrong-variant (`C_battle_1.png`, once per E1 exit), 1 missing-popup (`C_battle_3.png` alone), 1
happy-path (mobile). `ux-eval`: untouched, 30/30 still available for a future round.
Sim quota (`dev_user`): 100 → 59 (incidental, from clicking the real forecast button during
journey checks).

### Servers left running (for the next round)

- `py -m http.server 8790 --directory prototype` (background task `bwyqw9q8m`) — serves the mock
  at `http://localhost:8790/mocks/ocr_flow_mock.html`.
- CORS fixture server on port 8791 (background task `bilgloozp`,
  `C:\Users\Martin\AppData\Local\Temp\claude\...\scratchpad\fixture_server.py`) — serves
  `shell/tests/fixtures/panel_ocr/images/*.png` with `Access-Control-Allow-Origin: *`, needed for
  the picker-capture upload technique.

Both left running since this is an open loop (NOT SATISFIED) and the next round will need the
same side-by-side setup.

---

## ROUND 2 — 2026-08-15

### VERDICT: SATISFIED

**0 JOURNEY-BLOCKER · 0 MISMATCH · 0 FRICTION · 0 POLISH (open) · 6/6 Round-1 findings CLOSED**

All six Round-1 findings were independently re-verified as a user would experience them — real
clicks, real navigation, real (or deliberately controlled) network conditions — not just "the
code changed." A fresh sweep of the full journey coverage list (happy path at both widths, both
E1 wrong/partial/error sub-variants, the D-043/D-044 missing-popup honesty chain, D-041
recovery-dropzone survival, the free-tier gate) found nothing newly broken and no new findings.
This is the exact optimized experience the charter asked for; the loop ends here.

---

### Per-finding verification

#### UXJ-001 — CLOSED — CTA is now the first child of the stable `.input` section

Live-verified at both widths on a fresh navigation (no-cache client code, confirmed by
`fetch`-free DOM inspection of the freshly-loaded page):
- **Desktop (1280×800):** `#ocrfEntry.previousElementSibling === null` — it is now the literal
  first child of `section.input`, before the MY SIDE/ENEMY role toggle. Button top edge
  `y=110px`, fully inside the initial viewport.
- **Mobile (375×812):** button top edge `y=165px`, fully inside the initial viewport — no scroll
  needed at all (Round 1 measured 1389px, 1.7 screens down).
- **Stability check (new this round, not just a re-measurement):** clicked through Troops
  Formation → Stats → Buffs → back to Troops Formation; the CTA's `y` position stayed at exactly
  `110px` throughout. The fix is structurally anchored to the stable section, not to whichever tab
  happens to be active — a more robust fix than "just move it," since it can't regress by tab
  state alone.
- No horizontal overflow at either width.

#### UXJ-002 — CLOSED — mini-panels ported to S1 and S2, dropzone icon added

Full `outerHTML` of the real app's S1 and S2 screens compared directly against the mock's
equivalent markup (both pulled live, side by side):
- S1: all three cards (`ocrf-mini-panel--battle`, `--scout`, `--city`) now render the same rows
  with the **same values** as the mock (`+4859.0%`/`+694.3%` Infantry Attack, `748.49%` Troops'
  Attack, etc.) — a byte-level content match, differing only by the expected `ocrf-` class prefix.
- S2: both YOU and ENEMY side-sections carry the same battle mini-panel preview, and the dropzone
  now includes the SVG camera icon (`ocrf-dz-icon`, same `viewBox`/path geometry as the mock's
  `.dz-icon`) — confirmed present in the live DOM, not just in source.
- No horizontal overflow at 375px with the mini-panels present.

#### UXJ-003 — CLOSED — candy-stripe + step-pulse implemented, verified actively running during a real stuck read

Set up a **controlled stuck read** (patched `window.fetch` to return a promise that never
resolves for `/shell/ocr/panel` only — every other request untouched) so the S3 screen could be
inspected mid-flight without waiting on a real Gemini timeout:
- `ocrf-scan-fill::after`'s `getComputedStyle(...).animationName` = `ocrf-scan-stripes`;
  `fill.getAnimations({subtree:true})` returned 2 animations, both `playState: "running"` — the
  Web Animations API confirms both are genuinely active, not merely declared-but-idle.
- The fill's inline `style.width` was `88%` (not 100%) while parked on the last step
  ("Checking both sides…", marked active/not-done) — matches the claimed cap, correctly never
  claims false completion.
- **Caveat, noted honestly:** this evaluation harness's Browser pane does not appear to composite
  frames in this environment (the same limitation that makes `computer{action:"screenshot"}`
  time out, documented in both rounds) — sampling `::after`'s `background-position` twice, 9
  seconds apart, returned an unchanged `"0% 0%"` both times, and `Animation.currentTime` stayed at
  `0`. This reads as the render/compositor pipeline never being asked to paint a frame in this
  harness, not as the animation being non-functional — `playState`/`animationName` (the DOM-level,
  paint-independent source of truth) are unambiguous, and the CSS itself
  (`animation: ocrf-scan-stripes .7s linear infinite`, a plain unconditional infinite loop) has no
  logic that could make it stall in a real, rendering browser. Flagged here for transparency, not
  as an open finding.
- Reduced-motion: `@media (prefers-reduced-motion:reduce){ #ocrfRoot .ocrf-scan-fill::after{
  animation:none!important} }` was added specifically for the pseudo-element — necessary because
  the pre-existing broad `#ocrfRoot *{animation:none!important}` rule matches real elements but
  not `::after` pseudo-elements, so this was a genuine gap-fill, not a redundant addition.

#### UXJ-004 — CLOSED — all five HTTP error classes now render honest, class-specific copy

Explicitly per the coordinator's instruction, verified via `fetch` stubs on `/shell/ocr/panel`
only — **zero real quota spent on this finding**:

| Stubbed response | Result screen | Heading | Actions offered |
|---|---|---|---|
| `429 {error:"quota_exceeded"}` | e1/error | "That's today's limit" | **only** "Type the numbers in myself" (no pointless retry) |
| `429 {error:"burst"}` | e1/error | "Slow down a little" | "Try again" + "Type them in myself" |
| `402 {error:"payment_required"}` | e1/error | "This needs a paid plan" | "See plans" + "Type it in myself" |
| `503 {error:"engine_unavailable"}` | e1/error | "The reader is busy right now" | "Try again" + "Type them in myself" |
| `401 {error:"unauthorized"}` | e1/error | "Please sign in" | "Try again" + "Type them in myself" (see note) |

All five match `error_copy.mjs`'s `mapError()` exactly, each with the correct icon (⚠️, distinct
from the wrong-screenshot 🔍) and — critically — the quota case correctly **omits** "Add a
clearer screenshot" (retrying can't fix a quota limit; showing it would have repeated the original
dishonesty in a new form). The "See plans" button was clicked and confirmed to be genuinely wired
(not dead): it called the real checkout endpoint, got back a session id, and navigated to
`/shell/billing/mock-checkout?session_id=...`, which 404s in this dev environment — that 404 is a
**separate, out-of-scope billing/checkout stub gap**, not an OCR-flow regression, and is noted
here only for completeness, not as a UXJ finding.

Note on 401: its action is "Try again" rather than a sign-in-specific CTA. Read the code
(`pick_upload.mjs`'s `e1ActionHtml`) and found this is a **deliberate, commented** grouping —
"the screenshots themselves were never the problem — retry the exact same upload, or fall back to
typing" — bucketing 401/503/429-burst as retry-worthy versus 402/429-quota as needing a different
action. Reasonable, not a regression of the honesty problem UXJ-004 was about (it no longer claims
the *screenshot* is the problem); not filed as a finding.

**Regression check (this is what the fix could most plausibly have broken):** confirmed the
pre-existing, unrelated "genuinely bad image" paths still work, both live and stubbed:
- Real `C_battle_1.png` (a real wrong-variant screenshot, real RapidOCR+Gemini round trip) still
  produces the 🔍 "That doesn't look like the right screenshot" copy, not the new ⚠️ error variant.
- A stubbed `200 OK` with all 24 fields unreadable → same 🔍 "wrong" copy.
- A stubbed `200 OK` with 3 of 24 fields readable → 🔍 "We read 3 of 24 numbers... Type the missing
  numbers" (the "partial" sub-variant, correctly distinguished from both "wrong" and "error").
- D-041 (post-recovery dropzone survival): "Add a clearer screenshot" from the wrong-variant path
  still lands on S2 with the "We took that one out. Add a new screenshot." notice and a live,
  clickable dropzone.

#### UXJ-005 — CLOSED — S4→S5 now focuses a real heading

Real S4→S5 transition (Next click after a genuine full OCR read, not a shortcut), checked
immediately after the click: `document.activeElement` = `<h1 id="ocrfS5Heading" tabindex="-1">`
containing "Battle setup" — confirmed at both desktop and mobile widths.

#### UXJ-006 — CLOSED — S5's primary CTA reads "See who wins →"

`#runBtn.textContent.trim()` = `"See who wins →"` at real S5 arrival, both widths. Clicked it once
(desktop): fired a genuine `POST /api/predict` → 200, confirming the label change didn't disturb
the underlying handler.

---

### Fresh sweep — regression/new-issue check beyond the six findings

- **Digit-exact fill:** re-confirmed twice more this round (desktop + mobile, both against the
  same `C_battle_3.png`+`C_battle_4.png` pair) — `#statPanel` still matches the server response to
  the digit. No regression from the mini-panel/CTA/focus/label changes.
- **D-043/D-044 missing-popup chain:** re-run live (`C_battle_3.png` alone) — chip still reads
  "All 24 numbers read · your side and the enemy side not filled in — tap to check"
  (`ocrf-needs-attention`), both per-side notices still present with the exact D-045 wording
  ("tap the ! next to 'Stat Bonuses'"). No regression.
- **D-041 recovery-dropzone survival:** re-confirmed (see UXJ-004 above). No regression.
- **Free-tier gate:** re-confirmed at the entry point (`X-Dev-Plan: free` via a scoped `/shell/me`
  fetch patch) — upgrade sheet still shows correctly. No regression.
- **Undo:** clicked on the mobile happy-path run; restored the prior snapshot's values correctly
  (the prior snapshot happened to equal the just-filled values in this specific test sequence,
  since the same fixture pair was read twice back-to-back — not a bug, just means this spot-check
  wasn't independently discriminating; Undo's mechanism was already thoroughly proven in Round 1
  with a genuinely different before/after state and nothing in this round's commits touched
  `buildFillPlan`/Undo logic).
- **Console:** a fifth stale-shaped `429` appeared this round (Round 1 had exactly four, unchanging
  all round). Most plausibly self-inflicted: this round drove **two browser tabs concurrently**
  against the same `dev_user` identity, each independently hitting `/shell/me` and (once)
  `/api/predict` in quick succession — endpoints outside the OCR-specific burst carve-out
  (`OCR_ENDPOINTS`) — which is a harsher request pattern than any single real user would produce.
  No corresponding UI symptom was observed anywhere alongside it (every screen checked immediately
  around this rendered correctly). Not filed as a finding; noted for the record.
- **Type dropdowns, Battle-covers-both-sides messaging, S1 copy for all 3 types:** spot-checked in
  passing during the mini-panel and happy-path work above; unchanged from Round 1, no regressions.

No UXJ-007+ findings this round.

---

### Coverage log

| Area | How verified this round |
|---|---|
| UXJ-001 (CTA position) | Live DOM inspection, desktop + mobile, plus a tab-switch stability check not done in Round 1. No OCR read needed. |
| UXJ-002 (mini-panels) | Live `outerHTML` diff against the mock, S1 (all 3 cards) + S2 (both sides + dropzone icon), both widths. No OCR read needed. |
| UXJ-003 (animation) | Controlled stuck-read stub (`fetch` never resolves) + `getAnimations()`/computed-style inspection. Zero quota spent. |
| UXJ-004 (error copy) | Five stubbed HTTP responses (402/429-quota/429-burst/503/401) on `/shell/ocr/panel` only. Zero quota spent. Regression side confirmed with 1 real wrong-variant read + 2 stubbed (zero-field, partial-field) responses. |
| UXJ-005 (focus) | Real S4→S5 transition, both widths, `document.activeElement` checked immediately post-click. |
| UXJ-006 (CTA label) | Real S5 arrival, both widths; clicked once to confirm functional continuity. |
| Happy path, full journey, both widths | 2 real reads (desktop `C_battle_3`+`C_battle_4`, mobile same pair): digit-exact fill, tally, chip, focus, label, no overflow, clean console (aside from the noted pre-existing/self-inflicted 429s). |
| E1 wrong / partial / error sub-variants | 1 real read (wrong) + 2 stubbed (zero-field "wrong", 3-of-24 "partial") + 5 stubbed (error classes). All three visually/textually distinct, none cross-contaminated by the others' fix. |
| Missing-popup (D-043/D-044) | 1 real read (`C_battle_3.png` alone). Unaffected by this round's changes. |
| D-041 (recovery dropzone) | Exercised twice (once via real wrong-variant, once via stub). Both alive. |
| Free-tier gate | 1 scoped `/shell/me` header patch, no real OCR spent. |
| Undo, Reset, editor, provenance | Not re-driven end-to-end this round (untouched by any Round-2 commit; thoroughly proven in Round 1); Undo spot-checked in passing (see Fresh sweep). |
| Quota-exhaustion / burst copy | Covered by UXJ-004's stubbed 429-quota/429-burst cases above — stronger evidence than Round 1's pure-code-read, at zero real-quota cost. |

### Quota consumed

`dev_user`: **4 real OCR reads** this round (25 → 21 remaining) — 1 wrong-variant, 1 happy-path
desktop, 1 happy-path mobile, 1 missing-popup. All five HTTP-error-class checks and both
zero-field/partial-field regression checks used `fetch` stubs — **zero additional quota**.
`ux-eval`: still untouched, 30/30. Sim quota (`dev_user`) is now at 0 (incidental, from forecast
clicks across both rounds) — not part of this charter's tracked resource, noted for awareness only.

### Servers stopped

Verdict is SATISFIED — per the loop's instructions, both evaluator-owned servers were stopped:
mock static server on :8790 (background task `bwyqw9q8m`) and the CORS fixture server on :8791
(background task `bilgloozp`). The loop ends here; no further rounds expected unless new work
reopens the journey.

---

## ROUND 3 — 2026-08-15 (loop REOPENED — Presentation-container mandate)

### Owning the miss

Round 2's SATISFIED verdict was wrong in a way that mattered: the entire OCR flow was rendering
as a phone-width column at the very bottom of the page on desktop. Every check in Rounds 1–2 —
including UXJ-001's own CTA-position rect check — asserted DOM presence, text content, or a
single element's coordinates, but never asked the one question that actually defines "did the
user see this": is the thing they need to look at next inside the visual viewport, at the size a
modal takeover implies. `offsetParent`/DOM-presence checks are provably insufficient (a
`position:fixed` element has `offsetParent === null` by spec, and a phone-width column at
`y=6000px` still "exists" and still has correct `innerText`). This round re-audits the full
journey under the amended charter's binding rule: `getBoundingClientRect()` vs
`innerWidth`/`innerHeight` after every user action, at both widths, no exceptions.

### VERDICT: NOT SATISFIED

**0 JOURNEY-BLOCKER · 2 MISMATCH (new) · 1 FRICTION (new) · 0 POLISH open · all 6 Round-1/2
findings (UXJ-001..006) reconfirmed CLOSED under the new evidence standard**

The takeover itself (commit `6f6c2bc`) and a same-day follow-up polish round (commit `00b7f3d`,
which landed **while this round was in progress** — see note below) are a well-built, carefully
reasoned piece of work. Every geometry claim in both commit messages was independently
reproduced with rect-vs-viewport evidence at both widths: centered card, full-screen sheet,
scroll-lock, bounded dialog height with internal-only scroll, entrance/exit motion, backdrop-click
precision, non-destructive exit with CTA restoration. But the mandate's whole point is to hunt for
what "the code looks right" doesn't catch, and adversarial testing of the specific seams the
coordinator flagged (mid-read exit, re-entry, background inertness) found two real MISMATCHes and
one FRICTION that a fresh look at "is this modal actually behaving like a modal" was always going
to be the way to find.

**Mid-session note on evidence freshness:** partway through this round, `git status` showed
`shell/app/ocr/client/ocr_flow.js`/`ocr_flow.css` as uncommitted-modified — a polish round was
landing live, in parallel with this evaluation (it addressed, among other things, exactly the
"long-content screen scrolling within the overlay" item the coordinator asked to hammer, before I
got to it independently). That work is now commit `00b7f3d`. Every finding below was verified (or
re-verified) against the current `HEAD` (`00b7f3d`) as a final pass, specifically to avoid
reporting against a state that had already moved. This is noted for transparency, not as a
finding.

---

### Findings

#### UXJ-007 — MISMATCH — the outer S1-S4/E1 modal does not make the background page inert; keyboard focus can escape into it

**Charter citation:** amended mandate, "dialog semantics (role/aria-modal)" as part of the
takeover contract; PRD §5's general pattern "sheets set inert/aria-hidden and trap focus."

**What's wrong:** `#ocrfRoot` correctly carries `role="dialog"` / `aria-modal="true"` (confirmed),
which is necessary but not sufficient for real keyboard containment — `aria-modal` is a hint for
assistive-tech virtual cursors, not a mechanism that stops native Tab-key focus from reaching
covered content. Live-verified: with the modal open on any of S1/S2/S3/S4/E1 and **no inner sheet
open**, `document.querySelector('main.layout').inert` is `false`, and calling
`.focus()` directly on the page's own `#runBtn` (the "See who wins →" / "Run forecast" button,
visually underneath the backdrop) **succeeds** — `document.activeElement` becomes `#runBtn`.
Reproduced against the final committed `HEAD` (`00b7f3d`), not a stale state.

**Root cause, traced to source:** `shell/app/ocr/client/ocr_flow.js`'s `syncBackgroundInert()`
(the D-040 machinery, comment: *"whenever ANY sheet/menu is open, every OTHER direct child of
`<body>`... becomes inert"*) only fires from the editor/picture-sheet/type-menu open/close call
sites, and its own `openSheetEls()` query (`'.ocrf-modal-scrim, .ocrf-type-menu'`) does not include
`#ocrfRoot`. So the moment ONLY the outer takeover modal is open (the common case — no nested
sheet), nothing ever calls `syncBackgroundInert()` for that state, and `<main>`/`<header>` stay
exactly as tabbable as if no modal were open. **Contrast (confirmed working):** the moment an
inner sheet DOES open on top (e.g. S4's field editor), `syncBackgroundInert()` correctly inerts
BOTH `<main>` AND `#ocrfRoot` itself (verified: `mainInert:true`, `modalRootInert:true` while the
editor sheet is open) — proving the mechanism is sound, it is simply never invoked for the "just
the outer modal" state.

**Reachability:** DOM order confirms this is reachable via ordinary Tab cycling in both
directions, not just via my direct `.focus()` probe — `#ocrfRoot` is appended as the LAST child of
`<body>` (`document.body.appendChild(...)` in `boot()`'s `onProceed`), so forward-Tabbing past the
last focusable control inside the modal wraps to the top of the document (into the live page), and
Shift+Tab from the modal's first control (the close button) lands on whatever precedes `#ocrfRoot`
in the live page's own tab order. A screen-reader or keyboard-only user can tab straight through
the "modal" into fully-interactive, visually-hidden background controls.

**Expected vs observed:** expected the background page to be unreachable by keyboard/AT while any
takeover screen is open (the charter's "dialog semantics" + PRD's own "trap focus" pattern);
observed the background is only ever inerted when a SECOND, nested sheet is also open.

---

#### UXJ-008 — MISMATCH — exiting mid-read (Escape/✕/backdrop during S3) does not cancel the in-flight read; it silently races a torn-down DOM and repeatedly crashes

**Charter citation:** amended mandate's "non-destructive exit"; general product honesty/robustness
principle (§1.3 "never fabricate," extended here to "never silently misbehave").

**What's wrong, in three parts, all reproduced against `HEAD` (`00b7f3d`) via a controlled-delay
`fetch` stub on `/shell/ocr/panel` only (no real quota spent verifying this):**

1. **The network request is never aborted.** `postPanel()` (`ocr_flow.js`) builds its `fetch()`
   call with no `AbortController`/`signal` anywhere. Escaping S3 mid-read does not stop the
   request; it completes (or fails) on the server regardless of the user having left. In a real
   (non-stubbed) scenario this means **a real OCR-quota unit is silently spent on a read the user
   explicitly walked away from**, with no way for the user to know it happened — this is the
   direct answer to "what happens to the pending quota unit": it's gone.
2. **The step-narration interval is never cleared.** `reading.mjs`'s `driveScan()` only calls
   `clearInterval(timer)` inside the eventual `run().then(...)`/`.catch(...)` handlers — but
   `exitFlow()` (Escape/✕/backdrop's shared handler) never calls the `handle.cancel()` that would
   set the `cancelled` guard, unlike the pre-existing Cancel **button**, which does. Net effect:
   the interval keeps firing every 900ms — for the entire remaining duration of the abandoned
   read — and **every single tick throws an uncaught `TypeError: Cannot read properties of null
   (reading 'querySelectorAll')`** at `reading.mjs:27` (`onStepChange` inside the interval) and
   again at `reading.mjs:34` (the same call in the final resolve handler), because `onStepChange`
   is wired to `applyStepClasses(root(), i)` and `root()` (`#ocrfRoot`) no longer exists — it was
   torn down by the very `exitFlow()` that failed to cancel the timer. Reproduced live: a 20-25s
   delayed stub produced 7+ repeated identical uncaught exceptions in the console before the
   promise settled.
3. **The only reason the user isn't unexpectedly yanked back into a reopened modal is the crash
   itself, one line early.** `driveScan`'s success handler is `clearInterval(timer); if
   (cancelled) return; onStepChange(...); onDone(result);` — since `cancelled` is never set on
   this exit path, execution reaches `onStepChange`, which throws — and because it throws, the
   NEXT line, `onDone(result)` (i.e. `onReadDone` → `goto('s4'/'e1', ...)`), **never runs**. The
   visibly-benign outcome (user stays cleanly at 'entry', no surprise re-open) is an accident of
   which line crashes first, not a guarded, designed behavior. This is fragile: any future change
   to `onStepChange`/`applyStepClasses` (e.g. a defensive null-check, entirely plausible
   "hardening") would silently remove the accidental guard and expose the real bug underneath —
   `onReadDone` firing after the user left, attempting `show()` on a null `root()`, or worse,
   successfully reopening the modal and jumping to S4/E1 out of nowhere.

**Expected vs observed:** expected a mid-read exit to be genuinely non-destructive and clean (per
the takeover contract's own wording); observed an unaborted network call (real quota cost), a
runaway crashing interval, and a correct-looking end state that is a side effect of a crash, not
of design.

---

#### UXJ-009 — FRICTION — re-entering after a mid-flow exit shows stale S2 state with no signal that it's carried over

**What's wrong:** after uploading a screenshot on S2 and later exiting mid-read (Escape during
S3), re-opening the flow via "Fill from screenshots" → "Battle Report" lands back on S2 with the
**previous session's thumbnail already present** and **Continue already enabled** —
`app.shots`/`app.savedValues` are never cleared by `exitFlow()` (by design — "non-destructive"),
but nothing on screen distinguishes this from a screenshot the user just added in the current
visit. A user who mentally treated the earlier exit as "starting over" has no way to tell they're
looking at old data, and could click Continue straight through without realizing it's resubmitting
a stale upload.

**Expected vs observed:** expected either a fresh S2 (if exit is meant to reset) or an honest
"picking up where you left off"-style signal (if preservation is the intended, PRD-aligned
"never discard an upload" behavior, which is very plausibly correct here); observed silent
carry-over with zero copy or visual distinction either way.

---

### Investigated and NOT filed (debunked alarms — reported for transparency, per this round's own standard of rigor)

- **S5 rendering off-screen on arrival.** Mid-session, a stubbed S5 arrival measured
  `#ocrfS5Host` at `top:-1258px` (definitively out of viewport) with `window.scrollY:1378`. Traced
  the root cause: repeated `navigate {force:true}` reloads of the same URL across this long
  session caused the browser to restore a stale scroll position each time (confirmed independently
  — even a brand-new, never-scrolled tab loaded the same URL at `scrollY:2024` on first paint).
  Re-tested cleanly: with `scrollY` pinned to 0 before opening the flow (the realistic starting
  condition for a user who just loaded the page and clicked the near-top CTA), `scrollY` stayed
  at exactly 0 through the ENTIRE S1→S2→S3→S4→S5 flow (scroll-lock holds, nothing leaks), and
  `#ocrfS5Host` landed correctly in viewport (`top:120`, both widths) with focus on its heading.
  **Not reachable under realistic single-session use** — filing this against the product would
  have been exactly the kind of unearned alarm this round's rigor is supposed to prevent.
  One real, smaller-scale observation kept for the record rather than filed: S5's heading focus
  (`s5Heading.focus({ preventScroll: true })`, `ocr_flow.js`) is the one focus call in this whole
  feature that still suppresses scroll-into-view with no compensating guarantee — every other
  screen either lives inside the scroll-immune `position:fixed` modal (where the takeover-polish
  commit explicitly reasoned through why dropping `preventScroll` is safe) or is this one
  in-page exception, undocumented and untouched by either round. Worth a defensive
  `scrollIntoView`/dropped `preventScroll` the same way the modal got one, but not something I can
  currently demonstrate a real user hitting.

---

### Re-confirmation of UXJ-001..006 under the new evidence standard

All six re-verified this round with rect-vs-viewport evidence (not mere presence), at both widths,
against `HEAD` (`00b7f3d`):

| id | Re-check this round |
|---|---|
| UXJ-001 | CTA is the first child of `section.input`; `top:110` desktop / `top:165` mobile, both inside the initial viewport with zero scroll; position stays fixed across Troops-Formation/Stats/Buffs tab switches. |
| UXJ-002 | Mini-panels present on S1 (all 3 cards) + S2 (both sides) with byte-matching mock content; **and now legible** — the same-day polish round bumped mini-panel/pick-card type from the original 6.8-8px up to 9-18px at ≥768px, confirmed via computed `font-size`. |
| UXJ-003 | S3's `ocrf-scan-stripes`/`ocrf-step-pulse` confirmed `playState:"running"` via `getAnimations()` during a real controlled-delay stuck read. |
| UXJ-004 | All 5 HTTP error classes (402/429-quota/429-burst/503/401) re-verified via stub, now inside the dedicated `renderE1('error', mapped)` variant, card geometry confirmed in-viewport at both widths (760px band desktop, full-screen mobile) — a NEW check this round, not just content. |
| UXJ-005 | Real S4→S5 transition (desktop AND mobile, real two-shot reads): `document.activeElement` = `#ocrfS5Heading`, confirmed in viewport both times. |
| UXJ-006 | `#runBtn.textContent.trim() === "See who wins →"` at real S5 arrival, both widths; fired a genuine `/api/predict` once to confirm no functional regression. |

---

### What's new and confirmed working well this round (the takeover + polish, positively verified)

- **Full takeover contract**, both widths, rect-vs-viewport evidence: backdrop (`rgba(4,16,28,.66)`
  scrim, `z-index:2147482600`), `body.ocrf-flow-open{overflow:hidden}` scroll-lock, centered card
  (`leftGap≈rightGap`, desktop) / full-bleed sheet (mobile), `role="dialog" aria-modal="true"`,
  44×44px close button always in viewport, focus-to-heading on open.
- **Backdrop-click precision**, both widths: clicking anywhere inside `.screen` (including bare
  padding, corners, near the close button) never closes; clicking the true backdrop
  (`event.target.id === 'ocrfRoot'`) always does. Verified by direct coordinate + `elementFromPoint`
  checks, not just "it seemed to work."
  All three exits (Escape, ✕, backdrop) restore focus to `#ocrfCtaScreenshots`, confirmed actually
  inside the viewport (not just focused) under realistic scroll conditions.
- **Bounded dialog + internal-only scroll** (the same-day polish round, landed as `00b7f3d`):
  tested at a deliberately short 1280×600 viewport with a 24-field S4 grid — `.screen` correctly
  caps at `88vh`, only `.ocrf-scr-body` scrolls (`overflow-y:auto`), and the header/close-button/
  footer/Next-button rects are **byte-identical before and after** scrolling the body to full
  depth. This is exactly coordinator item (b) — confirmed fixed, not just claimed.
- **Entrance/exit motion**: `#ocrfRoot`/`,screen` animations (`ocrf-scrim-in`/`ocrf-dialog-in` on
  open, `ocrf-scrim-out`/`ocrf-dialog-out` on close) confirmed `playState:"running"` via
  `getAnimations()`; reduced-motion correctly silences both the pre-existing kill-switch's targets
  AND the two new animations living outside it (`#ocrfRoot`'s own scrim animation isn't a
  descendant of itself, so it needed and got its own explicit reduced-motion rule — same pattern
  UXJ-003 already established, correctly reused).
- **Editor sheet nested inside the modal** (coordinator item (a)): confirmed `z-index:2147483000`
  correctly layers above the modal's `2147482600`; confirmed the D-040 `syncBackgroundInert`
  machinery correctly inerts BOTH the live background page AND `#ocrfRoot` itself while the sheet
  is open (contrast with UXJ-007's gap for the outer modal alone); focus correctly enters
  `#ocrfEditorInput` and, on close, lands on the screen's own heading (a safe, if not
  pixel-perfect, fallback — not investigated further given higher-priority findings).
- **Type-tag menu inside the modal**: in-viewport at both widths, correct internal z-index (`70`,
  relative to the modal's own stacking context), closes on outside click.
- **Digit-exact happy path**, full re-verification with rect evidence at every single transition,
  both widths, two REAL two-shot reads (not stubs): desktop and mobile both landed
  `#statPanel` digit-exact, `scrollY` confirmed to stay at 0 throughout, S5 confirmed in viewport,
  "See who wins →" confirmed correct and functional.
- **Free-tier gate**: upgrade sheet confirmed centered and in-viewport (desktop).

---

### Coverage log

| Area | How verified |
|---|---|
| Viewport-rect evidence mandate | Applied to every screen transition tested this round: S0 CTA, S1 card, S2 (dropzones/mini-panels/hint/type-menu), S3 (card + stuck-read animation), S4 (card, bounded-height/internal-scroll, editor sheet), S5 (host, both widths), E1 (all variants' container geometry). |
| Takeover contract (backdrop/scroll-lock/card-vs-sheet/close/Escape/backdrop-click/dialog semantics) | Live, both widths, coordinate-precise backdrop-click test (inside-card vs true-backdrop). |
| (a) type-tag menu / editor sheet / picture sheet inside the modal — inert machinery | Type-tag menu: viewport+z-index, both widths. Editor sheet: viewport+z-index+inert-chain (background AND outer modal), confirmed via direct `.inert` checks. Picture sheet: not independently re-driven this round (Round 1/2 already confirmed its content/structure; no code in this round's diff touched it) — flagged as the one coordinator item given lighter treatment, given UXJ-007/008's severity took priority. |
| (b) long-content S4 grid scrolling within the overlay on a short viewport | Live at 1280×600 with a real 24-field grid: header/close/footer rects unchanged across a full internal scroll. Confirmed fixed by the same-day polish round. |
| (c) exiting mid-read (Escape during S3) — in-flight read + quota fate | Live, controlled-delay `fetch` stub (20-25s), zero real quota spent. Finding UXJ-008. |
| (d) re-entering after an exit — state preservation vs stale-notice confusion | Live. Finding UXJ-009. |
| (e) S5 host coexistence with the entry CTA | Live: `entryHidden:true` while S5 shows; `#ocrfS5Host` removed and CTA restored on returning to entry. The "off-screen on arrival" alarm investigated and debunked — see dedicated section above. |
| (f) backdrop click precision (inside-card must never exit) | Live, coordinate-precise, both widths — see "confirmed working well." |
| UXJ-001..006 | Re-confirmed with rect evidence — see dedicated table above. |
| E1 wrong / partial / error sub-variants | Content re-confirmed (Round 2); geometry NEWLY confirmed this round via the 429-quota case at both widths (screen-level CSS applies uniformly regardless of which copy variant is shown, so this generalizes to all 7 sub-variants without re-testing each individually). |
| Free-tier gate | Re-confirmed with viewport-rect evidence, desktop (upgrade sheet centered, in-viewport). Not re-checked at mobile this round (already confirmed at both widths in Round 1/2; no code touched this path). |
| Manual "Type them in myself" floor | Exercised as part of the E1 error-variant checks (same action button, same destination); not independently re-driven end-to-end to S5 this round given time/quota budget and zero code changes in that path. |
| Console/network cleanliness | Checked throughout; the ONLY new errors this round are the UXJ-008 crash (expected, reproduced deliberately) and the same class of stale pre-existing 429/402 noise noted in Rounds 1-2 (not attributable to anything in this round's changes). |

### Quota consumed

`dev_user`: OCR reads went from ~20 (session start) to **16 remaining** this round — 2 real
two-shot reads (desktop + mobile digit-exact re-verification, the only checks where real server
behavior specifically mattered) plus incidental consumption reconciled to roughly 4 total; every
other check in this round (takeover mechanics, all error classes, mid-read-exit, re-entry,
bounded-height, animations, inert-background) used `fetch` stubs at zero additional quota, per the
coordinator's explicit steer. `ux-eval` identity: untouched, still 30/30, available for a future
round. Sim quota (`dev_user`) is at 0 (incidental, cumulative across all three rounds — not
tracked by this charter).

### Servers

Left running (verdict is NOT SATISFIED, next round will need them): mock static server on :8790,
CORS fixture server on :8791 (`C:\Users\Martin\AppData\Local\Temp\claude\...\scratchpad\fixture_server.py`).
