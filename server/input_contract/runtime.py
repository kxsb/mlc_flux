from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL

from server.mlc_context import (
    ensure_mlc_instance_dirs,
    get_mlc_input001_db_path,
)


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

    return create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(db_path),
        ),
        connect_args={
            "timeout": 5,
        },
    )
