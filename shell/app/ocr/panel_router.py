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

Plan gating is NOT done here (QA D-031). Both OCR endpoints are metered by
LimitsMiddleware, whose free-tier signal is 402 ``payment_required``; the outer
layer wins, so a second in-route plan check could only ever disagree with it.
"""
from __future__ import annotations

import io
import os

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from ._shims import get_settings
from .panel.ladder import EngineUnavailable, extract_panel_production
from .panel.service import extract_panel

# 2026-08-29 (owner phone test): 16 MB aggregate — four-to-six real phone
# screenshots at 1.5-3 MB each; still a hard cap (E6/D2 intent kept).
MAX_BODY_BYTES = 16 * 1024 * 1024
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


def _upscale_to_width(image: bytes, target: int) -> bytes:
    """LANCZOS-upscale *image* so its width is at least *target* (aspect kept,
    re-encoded as PNG). Returns the original bytes unchanged when it is already
    wide enough or cannot be decoded (the ladder reports undecodable input)."""
    try:
        from PIL import Image as _Image
        with _Image.open(io.BytesIO(image)) as im:
            if im.size[0] >= target:
                return image
            scale = target / float(im.size[0])
            big = im.convert("RGB").resize(
                (target, max(1, int(round(im.size[1] * scale)))), _Image.LANCZOS)
            out = io.BytesIO()
            big.save(out, format="PNG")
            return out.getvalue()
    except Exception:
        return image


def _smallest_width(images) -> int | None:
    """Pixel width of the narrowest upload, or None if no header could be read
    (an undecodable image is the ladder's problem to report, not this guard's)."""
    widths = []
    for image in images:
        try:
            from PIL import Image as _Image
            with _Image.open(io.BytesIO(image)) as im:
                widths.append(int(im.size[0]))
        except Exception:
            continue
    return min(widths) if widths else None


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

    if side not in ("you", "enemy"):
        return JSONResponse(status_code=422, content={"error": "invalid_side"})
    if panel not in (None, "battle", "scout", "citystats"):
        return JSONResponse(status_code=422, content={"error": "invalid_panel"})
    # 2026-08-29: the four-row battle UI (Heroes+Experts / Battle stats /
    # Buffs x2 / Troop Power) legitimately sends up to 6 shots — the old cap
    # of 3 rejected the owner's first real phone read (422 invalid_file_count).
    if not file or len(file) > 6:
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
    # 2026-09-10: fail FAST and honestly on screenshots too small to read
    # (forwarded/compressed copies) — see config.MIN_OCR_IMAGE_WIDTH. Measured
    # before any engine runs, so a hopeless upload costs milliseconds, not the
    # ladder's full Gemini-timeout budget.
    min_width = int(getattr(get_settings(), "MIN_OCR_IMAGE_WIDTH", 120) or 0)
    if min_width > 0:
        too_small = _smallest_width(images)
        if too_small is not None and too_small < min_width:
            return JSONResponse(status_code=422, content={
                "error": "image_too_small", "width": too_small, "min_width": min_width})
    # 2026-09-11: small-but-readable screenshots (chat-forwarded copies, small
    # emulator windows — "not from phone") are upscaled to the ladder's working
    # width rather than refused; the ladder's Gemini gap-fill reads what
    # RapidOCR can't at that size. Never downscales.
    target = int(getattr(get_settings(), "OCR_UPSCALE_TARGET_WIDTH", 1000) or 0)
    if target > 0:
        images = [_upscale_to_width(image, target) for image in images]

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
