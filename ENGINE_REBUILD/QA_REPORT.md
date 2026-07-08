# QA Report

Date: 2026-07-08, second pass (supersedes both earlier reports below)

Verdict: **CONDITIONAL** - certified for WINNER/ranking on all FOUR real
anchors (the product-critical property); NOT certified for near-even survivor
depth (declared trade-off, labeled coin_flip in engine_meta) or for anchor-2
survivor type.

## 2026-07-08 SECOND Calibration Pass - anchor 4 (Amanda vs RampageR)

Martin's retest surfaced a fourth real battle the engine inverted: solo attack
vs a 69%-marksman garrison+support (real: attacker wins 58.3% survivors,
defenders wiped, ~16 turns; engine before this pass: attacker wiped,
p_win=0.000). Ingested as `wos_sim/data/pvp_t12_report_004.json` + anchor A4
in `wos_sim.anchor_eval` (input: `Scenarios/Calibration_Amanda_Ramp.json`).

**New ground truth exploited:** the report's per-skill KILL columns (both
sides) are the first direct skill-packet magnitude oracle. Real
skill-attributed kills are ~7% of casualties; the engine at K_skill=1.0
produced 38-50% (defender Ligeia: 99k engine kills vs 8,573 real, ~12x).
`K_skill=0.15` is now locked and A4 carries a `skill_kill_share < 20%` gate.

**Structural additions:** optional normalized compressions `q_off`/`q_def` on
the offense/defense stat products in `base_strike_damage` (defaults 1.0 =
legacy; general path unaffected). `q_def=0.7` locked - the beast-fitted
H^1.45 over-rewards health-stacked panels: A4's defender stacked +15%
Def/Leth/Health widgets (+36% leth/health vs the attacker) and still lost
decisively.

**Root-cause decomposition of the A4 inversion** (turn-1 per-stack factors):
their marksman out-punched her infantry ~5x per-capita via (a) class base
stats (marks base atk 30 vs inf 19, entering linearly), (b) the `pc` soft-cap
term (1.74x their favor, also base_atk-driven), (c) H^1.45 on health-stacked
panels. Note the beast-fitted ki/km ratio (2.23) almost exactly cancels the
marks/inf base-offense ratio (2.37) - the class weights are sound; `pc` and
`qh` were the distorting shapes.

**The declared trade-off (why near-even survivors got shallower):** no swept
parameter set satisfies near-even DEPTH (A1/A2 real: 3.45%/6.54% survivors)
and the decisive solo WINNERS (A3/A4) simultaneously. `def_k=1.0` (parity)
reproduces the deep grinds but inverts BOTH solo anchors; `def_k=0.5` ranks
all four correctly with shallow near-even depth (~65-73% predicted survivors
on A1/A2). Winner correctness wins: a wrong winner destroys user trust, an
uncertain magnitude can be labeled. Swept alternatives that FAILED to thread
all four: pc=0 (+rate rescale), km reduction (breaks A2, whose attacker is
marks-reliant), size-dependent def_ed>1 (breaks on A3-vs-A4: same scale,
opposite needs).

**Open mechanic (the A2-vs-A4 tension):** marks-heavy DEFENDERS underperform
their stats (A4) while a marks-reliant ATTACKER still ground out a deep
near-even win (A2). No shared scalar separates them; the missing physics is
most likely the discrete bypass-redistribution family already flagged (A2's
real dynamics were marks-annihilation-by-procs), plus possibly a
wall-integrity effect. Disambiguating data wanted: any battle where a
marksman-heavy side WINS, any attacker-LOSES report, or per-turn casualties.

**Honesty detector re-based:** the +-2% winner-flip probe dies in the
def_k=0.5 regime (nothing flips at +-5%). `_near_even_probe` now OR-s a
STATIC strength-symmetry test (aggregate n x (offense x toughness)^0.25
within +-10%) with the dynamic probe. A1/A2/A4 flag near_even/coin_flip (A4
was genuinely stat-close - she won on comp geometry); A3 reads directional.
The near-even note states the observed real range: battles this close ended
anywhere from 3% to 58% survivors on the winning side.

**Locked TURN_PARAMS (2026-07-08 second pass):** rate=155, def_k=0.5,
def_ed=1.0, fire_mode="start", mod_gamma=0.38, stat_floor=0.4, K_skill=0.15,
q_def=0.7 (q_off=1.0, pc/pin/km legacy).

**Scorecard (seed 0):** A1 A/15t (turns PASS, survivors FAIL high), A2 A/20t
(survivors FAIL high), A3 A/18t (turns PASS, survivors FAIL high at 75%),
A4 A/24t (survivors PASS 46% vs real 58%, turns FAIL +6). 20/36 gates; ALL
FOUR WINNERS PASS end-to-end via api.predict (p_win 1.00/1.00/0.997/1.00);
regression #12 guards all four winners.

---

# Superseded: first 2026-07-08 pass (three-anchor calibration)

Verdict then: CONDITIONAL - certified for winner/ranking + magnitude bands on
the three T12 anchors; NOT certified for survivor-type on anchor 2 or for
point survivor counts near even.

## 2026-07-08 Calibration Pass (Claude)

Structural fixes, in causal order (all verified against per-turn traces):

1. **Additive debuff stacking abolished.** Hero stat rows (captain + joiner,
   timed included) now compose MULTIPLICATIVELY, with a floor
   (`stat_floor=0.4`) on the composed multiplier. Before: -25%/-25%/-60% kits
   stacked additively to -97.8% defense and blew damage up through `def^qd`
   (anchor 1 ended in a 2-turn blowout with 1.49M auto kills on turn 2).
2. **Wounded-keep-fighting fire mode** (`fire_mode="start"`): a stack fires at
   its STARTING strength until it breaks. All three anchors show
   constant-in-time absolute casualty rates (A1 defender ~117k/turn at 1.87M
   live AND ~130k/turn in the endgame at 348k live) - not Lanchester taper.
   This is what makes deep near-mutual annihilation reproducible.
3. **Defender scale re-based to per-capita parity** (`def_k=1.0, def_ed=1.0`).
   The inherited general-engine pair (1000/0.483) made small garrisons fire at
   1.74x the attacker scale and rally-size ones at 0.57x, which inverted the
   decisive solo anchor (A3) while leaving near-even rallies shallow.
4. **Diminishing returns on stacked modifiers** (`mod_gamma=0.30`): raw
   multiplicative kits predicted a 3-4x exchange edge; the anchors show
   ~0.9-1.1x real. Compression exponent applied to all composed stat/dd/dt
   modifiers.
5. **Integration fix:** `kernel.run_batch`/`engine_meta` no longer leak the
   GENERAL engine's `DEFAULT_PVP_PARAMS` (rate/def_k/def_ed) into the turn
   engine's parameter layering (this silently overrode TURN_PARAMS on the API
   path and inverted near-parity matchups end-to-end).
6. **Honesty labels:** `engine_meta` now runs a +-2% defender-strength probe;
   if the winner flips, the matchup is labeled `confidence="coin_flip"` /
   `near_even=true` and the note says to trust the win probability, never a
   point survivor count. Decisive matchups are labeled `directional`.
   Verified: A1 flips (matches reality - it was won by 3.45%), A3 does not.
7. The API server default is now the turn engine (`engine="turn"`), since it
   outperforms the general path on every anchor and emits skill telemetry.

Fit log: coarse+refine grids in `wos_sim/fit_turn_params.py` (deterministic,
seed 0, replayable); scorecards from `wos_sim/anchor_eval.py`. Gate total went
5/27 -> 17/27, with all winner/magnitude-critical gates green.

## Locked Parameters (2026-07-08)

| Parameter | Value | Meaning |
|---|---:|---|
| rate | 168.0 | global damage scale (duration knob) |
| def_k | 1.0 | garrison per-capita parity |
| def_ed | 1.0 | no frontage exponent on live count |
| fire_mode | "start" | stacks fire at starting strength until broken |
| mod_gamma | 0.30 | diminishing returns on stacked skill modifiers |
| stat_floor | 0.4 | floor on composed per-stat multiplier |
| K_skill | 1.0 | skill-packet scale (unchanged) |
| ambush_proc | 0.20 | ambusher proc chance (unchanged) |
| ambush_frac | 1.0 | ambusher magnitude (unchanged) |
| cara_burst | 1.0 | backline-burst magnitude (unchanged) |

## Anchor Scores (2026-07-08, deterministic seed 0)

| Anchor | Predicted | Real | Verdict |
|---|---|---|---|
| A1 report_001 (rally, near-even) | A wins, 18t, MARKSMAN survive, 79,293 | A wins, 16t, MARKSMAN survive, 62,364 | winner/type/survivors PASS; turns +1 over gate; triggers: att Elif 11 (12+-1 PASS), Cara 7 (6+-1 PASS), Vulcanus SK2 7 (exact), SK3 6 (exact); def Elif 10 vs 15 FAIL |
| A2 report_002 (rally, near-even) | A wins, 23t, 61,184 survivors | A wins, 25t, LANCER survive, 118,068 | winner/turns/survivor-count PASS; survivor TYPE = marksman FAIL (real: lancers) |
| A3 Amanda/Omar (solo, decisive) | A wins (p=0.997), 15t, 51.3% survivors, wall holds (lancer loss 0%, inf survives 6.4%) | A wins, 19-20t, 34.3%, lancer loss 0%, inf survivors 1.8% | winner/wall-structure/def-wiped PASS; turns -2 under gate; marks_loss 7.8% vs 66% FAIL (bypass too weak) |

End-to-end via `api.predict` (the UI path): A1 p_win=0.48 labeled coin_flip
(real: won by 3.45% - a coin flip that landed), A2 p_win=0.995, A3 p_win=0.997
labeled directional.

## The honest residual (why CONDITIONAL, not PASS)

One family of gaps remains: **discrete backline-bypass procs are too weak and
purely scalar.** Reality's A2 lancer-survival and A3 66% marksman bleed both
require the defender's Ambusher/backline skills to REDISTRIBUTE damage onto
the enemy backline in discrete procs. Scalar amplification (`ambush_frac` etc.)
was swept and REJECTED: it tips the near-even knife-edge into defender wins
before it produces the right class mix. This needs redistribution mechanics
(bypass share carved out of front damage, per-proc), not bigger knobs - see
`06_NEXT_FIXES.md` P2 notes. Near-even fragility itself is REAL (verified: a
+-2% strength shift flips A1's winner, exactly like the two real battles),
so point survivor counts near even are unknowable in principle; the engine now
says so instead of pretending.

## G10 audit note (anchor kits)

Of the 18 live-audit mismatches, the ONLY anchor-kit row is **Vulcanus
skill_3** - the wiki text omits the "every 3 turns" cadence. Martin's real
trigger counts CONFIRM the workbook cadence empirically (6 triggers at 16
turns, 9 at 25: exactly every-3-turns). Documented exception, not a defect.
Blanchette's flagged rows are skill_2/3, which joiners never contribute.

---

# Superseded: QA Report of 2026-07-07 (FAIL)

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
Flora S3, Jeronimo S3, Hector S1/S3, Nora S3, Philly S3, Alonso S1/S2,
Lynn S1/S3, Rufus S2, Mia S1, Dominic S2, and Wayne S2. Negative amount rows
now keep negative per-proc signs.

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
Static passive hero stat skills now compose multiplicatively, matching the
legacy `ModifierBoard.skillmult` rule. Chance-based modifier proc sources are
now separated from effect receivers: explicit all-troop attack / all-troop
chance source text rolls independently per live attacking troop class, while
generic all-troop receiver effects such as Gisela S2/S3, Hector S1, Philly S3,
and Molly S1 fire once from the captain/global source. Raw widget rows are
filtered by Rally/Garrison context.

Same-source duration effects now refresh instead of self-stacking, except for
explicitly stackable Lynn S3. DD/DT multipliers are floored at zero effective
damage so overlapping debuffs cannot produce negative damage. Lynn S1 is now a
shared one-turn Damage Dealt buff instead of instant skill packets. Hector S3 is
now a discrete 25% damage proc instead of a passive EV-folded DD bonus.

Next-attack Damage Taken rows now have a packet path: paired rows such as Gwen
S2 fold into the direct packet for the struck target class, and DT-only rows
such as Blanchette S3 emit class-targeted skill packets. Target-text rows for
Rufus S2, Mia S1, and Dominic S2 now use `EffectReceiver.Target` instead of a
fixed enemy class.

Final/scouted panels now suppress own-side permanent hero stat multipliers in
both the legacy/general construct path and the turn-engine passive stat layer.
Those panels already contain the side's own pre-battle stat skills; enemy
debuffs and DD/DT battle effects still apply. This fixes the Amanda/Omar
solo-anchor ranking bug in the default path: the general engine no longer
inverts the decisive attacker win. The local API no longer forces the
uncalibrated turn engine by default; callers can still request it explicitly via
`params={"engine": "turn"}`.

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
| report 001 | A wins, 2 turns, mixed survivors: Inf 675,953 / Lan 317,235 / Marks 635,605, total 1,628,793 | A wins, 16 turns, only Marksman survivors, 62,364 | G1/G2/G3 FAIL |
| report 002 | A wins, 32 turns, mixed survivors: Lan 54,922 / Marks 236,084, total 291,006 | A wins, 25 turns, only Lancer survivors, 118,068 | G1/G2/G3 FAIL |

G4 remains failed because one shared calibrated parameter set has not yet been
fitted. G5/G7 are represented by strict anchor tests, but those tests are
marked expected-failure and the green unit-test count must not be read as
anchor acceptance until those expected failures are removed.

## Structural Gates

G6 conservation: PASS in the regression harness and focused packet tests.

G8 honesty: PASS for current engine metadata policy. Turn-engine predictions
remain uncalibrated and should not be reported as certified.

G10 hero source alignment: FAIL. The live wiki audit completed with 145 checks
and 18 non-ok rows. See `ENGINE_REBUILD/SKILL_SOURCE_AUDIT.md`.

G11 troop rule alignment: PARTIAL. Structural tests cover Crystal Lance no-proc
behavior, Ambusher proc suppression/forcing, Volley extra attack behavior,
troop-skill catalog coverage, and T12 catalog token coverage. Full independent
rules sign-off remains pending.

## Verification Commands

| Command | Result |
|---|---|
| `py -m pytest wos_sim\predictor\tests\test_pvp_turn_engine.py -q -p no:cacheprovider` | 40 passed, 2 expected failures, 20 subtests passed |
| `py -m pytest wos_sim\predictor\tests -q -p no:cacheprovider` | 86 passed, 8 skipped, 2 expected failures, 20 subtests passed |
| `py -m wos_sim.regression` | ALL GREEN |
| `py -m wos_sim.farm_engine` | PASS: quick BEST_PARAMS check, loss=1.97335 |
| `py -m wos_sim.skill_source_audit --live --output ENGINE_REBUILD\SKILL_SOURCE_AUDIT.md` | FAIL: 145 checks, 18 non-ok |

## Remaining Work

1. Resolve or document the 18 live source-audit mismatches.
2. Persist Hank, Estrella, and Viveca into the physical `Hero Profile` and
   `Hero Skills` workbook tabs without relying on supplemental loader rows.
3. Rebuild Hector S2's 10-attack / 85% decay mechanic as a discrete runtime
   effect; it remains represented by stale workbook EV rows.
4. Calibrate one shared `TURN_PARAMS` set against all three anchors, including
   `pvp_t12_report_003.json` / `Scenarios\Calibration_Amanda_Omar.json`.
5. Re-enable the turn engine as the default API path only after the strict
   anchor gates pass.
6. Re-run G1-G11 and update this report to PASS or CONDITIONAL only if the gate
   evidence supports it.
