# Engine Rebuild — Build Spec (turn-by-turn skill-firing PvP engine)

This is the engineering spec. Pair it with `02_TDD_TESTS.md` (build red→green).

New module: **`wos_sim/pvp_turn_engine.py`**. Do not delete `pvp_engine.py`; the new
engine reuses its damage core and can sit beside it during migration.

---

## 1. Design goals (in priority order)

1. **Correctness of casualties** — the per-turn casualty math is the ground truth;
   telemetry is derived from it.
2. **Reproduces the two anchors** — turns, survivor type, survivor count, and trigger
   counts (see `00_HANDOVER.md` §3).
3. **Emits report-shaped telemetry** — `result.skill_telemetry` per `ENGINE_INTERFACE.md` §8.
4. **Honest uncertainty** — near-even variance is represented, not smoothed away.
5. **Interface-compatible** — drops in behind `predict()`; non-mutating; CRN.

---

## 2. Core data structures

```python
# wos_sim/pvp_turn_engine.py
from dataclasses import dataclass, field
from enum import Enum
from wos_sim.models import TroopType   # INFANTRY, LANCER, MARKSMAN

ORDER = [TroopType.INFANTRY, TroopType.LANCER, TroopType.MARKSMAN]  # front -> back

@dataclass
class TypeStack:
    troop: TroopType
    tier: float
    n: float                 # live count (mutated only on local copies)
    n0: float                # starting count (immutable reference)
    astat: dict              # {"Attack":..,"Defense":..,"Lethality":..,"Health":..} effective per-unit stats
    # per-type attack counter for "every N attacks per type" cadence:
    attacks_made: int = 0

@dataclass
class SkillDef:
    owner: str               # hero name, or troop-skill name ("ambusher")
    side: str                # "attacker" | "defender"
    slot: str                # "skill_1"|"skill_2"|"skill_3" (heroes) or "troop"
    role: str                # "captain" | "joiner" | "troop_skill"
    troop: TroopType | None  # captain's class; None for joiners/some troop skills
    category: str            # "OFFENSIVE"|"DEFENSIVE"|"DAMAGE_DEALT"|"DAMAGE_TAKEN"
    amount: float            # fraction (e.g. 1.0 = +100%)
    freq: float | None       # cadence N (None = permanent/passive)
    duration: float | None   # effect duration in turns (None = instantaneous/permanent)
    cadence: str             # "turns" | "attacks_per_type" | "passive"  (derived; see §5)
    is_bypass: bool          # True = damage strikes enemy back line, not front
    bypass_targets: tuple    # e.g. (LANCER, MARKSMAN) for Cara SK3; (MARKSMAN,) for Ambusher
    deals_damage: bool       # True = forms its own damage packet & earns kills
    # runtime accumulators (per simulation run):
    triggers: int = 0
    kills: float = 0.0

@dataclass
class DamagePacket:
    source: SkillDef | str   # a SkillDef, or "auto" for base attack
    magnitude: float         # total damage this packet delivers
    target_mode: str         # "front"  (front-to-back absorb) | "backline"
    target_types: tuple      # ordered types to absorb into (for backline packets)

@dataclass
class TurnRecord:            # one per turn, for QA/debug
    turn: int
    start_counts: dict       # {"attacker": {troop:n}, "defender": {...}}
    packets: list            # DamagePackets fired this turn (both sides)
    casualties: dict         # {"attacker": {troop:killed}, "defender": {...}}
    kills_by_source: dict    # {source_id: killed}   (for conservation check)

@dataclass
class TurnEngineResult:
    winner: str              # "A" | "D" | "draw"
    turns: int
    a_survivors: dict        # {troop: n}
    d_survivors: dict
    a_incap: dict
    d_incap: dict
    skill_telemetry: dict    # ENGINE_INTERFACE.md §8 shape (or None if disabled)
    turn_log: list           # list[TurnRecord]  (kept for QA; UI may ignore)
```

---

## 3. Effective stats and the base damage packet

**Reuse the existing per-strike power formula.** In `pvp_engine._side_damage()` the
core term (see its body, ~lines 90–115) is the atk/def/leth/health ratio ×
tier-power × counter × (1+dd) × (1+dt). Refactor that inner expression into a small
pure function you can call per (attacker type → defender front type):

```python
def base_strike_damage(src: TypeStack, tgt_front: TypeStack, params) -> float:
    """Damage one source type deals into the current enemy FRONT type this turn,
    BEFORE skill packets. Reuses GAME_RULES §6 / pvp_engine formula:
    ~ src.n * atk_power(src) / def_power(tgt_front) * tier_power * counter."""
```

- `astat` (effective per-unit Attack/Def/Leth/Health) is built by the existing Layer 1
  (`construct.build`) exactly as today: `TierBase × (1+panel) × permanent_hero_skill_mult`
  in scouted mode. **Permanent (passive) stat skills are folded here, NOT fired as
  packets** (they have `cadence="passive"`, `deals_damage=False`, and show
  `triggers=1, kills=0` in telemetry — matching the report's blank-kill buff rows).
- Counters: use `COUNTERS` from `pvp_engine.py`.
- T12 troop skills (Indomitable Wall / Meridian / Starfire) enter exactly as today
  via `params["a_t12"]/["d_t12"]` (the `atk_marks_dd`, `def_inf_dt`, `def_enemy_out`
  multipliers in `_side_damage`). Keep that wiring.

The **base packet** for a side each turn = Σ over its alive types of
`base_strike_damage(type, enemy_front_type)`, aggregated. `source="auto"`.

---

## 4. Skill packets and kill attribution (THE core of this rebuild)

### 4.1 Which skills form packets
Load skills via `wos_sim.loader.load_skill_book()` + the routing already in
`predictor/skills.py` (`resolve` → captains full kit, joiners Skill-1). Classify each
resolved effect:

| Skill kind | `cadence` | `deals_damage` | `is_bypass` | Effect |
|---|---|---|---|---|
| Passive stat (OFFENSIVE/DEFENSIVE, `freq=None`) | `passive` | False | False | folded into `astat`; telemetry triggers=1, kills=0 |
| Periodic DAMAGE_DEALT with `freq` (e.g. Vulcanus SK2, Ligeia SK2/SK3) | `turns` or `attacks_per_type` | **True** | False | on trigger turn, adds a damage packet = `amount × K_skill × base_of_owner_type`; earns the kills that packet causes |
| Periodic DEFENSIVE with `freq`+`duration` (e.g. Vulcanus SK3 +60% def) | `turns` | False | False | while active (duration window), scales the OWNER side's def_power (reduces incoming); telemetry triggers counted, kills=0 |
| DAMAGE_TAKEN (e.g. enemy takes +X%) | `turns` or passive | False | False | scales the TARGET side's incoming damage while active |
| **Back-line bypass** — Ambusher troop skill; Cara-SK3-class hero bursts | `turns` (hero) / proc (troop) | **True** | **True** | packet with `target_mode="backline"`, `target_types` per skill; earns back-line kills |

> **Identifying bypass skills.** The skill book does NOT currently flag "bypass". You
> must add a small mapping (config table in `pvp_turn_engine.py`) marking which
> skills strike the back line. Known members from the two reports: **Ambusher**
> (Lancer T7+, targets `(MARKSMAN,)`), **Cara SK3** (targets `(LANCER, MARKSMAN)`).
> Make it a data table `BACKLINE_SKILLS = {...}` keyed by (hero, slot) / troop-skill
> name, so future skills are added without code changes. Document each entry.

### 4.2 Applying packets & attributing kills — strict rule
Per turn, per firing side, assemble the ordered packet list:
`[auto_base] + [each firing damage/​bypass skill packet]`. Then apply against the
enemy's **start-of-turn** stacks:

```
def apply_packets(packets, enemy_stacks):
    # front packets absorb Inf->Lancer->Marksman; backline packets absorb their
    # target_types in order. Each packet consumes health/count; the count it
    # removes IS its attributed kills.
    for pkt in packets:
        order = ORDER if pkt.target_mode == "front" else list(pkt.target_types)
        remaining = pkt.magnitude
        for t in order:
            stack = enemy_stacks[t]
            if stack.n <= 0 or remaining <= 0: continue
            killable = min(stack.n, remaining / cost_per_kill(stack))   # see note
            stack.n -= killable
            record_kill(pkt.source, killable)     # <-- telemetry = real casualties
            remaining -= killable * cost_per_kill(stack)
```

- **`cost_per_kill(stack)`** converts damage→casualties. Simplest defensible model:
  casualties = damage / effective_health(stack) where effective_health uses the
  target's Health/Defense `astat` (reuse whatever the current engine effectively
  does — see `_apply` in `pvp_engine.py`, which currently treats `dmg` as a direct
  count; if the current unit of "damage" is already "troops incapacitated", then
  `cost_per_kill = 1` and packet magnitude is in troop units). **Match the existing
  damage unit so calibration transfers.** Decide this explicitly and write it in a
  comment; the tests assume "packet magnitude is in incapacitated-troop units"
  unless you document otherwise.
- **Simultaneity:** compute BOTH sides' packet lists from the same start-of-turn
  snapshot, then apply both, then commit. Do not let side A's casualties this turn
  reduce side A's own outgoing damage this turn.
- **Conservation (mandatory):** after both sides resolve, for each side
  `Σ_source record_kill == Σ_type (start_n - end_n)` for the enemy it hit. Assert it.

### 4.3 Why this satisfies "kills must contribute to the result"
Because casualties ARE the packet applications, a skill that fires more (or with
bigger magnitude) removes more enemy troops, which (a) shortens the battle, (b)
changes which type collapses first, and (c) changes the survivor. The reported
`kills` for a skill is literally the sum of `record_kill(that_skill, …)` across the
battle. There is no second code path. **If you find yourself computing telemetry
anywhere other than inside `apply_packets`, stop — that's the failure mode.**

---

## 5. Cadence & trigger counting

Derive `cadence` and evaluate firing per turn `t` (1-indexed):

- `passive`: never "fires" as a packet; telemetry `triggers = 1` if present.
- `turns` (freq=N): fires when the owner's driving type is alive and the turn matches
  the skill's schedule. **Phase convention differs by skill and must be calibrated to
  the oracle** (see below). Provide a per-skill `start_turn` (default 1) so both
  observed conventions are expressible:
  - Vulcanus SK3 (N=3) fired at turns 1,4,7,… → `start_turn=1`,
    count `= floor((life-1)/N)+1`. Oracle: B1=6 (life16), B2=9 (life25). ✓
  - Cara SK3 (N=2) fired at turns 2,4,…,life → `start_turn=2`,
    count `= floor(life/N)`. Oracle: B1=6 (enemy-marks life 12), B2=9 (life 18). ✓
  - Elif SK3 fires every turn → `N=1`, count `= life`. Oracle: B1 his=12, enemy=15; B2 his=19, enemy=22. ✓
- `attacks_per_type` (freq=N, e.g. Vulcanus SK2): maintain `attacks_made` per TYPE
  (+1 each turn the type is alive & acts). Fire once each time any type crosses a
  multiple of N. Count `= Σ_type floor(type_life/N)`.
  Oracle: B1 inf floor(12/5)=2 + lancer floor(14/5)=2 + marks floor(16/5)=3 = 7. ✓
  B2 inf floor(19/5)=3 + lancer floor(25/5)=5 + marks floor(14/5)=2 = 10. ✓

**These trigger formulas are hard test oracles** (see `02_TDD_TESTS.md`). The engine
does not hard-code them — they must EMERGE from the simulated death schedule. The
formulas are how the tests check the emergent counts.

---

## 6. The turn loop (reference pseudocode)

```python
def simulate_turns(a_stacks, d_stacks, skills, params, rng, max_turns=60):
    log = []
    for t in range(1, max_turns + 1):
        start = snapshot(a_stacks, d_stacks)
        a_fire = [s for s in skills if s.side=="attacker" and fires_this_turn(s, t, a_stacks)]
        d_fire = [s for s in skills if s.side=="defender" and fires_this_turn(s, t, d_stacks)]
        for s in a_fire + d_fire: s.triggers += 1

        a_packets = build_packets("attacker", a_stacks, d_stacks, a_fire, params, rng)
        d_packets = build_packets("defender", d_stacks, a_stacks, d_fire, params, rng)

        # simultaneous: apply against snapshots, then commit
        cas_d = apply_packets(a_packets, d_stacks)   # attacker hits defender
        cas_a = apply_packets(d_packets, a_stacks)   # defender hits attacker

        for st in a_stacks + d_stacks:
            if st.n > 0: st.attacks_made += 1        # for attacks_per_type cadence

        assert_conservation(a_packets, cas_d); assert_conservation(d_packets, cas_a)
        log.append(TurnRecord(t, start, a_packets + d_packets, {"attacker":cas_a,"defender":cas_d}, ...))

        if total(d_stacks) <= EPS or total(a_stacks) <= EPS:
            break
    return build_result(a_stacks, d_stacks, skills, log, t)
```

- **RNG / CRN:** damage may carry per-turn multiplicative noise for the stochastic
  batch. The RNG stream must depend only on `(seed, run_index)` — reuse the
  `_run_rng(seed, i)` pattern already in `predictor/kernel.py`. A deterministic run
  (noise off / fixed seed) is what the anchor tests use.
- **Non-mutating:** operate on deep copies of the constructed units; never mutate the
  caller's `ConstructedMatchup`. (`predictor/kernel.py` already has `_replicate` for
  this discipline — follow it.)

---

## 7. Output & interface

- Wrap `TurnEngineResult` into the record stream `predictor/summary.summarize`
  consumes (winner, survivors, incap per troop). Keep `predict()` and its return type
  stable.
- Populate `result.skill_telemetry` per `ENGINE_INTERFACE.md` §8 from the per-`SkillDef`
  `triggers` / `kills` accumulators, **averaged over the stochastic batch**, grouped
  attacker/defender → heroes[] / troop_skills[].
- `engine_meta` (see `predictor/kernel.py::engine_meta`): when this engine runs,
  return `path="pvp_turn_engine"`, plus a **confidence** field:
  - `calibrated=True` only once QA passes both anchors.
  - Add `near_even: bool` and `confidence: "validated"|"directional"|"coin_flip"`.
    Compute `near_even` by a cheap symmetry/parity check (e.g. re-run with defender
    effective strength ±2%; if the winner flips or survivor% moves by >X, mark
    `coin_flip`). Surface `model_error` accordingly (small when decisive, large/None
    when coin_flip). **Do not emit a confident point survivor% for a coin_flip.**

---

## 8. Calibration knobs (what the QA/fitting pass will tune)

Keep ALL of these as named `params` (defaults in a `TURN_PARAMS` dict), so the QA
agent can fit without editing code:

| Knob | Sets | Start |
|---|---|---|
| `rate` (base damage scale) | battle length / turn count | reuse current ~80–168 range |
| `K_skill` (per-category or per-skill packet multiplier) | how hard damage-skills hit → non-linear attrition depth | 1.0 |
| `ambush_frac` / `ambush_proc` | how fast enemy Ambusher guts your marksman | tune to B2 marks die ~T14 |
| `cara_burst` (back-line burst magnitude) | back-line kill rate of Cara-class skills | tune to B1 marks chip ~690→580 & B2 marks death |
| counter multiplier `cm` | exchange ratios / who-survives | reuse current |

**Fitting is joint across BOTH anchors with one parameter set.** If no single set
hits both, that is a reportable finding (see `03_QA_CALIBRATION.md`) — not a licence
to overfit one.

---

## 9. Migration / integration checklist

1. Build `pvp_turn_engine.py` with the structures above; unit-test in isolation.
2. Add a `BACKLINE_SKILLS` config table + a `skill_defs_from_matchup(con)` adapter
   that turns `construct.build` output + `load_skill_book` into `list[SkillDef]`.
3. Route `predictor/kernel.py` to the new engine (feature-flag `params["engine"]="turn"`
   first; flip default once QA passes). Keep `_replicate`, `_run_rng`, `engine_meta`.
4. Populate `skill_telemetry`; wire through `summary`/`api` unchanged otherwise.
5. Extend `regression.py` with the anchor + conservation checks.
6. Hand to QA agent (`03_QA_CALIBRATION.md`).
