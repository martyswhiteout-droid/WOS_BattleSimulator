from .lexicon import CLASSES, PENALTY_LABELS

STATS = ("Attack", "Defense", "Lethality", "Health")

class CalibrationError(ValueError):
    pass

class MissingSpecialsError(ValueError):
    """The specials panel was not fully read (QA D-005, tightened by D-022).

    An unread — or partially read — specials panel is NOT the same as an
    account with no specials: folding whatever happened to be readable turns
    battle->scout conversion into (or towards) the identity, measured worst
    case 367.4 pp of silent error. Only the "read" capture state may fold.
    """

# Capture states for ``fold_sets(observed=...)`` (QA D-022). See
# service._specials for how each is decided from the rows.
OBSERVED_STATES = ("none", "partial", "read")

def _stat_of(label):
    for st in STATS:
        if st in label:
            return st
    return None

def fold_sets(specials_own, specials_enemy, *, observed, warnings=None):
    """Fold the specials panel into (S_scout, S_battle, P_enemy).

    ``observed`` (required, keyword-only) is the tri-state capture verdict from
    the service: "none" | "partial" | "read" (QA D-022). Only "read" may fold —
    "partial" (some special rows withheld) is just as untrustworthy as "none".
    An EMPTY ``specials_own`` under "read" is legal and folds to the identity
    correctly: that is a genuinely specials-free side (e.g. account B's enemy
    column), not a missing capture.

    ``warnings`` (optional out-parameter) collects rows that were excluded as
    suspect — currently own-side penalty rows with a positive value, i.e. OCR
    that lost the minus sign (QA D-013). The 3-tuple return is unchanged.
    """
    if observed not in OBSERVED_STATES:
        raise ValueError(
            f"observed must be one of {OBSERVED_STATES}, got {observed!r}")
    if observed != "read":
        raise MissingSpecialsError(
            f"specials panel state is {observed!r}: refusing to fold a set that "
            "was never captured or was only partly read (that would silently "
            "pull the conversion towards the identity)")
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
