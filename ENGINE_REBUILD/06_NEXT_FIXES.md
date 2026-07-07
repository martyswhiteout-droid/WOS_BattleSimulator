# Next fixes — post-suppression state & prioritized instructions

**Date:** 2026-07-08 · **Author:** engine analyst (Claude) · **For:** Codex + QA agent
**Context:** the scouted-panel suppression fix (commit `251b327`) is verified correct and
kept: it un-inverts anchor 3 on the general path. This doc is what remains, measured,
in priority order. Verified matrix (n=300, seed 4471 / n=100 seed 7):

| Anchor | Reality | GENERAL (post-fix) | TURN (post-fix) |
|---|---|---|---|
| 1 — rally, near-even | A wins, **3.45%** surv, **16t**, MARKS survive | ✓ win 1.00 · 69% surv · 10t | ✓ win 1.00 · **94% surv · 2t** ← collapsed |
| 2 — rally, near-even | A wins, **6.54%** surv, **25t**, LANCERS survive | ✓ win 1.00 · 68% surv · 19t | ✓ win 1.00 · 68% surv · 22t |
| 3 — solo, decisive | A wins, **34.3%** surv, **19–20t**, lancer loss 0% / marks 66% | ✓ win 0.997 · 43% surv · 14t · **class mix inverted** (lan 14% / marks 10%) | ✗ **STILL INVERTED** (A wiped, 9t) |

Reading: the general path now ranks **all three** anchors correctly — winner is
trustworthy. Magnitudes are not: near-even survivor% ~20× off (structural, known),
anchor-3 class mix inverted (no real bypass model), duration 25–30% fast. The turn
engine — the thing meant to fix all that — is now in the worst shape: its `TURN_PARAMS`
were fitted to the OLD (double-counted) stats, so the suppression invalidated the fit
(anchor 1 fell from a ~16-turn grind to a 2-turn blowout), and it still mis-ranks
anchor 3 outright.

---

## P1 — Refit `TURN_PARAMS` against the post-suppression stats, on ALL THREE anchors

The single highest-value task. The fit that existed before `251b327` is void — every
effective stat changed when the double-count was removed. Re-run the calibration
procedure of `03_QA_CALIBRATION.md` §3 with anchor 3 added:

1. **rate** first → turns 16 / 25 / 19–20 (one shared value; record if impossible).
2. **Bypass magnitudes** (`ambush_frac`, `cara_burst`, any backline-skill scaling)
   second — anchor 3 gives the cleanest pins in the corpus:
   - attacker marksman lose **66% while their wall never falls** (bypass received),
   - attacker lancers lose **0%** (wall integrity for 19–20 turns),
   - anchor 1: marks chip ~690k→~580k only; anchor 2: marks annihilated ~T14.
3. **cm / K_skill** last → survivor magnitudes 3.45% / 6.54% / 34.3%.

Acceptance = `03_QA_CALIBRATION.md` gates G1–G9 **plus** `05_ANCHOR3` §3 gates
(winner exact; att surv ∈ [20%,50%]; def wiped; turns ∈ [17,22]; att lancer loss <5%;
att marks loss ∈ [45%,85%]; att inf survivors ∈ (0,15%]).
**G4 honesty rule stands:** one param set for all three anchors, or CONDITIONAL with
the trade-off quantified — never per-anchor overrides.

## P2 — Root-cause the turn engine's anchor-3 inversion (structural, not just fit)

The general engine ranks anchor 3 correctly with the same inputs; the turn engine wipes
the attacker in 9 rounds. That gap is inside the turn loop, not in the stats. Check, in
order:
1. **Wall-holding:** reality's attacker infantry wall (136k, Gisela DT−20%) survived the
   entire battle. In the turn engine it must be collapsing early. Log per-turn front
   damage vs wall HP; verify T12 Indomitable Wall 3 and the DT routing apply post-suppression.
2. **Bypass scaling:** defender's 26.9k T11 lancers should chip attacker marksman
   (66% over ~19t), not help wipe the whole army; attacker's 68k T12 lancers should
   grind defender's 98k T11 marksman. If bypass output scales with something that
   over-weights the defender here, this anchor exposes it.
3. **The suppression parity:** confirm the turn engine's passive-stat layer applies the
   suppression identically to construct.py (Codex says it does — verify with a
   stat-dump equality test between the two paths, add it to the suite).

## P3 — Clear the G10 skill-source audit failures BEFORE locking calibration

`skill_source_audit --live` = **FAIL: 18/145 non-ok**. Calibrating on wrong skill
mechanics bakes the error into `TURN_PARAMS` permanently. Minimum bar: every hero in the
three anchors' kits must be clean or a documented exception —
**Gisela, Flora, Ligeia, Karol, Vulcanus** (anchor 3) and
**Elif, Dominic, Cara, Vulcanus + joiners** (anchors 1–2). Special attention:
Vulcanus SK1 (−20% enemy attack) and Ligeia SK1 (−25% enemy defense) are currently
applied army-wide/permanent/all-rows — verify target class and uptime against the wiki
text (this was L2 in `05_ANCHOR3`).

## P4 — Interim honesty surface (small, ship with P1)

While the general path is the default: `engine_meta`/UI must say what is and isn't
trustworthy — **winner/direction: validated on 3/3 anchors; survivor % and class
composition: NOT calibrated** (near-even survivor% off ~20×, class mix can invert,
duration ~25–30% fast). Keep the "directional" rendering; do not show a tight interval.

## Non-goals (don't spend time here)

- Improving the general engine's class-mix/bypass — that's the turn engine's job.
- New anchors ingestion tooling; three anchors are sufficient for this round. The one
  data ask stays: an attacker-barely-LOSES report when Martin can get one.
