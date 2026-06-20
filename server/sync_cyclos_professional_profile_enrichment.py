#!/usr/bin/env python3
"""
Synchronise les enrichissements de profils professionnels depuis Cyclos.

Objectif :
- éviter que les catégories internes restent figées après modification dans Cyclos ;
- historiser localement les changements détectés ;
- fournir un mode dry-run avant écriture.

La fenêtre `days` reste une fenêtre de transactions utilisée par le service existant
pour identifier les acteurs à rafraîchir. Pour un refresh complet, utiliser une
grande fenêtre et `--limit none`.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from server.database import get_db_path
from server.services.cyclos_professional_profile_enrichment import (
    fetch_professional_profile_enrichment_sample,
    sync_professional_profile_enrichment_sample,
)

TRACKED_FIELDS = [
    "display_name",
    "legal_name",
    "industry_name",
    "industry_internal_name",
    "secondary_industries",
    "secondary_industry_internal_names",
    "payment_methods_accepted",
    "detailed_activity",
    "short_description",
    "keywords",
    "website",
    "siret",
    "siren",
]


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def normalize_limit(value: str | None) -> int | None:
    if value is None:
        return None

    text = str(value).strip().lower()
    if text in {"", "none", "null", "full", "all"}:
        return None

    parsed = int(text)
    if parsed <= 0:
        raise ValueError("--limit doit être positif ou 'none'.")
    return parsed


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    return str(value).replace("\ufeff", "").strip()


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def ensure_changes_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS professional_enrichment_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mlc_id TEXT NOT NULL,
            sync_batch TEXT NOT NULL,
            professional_ref TEXT NOT NULL,
            display_name TEXT,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            detected_at TEXT NOT NULL,
            source_fetched_at TEXT,
            sync_days INTEGER,
            sync_limit INTEGER,
            applied INTEGER NOT NULL DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_professional_enrichment_changes_ref
        ON professional_enrichment_changes(professional_ref, detected_at)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_professional_enrichment_changes_batch
        ON professional_enrichment_changes(sync_batch)
    """)


def load_snapshot(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    columns = table_columns(conn, "professional_enrichment")
    selected = ["professional_ref"]

    for field in TRACKED_FIELDS + ["fetched_at", "updated_at"]:
        if field in columns:
            selected.append(field)

    query = f"""
        SELECT {", ".join(selected)}
        FROM professional_enrichment
        WHERE professional_ref IS NOT NULL
          AND TRIM(professional_ref) <> ''
    """

    rows = conn.execute(query).fetchall()
    return {
        str(row["professional_ref"]).strip(): dict(row)
        for row in rows
    }


def diff_snapshots(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    *,
    fields: list[str],
) -> list[dict[str, Any]]:
    changes = []

    for ref, after_row in sorted(after.items()):
        before_row = before.get(ref)
        if not before_row:
            continue

        for field in fields:
            if field not in after_row and field not in before_row:
                continue

            old = clean_text(before_row.get(field))
            new = clean_text(after_row.get(field))

            if old == new:
                continue

            changes.append({
                "professional_ref": ref,
                "display_name": clean_text(
                    after_row.get("display_name")
                    or before_row.get("display_name")
                    or ref
                ),
                "field_name": field,
                "old_value": old,
                "new_value": new,
                "source_fetched_at": clean_text(after_row.get("fetched_at")),
            })

    return changes


def diff_fetch_against_snapshot(
    before: dict[str, dict[str, Any]],
    fetched_rows: list[dict[str, Any]],
    *,
    fields: list[str],
) -> list[dict[str, Any]]:
    fetched_by_ref = {
        str(row.get("professional_ref") or "").strip(): row
        for row in fetched_rows
        if str(row.get("professional_ref") or "").strip()
    }

    changes = []

    for ref, fetched in sorted(fetched_by_ref.items()):
        current = before.get(ref)
        if not current:
            continue

        for field in fields:
            old = clean_text(current.get(field))
            new = clean_text(fetched.get(field))

            if old == new:
                continue

            changes.append({
                "professional_ref": ref,
                "display_name": clean_text(
                    fetched.get("display_name")
                    or current.get("display_name")
                    or ref
                ),
                "field_name": field,
                "old_value": old,
                "new_value": new,
                "source_fetched_at": clean_text(fetched.get("fetched_at")),
            })

    return changes


def insert_changes(
    conn: sqlite3.Connection,
    *,
    mlc_id: str,
    sync_batch: str,
    changes: list[dict[str, Any]],
    sync_days: int,
    sync_limit: int | None,
    applied: bool,
) -> None:
    detected_at = now_iso()

    for item in changes:
        conn.execute("""
            INSERT INTO professional_enrichment_changes (
                mlc_id,
                sync_batch,
                professional_ref,
                display_name,
                field_name,
                old_value,
                new_value,
                detected_at,
                source_fetched_at,
                sync_days,
                sync_limit,
                applied
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mlc_id,
            sync_batch,
            item["professional_ref"],
            item.get("display_name"),
            item["field_name"],
            item.get("old_value"),
            item.get("new_value"),
            detected_at,
            item.get("source_fetched_at"),
            sync_days,
            sync_limit,
            1 if applied else 0,
        ))


def summarize_changes(changes: list[dict[str, Any]]) -> dict[str, Any]:
    by_field: dict[str, int] = {}
    category_changes = []

    for item in changes:
        field = item["field_name"]
        by_field[field] = by_field.get(field, 0) + 1

        if field == "industry_name":
            category_changes.append({
                "professional_ref": item["professional_ref"],
                "name": item["display_name"],
                "before": item["old_value"],
                "after": item["new_value"],
            })

    return {
        "changed_fields": by_field,
        "category_changes_count": len(category_changes),
        "category_changes": category_changes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mlc", default="graine")
    parser.add_argument("--days", type=int, default=3650)
    parser.add_argument("--limit", default="none")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mlc_id = str(args.mlc).strip()
    sync_days = int(args.days)
    sync_limit = normalize_limit(args.limit)

    if sync_days <= 0:
        raise ValueError("--days doit être strictement positif.")

    with app.app_context():
        db = get_db_path()
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row

        ensure_changes_table(conn)
        before = load_snapshot(conn)

        sync_batch = datetime.now(UTC).strftime(
            f"professional_profile_{mlc_id}_%Y%m%d_%H%M%S"
        )

        print("DB:", db)
        print("MLC:", mlc_id)
        print("Mode:", "APPLY" if args.apply else "DRY-RUN")
        print("days:", sync_days)
        print("limit:", sync_limit)
        print("sync_batch:", sync_batch)
        print("local_rows_before:", len(before))

        if args.apply:
            result = sync_professional_profile_enrichment_sample(
                mlc_id=mlc_id,
                days=sync_days,
                limit=sync_limit,
            )

            after = load_snapshot(conn)
            changes = diff_snapshots(before, after, fields=TRACKED_FIELDS)
            insert_changes(
                conn,
                mlc_id=mlc_id,
                sync_batch=sync_batch,
                changes=changes,
                sync_days=sync_days,
                sync_limit=sync_limit,
                applied=True,
            )
            conn.commit()

            print()
            print("SYNC_RESULT")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            fetched_rows = fetch_professional_profile_enrichment_sample(
                mlc_id=mlc_id,
                days=sync_days,
                limit=sync_limit,
            )
            changes = diff_fetch_against_snapshot(
                before,
                fetched_rows,
                fields=TRACKED_FIELDS,
            )

            print()
            print("FETCH_RESULT")
            print(json.dumps({
                "fetched_rows": len(fetched_rows),
            }, ensure_ascii=False, indent=2))

        summary = summarize_changes(changes)

        print()
        print("CHANGE_SUMMARY")
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        print()
        print("CATEGORY_CHANGES")
        for item in summary["category_changes"]:
            print(json.dumps(item, ensure_ascii=False))

        print()
        print(json.dumps({
            "ok": True,
            "applied": bool(args.apply),
            "changes": len(changes),
            "category_changes": summary["category_changes_count"],
            "sync_batch": sync_batch,
        }, ensure_ascii=False, indent=2))

        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
