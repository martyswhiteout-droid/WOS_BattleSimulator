"""Hero GENERATION -> stat contribution (E-12).

Source of truth: the workbook 'Hero Stats' x 'Hero Profile' tabs + the
'Current Stats - Self' aggregation formula (read 2026-07-05). CONFIRMED facts:

  * A lead hero's four stat values depend ONLY on its GENERATION - not on the
    hero or the class. Gen 14 -> (Atk=Def 17.9143, Leth=HP 4.475), ... down to
    Gen 1. (Attack==Defense and Lethality==Health within every generation.)
  * The hero contributes its generation value ADDITIVELY into the stat panel, in
    the same units as the panel (x100 = percent), INSIDE the buff multiplier:
        Scouted = (Base + HeroesEffect + Gear*Fudge) * (1 + Buff) + Buff
    so a hero's NET panel contribution for a stat with buff b is value*(1+b).
    (Cross-checked against a controlled report: swapping Mia gen3 -> Fred gen9 as
    lancer lead moved lancer Attack by 6.5052*1.15=+748% [attack buff 0.15] and
    lancer Defense by 6.5052*1.0=+650% [defense buff 0] - the attack/defense gap
    IS the per-stat buff factor.)
  * GENERATION AFFECTS STATS ONLY, NEVER SKILLS. Skill effect amounts come from
    the skill book verbatim (assemble.py), with no generation multiplier - a
    gen-15 hero's skill is identical to a gen-1 hero's. Do not add gen scaling to
    skills.

This module exposes the generation table + the relayer that swaps which hero
leads each class (Martin's 'pre-assumed symmetric' method). It does NOT touch
skills.
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import StatType

# name -> generation, extracted from the workbook 'Hero Profile' tab (static so
# the deployed app needs no workbook). Regenerate from the workbook if heroes are
# added. SR/legacy heroes have generation "SR" (joiner-flags only, never leads).
_GEN_BY_NAME: dict | None = None


def _generations() -> dict:
    global _GEN_BY_NAME
    if _GEN_BY_NAME is None:
        p = Path(__file__).parent / "data" / "hero_generations.json"
        _GEN_BY_NAME = json.loads(p.read_text(encoding="utf-8"))
    return _GEN_BY_NAME


def hero_generation(name: str):
    """Lead-hero generation (int 1-15) for a hero NAME, or None if the hero is
    SR/legacy (joiner-only, no lead-stat contribution) or unknown."""
    entry = _generations().get(name)
    gen = entry.get("generation") if entry else None
    return gen if isinstance(gen, int) else None


def class_gens_from_names(lead_heroes: dict) -> dict:
    """{class: hero_name} (the front-end's `lead_heroes`) -> {class: generation}.
    Classes whose lead hero is SR/legacy/unknown are DROPPED (no lead-stat
    contribution -> that class's panel is left unchanged by the relayer)."""
    out = {}
    for cls, name in lead_heroes.items():
        gen = hero_generation(name)
        if gen is not None:
            out[cls] = gen
    return out

# generation -> (Attack==Defense value, Lethality==Health value); x100 = percent.
# Verified EXACT against every workbook hero for gen 2-14. Gen 1 is a mixed bucket
# of SR/legacy heroes with INDIVIDUAL values (e.g. Natalia leth 0.555, Jeronimo
# atk 2.602); those are joiner-flags only, never LEAD heroes, so they never
# contribute a lead-hero stat and the standard value below suffices. If a gen-1
# lead is ever needed, look the specific hero up in the HeroRoster instead.
GEN_STAT: dict[int, tuple[float, float]] = {
    15: (19.6156, 4.9),
    14: (17.9143, 4.475), 13: (16.2129, 4.05), 12: (14.5116, 3.625),
    11: (12.8102, 3.23),  10: (11.1088, 2.775), 9: (9.4075, 2.32),
    8:  (7.8062, 1.93),   7:  (6.5052, 1.605),  6: (5.4043, 1.335),
    5:  (4.4435, 1.11),   4:  (3.7029, 0.925),  3: (2.9023, 0.7),
    2:  (2.4019, 0.6),    1:  (2.0016, 0.5),
}
_AD = (StatType.ATTACK, StatType.DEFENSE)


def hero_stat(generation, stat) -> float:
    """Panel contribution (fraction, x100=%) of a lead hero of `generation` for
    one `stat` (StatType or its string). Attack==Defense, Lethality==Health."""
    ad, lh = GEN_STAT[int(generation)]
    return ad if StatType(stat) in _AD else lh


def _buff_for(buffs, cls, stat) -> float:
    if not buffs:
        return 0.0
    return buffs.get((cls, stat), buffs.get(stat, buffs.get(StatType(stat), 0.0)))


def relayer_panel(panel: dict, class_gens: dict, *, buffs: dict | None = None,
                  assumed_gen: int | None = None) -> dict:
    """Re-layer per-class lead-hero generations onto a PRE-ASSUMED symmetric
    panel (Martin's method, E-12). The supplied panel baked in the HIGHEST-gen
    hero across all classes uniformly; strip that and re-apply each class's ACTUAL
    lead-hero generation:

        new = panel + (hero_stat(class_gen) - hero_stat(assumed_gen)) * (1+buff)

    ONLY use this in the pre-assumed symmetric case (front-end supplied identical
    stats on both sides). When the two sides have DIFFERENT real scouted stats,
    the user gave actual stats - pass them through UNCHANGED (do not relayer).

    Args:
      panel:      {(class, stat): fraction}  (as construct.py uses; x100 = %).
      class_gens: {class: generation}  ACTUAL lead-hero generation per class.
      buffs:      optional {(class,stat) | stat: fraction}; the hero enters
                  scaled by (1+buff) per stat (workbook aggregation). Omit/None
                  => 0 (Martin's literal additive method).
      assumed_gen:override the baked-in generation; default = max(class_gens).
    Returns a NEW panel dict (input unchanged)."""
    if assumed_gen is None:
        assumed_gen = max(int(g) for g in class_gens.values())
    out = dict(panel)
    for (cls, stat), val in panel.items():
        g = class_gens.get(cls)
        if g is None:
            continue
        delta = ((hero_stat(g, stat) - hero_stat(assumed_gen, stat))
                 * (1.0 + _buff_for(buffs, cls, stat)))
        out[(cls, stat)] = val + delta
    return out


def relayer_by_names(panel: dict, lead_heroes: dict, *, buffs: dict | None = None,
                     assumed_gen: int | None = None) -> dict:
    """Convenience: relayer_panel driven by the front-end's `lead_heroes`
    {class: hero_name} (e.g. {"Infantry": "Gregory", "Lancer": "Renee",
    "Marksman": "Blanchette"}). Resolves names -> generations, then re-layers.
    Only LEAD heroes contribute stats; joiners are skills-only, so pass just
    lead_heroes here."""
    return relayer_panel(panel, class_gens_from_names(lead_heroes),
                         buffs=buffs, assumed_gen=assumed_gen)


def _self_test():
    from .models import StatType as S
    # generation table structure
    assert hero_stat(9, S.ATTACK) == hero_stat(9, S.DEFENSE) == 9.4075
    assert hero_stat(3, S.LETHALITY) == hero_stat(3, S.HEALTH) == 0.7
    # controlled report: Mia gen3 -> Fred gen9 lancer swap
    d_atk = (hero_stat(9, S.ATTACK) - hero_stat(3, S.ATTACK)) * (1 + 0.15)
    d_def = (hero_stat(9, S.DEFENSE) - hero_stat(3, S.DEFENSE)) * (1 + 0.0)
    assert abs(d_atk - 7.4810) < 1e-3, d_atk        # +748% (attack buff 0.15)
    assert abs(d_def - 6.5052) < 1e-3, d_def        # +650% (defense buff 0)
    # relayer: pre-assumed panel with gen11 baked in; re-layer inf14/lan3/mar8
    panel = {("Infantry", "Attack"): 12.8102, ("Lancer", "Attack"): 12.8102,
             ("Marksman", "Attack"): 12.8102}
    gens = {"Infantry": 14, "Lancer": 3, "Marksman": 8}   # assumed_gen -> 14
    out = relayer_panel(panel, gens)
    assert abs(out[("Infantry", "Attack")] - (12.8102 + (17.9143 - 17.9143))) < 1e-9
    assert abs(out[("Lancer", "Attack")] - (12.8102 + (2.9023 - 17.9143))) < 1e-9
    assert abs(out[("Marksman", "Attack")] - (12.8102 + (7.8062 - 17.9143))) < 1e-9
    # name resolver (front-end passes NAMES): Greg(g3 marks) != Gregory(g10 inf)
    assert hero_generation("Gregory") == 10 and hero_generation("Greg") == 3
    assert hero_generation("Renee") == 6 and hero_generation("Mia") == 3
    assert hero_generation("Jessie") is None            # SR -> not a lead
    leads = {"Infantry": "Gregory", "Lancer": "Renee", "Marksman": "Blanchette"}
    assert class_gens_from_names(leads) == {"Infantry": 10, "Lancer": 6, "Marksman": 10}
    by_names = relayer_by_names(panel, {"Infantry": "Elif", "Lancer": "Mia",
                                        "Marksman": "Hendrik"})   # g14/g3/g8
    assert by_names == out                               # same as gen-based relayer
    print("hero_stats self-test OK  (gen table + buff deltas + relayer + name resolver)")


if __name__ == "__main__":
    _self_test()
