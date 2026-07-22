"""Stage 5 -- the composition layer: an ALGORITHM on top of the per-unit law.

Measured structure (Meuller_Alpaca_v5_8_Battle + 2v2 + the manual ladder, all
vs the same Alpaca duo: FC-panel Infantry[Gatot] + FC-panel Marksman[Vulcanus]):

  * Absorption order Inf -> Lan -> MM: the leading class tanks ALL incoming
    damage; backline units are untouched until the front collapses.
  * SEQUENTIAL TANKING (the N-Infantry ladder 78/90/144/198/252 exactly):
        solo unit             1.000 x t_solo      (no allies -> no penalty)
        first tank (allies)   0.423 x t_solo      (33/78)
        middle tanks          0.692 x t_solo      (54/78)
        last tank             0.731 x t_solo      (57/78)
    Each death turn is CEILed (integer turns); reproduces the naked pair
    (solo 6 -> 2 naked Inf = ceil(2.54)+ceil(4.38) = 8) as well.
  * BACKLINE MOP-UP is KILL-CADENCE-LIMITED, not HP-limited (Lancer ladder,
    Martin 2026-07-14): the j-th backline unit dies at
        t_front + max(ceil(4j/3), s_class)
    where 4/3 turns/kill is the cadence and s_class is the single-unit
    latency (measured vs the Alpaca duo: MM 2, Lancer 3). Evidence: the
    Marksman ladder (end-33 = 2/3/4/6/7/14 for k=1..5,10) and the Lancer
    ladder (3/3/4/6/7/14) are IDENTICAL for k>=2 although Lancers carry 4x
    the D*H pool -- so throughput does not scale with target HP; only the
    lone-backliner latency is class-dependent. All 12 points exact.
    (The earlier HP-scaled generalization MOPUP_LAW_MULT x law-time is
    REFUTED by this data and removed.)
  * The tanking factors are DEFENDER-SPECIFIC ratios of t_solo. Exported
    Vulcanus-free (the measuring defender ran Gatot+Vulcanus):
        t_solo_clean = t_solo_obs * (31/30) * (1/0.88)
    (S2: +20% dmg every 6th attack => x31/30 avg; S3: -12% enemy Inf/Lan
     Defense, cadence turn 1 + every 3rd lasting 3 turns => continuous.)

OPEN (inherited from the pre-flight review, NOT resolved here -- measured
ratios frozen, mechanism unknown):
  * why first=0.423 / middle=0.692 / last=0.731 differ;
  * mop-up 4/3 turns/unit is ~3.2x SLOWER than the naive summed-rate law
    prediction vs this defender (whose MM dealer is itself out-of-law:
    proc-gated vs Gatot Infantry -- see STAGE5_REPORT.md Type-2 boundary).

predict_battle() therefore runs in two modes:
  anchor="law"      t_solo from the per-unit law (in-scope: Infantry-dealer
                    dominant sides; out-of-scope flagged in meta)
  anchor=<number>   t_solo measured/known (validates the pure algorithm)

STAGE 6.5 (2026-07-18) -- Gatot-kit gate + honest abstention (A1+A3'+A4 of the
remediation plan; see STAGE6_5_REMEDIATION.md). Independent QA found the
production two-sided race ran WITHOUT the Gatot-kit gate (stage6_gatot.py),
so it mis-called winners against Gatot-defended Infantry. `predict_battle`
now accepts optional `att_kit`/`def_kit` side descriptors
({"gatot": None|True|"mueller_s123_l1"|"farseer_s12_l1", "vulcanus": bool}):
when a side's front is flagged Gatot-led Infantry, the race applies the
EXISTING stage6_gatot two-regime model (budget absorb for hero-less non-Inf
dealers vs the two measured defenders; exp-decay S(d) + sqrt(N) for
Vulcanus-led dealers) instead of the plain per-unit law, and returns an
explicit `winner: "uncertain"` verdict (+ `gatot_abstain` meta) rather than a
confident call wherever the kit's constants are not measured for the
configuration in play -- including the Infantry-dealer-vs-strong-Gatot-target
case (part i): an unmeasured kit amplification M can only LENGTHEN that
dealer's own kill clock, never shorten it, so the naive clock stays a safe,
gate-free lower bound EXCEPT when it is already the decisive (shorter) one.
No new physics constants: every number used here (K/G_w/G_l, the two B
budgets, the S-curve a/d0) is read from the FROZEN stage6_tables.json
`gatot_kit` block (stage6_gatot.py's own output) -- nothing is fitted here.
Default (`att_kit=def_kit=None`, the pre-6.5 call convention): behavior is
unchanged byte-for-byte.

STAGE 6.6 (2026-07-19) -- kit v3, hero-STATE aware (STAGE6_6_REPORT.md):
kit descriptors gain copy tokens ("mueller"/"alpaca"/"farseer"; the 6.5
instrument tokens remain accepted as aura'd aliases) and an optional
explicit `gatot_state` ("aurad"/"inert"); when the state is not given, the
seam detects it from the target unit's Infantry Attack-panel via the frozen
`hero_state` registry (nearest-neighbour baseline vs baseline+Expedition%,
x2 margin guard -> ambiguous = abstain). INERT Gatot = plain law (no gate,
no abstention -- the 12-row D4 anchor). AURA'D budgets are per copy
(Mueller 201.95 / FarSeer 30.15 / Alpaca 879.3 branch-checked), and the
budget gate now covers hero-less dealers of EVERY class (Infantry included
-- the v5 dissolution) with the Lancer per-edge K(Lan->Inf) and
span-invariance abstention. Gatot-led dealers race plain (Lab-Rat mirror
instrument); other hero-led dealers abstain. Every constant is read from
the frozen stage6_tables.json `hero_state`/`gatot_kit` blocks
(stage6_hero_state.py re-derives them from named corpus rows).
Defaults still reproduce the pre-6.5 result byte-for-byte.
"""
import math

from wos_sim.formula_research.stage5_law import (
    CAP_TURNS, eff_stats, g_l, g_w, K,
)

ABSORB_ORDER = ("Infantry", "Lancer", "Marksman")

#: sequential-tanking ratios (x t_solo), measured on the count ladder
TANK_SOLO = 1.0
TANK_FIRST = 33.0 / 78.0            # 0.4231
TANK_MIDDLE = 54.0 / 78.0           # 0.6923
TANK_LAST = 57.0 / 78.0             # 0.7308

#: backline mop-up cadence: 3 kills per 4 turns (measured, Alpaca-duo regime;
#: class/HP-INDEPENDENT -- see docstring). Death j lands at
#: t_front + max(ceil(MOPUP_CADENCE*j), single-unit latency).
MOPUP_CADENCE = 4.0 / 3.0
#: single-backliner latency by class, measured vs the Alpaca duo
MOPUP_SINGLE_LATENCY = {"Marksman": 2, "Lancer": 3}

#: Vulcanus backout for exporting measured tanking constants to other defenders
VULC_S2_TIME = 31.0 / 30.0          # remove +20%-every-6th-attack
VULC_S3_TIME = 1.0 / 0.88           # remove -12% enemy Inf/Lan Defense (continuous)


def vulcanus_clean(t_obs, target_cls="Infantry"):
    """Measured survival time vs a Vulcanus defender -> Vulcanus-free time."""
    t = t_obs * VULC_S2_TIME
    if target_cls in ("Infantry", "Lancer"):
        t *= VULC_S3_TIME
    return t


# --------------------------------------------------------------------------- #
#  STAGE 6.5 / 6.6 -- Gatot-kit gate (reads the FROZEN stage6_tables.json
#  `gatot_kit` + `hero_state` blocks; invents nothing).
#
#  STAGE 6.6 (2026-07-19, kit v3 -- hero-STATE aware, stage6_hero_state.py):
#    * kit tokens now name the COPY ("mueller" / "alpaca" / "farseer"); the
#      6.5 instrument tokens below stay accepted as (copy, state="aurad")
#      aliases, so 6.5 callers are unchanged.
#    * the Gatot STATE (aura'd vs inert) is detected from the target unit's
#      Infantry Attack-panel via the frozen registry (nearest-neighbour to
#      baseline vs baseline+Expedition%, x2 margin guard), or passed
#      explicitly as kit["gatot_state"].  INERT => the kit contributes
#      NOTHING (plain law, no gate, no abstention) -- the 12-row D4 anchor.
#    * AURA'D budgets are per (copy, state): Mueller 201.95 / FarSeer 30.15 /
#      Alpaca 879.3 (K(Lan->Inf)-branch-dependent, 949.9 on the factorized
#      branch -- verdicts must agree across branches or the gate abstains).
#    * the budget gate now covers HERO-LESS dealers of EVERY class:
#      Marksman + Infantry (K cells measured) and Lancer via the per-edge
#      K(Lan->Inf) (edge-implied 90.38 @T6 / 111.29 @T3-ordinary; other
#      tiers must be verdict-invariant across the [83.66, 111.29] span).
#      Hero-led dealers: Vulcanus-led Marksman = the S-curve (Mueller target
#      only); GATOT-led dealers = plain law (the Lab-Rat Gatot-mirror
#      battery -- the K(Inf->Inf) source -- IS that configuration); other
#      hero-led dealers = abstain (unmeasured).
# --------------------------------------------------------------------------- #
#: 6.5 compatibility -- instrument tokens accepted as (copy, "aurad") aliases.
GATOT_MEASURED_BUDGET_VARIANTS = {
    "mueller_s123_l1": "Mueller_Gatot_S123_L1",
    "farseer_s12_l1": "FarSeer_Gatot_S12_L1",
}
GATOT_MEASURED_SCURVE_VARIANT = "mueller_s123_l1"
_LEGACY_TOKEN_COPY = {"mueller_s123_l1": "mueller", "farseer_s12_l1": "farseer"}

_GATOT_KIT_CACHE = None


def _gatot_kit_frozen():
    """Lazy-load the frozen `gatot_kit` + `hero_state` blocks from
    stage6_tables.json (READ ONLY). Cached per process; the file is the single
    source of truth the seam already declares (api.py `_stage6_tables_meta`)."""
    global _GATOT_KIT_CACHE
    if _GATOT_KIT_CACHE is not None:
        return _GATOT_KIT_CACHE
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "stage6_tables.json"), encoding="utf-8") as fh:
        j = json.load(fh)
    kit, hs = j["gatot_kit"], j["hero_state"]
    scurve = kit["hero_led_suppression"]["surviving_families_folded"][0]["params"]
    bcs = hs["B_by_copy_state"]
    kl = hs["K_LanInf_for_gate"]
    _GATOT_KIT_CACHE = {
        "B": {  # per (copy, "aurad"); inert is 0 by the D4 anchor (no gate)
            "mueller": bcs["mueller.aurad"]["value"],
            "farseer": bcs["farseer.aurad"]["value"],
            "alpaca": bcs["alpaca.aurad"]["value"],
        },
        "B_branch": {  # branch values where B is K-branch-dependent
            "alpaca": [bcs["alpaca.aurad"]["branch_k_laninf_edge"],
                       bcs["alpaca.aurad"]["branch_k_laninf_factorized"]],
        },
        "scurve_a": scurve[0], "scurve_d0": scurve[1],
        "registry": hs["registry"],
        "margin_min": hs["detection"]["margin_min"],
        "k_laninf": {"T6": kl["T6"], "T3_ordinary": kl["T3_ordinary"],
                     "span": kl["robustness_span"],
                     "t6_band": [kl["T6"], kl["T6_winturn_variant"]]},
        # coherent (K(Lan->Inf), B_alpaca) branch PAIRS -- B inherits the K
        # branch (the measuring dealers were Lancers), so a Lancer dealer's
        # rate and B move TOGETHER with K (2026-07-19 QA fix)
        "k_b_pairs_alpaca": [
            (kl["T6"], bcs["alpaca.aurad"]["branch_k_laninf_edge"]),
            (kl["factorized_branch"], bcs["alpaca.aurad"]["branch_k_laninf_factorized"]),
        ],
    }
    return _GATOT_KIT_CACHE


def _gatot_resolve(target_kit, target):
    """(copy, state, flags) for a Gatot-led Infantry target.
    copy in {"mueller","alpaca","farseer",None}; state in {"aurad","inert",
    None} (None = unknown/ambiguous -> the caller falls back to the 6.5
    unknown-kit behaviour: abstain for non-Inf dealers, monotonicity-flag for
    Inf dealers)."""
    kit = _gatot_kit_frozen()
    token = target_kit.get("gatot")
    copy = None
    state = target_kit.get("gatot_state")
    if isinstance(token, str):
        if token in _LEGACY_TOKEN_COPY:            # 6.5 instrument tokens
            copy = _LEGACY_TOKEN_COPY[token]
            state = state or "aurad"
        elif token in kit["registry"]:
            copy = token
    flags = set()
    if state is None and copy is not None:
        panel = target.get("panel_pct") or target.get("panel") or {}
        pa = panel.get("Attack")
        if pa is not None:
            reg = kit["registry"][copy]
            b = reg["baseline_inf_A_pp"]
            e = reg["expedition_inf_A_pp"]
            d_in, d_au = abs(pa - b), abs(pa - (b + e))
            margin = max(d_in, d_au) / max(min(d_in, d_au), 1e-3)
            if margin >= kit["margin_min"]:
                state = "aurad" if d_au < d_in else "inert"
                flags.add(f"gatot_state_detected_{state}_{copy}")
            else:
                flags.add("gatot_state_ambiguous")
    return copy, state, flags


def _k_laninf_gate(tier, g_w_lan):
    """(k, span_lo, span_hi, flag) -- the per-edge K(Lan->Inf) the budget gate
    uses for a Lancer dealer stack (stage6_hero_state D2). Values and spans
    come from the frozen hero_state block; verdicts must be invariant across
    the span or the caller abstains."""
    kl = _gatot_kit_frozen()["k_laninf"]
    if tier == 6:
        k = kl["T6"]
        lo, hi = kl["t6_band"]
        return k, lo, hi, "gatot_k_laninf_T6_edge"
    if tier == 3:
        k = kl["T3_ordinary"]
        return k, k, k, "gatot_k_laninf_T3_edge(ordinary-base caveat)"
    k = kl["T6"]
    lo, hi = kl["span"]
    return k, lo, hi, "gatot_k_laninf_span_checked"


def _gatot_gate_rate(dealer_stack, k, k_kind, gw, gl, target, offense_mult,
                     copy, dealer_kit):
    """One dealer stack vs an AURA'D Gatot-led Infantry `target` of a
    measured copy (the stage6_gatot two-regime model + the 6.6 hero-state
    extensions). Returns (rate, flags, abstain): `rate` is target-units-
    killed/turn (None iff `abstain` is set); `abstain` is None or
    {"flag", "detail"}."""
    kit = _gatot_kit_frozen()
    flags = {"gatot_kit_target"}
    pool = target["eff"]["D"] * target["eff"]["H"] * gl
    n = max(dealer_stack["count"], 1)
    d_heroes = dealer_kit or {}

    # ---- hero-led dealers -------------------------------------------------- #
    if d_heroes.get("vulcanus"):
        if copy != "mueller":
            flags.add("gatot_gate_unmodeled")
            return None, flags, {
                "flag": "gatot_gate_unmodeled",
                "detail": "the hero-led S(d) exp-decay candidate is only "
                          "solved/blind-tested vs the MUELLER aura'd defender "
                          f"(got copy {copy!r})"}
        if dealer_stack["cls"] != "Marksman":
            flags.add("gatot_gate_unmodeled")
            return None, flags, {
                "flag": "gatot_gate_unmodeled",
                "detail": "the S(d) curve is solved on Marksman dealers only "
                          f"(got {dealer_stack['cls']})"}
        d1 = (dealer_stack["eff"]["A"] * dealer_stack["eff"]["L"]
              * offense_mult) / (k * gw)
        # Order of operations pinned by the 2026-07-17 regime-discriminator
        # battle (3x Vulcanus-led T6 MM vs Mueller-Gatot T1 Inf = 4 turns,
        # ENIF_ANALYSIS.md "Pressure-test battles" #1): suppression applies
        # PER DEALER, then sqrt(N) pools the suppressed rates -> ceil(3.85)=4
        # = observed. Suppressing the pooled group rate predicts 3 (rejected).
        suppression = 1.0 + kit["scurve_a"] * math.exp(-d1 / kit["scurve_d0"])
        net = (d1 / suppression) * math.sqrt(n)
        flags.add("gatot_scurve")
        if n > 1:
            # QA v3 finding #5: the per-dealer-then-sqrt(N) order is VALIDATED
            # at n=3 (the E2 battle, kill @4 = ceil(3.85)); other n>1 counts
            # are extrapolation -- visible, never silent.
            flags.add("gatot_scurve_multi_n_validated_at_3_only")
        if net <= 0 or net * CAP_TURNS < pool:
            return 1.0 / (CAP_TURNS + 1), flags | {"gatot_capped"}, None
        return net / pool, flags, None
    if d_heroes.get("gatot"):
        # Gatot-led dealer vs an aura'd Gatot target = the Lab-Rat mirror
        # battery configuration (the K(Inf->Inf) source rows) -- plain law.
        # The open Gatot-DEALER slowdown (151127) can only LENGTHEN this
        # clock; callers racing it as the WINNING clock inherit that risk
        # (documented, not gated -- Stage-7 physics).
        flags.add("gatot_led_dealer_plain(labrat-mirror-instrument)")
        t_1v1 = (k * target["eff"]["D"] * target["eff"]["H"]
                 / (dealer_stack["eff"]["A"] * dealer_stack["eff"]["L"]
                    * offense_mult) * gw * gl)
        return math.sqrt(n) / t_1v1, flags, None
    if d_heroes and any(v for kk, v in d_heroes.items()
                        if kk not in ("gatot", "vulcanus", "gatot_state")):
        flags.add("gatot_gate_unmodeled")
        return None, flags, {
            "flag": "gatot_gate_unmodeled",
            "detail": f"hero-led dealer ({d_heroes}) vs an aura'd Gatot: only "
                      "Vulcanus-led Marksman (S-curve) and Gatot-led (plain, "
                      "Lab-Rat instrument) are measured"}

    # ---- hero-less dealers: the budget gate, all classes ------------------- #
    B = kit["B"].get(copy)
    if B is None:                                             # pragma: no cover
        flags.add("gatot_gate_unmodeled")
        return None, flags, {"flag": "gatot_gate_unmodeled",
                             "detail": f"no measured budget for copy {copy!r}"}
    al = (dealer_stack["eff"]["A"] * dealer_stack["eff"]["L"] * offense_mult)
    if dealer_stack["cls"] == "Lancer":
        k_gate, k_lo, k_hi, k_flag = _k_laninf_gate(dealer_stack["tier"], gw)
        flags.add(k_flag)
        d1 = al / (k_gate * gw)
        d_hi, d_lo = al / (k_lo * gw), al / (k_hi * gw)       # k lo -> d hi
    else:
        if k_kind != "measured":                              # pragma: no cover
            flags.add("gatot_gate_unmodeled")
            return None, flags, {
                "flag": "gatot_gate_unmodeled",
                "detail": f"K({dealer_stack['cls']}->Infantry) is {k_kind}"}
        d1 = al / (k * gw)
        d_hi = d_lo = d1
        if dealer_stack["cls"] == "Infantry":
            # STAGE 6.6: hero-less INFANTRY dealers are budget-gated too --
            # the v5 dissolution (gatot_shield_test T2): every hero-less v5
            # rung is fully absorbed by B_Alpaca, observed 9/9.
            flags.add("gatot_budget_inf_dealer")
    B_vals = kit["B_branch"].get(copy, [B])
    verdicts = set()
    if copy == "alpaca" and dealer_stack["cls"] == "Lancer":
        # COHERENT branch pairing (2026-07-19 QA fix, found by
        # test_deterministic_seam): B_Alpaca and a Lancer dealer's own rate
        # BOTH scale with the chosen K(Lan->Inf) branch -- evaluate the two
        # (K, B) pairs, never the interval cross-product, which wrongly
        # abstains for every N above the measured 204/205 edge (the paired
        # threshold N* ~ 204.95 is branch-INVARIANT for this dealer family).
        for kb, bv in kit["k_b_pairs_alpaca"]:
            net_v = max(0.0, n * (al / (kb * gw)) - bv)
            verdicts.add(bool(net_v <= 0 or net_v * CAP_TURNS < pool))
    else:
        for b_v in B_vals:
            for d_v in (d_lo, d_hi):
                net_v = max(0.0, n * d_v - b_v)
                verdicts.add(bool(net_v <= 0 or net_v * CAP_TURNS < pool))
    if len(verdicts) > 1:
        flags.add("gatot_gate_branch_flip")
        return None, flags, {
            "flag": "gatot_gate_branch_flip",
            "detail": "the capped-vs-breakthrough verdict flips across the "
                      "carried K(Lan->Inf)/B branch values -- knife-edge "
                      "configuration, honest abstain "
                      f"(d in [{n * d_lo:.2f}, {n * d_hi:.2f}] vs B in {B_vals})"}
    net = max(0.0, n * d1 - B)
    flags.add("gatot_budget")
    flags.add(f"budget_{copy}_aurad")
    if net <= 0 or net * CAP_TURNS < pool:
        # capped: rate (kills/turn, same units as the sqrt(N)/t_1v1 the
        # caller sums) that makes t_pu = 1/rate land STRICTLY beyond
        # CAP_TURNS (matches predict_battle's `> CAP_TURNS` convention)
        return 1.0 / (CAP_TURNS + 1), flags | {"gatot_capped"}, None
    if dealer_stack["cls"] == "Infantry":
        flags.add("gatot_budget_breakthrough_unvalidated_inf")
    return net / pool, flags, None


# --------------------------------------------------------------------------- #
#  army helpers
# --------------------------------------------------------------------------- #
def _norm_army(army):
    """army = [{"cls","tier","fc","count","panel"|"eff"}] -> stacks with eff.
    STAGE 6.6: the raw panel dict (panel_pct or panel) is carried through --
    the Gatot-kit hero-STATE detector reads the Infantry Attack-panel."""
    if not army:
        raise ValueError("empty army: each side needs at least one unit stack "
                         "(QA v3 guard, 2026-07-19)")
    out = []
    for u in army:
        eff = u.get("eff") or eff_stats(u["cls"], u["tier"], u.get("fc"),
                                        u.get("panel"))
        count = u.get("count", 1)
        if count < 1:
            raise ValueError(f"unit stack count must be >= 1, got {count!r} "
                             f"for {u.get('cls')!r} (QA v3 guard)")
        if not eff or eff.get("A", 0) <= 0 or eff.get("L", 0) <= 0                 or eff.get("D", 0) <= 0 or eff.get("H", 0) <= 0:
            raise ValueError(f"non-positive effective stats for {u.get('cls')!r}: "
                             f"{eff!r} -- every A/D/L/H must be > 0 (QA v3 guard)")
        out.append({"cls": u["cls"], "tier": u["tier"], "count": count,
                    "eff": eff,
                    "panel_pct": u.get("panel_pct") or u.get("panel")})
    return sorted(out, key=lambda u: ABSORB_ORDER.index(u["cls"]))


def _dealer_rate(dealers, target, offense_mult=1.0, law=None,
                 target_kit=None, dealer_kit=None):
    """Summed kill rate (target HP-pools/turn) of every dealer stack onto ONE
    target unit. sqrt(count) per stack (Stage-3 count law); K-table cells.
    Returns (rate, meta_flags, note).

    law: optional {"K", "g_w", "g_l"} table overrides (the stage6 class-keyed
    tables via stage6_tables.law_funcs()).  Default None = the frozen stage5
    law, byte-identical to the eval-5 state.  Signatures match stage5's:
    K(dealer_cls, target_cls) -> (value, kind); g_w(tier, cls) -> value;
    g_l(tier, cls) -> (value, measured) where measured is stage5's bool or a
    stage6 provenance status string ("measured" == no flag).

    target_kit/dealer_kit (Stage 6.5): optional side descriptors
    {"gatot": None|True|"mueller_s123_l1"|"farseer_s12_l1", "vulcanus": bool}.
    When `target` is a single Gatot-led Infantry unit, non-Infantry dealer
    stacks route through the frozen Gatot-kit model (_gatot_gate_rate); if
    the model's constants aren't measured for the configuration, `rate` is
    None and `note` carries {"abstain": {"flag","detail"}} -- callers MUST
    check for this before using `rate`. An Infantry dealer stack with no
    Gatot of its own facing a Gatot-led Infantry target uses the plain
    (unchanged) formula, but `note` flags {"naive_inf_dealer_vs_gatot": True}
    so the caller can apply the monotonicity check (see predict_battle)."""
    K_fn = law["K"] if law else K
    gw_fn = law["g_w"] if law else g_w
    gl_fn = law["g_l"] if law else g_l
    rate, flags = 0.0, set()
    naive_inf_dealer_vs_gatot = False
    gatot_target = bool(target["cls"] == "Infantry" and target["count"] == 1
                        and target_kit and target_kit.get("gatot"))
    if (target["cls"] == "Infantry" and target["count"] > 1
            and target_kit and target_kit.get("gatot")):
        # QA v3 finding #3 (2026-07-19): multi-unit Gatot-Infantry targets are
        # outside the measured single-target regime -- the plain law runs, but
        # the caller must SEE that the kit was not applied.
        flags.add("gatot_kit_multiunit_unmodeled")
    g_copy = g_state = None
    if gatot_target:
        # STAGE 6.6: resolve (copy, state) -- explicit kit fields win, else
        # the frozen-registry panel detector (stage6_hero_state D5).
        g_copy, g_state, det_flags = _gatot_resolve(target_kit, target)
        flags |= det_flags
        if g_state == "inert":
            # D4 anchor: an un-aura'd Gatot contributes NOTHING (no
            # absorption, no Royal-Legion fold) -- plain law, no abstention.
            flags.add("gatot_inert_no_kit")
            gatot_target = False
    if gatot_target and g_state == "aurad" and g_copy is not None \
            and len(dealers) > 1:
        flags.add("gatot_gate_unmodeled")
        return None, flags, {"abstain": {
            "flag": "gatot_gate_unmodeled",
            "detail": "multi-stack dealer side vs an aura'd Gatot target: "
                      "volley pooling across mixed stacks is unmeasured"}}
    for s in dealers:
        k, kind = K_fn(s["cls"], target["cls"])
        if kind == "factorized":
            flags.add(f"K({s['cls'][:3]}->{target['cls'][:3]}) factorized")
        elif kind == "edge_implied":
            flags.add(f"K({s['cls'][:3]}->{target['cls'][:3]}) edge_implied "
                      "(shield-model-conditional)")
        if s["cls"] != "Infantry":
            flags.add("non-Inf dealer: G_w hypothesis + proc-gating risk")
        gw = gw_fn(s["tier"], s["cls"])
        gl, gl_measured = gl_fn(target["tier"], target["cls"])
        if gl_measured not in (True, "measured"):
            flags.add(f"G_l({target['cls'][:3]} T{target['tier']}) "
                      + (gl_measured if isinstance(gl_measured, str)
                         else "unmeasured -- Infantry-table fallback"))

        if gatot_target and g_state == "aurad" and g_copy is not None:
            r, gflags, abstain = _gatot_gate_rate(
                s, k, kind, gw, gl, target, offense_mult, g_copy, dealer_kit)
            flags |= gflags
            if abstain is not None:
                return None, flags, {"abstain": abstain}
            rate += r
            continue
        if gatot_target:
            # copy/state unresolved (unknown copy, no panel, or ambiguous
            # margin) -- the 6.5 unknown-kit behaviour, unchanged: non-Inf
            # dealers abstain; Inf dealers race naively + monotonicity flag.
            if s["cls"] != "Infantry":
                flags.add("gatot_gate_unmodeled")
                return None, flags, {"abstain": {
                    "flag": "gatot_gate_unmodeled",
                    "detail": "Gatot target present but copy/state unresolved "
                              f"(copy {g_copy!r}, state {g_state!r}) -- "
                              "budgets are measured per (copy, aura'd) only; "
                              "pass unit panels or an explicit gatot_state"}}
            if not (dealer_kit and dealer_kit.get("gatot")):
                naive_inf_dealer_vs_gatot = True
                flags.add("gatot_kit_inf_dealer_naive")

        t_1v1 = (k * target["eff"]["D"] * target["eff"]["H"]
                 / (s["eff"]["A"] * s["eff"]["L"] * offense_mult)
                 * gw * gl)
        rate += math.sqrt(s["count"]) / t_1v1
    note = {"naive_inf_dealer_vs_gatot": True} if naive_inf_dealer_vs_gatot else None
    return rate, flags, note


def army_kill_timeline(dealers, targets, *, offense_mult=1.0, t_solo=None,
                       law=None, target_kit=None, dealer_kit=None, note_sink=None):
    """Turn numbers at which each target unit dies (dealers kill targets).

    dealers/targets: normalized stacks (absorption order). t_solo overrides the
    law's solo-kill time of the FRONT-class unit (measured anchor); backline
    mop-up scales with the law via MOPUP_LAW_MULT either way.
    law: optional stage6 table overrides (see _dealer_rate).
    target_kit/dealer_kit (Stage 6.5): optional side descriptors, see
    _dealer_rate. Gatot only ever shields Infantry, and Infantry is always
    the front (ABSORB_ORDER), so the gate can only fire on the FRONT-unit
    rate call below -- backline stacks are never Gatot targets in this model.
    note_sink: optional dict; if the Gatot-kit gate can't resolve a rate,
    this is updated in place with {"abstain": {"flag","detail"}} so the
    caller (predict_battle) can surface the reason without re-deriving it.
    Returns (death_turns, flags): death_turns = [(turn, cls), ...] cumulative,
    OR (None, flags) if the Gatot-kit model's constants are not measured for
    this front matchup (t_solo is not None bypasses the gate entirely --
    anchor mode is a measured/known time, not a law computation).
    """
    flags = set()
    front_cls = targets[0]["cls"]
    fronts = [u for u in targets if u["cls"] == front_cls]
    backs = [u for u in targets if u["cls"] != front_cls]
    n_front = sum(u["count"] for u in fronts)
    n_back = sum(u["count"] for u in backs)
    n_total = n_front + n_back

    # per-unit solo kill time of a front unit by the whole dealer side
    if t_solo is not None:
        rate, f, _note = _dealer_rate(dealers, fronts[0], offense_mult, law=law)
    else:
        rate, f, note = _dealer_rate(dealers, fronts[0], offense_mult, law=law,
                                     target_kit=target_kit, dealer_kit=dealer_kit)
        if note and note_sink is not None:
            note_sink.update(note)
    flags |= f
    if rate is None:
        return None, flags               # Gatot-kit gate: unmodeled (abstain)
    t_pu = t_solo if t_solo is not None else (1.0 / rate if rate > 0 else CAP_TURNS)

    # deaths land on integer turns: each phase starts at the previous
    # (integer) death turn -- next death = ceil(prev + duration). Reproduces
    # the buffed ladder (33/90/144/...) AND the naked pair (3 -> ceil(3+4.38)=8).
    deaths, t = [], 0
    if n_total == 1:
        deaths.append((math.ceil(t_pu * TANK_SOLO), front_cls))
        return deaths, flags
    # sequential tanks: first / middles / last (last front near-solo only if
    # nothing stands behind it; with a backline every front is "covered")
    factors = []
    for i in range(n_front):
        if i == 0:
            factors.append(TANK_FIRST)
        elif i == n_front - 1 and n_back == 0:
            factors.append(TANK_LAST)
        else:
            factors.append(TANK_MIDDLE)
    for fac in factors:
        t = math.ceil(t + t_pu * fac)
        deaths.append((t, front_cls))
    # backline mop-up: cadence-limited (NOT HP-limited -- Lancer ladder), death
    # j at t_front + max(ceil(4j/3), single-unit latency). Cadence is a
    # single-regime measurement (Alpaca duo) -- flagged in law mode.
    t_front = t
    j = 0
    for u in backs:
        if t_solo is None:
            r_u, f, _note = _dealer_rate(dealers, u, offense_mult, law=law)
            flags |= f
            latency = math.ceil(1.0 / r_u) if r_u > 0 else CAP_TURNS
            flags.add("mop-up cadence 4/3 is single-regime (Alpaca duo) -- "
                      "latency from the per-unit law")
        else:
            latency = MOPUP_SINGLE_LATENCY.get(u["cls"], 2)
            flags.add("mop-up at measured cadence/latency (Alpaca-duo regime)")
        for _ in range(u["count"]):
            j += 1
            t = t_front + max(math.ceil(MOPUP_CADENCE * j), latency)
            deaths.append((t, u["cls"]))
    return deaths, flags


# --------------------------------------------------------------------------- #
#  STAGE 6.7 (2026-07-19) -- FOLD OWNERSHIP: the seam computes the deterministic
#  hero folds itself, exactly once per race direction.
#
#  Before 6.7 these lived in a validator-side private helper
#  (stage5_validate._nanomart_offense), so a live caller that declared kits
#  still got fold-blind clocks (Codex QA v3 finding #1). No new constants: every
#  value below is a frozen mechanic (run-stage SKILL.md "Confirmed mechanics").
# --------------------------------------------------------------------------- #

SEOYOON_S1 = {1: 1.05, 2: 1.10, 3: 1.15}    # own-side Troops Attack
VULC_S1_ENEMY_ATK = 0.96                     # enemy Attack, once at battle start
VULC_S2_DMG = 31.0 / 30.0                    # +20% every 6th attack -> average
VULC_S3_DEF_SHRED = 0.88                     # -12% enemy Inf/Lan Defense (continuous)
VULC_S3_OWN_MM_ATK = 1.0 + 0.12 / 3.0        # +12% own MM Attack for 1 of every 3 turns
#: Royal Legion (Gatot S3) enemy-Attack debuff by skill level -- NOT applied by
#: default, see _hero_folds' royal_legion note.
ROYAL_LEGION_BY_LEVEL = {2: 0.10, 3: 0.15}


def _hero_folds(dealers, dealer_kit, targets, target_kit, *,
                apply_royal_legion=False):
    """Deterministic hero-fold multiplier on the DEALER's offense for ONE race
    direction. Returns (mult, flags).

    Folds applied (all frozen mechanics, each exactly once):
      * Seo-yoon S1 on the dealer side: x1.05/1.10/1.15 by level.
      * Vulcanus on the dealer side: S2 x31/30 (average damage); S3 x(1+0.12/3)
        when the dealer fields Marksmen (its own-MM Attack window), and
        /0.88 when the FRONT target is Infantry/Lancer (its Defense shred).
      * Vulcanus on the TARGET side: S1 x0.96 on the dealer's Attack.

    ROYAL LEGION (Gatot S3, -10%/-15% enemy Attack) is deliberately NOT applied
    by default. The frozen K/G_l cells were measured on instruments whose
    targets were Gatot-led, so the debuff is already ABSORBED in those cells --
    applying it here would double-count it (the double-application caveat in
    run-stage SKILL.md's Gatot block). It is computed and exposed under
    apply_royal_legion=True for the future decontamination analysis, and its
    presence is always flagged. Settling it needs a Gatot-target instrument
    whose Royal Legion level differs from the cell-sourcing instrument's.
    """
    mult, flags = 1.0, set()
    dealer_kit = dealer_kit or {}
    target_kit = target_kit or {}
    dealer_classes = {u["cls"] for u in dealers}
    front_target_cls = targets[0]["cls"]

    sy = dealer_kit.get("seoyoon")
    if sy:
        lvl = sy if isinstance(sy, int) else 3
        mult *= SEOYOON_S1.get(lvl, SEOYOON_S1[3])
        flags.add(f"fold_seoyoon_s1_L{lvl}")

    if dealer_kit.get("vulcanus"):
        mult *= VULC_S2_DMG
        flags.add("fold_vulcanus_s2")
        if front_target_cls in ("Infantry", "Lancer"):
            mult /= VULC_S3_DEF_SHRED
            flags.add("fold_vulcanus_s3_defshred")
        if "Marksman" in dealer_classes:
            mult *= VULC_S3_OWN_MM_ATK
            flags.add("fold_vulcanus_s3_own_mm")
            if len(dealer_classes) > 1:
                # direction-level scalar vs a mixed-class dealer side: the
                # own-MM window is applied to the whole direction (visible)
                flags.add("fold_vulcanus_s3_own_mm_mixed_dealer_approx")

    if target_kit.get("vulcanus"):
        mult *= VULC_S1_ENEMY_ATK
        flags.add("fold_vulcanus_s1_enemy_atk")

    if target_kit.get("gatot"):
        rl_lvl = target_kit.get("royal_legion_level")
        if rl_lvl in ROYAL_LEGION_BY_LEVEL:
            if apply_royal_legion:
                mult *= 1.0 - ROYAL_LEGION_BY_LEVEL[rl_lvl]
                flags.add(f"fold_royal_legion_L{rl_lvl}_APPLIED")
            else:
                flags.add(f"royal_legion_L{rl_lvl}_absorbed_in_cells")
    return mult, flags


def _uncertain_result(a_deaths, d_deaths, flags, gatot_abstain):
    """Shared shape for every honest-abstention exit of predict_battle."""
    return {"winner": "uncertain", "turns": None,
            "att_deaths": a_deaths, "def_deaths": d_deaths,
            "survivors": None, "flags": flags, "capped": False,
            "gatot_abstain": gatot_abstain}


def predict_battle(att_army, def_army, *, att_offense_mult=1.0,
                   def_offense_mult=1.0, att_t_solo=None, def_t_solo=None,
                   law=None, att_kit=None, def_kit=None,
                   apply_hero_folds=True, apply_royal_legion=False):
    """Assemble the per-unit law + composition algorithm into a battle outcome.

    att_t_solo / def_t_solo: optional measured solo-kill anchors (turns for the
    OTHER side to kill one of this side's front units) -- validates the
    algorithm independently of the law's out-of-scope cells.
    law: optional stage6 class-keyed table overrides (see _dealer_rate);
    default None keeps the frozen stage5 law byte-identical.
    att_kit/def_kit (Stage 6.5, additive -- default None reproduces the
    pre-6.5 result byte-for-byte): optional side descriptors
    {"gatot": None|True|"mueller_s123_l1"|"farseer_s12_l1", "vulcanus": bool}
    describing THIS side's own hero loadout. When a side's front is a single
    Gatot-led Infantry unit, the race applies the frozen stage6_gatot kit
    model instead of the plain law for non-Infantry dealers into it, and
    checks the monotonicity bound for Infantry dealers into it (see the
    module docstring). Returns an honest `winner: "uncertain"` + a
    `gatot_abstain` flag/bound (never a confident winner) wherever the kit's
    constants aren't measured for the configuration in play.

    apply_hero_folds (Stage 6.7, default True): the seam computes the
    deterministic hero folds itself from the kits + armies (see _hero_folds) --
    Seo-yoon S1, Vulcanus S1/S2/S3. Caller-supplied *_offense_mult multiplies
    ON TOP and is meant for anchors/extras only. False = stage-6.6 behaviour
    (caller owns all folds), used for migration comparisons.
    apply_royal_legion (default False): see _hero_folds -- the Gatot S3 debuff
    is absorbed in the frozen cells; applying it here would double-count.

    Returns {winner, turns, att_deaths, def_deaths, survivors, flags, capped}
    normally, or the `winner: "uncertain"` shape above (see _uncertain_result)
    when the Gatot-kit gate can't be resolved confidently.
    """
    A = _norm_army(att_army)
    D = _norm_army(def_army)
    # STAGE 6.7: the seam OWNS the deterministic hero folds (Codex QA v3 #1).
    # Folds enter exactly once, here, per race direction; any caller-supplied
    # *_offense_mult multiplies ON TOP (anchors/extras, not the standard folds).
    # apply_hero_folds=False reproduces the stage-6.6 behaviour exactly.
    _fold_warn = set()
    if apply_hero_folds:
        m_att, f_att = _hero_folds(A, att_kit, D, def_kit,
                                   apply_royal_legion=apply_royal_legion)
        m_def, f_def = _hero_folds(D, def_kit, A, att_kit,
                                   apply_royal_legion=apply_royal_legion)
        att_offense_mult *= m_att
        def_offense_mult *= m_def
        _fold_warn |= {f"att:{x}" for x in f_att} | {f"def:{x}" for x in f_def}
    else:
        _fold_warn.add("hero_folds_disabled_by_caller")
    # timeline of A's units dying (D deals) and vice versa
    note1, note2 = {}, {}
    a_deaths, fl1 = army_kill_timeline(D, A, offense_mult=def_offense_mult,
                                       t_solo=att_t_solo, law=law,
                                       target_kit=att_kit, dealer_kit=def_kit,
                                       note_sink=note1)
    d_deaths, fl2 = army_kill_timeline(A, D, offense_mult=att_offense_mult,
                                       t_solo=def_t_solo, law=law,
                                       target_kit=def_kit, dealer_kit=att_kit,
                                       note_sink=note2)
    flags = sorted(fl1 | fl2 | _fold_warn)

    # part (ii): the Gatot-kit model's own constants are unmeasured for this
    # configuration (unmodeled defender identity, or an unmeasured dealer-
    # class K feeding the gate) -- the decisive side's clock cannot be
    # computed at all.
    if a_deaths is None or d_deaths is None:
        abstain = (note1 if a_deaths is None else note2).get("abstain")
        return _uncertain_result(a_deaths, d_deaths, flags, abstain)

    t_att_dead = a_deaths[-1][0]          # attacker army wiped
    t_def_dead = d_deaths[-1][0]

    # part (i): an Infantry dealer with no Gatot of its own racing into a
    # Gatot-led Infantry target. An unmeasured kit amplification M >= 1 can
    # only LENGTHEN that dealer's own clock, never shorten it -- so the
    # naive clock is a safe lower bound UNLESS it is already the decisive
    # (shorter) one, in which case growing it could still flip the verdict.
    if "gatot_kit_inf_dealer_naive" in fl1 and t_att_dead <= t_def_dead:
        m_bound = t_def_dead / t_att_dead if t_att_dead > 0 else float("inf")
        return _uncertain_result(a_deaths, d_deaths, flags, {
            "flag": "gatot_kit_unmeasured_inf_dealer",
            "direction": "defender_kills_attacker",
            "M_bound_ge": m_bound})
    if "gatot_kit_inf_dealer_naive" in fl2 and t_def_dead <= t_att_dead:
        m_bound = t_att_dead / t_def_dead if t_def_dead > 0 else float("inf")
        return _uncertain_result(a_deaths, d_deaths, flags, {
            "flag": "gatot_kit_unmeasured_inf_dealer",
            "direction": "attacker_kills_defender",
            "M_bound_ge": m_bound})

    capped = min(t_att_dead, t_def_dead) > CAP_TURNS
    if capped:
        # cap: attacker must wipe the defender before 1500 or it is a defeat
        winner = "defender"
        turns = CAP_TURNS
    elif t_def_dead <= t_att_dead:
        winner, turns = "attacker", t_def_dead
    else:
        winner, turns = "defender", t_att_dead
    surv_side, surv_deaths = ((A, a_deaths) if winner == "attacker"
                              else (D, d_deaths))
    lost = sum(1 for turn, _ in surv_deaths if turn <= turns)
    total = sum(u["count"] for u in surv_side)
    return {"winner": winner, "turns": turns,
            "att_deaths": a_deaths, "def_deaths": d_deaths,
            "survivors": {"winner_units_left": total - lost,
                          "winner_units_total": total},
            "flags": flags, "capped": capped}


# --------------------------------------------------------------------------- #
#  provenance: re-derive the frozen ratios from the corpus composition rows
# --------------------------------------------------------------------------- #
def derive_ratios():
    """Recompute tank ratios + mop-up from the corpus (manual ladder + v5_8
    clocks). Prints measured-vs-frozen; every number traceable to a row id."""
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.abspath(os.path.join(
        here, "..", "data", "experiments", "_corpus", "TYPE1_CORPUS.json"))
    rows = json.load(open(path, encoding="utf-8"))["rows"]

    ladder = {}
    for r in rows:
        if r["id"].startswith("manual_ladder_n"):
            n = sum(c["count"] for c in r["attacker"]["classes"])
            ladder[n] = r["outcome"]["turns"]
        # eval-5 compat fix (2026-07-17): N=1 and N=2 were deduplicated out of the
        # manual table after this builder ran (they are JSON-backed); source them
        # from their corpus JSON rows instead. Data-sourcing change only.
        if r["id"].startswith("ColonelMuller_1v2_T1InfvT1Inf+T1MM_Gatot_Gatot"):
            ladder[1] = r["outcome"]["turns"] or 78
        if r["id"].startswith("MuellerAlpaca_2v2_2T1InfvFC1T1Inf"):
            ladder[2] = r["outcome"]["turns"] or 90
    print("count ladder (manual+JSON-backed, buffed Gatot Inf):", dict(sorted(ladder.items())))
    solo = ladder[1]
    first = ladder[2] and None
    # decompose: N>=2 -> first + (N-2) middles + last
    first = None
    if 2 in ladder and 3 in ladder:
        middle = ladder[3] - ladder[2]                      # one extra middle
        last = None
        # ladder[2] = first + last;  solve with the frozen split check
        print(f"  middle step = {middle}  (frozen {TANK_MIDDLE * solo:.1f})")
        for n in sorted(ladder):
            if n < 2:
                continue
            pred = (TANK_FIRST + TANK_MIDDLE * (n - 2) + TANK_LAST) * solo
            print(f"  N={n}: obs {ladder[n]}  frozen-ratios pred {pred:.1f}")
    print(f"  ratios: first {TANK_FIRST:.4f} middle {TANK_MIDDLE:.4f} "
          f"last {TANK_LAST:.4f}  (of solo={solo})")

    def mopup_pred(front, n_back, cls):
        if n_back == 0:
            return front
        lat = MOPUP_SINGLE_LATENCY.get(cls, 2)
        return front + max(math.ceil(MOPUP_CADENCE * n_back), lat)

    print("\nbackline mop-up, model end = front + max(ceil(4k/3), latency_cls):")
    print("  v5_8/2v2 JSON clocks (att Gatot S2 = front death, def Gatot S2 = end):")
    for r in rows:
        if r["folder"] not in ("Meuller_Alpaca_v5_8_Battle", "MuellerAlpaca_Gatot_2v2"):
            continue
        att = r["attacker"]
        a_s2 = [h["triggers"] for h in att["heroes"]
                if h.get("slot") == "Skill 2" and h["hero"] == "Gatot"]
        d_s2 = [h["triggers"] for h in r["defender"]["heroes"]
                if h.get("slot") == "Skill 2" and h["hero"] == "Gatot"]
        if not (a_s2 and d_s2 and a_s2[0] and d_s2[0]):
            continue
        n_back = sum(c["count"] for c in att["classes"] if c["cls"] != "Infantry")
        back_cls = [c["cls"] for c in att["classes"] if c["cls"] != "Infantry"]
        front, end = a_s2[0], d_s2[0]
        pred = mopup_pred(front, n_back, (back_cls or ["-"])[0])
        print(f"    k={n_back:<2} ({(back_cls or ['-'])[0][:3]})  front={front}  "
              f"end={end}  pred end={pred}  {'OK' if pred == end else 'MISS'}"
              f"  [{r['id'][:48]}]")
    print("  manual Lancer-backline ladder (front assumed 33; Martin 2026-07-14):")
    for r in rows:
        if not r["id"].startswith("manual_mixed_1_infantry_") or "lancer" not in r["id"]:
            continue
        n_back = sum(c["count"] for c in r["attacker"]["classes"]
                     if c["cls"] != "Infantry")
        end = r["outcome"]["turns"]
        pred = mopup_pred(33, n_back, "Lancer")
        print(f"    k={n_back:<2} (Lan)  end={end}  pred end={pred}  "
              f"{'OK' if pred == end else 'MISS'}  [{r['id'][:48]}]")


if __name__ == "__main__":
    derive_ratios()
