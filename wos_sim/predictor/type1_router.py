"""Stage 6.8 — the Type-1 router: classifies a Matchup as sitting inside the
frozen deterministic law's validated domain and, when so, builds the law's
call, maps its result onto the EXISTING Forecast/serialize/UI contract, and
hands it back to `api.predict()`. Conservative by construction: any
classification doubt returns `(False, reason)` and `api.predict()`'s
pre-6.8 body runs completely unchanged for that matchup.

See `.claude/skills/run-stage/SKILL.md` ("/run-stage 6.8") for the spec and
`wos_sim/formula_research/STAGE6_8_REPORT.md` for the design writeup,
classifier truth table, response-mapping table, and — importantly —
Ambiguity #1 there: both sides must deploy EXACTLY ONE troop (not merely one
CLASS). `stage5_composition.army_kill_timeline`'s sequential-tanking loop
(`range(n_front)`, n_front = the deployed troop COUNT) is only validated at
the single-troop instrument scale the frozen K/G_w/G_l tables were measured
on; feeding it a realistic army-sized single-class stack was empirically
shown, while building this router, to drive some battles past the 1500-turn
cap that obviously resolve in reality (a same-tier mirror). This also
subsumes the narrower "Gatot only shields a 1-troop target" gap called out
in the SKILL.md spec text.
"""
from __future__ import annotations

from wos_sim.models import TroopType

from . import construct
from .kernel import RunRecord
from .profiles import CLASSES, STATS, ClassQuality, Matchup, SideProfile
from .summary import summarize

_TROOP_ENUM = {"Infantry": TroopType.INFANTRY, "Lancer": TroopType.LANCER,
               "Marksman": TroopType.MARKSMAN}

#: hero names the law's kit machinery understands, keyed by a normalized form
#: (case/space/hyphen-insensitive). "gatot"/"vulcanus" are flags; "seoyoon"
#: carries a level, but SideProfile carries no skill-level field anywhere in
#: its schema, so it always defaults to 3 (max) -- see STAGE6_8_REPORT.md
#: Ambiguity #4.
_KNOWN_HEROES = {"seoyoon", "vulcanus", "gatot"}

#: clock-gap threshold below which a confident law winner is relabeled a
#: coin flip (spec: "clock gap <= 10%"). See STAGE6_8_REPORT.md for the exact
#: definition (the law's own two race clocks, not the turn-engine heuristic).
COIN_FLIP_GAP = 0.10

#: A9 exact-gate band (per the spec: "engine_model_error 0.03").
LAW_MODEL_ERROR = 0.03


def _norm_hero(name) -> str | None:
    """Case/space/hyphen-insensitive hero key, "" for no-hero, or None if the
    name is present but not one of {Seo-yoon, Vulcanus, Gatot}."""
    if not name:
        return ""
    key = "".join(ch for ch in str(name).lower() if ch.isalnum())
    return key if key in _KNOWN_HEROES else None


def _deployed_classes(side: SideProfile) -> list:
    counts = construct.class_counts(side)
    return [c for c in CLASSES if counts.get(c, 0) > 0]


def _type1_classifiable(matchup: Matchup):
    """(bool, reason). CLASSIFIABLE iff both sides deploy EXACTLY ONE troop
    of EXACTLY ONE class, that troop's tier/fc sits inside the law's domain,
    its lead hero (if any) is one of {Seo-yoon, Vulcanus, Gatot}, and there
    are no joiners/buffs on either side, and the panels don't trigger
    construct.py's symmetric-panel hero-generation relayering (which this
    router does not replicate). See STAGE6_8_REPORT.md for the full truth
    table, why tier/fc is checked before multi_class (so a T12 multi-class
    golden-backtest profile still reports "tier/fc"), and why the domain is
    single-TROOP, not merely single-CLASS (Ambiguity #1)."""
    for who, side in (("own", matchup.own), ("enemy", matchup.enemy)):
        counts = construct.class_counts(side)
        deployed = _deployed_classes(side)
        for cls in deployed:
            q = side.quality.get(cls) or ClassQuality()
            # Per-class tier ceiling (eval-6.8 correction of the spec's flat
            # "<= 6"): T7 INFANTRY is proc-free (Bands of Steel is always-on;
            # the T7 procs Ambusher/Volley are Lancer/Marksman unlocks) and
            # G_w(Inf,7) is a MEASURED cell (14.285, the 2026-07-18 T7
            # discriminator). Lancer/Marksman stay capped at T6; T8+ Infantry
            # is extrapolated-only -> rejected.
            tier_cap = 7 if cls == "Infantry" else 6
            if not float(q.tier).is_integer() or q.tier > tier_cap or q.fc >= 3:
                return False, (f"tier/fc: {who} {cls} tier={q.tier} fc={q.fc} "
                               f"outside the deterministic law's domain "
                               f"(whole-number tier <= {tier_cap} for {cls}, "
                               f"fc < 3)")
        if len(deployed) != 1:
            return False, (f"multi_class: {who} has {len(deployed)} deployed "
                           f"class(es) (need exactly 1)")
        cls = deployed[0]

        # Single-TROOP domain (not just single-CLASS) -- see
        # STAGE6_8_REPORT.md Ambiguity #1. Empirically confirmed: feeding
        # stage5_composition.predict_battle a realistic large single-class
        # stack (e.g. 10,000 T6 Infantry mirrors, the backtest.py composition
        # anchors) drives army_kill_timeline's sequential-tanking loop
        # (range(n_front) with n_front in the thousands) far past the 1500-
        # turn cap, turning an obviously-winnable mirror into a fabricated
        # "capped defeat". That algorithm's tanking ratios were measured on a
        # front-count ladder of ~1-5 vs ONE specific defender; the corpus's
        # own clean/exact-turn rows are themselves overwhelmingly count==1
        # (the K/G_w/G_l calibration instruments) -- the only count>300 rows
        # are either NanoMart (excluded, wrong additive base) or explicitly
        # "legacy_unverified". So: count must be exactly 1 for BOTH sides,
        # not just Gatot-led ones -- this also subsumes (and is strictly
        # broader than) the multi-unit Gatot-kit gap noted in the SKILL.md
        # spec text itself.
        if counts[cls] != 1:
            return False, (f"count: {who} {cls} deployed count={counts[cls]} "
                           f"!= 1 -- the composition/sequential-tanking "
                           f"algorithm is validated only at the single-troop "
                           f"instrument scale (see STAGE6_8_REPORT.md)")

        for hero_name in (side.lead_heroes or {}).values():
            if _norm_hero(hero_name) is None:
                return False, (f"hero: {who} lead hero {hero_name!r} not in "
                               f"{{Seo-yoon, Vulcanus, Gatot, none}}")

        if side.joiners:
            return False, (f"joiners: {who} has {len(side.joiners)} joiner(s) "
                           f"(must be empty)")
        if side.own_buffs:
            return False, f"buffs: {who} own_buffs non-empty"
        if side.debuffs_on_enemy:
            return False, f"buffs: {who} debuffs_on_enemy non-empty"

    own, enemy = matchup.own, matchup.enemy
    if (own.stats_mode == "scouted" and own.panel == enemy.panel
            and not own.panel_is_final and not enemy.panel_is_final):
        return False, ("relayer_ambiguous: symmetric non-final scouted panels "
                       "trigger construct.build's hero-generation relayering, "
                       "which this router does not replicate")
    return True, "classifiable"


def _kit_for_side(side: SideProfile, cls: str) -> dict:
    """Hero kit dict for `stage5_composition.predict_battle`'s att_kit/def_kit,
    from the deployed class's lead hero. Only reachable after
    `_type1_classifiable` accepted the matchup, so the hero name is always
    recognized here."""
    key = _norm_hero((side.lead_heroes or {}).get(cls))
    if key == "seoyoon":
        return {"seoyoon": 3}     # schema carries no level -- default max, L3
    if key == "vulcanus":
        return {"vulcanus": True}
    if key == "gatot":
        # Copy is unknown from a live profile (the schema has no such field);
        # stage5_composition's abstention machinery (_gatot_resolve) treats an
        # unresolved copy conservatively -- non-Infantry dealers into it
        # always abstain, Infantry dealers race naively under a monotonicity
        # check. That IS the intended abstain-fallthrough path (see
        # STAGE6_8_REPORT.md Ambiguity #1); it is never silently promoted to
        # "aurad" or "inert" without a copy to look up.
        return {"gatot": True}
    return {}


def _army_for_side(side: SideProfile):
    """(unit_dict, cls, count, kit) for a side already accepted by
    `_type1_classifiable` (so: exactly one deployed troop of one class,
    whole tier <= 6, fc < 3 -- `count` below is always 1 in practice, but is
    still read from the profile rather than hardcoded)."""
    counts = construct.class_counts(side)
    cls = _deployed_classes(side)[0]
    count = counts[cls]
    q = side.quality.get(cls) or ClassQuality()
    # panel fractions x100 -> displayed-percent (profiles.py: "1096% -> 10.96");
    # the law's eff_stats/_norm_army both read percent units under "panel".
    panel_pct = {stat: side.panel.get((cls, stat), 0.0) * 100.0 for stat in STATS}
    unit = {"cls": cls, "tier": int(q.tier), "fc": q.fc, "count": count,
            "panel": panel_pct}
    return unit, cls, count, _kit_for_side(side, cls)


def _note(law_version: str, winner_word: str, turns: int, *, coin_flip: bool,
          gap: float) -> str:
    if coin_flip:
        return (f"Deterministic Type-1 law ({law_version}): a near-even race "
                f"(clock gap {gap:.1%}) -- {winner_word} projected to win at "
                f"turn {turns}, but this is a coin flip either side can take.")
    return (f"Deterministic Type-1 law ({law_version}): exact result -- "
            f"{winner_word} wins at turn {turns}.")


def _try_deterministic(matchup: Matchup):
    """(Forecast|None, note_suffix). Assumes `_type1_classifiable(matchup)`
    already returned True. None -> the law abstained (gatot_abstain) or
    raised; `note_suffix` is a short "(deterministic law abstained: ...)"
    clause the caller appends to whatever engine_note the turn/general path
    produces. Never raises -- every failure mode is converted to the abstain
    return so a bug here can only ever fall back to the pre-6.8 behavior,
    never break `predict()`."""
    try:
        own_unit, own_cls, own_n, own_kit = _army_for_side(matchup.own)
        enemy_unit, enemy_cls, enemy_n, enemy_kit = _army_for_side(matchup.enemy)
        own_is_attacker = matchup.own_is_attacker
        if own_is_attacker:
            att_unit, att_cls, att_n, att_kit = own_unit, own_cls, own_n, own_kit
            def_unit, def_cls, def_n, def_kit = enemy_unit, enemy_cls, enemy_n, enemy_kit
        else:
            att_unit, att_cls, att_n, att_kit = enemy_unit, enemy_cls, enemy_n, enemy_kit
            def_unit, def_cls, def_n, def_kit = own_unit, own_cls, own_n, own_kit

        from . import api          # deferred: api imports this module at load time
        res = api.predict_deterministic_battle(
            [att_unit], [def_unit], att_kit=att_kit or None, def_kit=def_kit or None)

        if res["winner"] == "uncertain":
            abstain = (res.get("meta") or {}).get("gatot_abstain") or {}
            flag = abstain.get("flag", "unmodeled")
            return None, f"(deterministic law abstained: {flag})"

        turns = res["turns"]
        t_att = res["att_deaths"][-1][0]
        t_def = res["def_deaths"][-1][0]
        denom = max(t_att, t_def)
        gap = abs(t_att - t_def) / denom if denom > 0 else 0.0
        coin_flip = gap <= COIN_FLIP_GAP

        att_lost = sum(1 for t, _cls in res["att_deaths"] if t <= turns)
        def_lost = sum(1 for t, _cls in res["def_deaths"] if t <= turns)
        winner_tag = "A" if res["winner"] == "attacker" else "D"
        record = RunRecord(
            winner=winner_tag, turns=turns,
            attacker_start={_TROOP_ENUM[att_cls]: att_n},
            defender_start={_TROOP_ENUM[def_cls]: def_n},
            attacker_incap={_TROOP_ENUM[att_cls]: att_lost},
            defender_incap={_TROOP_ENUM[def_cls]: def_lost})

        law_version = (res.get("meta") or {}).get("law_version", "stage6.7")
        winner_word = res["winner"]     # "attacker" | "defender"
        note = _note(law_version, winner_word, turns, coin_flip=coin_flip, gap=gap)

        if coin_flip:
            fc = summarize(
                [record], own_is_attacker=own_is_attacker,
                engine_model_error=LAW_MODEL_ERROR, engine_path="deterministic_law",
                engine_note=note, stochastic=False, calibrated=True,
                near_even=True, confidence="coin_flip", win_prob_override=0.5)
        else:
            fc = summarize(
                [record], own_is_attacker=own_is_attacker,
                engine_model_error=LAW_MODEL_ERROR, engine_path="deterministic_law",
                engine_note=note, stochastic=False, calibrated=True,
                near_even=False, confidence="validated")
        return fc, ""
    except Exception as e:                                   # noqa: BLE001
        return None, f"(deterministic law abstained: exception:{type(e).__name__})"
