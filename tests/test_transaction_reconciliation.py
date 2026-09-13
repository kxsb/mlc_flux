import sqlite3
from contextlib import contextmanager

import pytest

from server import sync_transactions


def _safe_transaction(number, cyclos_id, *, amount="10.00"):
    return {
        "transactionNumber": number,
        "id": cyclos_id,
        "date": "2026-08-01T12:00:00+00:00",
        "group": "Compte Pro",
        "from": "P0001 - Exemple",
        "to": "T_Conversion",
        "amount": amount,
        "type": "Conversion en euro",
    }


def _legacy_connection_factory(db_path):
    def factory():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    return factory


def _create_minimal_legacy_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE transactions (
            transaction_number TEXT PRIMARY KEY,
            cyclos_id TEXT,
            date TEXT NOT NULL,
            group_label TEXT,
            from_label TEXT,
            to_label TEXT,
            amount REAL,
            type_label TEXT
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX idx_transactions_cyclos_id_unique
        ON transactions (cyclos_id)
        WHERE cyclos_id IS NOT NULL AND TRIM(cyclos_id) <> ''
    """)
    conn.commit()
    conn.close()


def test_reconciliation_counts_late_transaction_as_new(
    tmp_path,
    monkeypatch,
):
    """
    Une transaction ancienne devenue visible plus tard doit être insérée lors
    d'une réconciliation, tandis que les transactions déjà connues restent des
    upserts idempotents.
    """
    db_path = tmp_path / "legacy.db"
    _create_minimal_legacy_db(db_path)

    monkeypatch.setattr(
        sync_transactions,
        "get_connection",
        _legacy_connection_factory(db_path),
    )

    known = _safe_transaction(
        "G00000001",
        "cyclos-known",
    )
    late = _safe_transaction(
        "G00000002",
        "cyclos-late",
        amount="2500.00",
    )

    first = sync_transactions.insert_transactions(
        [known],
        return_stats=True,
    )

    assert first == {
        "upserted": 1,
        "inserted_new": 1,
        "existing": 0,
    }

    reconciliation = sync_transactions.insert_transactions(
        [known, late],
        return_stats=True,
    )

    assert reconciliation == {
        "upserted": 2,
        "inserted_new": 1,
        "existing": 1,
    }

    second_reconciliation = sync_transactions.insert_transactions(
        [known, late],
        return_stats=True,
    )

    assert second_reconciliation == {
        "upserted": 2,
        "inserted_new": 0,
        "existing": 2,
    }

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT transaction_number, cyclos_id FROM transactions ORDER BY transaction_number"
    ).fetchall()
    conn.close()

    assert rows == [
        ("G00000001", "cyclos-known"),
        ("G00000002", "cyclos-late"),
    ]


def test_reconcile_cli_is_explicit_and_mutually_exclusive():
    args = sync_transactions.parse_args([
        "--reconcile-days",
        "90",
    ])

    assert args.reconcile_days == 90
    assert args.days is None
    assert args.date_from is None
    assert args.date_to is None

    with pytest.raises(SystemExit):
        sync_transactions.parse_args([
            "--days",
            "3",
            "--reconcile-days",
            "90",
        ])

    with pytest.raises(SystemExit):
        sync_transactions.parse_args([
            "--reconcile-days",
            "0",
        ])


def test_run_sync_routes_reconciliation_to_distinct_sync_state(monkeypatch):
    calls = {}

    class DummyApp:
        @contextmanager
        def app_context(self):
            yield

    monkeypatch.setattr(
        sync_transactions,
        "create_app",
        lambda: DummyApp(),
    )
    monkeypatch.setattr(
        sync_transactions,
        "init_db",
        lambda: None,
    )

    def fake_get_transactions(**kwargs):
        calls["get_transactions"] = kwargs
        return [{"id": "late-1"}]

    monkeypatch.setattr(
        sync_transactions,
        "get_transactions",
        fake_get_transactions,
    )
    monkeypatch.setattr(
        sync_transactions,
        "anonymize_transactions",
        lambda rows: rows,
    )

    def fake_insert_transactions(rows, *, return_stats=False):
        assert return_stats is True
        assert rows == [{"id": "late-1"}]
        return {
            "upserted": 1,
            "inserted_new": 1,
            "existing": 0,
        }

    monkeypatch.setattr(
        sync_transactions,
        "insert_transactions",
        fake_insert_transactions,
    )
    monkeypatch.setattr(
        sync_transactions,
        "materialize_cyclos_shadow",
        lambda rows: {
            "enabled": False,
            "status": "disabled",
        },
    )

    def fake_save_sync_state(status, message, *, sync_name="daily_sync"):
        calls["sync_state"] = {
            "status": status,
            "message": message,
            "sync_name": sync_name,
        }

    monkeypatch.setattr(
        sync_transactions,
        "save_sync_state",
        fake_save_sync_state,
    )

    result = sync_transactions.run_sync(
        reconcile_days=90,
    )

    assert calls["get_transactions"] == {
        "days": 90,
        "date_from": None,
        "date_to": None,
    }
    assert calls["sync_state"]["sync_name"] == "reconciliation_sync"
    assert calls["sync_state"]["status"] == "success"
    assert "1 nouvelle(s)" in calls["sync_state"]["message"]

    assert result["mode"] == "reconciliation"
    assert result["fetched"] == 1
    assert result["written"] == 1
    assert result["upserted"] == 1
    assert result["inserted_new"] == 1
    assert result["existing"] == 0


def test_run_sync_rejects_mixed_reconciliation_periods():
    with pytest.raises(
        ValueError,
        match="exclusif",
    ):
        sync_transactions.run_sync(
            days=3,
            reconcile_days=90,
        )
