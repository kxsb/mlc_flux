import pytest

from server.resolver import (
    AccountFactCondition,
    AccountResolutionRule,
    AccountResolverRuleset,
    ResolverConfigurationError,
    ResolverInputError,
    resolve_account,
    resolve_accounts,
)


def _condition(field, *values):
    return AccountFactCondition(field=field, values=tuple(values))


def _rule(rule_id, family, *conditions, reason=None):
    return AccountResolutionRule(
        rule_id=rule_id,
        family=family,
        conditions=tuple(conditions),
        reason=reason,
    )


def _ruleset(*rules):
    return AccountResolverRuleset(
        version="resolver001-test-v1",
        rules=tuple(rules),
    )


def _account(**overrides):
    return {
        "account_id": "account-001",
        "source_system": "source-a",
        "native_account_type": "merchantAccount",
        "native_account_kind": "current",
        "native_status": "active",
        "display_label": "Nom affiché sans valeur sémantique",
        "native_owner_id": "owner-001",
        **overrides,
    }


def test_resolves_from_explicit_native_account_type_fact():
    ruleset = _ruleset(
        _rule(
            "native-merchant",
            "professional",
            _condition("native_account_type", "merchantAccount"),
            reason="Type natif explicitement déclaré professionnel.",
        )
    )

    result = resolve_account(_account(), ruleset=ruleset)

    assert result.status == "resolved"
    assert result.family == "professional"
    assert result.rule == "native-merchant"
    assert result.matched_rules == ("native-merchant",)
    assert result.evidence[0].matched_facts == (
        ("native_account_type", "merchantAccount"),
    )
    assert result.ruleset_version == "resolver001-test-v1"


def test_rule_can_scope_native_fact_to_a_source_system():
    ruleset = _ruleset(
        _rule(
            "source-a-merchant",
            "professional",
            _condition("source_system", "source-a"),
            _condition("native_account_type", "merchantAccount"),
        )
    )

    matching = resolve_account(_account(), ruleset=ruleset)
    other_source = resolve_account(
        _account(account_id="account-002", source_system="source-b"),
        ruleset=ruleset,
    )

    assert matching.status == "resolved"
    assert other_source.status == "unknown"
    assert other_source.family is None


def test_display_label_and_identifiers_never_classify_an_account():
    ruleset = _ruleset(
        _rule(
            "known-private-type",
            "individual",
            _condition("native_account_type", "privateAccount"),
        )
    )

    result = resolve_account(
        _account(
            native_account_type=None,
            native_account_kind=None,
            display_label="P9999",
            native_owner_id="professional-looking-owner",
        ),
        ruleset=ruleset,
    )

    assert result.status == "unknown"
    assert result.family is None
    assert result.evidence == ()


def test_conflicting_native_facts_are_exposed_instead_of_prioritized_silently():
    ruleset = _ruleset(
        _rule(
            "merchant-type",
            "professional",
            _condition("native_account_type", "merchantAccount"),
        ),
        _rule(
            "technical-kind",
            "technical",
            _condition("native_account_kind", "current"),
        ),
    )

    result = resolve_account(_account(), ruleset=ruleset)

    assert result.status == "conflict"
    assert result.family is None
    assert result.rule is None
    assert result.matched_rules == (
        "merchant-type",
        "technical-kind",
    )
    assert {item.family for item in result.evidence} == {
        "professional",
        "technical",
    }


def test_multiple_matching_rules_for_same_family_remain_resolved_with_full_evidence():
    ruleset = _ruleset(
        _rule(
            "merchant-type",
            "professional",
            _condition("native_account_type", "merchantAccount"),
        ),
        _rule(
            "merchant-kind",
            "professional",
            _condition("native_account_kind", "current"),
        ),
    )

    result = resolve_account(_account(), ruleset=ruleset)

    assert result.status == "resolved"
    assert result.family == "professional"
    assert result.rule is None
    assert result.matched_rules == (
        "merchant-type",
        "merchant-kind",
    )
    assert len(result.evidence) == 2


def test_missing_native_fact_stays_unknown_without_fallback():
    ruleset = _ruleset(
        _rule(
            "private-type",
            "individual",
            _condition("native_account_type", "privateAccount"),
        )
    )

    result = resolve_account(
        _account(native_account_type=None),
        ruleset=ruleset,
    )

    assert result.as_dict() == {
        "account_id": "account-001",
        "family": None,
        "status": "unknown",
        "rule": None,
        "matched_rules": [],
        "evidence": [],
        "ruleset_version": "resolver001-test-v1",
    }


def test_ruleset_rejects_display_label_as_semantic_evidence():
    with pytest.raises(
        ResolverConfigurationError,
        match="Champ de résolution non autorisé",
    ):
        _condition("display_label", "Professionnel")


def test_batch_resolution_preserves_order_and_requires_stable_account_id():
    ruleset = _ruleset(
        _rule(
            "merchant-type",
            "professional",
            _condition("native_account_type", "merchantAccount"),
        )
    )

    results = resolve_accounts(
        [
            _account(account_id="account-b"),
            _account(account_id="account-a", native_account_type=None),
        ],
        ruleset=ruleset,
    )

    assert [result.account_id for result in results] == [
        "account-b",
        "account-a",
    ]
    assert [result.status for result in results] == [
        "resolved",
        "unknown",
    ]

    with pytest.raises(ResolverInputError, match="account_id"):
        resolve_account(
            _account(account_id=""),
            ruleset=ruleset,
        )
