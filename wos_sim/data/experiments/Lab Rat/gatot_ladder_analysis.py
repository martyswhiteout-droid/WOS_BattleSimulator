"""Gatot beast-hunt stat-isolation analysis (re-runnable; reads the JSON reports).

Design (all from the reports, nothing hand-entered except the exponent grid):
  - Attacker = 1 troop, Far Seer, Infantry Attack panel FIXED at +188.6% across
    the whole Lethality ladder; only the displayed Lethality panel changes
    (0 -> 10 -> 21.6 -> 32.7 %).  Target = 18 identical Lv1 Cave Hyenas (fixed).
  - Gatot's skills are OWN-side defensive (S1 +6% own Inf Defense; S2 King's
    Bestowal = self-shield each attack) and never touch OUTGOING damage, so they
    cancel in every ratio.  King's Bestowal trigger count == attacks == rounds.
  - Global turn cap = 1500 (attacker survives -> a "defeat" simply means beasts
    remained at the cap).  Kills = a direct readout of cumulative damage in units
    of one beast's hidden HP.

Model on the Lethality ladder (A, D, target fixed):  per-round damage
    D(panel) = D0 * (1 + panel)^p          (p = Lethality exponent)
Let r = 1500 * D0 / beastHP  (exact beast-HP the BASE config delivers over 1500
rounds).  A defeat with k kills means cumulative in [k, k+1) beastHP; a victory
at turn T means cumulative reaches 18 by T (and not by T-1).  We scan p and keep
only the values for which a single r satisfies every row -> the feasible p-band.
"""
import glob, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(pat):
    f = glob.glob(os.path.join(HERE, pat))[0]
    d = json.load(open(f, encoding="utf-8"))
    return d["attacker"]["kills"], d["turn_inference"]["turns"], d["outcome"]["winner"]


# Lethality ladder: (panel_L, kills, turns, winner) pulled from the reports
ladder = []
for pat, panel in [("*T1InfvT1Inf_Gatotlvl1*020035.json", 0.0),
                   ("*Att+10L_Gatotlvl1*.json", 0.10),
                   ("*Att+21.6L_Gatotlvl1*021112.json", 0.216),
                   ("*Att+32.7L+53.2H_Gatotlvl1*.json", 0.327)]:
    k, t, w = load(pat)
    ladder.append((panel, k, t, w))
print("Lethality ladder (from reports):")
for panel, k, t, w in ladder:
    print(f"  +{panel*100:4.1f}% L  kills={k:2}  turns={t}  {w}")


def feasible(p):
    lo_r, hi_r = -math.inf, math.inf
    for panel, k, t, w in ladder:
        f = (1.0 + panel) ** p
        if w == "defender":       # attacker DEFEAT at the 1500 cap: cumulative in [k,k+1)
            lo_r = max(lo_r, k / f); hi_r = min(hi_r, (k + 1) / f)
        else:                     # attacker VICTORY at turn t: reaches 18 by t, not by t-1
            lo_r = max(lo_r, 18.0 * 1500 / (t * f))
            hi_r = min(hi_r, 18.0 * 1500 / ((t - 1) * f))
    return lo_r, hi_r, lo_r < hi_r


print("\nLethality-exponent feasibility (empty r-window => p EXCLUDED):")
for p in (0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0):
    lo, hi, ok = feasible(p)
    print(f"  p={p:4.2f}: r in [{lo:.3f},{hi:.3f}]  {'YES' if ok else 'no'}")
band = [p / 1000 for p in range(1, 3000) if feasible(p / 1000)[2]]
print(f"  => feasible ONLY for p in [{min(band):.3f}, {max(band):.3f}]  (L is LINEAR)")

# self-consistent prediction at p=1
lo, hi, _ = feasible(1.0)
r = (lo + hi) / 2
print(f"\n  at p=1, r={r:.3f} beastHP/1500rounds predicts:")
for panel, k, t, w in ladder:
    cum = r * (1 + panel)
    pt = 18 / (cum / 1500)
    print(f"    +{panel*100:4.1f}%L: cumulative={cum:.2f} beastHP -> "
          f"{'kills '+str(min(18,int(cum))) if cum < 18 else 'victory @%.0f rounds' % pt}")

# Tier ladder (panel L=0; target fixed)
print("\nTier ladder (panel L=0; base A & L both scale with tier; target fixed):")
tier = []
for pat, n in [("*T1InfvT1Inf_Gatotlvl1*020035.json", 1),
               ("*T2InfvT1Inf_Gatotlvl1*.json", 2),
               ("*T6InfvT1Inf_Gatotlvl1*.json", 6)]:
    k, t, w = load(pat); tier.append((n, k, t, w))
b_lo, b_hi = tier[0][1] / 1500, (tier[0][1] + 1) / 1500
for n, k, t, w in tier:
    if w == "defender":      # attacker defeat at cap
        lo, hi = k / 1500, (k + 1) / 1500
    else:                    # attacker victory at turn t
        lo, hi = 18 / t, 18 / (t - 1)
    if n == 1:
        print(f"  T{n}: dmg/round [{lo:.5f},{hi:.5f}] (base)")
    else:
        rlo, rhi = lo / b_hi, hi / b_lo
        s = f"n^[{math.log(rlo)/math.log(n):.2f},{math.log(rhi)/math.log(n):.2f}]"
        print(f"  T{n}: dmg/round [{lo:.5f},{hi:.5f}]  x T1 [{rlo:.2f},{rhi:.2f}]  combined(A*L)-exp {s}")
print("  If L-exp=1 (above), additive tier model forces A-exp<0 (unphysical)")
print("  => base A and/or L do NOT scale linearly with tier; needs an ATTACK-only ladder.")
