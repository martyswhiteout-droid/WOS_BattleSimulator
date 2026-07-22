"""Stage 7 Phase A — Type-2 proc telemetry mining (ANALYSIS-ONLY, read-only).

Mines the only structured skill-trigger telemetry on file — the 8 RAW golden-anchor
source reports ``wos_sim/data/reports/report_001..008.json`` — and tests observed
trigger counts against the catalog probabilities the repo itself ships:

  * hero skills:   ``wos_sim.loader.load_skill_book()`` (the workbook "Hero Skills"
                    tab, post ``_normalize_skill_effect`` corrections) — the same
                    catalog the turn engine consumes;
  * troop skills:  ``wos_sim.troop_catalog.TROOP_SKILL_CATALOG``.

No probability, cadence, or effect number is hand-copied into this script: every
catalog constant is read from those two sources at runtime (no-fudge guardrail).
The ONLY hand-curated content is the string→identity mapping for troop-skill icon
rows (each with the evidence note from the report files themselves) and the
skill-pair list for T-free conditional ratio tests.

Method
------
1. CLOCKS. Deterministic-cadence hero skills ("every k turns", no probability)
   clock the battle: observed count n under the floor convention (fires at turns
   k, 2k, 3k, ...; Martin-confirmed in report_001 notes and triangulated for
   Vulcanus S3 2026-07-18) gives T in [k*n, k*n+k-1]; the offset convention
   (fires at 1, k+1, ...) gives T in [(n-1)*k+1, n*k]. Both sides share T, so
   bands intersect across the whole report. Strikes-cadence skills of classes
   that finished with survivors > 0 are secondary clocks under assumption A1
   (one attack event per class-stack per battle turn).
2. OPPORTUNITY STREAMS. For each chance proc we test every defensible stream:
   TURNS (1 roll/turn), OWN_ATTACK_EVENTS (one roll per own class-stack attack
   event; bounded by [max(T, n_alive_classes*T), n_deployed_classes*T]),
   ENEMY_ATTACK_EVENTS (same bounds from the enemy side; the "Received" stream),
   OWN_CLASS_STRIKES (the hero's own class only; = T if the class survived,
   else in [n, T_hi] because the class died at an unknown turn).
3. TESTS. Exact two-sided binomial p-value (minimum-likelihood method) scanned
   over every integer N in the stream interval (max over the scan = the most
   favourable defensible p-value); Clopper-Pearson 95% CI at the interval
   endpoints. Per-report and pooled per skill. Verdicts: consistent (max p >=
   0.05), rejected (max p < 0.01 over the whole interval), else marginal.
   A rejection under EVERY stream = catalog CONTRADICTED (a finding to flag —
   never a number to refit). Exactly one surviving stream = stream
   identification (which opportunity model the game actually rolls).
4. RATIO TESTS (T-free). For two chance skills of the same hero sharing a
   stream, X1 | X1+X2 ~ Binomial(X1+X2, p1/(p1+p2)) regardless of T.
5. Auxiliary emits: per-class death-turn estimates from strikes-cadence rows of
   wiped classes; kills-column table (Phase-B EV design input); unidentified
   icon-row rate analysis (hypothesis generation ONLY — never asserted);
   verbatim T12 prose-note dump (the T12 anchors carry trigger numbers only as
   free text); binomial power grid for the Stage-7 experiment menu.

Output: deterministic markdown-ish tables on stdout + ``stage7a_telemetry.json``
next to this file (sorted keys, no timestamps — byte-reproducible).

Run:  py -m wos_sim.formula_research.stage7a_telemetry
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

from wos_sim import loader
from wos_sim.models import SkillMechanic, SkillSource, TriggerUnit
from wos_sim.troop_catalog import TROOP_SKILL_CATALOG

REPO = Path(__file__).resolve().parent.parent.parent
RAW_DIR = REPO / "wos_sim" / "data" / "reports"
T12_GLOB = "pvp_t12_report_*.json"
T12_DIR = REPO / "wos_sim" / "data"
OUT_JSON = Path(__file__).resolve().parent / "stage7a_telemetry.json"

CLASSES = ("Infantry", "Lancer", "Marksman")

# ---------------------------------------------------------------------------
# Binomial machinery (stdlib floats via log-gamma; stable and fast; p-values at
# these magnitudes are unaffected by float precision — documented method)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8192)
def _pmf_vector(n: int, p: float) -> tuple[float, ...]:
    if n <= 0:
        return (1.0,)
    lp, lq = math.log(p), math.log(1.0 - p)
    lg = math.lgamma
    logs = [lg(n + 1) - lg(k + 1) - lg(n - k + 1) + k * lp + (n - k) * lq
            for k in range(n + 1)]
    m = max(logs)
    v = [math.exp(x - m) for x in logs]
    s = sum(v)
    return tuple(x / s for x in v)


def binom_two_sided_p(k: int, n: int, p: float) -> float:
    """Exact-test two-sided p-value, minimum-likelihood method (sum of all
    outcomes no more likely than the observed one)."""
    if n <= 0:
        return 1.0
    vec = _pmf_vector(n, p)
    thresh = vec[k] * (1 + 1e-9)
    return min(1.0, sum(x for x in vec if x <= thresh))


def binom_cdf(k: int, n: int, p: float) -> float:
    if k < 0:
        return 0.0
    vec = _pmf_vector(n, p)
    return min(1.0, sum(vec[: k + 1]))


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """95% CI for the rate, by bisection on the exact binomial CDF."""
    if n == 0:
        return (0.0, 1.0)

    def solve(target: float, tail_upper: bool) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            # tail_upper: P(X >= k | p) = target  -> lower bound
            # else:       P(X <= k | p) = target  -> upper bound
            if tail_upper:
                val = 1.0 - binom_cdf(k - 1, n, mid) if k > 0 else 1.0
                if val < target:
                    lo = mid
                else:
                    hi = mid
            else:
                val = binom_cdf(k, n, mid)
                if val > target:
                    lo = mid
                else:
                    hi = mid
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else solve(alpha / 2, tail_upper=True)
    upper = 1.0 if k == n else solve(alpha / 2, tail_upper=False)
    return (lower, upper)


def scan_max_p(k: int, n_lo: int, n_hi: int, p: float, max_points: int = 400) -> tuple[float, int]:
    """Max two-sided p-value over integer stream sizes N in [n_lo, n_hi]
    (the most favourable defensible opportunity count), and its argmax N."""
    n_lo = max(n_lo, k)  # cannot have fewer opportunities than triggers
    if n_hi < n_lo:
        return (0.0, n_lo)
    ns = list(range(n_lo, n_hi + 1))
    if len(ns) > max_points:  # guard; never hit with current data
        step = len(ns) // max_points + 1
        ns = ns[::step] + [n_hi]
    best_p, best_n = -1.0, n_lo
    for n in ns:
        pv = binom_two_sided_p(k, n, p)
        if pv > best_p:
            best_p, best_n = pv, n
    return (best_p, best_n)


def verdict_from_p(max_p: float) -> str:
    if max_p >= 0.05:
        return "consistent"
    if max_p < 0.01:
        return "rejected"
    return "marginal"


# ---------------------------------------------------------------------------
# Catalog-driven hero-slot classification (NO hand-copied probabilities)
# ---------------------------------------------------------------------------

class SlotInfo:
    def __init__(self, hero: str, slot: str, rows):
        self.hero, self.slot, self.rows = hero, slot, rows
        self.kind = "stats"
        self.p = None          # proc chance (from workbook col J; p=1.0 = certainty)
        self.k = None          # cadence "every N" (workbook col L)
        self.unit = None       # workbook trigger unit (col M)
        # probability == 1.0 on Turn-based rows means "fires deterministically",
        # NOT a chance gate — only p < 1 makes a skill chance-based.
        chance_probs = sorted({r.probability for r in rows
                               if r.probability is not None and r.probability < 1.0})
        freqs = sorted({(r.frequency, r.trigger_unit) for r in rows
                        if r.frequency is not None and r.frequency > 1})
        if hero == "Vulcanus" and slot == "Skill 2":
            # Workbook: every-5-Strikes; triangulated research (troop-passives.md,
            # 2026-07-19): every 6th attack of EACH Vulcanus-side unit, summed.
            # Disputed cadence -> never usable as a battle clock; report both.
            self.kind = "cadence_multi"
            self.k = [5, 6]
            self.unit = ["Strikes(workbook)", "per-unit-attacks(research)"]
        elif all(r.mechanic == SkillMechanic.STATS_BASED for r in rows):
            self.kind = "stats"
        elif chance_probs and not freqs:
            self.kind = "chance"
            self.p = chance_probs[0] if len(chance_probs) == 1 else chance_probs
            units = {r.trigger_unit for r in rows
                     if r.probability is not None and r.probability < 1.0}
            self.unit = sorted(u.value for u in units if u is not None)
        elif freqs and not chance_probs:
            if len(freqs) == 1:
                self.kind = "cadence"
                self.k = int(freqs[0][0])
                self.unit = freqs[0][1].value if freqs[0][1] else None
            else:
                self.kind = "cadence_multi"
                self.k = sorted(int(f) for f, _ in freqs)
                self.unit = sorted({(u.value if u else "?") for _, u in freqs})
        elif chance_probs and freqs:
            self.kind = "hybrid"
            self.p, self.k = chance_probs[0], int(freqs[0][0])
            self.unit = freqs[0][1].value if freqs[0][1] else None
        else:
            # per-attack continuous rows (frequency<=1, no chance gate):
            # the game displays Triggered=1 for these (report_001 note 9)
            self.kind = "per_attack_display1"


def build_hero_slots() -> dict[tuple[str, str], SlotInfo]:
    book = loader.load_skill_book()
    out: dict[tuple[str, str], SlotInfo] = {}
    for hero in book.heroes():
        for source, rows in book.skills_of(hero).items():
            if source == SkillSource.WIDGET if hasattr(SkillSource, "WIDGET") else source.value == "Widget":
                continue
            out[(hero, source.value)] = SlotInfo(hero, source.value, rows)
    return out


def build_hero_classes() -> dict[str, str]:
    """hero -> troop class, from the repo's own data (never guessed)."""
    classes: dict[str, str] = {}
    for fn in ("load_hero_profiles", "load_hero_roster"):
        f = getattr(loader, fn, None)
        if f is None:
            continue
        try:
            obj = f()
        except Exception:
            continue
        heroes = obj.heroes() if hasattr(obj, "heroes") else obj
        try:
            iterator = list(heroes.values()) if isinstance(heroes, dict) else list(heroes)
        except TypeError:
            continue
        for h in iterator:
            name = getattr(h, "name", None)
            troop = getattr(h, "troop_type", None)
            if name and troop is not None and name not in classes:
                classes[name] = str(getattr(troop, "value", troop))
    return classes


TROOP_BY_NAME = {s.name: s for s in TROOP_SKILL_CATALOG}

# ---------------------------------------------------------------------------
# Curated icon-row mapping (evidence: the strings in the report files)
# ---------------------------------------------------------------------------
# Each rule: substring -> (troop skill name in TROOP_SKILL_CATALOG or None,
#                          stream kind, confidence note)
ICON_RULES = [
    ("Volley (", "Volley", "own_class_strikes",
     "explicit label in report ('Volley (10% second strike..' / 'Volley (second "
     "strike..'); Martin note report_001: the 3-trigger row = Volley"),
    ("Ambusher (bypass", "Ambusher", "own_class_strikes",
     "explicit ingestion label 'Ambusher (bypass, direct kills)'"),
    ("likely Ambusher", "Ambusher", "own_class_strikes",
     "report string 'red arrows, likely Ambusher'; identified=false in file"),
    ("(Ambusher?", "Ambusher", "own_class_strikes",
     "report string '(Ambusher?)'; tentative ingestion identification"),
]


def classify_row(hero: str, skill_str: str, slots) -> dict:
    m = re.match(r"^([A-Za-z][A-Za-z ()'-]*?) Skill ([123])\b", skill_str)
    if m:
        slot = f"Skill {m.group(2)}"
        info = slots.get((hero, slot))
        if info is None:
            return {"kind": "unknown_hero_slot", "id": f"{hero} {slot}"}
        return {"kind": info.kind, "id": f"{hero} {slot}", "slot": info}
    for needle, troop_name, stream, note in ICON_RULES:
        if needle in skill_str:
            ts = TROOP_BY_NAME.get(troop_name)
            return {"kind": "troop_proc", "id": troop_name, "troop": ts,
                    "stream": stream, "note": note}
    return {"kind": "unidentified", "id": skill_str}


# ---------------------------------------------------------------------------
# Report loading / side aggregation
# ---------------------------------------------------------------------------

def load_reports() -> list[dict]:
    out = []
    for i in range(1, 9):
        path = RAW_DIR / f"report_{i:03d}.json"
        out.append((f"RAW_{i:02d}", json.loads(path.read_text(encoding="utf-8"))))
    return out


def side_summary(side: dict) -> dict:
    surv = {c: 0 for c in CLASSES}
    deployed = set()
    for c in CLASSES:
        comp = side.get("composition", {}).get(c, {})
        if comp.get("share", 0) > 0:
            deployed.add(c)
    for part in side.get("participants", []):
        for row in part.get("rows", []):
            c = row.get("troop_type")
            if c in surv:
                surv[c] += int(row.get("survivors", 0) or 0)
                deployed.add(c)
    return {"deployed": sorted(deployed), "survivors": surv,
            "alive_end": sorted(c for c in deployed if surv[c] > 0)}


# ---------------------------------------------------------------------------
# Clocks
# ---------------------------------------------------------------------------

def cadence_band(n: int, k: int, convention: str) -> tuple[int, int]:
    if convention == "floor":      # fires at k, 2k, ...  -> n = floor(T/k)
        return (k * n, k * n + k - 1)
    return ((n - 1) * k + 1, n * k)  # fires at 1, k+1, ... -> n = 1+floor((T-1)/k)


def intersect(bands: list[tuple[int, int]]) -> tuple[int, int] | None:
    lo = max(b[0] for b in bands)
    hi = min(b[1] for b in bands)
    return (lo, hi) if lo <= hi else None


def derive_clock(rid: str, rep: dict, slots, hero_cls) -> dict:
    primary, secondary, rows_used = [], [], []
    for side_key in ("friendly", "enemy"):
        side = rep[side_key]
        summ = side_summary(side)
        for lh in side.get("lead_heroes", []):
            hero = lh["name"]
            for row in lh.get("rows", []):
                n = int(row.get("triggered", 0) or 0)
                if n < 2:      # Triggered=1 rows are uninformative (display rule)
                    continue
                cls = classify_row(hero, row["skill"], slots)
                if cls["kind"] != "cadence":
                    continue
                info = cls["slot"]
                entry = {"side": side_key, "hero": hero, "skill": cls["id"],
                         "k": info.k, "unit": info.unit, "n": n}
                if info.unit == TriggerUnit.TURNS.value:
                    primary.append(entry)
                elif info.unit == TriggerUnit.STRIKES.value:
                    hcls = hero_cls.get(hero)
                    entry["hero_class"] = hcls
                    entry["class_alive_end"] = bool(hcls and summ["survivors"].get(hcls, 0) > 0)
                    secondary.append(entry)
                rows_used.append(entry)
    out = {"rid": rid, "primary_rows": primary, "secondary_rows": secondary}
    for conv in ("floor", "offset1"):
        bands = [cadence_band(e["n"], e["k"], conv) for e in primary]
        out[f"T_{conv}"] = intersect(bands) if bands else None
        # secondary strikes-clocks only where the class survived the whole battle (A1)
        sec = [cadence_band(e["n"], e["k"], conv) for e in secondary if e.get("class_alive_end")]
        out[f"T_{conv}_with_strikes"] = intersect(
            (bands or []) + sec) if (bands or sec) else None
    # the working band: primary if available, else strikes-secondary (A1 caveat)
    band = out["T_floor"] or out["T_floor_with_strikes"]
    out["T_band"] = band
    out["T_source"] = ("turns-cadence" if out["T_floor"] else
                       ("strikes-cadence(A1)" if band else "none"))
    out["T_band_offset1"] = out["T_offset1"] or out["T_offset1_with_strikes"]
    return out


# ---------------------------------------------------------------------------
# Streams
# ---------------------------------------------------------------------------

def stream_bounds(kind: str, band: tuple[int, int], own: dict, enemy: dict,
                  hero_class: str | None, n_obs: int) -> tuple[int, int, str] | None:
    t_lo, t_hi = band
    if kind == "turns":
        return (t_lo, t_hi, "1 roll per battle turn")
    if kind in ("own_attack_events", "enemy_attack_events"):
        s = own if kind == "own_attack_events" else enemy
        n_dep = len(s["deployed"])
        n_alive = len(s["alive_end"])
        lo = max(t_lo, n_alive * t_lo)
        hi = n_dep * t_hi
        return (lo, hi, f"{n_alive} class(es) alive at end, {n_dep} deployed")
    if kind == "own_class_strikes":
        if hero_class is None:
            return None
        if own["survivors"].get(hero_class, 0) > 0:
            return (t_lo, t_hi, f"{hero_class} survived -> strikes = T")
        return (n_obs, t_hi, f"{hero_class} WIPED at unknown turn -> N in [n, T_hi]")
    return None


STREAM_KINDS = ("turns", "own_attack_events", "enemy_attack_events", "own_class_strikes")


# ---------------------------------------------------------------------------
# Main mining pass
# ---------------------------------------------------------------------------

def mine(convention: str = "floor"):
    slots = build_hero_slots()
    hero_cls = build_hero_classes()
    reports = load_reports()

    clocks, tests, kills_rows, unidentified, death_turns = [], [], [], [], []
    cadence_checks, vulcanus_s2 = [], []
    inventory: dict[str, int] = {}

    for rid, rep in reports:
        clock = derive_clock(rid, rep, slots, hero_cls)
        clocks.append(clock)
        band = clock["T_band"] if convention == "floor" else clock["T_band_offset1"]
        own_sum = {k: side_summary(rep[k]) for k in ("friendly", "enemy")}

        for side_key in ("friendly", "enemy"):
            side = rep[side_key]
            mine_sum = own_sum[side_key]
            other_sum = own_sum["enemy" if side_key == "friendly" else "friendly"]
            for lh in side.get("lead_heroes", []):
                hero = lh["name"]
                for row in lh.get("rows", []):
                    sstr = row["skill"]
                    n = int(row.get("triggered", 0) or 0)
                    inventory[f"{hero} :: {sstr}"] = inventory.get(f"{hero} :: {sstr}", 0) + 1
                    if row.get("kills") is not None:
                        kills_rows.append({
                            "rid": rid, "side": side_key, "hero": hero,
                            "skill": sstr, "n": n, "kills": int(row["kills"]),
                            "kills_per_trigger": round(int(row["kills"]) / n, 1) if n else None})
                    cls = classify_row(hero, sstr, slots)

                    if cls["kind"] == "cadence" and n >= 2 and band:
                        info = cls["slot"]
                        if info.unit == TriggerUnit.STRIKES.value:
                            hcls = hero_cls.get(hero)
                            alive = bool(hcls and mine_sum["survivors"].get(hcls, 0) > 0)
                            pred_lo = band[0] // info.k
                            pred_hi = band[1] // info.k
                            cadence_checks.append({
                                "rid": rid, "side": side_key, "hero": hero,
                                "skill": cls["id"], "k": info.k, "unit": info.unit,
                                "n": n, "pred_if_alive_all_T": [pred_lo, pred_hi],
                                "class": hcls, "class_alive_end": alive})
                            if not alive and hcls:
                                dt = cadence_band(n, info.k, "floor")
                                clamped_hi = min(dt[1], band[1])
                                death_turns.append({
                                    "rid": rid, "side": side_key, "class": hcls,
                                    "from_skill": cls["id"], "n": n, "k": info.k,
                                    "death_turn_band_floor_conv": [dt[0], clamped_hi],
                                    "impossible_under_catalog_cadence": dt[0] > clamped_hi})
                        continue

                    if cls["kind"] == "cadence_multi" and n >= 2:
                        # Vulcanus S2 (workbook rows: every-5-Strikes + Received);
                        # research (troop-passives.md) says every 6th attack per unit.
                        info = cls["slot"]
                        pred = {}
                        if band:
                            for k in (5, 6):
                                pred[f"every{k}_of_stack"] = [band[0] // k, band[1] // k]
                        vulcanus_s2.append({
                            "rid": rid, "side": side_key, "hero": hero,
                            "skill": cls["id"], "n": n, "T_band": band,
                            "workbook_ks": info.k, "pred_single_stack": pred})
                        continue

                    if cls["kind"] == "chance" and n >= 2 and band:
                        p = cls["slot"].p
                        if not isinstance(p, float):
                            continue
                        hcls = hero_cls.get(hero)
                        entry = {"rid": rid, "side": side_key, "hero": hero,
                                 "skill": cls["id"], "n": n, "p_catalog": p,
                                 "workbook_unit": cls["slot"].unit,
                                 "hero_class": hcls, "T_band": list(band),
                                 "streams": {}}
                        for sk in STREAM_KINDS:
                            b = stream_bounds(sk, band, mine_sum, other_sum, hcls, n)
                            if b is None:
                                continue
                            lo, hi, note = b
                            max_p, argmax_n = scan_max_p(n, lo, hi, p)
                            ci_lo = clopper_pearson(n, hi)
                            ci_hi = clopper_pearson(n, max(lo, n))
                            entry["streams"][sk] = {
                                "N": [lo, hi], "note": note,
                                "rate": [round(n / hi, 4), round(n / max(lo, n), 4)],
                                "max_p": round(max_p, 6), "argmax_N": argmax_n,
                                "ci_at_Nhi": [round(ci_lo[0], 4), round(ci_lo[1], 4)],
                                "ci_at_Nlo": [round(ci_hi[0], 4), round(ci_hi[1], 4)],
                                "verdict": verdict_from_p(max_p)}
                        tests.append(entry)
                        continue

                    if cls["kind"] == "troop_proc" and n >= 2 and band:
                        ts = cls["troop"]
                        if ts is None or ts.proc_chance is None:
                            continue
                        hcls = hero_cls.get(hero)
                        entry = {"rid": rid, "side": side_key, "hero": hero,
                                 "skill": ts.name, "raw_string": sstr,
                                 "identified_in_file": bool(row.get("identified", True)),
                                 "n": n, "p_catalog": ts.proc_chance,
                                 "hero_class": hcls, "T_band": list(band),
                                 "mapping_note": cls["note"], "streams": {}}
                        b = stream_bounds("own_class_strikes", band, mine_sum,
                                          other_sum, hcls, n)
                        if b is not None:
                            lo, hi, note = b
                            max_p, argmax_n = scan_max_p(n, lo, hi, ts.proc_chance)
                            entry["streams"]["own_class_strikes"] = {
                                "N": [lo, hi], "note": note,
                                "rate": [round(n / hi, 4), round(n / max(lo, n), 4)],
                                "max_p": round(max_p, 6), "argmax_N": argmax_n,
                                "verdict": verdict_from_p(max_p)}
                        tests.append(entry)
                        continue

                    if cls["kind"] == "unidentified" and n >= 2 and band:
                        hcls = hero_cls.get(hero)
                        icon_cls = None
                        mm = re.search(r"icon:(infantry|lancer|marksman)-troop-skill", sstr)
                        if mm:
                            icon_cls = mm.group(1).capitalize()
                        rates = {}
                        t_lo, t_hi = band
                        rates["per_turn"] = [round(n / t_hi, 3), round(n / max(t_lo, 1), 3)]
                        for label, s in (("own_attacks", mine_sum), ("enemy_attacks", other_sum)):
                            hi = len(s["deployed"]) * t_hi
                            lo = max(t_lo, len(s["alive_end"]) * t_lo)
                            rates[label] = [round(n / hi, 3), round(n / max(lo, 1), 3)]
                        unidentified.append({
                            "rid": rid, "side": side_key, "hero": hero,
                            "hero_class": hcls, "icon_class": icon_cls,
                            "skill": sstr, "n": n, "kills": row.get("kills"),
                            "T_band": list(band), "implied_rates": rates})

    return {"slots": slots, "hero_cls": hero_cls, "clocks": clocks, "tests": tests,
            "kills": kills_rows, "unidentified": unidentified,
            "death_turns": death_turns, "cadence_checks": cadence_checks,
            "vulcanus_s2": vulcanus_s2, "inventory": inventory}


# ---------------------------------------------------------------------------
# Pooling
# ---------------------------------------------------------------------------

def pool_tests(tests: list[dict]) -> list[dict]:
    by_skill: dict[str, list[dict]] = {}
    for t in tests:
        by_skill.setdefault(t["skill"], []).append(t)
    pooled = []
    for skill in sorted(by_skill):
        rows = by_skill[skill]
        p = rows[0]["p_catalog"]
        streams = sorted({s for r in rows for s in r["streams"]})
        entry = {"skill": skill, "p_catalog": p, "n_reports": len(rows),
                 "n_total": sum(r["n"] for r in rows), "streams": {}}
        for sk in streams:
            use = [r for r in rows if sk in r["streams"]]
            if not use:
                continue
            k = sum(r["n"] for r in use)
            lo = sum(r["streams"][sk]["N"][0] for r in use)
            hi = sum(r["streams"][sk]["N"][1] for r in use)
            max_p, argmax_n = scan_max_p(k, lo, hi, p)
            entry["streams"][sk] = {
                "k": k, "N": [lo, hi],
                "rate": [round(k / hi, 4), round(k / max(lo, k), 4)],
                "max_p": round(max_p, 6), "argmax_N": argmax_n,
                "verdict": verdict_from_p(max_p)}
        verdicts = {sk: v["verdict"] for sk, v in entry["streams"].items()}
        cons = [sk for sk, v in verdicts.items() if v != "rejected"]
        if not cons:
            entry["overall"] = "CONTRADICTED (all streams rejected)"
        elif len(cons) == 1:
            entry["overall"] = f"stream-identified: {cons[0]}"
        else:
            entry["overall"] = f"consistent (underdetermined among {cons})"
        pooled.append(entry)
    return pooled


# ---------------------------------------------------------------------------
# Conditional (T-free) ratio tests
# ---------------------------------------------------------------------------

RATIO_PAIRS = [
    # (hero, slot A, slot B) — both chance skills, assumed same opportunity
    # stream (both defensive "on being engaged" procs of the same hero).
    ("Gisela", "Skill 2", "Skill 3"),
]


def ratio_tests(reports, slots) -> list[dict]:
    out = []
    for hero, sa, sb in RATIO_PAIRS:
        ia, ib = slots.get((hero, sa)), slots.get((hero, sb))
        if not ia or not ib or not isinstance(ia.p, float) or not isinstance(ib.p, float):
            continue
        p_cond = ia.p / (ia.p + ib.p)
        per_rep, ka_t, m_t = [], 0, 0
        for rid, rep in reports:
            for side_key in ("friendly", "enemy"):
                counts = {}
                for lh in rep[side_key].get("lead_heroes", []):
                    if lh["name"] != hero:
                        continue
                    for row in lh.get("rows", []):
                        m = re.match(rf"^{hero} (Skill [123])\b", row["skill"])
                        if m:
                            counts[m.group(1)] = int(row.get("triggered", 0) or 0)
                if sa in counts and sb in counts and counts[sa] + counts[sb] > 0:
                    ka, m_tot = counts[sa], counts[sa] + counts[sb]
                    pv = binom_two_sided_p(ka, m_tot, p_cond)
                    per_rep.append({"rid": rid, "side": side_key, "kA": ka,
                                    "kB": counts[sb], "p_value": round(pv, 4)})
                    ka_t += ka
                    m_t += m_tot
        if per_rep:
            pv = binom_two_sided_p(ka_t, m_t, p_cond)
            out.append({"hero": hero, "slots": [sa, sb],
                        "pA": ia.p, "pB": ib.p, "p_cond": round(p_cond, 4),
                        "per_report": per_rep, "pooled_kA": ka_t, "pooled_m": m_t,
                        "pooled_rate": round(ka_t / m_t, 4),
                        "pooled_p_value": round(pv, 4),
                        "note": "T-free conditional binomial; assumes both skills "
                                "share one opportunity stream"})
    return out


# ---------------------------------------------------------------------------
# T12 prose dump (verbatim; the T12 anchors have no structured trigger data)
# ---------------------------------------------------------------------------

PROSE_KEY_RE = re.compile(r"timeline|trigger|oracle|clock|finding|structural|note",
                          re.IGNORECASE)


def t12_prose() -> dict:
    out = {}
    for path in sorted(T12_DIR.glob(T12_GLOB)):
        data = json.loads(path.read_text(encoding="utf-8"))
        fields = {}

        def walk(obj, prefix=""):
            if isinstance(obj, dict):
                for kk, vv in obj.items():
                    key = f"{prefix}.{kk}" if prefix else kk
                    if isinstance(vv, (dict, list)):
                        walk(vv, key)
                    elif isinstance(vv, str) and PROSE_KEY_RE.search(kk):
                        fields[key] = vv
            elif isinstance(obj, list):
                for i, vv in enumerate(obj):
                    walk(vv, f"{prefix}[{i}]")

        walk(data)
        out[path.name] = fields
    return out


# ---------------------------------------------------------------------------
# Power grid for the experiment menu
# ---------------------------------------------------------------------------

def exact_power(n: int, p0: float, p1: float, alpha: float = 0.05) -> float:
    vec1 = _pmf_vector(n, p1)
    return sum(vec1[k] for k in range(n + 1)
               if binom_two_sided_p(k, n, p0) < alpha)


POWER_CASES = [
    # (label, p0 = null to reject, p1 = alternative, Ns)
    ("Volley 10% vs 20%", 0.10, 0.20, [30, 60, 100, 200]),
    ("Ambusher 20% vs 10%", 0.20, 0.10, [30, 60, 100, 200]),
    ("Crystal Lance I 10% vs II 15%", 0.10, 0.15, [100, 200, 400, 800]),
    ("Crystal Gunpowder 20% (cat.) vs 30%", 0.20, 0.30, [60, 100, 200, 400]),
    ("Crystal Shield I 25% vs II 37.5%", 0.25, 0.375, [60, 100, 200, 400]),
    ("Incandescent Field 10% vs 15%", 0.10, 0.15, [100, 200, 400, 800]),
    ("Rufus S3 20%: per-turn vs 3x-stream (60%)", 0.20, 0.60, [20, 30, 45]),
]


def power_table() -> list[dict]:
    out = []
    for label, p0, p1, ns in POWER_CASES:
        rows = []
        for n in ns:
            k_exp = round(n * p1)
            ci = clopper_pearson(k_exp, n)
            rows.append({"N": n, "power": round(exact_power(n, p0, p1), 3),
                         "ci_width_at_expected": round(ci[1] - ci[0], 3)})
        out.append({"case": label, "p0": p0, "p1": p1, "rows": rows})
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def fmt_band(b):
    return f"[{b[0]},{b[1]}]" if b else "-"


def main() -> None:
    res = mine()
    res_offset = mine("offset1")   # convention-sensitivity pass
    reports = load_reports()
    pooled = pool_tests([t for t in res["tests"]])
    pooled_offset = pool_tests([t for t in res_offset["tests"]])
    ratios = ratio_tests(reports, res["slots"])
    prose = t12_prose()
    power = power_table()

    # do any pooled stream VERDICTS flip if the cadence convention is offset-1?
    off_map = {(p["skill"], sk): v["verdict"]
               for p in pooled_offset for sk, v in p["streams"].items()}
    flips = []
    for p in pooled:
        for sk, v in p["streams"].items():
            ov = off_map.get((p["skill"], sk))
            if ov is not None and ov != v["verdict"]:
                flips.append({"skill": p["skill"], "stream": sk,
                              "floor": v["verdict"], "offset1": ov})

    print("=" * 78)
    print("STAGE 7A TELEMETRY MINING - RAW_01..08 skill-trigger counts vs catalog")
    print("=" * 78)

    print("\n## Distinct skill strings observed (inventory; count = occurrences)")
    for key in sorted(res["inventory"]):
        print(f"  {res['inventory'][key]:>2}x  {key}")

    print("\n## Per-report battle clocks (turn-count bands from cadence skills)")
    print(f"{'rid':7} {'floor-conv':12} {'offset-conv':12} {'+strikes(A1)':13} source")
    for c in res["clocks"]:
        print(f"{c['rid']:7} {fmt_band(c['T_floor']):12} {fmt_band(c['T_offset1']):12} "
              f"{fmt_band(c['T_floor_with_strikes']):13} {c['T_source']}")
        for e in c["primary_rows"]:
            print(f"        turns-clock: {e['side']:8} {e['skill']:20} k={e['k']} n={e['n']}"
                  f" -> {fmt_band(cadence_band(e['n'], e['k'], 'floor'))}")
        for e in c["secondary_rows"]:
            tag = "alive-end" if e.get("class_alive_end") else "WIPED"
            print(f"        strikes-clock({tag}): {e['side']:8} {e['skill']:20} "
                  f"k={e['k']} n={e['n']} class={e.get('hero_class')}")

    print("\n## Chance-proc binomial tests, per report (exact two-sided p, scanned over N-band)")
    hdr = f"{'rid':7}{'side':9}{'skill':22}{'n':>4} {'p_cat':>6}  stream-> maxp/verdict"
    print(hdr)
    for t in res["tests"]:
        streams = "  ".join(
            f"{sk}:N{v['N']} p={v['max_p']:.3g} {v['verdict'].upper()}"
            for sk, v in t["streams"].items())
        print(f"{t['rid']:7}{t['side']:9}{t['skill']:22}{t['n']:>4} "
              f"{t['p_catalog']:>6}  {streams}")

    print("\n## Pooled per skill (across all reports)")
    for p in pooled:
        print(f"  {p['skill']}  p_cat={p['p_catalog']}  n_total={p['n_total']} "
              f"({p['n_reports']} report-sides)")
        for sk, v in p["streams"].items():
            print(f"      {sk:20} k={v['k']:>3} N={v['N']} rate={v['rate']} "
                  f"max_p={v['max_p']:.4g} -> {v['verdict'].upper()}")
        print(f"      OVERALL: {p['overall']}")

    print("\n## T-free conditional ratio tests (same-hero chance pairs)")
    for r in ratios:
        print(f"  {r['hero']} {r['slots'][0]} vs {r['slots'][1]}: pA={r['pA']} pB={r['pB']}"
              f" -> expect share {r['p_cond']}")
        for pr in r["per_report"]:
            print(f"      {pr['rid']} {pr['side']:8} kA={pr['kA']:>3} kB={pr['kB']:>3} "
                  f"p={pr['p_value']}")
        print(f"      POOLED kA={r['pooled_kA']} / m={r['pooled_m']} "
              f"rate={r['pooled_rate']} p={r['pooled_p_value']}")

    print("\n## Cadence self-checks (strikes-cadence skills vs prediction if class alive all T)")
    for c in res["cadence_checks"]:
        print(f"  {c['rid']} {c['side']:8} {c['skill']:20} k={c['k']} n={c['n']:>3} "
              f"pred-if-alive={c['pred_if_alive_all_T']} class={c['class']} "
              f"alive_end={c['class_alive_end']}")

    print("\n## Class death-turn estimates (from strikes-cadence counters of wiped classes)")
    for d in res["death_turns"]:
        flag = "  ** IMPOSSIBLE under catalog cadence -- counter exceeds battle length **" \
            if d["impossible_under_catalog_cadence"] else ""
        print(f"  {d['rid']} {d['side']:8} {d['class']:9} died ~turns "
              f"{d['death_turn_band_floor_conv']}  (from {d['from_skill']} k={d['k']} n={d['n']}){flag}")

    print("\n## Cadence-convention sensitivity (pooled verdicts, floor vs offset-1)")
    if flips:
        for f in flips:
            print(f"  FLIP: {f['skill']} / {f['stream']}: floor={f['floor']} offset1={f['offset1']}")
    else:
        print("  no pooled stream verdict changes between the floor and offset-1 conventions")

    print("\n## Vulcanus S2 at rally scale (cadence_multi; research: every-6th per unit)")
    for v in res["vulcanus_s2"]:
        print(f"  {v['rid']} {v['side']:8} n={v['n']} T={fmt_band(v['T_band'])} "
              f"single-stack preds={v['pred_single_stack']}")

    print("\n## Kills-column rows (direct-damage attribution; Phase-B EV input)")
    for kr in res["kills"]:
        print(f"  {kr['rid']} {kr['side']:8} {kr['hero']:10} n={kr['n']:>3} "
              f"kills={kr['kills']:>7} per-trigger={kr['kills_per_trigger']} :: {kr['skill'][:60]}")

    print("\n## Unidentified icon rows (rate analysis - HYPOTHESIS GENERATION ONLY)")
    for u in res["unidentified"]:
        print(f"  {u['rid']} {u['side']:8} {u['hero']:10} [{u['icon_class'] or u['hero_class']}] "
              f"n={u['n']:>3} kills={u['kills']} rates={u['implied_rates']} :: {u['skill'][:55]}")

    print("\n## T12 anchors - verbatim prose fields (no structured trigger data exists)")
    for fname, fields in prose.items():
        print(f"  {fname}:")
        for key in sorted(fields):
            txt = fields[key]
            txt = txt if len(txt) <= 700 else txt[:700] + " ...[truncated]"
            print(f"    - {key}: {txt}")

    print("\n## Binomial power grid (for the Stage-7 experiment menu)")
    for case in power:
        rows = "  ".join(f"N={r['N']}: power={r['power']}, CIw={r['ci_width_at_expected']}"
                         for r in case["rows"])
        print(f"  {case['case']} (reject p0={case['p0']} when true p={case['p1']}): {rows}")

    # ---- deterministic JSON emit --------------------------------------------
    emit = {
        "clocks": [{k: v for k, v in c.items() if k != "slots"} for c in res["clocks"]],
        "tests": res["tests"],
        "pooled": pooled,
        "pooled_offset_convention": pooled_offset,
        "convention_flips": flips,
        "ratio_tests": ratios,
        "cadence_checks": res["cadence_checks"],
        "death_turns": res["death_turns"],
        "vulcanus_s2": res["vulcanus_s2"],
        "kills": res["kills"],
        "unidentified": res["unidentified"],
        "t12_prose": prose,
        "power": power,
        "meta": {
            "script": "wos_sim/formula_research/stage7a_telemetry.py",
            "inputs": "wos_sim/data/reports/report_001..008.json + "
                      "wos_sim/data/pvp_t12_report_001..005.json",
            "catalog_sources": "wos_sim.loader.load_skill_book() + "
                               "wos_sim.troop_catalog.TROOP_SKILL_CATALOG",
            "conventions": {
                "cadence_floor": "fires at k,2k,..: n=floor(T/k) (primary; "
                                 "Martin-confirmed report_001 notes; Vulcanus S3 "
                                 "triangulated 2026-07-18)",
                "display1": "Triggered=1 rows are uninformative (report_001 note 9)",
                "A1": "one attack event per class-stack per battle turn",
            },
        },
    }
    OUT_JSON.write_text(json.dumps(emit, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(f"\nJSON written: {OUT_JSON}")


if __name__ == "__main__":
    main()
