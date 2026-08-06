---
name: wos-hero-identifier
description: Identify Whiteout Survival heroes from screenshots (hero panels, battle reports, lineup comparisons). Use whenever a WoS screenshot shows hero portraits that need naming — the portrait badge number IS the generation; map generation → the three hero names via wos_sim/data/hero_generations.json. Also use when decomposing stat panels (hero generation drives the U-block injection values).
---

# WoS Hero Identifier

**Rule (Martin, 2026-08-06): the number badge on a hero's portrait is the hero's GENERATION.**
A "15" on the portrait means Gen-15. Each generation has exactly three heroes — one per troop
class — so portrait number + class (or portrait art) identifies the hero uniquely.

## Identification procedure

1. Read the badge number N on the portrait → generation N.
2. Look up generation N in `wos_sim/data/hero_generations.json` (`{name: {generation, troop}}`)
   — it lists every hero's generation and class. Do NOT guess from art alone.
3. If the screenshot shows a lead-hero lineup (e.g. Hero Comparison), assign by class slot:
   each class row/slot gets the hero of that class from the badge's generation.
4. Cross-checks when available:
   - Stat-panel arithmetic: a lead hero injects its generation's stat block into its own
     class's panel rows — `HERO_GEN_STAT` (prototype/index.html, `const HERO_GEN_STAT`),
     e.g. Gen-15 → [19.6156, 4.9] = +1961.56% Atk=Def, +490% Leth=HP. If the panel math
     doesn't fit the badge generation, flag it (possible OCR misread) — see the
     ocr-anomaly rule: verify with Martin before theorizing.
   - Skill icons / exclusive weapon tags can confirm identity for known kits.

## Known reference identifications

| Date | Context | Heroes |
|---|---|---|
| 2026-08-06 | Martin's home-defense trio (the 2026-08-05 stat-panel screenshots; portraits badged 15) | **Hank** (Gen-15 Infantry), **Estrella** (Gen-15 Lancer), **Viveca** (Gen-15 Marksman) |
| 2026-03 (corpus report_004/005) | Martin's earlier defense trio | Gisela (G13 Inf), Flora (G13 Lan), Ligeia (G12 MM) |

## Notes

- Generation ↔ injection pairs live in `HERO_GEN_STAT` (gens 1–15 as of 2026-08).
- If a badge number exceeds the table (new generation released), add the hero names to
  `hero_generations.json` from the wiki BEFORE identifying, and extend HERO_GEN_STAT only
  with measured values (no-fudge rule).
- Used by: stat-panel decomposition (`docs/STAT_PANELS_FORMULA.md` §6 U-block), battle-report
  ingestion (hero fields), OCR hero-panel parsing.
