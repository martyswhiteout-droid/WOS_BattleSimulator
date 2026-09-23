// UX_START_JOURNEY_SPEC.md §3.1: the shell now has THREE possible launchers
// for the OCR flow, all running the same decideEntryAction path:
//   1. the START-SCREEN card (#startSlotReports, contract §1.1) — the
//      prototype's own start screen, shown when it exists on the host page;
//   2. the compact MODE-BAR launcher (#modeBarSlot) mounted alongside it,
//      shown while the workspace (not the start screen) is up;
//   3. the LEGACY hero CTA at the old `.input`-section anchor, for a host
//      page with no start screen at all (bare prototype before the start-
//      screen round, or any page that never gets it).
// "Fill from screenshots" / "Fastest way. No typing." are retired everywhere
// (owner 2026-09-20): the card's words are now "Forecast from battle
// reports" / "Upload screenshots. We read the stats for you." in every mode.
export function renderEntryCard() {
  // Owner 2026-08-29: the CTA is the page's PRIMARY action — hero-sized,
  // full width, impossible to miss. Legacy anchor only (no start screen on
  // the host page); the retired copy is gone, the hero treatment stays.
  return `
<section class="ocrf-entry ocrf-entry--hero" id="ocrfEntry">
  <button type="button" class="ocrf-cta ocrf-cta--hero" id="ocrfCtaScreenshots">
    <span class="ocrf-cta-emoji" aria-hidden="true">\u{1F4F7}</span>
    <span class="ocrf-cta-main">Forecast from battle reports</span>
    <span class="ocrf-cta-note">Upload screenshots. We read the stats for you.</span>
  </button>
</section>`.trim();
}

// Original inline art (contract §1.1: viewBox 0 0 48 48, currentColor
// strokes, 2.5px round joins/caps, no fills except currentColor at low
// opacity, no emoji, no game art) — a report sheet with a few stat lines and
// a small scan/viewfinder corner peeking off its bottom-right edge.
const REPORT_SCAN_ICON = `<svg viewBox="0 0 48 48" aria-hidden="true">
  <rect x="9" y="6" width="24" height="34" rx="3" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round"/>
  <line x1="15" y1="15" x2="27" y2="15" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="15" y1="22" x2="27" y2="22" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="15" y1="29" x2="22" y2="29" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M30 29 v9 h9" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

// contract §1.1: shell card fills #startSlotReports's Card-1 slot, reusing
// the prototype's own `.start-card`/`.start-card--primary` structure and
// classes VERBATIM (never restyled here — wos-ui-styling owns that chrome;
// this file only ever supplies its own icon markup and copy).
export function renderStartCard() {
  return `
<button type="button" class="start-card start-card--primary" data-start="reports" id="ocrfCtaScreenshots">
  <span class="start-card-icon" aria-hidden="true">${REPORT_SCAN_ICON}</span>
  <span class="start-card-tag">Fastest</span>
  <span class="start-card-title">Forecast from battle reports</span>
  <span class="start-card-line">Upload screenshots. We read the stats for you.</span>
  <span class="start-card-go" aria-hidden="true">→</span>
</button>`.trim();
}

// contract §3.1: the compact launcher mounted into #modeBarSlot once the
// user is already in the workspace (quick/custom) — same decideEntryAction
// path as the start card, a small report icon + short label. Reuses
// `.modebar-btn` (never restyled — the shell may only style
// `.ocrf-launch-mini`'s own icon spacing, per the build spec).
const MINI_REPORT_ICON = `<svg viewBox="0 0 48 48" aria-hidden="true">
  <rect x="10" y="8" width="20" height="28" rx="2.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/>
  <line x1="15" y1="17" x2="25" y2="17" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
  <line x1="15" y1="24" x2="25" y2="24" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
</svg>`;

// UXE-022 (Gate-1 UX round 1): the feature had three names - the start
// card's "Forecast from battle reports", this launcher's "Fill from battle
// reports", and the dialog's own type-neutral h1 "Screenshots" (which is
// owner-approved and STAYS: the dialog also takes scout reports and City
// Stats). The launcher now carries the feature's short name, so the mode bar
// and the start card agree, and it fits the bar better at 390px too.
export function renderMiniLauncher() {
  return `<button type="button" class="modebar-btn ocrf-launch-mini" id="ocrfCtaReportsMini">`
    + `<span class="ocrf-launch-mini-icon" aria-hidden="true">${MINI_REPORT_ICON}</span>`
    + `Battle reports</button>`;
}

export function renderUpgradeNote() {
  return `
<div class="ocrf-modal-scrim" id="ocrfUpgradeScrim" aria-hidden="true" inert>
  <div class="ocrf-sheet" role="dialog" aria-modal="true" aria-labelledby="ocrfUpgradeTitle">
    <h2 id="ocrfUpgradeTitle" tabindex="-1">This needs a paid plan</h2>
    <p>Reading screenshots is a paid feature. Typing the numbers in yourself is always free.</p>
    <div class="ocrf-sheet-actions">
      <button type="button" class="ocrf-btn-ghost" id="ocrfUpgradeClose">Type it in myself</button>
      <button type="button" class="ocrf-btn-primary" id="ocrfUpgradeCta">See plans</button>
    </div>
  </div>
</div>`.trim();
}

export async function decideEntryAction(checkAccess) {
  const access = await checkAccess();
  return access.allowed ? 'proceed' : 'upgrade';
}

// UXJ-001 fix (EVAL_UX_JOURNEY.md round 1): the old anchor — whatever
// `.iblock` CURRENTLY wraps #statPanel — is only stable at the instant this
// runs. mountEntry() executes from ocr_flow.js's boot(), a `type="module"`
// script that (per HTML module-script semantics) finishes BEFORE
// DOMContentLoaded fires — i.e. before prototype/index.html's own
// `initInputTabs()` (registered ON DOMContentLoaded) folds the Troops
// Formation/Stats/Buffs `.iblock`s into one `.tabgroup.input-tabs`, removing
// the small Stats `.iblock` this used to anchor on. The card itself is never
// touched by that later reflow (it isn't one of the `.iblock`s that gets
// removed), so it just stays wherever it landed — which turns out to be
// AFTER the entire consolidated tabgroup once the dust settles: below the
// whole manual form, on both desktop and mobile, instead of above it.
// Anchoring on the FORM SECTION itself (`.input`, never renamed or removed
// by initInputTabs()) and always inserting as its first child is stable no
// matter what mutates inside that section afterwards. Exported/tested on its
// own — same split as the pure decisions in ocr_flow.js (planS2Entry,
// decideAfterRead): the actual bug WAS this decision, not the DOM mutation.
// Legacy-anchor path only (§3.1 branch 3) — the contract path (branches 1-2)
// never calls this at all.
export function findEntrySection(statPanel) {
  return statPanel.closest('.input') || statPanel.parentElement;
}

// UX_START_JOURNEY_SPEC.md §1.1/§3.1: mountEntry() picks ONE of three shapes
// depending on what the host page offers, and reports which so ocr_flow.js's
// boot()/focus-return logic (which launcher(s) exist, which one a click came
// from) never has to re-derive it from the DOM:
//   { mode:'contract', node:<button#ocrfCtaScreenshots>, container:null,
//     mini:<button#ocrfCtaReportsMini>|null }
//   { mode:'legacy', node:<section#ocrfEntry>, container:<the same section>,
//     mini:null }
//   null — no #statPanel either; the OCR feature has nowhere to live on this
//     page at all (defensive; should not happen on the real app).
// `node` is always what the caller inserted/filled (never re-derived by a
// second DOM query), so this stays provable against the minimal fake DOM
// tests below use (no real `document`, no jsdom, per this repo's own
// discipline — see tests/screens_entry.test.mjs's UXJ-001 fakes).
export function mountEntry({ root = document } = {}) {
  const slot = root.getElementById('startSlotReports');
  if (slot) {
    slot.innerHTML = renderStartCard();
    slot.hidden = false;
    const node = slot.querySelector('#ocrfCtaScreenshots');
    let mini = null;
    const modeBarSlot = root.getElementById('modeBarSlot');
    if (modeBarSlot) {
      modeBarSlot.innerHTML = renderMiniLauncher();
      mini = modeBarSlot.querySelector('#ocrfCtaReportsMini');
    }
    return { mode: 'contract', node, container: null, mini };
  }
  // No start screen on this host page (bare prototype, or any page that
  // never gets one) — legacy hero CTA at the old anchor, new copy.
  const statPanel = root.getElementById('statPanel');
  if (!statPanel) return null;
  const section = findEntrySection(statPanel);
  const wrap = root.createElement('div');
  wrap.innerHTML = renderEntryCard();
  const node = wrap.firstElementChild;
  section.insertBefore(node, section.firstElementChild);
  return { mode: 'legacy', node, container: node, mini: null };
}

// Wires ONE launcher button (the start card, the mini launcher, or the
// legacy hero CTA — mountEntry() above always hands the caller the actual
// clickable button, never a container to re-query), so this can stay a
// single implementation for all three shapes.
export function wireEntry(button, { checkAccess, onProceed, onNeedsUpgrade }) {
  button.addEventListener('click', async () => {
    const action = await decideEntryAction(checkAccess);
    if (action === 'proceed') onProceed();
    else onNeedsUpgrade();
  });
}

export function wireUpgradeNote(node, { checkout } = {}) {
  const close = node.querySelector('#ocrfUpgradeClose');
  const cta = node.querySelector('#ocrfUpgradeCta');
  close.addEventListener('click', () => node.remove());
  cta.addEventListener('click', async () => {
    cta.disabled = true;
    cta.textContent = 'Opening…';
    try {
      const result = await (checkout ? checkout() : Promise.reject(new Error('no checkout configured')));
      if (result && result.url) { window.location.href = result.url; return; }
      throw new Error('no checkout url');
    } catch (err) {
      cta.textContent = 'Try again from the account panel';
    }
  });
}
