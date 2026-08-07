from .tokens import tokens_from_json
from .rows import assemble_rows, LOW_CONF
from .stitch import stitch
from .detect import detect_panel_type
from .lexicon import CLASSES, STATS

# Every class-stat the app expects on a full panel, in a fixed (deterministic)
# order — used to report fields that were never seen at all (QA D-006).
EXPECTED_KEYS = tuple(f"{c}|{s}" for c in CLASSES for s in STATS)


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
        if _is_bad(r):
            unreadable.append(f"stats.{key}")
        else:
            stats[key] = r.value
            conf[key] = round(r.conf, 4)
    return stats, conf, unreadable


def _specials(rows):
    """Specials pass the same honesty predicate as class rows (QA D-004):
    a low-confidence or value-less special is reported unreadable, never folded.
    """
    good, unreadable, observed = [], [], False
    for r in rows:
        if not r.canonical.startswith("special:"):
            continue
        observed = True  # QA D-005: seen at all, readable or not
        label = r.canonical.split(":", 1)[1]
        if _is_bad(r):
            unreadable.append(f"specials.{label}")
        else:
            good.append({"label": label, "value": r.value})
    return good, unreadable, observed


def extract_panel(token_shots, side_hint=None, panel_hint=None):
    shots = [assemble_rows(tokens_from_json(s), two_column=True) for s in token_shots]
    rows, warnings = stitch([r for r, _ in shots], [w for _, w in shots])
    ptype = panel_hint or detect_panel_type(rows)
    specials, special_unreadable, specials_observed = _specials(rows)
    out = {"panel_type": ptype, "specials": specials,
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
    out.setdefault("stats", {})
    return out
