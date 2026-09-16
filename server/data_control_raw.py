from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from server.sync_contracts import ContractRuntimeConfig


RAW_PREVIEW_LIMIT = 20


TRANSACTION_COLUMNS = {
    "transaction.amount": (
        "hash",
        "amount",
    ),
    "transaction.received_at": (
        "hash",
        "received_at",
    ),
    "transaction.sender_partner_id": (
        "hash",
        "sender_partner_id",
    ),
    "transaction.receiver_partner_id": (
        "hash",
        "receiver_partner_id",
    ),
    "transaction.type": (
        "hash",
        "type",
    ),
    "transaction.fn_abi": (
        "hash",
        "fn_abi",
    ),
    "transaction.hash": (
        "hash",
    ),
    "transaction.external_flags": (
        "hash",
        "is_sender_external",
        "is_receiver_external",
    ),
}


PARTNER_COLUMNS = {
    "partner.name": (
        "partner_id",
        "name",
    ),
    "partner.actor_family": (
        "partner_id",
        "is_company",
        "member_type_raw",
    ),
    "partner.industry": (
        "partner_id",
        "industry_id",
        "industry_name_raw",
        "industry_full_name_raw",
    ),
    "partner.zip": (
        "partner_id",
        "zip",
    ),
    "partner.coordinates": (
        "partner_id",
        "partner_latitude",
        "partner_longitude",
    ),
    "partner.city": (
        "partner_id",
        "city",
    ),
    "partner.member_type": (
        "partner_id",
        "member_type_id",
        "member_type_raw",
    ),
    "partner.active": (
        "partner_id",
        "active",
    ),
    "partner.is_published": (
        "partner_id",
        "is_published",
    ),
    "partner.legal_activity_code": (
        "partner_id",
        "legal_activity_code",
    ),
    "partner.siret": (
        "partner_id",
        "siret",
    ),
    "partner.siren": (
        "partner_id",
        "siren",
    ),
}


PARTNER_WHERE = {
    "partner.name": "p.name IS NOT NULL",
    "partner.actor_family": (
        "(p.is_company IS NOT NULL OR p.member_type_id IS NOT NULL)"
    ),
    "partner.industry": "p.industry_id IS NOT NULL",
    "partner.zip": "NULLIF(TRIM(p.zip), '') IS NOT NULL",
    "partner.coordinates": (
        "(p.partner_latitude IS NOT NULL "
        "OR p.partner_longitude IS NOT NULL)"
    ),
    "partner.city": "NULLIF(TRIM(p.city), '') IS NOT NULL",
    "partner.member_type": "p.member_type_id IS NOT NULL",
    "partner.active": "TRUE",
    "partner.is_published": "TRUE",
    "partner.legal_activity_code": (
        "NULLIF(TRIM(p.legal_activity_code), '') IS NOT NULL"
    ),
    "partner.siret": "NULLIF(TRIM(p.siret), '') IS NOT NULL",
    "partner.siren": "NULLIF(TRIM(p.siren), '') IS NOT NULL",
}


def available_raw_keys() -> frozenset[str]:
    return frozenset(
        set(TRANSACTION_COLUMNS)
        | set(PARTNER_COLUMNS)
    )


def _json_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): _json_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def _serialize_rows(rows) -> list[dict[str, Any]]:
    return [
        {
            str(key): _json_value(value)
            for key, value in dict(row).items()
        }
        for row in rows
    ]



def _epoch_seconds_to_utc(value: Any) -> str | None:
    """
    Rend lisible un timestamp Unix exprimé en secondes.

    La valeur PostgreSQL brute reste également exposée
    dans l'aperçu afin de permettre le contrôle visuel.
    """
    if value is None:
        return None

    try:
        timestamp = float(value)
        instant = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return None

    return instant.strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def _transaction_preview(
    key: str,
    config: ContractRuntimeConfig,
) -> dict[str, Any]:
    columns = TRANSACTION_COLUMNS[key]

    query_columns = list(columns)

    # received_at sert uniquement au tri des aperçus.
    # Il ne doit pas nécessairement apparaître dans le tableau affiché.
    if "received_at" not in query_columns:
        query_columns.append("received_at")

    if "hash" not in query_columns:
        query_columns.append("hash")

    selected_columns = sql.SQL(", ").join(
        sql.Identifier(column)
        for column in query_columns
    )

    query = sql.SQL(
        """
        SELECT DISTINCT {columns}
        FROM {schema}.{relation}
        ORDER BY received_at DESC, hash DESC
        LIMIT %s
        """
    ).format(
        columns=selected_columns,
        schema=sql.Identifier(config.transactions_schema),
        relation=sql.Identifier(config.transactions_relation),
    )

    with psycopg.connect(
        config.postgres_dsn,
        autocommit=False,
        row_factory=dict_row,
    ) as connection:
        with connection.transaction():
            connection.execute(
                "SET TRANSACTION READ ONLY"
            )

            rows = connection.execute(
                query,
                (RAW_PREVIEW_LIMIT,),
            ).fetchall()

    serialized_rows = _serialize_rows(rows)
    display_columns = list(columns)

    # On retire les colonnes techniques ajoutées uniquement pour le tri.
    display_rows = [
        {
            column: row.get(column)
            for column in display_columns
        }
        for row in serialized_rows
    ]

    if key == "transaction.received_at":
        display_columns = [
            "hash",
            "received_at_brut",
            "date_heure_utc",
        ]

        display_rows = [
            {
                "hash": row.get("hash"),
                "received_at_brut": row.get("received_at"),
                "date_heure_utc": _epoch_seconds_to_utc(
                    row.get("received_at")
                ),
            }
            for row in serialized_rows
        ]

    return {
        "key": key,
        "source": (
            f"{config.transactions_schema}."
            f"{config.transactions_relation}"
        ),
        "source_kind": "PostgreSQL · relation transactions",
        "columns": display_columns,
        "rows": display_rows,
        "limit": RAW_PREVIEW_LIMIT,
    }


def _partner_preview(
    key: str,
    config: ContractRuntimeConfig,
) -> dict[str, Any]:
    columns = PARTNER_COLUMNS[key]
    where_clause = PARTNER_WHERE[key]

    query = f"""
        SELECT
            p.id AS partner_id,
            p.name AS name,
            p.is_company AS is_company,
            p.member_type_id AS member_type_id,
            mt.name AS member_type_raw,
            p.industry_id AS industry_id,
            i.name AS industry_name_raw,
            i.full_name AS industry_full_name_raw,
            p.siret AS siret,
            p.siren AS siren,
            p.legal_activity_code AS legal_activity_code,
            p.city AS city,
            p.zip AS zip,
            p.partner_latitude AS partner_latitude,
            p.partner_longitude AS partner_longitude,
            p.active AS active,
            p.is_published AS is_published
        FROM public.res_partner AS p
        LEFT JOIN public.member_type AS mt
            ON mt.id = p.member_type_id
        LEFT JOIN public.res_partner_industry AS i
            ON i.id = p.industry_id
        WHERE {where_clause}
        ORDER BY p.id DESC
        LIMIT %s
    """

    with psycopg.connect(
        config.partners_postgres_dsn,
        autocommit=False,
        row_factory=dict_row,
    ) as connection:
        with connection.transaction():
            connection.execute(
                "SET TRANSACTION READ ONLY"
            )

            source_rows = connection.execute(
                query,
                (RAW_PREVIEW_LIMIT,),
            ).fetchall()

    rows = []

    for source_row in source_rows:
        row = dict(source_row)

        rows.append({
            column: _json_value(row.get(column))
            for column in columns
        })

    return {
        "key": key,
        "source": (
            "public.res_partner"
            " + public.member_type"
            " + public.res_partner_industry"
        ),
        "source_kind": "PostgreSQL · Odoo natif",
        "columns": list(columns),
        "rows": rows,
        "limit": RAW_PREVIEW_LIMIT,
    }


def fetch_raw_preview(key: str) -> dict[str, Any]:
    if key not in available_raw_keys():
        raise KeyError(key)

    config = ContractRuntimeConfig.from_env()

    if key in TRANSACTION_COLUMNS:
        return _transaction_preview(
            key,
            config,
        )

    return _partner_preview(
        key,
        config,
    )
