from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from server.database import DB_PATH, init_db


APP_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = APP_ROOT / "server"

DATA_DIR = SERVER_DIR / "data"
LOCKS_DIR = DATA_DIR / "locks"

SEED_DIR = SERVER_DIR / "bootstrap_seed"
SEED_INFO_PAGES_DIR = SEED_DIR / "info_pages"

SEED_FILES = {
    SEED_DIR / "prenoms.csv": DATA_DIR / "prenoms.csv",
    SEED_DIR / "device_private_actor_registry.json": DATA_DIR / "device_private_actor_registry.json",
    SEED_DIR / "info_pages_custom.json": DATA_DIR / "info_pages_custom.json",
    SEED_DIR / "info_pages_overrides.json": DATA_DIR / "info_pages_overrides.json",
}

USER_MAPPING_PATH = DATA_DIR / "user_mapping.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def copy_file_if_missing(source: Path, target: Path) -> str:
    if target.exists():
        return "déjà présent"

    if not source.exists():
        raise FileNotFoundError(f"Ressource d’amorçage absente : {source}")

    target.parent.mkdir(parents=True, exist_ok=True)

    tmp = target.with_name(f".{target.name}.bootstrap.tmp")
    shutil.copy2(source, tmp)
    tmp.replace(target)

    return "copié"


def copy_info_pages_if_missing() -> tuple[int, int]:
    if not SEED_INFO_PAGES_DIR.exists():
        raise FileNotFoundError(
            f"Répertoire d’amorçage des fiches info absent : {SEED_INFO_PAGES_DIR}"
        )

    target_dir = DATA_DIR / "info_pages"
    target_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    preserved = 0

    for source in sorted(SEED_INFO_PAGES_DIR.glob("*.md")):
        target = target_dir / source.name
        status = copy_file_if_missing(source, target)

        if status == "copié":
            copied += 1
        else:
            preserved += 1

    return copied, preserved


def ensure_empty_user_mapping_if_missing() -> str:
    if USER_MAPPING_PATH.exists():
        return "déjà présent"

    USER_MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = USER_MAPPING_PATH.with_name(".user_mapping.json.bootstrap.tmp")
    tmp.write_text("{}\n", encoding="utf-8")
    tmp.replace(USER_MAPPING_PATH)

    return "créé"


def bootstrap_install_only() -> int:
    print("========================================================================")
    print("MLCFlux bootstrap — mode install-only")
    print("========================================================================")
    print(f"Horodatage UTC : {utc_now_iso()}")
    print(f"Racine app     : {APP_ROOT}")
    print(f"Data dir       : {DATA_DIR}")
    print(f"Seed dir       : {SEED_DIR}")
    print(f"Base SQLite    : {DB_PATH}")
    print()

    print("1. Préparation des répertoires runtime")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   OK {DATA_DIR}")
    print(f"   OK {LOCKS_DIR}")
    print()

    print("2. Déploiement des données d’amorçage")
    try:
        for source, target in SEED_FILES.items():
            status = copy_file_if_missing(source, target)
            print(f"   {status.upper():14} {target}")

        copied_pages, preserved_pages = copy_info_pages_if_missing()
        print(
            f"   INFO_PAGES    {copied_pages} copiée(s), "
            f"{preserved_pages} déjà présente(s)"
        )
    except FileNotFoundError as exc:
        print(f"   ERREUR {exc}")
        return 2

    print()

    print("3. Initialisation du mapping de pseudonymes")
    mapping_status = ensure_empty_user_mapping_if_missing()
    print(f"   {mapping_status.upper():14} {USER_MAPPING_PATH}")
    print()

    print("4. Initialisation du schéma SQLite")
    init_db()

    if not DB_PATH.exists():
        print(f"   ERREUR base SQLite non créée : {DB_PATH}")
        return 3

    print(f"   OK {DB_PATH}")
    print()

    print("========================================================================")
    print("Bootstrap install-only terminé avec succès.")
    print("========================================================================")
    return 0


def parse_iso_day(value: str, *, field_name: str) -> str:
    raw = str(value or "").strip()

    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} invalide : {raw!r}. Format attendu : YYYY-MM-DD."
        ) from exc

    return parsed.isoformat()


def rebuild_years(date_from: str, date_to: str) -> list[int]:
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)

    if end < start:
        raise ValueError(
            f"Période invalide : date_to ({date_to}) est antérieure à "
            f"date_from ({date_from})."
        )

    return list(range(start.year, end.year + 1))


def run_rebuild_step(label: str, command: list[str]) -> None:
    print()
    print("========================================================================")
    print(label)
    print("========================================================================")
    print("Commande :", " ".join(command))
    print()
    sys.stdout.flush()

    subprocess.run(command, check=True)


def bootstrap_rebuild_core(*, date_from: str, date_to: str) -> int:
    try:
        normalized_date_from = parse_iso_day(date_from, field_name="--date-from")
        normalized_date_to = parse_iso_day(date_to, field_name="--date-to")
        years = rebuild_years(normalized_date_from, normalized_date_to)
    except ValueError as exc:
        print(f"ERREUR {exc}", file=sys.stderr)
        return 2

    print("========================================================================")
    print("MLCFlux bootstrap — mode rebuild-core")
    print("========================================================================")
    print(f"Période de reconstruction : {normalized_date_from} -> {normalized_date_to}")
    print(f"Années Odoo annuelles      : {', '.join(map(str, years))}")
    print()

    install_status = bootstrap_install_only()
    if install_status != 0:
        print()
        print("ERREUR : install-only a échoué, rebuild-core interrompu.")
        return install_status

    python = sys.executable

    monetary_year_args: list[str] = []
    for year in years:
        monetary_year_args.extend(["--year", str(year)])

    steps: list[tuple[str, list[str]]] = [
        (
            "1. Synchronisation des transactions Cyclos",
            [
                python,
                "-m",
                "server.sync_transactions",
                "--date-from",
                normalized_date_from,
                "--date-to",
                normalized_date_to,
            ],
        ),
        (
            "2. Reconstruction actor.id ↔ user.id — particuliers",
            [
                python,
                "-m",
                "server.sync_cyclos_actor_user_links",
                "--date-from",
                normalized_date_from,
                "--date-to",
                normalized_date_to,
            ],
        ),
        (
            "3. Reconstruction Pxxxx ↔ actor.id ↔ user.id — professionnels",
            [
                python,
                "-m",
                "server.sync_cyclos_professional_actor_user_links",
                "--date-from",
                normalized_date_from,
                "--date-to",
                normalized_date_to,
            ],
        ),
        (
            "4. Enrichissement Odoo — professionnels",
            [
                python,
                "-m",
                "server.sync_odoo_professional_enrichment",
            ],
        ),
        (
            "5. Enrichissement Odoo — particuliers",
            [
                python,
                "-m",
                "server.sync_odoo_individual_enrichment",
            ],
        ),
        (
            "6. Indicateurs monétaires Odoo — annuels",
            [
                python,
                "-m",
                "server.sync_odoo_monetary_indicators",
                *monetary_year_args,
            ],
        ),
        (
            "7. Indicateurs monétaires Odoo — quotidiens",
            [
                python,
                "-m",
                "server.sync_odoo_monetary_indicators_daily",
                "--date-from",
                normalized_date_from,
                "--date-to",
                normalized_date_to,
            ],
        ),
        (
            "8. Synthèse des chaînes de circulation professionnelles",
            [
                python,
                "-m",
                "server.sync_professional_chain_fate_summary",
            ],
        ),
        (
            "9. Reconstruction des périmètres postaux U→P",
            [
                python,
                "-m",
                "server.sync_consumption_postal_areas",
            ],
        ),
        (
            "10. Audit d’intégrité rapide",
            [
                python,
                "-m",
                "server.check_db_integrity",
                "--level",
                "quick",
                "--output-dir",
                str(DATA_DIR / "audits"),
                "--prefix",
                "BOOT002_REBUILD_CORE",
            ],
        ),
    ]

    try:
        for label, command in steps:
            run_rebuild_step(label, command)
    except subprocess.CalledProcessError as exc:
        print()
        print("========================================================================")
        print("REBUILD-CORE INTERROMPU")
        print("========================================================================")
        print(f"Étape en échec : {exc.cmd}")
        print(f"Code retour    : {exc.returncode}")
        return exc.returncode or 1

    print()
    print("========================================================================")
    print("Bootstrap rebuild-core terminé avec succès.")
    print("========================================================================")
    return 0



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prépare une instance MLCFlux vierge : répertoires runtime, "
            "données d’amorçage et base SQLite initiale."
        )
    )
    parser.add_argument(
        "--mode",
        choices=["install-only", "rebuild-core"],
        default="install-only",
        help=(
            "Mode de bootstrap. "
            "install-only prépare l’instance vide ; "
            "rebuild-core reconstruit le socle analytique principal."
        ),
    )
    parser.add_argument(
        "--date-from",
        dest="date_from",
        help=(
            "Date de début inclusive au format YYYY-MM-DD. "
            "Requis avec --mode rebuild-core."
        ),
    )
    parser.add_argument(
        "--date-to",
        dest="date_to",
        help=(
            "Date de fin inclusive au format YYYY-MM-DD. "
            "Requis avec --mode rebuild-core."
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "install-only":
        return bootstrap_install_only()

    if args.mode == "rebuild-core":
        if not args.date_from or not args.date_to:
            parser.error(
                "--mode rebuild-core requiert --date-from YYYY-MM-DD "
                "et --date-to YYYY-MM-DD."
            )

        return bootstrap_rebuild_core(
            date_from=args.date_from,
            date_to=args.date_to,
        )

    print(f"Mode non géré : {args.mode}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
