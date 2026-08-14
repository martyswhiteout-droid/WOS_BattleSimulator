import test from 'node:test';
import assert from 'node:assert/strict';
import {
  renderS1, renderS2, renderE1, dropzoneLabel, computeS2ContinueState, TYPE_LABEL, renderThumbs,
} from '../screens/pick_upload.mjs';

test('S1 uses the real flow_state type vocabulary and the mock copy verbatim', () => {
  const html = renderS1();
  assert.match(html, /Which screenshot do you have\?/);
  assert.match(html, /data-pick-type="battle"/);
  assert.match(html, /data-pick-type="scout"/);
  assert.match(html, /data-pick-type="citystats"/);   // NOT "city" — flow_state's real vocabulary
  assert.match(html, /BEST &middot; FILLS BOTH SIDES/);   // matches the mock's own HTML entity verbatim
  assert.match(html, /Shows your stats and the enemy's stats together\./);
  assert.match(html, /called Bonus Overview in the game/);
  assert.doesNotMatch(html, /\bpicture\b/i);
});

test('dropzoneLabel matches the mock exactly for all three states', () => {
  assert.equal(dropzoneLabel({ side: 'you', covered: false }), 'Tap to add your screenshot');
  assert.equal(dropzoneLabel({ side: 'enemy', covered: false }), "Tap to add the enemy's screenshot");
  assert.equal(dropzoneLabel({ side: 'you', covered: true }), 'Add your own screenshot instead');
  assert.equal(dropzoneLabel({ side: 'enemy', covered: true }), 'Add your own screenshot instead');
});

test('computeS2ContinueState matches updateS2Continue exactly, all four branches', () => {
  assert.deepEqual(computeS2ContinueState({ you: true, enemy: true }), { disabled: false, hint: null });
  assert.deepEqual(computeS2ContinueState({ you: true, enemy: false }),
    { disabled: true, hint: "Now add the enemy's screenshot." });
  assert.deepEqual(computeS2ContinueState({ you: false, enemy: true }),
    { disabled: true, hint: 'Now add your screenshot.' });
  assert.deepEqual(computeS2ContinueState({ you: false, enemy: false }),
    { disabled: true, hint: 'Add a screenshot to continue' });
});

test('S2 renders both sides, the always-on hint card, and reflects Continue state', () => {
  const html = renderS2({
    types: { you: 'battle', enemy: 'battle' },
    coverage: { you: true, enemy: true },
    shots: { you: ['shot1'], enemy: [] },
  });
  assert.match(html, /Add your screenshots/);
  assert.match(html, /data-side="you"/);
  assert.match(html, /data-side="enemy"/);
  assert.match(html, /Long list\? Take 2 screenshots that share a row\. We'll join them\./);
  assert.match(html, /Covered by your battle report/);   // enemy has no shots of its own but battle covers it
  assert.doesNotMatch(html, /disabled/);                 // both covered -> Continue enabled
});

test('S2 disables Continue and shows the hint when only one side is covered', () => {
  const html = renderS2({
    types: { you: 'scout', enemy: 'scout' },
    coverage: { you: true, enemy: false },
    shots: { you: ['shot1'], enemy: [] },
  });
  assert.match(html, /disabled/);
  assert.match(html, /Now add the enemy's screenshot\./);
});

test('D-039: S2 renders the removal notice verbatim when supplied (arriving from E1 recovery), and nothing when not', () => {
  const withNotice = renderS2({
    types: { you: 'scout', enemy: 'scout' }, coverage: { you: false, enemy: false },
    shots: { you: [], enemy: [] }, notice: 'We took that one out. Add a new screenshot.',
  });
  assert.match(withNotice, /We took that one out\. Add a new screenshot\./);

  const withoutNotice = renderS2({
    types: { you: 'scout', enemy: 'scout' }, coverage: { you: false, enemy: false },
    shots: { you: [], enemy: [] },
  });
  assert.doesNotMatch(withoutNotice, /ocrf-s2-notice/);
});

test('E1 "wrong" uses the mock copy verbatim', () => {
  const html = renderE1('wrong');
  assert.match(html, /That doesn't look like the right screenshot/);
  assert.match(html, /This looks like a different screen/);
  assert.match(html, />Type them in myself</);
  assert.match(html, /Add a clearer screenshot/);
});

test('E1 "partial" computes its heading from the real count, never a hardcoded demo number', () => {
  const html = renderE1('partial', { readCount: 9, totalCount: 24 });
  assert.match(html, /We read 9 of 24 numbers/);
  assert.match(html, />Type the missing numbers</);
  const other = renderE1('partial', { readCount: 20, totalCount: 24 });
  assert.match(other, /We read 20 of 24 numbers/);
});

test('TYPE_LABEL covers exactly the three real panel types', () => {
  assert.deepEqual(TYPE_LABEL, { battle: 'Battle Report', scout: 'Scout Report', citystats: 'City Stats' });
});

// --- D-035: no thumbnail, no remove — the .ocrf-thumbs container existed
// but was ALWAYS rendered empty, regardless of shotCount; nothing ever
// mapped over the actual shots to render into it. ---

test('D-035 probe: renderThumbs renders one thumb per shot id, each with a >=44px remove control carrying the side + INDEX (mock\'s .thumb-x counterpart, data-remove-thumb-side/data-remove-thumb)', () => {
  const html = renderThumbs('you', ['shotA', 'shotB']);
  const matches = [...html.matchAll(/data-remove-thumb-side="you" data-remove-thumb="(\d+)"/g)];
  assert.equal(matches.length, 2);
  assert.deepEqual(matches.map((m) => m[1]), ['0', '1']);
  assert.match(html, /aria-label="Remove screenshot"/);
  assert.match(html, /class="ocrf-thumb-x"/);
});

test('D-035 probe: renderThumbs is empty for zero shots (the container stays present but contentless)', () => {
  assert.equal(renderThumbs('you', []), '');
});

test('D-035: S2 actually renders thumb content into .ocrf-thumbs when a side has shots (previously always empty regardless of shotCount)', () => {
  const html = renderS2({
    types: { you: 'scout', enemy: 'scout' },
    coverage: { you: true, enemy: false },
    shots: { you: ['shotA'], enemy: [] },
  });
  assert.match(html, /data-remove-thumb-side="you" data-remove-thumb="0"/);
  assert.doesNotMatch(html, /data-thumbs="you"[^>]*\shidden/);   // visible now that it has content
});

// ---- QA defect 045: the upload screen must say the specials popup is needed --
test('QA defect 045: S2 shows the Special Bonuses popup hint for battle, and only for battle', () => {
  const battle = renderS2({
    types: { you: 'battle', enemy: 'battle' },
    coverage: { you: false, enemy: false },
  });
  assert.match(battle, /data-popup-hint/);
  assert.match(battle, /Special Bonuses popup/);
  assert.match(battle, /next to &ldquo;Stat Bonuses&rdquo;/);

  const scoutOnly = renderS2({
    types: { you: 'scout', enemy: 'scout' },
    coverage: { you: false, enemy: false },
  });
  assert.doesNotMatch(scoutOnly, /data-popup-hint/);
});
