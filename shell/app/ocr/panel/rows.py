from collections import namedtuple
from statistics import median
from .values import parse_value
from .lexicon import match_label

PanelRow = namedtuple("PanelRow", "canonical side value unit conf raw_label flags")
LOW_CONF = 0.90

def _group_rows(tokens):
    toks = sorted(tokens, key=lambda t: ((t.y0 + t.y1) / 2, t.x0))
    if not toks:
        return []
    h = median(t.y1 - t.y0 for t in toks)
    groups, cur, cur_y = [], [toks[0]], (toks[0].y0 + toks[0].y1) / 2
    for t in toks[1:]:
        cy = (t.y0 + t.y1) / 2
        if abs(cy - cur_y) <= 0.6 * h:
            cur.append(t)
            cur_y = min(cur_y, cy)
        else:
            groups.append(cur)
            cur, cur_y = [t], cy
    groups.append(cur)
    return groups

def assemble_rows(tokens, two_column):
    out = []
    for group in _group_rows(tokens):
        labels = [t for t in group if parse_value(t.text) is None]
        values = [t for t in group if parse_value(t.text) is not None]
        raw_label = " ".join(t.text for t in sorted(labels, key=lambda t: t.x0)).strip()
        canonical = match_label(raw_label)
        if canonical is None:
            continue
        if not values:
            out.append(PanelRow(canonical, None, None, None, 0.0, raw_label, ("missing_value",)))
            continue
        lx = (min(t.x0 for t in labels) + max(t.x1 for t in labels)) / 2 if labels else 0.5
        for vt in values:
            pv = parse_value(vt.text)
            flags = []
            side = None
            if two_column:
                geo = "left" if (vt.x0 + vt.x1) / 2 < lx else "right"
                col = {"green": "left", "red": "right"}.get(vt.color)
                side = col or geo
                if col and col != geo:
                    flags.append("col_conflict")
            if vt.conf < LOW_CONF:
                flags.append("low_conf")
            out.append(PanelRow(canonical, side, pv.value, pv.unit, vt.conf, raw_label, tuple(flags)))
    return out
