# OCR Panel Build — QA Round 1 Report (independent, pre-merge)

> Verbatim report of the independent QA agent (fresh context, non-builder model), executed against
> `docs/plans/2026-08-07-ocr-qa-round1-charter.md`. Coordinator triage + fix-round rulings are at the bottom.

**Branch:** `ocr-panel-build` · **HEAD:** `24a6c92` · **Baseline:** `e2417ef` · **Date:** 2026-08-07
**Fresh-run results (run twice, clean shell):** `py -m pytest shell/tests -q` → 187 passed. Node suites → 10 pass. Style guard → 7 passed. QA modified nothing.

## Defects

### DEFECT-001 [Critical] — Row-drift silently reports one stat's number under a different stat's label
`rows.py:17` groups tokens by `abs(cy - cur_y) <= 0.6*h`; a value token drifting ~half a row joins the PREVIOUS label's group and is emitted confidently under the wrong key while the true owner is marked unreadable. Evidence: `Infantry Attack@0.100` (no value) + `Infantry Defense@0.150` + `3979.1%@0.115` → `stats={'Infantry|Attack': 3979.1}`, `unreadable=['stats.Infantry|Defense']`. Blocks merge: YES.

### DEFECT-002 [Critical] — `col_conflict` raised then ignored; battle columns can be silently swapped
`service.py` tests `"conflict" in r.flags` (exact membership) which never matches `"col_conflict"`. A 12-row battle panel with color contradicting geometry everywhere → `status=ok`, all values attributed by color, zero warnings. Blocks merge: YES.

### DEFECT-003 [Critical] — A third screenshot erases an already-detected conflict
`stitch.py`: the conflicted row has `value=None`, so the next shot's plain row replaces it (the "cur.value is None" branch). Shots 4491.6 / 4431.6 / 1111.1 → 2 shots correct (conflict, absent); 3 shots → `stats={'Infantry|Attack': 1111.1}` clean. Plan rule was "keep NEITHER". Blocks merge: YES.

### DEFECT-004 [Critical] — `specials[]` bypasses every confidence/conflict/missing check
Specials are built with only `value is not None` — a conf-0.05 pet-buff row enters `specials` (and would multiply into every converted stat); a value-less special vanishes from both `specials` and `unreadable_fields`. Blocks merge: YES.

### DEFECT-005 [Critical] — Empty/unread specials silently turn battle→scout conversion into identity
`fold_sets([], [])` → all-zero → conversion returns battle numbers unchanged; nothing distinguishes "account has no specials" (real: account B enemy) from "special panel not captured/read". Worst silent error measured: 367.4 pp. Blocks merge: YES.

### DEFECT-006 [Major] — `unreadable_fields` incomplete: never-seen fields listed nowhere
`_bucket` reports only fields it saw; `service.py` computes the `missing` set and DISCARDS it. Battle panel missing its whole right column → `unreadable_fields=[]`. Blocks merge: YES.

### DEFECT-007 [Major] — Uploads >1 MiB spool to disk before ANY gate (auth/plan/size/sniff)
Starlette `spool_max_size=1 MiB`: a 6 MiB post hits disk on every rejection path incl. 401. Files are deleted at request end (not durably persisted) but the "in-memory only" claim is currently false and unauthenticated callers trigger writes. Blocks merge: No.

### DEFECT-008 [Major] — No plausibility/range validation anywhere
QA_PLAN §3 P7 + formula doc §8 specify 0–6000 (class rows) / penalty bands; nothing implements them: `-4491.6%`, `999999999%` → `status=ok`. (Absent from the TDD plan too — spec gap, not builder divergence.) Blocks merge: No.

### DEFECT-009 [Major] — Python (unicode `\d`) and JS (ASCII `\d`) disagree on non-ASCII digits
`٤٤٩١%` parses server-side, refuses client-side → same screenshot yields different rows per path. Fix: `re.ASCII`. Blocks merge: No.

### DEFECT-010 [Major] — Mock responses indistinguishable from real extractions
`OCR_PANEL_MOCK=1` returns hardcoded stats with no `source` marker, any env. Blocks merge: No.

### DEFECT-011 [Major] — `side` accepted, validated… and discarded (JS: literal `void sideHint`)
Battle output is pure geometry (`stats_left/right`); caller can't tell which column is theirs. Blocks merge: No.

### DEFECT-012 [Major] — `panel` hint OVERRIDES detection; forced mismatches produce incoherent output
City-Stats tokens forced `panel=battle` → `Troops|*` rows inside `stats_right`; forced `scout` → BO numbers presented as scout-net. Blocks merge: No.

### DEFECT-013 [Major] — `fold_sets` misses "Reduction"-worded penalties; sign-flipped own penalty folds as self-buff
`"Penalty"` substring test excludes lexicon-known `Enemy Attack/Defense Reduction`; an own `Enemy Defense Penalty` row that lost its `−` to OCR becomes +10% self-defense. Blocks merge: No.

### DEFECT-014 [Major] — No aggregate upload cap; per-file cap enforced after buffering (3×7 MiB → 200). Blocks merge: No.
### DEFECT-015 [Major] — `calibrate_U` uniformity guard vacuous with <3 classes (single-class calibration passes). Blocks merge: No.
### DEFECT-016 [Major] — Persistence test proves nothing (asserts pytest's own empty tmp_path); 401 / >3 files / zero-byte / invalid side/panel / mock-off-503 all unprotected by tests (probe-verified correct today). Blocks merge: No.
### DEFECT-017 [Minor] — Dead code: computed `missing` discarded; identical if/else branches (service.py).
### DEFECT-018 [Minor] — Battle responses carry `stats: {}` alongside `status: ok` (trap for clients reading the documented primary key).
### DEFECT-019 [Minor] — Non-ValueError exceptions escape token/convert layers (KeyError/TypeError/ZeroDivisionError; plain ValueError from `max([])` that `except CalibrationError` won't catch) — a 500 waiting for the Task-12 engine.
### DEFECT-020 [Minor] — One 2-edit fuzzy collision: Expert↔Pet lethality-penalty labels (same stat; bounded impact).

## No defects found — with evidence (abridged)
C2: all 8 Python modules byte-identical to the plan; thresholds byte-equal both languages. C3: ZERO fixture transcription mismatches vs independent re-transcription of formula doc §3+§9; independent law re-derivation worst residual 0.100 pp (bar 0.11). C5: byte-identical outputs over 3 runs both languages; zero clock/randomness imports. Fuzzy matcher: exhaustive 1-char deletion/substitution sweep → 0 wrong-canonical resolutions. Value grammar: 13 exotic forms all correctly refused. Endpoint: 401/403/405/413/415/422/400 all correct, no 500 on any probe; `resolve_plan` fails closed. No persistence/egress primitives in any panel module. C8: diff scope exactly as expected; D4 scanner change does NOT weaken the secrets gate; promote 23/23; style guard 7/7.

## Category results
C1 PASS · C2 FAIL (range-check spec gap) · C3 PASS · C4 FAIL · C5 PASS · C6 FAIL · C7 FAIL · C8 PASS

## GATED (reported, not skipped)
L2 image benchmark (no PNGs; Task 12 unbuilt) · L4 real UI (doesn't exist; flow_state reviewed as logic vs spec — matches) · perf budgets (no engines) · **quota/semaphore: confirmed absent with mechanism** — `limits.py OCR_ENDPOINTS={'/shell/ocr'}` exact-match ⇒ `/shell/ocr/panel` is unmetered/uncapped/unrecorded (open item for the shell fix-round).

## FINAL VERDICT: REVISE
Minimum to CONDITIONAL: DEFECT-001..006, each with a regression test derived from its probe. Recommended same pass: -007, -010, -016.

---

# Coordinator triage & fix-round rulings (Fable, 2026-08-07)

All 20 defects accepted as valid; none dismissed. Attribution note for the record: D-002/-003/-004/-006 (and the D-008 spec gap) originate in the TDD plan's own code blocks — the builder implemented the plan faithfully; the independent QA layer caught the plan author's defects, which is the system working as designed. Fix round dispatched with these rulings:

1. **D-001**: a value token joins a label's row ONLY if its vertical center lies within the label tokens' own band `[min y0 − 0.35h, max y1 + 0.35h]` (h = median row height). Rejected values become a warning (`orphan value near y=…`), the label keeps `missing_value`.
2. **D-002**: service's bad-predicate covers `col_conflict` (and any future `*conflict` flag — match by substring `conflict`).
3. **D-003**: conflicts are sticky in stitch — once flagged, never replaced.
4. **D-004**: specials pass the same bad-predicate; bad/valueless specials → `unreadable_fields` as `specials.<label>`.
5. **D-005**: `fold_sets(..., observed: bool)` (required kwarg): `observed=False` with empty own-specials raises `MissingSpecialsError`; service output gains `"specials_observed"` (true iff any special-canonical row was seen, readable or not). Account-B case (observed panel, zero enemy rows) stays legal.
6. **D-006**: wire the computed `missing` set into `unreadable_fields` (correct per-branch prefixes).
7. Same-pass: **D-007** (ASGI/dependency Content-Length reject > `MAX_BODY_BYTES` BEFORE form parsing; re-word the in-memory claim), **D-008** (range gate: class rows 0–6000, specials |v| ≤ 25 → unreadable), **D-009** (`re.ASCII`), **D-010** (`"source":"mock"` + refuse flag outside dev ENV), **D-011** (echo `requested_side`; when battle+side given, add `stats_you`/`stats_enemy` aliases — left column = report viewer), **D-012** (hint that contradicts detection → `status:"failed"` + warning, never an override), **D-013** (penalty classification by canonical-label list incl. Reduction rows; own-side positive "Enemy … Penalty/Reduction" → unreadable, never a self-buff), **D-014** (aggregate cap), **D-015** (require all 3 classes), **D-016** (rollover-spy persistence test + the 5 missing endpoint tests), **D-017/-018/-019** (dead code out; battle responses drop the empty `stats` key; defensive input validation → typed errors), **D-020** (documented, accepted).
8. Every fix lands with a regression test derived from the QA probe (`test_qa_defect_NNN_*`), JS mirror updated in the same commit where applicable, both suites + style guard green, commits per defect cluster.

---

# Cycle outcome (rounds 4–6, 2026-08-09/10) — engine ladder + metering: READY at `587ece2`

Rounds 4–6 covered the production ladder (`ladder.py`: RapidOCR primary under a per-loop CPU semaphore → Gemini gap-fill under a pre-committed daily budget → graceful degrade), router wiring (`source:"engine"`, engines_used, field_engine provenance, RuntimeError→503 backstop), and metering (`/shell/ocr/panel` joins OCR_ENDPOINTS: 402 free signal standardized (D-031 amendment), 30/day pro quota SHARED with /shell/ocr, burst, zero CPU for unauthorized). Defects D-028..D-034 found and closed across two fix rounds — headline: **specials are now SIDE-AWARE end-to-end** (D-029 dual-column double-count 0.18→0.10; D-034 closed it structurally by deriving two-column-ness from the rows, not the panel type). Final: **336 py / 41 node / 7 guard, all probes green in both languages; evaluator merge approval for this surface.** Papercut ruling kept: specials_you/enemy aliases stay battle-gated (geometric side is always emitted; semantic orientation is only asserted when earned). Residual one-liner offered (left-side row implies two columns) — non-blocking.

**Formally un-QA'd on the branch (evaluator's standing note):** the 10 commits `97af525..a9c63a7` — real engine adapters, L2 benchmark, account-C fixtures (golden_vectors gained accounts.C), gear-law docs, vendored tesseract.js. The real-image accuracy claim rests on the builder's benchmark **plus the owner's independent rerun** (RapidOCR 100% D2 PASS verified by Martin 2026-08-08); no third-party QA round has probed the adapters themselves. GATED still open: L4 overlay UI (unbuilt), performance budgets on real engines under load.

# Cycle outcome (rounds 2–3, 2026-08-07) — FINAL VERDICT: READY at `97af525` (+D-027 wording fix)

- **Fix round 1** (`e838c25..b0049b5`, 9 commits): all 20 defects fixed per rulings, +45 py/+16 node regression tests. One necessary deviation on D-001: the ruling's literal band was provably a no-op (±0.85h from centre, looser than the 0.6h grouper); the engineer anchored ±0.35h on the label centre — later independently re-derived and ENDORSED by QA.
- **QA round 2**: every round-1 probe re-run → 20/20 FIXED (5 Criticals confirmed in BOTH languages); verdict CONDITIONAL on **D-022** (`specials_observed=True` while all specials unreadable re-opened the 367pp identity-conversion class) + 5 residuals D-021/023/024/025/026 (all safe-direction).
- **Fix round 2** (`ab97182..97af525`, 4 commits): D-022 closed with tri-state `specials_observed: none|partial|read` and `fold_sets` refusing everything but `"read"` (legal zero-specials sides still convert — account B enemy exact); D-021 compatibility matrix (partial battle reads keep the good column); D-023 mock gate fails closed on Settings.ENV; D-024 pre-parse ceiling `MAX_BODY_BYTES+64KiB` + chunked→411; D-025 per-row band height; D-026 warnings dedupe/unmatched-row channel.
- **QA round 3 (micro-confirm)**: 6/6 verified by probe (guard-hole table, partial-battle read, fail-closed mock, 0-parse/0-spool oversize incl. unauthenticated, mixed-height pairing, deduped warnings). **VERDICT: READY — QA merge approval for Tasks 0–11 scope at `97af525`.** One new Minor **D-027** (the partial-battle warning literal asserted "enemy column" even when the viewer column was the empty one) — fixed post-verdict, side-neutral wording ("only one column was readable in this screenshot"), both languages + tests; suites 255/33/7 green.
- **Standing open (by design, unchanged):** ~~L2 real-image benchmark~~ · L4 overlay UI unbuilt · `/shell/ocr/panel` unmetered (`limits.py OCR_ENDPOINTS` exact-match — shell fix-round item) · bounded documented residuals: >1MiB sub-ceiling uploads spool to OS temp for request lifetime; absent-Content-Length fails open to post-parse caps.
- **L2 GATE CLOSED (2026-08-08, Task 12 commit `27d56dc` + corrected corpus image):** real-image benchmark on the account-C corpus (5 panel images, non-max account): **RapidOCR 100.00% digit accuracy, ZERO false-confident — D2 PASS** (owner-verified rerun); tesseract.js 64–76%, zero false-confident — benched pending preprocessing or replacement. The one original miss was a scroll-clipped row the pipeline correctly refused to guess (garbled label fuzzy-distance 3 → unmatched; garbage value conf 0.67 → withheld) — the honesty machinery validated on real pixels. Owner decisions: RapidOCR = primary engine v1; Gemini free-tier adapter benchmarked next on the same harness. Perf note: RapidOCR ~2.6–5.4 s/image local CPU.
- **Gemini live benchmark (2026-08-09, adapter commit `5ce702d`, model `gemini-3-flash-preview`): 100.00% digit accuracy, ZERO false-confident — D2 PASS, equal to RapidOCR.** Latency 6.7–62.6 s/image (throttle/thinking variance) vs RapidOCR's consistent ~3 s. Final v1 engine ladder: **RapidOCR primary (fast, local, deterministic) → Gemini second-opinion/fallback (accuracy-proven; owner's prepay balance funds it) → manual typing.** tesseract.js 64.29% — benched. Setup journey documented in docs/OCR_GEMINI_FREE_TIER.md §6 (owner's account cannot create AI-Studio-managed free-tier projects — org quirk; Cloud-console-created project + key works).
