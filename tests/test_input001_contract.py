import json
from datetime import datetime
from pathlib import Path


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "input001"
    / "normalized_reference_cases.json"
)

FORBIDDEN_CLASSIFICATION_FIELDS = {
    "family",
    "actor_family",
    "from_family",
    "to_family",
    "mlc_family",
}


def _load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _parse_datetime(value):
    if value is None:
        return
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_input001_reference_datasets_are_structurally_valid():
    payload = _load()

    assert payload["contract_version"] == "input001-v0.1"
    assert payload["datasets"]

    for dataset in payload["datasets"]:
        assert dataset["metadata"]["source_system"]
        assert dataset["accounts"]
        assert dataset["transactions"]

        accounts = {
            account["account_id"]: account
            for account in dataset["accounts"]
        }

        assert len(accounts) == len(dataset["accounts"])

        for account in dataset["accounts"]:
            assert account["account_id"]
            assert not (FORBIDDEN_CLASSIFICATION_FIELDS & account.keys())

        transaction_ids = set()

        for transaction in dataset["transactions"]:
            assert transaction["transaction_id"]
            assert transaction["transaction_id"] not in transaction_ids
            transaction_ids.add(transaction["transaction_id"])

            assert transaction["source_account_id"] in accounts
            assert transaction["destination_account_id"] in accounts

            assert isinstance(transaction["amount_minor"], int)
            assert not isinstance(transaction["amount_minor"], bool)

            assert isinstance(transaction["currency_exponent"], int)
            assert not isinstance(transaction["currency_exponent"], bool)
            assert transaction["currency_exponent"] >= 0

            _parse_datetime(transaction["occurred_at"])

            assert not (
                FORBIDDEN_CLASSIFICATION_FIELDS & transaction.keys()
            )


def test_input001_temporal_relations_reference_known_accounts():
    payload = _load()

    for dataset in payload["datasets"]:
        account_ids = {
            account["account_id"]
            for account in dataset["accounts"]
        }

        for state in dataset.get("account_states", []):
            assert state["account_id"] in account_ids
            _parse_datetime(state["valid_from"])
            _parse_datetime(state.get("valid_to"))

        for replacement in dataset.get("account_replacements", []):
            assert replacement["old_account_id"] in account_ids
            assert replacement["new_account_id"] in account_ids
            assert replacement["old_account_id"] != replacement["new_account_id"]
            _parse_datetime(replacement["effective_at"])


def test_input001_contract_contains_no_final_mlc_classification():
    payload = _load()

    serialized = json.dumps(payload, ensure_ascii=False)

    for forbidden in (
        '"from_family"',
        '"to_family"',
        '"actor_family"',
        '"mlc_family"',
    ):
        assert forbidden not in serialized
