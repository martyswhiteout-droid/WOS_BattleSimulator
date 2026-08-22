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
    # F1: a synthetic stand-in for .claude/skills/wos-battlereport-ingestion/
    # so the completeness gate (gate_ingestion_skill) sees a complete bundle
    # on this mini-repo, same as a real release must.
    skill = repo / promote.INGESTION_SKILL_DIR
    (skill / "scripts").mkdir(parents=True)
    (skill / "references").mkdir(parents=True)
    (skill / "scripts" / "validate_report.py").write_text(
        "# mini stand-in for the real validator\n", encoding="utf-8")
    (skill / "references" / "schema.md").write_text(
        "# mini stand-in for the real v2 schema\n", encoding="utf-8")
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
    assert "ingestion skill bundle (EVAL F1): clean" in text
    assert "secret scan (E4): clean" in text
    assert "UTF-8 index.html (G2): clean" in text
    assert "WORKING TREE" in text  # untagged dry-run fallback is recorded
    assert "ingestion skill included" in text

    # Step 1's honest status for an untagged dry-run: SKIP, never PASS (F20 —
    # a reviewer skimming the report must not read this as release-grade).
    # ev() renders "{status} — {first evidence line}"; check that directly
    # rather than the report's column spacing.
    assert "SKIP — tag `release-test` not found" in text
    assert "PASS — tag `release-test` not found" not in text

    # Bundle shape: shell runtime + artifact + assets + env config template
    bundle = build_root / "release-test" / "bundle"
    assert (bundle / "shell" / "assets_prod" / "manifest.json").is_file()
    assert (bundle / "shell" / "legal" / "tos.md").is_file()
    assert (bundle / "wos_sim" / "__init__.py").is_file()
    assert (bundle / "prototype" / "index.html").is_file()
    # F1: the ingestion skill ships at the exact path extract.py/vision.py
    # resolve at runtime.
    assert (bundle / promote.INGESTION_SKILL_VALIDATOR_REL).is_file()
    assert (bundle / promote.INGESTION_SKILL_SCHEMA_REL).is_file()
    cfg = (bundle / "config" / "staging.env").read_text(encoding="utf-8")
    assert "ENV=staging" in cfg and "DEV_BYPASS=0" in cfg
    assert "MIN_TROOPS_PER_SIDE=5000" in cfg
    # pipeline tooling must NOT ship
    assert not (bundle / "shell" / "promote.py").exists()
    assert not (bundle / "shell" / "tests").exists()
    assert not (bundle / "shell" / "probes").exists()


def test_dry_run_fails_when_ingestion_skill_is_missing(mini_repo, tmp_path):
    """F1 regression: a release whose tree does not carry the ingestion skill
    must be caught by the gate, not silently shipped to 500 on first OCR
    request (EVAL_ROUND_1.md F1 — reproduced live via a Docker-layout boot)."""
    import shutil as _shutil
    _shutil.rmtree(mini_repo / promote.INGESTION_SKILL_DIR)
    rc = promote.main([
        "--tag", "release-test", "--target", "staging", "--dry-run",
        "--skip-prototype-checks",
        "--repo-root", str(mini_repo),
        "--build-root", str(tmp_path / "build_missing_skill"),
    ])
    assert rc == 1, "a bundle missing the ingestion skill must fail the pipeline"
    text = (tmp_path / "build_missing_skill" / "release-test" /
            "GATE_REPORT_DRAFT_release-test.md").read_text(encoding="utf-8")
    assert "ingestion skill bundle (EVAL F1): FAIL" in text
    assert "missing ingestion-skill validator" in text
    assert "missing ingestion-skill schema doc" in text


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


def test_gate_report_documents_the_tests_exclusion_as_intended(mini_repo, tmp_path):
    """Mn4 (EVAL_ROUND_2.md): shell/tests/ has always been excluded from this
    scp/VPS bundle (see the assertion in
    test_dry_run_end_to_end_produces_draft_gate_report above), but the
    exclusion used to be silent — nothing in the gate report said so, which
    reads exactly like the F20-style "a reviewer skims past something
    load-bearing" failure class this pipeline exists to avoid. step3_assemble's
    own evidence string must now document it explicitly."""
    build_root = tmp_path / "build_mn4"
    rc = promote.main([
        "--tag", "release-test", "--target", "staging", "--dry-run",
        "--skip-prototype-checks",
        "--repo-root", str(mini_repo),
        "--build-root", str(build_root),
    ])
    assert rc == 0
    text = (build_root / "release-test" /
            "GATE_REPORT_DRAFT_release-test.md").read_text(encoding="utf-8")
    assert "shell/tests/ EXCLUDED from this bundle (INTENDED" in text
    assert "Mn4" in text
    assert "Docker" in text   # names the mitigating (primary) deploy path


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
    # the asset swap removed it, and the phash gate confirms a clean bundle.
    # The count also includes the real-game sample captures under
    # shell/app/ocr/client/samples/ (stripped since 2026-08-16, F1) — computed
    # from the real folder so this stays an EXACT assertion, not a >= 1.
    real_samples = SHELL_DIR / "app" / "ocr" / "client" / "samples"
    sample_rasters = [p for p in real_samples.iterdir()
                      if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]         if real_samples.is_dir() else []
    assert f"stripped {1 + len(sample_rasters)} raster images" in text
    assert "phash blocklist (F1): clean" in text
    bundle = tmp_path / "build3" / "release-test" / "bundle"
    assert not (bundle / "wos_sim" / "data" / "avatars" / src.name).exists()


def test_assemble_strips_the_real_screenshot_samples_from_the_bundle(mini_repo, tmp_path):
    # 2026-08-15/16: shell/app/ocr/client/samples/ ships REAL game screenshots
    # as upload guides (owner request). The bundle copies the real shell/ dir,
    # so those captures would have shipped untouched — the strip loop only
    # covered wos_sim/ and prototype/. They are Century Games IP (F1); the
    # client degrades to its hand-drawn mini-panels when they are absent.
    real_samples = SHELL_DIR / "app" / "ocr" / "client" / "samples"
    rasters = [p for p in real_samples.iterdir()
               if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    if not rasters:
        pytest.skip("no real sample captures present in this checkout")
    build_root = tmp_path / "build_samples"
    rc = promote.main([
        "--tag", "release-test", "--target", "staging", "--dry-run",
        "--skip-prototype-checks",
        "--repo-root", str(mini_repo),
        "--build-root", str(build_root),
    ])
    assert rc == 0
    bundled = build_root / "release-test" / "bundle" / "shell" / "app" / "ocr" / "client" / "samples"
    assert bundled.is_dir(), "samples folder itself (README) still ships"
    leaked = [p.name for p in bundled.iterdir()
              if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    assert leaked == [], f"real game screenshots leaked into the bundle: {leaked}"
    text = (build_root / "release-test" /
            "GATE_REPORT_DRAFT_release-test.md").read_text(encoding="utf-8")
    assert f"stripped {len(rasters)} raster images" in text
