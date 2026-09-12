import pytest

from server.providers.cyclos_facts import CyclosActorFacts
from server.providers.cyclos_normalized import (
    CyclosIdentityError,
    cyclos_account_row,
)


def actor(**overrides):
    values = {
        "actor_id": "account-123",
        "actor_number": "P0001",
        "native_account_type": "comptepro",
        "user_id": "user-456",
        "user_display": "Professionnel exemple",
    }
    values.update(overrides)
    return CyclosActorFacts(**values)


def test_actor_id_becomes_contract_account_id():
    row = cyclos_account_row(actor())

    assert row == {
        "account_id": "account-123",
        "native_account_number": "P0001",
        "native_account_type": "comptepro",
        "native_status": None,
        "display_label": "Professionnel exemple",
        "native_owner_id": "user-456",
        "source_system": "cyclos",
    }


def test_account_number_is_not_required_for_identity():
    row = cyclos_account_row(
        actor(
            actor_number=None,
            native_account_type="compteparticulier",
        )
    )

    assert row["account_id"] == "account-123"
    assert row["native_account_number"] is None


def test_user_id_is_not_required_for_account_identity():
    row = cyclos_account_row(
        actor(
            user_id=None,
            native_account_type="emission",
        )
    )

    assert row["account_id"] == "account-123"
    assert row["native_owner_id"] is None


def test_same_owner_may_have_multiple_accounts():
    first = cyclos_account_row(
        actor(
            actor_id="account-a",
            user_id="shared-user",
        )
    )
    second = cyclos_account_row(
        actor(
            actor_id="account-b",
            user_id="shared-user",
        )
    )

    assert first["account_id"] != second["account_id"]
    assert first["native_owner_id"] == second["native_owner_id"]


def test_missing_actor_remains_null_reference():
    assert cyclos_account_row(None) is None


def test_present_actor_without_actor_id_fails_closed():
    with pytest.raises(
        CyclosIdentityError,
        match="sans actor.id",
    ):
        cyclos_account_row(
            actor(
                actor_id=None,
                actor_number="P9999",
                user_id="user-9999",
            )
        )
