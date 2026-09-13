from server.resolver.account_report import build_account_resolution_report
from server.resolver.ruleset_loader import load_account_ruleset


def _account(account_id, native_type, *, kind=None, status=None):
    return {
        "account_id": account_id,
        "native_account_number": None,
        "native_account_type": native_type,
        "native_account_kind": kind,
        "native_account_type_label": None,
        "native_status": status,
        "display_label": None,
        "native_owner_id": None,
        "source_system": "cyclos",
    }


def _transaction(tx_id, source, destination):
    return {
        "transaction_id": tx_id,
        "source_account_id": source,
        "destination_account_id": destination,
    }


def test_gonette_ruleset_uses_native_types_without_labels_or_ids():
    ruleset = load_account_ruleset("gonette")

    report = build_account_resolution_report(
        accounts=[
            _account("opaque-a", "compteparticulier"),
            _account("opaque-b", "comptepro"),
            _account("opaque-c", "emission"),
            _account("opaque-d", "Conversion"),
        ],
        transactions=[],
        ruleset=ruleset,
    )

    assert report["summary"] == {
        "accounts_total": 4,
        "resolved": 4,
        "unknown": 0,
        "conflict": 0,
        "families": {
            "individual": 1,
            "professional": 1,
            "technical": 2,
        },
    }


def test_unknown_native_type_remains_unknown_and_is_visible_in_fact_report():
    ruleset = load_account_ruleset("gonette")

    report = build_account_resolution_report(
        accounts=[
            _account("opaque-a", "futureAccountType", kind="user"),
            _account("opaque-b", None),
        ],
        transactions=[],
        ruleset=ruleset,
    )

    assert report["summary"]["unknown"] == 2
    assert report["fact_coverage"] == {
        "unknown_native_account_type": 1,
        "unknown_native_account_kind": 1,
    }
    assert any(
        row["native_account_type"] == "futureAccountType"
        and row["resolver_statuses"] == {"unknown": 1}
        for row in report["fact_combinations"]
    )


def test_legacy_comparison_detects_operator_divergence_instead_of_masking_it():
    ruleset = load_account_ruleset("gonette")
    accounts = [
        _account("operator-account", "comptepro"),
        _account("ordinary-pro", "comptepro"),
    ]
    transactions = [
        _transaction("tx-1", "ordinary-pro", "operator-account"),
    ]
    legacy = [
        {
            "cyclos_id": "tx-1",
            "from_actor_family": "professional",
            "to_actor_family": "operator",
        }
    ]

    report = build_account_resolution_report(
        accounts=accounts,
        transactions=transactions,
        ruleset=ruleset,
        legacy_semantics_rows=legacy,
    )

    comparison = report["legacy_comparison"]
    assert comparison["available"] is True
    assert comparison["legacy_classifiable"] == 2
    assert comparison["legacy_vs_resolver_same"] == 1
    assert comparison["legacy_vs_resolver_different"] == 1
    assert comparison["legacy_families"] == {
        "operator": 1,
        "professional": 1,
    }


def test_conflicting_legacy_votes_are_reported_separately():
    ruleset = load_account_ruleset("gonette")
    accounts = [_account("account-a", "comptepro")]
    transactions = [
        _transaction("tx-1", "account-a", None),
        _transaction("tx-2", "account-a", None),
    ]
    legacy = [
        {
            "cyclos_id": "tx-1",
            "from_actor_family": "professional",
            "to_actor_family": "unknown",
        },
        {
            "cyclos_id": "tx-2",
            "from_actor_family": "operator",
            "to_actor_family": "unknown",
        },
    ]

    report = build_account_resolution_report(
        accounts=accounts,
        transactions=transactions,
        ruleset=ruleset,
        legacy_semantics_rows=legacy,
    )

    comparison = report["legacy_comparison"]
    assert comparison["legacy_classifiable"] == 0
    assert comparison["legacy_conflict"] == 1
    assert comparison["legacy_vs_resolver_same"] == 0
    assert comparison["legacy_vs_resolver_different"] == 0


def test_report_is_aggregate_and_does_not_expose_account_identity_fields():
    ruleset = load_account_ruleset("gonette")
    report = build_account_resolution_report(
        accounts=[
            {
                **_account("secret-account-id", "comptepro"),
                "display_label": "Visible business name",
                "native_owner_id": "secret-owner-id",
                "native_account_number": "P1234",
            }
        ],
        transactions=[],
        ruleset=ruleset,
    )

    serialized = str(report)
    assert "secret-account-id" not in serialized
    assert "Visible business name" not in serialized
    assert "secret-owner-id" not in serialized
    assert "P1234" not in serialized
