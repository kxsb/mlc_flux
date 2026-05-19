from flask import Blueprint, jsonify, request
from server.analytics import (
    compute_global_stats,
    get_available_years,
    get_available_period_bounds,
    compute_network_data,
    compute_professionals_ranking,
    get_professional_detail,
    get_professionals_map_data,
    compute_zip_territorial_activity,
    compute_sector_activity,
    compute_stats_charts,
)
from server.utils.sync_auth import require_sync_token

legacy_api_bp = Blueprint("legacy_api", __name__)


@legacy_api_bp.route("/api/health", methods=["GET"])
def legacy_health():
    return jsonify({"status": "ok"})


@legacy_api_bp.route("/api/years", methods=["GET"])
def years():
    return jsonify(get_available_years())


@legacy_api_bp.route("/api/period-bounds", methods=["GET"])
def period_bounds():
    return jsonify(get_available_period_bounds())


@legacy_api_bp.route("/api/stats", methods=["GET"])
def stats():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")
    return jsonify(compute_global_stats(start=start, end=end, year=year))


@legacy_api_bp.route("/api/network", methods=["GET"])
def network():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    include_operators_raw = str(
        request.args.get("include_operators", default="", type=str) or ""
    ).strip().lower()

    include_operators = include_operators_raw in {
        "1",
        "true",
        "yes",
        "on",
    }

    return jsonify(
        compute_network_data(
            start=start,
            end=end,
            year=year,
            include_operators=include_operators,
        )
    )


@legacy_api_bp.route("/api/pros", methods=["GET"])
def pros():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")
    return jsonify(compute_professionals_ranking(start=start, end=end, year=year))


@legacy_api_bp.route("/api/professionals-map", methods=["GET"])
def professionals_map():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    return jsonify(
        get_professionals_map_data(
            start=start,
            end=end,
            year=year,
        )
    )


@legacy_api_bp.route("/api/territories/zip", methods=["GET"])
def territories_zip():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    return jsonify(
        compute_zip_territorial_activity(
            start=start,
            end=end,
            year=year,
        )
    )


@legacy_api_bp.route("/api/sectors/activity", methods=["GET"])
def sectors_activity():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    return jsonify(
        compute_sector_activity(
            start=start,
            end=end,
            year=year,
        )
    )


@legacy_api_bp.route("/api/professionnels", methods=["GET"])
def professionnels():
    ranking = compute_professionals_ranking()
    pros = [row["Professionnel"] for row in ranking if row.get("Professionnel")]
    return jsonify(pros)


@legacy_api_bp.route("/api/pro/<num_professionnel>", methods=["GET"])
def pro_detail(num_professionnel):
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    result = get_professional_detail(
        num_professionnel,
        start=start,
        end=end,
        year=year,
    )

    if result is None:
        return jsonify({"error": "Professionnel introuvable"}), 404

    return jsonify(result)


@legacy_api_bp.route("/api/stats_charts", methods=["GET"])
def stats_charts():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    result = compute_stats_charts(start=start, end=end, year=year)

    # compat ancienne version frontend
    if "weekly" in result and "weekly_avg" not in result:
        result["weekly_avg"] = result["weekly"]

    return jsonify(result)


def _format_sync_message(fetched, written):
    fetched_label = "transaction vérifiée" if fetched == 1 else "transactions vérifiées"
    written_label = (
        "transaction écrite / upsertée"
        if written == 1
        else "transactions écrites / upsertées"
    )

    return (
        "Synchronisation terminée : "
        f"{fetched} {fetched_label}, "
        f"{written} {written_label}."
    )


@legacy_api_bp.route("/api/reload", methods=["POST"])
def reload_data():
    auth_error = require_sync_token()
    if auth_error is not None:
        return auth_error

    from server.sync_transactions import run_sync

    result = run_sync()
    fetched = result["fetched"]
    written = result["written"]

    return jsonify({
        "status": "ok",
        "rows": written,
        "fetched": fetched,
        "written": written,
        # Alias de compatibilité pour d'éventuels appelants historiques.
        "inserted": written,
        "message": _format_sync_message(fetched, written),
    })
