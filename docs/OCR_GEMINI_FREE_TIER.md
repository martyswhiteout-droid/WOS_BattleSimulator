# Gemini API free tier as the OCR engine — findings & setup guide

**Date:** 2026-08-06 · **Requested by:** Martin (owner) · **Status:** researched; adoption decision is Martin's.
**Question:** can Google AI Studio's free tier (≈1,500 calls/day) carry the stat-panel OCR for free — one call per screenshot?

## 1. Verdict in three lines

- **Yes for your scale.** Gemini **3 Flash** (Google's current recommended free-tier model) gives **10 requests/min · 250K tokens/min · 1,500 requests/day, vision included**, per project, no card required. One screenshot = one call; even a heavy day (20 users × a few panels) doesn't approach 1,500.
- **The quota is per PROJECT, shared by every user of wostests.com** — 1,500/day is a global pool, not per-user. Fine for you + alliance beta; a real public user base eats it.
- **The fine print matters for a public product:** free-tier inputs/outputs may be used by Google to improve products and **may be read by human reviewers**; Google says don't submit sensitive/personal data, frames the free tier for developer/business use "not for consumer use", and requires paid tier for EEA/UK/CH production. For your own use and a small opt-in beta: acceptable with a disclosure line. For the public paid product: use a paid-tier key (Flash-Lite-class OCR costs pennies) or the deterministic client path from `docs/OCR_SERVICE_PLAN.md`.

## 2. What the free tier actually is (verified 2026-08-06)

| Model (free tier) | RPM | RPD | Vision |
|---|---|---|---|
| **Gemini 3 Flash** (recommended) | 10 | **1,500** | yes |
| Gemini 2.5 Flash | 10 | 250 | yes |
| Gemini 2.5 Flash-Lite | 15 | 1,000 | yes |
| Gemini Pro models | — | **removed from free tier (Apr 2026)** | — |
| Gemma via API | not listed on the current free-tier tables — check YOUR project's numbers at aistudio.google.com/rate-limit | | |

- Limits are **per project, not per API key** (multiple keys in one project share the pool). Exceeding → `429 RESOURCE_EXHAUSTED`, resets daily.
- Google's own docs defer exact numbers to the **AI Studio → Rate Limit dashboard** — treat that page (in your `wos-tests` project) as authoritative; third-party figures above are the current consensus and match your "1,500/day" memory for Gemini 3 Flash.
- **On "just deploy Gemma":** you don't deploy anything — Gemma models are served through the same Gemini API endpoint and, when listed for your project, share the same free-quota mechanism. But the current free-tier tables push Flash as the free workhorse and Gemma-via-API availability fluctuates; Gemini 3 Flash is the safer bet and reads game screenshots at least as well. If your dashboard shows a separate (historically much larger) Gemma allowance, it's a fine overflow lane — same integration code, different `model=` string.

**Data-use terms (free tier, quoted):** "Google uses the content you submit … and any generated responses to provide, improve, and develop Google products", "human reviewers may read, annotate, and process your API input and output", "Do not submit sensitive, confidential, or personal information to the Unpaid Services." Paid tier: "Google doesn't use your prompts … or responses to improve our products." Game stat panels are low-sensitivity, but they do contain player names — disclose to users ("screenshots are read by Google's AI service") while on the free tier.

## 3. How it slots into our architecture (no redesign needed)

The engine layer was always pluggable. Gemini becomes an **engine adapter** producing the same structured fields, and EVERYTHING downstream stays: strict validators (format + 0–6000 range), the panel-law reconciliation (`docs/STAT_PANELS_FORMULA.md` §8), per-field confidence → the review screen, never-fabricate. Determinism caveat: temperature 0 + fixed prompt makes it *near*-deterministic, not guaranteed — another reason the validators + confirm screen stay mandatory.

Degrade ladder v1 (revised): **Gemini free tier (primary while beta) → server RapidOCR (when quota near/exhausted or Gemini down) → manual typing.** The client-side tesseract.js path remains the zero-cost-at-any-scale endgame from the main plan; building it is unaffected.

Practical notes:
- The shell already has the seam: `shell/app/ocr/vision.py` includes a Gemini client and `GEMINI_API_KEY` env slot — the panel OCR reuses that client with a panel-specific prompt + JSON `response_schema` (fields: `panel_type`, per-class stats, specials list, `unreadable_fields`).
- **Quota guard (must-build):** server-side daily counter (Supabase table, one row/day); at ≥1,400 calls switch new requests to the fallback ladder and show the honest state ("today's free reads are used up — type them in or try tomorrow"). Never let a 429 surface raw.
- Per-user quota (30/day paid) still applies on top; free tier of wostests.com gets no OCR regardless (owner decision D1).
- Batch friendliness: a battle report = 1 call (both columns in one image). Two overlapping screenshots = 2 calls.

## 4. Step-by-step setup (10 minutes, from the screen you showed)

1. In Google AI Studio (`martyswhiteout@gmail.com`) → **API Keys → Create API key** → choose the existing **`wos-tests`** project (keeps quota/billing visibility in one project; the page you screenshotted). Copy the key once — treat it like a password.
2. **Never** put it in the browser/client code or the repo. It goes server-side only: `shell/.env` → `GEMINI_API_KEY=<key>` (the slot already exists; `.env` is git-ignored per THIRD_PARTY_SETUP).
3. Leave the project on the **free billing tier** (your screenshot shows no billing attached — that IS the free tier). Don't attach a card until you deliberately want paid-tier data terms/quota.
4. Check **aistudio.google.com/rate-limit** with the project selected — confirm the per-model RPD your account actually has (authoritative over any blog table, including §2 above), and note which Gemma entries (if any) appear for you.
5. Smoke test (no code, free): in AI Studio's chat, pick Gemini 3 Flash, paste one of your stat-panel screenshots, prompt: "Read every row. Return JSON: {label, value} per row, exact digits." — eyeball digit fidelity on your own panels.
6. Wire-up order when building (maps to the TDD plan): implement the adapter behind the SAME `extract_panel` contract (plan Task 8), add the quota-guard counter, keep RapidOCR (plan Task 12) as fallback. The golden-vector fixtures then benchmark Gemini exactly like any other engine — same ≥99%-digits / zero-false-confident bar (owner decision D2).

## 5. Cost picture if/when you outgrow free

At 100k scans/month: paid Gemini Flash-Lite-class ≈ **$0.40–$40/mo** depending on model (still trivial), vs $0 for the client-side deterministic path — which is why the endgame architecture in `docs/OCR_SERVICE_PLAN.md` is unchanged; the free tier is the fastest zero-cost on-ramp, not the destination.

## Sources

- [Gemini API rate limits (official — defers numbers to your AI Studio dashboard)](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Gemini API additional terms (official — free-tier data use quotes)](https://ai.google.dev/gemini-api/terms)
- [TokenMix: Gemini API free tier 2026 — 1,500 req/day](https://tokenmix.ai/blog/gemini-api-free-tier-limits)
- [PE Collective: Gemini free tier guide 2026](https://pecollective.com/tools/gemini-free-tier-guide/)
- [AIFreeAPI: Gemini free tier complete guide 2026](https://www.aifreeapi.com/en/posts/gemini-api-free-tier-complete-guide)
- [Google AI Developers forum: Gemma rate limits](https://discuss.ai.google.dev/t/gemma-3-27b-rate-limits/73700)
