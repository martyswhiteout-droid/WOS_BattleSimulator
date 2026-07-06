"""First aggregate kernel fit across all ingested reports.

Model (wall-centric, per Martin): each side's grind rate
    G = sum_c  k_c * N_c^e * Atk_c * Leth_c^b * (1+dd_c)
        / (WallDef * WallHP) * (1 + wall_dt)
where c runs over the side's classes, the wall is the enemy's Infantry
(effective stats), dd/dt come from the assembled skill boards, and
k_Infantry / k_Lancer are class output coefficients (k_Marksman = 1).

Observations per report:
  * damage ratio  R = incap(attacker) / incap(defender)  -> G_def / G_atk
  * within-side class kill-share ratios (pro-rata kills across available
    participant rows), which cancel the wall and isolate k_c/N^e/stats.

Fit e, k_I, k_L (and optionally lethality weight b) by log-least-squares.
Run:  py -m wos_sim.fit_kernel
"""

import math
from itertools import product

from .assemble import assemble_battle
from .loader import load_skill_book
from .models import StatType, TroopType
from .reports import load_all_reports

book = load_skill_book()

# excluded reports (data issues); r8's specials remain anomaly-flagged but
# its flags are complete, so it is included with as-displayed specials
INCOMPLETE = set()

cases = []
for r in load_all_reports():
    if r.report_id in INCOMPLETE:
        continue
    atk_s, def_s, _ = assemble_battle(r, book)
    sides = {}
    for tag, ss, rs, other in (("atk", atk_s, r.attacker, def_s),
                               ("def", def_s, r.defender, atk_s)):
        classes = {}
        for t in TroopType:
            cl = ss.classes[t]
            if cl.count <= 0:
                continue
            classes[t] = {
                "n": cl.count,
                "atk": cl.effective(StatType.ATTACK),
                "leth": cl.effective(StatType.LETHALITY),
                "dd": cl.damage_dealt,
            }
        wall = other.classes[TroopType.INFANTRY]
        kills = {}
        for p in rs.participants:
            for row in p.rows:
                kills[row.troop_type] = kills.get(row.troop_type, 0) + row.kills
        sides[tag] = {
            "classes": classes,
            "wall_def": wall.effective(StatType.DEFENSE),
            "wall_hp": wall.effective(StatType.HEALTH),
            "wall_dt": wall.damage_taken,
            "incap": rs.troops - rs.survivors,
            "kills": kills,
        }
    cases.append((r.report_id, sides))


def grind(side, e, kI, kL, b):
    coeff = {TroopType.INFANTRY: kI, TroopType.LANCER: kL, TroopType.MARKSMAN: 1.0}
    total = 0.0
    for t, c in side["classes"].items():
        total += (coeff[t] * c["n"] ** e * c["atk"] * c["leth"] ** b * (1 + c["dd"]))
    return total / (side["wall_def"] * side["wall_hp"]) * (1 + side["wall_dt"])


def class_term(c, t, e, kI, kL, b):
    coeff = {TroopType.INFANTRY: kI, TroopType.LANCER: kL, TroopType.MARKSMAN: 1.0}
    return coeff[t] * c["n"] ** e * c["atk"] * c["leth"] ** b * (1 + c["dd"])


def loss(e, kI, kL, b, detail=False):
    total, rows = 0.0, []
    for rid, sides in cases:
        # wall-note: grind() uses the OTHER side's wall
        g_atk = grind({**sides["atk"], "wall_def": sides["def"]["wall_def"],
                       "wall_hp": sides["def"]["wall_hp"], "wall_dt": sides["def"]["wall_dt"]},
                      e, kI, kL, b)
        g_def = grind({**sides["def"], "wall_def": sides["atk"]["wall_def"],
                       "wall_hp": sides["atk"]["wall_hp"], "wall_dt": sides["atk"]["wall_dt"]},
                      e, kI, kL, b)
        r_pred = g_def / g_atk
        r_obs = sides["atk"]["incap"] / sides["def"]["incap"]
        total += 2.0 * (math.log(r_pred) - math.log(r_obs)) ** 2
        rows.append((rid, "dmg-ratio", r_obs, r_pred))
        for tag in ("atk", "def"):
            side = sides[tag]
            ks = {t: k for t, k in side["kills"].items() if k > 500
                  and t in side["classes"]}
            ref = (TroopType.MARKSMAN if TroopType.MARKSMAN in ks
                   else TroopType.LANCER if TroopType.LANCER in ks else None)
            if ref is None:
                continue
            for t, k in ks.items():
                if t == ref:
                    continue
                obs = k / ks[ref]
                pred = (class_term(side["classes"][t], t, e, kI, kL, b)
                        / class_term(side["classes"][ref], ref, e, kI, kL, b))
                total += (math.log(pred) - math.log(obs)) ** 2
                rows.append((rid, f"{tag}:{t}/{ref}", obs, pred))
    return (total, rows) if detail else total


def sweep(b_values, label):
    best = None
    for e in [x / 100 for x in range(30, 105, 5)]:
        for kI in (0.01, 0.02, 0.04, 0.07, 0.12, 0.2, 0.35, 0.6, 1.0):
            for kL in (0.5, 0.75, 1.0, 1.5, 2.2, 3.2, 4.5, 6.5, 9.0):
                for b in b_values:
                    l = loss(e, kI, kL, b)
                    if best is None or l < best[0]:
                        best = (l, e, kI, kL, b)
    # local refine
    l0, e, kI, kL, b = best
    for de, dkI, dkL, db in product((-0.025, 0, 0.025), (0.8, 1, 1.25),
                                    (0.8, 1, 1.25), (-0.1, 0, 0.1) if len(b_values) > 1 else (0,)):
        l = loss(e + de, kI * dkI, kL * dkL, b + db)
        if l < best[0]:
            best = (l, e + de, kI * dkI, kL * dkL, b + db)
    l0, e, kI, kL, b = best
    print(f"{label}: loss={l0:.3f}  e={e:.3f}  k_Inf={kI:.3f}  k_Lancer={kL:.2f}  leth_weight={b:.2f}")
    return best


print(f"fitting on {len(cases)} reports\n")
best_b1 = sweep([1.0], "equal lethality weight (b=1)  ")
best_bf = sweep([0.4, 0.6, 0.8, 1.0, 1.2, 1.4], "lethality weight free         ")

l, e, kI, kL, b = best_b1 if best_b1[0] <= best_bf[0] * 1.05 else best_bf
print(f"\n=== selected: e={e:.3f}, k_Inf={kI:.3f}, k_Lancer={kL:.2f}, b={b:.2f} ===")
_, rows = loss(e, kI, kL, b, detail=True)
print(f"{'report':<32}{'observable':<16}{'observed':>10}{'predicted':>11}")
for rid, kind, obs, pred in rows:
    print(f"{rid[:30]:<32}{kind:<16}{obs:>10.3f}{pred:>11.3f}")
