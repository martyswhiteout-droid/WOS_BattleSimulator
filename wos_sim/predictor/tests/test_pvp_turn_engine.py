"""Turn engine structural tests: catalog coverage, telemetry, conservation."""
import json
import random
import unittest
from pathlib import Path

from wos_sim.loader import load_hero_profiles, load_hero_roster, load_skill_book
from wos_sim import pvp_turn_engine
from wos_sim.models import (
    AffectingSide,
    EffectReceiver,
    SkillAttribute,
    SkillSource,
    StatType,
    TriggerUnit,
    TroopType,
)
from wos_sim.hero_stats import hero_generation, hero_stat
from wos_sim.predictor import api, construct
from wos_sim.predictor.profiles import ClassQuality, Matchup, SideProfile
from wos_sim.pvp_engine import A, D, H, L, Unit
from wos_sim.pvp_turn_engine import (
    DamagePacket,
    SkillDef,
    TypeStack,
    _make_hero_skill,
    _make_troop_skill,
    _skill_frequency,
    _skill_trigger_unit,
    _trigger_count_for_skill,
    apply_packets,
    catalog_classification_report,
    run_construct,
    skill_defs_from_matchup,
    simulate_turns,
)
from wos_sim.skill_source_audit import wiki_tokens, workbook_tokens, troop_skill_rule_tokens
from wos_sim.troop_catalog import TROOP_SKILL_CATALOG


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _panel():
    return {(c, s): 10.0
            for c in ("Infantry", "Lancer", "Marksman")
            for s in ("Attack", "Defense", "Lethality", "Health")}


def _side(role="rally", leads=None, joiners=None, widgets_in_panel=None):
    return SideProfile(
        role=role,
        troops_total=120_000,
        panel=_panel(),
        formation={"Infantry": 0.4, "Lancer": 0.3, "Marksman": 0.3},
        quality={c: ClassQuality(tier=12, fc=10, t12_stack=4)
                 for c in ("Infantry", "Lancer", "Marksman")},
        lead_heroes=leads or {
            "Infantry": "Elif",
            "Lancer": "Dominic",
            "Marksman": "Vulcanus",
        },
        joiners=joiners or ["Jessie", "Seo-yoon", "Ligeia", "Bradley"],
        widgets_in_panel=widgets_in_panel,
    )


def _unit(troop, n=100_000, tier=11.0):
    astat = {A: 100.0, D: 100.0, L: 100.0, H: 100.0}
    return Unit(troop, tier, float(n), astat, 100.0)


def _troop_skill(name):
    return next(s for s in TROOP_SKILL_CATALOG if s.name == name)


def _anchor_side(raw):
    comp = raw["composition"]
    total = sum(v["count"] for v in comp.values())
    levels = raw.get("t12_skill_levels") or raw.get("t12_skill_levels_ASSUMED") or {}
    t12_by_class = {
        "Infantry": levels.get("indomitable_wall", 0),
        "Lancer": levels.get("meridian_phalanx", 0),
        "Marksman": levels.get("starfire", 0),
    }
    joiners = ["Eleonora" if h == "Eleanora" else h
               for h in raw.get("joiner_flags", [])]
    return SideProfile(
        role=raw["role"],
        troops_total=total,
        stats_mode="scouted",
        formation={cls: comp[cls]["count"] / total for cls in comp},
        quality={
            cls: ClassQuality(
                tier=comp[cls]["avg_tier"],
                fc=10,
                t12_stack=t12_by_class[cls],
            )
            for cls in comp
        },
        panel={(cls, stat): value / 100.0
               for cls, stats in raw["panel_pct"].items()
               for stat, value in stats.items()},
        lead_heroes=raw.get("lead_heroes", {}),
        joiners=joiners,
    )


def _anchor_score(filename):
    data, res = _anchor_result(filename)
    survivors = res.a_survivors if res.winner == "A" else res.d_survivors
    live = {troop.value: n for troop, n in survivors.items() if n > 1e-6}
    expected_survivor = "Marksman" if filename.endswith("001.json") else "Lancer"
    return {
        "predicted_winner": res.winner,
        "predicted_turns": res.turns,
        "predicted_survivor_troop": next(iter(live)) if len(live) == 1 else None,
        "predicted_live_survivors": live,
        "predicted_survivors": sum(live.values()),
        "expected_winner": "A",
        "expected_survivor_troop": expected_survivor,
        "expected_survivors": data["attacker"]["survivors"],
    }


def _anchor_result(filename):
    data = json.loads((DATA_DIR / filename).read_text())
    matchup = Matchup(_anchor_side(data["attacker"]), _anchor_side(data["defender"]))
    con = construct.build(matchup, apply_legacy_skills=False)
    params = {
        "engine": "turn",
        "a_t12": data["attacker"].get("t12_skill_levels")
                 or data["attacker"].get("t12_skill_levels_ASSUMED"),
        "d_t12": data["defender"].get("t12_skill_levels")
                 or data["defender"].get("t12_skill_levels_ASSUMED"),
    }
    res = run_construct(con, random.Random(0), params=params)
    return data, res


def _death_turns(result, side: str) -> dict[str, int]:
    deaths = {}
    for record in result.turn_log:
        start = record.start_counts[side]
        casualties = record.casualties[side]
        for troop in TroopType:
            if troop.value in deaths:
                continue
            before = start.get(troop, 0.0)
            after = before - casualties.get(troop, 0.0)
            if before > 1e-6 and after <= 1e-6:
                deaths[troop.value] = record.turn
    return deaths


def _trigger_count(result, side: str, hero: str, slot: str) -> int:
    telemetry = result.skill_telemetry or {}
    for row in (telemetry.get(side, {}) or {}).get("heroes", []):
        if row.get("hero") != hero:
            continue
        for skill in row.get("skills") or []:
            if skill.get("slot") == slot:
                return int(skill.get("triggers") or 0)
    return 0


class TestCatalogCoverage(unittest.TestCase):
    def test_every_workbook_hero_skill_group_classifies(self):
        book = load_skill_book()
        count = 0
        for hero in book.heroes():
            for source in (SkillSource.SKILL_1, SkillSource.SKILL_2,
                           SkillSource.SKILL_3, SkillSource.WIDGET):
                rows = tuple(e for e in book.for_hero(hero) if e.source == source)
                if not rows:
                    continue
                skill = _make_hero_skill(hero, source, rows, "attacker",
                                         "captain", TroopType.INFANTRY, count)
                self.assertTrue(skill.rows)
                self.assertTrue(skill.is_passive or skill.deals_damage or skill.rows)
                count += 1
        self.assertGreater(count, 100)

    def test_skill_book_loader_accepts_string_paths(self):
        self.assertGreater(len(load_skill_book("WoS battle simulator.xlsx")), 100)

    def test_every_troop_skill_classifies(self):
        for idx, troop_skill in enumerate(TROOP_SKILL_CATALOG):
            skill = _make_troop_skill(troop_skill, "attacker", idx)
            self.assertEqual(skill.owner, troop_skill.name)
            self.assertEqual(skill.role, "troop_skill")
        tokens = troop_skill_rule_tokens()
        for expected in ("Ambusher", "Volley", "Crystal Shield II",
                         "Crystal Lance II", "Crystal Gunpowder II",
                         "indomitable_wall", "meridian_phalanx", "starfire"):
            self.assertIn(expected, tokens)

    def test_matchup_defs_include_widgets_troop_skills_and_t12(self):
        con = construct.build(Matchup(
            _side("rally", widgets_in_panel=False),
            _side("garrison", widgets_in_panel=False),
        ), apply_legacy_skills=False)
        report = catalog_classification_report(con)
        self.assertEqual(report["unclassified"], [])
        self.assertGreaterEqual(report["widgets"], 3)
        self.assertGreaterEqual(report["troop_skills"], 12)
        self.assertEqual(report["t12"], 6)

    def test_gen15_heroes_are_loaded_with_full_catalog_rows(self):
        profiles = load_hero_profiles()
        roster = load_hero_roster()
        book = load_skill_book()
        expected = {
            "Hank": TroopType.INFANTRY,
            "Estrella": TroopType.LANCER,
            "Viveca": TroopType.MARKSMAN,
        }
        for hero, troop in expected.items():
            self.assertEqual(profiles[hero].generation, "15")
            self.assertEqual(profiles[hero].troop_type, troop)
            self.assertEqual(roster.get(hero).troop_type, troop)
            self.assertEqual(hero_generation(hero), 15)
            self.assertAlmostEqual(roster.get(hero).get(StatType.ATTACK), 19.6156)
            self.assertAlmostEqual(hero_stat(15, StatType.ATTACK), 19.6156)
            self.assertAlmostEqual(hero_stat(15, StatType.LETHALITY), 4.9)
            self.assertEqual(
                {source for source in (SkillSource.SKILL_1, SkillSource.SKILL_2,
                                       SkillSource.SKILL_3, SkillSource.WIDGET)
                 if any(row.source == source for row in book.for_hero(hero))},
                {SkillSource.SKILL_1, SkillSource.SKILL_2,
                 SkillSource.SKILL_3, SkillSource.WIDGET},
            )
        hank_skill_2 = tuple(row for row in book.for_hero("Hank")
                             if row.source == SkillSource.SKILL_2)
        hank_def = _make_hero_skill("Hank", SkillSource.SKILL_2, hank_skill_2,
                                    "attacker", "captain", TroopType.INFANTRY, 0)
        self.assertEqual(_skill_frequency(hank_def), 5.0)
        self.assertEqual(_skill_trigger_unit(hank_def), TriggerUnit.STRIKES)
        self.assertTrue(all(row.duration is None for row in hank_skill_2))
        self.assertFalse(hank_def.deals_damage)

    def test_source_normalization_fixes_sign_side_and_per_proc(self):
        book = load_skill_book()

        cara = [row for row in book.for_hero("Cara")
                if row.source == SkillSource.SKILL_1]
        self.assertTrue(cara)
        self.assertTrue(all(row.side == AffectingSide.FOE for row in cara))
        self.assertTrue(all(row.amount < 0 for row in cara))

        vulcanus_def = [row for row in book.for_hero("Vulcanus")
                        if row.source == SkillSource.SKILL_3
                        and row.attribute == SkillAttribute.DEFENSE]
        self.assertTrue(vulcanus_def)
        self.assertTrue(all(row.side == AffectingSide.FOE for row in vulcanus_def))
        self.assertTrue(all(row.amount_per_proc < 0 for row in vulcanus_def))

        flora_marks = next(row for row in book.for_hero("Flora")
                           if row.source == SkillSource.SKILL_3
                           and row.receiver == EffectReceiver.MARKSMAN
                           and row.attribute == SkillAttribute.DAMAGE_DEALT)
        self.assertLess(flora_marks.amount_per_proc, 0)

        jeronimo = [row for row in book.for_hero("Jeronimo")
                    if row.source == SkillSource.SKILL_3]
        self.assertTrue(jeronimo)
        self.assertTrue(all(row.side == AffectingSide.FRIEND for row in jeronimo))
        self.assertTrue(all(abs(row.amount_per_proc - 0.30) < 1e-9
                            for row in jeronimo))

        for hero, source in (("Hector", SkillSource.SKILL_1),
                             ("Nora", SkillSource.SKILL_3),
                             ("Philly", SkillSource.SKILL_3),
                             ("Alonso", SkillSource.SKILL_2)):
            rows = [row for row in book.for_hero(hero) if row.source == source
                    and row.attribute in (SkillAttribute.DAMAGE_TAKEN,
                                          SkillAttribute.DAMAGE_DEALT)]
            self.assertTrue(rows, hero)
            negative_rows = [row for row in rows if row.amount < 0]
            self.assertTrue(negative_rows, hero)
            self.assertTrue(all(row.amount_per_proc is None
                                or row.amount_per_proc < 0
                                for row in negative_rows), hero)

    def test_strikes_and_turns_have_distinct_cadence(self):
        book = load_skill_book()

        def hero_skill(hero, source, troop):
            rows = tuple(row for row in book.for_hero(hero) if row.source == source)
            return _make_hero_skill(hero, source, rows, "attacker", "captain",
                                    troop, 0)

        def trigger_turns(skill, turns=26):
            stacks = {
                troop: TypeStack(troop, 12, 100_000, 100_000, {}, 100)
                for troop in TroopType
            }
            side_events = 0
            out = []
            rng = random.Random(0)
            for turn in range(1, turns + 1):
                if _trigger_count_for_skill(skill, turn, stacks, side_events, rng, {}):
                    out.append(turn)
                for stack in stacks.values():
                    stack.attacks_made += 1
                    side_events += 1
            return out

        vulcanus_2 = hero_skill("Vulcanus", SkillSource.SKILL_2,
                                TroopType.MARKSMAN)
        vulcanus_3 = hero_skill("Vulcanus", SkillSource.SKILL_3,
                                TroopType.MARKSMAN)
        cara_3 = hero_skill("Cara", SkillSource.SKILL_3, TroopType.MARKSMAN)
        ligeia_2 = hero_skill("Ligeia", SkillSource.SKILL_2,
                              TroopType.MARKSMAN)
        ahmose_1 = hero_skill("Ahmose", SkillSource.SKILL_1,
                              TroopType.INFANTRY)

        self.assertEqual(trigger_turns(vulcanus_2), [5, 10, 15, 20, 25])
        self.assertEqual(trigger_turns(vulcanus_3), [1, 4, 7, 10, 13, 16, 19, 22, 25])
        self.assertEqual(trigger_turns(cara_3, 8), [2, 4, 6, 8])
        self.assertEqual(trigger_turns(ligeia_2, 8), [2, 4, 6, 8])
        self.assertEqual(trigger_turns(ahmose_1, 12), [4, 8, 12])

    def test_ahmose_skill_1_pauses_infantry_and_delays_defense_window(self):
        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Ahmose")
                     if row.source == SkillSource.SKILL_1)
        skill = _make_hero_skill("Ahmose", SkillSource.SKILL_1, rows,
                                 "attacker", "captain", TroopType.INFANTRY, 0)
        result = simulate_turns(
            [_unit(TroopType.INFANTRY), _unit(TroopType.LANCER),
             _unit(TroopType.MARKSMAN)],
            [_unit(TroopType.INFANTRY), _unit(TroopType.LANCER),
             _unit(TroopType.MARKSMAN)],
            [skill],
            params={"rate": 0.0},
            rng=random.Random(0),
            max_turns=10,
        )
        events = {record.turn: record.attack_events["attacker"]
                  for record in result.turn_log}
        self.assertEqual(events[4][TroopType.INFANTRY], 0)
        self.assertEqual(events[8][TroopType.INFANTRY], 0)
        self.assertEqual(events[5][TroopType.INFANTRY], 1)
        self.assertEqual(events[4][TroopType.LANCER], 1)
        self.assertEqual(events[4][TroopType.MARKSMAN], 1)
        self.assertEqual(skill.triggers, 2)

    def test_all_class_direct_skills_fire_per_receiver_class(self):
        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Vulcanus")
                     if row.source == SkillSource.SKILL_2)
        skill = _make_hero_skill("Vulcanus", SkillSource.SKILL_2, rows,
                                 "attacker", "captain", TroopType.MARKSMAN, 0)
        stacks = {
            troop: TypeStack(troop, 12, 100_000, 100_000, {}, 100,
                             attacks_made=4)
            for troop in TroopType
        }
        self.assertEqual(
            _trigger_count_for_skill(skill, 5, stacks, 12, random.Random(0), {}),
            [TroopType.INFANTRY, TroopType.LANCER, TroopType.MARKSMAN],
        )

    def test_specific_target_rows_lock_damage_packets_to_target_class(self):
        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Wayne")
                     if row.source == SkillSource.SKILL_2)
        skill = _make_hero_skill("Wayne", SkillSource.SKILL_2, rows,
                                 "attacker", "captain", TroopType.MARKSMAN, 0)
        self.assertEqual(_skill_trigger_unit(skill), TriggerUnit.STRIKES)
        astat = {A: 100.0, D: 100.0, L: 100.0, H: 100.0}
        own = {troop: TypeStack(troop, 12, 100_000, 100_000, dict(astat), 100)
               for troop in TroopType}
        enemy = {troop: TypeStack(troop, 12, 100_000, 100_000, dict(astat), 100)
                 for troop in TroopType}
        mods = pvp_turn_engine._Mods()
        params = dict(pvp_turn_engine.BEST_PARAMS)
        params.update({"K_skill": 1.0, "rate": 1.0})
        packets = pvp_turn_engine._skill_packets(
            skill, [TroopType.MARKSMAN], own, enemy, mods, params,
            1.0, 1.0, 1.0, 1.0)
        self.assertEqual({pkt.target_types for pkt in packets},
                         {(TroopType.LANCER,), (TroopType.MARKSMAN,)})
        self.assertTrue(all(pkt.target_mode == "backline" for pkt in packets))
        casualties, _kills = apply_packets(packets, enemy)
        self.assertEqual(casualties[TroopType.INFANTRY], 0.0)
        self.assertGreater(casualties[TroopType.LANCER], 0.0)
        self.assertGreater(casualties[TroopType.MARKSMAN], 0.0)

    def test_t1_troop_damage_passives_are_target_class_scoped(self):
        astat = {A: 100.0, D: 100.0, L: 100.0, H: 100.0}
        params = dict(pvp_turn_engine.BEST_PARAMS)
        params.update({"mod_gamma": 1.0, "stat_floor": 0.0})

        cases = [
            ("Master Brawler", TroopType.INFANTRY, TroopType.LANCER,
             TroopType.MARKSMAN),
            ("Charge", TroopType.LANCER, TroopType.MARKSMAN,
             TroopType.INFANTRY),
            ("Ranged Strike", TroopType.MARKSMAN, TroopType.INFANTRY,
             TroopType.LANCER),
        ]
        for skill_name, source, target, non_target in cases:
            with self.subTest(skill=skill_name):
                skill = _make_troop_skill(_troop_skill(skill_name), "attacker", 0)
                mods = pvp_turn_engine._passive_mods([skill], {}, {})
                self.assertNotIn(("attacker", source), mods.normal_dd)
                self.assertAlmostEqual(
                    mods.normal_dd_target[("attacker", source, target)],
                    0.10,
                )

                src = TypeStack(source, 1, 100.0, 100.0, dict(astat), 100.0)
                target_stack = TypeStack(target, 1, 100.0, 100.0,
                                         dict(astat), 100.0)
                other_stack = TypeStack(non_target, 1, 100.0, 100.0,
                                        dict(astat), 100.0)
                base_target = pvp_turn_engine._damage_for(
                    src, target_stack, src, "attacker", "defender",
                    pvp_turn_engine._Mods(), params, 1.0)
                buffed_target = pvp_turn_engine._damage_for(
                    src, target_stack, src, "attacker", "defender",
                    mods, params, 1.0)
                base_other = pvp_turn_engine._damage_for(
                    src, other_stack, src, "attacker", "defender",
                    pvp_turn_engine._Mods(), params, 1.0)
                buffed_other = pvp_turn_engine._damage_for(
                    src, other_stack, src, "attacker", "defender",
                    mods, params, 1.0)

                self.assertAlmostEqual(buffed_target / base_target, 1.10)
                self.assertAlmostEqual(buffed_other / base_other, 1.0)

    def test_all_troop_attack_chance_rolls_independently_per_attack(self):
        class SeqRng:
            def __init__(self, values):
                self.values = iter(values)

            def random(self):
                return next(self.values)

        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Wayne")
                     if row.source == SkillSource.SKILL_3)
        skill = _make_hero_skill("Wayne", SkillSource.SKILL_3, rows,
                                 "attacker", "captain", TroopType.MARKSMAN, 0)
        stacks = {troop: TypeStack(troop, 12, 100_000, 100_000, {}, 100)
                  for troop in TroopType}
        self.assertEqual(len(_trigger_count_for_skill(
            skill, 1, stacks, 0, SeqRng([0.1, 0.9, 0.1]), {})), 2)
        self.assertEqual(len(_trigger_count_for_skill(
            skill, 1, stacks, 0, SeqRng([0.9, 0.9, 0.9]), {})), 0)
        self.assertEqual(len(_trigger_count_for_skill(
            skill, 1, stacks, 0, SeqRng([0.1, 0.1, 0.1]), {})), 3)

    def test_renee_companion_skills_do_not_self_trigger(self):
        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Renee")
                     if row.source == SkillSource.SKILL_2)
        skill = _make_hero_skill("Renee", SkillSource.SKILL_2, rows,
                                 "attacker", "captain", TroopType.LANCER, 0)
        stacks = {troop: TypeStack(troop, 12, 100_000, 100_000, {}, 100)
                  for troop in TroopType}
        self.assertEqual(_trigger_count_for_skill(
            skill, 1, stacks, 0, random.Random(0), {}), [])

    def test_widgets_apply_as_selected_passive_stats(self):
        scouted = construct.build(
            Matchup(_side("rally"), _side("garrison")),
            apply_legacy_skills=False,
        )
        self.assertEqual(
            catalog_classification_report(scouted)["widgets"],
            0,
        )
        final_rally = _side("rally", widgets_in_panel=False)
        final_garrison = _side("garrison", widgets_in_panel=False)
        final_rally.panel_is_final = True
        final_garrison.panel_is_final = True
        final_panel = construct.build(
            Matchup(final_rally, final_garrison),
            apply_legacy_skills=False,
        )
        self.assertEqual(
            catalog_classification_report(final_panel)["widgets"],
            0,
        )

        book = load_skill_book()
        widget_rows = tuple(row for row in book.for_hero("Vulcanus")
                            if row.source == SkillSource.WIDGET)
        widget = _make_hero_skill("Vulcanus", SkillSource.WIDGET, widget_rows,
                                  "attacker", "captain", TroopType.MARKSMAN, 0)
        pvp_turn_engine._init_passive_triggers([widget])
        widget_mods = pvp_turn_engine._passive_mods([widget], {}, {})
        self.assertGreater(
            widget_mods.stat.get(("attacker", TroopType.MARKSMAN, StatType.ATTACK), 0.0),
            0.0,
        )

        con = construct.build(Matchup(
            _side("rally", widgets_in_panel=False),
            _side("garrison", widgets_in_panel=False),
        ), apply_legacy_skills=False)
        skills = skill_defs_from_matchup(con, {"engine": "turn"})
        pvp_turn_engine._init_passive_triggers(skills)
        mods = pvp_turn_engine._passive_mods(skills, {}, {})
        self.assertGreater(
            mods.stat.get(("attacker", TroopType.MARKSMAN, StatType.ATTACK), 0.0),
            0.0,
        )
        row = next(row for row in pvp_turn_engine.skill_telemetry(skills)["attacker"]["heroes"]
                   if row["hero"] == "Vulcanus" and row["role"] == "captain")
        widget = next(skill for skill in row["skills"] if skill["slot"] == "widget")
        self.assertEqual(widget["triggers"], 1)

    def test_non_final_panel_turn_engine_applies_passive_hero_stat_skills(self):
        own = _side("rally", leads={"Infantry": "", "Lancer": "", "Marksman": ""},
                    joiners=["Gatot"], widgets_in_panel=True)
        enemy = _side("garrison", leads={"Infantry": "", "Lancer": "", "Marksman": ""},
                      joiners=[], widgets_in_panel=True)
        low_quality = {
            cls: ClassQuality(tier=6, fc=0, t12_stack=0)
            for cls in ("Infantry", "Lancer", "Marksman")
        }
        own.quality = low_quality
        enemy.quality = low_quality
        own.panel_is_final = False
        enemy.panel_is_final = False
        con = construct.build(Matchup(own, enemy), apply_legacy_skills=False)
        skills = skill_defs_from_matchup(con, {"engine": "turn"})
        mods = pvp_turn_engine._passive_mods(
            skills,
            {u.troop: pvp_turn_engine.TypeStack(u.troop, u.tier, u.n, u.n,
                                                dict(u.astat), u.base_atk)
             for u in con.attacker_units},
            {u.troop: pvp_turn_engine.TypeStack(u.troop, u.tier, u.n, u.n,
                                                dict(u.astat), u.base_atk)
             for u in con.defender_units},
        )
        own_no_joiner = _side(
            "rally",
            leads={"Infantry": "", "Lancer": "", "Marksman": ""},
            joiners=[],
            widgets_in_panel=True,
        )
        own_no_joiner.panel_is_final = True
        own_no_joiner.quality = low_quality
        base_con = construct.build(Matchup(own_no_joiner, enemy),
                                   apply_legacy_skills=False)
        base_skills = skill_defs_from_matchup(base_con, {"engine": "turn"})
        base_mods = pvp_turn_engine._passive_mods(
            base_skills,
            {u.troop: pvp_turn_engine.TypeStack(u.troop, u.tier, u.n, u.n,
                                                dict(u.astat), u.base_atk)
             for u in base_con.attacker_units},
            {u.troop: pvp_turn_engine.TypeStack(u.troop, u.tier, u.n, u.n,
                                                dict(u.astat), u.base_atk)
             for u in base_con.defender_units},
        )
        self.assertAlmostEqual(
            mods.stat[("attacker", TroopType.INFANTRY, StatType.DEFENSE)],
            (1.0 + base_mods.stat[("attacker", TroopType.INFANTRY, StatType.DEFENSE)])
            * 1.30 - 1.0,
        )

    def test_final_panel_turn_engine_suppresses_own_static_stat_rows_only(self):
        # joiners=[""] -> genuinely NO joiners: the helper's `joiners or [...]`
        # default silently adds four, and the old (buggy) joiner suppression
        # used to hide their stat rows, masking that this test wasn't
        # captain-only.
        own = _side(
            "rally",
            leads={"Infantry": "Gisela", "Lancer": "", "Marksman": ""},
            joiners=[""],
            widgets_in_panel=True,
        )
        enemy = _side(
            "garrison",
            leads={"Infantry": "", "Lancer": "Karol", "Marksman": "Vulcanus"},
            joiners=[""],
            widgets_in_panel=True,
        )
        own.panel_is_final = True
        enemy.panel_is_final = True
        con = construct.build(Matchup(own, enemy), apply_legacy_skills=False)
        skills = skill_defs_from_matchup(con, {"engine": "turn"})
        stacks = {
            troop: TypeStack(troop, 12, 100_000, 100_000,
                             {A: 100.0, D: 100.0, L: 100.0, H: 100.0}, 100.0)
            for troop in TroopType
        }
        mods = pvp_turn_engine._passive_mods(skills, stacks, stacks)

        self.assertNotIn(("defender", TroopType.LANCER, StatType.ATTACK), mods.stat)
        self.assertAlmostEqual(
            mods.stat[("attacker", TroopType.INFANTRY, StatType.ATTACK)],
            -0.20,
        )

    def test_final_panel_does_not_suppress_joiner_stat_rows(self):
        # A joiner is ANOTHER player's hero: its stat skills are never inside
        # this side's scouted/final panel, so they must apply at battle time.
        # Gatot SK1 = +30% own Infantry Defense (pure stat row).
        own = _side(
            "rally",
            leads={"Infantry": "Gisela", "Lancer": "", "Marksman": ""},
            joiners=["Gatot"],
            widgets_in_panel=True,
        )
        enemy = _side(
            "garrison",
            leads={"Infantry": "", "Lancer": "Karol", "Marksman": "Vulcanus"},
            joiners=[""],
            widgets_in_panel=True,
        )
        own.panel_is_final = True
        enemy.panel_is_final = True
        con = construct.build(Matchup(own, enemy), apply_legacy_skills=False)
        skills = skill_defs_from_matchup(con, {"engine": "turn"})
        joiner_defs = [s for s in skills if s.role == "joiner"]
        self.assertEqual([s.owner for s in joiner_defs], ["Gatot"])
        self.assertFalse(joiner_defs[0].suppress_own_stat_passives)
        stacks = {
            troop: TypeStack(troop, 12, 100_000, 100_000,
                             {A: 100.0, D: 100.0, L: 100.0, H: 100.0}, 100.0)
            for troop in TroopType
        }
        mods = pvp_turn_engine._passive_mods(skills, stacks, stacks)
        self.assertGreater(
            mods.stat.get(("attacker", TroopType.INFANTRY, StatType.DEFENSE), 0.0),
            0.0)

    def test_duplicate_joiners_stack(self):
        # GUARDRAIL: duplicate joiners STACK - N copies of a hero fire N Skill-1s,
        # they do NOT dedupe to one (WoS game-authoritative, Martin 2026-07-09).
        # This is the REVERSE of the retired test_duplicate_joiners_apply_once;
        # if it fails because a `seen_joiners`/`seen` dedup was re-added, remove
        # that dedup - do not weaken this test. See ENGINE_HANDOFF_joiner_stacking.md.
        for joiners, expected in ((["Nora"], 1), (["Nora"] * 4, 4),
                                  (["Nora", "Gatot", "Nora"], 3)):
            own = _side(
                "rally",
                leads={"Infantry": "Gisela", "Lancer": "", "Marksman": ""},
                joiners=joiners,
                widgets_in_panel=True,
            )
            enemy = _side(
                "garrison",
                leads={"Infantry": "", "Lancer": "Karol", "Marksman": "Vulcanus"},
                joiners=[""],
                widgets_in_panel=True,
            )
            own.panel_is_final = True
            enemy.panel_is_final = True
            con = construct.build(Matchup(own, enemy), apply_legacy_skills=False)
            skills = skill_defs_from_matchup(con, {"engine": "turn"})
            names = [s.owner for s in skills if s.role == "joiner"]
            self.assertEqual(len(names), expected, joiners)   # every copy applies - no dedup
        # magnitude: 4x a stat joiner shifts the joiner-aware strength fold
        # materially more than 1x (stacks, not collapses to one).
        from wos_sim.predictor import winprob

        def ratio(nj):
            o = _side("rally", leads={"Infantry": "Gisela", "Lancer": "", "Marksman": ""},
                      joiners=(["Gatot"] * nj), widgets_in_panel=True)
            e = _side("garrison", leads={"Infantry": "", "Lancer": "Karol", "Marksman": "Vulcanus"},
                      joiners=[""], widgets_in_panel=True)
            o.panel_is_final = True
            e.panel_is_final = True
            return winprob.effective_ratio(construct.build(Matchup(o, e), apply_legacy_skills=False))

        self.assertGreater(ratio(4), ratio(1) + 0.03, "4x joiner must stack well beyond 1x")

    def test_qa_named_static_stat_skills_emit_turn_engine_mods(self):
        book = load_skill_book()
        stacks = {
            troop: TypeStack(troop, 12, 100_000, 100_000,
                             {A: 100.0, D: 100.0, L: 100.0, H: 100.0}, 100.0)
            for troop in TroopType
        }
        cases = [
            ("Seo-yoon", SkillSource.SKILL_1, "attacker", TroopType.INFANTRY, StatType.ATTACK, 0.25),
            ("Elif", SkillSource.SKILL_1, "defender", TroopType.INFANTRY, StatType.ATTACK, -0.25),
            ("Elif", SkillSource.SKILL_2, "attacker", TroopType.LANCER, StatType.ATTACK, 0.15),
            ("Elif", SkillSource.SKILL_2, "attacker", TroopType.MARKSMAN, StatType.DEFENSE, 0.10),
            ("Cara", SkillSource.SKILL_1, "defender", TroopType.MARKSMAN, StatType.LETHALITY, -0.20),
            ("Cara", SkillSource.SKILL_2, "attacker", TroopType.LANCER, StatType.ATTACK, 0.30),
            ("Jeronimo", SkillSource.SKILL_2, "attacker", TroopType.MARKSMAN, StatType.ATTACK, 0.25),
        ]
        for hero, source, side, troop, stat, expected in cases:
            with self.subTest(hero=hero, source=source.value, troop=troop.value, stat=stat.value):
                rows = tuple(row for row in book.for_hero(hero) if row.source == source)
                skill = _make_hero_skill(hero, source, rows, "attacker",
                                         "captain", troop, 0)
                mods = pvp_turn_engine._passive_mods([skill], stacks, stacks)
                self.assertAlmostEqual(mods.stat[(side, troop, stat)], expected)

    def test_static_hero_stat_skills_stack_multiplicatively(self):
        book = load_skill_book()
        stacks = {
            troop: TypeStack(troop, 12, 100_000, 100_000,
                             {A: 100.0, D: 100.0, L: 100.0, H: 100.0}, 100.0)
            for troop in TroopType
        }
        skills = []
        for hero, source in (
            ("Seo-yoon", SkillSource.SKILL_1),
            ("Gregory", SkillSource.SKILL_1),
            ("Jeronimo", SkillSource.SKILL_2),
        ):
            rows = tuple(row for row in book.for_hero(hero) if row.source == source)
            skills.append(_make_hero_skill(hero, source, rows, "attacker",
                                           "captain", TroopType.INFANTRY, len(skills)))
        mods = pvp_turn_engine._passive_mods(skills, stacks, stacks)
        factor = 1.0 + mods.stat[("attacker", TroopType.INFANTRY, StatType.ATTACK)]
        self.assertAlmostEqual(factor, 1.25 * 1.15 * 1.25)

    def test_all_troop_attack_chance_modifiers_roll_per_attack(self):
        class SeqRng:
            def __init__(self, values):
                self.values = iter(values)

            def random(self):
                return next(self.values)

        book = load_skill_book()
        stacks = {troop: TypeStack(troop, 12, 100_000, 100_000, {}, 100)
                  for troop in TroopType}
        cases = [
            ("Alonso", SkillSource.SKILL_2, TroopType.MARKSMAN),
            ("Greg", SkillSource.SKILL_2, TroopType.INFANTRY),
            ("Rufus", SkillSource.SKILL_3, TroopType.MARKSMAN),
        ]
        for hero, source, troop in cases:
            with self.subTest(hero=hero, source=source.value):
                rows = tuple(row for row in book.for_hero(hero) if row.source == source)
                skill = _make_hero_skill(hero, source, rows, "attacker",
                                         "captain", troop, 0)
                self.assertEqual(len(_trigger_count_for_skill(
                    skill, 1, stacks, 0, SeqRng([0.1, 0.9, 0.1]), {})), 2)
                self.assertEqual(len(_trigger_count_for_skill(
                    skill, 1, stacks, 0, SeqRng([0.9, 0.9, 0.9]), {})), 0)
                self.assertEqual(len(_trigger_count_for_skill(
                    skill, 1, stacks, 0, SeqRng([0.1, 0.1, 0.1]), {})), 3)

    def test_all_troop_effect_receivers_do_not_imply_all_troop_triggers(self):
        class SeqRng:
            def __init__(self, values):
                self.values = iter(values)

            def random(self):
                return next(self.values)

        book = load_skill_book()
        stacks = {troop: TypeStack(troop, 12, 100_000, 100_000, {}, 100)
                  for troop in TroopType}
        cases = [
            ("Gisela", SkillSource.SKILL_2, TroopType.INFANTRY),
            ("Gisela", SkillSource.SKILL_3, TroopType.INFANTRY),
            ("Hector", SkillSource.SKILL_1, TroopType.INFANTRY),
            ("Philly", SkillSource.SKILL_3, TroopType.LANCER),
            ("Molly", SkillSource.SKILL_1, TroopType.INFANTRY),
        ]
        for hero, source, troop in cases:
            with self.subTest(hero=hero, source=source.value):
                rows = tuple(row for row in book.for_hero(hero) if row.source == source)
                skill = _make_hero_skill(hero, source, rows, "attacker",
                                         "captain", troop, 0)
                self.assertEqual(
                    _trigger_count_for_skill(skill, 1, stacks, 0, SeqRng([0.1]), {}),
                    [troop],
                )
                self.assertEqual(
                    _trigger_count_for_skill(skill, 1, stacks, 0, SeqRng([0.9]), {}),
                    [],
                )

    def test_same_skill_duration_reproc_refreshes_instead_of_stacking(self):
        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Greg")
                     if row.source == SkillSource.SKILL_2)
        skill = _make_hero_skill("Greg", SkillSource.SKILL_2, rows,
                                 "attacker", "captain", TroopType.INFANTRY, 0)
        stacks = {troop: TypeStack(troop, 12, 100_000, 100_000, {}, 100)
                  for troop in TroopType}
        active = []
        pvp_turn_engine._add_active_effect(
            active, pvp_turn_engine._ActiveEffect(skill, 1, 2))
        pvp_turn_engine._add_active_effect(
            active, pvp_turn_engine._ActiveEffect(skill, 2, 3))
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].expires_after, 3)
        mods = pvp_turn_engine._build_mods(
            pvp_turn_engine._Mods(), active, 2, stacks, stacks)
        self.assertAlmostEqual(
            mods.normal_dd[("defender", TroopType.INFANTRY)],
            -0.50,
        )

    def test_damage_modifier_view_is_floored_at_zero_multiplier(self):
        stack = TypeStack(TroopType.INFANTRY, 12, 100_000, 100_000,
                          {A: 100.0, D: 100.0, L: 100.0, H: 100.0}, 100.0)
        mods = pvp_turn_engine._Mods()
        mods.add_dd("attacker", TroopType.INFANTRY, -1.5)
        view = pvp_turn_engine._stack_view(stack, "attacker", mods)
        self.assertEqual(view.dd, -1.0)

    def test_lynn_skill_1_is_one_shared_damage_dealt_buff_not_damage_packets(self):
        class SeqRng:
            def __init__(self, values):
                self.values = iter(values)

            def random(self):
                return next(self.values)

        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Lynn")
                     if row.source == SkillSource.SKILL_1)
        skill = _make_hero_skill("Lynn", SkillSource.SKILL_1, rows,
                                 "attacker", "captain", TroopType.MARKSMAN, 0)
        stacks = {troop: TypeStack(troop, 12, 100_000, 100_000, {}, 100)
                  for troop in TroopType}
        self.assertFalse(skill.deals_damage)
        self.assertEqual(
            _trigger_count_for_skill(skill, 1, stacks, 0, SeqRng([0.1]), {}),
            [TroopType.MARKSMAN],
        )
        active = [pvp_turn_engine._ActiveEffect(skill, 1, 1)]
        mods = pvp_turn_engine._build_mods(
            pvp_turn_engine._Mods(), active, 1, stacks, stacks)
        self.assertAlmostEqual(
            mods.normal_dd[("attacker", TroopType.INFANTRY)],
            0.50,
        )

    def test_next_attack_damage_taken_rows_are_routed_to_packets(self):
        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Blanchette")
                     if row.source == SkillSource.SKILL_3)
        skill = _make_hero_skill("Blanchette", SkillSource.SKILL_3, rows,
                                 "attacker", "captain", TroopType.MARKSMAN, 0)
        astat = {A: 100.0, D: 100.0, L: 100.0, H: 100.0}
        own = {troop: TypeStack(troop, 12, 100_000, 100_000, dict(astat), 100)
               for troop in TroopType}
        enemy = {troop: TypeStack(troop, 12, 100_000, 100_000, dict(astat), 100)
                 for troop in TroopType}
        packets = pvp_turn_engine._skill_packets(
            skill, [TroopType.MARKSMAN], own, enemy, pvp_turn_engine._Mods(),
            dict(pvp_turn_engine.BEST_PARAMS), 1.0, 1.0, 1.0, 1.0)
        self.assertEqual(
            {pkt.target_types for pkt in packets},
            {(TroopType.LANCER,), (TroopType.MARKSMAN,)},
        )
        self.assertTrue(all(pkt.magnitude > 0 for pkt in packets))

    def test_non_target_next_attack_dt_rows_fold_into_direct_packets(self):
        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Gwen")
                     if row.source == SkillSource.SKILL_2)
        no_dt_rows = tuple(row for row in rows
                           if not pvp_turn_engine._is_next_attack_dt_row(row))
        skill = _make_hero_skill("Gwen", SkillSource.SKILL_2, rows,
                                 "attacker", "captain", TroopType.LANCER, 0)
        no_dt_skill = _make_hero_skill("Gwen", SkillSource.SKILL_2, no_dt_rows,
                                       "attacker", "captain", TroopType.LANCER, 0)
        astat = {A: 100.0, D: 100.0, L: 100.0, H: 100.0}
        own = {troop: TypeStack(troop, 12, 100_000, 100_000, dict(astat), 100)
               for troop in TroopType}
        enemy = {troop: TypeStack(troop, 12, 100_000, 100_000, dict(astat), 100)
                 for troop in TroopType}
        params = dict(pvp_turn_engine.BEST_PARAMS)
        with_dt = pvp_turn_engine._skill_packets(
            skill, [TroopType.INFANTRY], own, enemy, pvp_turn_engine._Mods(),
            params, 1.0, 1.0, 1.0, 1.0)
        without_dt = pvp_turn_engine._skill_packets(
            no_dt_skill, [TroopType.INFANTRY], own, enemy, pvp_turn_engine._Mods(),
            params, 1.0, 1.0, 1.0, 1.0)
        self.assertAlmostEqual(
            sum(pkt.magnitude for pkt in with_dt)
            / sum(pkt.magnitude for pkt in without_dt),
            1.15,
        )

    def test_target_text_rows_are_normalized_to_target_receiver(self):
        book = load_skill_book()
        cases = [
            ("Rufus", SkillSource.SKILL_2),
            ("Mia", SkillSource.SKILL_1),
            ("Dominic", SkillSource.SKILL_2),
        ]
        for hero, source in cases:
            with self.subTest(hero=hero, source=source.value):
                rows = tuple(row for row in book.for_hero(hero) if row.source == source)
                target_rows = [
                    row for row in rows
                    if row.attribute == SkillAttribute.DAMAGE_TAKEN
                    and row.side == AffectingSide.FOE
                    and row.amount_per_proc != 0
                ]
                self.assertEqual(len(target_rows), 1)
                self.assertEqual(target_rows[0].receiver, EffectReceiver.TARGET)

    def test_hector_skill_3_is_discrete_damage_proc_not_passive_ev(self):
        class SeqRng:
            def __init__(self, values):
                self.values = iter(values)

            def random(self):
                return next(self.values)

        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Hector")
                     if row.source == SkillSource.SKILL_3)
        skill = _make_hero_skill("Hector", SkillSource.SKILL_3, rows,
                                 "attacker", "captain", TroopType.INFANTRY, 0)
        stacks = {troop: TypeStack(troop, 12, 100_000, 100_000, {}, 100)
                  for troop in TroopType}
        self.assertFalse(skill.is_passive)
        self.assertTrue(skill.deals_damage)
        self.assertEqual(len(_trigger_count_for_skill(
            skill, 1, stacks, 0, SeqRng([0.1, 0.9, 0.1]), {})), 2)

    def test_raw_widget_rows_are_filtered_by_battle_context(self):
        def widget_slots(role, hero):
            side = SideProfile(
                role=role,
                troops_total=1000,
                panel=_panel(),
                formation={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0},
                lead_heroes={"Infantry": hero},
                widgets_in_panel=False,
            )
            foe = SideProfile(
                role="garrison" if role == "rally" else "rally",
                troops_total=1000,
                panel=_panel(),
                formation={"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0},
                widgets_in_panel=False,
            )
            con = construct.build(Matchup(side, foe), apply_legacy_skills=False)
            return [skill for skill in skill_defs_from_matchup(con, {"engine": "turn"})
                    if skill.owner == hero and skill.slot == "widget"]

        self.assertEqual(widget_slots("rally", "Elif"), [])
        self.assertEqual(len(widget_slots("garrison", "Elif")), 1)
        self.assertEqual(len(widget_slots("rally", "Vulcanus")), 1)
        self.assertEqual(widget_slots("garrison", "Vulcanus"), [])

    def test_next_attack_duration_rows_are_not_whole_turn_mods(self):
        book = load_skill_book()
        rows = tuple(row for row in book.for_hero("Vulcanus")
                     if row.source == SkillSource.SKILL_2)
        skill = _make_hero_skill("Vulcanus", SkillSource.SKILL_2, rows,
                                 "attacker", "captain", TroopType.MARKSMAN, 0)
        active = [pvp_turn_engine._ActiveEffect(skill, 1, 1)]
        mods = pvp_turn_engine._build_mods(
            pvp_turn_engine._Mods(), active, 1, {}, {})
        self.assertEqual(mods.skill_dt, {})

        astat = {A: 100.0, D: 100.0, L: 100.0, H: 100.0}
        own = {troop: TypeStack(troop, 12, 100_000, 100_000, dict(astat), 100)
               for troop in TroopType}
        enemy = {troop: TypeStack(troop, 12, 100_000, 100_000, dict(astat), 100)
                 for troop in TroopType}
        params = dict(pvp_turn_engine.BEST_PARAMS)
        with_target = pvp_turn_engine._skill_packets(
            skill, [TroopType.MARKSMAN], own, enemy, pvp_turn_engine._Mods(),
            params, 1.0, 1.0, 1.0, 1.0)[0].magnitude
        no_target_rows = tuple(row for row in rows if row.receiver != EffectReceiver.TARGET)
        no_target_skill = _make_hero_skill(
            "Vulcanus", SkillSource.SKILL_2, no_target_rows,
            "attacker", "captain", TroopType.MARKSMAN, 0)
        without_target = pvp_turn_engine._skill_packets(
            no_target_skill, [TroopType.MARKSMAN], own, enemy,
            pvp_turn_engine._Mods(), params, 1.0, 1.0, 1.0, 1.0)[0].magnitude
        self.assertAlmostEqual(with_target / without_target, 1.15, places=6)

    def test_captain_skill_can_trigger_when_slot_troop_is_absent(self):
        rows = tuple(row for row in load_skill_book().for_hero("Vulcanus")
                     if row.source == SkillSource.SKILL_3)
        skill = _make_hero_skill("Vulcanus", SkillSource.SKILL_3, rows,
                                 "defender", "captain", TroopType.MARKSMAN, 0)
        astat = {A: 100.0, D: 100.0, L: 100.0, H: 100.0}
        stacks = {
            TroopType.INFANTRY: TypeStack(
                TroopType.INFANTRY, 6, 200, 200, dict(astat), 100),
        }
        triggers = _trigger_count_for_skill(
            skill, 1, stacks, 0, random.Random(0), {})
        self.assertTrue(triggers)


class TestPacketConservation(unittest.TestCase):
    def test_skill_packet_kills_are_real_casualties(self):
        skill = SkillDef("Test Burst", "attacker", "skill_1", "captain",
                         TroopType.INFANTRY, source_id="skill:test",
                         deals_damage=True)
        stacks = {
            TroopType.INFANTRY: TypeStack(TroopType.INFANTRY, 11, 100, 100, {}, 1),
            TroopType.LANCER: TypeStack(TroopType.LANCER, 11, 100, 100, {}, 1),
            TroopType.MARKSMAN: TypeStack(TroopType.MARKSMAN, 11, 100, 100, {}, 1),
        }
        casualties, by_source = apply_packets([
            DamagePacket("auto", "attacker", 120),
            DamagePacket(skill, "attacker", 60),
        ], stacks)
        self.assertEqual(casualties[TroopType.INFANTRY], 100)
        self.assertEqual(casualties[TroopType.LANCER], 80)
        self.assertEqual(by_source["auto"], 120)
        self.assertEqual(by_source["skill:test"], 60)
        self.assertEqual(skill.kills, 60)


class TestTroopSkillRuntime(unittest.TestCase):
    def test_no_proc_crystal_lance_does_not_leak_passive_damage(self):
        attacker = [_unit(TroopType.LANCER)]
        defender = [_unit(TroopType.INFANTRY)]
        params = {"rate": 20.0, "def_k": 0.0, "crystal_lance_proc": 0.0}
        base = simulate_turns(attacker, defender, [], params=params,
                              rng=random.Random(1), max_turns=1)
        lance = _make_troop_skill(_troop_skill("Crystal Lance II"), "attacker", 0)
        with_skill = simulate_turns(attacker, defender, [lance], params=params,
                                    rng=random.Random(1), max_turns=1)
        self.assertAlmostEqual(
            base.d_incap[TroopType.INFANTRY],
            with_skill.d_incap[TroopType.INFANTRY],
            places=6,
        )
        self.assertEqual(lance.triggers, 0)
        self.assertEqual(lance.kills, 0)

    def test_ambush_proc_zero_suppresses_ambusher(self):
        attacker = [_unit(TroopType.LANCER)]
        defender = [
            _unit(TroopType.INFANTRY, n=1_000_000),
            _unit(TroopType.MARKSMAN, n=100_000),
        ]
        ambusher = _make_troop_skill(_troop_skill("Ambusher"), "attacker", 0)
        off = simulate_turns(attacker, defender, [ambusher],
                             params={"rate": 100.0, "def_k": 0.0, "ambush_proc": 0.0},
                             rng=random.Random(2), max_turns=1)
        self.assertEqual(ambusher.triggers, 0)
        self.assertEqual(off.d_incap[TroopType.MARKSMAN], 0)

        ambusher = _make_troop_skill(_troop_skill("Ambusher"), "attacker", 0)
        on = simulate_turns(attacker, defender, [ambusher],
                            params={"rate": 100.0, "def_k": 0.0, "ambush_proc": 1.0},
                            rng=random.Random(2), max_turns=1)
        self.assertEqual(ambusher.triggers, 1)
        self.assertGreater(on.d_incap[TroopType.MARKSMAN], 0)

    def test_volley_records_second_attack_and_rerolls_marksman_procs(self):
        attacker = [_unit(TroopType.MARKSMAN)]
        defender = [_unit(TroopType.INFANTRY, n=1_000_000)]
        volley = _make_troop_skill(_troop_skill("Volley"), "attacker", 0)
        gunpowder = _make_troop_skill(_troop_skill("Crystal Gunpowder II"),
                                      "attacker", 1)
        res = simulate_turns(
            attacker, defender, [volley, gunpowder],
            params={
                "rate": 10.0,
                "def_k": 0.0,
                "volley_proc": 1.0,
                "crystal_gunpowder_proc": 1.0,
            },
            rng=random.Random(3),
            max_turns=1,
        )
        self.assertEqual(volley.triggers, 1)
        self.assertEqual(gunpowder.triggers, 2)
        self.assertEqual(
            res.turn_log[0].attack_events["attacker"][TroopType.MARKSMAN],
            2,
        )


class TestHeroSkillRuntime(unittest.TestCase):
    def test_vulcanus_skill2_uses_direct_damage_cadence(self):
        rows = tuple(e for e in load_skill_book().for_hero("Vulcanus")
                     if e.source == SkillSource.SKILL_2)
        skill = _make_hero_skill("Vulcanus", SkillSource.SKILL_2, rows, "attacker",
                                 "captain", TroopType.MARKSMAN, 0)
        self.assertEqual(_skill_frequency(skill), 5.0)
        self.assertEqual(_skill_trigger_unit(skill), TriggerUnit.STRIKES)

    def test_skill_damage_taken_category_does_not_amplify_base_attacks(self):
        rows = tuple(e for e in load_skill_book().for_hero("Vulcanus")
                     if e.source == SkillSource.SKILL_2)
        vulcanus = _make_hero_skill("Vulcanus", SkillSource.SKILL_2, rows,
                                    "attacker", "captain", TroopType.MARKSMAN, 0)
        attacker = [_unit(TroopType.MARKSMAN, n=100_000)]
        defender = [_unit(TroopType.INFANTRY, n=1_000_000)]
        params = {"rate": 10.0, "def_k": 0.0, "K_skill": 0.0}
        base = simulate_turns(attacker, defender, [], params=params,
                              rng=random.Random(4), max_turns=5)
        with_skill = simulate_turns(attacker, defender, [vulcanus], params=params,
                                    rng=random.Random(4), max_turns=5)
        self.assertAlmostEqual(
            base.d_incap[TroopType.INFANTRY],
            with_skill.d_incap[TroopType.INFANTRY],
            places=6,
        )
        self.assertEqual(vulcanus.triggers, 1)

    def test_cara_bypass_rows_hit_marksman_even_behind_lancer(self):
        rows = tuple(e for e in load_skill_book().for_hero("Cara")
                     if e.source == SkillSource.SKILL_3)
        cara = _make_hero_skill("Cara", SkillSource.SKILL_3, rows, "attacker",
                                "captain", TroopType.MARKSMAN, 0)
        attacker = [_unit(TroopType.MARKSMAN)]
        defender = [
            _unit(TroopType.INFANTRY, n=1_000_000),
            _unit(TroopType.LANCER, n=1_000_000),
            _unit(TroopType.MARKSMAN, n=1_000_000),
        ]
        res = simulate_turns(attacker, defender, [cara],
                             params={"rate": 100.0, "def_k": 0.0, "cara_burst": 5.0},
                             rng=random.Random(4), max_turns=2)
        self.assertGreater(res.d_incap[TroopType.MARKSMAN], 0)
        self.assertGreater(res.d_survivors[TroopType.LANCER], 0)


class TestTurnEngineIntegration(unittest.TestCase):
    def test_predict_turn_engine_emits_per_slot_and_troop_telemetry(self):
        fc = api.predict(_side("rally", widgets_in_panel=False),
                         _side("garrison", widgets_in_panel=False), n=2, seed=3,
                         params={"engine": "turn", "rate": 50.0})
        self.assertEqual(fc.engine_path, "pvp_turn_engine")
        self.assertIsNotNone(fc.skill_telemetry)
        own = fc.skill_telemetry["own"]
        hero_slots = [s["slot"] for row in own if row["kind"] == "hero"
                      for s in row["skills"]]
        self.assertIn("widget", hero_slots)
        troop_skills = [s for row in own if row["kind"] == "hero"
                        for s in row["skills"] if s.get("source") == "troop"]
        self.assertTrue(troop_skills)
        troop_names = [s["name"] for s in troop_skills]
        self.assertIn("Ambusher", troop_names)

    def test_hero_telemetry_groups_all_captain_slots_into_one_row(self):
        fc = api.predict(_side("rally", widgets_in_panel=False),
                         _side("garrison", widgets_in_panel=False), n=1, seed=3,
                         params={"engine": "turn", "rate": 50.0})
        elif_rows = [row for row in fc.skill_telemetry["own"]
                     if row["kind"] == "hero"
                     and row["hero"] == "Elif"
                     and row["role"] == "captain"]
        self.assertEqual(len(elif_rows), 1)
        slots = {skill["slot"] for skill in elif_rows[0]["skills"]
                 if skill.get("source") == "hero"}
        self.assertGreaterEqual(slots, {"skill_1", "skill_2", "skill_3"})
        self.assertNotIn("widget", slots)
        own_slots = [skill["slot"] for row in fc.skill_telemetry["own"]
                     if row["kind"] == "hero"
                     for skill in row["skills"]]
        self.assertIn("widget", own_slots)

    def test_t12_anchor_jsons_are_scoreable_from_report_files(self):
        for filename in ("pvp_t12_report_001.json", "pvp_t12_report_002.json"):
            with self.subTest(filename=filename):
                score = _anchor_score(filename)
                self.assertEqual(score["expected_winner"], "A")
                self.assertIn(score["expected_survivor_troop"], {"Marksman", "Lancer"})
                self.assertIn(score["predicted_winner"], {"A", "D", "mutual"})
                self.assertGreater(score["predicted_turns"], 0)
                self.assertIsInstance(score["predicted_live_survivors"], dict)
                self.assertIsInstance(score["predicted_survivors"], float)


class TestT12AnchorGates(unittest.TestCase):
    def _assert_anchor(self, filename, expected):
        data, res = _anchor_result(filename)
        score = _anchor_score(filename)
        self.assertEqual(score["predicted_winner"], "A")
        self.assertEqual(
            score["predicted_live_survivors"].keys(),
            {expected["survivor_troop"]},
        )
        self.assertEqual(score["predicted_survivor_troop"], expected["survivor_troop"])
        self.assertGreaterEqual(res.turns, expected["turns_min"])
        self.assertLessEqual(res.turns, expected["turns_max"])
        self.assertGreaterEqual(score["predicted_survivors"], expected["survivors_min"])
        self.assertLessEqual(score["predicted_survivors"], expected["survivors_max"])
        self.assertEqual(sum(res.d_survivors.values()), 0)
        for key, want in expected["triggers"].items():
            side, hero, slot = key
            self.assertAlmostEqual(_trigger_count(res, side, hero, slot), want, delta=1)
        for side, wanted_deaths in expected["death_turns"].items():
            actual = _death_turns(res, side)
            for troop, turn in wanted_deaths.items():
                self.assertIn(troop, actual)
                self.assertAlmostEqual(actual[troop], turn, delta=2)
        self.assertEqual(data["attacker"]["survivors"], expected["reported_survivors"])

    @unittest.expectedFailure
    def test_report_001_g1_to_g7_anchor_acceptance(self):
        self._assert_anchor("pvp_t12_report_001.json", {
            "survivor_troop": "Marksman",
            "reported_survivors": 62_364,
            "turns_min": 15,
            "turns_max": 17,
            "survivors_min": 30_000,
            "survivors_max": 110_000,
            "triggers": {
                ("attacker", "Elif", "skill_3"): 12,
                ("defender", "Elif", "skill_3"): 15,
                ("defender", "Cara", "skill_3"): 6,
                ("attacker", "Vulcanus", "skill_2"): 7,
                ("attacker", "Vulcanus", "skill_3"): 6,
            },
            "death_turns": {
                "attacker": {"Infantry": 12, "Lancer": 14},
                "defender": {"Marksman": 12, "Infantry": 15, "Lancer": 16},
            },
        })

    @unittest.expectedFailure
    def test_report_002_g1_to_g7_anchor_acceptance(self):
        self._assert_anchor("pvp_t12_report_002.json", {
            "survivor_troop": "Lancer",
            "reported_survivors": 118_068,
            "turns_min": 23,
            "turns_max": 27,
            "survivors_min": 60_000,
            "survivors_max": 190_000,
            "triggers": {
                ("attacker", "Elif", "skill_3"): 19,
                ("defender", "Elif", "skill_3"): 22,
                ("defender", "Cara", "skill_3"): 9,
                ("attacker", "Vulcanus", "skill_2"): 10,
                ("attacker", "Vulcanus", "skill_3"): 9,
            },
            "death_turns": {
                "attacker": {"Marksman": 14, "Infantry": 19},
                "defender": {"Marksman": 18, "Infantry": 22},
            },
        })


class TestSourceAuditHelpers(unittest.TestCase):
    def test_wiki_token_parser_extracts_max_level_mechanics(self):
        text = ("Alonso grants all troops' attack a 20% chance of reducing damage "
                "dealt by 10%/20%/30%/40%/50% for all enemy troops for 2 turns.")
        tokens = wiki_tokens(text)
        self.assertIn("20% chance", tokens)
        self.assertIn("50%", tokens)
        self.assertIn("for 2 turns", tokens)

    def test_wiki_token_parser_handles_ladders_with_one_percent_sign(self):
        tokens = wiki_tokens("increasing Troops' Attack by 3/6/9/12/15%")
        self.assertIn("15%", tokens)
        self.assertNotIn("5%", tokens)

    def test_workbook_tokens_extract_runtime_fields(self):
        row = next(e for e in load_skill_book().for_hero("Alonso")
                   if e.source == SkillSource.SKILL_2)
        tokens = workbook_tokens([row])
        self.assertIn("20% chance", tokens)
        self.assertIn("50%", tokens)


if __name__ == "__main__":
    unittest.main()
