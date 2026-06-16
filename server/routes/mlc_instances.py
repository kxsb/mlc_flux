from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from flask import Blueprint, jsonify, request, session

from server.control_db import list_user_mlc_access
from server.mlc_profiles import get_mlc_profile, list_public_mlc_profiles
from server.routes.auth import current_user


mlc_instances_bp = Blueprint("mlc_instances", __name__)

ROOT_DIR = Path(__file__).resolve().parents[2]


def _instance_db_path(mlc_id: str) -> Path | None:
    candidates = [
        ROOT_DIR / "server" / "data" / "instances" / mlc_id / "mlcflux.db",
        ROOT_DIR / "server" / "data" / f"{mlc_id}.db",
        ROOT_DIR / "server" / "data" / "mlcflux.db",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(conn, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()
    return {row[1] for row in conn.execute(f"PRAGMA table_info({_quote_ident(table_name)})")}


def _pick_column(columns: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _format_public_date(value) -> str | None:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    raw = raw[:10]

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            pass

    return raw


def _number_or_none(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _smooth_series(values: list[float], radius: int = 2) -> list[float]:
    if not values:
        return []

    smoothed = []

    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        window = values[start:end]
        smoothed.append(sum(window) / len(window))

    return smoothed


def _downsample_points(points: list[dict], max_points: int = 64) -> list[dict]:
    if len(points) <= max_points:
        return points

    step = max(1, round(len(points) / max_points))
    sampled = points[::step]

    if sampled[-1] != points[-1]:
        sampled.append(points[-1])

    return sampled


def _extract_money_value_from_payload(payload):
    keywords = ("masse", "circulation", "numérique", "numerique", "monétaire", "monetaire")
    value_keys = ("value", "amount", "montant", "total", "balance", "current_value")

    def walk(node):
        if isinstance(node, dict):
            label = " ".join(
                str(node.get(key, ""))
                for key in ("label", "name", "title", "key", "metric", "description")
            ).lower()

            if any(keyword in label for keyword in keywords):
                for key in value_keys:
                    value = _number_or_none(node.get(key))
                    if value is not None:
                        return value

            for key in ("latest", "items", "metrics", "data", "series"):
                if key in node:
                    found = walk(node[key])
                    if found is not None:
                        return found

            for value in node.values():
                found = walk(value)
                if found is not None:
                    return found

        elif isinstance(node, list):
            for item in node:
                found = walk(item)
                if found is not None:
                    return found

        return None

    return walk(payload)


def _adaptive_circulating_money(mlc_id: str):
    # MONEY002_SELECTOR_MONEY_SOURCE
    # Source explicite pour les cartes publiques :
    # - Odoo daily si disponible : masse totale comptable, numérique + papier.
    # - pilotage_holdings_daily_cache sinon : masse numérique suivie.
    # - cyclos_system_daily_balances en fallback : compte dédié numérique.
    db_path = _instance_db_path(mlc_id)

    empty = {
        "value": None,
        "label": "Masse monétaire en circulation",
        "source": None,
        "snapshot_date": None,
        "quality": "missing",
    }

    if db_path is None:
        return empty

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row

            # 1) Source comptable Odoo : masse totale numérique + papier.
            if _table_exists(conn, "odoo_monetary_indicators_daily"):
                columns = _table_columns(conn, "odoo_monetary_indicators_daily")
                if {"snapshot_date", "gonettes_total_circulation"} <= columns:
                    row = conn.execute(
                        """
                        SELECT
                            snapshot_date,
                            gonettes_num_circulation,
                            gonettes_paper_circulation,
                            gonettes_total_circulation
                        FROM odoo_monetary_indicators_daily
                        WHERE gonettes_total_circulation IS NOT NULL
                        ORDER BY snapshot_date DESC
                        LIMIT 1
                        """
                    ).fetchone()

                    if row is not None:
                        return {
                            "value": float(row["gonettes_total_circulation"]),
                            "numeric_value": float(row["gonettes_num_circulation"] or 0),
                            "paper_value": float(row["gonettes_paper_circulation"] or 0),
                            "label": "Masse totale comptable",
                            "source": "odoo_monetary_indicators_daily",
                            "snapshot_date": row["snapshot_date"],
                            "quality": "accounting_total",
                        }

            # 2) Fallback annuel Odoo si le daily n’est pas présent.
            if _table_exists(conn, "odoo_monetary_indicators_yearly"):
                columns = _table_columns(conn, "odoo_monetary_indicators_yearly")
                if {"year", "gonettes_total_circulation"} <= columns:
                    row = conn.execute(
                        """
                        SELECT
                            year,
                            gonettes_num_circulation,
                            gonettes_paper_circulation,
                            gonettes_total_circulation
                        FROM odoo_monetary_indicators_yearly
                        WHERE gonettes_total_circulation IS NOT NULL
                        ORDER BY year DESC
                        LIMIT 1
                        """
                    ).fetchone()

                    if row is not None:
                        return {
                            "value": float(row["gonettes_total_circulation"]),
                            "numeric_value": float(row["gonettes_num_circulation"] or 0),
                            "paper_value": float(row["gonettes_paper_circulation"] or 0),
                            "label": "Masse totale comptable",
                            "source": "odoo_monetary_indicators_yearly",
                            "snapshot_date": str(row["year"]),
                            "quality": "accounting_total_yearly",
                        }

            # 3) Source multi-MLC : masse numérique suivie.
            if _table_exists(conn, "pilotage_holdings_daily_cache"):
                columns = _table_columns(conn, "pilotage_holdings_daily_cache")
                if {"day", "numeric_mass"} <= columns:
                    row = conn.execute(
                        """
                        SELECT day, numeric_mass
                        FROM pilotage_holdings_daily_cache
                        WHERE numeric_mass IS NOT NULL
                        ORDER BY day DESC
                        LIMIT 1
                        """
                    ).fetchone()

                    if row is not None:
                        return {
                            "value": float(row["numeric_mass"]),
                            "numeric_value": float(row["numeric_mass"]),
                            "paper_value": None,
                            "label": "Masse numérique suivie",
                            "source": "pilotage_holdings_daily_cache",
                            "snapshot_date": row["day"],
                            "quality": "numeric_mass",
                        }

            # 4) Fallback technique Cyclos : compte dédié numérique.
            if _table_exists(conn, "cyclos_system_daily_balances"):
                columns = _table_columns(conn, "cyclos_system_daily_balances")
                if {"balance_date", "role", "balance"} <= columns:
                    row = conn.execute(
                        """
                        SELECT balance_date, balance
                        FROM cyclos_system_daily_balances
                        WHERE role = 'digital_dedicated'
                          AND balance IS NOT NULL
                        ORDER BY balance_date DESC
                        LIMIT 1
                        """
                    ).fetchone()

                    if row is not None:
                        return {
                            "value": float(row["balance"]),
                            "numeric_value": float(row["balance"]),
                            "paper_value": None,
                            "label": "Masse numérique dédiée",
                            "source": "cyclos_system_daily_balances",
                            "snapshot_date": row["balance_date"],
                            "quality": "technical_balance",
                        }

    except Exception as exc:
        result = dict(empty)
        result["error"] = str(exc)
        return result

    return empty


@lru_cache(maxsize=32)
def _public_instance_summary_cached(mlc_id: str, db_mtime_ns: int):
    summary = {
        "available": False,
        "period_start": None,
        "period_end": None,
        "period_label": "Non disponible",
        "circulating_money": None,
        "active_professionals": None,
        "active_individuals": None,
        "active_total": None,
        "transaction_volume_trend": [],
        "transaction_count": None,
    }

    db_path = _instance_db_path(mlc_id)

    money_snapshot = _adaptive_circulating_money(mlc_id)
    summary["circulating_money"] = money_snapshot.get("value")
    summary["circulating_money_label"] = money_snapshot.get("label")
    summary["circulating_money_source"] = money_snapshot.get("source")
    summary["circulating_money_snapshot_date"] = money_snapshot.get("snapshot_date")
    summary["circulating_money_quality"] = money_snapshot.get("quality")
    summary["circulating_money_numeric_value"] = money_snapshot.get("numeric_value")
    summary["circulating_money_paper_value"] = money_snapshot.get("paper_value")

    if db_path is None:
        return summary

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row

            table = "transactions"
            columns = _table_columns(conn, table)

            if not columns:
                return summary

            date_col = _pick_column(columns, [
                "date",
                "created_at",
                "created",
                "transaction_date",
                "timestamp",
                "datetime",
            ])
            amount_col = _pick_column(columns, [
                "amount",
                "montant",
                "value",
                "volume",
                "total_amount",
            ])
            from_col = _pick_column(columns, [
                "from_label",
                "source_label",
                "from_name",
                "from_actor",
            ])
            to_col = _pick_column(columns, [
                "to_label",
                "target_label",
                "to_name",
                "to_actor",
            ])

            q_table = _quote_ident(table)

            if date_col:
                q_date = _quote_ident(date_col)
                row = conn.execute(
                    f"SELECT MIN({q_date}) AS start_date, MAX({q_date}) AS end_date, COUNT(*) AS tx_count FROM {q_table}"
                ).fetchone()

                start_label = _format_public_date(row["start_date"])
                end_label = _format_public_date(row["end_date"])

                summary["period_start"] = start_label
                summary["period_end"] = end_label
                summary["transaction_count"] = int(row["tx_count"] or 0)

                if start_label and end_label:
                    summary["period_label"] = f"{start_label} au {end_label}"

            if from_col and to_col:
                q_from = _quote_ident(from_col)
                q_to = _quote_ident(to_col)
                pros = set()
                individuals = set()

                for row in conn.execute(f"SELECT {q_from} AS src, {q_to} AS dst FROM {q_table}"):
                    for label in (row["src"], row["dst"]):
                        if not label:
                            continue

                        label = str(label)

                        if label in {"P0000", "P9999"}:
                            continue

                        if re.match(r"^P[0-9]+", label):
                            pros.add(label)
                        elif label.startswith("U_") or label.startswith("UD_"):
                            individuals.add(label)

                summary["active_professionals"] = len(pros)
                summary["active_individuals"] = len(individuals)
                summary["active_total"] = len(pros) + len(individuals)

            if date_col and from_col and to_col:
                q_date = _quote_ident(date_col)
                q_from = _quote_ident(from_col)
                q_to = _quote_ident(to_col)

                # AUTH_FLOW010_USAGE_FREQUENCY
                # Fréquence d'utilisation :
                # nombre de paiements par semaine sur le périmètre
                # U>P + P>P + P>U.
                weekly_rows = conn.execute(
                    f"SELECT substr({q_date}, 1, 10) AS day, {q_from} AS src, {q_to} AS dst "
                    f"FROM {q_table} "
                    f"WHERE {q_date} IS NOT NULL "
                    f"ORDER BY day"
                ).fetchall()

                weekly_counts = {}

                for row in weekly_rows:
                    day = row["day"]
                    src = row["src"]
                    dst = row["dst"]

                    if not day:
                        continue

                    if not _is_usage_frequency_payment(src, dst):
                        continue

                    day_str = str(day)[:10]
                    try:
                        dt = datetime.strptime(day_str, "%Y-%m-%d")
                    except ValueError:
                        try:
                            dt = datetime.strptime(day_str.replace("/", "-"), "%Y-%m-%d")
                        except ValueError:
                            continue

                    iso_year, iso_week, _ = dt.isocalendar()
                    week_key = f"{iso_year}-W{iso_week:02d}"
                    weekly_counts[week_key] = weekly_counts.get(week_key, 0) + 1

                raw_points = [
                    {"period": week_key, "value": float(weekly_counts[week_key])}
                    for week_key in sorted(weekly_counts)
                ]

                values = [point["value"] for point in raw_points]
                smoothed = _smooth_series(values, radius=1)

                points = []
                for point, value in zip(raw_points, smoothed):
                    points.append({
                        "period": point["period"],
                        "value": round(value, 2),
                    })

                summary["usage_frequency_trend"] = _downsample_points(points, max_points=96)
                summary["usage_frequency_label"] = "Fréquence d'utilisation"
                summary["usage_frequency_method"] = "weekly_payment_counts_UP_PP_PU_smoothed"
                summary["usage_frequency_unit"] = "paiements/semaine"
                summary["usage_frequency_max"] = max(values) if values else 0

            summary["available"] = True
            return summary

    except Exception as exc:
        summary["error"] = str(exc)
        return summary




def _actor_family(label: str | None) -> str | None:
    if not label:
        return None

    label = str(label).strip()

    if not label:
        return None

    if label in {"P0000", "P9999"}:
        return "operator"

    if label.startswith("U_") or label.startswith("UD_"):
        return "U"

    if re.match(r"^P[0-9]+", label):
        return "P"

    return None


def _is_usage_frequency_payment(from_label: str | None, to_label: str | None) -> bool:
    src = _actor_family(from_label)
    dst = _actor_family(to_label)

    if src == "operator" or dst == "operator":
        return False

    allowed = {
        ("U", "P"),
        ("P", "P"),
        ("P", "U"),
    }
    return (src, dst) in allowed


def _public_instance_summary(profile: dict):
    mlc_id = str(profile.get("id") or "").strip()
    if not mlc_id:
        return {
            "available": False,
            "period_label": "Non disponible",
            "usage_frequency_trend": [],
            "usage_frequency_max": 0,
        }

    db_path = _instance_db_path(mlc_id)
    db_mtime_ns = db_path.stat().st_mtime_ns if db_path and db_path.exists() else 0
    return _public_instance_summary_cached(mlc_id, db_mtime_ns)


def _visible_profiles_for_user(user):
    profiles = list_public_mlc_profiles()

    if user is None:
        visible_profiles = []
        for profile in profiles:
            item = dict(profile)
            item["access_role"] = None
            item["requires_login"] = True
            item["can_access"] = False
            item["locked"] = False
            item["public_summary"] = _public_instance_summary(item)
            visible_profiles.append(item)
        return visible_profiles

    access_items = list_user_mlc_access(user["id"])
    access_by_mlc = {
        item["mlc_id"]: item["role"]
        for item in access_items
    }

    is_admin = user.get("global_role") == "admin"
    visible_profiles = []

    for profile in profiles:
        role = access_by_mlc.get(profile["id"])
        can_access = bool(is_admin or role)

        item = dict(profile)
        item["access_role"] = role or ("admin" if is_admin else None)
        item["requires_login"] = False
        item["can_access"] = can_access
        item["locked"] = not can_access
        item["public_summary"] = _public_instance_summary(item)
        visible_profiles.append(item)

    return visible_profiles


def _user_can_access_mlc(user, mlc_id: str) -> tuple[bool, str | None]:
    if user.get("global_role") == "admin":
        try:
            get_mlc_profile(mlc_id)
        except KeyError:
            return False, None

        access_by_mlc = {
            item["mlc_id"]: item["role"]
            for item in list_user_mlc_access(user["id"])
        }
        return True, access_by_mlc.get(mlc_id, "admin")

    for item in list_user_mlc_access(user["id"]):
        if item["mlc_id"] == mlc_id:
            return True, item["role"]

    return False, None


@mlc_instances_bp.route("/api/mlc-instances", methods=["GET"])
def mlc_instances():
    user = current_user()
    instances = _visible_profiles_for_user(user)

    usage_frequency_scale_max = 0
    for item in instances:
        summary = item.get("public_summary") or {}
        scale_value = summary.get("usage_frequency_max") or 0
        if scale_value > usage_frequency_scale_max:
            usage_frequency_scale_max = scale_value

    return jsonify({
        "authenticated": user is not None,
        "user": None if user is None else {
            "email": user.get("email"),
            "display_name": user.get("display_name"),
            "global_role": user.get("global_role"),
        },
        "instances": instances,
        "usage_frequency_scale_max": usage_frequency_scale_max,
        "active_mlc_id": session.get("active_mlc_id"),
        "active_mlc_role": session.get("active_mlc_role"),
        "pending_mlc_id": session.get("pending_mlc_id"),
    })


@mlc_instances_bp.route("/api/current-mlc", methods=["GET"])
def current_mlc():
    user = current_user()

    if user is None:
        pending_mlc_id = session.get("pending_mlc_id") or session.get("active_mlc_id")
        pending_profile = None

        if pending_mlc_id:
            try:
                pending_profile = get_mlc_profile(pending_mlc_id).public_dict()
                pending_profile["requires_login"] = True
            except KeyError:
                session.pop("pending_mlc_id", None)
                session.pop("active_mlc_id", None)

        return jsonify({
            "authenticated": False,
            "active_mlc": pending_profile,
            "pending_mlc_id": session.get("pending_mlc_id"),
        })

    active_mlc_id = session.get("active_mlc_id")
    active_mlc_role = session.get("active_mlc_role")

    if not active_mlc_id:
        return jsonify({
            "authenticated": True,
            "active_mlc": None,
        })

    allowed, role = _user_can_access_mlc(user, active_mlc_id)
    if not allowed:
        session.pop("active_mlc_id", None)
        session.pop("active_mlc_role", None)
        return jsonify({
            "authenticated": True,
            "active_mlc": None,
        })

    profile = get_mlc_profile(active_mlc_id).public_dict()
    profile["access_role"] = active_mlc_role or role
    profile["requires_login"] = False

    return jsonify({
        "authenticated": True,
        "active_mlc": profile,
    })


@mlc_instances_bp.route("/api/select-mlc", methods=["POST"])
def select_mlc():
    user = current_user()

    payload = request.get_json(silent=True) or {}
    mlc_id = str(payload.get("mlc_id") or "").strip()

    if not mlc_id:
        return jsonify({
            "error": "mlc_id manquant.",
        }), 400

    try:
        profile = get_mlc_profile(mlc_id).public_dict()
    except KeyError:
        return jsonify({
            "error": "Monnaie locale inconnue.",
        }), 404

    if user is None:
        session["pending_mlc_id"] = mlc_id

        return jsonify({
            "ok": True,
            "authenticated": False,
            "requires_login": True,
            "login_url": "/login?next=/app",
            "active_mlc": profile,
        })

    allowed, role = _user_can_access_mlc(user, mlc_id)
    if not allowed:
        return jsonify({
            "error": "Accès refusé à cette monnaie locale.",
        }), 403

    profile["access_role"] = role
    profile["requires_login"] = False

    session["active_mlc_id"] = mlc_id
    session["active_mlc_role"] = role
    session.pop("pending_mlc_id", None)

    return jsonify({
        "ok": True,
        "authenticated": True,
        "active_mlc": profile,
    })
