#!/usr/bin/env python3
"""
Importe un registre économique professionnel depuis un CSV de décision D006C.

Doctrine :
- Ne modifie jamais professional_enrichment.
- Crée / alimente professional_economic_registry uniquement avec --apply.
- En dry-run, ne fait aucune écriture en base.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NAF_SECTION_LABELS = {
    "A": "Agriculture, sylviculture et pêche",
    "B": "Industries extractives",
    "C": "Industrie manufacturière",
    "D": "Production et distribution d'électricité, de gaz, de vapeur et d'air conditionné",
    "E": "Production et distribution d'eau ; assainissement, gestion des déchets et dépollution",
    "F": "Construction",
    "G": "Commerce ; réparation d'automobiles et de motocycles",
    "H": "Transports et entreposage",
    "I": "Hébergement et restauration",
    "J": "Information et communication",
    "K": "Activités financières et d'assurance",
    "L": "Activités immobilières",
    "M": "Activités spécialisées, scientifiques et techniques",
    "N": "Activités de services administratifs et de soutien",
    "O": "Administration publique",
    "P": "Enseignement",
    "Q": "Santé humaine et action sociale",
    "R": "Arts, spectacles et activités récréatives",
    "S": "Autres activités de services",
    "T": "Activités des ménages en tant qu'employeurs",
    "U": "Activités extra-territoriales",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def normalize_naf(value: Any) -> str:
    raw = clean(value).upper()
    raw = raw.replace(" ", "")
    if re.fullmatch(r"\d{2}\.\d{2}[A-Z]", raw):
        return raw
    compact = raw.replace(".", "")
    if re.fullmatch(r"\d{4}[A-Z]", compact):
        return f"{compact[:2]}.{compact[2:]}"
    return ""


def naf_section_from_code(naf_code: str) -> str:
    compact = normalize_naf(naf_code).replace(".", "")
    if len(compact) < 2 or not compact[:2].isdigit():
        return ""
    div = int(compact[:2])

    if 1 <= div <= 3:
        return "A"
    if 5 <= div <= 9:
        return "B"
    if 10 <= div <= 33:
        return "C"
    if div == 35:
        return "D"
    if 36 <= div <= 39:
        return "E"
    if 41 <= div <= 43:
        return "F"
    if 45 <= div <= 47:
        return "G"
    if 49 <= div <= 53:
        return "H"
    if 55 <= div <= 56:
        return "I"
    if 58 <= div <= 63:
        return "J"
    if 64 <= div <= 66:
        return "K"
    if div == 68:
        return "L"
    if 69 <= div <= 75:
        return "M"
    if 77 <= div <= 82:
        return "N"
    if div == 84:
        return "O"
    if div == 85:
        return "P"
    if 86 <= div <= 88:
        return "Q"
    if 90 <= div <= 93:
        return "R"
    if 94 <= div <= 96:
        return "S"
    if 97 <= div <= 98:
        return "T"
    if div == 99:
        return "U"
    return ""


def luhn_ok(number: str) -> bool:
    ds = [int(x) for x in str(number) if x.isdigit()]
    if not ds:
        return False
    total = 0
    parity = len(ds) % 2
    for idx, digit in enumerate(ds):
        if idx % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def is_real_siret(value: Any) -> bool:
    s = digits(value)
    if len(s) != 14:
        return False
    if len(set(s)) <= 1:
        return False
    if s.startswith("00000"):
        return False
    return luhn_ok(s)


def bool01(value: Any) -> int:
    return 1 if str(value).strip().lower() in {"yes", "true", "1", "oui"} else 0


def confidence_from_bucket(bucket: str) -> str:
    if bucket == "auto_siret_exact":
        return "exact"
    if bucket == "naf_code_high":
        return "high"
    if bucket in {"naf_code_medium", "naf_code_medium_activity_conflict", "naf_section_medium"}:
        return "medium"
    if bucket in {"manual_high", "closed_source_review"}:
        return "manual_high"
    if bucket == "manual_medium":
        return "manual_medium"
    if bucket in {"device_or_event", "not_eligible_functional_account"}:
        return "out_of_scope"
    if bucket == "public_directory_only":
        return "directory_only"
    if bucket == "no_match":
        return "none"
    return "unknown"


def source_layers(row: dict[str, str]) -> list[str]:
    layers: list[str] = ["d006c_decision"]

    if clean(row.get("source_siret")):
        layers.append("cyclos_source_field")
    if clean(row.get("pdf_name")):
        layers.append("public_directory_pdf")
    if clean(row.get("best_siret")) or clean(row.get("best_ape")):
        layers.append("recherche_entreprises_api")
    if clean(row.get("d006c_bucket")):
        layers.append("decision_rules_d006c")

    return layers


def build_record(row: dict[str, str]) -> dict[str, Any]:
    bucket = clean(row.get("d006c_bucket"))
    best_siret = digits(row.get("best_siret"))
    source_siret = digits(row.get("source_siret"))
    best_naf = normalize_naf(row.get("best_ape"))

    siret_exact_safe = bool01(row.get("d006c_siret_exact_safe"))
    naf_usable = bool01(row.get("d006c_naf_usable"))
    manual_required = bool01(row.get("d006c_manual_required"))

    siret = best_siret if siret_exact_safe and is_real_siret(best_siret) else ""

    # SIREN : uniquement dérivé d’un vrai SIRET exact sûr.
    # Les valeurs Cyclos 00000+SIREN ne deviennent pas des SIRET.
    siren = siret[:9] if siret else ""
    siren_source = "derived_from_exact_siret" if siren else ""

    # NAF :
    # - code détaillé seulement pour auto_siret_exact / naf_code_* ;
    # - section seule pour naf_section_medium.
    naf_code = ""
    naf_section = ""

    if naf_usable:
        if bucket in {
            "auto_siret_exact",
            "naf_code_high",
            "naf_code_medium",
            "naf_code_medium_activity_conflict",
        }:
            naf_code = best_naf
            naf_section = naf_section_from_code(best_naf)
        elif bucket == "naf_section_medium":
            naf_section = naf_section_from_code(best_naf)

    evidence = {
        "decision_source": "SIRET_DRYRUN006C_DECISION_BALANCED",
        "decision_bucket": bucket,
        "d006c_reason": clean(row.get("d006c_reason")),
        "d006c_db_score": clean(row.get("d006c_db_score")),
        "d006c_pdf_score": clean(row.get("d006c_pdf_score")),
        "d006c_duplicate_siret": clean(row.get("d006c_duplicate_siret")),
        "source_siret_raw": source_siret,
        "source_siren_raw": digits(row.get("source_siren")),
        "candidate_siret": best_siret,
        "candidate_naf": best_naf,
        "candidate_name": clean(row.get("best_name")),
        "candidate_status": clean(row.get("best_status")),
        "pdf_name": clean(row.get("pdf_name")),
        "pdf_activity": clean(row.get("pdf_activity")),
        "pdf_address": clean(row.get("pdf_address")),
        "pdf_area": clean(row.get("pdf_area")),
        "display_name": clean(row.get("display_name")),
        "legal_name": clean(row.get("legal_name")),
    }

    return {
        "professional_ref": clean(row.get("professional_ref")),
        "display_name_snapshot": clean(row.get("display_name")),
        "legal_name_snapshot": clean(row.get("legal_name")),
        "decision_bucket": bucket,
        "confidence_level": confidence_from_bucket(bucket),
        "economic_status": bucket,
        "siret": siret,
        "siren": siren,
        "siren_source": siren_source,
        "naf_code": naf_code,
        "naf_label": "",
        "naf_section": naf_section,
        "naf_section_label": NAF_SECTION_LABELS.get(naf_section, ""),
        "siret_exact_safe": siret_exact_safe,
        "naf_usable": naf_usable,
        "manual_review_required": manual_required,
        "internal_activity_usable": 1,
        "candidate_siret": best_siret,
        "candidate_siren": best_siret[:9] if is_real_siret(best_siret) else "",
        "candidate_name": clean(row.get("best_name")),
        "candidate_status": clean(row.get("best_status")),
        "candidate_naf_code": best_naf,
        "pdf_name": clean(row.get("pdf_name")),
        "pdf_activity": clean(row.get("pdf_activity")),
        "pdf_address": clean(row.get("pdf_address")),
        "source_layers_json": json.dumps(source_layers(row), ensure_ascii=False),
        "evidence_json": json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        "import_batch": "d006c_initial_import",
        "updated_at": now_iso(),
    }


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS professional_economic_registry (
    professional_ref TEXT PRIMARY KEY,
    display_name_snapshot TEXT,
    legal_name_snapshot TEXT,

    decision_bucket TEXT NOT NULL,
    confidence_level TEXT NOT NULL,
    economic_status TEXT NOT NULL,

    siret TEXT,
    siren TEXT,
    siren_source TEXT,

    naf_code TEXT,
    naf_label TEXT,
    naf_section TEXT,
    naf_section_label TEXT,

    siret_exact_safe INTEGER NOT NULL DEFAULT 0,
    naf_usable INTEGER NOT NULL DEFAULT 0,
    manual_review_required INTEGER NOT NULL DEFAULT 0,
    internal_activity_usable INTEGER NOT NULL DEFAULT 1,

    candidate_siret TEXT,
    candidate_siren TEXT,
    candidate_name TEXT,
    candidate_status TEXT,
    candidate_naf_code TEXT,

    pdf_name TEXT,
    pdf_activity TEXT,
    pdf_address TEXT,

    source_layers_json TEXT,
    evidence_json TEXT,

    import_batch TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_professional_economic_registry_bucket
ON professional_economic_registry(decision_bucket);

CREATE INDEX IF NOT EXISTS idx_professional_economic_registry_siret
ON professional_economic_registry(siret);

CREATE INDEX IF NOT EXISTS idx_professional_economic_registry_siren
ON professional_economic_registry(siren);

CREATE INDEX IF NOT EXISTS idx_professional_economic_registry_naf_code
ON professional_economic_registry(naf_code);

CREATE INDEX IF NOT EXISTS idx_professional_economic_registry_naf_section
ON professional_economic_registry(naf_section);

CREATE INDEX IF NOT EXISTS idx_professional_economic_registry_manual
ON professional_economic_registry(manual_review_required);
"""


UPSERT_SQL = """
INSERT INTO professional_economic_registry (
    professional_ref,
    display_name_snapshot,
    legal_name_snapshot,
    decision_bucket,
    confidence_level,
    economic_status,
    siret,
    siren,
    siren_source,
    naf_code,
    naf_label,
    naf_section,
    naf_section_label,
    siret_exact_safe,
    naf_usable,
    manual_review_required,
    internal_activity_usable,
    candidate_siret,
    candidate_siren,
    candidate_name,
    candidate_status,
    candidate_naf_code,
    pdf_name,
    pdf_activity,
    pdf_address,
    source_layers_json,
    evidence_json,
    import_batch,
    updated_at
)
VALUES (
    :professional_ref,
    :display_name_snapshot,
    :legal_name_snapshot,
    :decision_bucket,
    :confidence_level,
    :economic_status,
    :siret,
    :siren,
    :siren_source,
    :naf_code,
    :naf_label,
    :naf_section,
    :naf_section_label,
    :siret_exact_safe,
    :naf_usable,
    :manual_review_required,
    :internal_activity_usable,
    :candidate_siret,
    :candidate_siren,
    :candidate_name,
    :candidate_status,
    :candidate_naf_code,
    :pdf_name,
    :pdf_activity,
    :pdf_address,
    :source_layers_json,
    :evidence_json,
    :import_batch,
    :updated_at
)
ON CONFLICT(professional_ref) DO UPDATE SET
    display_name_snapshot = excluded.display_name_snapshot,
    legal_name_snapshot = excluded.legal_name_snapshot,
    decision_bucket = excluded.decision_bucket,
    confidence_level = excluded.confidence_level,
    economic_status = excluded.economic_status,
    siret = excluded.siret,
    siren = excluded.siren,
    siren_source = excluded.siren_source,
    naf_code = excluded.naf_code,
    naf_label = excluded.naf_label,
    naf_section = excluded.naf_section,
    naf_section_label = excluded.naf_section_label,
    siret_exact_safe = excluded.siret_exact_safe,
    naf_usable = excluded.naf_usable,
    manual_review_required = excluded.manual_review_required,
    internal_activity_usable = excluded.internal_activity_usable,
    candidate_siret = excluded.candidate_siret,
    candidate_siren = excluded.candidate_siren,
    candidate_name = excluded.candidate_name,
    candidate_status = excluded.candidate_status,
    candidate_naf_code = excluded.candidate_naf_code,
    pdf_name = excluded.pdf_name,
    pdf_activity = excluded.pdf_activity,
    pdf_address = excluded.pdf_address,
    source_layers_json = excluded.source_layers_json,
    evidence_json = excluded.evidence_json,
    import_batch = excluded.import_batch,
    updated_at = excluded.updated_at;
"""


def load_records(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    records = [build_record(row) for row in rows]

    missing_ref = [r for r in records if not r["professional_ref"]]
    if missing_ref:
        raise ValueError(f"{len(missing_ref)} lignes sans professional_ref")

    refs = [r["professional_ref"] for r in records]
    duplicates = sorted({ref for ref in refs if refs.count(ref) > 1})
    if duplicates:
        raise ValueError(f"professional_ref dupliqués dans le CSV : {duplicates[:20]}")

    return records


def summarize(records: list[dict[str, Any]]) -> Counter[str]:
    summary: Counter[str] = Counter()
    for record in records:
        summary[f"bucket:{record['decision_bucket']}"] += 1
        if record["siret_exact_safe"]:
            summary["siret_exact_safe"] += 1
        if record["siret"]:
            summary["siret_written"] += 1
        if record["naf_usable"]:
            summary["naf_usable"] += 1
        if record["naf_code"]:
            summary["naf_code_written"] += 1
        if record["naf_section"]:
            summary["naf_section_written"] += 1
        if record["manual_review_required"]:
            summary["manual_review_required"] += 1
    summary["total"] = len(records)
    return summary


def backup_db(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_path.with_name(f"{db_path.name}.bak_economic_registry_{timestamp}")
    shutil.copy2(db_path, backup)
    return backup


def apply_import(db_path: Path, records: list[dict[str, Any]], make_backup: bool) -> Path | None:
    backup = backup_db(db_path) if make_backup else None

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.executemany(UPSERT_SQL, records)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return backup


def check_existing_table(db_path: Path) -> tuple[bool, int]:
    conn = sqlite3.connect(db_path)
    try:
        exists = conn.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name='professional_economic_registry'
        """).fetchone() is not None
        count = 0
        if exists:
            count = conn.execute("SELECT COUNT(*) FROM professional_economic_registry").fetchone()[0]
        return exists, count
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"DB introuvable : {args.db}")
    if not args.csv.exists():
        raise SystemExit(f"CSV introuvable : {args.csv}")

    table_exists, before_count = check_existing_table(args.db)
    records = load_records(args.csv)
    summary = summarize(records)

    print("==================================================================")
    print("professional_economic_registry import")
    print("==================================================================")
    print(f"DB : {args.db}")
    print(f"CSV : {args.csv}")
    print(f"Mode : {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Table existait avant : {'oui' if table_exists else 'non'}")
    print(f"Lignes table avant : {before_count}")
    print()

    print("Synthèse préparée")
    for key in ["total", "siret_exact_safe", "siret_written", "naf_usable", "naf_code_written", "naf_section_written", "manual_review_required"]:
        print(f"{key}: {summary[key]}")

    print()
    print("Distribution buckets")
    for key in sorted(k for k in summary if k.startswith("bucket:")):
        print(f"{key.removeprefix('bucket:')}: {summary[key]}")

    print()
    print("Exemples lignes préparées")
    for record in records[:12]:
        print(
            f"{record['professional_ref']} | {record['display_name_snapshot']} | "
            f"bucket={record['decision_bucket']} | "
            f"siret={record['siret'] or '—'} | "
            f"naf={record['naf_code'] or '—'} | "
            f"section={record['naf_section'] or '—'} | "
            f"manual={record['manual_review_required']}"
        )

    if not args.apply:
        print()
        print("Dry-run terminé. Aucune écriture en base.")
        return

    backup = apply_import(args.db, records, make_backup=not args.no_backup)
    table_exists_after, after_count = check_existing_table(args.db)

    print()
    print("Écriture réalisée.")
    if backup:
        print(f"Backup DB : {backup}")
    print(f"Table existe après : {'oui' if table_exists_after else 'non'}")
    print(f"Lignes table après : {after_count}")


if __name__ == "__main__":
    main()
