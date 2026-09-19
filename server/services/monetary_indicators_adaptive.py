from __future__ import annotations

from typing import Any

from server.database import get_connection
from server.mlc_context import get_default_mlc_id


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_adaptive_monetary_indicators(
    mlc_id: str | None = None,
) -> dict[str, Any]:
    """
    Retourne les indicateurs monétaires depuis le modèle interne MLCFlux.

    En mode standalone, ce service ne sélectionne aucun provider et
    n'ouvre aucune autre instance. Les adaptateurs amont sont responsables
    d'alimenter monetary_indicators_yearly.
    """
    configured_mlc_id = get_default_mlc_id()
    requested_mlc_id = str(
        mlc_id or configured_mlc_id
    ).strip()

    if requested_mlc_id != configured_mlc_id:
        raise ValueError(
            "Cette installation standalone ne peut lire que "
            f"l'instance configurée {configured_mlc_id!r}, "
            f"pas {requested_mlc_id!r}."
        )

    conn = get_connection()

    try:
        table_exists = conn.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'monetary_indicators_yearly'
            LIMIT 1
        """).fetchone()

        if table_exists is None:
            return {
                "mlc_id": configured_mlc_id,
                "source": "monetary_indicators_yearly",
                "source_label": "Indicateurs monétaires internes",
                "confidence": "high",
                "available": False,
                "items": [],
                "latest": None,
                "warnings": [
                    "Le modèle interne ne contient pas "
                    "monetary_indicators_yearly."
                ],
                "debug": {
                    "table": "monetary_indicators_yearly",
                    "reason": "table_missing",
                },
            }

        rows = conn.execute("""
            SELECT
                year,
                numeric_circulation,
                paper_circulation,
                total_circulation,
                numeric_guarantee_fund,
                paper_guarantee_fund,
                numeric_guarantee_gap,
                paper_guarantee_gap,
                fetched_at,
                source
            FROM monetary_indicators_yearly
            ORDER BY year ASC
        """).fetchall()

    finally:
        conn.close()

    items = [
        {
            "year": row["year"],
            "digital_circulation": _safe_float(
                row["numeric_circulation"]
            ),
            "paper_circulation": _safe_float(
                row["paper_circulation"]
            ),
            "total_monetary_mass": _safe_float(
                row["total_circulation"]
            ),
            "digital_guarantee": _safe_float(
                row["numeric_guarantee_fund"]
            ),
            "paper_guarantee": _safe_float(
                row["paper_guarantee_fund"]
            ),
            "digital_gap": _safe_float(
                row["numeric_guarantee_gap"]
            ),
            "paper_gap": _safe_float(
                row["paper_guarantee_gap"]
            ),
            "fetched_at": row["fetched_at"],
            "source": row["source"],
        }
        for row in rows
    ]

    return {
        "mlc_id": configured_mlc_id,
        "source": "monetary_indicators_yearly",
        "source_label": "Indicateurs monétaires internes",
        "confidence": "high",
        "available": bool(items),
        "items": items,
        "latest": items[-1] if items else None,
        "warnings": (
            []
            if items
            else [
                "Aucun indicateur monétaire annuel n'est "
                "disponible dans le modèle interne."
            ]
        ),
        "debug": {
            "table": "monetary_indicators_yearly",
            "row_count": len(items),
        },
    }
