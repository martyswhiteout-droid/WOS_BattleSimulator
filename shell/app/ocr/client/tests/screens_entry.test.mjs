import test from 'node:test';
import assert from 'node:assert/strict';
import {
  renderEntryCard, renderStartCard, renderMiniLauncher, renderUpgradeNote, decideEntryAction, findEntrySection, mountEntry,
} from '../screens/entry.mjs';

// UX_START_JOURNEY_SPEC.md §3.1 (owner 2026-09-20): "Fill from screenshots"
// and "Fastest way. No typing." are retired everywhere — the legacy hero CTA
// (no start screen on the host page) gets the SAME new copy as the
// start-screen card: "Forecast from battle reports" / "Upload screenshots.
// We read the stats for you."
test('legacy entry card: retired copy is gone, new copy in place, never says "picture"', () => {
  const html = renderEntryCard();
  assert.doesNotMatch(html, /Fill from screenshots/);
  assert.doesNotMatch(html, /Fastest way\. No typing\./);
  assert.match(html, /Forecast from battle reports/);
  assert.match(html, /Upload screenshots\. We read the stats for you\./);
  assert.match(html, /id="ocrfCtaScreenshots"/);
  assert.doesNotMatch(html, /\bpicture\b/i);   // terminology rule: never "picture"
});

// --- contract §1.1/§3.1: the start-screen card and the mode-bar mini launcher ---

test('renderStartCard: reuses the prototype\'s own start-card structure/classes verbatim, original SVG icon (no emoji, no game art), same "Forecast from battle reports" copy', () => {
  const html = renderStartCard();
  assert.match(html, /class="start-card start-card--primary"/);
  assert.match(html, /id="ocrfCtaScreenshots"/);
  assert.match(html, /<span class="start-card-icon" aria-hidden="true"><svg viewBox="0 0 48 48"/);
  assert.match(html, /<span class="start-card-tag">Fastest<\/span>/);
  assert.match(html, /<span class="start-card-title">Forecast from battle reports<\/span>/);
  assert.match(html, /<span class="start-card-line">Upload screenshots\. We read the stats for you\.<\/span>/);
  assert.match(html, /<span class="start-card-go" aria-hidden="true">/);
  assert.doesNotMatch(html, /Fill from screenshots|Fastest way\. No typing\./);
  // no emoji / game-art shortcuts — an svg with only currentColor strokes
  assert.doesNotMatch(html, /[\u{1F300}-\u{1FAFF}]/u);
  assert.match(html, /stroke="currentColor"/);
});

test('renderMiniLauncher: compact modebar-btn, own icon-spacing class, short label, never the retired copy', () => {
  const html = renderMiniLauncher();
  assert.match(html, /<button type="button" class="modebar-btn ocrf-launch-mini" id="ocrfCtaReportsMini">/);
  // UXE-022 (Gate-1 UX round 1): the launcher carries the feature's SHORT
  // name so the mode bar, the start card and the dialog stop giving one
  // feature three names. The old "Fill from battle reports" is retired.
  assert.match(html, /Battle reports<\/button>/);
  assert.doesNotMatch(html, /Fill from battle reports/);
  assert.doesNotMatch(html, /Fill from screenshots/);
  assert.doesNotMatch(html, /[\u{1F300}-\u{1FAFF}]/u);
});

test('upgrade note never says OCR and matches the error-copy 402 body exactly', () => {
  const html = renderUpgradeNote();
  assert.match(html, /This needs a paid plan/);
  assert.match(html, /Reading screenshots is a paid feature\. Typing the numbers in yourself is always free\./);
  assert.doesNotMatch(html, /\bocr\b/i);
});

test('decideEntryAction proceeds for a paid plan and asks to upgrade otherwise', async () => {
  assert.equal(await decideEntryAction(async () => ({ allowed: true, plan: 'pro' })), 'proceed');
  assert.equal(await decideEntryAction(async () => ({ allowed: false, plan: 'free' })), 'upgrade');
  assert.equal(await decideEntryAction(async () => ({ allowed: false, plan: null, reachable: false })), 'upgrade');
});

// --- mountEntry: contract mode (start screen present) vs legacy fallback ---
// (§3.1) — minimal fakes, same discipline as UXJ-001's below: no real DOM
// under node:test, just enough surface to prove which branch ran and what
// it did. querySelector is faked by checking the id landed in the innerHTML
// string mountEntry itself set, close enough to prove wiring without a
// real HTML parser.
function fakeSlot() {
  return {
    _html: '',
    hidden: true,
    set innerHTML(v) { this._html = v; },
    get innerHTML() { return this._html; },
    querySelector(sel) {
      const m = sel.match(/^#([\w-]+)$/);
      return m && this._html.includes(`id="${m[1]}"`) ? { id: m[1] } : null;
    },
  };
}

test('mountEntry: contract mode fills #startSlotReports (Card-1, unhidden) and #modeBarSlot (mini launcher) when both exist', () => {
  const slot = fakeSlot();
  const modeBarSlot = fakeSlot();
  const fakeRoot = { getElementById: (id) => (id === 'startSlotReports' ? slot : id === 'modeBarSlot' ? modeBarSlot : null) };
  const result = mountEntry({ root: fakeRoot });
  assert.equal(result.mode, 'contract');
  assert.equal(result.container, null);   // nothing to hide/restore in contract mode
  assert.equal(slot.hidden, false);       // contract §1.1: "the shell fills it and removes hidden"
  assert.match(slot.innerHTML, /class="start-card start-card--primary"/);
  assert.match(modeBarSlot.innerHTML, /id="ocrfCtaReportsMini"/);
  assert.deepEqual(result.node, { id: 'ocrfCtaScreenshots' });
  assert.deepEqual(result.mini, { id: 'ocrfCtaReportsMini' });
});

test('mountEntry: contract mode works with #startSlotReports alone (no #modeBarSlot yet, e.g. before the workspace ever mounts one) — mini stays null, never throws', () => {
  const slot = fakeSlot();
  const fakeRoot = { getElementById: (id) => (id === 'startSlotReports' ? slot : null) };
  const result = mountEntry({ root: fakeRoot });
  assert.equal(result.mode, 'contract');
  assert.equal(result.mini, null);
});

test('mountEntry: legacy fallback when there is no #startSlotReports at all — mode "legacy", node and container are the same hide/restore target', () => {
  const inputSection = { className: 'input', kids: [], get firstElementChild() { return this.kids[0] ?? null; },
    insertBefore(node, ref) { const idx = ref ? this.kids.indexOf(ref) : -1; this.kids.splice(idx === -1 ? this.kids.length : idx, 0, node); } };
  const statPanel = { closest: (sel) => (sel === '.input' ? inputSection : null) };
  const legacyNode = { tag: 'ocrfEntry', hidden: true };
  const fakeRoot = {
    getElementById: (id) => (id === 'statPanel' ? statPanel : null),
    createElement: () => ({ _html: '', set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; }, firstElementChild: legacyNode }),
  };
  const result = mountEntry({ root: fakeRoot });
  assert.equal(result.mode, 'legacy');
  assert.equal(result.node, legacyNode);
  assert.equal(result.container, legacyNode);
  assert.equal(result.mini, null);
});

test('mountEntry: returns null when the host page has neither a start screen nor #statPanel at all (feature has nowhere to live — defensive)', () => {
  assert.equal(mountEntry({ root: { getElementById: () => null } }), null);
});

// --- UXJ-001 (EVAL_UX_JOURNEY.md round 1): the S0 CTA rendered BELOW the
// entire manual form on both desktop and mobile. Root cause: mountEntry()
// anchored on `statPanel.closest('.iblock')`, which resolves at MOUNT TIME
// (before prototype/index.html's DOMContentLoaded-driven initInputTabs()
// consolidates Troops Formation/Stats/Buffs into one .tabgroup and removes
// the small Stats .iblock) — a placement that only looks "above the form"
// until that later reflow strands the card between the new tabgroup and the
// hero-selection block. findEntrySection() must resolve the whole .input
// section instead, which initInputTabs() never renames or removes. ---

test('UXJ-001 probe: findEntrySection anchors on the whole .input form section, not whatever .iblock currently wraps #statPanel', () => {
  // Mirrors the real page's structure AT MOUNT TIME: #statPanel is still
  // inside its own small .iblock (initInputTabs() hasn't run yet), itself
  // inside the big .input section that also holds sides-head/troops-
  // formation/etc. The old `.closest('.iblock')` anchor stopped at the small
  // wrapper — exactly the bug. closest('.input') must resolve the OUTER
  // section instead, skipping right past the small wrapper.
  const inputSection = { className: 'input' };
  const statIblock = { className: 'iblock', parentElement: inputSection };
  const statPanel = {
    closest(selector) {
      if (selector === '.input') return inputSection;
      if (selector === '.iblock') return statIblock;
      return null;
    },
  };
  assert.equal(findEntrySection(statPanel), inputSection);
});

test('UXJ-001 probe: findEntrySection falls back to the immediate parent if #statPanel has no .input ancestor at all (defensive; should not happen on the real page)', () => {
  const parent = { tag: 'parent' };
  const statPanel = { closest: () => null, parentElement: parent };
  assert.equal(findEntrySection(statPanel), parent);
});

test('UXJ-001: mountEntry inserts the card as the FIRST child of the form section — above sides-head, troops formation, everything — using a fake DOM sufficient to prove insertion order', () => {
  // A minimal fake standing in for `document`/the real elements: just enough
  // surface (getElementById, closest, createElement/innerHTML/
  // firstElementChild, insertBefore) to prove WHERE the node lands, without
  // a real DOM (none is available under node:test in this repo).
  function fakeContainer(initialChildren) {
    const kids = [...initialChildren];
    return {
      kids,
      get firstElementChild() { return kids[0] ?? null; },
      insertBefore(node, ref) {
        const idx = ref ? kids.indexOf(ref) : -1;
        kids.splice(idx === -1 ? kids.length : idx, 0, node);
        return node;
      },
    };
  }
  const sidesHead = { tag: 'sides-head' };
  const troopsFormationIblock = { tag: 'troops-formation-iblock' };
  const section = fakeContainer([sidesHead, troopsFormationIblock]);
  const statPanel = { closest: (sel) => (sel === '.input' ? section : null) };
  const fakeNode = { tag: 'ocrfEntry' };
  const fakeRoot = {
    getElementById: (id) => (id === 'statPanel' ? statPanel : null),
    createElement: () => ({ _html: '', set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; }, firstElementChild: fakeNode }),
  };
  mountEntry({ root: fakeRoot });
  assert.deepEqual(section.kids, [fakeNode, sidesHead, troopsFormationIblock]);
});
