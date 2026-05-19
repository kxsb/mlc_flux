import json
from datetime import UTC, datetime

from server.analytics import fetch_transactions
from server.routes.monetary_indicators import (
    _build_pilotage_lm3_yearly_items,
    _build_pilotage_reuse_yearly_items,
)
from server.services.pilotage_yearly_cache import (
    PILOTAGE_LM3_YEARLY_SERIES_KEY,
    PILOTAGE_REUSE_YEARLY_SERIES_KEY,
    replace_pilotage_yearly_cache_series,
)


def refresh_pilotage_yearly_cache() -> dict:
    rows = fetch_transactions()
    computed_at = datetime.now(UTC).isoformat()

    reuse_items = _build_pilotage_reuse_yearly_items(rows)
    lm3_items = _build_pilotage_lm3_yearly_items(rows)

    reuse_result = replace_pilotage_yearly_cache_series(
        PILOTAGE_REUSE_YEARLY_SERIES_KEY,
        reuse_items,
        computed_at=computed_at,
    )
    lm3_result = replace_pilotage_yearly_cache_series(
        PILOTAGE_LM3_YEARLY_SERIES_KEY,
        lm3_items,
        computed_at=computed_at,
    )

    return {
        "transactions_count": len(rows),
        "computed_at": computed_at,
        "reuse_yearly": reuse_result,
        "lm3_yearly": lm3_result,
    }


def main():
    result = refresh_pilotage_yearly_cache()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
