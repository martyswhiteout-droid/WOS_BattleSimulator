"""Gatot S2 "King's Bestowal" shield test (2026-07-18, Martin-approved).

Hypothesis under test: the measured hero-less budget-absorb B is Gatot's S2
shield -- a recharging per-turn absorption with protection = s2% x Attack
(tooltip: "shield with protection equal to Attack x 12% each time they attack
for 1 turn", Alpaca L2). If true, B should be PREDICTABLE from the Gatot
unit's stats, and the v5 "M >= 2.58" cluster + the naked-mirror cluster should
dissolve into the already-measured budget gate (hero-less dealers fully
absorbed -> defender wins; no separate M constant needed).

Tests (all against corpus rows + frozen stage6_tables constants; no fitting):
  T1  B-scaling: which stat combination of the two measured Gatot units
      (Mueller threshold, FarSeer threshold) matches B_M/B_F = 6.698?
      The tooltip's literal reading (troop Attack) is checked first.
  T2  v5 dissolution: hero-less dealer rates d_raw(tau) for every v5 rung --
      if max(d_raw) is small (<< any plausible B_Alpaca), every v5 outcome is
      budget-capped -> defender wins, matching observation with NO M.
  T3  Naked-mirror dissolution: same check for the 12 T1 no-hero mirror rows.
  T4  Fresh-battle consistency: today's naked-T6-MM battle (capped, exact 150)
      and the Vulcanus-led 6-turn battle (hero-led regime bypasses the budget).
  T5  What the shield does NOT explain: the 151127 reverse-race battle
      (Gatot DEALER slow vs a naked target -- a shield protects, it cannot
      slow its holder's own offense).

Output: printout only (this file IS the record; numbers re-derive on run).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "..", "data", "experiments", "_corpus", "TYPE1_CORPUS.json")
TABLES = os.path.join(HERE, "stage6_tables.json")

K_INF_INF = 12.524
GW_INF = {1: 1.0, 2: 2.68, 3: 4.32, 4: 5.88, 5: 9.79, 6: 10.89}   # measured rungs
GW_INF_EXTRAP = {7: 13.2, 8: 15.6, 9: 18.0, 10: 20.5}             # cube-root interpolant (flagged)

rows = {r["id"]: r for r in json.load(open(CORPUS, encoding="utf-8"))["rows"]}
kit = json.load(open(TABLES, encoding="utf-8"))["gatot_kit"]
budgets = kit["no_hero_budget_gate"]["B_hp_units_per_turn"]
B_M = budgets["Mueller_Gatot_S123_L1"]
B_F = budgets["FarSeer_Gatot_S12_L1"]


def unit(row_id, side):
    return rows[row_id][side]["classes"][0]["eff"]


mueller_g = unit("AlpacaMueller_22v1_FC1T6MMvT1Inf_NoAttackerHero_Gatotlvl1_20260712_194558", "defender")
farseer_g = unit("LabRat_67v1_T3LanvT1Inf_NoAttackerHero_Gatotlvl1_20260712_214455", "defender")

print("=" * 78)
print("T1  B-SCALING: B_M/B_F vs stat-combination ratios of the two Gatot units")
print("=" * 78)
ratio_B = B_M / B_F
print(f"  B(Mueller) = {B_M}   B(FarSeer) = {B_F}   ratio = {ratio_B:.3f}")
print(f"  Mueller Gatot unit eff: {mueller_g}")
print(f"  FarSeer Gatot unit eff: {farseer_g}")
combos = {
    "A (tooltip literal)": lambda u: u["A"],
    "L": lambda u: u["L"],
    "D": lambda u: u["D"],
    "H": lambda u: u["H"],
    "A*L": lambda u: u["A"] * u["L"],
    "D*H (pool)": lambda u: u["D"] * u["H"],
    "A*D": lambda u: u["A"] * u["D"],
    "A*L*H": lambda u: u["A"] * u["L"] * u["H"],
    "A^2": lambda u: u["A"] ** 2,
    "(A*L)*(D*H)": lambda u: u["A"] * u["L"] * u["D"] * u["H"],
}
for name, f in combos.items():
    r = f(mueller_g) / f(farseer_g)
    verdict = "MATCH" if abs(r / ratio_B - 1) <= 0.10 else f"off x{max(ratio_B/r, r/ratio_B):.2f}"
    print(f"    {name:18} ratio {r:7.3f}   vs 6.698 -> {verdict}")
print("  (equal S2 levels assumed; a one-level s2 difference shifts these ~x1.2,")
print("   nowhere near the x3.46 gap on the tooltip-literal Attack reading)")
print("  => NOT explained by any captured troop stat alone.")

print()
print("-" * 78)
print("T1b HERO-SHEET TEST (Martin's hero-screen screenshots, 2026-07-18/19)")
print("-" * 78)
# Hero Overall Stats as photographed (provenance: Martin, 4th message 07-18/19):
#   copy:      HeroAtk HeroDef HeroHP  EscAtk EscDef EscHP  Escorts Expedition%
SHEETS = {
    "Mueller": (2608, 3403, 51067, 868, 1134, 17022, 8, 301.93),
    "Alpaca":  (3091, 4028, 60447, 1026, 1343, 20149, 9, 337.85),
    "FarSeer": (1686, 2200, 33003, 559, 733, 11001, 7, 186.45),
}
m, f = SHEETS["Mueller"], SHEETS["FarSeer"]
print("  AURA IDENTIFIED AT SOURCE: the Expedition block IS the aura --")
print(f"    Mueller Expedition +{m[7]}% vs measured aura +301.9/+302.0  (EXACT)")
print(f"    Alpaca  Expedition +{SHEETS['Alpaca'][7]}% vs measured cross-date aura +360.9")
print("      -> difference 23.05pp = the alliance A/D buff delta between the two")
print("         capture dates; the +10 L/H likewise (aura itself has NO L/H,")
print("         matching Mueller's same-day 0/0). Aura reconciled.")
labels = ["HeroAtk", "HeroDef", "HeroHP", "EscortAtk", "EscortDef", "EscortHP", "Escorts", "Expedition%"]
print("  sheet ratios Mueller/FarSeer (B ratio to explain: 6.698):")
for i, lab in enumerate(labels):
    print(f"    {lab:12} {m[i]/f[i]:6.3f}")
print("  => every sheet stat scales ~x1.55 while B scales x6.70 -- B is NOT")
print("     proportional to any single hero-sheet stat either.")
comp = {
    "troop A*L x HeroAtk": (combos["A*L"](mueller_g) * m[0]) / (combos["A*L"](farseer_g) * f[0]),
    "troop D*H x HeroAtk": (combos["D*H (pool)"](mueller_g) * m[0]) / (combos["D*H (pool)"](farseer_g) * f[0]),
    "troop A*L x Expedition": (combos["A*L"](mueller_g) * m[7]) / (combos["A*L"](farseer_g) * f[7]),
}
for name, r in comp.items():
    print(f"    composite {name:24} ratio {r:6.3f}  ({r/ratio_B-1:+.1%} vs 6.698)")
print("  STANDOUT: troop A*L x Expedition% at -0.8% -- a shared constant")
c_m = B_M / (combos["A*L"](mueller_g) * m[7])
c_f = B_F / (combos["A*L"](farseer_g) * f[7])
print(f"    c = B/(A_eff*L_eff*Exp%):  Mueller {c_m:.5f}   FarSeer {c_f:.5f}   "
      f"(spread {abs(c_m/c_f-1):.1%})")
print("  Caveat: 2 points, ~13 candidate composites -- selection risk is real.")
print("  FALSIFIABLE PREDICTION for the third aura'd instrument (Alpaca's Gatot")
print("  FC1T1, v5 loadout A_eff*L_eff = 6.371*2.197, Expedition 337.85):")
alp_al = 6.371 * 2.197
b_alp_exp = c_m * alp_al * SHEETS["Alpaca"][7]
b_alp_atk = (B_M / (combos["A*L"](mueller_g) * m[0])) * alp_al * SHEETS["Alpaca"][0]
print(f"    B_Alpaca = {b_alp_exp:.0f} (Expedition composite) / {b_alp_atk:.0f} (HeroAtk composite)")
print("  MEASUREMENT DESIGN (no big account needed): Mueller's HERO-LESS FC1 T6")
print("  Lancer stack (the 40v1 instrument, ~8.1 pool-units/turn each, FC1 -> no")
print("  procs, Type-1) vs Alpaca's aura'd Gatot-Inf; linear pooling -> kill/no-")
print(f"  kill threshold N* = B_Alpaca / 8.1 ~ {b_alp_exp/8.1:.0f}-{b_alp_atk/8.1:.0f} Lancers;")
print("  bracket N in {20, 30, 40, 50} then binary-search the knife edge. This")
print("  simultaneously stress-tests the factorized K(Lan->Inf) cell.")

print()
print("=" * 78)
print("T2  v5 DISSOLUTION: hero-less dealer rates vs a budget on Alpaca's Gatot")
print("=" * 78)
# v5 attacker loadout is constant; Alpaca S3 (Royal Legion L3) folds -15% on it
v5 = unit("MuellerAlpaca_v5_R04_1v1_T6InfvFC1T1Inf_AttInfA+179.1D+179.7L+112.0H+108.7"
          "_DefInfA+537.1D+529.9L+119.7H+119.3_NoAttackerHero_AlpacaGatotS8lvl64_20260712_205212"
          if False else next(i for i in rows if "_v5_R04" in i), "attacker")
AL = v5["A"] * v5["L"] * 0.85            # Royal Legion L3: -15% enemy Attack
print(f"  v5 dealer A*L (S3-folded) = {AL:.1f}")
dmax = 0.0
for tau in range(2, 11):
    gw = GW_INF.get(tau) or GW_INF_EXTRAP[tau]
    tag = "measured" if tau in GW_INF else "extrapolated"
    d = AL / (K_INF_INF * gw)
    dmax = max(dmax, d)
    print(f"    T{tau:>2}: d_raw = {d:6.3f} pool-units/turn   [G_w {tag}]")
print(f"  max over rungs = {dmax:.2f}  ->  ANY B_Alpaca >= {dmax:.2f} caps EVERY rung")
print(f"  (B_Mueller = {B_M}, B_FarSeer = {B_F}; a third copy at >= {dmax:.1f} is trivially plausible)")
print("  => every v5 battle predicts BUDGET-CAPPED attacker -> defender wins = OBSERVED 9/9.")
print("     The 'M >= 1.29..6.89' bounds were the naive-law shadow of full absorption;")
print("     no M constant is needed. (One-sided: the v5 rows BOUND B_Alpaca >= "
      f"{dmax:.2f}, they cannot pin it; the crossover battle that first beats")
print("     Alpaca's Gatot-Inf measures B_Alpaca exactly.)")

print()
print("=" * 78)
print("T3  NAKED-MIRROR DISSOLUTION: T1 no-hero dealers vs the same budget")
print("=" * 78)
# CORRECTED polarity (found during this test): in these 12 rows the ATTACKER
# is Mueller's GATOT-LED T1 Inf at UN-AURA'D panels (+194.1/+172.2 -- no +301.9
# aura, same 07-12 day as the aura'd +481 threshold battles), and the DEFENDER
# is Alpaca's hero-less FC1 T1 (+514 panels). The defender KILLED the Gatot
# unit slowly => PARTIAL absorption. If the budget mechanism is right, each row
# solves B_row = d_dealer - pool_att/t_obs and all 12 must agree on ONE value.
mirrors = [i for i in rows if i.startswith("MuellerAlpaca_1v1_T1InfvFC1T1Inf")]
print(f"  {len(mirrors)} Gatot-led-attacker (+194 un-aura'd) vs hero-less-Alpaca rows:")
bs = []
for i in sorted(mirrors):
    r = rows[i]
    mu, al = unit(i, "attacker"), unit(i, "defender")
    t = r["outcome"]["turns"] or (r["outcome"].get("turns_range") or [None])[0]
    if not t:
        continue
    d_folded = al["A"] * al["L"] * 0.90 / K_INF_INF      # IF Royal Legion -10% applied
    d_plain = al["A"] * al["L"] / K_INF_INF              # no Gatot effects at all
    pool_att = mu["D"] * mu["H"]                          # G_l(Inf,1)=1, no S1 branch
    b_folded = d_folded - pool_att / t
    b_plain = d_plain - pool_att / t
    extra = {h["hero"] for h in r["attacker"]["heroes"]} - {"Gatot"}
    bs.append((b_folded, b_plain, d_plain))
    print(f"    t_obs={t:>4}  pool={pool_att:6.1f}  B(S3 folded)={b_folded:6.3f}  "
          f"B(no folds)={b_plain:6.3f}  t_plain_err={(pool_att/d_plain)/t-1:+.1%}"
          f"{'  [+' + ','.join(extra) + ']' if extra else ''}")
if bs:
    import statistics as st
    plain = [b for _, b, _ in bs]
    rel = [abs(b) / d for _, b, d in bs]
    print(f"  B(no-folds) spread: mean {st.mean(plain):+.3f}, |B|/d <= {max(rel):.1%} on every row")
    print("  => the un-aura'd Gatot contributes NOTHING measurable: no absorption AND")
    print("     no Royal-Legion debuff -- all 12 rows fit the PLAIN LAW within ~3%.")
    print("  UNIFIED READING: aura, S2 shield capacity, and S3 debuff magnitude all")
    print("  scale with the HERO's own sheet (level/stars/gear) -- the same hidden")
    print("  variable. Aura'd states: B = 201.95 (Mueller) / 30.15 (FarSeer) /")
    print("  >= 6.3 (Alpaca, v5). Un-aura'd state: B ~ 0 and folds ~ 0.")
    print("  Seam implication: Gatot-present-but-panels-at-baseline => kit INERT;")
    print("  the 12 W6 abstains on these rows are upgradeable to plain-race calls.")

print()
print("=" * 78)
print("T4  FRESH-BATTLE CONSISTENCY (2026-07-18 pair)")
print("=" * 78)
b1 = next(i for i in rows if "162413" in i)
mm = unit(b1, "defender")
K_MM_INF = 90.11
d_naked_mm = mm["A"] * mm["L"] * 0.90 / K_MM_INF   # Mueller Royal Legion L2: -10%
print(f"  naked T6 MM dealer rate = {d_naked_mm:.3f} pool-units/turn  vs B_M = {B_M}")
print(f"  => fully absorbed, capped: observed = zero damage in 150 turns, Inf wins EXACT.")
print(f"  Vulcanus-led twin battle (164811): kill in 6 turns despite rate << B")
print(f"  => hero-led dealers BYPASS the budget (the frozen two-regime split), confirmed.")

print()
print("=" * 78)
print("T5  WHAT THE SHIELD DOES NOT EXPLAIN")
print("=" * 78)
print("  MuellerAlpaca_..._T7InfvFC1T1Inf_151127: the GATOT-LED DEALER runs slow vs")
print("  a NAKED target. A shield protects its holder; it cannot slow the holder's")
print("  own offense. THE T7 DISCRIMINATOR RAN (2026-07-18 23:53, ingested")
print("  ..._AlpacaFC1T1Vulcanus_20260718_235302): no-hero T7 vs the same naked-ish")
print("  FC1T1 killed in [75,77] => G_w(Inf,7) MEASURED = 14.1-14.5 (cube-root")
print("  extrapolant 13.2 was only -8% low). With G_w(7)~14.2 the 151127 dealer")
print("  predicts ~152 turns vs observed >599: >=3.9x slow WITH tier, base, panels")
print("  and target all controlled => the GATOT-DEALER SLOWDOWN IS REAL PHYSICS --")
print("  present even in the un-aura'd state that is INERT as a target kit.")
print("  Now the sharpest open question. CAUTION: every instrument cell measured")
print("  with a Gatot-led DEALER (G_l^MM via ENIF2, G_l^Inf via v5's Alpaca-Gatot")
print("  dealer, K(Inf->Inf) via Lab-Rat) may FOLD this dealer-side effect --")
print("  self-consistent within those instrument families, but a Stage-6.6 audit")
print("  must map which cells carry it before mixing instruments.")

print()
print("-" * 78)
print("T2b B_ALPACA MEASURED (2026-07-19 knife-edge, rows 204v1/205v1) -- the")
print("    composite-law prediction of ~257 is REFUTED")
print("-" * 78)
# 204x T6 Lancers capped at 1500 (defender untouched); 205x kill at turn 575.
# Lancer (FC1-base convention) A=10 L=11; panels +179.1 A / +105.3 L.
# CORRECTED 2026-07-19: the dealer rate must include G_w^Lan(6) = 1.625 --
# sanity anchor: the OLD 40/41 edge (Alpaca's Lancers A*L=732.3 vs B_Mueller
# =201.95, itself pinned independently by the 21/22 MM edge) gives
# K*G_w = 732.3/(201.95/40.5) = 146.9 => K(Lan->Inf) = 146.9/1.625 = 90.4,
# reproducing stage6's threshold-implied ~91. The first emit of this section
# omitted G_w^Lan and printed B_Alpaca ~ 1419-1543 -- superseded below.
GW_LAN6 = 1.625
lan_al = (10 * 2.791) * (11 * 2.053)
alp = None
for i, r in rows.items():
    if "205v1" in i:
        alp = r["defender"]["classes"][0]["eff"]
pool_alp = alp["D"] * alp["H"]
for k_lan, tag in ((90.4, "K(Lan->Inf)=90.4 (40/41-edge-implied)"), (83.7, "K=83.7 (factorized)")):
    r1 = lan_al / (k_lan * GW_LAN6)
    b = 205 * r1 - pool_alp / 575
    print(f"  {tag}: r/Lancer = {r1:.3f}  =>  B_Alpaca = 205r - pool/575 = {b:.0f}")
    print(f"     cap check 204: net = {204*r1 - b:+.2f} (must be <= {pool_alp/1500:.3f}) "
          f"{'OK' if 204*r1 - b <= pool_alp/1500 else 'VIOLATED'}")
print(f"  pool(Alpaca aura'd Gatot Inf) = {pool_alp:.1f}")
print("  VERDICTS: (1) B_Alpaca ~ 872-949 -- the (A*L x Expedition%) composite")
print("  predicted 257: REFUTED (x3.4-3.7 low). Cross-copy scaling stays OPEN --")
print("  sheets scale x1.12-1.19 Alpaca/Mueller while B scales ~x4.4; candidates:")
print("  skill level/stars (Alpaca S2 L2 + S8 stars vs Mueller unknown).")
print("  (2) The MECHANISM is confirmed harder than ever: the one-Lancer knife")
print("  edge at N=204/205 and the kill-time self-consistency (net(205) =")
print("  pool/575 lands exactly on the cap boundary at 204) are the LINEAR")
print("  subtractive-budget signature at N~200 -- 10x beyond the previous")
print("  largest pooled test.")
