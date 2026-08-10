import test from 'node:test';
import assert from 'node:assert/strict';
import { renderEntryCard, renderUpgradeNote, decideEntryAction } from '../screens/entry.mjs';

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
