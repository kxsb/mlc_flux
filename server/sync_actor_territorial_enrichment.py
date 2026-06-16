from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.services.cyclos_client import get_primary_address


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "server" / "data"
INSTANCES_DIR = DATA_DIR / "instances"
AUDIT_DIR = APP_DIR / "_audit_exports"

TABLE_NAME = "actor_territorial_enrichment"


@dataclass
class ActorRef:
    actor_ref: str
    actor_family: str
    actor_id: str | None
    user_id: str | None
    evidence_count: int | None
    source_link_path: str


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "na", "n/a"}:
        return None
    return text


def normalize_postal_code(value: Any) -> tuple[str | None, str]:
    """
    Retourne (postal_code_normalise, status).

    status:
    - strict_valid : déjà 5 chiffres
    - normalizable : extraction simple de 5 chiffres depuis une valeur bruitée
    - missing : vide
    - invalid : non vide mais non exploitable
    """
    raw = _clean_text(value)
    if raw is None:
        return None, "missing"

    if re.fullmatch(r"\d{5}", raw):
        return raw, "strict_valid"

    digits = re.sub(r"\D", "", raw)
    if len(digits) == 5:
        return digits, "normalizable"

    return None, "invalid"


def _instance_dir(mlc_id: str) -> Path:
    return INSTANCES_DIR / mlc_id


def _db_path(mlc_id: str) -> Path:
    return _instance_dir(mlc_id) / "mlcflux.db"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_actor_refs(mlc_id: str) -> list[ActorRef]:
    instance_dir = _instance_dir(mlc_id)

    actor_refs: list[ActorRef] = []

    individual_path = instance_dir / "actor_user_links.json"
    individual_links = (_read_json(individual_path).get("links") or {})
    for key, record in individual_links.items():
        if not isinstance(record, dict):
            continue
        actor_ref = _clean_text(record.get("pseudonym"))
        if not actor_ref:
            continue
        actor_refs.append(
            ActorRef(
                actor_ref=actor_ref,
                actor_family="individual",
                actor_id=_clean_text(record.get("actor_id") or key),
                user_id=_clean_text(record.get("user_id")),
                evidence_count=record.get("evidence_count"),
                source_link_path=str(individual_path.relative_to(APP_DIR)),
            )
        )

    professional_path = instance_dir / "professional_actor_user_links.json"
    professional_links = (_read_json(professional_path).get("links") or {})
    for key, record in professional_links.items():
        if not isinstance(record, dict):
            continue
        actor_ref = _clean_text(record.get("professional_ref") or key)
        if not actor_ref:
            continue
        actor_refs.append(
            ActorRef(
                actor_ref=actor_ref,
                actor_family="professional",
                actor_id=_clean_text(record.get("actor_id")),
                user_id=_clean_text(record.get("user_id")),
                evidence_count=record.get("evidence_count"),
                source_link_path=str(professional_path.relative_to(APP_DIR)),
            )
        )

    actor_refs.sort(key=lambda item: (item.actor_family, item.actor_ref))
    return actor_refs


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            actor_ref TEXT PRIMARY KEY,
            actor_family TEXT NOT NULL,
            actor_id TEXT,
            user_id TEXT,
            evidence_count INTEGER,

            postal_code TEXT,
            raw_postal_code TEXT,
            city TEXT,
            country TEXT,
            latitude REAL,
            longitude REAL,

            source_provider TEXT NOT NULL,
            source_priority INTEGER NOT NULL,
            source_status TEXT NOT NULL,
            source_detail TEXT,

            source_link_path TEXT,
            fetched_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_family
        ON {TABLE_NAME} (actor_family)
        """
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_postal
        ON {TABLE_NAME} (postal_code)
        """
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_source
        ON {TABLE_NAME} (source_provider, source_status)
        """
    )
    conn.commit()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({_qident(table)})").fetchall()
    }


def _fallback_from_existing_tables(
    conn: sqlite3.Connection,
    actor: ActorRef,
) -> dict[str, Any] | None:
    """
    Fallback de transition :
    - particuliers : odoo_individual_enrichment
    - pros : professional_enrichment puis odoo_professional_enrichment

    Ne contacte pas Odoo directement. Lit seulement les données déjà présentes en SQL.
    """
    candidates: list[tuple[str, str, str, str, int]] = []

    if actor.actor_family == "individual":
        candidates.append(
            ("odoo_individual_enrichment", "pseudonym", "zip", "city", 20)
        )
    elif actor.actor_family == "professional":
        candidates.append(
            ("professional_enrichment", "professional_ref", "zip", "city", 20)
        )
        candidates.append(
            ("odoo_professional_enrichment", "professional_ref", "cyclos_zip", "cyclos_city", 30)
        )
        candidates.append(
            ("odoo_professional_enrichment", "professional_ref", "zip", "city", 40)
        )

    for table, key_col, zip_col, city_col, priority in candidates:
        cols = _columns(conn, table)
        if not {key_col, zip_col}.issubset(cols):
            continue

        select_cols = [key_col, zip_col]
        if city_col in cols:
            select_cols.append(city_col)
        if "latitude" in cols:
            select_cols.append("latitude")
        if "longitude" in cols:
            select_cols.append("longitude")

        row = conn.execute(
            f"""
            SELECT {", ".join(_qident(c) for c in select_cols)}
            FROM {_qident(table)}
            WHERE {_qident(key_col)} = ?
            LIMIT 1
            """,
            (actor.actor_ref,),
        ).fetchone()

        if not row:
            continue

        data = dict(zip(select_cols, row))
        postal_code, status = normalize_postal_code(data.get(zip_col))

        if postal_code:
            return {
                "postal_code": postal_code,
                "raw_postal_code": _clean_text(data.get(zip_col)),
                "city": _clean_text(data.get(city_col)),
                "country": None,
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "source_provider": table,
                "source_priority": priority,
                "source_status": status,
                "source_detail": f"fallback_from_{table}",
            }

    return None


def _territorial_row_from_cyclos(actor: ActorRef) -> dict[str, Any]:
    if not actor.user_id:
        return {
            "postal_code": None,
            "raw_postal_code": None,
            "city": None,
            "country": None,
            "latitude": None,
            "longitude": None,
            "source_provider": "cyclos",
            "source_priority": 10,
            "source_status": "missing_user_id",
            "source_detail": "Lien acteur sans user_id Cyclos.",
        }

    try:
        address = get_primary_address(str(actor.user_id))
    except Exception as exc:
        return {
            "postal_code": None,
            "raw_postal_code": None,
            "city": None,
            "country": None,
            "latitude": None,
            "longitude": None,
            "source_provider": "cyclos",
            "source_priority": 10,
            "source_status": "error",
            "source_detail": repr(exc),
        }

    if not isinstance(address, dict):
        return {
            "postal_code": None,
            "raw_postal_code": None,
            "city": None,
            "country": None,
            "latitude": None,
            "longitude": None,
            "source_provider": "cyclos",
            "source_priority": 10,
            "source_status": "no_primary_address",
            "source_detail": "Cyclos ne retourne pas d'adresse primaire exploitable.",
        }

    raw_zip = _clean_text(address.get("cyclos_zip"))
    postal_code, zip_status = normalize_postal_code(raw_zip)

    return {
        "postal_code": postal_code,
        "raw_postal_code": raw_zip,
        "city": _clean_text(address.get("cyclos_city")),
        "country": _clean_text(address.get("cyclos_country")),
        "latitude": address.get("cyclos_latitude"),
        "longitude": address.get("cyclos_longitude"),
        "source_provider": "cyclos",
        "source_priority": 10,
        "source_status": zip_status if postal_code else f"cyclos_{zip_status}",
        "source_detail": "primary_address",
    }


def build_row(
    conn: sqlite3.Connection,
    actor: ActorRef,
) -> dict[str, Any]:
    cyclos_row = _territorial_row_from_cyclos(actor)

    if cyclos_row.get("postal_code"):
        chosen = cyclos_row
    else:
        fallback = _fallback_from_existing_tables(conn, actor)
        if fallback:
            chosen = fallback
            chosen["source_detail"] = (
                f"{chosen.get('source_detail')}; cyclos_status="
                f"{cyclos_row.get('source_status')}"
            )
        else:
            chosen = cyclos_row

    now = _now()
    return {
        "actor_ref": actor.actor_ref,
        "actor_family": actor.actor_family,
        "actor_id": actor.actor_id,
        "user_id": actor.user_id,
        "evidence_count": actor.evidence_count,

        "postal_code": chosen.get("postal_code"),
        "raw_postal_code": chosen.get("raw_postal_code"),
        "city": chosen.get("city"),
        "country": chosen.get("country"),
        "latitude": chosen.get("latitude"),
        "longitude": chosen.get("longitude"),

        "source_provider": chosen.get("source_provider") or "unknown",
        "source_priority": chosen.get("source_priority") or 999,
        "source_status": chosen.get("source_status") or "unknown",
        "source_detail": chosen.get("source_detail"),

        "source_link_path": actor.source_link_path,
        "fetched_at": now,
        "updated_at": now,
    }


def upsert_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    cols = [
        "actor_ref",
        "actor_family",
        "actor_id",
        "user_id",
        "evidence_count",
        "postal_code",
        "raw_postal_code",
        "city",
        "country",
        "latitude",
        "longitude",
        "source_provider",
        "source_priority",
        "source_status",
        "source_detail",
        "source_link_path",
        "fetched_at",
        "updated_at",
    ]

    placeholders = ", ".join("?" for _ in cols)
    update_cols = [c for c in cols if c != "actor_ref"]

    sql = f"""
        INSERT INTO {TABLE_NAME} ({", ".join(cols)})
        VALUES ({placeholders})
        ON CONFLICT(actor_ref) DO UPDATE SET
            {", ".join(f"{c}=excluded.{c}" for c in update_cols)}
    """

    conn.executemany(
        sql,
        [[row.get(c) for c in cols] for row in rows],
    )
    conn.commit()


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_family: dict[str, int] = {}
    by_source: dict[str, int] = {}

    for row in rows:
        by_status[row["source_status"]] = by_status.get(row["source_status"], 0) + 1
        by_family[row["actor_family"]] = by_family.get(row["actor_family"], 0) + 1
        by_source[row["source_provider"]] = by_source.get(row["source_provider"], 0) + 1

    usable = sum(1 for row in rows if row.get("postal_code"))
    return {
        "total": len(rows),
        "usable_with_postal_code": usable,
        "usable_pct": round(usable / len(rows) * 100, 2) if rows else 0,
        "by_family": by_family,
        "by_source": by_source,
        "by_status": by_status,
    }


def export_csv(mlc_id: str, rows: list[dict[str, Any]]) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / f"actor_territorial_enrichment_{mlc_id}_{time.strftime('%Y%m%d_%H%M%S')}.csv"

    fieldnames = [
        "actor_ref",
        "actor_family",
        "actor_id",
        "user_id",
        "evidence_count",
        "postal_code",
        "raw_postal_code",
        "city",
        "country",
        "latitude",
        "longitude",
        "source_provider",
        "source_priority",
        "source_status",
        "source_detail",
        "source_link_path",
        "fetched_at",
        "updated_at",
    ]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronise les codes postaux territoriaux acteurs depuis Cyclos vers SQLite."
    )
    parser.add_argument(
        "--mlc",
        default=os.getenv("MLCFLUX_DEFAULT_MLC_ID"),
        help="Instance MLC à traiter, ex: gonette ou graine. Défaut: MLCFLUX_DEFAULT_MLC_ID.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Écrit dans actor_territorial_enrichment. Sans cette option: dry-run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre d'acteurs traités pour test.",
    )
    parser.add_argument(
        "--family",
        choices=["individual", "professional"],
        default=None,
        help="Filtre optionnel par famille.",
    )
    args = parser.parse_args()

    mlc_id = _clean_text(args.mlc)
    if not mlc_id:
        print("ERREUR: --mlc ou MLCFLUX_DEFAULT_MLC_ID requis.", file=sys.stderr)
        return 2

    db_path = _db_path(mlc_id)
    if not db_path.exists():
        print(f"ERREUR: DB introuvable: {db_path}", file=sys.stderr)
        return 2

    actor_refs = load_actor_refs(mlc_id)
    if args.family:
        actor_refs = [actor for actor in actor_refs if actor.actor_family == args.family]
    if args.limit is not None:
        actor_refs = actor_refs[: args.limit]

    conn = sqlite3.connect(db_path)
    try:
        ensure_table(conn)

        rows: list[dict[str, Any]] = []
        for idx, actor in enumerate(actor_refs, start=1):
            row = build_row(conn, actor)
            rows.append(row)

            if idx == 1 or idx % 25 == 0 or idx == len(actor_refs):
                print(
                    f"[{mlc_id}] {idx}/{len(actor_refs)} "
                    f"{actor.actor_ref} -> {row['postal_code'] or '-'} "
                    f"({row['source_provider']} / {row['source_status']})"
                )

        csv_path = export_csv(mlc_id, rows)

        if args.write:
            upsert_rows(conn, rows)
            mode = "WRITE"
        else:
            mode = "DRY-RUN"

        print()
        print("========================================================================")
        print(f"SYNC ACTOR TERRITORIAL ENRICHMENT — {mlc_id} — {mode}")
        print("========================================================================")
        print("DB :", db_path)
        print("CSV:", csv_path)
        print("Résumé:", json.dumps(summarize(rows), ensure_ascii=False, indent=2))
        print("========================================================================")

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
