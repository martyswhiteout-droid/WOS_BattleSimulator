# Stage 8.3 spec — the integration engine: hero/troop intents ON the first-principles law

**Status:** proposed 2026-07-25, after the hero design layer passed QA (`hero_kit.py` +
`hero_roster.py` + `HERO_TEST_CASES.md`). This spec is the **bridge**: it defines how the
QA-approved effect *intents* combine with the frozen Stage-6 per-unit law and the (pending)
Stage-8.1 composition law to compute an army-scale battle — the thing that finally makes the
hero layer live and lets the app retire the `def_k` turn engine for covered battles.

This is the DESIGN. It is written to be buildable, but it **depends on** two things that do
not exist yet and are called out as inputs, not assumed done:
- **8.0 army-scale ground truth** — the only legitimate validation targets (no-fudge rule).
- **8.1/8.2 composition + scale + role law** — the deterministic backbone below the procs.
Where those are missing, 8.3 defines the seam and the contract; it does not invent their numbers.

---

## 0. What 8.3 is and is NOT
- **IS:** the resolver that (a) turns each side's heroes+troop-skills into per-attack-event
  effects, (b) applies them to the law's damage computation in a fixed, deterministic order,
  (c) Monte-Carlos the chance procs (CRN) into kill-turn / survivor / winner DISTRIBUTIONS.
- **IS NOT:** a new damage formula. The base damage is the Stage-6 law
  `turns = K·(D·H)/(A·L)·G_w·G_l/√N` (HP=D·H); 8.3 only *modifies its inputs and outputs*
  via intents. It also does not re-derive composition (8.1) or the role effect (8.2).

## 1. Battle model (the loop the intents plug into)
Per GAME_RULES §4 (authoritative), the loop is:
- **Turn-based, SIMULTANEOUS.** Each turn both sides compute damage from the SAME
  start-of-turn counts; casualties are removed together at turn END (next turn only).
- **Per turn, each surviving class on each side makes one attack event**, in absorption
  order **Infantry → Lancer → Marksman** (Ambusher: Lancer 20% strikes Marksmen directly).
- **Two counters the hero layer already consumes** (`BattleView`): `attack_no` = global
  own-side attack-event counter ("Attacks"); `strike_no` = the attacking class's own strike
  counter ("Strikes"). 8.3 is responsible for maintaining BOTH per side and passing the
  correct `attacker_class` on each event.
- **Absorption/composition** (from 8.1): attacks hit the front class until it dies, then the
  next; the composition law sets tank life and backline mop-up. 8.3 calls 8.1 for the
  base per-turn casualty; intents scale it.

## 2. Effect-intent → law application (the core contract)
Each turn, for each attacking-class event, 8.3 gathers the active effects (resolve() over all
of that side's captains' 3 skills + joiners' 1 skill + troop skills) and applies them to that
event's damage. Mapping, by primitive:

| Intent | How it modifies the law |
|---|---|
| `StatMod(side, target, stat, v)` | Adjusts the **effective stat** feeding A·L/(D·H) for the targeted troops. **Composition rule (GAME_RULES §6l, R4):** DISTINCT hero skills compose **multiplicatively** `Π(1+vᵢ)`; **DUPLICATE copies of the same joiner skill** compose **ADDITIVELY** `(1+Σv)`. Buff/debuff items net first (§2). Applied BEFORE the law computes damage. |
| `DamageMod(side, TARGET_or_class, DEALT/TAKEN, v, category, vs_class)` | Multiplies the event's damage. `DEALT` scales the attacker's output, `TAKEN` scales the victim's intake. `category` gates Normal/Skills/Both. `vs_class` applies the bonus ONLY when the struck defender is that class (not cumulatively). |
| `Crit(target, rate)` | On each attack event, with probability `rate` the event deals +100% damage. A stochastic proc (§4), CRN-rolled. |
| `Shield(target, scale_stat, pct, dur)` | An **absorb pool** = `unit[scale_stat]·pct`, placed IN FRONT of the target's HP (=D·H). Incoming damage depletes the shield first, then HP; the pool refreshes per its trigger and expires after `dur` turns. This is the mechanic the flat model could not express (Gatot/Elif) — 8.3 owns the absorb ledger. |
| `ExtraAttack(target, damage_pct)` | Inserts an ADDED attack event for that class dealing `damage_pct`× a normal attack. Like Volley: it advances the counters and RE-ROLLS procs for the extra event (so cadence/chance effects can fire on it). |
| `DecayingDamage(side, target, start, decay, N)` | A `DEALT` boost that decays each of the class's next `N` strikes: strike k gets `start·decay^(k-1)`. 8.3 tracks the per-unit window (Hector). |
| **`Target.TARGET` scaling (Martin 2026-07-25 / §3 Received)** | A `TARGET`-scoped debuff lands ONLY on the units actually struck this event — count = (attacking units that landed) × hits, NOT the whole class. 8.3 computes the struck count from the attacker headcount and applies the debuff to that many defenders (the rest of the class are unaffected). `Target.FRONTLINE` (whole class) is the class-wide case. |

## 3. Order of operations per attack event (deterministic, fixed)
1. Resolve `attacker_class`, `attack_no`, `strike_no` for the event.
2. **Compose stats** for both sides: base × (1+panel) × item-net × [Π distinct-skill, Σ duplicate-skill] (§2/§6l/R4). Auras (hero Expedition stat block, class-locked) are already in the captured panels.
3. **Base damage** for the event from the Stage-6 law (via 8.1 composition for the live front/back state): `dmg = f(A·L/(D·H), K, G_w, G_l, √N)`.
4. **Roll procs** (CRN) for this event: hero `ChanceProc`/`ScaledChance` (class-eligibility BEFORE the roll — already enforced in `resolve()`), `Crit`, troop skills (Crystal Lance/Gunpowder/Volley/Ambusher/Crystal Shield). Class-gated cadences use `strike_no`.
5. **Apply DEALT mults** (hero DamageMod DEALT + DecayingDamage + crit + troop DD), category-scoped, `vs_class`-gated by the struck defender.
6. **Resolve the struck target(s)** (absorption order, struck count for TARGET effects).
7. **Apply TAKEN mults + Shield absorption** on the victim: subtract from the shield pool first, then convert remaining to casualties via HP=D·H.
8. **Insert ExtraAttack events** (loop back to step 4 for the added strike).
9. **Arm deferred effects** for the NEXT event/turn (Vulcanus target-DT on the attack after the proc; Renee marks; stacking ramps) — see §5.
10. Accumulate casualties; at TURN end remove them for both sides simultaneously.

## 4. The stochastic layer (this is Stage 7 Phase B)
- All chance-based effects (hero ChanceProc/ScaledChance/Crit + troop procs) are rolled per
  event against a **CRN-seeded** RNG (seed = base_seed + run_index), so a run is reproducible
  and the app can replay any single battle. The hero layer's `resolve()` is already CRN-safe
  (wrong-class skills never touch the stream — QA round 3).
- A prediction is **N Monte-Carlo runs** → distributions of kill-turn, survivor%, and winner.
  **This is where the real win-rate emerges** (some runs won, some lost) — replacing the
  turn engine's fixed 1/0-plus-heuristic. `winprob.py`'s fabricated 0.5±0.05 is bypassed for
  covered battles.
- **Validation is DISTRIBUTION-ONLY (no-fudge, binding):** observed proc trigger counts vs
  binomial (the Stage-7A telemetry gates G-T1..G-T5), and observed real outcomes vs the
  predicted distribution. Never regression-fit a Type-2 row.

## 5. Stateful / deferred mechanics (the active-effect ledger 8.3 must own)
The hero layer emits these as intents but cannot resolve their timing statelessly; 8.3 keeps a
per-side ledger keyed by (source, expiry):
- **Deferred coupling:** Vulcanus target-DT on the attack AFTER the every-6 proc (already an
  offset cadence; the ledger enforces arm-on-6 / consume-on-7 precisely at army scale).
- **Marks/conditionals:** Renee Dream-Marks (place → consume next turn).
- **Stacking-until-end:** Lynn's +Attack ramp accumulates, does not refresh.
- **Attack-pause / bypass:** Ahmose pause (skip the class's own attack), Cara/Ambusher backline
  bypass (targeting change). These were explicitly deferred here from the hero layer.

## 6. Roles, joiners, widgets (GAME_RULES §3 — 8.3 enforces)
- **Captain** heroes fire all 3 skills + their widget (context-gated garrison/rally — already
  in the turn engine, R3). **Joiners** fire ONLY their slot-1 skill; cap 4; duplicates additive.
  8.3 selects which skills to resolve per hero role — the hero classes declare all 3; the
  engine gates by role. (The hero `resolve()` is role-agnostic by design.)
- **Auras** = the hero's Expedition stat block, class-locked, already captured in per-battle
  panels; 8.3 must not double-count them.

## 7. Seam / app wiring (additive; standing rules)
- New engine path behind `api.py` only (server.py untouched). `predict()` gains an
  `engine="army_law"` branch that runs this resolver; `engine_path="army_law"`,
  `stochastic=True`, real `p_win` from the run frequency, honest confidence. The Round-15
  honesty banner self-suppresses (path ≠ turn engine).
- **Router (8.4)** decides when a battle is covered (opens gates as 8.1/8.2/8.3 validate).
- **Gates:** `py -m wos_sim.backtest` (G12) must hold/rise; the golden T12 profiles must keep
  routing to whichever engine is validated for them; full predictor suite green.

## 8. Guardrails (inherit, binding)
No fabrication; no regression/best-fit; observed outcomes never inputs; ambiguity → branch;
Type-2 distribution-only; engine reached only through `api.py`; nothing enters WOSTests.com
until PRODUCTION_CRITERIA passes.

## 9. Dependencies & open items (honest)
- **BLOCKED ON 8.0 data** for validation — the whole stochastic gate (§4) needs the army
  battery; without it 8.3 can be BUILT but not VALIDATED (and must not be fit).
- **Needs 8.1/8.2** for the base composition + role law (8.3 calls them; it does not define them).
- **R4-real** (duplicate-same-skill additivity) is a live-engine fix; §2's composition rule
  here assumes it is done.
- **Strike interval 5-vs-6** for non-Vulcanus "every 5" heroes (R6) — unmeasured; a one-battle
  8.0 experiment settles it before those cadences are trusted at army scale.

*Next action if approved: this spec is the target for `/run-stage 8.3` once 8.0 data + the 8.1
composition law exist. Until then it defines the contract the composition work (8.1) builds toward.*
