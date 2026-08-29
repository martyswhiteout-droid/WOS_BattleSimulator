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

---

## ROUND 4 — 2026-08-15 (verifying the Round 3 fix commit)

### Continuity note

This is a fresh evaluator session (the prior one was cut off mid-round by a transient API auth
error; per the loop's own rule, continuity comes from the written record, not a carried-over
transcript). By the time this session started, Round 3's three findings (UXJ-007/008/009) had
already been fixed and committed as `ed25604` ("ocr: fix UXJ-007/008/009 — modal inert boundary,
mid-read exit teardown, re-entry notice"), landing live, in-progress, partway through this very
session (the same "a fix round is landing while I evaluate" situation Round 3 itself documented).
Everything below was verified against the final committed `HEAD` (`ed25604`), independently
reproduced in the real browser — none of it is taken on the commit message's word, including the
one place where its self-reported "live-verified" claim did not survive independent re-test on the
first attempt (see UXJ-009 below).

### VERDICT: NOT SATISFIED

**0 JOURNEY-BLOCKER · 1 MISMATCH (new) · 0 FRICTION · 0 POLISH open · UXJ-007/008/009 all
independently reconfirmed CLOSED**

The `ed25604` fix is real and mostly solid: the background-inert boundary (UXJ-007), the mid-read
abort-and-teardown (UXJ-008), and the re-entry notice (UXJ-009) all work correctly under live,
adversarial, properly-paced testing — including one live false alarm on UXJ-009 that traced back to
my own test harness racing the CTA's async access-check, not a product bug (details below, kept in
for transparency the same way Round 3 kept its own debunked alarms). But the UXJ-007 fix introduced
exactly the kind of integration seam the charter exists to catch: reordering `render()` to run
`syncBackgroundInert()` *after* `renderScreen()` means the two focus-restoration calls inside
`renderScreen()` (closing back to `entry`, and arriving at `S5`) now fire while the just-closed
modal's stale `inert` attribute is still sitting on `<main>` — silently killing both calls and
re-opening the previously-closed UXJ-005 (S4→S5 focus-to-heading) as a side effect of an unrelated
fix. One new finding, UXJ-010, filed below.

---

### Per-finding verification (UXJ-007/008/009, fix commit `ed25604`)

#### UXJ-007 — CLOSED — background is now genuinely inert while only the outer modal is open

Live-verified at 1280×720 with the modal open on S1 and **no nested sheet**: every direct child of
`<body>` — `<header class="bar">`, `<main class="layout">`, `#liveStatus`, the `wos-shell-*` chips,
every `.hpick-pop` hero-picker popup, all scripts/links — carries a real `inert` attribute; only
`#ocrfRoot` does not. The exact original repro (`document.getElementById('runBtn').focus()`) now
**fails**: `document.activeElement` stays on the modal's own `H1`, not `#runBtn`. Re-confirmed at
375×812 (`main.layout.inert === true` while S1 is open). Nested-sheet cases both re-verified and
distinguished correctly by DOM structure, not just by intent:
- Editor sheet / picture sheet (appended as siblings of `#ocrfRoot` directly on `<body>`): opening
  either sets **both** `<main>` AND `#ocrfRoot` itself `inert` — confirmed live
  (`modalRootInert:true, mainInert:true`, focus correctly inside the sheet). Escape closes only the
  topmost sheet (priority chain), modal stays open underneath — confirmed.
- Type-tag menu (inserted as a DOM **descendant** of `#ocrfRoot` via `insertAdjacentElement`, not a
  body-level sibling): opening it correctly leaves `#ocrfRoot` interactive
  (`modalRootInert:false`) while still inerting the true background (`mainInert:true`) — the
  `child.contains(el)` branch in `syncBackgroundInert()` is exactly why, and this live result is
  the first time this specific distinction was checked rather than asserted.

#### UXJ-008 — CLOSED — mid-read exit now aborts the request and tears down cleanly

Reproduced the original repro exactly: stubbed `window.fetch` to hang on `/shell/ocr/panel` (never
resolving) with an `AbortSignal` listener recording whether abort fired; drove a real upload through
to S3; pressed Escape mid-read. Result: `window.__abortSeen` flips `true` (the request genuinely
aborts, confirmed via the signal's own `abort` event, not inferred) and the console gained **zero**
new errors versus an 8-error pre-existing baseline (the same class of stale 429 noise every round
has documented in this long-lived tab) — a clean before/after diff, where the original bug produced
"7+ repeated identical uncaught exceptions." `#ocrfRoot` is confirmed gone and `body.ocrf-flow-open`
confirmed cleared within the 140ms close-animation window, with no stray re-navigation afterward.

#### UXJ-009 — CLOSED — re-entry notice appears correctly, but only after I ruled out a false alarm

First attempt (chained rapid `dispatchEvent` calls with fixed short timeouts) showed the notice
missing — traced this **before filing it** and found the cause was my own test pacing, not the
product: `wireEntry`'s CTA click handler does a genuine `await checkAccess()` (a real `/shell/me`
round trip) before `onProceed()` ever runs, so a script-dispatched Escape fired milliseconds later
can land while the flow is still on `entry` (Escape is a no-op there) — leaving a stale intermediate
state that made a *later* cycle's result look broken when it wasn't. Rebuilt the test with an actual
polling helper (wait for the real DOM state to change, never a fixed timeout) and reproduced the
**exact three-cycle sequence** that had failed: upload → Continue → Escape mid-read → open again,
immediately escape from S1 with no S2 visited → open a third time → pick a type → land on S2.
Properly paced, this passed cleanly and repeatably (3 independent runs, including the literal
three-cycle sequence): `#ocrfS2Notice` reads *"Picked up where you left off — your earlier
screenshots are still here. Tap the × on any of them if you want a fresh start."*, the prior
thumbnail is present, Continue is enabled. This is the one place this round where a commit message's
self-reported verification ("re-entry shows the notice with the carried thumbnail") did not survive
my first independent pass — it does hold up under a correctly-paced repro, but the discrepancy is
worth the coordinator knowing about rather than silently resolving.

---

### Findings

#### UXJ-010 — MISMATCH — the UXJ-007 fix reordered `render()` so screen-arrival focus calls now fire against a stale `inert` background, breaking focus-restoration on every modal exit and re-opening UXJ-005

**Charter citation:** PRD §5, "focus-to-heading on navigation" (the same carried-over pattern
UXJ-005 was originally about); amended mandate's dialog-semantics/takeover-contract line.

**What's wrong:** `ocr_flow.js`'s `render()` is now `leaveScanIfRunning(); renderScreen();
syncBackgroundInert();` — `syncBackgroundInert()` moved to the END so its own decision (sheet open /
modal-only open / nothing open) always sees the final DOM, which is the right call for UXJ-007
itself. But `renderScreen()` **also** performs two focus-restoration calls, and both target elements
that live *outside* `#ocrfRoot`, inside `<main class="layout">` — the exact element
`syncBackgroundInert()` marks `inert` whenever the modal is open:
- The `'entry'` branch: `entryNode.querySelector('#ocrfCtaScreenshots')?.focus(...)`.
- The `'s5'` branch: `s5Heading.focus({ preventScroll: true })` on `#ocrfS5Host`'s own heading
  (`#ocrfS5Host` is inserted as a sibling of `entryNode`, itself inside `section.input` inside
  `<main>`).

Both calls now fire **before** `syncBackgroundInert()` has cleared the *previous* cycle's `inert`
flag on `<main>` (set while the modal that's now closing was still open) — an element is
unfocusable while any ancestor carries `[inert]` (spec behavior, not a bug in `inert` itself), so
`.focus()` silently no-ops and `document.activeElement` falls back to `<body>`.

**Live evidence, both root-cause and reachability:**
1. Minimal isolated repro: a bare `<button>` inside a `<div inert>` — `.focus()` returns without
   moving `document.activeElement`, confirmed in this exact browser/engine.
2. Instrumented `HTMLElement.prototype.focus` on the real page, real Escape-from-S1 exit (no read
   involved, simplest possible case): the CTA's `.focus()` call fires with
   `mainInertAtCallTime: true`; `document.activeElement` is `BODY` afterward, permanently (nothing
   re-attempts the focus once it fails).
3. Real S4→S5 transition, **desktop, with the actual digit-exact happy-path read** (not a stub):
   clicking Next (`[data-goto="s5"]`) lands on S5 with chip/CTA text all correct, but
   `document.activeElement` is `BODY`, not `#ocrfS5Heading` — confirmed the heading itself is
   fine (`tabindex="-1"`, correct text, in-viewport at `top:120`) and a **manual** `.focus()` call
   on it succeeds once the render cycle has fully settled — isolating the bug to timing, not a
   broken target.
4. Same S4→S5 check repeated at 375×812 (stubbed, for speed): identical result
   (`activeElTag: "BODY"`) — not width-dependent.

**Reachability:** this is not a corner case — it is **every single exit** from the modal back to
`entry` (Escape, ✕, backdrop-click all funnel through the same `exitFlow()` → `render()` path) and
**every single S4→S5 arrival** (the only way S5 is ever reached). A keyboard or screen-reader user
gets no landmark signal on either transition; a sighted mouse user is unaffected (everything is
still visible and clickable), which is why this survived the fix's own live-verification pass
without being noticed.

**Scope check (what this does NOT affect):** the internal S1→S2→S3→S4 transitions all target
headings living *inside* `#ocrfRoot`, which is never itself the element `syncBackgroundInert()`
inerts while it's the active layer — confirmed by re-testing S1's own opening
heading-focus-on-modal-open, which still works correctly. This is specifically an
"exiting-to-somewhere-outside-`#ocrfRoot`" bug.

**Suggested fix direction (not prescriptive):** `syncBackgroundInert()`'s own decision already
depends only on `app.screen` (already updated before `render()` runs) and a live `openSheetEls()`
DOM query — neither depends on anything `renderScreen()` builds. Running it *before*
`renderScreen()` (restoring the original two-step order, just with the corrected three-state
decision logic UXJ-007 added) would very plausibly fix this without reintroducing UXJ-007, but that
tradeoff is the builder's to verify, not this report's to mandate.

**Severity:** MISMATCH, not JOURNEY-BLOCKER — no dead end, no lost work, the flow completes
end-to-end for a mouse user (verified: the real happy-path read finished correctly with this bug
present). Kept at the same class UXJ-005 originally carried, since this is materially a regression
of that exact finding.

---

### Investigated and NOT filed (debunked alarms, for transparency)

- **UXJ-009 "notice missing" on the first attempt.** Covered above under UXJ-009's own
  verification — traced to a self-inflicted test-harness race (script-dispatched Escape outrunning
  the CTA handler's `await checkAccess()`), not reproducible under realistic, properly-paced
  interaction (3 independent clean reproductions, including the exact failing sequence redone with
  polling instead of fixed timeouts). Not filed.
- **Mobile S1 card bottom edge measuring 815.8px inside an 812px viewport.** First measurement
  (immediately after the screen's heading text appeared) showed the card's `getBoundingClientRect()`
  bottom at 815.8px — 3.8px past the viewport. Checked `card.getAnimations()`:
  `playState:"running"`, `animationName:"ocrf-dialog-in"`, transform mid-flight at
  `matrix(0.97, 0, 0, 0.97, 0, 16)`, and — critically — `Animation.currentTime` stayed at `0` even
  400-900ms later, the identical symptom Round 3's own UXJ-003 investigation attributed to this
  Browser pane not compositing/advancing animation clocks at all. Forcing the animation to its end
  state (`anim.finish()`) settles the card to a **perfect** `{top:0, left:0, right:375, bottom:812}`
  with `transform: matrix(1,0,0,1,0,0)` (identity) — exactly filling the viewport. This is the same
  documented harness limitation, not a product overflow; not filed, consistent with how Round 3
  handled its own instance of this exact caveat.

---

### Confirmed working well this round (fresh evidence, not re-asserted from prior rounds)

- **Digit-exact happy path, real read (not stubbed), desktop:** uploaded real
  `C_battle_3.png` + `C_battle_4.png` via the CORS-fixture-server + captured-picker technique, one
  genuine `/shell/ocr/panel` round trip. All 24 fields — both the S4 review-grid display **and**
  the actual `#statPanel` form inputs — match `docs/OCR_TEST_INSTRUCTIONS.md` §3's table to the
  digit (Infantry 2269.7/2151.7/1126.5/1129.0, Lancer 2189.6/2064.1/1103.7/1058.4, Marksman
  2385.8/2240.6/1263.9/1257.3, all marked ✓). S4 card height measured exactly `633.59375px` inside
  a 720px-tall viewport — precisely `0.88 × 720`, confirming the `88vh` bound to the sub-pixel. S5
  chip read *"All 24 numbers in ✓ — tap to check"*; CTA read *"See who wins →"* (UXJ-006 intact).
- **Bounded dialog + internal-only scroll, both widths this round** (not just desktop as in prior
  rounds): at 375×812, S4's close button measured pixel-identical (`top:10, left:321`) before and
  after scrolling `.ocrf-scr-body` to its full depth.
- **Editor sheet and picture sheet**, re-driven fresh this round (not just cited from Round 1/2):
  both correctly enter focus on open, both correctly inert the full chain (`<main>` AND `#ocrfRoot`)
  while open, both correctly release on close.
- **S1 card visual substance** (the "stunning bar" checklist item, grounded in computed styles, not
  impression): title `18px`, mini-panel content `13.33px`, card footprint 207–211px × 249–317px,
  16px padding — legible, proportionate, not cramped; matches the mock's registered improvement
  from Round 2/3 (mini-panel type raised from an original 6.8–8px).
- **UXJ-001 (CTA position)** still holds at both widths this round (`top:110` desktop /
  `top:165` mobile) — unaffected by any of this round's changes, spot-checked for regression only.
- **Node suite:** 190 tests, 189 pass, 1 documented skip — matches the fix commit's own claim
  exactly.

---

### Coverage log

| Area | How verified this round |
|---|---|
| UXJ-007 (background inert) | Live, both widths: full `document.body.children` inert audit (not just `<main>`), the original `.focus()`-escape repro re-run and now blocked, both nested-sheet sub-cases (body-sibling scrims vs. `#ocrfRoot`-descendant type-menu) distinguished live. |
| UXJ-008 (mid-read abort) | Live, controlled-hang `fetch` stub with a real `AbortSignal` listener (not inferred from behavior alone) — abort event genuinely fires; console-error diff (8 baseline → 8 after, zero new) replaces the prior round's qualitative "crashed" observation with an exact count. |
| UXJ-009 (re-entry notice) | Live, 3 independent properly-paced repros (2× two-cycle, 1× three-cycle matching the exact sequence that first appeared to fail) using explicit DOM-state polling instead of fixed timeouts; one false alarm investigated to root cause and ruled out before being considered for filing. |
| UXJ-010 (new) | Live: minimal isolated `inert`-blocks-`.focus()` repro, instrumented real Escape-from-S1 exit, real S4→S5 transition on the actual digit-exact happy-path read (desktop), stubbed S4→S5 repeat at mobile width. |
| Digit-exact happy path | 1 real 2-shot read (`C_battle_3`+`C_battle_4`), desktop — both review-grid and raw `#statPanel` inputs checked against the documented table. Not repeated at mobile this round (stub used instead for the mobile S4/S5 geometry checks, to conserve quota — digit accuracy is server-side and width-independent, already proven here and in every prior round). |
| Bounded dialog + internal scroll | Re-driven fresh at **both** widths this round (Round 3 had only re-driven desktop). |
| Editor sheet / picture sheet | Re-driven fresh this round with the new 3-state `syncBackgroundInert()` in place — confirmed both still nest correctly. |
| Type-tag menu | Re-driven fresh this round (not merely cited) — confirmed correct viewport position, z-index, and the `#ocrfRoot`-stays-active-because-descendant nesting case specifically, at mobile width. |
| S1 card visual substance | Live computed-style pull (font-size, card dimensions, padding) grounding the "stunning bar" judgment in numbers rather than impression. |
| Backdrop-click precision | **Not re-driven this round** — `boot()`'s backdrop-click listener is untouched by `ed25604`'s diff (confirmed via `git show`), and Round 3 already proved this mechanism with coordinate-precise, both-width evidence; re-asserting it without a code change to justify the re-spend of turns was judged lower-value than the checks above. |
| Manual "Type them in myself" floor, free-tier gate | **Not re-driven this round** — untouched by `ed25604`, already thoroughly proven across Rounds 1–3. |
| Console/network cleanliness | Checked throughout via exact before/after error counts (not just "looked clean") at each of the UXJ-007/008/010 live checks. |

### Quota consumed

`dev_user`: **1 real OCR read** this round (16 → 15 remaining, confirmed via `GET /shell/me`'s
`remaining.ocr` directly, not estimated) — the desktop digit-exact happy-path re-verification.
Every other check (UXJ-007/008/009/010, the mobile-width pass, the sheet/menu regression sweep, the
S1 card-substance pull) used `fetch` stubs or pure DOM/CSS inspection at zero additional quota.
`ux-eval` identity: untouched. Sim quota (`dev_user`): unchanged at 0 (not touched this round — no
forecast button was clicked).

### Servers

Left running (verdict is NOT SATISFIED, next round will need them, consistent with how Rounds 1 and
3 handled the same situation): mock static server on :8790, CORS fixture server on :8791. Neither
was started by this session (both were already up when it began, left over from the prior
interrupted session) — this session only used them.

---

## ROUND 5 — 2026-08-15 (the verdict round)

### VERDICT: SATISFIED

**0 JOURNEY-BLOCKER · 0 MISMATCH · 0 FRICTION · 0 POLISH open · UXJ-010 CLOSED · no new findings**

Commit `62c29ff` fixes UXJ-010 correctly (`syncBackgroundInert()` now runs both before *and* after
`renderScreen()`, so the two outside-the-layer focus calls see fresh inert state) and, in verifying
it, closes a real arrival-visibility gap the charter's own mandate had been silently unable to catch
until someone looked at the *filled* panel specifically: the fill was landing in a hidden tab. Both
are independently reconfirmed below with the evaluator's own original repros plus a full real-data
happy-path run. This round found nothing to file — an exhaustive, deliberately adversarial pass
(a shorter-viewport stress test, an Undo-scroll-conflict investigation, a re-test of every
sheet/menu under the new double-sync render path, a Formation-tab data-loss probe, a no-back-from-S5
settle check, and a fresh-reload re-entry check) turned up nothing that reaches even FRICTION. The
loop closes here.

---

### Re-verification of UXJ-010 (my own original repros, both widths)

- **Modal-exit repro** (Escape from S1, no read involved — the simplest case, run first in Round 4):
  desktop — `activeElId: "ocrfCtaScreenshots"`, `main.layout.inert === false`. Mobile (375×812) —
  identical result. Both a clean pass: focus lands on the CTA, not `<body>`, and the background is
  genuinely interactive again.
- **S4→S5 repro**: desktop, stubbed — `activeElId: "ocrfS5Heading"`. Desktop, **real two-shot read**
  (`C_battle_3`+`C_battle_4`) — same result, plus `headingRect.top: 12.09`, `scrollY: 319`, matching
  the fix commit's own claimed measurement (`heading top 12`, `scrollY 319`) to two decimal places.
  Mobile, stubbed — `activeElId: "ocrfS5Heading"` again, `scrollY: 353`. UXJ-005 (the finding UXJ-010
  had silently reopened) is closed a second time, now under evidence from three independent runs
  across two data sources and two widths.

---

### The arrival experience, judged as a first-time human (both widths, real + stubbed)

**Mechanics, verified live:** clicking Next on S4 activates the real Stats tab (`aria-selected`
flips `true` via the tab's own button, not a synthetic override) *before* the fill runs, so
`applyFillPlan` writes into a panel that is actually laid out (non-zero rects) instead of the
hidden Formation tab. The host mounts as `statPanel.parentElement.insertBefore(host, statPanel)` —
live-confirmed directly above the panel, not at the old ~1150px-distant entry-CTA spot. A single
synchronous `window.scrollTo({behavior:'auto'})` is the *only* scroll intent on this path
(`applyFillPlan` is called with `{scroll:false}` here, confirmed in the diff and in the fact that
`scrollY` never changed after the initial jump in any of my measurements).

**Result, no scrolling from the user, both widths:**

| | Desktop 1280×720 (real read) | Mobile 375×812 (stubbed) |
|---|---|---|
| Heading | top 12.1, "Battle setup", focused | top 11.5, focused |
| Chip | top 45.6, "All 24 numbers in ✓ — tap to check" | top 45, same text pattern |
| S5's own CTA | top 165.6, h 48, "See who wins →" | top 177, h 48, "See who wins →" |
| Filled panel | Stats tab active, all 24 real values in view (last input bottom 716.6 of 720) | Stats tab active, all 24 stub values in view (last input bottom 766 of 812) |
| scrollY | 319 (single instant jump, matches commit's own claim exactly) | 353 |

Heading, chip, CTA, and the entire 24-field filled panel are simultaneously in view with **zero**
user scrolling at both widths — the charter's "chip + filled form + See-who-wins together in view"
line, which Round 3/4 had never actually been able to test (nothing was visible to test) is now
demonstrably true. The S5 CTA was confirmed to be a genuine proxy, not a decoration: intercepting
`#runBtn.click` and firing `#ocrfS5Run` shows the real button's handler runs, and a fresh
`POST /api/predict` appears in the network log immediately after (429 only because this long
session's `sims` quota was already exhausted by earlier rounds' incidental forecast clicks — an
untracked resource per this charter, not a finding).

**The beat, judged honestly:** the modal is not closed via `closeFlowLayer()` here — `root()?.remove()`
fires synchronously in the same tick as the S5 cluster is built and scrolled into place, so there is
no exit animation, only an instant cut from "modal" to "settled inline result." I think this is the
*right* call, not a corner cut: an animated close on this specific transition would be animating a
lie — a conventional modal-close implies "returning to what was behind you," but what's behind here
is not what the user last saw (the CTA's spot is gone, a new chip+CTA cluster and a different active
tab have taken its place). Committing instantly to the new, true state reads as more honest than
staging a reveal of something that never existed. It also sidesteps the actual bug this round's
predecessor was fixing — competing async scrolls that don't reliably fire in a throttled tab — with
a mechanism (one synchronous call) that has no timing window to lose a race in. I could not visually
confirm the "cut" (this harness's Browser pane does not composite frames — the same documented
limitation as every prior round's animation checks — and `computer{screenshot}` timed out on this
attempt, consistent with the standing caveat), but the DOM-level evidence (zero animation classes
applied to the outgoing root, zero elapsed time between the click and the fully-settled measurement)
supports that it is genuinely instant rather than merely fast, and the reasoning for why instant is
correct here holds up under my own scrutiny, not just the commit message's.

**One observation, not filed:** at exactly 1280×720 the last filled input's bottom measured 716.6px
— about 3.4px of margin inside a 720px viewport. That's real, not a rounding artifact (verified by
counting all 24 inputs individually: `fullyVisibleCount: 24`, none cut off). Curious whether this
was a hair's-breadth coincidence, I stress-tested at a shorter, still-realistic 1280×680: the
heading/chip/CTA cluster stayed fully in view unchanged (nothing in the fixed-position cluster
depends on viewport height), and only the bottom rows of the 24-field panel required scrolling to
see in full. That is ordinary, graceful responsive degradation — the mandate's "together in view"
promise is about the arrival *beat* (chip + CTA + the fact that your data landed somewhere visible),
not a guarantee that every browser height shows all 24 rows without scrolling — and the charter's
own tested contract is 1280×720, where it holds with real (if slim) margin. Not filed; noted for
whoever next touches this layout, since a couple more fields or a slightly taller notice card would
tip it.

---

### Regression sweep

- **Undo:** clicked from a settled S5 arrival. Functionally correct — restored a *different* value
  set than what was just filled (the page's own persisted pre-fill values, not the stub's), proving
  it's a genuine restore, not a no-op. Its retained "old" scroll call (`applyFillPlan` default
  `scroll:true` → `statPanel.scrollIntoView({behavior:'smooth', block:'start'})`) produced **no
  observable scrollY change** in this harness before/immediately/600ms-after. I can't fully rule out
  smooth-scroll animation frames simply not advancing here (the same class of limitation documented
  for CSS animations in Round 3/4), but structurally there is no race to lose either way: unlike the
  original arrival bug (two competing async scrolls), Undo's path is a single scroll call with
  nothing else contending for the viewport, so even unobserved, it has no counterpart to race against.
- **Reset:** two-tap confirm still fires (`Reset` → `Really reset?`), spot-checked — untouched by
  this round's commit, already thoroughly proven in Rounds 1–3.
- **Chip expand/collapse:** `aria-expanded` toggles `false→true→false` correctly, body
  shows/hides in step.
- **Notices path** (stubbed `specials_observed:'none'`, reproducing the missing-popup case at S5
  arrival): chip correctly reads *"All 24 numbers read · your side and the enemy side not filled
  in — tap to check"* (`ocrf-needs-attention`, not `ocrf-complete`), heading/CTA geometry and focus
  identical to the clean-complete case, 2 notice cards present with the exact D-045 wording, both
  correctly 0-height while the accordion is collapsed and both fully in-viewport (top 110/183 of
  720) once expanded.
- **Formation-tab typed values:** set a Formation-tab range slider to a distinctive `77` before
  clicking Next. After the auto tab-switch to Stats and the fill, re-read the same slider:
  still `77`. The switch is a pure visibility toggle (the tab panels are hidden via CSS, not
  destroyed/rebuilt), so nothing a user typed on Formation is at risk — confirmed, not just reasoned.
- **No back from S5 (by design):** confirmed the settled state is genuinely clean, not merely
  unreachable — `#ocrfEntry` is `hidden` with a `0×0` rect, `#ocrfRoot` is gone,
  `body.ocrf-flow-open` is cleared. There is no way to re-trigger the OCR flow from S5 itself (the
  CTA is hidden, not removed) — consistent with the PRD's own recovery story for "I don't like this
  fill" being Undo/Reset, not a re-run, and with the coordinator's framing that this is deliberate.
- **Re-entry after an S5 arrival:** a genuine fresh reload (not a same-session re-trigger, since
  none exists) shows zero contamination — `#ocrfS5Host` does not exist, the entry CTA is restored to
  its normal `top:110` position, and the Stats tab is back to its default unselected state. The flow
  is exercisable again from a clean slate exactly as if S5 had never happened.
- **Sheet/menu mechanics under the new double-`syncBackgroundInert()` render path** (genuinely new
  code since Round 4's testing predates commit `62c29ff` — re-verified rather than assumed):
  type-tag menu (`modalRootInert:false`, `mainInert:true`, in-viewport) and editor sheet
  (`modalRootInert:true`, `mainInert:true`, focus in the input) both still nest exactly as Round 4
  found, and settle cleanly on close (`modalRootInert` correctly flips back to `false` while `main`
  correctly stays `true`, since the outer S4 modal is still open). No regression from calling the
  sync twice per render.

---

### Stunning-bar final sweep

- **S5 cluster vertical rhythm** (new this round, measured not eyeballed): heading (26px) → 8px gap
  → chip (52px) → 12px gap → Undo-links row (44px — exactly the design system's touch-target
  minimum, not an arbitrary number) → 12px gap → CTA row (48px) → 14px gap → filled panel. Consistent
  8–14px rhythm throughout, a deliberate hierarchy (context → status → utility actions → primary
  action → detail), not a stack of leftover margins.
- **S5's own CTA** reuses `.ocrf-btn-primary` (Round 1's real primary-button treatment, not a
  scaled-down or ghost variant) at `max-width:340px` — reads as a genuine primary action, not an
  afterthought bolted on to solve a geometry problem.
- **Digit-exact accuracy** holds under real data at the exact moment it now matters most (the visible
  arrival, not just an off-screen fill): all 24 fields, both display and raw inputs, byte-match
  `docs/OCR_TEST_INSTRUCTIONS.md` §3.
- **Everything carried over from Rounds 1–4** (takeover contract, entrance/exit motion, bounded
  dialog + internal scroll, backdrop-click precision, S1 card substance at 18px/13.3px type,
  dialog semantics, error-copy honesty, D-043/044/045 chain) — untouched by this round's commits,
  spot-checked in passing during this round's own drives through S1→S4 with no regressions observed.
- Nothing surfaced in this pass reads as cheap, cramped, or half-hearted. The one genuine tightness
  (the 720px-height margin, above) is a property of real content meeting a real viewport, not of
  unfinished or careless work — it's documented, not hidden, and degrades gracefully.

---

### Coverage log

| Area | How verified this round |
|---|---|
| UXJ-010 re-verification | Both widths, both my original repro shapes (plain Escape-from-S1; S4→S5), plus the S4→S5 case run a third time on a real two-shot read for a non-stubbed confirmation. |
| Arrival geometry (heading/chip/CTA/panel together, zero scroll) | Live, both widths, both real and stubbed data: full rect table above, all 24 fields individually checked for in-viewport status (not just the container). |
| Arrival beat/feel | Reasoned and cross-checked against DOM-level animation evidence (no animation classes on the outgoing root, zero elapsed time to settle); screenshot attempted once and timed out per the standing harness limitation, consistent with every prior round. |
| Stress test: shorter viewport (1280×680) | Live — cluster stays fully visible, only the panel's tail needs scroll; treated as expected degradation, not filed. |
| S5 CTA → real forecast proxy | Live: intercepted `#runBtn.click`, confirmed invoked; confirmed a fresh `POST /api/predict` fires immediately after. |
| Undo | Live: value-restoration confirmed functionally correct (restored a distinct, non-stub value set); scroll-conflict investigated and reasoned to be structurally impossible (single scroll call, no competing scroll to race). |
| Reset, chip expand | Live spot-checks, both pass, unchanged from prior rounds. |
| Notices-path S5 arrival | Live, stubbed `specials_observed:'none'`; chip/notices/geometry/focus all correct, collapsed (0-height) and expanded (in-viewport) states both checked. |
| Formation-tab data preservation | Live: a distinctive typed value set before the transition, confirmed unchanged after the auto tab-switch and fill. |
| No-back-from-S5 / re-entry | Live: settled-state cleanliness confirmed (entry hidden, root gone, body unlocked); genuine fresh-reload re-entry confirmed contamination-free. |
| Sheet/menu nesting under new double-sync render() | Live re-test (not assumed from Round 4, which predates this commit): type-tag menu and editor sheet both re-verified, both settle correctly on close. |
| Digit-exact real read | 1 real 2-shot read (`C_battle_3`+`C_battle_4`), desktop — both S4 review grid and the S5 arrival's real `#statPanel` inputs checked. |
| Stunning-bar sweep | S5 cluster rhythm measured; CTA treatment confirmed as genuine-primary, not decorative; carried-over mechanics from Rounds 1–4 spot-checked in passing, no regressions found. |

### Quota consumed

`dev_user`: **1 real OCR read** this round (15 → 14 remaining, confirmed via `GET /shell/me`) — the
desktop real-data arrival verification, within the 1-read budget. Everything else (UXJ-010
re-verification at both widths, the full regression sweep, the viewport stress test, the sheet/menu
re-check) used `fetch` stubs or pure DOM/CSS inspection at zero additional quota. `ux-eval`
identity: untouched. Sim quota (`dev_user`): unchanged (still exhausted from earlier rounds'
incidental forecast clicks; not tracked by this charter).

### Servers

**Verdict is SATISFIED — the loop closes here.** Both evaluator-owned servers stopped: mock static
server on :8790 and the CORS fixture server on :8791. The app on :8200 was left untouched, as
always. No further rounds expected unless new work reopens the journey.

---

## ROUND 6 — 2026-08-16 (loop REOPENED — two post-close UI changes, no evaluator has seen either)

**Context:** this evaluator was terminated mid-Round-4 by a transient auth error; a parallel
session completed Rounds 4–5 (UXJ-007/008/009 closed, UXJ-010 found and fixed in `62c29ff`,
SATISFIED at 20:11 on 2026-08-15). Rounds 4–5 were **not** redone here, per the coordinator's
explicit instruction — this evaluator's Round 1–3 context (and the partial Round 4 work already
in progress) is what made it the right agent to pick up what comes next. Two owner-requested
changes landed **after** the loop closed and needed a first look: `5c12924` (real game screenshots
as upload samples) and `dff9bf8` (S2 reworked into per-row Heroes/Battle-stats/Buffs zones). The
app process had restarted (fresh state, quota reset to 30/30) and both evaluator-owned servers
(:8790, :8791) had to be restarted before testing.

### VERDICT: SATISFIED

**0 JOURNEY-BLOCKER · 0 MISMATCH · 0 FRICTION · 0 POLISH open**

Both changes were judged end-to-end against real server behavior, not assumed from the commit
messages. The one genuinely open risk in this round's brief — whether the new optional Heroes
zone could poison an otherwise-good battle read into a false E1 failure — was independently
disproven with a real adversarial upload, not just re-read from the builder's own claim.

---

### Item (a) — real game screenshots as upload samples (`5c12924`)

Judged live at both widths, S1 cards and S2 rows:

- **Legibility / load:** all 5 sample JPEGs (`sample_battle_panel`, `sample_battle_popup`,
  `sample_battle_heroes`, `sample_scout`, `sample_citystats`) confirmed genuinely loaded
  (`naturalWidth` 560-640px, not broken images) on both S1 (numbered 1/2 pair for Battle Report,
  single image for Scout/City Stats) and S2 (one image per row, beside that row's own zone).
  Captions/badges present and correct ("1 Stat Bonuses list" / "2 The popup behind the ! icon").
- **No layout breakage, no horizontal scroll at 375px:** confirmed via `document.body.scrollWidth`
  vs `innerWidth` at every screen touched this round — zero overflow anywhere, at either width.
  At mobile, the S1 pair correctly stacks vertically (`flex-direction: column`, matching the
  commit's own "below 560px viewports" rule) rather than being forced side-by-side into
  illegibility.
- **Does it help matching:** yes — this is a clear win over the hand-drawn mini-panels it
  replaces. A real screenshot of the actual "Stat Bonuses" list and the actual "!" popup is a much
  more direct "does this match what's on my phone" reference than a stylized illustration, and the
  numbered 1/2 pairing on the Battle Report card visually teaches the two-shot requirement (main
  panel + popup) before the user ever reaches S2.
- **No console errors** from any image load/fallback path during this round's testing.

**Release-gate note (not a UX finding — the owner already made this call; flagging the mechanical
fact for the record, independently verified rather than just repeated from the samples README's
own hedge):** `shell/app/ocr/client/samples/*.jpg` are real Whiteout Survival client screenshots
(Century Games IP). `shell/promote.py`'s raster-stripping step (`step_asset_swap`, the loop at
line 398) iterates `for sub in ("wos_sim", "prototype")` only — confirmed by direct read of the
current source — so `shell/app/ocr/client/samples/` is **not yet in that strip list** and these
five files would ship as-is through a promotion run today. The samples' own `README.md` already
flags this exact risk ("If promote's strip list doesn't yet cover this folder, add it there rather
than shipping these") and the app has a working fallback for the stripped state
(`renderSampleFallback`, confirmed wired to an `img error` listener that swaps in the hand-drawn
mini-panels) — so nothing is broken today and nothing needs to break at release time, but
`promote.py`'s strip loop does not yet cover this folder and PRODUCTION_CRITERIA F1's asset audit
should catch that before this ships to `WOSTests.com`.

---

### Item (b) — S2 reworked into per-row Heroes / Battle stats / Buffs zones (`dff9bf8`)

Read `docs/OCR_UX_FLOW_SPEC.md`'s 2026-08-15 amendment first, as instructed — it is the binding
authority for this section and states plainly: *"Every row's zone feeds the SAME per-side shot
set — the server sorts shots by content, so there is no wrong slot."* Confirmed at the DOM level
before testing: all three of a side's row zones share the identical `data-dropzone="you"` /
`data-dropzone="enemy"` target — there is no separate per-row upload channel to begin with, only a
shared shot array with different cosmetic framing per row.

**The critical question — does an unclassifiable "heroes" upload poison an otherwise-good read
into a false E1 failure? Tested for real, not assumed:**

Uploaded three real images to the "You" side across their three distinct row zones in one battle
side: `C_battle_1.png` (the documented non-stat-panel stand-in for a heroes-shaped screenshot,
per this round's fixture guidance) through the **Heroes** row, `C_battle_3.png` through **Battle
stats**, `C_battle_4.png` through **Buffs**. One real `POST /shell/ocr/panel` call (all three
files in a single multipart request — confirmed via network log), real RapidOCR, zero stubbing.
**Result: landed cleanly on S4 with `24/24 · All 24 numbers are in.`, and the raw response body
(pulled and inspected directly, not inferred) shows `"status":"ok"`, `specials_observed:"read"`,
zero `unreadable_fields`, and every one of the 24 values digit-exact against the same golden
reference used in every prior round** (`Infantry|Attack: 2269.7`, etc.). The response's own
`warnings` array contains seven `"unmatched row near y=…"` entries — this is where the heroes
image's unrecognized tokens went: absorbed by the extractor's existing orphan-token handling as
internal telemetry, never surfaced to the user, never mis-attributed to a real field. **The
dead-end risk does not materialize.** This independently reproduces (with a genuinely adversarial
input, not the builder's own smoke-test image) the commit message's claim that "the heroes
screenshot's tokens do not contaminate the parse."

**Three-zone coverage/Continue logic:** Continue correctly starts disabled with zero uploads
("Add a screenshot to continue"); a single upload to *any one* row (tested: Battle stats alone,
Heroes+Battle-stats+Buffs together) correctly enables it; the "Battle covers both sides" note on
the Enemy side (*"✓ Covered by your battle report"*) still fires correctly off a You-side-only
upload, unchanged by the row rework.

**Per-zone remove:** uploaded two distinguishably-named files through two different rows sharing
one thumbnail strip (confirmed: rows share a single `data-thumbs="you"` display, not one per row);
removing thumb index 0 correctly dropped to 1 remaining (Continue stayed enabled); removing the
last one correctly hid the thumb strip, disabled Continue, and cleared the Enemy side's "Covered"
note — full round-trip, no orphaned state.

**D-043/044/045 honesty chain with Buffs skipped, under the new UI:** uploaded Battle stats only
(Heroes and Buffs rows both left empty) and continued through to S5 on a real read. Chip correctly
read *"All 24 numbers read · your side and the enemy side not filled in — tap to check"*
(`ocrf-needs-attention`, not `ocrf-complete`); both per-side notices present with the exact D-045
popup-icon wording; `#statPanel` confirmed **not** phantom-filled (still at its 1300 default). No
regression from the row rework — the honesty chain lives in `setup.mjs`'s conversion logic, which
this commit didn't touch, and the live behavior confirms that isolation held.

**Heroes row's own honesty:** its copy — *"The hero part at the top. Captain auto-set is coming —
adding it now future-proofs your upload."* — matches the PRD amendment's mandate precisely (says
plainly that captain auto-set isn't wired yet) and matches Ruling #3 (hero-gen defaulting stays
dormant). Not filed as a finding, but noted: a user who uploads *only* a heroes screenshot has no
on-screen signal distinguishing "this did something" from "this is inert for now" — the thumb
looks identical to any other. Given the row's own copy is upfront about the current limitation and
the PRD amendment explicitly sanctions this as a deliberate, honestly-labeled placeholder
("capture-only for now... the row's copy says exactly this"), this reads as accepted-by-design
rather than a gap — mentioned for completeness, not raised to a POLISH item.

**Row counts per type, confirmed directly:** Scout → 1 row (`scout`). City Stats → You gets 1 row
(`citystats`), Enemy presets to Scout's 1 row (`scout`) — matching §3 S2's preset rule. Battle →
3 rows both sides (`battle_heroes`, `battle_panel`, `battle_popup`), in the documented order.

---

### Fresh sweep (regression check for these two commits only — UXJ-001..010 were verified in
Round 5 and are not being re-litigated in full here)

| Check | Result |
|---|---|
| Takeover contract (centered card ≥768px, background scrim, scroll-lock) | Confirmed in viewport at both widths throughout this round's testing. |
| UXJ-007 (background inert while modal-only open) | Re-confirmed: `main.inert === true`, `.focus()` on the live page's `#runBtn` blocked, while on the reworked S2. No regression from the new row markup. |
| UXJ-010 (focus restored to the CTA, in viewport, on exit) | Re-confirmed via Escape from the reworked S2: `document.activeElement.id === 'ocrfCtaScreenshots'`, confirmed in viewport. |
| Console errors | Zero, across the entire round (fresh app-restart session, no accumulated noise to discount this time). |
| Horizontal overflow at 375px | Zero, on S1, S2 (all three battle rows, both sides), S4, S5. |

No UXJ-011+ findings this round — both changes are clean.

---

### Coverage log

| Area | How verified |
|---|---|
| Real-screenshot samples (S1 + S2), both widths | Live: `naturalWidth`, viewport-rect, overflow checks on all 5 images at 1280px and 375px. |
| Heroes-zone dead-end risk | **1 real read**: `C_battle_1.png` (Heroes) + `C_battle_3.png` (Battle stats) + `C_battle_4.png` (Buffs), one multipart POST, raw response body inspected directly. |
| D-043/044/045 chain, Buffs skipped, new UI | **1 real read**: Battle stats only, followed through to S5, chip/notices/statPanel all checked. |
| Three-zone coverage/Continue | Live, both the empty-state and populated-state transitions. |
| Per-zone remove | Live, two distinguishable uploads across two rows sharing one thumb strip, removed one at a time to empty. |
| Row counts (Scout=1, City Stats=1+1, Battle=3+3) | Live, all four S1 type picks walked through to S2. |
| Release-gate asset-strip claim | Verified by direct read of `shell/promote.py`'s strip loop (line 398) and the samples `README.md`, not just repeated from either. |
| Takeover contract / UXJ-007 / UXJ-010 | Spot-checked live against the reworked S2 specifically (the surface these two commits actually touch), not a full Round 3-5 re-run. |
| Console/overflow cleanliness | Checked after every screen transition this round; zero errors, zero overflow. |

### Quota consumed

`dev_user`: **2 real OCR reads** this round (30 → 28 remaining, fresh 30/30 pool after the app
restart) — the Heroes-zone adversarial-mix test and the Buffs-skipped honesty-chain test, the two
checks where genuine server-side content classification was specifically what was being judged.
Three-zone coverage, per-zone remove, row counts, and the sample-image checks needed no OCR read
at all (pure upload-state/DOM/CSS verification). Within the 3-read budget with one held in
reserve and unused. `ux-eval` identity: not touched this round.

### Servers

**Verdict is SATISFIED — the loop closes here.** Both evaluator-owned servers (restarted at the
start of this round after the app process reset killed them) were stopped again: mock static
server on :8790, CORS fixture server on :8791. The app on :8200 was left untouched.


---

# UX GATE loop — slot-grid upload redesign (2026-08-29)

Owner mandate: merged S1+S2 slot-grid upload screen (built to a dedicated
multi-doc-upload research round) gated by a UX-expert evaluator loop with
STRICT word minimalism as a hard criterion. Evaluator = resumable agent
(ab337c6fdb34aeb9f); builder = main session. Evidence rule: viewport
rects/offsets via page JS (screenshots never composite on this pane).

## Round 1 — NOT SATISFIED (2 MAJOR, 2 MINOR, 3 NIT)

- UXG-001 MAJOR: Escape with the slot preview sheet open dismissed the FLOW
  and left the sheet orphaned over the entry page. FIXED: #ocrfSlotScrim
  heads decideSheetToClose (slotOpen-first); Escape peels layers topmost-in.
- UXG-002 MAJOR: Buffs "None" link was a 42x17px overlay colliding with the
  tile's picker zone. FIXED: full-width 40px block bar below the tile.
- UXG-003 MINOR: Power sample img 404'd 10+ times per open (capture still
  owed by owner). FIXED: img:null -> no img element until it ships.
- UXG-004 MINOR: corner x 20x20 zero padding. FIXED: ::before hit-slop
  (38px effective, 20px visual).
- UXG-005 NIT: "mobile dialog bottom 816 > 812". RETRACTED as environment
  artifact: the numbers are byte-exact the parked FIRST FRAME of
  .ocrf-dialog-enter (matrix .97/.97/+16) in the non-compositing pane;
  visible browsers complete the entrance and the sheet fits exactly.
  Lesson recorded in the CSS round: headless measurers read offsetHeight.
- UXG-006 NIT: tabs 39px. FIXED: min-height 44px.
- UXG-007 NIT: valid image at a full slot silently ignored. FIXED: gold
  pulse on the tile (reduced-motion-killed); no-room paste pulses summary.

Round-1 PASSES worth keeping: word counts max 13 of the 20 budget across all
7 audited states; mobile first-viewport rect-proven (tiles 181-383, Scan
736-783 at 375x812); point-of-action feedback synchronous; zero old-design
remnants; gating exact in every probed state. Fixes: commit dbe7dfb.

## Round 2 — ABSOLUTELY SATISFIED (loop CLOSED)

Evaluator independently re-measured every fix (offsets, not rects — the
parked-entrance-transform artifact from round 1 is now the documented
measurement rule) and re-ran the full regression sweep at both widths:

- UXG-001: Escape peels the sheet, flow alive, state intact; second Escape
  exits; verified both widths.
- UXG-002: None bar 40px below the tile, zero overlap; full attest/un-attest/
  override cycle wired; zero words added.
- UXG-003: zero troop-power requests across fresh reloads.
- UXG-004: elementFromPoint proves the 38px hit boundary both sides.
- UXG-005: retraction independently confirmed (matrix .97/.97/+16 parked at
  t=1150ms; layout offsets show the mobile sheet bottom exactly 812).
- UXG-006: offsetHeight 44 on all tabs, both widths.
- UXG-007: full-slot flash synchronous (MutationObserver t=7ms on the
  no-room paste), fraction truthful, reduced-motion kill confirmed in CSSOM.
- Regression: word counts unchanged (13/13/13/2/8), mobile first-viewport
  holds with the new bar (content bottom 778 <= 812), gating truthful in
  every probed state, zero console errors.

Verdict: "Ship it." Evaluator's aside that the 2-shot count badge is
untestable ("no slot configured max>1") is wrong about the config (stats and
buffs are max:2) but moot — the badge render is pinned by unit test
(screens_pick_upload.test.mjs). Known real-browser-only residuals unchanged:
entrance-animation smoothness, OS picker/clipboard roundtrips, S3-S5/E1
drives (need a real read).


---

# QA comprehension gate — requirement-row redesign (2026-08-29, owner round 2)

Owner rejected the shipped slot grid from desktop screenshots ("absolute
non-sense... makes no sense from a user understanding perspective"): tiles
clumped left, None orphaned, Enemy tile under the You header. Root cause of
the interleave: the retired S1 type-card desktop rule (3-col .ocrf-scr-body)
poured the merged screen's children into columns. Redesigned via the
frontend-design skill into requirement ROWS in contained You/Enemy cards
(commit 31334aa); gate = FRESH independent QA agent (adcb8cf3b4d3d7d8e),
criterion = a cold-read comprehension quiz ("is it crystal clear what's
required?") + adversarial ambiguity hunt, both widths.

## Round 1 — CRYSTAL CLEAR (0 blockers/majors; 4 MINOR + 4 NIT)

Quiz Q1-Q7 all CLEAR at both widths; the old ownership flaw proven
structurally dead (element.contains + elementFromPoint + geometry). Fixed
(58ea64f): QAC-001 per-thumb indexed x; QAC-002 rejection notes on the row
("Images only" / "N max", aria-live + pulse, locator restores); QAC-003/008
hints ("Your troop details", "Report · ! popup") + h1 "Screenshots";
QAC-004 + Add persists until cap; QAC-005 40px chips. Declined: QAC-006
(back stays — shared wizard header, both exits non-destructive), QAC-007
(scouting yourself is game knowledge). Round 2 re-verdict pending.

## Round 2 — CRYSTAL CLEAR (loop CLOSED)

All six fixes verified with hard evidence (per-thumb removal proven by blob
identity — the survivor IS the second file; all three rejection classes
speak and always restore; caps probed directly on all four slot types;
chips 40px both widths; zero truncation at 375 including the new texts).
Both declines' rationales accepted (QAC-006 back stays / QAC-007 game
knowledge). Capacity-wording removal judged SUFFICIENT: the persisting
+ Add chip discloses "more allowed" exactly when relevant, "N max" bounds
it, and stats/buffs share the identical mechanism.

Residual NITs, non-gating, documented: QAC-009 (per-thumb x hit-slop
grazes the row button by ~3px slivers — removal trivially reversible);
QAC-010 (rejection note holds ~2s vs the stated 1.6s in the parked pane;
consecutive rejections extend the hold by design; never-permanent invariant
proven in every path); QAC-003 residual (Power sample box empty until the
owner's real capture — no exemplar beats a fabricated one).

Verdict: CRYSTAL CLEAR at both widths, cold read and fix verification.
Fixes commit 58ea64f; ledger closed 2026-08-29.

## Round 3 — NOT CLEAR (1 BLOCKER, 2 MAJOR) — owner-walkthrough surface

The owner's 2026-08-30 walkthrough changes (instruction hints, full tab
names, battle scope toggle, symmetric City — commit e779582) re-audited
cold. The new comprehension surface itself passed (Q8 one-report-covers-
both, Q9 scope discovery + non-destructive parking blob-verified, Q11
required-ness without the retired *, Q12 symmetric City). Findings:

- QAC-011 BLOCKER: the None attestation was ONE shared bit behind two
  per-side chips — enemy-None silently attested the you side, the phantom
  reached the Scan gate, and removing a masking file resurrected it
  cross-side. FIXED per-side end-to-end (app state {you,enemy}, model
  attested-by-side w/ boolean back-compat, controller per-side read flags);
  same-report default keeps ONE deliberate shared surface and the read
  guard sends the shared flag for both sides in same-mode.
- QAC-016 MAJOR: the buffs hint named the WRONG in-game screen ("stat
  bonuses" = the main panel's title, D-043's exact trap). FIXED: "Upload
  the special bonuses popup (!)".
- QAC-012 MAJOR: desktop two-col cards set the buffs instruction as a
  137px one-word-per-line tower. FIXED: cards stack the action chips
  vertically; hint gets ~135px, row 87px.
- QAC-013/014 MINOR/NIT: drawn stand-in now ghosts at .55; possessives
  uniform; duplicate parentheticals gone. QAC-015 NIT accepted (the
  dictated stem, no residual cost after the fixes).

## Round 4 — CRYSTAL CLEAR (loop CLOSED for the walkthrough round)

Per-side attestation verified as an 8-path matrix (independent directions,
per-side file precedence, no cross-side resurrection, collapse truthful
with the stale flag inert both mirrors, same-mode uploads clear both,
re-expand mutates nothing — "each mode shows precisely the attestations it
consumes"). All other fixes verified verbatim; rejection notes swap/restore
the renamed hints; zero new defects. Fixes commit 4d0d180; closed 2026-08-30.

## Round 5 — CRYSTAL CLEAR (scope redesign; owner /loop mandate satisfied)

Owner rejected round-4's cards+checkbox on sight ("What's you? What's
enemy? What does the check box do?"; his dead checkbox = stale-tab version
skew, verified alive with real mouse events, moot — control deleted).
Redesign (058ea3f): segmented "Whose battle report?" Mine / Enemy's / Both
ABOVE the rows (gold active pill) + "Each report shows both sides." —
mine/enemy = 4 plain rows for that report; both = two labeled cards
"Your report" / "Enemy's report" w/ per-card counts, Scan 0/6; every scope
a full read; scope switches park shots non-destructively.

Gate verdict CRYSTAL CLEAR on the owner's exact bar: options visible above
the fold at both widths (label 186/pills 211-251/note 257 desktop;
160/185-225/231 mobile, zero scrolling), one-report-covers-both carried by
the label+note conjunction, the Both cards structurally contain their own
rows, pills guessable without tapping, hints clear w/ no word-tower return.
Adversarial: full scope round-trips blob-verified (1/3 -> 0/3 -> 1/6 ->
1/3), real-mouse pill clicks, None-per-scope matrix, scout/city untouched.

QAC-017 MINOR accepted w/ rationale: cross-scope None propagation is the
battle-wide attestation ("no buffs on either side", owner-defined
2026-08-25) — every scope's display is truthful; on-screen explanation
would spend words on a rare path. QAC-018 NIT FIXED post-verdict
(radiogroup pills; "Your report: X" aria prefixes under Both). QAC-019 NIT
accepted (mobile buffs hint 5 lines, untruncated). Loop CLOSED 2026-08-30.
