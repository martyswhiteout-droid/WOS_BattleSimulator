"""shell/app/overlay/middleware.py — response-time overlay injection (Agent A).

Implements PRODUCTION_PLAN.md §2 "small JS overlay ... injected at serve time —
prototype index.html NOT edited" (boundary rule 1: prototype/ is READ-ONLY).

When the mounted prototype app serves its index page, this middleware rewrites
the HTML *response body* to add ``<script defer src="/shell/overlay.js">``
just before ``</body>``. The file on disk is never touched; ENV makes no
difference (the overlay renders dev identity in DEV_BYPASS too).
"""
from __future__ import annotations

from ..config import Settings

SCRIPT_TAG = b'<script defer src="/shell/overlay.js"></script>'
# shell/app/ocr/client/ocr_flow.{js,css} — the OCR overlay UI (docs/plans/
# 2026-08-10-overlay-ui-tdd-plan.md Task 5). Injected alongside the account
# chip's SCRIPT_TAG rather than served by this middleware itself; the actual
# files are served by the static mount in shell/app/main.py.
OCR_FLOW_CSS_TAG = b'<link rel="stylesheet" href="/shell/ocr/client/ocr_flow.css">'
OCR_FLOW_SCRIPT_TAG = b'<script type="module" src="/shell/ocr/client/ocr_flow.js"></script>'
INJECTED_TAGS = SCRIPT_TAG + OCR_FLOW_CSS_TAG + OCR_FLOW_SCRIPT_TAG

# Only the app shell page gets the overlay — not arbitrary HTML assets.
_INJECT_PATHS = frozenset({"/", "/index.html"})


def inject(html: bytes) -> bytes:
    """Insert the overlay + ocr_flow tags before the LAST ``</body>`` (case-
    insensitive). No closing tag -> append (still a valid, working page)."""
    idx = html.lower().rfind(b"</body>")
    if idx == -1:
        return html + INJECTED_TAGS
    return html[:idx] + INJECTED_TAGS + html[idx:]


class OverlayMiddleware:
    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http"
                or scope.get("method") not in ("GET", "HEAD")
                or scope.get("path") not in _INJECT_PATHS):
            await self.app(scope, receive, send)
            return

        state = {"start": None, "chunks": [], "html": False, "done": False}

        async def capture(message):
            if state["done"]:
                return
            if message["type"] == "http.response.start":
                headers = message.get("headers") or []
                ctype = next((v for n, v in headers if n.lower() == b"content-type"), b"")
                if message.get("status") == 200 and b"text/html" in ctype:
                    state["start"], state["html"] = message, True
                else:                       # not the page: stream through untouched
                    await send(message)
            elif message["type"] == "http.response.body" and state["html"]:
                state["chunks"].append(message.get("body", b""))
                if not message.get("more_body"):
                    state["done"] = True
                    await _flush()
            else:
                await send(message)

        async def _flush():
            body = inject(b"".join(state["chunks"]))
            headers = [(n, v) for n, v in (state["start"].get("headers") or [])
                       if n.lower() != b"content-length"]
            headers.append((b"content-length", str(len(body)).encode()))
            await send({"type": "http.response.start",
                        "status": state["start"].get("status", 200),
                        "headers": headers})
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, capture)
