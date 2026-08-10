// shell/app/ocr/client/error_copy.mjs — HTTP status/body -> honest, jargon-free
// user copy. The server's own body.message (e.g. limits.py's "Screenshot OCR
// is a Pro feature. Upgrade to use it.") is written for logs/API consumers and
// contains banned jargon (the literal word "OCR") — never passed through.
// mapError always writes fresh copy keyed only on status/body.error.
export function mapError(status, body) {
  const code = body && body.error;

  if (status === 402) {
    return {
      heading: 'This needs a paid plan',
      body: 'Reading screenshots is a paid feature. Typing the numbers in yourself is always free.',
      cta: 'upgrade',
    };
  }
  if (status === 413 || status === 415) {
    return {
      heading: "That screenshot didn't come through",
      body: 'Try a smaller screenshot, saved as a plain PNG or JPEG.',
      cta: 'retake',
    };
  }
  if (status === 429 && code === 'burst') {
    return {
      heading: 'Slow down a little',
      body: 'Give it a few seconds, then try again.',
      cta: 'slow_down',
    };
  }
  if (status === 429) {
    return {
      heading: "That's today's limit",
      body: "You've used up today's screenshot reads. They come back at midnight. You can still type the numbers in.",
      cta: 'wait',
    };
  }
  if (status === 503) {
    return {
      heading: 'The reader is busy right now',
      body: "It's busy right now. Try again in a moment, or type the numbers in yourself.",
      cta: 'retry_or_type',
    };
  }
  if (status === 401) {
    return {
      heading: 'Please sign in',
      body: 'Sign in to read screenshots.',
      cta: 'sign_in',
    };
  }
  // 411/422/anything else the UI should never trigger by construction, plus a real
  // network failure (status 0, no body) — degrade the same honest way as 503 rather
  // than surface an internal code.
  return {
    heading: "That didn't work",
    body: "Something went wrong on our end. Try again, or type the numbers in yourself.",
    cta: 'retry_or_type',
  };
}
