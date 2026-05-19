from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(PROJECT_ROOT))

from server.database import DB_PATH
from server.services.db_integrity import (
    integrity_report_as_json,
    render_integrity_report_text,
    run_db_integrity_test,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def _status_to_exit_code(status: str | None) -> int:
    normalized = str(status or "").strip().lower()
    if normalized == "healthy":
        return 0
    if normalized == "degraded":
        return 1
    return 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exécute un audit d’intégrité DB MLCFlux en job autonome."
    )
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--level", choices=("quick", "full"), default="full")
    parser.add_argument("--prefix", default="DBINTEGRITY002")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    state_path = Path(args.state_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    state = _load_state(state_path)
    state.update(
        {
            "available": True,
            "job_id": args.job_id,
            "kind": "db_integrity_audit",
            "status": "running",
            "running": True,
            "started_at": state.get("started_at") or _utc_now_iso(),
            "completed_at": None,
            "level": args.level,
            "prefix": args.prefix,
            "pid": os.getpid(),
            "error_message": None,
        }
    )
    _atomic_write_json(state_path, state)

    try:
        suffix = _stamp()
        txt_path = output_dir / f"{args.prefix}_{suffix}.txt"
        json_path = output_dir / f"{args.prefix}_{suffix}.json"

        report = run_db_integrity_test(DB_PATH, level=args.level)
        txt_path.write_text(
            render_integrity_report_text(report) + "\n",
            encoding="utf-8",
        )
        json_path.write_text(
            integrity_report_as_json(report) + "\n",
            encoding="utf-8",
        )

        status = str(report.get("status") or "critical")
        exit_code = _status_to_exit_code(status)

        state = _load_state(state_path)
        state.update(
            {
                "status": "finished",
                "running": False,
                "completed_at": _utc_now_iso(),
                "report_txt_filename": txt_path.name,
                "report_json_filename": json_path.name,
                "integrity_status": status,
                "warnings_count": len(report.get("warnings") or []),
                "errors_count": len(report.get("errors") or []),
                "exit_code": exit_code,
                "error_message": None,
            }
        )
        _atomic_write_json(state_path, state)

        print("========================================================================")
        print("JOB AUDIT INTÉGRITÉ TERMINÉ")
        print("========================================================================")
        print(f"Statut intégrité : {status.upper()}")
        print(f"Rapport TXT      : {txt_path}")
        print(f"Rapport JSON     : {json_path}")
        print(f"Code retour      : {exit_code}")
        print("========================================================================")
        return exit_code

    except Exception as exc:
        state = _load_state(state_path)
        state.update(
            {
                "status": "error",
                "running": False,
                "completed_at": _utc_now_iso(),
                "error_message": str(exc),
                "exit_code": 3,
            }
        )
        _atomic_write_json(state_path, state)

        print("========================================================================")
        print("ERREUR JOB AUDIT INTÉGRITÉ")
        print("========================================================================")
        print(str(exc))
        print()
        traceback.print_exc()
        print("========================================================================")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
