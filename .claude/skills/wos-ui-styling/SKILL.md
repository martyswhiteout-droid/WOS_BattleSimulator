---
name: wos-ui-styling
description: Visual contract for the WoS Battle Simulator front-end (prototype/index.html). Use BEFORE any change that affects how the UI looks or moves — editing CSS, adding/restyling components, new panels/tabs/charts, layout tweaks, animations, fonts, colors, "make it prettier/glossier", or building any new page under prototype/. Also use when a style-guard test failure (test_ui_style_guard.py) needs resolving. The design system is palette-locked and enforced by tests; never improvise styling from scratch.
---

# WoS UI styling — stay true to the design system

The UI is a hand-built **Whiteout Survival in-game pastiche** (navy game panels + glossy
blue buttons for inputs; parchment battle-report cards for outputs; ice-vs-ember faction
mirroring). It looks the way it does on purpose, down to individual shadow layers.

## Non-negotiable workflow

1. **Read `prototype/DESIGN_SYSTEM.md` first** — tokens, material recipes (copy those, don't
   invent new finishes), motion grammar, layout invariants. Read `UX_BACKLOG.md` §0
   (UTF-8 discipline) before saving the file.
2. **Style changes are append-only.** Add a new `/* === Round N — purpose === */` block at
   the end of the `<style>` element; never rewrite historical rounds. Win specificity by
   source order, not `!important` (the `!important` count is budget-capped by the guard).
3. **Stay inside the palette.** Reuse tokens / shades / alphas from DESIGN_SYSTEM.md §3.
   The guard test fails on any color literal not in `prototype/style_baseline.json`.
   A genuinely new color is a design decision: regenerate the baseline via
   `py -m wos_sim.predictor.tests.test_ui_style_guard --update-baseline` and justify it
   in the commit message. Never regenerate just to make red tests green.
4. **No external anything.** No CDNs, no Tailwind/Bootstrap, no `@import`, no remote fonts.
   The page must work offline from `prototype/` alone. (Enforced.)
5. **Motion must respect reduced-motion.** The global kill-switch must survive (enforced);
   new JS animation checks `matchMedia('(prefers-reduced-motion: reduce)')` before starting.

## Before claiming done

- `py -m pytest wos_sim/predictor/tests/test_ui_style_guard.py -q` → green
  (or `py -m unittest wos_sim.predictor.tests.test_ui_style_guard`).
- `grep -c "Â\|â€\|â—\|âš" prototype/index.html` → 0.
- Live-verify via the `prototype` launch config (uvicorn :8137). **`preview_screenshot`
  does not work on this page** (hidden pane → no frames, rAF parked): verify with
  `preview_eval` / `preview_inspect` / `preview_snapshot`, check the console, test at
  ~1440px and ~800px, and confirm no horizontal overflow
  (`document.documentElement.scrollWidth <= window.innerWidth`).
- Check BOTH worlds: navy input side and parchment forecast side.
