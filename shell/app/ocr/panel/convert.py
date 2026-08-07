from .lexicon import CLASSES, PENALTY_LABELS

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

def fold_sets(specials_own, specials_enemy, *, observed, warnings=None):
    """Fold the specials panel into (S_scout, S_battle, P_enemy).

    ``observed`` (required, keyword-only) states whether a specials panel was
    actually captured and read. ``observed=False`` with no own specials raises
    MissingSpecialsError; ``observed=True`` with an empty enemy list is legal
    (real case: account B).

    ``warnings`` (optional out-parameter) collects rows that were excluded as
    suspect — currently own-side penalty rows with a positive value, i.e. OCR
    that lost the minus sign (QA D-013). The 3-tuple return is unchanged.
    """
    if not observed and not specials_own:
        raise MissingSpecialsError(
            "specials panel not observed and no own specials read: refusing to "
            "fold an empty set (that would make the conversion an identity)")
    S_scout = {st: 0.0 for st in STATS}
    territory = {st: 0.0 for st in STATS}
    for sp in specials_own:
        label, v, st = sp["label"], sp["value"] / 100.0, _stat_of(sp["label"])
        if st is None:
            continue
        if label in PENALTY_LABELS:
            # Own outgoing penalties never touch own rows. A POSITIVE one is an
            # OCR sign-loss suspect: excluded and reported, never a self-buff.
            if sp["value"] > 0 and warnings is not None:
                warnings.append(
                    f"own penalty row has a positive value (OCR sign loss?): {label}")
            continue
        if v < 0:
            continue
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
        if st is not None and sp["label"] in PENALTY_LABELS:
            P_enemy[st] += abs(sp["value"]) / 100.0
    return S_scout, S_battle, P_enemy

def _set_value(name, mapping, st):
    """One entry of an S/P set, as a float, or a typed error (QA D-019)."""
    try:
        return float(mapping[st])
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise CalibrationError(f"malformed {name} for {st}: {exc!r}") from exc

def battle_to_scoutnet(battle_rows, S_scout, S_battle, P_enemy):
    out = {}
    for cls, stats in battle_rows.items():
        out[cls] = {}
        for st, b in stats.items():
            s_battle = _set_value("S_battle", S_battle, st)
            if s_battle <= -1.0:
                raise CalibrationError(f"S_battle[{st}] <= -1 makes the conversion undefined")
            r = ((1 + _set_value("S_scout", S_scout, st))
                 * (1 + _set_value("P_enemy", P_enemy, st)) / (1 + s_battle))
            out[cls][st] = ((1 + b / 100.0) * r - 1) * 100.0
    return out

def calibrate_U(bo_troops, bo_class, scout_rows, S_scout):
    """Solve the per-class hero block U.

    Requires all three troop classes on BOTH the scout panel and the BO class
    block (QA D-015): with fewer, the uniformity guard below is vacuous and a
    single-class "calibration" would pass. Every malformed input is reported as
    CalibrationError, never a bare KeyError/TypeError/ZeroDivisionError/max([])
    ValueError (QA D-019).
    """
    if not isinstance(scout_rows, dict) or not isinstance(bo_class, dict):
        raise CalibrationError("scout_rows and bo_class must be mappings")
    absent = [c for c in CLASSES if c not in scout_rows or c not in bo_class]
    if absent:
        raise CalibrationError(
            f"calibration needs all three classes; missing {sorted(absent)}")
    U = {}
    for st in STATS:
        s = _set_value("S_scout", S_scout, st)
        if s <= -1.0:
            raise CalibrationError(f"S_scout[{st}] <= -1 makes the standardisation undefined")
        us = []
        for cls in CLASSES:
            try:
                std = ((1 + scout_rows[cls][st] / 100.0) / (1 + s) - 1) * 100.0
                us.append(std - bo_troops[st] - bo_class[cls][st])
            except (KeyError, TypeError, IndexError) as exc:
                raise CalibrationError(
                    f"malformed calibration input for {cls}|{st}: {exc!r}") from exc
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
