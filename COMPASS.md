# COMPASS.md — WoS Battle Simulator

**Status:** CURRENT · **Created:** 2026-07-29 · **Owner:** Martin
**Type:** Direction doc. Stable across sessions. Revised deliberately, not incidentally.

---

## 0. What this doc is for

Every other doc in this repo answers *how* or *what next*. They go stale — that is expected and fine. This one answers **why, for whom, what counts as good, and what we refuse to do.** Those should barely move.

Think of it as the difference between a compass and a map. The map (`ROADMAP.md`, `PRODUCTION_PLAN.md`, `STATUS.md`) gets redrawn every time the terrain changes. The compass does not. When a session opens and the maps disagree with each other — and right now several of them do — the compass is what tells you which way is still north.

**This doc does not override operational policy.** Precedence, highest first:

| Rank | Authority | Governs |
|---|---|---|
| 1 | `ENGINE_REBUILD/ENGINE_CHANGE_CHECKLIST.md` | Engine change legality (no-fudge rule) |
| 2 | `PRODUCTION_CRITERIA.md` | What may enter WOSTests.com |
| 3 | `CLAUDE.md` / `AGENTS.md` | Binding session rules for agents |
| 4 | **COMPASS.md** (this doc) | Direction, scope boundaries, definition of good |
| 5 | `CONTEXT_INDEX.md` | Which doc to read for a given topic |
| 6 | Everything else | Detail, history, working notes |

If this doc ever contradicts ranks 1–3, ranks 1–3 win and **this doc is the one that is wrong** — fix it here.

---

## 1. True north

> **Build the tool that tells a Whiteout Survival player the truth about a fight they have not yet committed to — including the truth that it is too close to call.**

The product is not "a battle calculator." Calculators already exist and they lie confidently. The asset being built here is a **reverse-engineered combat model plus the discipline to state its own uncertainty.** Honesty is the moat, not accuracy alone — a 70%-accurate model that flags its own 30% is more valuable, and more defensible commercially, than a 90%-accurate model that never admits doubt.

---

## 2. Who it serves, and the pain underneath

The stated user need is "will I win this rally?" That is the surface request. The thing actually being bought is different, and it matters for how the product is framed, priced and marketed.

| Audience | Surface ask | **Underlying pain** |
|---|---|---|
| Rally leader (R4/R5, alliance officer) | "Should I call this rally?" | *Being the one who burned the alliance's troops.* In alliance-heavy servers — which is most of them, and especially so on CN/SEA servers where alliance standing is social capital, not just a game stat — a failed rally is a public, named, reputational event. The fear is not lost troops. It is losing face in front of people you speak to daily. |
| Joiner / mid-spender | "Is it worth me joining?" | *Sunk cost anxiety.* They have spent real money on heroes and gear and have no way to know if it did anything. They want proof their investment converts into outcomes. |
| Whale / top-tier | "Which formation and joiners maximise this?" | *Optimising an expensive position.* Their pain is decision fatigue over a large combinatorial space, not affordability. |
| Martin (today, the only user) | "Is my model right yet?" | *Not shipping something that misleads people.* The engineering standards in this repo exist because of this. |

**Framing rule that follows from this:** market outcomes and confidence, never mechanics. "Know before you commit" beats "Monte-Carlo combat simulation with per-proc kill attribution." The mechanics are the proof, not the pitch.

**Cultural note worth holding onto:** most public WoS strategy content is English-language and creator-driven, and much of the western guidance assumes a solo-optimiser player. The dominant real-world use is *coordinated alliance play*. Anything designed as a lone-player tool will underperform against something that fits the "I need to justify this call to my alliance" moment — a shareable, screenshot-able verdict is likely worth more than a deeper solo optimiser. This is an assumption, not a finding; it has not been tested with real players.

---

## 3. What "good" means here

Good is defined by an **honesty ladder**, not a single accuracy number. A prediction may only claim the rung it has actually earned.

| Rung | Claim the product may make | Earned when |
|---|---|---|
| 4 — Certified | "This side wins, with this casualty band." | Type-1 exact fit, zero fudge; distribution-validated on Type-2; QA PASS |
| 3 — Ranked | "This side is favoured / option A beats option B." | Winner + ordering hold on the anchor set |
| 2 — Hedged | "Too close to call." | Genuine near-mirror; coin-flip flag shown |
| 1 — Out of regime | "Outside what has been validated." | Matchup falls outside any calibrated band |
| 0 — Silent miss | *Never acceptable.* | Confident, wrong, unflagged |

**Where the engine actually sits today (2026-07-29, from `STATUS.md` §23 and `ENGINE_REBUILD/QA_REPORT.md`):**

- Golden anchor set: **7 of 13 real battles** called correctly. All 6 misses are upsets. **2 of them (RAW_03, RAW_04) are rung-0 silent misses** — the single most important defect in the product.
- A `def_k` sweep across the full set peaks at 8/13. The misses are therefore **structural, not tunable**. No amount of parameter fitting fixes this; a mechanic is missing.
- QA certification is **CONDITIONAL** — winner/ranking only, on anchors A1–A4. Survivor magnitudes in near-even fights are *not* certified.
- The narrow `pvp_kernel` regime (50/50 comp, T10-vs-T7, attacker wipe) is genuinely solved and does **not** unify with the general engine. Two uncoupled regimes.
- Everything outside that band runs `calibrated=False, model_error=0.5` — a placeholder floor, not a real uncertainty band.
- `SKILL_SOURCE_AUDIT`: 18 of 145 hero-skill checks disagree with the wiki. Gate G10 **FAILS**.

The app layer, seam, profile schema, UI and telemetry are built and working end-to-end. **The engine is the only hard problem left.** Do not let UI or SaaS work create the impression of progress toward north.

---

## 4. Invariants

These hold regardless of plan, phase or deadline. Each is stated as the plain-English risk it prevents.

1. **No fudge factors.** *Risk it prevents:* a number tuned to make yesterday's eight battles look right will confidently mislead on the ninth. Type-1 (deterministic) reports are the only legitimate exact-fit targets and must fit with zero fudge. Type-2 (procs) is validated by distribution only, never regression-fit.

2. **The backtest ratchet only turns one way.** *Risk:* silently trading a fix for a break. `py -m wos_sim.backtest` before any engine/`TURN_PARAMS` change lands; pass count may only increase (gate G12).

3. **Hedging is a feature, not a bug.** *Risk:* someone "fixes" the coin-flip label and destroys the only thing that makes the product trustworthy. Near-even battles are genuinely chaotic. Never manufacture false precision — including never rendering a band off an uncalibrated `model_error`.

4. **Production is empty until it earns otherwise.** *Risk:* WIP leaking into something users pay for. `WOSTests.com` receives a release only after an independent QA agent's written **PASS** (CONDITIONAL is a polite FAIL) *and* Martin's explicit sign-off. Inferred approval never counts. Nothing is ever copied there "to populate it."

5. **The prototype stays a prototype.** *Risk:* auth, billing and paywall code strangling the experimental loop that is still doing the real work. No auth/paywall/DB code enters `wos_sim/` or `prototype/`; commercial code lives ONLY in the isolated `shell/` directory (added 2026-08-04 by Martin's directive — it imports the seam, never the reverse, and never edits prototype files). The production 5,000-troop minimum is **never** back-ported into the prototype — micro-battles are the research method.

6. **The formula is the product; assume the client is hostile.** *Risk:* the model being extracted by exactly the method used to build it. Engine server-side only, minimum battle size enforced server-side, layered rate limits, minimal output surface, no raw telemetry endpoints.

7. **Newest dated doc wins.** *Risk:* an agent confidently acting on a superseded plan. Several docs in this repo are known traps (see `CONTEXT_INDEX.md` §6). Route lookups through the index; do not read docs wholesale.

8. **Never fabricate an input.** *Risk:* an OCR guess propagating into a verdict a player acts on. Unreadable field returns `null`, flagged for confirmation.

---

## 5. Non-goals

Explicitly not being built, so nobody has to re-litigate it:

- Live game integration or automated troop deployment.
- Battle types beyond rally/garrison in the UI (engine may support them; UI does not target them).
- Multi-rally / reinforcement-timing simulation.
- The G1 optimiser **as a paid feature** — the engine is not certified for it. It remains an internal/prototype capability.
- Alliance/team tier, mobile app, UI localisation, referral system, admin dashboard beyond Supabase console + logs.
- Multi-region scale, or defending a serious DDoS on a single VPS.

---

## 6. Position, and the road

| Track | State | Next move |
|---|---|---|
| Engine | 7/13, structural misses, CONDITIONAL cert | First-principles formula derivation via controlled NanoMart/MiniMart experiments (`ENGINE_REBUILD/DEEPSEEK_FORMULA_DERIVATION_BRIEF.md`) |
| Data | 13 anchors, **every one a wipe** | Get at least one **non-wipe / close fight** — wipes censor the loser's damage output, which is why the upsets are unexplainable |
| App / UI | Built end-to-end, working | Hold. Do not add surface area while the engine is uncertified |
| Skill data | 18/145 wiki mismatches, G10 FAIL | Reconcile — cheap, and it may be quietly causing some of the 6 misses |
| Commercial shell | **BUILD IN PROGRESS** (Martin's 2026-08-04 directive; red-team skipped for the build, to be run against the built shell pre-launch). Code in `shell/`, mock-first, nothing deployed | Martin: register accounts (`THIRD_PARTY_SETUP.md`), review `DECISIONS_2026-08-04.md`. **LAUNCH stays blocked** behind QA gate PASS + sign-off + D4 certify-narrow scoping |

**Sequencing principle:** the engine gates everything downstream. Building the paid shell before the engine can be certified means building a payment system for a promise that cannot yet be kept. The one exception is Phase 0 of the production plan (verify Hostinger is actually a VPS, register accounts) — cheap, and it de-risks a decision that would otherwise be discovered late.

---

## 7. Decisions that are yours, not an agent's

| # | Decision | Recommendation | Pros | Cons / risk |
|---|---|---|---|---|
| D1 | **Run the controlled non-wipe experiment campaign?** (~15–25 rallies, incl. an N-ladder and one deliberately close fight) | **Yes — do this first** | The only known route past the 7/13 structural ceiling. Everything else is blocked on it. It is small, not the ~150-battle campaign once feared | Costs real in-game troops and calendar time. No guarantee the missing mechanic falls out of it |
| D2 | **Free vs paid quotas** — `PRODUCTION_CRITERIA.md` says ≤20/day free, ≤200/day paid; `PRODUCTION_PLAN.md` says 5/day free, ~100/day paid. Same date, different numbers | Reconcile to **one** number now and record it here. Suggest the *lower* pair (5 / 100) — anti-extraction is the binding constraint, not generosity | Removes a contradiction before it becomes code. Tighter default is easier to loosen later than to tighten | Too tight a free tier may kill trial conversion. Untested either way |
| D3 | **Approach Century Games, or stay quiet?** | **Ship IP-clean first, decide after.** Replace scraped portraits/icons with original assets and add the disclaimer regardless — that is required either way. Hold the letter | Removes the actual liability without inviting a response you cannot control | Silence is not consent; they could still act. A letter could equally provoke a demand rather than permission |
| D4 | **Certify narrow, or wait for general?** Ship paid coverage only for the validated band, or hold until the general engine works | **Certify narrow.** Sell what rung 3–4 covers, show rung 1 honestly elsewhere | Consistent with the honesty moat. Gets real user feedback years earlier | Small addressable slice at launch. Requires the UI to be very clear about regime, or trust is lost immediately |
| D5 | **Reconcile `BRD.md` to the commercial reality?** It still describes a single-user CLI/JSON tool for you alone | **Yes — add a supersession banner**, as `ROADMAP.md` already has. Do not rewrite it | Cheap. Stops future agents building to a superseded spec | Ten minutes of work, easy to keep deferring |

---

## 8. Doc map (short form)

`CLAUDE.md` → agent entry point · `CONTEXT_INDEX.md` → topic router with currency ratings · `TOOLS.md` → every command · `GAME_RULES.md` → mechanics source of truth · `ENGINE_INTERFACE.md` → the `api.py` seam contract · `PRODUCTION_CRITERIA.md` → the release gate · `ENGINE_REBUILD/` → current engine work.

**Known traps** (do not trust at face value): `ENGINE_REBUILD/00_HANDOVER.md` says "SPEC ONLY" — false, the turn engine is built and default. `ENGINE_REBUILD/07_CONTROLLED_EXPERIMENTS.md` headline `km` change was reverted. `STATUS.md` header date and §22 joiner-dedup claim are both wrong. `ROADMAP.md` engine track is superseded. `BRD.md` accuracy framing is optimistic.

---

## 9. Revision rule

Revise this doc when direction genuinely changes — a non-goal becomes a goal, an invariant is retired, a decision in §7 is made. Do **not** update it for progress; that is `STATUS.md`'s job. Every revision: bump the date, and note what changed and why below.

| Date | Change | Why |
|---|---|---|
| 2026-07-29 | Created | The tactical docs had drifted apart — `BRD.md` describes a single-user CLI tool, the production docs describe a paid multi-tenant service, and nothing reconciled the two. Needed a stable layer above them |
| 2026-08-04 | Shell build unblocked (§6, invariant 5 reworded); D2 decided (5/100, lower pair); D5 executed (BRD banner) | Martin's explicit directive to execute the production plan overnight. LAUNCH gating unchanged. Details: `DECISIONS_2026-08-04.md` |
