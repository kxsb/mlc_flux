from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

import server.control_db as control_db
from server.mlc_profiles import list_public_mlc_profiles
from server.routes.auth import current_user


account_requests_bp = Blueprint("account_requests", __name__)


def _control_db_path() -> Path:
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
    checked = []

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
        checked.append(str(path))

        if path.is_file():
            return path

    raise RuntimeError(
        "Base de contrôle introuvable. Chemins testés : " + ", ".join(checked[:12])
    )


def _profile_to_public_dict(profile):
    if isinstance(profile, dict):
        return dict(profile)

    if hasattr(profile, "public_dict"):
        return profile.public_dict()

    result = {}
    for key in ("id", "name", "short_name", "currency_symbol", "description"):
        if hasattr(profile, key):
            result[key] = getattr(profile, key)

    return result


def _quote_ident(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({_quote_ident(table)})")}


def _tables(conn) -> list[str]:
    return [
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    ]


def _pick_table(conn, candidates: list[str], required_columns: set[str]) -> str | None:
    lowered = {table.lower(): table for table in _tables(conn)}

    for candidate in candidates:
        table = lowered.get(candidate.lower())
        if table and required_columns <= _columns(conn, table):
            return table

    for table in _tables(conn):
        if required_columns <= _columns(conn, table):
            return table

    return None


def _pick_column(columns: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _users_schema(conn):
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

    users_table = None
    table_names = _tables(conn)

    for candidate in preferred_user_tables:
        for table in table_names:
            if table.lower() != candidate.lower():
                continue
            if table in excluded_tables:
                continue
            cols = _columns(conn, table)
            if {"id", "email"} <= cols:
                users_table = table
                break
        if users_table:
            break

    if users_table is None:
        scored = []
        for table in table_names:
            if table in excluded_tables:
                continue

            cols = _columns(conn, table)

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
        raise RuntimeError("Table utilisateurs réelle introuvable. Vérifier control.db.")

    cols = _columns(conn, users_table)

    return {
        "users_table": users_table,
        "cols": cols,
        "display_col": _pick_column(cols, ["display_name", "name", "username", "full_name"]),
        "password_col": _pick_column(cols, ["password_hash", "hashed_password", "password"]),
        "role_col": _pick_column(cols, ["global_role", "role", "admin_role"]),
        "active_col": _pick_column(cols, ["is_active", "active", "enabled"]),
    }



def _access_table(conn):
    return _pick_table(
        conn,
        ["user_mlc_access", "mlc_user_access", "user_instance_access"],
        {"user_id", "mlc_id", "role"},
    )


def _require_admin():
    user = current_user()
    if user is None:
        return None, (jsonify({
            "authenticated": False,
            "error": "Authentification requise.",
        }), 401)

    if user.get("global_role") != "admin":
        return None, (jsonify({
            "authenticated": True,
            "error": "Accès réservé aux administrateurs.",
        }), 403)

    return user, None


def _init_request_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS account_registration_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT,
            reviewed_by_user_id INTEGER,
            review_note TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS account_registration_request_access (
            request_id INTEGER NOT NULL,
            mlc_id TEXT NOT NULL,
            requested_role TEXT NOT NULL DEFAULT 'viewer',
            PRIMARY KEY (request_id, mlc_id),
            FOREIGN KEY (request_id) REFERENCES account_registration_requests(id)
        )
    """)

    conn.commit()


def _valid_mlc_ids() -> set[str]:
    result = set()
    for profile in list_public_mlc_profiles():
        item = _profile_to_public_dict(profile)
        mlc_id = item.get("id")
        if mlc_id:
            result.add(str(mlc_id))
    return result




def _insert_user_mlc_access(conn, access_table: str, user_id: int, mlc_id: str, role: str):
    access_cols = _columns(conn, access_table)
    now = datetime.utcnow().isoformat(timespec="seconds")

    values_by_col = {
        "user_id": user_id,
        "mlc_id": mlc_id,
        "role": role,
    }

    if "created_at" in access_cols:
        values_by_col["created_at"] = now

    if "updated_at" in access_cols:
        values_by_col["updated_at"] = now

    if "granted_at" in access_cols:
        values_by_col["granted_at"] = now

    if "is_active" in access_cols:
        values_by_col["is_active"] = 1

    if "active" in access_cols:
        values_by_col["active"] = 1

    if "enabled" in access_cols:
        values_by_col["enabled"] = 1

    for row in conn.execute(f"PRAGMA table_info({_quote_ident(access_table)})"):
        col = row[1]
        notnull = bool(row[3])
        default = row[4]
        pk = bool(row[5])

        if pk or col in values_by_col:
            continue

        if not notnull or default is not None:
            continue

        lower = col.lower()

        if lower in {"created_at", "updated_at", "granted_at"}:
            values_by_col[col] = now
        elif lower in {"is_active", "active", "enabled"}:
            values_by_col[col] = 1
        else:
            raise RuntimeError(
                f"Colonne obligatoire non gérée dans {access_table}: {col}"
            )

    insert_cols = [col for col in values_by_col.keys() if col in access_cols]
    insert_values = [values_by_col[col] for col in insert_cols]

    conn.execute(
        f"""
        INSERT OR REPLACE INTO {_quote_ident(access_table)}
            ({', '.join(_quote_ident(col) for col in insert_cols)})
        VALUES
            ({', '.join('?' for _ in insert_cols)})
        """,
        insert_values,
    )


def _build_user_insert_payload(conn, schema, request_row, global_role="user"):
    users_table = schema["users_table"]
    user_cols = schema["cols"]

    password_col = schema.get("password_col")
    display_col = schema.get("display_col")
    role_col = schema.get("role_col")
    active_col = schema.get("active_col")

    if not password_col:
        raise RuntimeError("Colonne de mot de passe introuvable dans la table utilisateurs.")

    values_by_col = {
        "email": request_row["email"],
        password_col: request_row["password_hash"],
    }

    if display_col:
        values_by_col[display_col] = request_row["display_name"]

    if role_col:
        values_by_col[role_col] = global_role

    if active_col:
        values_by_col[active_col] = 1

    now = datetime.utcnow().isoformat(timespec="seconds")

    # Remplissage des colonnes NOT NULL sans valeur par défaut.
    for row in conn.execute(f"PRAGMA table_info({_quote_ident(users_table)})"):
        col = row[1]
        notnull = bool(row[3])
        default = row[4]
        pk = bool(row[5])

        if pk or col in values_by_col:
            continue

        if not notnull or default is not None:
            continue

        lower = col.lower()

        if lower in {"created_at", "created_on", "created"}:
            values_by_col[col] = now
        elif lower in {"updated_at", "updated_on", "modified_at", "modified_on"}:
            values_by_col[col] = now
        elif lower in {"is_active", "active", "enabled"}:
            values_by_col[col] = 1
        elif lower in {"global_role", "role", "admin_role"}:
            values_by_col[col] = global_role
        elif lower in {"display_name", "name", "username", "full_name"}:
            values_by_col[col] = request_row["display_name"]
        else:
            raise RuntimeError(
                f"Colonne obligatoire non gérée dans {users_table}: {col}"
            )

    insert_cols = [col for col in values_by_col.keys() if col in user_cols]
    insert_values = [values_by_col[col] for col in insert_cols]

    return insert_cols, insert_values


def _request_to_dict(row, access_items):
    return {
        "id": int(row["id"]),
        "display_name": row["display_name"],
        "email": row["email"],
        "message": row["message"],
        "status": row["status"],
        "created_at": row["created_at"],
        "reviewed_at": row["reviewed_at"],
        "review_note": row["review_note"],
        "requested_access": access_items,
    }


def _load_pending_requests(conn):
    _init_request_tables(conn)

    rows = conn.execute("""
        SELECT *
        FROM account_registration_requests
        WHERE status = 'pending'
        ORDER BY created_at ASC
    """).fetchall()

    result = []

    for row in rows:
        access = [
            {
                "mlc_id": item["mlc_id"],
                "requested_role": item["requested_role"],
            }
            for item in conn.execute(
                """
                SELECT mlc_id, requested_role
                FROM account_registration_request_access
                WHERE request_id = ?
                ORDER BY mlc_id
                """,
                (row["id"],),
            ).fetchall()
        ]
        result.append(_request_to_dict(row, access))

    return result


@account_requests_bp.route("/api/account-requests", methods=["POST"])
def create_account_request():
    payload = request.get_json(silent=True) or {}

    display_name = str(payload.get("display_name") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    message = str(payload.get("message") or "").strip()
    requested_access = payload.get("requested_access") or []

    if not display_name:
        return jsonify({"error": "Nom d’utilisateur manquant."}), 400

    if "@" not in email or "." not in email:
        return jsonify({"error": "Adresse email invalide."}), 400

    if len(password) < 10:
        return jsonify({"error": "Mot de passe trop court : minimum 10 caractères."}), 400

    if not isinstance(requested_access, list) or not requested_access:
        return jsonify({"error": "Demandez au moins une instance."}), 400

    valid_mlc_ids = _valid_mlc_ids()
    normalized_access = []

    for item in requested_access:
        if not isinstance(item, dict):
            continue

        mlc_id = str(item.get("mlc_id") or "").strip()
        if mlc_id not in valid_mlc_ids:
            continue

        normalized_access.append({
            "mlc_id": mlc_id,
            "requested_role": "viewer",
        })

    if not normalized_access:
        return jsonify({"error": "Aucune instance valide demandée."}), 400

    db_path = _control_db_path()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _init_request_tables(conn)

        schema = _users_schema(conn)
        users_table = schema["users_table"]

        existing_user = conn.execute(
            f"SELECT id FROM {_quote_ident(users_table)} WHERE lower(email) = lower(?)",
            (email,),
        ).fetchone()

        if existing_user is not None:
            return jsonify({
                "ok": True,
                "status": "pending",
                "message": "Si la demande est recevable, elle sera transmise à un administrateur.",
            })

        existing_request = conn.execute(
            """
            SELECT id
            FROM account_registration_requests
            WHERE lower(email) = lower(?)
              AND status = 'pending'
            """,
            (email,),
        ).fetchone()

        if existing_request is not None:
            return jsonify({
                "ok": True,
                "status": "pending",
                "message": "Si la demande est recevable, elle sera transmise à un administrateur.",
            })

        cur = conn.execute(
            """
            INSERT INTO account_registration_requests
                (display_name, email, password_hash, message, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (
                display_name,
                email,
                generate_password_hash(password, method="pbkdf2:sha256", salt_length=16),
                message,
            ),
        )

        request_id = int(cur.lastrowid)

        for item in normalized_access:
            conn.execute(
                """
                INSERT INTO account_registration_request_access
                    (request_id, mlc_id, requested_role)
                VALUES (?, ?, ?)
                """,
                (request_id, item["mlc_id"], item["requested_role"]),
            )

        conn.commit()

    return jsonify({
        "ok": True,
        "status": "pending",
        "message": "Votre demande de compte a été enregistrée. Elle devra être validée par un administrateur.",
    })


@account_requests_bp.route("/api/admin/account-requests", methods=["GET"])
def admin_account_requests_list():
    _, error = _require_admin()
    if error:
        return error

    db_path = _control_db_path()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        requests = _load_pending_requests(conn)
        instances = [_profile_to_public_dict(profile) for profile in list_public_mlc_profiles()]

    return jsonify({
        "ok": True,
        "pending_count": len(requests),
        "requests": requests,
        "instances": instances,
    })


@account_requests_bp.route("/api/admin/account-requests/<int:request_id>/reject", methods=["POST"])
def admin_reject_account_request(request_id: int):
    admin_user, error = _require_admin()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    review_note = str(payload.get("review_note") or "").strip()

    db_path = _control_db_path()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _init_request_tables(conn)

        row = conn.execute(
            "SELECT id FROM account_registration_requests WHERE id = ? AND status = 'pending'",
            (request_id,),
        ).fetchone()

        if row is None:
            return jsonify({"error": "Demande introuvable ou déjà traitée."}), 404

        conn.execute(
            """
            UPDATE account_registration_requests
            SET status = 'rejected',
                reviewed_at = CURRENT_TIMESTAMP,
                reviewed_by_user_id = ?,
                review_note = ?
            WHERE id = ?
            """,
            (admin_user["id"], review_note, request_id),
        )
        conn.commit()

    return jsonify({"ok": True})


@account_requests_bp.route("/api/admin/account-requests/<int:request_id>/approve", methods=["POST"])
def admin_approve_account_request(request_id: int):
    try:
        admin_user, error = _require_admin()
        if error:
            return error

        payload = request.get_json(silent=True) or {}
        access_payload = payload.get("mlc_access")

        db_path = _control_db_path()

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            _init_request_tables(conn)

            request_row = conn.execute(
                """
                SELECT *
                FROM account_registration_requests
                WHERE id = ? AND status = 'pending'
                """,
                (request_id,),
            ).fetchone()

            if request_row is None:
                return jsonify({"error": "Demande introuvable ou déjà traitée."}), 404

            schema = _users_schema(conn)
            users_table = schema["users_table"]
            access_table = _access_table(conn)

            if not schema["password_col"]:
                return jsonify({
                    "error": "Colonne de mot de passe introuvable dans la table utilisateurs.",
                }), 500

            if access_table is None:
                return jsonify({
                    "error": "Table d'accès MLC introuvable.",
                }), 500

            existing_user = conn.execute(
                f"SELECT id FROM {_quote_ident(users_table)} WHERE lower(email) = lower(?)",
                (request_row["email"],),
            ).fetchone()

            if existing_user is not None:
                user_id = int(existing_user["id"])
            else:
                insert_cols, insert_values = _build_user_insert_payload(
                    conn,
                    schema,
                    request_row,
                    global_role="user",
                )

                cur = conn.execute(
                    f"INSERT INTO {_quote_ident(users_table)} "
                    f"({', '.join(_quote_ident(col) for col in insert_cols)}) "
                    f"VALUES ({', '.join('?' for _ in insert_cols)})",
                    insert_values,
                )

                user_id = int(cur.lastrowid)

            if access_payload is None:
                requested_rows = conn.execute(
                    """
                    SELECT mlc_id, requested_role
                    FROM account_registration_request_access
                    WHERE request_id = ?
                    """,
                    (request_id,),
                ).fetchall()

                access_items = [
                    {
                        "mlc_id": row["mlc_id"],
                        "role": row["requested_role"] or "viewer",
                        "enabled": True,
                    }
                    for row in requested_rows
                ]
            else:
                access_items = access_payload if isinstance(access_payload, list) else []

            for item in access_items:
                if not isinstance(item, dict):
                    continue

                if item.get("enabled") is False:
                    continue

                mlc_id = str(item.get("mlc_id") or "").strip()
                role = str(item.get("role") or item.get("requested_role") or "viewer").strip() or "viewer"

                if not mlc_id:
                    continue

                _insert_user_mlc_access(
                    conn,
                    access_table,
                    user_id,
                    mlc_id,
                    role,
                )

            conn.execute(
                """
                UPDATE account_registration_requests
                SET status = 'approved',
                    reviewed_at = CURRENT_TIMESTAMP,
                    reviewed_by_user_id = ?,
                    review_note = COALESCE(review_note, '') || ' | Validé AUTH_FLOW023.'
                WHERE id = ?
                """,
                (admin_user["id"], request_id),
            )

            conn.commit()

        return jsonify({
            "ok": True,
            "created_user_id": user_id,
        })

    except Exception as exc:
        return jsonify({
            "error": f"Impossible de valider la demande : {type(exc).__name__}: {exc}",
        }), 500

