"""Tests for shell/app/config.py's env-key completeness + boot refusal
(Agent A) — keyless.

F11 (EVAL_ROUND_1.md): IP_HASH_SALT, SWEEP_MIN_EVENTS, OCR_VISION_MODEL, and
OCR_MOCK_FIXTURE were read by Agent B/C modules (via os.environ or the
settings_extra() fallback) but never declared in config.py or .env.example —
"config.py carries every env key" (shell/ARCHITECTURE.md) did not hold. Also
covers the fail-fast boot refusal in shell/app/main.py:create_app when
IP_HASH_SALT is empty in a staging/prod environment.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from shell.app.config import Settings
from shell.app.main import create_app


# --------------------------------------------------------------- key coverage

def test_settings_declares_previously_missing_keys():
    s = Settings(_env_file=None)
    assert s.IP_HASH_SALT == ""
    assert s.SWEEP_MIN_EVENTS == 20
    assert s.OCR_VISION_MODEL == "claude-sonnet-4-5"
    assert s.OCR_MOCK_FIXTURE is None
    assert s.MAX_BODY_BYTES == 262_144


def test_lowercase_aliases_match_the_architecture_md_contract_casing():
    s = Settings(_env_file=None, IP_HASH_SALT="x", SWEEP_MIN_EVENTS=7)
    assert s.ip_hash_salt == "x"
    assert s.sweep_min_events == 7
    assert s.ocr_vision_model == s.OCR_VISION_MODEL
    assert s.max_body_bytes == s.MAX_BODY_BYTES


def test_env_example_documents_the_same_keys():
    text = (_REPO_ROOT / "shell" / ".env.example").read_text(encoding="utf-8")
    for key in ("IP_HASH_SALT", "SWEEP_MIN_EVENTS", "OCR_VISION_MODEL",
                "OCR_MOCK_FIXTURE", "MAX_BODY_BYTES"):
        assert key in text, f"{key} missing from shell/.env.example"


# --------------------------------------------------------- boot-refusal gate

def test_boot_refuses_when_staging_and_salt_empty():
    settings = Settings(_env_file=None, ENV="staging", IP_HASH_SALT="")
    with pytest.raises(RuntimeError, match="IP_HASH_SALT"):
        create_app(settings)


def test_boot_refuses_when_prod_and_salt_empty():
    settings = Settings(_env_file=None, ENV="prod", IP_HASH_SALT="")
    with pytest.raises(RuntimeError, match="IP_HASH_SALT"):
        create_app(settings)


def test_boot_refuses_even_under_dev_bypass_in_staging():
    """DEV_BYPASS is an escape hatch for AUTH, never for this privacy
    control — a misconfigured "staging with bypass on" must still refuse."""
    settings = Settings(_env_file=None, ENV="staging", DEV_BYPASS=True, IP_HASH_SALT="")
    with pytest.raises(RuntimeError, match="IP_HASH_SALT"):
        create_app(settings)


def test_boot_succeeds_when_staging_and_salt_present():
    settings = Settings(_env_file=None, ENV="staging", DEV_BYPASS=True,
                         IP_HASH_SALT="a-long-random-value")
    assert create_app(settings) is not None


def test_boot_never_blocked_in_dev_even_with_empty_salt():
    settings = Settings(_env_file=None, ENV="dev", IP_HASH_SALT="")
    assert create_app(settings) is not None
