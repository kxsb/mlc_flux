from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from server.database import get_connection
from server.services.cyclos_client import create_session_token, get_cyclos_config


INTERVAL_UNIT = "days"
INTERVAL_COUNT = "1"


DEFAULT_SYSTEM_ACCOUNT_ROLES = {
    "paper_guarantee": {
        "label": "T_billetCompteNantissement",
        "account_type": "billetCompteNantissement",
        "name": "Billets 6 Compte de Nantissement",
    },
    "digital_dedicated": {
        "label": "T_numeriqueCompteDedie",
        "account_type": "numeriqueCompteDedie",
        "name": "Numérique 3 Compte dédié",
    },
    "technical": {
        "label": "T_technique",
        "account_type": "technique",
        "name": "Technique",
    },
}


def _instance_dir(mlc_id: str) -> Path:
    return Path("server/data/instances") / mlc_id


def _profile_path(mlc_id: str) -> Path:
    return Path("server/data/mlc_profiles") / f"{mlc_id}.json"


def _load_profile(mlc_id: str) -> dict[str, Any]:
    path = _profile_path(mlc_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_system_accounts_from_profile(mlc_id: str) -> dict[str, dict[str, Any]]:
    profile = _load_profile(mlc_id)
    monetary = profile.get("monetary_indicators") or {}
    configured = monetary.get("technical_accounts") or {}

    accounts: dict[str, dict[str, Any]] = {}

    for role, item in configured.items():
        account_type = item.get("account_type")
        if not account_type:
            continue
        accounts[role] = {
            "label": item.get("label") or role,
            "account_type": account_type,
            "name": item.get("name") or role,
        }

    # Le profil Graine contient déjà paper_guarantee et digital_dedicated.
    # On ajoute le compte technique si absent : utile pour audit mais pas pour masse totale.
    if mlc_id == "graine":
        for role, item in DEFAULT_SYSTEM_ACCOUNT_ROLES.items():
            accounts.setdefault(role, item)

    return accounts


def ensure_system_daily_balances_table() -> None:
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cyclos_system_daily_balances (
                mlc_id TEXT NOT NULL,
                balance_date TEXT NOT NULL,
                role TEXT NOT NULL,
                label TEXT NOT NULL,
                account_type TEXT NOT NULL,
                account_name TEXT,
                account_id TEXT,
                account_number TEXT,
                balance REAL NOT NULL,
                source TEXT NOT NULL DEFAULT 'cyclos_system_balances_history_daily',
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (mlc_id, balance_date, role)
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_cyclos_system_daily_balances_date
            ON cyclos_system_daily_balances (mlc_id, balance_date)
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_cyclos_system_daily_balances_role
            ON cyclos_system_daily_balances (mlc_id, role, balance_date)
        """)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _fetch_system_balances_history(
    account_type: str,
    date_from: str,
    date_to: str,
) -> dict[str, Any]:
    cfg = get_cyclos_config()
    session_token = create_session_token()

    url = (
        cfg.base_url.rstrip("/")
        + "/system/accounts/"
        + quote(account_type, safe="")
        + "/balances-history"
    )

    response = requests.get(
        url,
        headers={
            "Session-Token": session_token,
            "Accept": "application/json",
        },
        params=[
            ("datePeriod", date_from),
            ("datePeriod", date_to),
            ("intervalUnit", INTERVAL_UNIT),
            ("intervalCount", INTERVAL_COUNT),
        ],
        timeout=60,
    )

    response.raise_for_status()
    payload = response.json()

    interval = payload.get("interval") or {}
    if interval.get("field") != "days" or str(interval.get("amount")) != "1":
        raise ValueError(f"Intervalle inattendu pour {account_type}: {interval!r}")

    return payload


def sync_cyclos_system_daily_balances(
    *,
    mlc_id: str,
    date_from: str,
    date_to: str,
) -> dict[str, Any]:
    ensure_system_daily_balances_table()

    accounts = _load_system_accounts_from_profile(mlc_id)
    if not accounts:
        return {
            "mlc_id": mlc_id,
            "date_from": date_from,
            "date_to": date_to,
            "accounts": 0,
            "points_written": 0,
            "warning": "Aucun compte système configuré dans le profil MLC.",
        }

    fetched_at = datetime.now(UTC).isoformat()
    written = 0
    account_reports = []

    conn = get_connection()
    cur = conn.cursor()

    try:
        for role, config in accounts.items():
            account_type = config["account_type"]
            payload = _fetch_system_balances_history(
                account_type=account_type,
                date_from=date_from,
                date_to=date_to,
            )

            account = payload.get("account") or {}
            account_type_payload = account.get("type") or {}
            balances = payload.get("balances") or []

            points = 0

            for point in balances:
                raw_date = point.get("date")
                raw_amount = point.get("amount")

                if not raw_date or raw_amount is None:
                    continue

                balance_date = str(raw_date)[:10]
                balance = float(Decimal(str(raw_amount)))

                cur.execute("""
                    INSERT INTO cyclos_system_daily_balances (
                        mlc_id,
                        balance_date,
                        role,
                        label,
                        account_type,
                        account_name,
                        account_id,
                        account_number,
                        balance,
                        source,
                        fetched_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(mlc_id, balance_date, role)
                    DO UPDATE SET
                        label = excluded.label,
                        account_type = excluded.account_type,
                        account_name = excluded.account_name,
                        account_id = excluded.account_id,
                        account_number = excluded.account_number,
                        balance = excluded.balance,
                        source = excluded.source,
                        fetched_at = excluded.fetched_at
                """, (
                    mlc_id,
                    balance_date,
                    role,
                    config.get("label") or role,
                    account_type_payload.get("internalName") or account_type,
                    account_type_payload.get("name") or config.get("name"),
                    account.get("id"),
                    account.get("number"),
                    balance,
                    "cyclos_system_balances_history_daily",
                    fetched_at,
                ))

                points += 1
                written += 1

            account_reports.append({
                "role": role,
                "account_type": account_type,
                "account_id": account.get("id"),
                "account_number": account.get("number"),
                "points": points,
                "current_balance": (account.get("status") or {}).get("balance"),
            })

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "mlc_id": mlc_id,
        "date_from": date_from,
        "date_to": date_to,
        "accounts": len(accounts),
        "points_written": written,
        "account_reports": account_reports,
        "fetched_at": fetched_at,
    }


def get_latest_system_monetary_snapshot(mlc_id: str) -> dict[str, Any] | None:
    ensure_system_daily_balances_table()

    conn = get_connection()
    cur = conn.cursor()

    try:
        day_row = cur.execute("""
            SELECT MAX(balance_date) AS day
            FROM cyclos_system_daily_balances
            WHERE mlc_id = ?
        """, (mlc_id,)).fetchone()

        if day_row is None or day_row["day"] is None:
            return None

        day = day_row["day"]

        rows = cur.execute("""
            SELECT role, label, account_type, account_name, balance
            FROM cyclos_system_daily_balances
            WHERE mlc_id = ?
              AND balance_date = ?
            ORDER BY role
        """, (mlc_id, day)).fetchall()

        by_role = {
            row["role"]: {
                "label": row["label"],
                "account_type": row["account_type"],
                "account_name": row["account_name"],
                "balance": float(row["balance"] or 0.0),
            }
            for row in rows
        }

        paper = by_role.get("paper_guarantee", {}).get("balance")
        digital = by_role.get("digital_dedicated", {}).get("balance")
        technical = by_role.get("technical", {}).get("balance")

        total = None
        if paper is not None and digital is not None:
            total = float(paper) + float(digital)

        return {
            "day": day,
            "paper_circulation": paper,
            "digital_circulation": digital,
            "technical_balance": technical,
            "total_monetary_mass": total,
            "accounts": by_role,
        }
    finally:
        conn.close()
