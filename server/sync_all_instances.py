from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronise plusieurs instances MLCFlux multi-MLC."
    )

    parser.add_argument("--mlc", action="append", choices=["graine", "gonette"])
    parser.add_argument("--env-file", default=str(APP_DIR / ".env"))
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--days", type=int, default=3)

    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")

    parser.add_argument("--skip-heavy-balances", action="store_true")
    parser.add_argument("--skip-balance-reconstruction", action="store_true")
    parser.add_argument("--skip-professional-chain-fate", action="store_true")
    parser.add_argument("--skip-actor-links", action="store_true")
    parser.add_argument("--skip-caches", action="store_true")
    parser.add_argument("--skip-integrity", action="store_true")
    parser.add_argument("--skip-odoo", action="store_true")

    parser.add_argument("--include-odoo", action="store_true")
    parser.add_argument("--include-system-balances", action="store_true")
    parser.add_argument("--skip-system-balances", action="store_true")

    parser.add_argument("--limit-users", type=int)
    parser.add_argument("--limit-professionals", type=int)
    parser.add_argument("--max-windows-per-user", type=int)
    parser.add_argument("--max-windows-per-professional", type=int)
    parser.add_argument("--request-pause-seconds", type=float)

    parser.add_argument("--json-out")

    return parser


def child_command(args: argparse.Namespace, mlc_id: str, child_json: Path) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "server.sync_mlc_instance",
        "--mlc",
        mlc_id,
        "--env-file",
        args.env_file,
        "--json-out",
        str(child_json),
    ]

    if args.date_from:
        command += ["--date-from", args.date_from]
    if args.date_to:
        command += ["--date-to", args.date_to]
    if args.days:
        command += ["--days", str(args.days)]

    for flag in [
        "dry_run",
        "plan_only",
        "continue_on_error",
        "skip_heavy_balances",
        "skip_balance_reconstruction",
        "skip_professional_chain_fate",
        "skip_actor_links",
        "skip_caches",
        "skip_integrity",
        "skip_odoo",
        "include_odoo",
        "include_system_balances",
        "skip_system_balances",
    ]:
        if getattr(args, flag):
            command.append("--" + flag.replace("_", "-"))

    for option in [
        "limit_users",
        "limit_professionals",
        "max_windows_per_user",
        "max_windows_per_professional",
        "request_pause_seconds",
    ]:
        value = getattr(args, option)
        if value is not None:
            command += ["--" + option.replace("_", "-"), str(value)]

    return command


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    mlc_ids = args.mlc or ["graine", "gonette"]
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    run_dir = APP_DIR / "_sync_logs" / f"sync_all_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "kind": "mlcflux_sync_all_instances_report",
        "generated_at": utc_now(),
        "instances": mlc_ids,
        "run_dir": str(run_dir),
        "ok": True,
        "children": [],
    }

    for mlc_id in mlc_ids:
        child_json = run_dir / f"{mlc_id}.json"
        command = child_command(args, mlc_id, child_json)
        started = time.monotonic()

        completed = subprocess.run(
            command,
            cwd=APP_DIR,
            text=True,
            capture_output=True,
        )

        child = {
            "mlc_id": mlc_id,
            "command": command,
            "returncode": completed.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout": sanitize_log_text(completed.stdout.strip()),
            "stderr": sanitize_log_text(completed.stderr.strip()),
            "json_out": str(child_json),
            "ok": completed.returncode == 0,
        }

        report["children"].append(child)

        print()
        print("=" * 72)
        print(f"INSTANCE {mlc_id} — returncode={completed.returncode}")
        print("=" * 72)
        if completed.stdout.strip():
            print(sanitize_log_text(completed.stdout.strip()))
        if completed.stderr.strip():
            print("--- STDERR ---")
            print(sanitize_log_text(completed.stderr.strip()))

        if completed.returncode != 0:
            report["ok"] = False
            if not args.continue_on_error:
                break

    output = json.dumps(report, ensure_ascii=False, indent=2)
    print()
    print("=" * 72)
    print("SYNC ALL REPORT")
    print("=" * 72)
    print(output)

    if args.json_out:
        Path(args.json_out).write_text(output + "\n", encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
