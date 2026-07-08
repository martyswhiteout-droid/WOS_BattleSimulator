"""Normalize every real battle report into ONE front-end scenario JSON format,
then expose them as a golden anchor set (real inputs + real outcomes).

Two source schemas are folded into the identical UI/scenario shape (the format
the front-end POSTs to /api/predict):
  * wos_sim/data/pvp_t12_report_00N.json  (rich T12 schema: attacker/defender,
    composition{count,tier,fc}, panel_pct, lead_heroes{class:name}, joiner_flags)
  * wos_sim/data/reports/report_00N.json   (raw schema: friendly/enemy,
    composition{share,tier_level,fc_badge}, scouted{Class|Stat}, lead_heroes[list])

Output: Scenarios/normalized/<id>.json (scenario format) + a golden manifest
returned by ``golden_anchors()`` = [(id, scenario_dict, expected_outcome)].

    py -m wos_sim.normalize_reports          # write normalized scenarios + print manifest

Expected outcome per battle = what REALLY happened (winner + own-survivor frac),
from the report's own recorded survivors. This is the anti-overfit ground truth.
"""
from __future__ import annotations

import json
from pathlib import Path

from wos_sim.hero_stats import hero_generation  # noqa: F401 (kept for parity)

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "data"
OUT = ROOT / "Scenarios" / "normalized"
CLASSES = ("Infantry", "Lancer", "Marksman")
STATS = ("Attack", "Defense", "Lethality", "Health")

# Joiner flags Martin confirmed in each raw report's notes (not in structured
# fields). friendly/enemy keyed. r001 joiners were never identified -> omitted.
RAW_JOINERS = {
    ("report_002", "friendly"): ["Gatot", "Jessie", "Blanchette", "Blanchette"],
    ("report_002", "enemy"):    ["Blanchette", "Blanchette", "Blanchette", "Blanchette"],
    ("report_003", "friendly"): ["Gatot", "Gatot", "Ling Xue", "Magnus"],
    ("report_003", "enemy"):    ["Jessie", "Seo-yoon", "Jessie", "Jessie"],
    ("report_004", "friendly"): ["Wu Ming", "Gatot", "Ahmose", "Wu Ming"],
    ("report_004", "enemy"):    ["Renee", "Renee", "Jessie", "Jessie"],
    ("report_005", "friendly"): ["Gatot", "Ahmose", "Nora", "Vulcanus"],
    ("report_005", "enemy"):    ["Jessie", "Jessie", "Renee", "Jessie"],
    ("report_006", "friendly"): ["Nora", "Nora", "Nora", "Nora"],
    ("report_006", "enemy"):    ["Gatot", "Hendrik", "Renee", "Blanchette"],
    ("report_007", "friendly"): ["Gatot", "Patrick", "Ling Xue", "Renee"],
    ("report_007", "enemy"):    ["Jessie", "Jessie", "Jessie", "Jessie"],
    ("report_008", "friendly"): ["Nora", "Nora", "Nora", "Nora"],
    ("report_008", "enemy"):    ["Gatot", "Hendrik", "Jessie", "Eleonora"],
}
_T12_KEY = {"Infantry": "indomitable_wall", "Lancer": "meridian_phalanx",
            "Marksman": "starfire"}


def _hero_troop_map():
    gen = json.loads((DATA / "hero_generations.json").read_text())
    return {name: info.get("troop") for name, info in gen.items()}


def _leads_by_class(lead_list, comp_classes) -> dict:
    """Map a raw [hero,hero,hero] captain list to {class: hero} by each hero's
    troop type. Falls back to positional Inf/Lancer/Marks if a lookup is
    missing, so the captain trio always resolves."""
    troop_of = _hero_troop_map()
    out = {}
    leftovers = []
    for name in lead_list:
        troop = troop_of.get(name)
        if troop in CLASSES and troop not in out:
            out[troop] = name
        else:
            leftovers.append(name)
    for cls in CLASSES:                       # fill gaps positionally
        if cls not in out and leftovers:
            out[cls] = leftovers.pop(0)
    return out


def _scaled_panel(panel_like: dict, is_pct: bool) -> dict:
    """Both schemas -> scenario panel {"Class|Stat": fraction}. pvp_t12 panel_pct
    is a percent (2647.1); raw `scouted` is already a fraction (26.471)."""
    out = {}
    div = 100.0 if is_pct else 1.0
    if is_pct:                                # nested {class:{stat:pct}}
        for c in CLASSES:
            for s in STATS:
                out[f"{c}|{s}"] = panel_like.get(c, {}).get(s, 0.0) / div
    else:                                     # flat {"Class|Stat":frac}
        for c in CLASSES:
            for s in STATS:
                out[f"{c}|{s}"] = float(panel_like.get(f"{c}|{s}", 0.0))
    return out


def _side_scenario(role, total, counts, tiers, fcs, panel, leads, joiners,
                   t12_stacks) -> dict:
    total = int(total)
    return {
        "role": role, "troops_total": total, "stats_mode": "scouted",
        "formation": {c: (counts[c] / total if total else 0.0) for c in CLASSES},
        "formation_counts": {c: float(counts[c]) for c in CLASSES},
        "quality": {c: {"fc": int(fcs[c]), "tier": float(tiers[c]),
                        "t12_stack": int(t12_stacks.get(c, 0))} for c in CLASSES},
        "panel": panel,
        "panel_is_final": True, "widgets_in_panel": True,
        "own_buffs": {}, "debuffs_on_enemy": {},
        "lead_heroes": leads, "joiners": list(joiners or []),
    }


def _from_pvp_t12(rep: dict) -> tuple[dict, dict, dict]:
    """pvp_t12_report -> (own=attacker, enemy=defender, expected). Marty/Amanda
    (the user) always attacked in these five."""
    def side(block, role):
        comp = block["composition"]
        counts = {c: comp[c]["count"] for c in CLASSES}
        tiers = {c: comp[c].get("avg_tier", comp[c].get("tier", 11)) for c in CLASSES}
        fcs = {c: comp[c].get("fc", 10) for c in CLASSES}
        t12 = block.get("t12_skill_levels") or {}
        t12_stacks = {c: int(t12.get(_T12_KEY[c], 0)) for c in CLASSES}
        return _side_scenario(
            role, block["troops"], counts, tiers, fcs,
            _scaled_panel(block["panel_pct"], is_pct=True),
            block["lead_heroes"],
            block.get("joiner_flags") or block.get("joiners") or [],
            t12_stacks)
    own = side(rep["attacker"], "rally")
    enemy = side(rep["defender"], "garrison")
    a, d = rep["attacker"], rep["defender"]
    expected = {
        "real_winner": "own" if rep["outcome"].startswith("attacker") else "enemy",
        "own_surv_frac": a["survivors"] / a["troops"],
        "enemy_surv_frac": d["survivors"] / d["troops"],
        "own_role": "attacker",
    }
    return own, enemy, expected


def _from_raw(rep: dict, rid: str) -> tuple[dict, dict, dict]:
    """raw report -> (own=friendly, enemy=enemy, expected)."""
    def side(block, who):
        comp = block["composition"]
        total = int(block["troops"])
        counts, tiers, fcs = {}, {}, {}
        for c in CLASSES:
            cc = comp.get(c) or {}
            counts[c] = round(total * cc.get("share", 0.0))
            tiers[c] = cc.get("tier_level", 11.0)
            fcs[c] = cc.get("fc_badge", 10)
        role = "rally" if block.get("role") == "Attacker" else "garrison"
        leads = _leads_by_class(
            [h.get("name") if isinstance(h, dict) else h
             for h in (block.get("lead_heroes") or [])], CLASSES)
        joiners = block.get("joiner_flags") or RAW_JOINERS.get((rid, who), [])
        return _side_scenario(role, total, counts, tiers, fcs,
                              _scaled_panel(block.get("scouted") or {}, is_pct=False),
                              leads, joiners, {})
    own = side(rep["friendly"], "friendly")
    enemy = side(rep["enemy"], "enemy")
    f, e = rep["friendly"], rep["enemy"]
    expected = {
        "real_winner": "own" if rep["outcome_friendly"] == "victory" else "enemy",
        "own_surv_frac": (f.get("survivors") or 0) / f["troops"] if f.get("troops") else 0.0,
        "enemy_surv_frac": (e.get("survivors") or 0) / e["troops"] if e.get("troops") else 0.0,
        "own_role": f.get("role", "?").lower(),
    }
    return own, enemy, expected


def golden_anchors() -> list[tuple[str, dict, dict]]:
    out = []
    for n in range(1, 6):
        p = DATA / f"pvp_t12_report_00{n}.json"
        if p.exists():
            rep = json.loads(p.read_text())
            own, enemy, exp = _from_pvp_t12(rep)
            out.append((f"T12_{n:02d}", {"own": own, "enemy": enemy}, exp))
    rdir = DATA / "reports"
    for n in range(1, 9):
        p = rdir / f"report_00{n}.json"
        if not p.exists():
            continue
        rep = json.loads(p.read_text())
        if n == 1:                            # joiners never identified -> flag
            pass
        own, enemy, exp = _from_raw(rep, f"report_00{n}")
        exp["note"] = "" if (f"report_00{n}", "friendly") in RAW_JOINERS or n == 1 \
            else "joiners-from-struct"
        out.append((f"RAW_{n:02d}", {"own": own, "enemy": enemy}, exp))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for aid, scen, exp in golden_anchors():
        payload = {"wos_config": 1, "name": aid, "runs": 200, "seed": 4471,
                   "own": scen["own"], "enemy": scen["enemy"],
                   "_expected_real_outcome": exp}
        (OUT / f"{aid}.json").write_text(json.dumps(payload, indent=2))
        manifest.append((aid, exp["real_winner"], round(exp["own_surv_frac"], 3),
                         round(exp["enemy_surv_frac"], 3), exp.get("own_role")))
    print(f"wrote {len(manifest)} normalized scenarios to {OUT}")
    print(f"{'id':9} {'real_winner':11} {'own_surv':>8} {'enemy_surv':>10} own_role")
    for aid, w, osf, esf, role in manifest:
        print(f"{aid:9} {w:11} {osf:8.3f} {esf:10.3f} {role}")


if __name__ == "__main__":
    main()
