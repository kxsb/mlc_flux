from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Blueprint, jsonify, request

import server.control_db as control_db
from server.mlc_profiles import list_public_mlc_profiles
from server.routes.auth import current_user


admin_accounts_bp = Blueprint("admin_accounts", __name__)


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


def _tables(conn) -> list[str]:
    return [
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    ]


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({_quote_ident(table)})")}


def _pick_table(conn, candidates: list[str], required_columns: set[str]) -> str | None:
    table_names = _tables(conn)
    lowered = {table.lower(): table for table in table_names}

    for candidate in candidates:
        table = lowered.get(candidate.lower())
        if table and required_columns <= _columns(conn, table):
            return table

    for table in table_names:
        if required_columns <= _columns(conn, table):
            return table

    return None


def _pick_column(columns: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _schema(conn):
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

    user_cols = _columns(conn, users_table)

    access_table = _pick_table(
        conn,
        ["control_user_mlc_access", "user_mlc_access", "mlc_user_access", "user_instance_access"],
        {"user_id", "mlc_id", "role"},
    )

    display_col = _pick_column(user_cols, ["display_name", "name", "username", "full_name"])
    role_col = _pick_column(user_cols, ["global_role", "role", "admin_role"])
    active_col = _pick_column(user_cols, ["is_active", "active", "enabled"])

    return {
        "users_table": users_table,
        "user_cols": user_cols,
        "access_table": access_table,
        "display_col": display_col,
        "role_col": role_col,
        "active_col": active_col,
    }



def _pending_request_emails(conn) -> set[str]:
    tables = _tables(conn)
    if "account_registration_requests" not in tables:
        return set()

    return {
        str(row["email"]).strip().lower()
        for row in conn.execute(
            """
            SELECT email
            FROM account_registration_requests
            WHERE status = 'pending'
              AND email IS NOT NULL
            """
        ).fetchall()
    }



def _access_table_required_defaults(conn, table: str) -> dict:
    defaults = {}

    for row in conn.execute(f"PRAGMA table_info({_quote_ident(table)})"):
        col = row[1]
        notnull = bool(row[3])
        default = row[4]
        pk = bool(row[5])

        if pk:
            continue

        if col in {"user_id", "mlc_id", "role"}:
            continue

        if notnull and default is None:
            if col in {"created_at", "updated_at", "granted_at"}:
                defaults[col] = "CURRENT_TIMESTAMP"
            elif col in {"created_by_user_id", "granted_by_user_id"}:
                defaults[col] = None
            elif col in {"is_active", "active", "enabled"}:
                defaults[col] = 1

    return defaults


def _replace_user_access_rows(conn, access_table: str, user_id: int, mlc_access: list, admin_user_id=None):
    access_cols = _columns(conn, access_table)
    q_access = _quote_ident(access_table)

    conn.execute(
        f"DELETE FROM {q_access} WHERE user_id = ?",
        (user_id,),
    )

    for item in mlc_access:
        if not isinstance(item, dict):
            continue

        enabled = bool(item.get("enabled"))
        if not enabled:
            continue

        mlc_id = str(item.get("mlc_id") or "").strip()
        role = str(item.get("role") or "viewer").strip() or "viewer"

        if not mlc_id:
            continue

        cols = ["user_id", "mlc_id", "role"]
        values = [user_id, mlc_id, role]

        if "created_by_user_id" in access_cols:
            cols.append("created_by_user_id")
            values.append(admin_user_id)

        if "granted_by_user_id" in access_cols:
            cols.append("granted_by_user_id")
            values.append(admin_user_id)

        if "created_at" in access_cols:
            cols.append("created_at")
            values.append(__import__("datetime").datetime.utcnow().isoformat(timespec="seconds"))

        if "granted_at" in access_cols:
            cols.append("granted_at")
            values.append(__import__("datetime").datetime.utcnow().isoformat(timespec="seconds"))

        if "is_active" in access_cols:
            cols.append("is_active")
            values.append(1)

        if "active" in access_cols:
            cols.append("active")
            values.append(1)

        if "enabled" in access_cols:
            cols.append("enabled")
            values.append(1)

        placeholders = ", ".join("?" for _ in cols)
        sql = (
            f"INSERT INTO {q_access} "
            f"({', '.join(_quote_ident(col) for col in cols)}) "
            f"VALUES ({placeholders})"
        )

        conn.execute(sql, values)


def _load_accounts(conn):
    schema = _schema(conn)
    users_table = schema["users_table"]
    q_users = _quote_ident(users_table)

    select_parts = [
        "id",
        "email",
    ]

    if schema["display_col"]:
        select_parts.append(f'{_quote_ident(schema["display_col"])} AS display_name')
    else:
        select_parts.append("email AS display_name")

    if schema["role_col"]:
        select_parts.append(f'{_quote_ident(schema["role_col"])} AS global_role')
    else:
        select_parts.append("'user' AS global_role")

    if schema["active_col"]:
        select_parts.append(f'{_quote_ident(schema["active_col"])} AS is_active')
    else:
        select_parts.append("1 AS is_active")

    pending_emails = _pending_request_emails(conn)

    users = [
        dict(row)
        for row in conn.execute(
            f"SELECT {', '.join(select_parts)} FROM {q_users} ORDER BY email COLLATE NOCASE"
        )
    ]

    # AUTH_FLOW021_PENDING_ACCOUNT_LOGIC_FIX
    # Si un email est encore dans les demandes pending, il ne doit pas être affiché
    # comme compte validé. Cela évite l’ambiguïté demande en attente / compte actif.
    users = [
        user for user in users
        if str(user.get("email") or "").strip().lower() not in pending_emails
    ]

    access_by_user = {int(user["id"]): [] for user in users}

    if schema["access_table"]:
        q_access = _quote_ident(schema["access_table"])
        for row in conn.execute(
            f"SELECT user_id, mlc_id, role FROM {q_access} ORDER BY mlc_id"
        ):
            uid = int(row["user_id"])
            if uid not in access_by_user:
                access_by_user[uid] = []
            access_by_user[uid].append({
                "mlc_id": row["mlc_id"],
                "role": row["role"],
            })

    for user in users:
        user["id"] = int(user["id"])
        user["is_active"] = bool(user.get("is_active"))
        user["mlc_access"] = access_by_user.get(user["id"], [])

    return users, schema


def _available_roles(accounts):
    global_roles = {"user", "admin"}
    instance_roles = {"viewer", "analyst", "admin"}

    for account in accounts:
        if account.get("global_role"):
            global_roles.add(str(account["global_role"]))

        for access in account.get("mlc_access", []):
            if access.get("role"):
                instance_roles.add(str(access["role"]))

    return {
        "global_roles": sorted(global_roles),
        "instance_roles": sorted(instance_roles),
    }


@admin_accounts_bp.route("/api/admin/accounts", methods=["GET"])
def admin_accounts_list():
    admin_user, error = _require_admin()
    if error:
        return error

    db_path = _control_db_path()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        accounts, schema = _load_accounts(conn)
        profiles = [_profile_to_public_dict(profile) for profile in list_public_mlc_profiles()]

    return jsonify({
        "ok": True,
        "accounts": accounts,
        "instances": profiles,
        "available_roles": _available_roles(accounts),
        "schema": {
            "users_table": schema["users_table"],
            "access_table": schema["access_table"],
            "has_global_role": bool(schema["role_col"]),
        },
        "current_admin": {
            "id": admin_user.get("id"),
            "email": admin_user.get("email"),
            "display_name": admin_user.get("display_name"),
            "global_role": admin_user.get("global_role"),
        },
    })


@admin_accounts_bp.route("/api/admin/accounts/<int:user_id>", methods=["POST"])
def admin_accounts_update(user_id: int):
    admin_user, error = _require_admin()
    if error:
        return error

    payload = request.get_json(silent=True) or {}

    global_role = str(payload.get("global_role") or "").strip()
    mlc_access = payload.get("mlc_access") or []

    if not isinstance(mlc_access, list):
        return jsonify({"error": "mlc_access doit être une liste."}), 400

    db_path = _control_db_path()

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            schema = _schema(conn)

            users_table = schema["users_table"]
            access_table = schema["access_table"]

            existing = conn.execute(
                f"SELECT id, email FROM {_quote_ident(users_table)} WHERE id = ?",
                (user_id,),
            ).fetchone()

            if existing is None:
                return jsonify({"error": "Compte introuvable."}), 404

            # Ne pas permettre à un admin de se retirer lui-même son rôle admin.
            if schema["role_col"] and global_role:
                current_admin_id = admin_user.get("id")
                if current_admin_id is not None and int(current_admin_id) == int(user_id) and global_role != "admin":
                    return jsonify({
                        "error": "Vous ne pouvez pas retirer votre propre rôle admin depuis cette interface.",
                    }), 400

                conn.execute(
                    f"UPDATE {_quote_ident(users_table)} SET {_quote_ident(schema['role_col'])} = ? WHERE id = ?",
                    (global_role, user_id),
                )

            if access_table is None:
                return jsonify({
                    "error": "Table d'accès MLC introuvable. Impossible de modifier les accès par instance.",
                }), 500

            _replace_user_access_rows(
                conn,
                access_table,
                user_id,
                mlc_access,
                admin_user_id=admin_user.get("id"),
            )

            conn.commit()

            accounts, _ = _load_accounts(conn)
            updated = next((account for account in accounts if account["id"] == user_id), None)

        return jsonify({
            "ok": True,
            "account": updated,
        })

    except Exception as exc:
        return jsonify({
            "error": f"Impossible d’enregistrer les droits : {type(exc).__name__}: {exc}",
        }), 500

@admin_accounts_bp.route("/api/admin/accounts/<int:user_id>/delete", methods=["POST"])
def admin_accounts_delete(user_id: int):
    admin_user, error = _require_admin()
    if error:
        return error

    db_path = _control_db_path()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        schema = _schema(conn)

        users_table = schema["users_table"]
        access_table = schema["access_table"]

        existing = conn.execute(
            f"SELECT id, email FROM {_quote_ident(users_table)} WHERE id = ?",
            (user_id,),
        ).fetchone()

        if existing is None:
            return jsonify({"error": "Compte introuvable."}), 404

        admin_id = admin_user.get("id")
        admin_email = str(admin_user.get("email") or "").strip().lower()
        target_email = str(existing["email"] or "").strip().lower()

        # Protection du compte connecté.
        # On compare l'id si fiable, mais aussi l'email pour éviter les faux positifs
        # liés aux collisions / conversions de session.
        if admin_id is not None and int(admin_id) == int(user_id):
            return jsonify({
                "error": (
                    "Suppression bloquée : le compte ciblé correspond à l'identifiant "
                    "de la session admin active. Déconnectez-vous/reconnectez-vous si "
                    "la session affichée semble incohérente."
                ),
                "current_admin": {
                    "id": admin_user.get("id"),
                    "email": admin_user.get("email"),
                    "display_name": admin_user.get("display_name"),
                },
                "target": {
                    "id": user_id,
                    "email": existing["email"],
                },
            }), 400

        if admin_email and admin_email == target_email:
            return jsonify({
                "error": "Vous ne pouvez pas supprimer votre propre compte admin connecté.",
                "current_admin": {
                    "id": admin_user.get("id"),
                    "email": admin_user.get("email"),
                    "display_name": admin_user.get("display_name"),
                },
                "target": {
                    "id": user_id,
                    "email": existing["email"],
                },
            }), 400

        if access_table is not None:
            conn.execute(
                f"DELETE FROM {_quote_ident(access_table)} WHERE user_id = ?",
                (user_id,),
            )

        conn.execute(
            f"DELETE FROM {_quote_ident(users_table)} WHERE id = ?",
            (user_id,),
        )

        conn.commit()

    return jsonify({
        "ok": True,
        "deleted_user_id": user_id,
    })

