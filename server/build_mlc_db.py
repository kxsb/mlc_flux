from __future__ import annotations

import argparse
import json
import os
import shlex
import sqlite3
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


DEFAULT_SECRETS_FILE = Path("/opt/mlcflux-secrets/mlcflux-multi-dev.env")


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_env_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Fichier secrets introuvable : {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        value = value.strip()

        if value:
            try:
                value = shlex.split(value, posix=True)[0]
            except Exception:
                pass

        key = key.strip()

        # En CLI multi-MLC, l'instance cible est portée par --mlc.
        # Le .env peut contenir MLCFLUX_DEFAULT_MLC_ID pour le service web,
        # mais il ne doit jamais écraser l'argument de build.
        if key == "MLCFLUX_DEFAULT_MLC_ID":
            continue

        os.environ[key] = value


def _positive_int_or_none(value: str | None) -> int | None:
    if value in (None, ""):
        return None

    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("La valeur doit être positive.")
    return parsed


def _db_counts(db_path: Path) -> dict[str, int | None]:
    tables = [
        "transactions",
        "professional_enrichment",
        "odoo_professional_enrichment",
    ]

    result: dict[str, int | None] = {}

    if not db_path.exists():
        return {table: None for table in tables}

    conn = sqlite3.connect(db_path)
    try:
        for table in tables:
            exists = conn.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = ?
                """,
                (table,),
            ).fetchone()

            if not exists:
                result[table] = None
                continue

            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            result[table] = int(count)
    finally:
        conn.close()

    return result


def _flow_summary(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        table_exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'transactions'
            """
        ).fetchone()

        if not table_exists:
            return []

        rows = conn.execute(
            """
            SELECT
              CASE
                WHEN from_label LIKE 'U_%' THEN 'U'
                WHEN from_label GLOB 'P[0-9][0-9][0-9][0-9]' THEN 'P'
                WHEN from_label LIKE 'T_%' THEN 'T'
                ELSE 'X'
              END || '→' ||
              CASE
                WHEN to_label LIKE 'U_%' THEN 'U'
                WHEN to_label GLOB 'P[0-9][0-9][0-9][0-9]' THEN 'P'
                WHEN to_label LIKE 'T_%' THEN 'T'
                ELSE 'X'
              END AS flow,
              COUNT(*) AS count,
              ROUND(SUM(amount), 2) AS volume
            FROM transactions
            GROUP BY flow
            ORDER BY count DESC, flow ASC
            """
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def _smoke_tests() -> dict[str, Any]:
    results: dict[str, Any] = {}

    try:
        from server.analytics import compute_global_stats

        stats = compute_global_stats()
        results["compute_global_stats"] = {
            "ok": True,
            "keys": list(stats.keys())[:12],
        }
    except Exception as exc:
        results["compute_global_stats"] = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    try:
        from server.analytics import compute_stats_charts

        charts = compute_stats_charts()
        results["compute_stats_charts"] = {
            "ok": True,
            "keys": list(charts.keys())[:12],
        }
    except Exception as exc:
        results["compute_stats_charts"] = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    try:
        from server.analytics import compute_professionals_ranking

        ranking = compute_professionals_ranking()
        results["compute_professionals_ranking"] = {
            "ok": True,
            "rows": len(ranking),
            "with_sector": sum(1 for row in ranking if row.get("Secteur d’activité")),
            "with_zip": sum(1 for row in ranking if row.get("Code postal")),
        }
    except Exception as exc:
        results["compute_professionals_ranking"] = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Construit / synchronise une base MLCFlux pour une instance MLC."
    )

    parser.add_argument("--mlc", required=True, help="Identifiant MLC, ex. graine ou gonette.")
    parser.add_argument("--secrets-file", default=str(DEFAULT_SECRETS_FILE))
    parser.add_argument("--days", type=_positive_int_or_none, default=7)
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to", default=None)
    parser.add_argument("--limit", type=_positive_int_or_none, default=100)
    parser.add_argument("--reset-transactions", action="store_true")
    parser.add_argument("--sync-professionals", action="store_true")
    parser.add_argument("--professional-days", type=_positive_int_or_none, default=30)
    parser.add_argument("--professional-limit", type=_positive_int_or_none, default=50)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    os.environ["MLCFLUX_DEFAULT_MLC_ID"] = args.mlc
    _load_env_file(Path(args.secrets_file))

    # --mlc prime aussi après chargement .env.
    os.environ["MLCFLUX_DEFAULT_MLC_ID"] = args.mlc

    from app import app
    from server.database import get_db_path, init_db, init_professional_enrichment_db
    from server.services.cyclos_transaction_sync import sync_cyclos_transactions
    from server.services.cyclos_professional_profile_enrichment import (
        fetch_professional_profile_enrichment_sample,
        sync_professional_profile_enrichment_sample,
    )
    from server.services.professional_ref_mapping import count_professional_mappings

    report: dict[str, Any] = {
        "kind": "mlcflux_build_mlc_db_report",
        "generated_at": _utc_now(),
        "mlc_id": args.mlc,
        "dry_run": bool(args.dry_run),
        "parameters": {
            "days": args.days,
            "date_from": args.date_from,
            "date_to": args.date_to,
            "limit": args.limit,
            "reset_transactions": args.reset_transactions,
            "sync_professionals": args.sync_professionals,
            "professional_days": args.professional_days,
            "professional_limit": args.professional_limit,
        },
    }

    with app.app_context():
        db_path = get_db_path()
        report["db_path"] = str(db_path)

        init_db()
        init_professional_enrichment_db()

        report["counts_before"] = _db_counts(db_path)

        report["transactions"] = sync_cyclos_transactions(
            mlc_id=args.mlc,
            days=args.days,
            date_from=args.date_from,
            date_to=args.date_to,
            limit=args.limit,
            reset=args.reset_transactions,
            write=not args.dry_run,
        )

        if args.sync_professionals:
            if args.dry_run:
                rows = fetch_professional_profile_enrichment_sample(
                    mlc_id=args.mlc,
                    days=args.professional_days or args.days or 30,
                    limit=args.professional_limit,
                )
                report["professional_enrichment"] = {
                    "write": False,
                    "fetched": len(rows),
                    "written": 0,
                    "with_industry": sum(1 for row in rows if row.get("industry_name")),
                    "with_zip": sum(1 for row in rows if row.get("zip")),
                    "with_geo": sum(1 for row in rows if row.get("latitude") is not None and row.get("longitude") is not None),
                }
            else:
                report["professional_enrichment"] = sync_professional_profile_enrichment_sample(
                    mlc_id=args.mlc,
                    days=args.professional_days or args.days or 30,
                    limit=args.professional_limit,
                )
        else:
            report["professional_enrichment"] = {
                "skipped": True,
            }

        report["professional_mapping_count"] = count_professional_mappings(args.mlc)
        report["counts_after"] = _db_counts(db_path)
        report["flow_summary"] = _flow_summary(db_path)

        if args.skip_smoke:
            report["smoke_tests"] = {
                "skipped": True,
            }
        else:
            report["smoke_tests"] = _smoke_tests()

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))

    has_error = bool(report.get("transactions", {}).get("error"))
    smoke_failed = any(
        isinstance(value, dict) and value.get("ok") is False
        for value in report.get("smoke_tests", {}).values()
    )

    return 1 if has_error or smoke_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
