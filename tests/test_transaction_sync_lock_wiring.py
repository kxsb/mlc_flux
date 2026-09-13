from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from server import backfill_transactions, sync_transactions
from server.runtime_lock import RuntimeLockBusy


def _recording_lock(events):
    @contextmanager
    def lock(*, operation):
        events.append(("lock_enter", operation))
        try:
            yield
        finally:
            events.append(("lock_exit", operation))

    return lock


def test_daily_sync_cli_runs_inside_shared_lock(monkeypatch):
    events = []
    monkeypatch.setattr(
        sync_transactions,
        "exclusive_transaction_sync_lock",
        _recording_lock(events),
    )

    def fake_run_sync(**kwargs):
        events.append(("run_sync", kwargs))
        return {"mode": "daily"}

    monkeypatch.setattr(sync_transactions, "run_sync", fake_run_sync)

    assert sync_transactions.main([]) == 0
    assert events == [
        ("lock_enter", "daily_sync"),
        (
            "run_sync",
            {
                "days": None,
                "date_from": None,
                "date_to": None,
                "reconcile_days": None,
            },
        ),
        ("lock_exit", "daily_sync"),
    ]


def test_reconciliation_cli_uses_same_lock_with_distinct_operation(monkeypatch):
    events = []
    monkeypatch.setattr(
        sync_transactions,
        "exclusive_transaction_sync_lock",
        _recording_lock(events),
    )

    def fake_run_sync(**kwargs):
        events.append(("run_sync", kwargs))
        return {"mode": "reconciliation"}

    monkeypatch.setattr(sync_transactions, "run_sync", fake_run_sync)

    assert sync_transactions.main(["--reconcile-days", "90"]) == 0
    assert events[0] == ("lock_enter", "reconciliation_sync")
    assert events[1][0] == "run_sync"
    assert events[1][1]["reconcile_days"] == 90
    assert events[-1] == ("lock_exit", "reconciliation_sync")


def test_busy_sync_lock_stops_before_runtime_or_sync_state_writes(monkeypatch):
    @contextmanager
    def busy_lock(*, operation):
        raise RuntimeLockBusy(f"busy: {operation}")
        yield

    run_sync = Mock()
    create_app = Mock()

    monkeypatch.setattr(
        sync_transactions,
        "exclusive_transaction_sync_lock",
        busy_lock,
    )
    monkeypatch.setattr(sync_transactions, "run_sync", run_sync)
    monkeypatch.setattr(sync_transactions, "create_app", create_app)

    with pytest.raises(RuntimeLockBusy, match="daily_sync"):
        sync_transactions.main([])

    run_sync.assert_not_called()
    create_app.assert_not_called()


def test_backfill_dry_run_never_acquires_writer_lock(monkeypatch, capsys):
    @contextmanager
    def forbidden_lock(*, operation):
        raise AssertionError("dry-run must not acquire writer lock")
        yield

    execute = Mock()
    monkeypatch.setattr(
        backfill_transactions,
        "exclusive_transaction_sync_lock",
        forbidden_lock,
    )
    monkeypatch.setattr(backfill_transactions, "execute_backfill", execute)

    assert backfill_transactions.main([
        "--date-from", "2026-01-01",
        "--date-to", "2026-01-02",
    ]) == 0

    execute.assert_not_called()
    assert '"executed": false' in capsys.readouterr().out


def test_backfill_execute_wraps_backup_and_all_windows_in_shared_lock(
    monkeypatch,
    capsys,
):
    events = []
    monkeypatch.setattr(
        backfill_transactions,
        "exclusive_transaction_sync_lock",
        _recording_lock(events),
    )

    def fake_execute(windows):
        events.append(("execute", [window.as_dict() for window in windows]))
        return {
            "mode": "historical_backfill",
            "executed": True,
            "input001_shadow_updated": False,
            "backups": {},
            "windows": [],
            "totals": {},
        }

    monkeypatch.setattr(
        backfill_transactions,
        "execute_backfill",
        fake_execute,
    )

    assert backfill_transactions.main([
        "--date-from", "2025-01-01",
        "--date-to", "2026-06-14",
        "--execute",
    ]) == 0

    assert events[0] == ("lock_enter", "historical_backfill")
    assert events[1][0] == "execute"
    assert events[1][1] == [
        {"date_from": "2026-01-01", "date_to": "2026-06-14"},
        {"date_from": "2025-01-01", "date_to": "2025-12-31"},
    ]
    assert events[-1] == ("lock_exit", "historical_backfill")
    assert '"executed": true' in capsys.readouterr().out
