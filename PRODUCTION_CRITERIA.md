# PRODUCTION_CRITERIA v2 — the gate between prototype and WOSTests.com

**Owner: Martin. Version 2, 2026-07-11.** Supersedes v1. Agents may PROPOSE changes (as a diff for review) but must never weaken or reinterpret an item to let a release through.

## Principle

`E:\WOS\Battle Simulator` is the **prototype** — everything there is work in progress by definition.
`E:\WOS\WOSTests.com` is **production only** — it contains nothing except releases that have passed EVERY item below.

**The default state of production is EMPTY.** An empty `WOSTests.com` folder means "nothing has qualified yet" — correct, not an error. No agent may copy files there to "populate" it, stage work there, or use it as scratch space.

## The gatekeeper rule (binding)

**Nothing enters production without an independent QA gate agent issuing a written PASS verdict, followed by Martin's explicit sign-off.**

- The QA gate agent must be a fresh, independent agent/session — never the builder reviewing its own work.
- The QA agent's job is to verify EVIDENCE for every item below, not to take the builder's word.
- Verdicts: **PASS** (ship), **CONDITIONAL** (do not ship; fix and re-gate), **FAIL** (do not ship). CONDITIONAL is a polite FAIL at this gate — only PASS opens the door.
- The verdict is recorded using the Gate Report template at the bottom of this file and referenced in `E:\WOS\WOSTests.com\PRODUCTION_LOG.md`.
- No QA green light = no push. There are no exceptions, including "Martin seemed to want it" — inferred approval does not count (item I2).

---

## A. Correctness & engine integrity

- [ ] **A1.** Full test suite passes: `py -m pytest` — zero failures/errors; skips require written justification.
- [ ] **A2.** Regression gate passes: `py -m wos_sim.regression`.
- [ ] **A3.** Golden-anchor backtest: `py -m wos_sim.backtest` — pass count ≥ recorded baseline (gate G12). Record the count in the gate report.
- [ ] **A4.** No-fudge compliance (`ENGINE_REBUILD/ENGINE_CHANGE_CHECKLIST.md`): Type-1 exact fit with zero fudge factors; Type-2 by distribution only.
- [ ] **A5.** Honesty surfaces intact: `coin_flip` labels, `engine_meta` path + model_error, confidence badges truthful; no over-claiming out-of-regime matchups.

## B. Data model robustness

- [ ] **B1.** The profile/scenario schema (BRD §9) is **versioned** (explicit `schema_version` field); production rejects unknown versions with a clean error instead of guessing.
- [ ] **B2.** Server-side validation is strict: every field type/range-checked; malformed, missing, or extra-field payloads produce clean 400s with safe messages — never 500s, hangs, or silent defaults that change results.
- [ ] **B3.** User-facing data model (accounts, subscriptions, entitlements, quotas, usage log) is designed, migration-tested, and backed up. No user or payment state stored in flat files alongside code.
- [ ] **B4.** Saved scenarios from prior schema versions either load correctly via migration or are rejected explicitly — no silent corruption.

## C. Access control & paywall

- [ ] **C1.** **Login required for all simulation endpoints.** No anonymous access to `/api/predict` or `/api/battle` in production — not even a "free taste" without an account. (A static marketing page may be public; the engine may not.)
- [ ] **C2.** Free and paid tiers exist with **server-side** entitlement enforcement. The client/UI must never be the thing deciding what a user is allowed to run — assume the client is hostile.
- [ ] **C3.** Payments via a hosted provider (e.g. Stripe/Paddle/Airwallex hosted checkout) — we never touch or store card data; PCI burden stays with the provider. Webhooks signature-verified; entitlement changes only via verified webhook or admin action.
- [ ] **C4.** Session/token security: expiring tokens, secure/httponly cookies or equivalent, logout works, no tokens in URLs or logs.
- [ ] **C5.** Account creation is abuse-resistant: email verification at minimum; free-tier quota is per verified account AND per IP, so burner accounts don't multiply free quota.

## D. Anti-distillation & engine protection

*Threat model: the engine's formula IS the product. It was itself reverse-engineered via controlled micro-battles (1v1, single-variable sweeps, thousands of runs) — so production must block exactly that methodology being used against us.*

- [ ] **D1.** **Minimum battle size enforced server-side: ≥ 5,000 troops per side** (configurable constant, default 5000; documented in the gate report). Requests below threshold → clean 400. This kills 1v1 / 10v10 isolation experiments. **Prototype is exempt** — micro battles remain essential for our own calibration; never port this limit back into the prototype.
- [ ] **D2.** Rate limiting, layered: per-account daily query budget (free tier: small, e.g. ≤ 20/day; paid: capped, e.g. ≤ 200/day), per-account burst limit (e.g. ≤ 5/min), per-IP limits, and a global concurrency cap so a flood degrades gracefully instead of taking the service down (DoS resilience).
- [ ] **D3.** Sweep detection: usage log per account; flag/throttle patterns of many near-identical queries with one variable stepped (the parameter-sweep signature). Alert goes to Martin; automated response is throttle, not ban (false positives happen).
- [ ] **D4.** Output surface minimized: production responses expose only user-facing results (win%, survivor ranges, badges). No raw TURN_PARAMS, no internal telemetry fields, no debug/dev endpoints, no verbose error traces. Survivor figures reported at product-appropriate precision (e.g. rounded/banded), **not** by adding random noise — noise would corrupt the honesty design.
- [ ] **D5.** The engine runs server-side only. No engine logic, constants, or formula fragments shipped to the browser. (The prototype's single-file UI is fine because the math lives in Python behind the API — keep it that way.)
- [ ] **D6.** Terms of Service explicitly prohibit reverse engineering, automated scraping, bulk querying, and model extraction; quota circumvention is a termination offence.

## E. Security & penetration testing

- [ ] **E1.** A penetration test (independent agent or tool-assisted: OWASP Top 10 — injection, auth bypass, IDOR, SSRF, etc.) has been run against the staging deployment; all High/Critical findings fixed, Mediums fixed or waived in writing by Martin.
- [ ] **E2.** Adversarial payload suite (per `QA_PROMPT.md`) passes: fuzzed/malicious inputs produce clean 400s.
- [ ] **E3.** Dependency audit clean: `pip-audit` (or equivalent) shows no known-critical CVEs in production requirements.
- [ ] **E4.** Secrets management: no keys/credentials in the repo or client; environment-based config; `.env` files gitignored and absent from the release artifacts.
- [ ] **E5.** Transport: HTTPS only; HSTS; CORS locked to the production origin.
- [ ] **E6.** Request timeouts and body-size limits set, so a single expensive request cannot monopolize the worker (complements D2's caps).

## F. Intellectual property & legal

*Context: Whiteout Survival and its art are Century Games' IP. The prototype currently uses scraped hero portraits and skill icons from the wiki — acceptable for a private prototype, a liability in a paid product.*

- [ ] **F1.** Asset audit: no copyrighted game assets (hero portraits, skill icons, game logo, official artwork) in the production release unless licensed. Replace with original/generic art, or Martin explicitly accepts the risk in writing in the gate report.
- [ ] **F2.** Trademark hygiene: the game's name used only nominatively ("simulator for Whiteout Survival"), never in the product's own name/logo/domain branding as if official; visible disclaimer: "Not affiliated with or endorsed by Century Games."
- [ ] **F3.** Scraped-content audit: no redistribution of wiki text or workbook-derived tables beyond what's needed to render OUR results; check the wiki's license terms for anything retained.
- [ ] **F4.** Legal pages live: Terms of Service (incl. D6 clauses), Privacy Policy (what we store, where; HK PDPO baseline, GDPR-aware if EU users can sign up), refund policy consistent with the payment provider's rules.
- [ ] **F5.** Fonts/libraries license check (current set — Chakra Petch, IBM Plex Mono, Inter, FastAPI stack — is open-license; re-verify anything added since).

## G. Product & UX

- [ ] **G1.** Shipped scope meets its BRD acceptance criteria.
- [ ] **G2.** No regression of the `UX_BACKLOG.md` "shipped, do-not-regress" list (mobile, encoding); all P1 items on shipped pages resolved.
- [ ] **G3.** Paywall UX honest: free-tier limits stated up front; no dark patterns; upgrade/cancel paths work end-to-end in staging.

## H. Documentation & traceability

- [ ] **H1.** `CONTEXT_INDEX.md` updated for the release; "Last audited" date bumped.
- [ ] **H2.** Release is a clean, tagged git commit (`release-YYYY-MM-DD`) — never a dirty working tree.
- [ ] **H3.** Gate report (template below) completed and stored with the release; entry appended to `E:\WOS\WOSTests.com\PRODUCTION_LOG.md`.

## I. Sign-off

- [ ] **I1.** Independent QA gate agent verdict: **PASS** (report attached).
- [ ] **I2.** Martin has explicitly approved this release, this scope, on this date — in his own words, not inferred.

---

## Gate Report template (QA agent fills this in)

```
# PRODUCTION GATE REPORT
Date:            YYYY-MM-DD
Release tag:     release-YYYY-MM-DD
QA agent:        <identifier; must not be the builder>
Scope shipped:   <one paragraph>

Evidence:
  A1 pytest:            PASS/FAIL (<n> tests, output ref)
  A2 regression:        PASS/FAIL
  A3 backtest count:    <n> vs baseline <m>
  A4 no-fudge:          PASS/FAIL (params diff reviewed)
  A5 honesty:           PASS/FAIL
  B  data model:        PASS/FAIL (schema_version, validation evidence)
  C  paywall/auth:      PASS/FAIL (endpoints probed anonymously → 401?)
  D  anti-distillation: PASS/FAIL (min-size probe, rate-limit probe, sweep-flag test)
  E  security/pentest:  PASS/FAIL (findings list + resolutions)
  F  IP/legal:          PASS/FAIL (asset audit list, disclaimers, ToS/Privacy live)
  G  product/UX:        PASS/FAIL
  H  docs/tag:          PASS/FAIL

Waivers granted by Martin (item, date, wording): <none | list>
VERDICT: PASS | CONDITIONAL | FAIL
Rationale (3 lines max):
```
