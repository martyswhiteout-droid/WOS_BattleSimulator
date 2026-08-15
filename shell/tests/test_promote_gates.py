"""Tests for shell/promote.py static gates + the production write guard
(Agent D). Keyless. Covers PRODUCTION_CRITERIA E4 (secret scan), D4 (debug
endpoints), G2 (UTF-8), and the WOSTests.com write refusal."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SHELL_DIR = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "promote_under_test", SHELL_DIR / "promote.py")
promote = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = promote
spec.loader.exec_module(promote)


@pytest.fixture()
def bundle(tmp_path: Path) -> Path:
    d = tmp_path / "bundle"
    (d / "prototype").mkdir(parents=True)
    (d / "prototype" / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'>ok✓", encoding="utf-8")
    return d


# ------------------------------------------------------------- secret scan

def test_secret_scan_catches_planted_keys(bundle):
    (bundle / "config.py").write_text(
        'STRIPE = "sk_live_FAKEabcdef1234567890"\n'
        'WEBHOOK = "whsec_FAKE1234567890abcdefgh"\n'
        'ANTHROPIC = "sk-ant-FAKEapi03-abcdef1234567890"\n'
        '"service_role": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdef"\n',
        encoding="utf-8")
    findings = promote.gate_secret_scan(bundle)
    text = "\n".join(findings)
    assert len(findings) >= 3
    assert "stripe secret key" in text
    assert "stripe webhook secret" in text
    assert "anthropic/openai key" in text
    assert "service_role" in text


def test_secret_scan_ignores_placeholders_and_env_example(bundle):
    (bundle / ".env.example").write_text(
        "STRIPE_SECRET_KEY=sk_live_replace_me_1234567890\n"
        "SUPABASE_SERVICE_ROLE_KEY=\n", encoding="utf-8")
    (bundle / "readme.md").write_text(
        "Set STRIPE_SECRET_KEY (looks like sk_live_your_key_here_123).\n"
        "The SUPABASE_SERVICE_ROLE_KEY name itself is not a secret.\n",
        encoding="utf-8")
    assert promote.gate_secret_scan(bundle) == []


def test_secret_scan_catches_db_url_with_password(bundle):
    (bundle / "settings.py").write_text(
        'DB = "postgresql://app:SuperSecret42!@db.internal:5432/wos"\n',
        encoding="utf-8")
    assert any("db url" in f for f in promote.gate_secret_scan(bundle))


def test_secret_scan_catches_extension_less_and_pem_key_files(bundle):
    """F26: TEXT_EXTS used to omit extension-less files and .pem/.key/.crt/
    .sh, so a planted id_rsa or server.key would be invisible to the scan
    despite the private-key pattern being ready for it."""
    (bundle / "id_rsa").write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIFAKEnotarealkeybody\n"
        "-----END RSA PRIVATE KEY-----\n", encoding="utf-8")
    (bundle / "server.key").write_text(
        "-----BEGIN PRIVATE KEY-----\nMIIFAKEnotarealkeyeither\n"
        "-----END PRIVATE KEY-----\n", encoding="utf-8")
    findings = promote.gate_secret_scan(bundle)
    text = "\n".join(findings)
    assert "id_rsa" in text
    assert "server.key" in text


# --------------------------------------------------------- debug endpoints

def test_debug_endpoint_gate(bundle):
    (bundle / "server.py").write_text(
        '@app.get("/api/debug/turn_params")\n'
        "def leak(): return TURN_PARAMS\n", encoding="utf-8")
    findings = promote.gate_debug_endpoints(bundle)
    assert any("/api/debug" in f for f in findings)


def test_debug_gate_clean_on_normal_code(bundle):
    (bundle / "server.py").write_text(
        "def predict(req):\n    return run(req)  # no debugging here\n",
        encoding="utf-8")
    assert promote.gate_debug_endpoints(bundle) == []


# ------------------------------------------------------------------- UTF-8

def test_utf8_gate_rejects_mojibake(bundle):
    (bundle / "prototype" / "index.html").write_bytes(
        b"<!doctype html>\xff\xfe broken \x93quotes\x94")
    assert promote.gate_utf8_index(bundle)


def test_utf8_gate_passes_valid_file(bundle):
    assert promote.gate_utf8_index(bundle) == []


def test_utf8_gate_flags_missing_index(tmp_path):
    assert promote.gate_utf8_index(tmp_path / "empty")


# ------------------------------------------- the production write guard

def test_write_guard_refuses_production_folder(tmp_path):
    prod_like = tmp_path / "WOSTests.com" / "release"
    with pytest.raises(promote.PromoteRefusal):
        promote.assert_safe_write_path(prod_like)


def test_write_guard_allows_normal_paths(tmp_path):
    assert promote.assert_safe_write_path(tmp_path / "build")
