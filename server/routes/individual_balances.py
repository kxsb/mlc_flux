from flask import Blueprint, jsonify, request

from server.services.individual_balance_analytics import (
    get_individual_balance_daily_series,
    get_individual_balance_distribution,
    get_individual_balance_period_summary,
    get_individual_balance_status,
    parse_optional_iso_date,
)


individual_balances_bp = Blueprint("individual_balances", __name__)


@individual_balances_bp.route("/api/individual-balances/status", methods=["GET"])
def individual_balances_status():
    return jsonify({
        "status": "ok",
        **get_individual_balance_status(),
    })


@individual_balances_bp.route("/api/individual-balances/daily", methods=["GET"])
def individual_balances_daily():
    try:
        requested_start = parse_optional_iso_date(request.args.get("start"), "start")
        requested_end = parse_optional_iso_date(request.args.get("end"), "end")
        payload = get_individual_balance_daily_series(
            requested_start=requested_start,
            requested_end=requested_end,
        )
    except ValueError as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400

    return jsonify({
        "status": "ok",
        **payload,
    })


@individual_balances_bp.route("/api/individual-balances/distribution", methods=["GET"])
def individual_balances_distribution():
    try:
        requested_date = parse_optional_iso_date(request.args.get("date"), "date")
        payload = get_individual_balance_distribution(
            requested_date=requested_date,
        )
    except ValueError as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400

    return jsonify({
        "status": "ok",
        **payload,
    })



@individual_balances_bp.route("/api/individual-balances/period-summary", methods=["GET"])
def individual_balances_period_summary():
    try:
        requested_start = parse_optional_iso_date(request.args.get("start"), "start")
        requested_end = parse_optional_iso_date(request.args.get("end"), "end")
        payload = get_individual_balance_period_summary(
            requested_start=requested_start,
            requested_end=requested_end,
        )
    except ValueError as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 400

    return jsonify({
        "status": "ok",
        **payload,
    })
