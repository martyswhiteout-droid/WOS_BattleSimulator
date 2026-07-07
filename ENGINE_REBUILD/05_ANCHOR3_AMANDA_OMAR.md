# Anchor 3 — Amanda vs Omar (solo, DECISIVE) + prediction-failure findings

**Date:** 2026-07-07 · **Owner:** engine analyst (Claude) · **For:** Codex (builder) + QA agent
**Ground truth:** `wos_sim/data/pvp_t12_report_003.json` · **Input:** `Scenarios/Calibration_Amanda_Omar.json`

Martin ran a real solo battle through the front-end (1000 runs, seed 4471). **Both engines
invert the winner.** This document is the verified diagnosis and what must change.

---

## 1. The failure (reproduced)

| | Reality | General engine | Turn engine |
|---|---|---|---|
| Winner | **Attacker, decisive** | Defender (p_win 2.6%) | Defender (p_win 0.0) |
| Attacker survivors | **93,432 / 272,772 = 34.3%** | 0% (median) | 0% |
| Defender survivors | **0 (wiped)** | ~38% | ~65% |
| Turns | **~19–20** (Gisela ×19 both sides) | 19–22 ✓ | 13 ✗ |
| Per-class (att) | Inf 2,421 surv / **Lancer 68,193 = ZERO losses** / Marks 22,818 | all wiped | all wiped |

This is NOT a near-even coin-flip the model is allowed to miss: reality was a **decisive
mis-ranking**. G1-style "winner exact" applies.

## 2. Verified defects (in causal order)

### L1 — Scouted-mode double-count of permanent hero stat skills (BUG, proven)
`construct.build` computes `astat = TierBase × (1+panel) × skillmult`. But the scouted
panel **already contains each side's own heroes' permanent stat skills** (that is what
the in-game panel shows). Multiplying `skillmult` on top double-counts them.
Measured on this battle: attacker Attack ×**0.800** army-wide (Vulcanus SK1 −20% enemy
attack landing on him) vs defender Attack ×**1.150** (Karol SK3 +15% own attack —
**double-counted**, it's already inside his +3645% panel). Net ×0.70 relative handicap.
- Why anchors 1/2 never caught it: both sides ran near-identical kits (Elif/Dominic/x) →
  the double-count cancelled. Asymmetric kits (this battle) expose it.
- **Fix:** in `stats_mode="scouted"`, permanent OWN-side stat skills must NOT multiply
  into astat (they're in the panel). Battle-time effects still apply: DD/DT, procs, and
  ENEMY-targeted debuffs (those are *not* in the victim's scouted panel).

### L2 — Enemy-debuff skills applied flat army-wide (SUSPECT, unverified vs wiki)
Vulcanus SK1 (−20% enemy attack) and Ligeia SK1 (−25% enemy defense) are folded as
permanent, all-classes, all-rows multipliers. Verify target-class / uptime / stacking
against the max-level Expedition text (G10 audit: `py -m wos_sim.skill_source_audit`).

### L3 — Stat physics mis-ranks the matchup even with L1 removed (STRUCTURAL)
Strip test (skillmult=1 everywhere, panel-only stats, dd/dt kept): **defender still wins
100%.** The engine's damage index gives the defender ×1.21 before skills, and Lanchester
dynamics turn any static edge into a rout. Reality's attacker levers the engine cannot
currently express:
1. **Sequencing/counter geometry:** defender is 45% T11 marksman behind a 26.9k lancer
   wall — once walls erode, attacker damage lands on cheap squishy marksman; attacker's
   25% T12 lancers ambush-bypass them all battle (counter: Lancer > Marksman).
2. **Sustained bypass:** attacker marksman lost 66% while their own wall NEVER fell
   (lancers 0 casualties) → defender's bypass output was large; symmetric logic says the
   attacker's (bigger, T12) lancer bypass into 98k marksman was larger still.
3. **T12 stacks 3/1/2 vs 0/0/0** and tier bases (T12 vs T11 on two classes).
The turn engine models (1)–(2) STRUCTURALLY but its current magnitudes are fit only to
the two near-even rally anchors — it under-weights them here (13-turn attacker wipe).

## 3. What this anchor uniquely pins (add to acceptance targets)

1. **Winner exact:** attacker wins, defender wiped. (Decisive regime — no coin-flip
   tolerance. If the calibrated engine can't rank THIS, it fails.)
2. **Attacker lancer casualties == 0** (±small): the wall must hold ~19–20 turns.
   This is the cleanest front-to-back + wall-holding test in the corpus.
3. **Attacker marksman lose ~66% via bypass while the wall stands** — pins bypass
   magnitude *received*; defender wipe pins bypass + grind *dealt*.
4. **Turns ≈ 19–20.**
5. **Attacker infantry survivors ≈ 2,421 / 136,386 (98.2% loss but NOT wiped)** — the
   wall must end the battle alive-but-barely. Very sensitive duration+magnitude probe.

Suggested QA gates (mirror `03_QA_CALIBRATION.md` style): winner exact; att survivors
∈ [20%, 50%]; def survivors == 0; turns ∈ [17, 22]; att lancer losses < 5%; att
marksman losses ∈ [45%, 85%]; att infantry survivors ∈ (0, 15%].

## 4. Cadence puzzle logged (do not silently "fix")

Defender Vulcanus shows a **16-trigger** row (10,212 kills) at ~19–20 turns; the current
"every 5 attacks per troop type" reading predicts ~9–12. Either the row is a different
skill slot than assumed or the cadence semantics are still wrong. Anchors 1/2 fit the
per-type reading exactly (7 and 10 triggers), so treat this as an open contradiction —
surface it in QA_REPORT, don't tune it away. Full trigger table is in the report JSON.

## 5. Sanity notes for the builder

- Scenario `role` is `"rally"` because the UI has no solo mode — with `joiners: []`
  the practical difference is nil today, but a proper `role: "solo"` (no rally-widget
  assumptions) is worth adding to the profile schema.
- All five heroes (Gisela, Flora, Karol, Ligeia, Vulcanus) resolve in the skill book and
  hero_generations.json — hero resolution is NOT the failure.
- Relayering did not fire (panels differ; correct).
- The front-end called the GENERAL engine (`params.engine` unset). Decide when the turn
  engine becomes the default; until then users see general-engine output.
