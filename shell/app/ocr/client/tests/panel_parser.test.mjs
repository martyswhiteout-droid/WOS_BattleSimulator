import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseValue, matchLabel, foldSets, battleToScoutnet, calibrateU } from '../panel_parser.mjs';
const FIX = JSON.parse(readFileSync(new URL('../../../../tests/fixtures/panel_ocr/golden_vectors.json', import.meta.url), 'utf8'));
const STATS = ['Attack', 'Defense', 'Lethality', 'Health'];

test('value grammar matches fixture', () => {
  for (const c of FIX.value_grammar_cases) {
    const got = parseValue(c.raw);
    if (c.value === null) assert.equal(got, null, c.raw);
    else assert.ok(got && Math.abs(got.value - c.value) < 1e-9, c.raw);
  }
});
test('labels match fixture', () => {
  for (const c of FIX.label_cases) assert.equal(matchLabel(c.raw), c.canonical, c.raw);
});
for (const acct of ['A', 'B']) {
  test(`law round-trips on account ${acct}`, () => {
    const a = FIX.accounts[acct];
    const [sScout, sBattle, pEnemy] = foldSets(a.specials_own, a.specials_enemy);
    for (const st of STATS) assert.ok(Math.abs(sScout[st] - a.S_scout[st]) < 1e-9, st);
    const scout = battleToScoutnet(a.battle_left, sScout, sBattle, pEnemy);
    for (const cls of Object.keys(a.scout))
      for (const st of STATS)
        assert.ok(Math.abs(scout[cls][st] - a.scout[cls][st]) <= 0.11, `${acct}/${cls}/${st}`);
    const U = calibrateU(a.bo_troops, a.bo_class, a.scout, a.S_scout);
    for (const st of STATS) assert.ok(Math.abs(U[st] - a.U[st]) <= 0.1, st);
  });
}
