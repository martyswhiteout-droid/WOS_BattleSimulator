"""Compatibility shims for Agent C's OCR module (PRODUCTION_PLAN.md §2.3).

Per shell/ARCHITECTURE.md: import Settings/UserCtx from shell.app.config /
shell.app.auth when Agent A has landed them; otherwise provide local stubs
that honour the same contract (env-driven, dev defaults, keyless-safe).

Everything here is deliberately duck-typed: downstream code accesses settings
via attributes with getattr defaults, so either Agent A's pydantic-settings
object or the stub below works unchanged.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# <root>/shell/app/ocr/_shims.py -> parents[3] == <root>. Same depth as
# extract.py/vision.py, so this resolves to the identical absolute path
# regardless of which module calls resolve_skill_dir().
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SKILL_DIR = _REPO_ROOT / ".claude" / "skills" / "wos-battlereport-ingestion"


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


class SkillUnavailableError(RuntimeError):
    """The wos-battlereport-ingestion skill directory could not be found.

    Raised by extract.py's validator loader and vision.py's schema loader
    when the resolved skill directory (settings.skill_ingestion_dir >
    SKILL_INGESTION_DIR env var > default repo-relative path) has no
    validator script / schema file. This is a deploy/ops problem (F1 in
    shell/EVAL_ROUND_1.md: the Docker image and promote bundle can omit
    .claude/), never a client error and never an unhandled crash — the
    router maps it to a clean 503, not a bare 500.
    """

    def __init__(self, message: str, code: str = "skill_unavailable"):
        super().__init__(message)
        self.code = code


def resolve_skill_dir(settings: Any = None) -> Path:
    """Resolve the ingestion-skill directory.

    Priority: settings.skill_ingestion_dir (if the settings object carries
    one) > SKILL_INGESTION_DIR env var > the default repo-relative path.
    Kept dynamic (not a frozen constant) so ops can relocate the skill
    directory in a deployed image without a code change, and so tests can
    exercise the "missing skill" path via a stub settings object instead of
    mutating process-wide env vars.
    """
    override = None
    if settings is not None:
        override = getattr(settings, "skill_ingestion_dir", None)
    if not override:
        override = os.environ.get("SKILL_INGESTION_DIR")
    if override:
        return Path(override)
    return _DEFAULT_SKILL_DIR


@runtime_checkable
class SettingsLike(Protocol):
    """Minimal settings surface the OCR module needs (ARCHITECTURE.md config keys)."""

    dev_bypass: bool
    anthropic_api_key: str | None
    ocr_mock: bool
    base_url: str


@dataclass
class _StubSettings:
    """Local fallback until Agent A's shell.app.config lands. Env-driven, dev defaults.

    NOTE (EVAL_ROUND_1.md F24): this stub is normally unreachable once
    shell.app.config exists — get_settings() below always prefers the real
    Settings object. It is kept as defensive fallback (matches its original
    pre-Agent-A purpose), so its defaults must still agree with config.py's
    rather than silently drifting. ocr_mock defaults True here to match
    config.py's OCR_MOCK=True (mock-first rule, ARCHITECTURE.md boundary 2) —
    this was previously False, a divergent default that only ever mattered if
    this fallback path were ever actually exercised.
    """

    dev_bypass: bool = True
    anthropic_api_key: str | None = None
    ocr_mock: bool = True
    base_url: str = "http://localhost:8200"
    # OCR-specific knobs (not in the shared contract list; Agent A may adopt them).
    ocr_vision_model: str = "claude-sonnet-4-5"
    ocr_mock_fixture: str | None = None
    skill_ingestion_dir: str | None = None


def _stub_from_env() -> _StubSettings:
    return _StubSettings(
        dev_bypass=_env_bool("DEV_BYPASS", True),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        ocr_mock=_env_bool("OCR_MOCK", True),
        base_url=os.environ.get("BASE_URL", "http://localhost:8200"),
        ocr_vision_model=os.environ.get("OCR_VISION_MODEL", "claude-sonnet-4-5"),
        ocr_mock_fixture=os.environ.get("OCR_MOCK_FIXTURE") or None,
        skill_ingestion_dir=os.environ.get("SKILL_INGESTION_DIR") or None,
    )


def get_settings() -> Any:
    """Return Agent A's Settings if importable, else the env-driven stub."""
    try:  # Agent A's config (preferred once it exists)
        from shell.app.config import get_settings as _real_get_settings  # type: ignore

        return _real_get_settings()
    except Exception:
        pass
    try:
        from shell.app.config import Settings as _RealSettings  # type: ignore

        return _RealSettings()
    except Exception:
        return _stub_from_env()


# --- UserCtx ---------------------------------------------------------------

try:  # Agent A's auth (preferred once it exists)
    from shell.app.auth import UserCtx  # type: ignore
except Exception:  # pragma: no cover - exercised only pre-Agent-A

    @dataclass
    class UserCtx:  # type: ignore[no-redef]
        """Stub matching the shared contract in shell/ARCHITECTURE.md exactly."""

        user_id: str
        email: str | None
        plan: str  # "free" | "pro"
