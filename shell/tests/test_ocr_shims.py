"""Agent C — unit tests for shell.app.ocr._shims (keyless).

Covers resolve_skill_dir()'s priority order (settings object > SKILL_
INGESTION_DIR env var > default repo-relative path) and the
SkillUnavailableError shape the router relies on to map a missing
wos-battlereport-ingestion skill directory to a clean 503 instead of an
unhandled 500 (EVAL_ROUND_1.md F1; MORNING_BRIEF.md Sec-Resume Agent C brief).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `shell.app.ocr` importable regardless of pytest invocation directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shell.app.ocr._shims import (  # noqa: E402
    SkillUnavailableError,
    UserCtx,
    _StubSettings,
    _stub_from_env,
    get_settings,
    resolve_skill_dir,
)


# --- resolve_skill_dir priority order ---------------------------------------

def test_resolve_skill_dir_default_is_the_real_repo_skill():
    """No override anywhere -> the actual skill directory shipped in this repo."""
    path = resolve_skill_dir()
    assert path.name == "wos-battlereport-ingestion"
    assert (path / "scripts" / "validate_report.py").is_file()
    assert (path / "references" / "schema.md").is_file()


def test_resolve_skill_dir_env_var_overrides_default(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILL_INGESTION_DIR", str(tmp_path))
    assert resolve_skill_dir() == tmp_path
    assert resolve_skill_dir(None) == tmp_path


def test_resolve_skill_dir_settings_object_wins_over_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILL_INGESTION_DIR", "/should/be/ignored")
    settings = _StubSettings(skill_ingestion_dir=str(tmp_path))
    assert resolve_skill_dir(settings) == tmp_path


def test_resolve_skill_dir_falls_through_when_settings_field_is_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILL_INGESTION_DIR", str(tmp_path))
    settings = _StubSettings(skill_ingestion_dir=None)  # explicit "no override"
    assert resolve_skill_dir(settings) == tmp_path


def test_resolve_skill_dir_ignores_settings_without_the_attribute(monkeypatch):
    """A settings object that simply doesn't carry skill_ingestion_dir (e.g. a
    bare object, or Agent A's real Settings before/unless it adopts the
    field) must fall through to the env var / default, never raise
    AttributeError — everything here is getattr-with-default, duck-typed."""
    monkeypatch.delenv("SKILL_INGESTION_DIR", raising=False)

    class Bare:
        pass

    assert resolve_skill_dir(Bare()) == resolve_skill_dir(None)


# --- SkillUnavailableError ---------------------------------------------------

def test_skill_unavailable_error_carries_a_machine_readable_code():
    err = SkillUnavailableError("boom")
    assert err.code == "skill_unavailable"
    assert str(err) == "boom"
    custom = SkillUnavailableError("boom2", code="other_code")
    assert custom.code == "other_code"
    assert isinstance(err, RuntimeError)


# --- _StubSettings / _stub_from_env -----------------------------------------

def test_stub_settings_ocr_mock_defaults_true_matching_config_py():
    """EVAL_ROUND_1.md F24: this stub previously defaulted ocr_mock=False
    while shell/app/config.py defaults OCR_MOCK=True — two shims disagreeing
    on the default for the same mock-first knob (ARCHITECTURE.md boundary 2:
    every external service must default to mock/keyless-safe)."""
    assert _StubSettings().ocr_mock is True


def test_stub_settings_skill_ingestion_dir_defaults_to_none():
    assert _StubSettings().skill_ingestion_dir is None


def test_stub_from_env_reads_skill_ingestion_dir(monkeypatch):
    monkeypatch.setenv("SKILL_INGESTION_DIR", "/tmp/somewhere")
    assert _stub_from_env().skill_ingestion_dir == "/tmp/somewhere"
    monkeypatch.delenv("SKILL_INGESTION_DIR", raising=False)
    assert _stub_from_env().skill_ingestion_dir is None


def test_stub_from_env_ocr_mock_defaults_true(monkeypatch):
    monkeypatch.delenv("OCR_MOCK", raising=False)
    assert _stub_from_env().ocr_mock is True
    monkeypatch.setenv("OCR_MOCK", "0")
    assert _stub_from_env().ocr_mock is False


# --- get_settings() / UserCtx contract shape --------------------------------

def test_get_settings_prefers_the_real_settings_when_config_importable():
    """shell.app.config exists in this tree, so get_settings() must prefer
    it over the local stub — the stub is a pre-Agent-A fallback only."""
    settings = get_settings()
    assert not isinstance(settings, _StubSettings)


def test_user_ctx_matches_shared_contract_shape():
    u = UserCtx(user_id="u1", email=None, plan="free")
    assert u.user_id == "u1"
    assert u.email is None
    assert u.plan == "free"
