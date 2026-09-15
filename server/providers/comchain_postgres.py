from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row


class ComChainPostgresError(RuntimeError):
    """Erreur de lecture de la source PostgreSQL ComChain."""


@dataclass(frozen=True)
class ComChainPostgresSource:
    dsn: str
    schema: str
    table: str = "transactions"

    def fetch_transactions(self) -> list[dict[str, Any]]:
        """
        Lit la relation ComChain native en transaction READ ONLY.

        La relation est fournie explicitement par l'installation :
        aucun nom de monnaie n'est codé en dur dans le connecteur.
        """
        if not self.dsn:
            raise ComChainPostgresError("DSN PostgreSQL absente.")

        if not self.schema:
            raise ComChainPostgresError("Schéma PostgreSQL absent.")

        if not self.table:
            raise ComChainPostgresError("Table PostgreSQL absente.")

        query = sql.SQL("""
            SELECT
                hash,
                block,
                received_at,
                caller,
                contract,
                contract_abi,
                fn,
                fn_abi,
                type,
                sender,
                receiver,
                amount,
                status
            FROM {}.{}
            ORDER BY block, hash
        """).format(
            sql.Identifier(self.schema),
            sql.Identifier(self.table),
        )

        try:
            with psycopg.connect(
                self.dsn,
                autocommit=False,
                row_factory=dict_row,
            ) as conn:
                with conn.transaction():
                    conn.execute(
                        "SET TRANSACTION READ ONLY"
                    )

                    rows = conn.execute(query).fetchall()

                    return [dict(row) for row in rows]

        except psycopg.Error as exc:
            raise ComChainPostgresError(
                "Échec de lecture PostgreSQL ComChain."
            ) from exc
