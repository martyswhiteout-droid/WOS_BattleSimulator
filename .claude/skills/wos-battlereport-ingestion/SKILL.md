---
name: wos-battlereport-ingestion
description: Standardized, deterministic ingestion of Whiteout Survival (WoS) battle reports into canonical JSON. Use whenever Martin provides WoS battle-report screenshots, a PDF of battle reports, or asks to record/ingest/capture/save a battle, experiment, beast hunt, or PvP report — even if he doesn't say "ingest" (e.g. "here are the reports", "record these", "put these into JSON", "save this battle"). Also use when normalizing or re-checking an existing battle JSON against the standard. Every engine/agent (Claude, Codex, anyone) must produce byte-identical structure for the same report, so ALWAYS follow this skill for WoS battle data rather than improvising a format.
---

# WoS battle-report ingestion

One battle report → one canonical JSON file. The formula-derivation program treats
these files as **exact-fit calibration data**, so a missed field or an invented
number silently corrupts the physics. Two rules dominate everything else:

1. **Capture everything the report shows.** A WoS report is MULTIPLE screens
   (Battle Overview → Bonus Source → Chief Gear → Troop Power Comparison →
   **Stat Bonuses** → Battle Details/participants). The Stat Bonuses screen is
   the one historically missed — missing it once caused a false "engine is
   wrong" investigation. STATS ALWAYS EXIST.
2. **Never fabricate.** Unknown → `null` + an entry in `_validation.missing`.
   Unreadable → say so ("OCR too small — resend larger") instead of guessing.
   A flagged gap costs a re-send; a guessed digit poisons the formula.

## Workflow

1. **Classify the report kind**: controlled experiment (1v1/NvM, NanoMart-style),
   PvP field report (rally/garrison, multi-participant), or beast hunt.
2. **Completeness gate.** Before extracting, check the screens present. If the
   Stat Bonuses panel (both sides) is missing → the report is INCOMPLETE: still
   record what exists, set `stats_capture` to `missing`, list it in
   `_validation.missing`, and ask Martin for the missing screen. Do not proceed
   silently and do not guess stats.
3. **Extract** every field per [references/schema.md](references/schema.md) —
   the canonical schema (v2). Follow its key order exactly (determinism).
4. **Derive troop passives.** Look up each side's tier/FC in
   [references/troop-passives.md](references/troop-passives.md) and record every
   unlocked skill with an `applies_in_this_battle` verdict based on the OPPOSING
   composition (e.g. Master Brawler only applies if the enemy fields Lancers).
   This is derived data the report does not print — deriving it here is the point.
5. **Classify Type 1 vs Type 2.** Type 1 = deterministic (no chance-based procs:
   T1-T6 troops, no proc heroes). Type 2 = any chance proc present (Ambusher,
   Volley, Crystal skills, hero procs). The tier/FC table in troop-passives.md
   gives the gates. Type decides how the file may be used downstream (Type 1 =
   exact-fit target; Type 2 = distribution check only — NEVER regression-fit).
6. **Record hero skills explicitly**: hero name, slot, skill name, LEVEL, the
   effect at that level, and trigger/kill counts when shown. Levels matter
   (Seo-yoon L3 = +15% Troops Attack; other levels differ — record what is
   known, mark unknown levels `null`, never assume).
7. **Infer turns** when a cadence hero is present (Vulcanus S3 fires turns
   3, 6, 9, … → k triggers ⇒ turns ∈ [3k, 3k+2]; S2 on a 1-unit side → m
   triggers ⇒ turns ∈ [6m, 6m+5]; intersect. Cadence corrected 2026-07-18 —
   see troop-passives.md). Record the trigger count, the inferred range, the
   chosen value, and the method in `turn_inference`.
8. **Name the file** per the convention below and write it to
   `wos_sim/data/experiments/` (experiments/beasts) or `wos_sim/data/` (PvP).
9. **Validate**: run
   `py .claude/skills/wos-battlereport-ingestion/scripts/validate_report.py <file.json>`
   and fix every ERROR before finishing. Report remaining WARNINGs to Martin
   verbatim — they are usually real OCR/data anomalies (see "suspicion rules").

## Filename convention

| Kind | Pattern | Example |
|---|---|---|
| 1v1 / NvM experiment | `<Account>_<AvD>_<TnCls>v<TnCls>_<HeroTokens>.json` | `NanoMart_1v1_T1LanvT1MM_SeoYoonlvl3_Vulcanus.json` |
| Count series | `<Account>_<count>_<HeroTokens>.json` | `NanoMart_100_SeoYoonlvl3.json` |
| Beast | `<Account>_Beast_<TroopDesc>v<BeastName>Lv<N>.json` | `Mueller_Beast_20kLv1InfvTitanRocLv18.json` |
| PvP report | `PvP_<Attacker>_vs_<Defender>_<YYYY-MM-DD>.json` | `PvP_Marty_vs_Bepo_2026-03-28.json` |

Class abbreviations: `Inf`, `Lan`, `MM`. Hero tokens: `SeoYoonlvl3`, `Vulcanus`,
`NoHero`, `NoAttackerHero_Vulcanus`, `VulcanusVsVulcanus` (attacker token first,
defender second). Attacker is always named first everywhere.

## Suspicion rules (hard-won — check before finishing)

- **Duplicate values across rows** (e.g. two different matchups both reading
  "96 turns") → flag as possible OCR/heading duplication; ask Martin to confirm.
- **Non-monotonic ladders** (T5→T1 faster than T6→T1) → flag, don't rationalize.
- **Heading vs content mismatch** (PDF heading says T11, panel shows T1) →
  record what the PANEL shows, note the mismatch in `notes`.
- **Tier as displayed**: record `"Lv 6.0"` / `"T6 FC10"` exactly as shown in
  `tier_display`; never substitute an assumed tier.
- **Mirrors must be stat-checked**: "mirror" means same class/tier, NOT equal
  stats — the panels always differ per player. Never label sides equal without
  comparing the captured panels.

## Reference files

- [references/schema.md](references/schema.md) — the full canonical JSON schema
  (field-by-field, with a complete worked example). Read it before writing any JSON.
- [references/troop-passives.md](references/troop-passives.md) — troop skill
  unlock table (tier/FC gates), the passive counter-triangle, Type-1/Type-2
  classification, and known hero kits (Seo-yoon, Vulcanus clock inversion).
- `scripts/validate_report.py` — deterministic validator (schema completeness +
  arithmetic identities). Always run it; never hand-verify arithmetic.

## After ingesting (mandatory)

Re-run the Type-1 corpus builder so the new battles enter the canonical dataset:
`py "wos_sim/data/experiments/_corpus/build_corpus.py"`. The corpus
(`TYPE1_CORPUS.json`/`.md` + `corpus.py` query CLI) is the single retrieval point
for ALL deterministic battles — analytics must read from it, not from scattered
folders. If a report needed a correction (OCR mislabel etc.), register it in
`_corpus/corrections.json` (never edit the source JSON's history silently).
