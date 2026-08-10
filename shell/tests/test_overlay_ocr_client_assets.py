from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from fastapi.testclient import TestClient

from shell.app.config import Settings
from shell.app.main import create_app
from shell.app.overlay import SCRIPT_TAG
from shell.app.overlay.middleware import OCR_FLOW_CSS_TAG, OCR_FLOW_SCRIPT_TAG

OVERLAY_TAG = SCRIPT_TAG.decode()
CSS_TAG = OCR_FLOW_CSS_TAG.decode()
JS_TAG = OCR_FLOW_SCRIPT_TAG.decode()


@pytest.fixture(autouse=True)
def _fresh_limits_state():
    try:
        from shell.app import db as _db
        _db.reset_db()
    except Exception:
        pass
    yield


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(_env_file=None, DEV_BYPASS=True)))


def test_served_index_carries_all_three_tags_in_order(client):
    resp = client.get("/")
    assert resp.status_code == 200
    text = resp.text
    assert OVERLAY_TAG in text and CSS_TAG in text and JS_TAG in text
    body_close = text.lower().rfind("</body>")
    assert text.find(OVERLAY_TAG) < text.find(CSS_TAG) < text.find(JS_TAG) < body_close


def test_ocr_flow_js_served_as_a_module_self_contained(client):
    resp = client.get("/shell/ocr/client/ocr_flow.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    for cdn in ("http://", "https://cdn", "googleapis", "unpkg", "jsdelivr"):
        assert cdn not in resp.text


def test_ocr_flow_css_served(client):
    resp = client.get("/shell/ocr/client/ocr_flow.css")
    assert resp.status_code == 200
    assert "css" in resp.headers["content-type"]


def test_sibling_client_modules_are_fetchable_for_browser_import(client):
    # The exact relative import targets ocr_flow.js resolves at runtime.
    for path in ("flow_state.mjs", "panel_parser.mjs", "engine_tesseract.mjs"):
        resp = client.get(f"/shell/ocr/client/{path}")
        assert resp.status_code == 200, path


def test_prototype_file_on_disk_still_untouched():
    html = (_REPO_ROOT / "prototype" / "index.html").read_text(encoding="utf-8")
    assert "/shell/ocr/client/ocr_flow.js" not in html
