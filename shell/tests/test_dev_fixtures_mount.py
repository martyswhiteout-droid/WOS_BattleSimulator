"""The DEV-ONLY fixture-image mount (/shell/ocr/dev-fixtures/).

Owner mandate 2026-09-06: the upload screen's L/R toggle ("read the Left /
Right column of this battle report") must be verified end-to-end with REAL
reads, not just at the seam. The browser can't reach shell/tests/fixtures/
on its own, so shell/app/main.py mounts the fixture images read-only — but
ONLY when the Settings object's ENV is "dev", the same fail-closed rule the
panel mock uses (panel_router._mock_enabled). A staging/prod build must never
serve those screenshots (Century Games IP; PRODUCTION_CRITERIA F1).
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from fastapi.testclient import TestClient

from shell.app.config import Settings
from shell.app.main import create_app


@pytest.fixture(autouse=True)
def _fresh_limits_state():
    try:
        from shell.app import db as _db
        _db.reset_db()
    except Exception:
        pass
    yield


def _client(env: str) -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True, ENV=env, IP_HASH_SALT="x")))


def test_dev_serves_fixture_battle_report():
    resp = _client("dev").get("/shell/ocr/dev-fixtures/C_battle_1.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("env", ["staging", "prod", " ", "DEV "])
def test_non_dev_never_mounts_fixtures(env):
    # "DEV " with trailing space is deliberately dev after strip — assert the
    # strip/lower rule matches the mock's; everything else must 404.
    resp = _client(env).get("/shell/ocr/dev-fixtures/C_battle_1.png")
    if env.strip().lower() == "dev":
        assert resp.status_code == 200
    else:
        assert resp.status_code == 404
