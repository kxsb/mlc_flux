from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from server.mlc_context import normalize_mlc_id
from server.mlc_profiles import load_mlc_profiles


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = APP_DIR / ".env"
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
ACCOUNT_ID_RE = re.compile(r'("account_id"\s*:\s*")([^"]+)(")')
ACCOUNT_NUMBER_RE = re.compile(r'("account_number"\s*:\s*")([^"]+)(")')


def sanitize_log_text(value: str) -> str:
    if not value:
        return ""
    value = EMAIL_RE.sub("[email masqué]", value)
    value = ACCOUNT_ID_RE.sub(r'\1[account_id masqué]\3', value)
    value = ACCOUNT_NUMBER_RE.sub(r'\1[account_number masqué]\3', value)
    return value


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value:
            try:
                value = shlex.split(value, posix=True)[0]
            except Exception:
                pass

        # L'instance cible doit être contrôlée par --mlc, jamais par le .env.
        if key in {"MLCFLUX_DEFAULT_MLC_ID", "MLCFLUX_ACTIVE_MLC_ID"}:
            continue

        os.environ[key] = value


def configure_instance(mlc_id: str, env_file: Path = DEFAULT_ENV_FILE) -> None:
    mlc_id = normalize_mlc_id(mlc_id)

    load_env_file(env_file)

    os.environ["MLCFLUX_DEFAULT_MLC_ID"] = mlc_id
    os.environ["MLCFLUX_ACTIVE_MLC_ID"] = mlc_id


def save_sync_state(sync_name: str, status: str, message: str) -> None:
    from app import app
    from server.database import get_connection

    with app.app_context():
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO sync_state (sync_name, last_run_at, last_status, last_message)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sync_name) DO UPDATE SET
                    last_run_at=excluded.last_run_at,
                    last_status=excluded.last_status,
                    last_message=excluded.last_message
                """,
                (sync_name, utc_now(), status, message),
            )
            conn.commit()
        finally:
            conn.close()


def run_subprocess_module(
    module: str,
    args: list[str],
    *,
    mlc_id: str,
    env_file: Path,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["MLCFLUX_DEFAULT_MLC_ID"] = mlc_id
    env["MLCFLUX_ACTIVE_MLC_ID"] = mlc_id

    command = [sys.executable, "-m", module, *args]
    started = time.monotonic()

    completed = subprocess.run(
        command,
        cwd=APP_DIR,
        env=env,
        text=True,
        capture_output=True,
    )

    duration = round(time.monotonic() - started, 3)

    return {
        "module": module,
        "args": args,
        "returncode": completed.returncode,
        "duration_seconds": duration,
        "stdout": sanitize_log_text(completed.stdout.strip()),
        "stderr": sanitize_log_text(completed.stderr.strip()),
        "ok": completed.returncode == 0,
    }


def step_result(name: str, status: str, **extra: Any) -> dict[str, Any]:
    return {
        "step": name,
        "status": status,
        "at": utc_now(),
        **extra,
    }


def sync_transactions_service(
    *,
    mlc_id: str,
    date_from: str,
    date_to: str,
    dry_run: bool,
    env_file: Path,
) -> dict[str, Any]:
    configure_instance(mlc_id, env_file)

    from app import app
    from server.database import init_db
    from server.services.cyclos_transaction_sync import sync_cyclos_transactions

    with app.app_context():
        init_db()
        result = sync_cyclos_transactions(
            mlc_id=mlc_id,
            date_from=date_from,
            date_to=date_to,
            limit=None,
            reset=False,
            write=not dry_run,
        )

    if result.get("error"):
        if not dry_run:
            save_sync_state("daily_sync", "error", str(result.get("error")))
        raise RuntimeError(json.dumps(result, ensure_ascii=False))

    if not dry_run:
        message = (
            f"{result.get('inserted', 0)} insérées, "
            f"{result.get('updated', 0)} mises à jour, "
            f"{result.get('skipped', 0)} ignorées "
            f"sur {result.get('selected', 0)} transactions sélectionnées "
            f"({result.get('fetched', 0)} récupérées)"
        )
        save_sync_state("daily_sync", "success", message)

    return result


def rebuild_semantics(
    *,
    mlc_id: str,
    date_from: str,
    date_to: str,
    env_file: Path,
) -> dict[str, Any]:
    configure_instance(mlc_id, env_file)

    from app import app
    from server.database import init_db
    from server.services.transaction_semantics import rebuild_transaction_semantics

    with app.app_context():
        init_db()
        return rebuild_transaction_semantics(
            start=date_from,
            end=date_to,
            reset=True,
        )


def refresh_cache_module(
    module: str,
    *,
    mlc_id: str,
    env_file: Path,
) -> dict[str, Any]:
    return run_subprocess_module(module, [], mlc_id=mlc_id, env_file=env_file)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronise la MLC de cette installation standalone."
    )

    parser.add_argument(
        "--mlc", required=True,
        choices=sorted(profile.id for profile in load_mlc_profiles()),
    )
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--days", type=int, default=3)

    parser.add_argument("--dry-run", action="store_true", help="N'écrit pas les transactions ; saute les étapes sans dry-run sûr.")
    parser.add_argument("--plan-only", action="store_true", help="Affiche le plan sans appeler Cyclos ni écrire en base.")
    parser.add_argument("--continue-on-error", action="store_true")

    parser.add_argument("--skip-heavy-balances", action="store_true")
    parser.add_argument("--skip-balance-reconstruction", action="store_true")
    parser.add_argument("--skip-professional-chain-fate", action="store_true")
    parser.add_argument("--skip-actor-links", action="store_true")
    parser.add_argument("--skip-cyclos-professional-profiles", action="store_true")
    parser.add_argument("--skip-caches", action="store_true")
    parser.add_argument("--skip-integrity", action="store_true")
    parser.add_argument("--skip-odoo", action="store_true")

    parser.add_argument("--include-odoo", action="store_true")
    parser.add_argument("--include-system-balances", action="store_true")
    parser.add_argument("--skip-system-balances", action="store_true")

    parser.add_argument("--limit-users", type=int)
    parser.add_argument("--limit-professionals", type=int)
    parser.add_argument("--professional-profile-days", type=int, default=3650)
    parser.add_argument("--professional-profile-limit", default="none")
    parser.add_argument("--max-windows-per-user", type=int)
    parser.add_argument("--max-windows-per-professional", type=int)
    parser.add_argument("--request-pause-seconds", type=float)

    parser.add_argument("--json-out")

    return parser


def resolve_period(args: argparse.Namespace) -> tuple[str, str]:
    if args.date_from and args.date_to:
        return args.date_from, args.date_to

    if args.date_to and not args.date_from:
        raise ValueError("--date-to nécessite --date-from")

    if args.date_from and not args.date_to:
        return args.date_from, datetime.now(UTC).date().isoformat()

    if args.days <= 0:
        raise ValueError("--days doit être strictement positif")

    today = datetime.now(UTC).date()
    start = today - timedelta(days=args.days)
    return start.isoformat(), today.isoformat()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env_file = Path(args.env_file)

    date_from, date_to = resolve_period(args)
    mlc_id = args.mlc

    include_odoo = bool(args.include_odoo or (mlc_id == "gonette" and not args.skip_odoo))
    include_system_balances = bool(
        args.include_system_balances
        or (mlc_id == "graine" and not args.skip_system_balances)
    )

    plan = {
        "mlc_id": mlc_id,
        "date_from": date_from,
        "date_to": date_to,
        "dry_run": bool(args.dry_run),
        "plan_only": bool(args.plan_only),
        "include_odoo": include_odoo,
        "include_system_balances": include_system_balances,
        "skip_heavy_balances": bool(args.skip_heavy_balances),
        "skip_balance_reconstruction": bool(args.skip_balance_reconstruction),
        "skip_professional_chain_fate": bool(args.skip_professional_chain_fate),
        "skip_actor_links": bool(args.skip_actor_links),
        "skip_cyclos_professional_profiles": bool(args.skip_cyclos_professional_profiles),
        "skip_caches": bool(args.skip_caches),
        "skip_integrity": bool(args.skip_integrity),
        "limit_users": args.limit_users,
        "limit_professionals": args.limit_professionals,
        "professional_profile_days": args.professional_profile_days,
        "professional_profile_limit": args.professional_profile_limit,
        "max_windows_per_user": args.max_windows_per_user,
        "max_windows_per_professional": args.max_windows_per_professional,
        "request_pause_seconds": args.request_pause_seconds,
    }

    report: dict[str, Any] = {
        "kind": "mlcflux_sync_mlc_instance_report",
        "generated_at": utc_now(),
        "plan": plan,
        "steps": [],
    }

    def add_step(name: str, fn, *, skip_when: bool = False, skip_reason: str = "") -> None:
        if skip_when:
            report["steps"].append(step_result(name, "skipped", reason=skip_reason))
            return

        if args.plan_only:
            report["steps"].append(step_result(name, "planned"))
            return

        started = time.monotonic()
        payload = None

        try:
            payload = fn()
            if isinstance(payload, dict) and (
                payload.get("ok") is False
                or ("returncode" in payload and payload["returncode"] != 0)
            ):
                raise RuntimeError(
                    f"Échec de {payload.get('module', name)} "
                    f"(returncode={payload.get('returncode')}, ok={payload.get('ok')})"
                )
            report["steps"].append(
                step_result(
                    name,
                    "ok",
                    duration_seconds=round(time.monotonic() - started, 3),
                    payload=payload,
                )
            )
        except Exception as exc:
            report["ok"] = False
            report["steps"].append(
                step_result(
                    name,
                    "error",
                    duration_seconds=round(time.monotonic() - started, 3),
                    error=f"{type(exc).__name__}: {exc}",
                    payload=payload,
                )
            )
            if not args.continue_on_error:
                raise

    configure_instance(mlc_id, env_file)

    add_step(
        "transactions",
        lambda: sync_transactions_service(
            mlc_id=mlc_id,
            date_from=date_from,
            date_to=date_to,
            dry_run=args.dry_run,
            env_file=env_file,
        ),
    )

    add_step(
        "transaction_semantics",
        lambda: rebuild_semantics(
            mlc_id=mlc_id,
            date_from=date_from,
            date_to=date_to,
            env_file=env_file,
        ),
        skip_when=args.dry_run,
        skip_reason="dry_run: transaction_semantics écrit en base",
    )

    add_step(
        "professional_chain_fate_summary",
        lambda: run_subprocess_module(
            "server.sync_professional_chain_fate_summary",
            ["--mlc", mlc_id],
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_professional_chain_fate,
        skip_reason="dry_run ou --skip-professional-chain-fate",
    )

    add_step(
        "actor_user_links",
        lambda: run_subprocess_module(
            "server.sync_cyclos_actor_user_links",
            ["--date-from", date_from, "--date-to", date_to],
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_actor_links,
        skip_reason="dry_run ou --skip-actor-links",
    )

    add_step(
        "professional_actor_user_links",
        lambda: run_subprocess_module(
            "server.sync_cyclos_professional_actor_user_links",
            ["--date-from", date_from, "--date-to", date_to],
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_actor_links,
        skip_reason="dry_run ou --skip-actor-links",
    )

    professional_profile_args = [
        "--mlc",
        mlc_id,
        "--days",
        str(args.professional_profile_days),
        "--limit",
        str(args.professional_profile_limit),
        "--apply",
    ]

    add_step(
        "cyclos_professional_profile_enrichment",
        lambda: run_subprocess_module(
            "server.sync_cyclos_professional_profile_enrichment",
            professional_profile_args,
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_cyclos_professional_profiles,
        skip_reason="dry_run ou --skip-cyclos-professional-profiles",
    )

    individual_balance_args = ["--date-from", date_from, "--date-to", date_to]
    if args.limit_users is not None:
        individual_balance_args += ["--limit-users", str(args.limit_users)]
    if args.max_windows_per_user is not None:
        individual_balance_args += ["--max-windows-per-user", str(args.max_windows_per_user)]
    if args.request_pause_seconds is not None:
        individual_balance_args += ["--request-pause-seconds", str(args.request_pause_seconds)]

    professional_balance_args = ["--date-from", date_from, "--date-to", date_to]
    if args.limit_professionals is not None:
        professional_balance_args += ["--limit-professionals", str(args.limit_professionals)]
    if args.max_windows_per_professional is not None:
        professional_balance_args += ["--max-windows-per-professional", str(args.max_windows_per_professional)]
    if args.request_pause_seconds is not None:
        professional_balance_args += ["--request-pause-seconds", str(args.request_pause_seconds)]

    add_step(
        "individual_daily_balances",
        lambda: run_subprocess_module(
            "server.sync_cyclos_individual_daily_balances",
            individual_balance_args,
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_heavy_balances,
        skip_reason="dry_run ou --skip-heavy-balances",
    )

    add_step(
        "professional_daily_balances",
        lambda: run_subprocess_module(
            "server.sync_cyclos_professional_daily_balances",
            professional_balance_args,
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_heavy_balances,
        skip_reason="dry_run ou --skip-heavy-balances",
    )

    add_step(
        "individual_balance_reconstruction",
        lambda: run_subprocess_module(
            "server.reconstruct_individual_balance_gaps",
            ["--mlc", mlc_id, "--date-from", date_from, "--date-to", date_to],
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_balance_reconstruction,
        skip_reason="dry_run ou --skip-balance-reconstruction",
    )

    add_step(
        "system_daily_balances",
        lambda: run_subprocess_module(
            "server.sync_cyclos_system_daily_balances",
            ["--mlc", mlc_id, "--date-from", date_from, "--date-to", date_to],
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_heavy_balances or not include_system_balances,
        skip_reason="dry_run, --skip-heavy-balances, ou instance sans soldes système quotidiens",
    )

    add_step(
        "odoo_professional_enrichment",
        lambda: run_subprocess_module(
            "server.sync_odoo_professional_enrichment",
            [],
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or not include_odoo,
        skip_reason="dry_run ou Odoo désactivé pour cette instance",
    )

    add_step(
        "odoo_individual_enrichment",
        lambda: run_subprocess_module(
            "server.sync_odoo_individual_enrichment",
            [],
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or not include_odoo,
        skip_reason="dry_run ou Odoo désactivé pour cette instance",
    )

    add_step(
        "odoo_monetary_indicators",
        lambda: run_subprocess_module(
            "server.sync_odoo_monetary_indicators",
            ["--current-year"],
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or not include_odoo,
        skip_reason="dry_run ou Odoo désactivé pour cette instance",
    )

    add_step(
        "odoo_monetary_indicators_daily",
        lambda: run_subprocess_module(
            "server.sync_odoo_monetary_indicators_daily",
            ["--date-from", date_from, "--date-to", date_to],
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or not include_odoo,
        skip_reason="dry_run ou Odoo désactivé pour cette instance",
    )

    add_step(
        "pilotage_holdings_daily_cache",
        lambda: refresh_cache_module(
            "server.refresh_pilotage_holdings_daily_cache",
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_caches,
        skip_reason="dry_run ou --skip-caches",
    )

    add_step(
        "pilotage_yearly_cache",
        lambda: refresh_cache_module(
            "server.refresh_pilotage_yearly_cache",
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_caches,
        skip_reason="dry_run ou --skip-caches",
    )

    integrity_dir = APP_DIR / "_audit_exports" / "sync_integrity"
    add_step(
        "integrity_quick",
        lambda: run_subprocess_module(
            "server.check_db_integrity",
            [
                "--level", "quick",
                "--output-dir", str(integrity_dir),
                "--prefix", f"sync_{mlc_id}",
            ],
            mlc_id=mlc_id,
            env_file=env_file,
        ),
        skip_when=args.dry_run or args.skip_integrity,
        skip_reason="dry_run ou --skip-integrity",
    )

    report["ok"] = all(step["status"] in {"ok", "skipped", "planned"} for step in report["steps"])

    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)

    if args.json_out:
        Path(args.json_out).write_text(output + "\n", encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
