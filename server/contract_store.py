from __future__ import annotations

from datetime import UTC, datetime
import sqlite3

from server.contracts.partners_v1 import (
    PartnerContractRow,
)
from server.contracts.transactions_v1 import (
    TransactionContractRow,
    transaction_event_signature,
)


def init_contract_tables(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS contract001_transactions (
            hash TEXT PRIMARY KEY,
            amount INTEGER NOT NULL,
            received_at INTEGER NOT NULL,
            fn_abi TEXT,
            type TEXT,
            is_sender_external INTEGER NOT NULL
                CHECK (is_sender_external IN (0, 1)),
            is_receiver_external INTEGER NOT NULL
                CHECK (is_receiver_external IN (0, 1))
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_contract001_transactions_received_at
        ON contract001_transactions (received_at)
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS
            contract001_transaction_partners (
                hash TEXT NOT NULL,
                side TEXT NOT NULL
                    CHECK (side IN ('sender', 'receiver')),
                partner_id INTEGER NOT NULL,
                PRIMARY KEY (hash, side, partner_id),
                FOREIGN KEY (hash)
                    REFERENCES contract001_transactions(hash)
                    ON DELETE CASCADE
            )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_contract001_transaction_partners_partner
        ON contract001_transaction_partners (
            partner_id,
            side
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_contract001_transaction_partners_hash
        ON contract001_transaction_partners (
            hash,
            side
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS contract002_partners (
            partner_id INTEGER PRIMARY KEY,
            name TEXT,
            is_company INTEGER
                CHECK (
                    is_company IS NULL
                    OR is_company IN (0, 1)
                ),
            member_type TEXT,
            industry_code TEXT,
            industry_name TEXT,
            siret TEXT,
            siren TEXT,
            legal_activity_code TEXT,
            city TEXT,
            zip TEXT,
            latitude REAL,
            longitude REAL,
            active INTEGER
                CHECK (
                    active IS NULL
                    OR active IN (0, 1)
                ),
            is_published INTEGER
                CHECK (
                    is_published IS NULL
                    OR is_published IN (0, 1)
                )
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_contract002_partners_siret
        ON contract002_partners (siret)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_contract002_partners_siren
        ON contract002_partners (siren)
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_runtime_state (
            contract_name TEXT PRIMARY KEY,
            contract_version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',
            source_instance_id TEXT NOT NULL DEFAULT 'unknown',
            source_ref TEXT,
            refreshed_at TEXT NOT NULL,
            row_count INTEGER NOT NULL
        )
        """
    )

    existing_state_columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(contract_runtime_state)"
        ).fetchall()
    }

    if "status" not in existing_state_columns:
        connection.execute(
            "ALTER TABLE contract_runtime_state "
            "ADD COLUMN status TEXT NOT NULL DEFAULT 'available'"
        )

    if "source_instance_id" not in existing_state_columns:
        connection.execute(
            "ALTER TABLE contract_runtime_state "
            "ADD COLUMN source_instance_id TEXT NOT NULL DEFAULT 'unknown'"
        )

    if "source_ref" not in existing_state_columns:
        connection.execute(
            "ALTER TABLE contract_runtime_state "
            "ADD COLUMN source_ref TEXT"
        )

    connection.execute(
        "DROP VIEW IF EXISTS contract_transaction_context_v1"
    )

    connection.execute(
        "DROP VIEW IF EXISTS "
        "contract_transaction_partner_context_v1"
    )

    connection.execute(
        """
        CREATE VIEW contract_transaction_context_v1 AS
        SELECT
            t.hash AS transaction_id,
            t.amount AS amount_minor,
            t.received_at AS received_at,
            t.type AS native_type,
            t.fn_abi AS native_subtype,
            t.is_sender_external AS is_sender_external,
            t.is_receiver_external AS is_receiver_external,

            (
                SELECT COUNT(*)
                FROM contract001_transaction_partners AS l
                WHERE l.hash = t.hash
                  AND l.side = 'sender'
            ) AS sender_partner_count,

            (
                SELECT COUNT(*)
                FROM contract001_transaction_partners AS l
                WHERE l.hash = t.hash
                  AND l.side = 'receiver'
            ) AS receiver_partner_count

        FROM contract001_transactions AS t
        """
    )

    connection.execute(
        """
        CREATE VIEW
            contract_transaction_partner_context_v1
        AS
        SELECT
            t.hash AS transaction_id,
            t.amount AS amount_minor,
            t.received_at AS received_at,
            t.type AS native_type,
            t.fn_abi AS native_subtype,

            l.side AS side,
            l.partner_id AS partner_id,

            CASE
                WHEN l.side = 'sender'
                THEN t.is_sender_external
                ELSE t.is_receiver_external
            END AS is_external,

            p.name AS partner_name,
            p.is_company AS partner_is_company,
            p.member_type AS partner_member_type,
            p.industry_code AS partner_industry_code,
            p.industry_name AS partner_industry_name,
            p.siret AS partner_siret,
            p.siren AS partner_siren,
            p.legal_activity_code AS
                partner_legal_activity_code,
            p.city AS partner_city,
            p.zip AS partner_zip,
            p.latitude AS partner_latitude,
            p.longitude AS partner_longitude,
            p.active AS partner_active,
            p.is_published AS partner_is_published,

            CASE
                WHEN p.partner_id IS NULL THEN 0
                ELSE 1
            END AS partner_profile_resolved

        FROM contract001_transactions AS t

        JOIN contract001_transaction_partners AS l
          ON l.hash = t.hash

        LEFT JOIN contract002_partners AS p
          ON p.partner_id = l.partner_id
        """
    )


def _nullable_bool(
    value: bool | None,
) -> int | None:
    if value is None:
        return None

    return int(value)


def replace_transaction_snapshot(
    connection: sqlite3.Connection,
    rows,
) -> int:
    """
    Remplace le snapshot transactionnel.

    contract001_transactions :
        un événement financier unique par hash.

    contract001_transaction_partners :
        zéro à N associations administratives par côté.

    Le nombre retourné est le nombre d'événements financiers,
    jamais le nombre de lignes source ni le nombre d'associations.
    """
    events: dict[str, TransactionContractRow] = {}
    event_signatures: dict[str, tuple] = {}
    partner_links: set[tuple[str, str, int]] = set()

    for transaction in rows:
        signature = transaction_event_signature(
            transaction
        )

        previous_signature = event_signatures.get(
            transaction.hash
        )

        if previous_signature is None:
            event_signatures[transaction.hash] = signature
            events[transaction.hash] = transaction
        elif previous_signature != signature:
            raise ValueError(
                "Faits financiers divergents pour le hash "
                f"{transaction.hash!r}."
            )

        if transaction.sender_partner_id is not None:
            partner_links.add(
                (
                    transaction.hash,
                    "sender",
                    transaction.sender_partner_id,
                )
            )

        if transaction.receiver_partner_id is not None:
            partner_links.add(
                (
                    transaction.hash,
                    "receiver",
                    transaction.receiver_partner_id,
                )
            )

    connection.execute(
        "DELETE FROM contract001_transaction_partners"
    )

    connection.execute(
        "DELETE FROM contract001_transactions"
    )

    for transaction in sorted(
        events.values(),
        key=lambda item: (
            item.received_at,
            item.hash,
        ),
    ):
        connection.execute(
            """
            INSERT INTO contract001_transactions (
                hash,
                amount,
                received_at,
                fn_abi,
                type,
                is_sender_external,
                is_receiver_external
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction.hash,
                transaction.amount,
                transaction.received_at,
                transaction.fn_abi,
                transaction.type,
                int(transaction.is_sender_external),
                int(transaction.is_receiver_external),
            ),
        )

    for tx_hash, side, partner_id in sorted(
        partner_links
    ):
        connection.execute(
            """
            INSERT INTO
                contract001_transaction_partners (
                    hash,
                    side,
                    partner_id
                )
            VALUES (?, ?, ?)
            """,
            (
                tx_hash,
                side,
                partner_id,
            ),
        )

    return len(events)


def replace_partner_snapshot(
    connection: sqlite3.Connection,
    rows,
) -> int:
    connection.execute(
        "DELETE FROM contract002_partners"
    )

    count = 0

    for partner in rows:
        connection.execute(
            """
            INSERT INTO contract002_partners (
                partner_id,
                name,
                is_company,
                member_type,
                industry_code,
                industry_name,
                siret,
                siren,
                legal_activity_code,
                city,
                zip,
                latitude,
                longitude,
                active,
                is_published
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                partner.partner_id,
                partner.name,
                _nullable_bool(partner.is_company),
                partner.member_type,
                partner.industry_code,
                partner.industry_name,
                partner.siret,
                partner.siren,
                partner.legal_activity_code,
                partner.city,
                partner.zip,
                partner.latitude,
                partner.longitude,
                _nullable_bool(partner.active),
                _nullable_bool(partner.is_published),
            ),
        )

        count += 1

    return count


def record_contract_state(
    connection: sqlite3.Connection,
    *,
    contract_name: str,
    contract_version: str,
    row_count: int,
    status: str = "available",
    source_instance_id: str,
    source_ref: str | None = None,
) -> None:
    if status not in {
        "available",
        "disabled",
    }:
        raise ValueError(
            f"Statut de contrat invalide: {status!r}"
        )

    if not str(source_instance_id or "").strip():
        raise ValueError(
            "source_instance_id ne peut pas être vide"
        )

    if row_count < 0:
        raise ValueError(
            "row_count ne peut pas être négatif"
        )

    connection.execute(
        """
        INSERT INTO contract_runtime_state (
            contract_name,
            contract_version,
            status,
            source_instance_id,
            source_ref,
            refreshed_at,
            row_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(contract_name) DO UPDATE SET
            contract_version = excluded.contract_version,
            status = excluded.status,
            source_instance_id = excluded.source_instance_id,
            source_ref = excluded.source_ref,
            refreshed_at = excluded.refreshed_at,
            row_count = excluded.row_count
        """,
        (
            contract_name,
            contract_version,
            status,
            source_instance_id,
            source_ref,
            datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat(),
            row_count,
        ),
    )
