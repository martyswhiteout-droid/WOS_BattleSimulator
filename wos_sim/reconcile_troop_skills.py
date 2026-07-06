"""Reconcile the workbook's troop-skill capture against the wostools catalog.

Run:  py -m wos_sim.reconcile_troop_skills
For each FC level, computes each catalog skill's expected value (gated
effects scaled by the gating skill's uptime) and matches it against the
"Troop Stats" tab rows by skill family + attribute.
"""

import re

from .loader import load_troop_skill_table
from .models import TroopType
from .troop_catalog import active_troop_skills, gate_chance_for


def family(name: str) -> str:
    """'Crystal Shield II' / 'Body of Light II (reduction)' -> canonical key."""
    name = re.sub(r"\s*\(.*\)$", "", name)
    name = re.sub(r"\s+(I|II)$", "", name)
    return name.replace(" ", "").lower()


def norm_attr(text: str | None) -> str | None:
    return None if text is None else text.replace(" ", "").lower()


def against_matches(tab_against: str | None, catalog_against: str) -> bool:
    if tab_against is None:
        return catalog_against == "All"
    return tab_against.rstrip("s").lower() == catalog_against.rstrip("s").lower()


tab = load_troop_skill_table()
print(f"workbook skills table: {len(tab)} rows")

for fc in (10, 9):
    print(f"\n=== Catalog at FC{fc} (T11) vs workbook table ===")
    for troop in TroopType:
        active = active_troop_skills(troop, fc)
        for skill in sorted(active, key=lambda s: (s.unlock, s.name)):
            rows = [e for e in tab if e.troop_type == troop
                    and family(e.skill_name) == family(skill.name)]
            if skill.special == "bypass_to_marksman":
                hit = [e for e in rows if e.attribute is None]
                ok = hit and abs(hit[0].value - skill.proc_chance) < 1e-9
                print(f"  {troop:<9} {skill.name:<28} chance {skill.proc_chance:.0%}"
                      f" -> {'OK (targeting rule)' if ok else f'CHECK: {rows}'}")
                continue
            if skill.special == "extra_attack":
                shorthand = skill.proc_chance * skill.proc_amount
                hit = [e for e in rows if abs(e.value - shorthand) < 1e-9]
                verdict = ("OK (tab keeps EV shorthand; engine models literal "
                           "second attack)" if hit else f"CHECK: {rows}")
                print(f"  {troop:<9} {skill.name:<28} chance {skill.proc_chance:.0%}"
                      f" x2 -> {verdict}")
                continue
            ev = skill.expected_value(gate_chance_for(skill, active))
            if skill.flat_offset is not None:
                ev = -ev  # workbook records damage offset as negative
            hit = [e for e in rows if norm_attr(e.attribute) == norm_attr(skill.attribute)]
            if not hit:
                others = ", ".join(f"{e.attribute}={e.value}" for e in rows) or "no row"
                print(f"  {troop:<9} {skill.name:<28} EV={ev:+.6g} -> NO TAB ROW"
                      f" for attribute {skill.attribute} (tab has: {others})")
                continue
            e = hit[0]
            issues = []
            if abs(e.value - ev) > 1e-6:
                issues.append(f"VALUE tab={e.value} vs catalog EV={ev:+.6g}")
            if not against_matches(e.against, skill.against):
                issues.append(f"AGAINST tab={e.against!r} vs catalog={skill.against!r}")
            print(f"  {troop:<9} {skill.name:<28} EV={ev:+.6g}"
                  f" -> {'OK' if not issues else '; '.join(issues)}")
