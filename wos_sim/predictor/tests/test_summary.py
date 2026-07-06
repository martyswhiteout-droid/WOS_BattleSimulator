"""Layer 2 — per-run records -> visual-ready statistics."""
import math
import unittest

from wos_sim.models import TroopType
from wos_sim.predictor.kernel import RunRecord
from wos_sim.predictor import summary

INF, LAN = TroopType.INFANTRY, TroopType.LANCER


def rec(winner, a_start=None, d_start=None, a_incap=None, d_incap=None, turns=10):
    a_start = a_start or {INF: 1000}
    d_start = d_start or {INF: 1000}
    a_incap = a_incap if a_incap is not None else {INF: 0}
    d_incap = d_incap if d_incap is not None else {INF: 0}
    return RunRecord(winner, turns, a_start, d_start, a_incap, d_incap)


class TestVerdict(unittest.TestCase):
    def test_win_loss_mutual_proportions_own_attacker(self):
        recs = [rec('A')] * 6 + [rec('mutual')] * 1 + [rec('D')] * 3
        fc = summary.summarize(recs, own_is_attacker=True)
        self.assertAlmostEqual(fc.p_win.p, 0.6)
        self.assertAlmostEqual(fc.p_mutual.p, 0.1)
        self.assertAlmostEqual(fc.p_loss.p, 0.3)
        self.assertAlmostEqual(fc.p_win_effective, 0.7)     # mutual -> attacker == own

    def test_mutual_counts_as_loss_when_own_is_defender(self):
        recs = [rec('A')] * 6 + [rec('mutual')] * 1 + [rec('D')] * 3
        fc = summary.summarize(recs, own_is_attacker=False)
        self.assertAlmostEqual(fc.p_win.p, 0.3)             # own is the defender (D)
        self.assertAlmostEqual(fc.p_loss.p, 0.6)
        self.assertAlmostEqual(fc.p_loss_effective, 0.7)    # mutual -> attacker(enemy) == own loss

    def test_mc_standard_error_of_a_proportion(self):
        recs = [rec('A')] * 68 + [rec('D')] * 32
        fc = summary.summarize(recs, own_is_attacker=True)
        self.assertAlmostEqual(fc.p_win.se, math.sqrt(0.68 * 0.32 / 100), places=9)


class TestOutcomeQuality(unittest.TestCase):
    def test_eight_buckets_by_winner_survivor_pct(self):
        recs = [
            rec('A', a_start={INF: 1000}, a_incap={INF: 100}),   # own win, 90% survive -> 8 Overwhelming
            rec('A', a_start={INF: 1000}, a_incap={INF: 600}),   # own win, 40% survive -> 6 Close
            rec('D', d_start={INF: 1000}, d_incap={INF: 900}),   # own loss, enemy 10% survive -> 4 Valiant
            rec('mutual', a_start={INF: 1000}, a_incap={INF: 1000}),  # mutual->own(A) win, 0% -> 5 Pyrrhic
            rec('D', d_start={INF: 1000}, d_incap={INF: 200}),   # own loss, enemy 80% survive -> 1 Crushing
        ]
        q = summary.summarize(recs, own_is_attacker=True).outcome_quality
        self.assertEqual(q, {1: 1, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1, 7: 0, 8: 1})

    def test_defender_perspective_maps_mutual_to_defeat_bucket(self):
        # own is the defender; mutual -> attacker(enemy) wins -> a DEFEAT for us.
        # enemy is the attacker (A); enemy survivor % decides the defeat severity.
        recs = [rec('mutual', a_start={INF: 1000}, a_incap={INF: 300})]  # enemy 70% survive -> 2 Decisive Defeat
        q = summary.summarize(recs, own_is_attacker=False).outcome_quality
        self.assertEqual(q[2], 1)
        self.assertEqual(sum(q.values()), 1)


class TestLossDistributions(unittest.TestCase):
    def test_army_loss_pct_distribution(self):
        recs = [rec('A', a_incap={INF: 100}),   # 10% of own lost
                rec('A', a_incap={INF: 500}),   # 50%
                rec('D', a_incap={INF: 900})]   # 90%   (a_start default 1000)
        fc = summary.summarize(recs, own_is_attacker=True)
        own = fc.army_losses['own']
        self.assertAlmostEqual(own.median, 50.0)
        self.assertAlmostEqual(own.mean, 50.0)
        self.assertEqual(sum(own.counts), 3)
        self.assertAlmostEqual(fc.army_losses['enemy'].median, 0.0)   # enemy(def) took 0

    def test_per_class_loss_distribution(self):
        recs = [rec('A', a_start={INF: 1000, LAN: 500}, a_incap={INF: 200, LAN: 250}),
                rec('A', a_start={INF: 1000, LAN: 500}, a_incap={INF: 400, LAN: 0})]
        fc = summary.summarize(recs, own_is_attacker=True)
        self.assertAlmostEqual(fc.class_losses['Infantry']['own'].median, 30.0)  # 20,40
        self.assertAlmostEqual(fc.class_losses['Lancer']['own'].median, 25.0)    # 50,0


class TestRounds(unittest.TestCase):
    def test_rounds_split_by_own_win_and_loss(self):
        recs = [rec('A', turns=20), rec('A', turns=30), rec('D', turns=15)]
        fc = summary.summarize(recs, own_is_attacker=True)
        self.assertEqual(sum(fc.rounds['win'].counts), 2)
        self.assertEqual(sum(fc.rounds['loss'].counts), 1)
        self.assertAlmostEqual(fc.rounds['win'].median, 25.0)   # median(20,30)


class TestSkillTelemetry(unittest.TestCase):
    def test_aggregates_per_run_hero_skills_separately(self):
        tel1 = {"attacker": {"heroes": [
            {"hero": "Elif", "role": "captain", "troop": "Infantry",
             "skills": [{"slot": "skill_1", "triggers": 10, "kills": 0},
                        {"slot": "skill_2", "triggers": 2, "kills": 100}]}
        ]}, "defender": {"heroes": []}}
        tel2 = {"attacker": {"heroes": [
            {"hero": "Elif", "role": "captain", "troop": "Infantry",
             "skills": [{"slot": "skill_1", "triggers": 14, "kills": 0},
                        {"slot": "skill_2", "triggers": 2, "kills": 300}]}
        ]}, "defender": {"heroes": []}}
        recs = [rec('A', turns=10), rec('A', turns=12)]
        recs[0].skill_telemetry = tel1
        recs[1].skill_telemetry = tel2

        fc = summary.summarize(recs, own_is_attacker=True)
        row = fc.skill_telemetry["own"][0]
        self.assertEqual(row["hero"], "Elif")
        self.assertEqual(row["role"], "captain")
        self.assertEqual(len(row["skills"]), 2)
        self.assertEqual(row["skills"][0]["slot"], "skill_1")
        self.assertIn("icon", row["skills"][0])
        self.assertAlmostEqual(row["skills"][0]["triggers"].median, 12.0)
        self.assertAlmostEqual(row["skills"][1]["triggers"].median, 2.0)
        self.assertAlmostEqual(row["skills"][1]["kills"].median, 200.0)

    def test_aggregates_troop_skill_rows(self):
        tel1 = {"attacker": {"heroes": [], "troop_skills": [
            {"name": "ambusher", "troop": "Lancer", "triggers": 8, "kills": 1000}
        ]}, "defender": {"heroes": []}}
        tel2 = {"attacker": {"heroes": [], "troop_skills": [
            {"name": "ambusher", "troop": "Lancer", "triggers": 10, "kills": 2000}
        ]}, "defender": {"heroes": []}}
        recs = [rec('A', turns=10), rec('A', turns=12)]
        recs[0].skill_telemetry = tel1
        recs[1].skill_telemetry = tel2

        fc = summary.summarize(recs, own_is_attacker=True)
        group = fc.skill_telemetry["own"][0]
        self.assertEqual(group["kind"], "troop")
        self.assertEqual(group["skills"][0]["name"], "Ambusher")
        self.assertAlmostEqual(group["skills"][0]["triggers"].median, 9.0)
        self.assertAlmostEqual(group["skills"][0]["kills"].median, 1500.0)

    def test_attaches_troop_skills_to_matching_captain_class(self):
        tel = {"attacker": {"heroes": [
            {"hero": "Dominic", "role": "captain", "troop": "Lancer",
             "skills": [{"slot": "skill_1", "triggers": 1, "kills": 0}]}
        ], "troop_skills": [
            {"name": "Incandescent Field II", "troop": "Lancer", "triggers": 4, "kills": 0}
        ]}, "defender": {"heroes": []}}
        recs = [rec('A', turns=10)]
        recs[0].skill_telemetry = tel

        fc = summary.summarize(recs, own_is_attacker=True)
        group = fc.skill_telemetry["own"][0]
        self.assertEqual(group["hero"], "Dominic")
        self.assertEqual([s["source"] for s in group["skills"]], ["hero", "troop"])
        self.assertEqual(group["skills"][1]["name"], "Incandescent Field")


class TestRobustness(unittest.TestCase):
    def test_empty_batch_does_not_crash(self):
        fc = summary.summarize([], own_is_attacker=True)
        self.assertEqual(fc.n, 0)
        self.assertEqual(fc.p_win.p, 0.0)
        self.assertEqual(fc.p_win.se, 0.0)
        self.assertEqual(sum(fc.outcome_quality.values()), 0)
        self.assertEqual(sum(fc.army_losses['own'].counts), 0)
        self.assertIsNone(fc.rounds['win'])


if __name__ == "__main__":
    unittest.main()
