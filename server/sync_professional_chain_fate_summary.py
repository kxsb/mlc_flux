from __future__ import annotations

import argparse
import json
import os

from server.services.professional_chain_fate_analytics import (
    compute_professional_chain_fate_summary,
    write_professional_chain_fate_summary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pré-calcule le résumé de trajectoires professionnelles pour une instance MLCFlux."
    )
    parser.add_argument("--mlc", choices=["graine", "gonette"])
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.mlc:
        os.environ["MLCFLUX_DEFAULT_MLC_ID"] = args.mlc
        os.environ["MLCFLUX_ACTIVE_MLC_ID"] = args.mlc

    payload = compute_professional_chain_fate_summary()
    write_professional_chain_fate_summary(payload)

    primary_key = payload["primary_model"]
    primary = payload["models"][primary_key]
    extended = payload["models"]["u_to_p_plus_t_to_p_seeds"]

    compact = {
        "mlc_id": (
            os.getenv("MLCFLUX_ACTIVE_MLC_ID")
            or os.getenv("MLCFLUX_DEFAULT_MLC_ID")
        ),
        "generated_at": payload["generated_at"],
        "metadata": payload["metadata"],
        "primary_model": primary_key,
        "primary": {
            "matched_share_of_p_to_t": primary["tracked_exit_to_t"]["matched_share_of_p_to_t"],
            "median_days_before_exit": primary["tracked_exit_to_t"]["summary"]["delay_days"].get("median"),
            "max_depth_before_exit": primary["tracked_exit_to_t"]["summary"]["depth"].get("max"),
            "quasi_immediate_direct_exit": primary["focus_indicators"]["quasi_immediate_direct_exit_depth0_le_7d"],
            "deep_chains_depth_ge_3": primary["focus_indicators"]["deep_chains_depth_ge_3"],
        },
        "extended_control_model": {
            "matched_share_of_p_to_t": extended["tracked_exit_to_t"]["matched_share_of_p_to_t"],
        },
    }

    print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
