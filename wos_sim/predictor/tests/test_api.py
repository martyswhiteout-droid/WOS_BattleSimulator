"""End-to-end: profiles -> construct -> batch -> summary."""
import unittest

from wos_sim.models import StatType, TroopType
from wos_sim.predictor.profiles import CLASSES, STATS, SideProfile
from wos_sim.predictor import api
from wos_sim.predictor.kernel import RunRecord
from wos_sim.troop_catalog import troop_base_stats


class TestPredict(unittest.TestCase):
    def _sides(self):
        panel = {(c, s): 10.0 for c in CLASSES for s in STATS}
        own = SideProfile(role="rally", troops_total=1_000_000, panel=dict(panel),
                          own_buffs={"Attack": 0.20, "Lethality": 0.12})
        enemy = SideProfile(role="garrison", troops_total=1_000_000, panel=dict(panel))
        return own, enemy

    def test_predict_runs_end_to_end(self):
        own, enemy = self._sides()
        fc = api.predict(own, enemy, n=50, seed=3)
        self.assertEqual(fc.n, 50)
        self.assertTrue(0.0 <= fc.p_win.p <= 1.0)
        self.assertEqual(sum(fc.outcome_quality.values()), 50)
        self.assertEqual(sum(fc.army_losses['own'].counts), 50)

    def test_predict_is_reproducible(self):
        own, enemy = self._sides()
        a = api.predict(own, enemy, n=40, seed=9)
        b = api.predict(own, enemy, n=40, seed=9)
        self.assertEqual(a.p_win.p, b.p_win.p)
        self.assertEqual(a.outcome_quality, b.outcome_quality)

    def test_predict_carries_engine_confidence_from_meta(self):
        own, enemy = self._sides()
        fc = api.predict(own, enemy, n=30, seed=2)
        self.assertIn(fc.engine_path, ("general", "pvp_kernel"))
        self.assertGreater(fc.engine_model_error, 0.0)          # real per-matchup band, not hardcoded
        self.assertIsInstance(fc.stochastic, bool)
        self.assertTrue(fc.engine_note)

    def test_turn_engine_uses_final_panel_without_legacy_skill_adjustments(self):
        panel = {(c, s): 0.0 for c in CLASSES for s in STATS}
        panel[("Infantry", "Attack")] = 10.0
        own = SideProfile(
            role="rally",
            troops_total=1000,
            panel=dict(panel),
            panel_is_final=True,
            widgets_in_panel=True,
            formation={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0},
            lead_heroes={"Infantry": "Elif"},
            joiners=["Jessie", "Seo-yoon"],
        )
        enemy = SideProfile(
            role="garrison",
            troops_total=1000,
            panel=dict(panel),
            panel_is_final=True,
            widgets_in_panel=True,
            formation={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0},
        )
        captured = {}
        old_run_batch = api.kernel.run_batch
        try:
            def fake_run_batch(con, *args, **kwargs):
                inf = next(u for u in con.attacker_units
                           if u.troop == TroopType.INFANTRY)
                captured["attack"] = inf.astat[StatType.ATTACK]
                captured["dd"] = inf.dd
                return [RunRecord(
                    winner="A", turns=1,
                    attacker_start={TroopType.INFANTRY: 1000},
                    defender_start={TroopType.INFANTRY: 1000},
                    attacker_incap={TroopType.INFANTRY: 0},
                    defender_incap={TroopType.INFANTRY: 1000},
                )]

            api.kernel.run_batch = fake_run_batch
            api.predict(own, enemy, n=1, seed=1, params={"engine": "turn"})
        finally:
            api.kernel.run_batch = old_run_batch

        base = troop_base_stats(12, 10, TroopType.INFANTRY)[StatType.ATTACK]
        self.assertAlmostEqual(captured["attack"], base * (1 + 10.0))
        self.assertEqual(captured["dd"], 0.0)


if __name__ == "__main__":
    unittest.main()
