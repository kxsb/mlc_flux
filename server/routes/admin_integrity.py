from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from server.services.admin_integrity_job import (
    IntegrityJobAlreadyRunningError,
    get_integrity_job_state,
    start_integrity_job,
)
from server.utils.admin_auth import require_admin_token


admin_integrity_bp = Blueprint("admin_integrity", __name__)

APP_ROOT = Path(__file__).resolve().parents[2]
AUDITS_DIR = APP_ROOT / "_audits"

REPORT_FILENAME_RE = re.compile(
    r"^(?:DBINTEGRITY|INTEGRITY_AUDIT)[A-Za-z0-9_-]*_\d{8}_\d{6}\.json$"
)
REPORT_PREFIX_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _admin_auth_error():
    return require_admin_token()


def _safe_report_json_path(report_filename: str) -> Path | None:
    filename = str(report_filename or "").strip()

    if not REPORT_FILENAME_RE.fullmatch(filename):
        return None

    candidate = (AUDITS_DIR / filename).resolve()

    try:
        candidate.relative_to(AUDITS_DIR.resolve())
    except ValueError:
        return None

    if not candidate.is_file():
        return None

    return candidate


def _peer_txt_path(json_path: Path) -> Path:
    return json_path.with_suffix(".txt")


def _load_report_payload(json_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def _report_summary(json_path: Path) -> dict[str, Any] | None:
    payload = _load_report_payload(json_path)
    if payload is None:
        return None

    warnings = payload.get("warnings") or []
    errors = payload.get("errors") or []
    database = payload.get("database") or {}
    transactions = payload.get("transactions") or {}
    schema = payload.get("schema") or {}
    sqlite_report = payload.get("sqlite") or {}

    txt_path = _peer_txt_path(json_path)

    return {
        "filename": json_path.name,
        "text_filename": txt_path.name if txt_path.is_file() else None,
        "generated_at": payload.get("generated_at"),
        "kind": payload.get("kind"),
        "level": payload.get("level"),
        "ok": bool(payload.get("ok")),
        "status": payload.get("status") or "unknown",
        "warnings_count": len(warnings),
        "errors_count": len(errors),
        "database": {
            "exists": database.get("exists"),
            "openable": database.get("openable"),
            "size_bytes": database.get("size_bytes"),
        },
        "sqlite": {
            "quick_check_ok": (sqlite_report.get("quick_check") or {}).get("ok"),
            "integrity_check_ok": (sqlite_report.get("integrity_check") or {}).get("ok"),
            "foreign_key_check_ok": (
                sqlite_report.get("foreign_key_check") or {}
            ).get("ok"),
        },
        "schema": {
            "missing_tables_count": len(schema.get("missing_tables") or []),
            "unexpected_tables_count": len(schema.get("unexpected_tables") or []),
            "missing_indexes_count": len(schema.get("missing_indexes") or []),
            "invalid_indexes_count": len(schema.get("invalid_indexes") or []),
            "missing_columns_count": len(schema.get("missing_columns") or []),
            "invalid_columns_count": len(schema.get("invalid_columns") or []),
        },
        "transactions": {
            "count": transactions.get("count"),
            "min_date": transactions.get("min_date"),
            "max_date": transactions.get("max_date"),
            "duplicate_cyclos_id_groups": transactions.get(
                "duplicate_cyclos_id_groups"
            ),
            "legacy_labels": transactions.get("legacy_labels") or {},
        },
    }


def _list_report_summaries() -> list[dict[str, Any]]:
    if not AUDITS_DIR.exists():
        return []

    candidates = [
        *AUDITS_DIR.glob("DBINTEGRITY*.json"),
        *AUDITS_DIR.glob("INTEGRITY_AUDIT*.json"),
    ]

    summaries: list[dict[str, Any]] = []

    for json_path in candidates:
        summary = _report_summary(json_path)
        if summary is not None:
            summaries.append(summary)

    summaries.sort(
        key=lambda item: str(item.get("generated_at") or ""),
        reverse=True,
    )

    return summaries


@admin_integrity_bp.route("/api/admin/integrity/reports", methods=["GET"])
def admin_integrity_reports_index():
    auth_error = _admin_auth_error()
    if auth_error is not None:
        return auth_error

    reports = _list_report_summaries()

    return jsonify(
        {
            "reports": reports,
            "count": len(reports),
        }
    )


@admin_integrity_bp.route("/api/admin/integrity/latest", methods=["GET"])
def admin_integrity_latest_report():
    auth_error = _admin_auth_error()
    if auth_error is not None:
        return auth_error

    reports = _list_report_summaries()
    latest = reports[0] if reports else None

    return jsonify(
        {
            "available": latest is not None,
            "latest": latest,
            "reports_count": len(reports),
        }
    )


@admin_integrity_bp.route("/api/admin/integrity/job", methods=["GET"])
def admin_integrity_job_status():
    auth_error = _admin_auth_error()
    if auth_error is not None:
        return auth_error

    return jsonify(
        {
            "job": get_integrity_job_state(),
        }
    )


@admin_integrity_bp.route("/api/admin/integrity/run", methods=["POST"])
def admin_integrity_run():
    auth_error = _admin_auth_error()
    if auth_error is not None:
        return auth_error

    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}

    if not isinstance(payload, dict):
        return jsonify({"error": "Corps JSON invalide."}), 400

    level = str(payload.get("level") or "full").strip().lower()
    if level not in {"quick", "full"}:
        return jsonify({"error": "Le niveau doit valoir 'quick' ou 'full'."}), 400

    prefix = str(payload.get("prefix") or "DBINTEGRITY002").strip()
    if not REPORT_PREFIX_RE.fullmatch(prefix):
        return jsonify({
            "error": (
                "Le préfixe de rapport doit contenir uniquement "
                "des lettres, chiffres, underscores ou tirets."
            )
        }), 400

    try:
        job = start_integrity_job(level=level, prefix=prefix)
    except IntegrityJobAlreadyRunningError as exc:
        return jsonify({
            "error": str(exc),
            "job": get_integrity_job_state(),
        }), 409
    except Exception as exc:
        return jsonify({
            "error": f"Impossible de démarrer l’audit : {exc}"
        }), 500

    return jsonify(
        {
            "status": "started",
            "message": "Audit d’intégrité lancé.",
            "job": job,
        }
    ), 202


@admin_integrity_bp.route(
    "/api/admin/integrity/reports/<report_filename>",
    methods=["GET"],
)
def admin_integrity_report_detail(report_filename: str):
    auth_error = _admin_auth_error()
    if auth_error is not None:
        return auth_error

    json_path = _safe_report_json_path(report_filename)
    if json_path is None:
        return jsonify({"error": "Rapport d’intégrité introuvable."}), 404

    payload = _load_report_payload(json_path)
    if payload is None:
        return jsonify({"error": "Rapport d’intégrité illisible."}), 422

    return jsonify(
        {
            "filename": json_path.name,
            "text_available": _peer_txt_path(json_path).is_file(),
            "report": payload,
        }
    )


@admin_integrity_bp.route(
    "/api/admin/integrity/reports/<report_filename>/text",
    methods=["GET"],
)
def admin_integrity_report_text(report_filename: str):
    auth_error = _admin_auth_error()
    if auth_error is not None:
        return auth_error

    json_path = _safe_report_json_path(report_filename)
    if json_path is None:
        return jsonify({"error": "Rapport d’intégrité introuvable."}), 404

    txt_path = _peer_txt_path(json_path)
    if not txt_path.is_file():
        return jsonify({"error": "Rapport TXT introuvable."}), 404

    try:
        content = txt_path.read_text(encoding="utf-8")
    except OSError:
        return jsonify({"error": "Rapport TXT illisible."}), 422

    return Response(
        content,
        mimetype="text/plain; charset=utf-8",
    )
