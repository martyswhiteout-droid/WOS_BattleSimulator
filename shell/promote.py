"""shell/promote.py — the gate pipeline (PRODUCTION_PLAN.md §3, steps 1–8).

One repeatable script that turns a tagged prototype release into a gated,
evidence-carrying staging deployment and a DRAFT Gate Report
(PRODUCTION_CRITERIA.md template). Steps 9–11 (independent QA verdict,
Martin's sign-off, promotion to production) are HUMAN gates — this script
automates none of the judgment, only the evidence.

    python shell/promote.py --tag release-2026-08-01 --target staging --dry-run

Steps (each a discrete function, results collected into the draft report):
  1. checkout   — export the tagged artifact (wos_sim + prototype/index.html +
                  avatars manifest) into a build dir; dry-run may fall back to
                  the working tree (recorded as such in the evidence).
  2. checks     — prototype-side: pytest, wos_sim.regression, wos_sim.backtest
                  (subprocess; pass counts captured for A1–A3).
  3. assemble   — bundle = shell source + artifact + assets_prod + env config.
  4. static     — gates: phash blocklist scan (F1), debug-endpoint grep (D4),
                  secret-pattern scan (E4), UTF-8 check of index.html (G2).
  5. docker     — build the image (graceful TODO if docker unavailable).
  6. deploy     — ssh/scp to the target stack (stubbed under --dry-run; the
                  real commands are documented in DEPLOY_COMMANDS).
  7. probes     — run shell/probes/run_probes.py against the deployed base URL
                  (skipped with instructions when nothing is deployed).
  8. report     — emit the DRAFT Gate Report with machine evidence filled in.

════════════════════════════════════════════════════════════════════════════
HARD RULE (COMPASS invariant 4; PRODUCTION_CRITERIA gatekeeper rule):

  promote.py NEVER writes to E:\\WOS\\WOSTests.com, and NEVER deploys to the
  prod target, unless BOTH of the following are supplied:
    --gate-report PATH   → a completed Gate Report whose verdict line is
                           exactly "VERDICT: PASS" (an independent QA agent's
                           report — CONDITIONAL or FAIL keeps the door shut)
    --martin-signoff "yes-I-approve"
  The default is REFUSAL (exit 3). The draft report this script emits can
  never satisfy the check: it is emitted with a DRAFT verdict, by design.
  Even when both gates are satisfied, this version performs no writes into
  WOSTests.com itself — it prints the exact archive commands for the release
  operator (a write-path guard raises on any attempt).
════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

SHELL_DIR = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = SHELL_DIR.parent
DEFAULT_BLOCKLIST = SHELL_DIR / "tools" / "blocklist.json"

# EVAL_ROUND_1.md F1: shell/app/ocr/extract.py's VALIDATOR_PATH and
# shell/app/ocr/vision.py's SCHEMA_MD_PATH both resolve here at runtime and
# hard-fail (FileNotFoundError, every request) if it is missing. Posix-style
# string for `git archive` pathspecs; Path() joins work with it unchanged on
# Windows (pathlib splits on "/" regardless of platform).
INGESTION_SKILL_DIR = ".claude/skills/wos-battlereport-ingestion"
INGESTION_SKILL_VALIDATOR_REL = f"{INGESTION_SKILL_DIR}/scripts/validate_report.py"
INGESTION_SKILL_SCHEMA_REL = f"{INGESTION_SKILL_DIR}/references/schema.md"

SIGNOFF_PHRASE = "yes-I-approve"
PASS_VERDICT_RE = re.compile(r"^VERDICT:\s*PASS\s*$", re.MULTILINE)
FORBIDDEN_WRITE_MARKER = "wostests.com"   # the production folder, any casing
DRAFT_VERDICT = ("DRAFT — machine evidence only; awaiting independent QA "
                 "agent (steps 9–10). Do NOT ship on this draft.")

# Files/dirs of the shell source that belong in a release bundle. Pipeline-side
# tooling (this script, probes, tests, phash tool, build output) does not ship.
#
# Mn4 (EVAL_ROUND_2.md): "tests" here is a DELIBERATE exclusion, not an
# oversight — reviewed and kept. Test code (fixtures, mocks, dev-only
# helpers) has no business on a production host; MockVision's FIXTURE_DIR
# (shell/tests/fixtures/ocr/) would go missing from THIS bundle if a
# deployment ever ran with OCR_MOCK=1 left on, but this scp/VPS bundle is a
# SECONDARY deploy path — the primary one (shell/Dockerfile, confirmed by
# docker-compose.yml's healthcheck/restart-policy/TLS-sidecar) does an
# unconditional `COPY shell/ shell/`, so it ships tests/ (and the fixtures)
# regardless. step3_assemble's own evidence string calls this exclusion out
# explicitly so a gate reviewer sees it documented, not silently absent.
BUNDLE_EXCLUDE_DIRS = {"build", "tests", "probes", "tools", "__pycache__",
                       ".pytest_cache", ".mypy_cache"}
BUNDLE_EXCLUDE_FILES = {"promote.py", ".env", "BUILD_LOG.md"}

SECRET_PATTERNS = [
    ("anthropic/openai key", re.compile(r"sk-[A-Za-z0-9_\-]{16,}")),
    ("stripe secret key", re.compile(r"[sr]k_(?:live|test)_[A-Za-z0-9]{10,}")),
    ("stripe webhook secret", re.compile(r"whsec_[A-Za-z0-9]{10,}")),
    ("supabase service_role value",
     re.compile(r"service_role[\"']?\s*[:=]\s*[\"'][A-Za-z0-9._\-]{20,}")),
    ("JWT token", re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.eyJ[A-Za-z0-9_\-]{10,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github token", re.compile(r"ghp_[A-Za-z0-9]{30,}")),
    ("slack token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("db url with password",
     re.compile(r"postgres(?:ql)?://[^\s\"']+:[^\s\"'@]{8,}@")),
]
SECRET_ALLOWLIST_SUBSTRINGS = ("example", "placeholder", "your_", "your-",
                               "changeme", "redacted", "xxxx", "dummy")
SECRET_SKIP_FILENAMES = {".env.example"}

DEBUG_PATTERNS = [
    re.compile(r"/api/debug"), re.compile(r"/shell/debug"),
    re.compile(r"/__debug__"), re.compile(r"debug=True"),
    re.compile(r"\bset_trace\("), re.compile(r"\bbreakpoint\("),
]
TEXT_EXTS = {".py", ".html", ".js", ".css", ".json", ".md", ".txt", ".env",
             ".yml", ".yaml", ".toml", ".cfg", ".ini", ".sql", ".example",
             ".pem", ".key", ".crt", ".sh"}

DEPLOY_COMMANDS = """\
# Real deploy commands (run by the operator from a machine with the deploy key;
# secrets live ONLY in the VPS env — never in this repo or bundle):
docker save wostests-shell:{tag} | gzip | ssh deploy@{host} 'gunzip | docker load'
ssh deploy@{host} 'mkdir -p /opt/wostests/{target}'
scp {bundle}/config/{target}.env deploy@{host}:/opt/wostests/{target}/.env.template
#   (operator merges real secrets into /opt/wostests/{target}/.env on the VPS)
ssh deploy@{host} 'cd /opt/wostests/{target} && TAG={tag} docker compose up -d && docker compose ps'
"""

ARCHIVE_COMMANDS = """\
# Step 11 (HUMAN, after QA PASS + Martin sign-off — see PRODUCTION_CRITERIA):
#   copy the release artifacts + gate report into E:\\WOS\\WOSTests.com and
#   append PRODUCTION_LOG.md there. promote.py never performs these writes.
"""


class PromoteRefusal(Exception):
    """Raised when the production gate refuses. Exit code 3."""


@dataclass
class StepResult:
    name: str
    status: str            # PASS | FAIL | SKIP | TODO
    evidence: str = ""
    required: bool = True  # FAIL on a required step fails the pipeline

    @property
    def failed(self) -> bool:
        return self.required and self.status == "FAIL"


@dataclass
class Pipeline:
    tag: str
    target: str
    repo_root: Path
    build_root: Path
    dry_run: bool
    results: list[StepResult] = field(default_factory=list)
    backtest_count: str = "n/a"
    probe_markdown: str = ""

    @property
    def build_dir(self) -> Path:
        return self.build_root / self.tag

    @property
    def artifact_dir(self) -> Path:
        return self.build_dir / "artifact"

    @property
    def bundle_dir(self) -> Path:
        return self.build_dir / "bundle"


# ---------------------------------------------------------------- guards

def assert_safe_write_path(path: Path | str) -> Path:
    """HARD guard: promote.py never writes inside the production folder."""
    rp = Path(path).resolve()
    if FORBIDDEN_WRITE_MARKER in str(rp).lower():
        raise PromoteRefusal(
            f"REFUSED: write path {rp} is inside the production folder "
            f"(WOSTests.com). promote.py never writes there — production "
            f"archiving is a human step after QA PASS + Martin sign-off.")
    return rp


def enforce_prod_gate(target: str, gate_report: Path | None,
                      signoff: str | None) -> None:
    """The prod door. Default = refuse; only a completed PASS gate report plus
    Martin's literal sign-off phrase opens it. See module docstring HARD RULE."""
    if target != "prod":
        return
    problems = []
    if gate_report is None:
        problems.append("--gate-report PATH is required for --target prod "
                        "(an independent QA agent's completed report)")
    else:
        if not gate_report.is_file():
            problems.append(f"gate report not found: {gate_report}")
        else:
            text = gate_report.read_text(encoding="utf-8", errors="replace")
            if not PASS_VERDICT_RE.search(text):
                problems.append(
                    "gate report does not contain a line 'VERDICT: PASS' — "
                    "CONDITIONAL or FAIL (or promote.py's own DRAFT) keeps "
                    "the door shut (PRODUCTION_CRITERIA: CONDITIONAL is a "
                    "polite FAIL)")
    if signoff != SIGNOFF_PHRASE:
        problems.append(f"--martin-signoff \"{SIGNOFF_PHRASE}\" is required "
                        "for --target prod (explicit, not inferred — "
                        "PRODUCTION_CRITERIA I2)")
    if problems:
        raise PromoteRefusal("REFUSED: production promotion blocked:\n  - "
                             + "\n  - ".join(problems))


# ---------------------------------------------------------------- helpers

def _python_cmd() -> list[str]:
    """Interpreter for subprocess checks. On Windows dev boxes `py -m` is the
    documented launcher (TOOLS.md); from inside a venv/sandbox sys.executable
    is the same thing, and portable."""
    return [sys.executable, "-m"]


def _run(cmd: list[str], cwd: Path, timeout: int = 2400):
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return 127, str(e)


def _copytree(src: Path, dst: Path, exclude_dirs=frozenset(),
              exclude_files=frozenset()):
    def ignore(directory, names):
        out = set()
        for n in names:
            if n in exclude_dirs or n.endswith(".pyc"):
                out.add(n)
            if n in exclude_files:
                out.add(n)
        return out
    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)


def _tail(text: str, lines: int = 6) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


# ---------------------------------------------------------------- steps 1–8

def _archive_extra_path(pl: Pipeline, rel_path: str) -> bool:
    """Best-effort: extract one extra path from the tag into artifact_dir, on
    top of the main archive already extracted by step1_checkout. A missing
    path here is NOT a step1 failure — it surfaces instead as a step4
    completeness-gate FAIL (F1), the actionable signal ("the release doesn't
    carry a required directory") rather than a checkout-step crash on what
    might be an old tag predating the requirement."""
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tf:
        tar_path = Path(tf.name)
    try:
        p = subprocess.run(["git", "-C", str(pl.repo_root), "archive",
                            "--format=tar", "-o", str(tar_path), pl.tag,
                            "--", rel_path],
                           capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            return False
        with tarfile.open(tar_path) as t:
            t.extractall(pl.artifact_dir)
        return True
    except (OSError, subprocess.SubprocessError, tarfile.TarError):
        return False
    finally:
        tar_path.unlink(missing_ok=True)


def step1_checkout(pl: Pipeline) -> StepResult:
    """Step 1–2 of the plan: pull the tagged artifact into the build dir."""
    assert_safe_write_path(pl.artifact_dir)
    if pl.artifact_dir.exists():
        shutil.rmtree(pl.artifact_dir)
    pl.artifact_dir.mkdir(parents=True)
    paths = ["wos_sim", "prototype/index.html", "prototype/avatars/manifest.json"]
    rc, out = _run(["git", "-C", str(pl.repo_root), "rev-parse", "--verify",
                    f"{pl.tag}^{{commit}}"], cwd=pl.repo_root, timeout=60)
    if rc == 0:
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tf:
            tar_path = Path(tf.name)
        try:
            p = subprocess.run(["git", "-C", str(pl.repo_root), "archive",
                                "--format=tar", "-o", str(tar_path), pl.tag,
                                "--"] + paths,
                               capture_output=True, text=True, timeout=300)
            if p.returncode != 0:
                return StepResult("1 checkout", "FAIL",
                                  f"git archive {pl.tag} failed: {p.stderr[:400]}")
            with tarfile.open(tar_path) as t:
                t.extractall(pl.artifact_dir)
        finally:
            tar_path.unlink(missing_ok=True)
        skill_ok = _archive_extra_path(pl, INGESTION_SKILL_DIR)
        n = sum(1 for f in pl.artifact_dir.rglob("*") if f.is_file())
        skill_note = "ingestion skill included" if skill_ok else (
            "ingestion skill NOT found at this tag — step 4's completeness "
            "gate (F1) will FAIL")
        return StepResult("1 checkout", "PASS",
                          f"git archive of tag `{pl.tag}` -> "
                          f"{n} files (clean tagged tree, H2) · {skill_note}")
    if not pl.dry_run:
        return StepResult("1 checkout", "FAIL",
                          f"tag `{pl.tag}` not found in {pl.repo_root} — a "
                          "release must be a clean tagged commit (H2). "
                          "Working-tree fallback is allowed only with --dry-run.")
    # dry-run fallback: working tree (explicitly recorded as NOT release-grade)
    _copytree(pl.repo_root / "wos_sim", pl.artifact_dir / "wos_sim",
              exclude_dirs={"__pycache__", ".pytest_cache"})
    (pl.artifact_dir / "prototype").mkdir(parents=True, exist_ok=True)
    shutil.copy2(pl.repo_root / "prototype" / "index.html",
                 pl.artifact_dir / "prototype" / "index.html")
    av = pl.repo_root / "prototype" / "avatars" / "manifest.json"
    if av.is_file():
        (pl.artifact_dir / "prototype" / "avatars").mkdir(parents=True,
                                                          exist_ok=True)
        shutil.copy2(av, pl.artifact_dir / "prototype" / "avatars" /
                     "manifest.json")
    skill_src = pl.repo_root / INGESTION_SKILL_DIR
    skill_ok = skill_src.is_dir()
    if skill_ok:
        _copytree(skill_src, pl.artifact_dir / INGESTION_SKILL_DIR,
                  exclude_dirs={"__pycache__"})
    skill_note = "ingestion skill included" if skill_ok else (
        "ingestion skill NOT found in the working tree — step 4's "
        "completeness gate (F1) will FAIL")
    n = sum(1 for f in pl.artifact_dir.rglob("*") if f.is_file())
    # F20: this is a working-tree fallback, not a release-grade checkout —
    # SKIP (not PASS) so the gate report cannot be skim-read as "H: PASS".
    return StepResult("1 checkout", "SKIP",
                      f"tag `{pl.tag}` not found; DRY-RUN fallback copied the "
                      f"WORKING TREE ({n} files). NOT release-grade evidence "
                      f"for H2 — tag the release before a real promotion. · "
                      f"{skill_note}", required=False)


def step2_prototype_checks(pl: Pipeline, skip: bool) -> StepResult:
    """pytest ▸ wos_sim.regression ▸ wos_sim.backtest (A1–A3)."""
    if skip:
        return StepResult(
            "2 prototype checks", "SKIP",
            "SKIPPED via --skip-prototype-checks (dev/dry-run only; a real "
            "promotion must run pytest + regression + backtest, A1–A3)",
            required=False)
    py = _python_cmd()
    evidence = []
    ok = True
    rc, out = _run(py + ["pytest", "-q"], cwd=pl.repo_root)
    m = re.search(r"(\d+) passed", out)
    evidence.append(f"pytest: rc={rc} ({m.group(0) if m else 'no summary'}) | "
                    f"{_tail(out, 2)}")
    ok &= rc == 0
    rc, out = _run(py + ["wos_sim.regression"], cwd=pl.repo_root)
    evidence.append(f"regression: rc={rc} | {_tail(out, 2)}")
    ok &= rc == 0
    rc, out = _run(py + ["wos_sim.backtest"], cwd=pl.repo_root)
    counts = re.search(r"(\d+)\s*/\s*(\d+)", out)
    pl.backtest_count = counts.group(0) if counts else f"rc={rc} (unparsed)"
    evidence.append(f"backtest: rc={rc} pass count={pl.backtest_count} | "
                    f"{_tail(out, 3)}")
    ok &= rc == 0
    return StepResult("2 prototype checks", "PASS" if ok else "FAIL",
                      "\n".join(evidence))


def step3_assemble(pl: Pipeline) -> StepResult:
    """Bundle = shell source + tagged artifact + assets_prod + env config."""
    assert_safe_write_path(pl.bundle_dir)
    if pl.bundle_dir.exists():
        shutil.rmtree(pl.bundle_dir)
    pl.bundle_dir.mkdir(parents=True)
    # shell source (runtime parts only — pipeline tooling excluded)
    _copytree(SHELL_DIR, pl.bundle_dir / "shell",
              exclude_dirs=BUNDLE_EXCLUDE_DIRS,
              exclude_files=BUNDLE_EXCLUDE_FILES)
    # artifact
    _copytree(pl.artifact_dir, pl.bundle_dir)
    # asset swap (PRODUCTION_PLAN §2.5): the prototype's scraped raster art
    # (hero avatars, skill icons — Century Games IP) never ships. Strip ALL
    # raster images from the artifact portions of the bundle; production art
    # is the original SVG pack in shell/assets_prod + hero names as text.
    # The phash gate (step 4) then verifies nothing slipped through.
    raster_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
    stripped = 0
    for sub in ("wos_sim", "prototype"):
        base = pl.bundle_dir / sub
        if base.is_dir():
            for p in base.rglob("*"):
                if p.is_file() and p.suffix.lower() in raster_exts:
                    p.unlink()
                    stripped += 1
    # env config stub (no secrets; real values live only on the VPS)
    cfg = pl.bundle_dir / "config"
    cfg.mkdir(exist_ok=True)
    env_example = SHELL_DIR / ".env.example"
    base = env_example.read_text(encoding="utf-8") if env_example.is_file() \
        else "# see shell/.env.example (Agent A)\n"
    (cfg / f"{pl.target}.env").write_text(
        f"# {pl.target} config TEMPLATE — generated by promote.py; "
        f"secrets are injected on the VPS, never stored here\n"
        f"ENV={pl.target}\nDEV_BYPASS=0\nMIN_TROOPS_PER_SIDE=5000\n" + base,
        encoding="utf-8")
    n = sum(1 for f in pl.bundle_dir.rglob("*") if f.is_file())
    has_assets = (pl.bundle_dir / "shell" / "assets_prod" /
                  "manifest.json").is_file()
    return StepResult("3 assemble", "PASS" if has_assets else "FAIL",
                      f"bundle: {n} files at {pl.bundle_dir} · asset swap "
                      f"stripped {stripped} raster images from the artifact "
                      f"(scraped art never ships, F1) · assets_prod manifest "
                      f"{'present' if has_assets else 'MISSING'} · "
                      f"config/{pl.target}.env written (template, no secrets) · "
                      f"shell/tests/ EXCLUDED from this bundle (INTENDED, "
                      f"Mn4 EVAL_ROUND_2.md — test code/fixtures don't ship; "
                      f"the primary Docker deploy path ships them via "
                      f"Dockerfile's unconditional COPY shell/ shell/, this "
                      f"scp bundle is the secondary path only)")


# -- step 4 static gates (each returns findings; empty list = clean) ---------

def gate_phash(bundle: Path, blocklist: Path, max_distance: int = 6) -> list[str]:
    if not blocklist.is_file():
        return [f"blocklist missing: {blocklist} — run "
                "`python shell/tools/phash_blocklist.py build ...` first"]
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "wos_shell_phash_blocklist", SHELL_DIR / "tools" / "phash_blocklist.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    res = mod.scan_bundle(bundle, blocklist, max_distance)
    # Only violations fail the gate; unreadable-image warnings ride along as
    # context when there IS a violation, and are dropped when clean.
    if not res["violations"]:
        return []
    findings = [f"BLOCKLISTED IMAGE in bundle: {v['file']} "
                f"(distance {v['distance']} vs {v['matches']})"
                for v in res["violations"]]
    findings += [f"warning: {w}" for w in res["warnings"]]
    return findings


def _iter_text_files(bundle: Path):
    for p in sorted(bundle.rglob("*")):
        if not p.is_file():
            continue
        # F26: extension-less files (id_rsa, a bare "Dockerfile"-style name,
        # etc.) used to be invisible to both the secret and debug scans even
        # though the secret patterns (e.g. "-----BEGIN ... PRIVATE KEY-----")
        # are ready for them. Scan them too — read_text below already
        # tolerates binary noise via errors="ignore".
        if (p.suffix.lower() in TEXT_EXTS or p.suffix == ""
                or p.name in SECRET_SKIP_FILENAMES):
            yield p


def gate_ingestion_skill(bundle: Path) -> list[str]:
    """EVAL_ROUND_1.md F1: shell/app/ocr/extract.py's VALIDATOR_PATH and
    shell/app/ocr/vision.py's SCHEMA_MD_PATH both resolve to files inside
    .claude/skills/wos-battlereport-ingestion/ at runtime and hard-fail
    (FileNotFoundError) on every request when absent — reproduced live in the
    eval as an HTTP 500 on every OCR upload in the actual deploy layout. This
    is a completeness ASSERT, not just a presence check: both files the app
    code actually opens must exist in the bundle, not merely the directory."""
    findings = []
    validator = bundle / INGESTION_SKILL_VALIDATOR_REL
    schema = bundle / INGESTION_SKILL_SCHEMA_REL
    if not validator.is_file():
        findings.append(
            f"missing ingestion-skill validator: {validator} — "
            "shell/app/ocr/extract.py:VALIDATOR_PATH will raise "
            "FileNotFoundError on every /shell/ocr request (EVAL F1)")
    if not schema.is_file():
        findings.append(
            f"missing ingestion-skill schema doc: {schema} — "
            "shell/app/ocr/vision.py:SCHEMA_MD_PATH will raise "
            "FileNotFoundError on every real-key OCR extraction (EVAL F1)")
    return findings


def gate_debug_endpoints(bundle: Path) -> list[str]:
    findings = []
    for p in _iter_text_files(bundle):
        # Documentation may legitimately DISCUSS debug patterns (e.g. the eval
        # report that flagged F5 quotes them); the D4 gate hunts live endpoints
        # in CODE/config only. Secrets gate still scans .md.
        if p.suffix.lower() == ".md":
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in DEBUG_PATTERNS:
            for m in pat.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                findings.append(f"debug pattern `{pat.pattern}` in "
                                f"{p.relative_to(bundle)}:{line}")
    return findings


def gate_secret_scan(bundle: Path) -> list[str]:
    findings = []
    for p in _iter_text_files(bundle):
        if p.name in SECRET_SKIP_FILENAMES:
            continue  # placeholder file by definition; still shipped keyless
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pat in SECRET_PATTERNS:
            for m in pat.finditer(text):
                token = m.group(0)
                if any(s in token.lower() for s in SECRET_ALLOWLIST_SUBSTRINGS):
                    continue
                line = text.count("\n", 0, m.start()) + 1
                findings.append(f"possible {label} in "
                                f"{p.relative_to(bundle)}:{line} "
                                f"({token[:12]}…)")
    return findings


def gate_utf8_index(bundle: Path) -> list[str]:
    idx = bundle / "prototype" / "index.html"
    if not idx.is_file():
        return [f"prototype/index.html missing from bundle at {idx}"]
    try:
        idx.read_bytes().decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        return [f"prototype/index.html is not valid UTF-8: {e}"]
    return []


def step4_static_gates(pl: Pipeline, blocklist: Path,
                       max_distance: int) -> StepResult:
    gates = {
        "phash blocklist (F1)": gate_phash(pl.bundle_dir, blocklist,
                                           max_distance),
        "ingestion skill bundle (EVAL F1)": gate_ingestion_skill(pl.bundle_dir),
        "debug endpoints (D4)": gate_debug_endpoints(pl.bundle_dir),
        "secret scan (E4)": gate_secret_scan(pl.bundle_dir),
        "UTF-8 index.html (G2)": gate_utf8_index(pl.bundle_dir),
    }
    lines, ok = [], True
    for name, findings in gates.items():
        if findings:
            ok = False
            lines.append(f"{name}: FAIL")
            lines += [f"    {f}" for f in findings[:20]]
        else:
            lines.append(f"{name}: clean")
    return StepResult("4 static gates", "PASS" if ok else "FAIL",
                      "\n".join(lines))


def step5_docker_build(pl: Pipeline) -> StepResult:
    image = f"wostests-shell:{pl.tag}"
    dockerfile = pl.bundle_dir / "shell" / "Dockerfile"
    cmd = (f"docker build -t {image} -f {dockerfile} {pl.bundle_dir}")
    if shutil.which("docker") is None:
        return StepResult("5 docker build", "TODO",
                          f"docker unavailable in this environment — run "
                          f"manually before deploy: `{cmd}`", required=False)
    if not dockerfile.is_file():
        return StepResult("5 docker build", "TODO",
                          f"shell/Dockerfile not in bundle (Agent A "
                          f"deliverable) — once present: `{cmd}`",
                          required=False)
    if pl.dry_run:
        return StepResult("5 docker build", "SKIP",
                          f"dry-run — would run: `{cmd}`", required=False)
    rc, out = _run(cmd.split(), cwd=pl.repo_root, timeout=1800)
    return StepResult("5 docker build", "PASS" if rc == 0 else "FAIL",
                      f"`{cmd}` rc={rc}\n{_tail(out, 5)}")


def step6_deploy(pl: Pipeline, host: str | None) -> StepResult:
    cmds = DEPLOY_COMMANDS.format(tag=pl.tag, target=pl.target,
                                  host=host or "<VPS_HOST>",
                                  bundle=pl.bundle_dir)
    if pl.target == "prod":
        cmds += ARCHIVE_COMMANDS
    if pl.dry_run or not host:
        why = "dry-run" if pl.dry_run else "no --deploy-host configured"
        return StepResult(f"6 deploy ({pl.target})", "SKIP",
                          f"{why} — real commands documented:\n{cmds}",
                          required=False)
    ok = True
    outs = []
    for line in [l for l in cmds.splitlines()
                 if l and not l.startswith("#")]:
        rc, out = _run(["bash", "-lc", line], cwd=pl.repo_root, timeout=900)
        outs.append(f"$ {line}\nrc={rc} {_tail(out, 2)}")
        ok &= rc == 0
        if not ok:
            break
    return StepResult(f"6 deploy ({pl.target})", "PASS" if ok else "FAIL",
                      "\n".join(outs))


def step7_probes(pl: Pipeline, base_url: str | None) -> StepResult:
    runner = SHELL_DIR / "probes" / "run_probes.py"
    if pl.dry_run or not base_url:
        why = "dry-run" if pl.dry_run else "no --probe-base-url given"
        return StepResult(
            "7 staging probes", "SKIP",
            f"{why} — run after deploy: `python {runner} --base "
            f"https://staging.wostests.com` (C1/D1/D2/§2.4/B2-E2 evidence)",
            required=False)
    out_md = pl.build_dir / "probe_report.md"
    assert_safe_write_path(out_md)
    rc, out = _run([sys.executable, str(runner), "--base", base_url,
                    "--out", str(out_md)], cwd=pl.repo_root, timeout=600)
    pl.probe_markdown = out_md.read_text(encoding="utf-8") \
        if out_md.is_file() else out
    return StepResult("7 staging probes", "PASS" if rc == 0 else "FAIL",
                      f"run_probes rc={rc} (0=all pass) — full table in "
                      f"{out_md}\n{_tail(out, 4)}")


def step8_gate_report(pl: Pipeline) -> Path:
    """Emit the DRAFT Gate Report (PRODUCTION_CRITERIA template) with machine
    evidence filled in. The verdict is ALWAYS a draft — only an independent QA
    agent may write 'VERDICT: PASS' (into their own copy, not this file)."""
    by_name = {r.name: r for r in pl.results}

    def ev(step: str, default: str = "not run") -> str:
        r = by_name.get(step)
        if r is None:
            return default
        first = r.evidence.splitlines()[0] if r.evidence else ""
        return f"{r.status} — {first}"

    checks = by_name.get("2 prototype checks")
    if checks and checks.status == "PASS":
        a1 = a2 = "PASS (see step 2 evidence)"
    elif checks and checks.status == "SKIP":
        a1 = a2 = "NOT RUN (--skip-prototype-checks; rerun for a real gate)"
    else:
        a1 = a2 = "FAIL (see step 2 evidence)"

    static = by_name.get("4 static gates")
    static_ev = static.evidence.replace("\n", "\n      ") if static else "n/a"
    detail = "\n".join(
        f"### Step {r.name}\nStatus: {r.status}\n```\n{r.evidence}\n```\n"
        for r in pl.results)
    probes_md = pl.probe_markdown or "(probes not run — see step 7)"

    report = f"""# PRODUCTION GATE REPORT
Date:            {time.strftime('%Y-%m-%d')}
Release tag:     {pl.tag}
QA agent:        PENDING — independent QA agent required (this DRAFT was
                 emitted by shell/promote.py, the builder pipeline; it cannot
                 issue a verdict — PRODUCTION_CRITERIA gatekeeper rule)
Scope shipped:   PENDING QA — one paragraph, written by the QA agent.

Evidence:
  A1 pytest:            {a1}
  A2 regression:        {a2}
  A3 backtest count:    {pl.backtest_count} vs baseline <QA: fill from
                        ENGINE_REBUILD/03_QA_CALIBRATION.md gate G12>
  A4 no-fudge:          PENDING QA (human judgment: params diff review)
  A5 honesty:           PENDING QA (coin_flip labels, engine_meta, badges)
  B  data model:        PARTIAL — adversarial payload probes below (B2);
                        schema_version/migration checks PENDING QA
  C  paywall/auth:      {ev('7 staging probes')}
  D  anti-distillation: {ev('7 staging probes')} (min-troops, burst; sweep-flag
                        test PENDING QA)
  E  security/pentest:  static gates below; pip-audit + pentest PENDING QA
      {static_ev}
  F  IP/legal:          phash scan above (F1 machine check); asset audit,
                        disclaimer + ToS/Privacy live-check PENDING QA
  G  product/UX:        PENDING QA
  H  docs/tag:          {ev('1 checkout')}

Waivers granted by Martin (item, date, wording): none
VERDICT: {DRAFT_VERDICT}
Rationale (3 lines max): Machine evidence gathered by promote.py steps 1–8.
Steps 9 (independent QA verdict) and 10 (Martin sign-off) are open.

---

## Probe evidence

{probes_md}

## Pipeline step detail

{detail}
"""
    out = pl.build_dir / f"GATE_REPORT_DRAFT_{pl.tag}.md"
    assert_safe_write_path(out)
    out.write_text(report, encoding="utf-8")
    return out


# ---------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="promote.py",
        description="WoS Battle Simulator gate pipeline (PRODUCTION_PLAN §3 "
                    "steps 1–8). Default target: staging. Production requires "
                    "a PASS gate report AND Martin's sign-off phrase.")
    ap.add_argument("--tag", required=True, help="release tag, e.g. "
                    "release-2026-08-01")
    ap.add_argument("--target", choices=["staging", "prod"], default="staging")
    ap.add_argument("--dry-run", action="store_true",
                    help="no deploy; working-tree checkout fallback allowed")
    ap.add_argument("--gate-report", type=Path, default=None,
                    help="completed Gate Report with 'VERDICT: PASS' "
                    "(required for --target prod)")
    ap.add_argument("--martin-signoff", default=None,
                    help=f'must be exactly "{SIGNOFF_PHRASE}" for prod')
    ap.add_argument("--skip-prototype-checks", action="store_true",
                    help="dev/dry-run only; refused for --target prod")
    ap.add_argument("--probe-base-url", default=None)
    ap.add_argument("--deploy-host", default=None,
                    help="ssh host for step 6 (omit = stubbed)")
    ap.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    ap.add_argument("--build-root", type=Path,
                    default=SHELL_DIR / "build")
    ap.add_argument("--blocklist", type=Path, default=DEFAULT_BLOCKLIST)
    ap.add_argument("--max-phash-distance", type=int, default=6)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        # The prod door is checked FIRST — before any work happens.
        enforce_prod_gate(args.target, args.gate_report, args.martin_signoff)
        if args.target == "prod" and args.skip_prototype_checks:
            raise PromoteRefusal("REFUSED: --skip-prototype-checks is not "
                                 "allowed for --target prod (A1–A3 are gate "
                                 "items, not suggestions).")
        if args.target == "prod" and args.dry_run is False and \
                args.deploy_host is None:
            print("note: prod gates satisfied but no --deploy-host; deploy "
                  "commands will be printed, not executed.")

        pl = Pipeline(tag=args.tag, target=args.target,
                      repo_root=args.repo_root.resolve(),
                      build_root=assert_safe_write_path(args.build_root),
                      dry_run=args.dry_run)
        pl.build_dir.mkdir(parents=True, exist_ok=True)

        pl.results.append(step1_checkout(pl))
        if pl.results[-1].failed:
            return _finish(pl)
        pl.results.append(step2_prototype_checks(
            pl, skip=args.skip_prototype_checks))
        pl.results.append(step3_assemble(pl))
        pl.results.append(step4_static_gates(pl, args.blocklist,
                                             args.max_phash_distance))
        pl.results.append(step5_docker_build(pl))
        pl.results.append(step6_deploy(pl, args.deploy_host))
        pl.results.append(step7_probes(pl, args.probe_base_url))
        return _finish(pl)
    except PromoteRefusal as e:
        print(str(e), file=sys.stderr)
        return 3


def _finish(pl: Pipeline) -> int:
    report_path = step8_gate_report(pl)
    print(f"\n{'=' * 70}")
    for r in pl.results:
        print(f"  [{r.status:>4}] step {r.name}")
    print(f"{'=' * 70}\nDraft gate report: {report_path}")
    print("Next (human) steps: 9) independent QA agent completes the report "
          "and issues a verdict; 10) Martin signs off; 11) only then may a "
          "release enter WOSTests.com.")
    failed = [r for r in pl.results if r.failed]
    if failed:
        print(f"PIPELINE FAIL: {', '.join(r.name for r in failed)}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
