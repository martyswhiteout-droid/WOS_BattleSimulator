import { renderReviewGrid } from './review.mjs';
import { toApplyPanelPayload, toApplyHeroesPayload } from '../fill_mapper.mjs';

// D-044: the chip (and S5 generally) must never claim completeness from raw
// OCR readability alone — a side whose conversion refused (needs_specials /
// needs_calibration / blocked) is left unfilled by buildFillPlan, and the
// user has to be told that, on screen, with the reason. These notices are
// derived from the same `conversion` object buildFillPlan consumes, so the
// chip and the fill can never disagree again. A side with NO conversion
// entry at all (nothing uploaded, or the pure-manual path) is not a notice —
// there was never an OCR promise to break for that side.
const SIDE_LABELS = { you: 'your side', enemy: "the enemy side" };

export function conversionNotices(conversion = {}) {
  const notices = [];
  for (const side of ['you', 'enemy']) {
    const entry = conversion[side];
    if (!entry || entry.outcome === 'ready') continue;
    const label = SIDE_LABELS[side];
    const message = entry.outcome === 'needs_specials'
      ? `We read ${label}'s numbers, but didn't fill them in: ${entry.reason}. Anything you typed yourself was kept.`
      : `We didn't fill in ${label}: ${entry.reason}`;
    notices.push({ side, outcome: entry.outcome, message });
  }
  return notices;
}

export function computeChipText(tally, notices = []) {
  if (notices.length) {
    const sides = notices.map((n) => SIDE_LABELS[n.side]).join(' and ');
    const lead = tally.clear ? `All ${tally.total} numbers read` : `${tally.okCount} of ${tally.total} in`;
    return `${lead} · ${sides} not filled in — tap to check`;
  }
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

export function renderS5({ chipText, complete, states, notices = [] }) {
  // Undo's own visibility is driven entirely by its `hidden` attribute (thin wiring,
  // via shouldShowUndo(snapshot), toggles that after mount) — the wrapping <p> is never
  // itself conditionally hidden, there is nothing else in it whose visibility depends on
  // anything this pure template knows.
  // D-044: conversion notices render inside the expanded body, above the grid,
  // reusing the neutral .ocrf-s2-notice card (no new CSS round needed).
  const noticesHtml = notices.map((n) =>
    `<p class="ocrf-s2-notice" data-conv-notice="${n.side}">${n.message}</p>`).join('');
  // UXJ-005 fix (EVAL_UX_JOURNEY.md round 1): S4->S5 never moved focus to a
  // heading — #ocrfS5 had no heading element at all, so ocr_flow.js's show()
  // (which auto-focuses whatever `h1, h2[tabindex]` it finds after
  // rendering, the same generic mechanism every other screen already relies
  // on) found nothing and left focus on <body>. Same convention as S1-S4:
  // an `<h1 tabindex="-1">`, no bespoke focus-handling code needed here.
  return `
<section class="ocrf-s5" id="ocrfS5">
  <h1 tabindex="-1" id="ocrfS5Heading">Battle setup</h1>
  <div class="ocrf-stats-accordion">
    <button type="button" class="ocrf-stats-chip${complete ? ' ocrf-complete' : ' ocrf-needs-attention'}"
      id="ocrfS5Chip" aria-expanded="false" aria-controls="ocrfS5Body">
      <span class="ocrf-chip-text">${chipText}</span>
      <span class="ocrf-chip-caret" aria-hidden="true">&#8964;</span>
    </button>
    <div class="ocrf-stats-body" id="ocrfS5Body" hidden>
      ${noticesHtml}
      <button type="button" class="ocrf-link-btn" data-open-picture>See my screenshot</button>
      <div class="ocrf-tally-actions"><button type="button" class="ocrf-reset-btn" id="ocrfResetS5">Reset</button></div>
      ${renderReviewGrid(states)}
    </div>
  </div>
  <p class="ocrf-s5-links" id="ocrfS5Links">
    <button type="button" class="ocrf-link-btn" id="ocrfUndoChip" hidden>Put my last numbers back</button>
  </p>
  <p class="ocrf-s5-cta-row">
    <button type="button" class="ocrf-btn-primary" id="ocrfS5Run" data-run-forecast>See who wins <span aria-hidden="true">&rarr;</span></button>
  </p>
</section>`.trim();
}

/* ---- thin DOM wiring below: exercised by the Task 10 browser gate, not node:test ---- */

// UXJ-006 fix (EVAL_UX_JOURNEY.md round 1): OCR_UX_FLOW_SPEC.md §3 S5.4 —
// "Primary CTA: 'See who wins →' = the existing forecast button" — but the
// real button is prototype/index.html's own #runBtn ("Run forecast"), and
// that file is READ-ONLY (CLAUDE.md: never touch prototype/). The relabel
// happens the same way every other S5 side effect in applyFillPlan already
// does (applyPanel/updateFinalStats/scrollIntoView): a runtime DOM write
// from this injected module, scoped to the OCR-arrival context only — a
// user who never touches the OCR flow never sees the button change. Exported
// on its own (same split as the rest of this file's pure-ish decisions) so
// the relabel itself is unit-testable without a real DOM.
export function relabelForecastCta({ doc = document } = {}) {
  const btn = doc.getElementById('runBtn');
  if (btn) btn.innerHTML = 'See who wins <span aria-hidden="true">&rarr;</span>';
  return btn;
}

export function applyFillPlan(plan, { win = window, scroll = true } = {}) {
  if (plan.me && typeof win.applyPanel === 'function') win.applyPanel('me', plan.me);
  if (plan.foe && typeof win.applyPanel === 'function') win.applyPanel('foe', plan.foe);
  // D-044 adjunct: only claim scouted-mode when something was actually
  // applied — an all-refused plan (both sides unconverted, nothing typed)
  // must not silently re-mode the user's untouched, pre-existing numbers.
  if (plan.me || plan.foe) {
    const statsScouted = document.getElementById('statsScouted');
    const statsBase = document.getElementById('statsBase');
    if (statsScouted) statsScouted.checked = true;
    if (statsBase) statsBase.checked = false;
  }
  if (plan.heroesMe && typeof win.applyHeroes === 'function') win.applyHeroes('#capMe', plan.heroesMe);
  if (plan.heroesFoe && typeof win.applyHeroes === 'function') win.applyHeroes('#capFoe', plan.heroesFoe);
  if (typeof win.updateFinalStats === 'function') win.updateFinalStats();
  relabelForecastCta();
  // scroll:false on the S5-arrival path — the s5 branch anchors the viewport
  // on its own chip+panel cluster instead (a competing smooth scroll here
  // was one of the two authors of the UXJ-010 arrival-geometry fight).
  // Undo and any other caller keep the original behavior.
  if (scroll) {
    const statPanel = document.getElementById('statPanel');
    statPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

export function wireS5(root, { onToggleChip, onOpenPicture, onReset, onUndo, onRunForecast }) {
  root.querySelector('#ocrfS5Chip')?.addEventListener('click', onToggleChip);
  root.querySelector('[data-open-picture]')?.addEventListener('click', onOpenPicture);
  root.querySelector('#ocrfResetS5')?.addEventListener('click', onReset);
  root.querySelector('#ocrfUndoChip')?.addEventListener('click', onUndo);
  // UXJ-010 adjunct 3: the app's own #runBtn sits ~1200px below the chip
  // (after the final-stats comparison), so "chip + panel + See who wins in
  // one view" is physically impossible with that button alone. The S5
  // cluster carries its own primary CTA (the mock's S5 did exactly this);
  // it proxies the real button so the forecast pipeline stays the app's.
  if (onRunForecast) root.querySelector('[data-run-forecast]')?.addEventListener('click', onRunForecast);
}
