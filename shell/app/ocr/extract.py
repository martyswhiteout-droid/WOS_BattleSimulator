"""OCR extraction orchestration (PRODUCTION_PLAN.md §2.3 steps 1-4).

Pipeline: image bytes → validation (size/type) + EXIF strip (pillow) → sha256
image hash → cache check → vision call → parse JSON → validator (wraps the
ingestion skill's scripts/validate_report.py WITHOUT modifying it) → map the
validated v2 report onto the BRD §9 profile shape for sim-form prefill.

Result contract (ARCHITECTURE.md):
    {"status": "ok"|"partial"|"failed", "profile": <BRD §9 partial or null>,
     "unreadable_fields": [...], "job_id": ...}
partial = extraction valid but some fields null/unreadable; failed = the
validator rejected the extraction or the model output was unparseable.
Never-fabricate (COMPASS invariant 8): unknowns surface as nulls +
unreadable_fields for manual entry — nothing is guessed on the user's behalf.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .cache import OcrJobStore, get_job_store
from .vision import VisionClient, get_vision_client

# --- image intake ----------------------------------------------------------

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB upload cap
# PIL format name -> media type sent to the vision API. Detection is by
# decoded content, never by filename/Content-Type (assume hostile client).
ALLOWED_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
# Screenshot-sized guard against decompression bombs (well above any phone/4K
# screenshot, well below PIL's default warning threshold).
MAX_IMAGE_PIXELS = 64_000_000

_REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = (
    _REPO_ROOT
    / ".claude"
    / "skills"
    / "wos-battlereport-ingestion"
    / "scripts"
    / "validate_report.py"
)

CLASSES = ("Infantry", "Lancer", "Marksman")
STATS = ("Attack", "Defense", "Lethality", "Health")


class ImageValidationError(ValueError):
    """Upload rejected before any vision call. ``code`` is machine-readable."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class PreparedImage:
    """EXIF-stripped, re-encoded image ready for the vision API."""

    data: bytes          # stripped bytes actually sent to the model
    media_type: str      # image/png | image/jpeg | image/webp
    sha256: str          # hash of the ORIGINAL upload bytes (cache key)


def prepare_image(raw: bytes) -> PreparedImage:
    """Validate size/type, strip EXIF/metadata, and hash the upload.

    Raises ImageValidationError (codes: empty_upload, image_too_large,
    invalid_image, unsupported_image_type) — the router maps these to 400.
    """
    if not raw:
        raise ImageValidationError("empty_upload", "Empty upload.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ImageValidationError(
            "image_too_large",
            f"Image is {len(raw)} bytes; the limit is {MAX_IMAGE_BYTES} (8 MB).",
        )
    try:
        img = Image.open(io.BytesIO(raw))
        fmt = img.format
        if (img.width * img.height) > MAX_IMAGE_PIXELS:
            raise ImageValidationError(
                "image_too_large",
                f"Image dimensions {img.width}x{img.height} exceed the pixel limit.",
            )
        img.load()
    except ImageValidationError:
        raise
    except Exception as exc:
        raise ImageValidationError(
            "invalid_image", f"Could not decode upload as an image: {exc}"
        ) from exc
    if fmt not in ALLOWED_FORMATS:
        raise ImageValidationError(
            "unsupported_image_type",
            f"Unsupported image type {fmt!r}; accepted: PNG, JPEG, WEBP.",
        )
    # EXIF strip: apply the orientation tag so the picture still looks right,
    # then re-encode WITHOUT metadata (no exif/pnginfo passed to save()).
    img = ImageOps.exif_transpose(img)
    out = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(out, format="JPEG", quality=92)
    elif fmt == "PNG":
        img.save(out, format="PNG")
    else:  # WEBP
        img.save(out, format="WEBP")
    return PreparedImage(
        data=out.getvalue(),
        media_type=ALLOWED_FORMATS[fmt],
        sha256=hashlib.sha256(raw).hexdigest(),
    )


# --- validator adapter (wraps the skill's script; the script is NOT modified) ---

_validator_module = None


def _load_validator():
    """importlib-load the ingestion skill's validate_report.py from its home.

    The skill file is the single source of validation truth (SKILL.md: "never
    hand-verify arithmetic"); we import it in place rather than copying logic.
    """
    global _validator_module
    if _validator_module is None:
        if not VALIDATOR_PATH.is_file():
            raise FileNotFoundError(
                f"Ingestion-skill validator not found at {VALIDATOR_PATH}; the "
                "deploy must include the wos-battlereport-ingestion skill."
            )
        spec = importlib.util.spec_from_file_location(
            "wos_ingestion_validate_report", VALIDATOR_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        _validator_module = module
    return _validator_module


def run_validator(doc: dict) -> tuple[list[str], list[str]]:
    """Run the skill validator's check() on an in-memory report dict.

    check() takes a file path, so the dict is round-tripped through a temp
    file — zero validator logic is duplicated or altered here.
    Returns (errors, warnings).
    """
    module = _load_validator()
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    try:
        json.dump(doc, tmp, ensure_ascii=False)
        tmp.close()
        return module.check(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# --- LLM output parsing ----------------------------------------------------

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_llm_json(text: str) -> dict | None:
    """Parse the model's raw text into a report dict; None if unparseable."""
    if not text or not text.strip():
        return None
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    try:
        doc = json.loads(cleaned)
    except json.JSONDecodeError:
        # Salvage: take the outermost {...} span (models sometimes add prose).
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            doc = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return doc if isinstance(doc, dict) else None


# --- report → BRD §9 profile mapping ---------------------------------------

_TIER_LV_RE = re.compile(r"^\s*Lv\s*(\d+)\.0\s*$", re.IGNORECASE)
_TIER_FC_RE = re.compile(r"^\s*T(\d+)\s*FC\s*(\d+)\s*$", re.IGNORECASE)


def parse_tier_display(tier_display: str | None) -> tuple[int | None, int | None]:
    """Parse the two unambiguous tier_display forms; anything else -> (None, None).

    "Lv 6.0" -> (6, 0); "T6 FC10" -> (6, 10). Never-fabricate: an unrecognized
    display is surfaced as unreadable, not coerced.
    """
    if not isinstance(tier_display, str):
        return None, None
    m = _TIER_LV_RE.match(tier_display)
    if m:
        return int(m.group(1)), 0
    m = _TIER_FC_RE.match(tier_display)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _role_to_profile_role(role: Any) -> str | None:
    """Map report roles onto the BRD §9 rally|garrison vocabulary."""
    if role in ("rally", "attacker"):
        return "rally"
    if role in ("garrison", "defender", "encampment"):
        return "garrison"
    return None


def map_report_to_profile(doc: dict, side: str = "attacker") -> tuple[dict, list[str]]:
    """Map one side of a validated v2 report onto the BRD §9 profile shape.

    Returns (profile, unreadable_fields). unreadable_fields lists profile
    paths that stayed null because the report could not read them, plus the
    report's own _validation.missing entries (prefixed "report:").
    """
    if side == "defender":
        side_obj = doc.get("defender") or doc.get("defender_beast") or {}
    else:
        side_obj = doc.get(side) or {}
    unreadable: list[str] = []

    def _null(path: str):
        unreadable.append(path)
        return None

    troops = side_obj.get("troops")
    if not isinstance(troops, (int, float)) or isinstance(troops, bool):
        troops = _null("troops_total")

    # formation: single-class controlled fights -> 1.0; PvP -> composition shares
    formation: dict[str, float] | None = None
    deployed = side_obj.get("deployed_class")
    composition = side_obj.get("composition")
    if isinstance(deployed, str) and deployed in CLASSES:
        formation = {c: (1.0 if c == deployed else 0.0) for c in CLASSES}
    elif isinstance(composition, dict) and composition:
        formation = {c: 0.0 for c in CLASSES}
        for cls, row in composition.items():
            share = row.get("share") if isinstance(row, dict) else None
            if cls in CLASSES and isinstance(share, (int, float)):
                formation[cls] = float(share)
    else:
        formation = _null("formation")

    # per_class tier/fc
    per_class: dict[str, dict] | None = None
    if isinstance(composition, dict) and composition:
        per_class = {}
        for cls, row in composition.items():
            if cls not in CLASSES or not isinstance(row, dict):
                continue
            tier, fc = row.get("tier_level"), row.get("fc_badge")
            entry = {
                "tier": int(tier) if isinstance(tier, (int, float)) else None,
                "fc": int(fc) if isinstance(fc, (int, float)) else None,
            }
            if entry["tier"] is None:
                unreadable.append(f"per_class.{cls}.tier")
            if entry["fc"] is None:
                unreadable.append(f"per_class.{cls}.fc")
            per_class[cls] = entry
    else:
        tier, fc = parse_tier_display(side_obj.get("tier_display"))
        classes = [deployed] if isinstance(deployed, str) and deployed in CLASSES else []
        if classes and tier is not None:
            per_class = {c: {"tier": tier, "fc": fc} for c in classes}
        elif classes:
            per_class = {c: {"tier": None, "fc": None} for c in classes}
            unreadable.append(f"per_class.{classes[0]}.tier")
        else:
            per_class = _null("per_class")

    # stats: flatten the displayed stat-bonuses grid to "Class|Stat" keys
    stats: dict[str, Any] = {"mode": "scouted"}
    stats_pct = side_obj.get("stats_pct")
    stats_flat = side_obj.get("stats_pct_FLAT")
    cap = side_obj.get("stats_capture") or {}
    if isinstance(stats_pct, dict):
        for cls in CLASSES:
            row = stats_pct.get(cls)
            for stat in STATS:
                val = row.get(stat) if isinstance(row, dict) else None
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    stats[f"{cls}|{stat}"] = val
                else:
                    unreadable.append(f"stats.{cls}|{stat}")
    elif isinstance(stats_flat, dict):
        flat = stats_flat.get("all_classes_all_stats")
        if isinstance(flat, (int, float)):
            for cls in CLASSES:
                for stat in STATS:
                    stats[f"{cls}|{stat}"] = flat
        else:
            unreadable.append("stats")
    else:
        # stats_capture is the honesty ledger — missing panel means manual entry
        unreadable.append("stats")
        if cap.get("attack_defense") == "missing":
            unreadable.extend(f"stats.{cls}|{s}" for cls in CLASSES for s in ("Attack", "Defense"))
        if cap.get("lethality_health") == "missing":
            unreadable.extend(f"stats.{cls}|{s}" for cls in CLASSES for s in ("Lethality", "Health"))

    # captain heroes + skill levels
    captain: dict | None = None
    lead = side_obj.get("lead_heroes")
    if isinstance(lead, dict) and lead:
        heroes: list[str] = []
        levels: list[int | None] = []
        skills = side_obj.get("hero_skills") or []
        for slot, h in lead.items():
            name = h.get("name") if isinstance(h, dict) else None
            if not isinstance(name, str):
                unreadable.append(f"captain.heroes[{slot}]")
                continue
            heroes.append(name)
            lvl = next(
                (s.get("level") for s in skills
                 if isinstance(s, dict) and s.get("hero") == name
                 and isinstance(s.get("level"), int)),
                None,
            )
            if lvl is None:
                unreadable.append(f"captain.skill_levels[{name}]")
            levels.append(lvl)
        captain = {"heroes": heroes, "skill_levels": levels, "widgets": []}
    # lead_heroes == null legitimately means "no heroes" (schema) — not unreadable.

    # joiners (PvP conditional)
    joiner_flags = side_obj.get("joiner_flags")
    joiners = (
        [{"flag_hero": f, "level": None} for f in joiner_flags if isinstance(f, str)]
        if isinstance(joiner_flags, list)
        else []
    )

    # specials
    specials = []
    for sp in side_obj.get("specials") or []:
        if isinstance(sp, dict):
            specials.append(
                {
                    "source": sp.get("source"),
                    "stat": sp.get("stat"),
                    "value": sp.get("value"),
                    "applies_to": sp.get("applies_to"),
                }
            )

    name = side_obj.get("name")
    label = f"OCR: {name}" if isinstance(name, str) and name else f"OCR: {side} (name unreadable)"
    if not (isinstance(name, str) and name):
        unreadable.append("label")

    profile = {
        "schema_version": 1,
        "label": label,
        "role": _role_to_profile_role(side_obj.get("role")),
        "context": None,  # not inferable from one screenshot — user selects in the form
        "troops_total": troops,
        "formation": formation,
        "per_class": per_class,
        "stats": stats,
        "captain": captain,
        "joiners": joiners,
        "specials": specials,
        "uncertainty": {},
    }
    if profile["role"] is None:
        unreadable.append("role")

    # carry the report's own honesty ledger through to the caller
    missing = (doc.get("_validation") or {}).get("missing") or []
    unreadable.extend(f"report:{m}" for m in missing if isinstance(m, str))

    # dedupe, order-preserving
    seen: set[str] = set()
    unreadable = [u for u in unreadable if not (u in seen or seen.add(u))]
    return profile, unreadable


# --- orchestration ---------------------------------------------------------

class OcrService:
    """image bytes → {"status", "profile", "unreadable_fields", "job_id", ...}."""

    def __init__(
        self,
        vision: VisionClient | None = None,
        jobs: OcrJobStore | None = None,
        settings=None,
    ):
        if settings is None:
            from ._shims import get_settings

            settings = get_settings()
        self.settings = settings
        self.vision = vision if vision is not None else get_vision_client(settings)
        self.jobs = jobs if jobs is not None else get_job_store()

    async def process(self, raw: bytes, *, user_id: str, side: str = "attacker") -> dict:
        prepared = prepare_image(raw)  # raises ImageValidationError → router 400

        cached = await self.jobs.get_by_hash(prepared.sha256)
        if cached is not None:
            out = dict(cached["result"])
            out["job_id"] = cached["job_id"]
            out["cached"] = True
            return out

        raw_text = self.vision.extract(prepared.data, prepared.media_type)
        doc = parse_llm_json(raw_text)
        if doc is None:
            result = {
                "status": "failed",
                "profile": None,
                "unreadable_fields": [],
                "reason": "unparseable_llm_output: the vision model did not "
                          "return a JSON report",
                "warnings": [],
            }
        else:
            errors, warnings = run_validator(doc)
            if errors:
                result = {
                    "status": "failed",
                    "profile": None,
                    "unreadable_fields": [],
                    "reason": "validator_rejected: " + "; ".join(errors[:5]),
                    "warnings": warnings,
                }
            else:
                profile, unreadable = map_report_to_profile(doc, side=side)
                result = {
                    "status": "partial" if unreadable else "ok",
                    "profile": profile,
                    "unreadable_fields": unreadable,
                    "reason": None,
                    "warnings": warnings,
                }

        job_id = await self.jobs.create_job(
            image_hash=prepared.sha256,
            user_id=user_id,
            status=result["status"],
            result=result,
            cost_estimate_usd=getattr(self.vision, "cost_estimate_usd", 0.0),
        )
        out = dict(result)
        out["job_id"] = job_id
        out["cached"] = False
        return out


_default_service: OcrService | None = None


def get_default_service() -> OcrService:
    global _default_service
    if _default_service is None:
        _default_service = OcrService()
    return _default_service
