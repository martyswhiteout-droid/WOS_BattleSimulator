"""Agent C — unit tests for shell.app.ocr.extract / vision (keyless, OCR_MOCK).

Covers: image size/type validation, EXIF stripping, the validator adapter that
wraps the ingestion skill's validate_report.py, LLM-output parsing, the
BRD §9 profile mapping, and keyless vision-client selection.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

# Make `shell.app.ocr` importable regardless of pytest invocation directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shell.app.ocr.extract import (  # noqa: E402
    MAX_IMAGE_BYTES,
    ImageValidationError,
    map_report_to_profile,
    parse_llm_json,
    parse_tier_display,
    prepare_image,
    run_validator,
)
from shell.app.ocr.vision import (  # noqa: E402
    FIXTURE_DIR,
    NEVER_FABRICATE_RULE,
    MockVision,
    build_extraction_prompt,
    get_vision_client,
)

VALID = json.loads((FIXTURE_DIR / "synthetic_valid_type1.json").read_text(encoding="utf-8"))
PARTIAL = json.loads((FIXTURE_DIR / "synthetic_partial_nulls.json").read_text(encoding="utf-8"))
INVALID = json.loads((FIXTURE_DIR / "synthetic_invalid.json").read_text(encoding="utf-8"))


def make_png(color=(10, 20, 30), size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def make_jpeg_with_exif() -> bytes:
    img = Image.new("RGB", (64, 64), (200, 100, 50))
    exif = Image.Exif()
    exif[0x010F] = "SyntheticCam"  # Make
    exif[0x0110] = "TestPhone 9"   # Model
    exif[0x0112] = 6               # Orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


# --- image intake ----------------------------------------------------------

def test_prepare_image_rejects_oversized():
    with pytest.raises(ImageValidationError) as ei:
        prepare_image(b"\x00" * (MAX_IMAGE_BYTES + 1))
    assert ei.value.code == "image_too_large"


def test_prepare_image_rejects_empty_and_garbage():
    with pytest.raises(ImageValidationError) as ei:
        prepare_image(b"")
    assert ei.value.code == "empty_upload"
    with pytest.raises(ImageValidationError) as ei:
        prepare_image(b"definitely not an image")
    assert ei.value.code == "invalid_image"


def test_prepare_image_rejects_unsupported_type():
    buf = io.BytesIO()
    Image.new("P", (16, 16)).save(buf, format="GIF")
    with pytest.raises(ImageValidationError) as ei:
        prepare_image(buf.getvalue())
    assert ei.value.code == "unsupported_image_type"


def test_prepare_image_accepts_png_and_hashes_original():
    raw = make_png()
    prep = prepare_image(raw)
    assert prep.media_type == "image/png"
    assert prep.sha256 == hashlib.sha256(raw).hexdigest()
    assert Image.open(io.BytesIO(prep.data)).format == "PNG"


def test_exif_actually_stripped():
    raw = make_jpeg_with_exif()
    # sanity: the source really carries EXIF
    assert dict(Image.open(io.BytesIO(raw)).getexif())
    prep = prepare_image(raw)
    out = Image.open(io.BytesIO(prep.data))
    assert dict(out.getexif()) == {}, "EXIF must be stripped from the bytes sent onward"
    assert prep.media_type == "image/jpeg"
    # cache key is the hash of the ORIGINAL upload, not the re-encode
    assert prep.sha256 == hashlib.sha256(raw).hexdigest()


# --- validator adapter (wraps the skill script unmodified) ------------------

def test_validator_adapter_passes_valid_fixture():
    errors, warnings = run_validator(VALID)
    assert errors == []
    assert warnings == []


def test_validator_adapter_passes_partial_fixture():
    errors, _ = run_validator(PARTIAL)
    assert errors == []


def test_validator_adapter_rejects_invalid_fixture():
    errors, _ = run_validator(INVALID)
    assert errors, "the deliberately broken fixture must produce validator ERRORs"
    joined = " ".join(errors)
    assert "casualty identity" in joined
    assert "'type' must be 1 or 2" in joined


# --- LLM output parsing ----------------------------------------------------

def test_parse_llm_json_variants():
    doc = {"schema_version": 2}
    assert parse_llm_json(json.dumps(doc)) == doc
    assert parse_llm_json("```json\n" + json.dumps(doc) + "\n```") == doc
    assert parse_llm_json("Here is the report:\n" + json.dumps(doc) + "\nDone.") == doc
    assert parse_llm_json("no json here") is None
    assert parse_llm_json("") is None
    assert parse_llm_json("[1, 2, 3]") is None  # non-object output is unusable


# --- tier parsing + profile mapping ----------------------------------------

def test_parse_tier_display_never_guesses():
    assert parse_tier_display("Lv 1.0") == (1, 0)
    assert parse_tier_display("Lv 6.0") == (6, 0)
    assert parse_tier_display("T6 FC10") == (6, 10)
    assert parse_tier_display("T11 FC5") == (11, 5)
    assert parse_tier_display("Lv 11.5") == (None, None)  # ambiguous -> unreadable
    assert parse_tier_display(None) == (None, None)
    assert parse_tier_display("garbled") == (None, None)


def test_profile_mapping_valid_attacker_is_complete():
    profile, unreadable = map_report_to_profile(VALID, side="attacker")
    assert unreadable == []
    assert profile["schema_version"] == 1
    assert profile["troops_total"] == 1000
    assert profile["role"] == "rally"
    assert profile["formation"] == {"Infantry": 1.0, "Lancer": 0.0, "Marksman": 0.0}
    assert profile["per_class"] == {"Infantry": {"tier": 1, "fc": 0}}
    assert profile["stats"]["mode"] == "scouted"
    assert profile["stats"]["Infantry|Attack"] == 150.0
    assert profile["stats"]["Marksman|Health"] == 107.0
    assert profile["captain"] is None  # lead_heroes null == genuinely no heroes
    assert profile["joiners"] == []


def test_profile_mapping_valid_defender_role():
    profile, unreadable = map_report_to_profile(VALID, side="defender")
    assert unreadable == []
    assert profile["role"] == "garrison"
    assert profile["troops_total"] == 1000
    assert profile["formation"]["Lancer"] == 1.0


def test_profile_mapping_partial_surfaces_unreadable_fields():
    # attacker side: stats readable, but the report's own missing-ledger carries through
    profile, unreadable = map_report_to_profile(PARTIAL, side="attacker")
    assert profile["troops_total"] == 500
    assert any(u.startswith("report:") for u in unreadable)
    # defender side: stat panel + tier genuinely unreadable -> explicit nulls, no guesses
    dprof, dunread = map_report_to_profile(PARTIAL, side="defender")
    assert dprof["per_class"] == {"Infantry": {"tier": None, "fc": None}}
    assert "per_class.Infantry.tier" in dunread
    assert "stats" in dunread
    assert all(k == "mode" for k in dprof["stats"])  # no stat values invented


# --- vision client selection + prompt --------------------------------------

def test_extraction_prompt_embeds_schema_and_never_fabricate():
    prompt = build_extraction_prompt()
    assert NEVER_FABRICATE_RULE in prompt
    assert "If a field is not clearly visible, return null. NEVER guess or infer values." in prompt
    # v2 schema embedded verbatim from references/schema.md
    assert "Canonical WoS battle-report JSON schema (v2)" in prompt
    assert "`stats_capture`" in prompt
    assert "Arithmetic identities" in prompt


def test_get_vision_client_keyless_returns_mock(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OCR_MOCK", raising=False)
    assert isinstance(get_vision_client(), MockVision)


def test_get_vision_client_ocr_mock_overrides_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-key-for-test")
    monkeypatch.setenv("OCR_MOCK", "1")
    assert isinstance(get_vision_client(), MockVision)


def test_mock_vision_returns_fixture_and_counts_calls():
    mv = MockVision(fixture="synthetic_valid_type1.json")
    out = mv.extract(b"irrelevant", "image/png")
    assert json.loads(out)["schema_version"] == 2
    assert mv.calls == 1
    mv.extract(b"irrelevant", "image/png")
    assert mv.calls == 2
