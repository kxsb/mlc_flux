from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, inspect, select

from server.input_contract.schema import (
    CAPABILITY_RELATIONS,
    CONTRACT_RELATION_COLUMNS,
    OPTIONAL_RELATIONS,
    REQUIRED_RELATIONS,
    SUPPORTED_CONTRACT_VERSIONS,
    accounts,
    dataset_metadata,
    transactions,
)


class InputContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContractCapabilities:
    relations: frozenset[str]
    account_state_history: bool
    balances: bool
    account_replacements: bool


class FinancialContractReader:
    def __init__(self, engine: Engine):
        self.engine = engine

    def relation_names(self) -> frozenset[str]:
        inspector = inspect(self.engine)
        names = set(inspector.get_table_names())
        names.update(inspector.get_view_names())
        return frozenset(names)

    def _relation_columns(self, relation_name: str) -> frozenset[str]:
        inspector = inspect(self.engine)

        try:
            columns = inspector.get_columns(relation_name)
        except Exception as exc:
            raise InputContractError(
                f"Unable to inspect financial contract relation "
                f"{relation_name!r}"
            ) from exc

        return frozenset(column["name"] for column in columns)

    def _validate_relation_columns(
        self,
        relation_name: str,
    ) -> None:
        expected = CONTRACT_RELATION_COLUMNS[relation_name]
        actual = self._relation_columns(relation_name)
        missing = expected - actual

        if missing:
            raise InputContractError(
                f"Financial contract relation {relation_name!r} "
                "is missing columns: "
                + ", ".join(sorted(missing))
            )

    def validate_required_relations(self) -> None:
        relations = self.relation_names()
        missing = REQUIRED_RELATIONS - relations

        if missing:
            raise InputContractError(
                "Missing required financial contract relations: "
                + ", ".join(sorted(missing))
            )

        relations_to_validate = REQUIRED_RELATIONS | (
            OPTIONAL_RELATIONS & relations
        )

        for relation_name in sorted(relations_to_validate):
            self._validate_relation_columns(relation_name)

    def metadata_row(self) -> dict:
        self.validate_required_relations()

        with self.engine.connect() as conn:
            rows = conn.execute(select(dataset_metadata)).mappings().all()

        if len(rows) != 1:
            raise InputContractError(
                "dataset_metadata must contain exactly one row"
            )

        meta = dict(rows[0])

        for field in (
            "dataset_id",
            "contract_version",
            "source_system",
        ):
            value = meta.get(field)

            if value is None or (
                isinstance(value, str) and not value.strip()
            ):
                raise InputContractError(
                    f"dataset_metadata.{field} must be populated"
                )

        version = meta["contract_version"]
        if version not in SUPPORTED_CONTRACT_VERSIONS:
            raise InputContractError(
                "Unsupported financial contract version: "
                f"{version!r}"
            )

        relations = self.relation_names()

        for capability, relation_name in CAPABILITY_RELATIONS.items():
            if meta.get(capability) and relation_name not in relations:
                raise InputContractError(
                    f"dataset_metadata declares capability "
                    f"{capability!r}, but relation "
                    f"{relation_name!r} is missing"
                )

        return meta

    def capabilities(self) -> ContractCapabilities:
        relations = self.relation_names()
        meta = self.metadata_row()

        return ContractCapabilities(
            relations=relations,
            account_state_history=bool(
                meta.get("account_state_history")
            ),
            balances=bool(meta.get("balances")),
            account_replacements=bool(
                meta.get("account_replacements")
            ),
        )

    def fetch_accounts(self) -> list[dict]:
        self.validate_required_relations()

        with self.engine.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    select(accounts).order_by(accounts.c.account_id)
                ).mappings()
            ]

    def fetch_transactions(self) -> list[dict]:
        self.validate_required_relations()

        with self.engine.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    select(transactions).order_by(
                        transactions.c.transaction_id
                    )
                ).mappings()
            ]
