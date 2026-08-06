"""shell.app.ocr — OCR battle-report ingestion service (Agent C).

Implements PRODUCTION_PLAN.md §2.3: the wos-battlereport-ingestion skill,
industrialized. Upload endpoint → vision-LLM extraction (v2 schema, never
fabricate) → validator (wraps the skill's scripts/validate_report.py) →
BRD §9 profile prefill, with image-hash caching and job recording.

Public surface:
    shell.app.ocr.router   — APIRouter exposing POST /shell/ocr
"""
from .router import router  # noqa: F401
