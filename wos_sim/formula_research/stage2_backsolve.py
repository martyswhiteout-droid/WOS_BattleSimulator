"""Stage 2 of the deterministic-formula derivation: exact constraint back-solve.

Input : ledger_dataset.json (built by parse_ledger.py from the canonical
        NANOMART_EXPERIMENT_LEDGER.md; deployed stats already include panels).
Output: stage2_constraints.json + STAGE2_CONSTRAINTS.md (same directory).
Run   : py -m wos_sim.formula_research.stage2_backsolve   (or py stage2_backsolve.py)

Method
------
* Effective per-side inputs = deployed stats x battle-time hero factors:
  Seo-yoon S1 own Attack x1.05/x1.10/x1.15 (L1/2/3); Vulcanus S1 enemy Attack
  x0.96; Vulcanus S3 enemy Infantry/Lancer Defense x0.88 (fires turns 1,4,7,...
  lasting 3 turns => continuous). Directional counter passives (Inf->Lan,
  Lan->MM, MM->Inf) x1.10 are recorded as a separate factor, never folded in.
* The only TIME-VARYING modifier is Vulcanus S2 (every 6th own attack event
  deals +20%; ambiguity branch: target's next-attack damage taken +5%).
  All constant factors stay folded inside the implied rate.
* Implied rate R := damage one side deals per attack event, measured in units
  of ONE target unit's hidden HP (the HP unit itself is left unknown; scaled
  displays x H_target and x (D_raw+H)_target let Stage 3 test HP~H vs HP~D+H).
  With W(T) = T + 1/5*floor(T/6) [+ 1/20*floor((T-1)/6) next-attack branch]
  for a Vulcanus side and W(T) = T otherwise (S2 cadence: own attack events
  6,12,18,... - the alternative cadence 1,7,13,... is REFUTED by the corpus,
  see cadence_check in the output):
    loser side wiped (N units) at exact turn T (casualties land end-of-turn)
        =>  R_winner*W(T) >= N  and  R_winner*W(T-1) < N
        =>  R_winner in [N/W(T), N/W(T-1))     (pool branch when N >= 2)
    winner kept all units  =>  R_loser*W_loser(T) < 1  (upper bound only:
        partial HP is invisible in reports).
  The true T is only known inside a band; constraints are emitted PER
  CANDIDATE T and as the projected union across the band. All arithmetic is
  exact (fractions module); floats are display-only.
* Observed outcomes are used ONLY to compute implied_* quantities (that is
  the purpose of Stage 2); nothing here is a prediction, nothing is fitted.
"""
from __future__ import annotations

from fractions import Fraction as F
from hashlib import sha256
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "ledger_dataset.json")
OUT_JSON = os.path.join(HERE, "stage2_constraints.json")
OUT_MD = os.path.join(HERE, "STAGE2_CONSTRAINTS.md")
LEDGER_FIRST_ROW_LINE = 11  # dataset preserves ledger row order

SY_FACTOR = {1: F(21, 20), 2: F(11, 10), 3: F(23, 20)}
VULC_S1_ENEMY_ATTACK = F(24, 25)
VULC_S3_ENEMY_DEFENSE = F(22, 25)
COUNTER_PAIRS = {("Infantry", "Lancer"), ("Lancer", "Marksman"), ("Marksman", "Infantry")}
COUNTER_MULT = F(11, 10)
S2_BOOST = F(1, 5)      # +20% on the boosted event
S2_NEXTATK = F(1, 20)   # +5% branch: target's next-attack damage taken

BRANCHES = ("s2_plain", "s2_nextatk")

ASSUMPTIONS = [
    "One attack event per side per turn (evidence: every S2 counter equals floor(T/6) "
    "with T taken from the S3 turn clock; a both-sides event count would double it).",
    "Simultaneous resolution; casualties are removed at end of turn, so the loser also "
    "attacks during its final turn T (GAME_RULES 4 / skill brief).",
    "Units removed from battle = loss + injured + lightly_injured (farm context: Loss=0); "
    "survivors never took a removing hit. Partial HP of survivors is invisible.",
    "Vulcanus S3 fires turns 1,4,7,... lasting 3 turns => -12% enemy Inf/Lan Defense is "
    "continuous; recorded turn bands presuppose this cadence (ledger method note).",
    "Deployed A/D/L/H in the dataset already include chief panels; Lethality/Health "
    "panels are 0% in this corpus (ledger header, Martin-confirmed).",
    "The report 'power' column is NOT used in constraints: power loss is demonstrably "
    "non-linear in units removed (e.g. 2v1 attacker loses 2 units at P-3 while 1v1 "
    "attacker loses 1 unit at the same P-3); it is carried as raw data only.",
    "Winner-side damage intervals for loser_count >= 2 assume the POOL overkill model "
    "(cumulative damage carries across units). The per-unit-overkill-wasted branch is "
    "emitted separately where tractable (loser_count == 2) and flagged elsewhere.",
]

BRANCH_REGISTRY = {
    "S2_CADENCE": {
        "question": "Does Vulcanus S2 fire on own attack events 6,12,18,... (A) or 1,7,13,... (B)?",
        "resolution": "A is CONSISTENT with every clocked row; B produces an empty feasible turn set "
                      "on the rows listed in cadence_check.branch_B_refuted_by (derived, not assumed). "
                      "All constraints below use cadence A.",
    },
    "S2_NEXTATK_5PCT": {
        "question": "Does the S2 empowered attack also make the target take +5% damage on the "
                    "following attack (ledger effect text: 'target next-attack Damage Taken +5%'), "
                    "or only +20% on the boosted event (skill-brief reading)?",
        "resolution": "OPEN - both branches emitted for every Vulcanus-side bound: "
                      "s2_plain (x1.2 on events 6k) and s2_nextatk (additionally x1.05 on events 6k+1).",
    },
    "S2_KILL_SEMANTICS": {
        "question": "Are S2 'K' kills just pool crossings that happened on a boosted event "
                    "(bookkeeping), or extra execute-kills beyond damage?",
        "resolution": "OPEN - affects only the five clocked ladder rows (K=1/1/1/2/1). Aggregate "
                      "records carry kills_by_damage for both readings.",
    },
    "POOL_VS_UNIT_OVERKILL": {
        "question": "Does damage overkill carry across units (side-level HP pool) or is it wasted "
                    "on the dying unit (per-unit targeting)?",
        "resolution": "OPEN - matters only when the wiped side had >= 2 units. Both branches emitted "
                      "for the two 2v1 defeats; larger rows are aggregate-only.",
    },
    "COUNT_LAW": {
        "question": "How does a stack's per-event output scale with live count N (g(N): linear, "
                    "sqrt, frontage)?",
        "resolution": "OPEN by design - multi-unit rates are emitted as g(N)*rate with the count "
                      "factor symbolic; ladder rows stay aggregate for Stage 3 simulation.",
    },
}


def frac(x) -> F:
    return F(str(x))


def fs(fr: F) -> str:
    return f"{fr.numerator}/{fr.denominator}"


def num(fr: F) -> float:
    return float(fr)


def weight(T: int, has_vulc: bool, nextatk: bool) -> F:
    """Cumulative damage weight of one side's first T attack events (cadence A)."""
    if T <= 0:
        return F(0)
    w = F(T)
    if has_vulc:
        w += S2_BOOST * (T // 6)
        if nextatk:
            w += S2_NEXTATK * ((T - 1) // 6)
    return w


def weights_at(T: int, has_vulc: bool) -> dict:
    return {
        "s2_plain": {"W_T": fs(weight(T, has_vulc, False)), "W_Tm1": fs(weight(T - 1, has_vulc, False))},
        "s2_nextatk": {"W_T": fs(weight(T, has_vulc, True)), "W_Tm1": fs(weight(T - 1, has_vulc, True))},
    }


def interval(lo: F, hi: F | None, scales: dict) -> dict:
    d = {
        "lo": fs(lo), "lo_float": num(lo), "lo_closed": True,
        "hi": fs(hi) if hi is not None else None,
        "hi_float": num(hi) if hi is not None else None,
        "hi_closed": False,
    }
    for label, s in scales.items():
        d[f"lo_x_{label}"] = fs(lo * s)
        d[f"lo_x_{label}_float"] = num(lo * s)
        d[f"hi_x_{label}"] = fs(hi * s) if hi is not None else None
        d[f"hi_x_{label}_float"] = num(hi * s) if hi is not None else None
    return d


def upper_bound(ub: F, scales: dict) -> dict:
    d = {"ub": fs(ub), "ub_float": num(ub), "closed": False}
    for label, s in scales.items():
        d[f"ub_x_{label}"] = fs(ub * s)
        d[f"ub_x_{label}_float"] = num(ub * s)
    return d


def side_view(row: dict, key: str) -> dict:
    mine, other = row[key], row["def" if key == "att" else "att"]
    heroes, opp = mine["heroes"], other["heroes"]
    has_vulc = any(k.startswith("vulc") for k in heroes)
    opp_vulc = any(k.startswith("vulc") for k in opp)
    sy = heroes.get("seoyoon_s1")
    cls, ocls = mine["force"]["cls"], other["force"]["cls"]
    A, D = frac(mine["stats"]["A"]), frac(mine["stats"]["D"])
    L, H = frac(mine["stats"]["L"]), frac(mine["stats"]["H"])
    factors = {}
    A_eff = A
    if sy:
        A_eff *= SY_FACTOR[sy]
        factors["seoyoon_s1"] = fs(SY_FACTOR[sy])
    if opp_vulc:
        A_eff *= VULC_S1_ENEMY_ATTACK
        factors["vulc_s1_enemy_attack"] = fs(VULC_S1_ENEMY_ATTACK)
    D_eff = D
    if opp_vulc and cls in ("Infantry", "Lancer"):
        D_eff *= VULC_S3_ENEMY_DEFENSE
        factors["vulc_s3_enemy_defense"] = fs(VULC_S3_ENEMY_DEFENSE)
    n = mine["force"]["count"]
    out = mine["out"]
    removed = sorted({c for c in (
        n - out["surv"] if out["surv"] is not None else None,
        (out["loss"] or 0) + (out["inj"] or 0) + (out["light"] or 0)
        if out["inj"] is not None or out["light"] is not None or out["loss"] is not None else None,
    ) if c is not None})
    return {
        "count": n,
        "cls": cls,
        "tier": mine["force"]["tier"],
        "stats_raw": {k: fs(frac(v)) for k, v in mine["stats"].items()},
        "A_eff": fs(A_eff), "A_eff_float": num(A_eff),
        "D_eff": fs(D_eff), "D_eff_float": num(D_eff),
        "L": fs(L), "H": fs(H),
        "battle_factors": factors,
        "counter_mult": fs(COUNTER_MULT if (cls, ocls) in COUNTER_PAIRS else F(1)),
        "has_vulc": has_vulc,
        "sy_level": sy,
        "s2_T": heroes.get("vulc_s2_T"), "s2_K": heroes.get("vulc_s2_K"),
        "s3_T": heroes.get("vulc_s3_T"),
        "outcome_raw": out,
        "removed_candidates": removed,
        "removed_quirk": len(removed) > 1,
        "_A_eff": A_eff, "_D_eff": D_eff, "_D_raw": D, "_L": L, "_H": H,
    }


def turn_analysis(row: dict) -> dict:
    rec = (row["turns_lo"], row["turns_hi"]) if row["turns_lo"] else None
    s2_bands_A, s2_bands_B, s3_bands = [], [], []
    for key in ("att", "def"):
        h = row[key]["heroes"]
        c2, c3 = h.get("vulc_s2_T"), h.get("vulc_s3_T")
        if c2:
            s2_bands_A.append([6 * c2, 6 * c2 + 5])
            s2_bands_B.append([6 * c2 - 5, 6 * c2])
        if c3:
            s3_bands.append([3 * c3 - 2, 3 * c3])

    def intersect(bandlists):
        if rec is None:
            return None
        lo, hi = rec
        for b_lo, b_hi in bandlists:
            lo, hi = max(lo, b_lo), min(hi, b_hi)
        return list(range(lo, hi + 1)) if lo <= hi else []

    t_A = intersect(s2_bands_A + s3_bands)
    t_B = intersect(s2_bands_B + s3_bands)
    return {
        "recorded": list(rec) if rec else None,
        "s2_bands_cadence_A": s2_bands_A,
        "s2_bands_cadence_B": s2_bands_B,
        "s3_bands": s3_bands,
        "t_set": t_A,
        "t_set_cadence_B": t_B,
        "narrowed_vs_recorded": bool(rec and t_A and (t_A[0] > rec[0] or t_A[-1] < rec[1])),
        "conflict_empty_t_set": bool(rec and t_A == []),
    }


EXP4_BASE = {"att": {"A": F("1.022"), "D": F("4.008"), "L": F(1), "H": F(6)},
             "def": {"A": F("1.020"), "D": F("4.000"), "L": F(1), "H": F(6)}}


def exp4_label_check(row: dict) -> list:
    """Exp4 rows are T1-Inf-mirror panel probes named Att+.../Def+....
    The captured deployed stats are authoritative; flag rows whose name
    declares a different set of boosted stats than was actually deployed."""
    import re
    quirks = []
    if "Exp4" not in row["name"]:
        return quirks
    for key, prefix in (("att", "Att"), ("def", "Def")):
        m = re.search(prefix + r"((?:\+\d+[ADLH])+)", row["name"])
        named = set(re.findall(r"[ADLH]", m.group(1))) if m else set()
        observed = {stat for stat, base in EXP4_BASE[key].items()
                    if abs(frac(row[key]["stats"][stat]) - base) / base > F(1, 1000)}
        if named != observed:
            deployed = ", ".join(f"{s}={row[key]['stats'][s]}" for s in "ADLH")
            quirks.append(
                f"{key} name declares boosts {sorted(named) or '(none)'} but deployed stats "
                f"changed {sorted(observed) or '(none)'} vs the T1 base ({deployed}); "
                f"deployed panel capture is authoritative, the name is a mislabel")
    return quirks


def normalize_winner(row: dict) -> str:
    w = row["winner"].strip().lower()
    if "victory" in w or w == "attacker":
        return "att"
    if "defeat" in w or w == "defender":
        return "def"
    raise ValueError(f"unrecognized winner label {row['winner']!r} in {row['name']}")


def classify(row: dict, turns: dict, w_key: str) -> str:
    if turns["t_set"] is None:
        return "survivor_only"
    l_key = "def" if w_key == "att" else "att"
    n_w, n_l = row[w_key]["force"]["count"], row[l_key]["force"]["count"]
    surv_w = row[w_key]["out"]["surv"]
    cas_w = n_w - surv_w if surv_w is not None else None
    if n_w == 1 and n_l == 1:
        return "exact_1v1"
    if cas_w == 0 and n_l == 1:
        return "exact_clean_multi"
    if cas_w == 0 and n_w == 1 and n_l == 2:
        return "winner_exact_loser_piecewise"
    return "aggregate"


def scales_for(target: dict) -> dict:
    """Scale factors that re-express a per-target-HP-unit rate in stat units."""
    return {"H": target["_H"], "DplusH": target["_D_raw"] + target["_H"]}


def wipe_interval(n_units: int, T: int, has_vulc: bool, nextatk: bool, scales: dict) -> dict:
    lo = F(n_units) / weight(T, has_vulc, nextatk)
    w_prev = weight(T - 1, has_vulc, nextatk)
    hi = F(n_units) / w_prev if w_prev > 0 else None
    return interval(lo, hi, scales)


def survive_bound(T: int, has_vulc: bool, nextatk: bool, scales: dict) -> dict:
    return upper_bound(F(1) / weight(T, has_vulc, nextatk), scales)


def unit_branch_enumeration(n_units: int, T: int, has_vulc: bool, nextatk: bool) -> list:
    """Per-unit overkill-wasted branch, loser_count==2: enumerate the first-kill
    turn t1 and emit the feasible per-event rate interval for each."""
    assert n_units == 2
    out = []
    for t1 in range(1, T):
        w_t1 = weight(t1, has_vulc, nextatk)
        w_t1m1 = weight(t1 - 1, has_vulc, nextatk)
        w_T = weight(T, has_vulc, nextatk)
        w_Tm1 = weight(T - 1, has_vulc, nextatk)
        lo = max(F(1) / w_t1, F(1) / (w_T - w_t1))
        his = []
        if w_t1m1 > 0:
            his.append(F(1) / w_t1m1)
        if w_Tm1 - w_t1 > 0:
            his.append(F(1) / (w_Tm1 - w_t1))
        hi = min(his) if his else None
        if hi is None or lo < hi:
            out.append({"t1": t1, "lo": fs(lo), "lo_float": num(lo),
                        "hi": fs(hi) if hi is not None else None,
                        "hi_float": num(hi) if hi is not None else None})
    return out


def build_battle(idx: int, row: dict, fingerprints: dict) -> dict:
    turns = turn_analysis(row)
    w_key = normalize_winner(row)
    l_key = "def" if w_key == "att" else "att"
    kind = classify(row, turns, w_key)
    att, deff = side_view(row, "att"), side_view(row, "def")
    views = {"att": att, "def": deff}
    winner, loser = views[w_key], views[l_key]
    quirks = []
    if att["removed_quirk"] or deff["removed_quirk"]:
        for k, v in views.items():
            if v["removed_quirk"]:
                quirks.append(f"{k} casualty readings disagree: survivors-based vs "
                              f"loss+inj+light give removed in {v['removed_candidates']}")
    if row[l_key]["out"]["surv"] not in (0, None):
        quirks.append("loser side reports survivors > 0 - winner label cross-check failed")
    if turns["conflict_empty_t_set"]:
        quirks.append("recorded turn band and counter bands have EMPTY intersection under cadence A")
    if any(row[k]["heroes"].get("vulc_s2_T") and row[k]["heroes"].get("vulc_s3_T") is None
           for k in ("att", "def")):
        quirks.append("a Vulcanus side has S2 count but S3 count not captured (TNC)")
    quirks += exp4_label_check(row)

    fp = json.dumps({"a": row["att"], "d": row["def"], "t": [row["turns_lo"], row["turns_hi"]],
                     "w": row["winner"]}, sort_keys=True)
    dup_of = fingerprints.get(fp)
    if dup_of is None:
        fingerprints[fp] = row["name"]

    battle = {
        "name": row["name"],
        "ledger_line": LEDGER_FIRST_ROW_LINE + idx,
        "kind": kind,
        "duplicate_of": dup_of,
        "winner": w_key,
        "shape": f"{att['count']}v{deff['count']}",
        "matchup": f"T{att['tier']}{att['cls'][:3]} vs T{deff['tier']}{deff['cls'][:3]}",
        "turns": turns,
        "sides": {"att": {k: v for k, v in att.items() if not k.startswith("_")},
                  "def": {k: v for k, v in deff.items() if not k.startswith("_")}},
        "quirks": quirks,
    }

    if kind == "survivor_only":
        battle["constraints"] = {
            "type": "survivor_only",
            "note": "no turn clock (no Vulcanus side): usable as outcome/ordinal data and for "
                    "Stage-3 count-law simulation, not for per-event rate intervals",
            "removed": {k: views[k]["removed_candidates"] for k in ("att", "def")},
        }
        return battle

    t_set = turns["t_set"]
    w_scales, l_scales = scales_for(loser), scales_for(winner)
    n_l = loser["count"]

    if kind in ("exact_1v1", "exact_clean_multi", "winner_exact_loser_piecewise"):
        per_T = []
        for T in t_set:
            entry = {"T": T, "winner_rate": {}, "loser_rate": {}}
            for br in BRANCHES:
                na = br == "s2_nextatk"
                entry["winner_rate"][br] = wipe_interval(n_l, T, winner["has_vulc"], na, w_scales)
                if kind != "winner_exact_loser_piecewise":
                    entry["loser_rate"][br] = survive_bound(T, loser["has_vulc"], na, l_scales)
            per_T.append(entry)
        projected = {}
        for br in BRANCHES:
            na = br == "s2_nextatk"
            lo = F(n_l) / weight(t_set[-1], winner["has_vulc"], na)
            w_prev = weight(t_set[0] - 1, winner["has_vulc"], na)
            projected[br] = {
                "winner_rate": interval(lo, F(n_l) / w_prev if w_prev > 0 else None, w_scales),
                "loser_rate_ub": None if kind == "winner_exact_loser_piecewise" else
                upper_bound(F(1) / weight(t_set[0], loser["has_vulc"], na), l_scales),
            }
        battle["constraints"] = {
            "type": kind,
            "winner_side": w_key,
            "winner_count_factor": f"g({winner['count']})",
            "loser_count_factor": f"g({loser['count']})",
            "rate_semantics": "damage per own attack event, in units of ONE target unit's hidden HP; "
                              "multiply by the emitted scale columns to test HP~H or HP~(D_raw+H)",
            "pool_branch_required": n_l >= 2,
            "per_T": per_T,
            "projected": projected,
        }
        if kind == "winner_exact_loser_piecewise":
            battle["constraints"]["unit_overkill_branch"] = {
                str(T): {br: unit_branch_enumeration(n_l, T, winner["has_vulc"], br == "s2_nextatk")
                         for br in BRANCHES}
                for T in t_set
            }
            battle["constraints"]["loser_piecewise"] = {
                "form": "R_l*(g(2)*W_l(t1) + g(1)*(W_l(T)-W_l(t1))) < 1  [winner uninjured; "
                        "t1 = turn the loser's first unit died; end-of-turn removal keeps that "
                        "unit attacking through t1]",
                "W_l_table": {
                    br: {str(t): fs(weight(t, loser["has_vulc"], br == "s2_nextatk"))
                         for t in range(1, t_set[-1] + 1)}
                    for br in BRANCHES
                },
            }
        return battle

    # aggregate: raw observables + exact weights so Stage 3 can plug count laws
    battle["constraints"] = {
        "type": "aggregate",
        "winner_side": w_key,
        "note": "winner and/or loser live counts varied during battle (casualties on both "
                "sides or loser_count large): per-event rate is not constant, so only "
                "aggregate constraints are exact. Kill schedule requires a count-law model.",
        "removed": {k: views[k]["removed_candidates"] for k in ("att", "def")},
        "s2_kills": {k: views[k]["s2_K"] for k in ("att", "def")},
        "s2_kill_branches": {
            "bookkeeping": "kills_by_damage = removed (K only labels crossings on boosted events)",
            "execute": "kills_by_damage = removed - K on the side Vulcanus targets",
        },
        "per_T_weights": [
            {"T": T,
             "att": weights_at(T, att["has_vulc"]),
             "def": weights_at(T, deff["has_vulc"])}
            for T in t_set
        ],
        "wipe": {"side": l_key, "units": n_l},
    }
    return battle


def cadence_check(battles: list) -> dict:
    refuted, narrowed = [], []
    for b in battles:
        t = b["turns"]
        if t["t_set"] is None:
            continue
        if t["t_set"] and t["t_set_cadence_B"] == []:
            refuted.append(b["name"])
        if t["narrowed_vs_recorded"]:
            narrowed.append(b["name"])
    return {
        "cadence_A": "S2 fires on own attack events 6,12,18,... (count = floor(T/6))",
        "cadence_B": "S2 fires on own attack events 1,7,13,... (count = floor((T+5)/6))",
        "branch_B_refuted_by": refuted,
        "verdict": ("cadence B REFUTED: the rows above have an empty feasible turn set under B "
                    "while cadence A fits every clocked row" if refuted else "no discrimination"),
        "rows_narrowed_by_counters": narrowed,
        "note": "narrowed rows: the recorded band (built from the S3 clock alone) shrinks once "
                "the S2 counter band is intersected under cadence A - many battles pin to a "
                "single exact T.",
    }


def top5(battles: list) -> list:
    scored = []
    for b in battles:
        c = b["constraints"]
        if c["type"] not in ("exact_1v1", "exact_clean_multi", "winner_exact_loser_piecewise"):
            continue
        if b["duplicate_of"]:
            continue
        proj = c["projected"]["s2_plain"]["winner_rate"]
        lo, hi = F(proj["lo"]), F(proj["hi"]) if proj["hi"] else None
        if hi is None:
            continue
        rel_width = (hi - lo) / lo
        scored.append((rel_width, -b["turns"]["t_set"][-1], b["name"]))
    scored.sort()
    return [{"name": name, "winner_rate_rel_width_float": float(w)} for w, _, name in scored[:5]]


def coverage(battles: list) -> dict:
    kinds = {}
    for b in battles:
        kinds[b["constraints"]["type"]] = kinds.get(b["constraints"]["type"], 0) + 1
    return {
        "total_rows": len(battles),
        "clocked_rows": sum(1 for b in battles if b["turns"]["t_set"] is not None),
        "by_kind": dict(sorted(kinds.items())),
        "duplicates": [b["name"] for b in battles if b["duplicate_of"]],
        "conflict_rows": [b["name"] for b in battles if b["turns"]["conflict_empty_t_set"]],
    }


def build() -> dict:
    raw = open(DATASET, "rb").read()
    rows = json.loads(raw.decode("utf-8"))
    fingerprints: dict = {}
    battles = [build_battle(i, row, fingerprints) for i, row in enumerate(rows)]
    return {
        "meta": {
            "stage": 2,
            "generated_by": "wos_sim/formula_research/stage2_backsolve.py",
            "dataset": "wos_sim/formula_research/ledger_dataset.json",
            "dataset_sha256": sha256(raw).hexdigest(),
            "mechanics_constants": {
                "seoyoon_s1_attack_factor": {str(k): fs(v) for k, v in SY_FACTOR.items()},
                "vulcanus_s1_enemy_attack": fs(VULC_S1_ENEMY_ATTACK),
                "vulcanus_s3_enemy_inf_lan_defense": fs(VULC_S3_ENEMY_DEFENSE),
                "counter_damage_mult": fs(COUNTER_MULT),
                "s2_boost_on_6th_event": fs(S2_BOOST),
                "s2_nextatk_branch": fs(S2_NEXTATK),
            },
            "assumptions": ASSUMPTIONS,
            "branch_registry": BRANCH_REGISTRY,
            "guardrail_statement": "No constants were fitted anywhere in this file: every bound is "
                                   "an exact rational consequence of one battle's observables and "
                                   "the confirmed mechanics above.",
        },
        "cadence_check": cadence_check(battles),
        "coverage": coverage(battles),
        "top5_constraint_rich": top5(battles),
        "battles": battles,
    }


# ---------------------------------------------------------------- markdown --
def g(x) -> str:
    return f"{x:.8g}" if x is not None else "-"


def md_exact_rows(battles: list) -> list:
    lines = [
        "| # | Battle | Shape | Matchup | W | T set | Side (role) | eff A / D / L / H | ctr | g(N) | "
        "rate lo (plain) | rate hi (plain) | rate lo (nextatk) | rate hi (nextatk) | rate x H lo..hi (plain) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for b in battles:
        c = b["constraints"]
        if c["type"] not in ("exact_1v1", "exact_clean_multi", "winner_exact_loser_piecewise"):
            continue
        t = b["turns"]["t_set"]
        t_str = str(t[0]) if len(t) == 1 else f"{t[0]}-{t[-1]}"
        w_key = c["winner_side"]
        l_key = "def" if w_key == "att" else "att"
        for role, key in (("winner", w_key), ("loser", l_key)):
            s = b["sides"][key]
            stats = (f"{num(F(s['A_eff'])):.6g} / {num(F(s['D_eff'])):.6g} / "
                     f"{num(F(s['L'])):.6g} / {num(F(s['H'])):.6g}")
            if role == "winner":
                p, pn = c["projected"]["s2_plain"]["winner_rate"], c["projected"]["s2_nextatk"]["winner_rate"]
                cells = [g(p["lo_float"]), g(p["hi_float"]), g(pn["lo_float"]), g(pn["hi_float"]),
                         f"[{g(p['lo_x_H_float'])}, {g(p['hi_x_H_float'])})"]
            elif c["type"] == "winner_exact_loser_piecewise":
                cells = ["(piecewise", "see JSON)", "-", "-", "-"]
            else:
                p, pn = c["projected"]["s2_plain"]["loser_rate_ub"], c["projected"]["s2_nextatk"]["loser_rate_ub"]
                cells = ["0", f"< {g(p['ub_float'])}", "0", f"< {g(pn['ub_float'])}",
                         f"[0, {g(p['ub_x_H_float'])})"]
            gN = c["winner_count_factor"] if role == "winner" else c["loser_count_factor"]
            dup = " (dup)" if b["duplicate_of"] else ""
            lines.append(
                f"| {b['ledger_line']} | {b['name']}{dup} | {b['shape']} | {b['matchup']} | {b['winner']} | "
                f"{t_str} | {key} ({role}) | {stats} | {s['counter_mult']} | {gN} | " + " | ".join(cells) + " |")
    return lines


def md_aggregate_rows(battles: list) -> list:
    lines = [
        "| # | Battle | Shape | W | T set | removed att | removed def | S2 kills a/d | wipe side | notes |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for b in battles:
        c = b["constraints"]
        if c["type"] != "aggregate":
            continue
        t = b["turns"]["t_set"]
        t_str = str(t[0]) if len(t) == 1 else f"{t[0]}-{t[-1]}"
        k = c["s2_kills"]
        lines.append(
            f"| {b['ledger_line']} | {b['name']} | {b['shape']} | {b['winner']} | {t_str} | "
            f"{c['removed']['att']} | {c['removed']['def']} | {k['att']}/{k['def']} | "
            f"{c['wipe']['side']} ({c['wipe']['units']}u) | {'; '.join(b['quirks']) or '-'} |")
    return lines


def md_survivor_rows(battles: list) -> list:
    lines = [
        "| # | Battle | Shape | W | removed att | removed def | SY level |",
        "|---|---|---|---|---|---|---|",
    ]
    for b in battles:
        if b["constraints"]["type"] != "survivor_only":
            continue
        r = b["constraints"]["removed"]
        sy = b["sides"]["att"]["sy_level"] or b["sides"]["def"]["sy_level"] or "-"
        lines.append(f"| {b['ledger_line']} | {b['name']} | {b['shape']} | {b['winner']} | "
                     f"{r['att']} | {r['def']} | {sy} |")
    return lines


def write_md(doc: dict) -> str:
    b = doc["battles"]
    cov = doc["coverage"]
    cad = doc["cadence_check"]
    lines = [
        "# Stage 2 - Exact constraint back-solve (NanoMart corpus)",
        "",
        f"Generated by `stage2_backsolve.py` from `ledger_dataset.json` "
        f"(sha256 `{doc['meta']['dataset_sha256'][:16]}...`). Every number below is a "
        "re-runnable exact-rational consequence of one battle's observables plus the "
        "confirmed mechanics; nothing is fitted. Floats shown are displays of exact "
        "fractions stored in `stage2_constraints.json`.",
        "",
        "## Rate semantics",
        "",
        "`rate` = damage one side deals per own attack event, in units of ONE target "
        "unit's hidden HP (HP unit deliberately unknown). `rate x H` columns re-express "
        "the same bound if the HP unit is the target's Health stat; the JSON also carries "
        "`x (D_raw+H)` scalings. Winner intervals come from the loser's wipe at end of "
        "turn T; loser upper bounds from the winner finishing with zero units removed. "
        "S2's every-6th-event boost is unfolded via W(T); all constant factors "
        "(Seo-yoon, Vulcanus S1/S3, counter passives) remain folded inside the rate, "
        "with effective stats and the counter multiplier tabulated for Stage 3.",
        "",
        "## Assumptions",
        "",
    ]
    lines += [f"{i}. {a}" for i, a in enumerate(doc["meta"]["assumptions"], 1)]
    lines += ["", "## Ambiguity branches", ""]
    for key, br in doc["meta"]["branch_registry"].items():
        lines += [f"- **{key}** - {br['question']}", f"  - {br['resolution']}"]
    lines += [
        "",
        "## S2 cadence finding (derived)",
        "",
        f"- {cad['verdict']}",
        f"- Refuting rows: {', '.join(cad['branch_B_refuted_by'])}",
        f"- Rows whose feasible T narrows once the S2 counter is intersected "
        f"(cadence A): {', '.join(cad['rows_narrowed_by_counters']) or 'none'}",
        "",
        "## Exact per-event rate constraints (per-T detail in JSON; projected across T set)",
        "",
    ]
    lines += md_exact_rows(b)
    lines += ["", "## Aggregate rows (count-law rows: exact totals, rates need a count model)", ""]
    lines += md_aggregate_rows(b)
    lines += ["", "## Survivor-only rows (no turn clock)", ""]
    lines += md_survivor_rows(b)
    lines += ["", "## Data quirks", ""]
    quirky = [f"- `{x['name']}` (ledger line {x['ledger_line']}): {q}" for x in b for q in x["quirks"]]
    lines += quirky or ["- none"]
    lines += [
        "",
        "## Five most constraint-rich battles",
        "",
        "Ranked by relative width of the projected winner-rate interval (plain branch), "
        "duplicates excluded; single-T pins with long clocks rank first:",
        "",
    ]
    for i, t in enumerate(doc["top5_constraint_rich"], 1):
        lines.append(f"{i}. `{t['name']}` - rel. width {t['winner_rate_rel_width_float']:.6g}")
    lines += [
        "",
        "## Coverage",
        "",
        f"- Rows: {cov['total_rows']} total, {cov['clocked_rows']} turn-clocked.",
        f"- By kind: {json.dumps(cov['by_kind'])}",
        f"- Duplicates (no independent weight): {', '.join(cov['duplicates']) or 'none'}",
        f"- Empty-T-set conflicts: {', '.join(cov['conflict_rows']) or 'none'}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    doc = build()
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    with open(OUT_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write(write_md(doc))
    cov, cad = doc["coverage"], doc["cadence_check"]
    print(f"battles: {cov['total_rows']}  clocked: {cov['clocked_rows']}  kinds: {cov['by_kind']}")
    print(f"cadence-B refuted by {len(cad['branch_B_refuted_by'])} rows; "
          f"{len(cad['rows_narrowed_by_counters'])} rows narrowed by counter intersection")
    print(f"conflicts: {cov['conflict_rows'] or 'none'}")
    print("top5:", [t["name"] for t in doc["top5_constraint_rich"]])
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
