"""Vision-LLM clients for OCR battle-report extraction (PRODUCTION_PLAN.md §2.3 step 2).

VisionClient protocol + two implementations:

- AnthropicVision: real Anthropic API call (model from settings, temperature 0,
  image + extraction prompt). The extraction prompt embeds the canonical v2
  schema (read verbatim from the ingestion skill's references/schema.md) and the
  never-fabricate rule (COMPASS invariant 8). The LLM sees ONLY the user's
  screenshot + the public report schema — no engine internals (D4).
- MockVision: active when OCR_MOCK=1 or no ANTHROPIC_API_KEY is configured.
  Returns canned extraction JSON from the synthetic test fixtures so the whole
  pipeline runs keyless (ARCHITECTURE.md mock-first rule).
"""
from __future__ import annotations

import base64
import os
from functools import lru_cache
from pathlib import Path
from typing import Protocol, runtime_checkable

# Repo root: <root>/shell/app/ocr/vision.py -> parents[3] == <root>
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_DIR = _REPO_ROOT / ".claude" / "skills" / "wos-battlereport-ingestion"
SCHEMA_MD_PATH = _SKILL_DIR / "references" / "schema.md"
# Synthetic mock-LLM outputs (plumbing tests only — NOT real battle data).
FIXTURE_DIR = _REPO_ROOT / "shell" / "tests" / "fixtures" / "ocr"
DEFAULT_MOCK_FIXTURE = "synthetic_valid_type1.json"

# The skill's never-fabricate rule, verbatim (COMPASS invariant 8).
NEVER_FABRICATE_RULE = (
    "If a field is not clearly visible, return null. NEVER guess or infer values."
)


@lru_cache(maxsize=1)
def build_extraction_prompt() -> str:
    """Build the extraction prompt with the v2 schema embedded verbatim.

    The schema text is read from the ingestion skill's references/schema.md at
    runtime so the prompt can never drift from the canonical spec. Raises a
    clear error if the skill file is missing (deployment must ship the repo).
    """
    if not SCHEMA_MD_PATH.is_file():
        raise FileNotFoundError(
            f"Canonical v2 schema not found at {SCHEMA_MD_PATH}. The OCR "
            "extraction prompt embeds references/schema.md verbatim; deploy "
            "must include the wos-battlereport-ingestion skill directory."
        )
    schema_text = SCHEMA_MD_PATH.read_text(encoding="utf-8")
    return (
        "You are a deterministic OCR extraction engine for Whiteout Survival "
        "(WoS) battle-report screenshots.\n"
        "Extract the battle report shown in the attached image into ONE "
        "canonical JSON document that follows schema v2 below EXACTLY, "
        "including key order.\n"
        "\n"
        "Binding rules:\n"
        f"1. {NEVER_FABRICATE_RULE}\n"
        "2. Unknown or not-visible values -> null, plus an entry in "
        "`_validation.missing` (a flagged gap is recoverable; a guessed digit "
        "poisons downstream data).\n"
        "3. Numbers are JSON numbers, never strings; record percentages as "
        "displayed (`176.2`, not `1.762`).\n"
        "4. Record `tier_display` EXACTLY as shown (e.g. \"Lv 1.0\", "
        "\"T6 FC10\"); never substitute an assumed tier.\n"
        "5. Player/entity names exactly as shown (keep CJK characters).\n"
        "6. If a schema-required screen (e.g. Stat Bonuses) is not part of the "
        "image, declare it missing via `stats_capture` / `_validation.missing` "
        "instead of inventing values.\n"
        "7. Output ONLY the JSON object - no markdown fences, no commentary.\n"
        "\n"
        "=== CANONICAL SCHEMA v2 (verbatim from the wos-battlereport-ingestion "
        "skill, references/schema.md) ===\n"
        f"{schema_text}\n"
        "=== END SCHEMA ===\n"
    )


@runtime_checkable
class VisionClient(Protocol):
    """Contract every vision backend implements."""

    #: Rough per-screenshot cost recorded on the ocr_jobs entry (USD).
    cost_estimate_usd: float

    def extract(self, image_bytes: bytes, media_type: str) -> str:
        """Return the model's raw text output for one screenshot."""
        ...


class AnthropicVision:
    """Real Anthropic vision call. Requires ANTHROPIC_API_KEY; temperature 0."""

    cost_estimate_usd = 0.03  # PRODUCTION_PLAN §2.3: ~US$0.01-0.05/screenshot

    def __init__(self, api_key: str, model: str, max_tokens: int = 8000):
        import anthropic  # imported lazily so keyless/mock runs need no client

        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def extract(self, image_bytes: bytes, media_type: str) -> str:
        message = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": build_extraction_prompt()},
                    ],
                }
            ],
        )
        return "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        )


class MockVision:
    """Keyless mock: returns a canned extraction from the synthetic fixtures.

    Fixture selection order: explicit ``fixture`` argument > OCR_MOCK_FIXTURE
    env var > DEFAULT_MOCK_FIXTURE. ``fixture`` may be a bare filename
    (resolved against fixture_dir) or a full path. ``calls`` counts extract()
    invocations so tests can assert the cache prevented a second vision call.
    """

    cost_estimate_usd = 0.0

    def __init__(self, fixture: str | os.PathLike | None = None,
                 fixture_dir: Path | None = None):
        self.fixture_dir = Path(fixture_dir) if fixture_dir else FIXTURE_DIR
        name = fixture or os.environ.get("OCR_MOCK_FIXTURE") or DEFAULT_MOCK_FIXTURE
        p = Path(name)
        self.fixture_path = p if p.is_absolute() else self.fixture_dir / p
        self.calls = 0

    def extract(self, image_bytes: bytes, media_type: str) -> str:
        self.calls += 1
        return self.fixture_path.read_text(encoding="utf-8")


def get_vision_client(settings=None) -> VisionClient:
    """Pick the backend: MockVision when OCR_MOCK=1 or no API key, else Anthropic."""
    if settings is None:
        from ._shims import get_settings

        settings = get_settings()
    ocr_mock = bool(getattr(settings, "ocr_mock", False))
    api_key = getattr(settings, "anthropic_api_key", None)
    if ocr_mock or not api_key:
        return MockVision(fixture=getattr(settings, "ocr_mock_fixture", None))
    model = getattr(settings, "ocr_vision_model", None) or "claude-sonnet-4-5"
    return AnthropicVision(api_key=api_key, model=model)
