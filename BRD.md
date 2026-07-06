# BRD - WoS Battle Predictor & Counter-Optimizer

Business Requirements Document. Owner: Martin. Drafted 2026-07-04.
Companion docs: GAME_RULES.md (mechanics), ENGINE_PLAN.md (engine build),
STATUS.md (state). This BRD assumes the battle engine reaches acceptable
accuracy (currently ~10-15%; round 4 pending) - see Dependencies.

---

## 1. Purpose

Build a decision-support tool that predicts Whiteout Survival rally/garrison
battle outcomes and recommends the best counter, BEFORE committing real
troops. Two questions it must answer:

- **Goal 2 - Predictor:** "Given this exact matchup, what is the likely
  result?" -> outcome probability distribution from 100K Monte-Carlo runs.
- **Goal 1 - Optimizer:** "Against this known enemy, what joiners and
  formation should I bring?" -> ranked recommendations with confidence.

## 2. Scope

IN scope:
- Ingest OWN side from screenshots -> a stat profile.
- Manually construct an ENEMY profile (stats, captain heroes, troop size,
  formation, 4 joiners, pet buffs, rally/garrison context) and persist it
  as a reusable JSON profile.
- A stochastic battle engine (deterministic core + proc scheduler).
- Monte-Carlo outcome prediction (Goal 2).
- Search/optimization over own joiners + formation (Goal 1).

OUT of scope (v1):
- Live game integration / automation of actual troop deployment.
- Non-rally battle types beyond rally-vs-garrison (foundry, territory,
  beasts) - engine supports them but UI targets PvP rally/garrison first.
- Multi-rally / reinforcement timing simulation.

## 3. Users & context

Single primary user (Martin), power-user, comfortable with JSON and CLI.
Used pre-battle: scout enemy -> build enemy profile -> load own profile ->
ask predictor or optimizer -> decide. Latency budget: seconds, not hours.

## 4. Goals & success criteria

| Goal | Success criterion |
|------|-------------------|
| G2 Predictor | 100K sims in < ~30s; returns P(win), casualty distribution (own/enemy killed, survivors), net power swing, with Monte-Carlo standard errors. Back-tests within engine tolerance against the 8 known PvP reports. |
| G1 Optimizer | Returns a ranked shortlist of (joiner set + formation) with P(win) and a statistically-significant ordering; evaluates the practical search space in < ~2 min; recommendation beats a naive baseline (current meta formation) on the validation matchups. |

## 5. Background - what already exists (reuse, don't rebuild)

- **Stat model** (CONFIRMED, GAME_RULES 6g-6o):
  `Effective = TierBase x (1+panel) x (1+Sum buffs) / (1+Sum enemy penalties) x Prod(1+hero stat skills)`.
  Cards inject into own-class panel rows; enemy penalties DIVIDE; skills
  multiply; joiner flag-S1 applies rally-wide.
- **Engine** (`wos_sim/farm_engine.py`): asymmetric combat-width mechanism,
  deterministic core validated to ~10-15% on 35 farm battles + 9 durations.
  Round 4 (penetration floor, cross-class balance, proc scheduler) pending.
- **Data model** (`wos_sim/models.py`, `reports.py`): PlayerStats,
  ReportSide, hero/skill/troop catalogs, rally activation rules
  (`mechanics.py`), troop stat tables (`troop_catalog.py`).
- **Vision extraction pattern**: PDF/PNG render -> panel read -> identity
  validation (used across ~150 battle reports).

The tool is largely an ORCHESTRATION + UI + search layer on top of these.

---

## 6. Functional requirements (by module)

### M1 - Own-side screenshot ingestion  ->  own profile
- FR1.1 Accept 1..N screenshots (battle report, scout panel, hero cards,
  specials/pet panel).
- FR1.2 Detect panel type and extract: 12-row Stat Bonuses (Inf/Lan/Mar x
  A/D/L/H), composition (per-class troop counts, tier badge, FC badge),
  specials pool (items/widgets/pets and enemy-penalty pets), captain hero
  trio + skill levels, hero cards (Expedition stat injection).
- FR1.3 Validate reads with the known identities (power-loss = severe x
  unit power; panel algebra internal consistency) and FLAG low-confidence
  cells for human confirmation. No silent guesses.
- FR1.4 Emit an OWN profile JSON (schema in S.9) and let the user correct
  any field before saving.
- NOTE: v1 may ship with manual entry only; automated vision is a fast-
  follow (Phase D). The profile schema is the contract either way.

### M2 - Enemy profile builder & persistence
- FR2.0 ENEMY SCOUT OCR (owner-confirmed primary path): the owner
  normally has a SCOUTED REPORT of the enemy; upload that screenshot and
  OCR renders the enemy stat panel into the enemy profile (same vision +
  identity-validation pipeline as M1, applied to the scout panel). Manual
  entry (below) is the fallback / for fields the scout doesn't show
  (heroes, joiners, formation, pets).
- FR2.1 Manual entry form for: player label; context (rally attacker vs
  garrison defender); troop size (total) and formation split
  (inf/lan/mar %, e.g. 60/40/0); per-class tier/FC; scouted stat panel OR
  raw stat pools; captain heroes (trio) + skill levels + widget set;
  first four joiners (flag hero + level each); pet buffs & enemy-penalty
  pets; war items.
- FR2.2 Apply the confirmed activation rules (mechanics.py): captain
  contributes 9 skills + 3 context-scoped widgets; joiners contribute
  top-4 flag S1 rally-wide; infantry widgets garrison-scoped; etc.
- FR2.3 Save / load / list / duplicate named profiles (JSON files in a
  profiles/ dir). Version each profile with a schema_version.
- FR2.4 Support PARTIAL / UNCERTAIN enemy data: any stat may be a point
  value OR a range/distribution (feeds robust optimization, S.7.G1).

### M3 - Battle-construct assembler
- FR3.1 Combine an OWN profile + an ENEMY profile + context into a fully-
  resolved two-sided battle input: per-class effective stats (via the
  stat model), skill/proc tables, absorption order, widget scoping.
- FR3.2 Reuse assemble.py's routing; extend from report-derived to
  profile-derived inputs.
- FR3.3 Deterministically reproducible given a seed.

### M4 - Simulation engine (stochastic)
- FR4.1 Deterministic per-turn core (round-3 mechanism) + PROC SCHEDULER:
  Bernoulli/again rolls for Ambusher (0.20), Crystal Lance (0.10/0.15),
  Crystal Shield offset, gun double-damage, hero proc skills with their
  TriggerUnit semantics; crit/direct-kill channels.
- FR4.2 One call = one battle -> full result record: outcome
  (win/loss/mutual-wipe), per-side per-class killed/injured/severe/light/
  survivors, turns, power swing, proc counts.
- FR4.3 Severe/light bookkeeping by structure type (post-battle split).
- FR4.4 **Batch mode**: run K battles vectorized (K as a numpy axis) for
  Monte-Carlo throughput - this is the performance-critical path (S.8).

### M5 - Goal 2: Outcome predictor (Monte Carlo)
- FR5.1 Input: one fully-specified battle construct + N (default 100K).
- FR5.2 Run N stochastic battles (independent proc RNG per run).
- FR5.3 Output an OUTCOME DISTRIBUTION:
  - P(win) / P(loss) / P(mutual wipe), each with Monte-Carlo std error.
  - Own killed and enemy killed: mean, median, P5/P25/P75/P95, histogram.
  - Survivors per side; net power swing distribution.
  - Expected proc-skill kill contributions (for explainability).
- FR5.4 Convergence report: stop early if CIs are tight enough; warn if
  the outcome is genuinely bimodal (e.g. hinges on one Ambusher proc).
- FR5.5 Surface ENGINE UNCERTAINTY explicitly (the ~10-15% model error is
  separate from MC sampling error) - do not present false precision.

### M6 - Goal 1: Counter-optimizer
- FR6.1 Fix: enemy profile (+ own captain, own troop size, own stat
  panel). Vary: the 4 joiners and the formation split (inf/lan/mar).
  Both search sets are CURATED (owner-confirmed approach), which is what
  makes the search tractable:
  - **Joiner candidate pool**: a user-supplied shortlist (typically 6-10
    heroes you'd actually field; default = the ~20-30 "usable joiner"
    set). Choose-4 from 8 = 70 combos; from 10 = 210.
  - **Formation library**: ~10-15 named "typical" formations
    (60/40/0, 50/30/20, 50/0/50, 40/40/20, ...), owner-editable.
  Search size = C(pool,4) x |formations| ~ 1k-2.5k candidates -> minutes
  with screening MC + racing (see 7.G1). No dedicated solver needed; the
  curated space + budget allocation does it.
- FR6.2 Objective is user-SELECTABLE (confirmed by owner):
  - **Win** - maximize P(win); or
  - **Troop economics** - maximize expected (enemy killed - own killed);
    or
  - **Suicide rally** - maximize expected ENEMY killed (damage dealt),
    IGNORING own survival/win. Real use case: owner's rally is a
    deliberate softener 1-2s ahead of an ally's follow-up rally; the
    objective is to maximize damage on the enemy so the ally cleans up.
    This objective must NOT penalize own losses at all.
  - or maximize P(win) subject to own-loss <= cap; or a weighted blend.
  Default: user picks per run; no silent default (the right objective
  is situational - a suicide rally and a hold are opposite goals).
- FR6.3 Return a RANKED shortlist of (joiners, formation) with objective
  value + CI, and a note on whether #1 is significantly better than #2
  (given MC noise).
- FR6.4 Explainability: WHY the recommendation wins (e.g. "enemy is marks-
  heavy -> your lancer Ambusher bypass + Renee lethality debuff dominates").
- FR6.5 Robust mode (optional): optimize expected/worst-case objective
  over the enemy uncertainty ranges from FR2.4.

### M7 - Interface
- FR7.1 v1 USER-FACING = LOCAL WEB APP (owner-confirmed): profile
  builder (own + enemy, incl. scout-OCR upload), run predictor/optimizer,
  visualize outcome distributions (histograms, P(win), casualty bands)
  and G1 rankings. Runs locally; publishable as a hosted service later.
- FR7.2 A thin CLI / Python API remains the INTERNAL engine interface the
  web app calls (and useful for batch/back-testing).
- FR7.3 Optional Excel bridge (write results into the open workbook) -
  aligns with the existing COM workflow.

---

## 7. Technical approach (the hard parts)

### 7.G2 - Monte Carlo predictor
- Randomness lives ONLY in proc rolls (engine core is deterministic -
  GAME_RULES 6i). So a "run" = deterministic evolution with a fresh proc
  RNG stream. 100K runs = 100K independent streams.
- **Batching**: represent the 100K runs as a leading array axis; step all
  battles together per turn; proc events draw 100K-vectors of uniforms and
  threshold. This turns 100K x ~80 turns into ~80 vectorized turn-steps.
  Compiled inner loop (numpy first; numba/Cython/Rust port if needed).
- Report both MC standard error (1/sqrt(N)) AND engine model error.
- Variance reduction: antithetic variates on proc streams; stratify on the
  highest-leverage proc (e.g. total Ambusher count) so the histogram tails
  are well-sampled.

### 7.G1 - Counter-optimizer
Search space = {4-joiner subset of roster} x {formation simplex}. Naive
C(50,4) ~ 230K x formations x MC each = intractable. Strategy:
1. **Analytic joiner pre-screen**: joiners contribute ONLY their flag S1,
   which is known and enters additively-in-pool. Score each candidate
   hero's marginal S1 value for THIS matchup (attack/DD buffs vs enemy
   wall; enemy-stat debuffs vs enemy dealers). Shortlist top ~8-12.
   (Because same-pool stacking is additive with mild diminishing returns,
   the best-4 is close to the top-4 marginal - but keep a shortlist for
   interaction effects.)
2. **Formation coarse grid**: inf/lan/mar at 10% steps on the simplex
   (~66 valid points), pruned to sensible walls (>=40% infantry etc.).
3. **Racing / successive halving**: evaluate the shortlist x grid with a
   SCREENING budget (1-5K sims each) under COMMON RANDOM NUMBERS (same
   proc seeds across candidates -> low-variance A/B). Cut losers, promote
   survivors to larger budgets, finalists to full 100K.
4. **Statistical gate**: only declare a winner if it beats runner-up
   beyond the paired-CRN confidence interval; otherwise report a tie set.
- Output: ranked table + the significance note + explainability (FR6.4).

### Common infrastructure
- One engine, two entry points (predict vs optimize). CRN + antithetic
  utilities shared. Result records are structured (dataclass/df) so both
  goals aggregate the same primitives.

## 8. Non-functional requirements

| # | Requirement |
|---|-------------|
| NFR1 Performance | G2: 100K sims < ~30s. G1: full search < ~2 min. Needs the batched/compiled core (7.G2). |
| NFR2 Reproducibility | Every run seed-controlled; a (construct, seed, N) triple reproduces exactly. |
| NFR3 Accuracy & honesty | Report engine model error alongside MC error; never present false precision; back-test against known reports and show residuals. |
| NFR4 Extensibility | New heroes/skills/troops (incl. T12), new beasts, new battle types add via catalogs/config, not code forks. |
| NFR5 Auditability | Any prediction can dump its resolved stat layers + a sample battle trace (turn-by-turn) for inspection. |
| NFR6 Portability | Pure-Python core (py 3.14) + numpy; optional compiled kernel; runs offline. |

## 9. Data model - profile JSON (contract)

Mirror/extend reports.py ReconcileSide. Sketch:
```
{
  "schema_version": 1,
  "label": "Enemy - [XXX]Warlord garrison",
  "role": "garrison",                     // rally | garrison
  "context": "rally_vs_garrison",
  "troops_total": 1500000,
  "formation": {"Infantry": 0.60, "Lancer": 0.40, "Marksman": 0.0},
  "per_class": {"Infantry": {"tier": 11, "fc": 10}, ...},
  "stats": {                              // scouted panel OR raw pools
    "mode": "scouted",                    // scouted | pools
    "Infantry|Attack": 31.35, ...         // if scouted (already net)
  },
  "captain": {"heroes": ["Gregory","Fred","Blanchette"],
              "skill_levels": [5,5,5], "widgets": [...]},
  "joiners": [{"flag_hero": "Jessie", "level": 5}, ...x4],
  "specials": [{"source":"item","stat":"Attack","value":0.20,"applies_to":"own"}, ...],
  "uncertainty": {"Infantry|Attack": [30.0, 32.5], ...}   // optional ranges
}
```
- Own profile: same schema, role="rally" (attacker), stats often from
  own scout/own-panel screenshots.
- Save both sides + context to define a full CONSTRUCT (or reference two
  profile files + a context).

## 10. Dependencies & assumptions

- **D1 (critical):** predictions are only as good as the engine. It is at
  ~10-15% today; round 4 + PvP-layer calibration on the 8 reports is a
  PREREQUISITE for trustworthy G1/G2 output. Ship the plumbing in parallel
  but gate "trust the number" on engine acceptance.
- **D2:** rally stat aggregation across joiners is still partly open
  (GAME_RULES 6f note) - controlled farm rallies would close it; until
  then aggregation uses the documented additive-pool assumption.
- **D3:** enemy info is often incomplete - the tool must degrade gracefully
  (ranges, robust mode) rather than demand exact enemy stats.
- **A1:** proc rates and skill parameters are as cataloged (troop_catalog,
  skill book) - already validated.

## 11. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Engine bias propagates to recommendations | Surface uncertainty bands; back-test; keep engine improving; prefer RELATIVE comparisons (G1 ranks candidates under CRN, so shared bias cancels). |
| Combinatorial blow-up in G1 | Analytic joiner pre-screen + racing/successive-halving + formation pruning. |
| Screenshot OCR errors | Identity validation + human-confirm low-confidence cells; manual override always available. |
| MC noise -> unstable recommendations | CRN paired comparisons + significance gating; report ties honestly. |
| Uncertain enemy config | Robust optimization over ranges; report sensitivity to the unknowns. |
| False precision erodes trust | Always pair numbers with error bars and an engine-tolerance caveat. |

## 12. Phasing / roadmap

- **Phase 0 (now):** finish engine round 4 + PvP calibration (ENGINE_PLAN).
- **Phase A:** profile schema + manual enemy/own builder + save/load/list.
- **Phase B:** batched stochastic engine + G2 predictor (single construct
  -> distribution + errors + histograms). Back-test vs 8 PvP reports.
- **Phase C:** G1 optimizer (pre-screen + grid + racing + significance).
- **Phase D:** automated screenshot ingestion for own side (vision + val).
- **Phase E:** UI polish (local UI and/or Excel bridge), robust mode,
  explainability.

## 13. Acceptance criteria

- AC1: A saved enemy profile round-trips (save -> load -> identical
  resolved construct).
- AC2: G2 on any of the 8 known PvP reports produces a distribution whose
  median casualties sit within engine tolerance of the actual result, with
  correct win/loss side.
- AC3: G2 100K sims complete within the NFR1 budget and report both error
  types.
- AC4: G1 returns a ranked shortlist with significance flags and an
  explanation, and its #1 pick beats the naive-meta baseline on >=N test
  matchups.
- AC5: Every recommendation is auditable to its resolved stat layers and a
  sample battle trace.

## 14. Open questions - RESOLVED (owner, 2026-07-04)

- OQ1 RESOLVED: use the workbook as the hero source for now. BACKLOG a
  separate "Hero Info" maintenance module (M8, S.15) as the future
  source of truth for hero stats/skills/cards.
- OQ2 RESOLVED: G1 objective is user-selectable across Win / Troop-
  economics / Suicide-rally (max enemy damage) / capped-win (FR6.2). No
  silent default - the situation dictates the goal.
- OQ3 PARTIAL: owner usually HAS a scouted enemy report (-> OCR, FR2.0),
  so enemy stats are typically known, not guessed. Robust/range mode
  (FR2.4) stays OPTIONAL, for the fields the scout doesn't reveal
  (exact joiners, pets).
- OQ4 RESOLVED: LOCAL WEB APP first; may publish as a hosted service
  later. (Supersedes the CLI-first note in FR7.1 - CLI is the internal
  engine interface; the user-facing v1 is a local web app.)
- OQ5 OPEN (v2): multi-rally / reinforcement timing.

## 15. Backlog (post-v1)

- M8 - Hero Info module: maintained store of hero stats, skills, cards,
  proc params (replaces workbook as source of truth). Feeds G1's joiner
  pool and the stat model.
- Hosted multi-user service (auth, saved profiles per user).
- Multi-rally / reinforcement-timing simulation (OQ5).
- Battle-type coverage beyond rally/garrison in the UI (foundry,
  territory, beasts - engine already supports).
