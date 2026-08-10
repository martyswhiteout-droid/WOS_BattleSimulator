import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const FIX = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/overlay_ui/api_samples.json', import.meta.url), 'utf8'));
const GOLD = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/panel_ocr/golden_vectors.json', import.meta.url), 'utf8'));

test('ok samples carry the real response shape', () => {
  const scout = FIX.ok.scout_you;
  assert.equal(scout.panel_type, 'scout');
  assert.equal(scout.requested_side, 'you');
  assert.equal(scout.status, 'ok');
  assert.equal(scout.specials_observed, 'read');
  assert.equal(Object.keys(scout.stats).length, 12);
  assert.deepEqual(scout.unreadable_fields, []);

  const battle = FIX.ok.battle_specials_read;
  assert.ok('stats_left' in battle && 'stats_right' in battle);
  assert.ok('stats_you' in battle && 'stats_enemy' in battle);
  assert.ok('specials_you' in battle && 'specials_enemy' in battle);
  assert.equal(battle.specials_observed, 'read');
});

test('ok scout_you reuses golden-vector account A numbers verbatim (no invented data)', () => {
  const scout = FIX.ok.scout_you.stats;
  for (const cls of Object.keys(GOLD.accounts.A.scout)) {
    for (const stat of Object.keys(GOLD.accounts.A.scout[cls])) {
      assert.equal(scout[`${cls}|${stat}`], GOLD.accounts.A.scout[cls][stat]);
    }
  }
});

test('battle_specials_read reuses golden-vector account A battle + specials verbatim', () => {
  const b = FIX.ok.battle_specials_read;
  for (const cls of Object.keys(GOLD.accounts.A.battle_left)) {
    for (const stat of Object.keys(GOLD.accounts.A.battle_left[cls])) {
      assert.equal(b.stats_you[`${cls}|${stat}`], GOLD.accounts.A.battle_left[cls][stat]);
      assert.equal(b.stats_enemy[`${cls}|${stat}`], GOLD.accounts.A.battle_right[cls][stat]);
    }
  }
  const ownLabels = new Set(b.specials_you.map((s) => s.label));
  for (const special of GOLD.accounts.A.specials_own) assert.ok(ownLabels.has(special.label));
});

test('partial/failed samples never smuggle a value into stats', () => {
  const p = FIX.partial.scout_missing_fields;
  assert.equal(p.status, 'partial');
  for (const key of p.unreadable_fields) assert.ok(!(key.split('.')[1] in p.stats));
  assert.equal(FIX.failed.scout_failed.status, 'failed');
  assert.deepEqual(FIX.failed.scout_failed.stats, {});
});

test('denial shapes match the real HTTP contract exactly', () => {
  assert.deepEqual(FIX.denials['401'], { status: 401, body: { error: 'auth_required' } });
  assert.equal(FIX.denials['402'].status, 402);
  assert.equal(FIX.denials['402'].body.error, 'payment_required');
  assert.match(FIX.denials['402'].body.message, /Pro feature/);
  assert.equal(FIX.denials['411'].status, 411);
  assert.equal(FIX.denials['411'].body.error, 'length_required');
  assert.equal(FIX.denials['413'].status, 413);
  assert.equal(FIX.denials['413'].body.error, 'body_too_large');
  assert.equal(FIX.denials['415'].status, 415);
  assert.equal(FIX.denials['415'].body.error, 'unsupported_image_type');
  assert.equal(FIX.denials['422_side'].body.error, 'invalid_side');
  assert.equal(FIX.denials['429_quota'].status, 429);
  assert.equal(FIX.denials['429_quota'].body.error, 'quota_exhausted');
  assert.equal(FIX.denials['429_burst'].body.error, 'burst');
  assert.equal(FIX.denials['503'].status, 503);
  assert.equal(FIX.denials['503'].body.error, 'ocr_engine_unavailable');
});
