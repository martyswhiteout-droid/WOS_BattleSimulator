"""shell/app/db.py — database access layer for the production shell (Agent B).

Implements PRODUCTION_PLAN.md §2.2 (data model: users, profiles,
subscriptions, entitlements, usage_events, ocr_jobs, saved_scenarios,
audit_log) and the db contract in shell/ARCHITECTURE.md:

    get_pool(), record_usage(...), get_entitlements(plan) -> Entitlements
    + upsert_user, get_subscription, apply_subscription_update,
      get_usage_today, scenario save/get, audit helpers.

Backends:
  * PostgresDB  — asyncpg pool against DATABASE_URL (Supabase Postgres,
                  service-role, server-side only; the shell is the ONLY
                  database client).
  * InMemoryDB  — dict-backed, same interface, per-day counters. Selected
                  automatically when DATABASE_URL is absent so every agent's
                  tests run KEYLESS (ARCHITECTURE.md boundary rule 2).

Module-level functions delegate to get_db(); reset_db() re-selects the
backend (used by tests after env changes).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from shell.app.billing._contracts import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


@dataclass(frozen=True)
class Entitlements:
    """Quota row for a plan — single source of truth (PRODUCTION_CRITERIA D2)."""

    plan: str
    daily_sim_quota: int
    daily_ocr_quota: int
    max_runs: int


_DEFAULT_MAX_RUNS = 1000


def _default_entitlements() -> dict[str, Entitlements]:
    s = get_settings()
    return {
        "free": Entitlements("free", int(s.free_sims_per_day), 0, _DEFAULT_MAX_RUNS),
        "pro": Entitlements(
            "pro", int(s.pro_sims_per_day), int(s.pro_ocr_per_day), _DEFAULT_MAX_RUNS
        ),
    }


# ===========================================================================
# In-memory backend (keyless dev / tests)
# ===========================================================================
class InMemoryDB:
    """Dict-backed stand-in implementing the exact PostgresDB interface.

    No asyncio primitives are held across calls, so it is safe to drive from
    multiple short-lived event loops (asyncio.run per test).
    """

    is_postgres = False

    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.profiles: dict[str, dict] = {}
        self.subscriptions: dict[str, dict] = {}
        self.usage_events: list[dict] = []
        self.ocr_jobs: dict[str, dict] = {}
        self.saved_scenarios: dict[str, dict] = {}
        self.audit_log: list[dict] = []
        self._audit_dedup: set[str] = set()
        self.entitlements: dict[str, Entitlements] = _default_entitlements()

    # -- lifecycle ---------------------------------------------------------
    async def close(self) -> None:
        return None

    # -- users / profiles --------------------------------------------------
    async def upsert_user(self, clerk_user_id: str, email: str | None = None) -> dict:
        row = self.users.get(clerk_user_id)
        if row is None:
            row = {
                "clerk_user_id": clerk_user_id,
                "email": email,
                "created_at": _utcnow(),
            }
            self.users[clerk_user_id] = row
        elif email:
            row["email"] = email
        return dict(row)

    async def upsert_profile(
        self,
        clerk_user_id: str,
        display_name: str | None = None,
        game_server: str | None = None,
    ) -> dict:
        row = self.profiles.setdefault(
            clerk_user_id, {"clerk_user_id": clerk_user_id}
        )
        if display_name is not None:
            row["display_name"] = display_name
        if game_server is not None:
            row["game_server"] = game_server
        row["updated_at"] = _utcnow()
        return dict(row)

    # -- entitlements ------------------------------------------------------
    async def get_entitlements(self, plan: str) -> Entitlements:
        return self.entitlements.get(plan) or self.entitlements["free"]

    # -- usage_events ------------------------------------------------------
    async def record_usage(
        self,
        user_id: str,
        endpoint: str,
        kind: str,
        ip_hash: str | None = None,
        request_fingerprint: str | None = None,
        fp_fields: dict[str, str] | None = None,
        troops_own: int | None = None,
        troops_enemy: int | None = None,
        ts: datetime | None = None,
    ) -> None:
        self.usage_events.append(
            {
                "clerk_user_id": user_id,
                "ip_hash": ip_hash,
                "endpoint": endpoint,
                "kind": kind,
                "request_fingerprint": request_fingerprint,
                "fp_fields": dict(fp_fields or {}),
                "troops_own": troops_own,
                "troops_enemy": troops_enemy,
                "ts": ts or _utcnow(),
            }
        )

    async def get_usage_today(self, user_id: str, kind: str) -> int:
        start, end = _day_bounds(_utcnow().date())
        return sum(
            1
            for e in self.usage_events
            if e["clerk_user_id"] == user_id
            and e["kind"] == kind
            and start <= e["ts"] < end
        )

    async def get_ip_usage_today(self, ip_hash: str, kind: str) -> int:
        if not ip_hash:
            return 0
        start, end = _day_bounds(_utcnow().date())
        return sum(
            1
            for e in self.usage_events
            if e["ip_hash"] == ip_hash and e["kind"] == kind and start <= e["ts"] < end
        )

    async def count_recent_events(self, user_id: str, seconds: int) -> int:
        cutoff = _utcnow() - timedelta(seconds=seconds)
        return sum(
            1
            for e in self.usage_events
            if e["clerk_user_id"] == user_id and e["ts"] >= cutoff
        )

    async def fetch_usage_for_day(self, day: date) -> list[dict]:
        start, end = _day_bounds(day)
        return [dict(e) for e in self.usage_events if start <= e["ts"] < end]

    # -- subscriptions -----------------------------------------------------
    async def get_subscription(self, user_id: str) -> Optional[dict]:
        row = self.subscriptions.get(user_id)
        return dict(row) if row else None

    async def get_user_by_customer(self, stripe_customer_id: str) -> Optional[str]:
        for uid, row in self.subscriptions.items():
            if row.get("stripe_customer_id") == stripe_customer_id:
                return uid
        return None

    async def apply_subscription_update(
        self,
        user_id: str,
        *,
        plan: str,
        status: str,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        current_period_end: datetime | None = None,
    ) -> dict:
        await self.upsert_user(user_id)
        row = self.subscriptions.setdefault(
            user_id,
            {
                "clerk_user_id": user_id,
                "stripe_customer_id": None,
                "stripe_subscription_id": None,
                "plan": "free",
                "status": "inactive",
                "current_period_end": None,
            },
        )
        row["plan"] = plan
        row["status"] = status
        if stripe_customer_id is not None:
            row["stripe_customer_id"] = stripe_customer_id
        if stripe_subscription_id is not None:
            row["stripe_subscription_id"] = stripe_subscription_id
        row["current_period_end"] = current_period_end
        row["updated_at"] = _utcnow()
        return dict(row)

    # -- ocr_jobs ----------------------------------------------------------
    async def create_ocr_job(
        self,
        user_id: str,
        upload_ref: str | None = None,
        image_hash: str | None = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        self.ocr_jobs[job_id] = {
            "id": job_id,
            "clerk_user_id": user_id,
            "upload_ref": upload_ref,
            "image_hash": image_hash,
            "status": "pending",
            "extracted": None,
            "validator_verdict": None,
            "cost_usd": None,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        }
        return job_id

    async def update_ocr_job(self, job_id: str, **fields: Any) -> Optional[dict]:
        row = self.ocr_jobs.get(job_id)
        if row is None:
            return None
        for key in ("status", "extracted", "validator_verdict", "cost_usd"):
            if key in fields and fields[key] is not None:
                row[key] = fields[key]
        row["updated_at"] = _utcnow()
        return dict(row)

    async def find_ocr_job_by_hash(self, image_hash: str) -> Optional[dict]:
        done = [
            r
            for r in self.ocr_jobs.values()
            if r["image_hash"] == image_hash and r["status"] in ("ok", "partial")
        ]
        if not done:
            return None
        return dict(max(done, key=lambda r: r["created_at"]))

    async def get_ocr_job_by_hash(self, image_hash: str) -> Optional[dict]:
        """Latest job for this image hash, ANY status (failures are cached too
        so a bad screenshot never costs twice — Agent C's cache contract)."""
        rows = [r for r in self.ocr_jobs.values() if r["image_hash"] == image_hash]
        if not rows:
            return None
        return dict(max(rows, key=lambda r: r["created_at"]))

    # -- saved_scenarios ---------------------------------------------------
    async def save_scenario(
        self, user_id: str, name: str, schema_version: str, payload: dict
    ) -> str:
        await self.upsert_user(user_id)
        sid = str(uuid.uuid4())
        self.saved_scenarios[sid] = {
            "id": sid,
            "clerk_user_id": user_id,
            "name": name,
            "schema_version": str(schema_version),
            "payload": payload,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        }
        return sid

    async def get_scenario(self, user_id: str, scenario_id: str) -> Optional[dict]:
        row = self.saved_scenarios.get(scenario_id)
        if row is None or row["clerk_user_id"] != user_id:
            return None  # ownership enforced server-side (assume hostile client)
        return dict(row)

    async def list_scenarios(self, user_id: str) -> list[dict]:
        rows = [
            dict(r)
            for r in self.saved_scenarios.values()
            if r["clerk_user_id"] == user_id
        ]
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return rows

    # -- audit_log ---------------------------------------------------------
    async def audit(
        self,
        event_type: str,
        actor: str | None = None,
        subject: str | None = None,
        detail: dict | None = None,
        dedup_key: str | None = None,
    ) -> bool:
        """Append an audit entry. Returns False (no write) on dedup_key replay."""
        if dedup_key is not None:
            if dedup_key in self._audit_dedup:
                return False
            self._audit_dedup.add(dedup_key)
        self.audit_log.append(
            {
                "event_type": event_type,
                "actor": actor,
                "subject": subject,
                "detail": detail or {},
                "dedup_key": dedup_key,
                "ts": _utcnow(),
            }
        )
        return True

    async def get_audit_entries(
        self, event_type: str | None = None, subject: str | None = None
    ) -> list[dict]:
        return [
            dict(e)
            for e in self.audit_log
            if (event_type is None or e["event_type"] == event_type)
            and (subject is None or e["subject"] == subject)
        ]


# ===========================================================================
# Postgres backend (Supabase; DATABASE_URL present)
# ===========================================================================
class PostgresDB:
    """asyncpg-backed implementation of the same interface as InMemoryDB.

    Not exercised by the keyless test suite; SQL matches 001_init.sql.
    """

    is_postgres = True

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool = None

    async def pool(self):
        if self._pool is None:
            import asyncpg  # deferred so keyless import never needs the driver

            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=8)
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def run_migrations(self) -> list[str]:
        """Apply shell/db/migrations/*.sql in filename order. Idempotent."""
        pool = await self.pool()
        applied: list[str] = []
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            sql = path.read_text(encoding="utf-8")
            async with pool.acquire() as conn:
                await conn.execute(sql)
            applied.append(path.name)
        return applied

    # -- users / profiles --------------------------------------------------
    async def upsert_user(self, clerk_user_id: str, email: str | None = None) -> dict:
        pool = await self.pool()
        row = await pool.fetchrow(
            """
            INSERT INTO users (clerk_user_id, email) VALUES ($1, $2)
            ON CONFLICT (clerk_user_id)
            DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email)
            RETURNING clerk_user_id, email, created_at
            """,
            clerk_user_id,
            email,
        )
        return dict(row)

    async def upsert_profile(
        self,
        clerk_user_id: str,
        display_name: str | None = None,
        game_server: str | None = None,
    ) -> dict:
        pool = await self.pool()
        row = await pool.fetchrow(
            """
            INSERT INTO profiles (clerk_user_id, display_name, game_server)
            VALUES ($1, $2, $3)
            ON CONFLICT (clerk_user_id) DO UPDATE SET
                display_name = COALESCE(EXCLUDED.display_name, profiles.display_name),
                game_server  = COALESCE(EXCLUDED.game_server, profiles.game_server),
                updated_at   = now()
            RETURNING *
            """,
            clerk_user_id,
            display_name,
            game_server,
        )
        return dict(row)

    # -- entitlements ------------------------------------------------------
    async def get_entitlements(self, plan: str) -> Entitlements:
        pool = await self.pool()
        row = await pool.fetchrow(
            "SELECT plan, daily_sim_quota, daily_ocr_quota, max_runs "
            "FROM entitlements WHERE plan = $1",
            plan,
        )
        if row is None:
            return _default_entitlements().get(plan, _default_entitlements()["free"])
        return Entitlements(
            row["plan"],
            row["daily_sim_quota"],
            row["daily_ocr_quota"],
            row["max_runs"],
        )

    # -- usage_events ------------------------------------------------------
    async def record_usage(
        self,
        user_id: str,
        endpoint: str,
        kind: str,
        ip_hash: str | None = None,
        request_fingerprint: str | None = None,
        fp_fields: dict[str, str] | None = None,
        troops_own: int | None = None,
        troops_enemy: int | None = None,
        ts: datetime | None = None,
    ) -> None:
        pool = await self.pool()
        await pool.execute(
            """
            INSERT INTO usage_events
                (clerk_user_id, ip_hash, endpoint, kind, request_fingerprint,
                 fp_fields, troops_own, troops_enemy, ts)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, COALESCE($9, now()))
            """,
            user_id,
            ip_hash,
            endpoint,
            kind,
            request_fingerprint,
            json.dumps(fp_fields or {}),
            troops_own,
            troops_enemy,
            ts,
        )

    async def get_usage_today(self, user_id: str, kind: str) -> int:
        start, end = _day_bounds(_utcnow().date())
        pool = await self.pool()
        return await pool.fetchval(
            "SELECT count(*) FROM usage_events "
            "WHERE clerk_user_id = $1 AND kind = $2 AND ts >= $3 AND ts < $4",
            user_id,
            kind,
            start,
            end,
        )

    async def get_ip_usage_today(self, ip_hash: str, kind: str) -> int:
        if not ip_hash:
            return 0
        start, end = _day_bounds(_utcnow().date())
        pool = await self.pool()
        return await pool.fetchval(
            "SELECT count(*) FROM usage_events "
            "WHERE ip_hash = $1 AND kind = $2 AND ts >= $3 AND ts < $4",
            ip_hash,
            kind,
            start,
            end,
        )

    async def count_recent_events(self, user_id: str, seconds: int) -> int:
        pool = await self.pool()
        cutoff = _utcnow() - timedelta(seconds=seconds)
        return await pool.fetchval(
            "SELECT count(*) FROM usage_events "
            "WHERE clerk_user_id = $1 AND ts >= $2",
            user_id,
            cutoff,
        )

    async def fetch_usage_for_day(self, day: date) -> list[dict]:
        start, end = _day_bounds(day)
        pool = await self.pool()
        rows = await pool.fetch(
            "SELECT * FROM usage_events WHERE ts >= $1 AND ts < $2", start, end
        )
        out = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("fp_fields"), str):
                d["fp_fields"] = json.loads(d["fp_fields"])
            out.append(d)
        return out

    # -- subscriptions -----------------------------------------------------
    async def get_subscription(self, user_id: str) -> Optional[dict]:
        pool = await self.pool()
        row = await pool.fetchrow(
            "SELECT * FROM subscriptions WHERE clerk_user_id = $1", user_id
        )
        return dict(row) if row else None

    async def get_user_by_customer(self, stripe_customer_id: str) -> Optional[str]:
        pool = await self.pool()
        return await pool.fetchval(
            "SELECT clerk_user_id FROM subscriptions WHERE stripe_customer_id = $1",
            stripe_customer_id,
        )

    async def apply_subscription_update(
        self,
        user_id: str,
        *,
        plan: str,
        status: str,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        current_period_end: datetime | None = None,
    ) -> dict:
        await self.upsert_user(user_id)
        pool = await self.pool()
        row = await pool.fetchrow(
            """
            INSERT INTO subscriptions
                (clerk_user_id, stripe_customer_id, stripe_subscription_id,
                 plan, status, current_period_end, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, now())
            ON CONFLICT (clerk_user_id) DO UPDATE SET
                stripe_customer_id =
                    COALESCE(EXCLUDED.stripe_customer_id, subscriptions.stripe_customer_id),
                stripe_subscription_id =
                    COALESCE(EXCLUDED.stripe_subscription_id, subscriptions.stripe_subscription_id),
                plan = EXCLUDED.plan,
                status = EXCLUDED.status,
                current_period_end = EXCLUDED.current_period_end,
                updated_at = now()
            RETURNING *
            """,
            user_id,
            stripe_customer_id,
            stripe_subscription_id,
            plan,
            status,
            current_period_end,
        )
        return dict(row)

    # -- ocr_jobs ----------------------------------------------------------
    async def create_ocr_job(
        self,
        user_id: str,
        upload_ref: str | None = None,
        image_hash: str | None = None,
    ) -> str:
        pool = await self.pool()
        return str(
            await pool.fetchval(
                "INSERT INTO ocr_jobs (clerk_user_id, upload_ref, image_hash) "
                "VALUES ($1, $2, $3) RETURNING id",
                user_id,
                upload_ref,
                image_hash,
            )
        )

    async def update_ocr_job(self, job_id: str, **fields: Any) -> Optional[dict]:
        pool = await self.pool()
        row = await pool.fetchrow(
            """
            UPDATE ocr_jobs SET
                status = COALESCE($2, status),
                extracted = COALESCE($3::jsonb, extracted),
                validator_verdict = COALESCE($4::jsonb, validator_verdict),
                cost_usd = COALESCE($5, cost_usd),
                updated_at = now()
            WHERE id = $1::uuid
            RETURNING *
            """,
            job_id,
            fields.get("status"),
            json.dumps(fields["extracted"]) if fields.get("extracted") is not None else None,
            json.dumps(fields["validator_verdict"])
            if fields.get("validator_verdict") is not None
            else None,
            fields.get("cost_usd"),
        )
        return dict(row) if row else None

    async def find_ocr_job_by_hash(self, image_hash: str) -> Optional[dict]:
        pool = await self.pool()
        row = await pool.fetchrow(
            "SELECT * FROM ocr_jobs WHERE image_hash = $1 "
            "AND status IN ('ok', 'partial') ORDER BY created_at DESC LIMIT 1",
            image_hash,
        )
        return dict(row) if row else None

    async def get_ocr_job_by_hash(self, image_hash: str) -> Optional[dict]:
        pool = await self.pool()
        row = await pool.fetchrow(
            "SELECT * FROM ocr_jobs WHERE image_hash = $1 "
            "ORDER BY created_at DESC LIMIT 1",
            image_hash,
        )
        if row is None:
            return None
        d = dict(row)
        if isinstance(d.get("extracted"), str):
            d["extracted"] = json.loads(d["extracted"])
        return d

    # -- saved_scenarios ---------------------------------------------------
    async def save_scenario(
        self, user_id: str, name: str, schema_version: str, payload: dict
    ) -> str:
        await self.upsert_user(user_id)
        pool = await self.pool()
        return str(
            await pool.fetchval(
                "INSERT INTO saved_scenarios "
                "(clerk_user_id, name, schema_version, payload) "
                "VALUES ($1, $2, $3, $4::jsonb) RETURNING id",
                user_id,
                name,
                str(schema_version),
                json.dumps(payload),
            )
        )

    async def get_scenario(self, user_id: str, scenario_id: str) -> Optional[dict]:
        pool = await self.pool()
        row = await pool.fetchrow(
            "SELECT * FROM saved_scenarios WHERE id = $1::uuid AND clerk_user_id = $2",
            scenario_id,
            user_id,
        )
        if row is None:
            return None
        d = dict(row)
        if isinstance(d.get("payload"), str):
            d["payload"] = json.loads(d["payload"])
        return d

    async def list_scenarios(self, user_id: str) -> list[dict]:
        pool = await self.pool()
        rows = await pool.fetch(
            "SELECT * FROM saved_scenarios WHERE clerk_user_id = $1 "
            "ORDER BY created_at DESC",
            user_id,
        )
        out = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("payload"), str):
                d["payload"] = json.loads(d["payload"])
            out.append(d)
        return out

    # -- audit_log ---------------------------------------------------------
    async def audit(
        self,
        event_type: str,
        actor: str | None = None,
        subject: str | None = None,
        detail: dict | None = None,
        dedup_key: str | None = None,
    ) -> bool:
        pool = await self.pool()
        row = await pool.fetchrow(
            """
            INSERT INTO audit_log (event_type, actor, subject, detail, dedup_key)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            ON CONFLICT (dedup_key) DO NOTHING
            RETURNING id
            """,
            event_type,
            actor,
            subject,
            json.dumps(detail or {}, default=str),
            dedup_key,
        )
        return row is not None

    async def get_audit_entries(
        self, event_type: str | None = None, subject: str | None = None
    ) -> list[dict]:
        pool = await self.pool()
        rows = await pool.fetch(
            "SELECT * FROM audit_log WHERE ($1::text IS NULL OR event_type = $1) "
            "AND ($2::text IS NULL OR subject = $2) ORDER BY ts",
            event_type,
            subject,
        )
        out = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("detail"), str):
                d["detail"] = json.loads(d["detail"])
            out.append(d)
        return out


# ===========================================================================
# Backend selection + module-level contract functions
# ===========================================================================
_db_instance: InMemoryDB | PostgresDB | None = None


def get_db() -> InMemoryDB | PostgresDB:
    """Return the process-wide DB backend.

    DATABASE_URL present -> PostgresDB; absent -> InMemoryDB (keyless dev,
    per ARCHITECTURE.md mock-first rule)."""
    global _db_instance
    if _db_instance is None:
        dsn = get_settings().database_url or os.environ.get("DATABASE_URL")
        _db_instance = PostgresDB(dsn) if dsn else InMemoryDB()
    return _db_instance


def reset_db() -> None:
    """Drop the cached backend (tests; env changes). Postgres pool closure is
    the caller's responsibility if one was opened.

    Also drops entitlements.resolve_plan()'s in-process cache: it is keyed by
    user_id, and user_ids are reused across test functions (e.g. "user_A" in
    test_billing_webhook.py), so a stale cached plan could otherwise leak
    from one test into the next. Deferred import to avoid a module-load-time
    cycle (billing/__init__.py imports webhook.py imports this module);
    best-effort — a pre-Agent-B-billing tree must still reset cleanly."""
    global _db_instance
    _db_instance = None
    try:
        from shell.app.billing.entitlements import invalidate_plan_cache

        invalidate_plan_cache()
    except Exception:
        pass


async def get_pool():
    """Contract function: asyncpg pool, or None when running in-memory."""
    db = get_db()
    if isinstance(db, PostgresDB):
        return await db.pool()
    return None


async def run_migrations() -> list[str]:
    db = get_db()
    if isinstance(db, PostgresDB):
        return await db.run_migrations()
    return []  # in-memory backend needs no migrations


# Thin delegating wrappers so callers can `from shell.app import db` and use
# module functions per the ARCHITECTURE.md contract.
async def record_usage(*args: Any, **kwargs: Any) -> None:
    return await get_db().record_usage(*args, **kwargs)


async def get_entitlements(plan: str) -> Entitlements:
    return await get_db().get_entitlements(plan)


async def get_usage_today(user_id: str, kind: str) -> int:
    return await get_db().get_usage_today(user_id, kind)


async def get_ip_usage_today(ip_hash: str, kind: str) -> int:
    return await get_db().get_ip_usage_today(ip_hash, kind)


async def count_recent_events(user_id: str, seconds: int) -> int:
    return await get_db().count_recent_events(user_id, seconds)


async def fetch_usage_for_day(day: date) -> list[dict]:
    return await get_db().fetch_usage_for_day(day)


async def upsert_user(clerk_user_id: str, email: str | None = None) -> dict:
    return await get_db().upsert_user(clerk_user_id, email)


async def upsert_profile(clerk_user_id: str, **kwargs: Any) -> dict:
    return await get_db().upsert_profile(clerk_user_id, **kwargs)


async def get_subscription(user_id: str) -> Optional[dict]:
    return await get_db().get_subscription(user_id)


async def get_user_by_customer(stripe_customer_id: str) -> Optional[str]:
    return await get_db().get_user_by_customer(stripe_customer_id)


async def apply_subscription_update(user_id: str, **kwargs: Any) -> dict:
    return await get_db().apply_subscription_update(user_id, **kwargs)


async def create_ocr_job(
    user_id: str = "unknown",
    *,
    upload_ref: str | None = None,
    image_hash: str | None = None,
    status: str | None = None,
    result: dict | None = None,
    cost_estimate_usd: float | None = None,
    **_extra: Any,
) -> str:
    """Create an ocr_jobs row. Two calling styles are supported:

    * Agent B two-step: create_ocr_job(user_id, upload_ref=..., image_hash=...)
      then update_ocr_job(job_id, status=..., extracted=..., cost_usd=...).
    * Agent C one-shot (shell/app/ocr/cache.py DbOcrJobs): keyword-only
      (image_hash, user_id, status, result, cost_estimate_usd) -> job_id.
    """
    backend = get_db()
    job_id = await backend.create_ocr_job(
        user_id, upload_ref=upload_ref, image_hash=image_hash
    )
    if status is not None or result is not None or cost_estimate_usd is not None:
        await backend.update_ocr_job(
            job_id, status=status, extracted=result, cost_usd=cost_estimate_usd
        )
    return job_id


async def update_ocr_job(job_id: str, **kwargs: Any) -> Optional[dict]:
    return await get_db().update_ocr_job(job_id, **kwargs)


async def find_ocr_job_by_hash(image_hash: str) -> Optional[dict]:
    return await get_db().find_ocr_job_by_hash(image_hash)


async def get_ocr_job_by_hash(image_hash: str) -> Optional[dict]:
    """Latest job for the hash, any status; record carries BOTH naming styles
    ("extracted"/"cost_usd" per §2.2 and "result"/"cost_estimate_usd" per
    Agent C's cache adapter)."""
    row = await get_db().get_ocr_job_by_hash(image_hash)
    if row is None:
        return None
    row = dict(row)
    row.setdefault("result", row.get("extracted"))
    if "cost_estimate_usd" not in row:
        cost = row.get("cost_usd")
        row["cost_estimate_usd"] = float(cost) if cost is not None else None
    return row


async def save_scenario(
    user_id: str, name: str, schema_version: str, payload: dict
) -> str:
    return await get_db().save_scenario(user_id, name, schema_version, payload)


async def get_scenario(user_id: str, scenario_id: str) -> Optional[dict]:
    return await get_db().get_scenario(user_id, scenario_id)


async def list_scenarios(user_id: str) -> list[dict]:
    return await get_db().list_scenarios(user_id)


async def audit(
    event_type: str,
    actor: str | None = None,
    subject: str | None = None,
    detail: dict | None = None,
    dedup_key: str | None = None,
) -> bool:
    return await get_db().audit(event_type, actor, subject, detail, dedup_key)


async def get_audit_entries(
    event_type: str | None = None, subject: str | None = None
) -> list[dict]:
    return await get_db().get_audit_entries(event_type, subject)
