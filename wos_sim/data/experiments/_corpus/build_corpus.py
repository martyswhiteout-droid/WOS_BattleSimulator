#!/usr/bin/env python3
"""
build_corpus.py — canonical Type-1 (deterministic) WoS battle-report corpus builder.

Walks the fixed set of input sources under wos_sim/data/experiments/, normalizes
every battle report (v2-schema JSON, the NanoMart ledger, hand-written manual
markdown rows, and legacy free-text exp*.json summaries) into one row schema,
applies the corrections.json overrides registry, and writes:

  - TYPE1_CORPUS.json  (machine-readable: {generated_at, generator, row_count, rows:[...]})
  - TYPE1_CORPUS.md    (human master table, grouped by folder, with coverage matrices)

This script never mutates any source file. Run it from anywhere; all paths are
resolved relative to this file's location (so the "Lab Rat" space-in-folder-name
issue is a non-issue — we never touch a shell glob for it).

Usage:
    py build_corpus.py
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # keep _corpus/ free of __pycache__ clutter (we `import corpus` below)

import datetime
import json
import re
from collections import defaultdict
from pathlib import Path

# --------------------------------------------------------------------------
# Paths (all resolved relative to this file, per the "run clean from _corpus
# dir" requirement; pathlib handles the space in "Lab Rat" transparently).
# --------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent                       # .../wos_sim/data/experiments/_corpus
EXPERIMENTS_ROOT = HERE.parent                                # .../wos_sim/data/experiments
DATA_ROOT = EXPERIMENTS_ROOT.parent                            # .../wos_sim/data
WOS_SIM_ROOT = DATA_ROOT.parent                                # .../wos_sim
REPO_ROOT = WOS_SIM_ROOT.parent                                # .../Battle Simulator

TROOP_STATS_PATH = REPO_ROOT / "docs" / "TroopStats" / "WOS_Troop_Stats_FC1-FC10_T1-T10.json"
LEDGER_PATH = WOS_SIM_ROOT / "formula_research" / "ledger_dataset.json"
LEDGER_MD_PATH = EXPERIMENTS_ROOT / "NANOMART_EXPERIMENT_LEDGER.md"
MANUAL_MD_PATH = EXPERIMENTS_ROOT / "MuellerAlpaca_Gatot_2v2" / "COMPOSITION_TESTS_manual.md"
CORRECTIONS_PATH = HERE / "corrections.json"
OUT_JSON_PATH = HERE / "TYPE1_CORPUS.json"
OUT_MD_PATH = HERE / "TYPE1_CORPUS.md"

# Section A: folder -> allowed filename-prefix tuple, or None to accept every
# *.json in that folder. Lab Rat and MuellerAlpaca contain a handful of files
# that do NOT belong to this ingestion (e.g. 4 "LabRat_32v1.../33v1.../66v1.../
# 67v1..." files physically living inside MuellerAlpaca/ that don't match any
# of the 3 prefixes below) -- confirmed by exact prefix-count sanity checks
# against the task's expected per-folder row counts before writing this.
FOLDER_PREFIXES = {
    "Lab Rat": ("FarSeer_1v1_", "LabRat_1v1_", "FarSeer_Beast_1v18_"),
    "MuellerAlpaca": ("MuellerAlpaca_", "MuellerMiniMart_", "Alpaca_", "RFJPlayer_1v1_", "LabRat_"),  # LabRat_ = T3 MM/Lan threshold pairs (32/33v1, 66/67v1) — recovered 2026-07-14; prefix widened from "MuellerAlpaca_1v1_" 2026-07-19 for the 204v1/205v1 B_Alpaca knife-edge (count-style names)
    "MuellerAlpaca_Gatot_v4": None,
    "ENIF": None,  # E-NIF battery (lives at wos_sim/data/ENIF, sibling of experiments/)
    "MuellerAlpaca_Gatot_v5": None,
    "MuellerAlpaca_Gatot_2v2": None,
    "Meuller_Alpaca_v5_8_Battle": None,
    "FarSeerGatot_v3": None,
    "AlpacaGatot_FC1_T6_LanMM": None,
}

# Section D: legacy free-text summaries at the experiments root.
LEGACY_FILES = [
    "exp0_beast.json",
    "exp1_mirror_20k.json",
    "exp2_mirror_2k.json",
    "exp3a_lancer.json",
    "exp3b_lancer.json",
    "exp4_inf_vs_lancer.json",
    "exp4b_inf_vs_lancer_mueller_updated.json",
    "exp4c_inf_vs_lancer_gordon.json",
    "exp5_inf_vs_marksman.json",
]

CLASS_NAMES = ("Infantry", "Lancer", "Marksman")

# Hero-name roster the determinism taxonomy actually cares about. Any other
# hero name seen in a report (e.g. "Lloyd"/"Ling Xue" cosmetic hero cards
# parked in an off-class hero slot that never fights, or "SeoYoon" - a flat,
# non-proc % buff) is deliberately NOT treated as "special": it neither makes
# a battle non-"clean" nor changes its bucket. See build_corpus README notes
# in the final report for the reasoning; rows with an out-of-roster hero name
# get an informational "other_hero_present" flag so nothing is hidden.
SPECIAL_ROSTER = {"Gatot", "Vulcanus", "Gordon", "Elif", "Ursar"}

BASE_TABLE = None  # populated in main(); module-global so correction-time
                    # recompute (after a corrections.json class/tier override)
                    # can re-derive base/eff without re-threading the table
                    # through every call site.


# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------

def rel(path: Path) -> str:
    """Path relative to the repo root, forward-slashed, for portable source_path values."""
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dedupe(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def add_flag(row: dict, flag: str) -> None:
    if flag not in row["flags"]:
        row["flags"].append(flag)


def normalize_winner(raw):
    """Normalize the many winner-string spellings seen across sources to 'attacker'/'defender'."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in ("attacker", "defender"):
        return s
    if "attacker" in s and "victory" in s:
        return "attacker"
    if "attacker" in s and "defeat" in s:
        return "defender"
    if "defender" in s and "victory" in s:
        return "defender"
    if "defender" in s and "defeat" in s:
        return "attacker"
    return s or None


_TS_RE = re.compile(r"_(\d{8})_(\d{6})$")


def parse_battle_ts(stem: str):
    """Extract _YYYYMMDD_HHMMSS from a filename stem (anchored at the end). None if absent
    (e.g. the '..._UserSummary' and '..._20260712_unknown' files have no parseable timestamp)."""
    m = _TS_RE.search(stem)
    if not m:
        return None
    try:
        dt = datetime.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


# --------------------------------------------------------------------------
# tier / fire-crystal parsing
# --------------------------------------------------------------------------

_FC_RE = re.compile(r"FC\s*(\d+)", re.IGNORECASE)
_TIER_DIRECT_RE = re.compile(r"(?<![A-Za-z])T(\d+)\b")
_TIER_LV_RE = re.compile(r"Lv\.?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def parse_tier_fc(source: dict):
    """Resolve (tier:int|None, fc:int|None) from a dict that may carry explicit
    tier_code/fc_code/fire_crystal_level fields (preferred) and/or a free-text
    tier_display like 'Lv 1.0' / 'Lv.6.0' / 'FC1 Lv 1.0' / 'FC1 Lv.6.0' / 'FC1 T1 ...'."""
    if not isinstance(source, dict):
        return None, None
    fc = None
    tier = None

    fc_code = source.get("fc_code") or source.get("fire_crystal_level")
    if fc_code:
        m = re.search(r"(\d+)", str(fc_code))
        if m:
            fc = int(m.group(1))

    tier_code = source.get("tier_code")
    if tier_code:
        m = re.search(r"(\d+)", str(tier_code))
        if m:
            tier = int(m.group(1))

    td = source.get("tier_display") or ""
    if fc is None:
        m = _FC_RE.search(td)
        if m:
            fc = int(m.group(1))
    if tier is None:
        m = _TIER_DIRECT_RE.search(td)
        if m:
            tier = int(m.group(1))
        else:
            m = _TIER_LV_RE.search(td)
            if m:
                tier = int(round(float(m.group(1))))
    return tier, fc


def lookup_base_stats(base_table, cls_name, tier, fc, flags):
    """troop_classes[cls]['tiers']['T{tier}']['fc_levels']['FC{fc or 1}'] -> {A,D,L,H}.
    Non-FC ('ordinary') troops use the FC1 row per the task's explicit rule."""
    if not cls_name or not tier:
        return None
    fc_key = f"FC{fc if fc else 1}"
    tier_key = f"T{tier}"
    try:
        node = base_table["troop_classes"][cls_name]["tiers"][tier_key]["fc_levels"][fc_key]
        return {"A": node["attack"], "D": node["defense"], "L": node["lethality"], "H": node["health"]}
    except KeyError:
        if "base_stat_lookup_failed" not in flags:
            flags.append("base_stat_lookup_failed")
        return None


def any_proc_risk(classes, base_table):
    """FC3+ troop skills (Crystal Shield/Lance/etc.) carry a chance-based proc.
    FC1/FC2 have an empty active_skills list in the reference table (confirmed
    by inspection) -- so this check is exactly 'does this unit's FC level have
    a populated active_skills list'. No tier itself (T1-T10) gates a troop-class
    skill in the reference table, only the FC level does."""
    for c in classes:
        cls, tier, fc = c.get("cls"), c.get("tier"), c.get("fc")
        if not cls or not tier:
            continue
        fc_key = f"FC{fc if fc else 1}"
        try:
            node = base_table["troop_classes"][cls]["tiers"][f"T{tier}"]["fc_levels"][fc_key]
            if node.get("fire_crystal_troop_skill", {}).get("active_skills"):
                return True
        except KeyError:
            continue
    return False


# --------------------------------------------------------------------------
# class-entry construction (shared by v2 JSON parsing)
# --------------------------------------------------------------------------

def make_class_entry(cls_name, count, tier_source, panel_source, base_table, flags):
    tier, fc = parse_tier_fc(tier_source if isinstance(tier_source, dict) else {})
    base = lookup_base_stats(base_table, cls_name, tier, fc, flags)

    provided_base = tier_source.get("base_troop_stats") if isinstance(tier_source, dict) else None
    if base is not None and isinstance(provided_base, dict):
        keymap = {"A": "Attack", "D": "Defense", "L": "Lethality", "H": "Health"}
        for k, pk in keymap.items():
            pv = provided_base.get(pk)
            if pv is not None:
                try:
                    if abs(float(pv) - float(base[k])) > 0.01:
                        add_flag_list(flags, "base_mismatch")
                except (TypeError, ValueError):
                    pass

    panel = None
    stats_pct = panel_source.get("stats_pct") if isinstance(panel_source, dict) else None
    if cls_name and isinstance(stats_pct, dict):
        panel = stats_pct.get(cls_name)

    eff = None
    if base is not None:
        eff = {}
        for k, pk in (("A", "Attack"), ("D", "Defense"), ("L", "Lethality"), ("H", "Health")):
            pct = panel.get(pk) if panel else None
            if pct is None:
                eff[k] = base[k]
                if pk in ("Lethality", "Health"):
                    add_flag_list(flags, "lh_panel_uncaptured")
            else:
                eff[k] = round(base[k] * (1 + pct / 100.0), 6)

    return {"cls": cls_name, "tier": tier, "fc": fc, "count": count, "base": base, "panel_pct": panel, "eff": eff}


def add_flag_list(flags, flag):
    if flag not in flags:
        flags.append(flag)


_SETUP_PART_RE = re.compile(
    r"(\d+)\s*(?:x\s*)?(?:Lv\.?\s*\d+(?:\.\d+)?\s+)?(Infantry|Lancer|Marksman)", re.IGNORECASE
)


def parse_mixed_setup_text(side_json, base_table, flags):
    """Last-resort fallback: derive a Mixed side's classes[] from the free-text
    setup/tier_display string when no structured composition list is present."""
    text = " ".join(
        str(side_json.get(k) or "") for k in ("tier_display", "setup")
    )
    matches = _SETUP_PART_RE.findall(text)
    if not matches:
        return None
    out = []
    for count_s, cls in matches:
        cls_norm = {"infantry": "Infantry", "lancer": "Lancer", "marksman": "Marksman"}[cls.lower()]
        fake_source = {"tier_display": text}
        out.append(make_class_entry(cls_norm, int(count_s), fake_source, side_json, base_table, flags))
    return out


def build_classes(side_json: dict, base_table: dict, flags: list) -> list:
    """Priority: a single, real (non-Mixed) deployed_class is authoritative and is
    trusted directly -- this is deliberate: at least one report in this corpus
    (ColonelMuller_1v2_T1MMvT1Inf+T1MM_NoHeroes..._112003) has a *stale* wrong
    class sitting in specials.troop_composition while deployed_class itself was
    already hand-corrected, so composition/specials lists are only consulted
    for genuinely Mixed (multi-class) sides, where deployed_class alone can't
    give the breakdown."""
    deployed = (side_json.get("deployed_class") or "").strip()
    if deployed and deployed.lower() != "mixed":
        count = side_json.get("troops")
        return [make_class_entry(deployed, count, side_json, side_json, base_table, flags)]

    comp = side_json.get("composition")
    if isinstance(comp, list) and comp:
        return [
            make_class_entry(part.get("class"), part.get("count"), part, side_json, base_table, flags)
            for part in comp
        ]
    for sp in side_json.get("specials") or []:
        if isinstance(sp, dict) and sp.get("type") == "troop_composition" and sp.get("units"):
            return [
                make_class_entry(u.get("class"), u.get("count"), u, side_json, base_table, flags)
                for u in sp["units"]
            ]
    parsed = parse_mixed_setup_text(side_json, base_table, flags)
    if parsed:
        add_flag_list(flags, "composition_from_setup_text")
        return parsed
    add_flag_list(flags, "composition_unparsed")
    return []


def build_side(side_json: dict, base_table: dict):
    flags = []
    classes = build_classes(side_json or {}, base_table, flags)
    heroes = []
    for hs in (side_json or {}).get("hero_skills") or []:
        heroes.append(
            {
                "hero": hs.get("hero"),
                "slot": hs.get("slot"),
                "name": hs.get("name"),
                "level": hs.get("level"),
                "triggers": hs.get("triggers"),
                "kills": hs.get("kills"),
            }
        )
    casualties = {
        "troops": (side_json or {}).get("troops"),
        "losses": (side_json or {}).get("losses"),
        "injured": (side_json or {}).get("injured"),
        "lightly_injured": (side_json or {}).get("lightly_injured"),
        "survivors": (side_json or {}).get("survivors"),
        "kills": (side_json or {}).get("kills"),
    }
    for sp in (side_json or {}).get("specials") or []:
        if isinstance(sp, dict) and sp.get("type") == "beast_mapping":
            add_flag_list(flags, "beast_mapping_assumed")

    side_row = {
        "name": (side_json or {}).get("name"),
        "classes": classes,
        "heroes": heroes,
        "casualties": casualties,
        "_stats_pct_full": (side_json or {}).get("stats_pct"),  # internal; stripped before output
    }
    return side_row, flags


def build_clock(ti, attacker_json, defender_json):
    if not ti:
        return {"side": None, "hero": None, "skill": None, "triggers": None}
    hero = ti.get("clock_hero")
    triggers = ti.get("trigger_count")
    turns = ti.get("turns")
    side_name, skill_name = None, None
    best_triggers = -1
    exact_found = False
    for sn, sobj in (("attacker", attacker_json), ("defender", defender_json)):
        for hs in (sobj or {}).get("hero_skills") or []:
            if not (hero and hs.get("hero") == hero):
                continue
            hs_triggers = hs.get("triggers")
            is_exact = turns is not None and hs_triggers == turns
            if is_exact and not exact_found:
                side_name, skill_name, exact_found = sn, hs.get("name"), True
            elif not exact_found and isinstance(hs_triggers, (int, float)) and hs_triggers > best_triggers:
                # no exact match yet: prefer the hero's most-active skill (e.g.
                # Gordon's Skill 2/3 cadence skills over an inert Skill 1) so the
                # 'skill' field names something that actually drove the clock.
                side_name, skill_name, best_triggers = sn, hs.get("name"), hs_triggers
    return {"side": side_name, "hero": hero, "skill": skill_name, "triggers": triggers}


def classify_determinism(special_heroes: set) -> str:
    if "Vulcanus" in special_heroes:
        return "vulcanus_deterministic"
    if special_heroes & {"Gordon", "Elif", "Ursar"}:
        return "gordon_deterministic"
    if not special_heroes or special_heroes == {"Gatot"}:
        return "clean"
    return "proc_or_unknown"


# --------------------------------------------------------------------------
# Section A: v2-schema JSON battle reports
# --------------------------------------------------------------------------

def parse_v2_file(path: Path, folder: str, base_table: dict) -> dict:
    data = load_json(path)  # let caller catch/flag exceptions

    attacker_json = data.get("attacker") or {}
    defender_json = data.get("defender") or {}

    attacker_row, aflags = build_side(attacker_json, base_table)
    defender_row, dflags = build_side(defender_json, base_table)
    flags = aflags + dflags

    ti = data.get("turn_inference")
    outcome_raw = data.get("outcome") or {}
    winner = normalize_winner(outcome_raw.get("winner"))
    turns = ti.get("turns") if ti else None
    turns_range = ti.get("turns_range") if ti else None
    turn_method = ti.get("method") if ti else None
    clock = build_clock(ti, attacker_json, defender_json)
    if ti is None:
        add_flag_list(flags, "no_turn_clock")

    heroes_raw = set()
    for side_json in (attacker_json, defender_json):
        for hs in side_json.get("hero_skills") or []:
            h = hs.get("hero")
            if h:
                heroes_raw.add(h)
    special = heroes_raw & SPECIAL_ROSTER
    other = heroes_raw - SPECIAL_ROSTER
    if other:
        add_flag_list(flags, "other_hero_present")
    determinism = classify_determinism(special)

    if any_proc_risk(attacker_row["classes"], base_table) or any_proc_risk(defender_row["classes"], base_table):
        add_flag_list(flags, "proc_risk")

    row = {
        "id": path.stem,
        "source_kind": "json",
        "source_path": rel(path),
        "source_refs": [],
        "folder": folder,
        "battle_ts": parse_battle_ts(path.stem),
        "attacker": attacker_row,
        "defender": defender_row,
        "outcome": {
            "winner": winner,
            "turns": turns,
            "turns_range": turns_range,
            "turn_method": turn_method,
            "clock": clock,
        },
        "determinism": determinism,
        "flags": dedupe(flags),
        "corrections_applied": [],
        "notes_excerpt": (data.get("setup") or "")[:200],
    }
    return row


def make_parse_failed_row(path: Path, folder: str, error: str, source_kind: str = "json") -> dict:
    return {
        "id": path.stem,
        "source_kind": source_kind,
        "source_path": rel(path),
        "source_refs": [],
        "folder": folder,
        "battle_ts": parse_battle_ts(path.stem),
        "attacker": {"name": None, "classes": [], "heroes": [], "casualties": {}},
        "defender": {"name": None, "classes": [], "heroes": [], "casualties": {}},
        "outcome": {
            "winner": None,
            "turns": None,
            "turns_range": None,
            "turn_method": None,
            "clock": {"side": None, "hero": None, "skill": None, "triggers": None},
        },
        "determinism": "proc_or_unknown",
        "flags": ["parse_failed"],
        "corrections_applied": [],
        "notes_excerpt": f"PARSE ERROR: {error}"[:200],
    }


# --------------------------------------------------------------------------
# Section B: NanoMart ledger (formula_research/ledger_dataset.json)
# --------------------------------------------------------------------------

def ledger_side_heroes(heroes_dict: dict) -> list:
    if not heroes_dict:
        return []
    out = []
    vulc = defaultdict(dict)
    for k, v in heroes_dict.items():
        m = re.match(r"vulc_s(\d)_([TK])$", k)
        if m:
            vulc[m.group(1)][m.group(2)] = v
            continue
        m2 = re.match(r"seoyoon_s(\d)$", k)
        if m2:
            n = m2.group(1)
            out.append(
                {"hero": "SeoYoon", "slot": f"Skill {n}", "name": f"Seo-yoon Skill {n}", "level": v,
                 "triggers": None, "kills": None}
            )
            continue
        m3 = re.match(r"gatot_s(\d)$", k, re.IGNORECASE)
        if m3:
            n = m3.group(1)
            out.append(
                {"hero": "Gatot", "slot": f"Skill {n}", "name": f"Gatot Skill {n}", "level": v,
                 "triggers": None, "kills": None}
            )
            continue
        # unrecognized hero-ish key: keep it, don't drop data silently
        out.append({"hero": k, "slot": None, "name": k, "level": v if isinstance(v, (int, float)) else None,
                     "triggers": None, "kills": None})
    for n, d in vulc.items():
        out.append(
            {"hero": "Vulcanus", "slot": f"Skill {n}", "name": f"Vulcanus Skill {n}", "level": None,
             "triggers": d.get("T"), "kills": d.get("K")}
        )
    return out


def parse_ledger_row(entry: dict, base_table: dict, root_json_names: set) -> dict:
    name = entry.get("name")
    att = entry.get("att") or {}
    deff = entry.get("def") or {}

    def side_from_force(force_side):
        force = force_side.get("force") or {}
        stats = force_side.get("stats") or {}
        cls = force.get("cls")
        tier = force.get("tier")
        count = force.get("count")
        eff = {"A": stats.get("A"), "D": stats.get("D"), "L": stats.get("L"), "H": stats.get("H")} if stats else None
        classes = (
            [{"cls": cls, "tier": tier, "fc": None, "count": count, "base": None, "panel_pct": None, "eff": eff}]
            if cls
            else []
        )
        heroes = ledger_side_heroes(force_side.get("heroes") or {})
        out = force_side.get("out") or {}
        casualties = {
            "troops": count,
            "losses": out.get("loss"),
            "injured": out.get("inj"),
            "lightly_injured": out.get("light"),
            "survivors": out.get("surv"),
            "kills": out.get("kills"),
        }
        return {"name": None, "classes": classes, "heroes": heroes, "casualties": casualties}

    attacker_row = side_from_force(att)
    defender_row = side_from_force(deff)

    winner = normalize_winner(entry.get("winner"))
    turns_lo = entry.get("turns_lo")
    turns_hi = entry.get("turns_hi")
    turns = turns_lo if (turns_lo is not None and turns_lo == turns_hi) else None
    turns_range = [turns_lo, turns_hi] if (turns_lo is not None or turns_hi is not None) else None

    # ---- Vulcanus-cadence band re-derivation, phase-3 (2026-07-18) ---------
    # Martin's in-game S3 tooltip + the 10-battle Gatot-clock triangulation
    # (formula_research/vulcanus_cadence_triangulation.py) fixed S3's cadence
    # at turns 3,6,9,... (count = floor(T/3)). The ledger's recorded turn
    # bands were derived at ingestion under the OLD 1,4,7 convention
    # (count = ceil(T/3): S3=k -> T in [3k-2, 3k]) and are +2-shifted.
    # Rather than hand-edit ~40 ledger cells, re-derive the band from the
    # RECORDED proc counters at build time (same registry-transform pattern
    # as corrections.json):  S3=k -> T in [3k, 3k+2]  (k=0 -> [1,2]);
    # S2=m, 1-unit side only (events==turns, procs at 6,12,...) ->
    # T in [6m, 6m+5]  (m=0 -> [1,5]); intersect every recorded constraint.
    band_flags = []

    heroes_raw = {h["hero"] for h in (attacker_row["heroes"] + defender_row["heroes"]) if h.get("hero")}
    special = heroes_raw & SPECIAL_ROSTER
    determinism = classify_determinism(special)

    clock_side = None
    if "Vulcanus" in special:
        if any(h["hero"] == "Vulcanus" for h in attacker_row["heroes"]):
            clock_side = "attacker"
        elif any(h["hero"] == "Vulcanus" for h in defender_row["heroes"]):
            clock_side = "defender"

    if "Vulcanus" in special and turns_range is not None:
        constraints = []
        for side_row in (attacker_row, defender_row):
            side_count = side_row["classes"][0]["count"] if side_row["classes"] else None
            for h in side_row["heroes"]:
                if h.get("hero") != "Vulcanus" or h.get("triggers") is None:
                    continue
                t = h["triggers"]
                if h.get("slot") == "Skill 3":
                    constraints.append((3 * t, 3 * t + 2) if t >= 1 else (1, 2))
                elif h.get("slot") == "Skill 2" and side_count == 1:
                    constraints.append((6 * t, 6 * t + 5) if t >= 1 else (1, 5))
        if constraints:
            new_lo = max(c[0] for c in constraints)
            new_hi = min(c[1] for c in constraints)
            if new_lo > new_hi:
                band_flags.append(
                    f"band_rederivation_conflict(recorded {turns_lo}-{turns_hi} kept; "
                    f"S2/S3 constraints disjoint)")
            elif [new_lo, new_hi] != turns_range:
                band_flags.append(
                    f"band_rederived_phase3(was {turns_lo}-{turns_hi})")
                turns_lo, turns_hi = new_lo, new_hi
                turns_range = [new_lo, new_hi]
                turns = new_lo if new_lo == new_hi else None

    a_cls = attacker_row["classes"][0] if attacker_row["classes"] else {}
    d_cls = defender_row["classes"][0] if defender_row["classes"] else {}
    notes_excerpt = (
        f"{a_cls.get('count')}x T{a_cls.get('tier')} {a_cls.get('cls')} vs "
        f"{d_cls.get('count')}x T{d_cls.get('tier')} {d_cls.get('cls')}"
    )[:200]

    fname = f"{name}.json"
    source_refs = [rel(EXPERIMENTS_ROOT / fname)] if fname in root_json_names else []

    return {
        "id": name,
        "source_kind": "nanomart_ledger",
        "source_path": f"{rel(LEDGER_PATH)}#{name}",
        "source_refs": source_refs,
        "folder": "NanoMart",
        "battle_ts": None,
        "attacker": attacker_row,
        "defender": defender_row,
        "outcome": {
            "winner": winner,
            "turns": turns,
            "turns_range": turns_range,
            "turn_method": "vulcanus_proc_count" if "Vulcanus" in special else None,
            "clock": {
                "side": clock_side,
                "hero": "Vulcanus" if "Vulcanus" in special else None,
                "skill": None,
                "triggers": None,
            },
        },
        "determinism": determinism,
        "flags": band_flags,
        "corrections_applied": [],
        "notes_excerpt": notes_excerpt,
    }


# --------------------------------------------------------------------------
# Section C: manual markdown rows (MuellerAlpaca_Gatot_2v2/COMPOSITION_TESTS_manual.md)
# --------------------------------------------------------------------------

_ARMY_PART_RE = re.compile(
    r"(\d+)\s+(?:(named|naked)\s+)?(Infantry|Marksman|Lancer)(?:\s*\((named|naked)\))?", re.IGNORECASE
)


def parse_army_text(text: str):
    parts = []
    for m in _ARMY_PART_RE.finditer(text):
        count = int(m.group(1))
        cls = m.group(3).capitalize()
        parts.append((cls, count))
    return parts


def _fixed_manual_defender(base_table, flags):
    def_classes = []
    for cls in ("Infantry", "Marksman"):
        base = lookup_base_stats(base_table, cls, 1, 1, flags)
        def_classes.append({"cls": cls, "tier": 1, "fc": 1, "count": 1, "base": base, "panel_pct": None,
                             "eff": dict(base) if base else None})
    return def_classes


def make_manual_row(row_id, folder, attacker_desc, attacker_classes, turns, label, note, base_table,
                     raw_turns_cell=None):
    flags = ["manual_tier_assumed_T1", "manual_no_panel_captured"]
    att_classes = []
    for cls, count in attacker_classes:
        base = lookup_base_stats(base_table, cls, 1, None, flags)
        att_classes.append(
            {"cls": cls, "tier": 1, "fc": None, "count": count, "base": base, "panel_pct": None,
             "eff": dict(base) if base else None}
        )
    def_classes = _fixed_manual_defender(base_table, flags)

    notes_bits = [attacker_desc]
    if raw_turns_cell is not None and str(raw_turns_cell) != str(turns):
        notes_bits.append(f"turns_detail={raw_turns_cell}")
    if note:
        notes_bits.append(note)
    notes_excerpt = " | ".join(b for b in notes_bits if b)[:200]

    total_att_troops = sum(c for _, c in attacker_classes) if attacker_classes else None

    return {
        "id": row_id,
        "source_kind": "manual",
        "source_path": rel(MANUAL_MD_PATH),
        "source_refs": [],
        "folder": folder,
        "battle_ts": None,
        "attacker": {
            "name": "Colonel Mueller",
            "classes": att_classes,
            "heroes": [],
            "casualties": {"troops": total_att_troops, "losses": None, "injured": None,
                           "lightly_injured": None, "survivors": 0, "kills": None},
        },
        "defender": {
            "name": "Alpaca",
            "classes": def_classes,
            "heroes": [
                {"hero": "Gatot", "slot": None, "name": "Gatot", "level": None, "triggers": None, "kills": None},
                {"hero": "Vulcanus", "slot": None, "name": "Vulcanus", "level": None, "triggers": None, "kills": None},
            ],
            "casualties": {"troops": 2, "losses": 0, "injured": 0, "lightly_injured": 0, "survivors": 2,
                           "kills": None},
        },
        "outcome": {
            "winner": "defender",
            "turns": turns,
            "turns_range": None,
            "turn_method": "manual_ladder_note",
            "clock": {"side": "defender", "hero": "Gatot", "skill": "King's Bestowal", "triggers": turns},
        },
        "determinism": "vulcanus_deterministic",
        "flags": flags,
        "corrections_applied": [],
        "notes_excerpt": notes_excerpt,
        "json_missing": True,
        "_manual_label": label,
    }


def _markdown_table_block(lines, header_needle):
    started = False
    collected = []
    for line in lines:
        if not started:
            if header_needle in line:
                started = True
            continue
        stripped = line.strip()
        if stripped.startswith("|"):
            inner = stripped.strip("|")
            # a markdown separator row like "---|---|---" still has interior
            # "|" characters after strip("|") strips only the outer ones --
            # strip those too before testing for "nothing but dashes/spaces".
            if set(inner.replace("-", "").replace(" ", "").replace("|", "")) == set():
                continue  # the |---|---|---| separator row
            collected.append(stripped)
        elif collected:
            break
    return collected


def parse_manual_rows(md_path: Path, folder_label: str, base_table: dict) -> list:
    if not md_path.exists():
        return []
    lines = md_path.read_text(encoding="utf-8").splitlines()
    rows = []

    for line in _markdown_table_block(lines, "| N Infantry | turns |"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        try:
            n = int(cells[0])
            turns = int(cells[1])
        except ValueError:
            continue
        rows.append(
            make_manual_row(
                row_id=f"manual_ladder_n{n}_inf",
                folder=folder_label,
                attacker_desc=f"{n} Infantry",
                attacker_classes=[("Infantry", n)],
                turns=turns,
                label=f"{n} Infantry = {turns} turns",
                note=cells[2] if len(cells) > 2 else "",
                base_table=base_table,
            )
        )

    for line in _markdown_table_block(lines, "| attacker army | turns |"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        army_text, turns_text = cells[0], cells[1]
        note = cells[2] if len(cells) > 2 else ""
        nums = [int(x) for x in re.findall(r"\d+", turns_text)]
        turns = max(nums) if nums else None
        classes = parse_army_text(army_text)
        slug = re.sub(r"[^a-z0-9]+", "_", army_text.lower()).strip("_")
        rows.append(
            make_manual_row(
                row_id=f"manual_mixed_{slug}",
                folder=folder_label,
                attacker_desc=army_text,
                attacker_classes=classes,
                turns=turns,
                label=f"{army_text} = {turns} turns",
                note=note,
                base_table=base_table,
                raw_turns_cell=turns_text,
            )
        )
    return rows


# --------------------------------------------------------------------------
# Section D: legacy free-text exp*.json summaries
# --------------------------------------------------------------------------

def normalize_legacy_winner(outcome_raw, att_cas, def_cas):
    text = None
    if isinstance(outcome_raw, str):
        text = outcome_raw
    elif isinstance(outcome_raw, dict):
        text = outcome_raw.get("winner")
    if text:
        low = text.lower()
        if "attacker" in low and ("won" in low or "victory" in low):
            return "attacker"
        if "defender" in low and ("won" in low or "victory" in low):
            return "defender"
    a_surv = (att_cas or {}).get("survivors")
    d_surv = (def_cas or {}).get("survivors")
    if isinstance(a_surv, (int, float)) and isinstance(d_surv, (int, float)):
        if a_surv > 0 and d_surv == 0:
            return "attacker"
        if d_surv > 0 and a_surv == 0:
            return "defender"
    return None


_LEGACY_CLASS_RE = re.compile(r"\b(Infantry|Lancer|Marksman)\b", re.IGNORECASE)


def parse_legacy_row(path: Path, folder_label: str) -> dict:
    data = load_json(path)
    legacy_flags = []

    def side_block(d):
        if not isinstance(d, dict):
            return {"name": None, "classes": [], "heroes": [], "casualties": {
                "troops": None, "losses": None, "injured": None, "lightly_injured": None,
                "survivors": None, "kills": None}}
        raw_cls = d.get("deployed_class")
        classes = []
        if raw_cls:
            # Some legacy files bake an uncertainty annotation directly into
            # deployed_class, e.g. "Lancer (INFERRED - CONFIRM: which side
            # deployed lancer vs marksman?)". Pull out the clean class token
            # for query-ability but keep the uncertainty visible as a flag
            # rather than silently discarding it.
            m = _LEGACY_CLASS_RE.search(str(raw_cls))
            cls = m.group(1).capitalize() if m else raw_cls
            if cls != raw_cls:
                add_flag_list(legacy_flags, "legacy_class_inferred")
            panel = None
            sp = d.get("stats_pct")
            if isinstance(sp, dict):
                panel = sp.get(cls) or sp.get(raw_cls)
            classes.append({"cls": cls, "tier": None, "fc": None, "count": d.get("troops"),
                             "base": None, "panel_pct": panel, "eff": None})
        return {
            "name": d.get("name"),
            "classes": classes,
            "heroes": [],
            "casualties": {
                "troops": d.get("troops"),
                "losses": d.get("losses"),
                "injured": d.get("injured"),
                "lightly_injured": d.get("lightly_injured"),
                "survivors": d.get("survivors"),
                "kills": d.get("kills"),
            },
        }

    attacker = side_block(data.get("attacker"))
    defender = side_block(data.get("defender") if data.get("defender") is not None else data.get("defender_beast"))

    outcome_raw = data.get("outcome")
    winner = normalize_legacy_winner(outcome_raw, attacker["casualties"], defender["casualties"])

    setup = data.get("setup")
    counter = data.get("counter")
    notes_bits = [str(b) for b in (setup, counter) if b]
    notes_excerpt = " | ".join(notes_bits)[:200]

    return {
        "id": path.stem,
        "source_kind": "legacy_summary",
        "source_path": rel(path),
        "source_refs": [],
        "folder": folder_label,
        "battle_ts": None,
        "attacker": attacker,
        "defender": defender,
        "outcome": {
            "winner": winner,
            "turns": None,
            "turns_range": None,
            "turn_method": None,
            "clock": {"side": None, "hero": None, "skill": None, "triggers": None},
        },
        "determinism": "legacy_unverified",
        "flags": dedupe(legacy_flags),
        "corrections_applied": [],
        "notes_excerpt": notes_excerpt,
    }


# --------------------------------------------------------------------------
# corrections.json application
# --------------------------------------------------------------------------

def recompute_class_entry(entry: dict, side_row: dict, base_table: dict) -> None:
    """Re-derive base/panel_pct/eff for a class entry after a corrections.json
    override changed its cls and/or tier, using the side's full stats_pct
    (kept internally as _stats_pct_full) so the CORRECT class's panel row is
    used, not the one the original mis-parse happened to pick up."""
    cls, tier, fc = entry.get("cls"), entry.get("tier"), entry.get("fc")
    flags_sink = []  # corrections are best-effort re-derivations; don't spam row flags
    base = lookup_base_stats(base_table, cls, tier, fc, flags_sink)
    full = side_row.get("_stats_pct_full") or {}
    panel = full.get(cls) if cls else None
    entry["base"] = base
    entry["panel_pct"] = panel
    if base is not None:
        eff = {}
        for k, pk in (("A", "Attack"), ("D", "Defense"), ("L", "Lethality"), ("H", "Health")):
            pct = panel.get(pk) if panel else None
            eff[k] = base[k] if pct is None else round(base[k] * (1 + pct / 100.0), 6)
        entry["eff"] = eff
    else:
        entry["eff"] = None


def apply_correction_set(row: dict, corr: dict) -> None:
    changes = corr.get("set", {})
    # attacker AND defender overrides, symmetric. <side>_stats_pct supplies the
    # verified panel rows for rows whose source carries none (ledger rows store
    # eff verbatim) -- eff is then re-derived as real base x (1 + pct).
    for side_key, cls_key, tier_key, pct_key in (
        ("attacker", "attacker_true_class", "attacker_true_tier", "attacker_stats_pct"),
        ("defender", "defender_true_class", "defender_true_tier", "defender_stats_pct"),
    ):
        touched = False
        classes = row[side_key]["classes"]
        if not classes:
            continue
        entry = classes[0]
        if cls_key in changes:
            entry["cls"] = changes[cls_key]
            touched = True
        if tier_key in changes:
            entry["tier"] = changes[tier_key]
            touched = True
        if pct_key in changes:
            row[side_key]["_stats_pct_full"] = changes[pct_key]
            touched = True
        if touched:
            recompute_class_entry(entry, row[side_key], BASE_TABLE)
    if changes.get("attacker_naked"):
        add_flag(row, "attacker_naked_corrected")
    row["corrections_applied"].append(
        {
            "match_basename_prefix": corr.get("match_basename_prefix"),
            "set": changes,
            "reason": corr.get("reason"),
            "verified_by": corr.get("verified_by"),
        }
    )


def resolve_ledger_md_names(line_numbers: set) -> list:
    """corrections.json's suspect_flags reference LINE NUMBERS in
    NANOMART_EXPERIMENT_LEDGER.md (not ledger_dataset.json array indices --
    verified by content: md line 32 is 'NanoMart_1v1_T5InfvT1Inf_SeoYoonlvl3_
    Vulcanus' turns 79-81, md line 69 is 'NanoMart_SetA_1v1_T5InfvT1Inf_
    SeoYoonlvl3_Vulcanus' turns 67-69 -- identical deployed stats, disjoint
    turn bands, exactly matching the 'hard_conflict' reason text; the ledger
    JSON array indices 32/69 point at unrelated rows that don't match the
    reason text at all)."""
    names = []
    if not LEDGER_MD_PATH.exists():
        return names
    with LEDGER_MD_PATH.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            if i in line_numbers:
                parts = line.split("|")
                if len(parts) > 1:
                    names.append(parts[1].strip())
    return names


def apply_corrections(all_rows: list, corrections_data: dict) -> list:
    ambiguities = []
    by_kind = defaultdict(list)
    for r in all_rows:
        by_kind[r["source_kind"]].append(r)

    for corr in corrections_data.get("corrections", []):
        prefix = corr.get("match_basename_prefix")
        if not prefix:
            continue
        # match_kind (default "json") lets a correction target other source
        # kinds, e.g. "nanomart_ledger" rows whose true classes Martin verified
        match_kind = corr.get("match_kind", "json")
        matched = [r for r in by_kind[match_kind] if r["id"].startswith(prefix)]
        if not matched:
            ambiguities.append(f"corrections: match_basename_prefix matched 0 rows: {prefix}")
            continue
        for r in matched:
            apply_correction_set(r, corr)

    for sus in corrections_data.get("suspect_flags", []):
        reason = sus.get("reason")
        flag = sus.get("flag")
        if "match_basename_prefix" in sus:
            prefix = sus["match_basename_prefix"]
            matched = [r for r in by_kind["json"] if r["id"].startswith(prefix)]
            if not matched:
                ambiguities.append(f"suspect_flags: match_basename_prefix matched 0 rows: {prefix}")
            for r in matched:
                add_flag(r, flag)
                r["corrections_applied"].append({"flag": flag, "reason": reason})
        elif "ledger_lines" in sus or "ledger_line" in sus:
            line_nums = sus.get("ledger_lines")
            if line_nums is None:
                line_nums = [sus["ledger_line"]]
            names = resolve_ledger_md_names(set(line_nums))
            matched = [r for r in by_kind["nanomart_ledger"] if r["id"] in names]
            if not matched:
                ambiguities.append(f"suspect_flags: ledger_lines {line_nums} resolved to names {names}, matched 0 rows")
            for r in matched:
                add_flag(r, flag)
                r["corrections_applied"].append({"flag": flag, "reason": reason})
        elif "manual_row" in sus:
            label = sus["manual_row"]
            matched = [r for r in by_kind["manual"] if r.get("_manual_label") == label]
            if not matched:
                ambiguities.append(f"suspect_flags: manual_row matched 0 rows: {label!r}")
            for r in matched:
                add_flag(r, flag)
                r["corrections_applied"].append({"flag": flag, "reason": reason})
        else:
            ambiguities.append(f"suspect_flags: entry has no recognized match key: {sus!r}")
    return ambiguities


# --------------------------------------------------------------------------
# markdown report writer
# --------------------------------------------------------------------------

def format_matchup(row: dict) -> str:
    def label(side_key):
        classes = row.get(side_key, {}).get("classes") or []
        if not classes:
            return "?"
        parts = []
        for c in classes:
            fc = f"FC{c['fc']}" if c.get("fc") else ""
            parts.append(f"{c.get('count')}x{fc}T{c.get('tier')}{c.get('cls')}")
        return "+".join(parts)

    return f"{label('attacker')} v {label('defender')}"


def write_markdown(rows: list, out_path: Path, coverage_data: dict) -> None:
    lines = []
    lines.append("# TYPE1_CORPUS — canonical Type-1 deterministic battle-report corpus")
    lines.append("")
    lines.append(f"Generated: {datetime.datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append(f"**Total rows: {len(rows)}**")
    lines.append("")

    lines.append("## Coverage")
    lines.append("")
    lines.append("### By folder")
    lines.append("")
    lines.append("| folder | rows |")
    lines.append("|---|---|")
    for k, v in sorted(coverage_data["folder"].items(), key=lambda kv: (-kv[1], str(kv[0]))):
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("### By determinism class")
    lines.append("")
    lines.append("| determinism | rows |")
    lines.append("|---|---|")
    for k, v in sorted(coverage_data["determinism"].items(), key=lambda kv: (-kv[1], str(kv[0]))):
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("### Matchup coverage (winner class -> loser class)")
    lines.append("")
    lines.append("| winner class | loser class | rows |")
    lines.append("|---|---|---|")
    for (a, b), v in sorted(coverage_data["matchup"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {a} | {b} | {v} |")
    lines.append("")

    lines.append("### Same-class Infantry mirrors (winner tier -> loser tier)")
    lines.append("")
    lines.append("| winner T | loser T | rows |")
    lines.append("|---|---|---|")
    for (a, b), v in sorted(coverage_data["same_class_infantry_tier_pairs"].items(), key=lambda kv: str(kv[0])):
        lines.append(f"| T{a} | T{b} | {v} |")
    lines.append("")

    lines.append("## Corrections & suspect flags applied")
    lines.append("")
    any_applied = False
    for r in rows:
        if r.get("corrections_applied"):
            any_applied = True
            lines.append(f"- **{r['id']}** (`{r['folder']}`, {r['source_kind']}):")
            for c in r["corrections_applied"]:
                if "set" in c:
                    lines.append(f"  - set `{c['set']}` — {c['reason']} (verified_by: {c.get('verified_by')})")
                else:
                    lines.append(f"  - flag `{c.get('flag')}` — {c['reason']}")
    if not any_applied:
        lines.append("(none applied)")
    lines.append("")

    lines.append("## Battles by folder")
    lines.append("")
    by_folder = defaultdict(list)
    for r in rows:
        by_folder[r["folder"]].append(r)
    for folder in sorted(by_folder):
        frows = sorted(by_folder[folder], key=lambda x: x["id"])
        lines.append(f"### {folder} ({len(frows)} rows)")
        lines.append("")
        lines.append("| id | matchup | winner | turns | determinism | flags |")
        lines.append("|---|---|---|---|---|---|")
        for r in frows:
            matchup = format_matchup(r)
            winner = (r.get("outcome") or {}).get("winner")
            turns = (r.get("outcome") or {}).get("turns")
            flags = ",".join(r.get("flags") or [])
            row_id = r["id"].replace("|", "\\|")
            lines.append(f"| {row_id} | {matchup} | {winner} | {turns} | {r['determinism']} | {flags} |")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    global BASE_TABLE
    BASE_TABLE = load_json(TROOP_STATS_PATH)
    corrections_data = load_json(CORRECTIONS_PATH)

    all_rows = []
    parse_failures = []

    # Section A
    for folder, prefixes in FOLDER_PREFIXES.items():
        folder_path = EXPERIMENTS_ROOT / folder
        if not folder_path.exists():
            folder_path = EXPERIMENTS_ROOT.parent / folder   # e.g. ENIF
        if not folder_path.exists():
            print(f"WARNING: folder missing: {folder_path}", file=sys.stderr)
            continue
        json_files = sorted(folder_path.glob("*.json"))
        for jf in json_files:
            if prefixes is not None and not any(jf.name.startswith(p) for p in prefixes):
                continue
            try:
                row = parse_v2_file(jf, folder, BASE_TABLE)
            except Exception as e:  # noqa: BLE001 - deliberately broad; never abort the build
                row = make_parse_failed_row(jf, folder, f"{type(e).__name__}: {e}")
                parse_failures.append((str(jf), str(e)))
            all_rows.append(row)

    # Section B
    root_json_names = {p.name for p in EXPERIMENTS_ROOT.glob("NanoMart_*.json")}
    try:
        ledger_data = load_json(LEDGER_PATH)
        for entry in ledger_data:
            try:
                all_rows.append(parse_ledger_row(entry, BASE_TABLE, root_json_names))
            except Exception as e:  # noqa: BLE001
                nm = entry.get("name", "unknown")
                parse_failures.append((f"ledger:{nm}", str(e)))
                all_rows.append(make_parse_failed_row(Path(nm), "NanoMart", str(e), source_kind="nanomart_ledger"))
    except FileNotFoundError:
        print(f"WARNING: ledger file missing: {LEDGER_PATH}", file=sys.stderr)

    # Section C
    all_rows.extend(parse_manual_rows(MANUAL_MD_PATH, "MuellerAlpaca_Gatot_2v2", BASE_TABLE))

    # Section D
    for name in LEGACY_FILES:
        p = EXPERIMENTS_ROOT / name
        if not p.exists():
            print(f"WARNING: legacy file missing: {p}", file=sys.stderr)
            continue
        try:
            all_rows.append(parse_legacy_row(p, "legacy"))
        except Exception as e:  # noqa: BLE001
            all_rows.append(make_parse_failed_row(p, "legacy", str(e), source_kind="legacy_summary"))
            parse_failures.append((str(p), str(e)))

    # Corrections
    ambiguities = apply_corrections(all_rows, corrections_data)

    # Strip internal helper keys before serialization
    for row in all_rows:
        row.get("attacker", {}).pop("_stats_pct_full", None)
        row.get("defender", {}).pop("_stats_pct_full", None)
        row.pop("_manual_label", None)

    # Deterministic ordering
    all_rows.sort(key=lambda r: (r["folder"], r["id"]))

    payload = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "generator": "build_corpus.py",
        "row_count": len(all_rows),
        "rows": all_rows,
    }
    OUT_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    sys.path.insert(0, str(HERE))
    import corpus as corpus_mod  # local module, see corpus.py

    cov = corpus_mod.coverage(all_rows)
    write_markdown(all_rows, OUT_MD_PATH, cov)

    print("=== TYPE1_CORPUS build summary ===")
    print(f"Total rows: {len(all_rows)}")
    print()
    print("Per-folder counts:")
    for k, v in sorted(cov["folder"].items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"  {k:<32} {v}")
    print()
    print("Determinism counts:")
    for k, v in sorted(cov["determinism"].items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"  {k:<24} {v}")
    print()
    print("Matchup coverage (winner class -> loser class):")
    for (a, b), v in sorted(cov["matchup"].items(), key=lambda kv: -kv[1]):
        print(f"  {a:<10} -> {b:<10} {v}")
    print()
    print("Same-class Infantry mirrors (winner T -> loser T):")
    for (a, b), v in sorted(cov["same_class_infantry_tier_pairs"].items(), key=lambda kv: str(kv[0])):
        print(f"  T{a} -> T{b}   {v}")
    print()
    if parse_failures:
        print(f"PARSE FAILURES ({len(parse_failures)}):")
        for fn, err in parse_failures:
            print(f"  {fn}: {err}")
        print()
    if ambiguities:
        print(f"AMBIGUITIES ({len(ambiguities)}):")
        for a in ambiguities:
            print(f"  {a}")
        print()
    print(f"Wrote {OUT_JSON_PATH}")
    print(f"Wrote {OUT_MD_PATH}")


if __name__ == "__main__":
    main()
