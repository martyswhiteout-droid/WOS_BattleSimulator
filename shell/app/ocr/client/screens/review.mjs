const CLASSES = ['Infantry', 'Lancer', 'Marksman'];
const STATS = ['Attack', 'Defense', 'Lethality', 'Health'];
const SIDE_NAME = { you: 'My side', enemy: 'Enemy' };
const STATE_ICON = { ok: '&#10003;', check: '!', missing: '+' };

export function fieldRenderState({ classification, savedValue }) {
  if (savedValue !== undefined && savedValue !== null) {
    return { state: 'ok', value: savedValue, typed: true };
  }
  return { state: classification.state, value: classification.value, typed: false };
}

export function provenanceText({ state, typed }) {
  if (state === 'missing') return 'Not read yet. Tap to type it.';
  return typed ? 'You typed this.' : 'Read from your screenshot.';
}

export function computeTally(states) {
  const total = states.length;
  const checkCount = states.filter((s) => s === 'check').length;
  const missingCount = states.filter((s) => s === 'missing').length;
  const okCount = total - checkCount - missingCount;
  if (checkCount === 0 && missingCount === 0) {
    return { okCount, checkCount, missingCount, total, clear: true,
      statusText: `All ${total} numbers are in.`, okPct: 100, checkPct: 0, missPct: 0 };
  }
  const checkPct = Math.round((checkCount / total) * 100);
  const missPct = Math.round((missingCount / total) * 100);
  const okPct = 100 - checkPct - missPct;   // remainder, not independently rounded — segments always sum to 100
  const parts = [`${okCount} of ${total} read well`];
  if (checkCount > 0) parts.push(`${checkCount} to check`);
  if (missingCount > 0) parts.push(`${missingCount} still empty`);
  return { okCount, checkCount, missingCount, total, clear: false, statusText: parts.join(' · '), okPct, checkPct, missPct };
}

export function validateEditorInput(raw) {
  const trimmed = (raw || '').trim();
  if (trimmed === '') return { ok: false, empty: true };
  if (!/^[+-]?\d+(\.\d+)?$/.test(trimmed)) return { ok: false, message: 'That needs to be a number.' };
  const num = parseFloat(trimmed);
  if (num < 0 || num > 6000) return { ok: false, message: 'Numbers here are usually between 0 and 6000.' };
  return { ok: true, value: num };
}

export function editorContentFor({ side, key, fieldState }) {
  const [cls, stat] = key.split('|');
  const title = `${SIDE_NAME[side]} · ${cls} · ${stat}`;
  if (fieldState.state === 'missing') {
    return { title, cropTag: 'NOT CAPTURED', cropBody: 'This part of the screenshot was not captured.',
      inputValue: '', help: "We couldn't read this one. Type the number." };
  }
  return { title, cropTag: 'WHAT WE SAW', cropBody: `${cls} ${stat}: +${Number(fieldState.value).toFixed(1)}`,
    inputValue: Number(fieldState.value).toFixed(1), help: 'Type over the number if it needs fixing.' };
}

export function nextResetState(current) {
  if (current === 'confirming') return { state: 'idle', label: 'Reset', shouldClear: true };
  return { state: 'confirming', label: 'Really reset?', shouldClear: false };
}

function fieldButtonHtml(side, key, fieldState) {
  const [, stat] = key.split('|');
  const display = fieldState.state === 'missing' ? '— —' : Number(fieldState.value).toFixed(1);
  const label = `${SIDE_NAME[side]} ${key.replace('|', ' ')}: ${display}. ${provenanceText(fieldState)}`;
  return `<button type="button" class="ocrf-rv-field ocrf-rv-${fieldState.state}" data-field="${side}-${key}" aria-label="${label}">
    <span class="ocrf-rv-lab">${stat}</span><span class="ocrf-rv-val">${display}</span>
    <span class="ocrf-rv-ic" aria-hidden="true">${STATE_ICON[fieldState.state]}</span>
  </button>`;
}

// A key absent from statesForSide (e.g. a caller passing a deliberately
// sparse/empty per-side object) reads exactly as "missing" — consistent with
// fill_mapper.mjs's classifyFields, which already defaults an absent key to
// FIELD_MISSING rather than throwing.
function fieldOrMissing(statesForSide, key) {
  return statesForSide[key] || { state: 'missing', value: null, typed: false };
}

function columnHtml(side, statesForSide) {
  const groups = CLASSES.map((cls) => {
    const fields = STATS.map((stat) => fieldButtonHtml(side, `${cls}|${stat}`, fieldOrMissing(statesForSide, `${cls}|${stat}`))).join('');
    return `<div class="ocrf-rv-group"><div class="ocrf-rv-group-head">${cls}</div><div class="ocrf-rv-stats">${fields}</div></div>`;
  }).join('');
  const headLabel = side === 'you' ? 'MY SIDE' : 'ENEMY';
  return `<div class="ocrf-rv-col ocrf-rv-${side === 'you' ? 'me' : 'enemy'}">
    <div class="ocrf-rv-col-head">${headLabel}</div>${groups}</div>`;
}

export function renderReviewGrid(states) {
  return `<div class="ocrf-review-grid">${columnHtml('you', states.you)}${columnHtml('enemy', states.enemy)}</div>`;
}

function tallyCardHtml(tally) {
  return `<div class="ocrf-tally-head"><span class="ocrf-tally-num">${tally.okCount}/${tally.total}</span>
  <span class="ocrf-tally-status${tally.clear ? ' ocrf-clear' : ''}">${tally.statusText}</span></div>
  <div class="ocrf-tally-bar"><i class="ocrf-b-ok" style="width:${tally.okPct}%"></i>
  <i class="ocrf-b-check" style="width:${tally.checkPct}%"></i>
  <i class="ocrf-b-missing" style="width:${tally.missPct}%"></i></div>`;
}

export function renderS4({ states, tally }) {
  return `
<section class="screen" data-screen="s4">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">Check your numbers</h1></header>
  <div class="ocrf-scr-body">
    <button type="button" class="ocrf-link-btn" data-open-picture>See my screenshot</button>
    <div class="ocrf-tally-card">${tallyCardHtml(tally)}</div>
    <div class="ocrf-tally-actions"><button type="button" class="ocrf-reset-btn" id="ocrfResetS4">Reset</button></div>
    ${renderReviewGrid(states)}
  </div>
  <footer class="ocrf-scr-foot">
    <button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s5">Next</button>
  </footer>
</section>`.trim();
}

export function renderEditorSheet() {
  return `
<div class="ocrf-modal-scrim" id="ocrfEditorScrim" aria-hidden="true" inert>
  <div class="ocrf-editor" role="dialog" aria-modal="true" aria-labelledby="ocrfEditorTitle">
    <div class="ocrf-editor-head"><h2 id="ocrfEditorTitle">&mdash;</h2>
      <button type="button" class="ocrf-close-x" id="ocrfEditorClose" aria-label="Close">&times;</button></div>
    <div class="ocrf-crop-box" id="ocrfEditorCrop"></div>
    <label class="ocrf-editor-label" for="ocrfEditorInput">Number</label>
    <input class="ocrf-big-input" id="ocrfEditorInput" type="text" inputmode="decimal" autocomplete="off">
    <p class="ocrf-editor-msg" id="ocrfEditorMsg" hidden></p>
    <p class="ocrf-editor-help" id="ocrfEditorHelp"></p>
    <div class="ocrf-editor-actions">
      <button type="button" class="ocrf-btn-ghost" id="ocrfEditorCancel">Cancel</button>
      <button type="button" class="ocrf-btn-primary" id="ocrfEditorSave">Save</button>
    </div>
  </div>
</div>`.trim();
}

// D-040 fix: previously renderPictureView's HTML was appended straight into
// the page with no scrim/close at all — no way to dismiss it, nothing for
// inert/Escape to act on. This is the same scrim+inert shell as
// renderEditorSheet, sized for the two-column grid (.ocrf-picture-scroll,
// already self-styled) instead of the narrow editor card.
export function renderPictureSheet() {
  return `
<div class="ocrf-modal-scrim" id="ocrfPictureScrim" aria-hidden="true" inert>
  <div class="ocrf-picture-wrap">
    <button type="button" class="ocrf-close-x ocrf-picture-close" id="ocrfPictureClose" aria-label="Close">&times;</button>
    <div id="ocrfPictureBody"></div>
  </div>
</div>`.trim();
}

export function renderPictureView(states) {
  const col = (side) => CLASSES.map((cls) => {
    const rows = STATS.map((stat) => {
      const fs = fieldOrMissing(states[side], `${cls}|${stat}`);
      if (fs.state === 'missing') {
        return `<div class="ocrf-game-row ocrf-dim"><span class="ocrf-gr-label">${stat}</span>`
          + '<span class="ocrf-gr-val ocrf-dim">Not captured</span></div>';
      }
      return `<div class="ocrf-game-row"><span class="ocrf-gr-label">${stat}</span>`
        + `<span class="ocrf-gr-val">+${Number(fs.value).toFixed(1)}</span></div>`;
    }).join('');
    return `<div class="ocrf-rv-group-head">${cls}</div>${rows}`;
  }).join('');
  return `<div class="ocrf-picture-scroll"><div>${col('you')}</div><div>${col('enemy')}</div></div>`;
}

/* ---- thin DOM wiring below: exercised by the Task 10 browser gate, not node:test ---- */

export function wireS4(root, { onOpenField, onOpenPicture, onReset }) {
  root.querySelectorAll('[data-field]').forEach((btn) => {
    btn.addEventListener('click', () => onOpenField(btn.dataset.field));
  });
  root.querySelector('[data-open-picture]')?.addEventListener('click', onOpenPicture);
  root.querySelector('#ocrfResetS4')?.addEventListener('click', onReset);
}
