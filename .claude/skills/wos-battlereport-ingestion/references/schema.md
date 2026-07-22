# Canonical WoS battle-report JSON schema (v2)

Every ingested battle produces ONE JSON document with the top-level keys below,
**in this order**. Order is part of the contract — two engines ingesting the
same report must produce structurally identical files. Omit a key only where
marked *(conditional)*; everything else is present even if `null`.

## Top level

| # | Key | Type | Content |
|---|---|---|---|
| 1 | `schema_version` | int | Always `2` (v1 = the pre-standard ad-hoc files) |
| 2 | `_type` | str | `experiment_1v1`, `experiment_count`, `mirror_encampment`, `counter`, `beast_control`, `pvp_report`, … |
| 3 | `type` | int | `1` = deterministic (no procs), `2` = has chance procs. See troop-passives.md |
| 4 | `battle_date` | str\|null | `"YYYY-MM-DD HH:MM:SS"` as shown on the report |
| 5 | `recommended_filename` | str | Per the convention in SKILL.md |
| 6 | `setup` | str | One-sentence human description of the battle |
| 7 | `outcome` | obj | `{"winner": "attacker"\|"defender"\|"mutual", "attacker_result": "victory"\|"defeat", "defender_result": ...}` |
| 8 | `turn_inference` | obj\|null | See below |
| 9 | `attacker` | obj | Side object (below) |
| 10 | `defender` | obj | Side object — key is `defender_beast` for beast hunts |
| 11 | `notes` | list[str] | Anomalies, mismatches, context. Never empty-string padding |
| 12 | `source_images` | list[str] | What screens/pages were provided (e.g. `"battle_overview"`, `"stat_bonuses_attacker"`, `"pdf_page_3"`) |
| 13 | `_extraction` | obj | `{"extracted_by": "<agent>", "timestamp": "YYYY-MM-DD", "ocr_confidence": "high"\|"medium"\|"low", "manual_overrides": []}` |
| 14 | `_validation` | obj | `{"arithmetic_checks": "pass"\|"fail: <detail>", "missing": [<field paths>], "suspicions": [<strings>]}` |

### `turn_inference`

```json
{
  "turns": null,
  "turns_range": [81, 83],
  "method": "vulcanus_proc_count",
  "clock_hero": "Vulcanus",
  "cadence": "S3 turns 3, 6, 9, ... (phase-3, corrected 2026-07-18)",
  "trigger_count": 27,
  "assumptions": ["S3: k triggers => turns in [3k, 3k+2]",
                  "S2 (1-unit side): m triggers => turns in [6m, 6m+5]; intersect"]
}
```

`method` is `"reported"` if the report states turns directly, `"unknown"` if no
clock exists (then `turns: null` — never estimate without a stated method).

## Side object (attacker / defender)

Keys in this order:

| # | Key | Type | Content |
|---|---|---|---|
| 1 | `name` | str\|null | Player/entity name exactly as shown (keep CJK) |
| 2 | `state` | int\|null | e.g. `191` from `[RFJ]Marty 191` |
| 3 | `alliance` | str\|null | Tag like `"RFJ"` if visible |
| 4 | `coords` | str\|null | `"X:766 Y:484"` |
| 5 | `role` | str | `rally`, `garrison`, `encampment`, `attacker`, `defender` |
| 6 | `power_loss` | int\|null | Negative number as shown |
| 7 | `troops` | int | Starting troops |
| 8 | `losses` | int\|null | |
| 9 | `injured` | int\|null | |
| 10 | `lightly_injured` | int\|null | |
| 11 | `survivors` | int\|null | |
| 12 | `kills` | int\|null | If the report shows a kills figure |
| 13 | `deployed_class` | str | *(controlled fights)* `"Infantry"`/`"Lancer"`/`"Marksman"` |
| 13' | `composition` | obj | *(PvP)* `{class: {"count": n, "share": f, "fc_badge": n, "tier_level": f}}` |
| 14 | `tier_display` | str | EXACTLY as shown: `"Lv 1.0"`, `"T6 FC10"` |
| 15 | `t12_skill_levels` | obj\|null | `{"indomitable_wall": n, "meridian_phalanx": n, "starfire": n}` when visible |
| 16 | `stats_pct` | obj | `{class: {"Attack": 176.2, "Defense": 169.0, "Lethality": 109.7, "Health": 109.3}}` for ALL THREE classes as displayed (`+176.2%` → `176.2`). Beasts: `stats_pct_FLAT` `{"all_classes_all_stats": 57.0}` |
| 17 | `stats_capture` | obj | `{"attack_defense": "visible"\|"missing", "lethality_health": "visible"\|"missing", "notes": str}` — the honesty ledger for #16 |
| 18 | `lead_heroes` | obj\|null | `{class_or_slot: {"name": str, "level": int\|null, "stars": int\|null}}`; `null` if side has no heroes |
| 19 | `hero_skills` | list | One entry per hero skill: `{"hero", "slot", "name", "level", "effect", "triggers", "kills", "status": "identified"\|"uncertain"}` |
| 20 | `troop_passives_active` | list | DERIVED (see troop-passives.md): `{"class", "skill", "unlock", "effect", "applies_in_this_battle": bool, "reason": str}` — one entry per unlocked skill, including the ones that do NOT apply |
| 21 | `specials` | list | `{"label", "value", "source": "item"\|"widget"\|"pet"\|"appointment"\|"title", "stat", "applies_to": "own"\|"enemy"}` |
| 22 | `participants` | list | *(PvP, conditional)* `{"player", "is_captain": bool, "flag_hero": str\|null, "troops", "kills", "power_loss", "rows": [{"troop_type", "fc_badge", "kills", "losses", "injured", "lightly_injured", "survivors"}]}` |
| 23 | `joiner_flags` | list | *(PvP, conditional)* flag-hero names in slot order, duplicates KEPT (duplicates stack) |
| 24 | `per_unit` | obj | *(beast, conditional)* per beast unit `{class: {"start", "kills", "losses", "injured", "lightly_injured", "survivors"}}` |

## Arithmetic identities (the validator enforces these)

- `troops == losses + injured + lightly_injured + survivors` (each side, when all present)
- `side.kills == opponent.losses + opponent.injured` (warning-level; held on every
  controlled report so far — a mismatch usually means an OCR digit error)
- `composition` shares sum to ~1.0; `participants`/`per_unit` rows sum to side totals
- `turns` within `turns_range`

## Determinism rules

- Numbers are JSON numbers, never strings; percentages recorded as displayed
  (`176.2`, not `1.762` — the engine divides by 100 at load time).
- Key order per the tables above. No extra ad-hoc keys — if a report shows
  something the schema lacks, put it in `notes` and tell Martin the schema may
  need a version bump.
- Unknown → `null` plus a `_validation.missing` entry. NEVER a guessed value.
- One battle = one file. A PDF of 15 reports = 15 files.

## Worked example (real battle — beast control, verified)

```json
{
  "schema_version": 2,
  "_type": "beast_control",
  "type": 1,
  "battle_date": "2026-07-08 21:37:45",
  "recommended_filename": "Mueller_Beast_20kLv1InfvTitanRocLv18.json",
  "setup": "20,000 Lv 1.0 Infantry attacker vs Lv.18 Titan Roc beast (8,645 in 3 Lv 6.0 units), deterministic.",
  "outcome": {"winner": "defender", "attacker_result": "defeat", "defender_result": "victory"},
  "turn_inference": null,
  "attacker": {
    "name": "[RTS]Colonel Müller",
    "state": null,
    "alliance": "RTS",
    "coords": "X:767 Y:486",
    "role": "attacker",
    "power_loss": -120,
    "troops": 20000,
    "losses": 0,
    "injured": 40,
    "lightly_injured": 19960,
    "survivors": 0,
    "kills": 1469,
    "deployed_class": "Infantry",
    "tier_display": "Lv 1.0",
    "t12_skill_levels": null,
    "stats_pct": {
      "Infantry": {"Attack": 181.3, "Defense": 153.0, "Lethality": 112.0, "Health": 108.7},
      "Lancer":   {"Attack": 184.6, "Defense": 150.7, "Lethality": 105.3, "Health": 102.6},
      "Marksman": {"Attack": 185.6, "Defense": 155.7, "Lethality": 121.2, "Health": 118.6}
    },
    "stats_capture": {"attack_defense": "visible", "lethality_health": "visible", "notes": ""},
    "lead_heroes": null,
    "hero_skills": [],
    "troop_passives_active": [
      {"class": "Infantry", "skill": "Master Brawler", "unlock": "T1",
       "effect": "+10% attack damage to Lancers",
       "applies_in_this_battle": true, "reason": "beast fields a Lancer unit"}
    ],
    "specials": []
  },
  "defender_beast": {
    "name": "Lv.18 Titan Roc",
    "coords": "X:755 Y:494",
    "role": "defender",
    "power_loss": -29380,
    "troops": 8645,
    "losses": 1469,
    "injured": 0,
    "lightly_injured": 0,
    "survivors": 7176,
    "kills": 40,
    "tier_display": "Lv 6.0",
    "stats_pct_FLAT": {"all_classes_all_stats": 57.0},
    "stats_capture": {"attack_defense": "visible", "lethality_health": "visible",
                      "notes": "beast panel shows flat +57.0% on every row"},
    "lead_heroes": null,
    "hero_skills": [],
    "troop_passives_active": [
      {"class": "Infantry", "skill": "Master Brawler", "unlock": "T1",
       "effect": "+10% attack damage to Lancers",
       "applies_in_this_battle": false, "reason": "attacker has no Lancers"},
      {"class": "Lancer", "skill": "Charge", "unlock": "T1",
       "effect": "+10% attack damage to Marksmen",
       "applies_in_this_battle": false, "reason": "attacker has no Marksmen"},
      {"class": "Marksman", "skill": "Ranged Strike", "unlock": "T1",
       "effect": "+10% attack damage to Infantry",
       "applies_in_this_battle": true, "reason": "attacker fields Infantry"}
    ],
    "specials": [],
    "per_unit": {
      "Infantry": {"start": 2595, "kills": 5,  "losses": 1469, "injured": 0, "lightly_injured": 0, "survivors": 1126},
      "Lancer":   {"start": 3025, "kills": 14, "losses": 0, "injured": 0, "lightly_injured": 0, "survivors": 3025},
      "Marksman": {"start": 3025, "kills": 21, "losses": 0, "injured": 0, "lightly_injured": 0, "survivors": 3025}
    }
  },
  "notes": [
    "Attacker only reached the beast's front Infantry unit (frontline absorption); Lancer/Marksman untouched.",
    "kills cross-check: attacker.kills 1469 == beast.losses 1469; beast.kills 40 == attacker.injured 40."
  ],
  "source_images": ["battle_overview", "troop_power_comparison", "stat_bonuses", "battle_details"],
  "_extraction": {"extracted_by": "claude", "timestamp": "2026-07-09", "ocr_confidence": "high", "manual_overrides": []},
  "_validation": {"arithmetic_checks": "pass", "missing": [], "suspicions": []}
}
```
