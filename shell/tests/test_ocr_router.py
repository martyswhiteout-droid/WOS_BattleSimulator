"""Agent C — endpoint tests for POST /shell/ocr (keyless, mock vision).

Covers the ARCHITECTURE.md response contract: ok / partial / failed statuses,
unreadable_fields surfacing, image-hash cache hits (no second vision call),
400s for oversized / wrong-type uploads, and 401 when unauthenticated.

Isolation note: fixing EVAL_ROUND_1.md F21 (below) means check_and_record now
actually records usage_events for every allowed request in this file, all
under the same user_id. limits.py's burst window (D2, default 5/min) and
daily quota are account-scoped in shell.app.db's process-wide singleton, so
without a reset these would bleed across tests / files. _reset_shell_db makes
every test in this file start from (and leave) a clean in-memory backend.

EVAL_ROUND_2.md C2: router.py no longer calls limits.check_and_record itself
(it double-metered every request against the real app's
shell.app.limits.LimitsMiddleware — see router.py's C2 comment). Most tests
below still use the bare, middleware-free `build_client()` harness — that is
correct for them, since they are testing the HANDLER's own behavior (image
validation, caching, auth-presence, 503 mapping), not metering. The tests
that specifically exercise the plan/quota gate pass
``with_limits_middleware=True`` to wire the real LimitsMiddleware, exactly
the way shell.app.main.create_app() does — the "surviving layer" the C2 fix
relies on.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

# Make `shell.app.ocr` importable regardless of pytest invocation directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from shell.app import db as real_db  # noqa: E402
from shell.app import limits as real_limits  # noqa: E402
from shell.app.ocr._shims import SkillUnavailableError, UserCtx, _StubSettings  # noqa: E402
from shell.app.ocr.cache import DbOcrJobs, InMemoryOcrJobs  # noqa: E402
from shell.app.ocr.extract import MAX_IMAGE_BYTES, OcrService  # noqa: E402
from shell.app.ocr.router import router as ocr_router  # noqa: E402
from shell.app.ocr.vision import MockVision  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_shell_db():
    """Fresh InMemoryDB before and after every test in this file (see module
    docstring) — check_and_record's burst/quota counters are per-user_id and
    all tests here share user_id="test_user"."""
    real_db.reset_db()
    yield
    real_db.reset_db()


def make_png(color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, format="PNG")
    return buf.getvalue()


def build_client(fixture: str, *, jobs=None, settings=None, plan: str = "pro",
                  raise_server_exceptions: bool = True,
                  with_limits_middleware: bool = False,
                  ) -> tuple[TestClient, MockVision]:
    """Test app: fake auth middleware (Agent A's contract) + injected OCR service.

    ``jobs`` defaults to InMemoryOcrJobs (fast unit-test double); pass a
    DbOcrJobs wired to the real shell.app.db module to exercise the app's
    REAL store (see test_cache_hit_via_real_db_store_no_key_mismatch below).
    ``settings`` defaults to the real get_settings(); pass a _StubSettings
    override to exercise settings-driven behaviour (e.g. skill_ingestion_dir).
    ``plan`` drives the real check_and_record's quota gate.
    ``with_limits_middleware`` (C2, EVAL_ROUND_2.md): wires the REAL
    shell.app.limits.LimitsMiddleware — the app's only surviving metering
    point post-C2 — around the router, exactly as shell.app.main.create_app()
    does. Registered BEFORE the ``@app.middleware("http")`` fake_auth
    decorator below so the middleware STACK ends up fake_auth (outer) then
    LimitsMiddleware (inner): Starlette runs the LAST-added middleware
    OUTERMOST (`app.add_middleware` inserts at the front of the stack), so
    this ordering is what makes fake_auth's ``request.state.user`` visible
    to LimitsMiddleware's own ``scope["state"]["user"]`` read BEFORE it runs
    its quota check — otherwise LimitsMiddleware would fall back to its own
    dev-bypass X-Dev-Plan-header shim (default plan="free") instead of the
    ``plan`` this harness was actually asked for.
    """
    vision = MockVision(fixture=fixture)
    service = OcrService(
        vision=vision,
        jobs=jobs if jobs is not None else InMemoryOcrJobs(),
        settings=settings,
    )
    app = FastAPI()

    if with_limits_middleware:
        app.add_middleware(real_limits.LimitsMiddleware)

    @app.middleware("http")
    async def fake_auth(request, call_next):  # stands in for Agent A's AuthMiddleware
        if request.headers.get("x-test-anon") != "1":
            request.state.user = UserCtx(
                user_id="test_user", email="t@example.invalid", plan=plan
            )
        return await call_next(request)

    app.include_router(ocr_router)
    app.state.ocr_service = service
    return TestClient(app, raise_server_exceptions=raise_server_exceptions), vision


def post_image(client: TestClient, data: bytes, filename="shot.png",
               content_type="image/png", headers=None, extra=None):
    return client.post(
        "/shell/ocr",
        files={"file": (filename, data, content_type)},
        data=extra or {},
        headers=headers or {},
    )


# --- happy / partial / failed paths ----------------------------------------

def test_upload_ok_path_with_valid_mock():
    client, vision = build_client("synthetic_valid_type1.json")
    resp = post_image(client, make_png())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["unreadable_fields"] == []
    assert body["job_id"]
    assert body["cached"] is False
    assert body["profile"]["troops_total"] == 1000
    assert body["profile"]["schema_version"] == 1
    assert body["profile"]["stats"]["Infantry|Attack"] == 150.0
    assert vision.calls == 1


def test_partial_path_surfaces_unreadable_fields():
    client, _ = build_client("synthetic_partial_nulls.json")
    resp = post_image(client, make_png(), extra={"side": "defender"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "partial"
    assert body["profile"] is not None
    assert body["unreadable_fields"], "partial results must name the unreadable fields"
    assert "stats" in body["unreadable_fields"]
    assert "per_class.Infantry.tier" in body["unreadable_fields"]


def test_invalid_mock_yields_failed_with_reason():
    client, _ = build_client("synthetic_invalid.json")
    resp = post_image(client, make_png())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["profile"] is None
    assert body["reason"].startswith("validator_rejected")
    assert "casualty identity" in body["reason"]
    assert body["job_id"]  # failures are recorded jobs too


# --- caching ---------------------------------------------------------------

def test_cache_hit_skips_second_vision_call():
    client, vision = build_client("synthetic_valid_type1.json")
    png = make_png()
    first = post_image(client, png).json()
    second = post_image(client, png).json()
    assert vision.calls == 1, "identical image must be served from the hash cache"
    assert second["cached"] is True
    assert first["cached"] is False
    assert second["job_id"] == first["job_id"]
    assert second["status"] == first["status"] == "ok"
    # a DIFFERENT image is a real second job
    third = post_image(client, make_png(color=(99, 0, 0))).json()
    assert vision.calls == 2
    assert third["cached"] is False


# --- rejects ---------------------------------------------------------------

def test_oversized_upload_400():
    client, vision = build_client("synthetic_valid_type1.json")
    resp = post_image(client, b"\x00" * (MAX_IMAGE_BYTES + 1))
    assert resp.status_code == 400
    assert resp.json()["error"] == "image_too_large"
    assert vision.calls == 0, "no vision spend on rejected uploads"


def test_wrong_type_upload_400():
    client, vision = build_client("synthetic_valid_type1.json")
    buf = io.BytesIO()
    Image.new("P", (16, 16)).save(buf, format="GIF")
    resp = post_image(client, buf.getvalue(), filename="anim.gif", content_type="image/gif")
    assert resp.status_code == 400
    assert resp.json()["error"] == "unsupported_image_type"
    assert vision.calls == 0


def test_garbage_upload_400():
    client, _ = build_client("synthetic_valid_type1.json")
    resp = post_image(client, b"not an image at all")
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_image"


def test_invalid_side_400():
    client, _ = build_client("synthetic_valid_type1.json")
    resp = post_image(client, make_png(), extra={"side": "spectator"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_side"


def test_unauthenticated_401():
    client, vision = build_client("synthetic_valid_type1.json")
    resp = post_image(client, make_png(), headers={"x-test-anon": "1"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] == "auth_required"
    assert "sign_in_url" in body
    assert vision.calls == 0


# --- regression: F21 (quota gate was dead code) -----------------------------

def test_free_plan_upload_is_actually_gated_402():
    """Regression for EVAL_ROUND_1.md F21, AMENDED for EVAL_ROUND_2.md C2.

    F21 originally: the router called check_and_record(user, "ocr", ...),
    but limits.classify_endpoint("ocr") normalizes to "/ocr", which is not in
    limits.OCR_ENDPOINTS ({"/shell/ocr", "/shell/ocr/panel"}) — so
    classify_endpoint returned None and check_and_record short-circuited to
    Allowed() unconditionally, before ever checking plan. Passing the correct
    "/shell/ocr" path fixed that call — but it turned out to be a SECOND,
    simultaneously-live metering point on top of shell.app.limits.
    LimitsMiddleware (which main.py's create_app() always wires, and which
    already matched and metered /shell/ocr on its own), doubling quota
    consumption and halving the effective burst budget (C2). The fix deleted
    router.py's own call entirely — LimitsMiddleware is now the ONLY
    metering point for this endpoint, matching panel_router.py's documented
    approach. This test is amended (not deleted, per the C2 remediation
    brief) to assert the 402 via that SURVIVING layer instead of the
    bare-router harness, which no longer has anything in it to produce a
    402 at all: must still be 402 payment_required, and must not spend a
    vision call."""
    client, vision = build_client("synthetic_valid_type1.json", plan="free",
                                  with_limits_middleware=True)
    resp = post_image(client, make_png())
    assert resp.status_code == 402, resp.text
    assert resp.json()["error"] == "payment_required"
    assert vision.calls == 0, "a denied request must not spend a vision call"


def test_free_plan_upload_without_limits_middleware_is_no_longer_gated():
    """Non-regression sanity check for the C2 deletion itself: the bare
    router (no LimitsMiddleware wired) now has NO metering layer at all —
    proving router.py's own check_and_record call is really gone, not just
    silently still there and coincidentally passing. (The real app always
    wires LimitsMiddleware — see test_free_plan_upload_is_actually_gated_402
    above for the behavior that actually matters in production.)"""
    client, vision = build_client("synthetic_valid_type1.json", plan="free")
    resp = post_image(client, make_png())
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"


# --- regression: C2 (double metering via router.py + LimitsMiddleware) -----

def test_two_pro_uploads_record_exactly_two_usage_events():
    """EVAL_ROUND_2.md C2, live-reproduced by the evaluator: with BOTH
    router.py's own (pre-fix) check_and_record call AND LimitsMiddleware
    wired, two successful uploads recorded FOUR usage_events (each request
    metered twice), not two. Against the real app (LimitsMiddleware wired,
    router.py's own call deleted), N successful uploads must record exactly
    N usage_events — checked against the real db store, not a mock."""
    client, vision = build_client("synthetic_valid_type1.json", plan="pro",
                                  with_limits_middleware=True)
    first = post_image(client, make_png(color=(1, 2, 3)))
    second = post_image(client, make_png(color=(4, 5, 6)))
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert vision.calls == 2   # two DIFFERENT images -> no cache hit either
    used = real_db.get_db().usage_events
    assert len([e for e in used if e["clerk_user_id"] == "test_user"
               and e["kind"] == "ocr"]) == 2, (
        "two successful uploads must record exactly 2 usage_events, not 4 "
        "(C2 — router.py must not meter on top of LimitsMiddleware)")


def test_burst_budget_is_not_halved_by_double_metering():
    """EVAL_ROUND_2.md C2 live reproduction, reconstructed exactly: with the
    bug present, a fresh pro account's default 5/min burst budget
    (BURST_PER_MIN) tripped after only 2 successful uploads (0:200, 1:200,
    2:429,429,429,429 — each request consuming 2 of the 5 slots). Post-fix,
    exactly BURST_PER_MIN uploads must succeed before the (N+1)th 429s."""
    from shell.app.billing._contracts import get_settings as get_limits_settings
    burst_cap = int(get_limits_settings().burst_per_min)
    assert burst_cap == 5   # pin the default this test relies on

    client, vision = build_client("synthetic_valid_type1.json", plan="pro",
                                  with_limits_middleware=True)
    statuses = []
    for i in range(burst_cap + 1):
        resp = post_image(client, make_png(color=(i, i, i)))
        statuses.append(resp.status_code)
    assert statuses[:burst_cap] == [200] * burst_cap, statuses
    assert statuses[burst_cap] == 429, statuses
    assert vision.calls == burst_cap, "the denied (burst) request must not spend a vision call"


# --- regression: F2 (job_id/id cache-key mismatch) --------------------------
#
# The lesson (MORNING_BRIEF.md §Resume, Agent C brief): "tests must use the
# app's REAL store" — a fully green suite still shipped a broken app because
# every existing test above injects InMemoryOcrJobs(), whose records always
# carry "job_id". Agent B's real store (Postgres ocr_jobs table AND its
# InMemoryDB keyless fallback) keys the row "id" instead. cache.get_job_store()
# prefers exactly this real store whenever shell.app.db exposes
# get_ocr_job_by_hash/create_ocr_job — i.e. always, in this app. This test
# wires DbOcrJobs to the real shell.app.db module (still keyless: no
# DATABASE_URL means InMemoryDB, but it is the SAME adapter class and row
# shape the app boots with in dev/staging/prod) instead of the test double.

def test_cache_hit_via_real_db_store_no_key_mismatch():
    """Regression for EVAL_ROUND_1.md F2: second upload of the same image
    against the app's real store used to 500 with KeyError('job_id') because
    the row's primary key is "id". Same image twice must be 200/200 with
    exactly one vision call, and the returned job_id must never be empty."""
    real_store = DbOcrJobs(real_db)
    client, vision = build_client(
        "synthetic_valid_type1.json", jobs=real_store, raise_server_exceptions=False
    )
    png = make_png()

    first = post_image(client, png)
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["cached"] is False
    assert first_body["job_id"], "job_id must be present on the first (uncached) response"

    second = post_image(client, png)
    assert second.status_code == 200, second.text  # <- was HTTP 500 pre-fix
    second_body = second.json()

    assert vision.calls == 1, "identical image must be served from the hash cache, not re-OCR'd"
    assert second_body["cached"] is True
    assert second_body["job_id"], "job_id must survive the real store's id-keyed row shape"
    assert second_body["job_id"] == first_body["job_id"]
    assert second_body["status"] == first_body["status"] == "ok"
    assert second_body["profile"] == first_body["profile"]


def test_cache_hit_via_real_db_store_preserves_failed_result():
    """Same regression, failed-job branch: failures are cached too (cost
    control), and the real store's row shape must not corrupt that path."""
    real_store = DbOcrJobs(real_db)
    client, vision = build_client(
        "synthetic_invalid.json", jobs=real_store, raise_server_exceptions=False
    )
    png = make_png()

    first = post_image(client, png)
    assert first.status_code == 200, first.text
    second = post_image(client, png)
    assert second.status_code == 200, second.text

    assert vision.calls == 1
    assert second.json()["job_id"] == first.json()["job_id"]
    assert second.json()["status"] == first.json()["status"] == "failed"


# --- skill-directory-missing -> clean 503, never a bare 500 -----------------

def test_skill_unavailable_returns_503_not_500(monkeypatch):
    """Regression for EVAL_ROUND_1.md F1 (OCR-module half): if the
    wos-battlereport-ingestion skill directory cannot be resolved (deploy
    omitted .claude/, or SKILL_INGESTION_DIR points nowhere), the endpoint
    must fail cleanly with 503 — never an unhandled 500."""
    import shell.app.ocr.extract as extract_module

    # The validator module is cached process-wide after first successful
    # load (by earlier tests in this session) — force a fresh resolution so
    # this test genuinely exercises the "missing" branch instead of hitting
    # the warm cache.
    monkeypatch.setattr(extract_module, "_validator_module", None)

    broken_settings = _StubSettings(skill_ingestion_dir="/definitely/not/a/real/path/xyz")
    client, vision = build_client(
        "synthetic_valid_type1.json", settings=broken_settings,
        raise_server_exceptions=False,
    )
    resp = post_image(client, make_png())
    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["error"] == "skill_unavailable"
    assert "message" in body and body["message"]
    # MockVision.extract() doesn't touch the skill dir (fixture-only), so the
    # (free) mock call still happens; the error surfaces one step later, at
    # the validator stage. A real Anthropic backend needs the skill dir to
    # build the prompt itself, so it fails before spending any API cost —
    # see test_ocr_shims.py for that path in isolation.
    assert vision.calls == 1
