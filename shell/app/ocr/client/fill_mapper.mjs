const CLASSES = ['Infantry', 'Lancer', 'Marksman'];
const STATS = ['Attack', 'Defense', 'Lethality', 'Health'];

export const ALL_FIELD_KEYS = CLASSES.flatMap((cls) => STATS.map((stat) => `${cls}|${stat}`));

export const FIELD_OK = 'ok';
export const FIELD_CHECK = 'check';
export const FIELD_MISSING = 'missing';

export function sideToWhich(side) {
  if (side === 'you') return 'me';
  if (side === 'enemy') return 'foe';
  throw new Error(`unknown side: ${side}`);
}

export function toApplyPanelPayload(percents) {
  const out = {};
  for (const [key, value] of Object.entries(percents)) {
    // A plain `value / 100` is mathematically right but leaves IEEE-754 noise
    // on the last bit (e.g. 4491.6/100 -> 44.916000000000004, one ULP off the
    // literal 44.916) — applyPanel() re-rounds to 2 decimal places on the
    // PERCENT scale anyway (prototype/index.html: `+(panel[k]*100).toFixed(2)`),
    // so snapping through toFixed(6) on the fraction (4 dp on the percent) is
    // lossless for this domain and keeps equal percents comparing equal.
    out[key] = parseFloat((value / 100).toFixed(6));
  }
  return out;
}

export function buildGenTable(heroGenerationsJson) {
  const table = {};
  for (const [name, info] of Object.entries(heroGenerationsJson)) {
    const gen = info.generation;
    const cls = info.troop;
    if (!CLASSES.includes(cls)) continue;    // non-troop-class entries (if any) are not lead-hero candidates
    table[gen] ??= {};
    if (table[gen][cls] && table[gen][cls] !== name) {
      throw new Error(`hero_generations.json data collision: generation ${gen} ${cls} has both `
        + `'${table[gen][cls]}' and '${name}' — expected exactly one hero per (generation, class)`);
    }
    table[gen][cls] = name;
  }
  return table;
}

export function toApplyHeroesPayload(namesByClass) {
  return CLASSES.map((cls) => namesByClass[cls] ?? null);
}

// Tier logic per COORDINATOR RULINGS 2026-08-10 #2 (real server contract, NOT
// the drafted client-engine `lowConfRows` design): ok = present in stats* and
// not flagged in field_engine (a plain RapidOCR read); check (gold, "please
// check") = present in stats* AND flagged in field_engine — a Gemini gap-fill,
// which carries both a value and provenance (shell/app/ocr/panel/ladder.py's
// `_fill_gaps`); missing = absent from stats* entirely (in unreadable_fields,
// or never reported). `fieldEngine` defaults to {} so a mock-path or
// clean-RapidOCR result naturally degrades to 2-tier (ok/missing) — there is
// no client-row recovery in server-only v1.
export function classifyFields({ expectedKeys, stats, fieldConf, fieldEngine = {} }) {
  const out = {};
  for (const key of expectedKeys) {
    if (key in stats) {
      const state = fieldEngine[key] ? FIELD_CHECK : FIELD_OK;
      out[key] = { state, value: stats[key], conf: fieldConf[key] ?? null };
      continue;
    }
    out[key] = { state: FIELD_MISSING, value: null, conf: null };
  }
  return out;
}

// The raw server result keys field_engine (and stats_*_conf) by the SAME
// prefix as unreadable_fields — "stats." for single-sided panels, or
// "stats_left."/"stats_right." for battle panels, chosen by which SCREENSHOT
// COLUMN a field came from, not by "you"/"enemy" (service.py's
// stats_you/stats_enemy are aliases of stats_left/stats_right, decided by
// requested_side — QA D-011). This resolves which raw prefix corresponds to a
// given (side, result) pair so fieldEngineForSide can translate it.
export function sideStatsPrefix(result, side) {
  if (!result || result.panel_type !== 'battle') return 'stats';
  const youKey = result.requested_side === 'you' ? 'stats_left' : 'stats_right';
  return side === 'you' ? youKey : (youKey === 'stats_left' ? 'stats_right' : 'stats_left');
}

// Bare-keyed (Class|Stat -> 'gemini'), filtered to one side, and stripped of
// the stats./stats_left./stats_right. prefix so it matches stats*'s own key
// shape — the exact input classifyFields's `fieldEngine` parameter expects.
export function fieldEngineForSide(result, side) {
  const prefix = sideStatsPrefix(result, side);
  const out = {};
  const fieldEngine = (result && result.field_engine) || {};
  for (const [key, engine] of Object.entries(fieldEngine)) {
    const dot = key.indexOf('.');
    if (dot === -1) continue;
    if (key.slice(0, dot) === prefix) out[key.slice(dot + 1)] = engine;
  }
  return out;
}

export function buildSnapshot({ percentsMe, percentsFoe, heroesMe, heroesFoe, statsScoutedChecked }) {
  return {
    me: { panel: toApplyPanelPayload(percentsMe) },
    foe: { panel: toApplyPanelPayload(percentsFoe) },
    heroesMe, heroesFoe, statsScoutedChecked,
  };
}
