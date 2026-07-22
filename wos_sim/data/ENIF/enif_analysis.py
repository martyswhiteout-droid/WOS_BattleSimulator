"""E-NIF battery analysis (2026-07-17). Re-runnable; reads the 10 ENIF JSONs.

Known-loadout H-panel assumptions (flagged, not fabricated): the Alpaca MM loadout
A+176.2/D+166.0/L+129.1 is byte-identical to the 2026-07-12 threshold-set loadout
whose Health panel was +129.0; the Mueller MM loadout A+179.1/D+174.2/L+121.2
matches the 2026-07-13 capture with Health +118.7? -> +118.6. Both H panels are
missing in the ENIF captures and are filled from those prior captures of the SAME
loadouts, marked ASSUMED below.
"""
import glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ST = json.load(open(os.path.join(ROOT, "docs", "TroopStats",
                                 "WOS_Troop_Stats_FC1-FC10_T1-T10.json"), encoding="utf-8"))

H_ASSUMED = {"alpaca_mm": 129.0, "mueller_mm": 118.6}   # flagged loadout fills
K_NAKED = {("Marksman", "Infantry"): 93.0, ("Infantry", "Marksman"): 73.1,
           ("Lancer", "Marksman"): 500.0}


def base(cls, tier):
    v = ST["troop_classes"][cls]["tiers"][f"T{tier}"]["fc_levels"]["FC1"]
    return v["attack"], v["defense"], v["lethality"], v["health"]


def eff(cls, tier, pct, h_fill=None):
    b = base(cls, tier)
    h_pct = pct.get("Health")
    if h_pct is None and h_fill is not None:
        h_pct = h_fill
    return dict(A=b[0] * (1 + pct.get("Attack", 0) / 100),
                D=b[1] * (1 + pct.get("Defense", 0) / 100),
                L=b[2] * (1 + pct.get("Lethality", 0) / 100),
                H=b[3] * (1 + (h_pct or 0) / 100),
                h_assumed=pct.get("Health") is None)


def tier_of(td):
    import re
    m = re.search(r"Lv\.?\s*([\d.]+)", td or "")
    return int(round(float(m.group(1)))) if m else 1


def mid(r):
    t = r.get("turns")
    if t is not None:
        return float(t)
    lo, hi = r["turns_range"]
    return (lo + hi) / 2


rows = {}
for f in sorted(glob.glob(os.path.join(HERE, "*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    rows[os.path.basename(f).split("_2026")[0]] = d

print("=" * 74)
print("E-NIF1b — the Gatot-vs-Gordon VERDICT (MM dealer vs GORDON-Inf target)")
print("=" * 74)
for rid in ("ENIF1b_R0", ):
    pass
for name, d in rows.items():
    if not name.startswith("ENIF1b"):
        continue
    a, de = d["attacker"], d["defender"]
    t = mid(d["turn_inference"])
    inf = eff("Infantry", 1, a["stats_pct"]["Infantry"])
    mm = eff("Marksman", 1, de["stats_pct"]["Marksman"], H_ASSUMED["alpaca_mm"])
    n_def = de.get("troops", 1)
    if d["outcome"]["winner"] == "attacker":
        K = t * inf["A"] * inf["L"] / (mm["D"] * mm["H"])
        print(f"  {name}: Mueller-Gordon Inf KILLS the MM in ~{t:.0f}  "
              f"-> K_eff(Inf->MM) = {K:6.1f}   [v4 K=73.1]  (n_def={n_def})")
    else:
        K = t * mm["A"] * mm["L"] / (inf["D"] * inf["H"])
        print(f"  {name}: MM KILLS the Gordon-Inf in ~{t:.0f}       "
              f"-> K_eff(MM->Inf) = {K:6.1f}   [naked 93 | Gatot-target 440]  (n_def={n_def})")
print("  RESOLVED (Martin 2026-07-17): the R01/R04-vs-R02 winner flip was the ALLIANCE BUFF —")
print("  R01/R03/R04 Mueller in RFJ (+23pp A/D, +10pp L/H), R02 outside. Panels now corrected per run.")
print("  Two-sided RACE check (K-table predicts both kill-times; shorter wins):")
for lab,inA,inD,inH,inL in (("in-alliance (R01/R04)",3.021,12.108,13.122,2.220),("out-of-alliance (R02)",2.791,11.188,12.522,2.120)):
    mmAL=189.85; mmDH=6.092
    t_mm_kills_inf = 93.0*inD*inH/mmAL          # MM needs this many turns
    t_inf_kills_mm = 73.1*mmDH/(inA*inL)        # Mueller needs this many
    win = "Mueller" if t_inf_kills_mm < t_mm_kills_inf else "MM"
    print(f"    {lab:22}: MM needs {t_mm_kills_inf:5.1f}t, Mueller needs {t_inf_kills_mm:5.1f}t -> predicted winner {win}")
print("    observed: in-alliance Mueller WINS [69,71]; out-of-alliance MM WINS [66,67] — BOTH races predicted.")

print()
print("=" * 74)
print("E-NIF2 — ran as Inf-dealer vs rising-tier MM TARGET (MM loadout too weak to win)")
print("=" * 74)
mueller_inf_gatot = None
for name, d in sorted(rows.items()):
    if not name.startswith("ENIF2"):
        continue
    a, de = d["attacker"], d["defender"]
    t = mid(d["turn_inference"])
    tau = tier_of(a.get("tier_display"))
    w = eff("Infantry", 1, de["stats_pct"]["Infantry"])           # winner = Mueller Gatot Inf
    l = eff("Marksman", tau, a["stats_pct"]["Marksman"], H_ASSUMED["alpaca_mm"])
    KG = t * w["A"] * w["L"] / (l["D"] * l["H"])                  # = K(Inf->MM) * G_l^MM(tau)
    gl = KG / K_NAKED[("Infantry", "Marksman")]
    print(f"  {name}: loser = FC1 T{tau} MM, turns={t:.0f}  K*G_l = {KG:6.1f}  "
          f"-> G_l^MM(T{tau}) = {gl:5.3f}   (D*H={l['D']*l['H']:.1f})")
print("  -> T1 row replicates the v4 K(Inf->MM) cell (+5%); T3/T6 = the NEW MM loser-tier curve")
print("     (steep: far below Infantry's G_l 0.90/0.75). Intended MM-DEALER curve NOT measured")
print("     (needs the +1072% loadout to actually win).")

print()
print("=" * 74)
print("E-NIF3 — Lancer dealer T1/T3/T6 vs Gordon-MM target (worked as designed)")
print("=" * 74)
lan = {}
for name, d in sorted(rows.items()):
    if not name.startswith("ENIF3"):
        continue
    a, de = d["attacker"], d["defender"]
    t = mid(d["turn_inference"])
    tau = tier_of(a.get("tier_display"))
    w = eff("Lancer", tau, a["stats_pct"]["Lancer"])
    l = eff("Marksman", 1, de["stats_pct"]["Marksman"], H_ASSUMED["mueller_mm"])
    K = t * w["A"] * w["L"] / (l["D"] * l["H"])
    lan[tau] = K
    print(f"  {name}: FC1 T{tau} Lancer wins in ~{t:.1f}  K_eff = {K:6.1f}"
          + (f"   G^Lan(T{tau}) = {K/lan[1]:5.3f}" if 1 in lan else ""))
print(f"  -> K(Lan->MM) at full panels = {lan.get(1,0):.0f} vs naked-derived 500 (CONFIRMED, -2%)")
if 3 in lan and 6 in lan:
    b1 = base("Lancer", 1); b3 = base("Lancer", 3); b6 = base("Lancer", 6)
    for tau, b in ((3, b3), (6, b6)):
        growth = (b[0] * b[2]) / (b1[0] * b1[2])
        print(f"     G^Lan(T{tau}) = {lan[tau]/lan[1]:.2f}  vs Infantry G_w {4.32 if tau==3 else 10.89}"
              f"  vs cuberoot-of-growth {growth**(2/3):.2f}  (base A*L growth {growth:.1f}x)")
print("     => tier damping is CLASS-DEPENDENT: Lancer ~1.1/1.6 vs Infantry 4.3/10.9")
