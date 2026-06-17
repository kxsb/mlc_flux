from __future__ import annotations

import re
import sqlite3
from datetime import date
from typing import Any

from server.database import get_db_path


OPERATOR_ACCOUNT_REFS = {"P0000", "P9999"}
PROFESSIONAL_REF_RE = re.compile(r"^P\d{4}$")

DEFAULT_LIMIT = 12
MAX_LIMIT = 30


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_professional_ref(value: str | None) -> str:
    ref = str(value or "").strip().upper()
    if not PROFESSIONAL_REF_RE.match(ref):
        raise ValueError(f"Référence professionnelle invalide : {value!r}")
    return ref


def _parse_iso_date(value: str | None, field_name: str) -> str | None:
    text = _clean_text(value)
    if not text:
        return None

    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"Date invalide pour {field_name}: {value!r}. Format attendu : YYYY-MM-DD."
        ) from exc



# REUSE_PROSPECTS002_PROFESSIONAL_NAMES
def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table_name or ""):
        return set()

    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()

    if not exists:
        return set()

    return {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _select_first_existing_column(columns: set[str], candidates: list[str]) -> str | None:
    for column in candidates:
        if column in columns:
            return column
    return None


def _professional_enrichment_lookup(
    conn: sqlite3.Connection,
    refs: set[str],
) -> dict[str, dict[str, Any]]:
    """Lookup multi-MLC hors Odoo : professional_enrichment quand disponible."""
    if not refs:
        return {}

    columns = _table_columns(conn, "professional_enrichment")

    if not columns:
        return {}

    ref_column = _select_first_existing_column(
        columns,
        ["professional_ref", "actor_ref", "ref", "account_number", "cyclos_ref"],
    )

    name_columns = [
        column
        for column in [
            "display_name",
            "legal_name",
            "name",
            "odoo_name",
            "business_name",
            "commercial_name",
            "label",
        ]
        if column in columns
    ]

    industry_column = _select_first_existing_column(
        columns,
        ["industry_name", "sector_name", "activity_sector", "category_name"],
    )

    activity_column = _select_first_existing_column(
        columns,
        ["short_description", "detailed_activity", "activity", "description"],
    )

    zip_column = _select_first_existing_column(
        columns,
        ["cyclos_zip", "zip", "postal_code"],
    )

    city_column = _select_first_existing_column(
        columns,
        ["cyclos_city", "city"],
    )

    if not ref_column or not name_columns:
        return {}

    placeholders = ",".join("?" for _ in refs)
    select_parts = [
        f"{ref_column} AS professional_ref",
        *[f"{column} AS name_{index}" for index, column in enumerate(name_columns)],
    ]

    if industry_column:
        select_parts.append(f"{industry_column} AS industry_name")

    if activity_column:
        select_parts.append(f"{activity_column} AS detailed_activity")

    if zip_column:
        select_parts.append(f"{zip_column} AS zip")

    if city_column:
        select_parts.append(f"{city_column} AS city")

    rows = conn.execute(
        f"""
        SELECT {", ".join(select_parts)}
        FROM professional_enrichment
        WHERE {ref_column} IN ({placeholders})
        """,
        sorted(refs),
    ).fetchall()

    lookup: dict[str, dict[str, Any]] = {}

    for row in rows:
        ref = _normalize_professional_ref(row["professional_ref"])
        name = None

        for index in range(len(name_columns)):
            name = _clean_text(row[f"name_{index}"])
            if name:
                break

        lookup[ref] = {
            "professional_ref": ref,
            "name": name or ref,
            "industry_name": _clean_text(row["industry_name"]) if "industry_name" in row.keys() else None,
            "detailed_activity": _clean_text(row["detailed_activity"]) if "detailed_activity" in row.keys() else None,
            "zip": _clean_text(row["zip"]) if "zip" in row.keys() else None,
            "city": _clean_text(row["city"]) if "city" in row.keys() else None,
        }

    return lookup


def _professional_identity(
    conn: sqlite3.Connection,
    professional_ref: str,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
          professional_ref,
          odoo_name,
          industry_name,
          detailed_activity,
          zip,
          city,
          cyclos_zip,
          cyclos_city
        FROM odoo_professional_enrichment
        WHERE professional_ref = ?
        """,
        (professional_ref,),
    ).fetchone()

    if not row:
        return {
            "professional_ref": professional_ref,
            "name": professional_ref,
            "industry_name": None,
            "detailed_activity": None,
            "zip": None,
            "city": None,
        }

    return {
        "professional_ref": professional_ref,
        "name": _clean_text(row["odoo_name"]) or professional_ref,
        "industry_name": _clean_text(row["industry_name"]),
        "detailed_activity": _clean_text(row["detailed_activity"]),
        "zip": _clean_text(row["cyclos_zip"]) or _clean_text(row["zip"]),
        "city": _clean_text(row["cyclos_city"]) or _clean_text(row["city"]),
    }


def _professional_lookup(
    conn: sqlite3.Connection,
    refs: set[str],
) -> dict[str, dict[str, Any]]:
    if not refs:
        return {}

    placeholders = ",".join("?" for _ in refs)

    rows = conn.execute(
        f"""
        SELECT
          professional_ref,
          odoo_name,
          industry_name,
          detailed_activity,
          zip,
          city,
          cyclos_zip,
          cyclos_city
        FROM odoo_professional_enrichment
        WHERE professional_ref IN ({placeholders})
        """,
        sorted(refs),
    ).fetchall()

    lookup: dict[str, dict[str, Any]] = {}

    for row in rows:
        ref = row["professional_ref"]
        lookup[ref] = {
            "professional_ref": ref,
            "name": _clean_text(row["odoo_name"]) or ref,
            "industry_name": _clean_text(row["industry_name"]),
            "detailed_activity": _clean_text(row["detailed_activity"]),
            "zip": _clean_text(row["cyclos_zip"]) or _clean_text(row["zip"]),
            "city": _clean_text(row["cyclos_city"]) or _clean_text(row["city"]),
        }

    # REUSE_PROSPECTS002_PROFESSIONAL_NAMES
    # Complément multi-MLC : si Odoo est absent/incomplet, récupérer le libellé
    # depuis professional_enrichment, utilisé notamment par Graine.
    generic_lookup = _professional_enrichment_lookup(conn, refs)

    for ref, generic in generic_lookup.items():
        current = lookup.get(ref)

        if not current:
            lookup[ref] = generic
            continue

        if current.get("name") == ref and generic.get("name"):
            current["name"] = generic["name"]

        for key in ["industry_name", "detailed_activity", "zip", "city"]:
            if not current.get(key) and generic.get(key):
                current[key] = generic[key]

    for ref in refs:
        lookup.setdefault(
            ref,
            {
                "professional_ref": ref,
                "name": ref,
                "industry_name": None,
                "detailed_activity": None,
                "zip": None,
                "city": None,
            },
        )

    return lookup


def _resolve_period(
    conn: sqlite3.Connection,
    requested_start: str | None,
    requested_end: str | None,
) -> dict[str, str | None]:
    start = _parse_iso_date(requested_start, "start")
    end = _parse_iso_date(requested_end, "end")

    bounds = conn.execute(
        """
        SELECT
          MIN(SUBSTR(date, 1, 10)) AS min_date,
          MAX(SUBSTR(date, 1, 10)) AS max_date
        FROM transactions
        """
    ).fetchone()

    effective_start = start or (bounds["min_date"] if bounds else None)
    effective_end = end or (bounds["max_date"] if bounds else None)

    if effective_start and effective_end and effective_start > effective_end:
        raise ValueError(
            f"Période invalide : start={effective_start} est postérieur à end={effective_end}."
        )

    return {
        "requested_start": start,
        "requested_end": end,
        "effective_start": effective_start,
        "effective_end": effective_end,
        "min_date": bounds["min_date"] if bounds else None,
        "max_date": bounds["max_date"] if bounds else None,
    }


def _same_sector_peers(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    industry_name: str,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT professional_ref
        FROM odoo_professional_enrichment
        WHERE professional_ref <> ?
          AND industry_name = ?
        ORDER BY professional_ref ASC
        """,
        (professional_ref, industry_name),
    ).fetchall()

    return [row["professional_ref"] for row in rows]


def _period_where(
    start: str | None,
    end: str | None,
    *,
    alias: str = "",
) -> tuple[list[str], list[Any]]:
    prefix = f"{alias}." if alias else ""
    where_parts: list[str] = []
    params: list[Any] = []

    if start:
        where_parts.append(f"SUBSTR({prefix}date, 1, 10) >= ?")
        params.append(start)

    if end:
        where_parts.append(f"SUBSTR({prefix}date, 1, 10) <= ?")
        params.append(end)

    return where_parts, params


def _active_peer_refs(
    conn: sqlite3.Connection,
    *,
    peer_refs: list[str],
    start: str | None,
    end: str | None,
) -> set[str]:
    if not peer_refs:
        return set()

    placeholders = ",".join("?" for _ in peer_refs)
    period_parts, period_params = _period_where(start, end)

    where_parts = [
        f"SUBSTR(TRIM(from_label), 1, 5) IN ({placeholders})",
        "SUBSTR(TRIM(to_label), 1, 5) GLOB 'P[0-9][0-9][0-9][0-9]'",
        "SUBSTR(TRIM(to_label), 1, 5) NOT IN ('P0000', 'P9999')",
    ]
    where_parts.extend(period_parts)

    rows = conn.execute(
        f"""
        SELECT DISTINCT SUBSTR(TRIM(from_label), 1, 5) AS peer_ref
        FROM transactions
        WHERE {" AND ".join(where_parts)}
        """,
        [*peer_refs, *period_params],
    ).fetchall()

    return {row["peer_ref"] for row in rows}


def _suppliers_already_paid_by_target(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> set[str]:
    period_parts, period_params = _period_where(start, end)

    where_parts = [
        "SUBSTR(TRIM(from_label), 1, 5) = ?",
        "SUBSTR(TRIM(to_label), 1, 5) GLOB 'P[0-9][0-9][0-9][0-9]'",
        "SUBSTR(TRIM(to_label), 1, 5) NOT IN ('P0000', 'P9999')",
        "SUBSTR(TRIM(to_label), 1, 5) <> ?",
    ]
    where_parts.extend(period_parts)

    rows = conn.execute(
        f"""
        SELECT DISTINCT SUBSTR(TRIM(to_label), 1, 5) AS supplier_ref
        FROM transactions
        WHERE {" AND ".join(where_parts)}
        """,
        [professional_ref, professional_ref, *period_params],
    ).fetchall()

    return {row["supplier_ref"] for row in rows}


def _suppliers_paid_before_period(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
) -> set[str]:
    if not start:
        return set()

    rows = conn.execute(
        """
        SELECT DISTINCT SUBSTR(TRIM(to_label), 1, 5) AS supplier_ref
        FROM transactions
        WHERE SUBSTR(TRIM(from_label), 1, 5) = ?
          AND SUBSTR(TRIM(to_label), 1, 5) GLOB 'P[0-9][0-9][0-9][0-9]'
          AND SUBSTR(TRIM(to_label), 1, 5) NOT IN ('P0000', 'P9999')
          AND SUBSTR(TRIM(to_label), 1, 5) <> ?
          AND SUBSTR(date, 1, 10) < ?
        """,
        (professional_ref, professional_ref, start),
    ).fetchall()

    return {row["supplier_ref"] for row in rows}


def _professionals_paying_target_in_period(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> set[str]:
    period_parts, period_params = _period_where(start, end)

    where_parts = [
        "SUBSTR(TRIM(to_label), 1, 5) = ?",
        "SUBSTR(TRIM(from_label), 1, 5) GLOB 'P[0-9][0-9][0-9][0-9]'",
        "SUBSTR(TRIM(from_label), 1, 5) NOT IN ('P0000', 'P9999')",
        "SUBSTR(TRIM(from_label), 1, 5) <> ?",
    ]
    where_parts.extend(period_parts)

    rows = conn.execute(
        f"""
        SELECT DISTINCT SUBSTR(TRIM(from_label), 1, 5) AS buyer_ref
        FROM transactions
        WHERE {" AND ".join(where_parts)}
        """,
        [professional_ref, professional_ref, *period_params],
    ).fetchall()

    return {row["buyer_ref"] for row in rows}


def _candidate_supplier_rows(
    conn: sqlite3.Connection,
    *,
    active_peer_refs: set[str],
    excluded_supplier_refs: set[str],
    target_ref: str,
    start: str | None,
    end: str | None,
) -> list[sqlite3.Row]:
    if not active_peer_refs:
        return []

    peer_placeholders = ",".join("?" for _ in active_peer_refs)

    period_parts, period_params = _period_where(start, end)

    where_parts = [
        f"SUBSTR(TRIM(from_label), 1, 5) IN ({peer_placeholders})",
        "SUBSTR(TRIM(to_label), 1, 5) GLOB 'P[0-9][0-9][0-9][0-9]'",
        "SUBSTR(TRIM(to_label), 1, 5) NOT IN ('P0000', 'P9999')",
        "SUBSTR(TRIM(to_label), 1, 5) <> ?",
    ]
    params: list[Any] = [*sorted(active_peer_refs), target_ref]

    if excluded_supplier_refs:
        excluded_placeholders = ",".join("?" for _ in excluded_supplier_refs)
        where_parts.append(
            f"SUBSTR(TRIM(to_label), 1, 5) NOT IN ({excluded_placeholders})"
        )
        params.extend(sorted(excluded_supplier_refs))

    where_parts.extend(period_parts)
    params.extend(period_params)

    return conn.execute(
        f"""
        SELECT
          SUBSTR(TRIM(from_label), 1, 5) AS peer_ref,
          SUBSTR(TRIM(to_label), 1, 5) AS supplier_ref,
          COUNT(*) AS tx_count,
          COALESCE(SUM(amount), 0) AS volume
        FROM transactions
        WHERE {" AND ".join(where_parts)}
        GROUP BY
          SUBSTR(TRIM(from_label), 1, 5),
          SUBSTR(TRIM(to_label), 1, 5)
        ORDER BY volume DESC, tx_count DESC
        """,
        params,
    ).fetchall()



# REUSE_PROSPECTS001D_REPLACE_MAIN_FUNCTION
def _empirical_network_peer_refs(
    conn: sqlite3.Connection,
    *,
    professional_ref: str,
    start: str | None,
    end: str | None,
) -> list[str]:
    """Pairs empiriques : pros qui paient d'autres pros sur la période."""
    period_parts, period_params = _period_where(start, end)

    where_parts = [
        "SUBSTR(TRIM(from_label), 1, 5) GLOB 'P[0-9][0-9][0-9][0-9]'",
        "SUBSTR(TRIM(to_label), 1, 5) GLOB 'P[0-9][0-9][0-9][0-9]'",
        "SUBSTR(TRIM(from_label), 1, 5) NOT IN ('P0000', 'P9999')",
        "SUBSTR(TRIM(to_label), 1, 5) NOT IN ('P0000', 'P9999')",
        "SUBSTR(TRIM(from_label), 1, 5) <> ?",
        "SUBSTR(TRIM(to_label), 1, 5) <> ?",
    ]
    where_parts.extend(period_parts)

    rows = conn.execute(
        f"""
        SELECT DISTINCT SUBSTR(TRIM(from_label), 1, 5) AS peer_ref
        FROM transactions
        WHERE {" AND ".join(where_parts)}
        ORDER BY peer_ref ASC
        """,
        [professional_ref, professional_ref, *period_params],
    ).fetchall()

    return [row["peer_ref"] for row in rows if row["peer_ref"]]


def _signal_level(peer_count: int, peer_share_pct: float) -> str:
    if peer_count >= 3 or peer_share_pct >= 30:
        return "strong"
    if peer_count >= 2 or peer_share_pct >= 15:
        return "medium"
    return "exploratory"


def get_professional_reuse_prospects(
    professional_ref: str,
    *,
    start: str | None = None,
    end: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    normalized_ref = _normalize_professional_ref(professional_ref)
    clean_limit = max(1, min(MAX_LIMIT, _safe_int(limit, DEFAULT_LIMIT)))

    with _connect() as conn:
        period = _resolve_period(conn, start, end)
        effective_start = period["effective_start"]
        effective_end = period["effective_end"]

        target = _professional_identity(conn, normalized_ref)
        target_industry = _clean_text(target.get("industry_name"))

        if target_industry:
            analysis_mode = "same_sector_odoo"
            same_sector_peers = _same_sector_peers(
                conn,
                professional_ref=normalized_ref,
                industry_name=target_industry,
            )
            active_peer_refs = _active_peer_refs(
                conn,
                peer_refs=same_sector_peers,
                start=effective_start,
                end=effective_end,
            )
        else:
            analysis_mode = "empirical_b2b_network"
            same_sector_peers = []
            active_peer_refs = set(_empirical_network_peer_refs(
                conn,
                professional_ref=normalized_ref,
                start=effective_start,
                end=effective_end,
            ))

        already_paid_in_period = _suppliers_already_paid_by_target(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
        )

        paid_before_period = _suppliers_paid_before_period(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
        )

        already_buys_from_target = _professionals_paying_target_in_period(
            conn,
            professional_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
        )

        candidate_rows = _candidate_supplier_rows(
            conn,
            active_peer_refs=active_peer_refs,
            excluded_supplier_refs=already_paid_in_period,
            target_ref=normalized_ref,
            start=effective_start,
            end=effective_end,
        )

        candidates_by_supplier: dict[str, dict[str, Any]] = {}

        for row in candidate_rows:
            supplier_ref = row["supplier_ref"]
            peer_ref = row["peer_ref"]
            tx_count = _safe_int(row["tx_count"])
            volume = _safe_float(row["volume"])

            candidate = candidates_by_supplier.setdefault(
                supplier_ref,
                {
                    "supplier_ref": supplier_ref,
                    "peer_refs": set(),
                    "peer_examples": [],
                    "tx_count": 0,
                    "volume": 0.0,
                },
            )

            candidate["peer_refs"].add(peer_ref)
            candidate["peer_examples"].append({
                "professional_ref": peer_ref,
                "tx_count": tx_count,
                "volume": volume,
            })
            candidate["tx_count"] += tx_count
            candidate["volume"] += volume

        all_refs: set[str] = set(candidates_by_supplier.keys()) | set(active_peer_refs)
        professional_info = _professional_lookup(conn, all_refs)

        active_peer_count = len(active_peer_refs)
        items: list[dict[str, Any]] = []

        for supplier_ref, candidate in candidates_by_supplier.items():
            peer_refs = candidate["peer_refs"]
            peer_count = len(peer_refs)
            peer_share_pct = (
                100.0 * peer_count / active_peer_count
                if active_peer_count > 0
                else 0.0
            )

            info = professional_info.get(supplier_ref, {})

            peer_examples = sorted(
                candidate["peer_examples"],
                key=lambda example: (
                    -_safe_float(example.get("volume")),
                    -_safe_int(example.get("tx_count")),
                    str(example.get("professional_ref") or ""),
                ),
            )[:4]

            enriched_peer_examples = []
            for example in peer_examples:
                peer_ref = example["professional_ref"]
                peer_info = professional_info.get(peer_ref, {})
                enriched_peer_examples.append({
                    "professional_ref": peer_ref,
                    "name": peer_info.get("name") or peer_ref,
                    "tx_count": _safe_int(example.get("tx_count")),
                    "volume": _safe_float(example.get("volume")),
                })

            items.append({
                "professional_ref": supplier_ref,
                "name": info.get("name") or supplier_ref,
                "industry_name": info.get("industry_name"),
                "detailed_activity": info.get("detailed_activity"),
                "zip": info.get("zip"),
                "city": info.get("city"),
                "peer_count": peer_count,
                "peer_share_pct": peer_share_pct,
                "tx_count": candidate["tx_count"],
                "volume": candidate["volume"],
                "signal_level": _signal_level(peer_count, peer_share_pct),
                "already_buys_from_target_in_period": supplier_ref in already_buys_from_target,
                "paid_before_period": supplier_ref in paid_before_period,
                "peer_examples": enriched_peer_examples,
            })

        items.sort(
            key=lambda item: (
                -_safe_int(item["peer_count"]),
                -_safe_float(item["peer_share_pct"]),
                -_safe_float(item["volume"]),
                -_safe_int(item["tx_count"]),
                str(item["professional_ref"]),
            )
        )

        displayed_items = items[:clean_limit]

        return {
            "status": "ok",
            "professional_ref": normalized_ref,
            "requested_period": {
                "start": period["requested_start"],
                "end": period["requested_end"],
            },
            "effective_period": {
                "start": effective_start,
                "end": effective_end,
            },
            "bounds": {
                "min_date": period["min_date"],
                "max_date": period["max_date"],
            },
            "target": target,
            "summary": {
                "analysis_mode": analysis_mode,
                "target_industry_name": target_industry,
                "same_sector_peer_count": len(same_sector_peers),
                "active_peer_count": active_peer_count,
                "candidate_count_total": len(items),
                "candidate_count_displayed": len(displayed_items),
            },
            "items": displayed_items,
            "status_detail": "ok" if target_industry else "empirical_fallback_missing_target_industry",
        }
