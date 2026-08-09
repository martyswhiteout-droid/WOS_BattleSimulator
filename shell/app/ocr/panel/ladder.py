"""Production engine ladder for ``POST /shell/ocr/panel``.

RapidOCR is the PRIMARY engine: every image is recognised locally and folded
through :func:`shell.app.ocr.panel.service.extract_panel`, which owns all the
never-fabricate gates. Gemini is a SECONDARY engine used only as a gap filler,
under a hard daily budget, because it costs money and quota per call.

**Cross-engine disagreement is impossible by construction.** Only keys the
RapidOCR pass reported in ``unreadable_fields`` are eligible for a Gemini
value. A field RapidOCR read is never re-consulted, never compared and never
overwritten, so the two engines can never produce competing numbers for one
field — there is nothing to reconcile and no tie to break. Provenance for
every gap-filled field is reported in ``field_engine``.

Ladder order:
  1. RapidOCR on each image, serialised through a module-level
     ``asyncio.Semaphore`` sized by ``OCR_CPU_CONCURRENCY`` (VPS protection:
     RapidOCR is CPU-bound and runs in a worker thread, so without this a
     burst of uploads would saturate every core).
  2. Clean result (status ok, nothing unreadable) -> return immediately;
     Gemini is not consulted and no budget is spent.
  3. Otherwise, if a GEMINI_API_KEY is configured and today's budget allows,
     call Gemini ONCE PER IMAGE (never per field) and fill only the gaps.
  4. Any Gemini failure — no key, exhausted budget, exception, timeout, or the
     engine's own failure result — degrades to "RapidOCR only" plus a single
     ``gemini fallback skipped: <reason>`` warning. A raw 429/500 never
     reaches the caller.

Budget accounting reuses the existing usage_events table and day-bounds
helpers: one row per actual Gemini call under the reserved system user, so
``db.get_usage_today`` is the counter. No new storage.
"""
from __future__ import annotations

import asyncio

from shell.app import db

from .lexicon import CLASSES
from .service import (
    CLASS_VALUE_MAX,
    CLASS_VALUE_MIN,
    SPECIAL_ABS_MAX,
    attach_side_specials,
    extract_panel,
)

DEFAULT_CPU_CONCURRENCY = 2
DEFAULT_GEMINI_DAILY_BUDGET = 1200

# Budget bookkeeping: a reserved pseudo-user so Gemini spend is global, never
# charged to (or capped by) any real account's OCR quota.
GEMINI_BUDGET_USER = "_system"
GEMINI_BUDGET_KIND = "gemini_ocr"
GEMINI_BUDGET_ENDPOINT = "/shell/ocr/panel"

# engine_gemini's documented marker for "the call itself failed" (it returns a
# normal failed result carrying this warning rather than raising).
_GEMINI_FAILURE_PREFIX = "gemini extraction failed"

_SKIP_PREFIX = "gemini fallback skipped: "

_CONF_KEYS = {"stats": "field_conf",
              "stats_left": "stats_left_conf",
              "stats_right": "stats_right_conf"}

_cpu_semaphore_instance: asyncio.Semaphore | None = None
_cpu_semaphore_size: int | None = None


class EngineUnavailable(RuntimeError):
    """The primary (RapidOCR) engine could not be loaded — the router maps
    this to 503 ``ocr_engine_unavailable``. Gemini alone is never a substitute
    for the primary engine: it is a gap filler, not a fallback engine."""


# --- engine seams (also the monkeypatch points in tests) -------------------

def _load_rapidocr():
    """Import lazily so the module (and the default test suite) never require
    the rapidocr wheel."""
    from .engine_rapidocr import recognize_image

    return recognize_image


def _load_gemini():
    """Returns ``(extract_panel_gemini, GeminiUnavailable, resolve_api_key)``.

    ``_resolve_api_key`` is engine_gemini's own definition of "a key is
    configured"; reusing it keeps one definition of that in the codebase.
    """
    from .engine_gemini import GeminiUnavailable, _resolve_api_key, extract_panel_gemini

    return extract_panel_gemini, GeminiUnavailable, _resolve_api_key


# --- settings helpers ------------------------------------------------------

def _int_setting(settings, name, default, minimum):
    value = getattr(settings, name, None)
    if value is None:
        value = default
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def _cpu_semaphore(settings) -> asyncio.Semaphore:
    global _cpu_semaphore_instance, _cpu_semaphore_size
    size = _int_setting(settings, "OCR_CPU_CONCURRENCY", DEFAULT_CPU_CONCURRENCY, 1)
    if _cpu_semaphore_instance is None or _cpu_semaphore_size != size:
        _cpu_semaphore_instance = asyncio.Semaphore(size)
        _cpu_semaphore_size = size
    return _cpu_semaphore_instance


# --- gap-fill plumbing -----------------------------------------------------

def _plausible(prefix, value):
    """The same plausibility bands service.py applies to its own engines
    (QA D-008). Belt and braces: engine_gemini already gates its output with
    these, and a gap fill must never be the one path that skips them."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if prefix in _SPECIALS_SIDE:
        return abs(value) <= SPECIAL_ABS_MAX
    return CLASS_VALUE_MIN <= value <= CLASS_VALUE_MAX


_SPECIALS_SIDE = {"specials": None, "specials_left": "left", "specials_right": "right"}


def _gemini_value(gemini_result, prefix, field):
    """The Gemini value for one unreadable key, or None.

    Only the SAME container is consulted: a Gemini result whose shape differs
    from the RapidOCR one (e.g. single-column where RapidOCR saw two) fills
    nothing rather than guessing which column a value belongs to. Specials are
    matched on (label, side) so a two-column panel's left entry can never be
    filled from the right column's value (QA D-029).
    """
    if prefix in _SPECIALS_SIDE:
        want_side = _SPECIALS_SIDE[prefix]
        for special in gemini_result.get("specials") or []:
            if (isinstance(special, dict) and special.get("label") == field
                    and special.get("side") == want_side):
                return special.get("value")
        return None
    container = gemini_result.get(prefix)
    return container.get(field) if isinstance(container, dict) else None


def _recompute_status(result):
    """service.extract_panel's own status convention, re-applied after a fill."""
    if "stats_left" in result:
        present = len(result.get("stats_left") or {}) + len(result.get("stats_right") or {})
        total = 24
    else:
        stats = result.get("stats") or {}
        present = len([k for k in stats if k.split("|")[0] in CLASSES])
        total = 12
    result["status"] = "ok" if present >= total else ("partial" if present > 0 else "failed")


def _fill_gaps(result, gemini_result):
    """Fill RapidOCR's gaps from *gemini_result*. Returns the keys filled."""
    filled = []
    for key in list(result.get("unreadable_fields") or []):
        prefix, _, field = key.partition(".")
        if prefix not in _CONF_KEYS and prefix not in _SPECIALS_SIDE:
            continue
        value = _gemini_value(gemini_result, prefix, field)
        if value is None or not _plausible(prefix, value):
            continue
        value = float(value)        # type parity with the RapidOCR path
        if prefix in _SPECIALS_SIDE:
            side = _SPECIALS_SIDE[prefix]
            entry = {"label": field, "value": value, "side": side}
            specials = result.setdefault("specials", [])
            # Replace the (label, side) entry if one exists; a fill for one
            # side must never disturb the other side's entry (QA D-029).
            for index, existing in enumerate(specials):
                if (isinstance(existing, dict) and existing.get("label") == field
                        and existing.get("side") == side):
                    specials[index] = entry
                    break
            else:
                specials.append(entry)
        else:
            target = result.get(prefix)
            if not isinstance(target, dict):
                continue
            # Mutated IN PLACE so the stats_you/stats_enemy aliases (which are
            # the same dict objects) follow automatically.
            target[field] = value
            conf = (gemini_result.get(_CONF_KEYS[prefix]) or {}).get(field)
            conf_target = result.get(_CONF_KEYS[prefix])
            if conf is not None and isinstance(conf_target, dict):
                conf_target[field] = conf
        result.setdefault("field_engine", {})[key] = "gemini"
        filled.append(key)
    if filled:
        dropped = set(filled)
        result["unreadable_fields"] = [k for k in result["unreadable_fields"]
                                       if k not in dropped]
        _recompute_status(result)
        # specials_you/specials_enemy are filtered copies, not aliases, so they
        # must be rebuilt from the updated specials list (QA D-029).
        attach_side_specials(result)
        _recompute_specials_observed(result)
    return filled


def _recompute_specials_observed(result):
    """A repaired specials panel is READ again (QA D-028).

    "partial" means rows were seen but at least one was withheld; once every
    specials key has been filled there is nothing withheld any more, so the
    verdict must return to "read" or convert.fold_sets would keep refusing a
    panel that is now complete. "none" (nothing ever seen) is never upgraded —
    there would be no specials key to fill in the first place.
    """
    if result.get("specials_observed") != "partial":
        return
    if any(key.split(".", 1)[0].startswith("specials")
           for key in result.get("unreadable_fields") or []):
        return
    result["specials_observed"] = "read"


def _engine_failure_reason(gemini_result):
    for warning in gemini_result.get("warnings") or []:
        if isinstance(warning, str) and warning.startswith(_GEMINI_FAILURE_PREFIX):
            return warning
    return None


def _skip(result, reason):
    warning = f"{_SKIP_PREFIX}{reason}"
    warnings = result.setdefault("warnings", [])
    if warning not in warnings:
        warnings.append(warning)


async def _gemini_gap_fill(result, images, side, panel_hint, *, settings):
    """Consult Gemini for the gaps. Never raises; degrades with a warning."""
    try:
        extract_gemini, unavailable_error, resolve_api_key = _load_gemini()
    except Exception as exc:                       # engine module not importable
        _skip(result, f"gemini engine unavailable ({exc})")
        return
    try:
        configured = bool(resolve_api_key(settings))
    except Exception as exc:
        _skip(result, f"gemini key lookup failed ({exc})")
        return
    if not configured:
        _skip(result, "GEMINI_API_KEY not configured")
        return

    budget = _int_setting(settings, "GEMINI_OCR_DAILY_BUDGET",
                          DEFAULT_GEMINI_DAILY_BUDGET, 0)
    spent = await db.get_usage_today(GEMINI_BUDGET_USER, GEMINI_BUDGET_KIND)
    # Gemini sees the panel type RapidOCR already established, so the two
    # results cannot end up in differently-shaped containers.
    hint = result.get("panel_type")
    if hint not in ("battle", "scout", "citystats"):
        hint = panel_hint
    calls = 0
    reason = None

    for image in images:
        if not result.get("unreadable_fields"):
            break                                   # every gap already filled
        if spent >= budget:
            reason = f"daily budget of {budget} gemini calls reached"
            break
        # Budget is committed BEFORE the call: a call that fails still consumed
        # the upstream quota, and pre-committing means no crash can leak an
        # unmetered call.
        await db.record_usage(GEMINI_BUDGET_USER, endpoint=GEMINI_BUDGET_ENDPOINT,
                              kind=GEMINI_BUDGET_KIND)
        spent += 1
        calls += 1
        try:
            gemini_result = await asyncio.to_thread(extract_gemini, image, hint, side)
        except unavailable_error as exc:
            reason = f"GEMINI_API_KEY not configured ({exc})"
            break
        except Exception as exc:                    # network, timeout, anything
            reason = f"{type(exc).__name__}: {exc}"
            break
        if not isinstance(gemini_result, dict):
            reason = "gemini returned a non-dict result"
            break
        failure = _engine_failure_reason(gemini_result)
        if failure:
            # One failure ends the Gemini phase: a failing API is unlikely to
            # serve the next image and every attempt costs budget.
            reason = failure
            break
        _fill_gaps(result, gemini_result)

    if calls:
        result["engines_used"] = ["rapidocr", "gemini"]
    if reason:
        _skip(result, reason)


async def extract_panel_production(image_bytes_list, side, panel_hint, *, settings):
    """RapidOCR -> (gaps only) Gemini. Returns a service.extract_panel result
    plus ``engines_used`` (in ladder order) and ``field_engine`` (per-field
    provenance for gap-filled keys, keyed exactly like ``unreadable_fields``).

    ``engines_used`` contains "gemini" iff a Gemini call was actually made and
    metered — a skipped fallback (no key, no budget) leaves it at
    ``["rapidocr"]``, while an attempted-but-failed call is reported honestly
    together with the ``gemini fallback skipped:`` warning explaining it.

    Raises :class:`EngineUnavailable` if the primary engine cannot be loaded.
    Image-level failures (a malformed image) surface as ValueError from the
    engine, which the router already maps to 422.
    """
    try:
        recognize = _load_rapidocr()
    except Exception as exc:
        raise EngineUnavailable(f"rapidocr engine unavailable: {exc}") from exc

    semaphore = _cpu_semaphore(settings)
    token_shots = []
    for image in image_bytes_list:
        async with semaphore:
            token_shots.append(await asyncio.to_thread(recognize, image))

    result = extract_panel(token_shots, side, panel_hint)
    result["engines_used"] = ["rapidocr"]
    result["field_engine"] = {}
    if result.get("status") == "ok" and not result.get("unreadable_fields"):
        return result

    await _gemini_gap_fill(result, image_bytes_list, side, panel_hint, settings=settings)
    return result
