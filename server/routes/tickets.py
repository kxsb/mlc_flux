from flask import Blueprint, current_app, jsonify, request

from server.services.tickets import (
    TicketClosedError,
    TicketNotFoundError,
    TicketValidationError,
    add_public_message,
    create_ticket,
    get_public_ticket,
    list_public_tickets,
)


tickets_bp = Blueprint("tickets", __name__)


@tickets_bp.route("/api/tickets", methods=["GET"])
def public_tickets_index():
    try:
        result = list_public_tickets(
            category=request.args.get("category"),
            status=request.args.get("status"),
            search=request.args.get("q"),
            sort=request.args.get("sort", default="last_activity"),
            limit=request.args.get("limit", default=50, type=int),
            offset=request.args.get("offset", default=0, type=int),
        )
        return jsonify(result)

    except TicketValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        current_app.logger.exception(
            "Erreur inattendue lors de la récupération des tickets publics."
        )
        return jsonify({"error": "Erreur serveur interne."}), 500


@tickets_bp.route("/api/tickets", methods=["POST"])
def public_tickets_create():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Corps JSON invalide."}), 400

    try:
        result = create_ticket(
            author_name=payload.get("author_name"),
            author_email=payload.get("author_email"),
            title=payload.get("title"),
            category=payload.get("category"),
            body_markdown=payload.get("body_markdown"),
            source_page=payload.get("source_page"),
            context=payload.get("context"),
        )
        return jsonify({
            "status": "created",
            **result,
        }), 201

    except TicketValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        current_app.logger.exception(
            "Erreur inattendue lors de la création d'un ticket public."
        )
        return jsonify({"error": "Erreur serveur interne."}), 500


@tickets_bp.route("/api/tickets/<slug>", methods=["GET"])
def public_ticket_detail(slug):
    try:
        return jsonify(get_public_ticket(slug))

    except TicketValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    except TicketNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404

    except Exception:
        current_app.logger.exception(
            "Erreur inattendue lors de la récupération d'un ticket public."
        )
        return jsonify({"error": "Erreur serveur interne."}), 500


@tickets_bp.route("/api/tickets/<slug>/messages", methods=["POST"])
def public_ticket_add_message(slug):
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Corps JSON invalide."}), 400

    try:
        result = add_public_message(
            slug=slug,
            author_name=payload.get("author_name"),
            author_email=payload.get("author_email"),
            body_markdown=payload.get("body_markdown"),
        )
        return jsonify({
            "status": "created",
            **result,
        }), 201

    except TicketValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    except TicketNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404

    except TicketClosedError as exc:
        return jsonify({"error": str(exc)}), 409

    except Exception:
        current_app.logger.exception(
            "Erreur inattendue lors de la publication d'une réponse publique."
        )
        return jsonify({"error": "Erreur serveur interne."}), 500
