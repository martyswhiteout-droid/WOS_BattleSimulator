"""Tests for shell/app/main.py's docs-guard middleware (Agent A) — keyless.

F5 (EVAL_ROUND_1.md): the SHELL app's own FastAPI instance already sets
docs_url=None/redoc_url=None/openapi_url=None (unconditionally), but it
mounts wos_sim.predictor.server:app at "/" (main.py:~237) and THAT app sets
no such override, so its /docs, /redoc, /openapi.json were reachable through
the mount in every environment, including staging/prod, while promote.py's
gate reported "debug endpoints: clean" (a false negative). wos_sim/ is a
READ-ONLY import (shell/ARCHITECTURE.md boundary rule 1) so this is fixed at
the shell boundary, not by editing the sub-app.
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


def _client(env):
    # IP_HASH_SALT: F11's fail-fast refuses to boot staging/prod without it;
    # this value is test-only, not a secret.
    return TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True, ENV=env,
                                          IP_HASH_SALT="test-only-salt")))


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_blocked_in_staging(path):
    resp = _client("staging").get(path)
    assert resp.status_code == 404


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_blocked_in_prod(path):
    resp = _client("prod").get(path)
    assert resp.status_code == 404


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_reachable_in_dev(path):
    """Dev convenience is preserved -- only staging/prod are locked down."""
    resp = _client("dev").get(path)
    assert resp.status_code == 200


def test_shells_own_docs_urls_stay_disabled_regardless_of_env():
    """The shell's OWN FastAPI instance never registers docs routes at all
    (docs_url=None etc., unconditional) -- both apps are covered."""
    app = create_app(Settings(_env_file=None, DEV_BYPASS=True, ENV="dev"))
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
