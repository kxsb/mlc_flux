from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any

from server.database import get_connection, init_db


DEFAULT_CLASSIFIER_VERSION = "transaction_semantics_v0.3_profile_rules_fallback"


@dataclass(frozen=True)
class TransactionSemantics:
    transaction_key: str
    cyclos_id: str | None
    transaction_number: str | None
    date: str
    from_label: str | None
    to_label: str | None
    amount: float | None
    type_label: str | None
    group_label: str | None

    from_actor_family: str
    to_actor_family: str
    from_account_medium: str
    to_account_medium: str
    operation_kind: str
    monetary_circuit: str

    is_economic_activity: int
    is_monetary_supply: int
    is_monetary_exit: int
    is_paper_operation: int
    is_bonus_operation: int
    is_regularization: int

    confidence: str
    reason: str
    classifier_version: str
    computed_at: str


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _clean(value).lower()




PROFILE_DIR = Path(__file__).resolve().parents[1] / "data" / "mlc_profiles"


def _active_mlc_id() -> str:
    return (
        os.environ.get("MLCFLUX_DEFAULT_MLC_ID")
        or os.environ.get("MLCFLUX_ACTIVE_MLC_ID")
        or "gonette"
    )


def _fold(value: Any) -> str:
    text = _lower(value)
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


@lru_cache(maxsize=32)
def _load_transaction_semantics_profile(mlc_id: str) -> dict[str, Any]:
    profile_path = PROFILE_DIR / f"{mlc_id}.json"

    if not profile_path.exists():
        return {}

    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    rules = profile.get("transaction_semantics")
    return rules if isinstance(rules, dict) else {}


def _classifier_version(mlc_id: str) -> str:
    rules = _load_transaction_semantics_profile(mlc_id)
    return str(rules.get("classifier_version") or DEFAULT_CLASSIFIER_VERSION)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value]

    return [str(value)]


def _match_text_rule(rule: dict[str, Any], field: str, value: Any) -> bool:
    raw = _clean(value)
    folded = _fold(value)

    exact_values = _as_list(rule.get(f"{field}_in"))
    if exact_values and folded not in {_fold(item) for item in exact_values}:
        return False

    startswith_values = _as_list(rule.get(f"{field}_startswith"))
    if startswith_values and not any(raw.startswith(item) for item in startswith_values):
        return False

    contains_any = _as_list(rule.get(f"{field}_contains_any"))
    if contains_any and not any(_fold(item) in folded for item in contains_any):
        return False

    contains_all = _as_list(rule.get(f"{field}_contains_all"))
    if contains_all and not all(_fold(item) in folded for item in contains_all):
        return False

    regex = rule.get(f"{field}_regex")
    if regex and not re.search(str(regex), raw):
        return False

    return True


def _match_operation_rule(
    rule: dict[str, Any],
    *,
    from_label: str,
    to_label: str,
    from_family: str,
    to_family: str,
    from_medium: str,
    to_medium: str,
    type_label: str,
    group_label: str,
) -> bool:
    text_fields = {
        "from_label": from_label,
        "to_label": to_label,
        "type_label": type_label,
        "group_label": group_label,
    }

    for field, value in text_fields.items():
        if any(key.startswith(field + "_") for key in rule):
            if not _match_text_rule(rule, field, value):
                return False

    exact_fields = {
        "from_actor_family": from_family,
        "to_actor_family": to_family,
        "from_account_medium": from_medium,
        "to_account_medium": to_medium,
    }

    for field, value in exact_fields.items():
        if field in rule and str(rule[field]) != value:
            return False

        in_key = f"{field}_in"
        if in_key in rule and value not in _as_list(rule[in_key]):
            return False

    return True


def _profile_actor_family(label: str, mlc_id: str) -> str | None:
    rules = _load_transaction_semantics_profile(mlc_id)

    for rule in rules.get("actor_family_rules") or []:
        if not isinstance(rule, dict):
            continue
        if _match_text_rule(rule, "label", label):
            family = rule.get("actor_family")
            if family:
                return str(family)

    return None


def _profile_account_medium(label: str, mlc_id: str) -> str | None:
    rules = _load_transaction_semantics_profile(mlc_id)

    for rule in rules.get("account_medium_rules") or []:
        if not isinstance(rule, dict):
            continue
        if _match_text_rule(rule, "label", label):
            medium = rule.get("account_medium")
            if medium:
                return str(medium)

    return None


def _profile_operation(
    *,
    mlc_id: str,
    from_label: str,
    to_label: str,
    from_family: str,
    to_family: str,
    from_medium: str,
    to_medium: str,
    type_label: str,
    group_label: str,
) -> tuple[str, str, str, str] | None:
    rules = _load_transaction_semantics_profile(mlc_id)

    for rule in rules.get("operation_rules") or []:
        if not isinstance(rule, dict):
            continue

        if not _match_operation_rule(
            rule,
            from_label=from_label,
            to_label=to_label,
            from_family=from_family,
            to_family=to_family,
            from_medium=from_medium,
            to_medium=to_medium,
            type_label=type_label,
            group_label=group_label,
        ):
            continue

        operation_kind = rule.get("operation_kind")
        monetary_circuit = rule.get("monetary_circuit")
        if not operation_kind or not monetary_circuit:
            continue

        confidence = str(rule.get("confidence") or "medium")
        reason = str(rule.get("reason") or f"profile rule: {rule.get('name') or operation_kind}")

        return (
            str(operation_kind),
            str(monetary_circuit),
            confidence,
            reason,
        )

    return None

def _transaction_key(row: sqlite3.Row | dict[str, Any]) -> str:
    cyclos_id = _clean(row["cyclos_id"])
    if cyclos_id:
        return f"cyclos:{cyclos_id}"

    tx_number = _clean(row["transaction_number"])
    if tx_number:
        return f"number:{tx_number}"

    raw = "|".join(
        _clean(row[key])
        for key in [
            "date",
            "from_label",
            "to_label",
            "amount",
            "type_label",
            "group_label",
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"synthetic:{digest}"


def _actor_family_from_label(label: str, mlc_id: str | None = None) -> str:
    mlc_id = mlc_id or _active_mlc_id()

    profile_family = _profile_actor_family(label, mlc_id)
    if profile_family:
        return profile_family

    text = _clean(label)

    if not text:
        return "unknown"

    if text.startswith("UD_"):
        return "individual_device"

    if text.startswith("U_"):
        return "individual"

    if text in {"P0000", "P9999"}:
        return "operator"

    if re.fullmatch(r"P\d{4,}", text):
        return "professional"

    if text.startswith("T_"):
        if "stock" in text.lower() or "bch" in text.lower():
            return "exchange_office_or_stock"
        return "system"

    return "unknown"


def _account_medium_from_label(label: str, actor_family: str, mlc_id: str | None = None) -> str:
    mlc_id = mlc_id or _active_mlc_id()

    profile_medium = _profile_account_medium(label, mlc_id)
    if profile_medium:
        return profile_medium

    text = _lower(label)

    if not text:
        return "unknown"

    if "bonus" in text or "compteurbonus" in text:
        return "bonus"

    if "nantissement" in text or "garantie" in text:
        return "guarantee"

    if "stockbillets" in text or "stockcoffrecentral" in text or "coffrecentral" in text:
        return "paper_stock"

    if "billets" in text or "billet" in text or "compteprobillets" in text:
        return "paper"

    if actor_family in {"individual", "individual_device", "professional", "operator"}:
        return "digital"

    if "émission" in text or "emission" in text or "conversion" in text or "numerique" in text:
        return "digital"

    return "technical"


def _operation_from_type_and_labels(
    *,
    mlc_id: str | None = None,
    from_label: str,
    to_label: str,
    from_family: str,
    to_family: str,
    from_medium: str,
    to_medium: str,
    type_label: str,
    group_label: str,
) -> tuple[str, str, str, str]:
    """
    Retourne operation_kind, monetary_circuit, confidence, reason.

    Version 0.1 volontairement prudente :
    - elle ne remplace pas encore les analyses existantes ;
    - elle rend visible une sémantique transactionnelle parallèle ;
    - elle privilégie les type_label explicites quand Cyclos les donne.
    """
    mlc_id = mlc_id or _active_mlc_id()

    profile_result = _profile_operation(
        mlc_id=mlc_id,
        from_label=from_label,
        to_label=to_label,
        from_family=from_family,
        to_family=to_family,
        from_medium=from_medium,
        to_medium=to_medium,
        type_label=type_label,
        group_label=group_label,
    )
    if profile_result:
        return profile_result

    t = _lower(type_label)
    f = _lower(from_label)
    to = _lower(to_label)

    # Papier / bureaux de change — observé Graine.
    if "bch2c" in t and "change" in t:
        return (
            "paper_exchange_to_individual",
            "monetary_supply",
            "high",
            "type_label Bch2C Change",
        )

    if "bch2b" in t and "change" in t:
        return (
            "paper_exchange_to_professional",
            "monetary_supply",
            "high",
            "type_label Bch2B Change",
        )

    if "livraison coffre central vers bch" in t or "s2bch" in t:
        return (
            "paper_stock_delivery",
            "paper_logistics",
            "high",
            "type_label livraison coffre central vers BCH",
        )

    if "ré intégration billets" in t or "re intégration billets" in t or "bch2s" in t:
        return (
            "paper_stock_return",
            "paper_logistics",
            "high",
            "type_label réintégration billets vers coffre central",
        )

    if "réception livraison billet vers stock" in t or "reception livraison billet vers stock" in t:
        return (
            "paper_stock_initial_receipt",
            "paper_logistics",
            "high",
            "type_label réception livraison billet vers stock",
        )

    if "entrée en stock" in t or "entree en stock" in t:
        return (
            "paper_stock_return",
            "paper_logistics",
            "high",
            "type_label entrée en stock",
        )

    if "bch2bdepotbilletscreditcpte" in t or "depot billets credit cpte" in t or "dépôtbilletscreditcpte" in t:
        return (
            "paper_deposit_to_professional_account",
            "paper_to_digital",
            "high",
            "type_label dépôt billets crédit compte professionnel",
        )

    if "recouvrement des encaissements billets" in t:
        return (
            "paper_cash_collection_recovery",
            "paper_accounting",
            "high",
            "type_label recouvrement des encaissements billets",
        )

    if "bonus 2%" in t:
        return (
            "bonus_issuance",
            "bonus",
            "high",
            "type_label Bonus 2%",
        )

    if "t2scopiecreditparticulier" in t or "t2scopiecreditprestataire" in t:
        return (
            "historical_digital_credit_replay",
            "technical_migration",
            "medium",
            "type_label T2Scopie crédit historique",
        )

    if "t2scopieconversionpro" in t:
        return (
            "historical_professional_reconversion_replay",
            "technical_migration",
            "medium",
            "type_label T2Scopie conversion pro historique",
        )

    if "s2semissiondédiénumériquesuitedépôt" in t or "s2semissiondedienumeriquesuitedepot" in t:
        return (
            "paper_deposit_to_digital_dedicated_account",
            "paper_to_digital",
            "high",
            "type_label émission dédiée numérique suite dépôt",
        )

    if "raz" in t or "régularisation" in t or "regularisation" in t or "annulation" in t:
        return (
            "regularization",
            "technical_adjustment",
            "high",
            "type_label RAZ/régularisation/annulation",
        )

    # Gonette / logique générique d'émission-reconversion.
    if ("émission" in f or "emission" in f) and to_family in {
        "individual",
        "individual_device",
        "professional",
    }:
        return (
            "euro_to_digital",
            "monetary_supply",
            "medium",
            "source label emission -> actor",
        )

    if from_family in {"individual", "individual_device", "professional"} and (
        "conversion" in to or "reconversion" in to
    ):
        return (
            "digital_to_euro",
            "monetary_exit",
            "medium",
            "actor -> conversion/reconversion label",
        )

    # Activité économique centrale.
    if from_family in {"individual", "individual_device", "professional"} and to_family == "professional":
        return (
            "economic_payment",
            "economic",
            "medium",
            "individual/professional -> professional",
        )

    if from_family == "professional" and to_family in {"professional", "individual", "individual_device"}:
        return (
            "economic_payment",
            "economic",
            "medium",
            "professional -> professional/individual",
        )

    if from_family in {"individual", "individual_device"} and to_family in {"individual", "individual_device"}:
        return (
            "individual_transfer",
            "peer_to_peer",
            "low",
            "individual -> individual",
        )

    if "paper" in {from_medium, to_medium} or "paper_stock" in {from_medium, to_medium}:
        return (
            "paper_operation_unclassified",
            "paper_logistics",
            "low",
            "paper medium detected without explicit known type_label",
        )

    if from_family == "system" or to_family == "system":
        return (
            "technical_transfer",
            "technical",
            "low",
            "system actor family detected",
        )

    return (
        "unknown",
        "unknown",
        "low",
        "no matching semantic rule",
    )


def infer_transaction_semantics(row: sqlite3.Row | dict[str, Any], *, mlc_id: str | None = None) -> TransactionSemantics:
    mlc_id = mlc_id or _active_mlc_id()

    from_label = _clean(row["from_label"])
    to_label = _clean(row["to_label"])
    type_label = _clean(row["type_label"])
    group_label = _clean(row["group_label"])

    from_family = _actor_family_from_label(from_label, mlc_id=mlc_id)
    to_family = _actor_family_from_label(to_label, mlc_id=mlc_id)

    from_medium = _account_medium_from_label(from_label, from_family, mlc_id=mlc_id)
    to_medium = _account_medium_from_label(to_label, to_family, mlc_id=mlc_id)

    operation_kind, circuit, confidence, reason = _operation_from_type_and_labels(
        mlc_id=mlc_id,
        from_label=from_label,
        to_label=to_label,
        from_family=from_family,
        to_family=to_family,
        from_medium=from_medium,
        to_medium=to_medium,
        type_label=type_label,
        group_label=group_label,
    )

    is_economic = int(operation_kind == "economic_payment")
    is_supply = int(circuit == "monetary_supply")
    is_exit = int(circuit == "monetary_exit")
    is_paper = int(
        operation_kind.startswith("paper_")
        or from_medium in {"paper", "paper_stock"}
        or to_medium in {"paper", "paper_stock"}
    )
    is_bonus = int(circuit == "bonus" or from_medium == "bonus" or to_medium == "bonus")
    is_regularization = int(operation_kind == "regularization")

    return TransactionSemantics(
        transaction_key=_transaction_key(row),
        cyclos_id=_clean(row["cyclos_id"]) or None,
        transaction_number=_clean(row["transaction_number"]) or None,
        date=_clean(row["date"]),
        from_label=from_label or None,
        to_label=to_label or None,
        amount=float(row["amount"]) if row["amount"] is not None else None,
        type_label=type_label or None,
        group_label=group_label or None,

        from_actor_family=from_family,
        to_actor_family=to_family,
        from_account_medium=from_medium,
        to_account_medium=to_medium,

        operation_kind=operation_kind,
        monetary_circuit=circuit,

        is_economic_activity=is_economic,
        is_monetary_supply=is_supply,
        is_monetary_exit=is_exit,
        is_paper_operation=is_paper,
        is_bonus_operation=is_bonus,
        is_regularization=is_regularization,

        confidence=confidence,
        reason=reason,
        classifier_version=_classifier_version(mlc_id),
        computed_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )


def _select_transactions(
    conn: sqlite3.Connection,
    *,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    where = []
    params: list[Any] = []

    if start:
        where.append("substr(date, 1, 10) >= ?")
        params.append(start)

    if end:
        where.append("substr(date, 1, 10) <= ?")
        params.append(end)

    sql = """
        SELECT
          transaction_number,
          cyclos_id,
          date,
          group_label,
          from_label,
          to_label,
          amount,
          type_label
        FROM transactions
    """

    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += " ORDER BY date ASC, COALESCE(cyclos_id, transaction_number, '') ASC"

    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))

    return conn.execute(sql, params).fetchall()


def rebuild_transaction_semantics(
    *,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
    reset: bool = True,
) -> dict[str, Any]:
    init_db()

    conn = get_connection()
    try:
        rows = _select_transactions(conn, start=start, end=end, limit=limit)
        mlc_id = _active_mlc_id()
        semantics = [infer_transaction_semantics(row, mlc_id=mlc_id) for row in rows]

        cur = conn.cursor()

        if reset:
            if start or end:
                conditions = []
                params: list[Any] = []
                if start:
                    conditions.append("substr(date, 1, 10) >= ?")
                    params.append(start)
                if end:
                    conditions.append("substr(date, 1, 10) <= ?")
                    params.append(end)
                cur.execute(
                    "DELETE FROM transaction_semantics WHERE " + " AND ".join(conditions),
                    params,
                )
            else:
                cur.execute("DELETE FROM transaction_semantics")

        for item in semantics:
            cur.execute(
                """
                INSERT INTO transaction_semantics (
                    transaction_key,
                    cyclos_id,
                    transaction_number,
                    date,
                    from_label,
                    to_label,
                    amount,
                    type_label,
                    group_label,
                    from_actor_family,
                    to_actor_family,
                    from_account_medium,
                    to_account_medium,
                    operation_kind,
                    monetary_circuit,
                    is_economic_activity,
                    is_monetary_supply,
                    is_monetary_exit,
                    is_paper_operation,
                    is_bonus_operation,
                    is_regularization,
                    confidence,
                    reason,
                    classifier_version,
                    computed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                ON CONFLICT(transaction_key) DO UPDATE SET
                    cyclos_id=excluded.cyclos_id,
                    transaction_number=excluded.transaction_number,
                    date=excluded.date,
                    from_label=excluded.from_label,
                    to_label=excluded.to_label,
                    amount=excluded.amount,
                    type_label=excluded.type_label,
                    group_label=excluded.group_label,
                    from_actor_family=excluded.from_actor_family,
                    to_actor_family=excluded.to_actor_family,
                    from_account_medium=excluded.from_account_medium,
                    to_account_medium=excluded.to_account_medium,
                    operation_kind=excluded.operation_kind,
                    monetary_circuit=excluded.monetary_circuit,
                    is_economic_activity=excluded.is_economic_activity,
                    is_monetary_supply=excluded.is_monetary_supply,
                    is_monetary_exit=excluded.is_monetary_exit,
                    is_paper_operation=excluded.is_paper_operation,
                    is_bonus_operation=excluded.is_bonus_operation,
                    is_regularization=excluded.is_regularization,
                    confidence=excluded.confidence,
                    reason=excluded.reason,
                    classifier_version=excluded.classifier_version,
                    computed_at=excluded.computed_at
                """,
                (
                    item.transaction_key,
                    item.cyclos_id,
                    item.transaction_number,
                    item.date,
                    item.from_label,
                    item.to_label,
                    item.amount,
                    item.type_label,
                    item.group_label,
                    item.from_actor_family,
                    item.to_actor_family,
                    item.from_account_medium,
                    item.to_account_medium,
                    item.operation_kind,
                    item.monetary_circuit,
                    item.is_economic_activity,
                    item.is_monetary_supply,
                    item.is_monetary_exit,
                    item.is_paper_operation,
                    item.is_bonus_operation,
                    item.is_regularization,
                    item.confidence,
                    item.reason,
                    item.classifier_version,
                    item.computed_at,
                ),
            )

        conn.commit()

        summary = conn.execute(
            """
            SELECT
              COUNT(*) AS rows,
              COUNT(DISTINCT operation_kind) AS operation_kinds,
              COUNT(DISTINCT monetary_circuit) AS monetary_circuits,
              SUM(is_economic_activity) AS economic_rows,
              SUM(is_paper_operation) AS paper_rows,
              SUM(is_bonus_operation) AS bonus_rows,
              SUM(is_regularization) AS regularization_rows
            FROM transaction_semantics
            """
        ).fetchone()

        by_operation = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  operation_kind,
                  monetary_circuit,
                  COUNT(*) AS count,
                  ROUND(SUM(amount), 2) AS volume
                FROM transaction_semantics
                GROUP BY operation_kind, monetary_circuit
                ORDER BY count DESC, operation_kind
                """
            ).fetchall()
        ]

        by_family = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  from_actor_family || '→' || to_actor_family AS flow,
                  COUNT(*) AS count,
                  ROUND(SUM(amount), 2) AS volume
                FROM transaction_semantics
                GROUP BY flow
                ORDER BY count DESC, flow
                """
            ).fetchall()
        ]

        return {
            "selected_transactions": len(rows),
            "written_semantics": len(semantics),
            "summary": dict(summary) if summary else {},
            "by_operation": by_operation,
            "by_family": by_family,
        }
    finally:
        conn.close()


def summarize_transaction_semantics() -> dict[str, Any]:
    conn = get_connection()
    try:
        total = conn.execute(
            "SELECT COUNT(*) AS count FROM transaction_semantics"
        ).fetchone()["count"]

        operations = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  operation_kind,
                  monetary_circuit,
                  COUNT(*) AS count,
                  ROUND(SUM(amount), 2) AS volume
                FROM transaction_semantics
                GROUP BY operation_kind, monetary_circuit
                ORDER BY count DESC, operation_kind
                """
            ).fetchall()
        ]

        families = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  from_actor_family || '→' || to_actor_family AS flow,
                  COUNT(*) AS count,
                  ROUND(SUM(amount), 2) AS volume
                FROM transaction_semantics
                GROUP BY flow
                ORDER BY count DESC, flow
                """
            ).fetchall()
        ]

        return {
            "rows": total,
            "operations": operations,
            "families": families,
        }
    finally:
        conn.close()
