from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL

from server.mlc_context import (
    ensure_mlc_instance_dirs,
    get_mlc_input001_db_path,
)


def _ensure_private_sqlite_file(db_path) -> None:
    """
    Garantit que la base INPUT001 existe avec des droits privés.

    INPUT001 contient des faits financiers et des identifiants de comptes :
    elle ne doit pas hériter d'un umask permissif.
    """
    try:
        fd = os.open(
            db_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError:
        db_path.chmod(0o600)
    else:
        os.close(fd)

        # Garantit 0600 même avec un umask inhabituel.
        db_path.chmod(0o600)


def create_input001_engine(
    mlc_id: str | None = None,
) -> Engine:
    """
    Crée le moteur SQL INPUT001 de l'instance.

    INPUT001 utilise volontairement une base distincte de mlcflux.db :
    les noms de relations du contrat, notamment `transactions`, sont
    incompatibles avec le schéma SQLite legacy.
    """
    dirs = ensure_mlc_instance_dirs(mlc_id)
    db_path = get_mlc_input001_db_path(mlc_id)

    if db_path == dirs["db_path"]:
        raise RuntimeError(
            "La base INPUT001 ne doit jamais être la base legacy."
        )

    _ensure_private_sqlite_file(db_path)

    return create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(db_path),
        ),
        connect_args={
            "timeout": 5,
        },
    )
