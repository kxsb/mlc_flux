from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Permet :
#   python server/check_db_integrity.py
# aussi bien que :
#   python -m server.check_db_integrity
if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(PROJECT_ROOT))

from server.database import DB_PATH
from server.services.db_integrity import (
    integrity_report_as_json,
    render_integrity_report_text,
    run_db_integrity_test,
)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Teste l’intégrité approfondie de la base SQLite MLCFlux "
            "et produit un rapport TXT + JSON."
        )
    )

    parser.add_argument(
        "--db-path",
        default=str(DB_PATH),
        help=f"Chemin de la base SQLite à contrôler. Défaut : {DB_PATH}",
    )

    parser.add_argument(
        "--level",
        choices=("quick", "full"),
        default="full",
        help=(
            "quick = contrôle allégé ; "
            "full = contrôle approfondi avec PRAGMA integrity_check. Défaut : full."
        ),
    )

    parser.add_argument(
        "--output-dir",
        default="_audits",
        help="Dossier de sortie des rapports. Défaut : _audits",
    )

    parser.add_argument(
        "--prefix",
        default="DBINTEGRITY002",
        help="Préfixe des fichiers de rapport. Défaut : DBINTEGRITY002",
    )

    parser.add_argument(
        "--print-report",
        action="store_true",
        help="Affiche le rapport TXT complet dans le terminal.",
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = _stamp()
    txt_path = output_dir / f"{args.prefix}_{suffix}.txt"
    json_path = output_dir / f"{args.prefix}_{suffix}.json"

    report = run_db_integrity_test(args.db_path, level=args.level)
    text_report = render_integrity_report_text(report)
    json_report = integrity_report_as_json(report)

    txt_path.write_text(text_report + "\n", encoding="utf-8")
    json_path.write_text(json_report + "\n", encoding="utf-8")

    print()
    print("========================================================================")
    print("MLCFlux — Audit d’intégrité DB terminé")
    print("========================================================================")
    print(f"Statut        : {str(report.get('status')).upper()}")
    print(f"OK logique    : {report.get('ok')}")
    print(f"Niveau        : {report.get('level')}")
    print(f"Rapport TXT   : {txt_path}")
    print(f"Rapport JSON  : {json_path}")
    print()

    transactions = report.get("transactions") or {}
    if transactions.get("available"):
        legacy = transactions.get("legacy_labels") or {}
        print("Résumé transactions :")
        print(f"- lignes                     : {transactions.get('count')}")
        print(
            f"- période                    : "
            f"{transactions.get('min_date')} → {transactions.get('max_date')}"
        )
        print(
            f"- doublons cyclos_id         : "
            f"{transactions.get('duplicate_cyclos_id_groups')}"
        )
        print(f"- Acteur masqué              : {legacy.get('acteur_masque_rows')}")
        print(f"- U_user_*                   : {legacy.get('u_user_rows')}")
        print(f"- U_inconnu                  : {legacy.get('u_inconnu_rows')}")
        print()

    print(f"Observations   : {len(report.get('observations') or [])}")
    print(f"Avertissements : {len(report.get('warnings') or [])}")
    print(f"Erreurs        : {len(report.get('errors') or [])}")
    print("========================================================================")

    if args.print_report:
        print()
        print(text_report)

    status = report.get("status")
    if status == "healthy":
        return 0
    if status == "degraded":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
