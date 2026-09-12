import pytest

from server.audit_transaction_semantics_profiles import (
    SYNTHETIC_CASES,
    run_synthetic_tests,
    validate_profile,
)


@pytest.mark.parametrize("profile_id", ["graine", "gonette"])
def test_transaction_semantics_profile_is_valid(profile_id):
    assert validate_profile(profile_id) == []


@pytest.mark.parametrize("profile_id", ["graine", "gonette"])
def test_transaction_semantics_synthetic_cases(profile_id):
    results = run_synthetic_tests(profile_id)

    assert len(results) == len(SYNTHETIC_CASES[profile_id])

    failures = [
        result
        for result in results
        if not result["ok"]
    ]

    assert failures == []
