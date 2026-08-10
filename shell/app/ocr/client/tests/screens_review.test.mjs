import test from 'node:test';
import assert from 'node:assert/strict';
import {
  fieldRenderState, provenanceText, computeTally, validateEditorInput, editorContentFor,
  nextResetState, renderReviewGrid, renderS4, renderPictureView,
} from '../screens/review.mjs';
import { FIELD_OK, FIELD_CHECK, FIELD_MISSING } from '../fill_mapper.mjs';

test('a typed value always wins and always reads ok, even over a check/missing classification', () => {
  const overCheck = fieldRenderState({ classification: { state: FIELD_CHECK, value: 300.6, conf: 0.6 }, savedValue: 350.0 });
  assert.deepEqual(overCheck, { state: 'ok', value: 350.0, typed: true });
  const overMissing = fieldRenderState({ classification: { state: FIELD_MISSING, value: null, conf: null }, savedValue: 12.0 });
  assert.deepEqual(overMissing, { state: 'ok', value: 12.0, typed: true });
  const untouched = fieldRenderState({ classification: { state: FIELD_OK, value: 4491.6, conf: 0.99 }, savedValue: undefined });
  assert.deepEqual(untouched, { state: 'ok', value: 4491.6, typed: false });
});

test('provenanceText matches the mock exactly, all three states', () => {
  assert.equal(provenanceText({ state: 'missing', typed: false }), 'Not read yet. Tap to type it.');
  assert.equal(provenanceText({ state: 'ok', typed: true }), 'You typed this.');
  assert.equal(provenanceText({ state: 'ok', typed: false }), 'Read from your screenshot.');
  assert.equal(provenanceText({ state: 'check', typed: false }), 'Read from your screenshot.');
});

test('computeTally: all clean', () => {
  const t = computeTally(Array(24).fill('ok'));
  assert.equal(t.statusText, 'All 24 numbers are in.');
  assert.equal(t.clear, true);
  assert.equal(t.okPct + t.checkPct + t.missPct, 100);
});

test('computeTally: mixed, exact copy and percentages that always sum to 100', () => {
  const states = [...Array(18).fill('ok'), ...Array(3).fill('check'), ...Array(3).fill('missing')];
  const t = computeTally(states);
  assert.equal(t.statusText, '18 of 24 read well · 3 to check · 3 still empty');
  assert.equal(t.okCount, 18); assert.equal(t.checkCount, 3); assert.equal(t.missingCount, 3);
  assert.equal(t.okPct + t.checkPct + t.missPct, 100);
});

test('computeTally: ok+check only, and ok+missing only (no "0 to check"/"0 still empty" ever shown)', () => {
  const checkOnly = computeTally([...Array(20).fill('ok'), ...Array(4).fill('check')]);
  assert.equal(checkOnly.statusText, '20 of 24 read well · 4 to check');
  const missingOnly = computeTally([...Array(22).fill('ok'), ...Array(2).fill('missing')]);
  assert.equal(missingOnly.statusText, '22 of 24 read well · 2 still empty');
});

test('validateEditorInput matches saveEditor exactly: empty is a silent no-op, bad format and out-of-range have distinct messages', () => {
  assert.deepEqual(validateEditorInput(''), { ok: false, empty: true });
  assert.deepEqual(validateEditorInput('   '), { ok: false, empty: true });
  assert.equal(validateEditorInput('abc').message, 'That needs to be a number.');
  assert.equal(validateEditorInput('12.').message, 'That needs to be a number.');
  assert.equal(validateEditorInput('.5').message, 'That needs to be a number.');
  assert.equal(validateEditorInput('-1').message, 'Numbers here are usually between 0 and 6000.');
  assert.equal(validateEditorInput('6000.01').message, 'Numbers here are usually between 0 and 6000.');
  assert.deepEqual(validateEditorInput('0'), { ok: true, value: 0 });       // inclusive lower bound
  assert.deepEqual(validateEditorInput('6000'), { ok: true, value: 6000 }); // inclusive upper bound
  assert.deepEqual(validateEditorInput('4491.6'), { ok: true, value: 4491.6 });
});

test('editorContentFor: missing vs present copy, exact strings', () => {
  const missing = editorContentFor({ side: 'enemy', key: 'Marksman|Attack', fieldState: { state: 'missing', value: null, typed: false } });
  assert.equal(missing.title, 'Enemy · Marksman · Attack');
  assert.equal(missing.cropTag, 'NOT CAPTURED');
  assert.equal(missing.cropBody, 'This part of the screenshot was not captured.');
  assert.equal(missing.inputValue, '');
  assert.equal(missing.help, "We couldn't read this one. Type the number.");

  const present = editorContentFor({ side: 'you', key: 'Infantry|Attack', fieldState: { state: 'ok', value: 4491.6, typed: false } });
  assert.equal(present.title, 'My side · Infantry · Attack');
  assert.equal(present.cropTag, 'WHAT WE SAW');
  assert.equal(present.inputValue, '4491.6');
  assert.equal(present.help, 'Type over the number if it needs fixing.');
});

test('nextResetState is a clean two-step transition', () => {
  assert.deepEqual(nextResetState('idle'), { state: 'confirming', label: 'Really reset?', shouldClear: false });
  assert.deepEqual(nextResetState('confirming'), { state: 'idle', label: 'Reset', shouldClear: true });
});

function fullStates(overrides = {}) {
  const keys = ['Infantry|Attack', 'Infantry|Defense', 'Infantry|Lethality', 'Infantry|Health',
    'Lancer|Attack', 'Lancer|Defense', 'Lancer|Lethality', 'Lancer|Health',
    'Marksman|Attack', 'Marksman|Defense', 'Marksman|Lethality', 'Marksman|Health'];
  const side = () => Object.fromEntries(keys.map((k) => [k, { state: 'ok', value: 100.0, typed: false }]));
  const states = { you: side(), enemy: side() };
  for (const [path, value] of Object.entries(overrides)) {
    const [s, k] = path.split('.');
    states[s][k] = value;
  }
  return states;
}

test('renderReviewGrid shows both columns, correct icons, and the exact missing placeholder', () => {
  const states = fullStates({ 'enemy.Marksman|Attack': { state: 'missing', value: null, typed: false } });
  const html = renderReviewGrid(states);
  assert.match(html, /MY SIDE/);
  assert.match(html, />ENEMY</);
  assert.match(html, /— —/);              // the missing placeholder, verbatim
  assert.match(html, /Not read yet\. Tap to type it\./);
});

test('renderReviewGrid and renderPictureView derive from the identical states object (cannot disagree)', () => {
  const states = fullStates({ 'you.Infantry|Attack': { state: 'ok', value: 4491.6, typed: true } });
  const grid = renderReviewGrid(states);
  const picture = renderPictureView(states);
  assert.match(grid, /4491\.6/);
  assert.match(picture, /\+4491\.6/);      // picture view prefixes a "+", grid does not — same underlying value either way
});

test('S4 assembles the grid inside the full screen shell with Next always enabled', () => {
  const states = fullStates();
  const html = renderS4({ states, tally: computeTally(Array(24).fill('ok')) });
  assert.match(html, /Check your numbers/);
  assert.match(html, /See my screenshot/);
  assert.doesNotMatch(html, /data-goto="s5"[^>]*disabled/);   // Next is never conditionally disabled
});
