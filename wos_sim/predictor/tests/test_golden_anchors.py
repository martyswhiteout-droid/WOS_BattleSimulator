"""Overfit guardrail (pytest mirror of regression check #13).

Locks in every real battle whose winner the engine currently predicts
correctly. A calibration change that fits one report but breaks a
previously-correct battle fails HERE. See wos_sim/data/golden_baseline.json.
"""
import unittest

from wos_sim.eval_reports import golden_regression


class TestGoldenAnchors(unittest.TestCase):
    def test_locked_battles_do_not_regress(self):
        v = golden_regression(n=20)
        self.assertEqual(
            v["broken"], [],
            f"Calibration regressed previously-correct battles: {v['broken']}. "
            f"A change may FIX known misses, never BREAK a locked battle.")

    def test_no_new_silent_wrong_winners(self):
        v = golden_regression(n=20)
        self.assertEqual(
            v["new_silent"], [],
            f"Change introduced NEW silent wrong-winners (confident + no "
            f"coin-flip flag): {v['new_silent']}.")

    def test_match_count_at_or_above_baseline(self):
        v = golden_regression(n=20)
        self.assertGreaterEqual(
            v["match_count"], v["baseline_count"],
            f"Winner-match count {v['match_count']} dropped below baseline "
            f"{v['baseline_count']}.")


if __name__ == "__main__":
    unittest.main()
