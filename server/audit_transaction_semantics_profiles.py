from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from server.services.transaction_semantics import infer_transaction_semantics


PROFILE_DIR = Path(__file__).resolve().parent / "data" / "mlc_profiles"


REQUIRED_TOP_KEYS = {
    "classifier_version": str,
    "actor_family_rules": list,
    "account_medium_rules": list,
    "operation_rules": list,
}

REQUIRED_OPERATION_KEYS = {
    "name",
    "operation_kind",
    "monetary_circuit",
    "confidence",
}


SYNTHETIC_CASES: dict[str, list[dict[str, Any]]] = {
    "graine": [
        {
            "name": "graine_economic_u_to_p",
            "row": {
                "transaction_number": "SYN-GRAINE-001",
                "cyclos_id": "SYN-GRAINE-001",
                "date": "2026-01-01T10:00:00+01:00",
                "group_label": "payment",
                "from_label": "U_Alice",
                "to_label": "P0010",
                "amount": 12,
                "type_label": "Paiement",
            },
            "expected": ["economic_payment", "economic"],
        },
        {
            "name": "graine_paper_exchange_to_individual",
            "row": {
                "transaction_number": "SYN-GRAINE-002",
                "cyclos_id": "SYN-GRAINE-002",
                "date": "2026-01-01T10:00:00+01:00",
                "group_label": "payment",
                "from_label": "T_StockBillets",
                "to_label": "T_Billets",
                "amount": 50,
                "type_label": "Bch2C Change contre paiement en Euro ou Mlcc",
            },
            "expected": ["paper_exchange_to_individual", "monetary_supply"],
        },
        {
            "name": "graine_paper_deposit_to_professional",
            "row": {
                "transaction_number": "SYN-GRAINE-003",
                "cyclos_id": "SYN-GRAINE-003",
                "date": "2026-01-01T10:00:00+01:00",
                "group_label": "payment",
                "from_label": "T_histoDepotPrestataire",
                "to_label": "P0010",
                "amount": 100,
                "type_label": "Bch2BdepotBilletsCreditCpte",
            },
            "expected": ["paper_deposit_to_professional_account", "paper_to_digital"],
        },
        {
            "name": "graine_bonus",
            "row": {
                "transaction_number": "SYN-GRAINE-004",
                "cyclos_id": "SYN-GRAINE-004",
                "date": "2026-01-01T10:00:00+01:00",
                "group_label": "payment",
                "from_label": "T_emissionBonusAsso",
                "to_label": "T_compteurBonus",
                "amount": 2,
                "type_label": "Bonus 2%",
            },
            "expected": ["bonus_issuance", "bonus"],
        },
    ],
    "gonette": [
        {
            "name": "gonette_euro_to_digital",
            "row": {
                "transaction_number": "SYN-GONETTE-001",
                "cyclos_id": "SYN-GONETTE-001",
                "date": "2026-01-01T10:00:00+01:00",
                "group_label": "payment",
                "from_label": "T_Émission",
                "to_label": "U_Alice",
                "amount": 50,
                "type_label": "Crédit automatique",
            },
            "expected": ["euro_to_digital", "monetary_supply"],
        },
        {
            "name": "gonette_economic_u_to_p",
            "row": {
                "transaction_number": "SYN-GONETTE-002",
                "cyclos_id": "SYN-GONETTE-002",
                "date": "2026-01-01T10:00:00+01:00",
                "group_label": "payment",
                "from_label": "U_Alice",
                "to_label": "P0010",
                "amount": 12,
                "type_label": "Paiement",
            },
            "expected": ["economic_payment", "economic"],
        },
        {
            "name": "gonette_economic_p_to_p",
            "row": {
                "transaction_number": "SYN-GONETTE-003",
                "cyclos_id": "SYN-GONETTE-003",
                "date": "2026-01-01T10:00:00+01:00",
                "group_label": "payment",
                "from_label": "P0010",
                "to_label": "P0020",
                "amount": 42,
                "type_label": "Paiement pro",
            },
            "expected": ["economic_payment", "economic"],
        },
        {
            "name": "gonette_digital_to_euro",
            "row": {
                "transaction_number": "SYN-GONETTE-004",
                "cyclos_id": "SYN-GONETTE-004",
                "date": "2026-01-01T10:00:00+01:00",
                "group_label": "payment",
                "from_label": "P0010",
                "to_label": "T_Conversion",
                "amount": 100,
                "type_label": "Reconversion",
            },
            "expected": ["digital_to_euro", "monetary_exit"],
        },
    ],
}


def load_profile(profile_id: str) -> dict[str, Any]:
    path = PROFILE_DIR / f"{profile_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Profil introuvable : {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def validate_profile(profile_id: str) -> list[str]:
    errors: list[str] = []
    profile = load_profile(profile_id)

    semantics = profile.get("transaction_semantics")
    if not isinstance(semantics, dict):
        return [f"{profile_id}: section transaction_semantics absente ou invalide"]

    for key, expected_type in REQUIRED_TOP_KEYS.items():
        value = semantics.get(key)
        if not isinstance(value, expected_type):
            errors.append(f"{profile_id}: transaction_semantics.{key} doit être {expected_type.__name__}")

    for list_key in ["actor_family_rules", "account_medium_rules", "operation_rules"]:
        names: set[str] = set()
        for idx, rule in enumerate(semantics.get(list_key) or []):
            if not isinstance(rule, dict):
                errors.append(f"{profile_id}: {list_key}[{idx}] doit être un objet")
                continue

            name = rule.get("name")
            if not name:
                errors.append(f"{profile_id}: {list_key}[{idx}] sans name")
            elif name in names:
                errors.append(f"{profile_id}: {list_key}[{idx}] name dupliqué: {name}")
            else:
                names.add(str(name))

    for idx, rule in enumerate(semantics.get("operation_rules") or []):
        missing = REQUIRED_OPERATION_KEYS - set(rule)
        if missing:
            errors.append(
                f"{profile_id}: operation_rules[{idx}] {rule.get('name') or '?'} manque {sorted(missing)}"
            )

    return errors


def run_synthetic_tests(profile_id: str) -> list[dict[str, Any]]:
    results = []

    for case in SYNTHETIC_CASES.get(profile_id, []):
        sem = infer_transaction_semantics(case["row"], mlc_id=profile_id)
        got = [sem.operation_kind, sem.monetary_circuit]
        expected = case["expected"]
        ok = got == expected

        results.append({
            "profile_id": profile_id,
            "case": case["name"],
            "ok": ok,
            "expected": expected,
            "got": got,
            "from_actor_family": sem.from_actor_family,
            "to_actor_family": sem.to_actor_family,
            "from_account_medium": sem.from_account_medium,
            "to_account_medium": sem.to_account_medium,
            "classifier_version": sem.classifier_version,
            "reason": sem.reason,
        })

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audite les profils MLC transaction_semantics et lance les tests synthétiques."
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["graine", "gonette"],
        help="Identifiants de profils MLC à tester.",
    )
    parser.add_argument("--json", action="store_true", help="Sortie JSON.")
    args = parser.parse_args()

    report: dict[str, Any] = {
        "profiles": {},
        "ok": True,
    }

    for profile_id in args.profiles:
        errors = validate_profile(profile_id)
        tests = run_synthetic_tests(profile_id)
        failed_tests = [item for item in tests if not item["ok"]]

        report["profiles"][profile_id] = {
            "validation_errors": errors,
            "synthetic_tests": tests,
            "ok": not errors and not failed_tests,
        }

        if errors or failed_tests:
            report["ok"] = False

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for profile_id, data in report["profiles"].items():
            print()
            print("------------------------------------------------------------------------")
            print(profile_id)
            print("------------------------------------------------------------------------")

            if data["validation_errors"]:
                print("VALIDATION ERRORS")
                for error in data["validation_errors"]:
                    print("-", error)
            else:
                print("validation_ok=True")

            for item in data["synthetic_tests"]:
                marker = "OK" if item["ok"] else "FAIL"
                print(
                    f"{marker} {item['case']} => {tuple(item['got'])} "
                    f"| expected={tuple(item['expected'])} "
                    f"| {item['from_actor_family']}→{item['to_actor_family']} "
                    f"| {item['from_account_medium']}→{item['to_account_medium']} "
                    f"| {item['classifier_version']} "
                    f"| {item['reason']}"
                )

        print()
        print("global_ok=", report["ok"])

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
