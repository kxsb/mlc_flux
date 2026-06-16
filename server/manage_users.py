from __future__ import annotations

import argparse
import getpass
import sys

from server.control_db import (
    CONTROL_DB_PATH,
    create_or_update_user,
    get_user_by_email,
    grant_mlc_access,
    init_control_db,
    list_user_mlc_access,
)


def _parse_mlc_access(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise argparse.ArgumentTypeError(
            "Format attendu : mlc_id:role, exemple graine:manager"
        )

    mlc_id, role = value.split(":", 1)
    mlc_id = mlc_id.strip()
    role = role.strip().lower()

    if not mlc_id or not role:
        raise argparse.ArgumentTypeError(
            "Format attendu : mlc_id:role, exemple graine:manager"
        )

    return mlc_id, role


def create_admin(args: argparse.Namespace) -> int:
    init_control_db()

    password = getpass.getpass("Mot de passe admin : ")
    confirm = getpass.getpass("Confirmation : ")

    if password != confirm:
        print("Erreur : les mots de passe ne correspondent pas.", file=sys.stderr)
        return 1

    user = create_or_update_user(
        email=args.email,
        display_name=args.name,
        password=password,
        global_role="admin",
        is_active=True,
    )

    for mlc_id, role in args.mlc:
        grant_mlc_access(email=args.email, mlc_id=mlc_id, role=role)

    access = list_user_mlc_access(user["id"])

    print("Utilisateur admin créé / mis à jour.")
    print(f"- email       : {user['email']}")
    print(f"- nom         : {user['display_name']}")
    print(f"- rôle global : {user['global_role']}")
    print(f"- DB contrôle : {CONTROL_DB_PATH}")
    print("- accès MLC   :")
    for item in access:
        print(f"  - {item['mlc_id']} : {item['role']}")

    return 0


def show_user(args: argparse.Namespace) -> int:
    init_control_db()

    user = get_user_by_email(args.email)
    if user is None:
        print("Utilisateur introuvable.", file=sys.stderr)
        return 1

    print(user)
    for item in list_user_mlc_access(user["id"]):
        print(f"- {item['mlc_id']} : {item['role']}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Gestion utilisateurs MLCFlux.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin_parser = subparsers.add_parser("create-admin")
    create_admin_parser.add_argument("--email", required=True)
    create_admin_parser.add_argument("--name", required=True)
    create_admin_parser.add_argument(
        "--mlc",
        action="append",
        type=_parse_mlc_access,
        default=[],
        help="Accès MLC au format mlc_id:role. Exemple : --mlc graine:manager",
    )
    create_admin_parser.set_defaults(func=create_admin)

    show_parser = subparsers.add_parser("show-user")
    show_parser.add_argument("--email", required=True)
    show_parser.set_defaults(func=show_user)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
