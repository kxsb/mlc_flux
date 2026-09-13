import sqlite3
from datetime import UTC, datetime

from server.input_contract.reader import FinancialContractReader
from server.input_contract.runtime import create_input001_engine
from server.input_contract.writer import (
    FinancialDatasetPayload,
    materialize_financial_dataset,
)
from server.mlc_context import (
    get_mlc_db_path,
    get_mlc_input001_db_path,
)


def test_input001_path_is_distinct_from_legacy():
    legacy = get_mlc_db_path("graine")
    normalized = get_mlc_input001_db_path("graine")

    assert legacy != normalized
    assert legacy.parent == normalized.parent

    assert legacy.name == "mlcflux.db"
    assert normalized.name == "input001.db"


def test_shadow_materialization_does_not_touch_legacy(
    tmp_path,
    monkeypatch,
):
    legacy_path = tmp_path / "mlcflux.db"
    input001_path = tmp_path / "input001.db"

    with sqlite3.connect(legacy_path) as conn:
        conn.execute(
            """
            CREATE TABLE transactions (
                transaction_number TEXT PRIMARY KEY,
                amount REAL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO transactions (
                transaction_number,
                amount
            )
            VALUES (?, ?)
            """,
            ("legacy-001", 12.5),
        )

    import server.input_contract.runtime as runtime

    monkeypatch.setattr(
        runtime,
        "get_mlc_input001_db_path",
        lambda mlc_id=None: input001_path,
    )

    monkeypatch.setattr(
        runtime,
        "ensure_mlc_instance_dirs",
        lambda mlc_id=None: {
            "instance_dir": tmp_path,
            "runtime_dir": tmp_path / "runtime",
            "locks_dir": tmp_path / "runtime" / "locks",
            "db_path": legacy_path,
        },
    )

    engine = runtime.create_input001_engine()

    payload = FinancialDatasetPayload(
        dataset_metadata={
            "dataset_id": "shadow-test",
            "contract_version": "input001-v0.1",
            "source_system": "cyclos",
            "account_state_history": False,
            "balances": False,
            "account_replacements": False,
        },
        accounts=[
            {
                "account_id": "A",
                "source_system": "cyclos",
            },
            {
                "account_id": "B",
                "source_system": "cyclos",
            },
        ],
        transactions=[
            {
                "transaction_id": "normalized-001",
                "occurred_at": datetime(
                    2026, 9, 13, 12, 0, tzinfo=UTC
                ),
                "source_account_id": "A",
                "destination_account_id": "B",
                "amount_minor": 1250,
                "currency_code": "LOCAL",
                "currency_exponent": 2,
            }
        ],
    )

    materialize_financial_dataset(engine, payload)

    reader = FinancialContractReader(engine)

    assert (
        reader.fetch_transactions()[0]["transaction_id"]
        == "normalized-001"
    )

    with sqlite3.connect(legacy_path) as conn:
        rows = conn.execute(
            """
            SELECT transaction_number, amount
            FROM transactions
            """
        ).fetchall()

    assert rows == [("legacy-001", 12.5)]


def test_runtime_refuses_legacy_database_alias(
    tmp_path,
    monkeypatch,
):
    shared = tmp_path / "shared.db"

    import server.input_contract.runtime as runtime

    monkeypatch.setattr(
        runtime,
        "get_mlc_input001_db_path",
        lambda mlc_id=None: shared,
    )

    monkeypatch.setattr(
        runtime,
        "ensure_mlc_instance_dirs",
        lambda mlc_id=None: {
            "instance_dir": tmp_path,
            "runtime_dir": tmp_path / "runtime",
            "locks_dir": tmp_path / "runtime" / "locks",
            "db_path": shared,
        },
    )

    try:
        runtime.create_input001_engine()
    except RuntimeError as exc:
        assert "jamais être la base legacy" in str(exc)
    else:
        raise AssertionError(
            "Le runtime aurait dû refuser la base legacy."
        )


def test_runtime_creates_input001_database_with_private_permissions(
    tmp_path,
    monkeypatch,
):
    import stat
    import server.input_contract.runtime as runtime

    legacy_path = tmp_path / "mlcflux.db"
    input001_path = tmp_path / "input001.db"

    monkeypatch.setattr(
        runtime,
        "get_mlc_input001_db_path",
        lambda mlc_id=None: input001_path,
    )

    monkeypatch.setattr(
        runtime,
        "ensure_mlc_instance_dirs",
        lambda mlc_id=None: {
            "instance_dir": tmp_path,
            "runtime_dir": tmp_path / "runtime",
            "locks_dir": tmp_path / "runtime" / "locks",
            "db_path": legacy_path,
        },
    )

    assert not input001_path.exists()

    engine = runtime.create_input001_engine()

    assert input001_path.exists()

    mode = stat.S_IMODE(
        input001_path.stat().st_mode
    )

    assert mode == 0o600

    engine.dispose()


def test_runtime_repairs_existing_input001_permissions(
    tmp_path,
    monkeypatch,
):
    import stat
    import server.input_contract.runtime as runtime

    legacy_path = tmp_path / "mlcflux.db"
    input001_path = tmp_path / "input001.db"

    input001_path.touch()
    input001_path.chmod(0o644)

    monkeypatch.setattr(
        runtime,
        "get_mlc_input001_db_path",
        lambda mlc_id=None: input001_path,
    )

    monkeypatch.setattr(
        runtime,
        "ensure_mlc_instance_dirs",
        lambda mlc_id=None: {
            "instance_dir": tmp_path,
            "runtime_dir": tmp_path / "runtime",
            "locks_dir": tmp_path / "runtime" / "locks",
            "db_path": legacy_path,
        },
    )

    runtime.create_input001_engine().dispose()

    mode = stat.S_IMODE(
        input001_path.stat().st_mode
    )

    assert mode == 0o600
