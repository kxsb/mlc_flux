from __future__ import annotations

import json
import os
from dataclasses import dataclass

from server.contract_store import (
    init_contract_tables,
    record_contract_state,
    replace_partner_snapshot,
    replace_transaction_snapshot,
)
from server.contracts.partners_v1 import (
    CONTRACT_VERSION as PARTNERS_VERSION,
)
from server.contracts.transactions_v1 import (
    CONTRACT_VERSION as TRANSACTIONS_VERSION,
)
from server.database import get_connection
from server.providers.normalized_transactions_postgres import (
    NormalizedTransactionsPostgresSource,
)
from server.providers.odoo_partners_postgres import (
    OdooPartnersPostgresSource,
)


class ContractRuntimeConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContractRuntimeConfig:
    postgres_dsn: str
    transactions_relation: str
    source_instance_id: str
    transactions_schema: str = "public"
    partners_provider: str = "disabled"
    partners_postgres_dsn: str = ""

    @classmethod
    def from_env(cls) -> "ContractRuntimeConfig":
        postgres_dsn = str(
            os.getenv("MLCFLUX_CONTRACT_PG_DSN") or ""
        ).strip()

        transactions_relation = str(
            os.getenv("MLCFLUX_TRANSACTIONS_RELATION") or ""
        ).strip()

        source_instance_id = str(
            os.getenv("MLCFLUX_CONTRACT_SOURCE_INSTANCE_ID")
            or ""
        ).strip()

        transactions_schema = str(
            os.getenv("MLCFLUX_TRANSACTIONS_SCHEMA")
            or "public"
        ).strip()

        partners_provider = str(
            os.getenv("MLCFLUX_PARTNERS_PROVIDER")
            or "disabled"
        ).strip().lower()

        partners_postgres_dsn = str(
            os.getenv("MLCFLUX_PARTNERS_PG_DSN")
            or postgres_dsn
        ).strip()

        if not postgres_dsn:
            raise ContractRuntimeConfigError(
                "MLCFLUX_CONTRACT_PG_DSN est requis."
            )

        if not transactions_relation:
            raise ContractRuntimeConfigError(
                "MLCFLUX_TRANSACTIONS_RELATION est requis."
            )

        if not source_instance_id:
            raise ContractRuntimeConfigError(
                "MLCFLUX_CONTRACT_SOURCE_INSTANCE_ID est requis."
            )

        if not transactions_schema:
            raise ContractRuntimeConfigError(
                "MLCFLUX_TRANSACTIONS_SCHEMA ne peut pas être vide."
            )

        if partners_provider not in {
            "disabled",
            "odoo_postgres",
        }:
            raise ContractRuntimeConfigError(
                "MLCFLUX_PARTNERS_PROVIDER doit valoir "
                "disabled ou odoo_postgres."
            )

        if (
            partners_provider == "odoo_postgres"
            and not partners_postgres_dsn
        ):
            raise ContractRuntimeConfigError(
                "MLCFLUX_PARTNERS_PG_DSN est requis "
                "pour odoo_postgres."
            )

        return cls(
            postgres_dsn=postgres_dsn,
            transactions_relation=transactions_relation,
            source_instance_id=source_instance_id,
            transactions_schema=transactions_schema,
            partners_provider=partners_provider,
            partners_postgres_dsn=partners_postgres_dsn,
        )


def _referenced_partner_ids(transactions) -> set[int]:
    partner_ids: set[int] = set()

    for transaction in transactions:
        if transaction.sender_partner_id is not None:
            partner_ids.add(
                transaction.sender_partner_id
            )

        if transaction.receiver_partner_id is not None:
            partner_ids.add(
                transaction.receiver_partner_id
            )

    return partner_ids


def _filter_referenced_partners(
    transactions,
    partners,
):
    referenced_partner_ids = (
        _referenced_partner_ids(transactions)
    )

    return tuple(
        partner
        for partner in partners
        if partner.partner_id
        in referenced_partner_ids
    )


def run_contract_sync(
    config: ContractRuntimeConfig | None = None,
) -> dict[str, object]:
    """
    Matérialise les contrats normalisés dans le SQLite de l'instance.

    Ce pipeline est indépendant du pipeline legacy Cyclos/INPUT001.
    Il n'alimente encore aucune route analytique de production.
    """
    config = config or ContractRuntimeConfig.from_env()

    transactions = NormalizedTransactionsPostgresSource(
        dsn=config.postgres_dsn,
        relation=config.transactions_relation,
        schema=config.transactions_schema,
    ).fetch_transactions()

    partners = None

    if config.partners_provider == "odoo_postgres":
        referenced_partner_ids = (
            _referenced_partner_ids(
                transactions
            )
        )

        source_partners = (
            OdooPartnersPostgresSource(
                dsn=config.partners_postgres_dsn,
            ).fetch_partners(
                partner_ids=referenced_partner_ids,
            )
        )

        partners = _filter_referenced_partners(
            transactions,
            source_partners,
        )

    connection = get_connection()

    try:
        init_contract_tables(connection)

        with connection:
            transaction_count = (
                replace_transaction_snapshot(
                    connection,
                    transactions,
                )
            )

            record_contract_state(
                connection,
                contract_name="transactions",
                contract_version=TRANSACTIONS_VERSION,
                row_count=transaction_count,
                status="available",
                source_instance_id=config.source_instance_id,
                source_ref=(
                    "postgresql:"
                    f"{config.transactions_schema}."
                    f"{config.transactions_relation}"
                ),
            )

            if partners is not None:
                partner_count = replace_partner_snapshot(
                    connection,
                    partners,
                )

                record_contract_state(
                    connection,
                    contract_name="partners",
                    contract_version=PARTNERS_VERSION,
                    row_count=partner_count,
                    status="available",
                    source_instance_id=config.source_instance_id,
                    source_ref=config.partners_provider,
                )
            else:
                partner_count = replace_partner_snapshot(
                    connection,
                    (),
                )

                record_contract_state(
                    connection,
                    contract_name="partners",
                    contract_version=PARTNERS_VERSION,
                    row_count=0,
                    status="disabled",
                    source_instance_id=config.source_instance_id,
                    source_ref=None,
                )

        return {
            "status": "ok",
            "transactions": transaction_count,
            "partners": partner_count,
            "partners_provider": (
                config.partners_provider
            ),
        }

    finally:
        connection.close()


def main() -> int:
    result = run_contract_sync()

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
