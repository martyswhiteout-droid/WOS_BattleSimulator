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

export function driveScan({ run, onStepChange, onDone, onError, stepIntervalMs = DEFAULT_STEP_INTERVAL_MS }) {
  let step = 0;
  let cancelled = false;
  onStepChange(step);
  const timer = setInterval(() => {
    if (cancelled) return;
    step = Math.min(step + 1, SCAN_STEPS.length - 1);
    onStepChange(step);
  }, stepIntervalMs);

  run().then(
    (result) => {
      clearInterval(timer);
      if (cancelled) return;
      onStepChange(SCAN_STEPS.length - 1);
      onDone(result);
    },
    (err) => {
      clearInterval(timer);
      if (cancelled) return;
      onError(err);
    },
  );

  return { cancel: () => { cancelled = true; clearInterval(timer); } };
}

export function renderS3() {
  const steps = SCAN_STEPS
    .map((label, i) => `<li class="ocrf-scan-step" data-step="${i}"><span class="ocrf-step-ic" aria-hidden="true"></span>${label}</li>`)
    .join('');
  return `
<section class="screen" data-screen="s3">
  <div class="ocrf-scr-body ocrf-scan-body">
    <h1 tabindex="-1">Reading your screenshot&hellip;</h1>
    <div class="ocrf-scan-track"><div class="ocrf-scan-fill" id="ocrfScanFill"></div></div>
    <ul class="ocrf-scan-steps" id="ocrfScanSteps">${steps}</ul>
    <p class="ocrf-trust-line">Sent securely and read right away. Your screenshots are never saved.</p>
  </div>
  <footer class="ocrf-scr-foot ocrf-scr-foot-ghost">
    <button type="button" class="ocrf-btn-ghost ocrf-btn-block" id="ocrfScanCancel">Cancel</button>
  </footer>
</section>`.trim();
}

/* ---- thin DOM wiring below: exercised by the Task 10 browser gate, not node:test ---- */

export function applyStepClasses(root, activeIndex) {
  root.querySelectorAll('.ocrf-scan-step').forEach((li) => {
    const i = Number(li.dataset.step);
    li.classList.toggle('ocrf-active', i === activeIndex);
    li.classList.toggle('ocrf-done', i < activeIndex);
  });
}

export function wireS3(root, { onCancel }) {
  root.querySelector('#ocrfScanCancel')?.addEventListener('click', onCancel);
}
