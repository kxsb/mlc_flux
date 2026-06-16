from __future__ import annotations

import argparse
import json

from server.services.monetary_indicators_adaptive import get_adaptive_monetary_indicators


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mlc", required=True)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    result = get_adaptive_monetary_indicators(args.mlc)

    if not args.debug:
        result = {
            key: value
            for key, value in result.items()
            if key != "debug"
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
