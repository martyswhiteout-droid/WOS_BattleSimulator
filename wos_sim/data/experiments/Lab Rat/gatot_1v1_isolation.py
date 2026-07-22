"""Gatot 1v1 single-target isolation analysis (re-runnable; reads the JSON reports).

The Gatot 1v1 battles are the cleanest instrument we have:
  - 1 troop vs 1 troop, exact turn count (King's Bestowal triggers == rounds).
  - Attacker (Far Seer + Gatot) is strong and never dies -> the ONLY event is the
    defender's death, so turns = defender_HP / attacker_damage_per_turn exactly.
  - Gatot's skills are own-side defensive (never touch outgoing damage).
  - Each ladder varies ONE stat with a KNOWN panel delta at fixed T1
    (T1 = base reference, so effective = base * (1+panel) is model-independent:
    base Inf T1 = A1 D4 L1 H6).

Result: turns = C * D_def * H_def / (A_att * L_att),  C ~ 12.54  (exponents
(A,L,D,H) = (+1,+1,-1,-1)) — i.e. damage/turn ~ A*L/D and HP ~ H.
"""
import glob, json, os, re, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = {"Infantry": (1, 4, 1, 6)}   # T1 reference (model-independent)


def rec(f):
    d = json.load(open(f, encoding="utf-8"))
    a, de = d["attacker"], d["defender"]
    pa = (a.get("stats_pct") or {}).get("Infantry", {})
    pd = (de.get("stats_pct") or {}).get("Infantry", {})
    A = 1 * (1 + pa.get("Attack", 0) / 100)
    L = 1 * (1 + pa.get("Lethality", 0) / 100)
    D = 4 * (1 + pd.get("Defense", 0) / 100)
    H = 6 * (1 + pd.get("Health", 0) / 100)
    t = (d.get("turn_inference") or {}).get("turns")
    tier = int(round(float(re.search(r"([\d.]+)", a.get("tier_display", "Lv 1")).group(1))))
    return dict(A=A, L=L, D=D, H=H, t=t, hcap=("Health" in pd), lcap=("Lethality" in pd),
                tier=tier, f=os.path.basename(f))


rows = [rec(f) for f in sorted(glob.glob(os.path.join(HERE, "FarSeer_1v1_T1InfvT1Inf_*.json")))]
rows = [r for r in rows if r["t"]]

# --- independent exponents -------------------------------------------------
print("Attack ladder (def naked D4 H6, L1): turns*A const => A-exp +1")
for r in sorted({(r["A"], r["t"]) for r in rows
                 if abs(r["D"] - 4) < 1e-6 and abs(r["H"] - 6) < 1e-6 and abs(r["L"] - 1) < 1e-6}):
    print(f"   A={r[0]:.3f} turns={r[1]}  turns*A={r[1]*r[0]:.1f}")

print("\nDefense ladder (att A3.577, H6, L1): turns/D const => D-exp -1")
for D, t in sorted({(r["D"], r["t"]) for r in rows
                    if abs(r["A"] - 3.577) < 1e-3 and abs(r["H"] - 6) < 1e-6 and abs(r["L"] - 1) < 1e-6}):
    print(f"   D={D:.3f} turns={t}  turns/D={t/D:.2f}")

# --- combined single-constant exact test -----------------------------------
full = [r for r in rows if r["hcap"]]
C = statistics.median([r["t"] * r["A"] * r["L"] / (r["D"] * r["H"]) for r in full])
worst = max(abs(C * r["D"] * r["H"] / (r["A"] * r["L"]) - r["t"]) for r in full)
print(f"\nCOMBINED turns = C*D*H/(A*L),  C={C:.3f}  =>  max|err| = {worst:.2f} turns "
      f"over {len(full)} T1 rows (captured H)")

# --- T3 internal consistency + tier factor ---------------------------------
print("\nT3 rows: implied (A*L)_eff = C*D*H/turns (same panel should agree)")
t3 = []
for f in sorted(glob.glob(os.path.join(HERE, "FarSeer_1v1_T3InfvT1Inf_*.json"))):
    r = rec(f)
    if not r["t"] or not r["hcap"]:
        continue
    AL = C * r["D"] * r["H"] / r["t"]
    t3.append(AL)
    print(f"   turns={r['t']} D={r['D']:.3f} H={r['H']:.3f} => (A*L)_eff={AL:.3f}")
if t3:
    at0 = [x for x in t3 if x < 8]   # the +0L panel cluster
    if at0:
        ratio = statistics.median(at0) / 3.577    # T1 (A*L) at same +257.7A panel = 3.577
        print(f"   base_T3(A*L)/base_T1(A*L) ~ {ratio:.2f}  => per-tier factor ~{ratio**0.25:.3f}/tier/stat")
        print("   (multiplicative, NOT additive n,n+3,..) -> A*L/(D*H) tier-invariant in mirrors")
