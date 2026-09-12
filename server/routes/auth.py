from __future__ import annotations
import hmac
from pathlib import Path
import sqlite3

from urllib.parse import urlparse

import server.control_db as control_db
from werkzeug.security import check_password_hash, generate_password_hash
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from server.control_db import (
    authenticate_user,
    get_user_by_id,
    list_user_mlc_access,
    record_auth_event,
)


auth_bp = Blueprint("auth", __name__)


def _safe_next_url(value: str | None) -> str:
    if not value:
        return "/"

    parsed = urlparse(value)

    if parsed.scheme or parsed.netloc:
        return "/"

    if not value.startswith("/"):
        return "/"

    if value.startswith("//"):
        return "/"

    return value



# AUTH_FLOW022_AUTH_AND_RIGHTS_FIX

def _auth_control_db_path() -> Path:
    root = Path(__file__).resolve().parents[2]

    preferred_names = [
        "CONTROL_DB_PATH",
        "AUTH_DB_PATH",
        "USERS_DB_PATH",
        "CONTROL_DATABASE_PATH",
        "DATABASE_PATH",
        "DB_PATH",
    ]

    candidates = []

    for name in preferred_names:
        if hasattr(control_db, name):
            value = getattr(control_db, name)
            if isinstance(value, (str, Path)):
                candidates.append(Path(value))

    for name in dir(control_db):
        upper = name.upper()
        if "DB" not in upper and "PATH" not in upper:
            continue

        value = getattr(control_db, name)
        if isinstance(value, (str, Path)):
            candidates.append(Path(value))

    candidates.extend([
        root / "server/data/control.db",
        root / "server/data/mlcflux_control.db",
        root / "server/data/users.db",
        root / "server/control.db",
    ])

    seen = set()

    for path in candidates:
        try:
            path = path.expanduser()
            if not path.is_absolute():
                path = root / path
            path = path.resolve()
        except Exception:
            continue

        if path in seen:
            continue

        seen.add(path)

        if path.is_file():
            return path

    raise RuntimeError("Base de contrôle introuvable.")


def _auth_quote_ident(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _auth_tables(conn) -> list[str]:
    return [
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    ]


def _auth_columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({_auth_quote_ident(table)})")}


def _auth_pick_column(columns: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _auth_users_schema(conn):
    excluded_tables = {
        "account_registration_requests",
        "account_registration_request_access",
        "control_user_mlc_access",
        "user_mlc_access",
        "mlc_user_access",
        "user_instance_access",
    }

    preferred_user_tables = [
        "control_users",
        "users",
        "auth_users",
        "app_users",
    ]

    table_names = _auth_tables(conn)
    users_table = None

    for candidate in preferred_user_tables:
        for table in table_names:
            if table.lower() != candidate.lower():
                continue
            if table in excluded_tables:
                continue
            cols = _auth_columns(conn, table)
            if {"id", "email"} <= cols:
                users_table = table
                break
        if users_table:
            break

    if not users_table:
        scored = []
        for table in table_names:
            if table in excluded_tables:
                continue

            cols = _auth_columns(conn, table)

            if not {"id", "email"} <= cols:
                continue

            score = 0
            lname = table.lower()

            if "user" in lname:
                score += 10
            if "control" in lname:
                score += 5
            if {"password_hash", "hashed_password", "password"} & cols:
                score += 8
            if {"global_role", "role", "admin_role"} & cols:
                score += 4
            if {"is_active", "active", "enabled"} & cols:
                score += 2
            if "request" in lname or "registration" in lname:
                score -= 100

            scored.append((score, table))

        if scored:
            scored.sort(reverse=True)
            users_table = scored[0][1]

    if not users_table:
        raise RuntimeError("Table utilisateurs réelle introuvable.")

    cols = _auth_columns(conn, users_table)

    return {
        "users_table": users_table,
        "cols": cols,
        "display_col": _auth_pick_column(cols, ["display_name", "name", "username", "full_name"]),
        "password_col": _auth_pick_column(cols, ["password_hash", "hashed_password", "password"]),
        "role_col": _auth_pick_column(cols, ["global_role", "role", "admin_role"]),
        "active_col": _auth_pick_column(cols, ["is_active", "active", "enabled"]),
    }


def _auth_verify_password(stored_password, raw_password: str) -> bool:
    if stored_password is None:
        return False

    stored = str(stored_password)
    raw = str(raw_password or "")

    if not stored:
        return False

    # Formats Werkzeug : pbkdf2:..., scrypt:..., etc.
    try:
        if check_password_hash(stored, raw):
            return True
    except Exception:
        pass

    # Fallback ancien format éventuel en clair, seulement pour compatibilité dev.
    # À supprimer plus tard si toute la base est migrée en hash.
    try:
        return hmac.compare_digest(stored, raw)
    except Exception:
        return False


def _auth_load_user_by_id(user_id):
    if user_id is None:
        return None

    with sqlite3.connect(_auth_control_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        schema = _auth_users_schema(conn)

        users_table = schema["users_table"]
        cols = schema["cols"]

        select_parts = ["id", "email"]

        if schema["display_col"]:
            select_parts.append(f'{_auth_quote_ident(schema["display_col"])} AS display_name')
        else:
            select_parts.append("email AS display_name")

        if schema["role_col"]:
            select_parts.append(f'{_auth_quote_ident(schema["role_col"])} AS global_role')
        else:
            select_parts.append("'user' AS global_role")

        if schema["active_col"]:
            select_parts.append(f'{_auth_quote_ident(schema["active_col"])} AS is_active')
        else:
            select_parts.append("1 AS is_active")

        row = conn.execute(
            f"SELECT {', '.join(select_parts)} FROM {_auth_quote_ident(users_table)} WHERE id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            return None

        user = dict(row)
        user["id"] = int(user["id"])
        user["is_active"] = bool(user.get("is_active", True))

        if not user["is_active"]:
            return None

        return user


def _auth_load_user_by_email(email):
    email = str(email or "").strip().lower()
    if not email:
        return None

    with sqlite3.connect(_auth_control_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        schema = _auth_users_schema(conn)

        users_table = schema["users_table"]

        if not schema["password_col"]:
            return None

        select_parts = [
            "id",
            "email",
            f'{_auth_quote_ident(schema["password_col"])} AS password_hash',
        ]

        if schema["display_col"]:
            select_parts.append(f'{_auth_quote_ident(schema["display_col"])} AS display_name')
        else:
            select_parts.append("email AS display_name")

        if schema["role_col"]:
            select_parts.append(f'{_auth_quote_ident(schema["role_col"])} AS global_role')
        else:
            select_parts.append("'user' AS global_role")

        if schema["active_col"]:
            select_parts.append(f'{_auth_quote_ident(schema["active_col"])} AS is_active')
        else:
            select_parts.append("1 AS is_active")

        row = conn.execute(
            f"SELECT {', '.join(select_parts)} FROM {_auth_quote_ident(users_table)} WHERE lower(email) = lower(?)",
            (email,),
        ).fetchone()

        if row is None:
            return None

        user = dict(row)
        user["id"] = int(user["id"])
        user["is_active"] = bool(user.get("is_active", True))

        if not user["is_active"]:
            return None

        return user


def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    try:
        user = _auth_load_user_by_id(user_id)
    except Exception:
        user = None

    if user is None:
        session.clear()
        return None

    # Synchronisation douce de la session avec la DB.
    session["user_id"] = user["id"]
    session["email"] = user["email"]
    session["display_name"] = user.get("display_name")
    session["global_role"] = user.get("global_role") or "user"

    return user


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method in ("GET", "HEAD"):
        return render_template(
            "login.html",
            next_url=_safe_next_url(request.args.get("next")),
            error=None,
        )

    email = request.form.get("email") or ""
    password = request.form.get("password") or ""
    next_url = _safe_next_url(request.form.get("next"))

    user = authenticate_user(
        email=email,
        password=password,
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        user_agent=request.headers.get("User-Agent"),
    )

    if user is None:
        return render_template(
            "login.html",
            next_url=next_url,
            error="Identifiants invalides.",
        ), 401

    return redirect(next_url or "/")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    user_id = session.get("user_id")
    email = session.get("user_email")

    if user_id:
        record_auth_event(
            event_type="logout",
            user_id=int(user_id),
            email=email,
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
            user_agent=request.headers.get("User-Agent"),
        )

    session.clear()
    return redirect("/")


@auth_bp.route("/api/me", methods=["GET"])
def api_me():
    user = current_user()

    if user is None:
        return jsonify({
            "authenticated": False,
            "user": None,
            "mlc_access": [],
        })

    return jsonify({
        "authenticated": True,
        "user": user,
        "mlc_access": list_user_mlc_access(user["id"]),
    })

@auth_bp.route("/api/me/password", methods=["POST"])
def change_my_password():
    user = current_user()

    if user is None:
        return jsonify({
            "error": "Authentification requise.",
        }), 401

    payload = request.get_json(silent=True) or {}

    current_password = str(payload.get("current_password") or "")
    new_password = str(payload.get("new_password") or "")
    confirm_password = str(payload.get("confirm_password") or "")

    if not current_password:
        return jsonify({"error": "Mot de passe actuel manquant."}), 400

    if len(new_password) < 10:
        return jsonify({"error": "Le nouveau mot de passe doit contenir au moins 10 caractères."}), 400

    if new_password != confirm_password:
        return jsonify({"error": "La confirmation ne correspond pas au nouveau mot de passe."}), 400

    try:
        with sqlite3.connect(_auth_control_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            schema = _auth_users_schema(conn)

            users_table = schema["users_table"]
            password_col = schema.get("password_col")

            if not password_col:
                return jsonify({
                    "error": "Colonne de mot de passe introuvable.",
                }), 500

            row = conn.execute(
                f"""
                SELECT id, email, {_auth_quote_ident(password_col)} AS password_hash
                FROM {_auth_quote_ident(users_table)}
                WHERE id = ?
                """,
                (user["id"],),
            ).fetchone()

            if row is None:
                return jsonify({"error": "Compte introuvable."}), 404

            if not _auth_verify_password(row["password_hash"], current_password):
                return jsonify({"error": "Mot de passe actuel incorrect."}), 403

            new_hash = generate_password_hash(
                new_password,
                method="pbkdf2:sha256",
                salt_length=16,
            )

            columns = _auth_columns(conn, users_table)

            if "updated_at" in columns:
                conn.execute(
                    f"""
                    UPDATE {_auth_quote_ident(users_table)}
                    SET {_auth_quote_ident(password_col)} = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (new_hash, user["id"]),
                )
            else:
                conn.execute(
                    f"""
                    UPDATE {_auth_quote_ident(users_table)}
                    SET {_auth_quote_ident(password_col)} = ?
                    WHERE id = ?
                    """,
                    (new_hash, user["id"]),
                )

            conn.commit()

        return jsonify({
            "ok": True,
            "message": "Mot de passe modifié.",
        })

    except Exception as exc:
        return jsonify({
            "error": f"Impossible de modifier le mot de passe : {type(exc).__name__}: {exc}",
        }), 500

