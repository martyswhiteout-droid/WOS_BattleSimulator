from .constraints import derive_one_v_one_constraints
from .dataset import discover_nanomart


def test_constraint_audit_exposes_incompatible_t5_clocks() -> None:
    records = [record for record in discover_nanomart() if record.included]
    rows, conflicts = derive_one_v_one_constraints(records)

    assert len(rows) == 37
    assert len(conflicts) == 1
    assert set(conflicts[0]["reports"]) == {
        "NanoMart_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus",
        "NanoMart_SetA_1v1_T5InfvT1Inf_SeoYoonlvl3_Vulcanus",
    }
