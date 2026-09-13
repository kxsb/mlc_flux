from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import create_engine

from server.input_contract.reader import FinancialContractReader
from server.mlc_context import (
    get_default_mlc_id,
    get_mlc_db_path,
    get_mlc_input001_db_path,
    normalize_mlc_id,
)
from server.resolver.account_resolver import (
    AccountResolution,
    AccountResolverRuleset,
    resolve_accounts,
)
from server.resolver.ruleset_loader import load_account_ruleset


FACT_FIELDS = (
    "source_system",
    "native_account_type",
    "native_account_kind",
    "native_status",
)

LEGACY_FAMILY_NORMALIZATION = {
    "professional": "professional",
    "individual": "individual",
    "individual_device": "individual",
    "system": "technical",
    "exchange_office_or_stock": "technical",
    # L'opérateur reste volontairement distinct. Si INPUT001 ne porte pas de
    # fait natif permettant de le reconnaître, RESOLVER002 doit montrer cette
    # divergence au lieu de la masquer.
    "operator": "operator",
}


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _readonly_sqlite_connection(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _readonly_input001_engine(path: Path):
    resolved = path.resolve()

    def creator():
        return sqlite3.connect(
            f"file:{resolved.as_posix()}?mode=ro",
            uri=True,
        )

    return create_engine("sqlite+pysqlite://", creator=creator)


def read_legacy_semantics(path: Path) -> list[dict[str, Any]] | None:
    """Lit les sémantiques legacy sans créer ni modifier de table."""
    if not path.exists():
        return None

    conn = _readonly_sqlite_connection(path)
    try:
        exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'transaction_semantics'
            LIMIT 1
            """
        ).fetchone()

        if exists is None:
            return None

        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    cyclos_id,
                    from_actor_family,
                    to_actor_family
                FROM transaction_semantics
                WHERE cyclos_id IS NOT NULL
                  AND TRIM(cyclos_id) <> ''
                """
            ).fetchall()
        ]
    finally:
        conn.close()


def _legacy_account_families(
    transactions: Sequence[Mapping[str, Any]],
    legacy_semantics_rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, set[str]]:
    if legacy_semantics_rows is None:
        return {}

    semantics_by_tx = {
        str(row.get("cyclos_id")): row
        for row in legacy_semantics_rows
        if _clean_optional_text(row.get("cyclos_id")) is not None
    }

    families: dict[str, set[str]] = defaultdict(set)

    for transaction in transactions:
        transaction_id = _clean_optional_text(
            transaction.get("transaction_id")
        )
        if transaction_id is None:
            continue

        legacy = semantics_by_tx.get(transaction_id)
        if legacy is None:
            continue

        for account_field, family_field in (
            ("source_account_id", "from_actor_family"),
            ("destination_account_id", "to_actor_family"),
        ):
            account_id = _clean_optional_text(
                transaction.get(account_field)
            )
            raw_family = _clean_optional_text(legacy.get(family_field))
            normalized = (
                LEGACY_FAMILY_NORMALIZATION.get(raw_family)
                if raw_family is not None
                else None
            )

            if account_id is not None and normalized is not None:
                families[account_id].add(normalized)

    return dict(families)


def _resolution_summary(
    resolutions: Sequence[AccountResolution],
) -> dict[str, Any]:
    status_counts = Counter(item.status for item in resolutions)
    family_counts = Counter(
        item.family
        for item in resolutions
        if item.status == "resolved" and item.family is not None
    )

    return {
        "accounts_total": len(resolutions),
        "resolved": status_counts.get("resolved", 0),
        "unknown": status_counts.get("unknown", 0),
        "conflict": status_counts.get("conflict", 0),
        "families": dict(sorted(family_counts.items())),
    }


def _fact_combinations(
    accounts: Sequence[Mapping[str, Any]],
    resolutions: Sequence[AccountResolution],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str | None, ...], dict[str, Any]] = {}

    for account, resolution in zip(accounts, resolutions, strict=True):
        signature = tuple(
            _clean_optional_text(account.get(field))
            for field in FACT_FIELDS
        )
        entry = grouped.setdefault(
            signature,
            {
                "count": 0,
                "statuses": Counter(),
                "families": Counter(),
            },
        )
        entry["count"] += 1
        entry["statuses"][resolution.status] += 1
        if resolution.family is not None:
            entry["families"][resolution.family] += 1

    rows = []
    for signature, entry in grouped.items():
        facts = dict(zip(FACT_FIELDS, signature, strict=True))
        rows.append({
            **facts,
            "count": entry["count"],
            "resolver_statuses": dict(sorted(entry["statuses"].items())),
            "resolver_families": dict(sorted(entry["families"].items())),
        })

    return sorted(
        rows,
        key=lambda row: (
            -int(row["count"]),
            str(row.get("native_account_type") or ""),
            str(row.get("native_account_kind") or ""),
            str(row.get("native_status") or ""),
        ),
    )


def _legacy_comparison(
    accounts: Sequence[Mapping[str, Any]],
    resolutions: Sequence[AccountResolution],
    legacy_families: Mapping[str, set[str]],
    *,
    legacy_available: bool,
) -> dict[str, Any]:
    if not legacy_available:
        return {
            "available": False,
            "legacy_classifiable": 0,
            "legacy_conflict": 0,
            "legacy_vs_resolver_same": 0,
            "legacy_vs_resolver_different": 0,
        }

    classifiable = 0
    conflict = 0
    same = 0
    different = 0
    legacy_family_counts: Counter[str] = Counter()

    for account, resolution in zip(accounts, resolutions, strict=True):
        account_id = _clean_optional_text(account.get("account_id"))
        observed = legacy_families.get(account_id or "", set())

        if len(observed) > 1:
            conflict += 1
            continue
        if len(observed) != 1:
            continue

        legacy_family = next(iter(observed))
        classifiable += 1
        legacy_family_counts[legacy_family] += 1

        if resolution.status != "resolved" or resolution.family is None:
            continue

        if resolution.family == legacy_family:
            same += 1
        else:
            different += 1

    return {
        "available": True,
        "legacy_classifiable": classifiable,
        "legacy_conflict": conflict,
        "legacy_families": dict(sorted(legacy_family_counts.items())),
        "legacy_vs_resolver_same": same,
        "legacy_vs_resolver_different": different,
    }


def build_account_resolution_report(
    *,
    accounts: Sequence[Mapping[str, Any]],
    transactions: Sequence[Mapping[str, Any]],
    ruleset: AccountResolverRuleset,
    legacy_semantics_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Construit un rapport agrégé sans exposer les identités de comptes."""
    resolutions = resolve_accounts(accounts, ruleset=ruleset)
    legacy_families = _legacy_account_families(
        transactions,
        legacy_semantics_rows,
    )

    missing_type = sum(
        _clean_optional_text(account.get("native_account_type")) is None
        for account in accounts
    )
    missing_kind = sum(
        _clean_optional_text(account.get("native_account_kind")) is None
        for account in accounts
    )

    return {
        "ruleset_version": ruleset.version,
        "summary": _resolution_summary(resolutions),
        "fact_coverage": {
            "unknown_native_account_type": missing_type,
            "unknown_native_account_kind": missing_kind,
        },
        "legacy_comparison": _legacy_comparison(
            accounts,
            resolutions,
            legacy_families,
            legacy_available=(legacy_semantics_rows is not None),
        ),
        "fact_combinations": _fact_combinations(
            accounts,
            resolutions,
        ),
    }


def _metadata_for_report(metadata: Mapping[str, Any]) -> dict[str, Any]:
    result = {}
    for field in (
        "dataset_id",
        "contract_version",
        "source_system",
        "snapshot_ref",
        "coverage_from",
        "coverage_to",
    ):
        value = metadata.get(field)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        result[field] = value
    return result


def build_runtime_report(mlc_id: str) -> dict[str, Any]:
    normalized = normalize_mlc_id(mlc_id)
    input001_path = get_mlc_input001_db_path(normalized)
    legacy_path = get_mlc_db_path(normalized)

    if not input001_path.exists():
        raise FileNotFoundError(
            f"Base INPUT001 introuvable : {input001_path}"
        )

    engine = _readonly_input001_engine(input001_path)
    try:
        reader = FinancialContractReader(engine)
        metadata = reader.metadata_row()
        accounts = reader.fetch_accounts()
        transactions = reader.fetch_transactions()
    finally:
        engine.dispose()

    ruleset = load_account_ruleset(normalized)
    legacy_rows = read_legacy_semantics(legacy_path)

    report = build_account_resolution_report(
        accounts=accounts,
        transactions=transactions,
        ruleset=ruleset,
        legacy_semantics_rows=legacy_rows,
    )
    report["mlc_id"] = normalized
    report["input001"] = _metadata_for_report(metadata)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare en lecture seule le resolver INPUT001 et les familles "
            "legacy, sans exposer les identités de comptes."
        )
    )
    parser.add_argument(
        "--mlc",
        default=None,
        help=(
            "Profil MLC à auditer. Par défaut, utilise "
            "MLCFLUX_DEFAULT_MLC_ID, qui doit être explicitement configuré."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    mlc_id = args.mlc or get_default_mlc_id()
    report = build_runtime_report(mlc_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
