"""Stage 4 shared library: REAL-stat loader + experiment parsers.

Everything downstream (within-tier confirmation, the tier-law derivation, and the
blind validator) imports this.  NO fitting here -- this file only turns the raw
report JSONs + the real base-stat table into effective (A,D,L,H) per side.

Guardrail compliance:
  * Effective stat = REAL base (docs/TroopStats/WOS_Troop_Stats_FC1-FC10_T1-T10.json)
    x (1 + panel/100).  The base is read from the table, never guessed.
  * Winner / loser are taken from outcome.winner (never assumed = attacker).
  * Observed `turns` is carried as a read-out only; it is never fed into an
    effective-stat computation.
"""
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
STAT_TABLE = os.path.join(REPO, "docs", "TroopStats", "WOS_Troop_Stats_FC1-FC10_T1-T10.json")
EXP = os.path.join(REPO, "wos_sim", "data", "experiments")

# directional counter triangle: Inf>Lan>MM>Inf  (+10% attack damage to the prey)
_PREY = {"Infantry": "Lancer", "Lancer": "Marksman", "Marksman": "Infantry"}


# --------------------------------------------------------------------------- #
#  real base-stat table
# --------------------------------------------------------------------------- #
def load_stat_table(path=STAT_TABLE):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


_TABLE = None


def base_stats(cls, tier, fc=1):
    """(A, D, L, H) real base for class/tier/fire-crystal-level from the table."""
    global _TABLE
    if _TABLE is None:
        _TABLE = load_stat_table()
    fcrec = _TABLE["troop_classes"][cls]["tiers"][f"T{tier}"]["fc_levels"][f"FC{fc}"]
    return (fcrec["attack"], fcrec["defense"], fcrec["lethality"], fcrec["health"])


def counter_mult(att_cls, def_cls):
    return 1.10 if _PREY.get(att_cls) == def_cls else 1.0


# --------------------------------------------------------------------------- #
#  parse a controlled 1v1 experiment JSON (Gatot / Mueller / FarSeer / Gordon)
# --------------------------------------------------------------------------- #
def _tier_of(side):
    tc = side.get("tier_code")
    if tc:
        return int(str(tc).lstrip("Tt"))
    m = re.search(r"([\d.]+)", side.get("tier_display", "Lv 1"))
    return int(round(float(m.group(1))))


def _fc_of(side):
    fc = side.get("fire_crystal_level")
    if fc:
        m = re.search(r"(\d+)", str(fc))
        if m:
            return int(m.group(1))
    return 1


def _eff(side):
    """effective (A,D,L,H) for a side, from REAL base x (1+panel)."""
    cls = side["deployed_class"]
    tier = _tier_of(side)
    fc = _fc_of(side)
    A0, D0, L0, H0 = base_stats(cls, tier, fc)
    p = (side.get("stats_pct") or {}).get(cls, {})

    def m(key):
        return 1.0 + float(p.get(key, 0.0)) / 100.0

    lcap = "Lethality" in p and p.get("Lethality") is not None
    hcap = "Health" in p and p.get("Health") is not None
    return dict(cls=cls, tier=tier, fc=fc,
                A=A0 * m("Attack"), D=D0 * m("Defense"),
                L=L0 * m("Lethality"), H=H0 * m("Health"),
                base=(A0, D0, L0, H0), lcap=lcap, hcap=hcap)


def parse_1v1(path):
    d = json.load(open(path, encoding="utf-8"))
    if not str(d.get("_type", "")).startswith("experiment_1v1"):
        return None
    att, dfn = d["attacker"], d["defender"]
    # single-troop only (the exact-turn instrument)
    if (att.get("troops") or 1) != 1 or (dfn.get("troops") or 1) != 1:
        return None
    win = d["outcome"]["winner"]              # "attacker" | "defender"
    W, Lo = (att, dfn) if win == "attacker" else (dfn, att)
    ew, el = _eff(W), _eff(Lo)
    ti = d.get("turn_inference") or {}
    turns = ti.get("turns")
    rng = ti.get("turns_range") or ([turns, turns] if turns else None)
    return dict(
        name=os.path.basename(path),
        win_side=win,
        w=ew, l=el,
        ctr=counter_mult(ew["cls"], el["cls"]),
        turns=turns,
        t_lo=(rng[0] if rng else None),
        t_hi=(rng[1] if rng else None),
        matchup=f"{ew['cls'][:3]}T{ew['tier']}>{el['cls'][:3]}T{el['tier']}",
        same_class=(ew["cls"] == el["cls"]),
        same_tier=(ew["tier"] == el["tier"]),
    )


def load_dir(subdir, pattern="*.json", need_exact=True):
    """need_exact=True keeps only rows with an exact integer turn count;
    need_exact=False also keeps band-only rows (turns is None, turns_range set)."""
    rows = []
    for f in sorted(glob.glob(os.path.join(EXP, subdir, pattern))):
        try:
            r = parse_1v1(f)
        except Exception as e:                # noqa: BLE001 - report, don't hide
            print(f"  !! parse error {os.path.basename(f)}: {e}")
            continue
        if not r:
            continue
        if need_exact and not r["turns"]:
            continue
        if r["turns"] or (r["t_lo"] is not None and r["t_hi"] is not None):
            rows.append(r)
    return rows


def load_all_exact():
    """All exact-turn 1v1 rows, tagged by source."""
    out = []
    for sub, tag in [("Lab Rat", "LabRat"), ("MuellerAlpaca", "Mueller"),
                     ("FarSeerGatot_v3", "FarSeer")]:
        for r in load_dir(sub):
            r["src"] = tag
            out.append(r)
    return out


def parse_beast(path):
    """1-vs-N Gatot beast rows -> per-kill 1v1 turns (winner strong, N identical
    losers killed sequentially: total_turns = N * turns_1v1).  REAL stats."""
    d = json.load(open(path, encoding="utf-8"))
    if d.get("_type") != "beast_hunt_experiment":
        return None
    att, dfn = d["attacker"], d["defender"]
    n_loser = dfn.get("troops") or 0
    kills = att.get("kills") or 0
    turns = (d.get("turn_inference") or {}).get("turns")
    if not (n_loser and turns and kills == n_loser):     # only fully-resolved rows
        return None
    ew, el = _eff(att), _eff(dfn)
    return dict(name=os.path.basename(path), w=ew, l=el,
                ctr=counter_mult(ew["cls"], el["cls"]),
                n_loser=n_loser, turns=turns, per_kill=turns / n_loser,
                matchup=f"{ew['cls'][:3]}T{ew['tier']}>{el['cls'][:3]}T{el['tier']}(x{n_loser})")


def load_validation():
    """Every 1v1 row with an observed turn constraint (exact OR band), incl. the
    held-out Gordon battery (band-only). For blind prediction / gate checks."""
    out = []
    for sub, tag in [("Lab Rat", "LabRat"), ("MuellerAlpaca", "Mueller"),
                     ("FarSeerGatot_v3", "FarSeer")]:
        for r in load_dir(sub, need_exact=False):
            r["src"] = tag
            # tag the Gordon held-out rows distinctly (they live in Lab Rat/)
            if "Gordon" in r["name"]:
                r["src"] = "Gordon"
            out.append(r)
    return out


def load_beasts():
    out = []
    for f in sorted(glob.glob(os.path.join(EXP, "Lab Rat", "*Beast*.json"))):
        r = parse_beast(f)
        if r:
            out.append(r)
    return out


if __name__ == "__main__":
    # Step 0 deliverable: PRINT the real base table so the additive structure is
    # on the record (this is what the multiplicative-base claim is retracted against).
    print("REAL base stats  (A, D, L, H)  at FC1, from the troop-stats table:\n")
    for cls in ("Infantry", "Lancer", "Marksman"):
        print(f"{cls}:")
        print("  tier :  A   D   L   H     |  D-A   H-L   (tier-invariant diffs?)")
        for t in range(1, 11):
            A, D, L, H = base_stats(cls, t, 1)
            print(f"  T{t:<2} : {A:3} {D:3} {L:3} {H:3}     |  {D-A:+3}   {H-L:+3}")
        print()
    print("Infantry FC dimension (T1, FC1..FC10) -- does FC move anything but Defense?")
    print("  FC :  A   D   L   H")
    for fc in range(1, 11):
        A, D, L, H = base_stats("Infantry", 1, fc)
        print(f"  FC{fc:<2}: {A:3} {D:3} {L:3} {H:3}")
