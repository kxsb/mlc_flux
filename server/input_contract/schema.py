from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    TypeDecorator,
)

class UTCDateTime(TypeDecorator):
    """
    Instant UTC portable entre SQLite et les moteurs avec timezone native.

    - toute écriture doit fournir un datetime timezone-aware ;
    - la valeur est normalisée en UTC avant stockage ;
    - SQLite stocke un DATETIME naïf représentant explicitement UTC ;
    - toute lecture restitue un datetime timezone-aware en UTC.
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(
            DateTime(timezone=dialect.name != "sqlite")
        )

    def process_bind_param(
        self,
        value: datetime | None,
        dialect,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "INPUT001 datetime values must be timezone-aware"
            )

        normalized = value.astimezone(UTC)

        if dialect.name == "sqlite":
            return normalized.replace(tzinfo=None)

        return normalized

    def process_result_value(
        self,
        value: datetime | None,
        dialect,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)


metadata = MetaData()

transactions = Table(
    "transactions",
    metadata,
    Column("transaction_id", Text, primary_key=True),
    Column("native_transaction_number", Text),
    Column("occurred_at", UTCDateTime(), nullable=False),
    Column("source_account_id", Text),
    Column("destination_account_id", Text),
    Column("amount_minor", BigInteger, nullable=False),
    Column("native_currency_id", Text),
    Column("currency_code", String(64), nullable=False),
    Column("currency_exponent", Integer, nullable=False),
    Column("native_transaction_type", Text),
    Column("native_transaction_label", Text),
    Column("native_transaction_group", Text),
    Column("native_transaction_description", Text),
)

accounts = Table(
    "accounts",
    metadata,
    Column("account_id", Text, primary_key=True),
    Column("native_account_number", Text),
    Column("native_account_type", Text),
    Column("native_account_kind", Text),
    Column("native_account_type_label", Text),
    Column("native_status", Text),
    Column("display_label", Text),
    Column("native_owner_id", Text),
    Column("source_system", String(64), nullable=False),
)

account_states = Table(
    "account_states",
    metadata,
    Column("account_id", Text, nullable=False),
    Column("valid_from", UTCDateTime(), nullable=False),
    Column("valid_to", UTCDateTime()),
    Column("native_account_type", Text),
    Column("native_status", Text),
)

dataset_metadata = Table(
    "dataset_metadata",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("contract_version", String(64), nullable=False),
    Column("source_system", String(64), nullable=False),
    Column("coverage_from", UTCDateTime()),
    Column("coverage_to", UTCDateTime()),
    Column("snapshot_ref", Text),
    Column("account_state_history", Boolean, nullable=False, default=False),
    Column("balances", Boolean, nullable=False, default=False),
    Column("account_replacements", Boolean, nullable=False, default=False),
)

balances = Table(
    "balances",
    metadata,
    Column("account_id", Text, nullable=False),
    Column("observed_at", UTCDateTime(), nullable=False),
    Column("balance_component", Text, nullable=False),
    Column("amount_minor", BigInteger, nullable=False),
    Column("currency_code", String(64), nullable=False),
    Column("currency_exponent", Integer, nullable=False),
    Column("source_system", String(64), nullable=False),
)

account_replacements = Table(
    "account_replacements",
    metadata,
    Column("old_account_id", Text, nullable=False),
    Column("new_account_id", Text, nullable=False),
    Column("effective_at", UTCDateTime(), nullable=False),
    Column("native_reason", Text),
)

REQUIRED_RELATIONS = {
    "transactions",
    "accounts",
    "dataset_metadata",
}

OPTIONAL_RELATIONS = {
    "account_states",
    "balances",
    "account_replacements",
}

SUPPORTED_CONTRACT_VERSIONS = frozenset({
    "input001-v0.1",
})

CONTRACT_RELATIONS = {
    table.name: table
    for table in (
        transactions,
        accounts,
        dataset_metadata,
        account_states,
        balances,
        account_replacements,
    )
}

CONTRACT_RELATION_COLUMNS = {
    name: frozenset(column.name for column in table.columns)
    for name, table in CONTRACT_RELATIONS.items()
}

CAPABILITY_RELATIONS = {
    "account_state_history": "account_states",
    "balances": "balances",
    "account_replacements": "account_replacements",
}
