from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from server.services.professional_economic_registry import (
    get_professional_economic_naf_sections,
    get_professional_economic_naf_codes,
    get_professional_economic_record,
    get_professional_economic_registry_summary,
)


professional_economic_registry_bp = Blueprint(
    "professional_economic_registry",
    __name__,
)


@professional_economic_registry_bp.route(
    "/api/economic-registry/summary",
    methods=["GET"],
)
def economic_registry_summary():
    try:
        return jsonify(get_professional_economic_registry_summary())
    except Exception as exc:
        current_app.logger.exception("Erreur /api/economic-registry/summary")
        return jsonify({"error": str(exc)}), 500


@professional_economic_registry_bp.route(
    "/api/economic-registry/naf-sections",
    methods=["GET"],
)
def economic_registry_naf_sections():
    try:
        return jsonify(get_professional_economic_naf_sections())
    except Exception as exc:
        current_app.logger.exception("Erreur /api/economic-registry/naf-sections")
        return jsonify({"error": str(exc)}), 500



@professional_economic_registry_bp.route(
    "/api/economic-registry/naf-codes",
    methods=["GET"],
)
def economic_registry_naf_codes():
    try:
        return jsonify(get_professional_economic_naf_codes())
    except Exception as exc:
        current_app.logger.exception("Erreur /api/economic-registry/naf-codes")
        return jsonify({"error": str(exc)}), 500


@professional_economic_registry_bp.route(
    "/api/economic-registry/pro/<professional_ref>",
    methods=["GET"],
)
def economic_registry_professional_record(professional_ref: str):
    try:
        payload = get_professional_economic_record(professional_ref)
        if payload.get("available") is True and payload.get("found") is False:
            return jsonify(payload), 404
        return jsonify(payload)
    except Exception as exc:
        current_app.logger.exception("Erreur /api/economic-registry/pro/%s", professional_ref)
        return jsonify({"error": str(exc)}), 500
