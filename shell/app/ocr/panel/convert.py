STATS = ("Attack", "Defense", "Lethality", "Health")

class CalibrationError(ValueError):
    pass

class MissingSpecialsError(ValueError):
    """The specials panel was never observed (QA D-005).

    An unread specials panel is NOT the same as an account with no specials:
    folding an empty set silently turns battle->scout conversion into the
    identity (measured worst-case silent error: 367.4 pp). Callers must state
    explicitly whether the panel was observed.
    """

def _stat_of(label):
    for st in STATS:
        if st in label:
            return st
    return None

def fold_sets(specials_own, specials_enemy, *, observed):
    """Fold the specials panel into (S_scout, S_battle, P_enemy).

    ``observed`` (required, keyword-only) states whether a specials panel was
    actually captured and read. ``observed=False`` with no own specials raises
    MissingSpecialsError; ``observed=True`` with an empty enemy list is legal
    (real case: account B).
    """
    if not observed and not specials_own:
        raise MissingSpecialsError(
            "specials panel not observed and no own specials read: refusing to "
            "fold an empty set (that would make the conversion an identity)")
    S_scout = {st: 0.0 for st in STATS}
    territory = {st: 0.0 for st in STATS}
    for sp in specials_own:
        label, v, st = sp["label"], sp["value"] / 100.0, _stat_of(sp["label"])
        if st is None or v < 0:
            continue                      # own outgoing penalties don't touch own rows
        if "When Defending Own City" in label:
            continue                      # displayed but never folded (measured, both accounts)
        if "Territory Defender" in label:
            territory[st] += v
        else:                             # pet self-buffs, defender-widget rows, item bonuses
            S_scout[st] += v
    S_battle = {st: S_scout[st] + territory[st] for st in STATS}
    P_enemy = {st: 0.0 for st in STATS}
    for sp in specials_enemy:
        st = _stat_of(sp["label"])
        if st is not None and sp["value"] < 0 and "Penalty" in sp["label"]:
            P_enemy[st] += abs(sp["value"]) / 100.0
    return S_scout, S_battle, P_enemy

def battle_to_scoutnet(battle_rows, S_scout, S_battle, P_enemy):
    out = {}
    for cls, stats in battle_rows.items():
        out[cls] = {}
        for st, b in stats.items():
            r = (1 + S_scout[st]) * (1 + P_enemy[st]) / (1 + S_battle[st])
            out[cls][st] = ((1 + b / 100.0) * r - 1) * 100.0
    return out

def calibrate_U(bo_troops, bo_class, scout_rows, S_scout):
    U = {}
    for st in STATS:
        us = []
        for cls, stats in scout_rows.items():
            std = ((1 + stats[st] / 100.0) / (1 + S_scout[st]) - 1) * 100.0
            us.append(std - bo_troops[st] - bo_class[cls][st])
        if max(us) - min(us) > 1.0:
            raise CalibrationError(f"U not uniform for {st}: spread {max(us)-min(us):.2f}")
        U[st] = sum(us) / len(us)
    return U

def citystats_to_scoutnet(bo_troops, bo_class, U, S_scout):
    out = {}
    for cls, stats in bo_class.items():
        out[cls] = {}
        for st in STATS:
            std = bo_troops[st] + stats[st] + U[st]
            out[cls][st] = ((1 + std / 100.0) * (1 + S_scout[st]) - 1) * 100.0
    return out
