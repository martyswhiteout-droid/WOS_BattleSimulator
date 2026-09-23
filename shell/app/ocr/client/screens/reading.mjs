// shell/app/ocr/client/screens/reading.mjs — the reading/scanning driver.
//
// SERVER-ONLY v1 (COORDINATOR RULING 2026-08-10 #1): the drafted plan built
// this as PREP + S3 — PREP being a one-time "getting ready" state for the
// client tesseract.js/WASM engine's first-run download. There is no such
// download under server-only v1 (every read is a network round trip to
// /shell/ocr/panel, every time — nothing is "first time only"), so PREP is
// dropped entirely rather than kept with now-false copy; this is also why
// docs/OCR_QA_PLAN.md row F9 ("engine download interrupted mid-fetch") is
// N/A-v1. S3 = upload + server read with progress, per the ruling. driveScan
// itself needed no change: it is a generic timer/promise orchestrator that
// never assumed which engine `run()` calls — advances narration while the
// real work (now: the /shell/ocr/panel round trip via controller.readAll)
// is in flight, jumps straight to "done" the moment it resolves, and
// supports a real Cancel that discards whatever the in-flight read
// eventually returns (QA row F1).
export const SCAN_STEPS = ['Reading the numbers…', 'Matching the labels…', 'Checking both sides…'];
const DEFAULT_STEP_INTERVAL_MS = 900;

// Gate-2 round 3, U3D-A2 (top annoyance #2): "Checking both sides…" sat for
// ~30s on a real read (u3d/017) while the note under the title still promised
// "Usually 10–40 seconds". It never looked broken — the bar keeps its stripes
// and all three steps stay ticked — but the screen had made a promise and then
// said nothing when it broke it, and that is exactly the moment an impatient
// player reaches for the tab close (the same defect the Gate-1 reviewer filed
// as UXE-043 after a ~3-minute read). The mitigation the front end owns is
// TIME-AWARENESS in the one line whose whole job is the expectation: two
// rungs, each a plain swap of that sentence, no new control, no new colour, no
// motion (so prefers-reduced-motion is untouched), and the SCAN_STEPS
// narration, the striped bar and Cancel all stay exactly as they were.
// Deliberately NOT a countdown: the read's real duration is server-side and
// unknown, so a number would be a second promise to break.
export const SCAN_NOTE = 'Usually 10–40 seconds.';
export const SCAN_NOTE_SLOW = 'Still reading — nearly there.';
export const SCAN_NOTE_SLOWER = 'Taking longer than usual — still working.';
// 20s: past every read this build has measured as normal (the fixtures land
// well inside it) and short of the ~30s the tester sat through. 50s: past the
// "40 seconds" the first line ever claimed, so the second rung only ever
// speaks when the original promise is already broken.
export const SCAN_NOTE_RUNGS = [
  { at: 20000, text: SCAN_NOTE_SLOW },
  { at: 50000, text: SCAN_NOTE_SLOWER },
];

// Which note an elapsed duration deserves. Pure; the rung list is data, so a
// test can prove the boundaries (19.999s is still the promise, 20s is not).
export function scanNoteFor(elapsedMs, rungs = SCAN_NOTE_RUNGS) {
  let text = SCAN_NOTE;
  for (const rung of rungs) if (elapsedMs >= rung.at) text = rung.text;
  return text;
}

export function driveScan({ run, onStepChange, onDone, onError, onNote, stepIntervalMs = DEFAULT_STEP_INTERVAL_MS,
  noteRungs = SCAN_NOTE_RUNGS }) {
  let step = 0;
  let cancelled = false;
  onStepChange(step);
  const timer = setInterval(() => {
    if (cancelled) return;
    step = Math.min(step + 1, SCAN_STEPS.length - 1);
    onStepChange(step);
  }, stepIntervalMs);
  // The note rungs share driveScan's ONE lifecycle so there is no second
  // thing to tear down: whichever way S3 is left (done, error, Cancel,
  // Escape, ✕, backdrop, back — all of which reach cancel() via
  // leaveScanIfRunning), the pending swaps go with it. No onNote (every
  // pre-existing caller and test) schedules nothing at all.
  const noteTimers = onNote
    ? noteRungs.map((rung) => setTimeout(() => { if (!cancelled) onNote(rung.text, rung.at); }, rung.at))
    : [];
  const stopNotes = () => { for (const id of noteTimers) clearTimeout(id); };

  run().then(
    (result) => {
      clearInterval(timer);
      stopNotes();
      if (cancelled) return;
      onStepChange(SCAN_STEPS.length - 1);
      onDone(result);
    },
    (err) => {
      clearInterval(timer);
      stopNotes();
      if (cancelled) return;
      onError(err);
    },
  );

  return { cancel: () => { cancelled = true; clearInterval(timer); stopNotes(); } };
}

// UXE-021 (Gate-1 UX round 1, polish): the title said "screenshot" while
// three were in flight, and the bar sits at its last checkpoint (88%) for
// the whole long tail of a real read - a determinate-looking bar that stops
// moving reads as HUNG. `shots` = how many screenshots this read actually
// sent (default 1 keeps every existing caller and test byte-identical), and
// the expectation line is its own short note: the trust line below it is
// pinned verbatim by screens_reading.test.mjs and is a promise about
// storage, not a place to bury a duration.
export function renderS3({ shots = 1 } = {}) {
  const steps = SCAN_STEPS
    .map((label, i) => `<li class="ocrf-scan-step" data-step="${i}"><span class="ocrf-step-ic" aria-hidden="true"></span>${label}</li>`)
    .join('');
  const title = shots > 1 ? 'Reading your screenshots&hellip;' : 'Reading your screenshot&hellip;';
  return `
<section class="screen" data-screen="s3">
  <div class="ocrf-scr-body ocrf-scan-body">
    <h1 tabindex="-1">${title}</h1>
    <p class="ocrf-scan-note" id="ocrfScanNote" aria-live="polite">${SCAN_NOTE}</p>
    <div class="ocrf-scan-track"><div class="ocrf-scan-fill" id="ocrfScanFill"></div></div>
    <ul class="ocrf-scan-steps" id="ocrfScanSteps">${steps}</ul>
    <p class="ocrf-trust-line">Sent securely and read right away. Your screenshots are never saved.</p>
  </div>
  <footer class="ocrf-scr-foot ocrf-scr-foot-ghost">
    <button type="button" class="ocrf-btn-ghost ocrf-btn-block" id="ocrfScanCancel">Cancel</button>
  </footer>
</section>`.trim();
}

// UXJ-003 fix (EVAL_UX_JOURNEY.md round 1): the progress bar was a flat,
// static width forever (no JS ever touched it) — one half of "the reading
// screen goes completely static during long reads" (the CSS candy-stripe
// overlay, ocr_flow.css, is the other half). Discrete per-step checkpoints,
// deliberately NEVER 100 here: onStepChange(SCAN_STEPS.length-1) fires both
// when the interval timer naturally reaches the last step (real work may
// still be running for the documented 45-70s Gemini gap-fill long tail) AND
// as part of driveScan's own completion branch (one last onStepChange right
// before onDone) — the two are indistinguishable from the index alone, so
// claiming 100% at that index would fabricate "done" while a read is, per
// this very finding, still genuinely in flight. Actual completion navigates
// away (S4/E1) before any width would need to reach 100 anyway.
const STEP_FILL_PCT = [30, 62, 88];

export function stepFillPct(activeIndex) {
  return STEP_FILL_PCT[activeIndex] ?? STEP_FILL_PCT[STEP_FILL_PCT.length - 1];
}

/* ---- thin DOM wiring below: exercised by the Task 10 browser gate, not node:test ---- */

export function applyStepClasses(root, activeIndex) {
  root.querySelectorAll('.ocrf-scan-step').forEach((li) => {
    const i = Number(li.dataset.step);
    li.classList.toggle('ocrf-active', i === activeIndex);
    li.classList.toggle('ocrf-done', i < activeIndex);
  });
  const fill = root.querySelector('.ocrf-scan-fill');
  if (fill) fill.style.width = `${stepFillPct(activeIndex)}%`;
}

export function wireS3(root, { onCancel }) {
  root.querySelector('#ocrfScanCancel')?.addEventListener('click', onCancel);
}

// U3D-A2: the one line that carries the duration expectation, swapped in
// place. aria-live="polite" is on the element itself (renderS3), so a screen
// reader hears the reassurance too instead of only seeing it; textContent, so
// the copy can never smuggle markup in.
export function setScanNote(root, text) {
  const note = root?.querySelector('.ocrf-scan-note');
  if (note) note.textContent = text;
}
