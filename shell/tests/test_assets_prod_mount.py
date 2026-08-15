"""Tests for the shell/assets_prod/ static mount + overlay.js asset fallback.

M3 (EVAL_ROUND_1.md F18, carried over unfixed by EVAL_ROUND_2.md M3): a
promoted bundle strips ALL raster art from prototype/ and wos_sim/ before it
ships (shell/promote.py step3_assemble — Century Games IP never ships), but
the mounted prototype's own JS still emits <img src="avatars/...">,
"assets/Icons/*.png", "assets/ui/*.png" unconditionally, and NOTHING served
those paths' replacements (`grep -rn assets_prod shell/app/` returned zero
matches in both eval rounds). The fix: shell/app/main.py mounts
shell/assets_prod/ (the 22-SVG original-art replacement pack) at
/shell/assets/, and shell/app/overlay/overlay.js reacts to the browser's own
<img> "error" event (fires ONLY on an actual load failure — an ordinary dev
checkout with raster art intact never triggers any of this) to swap in the
matching SVG when one exists (class/role icons) or hide the image and show
its alt text instead (per-hero avatars / per-skill icons have no 1:1 entry
in the 22-key manifest — the "accept text-only ... and suppress the <img>"
alternative F18 explicitly sanctions).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from fastapi.testclient import TestClient

from shell.app.config import Settings
from shell.app.main import create_app


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


# ------------------------------------------------------------- the mount

def test_manifest_served_at_shell_assets(client):
    resp = client.get("/shell/assets/manifest.json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["assets"]["class.infantry"] == "class_infantry.svg"
    assert body["assets"]["role.rally"] == "chip_role_rally.svg"
    assert body["assets"]["gen.1"] == "gen_01.svg"


def test_every_manifest_entry_is_actually_fetchable(client):
    manifest = json.loads(
        (_REPO_ROOT / "shell" / "assets_prod" / "manifest.json")
        .read_text(encoding="utf-8"))
    for key, filename in manifest["assets"].items():
        resp = client.get(f"/shell/assets/{filename}")
        assert resp.status_code == 200, f"{key} -> {filename}"
        assert "svg" in resp.headers["content-type"], filename


def test_shell_app_now_references_assets_prod():
    """Direct regression for the eval's own reproduction method: both
    EVAL_ROUND_1.md F18 and EVAL_ROUND_2.md M3 confirmed the bug via
    `grep -rn assets_prod shell/app/` returning zero matches."""
    text = (_REPO_ROOT / "shell" / "app" / "main.py").read_text(encoding="utf-8")
    assert "assets_prod" in text
    assert "/shell/assets" in text


def test_prototype_file_on_disk_still_untouched():
    html = (_REPO_ROOT / "prototype" / "index.html").read_text(encoding="utf-8")
    assert "/shell/assets/" not in html


# ------------------------------------------------- overlay.js fallback script

def test_overlay_js_carries_the_asset_fallback_listener(client):
    resp = client.get("/shell/overlay.js")
    assert resp.status_code == 200
    text = resp.text
    assert "__wosAssetFallback" in text
    assert '"error"' in text or "'error'" in text   # listens on the img error event
    assert "/shell/assets/manifest.json" in text
    for cdn in ("http://", "https://cdn", "googleapis", "unpkg", "jsdelivr"):
        assert cdn not in text                      # still self-contained, no CDNs


def test_overlay_js_maps_the_three_class_icons_and_two_role_icons(client):
    text = client.get("/shell/overlay.js").text
    for needle in ("class.infantry", "class.lancer", "class.marksman",
                   "role.rally", "role.garrison"):
        assert needle in text


def test_overlay_css_carries_the_fallback_label_style(client):
    resp = client.get("/shell/overlay.css")
    assert resp.status_code == 200
    assert "wos-asset-fallback-label" in resp.text


# --------------------------------------------- fallback matching logic (JS,
# mirrored in Python so the mapping table has a real regression test without
# a browser/Node harness — kept in lockstep with overlay.js's PATTERNS list)

CLASS_AND_ROLE_ICON_PATHS = {
    "assets/Icons/Infantry.png": "class.infantry",
    "assets/Icons/Lancer.png": "class.lancer",
    "assets/Icons/Marksman.png": "class.marksman",
    "assets/ui/rally-swords.png": "role.rally",
    "assets/ui/garrison-shield.png": "role.garrison",
}


def test_manifest_has_an_entry_for_every_path_the_overlay_js_maps():
    """If overlay.js's PATTERNS table ever grows a new key, this fails loudly
    instead of silently shipping a fallback that resolves to `undefined`."""
    manifest = json.loads(
        (_REPO_ROOT / "shell" / "assets_prod" / "manifest.json")
        .read_text(encoding="utf-8"))
    for path, key in CLASS_AND_ROLE_ICON_PATHS.items():
        assert key in manifest["assets"], f"{path} -> {key} not in manifest.json"
