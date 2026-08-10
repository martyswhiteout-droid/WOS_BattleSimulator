import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createController } from '../controller.mjs';

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
