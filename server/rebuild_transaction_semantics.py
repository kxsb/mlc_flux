from __future__ import annotations

import argparse
import json

from server.services.transaction_semantics import rebuild_transaction_semantics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconstruit la couche transaction_semantics depuis la table transactions."
    )
    parser.add_argument("--date-from", default=None, help="Date de début YYYY-MM-DD.")
    parser.add_argument("--date-to", default=None, help="Date de fin YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, default=None, help="Limite de transactions, pour test.")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Ne pas supprimer les lignes existantes sur le périmètre avant recalcul.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    report = rebuild_transaction_semantics(
        start=args.date_from,
        end=args.date_to,
        limit=args.limit,
        reset=not args.no_reset,
    )

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
