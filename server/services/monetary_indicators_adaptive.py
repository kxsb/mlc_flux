from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

def _db_path_for_mlc(mlc_id: str) -> Path:
    """
    Chemin SQLite explicite pour éviter toute mutation globale de contexte.

    Important en mode web multi-MLC : ne pas utiliser MLCFLUX_DEFAULT_MLC_ID
    comme sélecteur dynamique dans un service appelé par une route.
    """
    safe_mlc_id = str(mlc_id).strip()
    if not safe_mlc_id:
        raise ValueError("mlc_id vide")

    root = Path(__file__).resolve().parents[1]
    return root / "data" / "instances" / safe_mlc_id / "mlcflux.db"


def _connect_for_mlc(mlc_id: str) -> sqlite3.Connection:
    db_path = _db_path_for_mlc(mlc_id)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _qident(identifier: str) -> str:
    """
    Quote un identifiant SQL SQLite interne.

    Les valeurs attendues ici sont des noms de tables/colonnes internes,
    jamais des valeurs utilisateur. Cette validation évite qu'un identifiant
    dynamique puisse devenir un fragment SQL arbitraire.
    """
    value = str(identifier or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Identifiant SQL invalide: {value!r}")
    return f'"{value}"'


def _table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    if not _table_exists(conn, table_name):
        return []
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({_qident(table_name)})")]


def _first_existing(columns: list[str], candidates: list[str]) -> str | None:
    available = set(columns)
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_profile(mlc_id: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "mlc_profiles" / f"{mlc_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _odoo_yearly(conn: sqlite3.Connection) -> dict[str, Any]:
    table = "odoo_monetary_indicators_yearly"

    if not _table_exists(conn, table):
        return {
            "available": False,
            "reason": "table_missing",
            "items": [],
        }

    columns = _table_columns(conn, table)

    year_col = _first_existing(columns, ["year", "annee"])
    digital_col = _first_existing(
        columns,
        [
            "gonettes_num_circulation",
            "circulation_numerique",
            "numeric_circulation",
            "digital_circulation",
        ],
    )
    paper_col = _first_existing(
        columns,
        [
            "gonettes_paper_circulation",
            "circulation_papier",
            "paper_circulation",
        ],
    )
    total_col = _first_existing(
        columns,
        [
            "masse_monetaire_totale",
            "masse_monetaire_total",
            "total_circulation",
            "monetary_mass_total",
        ],
    )
    guarantee_digital_col = _first_existing(
        columns,
        [
            "fonds_garantie_num",
            "fonds_garantie_numerique",
            "digital_guarantee",
        ],
    )
    guarantee_paper_col = _first_existing(
        columns,
        [
            "fonds_garantie_paper",
            "fonds_garantie_papier",
            "paper_guarantee",
        ],
    )
    gap_digital_col = _first_existing(
        columns,
        [
            "ecart_num",
            "ecart_numerique",
            "digital_gap",
        ],
    )
    gap_paper_col = _first_existing(
        columns,
        [
            "ecart_paper",
            "ecart_papier",
            "paper_gap",
        ],
    )

    if not year_col:
        return {
            "available": False,
            "reason": "year_column_missing",
            "columns": columns,
            "items": [],
        }

    rows = conn.execute(f"SELECT * FROM {_qident(table)} ORDER BY {_qident(year_col)}").fetchall()

    items = []
    for row in rows:
        item = {
            "year": row[year_col],
            "digital_circulation": _safe_float(row[digital_col]) if digital_col else None,
            "paper_circulation": _safe_float(row[paper_col]) if paper_col else None,
            "total_monetary_mass": _safe_float(row[total_col]) if total_col else None,
            "digital_guarantee": _safe_float(row[guarantee_digital_col]) if guarantee_digital_col else None,
            "paper_guarantee": _safe_float(row[guarantee_paper_col]) if guarantee_paper_col else None,
            "digital_gap": _safe_float(row[gap_digital_col]) if gap_digital_col else None,
            "paper_gap": _safe_float(row[gap_paper_col]) if gap_paper_col else None,
        }

        if item["total_monetary_mass"] is None:
            total = 0.0
            has_any = False
            for key in ("digital_circulation", "paper_circulation"):
                if item[key] is not None:
                    total += item[key]
                    has_any = True
            item["total_monetary_mass"] = total if has_any else None

        items.append(item)

    return {
        "available": bool(items),
        "reason": None if items else "table_empty",
        "columns": columns,
        "items": items,
    }


def _cyclos_transaction_proxy(conn: sqlite3.Connection) -> dict[str, Any]:
    """
    Proxy de stock monétaire à partir des flux :
    cumul(monetary_supply) - cumul(monetary_exit).

    Ce n'est PAS une source comptable officielle.
    C'est un indicateur de secours pour MLC sans source de stock disponible.
    """
    if not _table_exists(conn, "transaction_semantics"):
        return {
            "available": False,
            "reason": "transaction_semantics_missing",
            "items": [],
        }

    rows = conn.execute(
        """
        SELECT
          substr(t.date, 1, 4) AS year,
          SUM(CASE WHEN s.monetary_circuit = 'monetary_supply' THEN t.amount ELSE 0 END) AS supply,
          SUM(CASE WHEN s.monetary_circuit = 'monetary_exit' THEN t.amount ELSE 0 END) AS exit_amount
        FROM transactions t
        JOIN transaction_semantics s
          ON s.transaction_number = t.transaction_number
        GROUP BY substr(t.date, 1, 4)
        ORDER BY year
        """
    ).fetchall()

    cumulative = 0.0
    items = []

    for row in rows:
        supply = float(row["supply"] or 0.0)
        exit_amount = float(row["exit_amount"] or 0.0)
        net = supply - exit_amount
        cumulative += net

        items.append(
            {
                "year": row["year"],
                "digital_supply_flow": supply,
                "digital_exit_flow": exit_amount,
                "net_supply_flow": net,
                "digital_circulation_proxy": cumulative,
                "total_monetary_mass": cumulative,
            }
        )

    return {
        "available": bool(items),
        "reason": None if items else "no_flow_data",
        "items": items,
    }


def get_adaptive_monetary_indicators(mlc_id: str) -> dict[str, Any]:
    """
    Retourne une structure commune pour les KPI de masse monétaire.

    La source est adaptative :
    - Odoo comptable si disponible ;
    - Cyclos technical balances plus tard ;
    - proxy transactionnel Cyclos en fallback explicite.
    """
    profile = _load_profile(mlc_id)
    configured = profile.get("monetary_indicators") or {}

    with _connect_for_mlc(mlc_id) as conn:
        odoo = _odoo_yearly(conn)
        proxy = _cyclos_transaction_proxy(conn)

    preferred_source = configured.get("source")

    if preferred_source == "odoo_accounting":
        if odoo["available"]:
            return {
                "mlc_id": mlc_id,
                "source": "odoo_accounting",
                "source_label": "Comptabilité Odoo",
                "confidence": "high",
                "available": True,
                "items": odoo["items"],
                "latest": odoo["items"][-1] if odoo["items"] else None,
                "warnings": [],
                "debug": {"odoo": odoo, "proxy_available": proxy["available"]},
            }

        return {
            "mlc_id": mlc_id,
            "source": "odoo_accounting",
            "source_label": "Comptabilité Odoo",
            "confidence": "high",
            "available": False,
            "items": [],
            "latest": None,
            "warnings": [
                "Source Odoo configurée mais aucune donnée monétaire Odoo n'est disponible dans cette instance."
            ],
            "debug": {"odoo": odoo, "proxy_available": proxy["available"]},
        }

    if preferred_source == "cyclos_technical_balances":
        # Prévu pour Graine : comptes de nantissement / compte dédié.
        # Pas encore implémenté tant que balances-history technique n'est pas validé.
        if proxy["available"]:
            return {
                "mlc_id": mlc_id,
                "source": "cyclos_transaction_proxy",
                "source_label": "Proxy Cyclos par flux",
                "confidence": "low",
                "available": True,
                "items": proxy["items"],
                "latest": proxy["items"][-1] if proxy["items"] else None,
                "warnings": [
                    "La source cible Cyclos technical balances est configurée mais pas encore implémentée.",
                    "Les valeurs retournées sont un proxy cumulatif alimentations - sorties, pas un stock comptable officiel.",
                ],
                "debug": {"configured": configured, "proxy": proxy},
            }

        return {
            "mlc_id": mlc_id,
            "source": "cyclos_technical_balances",
            "source_label": "Soldes comptes techniques Cyclos",
            "confidence": "medium",
            "available": False,
            "items": [],
            "latest": None,
            "warnings": [
                "Source Cyclos technical balances configurée mais non disponible."
            ],
            "debug": {"configured": configured, "proxy": proxy},
        }

    # Auto-détection par défaut.
    if odoo["available"]:
        return {
            "mlc_id": mlc_id,
            "source": "odoo_accounting",
            "source_label": "Comptabilité Odoo",
            "confidence": "high",
            "available": True,
            "items": odoo["items"],
            "latest": odoo["items"][-1] if odoo["items"] else None,
            "warnings": [],
            "debug": {"odoo": odoo},
        }

    if proxy["available"]:
        return {
            "mlc_id": mlc_id,
            "source": "cyclos_transaction_proxy",
            "source_label": "Proxy Cyclos par flux",
            "confidence": "low",
            "available": True,
            "items": proxy["items"],
            "latest": proxy["items"][-1] if proxy["items"] else None,
            "warnings": [
                "Aucune source de stock monétaire officielle disponible ; utilisation d'un proxy cumulatif alimentations - sorties."
            ],
            "debug": {"odoo": odoo, "proxy": proxy},
        }

    return {
        "mlc_id": mlc_id,
        "source": "none",
        "source_label": "Aucune source disponible",
        "confidence": "none",
        "available": False,
        "items": [],
        "latest": None,
        "warnings": [
            "Aucune donnée de masse monétaire disponible pour cette instance."
        ],
        "debug": {"odoo": odoo, "proxy": proxy},
    }



# ---------------------------------------------------------------------------
# Source adaptative Cyclos system balances
# ---------------------------------------------------------------------------
#
# Cette couche garde le comportement historique en fallback, mais utilise
# les soldes quotidiens des comptes système Cyclos lorsque la MLC le permet.
#
# Cas Graine :
# - paper_guarantee / billetCompteNantissement : repère papier / nantissement
# - digital_dedicated / numeriqueCompteDedie : masse numérique
# - technical / technique : compte technique audité mais exclu de la masse totale
#

import sqlite3 as _adaptive_sqlite3
from pathlib import Path as _AdaptivePath


_get_adaptive_monetary_indicators_legacy = get_adaptive_monetary_indicators


def _adaptive_instance_db_path(mlc_id: str) -> _AdaptivePath:
    return (
        _AdaptivePath("server")
        / "data"
        / "instances"
        / str(mlc_id)
        / "mlcflux.db"
    )


def _adaptive_connect_instance_db(mlc_id: str):
    db_path = _adaptive_instance_db_path(mlc_id)
    conn = _adaptive_sqlite3.connect(db_path)
    conn.row_factory = _adaptive_sqlite3.Row
    return conn


def _adaptive_table_exists(cur, table_name: str) -> bool:
    row = cur.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def _get_cyclos_system_monetary_indicators(mlc_id: str) -> dict:
    conn = _adaptive_connect_instance_db(mlc_id)
    cur = conn.cursor()

    try:
        if not _adaptive_table_exists(cur, "cyclos_system_daily_balances"):
            return {
                "mlc_id": mlc_id,
                "source": "cyclos_system_balances",
                "source_label": "Soldes comptes système Cyclos",
                "confidence": "medium",
                "available": False,
                "items": [],
                "latest": None,
                "warnings": [
                    "La table cyclos_system_daily_balances n'est pas encore disponible."
                ],
            }

        rows = cur.execute(
            """
            WITH daily_system_balances AS (
                SELECT
                    balance_date,
                    substr(balance_date, 1, 4) AS year,
                    SUM(
                        CASE
                            WHEN role = 'digital_dedicated'
                            THEN balance
                            ELSE 0.0
                        END
                    ) AS digital_circulation,
                    SUM(
                        CASE
                            WHEN role = 'paper_guarantee'
                            THEN balance
                            ELSE 0.0
                        END
                    ) AS paper_circulation,
                    SUM(
                        CASE
                            WHEN role = 'technical'
                            THEN balance
                            ELSE 0.0
                        END
                    ) AS technical_balance,
                    SUM(
                        CASE
                            WHEN role IN ('digital_dedicated', 'paper_guarantee')
                            THEN balance
                            ELSE 0.0
                        END
                    ) AS total_monetary_mass
                FROM cyclos_system_daily_balances
                WHERE mlc_id = ?
                  AND role IN ('paper_guarantee', 'digital_dedicated', 'technical')
                GROUP BY balance_date
            ),
            yearly_latest_days AS (
                SELECT
                    year,
                    MAX(balance_date) AS snapshot_date
                FROM daily_system_balances
                GROUP BY year
            )
            SELECT
                d.year AS year,
                d.balance_date AS snapshot_date,
                d.digital_circulation,
                d.paper_circulation,
                d.technical_balance,
                d.total_monetary_mass
            FROM daily_system_balances d
            JOIN yearly_latest_days y
              ON y.year = d.year
             AND y.snapshot_date = d.balance_date
            ORDER BY d.year ASC
            """,
            (mlc_id,),
        ).fetchall()

        items = []
        for row in rows:
            items.append({
                "year": int(row["year"]),
                "snapshot_date": row["snapshot_date"],
                "digital_circulation": round(float(row["digital_circulation"] or 0.0), 2),
                "paper_circulation": round(float(row["paper_circulation"] or 0.0), 2),
                "technical_balance": round(float(row["technical_balance"] or 0.0), 2),
                "total_monetary_mass": round(float(row["total_monetary_mass"] or 0.0), 2),
                "digital_guarantee": None,
                "paper_guarantee": None,
                "digital_gap": None,
                "paper_gap": None,
            })

        if not items:
            return {
                "mlc_id": mlc_id,
                "source": "cyclos_system_balances",
                "source_label": "Soldes comptes système Cyclos",
                "confidence": "medium",
                "available": False,
                "items": [],
                "latest": None,
                "warnings": [
                    "Aucun solde de compte système Cyclos n'est disponible pour cette instance."
                ],
            }

        return {
            "mlc_id": mlc_id,
            "source": "cyclos_system_balances",
            "source_label": "Soldes comptes système Cyclos",
            "confidence": "medium",
            "available": True,
            "items": items,
            "latest": items[-1],
            "warnings": [
                "La masse numérique est lue depuis le compte système Cyclos numeriqueCompteDedie.",
                "La masse papier est lue depuis le compte système Cyclos billetCompteNantissement.",
                "Le compte technique Cyclos est conservé comme information d'audit, mais n'est pas intégré à la masse totale."
            ],
        }
    finally:
        conn.close()


def get_adaptive_monetary_indicators(mlc_id: str) -> dict:
    """
    Retourne les indicateurs monétaires adaptatifs.

    Priorité :
    1. soldes système Cyclos si disponibles ;
    2. comportement historique legacy/proxy en fallback.

    Important : on teste les soldes système avant le legacy afin d'éviter
    de recalculer inutilement le proxy transactionnel quand une source de
    stock fiable est déjà disponible.
    """
    system_payload = _get_cyclos_system_monetary_indicators(mlc_id)

    if system_payload.get("available"):
        return system_payload

    return _get_adaptive_monetary_indicators_legacy(mlc_id)
