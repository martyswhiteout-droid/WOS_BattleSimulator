# Project Status / Session Handoff (updated 2026-07-02, evening)

Read GAME_RULES.md FIRST - it is the source of truth for all confirmed
mechanics, discoveries, fit results, and open questions. This file is the
working-state snapshot so a fresh session can resume without loss.

## Assets

- `WoS battle simulator.xlsx` - Martin's workbook (KEEP OPEN in Excel; edit
  via COM GetActiveObject, never openpyxl round-trip).
- `wos_sim/` package: models.py (typed data model incl. skills/TriggerUnit),
  loader.py (xlsx -> models; avatar extraction), mechanics.py (activation
  rules + battle constants), troop_catalog.py (wostools troop stats T10/T11
  FC0-10 + troop skills w/ raw proc params), battle.py (v0 hypothesis engine,
  static-EV; v1 per-turn engine is the NEXT BUILD), assemble.py (report ->
  engine bridge; EV computation from raw fields), reports.py (battle report
  data model + validation), fit_kernel.py (static aggregate fit),
  reconcile_troop_skills.py, fit_report.py, demo.py.
- `wos_sim/data/reports/report_00[1-8].json` - 8 fully validated PvP reports
  (all identities exact; flags/captains all confirmed by Martin).
- `wos_sim/data/beast_hunts.json` - 11 controlled beast experiments (Marty,
  BattleReportData.pdf p5-16) + attacker passive stat bonuses recorded there.
- `wos_sim/data/avatars/` - 51 hero avatar reference images + manifest.
- `wos_sim/data/beast_hunts_marlinman.json` - INGESTED (25 pages): the
  five wishlist experiments complete. HEADLINES: engine is STOCHASTIC
  (RNG in proc rolls, ~13% casualty variance across 5 identical runs);
  beast mitigation ladder Lv5-30 (+1.8%..+455%); N-ladder 10..3000;
  solo N=1 all three classes; first-strike single-event damage (100 inf
  kill 195/958 in one attack); attack-sequence confirmed via kill
  distribution; Marty-vs-Marlinman same-fight stat pair (win vs defeat);
  wall-ratio curve 600 lancers + 0..800 inf.

## Current fit state (static kernel, 8 reports)

e=0.525, k_Inf~0.5-0.6, k_Lancer=1.5 (k_Marks=1), lethality weight b=1.
Systematic residual = time-integration/erosion dynamics -> v1 per-turn
engine is the decisive next build, calibrated on beast hunts first
(cleanest), then the r6/r8 sister pair, then all reports.

## Key analysis conventions

- "Kills" columns everywhere = the SEVERE bucket only (35% of incapacitated
  in fortress/city PvP, 30% Foundry, ~0.2-1% beasts, 45%/35% territory).
  Incapacitated = losses+injured+lightly; units leave battle immediately.
- Turn-count inference: proc counts of known-cadence skills (e.g. every-4-
  turns x N procs); Crystal Shield procs / 0.375 ~ attacks received;
  Crystal Lance procs / 0.15 ~ lancer attack events.
- Beast armies = tiered unit groups (levels like troop tiers) + flat %
  bonus (L13 +18.5%, L18 +57%, L25 +257%, L30 +455%); same engine, same
  troop skills. TEST PENDING: beast unit base stats == troop tier tables?
- Account passive stats are read off each report's Stat Bonuses panel -
  experiments on ANY account are valid because panels self-document stats.
  Marlinman's maxed SKILLS make his hero tests valid too; his lower widget
  LEVELS simply show smaller widget % in the specials panel (self-
  documenting). No like-for-like Marty re-runs needed.

## Immediate next steps

1. DONE: beast-stats==tier-tables VERIFIED (power inversion; see
   GAME_RULES 6f). calibrate.py harness built (power check, first-strike
   equations, ladder tables). T12 provisioned (GAME_RULES 6e;
   troop_base_stats(12,...) live; T12 battle skills documented for the
   engine: battle-start shields, Indomitable Wall 8-member activation).
2. DONE 2026-07-03 am: calibration set 2 + Polar Terror INGESTED
   (beast_hunts_marlinman2.json, polar_terror_rally.json; GAME_RULES 6g).
   Buff algebra SOLVED exact; hero panel injection measured; attack
   elasticity ~2; marksman-wall 3.1x; absorption confirmed receiving-side;
   T12 skill texts confirmed; Polar Terror = separate bonus ladder.
2b. DONE 2026-07-03 midday: enemy-penalty A/B + Bradley ladder INGESTED
   (enemy_penalty_ab.json, bradley_skill_ladder.json; GAME_RULES 6h).
   COMPLETE stat formula: x(1+perm)x(1+Σbuffs)/(1+Σenemy penalties) -
   penalties DIVIDE (exact, RMS 0.03). Card injection proven by document.
   Bradley skill tooltips captured (S1 5%/lv Atk; S2 DD 6%L/5%I per lv;
   S3 DD 6%/lv pulsed 2-of-4). Code updated to divisor form
   (reports.standard_pool, assemble). Single-run skill-level deltas are
   below RNG noise -> ask repeats-before-upgrade design going forward.
2c. DONE 2026-07-03 midday: Far Seer pure-infantry ladder INGESTED
   (farseer_infantry_ladder.json; GAME_RULES 6i). HEADLINES: engine
   DETERMINISTIC without proc skills (3 identical runs -> identical to
   the unit); e=0.525 cross-validated from N-ladder (matches the PvP
   static fit exactly); tier ladder T1/T2/T7 = 11/26/252 at N=1000
   constrains kernel shape (plain A*L-linear overpredicts ~4x).
   Seo-yoon S1 ladder incoming (Attack stats-based; deterministic ->
   ONE run per skill level suffices on this farm).
2d. DONE 2026-07-03 pm: Far Seer set 3 INGESTED via parallel extraction
   workflow, all battles power-identity verified (farseer_set3.json;
   GAME_RULES 6j). LOCKED: attack elasticity 1.0 exact; attack skill ==
   DD skill per point (257==257); e=0.525 third derivation; determinism
   for 3-class armies; Seo-yoon Rallying Beat +5%/lv, Jassier Tactical
   Genius +10% DD tooltips. Multiplicative power-law kernel REJECTED by
   the deterministic data; subtractive/floor families are lead
   candidates (sweep in farm_fit.py - power/sub_floor/sub_floor_LD/
   saturate/two_stage families implemented).
3. NEXT: finish the kernel structure search on the deterministic farm
   points. Sweep status: full set - sub_floor best at loss 2.0 (~30%
   err, NOT solved); pure-infantry subset - loss 0.11 (~8% err) but
   only with unphysical exponents (negative qd/qh). None of five
   families (power/sub_floor/sub_floor_LD/saturate/two_stage) is the
   true form. Next structure ideas: integer/accumulator quantization,
   per-class k, spillover rules, separate beast-side kernel, event
   scheduling variants, damage split channels. Then v1 per-turn engine
   (deterministic core + proc scheduler), stochastic sets as EV ->
   r6/r8 -> all 8 PvP. NOTE: Ambusher is a T7+ lancer skill (wostools,
   confirmed) - explains determinism with T6 lancers; T4/T6 lancer
   catalog rows verified against wostools.
2e. DONE 2026-07-03 pm: set 4 INGESTED (farseer_set4.json; GAME_RULES
   6k). Tier ladder T1-T5+T7 = 11/26/51/87/125/252; single-class T6
   lancer 185 / marksman 202; beast ladder Lv10 (VICTORY, own 563/1000
   incap - first uncensored own-casualty point) /Lv12/Lv13/Lv15
   = wipe/252/177/83; Seo-yoon = MARKSMAN hero (card injection seen on
   Marlinman panel); Rallying Beat L5 = +25%. Marlinman discriminator
   censored (full wipes) - needs defeat configs.
3b. DONE - see 2f (multiplicative confirmed).
2f. DONE 2026-07-03 eve: set 5 INGESTED (farseer_set5.json; GAME_RULES
   6l). CLOSED: stat skills MULTIPLICATIVE (x1.2506 vs additive x1.026).
   Turn clocks cross-validate (Bradley S3 x4, Renee S1 x2 odd turns):
   Tapir vs 300 T7 = 31 turns, vs 1000 = 57-58 -> duration ~N^0.58 =>
   defender count enters kernel (~N^0.42); per-event attacker exponent
   ~0.95 (N-ladder 1.525 = per-event ~N^1 x duration ~N^0.53; old
   "e=0.525 per event" CORRECTED). T6 triple 174/185/202. Single-lancer
   probe: 1 lancer 0.45 vs 0.94 kills/turn with 300 vs 1000 wall ->
   side-level coupling. Bradley vs beast = S1 x1.15 x S3-EV 1.046, S2
   class-targeted DD did NOT act vs beast. FC procs account-gated.
   KERNEL STILL OPEN: duration-constrained sweep (ed dial) best
   sub_floor loss 4.48 - solo lancer/marks overpredicted ~2x, durations
   missed (pred 24/80 vs obs 31/57.5). Needed next: side-level N
   pooling forms (single-lancer probe demands it), a,b two-count
   exponents (a~0.95, b~0.42 analytic), saturating stat opposition.
2g. DONE 2026-07-03 night: set 6 INGESTED (farseer_set6.json; GAME_RULES
   6m). All three requested battles + Lloyd bonus. LETHALITY LINEAR
   (panel A/B via Far Seer leth 10->20 change); enemy-leth debuff ->
   survival ~linear (Lloyd); T2 durations 9.5/17.5 -> survival = own
   DxH product ~linear; dual clocks agree; GRAND COMPOSITION CHECK
   exact (246 = 177 x leth x Bradley x duration). Baselines reconciled
   across beasts (Musk->Tapir x0.70) and panels.
2h. DONE 2026-07-03 late: set 7 INGESTED (farseer_set7.json; GAME_RULES
   6n). Duration prediction PASSED (72-75 vs predicted 75-84);
   multiplier stack validated x4 more; T ~ N^0.515 locked (100..1000);
   T ~ (own DxH)^0.8-1.0 across tiers; EMERGING: total kills ~
   c x A x L x (N/1000)^1.5 with duration cancelling (c ~ 4.2-5.3) -
   mechanism still open (protected-lancer runs contradict pure
   retaliation).
3c. NEXT SESSION = ENGINE CONSTRUCTION (plan given to Martin):
   Phase 1 mechanism search on deterministic data (candidates:
   N_def-kernels, retaliation-paced, side pooling, engagement width,
   lifetime budget) - must reproduce ALL laws within rounding.
   Phase 2 engine v1 = deterministic core + proc scheduler + severe/
   light bookkeeping; regression harness over ~140 stored battles.
   Phase 3 PvP layer (rally aggregation done) calibrated on r6/r8,
   blind-tested on r1-r5,r7. Phase 4 predictor + Excel bridge.
2i. DONE 2026-07-03 late: set 8 INGESTED (farseer_set8.json; GAME_RULES
   6o). BLIND PREDICTION #2 PASSED (Ling Xue at L1 -4%: 14 procs/242
   kills vs predicted 14/244). Enemy-attack and enemy-defense debuffs
   both multiplicative/divisor, ~linear. Same-stat stacking ~full
   (additive-pool vs multiplicative below resolution at 5% - optional
   L5-scale test later, second-order). New cards: Elif (inf, +457),
   Estrella (lan, +404), Ligeia (marks, +200; S1 = enemy DEFENSE -5%
   per tooltip, not lethality). First T7-1000 VICTORY vs Tapir
   (3 heroes) = flagship regression battle.
   VERDICT: DATA SUFFICIENT - ENGINE CONSTRUCTION IS GO (plan in 3c).
4. ENGINE BUILD STARTED 2026-07-04 (see ENGINE_PLAN.md - the build
   spec with locked laws, mechanism candidates, verdict criteria).
   farm_fit.py extended: 9 clock durations as constraints, 'revenge'
   (casualty-paced exchange) family implemented alongside cadence
   kernels. FIRST RESULTS: revenge scored loss 42.8 (fails censored
   victories/mixed splits as ENGINE_PLAN anticipated via the whale-
   victory tension). Power-family w/ full 9-duration constraints:
   loss 7.71 - duration N-slope too steep (pred T~N^0.7 vs measured
   0.515: 11 vs 17.5 @N=100, 92 vs 73.5 Musk-T7), T7 kills over ~58%,
   mixed lancer splits under ~2x, censored Tapir wipe unreached.
   PHASE-1 ROUND 1 VERDICT: both pure extremes (cadence kernels,
   casualty-paced revenge) ELIMINATED.
   ROUND 3 COMPLETE (2026-07-04). MECHANISM FAMILY FOUND: asymmetric
   combat width + self-throttle + pinned-front + per-class k. Engine
   wos_sim/farm_engine.py; full results wos_sim/data/round3_results.json;
   verdict in ENGINE_PLAN "Phase 1 VERDICT". Reproduces 35 battles + 9
   durations to ~10-15% across 100x ranges; T7 N-ladder near-exact with
   cm=physical 1.10. Residuals -> ROUND 4: (a) beast-defense penetration
   floor for low-tier +30% overpredict; (b) cross-class dealer balance.
   Engine left in power-throttle + cm-pinned (honest) state. NO NEW
   EXPERIMENTS NEEDED - round 4 is compute.
   QA COMPLETE (external agent via Codex, 2026-07-04): read-only, no
   identity failures (32 power + 54 sum + 8 PvP checks all pass). Core
   stat-layer claims all reproduce. FOUND: (1) my coord-descent was
   UNDER-OPTIMIZED - ki 0.36->0.45 drops loss 20->4.3, so honest fit is
   likely much better than reported; (2) ed drifted to 0.55 vs clock
   0.483 - PIN it; (3) '~10-15%' headline over-claimed for the honest
   fit - downgraded; (4) assemble.py L184 stat-skill still additive not
   multiplicative - real code bug; (5) penetration floor needs a T7-
   protecting guard. Full round-4 action list in ENGINE_PLAN "ROUND 4 -
   actions" + round3_results.json qa_2026_07_04. Cheap fixes done:
   stale Lv13 beast levels 4.1->4.2; RMS/c/blind-pred claims softened.
   BRD.md written for the predictor/optimizer product (owner OQ answers
   folded in: suicide-rally objective, curated joiner+formation search,
   scout-OCR enemy load, local web app, hero-module backlog).
6. ROUND 4 DONE (2026-07-04; round4_results.json; farm_engine.BEST_PARAMS).
   QA #1 CONFIRMED+FIXED: round-3 loss 20.07 was an under-optimized coord-
   descent. Switched to scipy differential_evolution (global), PINNED
   ed=0.483 + cm=1.10 (physical), added marginal anchors -> loss ~2.0,
   10x better, NO free-knob cheat. Marginal linearity EXACT; T7 near-exact
   (~4%); mixed dealers ~5-15%; censored victories now classify right;
   durations within ~10%. Added armor-penetration term (base-attack keyed,
   buff-safe) - helped censored/mixed but did NOT fix low-tier residual
   (reclassed as throttle-curve / diagnostic-only regime). Residuals
   (solo low-tier +30-50%, solo marksman -30%) are DIAGNOSTIC-ONLY regimes
   that never occur in real high-tier PvP; model accurate where it matters.
   NEXT = PHASE 3 (below).
7. PHASE 3 STARTED (2026-07-04). DONE: (a) STAT-SKILL FIX - assemble.py +
   ModifierBoard now apply hero stat skills as MULTIPLICATIVE factors
   (board.skillmult, Prod(1+x)) not additive pool (QA finding fixed,
   GAME_RULES 6l); troop-skill stats stay additive; joiner-stacking form
   Prod-vs-Sum still open. (b) TWO-SIDED PvP ENGINE built
   (wos_sim/pvp_engine.py) - symmetric generalization reusing round-4
   BEST_PARAMS (per-class k, throttle, pin, penetration, counters,
   Ambusher bypass), one PvP rate-scale knob. (c) BACK-TEST harness
   (wos_sim/pvp_backtest.py) runs all 8 reports.
   FINDING: plumbing works; rate~70 gives realistic ~30-turn durations;
   BUT a SYSTEMATIC DEFENDER BIAS (engine: defender wins 6/8, often barely
   scratched; reality: attackers won ~half). DIAGNOSIS: the symmetric
   assumption is wrong - the farm mechanism was ASYMMETRIC (attacker full
   linear output vs compact target; defender/beast return fire frontage-
   limited ~N^ed sublinear). That asymmetry likely TRANSFERS: attacker
   piles onto the defender wall at full output, defender returns fire
   sublinearly -> would strengthen attackers and fix the bias.
   NEXT: implement the attacker-linear / defender-frontage-limited
   asymmetry in pvp_engine (restructure defender output as ~attacker-
   frontage^ed, mirroring farm's beast->own term), then CALIBRATE the
   PvP coupling (rate + asymmetry) on the r6/r8 SISTER PAIR only, and
   VALIDATE on the other 6 (do NOT fit all 8 - overfitting trap).
   Then proc scheduler + product build (BRD.md, separate agent).
   ROUND 2 (2026-07-04): 'paced' family (self-durability damping,
   symmetric) ELIMINATED (loss 69.8) BUT with the best DURATION surface
   yet (9 clocks within ~10-15%: 14/29/63 vs 17.5/31/57.5 etc.) and a
   decisive diagnostic: the tier-suppressor is NOT durability-linked -
   it is CLASS-linked. Same-tier solo classes kill nearly FLAT
   (T6 inf/lan/mar = 174/185/202) despite A*L ratios 1:2.5:3.05, while
   same-class tiers scale ~A*L. AND mixed-vs-solo per-unit factor
   10-16x suggests a PINNED-FRONT mechanic (units being targeted fire
   at reduced rate; protected units fire freely). ROUND 3 candidates:
   per-class k coefficients + pinned-front multiplier + paced duration
   structure. QA agent launched with QA_CONTEXT.md (memo pending).
   Jessie/DD scoping CORRECTED per Martin (rally-wide, GAME_RULES 6o) -
   also flagged in ENGINE_PLAN Phase 3: test 4x-Jessie stacking
   (additive pool x2.0 vs multiplicative x2.44) on r3/r7.
   Additive-with-panel predicts ~+2.6% kills at L5 (+25 points on +850);
   multiplicative predicts +25%.
3c. Other asks: T6 INFANTRY x1000 vs Lv12 Musk (completes the class
   triple with the T6 lancer/marks runs); a Bradley-on-MatiBlizzard
   pure-T10-infantry beast run (his S3 procs every 4 turns = TURN CLOCK
   -> pins absolute battle duration, decoupling k from time).
4. Asks to Martin (wishlist): (a) mid-range casualty hero A/B - 100
   lancers vs Lv20 with/without Sonya (casualty floor not saturated);
   (b) def/hp-only buff day (attack-free) for defensive elasticity;
   (c) controlled farm Polar Terror rallies (FC10 T10, no heroes,
   1/2/4 joiners known comps) for rally stat aggregation;
   (d) skill-level A/B (low-level S1 vs maxed, same hero card) if any
   account has unmaxed skills - isolates skill from card injection.
5. Then T12 reports/logic (structure already provisioned).

## Pending asks to Martin (minor)

- p1-p4 of BattleReportData.pdf (PvP experiments incl. mirror battles &
  territory battle) ingested at summary level only; may request re-crops.
- More PvP wishlist items: same-army A/B pairs, close fights, mutual-wipe
  report if ever seen again.

## 7. ENGINE TRACK (2026-07-04) - app track handed to a separate agent

This window is now ENGINE-ONLY. App track builds against wos_sim/api.py.
STRUCTURAL PvP FIX (E-2) DONE + KEPT: pvp_engine defender return-fire is
now frontage-limited (~N_def^def_ed, def_ed=0.483 beast value) + def_k
coefficient, replacing the symmetric-copy + scalar atk_adv. Calibrated
rate=320 / def_k=1000 on r6/r8 (clean). BUT holdouts stay 4/8 - diagnosed
as GENERALIZATION (two clean anchors can't extrapolate to the tankier /
marks-heavier r004 defender) + ONE-SIDED DATA (the winning enemy/scouted
attacker is under-specified in r004/r005). => The 8 reports cannot
identify a generalizable PvP kernel; the SMALL controlled E-4 campaign
(esp. E1 N-ladder + one NON-WIPE close fight) is genuinely needed.
Full write-up: ROADMAP.md sec 2b + 3.
CODING-ONLY infra that needs NO new data can proceed now: proc scheduler
(E-5, validate on beast determinism variance), T12 skills (E-7), batched
MC (E-6), regression harness (E-10), severe/light bookkeeping (E-11).

## 8. Proc scheduler + first T12 PvP report (2026-07-04)

- PROC SCHEDULER (E-5) BUILT: wos_sim/proc.py. Seeded per-turn proc rolls
  (Ambusher 0.20 whole-stack bypass; Crystal Lance double-damage) +
  monte_carlo() -> outcome distribution (P(win), casualty mean/sd/se/
  p5/p50/p95, turns). Validated: ~9.8% casualty variance from 2 procs
  (beast obs ~13-16%; more procs are pluggable -> higher), MC MEAN tracks
  the deterministic engine, CRN reproducible (same seed -> identical) for
  Goal-1 paired ranking. simulate_pvp now clones inputs (was mutating).
  HOOKS left: Crystal Shield 36-offset, gun double, hero proc skills.
- FIRST T12 PvP REPORT ingested: wos_sim/data/pvp_t12_report_001.json.
  Marty rally VICTORY over GFG garrison, but NEAR-EVEN (won w/ 62,364 of
  1.8M survivors, ~3.5%) => closest-to-boundary point in the corpus, high
  value for PvP calibration. Attacker had higher T12 research (Meridian
  5 vs 3, Starfire 8 vs 3) - likely decisive. Top-level totals + T12
  skill levels captured; per-participant splits available for a fuller
  pass.
- CONSTRAINT (Martin): battles can NEVER be non-wipe. So the E-4 "non-
  wipe close fight" ask is impossible; redesign the N-ladder to use the
  WINNER's (uncensored) casualties vs a VARYING garrison size (see reply).

## 9. T12 skills in-engine (2026-07-04)

T12 tier-3 skills BUILT (wos_sim/t12.py + hooks in pvp_engine + proc):
Meridian Phalanx (own marks DD +1%/lvl, own inf DT -1%/lvl, 5 turns),
Starfire (own marks DD +0.5%/lvl per 5-turn tick, ramps), Indomitable
Wall (enemy output -0.6%/lvl, 5 turns); summed level CLAMPED at 24.
Pass p['a_t12'] / p['d_t12'] = {indomitable_wall,meridian_phalanx,
starfire} level dicts (empty = no-op, engine unchanged). Verified both
directions (attacker marks buff -> faster kill/fewer losses; defender
wall -> attacker suffers). Regression-guarded. Effects confirmed from
tooltips; MAGNITUDE awaits PvP calibration like everything else PvP.
Buildable queue remaining (no data): richer harness scoring, more procs
(Crystal Shield/gun/hero), severe-light bookkeeping, batched MC.

## 10. PvP casualty kernel SOLVED for its regime (2026-07-04)

The 3-ladder controlled campaign is COMPLETE (v9 symmetric + v9b fixed-
attacker + v9c mirror; last 2 mirror rungs delivered = attacker 3K & 16K
vs a fixed 6K T7 garrison). All 8 unique count-pairs verified internally
consistent. See GAME_RULES 6p.

RESULT: one validated 2-param law (wos_sim/pvp_kernel.py):
  att_inf_incap = N_att - (N_att^E - K*N_def^E)^(1/E),  E=1.4291, K=0.1308.
Per-turn kernel R=k*N_own*N_enemy^(ed-1), ed=1.5709 (linear own +
target-abundance 0.571 on enemy). Train log-RMSE 0.0286 / max 5.6%,
LORO-CV 0.0400 (beats OLS baseline CV). Derived by the derive-pvp-kernel
design-panel workflow (beast_port won; asym/sym reduce to the same law -
gauge-degenerate) + independent refit. Regression check #7 added, ALL GREEN.

CONFIDENCE: HIGH within regime (50/50 comp, T10-vs-T7, attacker-wins-full-
wipe, no procs). This is the app's fast predictor for "rally this garrison,
what do I lose?". Do NOT extrapolate to other comps/tiers/close battles.

HONEST NEGATIVE: does NOT unify with the whale-report pvp_engine (r6/r8 at
~1.6M troops). Tested enemy_ab=0.571 on r6/r8 -> scale blowup, mutual-wipe
turn 1. So pvp_engine.enemy_ab defaults OFF (0.0); r6/r8 calibration
(rate=320,def_k=1000,def_ed=0.483) untouched; the two live as separate
regimes. Cross-scale/tier unification = future controlled ladders.

OPEN for a fuller kernel: (1) another very-attacker-heavy rung to nail the
+5.6% corner; (2) a non-50/50 composition rung to lift the comp assumption;
(3) a different tier matchup to see if ed=0.571 is universal or K just
re-tunes. None blocking - the current kernel is usable now.

UPDATE 2026-07-04: 20K 50/50 confirmation rung ingested (att_inf_incap 338,
kernel pred 329, -2.7% - CONFIRMS the kernel; high corner flattens ~5%). A
mixed 40/20/40 rung with T6 LANCERS (inf_incap 485). CORRECTION 2026-07-04:
T6 lancers have NO procs (Ambusher unlocks T7, Crystal Lance is FC/T11+), so
this battle is DETERMINISTIC - a CLEAN non-50/50 composition point (I had
wrongly assumed a proc from the lancer class). Composition shifts casualties
only ~-4% vs a same-size 50/50 army -> the total-count kernel is roughly
composition-robust. Both rungs in pvp_ladder_v9c.json. Martin chose "SHIP V1
NOW" - kernel kept at E=1.4291/K=0.1308 (9-pt refit is statistically identical).
Engine proc gating FIXED (Ambusher tier>=7, Crystal Lance tier>=11) in
mechanics.py/proc.py/predictor.kernel so sub-tier lancers no longer spuriously
proc; T6-lancer battles now correctly take the deterministic fast-path.

## 11. Engine<->predictor interface WIRED (2026-07-04)

Front-end agent shipped the predictor app layer (wos_sim/predictor/:
construct/summary/api + kernel seam) + a contract (ENGINE_INTERFACE.md). I
implemented the drop-in: wos_sim/predictor/kernel.py now defaults to a real
stochastic BatchKernel wrapping proc.simulate_stoch (non-mutating - clones per
battle). Delivered against the §6 checklist:
  * non-mutation, reproducibility, per-run RunRecords (winner/turns/per-class
    start+incap keyed by TroopType) - ALL verified;
  * CRN FIX: old run_batch used ONE shared RNG (stream depended on prior runs'
    lengths => on the units, breaking paired optimizer comparisons). Now run i
    seeds from (seed,i) ONLY via _run_rng. Added run_batch_units (§3 units
    entry) for the optimizer;
  * perf: 100K runs ~13s (<30s target) with NO vectorization; no-proc matchups
    short-circuit to one sim (instant). Vectorization (E-6) not needed yet;
  * params default injected DEFAULT_PVP_PARAMS={rate:320,def_k:1000,def_ed:0.483}
    (r6/r8) since the app passes params=None and rate=1.0 is meaningless.
19/19 predictor tests pass; engine regression still ALL GREEN.

CAVEATS surfaced to the app (in ENGINE_INTERFACE.md status section, not hidden):
(1) magnitude weakly calibrated (r6/r8 whale pair only) - that's what
engine_model_error is for; the VALIDATED farm kernel (pvp_kernel.py) is the
high-confidence path for the 50/50 garrison-wipe regime. (2) proc-variance
MAGNITUDE uncalibrated (whole-stack Ambusher, no repeat data); near-even fights
show ~45% spread (max proc-sensitivity), not the 13-16% farm-wipe figure.
Deferred (return as they land): proc_contributions, severe/light split (engine
returns raw total incap; app applies the split), sample trace, convergence
signal, true antithetic (E-6 no-op stub for now).

## 12. Troop base stats serve ALL tiers (2026-07-04)

Predictor construct hit KeyError on sub-T10 troops (e.g. T6 lancer) because
troop_base_stats() only read _FC_ROWS (T10/T11). ROOT CAUSE was CODE, not data:
the base tier tables (_TIER_ROWS, T1-T11, all 3 classes) were already present and
- verified this session against Martin's wostools wiki paste - EXACT for
Infantry/Lancer/Marksman (the old "Marksman T7-T9 provisional" flag was wrong;
they were right). Fix: troop_base_stats now serves T1-T12 (T1-T9 = base tier no
FC; T10/T11 = FC ladder; T12 = T11 FC+3). Regression check #8 added (ALL GREEN).
T6-lancer construct + api.predict now work end-to-end. Minor wiki note: T3 power
is Inf 6 vs Lan/Mar 5 (kept uniform=6; T3 unused, negligible). Wiki data is
Firestore-backed + Cloudflare-blocked to bots, so it can't be auto-fetched -
Martin pastes it; workbook "Troop Stats" tab only carries T11 FC9/FC10.
NOTE: front-end added wos_sim/predictor/tests/test_server.py (FastAPI endpoint);
it SKIPS cleanly when fastapi is absent (try/except guard), so full suite =
35 passed, 3 skipped in the engine env. No action needed.

## 17. Near-even T12 report FULLY extracted; earlier structural claim RETRACTED (2026-07-05)

CORRECTION (Martin caught it): my first-pass "structural mis-ranking / wall" was
drawn from a reconstruction that applied T12 troop skills but NOT the HERO skills
(built from panels only), then compared vs r6/r8 which DO have hero skills - an
invalid comparison. Also r6/r8 are PRE-T12 (no T12 skills, sub-Gen11 heroes) and
should NOT be force-fit with this T12 regime under one calibration. REDONE via
construct.build (hero skills on): skills add +8% stat + LARGE Damage-Dealt (+55%
inf/marks, +100% lancer) -> battle crushes to ~8 turns (real ~30+), attacker
~70% survivors (real 3.45%). rate=168 (fit on r6/r8's lower-DD pre-T12 config)
does not fit this high-DD T12 config. So the dominant issue is DD-driven over-
acceleration + a regime mismatch, NOT a clean structural mis-rank - retracted.
Possible DD over-count (conditional/targeted skills applied flat, assemble v0) -
TBD. PATH: calibrate the T12 regime SEPARATELY; needs several T12 near-even
reports + this battle's real round count. Below is the (now-superseded) first pass.



pvp_t12_report_001.json now has FULL stats (WOS_BattleReports_T12_146.pdf): both
sides' scouted panels per class/stat, per-class counts+avg tiers, lead heroes
(att Elif/Dominic/Vulcanus g14/14/13, def Elif/Dominic/Cara g14/14/14), buffs,
T12 levels. Attacker OFFENSE-focused (~+4093% inf atk), defender DEFENSE-focused
(~+3846% inf def). Attacker won RAZOR-THIN: 62,364 survivors of 1.805M = 3.45%,
defender fully wiped. This is the ONLY razor-thin anchor in the corpus.
RECALIBRATION VERDICT: the general engine CANNOT reproduce it. Reconstructed
exactly + swept def_ed x def_k (incl. the better symmetric-linear def_ed=1.0):
every config keeping r6/r8=attacker-wins gives the attacker >=50% survivors here
(vs real 3.45%); closing the gap cliffs to a defender blowout - no razor-thin
band. Deeper: the engine MIS-RANKS difficulty (computes this battle EASIER for
the attacker than r006, reality has it HARDER: 3.45% vs 28%). Root cause = per-
unit damage model under-weights the defender's Defense/Health (qd/qh from the
beast fit) so a defense-focused garrison isn't tanky enough. STRUCTURAL, not a
knob. PROMISING DIRECTION: symmetric-linear (def_ed=1.0) gives the right
DYNAMICS (40-turn near-mutual-annihilation grinds) vs the current def_ed=0.483
(too-decisive), and r006 casualties get closer (16.5% vs current 58% vs real
28%) - but NOT applied (partial, unvalidated, doesn't fix the mis-rank). NEED:
several more near-even reports with full stats (esp. an attacker-barely-LOSES) to
re-fit the PvP damage model. Until then near-even = untrustworthy (calibrated=false).

## 16. Duration calibration rate 320->168 (2026-07-05)

Martin: big rallies really last "several dozens" of rounds; engine gave 14-16.
DIAGNOSED: rate=320 was fit to r6/r8 CASUALTIES (which are ~rate-invariant), so
the turn count was never constrained -> ~2x too fast. Ground truth from Martin
(Bradley S3 counter ~4 rounds/proc): r006 8 procs ~33 rounds, r008 10 ~42. Fit
rate=168 -> engine r006=33t, r008=42t, winner still A, casualties unchanged.
DEFAULT_PVP_PARAMS rate=168; regression #4 now guards turns (r006 30-36, r008
38-45). GAME_RULES 6r. NOT cosmetic: T12's fixed 5-turn windows were over-
weighted ~2x by the too-fast clock, DISTORTING the winner (T12-off = rate-stable;
T12-on = flips with rate). Fix corrects T12-battle outcomes too. The 60/30/10
1.5M scenario now ~26.5 rounds (was ~15). Removed a fragile simulate_pvp
winner!='D' guard from _kernel_box (rate-dependent + redundant vs stat-range
checks). ALL GREEN (14 checks). CAVEAT: duration is calibrated; the near-even
T12 OUTCOME magnitude stays uncalibrated (calibrated=False) - direction only.

## 15. Hero GENERATION -> stats (E-12, 2026-07-05)

Martin flagged: hero GENERATION strongly affects STATS (higher gen = stronger),
but NEVER skills, and the "Hero Stats" tab wasn't being used. Findings + build:
  * CONFIRMED skills are NOT gen-scaled: assemble.py applies skill amounts from
    the skill book verbatim; generation only ever appears in Hero Profile
    identity + server-age math. No gen multiplier on any skill. (Martin's rule
    honored - no fix needed there.)
  * gen->stat is a clean LOOKUP (workbook 'Hero Stats' x 'Hero Profile'): a lead
    hero's 4 stats depend ONLY on generation (Atk==Def, Leth==HP). Exact table
    g1..g14 in wos_sim/hero_stats.py, verified vs every workbook hero for g2-14.
  * AGGREGATION (workbook 'Current Stats - Self' formula): Scouted =
    (Base + HeroesEffect + Gear*Fudge)*(1+Buff)+Buff; HeroesEffect = lead hero's
    gen value. So hero enters ADDITIVELY, inside the buff mult -> contribution =
    gen_value*(1+buff[stat]). Cross-checked vs the Mia g3->Fred g9 report: lancer
    Atk +748% (=6.5052*1.15) and Def +650% (=6.5052*1.0) - the atk/def gap IS the
    per-stat buff factor. Model reproduces it.
  * Was the GAP: assemble.py (report replay) never used HeroesEffect - fine for
    replay (scouted panel already includes heroes) but the PREDICTOR can't swap
    heroes without it. Built wos_sim/hero_stats.py: hero_stat(gen,stat) +
    relayer_panel(panel, class_gens, buffs) = Martin's strip-highest-gen /
    re-apply-per-class method for the PRE-ASSUMED symmetric case (actual-stats
    case = pass through unchanged). Regression check #10 added. ALL GREEN (13).
  * NAME RESOLVER: front-end passes hero NAMES (lead_heroes {class: name}), so
    added data/hero_generations.json (51 heroes, static - no workbook at runtime)
    + hero_generation(name), class_gens_from_names(), relayer_by_names(). Resolver
    distinguishes Greg(g3 marks) from Gregory(g10 inf); SR/legacy leads dropped.
  * WIRED INTO THE BATTLE PATH (2026-07-05): construct.build now calls the relayer
    in the PRE-ASSUMED symmetric case (own.panel==enemy.panel AND stats_mode==
    scouted): _relayer_hero_stats() strips the assumed highest-gen hero and
    re-applies each side's actual per-class lead-hero gen. Regression #11 guards
    it. Verified end-to-end: own inf Gisela(g13)->P(win)=1.00, Flint(g2)->0.00 -
    matching Martin's expectation (the swap now actually reaches the sim).
  * CONTRACT (Martin, 2026-07-05): panel = FULL SCOUTED, always stats_mode=scouted
    (base is derived by the engine's strip step); front-end sends the same scouted
    panel both sides (pre-assumed) + lead_heroes + RAW buffs via engine_params
    (panel is net of buffs, so relayer runs buff-free). joiners = skills only, no
    stat effect (workbook HeroesEffect sums only the 3 captain leads).
  * STILL OPEN (deeper): the general engine is KNIFE-EDGE + uncalibrated for near-
    even T12 whale matchups (own stats x0.5->0% win, x1->97%, x2->100% in <3
    rounds; 1-round wipes at high stats). The relayer fixes DIRECTION for large
    stat gaps; the win% for CLOSE matchups stays untrustworthy (calibrated=False)
    until we get controlled data in that regime. Not fixable without it.

## 14. Independent QA triage (2026-07-05, QA_FINDINGS.md)

Independent adversarial review (Codex) INDEPENDENTLY re-derived the kernel (E=1.4291,
K=0.1308, LORO-CV 0.03995, closed-form vs sim <0.03% - all confirmed) and found real
issues. All triaged + fixed:
  * CRITICAL (fast-path stat-blind): _kernel_box checked only tiers, so it stamped
    "validated +-4.5%" on matchups the attacker would LOSE (weak att vs godlike def).
    FIXED - gate is now stat-aware: both-side 50/50 inf+marks, tiers (att T10/def T7/
    marks T6), panel-range + inf panel-ratio<=4x sanity, AND a simulate_pvp direction
    guard (bail if the stat engine hands the defender the win). Being adversarially
    re-verified via workflow.
  * HIGH (0.13 general band not defensible - 4/8 winner, up to 85% casualty miss):
    engine_meta now returns calibrated=False + model_error=0.5 (coarse FLOOR, not a
    band) for general; render the badge on `calibrated`, not the number. pvp_kernel
    path -> calibrated=True, 0.045.
  * MEDIUM (deterministic batch aliased one RunRecord n times): _replicate makes n
    INDEPENDENT copies (both the kernel path and the no-proc short-circuit).
  * MEDIUM (v9c.json att_inf_survivors held TOTAL survivors on 16k/20k rungs): fixed to
    infantry survivors (7657/9662) + added att_total_survivors. Kernel fit used
    att_inf_incap so the fit was never affected.
  * MEDIUM (100K/<30s not met for slow-param stochastic fights): ENGINE_INTERFACE perf
    row corrected to "params-dependent; universal 100K guarantee needs E-6 vectorization".
  * LOW: troop_base_stats now ValueErrors on fc outside 0-10 (was neg-index/IndexError);
    pvp_engine.py uses AMBUSHER_MIN_TIER (was literal 7); mechanics.py:62 stale additive-
    pool comment corrected to multiplicative (skillmult); proc.py smoke test shows the
    surviving side's variance (loser saturates).
Regression hardened: check #9 now guards stat-aware routing + calibrated flags + non-
aliasing. ALL GREEN (12 checks); predictor suite 37 passed, 3 skipped.
QA's honest bottom line stands: trustworthy INSIDE the validated ladder law, and the
predictor now can't silently paint that high-confidence law onto unearned matchups.

## 13. Per-forecast confidence + validated fast-path (2026-07-04)

Front-end's critical ask (ENGINE_REPLY.md): per-matchup confidence so the UI can
show "+-4% validated" vs "+-13% provisional". DELIVERED in predictor/kernel.py:
  * engine_meta(a_units,d_units,params) -> {path, model_error, stochastic, note}.
    path='pvp_kernel'(0.045) | 'general'(0.13). Call once in api.predict; does NOT
    change run_batch's list contract.
  * FAST-PATH ROUTED: run_batch_units sends in-box matchups to pvp_kernel
    (deterministic closed form, all attacker loss on infantry, defender wiped) via
    _kernel_records; same gate as engine_meta so records match the reported error.
  * pvp_kernel gained garrison_wipe_forecast()/battle_turns()/MODEL_ERROR=0.045.
  * Severe fraction 0.35 CONFIRMED for rally-vs-garrison (ladder 2100/6000; att
    121/343, 272/775). Told front-end to use 0.35.
Regression check #9 added (in-box->pvp_kernel/0.045 w/ kernel casualties;
T12->general/0.13). ALL GREEN (12 checks); 29 predictor tests pass.

HONEST COVERAGE / STRATEGIC: the validated +-4.5% path is NARROW - K encodes the
exact T10-vs-T7 gap + ladder-like near-even panels, E the 50/50 comp. The app UI
is T10-T12, so MOST forecasts honestly fall to 'general' +-13%. Broadening the
validated band to real app matchups (T11/T12 vs garrison tiers, real panel gaps)
= controlled ladders at those gaps (parked). Open decision for Martin: ship v1
with mostly-provisional bands, or run a few targeted ladders to make the common
app matchups validated. NOT gating on panels (impractical) - documented instead.
Did NOT edit api.py/summary.py (front-end's layer); gave them the 3-line wiring.

## 18. Turn-engine recalibration against three anchors — CONDITIONAL certified (2026-07-08, Claude)

The turn engine was rebuilt from 5/27 to 17/27 anchor gates and is now the
**default API path** (it outranks the general engine on every anchor and emits
skill telemetry). Structural fixes: multiplicative debuff composition + floor
(was additive to −97.8% defense → 2-turn blowups), wounded-keep-fighting fire
mode (stacks fire at starting strength — the anchors show constant absolute
casualty rates, not Lanchester taper), defender per-capita parity
(def_k 1000/def_ed 0.483 → 1.0/1.0; the old pair inverted the decisive solo
anchor), mod_gamma=0.30 diminishing returns (kits netted 3-4x, reality ~1x),
and a kernel fix so the general engine's params no longer leak into the turn
path end-to-end. engine_meta now runs a ±2% perturbation probe and labels
near-even matchups `coin_flip` (A1 flips — as it did in reality at 3.45%).
Verdicts: A1 winner/type/survivors PASS (79k vs real 62k), A2 winner/turns/
count PASS but survivor-TYPE still marksman (real: lancers), A3 winner + wall
structure PASS (lancer 0% loss, inf barely survives) but marksman bypass bleed
7.8% vs real 66%. Honest residual: discrete bypass REDISTRIBUTION mechanics
(not scalar knobs — swept and rejected: they tip the knife-edge). Tools:
`wos_sim/anchor_eval.py` (scorecard/traces), `wos_sim/fit_turn_params.py`
(replayable grid fit); regression #12 guards all three anchor winners.
See ENGINE_REBUILD/QA_REPORT.md (CONDITIONAL, 2026-07-08).

## 19. Anchor 4 (Amanda vs RampageR) — second recalibration pass (2026-07-08, Claude)

Martin's retest surfaced a fourth inverted battle (solo vs 69%-marksman
garrison+support; real: A wins 58.3% survivors ~16t, engine: A wiped,
p_win=0.000). Ingested as `pvp_t12_report_004.json` / anchor A4. Its
per-skill kill columns pinned the skill-packet scale: real skill kills ≈7% of
casualties vs engine 38-50% (def Ligeia 99k vs 8.6k real) → K_skill locked
0.15 + a skill_kill_share<20% gate. Added q_off/q_def normalized
stat-compressions to base_strike_damage (q_def=0.7 locked; beast-fitted
H^1.45 over-rewarded health-stacked panels). DECLARED TRADE-OFF: def_k=0.5
ranks ALL FOUR anchors correctly (end-to-end p_win 1.00/1.00/0.997/1.00) but
sacrifices near-even survivor depth (A1/A2 predict ~65-73% survivors vs real
3-6%); def_k=1.0 did the reverse (deep grinds, both solo battles inverted).
Winners chosen over depth; near-even magnitudes labeled coin_flip via a
re-based detector (static strength-symmetry ±10% OR dynamic flip probe — the
±2% probe alone dies in the def_k=0.5 regime). Locked set: rate=155,
def_k=0.5, def_ed=1.0, fire_mode=start, mod_gamma=0.38, stat_floor=0.4,
K_skill=0.15, q_def=0.7. Scorecard 20/36 gates, 4/4 winners; regression #12
now guards all four. OPEN mechanic: A2-vs-A4 marks-heavy tension (bypass
redistribution + possible wall-integrity effect). Wanted data: a marks-heavy
side WINNING, any attacker-LOSES report, or per-turn casualties.

## 20. Joiner stat-skill suppression bug (2026-07-08, Claude; found via Martin's 4x-Nora probe)

Martin flagged a Gen15 mirror rally with 4x Nora joiners yielding 100% win.
Investigation: Nora's SK1 itself is correct (+15% DD / −15% DT inf+marks per
copy; audit-clean); the REAL bug was that `panel_is_final` suppression was
applied to JOINER stat rows too — but a joiner is another player's hero, so
its stat skills are never in this side's scouted panel. Effect: stat-row
joiners (Patrick +25% HP, Gatot +30% def) were silently zeroed while DD/DT
joiners (Nora, Bahiti) applied in full — an artificial joiner-kit asymmetry.
Fixed in both paths (skills.resolve role-aware; skill_defs_from_matchup passes
suppress=False for joiners) + a guard test. TURN_PARAMS re-touched after the
fix (rate 155→168, def_k 0.5→0.45, γ back to 0.30): 21/36 gates, 4/4 winners.
Remaining honest caveat: 4 identical joiners stack additively pre-compression;
whether the real game stacks 4 copies of the same joiner passive is UNKNOWN
(no anchor has duplicate joiners) — flagged for a future anchor.
