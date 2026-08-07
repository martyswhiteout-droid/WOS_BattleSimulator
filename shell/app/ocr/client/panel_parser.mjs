const CLASSES = ['Infantry', 'Lancer', 'Marksman'];
const STATS = ['Attack', 'Defense', 'Lethality', 'Health'];
const LOW_CONF = 0.90;

const SPECIALS = [
  "Defender Troops' Attack", "Defender Troops' Health",
  'Enemy Defense Penalty (Pet Skill)', 'Enemy Lethality Penalty (Pet Skill)',
  'Enemy Health Penalty (Pet Skill)', 'Attack Bonus (Pet Skill)',
  'Defense Bonus (Pet Skill)', 'Lethality Bonus (Pet Skill)',
  'Health Bonus (Pet Skill)', 'Territory Defender Attack',
  'Territory Defender Defense',
  'Defender Troops Attack When Defending Own City',
  'Defender Troops Defense When Defending Own City',
  'Enemy Lethality Penalty (Expert Skill)', 'Enemy Attack Penalty (Pet Skill)',
  'Attack Bonus', 'Defense Bonus', 'Lethality Bonus', 'Health Bonus',
  'Enemy Attack Reduction', 'Enemy Defense Reduction',
];
const META = [
  'Deployment Capacity', 'March Queue', 'March Speed Up',
  'Training Capacity', 'Training Speed', 'Healing Speed',
];
const HEADERS = ['Bonus Overview', 'Stat Bonuses', 'Military', 'Troops Total', 'Lootable'];

const PCT = /^([+-]?)(\d{1,3}(?:,\d{3})*|\d+)(\.\d+)?%$/;
const PCT_NOSYM = /^([+-])(\d{1,3}(?:,\d{3})*|\d+)(\.\d+)?$/;
const INT = /^(\d{1,3}(?:,\d{3})*|\d+)$/;

export function parseValue(raw) {
  raw = (raw || '').trim();
  let match = PCT.exec(raw);
  if (match) {
    const value = Number(match[2].replaceAll(',', '') + (match[3] || ''));
    return {
      value: match[1] === '-' ? -value : value,
      unit: 'pct',
      signed: match[1] !== '',
    };
  }
  match = PCT_NOSYM.exec(raw);
  if (match) {
    const value = Number(match[2].replaceAll(',', '') + (match[3] || ''));
    return { value: match[1] === '-' ? -value : value, unit: 'pct', signed: true };
  }
  match = INT.exec(raw);
  if (match) {
    return { value: Number(match[1].replaceAll(',', '')), unit: 'int', signed: false };
  }
  return null;
}

function skeleton(value) {
  return (value || '')
    .toLowerCase()
    .replaceAll('’', "'")
    .replaceAll('"', "'")
    .replaceAll('0', 'o')
    .replaceAll('1', 'l')
    .replace(/[^a-z]/g, '');
}

function distance(a, b) {
  if (Math.abs(a.length - b.length) > 2) return 3;
  let previous = Array.from({ length: b.length + 1 }, (_, index) => index);
  for (let i = 1; i <= a.length; i += 1) {
    const current = [i];
    for (let j = 1; j <= b.length; j += 1) {
      current.push(Math.min(
        previous[j] + 1,
        current[j - 1] + 1,
        previous[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0),
      ));
    }
    previous = current;
    if (Math.min(...previous) > 2) return 3;
  }
  return previous.at(-1);
}

const CANON = new Map();
for (const cls of CLASSES) {
  for (const stat of STATS) CANON.set(skeleton(`${cls} ${stat}`), `${cls}|${stat}`);
}
for (const stat of STATS) CANON.set(skeleton(`Troops' ${stat}`), `Troops|${stat}`);
for (const special of SPECIALS) CANON.set(skeleton(special), `special:${special}`);
for (const meta of META) CANON.set(skeleton(meta), `meta:${meta}`);
for (const header of HEADERS) CANON.set(skeleton(header), `header:${header}`);

export function matchLabel(raw) {
  const sk = skeleton(raw || '');
  if (sk.length < 4) return null;
  if (CANON.has(sk)) return CANON.get(sk);
  let best = null;
  let bestDistance = 3;
  for (const [candidate, canonical] of CANON.entries()) {
    const candidateDistance = distance(sk, candidate);
    if (candidateDistance < bestDistance) {
      best = canonical;
      bestDistance = candidateDistance;
    }
  }
  return bestDistance <= 2 ? best : null;
}

function tokensFromJson(items) {
  const output = [];
  for (const item of items) {
    const token = {
      text: String(item.text),
      x0: Number(item.x0),
      y0: Number(item.y0),
      x1: Number(item.x1),
      y1: Number(item.y1),
      conf: Number(item.conf),
      color: item.color ?? null,
    };
    for (const coordinate of [token.x0, token.y0, token.x1, token.y1]) {
      if (!(coordinate >= 0.0 && coordinate <= 1.0)) {
        throw new Error(`coord out of range: ${coordinate}`);
      }
    }
    if (!(token.conf >= 0.0 && token.conf <= 1.0)) {
      throw new Error(`conf out of range: ${token.conf}`);
    }
    if (token.x1 <= token.x0 || token.y1 <= token.y0) throw new Error('degenerate box');
    if (![null, 'green', 'red'].includes(token.color)) throw new Error(`bad color: ${token.color}`);
    output.push(token);
  }
  return output;
}

function median(values) {
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2) return sorted[middle];
  return (sorted[middle - 1] + sorted[middle]) / 2;
}

// QA D-001 (row drift): a value token may only pair with a label row whose own
// vertical band contains the value's centre — the label centres widened by
// BAND_SLACK * h (h = median token height for the shot). See rows.py for the
// documented deviation from the ruling's literal y0/y1 phrasing.
const BAND_SLACK = 0.35;

function groupRows(tokens, height) {
  const sorted = [...tokens].sort((left, right) => {
    const leftY = (left.y0 + left.y1) / 2;
    const rightY = (right.y0 + right.y1) / 2;
    return leftY - rightY || left.x0 - right.x0;
  });
  if (!sorted.length) return [];
  const groups = [];
  let current = [sorted[0]];
  let currentY = (sorted[0].y0 + sorted[0].y1) / 2;
  for (const token of sorted.slice(1)) {
    const centerY = (token.y0 + token.y1) / 2;
    if (Math.abs(centerY - currentY) <= 0.6 * height) {
      current.push(token);
      currentY = Math.min(currentY, centerY);
    } else {
      groups.push(current);
      current = [token];
      currentY = centerY;
    }
  }
  groups.push(current);
  return groups;
}

export function assembleRows(tokens, twoColumn) {
  const output = [];
  const warnings = [];
  if (!tokens.length) return [output, warnings];
  const height = median(tokens.map((token) => token.y1 - token.y0));
  for (const group of groupRows(tokens, height)) {
    const labels = group.filter((token) => parseValue(token.text) === null);
    const values = group.filter((token) => parseValue(token.text) !== null);
    const rawLabel = [...labels]
      .sort((left, right) => left.x0 - right.x0)
      .map((token) => token.text)
      .join(' ')
      .trim();
    const canonical = matchLabel(rawLabel);
    if (canonical === null) continue;
    const labelCenters = labels.map((token) => (token.y0 + token.y1) / 2);
    const bandLow = Math.min(...labelCenters) - BAND_SLACK * height;
    const bandHigh = Math.max(...labelCenters) + BAND_SLACK * height;
    const inBand = [];
    for (const valueToken of values) {
      const centerY = (valueToken.y0 + valueToken.y1) / 2;
      if (centerY >= bandLow && centerY <= bandHigh) inBand.push(valueToken);
      else warnings.push(`orphan value near y=${centerY.toFixed(3)}`);
    }
    if (!inBand.length) {
      output.push({
        canonical,
        side: null,
        value: null,
        unit: null,
        conf: 0.0,
        raw_label: rawLabel,
        flags: ['missing_value'],
      });
      continue;
    }
    const labelCenter = (Math.min(...labels.map((token) => token.x0))
      + Math.max(...labels.map((token) => token.x1))) / 2;
    for (const valueToken of inBand) {
      const parsed = parseValue(valueToken.text);
      const flags = [];
      let side = null;
      if (twoColumn) {
        const geometry = (valueToken.x0 + valueToken.x1) / 2 < labelCenter ? 'left' : 'right';
        const color = { green: 'left', red: 'right' }[valueToken.color];
        side = color || geometry;
        if (color && color !== geometry) flags.push('col_conflict');
      }
      if (valueToken.conf < LOW_CONF) flags.push('low_conf');
      output.push({
        canonical,
        side,
        value: parsed.value,
        unit: parsed.unit,
        conf: valueToken.conf,
        raw_label: rawLabel,
        flags,
      });
    }
  }
  return [output, warnings];
}

function stitchKey(row) {
  return JSON.stringify([row.canonical, row.side]);
}

function tupleDisplay(row) {
  const side = row.side === null ? 'None' : `'${row.side}'`;
  return `('${row.canonical}', ${side})`;
}

export function stitch(rowsPerShot, warningsPerShot = null) {
  const order = [];
  const best = new Map();
  const warnings = [];
  for (const shotWarnings of (warningsPerShot || [])) warnings.push(...shotWarnings);
  for (const rows of rowsPerShot) {
    for (const row of rows) {
      const key = stitchKey(row);
      if (!best.has(key)) {
        best.set(key, row);
        order.push(key);
      } else {
        const current = best.get(key);
        // QA D-003: conflicts are sticky — never replaced by a later shot.
        if (current.flags.includes('conflict')) continue;
        if (current.value !== null && row.value !== null && current.value !== row.value) {
          warnings.push(`conflict on ${tupleDisplay(row)}: ${current.value} vs ${row.value}`);
          best.set(key, {
            canonical: row.canonical,
            side: row.side,
            value: null,
            unit: null,
            conf: 0.0,
            raw_label: row.raw_label,
            flags: [...new Set([...current.flags, ...row.flags, 'conflict'])],
          });
        } else if (row.value !== null && (current.value === null || row.conf > current.conf)) {
          best.set(key, row);
        }
      }
    }
  }
  return [order.map((key) => best.get(key)), warnings];
}

function statOf(label) {
  for (const stat of STATS) {
    if (label.includes(stat)) return stat;
  }
  return null;
}

function zeroStats() {
  return Object.fromEntries(STATS.map((stat) => [stat, 0.0]));
}

export function foldSets(specialsOwn, specialsEnemy) {
  const sScout = zeroStats();
  const territory = zeroStats();
  for (const special of specialsOwn) {
    const label = special.label;
    const value = special.value / 100.0;
    const stat = statOf(label);
    if (stat === null || value < 0) continue;
    if (label.includes('When Defending Own City')) continue;
    if (label.includes('Territory Defender')) territory[stat] += value;
    else sScout[stat] += value;
  }
  const sBattle = Object.fromEntries(STATS.map((stat) => [stat, sScout[stat] + territory[stat]]));
  const pEnemy = zeroStats();
  for (const special of specialsEnemy) {
    const stat = statOf(special.label);
    if (stat !== null && special.value < 0 && special.label.includes('Penalty')) {
      pEnemy[stat] += Math.abs(special.value) / 100.0;
    }
  }
  return [sScout, sBattle, pEnemy];
}

export function battleToScoutnet(battleRows, sScout, sBattle, pEnemy) {
  const output = {};
  for (const [cls, stats] of Object.entries(battleRows)) {
    output[cls] = {};
    for (const [stat, battle] of Object.entries(stats)) {
      const ratio = (1 + sScout[stat]) * (1 + pEnemy[stat]) / (1 + sBattle[stat]);
      output[cls][stat] = ((1 + battle / 100.0) * ratio - 1) * 100.0;
    }
  }
  return output;
}

class CalibrationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'CalibrationError';
  }
}

export function calibrateU(boTroops, boClass, scoutRows, sScout) {
  const output = {};
  for (const stat of STATS) {
    const values = [];
    for (const [cls, stats] of Object.entries(scoutRows)) {
      const standard = ((1 + stats[stat] / 100.0) / (1 + sScout[stat]) - 1) * 100.0;
      values.push(standard - boTroops[stat] - boClass[cls][stat]);
    }
    const spread = Math.max(...values) - Math.min(...values);
    if (spread > 1.0) throw new CalibrationError(`U not uniform for ${stat}: spread ${spread.toFixed(2)}`);
    output[stat] = values.reduce((total, value) => total + value, 0) / values.length;
  }
  return output;
}

export function cityStatsToScoutnet(boTroops, boClass, U, sScout) {
  const output = {};
  for (const [cls, stats] of Object.entries(boClass)) {
    output[cls] = {};
    for (const stat of STATS) {
      const standard = boTroops[stat] + stats[stat] + U[stat];
      output[cls][stat] = ((1 + standard / 100.0) * (1 + sScout[stat]) - 1) * 100.0;
    }
  }
  return output;
}

function detectPanelType(rows) {
  const classRows = rows.filter((row) => row.canonical.includes('|')
    && !['special:', 'meta:', 'header:'].some((prefix) => row.canonical.startsWith(prefix)));
  if (rows.some((row) => row.canonical.startsWith('Troops|'))) return 'citystats';
  const sided = classRows.filter((row) => ['left', 'right'].includes(row.side));
  const left = new Set(sided.filter((row) => row.side === 'left').map((row) => row.canonical));
  const right = new Set(sided.filter((row) => row.side === 'right').map((row) => row.canonical));
  if ([...left].filter((canonical) => right.has(canonical)).length >= 4) return 'battle';
  if (classRows.length >= 4) return 'scout';
  return 'unknown';
}

// Every class-stat the app expects on a full panel, in a fixed (deterministic)
// order — used to report fields that were never seen at all (QA D-006).
const EXPECTED_KEYS = CLASSES.flatMap((cls) => STATS.map((stat) => `${cls}|${stat}`));

// The single honesty predicate. QA D-002: the flag test is a SUBSTRING match so
// `col_conflict` counts, not just the stitch `conflict`.
function isBad(row) {
  return row.value === null
    || row.conf < LOW_CONF
    || row.flags.some((flag) => flag.includes('conflict'));
}

function dedupe(items) {
  const seen = new Set();
  const output = [];
  for (const item of items) {
    if (!seen.has(item)) {
      seen.add(item);
      output.push(item);
    }
  }
  return output;
}

function bucket(rows, side) {
  const stats = {};
  const conf = {};
  const unreadable = [];
  for (const row of rows) {
    if (['special:', 'meta:', 'header:'].some((prefix) => row.canonical.startsWith(prefix))
        || !row.canonical.includes('|')) continue;
    const key = row.canonical;
    if (side !== null && row.side !== side) continue;
    if (isBad(row)) unreadable.push(`stats.${key}`);
    else {
      stats[key] = row.value;
      conf[key] = Math.round(row.conf * 10000) / 10000;
    }
  }
  return [stats, conf, unreadable];
}

// Specials pass the same honesty predicate as class rows (QA D-004).
function collectSpecials(rows) {
  const good = [];
  const unreadable = [];
  for (const row of rows) {
    if (!row.canonical.startsWith('special:')) continue;
    const label = row.canonical.slice('special:'.length);
    if (isBad(row)) unreadable.push(`specials.${label}`);
    else good.push({ label, value: row.value });
  }
  return [good, unreadable];
}

export function extractPanel(tokenShots, sideHint = null, panelHint = null) {
  const shots = tokenShots.map((shot) => assembleRows(tokensFromJson(shot), true));
  const [rows, warnings] = stitch(shots.map((shot) => shot[0]), shots.map((shot) => shot[1]));
  const panelType = panelHint || detectPanelType(rows);
  const [specials, specialUnreadable] = collectSpecials(rows);
  const output = { panel_type: panelType, specials, warnings: [...warnings] };
  const unreadableFields = [];
  let present;
  let total;
  if (panelType === 'battle') {
    for (const [side, key] of [['left', 'stats_left'], ['right', 'stats_right']]) {
      const [stats, conf, unreadable] = bucket(rows, side);
      output[key] = stats;
      output[`${key}_conf`] = conf;
      unreadableFields.push(...unreadable.map((item) => `${key}.${item.slice('stats.'.length)}`));
      unreadableFields.push(...EXPECTED_KEYS
        .filter((expected) => !(expected in stats))
        .map((expected) => `${key}.${expected}`));
    }
    present = Object.keys(output.stats_left).length + Object.keys(output.stats_right).length;
    total = 24;
  } else {
    const [stats, conf, unreadable] = bucket(rows, null);
    output.stats = stats;
    output.field_conf = conf;
    unreadableFields.push(...unreadable);
    unreadableFields.push(...EXPECTED_KEYS
      .filter((expected) => !(expected in stats))
      .map((expected) => `stats.${expected}`));
    present = Object.keys(stats).filter((key) => CLASSES.includes(key.split('|')[0])).length;
    total = 12;
  }
  output.unreadable_fields = dedupe([...unreadableFields, ...specialUnreadable]);
  output.status = present >= total ? 'ok' : (present > 0 ? 'partial' : 'failed');
  if (!output.stats) output.stats = {};
  void sideHint;
  return output;
}
