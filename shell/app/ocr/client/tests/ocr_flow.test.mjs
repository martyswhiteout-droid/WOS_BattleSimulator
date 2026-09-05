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
import { readFileSync } from 'node:fs';
import {
  createDelegatedClickHandler, planS2Entry, decideAfterRead, decideSheetToClose, takeNavOpts, pickReadError, presentationFor, reentryNotice, pasteTargetSlot,
  sendableShots, backLandsOnEntry,
} from '../ocr_flow.js';
import { mapError } from '../error_copy.mjs';
import { uploadModel } from '../screens/pick_upload.mjs';

// UXJ-004: the same real denial fixture error_copy.test.mjs/controller.test.mjs
// already use — reusing it here (rather than hand-rolling status/body pairs)
// keeps this integration-seam test honest to the real shapes the server
// actually returns.
const DENIALS = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/overlay_ui/api_samples.json', import.meta.url), 'utf8')).denials;

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
  assert.equal(plan.notice, 'Removed. Add a new one.');
});

test('D-039 probe: planS2Entry with fromRecovery=true and nothing tracked on one side still clears the other and still shows the notice', () => {
  const plan = planS2Entry({ fromRecovery: true, shotsYou: [], shotsEnemy: ['e1'] });
  assert.deepEqual(plan.clearYou, []);
  assert.deepEqual(plan.clearEnemy, ['e1']);
  assert.equal(plan.notice, 'Removed. Add a new one.');
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
  // UXG-001: the slot preview sheet overlays the upload screen — topmost of all
  assert.equal(decideSheetToClose({ slotOpen: true, pictureOpen: true, editorOpen: true, menuOpen: true }), 'slot');
});

test('D-040 probe: decideSheetToClose falls through to editor, then menu, then null (nothing open)', () => {
  assert.equal(decideSheetToClose({ pictureOpen: false, editorOpen: true, menuOpen: true }), 'editor');
  assert.equal(decideSheetToClose({ pictureOpen: false, editorOpen: false, menuOpen: true }), 'menu');
  assert.equal(decideSheetToClose({ slotOpen: false, pictureOpen: false, editorOpen: false, menuOpen: false }), null);
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

// --- UXJ-004 (EVAL_UX_JOURNEY.md round 1, most user-harmful finding of the
// round): HTTP errors during a read (quota, burst, payment lapsed mid-
// session, engine busy, session expired) previously ALL rendered as "that
// doesn't look like the right screenshot" — a fabricated cause; the
// screenshot was never the problem. controller.mjs's readAll() already
// computes {error:true, mapped} per failed side (error_copy.mjs's mapError)
// — pickReadError() surfaces it, and decideAfterRead now treats it as
// controlling, ahead of whatever the (necessarily all-missing, for an
// errored side) tally would otherwise say. ---

test('UXJ-004 probe: pickReadError returns null when neither side errored', () => {
  assert.equal(pickReadError({ you: { status: 'ok' }, enemy: { status: 'ok' } }), null);
  assert.equal(pickReadError({}), null);
  assert.equal(pickReadError(undefined), null);
});

test('UXJ-004 probe: pickReadError surfaces the errored side\'s mapped copy', () => {
  const mapped = mapError(429, DENIALS['429_burst'].body);
  const result = pickReadError({ you: { error: true, mapped }, enemy: { status: 'ok' } });
  assert.deepEqual(result, { side: 'you', mapped });
});

test('UXJ-004 probe: pickReadError checks "you" before "enemy" — deterministic, since both sides hit the same account-level gate within milliseconds of each other in virtually every real case', () => {
  const youMapped = mapError(402, DENIALS['402'].body);
  const enemyMapped = mapError(429, DENIALS['429_quota'].body);
  const result = pickReadError({ you: { error: true, mapped: youMapped }, enemy: { error: true, mapped: enemyMapped } });
  assert.equal(result.side, 'you');
  assert.equal(result.mapped, youMapped);
});

test('UXJ-004 probe: pickReadError finds an "enemy"-only error when "you" succeeded (or was never attempted)', () => {
  const mapped = mapError(503, DENIALS['503'].body);
  const result = pickReadError({ enemy: { error: true, mapped } });
  assert.deepEqual(result, { side: 'enemy', mapped });
});

test('UXJ-004: decideAfterRead prioritizes a real HTTP error over the tally — even a tally that would otherwise be a clean 24/24 pass', () => {
  const mapped = mapError(429, DENIALS['429_burst'].body);
  const decision = decideAfterRead(Array(24).fill('ok'), { side: 'you', mapped });
  assert.deepEqual(decision, { screen: 'e1', variant: 'error', mapped });
});

test('UXJ-004: decideAfterRead prioritizes a real HTTP error over an all-missing tally too (the exact live repro: a single covering upload fails, both sides read 0/24)', () => {
  const mapped = mapError(0, null);   // a genuine network failure, no HTTP response at all
  const decision = decideAfterRead(Array(24).fill('missing'), { side: 'you', mapped });
  assert.deepEqual(decision, { screen: 'e1', variant: 'error', mapped });
  assert.notEqual(decision.variant, 'wrong');   // never the old fabricated "wrong screenshot" story
});

test('UXJ-004: decideAfterRead behaves exactly as before when nothing actually errored (errorInfo null/omitted) — no regression to D-038\'s three-way branch', () => {
  assert.deepEqual(decideAfterRead(Array(24).fill('ok'), null), { screen: 's4' });
  assert.deepEqual(decideAfterRead(Array(24).fill('missing')), { screen: 'e1', variant: 'wrong' });   // 2-arg call still defaults errorInfo
});

// One assertion per real error class (fixture-driven — api_samples.json's
// denials, the SAME fixture error_copy.test.mjs/controller.test.mjs use):
// the E1 variant the user actually sees must carry THAT class's own honest
// copy and cta, never a generic or wrong-screenshot substitute.
const ERROR_CLASSES = [
  ['402 payment lapsed mid-session', 402, DENIALS['402'].body, 'upgrade'],
  ['429 burst-limited', 429, DENIALS['429_burst'].body, 'slow_down'],
  ['429 quota exhausted', 429, DENIALS['429_quota'].body, 'wait'],
  ['503 engine busy', 503, DENIALS['503'].body, 'retry_or_type'],
  ['401 session expired', 401, DENIALS['401'].body, 'sign_in'],
  ['413 file too large', 413, DENIALS['413'].body, 'retake'],
];
for (const [label, status, body, expectedCta] of ERROR_CLASSES) {
  test(`UXJ-004: ${label} reaches the user as its OWN honest E1 copy, distinct cta "${expectedCta}", never the wrong-screenshot fallback`, () => {
    const mapped = mapError(status, body);
    assert.equal(mapped.cta, expectedCta);   // error_copy.mjs's own contract, re-asserted here at the integration seam
    const errorInfo = pickReadError({ you: { error: true, mapped } });
    const decision = decideAfterRead(Array(24).fill('missing'), errorInfo);
    assert.equal(decision.screen, 'e1');
    assert.equal(decision.variant, 'error');
    assert.equal(decision.mapped.cta, expectedCta);
    assert.notEqual(decision.mapped.heading, "That doesn't look like the right screenshot");
  });
}

// ---- Takeover presentation (owner escalation 2026-08-15) -------------------
// #ocrfRoot used to render in normal flow at the end of <body> — on desktop
// the whole flow sat phone-width at the very bottom of the page, so clicking
// the CTA looked like "the button just disappeared". S1-S4/E1 are now a
// modal takeover; S5 deliberately is NOT (it renders inline in #ocrfS5Host —
// the mock's S5 is the app itself, not a dialog).

test('takeover: presentationFor is modal for every flow screen EXCEPT entry and s5', () => {
  for (const screen of ['s1', 's2', 's3', 's4', 'e1']) {
    assert.equal(presentationFor(screen).modal, true, screen);
  }
  assert.equal(presentationFor('entry').modal, false);
  assert.equal(presentationFor('s5').modal, false);
});

test('takeover: a click resolving [data-close-flow] calls the injected onCloseFlow, never goto/back', () => {
  const calls = [];
  const handle = createDelegatedClickHandler({
    goto: () => calls.push('goto'), back: () => calls.push('back'),
    onCloseFlow: () => calls.push('close'),
  });
  const el = { closest: (sel) => (sel === '[data-close-flow]' ? { dataset: {} } : null) };
  handle({ target: el, preventDefault: () => {} });
  assert.deepEqual(calls, ['close']);
});

test('takeover: without onCloseFlow injected, [data-close-flow] clicks fall through harmlessly', () => {
  const calls = [];
  const handle = createDelegatedClickHandler({ goto: () => calls.push('goto'), back: () => calls.push('back') });
  const el = { closest: (sel) => (sel === '[data-close-flow]' ? { dataset: {} } : null) };
  handle({ target: el, preventDefault: () => {} });
  assert.deepEqual(calls, []);
});

// ---- Takeover polish (2026-08-15, continued) — bounded dialog, entrance/
// exit motion, desktop scale. backLandsOnEntry is the one new PURE decision
// this round adds (everything else — the scrollTop reset, the one-shot
// .ocrf-dialog-enter class, the animated closeFlowLayer() delay — is DOM/
// timing plumbing exercised live, same split the rest of this file already
// uses for openScrim/closeScrim/syncBackgroundInert).

test('backLandsOnEntry: S1\'s own Back button is the one case that pops all the way to entry (history=[entry,s1], popping lands two-from-top on entry)', () => {
  assert.equal(backLandsOnEntry(['entry', 's1']), true);
});

test('backLandsOnEntry: every other screen\'s Back lands on another modal screen, never entry — S2->S1, S4->S2 (post read-pipeline replace), E1->S2', () => {
  assert.equal(backLandsOnEntry(['entry', 's1', 's2']), false);
  assert.equal(backLandsOnEntry(['entry', 's1', 's2', 's4']), false);
  assert.equal(backLandsOnEntry(['entry', 's1', 's2', 'e1']), false);
});

test('backLandsOnEntry: a length-1 history (just entry, nothing pushed yet) is false — back() itself already guards this with its own early return, but the decision must not claim a close from an empty stack', () => {
  assert.equal(backLandsOnEntry(['entry']), false);
  assert.equal(backLandsOnEntry([]), false);
});

// ---- Round 3 fixes (UXJ-007/008/009) ---------------------------------------

test('UXJ-009: reentryNotice speaks only when shots carried over (minimal-words copy, 2026-08-29)', () => {
  assert.equal(reentryNotice({ shotsYou: [], shotsEnemy: [] }), null);
  assert.equal(reentryNotice(), null);
  assert.equal(reentryNotice({ shotsYou: ['a'], shotsEnemy: [] }), 'Earlier screenshots kept.');
  assert.equal(reentryNotice({ shotsYou: [], shotsEnemy: ['b'] }), 'Earlier screenshots kept.');
});


// Slot-grid redesign (2026-08-29): paste routes to a SLOT — last-touched
// slot if it still has room, else first empty, else first with room.
// Two-card model (2026-09-06): these paste tests exercise YOUR card alone,
// so the enemy card is hidden behind the same-report box.
function model(type, shots, attested = false) {
  return uploadModel({ types: { you: type, enemy: type }, shots, attested, sameReport: true });
}
test('pasteTargetSlot: last-touched slot wins while it has room', () => {
  const m = model('battle', { you: [{ slot: 'heroes' }], enemy: [] });
  assert.equal(pasteTargetSlot(m, 'you:buffs'), 'you:buffs');
});
test('pasteTargetSlot: a FULL last-touched slot yields to the first empty slot', () => {
  const m = model('battle', { you: [{ slot: 'heroes' }], enemy: [] });
  assert.equal(pasteTargetSlot(m, 'you:heroes'), 'you:stats');   // heroes max=1, already full
});
test('pasteTargetSlot: no lastSlot -> first empty slot in grid order', () => {
  const m = model('battle', { you: [], enemy: [] });
  assert.equal(pasteTargetSlot(m, null), 'you:heroes');
});
test('pasteTargetSlot: all slots occupied but one has room -> that one; truly full grid -> null', () => {
  const oneEach = model('battle', { you: [{ slot: 'heroes' }, { slot: 'stats' }, { slot: 'buffs' }, { slot: 'power' }], enemy: [] });
  assert.equal(pasteTargetSlot(oneEach, null), 'you:stats');   // stats max=2, still has room
  const full = model('battle', { you: [{ slot: 'heroes' }, { slot: 'stats' }, { slot: 'stats' },
    { slot: 'buffs' }, { slot: 'buffs' }, { slot: 'power' }], enemy: [] });
  assert.equal(pasteTargetSlot(full, null), null);
});
test("sendableShots: the read sends ONLY the card's active-type slots — parked shots of other types stay home; the enemy sends nothing while the same-report box is on", () => {
  const shots = [{ slot: 'heroes', id: 'a' }, { slot: 'scout', id: 'b' }, { slot: 'stats', id: 'c' }];
  const bb = { you: 'battle', enemy: 'battle' };
  assert.deepEqual(sendableShots(bb, 'you', shots).map((s) => s.id), ['a', 'c']);
  assert.deepEqual(sendableShots({ you: 'scout', enemy: 'battle' }, 'you', shots).map((s) => s.id), ['b']);
  assert.deepEqual(sendableShots(bb, 'enemy', shots).map((s) => s.id), ['a', 'c']);   // its own report
  assert.deepEqual(sendableShots(bb, 'enemy', shots, true), []);                        // box on: covered by yours
  assert.deepEqual(sendableShots({ you: 'battle', enemy: 'scout' }, 'enemy', shots, true).map((s) => s.id), ['b']);   // box inert when not both battle
});
