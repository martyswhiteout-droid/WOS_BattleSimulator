# Engine-Rules Review — wiki/game mechanics vs codified combat rules

**Scope:** `GAME_RULES.md` (the project's source-of-truth combat rules) + the live
resolver (`pvp_turn_engine.py`) + the derived Stage-6 law, checked against the
game's documented mechanics (community/CS sources recorded in §4) and the
reverse-engineered corpus. Companion to `HERO_SKILL_AUDIT.md` (which covered
per-hero skills); this covers the combat SYSTEM rules. 2026-07-25.

## Findings (most consequential first)

### R1 [HIGH] `def_k=0.45` breaks the engine's own SYMMETRY corollary (reworded per QA)
The engine IS simultaneous — that part of §4 is implemented correctly. What `def_k`
violates is the **corollary**: §4 says "with exactly equal stats a battle is a mutual
annihilation," but `def_k=0.45` scales defender damage down, so a perfect mirror is an
attacker sweep instead of a mutual wipe. It breaks **symmetry** and the no-fudge rule,
not simultaneity itself. (Magnitude is scenario-dependent — the backtest shows ~58%
mirror survivors, not a fixed number; don't hard-code one.) This stays a real defect
to remove, but **not via a blind one-line `def_k=1.0` edit** — the backtest earlier
showed that scores 6/13 and fails the guardrail. It's replaced by measured physics
(Stage 8.2), not re-tuned.

### R2 [HIGH] GAME_RULES §4 battle formula is STALE — but update it WITH SCOPE (per QA)
§4 records the damage formula as **UNKNOWN**, listing hypotheses H1/H2 "to be
FITTED." Stages 1–6 DERIVED it: `turns = K(dealer,target)·(D·H)/(A·L)·G_w·G_l/√N`,
HP=D·H, counters folded into K. But the doc must record it as **exact only within its
validated domain** — single-troop, tier ≤6, FC<3, hero allowlist, no proc unlocks —
and explicitly keep **OPEN/unknown** status for Type-2 (procs), high-tier, and the
unresolved multi-class regimes. Update the doc, but do not overclaim the formula as
globally solved.

### R3 [RETRACTED — I was wrong; QA correct]
I claimed the widget role asymmetry (garrison 3 widgets, rally 2) is unmodelled and a
candidate to replace `def_k`. **Both parts are wrong.** The turn engine DOES select
GARRISON/RALLY context per side (`pvp_turn_engine.py:709`), filters widget rows by it,
and suppresses widgets already in the panel — and it's tested
(`test_pvp_turn_engine.py:926`). And the effect is small (one extra ±15% widget), not
remotely large enough to stand in for `def_k=0.45`. **Retracted.** The only genuine
residual is that the NEW `hero_kit` doesn't model widgets yet (a known scope gap for
Stage 8.3), which is minor and unrelated to the role-effect story.

### R4 [REWRITTEN per QA — I mis-stated the open question]
I called cross-hero stat composition "unresolved." It is NOT — **GAME_RULES §6l
(line 722) closes it: distinct hero stat skills are MULTIPLICATIVE, explicitly
superseding §2's additive wording.** The engine multiplying distinct skills is
correct. The REAL, narrower defect: **duplicate copies of the SAME joiner skill must
stack ADDITIVELY** (§3: "duplicates stack additively") — 4×+25% should give **+100%**,
but the engine multiplies every hero stat row (`pvp_turn_engine.py:871`), producing
`1.25⁴−1 = +144.14%`. The existing duplicate-joiner test only proves copies aren't
deduplicated; it does NOT verify the additive magnitude. Fix: make duplicate-same-skill
composition additive and add a magnitude test. (This is engine work, not hero_kit.)

### R5 [MED] Joiner role is not modelled in the hero interface
§3: a **joiner** contributes ONLY its slot-1 hero's FIRST skill (cap 4, duplicates
additive); a **captain** fires all 3 skills + widgets. The new `Hero.resolve()`
always emits all declared skills regardless of role. Engine integration (8.3) must
make resolution role-aware (S1-only for joiners) or the joiner contribution will be
3× too large. Not a rule error — an integration gap to encode.

### R6 [MED] Cadence unit ("Attacks" vs "Strikes") is ambiguous at army scale
The measured every-5→6 correction (Vulcanus S2) was taken in a **single-class 1v1**,
where "attacks" and "strikes" coincide. §3 distinguishes them: **Attacks** = all
own-side class attack events (3/turn in a full army); **Strikes** = the skill's own
class only. For a 3-class army, "every 5 attacks" and "every 5 strikes" fire at very
different rates. Which counter Vulcanus/Eleonora/Gwen/Hank/Nora use is unresolved —
needs an army-scale capture (Stage 8.0), and the `hero_kit` `attacks()` helper
should not be assumed correct for multi-class armies yet.

### R7 [MED] Troop skills carry the same EV-averaging the heroes did
§5 encodes troop procs as averages — Crystal Shield "−13.5 flat" (=0.375×36),
Flame Charge "DD +0.1125" (=0.375×0.30), Crystal Lance "DD +0.15". §3 says the
engine SHOULD compute from raw fields (probability/amount/cadence) and treat the
average as display-only, and `models.TroopSkill` does store the raw fields — but the
troop-skill layer needs the same audit-and-de-fudge pass the heroes just got, to
confirm the live path uses raw proc% + real cadence, not the averages.

### R8 [LOW, positive] The derived law AGREES with the community/wiki kernel (H1)
§4's H1 ("ratio kernel", kingshotguides/Reddit): `kills ≈ k·N^0.5·(A·L)/(D·H)`.
The reverse-engineered law's within-tier form `A·L/(D·H)` and √N offense **match H1
exactly** — independent corroboration that the empirical derivation landed on the
community-consensus mechanic. Note H2 (WoS customer-service "Lethality = TRUE
damage that ignores Defense") was NOT adopted; the corpus favoured H1. If the game
actually uses H2 semantics for some interaction (defence-ignoring lethality), a few
edge cases could differ — worth a targeted check, but H1 is empirically supported.

### R9 [LOW] Two troop-stat sources can diverge
`troop_catalog.py` (legacy, the T11 tables in §1) vs `docs/TroopStats/…T1-T10.json`
(used by the deterministic law). The law path reads docs/TroopStats ONLY. They must
be reconciled or the divergence documented so the two engines don't disagree on base
stats.

### R10 [LOW] Unresolved contradiction still parked in the rules
§5 flags "Body of Light — see contradiction A" (Defense +4%/6% plus extra damage
reduction while Crystal Shield active) as an open contradiction. Still unresolved in
the doc; relevant once the FC8/FC10 Infantry skills enter the proc layer.

## Cross-cutting conclusion (revised after QA 2026-07-25)
The rules doc is largely sound and — importantly — the **derived law matches the
community formula (R8)**, strong validation. Two of my original findings were wrong
and are corrected above: **R3 retracted** (widget context IS modelled + tested) and
**R4 rewritten** (cross-skill multiplication is settled by §6l; the real defect is
duplicate-same-skill additivity). The material problems that remain: (1) `def_k` breaks
the equal-stats symmetry corollary, to be replaced by measured physics not re-tuned
(R1); (2) the rules doc must be updated with the derived law, scoped to its validated
domain (R2); (3) duplicate-same-skill stat stacking should be additive but the engine
multiplies it (R4-real). R5–R7 remain integration/de-fudge tasks for Stage 8.3.
