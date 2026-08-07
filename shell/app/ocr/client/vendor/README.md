# Vendored client OCR runtime

This directory pins Tesseract.js 7.0.0, its matching 7.0.0 WASM core, and
the English trained-data package at 1.0.0. PNG.js 7.0.0 supplies deterministic
pixel access for the Node adapter's red/green classification. They are vendored
so screenshot reading does not depend on a CDN or a mutable package-registry
response.

Regenerate the lockfile and runtime files from this directory with:

```powershell
npm install --ignore-scripts --omit=dev
```

The nested `.gitignore` keeps npm's documentation, tests, inline-WASM wrappers,
and the larger language model out of the vendored runtime. Standalone baseline,
SIMD, and relaxed-SIMD cores are retained because Tesseract.js selects exactly
one supported core at runtime without a network request.
