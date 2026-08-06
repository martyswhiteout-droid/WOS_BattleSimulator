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
from typing import Any, Protocol, runtime_checkable


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@runtime_checkable
class SettingsLike(Protocol):
    """Minimal settings surface the OCR module needs (ARCHITECTURE.md config keys)."""

    dev_bypass: bool
    anthropic_api_key: str | None
    ocr_mock: bool
    base_url: str


@dataclass
class _StubSettings:
    """Local fallback until Agent A's shell.app.config lands. Env-driven, dev defaults."""

    dev_bypass: bool = True
    anthropic_api_key: str | None = None
    ocr_mock: bool = False
    base_url: str = "http://localhost:8200"
    # OCR-specific knobs (not in the shared contract list; Agent A may adopt them).
    ocr_vision_model: str = "claude-sonnet-4-5"
    ocr_mock_fixture: str | None = None


def _stub_from_env() -> _StubSettings:
    return _StubSettings(
        dev_bypass=_env_bool("DEV_BYPASS", True),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        ocr_mock=_env_bool("OCR_MOCK", False),
        base_url=os.environ.get("BASE_URL", "http://localhost:8200"),
        ocr_vision_model=os.environ.get("OCR_VISION_MODEL", "claude-sonnet-4-5"),
        ocr_mock_fixture=os.environ.get("OCR_MOCK_FIXTURE") or None,
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
