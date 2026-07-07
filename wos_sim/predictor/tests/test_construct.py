"""Layer 1 — profile -> engine construct."""
import unittest

from wos_sim.models import StatType, TroopType
from wos_sim.predictor.profiles import CLASSES, ClassQuality, Matchup, SideProfile
from wos_sim.predictor import construct


class TestClassCounts(unittest.TestCase):
    def test_formation_splits_total_into_per_class_counts(self):
        side = SideProfile(troops_total=1_000_000,
                           formation={"Infantry": 0.5, "Lancer": 0.2, "Marksman": 0.3})
        self.assertEqual(construct.class_counts(side),
                         {"Infantry": 500_000, "Lancer": 200_000, "Marksman": 300_000})


class TestEffectiveStats(unittest.TestCase):
    def test_applies_panel_own_buffs_and_enemy_penalty(self):
        from wos_sim.troop_catalog import troop_base_stats
        own = SideProfile(
            stats_mode="pools",
            quality={"Infantry": ClassQuality(tier=11, fc=10)},
            panel={("Infantry", "Attack"): 10.0},   # +1000% panel
            own_buffs={"Attack": 0.20})
        enemy = SideProfile(debuffs_on_enemy={"Attack": 0.10})   # enemy applies -10% attack to us

        base = troop_base_stats(11, 10, TroopType.INFANTRY)[StatType.ATTACK]
        eff = construct.effective_stats(own, enemy, "Infantry")
        expected = base * (1 + 10.0) * (1 + 0.20) / (1 + 0.10)
        self.assertAlmostEqual(eff[StatType.ATTACK], expected, places=6)

    def test_half_tier_interpolates_between_integer_tiers(self):
        from wos_sim.troop_catalog import troop_base_stats
        side = SideProfile(quality={"Lancer": ClassQuality(tier=10.5, fc=10)})
        enemy = SideProfile()
        lo = troop_base_stats(10, 10, TroopType.LANCER)[StatType.HEALTH]
        hi = troop_base_stats(11, 10, TroopType.LANCER)[StatType.HEALTH]
        eff = construct.effective_stats(side, enemy, "Lancer")
        self.assertAlmostEqual(eff[StatType.HEALTH], (lo + hi) / 2, places=6)


class TestBuild(unittest.TestCase):
    def _matchup(self):
        own = SideProfile(role="rally", troops_total=1_000_000,
                          formation={"Infantry": 0.6, "Lancer": 0.4, "Marksman": 0.0})
        enemy = SideProfile(role="garrison", troops_total=800_000,
                            formation={"Infantry": 0.5, "Lancer": 0.0, "Marksman": 0.5})
        return Matchup(own, enemy)

    def test_rally_own_is_attacker_and_zero_classes_dropped(self):
        con = construct.build(self._matchup())
        self.assertTrue(con.own_is_attacker)
        self.assertEqual({u.troop: u.n for u in con.attacker_units},
                         {TroopType.INFANTRY: 600_000, TroopType.LANCER: 400_000})
        self.assertEqual({u.troop: u.n for u in con.defender_units},
                         {TroopType.INFANTRY: 400_000, TroopType.MARKSMAN: 400_000})

    def test_units_carry_effective_and_base_stats(self):
        con = construct.build(self._matchup())
        inf = next(u for u in con.attacker_units if u.troop == TroopType.INFANTRY)
        self.assertGreater(inf.astat[StatType.ATTACK], 0)
        self.assertEqual(inf.base_atk, construct.tier_base(12, 10, TroopType.INFANTRY)[StatType.ATTACK])

    def test_garrison_role_makes_enemy_the_attacker(self):
        m = self._matchup()
        m.own.role, m.enemy.role = "garrison", "rally"
        con = construct.build(m)
        self.assertFalse(con.own_is_attacker)
        # attacker units now come from the enemy (rally) side: 800k @ 50/0/50
        self.assertEqual({u.troop: u.n for u in con.attacker_units},
                         {TroopType.INFANTRY: 400_000, TroopType.MARKSMAN: 400_000})


class TestStatsModeAndSkills(unittest.TestCase):
    def test_scouted_mode_treats_panel_as_net_ignoring_buff_inputs(self):
        from wos_sim.troop_catalog import troop_base_stats
        side = SideProfile(stats_mode="scouted",
                           quality={"Infantry": ClassQuality(tier=11, fc=10)},
                           panel={("Infantry", "Attack"): 10.0},
                           own_buffs={"Attack": 0.20})              # already in the scouted panel
        enemy = SideProfile(debuffs_on_enemy={"Attack": 0.10})
        base = troop_base_stats(11, 10, TroopType.INFANTRY)[StatType.ATTACK]
        eff = construct.effective_stats(side, enemy, "Infantry")
        self.assertAlmostEqual(eff[StatType.ATTACK], base * (1 + 10.0))   # buffs NOT re-added

    def test_hero_skill_multiplier_scales_the_effective_stat(self):
        from wos_sim.assemble import ModifierBoard
        board = ModifierBoard()
        board.mul_stat("A", TroopType.INFANTRY, StatType.ATTACK, 0.25)    # +25% hero stat skill
        side = SideProfile(stats_mode="scouted",
                           quality={"Infantry": ClassQuality(tier=11, fc=10)},
                           panel={("Infantry", "Attack"): 10.0})
        base = construct.effective_stats(side, SideProfile(), "Infantry")[StatType.ATTACK]
        with_skill = construct.effective_stats(side, SideProfile(), "Infantry", board, "A")[StatType.ATTACK]
        self.assertAlmostEqual(with_skill, base * 1.25)

    def test_final_panel_skips_own_permanent_stat_skill_but_keeps_enemy_debuff(self):
        from wos_sim.troop_catalog import troop_base_stats

        panel = {(c, s): 10.0 for c in CLASSES for s in ("Attack", "Defense", "Lethality", "Health")}
        own = SideProfile(
            role="rally",
            troops_total=1000,
            panel=dict(panel),
            panel_is_final=True,
            widgets_in_panel=True,
            formation={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0},
            lead_heroes={"Infantry": "Gisela"},
            quality={"Infantry": ClassQuality(tier=12, fc=10)},
        )
        enemy = SideProfile(
            role="garrison",
            troops_total=1000,
            panel=dict(panel),
            panel_is_final=True,
            widgets_in_panel=True,
            formation={"Infantry": 0.0, "Lancer": 1.0, "Marksman": 0.0},
            lead_heroes={"Lancer": "Karol", "Marksman": "Vulcanus"},
            quality={"Lancer": ClassQuality(tier=12, fc=10)},
        )
        con = construct.build(Matchup(own, enemy))
        own_inf = next(u for u in con.attacker_units if u.troop == TroopType.INFANTRY)
        enemy_lan = next(u for u in con.defender_units if u.troop == TroopType.LANCER)
        own_base = troop_base_stats(12, 10, TroopType.INFANTRY)[StatType.ATTACK]
        enemy_base = troop_base_stats(12, 10, TroopType.LANCER)[StatType.ATTACK]

        self.assertAlmostEqual(
            own_inf.astat[StatType.ATTACK],
            own_base * (1 + 10.0) * 0.80,
        )
        self.assertAlmostEqual(
            enemy_lan.astat[StatType.ATTACK],
            enemy_base * (1 + 10.0),
        )

    def test_build_routes_joiner_dd_skill_into_unit_dd(self):
        own = SideProfile(role="rally", troops_total=1000, joiners=["Jessie"])   # +25% Damage Dealt
        con = construct.build(Matchup(own, SideProfile(role="garrison", troops_total=1000)))
        self.assertTrue(all(u.dd > 0 for u in con.attacker_units))

    def test_clean_turn_construct_does_not_preapply_hero_skills(self):
        from wos_sim.troop_catalog import troop_base_stats
        own = SideProfile(
            role="rally",
            troops_total=1000,
            panel_is_final=True,
            panel={("Infantry", "Attack"): 10.0},
            formation={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0},
            quality={"Infantry": ClassQuality(tier=11, fc=10)},
            joiners=["Jessie", "Seo-yoon"],
        )
        con = construct.build(
            Matchup(own, SideProfile(role="garrison", troops_total=1000)),
            apply_legacy_skills=False,
        )
        inf = next(u for u in con.attacker_units if u.troop == TroopType.INFANTRY)
        base = troop_base_stats(11, 10, TroopType.INFANTRY)[StatType.ATTACK]
        self.assertAlmostEqual(inf.astat[StatType.ATTACK], base * (1 + 10.0))
        self.assertEqual(inf.dd, 0.0)

    def test_a_stronger_hero_changes_effective_attack(self):
        base_profile = dict(role="rally", troops_total=1000, panel={("Infantry", "Attack"): 5.0})
        weak = construct.build(Matchup(SideProfile(joiners=[], **base_profile),
                                       SideProfile(role="garrison")))
        strong = construct.build(Matchup(SideProfile(joiners=["Seo-yoon"], **base_profile),  # +25% Attack
                                         SideProfile(role="garrison")))
        w = next(u for u in weak.attacker_units if u.troop == TroopType.INFANTRY)
        s = next(u for u in strong.attacker_units if u.troop == TroopType.INFANTRY)
        self.assertGreater(s.astat[StatType.ATTACK], w.astat[StatType.ATTACK])


class TestT12Params(unittest.TestCase):
    def test_t12_stacking_becomes_engine_params_only_at_tier12(self):
        own = SideProfile(role="rally", quality={
            "Infantry": ClassQuality(tier=12, fc=10, t12_stack=24),   # -> indomitable_wall 24
            "Lancer":   ClassQuality(tier=11, fc=10, t12_stack=24),   # tier<12 -> gated to 0
            "Marksman": ClassQuality(tier=12, fc=10, t12_stack=10)})  # -> starfire 10
        enemy = SideProfile(role="garrison", quality={
            c: ClassQuality(tier=10, fc=10, t12_stack=24) for c in CLASSES})  # all tier<12
        con = construct.build(Matchup(own, enemy))
        self.assertEqual(con.engine_params["a_t12"],
                         {"indomitable_wall": 24, "meridian_phalanx": 0, "starfire": 10})
        self.assertIsNone(con.engine_params["d_t12"])   # no tier-12 class -> no T12


if __name__ == "__main__":
    unittest.main()
