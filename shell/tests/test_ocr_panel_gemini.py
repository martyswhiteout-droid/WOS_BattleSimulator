"""Offline unit tests for the Gemini OCR engine adapter (keyless, no network).

Every test here mocks the HTTP layer via httpx.MockTransport — nothing in
this file makes a real network call, and the module import cost stays inside
the default suite (unlike test_ocr_panel_benchmark.py's real-engine
benchmark, which is @pytest.mark.benchmark-gated). Mirrors the style of
test_ocr_router.py / test_ocr_extract.py: dependency-injected backend
(there, a MockVision object; here, an httpx.Client wired to a MockTransport),
synthetic fixtures built in-file, one behavior per test.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import httpx
import pytest
from PIL import Image

# Make `shell.app.ocr` importable regardless of pytest invocation directory
# (mirrors test_ocr_extract.py / test_ocr_router.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shell.app.ocr.panel.engine_gemini import (  # noqa: E402
    FALLBACK_MODEL,
    MAX_ATTEMPTS_PER_MODEL,
    PRIMARY_MODEL,
    GeminiUnavailable,
    extract_panel_gemini,
)

FAKE_KEY = "sk-fake-gemini-key-for-tests-only"


# --- fixtures / helpers ------------------------------------------------

def _make_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


class _FakeSettings:
    def __init__(self, gemini_api_key=None):
        self.gemini_api_key = gemini_api_key


class _SettingsWithoutGeminiKey:
    """Mimics _shims._StubSettings before it carries a gemini_api_key field
    at all — _resolve_api_key must fall through to the raw env var."""


def _counting_sleep():
    calls = []

    def sleep(seconds):
        calls.append(seconds)

    sleep.calls = calls
    return sleep


def _gemini_body(rows) -> dict:
    """Wrap `rows` (a list of {"label","value","side"} dicts) as a valid
    Gemini generateContent response envelope."""
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(rows)}], "role": "model"},
             "finishReason": "STOP"}
        ]
    }


class _ScriptedTransport:
    """httpx.MockTransport-compatible handler that plays a fixed script of
    (status, body) responses in order, repeating the last one once
    exhausted. Records every request it saw for assertions (URL, but never
    logs headers/params — tests check the key never leaks via a different
    route: the response body/warnings)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = (
            self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        )
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=body)


def _client_for(responses):
    transport = _ScriptedTransport(responses)
    return httpx.Client(transport=httpx.MockTransport(transport)), transport


def _explode_transport(request: httpx.Request) -> httpx.Response:  # pragma: no cover
    raise AssertionError("must not call Gemini when the API key is missing")


# --- key handling --------------------------------------------------------

def test_missing_key_raises_before_any_http_call():
    client = httpx.Client(transport=httpx.MockTransport(_explode_transport))
    with pytest.raises(GeminiUnavailable):
        extract_panel_gemini(
            b"irrelevant-bytes-never-touched",
            settings=_FakeSettings(gemini_api_key=None),
            client=client,
        )


def test_env_var_fallback_used_when_settings_lack_attribute(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    rows = [{"label": "Infantry Attack", "value": "+150", "side": None}]
    client, transport = _client_for([(200, _gemini_body(rows))])
    result = extract_panel_gemini(
        _make_png(), settings=_SettingsWithoutGeminiKey(), client=client,
    )
    assert result["stats"]["Infantry|Attack"] == 150.0
    assert len(transport.requests) == 1


# --- happy paths -----------------------------------------------------------

def _citystats_rows():
    rows = [
        {"label": "Troops' Attack", "value": "+429.07", "side": None},
        {"label": "Troops' Defense", "value": "+477.37", "side": None},
        {"label": "Troops' Lethality", "value": "+109.9", "side": None},
        {"label": "Troops' Health", "value": "+103.9", "side": None},
    ]
    per_class = {
        "Infantry": ("436.25", "435.25", "523.71", "516.77"),
        "Lancer": ("421.81", "407.81", "519.99", "521.82"),
        "Marksman": ("460.25", "440.25", "556.33", "555.74"),
    }
    for cls, (atk, dfn, leth, hp) in per_class.items():
        for stat, value in zip(("Attack", "Defense", "Lethality", "Health"), (atk, dfn, leth, hp)):
            rows.append({"label": f"{cls} {stat}", "value": f"+{value}", "side": None})
    return rows


def test_happy_path_citystats_full_panel():
    client, transport = _client_for([(200, _gemini_body(_citystats_rows()))])
    result = extract_panel_gemini(
        _make_png(), settings=_FakeSettings(gemini_api_key=FAKE_KEY), client=client,
    )
    assert result["panel_type"] == "citystats"
    assert result["status"] == "ok"
    assert result["stats"]["Troops|Attack"] == 429.07
    assert result["stats"]["Infantry|Attack"] == 436.25
    assert result["stats"]["Marksman|Health"] == 555.74
    assert len(result["stats"]) == 16  # 4 Troops + 3 classes x 4 stats
    assert result["unreadable_fields"] == []
    assert result["engine_model"] == PRIMARY_MODEL
    assert len(transport.requests) == 1


def _battle_rows():
    left = {
        "Infantry": ("2269.7", "2151.7", "1126.5", "1129.0"),
        "Lancer": ("2189.6", "2064.1", "1103.7", "1058.4"),
        "Marksman": ("2385.8", "2240.6", "1263.9", "1257.3"),
    }
    right = {
        "Infantry": ("543.3", "509.1", "411.7", "368.3"),
        "Lancer": ("553.1", "497.7", "417.0", "367.6"),
        "Marksman": ("645.4", "587.2", "466.1", "392.2"),
    }
    rows = []
    for side_name, table in (("left", left), ("right", right)):
        for cls, (atk, dfn, leth, hp) in table.items():
            for stat, value in zip(("Attack", "Defense", "Lethality", "Health"), (atk, dfn, leth, hp)):
                rows.append({"label": f"{cls} {stat}", "value": f"+{value}", "side": side_name})
    return rows


def test_happy_path_battle_two_columns_with_side_aliasing():
    client, _ = _client_for([(200, _gemini_body(_battle_rows()))])
    result = extract_panel_gemini(
        _make_png(), side_hint="you",
        settings=_FakeSettings(gemini_api_key=FAKE_KEY), client=client,
    )
    assert result["panel_type"] == "battle"
    assert result["status"] == "ok"
    assert result["stats_left"]["Infantry|Attack"] == 2269.7
    assert result["stats_right"]["Infantry|Attack"] == 543.3
    assert "stats" not in result  # QA D-018: battle results carry no bare "stats"
    # side_hint="you" -> left is you, right is enemy
    assert result["stats_you"] == result["stats_left"]
    assert result["stats_enemy"] == result["stats_right"]


# --- never-fabricate gates (binding decision #3) ---------------------------

def test_null_value_row_is_unreadable_not_emitted():
    rows = [{"label": "Infantry Attack", "value": None, "side": None}]
    client, _ = _client_for([(200, _gemini_body(rows))])
    result = extract_panel_gemini(
        _make_png(), settings=_FakeSettings(gemini_api_key=FAKE_KEY), client=client,
    )
    assert "Infantry|Attack" not in result["stats"]
    assert "stats.Infantry|Attack" in result["unreadable_fields"]


def test_wrong_format_value_is_unreadable_not_emitted():
    rows = [{"label": "Infantry Attack", "value": "12abc", "side": None}]
    client, _ = _client_for([(200, _gemini_body(rows))])
    result = extract_panel_gemini(
        _make_png(), settings=_FakeSettings(gemini_api_key=FAKE_KEY), client=client,
    )
    assert "Infantry|Attack" not in result["stats"]
    assert "stats.Infantry|Attack" in result["unreadable_fields"]
    assert result["status"] == "failed"


def test_out_of_range_class_value_is_unreadable():
    # CLASS_VALUE_MAX is 6000.0 (service.py) -> +99999 is an OCR artefact.
    rows = [{"label": "Infantry Attack", "value": "+99999", "side": None}]
    client, _ = _client_for([(200, _gemini_body(rows))])
    result = extract_panel_gemini(
        _make_png(), settings=_FakeSettings(gemini_api_key=FAKE_KEY), client=client,
    )
    assert "Infantry|Attack" not in result["stats"]
    assert "stats.Infantry|Attack" in result["unreadable_fields"]


def test_out_of_range_special_value_is_unreadable():
    # SPECIAL_ABS_MAX is 25.0 (service.py) -> +500% is implausible for a
    # special bonus row.
    rows = [{"label": "Defender Troops' Attack", "value": "+500%", "side": None}]
    client, _ = _client_for([(200, _gemini_body(rows))])
    result = extract_panel_gemini(
        _make_png(), settings=_FakeSettings(gemini_api_key=FAKE_KEY), client=client,
    )
    assert result["specials"] == []
    assert "specials.Defender Troops' Attack" in result["unreadable_fields"]


def test_unrecognized_label_is_dropped_silently():
    rows = [
        {"label": "Infantry Attack", "value": "+150", "side": None},
        {"label": "Completely Unknown Nonsense Row", "value": "+42", "side": None},
    ]
    client, _ = _client_for([(200, _gemini_body(rows))])
    result = extract_panel_gemini(
        _make_png(), settings=_FakeSettings(gemini_api_key=FAKE_KEY), client=client,
    )
    # the unknown row contributes nothing at all: not folded into stats under
    # any key, and not even reported as unreadable (mirrors rows.py, which
    # drops a label the lexicon can't match rather than guessing an
    # attribution for it).
    assert result["stats"] == {"Infantry|Attack": 150.0}
    assert not any("Unknown Nonsense" in field for field in result["unreadable_fields"])


# --- HTTP resilience (binding decision #5) ----------------------------------

def test_429_then_success_retries_once_and_key_never_leaks():
    rows = [{"label": "Infantry Attack", "value": "+150", "side": None}]
    client, transport = _client_for([
        (429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}}),
        (200, _gemini_body(rows)),
    ])
    sleep = _counting_sleep()
    result = extract_panel_gemini(
        _make_png(), settings=_FakeSettings(gemini_api_key=FAKE_KEY),
        client=client, sleep=sleep,
    )
    assert result["stats"]["Infantry|Attack"] == 150.0
    assert len(transport.requests) == 2
    assert len(sleep.calls) == 1
    # the key must never surface in the result (warnings, or anywhere else)
    assert FAKE_KEY not in json.dumps(result)


def test_persistent_5xx_exhausts_retry_budget_and_fails_cleanly():
    client, transport = _client_for([(503, {"error": {"code": 503, "status": "UNAVAILABLE"}})])
    sleep = _counting_sleep()
    result = extract_panel_gemini(
        _make_png(), settings=_FakeSettings(gemini_api_key=FAKE_KEY),
        client=client, sleep=sleep,
    )
    assert result["status"] == "failed"
    assert result["stats"] == {}
    assert any("gemini extraction failed" in w for w in result["warnings"])
    # exactly MAX_ATTEMPTS_PER_MODEL requests against the primary model, no more
    assert MAX_ATTEMPTS_PER_MODEL == 2
    assert len(transport.requests) == MAX_ATTEMPTS_PER_MODEL
    assert len(sleep.calls) == 1


@pytest.mark.parametrize("body", [
    "not json at all",
    {"candidates": []},
    {"candidates": [{"content": {"parts": [{"text": "Sure! Here are the rows: nope."}]}}]},
])
def test_malformed_or_empty_gemini_response_yields_failed_status_no_exception(body):
    client, _ = _client_for([(200, body)])
    result = extract_panel_gemini(
        _make_png(), settings=_FakeSettings(gemini_api_key=FAKE_KEY), client=client,
    )
    assert result["status"] == "failed"
    assert result["stats"] == {}
    assert result["specials"] == []
    assert any("gemini" in w.lower() for w in result["warnings"])


def test_model_404_falls_back_to_secondary_model():
    rows = [{"label": "Infantry Attack", "value": "+150", "side": None}]
    client, transport = _client_for([
        (404, {"error": {"code": 404, "status": "NOT_FOUND"}}),
        (200, _gemini_body(rows)),
    ])
    result = extract_panel_gemini(
        _make_png(), settings=_FakeSettings(gemini_api_key=FAKE_KEY), client=client,
    )
    assert result["stats"]["Infantry|Attack"] == 150.0
    assert result["engine_model"] == FALLBACK_MODEL
    assert len(transport.requests) == 2
    assert PRIMARY_MODEL in str(transport.requests[0].url)
    assert FALLBACK_MODEL in str(transport.requests[1].url)
