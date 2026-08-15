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
  renderS1, renderS2, renderE1, wireS1, wireS2,
  YOU_TYPES, ENEMY_TYPES, TYPE_LABEL,
} from './screens/pick_upload.mjs';
import { renderS3, driveScan, applyStepClasses, wireS3 } from './screens/reading.mjs';
import {
  renderS4, renderEditorSheet, renderPictureView, renderPictureSheet, fieldRenderState, computeTally,
  validateEditorInput, editorContentFor, nextResetState, wireS4,
} from './screens/review.mjs';
import { renderS5, computeChipText, conversionNotices, shouldShowUndo, buildFillPlan, applyFillPlan, wireS5 } from './screens/setup.mjs';
import { createController } from './controller.mjs';
import { classifyFields, ALL_FIELD_KEYS, buildSnapshot } from './fill_mapper.mjs';

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
// Created lazily inside boot() (not at module top level): this file must stay
// importable under node:test (no `window` there) so the pure pieces below
// (createDelegatedClickHandler, planS2Entry) are unit-testable — boot() only
// ever runs in a real browser (guarded at the bottom of this file), so
// window.localStorage is never reached outside one.
let controller = null;

const app = { history: ['entry'], screen: 'entry', navOpts: null,
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
  // [data-back] is handled by the single global delegate wired in boot()
  // (D-037) — no per-render listener here, so it can never double-fire.
}

function goto(screen, opts = {}) {
  if (app.resetTimer) { clearTimeout(app.resetTimer); app.resetTimer = null; }
  const push = opts.push !== false;
  if (push) app.history.push(screen); else app.history[app.history.length - 1] = screen;
  app.screen = screen;
  // Carries fromRecovery/showMissing (D-039) through to render()'s arrival
  // handling for the target screen. MUST be consumed via takeNavOpts (D-041
  // fix) by whichever render() branch reads it, not read directly — render()
  // is also called by internal actions (onDropzone's upload callback,
  // onTypeTag's selection) that are NOT a fresh navigation, and those calls
  // must see null, never this same opts object again. D-041 was exactly
  // this: nothing ever cleared it, so every post-upload re-render on s2
  // still saw {fromRecovery:true} from the ORIGINAL recovery navigation and
  // re-ran the "clear everything currently tracked" logic — wiping out the
  // shot that upload had just added, every single time.
  app.navOpts = opts;
  render();
}
// D-041 fix: exactly-once consumption of app.navOpts. Returns the pending
// opts (possibly {}, which is truthy — a plain goto() with no special opts
// is still a fresh entry) and clears them; returns null when nothing is
// pending, i.e. this render() call was NOT preceded by a fresh goto() —
// an internal action (upload, type change) re-rendering the current screen.
export function takeNavOpts(appLike) {
  const opts = appLike.navOpts;
  appLike.navOpts = null;
  return opts;
}
function back() {
  if (app.history.length > 1) { app.history.pop(); app.screen = app.history[app.history.length - 1]; render(); }
}

// D-037 fix (single global click delegate, the mock's own pattern —
// prototype/mocks/ocr_flow_mock.html's `document.addEventListener('click',
// ...)` block): every screen template's [data-goto]/[data-back] controls are
// bound here, ONE place, instead of per-screen wire*() functions — which is
// exactly how S4's "Next" (data-goto="s5") ended up bound to nothing at all.
// Exported and dependency-injected (goto/back passed in, never closed over)
// so the actual branching is unit-testable without a real DOM (see
// tests/ocr_flow.test.mjs) — the real listener below just wires this against
// the module's own goto/back closures.
export function createDelegatedClickHandler({ goto: gotoFn, back: backFn, onRemoveThumb, onOpenField }) {
  return function handleDelegatedClick(event) {
    const target = event.target;
    if (!target || typeof target.closest !== 'function') return;
    const goEl = target.closest('[data-goto]');
    if (goEl) {
      event.preventDefault();
      const opts = {};
      if (goEl.dataset.recovery) opts.fromRecovery = true;
      if (goEl.dataset.showMissing) opts.showMissing = true;
      gotoFn(goEl.dataset.goto, opts);
      return;
    }
    const backEl = target.closest('[data-back]');
    if (backEl) { event.preventDefault(); backFn(); return; }
    // D-035: screens/pick_upload.mjs's renderThumbs() remove control
    // (mock's .thumb-x counterpart) — side + INDEX into that side's shot list.
    const removeEl = target.closest('[data-remove-thumb]');
    if (removeEl && onRemoveThumb) {
      event.preventDefault();
      onRemoveThumb(removeEl.dataset.removeThumbSide, parseInt(removeEl.dataset.removeThumb, 10));
      return;
    }
    // S5 field-editor fix: screens/review.mjs's renderReviewGrid is embedded
    // identically in both renderS4's grid and renderS5's expanded stats
    // body — wireS4 used to wire [data-field] with a PER-BUTTON listener
    // (S4-only), and wireS5 never wired it at all, so a field tapped from
    // S5's own expanded chip silently did nothing. Handled once here,
    // uniformly, for whichever screen actually rendered the grid.
    const fieldEl = target.closest('[data-field]');
    if (fieldEl && onOpenField) {
      event.preventDefault();
      onOpenField(fieldEl.dataset.field);
    }
  };
}

// D-039 fix: the pure decision behind E1's "Add a clearer screenshot" exit
// (data-goto="s2" data-recovery="1", routed here by the delegate above).
// Previously onE1Retake only cleared app.shots (the byte-holding array) and
// never told controller.flow — so flow_state.mjs's own shotState (and
// therefore coverage()) still reported the old shots as present: phantom
// "covered" badges, Continue wrongly enabled with zero real shots, and (via
// the old onReadDone's unreadable===0-vacuously-true bug, fixed separately
// as D-038) a scan of nothing landing straight on S4. This returns exactly
// what needs clearing — the CURRENT ids tracked by controller.flow for BOTH
// sides, so the caller can remove every one of them from flow_state.mjs too
// — plus the exact removal notice (mock copy verbatim, ocr_flow_mock.html's
// enterAddPicture(fromRecovery)). Pure and DOM-free: testable without a real
// DOM (see tests/ocr_flow.test.mjs).
export function planS2Entry({ fromRecovery, shotsYou, shotsEnemy }) {
  if (!fromRecovery) return { clearYou: [], clearEnemy: [], notice: null };
  return {
    clearYou: [...shotsYou],
    clearEnemy: [...shotsEnemy],
    notice: 'We took that one out. Add a new screenshot.',
  };
}

// D-036 fix: reads app.lastRead.VIEWS (controller.mjs's deriveViews output),
// never app.lastRead.results directly. A battle-covered side (no upload of
// its own) has no entry in `results` at all — it only ever exists in
// `views`, which deriveViews already builds correctly (documented "never a
// second call") and is now enriched with fieldConf/fieldEngine (Ruling #2)
// specifically so this function doesn't need its own field_engine
// translation any more.
function fieldStatesFor(side) {
  const view = app.lastRead?.views?.[side];
  const classification = classifyFields({
    expectedKeys: ALL_FIELD_KEYS,
    stats: view?.stats ?? {},
    fieldConf: view?.fieldConf ?? {},
    fieldEngine: view?.fieldEngine ?? {},
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
    // D-039: arriving via E1's "Add a clearer screenshot" (data-goto="s2"
    // data-recovery="1") must actually clear the failed upload — from BOTH
    // app.shots (the bytes) AND controller.flow (flow_state.mjs's own
    // shotState, whose coverage()/isCovered() the phantom "covered" badge
    // and Continue-enabled bug both traced back to).
    //
    // D-041 fix: this block must run ONLY on a fresh navigation to s2 (a
    // real goto() call), never on a re-render triggered by an internal
    // action already ON s2 (onDropzone's upload callback, onTypeTag's
    // selection both call render() directly). takeNavOpts returns null for
    // those — the previous code read app.navOpts directly with nothing ever
    // clearing it, so EVERY re-render after landing here via recovery still
    // saw {fromRecovery:true} and re-cleared whatever the user had just
    // uploaded, forever (the reported "permanently dead" dropzones).
    const navOpts = takeNavOpts(app);
    if (navOpts) {
      const plan = planS2Entry({
        fromRecovery: !!navOpts.fromRecovery,
        shotsYou: controller.flow.shots('you'),
        shotsEnemy: controller.flow.shots('enemy'),
      });
      for (const id of plan.clearYou) controller.flow.removeShot('you', id);
      for (const id of plan.clearEnemy) controller.flow.removeShot('enemy', id);
      if (plan.clearYou.length || plan.clearEnemy.length) app.shots = { you: [], enemy: [] };
      app.s2Notice = plan.notice;
    }

    const coverage = controller.flow.coverage();
    show(renderS2({ types: controller.flow.types(), coverage, notice: app.s2Notice,
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
    wireS4(root(), { onOpenPicture: openPicture, onReset: () => doReset('s4') });
    return;
  }
  if (app.screen === 's5') {
    const states = allFieldStates();
    const tally = computeTally(flatTallyStates(states));
    const conversion = app.lastRead?.conversion ?? {};
    // D-042 fix: savedValues (S4's editor corrections, plus anything typed
    // via the pure-manual "Type them in myself" path where conversion is
    // never even attempted) now merges over conversion — previously this
    // call only ever saw `conversion`, so the manual path filled nothing
    // but statsScouted=true, and any S4 correction to an otherwise-ready
    // side's conversion was silently dropped.
    const plan = buildFillPlan({ conversion, savedValues: app.savedValues, heroesMe: null, heroesFoe: null });   // hero-gen defaulting: dormant, Ruling #3
    // D-044: the chip and the fill must agree — a side whose conversion
    // refused (needs_specials etc.) is left unfilled by the plan, so the
    // chip may not claim completeness and the body must say why.
    const notices = conversionNotices(conversion);
    app.priorSnapshot = buildSnapshot({
      percentsMe: window.readInputPanelPct ? window.readInputPanelPct('me') : {},
      percentsFoe: window.readInputPanelPct ? window.readInputPanelPct('foe') : {},
      heroesMe: null, heroesFoe: null, statsScoutedChecked: document.getElementById('statsScouted')?.checked ?? false,
    });
    applyFillPlan(plan);
    show(renderS5({ chipText: computeChipText(tally, notices), complete: tally.clear && !notices.length, states, notices }));
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
  // E1's two exits (data-goto="s2" data-recovery="1" / data-goto="s4"
  // data-show-missing="1") are handled entirely by the global delegate
  // (D-037/D-039) — no per-screen wireE1() here any more; keeping both would
  // double-fire goto() on every click (wireE1's own listener AND the
  // document-level delegate both matching the same button).
  if (app.screen === 'e1') { show(renderE1(app.e1Variant ?? 'wrong', app.e1Counts ?? {})); return; }
}

function onPickKind(kind) { controller.flow.pickKind(kind); goto('s2'); }

// Real file input: no decision logic (Task 6 already decided what's a valid
// type/what the dropzone says) — just OS-picker plumbing + reading bytes.
// The picker input must be ROOTED in the document while the OS dialog is
// open: a detached element (the original implementation) can be garbage-
// collected mid-pick, after which the change event simply never fires —
// "I picked a file and nothing happened" (owner report 2026-08-15).
// Synthetic-drive tests dispatch change directly and can't catch this, so
// the rooting is the guard; a stale picker left by a cancelled dialog is
// removed before creating the next one.
function onDropzone(side) {
  document.querySelector('input[data-ocrf-picker]')?.remove();
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/png,image/jpeg,image/webp';
  input.multiple = true;
  input.hidden = true;
  input.setAttribute('data-ocrf-picker', side);
  document.body.appendChild(input);
  input.addEventListener('change', async () => {
    for (const file of input.files) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const id = `${side}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      controller.flow.addShot(side, id);
      app.shots[side].push({ id, bytes });
    }
    // The recovery removal notice has served its purpose once a replacement
    // screenshot lands — leaving it up reads as stale (L4 closing nit).
    if (input.files.length) app.s2Notice = null;
    input.remove();
    render();
  });
  input.click();
}

// D-035 fix: index into app.shots[side] (matches renderThumbs's own
// side+index keying) resolved to the real shot id for controller.flow
// (flow_state.mjs removes by id, not position) — removing then re-renders,
// which naturally recomputes both sides' covered badges and Continue state
// (Task 6's existing, untouched dropzoneLabel/computeS2ContinueState).
function onRemoveThumb(side, index) {
  const shot = app.shots[side][index];
  if (!shot) return;
  controller.flow.removeShot(side, shot.id);
  app.shots[side].splice(index, 1);
  render();
}

// D-040 fix (mock's own proven pattern, ocr_flow_mock.html's
// syncBackgroundInert): whenever ANY sheet/menu is open, every OTHER direct
// child of <body> — the host page's own <main>/<header> (Formation, hero
// pickers, Run button, the account chip — none of them scoped by this file,
// all of them real interactive elements once "the flow renders inside the
// real app's page"), #ocrfRoot itself, and the entry card — becomes `inert`:
// unfocusable and unclickable. Combined with a real DOM's native Tab order,
// this is what makes "focus cannot escape" true without a hand-rolled
// focus-trap loop — there is simply nowhere else for Tab to land. Removed
// again the moment nothing is open.
function openSheetEls() {
  return [...document.querySelectorAll('.ocrf-modal-scrim, .ocrf-type-menu')]
    .filter((el) => el.isConnected && el.getAttribute('aria-hidden') !== 'true');
}
function syncBackgroundInert() {
  const open = openSheetEls();
  for (const child of document.body.children) {
    // CONTAINS, not just direct-child identity: the editor/picture scrims
    // are appended straight to <body> (child === el matches), but the
    // type-tag menu is inserted as a sibling deep inside #ocrfRoot's own
    // rendered content (child.contains(el) matches instead) — checking
    // identity alone would inert #ocrfRoot itself the moment the menu
    // opened, and `inert` cascades to descendants, silently inerting the
    // very menu it was supposed to keep interactive.
    const keepsSomethingOpen = open.some((el) => child === el || child.contains(el));
    if (keepsSomethingOpen || !open.length) child.removeAttribute('inert');
    else child.setAttribute('inert', '');
  }
}

let lastFocusBeforeSheet = null;
function openScrim(scrim, focusTarget) {
  lastFocusBeforeSheet = document.activeElement;
  scrim.removeAttribute('inert');
  scrim.setAttribute('aria-hidden', 'false');
  syncBackgroundInert();
  focusTarget.focus();
}
function closeScrim(scrim) {
  if (scrim.contains(document.activeElement)) document.activeElement.blur();
  scrim.remove();
  syncBackgroundInert();
  if (lastFocusBeforeSheet) { try { lastFocusBeforeSheet.focus(); } catch (err) { /* target gone */ } }
  lastFocusBeforeSheet = null;
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
  syncBackgroundInert();   // D-040: the menu counts as an open sheet too
  menu.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => {
      controller.flow.setSideType(side, btn.dataset.type);
      menu.remove();
      syncBackgroundInert();
      render();
    });
  });
  const dismiss = (ev) => {
    if (!menu.contains(ev.target) && ev.target !== tagElement) {
      menu.remove();
      syncBackgroundInert();
      document.removeEventListener('click', dismiss, true);
    }
  };
  setTimeout(() => document.addEventListener('click', dismiss, true), 0);
}

function onS2Continue() { goto('s3'); }   // PREP dropped entirely (Ruling #1) — every read is the same network round trip

// D-038 fix: onReadDone previously only checked "any unreadable at all?",
// collapsing two very different outcomes into one "partial" branch — a
// clean 200 that parsed NOTHING (the evaluator's probe: a C_battle_1-style
// response, 24 unreadable, 0 read) landed on E1's PARTIAL copy ("We read 0
// of 24 numbers... The rest were too unclear to read"), which is nonsense
// when none were read at all — that is exactly the WRONG-screenshot case.
// Pure decision, exported/tested (tests/ocr_flow.test.mjs) — reuses the
// SAME allFieldStates()/flatTallyStates() pipeline S4 itself renders from
// (Ruling #2's ok/check/missing tiers — a "check" field counts as read),
// so E1's reported count can never disagree with what S4 would actually show.
export function decideAfterRead(tallyStates) {
  const total = tallyStates.length;
  const missingCount = tallyStates.filter((s) => s === 'missing').length;
  const readCount = total - missingCount;
  if (missingCount === 0) return { screen: 's4' };
  if (readCount === 0) return { screen: 'e1', variant: 'wrong' };
  return { screen: 'e1', variant: 'partial', readCount, totalCount: total };
}
function onReadDone(result) {
  app.lastRead = result;
  const decision = decideAfterRead(flatTallyStates(allFieldStates()));
  if (decision.screen === 's4') { goto('s4', { push: false }); return; }
  app.e1Variant = decision.variant;
  app.e1Counts = decision.variant === 'partial' ? { readCount: decision.readCount, totalCount: decision.totalCount } : {};
  goto('e1', { push: false });
}
function onReadError(err) { app.e1Variant = 'wrong'; goto('e1', { push: false }); }
// onE1Retake/onE1TypeMissing retired (D-039): both are now the generic
// [data-goto] delegate (D-037) plus planS2Entry's clearing logic in the 's2'
// render branch above — see the comment on the 'e1' render branch.
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

// D-040 fix: previously appended via a throwaway wrapper div whose EMPTY
// shell was never removed (scrim.remove() only ever removed the inner
// element extracted via .firstElementChild) — a growing pile of empty <div>s
// on every open/close cycle. insertAdjacentHTML has no such wrapper. Also
// now tracks pre-open focus and runs syncBackgroundInert (D-040) instead of
// only toggling this one scrim's own inert/aria-hidden.
function openEditor(fieldKey) {
  const [side, key] = [fieldKey.split('-')[0], fieldKey.slice(fieldKey.indexOf('-') + 1)];
  const states = allFieldStates();
  const content = editorContentFor({ side, key, fieldState: states[side][key] });
  document.body.insertAdjacentHTML('beforeend', renderEditorSheet());
  const scrim = document.getElementById('ocrfEditorScrim');
  scrim.querySelector('#ocrfEditorTitle').textContent = content.title;
  scrim.querySelector('#ocrfEditorCrop').textContent = content.cropBody;
  scrim.querySelector('#ocrfEditorInput').value = content.inputValue;
  scrim.querySelector('#ocrfEditorHelp').textContent = content.help;
  const closeThis = () => closeScrim(scrim);
  scrim.querySelector('#ocrfEditorCancel').addEventListener('click', closeThis);
  scrim.querySelector('#ocrfEditorClose').addEventListener('click', closeThis);
  scrim.addEventListener('click', (ev) => { if (ev.target === scrim) closeThis(); });
  scrim.querySelector('#ocrfEditorSave').addEventListener('click', () => {
    const result = validateEditorInput(scrim.querySelector('#ocrfEditorInput').value);
    const msg = scrim.querySelector('#ocrfEditorMsg');
    if (!result.ok) { if (!result.empty) { msg.textContent = result.message; msg.hidden = false; } return; }
    app.savedValues[side][key] = result.value; app.typedFields[side][key] = true;
    closeScrim(scrim); render();
  });
  const input = scrim.querySelector('#ocrfEditorInput');
  openScrim(scrim, input);
  input.select();
}
function openPicture() {
  const states = allFieldStates();
  document.body.insertAdjacentHTML('beforeend', renderPictureSheet());
  const scrim = document.getElementById('ocrfPictureScrim');
  scrim.querySelector('#ocrfPictureBody').innerHTML = renderPictureView(states);
  const closeThis = () => closeScrim(scrim);
  scrim.querySelector('#ocrfPictureClose').addEventListener('click', closeThis);
  scrim.addEventListener('click', (ev) => { if (ev.target === scrim) closeThis(); });
  openScrim(scrim, scrim.querySelector('#ocrfPictureClose'));
}

// D-040: Escape closes whichever sheet/menu is currently open — same
// priority-chain shape as the mock's own keydown listener (its own OR-chain:
// flowmap > picture > editor > tagMenu; this build has no flow map, so
// picture > editor > menu). Split into a pure decision (exported, unit-
// tested — see tests/ocr_flow.test.mjs) and a thin DOM executor, same
// discipline as decideAfterRead (D-038) and planS2Entry (D-039): with
// syncBackgroundInert correctly applied, at most one of these is ever
// actually open at a time (everything else is inert, so nothing else is
// reachable to open a second one), but the chain stays defensive.
export function decideSheetToClose({ pictureOpen, editorOpen, menuOpen }) {
  if (pictureOpen) return 'picture';
  if (editorOpen) return 'editor';
  if (menuOpen) return 'menu';
  return null;
}
function closeWhicheverIsOpen() {
  const picture = document.getElementById('ocrfPictureScrim');
  const editor = document.getElementById('ocrfEditorScrim');
  const menu = document.querySelector('.ocrf-type-menu');
  const which = decideSheetToClose({
    pictureOpen: !!picture && picture.getAttribute('aria-hidden') === 'false',
    editorOpen: !!editor && editor.getAttribute('aria-hidden') === 'false',
    menuOpen: !!menu,
  });
  if (which === 'picture') { closeScrim(picture); return true; }
  if (which === 'editor') { closeScrim(editor); return true; }
  if (which === 'menu') { menu.remove(); syncBackgroundInert(); return true; }
  return false;
}

function boot() {
  controller = createController({ fetchMe, postPanel, storage: window.localStorage });
  document.addEventListener('click', createDelegatedClickHandler({ goto, back, onRemoveThumb, onOpenField: openEditor }));
  // D-040: Escape closes whichever sheet/menu is open (mock's own pattern).
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') closeWhicheverIsOpen(); });

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
