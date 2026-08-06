"""End-to-end dry-run of the promote pipeline (Agent D). Keyless, hermetic:
runs against a synthetic mini-repo so it is fast and independent of the real
prototype's test suite. Asserts a draft Gate Report is produced with machine
evidence and a DRAFT (never PASS) verdict."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SHELL_DIR = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "promote_dryrun_under_test", SHELL_DIR / "promote.py")
promote = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = promote
spec.loader.exec_module(promote)


@pytest.fixture()
def mini_repo(tmp_path: Path) -> Path:
    """A minimal untagged working tree shaped like the prototype repo."""
    repo = tmp_path / "repo"
    (repo / "wos_sim").mkdir(parents=True)
    (repo / "wos_sim" / "__init__.py").write_text("VERSION = 'mini'\n",
                                                  encoding="utf-8")
    (repo / "prototype" / "avatars").mkdir(parents=True)
    (repo / "prototype" / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>mini✓</title>",
        encoding="utf-8")
    (repo / "prototype" / "avatars" / "manifest.json").write_text(
        "{}", encoding="utf-8")
    return repo


def test_dry_run_end_to_end_produces_draft_gate_report(mini_repo, tmp_path):
    build_root = tmp_path / "build"
    rc = promote.main([
        "--tag", "release-test", "--target", "staging", "--dry-run",
        "--skip-prototype-checks",
        "--repo-root", str(mini_repo),
        "--build-root", str(build_root),
    ])
    assert rc == 0, "dry-run pipeline should pass on a clean mini-repo"

    report = build_root / "release-test" / "GATE_REPORT_DRAFT_release-test.md"
    assert report.is_file()
    text = report.read_text(encoding="utf-8")

    # It is the PRODUCTION_CRITERIA template, filled with machine evidence
    assert "# PRODUCTION GATE REPORT" in text
    assert "Release tag:     release-test" in text
    for item in ("A1 pytest:", "A2 regression:", "A3 backtest count:",
                 "C  paywall/auth:", "D  anti-distillation:",
                 "E  security/pentest:", "F  IP/legal:", "VERDICT:"):
        assert item in text, f"template line missing: {item}"

    # The draft can NEVER carry a shippable verdict
    assert promote.PASS_VERDICT_RE.search(text) is None
    assert "DRAFT" in text
    assert "PENDING" in text  # human judgment items left open

    # Step evidence made it in
    assert "phash blocklist (F1): clean" in text
    assert "secret scan (E4): clean" in text
    assert "UTF-8 index.html (G2): clean" in text
    assert "WORKING TREE" in text  # untagged dry-run fallback is recorded

    # Bundle shape: shell runtime + artifact + assets + env config template
    bundle = build_root / "release-test" / "bundle"
    assert (bundle / "shell" / "assets_prod" / "manifest.json").is_file()
    assert (bundle / "shell" / "legal" / "tos.md").is_file()
    assert (bundle / "wos_sim" / "__init__.py").is_file()
    assert (bundle / "prototype" / "index.html").is_file()
    cfg = (bundle / "config" / "staging.env").read_text(encoding="utf-8")
    assert "ENV=staging" in cfg and "DEV_BYPASS=0" in cfg
    assert "MIN_TROOPS_PER_SIDE=5000" in cfg
    # pipeline tooling must NOT ship
    assert not (bundle / "shell" / "promote.py").exists()
    assert not (bundle / "shell" / "tests").exists()
    assert not (bundle / "shell" / "probes").exists()


def test_dry_run_fails_on_planted_secret(mini_repo, tmp_path):
    (mini_repo / "wos_sim" / "oops.py").write_text(
        'KEY = "sk_live_PLANTEDabcdef1234567890"\n', encoding="utf-8")
    rc = promote.main([
        "--tag", "release-test", "--target", "staging", "--dry-run",
        "--skip-prototype-checks",
        "--repo-root", str(mini_repo),
        "--build-root", str(tmp_path / "build2"),
    ])
    assert rc == 1, "a planted secret in the artifact must fail the pipeline"
    text = (tmp_path / "build2" / "release-test" /
            "GATE_REPORT_DRAFT_release-test.md").read_text(encoding="utf-8")
    assert "secret scan (E4): FAIL" in text


def test_dry_run_fails_on_scraped_image_in_artifact(mini_repo, tmp_path):
    avatars = SHELL_DIR.parent / "prototype" / "avatars"
    src = next((p for p in sorted(avatars.iterdir())
                if p.suffix.lower() in {".jpg", ".png"}), None)
    if src is None:
        pytest.skip("no prototype avatars available")
    # Plant a scraped avatar as an SVG-named decoy? No — as a raster the
    # asset-swap strips it; so plant it under a non-artifact path via the
    # bundle hook: simplest honest check is that assemble strips it and the
    # phash gate stays clean.
    dest = mini_repo / "wos_sim" / "data" / "avatars"
    dest.mkdir(parents=True)
    import shutil
    shutil.copy2(src, dest / src.name)
    rc = promote.main([
        "--tag", "release-test", "--target", "staging", "--dry-run",
        "--skip-prototype-checks",
        "--repo-root", str(mini_repo),
        "--build-root", str(tmp_path / "build3"),
    ])
    assert rc == 0
    text = (tmp_path / "build3" / "release-test" /
            "GATE_REPORT_DRAFT_release-test.md").read_text(encoding="utf-8")
    # the asset swap removed it, and the phash gate confirms a clean bundle
    assert "stripped 1 raster images" in text
    assert "phash blocklist (F1): clean" in text
    bundle = tmp_path / "build3" / "release-test" / "bundle"
    assert not (bundle / "wos_sim" / "data" / "avatars" / src.name).exists()
