from collections import namedtuple
from statistics import median
from .values import parse_value
from .lexicon import match_label

PanelRow = namedtuple("PanelRow", "canonical side value unit conf raw_label flags")
LOW_CONF = 0.90

# QA D-001 (row drift): a value token may only pair with a label row whose own
# vertical band contains the value's centre. The band is the label tokens'
# centre span widened by BAND_SLACK * h_row, where (QA D-025)
#     h_row = max(median token height for the shot, median LABEL height of the
#                 row itself)
# so a tall row inside a shot of small tokens is judged against its own line
# height instead of the shot's — otherwise ordinary jitter on that row reads as
# drift and the value is wrongly orphaned.
#
# Deviation note (deliberate, documented): the ruling wrote the band as
# [min(label y0) - 0.35h, max(label y1) + 0.35h] tested against the value's
# centre. With single-token labels that band is +/-0.85h around the label
# centre, i.e. LOOSER than the 0.6h row-grouping tolerance, so it can never
# reject anything the grouper accepted (a no-op) and it does NOT produce the
# ruling's own probe outcome (value centre .130 vs label band .100-.130 must be
# rejected). Anchoring the band on the label centres makes the gate 0.35h,
# strictly tighter than the grouper, and reproduces the probe exactly.
BAND_SLACK = 0.35


def _median_height(tokens):
    return median(t.y1 - t.y0 for t in tokens)


def _group_rows(tokens, h):
    toks = sorted(tokens, key=lambda t: ((t.y0 + t.y1) / 2, t.x0))
    if not toks:
        return []
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
    """Group tokens into panel rows.

    Returns ``(rows, warnings)``. Warnings carry values that could not be
    attributed to any label row — "orphan value near y=..." when the value
    missed its row's band (QA D-001), "unmatched row near y=..." when a group
    holds numbers but no label the lexicon recognises (QA D-026). Such values
    are DROPPED, never guessed onto a neighbouring label.
    """
    out, warnings = [], []
    toks = list(tokens)
    if not toks:
        return out, warnings
    h = _median_height(toks)
    for group in _group_rows(toks, h):
        labels = [t for t in group if parse_value(t.text) is None]
        values = [t for t in group if parse_value(t.text) is not None]
        raw_label = " ".join(t.text for t in sorted(labels, key=lambda t: t.x0)).strip()
        canonical = match_label(raw_label)
        if canonical is None:
            if values:  # numbers with nothing to attach them to (QA D-026)
                cy = (values[0].y0 + values[0].y1) / 2
                warnings.append(f"unmatched row near y={cy:.3f}")
            continue
        h_row = max(h, median(t.y1 - t.y0 for t in labels))
        label_cys = [(t.y0 + t.y1) / 2 for t in labels]
        band_lo = min(label_cys) - BAND_SLACK * h_row
        band_hi = max(label_cys) + BAND_SLACK * h_row
        in_band = []
        for vt in values:
            cy = (vt.y0 + vt.y1) / 2
            if band_lo <= cy <= band_hi:
                in_band.append(vt)
            else:
                warnings.append(f"orphan value near y={cy:.3f}")
        if not in_band:
            out.append(PanelRow(canonical, None, None, None, 0.0, raw_label, ("missing_value",)))
            continue
        lx = (min(t.x0 for t in labels) + max(t.x1 for t in labels)) / 2
        for vt in in_band:
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
    return out, warnings
