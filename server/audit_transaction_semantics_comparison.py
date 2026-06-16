from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from server.database import get_connection


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _legacy_family(label: str) -> str:
    text = _clean(label)

    if text.startswith("UD_"):
        return "U"

    if text.startswith("U_"):
        return "U"

    if text in {"P0000", "P9999"}:
        return "OPERATOR"

    if re.fullmatch(r"P\d{4,}", text):
        return "P"

    if text.startswith("T_"):
        return "T"

    return "?"


def _legacy_flow(row: dict[str, Any]) -> str:
    return f"{_legacy_family(row['from_label'])}→{_legacy_family(row['to_label'])}"


def _legacy_bucket(row: dict[str, Any]) -> str:
    from_family = _legacy_family(row["from_label"])
    to_family = _legacy_family(row["to_label"])

    from_label = _clean(row["from_label"]).lower()
    to_label = _clean(row["to_label"]).lower()
    type_label = _clean(row["type_label"]).lower()

    if from_family in {"U", "P"} and to_family == "P":
        return "legacy_economic_activity"

    if from_family == "P" and to_family in {"U", "P"}:
        return "legacy_economic_activity"

    if from_family == "U" and to_family == "U":
        return "legacy_individual_transfer"

    if ("émission" in from_label or "emission" in from_label) and to_family in {"U", "P"}:
        return "legacy_supply_conversion"

    if from_family in {"U", "P"} and ("conversion" in to_label or "reconversion" in to_label):
        return "legacy_exit_reconversion"

    if "billet" in from_label or "billet" in to_label or "bch" in type_label:
        return "legacy_paper_or_bch"

    if "bonus" in from_label or "bonus" in to_label or "bonus" in type_label:
        return "legacy_bonus"

    if from_family == "T" or to_family == "T":
        return "legacy_technical_or_operator"

    return "legacy_unknown"


def _money(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _add_metric(counter: dict[str, dict[str, Any]], key: str, amount: float) -> None:
    item = counter.setdefault(key, {"count": 0, "volume": 0.0})
    item["count"] += 1
    item["volume"] += amount


def _rounded_metrics(counter: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for key, item in counter.items():
        rows.append({
            "key": key,
            "count": item["count"],
            "volume": round(item["volume"], 2),
        })
    return sorted(rows, key=lambda r: (-r["count"], r["key"]))


def build_comparison(limit_examples: int = 20) -> dict[str, Any]:
    conn = get_connection()
    try:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  t.date,
                  t.from_label,
                  t.to_label,
                  t.amount,
                  t.type_label,
                  t.group_label,
                  t.from_actor_family,
                  t.to_actor_family,
                  t.from_account_medium,
                  t.to_account_medium,
                  t.operation_kind,
                  t.monetary_circuit,
                  t.confidence,
                  t.reason,
                  t.classifier_version
                FROM transaction_semantics t
                ORDER BY t.date ASC
                """
            ).fetchall()
        ]
    finally:
        conn.close()

    legacy_flows: dict[str, dict[str, Any]] = {}
    legacy_buckets: dict[str, dict[str, Any]] = {}
    semantic_operations: dict[str, dict[str, Any]] = {}
    semantic_circuits: dict[str, dict[str, Any]] = {}

    cross_legacy_bucket_operation: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    cross_legacy_flow_operation: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    examples_by_mismatch: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        amount = _money(row["amount"])
        legacy_flow = _legacy_flow(row)
        legacy_bucket = _legacy_bucket(row)
        operation_key = f"{row['operation_kind']} / {row['monetary_circuit']}"

        _add_metric(legacy_flows, legacy_flow, amount)
        _add_metric(legacy_buckets, legacy_bucket, amount)
        _add_metric(semantic_operations, operation_key, amount)
        _add_metric(semantic_circuits, row["monetary_circuit"], amount)

        _add_metric(cross_legacy_bucket_operation[legacy_bucket], operation_key, amount)
        _add_metric(cross_legacy_flow_operation[legacy_flow], operation_key, amount)

        mismatch_key = None

        if legacy_bucket == "legacy_economic_activity" and row["operation_kind"] != "economic_payment":
            mismatch_key = "legacy_economic_not_semantic_economic"

        elif row["operation_kind"] == "economic_payment" and legacy_bucket != "legacy_economic_activity":
            mismatch_key = "semantic_economic_not_legacy_economic"

        elif legacy_bucket == "legacy_technical_or_operator" and row["monetary_circuit"] in {
            "monetary_supply",
            "monetary_exit",
            "paper_logistics",
            "paper_to_digital",
            "paper_accounting",
            "bonus",
            "technical_migration",
        }:
            mismatch_key = "legacy_technical_semantically_qualified"

        elif legacy_bucket == "legacy_paper_or_bch" and not (
            str(row["operation_kind"]).startswith("paper_")
            or row["monetary_circuit"] in {"paper_logistics", "paper_to_digital", "paper_accounting"}
        ):
            mismatch_key = "legacy_paper_not_semantic_paper"

        if mismatch_key and len(examples_by_mismatch[mismatch_key]) < limit_examples:
            examples_by_mismatch[mismatch_key].append({
                "date": row["date"],
                "from_label": row["from_label"],
                "to_label": row["to_label"],
                "amount": row["amount"],
                "type_label": row["type_label"],
                "legacy_flow": legacy_flow,
                "legacy_bucket": legacy_bucket,
                "operation_kind": row["operation_kind"],
                "monetary_circuit": row["monetary_circuit"],
                "reason": row["reason"],
            })

    cross_bucket_rows = []
    for legacy_bucket, operations in cross_legacy_bucket_operation.items():
        for operation, metrics in operations.items():
            cross_bucket_rows.append({
                "legacy_bucket": legacy_bucket,
                "semantic_operation": operation,
                "count": metrics["count"],
                "volume": round(metrics["volume"], 2),
            })

    cross_flow_rows = []
    for legacy_flow, operations in cross_legacy_flow_operation.items():
        for operation, metrics in operations.items():
            cross_flow_rows.append({
                "legacy_flow": legacy_flow,
                "semantic_operation": operation,
                "count": metrics["count"],
                "volume": round(metrics["volume"], 2),
            })

    cross_bucket_rows.sort(key=lambda r: (r["legacy_bucket"], -r["count"], r["semantic_operation"]))
    cross_flow_rows.sort(key=lambda r: (r["legacy_flow"], -r["count"], r["semantic_operation"]))

    return {
        "rows": len(rows),
        "classifier_versions": sorted({row["classifier_version"] for row in rows}),
        "legacy_flows": _rounded_metrics(legacy_flows),
        "legacy_buckets": _rounded_metrics(legacy_buckets),
        "semantic_operations": _rounded_metrics(semantic_operations),
        "semantic_circuits": _rounded_metrics(semantic_circuits),
        "cross_legacy_bucket_operation": cross_bucket_rows,
        "cross_legacy_flow_operation": cross_flow_rows,
        "examples_by_mismatch": dict(examples_by_mismatch),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare le modèle legacy par labels avec transaction_semantics."
    )
    parser.add_argument("--json", action="store_true", help="Sortie JSON complète.")
    parser.add_argument("--csv-dir", default=None, help="Répertoire où écrire des CSV de comparaison.")
    parser.add_argument("--examples", type=int, default=20, help="Nombre d'exemples par type d'écart.")
    args = parser.parse_args()

    report = build_comparison(limit_examples=args.examples)

    if args.csv_dir:
        csv_dir = Path(args.csv_dir)
        write_csv(csv_dir / "legacy_flows.csv", report["legacy_flows"])
        write_csv(csv_dir / "legacy_buckets.csv", report["legacy_buckets"])
        write_csv(csv_dir / "semantic_operations.csv", report["semantic_operations"])
        write_csv(csv_dir / "semantic_circuits.csv", report["semantic_circuits"])
        write_csv(csv_dir / "cross_legacy_bucket_operation.csv", report["cross_legacy_bucket_operation"])
        write_csv(csv_dir / "cross_legacy_flow_operation.csv", report["cross_legacy_flow_operation"])

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0

    print("rows =", report["rows"])
    print("classifier_versions =", report["classifier_versions"])

    print()
    print("------------------------------------------------------------------------")
    print("Legacy buckets")
    print("------------------------------------------------------------------------")
    for item in report["legacy_buckets"]:
        print(f"{item['key']:36s} | {item['count']:6d} | {item['volume']:12.2f}")

    print()
    print("------------------------------------------------------------------------")
    print("Semantic operations")
    print("------------------------------------------------------------------------")
    for item in report["semantic_operations"]:
        print(f"{item['key']:62s} | {item['count']:6d} | {item['volume']:12.2f}")

    print()
    print("------------------------------------------------------------------------")
    print("Cross legacy bucket → semantic operation")
    print("------------------------------------------------------------------------")
    for item in report["cross_legacy_bucket_operation"][:80]:
        print(
            f"{item['legacy_bucket']:36s} => {item['semantic_operation']:62s}"
            f" | {item['count']:6d} | {item['volume']:12.2f}"
        )

    print()
    print("------------------------------------------------------------------------")
    print("Examples by mismatch")
    print("------------------------------------------------------------------------")
    if not report["examples_by_mismatch"]:
        print("(aucun écart notable)")
    else:
        for key, examples in report["examples_by_mismatch"].items():
            print()
            print(f"[{key}]")
            for row in examples:
                print(
                    f"{row['date']} | {row['from_label']} → {row['to_label']}"
                    f" | {row['amount']} | {row['type_label']}"
                    f" | legacy={row['legacy_bucket']}"
                    f" | semantic={row['operation_kind']}/{row['monetary_circuit']}"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
