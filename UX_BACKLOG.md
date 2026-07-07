# Front-end improvement brief — prototype/index.html

**Audience:** the agent maintaining `prototype/index.html`.
**Source:** independent UX critique 2026-07-07 (Nielsen score 23/40 — solid bones, real gaps).
**Scope:** front-end only. Work top-to-bottom; P1 items are worth doing before any new features.

---

## 0. CRITICAL — file encoding discipline (read before ANY edit)

**Incident:** on 2026-07-07 a save of `prototype/index.html` double-encoded every
non-ASCII character (UTF-8 bytes re-read as cp1252, re-saved as UTF-8). Users saw
`Â·` `â—` `âš ` instead of `·` `●` `⚠` across the entire page. A full repair was
applied the same day (70 lines fixed) — the file is clean UTF-8 **now**.

**Rules from here on:**
1. Always read AND write this file as **UTF-8 (no BOM changes — line 1 already has one; leave it)**.
2. After every save, self-check for re-corruption:
   `grep -c "Â\|â€\|â—\|âš" prototype/index.html` → must be **0**.
3. If your toolchain can't guarantee UTF-8, replace literals with HTML entities /
   `\u` escapes (`&middot;` `●`) instead of raw glyphs.

---

## Already done — do NOT redo or regress

- Header badge "Live engine · local", footer rewritten (stale "static mock / no engine wired" removed).
- `.fc-meta` shows the run count once ("runs 1,000" + "● stochastic|deterministic").
- `showError()` sets `role="alert"` and `scrollIntoView({block:'center'})` — keep both.
- `renderMeta()`/`setVerdict()` render confidence on `eng.calibrated` (uncalibrated → "Uncalibrated · directional", haze hidden). Never render "± 50%" from an uncalibrated `model_error`.
- Skill icons carry `title` tooltips (description text).
- `prefers-reduced-motion` handling (line ~487) — keep.

---

## P1-1 · Config tabs must hold real state  *(decision confirmed by Martin: make them real, don't remove)*

**Problem:** tabs are stateless theater. All inputs are global; switching tabs just
re-runs the same shared form (`loadForecast(){ runForecast(); }`). A user comparing
"Config 1 vs Config 2" is comparing nothing.

**Build:**
- Keep an in-memory `Map tabEl → {config, forecast}`. On tab switch:
  1. snapshot the outgoing tab via the existing `formToConfig()` (it already
     round-trips everything incl. `_ui_buffs`), plus the current `FORECAST` object;
  2. restore the incoming tab via `configToForm(cfg)`; if it has a stored forecast,
     `FORECAST=stored; renderCharts(false)` instead of re-running.
- New tabs start as a snapshot of the current form (or defaults — pick one, be consistent).
- Fix the adjacent paper cuts in the same pass:
  - closing the **active** tab currently leaves zero tabs selected → select a neighbor;
  - the first tab has no ✕ while others do → make uniform;
  - the 5-tab cap is a silent no-op → disable the "+" button at cap with a `title` explaining why.

**Verify:** set different troop counts in two tabs, switch back and forth — inputs AND
verdicts swap correctly; close active tab → neighbor becomes selected.

## P1-2 · Stale-forecast invalidation

**Problem:** edit any of the 40+ inputs after a run and the old verdict keeps
describing inputs that no longer exist. Most dangerous trap in the tool.

**Build:** one delegated `input`/`change` listener on the input zone → add class
`stale` to the forecast section: dim it (e.g. `opacity:.55; filter:saturate(.6)`)
and show a small watermark chip "inputs changed — re-run" near the verdict.
Successful `runForecast()` completion removes it. Ignore events fired by
`configToForm`/tab-restore (set a suppression flag while applying).

**Verify:** run → change one slider → forecast dims + chip appears → Run → restored.

## P1-3 · Inline run status next to the Run button

**Problem:** from the Run button's viewport, the overlay/results are ~1500–2800px
below — a completed or failed run is invisible (errors now scroll, success doesn't).

**Build:** a compact status chip beside `#runBtn`: "Running…" (spinner) → "Done ✓"
(click = scroll to forecast) → "Failed ⚠" (click = scroll to banner). Keep the big
overlay as-is; this is a mirror, not a replacement.

**Verify:** at 375px width, Run → chip visible without scrolling for all 3 states.

## P2-1 · Keyboard & screen-reader cluster

- **Slider focus ring is dead:** `.form-ctl input[type=range]{...outline:none...}`
  (~line 424) beats the global `:focus-visible` rule (~line 30) on specificity.
  Fix: delete `outline:none` there and add
  `.form-ctl input[type=range]:focus-visible{outline:2px solid var(--ice);outline-offset:2px}`.
- **Hero picker popover:** trigger needs `aria-haspopup="listbox"` + `aria-expanded`
  toggling; list needs `role="listbox"` / options `role="option"`; ArrowUp/Down + Enter
  to select; on close (incl. Escape) return focus to the trigger button (today it
  strands focus on the hidden search input).
- **Announce run completion:** one visually-hidden `aria-live="polite"` region,
  updated on success: `Forecast updated — win chance 55.0%`. (Errors are already
  announced via `role=alert`.)
- **Tab close ✕** is a 9×15px `<span>` — make it a real `<button aria-label="Close config">`
  with ≥24px hit area; add a non-dblclick rename path (F2 or a pencil button) —
  dblclick-only is undiscoverable and unreachable by keyboard.
- **Stat inputs unnamed:** every stats-panel input gets
  `aria-label="My Infantry Attack %"` (side + class + stat + unit) and a visible `%` suffix. *(Fold into the Stats-section redesign.)*
- **Final Stats must not be color-only:** the green/red comparison (green = higher
  side vs enemy, red = lower — per Martin) needs a glyph too: append `▲`/`▼` (or
  `=` when equal) next to the number. *(Fold into the Stats-section redesign.)*

## P2-2 · Run-flow hardening

- **In-flight guard:** module-level flag + `AbortController` in `runForecast()`;
  a second invocation aborts the first (or is ignored — pick one); disable
  `#runBtn`/`#refreshBtn` + `aria-busy="true"` while running. Today double-click
  fires two racing POSTs and the slower (staler) response can win.
- **Enter runs the forecast:** global `keydown` (Enter) when focus is in the input
  zone and no popover is open → `runForecast()`.
- **Seed affordance (OPTIONAL — ask Martin):** seed is frozen at 4471, so Refresh
  can never show run-to-run variance. Suggestion: keep the reproducible default,
  add a small "new seed 🎲" control that re-rolls and displays the seed used.

## P2-3 · Mobile overhaul (375–430px) — ✅ SHIPPED 2026-07-07 (do not redo)

**Status:** M1–M6 implemented, adversarially reviewed, and verified live at 375/1360px.
Page height at 375px: 15,628px → **4,640px**; me/enemy pairs stay side-by-side; sections
collapse with live summary chips (distinct `aria-label`s per toggle); toolbar pins to the
thumb zone with `scroll-padding-bottom` so focus-scrolls clear it; 16px inputs (no iOS
focus-zoom); `any-pointer:coarse` hit-area rules; skill-telemetry section collapsible
(collapsed by default on mobile); `#touchTip` popover now dismisses on scroll + Escape,
has `role=tooltip`, and the confidence badge (`#fcProv`) is keyboard-reachable
(tabindex + Enter/Space). Desktop layout regression-checked.
**Leftovers:** M7 manifest/home-screen (optional, not done); skill icons still have no
keyboard path to their tooltips (54 icons, needs focusable buttons); real-device pass
(iOS focus-zoom, scroll-dismiss, safe-area insets) — verified in emulation only.
**Note:** collapsed-section summary chips + the Skill-details collapse toggle are also
visible on desktop (deliberate: fixes the "collapsed accordions hide state" finding).

Original spec below, kept for reference:

**Root cause first:** the responsive CSS exists (breakpoints at 960/520px) but its
strategy is wrong. At ≤960px, `.duo,.quality,.sides-head{grid-template-columns:1fr}`
stacks every *me | label | enemy* pair into one column. That (a) triples the length
of every paired section — the page measures ~15,600px (~19 screens) at 375px — and
(b) destroys the side-by-side me-vs-enemy comparison, which is the product's core
mental model. Fix the strategy, not just the symptoms — in this order:

### M1 · Keep the pairs side-by-side (the big win)
At ≤960px, do NOT stack the sides. Make paired rows 2-up with the label spanning:
```css
.duo{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.duo .lab{grid-column:1/-1;text-align:left;margin-top:6px}
```
Two ~170px inputs fit fine at 375px (values are ≤6 digits). Apply the same to
`.sides-head`, buff rows, and `.quality` (class label spans, me/foe cards side by
side). Keep a persistent MY SIDE / ENEMY header (or ice/ember dots) at the top of
each section so side identity survives without the desktop columns. Expected
result: page length roughly halves AND comparison is restored.

### M2 · Collapse-by-default with live summary chips
At ≤700px, start every input accordion collapsed except Troops + Formation. Each
collapsed header shows its state as a summary chip so nothing must be opened to
check: "Formation 50/20/30", "Buffs Max/Max", "Quality T12·FC10·24 ×3",
"Heroes 3 leads · 4 joiners", "Stats ~1300%". Compute the chips from the existing
`read*()` functions. This turns ~19 screens into ~3.

### M3 · Sticky bottom action bar (thumb zone)
At ≤700px: fixed bottom bar with Run (primary), the inline status chip from P1-3
(Running… / Done ✓ / Failed ⚠), and a "↓ results" jump. Pad with
`env(safe-area-inset-bottom)`. Desktop keeps the current button placement.

### M4 · Touch ergonomics
- **Hit areas ≥44px** for checkboxes (now 13×13), steppers (26×26), tab ✕ (9×15),
  and slider thumbs (grow thumb to ~28px on coarse pointers). Keep visual size;
  grow the interactive box via padding or an `::after` overlay.
- **Stop iOS focus-zoom:** inputs are 13px — iOS auto-zooms the page on focus.
  At ≤700px give all text/number inputs `font-size:16px`.
- **Right keyboard:** `inputmode="decimal"` on every numeric field (stats, troops).
- `touch-action:manipulation` on body (kills double-tap-zoom delay on buttons).
- **Tooltips:** on `@media (pointer:coarse)`, tap toggles a small popover with the
  same text (skill icons, confidence badge); `title` stays for desktop hover.

### M5 · Forecast fit
- Outcome-bucket label row currently **clips invisibly** at the card edge
  (overflow:hidden) — let it wrap or shrink.
- Charts go full-bleed at ≤520px (trim card padding-inline); thin the rounds-chart
  x-axis labels; after the first forecast, show a sticky mini-verdict chip so the
  headline number survives scrolling.

### M6 · State safety
- Debounced (~1s) `formToConfig()` → `localStorage`; restore on load with a
  dismissible "restored your last session" note. Mobile tabs get discarded
  constantly — today that loses every input.
- `scroll-margin-top` on section anchors so the sticky header doesn't cover them.

### M7 · Optional app-ification
Web manifest + icons so it can be added to the home screen as a standalone app;
pairs with the self-hosted-fonts item (P3-2) for offline-friendly use mid-rally.

### Mobile acceptance bar
375×812 and 390×844: no horizontal scroll anywhere; collapsed-state page height
≤ ~5,000px; focusing any input does NOT zoom the page (iOS); Run + status reachable
by thumb without scrolling; Lighthouse mobile tap-target audit passes; the me/enemy
pair for any stat is visible in one glance without horizontal panning.

## P3-1 · Type & contrast floor

- Nine font sizes below 11px; floor ALL text at **10px**, and consolidate ~20
  distinct sizes to ~6 steps.
- Worst measured contrast: `#3C4E5C` on `#0C141D` = **2.15:1** (bucket subtext),
  `#3C4E5C` on `#0A1017` = 2.22:1 (rail hints), `#5E7382` on `#16232F` = 3.23:1
  (picker gen tags). Lighten those grays until every text color hits **≥4.5:1**
  against its actual background (spot-check with a contrast tool, don't eyeball).

## P3-2 · Cosmetic / trust polish

- **Rail tab side-stripe:** `.rail-tabs .tab` selected state colors a 3px
  `border-left` (~line 439–442) — redundant with its full ice border. Remove the
  left-stripe; keep the full border + background change.
- **Demo-verdict flash:** the hardcoded 68.4% verdict in the HTML shows before the
  first real result. Initialize the verdict area to a skeleton/`—` until `FORECAST` exists.
- **Progress copy honesty:** stages ("Resolving hero procs…") are elapsed-time
  fiction. Either drop to a single generic "Simulating…" or leave the bar but cut
  the fake stage names.
- **Telemetry empty state:** when `skill_telemetry` is absent the section vanishes
  silently — show one muted line: "No skill telemetry for this matchup."
- **Semantics:** `aria-selected` is used on plain buttons — either add
  `role="tab"`/`role="tablist"` properly or switch to `aria-current="true"`.
- **Copy consistency:** "Lancers" vs "Marksman" pluralization drifts between labels — pick one convention.
- **Self-host fonts:** Google Fonts CDN in an otherwise-local tool; download the 3
  families as woff2 into `prototype/assets/fonts/` + `@font-face`, so it works offline.

## Data-side (not index.html, flag to whoever owns wos_sim/data)

- `wos_sim/data/skill_display/hero_skills.json` ships wiki typos, mojibake
  apostrophes ("Infantry�s"), and one German-language entry (Ling Xue
  "Furchteinflößende Aura") straight into user-facing tooltips.
- Engine confidence note leaks internal language ("until QA locks TURN_PARAMS") —
  reword for end users once the engine note stabilizes.

---

### Verification bar for every item

No console errors; `grep` encoding check from §0 returns 0; run a forecast end-to-end
(healthy + 0-troops error) after each change; keyboard-walk any control you touched.
