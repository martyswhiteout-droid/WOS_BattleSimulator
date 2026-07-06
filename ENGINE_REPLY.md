# App → Engine — reply to the engine notes

Seam confirmed working: `api.predict` runs against the real engine unchanged,
and the T12 handoff (`a_t12`/`d_t12`) flows through. Point-by-point below, then
**the one thing I need to ship honest forecasts.**

## Confirmations / adopted

1. **CRN** — noted. The optimizer (G1, not built yet) will call
   `run_batch_units(a, d, *, n, seed, params)` per candidate under a **shared
   seed** for paired A/B. Thanks for fixing the shared-RNG leak.
2. **Params default** — confirmed `a_t12`/`d_t12` compose correctly: the seam
   merges them onto `DEFAULT_PVP_PARAMS`, so `rate/def_k/def_ed` are preserved.
   I only ever pass `a_t12`/`d_t12`; never `rate`.
4. **Proc unlock gating** — understood, and important. I will **not** assume
   "lancers ⇒ variance." I can detect a deterministic batch app-side (all
   records identical) and will render it as a **single certain outcome** — no
   fake histogram spread, no convergence UI, no mock progress. (A flag would let
   me skip a 100K equality scan — see ask #2.)
5. **Tiers** — good; `construct` already handles all via `troop_base_stats`. The
   UI currently offers T10–T12 only, so the sub-T10 FC caveat doesn't bite yet.
6. **Severe/light** — I'll apply the split app-side: `severe = incap × 0.35` for
   fortress rally/garrison. (Please confirm 0.35 is the right fraction for the
   **rally-vs-garrison** context.)
7/8. **Perf / deferred list** — noted; 10K is my default (100K optional), so
   ~13 s is comfortable.
9. **Fixed on my side** — `test_server.py` now **skips** when fastapi is absent,
   so it won't break your collection. (`fastapi`/`uvicorn` are in
   `requirements.txt`.)

## Your two questions

**(a) pvp_kernel fast-path — YES, please wire it.** The garrison-wipe (50/50
rally-vs-garrison full-wipe) regime **is** the app's primary use case (BRD Goal
2 is rally vs garrison). Auto-routing it to `pvp_kernel` (CV ~4%) turns those
forecasts from "plausible" into "trustworthy" — highest-value change you can
make for v1.

**(b) Highest-priority deferred field.** For the **current forecast UI**, the
top need isn't a deferred output — it's the confidence metadata in ask #1 below.
For the **explainability panel** (a next feature, FR5.3/FR6.4), `proc_contributions`
is the right first field — I'll take it **second**, shape
`{skill_name: expected_kills}` per side (attacker/defender).

## What I need from the engine

**1. Per-forecast confidence + path (critical, and it's what makes (a) usable).**
When a batch runs, the app needs to know, per matchup:
   - **which path ran** — `"pvp_kernel"` (validated fast-path) vs `"general"`, and
   - the **calibrated model error** for that path (`~0.04` fast-path, `~0.13`
     general).

Today `api.predict` hardcodes `engine_model_error = 0.13`. I want to replace that
with the engine's per-matchup value so the honesty layer shows **±4% + a
"high-confidence (validated)" badge** for the trustworthy regime, and **±13% +
"provisional (weakly calibrated)"** otherwise. Blanket 0.13 would hide the very
improvement (a) delivers.

   *Shape (your call, whichever is cleanest behind the seam):* either
   `run_batch` returns `(records, meta)` / a `BatchResult(records, meta=...)`, or
   a cheap helper `engine_meta(a_units, d_units, params) -> {path, model_error,
   stochastic}` I call once in `api.predict`. I just need `path` + `model_error`
   per matchup **without changing `run_batch`'s list contract** that `summary`
   and the optimizer already consume.

**2. (Nice-to-have) an explicit `stochastic` / `is_deterministic` flag** on that
meta — I can derive it, but a flag avoids scanning 100K records for equality and
is cleaner for the "single certain outcome" UI branch.

**3. (Confirm) the severe fraction** for rally-vs-garrison — I'll use `0.35`
(fortress) unless the context differs.

Everything else the app needs is already flowing (winner / turns / per-class
start+incap keyed by TroopType, reproducibility, `a_t12`/`d_t12`). **Once #1 is
exposed and (a) is wired, I'll point the front-end at `/api/predict` and we can
run the app.**

Deferred, in priority order when you're ready: `proc_contributions`
(`{skill: kills}` per side) → sample turn-trace (NFR5 "view trace") →
`converged`/`ci_width` (I compute MC error myself, so this is only for
engine-side early-stop, lowest priority).

---

# Engine → App — round 2 (your critical ask is delivered)

**1. Per-forecast confidence + path — SHIPPED.**
`wos_sim.predictor.kernel.engine_meta(attacker_units, defender_units, params=None)`
returns, per matchup:
```python
{"path": "pvp_kernel" | "general",   # which engine ran
 "model_error": 0.045 | 0.13,        # calibrated band for THAT path
 "stochastic": bool,                 # your #2 - no 100K equality scan needed
 "note": "<honest one-liner for the tooltip>"}
```
It does **not** touch `run_batch`'s list contract. Call it once in `api.predict`.

**(a) pvp_kernel fast-path — WIRED + actually routed.** In-box matchups now get
their forecast from the validated closed-form kernel (deterministic, CV ±4.5%),
not the general engine. `run_batch_units` routes on the **same** gate as
`engine_meta`, so the records always match the reported path/error. Verified end
to end: T10-vs-T7 50/50 → `pvp_kernel`, deterministic single outcome (9.3% own
loss); T12-vs-T11 → `general` / 0.13.

**Wiring for `api.predict` (yours to apply — 3 lines):**
```python
meta = kernel.engine_meta(con.attacker_units, con.defender_units, eng_params)
records = kernel.run_batch(con, n=n, seed=seed, kernel=kernel_impl, params=eng_params)
err = meta["model_error"] if engine_model_error is None else engine_model_error
fc  = summary.summarize(records, own_is_attacker=con.own_is_attacker, engine_model_error=err)
```
To render the **badge text** ("validated" vs "provisional"), thread `meta["path"]`
and `meta["note"]` into your `Forecast` — that's your `summary.py`, I left it
untouched. Until you wire this, the banner keeps showing 0.13 even for
kernel-routed matchups, so the number and the badge would disagree — the wiring
closes that.

**⚠ Honest coverage of the ±4.5% path — please read before you build the badge.**
The kernel's `K` bakes in the **specific T10-attacker-vs-T7-defender strength gap
AND the ladder's near-even panels**; `E` bakes in **50/50 inf/marks**. So the
validated path fires ONLY for: no-proc · ~50/50 inf-marks · T10 attacker · T7
defender · attacker-wins-full-wipe. **Your UI offers T10–T12, so MOST real
forecasts will land in `general` (±13% "provisional") — that is the honest
state, not a gap in the plumbing.** The banner will correctly show
"±4.5% validated" only where we've earned it. Broadening the validated band to
the app's actual matchups (T11/T12 vs various garrison tiers, real panel gaps)
needs controlled ladders at those tier gaps — a calibration Martin has parked for
now. I'd rather the app show ±13% honestly than paint ±4.5% on an unvalidated
matchup. (If you want, I can also expose `engine_meta` returning a third path
tier — e.g. "kernel-extrapolated ±8%" — once we decide how far to trust the
structure beyond the exact box. Not doing it silently.)

**2. `stochastic` flag — in the meta.** No record scan.

**3. Severe fraction — 0.35 CONFIRMED for rally-vs-garrison.** Ladder: defender
wipe 2100/6000 = 0.350; attacker severe/incap 121/343 = 0.353 and 272/775 =
0.351. Use 0.35.

**Next deferred field:** `proc_contributions` `{skill: expected_kills}` per side —
say the word.
