from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[2]
AUDITS_DIR = APP_ROOT / "_audits"
JOB_LOGS_DIR = AUDITS_DIR / "job_logs"
JOB_STATE_PATH = AUDITS_DIR / "admin_integrity_job_state.json"


class IntegrityJobAlreadyRunningError(RuntimeError):
    """Un audit d’intégrité est déjà en cours."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _job_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _load_job_state() -> dict[str, Any] | None:
    if not JOB_STATE_PATH.is_file():
        return None

    try:
        payload = json.loads(JOB_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return payload if isinstance(payload, dict) else None


def _pid_is_alive(pid: Any) -> bool:
    try:
        normalized_pid = int(pid)
    except (TypeError, ValueError):
        return False

    if normalized_pid <= 0:
        return False

    try:
        os.kill(normalized_pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

    return True


def _mark_orphaned_running_job_as_error(state: dict[str, Any]) -> dict[str, Any]:
    if str(state.get("status") or "") != "running":
        return state

    if _pid_is_alive(state.get("pid")):
        return state

    state = dict(state)
    state["status"] = "error"
    state["running"] = False
    state["completed_at"] = _utc_now_iso()
    state["error_message"] = (
        "Le processus d’audit n’est plus actif, mais aucun état final "
        "n’a été enregistré."
    )
    _atomic_write_json(JOB_STATE_PATH, state)
    return state


def get_integrity_job_state() -> dict[str, Any]:
    state = _load_job_state()

    if state is None:
        return {
            "available": False,
            "status": "idle",
            "running": False,
        }

    state = _mark_orphaned_running_job_as_error(state)

    normalized = dict(state)
    normalized["available"] = True
    normalized["running"] = str(normalized.get("status") or "") == "running"
    return normalized


def start_integrity_job(
    *,
    level: str = "full",
    prefix: str = "DBINTEGRITY002",
) -> dict[str, Any]:
    existing = get_integrity_job_state()
    if existing.get("running"):
        raise IntegrityJobAlreadyRunningError(
            "Un audit d’intégrité est déjà en cours."
        )

    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    JOB_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    stamp = _job_stamp()
    job_id = f"integrity-{stamp}-{uuid.uuid4().hex[:8]}"
    log_filename = f"{prefix}_JOB_{stamp}.log"
    log_path = JOB_LOGS_DIR / log_filename

    state: dict[str, Any] = {
        "available": True,
        "job_id": job_id,
        "kind": "db_integrity_audit",
        "status": "starting",
        "running": False,
        "requested_at": _utc_now_iso(),
        "started_at": None,
        "completed_at": None,
        "level": level,
        "prefix": prefix,
        "pid": None,
        "log_filename": log_filename,
        "report_txt_filename": None,
        "report_json_filename": None,
        "integrity_status": None,
        "warnings_count": None,
        "errors_count": None,
        "exit_code": None,
        "error_message": None,
    }

    _atomic_write_json(JOB_STATE_PATH, state)

    command = [
        sys.executable,
        str(APP_ROOT / "server" / "run_admin_integrity_job.py"),
        "--job-id",
        job_id,
        "--state-path",
        str(JOB_STATE_PATH),
        "--output-dir",
        str(AUDITS_DIR),
        "--level",
        level,
        "--prefix",
        prefix,
    ]

    try:
        with log_path.open("ab") as log_handle:
            process = subprocess.Popen(
                command,
                cwd=str(APP_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
    except Exception as exc:
        state["status"] = "error"
        state["running"] = False
        state["completed_at"] = _utc_now_iso()
        state["error_message"] = f"Impossible de démarrer le job : {exc}"
        _atomic_write_json(JOB_STATE_PATH, state)
        raise

    state["status"] = "running"
    state["running"] = True
    state["started_at"] = _utc_now_iso()
    state["pid"] = process.pid
    _atomic_write_json(JOB_STATE_PATH, state)

    return get_integrity_job_state()
