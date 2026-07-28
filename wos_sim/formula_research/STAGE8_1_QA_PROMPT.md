# QA PROMPT — Stage 8.1 army-scale law + its live wiring

**Repo:** `E:\WOS\Battle Simulator` (Python; run everything with
`PYTHONPATH="E:\WOS\Battle Simulator"`).
**Your role:** independent, adversarial QA. Two previous rounds of this project's QA each
found real P1 defects in the author's work — assume this one has them too. **Do not trust
the author's numbers: recompute them.** Reporting "no findings" when a defect exists is the
worst outcome; reporting a defect the author already disclosed is fine and useful (confirm
or refute it).

---

## 1. What changed, and the claim being made

Until now, every army-scale battle in this app was predicted by the legacy turn engine via
**`def_k = 0.45`** — a flat "defender deals 45 % of the attacker's per-capita damage"
handicap with no physical basis (`wos_sim/pvp_turn_engine.py`, `TURN_PARAMS`). The author
claims to have **derived** a replacement for one narrow regime and wired it into the live
prediction path.

**The claim, precisely:**
> For a proc-free, hero-free, **same-class same-tier** battle at army scale, the outcome is
> set by the stat ratio alone and is exactly scale-invariant. With
> `alpha = A_att·L_att/(D_def·H_def)` and `beta = A_def·L_def/(D_att·H_att)`, the winner's
> surviving fraction is `sqrt(1 − beta/alpha)` (equal counts), i.e. Lanchester's **square
> law** with **linear** troop pooling. **Zero fitted constants.** `def_k` is unnecessary.

**Files under review**
| file | what it is |
|---|---|
| `wos_sim/formula_research/stage8_army.py` | the derived backbone (continuum + discrete forms, law-derived rate scale) |
| `wos_sim/predictor/army_router.py` | classifier + seam mapping onto the existing Forecast contract |
| `wos_sim/predictor/api.py` | the dispatch (search `army_router`) |
| `wos_sim/predictor/tests/test_army_router.py` | the author's 15 tests |
| `wos_sim/formula_research/STAGE8_1_FINDINGS.md` | the full evidence trail (Addenda 1–5) |
| `wos_sim/backtest.py` | one anchor target was changed (24.0 → 30.2) |
| `prototype/index.html` | `renderMeta` — banner copy now branches on `army_law` |
| `wos_sim/data/experiments/exp1_mirror_20k.json`, `exp2_mirror_2k.json`, `exp7_alliance_garrison_mirror_20k.json`, `exp6a_mixed_20k_run1.json`, `exp6b_mixed_20k_run2.json` | the anchors (exp6/exp7 newly OCR'd from screenshots this session) |

## 2. The ground truth you should verify against

Real in-game battles, deterministic (no procs), no heroes, single Infantry stack per side,
**Lv 1.0 both sides**:

| anchor | setup | observed |
|---|---|---|
| exp1 | 20,000 v 20,000, alliance-free encampment. Att panels Inf **176.2 / 169.0 / 109.7 / 109.3** (A/D/L/H %), def **174.3 / 153.0 / 112.0 / 108.7** | attacker survivors **4,837 = 0.24185**; defender 0 |
| exp2 | same players/stats, 2,000 v 2,000 | attacker **484 = 0.242**; defender 0 |
| exp7 | 20,000 v 20,000, **alliance garrison**, no heroes. Att **199.2 / 192.0 / 119.7 / 119.3**, def **189.1 / 167.2 / 122.0 / 118.7** | attacker **6,043 = 0.30215**; defender 0 |

Cross-class army anchors (NOT covered by the new code, but relevant to §4.7):
exp4 Inf-v-Lan 10k → att 0.4536 · exp4b → 0.4282 · exp5 Inf-v-MM 10k → 0.0488 ·
exp3a Lan-v-MM 10k → att 0.420.

## 3. Commands

```
PYTHONPATH="E:\WOS\Battle Simulator" py -m wos_sim.formula_research.stage8_army
PYTHONPATH="E:\WOS\Battle Simulator" py -m wos_sim.backtest
PYTHONPATH="E:\WOS\Battle Simulator" py -m pytest wos_sim/predictor/tests/ wos_sim/formula_research/ -q
PYTHONPATH="E:\WOS\Battle Simulator" py -m pytest wos_sim/predictor/tests/test_ui_style_guard.py -q
```
Author's reported results: backbone validation prints exp1 −0.44 % / exp2 −0.50 % /
exp7 +8.93 % (discrete) · **backtest PASS, 7/13 winners** · **195 passed**, 15 skipped,
2 xfailed · style guard 7 passed.

## 4. Attack list — the author's self-disclosed weaknesses. Confirm or refute EACH.

1. **The evidence base may be thinner than it looks.** exp1 and exp2 are *the same battle at
   10× scale* — arguably **one** independent stat configuration (it validates scale-
   invariance, not the formula's shape). exp7 is the second, and it is **+8.93 % off**. Is a
   law resting on two configurations, one of which misses, defensible in the LIVE path?
   Is `confidence="directional"` + `model_error=0.10` an honest declaration of that, or
   should this be gated off until a third configuration exists?
2. **`ARMY_MIN_TROOPS = 1000` is a judgment call, not measured** (lowest anchor is 2,000).
   It creates a **discontinuity**: 999 troops → turn engine (`def_k`), 1,000 → army law.
   Quantify the jump for an otherwise identical matchup. Is a cliff that size acceptable,
   and is 1,000–2,000 extrapolation disclosed?
3. **`model_error = 0.10` barely covers the +8.93 % residual.** Stress it: find a stat
   configuration where the law's error would exceed 10 % if the exp7-style residual is a real
   effect rather than noise. Is the band falsifiable/honest?
4. **`COIN_FLIP_FRACTION = 0.10` is arbitrary and unmeasured.** What does it do to battles
   near the boundary? Is a genuinely decisive battle ever mislabelled a coin flip, or vice versa?
5. **Silent coercions / unchecked fields.** `army_router._eff` does `int(fc) or 1` (FC0 → FC1).
   The classifier checks tier and fc but **not `t12_stack`**. Any other field it ignores that
   changes the physics (`stats_mode`, `panel_is_final`, `widgets_in_panel`, formation
   fractions vs `formation_counts`)?
6. **Production behaviour change.** `wos_sim/predictor/gate.py` enforces a **1,000-troop
   minimum on the deployed site**, exactly equal to `ARMY_MIN_TROOPS`. Trace what the
   deployed app now returns that it did not before. Is anything user-visible wrong?
7. **Is the continuum-vs-discrete choice sound?** The author defaults to a discrete
   simultaneous recurrence (`N_def(t+1) = N_def − c·alpha·N_att(t)`, both from start-of-turn
   counts) and claims it is faithful to `GAME_RULES.md` §4 (simultaneous resolution,
   casualties removed at turn end). Verify the recurrence, and verify the claim that
   discreteness contributes only ~0.4 % here (the author says these battles run 502–593
   turns, so the discrete form sits near its continuum limit). Also check `law_rate_scale`
   = `1/(K·G_w·G_l)` really follows from the frozen per-unit law rather than being a
   convenient choice.
8. **Was anything FITTED?** The project's binding rule is **no regression-fitting** (see
   `ENGINE_REBUILD/ENGINE_CHANGE_CHECKLIST.md`). The author asserts zero fitted constants.
   Audit for hidden fitting: was any constant chosen *because* it reproduced an observed
   outcome? Note there is a `_solve_rate()` helper in `stage8_army.py` — check whether its
   output is used anywhere in the shipped path (the author says no, and that discrete mode
   deliberately has no default rate constant). Confirm or refute.

## 5. Independent recomputation (do this by hand / your own script, not the author's)

- Compute `alpha`, `beta`, `beta/alpha` and `sqrt(1 − beta/alpha)` for **exp1** and **exp7**
  from the panels in §2. The author claims **0.24169** (vs observed 0.24185, +0.07 %) and
  **0.33017** (vs 0.30215, +9.27 %). Confirm to 4 decimals.
- Verify the author's discrimination of pooling laws: linear ⇒ `sqrt(1 − beta/alpha)` = 0.2417
  vs √N ⇒ `(1 − beta/alpha)^(2/3)` = 0.1506, observed 0.24185. Is the algebra right, and does
  it genuinely refute √N at army scale?
- Verify the claim that **base stats cancel** in `beta/alpha` for a same-class same-tier
  matchup (the author uses this to argue the tier label is irrelevant). Prove or disprove
  algebraically.
- Verify the **scale-invariance** claim from the raw data: every casualty ratio between exp1
  and exp2 should be ~10.0.
- Verify the author's **retracted** claim about exp1's power loss (they earlier said
  −497,000 implied T10; they now say the file always held −15,924 and the retraction is
  theirs). Check the file and the screenshots-derived values agree.

## 6. Also check

- **Seam discipline:** `predict()` must be unchanged for every matchup outside the new
  domain; `params={"army_router": False}` must restore the old path exactly. The standing rule
  is *engine only through `api.py`* — confirm `server.py` and the prototype were not made to
  depend on the new path.
- **Rejection completeness:** T7+, FC≥3, cross-class, cross-tier, multi-class, heroes,
  joiners, buffs, sub-1,000 counts must all fall through. Try to find a matchup that
  **leaks** into `army_law` when it shouldn't, or is **wrongly rejected** when it should qualify.
- **The changed backtest anchor** (`COMPOSITION_ANCHORS["mirror (inf v inf)"]`, 24.0 → 30.2).
  The author argues the row was mis-paired: its profiles are built from AP/DP, which are
  exp7's panels, so its true observed value is exp7's 30.2 %, while the old 24.0 % came from
  exp1 (different panels). **Verify this independently** — if the author is wrong, they have
  just moved a target to match their own model, which would be a serious no-fudge violation.
- **The banner copy** (`prototype/index.html`, `renderMeta`): `army_law` must NOT claim to run
  on "the older engine", `deterministic_law` must still suppress the strip entirely, and the
  turn-engine wording must be unchanged. Style guard must stay green.
- **Newly OCR'd anchors:** spot-check `exp6a`/`exp6b`/`exp7` JSONs against the numbers in
  §2 and the author's claim that exp6a/exp6b are **Type-2 (stochastic)** — identical setups
  that produced different outcomes (defender 8,302 vs 4,963) because troop-skill proc counts
  differed (6 vs 12, and 6 vs 4). If so they must never be used as exact-fit targets; confirm
  nothing does.

## 7. Output

For each finding: **severity (P1 blocking / P2 / P3)**, `file:line`, what is wrong, the
evidence (a command or computation someone else can rerun), and the minimal fix. Then:
- a one-line **verdict**: approve for the live path, or not, and why;
- an explicit **confirm/refute for each of the eight items in §4**;
- your recomputed numbers from §5 next to the author's.

State plainly if you believe the law is **not yet safe for the live prediction path** even
though the tests pass — "tests pass" is not the bar; the bar is whether a user's prediction
is honestly derived and its uncertainty honestly declared.
