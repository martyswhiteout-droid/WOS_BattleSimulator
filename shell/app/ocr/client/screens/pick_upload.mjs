export const TYPE_LABEL = { battle: 'Battle Report', scout: 'Scout Report', citystats: 'City Stats' };
export const YOU_TYPES = ['citystats', 'scout', 'battle'];
export const ENEMY_TYPES = ['scout', 'battle'];

export function dropzoneLabel({ side, covered }) {
  if (covered) return 'Add your own screenshot instead';
  return side === 'you' ? 'Tap to add your screenshot' : "Tap to add the enemy's screenshot";
}

export function computeS2ContinueState(coverage) {
  if (coverage.you && coverage.enemy) return { disabled: false, hint: null };
  if (coverage.you) return { disabled: true, hint: "Now add the enemy's screenshot." };
  if (coverage.enemy) return { disabled: true, hint: 'Now add your screenshot.' };
  return { disabled: true, hint: 'Add a screenshot to continue' };
}

export function renderS1() {
  return `
<section class="screen" data-screen="s1">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">Which screenshot do you have?</h1></header>
  <div class="ocrf-scr-body">
    <p class="ocrf-sub">Pick the one that matches your screenshot.</p>
    <button type="button" class="ocrf-pick-card ocrf-promoted" data-pick-type="battle"
      aria-label="Battle Report — best, fills both sides at once">
      <span class="ocrf-ribbon">BEST &middot; FILLS BOTH SIDES</span>
      <h2>Battle Report</h2>
      <p>Shows your stats and the enemy's stats together.</p>
      <span class="ocrf-crumb">Mail &rarr; Battle Report &rarr; Stat Bonuses</span>
    </button>
    <button type="button" class="ocrf-pick-card" data-pick-type="scout"
      aria-label="Scout Report — shows one side's stats">
      <h2>Scout Report</h2>
      <p>Shows one side's stats. Yours or the enemy's.</p>
      <span class="ocrf-crumb">Scout &rarr; Report &rarr; Stat Bonuses</span>
    </button>
    <button type="button" class="ocrf-pick-card ocrf-muted" data-pick-type="citystats"
      aria-label="City Stats — advanced, needs one-time setup">
      <span class="ocrf-tag">ADVANCED</span>
      <h2>City Stats<span class="ocrf-h2-sub">(called Bonus Overview in the game)</span></h2>
      <p>Your own city's stats. Needs a quick one-time setup.</p>
      <span class="ocrf-crumb">City &rarr; Bonuses &rarr; Overview</span>
    </button>
  </div>
</section>`.trim();
}

function sideSectionHtml(side, { type, covered, shotCount }) {
  const label = side === 'you' ? 'YOU' : 'ENEMY';
  const coveredNote = covered
    ? '<div class="ocrf-covered-note"><span class="ocrf-covered-check" aria-hidden="true">&#10003;</span>'
      + 'Covered by your battle report</div>'
    : '';
  const subLabel = covered ? '' : '<span>or paste it here</span>';
  return `
<div class="ocrf-side-section ocrf-side-${side}${covered ? ' ocrf-covered' : ''}" data-side="${side}">
  <div class="ocrf-side-head">
    <span class="ocrf-side-label">${label}</span>
    <button type="button" class="ocrf-type-tag" data-type-tag="${side}" aria-haspopup="menu">${TYPE_LABEL[type]} &#9662;</button>
  </div>
  ${coveredNote}
  <button type="button" class="ocrf-dropzone${covered ? ' ocrf-dropzone--muted' : ''}" data-dropzone="${side}">
    <b>${dropzoneLabel({ side, covered })}</b>
    ${subLabel}
  </button>
  <div class="ocrf-thumbs" data-thumbs="${side}"${shotCount ? '' : ' hidden'}></div>
</div>`.trim();
}

export function renderS2({ types, coverage, shots = { you: [], enemy: [] } }) {
  const you = sideSectionHtml('you',
    { type: types.you, covered: coverage.you && !shots.you.length, shotCount: shots.you.length });
  const enemy = sideSectionHtml('enemy',
    { type: types.enemy, covered: coverage.enemy && !shots.enemy.length, shotCount: shots.enemy.length });
  const state = computeS2ContinueState(coverage);
  return `
<section class="screen" data-screen="s2">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">Add your screenshots</h1></header>
  <div class="ocrf-scr-body">
    <div class="ocrf-s2-sides">${you}${enemy}</div>
    <div class="ocrf-hint-card"><span aria-hidden="true">&#128161;</span>
      <p>Long list? Take 2 screenshots that share a row. We'll join them.</p></div>
  </div>
  <footer class="ocrf-scr-foot">
    <button type="button" class="ocrf-btn-primary ocrf-btn-block" id="ocrfS2Continue"${state.disabled ? ' disabled' : ''}>Continue</button>
    ${state.hint ? `<p class="ocrf-foot-note">${state.hint}</p>` : ''}
  </footer>
</section>`.trim();
}

function e1PartialCopy(readCount, totalCount) {
  return {
    heading: `We read ${readCount} of ${totalCount} numbers`,
    body: 'The rest were too unclear to read. Add a clearer screenshot, or type them in yourself.',
    secondary: 'Type the missing numbers',
  };
}
const E1_WRONG_COPY = {
  heading: "That doesn't look like the right screenshot",
  body: 'This looks like a different screen. We need one with a numbers list, like this:',
  secondary: 'Type them in myself',
};

export function renderE1(variant, { readCount = 0, totalCount = 24 } = {}) {
  const copy = variant === 'partial' ? e1PartialCopy(readCount, totalCount) : E1_WRONG_COPY;
  return `
<section class="screen" data-screen="e1">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1" id="ocrfE1Heading">${copy.heading}</h1></header>
  <div class="ocrf-scr-body">
    <div class="ocrf-err-icon" aria-hidden="true">&#128269;</div>
    <p class="ocrf-sub" id="ocrfE1Body">${copy.body}</p>
    <p class="ocrf-fix-caption">A good example:</p>
    <div class="ocrf-e1-actions">
      <button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s2" data-recovery="1">
        <span aria-hidden="true">&#128247;</span> Add a clearer screenshot
      </button>
      <button type="button" class="ocrf-btn-ghost ocrf-btn-block" id="ocrfE1Secondary"
        data-goto="s4" data-show-missing="1">${copy.secondary}</button>
    </div>
  </div>
</section>`.trim();
}

/* ---- thin DOM wiring below: exercised by the Task 10 browser gate, not node:test ---- */

export function wireS1(root, { onPick }) {
  root.querySelectorAll('[data-pick-type]').forEach((card) => {
    card.addEventListener('click', () => onPick(card.dataset.pickType));
  });
}

export function wireS2(root, { onDropzone, onTypeTag, onContinue }) {
  root.querySelectorAll('[data-dropzone]').forEach((zone) => {
    zone.addEventListener('click', () => onDropzone(zone.dataset.dropzone));
  });
  root.querySelectorAll('[data-type-tag]').forEach((tag) => {
    tag.addEventListener('click', () => onTypeTag(tag.dataset.typeTag, tag));
  });
  const continueBtn = root.querySelector('#ocrfS2Continue');
  if (continueBtn) continueBtn.addEventListener('click', () => { if (!continueBtn.disabled) onContinue(); });
}

export function wireE1(root, { onRetake, onTypeMissing }) {
  root.querySelector('[data-recovery="1"]')?.addEventListener('click', onRetake);
  root.querySelector('#ocrfE1Secondary')?.addEventListener('click', onTypeMissing);
}
