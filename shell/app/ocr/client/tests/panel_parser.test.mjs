import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  parseValue, matchLabel, foldSets, battleToScoutnet, calibrateU, extractPanel,
} from '../panel_parser.mjs';
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
    const [sScout, sBattle, pEnemy] = foldSets(a.specials_own, a.specials_enemy, { observed: true });
    for (const st of STATS) assert.ok(Math.abs(sScout[st] - a.S_scout[st]) < 1e-9, st);
    const scout = battleToScoutnet(a.battle_left, sScout, sBattle, pEnemy);
    for (const cls of Object.keys(a.scout))
      for (const st of STATS)
        assert.ok(Math.abs(scout[cls][st] - a.scout[cls][st]) <= 0.11, `${acct}/${cls}/${st}`);
    const U = calibrateU(a.bo_troops, a.bo_class, a.scout, a.S_scout);
    for (const st of STATS) assert.ok(Math.abs(U[st] - a.U[st]) <= 0.1, st);
  });
}

const driftShot = () => ([
  { text: 'Infantry Attack', x0: 0.05, y0: 0.100, x1: 0.40, y1: 0.130, conf: 0.99 },
  { text: 'Infantry Defense', x0: 0.05, y0: 0.150, x1: 0.40, y1: 0.180, conf: 0.99 },
  { text: '3979.1%', x0: 0.70, y0: 0.115, x1: 0.95, y1: 0.145, conf: 0.99 },
]);

test('QA defect 001: drifted value is orphaned, never misattributed', () => {
  const result = extractPanel([driftShot()], null, null);
  assert.deepEqual(result.stats, {});
  assert.ok(result.unreadable_fields.includes('stats.Infantry|Attack'));
  assert.ok(result.unreadable_fields.includes('stats.Infantry|Defense'));
  assert.deepEqual(result.warnings, ['orphan value near y=0.130']);
  assert.equal(result.status, 'failed');
});

const CLASSES = ['Infantry', 'Lancer', 'Marksman'];
const tok = (text, x0, y0, x1, y1, conf = 0.99, color = null) => ({
  text, x0, y0, x1, y1, conf, color,
});

function scoutShot() {
  const shot = [];
  let y = 0.10;
  for (const cls of CLASSES) {
    for (const [st, v] of [['Attack', '+4491.6%'], ['Defense', '+3979.1%'],
      ['Lethality', '+2794.3%'], ['Health', '+3197.4%']]) {
      shot.push(tok(`${cls} ${st}`, 0.05, y, 0.40, y + 0.03));
      shot.push(tok(v, 0.70, y, 0.95, y + 0.03, 0.97));
      y += 0.05;
    }
  }
  return shot;
}

test('QA defect 002: col_conflict is never silently attributed', () => {
  const shot = [];
  let y = 0.10;
  for (const cls of CLASSES) {
    for (const st of STATS) {
      shot.push(tok(`${cls} ${st}`, 0.38, y, 0.58, y + 0.03));
      shot.push(tok('+4859.0%', 0.03, y, 0.23, y + 0.03, 0.99, 'red'));
      shot.push(tok('+694.3%', 0.70, y, 0.90, y + 0.03, 0.99, 'green'));
      y += 0.05;
    }
  }
  const result = extractPanel([shot], 'you', null);
  assert.equal(result.panel_type, 'battle');
  assert.deepEqual(result.stats_left, {});
  assert.deepEqual(result.stats_right, {});
  assert.equal(result.status, 'failed');
  assert.ok(result.unreadable_fields.includes('stats_left.Infantry|Attack'));
  assert.ok(result.unreadable_fields.includes('stats_right.Infantry|Attack'));
});

test('QA defect 003: a third shot cannot erase a conflict', () => {
  const shot = (value) => ([
    tok('Infantry Attack', 0.05, 0.10, 0.40, 0.13),
    tok(value, 0.70, 0.10, 0.95, 0.13),
  ]);
  const result = extractPanel([shot('4491.6%'), shot('4431.6%'), shot('1111.1%')], null, null);
  assert.ok(!('Infantry|Attack' in result.stats));
  assert.ok(result.unreadable_fields.includes('stats.Infantry|Attack'));
  assert.equal(result.warnings.length, 1);
});

test('QA defect 004: bad specials are unreadable, never folded', () => {
  const lowConf = scoutShot();
  lowConf.push(tok('Attack Bonus (Pet Skill)', 0.05, 0.80, 0.40, 0.83));
  lowConf.push(tok('+10.0%', 0.70, 0.80, 0.95, 0.83, 0.05));
  let result = extractPanel([lowConf], 'you', null);
  assert.deepEqual(result.specials, []);
  assert.ok(result.unreadable_fields.includes('specials.Attack Bonus (Pet Skill)'));

  const valueless = scoutShot();
  valueless.push(tok('Defense Bonus (Pet Skill)', 0.05, 0.80, 0.40, 0.83));
  result = extractPanel([valueless], 'you', null);
  assert.deepEqual(result.specials, []);
  assert.ok(result.unreadable_fields.includes('specials.Defense Bonus (Pet Skill)'));
});

test('QA defect 006: never-seen fields are listed unreadable', () => {
  const shot = scoutShot().filter((token) => !token.text.startsWith('Marksman'));
  const result = extractPanel([shot], 'enemy', null);
  assert.equal(result.status, 'partial');
  for (const st of STATS) assert.ok(result.unreadable_fields.includes(`stats.Marksman|${st}`));
});

test('QA defect 005: unobserved empty specials refuses the identity fold', () => {
  assert.throws(() => foldSets([], [], { observed: false }), (error) => error.code === 'missing_specials');
  assert.throws(() => foldSets([], []), TypeError);
  const b = FIX.accounts.B;
  const [sScout, , pEnemy] = foldSets(b.specials_own, b.specials_enemy, { observed: true });
  for (const st of STATS) {
    assert.equal(pEnemy[st], 0.0);
    assert.ok(Math.abs(sScout[st] - b.S_scout[st]) < 1e-9, st);
  }
});

test('QA defect 005: service reports whether specials were observed', () => {
  assert.equal(extractPanel([scoutShot()], 'you', null).specials_observed, false);
  const shot = scoutShot();
  shot.push(tok('Attack Bonus (Pet Skill)', 0.05, 0.80, 0.40, 0.83));
  shot.push(tok('+10.0%', 0.70, 0.80, 0.95, 0.83, 0.05));
  const seen = extractPanel([shot], 'you', null);
  assert.deepEqual(seen.specials, []);
  assert.equal(seen.specials_observed, true);
});

test('QA defect 008: out-of-range values are unreadable', () => {
  const shot = scoutShot();
  shot[1].text = '-4491.6%';
  shot[3].text = '999999999%';
  const result = extractPanel([shot], 'enemy', null);
  assert.ok(!('Infantry|Attack' in result.stats));
  assert.ok(!('Infantry|Defense' in result.stats));
  assert.ok(result.unreadable_fields.includes('stats.Infantry|Attack'));
  assert.ok(result.unreadable_fields.includes('stats.Infantry|Defense'));
  assert.equal(result.status, 'partial');

  const endpoints = scoutShot();
  endpoints[1].text = '0.0%';
  endpoints[3].text = '6000.0%';
  const kept = extractPanel([endpoints], 'enemy', null);
  assert.equal(kept.stats['Infantry|Attack'], 0.0);
  assert.equal(kept.stats['Infantry|Defense'], 6000.0);
  assert.equal(kept.status, 'ok');
});

test('QA defect 008: implausible special is unreadable', () => {
  const shot = scoutShot();
  shot.push(tok('Attack Bonus (Pet Skill)', 0.05, 0.80, 0.40, 0.83));
  shot.push(tok('+250.0%', 0.70, 0.80, 0.95, 0.83));
  shot.push(tok('Defense Bonus (Pet Skill)', 0.05, 0.86, 0.40, 0.89));
  shot.push(tok('+10.0%', 0.70, 0.86, 0.95, 0.89));
  const result = extractPanel([shot], 'you', null);
  assert.deepEqual(result.specials, [{ label: 'Defense Bonus (Pet Skill)', value: 10.0 }]);
  assert.ok(result.unreadable_fields.includes('specials.Attack Bonus (Pet Skill)'));
});

test('QA defect 009: non-ASCII digits never parse (pinned in both languages)', () => {
  assert.equal(parseValue('٤٤٩١%'), null);
  assert.equal(parseValue('٤٤٩١'), null);
  assert.equal(parseValue('４４９１％'), null);
  assert.equal(parseValue('４４９１%'), null);
});
