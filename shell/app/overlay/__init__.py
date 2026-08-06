"""shell/app/overlay — status-chip overlay assets + injection (Agent A).

Exports:
* ``router``            — GET /shell/overlay.js and /shell/overlay.css
                          (auth-exempt; they render the signed-out chip too)
* ``OverlayMiddleware`` — injects the script tag into the served index page
                          at response time (see middleware.py)

Implements PRODUCTION_PLAN.md §2 (overlay UI: login state, quota meter,
upgrade prompt) without ever editing prototype/index.html.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from .middleware import OverlayMiddleware, SCRIPT_TAG, inject

__all__ = ["router", "OverlayMiddleware", "SCRIPT_TAG", "inject"]

_HERE = Path(__file__).resolve().parent

router = APIRouter()

# no-cache: the overlay ships with the shell and may change every release;
# it is tiny, so revalidation beats a stale quota/plan chip.
_HEADERS = {"Cache-Control": "no-cache"}


@router.get("/shell/overlay.js", include_in_schema=False)
def overlay_js() -> FileResponse:
    return FileResponse(_HERE / "overlay.js",
                        media_type="application/javascript", headers=_HEADERS)


@router.get("/shell/overlay.css", include_in_schema=False)
def overlay_css() -> FileResponse:
    return FileResponse(_HERE / "overlay.css",
                        media_type="text/css", headers=_HEADERS)
