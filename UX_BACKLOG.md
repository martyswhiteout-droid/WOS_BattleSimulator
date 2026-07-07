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

## P2-3 · Mobile (375px)

- **Jump to results:** covered by P1-3's chip. Also consider a sticky mini-verdict
  bar at top once results exist.
- **Bucket labels clip** at the forecast card's right edge (overflow:hidden) —
  let the label row wrap or shrink instead of clipping invisible.
- **Tap targets:** checkboxes measured 13×13px, tab ✕ 9×15px, steppers 26×26px.
  Keep the visual size, grow the hit area (padding or `::after` overlay) to ≥24px
  now, 44px where layout allows.
- **Autosave:** debounce (~1s) `formToConfig()` → `localStorage`; on load, if a
  snapshot exists and differs from defaults, restore it and show a dismissible
  "restored your last session" note. Today an accidental refresh loses everything.
- **Tooltips are hover-only** (dead on touch): for skill icons, make tap toggle a
  small popover with the same text; `title` stays for desktop hover.

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
