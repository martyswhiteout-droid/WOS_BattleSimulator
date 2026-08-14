// shell/app/ocr/client/tests/ocr_flow.test.mjs — the bootstrap (ocr_flow.js)
// is integration/assembly, not independently unit-tested by design (Task 10:
// "every decision it makes was already made and tested by Tasks 1-9"). The
// L4 fix round adds NEW decision logic directly in the bootstrap (the
// delegated [data-goto]/[data-back] click handler, D-037; the S2
// recovery-entry plan, D-039 — the two are implemented together because
// D-039's fix IS routing E1's retake button through D-037's same delegate:
// keeping the old wireE1-specific handler active alongside the new generic
// delegate would double-fire goto() on every E1 exit, corrupting the history
// stack) that is genuinely worth unit-testing on its own — so both are
// exported as pure(-ish), injected-dependency functions, same discipline as
// controller.mjs, and tested here with hand-built event/element fakes (a
// real DOM is not available under node:test in this repo — no jsdom, zero
// new dependencies, per the plan's own tech-stack constraint). The actual
// wiring (document.addEventListener, real DOM effects, applyFillPlan's real
// writes into prototype/index.html's own inputs) stays thin and is
// exercised by the live-browser check, not here — same split the whole
// codebase already uses.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createDelegatedClickHandler, planS2Entry, decideAfterRead, decideSheetToClose, takeNavOpts } from '../ocr_flow.js';

function fakeElement(dataset) {
  return { dataset };
}
// Minimal .closest(selector) fake: resolves ONE specific attribute-selector
// match per element, exactly like a real DOM element would for these simple
// `[data-x]` selectors — enough to prove the handler's own branching without
// a real DOM.
function fakeTarget(matches) {
  return {
    closest(selector) {
      return matches[selector] ?? null;
    },
  };
}

test('D-037: a click whose target resolves [data-goto] calls the injected goto with the screen and no push override (deliberate clicks push, matching the mock convention)', () => {
  const calls = { goto: [], back: 0 };
  const handle = createDelegatedClickHandler({
    goto: (screen, opts) => calls.goto.push([screen, opts]),
    back: () => { calls.back += 1; },
  });
  const goToS5 = fakeElement({ goto: 's5' });
  const event = { target: fakeTarget({ '[data-goto]': goToS5 }), prevented: false, preventDefault() { this.prevented = true; } };
  handle(event);
  assert.deepEqual(calls.goto, [['s5', {}]]);
  assert.equal(calls.back, 0);
  assert.equal(event.prevented, true);
});

test('D-037 regression: S4\'s real "Next" button markup (data-goto="s5", no other data attrs) is exactly what the handler above proves works — this is THE fix (the button was previously bound to nothing at all)', () => {
  const calls = [];
  const handle = createDelegatedClickHandler({ goto: (s, o) => calls.push([s, o]), back: () => {} });
  // screens/review.mjs's renderS4() footer literally emits:
  //   <button ... class="ocrf-btn-primary ocrf-btn-block" data-goto="s5">Next</button>
  const nextButton = fakeElement({ goto: 's5' });
  handle({ target: fakeTarget({ '[data-goto]': nextButton }), preventDefault() {} });
  assert.deepEqual(calls, [['s5', {}]]);
});

test('D-039: a data-goto target additionally carrying data-recovery threads fromRecovery through to goto\'s opts (E1\'s "Add a clearer screenshot" button)', () => {
  const calls = [];
  const handle = createDelegatedClickHandler({ goto: (s, o) => calls.push([s, o]), back: () => {} });
  // screens/pick_upload.mjs's renderE1('wrong')/('partial') emits:
  //   <button ... data-goto="s2" data-recovery="1">Add a clearer screenshot</button>
  const retakeButton = fakeElement({ goto: 's2', recovery: '1' });
  handle({ target: fakeTarget({ '[data-goto]': retakeButton }), preventDefault() {} });
  assert.deepEqual(calls, [['s2', { fromRecovery: true }]]);
});

test('D-039: data-show-missing threads through the same way (E1\'s "Type the missing numbers" button)', () => {
  const calls = [];
  const handle = createDelegatedClickHandler({ goto: (s, o) => calls.push([s, o]), back: () => {} });
  const typeMissingButton = fakeElement({ goto: 's4', showMissing: '1' });
  handle({ target: fakeTarget({ '[data-goto]': typeMissingButton }), preventDefault() {} });
  assert.deepEqual(calls, [['s4', { showMissing: true }]]);
});

test('a click that resolves [data-back] calls the injected back(), not goto', () => {
  const calls = { goto: [], back: 0 };
  const handle = createDelegatedClickHandler({
    goto: (s, o) => calls.goto.push([s, o]), back: () => { calls.back += 1; },
  });
  const backButton = fakeElement({});
  handle({ target: fakeTarget({ '[data-back]': backButton }), preventDefault() {} });
  assert.deepEqual(calls.goto, []);
  assert.equal(calls.back, 1);
});

test('D-035: a click that resolves [data-remove-thumb] calls the injected onRemoveThumb with side + numeric index, not goto/back', () => {
  const calls = { goto: [], back: 0, removeThumb: [] };
  const handle = createDelegatedClickHandler({
    goto: (s, o) => calls.goto.push([s, o]), back: () => { calls.back += 1; },
    onRemoveThumb: (side, i) => calls.removeThumb.push([side, i]),
  });
  // screens/pick_upload.mjs's renderThumbs emits:
  //   <button ... data-remove-thumb-side="enemy" data-remove-thumb="2">&times;</button>
  const removeBtn = fakeElement({ removeThumbSide: 'enemy', removeThumb: '2' });
  handle({ target: fakeTarget({ '[data-remove-thumb]': removeBtn }), preventDefault() {} });
  assert.deepEqual(calls.removeThumb, [['enemy', 2]]);
  assert.deepEqual(calls.goto, []);
  assert.equal(calls.back, 0);
});

test('S5 field-editor observation (confirmed real, not a probe artifact): a click resolving [data-field] calls the injected onOpenField with the field key, regardless of which screen rendered the button — wireS5 never wired this at all, only wireS4 did, per-button, with no equivalent for S5\'s own embedded review grid', () => {
  const calls = [];
  const handle = createDelegatedClickHandler({ goto: () => {}, back: () => {}, onOpenField: (key) => calls.push(key) });
  // screens/review.mjs's renderReviewGrid (embedded identically in BOTH
  // renderS4's grid and renderS5's expanded stats body) emits:
  //   <button ... data-field="you-Infantry|Attack">...</button>
  const fieldBtn = fakeElement({ field: 'you-Infantry|Attack' });
  handle({ target: fakeTarget({ '[data-field]': fieldBtn }), preventDefault() {} });
  assert.deepEqual(calls, ['you-Infantry|Attack']);
});

test('a click matching none of the delegate\'s selectors is a silent no-op (never throws, never calls anything)', () => {
  const calls = { goto: 0, back: 0, removeThumb: 0, openField: 0 };
  const handle = createDelegatedClickHandler({
    goto: () => { calls.goto += 1; }, back: () => { calls.back += 1; },
    onRemoveThumb: () => { calls.removeThumb += 1; }, onOpenField: () => { calls.openField += 1; },
  });
  assert.doesNotThrow(() => handle({ target: fakeTarget({}), preventDefault() {} }));
  assert.deepEqual(calls, { goto: 0, back: 0, removeThumb: 0, openField: 0 });
});

// --- D-039: planS2Entry — the pure decision behind "Add a clearer screenshot" ---

test('D-039 probe: planS2Entry with fromRecovery=false is a no-op (normal S2 arrival, e.g. from S1)', () => {
  const plan = planS2Entry({ fromRecovery: false, shotsYou: ['y1'], shotsEnemy: ['e1'] });
  assert.deepEqual(plan, { clearYou: [], clearEnemy: [], notice: null });
});

test('D-039 probe: planS2Entry with fromRecovery=true clears BOTH sides\' currently-tracked shot ids and carries the exact removal notice (mock copy verbatim)', () => {
  const plan = planS2Entry({ fromRecovery: true, shotsYou: ['y1', 'y2'], shotsEnemy: ['e1'] });
  assert.deepEqual(plan.clearYou, ['y1', 'y2']);
  assert.deepEqual(plan.clearEnemy, ['e1']);
  assert.equal(plan.notice, 'We took that one out. Add a new screenshot.');
});

test('D-039 probe: planS2Entry with fromRecovery=true and nothing tracked on one side still clears the other and still shows the notice', () => {
  const plan = planS2Entry({ fromRecovery: true, shotsYou: [], shotsEnemy: ['e1'] });
  assert.deepEqual(plan.clearYou, []);
  assert.deepEqual(plan.clearEnemy, ['e1']);
  assert.equal(plan.notice, 'We took that one out. Add a new screenshot.');
});

// --- D-038: onReadDone must branch three ways, not two — a 200 that parsed
// NOTHING (evaluator's probe: "C_battle_1-style response, 24 unreadable, 0
// read") is the E1 WRONG-screenshot variant, never partial copy ("We read 0
// of 24 numbers... The rest were too unclear to read" is nonsense when NONE
// were read — that's "this doesn't look like the right screenshot"). ---

test('D-038 probe: 0 of 24 read (C_battle_1-style: totally unreadable) routes to the E1 WRONG variant, never partial', () => {
  const allMissing = Array(24).fill('missing');
  assert.deepEqual(decideAfterRead(allMissing), { screen: 'e1', variant: 'wrong' });
});

test('D-038: some read, some missing routes to E1 PARTIAL with the real (never hardcoded) counts', () => {
  const states = [...Array(9).fill('ok'), ...Array(15).fill('missing')];
  assert.deepEqual(decideAfterRead(states), { screen: 'e1', variant: 'partial', readCount: 9, totalCount: 24 });
});

test('D-038: everything read routes straight to S4', () => {
  assert.deepEqual(decideAfterRead(Array(24).fill('ok')), { screen: 's4' });
});

test('D-038: a "check" (Gemini gap-fill) field counts as read, not missing — only true missing routes away from S4', () => {
  const states = [...Array(20).fill('ok'), ...Array(4).fill('check')];
  assert.deepEqual(decideAfterRead(states), { screen: 's4' });
});

// --- D-040: Escape closes whichever sheet/menu is open — background gets
// inert, focus cannot escape (mock's syncBackgroundInert pattern, ported
// exactly: the picture/editor scrims' own inert/aria-hidden toggling is
// thin DOM wiring exercised live, but the PRIORITY the mock's own keydown
// OR-chain encodes — flowmap > picture > editor > tagMenu; this build has
// no flow map, so picture > editor > menu — is a genuine decision, pulled
// out the same way decideAfterRead (D-038) and planS2Entry (D-039) were. ---

test('D-040 probe: decideSheetToClose picks the picture sheet first when more than one is (structurally shouldn\'t happen once inert is applied, but the chain stays defensive, matching the mock\'s own OR-chain shape)', () => {
  assert.equal(decideSheetToClose({ pictureOpen: true, editorOpen: true, menuOpen: true }), 'picture');
});

test('D-040 probe: decideSheetToClose falls through to editor, then menu, then null (nothing open)', () => {
  assert.equal(decideSheetToClose({ pictureOpen: false, editorOpen: true, menuOpen: true }), 'editor');
  assert.equal(decideSheetToClose({ pictureOpen: false, editorOpen: false, menuOpen: true }), 'menu');
  assert.equal(decideSheetToClose({ pictureOpen: false, editorOpen: false, menuOpen: false }), null);
});

// --- D-041 (blocker): post-recovery dropzones permanently dead. Root cause:
// goto() sets app.navOpts on EVERY navigation but nothing ever cleared it —
// so every subsequent render() call triggered by an internal action
// (onDropzone's upload callback, onTypeTag's selection), NOT a fresh
// goto(), re-read the SAME stale {fromRecovery:true} from the ORIGINAL
// recovery navigation and re-ran planS2Entry's "clear everything currently
// tracked" — wiping out the shot the user had just added, every single
// time. takeNavOpts(app) makes consumption explicit and exactly-once. ---

test('D-041 probe: takeNavOpts consumes navOpts exactly once — a re-render not preceded by a fresh goto() sees null, never a stale fromRecovery', () => {
  const fakeApp = { navOpts: { fromRecovery: true } };
  const first = takeNavOpts(fakeApp);
  assert.deepEqual(first, { fromRecovery: true });
  assert.equal(fakeApp.navOpts, null);
  // THIS is the exact D-041 regression: a second read (modeling the
  // re-render onDropzone's callback triggers after an upload) must not see
  // fromRecovery again.
  const second = takeNavOpts(fakeApp);
  assert.equal(second, null);
});

test('D-041 probe: a plain goto() with no special opts is still a fresh entry ({} is truthy, distinct from null/"nothing pending")', () => {
  const fakeApp = { navOpts: {} };
  assert.deepEqual(takeNavOpts(fakeApp), {});
});
