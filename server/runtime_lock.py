from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Iterator

from server.mlc_context import get_mlc_locks_dir


TRANSACTION_SYNC_LOCK_NAME = "transaction-sync.lock"


class RuntimeLockError(RuntimeError):
    """Base error for runtime lock failures."""


class RuntimeLockBusy(RuntimeLockError):
    """Raised when another process already owns the requested lock."""


def _load_fcntl():
    try:
        import fcntl
    except ImportError as exc:
        raise RuntimeLockError(
            "MLCFlux runtime locks require a POSIX host with fcntl support."
        ) from exc
    return fcntl


def _owner_payload(operation: str) -> dict[str, object]:
    return {
        "pid": os.getpid(),
        "operation": str(operation),
        "acquired_at": datetime.now(UTC).isoformat(),
    }


def _read_owner_text(handle) -> str:
    try:
        handle.seek(0)
        return handle.read().strip()
    except OSError:
        return ""


@contextmanager
def exclusive_file_lock(
    lock_path: Path | str,
    *,
    operation: str,
) -> Iterator[Path]:
    """Acquire a non-blocking advisory process lock on ``lock_path``.

    The file itself may remain on disk. Ownership is enforced by ``flock`` and
    is released automatically by the OS when the process exits, including
    abnormal termination. The JSON payload is diagnostic only.
    """
    fcntl = _load_fcntl()
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    handle = path.open("a+", encoding="utf-8")
    acquired = False

    try:
        try:
            fcntl.flock(
                handle.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
            acquired = True
        except BlockingIOError as exc:
            owner = _read_owner_text(handle)
            detail = f" Owner: {owner}" if owner else ""
            raise RuntimeLockBusy(
                f"Runtime lock already held: {path}.{detail}"
            ) from exc

        handle.seek(0)
        handle.truncate()
        json.dump(
            _owner_payload(operation),
            handle,
            ensure_ascii=False,
            sort_keys=True,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

        yield path
    finally:
        try:
            if acquired and not handle.closed:
                try:
                    handle.seek(0)
                    handle.truncate()
                    handle.flush()
                finally:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
        finally:
            handle.close()


def transaction_sync_lock_path() -> Path:
    """Return the shared lock path for transaction writers of the active MLC."""
    return get_mlc_locks_dir() / TRANSACTION_SYNC_LOCK_NAME


@contextmanager
def exclusive_transaction_sync_lock(
    *,
    operation: str,
) -> Iterator[Path]:
    """Serialize daily sync, reconciliation and historical backfill writers."""
    with exclusive_file_lock(
        transaction_sync_lock_path(),
        operation=operation,
    ) as path:
        yield path
