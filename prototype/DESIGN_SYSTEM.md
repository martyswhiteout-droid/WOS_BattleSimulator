# DESIGN_SYSTEM — prototype/index.html visual contract

**Audience:** any agent about to change how the UI looks (CSS, new components, layout, motion).
**Status:** BINDING. The style guard test enforces parts of this mechanically
(`wos_sim/predictor/tests/test_ui_style_guard.py` + `prototype/style_baseline.json`).
Read `UX_BACKLOG.md` §0 (UTF-8 discipline) before any edit. Last updated: 2026-07-11.

---

## 1. The design in one paragraph

The page is a deliberate **Whiteout Survival in-game UI pastiche**, split into two "worlds":
a **navy game panel** for everything the player configures (header, scenario rail, input
section — dark navy surfaces, light porcelain controls, glossy blue 3D buttons) and a
**parchment battle report** for everything the engine outputs (cream/gold cards, brown ink,
ember accents). The two sides of a battle are color-coded factions everywhere:
**me = ice blue, enemy = ember red**, laid out as mirror images around a center column.
Depth is physical, not flat: bevels, speculars, ledges, inset wells, glass. If a new element
could not plausibly appear in the game's own UI, it is off-style.

## 2. Hard rules (enforced or load-bearing)

1. **Palette is locked.** Every color literal in `index.html` must already exist in
   `prototype/style_baseline.json`. Need a genuinely new color? Derive it from the tokens
   below (a shade or alpha of an existing hue), then update the baseline **deliberately**:
   `py -m wos_sim.predictor.tests.test_ui_style_guard --update-baseline` and say why in the
   commit message. Never introduce a new hue family (no purples, greens beyond `--ok`/check-green, etc.).
2. **Self-contained page.** No CDNs, no `@import`, no external fonts/scripts/styles —
   no Tailwind/Bootstrap/etc. Fonts are the local files in `assets/fonts/`. (Enforced.)
3. **Append-only style rounds.** Never rewrite historical CSS. Add a new commented block at
   the END of the `<style>` element: `/* === Round N — <purpose> === */`. Later rules win by
   source order; that is the file's versioning mechanism.
4. **Reduced motion stays.** The global kill-switch
   `@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}`
   must survive every edit (enforced). New JS-driven motion must ALSO check
   `matchMedia('(prefers-reduced-motion: reduce)')` before running (see the parallax module).
5. **`!important` budget.** Count may not grow past the baseline. Fix specificity by
   ordering/scoping instead.
6. **Both worlds, both widths.** Any change is verified on the navy input side AND the
   parchment forecast side, at ≥1280px and at ~800px (layout collapses under 960px).
   No horizontal page scroll, ever.

## 3. Tokens

### Faction identity (both worlds)
| Role | Ice (me) | Ember (enemy) |
|---|---|---|
| core | `#2EA1F2` | `#EF5F5F` |
| bright | `#55BFFF` | `#FF8181` |
| deep | `#1682D8` | `#C94646` |
| ghost bg | `rgba(46,161,242,.12–.14)` | `rgba(239,95,95,.12–.16)` |

Me = left column, enemy = right; enemy rows are `flex-direction:row-reverse` mirrors of mine.

### Navy world (header / rail / input)
- Surfaces: panel `#0B273D` · raised `#123B59`/`#123f66` · lit `#164A72` · dark inset well `rgba(6,20,34,.38)`
- Text on navy: primary `#EAF6FF` · muted `#B9D2E5` · labels `#cfe3f4` · faint `#8FB0C9`
- Light control tiles: face `#f4faff` (ramp to `#eef6fd`) · card `#cfe6f9`/`#d4e8f7` · border `#b3d0ea` · hover `#8fbde4` · focus `#5AAEF3` · text on tiles `#31506b`
- Glossy CTA ramp: `#8ED0FF → #5AAEF3 → #3E97E8`, ledge `#235f9c` (red variant `#FF9090 → #EF6868 → #DB4F4F`, ledge `#A83A3A`)
- Section title bars: `#78B5EA → #5E9DDA` · hero bars (periwinkle): `#93A0C8 → #6E7CA8`

### Parchment world (forecast)
- Card: `#FDEFD3 → #F7E3B9`, border `#E7C783`, header flourish `#D9A94F`
- Ink: body `#6a5647` · headers `#8d5b31` · muted `#8d6d56` · faint `#9a806c`
- Inner tiles: `rgba(255,255,255,.55)` wells with `rgba(106,86,71,.12–.22)` hairlines
- Active toggle face: `#FF9E7A → #EF6A4A`

### Typography
- **Chakra Petch** — display: headers, buttons, big numbers. 600–700, slight letterspacing.
- **Inter** — body copy and control labels.
- **IBM Plex Mono** — data, values, eyebrows (eyebrows: 9–11px, letterspacing `.1–.28em`, uppercase).

## 4. Material recipes (copy these, don't invent new finishes)

**Glossy 3D button** (Run/Refresh family):
```css
background:linear-gradient(180deg,#8ED0FF 0%,#5AAEF3 46%,#3E97E8 100%);
color:#fff;text-shadow:0 1px 2px rgba(10,52,96,.55);border:0;border-radius:16px;
box-shadow:inset 0 2px 1px rgba(255,255,255,.65),inset 0 -2px 1px rgba(20,96,170,.45),
  0 2px 0 #235f9c,0 3px 5px -2px rgba(4,22,44,.7);
/* hover: brightness(1.05) + translateY(-1px) + one-shot ::after sheen sweep
   active: translateY(2px) + shorter ledge */
```

**Game tile with specular** (formation cards):
```css
position:relative;isolation:isolate;
background:linear-gradient(180deg,#ddeffc 0%,#cfe6f9 55%,#c0dbf3 100%);
/* ::before — z-index:-1; inset:1px 1px 52% 1px; border-radius to match;
   background:linear-gradient(180deg,rgba(255,255,255,.5),rgba(255,255,255,.07)) */
box-shadow:inset 0 1px rgba(255,255,255,.78),inset 0 -2px 3px rgba(49,80,107,.14),
  0 9px 18px -12px rgba(0,0,0,.62);
```

**Dark inset well** (on navy — e.g. mode-check box):
```css
background:rgba(6,20,34,.38);
box-shadow:inset 0 2px 5px rgba(0,0,0,.45),inset 0 -1px 0 rgba(255,255,255,.07),
  0 1px 0 rgba(255,255,255,.06);
```

**Glass-tube slider**: two-layer track background — highlight ridge over the faction fill:
```css
background:linear-gradient(180deg,rgba(255,255,255,.38),rgba(255,255,255,0) 55%),
  linear-gradient(90deg,var(--fc) 0 var(--fill,50%),var(--tk,#20313d) var(--fill,50%) 100%);
box-shadow:inset 0 1px 2px rgba(0,0,0,.42),inset 0 -1px 1px rgba(255,255,255,.16);
/* thumb: radial-gradient(circle at 50% 30%,#fff,#eef7fa 55%,#cfe3ee), 3px faction border.
   JS must keep --fill in sync with value (see paintFill in sideSlider / paint in buildFormation). */
```

**Parchment report card** (forecast `.fc-part`): gold border + double frame:
```css
background:linear-gradient(180deg,#FDEFD3,#F7E3B9);border:1px solid #E7C783;border-radius:13px;
box-shadow:0 12px 24px -14px rgba(0,0,0,.55),inset 0 0 0 1px rgba(255,255,255,.5),
  inset 0 1px 0 rgba(255,255,255,.75);
/* header .h gets a 44px×3px #D9A94F→transparent flourish via ::after */
```

**Candy data bar** (every chart bar): `inset 0 1px 0 rgba(255,255,255,.4), inset 0 -1px 0 rgba(0,0,0,.12)`
(flip vertically for bars that grow downward).

**Porcelain input**: `background-image:linear-gradient(180deg,#fff,#eef6fd)` over the
`#f4faff` face + `border:1px solid #b3d0ea` + `inset 0 1px rgba(255,255,255,.85)`.
Selects must restate their two chevron gradient layers BEFORE the ramp layer.

## 5. Motion grammar

- Durations 120–250ms; easing default or `cubic-bezier(.2,.7–.9,.2–.3,1–1.2)` for pops.
- Hover = lift `translateY(-1px)`; press = sink `translateY(1–2px)` with the ledge shadow shortened.
- Popovers: `pop-in` (opacity + translateY(-6px) + scale(.97), ~160ms).
- Primary CTAs: one-shot diagonal sheen sweep on hover (`::after`, skewX(-22deg)).
- Progress: animated 45° candy stripes (`background-size:22px 22px`, linear infinite).
- Backdrop parallax: rAF-lerped `--par-x/--par-y` on `<html>`, applied only under
  `html.parallax-on` with `scale(1.1)` headroom; JS refuses to start under reduced-motion.
- Never animate layout properties; transform/opacity/filter only. Never attach transitions
  to `input[type=range]` backgrounds (live fill must not lag the thumb).
- **Result-reveal motion is confidence-tiered** (Round 14): celebration intensity comes ONLY
  from engine signals (`engine.confidence`/`near_even`/`calibrated` — coin_flip lands clean
  with no glow; uncalibrated gets a small settle; validated gets the full stamp+bloom).
  `win>=50` picks ice-vs-ember *direction* only, never intensity. Choreography fires only on
  user-initiated runs (never the page-load auto-run). Contract: `.claude/skills/wos-emotional-design/`.
- JS-animated **data values** (e.g. the `#pctNum` count-up) must guarantee completion via a
  non-rAF fallback (`setTimeout`) — rAF parks in hidden/background panes and the displayed
  number is data, not decoration.

## 6. Layout invariants

- The `.duo` grid: `minmax(0,1fr) | center-label | minmax(0,1fr)` — me right-aligned toward
  center, foe left-aligned toward center. Keep new side-by-side controls in this pattern.
- Breakpoints: 960px (rail stacks, duos become 2-col), 700px (bottom thumb toolbar), 520px (dense).
- Touch targets ≥ 30px under `any-pointer:coarse` (see the existing coarse-pointer block).
- Focus is always visible: focus ring `#5AAEF3` glow or the global `:focus-visible` outline.

## 7. Verify before you claim done

1. `py -m pytest wos_sim/predictor/tests/test_ui_style_guard.py -q` → must pass.
2. `grep -c "Â\|â€\|â—\|âš" prototype/index.html` → must be 0 (encoding, UX_BACKLOG §0).
3. Live check via the `prototype` launch config (port 8137). **`preview_screenshot` does NOT
   work on this page** (hidden pane ⇒ no frames, rAF parked) — verify with `preview_eval`
   (getComputedStyle / getBoundingClientRect), `preview_inspect`, `preview_snapshot`;
   check console for errors; test at 1440px AND 800px; confirm
   `document.documentElement.scrollWidth <= window.innerWidth`.
