"""shell/app/billing/_contracts.py — shared-contract shims (Agent B).

Purpose: give Agent B's modules (db.py, limits.py, billing/*) a single,
stable import point for UserCtx and Settings per shell/ARCHITECTURE.md
§"Shared contracts", regardless of whether Agent A's shell/app/auth.py and
shell/app/config.py have landed.

Resolution:
  * UserCtx  — re-exported from shell.app.auth when present; else a local
    dataclass matching the contract field-for-field.
  * Settings — Agent A's config.py declares fields in UPPERCASE env-key form
    (ENV, MIN_TROOPS_PER_SIDE, ...) while the ARCHITECTURE contract snippet
    reads them lowercase (settings.min_troops_per_side). SettingsView bridges
    both casings, so Agent B code follows the contract verbatim and still
    binds to Agent A's real Settings.
  * get_settings() here builds a FRESH Settings each call (Agent A's is
    lru_cached): env changes are picked up immediately, which keyless tests
    rely on. Cheap — pydantic-settings construction is microseconds.

All Agent B code imports these names from THIS module only.
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------
# UserCtx — contract: auth.py provides (Agent A)
# --------------------------------------------------------------------------
try:
    from shell.app.auth import UserCtx  # type: ignore[no-redef]
except Exception:  # pragma: no cover - only on a pre-Agent-A tree

    @dataclass
    class UserCtx:  # type: ignore[no-redef]
        """Authenticated request identity (contract copy from ARCHITECTURE.md)."""

        user_id: str  # clerk_user_id or "dev_user"
        email: str | None = None
        plan: str = "free"  # "free" | "pro"


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
_RealSettings = None
try:
    from shell.app.config import Settings as _RealSettings  # type: ignore
except Exception:  # pragma: no cover - only on a pre-Agent-A tree
    _RealSettings = None


class SettingsView:
    """Read-only case-bridging proxy over a Settings instance.

    Attribute lookup tries the exact name, then UPPERCASE, then lowercase —
    so ``view.min_troops_per_side`` hits config.py's ``MIN_TROOPS_PER_SIDE``
    and ``view.dev_bypass`` hits its property. Missing names raise
    AttributeError so ``getattr(view, name, default)`` behaves normally.
    """

    __slots__ = ("_inner",)

    def __init__(self, inner) -> None:
        object.__setattr__(self, "_inner", inner)

    def __getattr__(self, name: str):
        inner = object.__getattribute__(self, "_inner")
        for candidate in (name, name.upper(), name.lower()):
            if hasattr(inner, candidate):
                return getattr(inner, candidate)
        raise AttributeError(name)

    def __repr__(self) -> str:  # pragma: no cover - debugging nicety
        return f"SettingsView({object.__getattribute__(self, '_inner')!r})"


if _RealSettings is not None:
    Settings = _RealSettings  # re-export for callers that want the real class

    def get_settings() -> SettingsView:
        """Fresh, case-bridged settings (see module docstring)."""
        return SettingsView(_RealSettings())

else:  # pragma: no cover - stub branch for a pre-Agent-A tree
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):  # type: ignore[no-redef]
        """Env-driven settings stub matching ARCHITECTURE.md config keys."""

        model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

        dev_bypass: bool = False
        env: str = "dev"  # dev | staging | prod

        clerk_publishable_key: str | None = None
        clerk_secret_key: str | None = None
        clerk_jwks_url: str | None = None

        supabase_url: str | None = None
        supabase_service_role_key: str | None = None
        database_url: str | None = None

        stripe_secret_key: str | None = None
        stripe_webhook_secret: str | None = None
        stripe_price_id_pro: str | None = None

        anthropic_api_key: str | None = None
        gemini_api_key: str | None = None
        ocr_mock: bool = False

        min_troops_per_side: int = 5000
        free_sims_per_day: int = 5
        pro_sims_per_day: int = 100
        pro_ocr_per_day: int = 30
        burst_per_min: int = 5
        global_concurrency: int = 8

        base_url: str = "http://localhost:8200"

    def get_settings() -> SettingsView:  # type: ignore[no-redef]
        return SettingsView(Settings())


def settings_extra(settings: object, name: str, default):
    """Read an Agent-B-specific knob (IP_HASH_SALT, SWEEP_MIN_EVENTS) that
    Agent A's Settings does not define: attribute first, env var second."""
    import os

    val = getattr(settings, name, None)
    if val is not None:
        return val
    raw = os.environ.get(name.upper())
    if raw is None:
        return default
    try:
        return type(default)(raw)
    except (TypeError, ValueError):
        return default


__all__ = ["UserCtx", "Settings", "SettingsView", "get_settings", "settings_extra"]
