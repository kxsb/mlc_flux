from flask import Blueprint, jsonify, request

from server.services.info_content import (
    read_info_markdown,
    write_info_markdown,
)


info_content_bp = Blueprint("info_content", __name__)

MAX_INFO_MARKDOWN_LENGTH = 500_000


@info_content_bp.route("/api/info-content", methods=["GET"])
def get_info_content():
    return jsonify({
        "markdown": read_info_markdown(),
    })


@info_content_bp.route("/api/info-content", methods=["POST"])
def save_info_content():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Corps JSON invalide."
        }), 400

    markdown = payload.get("markdown")

    if not isinstance(markdown, str):
        return jsonify({
            "error": "Le champ 'markdown' doit être une chaîne."
        }), 400

    if len(markdown) > MAX_INFO_MARKDOWN_LENGTH:
        return jsonify({
            "error": (
                "Le contenu Markdown est trop volumineux "
                f"(maximum {MAX_INFO_MARKDOWN_LENGTH} caractères)."
            )
        }), 413

    write_info_markdown(markdown)

    return jsonify({
        "status": "ok",
        "message": "Documentation enregistrée.",
        "length": len(markdown),
    })
