from dataclasses import dataclass

@dataclass(frozen=True)
class OcrToken:
    text: str
    x0: float; y0: float; x1: float; y1: float
    conf: float
    color: str | None = None  # 'green' | 'red' | None

def tokens_from_json(items):
    out = []
    for it in items:
        t = OcrToken(str(it["text"]), float(it["x0"]), float(it["y0"]),
                     float(it["x1"]), float(it["y1"]), float(it["conf"]), it.get("color"))
        for v in (t.x0, t.y0, t.x1, t.y1):
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"coord out of range: {v}")
        if not 0.0 <= t.conf <= 1.0:
            raise ValueError(f"conf out of range: {t.conf}")
        if t.x1 <= t.x0 or t.y1 <= t.y0:
            raise ValueError("degenerate box")
        if t.color not in (None, "green", "red"):
            raise ValueError(f"bad color: {t.color}")
        out.append(t)
    return out
