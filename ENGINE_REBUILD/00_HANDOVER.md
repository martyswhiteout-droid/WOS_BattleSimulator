> **STATUS BANNER (2026-07-11): the "SPEC ONLY" line below is HISTORICAL — do not trust it.**
> The turn engine described here has since been BUILT and is the DEFAULT API path
> (`wos_sim/pvp_turn_engine.py`, 47 dedicated tests, `engine="turn"` hardcoded in `server.py`).
> This doc remains valuable for the rebuild mission and the exact anchor definitions (report_001/002).
> For current certification status see `QA_REPORT.md` (top entry); for binding change rules see `ENGINE_CHANGE_CHECKLIST.md`.

# Engine Rebuild — Handover to Codex

**Author:** predictor/engine track (Claude), 2026-07-05
**Audience:** Codex (builder) + a QA agent (validator)
**Status:** SPEC ONLY. No engine code has been written for this rebuild. Build it. *(superseded — see banner above)*

---

## 0. One-paragraph summary

The current PvP engine models hero/troop skills as **time-averaged damage/stat
modifiers**. That is why it (a) cannot tell the front-end how many times a skill
triggered or how many kills it made, and (b) cannot reproduce two real, fully
reconstructed near-even battles. You are to replace the PvP kernel with a
**turn-by-turn, skill-firing simulator** in which every skill proc is an actual
event that **deals real damage, causes real casualties, and thereby changes the
final result** — and is reported to the UI exactly as the in-game battle report
shows it (triggers + kills per skill, per hero, per joiner, per troop skill).

**The kills are not cosmetic.** A skill's reported kills MUST equal the casualties
its damage actually produced in the simulation that turn. Telemetry is a *byproduct*
of the real casualty math, never a separate estimate. This is the single most
important correctness constraint in this document.

---

## 1. Read these first (in order)

| Doc | Why |
|---|---|
| `ENGINE_REBUILD/01_BUILD_SPEC.md` | The engine architecture, mechanics, data structures, kill-attribution rules, output contract. |
| `ENGINE_REBUILD/02_TDD_TESTS.md` | The ordered TDD test suite. Build red→green against this. |
| `ENGINE_REBUILD/03_QA_CALIBRATION.md` | The QA agent's mandate + calibration acceptance gates. Do not declare "done" until QA passes. |
| `ENGINE_INTERFACE.md` §8 | The exact `result.skill_telemetry` JSON shape the front-end expects. |
| `GAME_RULES.md` §6 | The per-strike damage formula. **Reuse it. Do not invent a new damage formula.** |
| `wos_sim/pvp_engine.py` | The existing aggregate engine. Its `_side_damage()` power formula, `COUNTERS`, `ORDER`, `_apply()` absorption are the reusable core. |
| `wos_sim/data/pvp_t12_report_001.json` | **Ground-truth battle 1** (16 turns, marksman survive). Calibration + validation anchor. |
| `wos_sim/data/pvp_t12_report_002.json` | **Ground-truth battle 2** (25 turns, lancers survive). The matched-pair anchor. |

The two report JSONs contain, in their `reconstructed_timeline_*` and
`engine_finding_*` fields, the authoritative mechanics and the full per-turn death
schedule reconstructed from real skill-trigger counts. **Those two battles are the
spec's oracle.** Everything the engine does must be reconcilable with them.

---

## 2. The authoritative combat mechanics (from the battle owner, Martin)

These are game-truth, verified against two real reports. The build spec expands each.

1. **Turn-based, simultaneous strikes.** Each turn both sides fire based on the
   **start-of-turn** state; casualties from both sides are applied together; then
   the turn ends. If a side reaches 0 troops at end of turn *t*, the battle ends at
   *t* (turn *t+1* never commences).
2. **Strict front-to-back absorption.** A volley landing on a side is absorbed by
   **Infantry first, then Lancer, then Marksman.** Verbatim from Martin: *"When a
   volley lands on my army, it is strictly front-to-back."*
3. **Marksman are immortal behind a live wall** — a back-line type takes **zero**
   normal damage while any type in front of it is alive. The ONLY way to hurt the
   back line early is a **bypass proc** (see 4).
4. **Bypass procs reach the back line directly:**
   - **Lancer Ambusher** (troop skill, T7+): a portion of lancer output strikes the
     enemy **marksman** directly, bypassing the front. It is a **proc, not every
     round.**
   - **Certain hero skills strike the back line**, e.g. **Cara SK3** — a periodic
     burst (every 2 turns) that hits enemy **lancer + marksman** directly. Martin:
     *"it hits lancers and marksman directly."*
5. **Counter triangle:** Infantry > Lancer > Marksman > Infantry (attacker deals
   bonus damage into the type it counters). Already encoded as `COUNTERS` in
   `pvp_engine.py`. Crucially, the counter also governs *who dies last*: in battle 1
   the enemy **lancers survived longest because their counter — the attacker's
   infantry — died at T12**, leaving nothing efficient to kill them.
6. **Skills fire on turn-based cadences** (`freq` from the skill book) and some have
   a `duration`. Cadence vocabulary (disambiguated against both reports):
   - **"every N turns"** (e.g. Vulcanus SK3 `freq=3`, Cara SK3 `freq=2`): fires on a
     turn schedule while the owning troop type is alive.
   - **"every N attacks, per troop type"** (e.g. Vulcanus SK2 `freq=5`): each troop
     type has its own attack counter (one attack per alive turn); the skill fires
     each time a type's counter crosses a multiple of N. Trigger count =
     Σ_type floor(type_life_in_turns / N).
7. **Battle length is observable.** Because triggers are counted in the report, the
   battle clock and the per-type death turns are *known* for both anchors (see §3).
   The engine's simulated trigger counts MUST match the reports.

---

## 3. The two anchors — exact targets

Both are the SAME attacker (rally) vs the SAME defender (garrison), fought minutes
apart. **Identical stat panels, identical 1,805,272 attacker total, identical
special bonuses.** The only material difference is troop composition — and the
outcomes diverge wildly. That divergence is the whole point: the engine must be
sensitive to composition the way reality is.

### Battle 1 — `pvp_t12_report_001.json`
- Attacker comp: Inf 783,589 (T11.3) / Lancer 331,529 (T11.6) / Marksman 690,154 (T11.5)
- Defender comp: Inf 979,228 (T11.0) / Lancer 348,222 (T10.8) / Marksman 541,045 (T11.1)
- **Outcome:** attacker wins; **16 turns**; survivors = **62,364 MARKSMAN** (3.45%); defender fully wiped.
- **Death schedule** — his: Inf end T12, Lancer end T14, Marksman survive. Enemy: Marksman end T12 (his ambush), Inf end T15, Lancer end T16.
- **Trigger oracle:** his Elif SK3 = 12, enemy Elif SK3 = 15, enemy Cara SK3 = 6, his Vulcanus SK2 = 7, his Vulcanus SK3 = 6.

### Battle 2 — `pvp_t12_report_002.json`
- Attacker comp: Inf 656,570 (T11.4) / Lancer 522,386 (T11.8) / Marksman 626,316 (T11.5)
- Defender comp: Inf 1,087,726 (T11.1) / Lancer 354,482 (T11.1) / Marksman 426,664 (T11.0)
- **Outcome:** attacker wins; **25 turns**; survivors = **118,068 LANCERS** (6.54%); permanent losses 33,199; defender fully wiped.
- **Death schedule** — his: Marksman ~T14 (proc-annihilated via enemy Ambusher + Cara SK3 bypass), Inf end T19, Lancer survive. Enemy: Marksman ~T18, Inf end T22, Lancer end T25.
- **Trigger oracle:** his Elif SK3 = 19, enemy Elif SK3 = 22, enemy Cara SK3 = 9, his Vulcanus SK2 = 10, his Vulcanus SK3 = 9.

Panels, joiners, T12 skill levels, and special bonuses are in the JSONs. Lead
heroes both battles: attacker Elif/Dominic/Vulcanus, defender Elif/Dominic/Cara.

---

## 4. Definition of DONE (all must hold)

1. New turn-by-turn engine exists, plugged in behind the unchanged `predict()`
   facade (`wos_sim/predictor/api.py`). Non-mutating + CRN rules preserved
   (see `ENGINE_INTERFACE.md`).
2. `result.skill_telemetry` populated in the shape of `ENGINE_INTERFACE.md` §8, for
   captains, joiners, and troop skills, both sides.
3. **Kill conservation holds every turn:** Σ(per-source kills) == total casualties
   that turn, exactly (float tolerance 1e-6 relative). No phantom kills, no
   unattributed kills. (Enforced by tests + QA.)
4. All tests in `02_TDD_TESTS.md` pass.
5. QA agent (`03_QA_CALIBRATION.md`) reports PASS on both anchors within the stated
   tolerances, AND confirms the honesty gates (near-even is flagged high-variance;
   `engine_meta` does not overstate confidence).
6. `wos_sim/regression.py` extended with the new checks and green.

## 5. Non-negotiables / honesty rules (project standing policy)

- **Never fabricate precision.** If a single parameter set cannot hit both anchors,
  surface it (QA fails, `engine_meta.calibrated=False`) — do not tune one battle and
  hide the other.
- **Near-even is genuinely chaotic.** A ~1.4% effective-strength shift flips
  win↔total-wipe (measured). The engine must EXPRESS this: the stochastic batch
  should show the variance, and `engine_meta` must carry a near-even
  "high variance / coin-flip" confidence flag rather than a false point survivor %.
- **Kills drive the result.** Procs must change who wins and who survives, not just
  decorate the UI. A build where telemetry is computed separately from casualties is
  WRONG even if the numbers look plausible.
- Reuse the existing damage formula (`GAME_RULES.md` §6 / `pvp_engine._side_damage`).
  The rebuild is about *structure and sequencing*, not a new damage kernel.
