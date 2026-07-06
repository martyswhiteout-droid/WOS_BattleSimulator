# ROADMAP - Finalize the engine + build the web app (2026-07-04)

Synthesis of a 3-agent scoping pass (engine architect / app lead / data
strategist). Supersedes the earlier over-pessimistic "PvP needs a big
data campaign" framing - see the correction in section 1.

## 0. The important correction (adversarial finding)

Last turn I diagnosed the PvP failure as "the damage kernel doesn't
transfer from beast-scale (~20 health) to PvP-scale (~900 health)." The
data-strategy agent challenged this and is very likely RIGHT that it's a
MISDIAGNOSIS:

- The kernel is a RATIO form (A*L)/(D^qd * H^qh). Ratios are magnitude-
  invariant by construction - if D and H both scale with tier, absolute
  health cancels. So "magnitude doesn't transfer" is probably wrong.
- The ACTUAL bug: pvp_engine.py replaced the beast engine's ASYMMETRIC
  incoming term (kb * N_own^ed * beastpress * ... - a frontage-limited
  return-fire) with a SYMMETRIC COPY of the own-output term + a scalar
  atk_adv. That symmetric defender term over-powers the fortress wall ->
  the exact defender-win bias we see.
- I even NAMED the right fix in STATUS ("attacker-linear / defender-
  frontage-limited") but then implemented a scalar atk_adv instead of the
  frontage structure. So the proper structural fix was never tried.
- Also: phase3_backtest.py scores only winner + 2 incap totals. The 8
  reports carry per-class kill SPLITS and proc-derived TURN CLOCKS
  (r1 ~28-29t, r3 ~18-20t, r7 ~40+t) = ~30-50 constraints being thrown
  away. On this project "the kernel fails" has twice meant "the fit was
  under-optimized" (round 4: loss 20->2 from a better optimizer alone).

=> PvP is likely NOT data-blocked. The first moves are FREE (no new data).

## 1. Engine track (critical path = PvP)

Order matters. Do the free/structural steps BEFORE concluding data is needed.

| # | Task | Coding vs Data | Difficulty |
|---|------|----------------|------------|
| E-0 | Env: pin numpy/scipy/openpyxl + requirements.txt (fit + report-load path) | coding | low |
| E-1 | **Score harness on the data already in hand**: add per-class splits + proc turn-clocks to pvp_backtest so the fit is constrained by ~30-50 observables, not ~18 | coding | low |
| E-2 | **Structural PvP fix**: give the DEFENDER return-fire the beast's frontage-limited form (~N_att^ed), keep the round-4 OWN-OUTPUT term identical for both sides (it's a property of the firing troops). ed=0.483 + per-class k transfer unchanged. Re-fit only `rate` on r6/r8 scored with E-1 constraints | coding (STRUCTURAL) | high |
| E-3 | Non-dimensionalize: normalize A/D/L/H by T11-FC10 baseline so exponents are provably scale-invariant (insurance vs any residual magnitude sensitivity) | coding | low |
| E-4 | **Small controlled PvP campaign - ONLY IF E-1..E-3 don't flip the bias + reproduce r6/r8 within ~15%** (see section 3) | DATA (Martin) | - |
| E-5 | Proc scheduler (stochastic layer): seeded Bernoulli procs w/ TriggerUnit cadence; reproduces the EV path in the mean + ~13-16% run variance. THE Monte-Carlo substrate | coding | high |
| E-6 | Batched/vectorized MC core: 100K runs as a numpy axis (<30s); CRN + antithetic variates | coding | medium |
| E-7 | T12 skills in-engine: 3 battle-start 5-turn windows + Starfire ramp + top-8/level-24 clamp (needs E-5 turn clock) | coding | medium |
| E-8 | Close v0 gaps that bite in PvP: within-turn retarget, class-targeted troop skills (Charge/Bands/Master Brawler + Bradley S2 Lancer part), Crystal Shield 36-offset, Normal/Skills channel split | coding | medium |
| E-9 | Joiner stat-skill STACKING form (Prod vs Sum) - test 4x-Jessie on r3/r7 under the calibrated engine | coding + maybe data | medium |
| E-10 | Full-corpus regression harness (~150 battles): deterministic +-1, stochastic 1000-seed envelopes. The trust GATE against silent regressions | coding | medium |
| E-11 | Severe/light bookkeeping + power-swing outputs (by structure type) | coding | low |

Critical blocker = E-2 (the structural return-fire fix). Everything after
E-5 is tractable engineering gated on E-2 being right.

## 2. App track (BRD) - can start NOW, in parallel

The app codes against a thin facade `wos_sim/api.py`, NEVER the engines
directly, so finalizing the engine is a drop-in behind the seam.

Interface contract (from the app agent):
- `build_construct(own_profile, enemy_profile, context) -> Construct`
  (reuses assemble_battle/ModifierBoard/mechanics/standard_pool - STABLE today)
- `predict(construct, n=100_000, *, seed, convergence) -> PredictResult`
  (p_win/loss/mutual each w/ MC std-error; own/enemy incap Distributions;
  power_swing; per_class splits; proc_contributions; engine_model_error
  SEPARATE from MC se; sample_trace; engine_id/params_hash/seed)
- `optimize(enemy_profile, own_base, *, objective, joiner_pool,
  formation_lib, budget, seed, robust) -> OptimizeResult`
  (objective in {WIN, ECON, SUICIDE, CAPPED_WIN, BLEND}; enumerate
  C(pool,4)x|formations| under CRN + successive-halving; significance gate)
- Kernel swap contract: predict/optimize call ONE kernel object exposing
  step_batch(state, rng) + a proc hook. Current deterministic
  pvp_engine.simulate_pvp wraps as an n=1 EV kernel; swapping in the
  batched stochastic kernel changes nothing above api.py.

PARALLELIZABLE NOW (behind the stub kernel - only the NUMBERS are provisional):
1. Profile schema + validators + save/load/list/duplicate (BRD S.9; AC1 round-trip)
2. build_construct() + profile->ReportSide adapter feeding assemble_battle verbatim
3. api.py facade (signatures, Objective fns, CRN/seed plumbing, result dataclasses)
4. Local web app UI (FastAPI/Flask + JS): profile builder, run panels,
   histograms/P(win)/casualty bands/G1 ranked table - codes only vs api.py JSON
5. Optimizer orchestration (racing, CRN significance, analytic joiner pre-screen)
6. Explainability: dump resolved ModifierBoard stat layers + one sample trace

BLOCKED until engine finalized (BRD D1): the ACCURACY of any number. The
app renders a model-error caveat and treats outputs as provisional until
the engine passes the E-10 regression gate. OCR ingestion (M10) is a
Phase-D fast-follow (needs no engine).

## 2b. RESULT of the E-1/E-2 de-risk (2026-07-04) - DATA IS NEEDED

Executed the structural fix (the "free, no-data" move):
- E-2 DONE: pvp_engine now gives the DEFENDER frontage-limited return fire
  (~N_def^def_ed, def_ed=0.483 from the beast) + a def_k coefficient,
  replacing the symmetric-copy + scalar atk_adv. Correct, principled, KEPT.
- Re-calibrated rate+def_k on r6/r8: clean (both correct, loss 0.12).
- BUT holdouts stayed 4/8. Diagnosis (r004): the fix did NOT flip the
  bias because the failures are NOT a return-fire-structure problem:
  (a) GENERALIZATION - r004's defender is tankier (D=1582 vs 966) and
      marks-heavier (561k vs 289k) than the r6/r8 anchor, so one def_k
      fit on one matchup over-credits it. 2 clean anchors cannot
      extrapolate to differently-shaped matchups.
  (b) ONE-SIDED DATA - r004/r005 are viewed from the DEFENDER side, so
      the winning ATTACKER (enemy, scouted) army is under-specified ->
      engine under-credits the side that actually won.
- VERDICT: confirms the data strategist. The 8 reports cannot IDENTIFY a
  generalizable PvP kernel (only r6/r8 clean, holdouts confounded/one-
  sided, all wipes = censored loser damage). E-4 controlled campaign is
  genuinely required - but SMALL (the output physics is locked; we need
  to pin the attacker/defender asymmetry def_ed/def_k independently).
- MINIMAL ASK (do first): E1 N-ladder + one NON-WIPE close fight.

## 3. IF new PvP data is needed (E-4) - a SMALL targeted campaign

Only if E-1..E-3 fail. ~15-25 rallies (not ~150) because the output
physics is already locked. Each varies ONE thing, mirroring the farm method:
- E1 N-ladder (DECISIVE, do first): same garrison, identical rally comp/
  heroes at 3-4 troop sizes (300k/600k/1.0M/1.6M). -> return-fire frontage
  exponent + time-scale; decides if atk_adv is real or a fudge; sets rate.
- E5 role/rally-size: same two players, roles swapped; or 1/2/4 joiners
  into a fixed garrison. -> isolates atk_adv + validates rally aggregation.
- E2 formation A/B: fixed power/heroes, vary attacker split (5-0-5 / 3-3-4
  / 0-5-5). -> pin + absorption + counter cm at PvP scale.
- E3 single-hero on/off: -> validates multiplicative stat-skill + joiner
  stacking at PvP scale (also extractable from the r6/r8 +12.2% swap).
- E4 defender wall hardness (FC9 vs FC10 same comp): -> directly PROVES or
  DISPROVES the magnitude claim on D^qd*H^qh.
The single most valuable observable across all: a NON-WIPE / CLOSE fight
(both sides leave survivors) - every current report is a wipe, which
CENSORS the loser's damage output.

## 4. Recommended execution

- **Two agents, one seam.** ENGINE track (E-1..E-11) stays in an engine-
  focused session. APP track (build api.py + M2/M3/M7/optimizer/UI) is a
  SEPARATE agent working against the api.py contract with a stub kernel.
  They meet only at api.py - no rework when the real kernel lands.
- **Immediate de-risking move**: E-1 + E-2 (fix harness scoring + implement
  the frontage-limited defender return-fire). No new data, ~1 session,
  and it settles whether PvP was ever really blocked. Do this FIRST.
- Martin's only likely data ask is E-4's small campaign, and only if the
  structural fix underdelivers. Frame it as "maybe 15-25 rallies," not a
  farm-scale grind.
