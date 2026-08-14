"""RapidOCR adapter for stat-panel screenshots.

The public boundary deliberately returns the JSON-shaped token dictionaries
consumed by :mod:`shell.app.ocr.panel.tokens`; no RapidOCR objects escape.
"""
from __future__ import annotations

from io import BytesIO
from threading import Lock

from PIL import Image, ImageOps

from .values import parse_value


_ENGINE = None
_ENGINE_LOCK = Lock()


def _engine():
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_LOCK:
            if _ENGINE is None:
                from rapidocr import RapidOCR

                _ENGINE = RapidOCR()
    return _ENGINE


def _number_centres(tokens):
    return [
        (token["x0"] + token["x1"]) / 2.0
        for token in tokens
        if parse_value(token["text"]) is not None
    ]


def _is_two_column(tokens):
    centres = _number_centres(tokens)
    return any(value < 0.45 for value in centres) and any(
        value > 0.55 for value in centres
    )


def _value_color(image, token):
    if parse_value(token["text"]) is None:
        return None
    width, height = image.size
    left = max(0, min(width - 1, int(token["x0"] * width)))
    top = max(0, min(height - 1, int(token["y0"] * height)))
    right = max(left + 1, min(width, int(token["x1"] * width + 0.999)))
    bottom = max(top + 1, min(height, int(token["y1"] * height + 0.999)))
    green = red = 0
    crop = image.crop((left, top, right, bottom))
    for r_value, g_value, _ in crop.get_flattened_data():
        if g_value > r_value + 40:
            green += 1
        elif r_value > g_value + 40:
            red += 1
    if green == red == 0:
        return None
    return "green" if green > red else "red"


def _recognized_items(result):
    boxes = result.boxes if result is not None else None
    texts = result.txts if result is not None else None
    scores = result.scores if result is not None else None
    if boxes is None or texts is None or scores is None:
        return []
    items = []
    for box, text, score in zip(boxes, texts, scores, strict=True):
        clean = str(text).strip()
        parts = clean.split(maxsplit=1)
        if len(parts) != 2 or parse_value(parts[0]) is None:
            items.append((box, clean, score))
            continue
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        split = x0 + (x1 - x0) * len(parts[0]) / len(clean)
        value_box = ((x0, y0), (split, y0), (split, y1), (x0, y1))
        label_box = ((split, y0), (x1, y0), (x1, y1), (split, y1))
        items.extend(((value_box, parts[0], score), (label_box, parts[1], score)))
    return items


def recognize_image(image_bytes):
    """Recognize *image_bytes* and return normalized Task-1 token dicts."""
    if not isinstance(image_bytes, (bytes, bytearray, memoryview)):
        raise TypeError("image_bytes must be bytes-like")
    raw = bytes(image_bytes)
    try:
        with Image.open(BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except Exception as exc:
        raise ValueError("unsupported or malformed OCR image") from exc

    result = _engine()(raw)

    width, height = image.size
    tokens = []
    for box, text, score in _recognized_items(result):
        clean = str(text).strip()
        if not clean:
            continue
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        x0 = max(0.0, min(xs) / width)
        y0 = max(0.0, min(ys) / height)
        x1 = min(1.0, max(xs) / width)
        y1 = min(1.0, max(ys) / height)
        if x1 <= x0 or y1 <= y0:
            continue
        tokens.append({
            "text": clean,
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "conf": max(0.0, min(1.0, float(score))),
            "color": None,
        })

    if _is_two_column(tokens):
        for token in tokens:
            token["color"] = _value_color(image, token)
    return tokens
