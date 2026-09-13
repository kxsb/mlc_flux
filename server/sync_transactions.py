from datetime import datetime, UTC
import argparse
import inspect

from server import create_app
from server.database import init_db, get_connection
from server.services.cyclos_client import get_transactions
from server.utils.anonymizer import anonymize_transactions
from server.input_contract.shadow import materialize_cyclos_shadow
from server.runtime_lock import exclusive_transaction_sync_lock


def save_sync_state(status, message, *, sync_name="daily_sync"):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO sync_state (sync_name, last_run_at, last_status, last_message)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(sync_name) DO UPDATE SET
            last_run_at=excluded.last_run_at,
            last_status=excluded.last_status,
            last_message=excluded.last_message
    """, (
        sync_name,
        datetime.now(UTC).isoformat(),
        status,
        message,
    ))

    conn.commit()
    conn.close()


def insert_transactions(transactions, *, return_stats=False):
    """
    Insère ou met à jour un lot de transactions legacy.

    Par compatibilité, la fonction retourne le nombre de lignes upsertées.
    Avec return_stats=True, elle distingue en plus les transactions réellement
    nouvelles de celles qui existaient déjà avant le lot.
    """
    conn = get_connection()
    cur = conn.cursor()

    upserted = 0
    inserted_new = 0
    existing = 0

    for tx in transactions:
        transaction_number = tx.get("transactionNumber")
        cyclos_id = tx.get("id")

        already_exists = cur.execute("""
            SELECT 1
            FROM transactions
            WHERE transaction_number = ?
               OR (? IS NOT NULL AND cyclos_id = ?)
            LIMIT 1
        """, (
            transaction_number,
            cyclos_id,
            cyclos_id,
        )).fetchone() is not None

        cur.execute("""
            INSERT INTO transactions (
                transaction_number,
                cyclos_id,
                date,
                group_label,
                from_label,
                to_label,
                amount,
                type_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET
                cyclos_id=excluded.cyclos_id,
                date=excluded.date,
                group_label=excluded.group_label,
                from_label=excluded.from_label,
                to_label=excluded.to_label,
                amount=excluded.amount,
                type_label=excluded.type_label
        """, (
            transaction_number,
            cyclos_id,
            tx.get("date"),
            tx.get("group"),
            tx.get("from"),
            tx.get("to"),
            float(tx.get("amount")) if tx.get("amount") is not None else None,
            tx.get("type"),
        ))

        upserted += 1

        if already_exists:
            existing += 1
        else:
            inserted_new += 1

    conn.commit()
    conn.close()

    stats = {
        "upserted": upserted,
        "inserted_new": inserted_new,
        "existing": existing,
    }

    if return_stats:
        return stats

    return upserted


def _insert_transactions_for_sync(transactions):
    """
    Appelle l'écriture legacy en demandant les statistiques lorsqu'elles sont
    supportées.

    Certains tests historiques (et d'éventuels consommateurs externes qui
    monkeypatchent cette fonction) exposent encore l'ancienne signature
    insert_transactions(rows) -> int. On conserve cette compatibilité sans
    masquer un TypeError réellement levé à l'intérieur de l'implémentation.
    """
    parameters = inspect.signature(insert_transactions).parameters

    if "return_stats" in parameters:
        result = insert_transactions(
            transactions,
            return_stats=True,
        )
    else:
        result = insert_transactions(transactions)

    if isinstance(result, dict):
        return {
            "upserted": int(result["upserted"]),
            "inserted_new": int(result["inserted_new"]),
            "existing": int(result["existing"]),
        }

    # Compatibilité ancienne : le nombre de lignes upsertées est connu,
    # mais pas leur ventilation nouvelles / déjà présentes.
    return {
        "upserted": int(result),
        "inserted_new": None,
        "existing": None,
    }


def _sync_write_summary(insert_stats):
    upserted = insert_stats["upserted"]
    inserted_new = insert_stats["inserted_new"]
    existing = insert_stats["existing"]

    if inserted_new is None or existing is None:
        return f"{upserted} transactions upsertées"

    return (
        f"{upserted} transactions upsertées ; "
        f"{inserted_new} nouvelle(s), {existing} déjà présente(s)"
    )


def _shadow_coverage_kwargs(raw_transactions):
    """Propage uniquement les bornes attestées par le client source.

    Les listes historiques ou les mocks de tests n'ont pas ces attributs et
    conservent donc le comportement antérieur : aucune couverture n'est inventée
    à partir des dates min/max du lot.
    """
    kwargs = {}

    for field in ("coverage_from", "coverage_to"):
        value = getattr(raw_transactions, field, None)
        if value is not None:
            kwargs[field] = value

    return kwargs


def _run_sync_locked(
    *,
    effective_days,
    date_from,
    date_to,
    sync_name,
    sync_mode,
):
    app = create_app()

    with app.app_context():
        init_db()

        raw_transactions = get_transactions(
            days=effective_days,
            date_from=date_from,
            date_to=date_to,
        )
        safe_transactions = anonymize_transactions(raw_transactions)
        insert_stats = _insert_transactions_for_sync(
            safe_transactions
        )

        fetched = len(raw_transactions)
        upserted = insert_stats["upserted"]
        inserted_new = insert_stats["inserted_new"]
        existing = insert_stats["existing"]

        # INPUT001 reste un miroir de contrôle.
        #
        # Une erreur du shadow ne doit jamais invalider une écriture
        # legacy déjà réussie : le pipeline de production continue
        # actuellement de dépendre de mlcflux.db.
        try:
            shadow_result = materialize_cyclos_shadow(
                raw_transactions,
                **_shadow_coverage_kwargs(raw_transactions),
            )
        except Exception as exc:
            shadow_result = {
                "enabled": True,
                "status": "error",
                "error_type": type(exc).__name__,
            }

            print(
                "INPUT001 SHADOW ERROR - "
                f"{type(exc).__name__}: {exc}"
            )

        shadow_status = shadow_result.get(
            "status",
            "unknown",
        )
        write_summary = _sync_write_summary(insert_stats)
        state_message = (
            f"{write_summary} sur {fetched} récupérées ; "
            f"INPUT001 shadow={shadow_status}"
        )

        # Le chemin quotidien conserve l'appel historique à deux arguments.
        # Le nom explicite n'est nécessaire que pour l'état de réconciliation.
        if sync_name == "daily_sync":
            save_sync_state(
                status="success",
                message=state_message,
            )
        else:
            save_sync_state(
                status="success",
                message=state_message,
                sync_name=sync_name,
            )

        print(
            "SYNC OK - "
            f"{fetched} transactions récupérées, "
            f"{write_summary}, "
            f"INPUT001 shadow={shadow_status}"
        )

        return {
            "mode": sync_mode,
            "fetched": fetched,
            # Compatibilité avec les consommateurs historiques.
            "written": upserted,
            "upserted": upserted,
            "inserted_new": inserted_new,
            "existing": existing,
            "input001_shadow": shadow_result,
            # Une absence dans un lot source n'entraîne jamais de suppression.
            # Les annulations / suppressions source restent à spécifier avec le
            # producteur avant toute politique destructive.
            "source_absence_policy": "preserve",
        }


def run_sync(
    days=None,
    date_from=None,
    date_to=None,
    reconcile_days=None,
):
    """
    Synchronise les transactions Cyclos vers SQLite.

    Sans argument :
    - comportement quotidien par défaut du client Cyclos, actuellement 48h.

    Avec arguments :
    - days=N : fenêtre glissante manuelle ;
    - date_from/date_to : période calendaire explicite ;
    - reconcile_days=N : réconciliation historique glissante. Ce mode utilise
      le même upsert idempotent mais possède un état de sync distinct afin de
      ne pas masquer le résultat de la synchronisation quotidienne.

    Toute exécution de ce service partagé prend le verrou transactionnel de
    l'instance. Les routes HTTP qui appellent directement run_sync ne peuvent
    donc plus contourner la sérialisation appliquée aux CLI.
    """
    if reconcile_days is not None:
        if days is not None or date_from is not None or date_to is not None:
            raise ValueError(
                "reconcile_days est exclusif de days/date_from/date_to."
            )

        if reconcile_days <= 0:
            raise ValueError(
                "reconcile_days doit être un entier strictement positif."
            )

    sync_name = (
        "reconciliation_sync"
        if reconcile_days is not None
        else "daily_sync"
    )
    sync_mode = (
        "reconciliation"
        if reconcile_days is not None
        else "daily"
    )
    effective_days = (
        reconcile_days
        if reconcile_days is not None
        else days
    )

    with exclusive_transaction_sync_lock(operation=sync_name):
        return _run_sync_locked(
            effective_days=effective_days,
            date_from=date_from,
            date_to=date_to,
            sync_name=sync_name,
            sync_mode=sync_mode,
        )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Synchronise les transactions Cyclos vers la base SQLite MLCFlux."
    )

    period_group = parser.add_mutually_exclusive_group()

    period_group.add_argument(
        "--days",
        type=int,
        default=None,
        help="Nombre de jours glissants à récupérer depuis maintenant.",
    )

    period_group.add_argument(
        "--date-from",
        dest="date_from",
        type=str,
        default=None,
        help="Date de début, au format YYYY-MM-DD ou ISO 8601.",
    )

    period_group.add_argument(
        "--reconcile-days",
        dest="reconcile_days",
        type=int,
        default=None,
        help=(
            "Réconcilie une fenêtre historique glissante de N jours afin de "
            "rattraper les transactions devenues visibles tardivement."
        ),
    )

    parser.add_argument(
        "--date-to",
        dest="date_to",
        type=str,
        default=None,
        help="Date de fin, au format YYYY-MM-DD ou ISO 8601. Requiert --date-from.",
    )

    args = parser.parse_args(argv)

    if args.days is not None and args.days <= 0:
        parser.error("--days doit être un entier strictement positif.")

    if args.reconcile_days is not None and args.reconcile_days <= 0:
        parser.error("--reconcile-days doit être un entier strictement positif.")

    if args.date_to and not args.date_from:
        parser.error("--date-to nécessite --date-from.")

    return args


def main(argv=None):
    args = parse_args(argv)
    sync_name = (
        "reconciliation_sync"
        if args.reconcile_days is not None
        else "daily_sync"
    )

    # Le verrou extérieur garantit qu'un conflit est détecté avant même le
    # bloc de gestion d'erreur / sync_state. run_sync reprend le même verrou de
    # façon réentrante afin de protéger aussi ses appelants HTTP directs.
    with exclusive_transaction_sync_lock(operation=sync_name):
        try:
            run_sync(
                days=args.days,
                date_from=args.date_from,
                date_to=args.date_to,
                reconcile_days=args.reconcile_days,
            )
        except Exception as e:
            app = create_app()
            with app.app_context():
                init_db()
                if sync_name == "daily_sync":
                    save_sync_state(
                        status="error",
                        message=str(e),
                    )
                else:
                    save_sync_state(
                        status="error",
                        message=str(e),
                        sync_name=sync_name,
                    )
            raise

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
