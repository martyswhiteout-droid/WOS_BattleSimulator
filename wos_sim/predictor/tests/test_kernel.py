"""Kernel seam — construct -> per-run battle records (with proc-variance stub)."""
import unittest

from wos_sim.predictor.profiles import Matchup, SideProfile
from wos_sim.predictor import construct, kernel

_STATS = ("Attack", "Defense", "Lethality", "Health")
_CLASSES = ("Infantry", "Lancer", "Marksman")


def sample_construct():
    panel = {(c, s): 10.0 for c in _CLASSES for s in _STATS}   # ~+1000% -> PvP-scale stats
    own = SideProfile(role="rally", troops_total=1_000_000, panel=dict(panel))
    enemy = SideProfile(role="garrison", troops_total=1_000_000, panel=dict(panel))
    return construct.build(Matchup(own, enemy))


class TestKernel(unittest.TestCase):
    def test_run_batch_returns_n_records(self):
        recs = kernel.run_batch(sample_construct(), n=20, seed=1)
        self.assertEqual(len(recs), 20)
        r = recs[0]
        self.assertIn(r.winner, ("A", "D", "mutual"))
        self.assertGreater(r.turns, 0)
        self.assertEqual(set(r.attacker_start), set(r.attacker_incap))

    def test_same_seed_reproduces_identical_batch(self):
        a = kernel.run_batch(sample_construct(), n=15, seed=42)
        b = kernel.run_batch(sample_construct(), n=15, seed=42)
        self.assertEqual([(r.winner, r.turns, sum(r.attacker_incap.values())) for r in a],
                         [(r.winner, r.turns, sum(r.attacker_incap.values())) for r in b])

    def test_stub_produces_run_to_run_variance(self):
        recs = kernel.run_batch(sample_construct(), n=60, seed=7)
        totals = {round(sum(r.attacker_incap.values())) for r in recs}
        self.assertGreater(len(totals), 1)   # a real distribution, not one spike


if __name__ == "__main__":
    unittest.main()
