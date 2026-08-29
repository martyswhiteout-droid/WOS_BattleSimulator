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
// Owner 2026-08-30: tabs carry the full names — "Battle" alone read as vague.
export const TAB_LABEL = TYPE_LABEL;
export const YOU_TYPES = ['citystats', 'scout', 'battle'];
export const ENEMY_TYPES = ['scout', 'battle'];

const SAMPLE_IMG_BASE = '/shell/ocr/client/samples';

// One entry per named document slot. `max` = how many screenshots the slot
// takes (long lists scroll -> 2). `noneable` = the user may attest "None"
// instead of uploading (buffs). Battle is ONE group (the report carries both
// sides); scout/city repeat per side.
// `hint`/`hintEnemy` = the owner's dictated per-row instruction ("Upload the
// screenshot showing ...", 2026-08-30 — the terse locators "don't make
// sense" was his verdict). hintEnemy is used when the row renders in the
// Enemy card; hint is the You-side (and single-card) wording.
export const SLOTS = {
  battle: [
    { key: 'heroes', label: 'Heroes + Experts', required: true, max: 1, img: 'sample_battle_heroes.jpg',
      hint: 'Upload the screenshot showing heroes & experts' },
    { key: 'stats', label: 'Stats', required: true, max: 2, img: 'sample_battle_panel.jpg',
      hint: 'Upload the screenshot showing battle stats' },
    // QAC-016: the WHERE must name the popup behind the report's ! icon —
    // the in-game screen literally titled "Stat Bonuses" is the WRONG one
    // (D-043's exact trap). Short on purpose (QAC-012's word-tower).
    { key: 'buffs', label: 'Buffs', required: true, max: 2, img: 'sample_battle_popup.jpg', noneable: true,
      hint: 'Upload the special bonuses popup (!)',
      hintEnemy: "Upload the enemy's special bonuses popup (!)" },
    // img null (UXG-003): the Troop Power sample capture is still owed by the
    // owner — the drawn mini-panel stands in until the real capture ships.
    { key: 'power', label: 'Troops', required: false, max: 1, img: null, drawn: 'troops',
      hint: 'Upload the screenshot showing your troops',
      hintEnemy: "Upload the screenshot showing the enemy's troops" },
  ],
  scout: [
    { key: 'scout', label: 'Combat stats', required: true, max: 2, img: 'sample_scout.jpg',
      hint: 'Upload the scout report showing your combat stats',
      hintEnemy: "Upload the scout report showing the enemy's stats" },
  ],
  citystats: [
    { key: 'city', label: 'Bonus Overview', required: true, max: 2, img: 'sample_citystats.jpg',
      hint: 'Upload your City Stats screen',
      hintEnemy: "Upload the enemy's City Stats screen" },
  ],
};

// Which sides a type needs — every type is You + Enemy cards now.
// City is SYMMETRIC (owner 2026-08-30): the enemy's Bonus Overview comes
// from the other player, and the server accepts any side x panel.
// Battle scope (owner 2026-08-30): one report normally covers BOTH sides
// (the panel has My/Enemy columns), so the Enemy card defaults to a ticked
// "Same report as yours" toggle; unticking (enemySame=false) expands the
// enemy's own upload rows — for reading the OPPONENT's battle report, whose
// own My column is the enemy's stats (flow_state has modeled per-side
// battle uploads since Task 6).
function sideSlots(slots, side) {
  return slots.map((s) => (side === 'enemy' && s.hintEnemy ? { ...s, hint: s.hintEnemy } : s));
}
export function groupsFor(type, { enemySame = true } = {}) {
  if (type === 'battle') {
    return [
      { side: 'you', label: 'You', slots: SLOTS.battle },
      enemySame
        ? { side: 'enemy', label: 'Enemy', sameToggle: true, slots: [] }
        : { side: 'enemy', label: 'Enemy', sameToggle: true, slots: sideSlots(SLOTS.battle, 'enemy') },
    ];
  }
  const base = type === 'citystats' ? SLOTS.citystats : SLOTS.scout;
  return [
    { side: 'you', label: 'You', slots: sideSlots(base, 'you') },
    { side: 'enemy', label: 'Enemy', slots: sideSlots(base, 'enemy') },
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

export function uploadModel({ type, shots, attested = false, enemySame = true }) {
  // QAC-011: the None attestation is PER SIDE (mirror of the file store) —
  // a boolean still means "both sides" for back-compat and the same-report
  // default, an object keys by side.
  const att = (attested && typeof attested === 'object')
    ? attested : { you: !!attested, enemy: !!attested };
  const groups = groupsFor(type, { enemySame }).map((g) => ({
    ...g,
    slots: g.slots.map((def) => ({ ...def, ...slotState(def, shots[g.side] || [], att[g.side]) })),
  }));
  const required = groups.flatMap((g) => g.slots.filter((s) => s.required));
  const done = required.filter((s) => s.state !== 'empty').length;
  return { groups, done, total: required.length, canScan: done === required.length, enemySame };
}

// One requirement ROW (owner redesign round 2, 2026-08-29): sample crop on
// the left (recognition anchor — stays visible even after adding), name +
// in-game locator in the middle, action cluster on the right (+ Add chip ->
// per-shot thumbnail chips + remove x; Buffs adds the inline None chip).
// Rows read top-to-bottom at EVERY width — the 2-col tile grid died on
// desktop (ownership-by-proximity: the Enemy tile rendered under the You
// header; owner: "absolute non-sense").
function requirementRow(side, s) {
  // Owner 2026-08-30: the * cue is retired ("What does * mean?") — required
  // is the unmarked default; only "optional" earns a word. aria keeps saying
  // required for screen readers.
  const cue = s.required ? '' : ' <span class="ocrf-req-opt">optional</span>';
  const sample = s.img
    ? `<img class="ocrf-sample-img ocrf-req-sample" src="${SAMPLE_IMG_BASE}/${s.img}" alt="">`
    : (s.drawn ? renderSampleFallback(s.drawn) : '');
  // QAC-001: one x per thumbnail — removing one of two buffs never nukes
  // the other. QAC-004: + Add stays visible until the row hits its cap.
  // Chip count derives from s.count (never thumbUrls length): a shot whose
  // object-URL failed still gets its chip, tick, and its own remove x.
  const urls = s.thumbUrls || [];
  const thumbs = Array.from({ length: s.count }, (_, i) => (
    `<span class="ocrf-req-thumb"${urls[i] ? ` style="background-image:url('${urls[i]}')"` : ''}>`
    + '<span class="ocrf-req-tick" aria-hidden="true">&#10003;</span>'
    + `<button type="button" class="ocrf-req-thumb-x" data-slot-remove="${side}:${s.key}:${i}" aria-label="Remove">&times;</button></span>`
  )).join('');
  let cluster;
  if (s.state === 'added') {
    const more = s.count < s.max ? '<span class="ocrf-req-add" aria-hidden="true">+ Add</span>' : '';
    cluster = `${thumbs}${more}`;
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
      <span class="ocrf-req-name">${s.label}${cue}</span>
      <span class="ocrf-req-hint" data-hint="${s.hint}" aria-live="polite">${s.hint}</span>
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
    const count = g.sameToggle && model.enemySame ? ''
      : `<span class="ocrf-req-card-count">${req.filter((s) => s.state !== 'empty').length}/${req.length}</span>`;
    const head = g.label
      ? `<div class="ocrf-req-card-head"><span>${g.label}</span>${count}</div>`
      : '';
    // Battle's Enemy card: a ticked "Same report as yours" checkbox row.
    // Unticking expands the enemy's own upload rows below it.
    const same = g.sameToggle
      ? `<button type="button" class="ocrf-req-same${model.enemySame ? ' ocrf-req-same--on' : ''}"
          data-same-toggle aria-pressed="${model.enemySame}">
          <span class="ocrf-req-same-box" aria-hidden="true">${model.enemySame ? '&#10003;' : ''}</span>
          Same report as yours</button>`
      : '';
    return `<section class="ocrf-req-card" data-group="${g.side}">${head}${same}${g.slots.map((s) => requirementRow(g.side, s)).join('')}</section>`;
  }).join('');
  const noticeHtml = notice ? `<p class="ocrf-s2-notice" id="ocrfS2Notice">${notice}</p>` : '';
  // The fraction lives INSIDE the locked Scan button — the "why is this
  // disabled" answer sits exactly where the eye lands. No pips, no strip.
  const scanLabel = model.canScan ? 'Scan'
    : `Scan <span class="ocrf-scan-count">${model.done}/${model.total}</span>`;
  return `
<section class="screen" data-screen="s1">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">Screenshots</h1></header>
  <div class="ocrf-scr-body ocrf-upload-body">
    <p class="ocrf-upload-intro">Choose the type of screenshot to upload</p>
    <div class="ocrf-type-tabs" role="group" aria-label="Screenshot type">${tabs}</div>
    ${noticeHtml}
    <div class="ocrf-req-cards">${cards}</div>
  </div>
  <footer class="ocrf-scr-foot">
    <button type="button" class="ocrf-btn-primary ocrf-btn-block" id="ocrfScan"${model.canScan ? '' : ' disabled'}>${scanLabel}</button>
  </footer>
</section>`.trim();
}

export function wireUpload(root, { onTab, onSlot, onSlotRemove, onSlotNone, onScan, onSameToggle }) {
  root.querySelectorAll('[data-type-tab]').forEach((b) => {
    b.addEventListener('click', () => onTab(b.dataset.typeTab));
  });
  const same = root.querySelector('[data-same-toggle]');
  if (same && onSameToggle) same.addEventListener('click', () => onSameToggle());
  root.querySelectorAll('[data-slot]').forEach((b) => {
    b.addEventListener('click', () => {
      const [side, key] = b.dataset.slot.split(':');
      onSlot(side, key, b.dataset.slotState);
    });
  });
  root.querySelectorAll('[data-slot-remove]').forEach((b) => {
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      const [side, key, idx] = b.dataset.slotRemove.split(':');
      onSlotRemove(side, key, idx === undefined ? null : parseInt(idx, 10));
    });
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
  troops: [
    { label: 'Infantry', val: 'T11' },
    { label: 'Lancer', val: 'T11' },
    { label: 'Marksman', val: 'T11' },
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
  if (type === 'troops') {
    // Hand-drawn stand-in for the Troops (troop details) row — the real
    // capture is still owed by the owner; a drawn representation beats both
    // an empty box and a fabricated screenshot.
    const rows = SAMPLES.troops.map((r) => (
      `<div class="ocrf-mp-c-row"><span class="ocrf-mp-c-lab">${r.label}</span><span class="ocrf-mp-c-val">${r.val}</span></div>`
    )).join('');
    return `<div class="ocrf-mini-panel ocrf-mini-panel--troops"><div class="ocrf-mp-c-head">Troops</div>${rows}</div>`;
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
