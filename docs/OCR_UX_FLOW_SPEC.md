# OCR UX Flow — Build Spec / PRD (owner-locked decisions)

**Status:** BINDING for the real build · **Date:** 2026-08-06 · **Owner:** Martin (all decisions below are his, from mock reviews 2026-08-06)
**Visual source of truth:** `prototype/mocks/ocr_flow_mock.html` (mobile + desktop, evaluator-gated). **Architecture:** `docs/OCR_SERVICE_PLAN.md`. **Conversion math:** `docs/STAT_PANELS_FORMULA.md` §8.

## 1. Product rules (non-UI)

1. **Tiering (D1):** free tier = NO OCR of any kind — manual input only. OCR (including the zero-cost client-side path) is paid-tier. Enforce server-side via entitlements, not just hidden UI.
   - *Amended 2026-08-09 (QA D-031): the server-side enforcement signal is **402 `payment_required`** from `LimitsMiddleware` (shell-wide convention) for both `/shell/ocr` and `/shell/ocr/panel` — the endpoints carry no plan branch of their own.*
2. **Engines:** client-side WASM primary → server RapidOCR fallback. **Vision-LLM: deferred to a future build** — never in v1; unreadable fields are typed by the user.
   - *Amended 2026-08-10 (post-benchmark, owner-decided): v1 is SERVER-side — the production ladder at `/shell/ocr/panel` (RapidOCR primary at 100% D2 PASS → Gemini gap-fill under daily budget at 100% → manual typing). Client-side tesseract.js benchmarked 64% and is BENCHED as the future client tier. §3 S3's "stays on your phone" trust line is replaced accordingly: "Sent securely and read right away. Your screenshots are never saved."*
3. **Never fabricate:** unreadable = absent = highlighted for the user; no guesses, no zeros.
4. **Determinism:** same screenshot → same output; parsed values validate against the panel law (`STAT_PANELS_FORMULA` §8 recipes + sanity ranges).

## 2. Per-side OCR contract (owner-mandated capture)

- **Two OCR paths exist and must both be first-class: OCR for MY side and OCR for the ENEMY side.**
- Panel types per side: **You** = City Stats (Bonus Overview) | Scout Report | Battle Report. **Enemy** = Scout Report | Battle Report. (City Stats is self-only.)
- **Battle Report is two-column**: when supplied on either side's slot, extract that side's column at minimum; implementation SHOULD extract both columns and offer to fill the other side too (it's the same screenshot). Selecting Battle Report must NEVER change the screen/layout — same two-side screen, the OCR simply reads the battle-report format.
- Conversions to engine input (scout-net, `stats_mode="scouted"`): scout → as-is; battle → divide out fold sets per the law; City Stats → requires the account's calibrated U block (one-time calibration from any same-state City-Stats+scout pair; store per account).

## 3. Flow (screens; mock = reference implementation)

- **S0 Entry:** "📷 Fill from screenshots" CTA ABOVE the existing manual form; the manual form below is labeled as today's form. Free-tier users: CTA visible but leads to upgrade note (per D1) — mock shows paid experience.
- **S1 Which screenshot:** 3 cards with faithful mini-renderings of the real panels; Battle Report promoted ("fills both sides"); third card named **"City Stats"** with subtitle "(called Bonus Overview in the game)"; each card carries its in-game breadcrumb.
- **S2 Add screenshots — ALWAYS the two-side screen (You / Enemy).** No mode switch, no layout collapse, ever. Each side has a type dropdown (pop-in menu; options per §2) and its own add zone. **The S1 selection presets the dropdowns** (Scout → both sides Scout; City Stats → You=City, Enemy=Scout; Battle → both=Battle). A Battle-type side with an upload counts as covering both sides. Type changes never destroy uploads. General principle (twice a blocker in mock QC): **any action that would discard an upload confirms first**.
- **S3 Reading:** on-device scanning, candy-stripe progress, honest step narration, "stays on your phone" trust line, working Cancel. First-use engine download shown as a one-time "getting ready" state.
- **S4 Check your numbers:** single review screen, both sides mirrored (me ice / enemy ember). EVERY field tap-to-type-over with **Save/Cancel**; low-confidence = gold "please check"; missing = inline highlighted empties (no separate screen); **Reset** (restore as-scanned, quick confirm); "See my screenshot" compare view; provenance labels ("Read from your screenshot" / "You typed this"); state-derived tally; **Next always enabled**.
- **S5 Battle setup (the point of arrival) — OWNER RULE (2026-08-06 v2): this page is NOT a new design. It IS the current app's setup section with OCR values prefilled.** Reuse the existing components verbatim — same templates, same markup patterns, same interaction model, clear Me(ice)/Enemy(ember) split exactly as the current app renders it:
  1. Stats are DONE and collapsed — a minimized summary chip of the review grid (expandable); the full stat panel is not the star here.
  2. **Troops Formation** (the app's existing name — "true formation" terminology is retired): the adjustable control is the **RATIO** (percent), exactly the current app's formation-ratio mode (`#formMe`/`#formFoe` glass sliders, `formRatio`/`setFormationMode('pct')`); counts derive from total troops × ratio, not the other way round.
  3. **Hero selection AND joiners**: the current app's exact selection templates (`#capMe`/`#capFoe` captains, `#joinMe`/`#joinFoe` joiners) for BOTH sides — not new slot designs. Captains DEFAULT from the report's gen badge (gen → names via `wos_sim/data/hero_generations.json`; skill `.claude/skills/wos-hero-identifier/`; City-Stats-sourced side = no default, prompt instead). Joiners: blank/unset in v1.
  4. **Role toggle** (Rally/Garrison — the app's real control) persists as-is.
  Anything still missing/unfillable stays highlighted. Primary CTA: **"See who wins →" = the existing forecast button.**
- **E1 Recovery (single screen, two variants):** wrong-screenshot / partial-read; shows the wanted sample; exits: "Add a clearer screenshot" (→S2, failed upload removed with notice) and "Type them in myself" / "Type the missing numbers" (→S4 inline).

## 4. Copy & presentation rules

- Terminology: **"screenshot(s)" — never "picture"/"photo"**; no jargon (OCR/confidence/parse banned in user copy); reading level ~grade 2–3; verbs first.
- WoS design system binding (`prototype/DESIGN_SYSTEM.md`): navy/ice/ember, glossy CTAs, physical depth; me=ice left, enemy=ember right; reduced-motion kill-switch; ≥44px touch targets.
- Honesty: uncertainty always visible, never blocking dishonestly; tallies derive from state; celebration register calibrated (no confetti — forecasting tool).
- **Two presentations, one HTML:** mobile flow (phone-first) AND a slick desktop layout — responsive, not separate apps.

## 5. Engineering patterns proven in the mock (carry into the real build)

Auto-advance screens share ONE history slot (Back/Cancel always land on the last deliberate screen); `[hidden]{display:none!important}`; field state on a persistent store surviving navigation; grid and screenshot-view derive from the same field-state source (cannot disagree); undo = pre-run snapshot restore; strict numeric validation (format + 0–6000 range, distinct messages); focus-to-heading on navigation; sheets set inert/aria-hidden and trap focus.

## Amendment 2026-08-15 — S2 row arrangement + the three battle inputs (owner decision)

- **S2 upload layout is ROWS**: each row = the REAL sample screenshot on the left (cropped
  from the owner's own fixture captures, `shell/app/ocr/client/samples/`) and that row's own
  labeled add-zone on the right. Scout and City Stats sides show exactly ONE row each.
- **Battle = THREE rows, in order**: **Heroes** (OPTIONAL — the report's hero strip;
  capture-only for now: captain auto-set awaits the badge-reading derivation — the
  2026-08-15 spike showed RapidOCR reads the star rows cleanly but mangles gen-badge digits,
  and the portrait→class order convention is unproven; the row's copy says exactly this),
  **Battle stats** (the Stat Bonuses list — fills all 24 numbers), and **Buffs** (NEEDED —
  the "Notes on Special Bonuses" popup behind the ! icon; conversion refuses without it,
  D-043). D-045's popup guarantee moved INTO the Buffs row; the separate hint card is gone.
- Every row's zone feeds the SAME per-side shot set — the server sorts shots by content, so
  there is no wrong slot. **What battle needs and deliberately does NOT need** (owner
  question 2026-08-15): gear/charm/expert/pet screenshots are NOT inputs — the three-panel
  law proves they are already folded into the panel numbers; troops/formation are set in the
  app; hero screenshots become a live input the moment badge-reading ships.
- Samples degrade per-row when their images can't load (promoted bundles strip game-IP art):
  stats/scout/citystats rows fall back to the hand-drawn mini-panels, heroes/popup rows to
  their alt text.
