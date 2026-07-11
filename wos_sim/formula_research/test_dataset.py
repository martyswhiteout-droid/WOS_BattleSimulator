from .dataset import discover_nanomart, manifest_summary


def test_canonical_nanomart_manifest_has_seventy_included_fixtures():
    records = discover_nanomart()
    summary = manifest_summary(records)

    assert summary["discovered"] == 71
    assert summary["included"] == 70
    assert summary["excluded"] == 1
    assert summary["excluded_ids"][0]["report_id"].startswith(
        "NanoMart_1v1_T1LanvT1Inf"
    )


def test_every_included_record_has_complete_deployed_stats():
    for record in discover_nanomart():
        if not record.included:
            continue
        assert set(record.attacker.panel_pct) == {
            "Attack",
            "Defense",
            "Lethality",
            "Health",
        }
        assert set(record.defender.panel_pct) == {
            "Attack",
            "Defense",
            "Lethality",
            "Health",
        }
        assert record.attacker.tier >= 1
        assert record.defender.tier >= 1
