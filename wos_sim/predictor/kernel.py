"""Kernel seam — runs battles for a construct and returns per-run records.

This is the ONE seam between the predictor app (construct/summary/api, frozen)
and the battle engine. Per ENGINE_INTERFACE.md it must:
  * accept two ``list[Unit]`` (attacker A, defender D) and NEVER mutate them,
  * return per-run ``RunRecord`` (winner / turns / per-class start & incap),
  * batch n battles reproducibly with **CRN** streams keyed by (seed, i) ONLY.

The real stochastic engine is ``wos_sim.proc.simulate_stoch`` (deterministic
core from GAME_RULES 6i + the proc scheduler, E-5). It CLONES its inputs, so it
is non-mutating by construction. ``BatchKernel`` wraps it; ``StubKernel`` (the
old synthetic-variance placeholder) is kept for reference/tests.

Calibration note (honest): the general stat-based engine is magnitude-calibrated
only on the r6/r8 whale sister pair (rate/def_k/def_ed below) — a stopgap that
generalises weakly (GAME_RULES 6p), which is what ``engine_model_error`` (~0.13)
covers. The separately-validated farm/garrison kernel (``wos_sim.pvp_kernel``,
CV ~4%) is the high-confidence path for the 50/50 attacker-wins-full-wipe regime;
callers who know they are in that regime should prefer it.
"""
from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass

from wos_sim import pvp_kernel
from wos_sim.mechanics import AMBUSHER_MIN_TIER, CRYSTAL_LANCE_MIN_TIER
from wos_sim.models import StatType, TroopType
from wos_sim.pvp_engine import Unit, simulate_pvp
from wos_sim.proc import simulate_stoch

_A, _L = StatType.ATTACK, StatType.LETHALITY

# Best-available general PvP calibration (r6/r8). The app passes params=None by
# default; rate=1.0 (raw) would be meaningless, so the seam supplies these.
# Any key in a caller's `params` overrides. def_ed/def_k are the structural
# defender terms; enemy_ab defaults OFF (0.0) — the farm-ladder target-abundance
# does NOT transfer to whale scale (GAME_RULES 6p).
# rate=168 CALIBRATES DURATION (GAME_RULES 6r, 2026-07-05): fit to the real round
# counts of r6/r8 (Bradley S3 cadence ~4 rounds/proc -> r006 8 procs ~33 rounds,
# r008 10 procs ~42) - the engine now gives r006=33t, r008=42t. Casualties/winner
# are ~rate-invariant on these pre-T12 anchors, so this only corrects the clock
# (was 320 -> 17/22t, ~2x too fast, which OVER-weighted T12's fixed 5-turn windows
# and distorted outcomes).
DEFAULT_PVP_PARAMS = {"rate": 168.0, "def_k": 1000.0, "def_ed": 0.483}


@dataclass
class RunRecord:
    """One simulated battle, from the engine's A/D frame."""
    winner: str            # 'A' | 'D' | 'mutual'
    turns: int
    attacker_start: dict   # troop -> starting count
    defender_start: dict
    attacker_incap: dict   # troop -> incapacitated (raw total = severe + light;
    defender_incap: dict   #   the app applies the structure-type severe split)
    skill_telemetry: dict | None = None


def _starts(units) -> dict:
    """Per-class starting counts, aggregated by troop (robust to split stacks)."""
    out: dict = {}
    for u in units:
        out[u.troop] = out.get(u.troop, 0.0) + u.n
    return out


def _fill(incap: dict, start: dict) -> dict:
    """Guarantee every started class appears in incap (0 if untouched)."""
    return {t: float(incap.get(t, 0.0)) for t in start}


def _merged(params) -> dict:
    p = dict(DEFAULT_PVP_PARAMS)
    if params:
        p.update(params)
    return p


def _run_rng(seed: int, i: int) -> random.Random:
    """CRN stream for run i: depends on (seed, i) ONLY, never on the units, so
    paired candidate comparisons (optimizer) share proc draws per run."""
    return random.Random((seed * 1_000_003 + i) & 0x7FFF_FFFF_FFFF_FFFF)


def _has_procs(attacker_units, defender_units, params) -> bool:
    """Does this matchup have any stochastic proc source? Today the modelled
    procs are lancer SKILLS gated by their real unlock tier: Ambusher (T7+) and
    Crystal Lance (FC/T11+). A lancer BELOW those tiers has NO proc (a T6 lancer
    is NOT stochastic - confirmed Martin 2026-07-04; do not assume a proc from
    the class). No proc source -> DETERMINISTIC (GAME_RULES 6i) -> one sim ==
    all n runs. Extend when marksman/hero/gun procs are modelled."""
    cl = _merged(params).get("crystal_lance", 0.15)
    for u in list(attacker_units) + list(defender_units):
        if u.troop != TroopType.LANCER:
            continue
        if u.tier >= AMBUSHER_MIN_TIER:
            return True
        if cl > 0 and u.tier >= CRYSTAL_LANCE_MIN_TIER:
            return True
    return False


def _by_troop(units) -> dict:
    out: dict = {}
    for u in units:
        out[u.troop] = out.get(u.troop, 0.0) + u.n
    return out


def _inf_unit(units):
    for u in units:
        if u.troop == TroopType.INFANTRY and u.n > 0:
            return u
    return None


def _marks_unit(units):
    for u in units:
        if u.troop == TroopType.MARKSMAN and u.n > 0:
            return u
    return None


def _panel_mult(u):
    """Effective panel/buff multiplier of a unit (astat[Attack] vs base tier)."""
    return u.astat[_A] / u.base_atk if u.base_atk > 0 else float("inf")


def _kernel_box(attacker_units, defender_units, params):
    """If this matchup is inside pvp_kernel's VALIDATED box, return
    (n_att_total, n_def_total); else None.

    pvp_kernel's K encodes the EXACT ladder configuration - T10-attacker-vs-T7
    -defender tiers, 50/50 inf/marks BOTH sides, and the ladder's stat/panel
    levels - and IGNORES astat. Applying it to any other configuration is wrong,
    so the gate is deliberately tight AND stat-aware (QA 2026-07-04, Critical -
    the old tier-only gate stamped '+-4.5% validated' on matchups the attacker
    would actually LOSE):
      1. deterministic (no procs);
      2. BOTH sides infantry+marksman only, each ~50/50;
      3. attacker inf ~T10, defender inf ~T7, both marks ~T6;
      4. STAT SANITY - panels in a plausible range and the two sides' infantry
         panels within ~4x (rejects the stat-mismatched matchups the tier-only
         gate waved through);
      5. the stat-based engine does NOT hand the DEFENDER the win when fed the
         real astat (a genuine stat check that the attacker-wins premise holds).
    Everything else -> the general engine. Narrow ON PURPOSE; broadening +-4.5%
    to other configs needs controlled ladders there (deferred)."""
    if _has_procs(attacker_units, defender_units, params):
        return None
    a, d = _by_troop(attacker_units), _by_troop(defender_units)
    na = sum(v for v in a.values() if v > 0)
    nd = sum(v for v in d.values() if v > 0)
    if na <= 0 or nd <= 0:
        return None
    allowed = {TroopType.INFANTRY, TroopType.MARKSMAN}
    for side, tot in ((a, na), (d, nd)):
        if any(cnt > 0 and t not in allowed for t, cnt in side.items()):
            return None
        if not (0.40 <= side.get(TroopType.INFANTRY, 0.0) / tot <= 0.60):
            return None
    ai, di = _inf_unit(attacker_units), _inf_unit(defender_units)
    am, dm = _marks_unit(attacker_units), _marks_unit(defender_units)
    if None in (ai, di, am, dm):
        return None
    if not (9.5 <= ai.tier <= 10.5 and 6.5 <= di.tier <= 7.5
            and 5.5 <= am.tier <= 6.5 and 5.5 <= dm.tier <= 6.5):
        return None
    # STAT SANITY: reject pathological / grossly-mismatched panels the kernel
    # would otherwise silently misprice. Ratio-check BOTH classes (the ladder had
    # asymmetric MARKS, ~2.2x attacker-favoring, so allow up to ~4x either way but
    # reject the extreme marks mismatches the inf-only check used to wave through).
    mi_a, mi_d = _panel_mult(ai), _panel_mult(di)
    mm_a, mm_d = _panel_mult(am), _panel_mult(dm)
    if not all(0.8 <= m <= 300.0 for m in (mi_a, mi_d, mm_a, mm_d)):
        return None
    if not (0.25 <= mi_a / mi_d <= 4.0 and 0.25 <= mm_a / mm_d <= 4.0):
        return None
    # NOTE: an earlier simulate_pvp winner!='D' guard was REMOVED (2026-07-05) -
    # the general engine's direction is rate-dependent (it flipped when rate was
    # duration-recalibrated to 168) and thus fragile, and it is REDUNDANT: the
    # stat-range + panel-ratio checks above already reject the pathological
    # matchups (weak-att / godlike-def) that motivated it. The kernel's own
    # attacker-wins guard (wins below) stays.
    _, wins, _ = pvp_kernel.garrison_wipe_forecast(na, nd)
    return (na, nd) if wins else None


def _near_even_probe(attacker_units, defender_units, params, swing: float = 0.05,
                     band: float = 0.10) -> bool:
    """Coin-flip detector for the turn path. Two signals, OR-ed:

    1. STATIC strength symmetry: aggregate per-side strength index
       (sum of n x sqrt(offense x toughness) over stacks) within +-`band`.
       The near-even rally anchors are near-mirror inputs (within ~10%);
       both decisive solo anchors differ by >25%. Robust to the calibrated
       def_k regime (which deliberately un-balances the dynamic exchange).
    2. DYNAMIC perturbation: a +-`swing` defender-strength shift flips the
       simulated winner (three cheap deterministic hero-skill-free sims).
    """
    a_idx = _strength_index(attacker_units)
    d_idx = _strength_index(defender_units)
    if a_idx > 0 and d_idx > 0:
        import math
        if abs(math.log(a_idx / d_idx)) < math.log(1.0 + band):
            return True

    from wos_sim.pvp_turn_engine import simulate_turns

    winners = set()
    for mult in (1.0 - swing, 1.0, 1.0 + swing):
        d_units = []
        for u in defender_units:
            v = deepcopy(u)
            v.astat = {k: val * mult for k, val in v.astat.items()}
            d_units.append(v)
        res = simulate_turns([deepcopy(u) for u in attacker_units],
                             d_units, [], params=params, rng=random.Random(0))
        winners.add(res.winner)
    return len(winners) > 1


def _strength_index(units) -> float:
    """Aggregate side strength: n x sqrt(offense x toughness) per stack.
    Offense = Attack x Lethality, toughness = Defense x Health — the sqrt
    keeps the index linear in overall stat scale."""
    total = 0.0
    for u in units:
        off = u.astat[StatType.ATTACK] * u.astat[StatType.LETHALITY]
        tough = u.astat[StatType.DEFENSE] * u.astat[StatType.HEALTH]
        if off > 0 and tough > 0:
            total += u.n * (off * tough) ** 0.25
    return total


def engine_meta(attacker_units, defender_units, params=None) -> dict:
    """Per-matchup confidence + which path the forecast uses, for the app's
    honesty banner. Call ONCE (e.g. in api.predict); it does NOT change
    run_batch's list contract. run_batch_units routes on the SAME gate, so the
    returned records always match this path/error.

    Returns {path, calibrated, model_error, stochastic, note}:
      * path='pvp_kernel', calibrated=True,  model_error=0.045 -> validated regime,
      * path='general',    calibrated=False, model_error=0.5   -> everything else.
    IMPORTANT (QA 2026-07-04, High): render the app badge on `calibrated`, NOT on
    the number. The general path has NO calibrated band - off the r6/r8 anchor it
    mispredicts casualties by up to ~85% and the winner ~50% of the time (see
    pvp_calibrate). When calibrated is False, `model_error` is a COARSE FLOOR
    (0.5), not a prediction interval - show "uncalibrated / directional", not
    "+-50%". Only trust a numeric band when calibrated is True."""
    merged = _merged(params)
    if merged.get("engine") == "turn":
        # raw params only (see run_batch): the general-engine defaults in
        # `merged` must not leak into the turn engine's parameter layering.
        near_even = _near_even_probe(attacker_units, defender_units,
                                     dict(params or {}))
        if near_even:
            return {"path": "pvp_turn_engine", "calibrated": False,
                    "model_error": 0.5, "stochastic": True,
                    "near_even": True, "confidence": "coin_flip",
                    "note": "Near-even armies: real battles this close have "
                            "ended anywhere from 3% to 58% survivors on the "
                            "winning side (verified anchors). Trust the win "
                            "probability and the winner, never a point "
                            "survivor count."}
        return {"path": "pvp_turn_engine", "calibrated": False,
                "model_error": 0.35, "stochastic": True,
                "near_even": False, "confidence": "directional",
                "note": "Turn-by-turn skill engine, conditionally calibrated on "
                        "four real anchors (winner correct on all four). Read "
                        "survivor magnitudes as directional, not a tight "
                        "interval."}
    if _kernel_box(attacker_units, defender_units, params) is not None:
        return {"path": "pvp_kernel", "calibrated": True,
                "model_error": pvp_kernel.MODEL_ERROR, "stochastic": False,
                "note": "Validated garrison-wipe matchup class; typical model "
                        "error is about +-4.5% in this calibration box."}
    stoch = _has_procs(attacker_units, defender_units, params)
    return {"path": "general", "calibrated": False, "model_error": 0.5,
            "stochastic": stoch,
            "note": "Uncalibrated matchup class: use the forecast as directional "
                    "rather than as a precise prediction interval."
                    + ("" if stoch else " Deterministic (no procs).")}


def _replicate(rec, n) -> list:
    """n INDEPENDENT copies of a deterministic record (never aliased: each gets
    its own dicts, so a consumer mutating one run can't corrupt the others)."""
    return [RunRecord(rec.winner, rec.turns, dict(rec.attacker_start),
                      dict(rec.defender_start), dict(rec.attacker_incap),
                      dict(rec.defender_incap),
                      deepcopy(rec.skill_telemetry)) for _ in range(n)]


def _kernel_records(attacker_units, defender_units, na, nd, n) -> list:
    """n deterministic records from the validated closed-form kernel: attacker
    wins, defender fully wiped, all attacker losses on infantry."""
    cas, _, turns = pvp_kernel.garrison_wipe_forecast(na, nd)
    a_start, d_start = _starts(attacker_units), _starts(defender_units)
    a_incap = {t: 0.0 for t in a_start}
    a_incap[TroopType.INFANTRY] = min(cas, a_start.get(TroopType.INFANTRY, cas))
    d_incap = dict(d_start)                       # defender fully wiped
    return _replicate(RunRecord("A", turns, a_start, d_start, a_incap, d_incap), n)


class StubKernel:
    """Deterministic engine + synthetic proc variance (legacy placeholder).

    Superseded by BatchKernel (real procs). Retained so callers/tests can still
    request the old jitter behaviour explicitly via ``kernel=StubKernel()``.
    """

    def __init__(self, sigma: float = 0.13):
        self.sigma = sigma

    def _jitter(self, u, rng) -> Unit:
        astat = dict(u.astat)
        astat[_A] = astat[_A] * max(0.05, rng.gauss(1.0, self.sigma))
        astat[_L] = astat[_L] * max(0.05, rng.gauss(1.0, self.sigma))
        return Unit(troop=u.troop, tier=u.tier, n=u.n, astat=astat,
                    base_atk=u.base_atk, dd=u.dd, dt=u.dt)

    def run(self, attacker_units, defender_units, rng, params=None) -> RunRecord:
        a = [self._jitter(u, rng) for u in attacker_units]   # fresh copies
        d = [self._jitter(u, rng) for u in defender_units]
        res = simulate_pvp(a, d, _merged(params))
        a_start, d_start = _starts(attacker_units), _starts(defender_units)
        return RunRecord(res.winner, res.turns, a_start, d_start,
                         _fill(res.a_incap, a_start), _fill(res.d_incap, d_start),
                         getattr(res, "skill_telemetry", None))


class BatchKernel:
    """Real stochastic engine: the proc scheduler (E-5). Non-mutating —
    ``simulate_stoch`` clones its inputs, so the same construct Units are reused
    across all n battles safely."""

    def run(self, attacker_units, defender_units, rng, params=None) -> RunRecord:
        res = simulate_stoch(attacker_units, defender_units, _merged(params), rng)
        a_start, d_start = _starts(attacker_units), _starts(defender_units)
        return RunRecord(res.winner, res.turns, a_start, d_start,
                         _fill(res.a_incap, a_start), _fill(res.d_incap, d_start),
                         getattr(res, "skill_telemetry", None))


def run_batch_units(attacker_units, defender_units, *, n: int = 10_000,
                    seed: int = 0, params=None, antithetic: bool = False,
                    kernel=None) -> list:
    """Engine batched entry (ENGINE_INTERFACE §3). n stochastic battles ->
    ``list[RunRecord]``. Reproducible: (units, seed, n) -> identical batch.
    CRN: run i draws from ``_run_rng(seed, i)`` — a function of (seed, i) only.
    Deterministic (no-proc) matchups short-circuit to one sim replicated n times.

    ``antithetic`` is accepted for forward-compat but is a documented no-op for
    v1 (proper antithetic proc streams are the E-6 vectorization follow-up).

    Validated fast-path: when the matchup is inside pvp_kernel's box (see
    ``_kernel_box``) and no explicit kernel override is given, the forecast comes
    from the closed-form garrison-wipe kernel (deterministic, CV +-4.5%) instead
    of the general engine. ``engine_meta`` reports which path fired.
    """
    if kernel is None:
        box = _kernel_box(attacker_units, defender_units, params)
        if box is not None:
            return _kernel_records(attacker_units, defender_units, *box, n)
    k = kernel or BatchKernel()
    if isinstance(k, BatchKernel) and not _has_procs(attacker_units,
                                                     defender_units, params):
        rec = k.run(attacker_units, defender_units, _run_rng(seed, 0), params)
        return _replicate(rec, n)             # deterministic: identical but NOT aliased
    return [k.run(attacker_units, defender_units, _run_rng(seed, i), params)
            for i in range(n)]


def run_batch(construct, n: int = 10_000, seed: int = 0, kernel=None,
              params=None, antithetic: bool = False) -> list:
    """Seam signature the frozen ``api.predict`` calls. Delegates to
    ``run_batch_units`` on the construct's two unit lists. Default kernel is the
    real stochastic ``BatchKernel``."""
    if _merged(params).get("engine") == "turn" and kernel is None:
        from wos_sim.pvp_turn_engine import run_batch_construct
        # RAW caller params only: simulate_turns layers BEST_PARAMS+TURN_PARAMS
        # itself. Folding DEFAULT_PVP_PARAMS here would smuggle the GENERAL
        # engine's rate/def_k/def_ed (168/1000/0.483) over the turn engine's
        # calibrated set (168/1.0/1.0) and invert near-parity matchups.
        return run_batch_construct(construct, n=n, seed=seed,
                                   params=dict(params or {}))
    return run_batch_units(construct.attacker_units, construct.defender_units,
                           n=n, seed=seed, params=params, antithetic=antithetic,
                           kernel=kernel)
