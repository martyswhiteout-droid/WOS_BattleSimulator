import { renderReviewGrid } from './review.mjs';
import { toApplyPanelPayload, toApplyHeroesPayload } from '../fill_mapper.mjs';

export function computeChipText(tally) {
  if (tally.clear) {
    return `All ${tally.total} numbers in <span class="ocrf-chip-ok-ic" aria-hidden="true">&#10003;</span> — tap to check`;
  }
  const parts = [`${tally.okCount} of ${tally.total} in`];
  if (tally.checkCount > 0) parts.push(`${tally.checkCount} to check`);
  if (tally.missingCount > 0) parts.push(`${tally.missingCount} still empty`);
  return `${parts.join(' · ')} — tap to check`;
}

export function shouldShowUndo(snapshot) {
  return !!snapshot;
}

// D-042 fix: previously built solely from `conversion` — a side with no
// upload (or a totally-failed read, E1 "wrong") has no conversion entry at
// all, and even a ready conversion's own percents never reflect whatever
// the user corrected in S4's editor (savedValues), since that was never
// read here. The fill plan now merges savedValues OVER conversion-derived
// percents per side (user edits always win — the review screen's whole
// point) and fills even when conversion is entirely absent, i.e. the
// manual-only path ("Type them in myself"). A side stays unfilled (null)
// only when BOTH are empty — conversion never fabricates a non-ready
// side's own numbers (unchanged rule), it is only ever savedValues that can
// rescue an otherwise-empty side.
function mergedPercentsForSide(sideConversion, savedValuesForSide) {
  const base = (sideConversion && sideConversion.outcome === 'ready') ? sideConversion.percents : {};
  return { ...base, ...(savedValuesForSide || {}) };
}

export function buildFillPlan({ conversion, savedValues = { you: {}, enemy: {} }, heroesMe = null, heroesFoe = null }) {
  const plan = { me: null, foe: null, heroesMe: null, heroesFoe: null };
  const meMerged = mergedPercentsForSide(conversion.you, savedValues.you);
  if (Object.keys(meMerged).length) plan.me = toApplyPanelPayload(meMerged);
  const foeMerged = mergedPercentsForSide(conversion.enemy, savedValues.enemy);
  if (Object.keys(foeMerged).length) plan.foe = toApplyPanelPayload(foeMerged);
  if (heroesMe) plan.heroesMe = toApplyHeroesPayload(heroesMe);
  if (heroesFoe) plan.heroesFoe = toApplyHeroesPayload(heroesFoe);
  return plan;
}

export function renderS5({ chipText, complete, states }) {
  // Undo's own visibility is driven entirely by its `hidden` attribute (thin wiring,
  // via shouldShowUndo(snapshot), toggles that after mount) — the wrapping <p> is never
  // itself conditionally hidden, there is nothing else in it whose visibility depends on
  // anything this pure template knows.
  return `
<section class="ocrf-s5" id="ocrfS5">
  <div class="ocrf-stats-accordion">
    <button type="button" class="ocrf-stats-chip${complete ? ' ocrf-complete' : ' ocrf-needs-attention'}"
      id="ocrfS5Chip" aria-expanded="false" aria-controls="ocrfS5Body">
      <span class="ocrf-chip-text">${chipText}</span>
      <span class="ocrf-chip-caret" aria-hidden="true">&#8964;</span>
    </button>
    <div class="ocrf-stats-body" id="ocrfS5Body" hidden>
      <button type="button" class="ocrf-link-btn" data-open-picture>See my screenshot</button>
      <div class="ocrf-tally-actions"><button type="button" class="ocrf-reset-btn" id="ocrfResetS5">Reset</button></div>
      ${renderReviewGrid(states)}
    </div>
  </div>
  <p class="ocrf-s5-links" id="ocrfS5Links">
    <button type="button" class="ocrf-link-btn" id="ocrfUndoChip" hidden>Put my last numbers back</button>
  </p>
</section>`.trim();
}

/* ---- thin DOM wiring below: exercised by the Task 10 browser gate, not node:test ---- */

export function applyFillPlan(plan, { win = window } = {}) {
  if (plan.me && typeof win.applyPanel === 'function') win.applyPanel('me', plan.me);
  if (plan.foe && typeof win.applyPanel === 'function') win.applyPanel('foe', plan.foe);
  const statsScouted = document.getElementById('statsScouted');
  const statsBase = document.getElementById('statsBase');
  if (statsScouted) statsScouted.checked = true;
  if (statsBase) statsBase.checked = false;
  if (plan.heroesMe && typeof win.applyHeroes === 'function') win.applyHeroes('#capMe', plan.heroesMe);
  if (plan.heroesFoe && typeof win.applyHeroes === 'function') win.applyHeroes('#capFoe', plan.heroesFoe);
  if (typeof win.updateFinalStats === 'function') win.updateFinalStats();
  const statPanel = document.getElementById('statPanel');
  statPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export function wireS5(root, { onToggleChip, onOpenPicture, onReset, onUndo }) {
  root.querySelector('#ocrfS5Chip')?.addEventListener('click', onToggleChip);
  root.querySelector('[data-open-picture]')?.addEventListener('click', onOpenPicture);
  root.querySelector('#ocrfResetS5')?.addEventListener('click', onReset);
  root.querySelector('#ocrfUndoChip')?.addEventListener('click', onUndo);
}
