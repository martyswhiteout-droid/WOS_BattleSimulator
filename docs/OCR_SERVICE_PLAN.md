# OCR_SERVICE_PLAN.md — hosted OCR for in-game stat panels

**Status:** proposal, awaiting owner approval · **Date:** 2026-08-05 · **Author:** infra/ML architecture pass
**Owner decision (Martin, 2026-08-06): the vision-LLM tier is DEFERRED to a future build.** v1 ships client-WASM → server-RapidOCR only; fields neither engine can read fall back to manual typing in the confirm screen. Every mention of the LLM tier below is to be read as future-phase material.
**Owner decision D1 (Martin, 2026-08-06): free-tier users get NO OCR — manual input only.** OCR (client-side included) is a paid-tier feature; the "give free tier client OCR" recommendation in the TL;DR below is REJECTED. Gate the feature by plan server-side (entitlements), not just by hiding UI.
**Owner exploration (2026-08-06 late): Gemini API free tier as the v1 engine** — Gemini 3 Flash free tier = 1,500 vision requests/day per project ($0), which covers beta scale. Findings, caveats (shared quota pool, free-tier data-use/human-review terms, EEA restriction) and the 10-minute setup guide: `docs/OCR_GEMINI_FREE_TIER.md`. If adopted, ladder becomes Gemini-free → RapidOCR → manual for beta; the deterministic client path stays the scale endgame. This narrows (does not reverse) the earlier "LLM deferred" decision: deferred-for-cost no longer applies at $0, the deterministic pipeline/validators stay mandatory either way.
**Scope:** auto-filling the simulator's numeric inputs from in-game **stat-panel screenshots**.
**Not in scope:** the existing `shell/app/ocr/` **battle-report** ingestion path (vision-LLM, v2 schema) — that stays as-is. This plan adds a *second, deterministic* OCR capability beside it.

---

## TL;DR

**Recommendation: client-side WASM OCR as the primary engine, running in the user's browser, with all assets vendored and served same-origin from the shell.** Marginal cost per scan is **exactly $0** at every scale, the image never leaves the device, and the same image always produces the same output.

**Fallback chain (in order):**

1. **Client-side WASM OCR** — `tesseract.js` v7, English, with a digit-whitelisted second pass. Free for *all* users including free tier. $0/scan.
2. **Server-side RapidOCR** (PP-OCRv5/v6 mobile ONNX, CPU) on the existing VPS — for devices where WASM is unavailable/OOMs, and as a second opinion on low-confidence fields. $0/scan marginal; costs VPS CPU only. Metered + concurrency-capped.
3. ~~**Vision-LLM** (the existing Anthropic/Gemini client) — last resort, **explicit user action only** ("Still wrong? Use AI read"), counted against the paid OCR quota.~~ **DEFERRED to a future build (owner, 2026-08-06).** In v1, what tiers 1–2 cannot read is typed by the user in the confirm screen.

Every path terminates in the **same deterministic parser** and the **same human-confirm loop**. OCR never silently feeds the engine.

**Cost line for the recommendation (per month, all-in marginal):**

| Scans/month | Primary (client WASM) | + server fallback (~5%) | + LLM fallback (~1%, Gemini Flash-Lite) | **Total** |
|---|---|---|---|---|
| 1,000 | $0.00 | $0.00 | $0.004 | **~$0.00** |
| 10,000 | $0.00 | $0.00 | $0.04 | **~$0.04** |
| 100,000 | $0.00 | $0.00 | $0.40 | **~$0.40** |

For comparison at 100k scans: Google Cloud Vision **$148.50**, Azure Read **$150.00**, AWS Textract **$150.00**, Claude Haiku 4.5 **$375.60**. Sources in §3.

**Top 3 risks:** (1) silent digit corruption feeding a confidently-wrong prediction; (2) a game UI update changing labels/layout; (3) client payload size + device diversity on mobile data. Mitigations in §9.

**Product flag for the owner:** current quota says free = **0 OCR**, because LLM OCR was assumed and it costs real money. Client-side OCR costs **nothing per scan**. Recommendation: **give free-tier users unlimited client-side panel OCR.** It is the single best conversion surface in the product — it removes the most painful part of onboarding (typing 12–16 numbers by hand) at zero marginal cost, and the 5 sims/day cap still does the monetising.

---

## 1. Problem statement

Users currently hand-type 12–16 numeric fields per side into the simulator. They want to screenshot the in-game panel instead. Three panel types, v1 English only:

| # | Panel | Layout | Example rows |
|---|---|---|---|
| 1 | **Bonus Overview** (own city) | single column, label → value, unsigned | `Troops' Attack 748.49%`, `Infantry Health 1223.08%`, `Deployment Capacity 188,900` |
| 2 | **Scout report → Stat Bonuses** | single column, **signed** percentages | `Infantry Attack +4491.6%`, `Enemy Defense Penalty (Pet Skill) -10.0%` |
| 3 | **Battle report → Stat Bonuses** | **two columns**, green left = mine, red right = enemy, label centred | `+4859.0%  Infantry Attack  +694.3%`; plus a `Special Bonuses` sub-list, e.g. `Defender Troops' Attack +15.00% / +0.00%` |

Input characteristics that make this **much easier than general OCR**: clean flat UI, sans-serif, high contrast, no skew, no perspective, no handwriting, fixed label vocabulary, and a value grammar that is fully regex-describable. This is closer to "reading a rendered spreadsheet" than to document OCR.

Users may upload 1–3 screenshots per side; long panels may need 2 overlapping shots (dedup on the overlap).

### Binding constraints

| Constraint | Source | Implication |
|---|---|---|
| High-volume path must be **non-LLM** | Owner, verbatim: *"cannot rely on LLM all the time as the token cost will be huge"* | LLM is a capped last resort, never the default |
| **Deterministic** — same image → same output | House engineering standard; the whole product is a deterministic predictor | Rules out VLMs for the primary path |
| **Never fabricate** | `COMPASS` invariant 8; `shell/ARCHITECTURE.md` boundary rule 4 | An unreadable field is **absent**, never zero, never guessed |
| `prototype/` is **READ-ONLY** | `shell/ARCHITECTURE.md` boundary rule 1 | Client code ships via the overlay, not by editing `index.html` |
| Prototype must stay **self-contained** (no CDN/external fonts) | `CLAUDE.md` rule 5; enforced by `wos_sim/predictor/tests/test_ui_style_guard.py` | Any vendored lib must be same-origin — see §2 |
| VPS is small (~2 vCPU) and already fragile under load | `shell/EVAL_ROUND_1.md` F4: *no body-size limit and no execution cap — a single free-tier user can wedge the box* | Server-side CPU OCR must be concurrency-capped, and F4 is a **prerequisite** |

---

## 2. The self-containment problem, and why it evaporates

At first glance the strict rule in `CLAUDE.md` §5 blocks client-side OCR: the style guard's `URL_RE` rejects *any* `https?://` in `prototype/index.html`, and `FORBIDDEN_TOKENS` explicitly lists `jsdelivr`, `unpkg.com`, `cdnjs`. A 3.3 MB WASM binary obviously cannot be inlined into a 266 KB single-file page either.

**It resolves cleanly, because the shell already has the right seam.** `shell/app/overlay/middleware.py` injects `<script defer src="/shell/overlay.js">` into the served HTML at response time — the file on disk is never touched. So:

- OCR client code and assets live under **`shell/app/ocr/client/`**, served at `/shell/ocr/assets/*`, **same-origin**, no CDN.
- `prototype/index.html` is **not modified**, so the style guard never sees any of it. No baseline regeneration, no `!important` budget impact, no palette change.
- Boundary rule 1 is satisfied by construction.

This is the single most important structural finding in this document: **the overlay pattern makes client-side OCR compatible with the prototype's self-containment rule at zero cost.** The rule was never about "no JavaScript" — it was about no *third-party origins*, and we serve everything ourselves.

Caveat to design around: `onnxruntime-web` multi-threading needs `SharedArrayBuffer`, which needs the page to be **cross-origin isolated** via COOP/COEP headers ([web.dev/articles/coop-coep](https://web.dev/articles/coop-coep)). Enabling COOP/COEP site-wide would **break Clerk and Stripe embedded components**. Therefore: run client OCR **single-threaded**, or confine it to a dedicated cross-origin-isolated iframe. Do not set COOP/COEP on the main document. (`tesseract.js` does not require it.)

---

## 3. Options matrix

### (a) Client-side WASM OCR in the browser

**tesseract.js** — v**7.0.0**, released **2025-12-15** ([releases](https://github.com/naptha/tesseract.js/releases), [npm](https://registry.npmjs.org/tesseract.js/latest)). v7 adds a `relaxedsimd` build, **15–35% faster** than v6. v5 already cut file sizes 54% (English) and memory 47% vs v4 ([README](https://cdn.jsdelivr.net/npm/tesseract.js@7.0.0/README.md)).

Vendored payload (exact bytes from [jsdelivr package data](https://data.jsdelivr.com/v1/packages/npm/tesseract.js-core@7.0.0)):

| Asset | Size |
|---|---|
| `tesseract-core-simd-lstm.wasm` (one variant loads per session) | 2,857,601 B (~2.72 MB) |
| `eng.traineddata` — `tessdata_fast` variant ([GitHub](https://github.com/tesseract-ocr/tessdata_fast/blob/main/eng.traineddata)) | ~3.92 MB |
| worker + JS glue | ~0.5 MB |
| **Total one-time download** | **~7–8 MB** |

Self-hosting is first-class: `createWorker(lang, oem, {workerPath, corePath, langPath})` — `corePath` must point at a **directory** containing all core variants ([local-installation docs](https://github.com/naptha/tesseract.js/blob/master/docs/local-installation.md)). Default `langPath` hits jsDelivr; **we must override it.** The old `tessdata.projectnaptha.com` CDN is deprecated ([naptha/tessdata](https://github.com/naptha/tessdata/blob/gh-pages/README.md)) — do not point at it.

**`@paddleocr/paddleocr-js`** — the notable 2026 development: an **official** browser SDK inside the PaddleOCR monorepo ([GitHub](https://github.com/PaddlePaddle/PaddleOCR/tree/main/paddleocr-js)), first published **2026-04-02**, latest **v0.4.2 on 2026-06-11**, 8 releases in ~2 months ([npm](https://registry.npmjs.org/@paddleocr/paddleocr-js)). Built on `onnxruntime-web` + OpenCV.js; supports PP-OCRv5 and PP-OCRv6 mobile; assets self-hostable via `textDetectionModelAsset` / `wasmPaths`. Payload is much heavier: `ort-wasm-simd-threaded.wasm` alone is **12.9 MB** ([jsdelivr](https://data.jsdelivr.com/v1/packages/npm/onnxruntime-web@1.27.0)), plus det ~4.94 MB and rec ~17.2 MB ([HF PP-OCRv5_mobile_det](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det), [_mobile_rec](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec)) ⇒ **~35–40 MB**. The older `@paddlejs-models/ocr` is stale (last publish 2023-11-16) — do not use.

**Browser-native `TextDetector`** (Shape Detection API) is **not viable**: Chrome status is still *"In developer trial"* i.e. flag-gated, with milestones dating to Chrome 74 (2019) and no progression ([chromestatus 5644087665360896](https://chromestatus.com/api/v0/features/5644087665360896)). The spec itself split text detection into a non-normative document because it is *"not considered stable enough across computing platforms"* ([WICG](https://wicg.github.io/shape-detection-api/text.html)). Never shipped in Firefox/Safari. Rule it out.

| | Pros | Cons |
|---|---|---|
| | **$0/scan at any scale.** Image never leaves device — strongest privacy story, and it moots the entire "never persist" question. Zero VPS CPU. Deterministic. Works offline. Makes free-tier OCR viable. | One-time 8 MB (tesseract) / 35–40 MB (paddle) download. Device-dependent latency. Old/low-RAM phones may fail. Tesseract needs real preprocessing on screen text. |

**Accuracy expectation:** Tesseract targets ≥300 DPI and has a known trap where canvas/video sources report *"Invalid resolution 0 dpi. Using 70 instead"*, silently degrading accuracy ([tessdoc](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html), [issue #393](https://github.com/naptha/tesseract.js/issues/393)). PSM choice matters a lot — PSM 6 for a uniform block, PSM 7/13 for a single line; the default assumes a full page ([PSM guide](https://pyimagesearch.com/2021/11/15/tesseract-page-segmentation-modes-psms-explained-how-to-improve-your-ocr-accuracy/)). Documented character confusions **0/O/o, 1/l, 8/B, 5/S** ([tesseract #3144](https://github.com/tesseract-ocr/tesseract/issues/3144)). There is a long-standing unshipped request for a built-in "screenshot mode" — **you are expected to preprocess yourself** ([tesseract #929](https://github.com/tesseract-ocr/tesseract/issues/929)).

> **Honest gap:** no primary-source benchmark exists for OCR of clean flat-UI game-screenshot text. General comparisons cite PaddleOCR ≈0.94 F1 vs Tesseract ≈0.80, but those come from secondary marketing/comparison articles on scene-text datasets, **not** a paper or repo — treat as directional only. This is precisely why §8 Phase 0 exists: **measure on our own screenshots before committing.**
> The digit confusions above are the reason for the **digit-whitelist second pass** in §4 — restricting the charset to `0123456789.,%+-` makes `0/O`, `1/l`, `8/B` and `5/S` *mechanically impossible*, because the letters are not in the alphabet. This is a decisive advantage for a payload that is almost entirely digits, and `tesseract.js` supports it (`tessedit_char_whitelist`) whereas PaddleOCR-family engines do not expose an equivalent.

**Cost:** **$0 / $0 / $0** at 1k / 10k / 100k scans. Only cost is asset bandwidth, which Cloudflare's free CDN caches at the edge with `immutable` headers; 100k scans is *not* 100k downloads (browser cache + edge cache).

### (b) Self-hosted server OCR on the existing VPS

**RapidOCR** has unified into a single `rapidocr` package, now **v3.9.2 (2026-07-21)**, wheel **27.3 MB** ([PyPI](https://pypi.org/project/rapidocr/)). Install is `pip install rapidocr onnxruntime` ([README](https://github.com/RapidAI/RapidOCR)). Default models as of Aug 2026 are **PP-OCRv6** det/rec "small" ([releases](https://github.com/RapidAI/RapidOCR/releases)). The legacy `rapidocr-onnxruntime` package is stale (last release 2025-01-17) — do not pin it.

**Docker weight is the deciding factor between RapidOCR and PaddleOCR:** the `paddlepaddle` CPU wheel alone is **194.8 MB** ([PyPI](https://pypi.org/project/paddlepaddle/#files)), versus `rapidocr` 27.3 MB + `onnxruntime` 19.2 MB ([PyPI onnxruntime](https://pypi.org/project/onnxruntime/#files)) ≈ **46 MB**. A real published RapidOCR service image is **121 MB compressed** on its slim tag ([Docker Hub volador/rapidocr](https://hub.docker.com/r/volador/rapidocr/tags)), consistent with `python:3.12-slim` (~42–46 MB, [Docker Hub](https://hub.docker.com/layers/library/python/3.12-slim/images/sha256-f0c6bc1ab7b1ab270bbb612a31a67a7938d6171183ddce9121f04984ab3df44e)) plus those wheels. **Use RapidOCR, not PaddleOCR, server-side.**

**Latency — be realistic.** Two mutually-consistent official sources: PaddleOCR's own docs give PP-OCRv5 `mobile_min_736` at **1.75 s/image** (200 images, Intel Xeon Gold 6271C, [paddleocr.ai](http://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html), corroborated by [Baidu's HF blog](https://huggingface.co/blog/baidu/ppocrv5)); the PP-OCRv6 paper reports PP-OCRv5 mobile at **0.80 s/image** and PP-OCRv6 tiny at **0.32 s** end-to-end on Xeon 8350C ([arXiv 2606.13108](https://arxiv.org/html/2606.13108v1)). A widely-repeated "~90 ms" figure could not be traced to its cited source — **treat sub-100 ms claims as unverified.** These are datacenter Xeons; a 2 vCPU KVM slice will be *slower*. Budget **~1–2 s per image**, and note that end-to-end latency scales with the *number of detected text regions* — a dense stat panel is many short fields, i.e. at or above the average.

Aggregate CPU is fine; **peaks are the risk**. 100k scans × 1.5 s = 41.7 core-hours/month ≈ **5.7% of one core averaged over a 730-hour month**. Trivial on average. But 20 concurrent uploads on a 2 vCPU box, alongside sim runs, is exactly the wedge described in `EVAL_ROUND_1.md` F4. Mitigation: a dedicated OCR semaphore of **2**, a hard per-request timeout, and a 429 when the queue is full.

> Per-worker RAM for a PP-OCRv5-mobile det+rec pipeline: **NOT FOUND** in any authoritative source. Measure it in Phase 0 before sizing the container; do not assume.

| Pros | Cons |
|---|---|
| $0/scan marginal. Deterministic. Small client payload (just the upload). CJK nearly free (§8 Phase 2). Code sits beside the existing LLM OCR, reusing its validator and guards. | Image **leaves the device** — privacy + retention policy now matter. +120–160 MB Docker image. 1–2 s latency. Competes for the same 2 vCPU as the sim engine. Requires F4 to land first. |

**Cost:** **$0 / $0 / $0** marginal (VPS is a fixed cost already paid).

### (c) Cloud OCR APIs

| Provider | Price | Free tier | Limits |
|---|---|---|---|
| **Google Cloud Vision** `TEXT_DETECTION` / `DOCUMENT_TEXT_DETECTION` | **$1.50/1k** units (1,001–5M/mo); $0.60/1k above 5M | first **1,000 units/mo free** | 20 MB image, 10 MB JSON request, 75 MP. JPEG/PNG/GIF/BMP/WEBP/RAW/ICO/PDF/TIFF ([pricing](https://cloud.google.com/vision/pricing), [supported files](https://cloud.google.com/vision/docs/supported-files)) |
| **Azure AI Vision "Read"** (Image Analysis Group 2) | **$1.50/1k** transactions (0–1M/mo); $0.60/1k above ([Retail Prices API](https://prices.azure.com/api/retail/prices), meter *Image Analysis Group 2 Transactions*) | **F0: 5,000/mo**, 20 transactions/min | <500 MB paid / <4 MB free; 50×50 to 10,000×10,000 px ([OCR overview](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)) |
| **AWS Textract** `DetectDocumentText` | **$1.50/1k** pages (first 1M/mo); $0.60/1k above | 1,000 pages/mo, **new accounts, first 3 months only** | **10 MB sync**, ≤10,000 px/side, JPEG/PNG/PDF/TIFF ([pricing](https://aws.amazon.com/textract/pricing/), [limits](https://docs.aws.amazon.com/textract/latest/dg/limits-document.html)) |
| **Mistral OCR** | **$4/1k pages** ([mistral.ai/pricing/api](https://mistral.ai/pricing/api/)) | — | Batch discount referenced but exact OCR batch rate NOT FOUND on the official page |
| **OCR.space** | PRO **$30/mo** for 300k requests (5 MB cap) | 25,000/mo free (500/day/IP, 1 MB cap) ([ocr.space/ocrapi](https://ocr.space/ocrapi)) | Engine 3 has a smaller separate quota |

**Cost at our scales** (Vision/Azure-S1/Textract all price identically at $1.50/1k):

| Scans/mo | Google Vision | Azure Read (S1) | AWS Textract |
|---|---|---|---|
| 1,000 | **$0.00** (free tier) | $1.50 | $1.50 |
| 10,000 | **$13.50** | $15.00 | $15.00 |
| 100,000 | **$148.50** | $150.00 | $150.00 |

| Pros | Cons |
|---|---|
| Best-in-class raw accuracy, zero infra, zero client payload. | **Real per-scan cost that scales linearly** — directly contradicts the owner's constraint. Image leaves the device to a third party (new privacy/DPA surface). External dependency + network latency. Vendor lock-in. Still needs the same §4 parser — cloud OCR returns *text*, not *fields*. |

**Verdict: rejected as primary.** At 100k scans, $148.50/mo against a $7.99/mo product is a margin killer. Note the multiplier too: users upload **1–3 screenshots per side**, so a full two-side setup is 2–6 billable images, not one.

### (d) Cloudflare Workers AI / edge OCR

**There is no real OCR engine at the Cloudflare edge in 2026.** The Workers AI model catalog has no OCR task category ([models](https://developers.cloudflare.com/workers-ai/models/)); the closest is `@cf/moondream/moondream3.1-9B-A2B`, whose model page names OCR as a capability, priced **$0.30/M input, $1.00/M output** tokens ([model page](https://developers.cloudflare.com/workers-ai/models/moondream3.1-9B-A2B/)). That is a **VLM, not a deterministic OCR engine** — same non-determinism objection as (e), just cheaper. `toMarkdown` Markdown Conversion is a document utility that delegates images to those same vision models ([docs](https://developers.cloudflare.com/workers-ai/features/markdown-conversion/)). Workers AI bills in **Neurons at $0.011/1k**, with **10,000 Neurons/day free** on both Free and Paid plans ([pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)).

Also disqualifying for a compute-heavy path: Workers **Free plan allows 10 ms CPU per invocation** (Paid defaults to 30 s); request body limit is 100 MB on Free/Pro ([limits](https://developers.cloudflare.com/workers/platform/limits/)).

**Verdict: rejected.** Cloudflare stays in the architecture as CDN/TLS/WAF — which is where it earns its keep here (edge-caching the vendored WASM assets for free).

### (e) Vision-LLM — last resort only

Claude **Haiku 4.5**: **$1/MTok input, $5/MTok output** ([pricing](https://platform.claude.com/docs/en/about-claude/pricing)). Image tokens are **patch-based**, not the old `w×h/750` heuristic: `tokens = ⌈w/28⌉ × ⌈h/28⌉`, capped by a per-tier resize (Standard tier incl. Haiku 4.5: long edge 1568 px / 1568 visual tokens max) ([vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)). Max 10 MB base64 per image, 8000×8000 px.

For one 1080×2400 screenshot + ~300 prompt tokens + ~400 output tokens:

```
Haiku 4.5:  downscale 2400→1568 (×0.6533) ⇒ 706×1568
            image tokens = ⌈706/28⌉ × ⌈1568/28⌉ = 26 × 56 = 1,456
            input  = (1,456 + 300) × $1/1M  = $0.001756
            output = 400 × $5/1M            = $0.002000
            TOTAL  = $0.003756/scan
```
Pre-resizing client-side to 1568 px changes **nothing** on cost (Claude does the identical downscale internally) — it only reduces upload size/latency. The naive `w×h/750` rule would have said 3,456 tokens, ~2.4× too high.

```
Gemini 2.5 Flash-Lite ($0.10/MTok in, $0.40/MTok out — cheapest active vision model,
  https://ai.google.dev/gemini-api/docs/pricing):
            crop_unit = ⌊min(1080,2400)/1.5⌋ = 720
            tiles = ⌈1080/720⌉ × ⌈2400/720⌉ = 2 × 4 = 8 ⇒ 8 × 258 = 2,064 image tokens
            input  = (2,064 + 300) × $0.10/1M = $0.0002364
            output = 400 × $0.40/1M          = $0.0001600
            TOTAL  = $0.0003964/scan
```
(Gemini 3.x switches to a flat `media_resolution` allocation — 1120 tokens/image at the default "high" — [media-resolution docs](https://ai.google.dev/gemini-api/docs/media-resolution). Gemini 3.1 Flash-Lite works out to ~$0.000955/scan.)

| Scans/mo | Claude Haiku 4.5 | Gemini 2.5 Flash-Lite |
|---|---|---|
| 1,000 | $3.76 | $0.40 |
| 10,000 | $37.56 | $3.96 |
| 100,000 | **$375.60** | $39.64 |

**Verdict: last-resort fallback only.** Beyond cost, a VLM is **non-deterministic** — the same screenshot can yield different numbers on two calls. For a product whose entire value is numeric precision, that is disqualifying as a default path. It stays for the genuinely hard residue (a novel panel, a weird device) behind an explicit user tap.

---

## 4. Recommended architecture

```
┌─ BROWSER (overlay-injected, same-origin assets) ─────────────────────┐
│  upload/crop widget → preprocess (canvas) → tesseract.js v7 (WASM)   │
│                            ↓                                         │
│                    deterministic parser (§5)  ← the real work        │
│                            ↓                                         │
│         fields + per-field confidence → editable inputs (§7)         │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ only if: WASM unavailable, OOM,
                               │ or user taps "Try harder" on low-conf
                               ▼
        POST /shell/ocr/panel  →  RapidOCR (PP-OCRv5/v6 mobile, ONNX CPU)
                               →  SAME parser (shared spec, §5)
                               ▼
                     user taps "Use AI read" (quota-capped)
                               ▼
        existing shell/app/ocr vision client (Anthropic → Gemini)
                               →  SAME validation schema, never auto-applied
```

### Why this one

| Constraint | How it's met |
|---|---|
| Near-zero marginal cost | Primary path is **$0/scan by construction** — no API, no server CPU |
| Deterministic | Fixed WASM binary + fixed model file + pure-function parser. Pin asset hashes; a model swap is a versioned engine change, recorded as `engine_version` in the output |
| Privacy | **The image never leaves the device** on the primary path. No upload, no storage, no retention policy, no DPA. Strictly better than any hosted option |
| Fits the stack | Ships through the existing `OverlayMiddleware` seam; static assets edge-cached free by Cloudflare; fallbacks live beside the existing `shell/app/ocr/` |
| Free tier viable | Zero marginal cost means free users can have it. See the product flag in the TL;DR |
| VPS protection | Primary path uses **zero server CPU**. The CPU-bound fallback is opt-in, semaphore-capped, and expected to serve <5% of scans |

### Why tesseract.js over `@paddleocr/paddleocr-js` for v1

1. **The digit-whitelist trick is decisive.** Our payload is ~95% digits, `.`, `,`, `%`, `+`, `−`. Constraining the value pass to that charset makes the four documented Tesseract confusions (`0/O`, `1/l`, `8/B`, `5/S`) *structurally impossible*. PaddleOCR-family engines do not expose an equivalent charset constraint.
2. **Payload: ~8 MB vs ~35–40 MB.** On mobile data that is the difference between a shrug and an abandon.
3. **Maturity:** v7.0.0 with a multi-year release history, vs `@paddleocr/paddleocr-js` v**0.4.2**, four months old.
4. **No COOP/COEP entanglement** with Clerk/Stripe (§2).

**But this is a Phase-0-testable claim, not an article of faith.** Phase 0 benchmarks both against real screenshots. If PaddleOCR-js clears the bar and tesseract.js does not, swap the primary — the parser, the confirm loop, and the integration are engine-agnostic by design. PaddleOCR also wins outright for CJK later (§8 Phase 2), where its PP-OCRv5 mobile rec model covers zh + en + ja in **one 17.2 MB model**.

---

## 5. The deterministic parsing layer

**This is where OCR engines fail alone, and where most of the engineering value sits.** Raw OCR returns text and boxes; we need typed, validated, side-attributed fields. The parser is a pure function — `(ocr_tokens, panel_type, image_rgb) → fields[]` — identically specified for all three engines, and unit-testable without any OCR at all.

### 5.1 Canonical label lexicon

Versioned data, not code: **`shell/app/ocr/lexicon/en.json`**, carrying a `lexicon_version` echoed in every response.

- **Core grid (12):** {`Infantry`, `Lancer`, `Marksman`} × {`Attack`, `Defense`, `Lethality`, `Health`}
- **Army-wide (4):** `Troops' Attack`, `Troops' Defense`, `Troops' Lethality`, `Troops' Health`
- **Special/unsigned:** `Deployment Capacity`, `Enemy Defense Penalty (Pet Skill)`, `Defender Troops' Attack`, and the rest of the `Special Bonuses` sub-list
- Each entry: `{key, display, aliases[], panels[], value_type: percent|integer, signed: bool, range: [min,max]}`

**Normalization before matching** (order matters):
1. Unicode NFKC
2. **Apostrophe unification** — `'` `'` `` ` `` `´` `'` → `'`. *Non-optional:* `Troops'` is the single most common label in the set and OCR emits both `U+2019` and `U+0027`.
3. Collapse internal whitespace; strip trailing `:`; casefold
4. Strip a trailing parenthetical **only** when the base still matches uniquely (keeps `Enemy Defense Penalty (Pet Skill)` distinct from `Enemy Defense Penalty`)

**Fuzzy match** — normalized Damerau-Levenshtein similarity against the panel-restricted candidate set (restricting by panel type cuts collisions substantially):

| Ratio | Action |
|---|---|
| ≥ 0.92 | accept, label confidence 1.0 |
| 0.80 – 0.92 | accept, label confidence = ratio, field capped at **MED** |
| < 0.80 | **unknown row** — drop the row, emit a `warnings[]` entry, increment the unknown-label telemetry counter (§9 risk 2). **Never** snap to the nearest label |

### 5.2 Value grammar

```
PCT   ^([+\-−–]?)(\d{1,3}(?:,\d{3})*|\d+)(?:[.,](\d{1,2}))?\s*%$
INT   ^(\d{1,3}(?:,\d{3})*|\d+)$
```
- Accept `−` (U+2212) and `–` (en dash) as minus — OCR emits both for the in-game glyph.
- **Thousands-separator check:** every comma must be followed by *exactly* three digits. `1,22.08` fails ⇒ the decimal point was misread ⇒ LOW confidence, never repaired silently.
- **Decimal-place check:** >2 dp means a spurious separator ⇒ LOW.
- Ambiguous `.` vs `,` as the decimal mark is resolved by the 3-digit rule, then by the ≤2 dp rule; if still ambiguous ⇒ LOW.

### 5.3 Row assembly

Cluster tokens by vertical centre: tokens `a`, `b` share a row iff `|y_c(a) − y_c(b)| < 0.6 × median_glyph_height`. Sort rows by `y`, tokens within a row by `x`. Median glyph height is measured from the token boxes themselves, so it is resolution-independent.

### 5.4 Two-column split (battle report) — colour is the primary signal

Colours are stable UI constants, which makes this far more robust than geometry alone.

1. Sample the **median HSV** of the high-saturation pixels inside each value's bbox, on the **original RGB buffer** (never the binarized one — §6 keeps both).
2. Classify: hue ≈ 90–160° with `S > 0.30` ⇒ **mine (green)**; hue < 15° or > 345° with `S > 0.30` ⇒ **enemy (red)**; else **unknown**.
3. Independently classify by **geometry**: value bbox centre left of the label bbox centre ⇒ mine; right ⇒ enemy.
4. **Require both signals to agree.** Agreement ⇒ HIGH eligible. Disagreement or `unknown` colour ⇒ force **LOW** and require explicit confirmation. Never break the tie automatically — mixing up "mine" and "enemy" is the single worst silent failure this feature can produce.

**Preferred implementation (cleanest):** build a green-mask and a red-mask image in preprocessing and OCR each separately (§6). Column assignment then falls out for free and pairing ambiguity disappears entirely.

### 5.5 Digit-whitelist second pass

After row assembly, re-run OCR on **each value bbox only** (a tiny crop, so it is cheap) with `tessedit_char_whitelist=0123456789.,%+-` and `PSM 7` (single line).

- Whitelisted read **==** first-pass read ⇒ eligible for **HIGH**.
- Reads **differ** ⇒ **LOW**, and surface *both* candidates in the confirm UI.

This converts the engine's most dangerous failure mode — a plausible-looking wrong digit — into a visible disagreement. It is the highest-leverage single item in this document.

### 5.6 Overlap dedup across multiple screenshots

1. Parse each screenshot independently into `rows[]`.
2. Find the stitch point via the **longest common subsequence of canonical label sequences** — not y-coordinates, which are meaningless across images.
3. For a label present in both: values **agree** ⇒ keep one, promote confidence one tier (independent corroboration). Values **disagree** ⇒ keep **neither** silently; surface both with their source crops and force the user to choose. (Never-fabricate.)
4. Emit `duplicate_conflicts[]` in the response.

### 5.7 Confidence scoring

```
field_confidence = min( ocr_value_confidence,
                        label_match_ratio,
                        column_agreement ? 1.0 : 0.5,
                        whitelist_agreement ? 1.0 : 0.5,
                        range_plausible ? 1.0 : 0.6 )
```
Tiers: **HIGH** ≥ 0.95 · **MED** 0.80–0.95 · **LOW** < 0.80. `min` (not product) is deliberate — one bad signal should dominate rather than be averaged away.

### 5.8 Validation schema

| Check | Rule | On failure |
|---|---|---|
| Percent range | `0 ≤ v ≤ 6000` | LOW, never auto-accept |
| Sign presence | scout/battle ⇒ signed; Bonus Overview ⇒ unsigned | tier cap MED |
| Decimals | ≤ 2 dp | LOW |
| Completeness | report which of the 12 class×stat fields are present | `unreadable_fields[]` — **absent, not zero** |
| Duplicate labels within one image | a canonical key may appear once per column | LOW on all copies |
| Soft sanity | same-class Attack vs Defense within ~3× | flag only, never reject |

### 5.9 Cross-panel arithmetic check (the strongest available signal)

`docs/STAT_PANELS_FORMULA.md` (CONFIRMED 2026-08-05, zero fudge, worst residual 0.054 pp) establishes a **deterministic mapping between all three panel types** — the same account state viewed through different inclusion sets plus a multiplicative special-bonus fold. Its worked example is literally our example data: Infantry Attack **658.25%** (Bonus Overview) ⇄ **+4491.6%** (scouted) ⇄ **+4859.0%** (battle report).

This is a far stronger validator than any OCR confidence score, because it is **arithmetic on the extracted numbers themselves**:

- **Within one panel:** derived rows must reconcile with their components per that document's aggregation law. A single misread digit breaks the identity by orders of magnitude more than display rounding.
- **Across two panels** (user uploads e.g. a Bonus Overview *and* a scout report for the same account): apply the confirmed transform and compare. Agreement to within display rounding (~0.06 pp) ⇒ **promote every reconciled field to HIGH**. Disagreement ⇒ **demote all fields in the disagreeing rows to LOW** and surface both readings.

Treat it as a post-parse pass: `reconcile(fields, panel_type, other_panels[]) → confidence adjustments`. It never repairs a value — it only promotes or demotes confidence, keeping the never-fabricate rule intact. Phase 1 should implement the within-panel form; the cross-panel form lands with multi-screenshot support in Phase 2. **Owner note:** this makes the OCR feature meaningfully more trustworthy than OCR alone would be, and it is essentially free — the law is already derived and verified.

---

## 6. Preprocessing pipeline

All client-side on `<canvas>`; the server fallback mirrors it with OpenCV.

1. **Decode at natural resolution.** Read `naturalWidth/Height`, ignore CSS size.
2. **Optional user crop** — draggable box, with the framing hint from §7. Cropping away the status bar/notch removes a whole class of failure.
3. **Keep two buffers** for the rest of the pipeline: **(i) original RGB** — used only for colour-channel column detection (§5.4) and the confirm-UI thumbnails; **(ii) working grayscale** — used for OCR. Binarizing before colour sampling destroys the green/red signal; this is the most common way to get §5.4 wrong.
4. **Scale normalization.** Upscale (bicubic) so median glyph height lands in **32–40 px**. Heuristic: if image width < 1000 px, ×2; then if the first OCR pass reports median line height < 20 px, upscale and retry once.
5. **Explicit DPI.** Set the DPI hint rather than letting canvas sources trigger *"Invalid resolution 0 dpi. Using 70 instead"* ([tesseract.js #393](https://github.com/naptha/tesseract.js/issues/393)).
6. **Polarity detection.** WoS panels are dark-themed. Measure mean luminance; if dark-background, invert so text is dark-on-light.
7. **Binarize** — Otsu global threshold (the UI is flat and evenly lit; adaptive/Sauvola is unnecessary and adds artifacts on solid backgrounds).
8. **Colour-channel isolation** (battle reports): from buffer (i), build `green_mask` and `red_mask` via the §5.4 HSV ranges, dilate slightly to close glyph strokes, then run a separate OCR pass on each. Column assignment becomes structural rather than inferred.
9. **PSM selection:** PSM 6 (uniform block) for the full-panel pass; PSM 7 (single line) for value-crop passes.

---

## 7. Human-confirm loop (non-negotiable)

**OCR never silently feeds the engine.** House rule (`COMPASS` invariant 8, `shell/ARCHITECTURE.md` boundary rule 4) and simple product sense: a confidently wrong input yields a confidently wrong prediction, which is worse than no prediction.

| Tier | Behaviour |
|---|---|
| **HIGH** | Auto-filled, editable, subtle green left-border on the input |
| **MED** | Auto-filled, editable, amber left-border, counted in "N fields to review" |
| **LOW** | **Left empty**, red left-border, requires typing or an explicit tap-to-confirm on a proposed value |
| **Missing** | Absent from the response; input untouched; listed in "couldn't read" |

- **Run is blocked** until zero unconfirmed LOW fields remain.
- **Show the source crop.** Next to each MED/LOW field, render the ~40 px-tall thumbnail of that value's bbox. Verification drops to a single glance — cheap to build, disproportionately effective.
- **Conflicts** (§5.6) render as a two-button choice, never auto-resolved.
- **Manual entry is never blocked.** OCR is an accelerator; every input stays typeable.
- Style all of this through `.claude/skills/wos-ui-styling/`; the reveal/confidence moment is squarely in `.claude/skills/wos-emotional-design/` territory (confidence-tiered intensity maps naturally onto the three tiers).
- **Telemetry:** per-field `(tier, was_edited, engine, lexicon_version)`. **No images, no values, no PII.** This is the accuracy dataset that drives tuning and the §9 risk-2 alarm. Must pass through `MinimizeMiddleware`.

---

## 8. Integration sketch

### Where code lives

| Path | Contents | Notes |
|---|---|---|
| `shell/app/ocr/client/` | `tesseract.min.js`, `worker.min.js`, `tesseract-core-simd-lstm.wasm`, `eng.traineddata.gz`, `panel-ocr.js` (preprocess + parser), `panel-ui.js` | Served at `/shell/ocr/assets/*`, `Cache-Control: public, max-age=31536000, immutable`. **Lazy-loaded on panel open**, never on page load |
| `shell/app/ocr/lexicon/en.json` | canonical labels + ranges | Versioned data; hot-swappable without a deploy |
| `shell/app/ocr/panel_parser.py` | Python twin of the parser, for the server fallback | Shared spec, shared fixtures — the JS and Python parsers must agree on every Phase-0 fixture (a test) |
| `shell/app/ocr/rapid.py` | RapidOCR engine wrapper | New, beside the existing `vision.py` |
| `shell/app/ocr/panel_router.py` | `POST /shell/ocr/panel` | New, beside the existing `router.py` |
| `shell/app/overlay/overlay.js` | adds the "Scan screenshot" entry point | Existing overlay seam; `prototype/index.html` untouched |

**Do not modify** the existing `POST /shell/ocr` (battle-report ingestion). Different schema, different validator, different quota class. Two endpoints, cleanly separated.

### Endpoint shape (fallback path only — the primary path is client-side and hits no endpoint)

```
POST /shell/ocr/panel        (multipart/form-data)
  file:        image  (≤8 MB, ≤64 MP — reuse extract.py's existing guards)
  panel_type:  "bonus_overview" | "scout_stats" | "battle_stats"
  side:        "attacker" | "defender"        (ignored for battle_stats — colour decides)

200 →
{
  "status": "ok" | "partial" | "failed",
  "engine": "rapidocr",
  "engine_version": "rapidocr-3.9.2/ppocrv6-small",
  "lexicon_version": "en-2026.08",
  "panel_type": "battle_stats",
  "fields": [
    {"key":"infantry_attack","column":"mine","value":4859.0,"unit":"percent",
     "confidence":0.97,"tier":"high","bbox":[x,y,w,h],
     "signals":{"label_ratio":1.0,"colour":"green","column_agree":true,"whitelist_agree":true}}
  ],
  "unreadable_fields": ["lancer_lethality"],
  "duplicate_conflicts": [],
  "warnings": ["unknown_row: 'Detonation Bonus'"]
}
```
`status: "partial"` whenever `unreadable_fields` is non-empty. **A field that could not be read is absent — never `0`.**

### Quota, rate limiting, image handling

- Add **`panel_ocr`** as a third endpoint class in `limits.py`, alongside `sim` and `ocr` (`OCR_ENDPOINTS` currently hardcodes `{"/shell/ocr"}` — extend, don't overload).
- **Client-side path: unmetered.** It costs nothing; metering it would be theatre.
- **Server fallback:** new `FREE_PANEL_OCR_PER_DAY=10`, `PRO_PANEL_OCR_PER_DAY=60`. Cheap enough to give free users a real allowance.
- **LLM fallback:** counts against the existing `PRO_OCR_PER_DAY=30`. Free tier: 0 (unchanged).
- **Concurrency:** a dedicated `asyncio.Semaphore(2)` for RapidOCR, separate from `GLOBAL_CONCURRENCY=8`, plus a hard per-request timeout (suggest 10 s) → 429 when saturated. **`EVAL_ROUND_1.md` F4 (body-size limit + execution cap) is a hard prerequisite** for shipping the server fallback.
- **Image handling:** in memory only. Never written to disk, never logged, discarded when the request ends. Reuse `extract.py`'s `MAX_IMAGE_BYTES = 8 MB` and `MAX_IMAGE_PIXELS = 64_000_000` and its Pillow-based re-encode (which also sniffs the real format rather than trusting the client's `Content-Type`). Result cache, if any, is **in-memory TTL keyed by image hash, never on disk**.
- **Cloudflare:** `/shell/ocr/assets/*` edge-cached and immutable (free tier, this is the real win); `POST /shell/ocr/panel` bypasses cache. Our 8 MB cap sits far under Cloudflare's 100 MB free-plan body limit.

---

## 9. Phased rollout

### Phase 0 — Spike & benchmark (**the gate**) · 2–3 days

Build the corpus first, exactly as the Type-1 battle corpus was built.

**Corpus:** ~20 real screenshots at `shell/tests/fixtures/ocr_panels/` — ≥6 Bonus Overview, ≥6 scout Stat Bonuses, ≥8 battle Stat Bonuses; ≥3 distinct device resolutions; ≥2 JPEG-recompressed via a messaging app; ≥2 including a notch/status bar; ≥1 overlapping pair. Hand-label **every** field into ground-truth JSON. This corpus is the permanent regression asset.

**Metrics and pass bars:**

| Metric | Definition | Bar |
|---|---|---|
| **Digit accuracy** | parsed value string-equals truth, over fields returned as HIGH | **≥ 99.0%** |
| **False-confidence rate** | wrong values returned as **HIGH** | **≤ 1%, target 0** ← the safety-critical one |
| **Field recall** | ground-truth fields extracted at any tier | ≥ 95% |
| **Column accuracy** (battle) | correct mine/enemy assignment | ≥ 99.5% |
| **Latency** | p50 / p95, mid-range Android + iPhone | p95 ≤ 8 s |
| **Server RAM** | RSS per RapidOCR worker (currently unmeasured — see §3b) | record for sizing |

**Run the identical benchmark** against: (1) tesseract.js v7 without the whitelist pass, (2) tesseract.js v7 **with** it, (3) `@paddleocr/paddleocr-js` PP-OCRv5-mobile, (4) one Gemini Flash-Lite call as a reference ceiling.

**Decision rule:** ship the cheapest engine that clears the bar. If neither client engine clears **99% digit accuracy**, promote server RapidOCR to primary and demote the client to a fast preview. If nothing clears it, ship the feature with **no HIGH tier at all** — every field requires confirmation — rather than shipping silent corruption.

### Phase 1 — MVP · 5–8 days
English only. **Manual panel-type selection** (segmented control: *My Bonus Overview / Scout Report / Battle Report*) — auto-detection is a Phase-3 nicety, not an MVP requirement. Client-side only, no server fallback yet. Full parser (§5), preprocessing (§6), confirm loop (§7). One screenshot at a time. Ship to **free and paid** (zero marginal cost). Manual entry stays untouched throughout.

### Phase 2 — Fallback chain + CJK · 5–8 days
Add `POST /shell/ocr/panel` (RapidOCR) behind the semaphore, gated on F4 landing. Add the "Use AI read" button wired to the existing vision client, quota-capped. Add multi-screenshot overlap dedup (§5.6).
**CJK:** server-side PP-OCRv5 mobile rec covers Simplified + Traditional Chinese + English + **Japanese in a single 17.2 MB model** ([HF](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec)); Korean is a separate 13.9 MB model ([HF](https://huggingface.co/PaddlePaddle/korean_PP-OCRv5_mobile_rec/tree/main)) — full zh+en+ja+ko ≈ 36.6 MB. Add locale-keyed lexicons (`lexicon/zh.json`, …). **Pin PP-OCRv5 for CJK:** the PP-OCRv6 paper states the *tiny* tier **excludes Japanese** and does not mention Korean ([arXiv 2606.13108](https://arxiv.org/html/2606.13108v1)) — verify per-tier language tables before any v6 upgrade.

### Phase 3 — Auto-detect & polish · 3–5 days
Panel-type auto-detection: ≥3 rows with two distinct values ⇒ battle (2-col); all values signed + single column ⇒ scout; unsigned + contains `Deployment Capacity` ⇒ Bonus Overview. Ambiguous ⇒ ask. Plus the telemetry-driven accuracy loop and the unknown-label alarm (risk 2).

---

## 10. Risks & mitigations

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| **1** | **Silent digit corruption.** A misread digit returned as HIGH produces a confidently wrong prediction. This is the worst failure mode *for this product specifically* — numeric precision is the entire value proposition | **Critical** | Digit-whitelist second pass with agreement gate (§5.5); false-confidence rate is an explicit Phase-0 pass bar (target 0); mandatory confirm loop (§7); per-field source thumbnails; run blocked on unconfirmed LOW; never auto-run |
| **2** | **Game UI update** changes labels, adds rows, or reflows the layout | **High** | Lexicon is versioned JSON data, not code — patchable without a deploy; unknown-row telemetry counter with a threshold alarm; parser **degrades to "unknown row, please type it"** rather than mis-assigning; `lexicon_version` in every response; Phase-0 corpus is the regression suite |
| **3** | **Client payload + device diversity.** 8 MB on mobile data; old/low-RAM phones OOM; iOS Safari WASM memory ceilings | **High** | Lazy-load on panel open with an explicit *"one-time ~8 MB download"* notice; Cloudflare edge-cached immutable assets; feature-detect WASM + `deviceMemory` and route to the server fallback; **manual entry never blocked**; `tessdata_fast` (3.9 MB) over standard (22.4 MB) |
| 4 | **COOP/COEP collision** — cross-origin isolation for ORT threads would break Clerk and Stripe embeds | High | Run single-threaded, or confine OCR to a dedicated isolated iframe. **Never** set COOP/COEP on the main document. Avoided entirely by choosing tesseract.js |
| 5 | **JPEG recompression** from WhatsApp/Discord destroys thin glyph strokes | Medium | Recompressed samples are mandatory in the Phase-0 corpus; upscale + denoise in §6; UX asks for the original screenshot ("send as file, not photo") |
| 6 | **Dark-mode / theme variants**, notches, status bars, different aspect ratios | Medium | Auto-polarity detection (§6.6); HSV rather than RGB colour thresholds; user crop step; ≥3 resolutions in the corpus |
| 7 | **Adversarial / garbage uploads** — decompression bombs, MIME spoofing, non-screenshots | Medium | Existing `MAX_IMAGE_BYTES=8 MB` + `MAX_IMAGE_PIXELS=64 MP` guards; Pillow decode sniffs the real format (never trust `Content-Type`); re-encode before processing; never persist; **F4 body-size cap is a prerequisite**; a non-panel image simply yields zero matched labels and a clean `failed` |
| 8 | **Determinism drift** — swapping a WASM build or model file silently changes outputs | Medium | Pin and hash every asset; treat a model change like an engine-parameter change (recorded, benchmarked, `engine_version` in the response); Phase-0 corpus re-run required before any bump |
| 9 | **Localization mismatch** — user's game is in another language while lexicon is English | Low (v1) | Detect zero label matches ⇒ explicit *"panel language not supported yet"*, never a partial garbage fill; Phase 2 adds locales |
| 10 | **Server fallback wedges the VPS** under concurrent load | Medium | Semaphore(2), 10 s timeout, 429 on saturation, metered quota; fallback expected to serve <5% of scans |

---

## 11. Cost & effort

### Marginal cost per month, by option

| Option | 1k scans | 10k scans | 100k scans | Deterministic? | Image leaves device? |
|---|---|---|---|---|---|
| **(a) Client WASM — RECOMMENDED** | **$0** | **$0** | **$0** | Yes | **No** |
| (b) Self-hosted RapidOCR (VPS) | $0 | $0 | $0 | Yes | Yes |
| (c) Google Cloud Vision | $0 | $13.50 | $148.50 | Yes | Yes (3rd party) |
| (c) Azure AI Vision Read (S1) | $1.50 | $15.00 | $150.00 | Yes | Yes (3rd party) |
| (c) AWS Textract | $1.50 | $15.00 | $150.00 | Yes | Yes (3rd party) |
| (d) Cloudflare Workers AI | — no real OCR engine — | | | No (VLM) | Yes |
| (e) Claude Haiku 4.5 | $3.76 | $37.56 | $375.60 | **No** | Yes |
| (e) Gemini 2.5 Flash-Lite | $0.40 | $3.96 | $39.64 | **No** | Yes |
| **Recommended chain (client + ~5% server + ~1% LLM)** | **~$0.00** | **~$0.04** | **~$0.40** | Yes (primary) | **No** (primary) |

*"Scans" = images. Users upload 1–3 screenshots per side, so a full two-side setup is 2–6 images — multiply the metered rows accordingly. This multiplier is exactly why per-image pricing is the wrong shape for this product.*

### Effort

| Phase | Work | Effort |
|---|---|---|
| 0 | Corpus + hand-labelling + 4-way engine benchmark + harness | **2–3 days** |
| 1 | Vendored assets, preprocessing, parser, confirm UI, overlay wiring | **5–8 days** |
| 2 | Server RapidOCR + LLM fallback + multi-screenshot dedup + CJK | **5–8 days** |
| 3 | Auto-detect, telemetry loop, unknown-label alarm | **3–5 days** |
| | **Total to full capability** | **~15–24 days** |
| | **Total to shippable MVP (Phases 0–1)** | **~7–11 days** |

Recurring infra cost added: **$0.** Docker image grows ~120–160 MB in Phase 2 only. No new vendor, no new contract, no new DPA.

---

## 12. Final recommendation

**Approve: client-side WASM OCR (tesseract.js v7, vendored, served same-origin through the existing overlay seam) as the primary panel-OCR engine, with a deterministic parser, a mandatory human-confirm loop, and a two-step fallback chain (server RapidOCR → vision-LLM).**

Four things make this the right call rather than merely the cheap one:

1. **It is the only option whose marginal cost is structurally zero** — not "cheap", *zero*. There is no meter to watch, no bill that scales with success, no incentive to ration the feature. The owner's constraint is satisfied absolutely rather than approximately.
2. **It is the only option where the screenshot never leaves the device.** That is a better privacy posture than anything achievable with a hosted engine, and it deletes an entire category of retention, logging, and DPA work.
3. **The self-containment rule turns out not to bind**, because the shell's overlay middleware already injects code without touching `prototype/index.html`. There is no rule to bend and no baseline to regenerate.
4. **The hard part isn't the OCR engine — it's §5**, and §5 is engine-agnostic. Whichever engine wins Phase 0, the parser, the confidence model, the validation schema, and the confirm loop are unchanged. That makes the engine choice cheap to revise and the investment safe.

There is also a bonus the project has only just acquired: `docs/STAT_PANELS_FORMULA.md` (confirmed 2026-08-05) gives a **deterministic arithmetic relationship between the three panel types**, which §5.9 turns into a validation pass that checks OCR output against the game's own maths rather than against an OCR confidence score. That is a stronger correctness guarantee than any hosted OCR vendor can offer at any price, and it costs nothing to use.

**Two decisions requested:**

- **D1 — Free-tier OCR.** Current quota says free = 0 OCR, set when LLM OCR was the assumed implementation. Client-side OCR costs nothing per scan. **Recommendation: give free users unlimited client-side panel OCR**, keep the 5 sims/day cap as the monetisation lever, and allow 10/day of the *server* fallback. Typing 16 numbers by hand is the single biggest onboarding drop-off in the product; removing it for free costs nothing and makes the paid tier easier to sell.
- **D2 — Phase 0 first.** Do not commit to an engine before the benchmark. If neither client engine clears 99% digit accuracy on real screenshots, the correct response is to **ship with no HIGH tier** — every field confirmed by hand — not to ship silent corruption. The feature is still a large win at that level, because reading and confirming 16 pre-filled numbers beats typing them.

**Open items to resolve during Phase 0:** RapidOCR per-worker RAM (no published figure exists); real in-browser latency on a mid-range Android; whether `@paddleocr/paddleocr-js` at v0.4.2 is stable enough to be the Phase-2 CJK client path or whether CJK stays server-only.

---

## Appendix — sources

**Client-side OCR:** [tesseract.js releases](https://github.com/naptha/tesseract.js/releases) · [npm](https://registry.npmjs.org/tesseract.js/latest) · [core file sizes](https://data.jsdelivr.com/v1/packages/npm/tesseract.js-core@7.0.0) · [local installation](https://github.com/naptha/tesseract.js/blob/master/docs/local-installation.md) · [tessdata_fast eng](https://github.com/tesseract-ocr/tessdata_fast/blob/main/eng.traineddata) · [tessdata eng](https://github.com/tesseract-ocr/tessdata/blob/main/eng.traineddata) · [naptha/tessdata CDN deprecation](https://github.com/naptha/tessdata/blob/gh-pages/README.md) · [ImproveQuality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html) · [DPI issue #393](https://github.com/naptha/tesseract.js/issues/393) · [char confusion #3144](https://github.com/tesseract-ocr/tesseract/issues/3144) · [screenshot-mode #929](https://github.com/tesseract-ocr/tesseract/issues/929) · [PSM guide](https://pyimagesearch.com/2021/11/15/tesseract-page-segmentation-modes-psms-explained-how-to-improve-your-ocr-accuracy/) · [@paddleocr/paddleocr-js](https://github.com/PaddlePaddle/PaddleOCR/tree/main/paddleocr-js) · [npm](https://registry.npmjs.org/@paddleocr/paddleocr-js) · [onnxruntime-web sizes](https://data.jsdelivr.com/v1/packages/npm/onnxruntime-web@1.27.0) · [WebGPU EP](https://onnxruntime.ai/docs/tutorials/web/ep-webgpu.html) · [COOP/COEP](https://web.dev/articles/coop-coep) · [TextDetector status](https://chromestatus.com/api/v0/features/5644087665360896) · [WICG text detection](https://wicg.github.io/shape-detection-api/text.html)

**Self-hosted:** [RapidOCR](https://github.com/RapidAI/RapidOCR) · [PyPI rapidocr](https://pypi.org/project/rapidocr/) · [releases](https://github.com/RapidAI/RapidOCR/releases) · [PyPI onnxruntime](https://pypi.org/project/onnxruntime/#files) · [PyPI paddlepaddle](https://pypi.org/project/paddlepaddle/#files) · [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) · [PP-OCRv5 CPU benchmark](http://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html) · [Baidu PP-OCRv5 blog](https://huggingface.co/blog/baidu/ppocrv5) · [PP-OCRv6 paper](https://arxiv.org/html/2606.13108v1) · [PP-OCRv5_mobile_det](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det) · [_mobile_rec](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec) · [korean_rec](https://huggingface.co/PaddlePaddle/korean_PP-OCRv5_mobile_rec/tree/main) · [python:3.12-slim layers](https://hub.docker.com/layers/library/python/3.12-slim/images/sha256-f0c6bc1ab7b1ab270bbb612a31a67a7938d6171183ddce9121f04984ab3df44e) · [volador/rapidocr](https://hub.docker.com/r/volador/rapidocr/tags)

**Cloud & LLM pricing:** [Google Vision pricing](https://cloud.google.com/vision/pricing) · [supported files](https://cloud.google.com/vision/docs/supported-files) · [Azure Vision pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/computer-vision/) · [Azure Retail Prices API](https://prices.azure.com/api/retail/prices) · [Azure OCR overview](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr) · [AWS Textract pricing](https://aws.amazon.com/textract/pricing/) · [Textract limits](https://docs.aws.amazon.com/textract/latest/dg/limits-document.html) · [Workers AI models](https://developers.cloudflare.com/workers-ai/models/) · [moondream3.1](https://developers.cloudflare.com/workers-ai/models/moondream3.1-9B-A2B/) · [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) · [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) · [Markdown conversion](https://developers.cloudflare.com/workers-ai/features/markdown-conversion/) · [Mistral pricing](https://mistral.ai/pricing/api/) · [OCR.space](https://ocr.space/ocrapi) · [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing) · [Claude vision](https://platform.claude.com/docs/en/build-with-claude/vision) · [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) · [Gemini image understanding](https://ai.google.dev/gemini-api/docs/image-understanding) · [Gemini media resolution](https://ai.google.dev/gemini-api/docs/media-resolution)

**Caveats on sources:** Azure's dollar figures came from Microsoft's Retail Prices API because the marketing page gates the numbers behind JS/sign-in — worth a manual spot-check in the Azure Pricing Calculator before relying on them. AWS Textract figures are US West (Oregon); regional uniformity not confirmed. No primary-source benchmark exists for OCR of flat-UI game-screenshot text — the accuracy expectations in §3a are directional, which is the entire reason Phase 0 is a gate rather than a formality.
