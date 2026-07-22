# Stage 6.8 — the Type-1 router into the app's `predict()` path

Status: **DONE (builder). Awaiting eval-6.8.**

## Goal (recap)

When a submitted matchup is Type-1-classifiable and inside the frozen
deterministic law's validated domain, `api.predict()` should serve the law's
exact result through the *existing* Forecast/serialize/UI contract. Everything
else keeps running the stochastic turn/general engine byte-identically.
`server.py` and `prototype/index.html` are untouched.

## Files touched

- `wos_sim/predictor/type1_router.py` — **NEW.** Classifier
  (`_type1_classifiable`) + hero/army mapping + law call + Forecast
  construction (`_try_deterministic`). Kept out of `api.py` to keep that diff
  small.
- `wos_sim/predictor/api.py` — `predict()` gets a router preamble (7 lines +
  a comment) right after `validate.validate_matchup`, plus one `if
  abstain_note:` line before the final `summary.summarize(...)` call.
  Signature unchanged. Import line gained `type1_router`.
- `wos_sim/predictor/tests/test_type1_router.py` — **NEW**, 25 tests.
- No changes anywhere else. `server.py`, `prototype/index.html`,
  `stage6_tables.json`, the corpus, and every other `formula_research/*.py`
  file are untouched (verified via `git status`/`git diff` before finishing).

## THE HEADLINE FINDING — read this first

**Stage 6.8, as scoped by the SKILL.md item-1 checklist alone ("single-class
stacks"), would have silently served wrong "confidence=validated" answers for
ordinary-sized production matchups.** While building the router I ran the
existing `backtest.py` composition-magnitude anchors (Lv6, single-class,
hero-less, **10,000 troops per side** — a completely ordinary matchup shape
for this app) through my first draft of the classifier, which accepted them
(they satisfy every condition literally listed in the spec's item 1). The
result for the "mirror (inf v inf)" anchor:

```
before (turn engine, unrouted): "attacker" wins, 58.4% survivors (real: 24.0%)
after  (first draft router):    "defender" wins — CAPPED at turn 1500
```

A matchup the turn engine (and reality) says the attacker clearly wins came
back from the frozen law as a *capped defeat*. Root cause:
`stage5_composition.army_kill_timeline`'s sequential-tanking loop is
literally `for i in range(n_front):` where `n_front` is the deployed troop
**count** (not the number of unit-stacks) — for 10,000 troops that is a
10,000-entry death timeline built from tanking ratios (`TANK_FIRST=0.423`,
`TANK_MIDDLE=0.692`, `TANK_LAST=0.731`) that were measured on a front-count
ladder of **~1–5** troops against one specific defender
(`Meuller_Alpaca_v5_8_Battle`). At n≈10,000 the model's total front-clear
time balloons past the 1500-turn cap. I confirmed the corpus itself has no
real, validated support for this scale: every "clean" exact-turn row is
count==1 (the K/G_w/G_l calibration instruments); the only rows with
count > 300 are tagged `legacy_unverified` or are the excluded
wrong-additive-base NanoMart rows.

**Decision:** I added a domain restriction beyond the SKILL.md item-1 list —
**both sides must deploy exactly one troop** (not merely one class). This
is strictly broader than, and subsumes, the narrower "Gatot only shields a
1-troop target" scoping issue the SKILL.md text itself flags (see
`stage5_composition._dealer_rate`'s `target["count"] == 1` gate, and the
already-existing `test_multiunit_gatot_target_flagged_not_silent`). With
this restriction, re-running the exact same backtest command reproduces the
pre-router numbers **exactly** (58.4% / 49.9% / 58.3% / 72.0%, all four
composition anchors, byte-for-byte) — confirmed below.

**Practical consequence, stated plainly:** with this restriction, the router
essentially never fires for real user-submitted battles (which always field
far more than 1 troop per class). It is fully wired, tested, and correct for
the domain it *does* cover (single-troop 1v1 — exactly the corpus's own
calibration-instrument scale), and is available immediately for that domain
and for future generalization once the composition algorithm is validated at
production scale (a natural Stage 6.9+ candidate — NOT attempted here,
per the no-table/no-corpus-changes scope boundary). I judged shipping a
narrow-but-honest router far preferable to a broad one that is sometimes
silently wrong, given the whole project's no-fudge/never-guess ethos and the
concrete counter-example above. **This is the single most important thing
for the evaluator to scrutinize** — it is a real interpretive call, not a
mechanical implementation of the literal spec text.

## Router design

```
predict(own, enemy, ..., params=None):
    matchup = Matchup(own, enemy)
    validate.validate_matchup(matchup)          # unchanged

    if (params or {}).get("deterministic_router") is not False:   # opt-out
        classifiable, reason = type1_router._type1_classifiable(matchup)
        if classifiable:
            forecast, abstain_note = type1_router._try_deterministic(matchup)
            if forecast is not None:
                return forecast                  # confident OR coin_flip
            # else: abstain/exception -- abstain_note carried to the note below

    ... EXISTING turn/general engine body, byte-identical ...
    if abstain_note:
        note = f"{note} {abstain_note}".strip()
    return summary.summarize(..., engine_note=note, ...)
```

**Byte-identical guarantee:** when the router is opted out, or `classify()`
says NOT classifiable, `abstain_note` stays `""` and every line below the
preamble is the pre-6.8 code, unexecuted-differently — no new branches fire
inside it. This is how the golden backtest and predictor suite stay
unchanged for every non-Type-1 profile without a second maintained code path.

### Reusing `summary.summarize()` for the deterministic Forecast

Rather than hand-building `Distribution`/bucket objects, `_try_deterministic`
constructs ONE synthetic `kernel.RunRecord` (`winner='A'|'D'`, `turns`,
`*_start`/`*_incap` keyed on the ONE deployed `TroopType` per side, values
from `att_deaths`/`def_deaths` truncated at the battle-ending turn — computed
independently for BOTH sides, not just the winner, so it is also correct in
the `capped` shape) and feeds `[record]` through the real
`summary.summarize(..., win_prob_override=...)`. Because `_percentile` on a
length-1 list returns that element for every quantile, every
`Distribution.{median,mean,p5,p95}` collapses to the true value — a
"single-point distribution" using the EXACT existing pipeline (buckets,
army/class losses, rounds) — which is also why `serialize.forecast_to_dict`
round-trips it with zero modification: it is a real `Forecast`, produced by
the real `summarize()`. Verified directly in
`test_serialize_round_trips_without_modification`.

## Classifier truth table (`type1_router._type1_classifiable`)

Checked in this order (order matters for the golden set):

| # | Check | Reason tag | Notes |
|---|---|---|---|
| 1 | every deployed class, both sides: `tier` a whole number `<= 6` AND `fc < 3` | `tier/fc` | checked BEFORE the single-class/count checks so a T12 multi-class profile still reports `tier/fc` — verified on all 13 golden anchors |
| 2 | exactly one nonzero-count class per side | `multi_class` | via `construct.class_counts` (formation_counts else troops_total×formation — reused, not reimplemented) |
| 3 | **that one class's deployed troop count is exactly 1** | `count` | **addition beyond the SKILL.md item-1 list — see the headline finding above. Load-bearing, not cosmetic.** |
| 4 | every `lead_heroes` value (any class, not just the deployed one) normalizes to one of {none, Seo-yoon, Vulcanus, Gatot} | `hero` | case/space/hyphen-insensitive |
| 5 | `joiners` empty | `joiners` | |
| 6 | `own_buffs` and `debuffs_on_enemy` empty | `buffs` | |
| 7 | (cross-side, after both sides pass 1–6) NOT `(stats_mode=="scouted" and own.panel==enemy.panel and not own.panel_is_final and not enemy.panel_is_final)` | `relayer_ambiguous` | see Ambiguity #3 |

Any failing check short-circuits with `(False, reason)`. All pass ->
`(True, "classifiable")`.

Because check #3 (count==1) now subsumes it, there is no longer a
Gatot-specific count carve-out in the code — one uniform rule covers both the
composition-algorithm concern and the narrower Gatot-kit scoping gap the spec
text itself calls out.

## Response mapping (`type1_router._try_deterministic`)

| Law outcome | `p_win` | `stochastic` | `calibrated` | `confidence` | `near_even` | `engine_path` | `engine_model_error` |
|---|---|---|---|---|---|---|---|
| confident (clock gap > 10%) | 1.0/0.0 (se 0, from the real 1-run tally) | False | True | `"validated"` | False | `"deterministic_law"` | 0.03 |
| coin-flip (clock gap <= 10%) | 0.5 (`win_prob_override`) | False | True | `"coin_flip"` | True | `"deterministic_law"` | 0.03 |
| `winner=="uncertain"` (gatot_abstain) or an exception | `None` returned -> caller falls through to the turn/general engine unchanged, `engine_note` gets `" (deterministic law abstained: <flag>)"` appended | (whatever the turn/general path reports) | | | | | |

`clock gap := abs(t_att_dead - t_def_dead) / max(t_att_dead, t_def_dead)`,
read from `predict_battle`'s `att_deaths[-1][0]` / `def_deaths[-1][0]` (the
two sides' own would-be full-kill clocks) — the law's own internal race
margin, not the turn-engine's static-strength heuristic (`winprob.py`). No
exact formula for "clock gap" is given in the spec; this is my
interpretation of the phrase, flagged here for review. Empirically, 0 of the
87 real corpus rows I swept through the router landed in the coin-flip band
(40 confident, 47 abstain) — the coin-flip test therefore uses an
illustrative near-mirror synthetic fixture (documented in the test file), not
a corpus row.

`engine_note` always names `law_version` (from
`predict_deterministic_battle`'s `res["meta"]["law_version"]`, currently
`"stage6.7"`) and the exact clock.

## Ambiguities / deliberate additions (flagged for the evaluator)

1. **Single-troop domain, not single-class.** See the headline finding.
   Load-bearing; empirically demonstrated; this is the one I'd most want
   Martin/the evaluator to weigh in on, since it's the difference between a
   router that's honest-but-narrow and one that's broad-but-occasionally-wrong.
2. **Whole-number tier.** `stage4_common.base_stats` keys the stat table by
   `f"T{tier}"`; a half-tier (10.5/11.5 — legal in `ClassQuality`, only
   reachable above tier 6 in real UI use) would raise `KeyError` inside
   `eff_stats`. Folded into the `tier/fc` check as "whole number <= 6" rather
   than relying on the try/except abstain-fallthrough for a precondition
   cheaply checkable up front. Tested (`test_half_tier_rejects`).
3. **`panel_is_final` / relayer ambiguity.** `construct.build` relayers
   hero-generation stats out of a *shared, non-final, scouted* panel (the
   "pre-assumed symmetric" UI shortcut). The deterministic law has no
   equivalent step — it consumes the panel as already-final. Rather than
   requiring `panel_is_final` unconditionally (not in the spec's item-1
   list), I replicated `construct.build`'s own trigger predicate exactly and
   reject only that specific configuration, so it can never silently diverge
   from what the turn engine would have relayered. Tested.
4. **Seo-yoon skill level always defaults to 3.** `SideProfile` carries no
   hero-skill-level field anywhere in the schema (confirmed by grep across
   `profiles.py`/`serialize.py`/every predictor test) — "level-if-known-else
   3" therefore always resolves to 3 (max) in practice; this is a fact about
   the schema, not a policy choice.
5. **Hero-name validity is checked on every `lead_heroes` value**, not just
   the one on the deployed class (a stray disallowed name parked on a
   zero-troop class still rejects). Conservative per the spec's own "any
   doubt -> not classifiable"; the reverse (only checking the deployed
   class's hero) would also have been defensible.

## Tests (`wos_sim/predictor/tests/test_type1_router.py`, 25 tests)

Classifier truth table (spec item 4 + the two domain additions):
`test_happy_path_classifiable`, `test_tier_above_six_rejects`,
`test_half_tier_rejects`, `test_fc_at_or_above_three_rejects`,
`test_unknown_hero_gordon_rejects` (Gordon: a REAL, `validate.py`-recognized
hero, unlike a nonsense string — exactly why the spec names it),
`test_joiners_reject`, `test_own_buffs_reject`,
`test_debuffs_on_enemy_reject`, `test_multi_class_rejects`,
`test_count_above_one_rejects`,
`test_relayer_ambiguous_symmetric_nonfinal_panel_rejects`.

Hard invariant: `test_golden_backtest_profiles_all_reject_tier_fc` — all 13
`normalize_reports.golden_anchors()` profiles reject, all with `"tier/fc"` in
the reason.

Hero -> kit mapping: `test_seoyoon_maps_to_level_3_kit_case_and_hyphen_insensitive`
(4 spellings), `test_vulcanus_maps_to_flag_kit`,
`test_gatot_maps_to_flag_kit_no_copy`, `test_no_hero_maps_to_empty_kit`.

Router end-to-end (through `api.predict`, the real call path):
- `test_corpus_derived_confident_winner` —
  `FarSeer_1v1_T1InfvT1Inf_AttInfA+188.6_Gatotlvl1_NoDefenderHero_20260712_083001`
  (FarSeer Infantry T1, Gatot on its OWN side, vs a naked Lab-Rat Infantry
  T1). Asserts the full contract table (path/confidence/calibrated/
  stochastic/near_even/n/p_win/se/model_error/note), AND cross-checks the
  router's turn count against an independent direct call to
  `api.predict_deterministic_battle` with the equivalent army dicts (105 —
  1 turn off the historical 104 because that row's own capture flags
  Lethality/Health as uncaptured; this test is about wiring correctness, not
  re-validating the law's historical accuracy, which is `stage6_validate`'s
  job).
- `test_serialize_round_trips_without_modification` — JSON-serializable,
  every contract field present.
- `test_coin_flip_mapping` — synthetic near-mirror, gap ≈0.7%.
- `test_abstain_fallthrough_non_infantry_dealer` —
  `LabRat_1v1_T1LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_175807` (Lancer
  dealer, non-Infantry, into a Gatot-Infantry target of unresolvable copy —
  deterministically `gatot_gate_unmodeled`).
- `test_abstain_fallthrough_naive_infantry_dealer_monotonicity` —
  `MuellerAlpaca_1v1_T1InfvFC1T1Inf_..._20260712_150803` (an Infantry
  dealer's naive race into an actually-inert-but-unresolvable Gatot target
  trips the monotonicity check — the OTHER abstain flavor,
  `gatot_kit_unmeasured_inf_dealer`).
- `test_try_deterministic_converts_exceptions_to_abstain` — monkeypatches
  `api.predict_deterministic_battle` to raise; confirms the "OR raises"
  clause.
- `test_opt_out_param_forces_turn_path`.
- `test_not_classifiable_is_byte_identical_to_pre_router_note` — no
  abstain-clause leakage when the router never engaged.
- `test_predict_signature_unchanged`.

## Gates — before and after (all four commands, run identically both times)

| Gate | Before | After |
|---|---|---|
| `py -m pytest wos_sim/predictor/tests/ -q` | 125 passed, 8 skipped, 2 xfailed, 23 subtests | **150 passed** (125 + 25 new), 8 skipped, 2 xfailed, 23 subtests |
| `py -m wos_sim.backtest` | PASS, winners 7/13; composition 58.4/49.9/58.3/72.0% | **PASS, winners 7/13 (unchanged)**; composition **58.4/49.9/58.3/72.0% (byte-identical)** |
| `py -m wos_sim.formula_research.stage6_validate` | 11 PASS + 2 deliberate FAILs (D6 factorized-band, W6) | **11 PASS + the same 2 deliberate FAILs (unchanged)** — this script never calls `api.predict`, so it was never at risk |
| `py -m pytest wos_sim/formula_research/ -q` | 24 passed | **24 passed (unchanged)** |

No gate moved except the predictor suite's pass count growing by exactly the
25 new tests. `git status`/`git diff` confirm `server.py`,
`prototype/index.html`, `stage6_tables.json`, the corpus, and every other
`formula_research/*.py` file are untouched by this stage.

## Audit trail: existing tests checked for accidental Type-1 capture

Before finishing, I checked every existing call site of `api.predict()` for
profiles that might newly classify as Type-1 (a silent regression risk the
gates above wouldn't necessarily catch by themselves, since some assert on
`engine_path` values my router could change):
`test_api.py`, `test_server.py`, `test_winprob_joiners.py`,
`test_pvp_turn_engine.py`, `test_serialize.py`. Every one either defaults to
T12/FC10 quality, is multi-class, or carries joiners/unrecognized heroes —
none newly classifies as Type-1. `test_pvp_turn_engine.py`'s one
`ClassQuality(tier=6, fc=0, ...)` fixture calls `construct.build` directly,
never `api.predict`, so the router never sees it. The `backtest.py`
composition anchors WOULD have been newly captured (single-class, tier 6,
fc 1, hero-less, 10,000 troops) — that is exactly the headline finding above,
and is now correctly excluded by the count==1 domain restriction.

## What I did NOT touch (per the spec's OUT-OF-SCOPE list)

`server.py`, `prototype/index.html`, the corpus, `stage6_tables.json`/other
frozen tables, the composition multi-class generalization, anything in
Stage 7's scope. `stage5_composition.py`/`stage5_law.py`/`stage6_tables.py`
were read but not edited — the single-troop-domain restriction lives entirely
in the NEW `type1_router.py`, not in the frozen law files.

## Eval-6.8 (evaluator window, 2026-07-21): ACCEPT — with one spec-bug correction

1. **The builder's Ambiguity #1 (single-TROOP domain) is ENDORSED.** The
   evaluator independently reproduced the load-bearing claim: a 10,000-troop
   T6 Infantry mirror through the raw law returns capped/defender —
   `army_kill_timeline`'s sequential-tanking cascade is measured at the 1–5
   front-unit instrument scale only. Honest-but-narrow beats broad-but-wrong;
   the widening path (W6's winner-only multicount evidence) is Stage-7C
   material.
2. **One correction, attributed to the SPEC (the evaluator's own), not the
   builder:** the flat "tier ≤ 6" ceiling wrongly excluded T7 INFANTRY —
   proc-free (Bands of Steel is always-on; Ambusher/Volley are Lancer/MM
   unlocks) with a MEASURED G_w(Inf,7)=14.285. Corrected to a per-class cap
   (Infantry ≤ 7; Lancer/Marksman ≤ 6; T8+ Infantry extrapolated → reject);
   the builder's stale `test_tier_above_six_rejects` updated; 3 tests added
   (T7-Inf classifies + routes end-to-end with the exact clock; T7 Lan/MM
   reject; T8 Inf rejects). Router tests 25 → 27; suite 150 → 152.
3. **Gates re-run post-correction:** predictor suite 152 passed / 8 skipped /
   2 xfailed; backtest PASS 7/13 byte-identical; stage6_validate 11 PASS + 2
   deliberate FAILs unchanged; formula_research 24 passed.
4. **LIVE LOCALHOST VERIFICATION** (the definitive adoption proof): dev
   server on :8137, real HTTP POSTs to `/api/predict`:
   - the T7-discriminator matchup → `engine.path="deterministic_law"`,
     `stochastic=false`, `calibrated=true`, `confidence="validated"`,
     win 1.0 ± 0.0, note "Deterministic Type-1 law (stage6.7): exact result
     — attacker wins at turn 76" (observed battle: [75,77]);
   - a default T12/FC10 request → `engine.path="pvp_turn_engine"`,
     stochastic, n=200 — the production path untouched, live.
5. Verdict: **ACCEPT.** The deterministic law is adopted in the app's
   localhost path for its validated domain; everything else is provably
   unchanged.
