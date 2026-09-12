from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, inspect, select

from server.input_contract.schema import (
    REQUIRED_RELATIONS,
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

    def validate_required_relations(self) -> None:
        relations = self.relation_names()
        missing = REQUIRED_RELATIONS - relations

        if missing:
            raise InputContractError(
                "Missing required financial contract relations: "
                + ", ".join(sorted(missing))
            )

    def metadata_row(self) -> dict:
        self.validate_required_relations()

        with self.engine.connect() as conn:
            rows = conn.execute(select(dataset_metadata)).mappings().all()

        if len(rows) != 1:
            raise InputContractError(
                "dataset_metadata must contain exactly one row"
            )

        return dict(rows[0])

    def capabilities(self) -> ContractCapabilities:
        relations = self.relation_names()
        meta = self.metadata_row()

        return ContractCapabilities(
            relations=relations,
            account_state_history=bool(
                meta.get("account_state_history")
                and "account_states" in relations
            ),
            balances=bool(
                meta.get("balances")
                and "balances" in relations
            ),
            account_replacements=bool(
                meta.get("account_replacements")
                and "account_replacements" in relations
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
