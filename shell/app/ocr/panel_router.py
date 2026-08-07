from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from shell.app.billing.entitlements import resolve_plan
from .panel.service import extract_panel

MAX_BODY_BYTES = 8 * 1024 * 1024

router = APIRouter()


def _is_image(raw: bytes) -> bool:
    return (
        raw.startswith(b"\x89PNG\r\n\x1a\n")
        or raw.startswith(b"\xff\xd8\xff")
        or (len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP")
    )


def _mock_tokens():
    tokens = []
    y = 0.10
    for cls in ("Infantry", "Lancer", "Marksman"):
        for stat, value in (
            ("Attack", "+4491.6%"),
            ("Defense", "+3979.1%"),
            ("Lethality", "+2794.3%"),
            ("Health", "+3197.4%"),
        ):
            tokens.append({
                "text": f"{cls} {stat}", "x0": 0.05, "y0": y,
                "x1": 0.40, "y1": y + 0.03, "conf": 0.99,
            })
            tokens.append({
                "text": value, "x0": 0.70, "y0": y,
                "x1": 0.95, "y1": y + 0.03, "conf": 0.97,
            })
            y += 0.05
    return tokens


@router.post("/shell/ocr/panel")
async def panel_upload(
    request: Request,
    file: list[UploadFile] = File(...),
    side: str = Form(...),
    panel: str | None = Form(None),
):
    user = getattr(request.state, "user", None)
    if user is None:
        return JSONResponse(status_code=401, content={"error": "auth_required"})

    plan = await resolve_plan(user.user_id)
    if plan == "free":
        return JSONResponse(
            status_code=403,
            content={"error": "ocr_not_available_on_free"},
        )

    if side not in ("you", "enemy"):
        return JSONResponse(status_code=422, content={"error": "invalid_side"})
    if panel not in (None, "battle", "scout", "citystats"):
        return JSONResponse(status_code=422, content={"error": "invalid_panel"})
    if not file or len(file) > 3:
        return JSONResponse(status_code=422, content={"error": "invalid_file_count"})

    for upload in file:
        size = upload.size
        if size is None:
            current = upload.file.tell()
            upload.file.seek(0, 2)
            size = upload.file.tell()
            upload.file.seek(current)
        if size > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"error": "body_too_large"})

    images = [await upload.read() for upload in file]
    if any(not image for image in images):
        return JSONResponse(status_code=422, content={"error": "empty_file"})
    if any(not _is_image(image) for image in images):
        return JSONResponse(status_code=415, content={"error": "unsupported_image_type"})

    if os.environ.get("OCR_PANEL_MOCK") != "1":
        return JSONResponse(status_code=503, content={"error": "ocr_engine_unavailable"})

    # QA D-019: every malformed-token failure in the panel stack is a ValueError
    # (CalibrationError/MissingSpecialsError included) — a client-input problem,
    # not a server fault. No 500 is reachable from bad tokens.
    try:
        result = extract_panel([_mock_tokens() for _ in images], side, panel)
    except ValueError as exc:
        return JSONResponse(status_code=422,
                            content={"error": "unreadable_tokens", "message": str(exc)})
    return JSONResponse(status_code=200, content=result)
