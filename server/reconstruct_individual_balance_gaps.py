from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = "reconstructed_after_cyclos_404_from_last_balance_and_transactions"


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def db_path_for_mlc(mlc_id: str) -> Path:
    return APP_DIR / "server" / "data" / "instances" / mlc_id / "mlcflux.db"


def rules_path_for_mlc(mlc_id: str) -> Path:
    return APP_DIR / "server" / "data" / "instances" / mlc_id / "individual_balance_reconstruction_rules.json"


def load_rules(mlc_id: str) -> list[dict[str, Any]]:
    path = rules_path_for_mlc(mlc_id)
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError(f"Champ rules invalide dans {path}")

    return rules


def daily_delta(con: sqlite3.Connection, pseudonym: str, day: str) -> float:
    rows = con.execute(
        """
        SELECT from_label, to_label, amount
        FROM transactions
        WHERE substr(date, 1, 10) = ?
          AND (from_label = ? OR to_label = ?)
        """,
        (day, pseudonym, pseudonym),
    ).fetchall()

    delta = 0.0
    for row in rows:
        amount = float(row["amount"] or 0)
        if row["from_label"] == pseudonym:
            delta -= amount
        if row["to_label"] == pseudonym:
            delta += amount

    return delta


def reconstruct_rule(
    con: sqlite3.Connection,
    *,
    rule: dict[str, Any],
    requested_date_from: date,
    requested_date_to: date,
    dry_run: bool,
    fetched_at: str,
) -> dict[str, Any]:
    pseudonym = str(rule["pseudonym"])
    source = str(rule.get("source") or DEFAULT_SOURCE)
    reason = str(rule.get("reason") or "")
    rule_start = parse_date(str(rule.get("start_date") or requested_date_from.isoformat()))

    date_from = max(requested_date_from, rule_start)
    date_to = requested_date_to

    report: dict[str, Any] = {
        "pseudonym": pseudonym,
        "reason": reason,
        "source": source,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "inserted": 0,
        "skipped_existing": 0,
        "days": [],
        "ok": True,
    }

    if date_from > date_to:
        report["status"] = "out_of_range"
        return report

    last = con.execute(
        """
        SELECT balance_date, balance
        FROM cyclos_individual_daily_balances
        WHERE pseudonym = ?
          AND balance_date < ?
        ORDER BY balance_date DESC
        LIMIT 1
        """,
        (pseudonym, date_from.isoformat()),
    ).fetchone()

    if not last:
        report["ok"] = False
        report["status"] = "missing_previous_balance"
        return report

    running = float(last["balance"])
    report["previous_balance_date"] = last["balance_date"]
    report["previous_balance"] = running

    rows_to_insert: list[tuple[str, str, float, str, str]] = []

    for current in daterange(date_from, date_to):
        day = current.isoformat()

        delta = daily_delta(con, pseudonym, day)
        running += delta
        if abs(running) < 0.000001:
            running = 0.0

        existing = con.execute(
            """
            SELECT COUNT(*)
            FROM cyclos_individual_daily_balances
            WHERE pseudonym = ?
              AND balance_date = ?
            """,
            (pseudonym, day),
        ).fetchone()[0]

        day_report = {
            "day": day,
            "delta": round(delta, 8),
            "balance": round(running, 8),
            "existing": int(existing),
            "action": "skip_existing" if existing else "insert",
        }
        report["days"].append(day_report)

        if existing:
            report["skipped_existing"] += 1
            continue

        report["inserted"] += 1
        rows_to_insert.append((pseudonym, day, round(running, 8), fetched_at, source))

    if rows_to_insert and not dry_run:
        con.executemany(
            """
            INSERT INTO cyclos_individual_daily_balances
                (pseudonym, balance_date, balance, fetched_at, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )

    report["status"] = "ok"
    return report


def run(mlc_id: str, date_from: str, date_to: str, dry_run: bool) -> dict[str, Any]:
    db_path = db_path_for_mlc(mlc_id)
    rules = load_rules(mlc_id)
    fetched_at = datetime.now(UTC).isoformat()

    report: dict[str, Any] = {
        "kind": "mlcflux_individual_balance_reconstruction_report",
        "mlc_id": mlc_id,
        "db_path": str(db_path),
        "rules_path": str(rules_path_for_mlc(mlc_id)),
        "date_from": date_from,
        "date_to": date_to,
        "dry_run": dry_run,
        "fetched_at": fetched_at,
        "rules_count": len(rules),
        "inserted": 0,
        "skipped_existing": 0,
        "ok": True,
        "rules": [],
    }

    if not rules:
        report["status"] = "no_rules"
        return report

    requested_date_from = parse_date(date_from)
    requested_date_to = parse_date(date_to)

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    try:
        with con:
            for rule in rules:
                rule_report = reconstruct_rule(
                    con,
                    rule=rule,
                    requested_date_from=requested_date_from,
                    requested_date_to=requested_date_to,
                    dry_run=dry_run,
                    fetched_at=fetched_at,
                )
                report["rules"].append(rule_report)
                report["inserted"] += int(rule_report.get("inserted") or 0)
                report["skipped_existing"] += int(rule_report.get("skipped_existing") or 0)
                if not rule_report.get("ok"):
                    report["ok"] = False
    finally:
        con.close()

    report["status"] = "ok" if report["ok"] else "partial_error"
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconstruit explicitement des trous de soldes individuels à partir du dernier solde connu et des transactions."
    )
    parser.add_argument("--mlc", required=True, choices=["graine", "gonette"])
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-out")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    report = run(
        mlc_id=args.mlc,
        date_from=args.date_from,
        date_to=args.date_to,
        dry_run=args.dry_run,
    )

    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)

    if args.json_out:
        Path(args.json_out).write_text(output + "\n", encoding="utf-8")

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
