# Stage 8.1 — army-scale law: findings (2026-07-25)

Martin's push-back was correct: the corpus **does** contain army-scale deterministic
battles (up to 20,000 troops) with full stat panels. They were tagged
`legacy_unverified` (tier-label ambiguity) so the validators never scored them, and my
earlier "everything is a 1v1 lab fight" claim was wrong. These rows answer the central
questions. Every number below is reproducible from the cited files.

## The instrument: a 10x count-scaling pair
`exp1_mirror_20k.json` / `exp2_mirror_2k.json` — Alpaca vs Colonel Müller, pure
Infantry, **no heroes**, deterministic, open-field encampment. **Same players, same
stats, 20,000 v 20,000 and 2,000 v 2,000** (explicitly "a scale check"; the 20k ran x3
identical).

## Finding 1 — outcomes are EXACTLY SCALE-INVARIANT
| quantity | 20k | 2k | ratio |
|---|---|---|---|
| troops | 20000 | 2000 | 10.00 |
| injured | 5308 | 531 | 9.996 |
| lightly injured | 9855 | 985 | 10.005 |
| survivors | 4837 | 484 | 9.994 |
| **survivor fraction** | **0.24185** | **0.242** | **1.000** |
Ten times the army, identical fractions. **Attrition depends on the stat RATIO, not on
absolute size.**

## Finding 2 — army damage pools LINEARLY (Lanchester square law), not as √N
Two candidate pooling laws, both scale-invariant, are discriminated by the magnitude:
- **linear pooling** (dA/dt = −β·B) ⇒ winner fraction `= sqrt(1 − β/α)` → **0.2417**
- **√N pooling** (dA/dt = −β·√B) ⇒ winner fraction `= (1 − β/α)^(2/3)` → **0.1506**
Observed **0.24185**. Linear pooling **matches, √N is refuted at army scale.** (√N stays
the small-N lab regime; consistent with the earlier "linear volley pooling" Gatot result.)

## Finding 3 — the same-class army law is SOLVED, with ZERO free parameters
Per-unit kill-rate coefficient (from the frozen Stage-4/6 form, base stats cancel in a
same-class same-tier matchup, so the panels alone decide):
```
alpha = A_att·L_att / (D_def·H_def)      beta = A_def·L_def / (D_att·H_att)
winner_fraction = sqrt(1 − beta/alpha)          [equal counts]
general counts:  A_f² = N_a² − (beta/alpha)·N_d²
```
| | value |
|---|---|
| alpha | 1.096931 |
| beta | 1.032857 |
| beta/alpha | 0.941588 |
| **predicted fraction** | **0.24169** |
| **observed (20k)** | **0.24185** |
| **error** | **+0.07 %** |
Winner also correct (attacker). Nothing was fitted: the form is the frozen law, the
inputs are the captured panels.

## Finding 4 — `def_k` is definitively unnecessary (a fudge)
This is a **real near-mirror** (not a synthetic one): the attacker's panels are better
by **+16.0 pt Defense**, +1.9 Attack, +0.6 Health; the defender is +2.3 Lethality. That
stat edge alone reproduces 24.2 % / 0 % **exactly**. **No attacker role advantage is
needed.** (The file's own `KEY_FINDING` recorded this in 2026-07-08; it was never acted
on.) For contrast, the live `def_k=0.45` turn engine on the same matchup produces a
mirror sweep, and the current composition algorithm predicts the **wrong winner**, a
**turn-capped** battle, and **85–96 % survivors** whose fraction *drifts with N* —
violating the measured invariance.

## Finding 5 — cross-class at army scale is NOT solved (open)
Blind test, same square law + the **frozen K/G tables**, zero new constants:
| battle | observed | predicted (G applied) | predicted (G dropped) |
|---|---|---|---|
| exp4 Inf10k v Lan10k | attacker 0.4536 | **defender** 0.6322 ✗ | attacker 0.8668 (+91 %) |
| exp4b Inf10k v Lan10k | attacker 0.4282 | **defender** 0.6488 ✗ | attacker 0.8615 (+101 %) |
| exp5 Inf10k v MM10k | attacker 0.0488 | **defender** 0.4382 ✗ | **defender** 0.0700 ✗ |
Neither variant works: with the tier-damping factors the winner is wrong in all three;
without them two winners come right but magnitudes are ~2x off. **The K-table and
G_w/G_l were measured in the 1–6-unit lab regime and do not transfer to army scale as-is**
(and `G_l(Lancer,T6)` is itself an unmeasured/interpolated cell). Per the no-regression
rule these three points were NOT used to re-fit K — the gap is reported, not papered over.

## Anomaly to verify (OCR-anomaly rule)
`exp3a_lancer.json` and `exp3b_lancer.json` are labelled the **same setup** (10k/20k pure
Lancer vs pure Marksman) but record **opposite winners** (3a: Lancer attacker wins 42 %;
3b: Marksman defender wins 24.8 %). Martin should confirm whether the setups really were
identical — if so, that matchup is near-even/regime-sensitive, not deterministic.

## Where this leaves Stage 8.1
- **Same-class army battles: derived, exact, scale-invariant, fudge-free.** Ready to
  implement as the army-scale backbone (an O(1) closed form — no per-unit loop, no cap).
- **Cross-class army battles: open.** Needs the class-pair rate constants re-derived *in
  the army regime* (they cannot be inherited from the lab), which needs a few more
  class-pair army reports (Inf-v-Lan, Inf-v-MM, Lan-v-MM at matched stats) — a much
  narrower ask than the original 8.0 battery.
- The per-unit sequential-tanking composition model (`army_kill_timeline`) must be
  **replaced** at army scale by the pooled square-law form; it stays valid for small-N.

---

# ADDENDUM — the dig for more class-pair army battles (2026-07-25)

Searched the repo, `E:\WOS\Screeenshots`, `BattleReport Reader`, `SS`, `Dream`, `spikes`.
**Result: FOUR distinct class pairs already exist at army scale, all with stat panels** —
more than I first reported (one set was hidden under a non-standard key).

| file | matchup | scale | panels | observed |
|---|---|---|---|---|
| exp1_mirror_20k | Inf v Inf | 20,000 | yes | attacker 0.24185 |
| exp2_mirror_2k | Inf v Inf | 2,000 | yes | attacker 0.242 |
| exp3a_lancer | **Lan v MM** | 10,000 | yes — under `stats_pct_LEFT/RIGHT_side` (missed by the first scan); class assignment **INFERRED** | attacker 0.42 |
| exp3b_lancer | Lan v MM | 20,000 | **no** | defender 0.248 |
| exp4 / exp4b | Inf v Lan | 10,000 | yes | attacker 0.4536 / 0.4282 |
| exp4c | Inf v Lan (+Gordon) | 10,000 | yes | attacker 0.4533 |
| exp5 | Inf v MM | 10,000 | yes | attacker 0.0488 |
| exp0_beast | Inf v beast | 20,000 | yes | defeat |
| report_001..008 | real PvP, multi-class | ~1.7 M | yes | Type-2 (procs) — distribution-only |

## Cross-class remains OPEN across all four pairs
Blind-tested the square law three ways on every cross-class anchor (frozen K+G; K only;
pure stats). **No variant fits:**

| anchor | observed | K+G | K only | pure stats |
|---|---|---|---|---|
| Inf v Lan (exp4) | att 0.454 | def ✗ | att +91 % | def ✗ |
| Inf v MM (exp5) | att 0.049 | def ✗ | def ✗ | def ✗ |
| Lan v MM (exp3a) | att 0.420 | att +73 % | def ✗ | att −19 % |
Confirms the finding: **the lab-regime K-table and tier damping do not transfer to army
scale**, and no simple on/off of those factors rescues it. Not re-fitted (no-regression rule).

## Two data-hygiene problems found in the dig
1. **`backtest.py`'s "mirror (inf v inf)" composition anchor is MIS-PAIRED.** It builds the
   mirror from exp4's panels (Inf 199.2/192.0/119.7/119.3) but targets **24.0 %**, which
   came from the exp1 encampment mirror whose panels are **different** (176.2/169.0/109.7/
   109.3). The square law gives 0.330 for the backtest panels and 0.2417 for exp1's own
   panels (observed 0.24185) — i.e. the law is right and **the anchor's stats and target
   belong to two different battles.** That anchor is unreliable as a magnitude gate.
2. **A multi-class army battle was OVERWRITTEN and is LOST.** `exp3a_lancer.json`'s
   `NEEDS_CONFIRMATION` records that the file's original content was a *different* battle —
   **20k MIXED: (5k Inf + 15k Lancer) vs (5k Inf + 15k Marksman), Marksman DEFENDER won
   8,302 = 41.5 %** — and that it "must be re-recorded separately." That is exactly the
   multi-class army-scale Type-1 anchor Stage 8.1 needs, and its screenshots should still
   exist in the Calibration PDFs.

## Revised asks for Martin — recoverable from EXISTING screenshots, no new battles
1. **Re-record the overwritten mixed 20k battle** (5k Inf+15k Lan vs 5k Inf+15k MM,
   Marksman defender won 41.5 %) — the single most valuable missing anchor.
2. **Confirm exp3a's class assignment** (which side deployed Lancer vs Marksman) — the file
   flags it as inferred, and it decides the sign of the Lan-v-MM test.
3. **exp3a vs exp3b conflict**: labelled the same setup but opposite winners (42 % attacker
   vs 24.8 % defender). Given #2's overwrite history, exp3b may actually be the mixed
   battle. Needs disambiguation.
4. **Alliance-garrison Inf mirror (+10 pt attacker → 30.2 %)**: outcome is recorded in
   `ENGINE_REBUILD/07_CONTROLLED_EXPERIMENTS.md` but **no raw file/panels exist** — panels
   would give a second same-class blind test of the solved law.

---

# ADDENDUM 2 — Martin's screenshots ingested (2026-07-25)

Three battles OCR'd from Martin's screenshots; new files written to
`wos_sim/data/experiments/`. Every mystery in Addendum 1 is now resolved.

## New files
| file | battle | key numbers |
|---|---|---|
| `exp6a_mixed_20k_run1.json` | **the recovered "lost" mixed battle** (A1), 2026-07-08 21:59:44 | att 5,000 Inf + 15,000 Lancer vs def 5,000 Inf + 15,000 Marksman, Lv 10.0; **defender won 8,302 = 41.51 %**; attacker wiped |
| `exp6b_mixed_20k_run2.json` | **repeat of the same setup** (B1), 22:00:48 | identical setup/stats; **defender won 4,963 = 24.82 %** |
| `exp7_alliance_garrison_mirror_20k.json` | **alliance-garrison Infantry mirror** (A2), 23:27:15, **no heroes** | 20,000 v 20,000 Lv 1.0; **attacker won 6,043 = 30.215 %** |

## Resolution of the three open puzzles
1. **`exp3b` was mislabelled** — it is not a Lancer-v-Marksman repeat, it is the mixed
   battle's second run. Marked `_SUPERSEDED` and pointed at `exp6b`. The "opposite winners"
   anomaly I flagged was purely this mislabelling: exp3a (Lan-v-MM) and exp3b (mixed) are
   different battles. **No physics anomaly.**
2. **`exp3a` class assignment CONFIRMED** (Martin): Lancer = winning/attacking side,
   Marksman = losing/defending side. The earlier inference was right.
3. **The mixed battle is TYPE-2, not deterministic.** Two runs of an *identical* setup gave
   **different** outcomes (defender 8,302 vs 4,963 survivors) because the **troop-skill proc
   counts differed** (Ambusher-side triggers 6 vs 12; Volley-side 6 vs 4). Heroes were
   skill-less (Charlie/Cloris are blue heroes — Martin), so troop skills were the only procs.
   ⇒ These two runs are a **ready-made distribution pair for Stage 8.3**, and must NOT be
   used as exact-fit targets.

## Blind test of the army-scale square law on exp7 (a genuinely new anchor)
Same formula, zero new constants, panels straight off the screenshot:
| | value |
|---|---|
| alpha / beta | 1.124881 / 1.002258 |
| beta/alpha | 0.890991 |
| **predicted attacker fraction** | **0.33017** |
| **observed** | **0.30215** |
| winner | correct (attacker) |
| error on the fraction | **+9.27 %** |

**Interpretation — the residual is diagnostic, not noise.** Closing a +9.27 % gap in the
*fraction* needs only a **~2 % stat correction** (the fraction is `sqrt` of a small number,
so it amplifies stat error ~4-5x): the defender would have to be ~1 % stronger in Defense
*and* Health than its panel shows. And that is exactly what distinguishes the two mirrors:
- `exp1`/`exp2` — explicitly **"no alliance = no garrison research bonus"** → law fits to **+0.07 %**
- `exp7` — inside an **alliance garrison** → law over-predicts the attacker by ~2 % of stat

⇒ Working hypothesis: **the alliance-garrison research bonus is real and is NOT included in
the Stat Bonuses panel.** It is small (~1-2 % on defensive stats here) — nothing like the
`def_k=0.45` handicap, and it applies to the *defender's stats*, not to a fire-rate. This is
a measurable candidate mechanic for Stage 8.2, and it needs one more alliance-garrison
mirror (different stat gap) to pin the magnitude rather than infer it from one battle.

## Still open
- **B3 (beast panels)**: Martin notes Lv 18 beast formations never change, so the panel can
  be lifted from any other Lv 18 Titan Roc report — to do, low priority.
- Cross-class army law: unchanged, still open (Addendum 1, Finding 5).
- `build_corpus.py` has NOT been re-run; the three new files are not yet corpus rows (doing so
  will change row counts that some tests assert — a deliberate, separate step).

---

# ADDENDUM 3 — backbone IMPLEMENTED; the garrison hypothesis is REFUTED (2026-07-25)

## Implementation
`wos_sim/formula_research/stage8_army.py` — the army-scale same-class attrition backbone.
- `rates(att, dfn)` → `alpha = A_att·L_att/(D_def·H_def)`, `beta = A_def·L_def/(D_att·H_att)`
- `continuum_fraction(...)` → Lanchester square law, O(1)
- `predict_army_same_class(...)` → the **discrete** simultaneous-resolution recurrence
  (`N_def(t+1) = N_def − c·alpha·N_att(t)` and symmetrically), casualties removed at turn
  end per GAME_RULES §4. **O(turns), never O(troops)** — a 1,000,000-troop army costs the
  same as 10, and there is no per-unit loop and no cap blow-up.
- `law_rate_scale(cls, tier)` → the absolute rate `c = 1/(K·G_w·G_l)` **taken from the frozen
  per-unit law**, not fitted. Discrete mode *requires* a rate: there is deliberately **no
  default constant**, so no fudge can slip in.

Validation (rate from the law, nothing fitted):
| battle | observed | discrete | turns | continuum |
|---|---|---|---|---|
| exp1 20k encampment mirror | 0.24185 | 0.24079 (−0.44 %) | 593 | 0.24169 (−0.07 %) |
| exp2 2k encampment mirror | 0.24200 | 0.24079 (−0.50 %) | 593 | 0.24169 (−0.13 %) |
| exp7 20k **alliance garrison** | 0.30215 | 0.32913 (**+8.93 %**) | 502 | 0.33017 (+9.27 %) |
Survivor fraction is **constant from N=1,000 to N=1,000,000** — the measured scale-invariance
holds by construction.

## The exp7 residual: what is now RULED OUT
1. **Discretisation — RULED OUT.** With the law's own rate these battles run **502–593 turns**,
   so the discrete form sits essentially at its continuum limit; discreteness moves the
   fraction by only ~0.4 %, not the ~9 % needed.
2. **An "unpanelled alliance/garrison buff" — RULED OUT (Martin was right).** The same two
   players fought exp1 (21:43, alliance-free) and exp7 (23:27, alliance garrison). Comparing
   the Infantry panels between the two reports:
   - attacker gained **exactly +23.0 / +23.0 / +10.0 / +10.0** pp (A/D/L/H) — precisely the
     RFJ alliance buff already recorded in the Stage-6 notes (+23pp A/D, +10pp L/H);
   - defender gained +14.8 / +14.2 / +10.0 / +10.0 pp.
   **The alliance buff IS in the Stat Bonuses panel.** So the residual cannot be a hidden
   alliance/garrison stat bonus, and my Addendum-2 hypothesis is withdrawn.
3. **Wrong deployed class — RULED OUT.** Infantry is the best of the three (Infantry 0.330,
   Marksman 0.422, Lancer 0.584 vs observed 0.302), and a panel column-swap predicts a
   *defender* win, contradicting the report.
4. **Tier — RULED OUT algebraically.** In `beta/alpha` the base stats cancel exactly for a
   same-class same-tier matchup (verified numerically: identical ratio at T1 and T10), so the
   exp1/exp7 tier difference cannot produce it.

## What remains (honest, N=2 cannot separate them)
- **(a) A garrison-CONTEXT combat term** — not a stat bonus but a battle-time defensive
  effect in an alliance garrison, worth ~2 % of defender stat here. Distinct from the alliance
  buff, which is in-panel. Note exp7 had **no heroes**, so the §3 widget asymmetry cannot be it.
- **(b) The law's form** `A·L/(D·H)` being slightly approximate as the stat gap widens.
  Counter-evidence: the *sensitivity* argument runs the wrong way — exp1 has the **smaller**
  gap (beta/alpha 0.9416, hence a MORE sensitive sqrt) and fits exactly, while exp7 (0.8910,
  less sensitive) misses. A pure noise story would predict the opposite.

**The discriminator:** one more **alliance-free encampment** mirror with a *different* stat
gap. If the law fits it exactly, the battle CONTEXT is the variable ⇒ (a). If it misses by a
similar margin, the form needs refinement ⇒ (b). Also worth confirming exp1's formation icons
show the **same tier on both sides** (its screenshot was never captured; the tier label in the
file is already known-doubtful — power-loss per troop matches the Lv 10.0 mixed battles, not Lv 1.0).

---

# ADDENDUM 4 — exp1/exp2 screenshots verified (2026-07-25)

Martin supplied the exp1 (21:43:41) and exp2 (21:52:11) reports. **The load-bearing
assumption is CONFIRMED and one of my own inferences is retracted.**

## Confirmed
- **Formation icon row: ONE Infantry stack per side, "Lv 1.0", on BOTH sides** — exp1
  20,000 v 20,000, exp2 2,000 v 2,000. This was the whole point of the re-capture: the
  tiers are identical on both sides, so the base stats cancel exactly in `beta/alpha`
  and the same-class law's **−0.07 % fit on exp1 is sound, not a coincidence**.
- **No heroes** (Martin-confirmed; no Skill Details panel in either report).
- Stat Bonuses panel, casualties and survivors all match the file exactly. Report owner is
  Colonel Müller (defender, left/green column); the file's attacker/defender panel
  assignment was already correct.
- **Power loss also scales 10×**: −15,924 / −1,593 = 9.996 and −21,000 / −2,100 = 10.000,
  reinforcing the exact scale-invariance from a fourth independent quantity.

## Retracted (my error)
I earlier wrote that exp1's power-loss-per-troop "matches the Lv 10.0 mixed battles, so the
tier label is doubtful and exp1 is probably T10." **That was my own misreading** — I had
conflated the mixed battle's −497,000 (exp6a/exp6b) with exp1's file value, which was
**already correct at −15,924**. The tier label was never wrong: exp1/exp2 are genuinely
**Lv 1.0**. Nothing in the analysis depended on the mistaken claim (the ratio cancels tier
either way), but the note is corrected in both JSONs.

## Net effect on the open question
exp1/exp2 (Lv 1.0, alliance-free) and exp7 (Lv 1.0, alliance garrison) are **the same tier**,
so tier is definitively not the confound. The exp7 +9 % residual still has exactly two
candidates — a garrison-context battle-time term, or the law's form — and the discriminator
is unchanged: **one more alliance-free encampment mirror with a different stat gap.**

## exp0 (beast) — closed as not needed
Martin: beast reports expire quickly and would have to be replicated. **Not worth it.** The
beast branch is irrelevant to the army-scale troop law (beasts are a separate PvE regime,
already covered by the C6 beast bucket), and B3's original ask (Lv 18 panels) is satisfiable
from any other Titan Roc report if that branch ever matters.

---

# ADDENDUM 5 — the backbone is WIRED behind api.py (2026-07-25)

`wos_sim/predictor/army_router.py`, dispatched from `api.predict()` immediately after
the Type-1 router. Additive only: `predict()`'s existing behaviour is untouched for every
matchup outside the new domain, and `params={"army_router": False}` forces the old path.

## Domain (deliberately narrow)
Both sides deploy **one class, the SAME class, at the SAME tier**; proc-free (tier <= 6,
fc < 3); **no heroes / joiners / buffs**; and **>= 1,000 troops per side** (below that the
small-N composition regime still owns it). Cross-class stays on the turn engine — the lab
K-table does not transfer (Finding 5).

## Response contract
`engine_path="army_law"`, `stochastic=False`, `calibrated=False`,
**`confidence="directional"`** (never "validated"), **`model_error=0.10`**. The band is 10 %
because the app's battles are *garrison* battles and the garrison anchor is the one that
runs +8.93 % — declaring 3 % would be dishonest. A knife-edge stat ratio (winner fraction
< 10 %) is reported as `coin_flip` at p=0.5 rather than a confident call.

## Verification
| check | result |
|---|---|
| exp1 20k mirror through the seam | `army_law`, own_surv 0.24079 vs observed 0.24185 (**−0.44 %**) |
| exp2 2k mirror through the seam | identical fraction (**scale-invariance holds end-to-end**) |
| exp7 garrison mirror | 0.32913 vs 0.30215 (+8.93 %, inside the declared band) |
| T12/FC10, cross-class, cross-tier, small-N, heroes, joiners, buffs | all correctly **rejected** |
| opt-out param | falls back to `pvp_turn_engine` |
| **G12 backtest** | **PASS, 7/13 winners unchanged** |
| full suite | **195 passed**, 15 skipped, 2 xfailed (15 new army-router tests) |
| UI style guard | 7 passed (front-end untouched) |

## Bonus fix — the mis-paired backtest anchor
`backtest.py`'s `COMPOSITION_ANCHORS["mirror (inf v inf)"]` target was corrected
**24.0 % -> 30.2 %**. Its profiles are built from AP/DP (= exp7's panels), so its real
observed value is exp7's 30.2 %; the old 24.0 % came from exp1, a different mirror with
different panels. The row was unmeetable by construction. It now reads 32.9 % engine vs
30.2 % real — the honest +8.9 % gap instead of a phantom 37 % one. (Report-only line; the
PASS/FAIL gate is the winner lock, which is unaffected.)

---

# ADDENDUM 6 - independent QA: NOT APPROVED; live routing DISABLED (2026-07-25)

An independent QA reviewed the wiring and returned **"do not approve for the live
prediction path"** with four P1 defects. **The QA is correct on every count.** Live
routing is now **OFF by default** (`params={"army_router": True}` to enable); the
backbone remains for research and for the fixes below. No user prediction depends on it.

## Verified and fixed immediately
| # | QA finding | Verification | Fix |
|---|---|---|---|
| P1-1 | The 1,500-turn cap **fabricated winners**: with both sides alive it broke the tie toward the attacker and the router then zeroed the "loser" - two identical sides at 19,191.91 troops were reported as a 100% attacker win. | **CONFIRMED, and worse than a heuristic slip:** `GAME_RULES.md` s.424 (Martin-confirmed) states *"every battle ends in a wipe of at least one side - no exceptions, no turn cap, no retreat."* The cap contradicts a confirmed rule. | The capped state now returns `winner="uncertain"` with **both** survivor counts preserved; the router abstains and falls through. Regression-tested. |
| P1-2 | **Unequal FC leaked in**: the classifier bounded FC but never required equality, while the research base table varies with FC below T10 (the production catalog ignores FC at T1-T9). FC1-v-FC2 **reversed the winner**. | CONFIRMED. This also breaks the "base stats cancel" precondition the whole derivation rests on. | Classifier now rejects `cross_fc`; the silent `int(fc) or 1` coercion is removed. Regression-tested. |
| P1-3 | The +-10% band and the 0.10 coin threshold are **not calibrated**: applying exp7's own residual to a nominal 12% attacker win **flips the winner**, and `p_win=0.5` serialises with `p_loss=0`/`p_mutual=0` (mass sums to 0.5). | CONFIRMED (mass = 0.5 reproduced). Note the probability-contract half is **pre-existing** - `type1_router` uses the same `win_prob_override=0.5` - so it is a contract-level issue, not one this change introduced. | Routing disabled; band not shippable until more independent configurations exist. Contract issue logged for a separate, deliberate fix across both routers. |
| P1-4 | The 999/1,000 seam changed predictions discontinuously (58.18% -> 24.08% survival, p 0.55 -> 1.00, 35 -> 593 rounds) below the lowest measured anchor (2,000). | CONFIRMED - I had disclosed the cliff but under-weighted it. | Routing disabled; the threshold stays unsupported until a measured regime boundary exists. |
| P1-5 (UI) | The banner's "winner is derived" / "+-10%" copy overstated the evidence. | CONFIRMED. | Re-worded to "Experimental ... derived from only two measured configurations - treat both the winner and the survivor magnitude as provisional." |

## Accepted, not yet fixed (tracked)
- **P2-6 `/api/battle` vs `/api/predict` diverge.** `server.py` promises the timeline
  reproduces the forecast, but `api.battle_timeline` always runs the turn engine. With
  routing off this is dormant; it must be resolved before routing is ever re-enabled
  (route both through the same engine, or reject timeline requests for `army_law`).
- **P2-5 discrete-mode generality.** The "~0.4% discretisation" claim is Infantry-specific;
  QA measured -3.66% (Lancer T1) and -6.23% (Marksman T4). The module also contradicts
  itself (docstring says 6-12-turn battles, the validation prints 500-800). Prefer the
  continuum result and drop round predictions until an army clock is measured.
- **P3-7** `exp3b_lancer` (= stochastic exp6b) is still a Type-1 corpus row; harmless today
  (no usable inputs, skipped by validators) but should be reclassified on the next rebuild.

## What the QA CONFIRMED as sound
- The algebra: alpha/beta and the linear-vs-sqrtN discrimination reproduce exactly
  (0.241685 / 0.150545 vs observed 0.241850); the general form is `(1-beta/alpha)^(1/(p+1))`.
- Base stats cancel **only when both sides share the same base vector** - which is precisely
  why the FC fix was required.
- The 10x scale-invariance ratios.
- **The `24.0 -> 30.2` backtest anchor correction is VALID, not fudged** - AP/DP match exp7's
  panels and 6,043/20,000 = 30.215%; the model still prints 32.9%, so the target was not
  moved to fit the model. (QA suggests the row should also replay exp7's real T1/20k profile
  rather than T6/10k - a further improvement, not a defect.)
- **No hidden outcome-fitting**: `_solve_rate()` is defined but never referenced in the
  shipped path. Fair caveat accepted: the discrete response is not literally "zero fitted
  constants" - it consumes empirical `K/G` table values plus judgment constants (minimum
  size, error band, coin threshold), which should be described that way in future.

## Status
Guardrails after the fixes: **G12 backtest PASS**, **199 passed** / 15 skipped / 2 xfailed
(4 new QA regressions), style guard 7 passed, encoding clean. The live path is byte-identical
to pre-8.1 behaviour for every user request.

---

# ADDENDUM 7 - QA second pass: containment APPROVED; two more fixes landed (2026-07-25)

QA re-ran and **approved the fixes for the current live path** ("Stage 8.1 is now genuinely
opt-in and unreachable through the deployed API"), while **not approving re-enable**. Two
further findings were actioned; the rest are tracked as explicit re-enable gates.

## Fixed now

**1. The invalid probability distribution - this one was LIVE (QA P2 current / P1 before re-enable).**
`summarize()` applied `win_prob_override` to `p_win` but left `p_loss`/`p_mutual` at their
raw Monte-Carlo values, so the serialized distribution did not sum to 1. This was **not a
Stage 8.1 defect** - it affected the **deployed turn-engine path today**: a near-deterministic
own-win with the coin-flip override emitted `0.55 + 0 (loss) + 0 (mutual) = 0.55` to every
direct API consumer. The front-end never showed it because `index.html` derives loss as the
complement itself. Fixed in `summary.py`: an override now normalizes - mutual is preserved
(a genuinely distinct outcome) and loss takes the remainder; the effective pair is
normalized too. **Verified live: 0.55 + 0.45 + 0 = 1.0.** New `test_probability_contract.py`
pins 0 / 0.45 / 0.5 / 0.55 / 1.0 plus the no-override case (10 tests).

**2. The router now uses the CONTINUUM result and reports no turn count** (QA P2 x2).
This closes two findings at once:
- the discrete mode needed `c = 1/(K*G_w*G_l)`, whose transfer from the 1-6-unit lab to army
  scale is **unmeasured**;
- it made the answer depend on the research base table's sub-T10 **FC dependence**, which the
  production catalog says does not exist (FC ignored at T1-T9). Even with EQUAL FC the
  discrete result moved (Lancer T1 23.28% @FC1 vs 23.06% @FC2), and the turn counts moved far
  more.
The continuum result depends only on `beta/alpha`, where the base product cancels exactly, so
it is the honest estimator. **No turn count is claimed any more** (the army clock is
unmeasured). The note text now says EXPERIMENTAL, names the two-configuration evidence base,
and calls both winner and magnitude provisional.

## Tracked as explicit RE-ENABLE GATES (not fixed, not live)
| gate | why it blocks |
|---|---|
| Uncalibrated band + 0.10 coin threshold + the 999/1,000 cliff | needs more independent stat configurations and a measured regime boundary; an exp7-style residual flips a nominal 12% attacker win |
| `/api/battle` cannot reproduce an `army_law` forecast | `server.py` promises the timeline matches the forecast; dormant only because the server never passes `army_router=True` |
| No Stage 8.1 regression coverage in the mandatory backtest | `backtest.py` supplies `{"engine": "turn"}`, so the opt-in law has no guardrail; needs a separate research backtest at `army_router=True` using exp7's real T1/20k profile, plus Lancer/Marksman/threshold/timeline cases |
| Production canonical base-stat source | the continuum sidesteps it today, but any future discrete mode must use the production catalog, not the research table |
| `exp3b_lancer` still a Type-1 corpus row | it is the stochastic exp6b; reclassify on the next corpus rebuild |

## Guardrails after this round
**G12 backtest PASS** (7/13) - **209 passed** / 15 skipped / 2 xfailed - style guard 7 -
encoding clean - `git diff --check` clean (CRLF notices only). The deployed path is
byte-identical to pre-8.1 **except** the probability-distribution fix, which is a strict
correctness improvement for API consumers.

---

# ADDENDUM 8 - cross-class derivation attempt (2026-07-25)

Promised outcome: **either a working cross-class form, or a precise experiment list.**
Result: **the framework is validated, the closed form is not** - and the remaining ask is
now TWO battles instead of a guessed battery.

## The setup (zero new constants introduced)
If each attack direction carries a class-pair factor `C(attacker -> defender)`, then in
`beta/alpha` only the RATIO survives:
```
beta/alpha = S(stats) * R      where  S = (A_d L_d D_d H_d)/(A_a L_a D_a H_a)
                                      R = C(def->att) / C(att->def)
```
Same-class gives `R = 1`, which is why the same-class law worked with no extra term.
Each observed battle therefore MEASURES its pair's R via `R = (1 - f^2) / S`.

| battle | pair | S | **R measured** |
|---|---|---|---|
| exp4 | Inf -> Lan | 1.00169 | **0.7929** |
| exp4b | Inf -> Lan | 1.03856 | **0.7863** |
| exp5 | Inf -> MM | 1.23774 | **0.8060** |
| exp3a | Lan -> MM | 0.88398 | **0.9317** |

## RESULT 1 - the framework is CONFIRMED
`exp4` and `exp4b` are the same class pair with **different defender panels**, and they
return the same R to **0.83 %**. A single multiplicative per-pair constant on top of the
square law reproduces cross-class battles. That is a real, reproducible structure - not a fit.

## RESULT 2 - the factorization is REFUTED (the zero-parameter blind test)
If `C(X->Y) = f(X)g(Y)` then `R(a,d) = h(d)/h(a)`, which forces the triangle identity
`R(Inf,Lan) x R(Lan,MM) = R(Inf,MM)`. Solving the first two from exp4 + exp3a and
blind-predicting the third:
```
predicted R(Inf,MM) = 0.7929 x 0.9317 = 0.7388
measured  R(Inf,MM) =                   0.8060      ERROR -8.34%
=> predicted exp5 survivor fraction 0.2926 vs observed 0.0488
```
**REJECTED.** R cannot be decomposed into per-class factors; the three pairs are independent.

## RESULT 3 - simpler forms also fail
| hypothesis | verdict |
|---|---|
| R = one global constant | R spans 0.786 - 0.932; misses Lan->MM by **-14.9 %** |
| R = r(attacker class) only | identical failure on exp5 (**+179 %** on the fraction) |
| R independent per pair | fits by construction - 3 constants, **only 1 real check** |

## RESULT 4 - a structural insight that matters more than the constants
**exp5 is hypersensitive and must never be used as a magnitude anchor.** Its observed
`f = 0.0488` implies `beta/alpha = 0.99762` - within **0.24 %** of exact parity. Because
`f = sqrt(1 - beta/alpha)`, a **1.6 %** error in R becomes a **179 %** error in the survivor
fraction. This also re-frames the earlier "+794 %" cross-class miss: much of it was exp5's
sensitivity, not proof of a wildly wrong model. exp5 IS an excellent **winner-boundary**
anchor (it pins where the flip happens) - it is just useless for calibrating magnitude.

## Status: NOT shippable, and deliberately not shipped
Three constants supported by one independent check is exactly the "fit what you have" trap
that produced `def_k`. No R values have been written into the engine.

## THE ASK - two battles, not a battery
Each is the exact analogue of what exp4b already did for Inf-v-Lan: **the same class pair at
a DIFFERENT stat gap**, which converts a fitted constant into one with an independent blind check.

| # | battle | why |
|---|---|---|
| **X1** | **Lancer vs Marksman**, ~10k each, Lv<=6, no heroes, deterministic - stats deliberately DIFFERENT from exp3a | gives R(Lan,MM) its first check; currently a single unverified point |
| **X2** | **Infantry vs Marksman**, ~10k each, same conditions, stats DIFFERENT from exp5 - ideally NOT near-parity (aim for a decisive gap) | gives R(Inf,MM) its first check, and escapes exp5's hypersensitivity |

With those two, the cross-class model becomes 3 constants each carrying an independent
blind check - the same evidential standard the same-class law now meets.

---

# ADDENDUM 9 - X1/X2 delivered: the cross-class law is now MEASURED WITH CHECKS (2026-07-28)

Martin captured both requested battles. New files: `expX1_lan_vs_mm_10k.json`,
`expX2_inf_vs_mm_10k.json`. **Both blind checks pass**, and every class pair now carries
two independent measurements.

| battle | pair | setup | observed f |
|---|---|---|---|
| **X1** | Lan -> MM | 10k v 10k Lv6, no heroes; defender MM Defense **174.2** (vs exp3a's 155.7) | attacker **0.3013** |
| **X2** | Inf -> MM | 10k v 10k Lv6, no heroes; defender is a **near-zero-stat account** (+2% Atk, 0% else) - deliberately far from parity | attacker **0.9841** |

## The blind checks
| pair | prior | new | agreement |
|---|---|---|---|
| Inf -> Lan | exp4 0.7929 | exp4b 0.7863 | **0.83 %** |
| Inf -> MM | exp5 0.8060 | **X2 0.7859** | **2.49 %** |
| Lan -> MM | exp3a 0.9317 | **X1 0.9592** | **2.90 %** |

**The standout:** predicting X2's survivor fraction from **exp5's R alone** - a battle
measured months earlier, at a completely different stat gap - gives **0.9837 vs observed
0.9841, a 0.04 % blind prediction.** That is the strongest single confirmation the
cross-class framework has produced, and it works precisely because X2 is far from parity so
model error is not amplified.

## Full validation - all six cross-class battles, each pair's MEAN R
| battle | pair | predicted f | observed f | error |
|---|---|---|---|---|
| exp4 | Inf->Lan | 0.4572 | 0.4536 | **+0.8 %** |
| exp4b | Inf->Lan | 0.4242 | 0.4282 | **-0.9 %** |
| exp5 | Inf->MM | 0.1217 | 0.0488 | +149.5 % (NEAR-PARITY, see below) |
| X2 | Inf->MM | 0.9839 | 0.9841 | **-0.0 %** |
| exp3a | Lan->MM | 0.4053 | 0.4200 | **-3.5 %** |
| X1 | Lan->MM | 0.3222 | 0.3013 | **+6.9 %** |

**Five of six within 7 %.** The exp5 outlier is fully explained and was predicted in advance:
its R is only 2.5 % from the pair mean, but at `beta/alpha = 0.9976` (0.24 % from parity) the
`sqrt` amplifies that into 149 %. exp5 remains a valid **winner-boundary** anchor and an
invalid **magnitude** anchor - exactly as Addendum 8 stated before X2 existed.

## The measured cross-class law
```
beta/alpha = S(stats) * R(attacker_class, defender_class)
S = (A_d L_d D_d H_d) / (A_a L_a D_a H_a)
R:  Inf->Lan 0.7896 | Inf->MM 0.7959 | Lan->MM 0.9454   (same class = 1; reverse = 1/R)
```
Measured at **tier 6, 10k scale, proc-free, hero-free**. Each constant has an independent check.

## What is still NOT established
- **The factorization stays REFUTED.** With the improved values,
  `R(Inf,Lan) x R(Lan,MM) = 0.7465` vs measured `R(Inf,MM) = 0.7959` (**-6.2 %**). R does not
  decompose per class; all three pairs must be measured (they now are).
- **Tier dependence is unknown.** Every one of the six battles is tier 6. R may vary with tier.
- **Only two measurements per constant.** Better than the same-class law's evidence base, but
  the QA's standard for LIVE routing has not obviously been met.
- **This is NOT the whole of Stage 8.1.** It solves *single-class-vs-single-class* cross-class.
  TRUE multi-class composition (Inf+Lan+MM mixed on one side, absorption order, tanking) is
  still open, and the only multi-class army data (exp6a/exp6b) is Type-2/stochastic.

## Verdict
The **cross-class half of 8.1 is derived and checked**; the **multi-class-composition half
remains open**. Nothing has been wired into the engine - the R values live in this document
pending a decision and an independent QA.

---

# ADDENDUM 10 - the cross-class law is IMPLEMENTED (2026-07-28)

Wired into `stage8_army.py` and `army_router.py`. **Still opt-in** (`params={"army_router":
True}`); the live path is unchanged.

## What was added
- `R_TABLE` with per-pair provenance - each entry carries **both** measurements and the
  battles they came from:
  | pair | R | measurements | sources |
  |---|---|---|---|
  | Inf -> Lan | 0.7896 | 0.7929 / 0.7863 | exp4, exp4b |
  | Inf -> MM | 0.7959 | 0.8060 / 0.7859 | exp5, expX2 |
  | Lan -> MM | 0.9454 | 0.9317 / 0.9592 | exp3a, expX1 |
- `class_pair_R()` - same class returns exactly `(1.0, 0.0)`; the reverse direction is the
  reciprocal (`R(Y,X) = 1/R(X,Y)`, which follows from R's definition, not from a fit).
- `predict_army_cross_class()` - continuum only, no turn count claimed.

## The abstention is DERIVED, not a threshold (answers QA P1-3)
The router refuses to call a battle when `beta/alpha` sits **within the measured R spread**
of 1.0 - i.e. exactly where the two-measurement uncertainty could flip the winner. This is
the exp5 lesson made mechanical: at `beta/alpha = 0.9851` a 2.53 % uncertainty in R spans
the parity line, so no honest winner exists. **exp5 now abstains instead of being 149 % wrong.**

## Validation through the implemented path
| battle | pair | predicted | observed | error |
|---|---|---|---|---|
| exp4 | Inf->Lan | 0.4572 | 0.4536 | **+0.8 %** |
| exp4b | Inf->Lan | 0.4242 | 0.4282 | **-0.9 %** |
| exp5 | Inf->MM | **ABSTAIN** | 0.0488 | - (correctly refused) |
| expX2 | Inf->MM | 0.9839 | 0.9841 | **-0.0 %** |
| exp3a | Lan->MM | 0.4053 | 0.4200 | **-3.5 %** |
| expX1 | Lan->MM | 0.3222 | 0.3013 | **+6.9 %** |

## Guards (all tested)
Off-tier cross-class rejected (`cross_class_tier`); unmeasured pair rejected
(`cross_class_unmeasured`); reciprocal and same-class identity asserted; cross-class without
the opt-in flag still routes to the old engine.

## Gates
G12 backtest **PASS** (7/13) - **214 passed** / 15 skipped / 2 xfailed (5 new cross-class
tests) - live path verified unchanged.

## Unchanged limits
Tier 6 only; two measurements per constant; **multi-class composition (mixed Inf+Lan+MM on
one side) is still not implemented** - that is the remaining half of Stage 8.1 and its only
data (exp6a/exp6b) is Type-2.

