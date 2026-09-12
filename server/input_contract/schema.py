from __future__ import annotations

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
)

metadata = MetaData()

transactions = Table(
    "transactions",
    metadata,
    Column("transaction_id", Text, primary_key=True),
    Column("native_transaction_number", Text),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("source_account_id", Text),
    Column("destination_account_id", Text),
    Column("amount_minor", BigInteger, nullable=False),
    Column("native_currency_id", Text),
    Column("currency_code", String(64), nullable=False),
    Column("currency_exponent", Integer, nullable=False),
    Column("native_transaction_type", Text),
    Column("native_transaction_label", Text),
    Column("native_transaction_group", Text),
)

accounts = Table(
    "accounts",
    metadata,
    Column("account_id", Text, primary_key=True),
    Column("native_account_number", Text),
    Column("native_account_type", Text),
    Column("native_status", Text),
    Column("display_label", Text),
    Column("native_owner_id", Text),
    Column("source_system", String(64), nullable=False),
)

account_states = Table(
    "account_states",
    metadata,
    Column("account_id", Text, nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("valid_to", DateTime(timezone=True)),
    Column("native_account_type", Text),
    Column("native_status", Text),
)

dataset_metadata = Table(
    "dataset_metadata",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("contract_version", String(64), nullable=False),
    Column("source_system", String(64), nullable=False),
    Column("coverage_from", DateTime(timezone=True)),
    Column("coverage_to", DateTime(timezone=True)),
    Column("snapshot_ref", Text),
    Column("account_state_history", Boolean, nullable=False, default=False),
    Column("balances", Boolean, nullable=False, default=False),
    Column("account_replacements", Boolean, nullable=False, default=False),
)

balances = Table(
    "balances",
    metadata,
    Column("account_id", Text, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
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
    Column("effective_at", DateTime(timezone=True), nullable=False),
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
