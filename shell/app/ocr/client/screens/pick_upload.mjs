// screens/pick_upload.mjs — the combined Upload screen (owner redesign
// 2026-08-29, built to the multi-doc-upload research synthesis):
//   type tabs (Battle / Scout / City) -> summary fraction -> slot GRID with
//   every slot visible at once -> sticky Scan. One slot per named document,
//   state ON the slot (dashed empty w/ dimmed sample-crop icon, thumbnail +
//   check when added, count badge for multi, x to remove), * = required,
//   "optional" = the one word that earns its place. Stacked You/Enemy groups
//   for scout/city (research: tabs hide the other party's completion state).
// Replaces the old S1 type-cards + S2 rows two-screen flow entirely.
export const TYPE_LABEL = { battle: 'Battle Report', scout: 'Scout Report', citystats: 'City Stats' };
export const TAB_LABEL = { battle: 'Battle', scout: 'Scout', citystats: 'City' };
export const YOU_TYPES = ['citystats', 'scout', 'battle'];
export const ENEMY_TYPES = ['scout', 'battle'];

const SAMPLE_IMG_BASE = '/shell/ocr/client/samples';

// One entry per named document slot. `max` = how many screenshots the slot
// takes (long lists scroll -> 2). `noneable` = the user may attest "None"
// instead of uploading (buffs). Battle is ONE group (the report carries both
// sides); scout/city repeat per side.
export const SLOTS = {
  battle: [
    { key: 'heroes', label: 'Heroes', required: true, max: 1, img: 'sample_battle_heroes.jpg' },
    { key: 'stats', label: 'Stats', required: true, max: 2, img: 'sample_battle_panel.jpg' },
    { key: 'buffs', label: 'Buffs', required: true, max: 2, img: 'sample_battle_popup.jpg', noneable: true },
    // img null (UXG-003): the Troop Power sample capture is still owed by the
    // owner — no img element until it ships (a 404 per open is worse than the
    // dashed tile the img-error fallback would leave anyway).
    { key: 'power', label: 'Power', required: false, max: 1, img: null },
  ],
  scout: [
    { key: 'scout', label: 'Stats', required: true, max: 2, img: 'sample_scout.jpg' },
  ],
  citystats: [
    { key: 'city', label: 'City', required: true, max: 2, img: 'sample_citystats.jpg' },
  ],
};

// Which sides a type needs. Battle: one shared group stored on 'you'.
// City: the enemy side is a scout capture (ENEMY_TYPES has no citystats).
export function groupsFor(type) {
  if (type === 'battle') return [{ side: 'you', label: null, slots: SLOTS.battle }];
  if (type === 'citystats') {
    return [
      { side: 'you', label: 'You', slots: SLOTS.citystats },
      { side: 'enemy', label: 'Enemy', slots: SLOTS.scout },
    ];
  }
  return [
    { side: 'you', label: 'You', slots: SLOTS.scout },
    { side: 'enemy', label: 'Enemy', slots: SLOTS.scout },
  ];
}

// Pure per-slot state. shots = [{id, slot}] for ONE side; attested = the
// buffs "None" attestation flag.
export function slotState(slotDef, sideShots, attested) {
  const count = sideShots.filter((s) => s.slot === slotDef.key).length;
  if (count > 0) return { state: 'added', count };
  if (slotDef.noneable && attested) return { state: 'none', count: 0 };
  return { state: 'empty', count: 0 };
}

export function uploadModel({ type, shots, attested = false }) {
  const groups = groupsFor(type).map((g) => ({
    ...g,
    slots: g.slots.map((def) => ({ ...def, ...slotState(def, shots[g.side] || [], attested) })),
  }));
  const required = groups.flatMap((g) => g.slots.filter((s) => s.required));
  const done = required.filter((s) => s.state !== 'empty').length;
  return { groups, done, total: required.length, canScan: done === required.length };
}

function slotTile(side, s) {
  const cue = s.required
    ? '<span class="ocrf-slot-req" aria-label="required">*</span>'
    : '<span class="ocrf-slot-opt">optional</span>';
  const badge = s.state === 'added'
    ? `<span class="ocrf-slot-check" aria-hidden="true">&#10003;</span>${s.count > 1 ? `<span class="ocrf-slot-count">${s.count}</span>` : ''}`
    : s.state === 'none'
      ? '<span class="ocrf-slot-check ocrf-slot-check--none" aria-hidden="true">&#10003;</span>'
      : '';
  const remove = s.state === 'added'
    ? `<button type="button" class="ocrf-slot-x" data-slot-remove="${side}:${s.key}" aria-label="Remove">&times;</button>`
    : '';
  const noneLink = s.noneable && s.state === 'empty'
    ? `<button type="button" class="ocrf-slot-none" data-slot-none="${side}:${s.key}">None</button>`
    : '';
  const stateLabel = s.state === 'added' ? `${s.count} added` : s.state === 'none' ? 'none' : (s.required ? 'required' : 'optional');
  return `
<div class="ocrf-slot ocrf-slot--${s.state}${s.required ? '' : ' ocrf-slot--optional'}" data-slot-tile="${side}:${s.key}">
  <button type="button" class="ocrf-slot-main" data-slot="${side}:${s.key}" data-slot-state="${s.state}"
    aria-label="${s.label}, ${stateLabel}">
    <span class="ocrf-slot-fig"${s.thumbUrl ? ` style="background-image:url('${s.thumbUrl}')"` : ''}>
      ${s.thumbUrl || !s.img ? '' : `<img class="ocrf-sample-img ocrf-slot-sample" src="${SAMPLE_IMG_BASE}/${s.img}" alt="">`}
    </span>
    <span class="ocrf-slot-label">${s.label} ${cue}</span>
    ${badge}
  </button>
  ${remove}${noneLink}
</div>`;
}

export function renderUpload({ type, model, notice = null }) {
  const tabs = ['battle', 'scout', 'citystats'].map((t) => (
    `<button type="button" class="ocrf-type-tab${t === type ? ' ocrf-type-tab--on' : ''}"
      data-type-tab="${t}" aria-pressed="${t === type}">${TAB_LABEL[t]}</button>`
  )).join('');
  const pips = Array.from({ length: model.total }, (_, i) => (
    `<span class="ocrf-pip${i < model.done ? ' ocrf-pip--on' : ''}" aria-hidden="true"></span>`
  )).join('');
  const groups = model.groups.map((g) => `
${g.label ? `<div class="ocrf-group-head"><span>${g.label}</span><span class="ocrf-group-count">${g.slots.filter((s) => s.required && s.state !== 'empty').length}/${g.slots.filter((s) => s.required).length}</span></div>` : ''}
<div class="ocrf-slot-grid" data-group="${g.side}">${g.slots.map((s) => slotTile(g.side, s)).join('')}</div>`).join('');
  const noticeHtml = notice ? `<p class="ocrf-s2-notice" id="ocrfS2Notice">${notice}</p>` : '';
  return `
<section class="screen" data-screen="s1">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">New read</h1></header>
  <div class="ocrf-scr-body">
    <div class="ocrf-type-tabs" role="group" aria-label="Screenshot type">${tabs}</div>
    ${noticeHtml}
    <div class="ocrf-summary"><span class="ocrf-pips">${pips}</span><span class="ocrf-fraction">${model.done}/${model.total}</span></div>
    ${groups}
  </div>
  <footer class="ocrf-scr-foot">
    <button type="button" class="ocrf-btn-primary ocrf-btn-block" id="ocrfScan"${model.canScan ? '' : ' disabled'}>Scan</button>
  </footer>
</section>`.trim();
}

export function wireUpload(root, { onTab, onSlot, onSlotRemove, onSlotNone, onScan }) {
  root.querySelectorAll('[data-type-tab]').forEach((b) => {
    b.addEventListener('click', () => onTab(b.dataset.typeTab));
  });
  root.querySelectorAll('[data-slot]').forEach((b) => {
    b.addEventListener('click', () => {
      const [side, key] = b.dataset.slot.split(':');
      onSlot(side, key, b.dataset.slotState);
    });
  });
  root.querySelectorAll('[data-slot-remove]').forEach((b) => {
    b.addEventListener('click', (e) => { e.stopPropagation(); const [side, key] = b.dataset.slotRemove.split(':'); onSlotRemove(side, key); });
  });
  root.querySelectorAll('[data-slot-none]').forEach((b) => {
    b.addEventListener('click', (e) => { e.stopPropagation(); const [side, key] = b.dataset.slotNone.split(':'); onSlotNone(side, key); });
  });
  const scan = root.querySelector('#ocrfScan');
  if (scan) scan.addEventListener('click', () => { if (!scan.disabled) onScan(); });
}

// Hand-drawn mini-panels: the img-error fallback for promoted bundles that
// strip the real-game sample crops (PRODUCTION_CRITERIA F1). Unchanged.
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

// ---- E1 (read problems) — minimal words, targets the combined screen -----
export function e1ActionHtml(cta) {
  if (cta === 'wait') {
    return '<button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s4" data-show-missing="1">Type instead</button>';
  }
  if (cta === 'upgrade') {
    return `<button type="button" class="ocrf-btn-primary ocrf-btn-block" id="ocrfE1Upgrade">See plans</button>
      <button type="button" class="ocrf-btn-ghost ocrf-btn-block" data-goto="s4" data-show-missing="1">Type instead</button>`;
  }
  if (cta === 'retake') {
    return `<button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s1" data-recovery="1">Retake</button>
      <button type="button" class="ocrf-btn-ghost ocrf-btn-block" data-goto="s4" data-show-missing="1">Type instead</button>`;
  }
  // retry_or_type (503 / network / unknown)
  return `<button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s3">Try again</button>
    <button type="button" class="ocrf-btn-ghost ocrf-btn-block" data-goto="s4" data-show-missing="1">Type instead</button>`;
}

export function renderE1(variant, opts = {}) {
  const mapped = opts.mapped || null;
  const heading = mapped ? mapped.heading
    : variant === 'partial' ? 'Some numbers missing'
      : 'Wrong screenshot';
  const body = mapped ? mapped.body
    : variant === 'partial' ? `We read ${opts.okCount ?? 0} of ${opts.total ?? 24}.`
      : 'That is not the stat panel.';
  const cta = mapped ? mapped.cta : (variant === 'partial' ? 'type_missing' : 'retake');
  const actions = cta === 'type_missing'
    ? `<button type="button" class="ocrf-btn-primary ocrf-btn-block" data-goto="s4" data-show-missing="1">Type the rest</button>
      <button type="button" class="ocrf-btn-ghost ocrf-btn-block" data-goto="s1" data-recovery="1">Retake</button>`
    : e1ActionHtml(cta);
  return `
<section class="screen" data-screen="e1">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">${heading}</h1></header>
  <div class="ocrf-scr-body">
    <div class="ocrf-err-icon" aria-hidden="true">&#9888;</div>
    <p class="ocrf-err-body">${body}</p>
    <div class="ocrf-e1-actions">${actions}</div>
  </div>
</section>`.trim();
}
