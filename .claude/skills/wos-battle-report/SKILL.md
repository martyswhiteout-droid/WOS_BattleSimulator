---
name: wos-battle-report
description: Use whenever Martin sends Whiteout Survival battle-report screenshot(s) to extract into a normalized JSON for the battle simulator. Enforces capturing EVERY field — STATS ARE MANDATORY AND ALWAYS EXIST (scroll to the "Stat Bonuses" screen, which is a SEPARATE screen from Battle Overview and is easy to miss). Also classifies the report Type 1 (deterministic) vs Type 2 (procs).
---

# WoS battle-report capture

A WoS battle report is **multiple screens** (scroll down / swipe): Battle Overview
→ Bonus Source → Chief Gear Comparison → **Troop Power Comparison** → **Stat
Bonuses**. Martin sends the screenshots. **The Stat Bonuses screen is on screen 2+
and is the one most easily forgotten — it was missed once and caused a false
"engine is wrong" investigation. NEVER skip it.**

## MANDATORY fields — every report has these, capture ALL of them

1. **STATS (Stat Bonuses screen) — ALWAYS EXISTS, NEVER OPTIONAL.** For EACH side,
   the per-class stat bonuses as shown: Infantry/Lancer/Marksman × Attack /
   Defense / Lethality / Health (the "+NNN.N%" values). These ARE the scouted
   stats. If you only have the Battle Overview screen, the report is INCOMPLETE —
   ask Martin for the Stat Bonuses screen before extracting.
2. **Troop types + volume** per side (Troop Power Comparison: which classes, count,
   and the troop **tier/level as displayed**, e.g. "Lv 1.0" — capture what the
   report shows, do NOT assume a tier).
3. **Battle Overview**, both sides: troops, losses, injured, lightly injured,
   survivors, power loss, winner, timestamp, coords.

## OPTIONAL fields — may or may not exist (a battle can have no heroes)

4. **Hero names** (captain per class) — if present.
5. **Skill names + TRIGGER COUNTS** — if present. Trigger counts are how many times
   each proc fired (NOT when). This is what makes a report Type 2.
6. **Joiners** (rally-join heroes) — if present. Capture ALL copies (duplicates
   STACK — see [[joiner-stat-suppression-bug]]).

## Classify the report (drives how it is used — see the calibration rule below)

- **Type 1 — DETERMINISTIC (no proc skills).** No hero procs, no troop-skill procs
  (troop skills unlock at T7; Lv/T1-T6 troops have none). Same inputs → same
  survivors/kills every run. These are the ONLY exact-fit calibration targets.
- **Type 2 — HAS PROCS (Ambusher, Volley, Crystal Gunpowder, hero procs).** The
  report shows how MANY times a skill fired, not WHEN. One report is ONE sample of
  a huge proc-timing distribution — a SIGNAL, not ground truth.

## THE CALIBRATION RULE (locked, do not violate) — see ENGINE_CHANGE_CHECKLIST.md

- **Fit the engine EXACTLY to Type 1. Zero fudge factors are allowed if every Type
  1 report fits.** A fudge factor (e.g. an attacker-bias `def_k`) is an admission of
  a missing/incorrect mechanic — fix the mechanic, do not add a knob.
- **NEVER regression-fit to a Type 2 report.** Treat it as a signal only: reproduce
  the proc COUNTS, Monte-Carlo (≥10k), build the outcome distribution, and check
  whether the real outcome lies inside it. Inside (not "impossible") → do NOTHING,
  no calibration. Only an IMPOSSIBLE outcome (outside the whole distribution)
  implicates the engine. A cluster of edge cases is NOT proof of a bug.

## Output

Normalized JSON under `wos_sim/data/` (or `data/experiments/` for controlled
tests), with per-side `stats_pct` (the panel), troop counts, tier, outcome
(survivors/injured/lightly), heroes/skills/joiners if present, and a `type: 1|2`
tag. Then, for Type 1, run it through the engine and confirm EXACT fit; for Type 2,
run the distribution check — never tune params to it.
