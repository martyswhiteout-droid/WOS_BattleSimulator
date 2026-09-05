// tests for screens/pick_upload.mjs — TWO cards on one screen (owner
// 2026-09-06, designer spec): your report / the enemy's report, each with
// its own type selector, requirement rows, L/R column pill (battle) and
// the enemy's "Use your report for the enemy too" box.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  SLOTS, cardsFor, cardTitle, otherColumn, slotState, uploadModel, missingList,
  renderUpload, renderE1, TAB_LABEL, TYPES, DEFAULT_COLUMNS,
} from '../screens/pick_upload.mjs';

const BB = { you: 'battle', enemy: 'battle' };
const EMPTY = { you: [], enemy: [] };
const htmlOf = (over = {}) => renderUpload({ model: uploadModel({ types: BB, shots: EMPTY, ...over }), ...over.render });
const card = (html, side) => html.split(`data-group="${side}"`)[1].split('</section>')[0];

// --- slot config (unchanged, owner-approved) --------------------------------

test('battle slots: Heroes + Experts / Stats / Buffs / Troops; heroes required, troops optional, buffs noneable up to 2', () => {
  assert.deepEqual(SLOTS.battle.map((s) => s.key), ['heroes', 'stats', 'buffs', 'power']);
  assert.deepEqual(SLOTS.battle.map((s) => s.label), ['Heroes + Experts', 'Stats', 'Buffs', 'Troops']);
  const byKey = Object.fromEntries(SLOTS.battle.map((s) => [s.key, s]));
  assert.equal(byKey.heroes.required, true);
  assert.equal(byKey.power.required, false);
  assert.equal(byKey.buffs.noneable, true);
  assert.equal(byKey.buffs.max, 2);
});

test('slot labels stay short (<=3 words) and hints stay instructions (<=10 words)', () => {
  for (const type of Object.keys(SLOTS)) {
    for (const s of SLOTS[type]) {
      assert.ok(s.label.trim().split(/\s+/).filter((w) => /[a-zA-Z]/.test(w)).length <= 3, s.label);
      for (const h of [s.hint, s.hintEnemy].filter(Boolean)) {
        assert.ok(h.split(/\s+/).filter((w) => /[a-zA-Z0-9]/.test(w)).length <= 10, h);
      }
    }
  }
});

// --- cards model --------------------------------------------------------------

test('cardTitle: the owner\'s sentence with the noun swapped per type', () => {
  assert.equal(cardTitle('you', 'battle'), 'Upload screenshots of your battle report');
  assert.equal(cardTitle('enemy', 'battle'), "Upload screenshots of the enemy's battle report");
  assert.equal(cardTitle('you', 'scout'), 'Upload screenshots of your scout report');
  assert.equal(cardTitle('enemy', 'citystats'), "Upload screenshots of the enemy's City Stats");
});

test('cardsFor: two cards always; battle cards carry the column pill (you L / enemy R by default); the same-report box only when BOTH are battle', () => {
  const [you, enemy] = cardsFor({ types: BB });
  assert.equal(you.side, 'you'); assert.equal(enemy.side, 'enemy');
  assert.equal(you.showCol, true); assert.equal(you.column, 'L');
  assert.equal(enemy.showCol, true); assert.equal(enemy.column, 'R');
  assert.equal(enemy.showSame, true); assert.equal(enemy.sameActive, false);
  assert.equal(enemy.rowsHidden, false);
  assert.deepEqual(DEFAULT_COLUMNS, { you: 'L', enemy: 'R' });

  const mixed = cardsFor({ types: { you: 'battle', enemy: 'scout' } });
  assert.equal(mixed[1].showCol, false);
  assert.equal(mixed[1].showSame, false);
  assert.equal(mixed[1].slots[0].key, 'scout');
  assert.equal(mixed[1].slots[0].hint, "Upload the scout report showing the enemy's stats");
});

test('cardsFor: box on -> enemy rows hidden, its column DERIVED as the other column of yours and locked', () => {
  const [, enemy] = cardsFor({ types: BB, columns: { you: 'L', enemy: 'L' }, sameReport: true });
  assert.equal(enemy.sameActive, true);
  assert.equal(enemy.rowsHidden, true);
  assert.equal(enemy.colLocked, true);
  assert.equal(enemy.column, 'R');   // derived, ignoring the stored enemy L
  const [, enemy2] = cardsFor({ types: BB, columns: { you: 'R', enemy: 'R' }, sameReport: true });
  assert.equal(enemy2.column, 'L');
  // the flag is inert (remembered but not applied) when either card is not battle
  const [, enemy3] = cardsFor({ types: { you: 'citystats', enemy: 'battle' }, sameReport: true });
  assert.equal(enemy3.sameActive, false);
  assert.equal(enemy3.rowsHidden, false);
  assert.equal(enemy3.showSame, false);
  assert.equal(otherColumn('L'), 'R'); assert.equal(otherColumn('R'), 'L');
});

test('slotState: empty -> added (with count) -> and "none" only for a noneable slot with the attestation on', () => {
  const buffs = SLOTS.battle.find((s) => s.key === 'buffs');
  const heroes = SLOTS.battle.find((s) => s.key === 'heroes');
  assert.deepEqual(slotState(buffs, [], false), { state: 'empty', count: 0 });
  assert.deepEqual(slotState(buffs, [{ slot: 'buffs' }], false), { state: 'added', count: 1 });
  assert.deepEqual(slotState(buffs, [], true), { state: 'none', count: 0 });
  assert.deepEqual(slotState(heroes, [], true), { state: 'empty', count: 0 });
  assert.deepEqual(slotState(heroes, [{ slot: 'stats' }], false), { state: 'empty', count: 0 });
});

test('uploadModel: default battle/battle needs 6 (3 per card); box on needs 3; mixed types count each card\'s own rows', () => {
  const dflt = uploadModel({ types: BB, shots: EMPTY });
  assert.equal(dflt.total, 6); assert.equal(dflt.done, 0); assert.equal(dflt.canScan, false);
  const same = uploadModel({ types: BB, shots: EMPTY, sameReport: true });
  assert.equal(same.total, 3);
  const mixed = uploadModel({ types: { you: 'battle', enemy: 'scout' }, shots: EMPTY });
  assert.equal(mixed.total, 4);
  const ready = uploadModel({
    types: BB, sameReport: true, attested: true,
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] },
  });
  assert.equal(ready.done, 3); assert.equal(ready.canScan, true);
  // optional Troops never counts
  const full = uploadModel({ types: BB, sameReport: true,
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }, { slot: 'buffs' }], enemy: [] } });
  assert.equal(full.total, 3); assert.equal(full.canScan, true);
});

test('uploadModel: the enemy card\'s parked shots do not count while the box is on, and come back when it is off', () => {
  const shots = { you: [{ slot: 'heroes' }], enemy: [{ slot: 'heroes' }, { slot: 'stats' }] };
  assert.equal(uploadModel({ types: BB, shots, sameReport: true }).done, 1);
  assert.equal(uploadModel({ types: BB, shots, sameReport: false }).done, 3);
});

test('QAC-011: the None attestation is PER SIDE — a boolean means both, an object keys by side', () => {
  const m = uploadModel({ types: BB, shots: EMPTY, attested: { you: true, enemy: false } });
  assert.equal(m.cards[0].slots.find((s) => s.key === 'buffs').state, 'none');
  assert.equal(m.cards[1].slots.find((s) => s.key === 'buffs').state, 'empty');
  assert.equal(m.done, 1);
  const both = uploadModel({ types: BB, shots: EMPTY, attested: true });
  assert.equal(both.done, 2);
});

// --- missing prompt -----------------------------------------------------------

test('missingList: a card with nothing done -> its noun; partly done -> one item per empty required row; hidden enemy skipped', () => {
  assert.deepEqual(missingList(uploadModel({ types: BB, shots: EMPTY })),
    ['your battle report', "enemy's battle report"]);
  assert.deepEqual(missingList(uploadModel({ types: BB, shots: { you: [{ slot: 'heroes' }], enemy: [] } })),
    ['your Stats', 'your Buffs', "enemy's battle report"]);
  assert.deepEqual(missingList(uploadModel({ types: { you: 'battle', enemy: 'scout' },
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }, { slot: 'buffs' }], enemy: [] } })),
    ["enemy's scout report"]);
  assert.deepEqual(missingList(uploadModel({ types: BB, sameReport: true,
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] } })), ['your Buffs']);
  assert.deepEqual(missingList(uploadModel({ types: BB, sameReport: true, attested: true,
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] } })), []);
});

// --- renderUpload -------------------------------------------------------------

test('renderUpload: two cards on one screen — owner titles, no overarching tabs, no intro, no scope pills', () => {
  const html = htmlOf();
  assert.equal((html.match(/class="ocrf-req-card /g) || []).length, 2);
  assert.match(html, /Upload screenshots of your battle report/);
  assert.match(html, /Upload screenshots of the enemy's battle report/);
  assert.doesNotMatch(html, /data-type-tab=/);
  assert.doesNotMatch(html, /ocrf-upload-intro/);
  assert.doesNotMatch(html, /data-scope=/);
  assert.doesNotMatch(html, /Whose battle report/);
  assert.match(html, /ocrf-req-cards ocrf-req-cards--two/);
  assert.match(html, /<h1 tabindex="-1">Screenshots<\/h1>/);
});

test('renderUpload: each card has its own type radiogroup with its type checked', () => {
  const html = renderUpload({ model: uploadModel({ types: { you: 'battle', enemy: 'citystats' }, shots: EMPTY }) });
  const you = card(html, 'you'); const enemy = card(html, 'enemy');
  assert.match(you, /role="radiogroup" aria-label="Your report type"/);
  assert.match(you, /data-type="you:battle" aria-checked="true"/);
  assert.match(enemy, /data-type="enemy:citystats" aria-checked="true"/);
  assert.match(enemy, /data-type="enemy:battle" aria-checked="false"/);
  assert.match(enemy, /Upload screenshots of the enemy's City Stats/);
  assert.match(enemy, /data-slot-tile="enemy:city"/);
  assert.deepEqual(TYPES, ['battle', 'scout', 'citystats']);
  assert.deepEqual(Object.values(TAB_LABEL), ['Battle Report', 'Scout Report', 'City Stats']);
});

test('renderUpload: L/R pill on battle cards — a sentence with L left / R right, faction class, defaults you L / enemy R', () => {
  const html = htmlOf();
  const you = card(html, 'you'); const enemy = card(html, 'enemy');
  assert.match(you, /class="ocrf-col ocrf-col--you"[^>]*aria-label="Your stats column">Your stats are in the/);
  assert.match(you, /data-col="you:L" aria-checked="true"/);
  assert.match(you, /data-col="you:R" aria-checked="false"/);
  assert.ok(you.indexOf('data-col="you:L"') < you.indexOf('data-col="you:R"'));   // L is on the left
  assert.match(enemy, /Enemy's stats are in the/);
  assert.match(enemy, /data-col="enemy:R" aria-checked="true"/);
  // the sample wash follows the column
  assert.match(you, /ocrf-req-fig ocrf-req-fig--L ocrf-req-fig--you/);
  assert.match(enemy, /ocrf-req-fig ocrf-req-fig--R ocrf-req-fig--enemy/);
  // no pill on single-column types
  const scout = renderUpload({ model: uploadModel({ types: { you: 'scout', enemy: 'battle' }, shots: EMPTY }) });
  assert.doesNotMatch(card(scout, 'you'), /data-col=/);
});

test('renderUpload: the same-report box lives on the enemy card, unchecked by default, only when both cards are battle', () => {
  const html = htmlOf();
  const enemy = card(html, 'enemy');
  assert.match(enemy, /role="checkbox"\s+data-same aria-checked="false"/);
  assert.match(enemy, /Use your report for the enemy too/);
  assert.doesNotMatch(card(html, 'you'), /data-same/);
  const mixed = renderUpload({ model: uploadModel({ types: { you: 'scout', enemy: 'battle' }, shots: EMPTY }) });
  assert.doesNotMatch(mixed, /data-same/);
});

test('renderUpload: box on -> enemy rows gone, count gone, pill locked to the mirror column', () => {
  const html = renderUpload({ model: uploadModel({ types: BB, shots: EMPTY, sameReport: true, columns: { you: 'R', enemy: 'R' } }) });
  const enemy = card(html, 'enemy');
  assert.match(enemy, /data-same aria-checked="true"/);
  assert.doesNotMatch(enemy, /data-slot-tile=/);
  assert.doesNotMatch(enemy, /ocrf-req-card-count/);
  assert.match(enemy, /ocrf-col--locked/);
  assert.match(enemy, /data-col="enemy:L" aria-checked="true"[^>]*aria-disabled="true"/);
  assert.match(enemy, /<span class="ocrf-col-note">set by your report<\/span>/);   // QAC-021: visible, not hover-only
  assert.doesNotMatch(card(html, 'you'), /ocrf-col-note/);
  assert.match(html, /class="ocrf-scan-count">0\/3</);
});

test('renderUpload: rows — + Add is a real button, words inert, thumbnails open the preview, sample kept', () => {
  const model = uploadModel({ types: BB, shots: { you: [{ slot: 'buffs' }, { slot: 'buffs' }, { slot: 'heroes' }], enemy: [] } });
  model.cards[0].slots.find((s) => s.key === 'buffs').thumbUrls = ['blob:one', 'blob:two'];
  const html = renderUpload({ model });
  const you = card(html, 'you');
  assert.equal((you.match(/<button type="button" class="ocrf-req-add" data-slot="you:/g) || []).length, 2);   // stats + power still open
  assert.doesNotMatch(you, /<button[^>]*class="ocrf-req-main"/);
  const heroRow = you.split('data-slot-tile="you:heroes"')[1].split('data-slot-tile')[0];
  assert.doesNotMatch(heroRow, /data-slot="you:heroes"/);          // full (max 1): no add
  assert.match(heroRow, /data-slot-preview="you:heroes"/);
  assert.match(heroRow, /data-slot-remove="you:heroes:0"/);
  const buffsRow = you.split('data-slot-tile="you:buffs"')[1].split('data-slot-tile')[0];
  assert.equal((buffsRow.match(/class="ocrf-req-thumb"/g) || []).length, 2);
  assert.match(buffsRow, /url\('blob:one'\)/);
  assert.match(buffsRow, /ocrf-req-sample/);
  assert.match(buffsRow, /data-slot-remove="you:buffs:1"/);
  // row aria prefix names the card
  assert.match(you, /aria-label="Your battle report: Heroes \+ Experts, 1 added"/);
});

test('renderUpload: None chip states — empty shows None, attested shows None ✓ and keeps + Add, a file removes the chip', () => {
  const empty = card(htmlOf(), 'you');
  assert.match(empty, /data-slot-none="you:buffs"[^>]*aria-pressed="false"[^>]*>None</);
  const att = card(renderUpload({ model: uploadModel({ types: BB, shots: EMPTY, attested: { you: true, enemy: false } }) }), 'you');
  assert.match(att, /ocrf-req-none--on/);
  assert.match(att, /data-slot="you:buffs" data-slot-state="none"/);
  const filled = card(renderUpload({ model: uploadModel({ types: BB, shots: { you: [{ slot: 'buffs' }], enemy: [] } }) }), 'you');
  assert.doesNotMatch(filled, /data-slot-none=/);
});

test("Troops row shows the owner's real Troop Power capture with the drawn stand-in declared as fallback", () => {
  const you = card(htmlOf(), 'you');
  const powerRow = you.split('data-slot-tile="you:power"')[1];
  assert.match(powerRow, /ocrf-req-sample" src="\/shell\/ocr\/client\/samples\/sample_troop_power\.jpg"/);
  assert.match(powerRow, /data-drawn="troops"/);
  assert.match(powerRow, /Troops <span class="ocrf-req-opt">optional</);
  assert.doesNotMatch(you, /ocrf-req-star/);
});

test('renderUpload: footer — Scan is aria-disabled (not disabled) with the fraction while locked; the missing line appears once something is touched or requested', () => {
  const pristine = htmlOf();
  assert.match(pristine, /id="ocrfScan" aria-disabled="true">Scan <span class="ocrf-scan-count">0\/6</);
  assert.doesNotMatch(pristine, /ocrf-missing/);
  const requested = htmlOf({ render: { showMissing: true } });
  assert.match(requested, /<button type="button" class="ocrf-missing" data-missing-jump aria-live="polite"><b>Missing:<\/b> your battle report, enemy's battle report</);
  const touched = renderUpload({ model: uploadModel({ types: { you: 'battle', enemy: 'scout' },
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }, { slot: 'buffs' }], enemy: [] } }) });
  assert.match(touched, /<b>Missing:<\/b> enemy's scout report</);
  assert.match(touched, /class="ocrf-scan-count">3\/4</);
  const ready = renderUpload({ model: uploadModel({ types: BB, sameReport: true, attested: true,
    shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] } }) });
  assert.match(ready, /id="ocrfScan">Scan</);
  assert.doesNotMatch(ready, /id="ocrfScan" aria-disabled/);   // (the locked enemy pill keeps ITS aria-disabled)
  assert.doesNotMatch(ready, /ocrf-missing/);
});

test('renderUpload: the notice slot renders when given, absent when null', () => {
  const withNotice = htmlOf({ render: { notice: 'Removed. Add a new one.' } });
  assert.match(withNotice, /id="ocrfS2Notice">Removed\. Add a new one\.</);
  assert.doesNotMatch(htmlOf(), /ocrfS2Notice/);
});

// --- word budget: two owner-dictated cards; every word still earns its place.
// The drawn stand-in is excluded (it stands in for an IMAGE).
test('word budget: each card stays under 70 visible words; the whole default screen under 150', () => {
  const html = htmlOf().replace(/<div class="ocrf-mini-panel[\s\S]*?<\/div><\/div>/g, ' ');
  const words = (s) => s.replace(/<[^>]+>/g, ' ').split(/\s+/).filter((w) => /[a-zA-Z]/.test(w));
  const you = words(card(html, 'you')); const enemy = words(card(html, 'enemy'));
  assert.ok(you.length < 70, `you ${you.length}: ${you.join(' ')}`);
  assert.ok(enemy.length < 70, `enemy ${enemy.length}: ${enemy.join(' ')}`);
  assert.ok(words(html).length < 150, `total ${words(html).length}`);
});

// --- E1 (unchanged) -----------------------------------------------------------

test('renderE1("wrong"): keyword copy, Retake targets s1, Type instead fallback', () => {
  const html = renderE1('wrong');
  assert.match(html, /Wrong screenshot/);
  assert.match(html, /data-goto="s1" data-recovery="1">\s*Retake</);
  assert.match(html, /data-goto="s4" data-show-missing="1">Type instead</);
});

test('renderE1("partial"): says the read fraction and offers Type the rest / Retake', () => {
  const html = renderE1('partial', { okCount: 9, total: 24 });
  assert.match(html, /We read 9 of 24\./);
  assert.match(html, /data-goto="s4" data-show-missing="1">Type the rest</);
  assert.match(html, /data-goto="s1" data-recovery="1">Retake</);
});

test('renderE1("error", mapped): mapped heading/body verbatim; every cta variant wires its own buttons', () => {
  const html = renderE1('error', { mapped: { heading: 'Out of reads', body: 'Resets tomorrow.', cta: 'wait' } });
  assert.match(html, /Out of reads/);
  assert.match(html, /data-goto="s4" data-show-missing="1">Type instead</);
  assert.match(renderE1('error', { mapped: { heading: 'h', body: 'b', cta: 'upgrade' } }), /id="ocrfE1Upgrade">See plans</);
  assert.match(renderE1('error', { mapped: { heading: 'h', body: 'b', cta: 'retake' } }), /data-goto="s1" data-recovery="1">Retake</);
  assert.match(renderE1('error', { mapped: { heading: 'h', body: 'b', cta: 'retry_or_type' } }), /data-goto="s3">Try again</);
});
