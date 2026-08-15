"""POST /shell/ocr — screenshot upload endpoint (PRODUCTION_PLAN.md §2.3 step 1;
response contract per shell/ARCHITECTURE.md).

Flow: auth presence (request.state.user, set by Agent A's AuthMiddleware) →
shell.app.limits.LimitsMiddleware (402 for free plan, 429 quota/burst —
metered BEFORE this handler ever runs; see the C2 note below) → OcrService
pipeline (validate/strip → hash → cache → vision → validator → BRD §9
profile) → JSON result. Image-intake violations map to 400.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from ._shims import SkillUnavailableError, get_settings
from .extract import ImageValidationError, OcrService, get_default_service

router = APIRouter()


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

    # Quota / plan gate: EVAL_ROUND_2.md C2. This handler used to ALSO call
    # limits.check_and_record itself (the EVAL_ROUND_1.md F21 fix — passing
    # the full path "/shell/ocr" instead of the bare "ocr" string
    # limits.classify_endpoint couldn't match). That fix was textually
    # correct but created a second, simultaneously-live metering point:
    # shell.app.main.create_app() always wires shell.app.limits.LimitsMiddleware
    # as the app-wide limits layer, and LimitsMiddleware._metered() already
    # matches POST /shell/ocr and already calls check_and_record itself,
    # BEFORE the request ever reaches this route handler. Every allowed
    # request was therefore recorded TWICE — a Pro user's 30/day quota
    # became ~15 real uploads, and the 5/min burst window tripped after 2
    # uploads instead of 5 (live-confirmed by the evaluator). There is now
    # exactly ONE metering point for both OCR endpoints: LimitsMiddleware —
    # matching shell/app/ocr/panel_router.py's own documented approach
    # ("Plan gating is NOT done here ... a second in-route plan check could
    # only ever disagree with it"). Denial responses (402/429) are therefore
    # never produced by this file; they are handled by LimitsMiddleware
    # before this handler runs at all — see shell/tests/test_ocr_router.py's
    # test_free_plan_upload_is_actually_gated_402 for the "surviving layer"
    # regression coverage this change requires.

    raw = await file.read()
    service = _get_service(request)
    try:
        result = await service.process(raw, user_id=user.user_id, side=side)
    except ImageValidationError as exc:
        return JSONResponse(
            status_code=400, content={"error": exc.code, "message": str(exc)}
        )
    except SkillUnavailableError as exc:
        # Deploy/ops problem (missing .claude/skills/wos-battlereport-
        # ingestion — EVAL_ROUND_1.md F1), never a bare 500: the client did
        # nothing wrong and there is nothing for it to retry differently.
        return JSONResponse(
            status_code=503, content={"error": exc.code, "message": str(exc)}
        )
    return JSONResponse(status_code=200, content=result)
