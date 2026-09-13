from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import (
    Column,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete,
    insert,
    inspect as sa_inspect,
    select,
    update,
)

from server.input_contract.schema import (
    CONTRACT_RELATION_COLUMNS,
    CONTRACT_RELATIONS,
    REQUIRED_RELATIONS,
    UTCDateTime,
)


SHADOW_STORAGE_SCHEMA_VERSION = 1
SHADOW_RUNTIME_STATE_TABLE = "_input001_shadow_runtime_state"


class Input001ShadowStorageError(RuntimeError):
    """Le stockage shadow INPUT001 ne peut pas être préparé en sécurité."""


_runtime_metadata = MetaData()

shadow_runtime_state = Table(
    SHADOW_RUNTIME_STATE_TABLE,
    _runtime_metadata,
    Column("state_id", Integer, primary_key=True),
    Column("storage_schema_version", Integer, nullable=False),
    Column("last_attempt_at", UTCDateTime()),
    Column("last_success_at", UTCDateTime()),
    Column("last_status", String(32), nullable=False),
    Column("last_error_type", String(255)),
    Column("last_error_message", Text),
    Column("dataset_id", Text),
    Column("contract_version", String(64)),
    Column("snapshot_ref", Text),
    Column("coverage_from", UTCDateTime()),
    Column("coverage_to", UTCDateTime()),
)


@dataclass(frozen=True)
class ShadowStorageInspection:
    compatible: bool
    empty: bool
    reason: str | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def inspect_shadow_storage(engine: Engine) -> ShadowStorageInspection:
    """Inspecte uniquement les relations INPUT001 possédées par le shadow."""
    inspector = sa_inspect(engine)
    table_names = set(inspector.get_table_names())
    view_names = set(inspector.get_view_names())
    contract_names = set(CONTRACT_RELATIONS)

    contract_tables = table_names & contract_names
    contract_views = view_names & contract_names

    if contract_views:
        return ShadowStorageInspection(
            compatible=False,
            empty=False,
            reason=(
                "relations INPUT001 matérialisées comme vues : "
                + ", ".join(sorted(contract_views))
            ),
        )

    if not contract_tables:
        return ShadowStorageInspection(
            compatible=True,
            empty=True,
        )

    missing_required = REQUIRED_RELATIONS - contract_tables
    if missing_required:
        return ShadowStorageInspection(
            compatible=False,
            empty=False,
            reason=(
                "relations INPUT001 requises absentes : "
                + ", ".join(sorted(missing_required))
            ),
        )

    for relation_name in sorted(contract_tables):
        actual_columns = frozenset(
            column["name"]
            for column in inspector.get_columns(relation_name)
        )
        expected_columns = CONTRACT_RELATION_COLUMNS[relation_name]
        missing_columns = expected_columns - actual_columns

        if missing_columns:
            return ShadowStorageInspection(
                compatible=False,
                empty=False,
                reason=(
                    f"relation {relation_name!r} incomplète : "
                    + ", ".join(sorted(missing_columns))
                ),
            )

    return ShadowStorageInspection(
        compatible=True,
        empty=False,
    )


def _ensure_runtime_state_table(engine: Engine) -> None:
    inspector = sa_inspect(engine)
    tables = set(inspector.get_table_names())

    if SHADOW_RUNTIME_STATE_TABLE in tables:
        actual = frozenset(
            column["name"]
            for column in inspector.get_columns(SHADOW_RUNTIME_STATE_TABLE)
        )
        expected = frozenset(
            column.name for column in shadow_runtime_state.columns
        )

        if expected - actual:
            # Cette table est purement opérationnelle et reconstruisible.
            with engine.begin() as conn:
                shadow_runtime_state.drop(conn, checkfirst=True)

    with engine.begin() as conn:
        shadow_runtime_state.create(conn, checkfirst=True)


def _state_row(engine: Engine) -> dict[str, Any] | None:
    _ensure_runtime_state_table(engine)

    with engine.connect() as conn:
        row = conn.execute(
            select(shadow_runtime_state).where(
                shadow_runtime_state.c.state_id == 1
            )
        ).mappings().first()

    return dict(row) if row is not None else None


def _replace_state(engine: Engine, values: Mapping[str, Any]) -> None:
    _ensure_runtime_state_table(engine)
    payload = {
        "state_id": 1,
        "storage_schema_version": SHADOW_STORAGE_SCHEMA_VERSION,
        "last_status": "unknown",
        **dict(values),
    }

    with engine.begin() as conn:
        current = conn.execute(
            select(shadow_runtime_state.c.state_id).where(
                shadow_runtime_state.c.state_id == 1
            )
        ).first()

        if current is None:
            conn.execute(insert(shadow_runtime_state), [payload])
        else:
            conn.execute(
                update(shadow_runtime_state)
                .where(shadow_runtime_state.c.state_id == 1)
                .values(**payload)
            )


def _drop_contract_tables(engine: Engine) -> None:
    """Supprime uniquement les tables du cache INPUT001, jamais d'autres tables."""
    inspector = sa_inspect(engine)
    existing_tables = set(inspector.get_table_names())

    # Ordre inverse des dépendances logiques du contrat.
    drop_order = (
        "account_replacements",
        "balances",
        "account_states",
        "transactions",
        "accounts",
        "dataset_metadata",
    )

    with engine.begin() as conn:
        for relation_name in drop_order:
            if relation_name in existing_tables:
                CONTRACT_RELATIONS[relation_name].drop(
                    conn,
                    checkfirst=True,
                )


def prepare_shadow_storage(engine: Engine) -> dict[str, Any]:
    """
    Prépare le cache shadow avant matérialisation.

    INPUT001 shadow est un cache possédé par MLCFlux. Une ancienne forme de
    schéma peut donc être reconstruite au lieu d'être migrée ligne par ligne.
    Un stockage marqué avec une version *plus récente* que le code courant est
    en revanche refusé afin d'éviter un downgrade destructif silencieux.
    """
    inspection = inspect_shadow_storage(engine)
    state = _state_row(engine)
    stored_version = (
        int(state["storage_schema_version"])
        if state is not None
        else None
    )

    if (
        stored_version is not None
        and stored_version > SHADOW_STORAGE_SCHEMA_VERSION
    ):
        raise Input001ShadowStorageError(
            "Le cache INPUT001 a une version de stockage plus récente "
            f"({stored_version}) que celle supportée par ce code "
            f"({SHADOW_STORAGE_SCHEMA_VERSION})."
        )

    must_rebuild = not inspection.compatible

    if (
        stored_version is not None
        and stored_version < SHADOW_STORAGE_SCHEMA_VERSION
    ):
        must_rebuild = True

    if must_rebuild:
        _drop_contract_tables(engine)
        action = "reconstructed"
    elif inspection.empty:
        action = "initialized"
    elif stored_version is None:
        action = "adopted"
    else:
        action = "compatible"

    previous = state or {}
    _replace_state(
        engine,
        {
            "last_attempt_at": previous.get("last_attempt_at"),
            "last_success_at": previous.get("last_success_at"),
            "last_status": previous.get("last_status") or "unknown",
            "last_error_type": previous.get("last_error_type"),
            "last_error_message": previous.get("last_error_message"),
            "dataset_id": previous.get("dataset_id"),
            "contract_version": previous.get("contract_version"),
            "snapshot_ref": previous.get("snapshot_ref"),
            "coverage_from": previous.get("coverage_from"),
            "coverage_to": previous.get("coverage_to"),
        },
    )

    return {
        "action": action,
        "storage_schema_version": SHADOW_STORAGE_SCHEMA_VERSION,
        "reason": inspection.reason if must_rebuild else None,
    }


def record_shadow_attempt(engine: Engine) -> None:
    state = _state_row(engine) or {}
    _replace_state(
        engine,
        {
            "last_attempt_at": _utc_now(),
            "last_success_at": state.get("last_success_at"),
            "last_status": "running",
            "last_error_type": None,
            "last_error_message": None,
            "dataset_id": state.get("dataset_id"),
            "contract_version": state.get("contract_version"),
            "snapshot_ref": state.get("snapshot_ref"),
            "coverage_from": state.get("coverage_from"),
            "coverage_to": state.get("coverage_to"),
        },
    )


def record_shadow_error(engine: Engine, exc: BaseException) -> None:
    state = _state_row(engine) or {}
    _replace_state(
        engine,
        {
            "last_attempt_at": state.get("last_attempt_at") or _utc_now(),
            "last_success_at": state.get("last_success_at"),
            "last_status": "error",
            "last_error_type": type(exc).__name__,
            "last_error_message": str(exc),
            "dataset_id": state.get("dataset_id"),
            "contract_version": state.get("contract_version"),
            "snapshot_ref": state.get("snapshot_ref"),
            "coverage_from": state.get("coverage_from"),
            "coverage_to": state.get("coverage_to"),
        },
    )


def record_shadow_success(
    engine: Engine,
    dataset: Mapping[str, Any],
) -> None:
    state = _state_row(engine) or {}
    now = _utc_now()
    _replace_state(
        engine,
        {
            "last_attempt_at": state.get("last_attempt_at") or now,
            "last_success_at": now,
            "last_status": "success",
            "last_error_type": None,
            "last_error_message": None,
            "dataset_id": dataset.get("dataset_id"),
            "contract_version": dataset.get("contract_version"),
            "snapshot_ref": dataset.get("snapshot_ref"),
            "coverage_from": dataset.get("coverage_from"),
            "coverage_to": dataset.get("coverage_to"),
        },
    )


def read_shadow_health(engine: Engine) -> dict[str, Any]:
    state = _state_row(engine)

    if state is None:
        return {
            "storage_schema_version": SHADOW_STORAGE_SCHEMA_VERSION,
            "status": "unknown",
        }

    return {
        "storage_schema_version": int(state["storage_schema_version"]),
        "status": state["last_status"],
        "last_attempt_at": state["last_attempt_at"],
        "last_success_at": state["last_success_at"],
        "error_type": state["last_error_type"],
        "error": state["last_error_message"],
        "dataset_id": state["dataset_id"],
        "contract_version": state["contract_version"],
        "snapshot_ref": state["snapshot_ref"],
        "coverage_from": state["coverage_from"],
        "coverage_to": state["coverage_to"],
    }
