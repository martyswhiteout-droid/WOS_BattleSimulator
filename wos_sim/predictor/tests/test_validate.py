"""Input hardening — reject malformed profiles with clear messages."""
import unittest

from wos_sim.predictor.profiles import ClassQuality, Matchup, SideProfile
from wos_sim.predictor import validate


def _ok_side(role):
    return SideProfile(role=role, troops_total=1_000_000,
                       formation={"Infantry": 0.5, "Lancer": 0.2, "Marksman": 0.3})


class TestValidate(unittest.TestCase):
    def test_a_valid_matchup_passes(self):
        validate.validate_matchup(Matchup(_ok_side("rally"), _ok_side("garrison")))   # no raise

    def test_negative_marksman_formation_is_rejected(self):
        bad = SideProfile(role="rally", formation={"Infantry": 0.7, "Lancer": 0.6, "Marksman": -0.3})
        with self.assertRaises(validate.InvalidInput) as cm:
            validate.validate_matchup(Matchup(bad, _ok_side("garrison")))
        self.assertTrue(any("formation" in p.lower() for p in cm.exception.problems))

    def test_nonpositive_troops_rejected(self):
        bad = _ok_side("rally"); bad.troops_total = 0
        with self.assertRaises(validate.InvalidInput):
            validate.validate_matchup(Matchup(bad, _ok_side("garrison")))

    def test_unknown_hero_rejected(self):
        bad = _ok_side("rally"); bad.joiners = ["Nonexistent Hero"]
        with self.assertRaises(validate.InvalidInput) as cm:
            validate.validate_matchup(Matchup(bad, _ok_side("garrison")))
        self.assertTrue(any("hero" in p.lower() for p in cm.exception.problems))

    def test_generation_catalog_heroes_are_known(self):
        own = _ok_side("rally")
        own.lead_heroes = {"Infantry": "Hank", "Lancer": "Estrella", "Marksman": "Viveca"}
        validate.validate_matchup(Matchup(own, _ok_side("garrison")))   # no raise

    def test_out_of_range_quality_rejected(self):
        bad = _ok_side("rally"); bad.quality = {"Infantry": ClassQuality(tier=13, fc=99, t12_stack=40)}
        with self.assertRaises(validate.InvalidInput):
            validate.validate_matchup(Matchup(bad, _ok_side("garrison")))

    def test_roles_must_be_opposite(self):
        with self.assertRaises(validate.InvalidInput):
            validate.validate_matchup(Matchup(_ok_side("rally"), _ok_side("rally")))


if __name__ == "__main__":
    unittest.main()
