"""Layer 1b — hero-skill resolution (against the real workbook skill book)."""
import unittest

from wos_sim.models import CombatContext, SkillAttribute, StatType
from wos_sim.predictor.profiles import SideProfile
from wos_sim.predictor import skills

A = StatType.ATTACK


class TestSkillResolution(unittest.TestCase):
    def test_joiner_stat_skill_resolves_to_multiplicative_factor(self):
        # Seo-yoon Skill 1 = +25% Attack (stats-based) -> a MULTIPLICATIVE x1.25
        side = SideProfile(joiners=["Seo-yoon"])
        board = skills.resolve(side, SideProfile(), "A", "D", CombatContext.RALLY)
        atk = [v for (tag, tr, st), v in board.skillmult.items() if st == A and tag == "A"]
        self.assertTrue(atk, "expected an Attack skill multiplier")
        for v in atk:
            self.assertAlmostEqual(v, 1.25, places=3)

    def test_joiner_damage_dealt_skill_goes_to_dd_pool(self):
        # Jessie Skill 1 = +25% Damage Dealt -> the DD pool, not a stat factor
        side = SideProfile(joiners=["Jessie"])
        board = skills.resolve(side, SideProfile(), "A", "D", CombatContext.RALLY)
        self.assertTrue(any(tag == "A" and v > 0 for (tag, tr), v in board.dd.items()))
        self.assertFalse(any(st == A for (tag, tr, st) in board.skillmult))   # not a stat skill

    def test_only_joiner_skill_1_is_used(self):
        # Bradley has S1/S2/S3; as a JOINER only S1 (Attack) contributes.
        side = SideProfile(joiners=["Bradley"])
        board = skills.resolve(side, SideProfile(), "A", "D", CombatContext.RALLY)
        # S2 is an enemy Damage-Taken debuff; as a joiner it must NOT appear on the foe
        self.assertFalse(any(tag == "D" for (tag, tr) in board.dt.items()))


if __name__ == "__main__":
    unittest.main()
