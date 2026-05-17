from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Contrat de base actuellement attendu par MLCFlux.
# ---------------------------------------------------------------------------

EXPECTED_TABLES: tuple[str, ...] = (
    "transactions",
    "sync_state",
    "odoo_professional_enrichment",
    "odoo_professional_secondary_industries",
    "odoo_individual_enrichment",
    "odoo_monetary_indicators_yearly",
    "odoo_monetary_indicators_daily",
    "cyclos_individual_daily_balances",
    "cyclos_individual_daily_balance_windows",
    "cyclos_professional_daily_balances",
    "cyclos_professional_daily_balance_windows",
    "tickets",
    "ticket_messages",
    "ticket_events",
)

PRESERVED_APPLICATION_TABLES: tuple[str, ...] = (
    "tickets",
    "ticket_messages",
    "ticket_events",
)

REQUIRED_INDEXES: dict[str, dict[str, dict[str, Any]]] = {
    "transactions": {
        "idx_transactions_date": {
            "unique": False,
        },
        "idx_transactions_day": {
            "unique": False,
        },
        "idx_transactions_year": {
            "unique": False,
        },
        "idx_transactions_cyclos_id_unique": {
            "unique": True,
            "columns": ["cyclos_id"],
        },
    },
    "tickets": {
        "idx_tickets_visibility_status_activity": {
            "unique": False,
        },
        "idx_tickets_category": {
            "unique": False,
        },
    },
    "ticket_messages": {
        "idx_ticket_messages_ticket_visibility_created": {
            "unique": False,
        },
    },
    "ticket_events": {
        "idx_ticket_events_ticket_created": {
            "unique": False,
        },
    },
    "odoo_individual_enrichment": {
        "idx_odoo_individual_enrichment_match_status": {
            "unique": False,
        },
        "idx_odoo_individual_enrichment_zip": {
            "unique": False,
        },
        "idx_odoo_individual_enrichment_city": {
            "unique": False,
        },
    },
    "odoo_monetary_indicators_daily": {
        "idx_odoo_monetary_indicators_daily_year_month": {
            "unique": False,
        },
    },
    "cyclos_individual_daily_balances": {
        "idx_cyclos_individual_daily_balances_date": {
            "unique": False,
        },
        "idx_cyclos_individual_daily_balances_pseudonym": {
            "unique": False,
        },
    },
    "cyclos_individual_daily_balance_windows": {
        "idx_cyclos_individual_daily_balance_windows_status": {
            "unique": False,
        },
        "idx_cyclos_individual_daily_balance_windows_pseudonym": {
            "unique": False,
        },
    },
    "cyclos_professional_daily_balances": {
        "idx_cyclos_professional_daily_balances_date": {
            "unique": False,
        },
        "idx_cyclos_professional_daily_balances_ref": {
            "unique": False,
        },
    },
    "cyclos_professional_daily_balance_windows": {
        "idx_cyclos_professional_daily_balance_windows_status": {
            "unique": False,
        },
        "idx_cyclos_professional_daily_balance_windows_ref": {
            "unique": False,
        },
    },
}

# pk = rang de clé primaire dans PRAGMA table_info.
EXPECTED_COLUMN_CONTRACTS: dict[str, dict[str, dict[str, Any]]] = {
    "transactions": {
        "transaction_number": {"type": "TEXT", "pk": 1},
        "cyclos_id": {"type": "TEXT"},
        "date": {"type": "TEXT", "notnull": True},
        "group_label": {"type": "TEXT"},
        "from_label": {"type": "TEXT"},
        "to_label": {"type": "TEXT"},
        "amount": {"type": "REAL"},
        "type_label": {"type": "TEXT"},
    },
    "sync_state": {
        "sync_name": {"type": "TEXT", "pk": 1},
        "last_run_at": {"type": "TEXT"},
        "last_status": {"type": "TEXT"},
        "last_message": {"type": "TEXT"},
    },
    "odoo_professional_enrichment": {
        "professional_ref": {"type": "TEXT", "pk": 1},
        "odoo_partner_id": {"type": "INTEGER", "notnull": True},
        "odoo_name": {"type": "TEXT", "notnull": True},
        "industry_id": {"type": "INTEGER"},
        "industry_name": {"type": "TEXT"},
        "detailed_activity": {"type": "TEXT"},
        "website_description_html": {"type": "TEXT"},
        "keywords": {"type": "TEXT"},
        "naf": {"type": "TEXT"},
        "street": {"type": "TEXT"},
        "zip": {"type": "TEXT"},
        "city": {"type": "TEXT"},
        "latitude": {"type": "REAL"},
        "longitude": {"type": "REAL"},
        "date_localization": {"type": "TEXT"},
        "membership_state": {"type": "TEXT"},
        "is_former_member": {"type": "INTEGER"},
        "cyclos_address_id": {"type": "TEXT"},
        "cyclos_address_line1": {"type": "TEXT"},
        "cyclos_zip": {"type": "TEXT"},
        "cyclos_city": {"type": "TEXT"},
        "cyclos_latitude": {"type": "REAL"},
        "cyclos_longitude": {"type": "REAL"},
        "geo_distance_meters": {"type": "REAL"},
        "geo_match_status": {"type": "TEXT"},
        "fetched_at": {"type": "TEXT", "notnull": True},
    },
    "odoo_professional_secondary_industries": {
        "professional_ref": {"type": "TEXT", "pk": 1, "notnull": True},
        "industry_id": {"type": "INTEGER", "pk": 2, "notnull": True},
        "industry_name": {"type": "TEXT", "notnull": True},
    },
    "odoo_individual_enrichment": {
        "pseudonym": {"type": "TEXT", "pk": 1},
        "odoo_match_status": {"type": "TEXT", "notnull": True},
        "zip": {"type": "TEXT"},
        "city": {"type": "TEXT"},
        "latitude": {"type": "REAL"},
        "longitude": {"type": "REAL"},
        "membership_state": {"type": "TEXT"},
        "is_former_member": {"type": "INTEGER"},
        "has_zip": {"type": "INTEGER", "notnull": True, "default": "0"},
        "has_city": {"type": "INTEGER", "notnull": True, "default": "0"},
        "has_coordinates": {"type": "INTEGER", "notnull": True, "default": "0"},
        "fetched_at": {"type": "TEXT", "notnull": True},
        "source": {
            "type": "TEXT",
            "notnull": True,
            "default": "odoo_jsonrpc_via_cyclos_numadherent",
        },
    },
    "odoo_monetary_indicators_yearly": {
        "year": {"type": "INTEGER", "pk": 1},
        "gonettes_num_circulation": {"type": "REAL", "notnull": True},
        "gonettes_paper_circulation": {"type": "REAL", "notnull": True},
        "gonettes_total_circulation": {"type": "REAL", "notnull": True},
        "fonds_garantie_num": {"type": "REAL", "notnull": True},
        "fonds_garantie_paper": {"type": "REAL", "notnull": True},
        "ecart_num": {"type": "REAL", "notnull": True},
        "ecart_paper": {"type": "REAL", "notnull": True},
        "fetched_at": {"type": "TEXT", "notnull": True},
        "source": {"type": "TEXT", "notnull": True, "default": "odoo_jsonrpc"},
    },
    "odoo_monetary_indicators_daily": {
        "snapshot_date": {"type": "TEXT", "pk": 1},
        "year": {"type": "INTEGER", "notnull": True},
        "month": {"type": "INTEGER", "notnull": True},
        "day": {"type": "INTEGER", "notnull": True},
        "gonettes_num_circulation": {"type": "REAL", "notnull": True},
        "gonettes_paper_circulation": {"type": "REAL", "notnull": True},
        "gonettes_total_circulation": {"type": "REAL", "notnull": True},
        "fonds_garantie_num": {"type": "REAL", "notnull": True},
        "fonds_garantie_paper": {"type": "REAL", "notnull": True},
        "ecart_num": {"type": "REAL", "notnull": True},
        "ecart_paper": {"type": "REAL", "notnull": True},
        "fetched_at": {"type": "TEXT", "notnull": True},
        "source": {"type": "TEXT", "notnull": True, "default": "odoo_jsonrpc"},
    },
    "cyclos_individual_daily_balances": {
        "pseudonym": {"type": "TEXT", "pk": 1, "notnull": True},
        "balance_date": {"type": "TEXT", "pk": 2, "notnull": True},
        "balance": {"type": "REAL", "notnull": True},
        "fetched_at": {"type": "TEXT", "notnull": True},
        "source": {
            "type": "TEXT",
            "notnull": True,
            "default": "cyclos_balances_history_daily",
        },
    },
    "cyclos_individual_daily_balance_windows": {
        "pseudonym": {"type": "TEXT", "pk": 1, "notnull": True},
        "window_date_from": {"type": "TEXT", "pk": 2, "notnull": True},
        "window_date_to": {"type": "TEXT", "pk": 3, "notnull": True},
        "status": {"type": "TEXT", "notnull": True},
        "points_received": {"type": "INTEGER", "notnull": True, "default": "0"},
        "points_stored": {"type": "INTEGER", "notnull": True, "default": "0"},
        "attempts": {"type": "INTEGER", "notnull": True, "default": "0"},
        "last_error": {"type": "TEXT"},
        "last_run_at": {"type": "TEXT"},
        "fetched_at": {"type": "TEXT"},
    },
    "cyclos_professional_daily_balances": {
        "professional_ref": {"type": "TEXT", "pk": 1, "notnull": True},
        "balance_date": {"type": "TEXT", "pk": 2, "notnull": True},
        "balance": {"type": "REAL", "notnull": True},
        "fetched_at": {"type": "TEXT", "notnull": True},
        "source": {
            "type": "TEXT",
            "notnull": True,
            "default": "cyclos_professional_balances_history_daily",
        },
    },
    "cyclos_professional_daily_balance_windows": {
        "professional_ref": {"type": "TEXT", "pk": 1, "notnull": True},
        "window_date_from": {"type": "TEXT", "pk": 2, "notnull": True},
        "window_date_to": {"type": "TEXT", "pk": 3, "notnull": True},
        "status": {"type": "TEXT", "notnull": True},
        "points_received": {"type": "INTEGER", "notnull": True, "default": "0"},
        "points_stored": {"type": "INTEGER", "notnull": True, "default": "0"},
        "attempts": {"type": "INTEGER", "notnull": True, "default": "0"},
        "last_error": {"type": "TEXT"},
        "last_run_at": {"type": "TEXT"},
        "fetched_at": {"type": "TEXT"},
    },
    "tickets": {
        "id": {"type": "INTEGER", "pk": 1},
        "public_ref": {"type": "TEXT"},
        "slug": {"type": "TEXT"},
        "title": {"type": "TEXT", "notnull": True},
        "category": {"type": "TEXT", "notnull": True},
        "status": {"type": "TEXT", "notnull": True, "default": "new"},
        "visibility": {"type": "TEXT", "notnull": True, "default": "public"},
        "created_at": {"type": "TEXT", "notnull": True},
        "updated_at": {"type": "TEXT", "notnull": True},
        "last_activity_at": {"type": "TEXT", "notnull": True},
        "resolved_at": {"type": "TEXT"},
        "closed_at": {"type": "TEXT"},
        "author_name": {"type": "TEXT", "notnull": True},
        "author_email": {"type": "TEXT", "notnull": True},
        "source_page": {"type": "TEXT"},
        "context_json": {"type": "TEXT"},
        "official_message_id": {"type": "INTEGER"},
    },
    "ticket_messages": {
        "id": {"type": "INTEGER", "pk": 1},
        "ticket_id": {"type": "INTEGER", "notnull": True},
        "author_name": {"type": "TEXT", "notnull": True},
        "author_email": {"type": "TEXT", "notnull": True},
        "author_role": {"type": "TEXT", "notnull": True, "default": "public"},
        "body_markdown": {"type": "TEXT", "notnull": True},
        "visibility": {"type": "TEXT", "notnull": True, "default": "public"},
        "created_at": {"type": "TEXT", "notnull": True},
        "updated_at": {"type": "TEXT"},
    },
    "ticket_events": {
        "id": {"type": "INTEGER", "pk": 1},
        "ticket_id": {"type": "INTEGER", "notnull": True},
        "event_type": {"type": "TEXT", "notnull": True},
        "actor_role": {"type": "TEXT", "notnull": True},
        "old_value": {"type": "TEXT"},
        "new_value": {"type": "TEXT"},
        "created_at": {"type": "TEXT", "notnull": True},
    },
}

EXPECTED_FOREIGN_KEYS: dict[str, list[dict[str, Any]]] = {
    "ticket_messages": [
        {
            "from": "ticket_id",
            "table": "tickets",
            "to": "id",
            "on_delete": "CASCADE",
        }
    ],
    "ticket_events": [
        {
            "from": "ticket_id",
            "table": "tickets",
            "to": "id",
            "on_delete": "CASCADE",
        }
    ],
}

MONETARY_NUMERIC_FIELDS: tuple[str, ...] = (
    "gonettes_num_circulation",
    "gonettes_paper_circulation",
    "gonettes_total_circulation",
    "fonds_garantie_num",
    "fonds_garantie_paper",
    "ecart_num",
    "ecart_paper",
)


# ---------------------------------------------------------------------------
# Utilitaires généraux
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _append_issue(
    report: dict[str, Any],
    *,
    severity: str,
    code: str,
    message: str,
    details: Any = None,
) -> None:
    issue = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if details is not None:
        issue["details"] = details

    if severity == "error":
        report["errors"].append(issue)
    elif severity == "warning":
        report["warnings"].append(issue)
    elif severity == "observation":
        report["observations"].append(issue)
    else:
        raise ValueError(f"Severity d’intégrité inconnue : {severity}")


def _open_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return row[0]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return bool(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table_name,),
        )
    )


def _safe_table_count(conn: sqlite3.Connection, table_name: str) -> int | None:
    if not _table_exists(conn, table_name):
        return None
    return int(_scalar(conn, f'SELECT COUNT(*) FROM "{table_name}"') or 0)


def _sqlite_check_rows(conn: sqlite3.Connection, pragma_sql: str) -> list[str]:
    return [str(row[0]) for row in conn.execute(pragma_sql).fetchall()]


def _collect_tables(conn: sqlite3.Connection) -> list[str]:
    return [
        str(row["name"])
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    ]


def _normalize_type(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_default(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    if (
        len(normalized) >= 2
        and normalized[0] == normalized[-1]
        and normalized[0] in {"'", '"'}
    ):
        normalized = normalized[1:-1]

    return normalized


def _collect_column_catalog(
    conn: sqlite3.Connection,
    table_name: str,
) -> dict[str, dict[str, Any]]:
    if not _table_exists(conn, table_name):
        return {}

    catalog: dict[str, dict[str, Any]] = {}
    for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall():
        catalog[str(row["name"])] = {
            "type": _normalize_type(row["type"]),
            "notnull": bool(row["notnull"]),
            "default": _normalize_default(row["dflt_value"]),
            "pk": int(row["pk"] or 0),
        }

    return catalog


def _collect_index_catalog(
    conn: sqlite3.Connection,
    table_name: str,
) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}

    if not _table_exists(conn, table_name):
        return catalog

    for row in conn.execute(f'PRAGMA index_list("{table_name}")').fetchall():
        index_name = str(row["name"])
        columns = [
            info_row["name"]
            for info_row in conn.execute(f'PRAGMA index_info("{index_name}")').fetchall()
        ]

        catalog[index_name] = {
            "unique": bool(row["unique"]),
            "columns": columns,
        }

    return catalog


def _collect_foreign_key_catalog(
    conn: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    if not _table_exists(conn, table_name):
        return []

    return [
        {
            "from": str(row["from"]),
            "table": str(row["table"]),
            "to": str(row["to"]),
            "on_update": str(row["on_update"]),
            "on_delete": str(row["on_delete"]),
        }
        for row in conn.execute(f'PRAGMA foreign_key_list("{table_name}")').fetchall()
    ]


def _row_dicts(rows: list[sqlite3.Row], *, limit: int = 20) -> list[dict[str, Any]]:
    return [dict(row) for row in rows[:limit]]


def _numeric_type_invalid_count(
    conn: sqlite3.Connection,
    table: str,
    column: str,
) -> int:
    return int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM "{table}"
            WHERE "{column}" IS NULL
               OR typeof("{column}") NOT IN ('integer', 'real')
            """,
        )
        or 0
    )


def _invalid_date_only_count(
    conn: sqlite3.Connection,
    table: str,
    column: str,
) -> int:
    return int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM "{table}"
            WHERE "{column}" IS NULL
               OR TRIM("{column}") = ''
               OR DATE("{column}") IS NULL
            """,
        )
        or 0
    )


def _invalid_transaction_timestamp_sample(
    conn: sqlite3.Connection,
    *,
    limit: int = 20,
) -> tuple[int, list[str]]:
    invalid_count = 0
    sample: list[str] = []

    rows = conn.execute(
        """
        SELECT date
        FROM transactions
        WHERE date IS NOT NULL
          AND TRIM(date) <> ''
        """
    ).fetchall()

    for row in rows:
        raw_value = str(row["date"])
        try:
            datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            invalid_count += 1
            if len(sample) < limit:
                sample.append(raw_value)

    empty_count = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE date IS NULL
               OR TRIM(date) = ''
            """,
        )
        or 0
    )

    invalid_count += empty_count
    if empty_count and len(sample) < limit:
        sample.append("<NULL_OR_EMPTY_DATE>")

    return invalid_count, sample


# ---------------------------------------------------------------------------
# Intégrité SQLite et conformité de schéma
# ---------------------------------------------------------------------------

def _check_sqlite_integrity(
    conn: sqlite3.Connection,
    report: dict[str, Any],
    *,
    level: str,
) -> None:
    quick_check_rows = _sqlite_check_rows(conn, "PRAGMA quick_check")
    quick_ok = quick_check_rows == ["ok"]

    sqlite_report: dict[str, Any] = {
        "quick_check": {
            "ok": quick_ok,
            "rows": quick_check_rows,
        },
        "integrity_check": {
            "executed": level == "full",
            "ok": None,
            "rows": [],
        },
        "foreign_key_check": {
            "ok": True,
            "violations_count": 0,
            "sample": [],
        },
    }

    if not quick_ok:
        _append_issue(
            report,
            severity="error",
            code="sqlite.quick_check_failed",
            message="PRAGMA quick_check signale une anomalie SQLite.",
            details=quick_check_rows,
        )

    if level == "full":
        integrity_rows = _sqlite_check_rows(conn, "PRAGMA integrity_check")
        integrity_ok = integrity_rows == ["ok"]

        sqlite_report["integrity_check"] = {
            "executed": True,
            "ok": integrity_ok,
            "rows": integrity_rows,
        }

        if not integrity_ok:
            _append_issue(
                report,
                severity="error",
                code="sqlite.integrity_check_failed",
                message="PRAGMA integrity_check signale une anomalie SQLite.",
                details=integrity_rows,
            )

    foreign_key_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    violations_count = len(foreign_key_rows)
    fk_sample = [
        {
            "table": row[0],
            "rowid": row[1],
            "parent": row[2],
            "fkid": row[3],
        }
        for row in foreign_key_rows[:20]
    ]

    sqlite_report["foreign_key_check"] = {
        "ok": violations_count == 0,
        "violations_count": violations_count,
        "sample": fk_sample,
    }

    if violations_count:
        _append_issue(
            report,
            severity="error",
            code="sqlite.foreign_key_violations",
            message="Des violations de clés étrangères ont été détectées.",
            details={
                "count": violations_count,
                "sample": fk_sample,
            },
        )

    report["sqlite"] = sqlite_report


def _check_schema(conn: sqlite3.Connection, report: dict[str, Any]) -> None:
    existing_tables = _collect_tables(conn)
    existing_set = set(existing_tables)
    expected_set = set(EXPECTED_TABLES)

    missing_tables = sorted(expected_set - existing_set)
    unexpected_tables = sorted(existing_set - expected_set)

    report["schema"] = {
        "expected_tables": list(EXPECTED_TABLES),
        "existing_tables": existing_tables,
        "missing_tables": missing_tables,
        "unexpected_tables": unexpected_tables,
        "required_indexes": {},
        "missing_indexes": [],
        "invalid_indexes": [],
        "column_contracts": {},
        "missing_columns": [],
        "unexpected_columns": [],
        "invalid_columns": [],
        "foreign_keys": {},
        "missing_foreign_keys": [],
    }

    if missing_tables:
        _append_issue(
            report,
            severity="error",
            code="schema.missing_tables",
            message="Certaines tables MLCFlux attendues sont absentes.",
            details=missing_tables,
        )

    if unexpected_tables:
        _append_issue(
            report,
            severity="warning",
            code="schema.unexpected_tables",
            message="Des tables supplémentaires existent dans la base.",
            details=unexpected_tables,
        )

    # Index
    for table_name, expected_indexes in REQUIRED_INDEXES.items():
        catalog = _collect_index_catalog(conn, table_name)
        report["schema"]["required_indexes"][table_name] = {
            "existing": catalog,
            "expected": expected_indexes,
        }

        for index_name, requirements in expected_indexes.items():
            actual = catalog.get(index_name)
            if actual is None:
                issue = {
                    "table": table_name,
                    "index": index_name,
                }
                report["schema"]["missing_indexes"].append(issue)
                _append_issue(
                    report,
                    severity="error",
                    code="schema.missing_index",
                    message=f"Index attendu absent : {index_name}.",
                    details=issue,
                )
                continue

            expected_unique = requirements.get("unique")
            if expected_unique is not None and bool(actual["unique"]) != bool(expected_unique):
                issue = {
                    "table": table_name,
                    "index": index_name,
                    "expected_unique": bool(expected_unique),
                    "actual_unique": bool(actual["unique"]),
                }
                report["schema"]["invalid_indexes"].append(issue)
                _append_issue(
                    report,
                    severity="error",
                    code="schema.invalid_index_uniqueness",
                    message=f"Unicité invalide pour l’index {index_name}.",
                    details=issue,
                )

            expected_columns = requirements.get("columns")
            if expected_columns is not None:
                actual_columns = list(actual.get("columns") or [])
                if actual_columns != list(expected_columns):
                    issue = {
                        "table": table_name,
                        "index": index_name,
                        "expected_columns": list(expected_columns),
                        "actual_columns": actual_columns,
                    }
                    report["schema"]["invalid_indexes"].append(issue)
                    _append_issue(
                        report,
                        severity="error",
                        code="schema.invalid_index_columns",
                        message=f"Colonnes invalides pour l’index {index_name}.",
                        details=issue,
                    )

    # Colonnes
    for table_name, expected_columns in EXPECTED_COLUMN_CONTRACTS.items():
        actual_columns = _collect_column_catalog(conn, table_name)
        actual_names = set(actual_columns)
        expected_names = set(expected_columns)

        missing_columns = sorted(expected_names - actual_names)
        unexpected_columns = sorted(actual_names - expected_names)

        table_contract = {
            "expected": expected_columns,
            "actual": actual_columns,
            "missing_columns": missing_columns,
            "unexpected_columns": unexpected_columns,
            "invalid_columns": [],
        }
        report["schema"]["column_contracts"][table_name] = table_contract

        for column_name in missing_columns:
            issue = {
                "table": table_name,
                "column": column_name,
            }
            report["schema"]["missing_columns"].append(issue)
            _append_issue(
                report,
                severity="error",
                code="schema.missing_column",
                message=f"Colonne attendue absente : {table_name}.{column_name}.",
                details=issue,
            )

        for column_name in unexpected_columns:
            issue = {
                "table": table_name,
                "column": column_name,
            }
            report["schema"]["unexpected_columns"].append(issue)
            _append_issue(
                report,
                severity="warning",
                code="schema.unexpected_column",
                message=f"Colonne supplémentaire détectée : {table_name}.{column_name}.",
                details=issue,
            )

        for column_name in sorted(expected_names & actual_names):
            expected = expected_columns[column_name]
            actual = actual_columns[column_name]

            mismatches: dict[str, Any] = {}

            expected_type = expected.get("type")
            if expected_type is not None and actual["type"] != _normalize_type(expected_type):
                mismatches["type"] = {
                    "expected": _normalize_type(expected_type),
                    "actual": actual["type"],
                }

            if "notnull" in expected and bool(expected["notnull"]) != bool(actual["notnull"]):
                mismatches["notnull"] = {
                    "expected": bool(expected["notnull"]),
                    "actual": bool(actual["notnull"]),
                }

            if "pk" in expected and int(expected["pk"]) != int(actual["pk"]):
                mismatches["pk"] = {
                    "expected": int(expected["pk"]),
                    "actual": int(actual["pk"]),
                }

            if "default" in expected:
                expected_default = _normalize_default(expected["default"])
                actual_default = _normalize_default(actual["default"])
                if expected_default != actual_default:
                    mismatches["default"] = {
                        "expected": expected_default,
                        "actual": actual_default,
                    }

            if mismatches:
                issue = {
                    "table": table_name,
                    "column": column_name,
                    "mismatches": mismatches,
                }
                table_contract["invalid_columns"].append(issue)
                report["schema"]["invalid_columns"].append(issue)
                _append_issue(
                    report,
                    severity="error",
                    code="schema.invalid_column_contract",
                    message=f"Contrat invalide pour {table_name}.{column_name}.",
                    details=issue,
                )

    # Clés étrangères attendues
    for table_name, expected_fks in EXPECTED_FOREIGN_KEYS.items():
        actual_fks = _collect_foreign_key_catalog(conn, table_name)
        report["schema"]["foreign_keys"][table_name] = {
            "expected": expected_fks,
            "actual": actual_fks,
        }

        for expected_fk in expected_fks:
            found = any(
                fk["from"] == expected_fk["from"]
                and fk["table"] == expected_fk["table"]
                and fk["to"] == expected_fk["to"]
                and fk["on_delete"].upper() == str(expected_fk["on_delete"]).upper()
                for fk in actual_fks
            )

            if not found:
                issue = {
                    "table": table_name,
                    "expected_fk": expected_fk,
                    "actual_fks": actual_fks,
                }
                report["schema"]["missing_foreign_keys"].append(issue)
                _append_issue(
                    report,
                    severity="error",
                    code="schema.missing_foreign_key",
                    message=f"Clé étrangère attendue absente ou divergente sur {table_name}.",
                    details=issue,
                )


def _collect_table_counts(conn: sqlite3.Connection, report: dict[str, Any]) -> None:
    table_counts: dict[str, int | None] = {}

    for table_name in EXPECTED_TABLES:
        table_counts[table_name] = _safe_table_count(conn, table_name)

    report["table_counts"] = table_counts


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def _check_transactions(conn: sqlite3.Connection, report: dict[str, Any]) -> None:
    if not _table_exists(conn, "transactions"):
        report["transactions"] = {
            "available": False,
        }
        return

    total_count = int(_scalar(conn, "SELECT COUNT(*) FROM transactions") or 0)
    min_date = _scalar(conn, "SELECT MIN(date) FROM transactions")
    max_date = _scalar(conn, "SELECT MAX(date) FROM transactions")

    duplicate_cyclos_id_groups = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM (
                SELECT cyclos_id
                FROM transactions
                WHERE cyclos_id IS NOT NULL
                  AND TRIM(cyclos_id) <> ''
                GROUP BY cyclos_id
                HAVING COUNT(*) > 1
            )
            """,
        )
        or 0
    )

    duplicate_cyclos_id_rows = int(
        _scalar(
            conn,
            """
            SELECT COALESCE(SUM(group_size), 0)
            FROM (
                SELECT COUNT(*) AS group_size
                FROM transactions
                WHERE cyclos_id IS NOT NULL
                  AND TRIM(cyclos_id) <> ''
                GROUP BY cyclos_id
                HAVING COUNT(*) > 1
            )
            """,
        )
        or 0
    )

    null_cyclos_id_count = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE cyclos_id IS NULL
               OR TRIM(cyclos_id) = ''
            """,
        )
        or 0
    )

    null_transaction_number_count = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE transaction_number IS NULL
               OR TRIM(transaction_number) = ''
            """,
        )
        or 0
    )

    invalid_date_count, invalid_date_sample = _invalid_transaction_timestamp_sample(conn)

    invalid_amount_type_count = _numeric_type_invalid_count(conn, "transactions", "amount")
    negative_amount_count = int(
        _scalar(conn, "SELECT COUNT(*) FROM transactions WHERE amount < 0") or 0
    )
    zero_amount_count = int(
        _scalar(conn, "SELECT COUNT(*) FROM transactions WHERE amount = 0") or 0
    )

    empty_from_label_count = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE from_label IS NULL
               OR TRIM(from_label) = ''
            """,
        )
        or 0
    )

    empty_to_label_count = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE to_label IS NULL
               OR TRIM(to_label) = ''
            """,
        )
        or 0
    )

    self_transfer_count = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE from_label IS NOT NULL
              AND to_label IS NOT NULL
              AND TRIM(from_label) <> ''
              AND TRIM(to_label) <> ''
              AND from_label = to_label
            """,
        )
        or 0
    )

    legacy_masked_actor_rows = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE from_label = 'Acteur masqué'
               OR to_label = 'Acteur masqué'
            """,
        )
        or 0
    )

    legacy_u_user_rows = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE from_label LIKE 'U_user_%'
               OR to_label LIKE 'U_user_%'
            """,
        )
        or 0
    )

    legacy_u_inconnu_rows = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE from_label = 'U_inconnu'
               OR to_label = 'U_inconnu'
            """,
        )
        or 0
    )

    actor_family_rows = conn.execute(
        """
        WITH all_labels AS (
            SELECT from_label AS label FROM transactions
            UNION ALL
            SELECT to_label AS label FROM transactions
        )
        SELECT
            CASE
                WHEN label LIKE 'UD_%' THEN 'UD_*'
                WHEN label LIKE 'U_%' THEN 'U_*'
                WHEN label LIKE 'P%' THEN 'P*'
                WHEN label LIKE 'T_%' THEN 'T_*'
                WHEN label IS NULL OR TRIM(label) = '' THEN 'NULL_OR_EMPTY'
                ELSE 'OTHER'
            END AS family,
            COUNT(*) AS occurrences
        FROM all_labels
        GROUP BY family
        ORDER BY occurrences DESC, family ASC
        """
    ).fetchall()

    actor_family_counts = {
        str(row["family"]): int(row["occurrences"])
        for row in actor_family_rows
    }

    unknown_actor_label_rows = conn.execute(
        """
        WITH all_labels AS (
            SELECT from_label AS label FROM transactions
            UNION ALL
            SELECT to_label AS label FROM transactions
        )
        SELECT label, COUNT(*) AS occurrences
        FROM all_labels
        WHERE label IS NOT NULL
          AND TRIM(label) <> ''
          AND label NOT LIKE 'UD_%'
          AND label NOT LIKE 'U_%'
          AND label NOT LIKE 'P%'
          AND label NOT LIKE 'T_%'
        GROUP BY label
        ORDER BY occurrences DESC, label ASC
        LIMIT 50
        """
    ).fetchall()

    unknown_actor_label_sample = _row_dicts(unknown_actor_label_rows)
    unknown_actor_label_occurrences = sum(
        int(row["occurrences"]) for row in unknown_actor_label_rows
    )

    quasi_duplicate_groups = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    date,
                    from_label,
                    to_label,
                    amount,
                    COALESCE(group_label, '') AS group_label_norm,
                    COALESCE(type_label, '') AS type_label_norm,
                    COUNT(*) AS group_size
                FROM transactions
                GROUP BY
                    date,
                    from_label,
                    to_label,
                    amount,
                    COALESCE(group_label, ''),
                    COALESCE(type_label, '')
                HAVING COUNT(*) > 1
            )
            """,
        )
        or 0
    )

    quasi_duplicate_rows = int(
        _scalar(
            conn,
            """
            SELECT COALESCE(SUM(group_size), 0)
            FROM (
                SELECT
                    COUNT(*) AS group_size
                FROM transactions
                GROUP BY
                    date,
                    from_label,
                    to_label,
                    amount,
                    COALESCE(group_label, ''),
                    COALESCE(type_label, '')
                HAVING COUNT(*) > 1
            )
            """,
        )
        or 0
    )

    quasi_duplicate_sample_rows = conn.execute(
        """
        WITH duplicate_fingerprints AS (
            SELECT
                date,
                from_label,
                to_label,
                amount,
                COALESCE(group_label, '') AS group_label_norm,
                COALESCE(type_label, '') AS type_label_norm,
                COUNT(*) AS group_size
            FROM transactions
            GROUP BY
                date,
                from_label,
                to_label,
                amount,
                COALESCE(group_label, ''),
                COALESCE(type_label, '')
            HAVING COUNT(*) > 1
            ORDER BY group_size DESC, date DESC
            LIMIT 20
        )
        SELECT
            d.date,
            d.from_label,
            d.to_label,
            d.amount,
            d.group_label_norm AS group_label,
            d.type_label_norm AS type_label,
            d.group_size,
            GROUP_CONCAT(t.cyclos_id, ' | ') AS cyclos_ids,
            GROUP_CONCAT(COALESCE(t.transaction_number, '<NULL>'), ' | ') AS transaction_numbers
        FROM duplicate_fingerprints d
        JOIN transactions t
          ON t.date = d.date
         AND t.from_label = d.from_label
         AND t.to_label = d.to_label
         AND t.amount = d.amount
         AND COALESCE(t.group_label, '') = d.group_label_norm
         AND COALESCE(t.type_label, '') = d.type_label_norm
        GROUP BY
            d.date,
            d.from_label,
            d.to_label,
            d.amount,
            d.group_label_norm,
            d.type_label_norm,
            d.group_size
        ORDER BY d.group_size DESC, d.date DESC
        """
    ).fetchall()

    report["transactions"] = {
        "available": True,
        "count": total_count,
        "min_date": min_date,
        "max_date": max_date,
        "duplicate_cyclos_id_groups": duplicate_cyclos_id_groups,
        "duplicate_cyclos_id_rows": duplicate_cyclos_id_rows,
        "null_or_empty_cyclos_id_count": null_cyclos_id_count,
        "null_or_empty_transaction_number_count": null_transaction_number_count,
        "invalid_date_count": invalid_date_count,
        "invalid_date_sample": invalid_date_sample,
        "invalid_amount_type_count": invalid_amount_type_count,
        "negative_amount_count": negative_amount_count,
        "zero_amount_count": zero_amount_count,
        "empty_from_label_count": empty_from_label_count,
        "empty_to_label_count": empty_to_label_count,
        "self_transfer_count": self_transfer_count,
        "legacy_labels": {
            "acteur_masque_rows": legacy_masked_actor_rows,
            "u_user_rows": legacy_u_user_rows,
            "u_inconnu_rows": legacy_u_inconnu_rows,
        },
        "actor_family_occurrences": actor_family_counts,
        "unknown_actor_labels": {
            "occurrences_in_sample_limit": unknown_actor_label_occurrences,
            "sample": unknown_actor_label_sample,
        },
        "quasi_duplicates": {
            "groups": quasi_duplicate_groups,
            "rows": quasi_duplicate_rows,
            "sample": _row_dicts(quasi_duplicate_sample_rows),
        },
    }

    if total_count == 0:
        _append_issue(
            report,
            severity="warning",
            code="transactions.empty",
            message="La table transactions existe mais ne contient aucune ligne.",
        )

    if duplicate_cyclos_id_groups:
        _append_issue(
            report,
            severity="error",
            code="transactions.duplicate_cyclos_id",
            message="Des cyclos_id dupliqués existent malgré le garde-fou attendu.",
            details={
                "groups": duplicate_cyclos_id_groups,
                "rows": duplicate_cyclos_id_rows,
            },
        )

    if null_cyclos_id_count:
        _append_issue(
            report,
            severity="error",
            code="transactions.empty_cyclos_id",
            message="Certaines transactions ont un cyclos_id nul ou vide.",
            details={"rows": null_cyclos_id_count},
        )

    if invalid_date_count:
        _append_issue(
            report,
            severity="error",
            code="transactions.invalid_date",
            message="Certaines transactions ont une date absente ou non parseable.",
            details={
                "count": invalid_date_count,
                "sample": invalid_date_sample,
            },
        )

    if invalid_amount_type_count:
        _append_issue(
            report,
            severity="error",
            code="transactions.invalid_amount_type",
            message="Certaines transactions ont un montant NULL ou non numérique.",
            details={"rows": invalid_amount_type_count},
        )

    if empty_from_label_count or empty_to_label_count:
        _append_issue(
            report,
            severity="error",
            code="transactions.empty_actor_label",
            message="Certaines transactions ont un libellé source ou cible vide.",
            details={
                "empty_from_label": empty_from_label_count,
                "empty_to_label": empty_to_label_count,
            },
        )

    if negative_amount_count:
        _append_issue(
            report,
            severity="warning",
            code="transactions.negative_amount",
            message="Des montants négatifs ont été détectés dans les transactions.",
            details={"rows": negative_amount_count},
        )

    if legacy_masked_actor_rows:
        _append_issue(
            report,
            severity="warning",
            code="transactions.legacy_acteur_masque",
            message="Des libellés 'Acteur masqué' subsistent dans les transactions.",
            details={"rows": legacy_masked_actor_rows},
        )

    if legacy_u_user_rows:
        _append_issue(
            report,
            severity="warning",
            code="transactions.legacy_u_user",
            message="Des anciens pseudonymes U_user_* subsistent dans les transactions.",
            details={"rows": legacy_u_user_rows},
        )

    if legacy_u_inconnu_rows:
        _append_issue(
            report,
            severity="warning",
            code="transactions.legacy_u_inconnu",
            message="Des anciens pseudonymes U_inconnu subsistent dans les transactions.",
            details={"rows": legacy_u_inconnu_rows},
        )

    if actor_family_counts.get("OTHER"):
        _append_issue(
            report,
            severity="warning",
            code="transactions.unknown_actor_prefix",
            message="Des libellés d’acteurs ne correspondent pas aux familles U_ / UD_ / P* / T_* attendues.",
            details={
                "occurrences": actor_family_counts.get("OTHER"),
                "sample": unknown_actor_label_sample,
            },
        )

    if quasi_duplicate_groups:
        _append_issue(
            report,
            severity="observation",
            code="transactions.quasi_duplicate_fingerprints",
            message=(
                "Des groupes de transactions partagent exactement la même empreinte "
                "date/source/cible/montant/type. Ils peuvent être légitimes, mais méritent vérification."
            ),
            details={
                "groups": quasi_duplicate_groups,
                "rows": quasi_duplicate_rows,
                "sample": _row_dicts(quasi_duplicate_sample_rows),
            },
        )


# ---------------------------------------------------------------------------
# Soldes et fenêtres d'historisation
# ---------------------------------------------------------------------------

def _check_daily_balance_table(
    conn: sqlite3.Connection,
    report: dict[str, Any],
    *,
    table_name: str,
    actor_column: str,
    report_key: str,
) -> None:
    if not _table_exists(conn, table_name):
        report["balances"][report_key] = {
            "available": False,
        }
        return

    total_count = int(_scalar(conn, f'SELECT COUNT(*) FROM "{table_name}"') or 0)
    distinct_actors = int(
        _scalar(conn, f'SELECT COUNT(DISTINCT "{actor_column}") FROM "{table_name}"') or 0
    )
    min_date = _scalar(conn, f'SELECT MIN(balance_date) FROM "{table_name}"')
    max_date = _scalar(conn, f'SELECT MAX(balance_date) FROM "{table_name}"')

    empty_actor_count = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM "{table_name}"
            WHERE "{actor_column}" IS NULL
               OR TRIM("{actor_column}") = ''
            """,
        )
        or 0
    )

    invalid_date_count = _invalid_date_only_count(conn, table_name, "balance_date")
    invalid_balance_type_count = _numeric_type_invalid_count(conn, table_name, "balance")

    report["balances"][report_key] = {
        "available": True,
        "table": table_name,
        "actor_column": actor_column,
        "count": total_count,
        "distinct_actors": distinct_actors,
        "min_date": min_date,
        "max_date": max_date,
        "empty_actor_count": empty_actor_count,
        "invalid_date_count": invalid_date_count,
        "invalid_balance_type_count": invalid_balance_type_count,
    }

    if empty_actor_count:
        _append_issue(
            report,
            severity="error",
            code=f"balances.{report_key}.empty_actor",
            message=f"Des lignes de {table_name} ont un identifiant acteur vide.",
            details={"rows": empty_actor_count},
        )

    if invalid_date_count:
        _append_issue(
            report,
            severity="error",
            code=f"balances.{report_key}.invalid_date",
            message=f"Des lignes de {table_name} ont une balance_date invalide.",
            details={"rows": invalid_date_count},
        )

    if invalid_balance_type_count:
        _append_issue(
            report,
            severity="error",
            code=f"balances.{report_key}.invalid_balance_type",
            message=f"Des lignes de {table_name} ont un solde NULL ou non numérique.",
            details={"rows": invalid_balance_type_count},
        )


def _check_balance_window_table(
    conn: sqlite3.Connection,
    report: dict[str, Any],
    *,
    windows_table: str,
    balances_table: str,
    actor_column: str,
    report_key: str,
) -> None:
    if not _table_exists(conn, windows_table):
        report["balance_windows"][report_key] = {
            "available": False,
        }
        return

    total_count = int(_scalar(conn, f'SELECT COUNT(*) FROM "{windows_table}"') or 0)
    distinct_actors = int(
        _scalar(conn, f'SELECT COUNT(DISTINCT "{actor_column}") FROM "{windows_table}"') or 0
    )

    status_rows = conn.execute(
        f"""
        SELECT status, COUNT(*) AS count
        FROM "{windows_table}"
        GROUP BY status
        ORDER BY count DESC, status ASC
        """
    ).fetchall()
    status_counts = {str(row["status"]): int(row["count"]) for row in status_rows}

    empty_actor_count = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM "{windows_table}"
            WHERE "{actor_column}" IS NULL
               OR TRIM("{actor_column}") = ''
            """,
        )
        or 0
    )

    invalid_from_date_count = _invalid_date_only_count(
        conn,
        windows_table,
        "window_date_from",
    )
    invalid_to_date_count = _invalid_date_only_count(
        conn,
        windows_table,
        "window_date_to",
    )

    inverted_window_count = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM "{windows_table}"
            WHERE DATE(window_date_from) > DATE(window_date_to)
            """,
        )
        or 0
    )

    empty_status_count = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM "{windows_table}"
            WHERE status IS NULL
               OR TRIM(status) = ''
            """,
        )
        or 0
    )

    negative_counter_count = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM "{windows_table}"
            WHERE points_received < 0
               OR points_stored < 0
               OR attempts < 0
            """,
        )
        or 0
    )

    stored_gt_received_count = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM "{windows_table}"
            WHERE points_stored > points_received
            """,
        )
        or 0
    )

    date_coverage_mismatch_count = None
    date_coverage_mismatch_sample: list[dict[str, Any]] = []

    window_overlap_actor_count = None
    window_overlap_date_count = None
    window_overlap_extra_occurrences = None

    if _table_exists(conn, balances_table):
        coverage_sample_rows = conn.execute(
            f"""
            WITH RECURSIVE
            expanded_window_dates AS (
                SELECT
                    "{actor_column}" AS actor_key,
                    DATE(window_date_from) AS covered_date,
                    DATE(window_date_to) AS window_date_to
                FROM "{windows_table}"
                WHERE DATE(window_date_from) IS NOT NULL
                  AND DATE(window_date_to) IS NOT NULL
                  AND DATE(window_date_from) <= DATE(window_date_to)

                UNION ALL

                SELECT
                    actor_key,
                    DATE(covered_date, '+1 day') AS covered_date,
                    window_date_to
                FROM expanded_window_dates
                WHERE covered_date < window_date_to
            ),
            window_dates AS (
                SELECT
                    actor_key,
                    covered_date,
                    COUNT(*) AS coverage_occurrences
                FROM expanded_window_dates
                GROUP BY actor_key, covered_date
            ),
            balance_dates AS (
                SELECT
                    "{actor_column}" AS actor_key,
                    balance_date
                FROM "{balances_table}"
                GROUP BY "{actor_column}", balance_date
            ),
            mismatch_rows AS (
                SELECT
                    w.actor_key AS actor_key,
                    'covered_not_stored' AS mismatch_kind,
                    w.covered_date AS mismatch_date,
                    w.coverage_occurrences AS coverage_occurrences
                FROM window_dates w
                LEFT JOIN balance_dates b
                  ON b.actor_key = w.actor_key
                 AND b.balance_date = w.covered_date
                WHERE b.balance_date IS NULL

                UNION ALL

                SELECT
                    b.actor_key AS actor_key,
                    'stored_not_covered' AS mismatch_kind,
                    b.balance_date AS mismatch_date,
                    0 AS coverage_occurrences
                FROM balance_dates b
                LEFT JOIN window_dates w
                  ON w.actor_key = b.actor_key
                 AND w.covered_date = b.balance_date
                WHERE w.covered_date IS NULL
            ),
            mismatch_totals AS (
                SELECT
                    actor_key,
                    SUM(
                        CASE
                            WHEN mismatch_kind = 'covered_not_stored' THEN 1
                            ELSE 0
                        END
                    ) AS covered_not_stored_count,
                    SUM(
                        CASE
                            WHEN mismatch_kind = 'stored_not_covered' THEN 1
                            ELSE 0
                        END
                    ) AS stored_not_covered_count,
                    MIN(mismatch_date) AS first_mismatch_date,
                    MAX(mismatch_date) AS last_mismatch_date
                FROM mismatch_rows
                GROUP BY actor_key
            ),
            overlap_totals AS (
                SELECT
                    actor_key,
                    SUM(
                        CASE
                            WHEN coverage_occurrences > 1 THEN 1
                            ELSE 0
                        END
                    ) AS overlapping_dates_count,
                    SUM(
                        CASE
                            WHEN coverage_occurrences > 1
                            THEN coverage_occurrences - 1
                            ELSE 0
                        END
                    ) AS overlap_extra_occurrences
                FROM window_dates
                GROUP BY actor_key
            )
            SELECT
                m.actor_key,
                m.covered_not_stored_count,
                m.stored_not_covered_count,
                m.first_mismatch_date,
                m.last_mismatch_date,
                COALESCE(o.overlapping_dates_count, 0) AS overlapping_dates_count,
                COALESCE(o.overlap_extra_occurrences, 0) AS overlap_extra_occurrences
            FROM mismatch_totals m
            LEFT JOIN overlap_totals o
              ON o.actor_key = m.actor_key
            ORDER BY
                (m.covered_not_stored_count + m.stored_not_covered_count) DESC,
                m.actor_key ASC
            LIMIT 50
            """
        ).fetchall()

        date_coverage_mismatch_sample = _row_dicts(coverage_sample_rows, limit=50)

        coverage_summary = conn.execute(
            f"""
            WITH RECURSIVE
            expanded_window_dates AS (
                SELECT
                    "{actor_column}" AS actor_key,
                    DATE(window_date_from) AS covered_date,
                    DATE(window_date_to) AS window_date_to
                FROM "{windows_table}"
                WHERE DATE(window_date_from) IS NOT NULL
                  AND DATE(window_date_to) IS NOT NULL
                  AND DATE(window_date_from) <= DATE(window_date_to)

                UNION ALL

                SELECT
                    actor_key,
                    DATE(covered_date, '+1 day') AS covered_date,
                    window_date_to
                FROM expanded_window_dates
                WHERE covered_date < window_date_to
            ),
            window_dates AS (
                SELECT
                    actor_key,
                    covered_date,
                    COUNT(*) AS coverage_occurrences
                FROM expanded_window_dates
                GROUP BY actor_key, covered_date
            ),
            balance_dates AS (
                SELECT
                    "{actor_column}" AS actor_key,
                    balance_date
                FROM "{balances_table}"
                GROUP BY "{actor_column}", balance_date
            ),
            mismatch_rows AS (
                SELECT
                    w.actor_key AS actor_key
                FROM window_dates w
                LEFT JOIN balance_dates b
                  ON b.actor_key = w.actor_key
                 AND b.balance_date = w.covered_date
                WHERE b.balance_date IS NULL

                UNION ALL

                SELECT
                    b.actor_key AS actor_key
                FROM balance_dates b
                LEFT JOIN window_dates w
                  ON w.actor_key = b.actor_key
                 AND w.covered_date = b.balance_date
                WHERE w.covered_date IS NULL
            )
            SELECT
                (
                    SELECT COUNT(DISTINCT actor_key)
                    FROM mismatch_rows
                ) AS mismatching_actor_count,
                (
                    SELECT COUNT(DISTINCT actor_key)
                    FROM window_dates
                    WHERE coverage_occurrences > 1
                ) AS actors_with_overlapping_window_dates,
                (
                    SELECT COUNT(*)
                    FROM window_dates
                    WHERE coverage_occurrences > 1
                ) AS overlapping_dates_count,
                (
                    SELECT COALESCE(SUM(coverage_occurrences - 1), 0)
                    FROM window_dates
                    WHERE coverage_occurrences > 1
                ) AS overlap_extra_occurrences
            """
        ).fetchone()

        date_coverage_mismatch_count = int(
            coverage_summary["mismatching_actor_count"] or 0
        )
        window_overlap_actor_count = int(
            coverage_summary["actors_with_overlapping_window_dates"] or 0
        )
        window_overlap_date_count = int(
            coverage_summary["overlapping_dates_count"] or 0
        )
        window_overlap_extra_occurrences = int(
            coverage_summary["overlap_extra_occurrences"] or 0
        )

    report["balance_windows"][report_key] = {
        "available": True,
        "table": windows_table,
        "balances_table": balances_table,
        "actor_column": actor_column,
        "count": total_count,
        "distinct_actors": distinct_actors,
        "status_counts": status_counts,
        "empty_actor_count": empty_actor_count,
        "invalid_from_date_count": invalid_from_date_count,
        "invalid_to_date_count": invalid_to_date_count,
        "inverted_window_count": inverted_window_count,
        "empty_status_count": empty_status_count,
        "negative_counter_count": negative_counter_count,
        "stored_gt_received_count": stored_gt_received_count,
        "date_coverage_reconciliation": {
            "mismatching_actor_count": date_coverage_mismatch_count,
            "sample": date_coverage_mismatch_sample,
        },
        "window_overlap_summary": {
            "actors_with_overlapping_window_dates": window_overlap_actor_count,
            "overlapping_dates_count": window_overlap_date_count,
            "overlap_extra_occurrences": window_overlap_extra_occurrences,
        },
    }

    if empty_actor_count:
        _append_issue(
            report,
            severity="error",
            code=f"balance_windows.{report_key}.empty_actor",
            message=f"Des fenêtres de {windows_table} ont un identifiant acteur vide.",
            details={"rows": empty_actor_count},
        )

    if invalid_from_date_count or invalid_to_date_count:
        _append_issue(
            report,
            severity="error",
            code=f"balance_windows.{report_key}.invalid_date",
            message=f"Des fenêtres de {windows_table} ont une date invalide.",
            details={
                "invalid_window_date_from": invalid_from_date_count,
                "invalid_window_date_to": invalid_to_date_count,
            },
        )

    if inverted_window_count:
        _append_issue(
            report,
            severity="error",
            code=f"balance_windows.{report_key}.inverted_window",
            message=f"Des fenêtres de {windows_table} ont une borne de début postérieure à la borne de fin.",
            details={"rows": inverted_window_count},
        )

    if empty_status_count:
        _append_issue(
            report,
            severity="error",
            code=f"balance_windows.{report_key}.empty_status",
            message=f"Des fenêtres de {windows_table} ont un statut vide.",
            details={"rows": empty_status_count},
        )

    if negative_counter_count:
        _append_issue(
            report,
            severity="error",
            code=f"balance_windows.{report_key}.negative_counter",
            message=f"Des fenêtres de {windows_table} ont des compteurs négatifs.",
            details={"rows": negative_counter_count},
        )

    if stored_gt_received_count:
        _append_issue(
            report,
            severity="error",
            code=f"balance_windows.{report_key}.stored_gt_received",
            message=f"Des fenêtres de {windows_table} stockent plus de points qu’elles n’en déclarent reçus.",
            details={"rows": stored_gt_received_count},
        )

    if date_coverage_mismatch_count:
        _append_issue(
            report,
            severity="warning",
            code=f"balance_windows.{report_key}.date_coverage_reconciliation_mismatch",
            message=(
                f"Certaines dates couvertes par {windows_table} ne correspondent "
                f"pas aux dates effectivement stockées dans {balances_table}, "
                f"ou inversement."
            ),
            details={
                "mismatching_actor_count": date_coverage_mismatch_count,
                "sample": date_coverage_mismatch_sample,
            },
        )


def _check_balances_and_windows(conn: sqlite3.Connection, report: dict[str, Any]) -> None:
    report["balances"] = {}
    report["balance_windows"] = {}

    _check_daily_balance_table(
        conn,
        report,
        table_name="cyclos_individual_daily_balances",
        actor_column="pseudonym",
        report_key="individual",
    )
    _check_daily_balance_table(
        conn,
        report,
        table_name="cyclos_professional_daily_balances",
        actor_column="professional_ref",
        report_key="professional",
    )

    _check_balance_window_table(
        conn,
        report,
        windows_table="cyclos_individual_daily_balance_windows",
        balances_table="cyclos_individual_daily_balances",
        actor_column="pseudonym",
        report_key="individual",
    )
    _check_balance_window_table(
        conn,
        report,
        windows_table="cyclos_professional_daily_balance_windows",
        balances_table="cyclos_professional_daily_balances",
        actor_column="professional_ref",
        report_key="professional",
    )


# ---------------------------------------------------------------------------
# Cohérences inter-tables et contenu applicatif
# ---------------------------------------------------------------------------

def _check_professional_enrichment_consistency(
    conn: sqlite3.Connection,
    report: dict[str, Any],
) -> None:
    consistency: dict[str, Any] = {
        "available": (
            _table_exists(conn, "odoo_professional_enrichment")
            and _table_exists(conn, "odoo_professional_secondary_industries")
        ),
        "secondary_industry_orphans": {
            "count": None,
            "sample": [],
        },
    }

    if consistency["available"]:
        orphan_rows = conn.execute(
            """
            SELECT
                s.professional_ref,
                s.industry_id,
                s.industry_name
            FROM odoo_professional_secondary_industries s
            LEFT JOIN odoo_professional_enrichment p
              ON p.professional_ref = s.professional_ref
            WHERE p.professional_ref IS NULL
            ORDER BY s.professional_ref, s.industry_id
            LIMIT 50
            """
        ).fetchall()

        orphan_count = int(
            _scalar(
                conn,
                """
                SELECT COUNT(*)
                FROM odoo_professional_secondary_industries s
                LEFT JOIN odoo_professional_enrichment p
                  ON p.professional_ref = s.professional_ref
                WHERE p.professional_ref IS NULL
                """,
            )
            or 0
        )

        consistency["secondary_industry_orphans"] = {
            "count": orphan_count,
            "sample": _row_dicts(orphan_rows, limit=50),
        }

        if orphan_count:
            _append_issue(
                report,
                severity="error",
                code="intertables.secondary_industry_orphans",
                message=(
                    "Des industries secondaires Odoo pointent vers des professionnels "
                    "absents de odoo_professional_enrichment."
                ),
                details=consistency["secondary_industry_orphans"],
            )

    report["professional_enrichment_consistency"] = consistency


def _sum_consistency_rows(
    conn: sqlite3.Connection,
    *,
    table: str,
    sum_field: str,
    left_field: str,
    right_field: str,
    tolerance: float = 0.01,
) -> tuple[int, list[dict[str, Any]]]:
    rows = conn.execute(
        f"""
        SELECT
            *,
            ABS("{sum_field}" - ("{left_field}" + "{right_field}")) AS absolute_delta
        FROM "{table}"
        WHERE ABS("{sum_field}" - ("{left_field}" + "{right_field}")) > ?
        ORDER BY absolute_delta DESC
        LIMIT 50
        """,
        (tolerance,),
    ).fetchall()

    count = int(
        _scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM "{table}"
            WHERE ABS("{sum_field}" - ("{left_field}" + "{right_field}")) > ?
            """,
            (tolerance,),
        )
        or 0
    )

    return count, _row_dicts(rows, limit=50)


def _check_odoo_monetary_consistency(
    conn: sqlite3.Connection,
    report: dict[str, Any],
) -> None:
    consistency: dict[str, Any] = {
        "available": (
            _table_exists(conn, "odoo_monetary_indicators_yearly")
            and _table_exists(conn, "odoo_monetary_indicators_daily")
        ),
        "daily_total_circulation_sum_mismatch": {
            "count": None,
            "sample": [],
        },
        "yearly_total_circulation_sum_mismatch": {
            "count": None,
            "sample": [],
        },
        "yearly_vs_latest_daily": {
            "compared_years": 0,
            "missing_daily_years": [],
            "mismatches": [],
        },
    }

    if not consistency["available"]:
        report["odoo_monetary_consistency"] = consistency
        return

    daily_mismatch_count, daily_mismatch_sample = _sum_consistency_rows(
        conn,
        table="odoo_monetary_indicators_daily",
        sum_field="gonettes_total_circulation",
        left_field="gonettes_num_circulation",
        right_field="gonettes_paper_circulation",
    )
    yearly_mismatch_count, yearly_mismatch_sample = _sum_consistency_rows(
        conn,
        table="odoo_monetary_indicators_yearly",
        sum_field="gonettes_total_circulation",
        left_field="gonettes_num_circulation",
        right_field="gonettes_paper_circulation",
    )

    consistency["daily_total_circulation_sum_mismatch"] = {
        "count": daily_mismatch_count,
        "sample": daily_mismatch_sample,
    }
    consistency["yearly_total_circulation_sum_mismatch"] = {
        "count": yearly_mismatch_count,
        "sample": yearly_mismatch_sample,
    }

    if daily_mismatch_count:
        _append_issue(
            report,
            severity="warning",
            code="odoo_monetary.daily_total_sum_mismatch",
            message=(
                "Certaines lignes journalières Odoo ont une circulation totale "
                "différente de circulation numérique + circulation papier."
            ),
            details=consistency["daily_total_circulation_sum_mismatch"],
        )

    if yearly_mismatch_count:
        _append_issue(
            report,
            severity="warning",
            code="odoo_monetary.yearly_total_sum_mismatch",
            message=(
                "Certaines lignes annuelles Odoo ont une circulation totale "
                "différente de circulation numérique + circulation papier."
            ),
            details=consistency["yearly_total_circulation_sum_mismatch"],
        )

    yearly_rows = conn.execute(
        """
        SELECT *
        FROM odoo_monetary_indicators_yearly
        ORDER BY year
        """
    ).fetchall()

    yearly_daily_mismatches: list[dict[str, Any]] = []
    missing_daily_years: list[int] = []

    for yearly_row in yearly_rows:
        year = int(yearly_row["year"])
        daily_row = conn.execute(
            """
            SELECT *
            FROM odoo_monetary_indicators_daily
            WHERE year = ?
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            (year,),
        ).fetchone()

        if daily_row is None:
            missing_daily_years.append(year)
            continue

        field_deltas: dict[str, float] = {}
        for field in MONETARY_NUMERIC_FIELDS:
            yearly_value = float(yearly_row[field])
            daily_value = float(daily_row[field])
            delta = yearly_value - daily_value
            if abs(delta) > 0.01:
                field_deltas[field] = delta

        consistency["yearly_vs_latest_daily"]["compared_years"] += 1

        if field_deltas:
            yearly_daily_mismatches.append(
                {
                    "year": year,
                    "latest_daily_snapshot_date": daily_row["snapshot_date"],
                    "field_deltas_yearly_minus_daily": field_deltas,
                    "yearly_fetched_at": yearly_row["fetched_at"],
                    "daily_fetched_at": daily_row["fetched_at"],
                }
            )

    consistency["yearly_vs_latest_daily"]["missing_daily_years"] = missing_daily_years
    consistency["yearly_vs_latest_daily"]["mismatches"] = yearly_daily_mismatches

    if missing_daily_years:
        _append_issue(
            report,
            severity="warning",
            code="odoo_monetary.yearly_without_daily_snapshot",
            message=(
                "Certaines années présentes dans odoo_monetary_indicators_yearly "
                "n’ont aucun snapshot journalier correspondant."
            ),
            details={"years": missing_daily_years},
        )

    if yearly_daily_mismatches:
        _append_issue(
            report,
            severity="warning",
            code="odoo_monetary.yearly_latest_daily_drift",
            message=(
                "Certaines valeurs annuelles Odoo diffèrent du dernier snapshot journalier "
                "disponible pour la même année. Cela peut refléter un écart de fraîcheur "
                "ou un périmètre de calcul à documenter."
            ),
            details={"mismatches": yearly_daily_mismatches},
        )

    report["odoo_monetary_consistency"] = consistency


def _check_ticket_data_integrity(
    conn: sqlite3.Connection,
    report: dict[str, Any],
) -> None:
    integrity: dict[str, Any] = {
        "available": _table_exists(conn, "tickets") and _table_exists(conn, "ticket_messages"),
        "missing_public_ref_count": None,
        "missing_slug_count": None,
        "official_message_orphans": {
            "count": None,
            "sample": [],
        },
        "official_message_wrong_ticket": {
            "count": None,
            "sample": [],
        },
    }

    if not integrity["available"]:
        report["ticket_data_integrity"] = integrity
        return

    missing_public_ref_count = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM tickets
            WHERE public_ref IS NULL
               OR TRIM(public_ref) = ''
            """,
        )
        or 0
    )
    missing_slug_count = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM tickets
            WHERE slug IS NULL
               OR TRIM(slug) = ''
            """,
        )
        or 0
    )

    orphan_rows = conn.execute(
        """
        SELECT
            t.id AS ticket_id,
            t.public_ref,
            t.official_message_id
        FROM tickets t
        LEFT JOIN ticket_messages tm
          ON tm.id = t.official_message_id
        WHERE t.official_message_id IS NOT NULL
          AND tm.id IS NULL
        ORDER BY t.id
        LIMIT 50
        """
    ).fetchall()

    orphan_count = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM tickets t
            LEFT JOIN ticket_messages tm
              ON tm.id = t.official_message_id
            WHERE t.official_message_id IS NOT NULL
              AND tm.id IS NULL
            """,
        )
        or 0
    )

    wrong_ticket_rows = conn.execute(
        """
        SELECT
            t.id AS ticket_id,
            t.public_ref,
            t.official_message_id,
            tm.ticket_id AS message_ticket_id
        FROM tickets t
        JOIN ticket_messages tm
          ON tm.id = t.official_message_id
        WHERE t.official_message_id IS NOT NULL
          AND tm.ticket_id <> t.id
        ORDER BY t.id
        LIMIT 50
        """
    ).fetchall()

    wrong_ticket_count = int(
        _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM tickets t
            JOIN ticket_messages tm
              ON tm.id = t.official_message_id
            WHERE t.official_message_id IS NOT NULL
              AND tm.ticket_id <> t.id
            """,
        )
        or 0
    )

    integrity["missing_public_ref_count"] = missing_public_ref_count
    integrity["missing_slug_count"] = missing_slug_count
    integrity["official_message_orphans"] = {
        "count": orphan_count,
        "sample": _row_dicts(orphan_rows, limit=50),
    }
    integrity["official_message_wrong_ticket"] = {
        "count": wrong_ticket_count,
        "sample": _row_dicts(wrong_ticket_rows, limit=50),
    }

    if missing_public_ref_count:
        _append_issue(
            report,
            severity="warning",
            code="tickets.missing_public_ref",
            message="Certains tickets n’ont pas de référence publique.",
            details={"rows": missing_public_ref_count},
        )

    if missing_slug_count:
        _append_issue(
            report,
            severity="warning",
            code="tickets.missing_slug",
            message="Certains tickets n’ont pas de slug.",
            details={"rows": missing_slug_count},
        )

    if orphan_count:
        _append_issue(
            report,
            severity="error",
            code="tickets.official_message_orphan",
            message="Certains official_message_id pointent vers un message inexistant.",
            details=integrity["official_message_orphans"],
        )

    if wrong_ticket_count:
        _append_issue(
            report,
            severity="error",
            code="tickets.official_message_wrong_ticket",
            message="Certains official_message_id pointent vers un message rattaché à un autre ticket.",
            details=integrity["official_message_wrong_ticket"],
        )

    report["ticket_data_integrity"] = integrity


def _check_preserved_application_data(
    conn: sqlite3.Connection,
    report: dict[str, Any],
) -> None:
    tables: dict[str, dict[str, Any]] = {}

    for table_name in PRESERVED_APPLICATION_TABLES:
        exists = _table_exists(conn, table_name)
        tables[table_name] = {
            "exists": exists,
            "count": _safe_table_count(conn, table_name) if exists else None,
            "rebuild_policy": "preserve",
        }

    report["preserved_application_data"] = {
        "description": (
            "Ces tables contiennent des données applicatives ou humaines "
            "qui ne doivent pas être perdues lors d’un futur rebuild analytique."
        ),
        "tables": tables,
    }


# ---------------------------------------------------------------------------
# Finalisation et rendu
# ---------------------------------------------------------------------------

def _finalize_status(report: dict[str, Any]) -> None:
    if report["errors"]:
        report["ok"] = False
        report["status"] = "critical"
        return

    if report["warnings"]:
        report["ok"] = True
        report["status"] = "degraded"
        return

    report["ok"] = True
    report["status"] = "healthy"


def run_db_integrity_test(
    db_path: str | Path,
    *,
    level: str = "full",
) -> dict[str, Any]:
    normalized_level = str(level or "full").strip().lower()
    if normalized_level not in {"quick", "full"}:
        raise ValueError("level doit valoir 'quick' ou 'full'.")

    path = Path(db_path).expanduser().resolve()

    report: dict[str, Any] = {
        "kind": "mlcflux_db_integrity_report",
        "generated_at": _utc_now_iso(),
        "level": normalized_level,
        "ok": False,
        "status": "critical",
        "database": {
            "path": str(path),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
            "openable": False,
        },
        "sqlite": {},
        "schema": {},
        "table_counts": {},
        "transactions": {},
        "balances": {},
        "balance_windows": {},
        "professional_enrichment_consistency": {},
        "odoo_monetary_consistency": {},
        "ticket_data_integrity": {},
        "preserved_application_data": {},
        "observations": [],
        "warnings": [],
        "errors": [],
    }

    if not path.exists():
        _append_issue(
            report,
            severity="error",
            code="database.missing",
            message="Le fichier SQLite est introuvable.",
            details={"path": str(path)},
        )
        _finalize_status(report)
        return report

    try:
        conn = _open_readonly(path)
        report["database"]["openable"] = True
    except Exception as exc:
        _append_issue(
            report,
            severity="error",
            code="database.unopenable",
            message="Impossible d’ouvrir la base SQLite en lecture seule.",
            details={"error": str(exc)},
        )
        _finalize_status(report)
        return report

    try:
        _check_sqlite_integrity(conn, report, level=normalized_level)
        _check_schema(conn, report)
        _collect_table_counts(conn, report)
        _check_transactions(conn, report)
        _check_balances_and_windows(conn, report)
        _check_professional_enrichment_consistency(conn, report)
        _check_odoo_monetary_consistency(conn, report)
        _check_ticket_data_integrity(conn, report)
        _check_preserved_application_data(conn, report)
    except Exception as exc:
        _append_issue(
            report,
            severity="error",
            code="integrity.unexpected_exception",
            message="Une erreur inattendue est survenue pendant le test d’intégrité.",
            details={"error": str(exc)},
        )
    finally:
        conn.close()

    _finalize_status(report)
    return report


def integrity_report_as_json(report: dict[str, Any]) -> str:
    return json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )


def render_integrity_report_text(report: dict[str, Any]) -> str:
    database = report.get("database") or {}
    sqlite_report = report.get("sqlite") or {}
    schema = report.get("schema") or {}
    transactions = report.get("transactions") or {}
    balances = report.get("balances") or {}
    windows = report.get("balance_windows") or {}
    pro_consistency = report.get("professional_enrichment_consistency") or {}
    monetary = report.get("odoo_monetary_consistency") or {}
    tickets_integrity = report.get("ticket_data_integrity") or {}
    preserved = report.get("preserved_application_data") or {}
    table_counts = report.get("table_counts") or {}

    lines: list[str] = []

    lines.extend(
        [
            "========================================================================",
            "MLCFlux — Rapport d’intégrité approfondi de la base analytique",
            "========================================================================",
            f"Généré le       : {report.get('generated_at')}",
            f"Niveau          : {report.get('level')}",
            f"Statut          : {str(report.get('status')).upper()}",
            f"OK logique      : {report.get('ok')}",
            "",
            "------------------------------------------------------------------------",
            "1. Base SQLite",
            "------------------------------------------------------------------------",
            f"Chemin          : {database.get('path')}",
            f"Existe          : {database.get('exists')}",
            f"Ouvrable        : {database.get('openable')}",
            f"Taille          : {database.get('size_bytes')} octets",
            "",
        ]
    )

    quick = sqlite_report.get("quick_check") or {}
    integrity = sqlite_report.get("integrity_check") or {}
    fk = sqlite_report.get("foreign_key_check") or {}

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "2. Intégrité SQLite",
            "------------------------------------------------------------------------",
            f"quick_check     : {'OK' if quick.get('ok') else 'KO'}",
            f"integrity_check : "
            f"{'OK' if integrity.get('ok') else 'KO' if integrity.get('executed') else 'NON EXÉCUTÉ'}",
            f"foreign keys    : {'OK' if fk.get('ok') else 'KO'}",
            f"violations FK   : {fk.get('violations_count', '—')}",
            "",
        ]
    )

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "3. Schéma attendu",
            "------------------------------------------------------------------------",
            f"Tables attendues             : {len(schema.get('expected_tables') or [])}",
            f"Tables présentes             : {len(schema.get('existing_tables') or [])}",
            f"Tables manquantes            : {len(schema.get('missing_tables') or [])}",
            f"Tables inattendues           : {len(schema.get('unexpected_tables') or [])}",
            f"Index manquants              : {len(schema.get('missing_indexes') or [])}",
            f"Index invalides              : {len(schema.get('invalid_indexes') or [])}",
            f"Colonnes manquantes          : {len(schema.get('missing_columns') or [])}",
            f"Colonnes inattendues         : {len(schema.get('unexpected_columns') or [])}",
            f"Colonnes au contrat invalide : {len(schema.get('invalid_columns') or [])}",
            f"Clés étrangères manquantes   : {len(schema.get('missing_foreign_keys') or [])}",
            "",
        ]
    )

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "4. Volumes par table",
            "------------------------------------------------------------------------",
        ]
    )

    for table_name in EXPECTED_TABLES:
        lines.append(f"{table_name:48s} : {table_counts.get(table_name)}")

    lines.append("")

    if transactions.get("available"):
        legacy = transactions.get("legacy_labels") or {}
        families = transactions.get("actor_family_occurrences") or {}
        quasi = transactions.get("quasi_duplicates") or {}
        unknown = transactions.get("unknown_actor_labels") or {}

        lines.extend(
            [
                "------------------------------------------------------------------------",
                "5. Transactions",
                "------------------------------------------------------------------------",
                f"Nombre total                         : {transactions.get('count')}",
                f"Période min                           : {transactions.get('min_date')}",
                f"Période max                           : {transactions.get('max_date')}",
                f"Groupes cyclos_id dupliqués           : {transactions.get('duplicate_cyclos_id_groups')}",
                f"Lignes prises dans ces doublons       : {transactions.get('duplicate_cyclos_id_rows')}",
                f"cyclos_id nuls / vides                : {transactions.get('null_or_empty_cyclos_id_count')}",
                f"transaction_number nuls / vides      : {transactions.get('null_or_empty_transaction_number_count')}",
                f"Dates invalides                       : {transactions.get('invalid_date_count')}",
                f"Montants NULL / non numériques        : {transactions.get('invalid_amount_type_count')}",
                f"Montants négatifs                     : {transactions.get('negative_amount_count')}",
                f"Montants nuls                         : {transactions.get('zero_amount_count')}",
                f"from_label vides                      : {transactions.get('empty_from_label_count')}",
                f"to_label vides                        : {transactions.get('empty_to_label_count')}",
                f"Transactions source=cible             : {transactions.get('self_transfer_count')}",
                f"Groupes de quasi-doublons             : {quasi.get('groups')}",
                f"Lignes concernées quasi-doublons      : {quasi.get('rows')}",
                "",
                "Anciennes nomenclatures surveillées :",
                f"  - Acteur masqué                     : {legacy.get('acteur_masque_rows')}",
                f"  - U_user_*                          : {legacy.get('u_user_rows')}",
                f"  - U_inconnu                         : {legacy.get('u_inconnu_rows')}",
                "",
                "Occurrences de familles d’acteurs dans from_label/to_label :",
            ]
        )

        for family, occurrences in families.items():
            lines.append(f"  - {family:18s} : {occurrences}")

        lines.extend(
            [
                "",
                f"Libellés hors familles attendues — occurrences limitées par échantillon : {unknown.get('occurrences_in_sample_limit')}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "------------------------------------------------------------------------",
                "5. Transactions",
                "------------------------------------------------------------------------",
                "Table transactions indisponible.",
                "",
            ]
        )

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "6. Soldes historiques Cyclos",
            "------------------------------------------------------------------------",
        ]
    )

    for key, label in (
        ("individual", "Particuliers"),
        ("professional", "Professionnels"),
    ):
        item = balances.get(key) or {}
        lines.extend(
            [
                f"{label} :",
                f"  - disponible                       : {item.get('available')}",
                f"  - lignes                           : {item.get('count')}",
                f"  - acteurs distincts                : {item.get('distinct_actors')}",
                f"  - période                          : {item.get('min_date')} → {item.get('max_date')}",
                f"  - identifiants vides               : {item.get('empty_actor_count')}",
                f"  - dates invalides                  : {item.get('invalid_date_count')}",
                f"  - soldes NULL / non numériques     : {item.get('invalid_balance_type_count')}",
                "",
            ]
        )

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "7. Fenêtres de collecte des soldes",
            "------------------------------------------------------------------------",
        ]
    )

    for key, label in (
        ("individual", "Particuliers"),
        ("professional", "Professionnels"),
    ):
        item = windows.get(key) or {}
        coverage_reconciliation = item.get("date_coverage_reconciliation") or {}
        overlap_summary = item.get("window_overlap_summary") or {}
        lines.extend(
            [
                f"{label} :",
                f"  - disponible                              : {item.get('available')}",
                f"  - fenêtres                                : {item.get('count')}",
                f"  - acteurs distincts                       : {item.get('distinct_actors')}",
                f"  - identifiants vides                      : {item.get('empty_actor_count')}",
                f"  - dates début invalides                   : {item.get('invalid_from_date_count')}",
                f"  - dates fin invalides                     : {item.get('invalid_to_date_count')}",
                f"  - fenêtres inversées                      : {item.get('inverted_window_count')}",
                f"  - statuts vides                           : {item.get('empty_status_count')}",
                f"  - compteurs négatifs                      : {item.get('negative_counter_count')}",
                f"  - points stockés > points reçus           : {item.get('stored_gt_received_count')}",
                f"  - acteurs avec écart dates fenêtres↔soldes : {coverage_reconciliation.get('mismatching_actor_count')}",
                f"  - acteurs avec chevauchements de fenêtres  : {overlap_summary.get('actors_with_overlapping_window_dates')}",
                f"  - dates chevauchées uniques                : {overlap_summary.get('overlapping_dates_count')}",
                f"  - occurrences excédentaires d’overlap      : {overlap_summary.get('overlap_extra_occurrences')}",
                f"  - distribution des statuts                : {item.get('status_counts')}",
                "",
            ]
        )

    pro_orphans = (pro_consistency.get("secondary_industry_orphans") or {}).get("count")
    daily_sum_mismatch = (
        monetary.get("daily_total_circulation_sum_mismatch") or {}
    ).get("count")
    yearly_sum_mismatch = (
        monetary.get("yearly_total_circulation_sum_mismatch") or {}
    ).get("count")
    yearly_daily = monetary.get("yearly_vs_latest_daily") or {}

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "8. Cohérences inter-tables et indicateurs Odoo",
            "------------------------------------------------------------------------",
            f"Industries secondaires orphelines                 : {pro_orphans}",
            f"Daily Odoo — total circulation incohérent          : {daily_sum_mismatch}",
            f"Yearly Odoo — total circulation incohérent         : {yearly_sum_mismatch}",
            f"Yearly vs dernier daily — années comparées         : {yearly_daily.get('compared_years')}",
            f"Yearly vs dernier daily — années sans snapshot     : {yearly_daily.get('missing_daily_years')}",
            f"Yearly vs dernier daily — mismatches               : {len(yearly_daily.get('mismatches') or [])}",
            "",
        ]
    )

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "9. Intégrité applicative des tickets",
            "------------------------------------------------------------------------",
            f"Disponible                                      : {tickets_integrity.get('available')}",
            f"Tickets sans référence publique                 : {tickets_integrity.get('missing_public_ref_count')}",
            f"Tickets sans slug                               : {tickets_integrity.get('missing_slug_count')}",
            f"official_message_id orphelins                   : {(tickets_integrity.get('official_message_orphans') or {}).get('count')}",
            f"official_message_id vers mauvais ticket         : {(tickets_integrity.get('official_message_wrong_ticket') or {}).get('count')}",
            "",
        ]
    )

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "10. Données applicatives à préserver lors d’un futur rebuild",
            "------------------------------------------------------------------------",
            str(preserved.get("description") or ""),
        ]
    )

    preserved_tables = preserved.get("tables") or {}
    for table_name in PRESERVED_APPLICATION_TABLES:
        item = preserved_tables.get(table_name) or {}
        lines.append(
            f"{table_name:24s} : "
            f"exists={item.get('exists')} | "
            f"count={item.get('count')} | "
            f"policy={item.get('rebuild_policy')}"
        )

    lines.append("")

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "11. Observations",
            "------------------------------------------------------------------------",
        ]
    )

    observations = report.get("observations") or []
    if observations:
        for observation in observations:
            lines.append(f"- [{observation.get('code')}] {observation.get('message')}")
            if observation.get("details") is not None:
                lines.append(f"  détails : {observation.get('details')}")
    else:
        lines.append("- aucune")

    lines.append("")

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "12. Avertissements",
            "------------------------------------------------------------------------",
        ]
    )

    warnings = report.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- [{warning.get('code')}] {warning.get('message')}")
            if warning.get("details") is not None:
                lines.append(f"  détails : {warning.get('details')}")
    else:
        lines.append("- aucun")

    lines.append("")

    lines.extend(
        [
            "------------------------------------------------------------------------",
            "13. Erreurs",
            "------------------------------------------------------------------------",
        ]
    )

    errors = report.get("errors") or []
    if errors:
        for error in errors:
            lines.append(f"- [{error.get('code')}] {error.get('message')}")
            if error.get("details") is not None:
                lines.append(f"  détails : {error.get('details')}")
    else:
        lines.append("- aucune")

    lines.append("")
    lines.append("========================================================================")
    lines.append("FIN DU RAPPORT")
    lines.append("========================================================================")

    return "\n".join(lines)
