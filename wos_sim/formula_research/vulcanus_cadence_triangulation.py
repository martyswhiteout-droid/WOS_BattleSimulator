"""Triangulate Vulcanus S2/S3 proc cadence from every battle that has BOTH an
exact Gatot turn clock AND Vulcanus counters (Martin's request, 2026-07-18).

Models under test (S1 = once at start, uncontested):
  S2: (a) every 6th ATTACK EVENT of the Vulcanus side  -> count = floor(units*T/6)
      (b) every 6th TURN                               -> count = floor(T/6)
  S3: (p1) turn cadence phase-1 (turns 1,4,7,...)      -> count = ceil(T/3)
      (p3) turn cadence phase-3 (turns 3,6,9,...)      -> count = floor(T/3)
      (ev) every 3rd attack event                      -> count = floor(units*T/3)

`units` = live unit count on the Vulcanus side (constant in these battles: the
Vulcanus side wins with no losses everywhere it appears). T = battle length from
the Gatot S2 clock of whichever side survives to the end (defender in the
composition set; the dying Gatot-Inf's own clock in the 1v1s = its death turn =
battle end). Verdict per battle: which models hit the observed counts exactly.
"""
import glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
FOLDERS = ["data/experiments/MuellerAlpaca_Gatot_2v2", "data/experiments/Meuller_Alpaca_v5_8_Battle",
           "data/experiments/MuellerAlpaca", "data/ENIF"]

def sk(side, hero):
    out = {}
    for h in (side.get("hero_skills") or []):
        if h.get("hero") == hero:
            out[h.get("slot", "?")[-1:]] = h.get("triggers")
    return out

rows = []
for fol in FOLDERS:
    for f in sorted(glob.glob(os.path.join(ROOT, fol, "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        if "attacker" not in d:
            continue
        a, de = d["attacker"], d["defender"]
        va, vd = sk(a, "Vulcanus"), sk(de, "Vulcanus")
        if not va and not vd:
            continue
        vs_side = a if va else de
        v = va or vd
        ga, gd = sk(a, "Gatot"), sk(de, "Gatot")
        # battle length: Gatot S2 of the side that survives to the end; in 1v1s
        # the dying Gatot-Inf's clock also equals battle end. Prefer the WINNER's.
        win = d["outcome"]["winner"]
        g_win = ga if win == "attacker" else gd
        g_lose = gd if win == "attacker" else ga
        T = g_win.get("2") or g_lose.get("2")
        if not T:
            continue
        units = vs_side.get("troops") or 1
        # unit count integrity: Vulcanus side must not lose units for the clean
        # event count (true everywhere here; flag if not)
        lost = (vs_side.get("losses") or 0) + (vs_side.get("injured") or 0) + (vs_side.get("lightly_injured") or 0)
        clean = (lost == 0)
        rows.append(dict(f=os.path.basename(f)[:52], T=T, units=units, clean=clean,
                         s2=v.get("2"), s3=v.get("3")))

print(f"{'battle':52} {'T':>4} {'u':>2} {'S2obs':>5} | {'ev6':>4} {'tn6':>4} || {'S3obs':>5} | {'p1':>3} {'p3':>3} {'ev3':>4}  verdicts")
tally = {"s2_ev": 0, "s2_tn": 0, "s2_n": 0, "s3_p1": 0, "s3_p3": 0, "s3_ev": 0, "s3_n": 0, "s3_disc": []}
for r in rows:
    T, u = r["T"], r["units"]
    ev6, tn6 = (u * T) // 6, T // 6
    p1, p3, ev3 = -(-T // 3), T // 3, (u * T) // 3
    s2v = []
    if r["s2"] is not None:
        tally["s2_n"] += 1
        if r["s2"] == ev6: tally["s2_ev"] += 1; s2v.append("EV6")
        if r["s2"] == tn6: tally["s2_tn"] += 1; s2v.append("TN6")
    s3v = []
    if r["s3"] is not None:
        tally["s3_n"] += 1
        if r["s3"] == p1: tally["s3_p1"] += 1; s3v.append("P1")
        if r["s3"] == p3: tally["s3_p3"] += 1; s3v.append("P3")
        if r["s3"] == ev3: tally["s3_ev"] += 1; s3v.append("EV3")
        if p1 != p3 and (r["s3"] in (p1, p3)):
            tally["s3_disc"].append((r["f"], T, r["s3"], p1, p3))
    print(f"{r['f']:52} {T:>4} {u:>2} {str(r['s2']):>5} | {ev6:>4} {tn6:>4} || {str(r['s3']):>5} | {p1:>3} {p3:>3} {ev3:>4}  "
          f"S2:{'/'.join(s2v) or 'NONE'} S3:{'/'.join(s3v) or 'NONE'}{'' if r['clean'] else '  [side took damage]'}")

print(f"\nS2 verdict: every-6th-EVENT {tally['s2_ev']}/{tally['s2_n']}  vs every-6th-turn {tally['s2_tn']}/{tally['s2_n']}")
print(f"S3 verdict: phase-1 {tally['s3_p1']}/{tally['s3_n']}  phase-3 {tally['s3_p3']}/{tally['s3_n']}  event-based {tally['s3_ev']}/{tally['s3_n']}")
print("\nPHASE-DISCRIMINATING battles (T not divisible by 3, S3 matches exactly one phase):")
for f, T, obs, p1, p3 in tally["s3_disc"]:
    which = "PHASE-1" if obs == p1 else "PHASE-3"
    print(f"  {f:52} T={T:>3}  obs={obs}  (p1={p1}, p3={p3})  -> {which}")
