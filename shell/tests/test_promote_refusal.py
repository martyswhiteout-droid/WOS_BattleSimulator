"""Tests for promote.py's production door (Agent D).

The HARD RULE: --target prod refuses (exit 3) unless a completed gate report
contains 'VERDICT: PASS' AND --martin-signoff "yes-I-approve" is given.
CONDITIONAL is a polite FAIL; promote.py's own draft can never open the door.
(PRODUCTION_CRITERIA gatekeeper rule; COMPASS invariant 4.)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SHELL_DIR = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "promote_refusal_under_test", SHELL_DIR / "promote.py")
promote = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = promote
spec.loader.exec_module(promote)


def _report(tmp_path: Path, verdict: str) -> Path:
    p = tmp_path / "gate_report.md"
    p.write_text(
        "# PRODUCTION GATE REPORT\nQA agent: independent-qa-1\n"
        f"VERDICT: {verdict}\nRationale: test\n", encoding="utf-8")
    return p


def test_prod_refused_with_no_flags():
    assert promote.main(["--tag", "release-x", "--target", "prod"]) == 3


def test_prod_refused_without_signoff(tmp_path):
    rep = _report(tmp_path, "PASS")
    assert promote.main(["--tag", "release-x", "--target", "prod",
                         "--gate-report", str(rep)]) == 3


def test_prod_refused_with_wrong_signoff_phrase(tmp_path):
    rep = _report(tmp_path, "PASS")
    assert promote.main(["--tag", "release-x", "--target", "prod",
                         "--gate-report", str(rep),
                         "--martin-signoff", "yes"]) == 3
    assert promote.main(["--tag", "release-x", "--target", "prod",
                         "--gate-report", str(rep),
                         "--martin-signoff", "YES-I-APPROVE"]) == 3


@pytest.mark.parametrize("verdict", ["CONDITIONAL", "FAIL",
                                     "PASS pending fixes"])
def test_prod_refused_on_non_pass_verdicts(tmp_path, verdict):
    rep = _report(tmp_path, verdict)
    assert promote.main(["--tag", "release-x", "--target", "prod",
                         "--gate-report", str(rep),
                         "--martin-signoff", "yes-I-approve"]) == 3


def test_prod_refused_on_missing_report_file(tmp_path):
    assert promote.main(["--tag", "release-x", "--target", "prod",
                         "--gate-report", str(tmp_path / "nope.md"),
                         "--martin-signoff", "yes-I-approve"]) == 3


def test_own_draft_report_never_opens_the_door(tmp_path):
    """The draft promote.py emits has a DRAFT verdict — it must not satisfy
    the PASS regex."""
    assert not promote.PASS_VERDICT_RE.search(
        f"VERDICT: {promote.DRAFT_VERDICT}")
    with pytest.raises(promote.PromoteRefusal):
        rep = tmp_path / "draft.md"
        rep.write_text(f"VERDICT: {promote.DRAFT_VERDICT}\n", encoding="utf-8")
        promote.enforce_prod_gate("prod", rep, "yes-I-approve")


def test_prod_gate_opens_only_with_pass_and_exact_phrase(tmp_path):
    rep = _report(tmp_path, "PASS")
    # exact phrase + PASS -> the gate function does not raise
    promote.enforce_prod_gate("prod", rep, "yes-I-approve")
    # staging never needs the flags
    promote.enforce_prod_gate("staging", None, None)


def test_prod_refuses_skipping_prototype_checks(tmp_path):
    """Even with the door formally open, A1–A3 may not be skipped for prod."""
    rep = _report(tmp_path, "PASS")
    assert promote.main(["--tag", "release-x", "--target", "prod",
                         "--gate-report", str(rep),
                         "--martin-signoff", "yes-I-approve",
                         "--skip-prototype-checks"]) == 3
