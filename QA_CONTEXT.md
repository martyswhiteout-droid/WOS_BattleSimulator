# QA Context - WoS Battle Formula Project (running brief for a QA agent)

Updated: 2026-07-04. Owner: Martin. Builder: Claude (multi-session).

## Your role

Second-opinion robustness review of a reverse-engineering project: we are
deriving Whiteout Survival's battle formula from ~150 controlled battle
reports. Check that what is claimed as "confirmed" is actually supported
by the recorded data, that the code implements the documented rules, and
that conclusions would survive re-derivation. Do NOT nitpick style,
naming, or minor numeric formatting; focus on: unsupported claims,
circular calibration, data-entry errors that break identities, code that
diverges from GAME_RULES.md, and overfitting risks in the ongoing
mechanism search.

## Source-of-truth documents (read in this order)

1. GAME_RULES.md - every confirmed mechanic with provenance and dates.
   Sections 6g-6o are the 2026-07-03 calibration campaign (the core).
2. ENGINE_PLAN.md - the engine build spec: locked laws, candidate
   mechanisms, verdict criteria, phases.
3. STATUS.md - session-by-session state, incl. Phase-1 fit results and
   failure signatures (2/2h/2i and section 4).

## Data inventory (wos_sim/data/) - all extracted from battle-report
## screenshots (PDFs in E:\WOS\), vision-read, then arithmetic-verified

- reports/report_001..008.json - 8 PvP fortress battles (whale accounts,
  proc-heavy). Identities validated: participant sums == side totals.
- beast_hunts.json - Marty's 11 controlled beast experiments.
- beast_hunts_marlinman.json - 25 experiments incl. 5x determinism runs,
  N-ladder, solo classes, beast ladder, wall-ratio curve.
- beast_hunts_marlinman2.json - hero layering (Rufus/Sonya), repeat
  variance, marksman wall, buff ladder + BUFF ALGEBRA checks (12/12).
- enemy_penalty_ab.json - divisor-rule A/B panels (hypothesis race).
- bradley_skill_ladder.json - card-injection proof + skill tooltips.
- polar_terror_rally.json - rally-only beast + T12 skill texts.
- farseer_infantry_ladder.json - set 1: DETERMINISM proof (3 identical
  runs), N-ladder, tier ladder, power identities.
- farseer_set3.json - Seo-yoon/Jassier ladders (attack elasticity 1.0,
  DD == attack), mixed-class battles, replicate pairs.
- fs3_extraction_raw.json - raw multi-agent extraction output for set 3
  (provenance for QA cross-checks).
- farseer_set4.json - tier rungs T3-T5, solo lancer/marks, beast ladder.
- farseer_set5.json - MULTIPLICATIVE-skill verdict (Marlinman A/B),
  turn clocks (Bradley S3 x4 / Renee S1 x2), single-lancer probe.
- farseer_set6.json - lethality linearity (President-buff A/B), T2
  durations, dual-clock agreement, grand composition check (246).
- farseer_set7.json - tier durations, PASSED duration prediction,
  multiplier-stack cross-validation.
- farseer_set8.json - debuff directions, same-stat stacking, blind
  prediction #2 (Ling Xue 14 procs/242 kills), new hero cards.
- avatars/ - 51 hero portraits + manifest (identification aid only).

Raw PDFs: E:\WOS\WOS_BattleReports_*.pdf (originals of everything above).

## Round-3 mechanism (ACTIVE, 2026-07-04) - review the reasoning

farm_engine.py implements the leading candidate: ASYMMETRIC COMBAT WIDTH
+ per-class coefficients. The core claim you should sanity-check:
- The joint law T~N^0.515 AND total_kills~N^1.525 is derived to require
  ONE structure: own kill rate LINEAR in N (all units fire), beast
  engages own frontage SUBLINEAR ~N^ed with ed~0.485. Then T=N^(1-ed)
  and total=N^1 x N^(1-ed)=N^1.515. Verify this exponent algebra.
- Per-class k (ki,kl,km) absorbs cross-class flatness (T6 solo
  174/185/202 vs A*L 1:2.5:3.05). RISK: with 3 free per-class k's plus
  ed,qd,qh,kb,cm,bpow (9 params) against ~35 battles + 9 durations,
  watch for overfit. Check: does the fitted ed stay near 0.485
  (its independent clock-derived value) or drift to absorb error? A
  large drift = the mechanism is compensating, not explaining.
- Rounds 1 (cadence kernels) and 2 (symmetric paced/revenge) are
  ELIMINATED and documented in STATUS 4 - do not re-litigate them.
- ROUND 3 RESULT (wos_sim/data/round3_results.json): mechanism family
  found (asymmetric width + throttle + pin + per-class k), reproduces
  the corpus to ~10-15%. QA CHECKS WANTED on this specifically:
  (1) Is the asymmetric structure OVERFIT? It has ~11 free params
  (ki,kl,km,kb,ed,qd,qh,cm,bpow,so,pin) vs 35 battles + 9 durations =
  44 targets. Ratio ~4:1 - thin but not degenerate. Check whether any
  param is unconstrained (moves freely without changing loss) - that
  would signal redundancy. Especially: are so, pin, and per-class k
  DEGENERATE with each other (all three shape cross-class output)?
  (2) The two throttle variants (DH vs power) trade which residual they
  win. Verify the claim that a beast-defense penetration floor (not yet
  added) would explain the low-tier +30% - i.e. that low-tier attack is
  genuinely small vs beast defense (recompute A_eff vs beast D_eff for
  T2-T5 vs the Musk L4 beast; is A < D there?).
  (3) Sanity: does farm_engine.py's simulate() actually make OWN kill
  rate linear in N and beast engagement ~N^ed? Read the loop and
  confirm the code matches the claimed asymmetry (not just the docstring).
- ROUND 4 is scoped in round3_results.json - do not report its known
  targets as new findings.

## Code inventory (wos_sim/)

- models.py, loader.py - typed data model; xlsx ingestion (workbook
  'WoS battle simulator.xlsx' stays OPEN in Excel - never openpyxl-save).
- reports.py - PvP report model + identity validation + standard_pool()
  (divisor form - check against GAME_RULES 6h).
- assemble.py - report -> engine stat assembly (divisor form).
- mechanics.py - rally/garrison activation rules (captain 9 skills +
  3 context-scoped widgets; joiners top-4 flag S1 rally-wide).
- troop_catalog.py - wostools tier/FC stat tables + interpolation
  (beast units == tier units, verified by power inversion).
- calibrate.py - beast-data harness (power-mapping checks, observables).
- farm_fit.py - Phase-1 mechanism search: per-turn sim, kernel families,
  duration constraints, battle corpus. THE ACTIVE WORKBENCH.
- battle.py, fit_kernel.py - older static-EV engine (superseded,
  kept for reference).

## Claims register - spot-check these against the data files

1. Stat layer: Eff = Base x (1+panel) x (1+Sum buffs) / (1+Sum penalties)
   x Prod(1+skill_i). Evidence: beast_hunts_marlinman2 buff_algebra
   (12 exact checks); enemy_penalty_ab (RMS 0.034 vs 3.7/2.0 for rivals);
   farseer_set5 skill_pool_discriminator (x1.2506 vs additive x1.026).
2. Hero cards inject into own-class panel rows. Evidence:
   bradley_skill_ladder (card screenshot == deltas), sets 5-8 cards.
3. Determinism without procs; RNG only in proc skills. Evidence:
   farseer_infantry_ladder (3 identical), set3 replicate pairs.
4. Marginal linearity of Attack / Lethality / DD; debuffs divide both
   directions. Evidence: sets 3, 5, 6, 8 (incl. 2 passed blind
   predictions - check the prediction arithmetic independently).
5. Duration laws: T ~ N^0.515 x (own DxH)^0.8-1.0. Evidence: clock
   counts in sets 5-7 (Bradley S3 every 4 turns, Renee S1 every 2 on
   odd turns, Lloyd S2 every 3 - cross-validated in one battle).
6. Total kills ~ c x A x L x (N/1000)^1.525 with c ~ 4.2-5.3.
   Evidence: sets 1/4/7 tables. NOTE the +-13% c-drift is UNEXPLAINED -
   flag if any claim treats it as exact.
7. Power-loss identities: own power loss = severe count x unit power;
   beast power loss = kills x unit power. Every dataset should satisfy
   these EXACTLY - recompute a sample; any failure = data-entry bug.

## Known weaknesses / honest open items (do not report these as new)

- The core damage mechanism is UNSOLVED (Phase 1 in progress); all
  current kernel families fail some constraint subset - documented in
  STATUS 4 and ENGINE_PLAN. Risk to watch: overfitting a family to the
  corpus without mechanism plausibility.
- Same-stat stacking: additive-pool vs multiplicative indistinguishable
  below ~5% magnitudes (set 8). Joiner-stacking (4x Jessie) untested.
- Bradley S2 (class-targeted DD) did NOT act vs beasts (set 5) - anomaly.
- Low-tier battles (T1/T2) may be integer-quantization polluted.
- Vision extraction: numbers were read from screenshots; identity checks
  catch most errors, but panel rows without identities (e.g. stat
  bonuses) rest on single reads. fs3_extraction_raw.json preserves one
  set's raw agent output for spot audits.
- Marty's PDF pages 1-4 (PvP mirror experiments) only summarized.

## Web references

- Troop stat tables (used for all tier stats; verified against reports):
  https://wostools.net/wiki/troops/infantry
  https://wostools.net/wiki/troops/lancers
  https://wostools.net/wiki/troops/marksmen
- T12: https://wostools.net/blog/t12-exalted-troops-the-facts and
  /blog/t12-exalted-troops-guide
- Hero skill reference (audited vs workbook): https://whiteoutsurvival.wiki
  (note: hero "Gwen" lives at /heroes/gwen-2/; "Ling Xue" at slug
  ling-shuang).
- wostools blocks plain fetchers (403 + client-side rendering) - use a
  real browser session.

## How to re-verify quickly

- py -m wos_sim.calibrate            (beast power-mapping + observables)
- py -m wos_sim.farm_fit power       (mechanism-search harness; battles
  and DURATIONS tables embedded at top of farm_fit.py)
- Identity spot-check: load any dataset, assert kills x unit power ==
  beast power loss; severe x tier power == own power loss.
- Python is 'py' (3.14); plain 'python' is a broken venv.

## QA output wanted

A short memo: (1) claims that do NOT hold up or need caveats, with the
specific file/number; (2) any identity-check failures; (3) code-vs-rules
divergences; (4) top 3 robustness risks for the engine phase. Skip
anything already in "Known weaknesses".
