import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { convertSide } from '../convert_side.mjs';

const GOLD = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/panel_ocr/golden_vectors.json', import.meta.url), 'utf8'));

function flat(grouped) {
  const out = {};
  for (const [cls, stats] of Object.entries(grouped)) {
    for (const [stat, value] of Object.entries(stats)) out[`${cls}|${stat}`] = value;
  }
  return out;
}

test('scout panel type is ready, unchanged', () => {
  const a = GOLD.accounts.A;
  const stats = flat(a.scout);
  const result = convertSide({ panelType: 'scout', stats, specialsOwn: [], specialsEnemy: [], specialsObserved: 'none' });
  assert.equal(result.outcome, 'ready');
  assert.deepEqual(result.percents, stats);
});

for (const acct of ['A', 'B']) {
  test(`battle panel with specials 'read' converts to scout-net within tolerance (account ${acct})`, () => {
    const a = GOLD.accounts[acct];
    const result = convertSide({
      panelType: 'battle', stats: flat(a.battle_left),
      specialsOwn: a.specials_own, specialsEnemy: a.specials_enemy, specialsObserved: 'read',
    });
    assert.equal(result.outcome, 'ready');
    for (const cls of Object.keys(a.scout)) {
      for (const stat of Object.keys(a.scout[cls])) {
        const got = result.percents[`${cls}|${stat}`];
        assert.ok(Math.abs(got - a.scout[cls][stat]) <= 0.11, `${acct}/${cls}/${stat}: ${got} vs ${a.scout[cls][stat]}`);
      }
    }
  });
}

test('battle panel abstains when specials were not fully captured, offers the raw numbers labeled unconverted', () => {
  const a = GOLD.accounts.A;
  const battleStats = flat(a.battle_left);
  for (const observed of ['none', 'partial']) {
    const result = convertSide({ panelType: 'battle', stats: battleStats, specialsOwn: [], specialsEnemy: [], specialsObserved: observed });
    assert.equal(result.outcome, 'needs_specials');
    assert.equal(result.percents, null);
    assert.deepEqual(result.rawUnconverted, battleStats);
  }
});

test('citystats with no calibration and no scout to calibrate from needs_calibration', () => {
  const a = GOLD.accounts.A;
  const stats = { ...flat({ Troops: a.bo_troops }), ...flat(a.bo_class) };
  const result = convertSide({ panelType: 'citystats', stats, specialsOwn: a.specials_own, specialsEnemy: a.specials_enemy, specialsObserved: 'read' });
  assert.equal(result.outcome, 'needs_calibration');
});

for (const acct of ['A', 'B']) {
  test(`citystats calibrates U fresh from a same-state scout capture and reproduces scout-net (account ${acct})`, () => {
    const a = GOLD.accounts[acct];
    const stats = { ...flat({ Troops: a.bo_troops }), ...flat(a.bo_class) };
    const result = convertSide({
      panelType: 'citystats', stats,
      specialsOwn: a.specials_own, specialsEnemy: a.specials_enemy, specialsObserved: 'read',
      scoutForCalibration: flat(a.scout),
    });
    assert.equal(result.outcome, 'ready');
    for (const stat of ['Attack', 'Defense', 'Lethality', 'Health']) {
      assert.ok(Math.abs(result.calibratedU[stat] - a.U[stat]) <= 0.10, `${acct}/${stat} U`);
    }
    for (const cls of Object.keys(a.scout)) {
      for (const stat of Object.keys(a.scout[cls])) {
        const got = result.percents[`${cls}|${stat}`];
        assert.ok(Math.abs(got - a.scout[cls][stat]) <= 0.11, `${acct}/${cls}/${stat}`);
      }
    }
  });
}

test('citystats reuses an already-cached calibratedU without needing a fresh scout capture', () => {
  const a = GOLD.accounts.A;
  const stats = { ...flat({ Troops: a.bo_troops }), ...flat(a.bo_class) };
  const result = convertSide({
    panelType: 'citystats', stats,
    specialsOwn: a.specials_own, specialsEnemy: a.specials_enemy, specialsObserved: 'read',
    calibratedU: a.U,
  });
  assert.equal(result.outcome, 'ready');
  assert.equal(result.percents['Infantry|Attack'].toFixed(1), a.scout.Infantry.Attack.toFixed(1));
});

test('unknown panel type is blocked, never silently treated as anything', () => {
  const result = convertSide({ panelType: 'unknown', stats: {}, specialsOwn: [], specialsEnemy: [], specialsObserved: 'none' });
  assert.equal(result.outcome, 'blocked');
  assert.equal(result.percents, null);
});
