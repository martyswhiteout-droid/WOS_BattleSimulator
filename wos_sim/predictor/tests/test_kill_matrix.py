"""Per-turn attacker x victim kill matrix (ENGINE_HANDOFF_kill_matrix.md).

Pure instrumentation: the 3x3 matrix's row sums must equal the attacker
kills-by-class marginal and its column sums the opposing side's per-class
casualties, every turn. Also checks the matrix reaches the UI call
(api.battle_timeline)."""
import json
import os
import unittest

from wos_sim import pvp_turn_engine as te
from wos_sim.predictor import api, construct
from wos_sim.predictor.kernel import _run_rng
from wos_sim.predictor.profiles import ClassQuality, Matchup, SideProfile

_CLS = ("Infantry", "Lancer", "Marksman")
_ST = ("Attack", "Defense", "Lethality", "Health")


def _side(role, comp):
    total = float(sum(comp.values()))
    return SideProfile(
        role=role, troops_total=int(total), stats_mode="scouted",
        formation={c: comp[c] / total for c in _CLS},
        formation_counts={c: float(comp[c]) for c in _CLS},
        quality={c: ClassQuality(tier=12, fc=10) for c in _CLS},
        panel={(c, s): 25.0 for c in _CLS for s in _ST},
        panel_is_final=True, lead_heroes={}, joiners=[])


class TestKillMatrix(unittest.TestCase):
    def _run_compact(self):
        own = _side("rally", {"Infantry": 60000, "Lancer": 20000, "Marksman": 20000})
        enemy = _side("garrison", {"Infantry": 40000, "Lancer": 30000, "Marksman": 30000})
        con = construct.build(Matchup(own, enemy), apply_legacy_skills=False)
        res = te.run_construct(con, _run_rng(7, 0), dict(con.engine_params, engine="turn"))
        return te._compact_timeline(res.turn_log)

    def test_matrix_marginals_reconcile_every_turn(self):
        comp = self._run_compact()
        self.assertTrue(comp, "no turns produced")
        for ti, r in enumerate(comp):
            self.assertGreaterEqual(len(r), 10, "compact tuple missing matrix fields 8-9")
            for kmx_idx, dealt_idx, cas_idx in ((8, 6, 5), (9, 7, 4)):
                kmx = r[kmx_idx]                  # rows = attacker class, cols = victim
                row_sums = [sum(kmx[a][v] for v in range(3)) for a in range(3)]
                col_sums = [sum(kmx[a][v] for a in range(3)) for v in range(3)]
                for i in range(3):
                    # row sums == this side's kills-by-class marginal
                    self.assertAlmostEqual(row_sums[i], r[dealt_idx][i], places=4,
                                           msg=f"turn {ti+1} row-sum != kills-by-class")
                    # col sums == the OPPOSING side's per-class casualties
                    self.assertAlmostEqual(col_sums[i], r[cas_idx][i], places=4,
                                           msg=f"turn {ti+1} col-sum != opposing casualties")

    def test_matrix_exposed_in_battle_timeline(self):
        own = _side("rally", {"Infantry": 60000, "Lancer": 20000, "Marksman": 20000})
        enemy = _side("garrison", {"Infantry": 40000, "Lancer": 30000, "Marksman": 30000})
        tl = api.battle_timeline(own, enemy, seed=7, index=0, params={"engine": "turn"})
        self.assertIn("kill_matrix", tl)
        km = tl["kill_matrix"]
        self.assertEqual(len(km["own"]), len(tl["turns"]))
        self.assertEqual(len(km["enemy"]), len(tl["turns"]))
        # each turn entry is a 3x3
        for turn in km["own"]:
            self.assertEqual(len(turn), 3)
            self.assertTrue(all(len(row) == 3 for row in turn))


if __name__ == "__main__":
    unittest.main()
