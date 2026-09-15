from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
)

from server.database import get_connection
from server.services.contract_analytics import (
    ContractAnalyticsError,
    get_contract_overview,
)


contract_analytics_bp = Blueprint(
    "contract_analytics",
    __name__,
)


@contract_analytics_bp.route(
    "/api/neutral/overview",
    methods=["GET"],
)
def neutral_overview():
    start = (
        request.args.get(
            "start",
            default="",
            type=str,
        ).strip()
        or None
    )

    end = (
        request.args.get(
            "end",
            default="",
            type=str,
        ).strip()
        or None
    )

    connection = get_connection()

    try:
        result = get_contract_overview(
            connection,
            start=start,
            end=end,
        )

        return jsonify(result)

    except ContractAnalyticsError as exc:
        return jsonify({
            "available": False,
            "error": str(exc),
        }), 400

    finally:
        connection.close()


@contract_analytics_bp.route(
    "/neutral-preview",
    methods=["GET"],
)
def neutral_preview():
    return render_template(
        "neutral_preview.html"
    )
