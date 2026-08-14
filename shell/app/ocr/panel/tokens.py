from dataclasses import dataclass

@dataclass(frozen=True)
class OcrToken:
    text: str
    x0: float; y0: float; x1: float; y1: float
    conf: float
    color: str | None = None  # 'green' | 'red' | None

def tokens_from_json(items):
    """Validate one shot's worth of raw OCR tokens.

    Every rejection is a ValueError (QA D-019): a malformed engine payload must
    never surface as a KeyError/TypeError 500 further up the stack.
    """
    if not isinstance(items, (list, tuple)):
        raise ValueError(f"token shot must be a list, got {type(items).__name__}")
    out = []
    for it in items:
        if not isinstance(it, dict):
            raise ValueError(f"token must be an object, got {type(it).__name__}")
        try:
            t = OcrToken(str(it["text"]), float(it["x0"]), float(it["y0"]),
                         float(it["x1"]), float(it["y1"]), float(it["conf"]), it.get("color"))
        except KeyError as exc:
            raise ValueError(f"token missing key {exc}") from exc
        except TypeError as exc:
            raise ValueError(f"token has a non-numeric field: {exc}") from exc
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
