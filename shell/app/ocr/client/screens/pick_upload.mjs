// screens/pick_upload.mjs — the Upload screen: TWO cards on one screen
// (owner 2026-09-06, designer spec) — "Upload screenshots of your ..." and
// "... the enemy's ...", each with its own type selector, requirement rows
// (sample | name + instruction | + Add / thumbnails), an L/R column pill on
// battle cards, and the enemy's "Use your report for the enemy too" box.
// History: slot grid (08-29) -> requirement rows -> scope pills -> this.
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
    // Owner 2026-08-30 #2: bracket structure per dictation — "all buffs
    // (special bonuses)". Still names the POPUP's real title, never the
    // main panel's "Stat Bonuses" (D-043's trap); the "(!)" glyph is gone
    // ("the bracket is showing" — it read as broken markup).
    { key: 'buffs', label: 'Buffs', required: true, max: 2, img: 'sample_battle_popup.jpg', noneable: true,
      hint: 'Upload the screenshot showing all buffs (special bonuses)' },
    // Owner capture 2026-09-06: the real Troop Power Comparison screen; the
    // drawn mini-panel stays as the img-error fallback (promoted bundles
    // strip game art). Hint is SIDE-NEUTRAL: the card owns "whose".
    { key: 'power', label: 'Troops', required: false, max: 1, img: 'sample_troop_power.jpg', drawn: 'troops',
      hint: 'Upload the screenshot showing troop quality, ratio, FC tier' },
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

// ---- Two cards, one screen (owner 2026-09-06; designer spec) ------------
// Every read has YOUR report card and the ENEMY's report card. Each card
// chooses its own screenshot type (mixed types allowed), battle cards carry
// an L/R pill ("which column of this report holds this side's stats"), and
// the enemy card can defer to your battle report ("Use your report for the
// enemy too" — its stats are then the OTHER column of your report, its rows
// are hidden and its shots parked). Data flows: type -> flow.setSideType;
// column -> controller postSideFor (the posted side hint); sameReport ->
// no enemy upload, coverage from your read (deriveViews).
export const TYPES = ['battle', 'scout', 'citystats'];
export const COLUMNS = ['L', 'R'];
export const DEFAULT_COLUMNS = { you: 'L', enemy: 'R' };
const TITLE_NOUN = { battle: 'battle report', scout: 'scout report', citystats: 'City Stats' };
export function cardTitle(side, type) {
  const owner = side === 'you' ? 'your' : "the enemy's";
  return `Upload screenshots of ${owner} ${TITLE_NOUN[type]}`;
}
function sideSlots(slots, side) {
  return slots.map((s) => (side === 'enemy' && s.hintEnemy ? { ...s, hint: s.hintEnemy } : s));
}
export function otherColumn(col) { return col === 'L' ? 'R' : 'L'; }

// Pure card descriptors (no shot state yet).
export function cardsFor({ types, columns = DEFAULT_COLUMNS, sameReport = false }) {
  const bothBattle = types.you === 'battle' && types.enemy === 'battle';
  const sameActive = bothBattle && !!sameReport;
  const you = {
    side: 'you', type: types.you, label: cardTitle('you', types.you),
    slots: sideSlots(SLOTS[types.you], 'you'),
    showCol: types.you === 'battle', column: columns.you || 'L', colLocked: false,
    showSame: false, sameActive: false, rowsHidden: false,
  };
  const enemy = {
    side: 'enemy', type: types.enemy, label: cardTitle('enemy', types.enemy),
    slots: sideSlots(SLOTS[types.enemy], 'enemy'),
    showCol: types.enemy === 'battle',
    // With the box on the enemy's column is DERIVED: the other column of
    // your report. Never stored, never user-editable while locked.
    column: sameActive ? otherColumn(columns.you || 'L') : (columns.enemy || 'R'),
    colLocked: sameActive,
    showSame: bothBattle, sameActive, rowsHidden: sameActive,
  };
  return [you, enemy];
}

// Pure per-slot state. shots = [{id, slot}] for ONE side; attested = the
// buffs "None" attestation flag.
export function slotState(slotDef, sideShots, attested) {
  const count = sideShots.filter((s) => s.slot === slotDef.key).length;
  if (count > 0) return { state: 'added', count };
  if (slotDef.noneable && attested) return { state: 'none', count: 0 };
  return { state: 'empty', count: 0 };
}

export function uploadModel({ types, shots, attested = false, columns = DEFAULT_COLUMNS, sameReport = false }) {
  // QAC-011: the None attestation is PER SIDE (mirror of the file store) —
  // a boolean still means "both sides", an object keys by side.
  const att = (attested && typeof attested === 'object')
    ? attested : { you: !!attested, enemy: !!attested };
  const cards = cardsFor({ types, columns, sameReport }).map((c) => ({
    ...c,
    slots: c.slots.map((def) => ({ ...def, ...slotState(def, shots[c.side] || [], att[c.side]) })),
  }));
  const active = cards.filter((c) => !c.rowsHidden);
  const required = active.flatMap((c) => c.slots.filter((s) => s.required));
  const done = required.filter((s) => s.state !== 'empty').length;
  const model = { cards, done, total: required.length, canScan: done === required.length, sameReport, types, columns };
  model.missing = missingList(model);
  model.touched = cards.some((c) => c.slots.some((s) => s.state !== 'empty'));
  return model;
}

// Owner 2026-09-06: "there should be a prompt that says you're missing
// something" — specific items in card order: a card with NOTHING done ->
// its noun ("enemy's scout report"); a partly done card -> one item per
// empty required row ("your Buffs"). Troops never counts; a card hidden
// behind the same-report box is skipped. Pure; exported for tests.
export function missingList(model) {
  const out = [];
  for (const c of model.cards) {
    if (c.rowsHidden) continue;
    const req = c.slots.filter((s) => s.required);
    const empty = req.filter((s) => s.state === 'empty');
    if (!empty.length) continue;
    const owner = c.side === 'you' ? 'your' : "enemy's";
    if (empty.length === req.length) out.push(`${owner} ${TITLE_NOUN[c.type]}`);
    else out.push(...empty.map((s) => `${owner} ${s.label}`));
  }
  return out;
}

// One requirement ROW: sample crop left (recognition anchor — stays after
// adding; on battle rows a half-wash shows which COLUMN gets read), name +
// instruction line, action cluster right. "+ Add" is the ONLY picker
// trigger (owner 2026-09-06); the words are inert; each thumbnail is a
// button that opens its preview sheet (Replace / Remove).
function requirementRow(card, s) {
  const side = card.side;
  const ariaPrefix = `${side === 'you' ? 'Your' : "Enemy's"} ${TITLE_NOUN[card.type]}: `;
  const cue = s.required ? '' : ' <span class="ocrf-req-opt">optional</span>';
  const sample = s.img
    ? `<img class="ocrf-sample-img ocrf-req-sample" src="${SAMPLE_IMG_BASE}/${s.img}" alt="">`
    : (s.drawn ? renderSampleFallback(s.drawn) : '');
  const wash = card.showCol ? ` ocrf-req-fig--${card.column} ocrf-req-fig--${side}` : '';
  const urls = s.thumbUrls || [];
  const thumbs = Array.from({ length: s.count }, (_, i) => (
    `<span class="ocrf-req-thumb"${urls[i] ? ` style="background-image:url('${urls[i]}')"` : ''}>`
    + `<button type="button" class="ocrf-req-thumb-open" data-slot-preview="${side}:${s.key}" aria-label="Preview ${s.label} screenshot ${i + 1} of ${s.count}"></button>`
    + '<span class="ocrf-req-tick" aria-hidden="true">&#10003;</span>'
    + `<button type="button" class="ocrf-req-thumb-x" data-slot-remove="${side}:${s.key}:${i}" aria-label="Remove">&times;</button></span>`
  )).join('');
  const addBtn = s.count < s.max
    ? `<button type="button" class="ocrf-req-add" data-slot="${side}:${s.key}" data-slot-state="${s.state}" aria-label="Add ${s.label}">+ Add</button>`
    : '';
  let cluster;
  if (s.state === 'added') {
    cluster = `${thumbs}${addBtn}`;
  } else if (s.state === 'none') {
    cluster = `<button type="button" class="ocrf-req-none ocrf-req-none--on" data-slot-none="${side}:${s.key}" aria-pressed="true">None <span aria-hidden="true">&#10003;</span></button>${addBtn}`;
  } else {
    const noneChip = s.noneable
      ? `<button type="button" class="ocrf-req-none" data-slot-none="${side}:${s.key}" aria-pressed="false">None</button>`
      : '';
    cluster = `${noneChip}${addBtn}`;
  }
  const stateLabel = s.state === 'added' ? `${s.count} added` : s.state === 'none' ? 'none' : (s.required ? 'required' : 'optional');
  return `
<div class="ocrf-req ocrf-req--${s.state}" data-slot-tile="${side}:${s.key}" role="group"
  aria-label="${ariaPrefix}${s.label}, ${stateLabel}">
  <div class="ocrf-req-main">
    <span class="ocrf-req-fig${wash}"${s.drawn ? ` data-drawn="${s.drawn}"` : ''}>${sample}</span>
    <span class="ocrf-req-text">
      <span class="ocrf-req-name">${s.label}${cue}</span>
      <span class="ocrf-req-hint" data-hint="${s.hint}" aria-live="polite">${s.hint}</span>
    </span>
  </div>
  <span class="ocrf-req-cluster">${cluster}</span>
</div>`;
}

function typeSelector(card) {
  const owner = card.side === 'you' ? 'Your' : "Enemy's";
  return `<div class="ocrf-type-tabs ocrf-card-types" role="radiogroup" aria-label="${owner} report type">${TYPES.map((t) => (
    `<button type="button" role="radio" class="ocrf-type-tab${t === card.type ? ' ocrf-type-tab--on' : ''}"
      data-type="${card.side}:${t}" aria-checked="${t === card.type}">${TYPE_LABEL[t]}</button>`
  )).join('')}</div>`;
}

function columnPill(card) {
  const who = card.side === 'you' ? 'Your' : "Enemy's";
  const seg = (col) => (
    `<button type="button" role="radio" class="ocrf-col-seg${col === card.column ? ' ocrf-col-seg--on' : ''}"
      data-col="${card.side}:${col}" aria-checked="${col === card.column}"
      aria-label="${col === 'L' ? 'Left' : 'Right'} column"${card.colLocked ? ' aria-disabled="true" title="Set by your report"' : ''}>${col}</button>`
  );
  return `<div class="ocrf-col ocrf-col--${card.side}${card.colLocked ? ' ocrf-col--locked' : ''}" role="radiogroup"
    aria-label="${who} stats column">${who} stats are in the <span class="ocrf-col-pill">${seg('L')}${seg('R')}</span> column</div>`;
}

function cardHtml(card) {
  const req = card.slots.filter((s) => s.required);
  const count = card.rowsHidden ? ''
    : `<span class="ocrf-req-card-count">${req.filter((s) => s.state !== 'empty').length}/${req.length}</span>`;
  const same = card.showSame
    ? `<button type="button" class="ocrf-req-same${card.sameActive ? ' ocrf-req-same--on' : ''}" role="checkbox"
        data-same aria-checked="${card.sameActive}">
        <span class="ocrf-req-same-box" aria-hidden="true">${card.sameActive ? '&#10003;' : ''}</span>
        Use your report for the enemy too</button>`
    : '';
  const rows = card.rowsHidden ? '' : card.slots.map((s) => requirementRow(card, s)).join('');
  return `<section class="ocrf-req-card ocrf-req-card--${card.side}" data-group="${card.side}">
    <div class="ocrf-req-card-head"><span class="ocrf-req-card-title">${card.label}</span>${count}</div>
    ${typeSelector(card)}
    ${same}
    ${card.showCol ? columnPill(card) : ''}
    ${rows}
  </section>`;
}

export function renderUpload({ model, notice = null, showMissing = false }) {
  const cards = model.cards.map(cardHtml).join('');
  const noticeHtml = notice ? `<p class="ocrf-s2-notice" id="ocrfS2Notice">${notice}</p>` : '';
  // The fraction lives INSIDE the locked Scan button; the missing line is
  // the next action (owner: "a prompt that says you're missing something").
  // Scan is aria-disabled (not disabled) so a tap on it can reveal the line.
  const scanLabel = model.canScan ? 'Scan'
    : `Scan <span class="ocrf-scan-count">${model.done}/${model.total}</span>`;
  const missing = !model.canScan && (showMissing || model.touched) && model.missing.length
    ? `<button type="button" class="ocrf-missing" data-missing-jump aria-live="polite"><b>Missing:</b> ${model.missing.join(', ')}</button>`
    : '';
  return `
<section class="screen" data-screen="s1">
  <header class="ocrf-scr-head"><button type="button" class="ocrf-back-btn" data-back aria-label="Back">&#8249;</button>
    <h1 tabindex="-1">Screenshots</h1></header>
  <div class="ocrf-scr-body ocrf-upload-body">
    ${noticeHtml}
    <div class="ocrf-req-cards ocrf-req-cards--two">${cards}</div>
  </div>
  <footer class="ocrf-scr-foot">
    ${missing}
    <button type="button" class="ocrf-btn-primary ocrf-btn-block" id="ocrfScan"${model.canScan ? '' : ' aria-disabled="true"'}>${scanLabel}</button>
  </footer>
</section>`.trim();
}

export function wireUpload(root, { onType, onCol, onSame, onSlot, onSlotRemove, onSlotNone, onSlotPreview, onScan, onMissingJump }) {
  root.querySelectorAll('[data-type]').forEach((b) => {
    b.addEventListener('click', () => { const [side, type] = b.dataset.type.split(':'); if (onType) onType(side, type); });
  });
  root.querySelectorAll('[data-col]').forEach((b) => {
    b.addEventListener('click', () => { const [side, col] = b.dataset.col.split(':'); if (onCol) onCol(side, col, b.getAttribute('aria-disabled') === 'true'); });
  });
  const same = root.querySelector('[data-same]');
  if (same && onSame) same.addEventListener('click', () => onSame());
  root.querySelectorAll('[data-slot-preview]').forEach((b) => {
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      const [side, key] = b.dataset.slotPreview.split(':');
      if (onSlotPreview) onSlotPreview(side, key);
    });
  });
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
  const jump = root.querySelector('[data-missing-jump]');
  if (jump && onMissingJump) jump.addEventListener('click', () => onMissingJump());
  const scan = root.querySelector('#ocrfScan');
  if (scan) scan.addEventListener('click', () => onScan(scan.getAttribute('aria-disabled') === 'true'));
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
