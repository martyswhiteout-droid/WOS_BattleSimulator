from .rows import PanelRow


def stitch(rows_per_shot, warnings_per_shot=None):
    """Merge per-shot rows. Returns ``(rows, warnings)``.

    ``warnings_per_shot`` (QA D-001) carries the assembly warnings of each shot
    — orphaned values — which are merged, in shot order, ahead of the conflict
    warnings raised here.
    """
    order, best, warns = [], {}, []
    for shot_warnings in (warnings_per_shot or []):
        warns.extend(shot_warnings)
    for rows in rows_per_shot:
        for r in rows:
            k = (r.canonical, r.side)
            if k not in best:
                best[k] = r
                order.append(k)
            else:
                cur = best[k]
                if cur.value is not None and r.value is not None and cur.value != r.value:
                    warns.append(f"conflict on {k}: {cur.value} vs {r.value}")
                    best[k] = PanelRow(r.canonical, r.side, None, None, 0.0, r.raw_label,
                                       tuple(set(cur.flags) | set(r.flags) | {"conflict"}))
                elif r.value is not None and (cur.value is None or r.conf > cur.conf):
                    best[k] = r
    return [best[k] for k in order], warns
