"""Tests for shell/app/minimize.py (Agent A) — keyless.

Unit coverage of the transforms plus end-to-end proof that ENV=staging strips
kill matrices / debug keys and bands survivor counts to the nearest 100 while
leaving the verdict probabilities and the coin_flip/honesty labels untouched
(COMPASS invariant 3), and that ENV=dev is a byte-honest pass-through.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from fastapi.testclient import TestClient

from shell.app import minimize
from shell.app.config import Settings
from shell.app.main import create_app


# ------------------------------------------------------------------- units

def test_strip_debug_removes_nested_debug_keys():
    tree = {"a": 1, "a_debug": {"x": 1}, "debug": 2,
            "nested": [{"keep": True, "turn_debug": []}]}
    out = minimize.strip_debug(tree)
    assert out == {"a": 1, "nested": [{"keep": True}]}


def test_band_timeline_bands_counts_not_turns():
    tl = {"turns": [1, 2, 3], "own_survivors": [123456.7, 99.9, 49.0],
          "enemy_killed": [151.0, 0.0, 250.0],
          "by_class": {"Infantry": {"own": [1049.0], "own_dealt": [777.0]}},
          "truncated": False}
    out = minimize.band_timeline(tl)
    assert out["own_survivors"] == [123500, 100, 0]
    assert out["enemy_killed"] == [200, 0, 200]     # banker's rounding on .5*100
    assert out["by_class"]["Infantry"]["own"] == [1000]
    assert out["by_class"]["Infantry"]["own_dealt"] == [800]
    assert out["turns"] == [1, 2, 3]                # never banded
    assert out["truncated"] is False


def test_minimize_battle_drops_kill_matrix_keeps_procs():
    payload = {"index": 0, "turns": [1], "own_survivors": [123.0],
               "enemy_survivors": [456.0], "own_killed": [1.0],
               "enemy_killed": [2.0], "by_class": {},
               "procs": [[{"name": "Positional Battler", "kills": 3}]],
               "kill_matrix": {"own": [], "enemy": []}}
    out = minimize.minimize_battle(payload)
    assert "kill_matrix" not in out
    assert out["procs"] == payload["procs"]         # user-facing: untouched
    assert out["own_survivors"] == [100]


def test_minimize_predict_preserves_verdict_and_honesty_labels():
    payload = {
        "n": 10,
        "engine": {"path": "turn", "calibrated": False, "model_error": 0.13,
                   "note": "coin flip note", "near_even": True,
                   "confidence": "coin_flip", "stochastic": True,
                   "severe_fraction": 0.35},
        "verdict": {"win": {"p": 0.5123, "se": 0.01}},
        "internal_debug": {"secret": 1},
        "battle_timeline": {"turns": [1], "own_survivors": [1234.0]},
    }
    out = minimize.minimize_predict(payload)
    assert out["engine"] == payload["engine"]           # labels NEVER touched
    assert out["verdict"]["win"]["p"] == 0.5123          # probability untouched
    assert "internal_debug" not in out
    assert out["battle_timeline"]["own_survivors"] == [1200]


# -------------------------------------------------------------- end to end

@pytest.fixture(autouse=True)
def _fresh_limits_state():
    """Reset Agent B's process-global in-memory quota/burst store per test."""
    try:
        from shell.app import db as _db
        _db.reset_db()
    except Exception:
        pass
    yield


@pytest.fixture(scope="module")
def scenario():
    data = json.loads((_REPO_ROOT / "Scenarios" / "Scenario_1.json")
                      .read_text(encoding="utf-8"))
    return {"own": data["own"], "enemy": data["enemy"]}


@pytest.fixture(scope="module")
def dev_client():
    return TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True, ENV="dev")))


@pytest.fixture(scope="module")
def staging_client():
    return TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True, ENV="staging")))


def _all_banded(seq):
    return all(isinstance(v, int) and v % 100 == 0 for v in seq)


def test_staging_battle_is_minimized(staging_client, scenario):
    body = staging_client.post("/api/battle",
                               json={**scenario, "seed": 1, "index": 0}).json()
    assert "kill_matrix" not in body
    assert _all_banded(body["own_survivors"])
    assert _all_banded(body["enemy_survivors"])
    for sides in body["by_class"].values():
        assert _all_banded(sides["own"])
    assert "procs" in body                       # user-facing telemetry stays


def test_dev_battle_passthrough_keeps_kill_matrix(dev_client, scenario):
    body = dev_client.post("/api/battle",
                           json={**scenario, "seed": 1, "index": 0}).json()
    assert "kill_matrix" in body                 # dev env: untouched


def test_staging_predict_bands_timeline_but_not_verdict(dev_client, staging_client,
                                                        scenario):
    req = {**scenario, "n": 20, "seed": 1}
    dev = dev_client.post("/api/predict", json=req).json()
    stg = staging_client.post("/api/predict", json=req).json()
    # identical CRN-seeded run -> verdict and honesty labels must be identical
    assert stg["verdict"] == dev["verdict"]
    assert stg["engine"] == dev["engine"]        # incl. near_even/confidence/note
    assert stg["outcome_quality"] == dev["outcome_quality"]
    assert stg["army_losses"] == dev["army_losses"]   # % distributions: not banded
    tl = stg.get("battle_timeline")
    if tl is not None:                           # turn engine emits one by default
        assert _all_banded(tl["own_survivors"])
        assert _all_banded(tl["enemy_survivors"])
