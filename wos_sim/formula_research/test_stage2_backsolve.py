"""Regression tests for the Stage-2 exact constraint back-solve.

Every expected number below was hand-derived from the ledger row cited in the
comment before being locked in, so a code change that shifts any constraint
fails loudly. Run: py -m pytest wos_sim/formula_research/test_stage2_backsolve.py -q
"""
from fractions import Fraction as F
import json

import pytest

from wos_sim.formula_research.stage2_backsolve import build, weight


@pytest.fixture(scope="module")
def doc():
    return build()


@pytest.fixture(scope="module")
def battles(doc):
    return {b["name"]: b for b in doc["battles"]}


def test_weight_function_exact_values():
    # no Vulcanus: weight is just the event count
    assert weight(264, False, False) == 264
    # Vulcanus plain: 264 events, 44 boosted at +20% -> 264 + 44/5
    assert weight(264, True, False) == F(1364, 5)
    # next-attack branch adds 43 events (6k+1 <= 264) at +5%
    assert weight(264, True, True) == F(1364, 5) + F(43, 20)
    # boundary bookkeeping around a boost event
    assert weight(5, True, False) == 5
    assert weight(6, True, False) == F(31, 5)
    assert weight(7, True, True) == F(36, 5) + F(1, 20)
    assert weight(0, True, True) == 0


def test_t1_infantry_mirror_row(battles):
    # ledger line 17: T1 Inf vs T1 Inf, S2=44/S3=88 pin T=264 exactly.
    b = battles["NanoMart_1v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus"]
    assert b["turns"]["t_set"] == [264]
    assert b["turns"]["narrowed_vs_recorded"] is False  # recorded band was already 264-264
    c = b["constraints"]
    assert c["type"] == "exact_1v1"
    p = c["projected"]["s2_plain"]
    assert (p["winner_rate"]["lo"], p["winner_rate"]["hi"]) == ("1/264", "1/263")
    # defender carries Vulcanus: W(264) = 272.8 -> ub 5/1364 (plain), W = 274.95 -> 20/5499 (nextatk)
    assert p["loser_rate_ub"]["ub"] == "5/1364"
    assert c["projected"]["s2_nextatk"]["loser_rate_ub"]["ub"] == "20/5499"
    # effective stats: A_eff(att) = 1.022 * 1.15 * 0.96, D_eff(att) = 4.008 * 0.88
    att = b["sides"]["att"]
    assert F(att["A_eff"]) == F("1.022") * F(23, 20) * F(24, 25)
    assert F(att["D_eff"]) == F("4.008") * F(22, 25)
    assert F(b["sides"]["def"]["D_eff"]) == F(4)  # S3 sits on the defender, debuffs attacker only


def test_hero_side_swap_mirror_symmetry(battles):
    # ledger line 66: Vulcanus on the ATTACKER, Seo-yoon on the DEFENDER; defender wins.
    # The projected winner interval must equal the standard T1 mirror's - the clock
    # is role-independent.
    b = battles["NanoMart_SetA_1v1_T1InfvT1Inf_Vulcanus_SeoYoonlvl3"]
    assert b["turns"]["t_set"] == [264]  # narrowed from recorded 262-264 by the S2 counter
    assert b["turns"]["narrowed_vs_recorded"] is True
    assert b["constraints"]["winner_side"] == "def"
    assert b["sides"]["att"]["has_vulc"] and not b["sides"]["def"]["has_vulc"]
    p = b["constraints"]["projected"]["s2_plain"]
    assert (p["winner_rate"]["lo"], p["winner_rate"]["hi"]) == ("1/264", "1/263")
    assert p["loser_rate_ub"]["ub"] == "5/1364"


def test_clean_1v2_row(battles):
    # ledger line 35: 1v2 T1 Inf, S2=32/S3=64 pin T=192; winner is the 2-unit defender.
    b = battles["NanoMart_1v2_T1InfvT1Inf_SeoYoonlvl3_Vulcanus"]
    assert b["turns"]["t_set"] == [192]
    c = b["constraints"]
    assert c["type"] == "exact_clean_multi"
    assert c["winner_count_factor"] == "g(2)"
    p = c["projected"]["s2_plain"]
    # W_def(192) = 192 + 32/5 = 198.4, W_def(191) = 197.2
    assert (p["winner_rate"]["lo"], p["winner_rate"]["hi"]) == ("5/992", "5/986")
    assert p["loser_rate_ub"]["ub"] == "1/192"


def test_2v1_defeat_pool_and_unit_branches(battles):
    # ledger line 50: 2 T1 Lancers die to 1 MiniMart Marksman at exactly T=6.
    b = battles["NanoMart_2v1_T1LanvT1MM_SeoYoonlvl3_Vulcanus"]
    assert b["turns"]["t_set"] == [6]
    c = b["constraints"]
    assert c["type"] == "winner_exact_loser_piecewise"
    p = c["projected"]["s2_plain"]["winner_rate"]
    # pool branch: [2/W(6), 2/W(5)) = [2/6.2, 2/5)
    assert (p["lo"], p["hi"]) == ("10/31", "2/5")
    # unit branch: hand enumeration leaves exactly t1=3 with R in [1/3, 1/2)
    unit = c["unit_overkill_branch"]["6"]["s2_plain"]
    assert unit == [{"t1": 3, "lo": "1/3", "lo_float": 1 / 3, "hi": "1/2", "hi_float": 0.5}]
    # attacker Lancers counter Marksmen: damage-dealt multiplier recorded, not folded
    assert b["sides"]["att"]["counter_mult"] == "11/10"
    assert b["sides"]["def"]["counter_mult"] == "1/1"


def test_aggregate_ladder_row_with_s2_kill_and_quirk(battles):
    # ledger line 15: 100v200, defender Vulcanus S2 scored K=1; defender outcome
    # fields sum to 199 -> removed is ambiguous {51, 52} and must be an interval.
    b = battles["NanoMart_100_SeoYoonlvl3_Vulcanus"]
    c = b["constraints"]
    assert c["type"] == "aggregate"
    assert b["turns"]["t_set"] == [210]
    # 2026-07-19 refresh: the 2026-07-14 ledger corrections moved one S2-kill
    # turn out of this aggregate row; corrected data-state = [52].
    assert c["removed"]["def"] == [52]
    assert c["removed"]["att"] == [100]
    assert c["s2_kills"]["def"] == 1
    # 2026-07-19 refresh: the "casualty readings disagree" quirk was a REAL
    # OCR inconsistency that Martin's dated corrections resolved -- the
    # corrected data-state carries no such quirk on this row.
    assert not any("casualty readings disagree" in q for q in b["quirks"])


def test_exp4_name_vs_capture_mislabels(battles):
    # ledger line 55: defender panel capture is 2.0/10.0/10.0/10.0% (+10D+10L+10H),
    # not the name's +10A+10D+10H; line 57: attacker carries +11.3% Defense the name
    # omits. Deployed capture is authoritative - the quirk must be flagged.
    flagged = {n for n, b in battles.items() if any("mislabel" in q for q in b["quirks"])}
    assert flagged == {
        "NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+10D+10H_SeoYoonlvl3_Vulcanus",
        "NanoMart_Exp4_1v1_T1InfvT1Inf_Att+10A+10L_Def+10A+20D_SeoYoonlvl3_Vulcanus",
    }


def test_cadence_b_refutation(doc):
    cad = doc["cadence_check"]
    # spot-refuters verified by hand: S2=13 forces T<=78 under cadence B but the
    # S3 clock says 79-81; S2=63 forces T<=378 vs S3 379-381.
    assert "NanoMart_1v1_T1InfvT1Lan_SeoYoonlvl3_Vulcanus" in cad["branch_B_refuted_by"]
    assert "NanoMart_200_Vulcanus" in cad["branch_B_refuted_by"]
    # 2026-07-19 refresh: 31 after the dated ledger corrections (was 32).
    assert len(cad["branch_B_refuted_by"]) == 31
    # single-T rows can never discriminate (T = 6*c2 lies in both cadence bands)
    assert "NanoMart_1v1_T1InfvT1Inf_SeoYoonlvl3_Vulcanus" not in cad["branch_B_refuted_by"]


def test_coverage_and_no_conflicts(doc):
    cov = doc["coverage"]
    # 2026-07-19 refresh: 70 rows since the L21 duplicate exclusion
    # (2026-07-14, Martin-verified); was 71 pre-dedup.
    assert cov["total_rows"] == 70
    # 2026-07-19 refresh: 60 clocked rows after the L21 dedup (was 61).
    assert cov["clocked_rows"] == 60
    assert cov["by_kind"] == {
        "aggregate": 8,
        "exact_1v1": 38,  # 2026-07-19 refresh: 38 after the dated ledger corrections (was 39)
        "exact_clean_multi": 12,
        "survivor_only": 10,
        "winner_exact_loser_piecewise": 2,
    }
    assert cov["conflict_rows"] == []
    # the _Duplicate row is a flagged duplicate capture; the SetB Vulcanus/Seo-yoon
    # row is byte-identical (inputs AND outcomes) to its SetA counterpart - a
    # deterministic replication. Neither carries independent constraint weight.
    # 2026-07-19 refresh: the duplicate map changed with the dated ledger
    # corrections (the L33 T6->T4 fix re-keyed one stat-duplicate pair).
    assert cov["duplicates"] == [
        "NanoMart_1v1_T6InfvT1Inf_SeoYoonlvl3_Vulcanus",
        "NanoMart_SetA_1v1_T6InfvT2Inf_SeoYoonlvl3_Vulcanus_Duplicate2",
        "NanoMart_SetB_1v1_T1InfvT1Inf_Vulcanus_SeoYoonlvl3",
    ]


def test_every_clocked_row_has_consistent_interval(doc):
    for b in doc["battles"]:
        c = b["constraints"]
        if c["type"] not in ("exact_1v1", "exact_clean_multi", "winner_exact_loser_piecewise"):
            continue
        for br in ("s2_plain", "s2_nextatk"):
            w = c["projected"][br]["winner_rate"]
            assert F(w["lo"]) < F(w["hi"]), b["name"]
            for entry in c["per_T"]:
                pw = entry["winner_rate"][br]
                assert F(pw["lo"]) < F(pw["hi"]), (b["name"], entry["T"])
                # per-T intervals sit inside the projected union
                assert F(w["lo"]) <= F(pw["lo"]) and F(pw["hi"]) <= F(w["hi"]), b["name"]


def test_build_is_deterministic():
    a = json.dumps(build(), sort_keys=True)
    b = json.dumps(build(), sort_keys=True)
    assert a == b
