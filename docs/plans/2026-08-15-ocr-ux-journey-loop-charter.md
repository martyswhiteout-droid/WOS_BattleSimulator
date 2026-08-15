# OCR UX journey loop — evaluator ↔ builder charter

**Date:** 2026-08-15. **Requested by:** owner: *"use an evaluator sub-agent to check the user
journey of the OCR flow… if it's not absolutely satisfied, then push back to build agent and
continue to iterate until the evaluator sub-agent is absolutely satisfied that this is the exact
optimized User Experience required and it closely matches what the original clickable prototype
had."*

## Roles and loop

- **Evaluator** (fresh agent, adversarial UX eye): walks the REAL app's OCR journey in the
  browser like a first-time user, side by side with the original clickable mock. Produces a
  round report with a verdict: **SATISFIED** (loop ends) or **NOT SATISFIED** + findings.
- **Builder** (dispatched per round by the coordinator): fixes the evaluator's findings, with
  tests where the fix is logic, and commits.
- The SAME evaluator is resumed for every round (context intact) so standards can't drift.
  The loop runs until the evaluator's verdict is SATISFIED — no round limit.

## References (authority order)

1. `docs/OCR_UX_FLOW_SPEC.md` — the binding PRD **including its dated amendments**.
2. `shell/EVAL_OCR_PANEL_QA1.md` + `shell/EVAL_OCR_PANEL_QA2.md` — behaviors that were
   deliberately decided in QA rounds (e.g. D-044's honest chip, D-045's popup hint) are
   IMPROVEMENTS over the mock, not mismatches.
3. `prototype/mocks/ocr_flow_mock.html` — the owner-approved clickable prototype: the
   benchmark for FEEL — screen structure, copy tone, affordance placement, "8-year-old
   clarity" bar. Where the mock and the PRD/ledgers disagree, the later-dated ruling wins
   (house doc-trust order), but any *unexplained* divergence from the mock is a finding.

## Finding classes

- **JOURNEY-BLOCKER** — the flow breaks, dead-ends, or silently loses user work.
- **MISMATCH** — diverges from the mock/PRD without a documented ruling.
- **FRICTION** — works, but measurably clumsier than the mock's intent (extra taps, unclear
  copy, missing feedback, confusing state).
- **POLISH** — cosmetic.

SATISFIED requires: zero JOURNEY-BLOCKER, zero MISMATCH, zero FRICTION open; POLISH items may
be accepted-and-listed only with a written reason each.

## Journey coverage (minimum per full round)

Entry from the predictor page → S1 type pick (all three types' copy) → S2 upload (hints,
thumbs, remove, both sides where applicable) → S3 reading → S4 review (field states, editor
type-over, provenance, picture view) → S5 completion (chip truthfulness, expand, Undo, Reset)
→ form filled correctly → "See who wins" continuity; PLUS the unhappy paths: wrong-screenshot
E1 recovery (dropzones alive after recovery, notice clears on replacement), missing-popup
refusal (chip + notices + no phantom fill), manual "Type them in myself" floor, free-tier
plan gate (`X-Dev-Plan: free`), and quota-exhaustion messaging. Mobile-width pass
(`resize_window` 375px) on at least the happy path each round.

## Presentation-container mandate (amendment, 2026-08-15 — after the owner
## caught what two SATISFIED-bound rounds missed)

The rounds 1–2 evaluation verified screen CONTENT but never the flow's
PRESENTATION CONTAINER — the flow was rendering as a phone-width column at
the very bottom of the page on desktop, and no check caught it because every
assertion was DOM-presence-based, not viewport-based. Binding from round 3:

- **Viewport-visibility evidence is mandatory after EVERY user action, at
  BOTH widths** (≥1280px and 375px): the element the user must see next
  (heading, dropzone, error, chip) must be shown IN the visual viewport via
  `getBoundingClientRect()` against `innerWidth/innerHeight` — DOM presence
  or `offsetParent` alone is not evidence. (`position: fixed` elements have
  `offsetParent === null` by spec; rect-vs-viewport is the only honest
  check.)
- **The takeover contract:** S1–S4/E1 are a modal dialog — backdropped,
  scroll-locked, centered card ≥768px / full-screen sheet below, explicit
  close (✕), Escape and backdrop-click exit, dialog semantics
  (role/aria-modal), non-destructive exit. S5 is deliberately NOT modal: it
  renders inline at the top of the form section, chip + filled form + "See
  who wins →" together in view. Judge the container itself — entry,
  during-flow, and after-exit states — as part of every round.

## Report

`shell/EVAL_UX_JOURNEY.md` — append one section per round: verdict first, then findings
(class — id UXJ-NNN — evidence — expected-vs-observed, mock/PRD citation), then the coverage
log. The coordinator commits; the evaluator never commits.
