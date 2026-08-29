// tests for screens/pick_upload.mjs — the combined slot-grid Upload screen
// (owner redesign 2026-08-29, built to the multi-doc-upload research round).
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  SLOTS, groupsFor, slotState, uploadModel, renderUpload, renderE1, TAB_LABEL,
} from '../screens/pick_upload.mjs';

// --- slot config: the owner's document list, one word per label ------------

test('battle slots: Heroes/Stats/Buffs/Power — heroes required (owner 2026-08-25), power optional, buffs noneable up to 2', () => {
  const keys = SLOTS.battle.map((s) => s.key);
  assert.deepEqual(keys, ['heroes', 'stats', 'buffs', 'power']);
  assert.deepEqual(SLOTS.battle.map((s) => s.label), ['Heroes', 'Stats', 'Buffs', 'Power']);
  const byKey = Object.fromEntries(SLOTS.battle.map((s) => [s.key, s]));
  assert.equal(byKey.heroes.required, true);
  assert.equal(byKey.stats.required, true);
  assert.equal(byKey.buffs.required, true);
  assert.equal(byKey.power.required, false);
  assert.equal(byKey.buffs.noneable, true);
  assert.equal(byKey.buffs.max, 2);
});

test('every slot label is ONE word (strict word-minimalism, owner 2026-08-29)', () => {
  for (const type of Object.keys(SLOTS)) {
    for (const s of SLOTS[type]) {
      assert.equal(s.label.trim().split(/\s+/).length, 1, `${type}:${s.key} label "${s.label}"`);
    }
  }
});

test('groupsFor: battle is ONE shared group; scout is stacked You/Enemy; citystats pairs city(you) with scout(enemy)', () => {
  const battle = groupsFor('battle');
  assert.equal(battle.length, 1);
  assert.equal(battle[0].side, 'you');
  assert.equal(battle[0].label, null);

  const scout = groupsFor('scout');
  assert.deepEqual(scout.map((g) => [g.side, g.label]), [['you', 'You'], ['enemy', 'Enemy']]);

  const city = groupsFor('citystats');
  assert.deepEqual(city.map((g) => [g.side, g.label]), [['you', 'You'], ['enemy', 'Enemy']]);
  assert.equal(city[0].slots[0].key, 'city');
  assert.equal(city[1].slots[0].key, 'scout');   // enemy side has no city screen
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

test('every row carries its in-game locator hint (<=4 words) — the "what do I screenshot" answer', () => {
  const html = battleHtml();
  for (const s of SLOTS.battle) {
    assert.match(html, new RegExp(s.hint.replace(/[.*+?^${}()|[\]\!]/g, '\$&')), s.key);
    const words = s.hint.split(/\s+/).filter((w) => /[a-zA-Z0-9]/.test(w));
    assert.ok(words.length <= 4, `${s.key} hint "${s.hint}" is ${words.length} words`);
  }
});

test('UXG-003: a slot with no sample capture yet (Power) renders NO img element — no 404 per open', () => {
  const html = battleHtml();
  const powerRow = html.split('data-slot-tile="you:power"')[1];
  assert.doesNotMatch(powerRow, /ocrf-req-sample/);
  assert.doesNotMatch(html, /sample_troop_power/);
});

test('renderUpload: type tabs are Battle/Scout/City with the active one pressed', () => {
  const html = battleHtml();
  assert.match(html, /data-type-tab="battle"[^>]*aria-pressed="true"/);
  assert.match(html, /data-type-tab="scout"[^>]*aria-pressed="false"/);
  assert.match(html, /data-type-tab="citystats"[^>]*aria-pressed="false"/);
  assert.deepEqual(Object.values(TAB_LABEL), ['Battle', 'Scout', 'City']);
});

test('renderUpload: required = * cue, optional = the one word "optional"; empty rows show the + Add chip', () => {
  const html = battleHtml();
  assert.match(html, /Heroes <span class="ocrf-req-star"/);
  assert.match(html, /Power <span class="ocrf-req-opt">optional</);
  assert.doesNotMatch(html, /Power <span class="ocrf-req-star"/);
  assert.equal((html.match(/ocrf-req-add/g) || []).length, 4);
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
  assert.match(html, /data-slot="you:heroes" data-slot-state="added"/);
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
    assert.match(html, new RegExp(`data-hint="${s.hint.replace(/[.*+?^${}()|[\]\!]/g, '\$&')}" aria-live="polite"`), s.key);
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

test('renderUpload(battle): one card, no group header (the report covers both sides)', () => {
  const html = battleHtml();
  assert.equal((html.match(/class="ocrf-req-card"/g) || []).length, 1);
  assert.doesNotMatch(html, /ocrf-req-card-head/);
});

test('renderUpload: the notice slot renders when given, absent when null', () => {
  const withNotice = renderUpload({
    type: 'battle', model: uploadModel({ type: 'battle', shots: { you: [], enemy: [] } }),
    notice: 'Removed. Add a new one.',
  });
  assert.match(withNotice, /id="ocrfS2Notice">Removed\. Add a new one\.</);
  assert.doesNotMatch(battleHtml(), /ocrfS2Notice/);
});

// --- STRICT word budget (owner): every word must earn its place. The rows
// gained <=4-word in-game locators (the crystal-clear mandate) — the whole
// battle screen still stays under 35 visible words.
test('word budget: the entire battle upload screen shows fewer than 35 visible words', () => {
  const text = battleHtml().replace(/<[^>]+>/g, ' ');
  const words = text.split(/\s+/).filter((w) => /[a-zA-Z]/.test(w));
  assert.ok(words.length < 35, `${words.length} words: ${words.join(' ')}`);
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
