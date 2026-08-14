import {
  foldSets, battleToScoutnet, cityStatsToScoutnet, calibrateU,
  CalibrationError, MissingSpecialsError,
} from './panel_parser.mjs';

const CLASSES = ['Infantry', 'Lancer', 'Marksman'];
const STATS = ['Attack', 'Defense', 'Lethality', 'Health'];

function groupByClass(flat) {
  const out = {};
  for (const cls of CLASSES) {
    out[cls] = {};
    for (const stat of STATS) {
      const key = `${cls}|${stat}`;
      if (key in flat) out[cls][stat] = flat[key];
    }
  }
  return out;
}

function groupTroops(flat) {
  const out = {};
  for (const stat of STATS) {
    const key = `Troops|${stat}`;
    if (key in flat) out[stat] = flat[key];
  }
  return out;
}

function flattenByClass(grouped) {
  const out = {};
  for (const [cls, stats] of Object.entries(grouped)) {
    for (const [stat, value] of Object.entries(stats)) out[`${cls}|${stat}`] = value;
  }
  return out;
}

function ready(percents, extra = {}) {
  return { outcome: 'ready', percents, rawUnconverted: null, calibratedU: null, reason: null, ...extra };
}
function needsSpecials(rawUnconverted, reason) {
  return { outcome: 'needs_specials', percents: null, rawUnconverted, calibratedU: null, reason };
}
function needsCalibration(reason) {
  return { outcome: 'needs_calibration', percents: null, rawUnconverted: null, calibratedU: null, reason };
}
function blocked(reason) {
  return { outcome: 'blocked', percents: null, rawUnconverted: null, calibratedU: null, reason };
}

export function convertSide({
  panelType, stats, specialsOwn = [], specialsEnemy = [], specialsObserved = 'none',
  calibratedU = null, scoutForCalibration = null,
}) {
  if (panelType === 'scout') return ready(stats);

  if (panelType === 'battle') {
    if (specialsObserved !== 'read') {
      return needsSpecials(stats, 'the Stat Bonuses screenshot for this side has not been fully read yet');
    }
    try {
      const [sScout, sBattle, pEnemy] = foldSets(specialsOwn, specialsEnemy, { observed: specialsObserved });
      const scoutGrouped = battleToScoutnet(groupByClass(stats), sScout, sBattle, pEnemy);
      return ready(flattenByClass(scoutGrouped));
    } catch (err) {
      if (err instanceof MissingSpecialsError) return needsSpecials(stats, err.message);
      if (err instanceof CalibrationError) return blocked(err.message);
      throw err;
    }
  }

  if (panelType === 'citystats') {
    if (specialsObserved !== 'read') {
      return needsSpecials(null, 'the Stat Bonuses screenshot for this side has not been fully read yet');
    }
    const boTroops = groupTroops(stats);
    const boClass = groupByClass(stats);
    try {
      const [sScout] = foldSets(specialsOwn, specialsEnemy, { observed: specialsObserved });
      let U = calibratedU;
      let freshlyCalibrated = null;
      if (!U) {
        if (!scoutForCalibration) {
          return needsCalibration('this account needs a one-time setup: add a matching scout screenshot once');
        }
        U = calibrateU(boTroops, boClass, groupByClass(scoutForCalibration), sScout);
        freshlyCalibrated = U;
      }
      const scoutGrouped = cityStatsToScoutnet(boTroops, boClass, U, sScout);
      return ready(flattenByClass(scoutGrouped), { calibratedU: freshlyCalibrated });
    } catch (err) {
      if (err instanceof MissingSpecialsError) return needsSpecials(null, err.message);
      if (err instanceof CalibrationError) return blocked(err.message);
      throw err;
    }
  }

  return blocked(`cannot convert panel type: ${panelType}`);
}
