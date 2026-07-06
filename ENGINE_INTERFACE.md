# Engine ⇄ Predictor Interface Contract

**Audience:** the engine-builder agent.
**Goal:** define EXACTLY what the battle engine must accept and return so the
already-built predictor app layer (`wos_sim/predictor/`) works with the real
stochastic + batched engine **with zero upstream changes**.

The predictor calls the engine through one seam — `wos_sim/predictor/kernel.py`.
Get this contract right and the real engine is a **drop-in** behind that seam;
`construct.py` (Layer 1), `summary.py` (Layer 2), and `api.py` never change.

---

## 0. Where you plug in

Today (`wos_sim/predictor/kernel.py`):
- `StubKernel.run(attacker_units, defender_units, rng, params)` calls
  `wos_sim.pvp_engine.simulate_pvp(a_units, d_units, params)` for ONE battle and
  builds a `RunRecord` from the returned `PvpResult`.
- `run_batch(construct, n, seed, kernel, params)` loops that `n` times with one
  seeded RNG.

You replace `StubKernel` (or supply a `BatchKernel`) that exposes the **batched
entry** in §3. Everything above `kernel.py` is frozen.

---

## 1. INPUT — `Unit` (already fully resolved by Layer 1)

Each side is a `list[Unit]` (`wos_sim.pvp_engine.Unit`). Layer 1 has already
applied the entire stat model, so **do not re-apply panels/buffs/penalties**.

| field | type | semantics |
|---|---|---|
| `troop` | `TroopType` | `INFANTRY` / `LANCER` / `MARKSMAN` |
| `tier` | `float` | May be **fractional** (10.5, 11.5). Feed to `interpolated_tier_power` (float-safe) and the Ambusher gate (`tier >= 7`). |
| `n` | `float` | Starting troop count for this class. |
| `astat` | `dict{StatType: float}` | **Absolute effective** A/D/L/H (panel × buffs ÷ enemy penalties already baked in). |
| `base_atk` | `float` | Buff-independent base tier attack (armor penetration term). |
| `dd` | `float` | Damage-dealt bonus (own output), default `0.0`. |
| `dt` | `float` | Damage-taken bonus (incoming amplification), default `0.0`. |

- **List A = attacker (rally); List D = defender (garrison).** Layer 1 assigns
  this by role; the engine just treats A as attacker and D as defender (as
  `simulate_pvp` does today).
- **MUST NOT mutate the input lists.** Today `simulate_pvp` decrements `u.n` /
  accumulates `u.incap` in place. The batched kernel runs `n` battles on the
  **same** construct unit objects, so each battle must operate on a **fresh copy**
  — mutating shared inputs corrupts every subsequent run.

### T12 stacking — per-class, via `params` (already implemented ✅)

Per-class T12 tier-3 skill levels are **not `Unit` fields**; they ride in
`params` as `a_t12` / `d_t12` (each side's OWN levels):

```python
params["a_t12"] = {"indomitable_wall": <Infantry level 0-24>,   # Indomitable Wall
                   "meridian_phalanx": <Lancer   level 0-24>,   # Meridian Phalanx
                   "starfire":         <Marksman level 0-24>}   # Starfire  (None = no T12)
```

Layer 1 (`construct.build`) derives these from each class's `t12_stack` slider,
**gated on Tier 12**, and the facade merges them into `params`. The engine
(`wos_sim/t12.py`) applies the battle-start 5-turn windows + Starfire's every-5-turn
ramp + the clamp-24, per **GAME_RULES 6e**. Wired end-to-end (predictor test
`TestT12Params`).

---

## 2. PER-RUN OUTPUT — the record `summary.py` consumes

For ONE stochastic battle, return **at minimum** these fields (read by name in
`summary.py`; keys are the `TroopType` enum, **not** strings):

| field | type | semantics |
|---|---|---|
| `winner` | `str` | `'A'` (attacker) \| `'D'` (defender) \| `'mutual'` (both wiped same turn). The predictor maps A/D→own/enemy and counts **`'mutual'` as the ATTACKER's win**. |
| `turns` | `int` | Rounds to resolve. Bounded — see non-termination below. |
| `attacker_start` | `dict{TroopType: float}` | Per-class starting count (attacker). |
| `defender_start` | `dict{TroopType: float}` | Per-class starting count (defender). |
| `attacker_incap` | `dict{TroopType: float}` | Per-class incapacitated (attacker). **survivors = start − incap.** |
| `defender_incap` | `dict{TroopType: float}` | Per-class incapacitated (defender). |

Every class present in a side's `*_start` MUST also appear in `*_incap` (0 if
none lost). Today's `PvpResult` already gives `winner`, `turns`, `a_incap`,
`d_incap`; the batched kernel must **additionally** surface per-class **start**
counts (`*_start`) — trivial (the input units' `n` before the battle).

### Additions the BRD/ROADMAP require (return as they land; the app will consume them):
- `proc_contributions: dict{skill_name: float}` — kills attributed per proc skill
  (BRD FR5.3 explainability). Per-run or aggregated across the batch.
- **Severe/light split** — the game's "losses" = the **severe** bucket (~35%
  fortress, 30% foundry, etc.). Either return per-class `severe` counts, **or**
  document that you return raw `incap` and the app applies the structure-type
  split. **State which.** (ROADMAP E-11)
- **Sample trace** — for one representative run, an optional turn-by-turn log for
  auditability (BRD NFR5).

---

## 3. BATCHED ENTRY — "what to return when the engine is called"

The predictor needs `n` battles efficiently (default **10,000**; up to
**100,000 in < 30 s** → vectorized, ROADMAP E-6).

Drop-in signature (what `kernel.run_batch` will call):

```python
def run_batch(attacker_units, defender_units, *,
              n: int, seed: int, params: dict | None = None,
              antithetic: bool = False) -> BatchResult
```

- `n` — number of battles.
- `seed` — RNG seed. `(units, seed, n)` **must reproduce byte-identical results**
  (NFR2).
- `params` — engine params (default `farm_engine.BEST_PARAMS` + `rate`).
- `antithetic` — antithetic variates on proc streams for variance reduction.

`BatchResult` must make the **per-run fields in §2 recoverable** — either:
- a `list[RunRecord]` (simplest; exactly the shape below), **or**
- column arrays (`winner[n]`, `turns[n]`, per-class `start`/`incap` arrays) that
  the kernel adapter reshapes into what `summary.py` reads.

Also expose (optional now, consumed as available):
- `engine_model_error: float` (~0.10–0.15) — reported **separately** from MC
  sampling error (NFR3). The app surfaces the two distinctly.
- `converged: bool` / `ci_width: float` — convergence signal for early-stop
  (BRD FR5.4).

---

## 4. DETERMINISM & Common Random Numbers (CRN)

- **Reproducible:** `(units, seed, n)` → identical batch, always.
- **Per-run independence:** each of the `n` battles draws from an independent
  stream derived from `seed` (e.g. `SeedSequence(seed).spawn(n)` or `seed + i`).
- **CRN (critical for the optimizer):** the per-run stream for run `i` must depend
  **only on `(seed, i)` — NOT on the units.** The optimizer runs many candidate
  configs and compares them; running candidate A and candidate B under the same
  `seed` must give them the **same proc draws**, so the difference is the
  candidates, not luck. This underpins the paired-comparison + significance
  gating in ROADMAP G1.

---

## 5. Proc scheduler (ROADMAP E-5) — the only randomness

The deterministic core is fixed (GAME_RULES 6i); **randomness lives only in proc
rolls.** Seeded Bernoulli / "again" rolls for: Ambusher `0.20`, Crystal Lance
`0.10/0.15`, Crystal Shield offset, gun double-damage, and hero proc skills with
their `TriggerUnit` cadence. Requirements:
- Mean over `n` runs matches the deterministic EV path.
- Run-to-run casualty spread ≈ **13–16%** (observed on repeat farm runs).
- Must pass the **E-10 regression harness** (deterministic ±1; stochastic
  1000-seed envelopes vs the ~150 stored battles).

---

## 6. Drop-in checklist

- [ ] Accepts two `list[Unit]` (attacker, defender), as `simulate_pvp` does today.
- [ ] **Never mutates** the input lists (fresh copy per battle).
- [ ] Per-run returns `winner∈{A,D,mutual}`, `turns`, and `attacker/defender`
      `start` & `incap` dicts keyed by `TroopType`.
- [ ] Non-terminating battle → **bounded** `turns` (`max_turns`) with a defined
      winner rule; **document the value returned** and how it's classified.
- [ ] `run_batch(units, *, n, seed, params, antithetic)` — reproducible,
      per-run-independent, **CRN-capable** streams.
- [ ] 100K runs in < 30 s (vectorized).
- [ ] (When ready) `proc_contributions`, severe/light split, `engine_model_error`,
      convergence signal.

---

## Appendix — the exact record the app builds today

From `wos_sim/predictor/kernel.py`. If your batched engine yields exactly this per
run, the seam swap is **one line**:

```python
@dataclass
class RunRecord:
    winner: str            # 'A' | 'D' | 'mutual'
    turns: int
    attacker_start: dict   # {TroopType: count}
    defender_start: dict
    attacker_incap: dict   # {TroopType: incapacitated}
    defender_incap: dict
```

**Worked example (one returned record):**

```python
RunRecord(
    winner='A', turns=34,
    attacker_start={INFANTRY: 810_000, LANCER: 324_000, MARKSMAN: 486_000},
    defender_start={INFANTRY: 900_000, LANCER: 600_000},
    attacker_incap={INFANTRY: 138_000, LANCER:  0,      MARKSMAN:  27_000},
    defender_incap={INFANTRY: 900_000, LANCER: 600_000},   # defender wiped -> attacker win
)
# summary.py reads: winner->own/enemy + mutual rule; turns->rounds chart;
# survivors = start - incap -> outcome-quality bucket + loss-% distributions.
```

> Note on today's engine: `simulate_pvp` is deterministic and returns
> `PvpResult(winner, turns, a_incap, d_incap, a_total0, d_total0)` and **mutates**
> its inputs. The two gaps to close are (1) the **proc scheduler** (§5, makes it
> stochastic) and (2) the **batched, non-mutating** entry (§3) — everything else
> the app needs is already derivable from `PvpResult` + the input `Unit` counts.

---

## Implementation status — engine agent, 2026-07-04

**Wired behind the seam (`wos_sim/predictor/kernel.py`), no upstream changes.**
The default kernel is now the real stochastic engine — `api.predict` works as-is.

| Requirement | Status |
|---|---|
| Accept two `list[Unit]`, treat A=attacker/D=defender | ✅ (`BatchKernel`) |
| **Never mutate inputs** | ✅ `simulate_stoch` clones per battle; verified `u.n`/`u.incap` unchanged after a batch |
| Per-run `winner`/`turns`/per-class `*_start`+`*_incap` (TroopType keys) | ✅ every started class appears in `*_incap` (0 if untouched) |
| Non-terminating → bounded `turns` | ✅ `max_turns=4000`; if hit, winner = side with more troops (see `proc.simulate_stoch`) |
| `run_batch` reproducible `(units,seed,n)` → identical | ✅ |
| Per-run independent streams | ✅ `_run_rng(seed,i)` |
| **CRN** (stream = f(seed,i) only, NOT units) | ✅ **fixed a gap**: the old `run_batch` used one shared RNG (stream depended on prior runs' battle lengths → units). Now each run i seeds from `(seed,i)` only, so paired optimizer comparisons share draws |
| Real proc scheduler (§5): Ambusher 0.20, Crystal Lance | ✅ (via `wos_sim/proc.py`); hooks left for Crystal Shield / gun / hero procs |
| Mean over n ≈ deterministic EV | ✅ regression-guarded |
| 100K runs < 30 s | ⚠️ **params-dependent** (QA 2026-07-04). ~13 s for a proc matchup under the **default** calibration (battles resolve in a few turns); deterministic (no-proc) matchups short-circuit to one sim → instant. But a low-`rate` / long-turn stochastic fight is a pure-Python per-turn loop and does **not** meet 30 s (measured ~40 s for 5K → ~800 s for 100 K). The <30 s guarantee holds for the app's default n=10 K and default params; the universal 100 K guarantee needs **vectorization (E-6)**. |
| `run_batch(construct, n, seed, kernel, params)` signature | ✅ unchanged; also added `run_batch_units(a,d,*,n,seed,params,antithetic)` (§3 units entry for the optimizer) |

**Params default:** the seam injects `DEFAULT_PVP_PARAMS = {rate:320, def_k:1000, def_ed:0.483}` (the r6/r8 calibration) when the app passes `params=None` — `rate=1.0` would be meaningless. Any caller `params` override wins.

**Two honest caveats the app should surface, not hide:**
1. **Magnitude is weakly calibrated.** The stat-based engine is fit only on the r6/r8 whale pair (4/8 reports) — structurally sound, magnitude uncertain. That is exactly what `engine_model_error (~0.13)` is for; if anything it *understates* the whale-regime uncertainty. The separately-**validated** farm kernel (`wos_sim/pvp_kernel.py`, CV ~4%) is the high-confidence path for the **50/50 attacker-wins-full-wipe** regime — consider calling it directly when the matchup is in that box.
2. **Proc-variance magnitude is NOT yet calibrated.** The spread is real but its size depends on the whole-stack Ambusher model, which has no repeat-battle calibration data yet. Near-even matchups show large spread (~45% p5–p95) because a symmetric fight is maximally proc-sensitive; the "13–16%" target was for stable farm wipes. Treat the *distribution width* as provisional until proc-repeat data lands.

**Deferred (return as they land, per §2/§3):** `proc_contributions`, per-class `severe` split (engine returns **raw total `incap`** = severe+light; the **app applies the structure-type split** — stated per §2), sample turn-by-turn trace, `converged`/`ci_width`, and true `antithetic` (accepted as a documented no-op for now — E-6).

---

## Hero generation → stats (E-12) — ✅ NOW WIRED into `construct.build`

**Update 2026-07-05:** the relayer is now called **inside `construct.build`** automatically — you do NOT need to call it yourself. In the **pre-assumed symmetric** case (`own.panel == enemy.panel` and `stats_mode == "scouted"`), the engine strips the assumed highest-gen hero from the scouted panel and re-applies each side's actual per-class lead-hero generation, from `lead_heroes`. Verified: own infantry lead Gisela(Gen13)→P(win) 1.00, Flint(Gen2)→0.00.

**🚨 CRITICAL — send the FULL SCOUTED panel, not base.** The relayer *strips* the baked-in hero, so it needs the hero to be present. If you send a **base** panel (like `60_30_10_Vulcanus_1.json`, which sends `Infantry|Attack: 10.96` = the workbook "Base Stats"), stripping a Gen-13 hero that isn't there **underflows to negative garbage**. The engine now clamps that to base-tier so it won't crash, but the result is wrong. Per the confirmed contract: `panel` = **full scouted**, `stats_mode` always `"scouted"`, base is derived by the engine. Fix the payload to send scouted.

Hero **generation** affects a lead hero's **stat** contribution only, never **skills**. The table + relayer live in **`wos_sim/hero_stats.py`** (still callable directly if needed):

- `relayer_by_names(panel, lead_heroes, *, buffs=None) -> panel` — **pass your `lead_heroes` dict verbatim** (`{"Infantry": "Gregory", "Lancer": "Renee", "Marksman": "Blanchette"}`). The engine resolves each name → generation (static `data/hero_generations.json`, 51 heroes; needs no workbook) and re-layers. SR/legacy leads and unknown names are dropped (no lead-stat contribution). *(Also available: `hero_stat(gen, stat)`, `hero_generation(name)`, `class_gens_from_names(lead_heroes)`, and the gen-based `relayer_panel(panel, class_gens, ...)`.)*

**When to call it (your `construct.build`, Layer 1):**
- **Pre-assumed symmetric** matchup (you supplied *identical* stats on both sides): the supplied panel bakes in the user's highest-gen hero across all classes. Before building units:
  ```python
  panel = hero_stats.relayer_by_names(panel, lead_heroes, buffs=per_stat_buffs)
  ```
  `per_stat_buffs = {stat: fraction}` is the item/pet buff per stat — the hero enters *inside* the buff multiplier (`Scouted=(Base+Heroes+Gear)*(1+Buff)+Buff`), so it matters (Attack moved +748% vs Defense +650% purely from the 0.15 attack buff). Omit → treated as 0, a slight under-count on buffed stats.
- **Different real stats on the two sides**: the user gave *actual* scouted stats — **pass them through unchanged, do NOT relayer**.
- **Joiners are skills-only** — do NOT feed `joiners` into the relayer; only the 3 `lead_heroes` contribute stats.

The engine's `assemble.py` (report replay) is unchanged — a scouted panel there already includes the heroes. Only the predictor's hero-swap path needs the relayer. Note: **Greg** (gen3 Marksman) ≠ **Gregory** (gen10 Infantry) — the resolver distinguishes them, so pass the exact names your UI uses.

---

## 7. Front-end Final Stats panel contract (predictor UI 2026-07-06)

The browser now sends the **Final Stats** panel to `/api/predict`, not the
editable Input Stats Assumptions panel. In Base mode the browser computes:

```text
pre-buff panel = input base stats + selected lead-hero generation stats
               + enabled Max Gears for that troop class
Final panel    = (1 + pre-buff panel)
               x (1 + active item/pet buffs + active captain widgets)
               / (1 + enemy penalties)
               - 1
```

In Scouted mode the Final panel is an exact mirror of the user's input panel.
Max Gears is a UI-only Base-mode assumption. When checked for a troop class, it
adds `+200% Attack`, `+200% Defense`, `+600% Lethality`, and `+600% Health` to
that class before special buffs are applied. Widget stat rows are **not** added
to the pre-buff panel; they are part of the multiplicative special pool with
item/pet buffs, matching `GAME_RULES.md` section 2 / 6h.
Either way, the JSON profile sent by the browser has:

```python
profile["stats_mode"] = "scouted"
profile["panel_is_final"] = True
profile["widgets_in_panel"] = True
profile["own_buffs"] = {}
profile["debuffs_on_enemy"] = {}
```

So the engine must treat `profile.panel` as the effective stat panel for the
side. Do **not** re-apply input stats, raw buff controls, or widget stat rows on
top of this browser payload. The predictor keeps the older symmetric-scouted
relayer for legacy callers only; it is bypassed when `panel_is_final=True`.
`panel_is_final=True` also suppresses widget stat rows regardless of
`widgets_in_panel`, because the browser's Final Stats panel has already made
the widget decision.

For `/api/predict`, the server selects the catalog-driven turn engine. That
path builds units from the Final Stats panel directly and does **not** use the
legacy pre-battle hero-skill `ModifierBoard`. Captain, joiner, troop, and T12
skill effects are applied only by the turn engine during the simulated battle.

---

## 8. Per-stat buff channel — `params["*_buffs"]` / `params["*_debuffs_on_enemy"]` (legacy/API callers 2026-07-05)

**Legacy decision (Martin, confirmed):** the UI panel holds the **scouted-report number**,
which already nets in item/pet/widget buffs (GAME_RULES 6h). So Layer 1 runs in
**`stats_mode="scouted"`** — it does **NOT** fold the buffs into `astat` (that would
double-count). Instead the raw per-stat buff pools are forwarded to you **verbatim,
as a separate channel in `params`**, for every matchup:

```python
params["a_buffs"]             = {"Attack": 0.30, "Defense": 0.30, "Lethality": 0.30, "Health": 0.30}  # attacker's own item+pet buffs
params["d_buffs"]             = { ... }   # defender's own item+pet buffs
params["a_debuffs_on_enemy"]  = { ... }   # magnitude the ATTACKER applies to the DEFENDER, per stat
params["d_debuffs_on_enemy"]  = { ... }   # magnitude the DEFENDER applies to the ATTACKER, per stat
```

- Keys are **stat strings** `"Attack" | "Defense" | "Lethality" | "Health"`; values
  are **fractions** (`0.30 = +30%`; debuff magnitudes are positive, `0.20 = −20%`).
- Missing stat → treat as `0.0`. All four dicts are always present (may be empty).
- **These are RAW pools, NOT baked into `astat`.** In the current browser
  contract they are empty because the browser sends Final Stats. For legacy
  callers, scouted mode `astat` starts as `TierBase x (1+panel)`; the older
  general-engine path may still apply its legacy static skill approximation, but
  the turn engine does not.
  The panel *already* includes the buffs for the stat magnitude;
  `*_buffs`/`*_debuffs_on_enemy` are handed through only for legacy compatibility
  or future cross-checking.
- Same non-mutating / CRN rules as the rest of `params`. Unknown to your current
  code → harmlessly ignored (like any extra `params` key) until you consume them.

---

## 9. Skill-proc telemetry — `result.skill_telemetry` (Martin request 2026-07-05)

**What the UI wants:** the engine returns, for every battle, the **same per-skill
breakdown the in-game battle report shows** — for each captain-trio hero, each
joiner, and each troop skill: **how many times it triggered** and **how many kills
it directly made**. So the front-end can render a Skill-Details panel identical to
the report and validate the sim against real reports proc-for-proc.

**Shape** (mirrors the report's Skill Details table):

```python
result.skill_telemetry = {
  "attacker": {
    "heroes": [
      {"hero": "Elif",     "role": "captain", "troop": "Infantry",
       "skills": [ {"slot": "skill_1", "triggers": 1,  "kills": 0},
                   {"slot": "skill_2", "triggers": 12, "kills": 0},
                   {"slot": "skill_3", "triggers": 12, "kills": 0} ]},
      {"hero": "Vulcanus", "role": "captain", "troop": "Marksman",
       "skills": [ {"slot": "skill_2", "triggers": 7,  "kills": 122045},
                   {"slot": "skill_3", "triggers": 6,  "kills": 0} ]},
      {"hero": "Ligeia",   "role": "joiner",  "troop": null,
       "skills": [ {"slot": "skill_1", "triggers": 9,  "kills": 40352} ]}
    ],
    "troop_skills": [
      {"name": "ambusher",      "troop": "Lancer",   "triggers": 8, "kills": 61950},
      {"name": "crystal_lance", "troop": "Marksman", "triggers": 0, "kills": 0}
    ]
  },
  "defender": { ...same shape... }
}
```

- `triggers` = number of times the skill fired over the battle (turn-based cadence
  from `freq`); `kills` = troops the skill's own damage incapacitated (0 for
  pure buff/debuff/stat skills that make no direct kills — matches the report's blank).
- `slot` ∈ `"skill_1" | "skill_2" | "skill_3"` for heroes; troop skills keyed by name.
- Joiners: `troop: null` (rally-wide), Skill-1 only (as today).
- Every value is a **mean over the stochastic batch** (fractional triggers/kills are
  rounded for display by the UI). CRN/non-mutating rules unchanged.

**STATUS — contract defined, NOT yet emitted.** The *current* engine models skills as
**averaged damage/stat modifiers** (e.g. Vulcanus SK2 `+100% dmg, freq 5` → ~`+20%`
mean damage-dealt), so it does **not** fire discrete procs, count triggers, or
attribute kills → it returns **`result.skill_telemetry = None`**. Emitting real
telemetry requires the **turn-by-turn skill-firing engine** (the same rework needed to
reproduce the non-linear, proc-driven attrition seen in report_001/report_002).
Until that ships, treat `skill_telemetry` as **nullable** and hide the panel when null.
