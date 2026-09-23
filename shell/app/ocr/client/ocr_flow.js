// shell/app/ocr/client/ocr_flow.js — FINAL bootstrap (Task 10 Part A).
//
// Every decision this file makes was already built and tested by Tasks 1-9;
// this is pure assembly (a navigation stack mirroring the mock's own proven
// goto/back/show pattern, and the read -> convert -> classify -> render
// pipeline). SERVER-ONLY v1 (COORDINATOR RULING 2026-08-10 #1): no client
// OCR engine import, no PREP screen/step — see controller.mjs and
// screens/reading.mjs for the rationale. Upload mechanics (slot picker,
// drag-drop, paste, thumbnails) are wired here to real DOM plumbing; the
// decisions (which slots a type has, what counts as scannable) live in
// screens/pick_upload.mjs's pure model (2026-08-29 slot-grid redesign).
import { mountEntry, wireEntry, renderUpgradeNote, wireUpgradeNote } from './screens/entry.mjs';
import {
  renderUpload, wireUpload, uploadModel, cardsFor, SLOTS, DEFAULT_COLUMNS, otherColumn, renderE1,
  renderSampleFallback,
} from './screens/pick_upload.mjs';
import { renderS3, driveScan, applyStepClasses, wireS3, setScanNote } from './screens/reading.mjs';
import {
  renderS4, renderEditorSheet, renderPictureView, renderPictureSheet, fieldRenderState, computeTally,
  validateEditorInput, editorContentFor, nextResetState, wireS4,
} from './screens/review.mjs';
import { renderS5, computeChipText, conversionNotices, shouldShowUndo, buildFillPlan, applyFillPlan, wireS5 } from './screens/setup.mjs';
import { createController } from './controller.mjs';
import { classifyFields, ALL_FIELD_KEYS, buildSnapshot } from './fill_mapper.mjs';
import { mapError } from './error_copy.mjs';

function fetchMe() { return fetch('/shell/me', { credentials: 'same-origin' }).then((r) => r.json()); }
async function checkAccess() {
  try {
    const me = await fetchMe();
    const plan = me?.user?.plan;
    return { allowed: plan === 'pro', plan: plan ?? null, reachable: true, userId: me?.user?.user_id ?? null };
  } catch { return { allowed: false, plan: null, reachable: false, userId: null }; }
}
// UXJ-008 (round 3): the CURRENT scan's abort handle, set by render()'s s3
// branch and fired by leaveScanIfRunning() on ANY departure from S3 that
// isn't the read's own completion. Module-level (not threaded through
// controller.readAll) deliberately: postPanel is already this file's own
// injected dependency, and the controller seam's signature stays untouched.
// Honesty note: the server pre-commits the metering BEFORE the engines run
// (crash-proof quota, by design) — aborting the request stops the client
// machinery and the connection, but the quota unit for an abandoned read is
// already spent and is NOT refunded.
let activeScanAbort = null;

function postPanel({ shotBytesList, side, panelType }) {
  const form = new FormData();
  for (const bytes of shotBytesList) form.append('file', new Blob([bytes], { type: 'image/png' }), 'shot.png');
  form.append('side', side);
  if (panelType) form.append('panel', panelType);
  return fetch('/shell/ocr/panel', { method: 'POST', body: form, credentials: 'same-origin',
    signal: activeScanAbort ? activeScanAbort.signal : undefined }).then(async (r) => {
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
  noBuffs: { you: false, enemy: false },   // QAC-011: attestation is PER SIDE, like the file store
  lastSlot: null,   // paste routing (slot key "side:key")
  // UXE-008 (Gate-1 UX round 1): WHY lastSlot currently points where it
  // does. true = the user aimed at that row themselves (clicked its paste
  // well, dragged over it, or pressed its "+ Add"); false = a file just
  // LANDED there and the row is merely the most recent one touched. Only an
  // explicit aim may hold the armed well on a row that still has room - see
  // pasteTargetSlot.
  aimExplicit: false,
  // Owner 2026-09-06 (designer spec): per-side column choice for battle
  // reports (L = this side's stats are in the LEFT column), the enemy's
  // "Use your report for the enemy too" box, and whether the missing line
  // has been requested by a tap on the locked Scan.
  columns: { ...DEFAULT_COLUMNS }, sameReport: false, showMissing: false,
  // U1-M4 (Gate-2 round 1): has the same-report hint already fired its one
  // pulse for the CURRENT run of the condition? Edge tracking only — the
  // hint itself is derived fresh from the model on every render.
  sameHintPulsed: false,
  shots: { you: [], enemy: [] },            // [{id, bytes: Uint8Array, url, slot}]
  savedValues: { you: {}, enemy: {} }, typedFields: { you: {}, enemy: {} },
  lastRead: null, priorSnapshot: null, resetTimer: null };

function root() { return document.getElementById('ocrfRoot'); }

// Owner escalation 2026-08-15 ("these are way at the bottom of the page and
// they are mobile size"): #ocrfRoot used to sit in NORMAL FLOW at the end of
// <body>, so on desktop every screen rendered as a phone-width column below
// the entire app — clicking the CTA looked like "the page flashed and the
// button disappeared". The flow is now a TAKEOVER: S1-S4/E1 present as a
// modal dialog (fixed, backdropped, centered card; full-screen sheet under
// 768px — body.ocrf-flow-open in ocr_flow.css), while S5 deliberately is
// NOT modal: per the mock, S5 IS the app again — the Battle-setup chip
// renders inline at the top of the form section next to the freshly filled
// panel (see the s5 branch of render()). Pure so it's unit-testable.
// Owner redesign 2026-08-29 (slot grid): a paste has no target element, so
// the SLOT is decided by, in order: the slot the user last touched (tap or
// drag-over) if it still has room, the first empty slot, then the first
// slot with room. Pure; exported for tests. `model` = uploadModel() output.
// UXE-008 (Gate-1 UX round 1, Major): the Stats row takes TWO files (battle
// stats are two columns), so "last-touched slot wins while it has room" kept
// the armed well on Stats after the FIRST stats screenshot landed - and the
// user's next paste (the Buffs screenshot) silently filed itself as a second
// Stats image. Mis-filing is the one failure this screen exists to prevent,
// and it costs a metered OCR run to discover. New rule: a landed file never
// holds the aim - after anything lands, the target ADVANCES to the first
// empty row; a partially filled multi-file row is targeted again only when
// the user says so themselves (clicks its well, drags over it, presses its
// "+ Add"), which is what `aimExplicit` records. Default true keeps the
// signature honest for callers that mean "this ref was chosen deliberately".
export function pasteTargetSlot(model, lastSlot = null, aimExplicit = true) {
  const flat = model.cards.filter((c) => !c.rowsHidden)
    .flatMap((g) => g.slots.map((s) => ({ ...s, side: g.side, ref: `${g.side}:${s.key}` })));
  const room = (s) => s.state !== 'none' && s.count < s.max;
  const last = aimExplicit ? flat.find((s) => s.ref === lastSlot && room(s)) : null;
  if (last) return last.ref;
  const empty = flat.find((s) => s.state === 'empty');
  if (empty) return empty.ref;
  const any = flat.find(room);
  return any ? any.ref : null;
}

// Where the "Missing: ..." line jumps to. Gate-2 round 1, U1-M4: until now
// this was unconditionally "the first empty required row", which on the one
// screen the playtest got stuck on means the enemy card's Heroes + Experts —
// i.e. the jump scrolled STRAIGHT PAST the control that actually answers the
// question ("Use your report for the enemy too") to demand the very thing
// the user has just said they do not have. When the same-report hint is lit
// (pick_upload.mjs sameHintFor: your card complete, the box shown and off,
// the enemy card untouched), the box IS the missing item's answer, so the
// jump lands there. Every other case is unchanged, byte for byte.
// Pure (returns a selector, touches no DOM); exported for tests.
export function missingJumpTarget(model) {
  const hinted = model.cards.find((c) => c.sameHint);
  if (hinted) return '[data-same]';
  const first = model.cards.filter((c) => !c.rowsHidden)
    .flatMap((c) => c.slots.filter((s) => s.required && s.state === 'empty').map((s) => `${c.side}:${s.key}`))[0];
  return first ? `[data-slot-tile="${first}"]` : null;
}

// Which slot keys the active type accepts for a side — the read sends ONLY
// these (a shot uploaded under another tab stays parked, never silently
// included). Pure; exported for tests.
export function sendableShots(types, side, sideShots, sameReport = false) {
  const card = cardsFor({ types, sameReport }).find((c) => c.side === side);
  if (!card || card.rowsHidden) return [];
  const keys = new Set(card.slots.map((s) => s.key));
  return sideShots.filter((s) => keys.has(s.slot));
}

export function presentationFor(screen) {
  return { modal: screen !== 'entry' && screen !== 's5' };
}

// UX_START_JOURNEY_SPEC.md §3.1: "focus returns to whichever launcher opened
// the flow" — up to two real launchers can exist at once (the start-screen
// card, the workspace mode-bar's mini launcher), but only ONE of their host
// regions is ever visible at a time (the prototype's own body.view-start/
// view-work gate — #startScreen and #modeBar are never both shown). Prefer
// the one the click actually came from, PROVIDED it's still the visible one
// (defensive: nothing in this flow lets the user switch view while the
// modal's background is inert, but a future caller shouldn't have to prove
// that to trust this); otherwise fall back to whichever region IS visible.
// Legacy has exactly one launcher and no view-switching concept at all.
// Pure and exported — same split as pasteTargetSlot/decideAfterRead/
// planS2Entry: the DOM visibility check (offsetParent) is thin glue, this
// decision is not.
export function pickReturnLauncher({ mode, lastUsed, startVisible, miniVisible }) {
  if (mode === 'legacy') return 'start';
  if (lastUsed === 'mini' && miniVisible) return 'mini';
  if (lastUsed === 'start' && startVisible) return 'start';
  if (miniVisible) return 'mini';
  if (startVisible) return 'start';
  return null;
}
function isLauncherVisible(el) {
  return !!(el && el.offsetParent !== null);
}

// UX_START_JOURNEY_SPEC.md §3.3 (the owner's headline complaint: "there's no
// place for them to paste it... on mobile you should not be allowed to do
// that"). Pure helper, injectable matchMedia so it's unit-testable without a
// real DOM/browser — real callers omit the arg and fall through to
// window.matchMedia. Evaluated at render time (which rows get a well at
// all) AND again inside the paste listener (touch devices never act on a
// paste even if one somehow reached the document).
export function canPaste(matchMediaFn) {
  const mm = matchMediaFn || (typeof window !== 'undefined' ? window.matchMedia : null);
  if (!mm) return false;
  try { return mm('(hover: hover) and (pointer: fine)').matches; } catch (err) { return false; }
}

// Keycap glyph for the armed paste well: Ctrl+V everywhere except a real Mac
// keyboard, where it's Cmd+V (owner spec: detect via
// navigator.userAgentData?.platform / navigator.platform). Injectable navigator,
// same discipline as canPaste's injectable matchMedia.
export function isMacPlatform(nav) {
  const n = nav || (typeof navigator !== 'undefined' ? navigator : null);
  if (!n) return false;
  const platform = (n.userAgentData && n.userAgentData.platform) || n.platform || '';
  return /mac/i.test(platform);
}

// UXJ-009 (round 3): re-entering the flow after a mid-flow exit silently
// showed the PREVIOUS session's uploads with Continue already enabled — the
// non-destructive exit is deliberate (nothing is lost), but the carry-over
// must be SAID. Pure so it's unit-testable; consumed by boot()'s onProceed,
// rendered through the existing S2 notice slot (and cleared by the same
// existing rule the moment a new screenshot lands).
export function reentryNotice({ shotsYou = [], shotsEnemy = [] } = {}) {
  if (!shotsYou.length && !shotsEnemy.length) return null;
  return 'Earlier screenshots kept.';
}

// Takeover polish round (2026-08-15, continued — live rect verification at
// 1280x720/375x812 found the position:fixed architecture itself correct but
// entrance/exit motion entirely absent: #ocrfRoot.getAnimations() returned
// [] on open). Motion is JS-driven timing (WHEN the real teardown happens)
// wired to purely-CSS animations (WHAT it looks like, ocr_flow.css) — the
// design system's rule for JS-driven motion (see DESIGN_SYSTEM.md §2 rule 4,
// "New JS-driven motion must ALSO check matchMedia... before running") is
// about the JS side specifically: the CSS kill-switch alone silences the
// ANIMATION under reduced motion, but without this check the close path
// would still insert an artificial ~140ms delay with zero visual payoff —
// worse than either instant or animated. Entrance has no such delay (the
// class-add is fire-and-forget, CSS kill-switch is sufficient on its own),
// so only the close path needs the JS-level check.
function prefersReducedMotion() {
  return typeof window !== 'undefined' && !!window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// True for exactly one show() call: set by boot()'s onProceed right before
// the very first goto('s1') of a fresh open, consumed (and cleared) the next
// time show() runs. #ocrfRoot itself is only ever created once per open (see
// onProceed below), so its own scrim-fade animation is a plain unconditional
// CSS rule with no JS bookkeeping — but `.screen` is recreated by EVERY
// show() call (innerHTML swap on every navigation), so without this flag the
// dialog rise/scale would replay on every single S1->S2->S3->S4 click, not
// just the true "opening" moment (see the CSS round's own comment for why
// that's wrong: it would fight requirement 5, "must not scroll-jump BETWEEN
// screens").
let pendingEnterAnimation = false;

// Shared close-path timing for exitFlow()/back()-to-entry: both need the
// SAME "let the close animation play, THEN do the real teardown" shape, so
// this is the one place that owns it. #ocrfRoot must stay mounted (and
// body.ocrf-flow-open must stay applied — that only happens inside render(),
// deliberately deferred to onDone) for the FULL delay: removing the
// ocrf-flow-open class early would drop #ocrfRoot's position:fixed/z-index
// CSS mid-animation, collapsing it back into normal document flow for the
// last ~140ms — precisely the original bug, replayed as a flicker on every
// close. Reduced motion: skip the delay entirely (no class add, no timer) —
// the CSS kill-switch would silence the animation anyway, so waiting would
// only add a dead pause with no visual payoff.
function closeFlowLayer(onDone) {
  const layer = root();
  if (layer && !prefersReducedMotion()) {
    layer.classList.add('ocrf-flow-closing');
    setTimeout(onDone, 140);
  } else {
    onDone();
  }
}

function exitFlow() {
  closeFlowLayer(() => {
    app.history = ['entry'];
    app.screen = 'entry';
    app.navOpts = null;
    render();
  });
}

// Set once by boot() from mountEntry()'s return (screens/entry.mjs) — UP TO
// TWO real launchers now (UX_START_JOURNEY_SPEC.md §3.1): the start-screen
// card and the workspace mode-bar's mini launcher, or (mode:'legacy') the
// one old hero CTA on a host page with no start screen at all. `lastUsed`
// tracks which button a click actually came from, so back-to-entry can
// return focus to THAT one specifically — legacy has only ever had the one.
// Only the legacy card is hidden/restored ([hidden] show/hide) while the
// flow is open: the contract launchers live inside the prototype's own
// view-start/view-work-gated regions (already inert + dimmed by the modal
// scrim while the flow is open — see syncBackgroundInert), so hiding them
// too would just be a second, redundant visibility mechanism to keep in
// sync with the prototype's own CSS.
let launcher = { mode: null, node: null, container: null, mini: null, lastUsed: null };

function show(html) {
  root().innerHTML = html;
  // Takeover polish: #ocrfRoot is now the ONLY scroll owner across a
  // navigation boundary (.ocrf-scr-body scrolls internally WITHIN a
  // screen — see ocr_flow.css — but switching screens replaces the whole
  // subtree). Without this, a browser may carry over whatever scrollTop
  // the PREVIOUS screen left #ocrfRoot at, landing the next screen
  // mid-scroll instead of at its own top — requirement 5's "each screen
  // starts scrolled to top of the layer".
  root().scrollTop = 0;
  const card = root().querySelector('.screen, .ocrf-s5');
  // One-shot dialog entrance (see pendingEnterAnimation's own comment):
  // only the very first .screen shown after a fresh open gets the
  // rise/scale class — every later navigation inside the same open flow
  // swaps screens instantly, no replay.
  if (pendingEnterAnimation) {
    pendingEnterAnimation = false;
    if (card) card.classList.add('ocrf-dialog-enter');
  }
  // Modal chrome: every takeover screen gets an explicit ✕ (44px target)
  // that exits the whole flow — handled by the global delegate's
  // [data-close-flow] branch, same pattern as [data-back]/[data-goto].
  if (card && !card.querySelector('[data-close-flow]')) {
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'ocrf-flow-close';
    close.setAttribute('data-close-flow', '1');
    close.setAttribute('aria-label', 'Close and go back to the app');
    close.innerHTML = '&times;';
    card.prepend(close);
  }
  // preventScroll dropped (takeover polish): it was compensating for
  // #ocrfRoot sitting in normal page flow at the bottom of a long page —
  // focusing a heading down there would otherwise jerk the WHOLE PAGE to
  // scroll it into view. Now that #ocrfRoot is position:fixed (never part
  // of the page's own scroll flow), focus() cannot move the page at all;
  // it only affects #ocrfRoot's own scrollTop, which the reset two lines
  // up already pins to 0 before this runs.
  const heading = root().querySelector('h1, h2[tabindex]');
  if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus(); }
  // [data-back] is handled by the single global delegate wired in boot()
  // (D-037) — no per-render listener here, so it can never double-fire.
}

function goto(screen, opts = {}) {
  if (screen === 's2') screen = 's1';   // 2026-08-29: S1+S2 merged into one slot-grid screen
  if (app.resetTimer) { clearTimeout(app.resetTimer); app.resetTimer = null; }
  const push = opts.push !== false;
  if (push) app.history.push(screen); else app.history[app.history.length - 1] = screen;
  app.screen = screen;
  // Carries fromRecovery/showMissing (D-039) through to render()'s arrival
  // handling for the target screen. MUST be consumed via takeNavOpts (D-041
  // fix) by whichever render() branch reads it, not read directly — render()
  // is also called by internal actions (slot uploads, tab switches) that
  // are NOT a fresh navigation, and those calls
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
// S1 is the only screen whose [data-back] pops all the way to 'entry' (it's
// the first screen ever pushed after a fresh open — every other screen's
// back button lands on another modal screen: S2->S1, S4->S2 via the read
// pipeline's push:false replace, E1->wherever it replaced). That single
// case is a real CLOSE of the takeover, same as the X/Escape/backdrop path,
// so it gets the same animated closeFlowLayer() treatment — otherwise S1's
// own Back button would be the one remaining way to exit with a hard snap.
// Pure and exported (same split as decideAfterRead/planS2Entry/
// decideSheetToClose): a plain array-index check, no DOM needed to prove it.
export function backLandsOnEntry(history) {
  return history.length > 1 && history[history.length - 2] === 'entry';
}
function back() {
  if (app.history.length <= 1) return;
  if (backLandsOnEntry(app.history)) {
    closeFlowLayer(() => { app.history.pop(); app.screen = app.history[app.history.length - 1]; render(); });
    return;
  }
  app.history.pop(); app.screen = app.history[app.history.length - 1]; render();
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
export function createDelegatedClickHandler({ goto: gotoFn, back: backFn, onRemoveThumb, onOpenField, onCloseFlow }) {
  return function handleDelegatedClick(event) {
    const target = event.target;
    if (!target || typeof target.closest !== 'function') return;
    // Modal chrome ✕ (takeover fix, 2026-08-15): exits the whole flow.
    const closeEl = target.closest('[data-close-flow]');
    if (closeEl && onCloseFlow) { event.preventDefault(); onCloseFlow(); return; }
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
    notice: 'Removed. Add a new one.',
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

// UXJ-008 (round 3): ANY departure from S3 that isn't the read's own
// completion tears the scan down — interval cleared, callbacks suppressed,
// request aborted. Runs at the top of every render(): app.screen has
// already been updated by goto()/back()/exitFlow() by the time we get
// here, and the completion path nulls the handle BEFORE navigating, so
// this can never cancel a read that just delivered.
function leaveScanIfRunning() {
  if (app.screen === 's3') return;
  if (app.scanHandle) { app.scanHandle.cancel(); app.scanHandle = null; }
  if (activeScanAbort) { try { activeScanAbort.abort(); } catch (err) { /* already settled */ } activeScanAbort = null; }
}

function render() {
  leaveScanIfRunning();
  // UXJ-010 (round 4): inert bookkeeping BEFORE the branch as well — the two
  // focus restorations inside renderScreen that target elements OUTSIDE
  // #ocrfRoot (exit-to-entry's CTA, S4->S5's inline S5 heading, both living
  // in the host page's <main>) must run against the NEW screen's inert
  // state. syncBackgroundInert derives that from presentationFor(app.screen),
  // which goto() has already updated — running it only after renderScreen
  // left <main> carrying the PREVIOUS cycle's inert during those .focus()
  // calls, which silently no-op on inert subtrees by spec (every modal exit
  // parked focus on <body>; S4->S5 re-opened the closed UXJ-005).
  syncBackgroundInert();
  renderScreen();
  // UXJ-007 (round 3): and AFTER the branch has built/removed whatever it
  // builds, so the decision always sees the final DOM. Idempotent, so the
  // double pass is safe.
  syncBackgroundInert();
}

function renderScreen() {
  // Takeover state first: the modal class + dialog semantics track the
  // CURRENT screen on every render, so no branch below can leave a stale
  // backdrop or a scroll-locked page behind.
  const { modal } = presentationFor(app.screen);
  document.body.classList.toggle('ocrf-flow-open', modal);
  const stack = root();
  if (stack) {
    if (modal) {
      stack.setAttribute('role', 'dialog');
      stack.setAttribute('aria-modal', 'true');
      stack.setAttribute('aria-label', 'Forecast from battle reports');
    } else {
      stack.removeAttribute('role');
      stack.removeAttribute('aria-modal');
      stack.removeAttribute('aria-label');
    }
  }
  if (app.screen === 'entry') {
    // Back from S1 lands here. Legacy: restore the one hero CTA (hidden
    // while the flow was open) and refocus it — unchanged. Contract mode:
    // nothing was hidden (the launcher's own region was already inert +
    // scrim-dimmed while the modal was open — see `launcher`'s own comment),
    // so this only has to pick and refocus whichever launcher should get
    // focus back (§3.1: "focus returns to whichever launcher opened the
    // flow" / "focus whichever is visible").
    if (launcher.mode === 'legacy' && launcher.container) {
      launcher.container.hidden = false;
      launcher.node?.focus({ preventScroll: true });
      // Owner 2026-08-29: never strand the user where the CTA isn't visible.
      launcher.container.scrollIntoView({ block: 'nearest' });
    } else if (launcher.mode === 'contract') {
      const target = pickReturnLauncher({
        mode: launcher.mode, lastUsed: launcher.lastUsed,
        startVisible: isLauncherVisible(launcher.node), miniVisible: isLauncherVisible(launcher.mini),
      });
      const el = target === 'mini' ? launcher.mini : target === 'start' ? launcher.node : null;
      if (el) { el.focus({ preventScroll: true }); el.scrollIntoView?.({ block: 'nearest' }); }
    }
    document.getElementById('ocrfS5Host')?.remove();
    root()?.remove();
    return;
  }
  if (app.screen === 's1') {
    // Combined Upload screen (2026-08-29): type tabs + slot grid + Scan.
    // D-039 recovery and the UXJ-009 re-entry notice keep their exact
    // machinery — the branch just renders the merged screen now.
    // D-041: consume navOpts exactly once (fresh navigation only), never on
    // internal re-renders (slot add/remove/tab switch call render() direct).
    const navOpts = takeNavOpts(app);
    if (navOpts) {
      const plan = planS2Entry({
        fromRecovery: !!navOpts.fromRecovery,
        shotsYou: controller.flow.shots('you'),
        shotsEnemy: controller.flow.shots('enemy'),
      });
      for (const id of plan.clearYou) controller.flow.removeShot('you', id);
      for (const id of plan.clearEnemy) controller.flow.removeShot('enemy', id);
      if (plan.clearYou.length || plan.clearEnemy.length) {
        dropAllShots('you'); dropAllShots('enemy');
      }
      app.s2Notice = plan.notice ?? app.reentryNotice ?? null;
      app.reentryNotice = null;
    }
    const model = currentModel();
    // Thumbnails: LOCAL object URLs only (never uploaded, never stored —
    // the no-storage promise is about the server; self-confirmation that
    // the right screenshot landed is the research round's core finding).
    for (const c of model.cards) {
      for (const s of c.slots) {
        const mine = app.shots[c.side].filter((x) => x.slot === s.key);
        if (mine.length) s.thumbUrls = mine.map((x) => x.url || null);
      }
    }
    if (model.canScan) app.showMissing = false;
    // Desktop paste wells (§3.3): evaluated fresh on every render — a
    // window resize/pointer change between renders must never leave a stale
    // well/keycap on screen. Exactly one well is armed: the same slot a
    // paste would actually land in right now (pasteTargetSlot), so the
    // well's own promise ("Paste here") is never a lie.
    const pasteOn = canPaste();
    const paste = { on: pasteOn, armed: pasteOn ? pasteTargetSlot(model, app.lastSlot, app.aimExplicit) : null, mac: isMacPlatform() };
    show(renderUpload({ model, notice: app.s2Notice, showMissing: app.showMissing, paste }));
    wireUpload(root(), {
      // Per-card type: shots for the other types stay parked per side.
      onType: (side, t) => { controller.flow.setSideType(side, t); render(); },
      onCol: (side, col, locked) => {
        if (locked) { flashFull(document.querySelector('[data-same]')); return; }
        app.columns = { ...app.columns, [side]: col };
        render();
      },
      onSame: () => { app.sameReport = !app.sameReport; render(); },
      onSlot: (side, key) => {
        // "+ Add" is the ONLY picker trigger (owner 2026-09-06); it renders
        // only while the row has room, so this never has to arbitrate a
        // full row. Un-attesting is the None chip's own job.
        const slot = slotDef(side, key);
        if (!slot) return;
        const count = app.shots[side].filter((x) => x.slot === key).length;
        if (count >= slot.max) return;
        openPicker(side, key, slot.max - count);
      },
      onSlotPreview: (side, key) => { openSlotPreview(side, key); },
      // §3.3: a click on ANY well (armed or not) AIMS it — that is all it
      // does. UXE-003 (Gate-1 UX round 1, Major): this used to ALSO run
      // navigator.clipboard.read(), so one intentional paste landed TWICE
      // (the click read the clipboard, then the user's own Ctrl+V inserted
      // the same image again), and merely clicking a well to aim it could
      // silently drop a stale, unrelated clipboard image into a
      // battle-report row. Clicking a target means "aim here", never "act
      // now" — which is exactly what this screen's own tip line already
      // promises ("Paste with Ctrl+V, drop files, or use + Add"). The aim is
      // EXPLICIT (UXE-008): it may hold a partially-filled multi-file row,
      // unlike a row that merely received the last file.
      onPasteWell: (side, key) => {
        app.lastSlot = `${side}:${key}`;
        app.aimExplicit = true;
        render();
        root()?.querySelector(`[data-paste-slot="${side}:${key}"]`)?.focus({ preventScroll: true });
      },
      onMissingJump: () => {
        const sel = missingJumpTarget(currentModel());
        const row = sel ? document.querySelector(sel) : null;
        if (!row) return;
        row.scrollIntoView({ block: 'center' });
        flashFull(row);
        // U1-M4: the checkbox branch is the one jump target that is itself a
        // control, so hand it the keyboard too — a scroll-and-flash says
        // nothing to someone who is not looking at the screen, and the very
        // next key press should be the Space that ticks it. preventScroll so
        // the centring above is not immediately re-done by the focus (same
        // call shape the paste wells already use). A pointer user sees no
        // ring: Chromium withholds :focus-visible when the last input was a
        // tap. The row branch is untouched — a requirement row is a
        // container, not a control, and focusing it would be a lie.
        if (sel === '[data-same]') row.focus({ preventScroll: true });
      },
      onSlotRemove: (side, key, idx) => {
        if (idx === null || idx === undefined) { dropSlot(side, key); render(); return; }
        // QAC-001: the x on ONE thumb removes only that shot.
        const mine = app.shots[side].filter((x) => x.slot === key);
        const shot = mine[idx];
        if (!shot) return;
        dropShot(side, shot);
        app.shots[side] = app.shots[side].filter((x) => x !== shot);
        render();
      },
      onSlotNone: (side) => {
        // QAC-011: per-side toggle. With the same-report box on, your one
        // visible chip speaks for both sides of that one report — but ONLY
        // at read time (effective flags in the s3 branch). The enemy's own
        // stored flag is never written while its rows are hidden, so
        // unticking the box restores exactly the enemy's own state
        // (QAC-024: no attestation leaks onto a report never attested).
        app.noBuffs = { ...app.noBuffs, [side]: !app.noBuffs[side] };
        render();
      },
      onScan: (locked) => {
        // Locked Scan is aria-disabled, not disabled: a tap reveals the
        // missing line (owner: "a prompt that says you're missing something").
        if (locked || !currentModel().canScan) {
          app.showMissing = true; render();
          flashFull(document.querySelector('[data-missing-jump]'));
          return;
        }
        goto('s3');
      },
    });
    // Gate-2 round 1, U1-M4: ONE attention pulse on the rising edge of the
    // same-report hint — the render where your card just became complete and
    // the enemy card is still empty, i.e. the exact frame where the footer
    // starts saying "Missing: enemy's battle report". Edge-tracked, so the
    // many renders that follow (typing, tab switches, the L/R pill) leave the
    // now-static highlight alone; it re-arms only when the condition drops,
    // so undoing and redoing the same state can ask for attention again. The
    // static border/glow carries the message by itself under
    // prefers-reduced-motion, where the base round's kill-switch strips the
    // animation but not the class.
    const hintOn = model.cards.some((c) => c.sameHint);
    if (hintOn && !app.sameHintPulsed) {
      app.sameHintPulsed = true;
      flashFull(root()?.querySelector('[data-same]'));
    } else if (!hintOn) {
      app.sameHintPulsed = false;
    }
    return;
  }
  if (app.screen === 's3') {
    // UXE-021: the title must match reality - three screenshots in flight
    // under a singular "Reading your screenshot..." was simply wrong. Counted
    // from the same sendableShots() pairs the read itself posts below (parked
    // shots of an inactive type are NOT sent and must not be counted).
    const sendCount = sendableShots(typesNow(), 'you', app.shots.you, app.sameReport).length
      + sendableShots(typesNow(), 'enemy', app.shots.enemy, app.sameReport).length;
    show(renderS3({ shots: sendCount }));
    // UXJ-008: the abort controller + handle live in app/module state so
    // EVERY way of leaving S3 (Cancel button, Escape, ✕, backdrop, back —
    // all of which funnel through render() via leaveScanIfRunning below)
    // tears the scan down: interval cleared (no more per-tick TypeErrors
    // against a torn-down modal), callbacks suppressed (no surprise
    // navigation when the request finally settles), request aborted.
    activeScanAbort = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const handle = driveScan({
      run: () => controller.readAll(
        { you: sendableShots(typesNow(), 'you', app.shots.you, app.sameReport).map((s) => s.bytes),
          enemy: sendableShots(typesNow(), 'enemy', app.shots.enemy, app.sameReport).map((s) => s.bytes) },
        null, {
          // Same-report: ONE report covers both columns, so your chip's flag
          // speaks for both — a stale per-side split must never send
          // asymmetric attestations for a single shared report.
          noBuffsAttested: sameActive() ? { you: app.noBuffs.you, enemy: app.noBuffs.you } : { ...app.noBuffs },
          // L/R: the posted side hint per card (controller.postSideFor).
          columns: effectiveColumns(),
        }),
      onStepChange: (i) => { const r = root(); if (r) applyStepClasses(r, i); },
      // U3D-A2: a slow read now says so in the line that made the promise
      // ("Usually 10–40 seconds"), instead of repeating it for three minutes.
      // Same guard shape as onStepChange — S3 may already be gone (the swap is
      // scheduled, driveScan.cancel clears it, but never trust a live DOM).
      onNote: (text) => { const r = root(); if (r) setScanNote(r, text); },
      onDone: (result) => { app.scanHandle = null; activeScanAbort = null; onReadDone(result); },
      onError: (err) => { app.scanHandle = null; activeScanAbort = null; onReadError(err); },
    });
    app.scanHandle = handle;
    wireS3(root(), { onCancel: () => { goto('s1', { push: false }); } });
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
    // Owner feedback 2026-08-25: an APPLIED no-buffs attestation is said
    // out loud on S5 — informational only, it must never flip the chip
    // (that is what conversionNotices' blocker list is for).
    const infoNotes = [];
    const att = app.lastRead?.attested ?? {};
    if (att.you || att.enemy) {
      infoNotes.push({ kind: 'no-buffs', message:
        'Converted with no special bonuses \u2014 you told us there are none.' });
    }
    app.priorSnapshot = buildSnapshot({
      percentsMe: window.readInputPanelPct ? window.readInputPanelPct('me') : {},
      percentsFoe: window.readInputPanelPct ? window.readInputPanelPct('foe') : {},
      heroesMe: null, heroesFoe: null, statsScoutedChecked: document.getElementById('statsScouted')?.checked ?? false,
    });
    // UX_START_JOURNEY_SPEC.md §3.2: land in the CUSTOM workspace (not the
    // start screen, not quick mode) BEFORE the Stats-tab activation below —
    // #statPanel/its Stats tab are only laid out (non-zero rects) once
    // body.view-work is showing, so this must run first, and the S5 host
    // must land above a VISIBLE panel per the takeover charter's own
    // rect-vs-viewport rule. Optional-chained: must keep working on a host
    // page with no start screen (wosStart absent) exactly like before.
    window.wosStart?.enter('custom', { from: 'reports' });
    // UXJ-010 adjunct 2: #statPanel lives inside the prototype's runtime-
    // tabbed input block — if the user's active tab is Troops Formation (the
    // default), the fill writes .value into a HIDDEN panel (0-size rects)
    // and the whole arrival is invisible. Activate the Stats tab the way a
    // user would (its real tab button; prototype is read-only, there is no
    // API) BEFORE the fill, so applyFillPlan's own scroll targets a panel
    // that is actually laid out, and chip + freshly filled panel +
    // See-who-wins land on screen together.
    // OWNER WALKTHROUGH 2026-09-21 (supersedes the Stats-tab activation above):
    // "after I click ok, it lands on the stats page rather than the troop
    // formation page, which is confusing - please land on the first tab."
    // The stats are already filled in by the read, so the next thing the user
    // does is troops + formation: activate the FIRST input tab the way a user
    // would (wosStart.enter({from:'reports'}) already does this on a page with
    // the start screen; this keeps a host page without it consistent). The
    // fill itself only writes .value, so a hidden Stats panel is fine - what
    // must stay VISIBLE is the arrival cluster, which therefore mounts ABOVE
    // the tab group now (see the host placement below).
    const firstInputTab = document.querySelector('.input-tabs [role="tablist"] [role="tab"]');
    if (firstInputTab && firstInputTab.getAttribute('aria-selected') !== 'true') firstInputTab.click();
    applyFillPlan(plan, { scroll: false });   // the branch anchors its own arrival scroll below
    // Takeover ends HERE, by design (owner escalation 2026-08-15 + the
    // mock's own S5): S5 is the app again — the modal closes (the class
    // toggle at the top of render() already dropped the backdrop) and the
    // Battle-setup chip renders INLINE directly above the panel the fill
    // just populated. #ocrfRoot is removed so nothing lingers at the
    // bottom of the page.
    root()?.remove();
    let host = document.getElementById('ocrfS5Host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'ocrfS5Host';
      // UXJ-010 adjunct (round 4 arrival geometry): the chip must sit
      // DIRECTLY above the panel the fill populated. Mounting it at the
      // entry CTA's spot left it ~1300px above where applyFillPlan scrolls
      // the user (#statPanel), so the arrival moment showed the filled
      // panel but never the Battle-setup chip — violating the charter's
      // "chip + filled form + See-who-wins together in view". At S5-time
      // the prototype's tab consolidation has long run, so anchoring off
      // the live #statPanel is stable (unlike UXJ-001's mount-time anchor,
      // which broke precisely because it ran before that consolidation).
      // 2026-09-21: the arrival lands on the FIRST tab, so the cluster may
      // not live inside the (now hidden) Stats tab panel any more - it sits
      // directly above the whole tab group, visible whichever tab is active.
      const statPanel = document.getElementById('statPanel');
      const tabGroup = statPanel && statPanel.closest('.input-tabs');
      if (tabGroup && tabGroup.parentElement) {
        tabGroup.parentElement.insertBefore(host, tabGroup);
      } else if (statPanel && statPanel.parentElement) {
        statPanel.parentElement.insertBefore(host, statPanel);
      } else if ((launcher.container || launcher.node)?.parentElement) {
        const anchor = launcher.container || launcher.node;
        anchor.parentElement.insertBefore(host, anchor);
      } else {
        document.body.prepend(host);
      }
    }
    host.innerHTML = renderS5({ chipText: computeChipText(tally, notices), complete: tally.clear && !notices.length, states, notices, infoNotes });
    // Anchor the arrival scroll on the HOST — synchronous and INSTANT, as
    // the branch's own scroll intent (applyFillPlan's was suppressed above).
    // Instant, not smooth, deliberately: rAF/timers don't run in throttled
    // or backgrounded tabs, deferred smooth scrolls lose races to async
    // scrollers, and reduced-motion users get the same honest jump — the
    // modal just closed, so an immediate reveal of chip + filled panel is
    // the correct beat, not a second animation.
    // UXE-025 (Gate-1 UX round 1): a bare 12px offset put the host's top
    // edge 12px below the VIEWPORT's top - i.e. underneath the prototype's
    // own STICKY header (.bar, ~58-74px depending on width/view), which
    // sliced the green "All 24 numbers in" banner in half. The banner is the
    // single most reassuring thing in the whole flow, so it may not be the
    // one thing clipped. Measured live rather than hard-coded: the header's
    // height changes with viewport width and with view-start/view-work.
    const stickyHead = document.querySelector('header.bar');
    const headH = stickyHead && getComputedStyle(stickyHead).position === 'sticky'
      ? stickyHead.getBoundingClientRect().height : 0;
    window.scrollTo({ top: Math.max(0, host.getBoundingClientRect().top + window.scrollY - headH - 12), behavior: 'auto' });
    const s5Heading = host.querySelector('h1');
    if (s5Heading) { s5Heading.setAttribute('tabindex', '-1'); s5Heading.focus({ preventScroll: true }); }
    const undoChip = document.getElementById('ocrfUndoChip');
    if (undoChip) undoChip.hidden = !shouldShowUndo(app.priorSnapshot);
    wireS5(host, {
      onToggleChip: onToggleS5Chip, onOpenPicture: openPicture, onReset: () => doReset('s5'),
      onRunForecast: runForecastFromArrival,
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
  if (app.screen === 'e1') {
    show(renderE1(app.e1Variant ?? 'wrong', app.e1Opts ?? {}));
    // UXJ-004: the ONE error-recovery action with a real side effect (POST
    // /shell/billing/checkout) — every other action pick_upload.mjs's
    // e1ActionHtml renders is a plain data-goto the global delegate
    // (D-037/D-039) already handles, nothing extra to wire here.
    const upgradeBtn = document.getElementById('ocrfE1Upgrade');
    if (upgradeBtn) wireE1Upgrade(upgradeBtn);
    return;
  }
}

// --- UXE-028 (Gate-1 UX review round 2, MAJOR) ------------------------------
// The arrival's own "See who wins" (#ocrfS5Run) ran the forecast and showed
// NOTHING for it: measured at 1440x900 the page stayed at scrollY 421 while
// `.forecast` sat at y 2140 (3113 at 390x844) — two to three viewports below
// the fold — and the button never went busy. The cause was this branch
// proxying `#runBtn`, the compact header *Re-run* shortcut, whose own listener
// only starts the run. The page's DECLARED primary action is `#runBottom`, and
// the prototype hangs both of the missing halves off that one — a
// `scrollIntoView` on `.forecast` and a `Simulating…` label — so the arrival
// delegates THERE and inherits both instead of forking run logic (the engine
// call, the payload and formToConfig are untouched; nothing here relabels
// #runBtn, which stays "Re-run" per the owner's constraint and
// screens_setup.test.mjs's guard).
// `doc` is injected purely so node:test can pin the ORDER without a DOM (the
// whole reason the round-2 defect existed was an unpinned choice of button).
export function pagePrimaryRunButton(doc = (typeof document === 'undefined' ? null : document)) {
  if (!doc) return null;
  return doc.getElementById('runBottom') || doc.getElementById('runBtn');
}

// The arrival CTA needs its OWN feedback: the button the thumb is still on
// must say what is happening, not only the one 2000px below it. Busy state is
// OBSERVED from the page's primary button rather than assumed on a timer, so
// the arrival can never claim "Simulating…" for longer (or shorter) than the
// real run — the prototype mirrors #runBtn.disabled onto #runBottom already.
let s5RunBusyObserver = null;
let s5RunIdleHtml = 'See who wins <span aria-hidden="true">&rarr;</span>';

function syncS5RunBusy(target) {
  // Re-looked-up every time, never closed over: S5 can re-render (chip
  // toggle, undo) while a run is still in flight, and a stale node reference
  // would leave the live button stuck on whatever it last said.
  const btn = document.getElementById('ocrfS5Run');
  if (!btn) return;
  const busy = !!(target && target.disabled);
  if (busy === (btn.getAttribute('aria-busy') === 'true') && busy === btn.disabled) return;
  btn.disabled = busy;
  if (busy) {
    btn.setAttribute('aria-busy', 'true');
    btn.textContent = 'Simulating…';
  } else {
    btn.removeAttribute('aria-busy');
    btn.innerHTML = s5RunIdleHtml;   // restored byte-for-byte, arrow span included
  }
}

function watchS5RunBusy() {
  if (s5RunBusyObserver) { s5RunBusyObserver.disconnect(); s5RunBusyObserver = null; }
  const btn = document.getElementById('ocrfS5Run');
  const target = pagePrimaryRunButton();
  if (!btn || !target) return null;
  // Captured from the freshly-rendered markup (renderS5 always emits the idle
  // label) so the restore can never drift from the template.
  if (!btn.disabled) s5RunIdleHtml = btn.innerHTML;
  if (typeof MutationObserver === 'function') {
    s5RunBusyObserver = new MutationObserver(() => syncS5RunBusy(target));
    s5RunBusyObserver.observe(target, { attributes: true, attributeFilter: ['disabled'] });
  }
  syncS5RunBusy(target);
  return target;
}

export function runForecastFromArrival() {
  const target = watchS5RunBusy() || pagePrimaryRunButton();
  if (!target) return;
  target.click();
  // #runBottom's own handler already brings `.forecast` into view. When the
  // page offers only #runBtn (no #runBottom at all) nobody does, so the
  // arrival scrolls itself — instantly under reduced motion, per DESIGN_SYSTEM
  // §2 rule 4's JS-motion check.
  if (target.id !== 'runBottom') {
    const forecast = document.querySelector('.forecast');
    if (forecast) {
      forecast.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
    }
  }
}

// UXJ-004: the same checkout request entry.mjs's wireUpgradeNote already
// makes for the entry-gate 402 — this is the mid-flow twin (a real 402
// occurring DURING a read, after the entry gate already let the user in;
// e.g. a plan lapsing mid-session), wired onto a bare E1 button rather than
// a modal sheet.
function wireE1Upgrade(button) {
  button.addEventListener('click', async () => {
    button.disabled = true;
    button.textContent = 'Opening…';
    try {
      const r = await fetch('/shell/billing/checkout', { method: 'POST', credentials: 'same-origin' });
      if (!r.ok) throw new Error('checkout unavailable');
      const result = await r.json();
      if (result && result.url) { window.location.href = result.url; return; }
      throw new Error('no checkout url');
    } catch (err) {
      button.textContent = 'Try again from the account panel';
    }
  });
}

// Per-side types live in controller.flow (setSideType); both default to
// battle. The model is rebuilt from app state on every render.
function typesNow() { const t = controller.flow.types(); return { you: t.you || 'battle', enemy: t.enemy || 'battle' }; }
function currentModel() {
  return uploadModel({ types: typesNow(), shots: app.shots, attested: app.noBuffs,
    columns: app.columns, sameReport: app.sameReport });
}
function slotDef(side, key) {
  const type = typesNow()[side];
  return (SLOTS[type] || []).find((s) => s.key === key) || null;
}
// "Use your report for the enemy too" is ACTIVE only while both cards are
// battle type: then there is ONE report and ONE attestation surface (your
// None chip speaks for both sides); otherwise attestation is per side.
function sameActive() { const t = typesNow(); return app.sameReport && t.you === 'battle' && t.enemy === 'battle'; }
// The columns the read posts: the enemy's is DERIVED (other column of your
// report) while the box is on.
function effectiveColumns() {
  return sameActive() ? { you: app.columns.you, enemy: otherColumn(app.columns.you) } : { ...app.columns };
}

// Real file input, per SLOT now. The picker input must be ROOTED in the
// document while the OS dialog is open: a detached element can be garbage-
// collected mid-pick, after which the change event simply never fires —
// "I picked a file and nothing happened" (owner report 2026-08-15).
function openPicker(side, slot, remaining) {
  document.querySelector('input[data-ocrf-picker]')?.remove();
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/png,image/jpeg,image/webp';
  input.multiple = remaining > 1;
  input.hidden = true;
  input.setAttribute('data-ocrf-picker', `${side}:${slot}`);
  document.body.appendChild(input);
  input.addEventListener('change', async () => {
    await addFilesToSlot(side, slot, input.files);
    input.remove();
  });
  app.lastSlot = `${side}:${slot}`;   // paste routing: EXPLICIT aim (UXE-008) -
  app.aimExplicit = true;             // the user named this row by pressing its "+ Add"
  input.click();
}

// Shared ingest for every upload channel — picker, drag-drop, paste. Accepts
// only the image types the picker itself accepts; caps at the slot's max
// (extras are ignored, the count badge tells the truth); a call that adds
// nothing changes nothing.
const UPLOAD_IMAGE_TYPES = /^image\/(png|jpe?g|webp)$/;
async function addFilesToSlot(side, slot, fileList) {
  const def = slotDef(side, slot);
  if (!def) return 0;
  const have = app.shots[side].filter((s) => s.slot === slot).length;
  const all = [...(fileList || [])];
  const valid = all.filter((f) => UPLOAD_IMAGE_TYPES.test(f.type));
  const files = valid.slice(0, Math.max(0, def.max - have));
  // QAC-002: every rejection is SAID on the row it happened to — a pulse
  // plus a transient 2-3-word swap of the locator hint (aria-live).
  if (all.length && !valid.length) rejectNote(side, slot, 'Images only');
  else if (valid.length > files.length) rejectNote(side, slot, `${def.max} max`);
  if (!files.length) return 0;
  for (const file of files) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    const id = `${side}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    controller.flow.addShot(side, id);
    let url = null;
    try { url = URL.createObjectURL(file); } catch (err) { /* thumb only */ }
    app.shots[side].push({ id, bytes, url, slot });
  }
  if (def.noneable) {
    // A real upload beats the attestation — for THIS side only. (Under the
    // same-report box the enemy's effective flag mirrors yours at read
    // time; its own stored flag stays untouched — QAC-024.)
    app.noBuffs = { ...app.noBuffs, [side]: false };
  }
  app.lastSlot = `${side}:${slot}`;
  // UXE-008: a file LANDING here is not an aim. Dropping the explicit flag
  // makes pasteTargetSlot advance the armed well to the first EMPTY row, so
  // the next paste can never quietly become a second file on this row.
  app.aimExplicit = false;
  // The recovery/re-entry notice has served its purpose once a screenshot
  // lands — leaving it up reads as stale (L4 closing nit).
  app.s2Notice = null;
  render();
  return files.length;
}

// UXE-003 (Gate-1 UX round 1, Major): a `tryClipboardRead()` helper used to
// run navigator.clipboard.read() from the click-to-arm handler as a
// "progressive enhancement". It is GONE, deliberately, and must not come
// back: it made one intentional paste land twice (the click read the
// clipboard, the user's own Ctrl+V then inserted the same image again) and
// let a click meant to AIM a well silently insert a stale, unrelated
// clipboard image into a battle-report row. Clicking arms; Ctrl/⌘+V pastes
// (the document-level `paste` listener in boot()); "+ Add" and drag-drop are
// the other two channels. Nothing the screen ever promised is lost.

// Orchestrator polish (2026-09-21, item 4): "the only feedback [after a
// paste] is a 40px thumbnail appearing at the far right and the armed well
// jumping a row" — too easy to miss. Reuses the EXISTING full-slot pulse
// (ocrf-slot-flash/ocrf-full-pulse, already used for rejectNote and a full
// row) on the row that just received the image — addFilesToSlot's own
// synchronous render() has already swapped in the fresh thumbnail/advanced
// well by the time this runs, so the pulse lands on the real, current node.
function flashRowLanded(side, slot) {
  flashFull(document.querySelector(`[data-slot-tile="${side}:${slot}"]`));
}

// Orchestrator polish (2026-09-21, item 4): every row is full (or the whole
// grid is attested-none) and the user still pasted — reuses the S2
// notice slot (already aria-live, already the carrier for the recovery/
// re-entry notices) for a short-lived, visible message instead of the
// silent no-op UXG-007's fix used to fall back to. Auto-clears itself
// after 1.8s unless something else has already replaced it.
function pasteAllFull() {
  app.s2Notice = 'All rows are full.';
  render();
  setTimeout(() => {
    if (app.s2Notice === 'All rows are full.') { app.s2Notice = null; render(); }
  }, 1800);
}

// QAC-002: swap the row's locator hint for a short reason, restore after
// 1.6s (or on the next full render, which rebuilds the markup anyway).
function rejectNote(side, slot, msg) {
  const row = document.querySelector(`[data-slot-tile="${side}:${slot}"]`);
  flashFull(row);
  const hint = row ? row.querySelector('.ocrf-req-hint') : null;
  if (!hint) return;
  hint.textContent = msg;
  hint.classList.add('ocrf-req-hint--warn');
  setTimeout(() => {
    if (!hint.isConnected) return;
    hint.textContent = hint.getAttribute('data-hint') || '';
    hint.classList.remove('ocrf-req-hint--warn');
  }, 1600);
}
function flashFull(el) {
  if (!el) return;
  el.classList.remove('ocrf-slot-flash');
  void el.offsetWidth;   // restart the animation on repeat hits
  el.classList.add('ocrf-slot-flash');
  setTimeout(() => el.classList.remove('ocrf-slot-flash'), 600);
}
function dropShot(side, shot) {
  controller.flow.removeShot(side, shot.id);
  if (shot.url) { try { URL.revokeObjectURL(shot.url); } catch (err) { /* gone */ } }
}
function dropSlot(side, slot) {
  const keep = [];
  for (const s of app.shots[side]) {
    if (s.slot === slot) dropShot(side, s); else keep.push(s);
  }
  app.shots[side] = keep;
}
function dropAllShots(side) {
  for (const s of app.shots[side]) dropShot(side, s);
  app.shots[side] = [];
}

// D-035 successor: the delegate's [data-remove-thumb] branch still routes
// here from any legacy markup; slot tiles use wireUpload's own onSlotRemove.
function onRemoveThumb(side, index) {
  const shot = app.shots[side][index];
  if (!shot) return;
  dropShot(side, shot);
  app.shots[side].splice(index, 1);
  render();
}

// Tap on a FULL slot: preview what's there, Replace or Remove — never a
// silent overwrite (research round, 2026-08-29). Same scrim machinery as
// the editor/picture sheets (openScrim/closeScrim own focus + inert).
function openSlotPreview(side, slot) {
  const mine = app.shots[side].filter((s) => s.slot === slot);
  if (!mine.length) return;
  const imgs = mine.map((s) => (s.url ? `<img class="ocrf-slotprev-img" src="${s.url}" alt="">` : '')).join('');
  document.body.insertAdjacentHTML('beforeend', `
<div class="ocrf-modal-scrim" id="ocrfSlotScrim" aria-hidden="false">
  <div class="ocrf-sheet ocrf-slotprev" role="dialog" aria-label="Screenshot">
    <div class="ocrf-slotprev-body">${imgs}</div>
    <div class="ocrf-slotprev-actions">
      <button type="button" class="ocrf-btn-ghost" id="ocrfSlotRemove">Remove</button>
      <button type="button" class="ocrf-btn-primary" id="ocrfSlotReplace">Replace</button>
    </div>
  </div>
</div>`);
  const scrim = document.getElementById('ocrfSlotScrim');
  const closeThis = () => closeScrim(scrim);
  scrim.addEventListener('click', (ev) => { if (ev.target === scrim) closeThis(); });
  scrim.querySelector('#ocrfSlotRemove').addEventListener('click', () => {
    closeThis(); dropSlot(side, slot); render();
  });
  scrim.querySelector('#ocrfSlotReplace').addEventListener('click', () => {
    closeThis(); dropSlot(side, slot); render();
    const def = slotDef(side, slot);
    openPicker(side, slot, def ? def.max : 1);
  });
  openScrim(scrim, scrim.querySelector('#ocrfSlotReplace'));
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
  // UXJ-007 (round 3): the outer S1-S4/E1 modal is ALSO a focus boundary —
  // with role=dialog/aria-modal set but no inert, Tab and .focus() leaked
  // straight into the live background app. Three states now:
  //   a sheet/menu is open  -> keep only the sheet (inerts the modal too —
  //                            round 3 confirmed this nesting was already
  //                            correct when D-040's machinery DID run);
  //   only the modal is open-> keep only #ocrfRoot (background app inert;
  //                            this also fixes the leak closeScrim used to
  //                            reintroduce by clearing ALL inert on sheet
  //                            close while the modal was still up);
  //   nothing is open       -> clear everything.
  const modalLayer = (!open.length && presentationFor(app.screen).modal) ? root() : null;
  const keep = open.length ? open : (modalLayer ? [modalLayer] : []);
  for (const child of document.body.children) {
    // CONTAINS, not just direct-child identity: the editor/picture scrims
    // are appended straight to <body> (child === el matches), but the
    // type-tag menu is inserted as a sibling deep inside #ocrfRoot's own
    // rendered content (child.contains(el) matches instead) — checking
    // identity alone would inert #ocrfRoot itself the moment the menu
    // opened, and `inert` cascades to descendants, silently inerting the
    // very menu it was supposed to keep interactive.
    const keepsSomethingOpen = keep.some((el) => child === el || child.contains(el));
    if (keepsSomethingOpen || !keep.length) child.removeAttribute('inert');
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

// onTypeTag/onS2Continue retired (2026-08-29): the type is a TAB on the
// combined Upload screen (wireUpload's onTab -> flow.pickKind) and Scan is
// gated by uploadModel().canScan — no per-side type menu exists any more.

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
// UXJ-004 fix (EVAL_UX_JOURNEY.md round 1): errorInfo (from pickReadError,
// below) now takes priority over the tally-based read below it — a genuine
// HTTP error during the read (quota, burst, payment lapsed mid-session,
// engine busy, session expired) is NEVER an "unclear/wrong screenshot"
// story, no matter how many fields it happens to leave missing.
export function decideAfterRead(tallyStates, errorInfo = null) {
  if (errorInfo) return { screen: 'e1', variant: 'error', mapped: errorInfo.mapped };
  const total = tallyStates.length;
  const missingCount = tallyStates.filter((s) => s === 'missing').length;
  const readCount = total - missingCount;
  if (missingCount === 0) return { screen: 's4' };
  if (readCount === 0) return { screen: 'e1', variant: 'wrong' };
  return { screen: 'e1', variant: 'partial', readCount, totalCount: total };
}

// UXJ-004 fix: controller.mjs's readAll() resolves with {results, views,
// conversion}, where a failed side's `results[side]` carries {error:true,
// mapped} (error_copy.mjs's mapError output, already computed by
// controller.mjs's readSide) — but decideAfterRead previously only ever saw
// tally states DERIVED from `views`, which is simply null for an errored
// side (nothing to classify), collapsing every HTTP failure into the exact
// same "0 read" shape as a genuinely wrong screenshot. Pure, exported,
// tested on its own (same split as planS2Entry/decideSheetToClose): checks
// 'you' before 'enemy' — deterministic, not an arbitrary pick, since both
// sides hit the same account-level gate within milliseconds of each other
// in virtually every real case (quota/burst/plan/busy are account- or
// server-wide, not per-image) — and returns the first side's mapped copy,
// or null when neither side actually errored. app.lastRead is always set
// before this is consulted (onReadDone, below), so even when only ONE side
// errored, the OTHER side's real read is never lost — S4/S5 still derive
// from the real views for whichever side actually succeeded.
export function pickReadError(results = {}) {
  for (const side of ['you', 'enemy']) {
    const r = results[side];
    if (r && r.error) return { side, mapped: r.mapped };
  }
  return null;
}

function onReadDone(result) {
  app.lastRead = result;
  const errorInfo = pickReadError(result.results);
  const decision = decideAfterRead(flatTallyStates(allFieldStates()), errorInfo);
  if (decision.screen === 's4') { goto('s4', { push: false }); return; }
  app.e1Variant = decision.variant;
  app.e1Opts = decision.variant === 'partial' ? { readCount: decision.readCount, totalCount: decision.totalCount }
    : decision.variant === 'error' ? { mapped: decision.mapped } : {};
  goto('e1', { push: false });
}
// UXJ-004 fix: fires when readAll() ITSELF rejects (e.g. an unexpected throw
// outside readSide's own try/catch, never observed in practice today but
// still reachable in principle) — previously hardcoded 'wrong' regardless
// of `err`, the same fabricated-cause bug decideAfterRead had. mapError(0,
// null) degrades honestly ("Something went wrong on our end...") when
// there's no real status/body to key off, exactly like controller.mjs's own
// readSide does when postPanel itself is missing.
function onReadError(err) {
  app.e1Variant = 'error';
  app.e1Opts = { mapped: mapError(err?.status ?? 0, err?.body ?? null) };
  goto('e1', { push: false });
}
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
export function decideSheetToClose({ pictureOpen, editorOpen, menuOpen, slotOpen = false }) {
  if (slotOpen) return 'slot';   // UXG-001: the slot preview overlays the upload screen — topmost
  if (pictureOpen) return 'picture';
  if (editorOpen) return 'editor';
  if (menuOpen) return 'menu';
  return null;
}
function closeWhicheverIsOpen() {
  const slot = document.getElementById('ocrfSlotScrim');
  const picture = document.getElementById('ocrfPictureScrim');
  const editor = document.getElementById('ocrfEditorScrim');
  const menu = document.querySelector('.ocrf-type-menu');
  const which = decideSheetToClose({
    slotOpen: !!slot && slot.getAttribute('aria-hidden') === 'false',
    pictureOpen: !!picture && picture.getAttribute('aria-hidden') === 'false',
    editorOpen: !!editor && editor.getAttribute('aria-hidden') === 'false',
    menuOpen: !!menu,
  });
  if (which === 'slot') { closeScrim(slot); return true; }
  if (which === 'picture') { closeScrim(picture); return true; }
  if (which === 'editor') { closeScrim(editor); return true; }
  if (which === 'menu') { menu.remove(); syncBackgroundInert(); return true; }
  return false;
}

function boot() {
  controller = createController({ fetchMe, postPanel, storage: window.localStorage });
  document.addEventListener('click', createDelegatedClickHandler({ goto, back, onRemoveThumb, onOpenField: openEditor, onCloseFlow: exitFlow }));
  // D-040: Escape closes whichever sheet/menu is open (mock's own pattern).
  // Takeover fix (2026-08-15): if nothing smaller is open, Escape closes the
  // MODAL flow itself (standard dialog semantics; non-destructive — shots
  // and read results live in `app` and survive re-entry). S5 is inline (not
  // modal), so Escape does nothing there.
  document.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Escape') return;
    if (closeWhicheverIsOpen()) return;
    if (presentationFor(app.screen).modal) exitFlow();
  });
  // Backdrop click (the fixed #ocrfRoot itself, never its card) also exits.
  document.addEventListener('click', (ev) => {
    if (ev.target && ev.target.id === 'ocrfRoot' && presentationFor(app.screen).modal) exitFlow();
  });

  // Owner feedback 2026-08-25: uploads take DRAG-DROP and PASTE, not just
  // the OS picker. All three channels funnel into addFilesToSlot — the drop
  // target is the slot TILE, the paste target is pasteTargetSlot's pick.
  const tileOf = (ev) => (ev.target && typeof ev.target.closest === 'function')
    ? ev.target.closest('[data-slot-tile]') : null;
  document.addEventListener('dragover', (ev) => {
    if (app.screen !== 's1') return;
    ev.preventDefault();                     // required for drop to fire; also
    const tile = tileOf(ev);                 // stops the browser navigating away
    // Dragging OVER a row is an explicit aim (UXE-008) - the pointer is
    // literally on it - so it may hold a partially-filled multi-file row.
    if (tile) { tile.classList.add('ocrf-drag-over'); app.lastSlot = tile.dataset.slotTile; app.aimExplicit = true; }
  });
  document.addEventListener('dragleave', (ev) => { tileOf(ev)?.classList.remove('ocrf-drag-over'); });
  document.addEventListener('drop', (ev) => {
    if (app.screen !== 's1') return;
    ev.preventDefault();
    const tile = tileOf(ev);
    if (!tile) return;
    tile.classList.remove('ocrf-drag-over');
    const [side, key] = tile.dataset.slotTile.split(':');
    addFilesToSlot(side, key, ev.dataTransfer && ev.dataTransfer.files);
  });
  document.addEventListener('paste', (ev) => {
    if (app.screen !== 's1') return;
    // §3.3 (owner: "on mobile you should not be allowed to do that") — a
    // touch device that somehow still delivers a paste event (a Bluetooth
    // keyboard, an OS-level paste gesture) must be treated exactly like it
    // never happened. Re-checked here, not just at render time: hover/
    // pointer capability can change between renders (a 2-in-1 undocking).
    if (!canPaste()) return;
    const files = [...((ev.clipboardData && ev.clipboardData.files) || [])];
    if (!files.length) return;
    ev.preventDefault();
    const ref = pasteTargetSlot(currentModel(), app.lastSlot, app.aimExplicit);
    // Orchestrator polish (2026-09-21, item 4): UXG-007's original target,
    // `.ocrf-summary`, is dead markup left over from the retired slot-grid
    // round (2026-08-29) — flashFull() on a selector that matches nothing
    // is a silent no-op, so a paste against a totally full grid previously
    // gave the user NO feedback at all. Real, visible feedback now: the
    // same transient-notice slot the S2 recovery/re-entry notices already
    // use (aria-live, auto-clears).
    if (!ref) { pasteAllFull(); return; }
    const [side, key] = ref.split(':');
    addFilesToSlot(side, key, files).then((added) => { if (added > 0) flashRowLanded(side, key); });
  });
  // Real-screenshot samples degrade to the hand-drawn mini-panels when their
  // images can't load (a promoted bundle strips game-IP raster art —
  // PRODUCTION_CRITERIA F1). Error events don't bubble; capture phase, same
  // idiom as overlay.js's page-asset fallback.
  document.addEventListener('error', (ev) => {
    const img = ev.target;
    if (!(img instanceof HTMLImageElement) || !img.classList.contains('ocrf-sample-img')) return;
    // Slot tiles (2026-08-29 grid): the dimmed sample-crop icon simply goes
    // away — the dashed tile + label carry the state on their own (the tiny
    // tile can't host the hand-drawn mini-panels; renderSampleFallback stays
    // for any legacy .ocrf-sample container below).
    if (img.classList.contains('ocrf-slot-sample')) { img.remove(); return; }
    // Requirement rows: a broken sample degrades to the row's declared drawn
    // stand-in (Troops -> mini-panel) or simply disappears — never a broken
    // image icon next to the instruction.
    if (img.classList.contains('ocrf-req-sample')) {
      const fig = img.closest('.ocrf-req-fig');
      const drawn = fig && fig.getAttribute('data-drawn');
      if (fig && drawn) fig.innerHTML = renderSampleFallback(drawn); else img.remove();
      return;
    }
    const sample = img.closest('.ocrf-sample');
    const type = sample?.getAttribute('data-sample');
    if (sample && type) { sample.outerHTML = renderSampleFallback(type); return; }
  }, true);

  const mounted = mountEntry({ root: document });   // module-level `launcher` (see its own declaration above render())
  if (!mounted) return;
  launcher = { mode: mounted.mode, node: mounted.node, container: mounted.container, mini: mounted.mini, lastUsed: null };

  function onNeedsUpgrade() {
    const wrap = document.createElement('div'); wrap.innerHTML = renderUpgradeNote();
    const node = wrap.firstElementChild; document.body.appendChild(node);
    node.removeAttribute('inert'); node.setAttribute('aria-hidden', 'false');
    wireUpgradeNote(node, {
      checkout: () => fetch('/shell/billing/checkout', { method: 'POST', credentials: 'same-origin' })
        .then((r) => { if (!r.ok) throw new Error('checkout unavailable'); return r.json(); }),
    });
  }

  // Shared by both possible launchers (start card / mini launcher) and the
  // one legacy CTA — `source` (§3.1's "whichever launcher opened the flow")
  // is all that differs between them; everything else is the exact original
  // onProceed behavior.
  function onLauncherProceed(source) {
    launcher.lastUsed = source;
    if (launcher.mode === 'legacy' && launcher.container) launcher.container.hidden = true;
    // UXJ-009: a re-entry with carried-over shots must SAY so on S2
    // (the exit was non-destructive by design; the silence was the bug).
    // Staged in its own slot and consumed exactly once by the s2
    // branch's navOpts block — the recovery notice outranks it there,
    // and the clear-on-new-upload rule applies to both the same way.
    app.reentryNotice = reentryNotice({
      shotsYou: controller.flow.shots('you'),
      shotsEnemy: controller.flow.shots('enemy'),
    });
    // Reuse an existing #ocrfRoot (e.g. after Back-to-entry then proceeding
    // again) rather than appending a second one with a duplicate id.
    const stack = root() || document.body.appendChild(Object.assign(document.createElement('div'), { id: 'ocrfRoot' }));
    // Takeover polish: flag the NEXT show() (S1's) as the true "opening"
    // moment — see pendingEnterAnimation's own comment. Set here (not
    // inside goto/show generally) because this is the one and only call
    // site that starts a fresh flow open.
    pendingEnterAnimation = true;
    goto('s1');
  }

  if (launcher.node) wireEntry(launcher.node, { checkAccess, onProceed: () => onLauncherProceed('start'), onNeedsUpgrade });
  if (launcher.mini) wireEntry(launcher.mini, { checkAccess, onProceed: () => onLauncherProceed('mini'), onNeedsUpgrade });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}
