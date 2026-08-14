from .tokens import tokens_from_json
from .rows import assemble_rows, LOW_CONF
from .stitch import stitch
from .detect import detect_panel_type
from .lexicon import CLASSES, SPECIALS_PANEL_HEADERS, STATS

# Every class-stat the app expects on a full panel, in a fixed (deterministic)
# order â€” used to report fields that were never seen at all (QA D-006).
EXPECTED_KEYS = tuple(f"{c}|{s}" for c in CLASSES for s in STATS)

# Plausibility bands (QA D-008; QA_PLAN Â§3 P7 + formula doc Â§8). A number
# outside its band is an OCR artefact, not a stat: it goes to
# unreadable_fields, never into stats/specials.
CLASS_VALUE_MIN, CLASS_VALUE_MAX = 0.0, 6000.0
SPECIAL_ABS_MAX = 25.0


def _in_range(value, lo, hi):
    return value is not None and lo <= value <= hi


# Hint/detection pairs that cannot describe the same screenshot (QA D-021).
# Everything else that merely differs is read under the hint with a warning â€”
# notably (battle hint, scout detection), which is a battle report with only
# one column readable.
INCOMPATIBLE_HINTS = frozenset({
    ("citystats", "battle"), ("citystats", "scout"),
    ("battle", "citystats"), ("scout", "citystats"),
    ("scout", "battle"),
})


def _hint_warning(hint, detected):
    if detected == "unknown":
        return f"panel hint {hint} used: panel type could not be detected from these tokens"
    if (hint, detected) == ("battle", "scout"):
        return "panel hint battle used: only one column was readable in this screenshot"
    return f"panel hint {hint} used: detected {detected}"


def _is_bad(row):
    """The single honesty predicate: a value is emitted only when it is present,
    confident, and unconflicted.

    QA D-002: the flag test is a SUBSTRING match so `col_conflict` (column
    attribution contradicted by colour) counts, not just the stitch `conflict`.
    """
    return (row.value is None
            or row.conf < LOW_CONF
            or any("conflict" in f for f in row.flags))


def _dedupe(items):
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _bucket(rows, side):
    stats, conf, unreadable = {}, {}, []
    for r in rows:
        if r.canonical.startswith(("special:", "meta:", "header:")) or "|" not in r.canonical:
            continue
        key = r.canonical
        if side is not None and r.side != side:
            continue
        if _is_bad(r) or not _in_range(r.value, CLASS_VALUE_MIN, CLASS_VALUE_MAX):
            unreadable.append(f"stats.{key}")
        else:
            stats[key] = r.value
            conf[key] = round(r.conf, 4)
    return stats, conf, unreadable


def attach_side_specials(out):
    """(Re)build the ``specials_you`` / ``specials_enemy`` convenience lists.

    Same left=report-viewer orientation as stats_you/stats_enemy (QA D-011).
    Called by extract_panel and AGAIN by the ladder after a gap fill, so the
    convenience lists can never go stale relative to ``specials``.
    """
    if out.get("panel_type") != "battle" or out.get("requested_side") not in ("you", "enemy"):
        return out
    you_side = "left" if out["requested_side"] == "you" else "right"
    enemy_side = "right" if out["requested_side"] == "you" else "left"
    specials = out.get("specials") or []
    out["specials_you"] = [s for s in specials if s.get("side") == you_side]
    out["specials_enemy"] = [s for s in specials if s.get("side") == enemy_side]
    return out


def _specials_are_two_column(rows):
    """True when at least one special label appears in BOTH columns.

    Side-awareness is derived from the ROWS, never from the panel type
    (QA D-034): a standalone specials screenshot has no class rows, so it
    detects as "unknown" and may well be uploaded under a scout hint — gating
    on the panel type would collapse its two columns back into flat entries a
    caller would sum. A label with no counterpart in the other column cannot be
    summed with anything, so it keeps the flat single-column contract.
    """
    left, right = set(), set()
    for r in rows:
        if not r.canonical.startswith("special:"):
            continue
        if r.side == "left":
            left.add(r.canonical)
        elif r.side == "right":
            right.add(r.canonical)
    return not left.isdisjoint(right)


def _specials(rows):
    """Specials pass the same honesty predicate as class rows (QA D-004):
    a low-confidence or value-less special is reported unreadable, never folded.

    Specials are SIDE-AWARE on two-column layouts (QA D-029, D-034): the same
    label can appear in both columns with different values, so each entry
    carries its ``side`` and unreadable entries are keyed
    ``specials_left.<label>`` / ``specials_right.<label>``. Single-column
    layouts keep ``side: None`` and the flat ``specials.<label>`` key. Which
    one applies is decided by ``_specials_are_two_column(rows)`` — the rows
    themselves — so it holds for a standalone specials screenshot whose panel
    type is "unknown". Without this, two columns of one label collapse into two
    flat entries that fold_sets would sum.

    Returns ``(specials, unreadable, observed)`` where ``observed`` is the
    tri-state capture verdict (QA D-022) consumed by ``convert.fold_sets``:

    "none"    no special row and no specials-panel header â€” the panel was never
              captured, so folding would silently be the identity.
    "partial" special rows were seen but at least one was withheld â€” the fold
              would be built from an incomplete set.
    "read"    every special row seen was readable, OR the specials-panel header
              was seen with zero rows (the legal specials-free account).
    """
    two_column = _specials_are_two_column(rows)
    good, unreadable, seen = [], [], 0
    header_seen = False
    for r in rows:
        if r.canonical in SPECIALS_PANEL_HEADERS:
            header_seen = True
            continue
        if not r.canonical.startswith("special:"):
            continue
        seen += 1
        label = r.canonical.split(":", 1)[1]
        side = r.side if (two_column and r.side in ("left", "right")) else None
        key = f"specials_{side}.{label}" if side else f"specials.{label}"
        if _is_bad(r) or not _in_range(r.value, -SPECIAL_ABS_MAX, SPECIAL_ABS_MAX):
            unreadable.append(key)
        else:
            good.append({"label": label, "value": r.value, "side": side})
    if seen == 0:
        observed = "read" if header_seen else "none"
    else:
        observed = "partial" if unreadable else "read"
    return good, unreadable, observed


def extract_panel(token_shots, side_hint=None, panel_hint=None):
    """Tokens -> result JSON.

    ``warnings`` and ``unreadable_fields`` are DEVELOPER-FACING API fields
    (QA D-026): stable identifiers and diagnostics â€” field keys, panel types,
    token coordinates â€” for the caller to act on. The UI copy layer is what
    turns them into user-facing sentences; do not write end-user prose here.

    ``side_hint`` ("you" | "enemy" | None) is echoed back as ``requested_side``
    and, on battle panels, drives the ``stats_you`` / ``stats_enemy`` aliases
    (QA D-011). The LEFT column of a battle report always belongs to the report
    viewer, i.e. to whoever the uploader says the report belongs to:
    side="you"   -> stats_you = stats_left,  stats_enemy = stats_right
    side="enemy" -> stats_you = stats_right, stats_enemy = stats_left
    (`_conf` twins alias the same way). Single-sided panels get no aliases.

    Malformed input raises ValueError, never a KeyError/TypeError (QA D-019).

    ``panel_hint`` is a CHECK, never a blind override (QA D-012, refined by
    D-021). Pairs in INCOMPATIBLE_HINTS end as ``status="failed"`` with an
    explanatory warning and no stats. Any other disagreement is read under the
    hint WITH a warning â€” including (hint=battle, detected=scout), which is a
    battle report whose second column is unreadable: the battle branch runs and
    the absent column is enumerated in unreadable_fields.

    Battle results carry ``stats_left``/``stats_right`` and NO ``stats`` key
    (QA D-018); single-sided results carry ``stats``.
    """
    if not isinstance(token_shots, (list, tuple)):
        raise ValueError(f"token_shots must be a list of token lists, got "
                         f"{type(token_shots).__name__}")
    for shot in token_shots:
        if not isinstance(shot, (list, tuple)):
            raise ValueError(f"each token shot must be a list, got {type(shot).__name__}")
    shots = [assemble_rows(tokens_from_json(s), two_column=True) for s in token_shots]
    rows, warnings = stitch([r for r, _ in shots], [w for _, w in shots])
    detected = detect_panel_type(rows)
    ptype = detected
    warnings = list(warnings)
    contradiction = None
    if panel_hint:
        if (panel_hint, detected) in INCOMPATIBLE_HINTS:
            contradiction = f"panel hint {panel_hint} contradicts detected {detected}"
        else:
            if detected != panel_hint:
                warnings.append(_hint_warning(panel_hint, detected))
            ptype = panel_hint
    specials, special_unreadable, specials_observed = _specials(rows)
    if contradiction:
        return {"panel_type": detected, "requested_side": side_hint,
                "specials": specials, "specials_observed": specials_observed,
                "warnings": warnings + [contradiction],
                "stats": {}, "field_conf": {}, "unreadable_fields": [],
                "status": "failed"}
    out = {"panel_type": ptype, "requested_side": side_hint, "specials": specials,
           "specials_observed": specials_observed, "warnings": warnings}
    unreadable = []
    if ptype == "battle":
        for side, key in (("left", "stats_left"), ("right", "stats_right")):
            st, cf, un = _bucket(rows, side)
            out[key], out[key + "_conf"] = st, cf
            unreadable.extend(f"{key}.{u.split('.', 1)[1]}" for u in un)
            unreadable.extend(f"{key}.{k}" for k in EXPECTED_KEYS if k not in st)
        present = len(out["stats_left"]) + len(out["stats_right"])
        total = 24
    else:
        st, cf, un = _bucket(rows, None)
        out["stats"], out["field_conf"] = st, cf
        unreadable.extend(un)
        unreadable.extend(f"stats.{k}" for k in EXPECTED_KEYS if k not in st)
        present = len([k for k in st if k.split("|")[0] in CLASSES])
        total = 12
    out["unreadable_fields"] = _dedupe(unreadable + special_unreadable)
    out["status"] = "ok" if present >= total else ("partial" if present > 0 else "failed")
    if ptype == "battle" and side_hint in ("you", "enemy"):
        you_key = "stats_left" if side_hint == "you" else "stats_right"
        enemy_key = "stats_right" if side_hint == "you" else "stats_left"
        out["stats_you"], out["stats_you_conf"] = out[you_key], out[you_key + "_conf"]
        out["stats_enemy"], out["stats_enemy_conf"] = out[enemy_key], out[enemy_key + "_conf"]
    attach_side_specials(out)
    return out
