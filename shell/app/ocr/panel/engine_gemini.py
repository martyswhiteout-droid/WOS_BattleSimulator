"""Gemini vision-LLM adapter for stat-panel OCR (docs/OCR_GEMINI_FREE_TIER.md).

``extract_panel_gemini`` is a THIRD engine for the stat-panel OCR benchmark,
alongside :func:`shell.app.ocr.panel.engine_rapidocr.recognize_image` (token
OCR) and the client-side tesseract.js engine. Unlike those two, a vision LLM's
native strength is structured extraction, not per-token bounding boxes — so
this adapter does NOT fake the token/bbox contract consumed by
:mod:`shell.app.ocr.panel.tokens` / ``rows`` / ``stitch`` / ``detect``.
Instead it asks Gemini directly for one JSON row per panel line ({label,
value, side}) and returns the SAME final shape
:func:`shell.app.ocr.panel.service.extract_panel` does: stats /
stats_left+stats_right+aliases / specials / specials_observed /
unreadable_fields / warnings / status / panel_type.

Never-fabricate enforcement is OURS, not the model's (binding decision #3):
every returned value string is parsed by the existing grammar
(:func:`shell.app.ocr.panel.values.parse_value`), every label is resolved by
the existing lexicon (:func:`shell.app.ocr.panel.lexicon.match_label`), and
the exact same range gates / bucketing / status conventions from
:mod:`shell.app.ocr.panel.service` are imported and reused verbatim — that
module is never modified by this adapter. A value the grammar rejects, a
value outside its plausibility band, or a label the lexicon doesn't
recognise never reaches ``stats``/``specials``: it is dropped or reported
unreadable exactly like a bad real-OCR token would be.

Key handling: ``GEMINI_API_KEY`` is read the same way
:mod:`shell.app.ocr.vision` reads ``ANTHROPIC_API_KEY`` — via the shared
Settings shim, with a raw env-var fallback — and it is NEVER logged. No key
-> ``GeminiUnavailable`` (the caller, e.g. the benchmark, is expected to skip
this engine on that error; this module never crashes the caller otherwise).

Resilience (binding decision #5): one retry with backoff on 429/5xx, a hard
per-request timeout, and — separately — one fallback to a newer Flash model
id if the primary model 404s (binding decision #2). Every other failure mode
(network error, malformed JSON, an unexpected response shape) degrades to a
normal ``status: "failed"`` result carrying a diagnostic warning; it never
raises past this module's public entry point and never guesses a value.
"""
from __future__ import annotations

import base64
import json
import os
import time
from io import BytesIO

import httpx
from PIL import Image

from .detect import detect_panel_type
from .lexicon import CLASSES, match_label
from .rows import PanelRow
from .service import (
    CLASS_VALUE_MAX,
    CLASS_VALUE_MIN,
    EXPECTED_KEYS,
    INCOMPATIBLE_HINTS,
    SPECIAL_ABS_MAX,
    _bucket,
    _dedupe,
    _hint_warning,
    _specials,
)
from .values import parse_value

# --- model + endpoint --------------------------------------------------
# docs/OCR_GEMINI_FREE_TIER.md §1 (2026-08-06): "Gemini 3 Flash" is Google's
# current recommended free-tier model. Its exact API model-id string is a
# best-effort read of Google's docs, NOT verified live (no GEMINI_API_KEY in
# this environment) — that is exactly why the 404 fallback below is
# mandatory, not decorative (binding decision #2: "fall back to the newest
# Flash the API lists if that exact id 404s").
PRIMARY_MODEL = "gemini-3-flash-preview"
FALLBACK_MODEL = "gemini-2.5-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

REQUEST_TIMEOUT_S = 30.0       # binding decision #5: hard timeout ~30s/image
RETRY_BACKOFF_S = 1.0          # backoff before the single 429/5xx retry
MAX_ATTEMPTS_PER_MODEL = 2     # 1 initial attempt + 1 retry, per model id

_MEDIA_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}

PANEL_EXTRACTION_PROMPT = (
    "You are a deterministic OCR extraction engine reading ONE screenshot of "
    "a Whiteout Survival (WoS) stat panel (a city-stats / Bonus Overview "
    "screen, a scout report, a battle report, or a Stat Bonuses / specials "
    "screen).\n"
    "\n"
    "Return a JSON array with one object per row you can see on the panel:\n"
    '  {"label": <row label exactly as printed>, "value": <the row\'s value '
    'exactly as printed, as a string, or null>, "side": "left" | "right" | '
    "null}\n"
    "\n"
    "Binding rules:\n"
    "1. Transcribe EXACT digits. NEVER guess, round, or infer a value you "
    "cannot clearly read.\n"
    "2. If a row's value is not clearly legible, set \"value\" to null. A "
    "null value is always safer than a guessed digit.\n"
    "3. Preserve punctuation exactly as shown: a leading +/- sign, a "
    "trailing % sign, and thousands-separator commas — e.g. \"1,126.5\", "
    "\"+7.5%\", \"-25%\".\n"
    "4. Some panels show TWO value columns side by side (a comparison "
    "between two armies/players). The GREEN-colored column is \"left\"; the "
    "RED-colored column is \"right\". Read both columns and set \"side\" "
    "accordingly for each. On a single-column panel, set \"side\" to null.\n"
    "5. Include every row you can see, including section header/title rows "
    "(value null) and rows whose value is null.\n"
    "6. Output ONLY the JSON array — no markdown fences, no commentary, no "
    "extra keys.\n"
)

PANEL_ROW_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "label": {"type": "STRING"},
            "value": {"type": "STRING", "nullable": True},
            "side": {"type": "STRING", "enum": ["left", "right"], "nullable": True},
        },
        "required": ["label", "value", "side"],
    },
}


class GeminiUnavailable(RuntimeError):
    """No GEMINI_API_KEY configured; the caller should skip this engine."""


class _GeminiCallFailed(Exception):
    """Internal: any post-key-check failure. Always caught inside
    ``extract_panel_gemini`` and turned into a normal ``status: "failed"``
    result — this never escapes the public entry point."""


class _ModelNotFound(_GeminiCallFailed):
    """Internal: a model id 404d. Triggers the fallback-model attempt."""

    def __init__(self, model: str):
        super().__init__(f"model {model!r} was not found (404)")
        self.model = model


def _resolve_api_key(settings=None) -> str | None:
    """GEMINI_API_KEY via Settings, exactly like vision.py resolves its own
    key, with a raw env-var fallback for settings objects that predate this
    slot (mirrors _shims._StubSettings not yet carrying gemini_api_key)."""
    if settings is None:
        from .._shims import get_settings

        settings = get_settings()
    key = getattr(settings, "gemini_api_key", None) or getattr(settings, "GEMINI_API_KEY", None)
    if not key:
        key = os.environ.get("GEMINI_API_KEY")
    return key or None


def _sniff_media_type(image_bytes: bytes) -> str:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            fmt = image.format
    except Exception as exc:  # any PIL failure means "unreadable image"
        raise _GeminiCallFailed(f"unreadable image: {exc}") from exc
    media_type = _MEDIA_TYPES.get(fmt or "")
    if media_type is None:
        raise _GeminiCallFailed(f"unsupported image format for Gemini: {fmt}")
    return media_type


def _build_payload(image_bytes: bytes, media_type: str) -> dict:
    return {
        "contents": [{
            "role": "user",
            "parts": [
                {"inline_data": {
                    "mime_type": media_type,
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                }},
                {"text": PANEL_EXTRACTION_PROMPT},
            ],
        }],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": PANEL_ROW_SCHEMA,
        },
    }


def _call_model(client, model, api_key, payload, sleep):
    """POST *payload* to *model*. Returns the parsed response JSON on HTTP 200.

    Raises ``_ModelNotFound`` immediately on 404 (no retry — a wrong model id
    is a caller decision, not a transient failure). Retries once, after
    ``RETRY_BACKOFF_S``, on 429/5xx or a network-level error. Raises
    ``_GeminiCallFailed`` once the retry budget is exhausted, or immediately
    for any other non-2xx status (e.g. 400/401/403 — retrying won't fix
    those).
    """
    url = f"{API_BASE}/{model}:generateContent"
    last_error = None
    for attempt in range(MAX_ATTEMPTS_PER_MODEL):
        try:
            response = client.post(
                url, params={"key": api_key}, json=payload, timeout=REQUEST_TIMEOUT_S,
            )
        except httpx.HTTPError as exc:
            last_error = _GeminiCallFailed(f"network error calling Gemini ({model}): {exc}")
            retryable = True
        else:
            if response.status_code == 404:
                raise _ModelNotFound(model)
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    raise _GeminiCallFailed(
                        f"Gemini ({model}) response body was not valid JSON"
                    ) from exc
            last_error = _GeminiCallFailed(
                f"Gemini ({model}) returned HTTP {response.status_code}"
            )
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable:
                raise last_error
        if attempt + 1 < MAX_ATTEMPTS_PER_MODEL:
            sleep(RETRY_BACKOFF_S)
    raise last_error


def _call_with_fallback(client, api_key, payload, sleep):
    """Try PRIMARY_MODEL; on 404, try FALLBACK_MODEL once. Returns
    ``(response_json, model_id_used)``."""
    try:
        return _call_model(client, PRIMARY_MODEL, api_key, payload, sleep), PRIMARY_MODEL
    except _ModelNotFound:
        return _call_model(client, FALLBACK_MODEL, api_key, payload, sleep), FALLBACK_MODEL


def _to_panel_row(item):
    """One Gemini row -> a rows.PanelRow, or None if the label is unrecognised
    (dropped, exactly like an unmatched real-OCR row in rows.assemble_rows —
    QA D-026: numbers with nothing the lexicon recognises to attach them to
    are dropped, never guessed onto a neighbour)."""
    if not isinstance(item, dict):
        return None
    canonical = match_label(item.get("label") or "")
    if canonical is None:
        return None
    side = item.get("side")
    if side not in ("left", "right"):
        side = None
    raw_value = item.get("value")
    raw_label = str(item.get("label") or "")
    if raw_value is None:
        return PanelRow(canonical, side, None, None, 0.0, raw_label, ("missing_value",))
    parsed = parse_value(str(raw_value))
    if parsed is None:
        # Grammar rejected it (e.g. "12abc") — never fabricate a number from
        # a string the shared parser itself does not trust.
        return PanelRow(canonical, side, None, None, 0.0, raw_label, ("gemini_unparseable",))
    return PanelRow(canonical, side, parsed.value, parsed.unit, 1.0, raw_label, ())


def _parse_rows(response_json):
    candidates = response_json.get("candidates") or []
    if not candidates:
        raise _GeminiCallFailed("Gemini response had no candidates")
    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if not text.strip():
        raise _GeminiCallFailed("Gemini response had no text output")
    try:
        items = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _GeminiCallFailed(f"Gemini output was not valid JSON: {exc}") from exc
    if not isinstance(items, list):
        raise _GeminiCallFailed("Gemini output JSON was not a list of rows")
    return [row for row in (_to_panel_row(item) for item in items) if row is not None]


def _assemble_result(rows, warnings, side_hint, panel_hint):
    """The exact orchestration tail of ``service.extract_panel`` (detect ->
    hint check -> bucket -> specials -> dedupe -> status), reusing its gating
    helpers verbatim so Gemini's output is honoured by the SAME
    never-fabricate rules as every other engine. ``service.py`` itself is
    never modified or duplicated in substance — only this short control-flow
    shell differs, because the input here is already-assembled rows instead
    of raw token shots run through stitch()."""
    detected = detect_panel_type(rows)
    specials, special_unreadable, specials_observed = _specials(rows)
    ptype = detected
    warnings = list(warnings)
    if panel_hint:
        if (panel_hint, detected) in INCOMPATIBLE_HINTS:
            return {"panel_type": detected, "requested_side": side_hint,
                    "specials": specials, "specials_observed": specials_observed,
                    "warnings": warnings + [
                        f"panel hint {panel_hint} contradicts detected {detected}"],
                    "stats": {}, "field_conf": {}, "unreadable_fields": [],
                    "status": "failed"}
        if detected != panel_hint:
            warnings.append(_hint_warning(panel_hint, detected))
        ptype = panel_hint
    out = {"panel_type": ptype, "requested_side": side_hint, "specials": specials,
           "specials_observed": specials_observed, "warnings": warnings}
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


def extract_panel_gemini(image_bytes: bytes, panel_hint: str | None = None,
                          side_hint: str | None = None, *, settings=None,
                          client=None, sleep=None) -> dict:
    """Gemini vision engine adapter. Same output contract as
    ``service.extract_panel`` (see module docstring): panel_type / stats (or
    stats_left+stats_right+aliases) / specials / specials_observed /
    unreadable_fields / warnings / status, plus an informational
    ``engine_model`` field naming which model id actually served the
    request (None on total failure).

    ``settings``/``client``/``sleep`` are optional injection points for
    tests (a fake Settings-like object, an ``httpx.Client`` wired to a
    ``MockTransport``, and a fast/no-op backoff sleep) — production callers
    omit all three and get the real Settings, a real ``httpx.Client``, and
    ``time.sleep``.

    Raises ``GeminiUnavailable`` if no ``GEMINI_API_KEY`` is configured.
    Every other failure (network, HTTP, malformed output) is caught and
    returned as a normal ``status: "failed"`` result with a diagnostic
    warning — this function never raises for those and never fabricates a
    value (binding decision #5).
    """
    api_key = _resolve_api_key(settings)
    if not api_key:
        raise GeminiUnavailable(
            "GEMINI_API_KEY is not configured; set it in shell/.env or the "
            "environment to use the Gemini OCR engine "
            "(docs/OCR_GEMINI_FREE_TIER.md §4)."
        )
    sleep_fn = sleep or time.sleep
    owns_client = client is None
    http_client = client or httpx.Client()
    rows, warnings, engine_model = [], [], None
    try:
        media_type = _sniff_media_type(image_bytes)
        payload = _build_payload(image_bytes, media_type)
        response_json, engine_model = _call_with_fallback(http_client, api_key, payload, sleep_fn)
        rows = _parse_rows(response_json)
    except _GeminiCallFailed as exc:
        warnings.append(f"gemini extraction failed: {exc}")
        # engine_model may already be set here (HTTP succeeded, but the
        # model's own text output failed to parse) — keep it, it is still
        # useful diagnostic information about which model actually replied.
    finally:
        if owns_client:
            http_client.close()
    result = _assemble_result(rows, warnings, side_hint, panel_hint)
    result["engine_model"] = engine_model
    return result
