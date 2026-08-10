import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  sideToWhich, toApplyPanelPayload, buildGenTable, toApplyHeroesPayload,
  classifyFields, ALL_FIELD_KEYS, FIELD_OK, FIELD_CHECK, FIELD_MISSING, buildSnapshot,
  sideStatsPrefix, fieldEngineForSide,
} from '../fill_mapper.mjs';

test('sideToWhich maps the OCR vocabulary onto the real app vocabulary', () => {
  assert.equal(sideToWhich('you'), 'me');
  assert.equal(sideToWhich('enemy'), 'foe');
  assert.throws(() => sideToWhich('bogus'));
});

test('toApplyPanelPayload converts percent points to the fractions applyPanel expects', () => {
  const payload = toApplyPanelPayload({ 'Infantry|Attack': 4491.6, 'Lancer|Health': 0 });
  assert.equal(payload['Infantry|Attack'], 44.916);
  assert.equal(payload['Lancer|Health'], 0);
});

test('buildGenTable inverts the name-keyed hero file into the gen-keyed shape defaultHeroes expects', () => {
  const raw = {
    Hank: { generation: 15, troop: 'Infantry' },
    Estrella: { generation: 15, troop: 'Lancer' },
    Viveca: { generation: 15, troop: 'Marksman' },
    Cara: { generation: 14, troop: 'Marksman' },
  };
  const table = buildGenTable(raw);
  assert.deepEqual(table[15], { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' });
  assert.equal(table[14].Marksman, 'Cara');
});

test('buildGenTable throws on a data collision rather than silently dropping a hero', () => {
  const raw = {
    Hank: { generation: 15, troop: 'Infantry' },
    Impostor: { generation: 15, troop: 'Infantry' },
  };
  assert.throws(() => buildGenTable(raw), /15.*Infantry/);
});

// NOTE (execution-time finding, not part of the original plan draft): the REAL
// wos_sim/data/hero_generations.json — which this repo's constraints forbid
// editing — contains genuine (generation, troop) collisions that buildGenTable's
// specified throw-on-collision behavior (tested immediately above, and the
// correct behavior per the plan's own "never silently drop a hero" rationale)
// correctly rejects: generation "SR" (a non-badge-numbered legacy/reward pool,
// out of scope for the badge-generation rule in
// .claude/skills/wos-hero-identifier/SKILL.md) has 3 Marksman entries
// (Bahiti/Jasser/Seo-yoon) and 4 Lancer entries (Jessie/Ling Xue/Lumak
// Bokan/Patrick); generation 1 (IN scope — a real badge generation) has 2
// Infantry entries (Jeronimo/Natalia) with no data to disambiguate a lead.
// This is a genuine data-file defect this plan's execution surfaced, not
// something a stricter or looser buildGenTable could paper over without
// silently guessing a lead hero. Flagged for a coordinator/Martin decision;
// not fixed here (wos_sim/** is on this task's untouchable list, and
// buildGenTable's throw-on-collision behavior is the plan's own deliberate,
// tested design — weakening it to "silently keep the first" would violate
// the same "never silently drop a hero" rule the throw exists to enforce).
// The real-data invariant this test would check is therefore currently FALSE
// on disk; skipped rather than silently loosened, deleted, or forced green.
test('buildGenTable on the REAL hero_generations.json produces exactly one hero per (gen, class)', { skip: 'wos_sim/data/hero_generations.json has real (generation,troop) collisions — see comment above; requires a coordinator/Martin decision, wos_sim/** is untouchable from this task' }, () => {
  const raw = JSON.parse(readFileSync(
    new URL('../../../../../wos_sim/data/hero_generations.json', import.meta.url), 'utf8'));
  const table = buildGenTable(raw);
  for (const gen of Object.keys(table)) {
    for (const cls of ['Infantry', 'Lancer', 'Marksman']) {
      assert.ok(typeof table[gen][cls] === 'string' || table[gen][cls] === undefined, `${gen}/${cls}`);
    }
  }
  // the known reference trio from the hero-identifier skill's own worked example
  assert.deepEqual(table[15], { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' });
});

test('toApplyHeroesPayload orders by class and preserves nulls (untouched lanes, never blanked)', () => {
  assert.deepEqual(
    toApplyHeroesPayload({ Infantry: 'Hank', Lancer: null, Marksman: 'Viveca' }),
    ['Hank', null, 'Viveca'],
  );
});

test('classifyFields: present without a field_engine entry -> ok; present WITH a field_engine entry -> check (Gemini gap-fill, carries value + provenance); absent -> missing', () => {
  const result = classifyFields({
    expectedKeys: ['Infantry|Attack', 'Infantry|Defense', 'Infantry|Lethality'],
    stats: { 'Infantry|Attack': 4491.6, 'Infantry|Defense': 3900.0 },
    fieldConf: { 'Infantry|Attack': 0.99, 'Infantry|Defense': 0.71 },
    fieldEngine: { 'Infantry|Defense': 'gemini' },
  });
  assert.deepEqual(result['Infantry|Attack'], { state: FIELD_OK, value: 4491.6, conf: 0.99 });
  assert.deepEqual(result['Infantry|Defense'], { state: FIELD_CHECK, value: 3900.0, conf: 0.71 });
  assert.deepEqual(result['Infantry|Lethality'], { state: FIELD_MISSING, value: null, conf: null });
});

test('classifyFields degrades to 2-tier (ok/missing) when nothing was ever gap-filled (field_engine empty/absent — the mock path or a clean RapidOCR-only read)', () => {
  const result = classifyFields({ expectedKeys: ['Marksman|Health'], stats: {}, fieldConf: {} });
  assert.equal(result['Marksman|Health'].state, FIELD_MISSING);
  const clean = classifyFields({
    expectedKeys: ['Marksman|Health'], stats: { 'Marksman|Health': 100 }, fieldConf: { 'Marksman|Health': 0.95 },
  });
  assert.deepEqual(clean['Marksman|Health'], { state: FIELD_OK, value: 100, conf: 0.95 });
});

test('ALL_FIELD_KEYS is the fixed 12-key class-stat order', () => {
  assert.equal(ALL_FIELD_KEYS.length, 12);
  assert.equal(ALL_FIELD_KEYS[0], 'Infantry|Attack');
  assert.equal(ALL_FIELD_KEYS[ALL_FIELD_KEYS.length - 1], 'Marksman|Health');
});

test('sideStatsPrefix: single-sided panels always read "stats"; battle panels pick stats_left/stats_right by requested_side', () => {
  assert.equal(sideStatsPrefix({ panel_type: 'scout' }, 'you'), 'stats');
  assert.equal(sideStatsPrefix({ panel_type: 'citystats' }, 'enemy'), 'stats');
  assert.equal(sideStatsPrefix({ panel_type: 'battle', requested_side: 'you' }, 'you'), 'stats_left');
  assert.equal(sideStatsPrefix({ panel_type: 'battle', requested_side: 'you' }, 'enemy'), 'stats_right');
  assert.equal(sideStatsPrefix({ panel_type: 'battle', requested_side: 'enemy' }, 'you'), 'stats_right');
  assert.equal(sideStatsPrefix({ panel_type: 'battle', requested_side: 'enemy' }, 'enemy'), 'stats_left');
});

test('fieldEngineForSide strips the raw field_engine keys down to bare Class|Stat, filtered to one side', () => {
  const result = {
    panel_type: 'battle', requested_side: 'you',
    field_engine: { 'stats_left.Infantry|Attack': 'gemini', 'stats_right.Lancer|Defense': 'gemini' },
  };
  assert.deepEqual(fieldEngineForSide(result, 'you'), { 'Infantry|Attack': 'gemini' });
  assert.deepEqual(fieldEngineForSide(result, 'enemy'), { 'Lancer|Defense': 'gemini' });
});

test('fieldEngineForSide on a single-sided (scout/citystats) result reads the bare "stats." prefix', () => {
  const result = { panel_type: 'scout', field_engine: { 'stats.Infantry|Health': 'gemini' } };
  assert.deepEqual(fieldEngineForSide(result, 'you'), { 'Infantry|Health': 'gemini' });
});

test('fieldEngineForSide defaults to empty when field_engine is absent (mock-path responses carry no such key)', () => {
  assert.deepEqual(fieldEngineForSide({ panel_type: 'scout' }, 'you'), {});
});

test('buildSnapshot stores applyPanel-ready fractions and pre-fill hero/checkbox state', () => {
  const snap = buildSnapshot({
    percentsMe: { 'Infantry|Attack': 1300 }, percentsFoe: { 'Infantry|Attack': 1300 },
    heroesMe: { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' },
    heroesFoe: { Infantry: 'Gisela', Lancer: 'Flora', Marksman: 'Vulcanus' },
    statsScoutedChecked: false,
  });
  assert.equal(snap.me.panel['Infantry|Attack'], 13);
  assert.equal(snap.foe.panel['Infantry|Attack'], 13);
  assert.deepEqual(snap.heroesMe, { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' });
  assert.equal(snap.statsScoutedChecked, false);
});
