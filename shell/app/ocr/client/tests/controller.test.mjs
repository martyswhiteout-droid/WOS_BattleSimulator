import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createController, deriveViews, postSideFor } from '../controller.mjs';
import { classifyFields, ALL_FIELD_KEYS } from '../fill_mapper.mjs';

const GOLD = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/panel_ocr/golden_vectors.json', import.meta.url), 'utf8'));
const FIX = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/overlay_ui/api_samples.json', import.meta.url), 'utf8'));

function memoryStorage() {
  const map = new Map();
  return { getItem: (k) => (map.has(k) ? map.get(k) : null), setItem: (k, v) => map.set(k, v) };
}

test('checkAccess reports plan and allowed from the injected /shell/me', async () => {
  const proController = createController({ fetchMe: async () => ({ user: { plan: 'pro', user_id: 'u1' } }) });
  assert.deepEqual(await proController.checkAccess(), { allowed: true, plan: 'pro', reachable: true, userId: 'u1' });

  const freeController = createController({ fetchMe: async () => ({ user: { plan: 'free', user_id: 'u2' } }) });
  const freeResult = await freeController.checkAccess();
  assert.equal(freeResult.allowed, false);

  const offlineController = createController({ fetchMe: async () => { throw new Error('network down'); } });
  const offlineResult = await offlineController.checkAccess();
  assert.equal(offlineResult.allowed, false);
  assert.equal(offlineResult.reachable, false);
});

test('readAll calls postPanel exactly once per side that has bytes, and returns the raw server result untouched (server-only v1, COORDINATOR RULING 2026-08-10 #1)', async () => {
  const calls = [];
  const controller = createController({
    postPanel: async ({ side, panelType, shotBytesList }) => {
      calls.push({ side, panelType, bytes: shotBytesList.length });
      return FIX.ok.scout_you;
    },
    storage: memoryStorage(),
  });
  controller.flow.pickKind('scout');
  controller.flow.addShot('you', 's1');
  const { results, conversion } = await controller.readAll({ you: [new Uint8Array([1])] });
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], { side: 'you', panelType: 'scout', bytes: 1 });
  assert.equal(results.you.status, 'ok');
  assert.equal(conversion.you.outcome, 'ready');
  assert.equal(conversion.you.percents['Infantry|Attack'], 4491.6);
});

test('a rejected postPanel call (carrying .status/.body, the required contract) maps through error_copy — the caller never has to catch a raw throw', async () => {
  const controller = createController({
    postPanel: async () => { const err = new Error('denied'); err.status = 402; err.body = FIX.denials['402'].body; throw err; },
    storage: memoryStorage(),
  });
  controller.flow.pickKind('scout');
  controller.flow.addShot('you', 's1');
  const { results, views, conversion } = await controller.readAll({ you: [new Uint8Array([1])] });
  assert.equal(results.you.error, true);
  assert.equal(results.you.mapped.cta, 'upgrade');
  assert.equal(views.you, null);          // an errored read never fabricates a view to convert
  assert.equal(conversion.you, undefined);
});

test('readAll never calls postPanel for a side with no bytes of its own', async () => {
  let calls = 0;
  const controller = createController({ postPanel: async () => { calls += 1; return FIX.ok.scout_you; }, storage: memoryStorage() });
  controller.flow.pickKind('scout');
  controller.flow.addShot('you', 's1');
  await controller.readAll({ you: [new Uint8Array([1])] });   // no 'enemy' key
  assert.equal(calls, 1);
});

test('battle-covers-both: enemy view is derived from the same read, no second upload', async () => {
  let serverCalls = 0;
  const controller = createController({
    postPanel: async ({ side }) => {
      serverCalls += 1;
      return {
        panel_type: 'battle', requested_side: side, specials: [], specials_observed: 'read', warnings: [],
        stats_left: { 'Infantry|Attack': 4859.0 }, stats_left_conf: {},
        stats_right: { 'Infantry|Attack': 694.3 }, stats_right_conf: {},
        stats_you: { 'Infantry|Attack': 4859.0 }, stats_you_conf: {},
        stats_enemy: { 'Infantry|Attack': 694.3 }, stats_enemy_conf: {},
        specials_you: [], specials_enemy: [], field_engine: {},
        unreadable_fields: [], status: 'partial',
      };
    },
    storage: memoryStorage(),
  });
  controller.flow.pickKind('battle');
  controller.flow.addShot('you', 's1');
  assert.deepEqual(controller.flow.coverage(), { you: true, enemy: true, complete: true });
  const { views } = await controller.readAll({ you: [new Uint8Array([1])] });   // no 'enemy' key at all
  assert.equal(serverCalls, 1);      // only 'you' was uploaded
  assert.equal(views.you.stats['Infantry|Attack'], 4859.0);
  assert.equal(views.enemy.stats['Infantry|Attack'], 694.3);   // derived, no extra call
});

test('city-stats U cache round-trips through the injected storage, keyed per user', async () => {
  // Reuses account A's REAL specials rows (not an empty/invented set) — cityStatsToScoutnet's
  // S_scout term must match what U was actually calibrated against, or the round-trip is
  // mathematically meaningless even with the "right" U plugged in.
  const a = GOLD.accounts.A;
  const citystatsResult = (statsOverride) => ({
    panel_type: 'citystats', requested_side: 'you',
    specials: a.specials_own.map((s) => ({ ...s, side: null })),
    specials_observed: 'read', warnings: [],
    stats: statsOverride, field_conf: {}, field_engine: {}, unreadable_fields: [],
    status: Object.keys(statsOverride).length ? 'ok' : 'failed',
  });
  const fullCityStats = {
    'Troops|Attack': a.bo_troops.Attack, 'Troops|Defense': a.bo_troops.Defense,
    'Troops|Lethality': a.bo_troops.Lethality, 'Troops|Health': a.bo_troops.Health,
    'Infantry|Attack': a.bo_class.Infantry.Attack, 'Infantry|Defense': a.bo_class.Infantry.Defense,
    'Infantry|Lethality': a.bo_class.Infantry.Lethality, 'Infantry|Health': a.bo_class.Infantry.Health,
    'Lancer|Attack': a.bo_class.Lancer.Attack, 'Lancer|Defense': a.bo_class.Lancer.Defense,
    'Lancer|Lethality': a.bo_class.Lancer.Lethality, 'Lancer|Health': a.bo_class.Lancer.Health,
    'Marksman|Attack': a.bo_class.Marksman.Attack, 'Marksman|Defense': a.bo_class.Marksman.Defense,
    'Marksman|Lethality': a.bo_class.Marksman.Lethality, 'Marksman|Health': a.bo_class.Marksman.Health,
  };

  const storage = memoryStorage();
  const controllerA = createController({
    fetchMe: async () => ({ user: { plan: 'pro', user_id: 'acct-A' } }),
    postPanel: async () => citystatsResult(fullCityStats),
    storage,
  });
  const access = await controllerA.checkAccess();
  controllerA.flow.pickKind('citystats');
  controllerA.flow.addShot('you', 's1');
  const before = await controllerA.readAll({ you: [new Uint8Array([1])] }, access.userId);
  assert.equal(before.conversion.you.outcome, 'needs_calibration');   // nothing cached yet

  storage.setItem(`ocr_u_${access.userId}`, JSON.stringify(a.U));
  const controllerB = createController({
    postPanel: async () => citystatsResult(fullCityStats),
    storage,
  });
  const after = await controllerB.readAll({ you: [new Uint8Array([1])] }, access.userId);
  assert.equal(after.conversion.you.outcome, 'ready');
  assert.ok(Math.abs(after.conversion.you.percents['Infantry|Attack'] - a.scout.Infantry.Attack) <= 0.11);
});

// --- D-036 regression: the render path must route through deriveViews, not
// raw per-side `results`, or a battle-covered enemy column (no upload of its
// own) reads as entirely missing even though the single upload read it fine. ---

test('deriveViews is exported directly — the assembly routes S4 field-state/tally derivation through it, never raw per-side results (D-036)', () => {
  assert.equal(typeof deriveViews, 'function');
});

test('D-036 probe: a single full battle response (stats_you+stats_enemy, both 12/12) derives BOTH columns with enough data for 24/24 classifyFields, in exactly one network call', async () => {
  let serverCalls = 0;
  const fullSide = (base) => Object.fromEntries(ALL_FIELD_KEYS.map((k, i) => [k, base + i]));
  const confFor = (stats) => Object.fromEntries(Object.keys(stats).map((k) => [k, 0.95]));
  const controller = createController({
    postPanel: async ({ side }) => {
      serverCalls += 1;
      const you = fullSide(1000);
      const enemy = fullSide(100);
      return {
        panel_type: 'battle', requested_side: side, specials: [], specials_observed: 'read', warnings: [],
        stats_left: you, stats_left_conf: confFor(you),
        stats_right: enemy, stats_right_conf: confFor(enemy),
        stats_you: you, stats_you_conf: confFor(you),
        stats_enemy: enemy, stats_enemy_conf: confFor(enemy),
        specials_you: [], specials_enemy: [], field_engine: {},
        unreadable_fields: [], status: 'ok',
      };
    },
    storage: memoryStorage(),
  });
  controller.flow.pickKind('battle');
  controller.flow.addShot('you', 's1');
  const { views } = await controller.readAll({ you: [new Uint8Array([1])] });   // no 'enemy' key at all

  assert.equal(serverCalls, 1);
  assert.ok(views.enemy, 'enemy view must be derived, not left null, when the single battle upload covers it');
  assert.equal(views.enemy.stats['Infantry|Attack'], 100);
  // The whole point of D-036: the DERIVED side must carry the SAME field-tier
  // inputs (confidence + field_engine) as the directly-read side — not just
  // stats — or S4's ok/check/missing classification silently degrades for a
  // battle-covered column even though the read was complete.
  assert.ok(views.you.fieldConf && views.enemy.fieldConf, 'both views must carry fieldConf for classifyFields');
  assert.equal(views.enemy.fieldConf['Infantry|Attack'], 0.95);

  const classify = (view) => classifyFields({
    expectedKeys: ALL_FIELD_KEYS, stats: view.stats, fieldConf: view.fieldConf, fieldEngine: view.fieldEngine ?? {},
  });
  const allStates = [...Object.values(classify(views.you)), ...Object.values(classify(views.enemy))].map((f) => f.state);
  assert.equal(allStates.length, 24);
  assert.ok(allStates.every((s) => s === 'ok'), `expected 24/24 ok (both columns fully classified), got: ${JSON.stringify(allStates)}`);
});


// ---- Owner feedback 2026-08-16: the no-buffs attestation ------------------
// An explicit user claim "no buffs on either side" upgrades ONLY a silent
// absence ('none') to the legal zero-specials read state (QA D-022, attested
// by the user instead of a captured empty popup). 'partial' (rows SEEN but
// unreadable) and a real 'read' are never overridden.

test('attestedObserved: upgrades none, never partial, never read, never without the claim', () => {
  const c = createController({});
  assert.equal(c.attestedObserved('none', true), 'read');
  assert.equal(c.attestedObserved('none', false), 'none');
  assert.equal(c.attestedObserved('partial', true), 'partial');
  assert.equal(c.attestedObserved('read', true), 'read');
});

test('readAll with noBuffsAttested: a popup-less battle read converts, and the attestation is reported per side', async () => {
  const stats = {};
  for (const cls of ['Infantry', 'Lancer', 'Marksman']) {
    for (const st of ['Attack', 'Defense', 'Lethality', 'Health']) stats[`${cls}|${st}`] = 1000.0;
  }
  const fieldConf = Object.fromEntries(Object.keys(stats).map((k) => [k, 0.99]));
  const postPanel = async () => ({
    status: 'ok', panel_type: 'battle', requested_side: 'you',
    stats_left: stats, stats_left_conf: fieldConf,
    stats_right: stats, stats_right_conf: fieldConf,
    stats_you: stats, stats_you_conf: fieldConf,
    stats_enemy: stats, stats_enemy_conf: fieldConf,
    specials: [], specials_you: [], specials_enemy: [],
    specials_observed: 'none', unreadable_fields: [], warnings: [],
    field_engine: {}, engines_used: ['rapidocr'],
  });
  const c = createController({ postPanel });
  c.flow.pickKind('battle');
  const without = await c.readAll({ you: [new Uint8Array([1])] });
  assert.equal(without.conversion.you.outcome, 'needs_specials');
  const withAtt = await c.readAll({ you: [new Uint8Array([1])] }, null, { noBuffsAttested: true });
  assert.equal(withAtt.conversion.you.outcome, 'ready');
  assert.equal(withAtt.attested.you, true);
  // zero-specials fold is the identity: battle numbers pass through unchanged
  assert.equal(withAtt.conversion.you.percents['Infantry|Attack'], 1000.0);
});

test('QAC-011: a PER-SIDE noBuffsAttested object applies each flag to its own side only', async () => {
  const stats = {};
  for (const cls of ['Infantry', 'Lancer', 'Marksman']) {
    for (const st of ['Attack', 'Defense', 'Lethality', 'Health']) stats[`${cls}|${st}`] = 1000.0;
  }
  const fieldConf = Object.fromEntries(Object.keys(stats).map((k) => [k, 0.99]));
  const postPanel = async ({ side }) => ({
    status: 'ok', panel_type: 'battle', requested_side: side,
    stats_left: stats, stats_left_conf: fieldConf,
    stats_right: stats, stats_right_conf: fieldConf,
    stats_you: stats, stats_you_conf: fieldConf,
    stats_enemy: stats, stats_enemy_conf: fieldConf,
    specials: [], specials_you: [], specials_enemy: [],
    specials_observed: 'none', unreadable_fields: [], warnings: [],
    field_engine: {}, engines_used: ['rapidocr'],
  });
  const c = createController({ postPanel });
  c.flow.pickKind('battle');
  // separate reports: each side has its own bytes; only YOU attested none
  const out = await c.readAll(
    { you: [new Uint8Array([1])], enemy: [new Uint8Array([2])] },
    null, { noBuffsAttested: { you: true, enemy: false } });
  assert.equal(out.attested.you, true);
  assert.equal(out.attested.enemy, false);
  assert.equal(out.conversion.you.outcome, 'ready');
  assert.equal(out.conversion.enemy.outcome, 'needs_specials');
});

test('readAll attestation never overrides a partial read (the screen contradicts the claim)', async () => {
  const stats = { 'Infantry|Attack': 1000.0 };
  const conf = { 'Infantry|Attack': 0.99 };
  const postPanel = async () => ({
    status: 'partial', panel_type: 'battle', requested_side: 'you',
    stats_left: stats, stats_left_conf: conf,
    stats_right: stats, stats_right_conf: conf,
    stats_you: stats, stats_you_conf: conf,
    stats_enemy: stats, stats_enemy_conf: conf,
    specials: [], specials_you: [], specials_enemy: [],
    specials_observed: 'partial',
    unreadable_fields: ['specials.Attack Bonus (Pet Skill)'], warnings: [],
    field_engine: {}, engines_used: ['rapidocr'],
  });
  const c = createController({ postPanel });
  c.flow.pickKind('battle');
  const out = await c.readAll({ you: [new Uint8Array([1])] }, null, { noBuffsAttested: true });
  assert.equal(out.conversion.you.outcome, 'needs_specials');
  assert.equal(out.attested.you, false);
});


// --- L/R column selection (owner 2026-09-06) ---------------------------------

test('postSideFor: the L/R column choice flips the posted side hint; defaults are your-L / enemy-R', () => {
  assert.equal(postSideFor('you', 'L'), 'you');
  assert.equal(postSideFor('you', 'R'), 'enemy');
  assert.equal(postSideFor('enemy', 'R'), 'you');
  assert.equal(postSideFor('enemy', 'L'), 'enemy');
  assert.equal(postSideFor('you'), 'you');       // default L
  assert.equal(postSideFor('enemy'), 'you');     // default R (a report as YOU see it)
});

test('readAll posts the column-derived hint per battle card while results stay keyed by the card side', async () => {
  const stats = {};
  for (const cls of ['Infantry', 'Lancer', 'Marksman']) {
    for (const st of ['Attack', 'Defense', 'Lethality', 'Health']) stats[`${cls}|${st}`] = 1000.0;
  }
  const conf = Object.fromEntries(Object.keys(stats).map((k) => [k, 0.99]));
  const posted = [];
  const postPanel = async ({ side, panelType }) => {
    posted.push([side, panelType]);
    return {
      status: 'ok', panel_type: 'battle', requested_side: side,
      stats_left: stats, stats_left_conf: conf, stats_right: stats, stats_right_conf: conf,
      stats_you: stats, stats_you_conf: conf, stats_enemy: stats, stats_enemy_conf: conf,
      specials: [], specials_you: [], specials_enemy: [],
      specials_observed: 'read', unreadable_fields: [], warnings: [], field_engine: {}, engines_used: ['rapidocr'],
    };
  };
  const c = createController({ postPanel });
  c.flow.pickKind('battle');
  const out = await c.readAll(
    { you: [new Uint8Array([1])], enemy: [new Uint8Array([2])] },
    null, { columns: { you: 'R', enemy: 'L' } });
  // your card reading R posts 'enemy'; the enemy card reading L posts 'enemy'
  assert.deepEqual(posted, [['enemy', 'battle'], ['enemy', 'battle']]);
  assert.ok(out.results.you && out.results.enemy);   // keyed by CARD side
  assert.ok(out.views.you && out.views.enemy);
});

test('readAll defaults: both cards post side=you (your-L, enemy-R) and scout panels never flip', async () => {
  const posted = [];
  const postPanel = async ({ side, panelType }) => { posted.push([side, panelType]); return { status: 'ok', panel_type: panelType, requested_side: side, stats: {}, field_conf: {}, specials: [], specials_observed: 'read', unreadable_fields: [], warnings: [], field_engine: {}, engines_used: ['rapidocr'] }; };
  const c = createController({ postPanel });
  c.flow.pickKind('battle');
  await c.readAll({ you: [new Uint8Array([1])], enemy: [new Uint8Array([2])] });
  assert.deepEqual(posted, [['you', 'battle'], ['you', 'battle']]);
  posted.length = 0;
  c.flow.pickKind('scout');
  await c.readAll({ you: [new Uint8Array([1])], enemy: [new Uint8Array([2])] }, null, { columns: { you: 'R', enemy: 'L' } });
  assert.deepEqual(posted, [['you', 'scout'], ['enemy', 'scout']]);
});
