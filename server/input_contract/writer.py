from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from sqlalchemy import Engine, delete, insert, inspect as sa_inspect
from sqlalchemy.exc import SQLAlchemyError

from server.input_contract.schema import (
    CAPABILITY_RELATIONS,
    CONTRACT_RELATIONS,
    REQUIRED_RELATIONS,
    SUPPORTED_CONTRACT_VERSIONS,
    account_replacements,
    account_states,
    accounts,
    balances,
    dataset_metadata,
    transactions,
)


class InputContractWriteError(RuntimeError):
    pass


@dataclass(frozen=True)
class FinancialDatasetPayload:
    dataset_metadata: Mapping[str, Any]
    accounts: Sequence[Mapping[str, Any]]
    transactions: Sequence[Mapping[str, Any]]

    # None = capacité absente.
    # []   = capacité présente mais aucune ligne observée.
    account_states: Sequence[Mapping[str, Any]] | None = None
    balances: Sequence[Mapping[str, Any]] | None = None
    account_replacements: Sequence[Mapping[str, Any]] | None = None


def _copy_rows(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    relation_name: str,
) -> list[dict[str, Any]] | None:
    if rows is None:
        return None

    copied: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise InputContractWriteError(
                f"{relation_name}[{index}] doit être un mapping."
            )

        copied.append(dict(row))

    return copied


def _validate_columns(
    relation_name: str,
    rows: list[dict[str, Any]],
) -> None:
    allowed = {
        column.name
        for column in CONTRACT_RELATIONS[relation_name].columns
    }

    for index, row in enumerate(rows):
        unknown = set(row) - allowed

        if unknown:
            raise InputContractWriteError(
                f"{relation_name}[{index}] contient des colonnes "
                "inconnues : "
                + ", ".join(sorted(unknown))
            )


def _validate_payload(
    payload: FinancialDatasetPayload,
) -> dict[str, list[dict[str, Any]] | None]:
    meta = dict(payload.dataset_metadata)

    for field in (
        "dataset_id",
        "contract_version",
        "source_system",
    ):
        value = meta.get(field)

        if value is None or (
            isinstance(value, str) and not value.strip()
        ):
            raise InputContractWriteError(
                f"dataset_metadata.{field} doit être renseigné."
            )

    if (
        meta["contract_version"]
        not in SUPPORTED_CONTRACT_VERSIONS
    ):
        raise InputContractWriteError(
            "Version INPUT001 non supportée : "
            f"{meta['contract_version']!r}"
        )

    for capability in CAPABILITY_RELATIONS:
        if capability not in meta:
            raise InputContractWriteError(
                f"dataset_metadata.{capability} doit être explicite."
            )

        if not isinstance(meta[capability], bool):
            raise InputContractWriteError(
                f"dataset_metadata.{capability} doit être booléen."
            )

    relation_rows = {
        "accounts": _copy_rows(
            payload.accounts,
            relation_name="accounts",
        ),
        "transactions": _copy_rows(
            payload.transactions,
            relation_name="transactions",
        ),
        "account_states": _copy_rows(
            payload.account_states,
            relation_name="account_states",
        ),
        "balances": _copy_rows(
            payload.balances,
            relation_name="balances",
        ),
        "account_replacements": _copy_rows(
            payload.account_replacements,
            relation_name="account_replacements",
        ),
    }

    for capability, relation_name in CAPABILITY_RELATIONS.items():
        relation_present = relation_rows[relation_name] is not None

        if meta[capability] != relation_present:
            raise InputContractWriteError(
                f"Capacité {capability!r} incohérente avec "
                f"la relation {relation_name!r}."
            )

    _validate_columns("dataset_metadata", [meta])

    for relation_name, rows in relation_rows.items():
        if rows is not None:
            _validate_columns(relation_name, rows)

    source_system = meta["source_system"]

    account_rows = relation_rows["accounts"] or []
    account_ids: set[str] = set()

    for index, row in enumerate(account_rows):
        account_id = row.get("account_id")

        if not isinstance(account_id, str) or not account_id.strip():
            raise InputContractWriteError(
                f"accounts[{index}].account_id invalide."
            )

        account_ids.add(account_id)

        if row.get("source_system") != source_system:
            raise InputContractWriteError(
                f"accounts[{index}].source_system incohérent "
                "avec dataset_metadata.source_system."
            )

    for index, row in enumerate(
        relation_rows["transactions"] or []
    ):
        for field in (
            "source_account_id",
            "destination_account_id",
        ):
            account_id = row.get(field)

            if (
                account_id is not None
                and account_id not in account_ids
            ):
                raise InputContractWriteError(
                    f"transactions[{index}].{field} référence "
                    f"un compte absent : {account_id!r}"
                )

    for relation_name in (
        "account_states",
        "balances",
    ):
        for index, row in enumerate(
            relation_rows[relation_name] or []
        ):
            account_id = row.get("account_id")

            if account_id not in account_ids:
                raise InputContractWriteError(
                    f"{relation_name}[{index}] référence "
                    f"un compte absent : {account_id!r}"
                )

            if (
                relation_name == "balances"
                and row.get("source_system") != source_system
            ):
                raise InputContractWriteError(
                    f"balances[{index}].source_system incohérent "
                    "avec dataset_metadata.source_system."
                )

    for index, row in enumerate(
        relation_rows["account_replacements"] or []
    ):
        for field in (
            "old_account_id",
            "new_account_id",
        ):
            account_id = row.get(field)

            if account_id not in account_ids:
                raise InputContractWriteError(
                    f"account_replacements[{index}].{field} "
                    f"référence un compte absent : {account_id!r}"
                )

    relation_rows["dataset_metadata"] = [meta]

    return relation_rows


def materialize_financial_dataset(
    engine: Engine,
    payload: FinancialDatasetPayload,
) -> None:
    """
    Remplace atomiquement le contenu INPUT001 matérialisé.

    Seules les relations du contrat sont touchées.
    Les tables applicatives étrangères à INPUT001 sont ignorées.
    """
    relation_rows = _validate_payload(payload)

    inspector = sa_inspect(engine)
    contract_views = (
        set(inspector.get_view_names())
        & set(CONTRACT_RELATIONS)
    )

    if contract_views:
        raise InputContractWriteError(
            "Le writer matérialisé ne peut pas remplacer "
            "des vues INPUT001 : "
            + ", ".join(sorted(contract_views))
        )

    required_to_create = set(REQUIRED_RELATIONS)

    optional_to_create = {
        relation_name
        for relation_name in CAPABILITY_RELATIONS.values()
        if relation_rows[relation_name] is not None
    }

    to_create = required_to_create | optional_to_create

    try:
        with engine.begin() as conn:
            for relation_name in sorted(to_create):
                CONTRACT_RELATIONS[relation_name].create(
                    conn,
                    checkfirst=True,
                )

            existing_tables = set(
                sa_inspect(conn).get_table_names()
            )

            # Nettoyage de toute ancienne matérialisation INPUT001.
            for table in (
                account_replacements,
                balances,
                account_states,
                transactions,
                accounts,
                dataset_metadata,
            ):
                if table.name in existing_tables:
                    conn.execute(delete(table))

            # Les comptes précèdent les relations qui les référencent.
            if relation_rows["accounts"]:
                conn.execute(
                    insert(accounts),
                    relation_rows["accounts"],
                )

            if relation_rows["transactions"]:
                conn.execute(
                    insert(transactions),
                    relation_rows["transactions"],
                )

            if relation_rows["account_states"] is not None:
                rows = relation_rows["account_states"]
                if rows:
                    conn.execute(insert(account_states), rows)

            if relation_rows["balances"] is not None:
                rows = relation_rows["balances"]
                if rows:
                    conn.execute(insert(balances), rows)

            if relation_rows["account_replacements"] is not None:
                rows = relation_rows["account_replacements"]
                if rows:
                    conn.execute(
                        insert(account_replacements),
                        rows,
                    )

            conn.execute(
                insert(dataset_metadata),
                relation_rows["dataset_metadata"],
            )

    except SQLAlchemyError as exc:
        raise InputContractWriteError(
            "Échec de matérialisation du dataset INPUT001."
        ) from exc
