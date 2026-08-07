from .tokens import tokens_from_json
from .rows import assemble_rows, LOW_CONF
from .stitch import stitch
from .detect import detect_panel_type
from .lexicon import CLASSES, STATS

def _bucket(rows, side):
    stats, conf, unreadable = {}, {}, []
    for r in rows:
        if r.canonical.startswith(("special:", "meta:", "header:")) or "|" not in r.canonical:
            continue
        if r.canonical.startswith("Troops|"):
            key = r.canonical
        else:
            key = r.canonical
        if side is not None and r.side != side:
            continue
        bad = r.value is None or "conflict" in r.flags or r.conf < LOW_CONF
        if bad:
            unreadable.append(f"stats.{key}")
        else:
            stats[key] = r.value
            conf[key] = round(r.conf, 4)
    return stats, conf, unreadable

def extract_panel(token_shots, side_hint=None, panel_hint=None):
    shots = [assemble_rows(tokens_from_json(s), two_column=True) for s in token_shots]
    rows, warnings = stitch([r for r, _ in shots], [w for _, w in shots])
    ptype = panel_hint or detect_panel_type(rows)
    specials = [{"label": r.canonical.split(":", 1)[1], "value": r.value}
                for r in rows if r.canonical.startswith("special:") and r.value is not None]
    out = {"panel_type": ptype, "specials": specials, "warnings": list(warnings)}
    expected = {f"{c}|{s}" for c in CLASSES for s in STATS}
    if ptype == "battle":
        for side, key in (("left", "stats_left"), ("right", "stats_right")):
            st, cf, un = _bucket(rows, side)
            out[key], out[key + "_conf"] = st, cf
            out.setdefault("unreadable_fields", []).extend(f"{key}.{u.split('.',1)[1]}" for u in un)
        present = len(out["stats_left"]) + len(out["stats_right"])
        total = 24
    else:
        st, cf, un = _bucket(rows, None)
        out["stats"], out["field_conf"] = st, cf
        out["unreadable_fields"] = un
        present = len([k for k in st if k.split("|")[0] in CLASSES])
        total = 12
    missing = expected - set((out.get("stats") or {}) | (out.get("stats_left") or {}))
    out.setdefault("unreadable_fields", [])
    out["status"] = "ok" if present >= total else ("partial" if present > 0 else "failed")
    out.setdefault("stats", out.get("stats", {}))
    return out
