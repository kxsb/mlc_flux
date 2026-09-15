from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import Engine, select

from server.financial_core.schema import metadata


class FinancialCoreReadError(RuntimeError):
    """Erreur de lecture cohérente du Financial Core."""


_DATASETS = "financial_core_datasets"
_PUBLICATIONS = "financial_core_publications"
_CAPABILITIES = "financial_core_publication_capabilities"

_FACT_TABLES = (
    "financial_core_accounts",
    "financial_core_events",
    "financial_core_account_effects",
    "financial_core_actors",
    "financial_core_identity_links",
    "financial_core_balance_observations",
    "financial_core_monetary_observations",
    "financial_core_account_replacements",
)


@dataclass(frozen=True)
class FinancialCoreSnapshot:
    """
    Vue cohérente d'une publication Financial Core.

    Toutes les relations contenues dans cet objet ont été lues dans
    une même transaction et filtrées par le même publication_id.
    """

    dataset: Mapping[str, Any]
    publication: Mapping[str, Any]
    capabilities: tuple[Mapping[str, Any], ...]
    accounts: tuple[Mapping[str, Any], ...]
    events: tuple[Mapping[str, Any], ...]
    account_effects: tuple[Mapping[str, Any], ...]
    actors: tuple[Mapping[str, Any], ...]
    identity_links: tuple[Mapping[str, Any], ...]
    balance_observations: tuple[Mapping[str, Any], ...]
    monetary_observations: tuple[Mapping[str, Any], ...]
    account_replacements: tuple[Mapping[str, Any], ...]

    @property
    def dataset_id(self) -> str:
        return str(self.dataset["dataset_id"])

    @property
    def publication_id(self) -> str:
        return str(self.publication["publication_id"])

    def counts(self) -> dict[str, int]:
        return {
            "capabilities": len(self.capabilities),
            "accounts": len(self.accounts),
            "events": len(self.events),
            "account_effects": len(self.account_effects),
            "actors": len(self.actors),
            "identity_links": len(self.identity_links),
            "balance_observations": len(self.balance_observations),
            "monetary_observations": len(self.monetary_observations),
            "account_replacements": len(self.account_replacements),
        }


def _table(name: str):
    try:
        return metadata.tables[name]
    except KeyError as exc:
        raise FinancialCoreReadError(
            f"Relation Financial Core absente du schéma : {name}"
        ) from exc


def _row_dict(row) -> dict[str, Any]:
    return dict(row._mapping)


def _ordered_rows(
    conn,
    table_name: str,
    *,
    publication_id: str,
    dataset_id: str | None = None,
) -> tuple[dict[str, Any], ...]:
    table = _table(table_name)

    conditions = []

    if "publication_id" in table.c:
        conditions.append(table.c.publication_id == publication_id)

    if dataset_id is not None and "dataset_id" in table.c:
        conditions.append(table.c.dataset_id == dataset_id)

    stmt = select(table)

    if conditions:
        stmt = stmt.where(*conditions)

    primary_key_columns = list(table.primary_key.columns)
    if primary_key_columns:
        stmt = stmt.order_by(*primary_key_columns)

    return tuple(
        _row_dict(row)
        for row in conn.execute(stmt).fetchall()
    )


def get_current_publication_id(
    engine: Engine,
    dataset_id: str,
) -> str | None:
    """
    Retourne le pointeur courant d'un dataset.

    Cette fonction est utile pour le diagnostic. Pour lire les faits,
    utiliser read_current_financial_core afin de garder la lecture dans
    une transaction cohérente.
    """
    datasets = _table(_DATASETS)

    with engine.connect() as conn:
        row = conn.execute(
            select(datasets.c.current_publication_id).where(
                datasets.c.dataset_id == dataset_id
            )
        ).first()

    if row is None:
        return None

    value = row[0]
    return str(value) if value else None


def read_current_financial_core(
    engine: Engine,
    dataset_id: str,
) -> FinancialCoreSnapshot:
    """
    Lit la publication courante d'un dataset sans mélanger deux versions.

    Le publication_id est résolu une seule fois puis toutes les relations
    sont filtrées par ce même identifiant dans la même transaction.

    L'isolation SERIALIZABLE est demandée afin que la lecture garde un
    instantané cohérent aussi bien sur SQLite que sur PostgreSQL.
    """
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise FinancialCoreReadError("dataset_id doit être renseigné.")

    dataset_id = dataset_id.strip()

    datasets = _table(_DATASETS)
    publications = _table(_PUBLICATIONS)

    connection = engine.connect().execution_options(
        isolation_level="SERIALIZABLE"
    )

    try:
        with connection.begin():
            dataset_row = connection.execute(
                select(datasets).where(
                    datasets.c.dataset_id == dataset_id
                )
            ).first()

            if dataset_row is None:
                raise FinancialCoreReadError(
                    f"Dataset Financial Core introuvable : {dataset_id!r}"
                )

            dataset = _row_dict(dataset_row)

            publication_id = dataset.get("current_publication_id")

            if not publication_id:
                raise FinancialCoreReadError(
                    f"Le dataset {dataset_id!r} n'a pas de publication courante."
                )

            publication_id = str(publication_id)

            publication_row = connection.execute(
                select(publications).where(
                    publications.c.publication_id == publication_id,
                    publications.c.dataset_id == dataset_id,
                )
            ).first()

            if publication_row is None:
                raise FinancialCoreReadError(
                    "Le pointeur current_publication_id référence "
                    f"une publication absente : {publication_id!r}"
                )

            publication = _row_dict(publication_row)

            capabilities = _ordered_rows(
                connection,
                _CAPABILITIES,
                publication_id=publication_id,
            )

            fact_rows = {
                name: _ordered_rows(
                    connection,
                    name,
                    publication_id=publication_id,
                    dataset_id=dataset_id,
                )
                for name in _FACT_TABLES
            }

            return FinancialCoreSnapshot(
                dataset=dataset,
                publication=publication,
                capabilities=capabilities,
                accounts=fact_rows["financial_core_accounts"],
                events=fact_rows["financial_core_events"],
                account_effects=fact_rows["financial_core_account_effects"],
                actors=fact_rows["financial_core_actors"],
                identity_links=fact_rows["financial_core_identity_links"],
                balance_observations=fact_rows[
                    "financial_core_balance_observations"
                ],
                monetary_observations=fact_rows[
                    "financial_core_monetary_observations"
                ],
                account_replacements=fact_rows[
                    "financial_core_account_replacements"
                ],
            )
    finally:
        connection.close()
