import test from 'node:test';
import assert from 'node:assert/strict';
import { driveScan, SCAN_STEPS, renderS3 } from '../screens/reading.mjs';

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
