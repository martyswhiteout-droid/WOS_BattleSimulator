// shell/app/ocr/client/ocr_flow.js — FINAL bootstrap (Task 10 Part A).
//
// Every decision this file makes was already built and tested by Tasks 1-9;
// this is pure assembly (a navigation stack mirroring the mock's own proven
// goto/back/show pattern, and the read -> convert -> classify -> render
// pipeline). SERVER-ONLY v1 (COORDINATOR RULING 2026-08-10 #1): no client
// OCR engine import, no PREP screen/step — see controller.mjs and
// screens/reading.mjs for the rationale. onDropzone/onTypeTag (left as
// commented stubs in the plan's draft) are wired here to real DOM mechanics;
// they carry no decision logic of their own (every actual decision — which
// type is valid for a side, whether a type change confirms, what the
// dropzone should say — was already built and tested in Task 6).
import { mountEntry, wireEntry, renderUpgradeNote, wireUpgradeNote } from './screens/entry.mjs';
import {
  renderS1, renderS2, renderE1, wireS1, wireS2, wireE1,
  YOU_TYPES, ENEMY_TYPES, TYPE_LABEL,
} from './screens/pick_upload.mjs';
import { renderS3, driveScan, applyStepClasses, wireS3 } from './screens/reading.mjs';
import {
  renderS4, renderEditorSheet, renderPictureView, fieldRenderState, computeTally,
  validateEditorInput, editorContentFor, nextResetState, wireS4,
} from './screens/review.mjs';
import { renderS5, computeChipText, shouldShowUndo, buildFillPlan, applyFillPlan, wireS5 } from './screens/setup.mjs';
import { createController } from './controller.mjs';
import { classifyFields, ALL_FIELD_KEYS, buildSnapshot, fieldEngineForSide } from './fill_mapper.mjs';

function fetchMe() { return fetch('/shell/me', { credentials: 'same-origin' }).then((r) => r.json()); }
async function checkAccess() {
  try {
    const me = await fetchMe();
    const plan = me?.user?.plan;
    return { allowed: plan === 'pro', plan: plan ?? null, reachable: true, userId: me?.user?.user_id ?? null };
  } catch { return { allowed: false, plan: null, reachable: false, userId: null }; }
}
function postPanel({ shotBytesList, side, panelType }) {
  const form = new FormData();
  for (const bytes of shotBytesList) form.append('file', new Blob([bytes], { type: 'image/png' }), 'shot.png');
  form.append('side', side);
  if (panelType) form.append('panel', panelType);
  return fetch('/shell/ocr/panel', { method: 'POST', body: form, credentials: 'same-origin' }).then(async (r) => {
    if (r.ok) return r.json();
    const err = new Error('panel upload failed'); err.status = r.status; err.body = await r.json().catch(() => null);
    throw err;
  });
}

// No recognizeImage: SERVER-ONLY v1 (COORDINATOR RULING 2026-08-10 #1) — every
// read goes straight to /shell/ocr/panel's production ladder, nothing client-
// side to inject here (engine_tesseract.mjs stays the future client tier).
const controller = createController({ fetchMe, postPanel, storage: window.localStorage });

const app = { history: ['entry'], screen: 'entry',
  shots: { you: [], enemy: [] },            // [{id, bytes: Uint8Array}]
  savedValues: { you: {}, enemy: {} }, typedFields: { you: {}, enemy: {} },
  lastRead: null, priorSnapshot: null, resetTimer: null };

function root() { return document.getElementById('ocrfRoot'); }

// Set once by boot() — the S0 CTA card, hidden while the flow is open and
// restored on Back-to-entry (the [hidden] show/hide pattern, per the global
// constraints; the entry card is not itself part of the #ocrfRoot stack).
let entryNode = null;

function show(html) {
  root().innerHTML = html;
  const heading = root().querySelector('h1, h2[tabindex]');
  if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus({ preventScroll: true }); }
  // Every screen template's header carries the same data-back control
  // (S3/S5 render none — optional chaining is the no-op there).
  root().querySelector('[data-back]')?.addEventListener('click', back);
}

function goto(screen, { push = true } = {}) {
  if (app.resetTimer) { clearTimeout(app.resetTimer); app.resetTimer = null; }
  if (push) app.history.push(screen); else app.history[app.history.length - 1] = screen;
  app.screen = screen;
  render();
}
function back() {
  if (app.history.length > 1) { app.history.pop(); app.screen = app.history[app.history.length - 1]; render(); }
}

function fieldStatesFor(side) {
  const result = app.lastRead?.results?.[side];
  const classification = classifyFields({
    expectedKeys: ALL_FIELD_KEYS,
    stats: result?.panel_type === 'battle' ? (side === 'you' ? result.stats_you : result.stats_enemy) ?? {} : result?.stats ?? {},
    fieldConf: result?.panel_type === 'battle' ? (side === 'you' ? result.stats_you_conf : result.stats_enemy_conf) ?? {} : result?.field_conf ?? {},
    // COORDINATOR RULING 2026-08-10 #2: tier comes from the server's own
    // field_engine contract (Gemini gap-fills), translated to the bare-keyed,
    // per-side shape classifyFields expects.
    fieldEngine: result ? fieldEngineForSide(result, side) : {},
  });
  const out = {};
  for (const key of ALL_FIELD_KEYS) {
    out[key] = fieldRenderState({ classification: classification[key], savedValue: app.savedValues[side][key] });
  }
  return out;
}
function allFieldStates() { return { you: fieldStatesFor('you'), enemy: fieldStatesFor('enemy') }; }
function flatTallyStates(states) {
  return [...Object.values(states.you), ...Object.values(states.enemy)].map((f) => f.state);
}

function render() {
  if (app.screen === 'entry') {
    // Back from S1 lands here: restore the CTA, clear whatever the flow was
    // showing so a later "Fill from screenshots" tap starts clean.
    if (entryNode) { entryNode.hidden = false; entryNode.querySelector('#ocrfCtaScreenshots')?.focus({ preventScroll: true }); }
    root()?.remove();
    return;
  }
  if (app.screen === 's1') { show(renderS1()); wireS1(root(), { onPick: onPickKind }); return; }
  if (app.screen === 's2') {
    const coverage = controller.flow.coverage();
    show(renderS2({ types: controller.flow.types(), coverage,
      shots: { you: app.shots.you.map((s) => s.id), enemy: app.shots.enemy.map((s) => s.id) } }));
    wireS2(root(), { onDropzone, onTypeTag, onContinue: onS2Continue });
    return;
  }
  if (app.screen === 's3') {
    show(renderS3());
    const handle = driveScan({
      run: () => controller.readAll({ you: app.shots.you.map((s) => s.bytes), enemy: app.shots.enemy.map((s) => s.bytes) }),
      onStepChange: (i) => applyStepClasses(root(), i),
      onDone: onReadDone, onError: onReadError,
    });
    wireS3(root(), { onCancel: () => { handle.cancel(); goto('s2', { push: false }); } });
    return;
  }
  if (app.screen === 's4') {
    const states = allFieldStates();
    show(renderS4({ states, tally: computeTally(flatTallyStates(states)) }));
    wireS4(root(), { onOpenField: openEditor, onOpenPicture: openPicture, onReset: () => doReset('s4') });
    return;
  }
  if (app.screen === 's5') {
    const states = allFieldStates();
    const tally = computeTally(flatTallyStates(states));
    const conversion = app.lastRead?.conversion ?? {};
    const plan = buildFillPlan({ conversion, heroesMe: null, heroesFoe: null });   // hero-gen defaulting: dormant, Ruling #3
    app.priorSnapshot = buildSnapshot({
      percentsMe: window.readInputPanelPct ? window.readInputPanelPct('me') : {},
      percentsFoe: window.readInputPanelPct ? window.readInputPanelPct('foe') : {},
      heroesMe: null, heroesFoe: null, statsScoutedChecked: document.getElementById('statsScouted')?.checked ?? false,
    });
    applyFillPlan(plan);
    show(renderS5({ chipText: computeChipText(tally), complete: tally.clear, states }));
    const undoChip = document.getElementById('ocrfUndoChip');
    if (undoChip) undoChip.hidden = !shouldShowUndo(app.priorSnapshot);
    wireS5(root(), {
      onToggleChip: onToggleS5Chip, onOpenPicture: openPicture, onReset: () => doReset('s5'),
      onUndo: () => {
        const snap = app.priorSnapshot;
        if (!snap) return;
        applyFillPlan({ me: snap.me.panel, foe: snap.foe.panel, heroesMe: null, heroesFoe: null });
        const statsScouted = document.getElementById('statsScouted');
        if (statsScouted) statsScouted.checked = snap.statsScoutedChecked;
        if (window.updateFinalStats) window.updateFinalStats();
      },
    });
    return;
  }
  if (app.screen === 'e1') { show(renderE1(app.e1Variant ?? 'wrong', app.e1Counts ?? {})); wireE1(root(), { onRetake: onE1Retake, onTypeMissing: onE1TypeMissing }); return; }
}

function onPickKind(kind) { controller.flow.pickKind(kind); goto('s2'); }

// Real file input: no decision logic (Task 6 already decided what's a valid
// type/what the dropzone says) — just OS-picker plumbing + reading bytes.
function onDropzone(side) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/png,image/jpeg,image/webp';
  input.multiple = true;
  input.addEventListener('change', async () => {
    for (const file of input.files) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const id = `${side}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      controller.flow.addShot(side, id);
      app.shots[side].push({ id, bytes });
    }
    render();
  });
  input.click();
}

// Real anchored popover: no decision logic (Task 6's TYPE_LABEL/YOU_TYPES/
// ENEMY_TYPES are the only source of truth for what's offered).
function onTypeTag(side, tagElement) {
  document.querySelectorAll('.ocrf-type-menu').forEach((el) => el.remove());
  const options = side === 'you' ? YOU_TYPES : ENEMY_TYPES;
  const menu = document.createElement('div');
  menu.className = 'ocrf-type-menu';
  menu.setAttribute('role', 'menu');
  menu.innerHTML = options.map((type) => (
    `<button type="button" role="menuitem" data-type="${type}">${TYPE_LABEL[type]}</button>`
  )).join('');
  tagElement.insertAdjacentElement('afterend', menu);
  menu.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => {
      controller.flow.setSideType(side, btn.dataset.type);
      menu.remove();
      render();
    });
  });
  const dismiss = (ev) => {
    if (!menu.contains(ev.target) && ev.target !== tagElement) {
      menu.remove();
      document.removeEventListener('click', dismiss, true);
    }
  };
  setTimeout(() => document.addEventListener('click', dismiss, true), 0);
}

function onS2Continue() { goto('s3'); }   // PREP dropped entirely (Ruling #1) — every read is the same network round trip
function onReadDone(result) { app.lastRead = result; const unreadable = countUnreadable(result); if (unreadable === 0) goto('s4', { push: false }); else { app.e1Variant = 'partial'; app.e1Counts = { readCount: 24 - unreadable, totalCount: 24 }; goto('e1', { push: false }); } }
function onReadError(err) { app.e1Variant = 'wrong'; goto('e1', { push: false }); }
function countUnreadable(result) { return Object.values(result.results ?? {}).reduce((n, r) => n + (r?.unreadable_fields?.length ?? 0), 0); }
function onE1Retake() { app.shots = { you: [], enemy: [] }; goto('s2', { push: false }); }
function onE1TypeMissing() { goto('s4', { push: false }); }
function onToggleS5Chip() { const chip = document.getElementById('ocrfS5Chip'); const body = document.getElementById('ocrfS5Body'); const open = chip.getAttribute('aria-expanded') === 'true'; chip.setAttribute('aria-expanded', String(!open)); body.hidden = open; }

function doReset(screen) {
  const key = `resetState_${screen}`;
  const next = nextResetState(app[key] ?? 'idle');
  app[key] = next.state;
  const btn = document.getElementById(screen === 's4' ? 'ocrfResetS4' : 'ocrfResetS5');
  if (btn) btn.textContent = next.label;
  if (next.shouldClear) {
    app.savedValues = { you: {}, enemy: {} }; app.typedFields = { you: {}, enemy: {} };
    render();
  } else {
    app.resetTimer = setTimeout(() => { app[key] = 'idle'; if (btn) btn.textContent = 'Reset'; }, 3000);
  }
}

function openEditor(fieldKey) {
  const [side, key] = [fieldKey.split('-')[0], fieldKey.slice(fieldKey.indexOf('-') + 1)];
  const states = allFieldStates();
  const content = editorContentFor({ side, key, fieldState: states[side][key] });
  const scrim = document.body.appendChild(Object.assign(document.createElement('div'), { innerHTML: renderEditorSheet() })).firstElementChild;
  scrim.querySelector('#ocrfEditorTitle').textContent = content.title;
  scrim.querySelector('#ocrfEditorCrop').textContent = content.cropBody;
  scrim.querySelector('#ocrfEditorInput').value = content.inputValue;
  scrim.querySelector('#ocrfEditorHelp').textContent = content.help;
  scrim.removeAttribute('inert'); scrim.setAttribute('aria-hidden', 'false');
  scrim.querySelector('#ocrfEditorInput').focus();
  scrim.querySelector('#ocrfEditorCancel').addEventListener('click', () => scrim.remove());
  scrim.querySelector('#ocrfEditorClose').addEventListener('click', () => scrim.remove());
  scrim.querySelector('#ocrfEditorSave').addEventListener('click', () => {
    const result = validateEditorInput(scrim.querySelector('#ocrfEditorInput').value);
    const msg = scrim.querySelector('#ocrfEditorMsg');
    if (!result.ok) { if (!result.empty) { msg.textContent = result.message; msg.hidden = false; } return; }
    app.savedValues[side][key] = result.value; app.typedFields[side][key] = true;
    scrim.remove(); render();
  });
}
function openPicture() {
  const states = allFieldStates();
  const wrap = document.body.appendChild(Object.assign(document.createElement('div'), { innerHTML: renderPictureView(states) }));
  wrap.querySelector('.ocrf-picture-scroll')?.scrollIntoView({ block: 'center' });
}

function boot() {
  entryNode = mountEntry({ root: document });   // module-level (see the `let entryNode` declaration above render())
  if (!entryNode) return;
  wireEntry(entryNode, {
    checkAccess,
    onProceed: () => {
      entryNode.hidden = true;
      // Reuse an existing #ocrfRoot (e.g. after Back-to-entry then proceeding
      // again) rather than appending a second one with a duplicate id.
      const stack = root() || document.body.appendChild(Object.assign(document.createElement('div'), { id: 'ocrfRoot' }));
      goto('s1');
    },
    onNeedsUpgrade: () => {
      const wrap = document.createElement('div'); wrap.innerHTML = renderUpgradeNote();
      const node = wrap.firstElementChild; document.body.appendChild(node);
      node.removeAttribute('inert'); node.setAttribute('aria-hidden', 'false');
      wireUpgradeNote(node, {
        checkout: () => fetch('/shell/billing/checkout', { method: 'POST', credentials: 'same-origin' })
          .then((r) => { if (!r.ok) throw new Error('checkout unavailable'); return r.json(); }),
      });
    },
  });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}
