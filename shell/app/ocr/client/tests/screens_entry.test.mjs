import test from 'node:test';
import assert from 'node:assert/strict';
import { renderEntryCard, renderUpgradeNote, decideEntryAction, findEntrySection, mountEntry } from '../screens/entry.mjs';

test('entry card reuses the mock copy verbatim', () => {
  const html = renderEntryCard();
  assert.match(html, /Fill from screenshots/);
  assert.match(html, /Fastest way\. No typing\./);
  assert.match(html, /id="ocrfCtaScreenshots"/);
  assert.doesNotMatch(html, /\bpicture\b/i);   // terminology rule: never "picture"
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
