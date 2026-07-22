from .constraints import derive_one_v_one_constraints
from .dataset import discover_nanomart


def test_constraint_audit_exposes_incompatible_t5_clocks() -> None:
    records = [record for record in discover_nanomart() if record.included]
    rows, conflicts = derive_one_v_one_constraints(records)

    assert len(rows) == 37
    # 2026-07-19 refresh (Stage 6.6 housekeeping, eval-6 recommendation):
    # this test originally asserted the L32/L69 T5-clock CONFLICT EXISTS.
    # Martin's screenshot-verified counter-correction of 2026-07-14 (L69
    # counters T11->T13, T23->T27, 67-69->79-81) DISSOLVED it -- the two T5
    # reports now agree. The audit machinery is still exercised; the corrected
    # data-state is zero conflicts.
    assert len(conflicts) == 0
