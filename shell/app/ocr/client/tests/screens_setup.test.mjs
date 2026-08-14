import test from 'node:test';
import assert from 'node:assert/strict';
import { computeChipText, shouldShowUndo, buildFillPlan, renderS5 } from '../screens/setup.mjs';
import { computeTally } from '../screens/review.mjs';

test('computeChipText: complete', () => {
  const text = computeChipText(computeTally(Array(24).fill('ok')));
  assert.match(text, /^All 24 numbers in/);
  assert.match(text, /tap to check$/);
});

test('computeChipText: incomplete, same join rules as the tally card, always ends "tap to check"', () => {
  const states = [...Array(18).fill('ok'), ...Array(3).fill('check'), ...Array(3).fill('missing')];
  const text = computeChipText(computeTally(states));
  assert.equal(text, '18 of 24 in · 3 to check · 3 still empty — tap to check');
});

test('shouldShowUndo is true whenever a snapshot was captured, even on the very first fill', () => {
  assert.equal(shouldShowUndo(null), false);
  assert.equal(shouldShowUndo({ me: { panel: {} }, foe: { panel: {} }, heroesMe: null, heroesFoe: null, statsScoutedChecked: false }), true);
});

test('buildFillPlan only fills sides whose conversion is actually ready — never a partial/needs_specials side', () => {
  const plan = buildFillPlan({
    conversion: {
      you: { outcome: 'ready', percents: { 'Infantry|Attack': 4491.6 } },
      enemy: { outcome: 'needs_specials', percents: null, rawUnconverted: { 'Infantry|Attack': 694.3 } },
    },
    heroesMe: null, heroesFoe: null,
  });
  assert.ok(plan.me);
  assert.equal(plan.me['Infantry|Attack'], 44.916);
  assert.equal(plan.foe, null);
});

test('buildFillPlan carries hero payloads only when supplied, ordered Infantry/Lancer/Marksman', () => {
  const plan = buildFillPlan({
    conversion: { you: { outcome: 'ready', percents: {} }, enemy: { outcome: 'ready', percents: {} } },
    heroesMe: { Infantry: 'Hank', Lancer: null, Marksman: 'Viveca' },
    heroesFoe: null,
  });
  assert.deepEqual(plan.heroesMe, ['Hank', null, 'Viveca']);
  assert.equal(plan.heroesFoe, null);
});

// --- D-042 (blocker): the manual path ("Type them in myself") wrote
// nothing. buildFillPlan built solely from app.lastRead.conversion — a
// totally-unread side (E1 "wrong") has no conversion entry at all, and even
// a partially-ready side's conversion.percents never contains whatever the
// user typed over a field in S4's editor (app.savedValues), since that
// object was never read here. Ruling: user-typed values merge OVER
// conversion-derived ones (user edits always win — the review screen's
// whole point) and fill even when conversion is entirely absent. ---

test('D-042 probe: manual-only path — conversion entirely absent, typed values alone build the whole plan', () => {
  const plan = buildFillPlan({
    conversion: {},   // E1 "wrong": app.lastRead was never set, conversion is {}
    savedValues: { you: { 'Infantry|Attack': 777.7 }, enemy: {} },
    heroesMe: null, heroesFoe: null,
  });
  assert.ok(plan.me);
  assert.equal(plan.me['Infantry|Attack'], 7.777);   // 777.7 / 100, applyPanel's own fraction convention
  assert.equal(plan.foe, null);   // nothing typed for enemy, nothing converted either — correctly left alone
});

test('D-042 probe: mixed path — a typed override beats the converted value for THAT field only, the rest of the conversion survives untouched', () => {
  const plan = buildFillPlan({
    conversion: {
      you: { outcome: 'ready', percents: { 'Infantry|Attack': 4491.6, 'Infantry|Defense': 3979.1 } },
    },
    savedValues: { you: { 'Infantry|Attack': 777.7 }, enemy: {} },   // only Attack was hand-corrected
    heroesMe: null, heroesFoe: null,
  });
  assert.equal(plan.me['Infantry|Attack'], 7.777);      // the typed override
  assert.equal(plan.me['Infantry|Defense'], 39.791);    // untouched conversion value (3979.1/100)
});

test('D-042 probe: no savedValues at all (default) behaves exactly as before — the original ready/non-ready test above is unaffected by this change', () => {
  const plan = buildFillPlan({
    conversion: { you: { outcome: 'ready', percents: { 'Infantry|Attack': 100 } } },
    heroesMe: null, heroesFoe: null,
  });
  assert.equal(plan.me['Infantry|Attack'], 1);
  assert.equal(plan.foe, null);
});

test('renderS5 shows the collapsed chip, a hidden expandable body, and a hidden Undo link by default', () => {
  const states = { you: {}, enemy: {} };   // grid content itself is Task 8's concern, not re-tested here
  const html = renderS5({ chipText: 'All 24 numbers in ✓ — tap to check', complete: true, states });
  assert.match(html, /aria-expanded="false"/);
  assert.match(html, /id="ocrfS5Body" hidden/);
  assert.match(html, /id="ocrfUndoChip" hidden/);
  assert.doesNotMatch(html, /Troops Formation/);   // formation is explicitly NOT part of this widget
  assert.doesNotMatch(html, /hero-grid|joiner-pill/i);   // neither are heroes/joiners — those are the real app's own DOM
});
