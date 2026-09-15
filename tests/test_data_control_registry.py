from server.data_control_registry import (
    DATA_REQUIREMENTS,
    STATUS_META,
    get_data_control_rows,
    get_data_control_summary,
)


def test_data_control_registry_has_unique_keys_and_valid_statuses():
    keys = [item.key for item in DATA_REQUIREMENTS]

    assert len(keys) == len(set(keys))
    assert all(item.status in STATUS_META for item in DATA_REQUIREMENTS)
    assert all(item.consumers for item in DATA_REQUIREMENTS)


def test_data_control_rows_are_sorted_by_usage_descending():
    rows = get_data_control_rows()
    usage_counts = [row["usage_count"] for row in rows]

    assert usage_counts == sorted(usage_counts, reverse=True)


def test_data_control_summary_matches_registry():
    summary = get_data_control_summary()

    assert summary["total"] == len(DATA_REQUIREMENTS)
    assert sum(summary["status_counts"].values()) == len(DATA_REQUIREMENTS)
    assert summary["audited"] <= summary["total"]
