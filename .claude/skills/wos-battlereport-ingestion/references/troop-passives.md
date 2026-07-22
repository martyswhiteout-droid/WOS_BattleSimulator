# Troop skills, Type classification, and hero kits

Source of truth: `wos_sim/troop_catalog.py` (TROOP_SKILL_CATALOG) + GAME_RULES.md.
If this table ever disagrees with the catalog, the catalog wins — flag the drift.

## Troop skill unlock table

**Always-on passives** (deterministic — present in Type-1 battles):

| Class | Skill | Unlock | Effect |
|---|---|---|---|
| Infantry | Master Brawler | **T1** | +10% attack damage to **Lancers** |
| Infantry | Bands of Steel | T7 | +10% Defense against Lancers |
| Lancer | Charge | **T1** | +10% attack damage to **Marksmen** |
| Marksman | Ranged Strike | **T1** | +10% attack damage to **Infantry** |

**Chance procs** (stochastic — their presence makes a battle Type 2):

| Class | Skill | Unlock | Effect |
|---|---|---|---|
| Infantry | Crystal Shield I / II | FC3 / FC5 | 25% / 37.5% chance to offset 36 damage |
| Infantry | Body of Light I / II | FC8 / FC10 | +4%/+6% Def; extra reduction while Crystal Shield active |
| Lancer | Ambusher | T7 | 20% chance to strike Marksmen behind Infantry |
| Lancer | Crystal Lance I / II | FC3 / FC5 | 10% / 15% chance of double damage |
| Lancer | Incandescent Field I / II | FC8 / FC10 | 10% / 15% chance of half damage taken |
| Marksman | Volley | T7 | 10% chance to strike twice (a literal second attack event) |
| Marksman | Crystal Gunpowder II | FC5 | 30% chance of +50% damage |
| Marksman | Flame Charge I / II | FC8 / FC10 | +4%/+6% basic attack; extra damage while Gunpowder active |

## How to fill `troop_passives_active`

For EACH side, for each deployed class, list every skill unlocked at that side's
tier/FC — then judge `applies_in_this_battle` against the **opposing**
composition:

- Master Brawler applies ⟺ the opponent fields Lancers.
- Charge applies ⟺ the opponent fields Marksmen.
- Ranged Strike applies ⟺ the opponent fields Infantry.
- Bands of Steel applies ⟺ the opponent fields Lancers (defense against them).

Record the non-applying skills too, with `applies_in_this_battle: false` and the
reason — that a skill was present-but-inert is real information for the formula.

**The counter-triangle corollary** (load-bearing for the formula work):
- Every same-class MIRROR is passive-free (each T1 passive targets a class not
  present) → mirrors are clean core-law anchors.
- Every T1-T6 cross-class battle carries EXACTLY ONE +10% passive, on a known
  side. Getting this row right is why the derivation can decontaminate counters.

## Type 1 vs Type 2 classification

`type: 1` (deterministic) requires ALL of:
- Every deployed troop is **T1–T6** with **FC < 3** relevance (no Crystal procs),
  i.e. no Ambusher/Volley/Crystal/Body-of-Light/Incandescent/Flame unlocks in play.
- No hero on either side with a CHANCE-based skill (fixed-cadence skills like
  Vulcanus's every-3rd-turn are deterministic and OK).
- Martin's determinism test: re-running the identical battle yields identical
  survivors — when in doubt and a repeat exists, check it.

Anything else → `type: 2`. The downstream rule (ENGINE_CHANGE_CHECKLIST.md):
Type 1 = exact-fit calibration target; Type 2 = distribution validation ONLY,
never regression-fit.

## Known hero kits (record levels — effects change with level)

| Hero | Slot | Known effect | Notes |
|---|---|---|---|
| Seo-yoon | Skill 1, **L3** | +15% Troops Attack (own side) | Other levels differ — record the level shown; `level: null` if not visible |
| Vulcanus | Skill 1, L1 | −4% enemy Troops Attack | Once at battle start |
| Vulcanus | Skill 2 | Every 6th attack of **EACH unit** on its side (+20%, CAN kill); counters SUM across units (per-unit model, 2026-07-19) | 1v1: turns 6, 12, 18…; u units: u × floor(T/6) total procs |
| Vulcanus | Skill 3 ("True Strike") | Fires **turns 3, 6, 9, …** | THE turn clock (below). Per proc (L1): −12% enemy Inf/Lan Defense for 3 turns AND +12% own Marksmen's Attack for 1 turn (L4 = 48%/48%; scales with level) |

Any hero not in this table: record `{"hero", "slot", "name", "level", "effect"}`
from the report's Skill Details screen with `status: "identified"`, or
`status: "uncertain"` + a note if the effect text isn't readable.

## Vulcanus clock inversion (for `turn_inference`)

**CADENCE CORRECTED 2026-07-18** (10-battle Gatot-clock triangulation,
`wos_sim/formula_research/vulcanus_cadence_triangulation.py`, Martin's tooltip):
S3 fires turns 3, 6, 9, … so **k triggers ⇒ turns ∈ [3k, 3k+2]** (k=0 ⇒ [1,2]).
The OLD convention (turns 1,4,7 ⇒ [3k−2, 3k]) is WRONG — its "verified"
examples were circular (S2-turn-model and S3-phase-1 agree with each other in a
+2-shifted frame). S2 on a 1-unit side adds an independent constraint:
**m triggers ⇒ turns ∈ [6m, 6m+5]** (m=0 ⇒ [1,5]) — intersect all recorded
constraints. Record `trigger_count`, `turns_range`, and `turns` only if the
intersection is a single value.
If NO cadence hero is present, `turns: null`, `method: "unknown"` — never
estimate turns without a stated method.
