"""Calibration harness over the controlled beast-hunt experiments.

Run:  py -m wos_sim.calibrate
Loads both beast datasets, builds fully-known stat blocks for every fight
(attacker = recorded account bonuses on T11 FC10 bases; beast units =
interpolated tier stats x (1 + beast bonus)), verifies the beast-power
mapping, and extracts the clean observables for damage-model fitting:

  A. power-mapping check (beast units == interpolated troop tiers)
  B. first-strike single-event kills (one equation each, one unknown k)
  C. N-ladder (exponent), beast-level ladder (mitigation curve),
     wall-ratio curve, determinism spread

The damage model under test (per attack event, side s hitting wall w):
    incapacitated = k * N^e * (Atk_s*Leth_s)^p / (Def_w*HP_w)^q / HP_unit
with (k, e, p, q) fit dials. Extend as evidence demands.
"""

import json
from pathlib import Path

from .models import StatType, TroopType
from .troop_catalog import (interpolated_tier_power, interpolated_tier_stats,
                            troop_base_stats)

DATA = Path(__file__).resolve().parent / "data"
CLASS = {"Inf": TroopType.INFANTRY, "Lan": TroopType.LANCER,
         "Mar": TroopType.MARKSMAN, "Infantry": TroopType.INFANTRY,
         "Lancer": TroopType.LANCER, "Marksman": TroopType.MARKSMAN}


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


marty = load("beast_hunts.json")
marlin = load("beast_hunts_marlinman.json")


def attacker_stats(bonuses, troop: TroopType) -> dict[StatType, float]:
    """Effective stats: T11 FC10 base x (1 + recorded account bonus)."""
    base = troop_base_stats(11, 10, troop)
    b = bonuses[troop.value]
    key = {StatType.ATTACK: "Attack", StatType.DEFENSE: "Defense",
           StatType.LETHALITY: "Lethality", StatType.HEALTH: "Health"}
    return {s: base[s] * (1 + b[key[s]]) for s in StatType}


def beast_group_stats(unit_level: float, troop: TroopType,
                      beast_bonus: float) -> dict[StatType, float]:
    raw = interpolated_tier_stats(unit_level, troop)
    return {s: v * (1 + beast_bonus) for s, v in raw.items()}


def check_power_mapping():
    """Observed beast power-per-unit vs interpolated tier power."""
    print("A. Beast power-per-unit vs interpolated tier power")
    observed = {  # beast: (total power loss on wipe, units)  [wipe reports]
        "Lv5 Arctic Wolf": (660, 195), "Lv8 Arctic Wolf": (3100, 645),
        "Lv10 Musk Ox": (7065, 1070), "Lv13 Giant Tapir": (24100, 2460),
        "Lv15 Giant Tapir": (48620, 3740), "Lv18 Titan Roc": (172900, 8645),
        "Lv20 Titan Roc": (327460, 14115), "Lv25 Giant Elk": (1885940, 49630),
        "Lv30 Snow Leopard": (4429500, 81710),
    }
    for beast, (power, units) in observed.items():
        groups = marlin["beast_catalog"][beast]["groups"]
        pred = sum(n * interpolated_tier_power(lv) for _, lv, n in groups)
        print(f"  {beast:<20} observed/unit {power/units:7.3f}   "
              f"interp-pred {pred/units:7.3f}   "
              f"{'OK' if abs(pred - power)/power < 0.02 else 'CHECK'}")


def first_strike_equations():
    """Single-event observations: 300-mixed vs weak beasts, opening attack."""
    print("\nB. First-strike single-event observations (Marlinman, 100-unit stacks)")
    cases = [
        # (beast, attacking class, stack, units killed in the opening event)
        ("Lv5 Arctic Wolf", TroopType.INFANTRY, 100, 195),
        ("Lv10 Musk Ox", TroopType.INFANTRY, 100, 958),  # accumulated over ~turns, upper bound
    ]
    for beast, troop, n, kills in cases:
        cat = marlin["beast_catalog"][beast]
        # wall = beast front line = its infantry-class group(s)
        inf_groups = [g for g in cat["groups"] if CLASS[g[0]] == TroopType.INFANTRY]
        lv = inf_groups[0][1]
        wall = beast_group_stats(lv, TroopType.INFANTRY, cat["bonus"])
        atk = attacker_stats(marlin["attacker_bonuses"], troop)
        print(f"  {beast:<18} {troop:<9} N={n:<5} killed {kills:>5}  "
              f"| atk A*L={atk[StatType.ATTACK]*atk[StatType.LETHALITY]:9.0f} "
              f"| wall D*H={wall[StatType.DEFENSE]*wall[StatType.HEALTH]:7.1f} "
              f"| unitHP={wall[StatType.HEALTH]:5.2f}")
    print("  -> solve k in: kills = k * N^e * (A*L)^p / (D*H)^q / unitHP")


def ladder_tables():
    print("\nC. Ladders (fit targets)")
    print("  N-ladder (lancers vs Lv25, uncensored defeats):")
    for x in marlin["experiments"]["n_ladder_lancers_vs_Lv25"]:
        if x["result"] == "defeat":
            print(f"    N={x['n']:<6} beast losses {x['beast_losses']:>7,}")
    print("  Beast ladder (300 mixed):")
    for x in marlin["experiments"]["beast_ladder_300mixed"]:
        out = x.get("beast_losses", marlin["beast_catalog"][x["beast"]]["units"])
        print(f"    {x['beast']:<20} {x['result']:<8} beast losses {out:>7,}")
    print("  Wall-ratio (600 lancers + I infantry vs Lv30):")
    for x in marlin["experiments"]["wall_ratio_600lancers_plus_inf_vs_Lv30"]:
        print(f"    inf={x['inf']:<5} beast losses {x['beast_losses']:>6,}")
    spread = [sum(r["own"][1:3]) for r in
              marlin["experiments"]["determinism_5x_100lancers_vs_Lv18"]]
    print(f"  Determinism spread (5x same fight, own incapacitated): {spread}")


if __name__ == "__main__" or True:
    check_power_mapping()
    first_strike_equations()
    ladder_tables()
