from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Mapping, Sequence

from sqlalchemy import Engine, delete, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from .schema import (
    ALL_RELATIONS,
    CONTRACT_VERSION,
    MATERIALIZED_RELATIONS,
    account_effects,
    account_replacements,
    accounts,
    actors,
    balance_observations,
    datasets,
    financial_events,
    identity_links,
    metadata,
    monetary_observations,
    publication_capabilities,
    publications,
)


class FinancialCoreWriteError(RuntimeError):
    pass


@dataclass(frozen=True)
class FinancialCorePayload:
    dataset: Mapping[str, Any]
    publication: Mapping[str, Any]
    accounts: Sequence[Mapping[str, Any]]
    events: Sequence[Mapping[str, Any]]
    effects: Sequence[Mapping[str, Any]]
    actors: Sequence[Mapping[str, Any]] = ()
    identity_links: Sequence[Mapping[str, Any]] = ()
    balance_observations: Sequence[Mapping[str, Any]] = ()
    monetary_observations: Sequence[Mapping[str, Any]] = ()
    account_replacements: Sequence[Mapping[str, Any]] = ()
    capabilities: Mapping[str, Any] = field(default_factory=dict)


EXECUTION_STATES = {
    "realized",
    "pending",
    "scheduled",
    "cancelled",
    "failed",
    "reversed",
    "unknown",
}
TIME_PRECISIONS = {"instant", "date", "unknown"}
IDENTITY_LINK_STATUSES = {"resolved", "candidate", "rejected", "unknown"}
CAPABILITY_STATUSES = {"available", "partial", "unavailable", "unknown"}
ORIGINS = {"native", "derived_from_native_transfer", "derived", "unknown"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _non_empty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FinancialCoreWriteError(f"{label} doit être une chaîne non vide.")
    return value.strip()


def _exact_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FinancialCoreWriteError(f"{label} doit être un entier exact.")
    return value


def _exponent(value: Any, label: str) -> int:
    value = _exact_int(value, label)
    if value < 0 or value > 18:
        raise FinancialCoreWriteError(f"{label} doit être compris entre 0 et 18.")
    return value


def _aware_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise FinancialCoreWriteError(f"{label} doit être un datetime timezone-aware.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise FinancialCoreWriteError(f"{label} doit être un datetime timezone-aware.")
    return value


def _date_only(value: Any, label: str) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise FinancialCoreWriteError(f"{label} doit être une date YYYY-MM-DD.")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise FinancialCoreWriteError(f"{label} doit être une date valide.") from exc
    return value


def _validate_time(row: Mapping[str, Any], *, prefix: str, label: str) -> None:
    precision = row.get("time_precision")
    if precision not in TIME_PRECISIONS:
        raise FinancialCoreWriteError(
            f"{label}.time_precision invalide : {precision!r}."
        )

    instant_key = f"{prefix}_at"
    date_key = f"{prefix}_date"
    instant = row.get(instant_key)
    calendar_date = row.get(date_key)

    if precision == "instant":
        _aware_datetime(instant, f"{label}.{instant_key}")
        if calendar_date is not None:
            raise FinancialCoreWriteError(
                f"{label}.{date_key} doit être null pour time_precision='instant'."
            )
    elif precision == "date":
        _date_only(calendar_date, f"{label}.{date_key}")
        if instant is not None:
            raise FinancialCoreWriteError(
                f"{label}.{instant_key} doit être null pour time_precision='date'."
            )
    else:
        if instant is not None or calendar_date is not None:
            raise FinancialCoreWriteError(
                f"{label} ne doit pas fabriquer de date pour time_precision='unknown'."
            )


def _json_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            json.loads(value)
        except json.JSONDecodeError as exc:
            raise FinancialCoreWriteError(f"{label} doit contenir du JSON valide.") from exc
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise FinancialCoreWriteError(f"{label} n'est pas sérialisable en JSON.") from exc


def _copy_rows(rows: Sequence[Mapping[str, Any]], label: str) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise FinancialCoreWriteError(f"{label}[{index}] doit être un mapping.")
        item = dict(row)
        for key in list(item):
            if key.endswith("_json"):
                item[key] = _json_text(item[key], f"{label}[{index}].{key}")
        copied.append(item)
    return copied


def _validate_input_columns(table, rows: Sequence[Mapping[str, Any]], label: str) -> None:
    auto = {"dataset_id", "publication_id"}
    allowed = {column.name for column in table.columns} - auto
    for index, row in enumerate(rows):
        unknown = set(row) - allowed
        if unknown:
            raise FinancialCoreWriteError(
                f"{label}[{index}] contient des colonnes inconnues : "
                + ", ".join(sorted(unknown))
            )


def _unique(rows: Sequence[Mapping[str, Any]], key: str, label: str) -> set[str]:
    seen: set[str] = set()
    for index, row in enumerate(rows):
        value = _non_empty(row.get(key), f"{label}[{index}].{key}")
        if value in seen:
            raise FinancialCoreWriteError(f"{label}.{key} dupliqué : {value!r}")
        seen.add(value)
    return seen


def _validate_money(row: Mapping[str, Any], *, label: str, amount_key: str = "amount_minor") -> None:
    _exact_int(row.get(amount_key), f"{label}.{amount_key}")
    _non_empty(row.get("unit_code"), f"{label}.unit_code")
    _exponent(row.get("unit_exponent"), f"{label}.unit_exponent")
    _non_empty(row.get("monetary_dimension"), f"{label}.monetary_dimension")


def _normalize_capabilities(publication_id: str, capabilities: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(capabilities, Mapping):
        raise FinancialCoreWriteError("capabilities doit être un mapping.")

    result: list[dict[str, Any]] = []
    for raw_name, raw_value in sorted(capabilities.items()):
        name = _non_empty(raw_name, "capability")
        if isinstance(raw_value, str):
            status = raw_value
            detail = None
        elif isinstance(raw_value, Mapping):
            status = raw_value.get("status")
            detail = raw_value.get("detail")
        else:
            raise FinancialCoreWriteError(
                f"capabilities[{name!r}] doit être une chaîne ou un mapping."
            )
        if status not in CAPABILITY_STATUSES:
            raise FinancialCoreWriteError(
                f"capabilities[{name!r}].status invalide : {status!r}."
            )
        result.append({
            "publication_id": publication_id,
            "capability": name,
            "status": status,
            "detail_json": _json_text(detail, f"capabilities[{name!r}].detail"),
        })
    return result


def _validate_payload(payload: FinancialCorePayload) -> dict[str, Any]:
    dataset = dict(payload.dataset)
    publication = dict(payload.publication)

    allowed_dataset = {"dataset_id", "contract_version", "source_system", "source_instance_id"}
    unknown = set(dataset) - allowed_dataset
    if unknown:
        raise FinancialCoreWriteError("dataset contient des colonnes inconnues : " + ", ".join(sorted(unknown)))

    allowed_publication = {
        "publication_id", "coverage_from", "coverage_to", "source_cursor",
        "source_snapshot_ref", "adapter_name", "adapter_version", "content_hash",
    }
    unknown = set(publication) - allowed_publication
    if unknown:
        raise FinancialCoreWriteError("publication contient des colonnes inconnues : " + ", ".join(sorted(unknown)))

    dataset_id = _non_empty(dataset.get("dataset_id"), "dataset.dataset_id")
    if dataset.get("contract_version") != CONTRACT_VERSION:
        raise FinancialCoreWriteError(
            f"Version Financial Core non supportée : {dataset.get('contract_version')!r}."
        )
    _non_empty(dataset.get("source_system"), "dataset.source_system")
    _non_empty(dataset.get("source_instance_id"), "dataset.source_instance_id")

    publication_id = _non_empty(publication.get("publication_id"), "publication.publication_id")
    _non_empty(publication.get("adapter_name"), "publication.adapter_name")
    _non_empty(publication.get("adapter_version"), "publication.adapter_version")
    for key in ("coverage_from", "coverage_to"):
        if publication.get(key) is not None:
            _aware_datetime(publication[key], f"publication.{key}")
    if publication.get("coverage_from") and publication.get("coverage_to"):
        if publication["coverage_from"] > publication["coverage_to"]:
            raise FinancialCoreWriteError("publication.coverage_from est après coverage_to.")

    relation_rows = {
        "accounts": _copy_rows(payload.accounts, "accounts"),
        "events": _copy_rows(payload.events, "events"),
        "effects": _copy_rows(payload.effects, "effects"),
        "actors": _copy_rows(payload.actors, "actors"),
        "identity_links": _copy_rows(payload.identity_links, "identity_links"),
        "balance_observations": _copy_rows(payload.balance_observations, "balance_observations"),
        "monetary_observations": _copy_rows(payload.monetary_observations, "monetary_observations"),
        "account_replacements": _copy_rows(payload.account_replacements, "account_replacements"),
    }

    table_by_key = {
        "accounts": accounts,
        "events": financial_events,
        "effects": account_effects,
        "actors": actors,
        "identity_links": identity_links,
        "balance_observations": balance_observations,
        "monetary_observations": monetary_observations,
        "account_replacements": account_replacements,
    }
    for key, rows in relation_rows.items():
        _validate_input_columns(table_by_key[key], rows, key)

    account_ids = _unique(relation_rows["accounts"], "account_id", "accounts")
    event_ids = _unique(relation_rows["events"], "event_id", "events")
    effect_ids = _unique(relation_rows["effects"], "effect_id", "effects")
    actor_ids = _unique(relation_rows["actors"], "actor_id", "actors")
    _unique(relation_rows["identity_links"], "identity_link_id", "identity_links")
    _unique(relation_rows["balance_observations"], "observation_id", "balance_observations")
    _unique(relation_rows["monetary_observations"], "observation_id", "monetary_observations")
    _unique(relation_rows["account_replacements"], "replacement_id", "account_replacements")

    for index, row in enumerate(relation_rows["events"]):
        label = f"events[{index}]"
        _non_empty(row.get("event_kind"), f"{label}.event_kind")
        if row.get("execution_state") not in EXECUTION_STATES:
            raise FinancialCoreWriteError(f"{label}.execution_state invalide : {row.get('execution_state')!r}.")
        _validate_time(row, prefix="occurred", label=label)
        native_amount = row.get("native_amount_minor")
        native_money_fields = (
            row.get("native_unit_code"), row.get("native_unit_exponent"), row.get("native_monetary_dimension")
        )
        if native_amount is None:
            if any(value is not None for value in native_money_fields):
                raise FinancialCoreWriteError(
                    f"{label}: les dimensions monétaires natives exigent native_amount_minor."
                )
        else:
            _exact_int(native_amount, f"{label}.native_amount_minor")
            _non_empty(row.get("native_unit_code"), f"{label}.native_unit_code")
            _exponent(row.get("native_unit_exponent"), f"{label}.native_unit_exponent")
            _non_empty(row.get("native_monetary_dimension"), f"{label}.native_monetary_dimension")

    for index, row in enumerate(relation_rows["effects"]):
        label = f"effects[{index}]"
        if row.get("event_id") not in event_ids:
            raise FinancialCoreWriteError(f"{label}.event_id référence un événement absent : {row.get('event_id')!r}")
        if row.get("account_id") not in account_ids:
            raise FinancialCoreWriteError(f"{label}.account_id référence un compte absent : {row.get('account_id')!r}")
        _validate_money(row, label=label)
        if row.get("origin") not in ORIGINS:
            raise FinancialCoreWriteError(f"{label}.origin invalide : {row.get('origin')!r}.")

    for index, row in enumerate(relation_rows["actors"]):
        _non_empty(row.get("source_system"), f"actors[{index}].source_system")

    for index, row in enumerate(relation_rows["identity_links"]):
        label = f"identity_links[{index}]"
        subject_kind = _non_empty(row.get("subject_kind"), f"{label}.subject_kind")
        target_kind = _non_empty(row.get("target_kind"), f"{label}.target_kind")
        subject_id = _non_empty(row.get("subject_id"), f"{label}.subject_id")
        target_id = _non_empty(row.get("target_id"), f"{label}.target_id")
        _non_empty(row.get("link_kind"), f"{label}.link_kind")
        if row.get("status") not in IDENTITY_LINK_STATUSES:
            raise FinancialCoreWriteError(f"{label}.status invalide : {row.get('status')!r}.")
        if subject_kind == "account" and subject_id not in account_ids:
            raise FinancialCoreWriteError(f"{label}.subject_id référence un compte absent : {subject_id!r}")
        if target_kind == "account" and target_id not in account_ids:
            raise FinancialCoreWriteError(f"{label}.target_id référence un compte absent : {target_id!r}")
        if subject_kind == "actor" and subject_id not in actor_ids:
            raise FinancialCoreWriteError(f"{label}.subject_id référence un acteur absent : {subject_id!r}")
        if target_kind == "actor" and target_id not in actor_ids:
            raise FinancialCoreWriteError(f"{label}.target_id référence un acteur absent : {target_id!r}")
        for key in ("valid_from", "valid_to"):
            if row.get(key) is not None:
                _aware_datetime(row[key], f"{label}.{key}")
        if row.get("valid_from") and row.get("valid_to") and row["valid_from"] > row["valid_to"]:
            raise FinancialCoreWriteError(f"{label}.valid_from est après valid_to.")

    for key, prefix in (("balance_observations", "observed"), ("monetary_observations", "observed")):
        for index, row in enumerate(relation_rows[key]):
            label = f"{key}[{index}]"
            if key == "balance_observations" and row.get("account_id") not in account_ids:
                raise FinancialCoreWriteError(f"{label}.account_id référence un compte absent : {row.get('account_id')!r}")
            _validate_time(row, prefix=prefix, label=label)
            _validate_money(row, label=label)
            _non_empty(row.get("source_system"), f"{label}.source_system")
            if key == "balance_observations":
                _non_empty(row.get("balance_component"), f"{label}.balance_component")
            else:
                _non_empty(row.get("scope_kind"), f"{label}.scope_kind")
                _non_empty(row.get("metric_kind"), f"{label}.metric_kind")

    for index, row in enumerate(relation_rows["account_replacements"]):
        label = f"account_replacements[{index}]"
        for key in ("old_account_id", "new_account_id"):
            if row.get(key) not in account_ids:
                raise FinancialCoreWriteError(f"{label}.{key} référence un compte absent : {row.get(key)!r}")
        if row.get("old_account_id") == row.get("new_account_id"):
            raise FinancialCoreWriteError(f"{label}: ancien et nouveau compte doivent être distincts.")
        _validate_time(row, prefix="effective", label=label)

    # Silence lint-like tools and make duplicate detection explicit in diagnostics.
    _ = effect_ids

    capabilities = _normalize_capabilities(publication_id, payload.capabilities)

    for rows in relation_rows.values():
        for row in rows:
            row["dataset_id"] = dataset_id
            row["publication_id"] = publication_id

    now = _utc_now()
    publication_row = {
        **publication,
        "dataset_id": dataset_id,
        "created_at": now,
        "status": "published",
    }

    return {
        "dataset": dataset,
        "publication": publication_row,
        "capabilities": capabilities,
        **relation_rows,
    }


def publish_financial_core(engine: Engine, payload: FinancialCorePayload) -> str:
    """Validate and atomically publish one coherent Financial Core snapshot.

    The current materialized facts are replaced inside one DB transaction.  A
    failed publication therefore leaves the previous valid publication intact.
    Publication metadata is retained as a lightweight history.
    """

    prepared = _validate_payload(payload)
    dataset = prepared["dataset"]
    publication = prepared["publication"]
    dataset_id = dataset["dataset_id"]
    publication_id = publication["publication_id"]
    now = publication["created_at"]

    try:
        metadata.create_all(engine)
        with engine.begin() as conn:
            existing_dataset = conn.execute(
                select(datasets).where(datasets.c.dataset_id == dataset_id)
            ).mappings().first()

            if existing_dataset:
                for key in ("contract_version", "source_system", "source_instance_id"):
                    if existing_dataset[key] != dataset[key]:
                        raise FinancialCoreWriteError(
                            f"dataset {dataset_id!r}: {key} ne peut pas changer "
                            f"({existing_dataset[key]!r} -> {dataset[key]!r})."
                        )
            else:
                conn.execute(insert(datasets), [{
                    **dataset,
                    "current_publication_id": None,
                    "created_at": now,
                    "updated_at": now,
                }])

            if conn.execute(
                select(publications.c.publication_id).where(
                    publications.c.publication_id == publication_id
                )
            ).first():
                raise FinancialCoreWriteError(
                    f"publication_id déjà utilisé : {publication_id!r}."
                )

            # Remove only current materialized facts.  Old publication metadata
            # remains available for diagnostics, while facts stay bounded in size.
            for table in (
                identity_links,
                account_replacements,
                balance_observations,
                monetary_observations,
                account_effects,
                financial_events,
                actors,
                accounts,
            ):
                conn.execute(delete(table).where(table.c.dataset_id == dataset_id))

            conn.execute(insert(publications), [publication])
            if prepared["capabilities"]:
                conn.execute(insert(publication_capabilities), prepared["capabilities"])

            ordered = (
                (accounts, prepared["accounts"]),
                (actors, prepared["actors"]),
                (financial_events, prepared["events"]),
                (account_effects, prepared["effects"]),
                (identity_links, prepared["identity_links"]),
                (balance_observations, prepared["balance_observations"]),
                (monetary_observations, prepared["monetary_observations"]),
                (account_replacements, prepared["account_replacements"]),
            )
            for table, rows in ordered:
                if rows:
                    conn.execute(insert(table), rows)

            conn.execute(
                update(datasets)
                .where(datasets.c.dataset_id == dataset_id)
                .values(current_publication_id=publication_id, updated_at=now)
            )

    except FinancialCoreWriteError:
        raise
    except (SQLAlchemyError, ValueError) as exc:
        raise FinancialCoreWriteError(
            f"Échec de publication Financial Core {publication_id!r}."
        ) from exc

    return publication_id
