# DeepSeek Brief: Derive the Deterministic WoS Battle Formula

## Assignment

Derive a first-principles, turn-by-turn formula for deterministic Whiteout
Survival battle reports. The target is the real game mechanism, not a numerical
fit to the current simulator.

The immediate corpus is the NanoMart versus MiniMart controlled experiment set
under `wos_sim/data/experiments/`. These are intended to be deterministic:
there are no random troop procs in the low-tier T1-T6 controls. A formula must
therefore reproduce a report exactly when all recorded inputs are identical.

Do not introduce arbitrary attacker/defender handicaps, global damage rates, or
unidentified "fudge factors" merely to improve a fit. Any coefficient must have
a proposed game-mechanics identity and must work across the coherent controls.

## Evidence Priority

Use this priority order when sources disagree:

1. Latest instructions from Martin in this brief.
2. Raw experiment JSON and screenshot-derived trigger counts.
3. `wos_sim/data/experiments/NANOMART_EXPERIMENT_LEDGER.md`.
4. In-game / official hero tooltip text captured in
   `wos_sim/data/skill_display/hero_skills.json`.
5. `GAME_RULES.md` and the troop catalog.
6. Existing Python engine and older calibration notes. These contain known
   approximations and are not ground truth.

## Scope and Goal

There are two report types:

1. Type 1: no chance/proc skills. These are deterministic. The engine should
   reproduce them exactly, including winner, survivors, and turn count.
2. Type 2: chance/proc skills such as Ambusher. A single report is one outcome
   among many possible proc placements. These should be checked against a
   Monte Carlo distribution, not fitted as an exact calibration target.

This request concerns Type 1 and the controlled NanoMart set. Vulcanus has
periodic skills, but his Level-1 effects and their trigger counts are
deterministic. They should be simulated as scheduled events, not random procs.

## Definitions: A, D, L, H

Each troop has four combat attributes:

| Symbol | Name | Meaning in this investigation |
|---|---|---|
| A | Attack | Offensive stat. It must contribute to normal attack damage. |
| D | Defense | Defensive / mitigation stat. It must reduce incoming non-true damage. |
| L | Lethality | Offensive stat. It may be a second damage channel or an unmitigated / true-damage channel. Its exact relationship to D and H is still to be derived. |
| H | Health | Troop durability stat. It may set or scale a hidden per-troop HP pool. It is not a chief-panel bonus in these controls. |

The base stats for tier `n` are intrinsic troop values. A visible stat-bonus
panel percentage multiplies the corresponding base stat:

```text
pre-battle A = base A x (1 + visible A bonus)
pre-battle D = base D x (1 + visible D bonus)
pre-battle L = base L x (1 + visible L bonus)
pre-battle H = base H x (1 + visible H bonus)
```

For the NanoMart controls, Martin confirmed that chief-level Lethality and
Health bonuses are 0%. The screenshots omit those rows, so use only inherent
tier L and H. Visible A/D figures are recorded in the ledger. Apply battle-time
hero skills separately; do not double-count them inside the input panel.

## Relevant Base Troop Stats

The base values below are confirmed in `wos_sim/troop_catalog.py` and ordered
as `A / D / L / H`.

| Tier | Infantry | Lancer | Marksman |
|---|---|---|---|
| T1 | 1 / 4 / 1 / 6 | 4 / 2 / 5 / 2 | 5 / 1 / 5 / 1 |
| T2 | 2 / 5 / 2 / 7 | 5 / 3 / 6 / 3 | 6 / 2 / 7 / 2 |
| T3 | 3 / 6 / 3 / 8 | 6 / 4 / 7 / 4 | 7 / 3 / 8 / 3 |
| T4 | 4 / 7 / 4 / 9 | 7 / 5 / 8 / 5 | 8 / 4 / 9 / 4 |
| T5 | 5 / 8 / 5 / 10 | 8 / 6 / 9 / 6 | 9 / 5 / 10 / 5 |
| T6 | 6 / 9 / 6 / 11 | 9 / 7 / 10 / 7 | 10 / 6 / 11 / 6 |

## Confirmed Turn Resolution

1. Battle resolution is turn-based.
2. At the start of a turn, both sides inspect the same start-of-turn state.
3. Each live troop class makes its scheduled normal attack(s). With all three
   classes alive, each side has three normal class attacks that turn.
4. Both sides' damage is calculated before either side's casualties are
   removed. Resolution is simultaneous, with no first-strike advantage.
5. Normal damage is absorbed in strict order: Infantry, then Lancer, then
   Marksman. A protected back-line class receives no normal damage while a
   class in front remains alive.
6. A bypass skill is the only normal exception to this front-to-back rule.
   It targets its stated back-line troop type directly.
7. Casualties change the next turn's force. Fire mode is **live**, not
   starting strength: output must use the live troop state at the beginning of
   the current turn, never the original starting count.

The controlled one-versus-one battles strongly suggest a hidden HP state. A
single Infantry can survive and attack for about 264 turns before it falls.
The candidate physical model is therefore:

```text
damage dealt in turn t -> subtract from target HP pool
live troops in turn t+1 -> troops whose HP remains above zero
next turn's output -> based on those live troops
```

Do not model partial damage as an immediately fractional troop death. Also do
not reduce a still-living troop's attack merely because it has lost some HP,
unless evidence requires that rule. A one-troop duel can then remain at one
full-strength attacker per side for hundreds of turns, while HP accumulates
damage underneath.

The mapping between a troop's displayed Health stat and hidden HP capacity is
unknown. Determine or parameterize it with a named, testable rule.

## Counter Triangle and Deterministic T1 Passives

The class counter direction is:

```text
Infantry -> Lancer -> Marksman -> Infantry
```

The known T1 passives are real deterministic Damage Dealt modifiers, applied
only when the source class attacks its stated target class:

| Source | Target | Passive | Effect |
|---|---|---|---|
| Infantry | Lancer | Master Brawler | x1.10 outgoing damage |
| Lancer | Marksman | Charge | x1.10 outgoing damage |
| Marksman | Infantry | Ranged Strike | x1.10 outgoing damage |

Do not replace these with an arbitrary generic counter coefficient. Determine
whether the game has a further intrinsic class-counter term after these known
passives are applied.

## Hero Skill Rules for the NanoMart Controls

Unless a filename explicitly says otherwise:

- All Vulcanus expedition skills are Level 1.
- Seo-yoon Skill 1 is Level 3.
- Seo-yoon does not provide a random proc in these controls.

### Seo-yoon Skill 1, Level 3

```text
All own troops: Attack +15% for the battle.
```

For filenames ending in `lvl1`, `lvl2`, or `lvl3`, use +5%, +10%, or +15%
respectively.

### Vulcanus Skill 1: Raging Storm, Level 1

```text
All enemy troops: Attack -4% for the battle.
```

### Vulcanus Skill 2: Breaker Steel, Level 1

Tooltip:

```text
All own troops deal 20% extra damage after every 5 attacks.
The target takes 5% more damage in the next attack.
```

The controlled report counters establish the observable schedule for a
single-class battle:

```text
displayed S2 triggers = floor(total battle turns / 6)
S2 event turns = 6, 12, 18, 24, ...
```

Examples: 264 turns gives S2 = 44; 30 turns gives S2 = 5; 318 turns gives
S2 = 53. All 49 clocked NanoMart records match this relation.

The best interpretation is five ordinary attacks charge the skill and the
sixth attack is the empowered attack. Do not use a simple event schedule of
turns 5, 10, 15. The exact packet ordering of the +20% Damage Dealt and +5%
Damage Taken effect is not yet proven. Consider both possibilities explicitly:

- same empowered packet: multiplier `1.20 x 1.05 = 1.26`;
- two adjacent packets: +20% on the empowered packet, then +5% Damage Taken
  on the next qualifying received attack.

The report counters prove cadence, not this packet-order detail.

### Vulcanus Skill 3: True Strike, Level 1

```text
Enemy Infantry and Lancer Defense -12% for 3 turns.
Own Marksman Attack +12% for 1 turn.
```

The observable schedule is:

```text
displayed S3 triggers = ceil(total battle turns / 3)
S3 event turns = 1, 4, 7, 10, ...
```

In the single-class Infantry/Lancer drills, the enemy Defense reduction is
continuous: its three-turn duration exactly meets the next three-turn trigger.
The Marksman Attack component is irrelevant when no Marksmen are deployed.

## Correct Skill Backout for the Standard Infantry Drill

This is the most common controlled setup: NanoMart attacks with Seo-yoon L3;
MiniMart defends with Vulcanus L1. NanoMart's visible Infantry bonuses are
Attack +2.2%, Defense +0.2%. MiniMart's are Attack +2.0%, Defense +0.0%.

For NanoMart Tn Infantry, while Vulcanus S3 is active:

```text
A_N = n x 1.022 x 1.15 x 0.96 = 1.128288n
D_N = (n + 3) x 1.002 x 0.88 = 0.88176(n + 3)
L_N = n
H_N = n + 5
```

For MiniMart Tm Infantry:

```text
A_M = 1.020m
D_M = m + 3
L_M = m
H_M = m + 5
```

Vulcanus S2 is then a deterministic periodic modifier to MiniMart's outgoing
damage. These equations define the inputs to the unknown damage kernel; they
are not themselves the solved battle formula.

## Controlled Corpus

Primary ledger: `wos_sim/data/experiments/NANOMART_EXPERIMENT_LEDGER.md`.
It contains 59 JSON-backed rows, starting forces, visible A/D input values,
inherent L/H, heroes, results, trigger counts, inferred turns, and capture
warnings.

The high-value signals are:

| Control | Observed result | Why it matters |
|---|---|---|
| T1/T2/T3/T6 Infantry mirror, 1v1 | about 264-266 turns | Same-class Infantry clock is nearly tier-invariant. |
| T1 Lancer mirror, 1v1 | 30 turns | Class clock differs sharply from Infantry. |
| T2/T1, T3/T1, T4/T1, T5/T1 Infantry | 176, 126, 96, 80 turns in the original set | Tier edge changes the clock nonlinearly. |
| T1 Infantry 1v1/1v2/2v1 | 264 / 192 / 186 turns | Count is not simply linear in troop count. |
| T1 Lancer 1v1/1v2/2v1 | 30 / 20 / 20 turns | A second count-scaling constraint. |
| T1 Infantry -> Lancer and Lancer -> Infantry | 80 and 8 turns | Cross-class effects are directional. Apply T1 passives first. |
| T6 Infantry 100/200/250/300 versus 200, no hero | D149 / A4 / A109 / A178 survivors | Clean deterministic survivor curve. |
| Same T6 ladder with defender Vulcanus | clocked 205-207, 379-381, 355-357, 295-297 | Quantifies the deterministic Level-1 Vulcanus impact. |

### Data Conflict That Must Not Be Hidden

Two nominally identical captures currently disagree:

- `NanoMart_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus.json`: 79-81 turns.
- `NanoMart_SetA_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus.json`: 67-69 turns.

Both record T5 Infantry versus T1 Infantry, the same visible A/D bonuses,
Seo-yoon L3, Vulcanus L1, and a full attacker survivor. A deterministic formula
cannot fit both if every hidden input is truly identical. Treat this as an
unrecorded-state or extraction issue, not evidence for a new coefficient.

There are also explicitly flagged duplicate and heading/tier issues in the
ledger. Do not count a duplicate as an independent observation.

## Current Hypotheses and Rejections

1. The old direct-ratio form `damage ~ A x L / (D x H)` is inadequate. It
   predicts large tier-clock changes in same-class mirrors that are not seen.
2. A simple candidate `A / (A + D) / (D + H)` is falsified: it matches T1 and
   T6 Infantry endpoints but predicts a materially faster T2/T3 mirror than
   the observed 266 turns.
3. A provisional difference law, roughly `damage per turn proportional to
   A_attacker - D_defender + K`, explains some Infantry tier-ladder rows. It is
   not accepted. It must be retested after applying the true Seo-yoon and
   Vulcanus Level-1/Level-3 effects and after resolving the T5 conflict.
4. The strongest structural hypothesis is a live, hidden-HP recurrence with a
   class-specific damage/durability relationship and sublinear effective count
   scaling. The observed count exponent is roughly 0.5-0.6 in the small
   Infantry/Lancer mirror set, but it could represent a pairing or frontage
   rule rather than a literal power exponent.
5. Attack and Lethality may be one multiplicative offence channel, or they may
   be separate normal-damage and true-damage channels. Defense may mitigate
   only the Attack channel. Health may be the HP capacity or a multiplier of
   it. The controls must discriminate these alternatives.

## What Is Wrong With the Current Engine

The existing `wos_sim/pvp_turn_engine.py` is useful as infrastructure but is
not the formula oracle. It currently contains fitted parameters, an
approximate fractional-casualty representation, and a `fire_mode` setting that
must be live for this investigation. It also lacks a hero skill-level input,
so it cannot natively replay these Level-1 Vulcanus / Level-3 Seo-yoon tests.

Do not use its `rate`, `def_k`, `mod_gamma`, `stat_floor`, `K_skill`, class
coefficients, or start-strength behavior as facts about the game. A proposed
real formula should explain why any retained coefficient exists or remove it.

## Deliverables Requested From DeepSeek

1. State the smallest plausible per-turn mathematical model, including the
   hidden HP state, live troop count, Attack, Defense, Lethality, Health,
   class passives, and Vulcanus schedules.
2. Apply the exact skill backout above before analysing the NanoMart corpus.
3. Test the model against every non-duplicate, internally coherent Type-1
   experiment. Show a table of observed versus predicted winner, turns, and
   survivors.
4. Name and justify every parameter. Reject unnamed global rate or side-bias
   constants.
5. Explain whether Lethality is an independent true-damage channel or part of
   the same offence term, and what Health represents in the HP model.
6. Give code-ready pseudocode for the turn loop and per-turn state updates.
7. Identify exactly which reports cannot be reconciled and what missing input
   or one-troop experiment would distinguish the remaining hypotheses.

Do not calibrate to stochastic Type-2 battles. Do not infer a coefficient from
the answer it is supposed to produce. Prefer a smaller model that explains the
controlled corpus over a larger model that merely interpolates it.

## File Map

| File | Purpose |
|---|---|
| `wos_sim/data/experiments/NANOMART_EXPERIMENT_LEDGER.md` | Complete 59-row controlled ledger. |
| `wos_sim/data/experiments/NANOMART_MINIMART_1V1_STRUCTURED_TABLE.md` | 1v1 corpus and earlier formula reads. |
| `wos_sim/data/experiments/NANOMART_MINIMART_COUNT_SCALING_EXP2.md` | 1v2 / 2v1 count evidence. |
| `wos_sim/data/experiments/TYPE1_NANOMART_8POINT_CALIBRATION.md` | T6 no-hero and Vulcanus ladder. |
| `wos_sim/data/experiments/NanoMart_*.json` | Raw machine-readable experiment records. |
| `wos_sim/troop_catalog.py` | Verified base troop stats and troop passives. |
| `wos_sim/data/skill_display/hero_skills.json` | Tooltip text and skill progression. |
| `GAME_RULES.md` | Broader verified rules and older hypotheses; use with the evidence priority above. |
