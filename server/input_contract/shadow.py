from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from server.input_contract.reader import FinancialContractReader
from server.input_contract.runtime import create_input001_engine
from server.input_contract.writer import materialize_financial_dataset
from server.providers.cyclos_dataset import (
    build_cyclos_financial_dataset,
)
from server.providers.cyclos_normalized import (
    CyclosCurrencySpec,
)


class Input001ShadowConfigError(ValueError):
    """Configuration du miroir INPUT001 invalide."""


@dataclass(frozen=True)
class CyclosShadowConfig:
    enabled: bool
    dataset_id: str | None = None
    native_currency_id: str | None = None
    currency_code: str | None = None
    currency_exponent: int | None = None


_TRUE_VALUES = frozenset({
    "1",
    "true",
    "yes",
    "on",
})

_FALSE_VALUES = frozenset({
    "",
    "0",
    "false",
    "no",
    "off",
})


def _environment_flag(name: str) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()

    if raw in _FALSE_VALUES:
        return False

    if raw in _TRUE_VALUES:
        return True

    raise Input001ShadowConfigError(
        f"{name} doit être un booléen explicite."
    )


def _required_environment_text(name: str) -> str:
    value = str(os.getenv(name, "") or "").strip()

    if not value:
        raise Input001ShadowConfigError(
            f"{name} doit être renseigné lorsque "
            "le shadow INPUT001 est activé."
        )

    return value


def get_cyclos_shadow_config() -> CyclosShadowConfig:
    enabled = _environment_flag(
        "MLCFLUX_INPUT001_SHADOW_ENABLED"
    )

    if not enabled:
        return CyclosShadowConfig(enabled=False)

    dataset_id = _required_environment_text(
        "MLCFLUX_INPUT001_DATASET_ID"
    )
    native_currency_id = _required_environment_text(
        "MLCFLUX_INPUT001_CYCLOS_NATIVE_CURRENCY_ID"
    )
    currency_code = _required_environment_text(
        "MLCFLUX_INPUT001_CURRENCY_CODE"
    )

    exponent_raw = _required_environment_text(
        "MLCFLUX_INPUT001_CURRENCY_EXPONENT"
    )

    try:
        currency_exponent = int(exponent_raw, 10)
    except ValueError as exc:
        raise Input001ShadowConfigError(
            "MLCFLUX_INPUT001_CURRENCY_EXPONENT "
            "doit être un entier."
        ) from exc

    if currency_exponent < 0:
        raise Input001ShadowConfigError(
            "MLCFLUX_INPUT001_CURRENCY_EXPONENT "
            "ne peut pas être négatif."
        )

    return CyclosShadowConfig(
        enabled=True,
        dataset_id=dataset_id,
        native_currency_id=native_currency_id,
        currency_code=currency_code,
        currency_exponent=currency_exponent,
    )


def _default_snapshot_ref() -> str:
    return (
        "shadow-sync:"
        + datetime.now(UTC).isoformat(
            timespec="seconds"
        )
    )


def materialize_cyclos_shadow(
    raw_transactions: Sequence[Mapping[str, Any]],
    *,
    config: CyclosShadowConfig | None = None,
    snapshot_ref: str | None = None,
) -> dict[str, Any]:
    """
    Matérialise le dernier lot Cyclos dans input001.db.

    Le shadow est un miroir de contrôle :
    il ne remplace pas mlcflux.db et n'est pas encore utilisé
    par les analyses applicatives.
    """
    resolved = (
        config
        if config is not None
        else get_cyclos_shadow_config()
    )

    if not resolved.enabled:
        return {
            "enabled": False,
            "status": "disabled",
        }

    assert resolved.dataset_id is not None
    assert resolved.native_currency_id is not None
    assert resolved.currency_code is not None
    assert resolved.currency_exponent is not None

    currency_spec = CyclosCurrencySpec(
        native_currency_id=resolved.native_currency_id,
        currency_code=resolved.currency_code,
        currency_exponent=resolved.currency_exponent,
    )

    payload = build_cyclos_financial_dataset(
        raw_transactions,
        dataset_id=resolved.dataset_id,
        currency_specs={
            resolved.native_currency_id: currency_spec,
        },
        snapshot_ref=(
            snapshot_ref
            if snapshot_ref is not None
            else _default_snapshot_ref()
        ),
    )

    engine = create_input001_engine()

    materialize_financial_dataset(
        engine,
        payload,
    )

    reader = FinancialContractReader(engine)
    reader.validate_required_relations()

    metadata = reader.metadata_row()

    return {
        "enabled": True,
        "status": "success",
        "dataset_id": metadata["dataset_id"],
        "snapshot_ref": metadata["snapshot_ref"],
        "accounts": len(payload.accounts),
        "transactions": len(payload.transactions),
    }
