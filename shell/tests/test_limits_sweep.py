"""Tests for request fingerprinting + sweep_scan (Agent B; PRODUCTION_CRITERIA D3).

The fingerprint is sha256 of the normalized body (sorted keys, troop values
rounded to nearest 100). sweep_scan(day) flags accounts with >= 20
near-identical queries differing in at most one field, writing dedup'd
flags to audit_log.
"""

import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from shell.app import db, limits

run = asyncio.run

ENV_KEYS = [
    "DATABASE_URL", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "DEV_BYPASS",
    "ENV", "MIN_TROOPS_PER_SIDE", "FREE_SIMS_PER_DAY", "PRO_SIMS_PER_DAY",
    "PRO_OCR_PER_DAY", "BURST_PER_MIN", "SWEEP_MIN_EVENTS", "IP_HASH_SALT",
    "BASE_URL", "GLOBAL_CONCURRENCY", "STRIPE_PRICE_ID_PRO",
    "CLERK_SECRET_KEY", "CLERK_PUBLISHABLE_KEY", "CLERK_JWKS_URL",
]


@pytest.fixture(autouse=True)
def keyless_env(monkeypatch):
    for var in ENV_KEYS:
        monkeypatch.delenv(var, raising=False)
    db.reset_db()
    yield
    db.reset_db()


# ---------------------------------------------------------------------------
# Fingerprint normalization
# ---------------------------------------------------------------------------

def test_fingerprint_key_order_invariant():
    fp1, _ = limits.compute_fingerprint({"a": 1, "b": {"y": 2, "x": 3}})
    fp2, _ = limits.compute_fingerprint({"b": {"x": 3, "y": 2}, "a": 1})
    assert fp1 == fp2


def test_troops_rounded_to_nearest_100_half_up():
    base = {"own": {"troops_total": 5000}, "enemy": {"troops_total": 60000}}
    same_bucket = {"own": {"troops_total": 5049}, "enemy": {"troops_total": 60000}}
    next_bucket = {"own": {"troops_total": 5050}, "enemy": {"troops_total": 60000}}
    fp_base, _ = limits.compute_fingerprint(base)
    assert limits.compute_fingerprint(same_bucket)[0] == fp_base
    assert limits.compute_fingerprint(next_bucket)[0] != fp_base


def test_non_troop_numbers_not_rounded():
    fp1, _ = limits.compute_fingerprint({"hero_level": 41})
    fp2, _ = limits.compute_fingerprint({"hero_level": 42})
    assert fp1 != fp2


def test_fp_fields_flattens_leaf_paths():
    _, fields = limits.compute_fingerprint(
        {"own": {"troops_total": 50000, "hero": "Molly"}}
    )
    assert set(fields) == {"own.troops_total", "own.hero"}


# ---------------------------------------------------------------------------
# sweep_scan
# ---------------------------------------------------------------------------

def _record_sweep(user_id: str, n: int, step: int = 1000, ip="ipS"):
    """n requests identical except own.troops_total stepped by `step`."""
    for i in range(n):
        body = {
            "own": {"troops_total": 50000 + i * step, "hero": "Molly"},
            "enemy": {"troops_total": 60000, "hero": "Alonso"},
        }
        fp, fields = limits.compute_fingerprint(body)
        run(
            db.record_usage(
                user_id,
                endpoint="/api/predict",
                kind="sim",
                ip_hash=ip,
                request_fingerprint=fp,
                fp_fields=fields,
                troops_own=50000 + i * step,
                troops_enemy=60000,
            )
        )


def test_sweep_scan_flags_single_field_parameter_sweep():
    _record_sweep("sweeper", 25, step=1000)
    flags = run(limits.sweep_scan())
    mine = [f for f in flags if f["user_id"] == "sweeper"]
    assert mine, "sweep account not flagged"
    assert mine[0]["pattern"] == "one_field"
    assert mine[0]["field"] == "own.troops_total"
    assert mine[0]["count"] == 25
    entries = run(db.get_audit_entries("sweep_flag", "sweeper"))
    assert len(entries) == 1


def test_sweep_scan_flags_identical_hammering():
    body = {"own": {"troops_total": 50000}, "enemy": {"troops_total": 60000}}
    fp, fields = limits.compute_fingerprint(body)
    for _ in range(22):
        run(
            db.record_usage(
                "hammer", endpoint="/api/predict", kind="sim",
                request_fingerprint=fp, fp_fields=fields,
                troops_own=50000, troops_enemy=60000,
            )
        )
    flags = run(limits.sweep_scan())
    mine = [f for f in flags if f["user_id"] == "hammer" and f["pattern"] == "identical"]
    assert mine and mine[0]["count"] == 22


def test_micro_stepped_sweep_collapses_via_rounding_and_is_flagged():
    # steps of 1 troop all round to the same 100-bucket -> identical pattern
    _record_sweep("micro", 25, step=1)
    flags = run(limits.sweep_scan())
    assert any(f["user_id"] == "micro" and f["pattern"] == "identical" for f in flags)


def test_sweep_scan_ignores_normal_varied_usage():
    for i in range(25):
        body = {
            "own": {"troops_total": 50000 + i * 1000, "hero": f"hero_{i}"},
            "enemy": {"troops_total": 60000 + i * 500, "hero": "Alonso"},
        }
        fp, fields = limits.compute_fingerprint(body)
        run(
            db.record_usage(
                "normal_user", endpoint="/api/predict", kind="sim",
                request_fingerprint=fp, fp_fields=fields,
            )
        )
    flags = run(limits.sweep_scan())
    assert not [f for f in flags if f["user_id"] == "normal_user"]


def test_sweep_scan_below_threshold_not_flagged():
    _record_sweep("light_user", 19, step=1000)  # threshold is 20
    flags = run(limits.sweep_scan())
    assert not [f for f in flags if f["user_id"] == "light_user"]


def test_sweep_scan_rerun_does_not_duplicate_audit_entries():
    _record_sweep("sweeper2", 25, step=1000)
    run(limits.sweep_scan())
    run(limits.sweep_scan())  # nightly job re-run must be idempotent
    entries = run(db.get_audit_entries("sweep_flag", "sweeper2"))
    assert len(entries) == 1


def test_end_to_end_fingerprints_from_check_and_record_feed_sweep(monkeypatch):
    # go through the real check_and_record path (pro user, backdated to
    # dodge burst): fingerprints recorded there must be sweep-scannable
    monkeypatch.setenv("PRO_SIMS_PER_DAY", "1000")
    monkeypatch.setenv("BURST_PER_MIN", "1000")
    db.reset_db()
    from shell.app.billing._contracts import UserCtx

    pro = UserCtx(user_id="e2e_sweeper", email=None, plan="pro")
    for i in range(21):
        body = {
            "own": {"troops_total": 50000 + i * 1000},
            "enemy": {"troops_total": 60000},
        }
        verdict = run(limits.check_and_record(pro, "/api/predict", body, "ipX"))
        assert isinstance(verdict, limits.Allowed)
    flags = run(limits.sweep_scan())
    assert any(
        f["user_id"] == "e2e_sweeper" and f["pattern"] == "one_field" for f in flags
    )
