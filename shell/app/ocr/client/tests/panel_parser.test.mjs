import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  parseValue, matchLabel, foldSets, battleToScoutnet, calibrateU, extractPanel,
  CalibrationError,
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
for (const acct of ['A', 'B', 'C']) {
  test(`law round-trips on account ${acct}`, () => {
    const a = FIX.accounts[acct];
    const [sScout, sBattle, pEnemy] = foldSets(a.specials_own, a.specials_enemy, { observed: 'read' });
    for (const st of STATS) assert.ok(Math.abs(sScout[st] - a.S_scout[st]) < 1e-9, st);
    const scout = battleToScoutnet(a.battle_left, sScout, sBattle, pEnemy);
    for (const cls of Object.keys(a.scout))
      for (const st of STATS)
        assert.ok(Math.abs(scout[cls][st] - a.scout[cls][st]) <= 0.11, `${acct}/${cls}/${st}`);
  });
}
for (const acct of ['A', 'B']) {
  // Account C's hero block U is per-class (mixed-gen trio, docs/GEAR_LADDERS.md),
  // not per-stat, so calibrateU's uniformity assumption does not apply to it.
  test(`U calibrates on account ${acct}`, () => {
    const a = FIX.accounts[acct];
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
  assert.throws(() => foldSets([], [], { observed: 'none' }), (error) => error.code === 'missing_specials');
  assert.throws(() => foldSets([], []), TypeError);
  const b = FIX.accounts.B;
  const [sScout, , pEnemy] = foldSets(b.specials_own, b.specials_enemy, { observed: 'read' });
  for (const st of STATS) {
    assert.equal(pEnemy[st], 0.0);
    assert.ok(Math.abs(sScout[st] - b.S_scout[st]) < 1e-9, st);
  }
});

test('QA defect 005: service reports whether specials were observed', () => {
  assert.equal(extractPanel([scoutShot()], 'you', null).specials_observed, 'none');
  const shot = scoutShot();
  shot.push(tok('Attack Bonus (Pet Skill)', 0.05, 0.80, 0.40, 0.83));
  shot.push(tok('+10.0%', 0.70, 0.80, 0.95, 0.83, 0.05));
  const seen = extractPanel([shot], 'you', null);
  assert.deepEqual(seen.specials, []);
  assert.equal(seen.specials_observed, 'partial');
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
  assert.equal(parseValue('Ù¤Ù¤Ù©Ù¡%'), null);
  assert.equal(parseValue('Ù¤Ù¤Ù©Ù¡'), null);
  assert.equal(parseValue('ï¼”ï¼”ï¼™ï¼‘ï¼…'), null);
  assert.equal(parseValue('ï¼”ï¼”ï¼™ï¼‘%'), null);
});

function battleShot() {
  const shot = [];
  let y = 0.10;
  for (const cls of CLASSES) {
    for (const st of STATS) {
      shot.push(tok(`${cls} ${st}`, 0.38, y, 0.58, y + 0.03));
      shot.push(tok('+4859.0%', 0.03, y, 0.23, y + 0.03, 0.99, 'green'));
      shot.push(tok('+694.3%', 0.70, y, 0.90, y + 0.03, 0.99, 'red'));
      y += 0.05;
    }
  }
  return shot;
}

test('QA defect 011: requested_side echoed, you/enemy aliased both ways', () => {
  const you = extractPanel([battleShot()], 'you', null);
  assert.equal(you.requested_side, 'you');
  assert.deepEqual(you.stats_you, you.stats_left);
  assert.deepEqual(you.stats_enemy, you.stats_right);
  assert.deepEqual(you.stats_you_conf, you.stats_left_conf);

  const enemy = extractPanel([battleShot()], 'enemy', null);
  assert.equal(enemy.requested_side, 'enemy');
  assert.deepEqual(enemy.stats_you, enemy.stats_right);
  assert.deepEqual(enemy.stats_enemy, enemy.stats_left);

  const scout = extractPanel([scoutShot()], 'you', null);
  assert.equal(scout.requested_side, 'you');
  assert.ok(!('stats_you' in scout));
});

test('QA defect 012: a contradicting panel hint fails closed', () => {
  const result = extractPanel([scoutShot()], 'you', 'citystats');
  assert.equal(result.status, 'failed');
  assert.deepEqual(result.stats, {});
  assert.ok(!('stats_left' in result));
  assert.ok(result.warnings.includes('panel hint citystats contradicts detected scout'));
  assert.equal(extractPanel([scoutShot()], 'enemy', 'scout').status, 'ok');
});

test('QA defect 018: battle responses omit the empty stats key', () => {
  const result = extractPanel([battleShot()], 'you', null);
  assert.ok(!('stats' in result));
  assert.ok('stats_left' in result && 'stats_right' in result);
});

test('QA defect 013: penalties classify by canonical label, not substring or sign', () => {
  const [, , pEnemy] = foldSets([], [
    { label: 'Enemy Attack Reduction', value: -12.0 },
    { label: 'Enemy Defense Reduction', value: 8.0 },
  ], { observed: 'read' });
  assert.ok(Math.abs(pEnemy.Attack - 0.12) < 1e-9);
  assert.ok(Math.abs(pEnemy.Defense - 0.08) < 1e-9);

  const warnings = [];
  const [sScout, sBattle] = foldSets(
    [{ label: 'Enemy Defense Penalty (Pet Skill)', value: 10.0 }], [],
    { observed: 'read', warnings },
  );
  assert.equal(sScout.Defense, 0.0);
  assert.equal(sBattle.Defense, 0.0);
  assert.equal(warnings.length, 1);
  assert.ok(warnings[0].includes('Enemy Defense Penalty (Pet Skill)'));

  const quiet = [];
  const [negative] = foldSets(
    [{ label: 'Enemy Defense Penalty (Pet Skill)', value: -10.0 }], [],
    { observed: 'read', warnings: quiet },
  );
  assert.equal(negative.Defense, 0.0);
  assert.deepEqual(quiet, []);

  const [bonus] = foldSets([{ label: 'Defense Bonus (Pet Skill)', value: 10.0 }], [],
    { observed: 'read' });
  assert.ok(Math.abs(bonus.Defense - 0.10) < 1e-9);
});

test('QA defect 015: calibration requires all three classes', () => {
  const a = FIX.accounts.A;
  assert.throws(() => calibrateU(a.bo_troops, a.bo_class,
    { Infantry: a.scout.Infantry }, a.S_scout), CalibrationError);
  assert.throws(() => calibrateU(a.bo_troops, { Infantry: a.bo_class.Infantry },
    a.scout, a.S_scout), CalibrationError);
});

test('QA defect 019: convert + token layers raise typed errors, never TypeErrors', () => {
  const a = FIX.accounts.A;
  assert.throws(() => calibrateU(a.bo_troops, a.bo_class, {}, a.S_scout), CalibrationError);
  assert.throws(() => calibrateU(a.bo_troops, a.bo_class, a.scout,
    Object.fromEntries(STATS.map((st) => [st, -1.0]))), CalibrationError);
  assert.throws(() => calibrateU(a.bo_troops, a.bo_class, a.scout, null), CalibrationError);
  const holes = Object.fromEntries(Object.entries(a.scout)
    .map(([cls, stats]) => [cls, { ...stats, Health: undefined }]));
  assert.throws(() => calibrateU(a.bo_troops, a.bo_class, holes, a.S_scout), CalibrationError);
  assert.throws(() => battleToScoutnet(a.battle_left, a.S_scout,
    Object.fromEntries(STATS.map((st) => [st, -1.0])), a.P_enemy), CalibrationError);

  for (const bad of ['nope', [{ text: 'Infantry Attack' }], [null], 7]) {
    assert.throws(() => extractPanel(bad, null, null), Error);
  }
  for (const bad of [[['not an object']], [[{ x0: 0.1, y0: 0.1, x1: 0.2, y1: 0.2, conf: 0.9 }]],
    [[{ text: 'x', x0: 'a', y0: 0.1, x1: 0.2, y1: 0.2, conf: 0.9 }]],
    [[{ text: 'x', x0: 0.1, y0: 0.1, x1: 0.2, y1: 0.2, conf: null }]]]) {
    assert.throws(() => extractPanel(bad, null, null), Error);
  }
});

test('QA defect 022: only a fully read specials panel may fold', () => {
  const own = [{ label: 'Attack Bonus (Pet Skill)', value: 10.0 }];
  for (const state of ['none', 'partial']) {
    assert.throws(() => foldSets([], [], { observed: state }), (e) => e.code === 'missing_specials');
    assert.throws(() => foldSets(own, [], { observed: state }), (e) => e.code === 'missing_specials');
  }
  const [sScout, sBattle, pEnemy] = foldSets([], [], { observed: 'read' });
  for (const st of STATS) {
    assert.equal(sScout[st], 0.0);
    assert.equal(sBattle[st], 0.0);
    assert.equal(pEnemy[st], 0.0);
  }
  for (const bad of [true, false, null, 1, 'yes', 'READ', undefined]) {
    assert.throws(() => foldSets([], [], { observed: bad }), TypeError);
  }
});

test('QA defect 022: service reports the tri-state capture verdict', () => {
  const partial = scoutShot();
  partial.push(tok('Attack Bonus (Pet Skill)', 0.05, 0.80, 0.40, 0.83));
  partial.push(tok('+10.0%', 0.70, 0.80, 0.95, 0.83, 0.20));
  assert.equal(extractPanel([partial], 'you', null).specials_observed, 'partial');

  const headerOnly = scoutShot();
  headerOnly.push(tok('Stat Bonuses', 0.05, 0.80, 0.40, 0.83));
  const headerResult = extractPanel([headerOnly], 'you', null);
  assert.deepEqual(headerResult.specials, []);
  assert.equal(headerResult.specials_observed, 'read');

  assert.equal(extractPanel([scoutShot()], 'you', null).specials_observed, 'none');

  const readable = scoutShot();
  readable.push(tok('Attack Bonus (Pet Skill)', 0.05, 0.80, 0.40, 0.83));
  readable.push(tok('+10.0%', 0.70, 0.80, 0.95, 0.83));
  assert.equal(extractPanel([readable], 'you', null).specials_observed, 'read');
});

function cityStatsShot() {
  const shot = [];
  let y = 0.10;
  for (const [st, v] of [['Attack', '748.49%'], ['Defense', '612.10%'],
    ['Lethality', '540.00%'], ['Health', '601.25%']]) {
    shot.push(tok(`Troops' ${st}`, 0.05, y, 0.40, y + 0.03));
    shot.push(tok(v, 0.70, y, 0.95, y + 0.03));
    y += 0.05;
  }
  for (const cls of CLASSES) {
    for (const st of STATS) {
      shot.push(tok(`${cls} ${st}`, 0.05, y, 0.40, y + 0.03));
      shot.push(tok('120.00%', 0.70, y, 0.95, y + 0.03));
      y += 0.05;
    }
  }
  return shot;
}

function oneColumnBattleShot() {
  const shot = [];
  let y = 0.10;
  for (const cls of CLASSES) {
    for (const st of STATS) {
      shot.push(tok(`${cls} ${st}`, 0.38, y, 0.58, y + 0.03));
      shot.push(tok('+4859.0%', 0.03, y, 0.23, y + 0.03, 0.99, 'green'));
      y += 0.05;
    }
  }
  return shot;
}

test('QA defect 021: incompatible hint/detection pairs still fail closed', () => {
  const cases = [
    ['citystats', scoutShot(), 'scout'],
    ['citystats', battleShot(), 'battle'],
    ['battle', cityStatsShot(), 'citystats'],
    ['scout', cityStatsShot(), 'citystats'],
    ['scout', battleShot(), 'battle'],
  ];
  for (const [hint, shot, detected] of cases) {
    const result = extractPanel([shot], 'you', hint);
    assert.equal(result.status, 'failed', `${hint}/${detected}`);
    assert.deepEqual(result.stats, {}, `${hint}/${detected}`);
    assert.ok(result.warnings.includes(`panel hint ${hint} contradicts detected ${detected}`));
  }
});

test('QA defect 021: battle hint on a one-column shot is a partial battle read', () => {
  const result = extractPanel([oneColumnBattleShot()], 'you', 'battle');
  assert.equal(result.panel_type, 'battle');
  assert.equal(result.status, 'partial');
  assert.equal(Object.keys(result.stats_left).length, 12);
  assert.deepEqual(result.stats_right, {});
  assert.deepEqual(result.stats_you, result.stats_left);
  for (const cls of CLASSES) {
    for (const st of STATS) {
      assert.ok(result.unreadable_fields.includes(`stats_right.${cls}|${st}`));
      assert.ok(!result.unreadable_fields.includes(`stats_left.${cls}|${st}`));
    }
  }
  assert.ok(result.warnings.some((w) => w.includes('only one column was readable')));
});

test('QA defect 021: agreeing hints stay silent, unknown detection warns', () => {
  for (const [hint, shot] of [['scout', scoutShot()], ['battle', battleShot()],
    ['citystats', cityStatsShot()]]) {
    const result = extractPanel([shot], 'you', hint);
    assert.equal(result.panel_type, hint);
    assert.deepEqual(result.warnings, [], hint);
  }
  const sparse = [tok('Infantry Attack', 0.05, 0.10, 0.40, 0.13),
    tok('+4491.6%', 0.70, 0.10, 0.95, 0.13)];
  const result = extractPanel([sparse], 'you', 'scout');
  assert.equal(result.panel_type, 'scout');
  assert.equal(result.status, 'partial');
  assert.ok(result.warnings.some((w) => w.includes('could not be detected')));
});

test('QA defect 025: a tall row in a short shot still pairs', () => {
  const shot = [];
  let y = 0.10;
  for (const [cls, st] of [['Infantry', 'Attack'], ['Infantry', 'Defense'],
    ['Infantry', 'Lethality'], ['Infantry', 'Health'], ['Lancer', 'Attack'],
    ['Lancer', 'Defense'], ['Lancer', 'Lethality']]) {
    shot.push(tok(`${cls} ${st}`, 0.05, y, 0.25, y + 0.008));
    shot.push(tok('120.00%', 0.70, y, 0.90, y + 0.008));
    y += 0.02;
  }
  shot.push(tok('Marksman Attack', 0.05, 0.500, 0.25, 0.530));       // centre .515
  shot.push(tok('4491.6%', 0.70, 0.5039, 0.90, 0.5339));             // centre .5189
  const result = extractPanel([shot], 'you', null);
  assert.equal(result.stats['Marksman|Attack'], 4491.6);
  assert.equal(result.stats['Infantry|Attack'], 120.0);
  assert.deepEqual(result.warnings, []);
});

test('QA defect 026: warnings are deduped and unmatched rows are reported', () => {
  const repeated = extractPanel([driftShot(), driftShot(), driftShot()], null, null);
  assert.deepEqual(repeated.warnings, ['orphan value near y=0.130']);

  const valueOnly = extractPanel([[tok('1,234,567', 0.70, 0.10, 0.90, 0.13)]], null, null);
  assert.deepEqual(valueOnly.warnings, ['unmatched row near y=0.115']);

  const unmatchedLabel = extractPanel([[tok('Zzyzx', 0.05, 0.20, 0.25, 0.23),
    tok('42', 0.70, 0.20, 0.90, 0.23)]], null, null);
  assert.deepEqual(unmatchedLabel.warnings, ['unmatched row near y=0.215']);

  const quiet = extractPanel([[tok('Zzyzx', 0.05, 0.20, 0.25, 0.23)]], null, null);
  assert.deepEqual(quiet.warnings, []);
});
