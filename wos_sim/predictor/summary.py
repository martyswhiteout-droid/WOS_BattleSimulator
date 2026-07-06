"""Layer 2 — turn per-run RunRecords into the statistics the UI renders.

Everything is reported from the OWN perspective (A/D mapped via
own_is_attacker), and mutual wipes count as the ATTACKER's win.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from wos_sim.models import TroopType
from . import skill_display

_TROOP = {"Infantry": TroopType.INFANTRY, "Lancer": TroopType.LANCER, "Marksman": TroopType.MARKSMAN}


@dataclass
class Proportion:
    p: float
    se: float               # Monte-Carlo standard error


@dataclass
class Distribution:
    counts: list            # frequency per bin
    edges: list             # bin edges (len = nbins + 1)
    median: float
    mean: float
    p5: float
    p95: float


def _percentile(sorted_vals: list, q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = q * (len(sorted_vals) - 1)
    lo, hi = int(math.floor(rank)), int(math.ceil(rank))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (rank - lo) * (sorted_vals[hi] - sorted_vals[lo])


def _distribution(values: list, lo: float, hi: float, nbins: int) -> Distribution:
    width = (hi - lo) / nbins if hi > lo else 1.0
    counts = [0] * nbins
    for v in values:
        idx = min(max(int((v - lo) / width), 0), nbins - 1)
        counts[idx] += 1
    edges = [lo + i * width for i in range(nbins + 1)]
    s = sorted(values)
    mean = sum(values) / len(values) if values else 0.0
    return Distribution(counts, edges, _percentile(s, 0.5), mean,
                        _percentile(s, 0.05), _percentile(s, 0.95))


def _prop(count: int, n: int) -> Proportion:
    p = count / n if n else 0.0
    return Proportion(p, math.sqrt(p * (1 - p) / n) if n else 0.0)


def _own_enemy(r, own_is_attacker):
    """(own_start, own_incap, enemy_start, enemy_incap) dicts for one run."""
    if own_is_attacker:
        return r.attacker_start, r.attacker_incap, r.defender_start, r.defender_incap
    return r.defender_start, r.defender_incap, r.attacker_start, r.attacker_incap


def _survivor_pct(start: dict, incap: dict) -> float:
    total = sum(start.values())
    return (total - sum(incap.values())) / total if total else 0.0


def _own_won(r, own_is_attacker: bool) -> bool:
    own_side = 'A' if own_is_attacker else 'D'
    return r.winner == own_side or (r.winner == 'mutual' and own_is_attacker)


def _bucket(r, own_is_attacker: bool) -> int:
    """1-8 by the WINNER's surviving-troop %. Defeats 1-4, victories 5-8."""
    own_start, own_incap, enemy_start, enemy_incap = _own_enemy(r, own_is_attacker)
    if _own_won(r, own_is_attacker):
        sp = _survivor_pct(own_start, own_incap)
        return 8 if sp >= 0.75 else 7 if sp >= 0.50 else 6 if sp >= 0.25 else 5
    sp = _survivor_pct(enemy_start, enemy_incap)          # the enemy is the winner
    return 1 if sp >= 0.75 else 2 if sp >= 0.50 else 3 if sp >= 0.25 else 4


def _loss_pct(start: dict, incap: dict) -> float:
    total = sum(start.values())
    return 100.0 * sum(incap.values()) / total if total else 0.0


def _army_loss_dist(records, own_is_attacker, which, nbins=10):   # 10% brackets
    vals = []
    for r in records:
        os_, oi, es, ei = _own_enemy(r, own_is_attacker)
        start, incap = (os_, oi) if which == 'own' else (es, ei)
        vals.append(_loss_pct(start, incap))
    return _distribution(vals, 0.0, 100.0, nbins)


def _class_loss_dist(records, own_is_attacker, which, troop, nbins=10):   # 10% brackets
    vals = []
    for r in records:
        os_, oi, es, ei = _own_enemy(r, own_is_attacker)
        start, incap = (os_, oi) if which == 'own' else (es, ei)
        s = start.get(troop, 0)
        if s > 0:
            vals.append(100.0 * incap.get(troop, 0) / s)
    return _distribution(vals, 0.0, 100.0, nbins) if vals else None


def _skill_values(skill_row: dict) -> tuple[float, float]:
    triggers = float(skill_row.get("triggers") or 0.0)
    kills = float(skill_row.get("kills") or 0.0)
    return triggers, kills


def _metric_dist(values: list[float], nbins: int = 12) -> Distribution:
    hi = max(values) if values else 1.0
    return _distribution(values, 0.0, hi if hi > 0 else 1.0, nbins)


def _hero_rows_for(tel: dict | None, side_key: str) -> list:
    return (((tel or {}).get(side_key) or {}).get("heroes") or [])


def _troop_rows_for(tel: dict | None, side_key: str) -> list:
    return (((tel or {}).get(side_key) or {}).get("troop_skills") or [])


def _matching_hero_row(rows: list, template: dict, idx: int) -> dict:
    if idx < len(rows) and rows[idx].get("hero") == template.get("hero"):
        return rows[idx]
    for row in rows:
        if (row.get("hero") == template.get("hero")
                and row.get("role") == template.get("role")
                and row.get("troop") == template.get("troop")):
            return row
    return {}


def _matching_skill(skills: list, template: dict) -> dict:
    slot = template.get("slot")
    name = template.get("name")
    if name:
        for skill in skills:
            if skill.get("name") == name:
                return skill
    for skill in skills:
        if slot and skill.get("slot") == slot:
            return skill
    return {}


def _skill_dist_for(records, side_key: str, group_kind: str, group_idx: int,
                    group_template: dict, skill_template: dict):
    trigger_vals, kill_vals = [], []
    for r in records:
        tel = getattr(r, "skill_telemetry", None)
        if group_kind == "hero":
            rows = _hero_rows_for(tel, side_key)
            group = _matching_hero_row(rows, group_template, group_idx)
            actual = _matching_skill(group.get("skills") or [], skill_template)
        else:
            rows = _troop_rows_for(tel, side_key)
            actual = _matching_skill(rows, skill_template)
        triggers, kills = _skill_values(actual)
        trigger_vals.append(triggers)
        kill_vals.append(kills)
    return _metric_dist(trigger_vals), _metric_dist(kill_vals)


def _hero_group(records, side_key: str, idx: int, row: dict,
                troop_skills: list | None = None) -> dict:
    skills = []
    for skill_row in row.get("skills") or []:
        meta = skill_display.hero_skill(row.get("hero"), skill_row.get("slot"))
        triggers, kills = _skill_dist_for(records, side_key, "hero", idx, row, skill_row)
        skills.append({
            "source": "hero",
            "slot": skill_row.get("slot"),
            "name": meta["name"],
            "icon": meta["icon"],
            "effect": meta["effect"],
            "triggers": triggers,
            "kills": kills,
        })
    skills.extend(troop_skills or [])
    return {
        "kind": "hero",
        "hero": row.get("hero", ""),
        "role": row.get("role", ""),
        "troop": row.get("troop"),
        "skills": skills,
    }


def _troop_group(records, side_key: str, template: list) -> dict | None:
    skills = []
    for idx, skill_row in enumerate(template):
        meta = skill_display.troop_skill(skill_row.get("name"))
        triggers, kills = _skill_dist_for(records, side_key, "troop", idx, {}, skill_row)
        skills.append({
            "slot": skill_row.get("name"),
            "name": meta["name"],
            "icon": meta["icon"],
            "effect": meta["effect"],
            "troop": skill_row.get("troop") or meta.get("troop"),
            "triggers": triggers,
            "kills": kills,
        })
    if not skills:
        return None
    return {
        "kind": "troop",
        "hero": "Troop Skills",
        "role": "troop",
        "troop": None,
        "skills": skills,
    }


def _troop_skills_by_troop(records, side_key: str) -> dict:
    template = []
    for r in records:
        rows = [row for row in _troop_rows_for(getattr(r, "skill_telemetry", None), side_key)
                if not row.get("is_passive")]
        if rows:
            template = rows
            break
    grouped = {}
    for idx, skill_row in enumerate(template):
        meta = skill_display.troop_skill(skill_row.get("name"))
        troop = skill_row.get("troop") or meta.get("troop")
        triggers, kills = _skill_dist_for(records, side_key, "troop", idx, {}, skill_row)
        grouped.setdefault(troop or "", []).append({
            "source": "troop",
            "slot": skill_row.get("name"),
            "name": meta["name"],
            "icon": meta["icon"],
            "effect": meta["effect"],
            "troop": troop,
            "triggers": triggers,
            "kills": kills,
        })
    return grouped


def _skill_telemetry(records, own_is_attacker: bool):
    if not any(getattr(r, "skill_telemetry", None) for r in records):
        return None
    side_keys = {
        "own": "attacker" if own_is_attacker else "defender",
        "enemy": "defender" if own_is_attacker else "attacker",
    }
    out = {}
    for label, side_key in side_keys.items():
        template = []
        for r in records:
            rows = _hero_rows_for(getattr(r, "skill_telemetry", None), side_key)
            if rows:
                template = rows
                break
        side_out = []
        troop_by_class = _troop_skills_by_troop(records, side_key)
        attached_troops = set()
        for idx, row in enumerate(template):
            extras = []
            if row.get("role") == "captain":
                attached_troops.add(row.get("troop"))
                extras = troop_by_class.get(row.get("troop"), [])
            side_out.append(_hero_group(records, side_key, idx, row, extras))
        for troop, skills in troop_by_class.items():
            if troop not in attached_troops:
                side_out.append({
                    "kind": "troop",
                    "hero": f"{troop or 'Troop'} Skills",
                    "role": "troop",
                    "troop": troop,
                    "skills": skills,
                })
        out[label] = side_out
    return out


@dataclass
class Forecast:
    n: int
    p_win: Proportion
    p_mutual: Proportion
    p_loss: Proportion
    p_win_effective: float      # incl. mutual when own is the attacker
    p_loss_effective: float     # incl. mutual when own is the defender
    outcome_quality: dict       # bucket 1..8 -> count
    army_losses: dict           # {'own': Distribution, 'enemy': Distribution}  (% troops lost)
    class_losses: dict          # {class: {'own': Distribution|None, 'enemy': ...}}
    rounds: dict                # {'win': Distribution|None, 'loss': Distribution|None}
    skill_telemetry: dict | None = None
    engine_model_error: float = 0.13    # per-matchup, from engine_meta
    engine_path: str = "general"        # "pvp_kernel" (validated) | "general" (provisional)
    engine_note: str = ""               # honest one-liner for the tooltip
    stochastic: bool = True             # False -> single certain outcome (no distribution/convergence)
    severe_fraction: float = 0.35       # permanent (severe) losses = incap x this (fortress PvP)
    calibrated: bool = False            # True only inside the validated (pvp_kernel) box -> model_error is a
    near_even: bool = False
    confidence: str = "directional"
                                        #   real band. False -> model_error is a coarse floor; render the UI
                                        #   as "directional", NOT "± N%" (engine_meta QA note).


def summarize(records, own_is_attacker: bool, engine_model_error: float = 0.13,
              engine_path: str = "general", engine_note: str = "",
              stochastic: bool = True, severe_fraction: float = 0.35,
              calibrated: bool = False, near_even: bool = False,
              confidence: str = "directional") -> Forecast:
    n = len(records)
    own, enemy = ('A', 'D') if own_is_attacker else ('D', 'A')
    wins = sum(1 for r in records if r.winner == own)
    mutual = sum(1 for r in records if r.winner == 'mutual')
    losses = sum(1 for r in records if r.winner == enemy)

    eff_win = (wins + mutual) if own_is_attacker else wins        # mutual -> attacker
    eff_loss = (losses + mutual) if not own_is_attacker else losses

    buckets = {i: 0 for i in range(1, 9)}
    for r in records:
        buckets[_bucket(r, own_is_attacker)] += 1

    army_losses = {'own': _army_loss_dist(records, own_is_attacker, 'own'),
                   'enemy': _army_loss_dist(records, own_is_attacker, 'enemy')}
    class_losses = {cls: {'own': _class_loss_dist(records, own_is_attacker, 'own', troop),
                          'enemy': _class_loss_dist(records, own_is_attacker, 'enemy', troop)}
                    for cls, troop in _TROOP.items()}

    # rounds split by own win/loss, over a shared turn range so the two align
    win_turns = [r.turns for r in records if _own_won(r, own_is_attacker)]
    loss_turns = [r.turns for r in records if not _own_won(r, own_is_attacker)]
    all_turns = win_turns + loss_turns
    lo = min(all_turns) if all_turns else 0.0
    hi = max(all_turns) if all_turns else 1.0
    rounds = {'win': _distribution(win_turns, lo, hi, 34) if win_turns else None,
              'loss': _distribution(loss_turns, lo, hi, 34) if loss_turns else None}

    return Forecast(
        n=n,
        p_win=_prop(wins, n), p_mutual=_prop(mutual, n), p_loss=_prop(losses, n),
        p_win_effective=eff_win / n if n else 0.0,
        p_loss_effective=eff_loss / n if n else 0.0,
        outcome_quality=buckets, army_losses=army_losses,
        class_losses=class_losses, rounds=rounds,
        skill_telemetry=_skill_telemetry(records, own_is_attacker),
        engine_model_error=engine_model_error, engine_path=engine_path,
        engine_note=engine_note, stochastic=stochastic, severe_fraction=severe_fraction,
        calibrated=calibrated, near_even=near_even, confidence=confidence)
