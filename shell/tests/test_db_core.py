"""Tests for shell/app/db.py (Agent B) — keyless: exercises the InMemoryDB
fallback selected when DATABASE_URL is absent (ARCHITECTURE.md rule 2), plus
static schema guards on shell/db/migrations/001_init.sql."""

import asyncio
import pathlib
import sys
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from shell.app import db

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
# Backend selection
# ---------------------------------------------------------------------------

def test_keyless_selects_in_memory_backend():
    backend = db.get_db()
    assert isinstance(backend, db.InMemoryDB)
    assert backend.is_postgres is False


def test_get_pool_is_none_in_memory_mode():
    assert run(db.get_pool()) is None


def test_database_url_selects_postgres_backend(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@localhost:5432/wos")
    db.reset_db()
    backend = db.get_db()
    assert isinstance(backend, db.PostgresDB)  # no connection made yet (lazy)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def test_upsert_user_creates_then_updates_email():
    row = run(db.upsert_user("user_1", None))
    assert row["clerk_user_id"] == "user_1" and row["email"] is None
    row = run(db.upsert_user("user_1", "m@example.com"))
    assert row["email"] == "m@example.com"
    # upsert without email must not clobber the stored one
    row = run(db.upsert_user("user_1", None))
    assert row["email"] == "m@example.com"


# ---------------------------------------------------------------------------
# Entitlements (seed: free=5 sims/0 OCR, pro=100 sims/30 OCR, max_runs 1000)
# ---------------------------------------------------------------------------

def test_entitlements_seed_values():
    free = run(db.get_entitlements("free"))
    pro = run(db.get_entitlements("pro"))
    assert (free.daily_sim_quota, free.daily_ocr_quota, free.max_runs) == (5, 0, 1000)
    assert (pro.daily_sim_quota, pro.daily_ocr_quota, pro.max_runs) == (100, 30, 1000)


def test_unknown_plan_falls_back_to_free():
    ent = run(db.get_entitlements("enterprise"))
    assert ent.daily_sim_quota == 5 and ent.daily_ocr_quota == 0


# ---------------------------------------------------------------------------
# usage_events: per-day counters, IP counters, sliding window
# ---------------------------------------------------------------------------

def test_usage_today_counts_only_today_and_kind():
    backend = db.get_db()
    for _ in range(3):
        run(db.record_usage("u1", endpoint="/api/predict", kind="sim", ip_hash="ipA"))
    run(db.record_usage("u1", endpoint="/shell/ocr", kind="ocr", ip_hash="ipA"))
    # yesterday's event must not count
    yesterday = db._utcnow() - timedelta(days=1)
    run(db.record_usage("u1", endpoint="/api/predict", kind="sim", ts=yesterday))
    assert run(db.get_usage_today("u1", "sim")) == 3
    assert run(db.get_usage_today("u1", "ocr")) == 1
    assert run(db.get_usage_today("u2", "sim")) == 0
    assert len(backend.usage_events) == 5


def test_ip_usage_today_aggregates_across_users():
    run(db.record_usage("u1", endpoint="/api/predict", kind="sim", ip_hash="ipZ"))
    run(db.record_usage("u2", endpoint="/api/predict", kind="sim", ip_hash="ipZ"))
    run(db.record_usage("u3", endpoint="/api/predict", kind="sim", ip_hash="other"))
    assert run(db.get_ip_usage_today("ipZ", "sim")) == 2
    assert run(db.get_ip_usage_today("", "sim")) == 0


def test_count_recent_events_sliding_window():
    old = db._utcnow() - timedelta(seconds=120)
    run(db.record_usage("u1", endpoint="/api/predict", kind="sim", ts=old))
    run(db.record_usage("u1", endpoint="/api/predict", kind="sim"))
    run(db.record_usage("u1", endpoint="/api/predict", kind="sim"))
    assert run(db.count_recent_events("u1", 60)) == 2
    assert run(db.count_recent_events("u1", 300)) == 3


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

def test_subscription_lifecycle():
    assert run(db.get_subscription("u1")) is None
    row = run(
        db.apply_subscription_update(
            "u1",
            plan="pro",
            status="active",
            stripe_customer_id="cus_9",
            stripe_subscription_id="sub_9",
        )
    )
    assert row["plan"] == "pro" and row["status"] == "active"
    fetched = run(db.get_subscription("u1"))
    assert fetched["stripe_customer_id"] == "cus_9"
    assert run(db.get_user_by_customer("cus_9")) == "u1"
    assert run(db.get_user_by_customer("cus_nope")) is None
    # downgrade keeps stripe ids (COALESCE semantics)
    run(db.apply_subscription_update("u1", plan="pro", status="canceled"))
    fetched = run(db.get_subscription("u1"))
    assert fetched["status"] == "canceled"
    assert fetched["stripe_customer_id"] == "cus_9"


# ---------------------------------------------------------------------------
# Saved scenarios (schema_version mandatory — PRODUCTION_CRITERIA B1)
# ---------------------------------------------------------------------------

def test_scenario_save_get_list_and_ownership():
    sid = run(db.save_scenario("u1", "rally A", "2", {"own": {"troops_total": 90000}}))
    row = run(db.get_scenario("u1", sid))
    assert row["name"] == "rally A"
    assert row["schema_version"] == "2"
    assert row["payload"]["own"]["troops_total"] == 90000
    # hostile client: another user must not read it
    assert run(db.get_scenario("u2", sid)) is None
    assert [r["id"] for r in run(db.list_scenarios("u1"))] == [sid]
    assert run(db.list_scenarios("u2")) == []


# ---------------------------------------------------------------------------
# OCR jobs
# ---------------------------------------------------------------------------

def test_ocr_job_create_update_and_hash_cache():
    job_id = run(db.create_ocr_job("u1", upload_ref="up_1", image_hash="ph_abc"))
    assert run(db.find_ocr_job_by_hash("ph_abc")) is None  # pending: not cacheable
    run(db.update_ocr_job(job_id, status="ok", extracted={"a": 1}, cost_usd=0.02))
    hit = run(db.find_ocr_job_by_hash("ph_abc"))
    assert hit["id"] == job_id and hit["extracted"] == {"a": 1}


def test_ocr_job_agent_c_one_shot_style():
    # shell/app/ocr/cache.py DbOcrJobs calling convention (keyword one-shot)
    job_id = run(
        db.create_ocr_job(
            image_hash="ph_xyz",
            user_id="u9",
            status="partial",
            result={"status": "partial", "profile": {"x": 1}},
            cost_estimate_usd=0.03,
        )
    )
    rec = run(db.get_ocr_job_by_hash("ph_xyz"))
    assert rec["id"] == job_id
    assert rec["result"] == {"status": "partial", "profile": {"x": 1}}
    assert rec["cost_estimate_usd"] == 0.03
    # failures are cached too (any-status lookup)
    run(db.create_ocr_job(image_hash="ph_bad", user_id="u9",
                          status="failed", result={"status": "failed"},
                          cost_estimate_usd=0.03))
    assert run(db.get_ocr_job_by_hash("ph_bad"))["status"] == "failed"
    assert run(db.find_ocr_job_by_hash("ph_bad")) is None  # ok/partial only


# ---------------------------------------------------------------------------
# Audit log + dedup (idempotency ledger)
# ---------------------------------------------------------------------------

def test_audit_dedup_key_is_write_once():
    assert run(db.audit("stripe_webhook", dedup_key="stripe_evt:evt_1")) is True
    assert run(db.audit("stripe_webhook", dedup_key="stripe_evt:evt_1")) is False
    assert run(db.audit("stripe_webhook", dedup_key="stripe_evt:evt_2")) is True
    assert run(db.audit("note", detail={"k": "v"})) is True  # no key: always writes
    entries = run(db.get_audit_entries("stripe_webhook"))
    assert len(entries) == 2


# ---------------------------------------------------------------------------
# Static schema guards on 001_init.sql (PRODUCTION_PLAN §2.2)
# ---------------------------------------------------------------------------

def _migration_sql() -> str:
    path = ROOT / "shell" / "db" / "migrations" / "001_init.sql"
    return path.read_text(encoding="utf-8")


def test_migration_defines_all_eight_tables():
    sql = _migration_sql()
    for table in [
        "users", "profiles", "subscriptions", "entitlements",
        "usage_events", "ocr_jobs", "saved_scenarios", "audit_log",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql, table


def test_migration_has_required_indexes_rls_and_seeds():
    sql = _migration_sql()
    assert "idx_usage_events_user_ts" in sql
    assert "idx_usage_events_fingerprint" in sql
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 8
    assert "('free', 5,   0,  1000)" in sql
    assert "('pro',  100, 30, 1000)" in sql
    assert "schema_version" in sql  # B1: mandatory on saved_scenarios
    assert "dedup_key   TEXT UNIQUE" in sql  # webhook idempotency ledger
