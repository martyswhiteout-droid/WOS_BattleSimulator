from .tokens import tokens_from_json
from .rows import assemble_rows, LOW_CONF
from .stitch import stitch
from .detect import detect_panel_type
from .lexicon import CLASSES, SPECIALS_PANEL_HEADERS, STATS

# Every class-stat the app expects on a full panel, in a fixed (deterministic)
# order — used to report fields that were never seen at all (QA D-006).
EXPECTED_KEYS = tuple(f"{c}|{s}" for c in CLASSES for s in STATS)

# Plausibility bands (QA D-008; QA_PLAN §3 P7 + formula doc §8). A number
# outside its band is an OCR artefact, not a stat: it goes to
# unreadable_fields, never into stats/specials.
CLASS_VALUE_MIN, CLASS_VALUE_MAX = 0.0, 6000.0
SPECIAL_ABS_MAX = 25.0


def _in_range(value, lo, hi):
    return value is not None and lo <= value <= hi


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


def _specials(rows):
    """Specials pass the same honesty predicate as class rows (QA D-004):
    a low-confidence or value-less special is reported unreadable, never folded.

    Returns ``(specials, unreadable, observed)`` where ``observed`` is the
    tri-state capture verdict (QA D-022) consumed by ``convert.fold_sets``:

    "none"    no special row and no specials-panel header — the panel was never
              captured, so folding would silently be the identity.
    "partial" special rows were seen but at least one was withheld — the fold
              would be built from an incomplete set.
    "read"    every special row seen was readable, OR the specials-panel header
              was seen with zero rows (the legal specials-free account).
    """
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
        if _is_bad(r) or not _in_range(r.value, -SPECIAL_ABS_MAX, SPECIAL_ABS_MAX):
            unreadable.append(f"specials.{label}")
        else:
            good.append({"label": label, "value": r.value})
    if seen == 0:
        observed = "read" if header_seen else "none"
    else:
        observed = "partial" if unreadable else "read"
    return good, unreadable, observed


def extract_panel(token_shots, side_hint=None, panel_hint=None):
    """Tokens -> result JSON.

    ``side_hint`` ("you" | "enemy" | None) is echoed back as ``requested_side``
    and, on battle panels, drives the ``stats_you`` / ``stats_enemy`` aliases
    (QA D-011). The LEFT column of a battle report always belongs to the report
    viewer, i.e. to whoever the uploader says the report belongs to:
    side="you"   -> stats_you = stats_left,  stats_enemy = stats_right
    side="enemy" -> stats_you = stats_right, stats_enemy = stats_left
    (`_conf` twins alias the same way). Single-sided panels get no aliases.

    Malformed input raises ValueError, never a KeyError/TypeError (QA D-019).

    ``panel_hint`` is a CHECK, never an override (QA D-012): if it contradicts
    the detected panel type the result is ``status="failed"`` with an
    explanatory warning and no stats. A hint is only followed when detection
    itself is "unknown" (tokens too sparse to decide).

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
    specials, special_unreadable, specials_observed = _specials(rows)
    ptype = detected
    if panel_hint:
        if detected not in ("unknown", panel_hint):
            return {"panel_type": detected, "requested_side": side_hint,
                    "specials": specials, "specials_observed": specials_observed,
                    "warnings": list(warnings) + [
                        f"panel hint {panel_hint} contradicts detected {detected}"],
                    "stats": {}, "field_conf": {}, "unreadable_fields": [],
                    "status": "failed"}
        ptype = panel_hint
    out = {"panel_type": ptype, "requested_side": side_hint, "specials": specials,
           "specials_observed": specials_observed, "warnings": list(warnings)}
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
    return out
