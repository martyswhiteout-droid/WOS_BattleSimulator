"""Deployment-gate tests (gate.py, 2026-07-21): the Vercel-only guard —
10 requests/IP/day + 1,000-troop minimum — and, just as load-bearing, the
guarantee that LOCALHOST STAYS UNGATED (PRODUCTION_CRITERIA.md D1: the
prototype's micro-battles are essential; never port the limit back)."""
import pytest

from wos_sim.predictor import gate

try:
    import fastapi  # noqa: F401
    from fastapi.testclient import TestClient
    from wos_sim.predictor.server import app
    _HAS_FASTAPI = True
except Exception:                                     # fastapi/httpx absent
    _HAS_FASTAPI = False

pytestmark_endpoint = pytest.mark.skipif(not _HAS_FASTAPI,
                                         reason="fastapi not importable")


def _req(troops=2000, cls="Infantry"):
    side = {"role": "rally", "troops_total": troops,
            "formation_counts": {cls: troops},
            "quality": {cls: {"tier": 12, "fc": 10, "t12_stack": 0}}}
    enemy = dict(side, role="garrison")
    return {"own": side, "enemy": enemy, "n": 5, "seed": 0}


@pytest.fixture()
def client():
    if not _HAS_FASTAPI:
        pytest.skip("fastapi not importable")
    return TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_counts():
    gate._COUNTS.clear()
    yield
    gate._COUNTS.clear()


@pytestmark_endpoint
def test_localhost_default_is_ungated(client, monkeypatch):
    # no VERCEL / WOS_GATE env: a 1-troop lab request sails through the gate
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("WOS_GATE", raising=False)
    r = client.post("/api/predict", json=_req(troops=1))
    assert r.status_code == 200          # the gate did not interfere


@pytestmark_endpoint
def test_min_troops_rejected_when_gated(client, monkeypatch):
    monkeypatch.setenv("WOS_GATE", "1")
    r = client.post("/api/predict", json=_req(troops=999))
    assert r.status_code == 400
    assert r.json()["error"] == "below_min_troops"


@pytestmark_endpoint
def test_min_troops_boundary_passes(client, monkeypatch):
    monkeypatch.setenv("WOS_GATE", "1")
    r = client.post("/api/predict", json=_req(troops=1000))
    assert r.status_code == 200


@pytestmark_endpoint
def test_daily_limit_429_on_11th(client, monkeypatch):
    monkeypatch.setenv("WOS_GATE", "1")
    for i in range(10):
        assert client.post("/api/predict", json=_req()).status_code == 200, i
    r = client.post("/api/predict", json=_req())
    assert r.status_code == 429
    assert r.json()["error"] == "daily_limit_reached"


@pytestmark_endpoint
def test_limit_is_per_ip(client, monkeypatch):
    monkeypatch.setenv("WOS_GATE", "1")
    for _ in range(10):
        client.post("/api/predict", json=_req())
    # a different client IP (x-forwarded-for, as Vercel presents it) is fresh
    r = client.post("/api/predict", json=_req(),
                    headers={"x-forwarded-for": "203.0.113.7"})
    assert r.status_code == 200


@pytestmark_endpoint
def test_battle_endpoint_shares_the_gate(client, monkeypatch):
    monkeypatch.setenv("WOS_GATE", "1")
    body = _req(troops=500)
    body.pop("n")
    body["index"] = 0
    r = client.post("/api/battle", json=body)
    assert r.status_code == 400
    assert r.json()["error"] == "below_min_troops"


@pytestmark_endpoint
def test_env_overrides(client, monkeypatch):
    monkeypatch.setenv("WOS_GATE", "1")
    monkeypatch.setenv("WOS_GATE_MIN_TROOPS", "5000")
    r = client.post("/api/predict", json=_req(troops=2000))
    assert r.status_code == 400          # 2000 < the overridden 5000 floor

# ---- pure-python logic tests (no FastAPI needed; always run) ----------------

class _FakeReq:
    def __init__(self, ip="198.51.100.1", fwd=None):
        self.headers = {"x-forwarded-for": fwd} if fwd else {}
        self.client = type("C", (), {"host": ip})()


def _sides(troops):
    s = {"troops_total": troops, "formation_counts": {"Infantry": troops}}
    return s, dict(s)


def test_logic_inactive_by_default(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("WOS_GATE", raising=False)
    own, enemy = _sides(1)
    gate.check_gate(_FakeReq(), own, enemy)          # no raise: localhost lab


def test_logic_min_troops(monkeypatch):
    monkeypatch.setenv("WOS_GATE", "1")
    own, enemy = _sides(999)
    with pytest.raises(gate.GateReject) as e:
        gate.check_gate(_FakeReq(), own, enemy)
    assert e.value.status == 400 and e.value.error == "below_min_troops"


def test_logic_daily_limit_and_per_ip(monkeypatch):
    monkeypatch.setenv("WOS_GATE", "1")
    own, enemy = _sides(5000)
    for _ in range(10):
        gate.check_gate(_FakeReq(ip="10.0.0.9"), own, enemy)
    with pytest.raises(gate.GateReject) as e:
        gate.check_gate(_FakeReq(ip="10.0.0.9"), own, enemy)
    assert e.value.status == 429
    gate.check_gate(_FakeReq(fwd="203.0.113.7"), own, enemy)   # fresh IP passes


def test_logic_env_overrides(monkeypatch):
    monkeypatch.setenv("WOS_GATE", "1")
    monkeypatch.setenv("WOS_GATE_MIN_TROOPS", "5000")
    own, enemy = _sides(2000)
    with pytest.raises(gate.GateReject):
        gate.check_gate(_FakeReq(), own, enemy)

