#!/usr/bin/env python3
"""
corpus.py — loader + query API + CLI for the canonical Type-1 WoS battle corpus.

Read-only: this module never touches the source battle reports, only the
generated TYPE1_CORPUS.json produced by build_corpus.py in this same directory.

API:
    load(path=None) -> list[dict]
        Load all rows. Defaults to TYPE1_CORPUS.json next to this file.

    find(rows, dealer_cls=None, target_cls=None, dealer_tier=None, target_tier=None,
         folder=None, determinism=None, winner_side=None, mixed=None, text=None) -> list[dict]
        Filter rows. "dealer" = the WINNER side's first class; "target" = the
        LOSER side's first class (matches the task's definition literally).

    coverage(rows) -> dict
        {"matchup": {(dealer_cls, target_cls): n}, "same_class_infantry_tier_pairs": {(wt, lt): n},
         "determinism": {name: n}, "folder": {name: n}}

CLI:
    py corpus.py --dealer Infantry --target Marksman --det clean
    py corpus.py --coverage
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PATH = HERE / "TYPE1_CORPUS.json"


def load(path=None) -> list:
    p = Path(path) if path else DEFAULT_PATH
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "rows" in data:
        return data["rows"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unrecognized corpus file shape at {p}")


def _first_class(row: dict, side: str):
    classes = (row.get(side) or {}).get("classes") or []
    return classes[0] if classes else None


def _dealer_target_sides(row: dict):
    """dealer = winner's side name, target = loser's side name. Falls back to
    attacker/defender (in that order) when the winner isn't recorded, so rows
    with an unresolved winner are still queryable rather than silently dropped."""
    winner = (row.get("outcome") or {}).get("winner")
    if winner == "attacker":
        return "attacker", "defender"
    if winner == "defender":
        return "defender", "attacker"
    return "attacker", "defender"


def find(rows, dealer_cls=None, target_cls=None, dealer_tier=None, target_tier=None,
         folder=None, determinism=None, winner_side=None, mixed=None, text=None) -> list:
    out = []
    for r in rows:
        dealer_side, target_side = _dealer_target_sides(r)
        dealer = _first_class(r, dealer_side)
        target = _first_class(r, target_side)

        if dealer_cls and not (dealer and dealer.get("cls") == dealer_cls):
            continue
        if target_cls and not (target and target.get("cls") == target_cls):
            continue
        if dealer_tier is not None and not (dealer and dealer.get("tier") == dealer_tier):
            continue
        if target_tier is not None and not (target and target.get("tier") == target_tier):
            continue
        if folder and r.get("folder") != folder:
            continue
        if determinism and r.get("determinism") != determinism:
            continue
        if winner_side and (r.get("outcome") or {}).get("winner") != winner_side:
            continue
        if mixed is not None:
            is_mixed = (
                len((r.get("attacker") or {}).get("classes") or []) > 1
                or len((r.get("defender") or {}).get("classes") or []) > 1
            )
            if bool(mixed) != is_mixed:
                continue
        if text:
            hay = " ".join(
                [
                    r.get("id", "") or "",
                    r.get("notes_excerpt", "") or "",
                    json.dumps(r.get("attacker", {})),
                    json.dumps(r.get("defender", {})),
                ]
            ).lower()
            if text.lower() not in hay:
                continue
        out.append(r)
    return out


def coverage(rows) -> dict:
    matchup = Counter()
    tier_pairs = Counter()
    determinism_counts = Counter()
    folder_counts = Counter()
    for r in rows:
        folder_counts[r.get("folder")] += 1
        determinism_counts[r.get("determinism")] += 1

        dealer_side, target_side = _dealer_target_sides(r)
        winner = (r.get("outcome") or {}).get("winner")
        if winner not in ("attacker", "defender"):
            continue
        dealer = _first_class(r, dealer_side)
        target = _first_class(r, target_side)
        if dealer and target and dealer.get("cls") and target.get("cls"):
            matchup[(dealer["cls"], target["cls"])] += 1
            if dealer["cls"] == "Infantry" and target["cls"] == "Infantry":
                if dealer.get("tier") is not None and target.get("tier") is not None:
                    tier_pairs[(dealer["tier"], target["tier"])] += 1
    return {
        "matchup": dict(matchup),
        "same_class_infantry_tier_pairs": dict(tier_pairs),
        "determinism": dict(determinism_counts),
        "folder": dict(folder_counts),
    }


def _label_classes(classes):
    if not classes:
        return "?"
    parts = []
    for c in classes:
        fc = f"FC{c['fc']}" if c.get("fc") else ""
        parts.append(f"{c.get('count')}x{fc}T{c.get('tier')}{c.get('cls')}")
    return "+".join(parts)


def _print_table(rows):
    header = f"{'id':<74} {'matchup':<28} {'winner':<9} {'turns':<7} {'determinism':<22} flags"
    print(header)
    print("-" * len(header))
    for r in rows:
        att = _label_classes((r.get("attacker") or {}).get("classes"))
        deff = _label_classes((r.get("defender") or {}).get("classes"))
        matchup = f"{att} v {deff}"
        winner = (r.get("outcome") or {}).get("winner")
        turns = (r.get("outcome") or {}).get("turns")
        rid = r.get("id", "")
        print(f"{rid[:74]:<74} {matchup[:28]:<28} {str(winner):<9} {str(turns):<7} "
              f"{r.get('determinism', ''):<22} {','.join(r.get('flags') or [])}")


def _print_coverage(rows):
    cov = coverage(rows)
    print(f"Total rows: {len(rows)}")
    print()
    print("By folder:")
    for k, v in sorted(cov["folder"].items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"  {str(k):<32} {v}")
    print()
    print("By determinism:")
    for k, v in sorted(cov["determinism"].items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"  {str(k):<24} {v}")
    print()
    print("Matchup (winner-class -> loser-class):")
    for (a, b), v in sorted(cov["matchup"].items(), key=lambda kv: -kv[1]):
        print(f"  {a:<10} -> {b:<12} {v}")
    print()
    print("Same-class Infantry mirrors (winner-tier -> loser-tier):")
    for (a, b), v in sorted(cov["same_class_infantry_tier_pairs"].items(), key=lambda kv: str(kv[0])):
        print(f"  T{a} -> T{b:<4} {v}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Query the canonical Type-1 WoS battle corpus.")
    ap.add_argument("--path", default=None, help="path to TYPE1_CORPUS.json (default: alongside this file)")
    ap.add_argument("--dealer", default=None, help="winner's troop class, e.g. Infantry")
    ap.add_argument("--target", default=None, help="loser's troop class, e.g. Marksman")
    ap.add_argument("--dealer-tier", type=int, default=None)
    ap.add_argument("--target-tier", type=int, default=None)
    ap.add_argument("--folder", default=None)
    ap.add_argument("--det", default=None, help="determinism class: clean|vulcanus_deterministic|"
                                                  "gordon_deterministic|proc_or_unknown|legacy_unverified")
    ap.add_argument("--winner", default=None, help="attacker|defender")
    ap.add_argument("--mixed", default=None, help="1/true to require multi-class sides, 0/false to exclude")
    ap.add_argument("--text", default=None, help="free-text substring search")
    ap.add_argument("--coverage", action="store_true", help="print coverage matrices instead of a row table")
    args = ap.parse_args(argv)

    rows = load(args.path)

    if args.coverage:
        _print_coverage(rows)
        return

    mixed = None
    if args.mixed is not None:
        mixed = args.mixed.lower() in ("1", "true", "yes", "y")

    filtered = find(
        rows,
        dealer_cls=args.dealer,
        target_cls=args.target,
        dealer_tier=args.dealer_tier,
        target_tier=args.target_tier,
        folder=args.folder,
        determinism=args.det,
        winner_side=args.winner,
        mixed=mixed,
        text=args.text,
    )
    print(f"{len(filtered)} matching rows (of {len(rows)} total)")
    _print_table(filtered)


if __name__ == "__main__":
    main()
