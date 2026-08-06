"""Tests for shell/tools/phash_blocklist.py (Agent D).

Keyless; needs pillow + imagehash. Verifies the F1 gate mechanics:
a copied (and a recompressed/resized) prototype avatar is caught, original
art (SVG or freshly drawn raster) passes, and the CLI exit codes hold.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

SHELL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SHELL_DIR.parent
BLOCKLIST = SHELL_DIR / "tools" / "blocklist.json"
AVATAR_DIR = REPO_ROOT / "prototype" / "avatars"

spec = importlib.util.spec_from_file_location(
    "phash_blocklist_under_test", SHELL_DIR / "tools" / "phash_blocklist.py")
pb = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pb
spec.loader.exec_module(pb)


def _an_avatar() -> Path:
    for p in sorted(AVATAR_DIR.iterdir()):
        if p.suffix.lower() in {".jpg", ".png"}:
            return p
    pytest.skip("no prototype avatars available")


@pytest.fixture()
def bundle(tmp_path: Path) -> Path:
    d = tmp_path / "bundle"
    d.mkdir()
    return d


def test_blocklist_exists_and_covers_prototype_art():
    assert BLOCKLIST.is_file(), "run: python shell/tools/phash_blocklist.py build ..."
    data = json.loads(BLOCKLIST.read_text(encoding="utf-8"))
    assert data["algorithm"] == "phash"
    assert data["image_count"] == len(data["entries"]) >= 250, \
        "blocklist should cover the full scraped-art corpus"


def test_exact_copy_of_prototype_avatar_is_caught(bundle):
    shutil.copy2(_an_avatar(), bundle / "sneaky.jpg")
    res = pb.scan_bundle(bundle, BLOCKLIST)
    assert res["violations"], "exact copy of a scraped avatar must be flagged"
    assert res["violations"][0]["distance"] == 0


def test_recompressed_resized_copy_is_caught(bundle):
    from PIL import Image
    with Image.open(_an_avatar()) as im:
        im.convert("RGB").resize((96, 96)).save(bundle / "resized.png")
    res = pb.scan_bundle(bundle, BLOCKLIST)
    assert res["violations"], \
        "resized/recompressed scraped art must still be within distance 6"


def test_original_svg_and_original_raster_pass(bundle):
    # original SVG (vector): skipped by design, never a violation
    shutil.copy2(SHELL_DIR / "assets_prod" / "class_infantry.svg",
                 bundle / "class_infantry.svg")
    # original raster drawn from scratch: far from any scraped hash
    from PIL import Image
    im = Image.new("RGB", (128, 128))
    px = im.load()
    for x in range(128):
        for y in range(128):
            px[x, y] = (x * 2 % 256, y * 2 % 256, (x ^ y) % 256)
    im.save(bundle / "original.png")
    res = pb.scan_bundle(bundle, BLOCKLIST)
    assert res["violations"] == []
    assert res["scanned"] == 1  # the SVG was skipped, only the PNG hashed


def test_cli_exit_codes(bundle, tmp_path):
    shutil.copy2(_an_avatar(), bundle / "copy.jpg")
    assert pb.main(["scan", "--bundle", str(bundle),
                    "--blocklist", str(BLOCKLIST)]) == 2
    clean = tmp_path / "clean"
    clean.mkdir()
    assert pb.main(["scan", "--bundle", str(clean),
                    "--blocklist", str(BLOCKLIST)]) == 0


def test_build_mode(tmp_path):
    src = tmp_path / "root"
    src.mkdir()
    shutil.copy2(_an_avatar(), src / "a.jpg")
    out = tmp_path / "bl.json"
    data = pb.build_blocklist([src], out)
    assert out.is_file() and data["image_count"] == 1
    # and a copy of that image is then caught by the fresh blocklist
    bundle = tmp_path / "b"
    bundle.mkdir()
    shutil.copy2(_an_avatar(), bundle / "b.jpg")
    assert pb.scan_bundle(bundle, out)["violations"]
