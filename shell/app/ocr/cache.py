"""Image-hash → OCR result cache / job store (PRODUCTION_PLAN.md §2.3, §2.2 ocr_jobs).

Contract (async, duck-typed):
    get_by_hash(image_hash) -> job record dict | None
    create_job(image_hash=..., user_id=..., status=..., result=...,
               cost_estimate_usd=...) -> job_id (str)

Backend selection: if Agent B's shell.app.db exposes ocr_jobs helpers
(``get_ocr_job_by_hash`` / ``create_ocr_job``), use them; otherwise fall back
to an in-memory dict with the identical interface so Agent C's tests run
keyless (ARCHITECTURE.md: db.py provides an in-memory fallback in DEV_BYPASS).

Notes:
- Cache key is the sha256 of the ORIGINAL upload bytes (stable across
  re-uploads of the same file). Cached content derives solely from the image
  itself, so a cross-user hit only ever returns data the uploader already
  holds in the image; results are never listed or browsable (plan §2.5).
- Deterministic failures (validator_rejected / unparseable at temperature 0)
  are cached too — re-uploading the same image must not burn another vision call.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

try:  # Agent B's Postgres access layer (may not exist yet)
    from shell.app import db as _db  # type: ignore
except Exception:  # pragma: no cover - exercised only pre-Agent-B
    _db = None


@runtime_checkable
class OcrJobStore(Protocol):
    async def get_by_hash(self, image_hash: str) -> dict[str, Any] | None: ...

    async def create_job(self, *, image_hash: str, user_id: str, status: str,
                         result: dict[str, Any], cost_estimate_usd: float) -> str: ...


class InMemoryOcrJobs:
    """Keyless fallback store; same shape Agent B's ocr_jobs table records."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._by_hash: dict[str, dict[str, Any]] = {}

    async def get_by_hash(self, image_hash: str) -> dict[str, Any] | None:
        return self._by_hash.get(image_hash)

    async def create_job(self, *, image_hash: str, user_id: str, status: str,
                         result: dict[str, Any], cost_estimate_usd: float) -> str:
        job_id = uuid.uuid4().hex
        record = {
            "job_id": job_id,
            "image_hash": image_hash,
            "user_id": user_id,
            "status": status,
            "result": result,
            "cost_estimate_usd": cost_estimate_usd,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._jobs[job_id] = record
        self._by_hash[image_hash] = record
        return job_id

    def clear(self) -> None:
        self._jobs.clear()
        self._by_hash.clear()


class DbOcrJobs:
    """Thin adapter over Agent B's db helpers (name contract TBC with Agent B).

    TODO(Agent B): confirm helper names/signatures once shell/app/db.py lands.
    Expected: async get_ocr_job_by_hash(image_hash) -> record|None and
    async create_ocr_job(image_hash, user_id, status, result, cost_estimate_usd) -> job_id.
    """

    def __init__(self, dbmod) -> None:
        self._db = dbmod

    async def get_by_hash(self, image_hash: str) -> dict[str, Any] | None:
        return await self._db.get_ocr_job_by_hash(image_hash)

    async def create_job(self, *, image_hash: str, user_id: str, status: str,
                         result: dict[str, Any], cost_estimate_usd: float) -> str:
        return await self._db.create_ocr_job(
            image_hash=image_hash,
            user_id=user_id,
            status=status,
            result=result,
            cost_estimate_usd=cost_estimate_usd,
        )


_default_store: OcrJobStore | None = None


def get_job_store() -> OcrJobStore:
    """Module-level default store (singleton). Prefers Agent B's db when present."""
    global _default_store
    if _default_store is None:
        if (
            _db is not None
            and hasattr(_db, "get_ocr_job_by_hash")
            and hasattr(_db, "create_ocr_job")
        ):
            _default_store = DbOcrJobs(_db)
        else:
            _default_store = InMemoryOcrJobs()
    return _default_store
