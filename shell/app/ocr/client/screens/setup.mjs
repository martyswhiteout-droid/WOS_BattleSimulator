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

export function buildFillPlan({ conversion, heroesMe = null, heroesFoe = null }) {
  const plan = { me: null, foe: null, heroesMe: null, heroesFoe: null };
  if (conversion.you && conversion.you.outcome === 'ready') {
    plan.me = toApplyPanelPayload(conversion.you.percents);
  }
  if (conversion.enemy && conversion.enemy.outcome === 'ready') {
    plan.foe = toApplyPanelPayload(conversion.enemy.percents);
  }
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
