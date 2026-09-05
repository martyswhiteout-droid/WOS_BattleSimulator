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

// Which sides a type needs.
// City is SYMMETRIC (owner 2026-08-30): the enemy's Bonus Overview comes
// from the other player, and the server accepts any side x panel.
// BATTLE SCOPE (owner 2026-08-30 #2, replacing the You/Enemy cards +
// "Same report as yours" checkbox — "What's you? What's enemy? What does
// the check box do?"): the user answers the question they actually think
// in — "Whose battle report?" — via a segmented control ABOVE the rows:
//   mine  -> 4 rows, side 'you'   (default; a report shows both sides)
//   enemy -> 4 rows, side 'enemy' (the OPPONENT's report; service.py's
//            side swap maps its My column to stats_enemy)
//   both  -> two labeled groups, "Your report" / "Enemy's report"
// Every scope yields a full read (each report carries both columns).
export const BATTLE_SCOPES = ['mine', 'enemy', 'both'];
export const SCOPE_LABEL = { mine: 'Mine', enemy: "Enemy's", both: 'Both' };
function sideSlots(slots, side) {
  return slots.map((s) => (side === 'enemy' && s.hintEnemy ? { ...s, hint: s.hintEnemy } : s));
}
export function groupsFor(type, { scope = 'mine' } = {}) {
  if (type === 'battle') {
    if (scope === 'enemy') return [{ side: 'enemy', label: null, slots: SLOTS.battle }];
    if (scope === 'both') {
      return [
        { side: 'you', label: 'Your report', slots: SLOTS.battle },
        { side: 'enemy', label: "Enemy's report", slots: SLOTS.battle },
      ];
    }
    return [{ side: 'you', label: null, slots: SLOTS.battle }];
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

export function uploadModel({ type, shots, attested = false, scope = 'mine' }) {
  // QAC-011: the None attestation is PER SIDE (mirror of the file store) —
  // a boolean still means "both sides" for back-compat and the one-report
  // scopes, an object keys by side.
  const att = (attested && typeof attested === 'object')
    ? attested : { you: !!attested, enemy: !!attested };
  const groups = groupsFor(type, { scope }).map((g) => ({
    ...g,
    slots: g.slots.map((def) => ({ ...def, ...slotState(def, shots[g.side] || [], att[g.side]) })),
  }));
  const required = groups.flatMap((g) => g.slots.filter((s) => s.required));
  const done = required.filter((s) => s.state !== 'empty').length;
  return { groups, done, total: required.length, canScan: done === required.length, scope };
}

// Owner 2026-09-06: "there should be a prompt that says you're missing
// something" — the specific required rows still empty, grouped by card, as
// short strings for the missing line above Scan. Pure; exported for tests.
export function missingList(model) {
  const out = [];
  for (const g of model.groups) {
    const names = g.slots.filter((s) => s.required && s.state === 'empty').map((s) => s.label);
    if (!names.length) continue;
    out.push(g.label ? `${g.label}: ${names.join(', ')}` : names.join(', '));
  }
  return out;
}

// One requirement ROW (owner redesign round 2, 2026-08-29): sample crop on
// the left (recognition anchor — stays visible even after adding), name +
// in-game locator in the middle, action cluster on the right (+ Add chip ->
// per-shot thumbnail chips + remove x; Buffs adds the inline None chip).
// Rows read top-to-bottom at EVERY width — the 2-col tile grid died on
// desktop (ownership-by-proximity: the Enemy tile rendered under the You
// header; owner: "absolute non-sense").
function requirementRow(side, s, ariaPrefix = '') {
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
  // Owner 2026-09-06: "+ Add" IS the trigger (it used to be decorative
  // while the row's words opened the picker — "not intuitive"). The words
  // are inert now; each thumbnail is a button that opens its preview sheet
  // (Replace / Remove). The + Add button stays while the row has room,
  // including the attested "None" state (a real upload overrides None).
  const urls = s.thumbUrls || [];
  const thumbs = Array.from({ length: s.count }, (_, i) => (
    `<span class="ocrf-req-thumb"${urls[i] ? ` style="background-image:url('${urls[i]}')"` : ''}>`
    + `<button type="button" class="ocrf-req-thumb-open" data-slot-preview="${side}:${s.key}" aria-label="View screenshot ${i + 1}"></button>`
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
    <span class="ocrf-req-fig"${s.drawn ? ` data-drawn="${s.drawn}"` : ''}>${sample}</span>
    <span class="ocrf-req-text">
      <span class="ocrf-req-name">${s.label}${cue}</span>
      <span class="ocrf-req-hint" data-hint="${s.hint}" aria-live="polite">${s.hint}</span>
    </span>
  </div>
  <span class="ocrf-req-cluster">${cluster}</span>
</div>`;
}

export function renderUpload({ type, model, notice = null }) {
  const tabs = ['battle', 'scout', 'citystats'].map((t) => (
    `<button type="button" class="ocrf-type-tab${t === type ? ' ocrf-type-tab--on' : ''}"
      data-type-tab="${t}" aria-pressed="${t === type}">${TAB_LABEL[t]}</button>`
  )).join('');
  // Battle only: the scope question sits ABOVE the rows, always visible —
  // segmented Mine / Enemy's / Both plus one reassurance line that kills
  // the coverage doubt. (Owner 2026-08-30 #2; the checkbox is dead.)
  const scopeBar = type === 'battle'
    ? `<div class="ocrf-scope">
    <span class="ocrf-scope-q" id="ocrfScopeQ">Whose battle report?</span>
    <div class="ocrf-scope-tabs" role="radiogroup" aria-labelledby="ocrfScopeQ">${BATTLE_SCOPES.map((sc) => (
      `<button type="button" role="radio" class="ocrf-scope-tab${sc === model.scope ? ' ocrf-scope-tab--on' : ''}"
        data-scope="${sc}" aria-checked="${sc === model.scope}">${SCOPE_LABEL[sc]}</button>`
    )).join('')}</div>
    <span class="ocrf-scope-note">Each report shows both sides.</span>
  </div>`
    : '';
  const cards = model.groups.map((g) => {
    const req = g.slots.filter((s) => s.required);
    const head = g.label
      ? `<div class="ocrf-req-card-head"><span>${g.label}</span>`
        + `<span class="ocrf-req-card-count">${req.filter((s) => s.state !== 'empty').length}/${req.length}</span></div>`
      : '';
    // QAC-018: labeled cards prefix their name into each row's aria-label
    // so non-visual users can tell whose row is whose under "Both".
    const prefix = g.label ? `${g.label}: ` : '';
    return `<section class="ocrf-req-card" data-group="${g.side}">${head}${g.slots.map((s) => requirementRow(g.side, s, prefix)).join('')}</section>`;
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
    ${scopeBar}
    <div class="ocrf-req-cards${model.groups.length > 1 ? ' ocrf-req-cards--two' : ''}">${cards}</div>
  </div>
  <footer class="ocrf-scr-foot">
    <button type="button" class="ocrf-btn-primary ocrf-btn-block" id="ocrfScan"${model.canScan ? '' : ' disabled'}>${scanLabel}</button>
  </footer>
</section>`.trim();
}

export function wireUpload(root, { onTab, onSlot, onSlotRemove, onSlotNone, onScan, onScope, onSlotPreview }) {
  root.querySelectorAll('[data-slot-preview]').forEach((b) => {
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      const [side, key] = b.dataset.slotPreview.split(':');
      if (onSlotPreview) onSlotPreview(side, key);
    });
  });
  root.querySelectorAll('[data-type-tab]').forEach((b) => {
    b.addEventListener('click', () => onTab(b.dataset.typeTab));
  });
  root.querySelectorAll('[data-scope]').forEach((b) => {
    b.addEventListener('click', () => { if (onScope) onScope(b.dataset.scope); });
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
