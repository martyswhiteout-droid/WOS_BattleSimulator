# Independent QA Findings - 2026-07-04

Scope: adversarial review from the attached prompt. I treated docs/comments as claims, re-derived the core PvP kernel from JSON, ran the requested commands, and avoided workbook edits.

Commands run:
- `py -m wos_sim.regression` -> all green
- `py -m pytest wos_sim/predictor/tests/ -q` -> 37 passed, 3 skipped
- `py -m wos_sim.pvp_kernel` -> self-test OK
- `py -m wos_sim.proc` -> ran, but its printed metric is saturated/no-variance for attacker incap
- `py -m wos_sim.pvp_calibrate` -> 4/8 winner accuracy, 2/6 holdout accuracy

## Findings

### Critical - `wos_sim/predictor/kernel.py:113`
Fast-path gate admits out-of-regime matchups and assigns validated `pvp_kernel` confidence.

Reproduction:
```powershell
@'
from wos_sim.models import TroopType, StatType
from wos_sim.pvp_engine import Unit
from wos_sim.predictor.kernel import engine_meta, run_batch_units, BatchKernel
A,D,L,H=StatType.ATTACK,StatType.DEFENSE,StatType.LETHALITY,StatType.HEALTH
INF,MAR=TroopType.INFANTRY,TroopType.MARKSMAN
def u(t,tier,n,atk=100,df=100,le=100,hp=100):
    return Unit(t,tier,float(n),{A:atk,D:df,L:le,H:hp},10.)
a=[u(INF,10,3000,1,1,1,1), u(MAR,6,3000,1,1,1,1)]
d=[u(INF,7,3000,1e6,1e6,1e6,1e6), u(MAR,6,3000,1e6,1e6,1e6,1e6)]
print(engine_meta(a,d,None))
print(run_batch_units(a,d,n=1,seed=1)[0])
print(run_batch_units(a,d,n=1,seed=1,kernel=BatchKernel())[0])
'@ | py -u -
```
Observed: `engine_meta` returns `{'path': 'pvp_kernel', 'model_error': 0.045, ...}` and the default route predicts attacker win with defender fully wiped. The general engine, using the supplied stats, predicts defender win on turn 1.

Why it matters: `GAME_RULES.md:857` says the validated regime is 50/50 composition, T10-vs-T7 tier gap, no proc/RNG, and no extrapolation. `_kernel_box` only checks attacker infantry fraction and infantry tiers (`kernel.py:134-139`); it ignores defender composition, marksman tiers, effective stats/panel strength, DD/DT, and the presence of non-proc T6 lancers. This can put the UI's "validated +/-4.5%" badge on matchups that are plainly outside the calibration data.

### High - `wos_sim/predictor/kernel.py:32`
General path reports `engine_model_error=0.13` despite holdout misses far larger than 13%.

Reproduction:
```powershell
py -m wos_sim.pvp_calibrate
```
Observed:
- winner accuracy `4/8`, only `2/6` on holdouts
- `report_004`: defender incap `118,399` predicted vs `1,771,872` observed
- `report_005`: defender incap `235,997` predicted vs `1,771,872` observed
- `report_007`: defender incap `164,521` predicted vs `1,340,639` observed

Why it matters: `api.predict` passes `engine_meta(...).model_error` into the forecast (`api.py:24-30`). A fixed `0.13` is not defensible for the broad "general" path; the current holdout errors include wrong winners and 80-90% casualty misses. The docs call it provisional, but the numeric band is still surfaced as if calibrated.

### Medium - `wos_sim/predictor/kernel.py:173` and `wos_sim/predictor/kernel.py:238`
Deterministic batch returns alias the same mutable `RunRecord` object `n` times.

Reproduction:
```powershell
@'
from wos_sim.models import TroopType, StatType
from wos_sim.pvp_engine import Unit
from wos_sim.predictor.kernel import run_batch_units
A,D,L,H=StatType.ATTACK,StatType.DEFENSE,StatType.LETHALITY,StatType.HEALTH
INF,MAR=TroopType.INFANTRY,TroopType.MARKSMAN
def u(t,tier,n): return Unit(t,tier,float(n),{A:100.,D:100.,L:100.,H:100.},10.)
recs=run_batch_units([u(INF,10,3000),u(MAR,6,3000)],[u(INF,7,3000),u(MAR,6,3000)],n=3,seed=0)
print([id(r) for r in recs])
recs[0].attacker_incap[INF]=999999
print([r.attacker_incap[INF] for r in recs])
'@ | py -u -
```
Observed: all three ids are identical; mutating record 0 mutates all records.

Why it matters: current `summary.py` is read-only, so this does not break today's UI. But the contract asks for per-run records recoverable from the batch; shared mutable records are a trap for optimizers, explainability traces, or future annotators.

### Medium - `wos_sim/data/pvp_ladder_v9c.json:8`
`att_inf_survivors` is mislabeled as total attacker survivors for the 16k and 20k rungs.

Reproduction:
```powershell
@'
import json
from pathlib import Path
d=json.loads(Path(r"wos_sim/data/pvp_ladder_v9c.json").read_text())
for i,r in enumerate(d["rungs"]):
    print(i, r["att_inf"], r["att_inf_incap"], r["att_inf_survivors"],
          r["att_inf"] - r["att_inf_incap"])
'@ | py -u -
```
Observed:
- 16k rung: `att_inf=8000`, `att_inf_incap=343`, expected infantry survivors `7657`, stored `att_inf_survivors=15657`
- 20k rung: `att_inf=10000`, `att_inf_incap=338`, expected `9662`, stored `19662`

Why it matters: the field name says infantry survivors, but the value is total survivors including untouched marksmen. Current kernel fitting uses `att_inf_incap`, so the fit is not broken. A future ingestion script that trusts the field name will fail identities or double-count marksmen.

### Medium - `wos_sim/predictor/kernel.py:214`
The batched stochastic path does not meet the 100K/<30s contract for longer-turn stochastic matchups.

Reproduction:
```powershell
@'
import time
from wos_sim.models import TroopType, StatType
from wos_sim.pvp_engine import Unit, BEST_PARAMS
from wos_sim.predictor.kernel import run_batch_units
A,D,L,H=StatType.ATTACK,StatType.DEFENSE,StatType.LETHALITY,StatType.HEALTH
INF,LN,MAR=TroopType.INFANTRY,TroopType.LANCER,TroopType.MARKSMAN
def u(t,tier,n): return Unit(t,tier,float(n),{A:100.,D:100.,L:100.,H:100.},10.)
P=dict(BEST_PARAMS); P.update({"rate":1.0,"def_k":1.0,"def_ed":1.0,"crystal_lance":0.0})
t=time.perf_counter()
run_batch_units([u(INF,10,1000),u(LN,7,1000),u(MAR,6,1000)],
                [u(INF,7,2000),u(MAR,6,2000)], n=5000, seed=1, params=P)
print(time.perf_counter()-t)
'@ | py -u -
```
Observed: 5,000 runs took about `40.9s`, projecting to roughly `818s` for 100K.

Why it matters: the default high-rate calibration often resolves in one turn and is fast, but the contract is not robust to legal params or longer stochastic fights. If optimization probes slower regimes, the current pure-Python per-turn loop will not satisfy the interface promise.

### Low - `wos_sim/troop_catalog.py:65`
`troop_base_stats` accepts negative FC levels through Python negative indexing and raises a raw `IndexError` for FC > 10.

Reproduction:
```powershell
@'
from wos_sim.troop_catalog import troop_base_stats
from wos_sim.models import TroopType
print(troop_base_stats(10, -1, TroopType.INFANTRY))
try:
    troop_base_stats(10, 11, TroopType.INFANTRY)
except Exception as e:
    print(type(e).__name__, e)
'@ | py -u -
```
Observed: `fc=-1` returns the FC10 row; `fc=11` raises `IndexError`.

Why it matters: predictor validation currently rejects FC outside 1-10, but the catalog API itself claims to serve tier configs and should fail closed with a clear `ValueError` if called directly.

### Low - `wos_sim/pvp_engine.py:112`
Ambusher gating is hard-coded as `tier >= 7` instead of using `AMBUSHER_MIN_TIER`.

Reproduction:
```powershell
Select-String -Path wos_sim/pvp_engine.py,wos_sim/proc.py,wos_sim/predictor/kernel.py -Pattern "tier >= 7|AMBUSHER_MIN_TIER"
```
Observed: `proc.py` and `predictor/kernel.py` use `AMBUSHER_MIN_TIER`; `pvp_engine.py` uses literal `7`.

Why it matters: behavior is currently consistent because the constant is 7. This is a drift risk if the unlock is corrected or made tier/FC dependent later.

### Low - `wos_sim/mechanics.py:62`
Stale cross-doc comment still says hero stat skills join the additive standard pool.

Reproduction:
```powershell
Select-String -Path wos_sim/mechanics.py,wos_sim/assemble.py,GAME_RULES.md -Pattern "hero-skill stat|skillmult|STAT SKILLS ARE MULTIPLICATIVE"
```
Observed: `assemble.py` correctly implements `skillmult` (`assemble.py:87-114`, `assemble.py:210-214`), and `GAME_RULES.md:710-716` says stat skills are multiplicative. `mechanics.py:62` still says the old additive rule.

Why it matters: this is not a runtime defect, but it is exactly the kind of stale rule note that causes future regressions.

### Low - `wos_sim/regression.py:63`
Regression tests do not guard the main failure modes found above.

Reproduction:
```powershell
py -m wos_sim.regression
py -m pytest wos_sim/predictor/tests/ -q
```
Observed: all tests pass while:
- `_kernel_box` still routes arbitrary effective stats and defender compositions to `pvp_kernel`
- deterministic batches return aliased records
- the general path still reports `0.13` despite poor holdout accuracy
- `py -m wos_sim.proc` prints zero attacker-incap spread for r004 because attacker incap is saturated, so it does not demonstrate proc variance magnitude

Why it matters: the suite proves several solved pieces, but it is weak as a guardrail for confidence routing, aliasing, and overclaiming.

## Verified Correct

- PvP kernel fit from raw data: independently extracted the 8 unique `(N_att_total, N_def_total, att_inf_incap)` points from `pvp_ladder_v9/v9b/v9c.json`. Best fit: `E=1.429060012`, `K=0.130808252`, train log-RMSE `0.0285869`, max abs error `5.63%`. The code constants `E=1.4291`, `K=0.1308` are not transcription errors.
- Leave-one-rung-out CV: independent LORO fit gives CV log-RMSE `0.03995`; fold parameter CV about `0.6%` for both `E` and `K`.
- 9-point sensitivity including the 20k confirmation rung barely moves the fit: `E=1.423505`, `K=0.130494`, RMSE `0.02804`.
- Closed-form vs turn-by-turn: simulating `R_side = k*N_own*N_enemy^(ed-1)` with `ed=3-E=1.57094` matches the closed form to `<0.03%` with a small-step integrator.
- Count basis is total troops in the fitted kernel, and `predictor/kernel.py` also passes total side counts to `pvp_kernel`.
- Proc scheduler public behavior: Ambusher-only MC mean matched deterministic EV in the tested setup; same seed produced byte-identical batches; `_run_rng(seed,i)` is repeatable and independent of units; batch calls did not mutate input `Unit`s.
- Proc unlocks: `proc.py` and `predictor/kernel.py` apply `AMBUSHER_MIN_TIER=7` and `CRYSTAL_LANCE_MIN_TIER=11`. A T6 lancer batch was deterministic; a T7 lancer batch set `stochastic=True` and produced Ambusher variance in defender marksman damage.
- Whole-stack Ambusher: direct one-turn probe produced a two-point bypass distribution (`0` or whole-stack bypass damage), consistent with the documented whole-stack Bernoulli rule. The magnitude remains uncalibrated.
- `engine_meta` and `run_batch_units` route through the same `_kernel_box` gate.
- `_kernel_records` shape is valid in tested cases: start/incap keys match, defender is fully wiped, and attacker infantry casualties are capped to started infantry.
- Troop catalog serves valid T1-T12 x all classes x FC `{0,1,5,9,10}` with positive A/D/L/H values.
- Eight PvP report JSON files pass `BattleReport.validate()`. Aggregate `kills_by_class` and `beast_group_losses` sum checks passed across the JSON data I checked.
- Current `assemble.py` implements the stat algebra correctly for hero stat skills: stats-based hero stat effects multiply through `skillmult`; chance/turn stat effects enter the additive EV pool; enemy penalties divide.

## Residual Risk

- I did not exhaustively audit every workbook-derived hero skill row. The workbook-dependent path was available enough for `regression` and `pvp_calibrate` to run, and I inspected the routing code, but a full skill-book row audit would be a separate task.
- Proc variance magnitude is still not calibrated to repeat PvP data. Whole-stack Ambusher is mechanically defensible, but the width of forecast distributions should remain provisional.
- The general PvP engine remains weakly validated. Its current confidence number should not be treated as a calibrated prediction interval outside the r6/r8 anchor pair.
- The fast-path can be trustworthy only after `_kernel_box` enforces the actual validated box: both-side 50/50 inf/marks, correct marks tiers or an explicit composition tolerance, no lancers unless deliberately accepted, near-calibration stat ratios/panels, and attacker-wins-full-wipe.

Honest bottom line: this engine is not yet trustworthy for deciding real in-game troop commitments broadly; it is promising inside the controlled PvP ladder law, but the current predictor can silently apply that high-confidence law to matchups where it has not been earned.
