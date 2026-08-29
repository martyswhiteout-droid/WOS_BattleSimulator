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
// `hint` = a <=4-word in-game locator ("what do I screenshot?") — the one
// piece of information the owner's crystal-clear mandate demands per row.
export const SLOTS = {
  battle: [
    { key: 'heroes', label: 'Heroes', required: true, max: 1, img: 'sample_battle_heroes.jpg', hint: 'Report · hero rows' },
    { key: 'stats', label: 'Stats', required: true, max: 2, img: 'sample_battle_panel.jpg', hint: 'Report · stat rows' },
    { key: 'buffs', label: 'Buffs', required: true, max: 2, img: 'sample_battle_popup.jpg', noneable: true, hint: '! popup · up to 2' },
    // img null (UXG-003): the Troop Power sample capture is still owed by the
    // owner — no img element until it ships (a 404 per open is worse than the
    // dashed tile the img-error fallback would leave anyway).
    { key: 'power', label: 'Power', required: false, max: 1, img: null, hint: 'Troop details screen' },
  ],
  scout: [
    { key: 'scout', label: 'Stats', required: true, max: 2, img: 'sample_scout.jpg', hint: 'Scout report' },
  ],
  citystats: [
    { key: 'city', label: 'City', required: true, max: 2, img: 'sample_citystats.jpg', hint: 'Bonus Overview' },
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

// One requirement ROW (owner redesign round 2, 2026-08-29): sample crop on
// the left (recognition anchor — stays visible even after adding), name +
// in-game locator in the middle, action cluster on the right (+ Add chip ->
// per-shot thumbnail chips + remove x; Buffs adds the inline None chip).
// Rows read top-to-bottom at EVERY width — the 2-col tile grid died on
// desktop (ownership-by-proximity: the Enemy tile rendered under the You
// header; owner: "absolute non-sense").
function requirementRow(side, s) {
  const cue = s.required
    ? '<span class="ocrf-req-star" aria-label="required">*</span>'
    : '<span class="ocrf-req-opt">optional</span>';
  const sample = s.img
    ? `<img class="ocrf-sample-img ocrf-req-sample" src="${SAMPLE_IMG_BASE}/${s.img}" alt="">`
    : '';
  const thumbs = (s.thumbUrls || []).map((u) => (
    `<span class="ocrf-req-thumb"${u ? ` style="background-image:url('${u}')"` : ''}>`
    + '<span class="ocrf-req-tick" aria-hidden="true">&#10003;</span></span>'
  )).join('');
  let cluster;
  if (s.state === 'added') {
    cluster = `${thumbs}<button type="button" class="ocrf-req-x" data-slot-remove="${side}:${s.key}" aria-label="Remove">&times;</button>`;
  } else if (s.state === 'none') {
    cluster = `<button type="button" class="ocrf-req-none ocrf-req-none--on" data-slot-none="${side}:${s.key}" aria-pressed="true">None <span aria-hidden="true">&#10003;</span></button>`;
  } else {
    const noneChip = s.noneable
      ? `<button type="button" class="ocrf-req-none" data-slot-none="${side}:${s.key}" aria-pressed="false">None</button>`
      : '';
    cluster = `${noneChip}<span class="ocrf-req-add" aria-hidden="true">+ Add</span>`;
  }
  const stateLabel = s.state === 'added' ? `${s.count} added` : s.state === 'none' ? 'none' : (s.required ? 'required' : 'optional');
  return `
<div class="ocrf-req ocrf-req--${s.state}" data-slot-tile="${side}:${s.key}">
  <button type="button" class="ocrf-req-main" data-slot="${side}:${s.key}" data-slot-state="${s.state}"
    aria-label="${s.label}, ${stateLabel}">
    <span class="ocrf-req-fig">${sample}</span>
    <span class="ocrf-req-text">
      <span class="ocrf-req-name">${s.label} ${cue}</span>
      <span class="ocrf-req-hint">${s.hint}</span>
    </span>
  </button>
  <span class="ocrf-req-cluster">${cluster}</span>
</div>`;
}

export function renderUpload({ type, model, notice = null }) {
  const tabs = ['battle', 'scout', 'citystats'].map((t) => (
    `<button type="button" class="ocrf-type-tab${t === type ? ' ocrf-type-tab--on' : ''}"
      data-type-tab="${t}" aria-pressed="${t === type}">${TAB_LABEL[t]}</button>`
  )).join('');
  const cards = model.groups.map((g) => {
    const req = g.slots.filter((s) => s.required);
    const head = g.label
      ? `<div class="ocrf-req-card-head"><span>${g.label}</span>`
        + `<span class="ocrf-req-card-count">${req.filter((s) => s.state !== 'empty').length}/${req.length}</span></div>`
      : '';
    return `<section class="ocrf-req-card" data-group="${g.side}">${head}${g.slots.map((s) => requirementRow(g.side, s)).join('')}</section>`;
  }).join('');
  const noticeHtml = notice ? `<p class="ocrf-s2-notice" id="ocrfS2Notice">${notice}</p>` : '';
  // The fraction lives INSIDE the locked Scan button — the "why is this
  // disabled" answer sits exactly where the eye lands. No pips, no strip.
  const scanLabel = model.canScan ? 'Scan'
    : `Scan <span class="ocrf-scan-count">${model.done}/${model.total}</span>`;
  return `
<section class="screen" data-screen="s1">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">New read</h1></header>
  <div class="ocrf-scr-body ocrf-upload-body">
    <div class="ocrf-type-tabs" role="group" aria-label="Screenshot type">${tabs}</div>
    ${noticeHtml}
    ${cards}
  </div>
  <footer class="ocrf-scr-foot">
    <button type="button" class="ocrf-btn-primary ocrf-btn-block" id="ocrfScan"${model.canScan ? '' : ' disabled'}>${scanLabel}</button>
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
