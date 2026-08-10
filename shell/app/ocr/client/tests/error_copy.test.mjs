import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { mapError } from '../error_copy.mjs';

const FIX = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/overlay_ui/api_samples.json', import.meta.url), 'utf8'));

const BANNED = /\b(ocr|parse|parsing|confidence|payment_required|quota_exhausted|auth_required|ocr_engine_unavailable|unsupported_image_type|body_too_large|invalid_side|invalid_panel|invalid_file_count|burst)\b/i;
const STATUS_CODE_LEAK = /\b(401|402|411|413|415|422|429|503)\b/;

function allCopyText(result) {
  return `${result.heading} ${result.body}`;
}

test('402 payment_required maps to an honest upgrade note, never the word OCR', () => {
  const d = FIX.denials['402'];
  const result = mapError(d.status, d.body);
  assert.equal(result.cta, 'upgrade');
  assert.doesNotMatch(allCopyText(result), BANNED);
  assert.doesNotMatch(allCopyText(result), STATUS_CODE_LEAK);
});

test('413 and 415 both map to retake guidance', () => {
  for (const code of ['413', '415']) {
    const d = FIX.denials[code];
    const result = mapError(d.status, d.body);
    assert.equal(result.cta, 'retake');
  }
});

test('429 quota_exhausted and 429 burst map to DIFFERENT, distinguishing copy', () => {
  const quota = mapError(FIX.denials['429_quota'].status, FIX.denials['429_quota'].body);
  const burst = mapError(FIX.denials['429_burst'].status, FIX.denials['429_burst'].body);
  assert.equal(quota.cta, 'wait');
  assert.equal(burst.cta, 'slow_down');
  assert.notEqual(quota.heading, burst.heading);
});

test('503 maps to "the reader is busy" plus a manual-typing path', () => {
  const d = FIX.denials['503'];
  const result = mapError(d.status, d.body);
  assert.equal(result.cta, 'retry_or_type');
  assert.match(result.body, /busy/i);
});

test('401 maps to a sign-in prompt', () => {
  const result = mapError(FIX.denials['401'].status, FIX.denials['401'].body);
  assert.equal(result.cta, 'sign_in');
});

test('every real denial shape maps to copy with no banned jargon and no leaked status code', () => {
  for (const [name, d] of Object.entries(FIX.denials)) {
    const result = mapError(d.status, d.body);
    assert.ok(result.heading && result.body && result.cta, name);
    assert.doesNotMatch(allCopyText(result), BANNED, name);
    assert.doesNotMatch(allCopyText(result), STATUS_CODE_LEAK, name);
  }
});

test('unrecognized status/network failure falls back to a generic honest retry-or-type message', () => {
  const result = mapError(0, null);   // 0 = fetch threw (offline, DNS, etc.), no HTTP response at all
  assert.equal(result.cta, 'retry_or_type');
  assert.doesNotMatch(allCopyText(result), BANNED);
});
