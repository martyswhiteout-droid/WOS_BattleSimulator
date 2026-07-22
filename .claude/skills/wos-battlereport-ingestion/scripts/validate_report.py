"""Validator for canonical WoS battle-report JSON (schema v2).

Usage:
    py validate_report.py <report.json> [more.json ...]

Exit 0 = all files pass (warnings allowed). Exit 1 = any ERROR.

ERRORs are schema/consistency violations that make the file unusable as
calibration data. WARNINGs are suspicious-but-possible values (usually OCR
digit errors) that a human must confirm. Machine-checking these identities is
what makes ingestion deterministic across engines - never hand-verify.
"""
from __future__ import annotations

import json
import sys

TOP_KEYS = ["schema_version", "_type", "type", "battle_date", "recommended_filename",
            "setup", "outcome", "turn_inference", "attacker", "notes",
            "source_images", "_extraction", "_validation"]
SIDE_REQUIRED = ["name", "role", "troops", "stats_capture"]
CLASSES = ("Infantry", "Lancer", "Marksman")
STATS = ("Attack", "Defense", "Lethality", "Health")
CASUALTY_KEYS = ("losses", "injured", "lightly_injured", "survivors")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_side(tag, side, errors, warnings):
    for k in SIDE_REQUIRED:
        if k not in side:
            errors.append(f"{tag}: missing required key '{k}'")
    # casualty identity: troops == losses + injured + lightly_injured + survivors
    if all(_num(side.get(k)) for k in ("troops",) + tuple(CASUALTY_KEYS)):
        total = sum(side[k] for k in CASUALTY_KEYS)
        if abs(total - side["troops"]) > 0.5:
            errors.append(f"{tag}: casualty identity fails - troops={side['troops']} "
                          f"but losses+injured+lightly+survivors={total}")
    # stats: full 3x4 grid, flat beast panel, or an explicit missing declaration
    sp = side.get("stats_pct")
    flat = side.get("stats_pct_FLAT")
    cap = side.get("stats_capture") or {}
    if isinstance(sp, dict):
        for c in CLASSES:
            row = sp.get(c)
            if not isinstance(row, dict):
                # partial-class panels are fine for controlled fights ONLY if declared
                if cap.get("notes") in (None, ""):
                    warnings.append(f"{tag}: stats_pct missing class '{c}' with no stats_capture note")
                continue
            for s in STATS:
                if s not in row:
                    if cap.get("lethality_health") == "missing" and s in ("Lethality", "Health"):
                        continue
                    errors.append(f"{tag}: stats_pct[{c}] missing '{s}' and not declared missing")
                elif not _num(row[s]):
                    errors.append(f"{tag}: stats_pct[{c}][{s}] is not a number")
                elif isinstance(row.get(s), (int, float)) and 0 < row[s] < 10:
                    warnings.append(f"{tag}: stats_pct[{c}][{s}]={row[s]} looks like a "
                                    f"fraction, not a displayed percent (expect e.g. 176.2)")
    elif flat is None:
        if cap.get("attack_defense") != "missing":
            errors.append(f"{tag}: no stats_pct/stats_pct_FLAT and stats_capture does not declare it missing")
    # per_unit / participants row sums
    pu = side.get("per_unit")
    if isinstance(pu, dict):
        for field, side_key in (("kills", "kills"), ("losses", "losses"), ("survivors", "survivors")):
            if _num(side.get(side_key)):
                s = sum(u.get(field, 0) or 0 for u in pu.values())
                if abs(s - side[side_key]) > 0.5:
                    errors.append(f"{tag}: per_unit {field} sum {s} != side {side_key} {side[side_key]}")
    parts = side.get("participants")
    if isinstance(parts, list) and parts and _num(side.get("troops")):
        s = sum(p.get("troops", 0) or 0 for p in parts)
        if s and abs(s - side["troops"]) > 0.5:
            warnings.append(f"{tag}: participants troops sum {s} != side troops {side['troops']}")


def check(path):
    errors, warnings = [], []
    try:
        doc = json.loads(open(path, encoding="utf-8").read())
    except Exception as e:
        return [f"unreadable JSON: {e}"], []
    if doc.get("schema_version") != 2:
        errors.append(f"schema_version must be 2, got {doc.get('schema_version')!r}")
    for k in TOP_KEYS:
        if k not in doc:
            errors.append(f"missing top-level key '{k}'")
    if doc.get("type") not in (1, 2):
        errors.append(f"'type' must be 1 or 2, got {doc.get('type')!r}")
    out = doc.get("outcome")
    if not (isinstance(out, dict) and out.get("winner") in ("attacker", "defender", "mutual")):
        errors.append("outcome.winner must be attacker/defender/mutual")
    defender = doc.get("defender") or doc.get("defender_beast")
    if defender is None:
        errors.append("missing 'defender' (or 'defender_beast')")
    att = doc.get("attacker")
    if isinstance(att, dict):
        check_side("attacker", att, errors, warnings)
    if isinstance(defender, dict):
        check_side("defender", defender, errors, warnings)
    # cross-side kills identity (warning-level): kills == opponent losses+injured
    if isinstance(att, dict) and isinstance(defender, dict):
        for a, b, an, bn in ((att, defender, "attacker", "defender"),
                             (defender, att, "defender", "attacker")):
            if _num(a.get("kills")) and _num(b.get("losses")) and _num(b.get("injured")):
                expect = b["losses"] + b["injured"]
                if abs(a["kills"] - expect) > 0.5:
                    warnings.append(f"{an}.kills={a['kills']} != {bn}.losses+injured={expect} "
                                    f"(held on all controlled reports so far - check OCR)")
    # turn inference consistency
    ti = doc.get("turn_inference")
    if isinstance(ti, dict):
        t, rng = ti.get("turns"), ti.get("turns_range")
        if _num(t) and isinstance(rng, list) and len(rng) == 2:
            if not (rng[0] - 0.5 <= t <= rng[1] + 0.5):
                errors.append(f"turn_inference.turns={t} outside turns_range={rng}")
        if ti.get("method") == "vulcanus_proc_count" and _num(ti.get("trigger_count")):
            # Phase-3 cadence (corrected 2026-07-18): S3 fires turns 3,6,9,...
            # so k triggers => [3k, 3k+2] (k=0 => [1,2]). The recorded range may
            # be NARROWER when an S2 constraint was intersected -- only warn if
            # it falls OUTSIDE the S3 window.
            k = ti["trigger_count"]
            want = [3 * k, 3 * k + 2] if k >= 1 else [1, 2]
            if isinstance(rng, list) and len(rng) == 2 and \
                    (rng[0] < want[0] or rng[1] > want[1]):
                warnings.append(f"turn_inference.turns_range={rng} outside the "
                                f"S3 phase-3 window {want} for k={k}")
    # validation block honesty
    v = doc.get("_validation")
    if isinstance(v, dict):
        if errors and v.get("arithmetic_checks") == "pass":
            warnings.append("_validation.arithmetic_checks says 'pass' but validator found errors")
    return errors, warnings


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    any_err = False
    for path in argv:
        errors, warnings = check(path)
        status = "FAIL" if errors else "PASS"
        print(f"[{status}] {path}")
        for e in errors:
            print(f"  ERROR:   {e}")
        for w in warnings:
            print(f"  WARNING: {w}")
        any_err = any_err or bool(errors)
    return 1 if any_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
