def detect_panel_type(rows):
    class_rows = [r for r in rows if "|" in r.canonical and not r.canonical.startswith(("special:", "meta:", "header:"))]
    if any(r.canonical.startswith("Troops|") for r in rows):
        return "citystats"
    sided = [r for r in class_rows if r.side in ("left", "right")]
    if len({(r.canonical) for r in sided if r.side == "left"} & {(r.canonical) for r in sided if r.side == "right"}) >= 4:
        return "battle"
    if len(class_rows) >= 4:
        return "scout"
    return "unknown"
