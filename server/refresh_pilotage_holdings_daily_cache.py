import json

from server.services.pilotage_holdings_daily_cache import (
    refresh_pilotage_holdings_daily_cache,
)


def main():
    result = refresh_pilotage_holdings_daily_cache()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
