> **STATUS BANNER (2026-07-11): the headline "Step 1 landed: km 1.206 → 2.41" was REVERTED.**
> Commit `036e4ed` (2026-07-10, "Phase 1: remove km fudge") removed the km coefficient under the
> no-fudge rule (`ENGINE_CHANGE_CHECKLIST.md`, 07-09). The EVIDENCE in this doc (def_k overload,
> counter-triangle data, "winner ~2× too healthy") remains valid and feeds the first-principles
> derivation (`DEEPSEEK_FORMULA_DERIVATION_BRIEF.md`) — only the scalar-fix conclusion is superseded.

# Controlled experiments (Martin, 2026-07-08) — root-cause of the near-even misses

Martin ran controlled in-game experiments (minimal/no skills, deterministic, no
procs) to isolate why the engine mis-predicts. Raw data: `wos_sim/data/experiments/`.

## The convergent finding: ONE dominant error — the winner is left ~2x too healthy

| Experiment (deterministic, no procs) | Real winner survivors | Engine | Ratio |
|---|---|---|---|
| Encampment infantry mirror (2k & 20k) | **24.2%** | 53% | 2.2x |
| Alliance-garrison infantry mirror (attacker +10pt) | **30.2%** | 60% | 2.0x |
| Pure 10k lancer vs 10k marksman, Lv6 (no ambush) | **42%** (lancer wins) | 70% | 1.7x |

Every case: **winner DIRECTION correct, survivor MAGNITUDE ~2x too high.**

## Root cause: `def_k=0.45` under-grinds. It is OVERLOADED.

Mirror survivor% vs `def_k` (real = 24%): 0.45 -> 53.7%, **0.70 -> 28%**, 1.0 -> 0%
(flips to defender). So the clean mirror calibrates `def_k ~ 0.70` for the
mutual-attrition MAGNITUDE. But the 13-battle golden winner sweep wants `def_k`
LOW: 0.30 -> 8/13, 0.45 -> 7/13, 0.70 -> ~5/13.

**`def_k` sets two things at once** — the mutual-attrition rate (mirror wants
~0.70) AND the attacker/defender balance (winner ranking wants ~0.30-0.45). One
scalar cannot satisfy both; that is the mechanism behind every "fix one battle,
break another" episode. The `def_k=0.45` handicap (defender fires at 45%) is a
hack papering over missing win-ranking physics, and its side effect is the
under-grind.

## Two hypotheses RETIRED by Martin's experiments (honest updates)

1. **Garrison/fortress defender bonus — NOT a decisive factor.** The
   alliance-garrison mirror behaved like the encampment: the attacker won and
   the defender was wiped, even inside maxed alliance garrisons. A large
   defender home-advantage that flips mirrors does not exist at these scales.
   (Earlier "garrison bonus" hypothesis withdrawn.)
2. **Lancer-vs-marksman counter is NOT backwards.** Pure Lv6 lancer beat pure
   marksman (42%), and the engine agrees on direction. The Exp-3 case where a
   marksman DEFENDER beat a lancer attacker was T10 WITH troop skills (marksman
   Volley/Gunpowder) + infantry walls — a second-order T12-skill-regime effect,
   not a base-counter error.

## The right fix (structural; must pass G12 guardrail)

DECOUPLE the two roles `def_k` currently conflates:
- a **grind/mutual-attrition** control set so a mirror lands at ~24% (both
  sides fire ~parity in the exchange), and
- an **attacker/defender + composition** balance handled by real physics
  (tier, T12 troop skills, and only THEN any measured garrison term), not a
  global defender fire-rate handicap.

Do NOT just raise `def_k` (it flips near-mirrors to the defender and drops
golden winners). The mirror is now the clean magnitude anchor; the golden set
is the winner lock. Any decoupled fit must hold BOTH.

## Prototype outcome (2026-07-08): the decoupling does NOT work via parameters

Root cause of the under-grind pinned exactly: `fire_mode="start"` makes a
nearly-dead stack fire at its ORIGINAL size (a 1-troop stack dealt a
full-strength final volley), forcing mutual annihilation and handing a
near-mirror to the defender at parity. Added a smooth `fire_blend` knob
(0=live/Lanchester, 1=start; **default preserves current behavior**) to taper
the endgame.

Searched `fire_blend` x `def_k` against BOTH the mirror (target 24%) and the 13
golden winners. **Result: no combination satisfies both.** Every config that
pulls the mirror to ~24% needs `def_k >= 0.75`, and that breaks the SAME three
locked battles — RAW_06, RAW_08, T12_04 — attackers who really won but flip to
defender-wins once the defender grinds harder. The only configs that keep all 7
locked winners sit at `def_k=0.45`, where the mirror reads ~53%.

**Conclusion:** the grind magnitude and the winner ranking are coupled through
`def_k` and CANNOT be separated by a scalar. The three break-battles prove the
missing piece is real WIN-PHYSICS the engine doesn't model (the composition /
T12-troop-skill / tier advantages that let those specific attackers win against
a harder-grinding defender). A global grind or balance knob can't encode a
matchup-specific advantage.

**Action taken:** kept the `fire_blend` generalization (inert at default) as
scaffolding; **did NOT change the operating point** (`def_k=0.45`, 7/13 winners
preserved, no regression). Shipping the grind fix would have broken 3 currently
-correct battles — a net loss under G12.

**The real next step (structural, scoped):** model the per-matchup win advantage
(composition counter strength, T12 troop-skill damage, tier gap) so the correct
attacker wins even at `def_k~0.9`; THEN the grind can be set right and the
survivor magnitudes fall into range too. That is a multi-step build, not a tune,
and every step must hold G12.

## Counter-triangle data + step-1 status (2026-07-09)

Two more deterministic Lv6 (no-skill) battles, SAME 10k infantry attacker, only
the defender type changes:
- Infantry vs Lancer  -> infantry WON, **45.4%** survivors (favorable counter)
- Infantry vs Marksman -> infantry WON, **4.9%** survivors (unfavorable counter)

A **9x** survivor swing from the counter alone. Engine (cm=1.1) vs reality:

| matchup | real surv% | engine surv% |
|---|---|---|
| inf > lancer | 45 | 48 (ok) |
| inf < marksman | 4.9 | **67** (backwards) |
| lancer > marksman | 42 | 71 |
| mirror | 24 | 57 |

The engine has infantry doing BETTER vs marksman than vs lancer — reality is the
reverse. Root: the engine kills the fragile marksman (low def/health) before
they deal their (very high) damage, so it under-credits marksman offense. This
is a **damage-formula weighting** problem (marksman offense vs fragility, i.e.
`km`/`q_off`/`qd`/`qh` and the counter model), NOT a single `cm` boost.

Joint `(def_k, fire_blend, cm)` search: configs that fit the composition spread
(def_k>=0.8) still break RAW_06/RAW_08/T12_04; a flat `cm` up to 4.0 does not
rescue them. So step 1 is a genuine multi-mechanism build, coupled with the
grind and the winner lock.

### Step 1 landed (2026-07-09): `km` 1.206 -> 2.41 (turn engine only)

The counter gap was NOT `cm` — it was the marksman DAMAGE coefficient `km`. It
under-weighted marksman offense ~2x, so the engine killed the fragile marksman
before they dealt their high damage. Doubling it (calibrated to the clean
lancer>marksman anchor):

| matchup | real | before (km=1.21) | after (km=2.41) |
|---|---|---|---|
| lancer > marksman | 42.0 | 71.2 | **42.5** (exact) |
| inf < marksman | 4.9 | 66.7 | **33.4** (halved) |
| inf > lancer | 45.4 | 48.4 | 48.4 (unchanged) |
| mirror | 24.0 | 57.2 | 57.2 (no marksman) |

Back-test PASS: 7/7 locked golden winners hold, no new silent miss, regression
+ pytest green. Scoped to `TURN_PARAMS` so the PvE/farm kernel `BEST_PARAMS` is
untouched (no PvE data to justify changing it). The residual inf<marksman gap
(33% vs 4.9%) is the coupled UNDER-GRIND (mirror still 57% vs 24%) — do NOT
chase it with more `km` (km x4 over-kills lancer>marksman to 0%). That is the
grind step below.

### Roadmap (each step MUST pass `py -m wos_sim.backtest`)
1. **Composition/counter physics** — ✅ PARTIAL (km fix above): lancer>marksman
   exact, inf<marksman halved, winners held. Remaining counter residual is
   grind-coupled (below), not a km problem.
2. **T12 troop-skill damage**: marksman Volley/Gunpowder etc. (the mechanic that
   flipped Exp 3 lancer-vs-marksman between Lv6 and T10).
3. **Grind**: set `fire_blend`/`def_k` against the mirror once 1+2 let the correct
   attackers win at higher def_k. This is what closes inf<marksman 33% -> ~5%
   and mirror 57% -> ~24% together.
4. **Full re-audit**: back-test all reports; magnitudes should now fall in range.
