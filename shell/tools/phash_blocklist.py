"""shell/tools/phash_blocklist.py — perceptual-hash blocklist builder + scanner.

Implements PRODUCTION_PLAN.md §2.5 ("perceptual-hash blocklist of known scraped
images — build FAILS if any blocklisted image is in the bundle") and feeds
promote.py step 5 (static gates) / PRODUCTION_CRITERIA.md item F1.

Two modes:

  build  — walk the prototype's scraped-image directories (hero avatars, skill
           icons), compute a perceptual hash (pHash, 64-bit) for every raster
           image, and write them to a blocklist JSON. The prototype dirs are
           READ-ONLY inputs (ARCHITECTURE.md boundary rule 1).

  scan   — walk a candidate release bundle; if ANY raster image in the bundle
           is within Hamming distance <= --max-distance (default 6) of a
           blocklisted hash, print the violations and exit 2 (gate FAIL).

Exit codes: 0 = clean · 2 = blocklisted image found · 1 = usage/config error.

Notes:
  * SVG (and other vector/code) files are skipped by design: they cannot be
    perceptually hashed and our production art (shell/assets_prod/) is
    original code-drawn SVG. The blocklist targets raster COPIES of Century
    Games artwork leaking into a bundle.
  * Unreadable/corrupt raster files are reported as warnings, not violations.
  * pHash at 64 bits with threshold 6 catches recompression, mild rescale and
    format conversion of the same artwork while keeping false positives on
    unrelated originals essentially nil.

Usage (repo root):
  python shell/tools/phash_blocklist.py build \
      --roots prototype/avatars prototype/assets \
      --out shell/tools/blocklist.json
  python shell/tools/phash_blocklist.py scan \
      --bundle <bundle_dir> --blocklist shell/tools/blocklist.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

RASTER_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
SKIP_EXTS = {".svg"}  # vector originals — not hashable, not blocklistable
DEFAULT_MAX_DISTANCE = 6
HASH_ALGORITHM = "phash"  # imagehash.phash, hash_size=8 -> 64-bit
BLOCKLIST_VERSION = 1


def _require_imagehash():
    try:
        import imagehash  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as e:  # pragma: no cover
        print(f"ERROR: pillow + imagehash are required ({e}). "
              "pip install pillow imagehash", file=sys.stderr)
        raise SystemExit(1)


def compute_phash(path: Path):
    """64-bit perceptual hash of a raster image, or None if unreadable."""
    import imagehash
    from PIL import Image
    try:
        with Image.open(path) as im:
            return imagehash.phash(im.convert("RGB"))
    except Exception:
        return None


def iter_raster_files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in RASTER_EXTS:
            yield p


def build_blocklist(roots: list[Path], out_path: Path) -> dict:
    """Hash every raster image under `roots` (read-only) into a blocklist dict."""
    _require_imagehash()
    entries, unreadable = [], []
    for root in roots:
        if not root.is_dir():
            print(f"WARNING: root not found, skipping: {root}", file=sys.stderr)
            continue
        for p in iter_raster_files(root):
            h = compute_phash(p)
            rel = str(p.relative_to(root.parent)) if root.parent in p.parents else str(p)
            if h is None:
                unreadable.append(rel)
                continue
            entries.append({"hash": str(h), "source": rel.replace("\\", "/")})
    blocklist = {
        "version": BLOCKLIST_VERSION,
        "algorithm": HASH_ALGORITHM,
        "hash_bits": 64,
        "built": date.today().isoformat(),
        "roots": [str(r).replace("\\", "/") for r in roots],
        "image_count": len(entries),
        "unreadable": unreadable,
        "entries": entries,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(blocklist, indent=1), encoding="utf-8")
    print(f"blocklist: {len(entries)} images hashed "
          f"({len(unreadable)} unreadable) -> {out_path}")
    return blocklist


def load_blocklist(path: Path) -> list[tuple[object, str]]:
    import imagehash
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("algorithm") != HASH_ALGORITHM:
        raise ValueError(f"unsupported blocklist algorithm: {data.get('algorithm')}")
    return [(imagehash.hex_to_hash(e["hash"]), e["source"]) for e in data["entries"]]


def scan_bundle(bundle: Path, blocklist_path: Path,
                max_distance: int = DEFAULT_MAX_DISTANCE) -> dict:
    """Scan a bundle dir. Returns {'violations': [...], 'warnings': [...],
    'scanned': n}. A violation = raster image within max_distance of any
    blocklisted hash."""
    _require_imagehash()
    hashes = load_blocklist(blocklist_path)
    violations, warnings, scanned = [], [], 0
    for p in sorted(bundle.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in SKIP_EXTS or ext not in RASTER_EXTS:
            continue
        scanned += 1
        h = compute_phash(p)
        rel = str(p.relative_to(bundle)).replace("\\", "/")
        if h is None:
            warnings.append(f"unreadable raster image (manual review): {rel}")
            continue
        best = min(((h - bh, src) for bh, src in hashes), default=(999, ""))
        if best[0] <= max_distance:
            violations.append({"file": rel, "distance": best[0],
                               "matches": best[1]})
    return {"violations": violations, "warnings": warnings, "scanned": scanned}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)

    b = sub.add_parser("build", help="hash prototype image dirs into a blocklist")
    b.add_argument("--roots", nargs="+", required=True, type=Path)
    b.add_argument("--out", required=True, type=Path)

    s = sub.add_parser("scan", help="fail (exit 2) if bundle contains blocklisted art")
    s.add_argument("--bundle", required=True, type=Path)
    s.add_argument("--blocklist", required=True, type=Path)
    s.add_argument("--max-distance", type=int, default=DEFAULT_MAX_DISTANCE)

    args = ap.parse_args(argv)

    if args.mode == "build":
        build_blocklist(list(args.roots), args.out)
        return 0

    if not args.bundle.is_dir():
        print(f"ERROR: bundle dir not found: {args.bundle}", file=sys.stderr)
        return 1
    if not args.blocklist.is_file():
        print(f"ERROR: blocklist not found: {args.blocklist}", file=sys.stderr)
        return 1
    res = scan_bundle(args.bundle, args.blocklist, args.max_distance)
    for w in res["warnings"]:
        print(f"WARNING: {w}")
    if res["violations"]:
        print(f"FAIL: {len(res['violations'])} blocklisted image(s) in bundle "
              f"(scanned {res['scanned']}):")
        for v in res["violations"]:
            print(f"  {v['file']}  (distance {v['distance']} vs {v['matches']})")
        return 2
    print(f"OK: no blocklisted images ({res['scanned']} raster files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
