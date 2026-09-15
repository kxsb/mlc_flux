from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    TypeDecorator,
)


CONTRACT_VERSION = "financial-core-v0.1"


class UTCDateTime(TypeDecorator):
    """Portable UTC instant for SQLite and timezone-aware SQL engines."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(DateTime(timezone=dialect.name != "sqlite"))

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Financial Core datetime values must be timezone-aware")
        value = value.astimezone(UTC)
        if dialect.name == "sqlite":
            return value.replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


metadata = MetaData()


datasets = Table(
    "financial_core_datasets",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("contract_version", String(64), nullable=False),
    Column("source_system", String(128), nullable=False),
    Column("source_instance_id", Text, nullable=False),
    Column("current_publication_id", Text),
    Column("created_at", UTCDateTime(), nullable=False),
    Column("updated_at", UTCDateTime(), nullable=False),
)

publications = Table(
    "financial_core_publications",
    metadata,
    Column("publication_id", Text, primary_key=True),
    Column("dataset_id", Text, nullable=False),
    Column("created_at", UTCDateTime(), nullable=False),
    Column("coverage_from", UTCDateTime()),
    Column("coverage_to", UTCDateTime()),
    Column("source_cursor", Text),
    Column("source_snapshot_ref", Text),
    Column("adapter_name", String(128), nullable=False),
    Column("adapter_version", String(128), nullable=False),
    Column("content_hash", Text),
    Column("status", String(32), nullable=False),
)
Index("ix_financial_core_publications_dataset", publications.c.dataset_id)

publication_capabilities = Table(
    "financial_core_publication_capabilities",
    metadata,
    Column("publication_id", Text, primary_key=True),
    Column("capability", String(128), primary_key=True),
    Column("status", String(32), nullable=False),
    Column("detail_json", Text),
)

accounts = Table(
    "financial_core_accounts",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("account_id", Text, primary_key=True),
    Column("publication_id", Text, nullable=False),
    Column("native_account_id", Text),
    Column("native_account_number", Text),
    Column("native_account_type", Text),
    Column("native_account_kind", Text),
    Column("native_status", Text),
    Column("display_label", Text),
    Column("native_owner_id", Text),
    Column("native_attributes_json", Text),
    Column("provenance_ref", Text),
    Column("provenance_hash", Text),
)
Index("ix_financial_core_accounts_publication", accounts.c.publication_id)

financial_events = Table(
    "financial_core_events",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("event_id", Text, primary_key=True),
    Column("publication_id", Text, nullable=False),
    Column("native_event_id", Text),
    Column("native_event_number", Text),
    Column("event_kind", String(128), nullable=False),
    Column("native_event_type", Text),
    Column("native_event_subtype", Text),
    Column("native_method", Text),
    Column("native_status", Text),
    Column("execution_state", String(32), nullable=False),
    Column("time_precision", String(16), nullable=False),
    Column("occurred_at", UTCDateTime()),
    Column("occurred_date", String(10)),
    Column("business_timezone", String(128)),
    Column("native_amount_minor", BigInteger),
    Column("native_unit_code", String(64)),
    Column("native_unit_exponent", Integer),
    Column("native_monetary_dimension", String(128)),
    Column("native_attributes_json", Text),
    Column("provenance_ref", Text),
    Column("provenance_hash", Text),
)
Index("ix_financial_core_events_publication", financial_events.c.publication_id)
Index("ix_financial_core_events_occurred_at", financial_events.c.occurred_at)

account_effects = Table(
    "financial_core_account_effects",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("effect_id", Text, primary_key=True),
    Column("publication_id", Text, nullable=False),
    Column("event_id", Text, nullable=False),
    Column("account_id", Text, nullable=False),
    Column("amount_minor", BigInteger, nullable=False),
    Column("unit_code", String(64), nullable=False),
    Column("unit_exponent", Integer, nullable=False),
    Column("monetary_dimension", String(128), nullable=False),
    Column("origin", String(64), nullable=False),
    Column("native_effect_id", Text),
    Column("native_attributes_json", Text),
    Column("provenance_ref", Text),
    Column("provenance_hash", Text),
)
Index("ix_financial_core_effects_event", account_effects.c.dataset_id, account_effects.c.event_id)
Index("ix_financial_core_effects_account", account_effects.c.dataset_id, account_effects.c.account_id)

actors = Table(
    "financial_core_actors",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("actor_id", Text, primary_key=True),
    Column("publication_id", Text, nullable=False),
    Column("source_system", String(128), nullable=False),
    Column("native_actor_id", Text),
    Column("native_actor_kind", Text),
    Column("display_label", Text),
    Column("native_attributes_json", Text),
    Column("provenance_ref", Text),
    Column("provenance_hash", Text),
)

identity_links = Table(
    "financial_core_identity_links",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("identity_link_id", Text, primary_key=True),
    Column("publication_id", Text, nullable=False),
    Column("subject_kind", String(64), nullable=False),
    Column("subject_id", Text, nullable=False),
    Column("target_kind", String(64), nullable=False),
    Column("target_id", Text, nullable=False),
    Column("link_kind", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("confidence", String(32)),
    Column("source_system", String(128)),
    Column("valid_from", UTCDateTime()),
    Column("valid_to", UTCDateTime()),
    Column("evidence_json", Text),
)

balance_observations = Table(
    "financial_core_balance_observations",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("observation_id", Text, primary_key=True),
    Column("publication_id", Text, nullable=False),
    Column("account_id", Text, nullable=False),
    Column("time_precision", String(16), nullable=False),
    Column("observed_at", UTCDateTime()),
    Column("observed_date", String(10)),
    Column("business_timezone", String(128)),
    Column("amount_minor", BigInteger, nullable=False),
    Column("unit_code", String(64), nullable=False),
    Column("unit_exponent", Integer, nullable=False),
    Column("monetary_dimension", String(128), nullable=False),
    Column("balance_component", String(128), nullable=False),
    Column("source_system", String(128), nullable=False),
    Column("provenance_ref", Text),
    Column("provenance_hash", Text),
)

monetary_observations = Table(
    "financial_core_monetary_observations",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("observation_id", Text, primary_key=True),
    Column("publication_id", Text, nullable=False),
    Column("scope_kind", String(64), nullable=False),
    Column("scope_id", Text),
    Column("metric_kind", String(128), nullable=False),
    Column("time_precision", String(16), nullable=False),
    Column("observed_at", UTCDateTime()),
    Column("observed_date", String(10)),
    Column("business_timezone", String(128)),
    Column("amount_minor", BigInteger, nullable=False),
    Column("unit_code", String(64), nullable=False),
    Column("unit_exponent", Integer, nullable=False),
    Column("monetary_dimension", String(128), nullable=False),
    Column("source_system", String(128), nullable=False),
    Column("basis", Text),
    Column("provenance_ref", Text),
    Column("provenance_hash", Text),
)

account_replacements = Table(
    "financial_core_account_replacements",
    metadata,
    Column("dataset_id", Text, primary_key=True),
    Column("replacement_id", Text, primary_key=True),
    Column("publication_id", Text, nullable=False),
    Column("old_account_id", Text, nullable=False),
    Column("new_account_id", Text, nullable=False),
    Column("time_precision", String(16), nullable=False),
    Column("effective_at", UTCDateTime()),
    Column("effective_date", String(10)),
    Column("business_timezone", String(128)),
    Column("native_reason", Text),
    Column("provenance_ref", Text),
)

MATERIALIZED_RELATIONS = {
    table.name: table
    for table in (
        accounts,
        financial_events,
        account_effects,
        actors,
        identity_links,
        balance_observations,
        monetary_observations,
        account_replacements,
    )
}

ALL_RELATIONS = {
    table.name: table
    for table in (
        datasets,
        publications,
        publication_capabilities,
        *MATERIALIZED_RELATIONS.values(),
    )
}
