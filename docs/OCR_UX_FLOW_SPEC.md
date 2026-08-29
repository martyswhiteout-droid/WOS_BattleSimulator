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

## Amendment 2026-08-25 — S2 ingestion channels, row relabels, buffs attestation (owner feedback)

- **Every add-zone takes three equal channels**: tap (OS picker), **paste**, and **drag-drop**
  (owner: "make it a copy/paste as well as a drop-image in widget"). Paste routes to the
  focused zone, else the last-touched zone, else YOU. All channels accept png/jpeg/webp only
  and funnel through one ingest path.
- **Heroes row → "Heroes + Experts", no OPTIONAL tag, explainer sentence removed** (owner).
  Engine reality unchanged: the row is capture-only until the badge-reading derivation ships
  (2026-08-15 spike: star rows read cleanly, gen-badge digits mangle) — the REQUIRED
  presentation is the owner's call and is recorded here; a heroes upload cannot poison a read
  (round-6 adversarial proof, EVAL_UX_JOURNEY.md).
- **Buffs row: NEEDED tag dropped** (hard to see); the row takes **1 or 2 screenshots** (long
  popup lists scroll; stitch merges by (canonical,side) — pinned by
  `test_owner_20260825_two_popup_screenshots_merge_into_one_specials_set`).
- **Explicit "No buffs on either side" attestation** (battle only): a toggle under the battle
  rows. Semantics are STRICT (honesty rule): the attestation upgrades ONLY a silent absence
  (`specials_observed: "none"`) to the legal zero-specials read state (QA D-022's documented
  legal state, attested by the user instead of a captured empty popup). It never overrides
  `"partial"` (rows were SEEN but unreadable — the screen contradicts the claim) and never
  overrides a real read. An APPLIED attestation is said out loud on S5 as an informational
  note that never demotes the completion chip. Sticky across re-entry, like the shot set.
- **Enemy X Penalty rows, conversion vs prediction** (owner question): conversion-side folding
  is correct and now pinned by name (enemy-side rows → P[stat] as |value|, D-013 sign guard;
  own-side rows never leak into own S sets) — but captured penalty rows are NOT yet propagated
  into the prediction's `debuffs_on_enemy` (the app's Buffs tab). That propagation is a
  PROPOSED follow-up awaiting the owner's call (it changes prediction inputs).
- **Resolved without new screenshots (2026-08-25 double-check):** the long-form scout and
  City Stats previews were regenerated from the owner's own fixtures (C_scout.png full
  12-row panel; C_citystats_1.png full Bonus Overview); the Heroes + Experts preview is now
  the report's Hero Comparison + Expert Comparison sections cropped from C_battle_1.png
  (owner to confirm it matches his attachment 3). The four "Appoint-based Troop's
  Attack/Defense/Lethality/Health" labels are in BOTH lexicons per the owner's typed
  instruction (skeleton matching is alpha-only, so in-game apostrophe/hyphen variants
  resolve identically); their fold bucket is plain-buff (S_scout) per the owner — one real
  battle+scout capture pair from an appointed account will confirm scout-visible vs
  battle-only, and the real popup captures will confirm the exact wording.
- **Troop Power (owner 2026-08-25):** battle has a fourth, OPTIONAL row — the Troop Power
  screen (troop type, quality, FC tier, T12 level, per-level counts -> the final checks).
  Capture-only until the Troop Power parser ships; its sample image is PENDING an owner
  capture (the row falls back to alt text meanwhile).
- **Still pending owner screenshots** (never guessed): the two buffs-popup captures
  (attachments 5-6 — fixtures + exact Appoint-based wording confirmation) and the Troop
  Power screen (sample + parser ground truth). Drop into
  `shell/tests/fixtures/panel_ocr/images/`.

## Amendment 2026-08-29 — merged slot-grid Upload screen (SUPERSEDES the 2026-08-25 rows layout)

Owner redesign, built to a dedicated multi-document-upload UX research round
(sub-agent, 2026-08-29). S1 (type cards) and S2 (sample rows) are ONE screen now:

- **Type tabs** at the top — `Battle / Scout / City` (one word each), battle
  preselected (`flow_state` initial is now `battle`). Switching tabs is
  non-destructive: shots stay parked under their slot keys; the read sends ONLY
  the active type's slots (`sendableShots`).
- **Slot grid** — one tile per named screenshot, 2-column, ALL tiles visible in
  the first viewport at 375x812 (verified by rect: tiles 181-383px, Scan 736-783px).
  Battle = Heroes* / Stats* / Buffs* / Power(optional); scout & city = stacked
  You/Enemy groups with per-group `n/m` counts (research: never side-tabs).
- **State lives on the tile**: empty = dashed + dimmed sample-crop icon; added =
  real LOCAL thumbnail (object URL — never uploaded, never stored) + green check
  + corner x; 2-shot slots add a count badge; Buffs offers a one-word `None`
  attestation link (sets the no-buffs attestation; a real upload clears it).
- **Summary strip**: pips + bare fraction (`2/3`). Footer CTA: `Scan` (one word),
  disabled until every required slot is covered.
- **Tap a FULL tile** -> preview sheet (thumbnail + `Remove` / `Replace`) — never
  a silent overwrite. Tap a tile with room -> OS picker; drag-drop targets the
  tile; paste routes via `pasteTargetSlot` (last-touched slot with room, else
  first empty, else first with room).
- **Word budget is enforced**: every slot label is one word (unit test), and the
  whole battle screen shows < 20 visible words (unit test). Notices trimmed:
  re-entry = `Earlier screenshots kept.`; recovery = `Removed. Add a new one.`
  E1 actions: `Retake` / `Type instead` / `Try again` / `Type the rest`.
- **Compat**: `goto('s2')` aliases to `s1`; E1 recovery targets `s1` directly.
  D-039/D-041 recovery machinery, the D-040 inert rules, and the sample-img
  promoted-bundle fallback (tile icon degrades to label-only) all carry over.
- Troop Power's sample image is still PENDING an owner capture — its tile
  renders label-only via the img-error fallback meanwhile.
