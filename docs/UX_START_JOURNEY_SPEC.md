# Start journey, desktop paste, generation picker — build spec

**Owner directive:** 2026-09-20 (dictated, then asleep — execute autonomously).
**Scope:** FRONT-END ONLY. No Python, no API, no engine, no payload changes.
`formToConfig()` output for the same inputs must be byte-identical before/after.
**Governing rules:** `prototype/DESIGN_SYSTEM.md` (palette lock, append-only style
rounds, no external assets, reduced-motion kill-switch, `!important` budget 10),
`UX_BACKLOG.md` §0 (UTF-8, mojibake self-check), `.claude/skills/wos-ui-styling`,
`.claude/skills/wos-emotional-design`.

## 0. What the owner asked for (verbatim intent)

1. **Desktop paste.** On the screenshot upload screen you can only "+ Add" a file.
   On a desktop the user must be able to Ctrl+V a screenshot, and must SEE a
   placeholder that invites the paste. On mobile: no paste affordance, no paste.
2. **A simple first page.** A newcomer sees three big options, nothing else:
   (a) forecast from battle reports (NOT the words "fill from screenshots"),
   (b) a quick test on heroes and formations with prefilled, equal stats,
   (c) a custom test where they key in every stat themselves.
3. **Hero generation picker.** Per side, captain heroes only: choose "Gen 15" and
   that side's three captains switch to the Gen-15 heroes. Either side, any gen.

Then two quality gates (run by the orchestrator, not by builders): a UX/UI expert
who must be impressed on desktop AND mobile, then an impatient, easily-confused
first-time user whose confusion score must be <= 3/10.

## 1. Architecture

Two surfaces, one contract:

- `prototype/index.html` (single-file app, served bare on :8137 and by the shell on
  :8200) OWNS the start screen, the quick/custom workspace modes, the bottom run
  button and the generation picker.
- `shell/app/ocr/client/*` (injected by the shell at serve time) OWNS the battle-report
  option, the OCR flow, and the paste wells. It plugs into the start screen through
  the contract below. With no shell (bare prototype) the page shows two options.

### 1.1 Contract (both builders code against this EXACTLY)

DOM provided by the prototype:

| id / selector | what |
|---|---|
| `body.view-start` / `body.view-work` | exactly one is set; CSS shows the start screen or the workspace |
| `body[data-mode="quick"]` / `[data-mode="custom"]` | workspace mode (attribute absent on start) |
| `#startScreen` | the start section (`<section class="start" id="startScreen" aria-labelledby="startTitle">`) |
| `#startGrid` | the options grid; children in order: `#startSlotReports`, quick card, custom card |
| `#startSlotReports` | `<div class="start-slot" id="startSlotReports" hidden></div>` — FIRST child of the grid. The shell fills it and removes `hidden`. While `hidden` the grid lays out the two native cards only |
| `button.start-card[data-start="quick"]`, `[data-start="custom"]` | native cards |
| `#startResume` | "Continue your last setup" button, `hidden` unless an autosave exists |
| `#modeBar` | slim bar at the top of `section.input` (workspace only) |
| `#modeBarSlot` | empty `<span class="modebar-slot" id="modeBarSlot"></span>` inside `#modeBar`; the shell mounts its compact launcher here |
| `#runBottom` | bottom "See who wins" button (end of `section.input`) |
| `#genMe`, `#genFoe` | the generation `<select>`s |

CSS classes the prototype defines and the shell may reuse (shell must not restyle
them): `.start-card`, `.start-card--primary`, `.start-card-icon`, `.start-card-title`,
`.start-card-line`, `.start-card-tag`, `.start-card-go`, `.modebar-btn`.

Card inner structure (identical for native and shell cards):

```html
<button type="button" class="start-card [start-card--primary]" data-start="…">
  <span class="start-card-icon" aria-hidden="true"><svg viewBox="0 0 48 48" …/></span>
  <span class="start-card-tag">…</span>            <!-- optional, max 2 words -->
  <span class="start-card-title">…</span>
  <span class="start-card-line">…</span>
  <span class="start-card-go" aria-hidden="true">→</span>
</button>
```

Icons: original inline SVG, `viewBox="0 0 48 48"`, stroke `currentColor`, 2.5px round
strokes, no fills except `currentColor` at low opacity. No emoji, no game art.

JS API provided by the prototype (`window.wosStart`):

```js
wosStart.enter(mode, opts)  // mode: 'quick'|'custom'. opts.from: 'start'|'resume'|'reports'|'hash'|'switch'
                            // opts.template: default true only for quick+from:'start' — see §2.4
wosStart.showStart()        // back to the start screen
wosStart.view()             // 'start' | 'work'
wosStart.mode()             // 'quick' | 'custom' | null
```

Event: `document.dispatchEvent(new CustomEvent('wos:view',{detail:{view,mode,from}}))`
after every change. Routing: `location.hash` = `#start` (or empty), `#quick`, `#custom`
— set by the prototype; browser Back returns to the start screen; loading the page
with `#quick`/`#custom` goes straight to that workspace mode.

The shell calls `window.wosStart?.enter('custom',{from:'reports'})` immediately before
its S5 arrival fills the Stats panel, and must keep working when `wosStart` is absent.

## 2. Prototype — start screen and modes

### 2.1 Start screen

Shown on every load without a mode hash. Header brand stays; `.top-actions` (Runs /
Run forecast / engine note), the scenario strip and the whole workspace are
`display:none` under `body.view-start`. The boot auto-run `runForecast()` must NOT
fire while the start screen is up (it burns a metered sim and renders into a hidden,
zero-size forecast). It fires once, on the instant path (no celebration), the first
time the workspace is entered. Set `class="view-start"` on `<body>` in the markup so
there is no flash of the workspace.

Copy (final unless a gate changes it — keep it this short):

- H1 `#startTitle`: **Who wins this battle?**
- Sub: **Choose how to set it up.**
- Card 1 (shell): tag **Fastest** · title **Forecast from battle reports** · line
  **Upload screenshots. We read the stats for you.**
- Card 2: tag **No typing** · title **Quick test** · line **Test heroes and
  formations. Stats are already filled in.**
- Card 3: title **Custom test** · line **Enter every stat yourself.**
- Resume: **Continue your last setup →** (only when `localStorage['wos:lastConfig:v2']` exists)

Layout: desktop ≥961px three equal cards in a row (two when the slot is hidden),
max content width ~1080px, centred, the cards are the visual centre of the first
viewport (no scrolling at 1440×900 or 1280×720). ≤700px: cards stack full-width, icon
left / text right, each ≥96px tall, all three + resume visible without scrolling at
390×844 and 375×667 (tighten, don't shrink text below 15px title / 13px line).
Whole card is one button (≥44px targets, visible `:focus-visible` ring, Enter/Space).

Material: navy world. Card 1 = glossy blue CTA ramp (DESIGN_SYSTEM §4 "Glossy 3D
button", scaled to a card: gradient, inset highlights, ledge shadow, hover lift
−1px + one-shot sheen, press sink). Cards 2–3 = raised navy panel (`#123B59` family,
1px ice-ghost border, soft inner top highlight, same hover/press grammar, arrow
nudges 2px right on hover). Tags = small caps mono pill. Entrance: cards rise+fade
60ms staggered, ≤220ms, transform/opacity only, none under reduced motion.
Palette-locked: reuse existing literals only (check `prototype/style_baseline.json`).

### 2.2 Workspace mode bar (`#modeBar`, first child of `section.input`)

`[‹ Start]  <mode title> · <one helper line>        [#modeBarSlot] [mode switch link]`

- `‹ Start` = `button.modebar-btn` → `wosStart.showStart()`.
- quick: title **Quick test**, helper **Stats are prefilled and equal. Change heroes
  and formation, then run.**, link-button **Edit all stats** → `enter('custom',{from:'switch'})`.
- custom: title **Custom test**, helper **Every stat is yours to set.**, no link.
- ≤700px: helper line wraps under the title; nothing overflows; no horizontal scroll.

### 2.3 Quick mode (`body[data-mode="quick"]`)

Hide with CSS: the input tab bar (`.input-tabs > .tabbar`), the Stats and Buffs
panels, and the Final Stats block. Force the Troops Formation tab active on entry
(`selectTabIn`). Visible: side roles, troops + formation, captain heroes with the
generation pickers, joiners, `#runBottom`. Custom mode shows everything and, on
entry from the start screen, activates the **Stats** tab.

### 2.4 Quick-test template

Template = the page's own boot defaults (equal stats both sides). Capture it once in
the main boot handler right BEFORE `restoreAutosave()`:
`window.__wosDefaults = formToConfig();` (the only allowed edits to existing JS are
this line and the boot `runForecast()` guard in §2.1).

`enter('quick',{from:'start'})`:
- active scenario already equals the template (compare `own`/`enemy` JSON) → just enter;
- else if fewer than 5 scenario tabs → create a NEW scenario tab named **Quick test**
  holding the template and select it (reuse `makeTab`/`selectTab`; never overwrite the
  user's scenario);
- else (5 tabs) → enter quick mode on the current scenario unchanged and show the
  existing session-note toast: "Scenario limit reached — using your current stats".

`enter('custom',…)` never touches data. `from:'resume'` = custom, no tab change.

### 2.5 Bottom run button

`#runBottom` — big glossy CTA, label **See who wins →**, last child of `section.input`.
Click → `document.getElementById('runBtn').click()` (keeps the user-initiated
celebration path and busy state) then scroll `.forecast` to the top of the viewport
(`behavior:'smooth'` unless reduced motion). Mirrors `#runBtn`'s disabled state
while a run is in flight (observe the attribute; do not fork run logic).

### 2.6 Generation picker

One row at the top of the captain hero block, inside the existing `.duo` grid:
me cell = `<label class="gen-pick">Generation <select id="genMe"></select></label>`,
centre label = **Captain heroes**, foe cell mirrors with `#genFoe`. Options: `Gen 15`
… `Gen 1` (numeric gens present in `ROSTER`, newest first) plus a disabled, hidden-
from-list `Mixed` state shown only when the three captains do not share a generation.
Change → for each class I/L/M call the existing picker's `setHero(name)` with the
`ROSTER` hero of that class and generation (ignore a class the generation lacks).
Sync back: on any `herochange` inside `#capMe`/`#capFoe` (manual pick, config load,
scenario switch, OCR) recompute the select. Porcelain select recipe (same as the
FC/Tier selects). Must sit cleanly in the mobile hero layout (≤700px) — check it.
Joiners are untouched. No payload change: only the hero names change.

### 2.7 Non-goals / guards

No new colours. No CDN/fonts/images. No `!important` growth. Append a new
`/* === Round 18 — start journey, modes, generation picker (owner 2026-09-20) === */`
block at the END of the `<style>` element; new JS in a NEW `<script>` block before
`</body>` (after the Round 8 parallax script). Do not reorder or rewrite existing
CSS/JS. Keep `#statPanel`, `#runBtn`, `#refreshBtn`, tab ids and all existing ids.

## 3. Shell OCR client

### 3.1 Launchers

`screens/entry.mjs`: `mountEntry()` now
1. if `#startSlotReports` exists → render the Card-1 markup (§1.1, id
   `ocrfCtaScreenshots`, classes `start-card start-card--primary`) into it and remove
   `hidden`; and if `#modeBarSlot` exists → mount a compact launcher
   `<button type="button" class="modebar-btn ocrf-launch-mini" id="ocrfCtaReportsMini">`
   with a small report icon + **Fill from battle reports**;
2. else (no start screen in the host page) → legacy hero CTA at the old anchor, with
   the new copy (title **Forecast from battle reports**, note **Upload screenshots.
   We read the stats for you.**).
Both launchers run the same `decideEntryAction` path. Focus returns to whichever
launcher opened the flow when the user backs out. The words "Fill from screenshots"
and "Fastest way. No typing." are retired everywhere (dialog `aria-label` becomes
"Forecast from battle reports"). Update the pinned-copy tests accordingly.

### 3.2 S5 arrival

Before activating the Stats tab: `window.wosStart?.enter('custom',{from:'reports'})`.
The S5 host must land above a VISIBLE `#statPanel` (the takeover charter's
rect-vs-viewport rule still holds).

### 3.3 Desktop paste wells (the owner's headline complaint)

Capability: `canPaste()` = `matchMedia('(hover: hover) and (pointer: fine)').matches`
(pure helper taking an injectable `matchMedia`, exported, unit-tested). Evaluated at
render time and again inside the `paste` listener — on touch devices the listener
returns immediately and no well is rendered (owner: "on mobile you should not be
allowed to do that").

When `canPaste()`:
- every requirement row with room renders a **paste well**: a dashed, clearly
  "empty placeholder" rectangle on its own line under the row text, spanning the row,
  with the "+ Add" button at its right end. It is a `<button type="button"
  class="ocrf-paste-well" data-paste-slot="side:key" aria-label="Paste a screenshot
  into {Your|Enemy's} {label}">`.
- exactly ONE well is **armed** at a time = `pasteTargetSlot(model, app.lastSlot)`.
  Armed well: brighter dashed border (ice for the you card / ember for the enemy
  card), keycaps `<kbd>Ctrl</kbd><kbd>V</kbd>` (`⌘` `V` on Mac — detect via
  `navigator.userAgentData?.platform` / `navigator.platform`) and the words
  **Paste here**. Un-armed wells show only a small clipboard glyph (no words — the
  screen's word budget is nearly spent: ~145 of 150).
- clicking a well arms it (`app.lastSlot = ref`, re-render, keep focus on the well)
  and then tries `navigator.clipboard.read()` as a progressive enhancement: an image
  item → `addFilesToSlot`; permission denied / API missing → stay armed silently;
  clipboard holds no image → the row's existing transient hint says **Copy a
  screenshot first** (restores like the "Images only" hint).
- Ctrl/⌘+V anywhere on the screen pastes into the armed row; after a paste the armed
  state advances to the next empty row automatically (that is already what
  `pasteTargetSlot` returns).
- drag-over a row still highlights it; dropping on the well works (it is inside the
  row tile).
- The desktop dialog may grow (≤ 980px wide at ≥1100px viewports) so two cards with
  wells do not feel cramped; at 1440×900 the whole "your report" card must be visible
  without internal scrolling.
- Mobile/touch render is byte-identical to today's (no wells, no paste).

### 3.4 Quota chip vs header (existing defect on the journey)

At ≤700px the fixed quota chip (`shell/app/overlay/overlay.css`) overlaps the header's
Runs select and Run button. Fix in overlay CSS: the chip must never cover an
interactive control at 360–430px widths (e.g. dock it under the header row, or make
it static in flow below the header on small screens). Check start screen AND
workspace.

### 3.5 Tests (node: `node --test shell/app/ocr/client/tests/*.test.mjs`)

Update pinned copy; add: start-slot mount vs legacy fallback; mini launcher mount;
`canPaste` true/false; render with paste on (one armed well = pasteTargetSlot, wells
only on rows with room, none when full/attested-none) and paste off (no
`ocrf-paste-well` in the HTML); word budget with paste on (≤ +8 words over
paste-off); Mac keycaps. Keep the whole suite green. Python:
`py -m pytest shell/tests -q` must stay green (no Python edits expected).

## 4. Verification every builder must run before reporting

- `py -m pytest wos_sim/predictor/tests/test_ui_style_guard.py -q` (prototype builder)
- `grep -c "Â\|â€\|â—\|âš" prototype/index.html` → 0
- `node --test shell/app/ocr/client/tests/*.test.mjs` (shell builder)
- Real browser check with Playwright (python `playwright` is installed, chromium
  works headless) against `http://127.0.0.1:8201/` (QA instance of the shell, same
  working tree, static files are read per request — no restart needed) at 1440×900,
  1280×720, 390×844 (`is_mobile`, `has_touch`) and 375×667: screenshots reviewed by
  the builder, zero console errors, `scrollWidth <= innerWidth`, every flow in §2–§3
  clicked through at both widths.
