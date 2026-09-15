"""MLCFlux Financial Core.

Neutral persistence contract for financial facts. This package deliberately
sits next to the legacy INPUT001 contract while the migration is in progress.
"""

from .schema import CONTRACT_VERSION
from .writer import (
    FinancialCorePayload,
    FinancialCoreWriteError,
    publish_financial_core,
    validate_financial_core_payload,
)
from .reader import (
    FinancialCoreReadError,
    FinancialCoreSnapshot,
    get_current_publication_id,
    read_current_financial_core,
)
from .publication import (
    FinancialCoreCandidate,
    FinancialCorePublicationError,
    prepare_financial_core_candidate,
    publish_financial_core_candidate,
    validate_and_publish_financial_core,
)

__all__ = [
    "CONTRACT_VERSION",
    "FinancialCorePayload",
    "FinancialCoreWriteError",
    "publish_financial_core",
    "validate_financial_core_payload",
    "FinancialCoreReadError",
    "FinancialCoreSnapshot",
    "get_current_publication_id",
    "read_current_financial_core",
    "FinancialCoreCandidate",
    "FinancialCorePublicationError",
    "prepare_financial_core_candidate",
    "publish_financial_core_candidate",
    "validate_and_publish_financial_core",
]
