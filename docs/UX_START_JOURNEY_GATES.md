# Start journey — quality gates (charters + ledger)

Owner directive 2026-09-20: build → **Gate 1** (UX/UI expert must be impressed, desktop
and mobile) → **Gate 2** (impatient, easily-confused first-time user; confusion score
must be ≤ 3/10) → iterate until both pass. Build spec: `docs/UX_START_JOURNEY_SPEC.md`.

## How reviewers drive the app

A persistent headless browser driver keeps state between commands:

```
py "<SCRATCH>\uxd.py" <session> new desktop|laptop|tablet|mobile|small
py "<SCRATCH>\uxd.py" <session> goto http://127.0.0.1:8201/
py "<SCRATCH>\uxd.py" <session> shot <label>        # prints a PNG path → open it with the Read tool
py "<SCRATCH>\uxd.py" <session> clicktext "Quick test" | xy <x> <y> | click <css> | press <Key> | type <text>
py "<SCRATCH>\uxd.py" <session> select <css> <label> | scroll <dy> | back | reload | wait <ms>
py "<SCRATCH>\uxd.py" <session> pick <x> <y> <option label>    # dropdown at those screenshot coordinates → choose that option
py "<SCRATCH>\uxd.py" <session> choosexy <x> <y> <file…>     # click at coordinates that opens a file picker, then pick files
py "<SCRATCH>\uxd.py" <session> drag <x1> <y1> <x2> <y2>     # drag (sliders)
py "<SCRATCH>\uxd.py" <session> choose <css> <file…>         # same, by CSS selector (experts only)
py "<SCRATCH>\uxd.py" <session> copyimg <file>          # "I copied a screenshot" → then: press Control+V
py "<SCRATCH>\uxd.py" <session> controls | text | eval <js> | console | info     # inspection (experts only)
```

Profiles: `desktop` 1440×900, `laptop` 1280×720, `tablet` 820×1180 touch, `mobile`
390×844 touch, `small` 375×667 touch. `xy` takes the pixel coordinates you see in the
last viewport screenshot. App under test: `http://127.0.0.1:8201/` (QA instance of the
shell + prototype, unlimited quota). Dummy battle-report screenshots:
`shell/tests/fixtures/panel_ocr/images/` — `C_battle_1.png` (heroes + experts),
`C_battle_3.png` (battle stats, two columns), `C_battle_4.png` (special-bonuses popup),
`C_battle_2.png` (troops), `C_scout.png`, `C_citystats_1.png`.

## Gate 1 — UX/UI expert charter

**Who:** principal product designer — human-centred design, mobile app UX, modern UI
craft, accessibility. Exacting. Not a rubber stamp; equally, not a scope-creeper.

**What is under review:** the owner's three asks and the path they sit on —
(1) the first page with three options, (2) quick-test and custom-test workspaces up to
and including pressing "See who wins" and seeing the forecast arrive, (3) the hero
generation pickers, (4) the battle-report upload screen with desktop paste wells
(desktop: visible placeholder + Ctrl+V works; touch: no wells, no paste).

**Fixed constraints (not findings):** the visual language is a deliberate Whiteout
Survival in-game pastiche (navy panels, glossy blue buttons, parchment reports; palette
locked by `prototype/DESIGN_SYSTEM.md` and a style-guard test); no external fonts /
CDNs / images; upload-row instruction sentences and row labels are owner-dictated; the
upload screen has a tested word budget; front-end only. Judge excellence WITHIN that
language. Pre-existing issues outside the reviewed path go in a separate
"out of scope" list and never block.

**Method (every round, on the current build):** drive the real app at `desktop`,
`laptop`, `mobile`, `small` (tablet sanity once). Look at real screenshots for every
claim. Exercise: first-load impression (5-second test), each option, quick test →
change both generation pickers → formation → run → forecast arrival, custom test →
Stats tab → type values → run, browser Back, resume link for a returning user, direct
`#quick` / `#custom` links, keyboard-only pass (Tab order, focus visibility,
Enter/Space, Escape), reduced-motion, upload screen: armed well, click-to-arm, real
`copyimg` + `Control+V`, row fills and armed state advances, full rows, enemy card,
"Use your report for the enemy too", mobile render without wells, quota chip never
covering a control. Check console errors and horizontal overflow.

**Findings format:** `ID · severity (Blocker / Major / Minor / Polish) · viewport ·
steps · what you saw (screenshot path) · why it matters (principle) · concrete fix`.

**Verdict:** `SATISFIED` only when no Blocker/Major/Minor remains AND craft scores are
≥ 9/10 for desktop and ≥ 9/10 for mobile (first impression, clarity, affordance,
feedback, consistency, accessibility, polish). Otherwise `NOT SATISFIED` with the
ordered fix list. On re-review, verify each prior finding as FIXED / NOT FIXED /
REGRESSED before looking for new ones.

## Gate 2 — first-time user charter

**Who:** a casual Whiteout Survival player. Impatient, skims, never reads more than a
few words, gets confused easily, has never seen this site, not technical. Gives up
quickly. Acts only on what is visible in screenshots (no DOM inspection, no `eval`,
no `controls`, no `text`, no CSS selectors except the file-picker `choose` fallback).

**Tasks (goals, not steps):**
1. Land on the site cold. In five seconds: what is this, what can I do, what would I tap?
2. "I just want to see if the enemy's Gen 14 heroes beat my Gen 15 heroes with a
   60 / 20 / 20 formation" — get a win percentage.
3. "I have screenshots of my battle report" — get a forecast from them (desktop: one
   is already copied to the clipboard, try pasting; phone: upload).
4. "I want to type my own numbers" — set a few stats for both sides and get a forecast.
5. Find the way back to the first page and start something else.

**Score:** confusion/dissatisfaction 1–10 per task and overall (overall ≥ the worst
task unless justified). 1 = instantly obvious, never hesitated · 2 = one tiny
hesitation · 3 = hesitated once or twice, recovered alone in seconds · 5 = had to guess
or backtrack · 7 = lost, got there by luck · 10 = gave up. Every point above 1 needs
the exact moment, screenshot and the thought in the user's head. **Pass = overall ≤ 3
on desktop AND on mobile**, from a FRESH agent each round (a returning tester has
learned the UI and is no longer a first-time user).

## Ledger

(rounds appended below by the orchestrator)

### Gate 1 · round 1 — NOT SATISFIED (desktop 7.0, mobile 6.2)

Reviewer report: session scratchpad `gates/ux_round1.md` (UXE-001…027; 1 Blocker, 7 Major).
Orchestrator triage:

- **Accepted → prototype builder:** UXE-002 (primary-card contrast), 005 (header run
  button demoted to a compact "Re-run" in the workspace; `#runBottom` is the one primary),
  006 (card hover/press physics + sheen), 007 (focus ring on mode title), 009 (card
  alignment), 010 (generation pickers mirrored, ember chevron, aligned to hero tiles),
  011 (375×667 fit with resume), 012 (resume as centred ghost pill), 017 (44px touch
  targets), 023 (Mixed state styling), 026 (generation-change pulse), 027 (Custom → Quick
  reciprocal link); plus the out-of-scope doubled "+" on "+ New scenario".
- **Accepted → shell builder:** UXE-001 (legal strip no longer eats taps / overlays
  controls), 003 (click arms only — clipboard auto-read removed), 004 (only the armed well
  says "Paste here"), 005 (shell stops relabelling `#runBtn`), 008 (auto-advance goes to
  the first EMPTY row; `n/max` counter on multi-file rows), 013 (scroll-body fade), 014 (row
  min-height — nothing moves after a paste), 015 (bigger thumbnails, 28/44px remove
  target), 016 (chip minimal on mobile start, hidden under the dialog), 017, 020
  ("Lethality" tile), 021 (plural + expectation copy), 022 (mini launcher = "Battle
  reports"), 024 (legal links nowrap), 025 (arrival scroll clears the sticky header).
- **Declined (fixed constraints from earlier owner walkthroughs, 2026-08-30 / 09-06):**
  UXE-018/019 — "Use your report for the enemy too" stays inside the enemy card and the
  two-cards-always structure stays; UXE-022 (dialog h1) — "Screenshots" is type-neutral
  (battle / scout / city) and owner-approved. The S5 arrival keeps its own "See who wins"
  next to the filled panel (arrival charter: chip + filled panel + action in one view).
