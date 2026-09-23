import test from 'node:test';
import assert from 'node:assert/strict';
import {
  driveScan, SCAN_STEPS, renderS3, stepFillPct,
  SCAN_NOTE, SCAN_NOTE_SLOW, SCAN_NOTE_SLOWER, SCAN_NOTE_RUNGS, scanNoteFor, setScanNote,
} from '../screens/reading.mjs';

test('driveScan advances steps on a timer while real work is pending, then completes on resolve', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval'] });   // mocking setInterval covers its paired clearInterval too;
                                                      // Node's mock.timers rejects 'clearInterval' as a separate name
  const steps = [];
  let resolveRun;
  const run = () => new Promise((resolve) => { resolveRun = resolve; });
  let done = null;
  driveScan({ run, onStepChange: (s) => steps.push(s), onDone: (r) => { done = r; }, onError: () => {}, stepIntervalMs: 900 });

  assert.deepEqual(steps, [0]);
  t.mock.timers.tick(900);
  assert.deepEqual(steps, [0, 1]);
  t.mock.timers.tick(900);
  assert.deepEqual(steps, [0, 1, 2]);
  t.mock.timers.tick(900);              // caps at the last step — never runs off the end of SCAN_STEPS
  assert.deepEqual(steps, [0, 1, 2, 2]);

  resolveRun({ status: 'ok' });
  await Promise.resolve(); await Promise.resolve();
  assert.deepEqual(done, { status: 'ok' });
  assert.deepEqual(steps, [0, 1, 2, 2, 2]);   // onDone force-sets the final step too
});

test('driveScan resolves fast work immediately, without waiting out the schedule', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval'] });   // mocking setInterval covers its paired clearInterval too;
                                                      // Node's mock.timers rejects 'clearInterval' as a separate name
  const steps = [];
  let done = null;
  driveScan({
    run: () => Promise.resolve({ status: 'ok' }),
    onStepChange: (s) => steps.push(s), onDone: (r) => { done = r; }, onError: () => {},
    stepIntervalMs: 900,
  });
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  assert.deepEqual(done, { status: 'ok' });
  assert.deepEqual(steps, [0, 2]);   // never advanced through step 1 — the work finished first
});

test('driveScan calls onError on rejection, never onDone', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval'] });   // mocking setInterval covers its paired clearInterval too;
                                                      // Node's mock.timers rejects 'clearInterval' as a separate name
  let rejectRun;
  const run = () => new Promise((_resolve, reject) => { rejectRun = reject; });
  let error = null;
  let doneCalls = 0;
  driveScan({ run, onStepChange: () => {}, onDone: () => { doneCalls += 1; }, onError: (e) => { error = e; }, stepIntervalMs: 900 });
  rejectRun(new Error('engine crashed'));
  await Promise.resolve(); await Promise.resolve();
  assert.equal(error.message, 'engine crashed');
  assert.equal(doneCalls, 0);
});

test('driveScan.cancel() suppresses the eventual onDone and stops advancing (QA row F1)', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval'] });   // mocking setInterval covers its paired clearInterval too;
                                                      // Node's mock.timers rejects 'clearInterval' as a separate name
  let resolveRun;
  const run = () => new Promise((resolve) => { resolveRun = resolve; });
  const steps = [];
  let done = null;
  const handle = driveScan({ run, onStepChange: (s) => steps.push(s), onDone: (r) => { done = r; }, onError: () => {}, stepIntervalMs: 900 });
  t.mock.timers.tick(900);
  handle.cancel();
  t.mock.timers.tick(900);              // no further advancement after cancel
  resolveRun({ status: 'ok' });         // the abandoned work finishes anyway — must be ignored
  await Promise.resolve(); await Promise.resolve();
  assert.equal(done, null);
  assert.deepEqual(steps, [0, 1]);
});

// --- UXJ-003 (EVAL_UX_JOURNEY.md round 1): the progress bar's width never
// moved at all (no JS touched it, ever) — one half of "the reading screen
// goes completely static during long reads" (the CSS candy-stripe overlay
// is the other half, verified live — see ocr_flow.css). stepFillPct must
// advance per step but never reach 100: the LAST step's onStepChange fires
// both mid-wait (work may still be running for the documented 45-70s
// Gemini gap-fill long tail) and as part of actual completion — the two
// are indistinguishable from the index alone, so 100% at that index would
// fabricate "done" while a read may still be genuinely in flight. ---

test('UXJ-003 probe: stepFillPct advances per step, strictly increasing, and never reaches 100 (only real completion, i.e. navigating away, may look "done")', () => {
  assert.equal(stepFillPct(0), 30);
  assert.equal(stepFillPct(1), 62);
  assert.equal(stepFillPct(2), 88);
  assert.ok(stepFillPct(0) < stepFillPct(1) && stepFillPct(1) < stepFillPct(2));
  assert.ok(stepFillPct(2) < 100);
});

test('UXJ-003 probe: stepFillPct clamps to the last checkpoint for any out-of-range index (defensive — SCAN_STEPS is always length 3 today, but never throw)', () => {
  assert.equal(stepFillPct(2), stepFillPct(5));
});

// --- UXE-021 (Gate-1 UX round 1, polish): the title claimed ONE screenshot
// while three were in flight, and the bar's last checkpoint (88%) sits there
// for the whole long tail of a real read, which reads as "hung" without an
// expectation. `shots` defaults to 1 so every pre-existing caller/test is
// byte-identical; the trust line stays verbatim (it is a storage promise,
// not a place for a duration).

test('UXE-021: the S3 title is plural only when more than one screenshot was sent, and the read sets a duration expectation', () => {
  assert.match(renderS3({ shots: 3 }), /Reading your screenshots&hellip;/);
  assert.match(renderS3({ shots: 1 }), /Reading your screenshot&hellip;/);
  assert.doesNotMatch(renderS3({ shots: 1 }), /screenshots&hellip;/);
  assert.match(renderS3(), /Reading your screenshot&hellip;/);          // no-arg default
  for (const n of [1, 2, 6]) assert.match(renderS3({ shots: n }), /Usually 10–40 seconds\./);
  // U3D-A2: that sentence is now time-aware, so it is a named constant and the
  // render still starts on the PROMISE - neither reassurance rung ships in the
  // initial markup, and the element can be spoken when it changes.
  assert.equal(SCAN_NOTE, 'Usually 10–40 seconds.');
  assert.ok(renderS3({ shots: 3 }).includes(SCAN_NOTE));
  assert.match(renderS3(), /<p class="ocrf-scan-note" id="ocrfScanNote" aria-live="polite">/);
  for (const later of [SCAN_NOTE_SLOW, SCAN_NOTE_SLOWER]) assert.ok(!renderS3({ shots: 3 }).includes(later), later);
});

test('S3 renders the three narration steps and the server-only trust line (COORDINATOR RULING 2026-08-10 #1)', () => {
  const html = renderS3();
  assert.match(html, /Reading your screenshot/);
  for (const step of SCAN_STEPS) assert.ok(html.includes(step), step);
  assert.match(html, /Sent securely and read right away\. Your screenshots are never saved\./);
  // neither the mock's original client-side overclaim nor the pre-ruling draft's
  // "try... on your phone first" wording belongs in a server-only v1 build
  assert.doesNotMatch(html, /stays on your phone/i);
  assert.doesNotMatch(html, /on your phone first/i);
  assert.match(html, /id="ocrfScanCancel"/);
});

// --- U3D-A2 (Gate-2 round 3, top annoyance #2 / Gate-1 UXE-043): the reading
// screen promised "Usually 10-40 seconds" and then said nothing for the ~30s
// the tester actually waited (and ~3 minutes in the reviewer's run). The
// front end cannot make the server faster, so it stops repeating a broken
// promise: two rungs of plain copy in the line whose job is the expectation.
// Nothing else on the screen moves - same SCAN_STEPS, same order, same striped
// bar, same Cancel, no new control, and no motion (so prefers-reduced-motion
// needs no new guard). ---------------------------------------------------

test('U3D-A2: scanNoteFor is the promise until 20s, reassurance from 20s, and the second rung only past 50s (boundaries exact)', () => {
  assert.equal(scanNoteFor(0), SCAN_NOTE);
  assert.equal(scanNoteFor(19999), SCAN_NOTE);
  assert.equal(scanNoteFor(20000), SCAN_NOTE_SLOW);
  assert.equal(scanNoteFor(49999), SCAN_NOTE_SLOW);
  assert.equal(scanNoteFor(50000), SCAN_NOTE_SLOWER);
  assert.equal(scanNoteFor(600000), SCAN_NOTE_SLOWER);
  // the rungs are data, in order, and the second one lands past the "40
  // seconds" the first line ever claimed
  assert.deepEqual(SCAN_NOTE_RUNGS.map((r) => r.at), [20000, 50000]);
  assert.ok(SCAN_NOTE_RUNGS[0].at < SCAN_NOTE_RUNGS[1].at);
  assert.ok(SCAN_NOTE_RUNGS[1].at > 40000);
});

test('U3D-A2: driveScan swaps the note at exactly 20s (never a tick before), again at 50s, and leaves the step narration alone', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval', 'setTimeout'] });
  const notes = []; const steps = [];
  let resolveRun;
  const run = () => new Promise((resolve) => { resolveRun = resolve; });
  driveScan({ run, onStepChange: (s) => steps.push(s), onDone: () => {}, onError: () => {},
    onNote: (text) => notes.push(text), stepIntervalMs: 900 });
  t.mock.timers.tick(19999);
  assert.deepEqual(notes, [], 'the promise stands until the rung');
  t.mock.timers.tick(1);
  assert.deepEqual(notes, [SCAN_NOTE_SLOW]);
  t.mock.timers.tick(29999);
  assert.deepEqual(notes, [SCAN_NOTE_SLOW]);
  t.mock.timers.tick(1);
  assert.deepEqual(notes, [SCAN_NOTE_SLOW, SCAN_NOTE_SLOWER]);
  t.mock.timers.tick(600000);
  assert.deepEqual(notes, [SCAN_NOTE_SLOW, SCAN_NOTE_SLOWER], 'two rungs, then silence');
  // the narration is untouched: still capped at the last step, never rewound
  assert.equal(steps[0], 0);
  assert.deepEqual([...new Set(steps)], [0, 1, 2]);
  resolveRun({ status: 'ok' });
  await Promise.resolve(); await Promise.resolve();
});

test('U3D-A2: a read that finishes inside the promise never swaps the note, and the pending swaps die with it', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval', 'setTimeout'] });
  const notes = [];
  let resolveRun;
  const run = () => new Promise((resolve) => { resolveRun = resolve; });
  driveScan({ run, onStepChange: () => {}, onDone: () => {}, onError: () => {}, onNote: (text) => notes.push(text) });
  t.mock.timers.tick(5000);
  resolveRun({ status: 'ok' });
  await Promise.resolve(); await Promise.resolve();
  t.mock.timers.tick(600000);
  assert.deepEqual(notes, []);
});

test('U3D-A2: cancel() and a failed read both take the pending note swaps with them (QA row F1: nothing writes into a torn-down S3)', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval', 'setTimeout'] });
  const cancelled = [];
  const handle = driveScan({ run: () => new Promise(() => {}), onStepChange: () => {}, onDone: () => {},
    onError: () => {}, onNote: (text) => cancelled.push(text) });
  handle.cancel();
  t.mock.timers.tick(600000);
  assert.deepEqual(cancelled, []);

  const failed = [];
  let rejectRun;
  driveScan({ run: () => new Promise((_r, reject) => { rejectRun = reject; }), onStepChange: () => {},
    onDone: () => {}, onError: () => {}, onNote: (text) => failed.push(text) });
  rejectRun(new Error('engine crashed'));
  await Promise.resolve(); await Promise.resolve();
  t.mock.timers.tick(600000);
  assert.deepEqual(failed, []);
});

test('U3D-A2: no onNote schedules nothing at all — every pre-existing caller behaves byte-identically', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval', 'setTimeout'] });
  const steps = [];
  let resolveRun;
  const run = () => new Promise((resolve) => { resolveRun = resolve; });
  driveScan({ run, onStepChange: (s) => steps.push(s), onDone: () => {}, onError: () => {}, stepIntervalMs: 900 });
  t.mock.timers.tick(600000);            // would fire both rungs if they had been scheduled
  assert.deepEqual([...new Set(steps)], [0, 1, 2]);
  resolveRun({ status: 'ok' });
  await Promise.resolve(); await Promise.resolve();
});

test('U3D-A2: setScanNote writes the copy into the expectation line as text, and tolerates an S3 that has already gone', () => {
  const node = { textContent: SCAN_NOTE };
  const seen = [];
  const root = { querySelector: (sel) => { seen.push(sel); return sel === '.ocrf-scan-note' ? node : null; } };
  setScanNote(root, SCAN_NOTE_SLOW);
  assert.equal(node.textContent, SCAN_NOTE_SLOW);
  assert.deepEqual(seen, ['.ocrf-scan-note']);
  setScanNote(null, SCAN_NOTE_SLOWER);                      // modal already torn down
  setScanNote({ querySelector: () => null }, SCAN_NOTE_SLOWER);  // S3 replaced by S4/E1
  assert.equal(node.textContent, SCAN_NOTE_SLOW);
});
