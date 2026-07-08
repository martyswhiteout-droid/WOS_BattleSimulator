"""Layer 3 — JSON boundary. Profile dicts (BRD S.9 shape) <-> SideProfile,
and Forecast -> a JSON-serializable dict the front-end renders directly.

Panel keys are `"Class|Stat"` strings on the wire (JSON can't key on tuples).
"""
from __future__ import annotations

from .profiles import CLASSES, ClassQuality, SideProfile
from .summary import Distribution, Forecast, Proportion


def profile_from_dict(d: dict) -> SideProfile:
    quality = {cls: ClassQuality(tier=float(q.get("tier", 12)), fc=int(q.get("fc", 10)),
                                 t12_stack=int(q.get("t12_stack", 0)))
               for cls, q in (d.get("quality") or {}).items()}
    panel = {}
    for k, v in (d.get("panel") or {}).items():
        cls, stat = k.split("|")
        panel[(cls, stat)] = float(v)
    return SideProfile(
        label=d.get("label", ""), role=d.get("role", "rally"),
        troops_total=int(d.get("troops_total", 1_000_000)),
        stats_mode=d.get("stats_mode", "scouted"),
        formation=d.get("formation") or {"Infantry": 0.5, "Lancer": 0.2, "Marksman": 0.3},
        formation_counts={k: float(v) for k, v in (d.get("formation_counts") or {}).items()},
        quality=quality or {c: ClassQuality() for c in CLASSES},
        panel=panel,
        panel_is_final=bool(d.get("panel_is_final", False)),
        own_buffs=d.get("own_buffs") or {},
        debuffs_on_enemy=d.get("debuffs_on_enemy") or {},
        widgets_in_panel=d.get("widgets_in_panel"),
        lead_heroes=d.get("lead_heroes") or {},
        joiners=d.get("joiners") or [])


def profile_to_dict(p: SideProfile) -> dict:
    return {
        "label": p.label, "role": p.role, "troops_total": p.troops_total,
        "stats_mode": p.stats_mode, "formation": p.formation,
        "formation_counts": p.formation_counts,
        "quality": {c: {"tier": q.tier, "fc": q.fc, "t12_stack": q.t12_stack}
                    for c, q in p.quality.items()},
        "panel": {f"{c}|{s}": v for (c, s), v in p.panel.items()},
        "panel_is_final": p.panel_is_final,
        "own_buffs": p.own_buffs, "debuffs_on_enemy": p.debuffs_on_enemy,
        "widgets_in_panel": p.widgets_in_panel,
        "lead_heroes": p.lead_heroes, "joiners": p.joiners,
    }


def _prop(p: Proportion) -> dict:
    return {"p": p.p, "se": p.se}


def _dist(d: Distribution | None):
    if d is None:
        return None
    return {"counts": d.counts, "edges": d.edges,
            "median": d.median, "mean": d.mean, "p5": d.p5, "p95": d.p95}


def _skill_telemetry(tel):
    if tel is None:
        return None
    return {
        side: [{
            "kind": row.get("kind", "hero"),
            "hero": row.get("hero", ""),
            "role": row.get("role", ""),
            "troop": row.get("troop"),
            "skills": [{
                "source": skill.get("source", "hero"),
                "slot": skill.get("slot"),
                "name": skill.get("name", ""),
                "icon": skill.get("icon"),
                "effect": skill.get("effect", ""),
                "troop": skill.get("troop"),
                "triggers": _dist(skill.get("triggers")),
                "kills": _dist(skill.get("kills")),
            } for skill in row.get("skills", [])],
        } for row in rows]
        for side, rows in tel.items()
    }


def forecast_to_dict(fc: Forecast) -> dict:
    return {
        "n": fc.n,
        "engine": {"path": fc.engine_path, "calibrated": fc.calibrated,
                   "model_error": fc.engine_model_error,
                   "note": fc.engine_note, "stochastic": fc.stochastic,
                   "severe_fraction": fc.severe_fraction,
                   "near_even": fc.near_even,
                   "confidence": fc.confidence},
        "verdict": {"win": _prop(fc.p_win), "mutual": _prop(fc.p_mutual), "loss": _prop(fc.p_loss),
                    "win_effective": fc.p_win_effective, "loss_effective": fc.p_loss_effective,
                    "model_error": fc.engine_model_error},
        "outcome_quality": fc.outcome_quality,
        "army_losses": {k: _dist(v) for k, v in fc.army_losses.items()},
        "class_losses": {cls: {side: _dist(dst) for side, dst in sides.items()}
                         for cls, sides in fc.class_losses.items()},
        "rounds": {k: _dist(v) for k, v in fc.rounds.items()},
        "skill_telemetry": _skill_telemetry(fc.skill_telemetry),
        "battle_timeline": fc.timeline,
    }
