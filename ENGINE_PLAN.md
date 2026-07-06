# Engine v1 - Build Spec (started 2026-07-04)

Goal: per-turn battle engine reproducing the full corpus (~150 battles in
wos_sim/data/). Phase status lives in STATUS.md; confirmed laws in
GAME_RULES.md 6g-6o.

## Locked inputs (do not refit)

- Stat layer: Eff = Base x (1+panel) x (1+buffs)/(1+penalties) x
  Prod(1+skill_i). Cards inject into own-class panel rows.
- Marginal laws: Attack, Lethality, DD each linear (elasticity 1.0);
  DD == attack-skill per point; debuffs divide (both directions).
- Durations (clock-measured, no-hero equivalents):
  Tapir13/T7: N=100 -> 17.5, 300 -> 31, 1000 -> 57.5 turns
  Tapir13/T2: 300 -> ~9.5, 1000 -> ~17.5
  Musk12/T3/T4/T5/T7 @1000: 33.5 / 41.5 / 49.5 / 73.5
  Laws: T ~ N^0.515 x (own DxH)^0.8-1.0 / beast-pressure
- Total own kills ~ c x A_eff x L_eff x (N/1000)^1.525 / wall,
  c ~ 4.2-5.3 (duration cancels across tiers; +-13% drift unexplained)
- Absorption Inf->Lan->Marks; Ambusher (T7+ lancers) 20% whole-stack
  bypass to marksmen; front-only damage otherwise; overkill caps at
  front stack then next group.
- Severe/light split is post-battle bookkeeping by structure type.

## The one open mechanism (Phase 1)

Must simultaneously generate: (i) bilinear A x L with duration
cancelling across tiers, (ii) total ~ N^1.525 WITH duration scaling
N^0.515, (iii) incoming ~ N_def^0.485, (iv) protected-dealer output
scaling with side deaths/turn (~x1.8-2.1 for wall 300->1000), (v) big
output despite near-zero own deaths in whale victories (Marlinman 300
T11 wiping 14k-unit beasts) - note (iv) and (v) TENSION: pure
casualty-paced revenge fits (i,ii,iv) but fails (v); pure cadence
kernels fit (v) but fail (i)-tier-cancellation. Leading candidates:
1. two_count: kills/event = k N_att^~1 N_def^~0.5 A L/(D^q H^q), fixed
   cadence both sides (fails tier-cancellation by (DxH)^0.85 - REJECTED
   unless a compensator exists)
2. revenge: own output/turn = k x own_deaths_this_turn x N^0.5 x A L /
   wall; beast fixed-cadence two_count (fails whale victories?)
3. hybrid: output = cadence_term + revenge_term (test mixing weights)
4. exchange-rounds: turn count driven by N^0.515 rounds; per-round
   reciprocal exchanges
Verdict criteria: deterministic battles within integer rounding,
durations within proc windows (+-1.5 turns).

## Phase 1 VERDICT (2026-07-04): mechanism family = ASYMMETRIC COMBAT WIDTH

Full results: wos_sim/data/round3_results.json. Engine: farm_engine.py.
Structure that survived (rounds 1-2 eliminated all symmetric forms):
  * OWN kill rate LINEAR in own N (every unit fires at the compact beast).
  * BEAST engages own frontage SUBLINEAR ~N^ed (ed~0.485-0.55). One ed
    gives BOTH T~N^0.515 and total~N^1.515 (the pair no symmetric form
    could satisfy).
  * SELF-THROTTLE (power- or DxH-based): tankier/higher-tier troops fire
    slower per unit but live proportionally longer -> total ~ A*L within
    class, while a pure attack buff stays exactly linear (throttle stat
    unchanged). Resolves the marginal-linear vs tier-sublinear paradox.
  * PINNED FRONT: the own stack being attacked fires at fraction pin<1;
    protected back stacks fire freely -> mixed-army splits + solo-dealer
    modesty + protected-dealer explosion, all from one rule.
  * PER-CLASS k (ki,kl,km): cross-class balance at equal tier/power.
Fit quality: STRUCTURE validated, but headline accuracy over-claimed (see
QA below). NOT yet at integer-rounding bar.

## ROUND 4 - PROGRESS (2026-07-04)

- STEP 1+2 DONE: replaced coord-descent with scipy differential_evolution
  (global; no local-optimum trap) and PINNED ed=0.483 (clock) + cm=1.10
  (physical). Added marginal-linearity ANCHORS to the loss (weight 6x) so
  the confirmed Seo-yoon/buff linearity cannot be traded away.
  RESULT: loss 20.07 -> 2.13 at FULLY PHYSICAL pinned values. This
  confirms the QA finding (my coord-descent was stuck) AND validates the
  mechanism honestly (no free-knob cheat). Marginal anchors held exactly
  (x1.05->1.056, x1.10->1.118, x1.15->1.160).
- CONFIRMED REAL (not optimizer artifact): low-tier T2-T5 still overpredict
  ~30-40% (T3 74 vs 51) while T7 near-exact -> penetration floor is
  JUSTIFIED (tested-before-adding). Also: marksman-solo underpredicts ~40%,
  high-N durations run ~15% long (secondary residuals).
- STEP 3 DONE: armor-penetration term added (keyed on BASE tier attack,
  buff-independent). Final honest fit loss 1.97 (params in
  farm_engine.BEST_PARAMS; full write-up round4_results.json). BUT the
  penetration DoF did NOT resolve the low-tier residual - the global
  optimizer spent it on censored-victory + mixed gains (both now correct)
  instead. Low-tier T2-T5 overpredict persists (~30-50%) - reclassified
  as a throttle-CURVE / diagnostic-regime issue, not the hypothesized
  armor floor. KEY: residuals live in DIAGNOSTIC-ONLY regimes (solo
  low-tier, solo marksman) that never occur in real high-tier PvP; the
  model is accurate WHERE IT MATTERS (T7 ~4%, mixed dealers ~5-15%,
  marginal exact, win/loss correct).
- ROUND 4 VERDICT: mechanism VALIDATED honestly (loss ~2 at physical
  pinned values, 10x better than the stuck round-3 fit). NEXT = PvP layer
  + the 8-report back-test (the real high-tier accuracy check), NOT more
  farm-regime tuning.

## ROUND 4 - actions (from external QA 2026-07-04; details round3_results.json)

Priority order:
1. FIX THE OPTIMIZER FIRST. Coord-descent got stuck: QA probe found
   ki 0.36->0.45 drops loss 20.07 -> 4.30. Use multi-start + Nelder-Mead
   (scipy) or basin-hopping; re-weight the loss to protect the T7 anchor
   (currently a lower scalar loss can worsen T7). Re-run BEFORE trusting
   any accuracy figure - the honest fit is probably far better than 20.07.
2. PIN ed = 0.483 (clock value); fitted drifted to 0.55. If the mechanism
   holds with ed fixed at its independently-measured value, that's strong
   validation. Keep physical-prior fits SEPARATE from free-knob fits.
3. BEAST-DEFENSE PENETRATION FLOOR for the low-tier +30% overpredict, WITH
   a guard regression: effective own A vs beast D across T2-T7
   (A/D = 0.28/0.42/0.56/0.70/.../0.98 vs Musk12) so the floor cannot fix
   low tiers by damaging the T7 calibration (T7 is also sub-defense).
4. CROSS-CLASS dealer balance (solo lancer high / marksman low) - likely
   pin/duration interplay; may need class-specific pin or proper counter
   routing through the beast group structure.
5. FIX assemble.py L184 / reports.py L253: hero stat skills are separate
   MULTIPLICATIVE factors (GAME_RULES 6l), not additive-pool. PvP path.
6. within-turn retarget: recompute front stats when a beast front group
   dies mid-turn (farm_engine currently uses turn-start snapshot).
Then: lock params, add proc scheduler, full-corpus regression incl. PvP.

## Phase 2 - engine assembly (after mechanism verdict)

- Deterministic core (winner) + proc scheduler (Bernoulli: Ambusher 0.20,
  Crystal Lance 0.10/0.15, Crystal Shield offset 36 @0.25/0.375, gun
  double-damage, hero procs w/ TriggerUnit semantics from skill book)
  + per-attack-event EV alternative mode for fast PvP fitting.
- Bookkeeping: severe/light by structure (0.35 fortress / 0.30 foundry /
  0.45-0.35 territory / ~0.0025 beasts); power-loss = severe x unit power.
- Regression harness: replay all battles in wos_sim/data/*.json ->
  report per battle: kills pred/obs, duration pred/obs (when clocked),
  per-class splits, group-level losses. Deterministic: exact (+-1).
  Stochastic: 1000-seed envelopes vs observed (incl. repeat-run spreads).

## Phase 3 - PvP layer

Rally aggregation (captain 9 skills + 3 widgets context-scoped; joiners
top-4 flag S1 rally-wide, additive... NOTE: verify additive-vs-
multiplicative for STACKED joiner skills - 4x Jessie +25% DD: additive
pool (x2.0) vs multiplicative (x2.44) - r3/r7 reports may separate).
Calibrate on r6/r8 pair; blind-test r1-r5, r7. Targets: totals within
10-15%, kill-share ordering exact, skill-kill rows within proc-EV.

## Phase 4 - product

predict(army, heroes, panels, context) -> outcome distribution;
Excel bridge to WoS battle simulator.xlsx.
