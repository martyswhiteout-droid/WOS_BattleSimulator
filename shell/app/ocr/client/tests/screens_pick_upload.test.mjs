import test from 'node:test';
import assert from 'node:assert/strict';
import {
  renderS1, renderS2, renderE1, dropzoneLabel, computeS2ContinueState, TYPE_LABEL, renderThumbs,
  renderSample, renderSampleFallback,
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

// ---- UXJ-004 (EVAL_UX_JOURNEY.md round 1): an HTTP error during a read
// (quota, burst, payment lapsed mid-session, engine busy, session expired)
// must show ITS OWN honest heading/body (error_copy.mjs's mapError output),
// never the "wrong screenshot" copy, plus the recovery action that actually
// matches the failure — never the generic "add a clearer screenshot" +
// sample, which doesn't apply when the screenshot was never the problem. ----

test('UXJ-004: renderE1("error", ...) shows the mapped heading/body verbatim, never the wrong-screenshot copy, and drops the "good example" sample', () => {
  const mapped = { heading: "That's today's limit", body: "You've used up today's screenshot reads. They come back at midnight. You can still type the numbers in.", cta: 'wait' };
  const html = renderE1('error', { mapped });
  assert.match(html, /That's today's limit/);
  assert.match(html, /come back at midnight/);
  assert.doesNotMatch(html, /doesn't look like the right screenshot/i);
  assert.doesNotMatch(html, /A good example:/);
});

test('UXJ-004: cta "wait" (429 quota) offers ONLY typing — retrying is pointless until midnight', () => {
  const html = renderE1('error', { mapped: { heading: 'h', body: 'b', cta: 'wait' } });
  assert.match(html, />Type the numbers in myself</);
  assert.doesNotMatch(html, /Try again/);
  assert.doesNotMatch(html, /data-goto="s2"/);   // never routes back through re-upload
});

test('UXJ-004: cta "slow_down" (429 burst) and "retry_or_type" (503/unknown) both offer "Try again" (re-reads the SAME uploaded bytes via data-goto="s3") plus a typing fallback', () => {
  for (const cta of ['slow_down', 'retry_or_type', 'sign_in']) {
    const html = renderE1('error', { mapped: { heading: 'h', body: 'b', cta } });
    assert.match(html, /data-goto="s3"[^>]*>Try again</, cta);
    assert.match(html, /data-goto="s4" data-show-missing="1"[^>]*>Type them in myself</, cta);
  }
});

test('UXJ-004: cta "retake" (413/415, a bad-file problem) offers re-upload (data-goto="s2" data-recovery="1") plus a typing fallback', () => {
  const html = renderE1('error', { mapped: { heading: 'h', body: 'b', cta: 'retake' } });
  assert.match(html, /data-goto="s2" data-recovery="1"/);
  assert.match(html, /Add a different screenshot/);
  assert.match(html, /data-goto="s4" data-show-missing="1"[^>]*>Type them in myself</);
});

test('UXJ-004: cta "upgrade" (402 mid-session) offers a real "See plans" action (its own id, wired with a side effect elsewhere) plus a typing fallback, never a bare retry', () => {
  const html = renderE1('error', { mapped: { heading: 'h', body: 'b', cta: 'upgrade' } });
  assert.match(html, /id="ocrfE1Upgrade"[^>]*>See plans</);
  assert.match(html, /data-goto="s4" data-show-missing="1"[^>]*>Type it in myself</);
  assert.doesNotMatch(html, /data-goto="s3"/);
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

// ---- UXJ-002 (EVAL_UX_JOURNEY.md round 1) + owner request 2026-08-15: the
// samples are REAL cropped game screenshots (the owner's own fixture
// captures, served from /shell/ocr/client/samples/); the hand-typed
// mini-panels survive as renderSampleFallback for art-stripped bundles. ----

test('samples: battle renders the TWO required real screenshots, numbered (panel then popup)', () => {
  const html = renderSample('battle');
  assert.match(html, /ocrf-sample--pair/);
  assert.match(html, /sample_battle_panel\.jpg/);
  assert.match(html, /sample_battle_popup\.jpg/);
  assert.match(html, /ocrf-sample-badge[^>]*>1</);
  assert.match(html, /ocrf-sample-badge[^>]*>2</);
  assert.match(html, /Stat Bonuses list/);
  assert.match(html, /popup behind the ! icon/);
  // both images carry honest alt text
  assert.match(html, /alt="The battle report's Stat Bonuses panel"/);
  assert.match(html, /alt="The Notes on Special Bonuses popup"/);
});

test('samples: scout and citystats render their single real screenshot; unknown keys render nothing', () => {
  assert.match(renderSample('scout'), /sample_scout\.jpg/);
  assert.match(renderSample('citystats'), /sample_citystats\.jpg/);
  assert.doesNotMatch(renderSample('scout'), /ocrf-sample-badge/);
  assert.equal(renderSample('city'), '');   // the mock's demo key is NOT this file's vocabulary
});

test('samples: renderSampleFallback keeps the hand-drawn mini-panels intact (the img-error path for art-stripped bundles)', () => {
  assert.match(renderSampleFallback('battle'), /ocrf-mini-panel--battle/);
  assert.match(renderSampleFallback('battle'), /\+4859\.0%/);
  assert.match(renderSampleFallback('scout'), /ocrf-mini-panel--scout/);
  assert.match(renderSampleFallback('citystats'), /ocrf-mini-panel--city/);
  assert.match(renderSampleFallback('citystats'), /Bonus Overview/);
  assert.equal(renderSampleFallback('city'), '');
});

test('UXJ-002: S1\'s three cards each carry their matching real-screenshot sample', () => {
  const html = renderS1();
  const battleCard = html.slice(html.indexOf('data-pick-type="battle"'), html.indexOf('data-pick-type="scout"'));
  assert.match(battleCard, /sample_battle_panel\.jpg/);
  const scoutCard = html.slice(html.indexOf('data-pick-type="scout"'), html.indexOf('data-pick-type="citystats"'));
  assert.match(scoutCard, /sample_scout\.jpg/);
  const cityCard = html.slice(html.indexOf('data-pick-type="citystats"'));
  assert.match(cityCard, /sample_citystats\.jpg/);
});

test('UXJ-002: S2 renders the dropzone camera icon and, for an uncovered side, the type\'s real sample', () => {
  const html = renderS2({
    types: { you: 'battle', enemy: 'scout' },
    coverage: { you: false, enemy: false },
  });
  assert.match(html, /ocrf-dz-icon/);
  assert.match(html, /sample_battle_panel\.jpg/);   // you = battle
  assert.match(html, /sample_scout\.jpg/);          // enemy = scout
});

test('UXJ-002: a COVERED side shows the covered-note, not a mini-panel (mutually exclusive, matching the mock)', () => {
  const html = renderS2({
    types: { you: 'battle', enemy: 'battle' },
    coverage: { you: true, enemy: true },
    shots: { you: ['shot1'], enemy: [] },   // enemy is covered by you's battle upload, no shots of its own
  });
  const enemySection = html.slice(html.indexOf('data-side="enemy"'));
  assert.match(enemySection, /Covered by your battle report/);
  const beforeDropzone = enemySection.slice(0, enemySection.indexOf('ocrf-dropzone'));
  assert.doesNotMatch(beforeDropzone, /ocrf-mini-panel/);
  assert.doesNotMatch(beforeDropzone, /ocrf-sample-img/);   // no real sample either — covered needs no reference
  // the dropzone icon is still present even when covered/muted (mock parity)
  assert.match(html, /ocrf-dz-icon/);
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
