# Engine Rebuild — TDD Test Plan

Build the engine **red → green** against these, in order. Each test states its
**oracle** (the exact expected value or the tolerance). Put them in
`wos_sim/predictor/tests/test_pvp_turn_engine.py` (that is the existing test dir —
`test_kernel.py`, `test_summary.py`, etc. live there; there is NO top-level `tests/`)
and also register the integration ones into `wos_sim/regression.py`.

Run: `PYTHONPATH="E:\WOS\Battle Simulator" py -m pytest wos_sim/predictor/tests/test_pvp_turn_engine.py -x -q`
(the environment uses `py`, Python 3.14 — NOT `python`).

Legend: **[U]** unit, **[I]** integration, **[A]** anchor, **[C]** conservation/invariant,
**[H]** honesty. Tolerances are deliberate — near-even is chaotic, so anchor bands are wide
on survivor COUNT but tight on survivor TYPE, winner, and trigger counts.

---

## Tier 0 — mechanics units (no skills)

**[U] T0.1 front-to-back absorption.** One front packet of magnitude M into stacks
Inf=100/Lan=100/Mar=100 (cost_per_kill=1): M=150 → Inf 0, Lan 50, Mar 100. M=250 →
Inf 0, Lan 0, Mar 50. M=500 → all 0, 100 damage wasted (no negative counts).

**[U] T0.2 marksman immortal behind wall.** Front packet M=90 into 100/100/100 →
Mar untouched (=100). Marksman only lose count once Inf AND Lan are 0.

**[U] T0.3 backline bypass.** A `target_mode="backline", target_types=(MARKSMAN,)`
packet of M=40 into 100/100/100 → Inf 100, Lan 100, **Mar 60** (bypassed the wall).
A `(LANCER, MARKSMAN)` packet absorbs Lancer first, then Marksman.

**[U] T0.4 simultaneity.** Two sides each deal lethal damage in one turn; BOTH sets
of casualties are computed from the start-of-turn snapshot (side A's losses this turn
do not reduce side A's outgoing damage this turn). Construct a symmetric 100-v-100
one-type case where each wipes the other → both end at 0 on the same turn, winner
"draw".

**[U] T0.5 counter multiplier.** Infantry into Lancer gets the `cm` bonus; Infantry
into Marksman does not. Assert damage ratio == `cm` for the countered pairing.

**[U] T0.6 battle end / no extra turn.** If defender hits 0 at end of turn t, loop
stops at t; `result.turns == t`; no turn t+1 casualties are recorded.

---

## Tier 1 — cadence & trigger counting (the clock)

Drive these with synthetic death schedules (force a stack to die on a chosen turn) so
the trigger math is isolated from the damage model.

**[U] T1.1 every-turn cadence (Elif SK3, N=1).** Infantry alive `L` turns → triggers
== `L`. Check L=12 → 12, L=19 → 19.

**[U] T1.2 every-N-turns, start_turn=1 (Vulcanus SK3, N=3).** Owner alive `L` →
triggers == `floor((L-1)/3)+1`. L=16 → **6**, L=25 → **9**.

**[U] T1.3 every-N-turns, start_turn=2 (Cara SK3, N=2).** Driving type alive `L` →
triggers == `floor(L/2)`. L=12 → **6**, L=18 → **9**.

**[U] T1.4 attacks-per-type (Vulcanus SK2, N=5).** With per-type lives
(inf=Li, lan=Ll, mar=Lm), triggers == `floor(Li/5)+floor(Ll/5)+floor(Lm/5)`.
(12,14,16) → **7**; (19,25,14) → **10**.

---

## Tier 2 — kill attribution & conservation

**[C] T2.1 conservation per turn.** For every turn, `Σ_source kills_this_turn ==
Σ_type (start_n − end_n)` for the struck side, to 1e-6 relative. Assert inside the
engine AND in a test that runs a full battle and checks every `TurnRecord`.

**[U] T2.2 base vs skill kill split.** One turn: base packet kills K_b, one firing
damage-skill packet kills K_s, applied in order [base, skill]. `auto` telemetry gets
K_b, the skill gets K_s, K_b+K_s == total casualties. A skill applied AFTER the base
only earns kills from the enemy the base did not already remove.

**[U] T2.3 buff-only skills earn zero kills.** A passive OFFENSIVE/DEFENSIVE stat
skill and a DEFENSIVE `+60% def` (Vulcanus SK3) both report `kills == 0` while still
counting `triggers` (matches the report's blank-kill rows). Their effect shows up
only as changed `astat` / reduced incoming damage.

**[U] T2.4 procs change the result.** Same matchup, run with `cara_burst=0` and
`ambush_frac=0` vs nominal. Assert (a) survivor TYPE and/or survivor COUNT differ, and
(b) turn count differs. Proves procs feed the actual casualty path, not just display.

---

## Tier 3 — the two anchors (calibration targets)

Load the matchups directly from the report JSONs (`wos_sim/data/pvp_t12_report_00{1,2}.json`)
so the test data can't drift from ground truth. Run a **deterministic** sim (noise off).

### [A] T3.1 — Battle 1 (report_001)
Oracle (tolerances in parens):
- winner == attacker **(exact)**
- survivor TYPE == MARKSMAN **(exact)**
- turns == 16 **(±1)**
- attacker survivors ≈ 62,364 → **band [30k, 110k]** (wide: near-even is chaotic)
- defender fully wiped (survivors == 0) **(exact)**
- death order his side: Inf(T12) < Lancer(T14) < Marksman survives **(order exact, turns ±1)**
- death order enemy: Marksman(T12) < Inf(T15) < Lancer(T16) **(order exact, turns ±1)**
- trigger counts (±1): his Elif=12, enemy Elif=15, enemy Cara=6, his Vulcanus SK2=7, his Vulcanus SK3=6

### [A] T3.2 — Battle 2 (report_002)
Oracle (tolerances in parens):
- winner == attacker **(exact)**
- survivor TYPE == LANCER **(exact — this is the test the old engine fails)**
- turns == 25 **(±2)**
- attacker survivors ≈ 118,068 → **band [60k, 190k]**
- defender fully wiped **(exact)**
- his MARKSMAN annihilated by ~T14 **(±2)** via bypass procs; his Inf dies ~T19 **(±2)**; his Lancer survives
- trigger counts (±1): his Elif=19, enemy Elif=22, enemy Cara=9, his Vulcanus SK2=10, his Vulcanus SK3=9

### [A] T3.3 — joint fit (the hard one)
Both T3.1 and T3.2 must pass with **one identical parameter set** (same `TURN_PARAMS`).
No per-battle overrides. If impossible, the test is allowed to `xfail` with a recorded
reason string, and QA must be told (see `03_QA_CALIBRATION.md` gate G4).

### [A] T3.4 — composition sensitivity (the matched pair's whole point)
Feed battle-1 panels but swap ONLY the attacker composition from B1's mix to B2's mix
(more lancers, fewer marks). Assert the survivor type moves toward LANCER and the turn
count lengthens — i.e. the engine is sensitive to composition the way reality was.

---

## Tier 4 — telemetry shape

**[U] T4.1 shape matches contract.** `result.skill_telemetry` validates against
`ENGINE_INTERFACE.md` §8: keys `attacker`/`defender`, each with `heroes[]`
(hero, role, troop, skills[{slot,triggers,kills}]) and `troop_skills[]`
(name, troop, triggers, kills). Joiners have `troop==None`, Skill-1 only.

**[U] T4.2 telemetry == accumulated casualties.** For a full battle, every skill's
reported `kills` equals the sum of that skill's `record_kill` across all turns
(cross-check against `turn_log`). No independent recomputation path exists.

**[U] T4.3 ambusher + Cara appear as troop/hero skills with non-zero kills in B2**
(they are what annihilate the marksman). In B1 the same skills have far smaller kills
(marks mostly survive). Assert B2 ambusher/Cara kills ≫ B1.

---

## Tier 5 — honesty / invariants

**[H] T5.1 near-even flag.** For both anchors, `engine_meta["confidence"]=="coin_flip"`
(or near_even==True) and `engine_meta` does NOT return a tight `model_error` around a
point survivor%. Perturb defender strength ±2% → winner or survivor% swings materially
(demonstrating the chaos, matching the measured 1.4% flip).

**[H] T5.2 non-mutating.** After `predict()`, the input `SideProfile`/`ConstructedMatchup`
objects are unchanged (deep-equality pre/post).

**[H] T5.3 CRN determinism.** Same `(seed, n)` → identical results across two calls;
different `seed` → different sampling but same means within MC error.

**[C] T5.4 no negative counts, no resurrection.** Across all turns every stack count
is monotone non-increasing and ≥ 0.

---

## Notes for the builder
- Start Tier 0–2 with tiny synthetic stacks (hand-computable). Only move to Tier 3
  once cadence + conservation are green — the anchors will be un-debuggable otherwise.
- Tier 3 will fail until calibration; that's expected. Get the STRUCTURE (types,
  turns order, trigger counts) right first; hand the magnitude-fitting to the QA
  agent, which owns the parameter search.
- If a Tier-3 sub-assertion is impossible to satisfy structurally (not just
  numerically), STOP and flag it — it means a mechanic in `01_BUILD_SPEC.md` is wrong
  and Martin needs to re-adjudicate, not that you should overfit.
