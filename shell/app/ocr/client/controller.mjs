// shell/app/ocr/client/controller.mjs — flow controller ("state glue").
//
// SERVER-ONLY v1 (COORDINATOR RULING 2026-08-10 #1): the drafted plan built
// this as a client-engine-first, server-escalation controller (tesseract.js
// via an injected recognizeImage, merged against a /shell/ocr/panel fallback
// by "fewer unreadable_fields wins"). That premise is superseded — v1 reads
// go straight to the server's own production ladder (RapidOCR primary,
// Gemini gap-fill), so there is no client result to race, merge, or label
// "client"/"server"/"client+server". This module keeps the same shape
// (createController({...}) -> {flow, checkAccess, readAll}), the same
// injected-dependency discipline (no network/localStorage touched directly —
// tests never touch a real network or storage), and the same honest,
// coverage-aware, U-cached behavior — just without a tesseract path.
import { createFlow } from './flow_state.mjs';
import { convertSide } from './convert_side.mjs';
import { mapError } from './error_copy.mjs';
import { fieldEngineForSide } from './fill_mapper.mjs';

const SIDES = ['you', 'enemy'];

// D-036 fix: a view carries everything BOTH convertSide (Task 1's
// panelType/stats/specialsOwn/specialsEnemy/specialsObserved) AND
// classifyFields (fieldConf/fieldEngine, COORDINATOR RULING 2026-08-10 #2)
// need — so the assembly can derive S4's field-state/tally for EITHER side
// through this one function, never by reading a raw per-side `results[side]`
// directly (which is simply absent for a battle-covered side that had no
// upload of its own).
function extractView(result, side) {
  if (result.panel_type === 'battle') {
    return {
      panelType: 'battle',
      stats: (side === 'you' ? result.stats_you : result.stats_enemy) || {},
      fieldConf: (side === 'you' ? result.stats_you_conf : result.stats_enemy_conf) || {},
      fieldEngine: fieldEngineForSide(result, side),
      specialsOwn: (side === 'you' ? result.specials_you : result.specials_enemy) || [],
      specialsEnemy: (side === 'you' ? result.specials_enemy : result.specials_you) || [],
      specialsObserved: result.specials_observed,
    };
  }
  return {
    panelType: result.panel_type,
    stats: result.stats || {},
    fieldConf: result.field_conf || {},
    fieldEngine: fieldEngineForSide(result, side),
    specialsOwn: result.specials || [],
    specialsEnemy: [],
    specialsObserved: result.specials_observed,
  };
}

// Coverage-aware: a side with no bytes of its own but covered by the other
// side's battle-typed, successfully-read upload gets its view DERIVED from
// that same result's stats_you/stats_enemy/specials_you/specials_enemy
// aliases (service.py's own documented behavior) — never a second call.
// Exported (D-036): this is the SOLE source of per-side view data — the
// assembly must never read app.lastRead.results[side] directly for
// field-state/tally purposes, or a battle-covered side (no results[side]
// entry of its own) silently reads as entirely missing.
export function deriveViews(types, results) {
  const views = { you: null, enemy: null };
  for (const side of SIDES) {
    const other = side === 'you' ? 'enemy' : 'you';
    if (results[side] && !results[side].error) {
      views[side] = extractView(results[side], side);
    } else if (types[other] === 'battle' && results[other] && !results[other].error
               && results[other].panel_type === 'battle') {
      views[side] = extractView(results[other], side);
    }
  }
  return views;
}

export function createController({ genTable = {}, postPanel, fetchMe, storage } = {}) {
  const flow = createFlow({ genTable });

  async function checkAccess() {
    if (!fetchMe) return { allowed: false, plan: null, reachable: false, userId: null };
    let me;
    try {
      me = await fetchMe();
    } catch (err) {
      return { allowed: false, plan: null, reachable: false, userId: null };
    }
    const plan = me && me.user && me.user.plan;
    const userId = (me && me.user && me.user.user_id) || null;
    return { allowed: plan === 'pro', plan: plan || null, reachable: true, userId };
  }

  // Exactly one /shell/ocr/panel call per side per readAll() — no retry loop.
  // On any non-2xx, postPanel must reject with an Error carrying .status and
  // .body (asserted by controller.test.mjs, not by this module) so mapError
  // can read them. A leftover gap is left for the user to type, honestly,
  // never silently retried forever.
  async function readSide({ side, panelType, shotBytesList }) {
    if (!postPanel) return { error: true, mapped: mapError(0, null) };
    try {
      return await postPanel({ shotBytesList, side, panelType });
    } catch (err) {
      return { error: true, mapped: mapError(err.status ?? 0, err.body ?? null) };
    }
  }

  function loadCachedU(userId) {
    if (!storage || !userId) return null;
    const raw = storage.getItem(`ocr_u_${userId}`);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (err) { return null; }
  }
  function saveCachedU(userId, U) {
    if (!storage || !userId) return;
    storage.setItem(`ocr_u_${userId}`, JSON.stringify(U));
  }

  async function readAll(shotBytesBySide, userId = null) {
    const types = flow.types();
    const results = {};
    for (const side of SIDES) {
      const bytesList = shotBytesBySide[side];
      if (!bytesList || !bytesList.length) continue;
      results[side] = await readSide({ side, panelType: types[side], shotBytesList: bytesList });
    }
    const views = deriveViews(types, results);
    const conversion = {};
    const cachedU = loadCachedU(userId);
    for (const side of SIDES) {
      if (!views[side]) continue;
      const extra = side === 'you' ? { calibratedU: cachedU } : {};
      const outcome = convertSide({ ...views[side], ...extra });
      conversion[side] = outcome;
      if (side === 'you' && outcome.calibratedU) saveCachedU(userId, outcome.calibratedU);
    }
    return { results, views, conversion };
  }

  return { flow, checkAccess, readAll };
}
