# Engine handoff — duplicate joiners STACK (remove the dedup)

> **STATUS: DONE 2026-07-09.** Dedup removed in BOTH paths + guardrail comments:
> `pvp_turn_engine.py` (`seen_joiners`, turn/production path) AND
> `predictor/skills.py` (`seen`, general/legacy path — **this handoff said skills.py
> had none; it did**, so both were fixed). Verified: 4x a joiner -> 4 skill-defs,
> 4 telemetry rows (UI shows all 4), and the effect STACKS in the sim (own
> survivors 62%->74% for 0->4 Gatot) and the strength fold (ratio 0.973->1.115).
> `test_duplicate_joiners_apply_once` replaced by `test_duplicate_joiners_stack`.
> Back-test PASS (7/13 locked winners held, no new silent). The 4x-Nora
> pvp_t12_report_005 did NOT blow up to a confident win - it stays a labelled
> coin-flip miss because the near-even tempering (winprob.py) absorbs it, which
> is exactly the "fix it via the coin-flip path" the note below asks for.

**Requested by:** Martin (domain-authoritative), via front-end agent — 2026-07-09
**Owner to implement:** engine agent (`wos_sim/pvp_turn_engine.py`)
**Correction:** The earlier **duplicate-joiner dedup is WRONG.** In WoS, four copies of the
same joiner hero fire **four** skills and they **stack** — the game does not collapse them
to one. All copies must apply their effect, and all must be reported so the UI shows all four.

This reverses the "DUPLICATE-JOINER DEDUP" that was added from a single-battle analysis
(4×Nora, `pvp_t12_report_005`) and was already flagged in code as "one-battle evidence …
an assumption." Martin confirms the mechanic: **joiners stack per copy.**

---

## The change — remove the `seen_joiners` skip

`wos_sim/pvp_turn_engine.py` ~line 726, in the joiner loop of the skill-def builder:

```python
seen_joiners: set[str] = set()
for hero in (profile.joiners or [])[:4]:
    if not hero:
        continue
    if hero in seen_joiners:          # <-- DELETE these two lines
        continue                      # <--
    seen_joiners.add(hero)            # <-- DELETE
    rows = _hero_rows(book, hero, SkillSource.SKILL_1, battle)
    if rows:
        defs.append(_make_hero_skill(hero, SkillSource.SKILL_1, rows, side,
                                     "joiner", None, ordinal, False))
    ordinal += 1
```

After removal the loop should process **every** slot in `profile.joiners[:4]`, so N copies of a
hero append N joiner skill-defs (each with its own `ordinal`), and each applies + is reported.
Keep the `[:4]` cap and the `if not hero: continue` (empty slots). Keep the JOINER
no-panel-suppression behavior (that fix is correct — joiners are never panel-suppressed).

- The `enemy Jessie×2` symmetric case falls out the same way (both copies apply).
- `wos_sim/assemble.py::_dedupe_damage_category_splits` is a **different** dedup (it merges
  DD/DT category splits *within one activation*) and its own comment says it must run
  per-activation so *duplicate joiner stacks* are preserved — **leave it alone.**
- CORRECTION (2026-07-09): `skills.py` **did** have a second joiner dedup (a `seen`
  set in `_side_effects`, ~line 56, general/legacy path) — this handoff's original
  "skills.py has none" was wrong. BOTH were removed.

## Tests

- The guard `test_duplicate_joiners_apply_once` now asserts the wrong thing. Replace with
  `test_duplicate_joiners_stack`: 4× the same joiner ⇒ ~4× that joiner's SK1 contribution
  (vs 1×), not equal to 1×. `_side` test helper caveat still applies: pass `[""]` for
  genuinely-no-joiners (its `joiners or [...]` default silently injects 4).

## Anchors / calibration note (important)

Removing the dedup will make the 4×Nora near-mirror (`report_005`) predict a **strong win**,
even though Martin's real battle there was a **LOSS**. That defeat is NOT evidence against
stacking — per [[near-even-two-structural-gaps]] the base near-mirror is a coin-flip the engine
ranks the wrong way, and anchor-5 is already labeled a `coin_flip` miss (±20% band), not a
locked winner. So:
- Stacking is the correct mechanic; keep it.
- Do **not** re-add the dedup to "fix" report_005 — address that via the near-even/coin-flip
  path, not by suppressing real stacking.
- Re-run the golden anchors: the 7/13 **locked winners** (golden_baseline.json / G12 / test_golden_anchors)
  must not regress. If a locked winner flips, that's a real calibration signal to chase
  separately — not a reason to restore the dedup.

## Front-end status (no change needed)

The app already sends every selected joiner (`readHeroes('#joinMe')` — no dedup) and
`joinerPack` renders every joiner in `skill_telemetry`. Once the engine reports all four,
the Skills tab shows all four automatically. The "N active flags" count will read the true
number of applied joiners.
