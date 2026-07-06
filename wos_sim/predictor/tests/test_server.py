"""Layer 3 — the FastAPI predict endpoint.

Skips cleanly when fastapi/uvicorn aren't installed (e.g. the engine env), so it
never breaks test collection there — the other predictor tests are dep-free.
"""
import unittest

try:
    from fastapi.testclient import TestClient
    from wos_sim.models import TroopType
    from wos_sim.predictor import server, summary
    from wos_sim.predictor.kernel import RunRecord
    from wos_sim.predictor.server import app
    client = TestClient(app)
    _HAS_FASTAPI = True
except Exception:
    client = None
    _HAS_FASTAPI = False

_FLAT = {"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0}   # pure-infantry -> deterministic, fast


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/uvicorn not installed")
class TestServer(unittest.TestCase):
    def test_health(self):
        r = client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_predict_returns_forecast_json(self):
        body = {
            "own": {"role": "rally", "troops_total": 1_000_000, "formation": _FLAT,
                    "panel": {"Infantry|Attack": 5.0}, "joiners": ["Seo-yoon"]},
            "enemy": {"role": "garrison", "troops_total": 1_000_000, "formation": _FLAT},
            "n": 10, "seed": 1,
        }
        r = client.post("/api/predict", json=body)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["n"], 10)
        self.assertIn("win", d["verdict"])
        self.assertEqual(len(d["outcome_quality"]), 8)
        self.assertIn("own", d["army_losses"])

    def test_bad_profile_returns_clean_400_not_500(self):
        body = {
            "own": {"role": "rally", "troops_total": 0, "formation": _FLAT},   # 0 troops -> invalid
            "enemy": {"role": "garrison", "formation": _FLAT},
            "n": 10, "seed": 1,
        }
        r = client.post("/api/predict", json=body)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "invalid_input")
        self.assertTrue(any("troops" in p.lower() for p in r.json()["problems"]))

    def test_predict_rejects_runs_above_ceiling(self):
        body = {
            "own": {"role": "rally", "troops_total": 1_000, "formation": _FLAT},
            "enemy": {"role": "garrison", "troops_total": 1_000, "formation": _FLAT},
            "n": server.MAX_RUNS + 1, "seed": 1,
        }
        r = client.post("/api/predict", json=body)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "invalid_input")
        self.assertTrue(any(f"{server.MAX_RUNS:,}" in p for p in r.json()["problems"]))

    def test_predict_defaults_to_default_runs(self):
        captured = {}
        old_predict = server.api.predict
        try:
            def fake_predict(*args, **kwargs):
                captured["n"] = kwargs["n"]
                return summary.summarize([RunRecord(
                    winner="A", turns=1,
                    attacker_start={TroopType.INFANTRY: 10},
                    defender_start={TroopType.INFANTRY: 10},
                    attacker_incap={TroopType.INFANTRY: 0},
                    defender_incap={TroopType.INFANTRY: 10},
                )], own_is_attacker=True)
            server.api.predict = fake_predict
            body = {
                "own": {"role": "rally", "troops_total": 1_000, "formation": _FLAT},
                "enemy": {"role": "garrison", "troops_total": 1_000, "formation": _FLAT},
            }
            r = client.post("/api/predict", json=body)
        finally:
            server.api.predict = old_predict
        self.assertEqual(r.status_code, 200)
        self.assertEqual(captured["n"], server.DEFAULT_RUNS)
        self.assertEqual(r.json()["n"], 1)

    def test_predict_enables_turn_engine_telemetry(self):
        captured = {}
        old_predict = server.api.predict
        try:
            def fake_predict(*args, **kwargs):
                captured["params"] = kwargs.get("params")
                return summary.summarize([RunRecord(
                    winner="A", turns=1,
                    attacker_start={TroopType.INFANTRY: 10},
                    defender_start={TroopType.INFANTRY: 10},
                    attacker_incap={TroopType.INFANTRY: 0},
                    defender_incap={TroopType.INFANTRY: 10},
                )], own_is_attacker=True)
            server.api.predict = fake_predict
            body = {
                "own": {"role": "rally", "troops_total": 1_000, "formation": _FLAT},
                "enemy": {"role": "garrison", "troops_total": 1_000, "formation": _FLAT},
                "n": 1, "seed": 1,
            }
            r = client.post("/api/predict", json=body)
        finally:
            server.api.predict = old_predict
        self.assertEqual(r.status_code, 200)
        self.assertEqual(captured["params"], server.TELEMETRY_ENGINE_PARAMS)

    def test_predict_serializes_skill_telemetry_for_frontend(self):
        rec = RunRecord(
            winner="A", turns=10,
            attacker_start={TroopType.INFANTRY: 100, TroopType.LANCER: 100},
            defender_start={TroopType.INFANTRY: 100, TroopType.LANCER: 100},
            attacker_incap={TroopType.INFANTRY: 10, TroopType.LANCER: 20},
            defender_incap={TroopType.INFANTRY: 30, TroopType.LANCER: 40},
            skill_telemetry={
                "attacker": {
                    "heroes": [
                        {"hero": "Elif", "role": "captain", "troop": "Infantry",
                         "skills": [{"slot": "skill_1", "triggers": 1, "kills": 0}]},
                        {"hero": "Dominic", "role": "captain", "troop": "Lancer",
                         "skills": [{"slot": "skill_1", "triggers": 1, "kills": 0}]},
                        {"hero": "Flora", "role": "joiner", "troop": None,
                         "skills": [{"slot": "skill_1", "triggers": 3, "kills": 25}]},
                    ],
                    "troop_skills": [
                        {"name": "Incandescent Field II", "troop": "Lancer",
                         "triggers": 4, "kills": 0},
                    ],
                },
                "defender": {"heroes": [], "troop_skills": []},
            },
        )
        forecast = summary.summarize([rec], own_is_attacker=True)
        old_predict = server.api.predict
        try:
            server.api.predict = lambda *args, **kwargs: forecast
            body = {
                "own": {"role": "rally", "troops_total": 100, "formation": _FLAT},
                "enemy": {"role": "garrison", "troops_total": 100, "formation": _FLAT},
                "n": 1, "seed": 9,
            }
            r = client.post("/api/predict", json=body)
        finally:
            server.api.predict = old_predict

        self.assertEqual(r.status_code, 200)
        tel = r.json()["skill_telemetry"]["own"]
        lancer = next(row for row in tel if row["hero"] == "Dominic")
        troop_skill = next(s for s in lancer["skills"] if s["source"] == "troop")
        self.assertEqual(troop_skill["name"], "Incandescent Field")
        self.assertEqual(troop_skill["troop"], "Lancer")
        self.assertEqual(troop_skill["icon"], "assets/troop_skills/Incandescent Field.png")
        self.assertIn("15% chance", troop_skill["effect"])
        self.assertEqual(troop_skill["triggers"]["median"], 4.0)
        self.assertEqual(troop_skill["kills"]["median"], 0.0)

        joiner = next(row for row in tel if row["role"] == "joiner")
        self.assertEqual(joiner["hero"], "Flora")
        self.assertEqual(len(joiner["skills"]), 1)
        self.assertEqual(joiner["skills"][0]["source"], "hero")

    def test_skill_display_assets_are_served_by_static_mount(self):
        bundle = client.get("/assets/skill_display.js")
        self.assertEqual(bundle.status_code, 200)
        self.assertIn("HERO_SKILL_DISPLAY", bundle.text)
        self.assertIn("TROOP_SKILL_DISPLAY", bundle.text)
        self.assertIn("Incandescent Field", bundle.text)

        icon = client.get("/assets/troop_skills/Incandescent%20Field.png")
        self.assertEqual(icon.status_code, 200)
        self.assertTrue(icon.content.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
