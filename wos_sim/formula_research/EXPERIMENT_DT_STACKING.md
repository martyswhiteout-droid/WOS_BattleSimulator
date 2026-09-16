# Experiment — how the game composes stacked Damage-Taken joiners (pre-registered)

**Date:** 2026-09-11 · **Owner:** Martin (fights the battles) · **Analysis:** `dt_stacking_ladder.py` (frozen)
**Status:** FIRST PASS FOUGHT 2026-09-11 (six battles, Lv2/Lv3 skills — see §8). The §1 table stays frozen for the max-level rungs.
**Trigger:** `Scenarios/Gend15/Gen15_Rally_WM.json` — 3× Wu Ming makes a garrison hold 99/100 sim runs;
swapping one Wu Ming for Gatot makes it lose 100/100. The whole outcome rides on how stacked
Damage-Taken composes, and that has never been measured (corpus: zero Type-1 rows with any DT joiner).
`GAME_RULES.md` s.148 records the form as open ("Martin confirmed additive for same-skill stacks …
cross-source composition is a fittable option") and s.304 records a real battle that contradicts a
raw additive stack (Wu Ming ×2 + Ahmose, nominally −90%: "his infantry still fell").

---

## 1. The question, stated so a battle can answer it

Wu Ming's expedition skill 1 gives Infantry **−25% damage taken from Normal attacks** (and −30% from
Skills — irrelevant here, see §3). With **k** copies of Wu Ming among the joiners, what is the
effective-toughness multiple **M_k** of the Infantry?

| family | M_1 | M_2 | M_3 | what it means |
|---|---|---|---|---|
| **additive** | 1.333 | 2.000 | 4.000 | reductions add: −25/−50/−75% |
| **multiplicative** | 1.333 | 1.778 | 2.370 | each copy scales the remainder: 0.75^k |
| **engine today** (additive + `mod_gamma` 0.30) | 1.090 | 1.231 | 1.516 | what `pvp_turn_engine.py` computes now |
| capped at −50% | 1.333 | 2.000 | 2.000 | plateau after two copies |
| capped at −60% | 1.333 | 2.000 | 2.500 | plateau at the stat-floor analogue |

Two rungs do most of the work:
- **k = 1 tests the gamma compression on its own**: 1.333 (any uncompressed form) vs 1.090 (engine today) — a 22% gap.
- **k = 3 separates additive from multiplicative**: 4.000 vs 2.370 — a 69% gap.

Turns land on integers (deaths are quantised: predicted `t_k = ceil(t_0 · M_k)`), so with a base
clock of ~80 turns the ratios resolve to ~1%. That is far finer than any gap in the table.

## 2. The observable — the DT side must DIE

In the Type-1 lab regime the kill clock is proportional to the target's effective HP
(`turns = K · D_l·H_l/(A_w·L_w) · G_w · G_l`, exact to ≤0.4 turns on the Gatot ladders). So

    t_k / t_0 = M_k

**only if the Wu-Ming-buffed Infantry is the side that dies.** In a plain mirror the buffed side
would win, the battle would end when the *attacker* died, and the multiple would never be observed.
Therefore the design is the project's **Gatot instrument** shape: the winner carries Gatot (its holder
is shielded as a target, so the winner never dies) and the loser's death turn is the measurement.

Everything on the winner's side cancels in the ratio `t_k / t_0` — kit level, tier damping, alliance
buffs — because only the loser's joiners vary across the ladder. `t_0` is measured, not assumed.

## 3. Setup

| | **Loser (measured)** | **Winner (constant)** |
|---|---|---|
| role | **Garrison** — Martin's city (joiners reinforce it) | Rally / attacker |
| troops | 1 × Infantry, T1 (the usual Lab-Rat single) | Gatot-led, strong enough to kill the loser in **< 375 turns at k = 0** (see cap, §5) |
| captain heroes | none, or an inert set — **no proc heroes, no skill-damage heroes** | Gatot as captain (constant across all battles) |
| joiners | **k × Wu Ming as flag hero**, k = 0, 1, 2, 3 | none |
| class of damage dealt | — | Normal only (T1–T6 troops carry no proc troop-skills: Ambusher is T7+, Crystal Lance T11+) |

Why the winner deals **Normal damage only**: Wu Ming's second row (−30% from *Skills*) then never
fires, so the ladder isolates the −25% Normal channel and the table above applies unchanged.

**The joiner-troop confound and its control.** Reinforcing a garrison sends troops, so k joiners add k
units to the loser's stack and lengthen its death clock regardless of any skill. Two acceptable ways
to handle it — Martin picks whichever the game allows:

- **(a) 0-troop reinforcement**, if the game permits a hero-only reinforcement. Then no control is needed.
- **(b) Control ladder** (assumed): every joiner sends exactly **1 × T1 Infantry**, and a second ladder
  is fought with k joiners whose flag hero's skill 1 is **inert for an Infantry defender** (e.g. a
  Marksman-only buff hero). Then `t_k(control)` carries the pure count effect and the measured
  multiple is `M_k = t_k(Wu Ming) / t_k(control)`. Seven battles total: `t_0` + 3 + 3.

Hold constant across every battle: attacker composition and heroes, alliance buffs, gear/pets/items,
time of day if any event buff is running, and **the Stat Bonuses screens must be captured for both
sides every time** (the earlier "mirrors" that turned out unequal are why this rule exists).

## 4. Capture and ingestion (unchanged project rules)

Per battle, via the `wos-battlereport-ingestion` skill: Battle Overview (both sides' troop counts),
**Stat Bonuses panel for BOTH sides (all 12 rows)**, hero lineups incl. the joiner list, casualties,
and the **turn count** (the observable). Save as v2-schema JSON under
`wos_sim/data/experiments/DT_Stacking_Ladder/`, validate with the skill's `validate_report.py`, then
rebuild the corpus (`build_corpus.py`). Determinism class must come out `clean` — if any row is flagged
`proc_or_unknown`, the battle had a proc hero in it and does not count.

## 5. Decision rule — frozen now, applied later

Run `py -m wos_sim.formula_research.dt_stacking_ladder t_0 t_1 t_2 t_3` (using the control-corrected
turns if design (b) was used).

- A family is **ACCEPTED** only if **every** rung k = 1..3 lies within **±5%** of its quantised
  prediction. This is the same exact-fit bar the A6 validation gate uses.
- If **no** family passes, the best log-least-squares family is reported as a **HYPOTHESIS ONLY**.
  Nothing gets fitted to the ladder; that is the point of freezing the table.
- **Cap guard**: `t_0 · 4.0` must be **< 1500** (the global battle cap). If the k = 0 battle takes
  more than 375 turns, strengthen the attacker and re-measure `t_0` before fighting k = 1..3.
- **OCR-anomaly rule** applies: a rung that makes no physical sense (e.g. t_2 < t_1) is flagged to
  Martin to re-check the capture *before* any interpretation.

## 6. What happens with the answer

Whichever family is accepted becomes the engine's DT composition rule — a **mechanic verified on a
Type-1 anchor**, landed through `api.py`, gated by `py -m wos_sim.backtest` (G12) and the suite like
any engine change. Consequences by outcome:

- **additive accepted** → the raw form is right; the `mod_gamma` compression on DT is what is wrong
  (k = 1 will already have shown 1.33 ≠ 1.09). Retire gamma from the DT channel.
- **multiplicative or capped accepted** → the engine over-credits stacked DT today; that is the
  mechanism behind "3× Wu Ming holds 99/100", and `Gen15_Rally_WM` will read very differently.
  *[Corrected 2026-09-11 after the first pass, §8: this bullet assumed the γ compression would survive. It did not —
  γ was rejected on the same data — so the two errors partly cancel and the engine's net effect is to UNDER-credit
  stacked Wu Ming (×1.52 vs the accepted form's ~×2.0–2.37). `Gen15_Rally_WM`'s 99/100 hold is not contradicted.]*
- **engine-today accepted** → the current fitted form happens to be right; keep it and document the
  measurement that justifies it (it currently has none).

Until then the product shows the dependence honestly rather than asserting one side (the
opt-in stacking-sensitivity probe proposed 2026-09-11): default engine unchanged.

## 7. Not in scope

Cross-hero composition (Wu Ming + Ahmose), the Skills channel (−30%), and Damage-Dealt stacking each
need their own rung and are deliberately excluded so this ladder answers one question cleanly.

**Related:** `GAME_RULES.md` s.148–151, s.300–306 · `ENGINE_HANDOFF_joiner_stacking.md` (copies stack — settled) ·
`STAGE4_REPORT.md` / `STAGE6_REPORT.md` (the Gatot instrument) · `wos_sim/predictor/winprob.py` (fold fix, 2026-09-11).

---

## 8. Results — first pass, 2026-09-11 (six battles, `wos_sim/data/experiments/Wu Ming Experiments/`)

Evaluator: `dt_stacking_wuming_20260911.py` (bespoke — the generic ladder script assumes k × −25% and must not be run on these).

**As fought (deviations from §3):** attacker = 5 × T10 FC2 Infantry led by Gatot L71 (all three Gatot skills are stat
passives, `deals_damage=False`, no chance-based troop skill active ⇒ **Normal damage only, so only Wu Ming's Normal
channel fired**). Defender = **2 Infantry in every battle** (MatiLife T9 + MatiBlizzard T10, "Lv 9.5"), so the joiner-troop
confound of §3(b) did not arise. Wu Ming (hero L1) was fielded as **captain** in B2/B3 and as captain + **joiner** in B4/B5;
S1 "Shadow's Evasion" Lv2 = −10% Normal / −12% Skills, Lv3 = −15% / −18% — i.e. **2.5× weaker than the max-level −25%
the §1 table assumes**. All six: attacker victory, no attacker casualties, deterministic.

| # | defender panel (Inf Atk / Def / Leth / Health) | Wu Ming | Gatot S2 = turns |
|---|---|---|---|
| B1 | 179.5 / 164.9 / 114.4 / 113.6 | none | **69** |
| B2 | 343.3 / 330.4 / 96.2 / 98.0 (Blizzard-led) | captain Lv2 | **113** |
| B3 | 351.2 / 336.6 / 114.4 / 113.6 (Life-led) | captain Lv3 | **130** |
| B4 | = B3 | captain Lv3 + joiner Lv2 | **141** |
| B5 | = B4 (carried) | captain Lv3 + joiner Lv3 | **146** |
| B6 | = B2 (carried) | captain Lv3 | **118** |

A Wu Ming captain adds exactly +171.7 to Infantry Attack and Defense (B1 → B3 differ on nothing else), so rung (a) is
corrected through the law's exponent-1 Defense term: `M = (t_b/t_a) / (D_b·H_b / D_a·H_a)`, D = 1 + panel/100.

| rung (single-variable) | observed M | additive | multiplicative | engine-today (γ 0.30) |
|---|---|---|---|---|
| (a) B1→B3, single −15% (D-corrected ×1.648) | **1.143** | 1.176 (−2.8%) ok | 1.176 (−2.8%) ok | 1.050 (**+8.9%**) ✗ |
| (b) B3→B4, +joiner −10% on −15% | 1.085 | 1.133 (−4.3%) ok | 1.111 (−2.4%) ok | 1.038 (+4.5%) ok |
| (c) B3→B5, +joiner −15% on −15% | **1.123** | 1.214 (**−7.5%**) ✗ | 1.176 (−4.5%) ok | 1.060 (**+6.0%**) ✗ |
| (d) B2→B6, captain −10% → −15% | 1.044 | 1.059 (−1.4%) | 1.059 (−1.4%) | 1.017 (+2.6%) — all within band |
| (e) B4→B5, joiner −10% → −15% | 1.036 | 1.071 (−3.4%) | 1.059 (−2.2%) | 1.021 (+1.4%) — all within band |

**Verdict under the frozen ±5% rule: multiplicative ACCEPTED · additive REJECTED · engine-today REJECTED.**

**Implemented 2026-09-11:** `TURN_PARAMS["modifier_stacking"]` ∈ {`legacy`, `dt_multiplicative`, `multiplicative`} (`wos_sim/pvp_turn_engine.py`; tests `test_modifier_stacking.py`). Gates per mode — G12 7/13 PASS with no locked regression in all three; suite green; 22-battle Brier legacy 0.2011 / dt_multiplicative 0.2011 / multiplicative **0.1817**. Default → `dt_multiplicative` (the measured half) on 2026-09-11; **owner decision 2026-09-16 (Martin): default → `multiplicative`** — DD adopted by symmetry as a documented hypothesis (same modifier family, same legacy floor hazard), gates at adoption G12 7/13 / suite green / Brier 0.1817. **Display-rule refinement, same day:** the measured DT rule moved a synthetic troop ladder's tipping point so a `decisive_agree` rung (raw sim 1.00, stability S = 0.53) sat beside a knife-edge hedge (0.75) — a 0.25 drop as troops rose. `winprob.hybrid_win_prob_ex` now scales a decisive-agree call's trust with its stability, `trust = DAMP + (1−DAMP)·|S−0.5|/0.5` (DAMP at a knife-edge, full trust when unanimous); unanimous calls (expX2, RAW_04) are unchanged, so G12 (7/13) and the 22-battle Brier (0.2011) did not move; the ladder's largest dip is 0.015. Suite green on the new default (232 tests as of 2026-09-16). **Red-team QA 2026-09-16 (two passes): SHIP.** Pass 1 found 3 bugs (no test guarded the shipped default; `_joiner_mults` was channel-blind and overstated Wu Ming ~23%; a typo'd mode silently ran legacy) — all fixed and independently re-verified; 13/13 mutation attacks caught; multiplicative is ~27% faster than legacy. **Known follow-up (pre-existing, display-only):** where the binary ±5% blind probe flips a `decisive_agree` call into the knife-edge hedge, the headline can jump by up to `0.5·(1−DAMP)` = 0.25 (live repro: Gen15_50_10_40 + 4×Nora, troops ×0.81→×0.82). Bounded by a sentinel test; the real fix is a continuous blind-probe signal (kernel `_near_even_probe`, under the coin-flip rule), not a display patch.
Same-hero DT reductions compose as `Π(1 − x_i)`, not `1 − Σx_i`, and the engine's γ = 0.30 compression on the DT channel
under-credits a single source by ~9%. Observations sit **2.8–4.5% below** pure multiplicative on every rung — a consistent
shortfall that hints at *mild* compression (an effective exponent near 0.8 would fit — recorded as a HYPOTHESIS, not fitted).

**What this means for the engine — CORRECTED 2026-09-11 after implementing the rule.** The engine is wrong in both
directions (γ under-credits single sources; additive over-credits stacks) — but the original paragraph here reasoned from
*three* sources and missed that `Gen15_Rally_WM`'s garrison Infantry carries **four permanent −25% Normal-channel DT rows**
(Estrella S3 + 3 × Wu Ming S1). Additively that is exactly −100%: the legacy rule floors the sum at −1.0, `0^0.30 = 0`, and
`base_strike_damage` multiplies incoming damage by `max(0, 1 + dt)` = **0 — the Infantry become immune**. The "99/100 hold"
was an immunity cliff, not a toughness value, and swapping one Wu Ming for Gatot (sum −75%, off the cliff) is why a single
joiner flipped the outcome. Under the accepted multiplicative rule the same rows give `0.75⁴ = 0.316` → ×3.16 toughness —
strong, finite — and this attacker grinds the garrison down: **hold rate 0/100** under both multiplicative modes (the third
Wu Ming still helps: casualty margin −0.49 → −0.28). The owner's "farfetched" instinct was right; the mechanism is the
additive floor. *(Superseded text: "the engine under-credits a stacked Wu Ming garrison … `Gen15_Rally_WM`'s 99/100 hold is
not contradicted" — wrong for this scenario.)*

**The residual, quantified (hypotheses, not fits).** Two one-parameter stories reproduce a shortfall below pure
multiplicative, solved per rung: a DT-immune slice of incoming damage (e.g. an H2-style Lethality/true-damage component,
`GAME_RULES.md` s.146) gives immune share **f = 0.17 / 0.19 / 0.24** on rungs (a)/(b)/(c); a compression exponent on the
composed factor gives **g = 0.82 / 0.77 / 0.71**. Both DRIFT with stack size — the shortfall grows faster than either
single parameter predicts — so three rungs at ~3% precision cannot separate them (or a combination, or the onset of a cap).
Pure multiplicative remains the accepted, parameter-free form; the residual is recorded for the day more data exists.

**Skill levels.** The engine has no hero skill-level concept (`profiles.py`, `serialize.py`, `construct.py`, `loader.py`):
it always applies the catalog's max-level rows (Wu Ming S1 = −25%/−30%). These six battles used S1 Lv2/Lv3, so they cannot
be reproduced by the engine as an anchor — the DT rule rests on the ratio analysis above — and every product prediction
silently assumes maxed hero skills. That is a separate, pre-existing gap worth its own ticket.

**Caveats.** (i) Rung (a) assumes B1 is MatiLife's garrison with no captain hero — the panel says so (Leth/Health identical to
B3, Atk/Def exactly −171.7) but the header names MatiBlizzard: Martin to confirm. Rungs (b)/(c) do not depend on it and alone
reject additive and γ. (ii) B5/B6 reuse B4/B2 screenshots for overview/panel; only their turn counts are new — carried per
"no other changes". (iii) The FORM is measured at −10/−15%; its extrapolation to −25% × 3 is not, and the 3–4.5% shortfall
may grow with the stack.

**Next.** (1) Confirm the B1 header. (2) ~~The §1 ladder at max-level S1~~ — **not feasible** (owner, 2026-09-11: a max-level Wu Ming needs an account too developed to keep its troops out of the proc-skill zone; no farm satisfies both). This first pass is the final data. (3) Therefore the engine change proceeds on the accepted family alone, gated: `modifier_stacking` engine option (`legacy` | `dt_multiplicative` | `multiplicative`), G12 + suite + 22-battle Brier run per mode, default changed only if the measured mode holds every locked winner. DD stays a symmetry hypothesis until a DD ladder exists.
