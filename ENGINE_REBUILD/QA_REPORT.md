# QA Report

Date: 2026-07-06

Verdict: FAIL - not QA-certified yet.

This report reflects the build after the QA pass for mixed-skill cadence,
damage-category channels, owner-troop strike cadence, strict T12 anchor gates,
source-sign normalization, target locking, widget application, and Gen-15 hero
catalog coverage. No calibration tuning was performed in this pass.

## Fixed In This Pass

Mixed-skill cadence selection now prefers direct-damage/cadence rows instead of
blindly taking the first row in a skill group. Vulcanus Skill 2 now resolves to
every 5 own-troop strikes instead of the companion Target/Received row.

`Strikes` now means attacks made by the skill owner's troop, not every troop
receiver row affected by the skill. Turn-based skills with a frequency of 3 and
start turn 1 fire on turns 1, 4, 7, 10, 13, 16, 19, 22, 25, etc.

Ahmose Skill 1 now starts on turn 4 and repeats on turns 8, 12, 16, etc. His
Infantry skips its base attack on those trigger turns, and the Damage Taken
reduction window starts on the following turn for 2 turns.

Known stale workbook rows are normalized at load time: Cara S1, Vulcanus S3,
Flora S3, Jeronimo S3, Hector S1, Nora S3, Philly S3, Alonso S1/S2, Lynn S3,
and Wayne S2. Negative amount rows now keep negative per-proc signs.

All-class direct-damage rows now emit per receiver class instead of collapsing
to the captain troop. Specific target rows now lock packets to the requested
target class. Renee S2/S3 no longer self-trigger; they are linked to Renee S1
Dream Mark windows.

Selected hero widgets now apply as passive stat modifiers only for legacy/raw
profiles that explicitly do not include widgets in the panel. `panel_is_final`
profiles always suppress widget stat rows because the front-end Final Stats
panel has already accounted for them.

The `/api/predict` turn-engine path now builds units directly from Final Stats
and skips the legacy pre-battle hero-skill `ModifierBoard`. Captain, joiner,
troop, and T12 skills are applied only inside the turn engine during battle.
Passive hero stat-skill rows now also apply in the turn engine. This fixes a
Final Stats regression where DD/DT skills such as Nora S1 applied, but stat
skills such as Gatot S1 / Hank S1 / Cara S1 were skipped as if already folded
into the panel.

Damage modifiers are split by damage category: Normal, Skills, and Both. Skill
only Damage Taken / Damage Dealt rows no longer amplify ordinary base attacks.

Anchor scoring now reports the full live survivor composition. It no longer
passes G1 by taking the largest surviving troop class when multiple classes are
still alive.

Gen-15 heroes Hank, Estrella, and Viveca are present in the physical workbook
`Hero Stats` tab and are loaded by the engine with Attack/Defense 19.6156 and
Lethality/Health 4.9. Their `Hero Profile` and `Hero Skills` workbook rows are
still absent, so the loader supplemental catalog remains the active runtime
source for those profile/skill rows. All three Gen-15 heroes pass the live
source-audit token check.

## Locked Parameters

Current turn-engine defaults remain:

| Parameter | Value |
|---|---:|
| rate | 168.0 |
| def_k | 1000.0 |
| def_ed | 0.483 |
| K_skill | 1.0 |
| ambush_proc | 0.20 |
| ambush_frac | 1.0 |
| cara_burst | 1.0 |

## Anchor Scores

Scored directly from `wos_sim/data/pvp_t12_report_001.json` and
`wos_sim/data/pvp_t12_report_002.json`.

| Anchor | Predicted | Expected | Gate Status |
|---|---|---|---|
| report 001 | A wins, 5 turns, mixed survivors: Inf 560,650 / Lan 301,938 / Marks 563,130, total 1,425,719 | A wins, 16 turns, only Marksman survivors, 62,364 | G1/G2/G3 FAIL |
| report 002 | A wins, 17 turns, mixed survivors: Inf 270,069 / Lan 459,133 / Marks 357,991, total 1,087,192 | A wins, 25 turns, only Lancer survivors, 118,068 | G1/G2/G3 FAIL |

G4 remains failed because one shared calibrated parameter set has not yet been
fitted. G5/G7 are now represented by strict anchor tests, but those tests are
marked expected-failure until calibration and remaining source mismatches are
resolved.

## Structural Gates

G6 conservation: PASS in the regression harness and focused packet tests.

G8 honesty: PASS for current engine metadata policy. Turn-engine predictions
remain uncalibrated and should not be reported as certified.

G10 hero source alignment: FAIL. The live wiki audit completed with 145 checks
and 19 non-ok rows. See `ENGINE_REBUILD/SKILL_SOURCE_AUDIT.md`.

G11 troop rule alignment: PARTIAL. Structural tests cover Crystal Lance no-proc
behavior, Ambusher proc suppression/forcing, Volley extra attack behavior,
troop-skill catalog coverage, and T12 catalog token coverage. Full independent
rules sign-off remains pending.

## Verification Commands

| Command | Result |
|---|---|
| `py -m pytest wos_sim\predictor\tests\test_pvp_turn_engine.py -q -p no:cacheprovider` | 29 passed, 2 expected failures, 9 subtests passed |
| `py -m pytest wos_sim\predictor\tests -q -p no:cacheprovider` | 72 passed, 8 skipped, 2 expected failures, 9 subtests passed |
| `py -m wos_sim.regression` | ALL GREEN |
| `py -m wos_sim.skill_source_audit --live --output ENGINE_REBUILD\SKILL_SOURCE_AUDIT.md` | FAIL: 145 checks, 19 non-ok |

## Remaining Work

1. Resolve or document the 19 live source-audit mismatches.
2. Persist Hank, Estrella, and Viveca into the physical `Hero Profile` and
   `Hero Skills` workbook tabs without relying on supplemental loader rows.
3. Calibrate one shared `TURN_PARAMS` set against both T12 anchors.
4. Re-run G1-G11 and update this report to PASS or CONDITIONAL only if the gate
   evidence supports it.
