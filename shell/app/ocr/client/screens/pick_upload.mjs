export const TYPE_LABEL = { battle: 'Battle Report', scout: 'Scout Report', citystats: 'City Stats' };
export const YOU_TYPES = ['citystats', 'scout', 'battle'];
export const ENEMY_TYPES = ['scout', 'battle'];

// UXJ-002 fix (EVAL_UX_JOURNEY.md round 1): "faithful mini-renderings of the
// real panels" (OCR_UX_FLOW_SPEC.md §3 S1) — ported verbatim from the mock's
// own SAMPLES/renderSample (prototype/mocks/ocr_flow_mock.html), including
// its exact sample numbers, onto this build's `ocrf-`-prefixed classes (the
// mock's own originals are IP-safe: hand-typed sample rows, never a captured
// game screenshot). `city` renamed to `citystats` to match this file's real
// panel-type vocabulary (TYPE_LABEL/YOU_TYPES above), not the mock's demo key.
const SAMPLES = {
  battle: [
    { label: 'Infantry Attack', me: '+4859.0%', enemy: '+694.3%' },
    { label: 'Infantry Defense', me: '+4098.0%', enemy: '+545.6%' },
    { label: 'Infantry Lethality', me: '+2683.0%', enemy: '+495.7%' },
  ],
  scout: [
    { label: 'Infantry Attack', val: '+4491.6%' },
    { label: 'Infantry Defense', val: '+3979.1%' },
    { label: 'Infantry Lethality', val: '+2794.3%' },
  ],
  citystats: [
    { label: "Troops' Attack", val: '748.49%' },
    { label: "Troops' Defense", val: '775.42%' },
    { label: 'Infantry Attack', val: '658.25%' },
  ],
};

// Owner request 2026-08-15 ("the samples need to look real... users will
// resonate with the game screenshots"): the samples are now REAL crops of
// the owner's own fixture captures, served from the mounted client tree
// (shell/app/ocr/client/samples/, no-cache). Battle deliberately shows the
// TWO required shots, numbered — the strongest possible cure for the
// forget-the-popup trap (D-043/D-045): shot 1's crop even shows the real
// "!" icon that opens shot 2. The hand-typed mini-panels below survive as
// renderSampleFallback: a promoted bundle strips game-IP raster art
// (PRODUCTION_CRITERIA F1 / promote.py), and the img error listener in
// ocr_flow.js swaps the figures back to the drawn panels automatically.
const SAMPLE_IMG_BASE = '/shell/ocr/client/samples';

export function renderSample(type) {
  const fig = (src, alt, badge, caption) => (
    '<figure class="ocrf-sample-shot">'
    + (badge ? `<span class="ocrf-sample-badge" aria-hidden="true">${badge}</span>` : '')
    + `<img class="ocrf-sample-img" src="${SAMPLE_IMG_BASE}/${src}" alt="${alt}">`
    + (caption ? `<figcaption class="ocrf-sample-cap">${caption}</figcaption>` : '')
    + '</figure>');
  if (type === 'battle') {
    return `<div class="ocrf-sample ocrf-sample--pair" data-sample="battle">`
      + fig('sample_battle_panel.jpg', "The battle report's Stat Bonuses panel", '1', 'Stat Bonuses list')
      + fig('sample_battle_popup.jpg', 'The Notes on Special Bonuses popup', '2', 'The popup behind the ! icon')
      + '</div>';
  }
  if (type === 'scout') {
    return `<div class="ocrf-sample" data-sample="scout">`
      + fig('sample_scout.jpg', "The scout report's Stat Bonuses panel", '', '')
      + '</div>';
  }
  if (type === 'citystats') {
    return `<div class="ocrf-sample" data-sample="citystats">`
      + fig('sample_citystats.jpg', 'The Bonus Overview panel', '', '')
      + '</div>';
  }
  return '';
}

export function renderSampleFallback(type) {
  if (type === 'battle') {
    const rows = SAMPLES.battle.map((r) => (
      `<div class="ocrf-mp-b-row"><span class="ocrf-mp-b-val ocrf-mp-b-me">${r.me}</span>`
      + `<span class="ocrf-mp-b-lab">${r.label}</span><span class="ocrf-mp-b-val ocrf-mp-b-enemy">${r.enemy}</span></div>`
    )).join('');
    return `<div class="ocrf-mini-panel ocrf-mini-panel--battle"><div class="ocrf-mp-b-head">`
      + `<span class="ocrf-mp-b-side ocrf-mp-b-me">MY SIDE</span><span class="ocrf-mp-b-side ocrf-mp-b-enemy">ENEMY</span></div>${rows}</div>`;
  }
  if (type === 'scout') {
    const rows = SAMPLES.scout.map((r) => (
      `<div class="ocrf-mp-s-row"><span class="ocrf-mp-s-lab">${r.label}</span><span class="ocrf-mp-s-val">${r.val}</span></div>`
    )).join('');
    return `<div class="ocrf-mini-panel ocrf-mini-panel--scout">${rows}</div>`;
  }
  if (type === 'citystats') {
    const rows = SAMPLES.citystats.map((r) => (
      `<div class="ocrf-mp-c-row"><span class="ocrf-mp-c-lab">${r.label}</span><span class="ocrf-mp-c-val">${r.val}</span></div>`
    )).join('');
    return `<div class="ocrf-mini-panel ocrf-mini-panel--city"><div class="ocrf-mp-c-head">Bonus Overview</div>${rows}</div>`;
  }
  return '';
}

// Dropzone camera/upload glyph — ported verbatim from the mock's dzSvg(),
// self-contained inline SVG (no external asset, no CDN, no game screenshot).
const DZ_ICON = '<svg class="ocrf-dz-icon" viewBox="0 0 48 48" aria-hidden="true">'
  + '<rect x="6" y="14" width="36" height="26" rx="4" fill="none" stroke="currentColor" stroke-width="3"/>'
  + '<circle cx="24" cy="27" r="7" fill="none" stroke="currentColor" stroke-width="3"/>'
  + '<rect x="17" y="8" width="14" height="7" rx="2" fill="currentColor"/></svg>';

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
      ${renderSample('battle')}
      <h2>Battle Report</h2>
      <p>Shows your stats and the enemy's stats together.</p>
      <span class="ocrf-crumb">Mail &rarr; Battle Report &rarr; Stat Bonuses</span>
    </button>
    <button type="button" class="ocrf-pick-card" data-pick-type="scout"
      aria-label="Scout Report — shows one side's stats">
      ${renderSample('scout')}
      <h2>Scout Report</h2>
      <p>Shows one side's stats. Yours or the enemy's.</p>
      <span class="ocrf-crumb">Scout &rarr; Report &rarr; Stat Bonuses</span>
    </button>
    <button type="button" class="ocrf-pick-card ocrf-muted" data-pick-type="citystats"
      aria-label="City Stats — advanced, needs one-time setup">
      <span class="ocrf-tag">ADVANCED</span>
      ${renderSample('citystats')}
      <h2>City Stats<span class="ocrf-h2-sub">(called Bonus Overview in the game)</span></h2>
      <p>Your own city's stats. Needs a quick one-time setup.</p>
      <span class="ocrf-crumb">City &rarr; Bonuses &rarr; Overview</span>
    </button>
  </div>
</section>`.trim();
}

// D-035 fix: one thumb per shot, each with a >=44px remove control keyed by
// (side, INDEX) — mock's own convention (ocr_flow_mock.html's
// renderThumbsFor/removeThumbSide use position, not an id, since its own
// thumbsArrFor is a placeholder array; this build's shots DO carry real
// stable ids, but the delegate/removal wiring stays index-based to match
// the mock 1:1 — the index is resolved back to the real shot id where the
// removal actually happens, in ocr_flow.js). The icon is the same generic
// "screenshot" glyph the mock uses (never a real image preview — no
// screenshot bytes are ever re-rendered as an <img>, consistent with
// "screenshots are never saved").
const THUMB_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="3" '
  + 'fill="none" stroke="currentColor" stroke-width="2"/><circle cx="8" cy="10" r="2" fill="currentColor"/>'
  + '<path d="M4 17 L9 12 L13 15 L16 11 L20 16" fill="none" stroke="currentColor" stroke-width="2"/></svg>';

export function renderThumbs(side, ids) {
  return ids.map((_, i) => (
    `<div class="ocrf-thumb">${THUMB_ICON}<button type="button" class="ocrf-thumb-x" aria-label="Remove screenshot" `
    + `data-remove-thumb-side="${side}" data-remove-thumb="${i}">&times;</button></div>`
  )).join('');
}

// Owner arrangement 2026-08-15: the upload area is ROWS — each row a real
// sample on the left and its OWN labeled add-button on the right, so it is
// "very clear which is which". Battle = THREE rows (Heroes / Battle stats /
// Buffs); scout and citystats = one row each. Every row's zone feeds the
// SAME per-side shot set (the server sorts shots by content, so there is no
// wrong slot to put a screenshot in). The Heroes row is capture-only today:
// captain auto-set needs the badge-reading derivation (spike 2026-08-15:
// RapidOCR reads the star rows cleanly but mangles gen-badge digits, and
// the portrait->class order convention is unproven) — the copy says
// exactly that, no dead-slot pretence.
export const UPLOAD_ROWS = {
  battle: [
    // Owner feedback 2026-08-25: 'Heroes + Experts', no OPTIONAL tag, and the
    // capture-only explainer sentence removed. Still capture-only in the
    // engine until badge-reading ships — the spec amendment records that the
    // REQUIRED presentation is the owner's call.
    { key: 'battle_heroes', img: 'sample_battle_heroes.jpg', alt: "The report's heroes and experts",
      label: 'Heroes + Experts', tag: '',
      copy: 'The heroes and experts shown on the report.' },
    { key: 'battle_panel', img: 'sample_battle_panel.jpg', alt: "The battle report's Stat Bonuses panel",
      label: 'Battle stats', tag: '',
      copy: 'The Stat Bonuses list — fills all 24 numbers, both sides.' },
    // Owner feedback 2026-08-25: NEEDED tag dropped (hard to see); this row
    // takes 1 or 2 screenshots; an explicit "no buffs" attestation replaces
    // silent absence (rendered below the rows, battle only).
    { key: 'battle_popup', img: 'sample_battle_popup.jpg', alt: 'The Notes on Special Bonuses popup',
      label: 'Buffs', tag: '',
      copy: 'Tap the ! next to “Stat Bonuses”. Long list? Add up to 2 screenshots.' },
    // Owner feedback 2026-08-25: an OPTIONAL Troop Power row — troop type,
    // quality, FC tier, T12 level, and per-level counts for the final
    // checks. Capture-only until the Troop Power parser ships (the sample
    // image is PENDING an owner capture; the img-error fallback shows the
    // alt text until then).
    { key: 'battle_troop_power', img: 'sample_troop_power.jpg', alt: 'The Troop Power screen',
      label: 'Troop Power', tag: 'OPTIONAL',
      copy: 'Your Troop Power screen — troop counts and tiers for the final checks.' },
  ],
  scout: [
    { key: 'scout', img: 'sample_scout.jpg', alt: "The scout report's Stat Bonuses panel",
      label: 'Scout stats', tag: '',
      copy: 'The Stat Bonuses list from the scout report.' },
  ],
  citystats: [
    { key: 'citystats', img: 'sample_citystats.jpg', alt: 'The Bonus Overview panel',
      label: 'City Stats', tag: '',
      copy: 'The Bonus Overview — scroll to include the City Defenses rows.' },
  ],
};

function uploadRowsHtml(side, type, noBuffs = false) {
  const rows = (UPLOAD_ROWS[type] || []).map((row) => `
<div class="ocrf-sample-row" data-sample-row="${row.key}">
  <figure class="ocrf-sample-shot">
    <img class="ocrf-sample-img" src="${SAMPLE_IMG_BASE}/${row.img}" alt="${row.alt}">
  </figure>
  <button type="button" class="ocrf-dropzone ocrf-row-zone" data-dropzone="${side}">
    <span class="ocrf-row-label">${row.label}${row.tag ? ` <span class="ocrf-row-tag${row.tag === 'OPTIONAL' ? ' ocrf-row-tag--muted' : ''}">${row.tag}</span>` : ''}</span>
    <span class="ocrf-row-copy">${row.copy}</span>
    <span class="ocrf-row-add">${DZ_ICON}<b>Tap · paste · drop</b></span>
  </button>
</div>`);
  // Owner feedback 2026-08-25: explicit opt-out INSTEAD of silent absence -
  // the user attests there are no special bonuses on either side. Battle
  // only (the popup is a battle artifact; scout needs no conversion).
  if (type === 'battle') {
    rows.push(`
<button type="button" class="ocrf-no-buffs${noBuffs ? ' ocrf-no-buffs--on' : ''}" data-no-buffs="${side}"
  aria-pressed="${noBuffs ? 'true' : 'false'}">
  <span class="ocrf-no-buffs-box" aria-hidden="true">${noBuffs ? '&#10003;' : ''}</span>
  No buffs on either side — skip the popup
</button>`);
  }
  return rows.join('');
}

function sideSectionHtml(side, { type, covered, shotCount, ids = [], noBuffs = false }) {
  const label = side === 'you' ? 'YOU' : 'ENEMY';
  // A covered side needs no reference rows (there's nothing to upload here);
  // an uncovered side gets the per-row samples for its CURRENT type.
  const middleHtml = covered
    ? '<div class="ocrf-covered-note"><span class="ocrf-covered-check" aria-hidden="true">&#10003;</span>'
      + 'Covered by your battle report</div>'
      + `<button type="button" class="ocrf-dropzone ocrf-dropzone--muted" data-dropzone="${side}">`
      + `${DZ_ICON}<b>${dropzoneLabel({ side, covered })}</b></button>`
    : uploadRowsHtml(side, type, noBuffs);
  return `
<div class="ocrf-side-section ocrf-side-${side}${covered ? ' ocrf-covered' : ''}" data-side="${side}">
  <div class="ocrf-side-head">
    <span class="ocrf-side-label">${label}</span>
    <button type="button" class="ocrf-type-tag" data-type-tag="${side}" aria-haspopup="menu">${TYPE_LABEL[type]} &#9662;</button>
  </div>
  ${middleHtml}
  <div class="ocrf-thumbs" data-thumbs="${side}"${shotCount ? '' : ' hidden'}>${renderThumbs(side, ids)}</div>
</div>`.trim();
}

export function renderS2({ types, coverage, shots = { you: [], enemy: [] }, notice = null, noBuffs = false }) {
  const you = sideSectionHtml('you',
    { type: types.you, covered: coverage.you && !shots.you.length, shotCount: shots.you.length, ids: shots.you, noBuffs });
  const enemy = sideSectionHtml('enemy',
    { type: types.enemy, covered: coverage.enemy && !shots.enemy.length, shotCount: shots.enemy.length, ids: shots.enemy, noBuffs });
  const state = computeS2ContinueState(coverage);
  // D-039: the E1-recovery removal notice (mock's #s2Notice) — only rendered
  // when actually supplied, never an empty placeholder element.
  const noticeHtml = notice ? `<p class="ocrf-s2-notice" id="ocrfS2Notice">${notice}</p>` : '';
  // D-045's popup guarantee now lives IN the battle rows themselves — the
  // "Buffs · NEEDED" row with the real popup screenshot teaches the
  // requirement in place, so the old separate hint card is gone (one less
  // thing to read; the same information, exactly where the action happens).
  return `
<section class="screen" data-screen="s2">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">Add your screenshots</h1></header>
  <div class="ocrf-scr-body">
    ${noticeHtml}
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

// UXJ-004 fix (EVAL_UX_JOURNEY.md round 1): HTTP errors during a read (429
// quota/burst, 402 mid-session, 503, 401 session expiry) always rendered as
// the WRONG-screenshot copy above — a fabricated cause (the screenshot was
// never the problem). error_copy.mjs's mapError() already computes honest,
// distinct copy per failure mode plus a `cta` naming the correct recovery
// action; this maps each cta to that action's markup. Every action is
// expressed as a plain data-goto/data-recovery/data-show-missing button —
// the SAME generic delegate (D-037/D-039) every other screen's navigation
// already uses — so "Try again" (retry the exact same uploaded bytes) is
// just `data-goto="s3"` (its render branch always re-reads app.shots fresh)
// and "Type them/it in myself" is the SAME `data-goto="s4"
// data-show-missing="1"` E1's other two variants already use. (app.lastRead
// is set before this branch is ever chosen, so in a mixed outcome — one
// side errors, the other genuinely succeeded — the successful side still
// shows its real read on S4; only the side that actually failed needs
// typing.) The one exception is 'upgrade': "See plans" has a real side
// effect (POST /shell/billing/checkout, same request entry.mjs's
// renderUpgradeNote/wireUpgradeNote already makes for the entry-gate 402)
// and gets its own id, wired once in ocr_flow.js's 'e1' render branch.
function e1ActionHtml(cta) {
  if (cta === 'upgrade') {
    return `<button type="button" class="ocrf-btn-primary ocrf-btn-block" id="ocrfE1Upgrade">See plans</button>
      <button type="button" class="ocrf-btn-ghost ocrf-btn-block" data-goto="s4" data-show-missing="1">Type it in myself</button>`;
  }
  if (cta === 'wait') {
    // Quota exhausted until midnight — retrying is pointless, per mapError's own copy.
    return '<button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s4" data-show-missing="1">Type the numbers in myself</button>';
  }
  if (cta === 'retake') {
    return `<button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s2" data-recovery="1">
        <span aria-hidden="true">&#128247;</span> Add a different screenshot</button>
      <button type="button" class="ocrf-btn-ghost ocrf-btn-block" data-goto="s4" data-show-missing="1">Type them in myself</button>`;
  }
  // slow_down (429 burst) / retry_or_type (503, unknown) / sign_in (401):
  // the screenshots themselves were never the problem — retry the exact
  // same upload, or fall back to typing.
  return `<button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s3">Try again</button>
    <button type="button" class="ocrf-btn-ghost ocrf-btn-block" data-goto="s4" data-show-missing="1">Type them in myself</button>`;
}

export function renderE1(variant, opts = {}) {
  if (variant === 'error') {
    const { mapped } = opts;
    return `
<section class="screen" data-screen="e1">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1" id="ocrfE1Heading">${mapped.heading}</h1></header>
  <div class="ocrf-scr-body">
    <div class="ocrf-err-icon" aria-hidden="true">&#9888;&#65039;</div>
    <p class="ocrf-sub" id="ocrfE1Body">${mapped.body}</p>
    <div class="ocrf-e1-actions">${e1ActionHtml(mapped.cta)}</div>
  </div>
</section>`.trim();
  }
  const copy = variant === 'partial' ? e1PartialCopy(opts.readCount ?? 0, opts.totalCount ?? 24) : E1_WRONG_COPY;
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

export function wireS2(root, { onDropzone, onTypeTag, onContinue, onNoBuffs }) {
  root.querySelectorAll('[data-dropzone]').forEach((zone) => {
    zone.addEventListener('click', () => onDropzone(zone.dataset.dropzone));
  });
  root.querySelectorAll('[data-no-buffs]').forEach((btn) => {
    btn.addEventListener('click', () => onNoBuffs && onNoBuffs());
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
