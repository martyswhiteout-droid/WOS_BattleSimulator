---
name: wos-emotional-design
description: Use when a change targets how the WoS Battle Simulator prototype FEELS rather than what it computes — "juice it up", "make it delightful / rewarding / alive / premium", adding micro-interactions, celebration, or reveal moments, or designing feedback for any user-facing state (run button, loading, result reveal, win/defeat framing, honesty badge, saves, errors). Applies BEFORE implementation via wos-ui-styling.
---

# WoS emotional design — motion as calibrated information

## Overview

`prototype/index.html` is a single-power-user **trust instrument**, not an engagement app.
Its emotional job: make the user trust the prediction **exactly as much as it deserves**.
Core principle: **celebration intensity is a claim about confidence — the UI may never
claim more than the engine does.**

## The register rule

The app *predicts* battles; it doesn't win them. Feedback celebrates the quality of the
read (a decisive call landing), never the victory itself. Translate "win screen" requests
into **verdict-delivery choreography**: anticipation → landing → meaning. Defeat gets the
same intensity in ember — defeat is information, not punishment.

## Intensity ladder — key every effect to observable engine signals

The `/api/predict` payload carries `engine.confidence` (`"coin_flip"`|`"directional"`),
`engine.near_even`, `engine.calibrated`, `engine.model_error` (set in
`wos_sim/predictor/api.py`; the UI reads `FORECAST.engine` but currently ignores the
first two). Tier from these — **never invent a % threshold in front-end JS**; if a
treatment needs a cutoff, the cutoff belongs in the engine/API.

| Signal state | Allowed treatment |
|---|---|
| `confidence === 'coin_flip'` / `near_even` | Hedged: motion says "landed", never "triumph". No glow, burst, or bloom; neutral ink. The hedge is designed output (CLAUDE.md rule 4) — style it proudly, don't mute it apologetically. |
| directional + NOT `calibrated` (badge: "Uncalibrated · directional") | Restrained: sequencing, pops, stamps — no burst-tier effects while the badge admits 10–15% model error. |
| directional + `calibrated` (badge: "Validated ± X%") | Full treatment permitted. |

## Moment gates

- Reveal choreography fires **only on user-initiated runs** (`#runBtn`, `#refreshBtn`,
  Enter). The `DOMContentLoaded` auto-run and tab-restore re-renders take the instant
  path (`renderCharts(false)`).
- One celebration per distinct forecast; a new run cancels the previous sequence's
  timers (mirror the `activeRun.abort()` pattern).
- Nothing loops forever except the existing `stale-pulse` — persistent attention loops
  are reserved for "your forecast is out of date".

## Moment map (journey audit 2026-07-14)

| Moment | Emotion to land | Current state |
|---|---|---|
| Run press (`#runBtn`) | commitment — press acknowledged | flat: 220 ms brightness blip; sheen is hover-only |
| overlay → report handoff | arrival | flat: hard cut after 260 ms |
| verdict number (`#pctNum`) | anticipation → landing | flat: `textContent` snap |
| verdict meaning | comprehension | missing: no victory/defeat/too-close framing anywhere |
| honesty badge (`#fcProv`) | authority — part of the verdict, not a footnote | flat: silent text write |
| below-fold charts | analysis | leave functional; don't choreograph |
| Final Stats (config side) | responsiveness | flat: instant green/red snap; ease/highlight yes, celebration no |
| streaks / scores / mascots / daily mechanics | — | never; single-user tool |

## Hand-off (REQUIRED)

This skill decides **when/why** feedback exists. **How** is owned by the skill
`wos-ui-styling` + `prototype/DESIGN_SYSTEM.md` (palette lock, append-only rounds,
reduced-motion kill-switch + JS `matchMedia` guard, transform/opacity/filter only,
`!important` budget, style-guard test). Read both before implementing.

## Red flags

- A confidence threshold written in JS (`win >= 55`) → read the engine fields instead.
- Full celebration while `#fcProv` says Uncalibrated → tier it down.
- Choreography firing on the page-load auto-run → gate on user initiation.
- Confetti/fireworks for a *predicted* outcome → register error; it's a forecast.
- Any streak/score/gamification mechanic → delete.
