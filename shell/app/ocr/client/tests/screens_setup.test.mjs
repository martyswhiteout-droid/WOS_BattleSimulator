import test from 'node:test';
import assert from 'node:assert/strict';
import { computeChipText, conversionNotices, shouldShowUndo, buildFillPlan, renderS5 } from '../screens/setup.mjs';
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

// --- UXJ-005 (EVAL_UX_JOURNEY.md round 1): S4->S5 never moved focus to a
// heading — #ocrfS5 had no heading element at all, so ocr_flow.js's generic
// show() (root().querySelector('h1, h2[tabindex]') -> focus) found nothing
// and left focus on <body>. Same convention as every other screen. ---

test('UXJ-005 probe: renderS5 carries a focusable h1 (same convention as S1-S4), so the generic show() focus mechanism has something to find', () => {
  const html = renderS5({ chipText: 'x', complete: true, states: { you: {}, enemy: {} } });
  assert.match(html, /<h1 tabindex="-1"[^>]*>Battle setup<\/h1>/);
});

test('UXJ-005 probe: the heading is the FIRST thing in #ocrfS5 — before the stats accordion, notices, or anything else', () => {
  const html = renderS5({ chipText: 'x', complete: true, states: { you: {}, enemy: {} } });
  const sectionOpen = html.indexOf('<section class="ocrf-s5"');
  const heading = html.indexOf('<h1');
  const accordion = html.indexOf('ocrf-stats-accordion');
  assert.ok(sectionOpen !== -1 && heading !== -1 && accordion !== -1);
  assert.ok(sectionOpen < heading && heading < accordion);
});

// ---- QA defect 044: chip/tally must reflect conversion-readiness ----------
// QA2's probe: 12 fields all read cleanly (tally.clear === true) while the
// side's convertSide() outcome is needs_specials — the old chip said
// "All 12 numbers in ✓" while buildFillPlan left the side untouched and
// nothing on screen said why. The notices are derived from the same
// `conversion` object buildFillPlan consumes, so they cannot disagree.

test('QA defect 044: conversionNotices — ready sides and absent sides produce nothing', () => {
  assert.deepEqual(conversionNotices({}), []);   // pure-manual path: no OCR promise to break
  assert.deepEqual(conversionNotices({ you: { outcome: 'ready', percents: {} } }), []);
});

test('QA defect 044: a needs_specials side yields a notice that names the side, the reason, and the typed-values guarantee', () => {
  const notices = conversionNotices({
    you: { outcome: 'ready', percents: {} },
    enemy: { outcome: 'needs_specials', reason: 'the Special Bonuses screenshot for this side is missing — in the report, tap the ! next to "Stat Bonuses" and screenshot that popup' },
  });
  assert.equal(notices.length, 1);
  assert.equal(notices[0].side, 'enemy');
  assert.equal(notices[0].outcome, 'needs_specials');
  assert.match(notices[0].message, /the enemy side/);
  assert.match(notices[0].message, /Special Bonuses screenshot/);
  assert.match(notices[0].message, /Anything you typed yourself was kept/);
});

test('QA defect 044: the chip never claims completeness while a side is unconverted', () => {
  const tally = computeTally(Array(24).fill('ok'));
  assert.equal(tally.clear, true);
  const notices = conversionNotices({ enemy: { outcome: 'needs_specials', reason: 'x' } });
  const text = computeChipText(tally, notices);
  assert.doesNotMatch(text, /numbers in </);            // the old "All N numbers in ✓" claim
  assert.match(text, /All 24 numbers read · the enemy side not filled in — tap to check/);
  // and with imperfect reads + a notice, both truths appear
  const mixed = computeTally([...Array(20).fill('ok'), ...Array(4).fill('missing')]);
  assert.match(computeChipText(mixed, notices), /20 of 24 in · the enemy side not filled in/);
});

test('QA defect 044: renderS5 shows the notice card inside the body and the chip drops the complete styling', () => {
  const notices = conversionNotices({ you: { outcome: 'needs_specials', reason: 'popup missing' } });
  const html = renderS5({ chipText: 'x', complete: false, states: { you: {}, enemy: {} }, notices });
  assert.match(html, /data-conv-notice="you"/);
  assert.match(html, /We read your side's numbers, but didn't fill them in: popup missing/);
  assert.match(html, /ocrf-needs-attention/);
  assert.doesNotMatch(html, /ocrf-complete/);
});
