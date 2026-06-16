from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash


CONTROL_DB_PATH = Path(__file__).resolve().parent / "data" / "control.db"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GLOBAL_ROLES = {"admin", "user"}
MLC_ROLES = {"viewer", "editor", "manager"}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def normalize_email(email: str) -> str:
    value = str(email or "").strip().lower()
    if not _EMAIL_RE.fullmatch(value):
        raise ValueError(f"Adresse email invalide : {email!r}")
    return value


def get_control_connection() -> sqlite3.Connection:
    CONTROL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(CONTROL_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_control_db() -> None:
    conn = get_control_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS control_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            global_role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS control_user_mlc_access (
            user_id INTEGER NOT NULL,
            mlc_id TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, mlc_id),
            FOREIGN KEY (user_id) REFERENCES control_users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS control_auth_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT,
            event_type TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            details_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES control_users(id) ON DELETE SET NULL
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_control_auth_events_created
        ON control_auth_events (created_at DESC)
    """)

    conn.commit()
    conn.close()


def row_to_user(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None

    return {
        "id": int(row["id"]),
        "email": row["email"],
        "display_name": row["display_name"],
        "global_role": row["global_role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_login_at": row["last_login_at"],
    }


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    conn = get_control_connection()
    row = conn.execute(
        """
        SELECT id, email, display_name, global_role, is_active,
               created_at, updated_at, last_login_at
        FROM control_users
        WHERE id = ?
        """,
        (int(user_id),),
    ).fetchone()
    conn.close()
    return row_to_user(row)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    normalized = normalize_email(email)

    conn = get_control_connection()
    row = conn.execute(
        """
        SELECT id, email, display_name, global_role, is_active,
               created_at, updated_at, last_login_at
        FROM control_users
        WHERE email = ?
        """,
        (normalized,),
    ).fetchone()
    conn.close()
    return row_to_user(row)


def create_or_update_user(
    *,
    email: str,
    display_name: str,
    password: str,
    global_role: str = "user",
    is_active: bool = True,
) -> dict[str, Any]:
    normalized = normalize_email(email)
    role = str(global_role or "user").strip().lower()

    if role not in GLOBAL_ROLES:
        raise ValueError(f"Rôle global invalide : {global_role!r}")

    if not str(display_name or "").strip():
        raise ValueError("Le nom affiché ne peut pas être vide.")

    if len(str(password or "")) < 12:
        raise ValueError("Le mot de passe doit contenir au moins 12 caractères.")

    now = utc_now()
    password_hash = generate_password_hash(str(password), method="scrypt")

    conn = get_control_connection()
    conn.execute(
        """
        INSERT INTO control_users (
            email, display_name, password_hash, global_role,
            is_active, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            display_name = excluded.display_name,
            password_hash = excluded.password_hash,
            global_role = excluded.global_role,
            is_active = excluded.is_active,
            updated_at = excluded.updated_at
        """,
        (
            normalized,
            str(display_name).strip(),
            password_hash,
            role,
            1 if is_active else 0,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()

    user = get_user_by_email(normalized)
    if user is None:
        raise RuntimeError("Création utilisateur échouée.")

    return user


def grant_mlc_access(*, email: str, mlc_id: str, role: str) -> None:
    normalized = normalize_email(email)
    mlc_id = str(mlc_id or "").strip()
    role = str(role or "").strip().lower()

    if not mlc_id:
        raise ValueError("mlc_id vide.")

    if role not in MLC_ROLES:
        raise ValueError(f"Rôle MLC invalide : {role!r}")

    user = get_user_by_email(normalized)
    if user is None:
        raise KeyError(f"Utilisateur introuvable : {normalized}")

    conn = get_control_connection()
    conn.execute(
        """
        INSERT INTO control_user_mlc_access (user_id, mlc_id, role, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, mlc_id) DO UPDATE SET
            role = excluded.role
        """,
        (user["id"], mlc_id, role, utc_now()),
    )
    conn.commit()
    conn.close()


def list_user_mlc_access(user_id: int) -> list[dict[str, Any]]:
    conn = get_control_connection()
    rows = conn.execute(
        """
        SELECT mlc_id, role, created_at
        FROM control_user_mlc_access
        WHERE user_id = ?
        ORDER BY mlc_id
        """,
        (int(user_id),),
    ).fetchall()
    conn.close()

    return [
        {
            "mlc_id": row["mlc_id"],
            "role": row["role"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def record_auth_event(
    *,
    event_type: str,
    user_id: int | None = None,
    email: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    conn = get_control_connection()
    conn.execute(
        """
        INSERT INTO control_auth_events (
            user_id, email, event_type, ip_address,
            user_agent, details_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            email,
            event_type,
            ip_address,
            user_agent,
            json.dumps(details or {}, ensure_ascii=False),
            utc_now(),
        ),
    )
    conn.commit()
    conn.close()


def authenticate_user(
    *,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any] | None:
    normalized = normalize_email(email)

    conn = get_control_connection()
    row = conn.execute(
        """
        SELECT id, email, display_name, password_hash, global_role,
               is_active, created_at, updated_at, last_login_at
        FROM control_users
        WHERE email = ?
        """,
        (normalized,),
    ).fetchone()

    if row is None:
        conn.close()
        record_auth_event(
            event_type="login_failure_unknown_email",
            email=normalized,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return None

    if not bool(row["is_active"]):
        conn.close()
        record_auth_event(
            event_type="login_failure_inactive_user",
            user_id=int(row["id"]),
            email=normalized,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return None

    if not check_password_hash(row["password_hash"], str(password or "")):
        conn.close()
        record_auth_event(
            event_type="login_failure_bad_password",
            user_id=int(row["id"]),
            email=normalized,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return None

    now = utc_now()
    conn.execute(
        "UPDATE control_users SET last_login_at = ?, updated_at = ? WHERE id = ?",
        (now, now, int(row["id"])),
    )
    conn.commit()
    conn.close()

    user = get_user_by_id(int(row["id"]))
    record_auth_event(
        event_type="login_success",
        user_id=int(row["id"]),
        email=normalized,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return user
