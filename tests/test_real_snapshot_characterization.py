from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from server.audit_transaction_semantics_comparison import (
    build_comparison,
)


ROOT = Path(__file__).resolve().parents[1]

BASELINE_PATH = (
    ROOT
    / "tests"
    / "baselines"
    / "neutral_runtime_20260912.json"
)

FINGERPRINT_KEYS = (
    "rows",
    "classifier_versions",
    "legacy_flows",
    "legacy_buckets",
    "semantic_operations",
    "semantic_circuits",
    "cross_legacy_bucket_operation",
    "cross_legacy_flow_operation",
)


def _fingerprint_report(report):
    payload = {
        key: report[key]
        for key in FINGERPRINT_KEYS
    }

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(canonical).hexdigest()


@pytest.mark.parametrize(
    "mlc_id",
    ["gonette", "graine"],
)
def test_real_snapshot_semantic_fingerprint(
    mlc_id,
    monkeypatch,
):
    """
    Test local de caractérisation sur le snapshot de production
    figé au début du chantier Neutral.

    Les données réelles ne sont jamais versionnées.
    Le test est ignoré si le snapshot local n'est pas installé.
    """

    db_path = (
        ROOT
        / "server"
        / "data"
        / "instances"
        / mlc_id
        / "mlcflux.db"
    )

    if not db_path.exists():
        pytest.skip(
            f"Snapshot runtime {mlc_id} non installé."
        )

    baseline = json.loads(
        BASELINE_PATH.read_text(encoding="utf-8")
    )

    monkeypatch.setenv(
        "MLCFLUX_DEFAULT_MLC_ID",
        mlc_id,
    )

    report = build_comparison(
        limit_examples=0
    )

    actual = _fingerprint_report(report)

    expected = baseline["profiles"][mlc_id]["fingerprint"]

    assert actual == expected
