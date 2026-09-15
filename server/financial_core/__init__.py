"""MLCFlux Financial Core.

Neutral persistence contract for financial facts.  This package deliberately
sits next to the legacy INPUT001 contract while the migration is in progress.
"""

from .schema import CONTRACT_VERSION
from .writer import FinancialCorePayload, FinancialCoreWriteError, publish_financial_core

__all__ = [
    "CONTRACT_VERSION",
    "FinancialCorePayload",
    "FinancialCoreWriteError",
    "publish_financial_core",
]
