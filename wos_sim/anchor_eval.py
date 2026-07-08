"""Anchor evaluation harness for the turn engine (ENGINE_REBUILD P1/P2).

Runs the three T12 ground-truth battles through ``pvp_turn_engine`` exactly the
way production does (profiles -> construct.build -> skill_defs_from_matchup ->
simulate_turns) and scores them against the calibration gates
(03_QA_CALIBRATION.md G1-G7 + 05_ANCHOR3 SS3).

    py -m wos_sim.anchor_eval                     # scorecard, TURN_PARAMS defaults
    py -m wos_sim.anchor_eval --set rate=80 --set ambush_frac=2
    py -m wos_sim.anchor_eval --log A3            # + per-turn casualty trace
    py -m wos_sim.anchor_eval --engine general    # same scorecard, legacy engine

Anchors:
  A1  wos_sim/data/pvp_t12_report_001.json  (rally, near-even, MARKS survive)
  A2  wos_sim/data/pvp_t12_report_002.json  (rally, near-even, LANCERS survive)
  A3  Scenarios/Calibration_Amanda_Omar.json (solo, decisive, via the UI path)
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from wos_sim.models import TroopType
from wos_sim.predictor import construct as _construct
from wos_sim.predictor import serialize
from wos_sim.predictor.profiles import ClassQuality, Matchup, SideProfile

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "data"
CLASSES = ("Infantry", "Lancer", "Marksman")
STATS = ("Attack", "Defense", "Lethality", "Health")
_T12_KEY = {"Infantry": "indomitable_wall", "Lancer": "meridian_phalanx",
            "Marksman": "starfire"}


def _profile_from_report_side(side: dict, role: str, joiners: list) -> SideProfile:
    comp = side["composition"]
    counts = {c: float(comp[c]["count"]) for c in CLASSES}
    total = int(sum(counts.values()))
    t12 = side.get("t12_skill_levels", {})
    quality = {}
    for c in CLASSES:
        row = comp[c]
        quality[c] = ClassQuality(
            tier=float(row.get("avg_tier", row.get("tier", 11))),
            fc=int(row.get("fc", 10)),
            t12_stack=int(t12.get(_T12_KEY[c], row.get("t12_stack", 0))))
    return SideProfile(
        role=role, troops_total=total, stats_mode="scouted",
        formation={c: counts[c] / total for c in CLASSES},
        formation_counts=counts,
        quality=quality,
        panel={(c, s): side["panel_pct"][c][s] / 100.0 for c in CLASSES for s in STATS},
        panel_is_final=True,
        lead_heroes=side["lead_heroes"],
        joiners=list(joiners or []))


def _load_report_anchor(path: Path) -> Matchup:
    rep = json.loads(path.read_text())
    att, dfn = rep["attacker"], rep["defender"]
    own = _profile_from_report_side(att, "rally", att.get("joiner_flags") or att.get("joiners"))
    enemy = _profile_from_report_side(dfn, "garrison", dfn.get("joiner_flags") or dfn.get("joiners"))
    return Matchup(own, enemy)


def _load_scenario_anchor(path: Path) -> Matchup:
    sc = json.loads(path.read_text())
    return Matchup(serialize.profile_from_dict(sc["own"]),
                   serialize.profile_from_dict(sc["enemy"]))


# reality: per-anchor gate targets. "att_*_loss" are fractions of the class start.
REALITY = {
    "A1": dict(winner="A", turns=(15, 17), surv_type=TroopType.MARKSMAN,
               att_surv_band=(30_000, 110_000), att_surv_real=62_364,
               def_wiped=True,
               triggers={("attacker", "Elif", "skill_3"): 12,
                         ("defender", "Elif", "skill_3"): 15,
                         ("defender", "Cara", "skill_3"): 6,
                         ("attacker", "Vulcanus", "skill_2"): 7,
                         ("attacker", "Vulcanus", "skill_3"): 6}),
    "A2": dict(winner="A", turns=(23, 27), surv_type=TroopType.LANCER,
               att_surv_band=(60_000, 190_000), att_surv_real=118_068,
               def_wiped=True,
               triggers={("attacker", "Elif", "skill_3"): 19,
                         ("defender", "Elif", "skill_3"): 22,
                         ("defender", "Cara", "skill_3"): 9,
                         ("attacker", "Vulcanus", "skill_2"): 10,
                         ("attacker", "Vulcanus", "skill_3"): 9}),
    "A3": dict(winner="A", turns=(17, 22), surv_type=None,
               att_surv_frac_band=(0.20, 0.50), att_surv_real=93_432,
               def_wiped=True,
               class_gates=dict(lancer_loss_max=0.05,
                                marks_loss_band=(0.45, 0.85),
                                inf_surv_frac_band=(0.0, 0.15)),
               triggers={}),
    # Amanda vs RampageR+Dolan (solo, decisive, all-T11, marksman-heavy garrison
    # with leth/health-stacked panels). Report also gives per-skill kill counts
    # -> skill_kill_share gate (real: ~7% of casualties are skill-attributed).
    "A4": dict(winner="A", turns=(14, 18), surv_type=None,
               att_surv_frac_band=(0.45, 0.70), att_surv_real=152_854,
               def_wiped=True,
               class_gates=dict(lancer_loss_max=0.05,
                                marks_loss_band=(0.05, 0.30),
                                inf_surv_frac_band=(0.25, 0.55)),
               skill_kill_share_max=0.20,
               triggers={}),
}


def anchors() -> list[tuple[str, Matchup]]:
    return [
        ("A1", _load_report_anchor(DATA / "pvp_t12_report_001.json")),
        ("A2", _load_report_anchor(DATA / "pvp_t12_report_002.json")),
        ("A3", _load_scenario_anchor(ROOT / "Scenarios" / "Calibration_Amanda_Omar.json")),
        ("A4", _load_scenario_anchor(ROOT / "Scenarios" / "Calibration_Amanda_Ramp.json")),
    ]


def _telemetry_lookup(tel: dict, side: str, hero: str, slot: str):
    for row in (tel or {}).get(side, {}).get("heroes", []):
        if row.get("hero") == hero:
            for s in row.get("skills", []):
                if s.get("slot") == slot:
                    return s.get("triggers")
    return None


def run_turn(matchup: Matchup, params: dict | None, seed: int = 0):
    from wos_sim.pvp_turn_engine import run_construct
    # mirror api.predict: the turn engine owns ALL skill effects, so it gets
    # panel-only units (no legacy hero-skill folding).
    con = _construct.build(matchup, apply_legacy_skills=False)
    return con, run_construct(con, random.Random(seed), params=params)


def run_general(matchup: Matchup, params: dict | None):
    from wos_sim.predictor.kernel import DEFAULT_PVP_PARAMS
    from wos_sim.pvp_engine import simulate_pvp
    con = _construct.build(matchup)
    p = dict(DEFAULT_PVP_PARAMS)
    p.update(con.engine_params)
    if params:
        p.update(params)
    res = simulate_pvp(con.attacker_units, con.defender_units, p)
    return con, res


def scorecard(name: str, con, res, is_turn: bool) -> dict:
    real = REALITY[name]
    if is_turn:
        a_surv = dict(res.a_survivors)
        d_total = sum(res.d_survivors.values())
        tel = res.skill_telemetry
    else:
        start = {u.troop: u.n for u in con.attacker_units}
        a_surv = {t: start[t] - res.a_incap.get(t, 0.0) for t in start}
        d_start = {u.troop: u.n for u in con.defender_units}
        d_total = sum(d_start.values()) - sum(res.d_incap.values())
        tel = None
    a_start = {u.troop: u.n for u in con.attacker_units}
    a_total = sum(a_surv.values())
    surv_type = max(a_surv, key=a_surv.get) if a_total > 1 else None

    checks = {}
    checks["winner"] = (res.winner, real["winner"], res.winner == real["winner"])
    lo, hi = real["turns"]
    checks["turns"] = (res.turns, f"[{lo},{hi}]", lo <= res.turns <= hi)
    if real.get("surv_type") is not None:
        checks["surv_type"] = (surv_type.name if surv_type else None,
                               real["surv_type"].name,
                               surv_type == real["surv_type"])
    if "att_surv_band" in real:
        lo, hi = real["att_surv_band"]
        checks["att_surv"] = (round(a_total), f"[{lo},{hi}] real {real['att_surv_real']}",
                              lo <= a_total <= hi)
    if "att_surv_frac_band" in real:
        lo, hi = real["att_surv_frac_band"]
        frac = a_total / sum(a_start.values())
        checks["att_surv"] = (f"{frac:.1%}", f"[{lo:.0%},{hi:.0%}] real 34.3%",
                              lo <= frac <= hi)
    checks["def_wiped"] = (round(d_total), 0, d_total <= max(1.0, 1e-6))
    for cls_gate, spec in (real.get("class_gates") or {}).items():
        if cls_gate == "lancer_loss_max":
            loss = 1 - a_surv[TroopType.LANCER] / a_start[TroopType.LANCER]
            checks["lancer_loss"] = (f"{loss:.1%}", f"<{spec:.0%}", loss < spec)
        elif cls_gate == "marks_loss_band":
            loss = 1 - a_surv[TroopType.MARKSMAN] / a_start[TroopType.MARKSMAN]
            checks["marks_loss"] = (f"{loss:.1%}", f"[{spec[0]:.0%},{spec[1]:.0%}]",
                                    spec[0] <= loss <= spec[1])
        elif cls_gate == "inf_surv_frac_band":
            frac = a_surv[TroopType.INFANTRY] / a_start[TroopType.INFANTRY]
            checks["inf_surv"] = (f"{frac:.1%}", f"({spec[0]:.0%},{spec[1]:.0%}]",
                                  spec[0] < frac <= spec[1])
    for (side, hero, slot), want in (real.get("triggers") or {}).items():
        got = _telemetry_lookup(tel, side, hero, slot) if tel else None
        ok = got is not None and abs(got - want) <= 1
        checks[f"trig {side[:3]} {hero} {slot[-1]}"] = (got, f"{want}+-1", ok)
    if real.get("skill_kill_share_max") is not None and is_turn and tel:
        # share of casualties attributed to SKILL packets (vs base attacks).
        # Reality (A4 report, per-skill kill columns both sides): ~7%.
        cap = real["skill_kill_share_max"]
        for side_key, incap in (("attacker", res.d_incap), ("defender", res.a_incap)):
            dealt = sum(incap.values())
            skill_kills = 0.0
            for row in tel.get(side_key, {}).get("heroes", []):
                skill_kills += sum(float(s.get("kills") or 0) for s in row.get("skills", []))
            for row in tel.get(side_key, {}).get("troop_skills", []):
                skill_kills += float(row.get("kills") or 0)
            share = skill_kills / dealt if dealt > 0 else 0.0
            checks[f"skill_kill_share {side_key[:3]}"] = (
                f"{share:.1%}", f"<{cap:.0%} (real ~7%)", share < cap)
    return checks


def print_scorecard(name: str, checks: dict):
    n_ok = sum(1 for *_, ok in checks.values() if ok)
    print(f"--- {name}: {n_ok}/{len(checks)} gates ---")
    for key, (got, want, ok) in checks.items():
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {key:24} got={got}  want={want}")


def dump_log(res, max_rows: int = 40):
    print("turn |    att inf/lan/mar (start)      |    def inf/lan/mar (start)      | top kill sources")
    for rec in res.turn_log[:max_rows]:
        sa = rec.start_counts["attacker"]
        sd = rec.start_counts["defender"]
        both = {**{f"A:{k}": v for k, v in rec.kills_by_source["attacker"].items()},
                **{f"D:{k}": v for k, v in rec.kills_by_source["defender"].items()}}
        top = sorted(both.items(), key=lambda kv: -kv[1])[:3]
        tops = ", ".join(f"{k}={v:,.0f}" for k, v in top)
        print(f"{rec.turn:4} | {sa.get(TroopType.INFANTRY,0):9,.0f}/{sa.get(TroopType.LANCER,0):9,.0f}/{sa.get(TroopType.MARKSMAN,0):9,.0f} "
              f"| {sd.get(TroopType.INFANTRY,0):9,.0f}/{sd.get(TroopType.LANCER,0):9,.0f}/{sd.get(TroopType.MARKSMAN,0):9,.0f} | {tops}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", action="append", default=[], metavar="K=V",
                    help="override a TURN_PARAMS knob, e.g. --set rate=80")
    ap.add_argument("--engine", choices=("turn", "general"), default="turn")
    ap.add_argument("--log", choices=("A1", "A2", "A3"), default=None,
                    help="dump the per-turn trace for one anchor (turn engine only)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    params = {}
    for kv in args.set:
        k, v = kv.split("=", 1)
        params[k] = float(v)
    total_ok = total = 0
    for name, matchup in anchors():
        if args.engine == "turn":
            con, res = run_turn(matchup, params, seed=args.seed)
            checks = scorecard(name, con, res, is_turn=True)
        else:
            con, res = run_general(matchup, params)
            checks = scorecard(name, con, res, is_turn=False)
        print_scorecard(name, checks)
        if args.log == name and args.engine == "turn":
            dump_log(res)
        total_ok += sum(1 for *_, ok in checks.values() if ok)
        total += len(checks)
    print(f"=== TOTAL {total_ok}/{total} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
