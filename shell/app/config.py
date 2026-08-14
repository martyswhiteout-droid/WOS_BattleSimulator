"""shell/app/config.py — production-shell settings (Agent A).

Implements PRODUCTION_PLAN.md §2 / §2.4 and the "config.py keys" contract in
shell/ARCHITECTURE.md. Every key is optional with a dev-safe default so the
whole shell boots and tests KEYLESS (mock-first rule). Real keys, provided as
environment variables (or a .env file in the working directory), activate the
real integrations — no code change required.

Conditional default: DEV_BYPASS is auto-True when no CLERK_SECRET_KEY is
configured (use the ``dev_bypass`` property, never the raw field).
"""
from __future__ import annotations

import base64
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every env key from shell/ARCHITECTURE.md, exactly. All optional."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- mode ------------------------------------------------------------
    ENV: str = "dev"                       # dev | staging | prod
    DEV_BYPASS: bool | None = None         # None => auto (True iff no CLERK_SECRET_KEY)
    BASE_URL: str = "http://localhost:8200"

    # --- Clerk (auth; verified server-side via JWKS) ----------------------
    CLERK_PUBLISHABLE_KEY: str | None = None
    CLERK_SECRET_KEY: str | None = None
    CLERK_JWKS_URL: str | None = None      # derived from the publishable key if unset

    # --- Supabase Postgres (Agent B's db.py is the only client) -----------
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    DATABASE_URL: str | None = None

    # --- Stripe (Agent B's billing/) --------------------------------------
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_PRICE_ID_PRO: str | None = None

    # --- OCR (Agent C's ocr/) ---------------------------------------------
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OCR_MOCK: bool = True                  # mock-first: real vision calls are opt-in

    # --- OCR engine ladder (shell/app/ocr/panel/ladder.py) ----------------
    OCR_CPU_CONCURRENCY: int = 2           # concurrent RapidOCR executions (VPS cores)
    GEMINI_OCR_DAILY_BUDGET: int = 1200    # hard daily cap on Gemini gap-fill calls
    OCR_VISION_MODEL: str = "claude-sonnet-4-5"   # Agent C's ocr/vision.py + _shims.py
    OCR_MOCK_FIXTURE: str | None = None           # Agent C's ocr/vision.py MockVision

    # --- production limits (enforced by Agent B's limits.py; defaults here
    #     are the single source for keyless/dev fallbacks) ------------------
    MIN_TROOPS_PER_SIDE: int = 5000
    FREE_SIMS_PER_DAY: int = 5
    PRO_SIMS_PER_DAY: int = 100
    PRO_OCR_PER_DAY: int = 30
    BURST_PER_MIN: int = 5
    GLOBAL_CONCURRENCY: int = 8
    SWEEP_MIN_EVENTS: int = 20              # Agent B's limits.sweep_scan threshold

    # --- privacy (Agent B's limits.hash_ip) --------------------------------
    # F11 (EVAL_ROUND_1.md): an UNSALTED sha256(ip) is a 2**32-entry rainbow
    # table — minutes to reverse. Empty by default (dev-safe, matches every
    # other key here); create_app() in main.py refuses to boot when this is
    # empty AND settings.is_prodlike, so an empty salt can never reach real
    # traffic silently. Never set to a short/guessable value in prod.
    IP_HASH_SALT: str = ""

    # --- security / transport -----------------------------------------------
    MAX_BODY_BYTES: int = 262_144           # 256 KiB; mirrors shell/Caddyfile's cap

    # --- derived helpers (properties, not env keys) -----------------------

    @property
    def dev_bypass(self) -> bool:
        """DEV_BYPASS with its conditional default: explicitly set wins;
        otherwise True exactly when no Clerk secret key is configured."""
        if self.DEV_BYPASS is not None:
            return self.DEV_BYPASS
        return not self.CLERK_SECRET_KEY

    @property
    def is_prodlike(self) -> bool:
        return self.ENV.lower() in ("staging", "prod")

    @property
    def clerk_frontend_api(self) -> str | None:
        """Frontend-API domain decoded from the publishable key
        (``pk_test_<b64(domain$)>`` / ``pk_live_<b64(domain$)>``)."""
        key = self.CLERK_PUBLISHABLE_KEY or ""
        for prefix in ("pk_test_", "pk_live_"):
            if key.startswith(prefix):
                blob = key[len(prefix):]
                try:
                    pad = "=" * (-len(blob) % 4)
                    domain = base64.b64decode(blob + pad).decode("utf-8")
                except Exception:
                    return None
                return domain.rstrip("$") or None
        return None

    @property
    def jwks_url(self) -> str | None:
        """CLERK_JWKS_URL, or the standard well-known URL on the frontend API."""
        if self.CLERK_JWKS_URL:
            return self.CLERK_JWKS_URL
        fapi = self.clerk_frontend_api
        return f"https://{fapi}/.well-known/jwks.json" if fapi else None

    @property
    def sign_in_url(self) -> str:
        """Clerk hosted Account Portal sign-in page, derived from the
        publishable key (dev instances: ``x.clerk.accounts.dev`` →
        ``x.accounts.dev``; prod: ``clerk.example.com`` →
        ``accounts.example.com``). Keyless fallback: BASE_URL/sign-in
        (a dead-end placeholder — fine, because keyless implies DEV_BYPASS)."""
        fapi = self.clerk_frontend_api
        if fapi:
            if fapi.endswith(".clerk.accounts.dev"):
                portal = fapi[: -len(".clerk.accounts.dev")] + ".accounts.dev"
            elif fapi.startswith("clerk."):
                portal = "accounts." + fapi[len("clerk."):]
            else:
                portal = fapi
            return f"https://{portal}/sign-in"
        return self.BASE_URL.rstrip("/") + "/sign-in"


# Lowercase read-only aliases (settings.min_troops_per_side etc.): the
# shared-contract text in shell/ARCHITECTURE.md references the lowercase
# forms, and Agents B/C coded against a lowercase stub before this file
# landed. DEV_BYPASS is excluded — its lowercase form is the conditional-
# default property above.
def _alias(field_name: str) -> property:
    return property(lambda self: getattr(self, field_name))


for _key in ("ENV", "BASE_URL", "CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY",
             "CLERK_JWKS_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
             "DATABASE_URL", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
             "STRIPE_PRICE_ID_PRO", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
             "OCR_MOCK", "OCR_CPU_CONCURRENCY", "GEMINI_OCR_DAILY_BUDGET",
             "OCR_VISION_MODEL", "OCR_MOCK_FIXTURE",
             "MIN_TROOPS_PER_SIDE", "FREE_SIMS_PER_DAY",
             "PRO_SIMS_PER_DAY", "PRO_OCR_PER_DAY", "BURST_PER_MIN",
             "GLOBAL_CONCURRENCY", "SWEEP_MIN_EVENTS", "IP_HASH_SALT",
             "MAX_BODY_BYTES"):
    setattr(Settings, _key.lower(), _alias(_key))


@lru_cache()
def get_settings() -> Settings:
    """Process-wide settings singleton (tests build their own Settings and
    pass them to ``main.create_app`` instead of mutating this cache)."""
    return Settings()
