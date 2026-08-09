"""Production engine ladder (shell/app/ocr/panel/ladder.py).

Both engines are ALWAYS faked here: the default suite must not import
rapidocr, must not touch the network, and must not need a GEMINI_API_KEY.
The seams are ``ladder._load_rapidocr`` / ``ladder._load_gemini``.
"""
import asyncio
import pathlib
import sys
import threading
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from shell.app import db
from shell.app.ocr.panel import ladder

run = asyncio.run

CLASSES = ("Infantry", "Lancer", "Marksman")
STATS = ("Attack", "Defense", "Lethality", "Health")
IMAGE = b"\x89PNG\r\n\x1a\nfake-one"
IMAGE_2 = b"\x89PNG\r\n\x1a\nfake-two"


class _Settings:
    def __init__(self, cpu=2, budget=1200):
        self.OCR_CPU_CONCURRENCY = cpu
        self.GEMINI_OCR_DAILY_BUDGET = budget


class _FakeGeminiUnavailable(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    db.reset_db()
    monkeypatch.setattr(db, "_utcnow",
                        lambda: datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc))
    yield
    db.reset_db()


def _expected_value(cls, stat):
    """Distinct per key, so an overwrite is visible."""
    return 1000.0 + CLASSES.index(cls) * 100 + STATS.index(stat) * 10 + 0.5


def _scout_tokens(missing=(), special_conf=None):
    tokens, y = [], 0.10
    for cls in CLASSES:
        for stat in STATS:
            key = f"{cls}|{stat}"
            tokens.append({"text": f"{cls} {stat}", "x0": 0.05, "y0": y,
                           "x1": 0.40, "y1": y + 0.03, "conf": 0.99})
            tokens.append({"text": f"+{_expected_value(cls, stat)}%", "x0": 0.70, "y0": y,
                           "x1": 0.95, "y1": y + 0.03,
                           "conf": 0.20 if key in missing else 0.97})
            y += 0.05
    if special_conf is not None:
        tokens.append({"text": "Attack Bonus (Pet Skill)", "x0": 0.05, "y0": y,
                       "x1": 0.40, "y1": y + 0.03, "conf": 0.99})
        tokens.append({"text": "+10.0%", "x0": 0.70, "y0": y,
                       "x1": 0.95, "y1": y + 0.03, "conf": special_conf})
    return tokens


def _install_rapid(monkeypatch, missing=(), special_conf=None, recognize=None):
    calls = []

    def default_recognize(image_bytes):
        calls.append(image_bytes)
        return _scout_tokens(missing, special_conf)

    monkeypatch.setattr(ladder, "_load_rapidocr", lambda: recognize or default_recognize)
    return calls


def _install_gemini(monkeypatch, result=None, key="test-key", raises=None, loader=None):
    calls = []

    def extract(image_bytes, panel_hint=None, side_hint=None, **kwargs):
        calls.append({"image": image_bytes, "panel_hint": panel_hint, "side_hint": side_hint})
        if raises is not None:
            raise raises
        return result if result is not None else _gemini_result()

    monkeypatch.setattr(
        ladder, "_load_gemini",
        loader or (lambda: (extract, _FakeGeminiUnavailable, lambda settings: key)))
    return calls


def _gemini_result(stats=None, specials=None, warnings=(), status="partial"):
    stats = dict(stats or {})
    return {"panel_type": "scout", "requested_side": None,
            "stats": stats, "field_conf": {k: 1.0 for k in stats},
            "specials": list(specials or []), "specials_observed": "none",
            "unreadable_fields": [], "warnings": list(warnings), "status": status}


def _ladder(settings=None, images=(IMAGE,), side="you", panel_hint=None):
    return run(ladder.extract_panel_production(list(images), side, panel_hint,
                                               settings=settings or _Settings()))


def _gemini_events():
    return [e for e in db.get_db().usage_events if e["kind"] == ladder.GEMINI_BUDGET_KIND]


# ---------------------------------------------------------------------------
# (b) RapidOCR clean -> Gemini is never consulted
# ---------------------------------------------------------------------------

def test_clean_rapidocr_result_never_calls_gemini(monkeypatch):
    _install_rapid(monkeypatch)
    gemini_calls = _install_gemini(monkeypatch)
    result = _ladder()
    assert result["status"] == "ok"
    assert result["unreadable_fields"] == []
    assert result["engines_used"] == ["rapidocr"]
    assert result["field_engine"] == {}
    assert result["stats"]["Infantry|Attack"] == _expected_value("Infantry", "Attack")
    assert gemini_calls == []
    assert _gemini_events() == []


# ---------------------------------------------------------------------------
# (c) gap-fill: only the gaps, with provenance
# ---------------------------------------------------------------------------

def test_gemini_fills_only_the_gaps_with_provenance(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack", "Lancer|Health"})
    gemini_calls = _install_gemini(monkeypatch, result=_gemini_result(
        stats={"Infantry|Attack": 4491.6, "Lancer|Health": 3197.4}))

    result = _ladder()

    assert result["stats"]["Infantry|Attack"] == 4491.6
    assert result["stats"]["Lancer|Health"] == 3197.4
    assert result["field_engine"] == {"stats.Infantry|Attack": "gemini",
                                      "stats.Lancer|Health": "gemini"}
    assert result["unreadable_fields"] == []
    assert result["status"] == "ok"                     # recomputed from 10 -> 12
    assert result["engines_used"] == ["rapidocr", "gemini"]
    assert result["field_conf"]["Infantry|Attack"] == 1.0
    # every RapidOCR-read field keeps its own value
    for cls in CLASSES:
        for stat in STATS:
            key = f"{cls}|{stat}"
            if key not in ("Infantry|Attack", "Lancer|Health"):
                assert result["stats"][key] == _expected_value(cls, stat), key
    assert len(gemini_calls) == 1 and gemini_calls[0]["image"] == IMAGE
    assert len(_gemini_events()) == 1


def test_gemini_is_called_once_per_image_not_per_field(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack", "Lancer|Health", "Marksman|Health"})
    gemini_calls = _install_gemini(monkeypatch, result=_gemini_result(
        stats={"Infantry|Attack": 4491.6}))
    result = _ladder(images=(IMAGE, IMAGE_2))
    assert len(gemini_calls) == 2                       # two images, two calls
    assert len(_gemini_events()) == 2
    assert result["field_engine"] == {"stats.Infantry|Attack": "gemini"}
    assert "stats.Lancer|Health" in result["unreadable_fields"]


def test_gemini_stops_once_every_gap_is_filled(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})
    gemini_calls = _install_gemini(monkeypatch, result=_gemini_result(
        stats={"Infantry|Attack": 4491.6}))
    _ladder(images=(IMAGE, IMAGE_2))
    assert len(gemini_calls) == 1                       # second image not needed
    assert len(_gemini_events()) == 1


def test_gemini_value_for_a_field_rapidocr_read_is_ignored(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})
    gemini_calls = _install_gemini(monkeypatch, result=_gemini_result(stats={
        "Infantry|Attack": 4491.6,          # the gap: accepted
        "Lancer|Defense": 9.0,              # RapidOCR read this one: ignored
    }))
    result = _ladder()
    assert result["stats"]["Infantry|Attack"] == 4491.6
    assert result["stats"]["Lancer|Defense"] == _expected_value("Lancer", "Defense")
    assert result["field_engine"] == {"stats.Infantry|Attack": "gemini"}
    assert len(gemini_calls) == 1


def test_gemini_fills_a_battle_column_gap_through_the_aliases(monkeypatch):
    def recognize(image_bytes):
        tokens, y = [], 0.10
        for cls in CLASSES:
            for stat in STATS:
                tokens.append({"text": f"{cls} {stat}", "x0": 0.38, "y0": y,
                               "x1": 0.58, "y1": y + 0.03, "conf": 0.99})
                tokens.append({"text": "+1200.5%", "x0": 0.03, "y0": y, "x1": 0.23,
                               "y1": y + 0.03, "conf": 0.99, "color": "green"})
                conf = 0.20 if (cls, stat) == ("Infantry", "Attack") else 0.99
                tokens.append({"text": "+700.5%", "x0": 0.70, "y0": y, "x1": 0.90,
                               "y1": y + 0.03, "conf": conf, "color": "red"})
                y += 0.05
        return tokens

    _install_rapid(monkeypatch, recognize=recognize)
    gemini_calls = _install_gemini(monkeypatch, result={
        "panel_type": "battle", "stats_left": {}, "stats_right": {"Infantry|Attack": 694.3},
        "stats_left_conf": {}, "stats_right_conf": {"Infantry|Attack": 1.0},
        "specials": [], "unreadable_fields": [], "warnings": [], "status": "partial"})

    result = _ladder(side="you")

    assert result["panel_type"] == "battle"
    assert result["stats_right"]["Infantry|Attack"] == 694.3
    assert result["stats_enemy"]["Infantry|Attack"] == 694.3     # alias follows in place
    assert result["field_engine"] == {"stats_right.Infantry|Attack": "gemini"}
    assert result["status"] == "ok"
    # the panel type RapidOCR detected is handed to Gemini so shapes cannot diverge
    assert gemini_calls[0]["panel_hint"] == "battle"
    assert gemini_calls[0]["side_hint"] == "you"


# ---------------------------------------------------------------------------
# never-fabricate: an implausible Gemini value is not a fill
# ---------------------------------------------------------------------------

def test_gemini_value_failing_validation_stays_unreadable(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})
    _install_gemini(monkeypatch, result=_gemini_result(
        stats={"Infantry|Attack": 999999.0}))       # outside the 0..6000 band
    result = _ladder()
    assert "Infantry|Attack" not in result["stats"]
    assert "stats.Infantry|Attack" in result["unreadable_fields"]
    assert result["field_engine"] == {}
    assert result["status"] == "partial"


def test_gemini_implausible_special_stays_unreadable(monkeypatch):
    _install_rapid(monkeypatch, special_conf=0.20)
    _install_gemini(monkeypatch, result=_gemini_result(
        specials=[{"label": "Attack Bonus (Pet Skill)", "value": 250.0}]))
    result = _ladder()
    assert result["specials"] == []
    assert "specials.Attack Bonus (Pet Skill)" in result["unreadable_fields"]
    assert result["field_engine"] == {}


def test_gemini_readable_special_fills_the_gap(monkeypatch):
    _install_rapid(monkeypatch, special_conf=0.20)
    _install_gemini(monkeypatch, result=_gemini_result(
        specials=[{"label": "Attack Bonus (Pet Skill)", "value": 10.0}]))
    result = _ladder()
    assert result["specials"] == [{"label": "Attack Bonus (Pet Skill)", "value": 10.0}]
    assert "specials.Attack Bonus (Pet Skill)" not in result["unreadable_fields"]
    assert result["field_engine"] == {"specials.Attack Bonus (Pet Skill)": "gemini"}


# ---------------------------------------------------------------------------
# (d)/(e) budget guard and graceful degradation
# ---------------------------------------------------------------------------

def test_budget_at_limit_skips_gemini_with_a_warning(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})
    gemini_calls = _install_gemini(monkeypatch, result=_gemini_result(
        stats={"Infantry|Attack": 4491.6}))
    for _ in range(5):
        run(db.record_usage(ladder.GEMINI_BUDGET_USER,
                            endpoint=ladder.GEMINI_BUDGET_ENDPOINT,
                            kind=ladder.GEMINI_BUDGET_KIND))

    result = _ladder(settings=_Settings(budget=5))

    assert gemini_calls == []
    assert len(_gemini_events()) == 5                    # no new events
    assert result["engines_used"] == ["rapidocr"]
    assert "stats.Infantry|Attack" in result["unreadable_fields"]
    assert any(w.startswith("gemini fallback skipped:") for w in result["warnings"])


def test_budget_of_zero_disables_gemini(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})
    gemini_calls = _install_gemini(monkeypatch)
    result = _ladder(settings=_Settings(budget=0))
    assert gemini_calls == [] and _gemini_events() == []
    assert any("budget" in w for w in result["warnings"])


def test_budget_counter_increments_only_on_real_calls(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})
    _install_gemini(monkeypatch, result=_gemini_result(stats={"Infantry|Attack": 4491.6}))
    _ladder()
    assert len(_gemini_events()) == 1
    _ladder()
    assert len(_gemini_events()) == 2
    # a clean read consults nobody and spends nothing
    _install_rapid(monkeypatch)
    _ladder()
    assert len(_gemini_events()) == 2


def test_missing_api_key_skips_gemini_without_spending_budget(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})
    gemini_calls = _install_gemini(monkeypatch, key=None)
    result = _ladder()
    assert gemini_calls == [] and _gemini_events() == []
    assert result["engines_used"] == ["rapidocr"]
    assert any("GEMINI_API_KEY" in w for w in result["warnings"])


def test_gemini_exception_degrades_gracefully(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})
    _install_gemini(monkeypatch, raises=RuntimeError("connection reset"))
    result = _ladder()
    assert result["status"] == "partial"
    assert "stats.Infantry|Attack" in result["unreadable_fields"]
    assert result["field_engine"] == {}
    assert any("gemini fallback skipped:" in w and "connection reset" in w
               for w in result["warnings"])
    assert len(_gemini_events()) == 1        # the attempt still cost budget


def test_gemini_unavailable_error_degrades_gracefully(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})
    _install_gemini(monkeypatch, raises=_FakeGeminiUnavailable("no key"))
    result = _ladder()
    assert any("gemini fallback skipped:" in w for w in result["warnings"])
    assert "stats.Infantry|Attack" in result["unreadable_fields"]


def test_gemini_engine_import_failure_degrades_gracefully(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})

    def boom():
        raise ImportError("no module named httpx")

    monkeypatch.setattr(ladder, "_load_gemini", boom)
    result = _ladder()
    assert result["engines_used"] == ["rapidocr"]
    assert any("gemini fallback skipped:" in w for w in result["warnings"])
    assert _gemini_events() == []


def test_gemini_own_failure_result_is_reported_not_raised(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack"})
    _install_gemini(monkeypatch, result=_gemini_result(
        status="failed", warnings=["gemini extraction failed: HTTP 429"]))
    result = _ladder()
    assert result["field_engine"] == {}
    assert any("HTTP 429" in w for w in result["warnings"])
    assert "stats.Infantry|Attack" in result["unreadable_fields"]


def test_only_one_skip_warning_is_added(monkeypatch):
    _install_rapid(monkeypatch, missing={"Infantry|Attack", "Lancer|Health"})
    _install_gemini(monkeypatch, raises=RuntimeError("boom"))
    result = _ladder(images=(IMAGE, IMAGE_2))
    assert sum(1 for w in result["warnings"] if w.startswith("gemini fallback skipped:")) == 1


# ---------------------------------------------------------------------------
# (a) CPU semaphore around RapidOCR
# ---------------------------------------------------------------------------

def _concurrency_probe(monkeypatch, cap, calls, pair_size):
    state = {"in_flight": 0, "peak": 0}
    lock = threading.Lock()
    barrier = threading.Barrier(pair_size, timeout=10) if pair_size > 1 else None

    def recognize(image_bytes):
        with lock:
            state["in_flight"] += 1
            state["peak"] = max(state["peak"], state["in_flight"])
        if barrier is not None:
            barrier.wait()          # deadlocks (and fails) if fewer than
        else:                       # `pair_size` executions run concurrently
            threading.Event().wait(0.02)
        with lock:
            state["in_flight"] -= 1
        return _scout_tokens()

    _install_rapid(monkeypatch, recognize=recognize)

    async def main(settings):
        await asyncio.gather(*[
            ladder.extract_panel_production([IMAGE], "you", None, settings=settings)
            for _ in range(calls)
        ])

    run(main(_Settings(cpu=cap)))
    return state["peak"]


def test_semaphore_caps_in_flight_rapidocr_executions(monkeypatch):
    peak = _concurrency_probe(monkeypatch, cap=2, calls=6, pair_size=2)
    assert peak == 2      # exactly the cap: the barrier proves 2 ran together


def test_semaphore_of_one_serializes_rapidocr(monkeypatch):
    peak = _concurrency_probe(monkeypatch, cap=1, calls=4, pair_size=1)
    assert peak == 1
