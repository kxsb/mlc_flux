from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from server.contracts.transactions_v1 import (
    CONTRACT_COLUMNS,
    TransactionContractError,
    TransactionContractRow,
    normalize_transaction_rows,
)


class NormalizedTransactionsPostgresError(RuntimeError):
    """Erreur de lecture du contrat SQL TRANSACTIONS001."""


@dataclass(frozen=True)
class NormalizedTransactionsPostgresSource:
    """
    Lecteur PostgreSQL du contrat transactions_*.

    `relation` est fournie par l'installation.
    Aucun nom ComChain/Cyclos/monnaie n'est codé en dur.
    """

    dsn: str
    relation: str
    schema: str = "public"

    def _validate_configuration(self) -> None:
        if not self.dsn:
            raise NormalizedTransactionsPostgresError(
                "DSN PostgreSQL absente."
            )

        if not self.schema:
            raise NormalizedTransactionsPostgresError(
                "Schéma PostgreSQL absent."
            )

        if not self.relation:
            raise NormalizedTransactionsPostgresError(
                "Relation PostgreSQL absente."
            )

    def fetch_raw_rows(self) -> list[dict]:
        """
        Lecture strictement READ ONLY.

        SELECT DISTINCT élimine le bug actuel de fixture lorsque
        plusieurs jointures produisent une ligne normalisée identique.
        """
        self._validate_configuration()

        columns = sql.SQL(", ").join(
            sql.Identifier(column)
            for column in CONTRACT_COLUMNS
        )

        query = sql.SQL("""
            SELECT DISTINCT {}
            FROM {}.{}
            ORDER BY received_at, hash
        """).format(
            columns,
            sql.Identifier(self.schema),
            sql.Identifier(self.relation),
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
            raise NormalizedTransactionsPostgresError(
                "Échec de lecture du contrat TRANSACTIONS001."
            ) from exc

    def fetch_transactions(
        self,
    ) -> tuple[TransactionContractRow, ...]:
        try:
            return normalize_transaction_rows(
                self.fetch_raw_rows()
            )

        except TransactionContractError:
            raise
