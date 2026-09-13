from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import threading
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


_transaction_lock_local = threading.local()


def _thread_transaction_locks() -> dict[str, dict[str, object]]:
    locks = getattr(_transaction_lock_local, "locks", None)
    if locks is None:
        locks = {}
        _transaction_lock_local.locks = locks
    return locks


@contextmanager
def exclusive_transaction_sync_lock(
    *,
    operation: str,
) -> Iterator[Path]:
    """Serialize supported transaction writers for the active MLC.

    Re-entry is allowed only in the same thread and for the same logical
    operation. This lets high-level entrypoints and the shared runtime service
    both enforce the lock without deadlocking each other, while a second thread
    or process still fails fast through ``flock``.
    """
    path = transaction_sync_lock_path()
    key = str(path.resolve())
    held = _thread_transaction_locks()
    current = held.get(key)

    if current is not None:
        current_operation = str(current["operation"])
        if current_operation != str(operation):
            raise RuntimeLockError(
                "Transaction writer lock re-entered with a different operation: "
                f"{current_operation!r} -> {operation!r}."
            )

        current["depth"] = int(current["depth"]) + 1
        try:
            yield path
        finally:
            current["depth"] = int(current["depth"]) - 1
        return

    with exclusive_file_lock(
        path,
        operation=operation,
    ) as acquired_path:
        held[key] = {
            "operation": str(operation),
            "depth": 1,
        }
        try:
            yield acquired_path
        finally:
            held.pop(key, None)
