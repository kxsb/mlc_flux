import json
import os

import pytest

from server import runtime_lock


pytestmark = pytest.mark.skipif(
    os.name != "posix",
    reason="Runtime lock contract targets the Linux/POSIX deployment host.",
)


def test_exclusive_file_lock_blocks_second_owner_and_preserves_metadata(tmp_path):
    path = tmp_path / "transaction-sync.lock"

    with runtime_lock.exclusive_file_lock(
        path,
        operation="historical_backfill",
    ):
        owner = json.loads(path.read_text(encoding="utf-8"))
        assert owner["pid"] == os.getpid()
        assert owner["operation"] == "historical_backfill"
        assert owner["acquired_at"]

        with pytest.raises(
            runtime_lock.RuntimeLockBusy,
            match="already held",
        ) as error:
            with runtime_lock.exclusive_file_lock(
                path,
                operation="daily_sync",
            ):
                raise AssertionError("second owner must never enter")

        assert "historical_backfill" in str(error.value)

        still_owner = json.loads(path.read_text(encoding="utf-8"))
        assert still_owner["operation"] == "historical_backfill"


def test_lock_is_released_and_file_cleared_after_normal_exit(tmp_path):
    path = tmp_path / "transaction-sync.lock"

    with runtime_lock.exclusive_file_lock(
        path,
        operation="daily_sync",
    ):
        assert path.read_text(encoding="utf-8").strip()

    assert path.exists()
    assert path.read_text(encoding="utf-8") == ""

    with runtime_lock.exclusive_file_lock(
        path,
        operation="reconciliation_sync",
    ):
        owner = json.loads(path.read_text(encoding="utf-8"))
        assert owner["operation"] == "reconciliation_sync"


def test_lock_is_released_after_exception(tmp_path):
    path = tmp_path / "transaction-sync.lock"

    with pytest.raises(RuntimeError, match="boom"):
        with runtime_lock.exclusive_file_lock(
            path,
            operation="historical_backfill",
        ):
            raise RuntimeError("boom")

    with runtime_lock.exclusive_file_lock(
        path,
        operation="daily_sync",
    ):
        owner = json.loads(path.read_text(encoding="utf-8"))
        assert owner["operation"] == "daily_sync"


def test_transaction_sync_lock_uses_active_instance_locks_dir(
    tmp_path,
    monkeypatch,
):
    locks_dir = tmp_path / "runtime" / "locks"
    monkeypatch.setattr(
        runtime_lock,
        "get_mlc_locks_dir",
        lambda: locks_dir,
    )

    expected = locks_dir / runtime_lock.TRANSACTION_SYNC_LOCK_NAME
    assert runtime_lock.transaction_sync_lock_path() == expected

    with runtime_lock.exclusive_transaction_sync_lock(
        operation="daily_sync",
    ) as acquired:
        assert acquired == expected
        owner = json.loads(expected.read_text(encoding="utf-8"))
        assert owner["operation"] == "daily_sync"


def test_transaction_sync_lock_reenters_same_operation_without_relocking(
    tmp_path,
    monkeypatch,
):
    locks_dir = tmp_path / "runtime" / "locks"
    monkeypatch.setattr(
        runtime_lock,
        "get_mlc_locks_dir",
        lambda: locks_dir,
    )

    expected = locks_dir / runtime_lock.TRANSACTION_SYNC_LOCK_NAME

    with runtime_lock.exclusive_transaction_sync_lock(
        operation="daily_sync",
    ) as outer:
        owner_before = expected.read_text(encoding="utf-8")

        with runtime_lock.exclusive_transaction_sync_lock(
            operation="daily_sync",
        ) as inner:
            assert inner == outer == expected
            assert expected.read_text(encoding="utf-8") == owner_before

        assert expected.read_text(encoding="utf-8") == owner_before

    assert expected.read_text(encoding="utf-8") == ""


def test_transaction_sync_lock_rejects_nested_different_operation(
    tmp_path,
    monkeypatch,
):
    locks_dir = tmp_path / "runtime" / "locks"
    monkeypatch.setattr(
        runtime_lock,
        "get_mlc_locks_dir",
        lambda: locks_dir,
    )

    with runtime_lock.exclusive_transaction_sync_lock(
        operation="daily_sync",
    ):
        with pytest.raises(
            runtime_lock.RuntimeLockError,
            match="different operation",
        ):
            with runtime_lock.exclusive_transaction_sync_lock(
                operation="historical_backfill",
            ):
                raise AssertionError("different nested operation must not enter")
