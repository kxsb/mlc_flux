from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, UTC
from pathlib import Path
from typing import Any

from server import create_app
from server.database import init_db
from server.mlc_context import (
    get_active_mlc_db_path,
    get_active_mlc_input001_db_path,
)
from server.runtime_lock import exclusive_transaction_sync_lock
from server.services.cyclos_client import get_transactions
from server.sync_transactions import (
    _insert_transactions_for_sync,
    save_sync_state,
)
from server.utils.anonymizer import anonymize_transactions


SYNC_NAME = "historical_backfill"


@dataclass(frozen=True)
class BackfillWindow:
    date_from: date
    date_to: date

    def as_dict(self) -> dict[str, str]:
        return {
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
        }


def _parse_calendar_date(value: str, *, field_name: str) -> date:
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(
            f"{field_name} doit être au format YYYY-MM-DD."
        ) from exc


def build_year_windows(
    date_from: str,
    date_to: str,
    *,
    newest_first: bool = True,
) -> list[BackfillWindow]:
    """Découpe une période inclusive en fenêtres annuelles calendaires."""
    start = _parse_calendar_date(date_from, field_name="date_from")
    end = _parse_calendar_date(date_to, field_name="date_to")

    if end < start:
        raise ValueError("date_to doit être postérieure ou égale à date_from.")

    windows = []

    for year in range(start.year, end.year + 1):
        window_start = max(start, date(year, 1, 1))
        window_end = min(end, date(year, 12, 31))
        windows.append(
            BackfillWindow(
                date_from=window_start,
                date_to=window_end,
            )
        )

    if newest_first:
        windows.reverse()

    return windows


def _sqlite_backup(source_path: Path, destination_path: Path) -> None:
    """Create a private online SQLite backup without exposing a 0644 window."""
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(
        destination_path,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        0o600,
    )
    os.close(fd)

    source = sqlite3.connect(source_path)
    target = sqlite3.connect(destination_path)
    succeeded = False

    try:
        with target:
            source.backup(target)
        succeeded = True
    finally:
        source.close()
        target.close()

        if succeeded:
            os.chmod(destination_path, 0o600)
        else:
            try:
                destination_path.unlink()
            except FileNotFoundError:
                pass


def create_pre_backfill_backups() -> dict[str, str]:
    """Sauvegarde les bases runtime avant toute écriture historique."""
    legacy_path = get_active_mlc_db_path()
    input001_path = get_active_mlc_input001_db_path()

    backup_dir = legacy_path.parents[2] / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(backup_dir, 0o700)

    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    result: dict[str, str] = {}

    for label, source_path in (
        ("legacy", legacy_path),
        ("input001", input001_path),
    ):
        if not source_path.exists():
            continue

        destination = (
            backup_dir
            / f"{source_path.parent.name}_before_historical_backfill_{stamp}_{source_path.name}"
        )
        _sqlite_backup(source_path, destination)
        result[label] = str(destination)

    return result


def backfill_window(window: BackfillWindow) -> dict[str, Any]:
    """
    Réconcilie une fenêtre historique dans la base legacy uniquement.

    INPUT001 est volontairement laissé intact : le shadow représente le dernier
    lot de contrôle courant et ne doit pas être remplacé par une année ancienne.
    """
    app = create_app()

    with app.app_context():
        init_db()

        raw_transactions = get_transactions(
            date_from=window.date_from.isoformat(),
            date_to=window.date_to.isoformat(),
        )
        safe_transactions = anonymize_transactions(raw_transactions)
        stats = _insert_transactions_for_sync(safe_transactions)

    return {
        **window.as_dict(),
        "fetched": len(raw_transactions),
        "upserted": stats["upserted"],
        "inserted_new": stats["inserted_new"],
        "existing": stats["existing"],
    }


def _save_backfill_state(status: str, message: str) -> None:
    app = create_app()

    with app.app_context():
        init_db()
        save_sync_state(
            status=status,
            message=message,
            sync_name=SYNC_NAME,
        )


def execute_backfill(
    windows: list[BackfillWindow],
) -> dict[str, Any]:
    backups = create_pre_backfill_backups()
    results = []

    totals = {
        "fetched": 0,
        "upserted": 0,
        "inserted_new": 0,
        "existing": 0,
    }

    try:
        for window in windows:
            result = backfill_window(window)
            results.append(result)

            for key in totals:
                value = result.get(key)
                if value is not None:
                    totals[key] += int(value)

    except Exception as exc:
        _save_backfill_state(
            "error",
            (
                f"Backfill interrompu après {len(results)} fenêtre(s) réussie(s) : "
                f"{type(exc).__name__}: {exc}"
            ),
        )
        raise

    _save_backfill_state(
        "success",
        (
            f"{len(results)} fenêtre(s) ; {totals['fetched']} récupérées ; "
            f"{totals['upserted']} upsertées ; "
            f"{totals['inserted_new']} nouvelle(s) ; "
            f"{totals['existing']} déjà présente(s)"
        ),
    )

    return {
        "mode": "historical_backfill",
        "executed": True,
        "input001_shadow_updated": False,
        "backups": backups,
        "windows": results,
        "totals": totals,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill historique Cyclos contrôlé, découpé par années civiles. "
            "Sans --execute, affiche uniquement le plan."
        )
    )
    parser.add_argument(
        "--date-from",
        required=True,
        help="Début inclusif au format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--date-to",
        required=True,
        help="Fin inclusive au format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--oldest-first",
        action="store_true",
        help="Traite les fenêtres de la plus ancienne à la plus récente.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Exécute réellement le backfill et les upserts legacy.",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        windows = build_year_windows(
            args.date_from,
            args.date_to,
            newest_first=not args.oldest_first,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if not args.execute:
        report = {
            "mode": "historical_backfill",
            "executed": False,
            "input001_shadow_updated": False,
            "windows": [window.as_dict() for window in windows],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    # Le verrou couvre le backup initial et toutes les fenêtres. Un backfill qui
    # ne peut pas l'acquérir n'écrit donc ni base, ni backup, ni sync_state.
    with exclusive_transaction_sync_lock(operation=SYNC_NAME):
        report = execute_backfill(windows)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
