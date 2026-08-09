"""POST /shell/ocr/panel — stat-panel screenshot upload.

What happens to the uploaded bytes (QA D-007/D-024, stated honestly): Starlette
parses the multipart body into UploadFile objects backed by
``tempfile.SpooledTemporaryFile`` with a 1 MiB spool threshold. Uploads under
1 MiB stay in memory; anything larger IS written to the OS temp directory for
the life of the request and deleted when the request ends. This module never
opens a file for writing and never persists anything itself — the only durable
artefacts are Starlette's short-lived spill files.

The route guard below runs BEFORE the body is read or parsed, so it bounds what
can ever reach the spool:
  * ``Transfer-Encoding: chunked`` (any casing) -> 411. A chunked body declares
    no length, so it cannot be size-checked up front.
  * declared ``Content-Length`` over MAX_REQUEST_BYTES (MAX_BODY_BYTES plus
    64 KiB of multipart framing) -> 413.
  * no Content-Length and not chunked -> FAIL OPEN, deliberately: the request
    reaches the handler and is caught by the post-parse per-file and aggregate
    caps, which means such a body can be spooled first.
So the worst case an unauthenticated caller can put on disk is one body of
roughly MAX_BODY_BYTES + 64 KiB, not the 3x that the earlier ceiling allowed.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from shell.app.billing.entitlements import resolve_plan
from ._shims import get_settings
from .panel.ladder import EngineUnavailable, extract_panel_production
from .panel.service import extract_panel

MAX_BODY_BYTES = 8 * 1024 * 1024
# The aggregate cap plus 64 KiB of multipart framing: nothing legitimate can
# declare more, so anything larger is refused before the body is read
# (QA D-024 tightened this from 3 x MAX_BODY_BYTES).
MAX_REQUEST_BYTES = MAX_BODY_BYTES + 65536


def _is_chunked(request: Request) -> bool:
    return "chunked" in request.headers.get("transfer-encoding", "").lower()


def _declared_length_too_large(request: Request) -> bool:
    raw = request.headers.get("content-length")
    if not raw:
        return False        # deliberate fail-open; see the module docstring
    try:
        return int(raw) > MAX_REQUEST_BYTES
    except ValueError:
        return False


class _ContentLengthGuardRoute(APIRoute):
    """Reject unsizeable/oversize requests before FastAPI reads or parses the
    body (QA D-007/D-024).

    A route-class wrapper is the only hook that runs ahead of form parsing: a
    handler-level check (or a Depends) would fire only after Starlette had
    already spooled the upload to disk.
    """

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded(request: Request) -> Response:
            if _is_chunked(request):
                return JSONResponse(
                    status_code=411,
                    content={"error": "length_required",
                             "message": "chunked uploads are not accepted; "
                                        "send a Content-Length"})
            if _declared_length_too_large(request):
                return JSONResponse(status_code=413, content={"error": "body_too_large"})
            return await handler(request)

        return guarded


router = APIRouter(route_class=_ContentLengthGuardRoute)


def _is_image(raw: bytes) -> bool:
    return (
        raw.startswith(b"\x89PNG\r\n\x1a\n")
        or raw.startswith(b"\xff\xd8\xff")
        or (len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP")
    )


def _mock_enabled() -> bool:
    """Fixture tokens are a DEV convenience only (QA D-010/D-023).

    The environment comes from the app's Settings — the same object the rest of
    the shell is configured from — NOT from os.environ, which can disagree with
    it (.env file, cached settings). Anything other than "dev" fails CLOSED:
    blank, whitespace, a non-dev value, or a settings object without ENV all
    disable the mock, so no environment can be tricked into serving synthetic
    stats that look like a real read.
    """
    if os.environ.get("OCR_PANEL_MOCK") != "1":
        return False
    env = getattr(get_settings(), "ENV", None)
    return isinstance(env, str) and env.strip().lower() == "dev"


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

    total_bytes = 0
    for upload in file:
        size = upload.size
        if size is None:
            current = upload.file.tell()
            upload.file.seek(0, 2)
            size = upload.file.tell()
            upload.file.seek(current)
        if size > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"error": "body_too_large"})
        total_bytes += size
    if total_bytes > MAX_BODY_BYTES:      # QA D-014: aggregate cap, not just per file
        return JSONResponse(status_code=413, content={"error": "body_too_large"})

    images = [await upload.read() for upload in file]
    if any(not image for image in images):
        return JSONResponse(status_code=422, content={"error": "empty_file"})
    if any(not _is_image(image) for image in images):
        return JSONResponse(status_code=415, content={"error": "unsupported_image_type"})

    # QA D-019: every malformed-input failure in the panel stack is a ValueError
    # (CalibrationError/MissingSpecialsError included) — a client-input problem,
    # not a server fault. No 500 is reachable from bad tokens or bad images.
    if _mock_enabled():
        try:
            result = extract_panel([_mock_tokens() for _ in images], side, panel)
        except ValueError as exc:
            return JSONResponse(status_code=422,
                                content={"error": "unreadable_tokens", "message": str(exc)})
        result["source"] = "mock"   # QA D-010: mock output is never mistakable for a real read
        return JSONResponse(status_code=200, content=result)

    # Production: the engine ladder (RapidOCR primary, Gemini gap filler).
    # engines_used / field_engine pass straight through to the caller.
    try:
        result = await extract_panel_production(images, side, panel,
                                                settings=get_settings())
    except EngineUnavailable:
        return JSONResponse(status_code=503, content={"error": "ocr_engine_unavailable"})
    except RuntimeError:
        # Backstop for loop/primitive-level faults inside the ladder (e.g. an
        # asyncio primitive bound to a dead loop, QA D-030): the engine is what
        # is broken, so report it as unavailable rather than a 500.
        return JSONResponse(status_code=503, content={"error": "ocr_engine_unavailable"})
    except ValueError as exc:
        return JSONResponse(status_code=422,
                            content={"error": "unreadable_tokens", "message": str(exc)})
    result["source"] = "engine"     # the mock/real distinction is one field in both paths
    return JSONResponse(status_code=200, content=result)
