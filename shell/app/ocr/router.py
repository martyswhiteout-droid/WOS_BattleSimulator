"""POST /shell/ocr — screenshot upload endpoint (PRODUCTION_PLAN.md §2.3 step 1;
response contract per shell/ARCHITECTURE.md).

Flow: auth presence (request.state.user, set by Agent A's AuthMiddleware) →
Agent B's limits.check_and_record (402 for free plan, 429 quota/burst) →
OcrService pipeline (validate/strip → hash → cache → vision → validator →
BRD §9 profile) → JSON result. Image-intake violations map to 400.
"""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from ._shims import get_settings
from .extract import ImageValidationError, OcrService, get_default_service

try:  # Agent B's quota/rate layer (may not exist yet)
    from shell.app.limits import check_and_record  # type: ignore
except Exception:  # pragma: no cover - exercised only pre-Agent-B
    # TODO(Agent B): remove this no-op once shell/app/limits.py lands.
    # Contract: async check_and_record(user, endpoint, body, ip_hash) -> LimitVerdict;
    # Denied carries (status, code, message) — e.g. 402 payment_required for OCR
    # on the free plan, 429 quota_exhausted/burst.
    check_and_record = None

router = APIRouter()


def _ip_hash(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return hashlib.sha256(host.encode("utf-8")).hexdigest()


def _get_service(request: Request) -> OcrService:
    """App-supplied service (tests / main.py wiring) or the module default."""
    svc = getattr(request.app.state, "ocr_service", None)
    return svc if isinstance(svc, OcrService) else get_default_service()


@router.post("/shell/ocr")
async def ocr_upload(
    request: Request,
    file: UploadFile = File(...),
    side: str = Form("attacker"),
):
    # Auth presence — AuthMiddleware populates request.state.user (Agent A).
    user = getattr(request.state, "user", None)
    if user is None:
        settings = get_settings()
        base = getattr(settings, "base_url", "") or ""
        return JSONResponse(
            status_code=401,
            content={"error": "auth_required", "sign_in_url": f"{base}/sign-in"},
        )

    if side not in ("attacker", "defender"):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_side",
                     "message": "side must be 'attacker' or 'defender'"},
        )

    # Quota / plan gate (Agent B). Duck-typed: Denied carries status/code/message.
    if check_and_record is not None:
        verdict = await check_and_record(user, "ocr", None, _ip_hash(request))
        denied_status = getattr(verdict, "status", None)
        if isinstance(denied_status, int):
            return JSONResponse(
                status_code=denied_status,
                content={
                    "error": getattr(verdict, "code", "denied"),
                    "message": getattr(verdict, "message", ""),
                },
            )

    raw = await file.read()
    service = _get_service(request)
    try:
        result = await service.process(raw, user_id=user.user_id, side=side)
    except ImageValidationError as exc:
        return JSONResponse(
            status_code=400, content={"error": exc.code, "message": str(exc)}
        )
    return JSONResponse(status_code=200, content=result)
