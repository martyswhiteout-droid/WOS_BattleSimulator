// tests for screens/pick_upload.mjs — the combined slot-grid Upload screen
// (owner redesign 2026-08-29, built to the multi-doc-upload research round).
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  SLOTS, groupsFor, slotState, uploadModel, renderUpload, renderE1, TAB_LABEL, missingList,
} from '../screens/pick_upload.mjs';

// --- slot config: the owner's document list, one word per label ------------

test('battle slots: owner labels 2026-08-30 — Heroes + Experts / Stats / Buffs / Troops; heroes required, troops optional, buffs noneable up to 2', () => {
  const keys = SLOTS.battle.map((s) => s.key);
  assert.deepEqual(keys, ['heroes', 'stats', 'buffs', 'power']);
  assert.deepEqual(SLOTS.battle.map((s) => s.label), ['Heroes + Experts', 'Stats', 'Buffs', 'Troops']);
  const byKey = Object.fromEntries(SLOTS.battle.map((s) => [s.key, s]));
  assert.equal(byKey.heroes.required, true);
  assert.equal(byKey.stats.required, true);
  assert.equal(byKey.buffs.required, true);
  assert.equal(byKey.power.required, false);
  assert.equal(byKey.buffs.noneable, true);
  assert.equal(byKey.buffs.max, 2);
});

test('slot labels stay short (<=3 words; owner names them: Heroes + Experts / Combat stats / Bonus Overview)', () => {
  for (const type of Object.keys(SLOTS)) {
    for (const s of SLOTS[type]) {
      const words = s.label.trim().split(/\s+/).filter((w) => /[a-zA-Z]/.test(w));
      assert.ok(words.length <= 3, `${type}:${s.key} label "${s.label}"`);
    }
  }
});

test('groupsFor(battle): scope model — mine = 4 plain rows; enemy = the opponent-report rows; both = two labeled report groups', () => {
  const mine = groupsFor('battle');
  assert.deepEqual(mine.map((g) => [g.side, g.label]), [['you', null]]);
  assert.equal(mine[0].slots.length, 4);

  const enemy = groupsFor('battle', { scope: 'enemy' });
  assert.deepEqual(enemy.map((g) => [g.side, g.label]), [['enemy', null]]);
  assert.equal(enemy[0].slots.length, 4);

  const both = groupsFor('battle', { scope: 'both' });
  assert.deepEqual(both.map((g) => [g.side, g.label]),
    [['you', 'Your report'], ['enemy', "Enemy's report"]]);
  // battle hints are SIDE-NEUTRAL (the scope control owns "whose")
  for (const g of both) {
    assert.equal(g.slots[3].hint, 'Upload the screenshot showing troop quality, ratio, FC tier');
  }
});

test('groupsFor: scout/city stay You+Enemy; city is SYMMETRIC (owner 2026-08-30)', () => {
  const scout = groupsFor('scout');
  assert.deepEqual(scout.map((g) => [g.side, g.label]), [['you', 'You'], ['enemy', 'Enemy']]);
  assert.equal(scout[1].slots[0].hint, "Upload the scout report showing the enemy's stats");

  const city = groupsFor('citystats');
  assert.equal(city[0].slots[0].key, 'city');
  assert.equal(city[1].slots[0].key, 'city');   // enemy uploads City Stats too now
  assert.match(city[1].slots[0].hint, /enemy's City Stats/);
});

// --- slotState: the per-tile state machine --------------------------------

test('slotState: empty -> added (with count) -> and "none" only for a noneable slot with the attestation on', () => {
  const buffs = SLOTS.battle.find((s) => s.key === 'buffs');
  const heroes = SLOTS.battle.find((s) => s.key === 'heroes');
  assert.deepEqual(slotState(buffs, [], false), { state: 'empty', count: 0 });
  assert.deepEqual(slotState(buffs, [{ slot: 'buffs' }], false), { state: 'added', count: 1 });
  assert.deepEqual(slotState(buffs, [{ slot: 'buffs' }, { slot: 'buffs' }], true), { state: 'added', count: 2 });
  assert.deepEqual(slotState(buffs, [], true), { state: 'none', count: 0 });
  // attestation never touches a non-noneable slot
  assert.deepEqual(slotState(heroes, [], true), { state: 'empty', count: 0 });
  // shots parked under other slots don't count
  assert.deepEqual(slotState(heroes, [{ slot: 'stats' }], false), { state: 'empty', count: 0 });
});

// --- uploadModel: fraction + Scan gate ------------------------------------

test('uploadModel(battle): 3 required slots; Scan stays gated until heroes+stats+buffs are covered (None counts for buffs)', () => {
  const empty = uploadModel({ type: 'battle', shots: { you: [], enemy: [] } });
  assert.equal(empty.total, 3);
  assert.equal(empty.done, 0);
  assert.equal(empty.canScan, false);

  const partial = uploadModel({
    type: 'battle',
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] },
  });
  assert.equal(partial.done, 2);
  assert.equal(partial.canScan, false);

  const attested = uploadModel({
    type: 'battle',
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] },
    attested: true,
  });
  assert.equal(attested.done, 3);
  assert.equal(attested.canScan, true);

  const full = uploadModel({
    type: 'battle',
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }, { slot: 'buffs' }], enemy: [] },
  });
  assert.equal(full.canScan, true);
  // optional Power never enters the fraction
  assert.equal(full.total, 3);
});

test('uploadModel(scout): BOTH sides required — one covered side is not scannable', () => {
  const one = uploadModel({ type: 'scout', shots: { you: [{ slot: 'scout' }], enemy: [] } });
  assert.equal(one.total, 2);
  assert.equal(one.done, 1);
  assert.equal(one.canScan, false);
  const both = uploadModel({ type: 'scout', shots: { you: [{ slot: 'scout' }], enemy: [{ slot: 'scout' }] } });
  assert.equal(both.canScan, true);
});

// --- renderUpload: requirement rows in contained cards (owner round 2) ----

function battleHtml(over = {}) {
  const model = uploadModel({ type: 'battle', shots: { you: [], enemy: [] }, ...over.modelArgs });
  return renderUpload({ type: 'battle', model, ...over });
}

test('renderUpload: all four battle requirement rows render at once, top-to-bottom', () => {
  const html = battleHtml();
  for (const key of ['heroes', 'stats', 'buffs', 'power']) {
    assert.match(html, new RegExp(`data-slot-tile="you:${key}"`), key);
  }
  assert.match(html, /data-screen="s1"/);
  assert.match(html, /class="ocrf-req-card"/);
});

test('every row carries the owner-dictated upload instruction (<=10 words)', () => {
  const html = battleHtml();
  for (const s of SLOTS.battle) {
    assert.match(html, new RegExp(s.hint.replace(/[.*+?^${}()|[\]\!&]/g, '\\$&')), s.key);
  }
  for (const type of Object.keys(SLOTS)) {
    for (const s of SLOTS[type]) {
      for (const h of [s.hint, s.hintEnemy].filter(Boolean)) {
        const words = h.split(/\s+/).filter((w) => /[a-zA-Z0-9]/.test(w));
        assert.ok(words.length <= 10, `${type}:${s.key} hint "${h}" is ${words.length} words`);
      }
    }
  }
});

test("Troops row shows the owner's real Troop Power capture (2026-09-06) with the drawn stand-in declared as fallback", () => {
  const html = battleHtml();
  const powerRow = html.split('data-slot-tile="you:power"')[1].split('data-slot-tile')[0];
  assert.match(powerRow, /ocrf-req-sample" src="\/shell\/ocr\/client\/samples\/sample_troop_power\.jpg"/);
  assert.match(powerRow, /data-drawn="troops"/);
});

test('renderUpload: tabs carry the FULL type names (owner 2026-08-30) with the active one pressed; intro line present', () => {
  const html = battleHtml();
  assert.match(html, /data-type-tab="battle"[^>]*aria-pressed="true"/);
  assert.match(html, /data-type-tab="scout"[^>]*aria-pressed="false"/);
  assert.match(html, /data-type-tab="citystats"[^>]*aria-pressed="false"/);
  assert.deepEqual(Object.values(TAB_LABEL), ['Battle Report', 'Scout Report', 'City Stats']);
  assert.match(html, /class="ocrf-upload-intro">Choose the type of screenshot to upload</);
});

test('renderUpload: the * cue is RETIRED (owner: "What does * mean?"); only optional is marked; + Add is a real BUTTON on every empty row', () => {
  const html = battleHtml();
  assert.doesNotMatch(html, /ocrf-req-star/);
  assert.match(html, /Troops <span class="ocrf-req-opt">optional</);
  assert.equal((html.match(/<button type="button" class="ocrf-req-add" data-slot="you:/g) || []).length, 4);
  // the row words are inert: no button wraps the sample/text any more
  assert.doesNotMatch(html, /<button[^>]*class="ocrf-req-main"/);
  assert.match(html, /<div class="ocrf-req-main">/);
});

test('battle scope (owner 2026-08-30 #2): segmented Whose battle report? sits above the rows, Mine active by default', () => {
  const html = battleHtml();
  assert.match(html, /Whose battle report\?/);
  assert.match(html, /role="radiogroup"/);
  assert.match(html, /data-scope="mine"[^>]*aria-checked="true"[^>]*>Mine</);
  assert.match(html, /data-scope="enemy"[^>]*aria-checked="false"[^>]*>Enemy's</);
  assert.match(html, /data-scope="both"[^>]*aria-checked="false"[^>]*>Both</);
  assert.match(html, /Each report shows both sides\./);
  // the checkbox is DEAD
  assert.doesNotMatch(html, /data-same-toggle/);
  assert.doesNotMatch(html, /Same report as yours/);
  // default: ONE plain card, no group header, rows for side you
  assert.equal((html.match(/class="ocrf-req-card"/g) || []).length, 1);
  assert.doesNotMatch(html, /ocrf-req-card-head/);
  assert.match(html, /data-slot-tile="you:heroes"/);
});

test('battle scope: enemy = the same 4 rows for side enemy; both = two labeled report cards, Scan 0/6', () => {
  const enemy = renderUpload({
    type: 'battle',
    model: uploadModel({ type: 'battle', shots: { you: [], enemy: [] }, scope: 'enemy' }),
  });
  for (const key of ['heroes', 'stats', 'buffs', 'power']) {
    assert.match(enemy, new RegExp(`data-slot-tile="enemy:${key}"`), key);
  }
  assert.doesNotMatch(enemy, /data-slot-tile="you:/);
  assert.match(enemy, /id="ocrfScan" disabled>Scan <span class="ocrf-scan-count">0\/3</);

  const both = renderUpload({
    type: 'battle',
    model: uploadModel({ type: 'battle', shots: { you: [], enemy: [] }, scope: 'both' }),
  });
  assert.match(both, /<span>Your report<\/span>/);
  assert.match(both, /<span>Enemy's report<\/span>/);
  assert.match(both, /ocrf-req-cards ocrf-req-cards--two/);
  assert.match(both, /class="ocrf-scan-count">0\/6</);
});

test('battle scope model: mine/enemy -> 3 required; both -> 6 (each side gates Scan)', () => {
  assert.equal(uploadModel({ type: 'battle', shots: { you: [], enemy: [] } }).total, 3);
  assert.equal(uploadModel({ type: 'battle', shots: { you: [], enemy: [] }, scope: 'enemy' }).total, 3);
  const both = uploadModel({ type: 'battle', shots: { you: [], enemy: [] }, scope: 'both' });
  assert.equal(both.total, 6);
  const ready = uploadModel({
    type: 'battle', scope: 'both', attested: true,
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [{ slot: 'heroes' }, { slot: 'stats' }] },
  });
  assert.equal(ready.canScan, true);
});

test('renderUpload: the fraction lives INSIDE the locked Scan button; enabled Scan is the bare word', () => {
  const gated = battleHtml();
  assert.match(gated, /id="ocrfScan" disabled>Scan <span class="ocrf-scan-count">0\/3</);
  const ready = renderUpload({
    type: 'battle',
    model: uploadModel({ type: 'battle', shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] }, attested: true }),
  });
  assert.match(ready, /id="ocrfScan">Scan</);
  assert.doesNotMatch(ready, /ocrf-scan-count/);
  // the old detached summary strip and pips are GONE
  assert.doesNotMatch(gated, /ocrf-pip/);
  assert.doesNotMatch(gated, /ocrf-summary/);
});

test('renderUpload: an added row keeps its sample and gives each thumb its OWN remove x (QAC-001)', () => {
  const model = uploadModel({
    type: 'battle',
    shots: { you: [{ slot: 'buffs' }, { slot: 'buffs' }, { slot: 'heroes' }], enemy: [] },
  });
  model.groups[0].slots.find((s) => s.key === 'buffs').thumbUrls = ['blob:one', 'blob:two'];
  const html = renderUpload({ type: 'battle', model });
  // owner 2026-09-06: + Add is the trigger; a FULL row (heroes max 1) has
  // no add button, its thumbnail opens the preview instead
  const heroRow = html.split('data-slot-tile="you:heroes"')[1].split('data-slot-tile')[0];
  assert.doesNotMatch(heroRow, /data-slot="you:heroes"/);
  assert.match(heroRow, /data-slot-preview="you:heroes"/);
  assert.match(html, /data-slot-remove="you:heroes:0"/);
  const buffsRow = html.split('data-slot-tile="you:buffs"')[1].split('data-slot-tile')[0];
  assert.equal((buffsRow.match(/class="ocrf-req-thumb"/g) || []).length, 2);
  assert.match(buffsRow, /data-slot-remove="you:buffs:0"/);
  assert.match(buffsRow, /data-slot-remove="you:buffs:1"/);
  assert.match(buffsRow, /url\('blob:one'\)/);
  assert.match(buffsRow, /ocrf-req-sample/);   // the recognition sample never disappears
  assert.doesNotMatch(html, /data-slot-remove="you:stats/);
});

test('QAC-004: a row below its cap keeps the + Add chip; a full row drops it', () => {
  const one = uploadModel({ type: 'battle', shots: { you: [{ slot: 'buffs' }], enemy: [] } });
  const oneHtml = renderUpload({ type: 'battle', model: one });
  const buffs1 = oneHtml.split('data-slot-tile="you:buffs"')[1].split('data-slot-tile')[0];
  assert.match(buffs1, /ocrf-req-add/);
  const full = uploadModel({ type: 'battle', shots: { you: [{ slot: 'buffs' }, { slot: 'buffs' }], enemy: [] } });
  const fullHtml = renderUpload({ type: 'battle', model: full });
  const buffs2 = fullHtml.split('data-slot-tile="you:buffs"')[1].split('data-slot-tile')[0];
  assert.doesNotMatch(buffs2, /ocrf-req-add/);
  // heroes (max 1) drops its chip after one shot
  const hero = uploadModel({ type: 'battle', shots: { you: [{ slot: 'heroes' }], enemy: [] } });
  const heroRow = renderUpload({ type: 'battle', model: hero }).split('data-slot-tile="you:heroes"')[1].split('data-slot-tile')[0];
  assert.doesNotMatch(heroRow, /ocrf-req-add/);
});

test('QAC-002: every hint span carries its data-hint restore value and an aria-live channel', () => {
  const html = battleHtml();
  for (const s of SLOTS.battle) {
    assert.match(html, new RegExp(`data-hint="${s.hint.replace(/[.*+?^${}()|[\]\!&]/g, '\\$&')}" aria-live="polite"`), s.key);
  }
});

test('renderUpload: None is an inline chip on the Buffs row — pressed state when attested, gone when a file lands', () => {
  const empty = battleHtml();
  assert.match(empty, /data-slot-none="you:buffs"[^>]*aria-pressed="false"[^>]*>None</);
  const attested = renderUpload({
    type: 'battle',
    model: uploadModel({ type: 'battle', shots: { you: [], enemy: [] }, attested: true }),
  });
  assert.match(attested, /ocrf-req-none--on/);
  assert.match(attested, /aria-pressed="true"/);
  assert.match(attested, /data-slot="you:buffs" data-slot-state="none"/);
  const filled = renderUpload({
    type: 'battle',
    model: uploadModel({ type: 'battle', shots: { you: [{ slot: 'buffs' }], enemy: [] } }),
  });
  assert.doesNotMatch(filled, /data-slot-none=/);
});

test('renderUpload(scout): You and Enemy are SEPARATE bordered cards, each with its own header + count', () => {
  const model = uploadModel({ type: 'scout', shots: { you: [{ slot: 'scout' }], enemy: [] } });
  const html = renderUpload({ type: 'scout', model });
  assert.equal((html.match(/class="ocrf-req-card"/g) || []).length, 2);
  assert.match(html, /<span>You<\/span><span class="ocrf-req-card-count">1\/1</);
  assert.match(html, /<span>Enemy<\/span><span class="ocrf-req-card-count">0\/1</);
  // each card CONTAINS its own row — ownership by containment, not proximity
  const youCard = html.split('data-group="you"')[1].split('</section>')[0];
  assert.match(youCard, /data-slot-tile="you:scout"/);
  const enemyCard = html.split('data-group="enemy"')[1].split('</section>')[0];
  assert.match(enemyCard, /data-slot-tile="enemy:scout"/);
});

test('renderUpload(citystats): the Enemy card uploads City Stats too — never a scout row (owner 2026-08-30)', () => {
  const model = uploadModel({ type: 'citystats', shots: { you: [], enemy: [] } });
  const html = renderUpload({ type: 'citystats', model });
  const enemyCard = html.split('data-group="enemy"')[1].split('</section>')[0];
  assert.match(enemyCard, /data-slot-tile="enemy:city"/);
  assert.doesNotMatch(enemyCard, /data-slot-tile="enemy:scout"/);
  assert.match(enemyCard, /enemy's City Stats/);
});

test("renderUpload(battle, scope both): each labeled card carries its own n/m count", () => {
  const html = renderUpload({
    type: 'battle',
    model: uploadModel({ type: 'battle', shots: { you: [{ slot: 'stats' }], enemy: [] }, scope: 'both' }),
  });
  assert.match(html, /<span>Your report<\/span><span class="ocrf-req-card-count">1\/3</);
  assert.match(html, /<span>Enemy's report<\/span><span class="ocrf-req-card-count">0\/3</);
  // QAC-018: each labeled card prefixes its name into row aria-labels
  assert.match(html, /aria-label="Your report: Stats, 1 added"/);
  assert.match(html, /aria-label="Enemy's report: Heroes \+ Experts, required"/);
});

test('QAC-011: the None attestation is PER SIDE — scope both renders independent chip states', () => {
  const model = uploadModel({
    type: 'battle', scope: 'both',
    shots: { you: [], enemy: [] },
    attested: { you: true, enemy: false },
  });
  const html = renderUpload({ type: 'battle', model });
  const youCard = html.split('data-group="you"')[1].split('</section>')[0];
  const enemyCard = html.split('data-group="enemy"')[1].split('</section>')[0];
  assert.match(youCard, /data-slot="you:buffs" data-slot-state="none"/);
  assert.match(enemyCard, /data-slot="enemy:buffs" data-slot-state="empty"/);
  assert.match(enemyCard, /data-slot-none="enemy:buffs"[^>]*aria-pressed="false"/);
  // one side attested + nothing else -> 1 of 6, never 2
  assert.equal(model.done, 1);
  assert.equal(model.total, 6);
});

test('QAC-011 back-compat: a boolean attested still means both sides (same-report default)', () => {
  const model = uploadModel({ type: 'battle', shots: { you: [], enemy: [] }, attested: true });
  const buffs = model.groups[0].slots.find((s) => s.key === 'buffs');
  assert.equal(buffs.state, 'none');
  assert.equal(model.done, 1);
});

test('renderUpload: the notice slot renders when given, absent when null', () => {
  const withNotice = renderUpload({
    type: 'battle', model: uploadModel({ type: 'battle', shots: { you: [], enemy: [] } }),
    notice: 'Removed. Add a new one.',
  });
  assert.match(withNotice, /id="ocrfS2Notice">Removed\. Add a new one\.</);
  assert.doesNotMatch(battleHtml(), /ocrfS2Notice/);
});

// --- Word budget: the owner dictated full upload instructions per row and
// the scope question (2026-08-30) — every word still has to earn its place;
// the default battle screen stays under 70 visible words. The drawn Troops
// mini-panel is excluded: it stands in for an IMAGE (zero words once the
// real capture ships), not for copy.
test('word budget: the entire default battle upload screen shows fewer than 70 visible words', () => {
  const html = battleHtml().replace(/<div class="ocrf-mini-panel[\s\S]*?<\/div><\/div>/g, ' ');
  const text = html.replace(/<[^>]+>/g, ' ');
  const words = text.split(/\s+/).filter((w) => /[a-zA-Z]/.test(w));
  assert.ok(words.length < 70, `${words.length} words: ${words.join(' ')}`);
});

// --- E1: minimal words, targets the combined s1 screen --------------------

test('renderE1("wrong"): keyword copy, Retake/Try-again paths target s1 (the merged screen), Type instead fallback', () => {
  const html = renderE1('wrong');
  assert.match(html, /Wrong screenshot/);
  assert.match(html, /data-goto="s1" data-recovery="1">\s*Retake</);
  assert.match(html, /data-goto="s4" data-show-missing="1">Type instead</);
});

test('renderE1("partial"): says the read fraction and offers Type the rest / Retake', () => {
  const html = renderE1('partial', { okCount: 9, total: 24 });
  assert.match(html, /Some numbers missing/);
  assert.match(html, /We read 9 of 24\./);
  assert.match(html, /data-goto="s4" data-show-missing="1">Type the rest</);
  assert.match(html, /data-goto="s1" data-recovery="1">Retake</);
});

test('renderE1("error", mapped): mapped heading/body verbatim; every cta variant wires its own buttons', () => {
  const mapped = { heading: 'Out of reads', body: 'Resets tomorrow.', cta: 'wait' };
  const html = renderE1('error', { mapped });
  assert.match(html, /Out of reads/);
  assert.match(html, /Resets tomorrow\./);
  assert.match(html, /data-goto="s4" data-show-missing="1">Type instead</);

  const upgrade = renderE1('error', { mapped: { heading: 'h', body: 'b', cta: 'upgrade' } });
  assert.match(upgrade, /id="ocrfE1Upgrade">See plans</);

  const retake = renderE1('error', { mapped: { heading: 'h', body: 'b', cta: 'retake' } });
  assert.match(retake, /data-goto="s1" data-recovery="1">Retake</);

  const retry = renderE1('error', { mapped: { heading: 'h', body: 'b', cta: 'retry_or_type' } });
  assert.match(retry, /data-goto="s3">Try again</);
});

// --- missing prompt (owner 2026-09-06) ---------------------------------------

test('missingList: names exactly the required rows still empty, grouped by card label', () => {
  const both = uploadModel({
    type: 'battle', scope: 'both', attested: { you: true, enemy: false },
    shots: { you: [{ slot: 'heroes' }], enemy: [] },
  });
  assert.deepEqual(missingList(both), ['Your report: Stats', "Enemy's report: Heroes + Experts, Stats, Buffs"]);
  const mine = uploadModel({ type: 'battle', shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }, { slot: 'buffs' }], enemy: [] } });
  assert.deepEqual(missingList(mine), []);   // optional Troops never counts as missing
  const scout = uploadModel({ type: 'scout', shots: { you: [{ slot: 'scout' }], enemy: [] } });
  assert.deepEqual(missingList(scout), ['Enemy: Combat stats']);
});
