// tests for screens/pick_upload.mjs — TWO cards on one screen (owner
// 2026-09-06, designer spec): your report / the enemy's report, each with
// its own type selector, requirement rows, L/R column pill (battle) and
// the enemy's "Use your report for the enemy too" box.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  SLOTS, cardsFor, cardTitle, otherColumn, slotState, uploadModel, missingList,
  renderUpload, wireUpload, renderE1, TAB_LABEL, TYPES, DEFAULT_COLUMNS, slotHasRoom, pasteWellHtml,
  mirrorConfirmHtml, sameHintFor, SAME_POINTER_HTML,
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

// --- desktop paste wells (UX_START_JOURNEY_SPEC.md §3.3, owner 2026-09-20:
// "there's no place for them to paste it... on mobile you should not be
// allowed to do that"). Default paste is OFF (every test above, and the
// mobile render, must stay byte-identical to before this round). ------------

test('slotHasRoom: room iff not attested "none" and not yet at max — the exact predicate pasteTargetSlot (ocr_flow.js) uses to pick where a paste lands', () => {
  assert.equal(slotHasRoom({ state: 'empty', count: 0, max: 1 }), true);
  assert.equal(slotHasRoom({ state: 'added', count: 1, max: 2 }), true);
  assert.equal(slotHasRoom({ state: 'added', count: 1, max: 1 }), false);
  assert.equal(slotHasRoom({ state: 'none', count: 0, max: 2 }), false);
});

test('pasteWellHtml: armed shows platform keycaps + "Paste here" and the ice/ember faction class; un-armed shows only the glyph, no words', () => {
  const armedYou = pasteWellHtml({ side: 'you', key: 'heroes', label: 'Heroes + Experts', armed: true, mac: false });
  assert.match(armedYou, /class="ocrf-paste-well ocrf-paste-well--armed ocrf-paste-well--you"/);
  assert.match(armedYou, /<kbd>Ctrl<\/kbd><kbd>V<\/kbd>/);
  assert.match(armedYou, /Paste here/);
  assert.match(armedYou, /data-paste-slot="you:heroes"/);
  assert.match(armedYou, /aria-label="Paste a screenshot into Your Heroes \+ Experts"/);
  const armedMac = pasteWellHtml({ side: 'enemy', key: 'stats', label: 'Stats', armed: true, mac: true });
  assert.match(armedMac, /<kbd>⌘<\/kbd><kbd>V<\/kbd>/);
  assert.doesNotMatch(armedMac, /Ctrl/);
  assert.match(armedMac, /ocrf-paste-well--enemy/);
  assert.match(armedMac, /aria-label="Paste a screenshot into Enemy's Stats"/);
  const unarmed = pasteWellHtml({ side: 'you', key: 'power', label: 'Troops', armed: false, mac: false });
  assert.doesNotMatch(unarmed, /ocrf-paste-well--armed/);
  assert.doesNotMatch(unarmed, /Paste here|Ctrl|<kbd>/);
  assert.match(unarmed, /<svg class="ocrf-paste-ic"/);
});

test('renderUpload: paste off (default) never emits a well — byte-identical to every pre-existing test above', () => {
  assert.doesNotMatch(htmlOf(), /ocrf-paste-well/);
  assert.doesNotMatch(htmlOf(), /ocrf-paste-row/);
});

test('renderUpload: paste on renders exactly one armed well (pasteTargetSlot\'s own pick) and a well on every OTHER row with room, on both cards', () => {
  const html = renderUpload({ model: uploadModel({ types: BB, shots: EMPTY }), paste: { on: true, armed: 'you:heroes', mac: false } });
  assert.equal((html.match(/data-paste-slot="/g) || []).length, 8);   // 4 rows x 2 cards, all empty -> all have room
  assert.equal((html.match(/ocrf-paste-well--armed/g) || []).length, 1);
  const you = card(html, 'you');
  const heroRow = you.split('data-slot-tile="you:heroes"')[1].split('data-slot-tile')[0];
  assert.match(heroRow, /ocrf-paste-well--armed/);
  assert.match(heroRow, /Paste here/);
  const statsRow = you.split('data-slot-tile="you:stats"')[1].split('data-slot-tile')[0];
  assert.doesNotMatch(statsRow, /ocrf-paste-well--armed/);
  assert.match(statsRow, /ocrf-paste-well/);
  assert.doesNotMatch(statsRow, /Paste here/);
  // "+ Add" moves down next to the well, never duplicated in the top cluster
  assert.equal((heroRow.match(/ocrf-req-add/g) || []).length, 1);
  assert.match(heroRow, /ocrf-paste-row"><button[^>]*ocrf-paste-well[\s\S]*ocrf-req-add/);
});

test('renderUpload: no well on a row with no room — already full, or attested "none"', () => {
  const html = renderUpload({
    model: uploadModel({ types: BB, shots: { you: [{ slot: 'heroes' }], enemy: [] }, attested: { you: true, enemy: false } }),
    paste: { on: true, armed: 'you:stats', mac: false },
  });
  const you = card(html, 'you');
  const heroRow = you.split('data-slot-tile="you:heroes"')[1].split('data-slot-tile')[0];   // full: max 1, count 1
  assert.doesNotMatch(heroRow, /ocrf-paste-well/);
  const buffsRow = you.split('data-slot-tile="you:buffs"')[1].split('data-slot-tile')[0];   // attested none
  assert.doesNotMatch(buffsRow, /ocrf-paste-well/);
  const statsRow = you.split('data-slot-tile="you:stats"')[1].split('data-slot-tile')[0];   // still empty -> has room
  assert.match(statsRow, /ocrf-paste-well--armed/);
});

test('word budget: paste on adds at most 16 words over paste-off — the ONE armed well ("Ctrl V Paste here") plus the first-use tip line, both gone once the screen is touched (un-armed wells are glyph + aria-label only, both stripped by the word-count regex)', () => {
  const words = (s) => s.replace(/<[^>]+>/g, ' ').split(/\s+/).filter((w) => /[a-zA-Z]/.test(w));
  const strip = (s) => s.replace(/<div class="ocrf-mini-panel[\s\S]*?<\/div><\/div>/g, ' ');
  const offCount = words(strip(htmlOf())).length;
  const onHtml = strip(renderUpload({ model: uploadModel({ types: BB, shots: EMPTY }), paste: { on: true, armed: 'you:heroes', mac: false } }));
  const onCount = words(onHtml).length;
  assert.ok(onCount - offCount <= 16, `+${onCount - offCount} words (off ${offCount}, on ${onCount})`);
});

// --- first-use tip (§3.3 orchestrator polish, 2026-09-21): one line under
// the h1, only while paste is on AND the screen is untouched. -------------

test('renderUpload: the first-use paste tip shows only when paste is on and nothing has been touched yet, Mac keycap swapped, gone once a shot lands', () => {
  const untouched = uploadModel({ types: BB, shots: EMPTY });
  const withTip = renderUpload({ model: untouched, paste: { on: true, armed: 'you:heroes', mac: false } });
  assert.match(withTip, /id="ocrfPasteTip">Paste with Ctrl\+V, drop files, or use \+ Add\.</);
  const macTip = renderUpload({ model: untouched, paste: { on: true, armed: 'you:heroes', mac: true } });
  assert.match(macTip, /Paste with ⌘V, drop files, or use \+ Add\./);
  // paste off: no tip at all
  assert.doesNotMatch(htmlOf(), /ocrfPasteTip/);
  // paste on but touched (a shot already landed): tip is gone
  const touched = uploadModel({ types: BB, shots: { you: [{ slot: 'heroes' }], enemy: [] } });
  assert.equal(touched.touched, true);
  assert.doesNotMatch(renderUpload({ model: touched, paste: { on: true, armed: 'you:stats', mac: false } }), /ocrfPasteTip/);
});

// --- UXE-008 (Gate-1 UX round 1): a row that takes more than one file says
// so in digits, beside its title. Digits only - no words, so the word-budget
// tests above are unaffected by construction (their regex keeps only tokens
// containing a letter). Absent on single-file rows.

test('UXE-008: rows with max > 1 carry a digits-only counter beside the title; single-file rows carry none', () => {
  const empty = renderUpload({ model: uploadModel({ types: BB, shots: EMPTY }) });
  const you = card(empty, 'you');
  const row = (html, key) => html.split(`data-slot-tile="you:${key}"`)[1].split('data-slot-tile')[0];
  assert.match(row(you, 'stats'), /class="ocrf-req-count">0\/2</);      // muted at zero
  assert.match(row(you, 'buffs'), /class="ocrf-req-count">0\/2</);
  assert.doesNotMatch(row(you, 'heroes'), /ocrf-req-count/);            // max 1 - nothing at all
  assert.doesNotMatch(row(you, 'power'), /ocrf-req-count/);
  // partially full -> faction-tinted; satisfied -> the ok tint
  const part = card(renderUpload({ model: uploadModel({ types: BB, shots: { you: [{ slot: 'stats' }], enemy: [] } }) }), 'you');
  assert.match(row(part, 'stats'), /class="ocrf-req-count ocrf-req-count--part">1\/2</);
  const full = card(renderUpload({ model: uploadModel({ types: BB, shots: { you: [{ slot: 'stats' }, { slot: 'stats' }], enemy: [] } }) }), 'you');
  assert.match(row(full, 'stats'), /class="ocrf-req-count ocrf-req-count--full">2\/2</);
  // it is inside the row's own name element, not a new line of its own
  assert.match(row(you, 'stats'), /class="ocrf-req-name">Stats <span class="ocrf-req-count">0\/2<\/span>/);
});

// --- UXE-015 (Gate-1 UX round 1): the remove control is a real sibling
// button OUTSIDE the thumbnail image (it used to be a 20px badge painted
// over the very pixels it exists to let you re-check), and it says what it
// removes.

test('UXE-015: each thumbnail is a set of {image (preview + tick), remove button outside it} and the remove button names its target', () => {
  const html = renderUpload({ model: uploadModel({ types: BB, shots: { you: [{ slot: 'stats' }, { slot: 'stats' }], enemy: [] } }) });
  const row = card(html, 'you').split('data-slot-tile="you:stats"')[1].split('data-slot-tile')[0];
  assert.equal((row.match(/ocrf-req-thumb-set/g) || []).length, 2);            // one set per file
  assert.equal((row.match(/aria-label="Remove this screenshot"/g) || []).length, 2);
  assert.doesNotMatch(row, /aria-label="Remove"/);
  // the x is a SIBLING of .ocrf-req-thumb, after the image closes - never inside it
  assert.match(row, /<\/span><button type="button" class="ocrf-req-thumb-x"/);
  // the tick stays inside the image
  assert.match(row, /class="ocrf-req-tick" aria-hidden="true">&#10003;<\/span><\/span>/);
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

// --- UXE-036 (Gate-1 UX review round 2, Polish): the mirrored enemy column ---
// Measured at 1440x900 with the box ticked: your card 583px, the enemy card
// collapsed to ~165px, a ~420px void beneath it and Scan floating under
// nothing. The structure is settled (UXE-018/019 declined-accepted), so the
// fix is purely additive — a quiet confirmation of what the tick just did,
// under the collapsed card. These pin that it appears ONLY in that exact
// state, that it carries no control, and that its caption follows the mirror.

const mirrorModel = (columns = DEFAULT_COLUMNS, shots = [{ slot: 'heroes' }, { slot: 'stats' }, { slot: 'buffs' }]) => {
  const m = uploadModel({ types: BB, shots: { you: shots, enemy: [] }, sameReport: true, columns });
  const you = m.cards.find((c) => c.side === 'you');
  for (const s of shots) you.slots.find((x) => x.key === s.slot).thumbUrls = [`blob:${s.slot}`];
  return m;
};
const PASTE_ON = { on: true, armed: null, mac: false };

test('UXE-036: the mirror confirmation is ABSENT by default — not ticked, and (mobile) paste off', () => {
  assert.doesNotMatch(htmlOf(), /ocrf-mirror/);
  assert.doesNotMatch(htmlOf({ render: { paste: PASTE_ON } }), /ocrf-mirror/);
  // ticked but stacked/touch render (paste off) stays byte-identical
  assert.doesNotMatch(renderUpload({ model: mirrorModel() }), /ocrf-mirror/);
});

test('UXE-036: present only when ticked AND your card holds >=1 screenshot AND the two cards sit side by side (paste-capable desktop)', () => {
  const none = uploadModel({ types: BB, shots: EMPTY, sameReport: true });
  assert.doesNotMatch(renderUpload({ model: none, paste: PASTE_ON }), /ocrf-mirror/);
  const html = renderUpload({ model: mirrorModel(), paste: PASTE_ON });
  assert.match(html, /class="ocrf-mirror-note"/);
  // the SAME object URLs your card already renders, re-used — one per shot
  assert.equal((html.match(/class="ocrf-mirror-shot"/g) || []).length, 3);
  assert.match(html, /ocrf-mirror-shot" style="background-image:url\('blob:heroes'\)"/);
  // and it lives in the ENEMY column, under the collapsed enemy card
  assert.match(card(html, 'enemy'), /ocrf-mirror-note/);
  assert.doesNotMatch(card(html, 'you'), /ocrf-mirror-note/);
});

test('UXE-036: the caption FOLLOWS the mirror — the enemy column is whatever the mirror resolves to, flipping with your own L/R pill', () => {
  const rColumn = renderUpload({ model: mirrorModel({ you: 'L', enemy: 'R' }), paste: PASTE_ON });
  assert.match(rColumn, /<span class="ocrf-mirror-cap" role="note">READ AS THE R COLUMN<\/span>/);
  const lColumn = renderUpload({ model: mirrorModel({ you: 'R', enemy: 'L' }), paste: PASTE_ON });
  assert.match(lColumn, /<span class="ocrf-mirror-cap" role="note">READ AS THE L COLUMN<\/span>/);
});

test('UXE-036: the block is evidence, not a control — no button, input, picker trigger, remove/preview hook or focusable node anywhere in it', () => {
  const block = mirrorConfirmHtml(mirrorModel(), PASTE_ON);
  assert.doesNotMatch(block, /<button|<input|<a |tabindex|data-slot|data-paste-slot|data-same|data-type|data-col/);
  assert.match(block, /aria-hidden="true"/);   // the thumbnails are decorative
  // <=5 words, so the screen's word budget barely moves
  const words = block.replace(/<[^>]+>/g, ' ').split(/\s+/).filter((w) => /[a-zA-Z]/.test(w));
  assert.ok(words.length <= 5, `caption words ${words.length}: ${words.join(' ')}`);
});

// --- U1-M4: the same-report hint (Gate-2 round 1) ---------------------------
// Playtest evidence (mobile task 3, scored 2): your card at 3/3, the footer
// says "Missing: enemy's battle report", the tester owns exactly ONE report
// and stalls until they notice the dashed, low-contrast checkbox. The flag
// below marks that exact state so the CSS can make the EXISTING control
// louder — no new control, no new word, nothing moved (owner constraint 1).

const YOU_DONE = [{ slot: 'heroes' }, { slot: 'stats' }, { slot: 'buffs' }];
const hintOf = (over = {}) => {
  const m = uploadModel({ types: BB, shots: EMPTY, ...over });
  return m.cards.find((c) => c.side === 'enemy').sameHint;
};

test('sameHint: TRUE in exactly the stuck state — your card complete, the box shown and OFF, the enemy card completely untouched (and never on YOUR card)', () => {
  const m = uploadModel({ types: BB, shots: { you: YOU_DONE, enemy: [] } });
  const [you, enemy] = m.cards;
  assert.equal(enemy.sameHint, true);
  assert.equal(you.sameHint, false, 'the hint belongs to the enemy card only');
  // this is the state the playtest measured: 3/3 and "Missing: enemy's battle report"
  assert.equal(m.done, 3);
  assert.deepEqual(m.missing, ["enemy's battle report"]);
});

test('sameHint: a "None" buffs attestation completes your card just as a file does', () => {
  assert.equal(hintOf({ shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] },
    attested: { you: true, enemy: false } }), true);
});

test('sameHint: FALSE once the box is ticked — the user already knows, there is nothing to point at', () => {
  assert.equal(hintOf({ shots: { you: YOU_DONE, enemy: [] }, sameReport: true }), false);
});

test('sameHint: FALSE as soon as the enemy card is touched — any required file, any OPTIONAL file, or its own "None"', () => {
  assert.equal(hintOf({ shots: { you: YOU_DONE, enemy: [{ slot: 'heroes' }] } }), false);
  // Troops is optional and still counts: it is the user showing they DO have
  // an enemy report, which is precisely what the hint must stop claiming.
  assert.equal(hintOf({ shots: { you: YOU_DONE, enemy: [{ slot: 'power' }] } }), false);
  assert.equal(hintOf({ shots: { you: YOU_DONE, enemy: [] },
    attested: { you: false, enemy: true } }), false);
});

test('sameHint: FALSE while your own card is still incomplete — the enemy report is not yet the only thing left', () => {
  assert.equal(hintOf({ shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] } }), false);
  assert.equal(hintOf({ shots: { you: [{ slot: 'heroes' }], enemy: [] } }), false);
  assert.equal(hintOf({ shots: EMPTY }), false);
  // Troops alone never completes your card (it is optional).
  assert.equal(hintOf({ shots: { you: [{ slot: 'power' }], enemy: [] } }), false);
});

test('sameHint: FALSE for every card pairing that does not show the box at all (the box is battle+battle only)', () => {
  for (const types of [{ you: 'battle', enemy: 'scout' }, { you: 'citystats', enemy: 'battle' },
    { you: 'scout', enemy: 'scout' }, { you: 'citystats', enemy: 'scout' }]) {
    const m = uploadModel({ types, shots: { you: [{ slot: 'scout' }, { slot: 'city' }], enemy: [] } });
    for (const c of m.cards) assert.equal(c.sameHint, false, JSON.stringify(types));
  }
});

test('sameHintFor is pure and self-contained: it reads only the two stated cards handed to it', () => {
  const stated = (over) => uploadModel({ types: BB, shots: EMPTY, ...over }).cards;
  const on = stated({ shots: { you: YOU_DONE, enemy: [] } });
  assert.equal(sameHintFor(on[1], on), true);
  assert.equal(sameHintFor(on[0], on), false);
  // no "you" card in the list at all -> never true
  assert.equal(sameHintFor(on[1], [on[1]]), false);
});

test('renderUpload: the hint is ONE modifier class on the existing [data-same] button — the label, its place inside the enemy card and every word are byte-identical', () => {
  const lit = renderUpload({ model: uploadModel({ types: BB, shots: { you: YOU_DONE, enemy: [] } }) });
  const dark = renderUpload({ model: uploadModel({ types: BB, shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] } }) });
  assert.match(lit, /class="ocrf-req-same ocrf-req-same--hint" role="checkbox"/);
  assert.doesNotMatch(dark, /ocrf-req-same--hint/);
  // the control still lives in the ENEMY card, unticked, with its owner-approved words
  const enemyCard = card(lit, 'enemy');
  assert.match(enemyCard, /ocrf-req-same--hint/);
  assert.match(enemyCard, /aria-checked="false"/);
  assert.match(enemyCard, /Use your report for the enemy too/);
  assert.doesNotMatch(card(lit, 'you'), /ocrf-req-same/);
  // and the lit markup differs from the unlit one ONLY by that class token
  const litSame = lit.split('data-same')[0].split('<button').pop();
  const darkSame = dark.split('data-same')[0].split('<button').pop();
  assert.equal(litSame.replace(' ocrf-req-same--hint', ''), darkSame);
});

// U3D-T3 (Gate-2 round 3) revises this invariant, with the reviewer's own
// measurement in hand: the hint used to spend ZERO words, and that is exactly
// why it failed. The tester's eye was on the FOOTER - the line naming what is
// missing, beside the button it blocks - so a wordless glow on the card was
// read a beat too late ("do I have to go back into the game and take more
// screenshots?"). The hint now spends ONE thing and nothing else: the footer
// pointer. The CARDS stay byte-identical apart from the single class token (the
// box keeps its home, its words and its default-OFF - owner constraint 1), and
// the whole screen differs from the unlit render by that token plus
// SAME_POINTER_HTML, character for character.
test('word budget: the hint spends only the footer pointer - the cards stay byte-identical apart from the one class token, the whole screen differs by that token plus the pointer alone, and the lit state stays inside the owner-pinned budgets', () => {
  const litHtml = renderUpload({ model: uploadModel({ types: BB, shots: { you: YOU_DONE, enemy: [] } }) });
  const unlitHtml = renderUpload({
    model: (() => { const m = uploadModel({ types: BB, shots: { you: YOU_DONE, enemy: [] } });
      for (const c of m.cards) c.sameHint = false; return m; })(),
  });
  // the cards: not one word, node or attribute added or moved
  assert.equal(card(litHtml, 'you'), card(unlitHtml, 'you'));
  assert.equal(card(litHtml, 'enemy').replace(' ocrf-req-same--hint', ''), card(unlitHtml, 'enemy'));
  // the whole screen: the class token + the pointer, and nothing else at all
  assert.equal(litHtml.replace(' ocrf-req-same--hint', '').replace(SAME_POINTER_HTML, ''), unlitHtml);
  // the pointer's exact cost, pinned: "or tick" + the box's own seven-word
  // label, verbatim. The em dash, the quotes and the aria-hidden arrow carry no
  // letters, so they cost nothing against a word budget.
  const words = (str) => str.replace(/<[^>]+>/g, ' ').split(/\s+/).filter((w) => /[a-zA-Z]/.test(w));
  assert.deepEqual(words(SAME_POINTER_HTML),
    ['or', 'tick', '\u201cUse', 'your', 'report', 'for', 'the', 'enemy', 'too\u201d']);
  // and the live budgets the owner pinned still hold in the lit state
  const strip = (str) => str.replace(/<div class="ocrf-mini-panel[\s\S]*?<\/div><\/div>/g, ' ');
  const html = strip(litHtml);
  assert.ok(words(card(html, 'you')).length < 70, `you ${words(card(html, 'you')).length}`);
  assert.ok(words(card(html, 'enemy')).length < 70, `enemy ${words(card(html, 'enemy')).length}`);
  assert.ok(words(html).length < 150, `total ${words(html).length}`);
});

test("U3D-T3: in the sameHint moment the missing line says the answer where the question is asked - the pointer echoes the box's exact label and points at it", () => {
  const lit = renderUpload({ model: uploadModel({ types: BB, shots: { you: YOU_DONE, enemy: [] } }) });
  const line = lit.split('class="ocrf-missing"')[1].split('</button>')[0];
  assert.match(line, /<b>Missing:<\/b> enemy's battle report/);
  assert.ok(line.includes(SAME_POINTER_HTML.trim()), line);
  // the echo is the control's label, verbatim - the same string the enemy card
  // renders, so the eye can match the sentence to the box
  assert.ok(SAME_POINTER_HTML.includes('Use your report for the enemy too'));
  assert.match(card(lit, 'enemy'), /Use your report for the enemy too/);
  // the arrow is decoration, not a word a screen reader must read out
  assert.match(SAME_POINTER_HTML, /<span class="ocrf-missing-tip-arrow" aria-hidden="true">\u2191<\/span>/);
  // and it is the ONE existing jump button, not a second control with the same
  // label: the footer holds exactly the missing line and Scan, and the only
  // [data-same] on the screen is still the box inside the enemy card
  const foot = lit.split('<footer class="ocrf-scr-foot">')[1];
  assert.equal((foot.match(/<button/g) || []).length, 2);
  assert.equal((lit.match(/data-same/g) || []).length, 1);
  assert.doesNotMatch(foot, /data-same/);
  assert.match(lit, /class="ocrf-missing" data-missing-jump aria-live="polite"/);
});

test('U3D-T3: the pointer has the hint\'s own lifecycle - absent while your card is incomplete, gone the moment the box is ticked or the enemy card takes any file / "None"', () => {
  const pointerIn = (over) => renderUpload({ model: uploadModel({ types: BB, shots: EMPTY, ...over }) })
    .includes(SAME_POINTER_HTML);
  assert.equal(pointerIn({ shots: { you: YOU_DONE, enemy: [] } }), true);
  // your card not finished yet: the enemy report is not the only thing left
  assert.equal(pointerIn({ shots: { you: [{ slot: 'heroes' }, { slot: 'stats' }], enemy: [] } }), false);
  // ticked: the box has answered the question (and Scan is live anyway)
  assert.equal(pointerIn({ shots: { you: YOU_DONE, enemy: [] }, sameReport: true }), false);
  // any enemy file, required or optional, or its own "None" attestation
  assert.equal(pointerIn({ shots: { you: YOU_DONE, enemy: [{ slot: 'heroes' }] } }), false);
  assert.equal(pointerIn({ shots: { you: YOU_DONE, enemy: [{ slot: 'power' }] } }), false);
  assert.equal(pointerIn({ shots: { you: YOU_DONE, enemy: [] }, attested: { you: false, enemy: true } }), false);
  // and never where the box does not exist at all (battle+battle only)
  assert.equal(renderUpload({ model: uploadModel({ types: { you: 'battle', enemy: 'scout' },
    shots: { you: YOU_DONE, enemy: [] } }) }).includes(SAME_POINTER_HTML), false);
  // nothing touched yet: no missing line is even rendered, so no pointer
  assert.equal(htmlOf({ render: { showMissing: true } }).includes(SAME_POINTER_HTML), false);
});

test('U3D-T3: the pointer is copy, not capability - the touch render (paste OFF, the only render a phone ever gets) carries the same sentence and still no paste well', () => {
  const model = uploadModel({ types: BB, shots: { you: YOU_DONE, enemy: [] } });
  const touch = renderUpload({ model });                                   // phone/tablet: paste off
  const desk = renderUpload({ model, paste: { on: true, armed: null, mac: false } });
  assert.ok(touch.includes(SAME_POINTER_HTML));
  assert.doesNotMatch(touch, /ocrf-paste-well/);
  assert.doesNotMatch(touch, /Paste with/);
  // byte-identical footers: the pointer is not a desktop-only affordance
  const footOf = (h) => h.split('<footer class="ocrf-scr-foot">')[1];
  assert.equal(footOf(touch), footOf(desk));
});

test('renderUpload: a ticked box is never also hinted — .ocrf-req-same--on and --hint can never collide', () => {
  const on = renderUpload({ model: uploadModel({ types: BB, shots: { you: YOU_DONE, enemy: [] }, sameReport: true }) });
  assert.match(on, /ocrf-req-same ocrf-req-same--on/);
  assert.doesNotMatch(on, /ocrf-req-same--hint/);
});
