"""Layer 3 — JSON <-> profile, and forecast -> JSON for the front-end."""
import json
import unittest

from wos_sim.predictor.profiles import SideProfile
from wos_sim.predictor import api, serialize


class TestProfileFromDict(unittest.TestCase):
    def test_parses_core_fields_and_pipe_panel_keys(self):
        d = {"role": "rally", "troops_total": 1_500_000, "stats_mode": "scouted",
             "formation": {"Infantry": 0.5, "Lancer": 0.2, "Marksman": 0.3},
             "quality": {"Infantry": {"tier": 11, "fc": 9, "t12_stack": 0}},
             "panel": {"Infantry|Attack": 9.0},
             "panel_is_final": True,
             "widgets_in_panel": False,
             "lead_heroes": {"Infantry": "Gregory"}, "joiners": ["Jessie"]}
        p = serialize.profile_from_dict(d)
        self.assertEqual(p.role, "rally")
        self.assertEqual(p.troops_total, 1_500_000)
        self.assertEqual(p.quality["Infantry"].tier, 11)
        self.assertEqual(p.quality["Infantry"].fc, 9)
        self.assertEqual(p.panel[("Infantry", "Attack")], 9.0)   # "Class|Stat" -> tuple key
        self.assertTrue(p.panel_is_final)
        self.assertFalse(p.widgets_in_panel)
        self.assertEqual(p.joiners, ["Jessie"])


class TestForecastToDict(unittest.TestCase):
    def test_json_serializable_with_expected_shape(self):
        own = SideProfile(role="rally", panel={("Infantry", "Attack"): 5.0},
                          formation={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0})
        enemy = SideProfile(role="garrison",
                            formation={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0})
        d = serialize.forecast_to_dict(api.predict(own, enemy, n=50, seed=1))
        json.dumps(d)   # must be JSON-serializable end to end
        self.assertEqual(d["n"], 50)
        self.assertIn("win", d["verdict"])
        self.assertIn("p", d["verdict"]["win"])
        self.assertEqual(len(d["outcome_quality"]), 8)
        self.assertIn("counts", d["army_losses"]["own"])
        self.assertIn("Infantry", d["class_losses"])
        self.assertIn("engine", d)                     # confidence block for the honesty banner
        self.assertIn("path", d["engine"])
        self.assertIn("model_error", d["engine"])
        self.assertIn("stochastic", d["engine"])


if __name__ == "__main__":
    unittest.main()
